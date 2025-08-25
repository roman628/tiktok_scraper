#!/usr/bin/env python3
"""
Robust TikTok Data Collector - Main Orchestrator
Manages the complete pipeline for TikTok data collection.
"""

import os
import sys
import json
import argparse
import asyncio
import time
import signal
import queue
import multiprocessing as mp
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models import VideoData, ProcessingState, Comment
from src.url_processor import URLProcessor  
from utils.resource_manager import ResourceManager
from utils.data_manager import DataManager
from src.database_manager import DatabaseOrJsonManager
from src.video_extractor import VideoExtractor, load_whisper_model
from src.comment_extractor import CommentExtractor
from src.transcript_extractor import TranscriptExtractor
from utils.display_manager import create_display
from utils.worker_progress import WorkerProgress
from utils.collector_registry import CollectorRegistry, CollectorConfig
from utils.worker_manager import WorkerManager

class RobustTikTokProcessor:
    """Main processor for TikTok data collection."""
    
    def __init__(self, args, config=None):
        self.args = args
        self.master_file = None  # Legacy - database is primary storage
        self.source_file = None
        self.shutdown_requested = False
        self.config = config or {}
        
        # Initialize components - always use database
        self.data_manager = DatabaseOrJsonManager(self.config)
        self.video_extractor = VideoExtractor(
            output_dir=args.output,
            quality=args.quality,
            proxy=args.proxy
        )
        self.comment_extractor = None
        self.resource_manager = ResourceManager()
        
        # MS_TOKEN for comments
        self.ms_token = None
        
        # Processing state
        self.state = ProcessingState()
        
        # Initialize collector registry
        self.collector_registry = CollectorRegistry()
        self.config = {}  # Will be loaded later
        
    async def cleanup(self):
        """Cleanup resources on shutdown."""
        self.shutdown_requested = True
        self.save_progress()

        cleanup_tasks = []
        if self.comment_extractor:
            cleanup_tasks.append(self.comment_extractor.cleanup())

        # video_extractor cleanup is synchronous
        self.video_extractor.cleanup()

        if cleanup_tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*cleanup_tasks), timeout=5.0)
            except asyncio.TimeoutError:
                print("Warning: Async cleanup timed out, forcing browser kill")
                self.resource_manager.kill_browser_processes()
        
        print("Cleanup completed")
    
    def get_ms_token(self) -> bool:
        """Get MS_TOKEN from args or environment."""
        self.ms_token = self.args.ms_token or os.getenv('MS_TOKEN')
        if self.ms_token:
            print(f"Using MS_TOKEN: {self.ms_token[:20]}...")
            return True
        return False
    
    async def validate_ms_token(self) -> bool:
        """Validate MS_TOKEN by attempting to initialize API."""
        if not self.ms_token:
            return False
        
        try:
            self.comment_extractor = CommentExtractor(
                ms_token=self.ms_token,
                max_comments=self.args.max_comments
            )
            await self.comment_extractor._initialize_api()
            print("MS_TOKEN validated successfully")
            return True
        except Exception as e:
            print(f"MS_TOKEN validation failed: {e}")
            return False
    
    def load_existing_progress(self):
        """Load existing URLs from master file for duplicate detection."""
        # This is now handled by DataManager
        # Handle both DatabaseOrJsonManager and DataManager
        if hasattr(self.data_manager, 'existing_urls'):
            existing_count = len(self.data_manager.existing_urls)
        else:
            existing_count = len(self.data_manager.get_existing_urls())
        if existing_count > 0:
            print(f"Loaded {existing_count} existing URLs from {self.master_file}")
    
    def save_progress(self):
        """Save current progress state."""
        # Progress saving disabled to avoid creating clutter files
        pass
    
    def filter_urls(self, urls: List[str]) -> List[str]:
        """Filter out already processed URLs."""
        # Skip filtering if force_redownload is enabled
        if self.args.force_redownload:
            return urls
        
        filtered = []
        for url in urls:
            if not self.data_manager.is_duplicate(url):
                filtered.append(url)
        return filtered
    
    def _start_watchdog_thread(self, workers, shutdown_event, result_queue=None, status_queue=None):
        """Start a watchdog thread to monitor for deadlocks and worker health.
        
        Args:
            workers: List of worker processes
            shutdown_event: Event to trigger shutdown
            result_queue: Queue where workers send results (for progress tracking)
            status_queue: Queue where workers send status updates (for heartbeat tracking)
        """
        def watchdog():
            last_progress_time = time.time()
            last_processed_count = 0
            stall_count = 0
            last_heartbeat_time = time.time()
            
            # For recalibration mode, be more patient (transcription can take time)
            is_recalibrate = getattr(self, 'recalibrate_mode', False)
            stall_timeout = 600 if is_recalibrate else 300  # 10 min for recalibrate, 5 min normal
            max_stall_checks = 6 if is_recalibrate else 3  # More patience for recalibration
            
            while not shutdown_event.is_set():
                time.sleep(10)  # Check every 10 seconds
                
                # Check if any workers are alive
                alive_count = sum(1 for w in workers if w.is_alive())
                
                if alive_count == 0 and not shutdown_event.is_set():
                    print("\n🔴 Watchdog: All workers dead unexpectedly, setting shutdown event")
                    shutdown_event.set()
                    break
                
                # Track actual progress via the state object
                current_processed = getattr(self.state, 'processed_urls', 0)
                current_time = time.time()
                
                # Check if we're making progress
                if current_processed > last_processed_count:
                    # Progress detected! Reset stall detection
                    last_progress_time = current_time
                    last_processed_count = current_processed
                    stall_count = 0  # Reset stall counter
                    if is_recalibrate:
                        print(f"  ✅ Watchdog: Progress detected - {current_processed} URLs processed")
                
                # Check for heartbeats from status queue (if available)
                if status_queue:
                    try:
                        # Non-blocking check for any status updates
                        import queue
                        while True:
                            try:
                                status = status_queue.get_nowait()
                                if status.get('type') == 'heartbeat':
                                    last_heartbeat_time = current_time
                                # Put it back for main loop to process
                                status_queue.put(status)
                                break
                            except queue.Empty:
                                break
                    except:
                        pass  # Queue might not be available
                
                # Check for extended stalls (workers alive but not producing results)
                time_since_progress = current_time - last_progress_time
                time_since_heartbeat = current_time - last_heartbeat_time
                
                # Only consider it a stall if no progress AND no recent heartbeats
                if time_since_progress > 120 and time_since_heartbeat > 60:  # 2 min no progress, 1 min no heartbeat
                    stall_count += 1
                    if stall_count >= max_stall_checks:
                        print(f"\n🔴 Watchdog: Extended stall detected (no progress for {int(time_since_progress)}s), forcing shutdown")
                        print(f"    Last progress: {last_processed_count} URLs processed")
                        print(f"    Workers alive: {alive_count}/{len(workers)}")
                        shutdown_event.set()
                        break
                    else:
                        print(f"\n⚠️ Watchdog: Possible stall detected (check {stall_count}/{max_stall_checks})")
                        print(f"    No progress for {int(time_since_progress)}s")
                        print(f"    Workers alive: {alive_count}/{len(workers)}")
                
                # Log periodic health status
                if int(current_time) % 60 == 0:  # Every minute
                    status_msg = f"  🟢 Watchdog: {alive_count}/{len(workers)} workers alive"
                    if current_processed > 0:
                        status_msg += f", {current_processed} URLs processed"
                    print(status_msg)
        
        watchdog_thread = threading.Thread(target=watchdog, daemon=True, name="CollectorWatchdog")
        watchdog_thread.start()
        return watchdog_thread
    
    def _drain_queues_forcibly(self, result_queue, display_queue, display_manager):
        """Forcibly drain queues when deadlock is detected or during cleanup."""
        drained_results = 0
        drained_display = 0
        
        # Drain result queue
        try:
            while True:
                try:
                    result = result_queue.get_nowait()
                    drained_results += 1
                    if drained_results > 1000:  # Prevent infinite loop
                        print(f"  ⚠️ Stopped draining result queue after {drained_results} items")
                        break
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"  Error draining result queue: {e}")
                    break
        except Exception as e:
            print(f"  Failed to drain result queue: {e}")
        
        # Drain display queue
        try:
            while True:
                try:
                    msg = display_queue.get_nowait()
                    if display_manager:
                        try:
                            display_manager.process_update(msg)
                        except:
                            pass  # Display might be stopped already
                    drained_display += 1
                    if drained_display > 1000:  # Prevent infinite loop
                        print(f"  ⚠️ Stopped draining display queue after {drained_display} items")
                        break
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"  Error draining display queue: {e}")
                    break
        except Exception as e:
            print(f"  Failed to drain display queue: {e}")
        
        if drained_results > 0 or drained_display > 0:
            print(f"  Drained {drained_results} results, {drained_display} display messages")
    
    async def process_urls(self, urls: List[str], download_kwargs: Dict[str, Any]):
        """Process all URLs using worker processes with robust management."""
        self.state.total_urls = len(urls)
        print(f"\nProcessing {len(urls)} URLs with {self.args.workers} worker(s)...")
        
        # Initialize worker manager for robust tracking
        worker_manager = WorkerManager(
            db_config=self.config.get('database', {}),
            worker_count=self.args.workers
        )
        worker_manager.init_worker_tracking_table()
        worker_manager.cleanup_stuck_urls()
        
        # Setup multiprocessing components
        manager = mp.Manager()
        url_queue = manager.Queue()
        result_queue = manager.Queue()
        display_queue = manager.Queue()
        status_queue = worker_manager.status_queue  # Dedicated status queue
        shutdown_event = manager.Event()
        
        # Add URLs to queue
        for url in urls:
            url_queue.put(url)
        
        # Add sentinel values
        for _ in range(self.args.workers):
            url_queue.put(None)
        
        # Setup display - detect subprocess and force simple mode
        display_mode = getattr(self.args, 'display_mode', 'auto')
        
        # Force simple mode if running as subprocess
        if os.environ.get('COLLECTOR_SUBPROCESS') or not sys.stdout.isatty():
            display_mode = 'simple'
        
        raw_log_path = None
        if getattr(self.args, 'raw_log', False):
            # Use logs directory from config
            logs_dir = self.config.get('display', {}).get('raw_log_dir', 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            raw_log_path = os.path.join(logs_dir, f"processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        display_manager = create_display(
            self.args.workers,
            len(urls),
            mode=display_mode,
            raw_log_path=raw_log_path
        )
        display_manager.start()
        
        # Setup Whisper config if needed
        whisper_config = None
        if self.args.whisper:
            from utils.device_manager import DeviceManager
            device_manager = DeviceManager()
            device = device_manager.get_best_device(force_cpu=self.args.force_cpu)
            whisper_config = {
                'model_size': getattr(self.args, 'whisper_model', 'small.en'),
                'device': device.lower(),
                'compute_type': 'float16' if device.lower() in ['cuda', 'mps'] else 'int8'
            }
        
        # Create workers with enhanced management
        workers = []
        from utils.worker_manager import enhanced_worker_process
        for i in range(self.args.workers):
            worker_manager.register_worker(i)
            p = mp.Process(
                target=enhanced_worker_process,
                args=(i, url_queue, result_queue, status_queue, display_queue, shutdown_event,
                      self.args, download_kwargs, self.ms_token, whisper_config, len(urls), self.config)
            )
            p.start()
            workers.append(p)
        
        # Start watchdog thread for additional monitoring
        watchdog = self._start_watchdog_thread(workers, shutdown_event, result_queue, status_queue)
        
        # Process results
        processed = 0
        failed = 0
        workers_done = 0
        
        # Deadlock detection variables
        loop_start_time = time.time()
        max_processing_time = len(urls) * 300  # 5 minutes per URL max
        last_progress_time = time.time()
        last_workers_done = 0
        stall_check_interval = 60  # Check for stalls every 60 seconds
        
        try:
            # Use database-based completion detection instead of queue counting
            while not worker_manager.detect_completion(workers):
                loop_iteration_start = time.time()
                
                # DEADLOCK DETECTION: Check for overall timeout
                if loop_iteration_start - loop_start_time > max_processing_time:
                    print(f"\n⚠️ WARNING: Processing timeout after {max_processing_time}s, forcing shutdown")
                    shutdown_event.set()
                    break
                
                # Process status updates from workers
                status_updates = worker_manager.process_status_updates(timeout=0.1)
                
                # Check worker health and detect stalls
                worker_health = worker_manager.check_worker_health()
                active_count = worker_manager.get_active_worker_count()
                completed_count = worker_manager.get_completed_worker_count()
                
                # Track workers_done for backward compatibility
                workers_done = completed_count
                
                # Improved stall detection with database tracking
                if completed_count == last_workers_done:
                    if loop_iteration_start - last_progress_time > stall_check_interval:
                        print(f"\n⚠️ WARNING: No progress for {stall_check_interval}s, checking worker health...")
                        alive_workers = sum(1 for w in workers if w.is_alive())
                        print(f"  Alive: {alive_workers}/{len(workers)}, Active: {active_count}, Completed: {completed_count}")
                        
                        # Check for dead workers and reassign their work
                        dead_workers = worker_manager.cleanup_dead_workers(workers)
                        if dead_workers:
                            print(f"  ✓ Cleaned up {len(dead_workers)} dead workers and reassigned their URLs")
                        
                        if alive_workers == 0 and completed_count < self.args.workers:
                            print("  ❌ All workers dead before completion")
                            break
                        elif active_count == 0 and completed_count == self.args.workers:
                            print("  ✓ All workers completed successfully")
                            break
                else:
                    last_progress_time = loop_iteration_start
                    last_workers_done = completed_count
                    stall_check_interval = 60  # Reset to normal interval
                
                # Update display
                while not display_queue.empty():
                    try:
                        msg = display_queue.get_nowait()
                        display_manager.process_update(msg)
                    except queue.Empty:
                        break
                    except Exception as e:
                        print(f"Display queue error: {e}")
                        break
                
                display_manager.update()
                
                # Process results
                try:
                    result = result_queue.get(timeout=0.1)
                    if result is None:
                        workers_done += 1
                        last_progress_time = time.time()  # Reset progress timer
                    elif result['success']:
                        processed += 1
                        self.state.processed_urls = processed
                    else:
                        failed += 1
                        self.state.failed_urls.append(result.get('url', 'unknown'))
                        if result.get('deleted') and self.source_file:
                            URLProcessor.remove_url_from_file(result['url'], self.source_file)
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Result queue error: {e}")
                    continue
                
                # Check for shutdown
                if self.shutdown_requested:
                    shutdown_event.set()
                    break
        
        except KeyboardInterrupt:
            print("\nShutdown requested...")
            shutdown_event.set()
        
        finally:
            # Signal shutdown to all workers
            shutdown_event.set()
            
            # Improved worker termination with better timeouts
            print("\nWaiting for workers to finish...")
            for i, p in enumerate(workers):
                p.join(timeout=10)  # Increased timeout from 5 to 10 seconds
                if p.is_alive():
                    print(f"Worker {i} didn't respond to shutdown, terminating forcibly")
                    p.terminate()
                    # Give it a moment to clean up
                    p.join(timeout=2)
                    if p.is_alive():
                        # Last resort - force kill
                        try:
                            print(f"Worker {i} still alive, force killing")
                            p.kill()
                            p.join(timeout=1)
                        except Exception as e:
                            print(f"Failed to kill worker {i}: {e}")
            
            # Drain any remaining messages from queues to prevent deadlock
            print("Draining queues...")
            self._drain_queues_forcibly(result_queue, display_queue, display_manager)
            
            # Stop display
            display_manager.stop()
            
            # Final stats
            self.save_progress()
            print(f"\nCompleted: {processed}/{len(urls)} URLs processed, {failed} failed")
    
    # process_single_url removed - now using process_tiktok_url in workers
    
    async def cleanup_api_session(self):
        """Clean up API sessions."""
        if self.comment_extractor:
            await self.comment_extractor.cleanup()

# MultiprocessCoordinator class removed - functionality merged into RobustTikTokProcessor

def load_cached_whisper_model(model_config: Dict[str, Any]):
    """Load Whisper model using configuration.
    
    Args:
        model_config: Configuration dictionary with model parameters
        
    Returns:
        Loaded Whisper model or None
    """
    if not model_config:
        return None
        
    try:
        from faster_whisper import WhisperModel
        
        # Extract configuration
        model_size = model_config.get('model_size', 'small.en')
        device = model_config.get('device', 'cpu')
        compute_type = model_config.get('compute_type', 'int8')
        
        print(f"Worker loading Whisper model: {model_size} on {device.upper()}")
        
        # Load model - will use HF cache automatically if already downloaded
        model = WhisperModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type
        )
        return model
        
    except Exception as e:
        print(f"Failed to load Whisper model: {e}")
        return None

def worker_process_wrapper(worker_id: int, url_queue, result_queue, display_queue, 
                           shutdown_event, args, download_kwargs: Dict[str, Any], 
                           ms_token: Optional[str], whisper_config: Dict[str, Any] = None,
                           total_urls: int = 0, config: Optional[Dict[str, Any]] = None):
    """Synchronous wrapper to run the async worker process."""
    try:
        asyncio.run(worker_process(
            worker_id, url_queue, result_queue, display_queue,
            shutdown_event, args, download_kwargs, ms_token,
            whisper_config, total_urls, config
        ))
    except KeyboardInterrupt:
        # Let the shutdown event handle termination
        pass

async def process_tiktok_url(url: str, video_extractor: VideoExtractor,
                             comment_extractor: Optional[CommentExtractor],
                             data_manager: DataManager,
                             progress: WorkerProgress,
                             download_kwargs: Dict[str, Any],
                             args,
                             ms_token: Optional[str],
                             whisper_config: Optional[Dict[str, Any]] = None,
                             shutdown_event: Optional[mp.Event] = None,
                             config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process a single TikTok URL with consistent flattened output.
    
    Returns:
        Dict with 'success' bool and 'video_data' if successful or 'error' if failed.
    """
    # Check if we're in recalibrate mode
    recalibrate_mode = download_kwargs.get('recalibrate_mode', False)
    recalibrate_components = download_kwargs.get('recalibrate_components', [])
    
    # Check data collection config
    data_collection_config = config.get('data_collection', {}) if config else {}
    
    # Build list of enabled collectors from boolean flags
    enabled_collectors = []
    if data_collection_config.get('metadata', True):
        enabled_collectors.append('metadata')
    if data_collection_config.get('transcription', True):
        enabled_collectors.append('transcription')
    if data_collection_config.get('comments', False):
        enabled_collectors.append('comments')
    
    # In recalibrate mode, log what we're doing
    if recalibrate_mode:
        progress.send_log(f"Recalibrating: {', '.join(recalibrate_components)}", 'info')
    
    # Check for duplicate (unless force_redownload is enabled or recalibrate mode)
    if not args.force_redownload and not recalibrate_mode and data_manager.is_duplicate(url):
        progress.send_log("Skipping duplicate", 'info')
        return {'success': True, 'duplicate': True}
    
    # Check shutdown
    if shutdown_event and shutdown_event.is_set():
        return {'success': False, 'error': 'Shutdown requested'}
    
    try:
        # In recalibrate mode, handle different component types
        if recalibrate_mode:
            # For metadata-only recalibration, we don't need to download the video
            if 'metadata' in recalibrate_components and 'transcripts' not in recalibrate_components:
                progress.send_log("Fetching metadata only (no download needed)", 'info')
                # Will be handled by video_extractor with metadata_only flag
            
            # For OCR recalibration, check for existing video files
            elif 'ocr' in recalibrate_components:
                import glob
                url_proc = URLProcessor()
                video_id = url_proc.extract_video_id(url)
                video_files = glob.glob(f"{args.output}/*{video_id}*")
                
                if video_files:
                    progress.send_log(f"Found existing file for OCR: {video_files[0]}", 'info')
                else:
                    progress.send_log("No local file found, will download for OCR extraction", 'info')
            
            # For transcript recalibration
            elif 'transcripts' in recalibrate_components:
                # Try to find existing video file for this URL
                import glob
                
                # Extract video ID from URL
                # Import moved to top of file to avoid repeated imports
                url_proc = URLProcessor()
                video_id = url_proc.extract_video_id(url)
                
                # Look for existing video file in configured output directory
                video_files = glob.glob(f"{args.output}/*{video_id}*")
                
                if video_files:
                    # File exists, just transcribe it
                    progress.send_log(f"Found existing file: {video_files[0]}", 'info')
                    # We'll call download_single_video which should detect the existing file
                else:
                    # No local file, need to download it first
                    progress.send_log("No local file found, downloading video first", 'info')
                    # The download_single_video call below will handle downloading
        
        # For hashtag-only recalibration, skip video download entirely
        if recalibrate_mode and recalibrate_components == ['hashtags']:
            # No need to download anything for hashtag extraction
            video_result = {'success': True, 'metadata': {}, 'file_path': None}
            metadata = {}
            progress.send_log("Skipping download for hashtag-only recalibration", 'info')
        else:
            # Download video (or use existing in recalibrate mode)
            progress.start_download()
            
            # Setup whisper model if needed - check if transcription is enabled
            whisper_model = None
            use_whisper = 'transcription' in enabled_collectors and download_kwargs.get('use_whisper', False)
            
            # Force whisper for transcript recalibration
            if recalibrate_mode and 'transcripts' in recalibrate_components:
                use_whisper = True
                args.whisper = True
            
            if args.whisper and whisper_config and use_whisper:
                whisper_model = whisper_config.get('model')
            
            # Check if we only need metadata (no video download)
            metadata_only = recalibrate_mode and 'metadata' in recalibrate_components and \
                           'transcripts' not in recalibrate_components and \
                           'ocr' not in recalibrate_components
            
            video_result = video_extractor.download_single_video(
                url,
                audio_only=download_kwargs.get('audio_only', False),
                use_whisper=use_whisper,
                whisper_model=whisper_model,
                whisper_device=whisper_config.get('device', 'CPU').upper() if whisper_config else 'CPU',
                shutdown_event=shutdown_event,
                progress_callback=progress,
                metadata_only=metadata_only  # Add metadata_only flag
                # In recalibrate mode, it will download if file doesn't exist, or use existing if it does
            )
            
            metadata = video_result.get('metadata', {})
        
        # Skip metadata handling for hashtag-only recalibration
        if recalibrate_mode and recalibrate_components == ['hashtags']:
            # For hashtag-only, jump directly to database operations
            metadata = {}
            video_data = {}
        else:
            progress.send_progress('downloading', 100)
            
            if not video_result['success']:
                error_msg = video_result.get('error', 'Download failed')
                progress.report_error('download', error_msg)
                
                # Handle deleted videos
                if video_result.get('deleted'):
                    return {'success': False, 'error': error_msg, 'deleted': True}
                return {'success': False, 'error': error_msg}
            
            metadata = video_result['metadata']
        
        # Extract metadata (skip for hashtag-only recalibration)
        if not (recalibrate_mode and recalibrate_components == ['hashtags']):
            progress.start_metadata_extraction()
            progress.send_log("Processing metadata...", 'progress')
            if 'likes' in metadata:
                progress.complete_metadata(
                    metadata.get('likes', 0),
                    metadata.get('comment_count', 0)
                )
            else:
                progress.send_progress('metadata', 100)
                progress.send_log("Metadata extracted", 'success')
        
        # Handle transcription
        transcript = metadata.get('whisper_transcription', '')
        if transcript:
            progress.send_progress('transcribing', 100)
            progress.complete_transcription(metadata.get('duration', 0))
        elif download_kwargs.get('use_whisper', False):
            progress.skip_transcription("No audio found")
        else:
            progress.skip_transcription("Whisper not enabled")
        
        # Extract comments if available and enabled
        comments = []
        if 'comments' in enabled_collectors and comment_extractor and ms_token and (not shutdown_event or not shutdown_event.is_set()):
            progress.start_comments()
            try:
                comment_objects = await comment_extractor.extract_comments(url)
                comments = [comment.to_dict() for comment in comment_objects]
                progress.complete_comments(len(comments))
            except Exception as e:
                progress.report_error('comments', str(e))
        
        # Create FLATTENED data structure (skip for hashtag-only recalibration)
        if not (recalibrate_mode and recalibrate_components == ['hashtags']):
            video_data = {
            'title': metadata.get('title', ''),
            'description': metadata.get('description', ''),
            'duration': metadata.get('duration', 0),
            'video_id': metadata.get('video_id', ''),
            'url': url,
            'uploader': metadata.get('uploader', ''),
            'uploader_id': metadata.get('uploader_id', ''),
            'uploader_url': metadata.get('uploader_url', ''),
            'view_count': metadata.get('view_count', 0),
            'like_count': metadata.get('like_count', 0),
            'comment_count': metadata.get('comment_count', 0),
            'repost_count': metadata.get('repost_count', 0),
            'save_count': metadata.get('save_count', 0),
            'share_count': metadata.get('share_count', 0),
            'hashtags': metadata.get('hashtags', []),
            'upload_date': metadata.get('upload_date', ''),
            'timestamp': metadata.get('timestamp', 0),
            'width': metadata.get('width', 0),
            'height': metadata.get('height', 0),
            'filesize': metadata.get('filesize', 0),
            'format': metadata.get('format', ''),
            'downloaded_at': metadata.get('downloaded_at', ''),
            'downloaded_with': metadata.get('downloaded_with', ''),
            'platform': metadata.get('platform', ''),
            'whisper_transcription': transcript,
                'transcription_timestamp': metadata.get('transcription_timestamp', ''),
                'top_comments': comments,
                'comments_extracted': len(comments) > 0,
                'comments_extracted_at': datetime.now().isoformat() if comments else ''
            }
        
        # Save to master file
        progress.start_saving()
        
        # In recalibrate mode, update existing video; otherwise insert new
        if recalibrate_mode:
            # Get existing video ID from database for updates
            existing_video = None
            if hasattr(data_manager, 'manager') and hasattr(data_manager.manager, 'get_connection'):
                try:
                    with data_manager.manager.get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT id, video_id FROM videos WHERE url = %s",
                                (url,)
                            )
                            row = cursor.fetchone()
                            if row:
                                existing_video = {'id': row[0], 'video_id': row[1]}
                except Exception as e:
                    progress.send_log(f"Failed to find existing video: {e}", 'error')
            
            if not existing_video:
                progress.send_log("Video not found in database for recalibration", 'error')
                return {'success': False, 'error': 'Video not found for recalibration'}
            
            # Handle different recalibration components
            success = True
            
            # Update metadata if requested
            if 'metadata' in recalibrate_components:
                metadata_fields = {
                    'track_name': metadata.get('track_name'),
                    'track_artist': metadata.get('track_artist'),
                    'duration': metadata.get('duration'),
                    'width': metadata.get('width'),
                    'height': metadata.get('height')
                }
                
                # Update metadata in database
                success = data_manager.manager.update_video_metadata(
                    existing_video['video_id'], 
                    metadata_fields
                )
                if success:
                    progress.send_log("Updated video metadata", 'success')
                else:
                    progress.send_log("Failed to update metadata", 'error')
            
            # Update transcription if requested and available
            if 'transcripts' in recalibrate_components and metadata.get('whisper_transcription'):
                # Update transcription (handled by existing logic)
                success = data_manager.update_video_components(video_data)
                if success:
                    progress.send_log("Updated transcription", 'success')
                else:
                    progress.send_log("Failed to update transcription", 'error')
            
            # Extract hashtags if requested
            if 'hashtags' in recalibrate_components:
                try:
                    from database.extract_hashtags import extract_and_save_hashtags_for_video
                    from psycopg2.extras import RealDictCursor
                    with data_manager.manager.get_connection() as conn:
                        # Use RealDictCursor as expected by extract_hashtags function
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            # Get title and description from database, not from video_data
                            cursor.execute(
                                "SELECT title, description FROM videos WHERE id = %s",
                                (existing_video['id'],)
                            )
                            video_info = cursor.fetchone()
                            if video_info:
                                hashtags = extract_and_save_hashtags_for_video(
                                    cursor,
                                    existing_video['id'],
                                    video_info['title'],
                                    video_info['description']
                                )
                                conn.commit()
                                if hashtags:
                                    progress.send_log(f"Extracted {len(hashtags)} hashtags", 'info')
                            else:
                                progress.send_log(f"Video not found in database", 'warning')
                                success = False
                except Exception as e:
                    progress.send_log(f"Hashtag extraction failed: {e}", 'warning')
                    success = False
            
            # OCR extraction removed - no longer supported
            
            if not success:
                return {'success': False, 'error': 'Failed to update some components'}
        else:
            # Normal mode - insert new video
            result = data_manager.append_to_master(video_data)
            if not result:
                progress.send_log("Failed to insert video", 'error')
                return {'success': False, 'error': 'Failed to insert to database'}
        
        # Update cache for duplicate detection
        if hasattr(data_manager, 'existing_urls'):
            data_manager.existing_urls.add(url)
        
        # Extract hashtags if enabled and we have a database connection
        if data_collection_config.get('hashtags', True) and hasattr(data_manager, 'conn'):
            try:
                from database.extract_hashtags import extract_and_save_hashtags_for_video
                # Get the video_id we just inserted
                if result and isinstance(result, dict) and 'id' in result:
                    video_id = result['id']
                    hashtags = extract_and_save_hashtags_for_video(
                        data_manager.conn.cursor(),
                        video_id,
                        video_data.get('title', ''),
                        video_data.get('description', '')
                    )
                    if hashtags:
                        progress.send_log(f"Extracted {len(hashtags)} hashtags", 'info')
            except Exception as e:
                progress.send_log(f"Hashtag extraction failed: {e}", 'warning')
        
        # OCR extraction removed - no longer supported
        
        progress.complete_saving()
        
        # Cleanup if needed
        if args.mp3 and video_result.get('folder'):
            ResourceManager().cleanup_directory(video_result['folder'])
        
        return {'success': True, 'video_data': video_data}
        
    except Exception as e:
        progress.report_error('processing', str(e))
        return {'success': False, 'error': str(e)}


async def worker_process(worker_id: int, url_queue, result_queue, display_queue, 
                  shutdown_event, args, download_kwargs: Dict[str, Any], 
                  ms_token: Optional[str], whisper_config: Dict[str, Any] = None,
                  total_urls: int = 0, config: Optional[Dict[str, Any]] = None):
    """Worker process for parallel data collection."""
    # Initialize progress tracker
    progress = WorkerProgress(worker_id, display_queue, total_urls)
    progress.send_status('initializing')
    
    # Set up signal handler for this worker to set the shared event
    def worker_signal_handler(signum, frame):
        print(f"Worker {worker_id} received shutdown signal")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, worker_signal_handler)
    signal.signal(signal.SIGTERM, worker_signal_handler)
    
    # Initialize components for this worker
    video_extractor = VideoExtractor(
        output_dir=args.output,
        quality=args.quality,
        proxy=download_kwargs.get('proxy')
    )
    video_extractor.shutdown_event = shutdown_event
    
    comment_extractor = None
    if ms_token:
        comment_extractor = CommentExtractor(ms_token=ms_token, max_comments=args.max_comments)
    
    # Initialize data manager for this worker - always use database
    data_manager = DatabaseOrJsonManager(config)

    # Setup Whisper
    whisper_model = None
    whisper_config_with_model = None
    if args.whisper:
        progress.send_log('Loading Whisper model...', 'info')
        if whisper_config:
            whisper_model = load_cached_whisper_model(whisper_config)
            if whisper_model:
                whisper_config_with_model = whisper_config.copy()
                whisper_config_with_model['model'] = whisper_model
                progress.send_log(f"Loaded Whisper model on {whisper_config.get('device', 'cpu').upper()}", 'success')
            else:
                progress.send_log('Failed to load Whisper model', 'error')
    
    progress.send_status('idle')

    try:
        while not shutdown_event.is_set():
            try:
                url = url_queue.get(timeout=0.5)
                if url is None:
                    break
            except queue.Empty:
                continue

            if shutdown_event.is_set():
                try:
                    url_queue.put(url, timeout=0.1)
                except:
                    pass
                break

            progress.start_url(url)
            
            # Use the unified processing function
            result = await process_tiktok_url(
                url=url,
                video_extractor=video_extractor,
                comment_extractor=comment_extractor,
                data_manager=data_manager,
                progress=progress,
                download_kwargs=download_kwargs,
                args=args,
                ms_token=ms_token,
                whisper_config=whisper_config_with_model,
                shutdown_event=shutdown_event,
                config=config
            )
            
            if shutdown_event.is_set():
                break
            
            # Send result to queue
            if not shutdown_event.is_set():
                if result.get('duplicate'):
                    # Skip duplicates silently
                    progress.complete_url()
                elif result['success']:
                    result_queue.put({'success': True, 'data': result['video_data']})
                    progress.complete_url()
                else:
                    result_queue.put({
                        'success': False,
                        'error': result.get('error', 'Unknown error'),
                        'deleted': result.get('deleted', False),
                        'url': url
                    })

    except Exception as e:
        print(f"Worker {worker_id} error: {e}")
    finally:
        # Cleanup
        try:
            video_extractor.cleanup()
            if comment_extractor:
                await comment_extractor.cleanup()
            if whisper_model:
                del whisper_model
        except Exception as e:
            print(f"Worker {worker_id} cleanup error: {e}")
        
        # Ensure we signal completion - try multiple times with better timeout
        completion_sent = False
        for attempt in range(3):
            try:
                result_queue.put(None, timeout=1.0)  # Increased timeout from 0.1 to 1.0
                completion_sent = True
                print(f"Worker {worker_id} sent completion signal")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"Worker {worker_id} failed to send completion signal after 3 attempts: {e}")
                time.sleep(0.2)  # Brief pause before retry
        
        # If we couldn't signal through queue, log it
        if not completion_sent:
            print(f"⚠️ Worker {worker_id} could not signal completion via queue")
            # Write to a file as last resort for debugging
            try:
                with open(f'/tmp/worker_{worker_id}_failed_signal', 'w') as f:
                    f.write(f'Worker {worker_id} completed but could not signal via queue\n')
            except:
                pass
        
        progress.send_status('completed')
        progress.send_log('Worker finished', 'success')

def load_urls_from_file(file_path: str) -> List[str]:
    """Load URLs from file."""
    return URLProcessor.load_urls_from_file(file_path)

def auto_clean_master_json(master_file: str):
    """Auto-clean master JSON file to remove duplicates."""
    try:
        data_manager = DataManager(master_file)
        stats = data_manager.get_stats()
        print(f"Master file stats: {stats['total_entries']} entries, "
              f"{stats['file_size_mb']:.1f}MB")
    except Exception as e:
        print(f"Error cleaning master file: {e}")

def get_cli_provided_args() -> set:
    """Track which arguments were explicitly provided on CLI."""
    import sys
    provided = set()
    
    # Map short flags to long names
    short_flags = {
        'o': 'output',
        'q': 'quality'
    }
    
    i = 0
    argv = sys.argv[1:]
    while i < len(argv):
        arg = argv[i]
        
        if arg.startswith('--'):
            # Long flag: --workers, --batch-size
            flag_name = arg[2:].split('=')[0].replace('-', '_')
            provided.add(flag_name)
            # If it's not using '=', the next arg might be its value
            if '=' not in arg and i + 1 < len(argv) and not argv[i + 1].startswith('-'):
                i += 1  # Skip the value
        elif arg.startswith('-') and not arg[1:].replace('.','').replace('-','').isdigit():
            # Short flag: -o, -q
            for char in arg[1:]:
                if char in short_flags:
                    provided.add(short_flags[char])
                    # Skip next arg if it's a value for this flag
                    if i + 1 < len(argv) and not argv[i + 1].startswith('-'):
                        i += 1
                elif char == 'h':  # Help flag
                    pass
                else:
                    # Single-letter flags without arguments (like boolean flags)
                    # Map common ones
                    if char == 'w':  # Could be whisper
                        provided.add('whisper')
        i += 1
    
    # Also check for store_true actions that were provided
    for arg in argv:
        if arg == '--mp3':
            provided.add('mp3')
        elif arg == '--whisper':
            provided.add('whisper')
        elif arg == '--force-cpu':
            provided.add('force_cpu')
        elif arg == '--force-redownload':
            provided.add('force_redownload')
        elif arg == '--clean-progress':
            provided.add('clean_progress')
    
    return provided

def load_config(config_path: str = "config.toml") -> Dict[str, Any]:
    """Load configuration from TOML file and auto-update with missing settings from template."""
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
            print(f"✓ Loaded configuration from {config_path}")
        except Exception as e:
            print(f"Warning: Could not load {config_path}: {e}")
    
    # Auto-update config with missing settings from template
    template_path = "assets/config.template.toml"
    if os.path.exists(template_path) and os.path.exists(config_path):
        try:
            with open(template_path, 'rb') as f:
                template_config = tomllib.load(f)
            
            # Find missing settings
            missing_sections = []
            for section, section_values in template_config.items():
                if section not in config:
                    config[section] = section_values
                    missing_sections.append(section)
                elif isinstance(section_values, dict):
                    # Check for missing keys within section
                    for key, value in section_values.items():
                        if key not in config[section]:
                            config[section][key] = value
                            missing_sections.append(f"{section}.{key}")
            
            # If there were missing settings, update the config file
            if missing_sections:
                print(f"⚠️  Warning: Found missing config settings, adding defaults for: {', '.join(missing_sections[:5])}")
                if len(missing_sections) > 5:
                    print(f"   ... and {len(missing_sections) - 5} more")
                
                # Write updated config back to file
                try:
                    import toml
                    with open(config_path, 'w') as f:
                        toml.dump(config, f)
                    print(f"   ✓ Updated {config_path} with missing settings")
                except ImportError:
                    print("   ⚠️  Could not update config file (toml package not installed)")
                except Exception as e:
                    print(f"   ⚠️  Could not update config file: {e}")
                    
        except Exception as e:
            print(f"Warning: Could not check template config: {e}")
    
    return config

def merge_config_with_args(args, config: Dict[str, Any], cli_provided: set):
    """Merge TOML config with command-line arguments. 
    
    Rules:
    1. CLI explicitly provided args always win
    2. Config values apply for non-provided args
    3. Argparse defaults only used if neither CLI nor config provides value
    """
    if not config:
        return args
    
    # Map config sections to argument names
    config_mappings = {
        # TikTok settings
        ('tiktok', 'ms_token'): 'ms_token',
        
        # Input settings
        ('input', 'default_urls_file'): 'from_file',
        ('input', 'limit'): 'limit',
        
        # Download settings
        ('download', 'output_dir'): 'output',
        ('download', 'quality'): 'quality',
        ('download', 'audio_only'): 'mp3',
        ('download', 'use_whisper'): 'whisper',
        ('download', 'force_cpu'): 'force_cpu',
        
        # Comments settings
        ('comments', 'max_comments'): 'max_comments',
        
        # Processing settings
        ('processing', 'batch_size'): 'batch_size',
        ('processing', 'delay'): 'delay',
        ('processing', 'workers'): 'workers',
        
        
        # Display settings
        ('display', 'mode'): 'display_mode',
        ('display', 'raw_log'): 'raw_log',
        
        # Resume settings
        ('resume', 'force_redownload'): 'force_redownload',
        ('resume', 'clean_start'): 'clean_progress',
        
        # Network settings
        ('network', 'proxy'): 'proxy',
    }
    
    # Apply config values for non-CLI-provided arguments
    for (section, key), arg_name in config_mappings.items():
        if section in config and key in config[section]:
            config_value = config[section][key]
            
            # Skip if explicitly provided via CLI
            if arg_name in cli_provided:
                continue
                
            # Apply config value
            setattr(args, arg_name, config_value)
            print(f"  Applied config: {arg_name} = {config_value}")
    
    # Handle skip_duplicates (inverse of force_redownload)
    if 'resume' in config and 'skip_duplicates' in config['resume']:
        if 'force_redownload' not in cli_provided:
            args.force_redownload = not config['resume']['skip_duplicates']
            print(f"  Applied config: force_redownload = {args.force_redownload} (from skip_duplicates)")
    
    return args

async def main():
    """Main entry point with proper shutdown integration."""
    from utils.shutdown_manager import shutdown_manager
    
    # Initialize shutdown manager first
    shutdown_manager.register_signal_handlers(force_exit_on_double=True)
    
    # Track CLI arguments BEFORE parsing
    cli_provided = get_cli_provided_args()
    print(f"CLI provided arguments: {cli_provided}")
    
    parser = argparse.ArgumentParser(description="Robust TikTok Data Collector")
    
    # Input options
    parser.add_argument("--url", type=str, help="Single TikTok URL to process")
    parser.add_argument("--from-file", type=str, help="File containing URLs (one per line)")
    parser.add_argument("--limit", type=int, help="Limit number of URLs to process")
    
    # Download options
    parser.add_argument("-o", "--output", default="downloads", help="Output directory")
    parser.add_argument("-q", "--quality", default="best", 
                       choices=["best", "worst", "720p", "480p", "360p"],
                       help="Video quality")
    parser.add_argument("--mp3", action="store_true", help="Download audio only as MP3")
    parser.add_argument("--whisper", action="store_true", help="Use Whisper for transcription")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU for Whisper")
    
    # Comment options
    parser.add_argument("--max-comments", type=int, default=10, help="Max comments per video")
    parser.add_argument("--ms-token", type=str, help="MS_TOKEN for comment extraction")
    
    # Batch options
    parser.add_argument("--batch-size", type=int, default=10, help="Save every N videos")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests (seconds)")
    # Legacy json-output removed - using PostgreSQL database
    
    # Resume options
    parser.add_argument("--force-redownload", action="store_true", help="Ignore duplicates")
    parser.add_argument("--clean-progress", action="store_true", help="Start fresh")
    
    # Recalibration options
    parser.add_argument("--recalibrate", type=str, nargs='?', const='auto',
                       help="Fill missing data for existing videos. Options: auto, transcripts, comments, metadata")
    parser.add_argument("--recalibrate-limit", type=int, default=None,
                       help="Limit number of videos to recalibrate")
    
    # System options
    parser.add_argument("--proxy", type=str, help="Proxy URL")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    # Display options
    parser.add_argument("--display-mode", type=str, default="auto",
                       choices=["rich", "simple", "auto"],
                       help="Display mode for progress tracking")
    parser.add_argument("--raw-log", action="store_true", 
                       help="Save raw output to timestamped log file")
    
    args = parser.parse_args()
    
    # Load configuration from config.toml
    config = load_config()
    
    # Merge config with command-line arguments (CLI takes precedence)
    args = merge_config_with_args(args, config, cli_provided)
    
    # Database is now primary storage - no JSON output needed
    args.json_output = None
    
    # Handle recalibration mode first
    if args.recalibrate:
        from src.database_manager import DatabaseOrJsonManager
        from src.recalibrator import Recalibrator
        
        print("\n🔧 Recalibration Mode")
        
        # Setup database connection
        db_config = config.get('database', {})
        if not db_config.get('enabled', True):
            print("Error: Database is disabled in config.toml. Recalibration requires database.")
            return
        
        data_manager = DatabaseOrJsonManager(config)
        
        # Create recalibrator
        recalibrator = Recalibrator(data_manager, config)
        
        # Determine components to process
        components_requested = None if args.recalibrate == 'auto' else args.recalibrate
        components = recalibrator.get_components_to_process(components_requested)
        
        if not components:
            print("No components available for recalibration.")
            print("Check config.toml settings (use_whisper, ms_token, etc.)")
            return
        
        # Get videos needing recalibration
        videos = recalibrator.get_videos_needing_recalibration(
            components, 
            args.recalibrate_limit
        )
        
        # Show summary
        print(recalibrator.format_summary(videos, components))
        
        if not videos:
            return
        
        # Create processor for recalibration
        processor = RobustTikTokProcessor(args, config)
        processor.recalibrate_mode = True  # Set flag for special processing
        
        # Override some args for recalibration mode
        args.force_redownload = False  # Don't redownload existing videos
        if 'transcripts' in components:
            args.whisper = True
        
        # Process videos (reusing existing infrastructure)
        print(f"\n📊 Processing {len(videos)} videos with {args.workers} worker(s)...")
        
        # Extract URLs for processing
        urls = [v['url'] for v in videos]
        
        # Prepare download kwargs with recalibrate flag
        download_kwargs = {
            'output_dir': args.output,
            'quality': args.quality,
            'audio_only': args.mp3,
            'use_whisper': args.whisper,
            'proxy': args.proxy,
            'recalibrate_mode': True,  # Special flag for recalibration
            'recalibrate_components': components  # Which components to process
        }
        
        # Process the URLs with recalibration flag
        await processor.process_urls(urls, download_kwargs)
        
        print("\n✅ Recalibration complete")
        data_manager.close()
        return
    
    # Auto-discovery logic - check database queue first
    # This mode enables continuous processing of the queue
    database_mode = False
    db = None
    
    # Check if we should use database mode (no CLI arguments provided)
    if 'url' not in cli_provided and 'from_file' not in cli_provided:
        # Database queue mode - ignore config file defaults for from_file
        # Check database queue for pending URLs
        from src.database_manager import DatabaseManager
        
        db_config = config.get('database', {})
        if db_config.get('enabled', True):
            try:
                db = DatabaseManager(
                    host=db_config.get('host', 'localhost'),
                    database=db_config.get('database', 'tiktok_scraper'),
                    user=db_config.get('user'),  # Use config value, no default
                    password=db_config.get('password', ''),
                    port=db_config.get('port', 5432)
                )
                database_mode = True
                
                # Clear args.from_file to prevent conflict with database mode
                args.from_file = None
                args.url = None
                
                # Mark collector as running in database
                with db.get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO collector_status (status, started_at, pid)
                        VALUES ('running', NOW(), %s)
                        ON CONFLICT (id) DO UPDATE
                        SET status = 'running', started_at = NOW(), pid = %s
                        WHERE collector_status.id = 1
                    """, (os.getpid(), os.getpid()))
                    cursor.connection.commit()
                
                # Apply defaults if not in config
                if 'mp3' not in cli_provided:
                    if not ('download' in config and 'audio_only' in config['download']):
                        args.mp3 = True
                        
                if 'whisper' not in cli_provided:
                    if not ('download' in config and 'use_whisper' in config['download']):
                        args.whisper = True
                        
            except Exception as e:
                print(f"Error connecting to database: {e}")
                return
        else:
            print("Database is disabled in config.toml")
            return
    
    # Database continuous processing loop
    if database_mode:
        import time
        no_urls_count = 0
        max_idle_iterations = 3  # Exit after 3 checks with no URLs
        check_interval = 5  # Seconds between checks
        
        print("\n🔄 Starting continuous queue processing mode...")
        print(f"Will check for new URLs every {check_interval} seconds")
        print("Press Ctrl+C to stop\n")
        
        while not shutdown_manager.shutdown_event.is_set():
            try:
                # Get pending URLs from queued_urls table
                with db.get_cursor() as cursor:
                    cursor.execute("""
                        SELECT url FROM queued_urls 
                        WHERE status = 'pending'
                        ORDER BY added_at
                    """)
                    pending_urls = cursor.fetchall()
                    
                    if pending_urls:
                        no_urls_count = 0  # Reset idle counter
                        url_list = [url[0] for url in pending_urls]
                        
                        # Update status to processing
                        cursor.execute("""
                            UPDATE queued_urls 
                            SET status = 'processing', processed_at = NOW()
                            WHERE url = ANY(%s)
                        """, (url_list,))
                        cursor.connection.commit()
                        
                        print(f"\n📋 Found {len(url_list)} pending URL(s) in database queue")
                        args.url = ','.join(url_list)
                        
                        # Initialize processor for this batch
                        processor = RobustTikTokProcessor(args, config)
                        
                        # Load existing progress
                        if not args.force_redownload:
                            processor.load_existing_progress()
                        
                        # Get MS_TOKEN
                        if processor.get_ms_token():
                            if not await processor.validate_ms_token():
                                print("MS_TOKEN validation failed - continuing without comments")
                                processor.ms_token = None
                        
                        # Prepare download kwargs
                        download_kwargs = {
                            'output_dir': args.output,
                            'quality': args.quality,
                            'audio_only': args.mp3,
                            'use_whisper': args.whisper,
                            'proxy': args.proxy
                        }
                        
                        # Fix 1: Handle comma-separated URLs properly
                        if ',' in args.url:
                            urls = args.url.split(',')
                        else:
                            urls = [args.url]
                        
                        # Filter duplicates
                        original_count = len(urls)
                        urls = processor.filter_urls(urls)
                        
                        if urls:
                            print(f"Processing {len(urls)} of {original_count} URLs")
                            
                            # Process URLs using unified worker-based approach
                            await processor.process_urls(urls, download_kwargs)
                            
                            # Mark processed URLs as completed
                            with db.get_cursor() as cursor:
                                for url in urls:
                                    if url not in processor.state.failed_urls:
                                        cursor.execute("""
                                            UPDATE queued_urls 
                                            SET status = 'completed', processed_at = NOW()
                                            WHERE url = %s
                                        """, (url,))
                                    else:
                                        cursor.execute("""
                                            UPDATE queued_urls 
                                            SET status = 'failed', error_message = 'Processing failed', processed_at = NOW()
                                            WHERE url = %s
                                        """, (url,))
                                cursor.connection.commit()
                            
                            print(f"✅ Batch completed: {len(urls)} URL(s) processed")
                            
                            # Update collector status
                            with db.get_cursor() as cursor:
                                cursor.execute("""
                                    UPDATE collector_status
                                    SET last_activity = NOW(), urls_processed = urls_processed + %s
                                    WHERE id = 1
                                """, (len(urls),))
                                cursor.connection.commit()
                        else:
                            print(f"All {original_count} URLs already processed")
                    else:
                        no_urls_count += 1
                        if no_urls_count >= max_idle_iterations:
                            print(f"\n📭 No new URLs found after {max_idle_iterations} checks. Exiting...")
                            break
                        else:
                            print(f"⏳ No pending URLs found (check {no_urls_count}/{max_idle_iterations}). Waiting {check_interval} seconds...")
                            await asyncio.sleep(check_interval)
                            
            except Exception as e:
                print(f"Error in processing loop: {e}")
                await asyncio.sleep(check_interval)
        
        # Mark collector as stopped and notify server
        if db:
            try:
                # Update database status
                with db.get_cursor() as cursor:
                    cursor.execute("""
                        UPDATE collector_status
                        SET status = 'stopped', stopped_at = NOW()
                        WHERE id = 1
                    """)
                    cursor.connection.commit()
                print("\n✅ Collector status updated to 'stopped'")
                
                # Get stats for notification
                with db.get_cursor() as cursor:
                    cursor.execute("""
                        SELECT started_at, stopped_at, urls_processed
                        FROM collector_status
                        WHERE id = 1
                    """)
                    result = cursor.fetchone()
                    if result:
                        started_at, stopped_at, urls_processed = result
                        
                        # Send completion notification to server
                        try:
                            import requests
                            from datetime import datetime
                            
                            notification_data = {
                                'urls_processed': urls_processed or 0,
                                'started_at': started_at.isoformat() if started_at else None,
                                'stopped_at': stopped_at.isoformat() if stopped_at else datetime.now().isoformat(),
                                'reason': 'idle_timeout' if no_urls_count >= max_idle_iterations else 'completed'
                            }
                            
                            response = requests.post(
                                'http://localhost:8000/api/collector-complete/',
                                json=notification_data,
                                timeout=5
                            )
                            
                            if response.status_code == 200:
                                print("📨 Server notified of collector completion")
                            else:
                                print(f"⚠️ Could not notify server: {response.status_code}")
                        except Exception as e:
                            print(f"⚠️ Could not send completion notification: {e}")
                
            except Exception as e:
                print(f"Warning: Could not update collector status: {e}")
        
        return  # Exit after database mode processing
    
    # Regular mode (single batch from file or URL argument)
    # Initialize processor with config
    processor = RobustTikTokProcessor(args, config)
    
    # Load existing progress
    if not args.force_redownload:
        processor.load_existing_progress()
    
    # Get MS_TOKEN
    if processor.get_ms_token():
        if not await processor.validate_ms_token():
            print("MS_TOKEN validation failed - continuing without comments")
            processor.ms_token = None
    
    # Don't load Whisper model in main process - workers will load their own
    if args.whisper:
        from utils.device_manager import DeviceManager
        device, _ = DeviceManager.get_whisper_device_config(args.force_cpu)
        whisper_device = device.upper()
        print(f"\n✓ Using {args.workers} worker(s) with {whisper_device} acceleration.")
    else:
        whisper_device = "CPU"
    
    # Prepare download kwargs
    download_kwargs = {
        'output_dir': args.output,
        'quality': args.quality,
        'audio_only': args.mp3,
        'use_whisper': args.whisper,
        'proxy': args.proxy
    }
    
    # Get URLs
    if args.from_file:
        urls = load_urls_from_file(args.from_file)
        processor.source_file = args.from_file
        if args.limit:
            urls = urls[:args.limit]
    else:
        # Fix 1: Handle comma-separated URLs properly
        if ',' in args.url:
            urls = args.url.split(',')
        else:
            urls = [args.url]
        processor.source_file = None
    
    if not urls:
        print("No URLs to process")
        return

    # Filter duplicates
    original_count = len(urls)
    urls = processor.filter_urls(urls)
    
    if not urls:
        print(f"All {original_count} URLs already processed!")
        return
    
    print(f"Processing {len(urls)} of {original_count} URLs")
    
    # Process URLs using unified worker-based approach
    try:
        # Always use worker processes (even if just 1)
        await processor.process_urls(urls, download_kwargs)
        
        # Update URL statuses in database queue if we're using it
        if 'url' not in cli_provided and 'from_file' not in cli_provided:
            db_config = config.get('database', {})
            if db_config.get('enabled', True):
                try:
                    db = DatabaseManager(
                        host=db_config.get('host', 'localhost'),
                        database=db_config.get('database', 'tiktok_scraper'),
                        user=db_config.get('user'),  # Use config value, no default
                        password=db_config.get('password', ''),
                        port=db_config.get('port', 5432)
                    )
                    
                    # Mark processed URLs as completed
                    with db.get_cursor() as cursor:
                        for url in urls:
                            if url not in processor.state.failed_urls:
                                cursor.execute("""
                                    UPDATE queued_urls 
                                    SET status = 'completed', processed_at = NOW()
                                    WHERE url = %s
                                """, (url,))
                            else:
                                cursor.execute("""
                                    UPDATE queued_urls 
                                    SET status = 'failed', error_message = 'Processing failed'
                                    WHERE url = %s
                                """, (url,))
                        cursor.connection.commit()
                        print(f"✅ Updated database queue status for {len(urls)} URL(s)")
                except Exception as e:
                    print(f"Warning: Could not update database queue status: {e}")
        
        # Clean up
        # Legacy auto-clean removed - using database now
        
    except KeyboardInterrupt:
        # This should not be reached due to signal handlers, but keep as fallback
        print("\nUnexpected KeyboardInterrupt in main()")
        shutdown_manager.shutdown_event.set()
    finally:
        # Ensure cleanup runs if not already initiated
        if not shutdown_manager.shutdown_initiated:
            await processor.cleanup()

if __name__ == "__main__":
    # Set spawn method for CUDA compatibility BEFORE any imports that might use multiprocessing
    import multiprocessing
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # Already set
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle the case where asyncio.run itself is interrupted
        print("\nForced shutdown")
        sys.exit(1)
