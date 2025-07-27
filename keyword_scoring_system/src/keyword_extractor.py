"""
Keyword extraction module using the existing TikTok-optimized extraction methods.

This module integrates the existing keyword extraction system and adapts it
for the keyword scoring pipeline.
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import importlib.util

# Add the src directory to Python path to import existing modules
SRC_PATH = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

try:
    from stopwords.comprehensive_stopwords import TikTokStopwordManager, get_tiktok_stopwords
    from keyword_extraction.extraction_methods import (
        MultiMethodExtractor, ExtractedKeyword, RAKEExtractor, 
        TextRankExtractor, TFIDFExtractor, YAKEExtractor
    )
except ImportError as e:
    logging.error(f"Could not import existing keyword extraction modules: {e}")
    # Fallback implementation will be provided below

logger = logging.getLogger(__name__)


class TikTokKeywordExtractor:
    """
    Wrapper for TikTok keyword extraction with scoring integration.
    
    Uses the existing multi-method extraction system optimized for TikTok content.
    """
    
    def __init__(self, 
                 methods: Optional[List[str]] = None,
                 stopword_tier: str = "extended",
                 custom_stopwords: Optional[Set[str]] = None):
        """
        Initialize the keyword extractor.
        
        Args:
            methods: List of extraction methods to use
            stopword_tier: Tier of stopwords ('essential', 'extended', 'all')
            custom_stopwords: Additional custom stopwords
        """
        self.methods = methods or ['rake', 'textrank', 'yake']
        self.stopword_tier = stopword_tier
        self.custom_stopwords = custom_stopwords or set()
        
        # Initialize stopword manager
        try:
            self.stopword_manager = TikTokStopwordManager()
            if self.custom_stopwords:
                self.stopword_manager.add_custom_stopwords(self.custom_stopwords)
        except NameError:
            logger.warning("TikTokStopwordManager not available, using fallback")
            self.stopword_manager = None
        
        # Initialize multi-method extractor
        try:
            self.extractor = MultiMethodExtractor(
                methods=self.methods,
                stopword_manager=self.stopword_manager,
                stopword_tier=self.stopword_tier
            )
        except NameError:
            logger.warning("MultiMethodExtractor not available, using fallback")
            self.extractor = None
    
    def extract_keywords(self, text: str, 
                        top_k: int = 20,
                        fusion_method: str = "rank_fusion") -> List[Dict]:
        """
        Extract keywords from text.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            fusion_method: Method for fusing results
            
        Returns:
            List of keyword dictionaries
        """
        if not text or not text.strip():
            return []
        
        try:
            if self.extractor:
                # Use the existing multi-method extractor
                results = self.extractor.extract_keywords(
                    text, top_k=top_k, fusion_method=fusion_method
                )
                
                # Convert to dictionary format
                keywords = []
                for result in results:
                    keywords.append({
                        'keyword': result.keyword,
                        'score': result.score,
                        'method': result.method,
                        'position': result.position,
                        'frequency': getattr(result, 'frequency', None),
                        'length': getattr(result, 'length', len(result.keyword.split()))
                    })
                
                return keywords
            else:
                # Fallback to simple extraction
                return self._fallback_extraction(text, top_k)
                
        except Exception as e:
            logger.error(f"Error in keyword extraction: {e}")
            return self._fallback_extraction(text, top_k)
    
    def _fallback_extraction(self, text: str, top_k: int) -> List[Dict]:
        """
        Fallback keyword extraction using simple frequency analysis.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of keywords to return
            
        Returns:
            List of keyword dictionaries
        """
        import re
        from collections import Counter
        
        # Simple tokenization
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter short words and common stopwords
        basic_stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'is', 'am', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'myself',
            'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
            'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
            'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves'
        }
        
        # Add custom stopwords
        all_stopwords = basic_stopwords | self.custom_stopwords
        
        # Filter words
        filtered_words = [
            word for word in words 
            if len(word) > 2 and word not in all_stopwords and not word.isdigit()
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
    
    def extract_content_keywords(self, video_data, top_k: int = 15) -> Dict[str, List[Dict]]:
        """
        Extract keywords from different parts of video content.
        
        Args:
            video_data: VideoData object
            top_k: Number of keywords per section
            
        Returns:
            Dictionary with keywords from different content sections
        """
        results = {}
        
        # Extract from title
        if video_data.title:
            results['title'] = self.extract_keywords(video_data.title, top_k=top_k//2)
        else:
            results['title'] = []
        
        # Extract from description
        if video_data.description:
            results['description'] = self.extract_keywords(video_data.description, top_k=top_k//2)
        else:
            results['description'] = []
        
        # Extract from transcription
        if video_data.transcription:
            results['transcription'] = self.extract_keywords(video_data.transcription, top_k=top_k)
        else:
            results['transcription'] = []
        
        # Extract from combined content
        results['combined_content'] = self.extract_keywords(video_data.content_text, top_k=top_k)
        
        # Extract from comments
        comment_text = ' '.join([
            comment.get('comment_text', '') 
            for comment in video_data.top_comments
        ])
        if comment_text.strip():
            results['comments'] = self.extract_keywords(comment_text, top_k=top_k//2)
        else:
            results['comments'] = []
        
        return results
    
    def get_all_unique_keywords(self, keyword_results: Dict[str, List[Dict]]) -> Set[str]:
        """
        Get all unique keywords from extraction results.
        
        Args:
            keyword_results: Results from extract_content_keywords
            
        Returns:
            Set of all unique keywords
        """
        all_keywords = set()
        
        for section_keywords in keyword_results.values():
            for keyword_data in section_keywords:
                all_keywords.add(keyword_data['keyword'])
        
        return all_keywords
    
    def merge_keyword_scores(self, keyword_results: Dict[str, List[Dict]], 
                           weights: Optional[Dict[str, float]] = None) -> List[Dict]:
        """
        Merge keyword scores from different content sections.
        
        Args:
            keyword_results: Results from extract_content_keywords
            weights: Weights for different sections
            
        Returns:
            List of merged keyword dictionaries
        """
        if weights is None:
            weights = {
                'title': 2.0,
                'description': 1.5,
                'transcription': 1.0,
                'combined_content': 1.2,
                'comments': 0.8
            }
        
        # Collect all keywords with their scores
        keyword_scores = {}
        keyword_methods = {}
        keyword_frequencies = {}
        
        for section, section_keywords in keyword_results.items():
            section_weight = weights.get(section, 1.0)
            
            for keyword_data in section_keywords:
                keyword = keyword_data['keyword']
                score = keyword_data['score'] * section_weight
                
                if keyword in keyword_scores:
                    keyword_scores[keyword] += score
                    keyword_frequencies[keyword] += keyword_data.get('frequency', 1)
                else:
                    keyword_scores[keyword] = score
                    keyword_methods[keyword] = keyword_data['method']
                    keyword_frequencies[keyword] = keyword_data.get('frequency', 1)
        
        # Create merged results
        merged_keywords = []
        for i, (keyword, score) in enumerate(
            sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        ):
            merged_keywords.append({
                'keyword': keyword,
                'score': score,
                'method': keyword_methods[keyword],
                'position': i + 1,
                'frequency': keyword_frequencies[keyword],
                'length': len(keyword.split()),
                'sections_found': len([
                    section for section, keywords in keyword_results.items()
                    if any(k['keyword'] == keyword for k in keywords)
                ])
            })
        
        return merged_keywords


def extract_video_keywords(video_data, 
                          methods: Optional[List[str]] = None,
                          top_k: int = 20) -> List[Dict]:
    """
    Convenience function to extract keywords from video data.
    
    Args:
        video_data: VideoData object
        methods: Extraction methods to use
        top_k: Number of keywords to return
        
    Returns:
        List of keyword dictionaries
    """
    extractor = TikTokKeywordExtractor(methods=methods)
    keyword_results = extractor.extract_content_keywords(video_data, top_k)
    return extractor.merge_keyword_scores(keyword_results)[:top_k]