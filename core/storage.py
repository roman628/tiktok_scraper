#!/usr/bin/env python3
"""
Unified storage management for TikTok scraper
Consolidates all JSON and file operations
"""

import os
import json
import shutil
import threading
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime
from pathlib import Path

from .models import VideoMetadata, ProcessingSummary
from .utils import FileUtils, ValidationUtils
from .exceptions import StorageException, ErrorHandler


class StorageManager:
    """Unified storage manager for JSON operations and file management"""
    
    def __init__(self, master_file: str = "master2.json", 
                 error_handler: ErrorHandler = None):
        self.master_file = master_file
        self.error_handler = error_handler or ErrorHandler()
        self._file_lock = threading.Lock()
        self._url_cache = set()
        self._cache_timestamp = None
        
        # Initialize master file if it doesn't exist
        self._initialize_master_file()
    
    def _initialize_master_file(self):
        """Initialize master file if it doesn't exist"""
        if not os.path.exists(self.master_file):
            try:
                FileUtils.safe_json_save(self.master_file, [], create_backup=False)
                self.error_handler.handle_success(
                    f"Initialized master file: {self.master_file}",
                    "Storage"
                )
            except Exception as e:
                self.error_handler.handle_error(
                    StorageException(f"Failed to initialize master file: {e}"),
                    "Storage Initialization"
                )
    
    def load_existing_urls(self) -> set:
        """Load existing URLs from master file for duplicate detection"""
        self.error_handler.handle_info("Loading existing URLs...", "Storage")
        
        with self._file_lock:
            try:
                # Use streaming approach for large files
                urls = set()
                
                if not os.path.exists(self.master_file):
                    return urls
                
                # Try to use ijson for streaming if available
                try:
                    import ijson
                    with open(self.master_file, 'rb') as f:
                        parser = ijson.items(f, 'item.url')
                        for url in parser:
                            if url:
                                urls.add(url)
                except ImportError:
                    # Fallback to regular JSON loading
                    data = FileUtils.safe_json_load(self.master_file)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'url' in item:
                                urls.add(item['url'])
                
                self._url_cache = urls
                self._cache_timestamp = datetime.now()
                
                self.error_handler.handle_success(
                    f"Loaded {len(urls)} existing URLs",
                    "Storage"
                )
                
                return urls
                
            except Exception as e:
                self.error_handler.handle_error(
                    StorageException(f"Failed to load existing URLs: {e}"),
                    "Storage"
                )
                return set()
    
    def is_duplicate_url(self, url: str) -> bool:
        """Check if URL already exists in storage"""
        # Use cache if available and recent
        if (self._url_cache and self._cache_timestamp and 
            (datetime.now() - self._cache_timestamp).seconds < 300):  # 5 minute cache
            return url in self._url_cache
        
        # Refresh cache
        self._url_cache = self.load_existing_urls()
        return url in self._url_cache
    
    def append_videos(self, videos: List[VideoMetadata], 
                     remove_duplicates: bool = True) -> bool:
        """Append videos to master file with optional deduplication"""
        if not videos:
            return True
        
        try:
            with self._file_lock:
                # Convert to dictionaries
                video_dicts = [video.to_dict() for video in videos]
                
                # Load existing data
                existing_data = FileUtils.safe_json_load(self.master_file) or []
                
                if remove_duplicates:
                    # Filter out duplicates
                    existing_urls = {item.get('url') for item in existing_data if isinstance(item, dict)}
                    video_dicts = [v for v in video_dicts if v.get('url') not in existing_urls]
                    
                    if len(video_dicts) < len(videos):
                        self.error_handler.handle_info(
                            f"Filtered out {len(videos) - len(video_dicts)} duplicates",
                            "Storage"
                        )
                
                if not video_dicts:
                    return True
                
                # Append new videos
                existing_data.extend(video_dicts)
                
                # Save back to file
                success = FileUtils.safe_json_save(self.master_file, existing_data)
                
                if success:
                    # Update cache
                    for video_dict in video_dicts:
                        if video_dict.get('url'):
                            self._url_cache.add(video_dict['url'])
                    
                    self.error_handler.handle_success(
                        f"Saved {len(video_dicts)} videos to {self.master_file}",
                        "Storage"
                    )
                
                return success
                
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Failed to append videos: {e}"),
                "Storage"
            )
            return False
    
    def append_single_video(self, video: VideoMetadata) -> bool:
        """Append single video to master file (atomic operation)"""
        return self.append_videos([video])
    
    def load_all_videos(self) -> List[VideoMetadata]:
        """Load all videos from master file"""
        try:
            data = FileUtils.safe_json_load(self.master_file)
            if not isinstance(data, list):
                self.error_handler.handle_warning(
                    "Master file is not a valid array",
                    "Storage"
                )
                return []
            
            videos = []
            for item in data:
                if isinstance(item, dict):
                    try:
                        video = VideoMetadata.from_dict(item)
                        videos.append(video)
                    except Exception as e:
                        self.error_handler.handle_warning(
                            f"Failed to parse video metadata: {e}",
                            "Storage"
                        )
            
            self.error_handler.handle_success(
                f"Loaded {len(videos)} videos from {self.master_file}",
                "Storage"
            )
            
            return videos
            
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Failed to load videos: {e}"),
                "Storage"
            )
            return []
    
    def remove_duplicates(self) -> int:
        """Remove duplicate entries from master file, keeping most complete"""
        try:
            with self._file_lock:
                data = FileUtils.safe_json_load(self.master_file)
                if not isinstance(data, list):
                    return 0
                
                original_count = len(data)
                self.error_handler.handle_info(
                    f"Checking {original_count} entries for duplicates",
                    "Deduplication"
                )
                
                # Group by URL
                url_groups = {}
                non_url_entries = []
                
                for entry in data:
                    if isinstance(entry, dict) and 'url' in entry:
                        url = entry['url']
                        if url not in url_groups:
                            url_groups[url] = []
                        url_groups[url].append(entry)
                    else:
                        non_url_entries.append(entry)
                
                # Keep best entry for each URL
                deduplicated_data = []
                removed_count = 0
                
                for url, entries in url_groups.items():
                    if len(entries) == 1:
                        deduplicated_data.extend(entries)
                    else:
                        # Score entries and keep the best
                        best_entry = max(entries, key=ValidationUtils.calculate_completeness_score)
                        deduplicated_data.append(best_entry)
                        removed_count += len(entries) - 1
                
                # Add back non-URL entries
                deduplicated_data.extend(non_url_entries)
                
                if removed_count > 0:
                    # Save deduplicated data
                    success = FileUtils.safe_json_save(self.master_file, deduplicated_data)
                    
                    if success:
                        self.error_handler.handle_success(
                            f"Removed {removed_count} duplicate entries",
                            "Deduplication"
                        )
                        
                        # Update cache
                        self._url_cache = {entry.get('url') for entry in deduplicated_data 
                                         if isinstance(entry, dict) and entry.get('url')}
                        self._cache_timestamp = datetime.now()
                    
                    return removed_count
                else:
                    self.error_handler.handle_info(
                        "No duplicates found",
                        "Deduplication"
                    )
                    return 0
                
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Failed to remove duplicates: {e}"),
                "Deduplication"
            )
            return 0
    
    def clean_short_transcriptions(self, min_length: int = 50) -> int:
        """Remove entries with transcriptions shorter than min_length"""
        try:
            with self._file_lock:
                data = FileUtils.safe_json_load(self.master_file)
                if not isinstance(data, list):
                    return 0
                
                original_count = len(data)
                
                # Filter entries
                valid_entries = []
                removed_count = 0
                
                for entry in data:
                    if isinstance(entry, dict):
                        if ('url' not in entry or 
                            ValidationUtils.has_transcription(entry, min_length)):
                            valid_entries.append(entry)
                        else:
                            removed_count += 1
                    else:
                        valid_entries.append(entry)
                
                if removed_count > 0:
                    success = FileUtils.safe_json_save(self.master_file, valid_entries)
                    
                    if success:
                        self.error_handler.handle_success(
                            f"Removed {removed_count} entries with short transcriptions",
                            "Cleanup"
                        )
                        
                        # Update cache
                        self._url_cache = {entry.get('url') for entry in valid_entries 
                                         if isinstance(entry, dict) and entry.get('url')}
                        self._cache_timestamp = datetime.now()
                    
                    return removed_count
                else:
                    self.error_handler.handle_info(
                        "No entries with short transcriptions found",
                        "Cleanup"
                    )
                    return 0
                
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Failed to clean short transcriptions: {e}"),
                "Cleanup"
            )
            return 0
    
    def auto_cleanup(self) -> bool:
        """Perform automatic cleanup (deduplication + short transcription removal)"""
        try:
            self.error_handler.handle_info("Starting automatic cleanup", "Auto Cleanup")
            
            duplicates_removed = self.remove_duplicates()
            short_removed = self.clean_short_transcriptions()
            
            total_removed = duplicates_removed + short_removed
            
            if total_removed > 0:
                self.error_handler.handle_success(
                    f"Auto cleanup completed - removed {total_removed} entries",
                    "Auto Cleanup"
                )
            else:
                self.error_handler.handle_info(
                    "Auto cleanup completed - no changes needed",
                    "Auto Cleanup"
                )
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Auto cleanup failed: {e}"),
                "Auto Cleanup"
            )
            return False
    
    def repair_corrupted_file(self) -> bool:
        """Attempt to repair corrupted JSON file"""
        try:
            self.error_handler.handle_info(
                f"Attempting to repair {self.master_file}",
                "File Repair"
            )
            
            # Create backup first
            backup_path = FileUtils.create_backup(self.master_file)
            
            # Try to extract valid JSON objects
            valid_objects = []
            
            with open(self.master_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple repair: try to extract individual JSON objects
            import re
            
            # Look for JSON objects (simplified approach)
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, content, re.DOTALL)
            
            for match in matches:
                try:
                    obj = json.loads(match)
                    if isinstance(obj, dict) and 'url' in obj:
                        valid_objects.append(obj)
                except json.JSONDecodeError:
                    continue
            
            if valid_objects:
                success = FileUtils.safe_json_save(self.master_file, valid_objects)
                
                if success:
                    self.error_handler.handle_success(
                        f"Repaired file - recovered {len(valid_objects)} valid entries",
                        "File Repair"
                    )
                    return True
            
            self.error_handler.handle_error(
                StorageException("Could not repair file - no valid objects found"),
                "File Repair"
            )
            return False
            
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"File repair failed: {e}"),
                "File Repair"
            )
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            videos = self.load_all_videos()
            
            stats = {
                'total_videos': len(videos),
                'with_comments': sum(1 for v in videos if v.comments_extracted),
                'with_transcription': sum(1 for v in videos if v.has_valid_transcription()),
                'by_status': {},
                'file_size': os.path.getsize(self.master_file) if os.path.exists(self.master_file) else 0
            }
            
            # Count by status
            for video in videos:
                status = video.processing_status.value
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            return stats
            
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Failed to get statistics: {e}"),
                "Statistics"
            )
            return {}
    
    def create_backup(self) -> Optional[str]:
        """Create timestamped backup of master file"""
        return FileUtils.create_backup(self.master_file)
    
    def save_processing_summary(self, summary: ProcessingSummary, 
                              filename: str = "processing_summary.json") -> bool:
        """Save processing summary to file"""
        try:
            summary_data = {
                'total_urls': summary.total_urls,
                'successful_count': summary.successful_count,
                'failed_count': summary.failed_count,
                'skipped_count': summary.skipped_count,
                'duplicate_count': summary.duplicate_count,
                'started_at': summary.started_at,
                'completed_at': summary.completed_at,
                'processing_rate': summary.processing_rate,
                'success_rate': summary.success_rate,
                'failed_urls': summary.failed_urls,
                'errors': summary.errors,
                'worker_stats': [
                    {
                        'worker_id': ws.worker_id,
                        'completed_count': ws.completed_count,
                        'failed_count': ws.failed_count,
                        'skipped_count': ws.skipped_count,
                        'total_processed': ws.total_processed
                    }
                    for ws in summary.worker_stats
                ]
            }
            
            return FileUtils.safe_json_save(filename, summary_data, create_backup=False)
            
        except Exception as e:
            self.error_handler.handle_error(
                StorageException(f"Failed to save processing summary: {e}"),
                "Summary"
            )
            return False