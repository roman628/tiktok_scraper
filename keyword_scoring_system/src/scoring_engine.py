"""
Keyword scoring engine that combines extraction, sentiment, and engagement metrics.

This module implements the core scoring algorithm that weighs keywords based on
their performance correlation with video success metrics.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import numpy as np
import pandas as pd
from pathlib import Path
import json

from .data_loader import VideoData, TikTokDataLoader
from .keyword_extractor import TikTokKeywordExtractor, extract_video_keywords
from .sentiment_analyzer import TikTokSentimentAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class KeywordScore:
    """Represents a keyword with its comprehensive scoring metrics."""
    keyword: str
    total_score: float
    frequency: int
    video_count: int
    avg_engagement: float
    avg_views: float
    avg_likes: float
    avg_comments: float
    sentiment_score: float
    performance_correlation: float
    top_videos: List[str] = field(default_factory=list)
    context_categories: Set[str] = field(default_factory=set)
    
    @property
    def score_per_video(self) -> float:
        """Average score per video appearance."""
        return self.total_score / self.video_count if self.video_count > 0 else 0.0
    
    @property
    def rarity_bonus(self) -> float:
        """Bonus for rare but high-performing keywords."""
        if self.video_count == 0:
            return 0.0
        
        # Inverse frequency with logarithmic scaling
        base_rarity = 1.0 / self.video_count
        return math.log(1 + base_rarity * 100)
    
    @property
    def final_score(self) -> float:
        """Final score combining all factors."""
        return (
            self.total_score * 
            (1 + self.rarity_bonus * 0.1) *  # Small rarity bonus
            (1 + max(0, self.sentiment_score) * 0.2)  # Sentiment boost
        )


class KeywordScoringEngine:
    """
    Main engine for keyword scoring and analysis.
    
    Processes video data to extract keywords and score them based on
    their correlation with video performance metrics.
    """
    
    def __init__(self, 
                 extraction_methods: Optional[List[str]] = None,
                 sentiment_analysis: bool = True,
                 performance_weights: Optional[Dict[str, float]] = None):
        """
        Initialize the scoring engine.
        
        Args:
            extraction_methods: Keyword extraction methods to use
            sentiment_analysis: Whether to include sentiment analysis
            performance_weights: Weights for different performance metrics
        """
        self.extraction_methods = extraction_methods or ['rake', 'textrank', 'yake']
        self.sentiment_analysis = sentiment_analysis
        
        # Default weights for performance metrics
        self.performance_weights = performance_weights or {
            'engagement_score': 3.0,
            'view_count': 1.0,
            'like_count': 2.0,
            'comment_count': 2.5,
            'repost_count': 1.5
        }
        
        # Initialize components
        self.keyword_extractor = TikTokKeywordExtractor(methods=self.extraction_methods)
        
        if self.sentiment_analysis:
            self.sentiment_analyzer = TikTokSentimentAnalyzer()
        else:
            self.sentiment_analyzer = None
        
        # Storage for analysis results
        self.keyword_data: Dict[str, Dict] = defaultdict(lambda: {
            'videos': [],
            'total_engagement': 0.0,
            'total_views': 0,
            'total_likes': 0,
            'total_comments': 0,
            'total_reposts': 0,
            'sentiment_scores': [],
            'contexts': set()
        })
        
        self.processed_videos = 0
        self.total_videos = 0
    
    def process_video_batch(self, videos: List[VideoData], 
                           min_keyword_score: float = 0.1) -> None:
        """
        Process a batch of videos for keyword scoring.
        
        Args:
            videos: List of VideoData objects to process
            min_keyword_score: Minimum keyword score threshold
        """
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
        """
        Process a single video for keyword scoring.
        
        Args:
            video: VideoData object
            min_keyword_score: Minimum keyword score threshold
        """
        # Extract keywords from video content
        keywords = extract_video_keywords(
            video, 
            methods=self.extraction_methods, 
            top_k=30
        )
        
        # Filter keywords by minimum score
        keywords = [k for k in keywords if k['score'] >= min_keyword_score]
        
        if not keywords:
            return
        
        # Calculate video performance metrics
        performance_score = self._calculate_performance_score(video)
        
        # Analyze sentiment if enabled
        sentiment_data = None
        if self.sentiment_analyzer:
            sentiment_data = self.sentiment_analyzer.analyze_content_sentiment(video)
        
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
                'repost_count': video.repost_count,
                'sentiment': sentiment_data['overall_sentiment'] if sentiment_data else 0.0
            })
            
            # Accumulate metrics
            self.keyword_data[keyword]['total_engagement'] += video.engagement_score
            self.keyword_data[keyword]['total_views'] += video.view_count
            self.keyword_data[keyword]['total_likes'] += video.like_count
            self.keyword_data[keyword]['total_comments'] += video.comment_count
            self.keyword_data[keyword]['total_reposts'] += video.repost_count
            
            if sentiment_data:
                self.keyword_data[keyword]['sentiment_scores'].append(
                    sentiment_data['overall_sentiment']
                )
            
            # Add context information
            self.keyword_data[keyword]['contexts'].add(
                self._determine_content_context(video)
            )
    
    def _calculate_performance_score(self, video: VideoData) -> float:
        """
        Calculate weighted performance score for a video.
        
        Args:
            video: VideoData object
            
        Returns:
            Weighted performance score
        """
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
    
    def _determine_content_context(self, video: VideoData) -> str:
        """
        Determine the context category of video content.
        
        Args:
            video: VideoData object
            
        Returns:
            Context category string
        """
        content = (video.title + " " + video.description + " " + 
                  (video.transcription or "")).lower()
        
        # Define context keywords
        contexts = {
            'comedy': ['funny', 'laugh', 'humor', 'joke', 'meme', 'comedy', 'hilarious'],
            'dance': ['dance', 'dancing', 'choreography', 'moves', 'routine'],
            'music': ['song', 'music', 'sing', 'singing', 'cover', 'remix'],
            'education': ['learn', 'education', 'tutorial', 'how', 'tips', 'guide'],
            'lifestyle': ['life', 'daily', 'routine', 'vlog', 'day', 'lifestyle'],
            'beauty': ['makeup', 'beauty', 'skincare', 'hair', 'style', 'fashion'],
            'food': ['food', 'recipe', 'cooking', 'eat', 'restaurant', 'meal'],
            'travel': ['travel', 'trip', 'vacation', 'explore', 'adventure'],
            'pets': ['pet', 'dog', 'cat', 'animal', 'puppy', 'kitten'],
            'sports': ['sport', 'game', 'play', 'team', 'win', 'competition']
        }
        
        # Check for context matches
        for context, keywords in contexts.items():
            if any(keyword in content for keyword in keywords):
                return context
        
        return 'general'
    
    def calculate_keyword_scores(self, min_video_count: int = 2) -> List[KeywordScore]:
        """
        Calculate final keyword scores.
        
        Args:
            min_video_count: Minimum number of videos a keyword must appear in
            
        Returns:
            List of KeywordScore objects sorted by final score
        """
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
            
            # Calculate average sentiment
            sentiment_scores = data['sentiment_scores']
            avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0.0
            
            # Calculate performance correlation
            video_performances = [v['performance_score'] for v in data['videos']]
            performance_correlation = np.mean(video_performances)
            
            # Calculate total score (weighted by video count and performance)
            total_score = performance_correlation * video_count
            
            # Get top performing videos
            top_videos = sorted(
                data['videos'], 
                key=lambda x: x['performance_score'], 
                reverse=True
            )[:5]
            top_video_ids = [v['video_id'] for v in top_videos]
            
            keyword_score = KeywordScore(
                keyword=keyword,
                total_score=total_score,
                frequency=video_count,
                video_count=video_count,
                avg_engagement=avg_engagement,
                avg_views=avg_views,
                avg_likes=avg_likes,
                avg_comments=avg_comments,
                sentiment_score=avg_sentiment,
                performance_correlation=performance_correlation,
                top_videos=top_video_ids,
                context_categories=data['contexts']
            )
            
            keyword_scores.append(keyword_score)
        
        # Sort by final score
        keyword_scores.sort(key=lambda x: x.final_score, reverse=True)
        
        logger.info(f"Generated scores for {len(keyword_scores)} keywords")
        return keyword_scores
    
    def process_dataset(self, 
                       data_loader: TikTokDataLoader,
                       batch_size: int = 100,
                       min_keyword_score: float = 0.1) -> List[KeywordScore]:
        """
        Process entire dataset and calculate keyword scores.
        
        Args:
            data_loader: Loaded TikTokDataLoader
            batch_size: Size of processing batches
            min_keyword_score: Minimum keyword extraction score
            
        Returns:
            List of KeywordScore objects
        """
        videos = data_loader.get_videos()
        self.total_videos = len(videos)
        
        logger.info(f"Processing {self.total_videos} videos in batches of {batch_size}")
        
        # Process in batches
        for batch in data_loader.get_video_iterator(batch_size):
            self.process_video_batch(batch, min_keyword_score)
        
        # Calculate final scores
        return self.calculate_keyword_scores()
    
    def save_results(self, keyword_scores: List[KeywordScore], 
                    output_path: Union[str, Path],
                    format: str = 'json') -> None:
        """
        Save keyword scoring results.
        
        Args:
            keyword_scores: List of KeywordScore objects
            output_path: Path to save results
            format: Output format ('json', 'csv', 'both')
        """
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
                'sentiment_score': score.sentiment_score,
                'performance_correlation': score.performance_correlation,
                'score_per_video': score.score_per_video,
                'rarity_bonus': score.rarity_bonus,
                'top_videos': score.top_videos,
                'context_categories': list(score.context_categories)
            })
        
        if format in ['json', 'both']:
            json_path = output_path.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'total_keywords': len(keyword_scores),
                        'processed_videos': self.processed_videos,
                        'extraction_methods': self.extraction_methods,
                        'performance_weights': self.performance_weights
                    },
                    'keywords': results_data
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved JSON results to {json_path}")
        
        if format in ['csv', 'both']:
            csv_path = output_path.with_suffix('.csv')
            df = pd.DataFrame(results_data)
            
            # Flatten complex fields for CSV
            df['top_videos'] = df['top_videos'].apply(lambda x: ';'.join(x))
            df['context_categories'] = df['context_categories'].apply(lambda x: ';'.join(x))
            
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved CSV results to {csv_path}")
    
    def get_statistics(self) -> Dict[str, Union[int, float]]:
        """
        Get processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        keyword_counts = [len(data['videos']) for data in self.keyword_data.values()]
        
        return {
            'processed_videos': self.processed_videos,
            'total_keywords': len(self.keyword_data),
            'avg_keywords_per_video': np.mean(keyword_counts) if keyword_counts else 0,
            'max_keyword_frequency': max(keyword_counts) if keyword_counts else 0,
            'unique_contexts': len(set().union(*[data['contexts'] for data in self.keyword_data.values()]))
        }


def score_keywords(json_path: Union[str, Path],
                  output_path: Union[str, Path],
                  max_videos: Optional[int] = None,
                  extraction_methods: Optional[List[str]] = None,
                  **kwargs) -> List[KeywordScore]:
    """
    Convenience function to score keywords from TikTok data.
    
    Args:
        json_path: Path to TikTok JSON data
        output_path: Path to save results
        max_videos: Maximum videos to process
        extraction_methods: Keyword extraction methods
        **kwargs: Additional arguments for scoring engine
        
    Returns:
        List of KeywordScore objects
    """
    # Load data
    data_loader = TikTokDataLoader(json_path)
    data_loader.load_data(max_videos=max_videos)
    
    # Initialize scoring engine
    scoring_engine = KeywordScoringEngine(
        extraction_methods=extraction_methods,
        **kwargs
    )
    
    # Process and score
    keyword_scores = scoring_engine.process_dataset(data_loader)
    
    # Save results
    scoring_engine.save_results(keyword_scores, output_path, format='both')
    
    return keyword_scores