"""Data models for TikTok data collection system."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class Comment:
    """Represents a TikTok comment."""
    text: str
    user: str
    likes: int
    replies: List['Comment'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'user': self.user,
            'likes': self.likes,
            'replies': [reply.to_dict() for reply in self.replies]
        }

@dataclass
class VideoData:
    """Complete TikTok video data structure."""
    url: str
    video_id: str
    transcript: str
    metadata: Dict[str, Any]
    comments: List[Comment] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'url': self.url,
            'video_id': self.video_id,
            'transcript': self.transcript,
            'metadata': self.metadata,
            'comments': [comment.to_dict() for comment in self.comments]
        }
    
    def is_complete(self) -> bool:
        """Check if all essential data is present."""
        return bool(
            self.url and 
            self.transcript and 
            self.metadata and 
            self.comments
        )

@dataclass
class ProcessingState:
    """Tracks processing state for resumable operations."""
    total_urls: int = 0
    processed_urls: int = 0
    failed_urls: List[str] = field(default_factory=list)
    existing_urls: set = field(default_factory=set)
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def progress_percentage(self) -> float:
        if self.total_urls == 0:
            return 0.0
        return (self.processed_urls / self.total_urls) * 100