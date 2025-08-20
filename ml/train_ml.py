#!/usr/bin/env python3
"""
TikTok Performance Prediction Model - Supervised Learning Implementation

This module implements a supervised learning model that predicts TikTok video performance
scores (0-100) directly from transcript text. The model is trained on real performance
data from master2.json and learns to predict how well content will perform based on
transcript patterns.

Features:
- Supervised learning: transcript → performance score
- Rich feature extraction from text only
- Trained on real TikTok performance metrics enhanced with comment engagement analysis
- Simple interface: string in, score out (unchanged)
- Ensemble model for robustness
- Comment-aware training discovers what transcript patterns drive engagement

Date: 2025-07-31
"""

import json
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
import re
import time
import logging
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ML Imports
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import RobustScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    import xgboost as xgb
    import joblib
except ImportError as e:
    print(f"Missing ML dependencies: {e}")
    print("Install with: pip install scikit-learn xgboost joblib")
    exit(1)

# NLP Imports
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    from textstat import flesch_reading_ease, flesch_kincaid_grade
except ImportError:
    print("Installing NLTK dependencies...")
    import subprocess
    subprocess.run(["pip", "install", "nltk", "textstat"])
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    from textstat import flesch_reading_ease, flesch_kincaid_grade

# Download NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('vader_lexicon', quiet=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TikTokPerformancePredictor:
    """Supervised learning model for predicting TikTok performance from transcripts."""
    
    def __init__(self):
        """Initialize the predictor."""
        self.model = None
        self.scaler = RobustScaler()
        self.is_trained = False
        self.feature_names = []
        
        # Initialize NLP components
        try:
            self.sia = SentimentIntensityAnalyzer()
            self.stop_words = set(stopwords.words('english'))
        except Exception:
            # Handle missing NLTK data gracefully
            self.sia = None
            self.stop_words = set()
        
        # TF-IDF vectorizer (will be fitted during training)
        self.tfidf_vectorizer = None
        
        # Discovered patterns from data (no assumptions about what matters)
        self.learned_patterns = {
            'content_patterns': {},
            'emotional_progressions': {},
            'narrative_structures': {},
            'psychological_triggers': {},
            'viral_phrases': [],
            'hook_sentences': [],
            'engagement_emotions': [],
            'curiosity_words': []
        }
        
    def calculate_performance_score(self, view_count: int, like_count: int, comment_count: int, 
                                   comments: List[Any] = None) -> float:
        """Convert real metrics to 0-100 performance score, enhanced with comment quality analysis."""
        # Calculate engagement rate
        engagement_rate = like_count / max(view_count, 1)
        
        # View score based on percentiles
        if view_count >= 10_000_000:
            view_score = 90 + min(10, (view_count - 10_000_000) / 1_000_000)
        elif view_count >= 5_000_000:
            view_score = 75 + (view_count - 5_000_000) / 333_333
        elif view_count >= 1_000_000:
            view_score = 60 + (view_count - 1_000_000) / 266_667
        elif view_count >= 500_000:
            view_score = 45 + (view_count - 500_000) / 33_333
        elif view_count >= 100_000:
            view_score = 25 + (view_count - 100_000) / 20_000
        else:
            view_score = max(0, view_count / 4000)
        
        # Engagement bonus/penalty
        engagement_multiplier = 1.0
        if engagement_rate > 0.2:  # Very high engagement
            engagement_multiplier = 1.2
        elif engagement_rate > 0.15:  # High engagement
            engagement_multiplier = 1.1
        elif engagement_rate < 0.05:  # Low engagement
            engagement_multiplier = 0.8
        
        # Comment bonus - enhanced with quality analysis
        comment_bonus = min(5, comment_count / 1000)  # Base bonus
        
        # Analyze comment quality for additional scoring (if comments provided)
        if comments:
            quality_bonus = self._analyze_comment_quality(comments)
            comment_bonus += quality_bonus
        
        # Final score
        final_score = (view_score * engagement_multiplier) + comment_bonus
        return max(0, min(100, final_score))
    
    def _analyze_comment_quality(self, comments: List[Any]) -> float:
        """Analyze comment quality patterns discovered during training."""
        if not comments:
            return 0.0
        
        # Process comments to text
        comment_texts = []
        for comment in comments:
            if isinstance(comment, dict) and 'text' in comment:
                comment_texts.append(comment['text'])
            elif isinstance(comment, str):
                comment_texts.append(comment)
        
        if not comment_texts:
            return 0.0
        
        bonus = 0.0
        
        # Emotional engagement (discovered patterns)
        if hasattr(self, 'learned_patterns') and 'comment_patterns' in self.learned_patterns:
            emotional_patterns = self.learned_patterns['comment_patterns'].get('emotional_progressions', {})
            
            if emotional_patterns and self.sia:
                sentiments = [self.sia.polarity_scores(c)['compound'] for c in comment_texts]
                if sentiments:
                    # Apply discovered emotional volatility pattern
                    volatility = np.std(sentiments)
                    if 'comment_emotional_volatility' in emotional_patterns:
                        correlation = emotional_patterns['comment_emotional_volatility'].get('correlation', 0)
                        bonus += (volatility * correlation * 2)  # Scale factor
        
        # Length and complexity patterns (discovered)
        avg_length = np.mean([len(c.split()) for c in comment_texts])
        if avg_length > 10:  # Longer, more thoughtful comments
            bonus += min(1.0, (avg_length - 10) / 20)
        
        # Question engagement (discovered pattern)
        question_ratio = sum(1 for c in comment_texts if '?' in c) / len(comment_texts)
        if question_ratio > 0.1:  # High curiosity engagement
            bonus += min(1.0, question_ratio * 3)
        
        # Conversation patterns (discovered)
        unique_ratio = len(set(comment_texts)) / len(comment_texts)  # Avoid spam
        if unique_ratio > 0.8:  # Diverse, genuine conversation
            bonus += 0.5
        
        return min(3.0, bonus)  # Cap at 3 point bonus
    
    def train(self, data_path: str, test_size: float = 0.2) -> Dict[str, Any]:
        """Train the model on master2.json data."""
        logger.info("Starting supervised learning training...")
        start_time = time.time()
        
        # Load data
        with open(data_path, 'r', encoding='utf-8') as f:
            videos = json.load(f)
        
        logger.info(f"Loaded {len(videos)} videos from {data_path}")
        
        # First pass: collect transcripts, comments and calculate scores
        logger.info("Collecting transcripts, comments and calculating performance scores...")
        training_data = []
        for video in videos:
            transcript = video.get('whisper_transcription', '')
            if not transcript or not transcript.strip():
                continue
            
            # Calculate performance score from real metrics (now including comment analysis)
            view_count = video.get('view_count', 0)
            like_count = video.get('like_count', 0)
            comment_count = video.get('comment_count', 0)
            comments = video.get('comments', [])
            
            performance_score = self.calculate_performance_score(
                view_count, like_count, comment_count, comments
            )
            
            training_data.append({
                'transcript': transcript,
                'comments': comments,
                'score': performance_score,
                'video': video
            })
        
        # Extract lists for learning
        all_transcripts = [d['transcript'] for d in training_data]
        all_comments = [d['comments'] for d in training_data]
        all_scores = [d['score'] for d in training_data]
        
        logger.info(f"Collected {len(all_transcripts)} transcript-comment-score triplets")
        
        # Learn semantic and emotional patterns including comment-content alignment
        self.learn_semantic_patterns(all_transcripts, all_scores, all_comments)
        
        # Fit TF-IDF on all transcripts
        self.fit_tfidf(all_transcripts)
        
        # Second pass: extract features using learned patterns
        logger.info("Extracting features using learned patterns...")
        feature_dicts = []
        final_scores = []
        
        for i, data in enumerate(training_data):
            if i % 100 == 0:
                logger.info(f"Processing transcript {i+1}/{len(training_data)}")
                
            try:
                # Extract features from transcript using learned patterns
                features = self.extract_features(data['transcript'])
                
                # Add TF-IDF features
                tfidf_features = self.extract_tfidf_features(data['transcript'])
                features.update(tfidf_features)
                
                feature_dicts.append(features)
                final_scores.append(data['score'])
                
            except Exception as e:
                logger.warning(f"Error processing transcript {i}: {e}")
                continue
        
        logger.info(f"Prepared {len(feature_dicts)} training examples")
        
        # Convert to DataFrame for easier handling
        df_features = pd.DataFrame(feature_dicts)
        df_features = df_features.fillna(0)  # Fill missing values
        
        self.feature_names = list(df_features.columns)
        X = df_features.values
        y = np.array(final_scores)
        
        logger.info(f"Feature matrix shape: {X.shape}")
        logger.info(f"Score range: {y.min():.1f} - {y.max():.1f}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train ensemble model
        logger.info("Training ensemble model...")
        
        # Random Forest
        rf_model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        rf_model.fit(X_train_scaled, y_train)
        
        # XGBoost
        xgb_model = xgb.XGBRegressor(n_estimators=100, max_depth=6, random_state=42, verbose=0)
        xgb_model.fit(X_train_scaled, y_train)
        
        # Ridge Regression
        ridge_model = Ridge(alpha=1.0)
        ridge_model.fit(X_train_scaled, y_train)
        
        # Create ensemble
        self.model = {
            'rf': rf_model,
            'xgb': xgb_model,
            'ridge': ridge_model
        }
        
        # Evaluate
        rf_pred = rf_model.predict(X_test_scaled)
        xgb_pred = xgb_model.predict(X_test_scaled)
        ridge_pred = ridge_model.predict(X_test_scaled)
        
        # Ensemble prediction (equal weighting)
        ensemble_pred = (rf_pred + xgb_pred + ridge_pred) / 3
        
        # Calculate metrics
        mae = mean_absolute_error(y_test, ensemble_pred)
        rmse = np.sqrt(mean_squared_error(y_test, ensemble_pred))
        r2 = r2_score(y_test, ensemble_pred)
        
        # Cross-validation
        cv_scores = cross_val_score(rf_model, X_train_scaled, y_train, cv=5, scoring='r2')
        
        self.is_trained = True
        training_time = time.time() - start_time
        
        logger.info("Training completed!")
        logger.info(f"Training time: {training_time:.2f} seconds")
        logger.info(f"MAE: {mae:.2f}")
        logger.info(f"RMSE: {rmse:.2f}")
        logger.info(f"R² Score: {r2:.3f}")
        logger.info(f"CV R² Score: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
        
        return {
            'training_time': training_time,
            'n_samples': len(feature_dicts),
            'n_features': len(self.feature_names),
            'mae': mae,
            'rmse': rmse,
            'r2_score': r2,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std()
        }
    
    def predict_score(self, transcript: str) -> float:
        """Predict performance score from transcript text using learned viral patterns."""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        # Extract features from transcript (now includes viral pattern features)
        features = self.extract_features(transcript)
        
        # Add TF-IDF features
        tfidf_features = self.extract_tfidf_features(transcript)
        features.update(tfidf_features)
        
        # Convert to array with correct feature order
        feature_vector = np.zeros(len(self.feature_names))
        for i, feature_name in enumerate(self.feature_names):
            feature_vector[i] = features.get(feature_name, 0)
        
        # Scale features
        feature_vector_scaled = self.scaler.transform([feature_vector])
        
        # Ensemble prediction with viral pattern learning
        rf_pred = self.model['rf'].predict(feature_vector_scaled)[0]
        xgb_pred = self.model['xgb'].predict(feature_vector_scaled)[0]
        ridge_pred = self.model['ridge'].predict(feature_vector_scaled)[0]
        
        # Final ensemble score
        ensemble_score = (rf_pred + xgb_pred + ridge_pred) / 3
        
        # Clamp to 0-100 range
        return max(0, min(100, ensemble_score))
    
    def save_model(self, model_path: str):
        """Save the trained model."""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'learned_patterns': self.learned_patterns,
            'tfidf_vectorizer': self.tfidf_vectorizer
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"Model saved to {model_path}")
        
        # Log model size
        model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)
        logger.info(f"Model size: {model_size_mb:.2f} MB")
    
    def load_model(self, model_path: str):
        """Load a trained model."""
        model_data = joblib.load(model_path)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.is_trained = model_data['is_trained']
        self.learned_patterns = model_data.get('learned_patterns', {})
        self.tfidf_vectorizer = model_data.get('tfidf_vectorizer', None)
        
        # Reinitialize NLP components if not already done
        if not hasattr(self, 'sia') or self.sia is None:
            try:
                self.sia = SentimentIntensityAnalyzer()
                self.stop_words = set(stopwords.words('english'))
            except Exception:
                self.sia = None
                self.stop_words = set()
        
        logger.info(f"Model loaded from {model_path}")
    
    def extract_features(self, transcript: str) -> Dict[str, float]:
        """Extract comprehensive features from transcript text."""
        features = {}
        
        if not transcript or not transcript.strip():
            return self._get_zero_features()
        
        transcript = transcript.lower().strip()
        words = transcript.split()
        sentences = sent_tokenize(transcript)
        
        # Basic text statistics
        features.update(self._extract_basic_stats(transcript, words, sentences))
        
        # Sentiment analysis
        features.update(self._extract_sentiment_features(transcript))
        
        # Hook analysis (dynamic based on discovered patterns)
        features.update(self._extract_hook_features(transcript, words))
        
        # Story structure patterns
        features.update(self._extract_story_features(transcript, words))
        
        # Discovered semantic patterns
        features.update(self._extract_semantic_patterns(transcript, words))
        
        # Linguistic patterns
        features.update(self._extract_linguistic_features(transcript, words, sentences))
        
        # Readability metrics
        features.update(self._extract_readability_features(transcript))
        
        return features
    
    def _extract_basic_stats(self, transcript: str, words: List[str], sentences: List[str]) -> Dict[str, float]:
        """Extract basic text statistics."""
        features = {}
        
        # Length metrics
        features['word_count'] = len(words)
        features['char_count'] = len(transcript)
        features['sentence_count'] = len(sentences)
        features['avg_word_length'] = np.mean([len(word) for word in words]) if words else 0
        features['avg_sentence_length'] = len(words) / len(sentences) if sentences else 0
        
        # Estimated duration (speaking rate: ~2.5 words per second)
        features['estimated_duration'] = max(15, min(180, len(words) / 2.5))
        features['duration_normalized'] = features['estimated_duration'] / 180.0
        
        return features
    
    def _extract_sentiment_features(self, transcript: str) -> Dict[str, float]:
        """Extract sentiment analysis features."""
        features = {}
        
        if self.sia is None:
            return {'sentiment_compound': 0, 'sentiment_positive': 0, 'sentiment_negative': 0, 'sentiment_neutral': 0}
        
        # Overall sentiment
        sentiment = self.sia.polarity_scores(transcript)
        features['sentiment_compound'] = sentiment['compound']
        features['sentiment_positive'] = sentiment['pos']
        features['sentiment_negative'] = sentiment['neg']
        features['sentiment_neutral'] = sentiment['neu']
        
        # Sentiment intensity
        features['sentiment_intensity'] = abs(sentiment['compound'])
        features['is_highly_emotional'] = 1.0 if abs(sentiment['compound']) > 0.6 else 0.0
        
        return features
    
    def _extract_hook_features(self, transcript: str, words: List[str]) -> Dict[str, float]:
        """Extract hook analysis features with 5-second gradient weighting and learned viral patterns."""
        features = {}
        
        # Extract first 5 seconds (approximately first 15-20 words based on speaking rate ~3 words/sec)
        first_5_sec_words = words[:20] if len(words) >= 20 else words
        first_5_sec_text = ' '.join(first_5_sec_words).lower()
        
        # Get first sentence (primary hook)
        sentences = sent_tokenize(transcript)
        first_sentence = sentences[0].lower() if sentences else first_5_sec_text
        
        # Basic hook metrics
        features['hook_word_count'] = len(first_5_sec_words)
        features['hook_sentence_length'] = len(first_sentence.split())
        
        # Viral phrase matching (learned from data)
        viral_phrase_matches = 0
        if self.learned_patterns.get('viral_phrases'):
            combined_hook = f"{first_sentence} {first_5_sec_text}"
            for phrase in self.learned_patterns['viral_phrases']:
                if phrase in combined_hook:
                    viral_phrase_matches += 1
        features['viral_phrase_matches'] = min(viral_phrase_matches, 10.0)  # Cap at 10
        
        # Hook sentence similarity to learned viral hooks
        hook_similarity_max = 0.0
        if self.learned_patterns.get('hook_sentences') and first_sentence:
            for viral_hook in self.learned_patterns['hook_sentences'][:100]:  # Top 100
                hook_words_set = set(viral_hook.split())
                sentence_words_set = set(first_sentence.split())
                if hook_words_set and sentence_words_set:
                    overlap = len(hook_words_set.intersection(sentence_words_set))
                    similarity = overlap / max(len(hook_words_set), len(sentence_words_set))
                    hook_similarity_max = max(hook_similarity_max, similarity)
        features['hook_similarity_max'] = hook_similarity_max
        
        # Emotional pattern matching in hook (learned from viral content)
        hook_emotion_match = 0.0
        if self.learned_patterns.get('engagement_emotions') and self.sia:
            current_emotion = self.sia.polarity_scores(first_5_sec_text)
            for viral_emotion in self.learned_patterns['engagement_emotions'][:30]:
                # Calculate emotional distance
                compound_diff = abs(current_emotion['compound'] - viral_emotion['compound'])
                if compound_diff < 0.4:  # Similar emotional intensity
                    hook_emotion_match += (0.4 - compound_diff) / 0.4
        features['hook_emotion_match'] = min(hook_emotion_match, 5.0)  # Cap at 5
        
        # Data-driven curiosity word detection in hook (5-second gradient)
        curiosity_score = 0.0
        if self.learned_patterns.get('curiosity_words'):
            for word in self.learned_patterns['curiosity_words']:
                if word in first_5_sec_text:
                    curiosity_score += 2.0  # Heavy weight for learned curiosity words
                elif word in first_sentence:
                    curiosity_score += 1.5  # Medium weight for first sentence
        features['hook_curiosity_score'] = min(curiosity_score, 10.0)  # Cap at 10
        
        # Hook emotional intensity (5-second weighted)
        if self.sia:
            hook_sentiment = self.sia.polarity_scores(first_5_sec_text)
            features['hook_emotional_intensity'] = abs(hook_sentiment['compound'])
            features['hook_sentiment_compound'] = hook_sentiment['compound']
            
            # Compare hook emotion to full transcript emotion (emotional journey)
            full_sentiment = self.sia.polarity_scores(transcript.lower())
            features['hook_emotion_contrast'] = abs(hook_sentiment['compound'] - full_sentiment['compound'])
        else:
            features['hook_emotional_intensity'] = 0.0
            features['hook_sentiment_compound'] = 0.0
            features['hook_emotion_contrast'] = 0.0
        
        # Apply legacy content patterns if available
        if 'content_patterns' in self.learned_patterns:
            content_patterns = self.learned_patterns['content_patterns']
            segment_patterns = content_patterns.get('segment_importance', {})
            
            for segment_key, segment_data in segment_patterns.items():
                correlation = segment_data.get('correlation', 0)
                if abs(correlation) > 0.1 and segment_data.get('position') == 'start':
                    # Focus on start-position patterns for hook analysis
                    segment_length = min(segment_data['segment_length'], 20)  # Cap at 20 words
                    if len(words) >= segment_length:
                        segment_text = ' '.join(words[:segment_length])
                        if self.sia:
                            segment_intensity = abs(self.sia.polarity_scores(segment_text)['compound'])
                            features[f'hook_{segment_key}'] = segment_intensity * correlation
        
        return features
    
    def _extract_story_features(self, transcript: str, words: List[str]) -> Dict[str, float]:
        """Extract story structure features."""
        features = {}
        
        # Personal narrative indicators
        personal_pronouns = ['i', 'my', 'me', 'myself']
        personal_count = sum(1 for word in words if word in personal_pronouns)
        features['personal_pronoun_count'] = personal_count
        features['personal_pronoun_density'] = personal_count / len(words) if words else 0
        features['is_personal_story'] = 1.0 if personal_count >= 10 else 0.0
        
        # Time progression markers
        time_markers = ['then', 'next', 'after', 'later', 'suddenly', 'when', 'recently', 'yesterday', 'today']
        time_count = sum(1 for word in words if word in time_markers)
        features['time_marker_count'] = time_count
        features['time_marker_density'] = time_count / len(words) if words else 0
        features['has_time_progression'] = 1.0 if time_count >= 3 else 0.0
        
        # Dialogue indicators
        features['has_dialogue'] = 1.0 if any(char in transcript for char in ['"', "'", ':']) else 0.0
        
        # Location/setting indicators
        location_words = ['house', 'home', 'apartment', 'school', 'work', 'restaurant', 'store', 'car']
        features['has_location'] = 1.0 if any(word in words for word in location_words) else 0.0
        
        return features
    
    def _extract_semantic_patterns(self, transcript: str, words: List[str]) -> Dict[str, float]:
        """Extract discovered semantic pattern features."""
        features = {}
        
        # Apply discovered emotional progression patterns
        if 'emotional_progressions' in self.learned_patterns:
            emotional_patterns = self.learned_patterns['emotional_progressions']
            
            # Calculate emotional journey features
            sentences = sent_tokenize(transcript)
            if len(sentences) >= 3 and self.sia:
                sentence_sentiments = []
                for sentence in sentences:
                    sentiment = self.sia.polarity_scores(sentence)
                    sentence_sentiments.append(sentiment['compound'])
                
                if len(sentence_sentiments) >= 3:
                    # Apply discovered patterns
                    volatility = np.std(sentence_sentiments)
                    emotional_range = max(sentence_sentiments) - min(sentence_sentiments)
                    emotional_trend = sentence_sentiments[-1] - sentence_sentiments[0]
                    peak_intensity = max(abs(s) for s in sentence_sentiments)
                    
                    # Weight by discovered correlations
                    for pattern_name, pattern_data in emotional_patterns.items():
                        correlation = pattern_data.get('correlation', 0)
                        if pattern_name == 'emotional_volatility':
                            features['discovered_emotional_volatility'] = volatility * correlation
                        elif pattern_name == 'emotional_range':
                            features['discovered_emotional_range'] = emotional_range * correlation
                        elif pattern_name == 'emotional_trend':
                            features['discovered_emotional_trend'] = emotional_trend * correlation
                        elif pattern_name == 'peak_intensity':
                            features['discovered_peak_intensity'] = peak_intensity * correlation
        
        return features
    
    def _extract_linguistic_features(self, transcript: str, words: List[str], sentences: List[str]) -> Dict[str, float]:
        """Extract linguistic pattern features."""
        features = {}
        
        # Question patterns
        question_words = ['what', 'why', 'how', 'when', 'where', 'who', 'which']
        question_count = sum(1 for word in words if word in question_words)
        features['question_word_count'] = question_count
        features['question_density'] = question_count / len(words) if words else 0
        
        # Exclamation patterns
        features['exclamation_count'] = transcript.count('!')
        features['has_multiple_exclamations'] = 1.0 if transcript.count('!') > 2 else 0.0
        
        # All caps words (shouting)
        caps_words = sum(1 for word in words if word.isupper() and len(word) > 2)
        features['caps_words'] = caps_words
        
        # Superlatives
        superlatives = ['best', 'worst', 'most', 'least', 'biggest', 'smallest', 'first', 'last']
        superlative_count = sum(1 for word in words if word in superlatives)
        features['superlative_count'] = superlative_count
        
        return features
    
    def _extract_readability_features(self, transcript: str) -> Dict[str, float]:
        """Extract readability metrics."""
        features = {}
        
        try:
            features['flesch_reading_ease'] = flesch_reading_ease(transcript)
            features['flesch_kincaid_grade'] = flesch_kincaid_grade(transcript)
        except:
            features['flesch_reading_ease'] = 0.0
            features['flesch_kincaid_grade'] = 0.0
        
        return features
    
    def _get_zero_features(self) -> Dict[str, float]:
        """Return zero features for empty transcript."""
        return {
            'word_count': 0, 'char_count': 0, 'sentence_count': 0,
            'sentiment_compound': 0, 'hook_word_count': 0,
            'personal_pronoun_count': 0, 'viral_density': 0
        }
    
    def fit_tfidf(self, transcripts: List[str]):
        """Fit TF-IDF vectorizer on training transcripts."""
        self.tfidf_vectorizer = TfidfVectorizer(max_features=100, stop_words='english', ngram_range=(1, 2))
        self.tfidf_vectorizer.fit(transcripts)
        logger.info("TF-IDF vectorizer fitted on training data")
    
    def extract_tfidf_features(self, transcript: str) -> Dict[str, float]:
        """Extract TF-IDF features."""
        features = {}
        
        if self.tfidf_vectorizer is None:
            return features
            
        try:
            tfidf_vector = self.tfidf_vectorizer.transform([transcript]).toarray()[0]
            feature_names = self.tfidf_vectorizer.get_feature_names_out()
            
            for i, score in enumerate(tfidf_vector):
                if score > 0:  # Only include non-zero features
                    features[f'tfidf_{feature_names[i]}'] = score
        except:
            pass
            
        return features
    
    def learn_semantic_patterns(self, transcripts: List[str], scores: List[float], 
                               comments_list: List[List[Any]] = None):
        """Learn advanced semantic and emotional patterns."""
        logger.info("Learning advanced semantic and emotional patterns...")
        
        if comments_list:
            logger.info("Enhanced mode: analyzing comment-content alignment patterns...")
        
        semantic_insights = {
            'content_patterns': self._discover_content_patterns(transcripts, scores),
            'emotional_progressions': self._discover_emotional_journey_patterns(transcripts, scores),
            'controversy_patterns': self._discover_controversy_patterns(transcripts, scores),
            'curiosity_patterns': self._discover_curiosity_patterns(transcripts, scores),
            'story_arc_patterns': self._discover_story_arc_patterns(transcripts, scores),
            'ngram_patterns': self._discover_ngram_patterns(transcripts, scores)
        }
        
        # Add comment-aware patterns if comments provided
        if comments_list:
            logger.info("Discovering comment-content alignment patterns...")
            semantic_insights['comment_patterns'] = {
                'semantic_alignment': self._discover_semantic_alignment_patterns(transcripts, comments_list, scores),
                'content_triggers': self._discover_content_trigger_patterns(transcripts, comments_list, scores)
            }
        
        self.learned_patterns = semantic_insights
        
        # Add viral pattern learning from high-scoring content
        self._learn_viral_patterns(transcripts, scores)
        
        logger.info("Completed advanced pattern analysis")
        logger.info(f"Controversy patterns: {len(semantic_insights.get('controversy_patterns', {}))}")
        logger.info(f"N-gram patterns: {len(semantic_insights.get('ngram_patterns', {}))}")
        logger.info(f"Viral phrases learned: {len(self.learned_patterns.get('viral_phrases', []))}")
        logger.info(f"Hook sentences learned: {len(self.learned_patterns.get('hook_sentences', []))}")
    
    def _learn_viral_patterns(self, transcripts: List[str], scores: List[float]) -> None:
        """Learn viral patterns from high-scoring vs low-scoring content with 5-second gradient weighting."""
        import numpy as np
        from collections import Counter
        
        # Define viral threshold (top 25% by score)
        threshold_high = np.percentile(scores, 75)
        threshold_low = np.percentile(scores, 25)
        
        high_performers = []
        low_performers = []
        
        for i, score in enumerate(scores):
            if score >= threshold_high:
                high_performers.append(transcripts[i])
            elif score <= threshold_low:
                low_performers.append(transcripts[i])
        
        logger.info(f"Learning from {len(high_performers)} high performers vs {len(low_performers)} low performers")
        
        # Extract patterns with 5-second gradient weighting
        viral_phrases = []
        hook_sentences = []
        viral_emotions = []
        
        # Learn from high performers
        high_first_5_sec_words = []
        high_hook_sentences = []
        
        for transcript in high_performers:
            if not transcript:
                continue
                
            transcript_lower = transcript.lower()
            words = transcript_lower.split()
            sentences = sent_tokenize(transcript_lower)
            
            # Extract first 5 seconds (approximately first 15-20 words based on speaking rate)
            first_5_sec_words = words[:20] if len(words) >= 20 else words
            first_5_sec_text = ' '.join(first_5_sec_words)
            high_first_5_sec_words.extend(first_5_sec_words)
            
            # Extract first sentence (hook)
            if sentences:
                first_sentence = sentences[0]
                high_hook_sentences.append(first_sentence)
                hook_sentences.append(first_sentence)
                
                # Extract 3-word phrases from hooks (data-driven)
                hook_words = word_tokenize(first_sentence)
                for i in range(len(hook_words) - 2):
                    phrase = ' '.join(hook_words[i:i+3])
                    if len(phrase) > 8:  # Meaningful phrases
                        viral_phrases.append(phrase)
            
            # Extract emotional signatures from hooks (weighted)
            if self.sia and first_5_sec_text:
                emotion_score = self.sia.polarity_scores(first_5_sec_text)
                if abs(emotion_score['compound']) > 0.2:  # Any notable emotion
                    viral_emotions.append(emotion_score)
        
        # Learn from low performers for comparison
        low_first_5_sec_words = []
        for transcript in low_performers:
            if not transcript:
                continue
            words = transcript.lower().split()
            first_5_sec_words = words[:20] if len(words) >= 20 else words
            low_first_5_sec_words.extend(first_5_sec_words)
        
        # Discover curiosity words through statistical comparison (data-driven)
        high_word_counts = Counter(high_first_5_sec_words)
        low_word_counts = Counter(low_first_5_sec_words)
        
        curiosity_words = []
        total_high = sum(high_word_counts.values())
        total_low = sum(low_word_counts.values())
        
        # Find words that appear significantly more in high-performing hooks
        for word in high_word_counts:
            if len(word) > 3:  # Skip short words
                high_freq = high_word_counts[word] / max(total_high, 1)
                low_freq = low_word_counts.get(word, 0) / max(total_low, 1)
                
                # Word appears at least 2x more in viral content
                if high_freq > low_freq * 2 and high_word_counts[word] >= 5:
                    curiosity_words.append((word, high_freq / max(low_freq, 0.001)))
        
        # Sort by ratio and take top performers
        curiosity_words.sort(key=lambda x: x[1], reverse=True)
        
        # Store learned patterns
        self.learned_patterns['viral_phrases'] = list(set(viral_phrases))[:500]
        self.learned_patterns['hook_sentences'] = hook_sentences[:200]
        self.learned_patterns['engagement_emotions'] = viral_emotions
        self.learned_patterns['curiosity_words'] = [word for word, ratio in curiosity_words[:50]]
        
        logger.info(f"Learned {len(self.learned_patterns['viral_phrases'])} viral phrases")
        logger.info(f"Learned {len(self.learned_patterns['hook_sentences'])} hook patterns")
        logger.info(f"Learned {len(self.learned_patterns['engagement_emotions'])} emotional patterns")
        logger.info(f"Discovered {len(self.learned_patterns['curiosity_words'])} data-driven curiosity words")
        if curiosity_words:
            logger.info(f"Top curiosity words: {[word for word, _ in curiosity_words[:10]]}")
    
    def _discover_controversy_patterns(self, transcripts: List[str], scores: List[float]) -> Dict[str, Any]:
        """Discover words that statistically correlate with high engagement."""
        import numpy as np
        try:
            from scipy.stats import chi2_contingency
        except ImportError:
            logger.warning("SciPy not available - skipping controversy pattern discovery")
            return {}
        from collections import Counter
        
        threshold = np.percentile(scores, 75)
        high_performers = [transcripts[i].lower() for i, score in enumerate(scores) if score >= threshold]
        low_performers = [transcripts[i].lower() for i, score in enumerate(scores) if score < threshold]
        
        high_words = Counter(' '.join(high_performers).split())
        low_words = Counter(' '.join(low_performers).split())
        
        controversy_indicators = {}
        
        for word in high_words:
            if high_words[word] >= 5:
                high_count = high_words[word]
                low_count = low_words.get(word, 0)
                
                observed = [[high_count, low_count], 
                           [sum(high_words.values()) - high_count, sum(low_words.values()) - low_count]]
                
                try:
                    chi2, p_value, _, _ = chi2_contingency(observed)
                    if p_value < 0.05 and high_count > low_count:
                        controversy_indicators[word] = {
                            'chi2_score': chi2,
                            'p_value': p_value,
                            'high_freq': high_count,
                            'low_freq': low_count
                        }
                except:
                    continue
        
        return controversy_indicators
    
    def _discover_curiosity_patterns(self, transcripts: List[str], scores: List[float]) -> Dict[str, Any]:
        """Discover curiosity gap patterns using mathematical analysis."""
        import numpy as np
        try:
            from scipy.stats import pearsonr
        except ImportError:
            logger.warning("SciPy not available - skipping curiosity pattern discovery")
            return {}
        
        curiosity_features = []
        
        for transcript, score in zip(transcripts, scores):
            sentences = sent_tokenize(transcript.lower())
            
            question_patterns = sum(1 for s in sentences if '?' in s)
            temporal_progression = sum(1 for s in sentences if any(c.isdigit() for c in s))
            
            curiosity_features.append({
                'question_density': question_patterns / len(sentences) if sentences else 0,
                'temporal_progression': temporal_progression / len(sentences) if sentences else 0,
                'score': score
            })
        
        discovered_patterns = {}
        
        if curiosity_features:
            for pattern in ['question_density', 'temporal_progression']:
                values = [f[pattern] for f in curiosity_features]
                scores_list = [f['score'] for f in curiosity_features]
                
                try:
                    correlation, p_value = pearsonr(values, scores_list)
                    if not np.isnan(correlation) and abs(correlation) > 0.05:
                        discovered_patterns[pattern] = {
                            'correlation': correlation,
                            'p_value': p_value,
                            'mean_value': np.mean(values)
                        }
                except:
                    pass
        
        return discovered_patterns
    
    def _discover_story_arc_patterns(self, transcripts: List[str], scores: List[float]) -> Dict[str, Any]:
        """Discover story structure patterns using mathematical analysis."""
        import numpy as np
        try:
            from scipy.stats import pearsonr
        except ImportError:
            logger.warning("SciPy not available - skipping story arc pattern discovery")
            return {}
        
        story_features = []
        
        for transcript, score in zip(transcripts, scores):
            sentences = sent_tokenize(transcript)
            sentence_lengths = [len(s.split()) for s in sentences]
            
            if len(sentence_lengths) > 3:
                pacing_variance = np.var(sentence_lengths)
                dialogue_ratio = sum(1 for s in sentences if '"' in s or "'" in s) / len(sentences)
                punctuation_density = sum(transcript.count(p) for p in '.,!?;:') / len(transcript)
                
                story_features.append({
                    'pacing_variance': pacing_variance,
                    'dialogue_ratio': dialogue_ratio,
                    'punctuation_density': punctuation_density,
                    'score': score
                })
        
        discovered_patterns = {}
        
        if story_features:
            for pattern in ['pacing_variance', 'dialogue_ratio', 'punctuation_density']:
                values = [f[pattern] for f in story_features]
                scores_list = [f['score'] for f in story_features]
                
                try:
                    correlation, p_value = pearsonr(values, scores_list)
                    if not np.isnan(correlation) and abs(correlation) > 0.05:
                        discovered_patterns[pattern] = {
                            'correlation': correlation,
                            'p_value': p_value,
                            'mean_value': np.mean(values)
                        }
                except:
                    pass
        
        return discovered_patterns
    
    def _discover_ngram_patterns(self, transcripts: List[str], scores: List[float]) -> Dict[str, Any]:
        """Discover n-gram patterns that correlate with high performance."""
        from sklearn.feature_extraction.text import CountVectorizer
        import numpy as np
        
        vectorizer = CountVectorizer(ngram_range=(2, 3), min_df=3, max_features=200)
        
        try:
            ngram_matrix = vectorizer.fit_transform(transcripts)
            feature_names = vectorizer.get_feature_names_out()
            
            ngram_correlations = {}
            
            for i, ngram in enumerate(feature_names):
                ngram_counts = ngram_matrix[:, i].toarray().flatten()
                correlation = np.corrcoef(ngram_counts, scores)[0, 1]
                
                if not np.isnan(correlation) and abs(correlation) > 0.08:
                    ngram_correlations[ngram] = {
                        'correlation': correlation,
                        'frequency': np.sum(ngram_counts)
                    }
            
            return ngram_correlations
            
        except Exception as e:
            logger.warning(f"Error in n-gram discovery: {e}")
            return {}
    
    def _discover_content_patterns(self, transcripts: List[str], scores: List[float]) -> Dict[str, Any]:
        """Discover patterns throughout content."""
        import numpy as np
        try:
            from scipy.stats import pearsonr
        except ImportError:
            logger.warning("SciPy not available - skipping content pattern discovery")
            return {}
        from collections import defaultdict
        
        discovered_patterns = {}
        segment_correlations = {}
        
        for segment_length in [5, 10, 20, 30]:
            for position in ['start', 'middle', 'end']:
                segment_features = []
                
                for transcript in transcripts:
                    words = transcript.lower().split()
                    if len(words) < segment_length:
                        segment_features.append('')
                        continue
                    
                    if position == 'start':
                        segment = ' '.join(words[:segment_length])
                    elif position == 'end':
                        segment = ' '.join(words[-segment_length:])
                    else:
                        mid_point = len(words) // 2
                        start_idx = max(0, mid_point - segment_length // 2)
                        end_idx = min(len(words), start_idx + segment_length)
                        segment = ' '.join(words[start_idx:end_idx])
                    
                    segment_features.append(segment)
                
                intensities = [abs(self.sia.polarity_scores(seg)['compound']) if seg and self.sia else 0 
                             for seg in segment_features]
                
                try:
                    correlation, p_value = pearsonr(intensities, scores)
                    if not np.isnan(correlation):
                        segment_correlations[f'{position}_{segment_length}_words'] = {
                            'correlation': correlation,
                            'p_value': p_value,
                            'segment_length': segment_length,
                            'position': position
                        }
                except:
                    pass
        
        discovered_patterns['segment_importance'] = segment_correlations
        return discovered_patterns
    
    def _discover_emotional_journey_patterns(self, transcripts: List[str], scores: List[float]) -> Dict[str, Any]:
        """Discover emotional progression patterns."""
        import numpy as np
        try:
            from scipy.stats import pearsonr
        except ImportError:
            logger.warning("SciPy not available - skipping emotional journey pattern discovery")
            return {}
        
        emotional_features = []
        
        for transcript, score in zip(transcripts, scores):
            sentences = sent_tokenize(transcript)
            if len(sentences) < 3 or not self.sia:
                continue
                
            sentence_sentiments = []
            for sentence in sentences:
                sentiment = self.sia.polarity_scores(sentence)
                sentence_sentiments.append(sentiment['compound'])
            
            if len(sentence_sentiments) >= 3:
                features = {
                    'emotional_volatility': np.std(sentence_sentiments),
                    'emotional_range': max(sentence_sentiments) - min(sentence_sentiments),
                    'emotional_trend': sentence_sentiments[-1] - sentence_sentiments[0],
                    'peak_intensity': max(abs(s) for s in sentence_sentiments),
                    'opening_to_peak_change': max(sentence_sentiments) - sentence_sentiments[0],
                    'score': score
                }
                emotional_features.append(features)
        
        discovered_patterns = {}
        
        if emotional_features:
            for pattern in ['emotional_volatility', 'emotional_range', 'emotional_trend', 
                          'peak_intensity', 'opening_to_peak_change']:
                values = [f[pattern] for f in emotional_features]
                scores_list = [f['score'] for f in emotional_features]
                
                try:
                    correlation, p_value = pearsonr(values, scores_list)
                    if not np.isnan(correlation):
                        discovered_patterns[pattern] = {
                            'correlation': correlation,
                            'p_value': p_value,
                            'mean_value': np.mean(values)
                        }
                except:
                    pass
        
        return discovered_patterns
    
    def _discover_semantic_alignment_patterns(self, transcripts: List[str], comments_list: List[List[Any]], 
                                            scores: List[float]) -> Dict[str, Any]:
        """Discover semantic word overlap patterns between content and comments."""
        import numpy as np
        from scipy.stats import pearsonr
        
        alignment_features = []
        
        for transcript, comments, score in zip(transcripts, comments_list, scores):
            if not comments:
                alignment_features.append({'overlap_ratio': 0, 'response_diversity': 0, 'score': score})
                continue
            
            # Process comments to text
            comment_texts = []
            for comment in comments:
                if isinstance(comment, dict) and 'text' in comment:
                    comment_texts.append(comment['text'].lower())
                elif isinstance(comment, str):
                    comment_texts.append(comment.lower())
            
            if not comment_texts:
                alignment_features.append({'overlap_ratio': 0, 'response_diversity': 0, 'score': score})
                continue
            
            # Calculate semantic overlap
            transcript_words = set(transcript.lower().split())
            all_comment_words = set()
            for comment in comment_texts:
                all_comment_words.update(comment.split())
            
            # Remove common stop words for meaningful overlap
            meaningful_transcript = transcript_words - self.stop_words
            meaningful_comments = all_comment_words - self.stop_words
            
            if meaningful_transcript:
                overlap_ratio = len(meaningful_transcript.intersection(meaningful_comments)) / len(meaningful_transcript)
                response_diversity = len(meaningful_comments - meaningful_transcript) / len(meaningful_transcript)
            else:
                overlap_ratio = 0
                response_diversity = 0
            
            alignment_features.append({
                'overlap_ratio': overlap_ratio,
                'response_diversity': response_diversity,
                'score': score
            })
        
        # Find correlations
        patterns = {}
        
        if alignment_features:
            for feature in ['overlap_ratio', 'response_diversity']:
                values = [f[feature] for f in alignment_features]
                scores_list = [f['score'] for f in alignment_features]
                
                try:
                    correlation, p_value = pearsonr(values, scores_list)
                    if not np.isnan(correlation) and abs(correlation) > 0.05:
                        patterns[feature] = {
                            'correlation': correlation,
                            'p_value': p_value,
                            'mean_value': np.mean(values)
                        }
                except:
                    pass
        
        return patterns
    
    def _discover_content_trigger_patterns(self, transcripts: List[str], comments_list: List[List[Any]], 
                                         scores: List[float]) -> Dict[str, Any]:
        """Discover which transcript content triggers specific comment responses."""
        from collections import defaultdict
        import numpy as np
        from scipy.stats import pearsonr
        
        trigger_patterns = {}
        
        # Entity response patterns (relationships, names that trigger responses)
        entity_response_data = defaultdict(list)
        
        for transcript, comments, score in zip(transcripts, comments_list, scores):
            if not comments:
                continue
            
            # Extract potential entities/subjects without hardcoding
            transcript_words = transcript.split()
            entities = []
            
            # Find capitalized words (potential names/places)
            for word in transcript_words:
                cleaned = word.strip('.,!?').lower()
                if len(cleaned) > 2 and word[0].isupper() and not word.isupper():
                    entities.append(cleaned)
            
            # Process comments
            comment_texts = []
            for comment in comments:
                if isinstance(comment, dict) and 'text' in comment:
                    comment_texts.append(comment['text'].lower())
                elif isinstance(comment, str):
                    comment_texts.append(comment.lower())
            
            if not entities or not comment_texts:
                continue
            
            # Check comment responses for entity references
            for entity in set(entities):
                entity_mentions = sum(entity in comment for comment in comment_texts)
                entity_response_rate = entity_mentions / len(comment_texts)
                
                entity_response_data[entity].append({
                    'response_rate': entity_response_rate,
                    'score': score
                })
        
        # Analyze which entities correlate with performance
        # Use dynamic threshold based on data distribution
        all_frequencies = [len(data_points) for data_points in entity_response_data.values()]
        min_threshold = max(2, int(np.percentile(all_frequencies, 25))) if all_frequencies else 2
        
        entity_patterns = {}
        for entity, data_points in entity_response_data.items():
            if len(data_points) >= min_threshold:
                response_rates = [d['response_rate'] for d in data_points]
                scores_list = [d['score'] for d in data_points]
                
                try:
                    correlation, p_value = pearsonr(response_rates, scores_list)
                    if not np.isnan(correlation) and abs(correlation) > 0.1:
                        entity_patterns[entity] = {
                            'correlation': correlation,
                            'p_value': p_value,
                            'avg_response_rate': np.mean(response_rates)
                        }
                except:
                    pass
        
        trigger_patterns['entity_responses'] = entity_patterns
        
        # Emotional trigger patterns
        emotional_trigger_data = []
        
        for transcript, comments, score in zip(transcripts, comments_list, scores):
            if not comments or not self.sia:
                continue
            
            # Analyze emotional amplification
            transcript_sentiment = self.sia.polarity_scores(transcript)['compound']
            
            comment_texts = []
            for comment in comments:
                if isinstance(comment, dict) and 'text' in comment:
                    comment_texts.append(comment['text'])
                elif isinstance(comment, str):
                    comment_texts.append(comment)
            
            if not comment_texts:
                continue
            
            comment_sentiments = [self.sia.polarity_scores(c)['compound'] for c in comment_texts]
            
            # Calculate emotional amplification
            avg_comment_intensity = np.mean([abs(s) for s in comment_sentiments])
            transcript_intensity = abs(transcript_sentiment)
            emotional_amplification = avg_comment_intensity - transcript_intensity
            
            emotional_trigger_data.append({
                'emotional_amplification': emotional_amplification,
                'score': score
            })
        
        # Find emotional patterns
        if emotional_trigger_data:
            values = [d['emotional_amplification'] for d in emotional_trigger_data]
            scores_list = [d['score'] for d in emotional_trigger_data]
            
            try:
                correlation, p_value = pearsonr(values, scores_list)
                if not np.isnan(correlation) and abs(correlation) > 0.05:
                    trigger_patterns['emotional_amplification'] = {
                        'correlation': correlation,
                        'p_value': p_value,
                        'mean_value': np.mean(values)
                    }
            except:
                pass
        
        return trigger_patterns


def predict_performance_score(transcript: str) -> float:
    """Simple function interface for text scoring with viral pattern learning.""" 
    # Try to load existing model
    script_dir = Path(__file__).parent
    model_path = script_dir / "models" / "snoo.pkl"
    
    try:
        predictor = TikTokPerformancePredictor()
        predictor.load_model(str(model_path))
        return predictor.predict_score(transcript)
    except FileNotFoundError:
        logger.error(f"Model not found at {model_path}. Please train the model first.")
        return 0.0
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return 0.0


def main():
    """Command line interface."""
    import sys
    import argparse
    
    # Get project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    parser = argparse.ArgumentParser(description="TikTok Performance Predictor")
    parser.add_argument('command', choices=['train', 'predict'], help='Command to run')
    parser.add_argument('--data', default=str(project_root / 'data' / 'master2.json'), 
                       help='Path to training data (master2.json)')
    parser.add_argument('--model', default=str(script_dir / 'models' / 'snoo.pkl'),
                       help='Path to model file')
    parser.add_argument('--text', help='Text to predict (for predict command)')
    
    args = parser.parse_args()
    
    if args.command == 'train':
        predictor = TikTokPerformancePredictor()
        metrics = predictor.train(args.data)
        predictor.save_model(args.model)
        
        print("\n=== Training Complete ===")
        print(f"Samples: {metrics['n_samples']}")
        print(f"Features: {metrics['n_features']}")
        print(f"R² Score: {metrics['r2_score']:.3f}")
        print(f"MAE: {metrics['mae']:.2f}")
        print(f"Training Time: {metrics['training_time']:.1f}s")
        
    elif args.command == 'predict':
        if not args.text:
            print("Error: --text argument required for predict command")
            sys.exit(1)
            
        score = predict_performance_score(args.text)
        print(f"Score: {score:.1f}")


if __name__ == "__main__":
    main()