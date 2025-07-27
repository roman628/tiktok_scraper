"""
Data loading and processing module for TikTok JSON database.

This module handles loading, parsing, and basic validation of the master2.json file
and provides efficient access to video data for keyword scoring analysis.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Iterator, Tuple
from dataclasses import dataclass, field
import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)


@dataclass
class VideoData:
    """Represents a single TikTok video with all relevant data."""
    video_id: str
    title: str
    description: str
    uploader: str
    view_count: int
    like_count: int
    comment_count: int
    repost_count: int
    duration: int
    upload_date: str
    hashtags: List[str] = field(default_factory=list)
    transcription: Optional[str] = None
    top_comments: List[Dict] = field(default_factory=list)
    url: str = ""
    
    @property
    def engagement_score(self) -> float:
        """Calculate engagement score based on metrics."""
        if self.view_count == 0:
            return 0.0
        
        # Weighted engagement calculation
        engagement = (
            (self.like_count * 1.0) +
            (self.comment_count * 2.0) +  # Comments weighted higher
            (self.repost_count * 1.5)
        ) / self.view_count
        
        return engagement
    
    @property
    def all_text(self) -> str:
        """Get all text content combined."""
        texts = []
        
        if self.title:
            texts.append(self.title)
        if self.description:
            texts.append(self.description)
        if self.transcription:
            texts.append(self.transcription)
        
        # Add comment text
        for comment in self.top_comments:
            if comment.get('comment_text'):
                texts.append(comment['comment_text'])
        
        return ' '.join(texts)
    
    @property
    def content_text(self) -> str:
        """Get content text (title + description + transcription)."""
        texts = []
        
        if self.title:
            texts.append(self.title)
        if self.description:
            texts.append(self.description)
        if self.transcription:
            texts.append(self.transcription)
        
        return ' '.join(texts)


class TikTokDataLoader:
    """
    Loads and processes TikTok data from JSON files.
    
    Provides efficient loading, filtering, and access to video data
    for keyword scoring analysis.
    """
    
    def __init__(self, json_path: Union[str, Path]):
        """
        Initialize the data loader.
        
        Args:
            json_path: Path to the master JSON file
        """
        self.json_path = Path(json_path)
        self.videos: List[VideoData] = []
        self.loaded = False
        
        if not self.json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {self.json_path}")
    
    def load_data(self, 
                  max_videos: Optional[int] = None,
                  min_engagement: float = 0.0,
                  require_transcription: bool = False,
                  require_comments: bool = False) -> None:
        """
        Load video data from JSON file with optional filtering.
        
        Args:
            max_videos: Maximum number of videos to load
            min_engagement: Minimum engagement score threshold
            require_transcription: Only load videos with transcription
            require_comments: Only load videos with comments
        """
        logger.info(f"Loading data from {self.json_path}")
        
        with open(self.json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        if not isinstance(raw_data, list):
            raise ValueError("JSON file should contain a list of video objects")
        
        logger.info(f"Found {len(raw_data)} videos in JSON file")
        
        # Process videos with progress bar
        loaded_count = 0
        for video_dict in tqdm(raw_data, desc="Loading videos"):
            try:
                video = self._parse_video(video_dict)
                
                # Apply filters
                if self._should_include_video(video, min_engagement, 
                                            require_transcription, require_comments):
                    self.videos.append(video)
                    loaded_count += 1
                    
                    if max_videos and loaded_count >= max_videos:
                        break
                        
            except Exception as e:
                logger.warning(f"Error parsing video {video_dict.get('video_id', 'unknown')}: {e}")
                continue
        
        self.loaded = True
        logger.info(f"Successfully loaded {len(self.videos)} videos")
    
    def _parse_video(self, video_dict: Dict) -> VideoData:
        """
        Parse a video dictionary into a VideoData object.
        
        Args:
            video_dict: Raw video data dictionary
            
        Returns:
            Parsed VideoData object
        """
        # Handle different possible field names and formats
        video_id = str(video_dict.get('video_id', ''))
        title = video_dict.get('title', '').strip()
        description = video_dict.get('description', '').strip()
        uploader = video_dict.get('uploader', '').strip()
        
        # Parse numeric fields with error handling
        view_count = self._safe_int(video_dict.get('view_count', 0))
        like_count = self._safe_int(video_dict.get('like_count', 0))
        comment_count = self._safe_int(video_dict.get('comment_count', 0))
        repost_count = self._safe_int(video_dict.get('repost_count', 0))
        duration = self._safe_int(video_dict.get('duration', 0))
        
        upload_date = video_dict.get('upload_date', '')
        hashtags = video_dict.get('hashtags', [])
        if isinstance(hashtags, str):
            hashtags = [hashtags]
        
        # Handle transcription field variations
        transcription = (
            video_dict.get('whisper_transcription') or
            video_dict.get('transcription') or
            video_dict.get('transcript') or
            ''
        ).strip()
        
        top_comments = video_dict.get('top_comments', [])
        if not isinstance(top_comments, list):
            top_comments = []
        
        url = video_dict.get('url', '')
        
        return VideoData(
            video_id=video_id,
            title=title,
            description=description,
            uploader=uploader,
            view_count=view_count,
            like_count=like_count,
            comment_count=comment_count,
            repost_count=repost_count,
            duration=duration,
            upload_date=upload_date,
            hashtags=hashtags,
            transcription=transcription,
            top_comments=top_comments,
            url=url
        )
    
    def _safe_int(self, value: Union[str, int, float]) -> int:
        """Safely convert value to integer."""
        try:
            if isinstance(value, str):
                # Remove commas and other formatting
                value = value.replace(',', '').replace(' ', '')
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def _should_include_video(self, 
                            video: VideoData,
                            min_engagement: float,
                            require_transcription: bool,
                            require_comments: bool) -> bool:
        """
        Check if a video should be included based on filters.
        
        Args:
            video: VideoData object to check
            min_engagement: Minimum engagement threshold
            require_transcription: Whether transcription is required
            require_comments: Whether comments are required
            
        Returns:
            True if video should be included
        """
        # Check engagement threshold
        if video.engagement_score < min_engagement:
            return False
        
        # Check transcription requirement
        if require_transcription and not video.transcription:
            return False
        
        # Check comments requirement
        if require_comments and not video.top_comments:
            return False
        
        # Must have some text content
        if not video.content_text.strip():
            return False
        
        return True
    
    def get_videos(self) -> List[VideoData]:
        """
        Get loaded videos.
        
        Returns:
            List of VideoData objects
        """
        if not self.loaded:
            raise RuntimeError("Data not loaded. Call load_data() first.")
        return self.videos
    
    def get_video_iterator(self, batch_size: int = 100) -> Iterator[List[VideoData]]:
        """
        Get videos in batches for memory-efficient processing.
        
        Args:
            batch_size: Number of videos per batch
            
        Yields:
            Batches of VideoData objects
        """
        if not self.loaded:
            raise RuntimeError("Data not loaded. Call load_data() first.")
        
        for i in range(0, len(self.videos), batch_size):
            yield self.videos[i:i + batch_size]
    
    def filter_videos(self,
                     min_views: int = 0,
                     min_likes: int = 0,
                     min_comments: int = 0,
                     uploaders: Optional[List[str]] = None,
                     date_range: Optional[Tuple[str, str]] = None) -> List[VideoData]:
        """
        Filter videos based on various criteria.
        
        Args:
            min_views: Minimum view count
            min_likes: Minimum like count
            min_comments: Minimum comment count
            uploaders: List of specific uploaders to include
            date_range: Tuple of (start_date, end_date) in YYYYMMDD format
            
        Returns:
            List of filtered VideoData objects
        """
        if not self.loaded:
            raise RuntimeError("Data not loaded. Call load_data() first.")
        
        filtered = []
        
        for video in self.videos:
            # Apply filters
            if video.view_count < min_views:
                continue
            if video.like_count < min_likes:
                continue
            if video.comment_count < min_comments:
                continue
            
            if uploaders and video.uploader not in uploaders:
                continue
            
            if date_range:
                start_date, end_date = date_range
                if not (start_date <= video.upload_date <= end_date):
                    continue
            
            filtered.append(video)
        
        return filtered
    
    def get_statistics(self) -> Dict[str, Union[int, float]]:
        """
        Get statistics about the loaded data.
        
        Returns:
            Dictionary with data statistics
        """
        if not self.loaded:
            raise RuntimeError("Data not loaded. Call load_data() first.")
        
        if not self.videos:
            return {}
        
        view_counts = [v.view_count for v in self.videos]
        like_counts = [v.like_count for v in self.videos]
        comment_counts = [v.comment_count for v in self.videos]
        engagement_scores = [v.engagement_score for v in self.videos]
        
        transcription_count = sum(1 for v in self.videos if v.transcription)
        comment_videos = sum(1 for v in self.videos if v.top_comments)
        
        return {
            'total_videos': len(self.videos),
            'videos_with_transcription': transcription_count,
            'videos_with_comments': comment_videos,
            'avg_views': sum(view_counts) / len(view_counts),
            'avg_likes': sum(like_counts) / len(like_counts),
            'avg_comments': sum(comment_counts) / len(comment_counts),
            'avg_engagement': sum(engagement_scores) / len(engagement_scores),
            'max_views': max(view_counts),
            'max_likes': max(like_counts),
            'max_comments': max(comment_counts),
            'max_engagement': max(engagement_scores)
        }
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert videos to pandas DataFrame.
        
        Returns:
            DataFrame with video data
        """
        if not self.loaded:
            raise RuntimeError("Data not loaded. Call load_data() first.")
        
        data = []
        for video in self.videos:
            data.append({
                'video_id': video.video_id,
                'title': video.title,
                'description': video.description,
                'uploader': video.uploader,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'comment_count': video.comment_count,
                'repost_count': video.repost_count,
                'duration': video.duration,
                'upload_date': video.upload_date,
                'hashtag_count': len(video.hashtags),
                'has_transcription': bool(video.transcription),
                'comment_count_actual': len(video.top_comments),
                'engagement_score': video.engagement_score,
                'content_length': len(video.content_text),
                'total_text_length': len(video.all_text)
            })
        
        return pd.DataFrame(data)


def load_tiktok_data(json_path: Union[str, Path], **kwargs) -> TikTokDataLoader:
    """
    Convenience function to load TikTok data.
    
    Args:
        json_path: Path to JSON file
        **kwargs: Additional arguments for load_data()
        
    Returns:
        Loaded TikTokDataLoader instance
    """
    loader = TikTokDataLoader(json_path)
    loader.load_data(**kwargs)
    return loader