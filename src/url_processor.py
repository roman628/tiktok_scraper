"""URL processing and validation for TikTok videos."""

import re
from typing import Optional, List, Set
from urllib.parse import urlparse

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