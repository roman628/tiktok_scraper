"""URL processing and validation for TikTok videos."""

import re
import os
from typing import Optional, List, Set
from urllib.parse import urlparse
from datetime import datetime

class URLProcessor:
    """Handles all URL processing, validation, and extraction."""
    
    TIKTOK_PATTERNS = [
        r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)',
        r'https?://(?:vm|vt)\.tiktok\.com/[^\s]+',
        r'https?://(?:www\.)?tiktok\.com/t/[^\s]+'
    ]
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extract video ID from TikTok URL."""
        for pattern in cls.TIKTOK_PATTERNS:
            match = re.search(pattern, url)
            if match and len(match.groups()) > 0:
                return match.group(1)
        
        # Try to extract from URL path
        if '/video/' in url:
            parts = url.split('/video/')
            if len(parts) > 1:
                video_id = parts[1].split('?')[0].split('/')[0]
                if video_id.isdigit():
                    return video_id
        return None
    
    @classmethod
    def is_valid_tiktok_url(cls, url: str) -> bool:
        """Check if URL is a valid TikTok video URL."""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            return False
        
        return any(re.match(pattern, url) for pattern in cls.TIKTOK_PATTERNS)
    
    @classmethod
    def normalize_url(cls, url: str) -> str:
        """Normalize TikTok URL to standard format."""
        url = url.strip()
        video_id = cls.extract_video_id(url)
        if video_id:
            return f"https://www.tiktok.com/@user/video/{video_id}"
        return url
    
    @classmethod
    def load_urls_from_file(cls, file_path: str) -> List[str]:
        """Load and validate URLs from file."""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith('#') and cls.is_valid_tiktok_url(url):
                        urls.append(url)
        except FileNotFoundError:
            print(f"URL file not found: {file_path}")
        except Exception as e:
            print(f"Error loading URLs: {e}")
        return urls
    
    @classmethod
    def deduplicate_urls(cls, urls: List[str], existing: Set[str] = None) -> List[str]:
        """Remove duplicate URLs."""
        existing = existing or set()
        seen = set(existing)
        unique = []
        
        for url in urls:
            normalized = cls.normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)
        
        return unique
    
    @classmethod
    def remove_url_from_file(cls, url: str, file_path: str) -> bool:
        """Remove a specific URL from the source file.
        
        Args:
            url: URL to remove
            file_path: Path to the file containing URLs
            
        Returns:
            True if URL was removed, False otherwise
        """
        if not os.path.exists(file_path):
            return False
        
        try:
            # Read all URLs
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Filter out the URL
            normalized_target = cls.normalize_url(url)
            filtered_lines = []
            removed = False
            
            for line in lines:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#'):
                    if cls.is_valid_tiktok_url(line_stripped):
                        if cls.normalize_url(line_stripped) == normalized_target:
                            removed = True
                            continue  # Skip this URL
                filtered_lines.append(line)
            
            # Write back if URL was found and removed
            if removed:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(filtered_lines)
                print(f"Removed deleted/private video from {file_path}: {url}")
                return True
                
        except Exception as e:
            print(f"Error removing URL from file: {e}")
        
        return False
    
    @classmethod
    def is_deleted_video_error(cls, error_message: str) -> bool:
        """Check if an error message indicates a deleted/private video.
        
        Args:
            error_message: Error message from yt-dlp or TikTok API
            
        Returns:
            True if the error indicates a deleted/private video
        """
        deleted_indicators = [
            "Your IP address is blocked from accessing this post",
            "This video is private",
            "This video has been deleted",
            "Video not available",
            "This content isn't available",
            "Sorry, this content is not available"
        ]
        
        error_lower = error_message.lower()
        return any(indicator.lower() in error_lower for indicator in deleted_indicators)