"""
Keyword extraction methods optimized for TikTok content analysis.

This module implements various keyword extraction algorithms (RAKE, TextRank, TF-IDF, YAKE)
optimized for social media content, particularly TikTok posts with short text and informal language.
"""

import re
import math
import string
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Set, Optional, Union
from dataclasses import dataclass
import networkx as nx
import numpy as np
from pathlib import Path
import logging

from ..stopwords.comprehensive_stopwords import TikTokStopwordManager

logger = logging.getLogger(__name__)

@dataclass
class ExtractedKeyword:
    """Represents an extracted keyword with its score and metadata."""
    keyword: str
    score: float
    method: str
    position: Optional[int] = None
    frequency: Optional[int] = None
    length: Optional[int] = None


class BaseKeywordExtractor:
    """Base class for keyword extractors."""
    
    def __init__(self, stopword_manager: Optional[TikTokStopwordManager] = None,
                 stopword_tier: str = "extended"):
        """
        Initialize the base extractor.
        
        Args:
            stopword_manager: Custom stopword manager
            stopword_tier: Tier of stopwords to use
        """
        self.stopword_manager = stopword_manager or TikTokStopwordManager()
        self.stopword_tier = stopword_tier
        self.stopwords = self.stopword_manager.get_comprehensive_stopwords(stopword_tier)
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for keyword extraction.
        
        Args:
            text: Raw text to preprocess
            
        Returns:
            Cleaned and preprocessed text
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove mentions (@username)
        text = re.sub(r'@\w+', '', text)
        
        # Handle hashtags - remove # but keep the word
        text = re.sub(r'#(\w+)', r'\1', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        # Simple word tokenization
        tokens = re.findall(r'\b\w+\b', text)
        
        # Filter out very short tokens and numbers-only tokens
        tokens = [token for token in tokens 
                 if len(token) > 2 and not token.isdigit()]
        
        return tokens
    
    def is_stopword(self, word: str) -> bool:
        """Check if a word is a stopword."""
        return word.lower() in self.stopwords
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[ExtractedKeyword]:
        """
        Extract keywords from text. To be implemented by subclasses.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            
        Returns:
            List of extracted keywords
        """
        raise NotImplementedError("Subclasses must implement extract_keywords")


class RAKEExtractor(BaseKeywordExtractor):
    """
    RAKE (Rapid Automatic Keyword Extraction) implementation.
    
    Optimized for extracting key phrases from social media content.
    """
    
    def __init__(self, stopword_manager: Optional[TikTokStopwordManager] = None,
                 stopword_tier: str = "extended",
                 phrase_delimiters: Optional[Set[str]] = None):
        """
        Initialize RAKE extractor.
        
        Args:
            stopword_manager: Custom stopword manager
            stopword_tier: Tier of stopwords to use
            phrase_delimiters: Custom phrase delimiters
        """
        super().__init__(stopword_manager, stopword_tier)
        
        # Default phrase delimiters including social media specific ones
        self.phrase_delimiters = phrase_delimiters or {
            '.', '!', '?', ';', ':', ',', '"', "'", '(', ')', '[', ']', 
            '{', '}', '|', '\\', '/', '-', '_', '+', '=', '*', '&', '%',
            '$', '#', '@', '^', '~', '`', '<', '>', '\n', '\t'
        }
    
    def extract_candidate_phrases(self, text: str) -> List[str]:
        """
        Extract candidate phrases by splitting on delimiters and stopwords.
        
        Args:
            text: Text to extract phrases from
            
        Returns:
            List of candidate phrases
        """
        # Split on phrase delimiters
        for delimiter in self.phrase_delimiters:
            text = text.replace(delimiter, ' ')
        
        # Split into words and remove stopwords
        words = self.tokenize(text)
        
        # Group consecutive non-stopwords into phrases
        phrases = []
        current_phrase = []
        
        for word in words:
            if self.is_stopword(word):
                if current_phrase:
                    phrases.append(' '.join(current_phrase))
                    current_phrase = []
            else:
                current_phrase.append(word)
        
        # Add final phrase if exists
        if current_phrase:
            phrases.append(' '.join(current_phrase))
        
        return [phrase for phrase in phrases if phrase.strip()]
    
    def calculate_word_scores(self, phrases: List[str]) -> Dict[str, float]:
        """
        Calculate word scores based on frequency and degree.
        
        Args:
            phrases: List of candidate phrases
            
        Returns:
            Dictionary mapping words to their scores
        """
        word_freq = Counter()
        word_degree = defaultdict(int)
        
        # Calculate frequency and degree for each word
        for phrase in phrases:
            words = phrase.split()
            word_list_length = len(words)
            word_freq.update(words)
            
            for word in words:
                word_degree[word] += word_list_length - 1
        
        # Calculate word scores (degree + frequency) / frequency
        word_scores = {}
        for word in word_freq:
            word_scores[word] = (word_degree[word] + word_freq[word]) / word_freq[word]
        
        return word_scores
    
    def calculate_phrase_scores(self, phrases: List[str], 
                              word_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate phrase scores by summing word scores.
        
        Args:
            phrases: List of candidate phrases
            word_scores: Dictionary of word scores
            
        Returns:
            Dictionary mapping phrases to their scores
        """
        phrase_scores = {}
        
        for phrase in phrases:
            words = phrase.split()
            score = sum(word_scores.get(word, 0) for word in words)
            phrase_scores[phrase] = score
        
        return phrase_scores
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[ExtractedKeyword]:
        """
        Extract keywords using RAKE algorithm.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            
        Returns:
            List of extracted keywords
        """
        # Preprocess text
        processed_text = self.preprocess_text(text)
        
        # Extract candidate phrases
        phrases = self.extract_candidate_phrases(processed_text)
        
        if not phrases:
            return []
        
        # Calculate word scores
        word_scores = self.calculate_word_scores(phrases)
        
        # Calculate phrase scores
        phrase_scores = self.calculate_phrase_scores(phrases, word_scores)
        
        # Sort phrases by score and return top-k
        sorted_phrases = sorted(phrase_scores.items(), 
                              key=lambda x: x[1], reverse=True)
        
        results = []
        for i, (phrase, score) in enumerate(sorted_phrases[:top_k]):
            results.append(ExtractedKeyword(
                keyword=phrase,
                score=score,
                method="RAKE",
                position=i + 1,
                length=len(phrase.split())
            ))
        
        return results


class TextRankExtractor(BaseKeywordExtractor):
    """
    TextRank implementation for keyword extraction.
    
    Uses graph-based ranking to identify important words based on co-occurrence.
    """
    
    def __init__(self, stopword_manager: Optional[TikTokStopwordManager] = None,
                 stopword_tier: str = "extended",
                 window_size: int = 4,
                 damping: float = 0.85,
                 iterations: int = 30):
        """
        Initialize TextRank extractor.
        
        Args:
            stopword_manager: Custom stopword manager
            stopword_tier: Tier of stopwords to use
            window_size: Size of sliding window for co-occurrence
            damping: Damping factor for PageRank
            iterations: Number of iterations for convergence
        """
        super().__init__(stopword_manager, stopword_tier)
        self.window_size = window_size
        self.damping = damping
        self.iterations = iterations
    
    def build_word_graph(self, tokens: List[str]) -> nx.Graph:
        """
        Build a graph of word co-occurrences.
        
        Args:
            tokens: List of tokens
            
        Returns:
            NetworkX graph of word relationships
        """
        # Filter stopwords
        filtered_tokens = [token for token in tokens if not self.is_stopword(token)]
        
        # Build co-occurrence graph
        graph = nx.Graph()
        
        # Add nodes
        for token in set(filtered_tokens):
            graph.add_node(token)
        
        # Add edges based on co-occurrence within window
        for i, token in enumerate(filtered_tokens):
            start = max(0, i - self.window_size // 2)
            end = min(len(filtered_tokens), i + self.window_size // 2 + 1)
            
            for j in range(start, end):
                if i != j and filtered_tokens[j] != token:
                    if graph.has_edge(token, filtered_tokens[j]):
                        graph[token][filtered_tokens[j]]['weight'] += 1
                    else:
                        graph.add_edge(token, filtered_tokens[j], weight=1)
        
        return graph
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[ExtractedKeyword]:
        """
        Extract keywords using TextRank algorithm.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            
        Returns:
            List of extracted keywords
        """
        # Preprocess and tokenize
        processed_text = self.preprocess_text(text)
        tokens = self.tokenize(processed_text)
        
        if not tokens:
            return []
        
        # Build word graph
        graph = self.build_word_graph(tokens)
        
        if not graph.nodes():
            return []
        
        # Calculate TextRank scores
        try:
            scores = nx.pagerank(graph, alpha=self.damping, max_iter=self.iterations)
        except:
            # Fallback to degree centrality if PageRank fails
            scores = nx.degree_centrality(graph)
        
        # Sort by score and return top-k
        sorted_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for i, (word, score) in enumerate(sorted_words[:top_k]):
            results.append(ExtractedKeyword(
                keyword=word,
                score=score,
                method="TextRank",
                position=i + 1,
                frequency=tokens.count(word)
            ))
        
        return results


class TFIDFExtractor(BaseKeywordExtractor):
    """
    TF-IDF based keyword extraction.
    
    Adapted for single document analysis with pseudo-IDF calculation.
    """
    
    def __init__(self, stopword_manager: Optional[TikTokStopwordManager] = None,
                 stopword_tier: str = "extended",
                 min_word_length: int = 3):
        """
        Initialize TF-IDF extractor.
        
        Args:
            stopword_manager: Custom stopword manager
            stopword_tier: Tier of stopwords to use
            min_word_length: Minimum word length to consider
        """
        super().__init__(stopword_manager, stopword_tier)
        self.min_word_length = min_word_length
    
    def calculate_tf(self, tokens: List[str]) -> Dict[str, float]:
        """
        Calculate term frequency.
        
        Args:
            tokens: List of tokens
            
        Returns:
            Dictionary mapping terms to their TF scores
        """
        word_count = len(tokens)
        word_freq = Counter(tokens)
        
        tf_scores = {}
        for word, freq in word_freq.items():
            tf_scores[word] = freq / word_count
        
        return tf_scores
    
    def calculate_pseudo_idf(self, tokens: List[str]) -> Dict[str, float]:
        """
        Calculate pseudo-IDF for single document.
        
        Uses sentence-level distribution as pseudo-documents.
        
        Args:
            tokens: List of tokens
            
        Returns:
            Dictionary mapping terms to their pseudo-IDF scores
        """
        # Split into sentences as pseudo-documents
        text = ' '.join(tokens)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) < 2:
            # Fallback: use word position distribution
            word_positions = defaultdict(list)
            for i, token in enumerate(tokens):
                word_positions[token].append(i)
            
            # Calculate spread as inverse concentration
            idf_scores = {}
            for word, positions in word_positions.items():
                if len(positions) > 1:
                    spread = max(positions) - min(positions)
                    concentration = len(positions) / (spread + 1)
                    idf_scores[word] = math.log(1 / (concentration + 0.001))
                else:
                    idf_scores[word] = 0.0
            
            return idf_scores
        
        # Calculate IDF based on sentence distribution
        word_in_sentences = defaultdict(int)
        for sentence in sentences:
            sentence_words = set(self.tokenize(sentence))
            for word in sentence_words:
                word_in_sentences[word] += 1
        
        total_sentences = len(sentences)
        idf_scores = {}
        for word, doc_freq in word_in_sentences.items():
            idf_scores[word] = math.log(total_sentences / (doc_freq + 1))
        
        return idf_scores
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[ExtractedKeyword]:
        """
        Extract keywords using TF-IDF scores.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            
        Returns:
            List of extracted keywords
        """
        # Preprocess and tokenize
        processed_text = self.preprocess_text(text)
        tokens = self.tokenize(processed_text)
        
        # Filter tokens
        filtered_tokens = [
            token for token in tokens 
            if not self.is_stopword(token) and len(token) >= self.min_word_length
        ]
        
        if not filtered_tokens:
            return []
        
        # Calculate TF and pseudo-IDF
        tf_scores = self.calculate_tf(filtered_tokens)
        idf_scores = self.calculate_pseudo_idf(filtered_tokens)
        
        # Calculate TF-IDF scores
        tfidf_scores = {}
        for word in set(filtered_tokens):
            tfidf_scores[word] = tf_scores[word] * idf_scores.get(word, 0)
        
        # Sort by score and return top-k
        sorted_words = sorted(tfidf_scores.items(), 
                            key=lambda x: x[1], reverse=True)
        
        results = []
        for i, (word, score) in enumerate(sorted_words[:top_k]):
            results.append(ExtractedKeyword(
                keyword=word,
                score=score,
                method="TF-IDF",
                position=i + 1,
                frequency=filtered_tokens.count(word)
            ))
        
        return results


class YAKEExtractor(BaseKeywordExtractor):
    """
    YAKE (Yet Another Keyword Extractor) implementation.
    
    Optimized for single document keyword extraction without corpus dependency.
    """
    
    def __init__(self, stopword_manager: Optional[TikTokStopwordManager] = None,
                 stopword_tier: str = "extended",
                 ngram_size: int = 3,
                 deduplication_threshold: float = 0.9):
        """
        Initialize YAKE extractor.
        
        Args:
            stopword_manager: Custom stopword manager
            stopword_tier: Tier of stopwords to use
            ngram_size: Maximum n-gram size to consider
            deduplication_threshold: Threshold for deduplication
        """
        super().__init__(stopword_manager, stopword_tier)
        self.ngram_size = ngram_size
        self.deduplication_threshold = deduplication_threshold
    
    def calculate_word_features(self, tokens: List[str]) -> Dict[str, Dict]:
        """
        Calculate YAKE word features.
        
        Args:
            tokens: List of tokens
            
        Returns:
            Dictionary mapping words to their feature dictionaries
        """
        word_features = defaultdict(lambda: {
            'freq': 0,
            'positions': [],
            'left_context': [],
            'right_context': []
        })
        
        for i, token in enumerate(tokens):
            if not self.is_stopword(token):
                word_features[token]['freq'] += 1
                word_features[token]['positions'].append(i)
                
                # Context information
                if i > 0:
                    word_features[token]['left_context'].append(tokens[i-1])
                if i < len(tokens) - 1:
                    word_features[token]['right_context'].append(tokens[i+1])
        
        return dict(word_features)
    
    def calculate_yake_score(self, word: str, features: Dict, 
                           total_tokens: int) -> float:
        """
        Calculate YAKE score for a word.
        
        Args:
            word: Word to score
            features: Word features dictionary
            total_tokens: Total number of tokens
            
        Returns:
            YAKE score (lower is better)
        """
        # Relatedness to left context
        left_context = features.get('left_context', [])
        left_relatedness = len(set(left_context)) / (len(left_context) + 1)
        
        # Relatedness to right context  
        right_context = features.get('right_context', [])
        right_relatedness = len(set(right_context)) / (len(right_context) + 1)
        
        # Position-based score (earlier positions are better)
        positions = features.get('positions', [])
        if positions:
            position_score = sum(1 / (pos + 1) for pos in positions) / len(positions)
        else:
            position_score = 0
        
        # Frequency normalization
        freq = features.get('freq', 0)
        freq_score = freq / total_tokens
        
        # Different case occurrence
        case_score = 1.0  # Simplified for this implementation
        
        # Calculate final YAKE score
        yake_score = (left_relatedness + right_relatedness) / (case_score + 
                     (freq_score / left_relatedness) + (freq_score / right_relatedness))
        
        return yake_score
    
    def generate_ngrams(self, tokens: List[str]) -> List[Tuple[str, List[int]]]:
        """
        Generate n-grams with their positions.
        
        Args:
            tokens: List of tokens
            
        Returns:
            List of (ngram, positions) tuples
        """
        ngrams = []
        
        for n in range(1, min(self.ngram_size + 1, len(tokens) + 1)):
            for i in range(len(tokens) - n + 1):
                ngram_tokens = tokens[i:i+n]
                
                # Skip if contains stopwords (except for unigrams)
                if n > 1 and any(self.is_stopword(token) for token in ngram_tokens):
                    continue
                
                ngram = ' '.join(ngram_tokens)
                ngrams.append((ngram, list(range(i, i+n))))
        
        return ngrams
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[ExtractedKeyword]:
        """
        Extract keywords using YAKE algorithm.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            
        Returns:
            List of extracted keywords
        """
        # Preprocess and tokenize
        processed_text = self.preprocess_text(text)
        tokens = self.tokenize(processed_text)
        
        if not tokens:
            return []
        
        # Calculate word features
        word_features = self.calculate_word_features(tokens)
        
        # Generate n-grams
        ngrams = self.generate_ngrams(tokens)
        
        # Calculate scores for each n-gram
        ngram_scores = {}
        for ngram, positions in ngrams:
            words = ngram.split()
            
            if len(words) == 1:
                # Unigram score
                if words[0] in word_features:
                    score = self.calculate_yake_score(words[0], word_features[words[0]], len(tokens))
                    ngram_scores[ngram] = score
            else:
                # Multi-word score (product of individual word scores)
                word_scores = []
                for word in words:
                    if word in word_features:
                        word_score = self.calculate_yake_score(word, word_features[word], len(tokens))
                        word_scores.append(word_score)
                
                if word_scores:
                    # Geometric mean of word scores
                    ngram_scores[ngram] = np.prod(word_scores) ** (1.0 / len(word_scores))
        
        # Sort by score (lower is better for YAKE)
        sorted_ngrams = sorted(ngram_scores.items(), key=lambda x: x[1])
        
        results = []
        for i, (ngram, score) in enumerate(sorted_ngrams[:top_k]):
            results.append(ExtractedKeyword(
                keyword=ngram,
                score=1.0 / (score + 0.001),  # Convert to higher-is-better
                method="YAKE",
                position=i + 1,
                length=len(ngram.split())
            ))
        
        return results


class MultiMethodExtractor:
    """
    Combines multiple keyword extraction methods for robust results.
    """
    
    def __init__(self, methods: Optional[List[str]] = None,
                 stopword_manager: Optional[TikTokStopwordManager] = None,
                 stopword_tier: str = "extended"):
        """
        Initialize multi-method extractor.
        
        Args:
            methods: List of methods to use ('rake', 'textrank', 'tfidf', 'yake')
            stopword_manager: Custom stopword manager
            stopword_tier: Tier of stopwords to use
        """
        self.methods = methods or ['rake', 'textrank', 'yake']
        self.stopword_manager = stopword_manager or TikTokStopwordManager()
        self.stopword_tier = stopword_tier
        
        # Initialize extractors
        self.extractors = {}
        if 'rake' in self.methods:
            self.extractors['rake'] = RAKEExtractor(stopword_manager, stopword_tier)
        if 'textrank' in self.methods:
            self.extractors['textrank'] = TextRankExtractor(stopword_manager, stopword_tier)
        if 'tfidf' in self.methods:
            self.extractors['tfidf'] = TFIDFExtractor(stopword_manager, stopword_tier)
        if 'yake' in self.methods:
            self.extractors['yake'] = YAKEExtractor(stopword_manager, stopword_tier)
    
    def extract_keywords(self, text: str, top_k: int = 10, 
                        fusion_method: str = "rank_fusion") -> List[ExtractedKeyword]:
        """
        Extract keywords using multiple methods and fuse results.
        
        Args:
            text: Text to extract keywords from
            top_k: Number of top keywords to return
            fusion_method: Method for fusing results ('rank_fusion', 'score_fusion')
            
        Returns:
            List of fused extracted keywords
        """
        # Extract keywords with each method
        all_results = {}
        for method_name, extractor in self.extractors.items():
            try:
                results = extractor.extract_keywords(text, top_k * 2)  # Extract more for fusion
                all_results[method_name] = results
            except Exception as e:
                logger.warning(f"Error in {method_name} extraction: {e}")
                all_results[method_name] = []
        
        if not all_results:
            return []
        
        # Fuse results
        if fusion_method == "rank_fusion":
            return self._rank_fusion(all_results, top_k)
        elif fusion_method == "score_fusion":
            return self._score_fusion(all_results, top_k)
        else:
            raise ValueError("fusion_method must be 'rank_fusion' or 'score_fusion'")
    
    def _rank_fusion(self, all_results: Dict[str, List[ExtractedKeyword]], 
                    top_k: int) -> List[ExtractedKeyword]:
        """
        Fuse results using rank-based fusion.
        
        Args:
            all_results: Dictionary of method results
            top_k: Number of keywords to return
            
        Returns:
            List of fused keywords
        """
        keyword_ranks = defaultdict(list)
        
        # Collect ranks for each keyword
        for method_name, results in all_results.items():
            for i, result in enumerate(results):
                keyword_ranks[result.keyword].append(i + 1)
        
        # Calculate reciprocal rank fusion scores
        fused_scores = {}
        for keyword, ranks in keyword_ranks.items():
            score = sum(1.0 / (rank + 60) for rank in ranks)  # RRF with k=60
            fused_scores[keyword] = score
        
        # Sort and return top-k
        sorted_keywords = sorted(fused_scores.items(), 
                               key=lambda x: x[1], reverse=True)
        
        results = []
        for i, (keyword, score) in enumerate(sorted_keywords[:top_k]):
            results.append(ExtractedKeyword(
                keyword=keyword,
                score=score,
                method="MultiMethod",
                position=i + 1
            ))
        
        return results
    
    def _score_fusion(self, all_results: Dict[str, List[ExtractedKeyword]], 
                     top_k: int) -> List[ExtractedKeyword]:
        """
        Fuse results using score-based fusion.
        
        Args:
            all_results: Dictionary of method results
            top_k: Number of keywords to return
            
        Returns:
            List of fused keywords
        """
        # Normalize scores within each method
        normalized_results = {}
        for method_name, results in all_results.items():
            if not results:
                continue
            
            scores = [r.score for r in results]
            if max(scores) > min(scores):
                min_score, max_score = min(scores), max(scores)
                normalized = []
                for result in results:
                    normalized_score = (result.score - min_score) / (max_score - min_score)
                    normalized_result = ExtractedKeyword(
                        keyword=result.keyword,
                        score=normalized_score,
                        method=result.method,
                        position=result.position
                    )
                    normalized.append(normalized_result)
                normalized_results[method_name] = normalized
            else:
                normalized_results[method_name] = results
        
        # Aggregate normalized scores
        keyword_scores = defaultdict(list)
        for method_name, results in normalized_results.items():
            for result in results:
                keyword_scores[result.keyword].append(result.score)
        
        # Calculate mean scores
        fused_scores = {}
        for keyword, scores in keyword_scores.items():
            fused_scores[keyword] = np.mean(scores)
        
        # Sort and return top-k
        sorted_keywords = sorted(fused_scores.items(), 
                               key=lambda x: x[1], reverse=True)
        
        results = []
        for i, (keyword, score) in enumerate(sorted_keywords[:top_k]):
            results.append(ExtractedKeyword(
                keyword=keyword,
                score=score,
                method="MultiMethod",
                position=i + 1
            ))
        
        return results