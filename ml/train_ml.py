#!/usr/bin/env python3
"""
TikTok Performance Prediction Model - Supervised Learning Implementation

This module implements a supervised learning model that predicts TikTok video performance
scores (0-100) directly from transcript text. The model is trained on real performance
data from the PostgreSQL database and learns to predict how well content will perform based on
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

import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
import re
import time
import logging
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')
import psycopg2
from psycopg2.extras import RealDictCursor
import tomllib
import os
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.device_manager import DeviceManager

# ML Imports
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import Ridge, QuantileRegressor
    from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
    from sklearn.preprocessing import RobustScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.isotonic import IsotonicRegression
    from sklearn.utils.class_weight import compute_sample_weight
    import xgboost as xgb
    import joblib
except ImportError as e:
    print(f"Missing ML dependencies: {e}")
    print("Install with: pip install scikit-learn xgboost joblib")
    exit(1)

# Sentence Transformer imports (optional but recommended)
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    # Logger not initialized yet, will warn later

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

# Log sentence transformer availability
if not SENTENCE_TRANSFORMERS_AVAILABLE:
    logger.info("sentence-transformers not installed. Using TF-IDF only.")
    logger.info("For better semantic understanding, install with: pip install sentence-transformers")

class TikTokPerformancePredictor:
    """Supervised learning model for predicting TikTok performance from transcripts.
    
    Enhanced with stratified sampling, quantile regression, and calibration to fix
    score clustering around the mean (65-77 range issue).
    """
    
    def __init__(self):
        """Initialize the predictor."""
        self.model = None
        self.scaler = RobustScaler()
        self.is_trained = False
        self.feature_names = []
        
        # GPU acceleration detection
        self.device = DeviceManager.get_best_device()
        self.device_info = DeviceManager.get_device_info()
        logger.info(f"Device initialized: {self.device}")
        if self.device == 'cuda':
            logger.info(f"GPU: {self.device_info['cuda_device_name']}")
        
        # Calibration models for score spreading
        self.isotonic_calibrator = None
        self.score_percentiles = None
        
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
        
        # Sentence transformer for semantic embeddings
        self.sentence_transformer = None
        self.embedding_dim = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Use a smaller, faster model for efficiency
                self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
                self.embedding_dim = 384  # Dimension of all-MiniLM-L6-v2
                logger.info("Sentence transformer loaded: all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"Could not load sentence transformer: {e}")
                self.sentence_transformer = None
        
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
    
    def _load_from_database(self, filter_reddit_like: bool = True) -> List[Dict]:
        """Load training data from PostgreSQL database using config.toml settings.
        
        Args:
            filter_reddit_like: If True, filter for Reddit-like content (text-heavy narratives)
        """
        # Load database config
        config_path = Path(__file__).parent.parent / 'config.toml'
        if not config_path.exists():
            raise FileNotFoundError(f"config.toml not found at {config_path}")
        
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
        
        db_config = config.get('database', {})
        ml_config = config.get('ml', {})
        if not db_config.get('enabled', True):
            raise ValueError("Database is disabled in config.toml")
        
        # Connect to database
        conn_params = {
            'host': db_config.get('host', 'localhost'),
            'database': db_config.get('database', 'tiktok_scraper'),
            'user': db_config.get('user', os.getenv('USER')),
            'password': db_config.get('password', ''),
            'port': db_config.get('port', 5432)
        }
        
        # Remove empty password if not set
        if not conn_params['password']:
            del conn_params['password']
        
        conn = psycopg2.connect(**conn_params, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        
        # Get filter settings from config
        min_duration = ml_config.get('min_duration', 45)
        min_words = ml_config.get('min_words', 150)
        min_words_per_second = ml_config.get('min_words_per_second', 2.0)
        
        # Build query with optional filtering for Reddit-like content
        duration_filter = f"AND v.duration >= {min_duration}" if filter_reddit_like else ""
        
        # Query to get data from gold layer (or silver if gold not ready)
        query = f"""
            SELECT 
                v.video_id,
                v.url,
                v.title,
                v.description,
                v.uploader,
                v.view_count,
                v.like_count,
                v.comment_count,
                v.share_count,
                v.upload_date,
                v.duration,
                t.whisper_transcription,
                -- Calculate transcription metrics
                array_length(string_to_array(t.whisper_transcription, ' '), 1) as word_count,
                CASE 
                    WHEN v.duration > 0 THEN 
                        array_length(string_to_array(t.whisper_transcription, ' '), 1)::float / v.duration 
                    ELSE 0 
                END as words_per_second,
                -- Get comments as JSONB array
                COALESCE(
                    (SELECT jsonb_agg(
                        jsonb_build_object(
                            'comment_id', c.comment_id,
                            'username', c.username,
                            'comment_text', c.comment_text,
                            'like_count', c.like_count
                        ) ORDER BY c.like_count DESC
                    ) 
                    FROM comments c 
                    WHERE c.video_id = v.id
                    LIMIT 100
                    ), '[]'::jsonb
                ) as comments,
                -- Get features from gold layer if available
                f.engagement_rate,
                f.virality_score,
                f.performance_tier
            FROM videos v
            LEFT JOIN transcriptions t ON t.video_id = v.id
            LEFT JOIN gold.ml_features f ON f.video_id = v.video_id
            WHERE v.view_count IS NOT NULL
            AND t.whisper_transcription IS NOT NULL
            AND LENGTH(t.whisper_transcription) > 10
            {duration_filter}
            ORDER BY v.downloaded_at DESC
        """
        
        try:
            cursor.execute(query)
            results = cursor.fetchall()
            
            # Convert to list of dicts matching expected format
            videos = []
            filtered_count = 0
            total_count = 0
            
            for row in results:
                video = dict(row)
                total_count += 1
                
                # Apply Reddit-like content filtering
                if filter_reddit_like:
                    word_count = video.get('word_count', 0) or 0
                    words_per_second = video.get('words_per_second', 0) or 0
                    duration = video.get('duration', 0) or 0
                    
                    # Filter criteria: substantial talking content
                    # 1. Has enough words (>150) OR decent speaking rate (>2 words/sec)
                    has_substantial_talking = (word_count > min_words) or (words_per_second > min_words_per_second)
                    
                    # 2. Not pure music/dance (very low transcription density)
                    expected_words = duration * 2.5  # Average speaking rate
                    is_not_music_dance = word_count > (expected_words * 0.1)  # At least 10% of expected
                    
                    if not (has_substantial_talking and is_not_music_dance):
                        filtered_count += 1
                        continue
                
                # Ensure comments is a list
                if isinstance(video.get('comments'), str):
                    pass  # Already in correct format from jsonb
                elif video.get('comments') is None:
                    video['comments'] = []
                    
                videos.append(video)
            
            if filter_reddit_like:
                logger.info(f"Filtered {filtered_count}/{total_count} videos to focus on Reddit-like content")
                logger.info(f"Retained {len(videos)} videos with substantial narrative/talking content")
            
            return videos
            
        finally:
            cursor.close()
            conn.close()
        
    def calculate_performance_score(self, view_count: int, like_count: int, comment_count: int, 
                                   comments: List[Any] = None) -> float:
        """Calculate virality score with better differentiation between content tiers."""
        # Enhanced engagement metrics
        engagement_rate = like_count / max(view_count, 1)
        comment_rate = comment_count / max(view_count, 1)
        
        # Virality multiplier based on engagement quality
        virality_multiplier = 1.0
        if engagement_rate > 0.15:  # Exceptional engagement (>15%)
            virality_multiplier = 2.0
        elif engagement_rate > 0.10:  # Great engagement (>10%)
            virality_multiplier = 1.5
        elif engagement_rate > 0.05:  # Good engagement (>5%)
            virality_multiplier = 1.2
        
        # Enhanced view score with wider range
        if view_count >= 10_000_000:
            view_score = 85 + min(15, (view_count - 10_000_000) / 2_000_000)
        elif view_count >= 5_000_000:
            view_score = 70 + (view_count - 5_000_000) / 333_333 * virality_multiplier
        elif view_count >= 1_000_000:
            view_score = 50 + (view_count - 1_000_000) / 80_000 * virality_multiplier
        elif view_count >= 500_000:
            view_score = 35 + (view_count - 500_000) / 33_333 * virality_multiplier
        elif view_count >= 100_000:
            view_score = 20 + (view_count - 100_000) / 26_666
        elif view_count >= 10_000:
            view_score = 10 + (view_count - 10_000) / 9_000
        else:
            # Low performing content gets much lower scores
            view_score = max(0, view_count / 1000)
        
        # Enhanced engagement scoring with wider variance
        if engagement_rate > 0.2:  # Exceptional (>20% engagement)
            engagement_bonus = 25
        elif engagement_rate > 0.15:  # Viral-level (>15%)
            engagement_bonus = 20
        elif engagement_rate > 0.10:  # Great (>10%)
            engagement_bonus = 15
        elif engagement_rate > 0.05:  # Good (>5%)
            engagement_bonus = 8
        elif engagement_rate > 0.02:  # Average (2-5%)
            engagement_bonus = 3
        else:  # Poor (<2%)
            engagement_bonus = -5  # Penalty for low engagement
        
        # Comment engagement scoring
        comment_bonus = 0
        if comment_rate > 0.01:  # >1% comment rate is excellent
            comment_bonus = 10
        elif comment_rate > 0.005:  # 0.5-1% is good
            comment_bonus = 5
        elif comment_rate > 0.001:  # 0.1-0.5% is average
            comment_bonus = 2
        
        # Analyze comment quality for additional scoring (if comments provided)
        if comments:
            quality_bonus = self._analyze_comment_quality(comments)
            comment_bonus += quality_bonus
        
        # Calculate final score with wider distribution
        base_score = view_score + engagement_bonus + comment_bonus
        
        # Apply logarithmic scaling for extreme outliers
        if view_count > 50_000_000:  # Mega-viral content
            base_score = min(100, base_score * 1.2)
        elif view_count < 1000 and engagement_rate < 0.02:  # Very poor performance
            base_score = max(0, base_score * 0.5)
        
        return max(0, min(100, base_score))
    
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
    
    def train(self, data_source: Optional[str] = None, test_size: float = 0.2, use_database: bool = True, 
              filter_reddit_like: bool = True) -> Dict[str, Any]:
        """Train the model on database data with enhanced distribution spreading.
        
        Args:
            filter_reddit_like: If True, filter training data to Reddit-like content
        """
        logger.info("Starting enhanced supervised learning training...")
        logger.info(f"Using device: {self.device}")
        logger.info(f"Reddit-like filtering: {filter_reddit_like}")
        start_time = time.time()
        
        # Load data from database with optional filtering
        videos = self._load_from_database(filter_reddit_like=filter_reddit_like)
        logger.info(f"Loaded {len(videos)} videos from database")
        
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
        all_scores = np.array([d['score'] for d in training_data])
        
        logger.info(f"Collected {len(all_transcripts)} transcript-comment-score triplets")
        logger.info(f"Score distribution - Min: {all_scores.min():.1f}, Max: {all_scores.max():.1f}, Mean: {all_scores.mean():.1f}, Std: {all_scores.std():.1f}")
        
        # Store percentiles for calibration
        self.score_percentiles = np.percentile(all_scores, np.arange(0, 101, 1))
        
        # Learn semantic and emotional patterns including comment-content alignment
        self.learn_semantic_patterns(all_transcripts, all_scores, all_comments)
        
        # Fit TF-IDF on all transcripts
        self.fit_tfidf(all_transcripts)
        
        # Pre-compute sentence embeddings if available
        if self.sentence_transformer:
            logger.info("Computing sentence embeddings for training data...")
            self._precompute_embeddings(all_transcripts)
        
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
                
                # Add sentence embedding features if available
                if self.sentence_transformer:
                    embedding_features = self.extract_embedding_features(data['transcript'], index=i)
                    features.update(embedding_features)
                
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
        
        # STRATIFIED SAMPLING: Bin scores for balanced training
        y_binned = pd.qcut(y, q=5, labels=False, duplicates='drop')  # 5 quantile bins
        
        # Split data with stratification
        X_train, X_test, y_train, y_test, y_train_binned, y_test_binned = train_test_split(
            X, y, y_binned, test_size=test_size, random_state=42, stratify=y_binned
        )
        
        # SAMPLE WEIGHTING: Give more importance to extreme values
        sample_weights = self._compute_sample_weights(y_train)
        logger.info(f"Sample weights range: {sample_weights.min():.2f} - {sample_weights.max():.2f}")
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train enhanced ensemble model
        logger.info("Training enhanced ensemble with quantile regression...")
        
        # Configure XGBoost for GPU if available
        xgb_params = {
            'n_estimators': 100,
            'max_depth': 6,
            'random_state': 42,
            'verbose': 0,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8
        }
        if self.device == 'cuda':
            xgb_params['tree_method'] = 'gpu_hist'
            xgb_params['gpu_id'] = 0
            logger.info("XGBoost configured for GPU acceleration")
        
        # Random Forest with sample weights
        rf_model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        rf_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        
        # XGBoost with sample weights
        xgb_model = xgb.XGBRegressor(**xgb_params)
        xgb_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        
        # QUANTILE REGRESSION: Train models for different percentiles including extremes
        logger.info("Training quantile regressors (including extreme quantiles 0.05 and 0.95)...")
        quantile_models = {}
        # Add extreme quantiles for better spread
        for quantile in [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]:
            try:
                # Use QuantileRegressor if available (sklearn >= 1.0)
                q_model = QuantileRegressor(quantile=quantile, alpha=0.1, solver='highs')
                q_model.fit(X_train_scaled, y_train)
                quantile_models[f'q{int(quantile*100)}'] = q_model
                logger.info(f"Trained quantile model for q{int(quantile*100)}")
            except:
                # Fallback to GradientBoosting with quantile loss
                q_model = GradientBoostingRegressor(
                    loss='quantile', 
                    alpha=quantile,
                    n_estimators=100,
                    max_depth=5,
                    random_state=42
                )
                q_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
                quantile_models[f'q{int(quantile*100)}'] = q_model
                logger.info(f"Trained GradientBoosting quantile model for q{int(quantile*100)}")
        
        # Ridge Regression (baseline)
        ridge_model = Ridge(alpha=1.0)
        ridge_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        
        # Create enhanced ensemble
        self.model = {
            'rf': rf_model,
            'xgb': xgb_model,
            'ridge': ridge_model,
            **quantile_models  # Add quantile models
        }
        
        # ISOTONIC CALIBRATION: Fit on TRAINING data to avoid overfitting
        logger.info("Fitting isotonic calibration on training set...")
        train_predictions = {}
        for name, model in self.model.items():
            train_predictions[name] = model.predict(X_train_scaled)
        
        # Get training ensemble predictions
        train_ensemble = self._compute_ensemble_prediction(train_predictions)
        
        # Fit calibrator on training data
        self.isotonic_calibrator = IsotonicRegression(out_of_bounds='clip')
        self.isotonic_calibrator.fit(train_ensemble, y_train)
        
        # Now evaluate on test set
        test_predictions = {}
        for name, model in self.model.items():
            test_predictions[name] = model.predict(X_test_scaled)
        
        # Weighted ensemble prediction
        ensemble_pred = self._compute_ensemble_prediction(test_predictions)
        
        # Apply calibration
        calibrated_pred = self.isotonic_calibrator.transform(ensemble_pred)
        
        # Calculate metrics (on calibrated predictions)
        mae = mean_absolute_error(y_test, calibrated_pred)
        rmse = np.sqrt(mean_squared_error(y_test, calibrated_pred))
        r2 = r2_score(y_test, calibrated_pred)
        
        # Calculate distribution metrics
        pred_range = calibrated_pred.max() - calibrated_pred.min()
        pred_std = calibrated_pred.std()
        true_range = y_test.max() - y_test.min()
        true_std = y_test.std()
        
        logger.info(f"Prediction range: {calibrated_pred.min():.1f} - {calibrated_pred.max():.1f} (spread: {pred_range:.1f})")
        logger.info(f"True range: {y_test.min():.1f} - {y_test.max():.1f} (spread: {true_range:.1f})")
        logger.info(f"Prediction std: {pred_std:.1f}, True std: {true_std:.1f}")
        
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
            'cv_std': cv_scores.std(),
            'prediction_range': pred_range,
            'prediction_std': pred_std,
            'device_used': self.device
        }
    
    def predict_score(self, transcript: str) -> float:
        """Predict performance score with enhanced distribution spreading."""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        # Extract features from transcript
        features = self.extract_features(transcript)
        
        # Add TF-IDF features
        tfidf_features = self.extract_tfidf_features(transcript)
        features.update(tfidf_features)
        
        # Add sentence embedding features if available
        if self.sentence_transformer:
            embedding_features = self.extract_embedding_features(transcript)
            features.update(embedding_features)
        
        # Convert to array with correct feature order
        feature_vector = np.zeros(len(self.feature_names))
        for i, feature_name in enumerate(self.feature_names):
            feature_vector[i] = features.get(feature_name, 0)
        
        # Scale features
        feature_vector_scaled = self.scaler.transform([feature_vector])
        
        # Get predictions from all models
        predictions = {}
        for name, model in self.model.items():
            predictions[name] = model.predict(feature_vector_scaled)[0]
        
        # Compute weighted ensemble
        ensemble_score = self._compute_ensemble_prediction(predictions, single_sample=True)
        
        # Apply isotonic calibration if available
        if self.isotonic_calibrator is not None:
            calibrated_score = self.isotonic_calibrator.transform([ensemble_score])[0]
        else:
            calibrated_score = ensemble_score
        
        # Apply confidence-based spreading
        final_score = self._apply_confidence_spreading(calibrated_score, predictions)
        
        # Clamp to 0-100 range
        return max(0, min(100, final_score))
    
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
            'tfidf_vectorizer': self.tfidf_vectorizer,
            'isotonic_calibrator': self.isotonic_calibrator,
            'score_percentiles': self.score_percentiles,
            'device_trained_on': self.device,
            'sentence_transformer_model': 'all-MiniLM-L6-v2' if self.sentence_transformer else None,
            'embedding_cache': getattr(self, 'embedding_cache', None)
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
        self.isotonic_calibrator = model_data.get('isotonic_calibrator', None)
        self.score_percentiles = model_data.get('score_percentiles', None)
        
        # Load sentence transformer if it was used during training
        transformer_model = model_data.get('sentence_transformer_model', None)
        if transformer_model and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_transformer = SentenceTransformer(transformer_model)
                self.embedding_dim = 384
                self.embedding_cache = model_data.get('embedding_cache', {})
                logger.info(f"Loaded sentence transformer: {transformer_model}")
            except Exception as e:
                logger.warning(f"Could not load sentence transformer: {e}")
                self.sentence_transformer = None
        else:
            self.sentence_transformer = None
        
        # Log device info
        trained_device = model_data.get('device_trained_on', 'unknown')
        logger.info(f"Model was trained on: {trained_device}, current device: {self.device}")
        
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
        
        # NEW: Narrative arc detection
        features.update(self._extract_narrative_arc_features(transcript, sentences))
        
        # NEW: Information density and controversy
        features.update(self._extract_information_density_features(transcript, words, sentences))
        
        # NEW: Reddit-specific patterns
        features.update(self._extract_reddit_patterns(transcript, words, sentences))
        
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
        """Extract hook analysis features with enhanced viral pattern detection."""
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
        
        # ENHANCED VIRAL PATTERNS
        # Psychological trigger words (expanded set)
        psychological_triggers = [
            'secret', 'hidden', 'nobody', 'everyone', 'always', 'never', 'truth',
            'shocking', 'insane', 'crazy', 'unbelievable', 'mind-blowing', 'literally',
            'actually', 'honestly', 'warning', 'urgent', 'breaking', 'exclusive'
        ]
        
        # FOMO (Fear of Missing Out) indicators
        fomo_patterns = [
            'before its', 'limited time', 'dont miss', 'hurry', 'last chance',
            'trending', 'viral', 'everyone is', 'you need to', 'must see'
        ]
        
        # Curiosity gap creators
        curiosity_patterns = [
            'wait till', 'you wont believe', 'this is why', 'the reason',
            'what happens when', 'i discovered', 'nobody talks about',
            'the truth about', 'what they dont tell'
        ]
        
        # Count psychological triggers in opening
        trigger_count = sum(1 for word in first_5_sec_text.split() if word in psychological_triggers)
        features['opening_trigger_count'] = trigger_count
        features['opening_trigger_density'] = trigger_count / max(len(first_5_sec_words), 1)
        
        # Check for FOMO patterns
        fomo_score = sum(1 for pattern in fomo_patterns if pattern in first_5_sec_text)
        features['fomo_hook_score'] = fomo_score
        
        # Check for curiosity patterns
        curiosity_score = sum(1 for pattern in curiosity_patterns if pattern in first_5_sec_text)
        features['curiosity_hook_score'] = curiosity_score
        
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
    
    def _extract_narrative_arc_features(self, transcript: str, sentences: List[str]) -> Dict[str, float]:
        """Extract narrative arc and emotional journey features.
        
        This captures how the emotional tone changes throughout the content,
        which is crucial for Reddit-style storytelling.
        """
        features = {}
        
        if len(sentences) < 3 or not self.sia:
            return {
                'emotional_arc_volatility': 0.0,
                'emotional_arc_range': 0.0,
                'emotional_arc_trend': 0.0,
                'narrative_tension_peak': 0.0,
                'narrative_resolution': 0.0
            }
        
        # Calculate sentiment for each sentence
        sentence_sentiments = []
        for sentence in sentences:
            sentiment = self.sia.polarity_scores(sentence)
            sentence_sentiments.append(sentiment['compound'])
        
        # Narrative arc metrics
        features['emotional_arc_volatility'] = np.std(sentence_sentiments)
        features['emotional_arc_range'] = max(sentence_sentiments) - min(sentence_sentiments)
        features['emotional_arc_trend'] = sentence_sentiments[-1] - sentence_sentiments[0]
        
        # Find narrative tension peak (highest emotional intensity)
        peak_intensity = max(abs(s) for s in sentence_sentiments)
        peak_position = [abs(s) for s in sentence_sentiments].index(peak_intensity) / len(sentence_sentiments)
        features['narrative_tension_peak'] = peak_intensity
        features['narrative_tension_position'] = peak_position  # 0=beginning, 1=end
        
        # Resolution score (how much emotion settles at the end)
        if len(sentence_sentiments) >= 5:
            beginning_avg = np.mean(sentence_sentiments[:2])
            ending_avg = np.mean(sentence_sentiments[-2:])
            features['narrative_resolution'] = abs(ending_avg) - abs(beginning_avg)
        else:
            features['narrative_resolution'] = 0.0
        
        # Three-act structure detection
        if len(sentence_sentiments) >= 6:
            third = len(sentence_sentiments) // 3
            act1 = np.mean(sentence_sentiments[:third])
            act2 = np.mean(sentence_sentiments[third:2*third])
            act3 = np.mean(sentence_sentiments[2*third:])
            
            # Classic narrative: setup (neutral) -> conflict (intense) -> resolution
            features['three_act_structure'] = abs(act2) - (abs(act1) + abs(act3)) / 2
        else:
            features['three_act_structure'] = 0.0
        
        return features
    
    def _precompute_embeddings(self, transcripts: List[str]) -> None:
        """Pre-compute sentence embeddings for training efficiency."""
        if not self.sentence_transformer:
            return
        
        logger.info(f"Computing embeddings for {len(transcripts)} transcripts...")
        self.embedding_cache = {}
        
        # Process in batches for efficiency
        batch_size = 32
        for i in range(0, len(transcripts), batch_size):
            batch = transcripts[i:i+batch_size]
            # Truncate very long texts to first 512 tokens (model limit)
            batch_truncated = [t[:2000] for t in batch]  # Roughly 512 tokens
            try:
                embeddings = self.sentence_transformer.encode(batch_truncated, show_progress_bar=False)
                for j, embedding in enumerate(embeddings):
                    self.embedding_cache[i + j] = embedding
            except Exception as e:
                logger.warning(f"Error computing embeddings for batch {i}: {e}")
        
        logger.info(f"Computed {len(self.embedding_cache)} embeddings")
    
    def extract_embedding_features(self, transcript: str, index: Optional[int] = None) -> Dict[str, float]:
        """Extract sentence embedding features.
        
        Args:
            transcript: Text to embed
            index: Optional index for cached embeddings during training
        """
        features = {}
        
        if not self.sentence_transformer:
            return features
        
        try:
            # Use cached embedding if available (during training)
            if index is not None and hasattr(self, 'embedding_cache') and index in self.embedding_cache:
                embedding = self.embedding_cache[index]
            else:
                # Compute embedding (truncate to model limit)
                truncated = transcript[:2000]  # Roughly 512 tokens
                embedding = self.sentence_transformer.encode([truncated], show_progress_bar=False)[0]
            
            # Add embedding dimensions as features
            # Use PCA-like reduction: take top components
            # Instead of all 384 dimensions, use top 50 most informative
            for i in range(min(50, len(embedding))):
                features[f'emb_{i}'] = float(embedding[i])
            
            # Add aggregate embedding statistics
            features['emb_mean'] = float(np.mean(embedding))
            features['emb_std'] = float(np.std(embedding))
            features['emb_max'] = float(np.max(embedding))
            features['emb_min'] = float(np.min(embedding))
            
        except Exception as e:
            logger.warning(f"Error extracting embedding features: {e}")
            # Return zero features on error
            for i in range(50):
                features[f'emb_{i}'] = 0.0
            features['emb_mean'] = 0.0
            features['emb_std'] = 0.0
            features['emb_max'] = 0.0
            features['emb_min'] = 0.0
        
        return features
    
    def _extract_information_density_features(self, transcript: str, words: List[str], 
                                            sentences: List[str]) -> Dict[str, float]:
        """Extract information density and controversy indicators.
        
        These features help identify content that provides value or sparks engagement,
        which is crucial for Reddit-style educational or controversial content.
        """
        features = {}
        
        # Information density metrics
        unique_words = set(words)
        features['vocabulary_diversity'] = len(unique_words) / max(len(words), 1)
        
        # Fact/claim indicators (things that could be verified or disputed)
        fact_indicators = ['study', 'research', 'percent', '%', 'found', 'shows', 'proves',
                          'data', 'statistics', 'report', 'survey', 'analysis', 'evidence']
        fact_count = sum(1 for word in words if word in fact_indicators)
        features['fact_claim_density'] = fact_count / max(len(words), 1) * 100
        
        # Number/statistic density (concrete information)
        number_count = sum(1 for word in words if any(c.isdigit() for c in word))
        features['number_density'] = number_count / max(len(words), 1) * 100
        
        # Controversy indicators (Reddit-style debate triggers)
        controversy_words = [
            'actually', 'wrong', 'myth', 'truth', 'real', 'fake', 'debate', 'controversial',
            'unpopular', 'opinion', 'believe', 'think', 'disagree', 'argue', 'proof',
            'evidence', 'clearly', 'obviously', 'definitely', 'never', 'always', 'everyone',
            'nobody', 'impossible', 'guaranteed', 'fact', 'fiction', 'lie', 'honest'
        ]
        controversy_count = sum(1 for word in words if word in controversy_words)
        features['controversy_score'] = controversy_count / max(len(words), 1) * 100
        
        # Explanation depth (educational content indicator)
        explanation_words = ['because', 'therefore', 'thus', 'hence', 'so', 'means',
                           'explains', 'reason', 'why', 'how', 'what', 'when', 'where']
        explanation_count = sum(1 for word in words if word in explanation_words)
        features['explanation_depth'] = explanation_count / max(len(words), 1) * 100
        
        # List/enumeration detection (common in educational Reddit posts)
        list_indicators = ['first', 'second', 'third', 'finally', 'lastly', 'one', 'two',
                          'three', '1', '2', '3', 'a)', 'b)', 'c)', '-', '•']
        has_list = sum(1 for indicator in list_indicators if indicator in transcript)
        features['has_enumeration'] = min(1.0, has_list / 3)  # Normalize to 0-1
        
        # Information chunks (average facts/claims per sentence)
        if sentences:
            features['info_chunks_per_sentence'] = fact_count / len(sentences)
        else:
            features['info_chunks_per_sentence'] = 0.0
        
        # Specificity score (specific vs vague language)
        specific_words = ['specifically', 'exactly', 'precisely', 'particular', 'certain',
                         'example', 'instance', 'case', 'situation', 'scenario']
        specific_count = sum(1 for word in words if word in specific_words)
        features['specificity_score'] = specific_count / max(len(words), 1) * 100
        
        # Call-to-action or engagement triggers
        cta_phrases = ['what do you think', 'let me know', 'comment below', 'tell me',
                      'share your', 'have you ever', 'did you know', 'imagine if']
        cta_count = sum(1 for phrase in cta_phrases if phrase in transcript)
        features['engagement_cta_score'] = cta_count
        
        return features
    
    def _extract_reddit_patterns(self, transcript: str, words: List[str], 
                                sentences: List[str]) -> Dict[str, float]:
        """Extract Reddit-specific content patterns.
        
        These patterns are common in Reddit posts and help identify
        content that originated from or would work well on Reddit.
        """
        features = {}
        
        # Reddit-style disclaimers and meta-commentary
        reddit_disclaimers = [
            'edit:', 'update:', 'tldr', 'tl;dr', 'obligatory', 'throwaway',
            'long post', 'sorry for', 'english is not my', 'on mobile',
            'first time posting', 'long time lurker', 'delete if not allowed'
        ]
        disclaimer_count = sum(1 for phrase in reddit_disclaimers if phrase in transcript)
        features['reddit_disclaimer_count'] = disclaimer_count
        
        # AITA (Am I The Asshole) patterns
        aita_patterns = [
            'aita', 'am i the', 'was i wrong', 'did i overreact', 'am i being',
            'judge me', 'need perspective', 'outside opinion', 'am i crazy'
        ]
        aita_score = sum(1 for pattern in aita_patterns if pattern in transcript)
        features['aita_pattern_score'] = aita_score
        
        # Story continuation indicators
        continuation_patterns = [
            'part 2', 'part two', 'continued', 'update:', 'follow up',
            'what happened next', 'fast forward', 'few days later', 'update post'
        ]
        has_continuation = sum(1 for pattern in continuation_patterns if pattern in transcript)
        features['has_continuation_pattern'] = min(1.0, has_continuation)
        
        # Relationship/drama indicators (popular on Reddit)
        relationship_words = [
            'boyfriend', 'girlfriend', 'husband', 'wife', 'ex', 'partner',
            'relationship', 'cheating', 'divorce', 'breakup', 'dating',
            'mother', 'father', 'sister', 'brother', 'family', 'parents'
        ]
        relationship_count = sum(1 for word in words if word in relationship_words)
        features['relationship_content_score'] = relationship_count / max(len(words), 1) * 100
        
        # Reddit-style humor and self-awareness
        humor_patterns = [
            '/s', 'lol', 'lmao', 'edit: spelling', 'edit: grammar',
            'thanks for the gold', 'rip inbox', 'this blew up', 'front page'
        ]
        humor_count = sum(1 for pattern in humor_patterns if pattern in transcript)
        features['reddit_humor_score'] = humor_count
        
        # Advice-seeking patterns
        advice_patterns = [
            'what should i', 'what would you', 'need advice', 'help me',
            'what do i do', 'should i', 'would you', 'is it normal',
            'has anyone', 'does anyone', 'can someone explain'
        ]
        advice_count = sum(1 for pattern in advice_patterns if pattern in transcript)
        features['advice_seeking_score'] = advice_count
        
        # List format detection (common in educational Reddit posts)
        numbered_list = sum(1 for s in sentences if any(s.strip().startswith(str(i)) for i in range(1, 10)))
        bullet_list = sum(1 for s in sentences if s.strip().startswith(('-', '•', '*')))
        features['has_list_format'] = min(1.0, (numbered_list + bullet_list) / 3)
        
        # "Today I Learned" (TIL) patterns
        til_patterns = [
            'today i learned', 'til', 'fun fact', 'did you know',
            'interesting fact', 'i just learned', 'apparently', 'turns out'
        ]
        til_score = sum(1 for pattern in til_patterns if pattern in transcript)
        features['til_pattern_score'] = til_score
        
        # Malicious compliance / revenge story patterns
        revenge_patterns = [
            'malicious compliance', 'revenge', 'got back at', 'sweet justice',
            'karma', 'instant karma', 'backfired', 'tables turned', 'showed them'
        ]
        revenge_score = sum(1 for pattern in revenge_patterns if pattern in transcript)
        features['revenge_story_score'] = revenge_score
        
        # "Choosing Beggar" patterns
        cb_patterns = [
            'for free', 'exposure', 'do it for', 'its for church',
            'next!', 'not good enough', 'can you do', 'but i need'
        ]
        cb_score = sum(1 for pattern in cb_patterns if pattern in transcript)
        features['choosing_beggar_score'] = cb_score
        
        # Credibility boosters (common in Reddit stories)
        credibility_patterns = [
            'i work as', 'i am a', 'professional', 'years of experience',
            'certified', 'licensed', 'phd', 'doctor', 'lawyer', 'engineer',
            'source:', 'proof:', 'verified', 'confirmed'
        ]
        credibility_count = sum(1 for pattern in credibility_patterns if pattern in transcript)
        features['credibility_boost_score'] = credibility_count
        
        # Meta-Reddit references
        meta_patterns = [
            'reddit', 'redditor', 'subreddit', 'karma', 'upvote', 'downvote',
            'op', 'original poster', 'crosspost', 'repost'
        ]
        meta_count = sum(1 for pattern in meta_patterns if pattern in transcript)
        features['reddit_meta_score'] = meta_count
        
        # Calculate overall "Reddit-ness" score
        reddit_scores = [
            disclaimer_count * 2,  # Disclaimers are very Reddit-specific
            aita_score * 1.5,
            relationship_count,
            advice_count,
            til_score,
            meta_count * 2  # Direct Reddit references
        ]
        features['overall_reddit_score'] = sum(reddit_scores) / max(len(words), 1) * 100
        
        return features
    
    def filter_training_data(self, videos: List[Dict], progressive: bool = True) -> List[Dict]:
        """Apply progressive filtering to training data for Reddit-like content.
        
        Args:
            videos: List of video dictionaries
            progressive: If True, apply filtering progressively (start loose, get stricter)
            
        Returns:
            Filtered list of videos
        """
        logger.info(f"Starting progressive filtering on {len(videos)} videos")
        
        # Stage 1: Basic quality filter
        stage1 = []
        for video in videos:
            transcript = video.get('whisper_transcription', '')
            duration = video.get('duration', 0)
            
            # Skip very short or no-transcript videos
            if not transcript or duration < 30:
                continue
                
            stage1.append(video)
        
        logger.info(f"Stage 1: {len(stage1)}/{len(videos)} videos passed basic quality filter")
        
        if not progressive:
            return stage1
        
        # Stage 2: Content density filter
        stage2 = []
        for video in stage1:
            transcript = video.get('whisper_transcription', '')
            duration = video.get('duration', 0)
            word_count = len(transcript.split())
            
            # Calculate speaking density
            words_per_second = word_count / max(duration, 1)
            
            # Keep videos with substantial talking (not music/dance)
            if words_per_second > 1.5 or word_count > 100:
                stage2.append(video)
        
        logger.info(f"Stage 2: {len(stage2)}/{len(stage1)} videos passed content density filter")
        
        # Stage 3: Narrative quality filter
        stage3 = []
        for video in stage2:
            transcript = video.get('whisper_transcription', '')
            
            # Check for narrative indicators
            has_sentences = len(sent_tokenize(transcript)) > 3
            has_structure = any(word in transcript.lower() for word in 
                              ['then', 'after', 'because', 'but', 'so', 'when'])
            
            if has_sentences and has_structure:
                stage3.append(video)
        
        logger.info(f"Stage 3: {len(stage3)}/{len(stage2)} videos passed narrative quality filter")
        
        # Ensure we don't filter out too much
        min_retention = 0.3  # Keep at least 30% of original
        if len(stage3) < len(videos) * min_retention:
            logger.warning(f"Progressive filtering too aggressive, using stage 2 results")
            return stage2
        
        return stage3
    
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
        """Discover viral content patterns from high-performing videos."""
        import numpy as np
        try:
            from scipy.stats import pearsonr
        except ImportError:
            logger.warning("SciPy not available - skipping content pattern discovery")
            return {}
        from collections import defaultdict
        
        discovered_patterns = {}
        
        # Focus on top 20% performing content for viral pattern learning
        threshold = np.percentile(scores, 80)
        viral_transcripts = [t for t, s in zip(transcripts, scores) if s >= threshold]
        
        # Learn opening patterns from viral content
        viral_openings = []
        for transcript in viral_transcripts[:100]:  # Sample top 100
            words = transcript.lower().split()[:20]  # First 20 words
            if words:
                viral_openings.append(' '.join(words))
        
        discovered_patterns['viral_openings'] = viral_openings[:10]  # Store top 10 examples
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
    
    def _compute_sample_weights(self, scores: np.ndarray) -> np.ndarray:
        """Compute sample weights to emphasize extreme values.
        
        Args:
            scores: Array of performance scores
            
        Returns:
            Array of sample weights
        """
        # Create weight bins - higher weight for extreme values
        weights = np.ones_like(scores)
        
        # Very low scores (0-20) get 3x weight
        weights[scores < 20] = 3.0
        
        # Low scores (20-40) get 2x weight
        weights[(scores >= 20) & (scores < 40)] = 2.0
        
        # Middle scores (40-60) get normal weight
        weights[(scores >= 40) & (scores < 60)] = 1.0
        
        # High scores (60-80) get normal weight
        weights[(scores >= 60) & (scores < 80)] = 1.0
        
        # Very high scores (80-100) get 3x weight
        weights[scores >= 80] = 3.0
        
        # Normalize weights
        weights = weights / weights.mean()
        
        return weights
    
    def _compute_ensemble_prediction(self, predictions: Dict[str, np.ndarray], 
                                    single_sample: bool = False) -> np.ndarray:
        """Compute weighted ensemble prediction with emphasis on quantile models.
        
        Args:
            predictions: Dictionary of model predictions
            single_sample: Whether this is a single sample (scalar) or array
            
        Returns:
            Weighted ensemble prediction
        """
        if single_sample:
            # For single predictions
            base_pred = (predictions['rf'] + predictions['xgb'] + predictions['ridge']) / 3
            
            # Average quantile predictions for spread
            quantile_preds = []
            for key in predictions:
                if key.startswith('q'):
                    quantile_preds.append(predictions[key])
            
            if quantile_preds:
                # Weight: 60% base models, 40% quantile models
                quantile_avg = np.mean(quantile_preds)
                ensemble = 0.6 * base_pred + 0.4 * quantile_avg
            else:
                ensemble = base_pred
                
            return ensemble
        else:
            # For array predictions
            base_pred = (predictions['rf'] + predictions['xgb'] + predictions['ridge']) / 3
            
            # Collect quantile predictions
            quantile_preds = []
            for key in predictions:
                if key.startswith('q'):
                    quantile_preds.append(predictions[key])
            
            if quantile_preds:
                # Stack and average quantile predictions
                quantile_stack = np.column_stack(quantile_preds)
                quantile_avg = quantile_stack.mean(axis=1)
                
                # Weight: 60% base models, 40% quantile models
                ensemble = 0.6 * base_pred + 0.4 * quantile_avg
            else:
                ensemble = base_pred
                
            return ensemble
    
    def _apply_confidence_spreading(self, base_score: float, 
                                   predictions: Dict[str, float]) -> float:
        """Apply confidence-based spreading to push predictions away from mean.
        
        Args:
            base_score: Base calibrated score
            predictions: Dictionary of all model predictions
            
        Returns:
            Score with confidence-based spreading applied
        """
        # Enhanced spreading using quantile predictions
        spread_score = base_score
        
        # Use quantile predictions to determine spread direction
        if 'q10' in predictions and 'q90' in predictions:
            q10 = predictions['q10']
            q90 = predictions['q90']
            q50 = predictions.get('q50', base_score)
            
            # Calculate quantile spread
            quantile_range = q90 - q10
            
            # If quantiles suggest wide spread, push score toward extremes
            if quantile_range > 40:  # High variance expected
                if base_score > q50:
                    # Push toward higher scores
                    spread_score = base_score + (q90 - base_score) * 0.2
                else:
                    # Push toward lower scores
                    spread_score = base_score - (base_score - q10) * 0.2
            
            # Use extreme quantiles for boundary adjustment
            if 'q5' in predictions and base_score < 30:
                # For low scores, use q5 as guidance
                spread_score = min(spread_score, predictions['q5'] * 1.1)
            elif 'q95' in predictions and base_score > 70:
                # For high scores, use q95 as guidance
                spread_score = max(spread_score, predictions['q95'] * 0.9)
        
        # Calculate model confidence from agreement
        all_preds = list(predictions.values())
        pred_std = np.std(all_preds)
        
        # High confidence (low std) -> more aggressive spreading
        if pred_std < 10:  # Models agree strongly
            if spread_score > 60:
                spread_score = spread_score * 1.1  # Push high scores higher
            elif spread_score < 40:
                spread_score = spread_score * 0.9  # Push low scores lower
        
        # Ensure we're using full range
        return max(0, min(100, spread_score))


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
    """Enhanced command line interface for Reddit→TikTok virality prediction."""
    import sys
    import argparse
    import json
    import time
    
    # Get project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    parser = argparse.ArgumentParser(
        description="TikTok Performance Predictor - Enhanced for Reddit Content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Train model with Reddit filtering:
    python ml/train_ml.py train --filter-reddit
    
  Train without filtering (use all data):
    python ml/train_ml.py train --no-filter
    
  Predict score for text:
    python ml/train_ml.py predict --text "Your Reddit post here"
    
  Test with sample Reddit posts:
    python ml/train_ml.py test
        """
    )
    
    parser.add_argument('command', choices=['train', 'predict', 'test'], 
                       help='Command to run')
    parser.add_argument('--model', default=str(script_dir / 'models' / 'snoo.pkl'),
                       help='Path to model file (default: models/snoo.pkl)')
    parser.add_argument('--text', help='Text to predict (for predict command)')
    parser.add_argument('--filter-reddit', action='store_true', default=True,
                       help='Filter training data for Reddit-like content (default: True)')
    parser.add_argument('--no-filter', dest='filter_reddit', action='store_false',
                       help='Use all training data without filtering')
    parser.add_argument('--no-embeddings', action='store_true',
                       help='Disable sentence embeddings for faster training')
    parser.add_argument('--save-metrics', action='store_true',
                       help='Save training metrics to JSON file')
    
    args = parser.parse_args()
    
    if args.command == 'train':
        print("=" * 80)
        print("Enhanced TikTok Performance Predictor Training")
        print("=" * 80)
        print("\nConfiguration:")
        print(f"  Model path: {args.model}")
        print(f"  Reddit filtering: {'Enabled' if args.filter_reddit else 'Disabled'}")
        print(f"  Sentence embeddings: {'Disabled' if args.no_embeddings else 'Enabled'}")
        
        # Disable embeddings if requested
        if args.no_embeddings:
            global SENTENCE_TRANSFORMERS_AVAILABLE
            SENTENCE_TRANSFORMERS_AVAILABLE = False
            
        print("\nFeatures enabled:")
        print("  ✓ Reddit-like content filtering" if args.filter_reddit else "  ✗ Reddit filtering disabled")
        print("  ✓ Narrative arc detection")
        print("  ✓ Information density analysis")
        print("  ✓ Controversy indicators")
        print("  ✓ Sentence transformer embeddings" if not args.no_embeddings else "  ✗ Embeddings disabled")
        print("  ✓ Reddit-specific patterns")
        print("  ✓ Extreme quantile regression (0.05, 0.95)")
        print("  ✓ Enhanced calibration spreading")
        print("\n" + "=" * 80)
        
        # Initialize and train
        predictor = TikTokPerformancePredictor()
        print("\nStarting training...")
        
        start_time = time.time()
        metrics = predictor.train(filter_reddit_like=args.filter_reddit)
        
        # Save model
        model_dir = Path(args.model).parent
        model_dir.mkdir(exist_ok=True)
        predictor.save_model(args.model)
        
        print("\n" + "=" * 80)
        print("Training Complete!")
        print("=" * 80)
        print("\nModel Performance:")
        print(f"  Training samples: {metrics['n_samples']}")
        print(f"  Features extracted: {metrics['n_features']}")
        print(f"  R² Score: {metrics['r2_score']:.3f}")
        print(f"  MAE: {metrics['mae']:.2f}")
        print(f"  RMSE: {metrics['rmse']:.2f}")
        print(f"  Prediction range: {metrics['prediction_range']:.1f}")
        print(f"  Prediction std: {metrics['prediction_std']:.1f}")
        print(f"  Cross-validation R²: {metrics['cv_mean']:.3f} ± {metrics['cv_std']:.3f}")
        print(f"  Device used: {metrics['device_used']}")
        print(f"  Training time: {metrics['training_time']:.1f} seconds")
        
        # Save metrics if requested
        if args.save_metrics:
            metrics_path = model_dir / "training_metrics.json"
            with open(metrics_path, 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"\nMetrics saved to: {metrics_path}")
        
        print(f"Model saved to: {args.model}")
        
    elif args.command == 'predict':
        if not args.text:
            print("Error: --text argument required for predict command")
            sys.exit(1)
        
        # Load and predict
        try:
            predictor = TikTokPerformancePredictor()
            predictor.load_model(args.model)
            score = predictor.predict_score(args.text)
            
            print(f"\nText: {args.text[:100]}...")
            print(f"Predicted virality score: {score:.1f}/100")
            
            # Provide interpretation
            if score >= 80:
                interpretation = "🔥 High viral potential!"
            elif score >= 60:
                interpretation = "📈 Good viral potential"
            elif score >= 40:
                interpretation = "📊 Moderate potential"
            elif score >= 20:
                interpretation = "📉 Low viral potential"
            else:
                interpretation = "❄️ Very low viral potential"
            
            print(f"Interpretation: {interpretation}")
            
        except FileNotFoundError:
            print(f"Error: Model not found at {args.model}")
            print("Please train the model first with: python ml/train_ml.py train")
            sys.exit(1)
    
    elif args.command == 'test':
        print("\nTesting with sample Reddit-style posts...")
        print("-" * 60)
        
        test_posts = [
            {
                "type": "AITA",
                "text": "AITA for not inviting my sister to my wedding? She cheated with my ex-boyfriend 5 years ago and my family thinks I should forgive and forget."
            },
            {
                "type": "TIL",
                "text": "TIL that honey never spoils. Archaeologists have found 3000 year old honey in Egyptian tombs that was still perfectly edible!"
            },
            {
                "type": "Story",
                "text": "So yesterday I discovered my cat has been living a double life. Turns out she's been visiting our elderly neighbor every day."
            },
            {
                "type": "Advice",
                "text": "What should I do? My roommate keeps eating my food and denies it, but I have video proof. How do I confront them?"
            }
        ]
        
        try:
            predictor = TikTokPerformancePredictor()
            predictor.load_model(args.model)
            
            for post in test_posts:
                score = predictor.predict_score(post['text'])
                print(f"\n[{post['type']}] {post['text'][:60]}...")
                print(f"Score: {score:.1f}/100")
                
        except FileNotFoundError:
            print(f"Error: Model not found at {args.model}")
            print("Please train the model first with: python ml/train_ml.py train")
            sys.exit(1)


if __name__ == "__main__":
    main()