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
        self.shutdown_requested = True
        self.save_progress()
        if self.comment_extractor:
            self.comment_extractor.cleanup_sync()
        self.video_extractor.cleanup()
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
                print(f"Download failed: {video_result.get('error')}")
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
                     self.args, download_kwargs, self.ms_token)
            )
            worker.start()
            workers.append(worker)
        
        # Collect results
        data_manager = DataManager(master_file)
        processed_count = 0
        
        try:
            while processed_count < len(urls):
                try:
                    result = self.result_queue.get(timeout=1)
                    if result and result.get('success'):
                        data_manager.append_to_master(result['data'])
                        self.shared_state['processed'] += 1
                    else:
                        self.shared_state['failed'] += 1
                    processed_count += 1
                    
                    # Progress update
                    if processed_count % 10 == 0:
                        print(f"Progress: {processed_count}/{len(urls)} URLs processed")
                        
                except:
                    continue
                    
        except KeyboardInterrupt:
            print("Shutting down workers...")
            self.shutdown_event.set()
        
        # Wait for workers to finish
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
        
        print(f"Multiprocessing complete: {self.shared_state['processed']} successful, "
              f"{self.shared_state['failed']} failed")

def worker_process(worker_id: int, url_queue, result_queue, shutdown_event,
                  args, download_kwargs: Dict[str, Any], ms_token: Optional[str]):
    """Worker process for parallel data collection."""
    print(f"Worker {worker_id} started")
    
    # Initialize components for this worker
    video_extractor = VideoExtractor(
        output_dir=args.output,
        quality=args.quality,
        proxy=download_kwargs.get('proxy')
    )
    
    # Load whisper model if needed
    whisper_model = None
    if args.whisper:
        whisper_model, _ = load_whisper_model(force_cpu=args.force_cpu)
    
    # Process URLs
    while not shutdown_event.is_set():
        try:
            url = url_queue.get(timeout=1)
        except:
            continue
        
        if url is None:
            break
        
        # Process URL
        result = video_extractor.download_single_video(
            url,
            audio_only=download_kwargs.get('audio_only', False),
            use_whisper=args.whisper,
            whisper_model=whisper_model,
            whisper_device='CPU' if args.force_cpu else 'auto'
        )
        
        if result['success']:
            # Extract comments if MS_TOKEN available
            comments = []
            if ms_token:
                try:
                    comment_extractor = CommentExtractor(ms_token=ms_token, max_comments=args.max_comments)
                    comments = [c.to_dict() for c in comment_extractor.extract_comments_sync(url)]
                except:
                    pass
            
            # Prepare data
            video_data = {
                'url': url,
                'video_id': result['metadata'].get('video_id', ''),
                'transcript': result['metadata'].get('whisper_transcription', ''),
                'metadata': result['metadata'],
                'comments': comments
            }
            
            result_queue.put({'success': True, 'data': video_data})
        else:
            result_queue.put({'success': False, 'error': result.get('error')})
    
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

def merge_config_with_args(args, config: Dict[str, Any]):
    """Merge TOML config with command-line arguments (CLI takes precedence)."""
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
        ('resume', 'skip_duplicates'): None,  # Inverse of force_redownload
        ('resume', 'force_redownload'): 'force_redownload',
        ('resume', 'clean_start'): 'clean_progress',
        
        # Network settings
        ('network', 'proxy'): 'proxy',
    }
    
    # Apply config values where CLI args are not set
    for (section, key), arg_name in config_mappings.items():
        if arg_name is None:
            continue
            
        if section in config and key in config[section]:
            config_value = config[section][key]
            current_value = getattr(args, arg_name, None)
            
            # Only apply config value if CLI arg was not explicitly set
            if arg_name == 'from_file':
                # Special handling for from_file - only use if no URL input provided
                if not args.url and not args.from_file:
                    setattr(args, arg_name, config_value)
            elif arg_name in ['mp3', 'whisper', 'force_cpu', 'force_redownload', 'clean_progress']:
                # Boolean flags - only override if False (not set via CLI)
                if not current_value:
                    setattr(args, arg_name, config_value)
            elif current_value is None:
                # Regular arguments - apply if None or still at default
                setattr(args, arg_name, config_value)
    
    # Handle skip_duplicates (inverse of force_redownload)
    if 'resume' in config and 'skip_duplicates' in config['resume']:
        if not args.force_redownload:  # Only apply if not explicitly set
            args.force_redownload = not config['resume']['skip_duplicates']
    
    return args

async def main():
    """Main entry point."""
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
    parser.add_argument("--json-output", type=str, default="master2.json", help="JSON output file")
    
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
    args = merge_config_with_args(args, config)
    
    # Default to urls.txt if no input specified (and not in config)
    if not args.url and not args.from_file:
        if os.path.exists('urls.txt'):
            print("Using default: --from-file urls.txt --mp3 --whisper")
            args.from_file = 'urls.txt'
            args.mp3 = True
            args.whisper = True
        else:
            print("Error: Provide --url or --from-file (or set default_urls_file in config.toml)")
            sys.exit(1)
    
    # Initialize processor
    processor = RobustTikTokProcessor(args)
    
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
        print("Loading Whisper model...")
        whisper_model, whisper_device = load_whisper_model(force_cpu=args.force_cpu)
        if whisper_model:
            print(f"Whisper model loaded on {whisper_device}")
    
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
    
    # Process URLs
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
        print("\nShutdown initiated...")
        processor.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())