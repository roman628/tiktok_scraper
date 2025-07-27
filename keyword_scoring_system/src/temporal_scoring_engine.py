"""
Time-Weighted Gradient Scoring System for TikTok Content Analysis.

This module implements a temporal weighting system that scores content based on 
when it appears in the video, with the first 5 seconds receiving the highest weight.
The system ensures the entire video remains engaging while prioritizing early content.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np
from pathlib import Path
import json

from .data_loader import VideoData, TikTokDataLoader
from .scoring_engine import KeywordScoringEngine, KeywordScore

logger = logging.getLogger(__name__)


@dataclass
class TemporalSegment:
    """Represents a temporal segment of video content with timing information."""
    start_time: float
    end_time: float
    content: str
    segment_id: int
    temporal_weight: float
    keywords: List[Dict] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Duration of the segment in seconds."""
        return self.end_time - self.start_time
    
    @property
    def midpoint(self) -> float:
        """Midpoint time of the segment."""
        return (self.start_time + self.end_time) / 2.0


@dataclass
class TemporalKeywordScore(KeywordScore):
    """Extended keyword score with temporal weighting information."""
    temporal_distribution: Dict[float, float] = field(default_factory=dict)
    early_presence_boost: float = 1.0
    temporal_consistency: float = 1.0
    peak_timing: float = 0.0  # Time when keyword has highest impact
    
    @property
    def temporal_weighted_score(self) -> float:
        """Final score incorporating temporal weighting."""
        return (
            self.final_score * 
            self.early_presence_boost * 
            self.temporal_consistency
        )


class TemporalWeightingFunction:
    """
    Defines temporal weighting functions for content scoring.
    
    The weighting function prioritizes the first 5 seconds while ensuring
    the entire video remains engaging without dead spots.
    """
    
    def __init__(self, 
                 peak_weight: float = 3.0,
                 decay_rate: float = 0.3,
                 minimum_weight: float = 0.4):
        """
        Initialize temporal weighting parameters.
        
        Args:
            peak_weight: Maximum weight for first 5 seconds (default: 3.0)
            decay_rate: Rate of weight decay after peak period (default: 0.3)
            minimum_weight: Minimum weight to ensure no dead spots (default: 0.4)
        """
        self.peak_weight = peak_weight
        self.decay_rate = decay_rate
        self.minimum_weight = minimum_weight
        self.peak_duration = 5.0  # First 5 seconds get peak weight
    
    def calculate_temporal_weight(self, time_position: float, video_duration: float) -> float:
        """
        Calculate temporal weight for a given time position.
        
        Mathematical Formula:
        W(t) = max(min_weight, peak_weight * exp(-decay_rate * max(0, t - peak_duration)))
        
        Where:
        - t: time position in seconds
        - peak_duration: 5 seconds (peak period)
        - Ensures smooth decay without dead spots
        
        Args:
            time_position: Time position in seconds (0 to video_duration)
            video_duration: Total video duration in seconds
            
        Returns:
            Temporal weight value (minimum_weight to peak_weight)
        """
        if time_position <= self.peak_duration:
            # First 5 seconds get peak weight
            return self.peak_weight
        
        # Exponential decay after peak period
        time_since_peak = time_position - self.peak_duration
        decay_factor = math.exp(-self.decay_rate * time_since_peak)
        
        # Apply decay but ensure minimum weight to avoid dead spots
        decayed_weight = self.peak_weight * decay_factor
        
        return max(self.minimum_weight, decayed_weight)
    
    def calculate_segment_weight(self, start_time: float, end_time: float, 
                                video_duration: float) -> float:
        """
        Calculate average weight for a content segment.
        
        Uses numerical integration for accurate segment weighting.
        
        Args:
            start_time: Segment start time in seconds
            end_time: Segment end time in seconds
            video_duration: Total video duration in seconds
            
        Returns:
            Average temporal weight for the segment
        """
        if start_time >= end_time:
            return self.minimum_weight
        
        # Use numerical integration with small step size for accuracy
        step_size = 0.1  # 100ms steps
        total_weight = 0.0
        num_steps = 0
        
        current_time = start_time
        while current_time < end_time:
            weight = self.calculate_temporal_weight(current_time, video_duration)
            total_weight += weight
            num_steps += 1
            current_time += step_size
        
        if num_steps == 0:
            return self.minimum_weight
        
        return total_weight / num_steps
    
    def get_early_presence_boost(self, keyword_first_appearance: float) -> float:
        """
        Calculate boost for keywords appearing early in the video.
        
        Args:
            keyword_first_appearance: Time of first keyword appearance
            
        Returns:
            Boost multiplier (1.0 to 2.0)
        """
        if keyword_first_appearance <= 2.0:
            return 2.0  # Maximum boost for first 2 seconds
        elif keyword_first_appearance <= 5.0:
            return 1.5  # High boost for first 5 seconds
        elif keyword_first_appearance <= 10.0:
            return 1.2  # Medium boost for first 10 seconds
        else:
            return 1.0  # No boost after 10 seconds


class TemporalContentSegmenter:
    """
    Segments video content into temporal chunks for analysis.
    
    Creates intelligent segments based on natural content boundaries
    while maintaining temporal precision.
    """
    
    def __init__(self, 
                 default_segment_duration: float = 2.0,
                 min_segment_duration: float = 0.5,
                 max_segment_duration: float = 5.0):
        """
        Initialize segmentation parameters.
        
        Args:
            default_segment_duration: Default segment length in seconds
            min_segment_duration: Minimum allowed segment length
            max_segment_duration: Maximum allowed segment length
        """
        self.default_segment_duration = default_segment_duration
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
    
    def segment_transcription(self, video_data: VideoData) -> List[TemporalSegment]:
        """
        Segment video transcription into temporal chunks.
        
        Uses intelligent segmentation based on:
        1. Natural speech boundaries (sentence breaks)
        2. Temporal duration constraints
        3. Content density optimization
        
        Args:
            video_data: Video data containing transcription and timing
            
        Returns:
            List of TemporalSegment objects
        """
        transcription = video_data.transcription or ""
        estimated_duration = self._estimate_video_duration(video_data)
        
        if not transcription or estimated_duration <= 0:
            return self._create_fallback_segments(video_data, estimated_duration)
        
        # Try to extract timing information from transcription
        timed_segments = self._extract_timed_segments(transcription, estimated_duration)
        
        if timed_segments:
            return timed_segments
        else:
            # Fallback to estimation-based segmentation
            return self._create_estimated_segments(transcription, estimated_duration)
    
    def _estimate_video_duration(self, video_data: VideoData) -> float:
        """
        Estimate video duration from available data.
        
        Args:
            video_data: Video data object
            
        Returns:
            Estimated duration in seconds
        """
        # Try to get duration from metadata
        if hasattr(video_data, 'duration') and video_data.duration:
            return float(video_data.duration)
        
        # Estimate from transcription length (average speech rate: 150 words/minute)
        transcription = video_data.transcription or ""
        if transcription:
            word_count = len(transcription.split())
            estimated_duration = (word_count / 150) * 60  # Convert to seconds
            
            # Apply reasonable bounds (TikTok videos: 15-180 seconds)
            return max(15.0, min(180.0, estimated_duration))
        
        # Default TikTok duration
        return 30.0
    
    def _extract_timed_segments(self, transcription: str, duration: float) -> List[TemporalSegment]:
        """
        Extract segments with timing information from transcription.
        
        Looks for timing markers in transcription (e.g., timestamps, SRT format)
        """
        segments = []
        
        # Check for SRT-style timestamps [00:00:00,000 --> 00:00:02,500]
        import re
        srt_pattern = r'\[(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\](.*?)(?=\[|$)'
        matches = re.findall(srt_pattern, transcription, re.DOTALL)
        
        if matches:
            for i, (start_str, end_str, content) in enumerate(matches):
                start_time = self._parse_timestamp(start_str)
                end_time = self._parse_timestamp(end_str)
                
                segment = TemporalSegment(
                    start_time=start_time,
                    end_time=end_time,
                    content=content.strip(),
                    segment_id=i,
                    temporal_weight=0.0  # Will be calculated later
                )
                segments.append(segment)
            
            return segments
        
        # Check for simple timestamp markers [0:00] content [0:05] more content
        simple_pattern = r'\[(\d+:\d{2})\](.*?)(?=\[|$)'
        matches = re.findall(simple_pattern, transcription, re.DOTALL)
        
        if matches:
            for i, (timestamp, content) in enumerate(matches):
                start_time = self._parse_simple_timestamp(timestamp)
                end_time = start_time + self.default_segment_duration
                
                # Adjust end time for last segment
                if i == len(matches) - 1:
                    end_time = duration
                elif i < len(matches) - 1:
                    next_timestamp = matches[i + 1][0]
                    end_time = min(end_time, self._parse_simple_timestamp(next_timestamp))
                
                segment = TemporalSegment(
                    start_time=start_time,
                    end_time=min(end_time, duration),
                    content=content.strip(),
                    segment_id=i,
                    temporal_weight=0.0
                )
                segments.append(segment)
            
            return segments
        
        return []
    
    def _create_estimated_segments(self, transcription: str, duration: float) -> List[TemporalSegment]:
        """
        Create segments based on estimated timing.
        
        Uses natural language boundaries and estimated speech rate.
        """
        segments = []
        
        # Split on sentence boundaries
        import re
        sentences = re.split(r'[.!?]+', transcription)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return self._create_fallback_segments({"content_text": transcription}, duration)
        
        # Estimate time per sentence based on word count
        total_words = sum(len(sentence.split()) for sentence in sentences)
        words_per_second = total_words / duration if duration > 0 else 2.5  # Average speech rate
        
        current_time = 0.0
        for i, sentence in enumerate(sentences):
            sentence_words = len(sentence.split())
            sentence_duration = sentence_words / words_per_second
            
            # Apply duration constraints
            sentence_duration = max(self.min_segment_duration, 
                                  min(self.max_segment_duration, sentence_duration))
            
            end_time = min(current_time + sentence_duration, duration)
            
            segment = TemporalSegment(
                start_time=current_time,
                end_time=end_time,
                content=sentence,
                segment_id=i,
                temporal_weight=0.0
            )
            segments.append(segment)
            
            current_time = end_time
            
            if current_time >= duration:
                break
        
        return segments
    
    def _create_fallback_segments(self, video_data: Union[VideoData, Dict], 
                                 duration: float) -> List[TemporalSegment]:
        """
        Create basic segments when no transcription timing is available.
        """
        if isinstance(video_data, dict):
            content = video_data.get("content_text", "")
        else:
            content = video_data.content_text
        
        segments = []
        num_segments = max(1, int(duration / self.default_segment_duration))
        segment_duration = duration / num_segments
        
        # Split content roughly evenly
        content_parts = self._split_content_evenly(content, num_segments)
        
        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, duration)
            
            segment = TemporalSegment(
                start_time=start_time,
                end_time=end_time,
                content=content_parts[i] if i < len(content_parts) else "",
                segment_id=i,
                temporal_weight=0.0
            )
            segments.append(segment)
        
        return segments
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse SRT-style timestamp to seconds."""
        # Format: HH:MM:SS,mmm
        time_part, ms_part = timestamp_str.split(',')
        h, m, s = map(int, time_part.split(':'))
        ms = int(ms_part)
        
        return h * 3600 + m * 60 + s + ms / 1000.0
    
    def _parse_simple_timestamp(self, timestamp_str: str) -> float:
        """Parse simple timestamp to seconds."""
        # Format: M:SS or MM:SS
        parts = timestamp_str.split(':')
        if len(parts) == 2:
            m, s = map(int, parts)
            return m * 60 + s
        return 0.0
    
    def _split_content_evenly(self, content: str, num_parts: int) -> List[str]:
        """Split content into roughly equal parts."""
        if not content:
            return [""] * num_parts
        
        words = content.split()
        words_per_part = len(words) // num_parts
        
        parts = []
        for i in range(num_parts):
            start_idx = i * words_per_part
            if i == num_parts - 1:  # Last part gets remaining words
                end_idx = len(words)
            else:
                end_idx = (i + 1) * words_per_part
            
            part_words = words[start_idx:end_idx]
            parts.append(' '.join(part_words))
        
        return parts


class TemporalScoringEngine(KeywordScoringEngine):
    """
    Enhanced scoring engine with temporal weighting capabilities.
    
    Extends the base KeywordScoringEngine to incorporate time-based
    weighting for viral content analysis.
    """
    
    def __init__(self, 
                 temporal_weight_params: Optional[Dict] = None,
                 **kwargs):
        """
        Initialize temporal scoring engine.
        
        Args:
            temporal_weight_params: Parameters for temporal weighting function
            **kwargs: Arguments passed to base KeywordScoringEngine
        """
        super().__init__(**kwargs)
        
        # Initialize temporal components
        weight_params = temporal_weight_params or {}
        self.temporal_weighting = TemporalWeightingFunction(**weight_params)
        self.content_segmenter = TemporalContentSegmenter()
        
        # Enhanced storage for temporal data
        self.temporal_keyword_data: Dict[str, Dict] = defaultdict(lambda: {
            'videos': [],
            'temporal_appearances': defaultdict(list),  # time -> score mappings
            'total_temporal_score': 0.0,
            'early_appearances': 0,
            'late_appearances': 0,
            'peak_timings': []
        })
    
    def _process_single_video(self, video: VideoData, min_keyword_score: float) -> None:
        """
        Process a single video with temporal analysis.
        
        Overrides base method to include temporal weighting.
        """
        # Get video duration estimate
        video_duration = self._estimate_video_duration(video)
        
        # Create temporal segments
        segments = self.content_segmenter.segment_transcription(video)
        
        # Process each segment with temporal weighting
        for segment in segments:
            self._process_temporal_segment(video, segment, video_duration, min_keyword_score)
        
        # Also process title and description (time 0)
        self._process_static_content(video, video_duration, min_keyword_score)
    
    def _process_temporal_segment(self, video: VideoData, segment: TemporalSegment, 
                                 video_duration: float, min_keyword_score: float) -> None:
        """
        Process a single temporal segment for keyword extraction and scoring.
        """
        if not segment.content or not segment.content.strip():
            return
        
        # Calculate temporal weight for this segment
        temporal_weight = self.temporal_weighting.calculate_segment_weight(
            segment.start_time, segment.end_time, video_duration
        )
        segment.temporal_weight = temporal_weight
        
        # Extract keywords from segment content
        from .keyword_extractor import extract_video_keywords
        
        # Create temporary video data for segment
        segment_video_data = VideoData(
            video_id=video.video_id,
            title="",
            description="",
            transcription=segment.content,
            view_count=video.view_count,
            like_count=video.like_count,
            comment_count=video.comment_count,
            repost_count=video.repost_count
        )
        
        keywords = extract_video_keywords(
            segment_video_data,
            methods=self.extraction_methods,
            top_k=30
        )
        
        # Filter and process keywords
        keywords = [k for k in keywords if k['score'] >= min_keyword_score]
        segment.keywords = keywords
        
        if not keywords:
            return
        
        # Calculate performance metrics
        performance_score = self._calculate_performance_score(video)
        
        # Process each keyword with temporal information
        for keyword_data in keywords:
            keyword = keyword_data['keyword']
            base_score = keyword_data['score']
            
            # Apply temporal weighting
            temporal_score = base_score * temporal_weight
            
            # Store in both regular and temporal data structures
            self._store_temporal_keyword_data(
                keyword, video, segment, temporal_score, performance_score
            )
            
            # Also store in base data structure for compatibility
            self._store_base_keyword_data(keyword, video, keyword_data, performance_score)
    
    def _process_static_content(self, video: VideoData, video_duration: float, 
                               min_keyword_score: float) -> None:
        """
        Process title and description as time-0 content.
        """
        static_content = f"{video.title} {video.description}".strip()
        if not static_content:
            return
        
        # Create segment for static content (time 0)
        static_segment = TemporalSegment(
            start_time=0.0,
            end_time=0.1,  # Very brief duration
            content=static_content,
            segment_id=-1,  # Special ID for static content
            temporal_weight=self.temporal_weighting.peak_weight  # Maximum weight
        )
        
        self._process_temporal_segment(video, static_segment, video_duration, min_keyword_score)
    
    def _store_temporal_keyword_data(self, keyword: str, video: VideoData, 
                                    segment: TemporalSegment, temporal_score: float,
                                    performance_score: float) -> None:
        """
        Store keyword data with temporal information.
        """
        # Determine if this is an early appearance
        is_early = segment.midpoint <= 5.0
        
        # Store temporal appearance
        self.temporal_keyword_data[keyword]['temporal_appearances'][segment.midpoint].append({
            'score': temporal_score,
            'segment_id': segment.segment_id,
            'video_id': video.video_id,
            'temporal_weight': segment.temporal_weight
        })
        
        # Update counters
        if is_early:
            self.temporal_keyword_data[keyword]['early_appearances'] += 1
        else:
            self.temporal_keyword_data[keyword]['late_appearances'] += 1
        
        # Store peak timing
        self.temporal_keyword_data[keyword]['peak_timings'].append(segment.midpoint)
        
        # Add to total temporal score
        self.temporal_keyword_data[keyword]['total_temporal_score'] += temporal_score
        
        # Store video reference with temporal info
        self.temporal_keyword_data[keyword]['videos'].append({
            'video_id': video.video_id,
            'temporal_score': temporal_score,
            'segment_timing': segment.midpoint,
            'temporal_weight': segment.temporal_weight,
            'performance_score': performance_score,
            'is_early_appearance': is_early
        })
    
    def _store_base_keyword_data(self, keyword: str, video: VideoData, 
                                keyword_data: Dict, performance_score: float) -> None:
        """
        Store data in base format for compatibility.
        """
        # Store in base data structure
        self.keyword_data[keyword]['videos'].append({
            'video_id': video.video_id,
            'keyword_score': keyword_data['score'],
            'performance_score': performance_score,
            'engagement_score': video.engagement_score,
            'view_count': video.view_count,
            'like_count': video.like_count,
            'comment_count': video.comment_count,
            'repost_count': video.repost_count
        })
        
        # Accumulate base metrics
        self.keyword_data[keyword]['total_engagement'] += video.engagement_score
        self.keyword_data[keyword]['total_views'] += video.view_count
        self.keyword_data[keyword]['total_likes'] += video.like_count
        self.keyword_data[keyword]['total_comments'] += video.comment_count
        self.keyword_data[keyword]['total_reposts'] += video.repost_count
    
    def calculate_temporal_keyword_scores(self, min_video_count: int = 2) -> List[TemporalKeywordScore]:
        """
        Calculate temporal keyword scores.
        
        Args:
            min_video_count: Minimum number of videos a keyword must appear in
            
        Returns:
            List of TemporalKeywordScore objects sorted by temporal weighted score
        """
        logger.info(f"Calculating temporal scores for {len(self.temporal_keyword_data)} keywords")
        
        temporal_scores = []
        
        for keyword, temporal_data in self.temporal_keyword_data.items():
            video_count = len(temporal_data['videos'])
            
            if video_count < min_video_count:
                continue
            
            # Get base keyword score data
            base_data = self.keyword_data.get(keyword, {})
            if not base_data.get('videos'):
                continue
            
            # Calculate base metrics (reuse from parent class logic)
            base_score_obj = self._create_base_keyword_score(keyword, base_data)
            
            if base_score_obj is None:
                continue
            
            # Calculate temporal-specific metrics
            temporal_metrics = self._calculate_temporal_metrics(keyword, temporal_data)
            
            # Create temporal keyword score
            temporal_score = TemporalKeywordScore(
                # Base fields from KeywordScore
                keyword=base_score_obj.keyword,
                total_score=base_score_obj.total_score,
                frequency=base_score_obj.frequency,
                video_count=base_score_obj.video_count,
                avg_engagement=base_score_obj.avg_engagement,
                avg_views=base_score_obj.avg_views,
                avg_likes=base_score_obj.avg_likes,
                avg_comments=base_score_obj.avg_comments,
                sentiment_score=base_score_obj.sentiment_score,
                performance_correlation=base_score_obj.performance_correlation,
                top_videos=base_score_obj.top_videos,
                context_categories=base_score_obj.context_categories,
                
                # Temporal-specific fields
                temporal_distribution=temporal_metrics['temporal_distribution'],
                early_presence_boost=temporal_metrics['early_presence_boost'],
                temporal_consistency=temporal_metrics['temporal_consistency'],
                peak_timing=temporal_metrics['peak_timing']
            )
            
            temporal_scores.append(temporal_score)
        
        # Sort by temporal weighted score
        temporal_scores.sort(key=lambda x: x.temporal_weighted_score, reverse=True)
        
        logger.info(f"Generated temporal scores for {len(temporal_scores)} keywords")
        return temporal_scores
    
    def _create_base_keyword_score(self, keyword: str, base_data: Dict) -> Optional[KeywordScore]:
        """
        Create base KeywordScore object from base data.
        """
        try:
            video_count = len(base_data['videos'])
            
            # Calculate averages
            avg_engagement = base_data['total_engagement'] / video_count
            avg_views = base_data['total_views'] / video_count
            avg_likes = base_data['total_likes'] / video_count
            avg_comments = base_data['total_comments'] / video_count
            
            # Calculate performance correlation
            video_performances = [v['performance_score'] for v in base_data['videos']]
            performance_correlation = np.mean(video_performances) if video_performances else 0.0
            
            # Calculate total score
            total_score = performance_correlation * video_count
            
            # Get top videos
            top_videos = sorted(
                base_data['videos'],
                key=lambda x: x['performance_score'],
                reverse=True
            )[:5]
            top_video_ids = [v['video_id'] for v in top_videos]
            
            return KeywordScore(
                keyword=keyword,
                total_score=total_score,
                frequency=video_count,
                video_count=video_count,
                avg_engagement=avg_engagement,
                avg_views=avg_views,
                avg_likes=avg_likes,
                avg_comments=avg_comments,
                sentiment_score=0.0,  # Will be filled by sentiment analyzer if available
                performance_correlation=performance_correlation,
                top_videos=top_video_ids,
                context_categories=set()
            )
            
        except Exception as e:
            logger.warning(f"Error creating base score for keyword '{keyword}': {e}")
            return None
    
    def _calculate_temporal_metrics(self, keyword: str, temporal_data: Dict) -> Dict:
        """
        Calculate temporal-specific metrics for a keyword.
        """
        # Temporal distribution
        temporal_distribution = {}
        for time_point, appearances in temporal_data['temporal_appearances'].items():
            avg_score = np.mean([app['score'] for app in appearances])
            temporal_distribution[time_point] = avg_score
        
        # Early presence boost
        early_count = temporal_data['early_appearances']
        total_count = early_count + temporal_data['late_appearances']
        early_ratio = early_count / max(total_count, 1)
        
        # Calculate first appearance time
        peak_timings = temporal_data['peak_timings']
        first_appearance = min(peak_timings) if peak_timings else float('inf')
        
        early_presence_boost = self.temporal_weighting.get_early_presence_boost(first_appearance)
        
        # Additional boost for high early presence
        if early_ratio > 0.7:
            early_presence_boost *= 1.2
        elif early_ratio > 0.5:
            early_presence_boost *= 1.1
        
        # Temporal consistency (how consistently the keyword appears across time)
        if len(temporal_distribution) > 1:
            time_points = sorted(temporal_distribution.keys())
            time_gaps = []
            for i in range(1, len(time_points)):
                gap = time_points[i] - time_points[i-1]
                time_gaps.append(gap)
            
            # Lower variance in gaps = higher consistency
            gap_variance = np.var(time_gaps) if time_gaps else 0
            temporal_consistency = 1.0 / (1.0 + gap_variance * 0.1)
        else:
            temporal_consistency = 1.0
        
        # Peak timing (when keyword has maximum impact)
        if temporal_distribution:
            peak_timing = max(temporal_distribution.items(), key=lambda x: x[1])[0]
        else:
            peak_timing = 0.0
        
        return {
            'temporal_distribution': temporal_distribution,
            'early_presence_boost': early_presence_boost,
            'temporal_consistency': temporal_consistency,
            'peak_timing': peak_timing
        }
    
    def _estimate_video_duration(self, video: VideoData) -> float:
        """
        Estimate video duration from available data.
        """
        return self.content_segmenter._estimate_video_duration(video)
    
    def save_temporal_results(self, temporal_scores: List[TemporalKeywordScore], 
                             output_path: Union[str, Path],
                             format: str = 'json') -> None:
        """
        Save temporal keyword scoring results.
        
        Args:
            temporal_scores: List of TemporalKeywordScore objects
            output_path: Path to save results
            format: Output format ('json', 'csv', 'both')
        """
        output_path = Path(output_path)
        
        # Prepare data for export
        results_data = []
        for score in temporal_scores:
            results_data.append({
                'keyword': score.keyword,
                'total_score': score.total_score,
                'final_score': score.final_score,
                'temporal_weighted_score': score.temporal_weighted_score,
                'frequency': score.frequency,
                'video_count': score.video_count,
                'avg_engagement': score.avg_engagement,
                'avg_views': score.avg_views,
                'avg_likes': score.avg_likes,
                'avg_comments': score.avg_comments,
                'sentiment_score': score.sentiment_score,
                'performance_correlation': score.performance_correlation,
                'early_presence_boost': score.early_presence_boost,
                'temporal_consistency': score.temporal_consistency,
                'peak_timing': score.peak_timing,
                'temporal_distribution': score.temporal_distribution,
                'top_videos': score.top_videos,
                'context_categories': list(score.context_categories)
            })
        
        if format in ['json', 'both']:
            json_path = output_path.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'total_keywords': len(temporal_scores),
                        'processed_videos': self.processed_videos,
                        'extraction_methods': self.extraction_methods,
                        'performance_weights': self.performance_weights,
                        'temporal_weighting_params': {
                            'peak_weight': self.temporal_weighting.peak_weight,
                            'decay_rate': self.temporal_weighting.decay_rate,
                            'minimum_weight': self.temporal_weighting.minimum_weight,
                            'peak_duration': self.temporal_weighting.peak_duration
                        }
                    },
                    'keywords': results_data
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved temporal JSON results to {json_path}")
        
        if format in ['csv', 'both']:
            import pandas as pd
            csv_path = output_path.with_suffix('.csv')
            df = pd.DataFrame(results_data)
            
            # Flatten complex fields for CSV
            df['temporal_distribution'] = df['temporal_distribution'].apply(lambda x: str(x))
            df['top_videos'] = df['top_videos'].apply(lambda x: ';'.join(x))
            df['context_categories'] = df['context_categories'].apply(lambda x: ';'.join(x))
            
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved temporal CSV results to {csv_path}")


def score_keywords_with_temporal_weighting(json_path: Union[str, Path],
                                          output_path: Union[str, Path],
                                          max_videos: Optional[int] = None,
                                          temporal_params: Optional[Dict] = None,
                                          **kwargs) -> List[TemporalKeywordScore]:
    """
    Convenience function to score keywords with temporal weighting.
    
    Args:
        json_path: Path to TikTok JSON data
        output_path: Path to save results
        max_videos: Maximum videos to process
        temporal_params: Parameters for temporal weighting
        **kwargs: Additional arguments for scoring engine
        
    Returns:
        List of TemporalKeywordScore objects
    """
    # Load data
    data_loader = TikTokDataLoader(json_path)
    data_loader.load_data(max_videos=max_videos)
    
    # Initialize temporal scoring engine
    temporal_engine = TemporalScoringEngine(
        temporal_weight_params=temporal_params,
        **kwargs
    )
    
    # Process videos
    videos = data_loader.get_videos()
    temporal_engine.total_videos = len(videos)
    
    logger.info(f"Processing {len(videos)} videos with temporal weighting")
    
    # Process in batches
    for batch in data_loader.get_video_iterator(batch_size=100):
        temporal_engine.process_video_batch(batch)
    
    # Calculate temporal scores
    temporal_scores = temporal_engine.calculate_temporal_keyword_scores()
    
    # Save results
    temporal_engine.save_temporal_results(temporal_scores, output_path, format='both')
    
    return temporal_scores