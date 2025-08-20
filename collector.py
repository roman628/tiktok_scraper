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
from src.resource_manager import ResourceManager
from src.data_manager import DataManager
from src.video_extractor import VideoExtractor, load_whisper_model, get_memory_usage
from src.comment_extractor import CommentExtractor
from src.transcript_extractor import TranscriptExtractor

# For compatibility with existing code
from src.video_extractor import VideoExtractor
download_single_video = VideoExtractor().download_single_video

class RobustTikTokProcessor:
    """Main processor for TikTok data collection."""
    
    def __init__(self, args):
        self.args = args
        self.master_file = args.json_output
        self.source_file = None
        self.shutdown_requested = False
        
        # Initialize components
        self.data_manager = DataManager(self.master_file)
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
        
        # Register signal handlers
        self.resource_manager.register_signal_handlers(self.cleanup)
    
    def cleanup(self):
        """Cleanup resources on shutdown."""
        import concurrent.futures
        self.shutdown_requested = True
        self.save_progress()
        
        # Cleanup with timeout
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            
            # Schedule cleanup tasks
            if self.comment_extractor:
                futures.append(executor.submit(self.comment_extractor.cleanup_sync))
            futures.append(executor.submit(self.video_extractor.cleanup))
            
            # Wait for cleanup with timeout
            done, not_done = concurrent.futures.wait(futures, timeout=5)
            
            if not_done:
                print("Warning: Some cleanup tasks timed out")
                # Force kill browser processes if cleanup hangs
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
        existing_count = len(self.data_manager.existing_urls)
        if existing_count > 0:
            print(f"Loaded {existing_count} existing URLs from {self.master_file}")
    
    def save_progress(self):
        """Save current progress state."""
        # Progress saving disabled to avoid creating clutter files
        pass
    
    def filter_urls(self, urls: List[str]) -> List[str]:
        """Filter out already processed URLs."""
        filtered = []
        for url in urls:
            if not self.data_manager.is_duplicate(url):
                filtered.append(url)
        return filtered
    
    async def process_urls(self, urls: List[str], download_kwargs: Dict[str, Any]):
        """Process list of URLs."""
        self.state.total_urls = len(urls)
        
        for i, url in enumerate(urls):
            if self.shutdown_requested:
                print("Shutdown requested, stopping processing")
                break
            
            print(f"\nProcessing {i+1}/{len(urls)}: {url}")
            
            # Process single URL
            result = await self.process_single_url(url, download_kwargs)
            
            if result:
                self.state.processed_urls += 1
            else:
                self.state.failed_urls.append(url)
            
            # Save progress periodically
            if (i + 1) % self.args.batch_size == 0:
                self.save_progress()
            
            # Delay between requests
            if i < len(urls) - 1:
                time.sleep(self.args.delay)
            
            # Memory cleanup
            if (i + 1) % 3 == 0:
                self.resource_manager.check_memory_and_cleanup()
        
        # Final save
        self.save_progress()
        print(f"\nCompleted: {self.state.processed_urls}/{self.state.total_urls} URLs processed")
    
    async def process_single_url(self, url: str, download_kwargs: Dict[str, Any]) -> bool:
        """Process a single TikTok URL."""
        # Check if URL was already processed
        if url in self.data_manager.existing_urls:
            print(f"⏭️  Skipping duplicate: {url}")
            return True  # Return True since it's already processed
        
        try:
            # Download video and extract metadata
            print("Downloading video...")
            video_result = self.video_extractor.download_single_video(
                url,
                audio_only=download_kwargs.get('audio_only', False),
                use_whisper=download_kwargs.get('use_whisper', False),
                whisper_model=download_kwargs.get('whisper_model'),
                whisper_device=download_kwargs.get('whisper_device', 'CPU')
            )
            
            if not video_result['success']:
                error_msg = video_result.get('error', '')
                print(f"Download failed: {error_msg}")
                
                # Check if this is a deleted/private video
                if video_result.get('deleted'):
                    # Remove from source file if we have one
                    if self.source_file:
                        URLProcessor.remove_url_from_file(url, self.source_file)
                
                return False
            
            metadata = video_result['metadata']
            
            # Extract transcript from metadata if present
            transcript = metadata.get('whisper_transcription', '')
            
            # Extract comments if MS_TOKEN is available
            comments = []
            if self.comment_extractor and self.ms_token:
                print("Extracting comments...")
                try:
                    comment_objects = await self.comment_extractor.extract_comments(url)
                    comments = [comment.to_dict() for comment in comment_objects]
                    print(f"Extracted {len(comments)} comments")
                except Exception as e:
                    print(f"Comment extraction failed: {e}")
            
            # Create flattened data structure (all fields at top level)
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
                'hashtags': metadata.get('hashtags', []),
                'upload_date': metadata.get('upload_date', ''),
                'timestamp': metadata.get('timestamp', 0),
                'width': metadata.get('width', 0),
                'height': metadata.get('height', 0),
                'fps': metadata.get('fps', 0),
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
            self.data_manager.append_to_master(video_data)
            
            # Add URL to existing set to prevent reprocessing
            self.data_manager.existing_urls.add(url)
            
            # Cleanup download folder if needed
            if self.args.mp3 and video_result.get('folder'):
                self.resource_manager.cleanup_directory(video_result['folder'])
            
            return True
            
        except Exception as e:
            print(f"Error processing URL: {e}")
            return False
    
    async def cleanup_api_session(self):
        """Clean up API sessions."""
        if self.comment_extractor:
            await self.comment_extractor.cleanup()

class MultiprocessCoordinator:
    """Coordinator for multiprocess data collection."""
    
    def __init__(self, args, ms_token: Optional[str] = None):
        self.args = args
        self.ms_token = ms_token
        self.num_workers = args.workers
        self.manager = mp.Manager()
        self.shared_state = self.manager.dict()
        self.url_queue = self.manager.Queue()
        self.result_queue = self.manager.Queue()
        self.shutdown_event = self.manager.Event()
        self.whisper_config = None
        
        # Pre-load Whisper model to cache if needed
        if args.whisper:
            print("Pre-loading Whisper model to cache for workers...")
            model, device = load_whisper_model(force_cpu=args.force_cpu)
            if model:
                # Get the cache directory from the model if available
                cache_dir = None
                if hasattr(model, 'model_path'):
                    cache_dir = os.path.dirname(model.model_path)
                elif hasattr(model, 'download_root'):
                    cache_dir = model.download_root
                else:
                    # Default cache directory for faster-whisper
                    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
                
                # Prepare configuration for workers
                self.whisper_config = {
                    'model_size': 'small.en',
                    'device': device.lower() if device != 'MPS' else 'cpu',  # Force CPU for MPS
                    'compute_type': 'int8' if device.lower() == 'cpu' else 'float16',
                    'cache_dir': cache_dir
                }
                print(f"✓ Whisper model cached, workers will load from: {cache_dir}")
                
                # Clean up the pre-loaded model to free memory
                del model
                import gc
                gc.collect()
            else:
                print("Failed to pre-load Whisper model")
    
    async def process_urls_multiprocess(self, urls: List[str], download_kwargs: Dict[str, Any], 
                                       master_file: str, source_file: Optional[str]):
        """Process URLs using multiple worker processes."""
        # Initialize shared state
        self.shared_state['total'] = len(urls)
        self.shared_state['processed'] = 0
        self.shared_state['failed'] = 0
        
        # Add URLs to queue
        for url in urls:
            self.url_queue.put(url)
        
        # Start worker processes
        workers = []
        for i in range(self.num_workers):
            worker = mp.Process(
                target=worker_process,
                args=(i, self.url_queue, self.result_queue, self.shutdown_event,
                     self.args, download_kwargs, self.ms_token, self.whisper_config)
            )
            worker.start()
            workers.append(worker)
        
        # Collect results
        data_manager = DataManager(master_file)
        processed_count = 0
        
        try:
            while processed_count < len(urls) and not self.shutdown_event.is_set():
                try:
                    result = self.result_queue.get(timeout=0.5)  # Shorter timeout for responsive shutdown
                    
                    # Check for sentinel value indicating worker shutdown
                    if result is None:
                        print("Received worker shutdown signal")
                        continue
                    
                    if result and result.get('success'):
                        data_manager.append_to_master(result['data'])
                        self.shared_state['processed'] += 1
                    else:
                        # Check if it's a deleted video
                        if result and result.get('deleted') and source_file:
                            url = result.get('url')
                            if url:
                                URLProcessor.remove_url_from_file(url, source_file)
                        self.shared_state['failed'] += 1
                    processed_count += 1
                    
                    # Progress update
                    if processed_count % 10 == 0:
                        print(f"Progress: {processed_count}/{len(urls)} URLs processed")
                        
                except queue.Empty:
                    # Check shutdown status during timeout
                    if self.shutdown_event.is_set():
                        print("Shutdown requested during queue processing")
                        break
                    continue
                except Exception as e:
                    print(f"Error processing result: {e}")
                    if self.shutdown_event.is_set():
                        break
                    continue
                    
        except KeyboardInterrupt:
            print("\nShutting down workers gracefully...")
            self.shutdown_event.set()
            
            # Send poison pills to wake up any blocking queue operations
            for _ in range(self.num_workers):
                try:
                    self.url_queue.put(None, timeout=0.1)
                except:
                    pass
        
        # Wait for workers to finish
        for worker in workers:
            worker.join(timeout=10)  # Give workers 10 seconds to finish gracefully
            if worker.is_alive():
                print(f"Worker {worker.pid} not responding, terminating...")
                worker.terminate()
                worker.join(timeout=2)  # Wait briefly for termination
                if worker.is_alive():
                    print(f"Worker {worker.pid} still alive, force killing...")
                    worker.kill()
        
        print(f"Multiprocessing complete: {self.shared_state['processed']} successful, "
              f"{self.shared_state['failed']} failed")

def load_cached_whisper_model(model_config: Dict[str, Any]):
    """Load Whisper model from cached configuration.
    
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
        cache_dir = model_config.get('cache_dir')
        
        print(f"Worker loading cached Whisper model: {model_size} on {device.upper()}")
        
        # Load model with cache directory to avoid re-downloading
        model_kwargs = {
            "model_size_or_path": model_size,
            "device": device,
            "compute_type": compute_type
        }
        if cache_dir:
            model_kwargs["download_root"] = cache_dir
            
        model = WhisperModel(**model_kwargs)
        return model
        
    except Exception as e:
        print(f"Failed to load cached Whisper model: {e}")
        return None

def worker_process(worker_id: int, url_queue, result_queue, shutdown_event,
                  args, download_kwargs: Dict[str, Any], ms_token: Optional[str],
                  whisper_config: Dict[str, Any] = None):
    """Worker process for parallel data collection."""
    print(f"Worker {worker_id} started")
    
    # Import shutdown handler for worker
    from src.shutdown_manager import WorkerShutdownHandler
    worker_handler = WorkerShutdownHandler(worker_id, shutdown_event)
    
    # Set up signal handler for this worker
    def worker_signal_handler(signum, frame):
        print(f"Worker {worker_id} received shutdown signal")
        shutdown_event.set()
        # Don't exit immediately - let the worker loop handle cleanup
    
    signal.signal(signal.SIGINT, worker_signal_handler)
    signal.signal(signal.SIGTERM, worker_signal_handler)
    
    # Initialize components for this worker
    video_extractor = VideoExtractor(
        output_dir=args.output,
        quality=args.quality,
        proxy=download_kwargs.get('proxy')
    )
    
    # Pass shutdown event to video extractor
    video_extractor.shutdown_event = shutdown_event
    
    # Load whisper model from cache config if provided
    whisper_model = None
    if args.whisper:
        if whisper_config:
            # Load from cached configuration (avoids re-download)
            whisper_model = load_cached_whisper_model(whisper_config)
            if not whisper_model:
                print(f"Worker {worker_id}: Failed to load Whisper model from cache")
        else:
            # Fallback to regular loading (for backwards compatibility)
            whisper_model, _ = load_whisper_model(force_cpu=args.force_cpu)
    
    # Process URLs with shutdown checking
    try:
        while not shutdown_event.is_set():
            try:
                url = url_queue.get(timeout=0.5)  # Shorter timeout for responsiveness
                if url is None:  # Sentinel value for shutdown
                    break
            except queue.Empty:
                continue
            except Exception:
                if shutdown_event.is_set():
                    break
                continue
            
            # Check shutdown before starting work
            if shutdown_event.is_set():
                # Put URL back for another worker if possible
                try:
                    url_queue.put(url, timeout=0.1)
                except:
                    pass
                break
            
            # Process URL with shutdown event passed
            result = video_extractor.download_single_video(
                url,
                audio_only=download_kwargs.get('audio_only', False),
                use_whisper=args.whisper,
                whisper_model=whisper_model,
                whisper_device='CPU' if args.force_cpu else 'auto',
                shutdown_event=shutdown_event  # Pass shutdown event
            )
        
            # Check shutdown after download
            if shutdown_event.is_set():
                break
                
            if result['success']:
                # Extract comments if MS_TOKEN available
                comments = []
                if ms_token and not shutdown_event.is_set():
                    comment_extractor = None
                    try:
                        comment_extractor = CommentExtractor(ms_token=ms_token, max_comments=args.max_comments)
                        comments = [c.to_dict() for c in comment_extractor.extract_comments_sync(url)]
                    except Exception as e:
                        print(f"Error extracting comments: {e}")
                    finally:
                        # Ensure cleanup happens
                        if comment_extractor:
                            comment_extractor.cleanup_sync()
                
                # Prepare data
                video_data = {
                    'url': url,
                    'video_id': result['metadata'].get('video_id', ''),
                    'transcript': result['metadata'].get('whisper_transcription', ''),
                    'metadata': result['metadata'],
                    'comments': comments
                }
                
                if not shutdown_event.is_set():
                    result_queue.put({'success': True, 'data': video_data})
            else:
                # Pass along deleted flag if present
                if not shutdown_event.is_set():
                    result_queue.put({
                        'success': False, 
                        'error': result.get('error'),
                        'deleted': result.get('deleted', False),
                        'url': url
                    })
    
    except Exception as e:
        print(f"Worker {worker_id} error: {e}")
    finally:
        # Cleanup with timeout protection
        try:
            video_extractor.cleanup()
            if whisper_model:
                del whisper_model
        except Exception as e:
            print(f"Worker {worker_id} cleanup error: {e}")
        
        # Send sentinel to indicate this worker is done
        try:
            result_queue.put(None, timeout=0.1)
        except:
            pass
        
        print(f"Worker {worker_id} finished")

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
    """Load configuration from TOML file."""
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
            print(f"✓ Loaded configuration from {config_path}")
        except Exception as e:
            print(f"Warning: Could not load {config_path}: {e}")
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
        
        # Output settings
        ('output', 'json_output'): 'json_output',
        
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
    from src.shutdown_manager import shutdown_manager
    
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
    parser.add_argument("--json-output", type=str, default=None, help="JSON output file")
    
    # Resume options
    parser.add_argument("--force-redownload", action="store_true", help="Ignore duplicates")
    parser.add_argument("--clean-progress", action="store_true", help="Start fresh")
    
    # System options
    parser.add_argument("--proxy", type=str, help="Proxy URL")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    args = parser.parse_args()
    
    # Load configuration from config.toml
    config = load_config()
    
    # Merge config with command-line arguments (CLI takes precedence)
    args = merge_config_with_args(args, config, cli_provided)
    
    # Ensure json_output has a value (fallback to default if not set)
    if args.json_output is None:
        args.json_output = "master2.json"
        print("Warning: No json_output specified in config or CLI, using default: master2.json")
    
    # Auto-discovery logic without overriding config
    if 'url' not in cli_provided and 'from_file' not in cli_provided:
        if not args.url and not args.from_file:
            # Check for urls.txt in order of preference
            possible_files = ['data/urls.txt', 'urls.txt']
            for file_path in possible_files:
                if os.path.exists(file_path):
                    args.from_file = file_path
                    print(f"Auto-detected input file: {file_path}")
                    
                    # Only set defaults if not in config AND not in CLI
                    if 'mp3' not in cli_provided:
                        # Check if audio_only is in config
                        if not ('download' in config and 'audio_only' in config['download']):
                            args.mp3 = True  # Default for auto-discovery
                            print("  Applied auto-discovery default: mp3 = True")
                    
                    if 'whisper' not in cli_provided:
                        # Check if use_whisper is in config
                        if not ('download' in config and 'use_whisper' in config['download']):
                            args.whisper = True  # Default for auto-discovery
                            print("  Applied auto-discovery default: whisper = True")
                    break
            else:
                print("Error: Provide --url or --from-file (or set default_urls_file in config.toml)")
                sys.exit(1)
    
    # Initialize processor with shutdown manager
    processor = RobustTikTokProcessor(args)
    shutdown_manager.register_cleanup_handler(processor.cleanup)
    
    # Load existing progress
    if not args.force_redownload:
        processor.load_existing_progress()
    
    # Get MS_TOKEN
    if processor.get_ms_token():
        if not await processor.validate_ms_token():
            print("MS_TOKEN validation failed - continuing without comments")
            processor.ms_token = None
    
    # Load Whisper model if requested
    whisper_model = None
    whisper_device = "CPU"
    if args.whisper:
        from src.device_manager import DeviceManager
        whisper_model, whisper_device = load_whisper_model(force_cpu=args.force_cpu)
        if whisper_model:
            # Print device warning if using multiple workers with CPU
            DeviceManager.print_device_warning(args.workers, whisper_device.lower())
    
    # Prepare download kwargs
    download_kwargs = {
        'output_dir': args.output,
        'quality': args.quality,
        'audio_only': args.mp3,
        'use_whisper': args.whisper,
        'whisper_model': whisper_model,
        'whisper_device': whisper_device,
        'proxy': args.proxy
    }
    
    # Get URLs
    if args.from_file:
        urls = load_urls_from_file(args.from_file)
        processor.source_file = args.from_file
        if args.limit:
            urls = urls[:args.limit]
    else:
        urls = [args.url]
        processor.source_file = None
    
    if not urls:
        print("No URLs to process")
        sys.exit(1)
    
    # Filter duplicates
    original_count = len(urls)
    urls = processor.filter_urls(urls)
    
    if not urls:
        print(f"All {original_count} URLs already processed!")
        sys.exit(0)
    
    print(f"Processing {len(urls)} of {original_count} URLs")
    
    # Process URLs with shutdown checking
    try:
        if args.workers <= 1:
            # Single process mode
            await processor.process_urls(urls, download_kwargs)
        else:
            # Multiprocess mode
            if not args.from_file:
                print("Multiprocessing requires --from-file")
                sys.exit(1)
            
            coordinator = MultiprocessCoordinator(args, processor.ms_token)
            coordinator.shutdown_event = shutdown_manager.shutdown_event
            
            # Remove model from kwargs for multiprocessing
            mp_kwargs = download_kwargs.copy()
            mp_kwargs.pop('whisper_model', None)
            mp_kwargs.pop('whisper_device', None)
            
            await coordinator.process_urls_multiprocess(
                urls, mp_kwargs, processor.master_file, processor.source_file
            )
        
        # Clean up
        auto_clean_master_json(processor.master_file)
        
    except KeyboardInterrupt:
        # This should not be reached due to signal handlers, but keep as fallback
        print("\nUnexpected KeyboardInterrupt in main()")
        shutdown_manager.shutdown_event.set()
    finally:
        # Ensure cleanup runs if not already initiated
        if not shutdown_manager.shutdown_initiated:
            processor.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle the case where asyncio.run itself is interrupted
        print("\nForced shutdown")
        sys.exit(1)