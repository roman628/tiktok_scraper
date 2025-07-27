"""
Sentiment analysis module for TikTok comments and content.

Implements VADER sentiment analysis optimized for social media content,
with special handling for TikTok-specific language and emoji.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import nltk
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    """Represents sentiment analysis results."""
    positive: float
    negative: float
    neutral: float
    compound: float
    
    @property
    def label(self) -> str:
        """Get sentiment label based on compound score."""
        if self.compound >= 0.05:
            return 'positive'
        elif self.compound <= -0.05:
            return 'negative'
        else:
            return 'neutral'
    
    @property
    def intensity(self) -> str:
        """Get sentiment intensity level."""
        abs_compound = abs(self.compound)
        if abs_compound >= 0.7:
            return 'very_strong'
        elif abs_compound >= 0.5:
            return 'strong'
        elif abs_compound >= 0.2:
            return 'moderate'
        else:
            return 'weak'


class TikTokSentimentAnalyzer:
    """
    Sentiment analyzer optimized for TikTok content.
    
    Extends VADER with TikTok-specific vocabulary and emoji handling.
    """
    
    def __init__(self, use_emoji: bool = True, 
                 boost_slang: bool = True):
        """
        Initialize the sentiment analyzer.
        
        Args:
            use_emoji: Whether to include emoji sentiment analysis
            boost_slang: Whether to boost TikTok slang recognition
        """
        self.use_emoji = use_emoji
        self.boost_slang = boost_slang
        
        # Initialize VADER
        self.analyzer = SentimentIntensityAnalyzer()
        
        # Add TikTok-specific lexicon updates
        if boost_slang:
            self._update_lexicon()
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
    
    def _update_lexicon(self):
        """Update VADER lexicon with TikTok-specific terms."""
        
        # TikTok-specific positive terms
        tiktok_positive = {
            'slay': 2.5,
            'slaps': 2.0,
            'fire': 2.2,
            'queen': 2.0,
            'king': 2.0,
            'iconic': 2.1,
            'legend': 2.0,
            'periodt': 1.8,
            'bestie': 1.5,
            'bop': 1.8,
            'chef_kiss': 2.5,
            'chefs_kiss': 2.5,
            'no_cap': 1.9,
            'nocap': 1.9,
            'hits_different': 2.0,
            'different': 1.5,
            'rizz': 1.7,
            'main_character': 1.8,
            'serve': 2.0,
            'serving': 2.0,
            'ate': 2.2,
            'left_no_crumbs': 2.5,
            'understood_the_assignment': 2.3,
            'bussin': 2.0,
            'valid': 1.8,
            'vibe': 1.3,
            'vibes': 1.3,
            'aesthetic': 1.5,
            'immaculate': 2.4,
            'elite': 2.0,
            'goated': 2.3,
            'based': 1.8,
            'wholesome': 2.0,
            'chef': 2.0,
            'masterpiece': 2.5,
            'perfection': 2.8,
            'flawless': 2.6
        }
        
        # TikTok-specific negative terms
        tiktok_negative = {
            'cringe': -2.0,
            'cringey': -2.0,
            'mid': -1.5,
            'sus': -1.2,
            'suspicious': -1.2,
            'toxic': -2.5,
            'cancelled': -2.8,
            'problematic': -2.2,
            'flop': -2.0,
            'flopped': -2.0,
            'disappointing': -1.8,
            'overrated': -1.5,
            'try_hard': -1.3,
            'tryhard': -1.3,
            'secondhand_embarrassment': -2.2,
            'yikes': -1.8,
            'oof': -1.2,
            'awkward': -1.5,
            'uncomfortable': -1.7,
            'concerning': -1.9,
            'questionable': -1.4,
            'weird': -1.0,
            'strange': -0.8,
            'off': -1.1,
            'miss': -1.2,
            'missed': -1.2,
            'not_it': -1.8,
            'ain_t_it': -1.8
        }
        
        # Update the lexicon
        self.analyzer.lexicon.update(tiktok_positive)
        self.analyzer.lexicon.update(tiktok_negative)
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for sentiment analysis.
        
        Args:
            text: Raw text to preprocess
            
        Returns:
            Cleaned text ready for analysis
        """
        if not text:
            return ""
        
        # Convert to string if not already
        text = str(text)
        
        # Handle common TikTok abbreviations and algospeak
        text = re.sub(r'\b(idk|IDK)\b', 'i do not know', text)
        text = re.sub(r'\b(tbh|TBH)\b', 'to be honest', text)
        text = re.sub(r'\b(ngl|NGL)\b', 'not going to lie', text)
        text = re.sub(r'\b(fr|FR)\b', 'for real', text)
        text = re.sub(r'\b(ong|ONG)\b', 'on god', text)
        text = re.sub(r'\bunalive\b', 'kill', text, flags=re.IGNORECASE)
        text = re.sub(r'\bseggs\b', 'sex', text, flags=re.IGNORECASE)
        
        # Handle repeated characters (looooove -> love)
        text = re.sub(r'(.)\1{2,}', r'\1\1', text)
        
        # Handle excessive punctuation
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        # Convert common emoji representations
        if self.use_emoji:
            text = self._convert_emoji_text(text)
        
        return text
    
    def _convert_emoji_text(self, text: str) -> str:
        """Convert text representations of emotions to words."""
        
        # Positive emoji/emoticon patterns
        positive_patterns = [
            (r':\)', 'happy'),
            (r':-\)', 'happy'),
            (r':D', 'very happy'),
            (r':-D', 'very happy'),
            (r'<3', 'love'),
            (r'♥', 'love'),
            (r'❤', 'love'),
            (r'💕', 'love'),
            (r'😍', 'love'),
            (r'🥰', 'love'),
            (r'😊', 'happy'),
            (r'😄', 'happy'),
            (r'😃', 'happy'),
            (r'😁', 'happy'),
            (r'🔥', 'fire'),
            (r'💯', 'perfect'),
            (r'👏', 'applause'),
            (r'🙌', 'praise'),
            (r'✨', 'sparkle'),
            (r'💖', 'love'),
            (r'💝', 'love'),
        ]
        
        # Negative emoji/emoticon patterns
        negative_patterns = [
            (r':\(', 'sad'),
            (r':-\(', 'sad'),
            (r':/', 'disappointed'),
            (r':-/', 'disappointed'),
            (r'💀', 'dead'),
            (r'😭', 'crying'),
            (r'😢', 'sad'),
            (r'😞', 'sad'),
            (r'😔', 'sad'),
            (r'😕', 'disappointed'),
            (r'😒', 'annoyed'),
            (r'🙄', 'annoyed'),
            (r'😤', 'angry'),
            (r'😠', 'angry'),
            (r'😡', 'angry'),
            (r'🤮', 'disgusted'),
            (r'🤢', 'sick'),
            (r'💩', 'bad'),
        ]
        
        # Apply positive patterns
        for pattern, replacement in positive_patterns:
            text = re.sub(pattern, f' {replacement} ', text)
        
        # Apply negative patterns
        for pattern, replacement in negative_patterns:
            text = re.sub(pattern, f' {replacement} ', text)
        
        return text
    
    def analyze_text(self, text: str) -> SentimentScore:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentScore object
        """
        if not text or not str(text).strip():
            return SentimentScore(0.0, 0.0, 1.0, 0.0)
        
        # Preprocess text
        processed_text = self.preprocess_text(text)
        
        # Get VADER scores
        scores = self.analyzer.polarity_scores(processed_text)
        
        return SentimentScore(
            positive=scores['pos'],
            negative=scores['neg'],
            neutral=scores['neu'],
            compound=scores['compound']
        )
    
    def analyze_comments(self, comments: List[Dict]) -> Dict[str, Union[float, int, Dict]]:
        """
        Analyze sentiment of multiple comments with engagement weighting.
        
        Args:
            comments: List of comment dictionaries with 'comment_text' and 'like_count'
            
        Returns:
            Dictionary with aggregated sentiment metrics
        """
        if not comments:
            return {
                'overall_sentiment': 0.0,
                'positive_ratio': 0.0,
                'negative_ratio': 0.0,
                'neutral_ratio': 0.0,
                'weighted_sentiment': 0.0,
                'comment_count': 0,
                'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
            }
        
        sentiment_scores = []
        weighted_scores = []
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        total_likes = 0
        
        for comment in comments:
            comment_text = comment.get('comment_text', '')
            like_count = comment.get('like_count', 0)
            
            if not comment_text:
                continue
            
            # Analyze sentiment
            sentiment = self.analyze_text(comment_text)
            sentiment_scores.append(sentiment.compound)
            
            # Weight by engagement (likes + 1 to avoid zero weights)
            weight = like_count + 1
            weighted_scores.append(sentiment.compound * weight)
            total_likes += weight
            
            # Count sentiment categories
            sentiment_counts[sentiment.label] += 1
        
        if not sentiment_scores:
            return {
                'overall_sentiment': 0.0,
                'positive_ratio': 0.0,
                'negative_ratio': 0.0,
                'neutral_ratio': 0.0,
                'weighted_sentiment': 0.0,
                'comment_count': 0,
                'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
            }
        
        # Calculate metrics
        overall_sentiment = np.mean(sentiment_scores)
        weighted_sentiment = sum(weighted_scores) / total_likes if total_likes > 0 else 0.0
        
        total_comments = len(sentiment_scores)
        positive_ratio = sentiment_counts['positive'] / total_comments
        negative_ratio = sentiment_counts['negative'] / total_comments
        neutral_ratio = sentiment_counts['neutral'] / total_comments
        
        return {
            'overall_sentiment': overall_sentiment,
            'positive_ratio': positive_ratio,
            'negative_ratio': negative_ratio,
            'neutral_ratio': neutral_ratio,
            'weighted_sentiment': weighted_sentiment,
            'comment_count': total_comments,
            'sentiment_distribution': sentiment_counts,
            'sentiment_scores': sentiment_scores
        }
    
    def get_emotional_keywords(self, text: str, min_intensity: float = 0.5) -> List[Tuple[str, float, str]]:
        """
        Extract emotionally charged keywords from text.
        
        Args:
            text: Text to analyze
            min_intensity: Minimum sentiment intensity threshold
            
        Returns:
            List of (keyword, sentiment_score, sentiment_label) tuples
        """
        if not text:
            return []
        
        processed_text = self.preprocess_text(text)
        words = processed_text.split()
        
        emotional_keywords = []
        
        for word in words:
            # Clean word
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            if len(clean_word) < 3:
                continue
            
            # Check if word has sentiment in lexicon
            if clean_word in self.analyzer.lexicon:
                sentiment_score = self.analyzer.lexicon[clean_word]
                
                if abs(sentiment_score) >= min_intensity:
                    label = 'positive' if sentiment_score > 0 else 'negative'
                    emotional_keywords.append((clean_word, sentiment_score, label))
        
        # Sort by absolute sentiment strength
        emotional_keywords.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return emotional_keywords
    
    def analyze_content_sentiment(self, video_data) -> Dict[str, Union[float, Dict]]:
        """
        Analyze sentiment of video content (title, description, transcription).
        
        Args:
            video_data: VideoData object
            
        Returns:
            Dictionary with content sentiment analysis
        """
        content_sentiment = self.analyze_text(video_data.content_text)
        comments_analysis = self.analyze_comments(video_data.top_comments)
        
        # Calculate overall video sentiment (weighted average)
        content_weight = 0.7  # Content is weighted higher than comments
        comment_weight = 0.3
        
        overall_sentiment = (
            content_sentiment.compound * content_weight +
            comments_analysis['weighted_sentiment'] * comment_weight
        )
        
        return {
            'content_sentiment': {
                'compound': content_sentiment.compound,
                'positive': content_sentiment.positive,
                'negative': content_sentiment.negative,
                'neutral': content_sentiment.neutral,
                'label': content_sentiment.label,
                'intensity': content_sentiment.intensity
            },
            'comments_sentiment': comments_analysis,
            'overall_sentiment': overall_sentiment,
            'sentiment_alignment': self._calculate_sentiment_alignment(
                content_sentiment.compound, 
                comments_analysis['weighted_sentiment']
            )
        }
    
    def _calculate_sentiment_alignment(self, content_sentiment: float, 
                                     comment_sentiment: float) -> Dict[str, Union[float, str]]:
        """
        Calculate alignment between content and comment sentiment.
        
        Args:
            content_sentiment: Content sentiment score
            comment_sentiment: Comment sentiment score
            
        Returns:
            Dictionary with alignment metrics
        """
        # Calculate absolute difference
        difference = abs(content_sentiment - comment_sentiment)
        
        # Calculate alignment score (1 = perfect alignment, 0 = complete disagreement)
        alignment_score = max(0, 1 - difference / 2)
        
        # Determine alignment category
        if alignment_score >= 0.8:
            alignment_category = 'strong_agreement'
        elif alignment_score >= 0.6:
            alignment_category = 'moderate_agreement'
        elif alignment_score >= 0.4:
            alignment_category = 'weak_agreement'
        else:
            alignment_category = 'disagreement'
        
        return {
            'alignment_score': alignment_score,
            'alignment_category': alignment_category,
            'sentiment_difference': difference
        }


def analyze_sentiment(text: str, **kwargs) -> SentimentScore:
    """
    Convenience function for quick sentiment analysis.
    
    Args:
        text: Text to analyze
        **kwargs: Additional arguments for TikTokSentimentAnalyzer
        
    Returns:
        SentimentScore object
    """
    analyzer = TikTokSentimentAnalyzer(**kwargs)
    return analyzer.analyze_text(text)