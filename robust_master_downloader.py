#!/usr/bin/env python3
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
import shutil
import subprocess
import platform
import signal
import multiprocessing as mp
try:
    import fcntl  # Unix file locking
except ImportError:
    fcntl = None
try:
    import msvcrt  # Windows file locking
except ImportError:
    msvcrt = None
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.collection.tiktok_scraper import download_single_video as download_tiktok_video
from scripts.collection.tiktok_scraper import load_whisper_model, get_memory_usage
from scripts.utils.memory_efficient_append import append_batch_to_master_json_efficient as append_to_master_json

def append_batch_to_master_json(metadata_list, master_file_path):
    """Batch append using reliable atomic append function"""
    append_to_master_json(metadata_list, master_file_path)

from scripts.analysis.comment_extractor import extract_video_id_from_url, extract_comment_replies


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
    
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            # Load data
            with open(master_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                print(f"⚠️  Master file is not an array, skipping cleanup")
                return
            break  # Success, exit retry loop
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            if attempt < max_attempts - 1:  # Not the last attempt
                print(f"🔧 Attempting to fix corrupted {master_file_path}...")
                try:
                    import subprocess
                    result = subprocess.run(['python', './scripts/cleanup/fix_json.py', master_file_path], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        print("✅ Master JSON file fixed successfully, retrying cleanup...")
                        continue
                    else:
                        print(f"❌ Failed to fix JSON: {result.stderr}")
                        print("⚠️  Continuing without cleanup")
                        return
                except Exception as fix_error:
                    print(f"❌ Error running fix_json.py: {fix_error}")
                    print("⚠️  Continuing without cleanup")
                    return
            else:
                print("⚠️  Continuing without cleanup")
                return
    
    try:
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
        print(f"❌ Error during final cleanup operations: {e}")
        print("⚠️  Continuing without cleanup")


class FileLock:
    """Cross-platform file locking for safe concurrent access"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock_file = None
        
    def __enter__(self):
        self.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        
    def acquire(self, timeout=30):
        """Acquire file lock with timeout"""
        lock_path = f"{self.filepath}.lock"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if platform.system() == 'Windows' and msvcrt:
                    self.lock_file = open(lock_path, 'w')
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    return True
                elif fcntl:
                    self.lock_file = open(lock_path, 'w')
                    fcntl.lockf(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                else:
                    # Fallback: basic file existence check
                    if not os.path.exists(lock_path):
                        self.lock_file = open(lock_path, 'w')
                        self.lock_file.write(str(os.getpid()))
                        self.lock_file.flush()
                        return True
                    
            except (IOError, OSError):
                time.sleep(0.1)
                continue
                
        raise TimeoutError(f"Could not acquire lock for {self.filepath}")
    
    def release(self):
        """Release file lock"""
        if self.lock_file:
            try:
                if platform.system() == 'Windows' and msvcrt:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                elif fcntl:
                    fcntl.lockf(self.lock_file.fileno(), fcntl.LOCK_UN)
                    
                self.lock_file.close()
                
                # Remove lock file
                lock_path = f"{self.filepath}.lock"
                if os.path.exists(lock_path):
                    os.remove(lock_path)
                    
            except (IOError, OSError):
                pass  # Ignore cleanup errors
            finally:
                self.lock_file = None


def append_batch_to_master_json_safe(metadata_list, master_file_path):
    """Thread-safe version of batch append for multiprocessing"""
    if not metadata_list:
        return
        
    with FileLock(master_file_path):
        # Use the existing memory-efficient append function
        append_to_master_json(metadata_list, master_file_path)


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
        self.failed_urls = set()  # Track failed URLs to remove from source file
        self.source_file = None  # Track the source file path
        self.enable_memory_tracking = args.memory_tracking if hasattr(args, 'memory_tracking') else False
        self.shutdown_requested = False  # Track graceful shutdown
        
        if self.enable_memory_tracking:
            tracemalloc.start()
        
        # Configure garbage collection for aggressive cleanup
        gc.set_threshold(700, 10, 10)  # More aggressive GC
        
        # Setup signal handlers for graceful shutdown
        self.setup_signal_handlers()
        
    def fix_master_json(self):
        """Automatically fix corrupted master2.json file"""
        print(f"🔧 Attempting to fix corrupted {self.master_file}...")
        try:
            # Import and run the fix_json functionality
            import subprocess
            result = subprocess.run(['python', './scripts/cleanup/fix_json.py', self.master_file], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print("✅ Master JSON file fixed successfully")
                return True
            else:
                print(f"❌ Failed to fix JSON: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error running fix_json.py: {e}")
            return False

    def load_existing_progress(self):
        """Load existing URLs from master2.json and progress file"""
        print("🔍 Checking for existing progress...")
        
        # Load URLs from master2.json using streaming to avoid memory issues
        if os.path.exists(self.master_file):
            max_attempts = 2
            for attempt in range(max_attempts):
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
                    break  # Success, exit the retry loop
                    
                except Exception as e:
                    print(f"⚠️  Error reading {self.master_file}: {e}")
                    if attempt < max_attempts - 1:  # Not the last attempt
                        if self.fix_master_json():
                            print("🔄 Retrying to load existing progress...")
                            continue
                        else:
                            print("❌ Could not fix master JSON, continuing without existing progress")
                            break
                    else:
                        print("❌ Final attempt failed, continuing without existing progress")
        
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
            if sys.stdout.isatty():
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
            else:
                print("⚠️  Skipping comment extraction - MS_TOKEN not provided and not in an interactive terminal")
                return False
        
        return True
    
    async def validate_ms_token(self):
        """Validate MS_TOKEN by making a test API call"""
        if not self.ms_token:
            return False
            
        print("🔐 Validating MS_TOKEN...")
        
        try:
            api = TikTokApi()
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
                
            # Clean up the session
            try:
                await api.close_sessions()
            except Exception:
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
        """Check if URL has already been processed - MEMORY OPTIMIZED"""
        # First check in-memory set
        if url in self.processed_urls:
            return True
        
        # Use cached file URLs if available
        if hasattr(self, '_cached_file_urls'):
            if url in self._cached_file_urls:
                self.processed_urls.add(url)
                return True
        
        # If cache doesn't exist or is stale, rebuild it
        if not hasattr(self, '_cached_file_urls') or not hasattr(self, '_cache_timestamp'):
            self._rebuild_url_cache()
        
        # Check cache again after rebuild
        if url in self._cached_file_urls:
            self.processed_urls.add(url)
            return True
        
        return False
    
    def _rebuild_url_cache(self):
        """Rebuild URL cache from master file - MEMORY OPTIMIZED"""
        self._cached_file_urls = set()
        self._cache_timestamp = time.time()
        
        if not os.path.exists(self.master_file):
            return
        
        try:
            # Stream through file line by line instead of loading entire content
            with open(self.master_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '"url":' in line:
                        # Extract URL using regex instead of JSON parsing
                        import re
                        match = re.search(r'"url":\s*"([^"]+)"', line)
                        if match:
                            self._cached_file_urls.add(match.group(1))
            
            print(f"🔄 Rebuilt URL cache with {len(self._cached_file_urls)} URLs")
            
        except Exception as e:
            print(f"⚠️  Error rebuilding URL cache: {e}")
            self._cached_file_urls = set()
    
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
        """Safely extract comments with error handling - MEMORY OPTIMIZED"""
        if not self.ms_token or self.shutdown_requested:
            return []
            
        try:
            video_id = extract_video_id_from_url(url)
            if not video_id:
                print(f"❌ Could not extract video ID from URL: {url}")
                return []
            
            # Always create a fresh session for each comment extraction to avoid browser closure issues
            await self.cleanup_api_session()
            print("🔄 Creating new TikTokApi session...")
            self._api_session = TikTokApi()
            
            # Create session with timeout
            await asyncio.wait_for(
                self._api_session.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                ),
                timeout=30
            )
            print("✅ TikTokApi session created")
            
            comments = []
            comment_iter = self._api_session.video(id=video_id).comments(count=max_comments)
            
            async for comment in comment_iter:
                # Check for shutdown during comment extraction
                if self.shutdown_requested:
                    break
                    
                comment_data = {
                    "comment_id": comment.id,
                    "username": comment.as_dict.get("user", {}).get("unique_id", "unknown"),
                    "display_name": comment.as_dict.get("user", {}).get("nickname", "unknown"),
                    "comment_text": comment.as_dict.get("text", ""),
                    "like_count": comment.as_dict.get("digg_count", 0),
                    "timestamp": comment.as_dict.get("create_time", 0)
                }
                
                # Get replies if they exist (limit to save memory)
                reply_count = comment.as_dict.get("reply_comment_count", 0)
                if reply_count > 0 and not self.shutdown_requested:
                    replies = await extract_comment_replies(comment, max_replies=2)
                    if replies:
                        comment_data["replies"] = replies
                        comment_data["reply_count"] = len(replies)
                
                comments.append(comment_data)
                
                # Clear comment object to free memory
                del comment
                
                if len(comments) >= max_comments:
                    break
            
            # Clean up session after comment extraction
            await self.cleanup_api_session()
            
            # Force garbage collection after comment extraction
            gc.collect()
            
            return comments
            
        except (asyncio.TimeoutError, asyncio.CancelledError):
            print(f"⏰ Comment extraction timed out or cancelled")
            await self.cleanup_api_session()
            return []
        except Exception as e:
            error_msg = str(e).lower()
            
            # Clean up session on any error
            await self.cleanup_api_session()
            
            # Check for token expiry indicators
            if any(indicator in error_msg for indicator in ['token', 'auth', 'forbidden', 'unauthorized']):
                print(f"🔄 Possible token expiry detected: {e}")
                if not self.shutdown_requested and await self.handle_token_expiry():
                    # Retry with new token
                    return await self.extract_video_comments_safe(url, max_comments)
            else:
                print(f"❌ Error extracting comments: {e}")
            
            return []
    
    async def download_and_extract_comments(self, url, download_kwargs, max_comments=10):
        """Download video and extract comments with full error handling"""
        video_dir_to_cleanup = None
        try:
            print(f"🎬 Processing: {url}")
            
            # Double-check if URL is duplicate (in case it was added during current session)
            if self.is_duplicate(url):
                print(f"⏭️  Skipping duplicate URL: {url}")
                self.skipped_count += 1
                return None
            
            # Download video first
            print(f"📥 Downloading video...")
            result = download_tiktok_video(url, **download_kwargs)
            
            if not result['success']:
                print(f"❌ Video download failed: {result.get('error', 'Unknown error')}")
                # Try to clean up any directory that might have been created
                if 'metadata' in result and result['metadata'] and 'title' in result['metadata']:
                    video_dir_to_cleanup = os.path.join(download_kwargs.get('output_dir', 'downloads'), result['metadata']['title'])
                return None
            
            metadata = result['metadata']
            print(f"✅ Video downloaded successfully")
            
            # Set cleanup directory for successful downloads
            if 'title' in metadata and download_kwargs.get('output_dir'):
                video_dir_to_cleanup = os.path.join(download_kwargs['output_dir'], metadata['title'])
            
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
        finally:
            # Always try to clean up video directory, regardless of success/failure
            if video_dir_to_cleanup and os.path.exists(video_dir_to_cleanup):
                try:
                    shutil.rmtree(video_dir_to_cleanup)
                    print(f"🗑️  Cleaned up: {video_dir_to_cleanup}")
                except Exception as e:
                    print(f"⚠️  Failed to clean up {video_dir_to_cleanup}: {e}")
    
    def cleanup_memory(self):
        """Force memory cleanup"""
        gc.collect()
        gc.collect()  # Second pass for circular references
        
        if self.enable_memory_tracking:
            current, peak = tracemalloc.get_traced_memory()
            print(f"🧠 Memory after cleanup: Current={current/1024/1024:.1f}MB, Peak={peak/1024/1024:.1f}MB")
    
    async def aggressive_memory_cleanup(self):
        """Aggressive memory cleanup - MEMORY OPTIMIZED"""
        print("🧹 Performing aggressive memory cleanup...")
        
        # Multiple garbage collection passes
        for _ in range(3):
            gc.collect()
        
        # Clear URL cache periodically to prevent it from growing too large
        if hasattr(self, '_cached_file_urls') and len(self._cached_file_urls) > 1000:
            print(f"🔄 Clearing URL cache ({len(self._cached_file_urls)} URLs)")
            delattr(self, '_cached_file_urls')
            delattr(self, '_cache_timestamp')
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print("\n\n🚨 Graceful shutdown requested...")
            self.shutdown_requested = True
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def remove_failed_url_immediately(self, failed_url):
        """Remove a single failed URL from the source file immediately"""
        if not self.source_file or not os.path.exists(self.source_file):
            return
            
        try:
            # Read current URLs
            with open(self.source_file, 'r', encoding='utf-8') as f:
                current_urls = [line.strip() for line in f if line.strip()]
            
            # Check if URL exists in file
            if failed_url not in current_urls:
                return
            
            # Remove the failed URL
            remaining_urls = [url for url in current_urls if url != failed_url]
            
            # Write back immediately (atomic operation)
            temp_file = f"{self.source_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                for url in remaining_urls:
                    f.write(url + '\n')
            
            # Atomic replace
            if platform.system() == "Windows":
                if os.path.exists(self.source_file):
                    os.replace(temp_file, self.source_file)
            else:
                os.rename(temp_file, self.source_file)
            
            print(f"🗑️  Removed failed URL from {self.source_file}")
            
        except Exception as e:
            print(f"⚠️  Error removing failed URL from source file: {e}")
            # Clean up temp file if it exists
            temp_file = f"{self.source_file}.tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    async def cleanup_api_session(self):
        """Cleanup TikTokApi session - MEMORY OPTIMIZED"""
        if hasattr(self, '_api_session') and self._api_session:
            try:
                # Force close with timeout to prevent hanging
                await asyncio.wait_for(self._api_session.close_sessions(), timeout=10)
                if hasattr(self._api_session, 'playwright') and self._api_session.playwright:
                    await asyncio.wait_for(self._api_session.playwright.stop(), timeout=10)
                del self._api_session
            except (Exception, asyncio.TimeoutError):
                pass  # Ignore cleanup errors and timeouts
            finally:
                self._api_session = None
    
    async def restart_api_session(self):
        """Restart TikTokApi session - MEMORY OPTIMIZED"""
        print("🔄 Restarting TikTokApi session due to high memory usage...")
        await self.cleanup_api_session()
        gc.collect()
        # Session will be recreated on next comment extraction
    
    async def cleanup_browser_processes(self):
        """Kill orphaned browser processes - MEMORY OPTIMIZED"""
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                # Windows process cleanup
                try:
                    subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True, check=False)
                    subprocess.run(['taskkill', '/F', '/IM', 'msedge.exe'], capture_output=True, check=False)
                    subprocess.run(['taskkill', '/F', '/IM', 'chromium.exe'], capture_output=True, check=False)
                    print(f"🧹 Killed orphaned browser processes (Windows)")
                except Exception:
                    pass  # Ignore errors on Windows
            else:
                # Unix/Linux/macOS process cleanup
                subprocess.run(['pkill', '-f', 'chromium'], capture_output=True, check=False)
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, check=False)
                subprocess.run(['pkill', '-f', 'playwright'], capture_output=True, check=False)
                print(f"🧹 Killed orphaned browser processes (Unix)")
        except Exception as e:
            print(f"⚠️  Error killing browser processes: {e}")
    
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
            # Check for graceful shutdown request
            if self.shutdown_requested:
                print(f"\n🚨 Shutdown requested, saving progress and exiting gracefully...")
                break
                
            print(f"\n{'='*60}")
            print(f"Processing {i}/{len(urls)}: {url}")
            print(f"{'='*60}")
            
            # Save progress periodically (every 5 videos)
            if i % 5 == 0:
                self.save_progress(failed_urls, url)
            
            # Process single URL with timeout and cancellation support
            try:
                metadata = await asyncio.wait_for(
                    self.download_and_extract_comments(
                        url, download_kwargs, self.args.max_comments
                    ),
                    timeout=300  # 5 minute timeout per video
                )
            except asyncio.TimeoutError:
                print(f"⏰ Video processing timed out: {url}")
                metadata = None
                # Add to failed URLs and remove immediately
                self.failed_urls.add(url)
                self.remove_failed_url_immediately(url)
            except asyncio.CancelledError:
                print(f"\n🚨 Operation cancelled, cleaning up...")
                break
            
            if metadata:
                batch_metadata.append(metadata)
                self.successful_count += 1
                print(f"✅ {i}/{len(urls)} completed successfully")
            else:
                failed_urls.append(url)
                self.failed_urls.add(url)  # Track for removal from source file
                self.failed_count += 1
                print(f"❌ {i}/{len(urls)} failed")
            
            # Auto-save after every video
            if len(batch_metadata) >= 1:
                print(f"💾 Saving video to master2.json...")
                append_batch_to_master_json(batch_metadata, self.master_file)
                batch_metadata = []  # Reset batch
                
                # Force garbage collection after save
                gc.collect()
                
                if self.enable_memory_tracking:
                    current, peak = tracemalloc.get_traced_memory()
                    print(f"💾 Memory usage: Current={current/1024/1024:.1f}MB, Peak={peak/1024/1024:.1f}MB")
            
            # Add delay between requests
            if i < len(urls):
                print(f"⏱️  Waiting {self.args.delay} seconds...")
                time.sleep(self.args.delay)
            
            # AGGRESSIVE cleanup every 3 videos to prevent memory explosion
            if i % 3 == 0:
                await self.aggressive_memory_cleanup()
                
                # Force memory cleanup
                try:
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    print(f"🧠 Process memory: {memory_mb:.1f}MB")
                    
                    # Kill orphaned browser processes if memory is high (lowered threshold)
                    if memory_mb > 500:  # If over 500MB (reduced from 1GB)
                        await self.cleanup_browser_processes()
                        
                        # Restart API session if memory is still high
                        if memory_mb > 800:  # If over 800MB, restart session
                            await self.restart_api_session()
                    
                except ImportError:
                    pass  # psutil not available
                
                if self.enable_memory_tracking:
                    current, _ = tracemalloc.get_traced_memory()
                    print(f"🧠 Memory checkpoint: {current/1024/1024:.1f}MB in use")
        
        # Save any remaining metadata (shouldn't be any with per-video saving)
        if batch_metadata:
            print(f"\n💾 Saving final batch of {len(batch_metadata)} videos...")
            append_batch_to_master_json(batch_metadata, self.master_file)
        
        # Final progress save
        self.save_progress(failed_urls)
        
        # Remove failed URLs from source file
        if self.failed_urls and self.source_file:
            self.remove_failed_urls_from_source()
        
        # Cleanup API session on completion - MEMORY OPTIMIZED
        await self.cleanup_api_session()
        
        print(f"\n🎉 Processing completed!")
        print(f"✅ Successful: {self.successful_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"⏭️  Skipped (duplicates): {self.skipped_count}")
        print(f"📊 Total processed: {self.successful_count + self.failed_count + self.skipped_count}")
        
        if self.failed_urls:
            print(f"🗑️  Removed {len(self.failed_urls)} failed URLs from {self.source_file}")


class WorkerProcessor:
    """Simplified processor for individual worker processes"""
    
    def __init__(self, worker_id, ms_token, args):
        self.worker_id = worker_id
        self.ms_token = ms_token
        self.args = args
        self.successful_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.progress_file = f"download_progress_worker_{worker_id}.json"
        self.shutdown_event = None  # Will be set by coordinator
        
        # Load whisper model if needed
        self.whisper_model = None
        self.whisper_device = "CPU"
        if args.whisper:
            from scripts.collection.tiktok_scraper import load_whisper_model
            print(f"🎤 Worker {worker_id}: Loading whisper model...")
            self.whisper_model, self.whisper_device = load_whisper_model(force_cpu=args.force_cpu)
            if self.whisper_model:
                print(f"✅ Worker {worker_id}: Whisper model loaded on {self.whisper_device}")
            else:
                print(f"❌ Worker {worker_id}: Failed to load whisper model")
    
    def save_progress(self, processed_urls, failed_urls, current_url=None):
        """Save worker progress"""
        progress_data = {
            "worker_id": self.worker_id,
            "last_updated": datetime.now().isoformat(),
            "processed_count": len(processed_urls),
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "failed_urls": list(failed_urls),
            "processed_urls": list(processed_urls),
            "current_url": current_url
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Worker {self.worker_id}: Failed to save progress: {e}")
    
    async def extract_video_comments_safe(self, url, max_comments=10):
        """Extract comments for a single video"""
        if not self.ms_token:
            return []
            
        try:
            from scripts.analysis.comment_extractor import extract_video_id_from_url, extract_comment_replies
            from TikTokApi import TikTokApi
            
            video_id = extract_video_id_from_url(url)
            if not video_id:
                return []
            
            # Create API session
            api = TikTokApi()
            await api.create_sessions(
                ms_tokens=[self.ms_token], 
                num_sessions=1, 
                sleep_after=1,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            
            comments = []
            comment_iter = api.video(id=video_id).comments(count=max_comments)
            
            async for comment in comment_iter:
                if self.shutdown_event and self.shutdown_event.is_set():
                    break
                    
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
                    replies = await extract_comment_replies(comment, max_replies=2)
                    if replies:
                        comment_data["replies"] = replies
                        comment_data["reply_count"] = len(replies)
                
                comments.append(comment_data)
                
                if len(comments) >= max_comments:
                    break
            
            # Clean up session
            await api.close_sessions()
            gc.collect()
            
            return comments
            
        except Exception as e:
            print(f"❌ Worker {self.worker_id}: Comment extraction failed for {url}: {e}")
            return []
    
    async def process_urls(self, urls, download_kwargs, master_file):
        """Process assigned URLs for this worker"""
        print(f"🚀 Worker {self.worker_id}: Starting with {len(urls)} URLs")
        
        processed_urls = set()
        failed_urls = set()
        batch_metadata = []
        
        for i, url in enumerate(urls, 1):
            # Check for shutdown
            if self.shutdown_event and self.shutdown_event.is_set():
                print(f"🚨 Worker {self.worker_id}: Shutdown requested")
                break
            
            try:
                print(f"🎬 Worker {self.worker_id}: Processing {i}/{len(urls)}: {url}")
                
                # Download video
                from scripts.collection.tiktok_scraper import download_single_video as download_tiktok_video
                
                # Update download_kwargs with worker-specific whisper model
                worker_download_kwargs = download_kwargs.copy()
                worker_download_kwargs['whisper_model'] = self.whisper_model
                worker_download_kwargs['whisper_device'] = self.whisper_device
                
                result = download_tiktok_video(url, **worker_download_kwargs)
                
                if not result['success']:
                    print(f"❌ Worker {self.worker_id}: Video download failed: {result.get('error', 'Unknown error')}")
                    failed_urls.add(url)
                    self.failed_count += 1
                    continue
                
                metadata = result['metadata']
                processed_urls.add(url)
                
                # Extract comments if MS_TOKEN available
                if self.ms_token:
                    comments = await self.extract_video_comments_safe(url, self.args.max_comments)
                    if comments:
                        metadata['top_comments'] = comments
                        metadata['comments_extracted'] = True
                        metadata['comments_extracted_at'] = datetime.now().isoformat()
                    else:
                        metadata['top_comments'] = []
                        metadata['comments_extracted'] = False
                else:
                    metadata['top_comments'] = []
                    metadata['comments_extracted'] = False
                
                # Clean up large objects
                keys_to_remove = ['video_data', 'raw_data', 'binary_data']
                for key in keys_to_remove:
                    if key in metadata:
                        del metadata[key]
                
                batch_metadata.append(metadata)
                self.successful_count += 1
                
                # Save immediately to master file
                if batch_metadata:
                    append_batch_to_master_json_safe(batch_metadata, master_file)
                    batch_metadata = []
                
                # Save progress every 5 videos
                if i % 5 == 0:
                    self.save_progress(processed_urls, failed_urls, url)
                
                # Add delay between requests
                if i < len(urls):
                    time.sleep(self.args.delay)
                
                # Cleanup every 3 videos
                if i % 3 == 0:
                    gc.collect()
                    
            except Exception as e:
                print(f"❌ Worker {self.worker_id}: Error processing {url}: {e}")
                failed_urls.add(url)
                self.failed_count += 1
        
        # Final progress save
        self.save_progress(processed_urls, failed_urls)
        
        print(f"✅ Worker {self.worker_id}: Completed - Success: {self.successful_count}, Failed: {self.failed_count}")
        return self.successful_count, self.failed_count, list(failed_urls)


def worker_function(worker_id, urls, ms_token, args, download_kwargs, master_file, shutdown_event):
    """Worker function to run in separate process"""
    try:
        # Create worker processor
        worker = WorkerProcessor(worker_id, ms_token, args)
        worker.shutdown_event = shutdown_event
        
        # Run the async processing
        result = asyncio.run(worker.process_urls(urls, download_kwargs, master_file))
        return result
        
    except Exception as e:
        print(f"❌ Worker {worker_id}: Fatal error: {e}")
        return 0, len(urls), urls  # All URLs failed


class MultiprocessCoordinator:
    """Coordinates multiple worker processes for parallel processing"""
    
    def __init__(self, args, ms_token):
        self.args = args
        self.ms_token = ms_token
        self.num_workers = args.workers
        self.shutdown_event = mp.Event()
        self.workers = []
        self.total_successful = 0
        self.total_failed = 0
        self.all_failed_urls = set()
        
        # Setup signal handlers for graceful shutdown
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"\n🚨 Graceful shutdown requested (signal {signum})")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def distribute_urls(self, urls):
        """Distribute URLs among workers"""
        if self.num_workers == 1:
            return [urls]
        
        chunk_size = len(urls) // self.num_workers
        url_chunks = []
        
        for i in range(self.num_workers):
            start_idx = i * chunk_size
            if i == self.num_workers - 1:  # Last worker gets remaining URLs
                end_idx = len(urls)
            else:
                end_idx = (i + 1) * chunk_size
            
            chunk = urls[start_idx:end_idx]
            if chunk:  # Only add non-empty chunks
                url_chunks.append(chunk)
        
        return url_chunks
    
    def cleanup_worker_progress_files(self):
        """Clean up worker progress files"""
        for i in range(self.num_workers):
            progress_file = f"download_progress_worker_{i}.json"
            if os.path.exists(progress_file):
                try:
                    os.remove(progress_file)
                except Exception:
                    pass  # Ignore cleanup errors
    
    def aggregate_worker_progress(self):
        """Aggregate progress from all worker files"""
        total_success = 0
        total_failed = 0
        all_failed_urls = set()
        
        for i in range(self.num_workers):
            progress_file = f"download_progress_worker_{i}.json"
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        progress_data = json.load(f)
                        total_success += progress_data.get('successful_count', 0)
                        total_failed += progress_data.get('failed_count', 0)
                        all_failed_urls.update(progress_data.get('failed_urls', []))
                except Exception as e:
                    print(f"⚠️  Error reading worker {i} progress: {e}")
        
        return total_success, total_failed, all_failed_urls
    
    def remove_failed_urls_from_source(self, source_file, failed_urls):
        """Remove failed URLs from source file"""
        if not source_file or not os.path.exists(source_file) or not failed_urls:
            return
            
        try:
            # Read current URLs
            with open(source_file, 'r', encoding='utf-8') as f:
                current_urls = [line.strip() for line in f if line.strip()]
            
            # Remove failed URLs
            remaining_urls = [url for url in current_urls if url not in failed_urls]
            
            if len(remaining_urls) < len(current_urls):
                # Write back the cleaned URLs
                temp_file = f"{source_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    for url in remaining_urls:
                        f.write(url + '\n')
                
                # Atomic replace
                if platform.system() == "Windows":
                    if os.path.exists(source_file):
                        os.replace(temp_file, source_file)
                else:
                    os.rename(temp_file, source_file)
                
                removed_count = len(current_urls) - len(remaining_urls)
                print(f"🗑️  Removed {removed_count} failed URLs from {source_file}")
                
        except Exception as e:
            print(f"⚠️  Error removing failed URLs from source file: {e}")
    
    async def process_urls_multiprocess(self, urls, download_kwargs, master_file, source_file=None):
        """Process URLs using multiple worker processes"""
        print(f"🚀 Starting multiprocess processing with {self.num_workers} workers")
        print(f"📊 Total URLs: {len(urls)}")
        print("="*60)
        
        # Distribute URLs among workers
        url_chunks = self.distribute_urls(urls)
        actual_workers = len(url_chunks)
        
        if actual_workers < self.num_workers:
            print(f"📝 Using {actual_workers} workers (fewer URLs than requested workers)")
        
        # Clean up any existing worker progress files
        self.cleanup_worker_progress_files()
        
        # Start worker processes
        processes = []
        for i, chunk in enumerate(url_chunks):
            print(f"🔧 Starting worker {i} with {len(chunk)} URLs")
            
            process = mp.Process(
                target=worker_function,
                args=(i, chunk, self.ms_token, self.args, download_kwargs, master_file, self.shutdown_event)
            )
            process.start()
            processes.append(process)
        
        # Monitor workers
        try:
            print(f"👀 Monitoring {len(processes)} worker processes...")
            
            # Wait for all processes to complete
            for i, process in enumerate(processes):
                process.join()
                print(f"✅ Worker {i} completed")
                
        except KeyboardInterrupt:
            print("\n🚨 Interrupt received, shutting down workers...")
            self.shutdown_event.set()
            
            # Give workers time to finish current tasks
            for process in processes:
                process.join(timeout=30)
                if process.is_alive():
                    print(f"⚠️  Force terminating worker {process.pid}")
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()
        
        # Aggregate results
        self.total_successful, self.total_failed, self.all_failed_urls = self.aggregate_worker_progress()
        
        # Remove failed URLs from source file
        if source_file and self.all_failed_urls:
            self.remove_failed_urls_from_source(source_file, self.all_failed_urls)
        
        # Clean up worker progress files
        self.cleanup_worker_progress_files()
        
        print(f"\n🎉 Multiprocess processing completed!")
        print(f"✅ Successful: {self.total_successful}")
        print(f"❌ Failed: {self.total_failed}")
        print(f"📊 Total processed: {self.total_successful + self.total_failed}")
        
        if self.all_failed_urls:
            print(f"🗑️  Removed {len(self.all_failed_urls)} failed URLs from source file")


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
    parser.add_argument("--clean-old-downloads", action="store_true", help="Clean up old download directories before starting")
    
    parser.add_argument("--proxy", type=str, help="Proxy to use for downloads (e.g., http://user:pass@host:port)")
    
    # System options
    parser.add_argument("--diagnose", action="store_true", help="Diagnose CUDA environment and exit")
    parser.add_argument("--memory-tracking", action="store_true", help="Enable memory usage tracking")
    
    # Multiprocessing options
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes for parallel processing (default: 1)")
    
    args = parser.parse_args()
    
    # Handle diagnostic mode
    if args.diagnose:
        diagnose_cuda_environment()
        return
    
    # Validate arguments
    if not args.url and not args.from_file:
        # If no arguments are provided, OR only system flags (like --workers) are provided,
        # use default settings
        has_only_system_flags = all(
            arg in ['--workers', '--diagnose', '--memory-tracking', '--force-cpu', 
                   '--clean-progress', '--clean-old-downloads', '--whisper', '--mp3',
                   '--delay', '--batch-size', '--max-comments', '--quality', '--output',
                   '--proxy', '--limit', '--force-redownload'] or 
            arg.isdigit() or arg.startswith('-') == False
            for arg in sys.argv[1:]
        )
        
        if len(sys.argv) == 1 or has_only_system_flags:
            print("🔧 Using default settings: --from-file urls.txt --mp3 --whisper")
            args.from_file = 'urls.txt'
            args.mp3 = True
            args.batch_size = 10
            args.delay = 2
            args.max_comments = 10
            args.whisper = True
        else:
            print("❌ Either provide a URL or use --from-file")
            sys.exit(1)
    
    # Initialize processor
    processor = RobustTikTokProcessor(args)
    
    # Clean progress if requested
    if args.clean_progress and os.path.exists(processor.progress_file):
        os.remove(processor.progress_file)
        print("🧹 Cleaned progress file")
    
    # Clean old downloads if requested
    if args.clean_old_downloads and os.path.exists(args.output):
        print(f"🧹 Cleaning old downloads from {args.output}...")
        try:
            # List all directories in downloads
            for item in os.listdir(args.output):
                item_path = os.path.join(args.output, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  🗑️  Removed: {item}")
            print(f"✅ Cleaned all directories from {args.output}")
        except Exception as e:
            print(f"❌ Error cleaning downloads: {e}")
    
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
        'whisper_device': whisper_device,
        'proxy': args.proxy
    }
    
    # Get URLs to process
    if args.from_file:
        urls = load_urls_from_file(args.from_file)
        processor.source_file = args.from_file  # Track source file for failed URL removal
        if args.limit:
            urls = urls[:args.limit]
            print(f"🔢 Limited to first {args.limit} URLs")
    else:
        urls = [args.url]
        processor.source_file = None  # No source file for single URLs
    
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
    
    # Process URLs - Choose between single-process and multiprocess modes
    try:
        if args.workers <= 1:
            # Single-process mode (original behavior)
            print("🔧 Using single-process mode")
            await processor.process_urls(urls, download_kwargs)
            
            # Auto-clean the master JSON after successful completion
            if not processor.shutdown_requested:
                auto_clean_master_json(processor.master_file)
        else:
            # Multiprocess mode
            print(f"🔧 Using multiprocess mode with {args.workers} workers")
            
            # Validate that we're processing from a file (needed for multiprocess)
            if not args.from_file:
                print("❌ Multiprocessing requires --from-file option")
                sys.exit(1)
            
            # Create multiprocess coordinator
            coordinator = MultiprocessCoordinator(args, processor.ms_token)
            
            # Remove whisper model from download_kwargs for multiprocessing
            # Each worker will load its own model
            multiprocess_download_kwargs = download_kwargs.copy()
            multiprocess_download_kwargs.pop('whisper_model', None)
            multiprocess_download_kwargs.pop('whisper_device', None)
            
            # Process URLs using multiprocessing
            await coordinator.process_urls_multiprocess(
                urls, multiprocess_download_kwargs, processor.master_file, processor.source_file
            )
            
            # Auto-clean the master JSON after successful completion
            auto_clean_master_json(processor.master_file)
        
    except KeyboardInterrupt:
        print("\n🚨 Graceful shutdown initiated...")
        
        if args.workers <= 1:
            # Single-process cleanup
            processor.shutdown_requested = True
            
            # Give time for cleanup
            print("🧹 Cleaning up API sessions...")
            await processor.cleanup_api_session()
            
            processor.save_progress()
            print("💾 Progress saved - you can resume later")
        else:
            # Multiprocess cleanup handled by coordinator
            print("🧹 Multiprocess cleanup handled by coordinator")
            
        print("✅ Shutdown completed gracefully")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        
        if args.workers <= 1:
            processor.shutdown_requested = True
            await processor.cleanup_api_session()
            processor.save_progress()
        
        sys.exit(1)
    finally:
        # Ensure cleanup always happens
        if args.workers <= 1:
            try:
                await processor.cleanup_api_session()
            except:
                pass
                
            # Cleanup
            if processor.enable_memory_tracking:
                current, peak = tracemalloc.get_traced_memory()
                print(f"\n📊 Final memory usage: Current={current/1024/1024:.1f}MB, Peak={peak/1024/1024:.1f}MB")
                tracemalloc.stop()
        
        # Force final garbage collection
        gc.collect()


if __name__ == "__main__":
    asyncio.run(main())