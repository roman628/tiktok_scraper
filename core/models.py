#!/usr/bin/env python3
"""
Core data models for TikTok scraper
Standardizes data structures across the codebase
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ProcessingStatus(Enum):
    """Status of video processing"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    EXTRACTING_COMMENTS = "extracting_comments"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CommentData:
    """Standardized comment data structure"""
    comment_id: str
    username: str
    display_name: str
    text: str
    like_count: int = 0
    timestamp: int = 0
    replies: List['CommentData'] = field(default_factory=list)
    reply_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            'comment_id': self.comment_id,
            'username': self.username,
            'display_name': self.display_name,
            'comment_text': self.text,
            'like_count': self.like_count,
            'timestamp': self.timestamp
        }
        
        if self.replies:
            data['replies'] = [reply.to_dict() for reply in self.replies]
            data['reply_count'] = len(self.replies)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommentData':
        """Create from dictionary"""
        replies = []
        if 'replies' in data:
            replies = [cls.from_dict(reply) for reply in data['replies']]
        
        return cls(
            comment_id=data.get('comment_id', ''),
            username=data.get('username', ''),
            display_name=data.get('display_name', ''),
            text=data.get('comment_text', ''),
            like_count=data.get('like_count', 0),
            timestamp=data.get('timestamp', 0),
            replies=replies,
            reply_count=data.get('reply_count', len(replies))
        )


@dataclass
class VideoMetadata:
    """Standardized video metadata structure"""
    url: str
    video_id: str
    title: str = ""
    description: str = ""
    uploader: str = ""
    upload_date: str = ""
    
    # Media properties
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    filesize: Optional[int] = None
    
    # Statistics
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    
    # Transcription data
    transcription: str = ""
    whisper_transcription: str = ""
    automatic_captions: str = ""
    subtitle: str = ""
    
    # Comments
    comments_extracted: bool = False
    comments_extracted_at: Optional[str] = None
    top_comments: List[CommentData] = field(default_factory=list)
    
    # Processing metadata
    downloaded_at: Optional[str] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    download_path: Optional[str] = None
    error_message: Optional[str] = None
    
    # Quality metadata
    quality: str = "best"
    format_id: Optional[str] = None
    audio_only: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            'url': self.url,
            'video_id': self.video_id,
            'title': self.title,
            'description': self.description,
            'uploader': self.uploader,
            'upload_date': self.upload_date,
            'duration': self.duration,
            'width': self.width,
            'height': self.height,
            'filesize': self.filesize,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'share_count': self.share_count,
            'transcription': self.transcription,
            'whisper_transcription': self.whisper_transcription,
            'automatic_captions': self.automatic_captions,
            'subtitle': self.subtitle,
            'comments_extracted': self.comments_extracted,
            'comments_extracted_at': self.comments_extracted_at,
            'top_comments': [comment.to_dict() for comment in self.top_comments],
            'downloaded_at': self.downloaded_at,
            'processing_status': self.processing_status.value,
            'download_path': self.download_path,
            'error_message': self.error_message,
            'quality': self.quality,
            'format_id': self.format_id,
            'audio_only': self.audio_only
        }
        
        # Remove None values for cleaner output
        return {k: v for k, v in data.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoMetadata':
        """Create from dictionary"""
        # Parse comments
        comments = []
        if 'top_comments' in data:
            comments = [CommentData.from_dict(comment) for comment in data['top_comments']]
        
        # Parse processing status
        status = ProcessingStatus.PENDING
        if 'processing_status' in data:
            try:
                status = ProcessingStatus(data['processing_status'])
            except ValueError:
                status = ProcessingStatus.PENDING
        
        return cls(
            url=data.get('url', ''),
            video_id=data.get('video_id', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            uploader=data.get('uploader', ''),
            upload_date=data.get('upload_date', ''),
            duration=data.get('duration'),
            width=data.get('width'),
            height=data.get('height'),
            filesize=data.get('filesize'),
            view_count=data.get('view_count'),
            like_count=data.get('like_count'),
            comment_count=data.get('comment_count'),
            share_count=data.get('share_count'),
            transcription=data.get('transcription', ''),
            whisper_transcription=data.get('whisper_transcription', ''),
            automatic_captions=data.get('automatic_captions', ''),
            subtitle=data.get('subtitle', ''),
            comments_extracted=data.get('comments_extracted', False),
            comments_extracted_at=data.get('comments_extracted_at'),
            top_comments=comments,
            downloaded_at=data.get('downloaded_at'),
            processing_status=status,
            download_path=data.get('download_path'),
            error_message=data.get('error_message'),
            quality=data.get('quality', 'best'),
            format_id=data.get('format_id'),
            audio_only=data.get('audio_only', False)
        )
    
    def has_valid_transcription(self, min_length: int = 50) -> bool:
        """Check if video has valid transcription"""
        transcription_fields = [
            self.transcription, self.whisper_transcription,
            self.automatic_captions, self.subtitle
        ]
        
        for text in transcription_fields:
            if text and len(text.strip()) >= min_length:
                return True
        
        return False
    
    def calculate_completeness_score(self) -> int:
        """Calculate data completeness score"""
        score = 0
        
        # Basic metadata (1 point each)
        basic_fields = [self.title, self.description, self.uploader, self.upload_date]
        score += sum(1 for field in basic_fields if field)
        
        # Statistics (1 point each) 
        stat_fields = [self.view_count, self.like_count, self.comment_count, 
                      self.duration, self.width, self.height]
        score += sum(1 for field in stat_fields if field is not None)
        
        # Comments (10 points if extracted, plus up to 10 for comment count)
        if self.comments_extracted:
            score += 10
            score += min(len(self.top_comments), 10)
        
        # Transcription (5 points)
        if self.has_valid_transcription():
            score += 5
        
        # Download completion (2 points)
        if self.downloaded_at:
            score += 2
        
        return score
    
    def update_status(self, status: ProcessingStatus, error_message: str = None):
        """Update processing status"""
        self.processing_status = status
        if error_message:
            self.error_message = error_message
        
        if status == ProcessingStatus.COMPLETED:
            self.downloaded_at = datetime.now().isoformat()


@dataclass
class ProcessingJob:
    """Represents a video processing job"""
    url: str
    video_id: str
    priority: int = 0
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_attempt_at: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    worker_id: Optional[int] = None
    
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.attempts < self.max_attempts and self.status == ProcessingStatus.FAILED
    
    def mark_attempt(self, worker_id: int = None):
        """Mark processing attempt"""
        self.attempts += 1
        self.last_attempt_at = datetime.now().isoformat()
        self.worker_id = worker_id
    
    def mark_completed(self):
        """Mark job as completed"""
        self.status = ProcessingStatus.COMPLETED
    
    def mark_failed(self, error_message: str):
        """Mark job as failed"""
        self.status = ProcessingStatus.FAILED
        self.error_message = error_message


@dataclass
class WorkerStats:
    """Statistics for a worker process"""
    worker_id: int
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    current_job: Optional[ProcessingJob] = None
    status: str = "idle"
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def update_activity(self, status: str, job: ProcessingJob = None):
        """Update worker activity"""
        self.status = status
        self.current_job = job
        self.last_activity = datetime.now().isoformat()
    
    def increment_completed(self):
        """Increment completed count"""
        self.completed_count += 1
        self.update_activity("completed")
    
    def increment_failed(self):
        """Increment failed count"""
        self.failed_count += 1
        self.update_activity("failed")
    
    def increment_skipped(self):
        """Increment skipped count"""
        self.skipped_count += 1
        self.update_activity("skipped")
    
    @property
    def total_processed(self) -> int:
        """Total videos processed by this worker"""
        return self.completed_count + self.failed_count + self.skipped_count


@dataclass
class ProcessingSummary:
    """Summary of processing results"""
    total_urls: int = 0
    successful_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    duplicate_count: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    worker_stats: List[WorkerStats] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def processing_rate(self) -> float:
        """Calculate processing rate in videos per minute"""
        if not self.completed_at:
            return 0.0
        
        start_time = datetime.fromisoformat(self.started_at)
        end_time = datetime.fromisoformat(self.completed_at)
        duration_minutes = (end_time - start_time).total_seconds() / 60
        
        if duration_minutes == 0:
            return 0.0
        
        return self.successful_count / duration_minutes
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        total_attempted = self.successful_count + self.failed_count
        if total_attempted == 0:
            return 0.0
        
        return (self.successful_count / total_attempted) * 100
    
    def finalize(self):
        """Mark processing as completed"""
        self.completed_at = datetime.now().isoformat()
    
    def add_error(self, error_message: str):
        """Add error to summary"""
        self.errors.append(error_message)
    
    def add_failed_url(self, url: str):
        """Add failed URL to summary"""
        if url not in self.failed_urls:
            self.failed_urls.append(url)