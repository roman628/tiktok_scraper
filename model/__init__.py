"""
TikTok Performance Predictor Package

This package contains tools for predicting TikTok video performance:
- TikTokPredictor: Main prediction class
- TikTokPredictionAPI: API interface for predictions
- predict_performance: CLI tool for text-based predictions
"""

from .tiktok_predictor import TikTokPredictor, TikTokPredictionAPI, TikTokFeatureExtractor

__all__ = ['TikTokPredictor', 'TikTokPredictionAPI', 'TikTokFeatureExtractor']