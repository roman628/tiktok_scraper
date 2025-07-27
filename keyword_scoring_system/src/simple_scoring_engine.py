"""
Simplified keyword scoring engine without external NLP dependencies.

This module implements the core scoring algorithm using only built-in Python libraries
for cases where the full NLP stack is not available.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import json
from pathlib import Path

from .data_loader import VideoData, TikTokDataLoader

logger = logging.getLogger(__name__)


@dataclass
class SimpleKeywordScore:
    """Simplified keyword score representation."""
    keyword: str
    total_score: float
    frequency: int
    video_count: int
    avg_engagement: float
    avg_views: float
    avg_likes: float
    avg_comments: float
    performance_correlation: float
    top_videos: List[str] = field(default_factory=list)
    
    @property
    def score_per_video(self) -> float:
        """Average score per video appearance."""
        return self.total_score / self.video_count if self.video_count > 0 else 0.0
    
    @property
    def rarity_bonus(self) -> float:
        """Bonus for rare but high-performing keywords."""
        if self.video_count == 0:
            return 0.0
        base_rarity = 1.0 / self.video_count
        return math.log(1 + base_rarity * 100)
    
    @property
    def final_score(self) -> float:
        """Final score with rarity bonus."""
        return self.total_score * (1 + self.rarity_bonus * 0.1)


class SimpleKeywordExtractor:
    """Simple keyword extractor using only frequency analysis."""
    
    def __init__(self, min_word_length: int = 3):
        self.min_word_length = min_word_length
        
        # Basic stopwords (no external dependencies)
        self.stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'is', 'am', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'myself',
            'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
            'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
            'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
            'like', 'just', 'get', 'got', 'go', 'going', 'went', 'come', 'came',
            'see', 'saw', 'look', 'looking', 'make', 'made', 'take', 'took',
            'know', 'think', 'want', 'say', 'said', 'tell', 'told', 'ask', 'asked',
            'give', 'gave', 'put', 'let', 'good', 'bad', 'big', 'small', 'new', 'old',
            # TikTok common words
            'video', 'tiktok', 'watch', 'follow', 'like', 'comment', 'share', 'fyp'
        }
    
    def extract_keywords(self, text: str, top_k: int = 20) -> List[Dict]:
        """Extract keywords using simple frequency analysis."""
        if not text or not text.strip():
            return []
        
        # Simple preprocessing
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation
        words = text.split()
        
        # Filter words
        filtered_words = [
            word for word in words 
            if (len(word) >= self.min_word_length and 
                word not in self.stopwords and 
                not word.isdigit())
        ]
        
        # Count frequencies
        word_counts = Counter(filtered_words)
        
        # Create keyword list
        keywords = []
        for i, (word, count) in enumerate(word_counts.most_common(top_k)):
            keywords.append({
                'keyword': word,
                'score': count,
                'method': 'frequency',
                'position': i + 1,
                'frequency': count,
                'length': 1
            })
        
        return keywords


class SimpleScoringEngine:
    """Simplified scoring engine without external dependencies."""
    
    def __init__(self, performance_weights: Optional[Dict[str, float]] = None):
        """Initialize the simplified scoring engine."""
        
        # Default weights for performance metrics
        self.performance_weights = performance_weights or {
            'engagement_score': 3.0,
            'view_count': 1.0,
            'like_count': 2.0,
            'comment_count': 2.5,
            'repost_count': 1.5
        }
        
        # Initialize keyword extractor
        self.keyword_extractor = SimpleKeywordExtractor()
        
        # Storage for analysis results
        self.keyword_data: Dict[str, Dict] = defaultdict(lambda: {
            'videos': [],
            'total_engagement': 0.0,
            'total_views': 0,
            'total_likes': 0,
            'total_comments': 0,
            'total_reposts': 0
        })
        
        self.processed_videos = 0
    
    def process_video_batch(self, videos: List[VideoData], 
                           min_keyword_score: float = 1.0) -> None:
        """Process a batch of videos for keyword scoring."""
        logger.info(f"Processing batch of {len(videos)} videos")
        
        for video in videos:
            try:
                self._process_single_video(video, min_keyword_score)
                self.processed_videos += 1
                
                if self.processed_videos % 100 == 0:
                    logger.info(f"Processed {self.processed_videos} videos")
                    
            except Exception as e:
                logger.warning(f"Error processing video {video.video_id}: {e}")
                continue
    
    def _process_single_video(self, video: VideoData, min_keyword_score: float) -> None:
        """Process a single video for keyword scoring."""
        
        # Extract keywords from video content
        keywords = self.keyword_extractor.extract_keywords(video.content_text, top_k=30)
        
        # Filter keywords by minimum score
        keywords = [k for k in keywords if k['score'] >= min_keyword_score]
        
        if not keywords:
            return
        
        # Calculate video performance metrics
        performance_score = self._calculate_performance_score(video)
        
        # Update keyword data
        for keyword_data in keywords:
            keyword = keyword_data['keyword']
            
            # Store video reference
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
            
            # Accumulate metrics
            self.keyword_data[keyword]['total_engagement'] += video.engagement_score
            self.keyword_data[keyword]['total_views'] += video.view_count
            self.keyword_data[keyword]['total_likes'] += video.like_count
            self.keyword_data[keyword]['total_comments'] += video.comment_count
            self.keyword_data[keyword]['total_reposts'] += video.repost_count
    
    def _calculate_performance_score(self, video: VideoData) -> float:
        """Calculate weighted performance score for a video."""
        
        # Normalize metrics to 0-1 scale (using log transformation for large numbers)
        normalized_engagement = min(1.0, video.engagement_score / 0.1)  # Cap at 10% engagement
        normalized_views = min(1.0, math.log(video.view_count + 1) / math.log(10000000))  # Cap at 10M views
        normalized_likes = min(1.0, math.log(video.like_count + 1) / math.log(1000000))  # Cap at 1M likes
        normalized_comments = min(1.0, math.log(video.comment_count + 1) / math.log(100000))  # Cap at 100K comments
        normalized_reposts = min(1.0, math.log(video.repost_count + 1) / math.log(100000))  # Cap at 100K reposts
        
        # Calculate weighted score
        performance_score = (
            normalized_engagement * self.performance_weights['engagement_score'] +
            normalized_views * self.performance_weights['view_count'] +
            normalized_likes * self.performance_weights['like_count'] +
            normalized_comments * self.performance_weights['comment_count'] +
            normalized_reposts * self.performance_weights['repost_count']
        )
        
        # Normalize by total weights
        total_weights = sum(self.performance_weights.values())
        return performance_score / total_weights
    
    def calculate_keyword_scores(self, min_video_count: int = 2) -> List[SimpleKeywordScore]:
        """Calculate final keyword scores."""
        logger.info(f"Calculating scores for {len(self.keyword_data)} keywords")
        
        keyword_scores = []
        
        for keyword, data in self.keyword_data.items():
            video_count = len(data['videos'])
            
            if video_count < min_video_count:
                continue
            
            # Calculate averages
            avg_engagement = data['total_engagement'] / video_count
            avg_views = data['total_views'] / video_count
            avg_likes = data['total_likes'] / video_count
            avg_comments = data['total_comments'] / video_count
            
            # Calculate performance correlation
            video_performances = [v['performance_score'] for v in data['videos']]
            performance_correlation = sum(video_performances) / len(video_performances)
            
            # Calculate total score (weighted by video count and performance)
            total_score = performance_correlation * video_count
            
            # Get top performing videos
            top_videos = sorted(
                data['videos'], 
                key=lambda x: x['performance_score'], 
                reverse=True
            )[:5]
            top_video_ids = [v['video_id'] for v in top_videos]
            
            keyword_score = SimpleKeywordScore(
                keyword=keyword,
                total_score=total_score,
                frequency=video_count,
                video_count=video_count,
                avg_engagement=avg_engagement,
                avg_views=avg_views,
                avg_likes=avg_likes,
                avg_comments=avg_comments,
                performance_correlation=performance_correlation,
                top_videos=top_video_ids
            )
            
            keyword_scores.append(keyword_score)
        
        # Sort by final score
        keyword_scores.sort(key=lambda x: x.final_score, reverse=True)
        
        logger.info(f"Generated scores for {len(keyword_scores)} keywords")
        return keyword_scores
    
    def process_dataset(self, 
                       data_loader: TikTokDataLoader,
                       batch_size: int = 100,
                       min_keyword_score: float = 1.0) -> List[SimpleKeywordScore]:
        """Process entire dataset and calculate keyword scores."""
        
        videos = data_loader.get_videos()
        total_videos = len(videos)
        
        logger.info(f"Processing {total_videos} videos in batches of {batch_size}")
        
        # Process in batches
        for i in range(0, len(videos), batch_size):
            batch = videos[i:i + batch_size]
            self.process_video_batch(batch, min_keyword_score)
        
        # Calculate final scores
        return self.calculate_keyword_scores()
    
    def save_results(self, keyword_scores: List[SimpleKeywordScore], 
                    output_path: Union[str, Path]) -> None:
        """Save keyword scoring results."""
        output_path = Path(output_path)
        
        # Prepare data for export
        results_data = []
        for score in keyword_scores:
            results_data.append({
                'keyword': score.keyword,
                'total_score': score.total_score,
                'final_score': score.final_score,
                'frequency': score.frequency,
                'video_count': score.video_count,
                'avg_engagement': score.avg_engagement,
                'avg_views': score.avg_views,
                'avg_likes': score.avg_likes,
                'avg_comments': score.avg_comments,
                'performance_correlation': score.performance_correlation,
                'score_per_video': score.score_per_video,
                'rarity_bonus': score.rarity_bonus,
                'top_videos': score.top_videos
            })
        
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'total_keywords': len(keyword_scores),
                    'processed_videos': self.processed_videos,
                    'performance_weights': self.performance_weights,
                    'extraction_method': 'simple_frequency'
                },
                'keywords': results_data
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved results to {json_path}")


def simple_score_keywords(json_path: Union[str, Path],
                         output_path: Union[str, Path],
                         max_videos: Optional[int] = None) -> List[SimpleKeywordScore]:
    """
    Simple keyword scoring function without external dependencies.
    
    Args:
        json_path: Path to TikTok JSON data
        output_path: Path to save results
        max_videos: Maximum videos to process
        
    Returns:
        List of SimpleKeywordScore objects
    """
    # Load data
    data_loader = TikTokDataLoader(json_path)
    data_loader.load_data(max_videos=max_videos)
    
    # Initialize simplified scoring engine
    scoring_engine = SimpleScoringEngine()
    
    # Process and score
    keyword_scores = scoring_engine.process_dataset(data_loader)
    
    # Save results
    scoring_engine.save_results(keyword_scores, output_path)
    
    return keyword_scores