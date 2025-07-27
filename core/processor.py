#!/usr/bin/env python3
"""
Main TikTok processor coordinating all operations
Replaces the complex robust_master_downloader.py
"""

import asyncio
import signal
import gc
from typing import List, Optional
from datetime import datetime

from .config import TikTokConfig
from .models import VideoMetadata, ProcessingStatus, ProcessingSummary, ProcessingJob
from .downloader import VideoDownloader
from .comments import CommentExtractor
from .storage import StorageManager
from .utils import URLUtils, FileUtils, extract_title_for_display
from .exceptions import ErrorHandler, TikTokScraperException


class TikTokProcessor:
    """Main processor coordinating video downloads and comment extraction"""
    
    def __init__(self, config: TikTokConfig):
        self.config = config
        self.error_handler = ErrorHandler(verbose=config.verbose)
        self.storage = StorageManager(config.master_file, self.error_handler)
        self.downloader = VideoDownloader(config, self.error_handler)
        self.comment_extractor = CommentExtractor(config.ms_token, self.error_handler)
        
        self.shutdown_requested = False
        self.summary = ProcessingSummary()
        
        # Setup signal handlers for graceful shutdown (only in single process mode)
        if config.workers <= 1:
            self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.error_handler.handle_info("Graceful shutdown requested", "System")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self) -> bool:
        """Initialize processor and validate configuration"""
        try:
            self.error_handler.handle_info("Initializing TikTok processor", "System")
            
            # Validate configuration
            self.config.validate()
            
            # Apply environment overrides
            self.config.apply_environment_overrides()
            
            # Validate MS_TOKEN if provided
            if self.config.ms_token:
                if not await self.comment_extractor.validate_token():
                    self.error_handler.handle_warning(
                        "MS_TOKEN validation failed - continuing without comments",
                        "Initialization"
                    )
                    self.config.ms_token = None
                    self.comment_extractor.ms_token = None
            
            # Load existing URLs for duplicate detection
            existing_urls = self.storage.load_existing_urls()
            self.summary.duplicate_count = len(existing_urls)
            
            self.error_handler.handle_success("Processor initialized successfully", "System")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "Initialization", critical=True)
            return False
    
    def load_urls_to_process(self) -> List[str]:
        """Load URLs to process from file or single URL"""
        urls = []
        
        if self.config.input_file:
            # Load from file
            try:
                with open(self.config.input_file, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f 
                           if line.strip() and URLUtils.is_valid_tiktok_url(line.strip())]
            except Exception as e:
                self.error_handler.handle_error(
                    TikTokScraperException(f"Failed to load URLs from {self.config.input_file}", original_error=e),
                    "URL Loading"
                )
                return []
        elif self.config.url:
            # Single URL
            if URLUtils.is_valid_tiktok_url(self.config.url):
                urls = [self.config.url]
            else:
                self.error_handler.handle_error(
                    TikTokScraperException(f"Invalid TikTok URL: {self.config.url}"),
                    "URL Validation"
                )
                return []
        
        # Apply limit if specified
        if self.config.limit and len(urls) > self.config.limit:
            urls = urls[:self.config.limit]
            self.error_handler.handle_info(
                f"Limited to first {self.config.limit} URLs",
                "URL Loading"
            )
        
        # Filter out duplicates unless force redownload is enabled
        if not self.config.force_redownload:
            original_count = len(urls)
            urls = [url for url in urls if not self.storage.is_duplicate_url(url)]
            
            duplicate_count = original_count - len(urls)
            if duplicate_count > 0:
                self.summary.duplicate_count += duplicate_count
                self.error_handler.handle_info(
                    f"Filtered out {duplicate_count} duplicate URLs",
                    "URL Loading"
                )
        
        self.summary.total_urls = len(urls)
        
        self.error_handler.handle_success(
            f"Loaded {len(urls)} URLs to process",
            "URL Loading"
        )
        
        return urls
    
    async def process_single_video(self, url: str) -> Optional[VideoMetadata]:
        """Process a single video URL"""
        try:
            self.error_handler.handle_info(
                f"Processing: {extract_title_for_display(url)}",
                "Processing"
            )
            
            # Download video and extract metadata
            metadata = await asyncio.wait_for(
                self._download_with_timeout(url),
                timeout=300  # 5 minute timeout
            )
            
            if not metadata:
                return None
            
            # Extract comments if MS_TOKEN available
            if self.config.ms_token:
                await self.comment_extractor.extract_and_update_metadata(
                    metadata, self.config.max_comments
                )
            else:
                metadata.comments_extracted = False
                metadata.top_comments = []
            
            # Mark as completed
            metadata.update_status(ProcessingStatus.COMPLETED)
            
            self.error_handler.handle_success(
                f"Completed: {extract_title_for_display(url)}",
                "Processing"
            )
            
            return metadata
            
        except asyncio.TimeoutError:
            self.error_handler.handle_error(
                TikTokScraperException(f"Processing timeout for {url}"),
                "Processing"
            )
            return None
        except Exception as e:
            self.error_handler.handle_error(e, "Processing")
            return None
    
    async def _download_with_timeout(self, url: str) -> Optional[VideoMetadata]:
        """Download video with timeout handling"""
        try:
            return self.downloader.download_video(url)
        except Exception as e:
            self.error_handler.handle_error(
                TikTokScraperException(f"Download failed for {url}", original_error=e),
                "Download"
            )
            return None
    
    async def process_urls(self, urls: List[str]) -> ProcessingSummary:
        """Process list of URLs with batch saving"""
        self.summary.started_at = datetime.now().isoformat()
        
        try:
            self.error_handler.handle_info(
                f"Starting batch processing of {len(urls)} URLs",
                "Batch Processing"
            )
            
            batch_metadata = []
            
            for i, url in enumerate(urls, 1):
                # Check for shutdown request
                if self.shutdown_requested:
                    self.error_handler.handle_info(
                        "Shutdown requested - saving progress and exiting",
                        "Batch Processing"
                    )
                    break
                
                self.error_handler.handle_info(
                    f"Processing {i}/{len(urls)}: {extract_title_for_display(url)}",
                    "Progress"
                )
                
                # Process single video
                metadata = await self.process_single_video(url)
                
                if metadata:
                    batch_metadata.append(metadata)
                    self.summary.successful_count += 1
                else:
                    self.summary.failed_count += 1
                    self.summary.add_failed_url(url)
                
                # Save batch periodically
                if len(batch_metadata) >= self.config.batch_size:
                    await self._save_batch(batch_metadata)
                    batch_metadata = []
                
                # Add delay between requests
                if i < len(urls) and self.config.delay > 0:
                    self.error_handler.handle_info(
                        f"Waiting {self.config.delay} seconds...",
                        "Delay"
                    )
                    await asyncio.sleep(self.config.delay)
                
                # Periodic cleanup
                if i % 5 == 0:
                    gc.collect()
            
            # Save any remaining videos
            if batch_metadata:
                await self._save_batch(batch_metadata)
            
            # Perform auto cleanup if processing completed successfully
            if not self.shutdown_requested:
                self.storage.auto_cleanup()
            
            self.summary.finalize()
            
            self.error_handler.handle_success(
                f"Batch processing completed - {self.summary.successful_count} successful, {self.summary.failed_count} failed",
                "Batch Processing"
            )
            
            return self.summary
            
        except Exception as e:
            self.error_handler.handle_error(e, "Batch Processing", critical=True)
            self.summary.finalize()
            return self.summary
    
    async def _save_batch(self, videos: List[VideoMetadata]):
        """Save batch of videos to storage"""
        if not videos:
            return
        
        try:
            success = self.storage.append_videos(videos)
            if success:
                self.error_handler.handle_success(
                    f"Saved batch of {len(videos)} videos",
                    "Storage"
                )
            else:
                self.error_handler.handle_error(
                    TikTokScraperException("Failed to save video batch"),
                    "Storage"
                )
        except Exception as e:
            self.error_handler.handle_error(e, "Storage")
    
    def print_summary(self):
        """Print processing summary"""
        print("\n" + "="*60)
        print("🎉 PROCESSING COMPLETE")
        print("="*60)
        print(f"✅ Successful: {self.summary.successful_count}")
        print(f"❌ Failed: {self.summary.failed_count}")
        print(f"⏭️  Skipped (duplicates): {self.summary.duplicate_count}")
        print(f"📊 Total URLs: {self.summary.total_urls}")
        
        if self.summary.completed_at:
            print(f"📈 Processing rate: {self.summary.processing_rate:.1f} videos/min")
            print(f"🎯 Success rate: {self.summary.success_rate:.1f}%")
        
        if self.summary.failed_urls:
            print(f"\n❌ Failed URLs ({len(self.summary.failed_urls)}):")
            for url in self.summary.failed_urls[:5]:  # Show first 5
                print(f"   - {extract_title_for_display(url)}")
            if len(self.summary.failed_urls) > 5:
                print(f"   ... and {len(self.summary.failed_urls) - 5} more")
        
        print("="*60)
        
        # Save summary to file
        self.storage.save_processing_summary(self.summary)
    
    async def cleanup(self):
        """Cleanup processor resources"""
        try:
            self.error_handler.handle_info("Cleaning up processor resources", "Cleanup")
            
            # Cleanup components
            await self.comment_extractor.cleanup()
            self.downloader.cleanup_resources()
            
            # Final garbage collection
            gc.collect()
            
            self.error_handler.handle_success("Cleanup completed", "Cleanup")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Cleanup")
    
    def get_error_summary(self):
        """Get error summary from error handler"""
        return self.error_handler.get_error_summary()


async def create_and_run_processor(config: TikTokConfig) -> ProcessingSummary:
    """Create processor and run complete processing workflow"""
    processor = TikTokProcessor(config)
    
    try:
        # Initialize
        if not await processor.initialize():
            processor.error_handler.handle_error(
                TikTokScraperException("Processor initialization failed"),
                "System",
                critical=True
            )
            return processor.summary
        
        # Load URLs
        urls = processor.load_urls_to_process()
        if not urls:
            processor.error_handler.handle_warning(
                "No URLs to process",
                "System"
            )
            return processor.summary
        
        # Process URLs
        summary = await processor.process_urls(urls)
        
        # Print summary
        processor.print_summary()
        
        return summary
        
    except KeyboardInterrupt:
        processor.error_handler.handle_info("Graceful shutdown initiated", "System")
        processor.shutdown_requested = True
        return processor.summary
    except Exception as e:
        processor.error_handler.handle_error(e, "System", critical=True)
        return processor.summary
    finally:
        await processor.cleanup()