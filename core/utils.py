#!/usr/bin/env python3
"""
Shared utilities for TikTok scraper
Consolidates common patterns from across the codebase
"""

import os
import json
import shutil
import platform
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

class FileUtils:
    """Unified file operations utilities"""
    
    @staticmethod
    def safe_json_load(file_path: str) -> Optional[Any]:
        """Load JSON with error recovery"""
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON decode error in {file_path}: {e}")
            return None
        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}")
            return None
    
    @staticmethod
    def safe_json_save(file_path: str, data: Any, create_backup: bool = True) -> bool:
        """Save JSON with atomic operations and optional backup"""
        try:
            # Create backup if requested and file exists
            if create_backup and os.path.exists(file_path):
                FileUtils.create_backup(file_path)
            
            # Atomic write using temp file
            temp_file = f"{file_path}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic replace
            FileUtils.atomic_replace(temp_file, file_path)
            return True
            
        except Exception as e:
            print(f"❌ Error saving JSON to {file_path}: {e}")
            # Clean up temp file
            if os.path.exists(f"{file_path}.tmp"):
                try:
                    os.remove(f"{file_path}.tmp")
                except:
                    pass
            return False
    
    @staticmethod
    def create_backup(file_path: str) -> Optional[str]:
        """Create timestamped backup of file in backups directory"""
        if not os.path.exists(file_path):
            return None
        
        # Ensure backups directory exists
        backup_dir = "backups"
        if not FileUtils.ensure_directory(backup_dir):
            print(f"⚠️  Failed to create backups directory: {backup_dir}")
            return None
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = os.path.basename(file_path)
        backup_path = os.path.join(backup_dir, f"{file_name}.backup_{timestamp}")
        
        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            print(f"⚠️  Failed to create backup: {e}")
            return None
    
    @staticmethod
    def atomic_replace(src: str, dst: str) -> bool:
        """Cross-platform atomic file replacement"""
        try:
            if platform.system() == "Windows":
                if os.path.exists(dst):
                    os.replace(src, dst)
                else:
                    os.rename(src, dst)
            else:
                os.rename(src, dst)
            return True
        except Exception as e:
            print(f"❌ Atomic replace failed: {e}")
            return False
    
    @staticmethod
    def ensure_directory(dir_path: str) -> bool:
        """Ensure directory exists, create if needed"""
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"❌ Failed to create directory {dir_path}: {e}")
            return False


class URLUtils:
    """URL parsing and validation utilities"""
    
    TIKTOK_URL_PATTERN = re.compile(
        r'https?://(?:www\.|vm\.)?tiktok\.com/(?:@[\w.-]+/video/(\d+)|.*?/(\d+))'
    )
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from TikTok URL"""
        match = URLUtils.TIKTOK_URL_PATTERN.search(url)
        if match:
            return match.group(1) or match.group(2)
        return None
    
    @staticmethod
    def is_valid_tiktok_url(url: str) -> bool:
        """Validate TikTok URL format"""
        return bool(URLUtils.extract_video_id(url))
    
    @staticmethod
    def extract_username(url: str) -> Optional[str]:
        """Extract username from TikTok URL"""
        match = re.search(r'@([\w.-]+)', url)
        return match.group(1) if match else None
    
    @staticmethod
    def clean_url(url: str) -> str:
        """Clean and normalize TikTok URL"""
        # Remove tracking parameters and normalize
        url = url.split('?')[0]  # Remove query params
        url = url.replace('vm.tiktok.com', 'www.tiktok.com')
        return url


class ValidationUtils:
    """Data validation utilities"""
    
    @staticmethod
    def has_transcription(entry: Dict[str, Any], min_length: int = 50) -> bool:
        """Check if entry has transcription with minimum length"""
        if not isinstance(entry, dict):
            return False
        
        # Check various transcription fields
        transcription_fields = [
            'transcription', 'subtitle', 'subtitles', 
            'whisper_transcription', 'automatic_captions'
        ]
        
        for field in transcription_fields:
            value = entry.get(field, '')
            if isinstance(value, str) and len(value.strip()) >= min_length:
                return True
        
        # Check for any field containing 'transcript'
        for key, value in entry.items():
            if 'transcript' in key.lower() and value:
                text = str(value).strip()
                if len(text) >= min_length:
                    return True
        
        return False
    
    @staticmethod
    def calculate_completeness_score(entry: Dict[str, Any]) -> int:
        """Calculate data completeness score for an entry"""
        score = 0
        
        # Basic metadata fields (1 point each)
        basic_fields = ['title', 'description', 'url', 'video_id', 'uploader', 'upload_date']
        for field in basic_fields:
            if field in entry and entry[field]:
                score += 1
        
        # Statistical fields (1 point each)
        stat_fields = ['view_count', 'like_count', 'comment_count', 'duration', 'width', 'height']
        for field in stat_fields:
            if field in entry and entry[field] is not None:
                score += 1
        
        # Comments (10 points if extracted, plus up to 10 for comment count)
        if entry.get('comments_extracted') is True:
            score += 10
            comments = entry.get('top_comments', [])
            score += min(len(comments), 10)
        
        # Transcription (5 points)
        if ValidationUtils.has_transcription(entry):
            score += 5
        
        # Download timestamp (2 points)
        if entry.get('downloaded_at'):
            score += 2
        
        return score


class FormatUtils:
    """Output formatting utilities"""
    
    @staticmethod
    def format_size(bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    @staticmethod
    def truncate_text(text: str, max_length: int) -> str:
        """Truncate text with ellipsis"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."


def extract_title_for_display(url: str) -> str:
    """Extract displayable title from URL"""
    username = URLUtils.extract_username(url)
    video_id = URLUtils.extract_video_id(url)
    
    if username and video_id:
        return f"@{username} - {video_id[:10]}..."
    elif video_id:
        return f"Video {video_id[:10]}..."
    else:
        return FormatUtils.truncate_text(url, 50)