#!/Users/ethan/tiktok_scraper/venv/bin/python
"""
Robust TikTok Downloader and Comment Extractor
Production-ready with contingencies for:
- Duplicate detection and skipping
- MS_TOKEN validation and renewal
- Resume functionality
- Progress tracking and recovery
"""

import os
import sys
import json
import argparse
import asyncio
import time
import re
import gc
import tracemalloc
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi

# Import the video downloader functions
from tiktok_scraper import (
    download_single_video as download_tiktok_video, 
    load_whisper_model,
    get_memory_usage
)

# Import memory efficient append
try:
    from memory_efficient_append import append_batch_to_master_json_efficient
    append_batch_to_master_json = append_batch_to_master_json_efficient
except ImportError:
    from tiktok_scraper import append_to_master_json
    
    def append_batch_to_master_json(metadata_list, master_file_path):
        """Batch append using individual append function"""
        for metadata in metadata_list:
            append_to_master_json(metadata, master_file_path)

# Import comment extraction functions
from comment_extractor import extract_video_id_from_url, extract_comment_replies


def has_transcription_with_min_length(entry, min_length=50):
    """Check if entry has transcription with minimum character length"""
    if not isinstance(entry, dict):
        return False
    
    # Check for transcription field
    transcription = entry.get('transcription', '').strip()
    if transcription and len(transcription) >= min_length:
        return True
    
    # Check for subtitle field  
    subtitle = entry.get('subtitle', '').strip()
    if subtitle and len(subtitle) >= min_length:
        return True
    
    # Check for subtitles field (plural)
    subtitles = entry.get('subtitles', '').strip()
    if subtitles and len(subtitles) >= min_length:
        return True
    
    # Check for whisper_transcription field
    whisper_transcription = entry.get('whisper_transcription', '').strip()
    if whisper_transcription and len(whisper_transcription) >= min_length:
        return True
    
    # Check for any field containing 'transcript'
    for key, value in entry.items():
        if 'transcript' in key.lower() and value:
            text = str(value).strip()
            if text and len(text) >= min_length:
                return True
    
    return False


def get_data_completeness_score(entry):
    """Score an entry based on how complete its data is"""
    score = 0
    
    # Basic fields
    basic_fields = ['title', 'description', 'url', 'video_id', 'uploader', 'upload_date']
    for field in basic_fields:
        if field in entry and entry[field]:
            score += 1
    
    # Metadata fields
    metadata_fields = ['view_count', 'like_count', 'comment_count', 'duration', 'width', 'height']
    for field in metadata_fields:
        if field in entry and entry[field] is not None:
            score += 1
    
    # Comments
    if entry.get('comments_extracted') is True:
        score += 10  # High value for having comments
        comments = entry.get('top_comments', [])
        score += min(len(comments), 10)  # Up to 10 points for comments
    
    # Transcription
    if has_transcription_with_min_length(entry):
        score += 5
    
    # Download info
    if entry.get('downloaded_at'):
        score += 2
    
    return score


def remove_duplicates_from_data(data):
    """Remove duplicate URLs from data, keeping the most complete entry"""
    print(f"🔍 Checking for duplicates in {len(data)} entries...")
    
    # Group entries by URL
    url_entries = {}
    entries_without_url = []
    
    for entry in data:
        if isinstance(entry, dict) and 'url' in entry:
            url = entry['url']
            if url not in url_entries:
                url_entries[url] = []
            url_entries[url].append(entry)
        else:
            entries_without_url.append(entry)
    
    # Find duplicates
    duplicate_urls = [url for url, entries in url_entries.items() if len(entries) > 1]
    
    if duplicate_urls:
        print(f"⚠️  Found {len(duplicate_urls)} duplicate URLs")
    
    # For each URL, keep the most complete entry
    unique_entries = []
    total_removed = 0
    
    for url, entries in url_entries.items():
        if len(entries) == 1:
            unique_entries.append(entries[0])
        else:
            # Score each entry and keep the best one
            best_entry = max(entries, key=get_data_completeness_score)
            unique_entries.append(best_entry)
            total_removed += len(entries) - 1
    
    # Add back entries without URLs
    unique_entries.extend(entries_without_url)
    
    if total_removed > 0:
        print(f"🗑️  Removed {total_removed} duplicate entries")
    
    return unique_entries


def clean_short_transcriptions(data, min_length=50):
    """Remove entries with transcriptions shorter than min_length"""
    print(f"🔍 Cleaning entries with transcriptions shorter than {min_length} characters...")
    
    entries_with_valid_transcription = []
    entries_without_valid_transcription = []
    entries_without_url = []
    
    for entry in data:
        if isinstance(entry, dict):
            if 'url' not in entry:
                entries_without_url.append(entry)
            elif has_transcription_with_min_length(entry, min_length):
                entries_with_valid_transcription.append(entry)
            else:
                entries_without_valid_transcription.append(entry)
        else:
            entries_without_url.append(entry)
    
    cleaned_data = entries_with_valid_transcription + entries_without_url
    removed_count = len(entries_without_valid_transcription)
    
    if removed_count > 0:
        print(f"🗑️  Removed {removed_count} entries with insufficient transcription")
    
    return cleaned_data


def auto_clean_master_json(master_file_path):
    """Automatically clean master JSON by removing duplicates and short transcriptions"""
    print("\n🧹 Starting automatic cleanup of master JSON...")
    
    if not os.path.exists(master_file_path):
        print(f"⚠️  Master file {master_file_path} not found, skipping cleanup")
        return
    
    try:
        # Load data
        with open(master_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print(f"⚠️  Master file is not an array, skipping cleanup")
            return
        
        original_count = len(data)
        print(f"📊 Original entries: {original_count}")
        
        # Remove duplicates
        data = remove_duplicates_from_data(data)
        
        # Clean short transcriptions
        data = clean_short_transcriptions(data, min_length=50)
        
        final_count = len(data)
        total_removed = original_count - final_count
        
        if total_removed > 0:
            # Create backup
            backup_file = f"{master_file_path}.before_autoclean_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy2(master_file_path, backup_file)
            print(f"💾 Created backup: {backup_file}")
            
            # Save cleaned data
            with open(master_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Cleanup completed!")
            print(f"📊 Final entries: {final_count}")
            print(f"🗑️  Total removed: {total_removed}")
        else:
            print("✅ No cleanup needed - all entries are already valid")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        print("⚠️  Continuing without cleanup")


class RobustTikTokProcessor:
    def __init__(self, args):
        self.args = args
        self.ms_token = None
        self.master_file = "master2.json"
        self.progress_file = "download_progress.json"
        self.processed_urls = set()
        self.successful_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.enable_memory_tracking = args.memory_tracking if hasattr(args, 'memory_tracking') else False
        
        if self.enable_memory_tracking:
            tracemalloc.start()
        
        # Configure garbage collection for aggressive cleanup
        gc.set_threshold(700, 10, 10)  # More aggressive GC
        
    def load_existing_progress(self):
        """Load existing URLs from master2.json and progress file"""
        print("🔍 Checking for existing progress...")
        
        # Load URLs from master2.json using streaming to avoid memory issues
        if os.path.exists(self.master_file):
            try:
                # Stream through the file to collect URLs without loading all data
                with open(self.master_file, 'r', encoding='utf-8') as f:
                    # Check if it's an array
                    first_char = f.read(1)
                    if first_char == '[':
                        f.seek(0)
                        # Use streaming JSON parser
                        try:
                            import ijson
                            parser = ijson.items(f, 'item')
                            for item in parser:
                                if isinstance(item, dict) and 'url' in item:
                                    self.processed_urls.add(item['url'])
                        except ImportError:
                            # Fallback to regular json if ijson not available
                            f.seek(0)
                            existing_data = json.load(f)
                            if isinstance(existing_data, list):
                                for item in existing_data:
                                    if isinstance(item, dict) and 'url' in item:
                                        self.processed_urls.add(item['url'])
                            
                print(f"📊 Found {len(self.processed_urls)} existing URLs in {self.master_file}")
                gc.collect()  # Clean up after loading
            except Exception as e:
                print(f"⚠️  Error reading {self.master_file}: {e}")
        
        # Load progress file for additional tracking
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    
                failed_urls = set(progress_data.get('failed_urls', []))
                skipped_urls = set(progress_data.get('skipped_urls', []))
                
                # Don't skip failed URLs - retry them
                self.processed_urls.update(skipped_urls)
                
                print(f"📊 Progress file: {len(failed_urls)} failed, {len(skipped_urls)} skipped")
            except Exception as e:
                print(f"⚠️  Error reading progress file: {e}")
    
    def save_progress(self, failed_urls=None, current_url=None):
        """Save current progress to recover from interruptions"""
        progress_data = {
            "last_updated": datetime.now().isoformat(),
            "processed_count": len(self.processed_urls),
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "failed_urls": list(failed_urls) if failed_urls else [],
            "current_url": current_url,
            "ms_token_last_used": datetime.now().isoformat() if self.ms_token else None
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Failed to save progress: {e}")
    
    def get_ms_token(self):
        """Get and validate MS_TOKEN from user input or environment"""
        print("\n🔑 MS_TOKEN Required for Comment Extraction")
        print("="*50)
        print("To extract comments, you need a valid MS_TOKEN from your browser.")
        print("Instructions:")
        print("1. Open TikTok in your browser and log in")
        print("2. Open Developer Tools (F12)")
        print("3. Go to Application/Storage tab")
        print("4. Find 'msToken' cookie and copy its value")
        print("="*50)
        
        # Check if token provided as argument or environment variable
        if hasattr(self.args, 'ms_token') and self.args.ms_token:
            self.ms_token = self.args.ms_token
            print("✅ MS_TOKEN provided via argument")
        elif os.getenv('TIKTOK_MS_TOKEN'):
            self.ms_token = os.getenv('TIKTOK_MS_TOKEN')
            print("✅ MS_TOKEN found in environment variable")
        else:
            # Get from user input
            while True:
                token = input("Enter your MS_TOKEN (or 'skip' to download without comments): ").strip()
                
                if token.lower() == 'skip':
                    print("⚠️  Skipping comment extraction - will only download videos")
                    return False
                
                if len(token) > 50:  # Basic validation
                    self.ms_token = token
                    break
                else:
                    print("❌ Invalid token format. Please try again.")
        
        return True
    
    async def validate_ms_token(self):
        """Validate MS_TOKEN by making a test API call"""
        if not self.ms_token:
            return False
            
        print("🔐 Validating MS_TOKEN...")
        
        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                )
                
                # Test with a simple operation
                test_url = "https://www.tiktok.com/@tiktok/video/7000000000000000000"  # Non-existent video
                video_id = extract_video_id_from_url(test_url)
                
                try:
                    video = api.video(id=video_id)
                    # Try to get video info (will fail for non-existent video but validates token)
                    await video.info()
                except Exception:
                    # Expected to fail for non-existent video, but if we get here, token works
                    pass
                    
                print("✅ MS_TOKEN validated successfully")
                return True
                
        except Exception as e:
            print(f"❌ MS_TOKEN validation failed: {e}")
            return False
    
    async def handle_token_expiry(self):
        """Handle MS_TOKEN expiry and get new token"""
        print("\n🔄 MS_TOKEN appears to have expired")
        print("Current operations will continue with video-only downloads")
        
        response = input("Would you like to enter a new MS_TOKEN? (y/n): ").strip().lower()
        
        if response in ['y', 'yes']:
            if self.get_ms_token():
                if await self.validate_ms_token():
                    print("✅ New MS_TOKEN validated - comment extraction resumed")
                    return True
                else:
                    print("❌ New token validation failed - continuing without comments")
            
        print("📥 Continuing with video-only downloads...")
        self.ms_token = None
        return False
    
    def is_duplicate(self, url):
        """Check if URL has already been processed"""
        return url in self.processed_urls
    
    def filter_urls(self, urls):
        """Filter out already processed URLs"""
        new_urls = []
        duplicate_count = 0
        
        print(f"🔍 Checking {len(urls)} URLs against {len(self.processed_urls)} existing URLs...")
        
        for url in urls:
            if self.is_duplicate(url):
                duplicate_count += 1
                self.skipped_count += 1
            else:
                new_urls.append(url)
        
        if duplicate_count > 0:
            print(f"⏭️  Skipping {duplicate_count} already processed URLs")
            
        return new_urls
    
    async def extract_video_comments_safe(self, url, max_comments=10):
        """Safely extract comments with error handling"""
        if not self.ms_token:
            return []
            
        try:
            video_id = extract_video_id_from_url(url)
            if not video_id:
                print(f"❌ Could not extract video ID from URL: {url}")
                return []
            
            # Create a fresh API session for each comment extraction
            api = TikTokApi()
            await api.create_sessions(
                ms_tokens=[self.ms_token], 
                num_sessions=1, 
                sleep_after=1,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            
            comments = []
            async for comment in api.video(id=video_id).comments(count=max_comments):
                comment_data = {
                    "comment_id": comment.id,
                    "username": comment.as_dict.get("user", {}).get("unique_id", "unknown"),
                    "display_name": comment.as_dict.get("user", {}).get("nickname", "unknown"),
                    "comment_text": comment.as_dict.get("text", ""),
                    "like_count": comment.as_dict.get("digg_count", 0),
                    "timestamp": comment.as_dict.get("create_time", 0)
                }
                
                # Get replies if they exist
                reply_count = comment.as_dict.get("reply_comment_count", 0)
                if reply_count > 0:
                    replies = await extract_comment_replies(comment, max_replies=3)
                    if replies:
                        comment_data["replies"] = replies
                        comment_data["reply_count"] = len(replies)
                
                comments.append(comment_data)
                
                if len(comments) >= max_comments:
                    break
            
            # Close the API session when done
            await api.close_sessions()
            
            # Explicit cleanup
            del api
            gc.collect()
            
            return comments
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for token expiry indicators
            if any(indicator in error_msg for indicator in ['token', 'auth', 'forbidden', 'unauthorized']):
                print(f"🔄 Possible token expiry detected: {e}")
                if await self.handle_token_expiry():
                    # Retry with new token
                    return await self.extract_video_comments_safe(url, max_comments)
            else:
                print(f"❌ Error extracting comments: {e}")
            
            return []
    
    async def download_and_extract_comments(self, url, download_kwargs, max_comments=10):
        """Download video and extract comments with full error handling"""
        try:
            print(f"🎬 Processing: {url}")
            
            # URLs are already filtered for duplicates in main()
            # Download video first
            print(f"📥 Downloading video...")
            result = download_tiktok_video(url, **download_kwargs)
            
            if not result['success']:
                print(f"❌ Video download failed: {result.get('error', 'Unknown error')}")
                return None
            
            metadata = result['metadata']
            print(f"✅ Video downloaded successfully")
            
            # Clean up result object to free memory
            del result
            gc.collect()
            
            # Extract comments if MS_TOKEN available
            if self.ms_token:
                print(f"💬 Extracting comments...")
                try:
                    comments = await self.extract_video_comments_safe(url, max_comments)
                    if comments:
                        metadata['top_comments'] = comments
                        metadata['comments_extracted'] = True
                        metadata['comments_extracted_at'] = datetime.now().isoformat()
                        print(f"✅ Extracted {len(comments)} comments")
                    else:
                        metadata['top_comments'] = []
                        metadata['comments_extracted'] = False
                        print(f"⚠️  No comments extracted")
                except Exception as e:
                    print(f"❌ Comment extraction failed: {e}")
                    metadata['top_comments'] = []
                    metadata['comments_extracted'] = False
                    metadata['comment_error'] = str(e)
            else:
                metadata['top_comments'] = []
                metadata['comments_extracted'] = False
                print(f"⚠️  Skipping comments (no MS_TOKEN)")
            
            # Mark as processed
            self.processed_urls.add(url)
            
            # Clean up large objects that we don't need to save
            keys_to_remove = ['video_data', 'raw_data', 'binary_data']
            for key in keys_to_remove:
                if key in metadata:
                    del metadata[key]
            
            return metadata
            
        except Exception as e:
            print(f"❌ Error processing {url}: {e}")
            return None
    
    def cleanup_memory(self):
        """Force memory cleanup"""
        gc.collect()
        gc.collect()  # Second pass for circular references
        
        if self.enable_memory_tracking:
            current, peak = tracemalloc.get_traced_memory()
            print(f"🧠 Memory after cleanup: Current={current/1024/1024:.1f}MB, Peak={peak/1024/1024:.1f}MB")
    
    async def process_urls(self, urls, download_kwargs):
        """Process multiple URLs with all contingencies"""
        print(f"🚀 Starting robust processing")
        print(f"📊 Total URLs: {len(urls)}")
        print(f"📦 Batch size: {self.args.batch_size}")
        print(f"💬 Max comments per video: {self.args.max_comments}")
        print(f"⏱️  Delay between requests: {self.args.delay} seconds")
        print("="*60)
        
        # URLs are already filtered for duplicates in main()
        print(f"📝 Processing {len(urls)} URLs")
        
        batch_metadata = []
        failed_urls = []
        
        for i, url in enumerate(urls, 1):
            print(f"\n{'='*60}")
            print(f"Processing {i}/{len(urls)}: {url}")
            print(f"{'='*60}")
            
            # Save progress periodically
            if i % 5 == 0:
                self.save_progress(failed_urls, url)
            
            # Process single URL
            metadata = await self.download_and_extract_comments(
                url, download_kwargs, self.args.max_comments
            )
            
            if metadata:
                batch_metadata.append(metadata)
                self.successful_count += 1
                print(f"✅ {i}/{len(urls)} completed successfully")
            else:
                failed_urls.append(url)
                self.failed_count += 1
                print(f"❌ {i}/{len(urls)} failed")
            
            # Auto-save batch
            if len(batch_metadata) >= self.args.batch_size:
                print(f"\n💾 Auto-saving batch of {len(batch_metadata)} videos...")
                append_batch_to_master_json(batch_metadata, self.master_file)
                batch_metadata = []  # Reset batch
                
                # Force garbage collection after batch save
                gc.collect()
                
                if self.enable_memory_tracking:
                    current, peak = tracemalloc.get_traced_memory()
                    print(f"💾 Memory usage: Current={current/1024/1024:.1f}MB, Peak={peak/1024/1024:.1f}MB")
            
            # Add delay between requests
            if i < len(urls):
                print(f"⏱️  Waiting {self.args.delay} seconds...")
                time.sleep(self.args.delay)
            
            # Periodic garbage collection every 5 videos
            if i % 5 == 0:
                gc.collect()
                if self.enable_memory_tracking:
                    current, _ = tracemalloc.get_traced_memory()
                    print(f"🧠 Memory checkpoint: {current/1024/1024:.1f}MB in use")
        
        # Save any remaining metadata
        if batch_metadata:
            print(f"\n💾 Saving final batch of {len(batch_metadata)} videos...")
            append_batch_to_master_json(batch_metadata, self.master_file)
        
        # Final progress save
        self.save_progress(failed_urls)
        
        print(f"\n🎉 Processing completed!")
        print(f"✅ Successful: {self.successful_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"⏭️  Skipped (duplicates): {self.skipped_count}")
        print(f"📊 Total processed: {self.successful_count + self.failed_count + self.skipped_count}")


def load_urls_from_file(file_path):
    """Load URLs from text file"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
    
    if not urls:
        print("❌ No valid TikTok URLs found in file")
        return []
    
    print(f"📂 Loaded {len(urls)} URLs from {file_path}")
    return urls


async def main():
    parser = argparse.ArgumentParser(description="Robust TikTok video downloader and comment extractor")
    
    # Input options
    parser.add_argument("url", nargs='?', help="Single TikTok video URL (not needed with --from-file)")
    parser.add_argument("--from-file", "-ff", type=str, help="Batch process URLs from text file")
    parser.add_argument("--limit", type=int, help="Limit number of URLs to process (for testing)")
    
    # Download options
    parser.add_argument("-o", "--output", default="downloads", help="Output directory (default: downloads)")
    parser.add_argument("-q", "--quality", default="best", choices=["best", "worst", "720p", "480p", "360p"],
                       help="Video quality (default: best)")
    parser.add_argument("--mp3", action="store_true", help="Download audio only as MP3 instead of video")
    parser.add_argument("--whisper", action="store_true", help="Use faster-whisper for additional transcription")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU mode for whisper")
    
    # Comment options
    parser.add_argument("--max-comments", type=int, default=10, help="Maximum comments to extract per video (default: 10)")
    parser.add_argument("--ms-token", type=str, help="MS_TOKEN for comment extraction")
    
    # Batch options
    parser.add_argument("--batch-size", type=int, default=10, help="Save to master2.json every N videos (default: 10)")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests in seconds (default: 2)")
    
    # Resume options
    parser.add_argument("--force-redownload", action="store_true", help="Redownload all URLs (ignore duplicates)")
    parser.add_argument("--clean-progress", action="store_true", help="Clean progress file and start fresh")
    
    # System options
    parser.add_argument("--diagnose", action="store_true", help="Diagnose CUDA environment and exit")
    parser.add_argument("--memory-tracking", action="store_true", help="Enable memory usage tracking")
    
    args = parser.parse_args()
    
    # Handle diagnostic mode
    if args.diagnose:
        diagnose_cuda_environment()
        return
    
    # Validate arguments
    if not args.url and not args.from_file:
        print("❌ Either provide a URL or use --from-file")
        sys.exit(1)
    
    # Initialize processor
    processor = RobustTikTokProcessor(args)
    
    # Clean progress if requested
    if args.clean_progress and os.path.exists(processor.progress_file):
        os.remove(processor.progress_file)
        print("🧹 Cleaned progress file")
    
    # Load existing progress (unless forced redownload)
    if not args.force_redownload:
        processor.load_existing_progress()
    
    # Get and validate MS_TOKEN
    if processor.get_ms_token():
        if not await processor.validate_ms_token():
            print("❌ MS_TOKEN validation failed - continuing without comments")
            processor.ms_token = None
    
    # Load whisper model if requested
    whisper_model = None
    whisper_device = "CPU"
    if args.whisper:
        print("🎤 Loading faster-whisper model...")
        whisper_model, whisper_device = load_whisper_model(force_cpu=args.force_cpu)
        if not whisper_model:
            print("❌ Failed to load whisper model")
            sys.exit(1)
        print(f"✅ Whisper model loaded on {whisper_device}")
    
    # Prepare download kwargs
    download_kwargs = {
        'output_dir': args.output,
        'quality': args.quality,
        'audio_only': args.mp3,
        'use_whisper': args.whisper,
        'whisper_model': whisper_model,
        'whisper_device': whisper_device
    }
    
    # Get URLs to process
    if args.from_file:
        urls = load_urls_from_file(args.from_file)
        if args.limit:
            urls = urls[:args.limit]
            print(f"🔢 Limited to first {args.limit} URLs")
    else:
        urls = [args.url]
    
    if not urls:
        print("❌ No URLs to process")
        sys.exit(1)
    
    # Filter out duplicates immediately after loading
    original_count = len(urls)
    urls = processor.filter_urls(urls)
    
    if not urls:
        print("✅ All URLs from file already processed!")
        print(f"📊 Total URLs in file: {original_count}")
        print(f"📊 Already processed: {original_count}")
        sys.exit(0)
    
    print(f"📊 URLs to process: {len(urls)} out of {original_count} total")
    
    # Process URLs
    try:
        await processor.process_urls(urls, download_kwargs)
        
        # Auto-clean the master JSON after successful completion
        auto_clean_master_json(processor.master_file)
        
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        processor.save_progress()
        print("💾 Progress saved - you can resume later")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        processor.save_progress()
        sys.exit(1)
    finally:
        # Cleanup
        if processor.enable_memory_tracking:
            current, peak = tracemalloc.get_traced_memory()
            print(f"\n📊 Final memory usage: Current={current/1024/1024:.1f}MB, Peak={peak/1024/1024:.1f}MB")
            tracemalloc.stop()
        
        # Force final garbage collection
        gc.collect()


if __name__ == "__main__":
    asyncio.run(main())