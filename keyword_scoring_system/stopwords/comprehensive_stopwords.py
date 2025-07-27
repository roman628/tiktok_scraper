"""
Comprehensive stopword lists for TikTok content analysis.

This module provides carefully curated stopword lists optimized for social media content,
particularly TikTok, including platform-specific terms, contemporary slang, and algospeak.
"""

import spacy
from typing import Set, List, Dict
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

class TikTokStopwordManager:
    """
    Manages comprehensive stopword lists for TikTok content analysis.
    
    Provides multi-tier stopword filtering with regular updates for emerging slang
    and platform-specific terminology.
    """
    
    def __init__(self, use_base_spacy: bool = True, include_contractions: bool = True):
        """
        Initialize the stopword manager.
        
        Args:
            use_base_spacy: Whether to include spaCy's base English stopwords
            include_contractions: Whether to include contractions in stopwords
        """
        self.use_base_spacy = use_base_spacy
        self.include_contractions = include_contractions
        self._base_stopwords = set()
        self._platform_stopwords = set()
        self._slang_stopwords = set()
        self._noise_stopwords = set()
        self._preserve_words = set()
        
        self._initialize_stopwords()
    
    def _initialize_stopwords(self):
        """Initialize all stopword categories."""
        if self.use_base_spacy:
            try:
                nlp = spacy.load("en_core_web_sm")
                self._base_stopwords = set(nlp.Defaults.stop_words)
            except OSError:
                logger.warning("spaCy model not found, using fallback stopwords")
                self._base_stopwords = self._get_fallback_stopwords()
        
        self._platform_stopwords = self._get_platform_stopwords()
        self._noise_stopwords = self._get_noise_stopwords()
        self._preserve_words = self._get_preserve_words()
    
    def _get_fallback_stopwords(self) -> Set[str]:
        """Fallback stopwords if spaCy is not available."""
        return {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'would', 'you', 'your',
            'i', 'me', 'my', 'we', 'us', 'our', 'they', 'them', 'their',
            'this', 'these', 'those', 'have', 'had', 'been', 'being',
            'do', 'does', 'did', 'can', 'could', 'should', 'would', 'may',
            'might', 'must', 'shall', 'will', 'am', 'is', 'are', 'was', 'were'
        }
    
    def _get_platform_stopwords(self) -> Set[str]:
        """Platform-specific stopwords for TikTok and social media."""
        return {
            # TikTok specific
            'fyp', 'fvp', 'foryou', 'foryoupage', 'pov', 'grwm', 'iykyk', 'ootd',
            'npc', 'nsfw', 'periodt', 'bestie', 'ceo', 'gyat', 'oomf',
            
            # General social media
            'like', 'follow', 'share', 'comment', 'subscribe', 'notification',
            'trending', 'viral', 'algorithm', 'hashtag', 'tag', 'mention',
            'retweet', 'rt', 'dm', 'pm', 'story', 'reel', 'video', 'clip',
            'live', 'stream', 'broadcast', 'post', 'upload', 'content',
            
            # Platform names
            'tiktok', 'instagram', 'twitter', 'facebook', 'youtube', 'snapchat',
            'app', 'platform', 'social', 'media'
        }
    
    def _get_noise_stopwords(self) -> Set[str]:
        """High-frequency, low-content words specific to social media."""
        return {
            # Generic intensifiers without specific meaning
            'smash', 'hit', 'bang', 'fire', 'sick', 'insane', 'crazy',
            'wild', 'mad', 'epic', 'savage', 'based', 'cringe', 'mid',
            
            # Non-specific descriptors
            'random', 'weird', 'strange', 'odd', 'normal', 'regular',
            'basic', 'simple', 'easy', 'hard', 'difficult', 'tough',
            
            # Temporal references (unless doing time-series analysis)
            'today', 'yesterday', 'tomorrow', 'now', 'then', 'later',
            'morning', 'afternoon', 'evening', 'night', 'day', 'time',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
            'saturday', 'sunday', 'week', 'month', 'year',
            
            # Single characters and short words (≤2 chars)
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l',
            'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x',
            'y', 'z', 'an', 'as', 'at', 'be', 'by', 'do', 'go', 'he',
            'if', 'in', 'is', 'it', 'me', 'my', 'no', 'of', 'on', 'or',
            'so', 'to', 'up', 'us', 'we'
        }
    
    def _get_preserve_words(self) -> Set[str]:
        """Words to preserve even if they appear in other stopword lists."""
        return {
            # Sentiment indicators
            'not', 'never', 'no', 'none', 'neither', 'nor', 'nothing',
            'nowhere', 'nobody', 'cannot', 'cant', 'wont', 'dont',
            'doesnt', 'didnt', 'wouldnt', 'shouldnt', 'couldnt',
            
            # Intensity modifiers
            'very', 'extremely', 'incredibly', 'absolutely', 'totally',
            'completely', 'entirely', 'utterly', 'thoroughly', 'highly',
            
            # Emotional expressions
            'love', 'hate', 'amazing', 'terrible', 'awesome', 'awful',
            'fantastic', 'horrible', 'wonderful', 'disgusting', 'beautiful',
            'ugly', 'perfect', 'disaster', 'brilliant', 'stupid'
        }
    
    def get_comprehensive_stopwords(self, tier: str = "all") -> Set[str]:
        """
        Get stopwords based on filtering tier.
        
        Args:
            tier: Filtering level - 'essential', 'extended', or 'all'
                - essential: Core grammatical and platform words
                - extended: Includes slang and noise words
                - all: Complete comprehensive set
        
        Returns:
            Set of stopwords for the specified tier
        """
        essential = self._base_stopwords | self._platform_stopwords
        
        if tier == "essential":
            return essential - self._preserve_words
        elif tier == "extended":
            return essential | self._slang_stopwords - self._preserve_words
        elif tier == "all":
            return (essential | self._slang_stopwords | self._noise_stopwords 
                   - self._preserve_words)
        else:
            raise ValueError("Tier must be 'essential', 'extended', or 'all'")
    
    def get_category_stopwords(self, category: str) -> Set[str]:
        """
        Get stopwords for a specific category.
        
        Args:
            category: One of 'base', 'platform', 'slang', 'noise', 'preserve'
        
        Returns:
            Set of stopwords for the specified category
        """
        categories = {
            'base': self._base_stopwords,
            'platform': self._platform_stopwords,
            'slang': self._slang_stopwords,
            'noise': self._noise_stopwords,
            'preserve': self._preserve_words
        }
        
        if category not in categories:
            raise ValueError(f"Category must be one of {list(categories.keys())}")
        
        return categories[category]
    
    def is_stopword(self, word: str, tier: str = "all") -> bool:
        """
        Check if a word is a stopword.
        
        Args:
            word: Word to check
            tier: Filtering tier to use
        
        Returns:
            True if word is a stopword, False otherwise
        """
        stopwords = self.get_comprehensive_stopwords(tier)
        return word.lower() in stopwords
    
    def filter_tokens(self, tokens: List[str], tier: str = "all") -> List[str]:
        """
        Filter stopwords from a list of tokens.
        
        Args:
            tokens: List of tokens to filter
            tier: Filtering tier to use
        
        Returns:
            List of tokens with stopwords removed
        """
        stopwords = self.get_comprehensive_stopwords(tier)
        return [token for token in tokens if token.lower() not in stopwords]
    
    def add_custom_stopwords(self, words: Set[str], category: str = "custom"):
        """
        Add custom stopwords to a specific category.
        
        Args:
            words: Set of words to add
            category: Category to add to ('platform', 'slang', 'noise')
        """
        if category == "platform":
            self._platform_stopwords.update(words)
        elif category == "slang":
            self._slang_stopwords.update(words)
        elif category == "noise":
            self._noise_stopwords.update(words)
        else:
            # Add to noise category by default
            self._noise_stopwords.update(words)
        
        logger.info(f"Added {len(words)} custom stopwords to {category} category")
    
    def save_stopwords(self, filepath: Path, tier: str = "all"):
        """
        Save stopwords to a JSON file.
        
        Args:
            filepath: Path to save the stopwords
            tier: Tier of stopwords to save
        """
        stopwords = self.get_comprehensive_stopwords(tier)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(list(stopwords), f, indent=2, sort_keys=True)
        
        logger.info(f"Saved {len(stopwords)} stopwords to {filepath}")
    
    def load_custom_stopwords(self, filepath: Path, category: str = "custom"):
        """
        Load custom stopwords from a JSON file.
        
        Args:
            filepath: Path to load stopwords from
            category: Category to add the loaded stopwords to
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            custom_words = set(json.load(f))
        
        self.add_custom_stopwords(custom_words, category)
        logger.info(f"Loaded {len(custom_words)} custom stopwords from {filepath}")
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the stopword sets.
        
        Returns:
            Dictionary with counts for each category
        """
        return {
            'base_stopwords': len(self._base_stopwords),
            'platform_stopwords': len(self._platform_stopwords),
            'slang_stopwords': len(self._slang_stopwords),
            'noise_stopwords': len(self._noise_stopwords),
            'preserve_words': len(self._preserve_words),
            'total_essential': len(self.get_comprehensive_stopwords('essential')),
            'total_extended': len(self.get_comprehensive_stopwords('extended')),
            'total_comprehensive': len(self.get_comprehensive_stopwords('all'))
        }


# Convenience function for quick access
def get_tiktok_stopwords(tier: str = "all") -> Set[str]:
    """
    Quick function to get TikTok stopwords.
    
    Args:
        tier: Filtering tier ('essential', 'extended', or 'all')
    
    Returns:
        Set of stopwords
    """
    manager = TikTokStopwordManager()
    return manager.get_comprehensive_stopwords(tier)


# Pre-built stopword sets for immediate use
ESSENTIAL_STOPWORDS = get_tiktok_stopwords("essential")
EXTENDED_STOPWORDS = get_tiktok_stopwords("extended")
COMPREHENSIVE_STOPWORDS = get_tiktok_stopwords("all")