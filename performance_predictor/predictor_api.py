#!/usr/bin/env python3
"""
TikTok Performance Predictor - Simple API Interface

A simple web API wrapper for the TikTok performance prediction model.
Provides HTTP endpoints for training and prediction.

Usage:
    python predictor_api.py --host 0.0.0.0 --port 8000
    
Endpoints:
    POST /train - Train the model
    POST /predict - Predict video performance
    GET /health - Health check
    GET /info - Model information

Author: EfficientCoder Agent
Date: 2025-07-27
"""

import json
import time
from typing import Dict, Any
from pathlib import Path
import logging

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    print("Flask not installed. Install with: pip install flask flask-cors")
    exit(1)

from .tiktok_predictor import TikTokPredictionAPI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for web integration

# Global API instance
predictor_api = None
MODEL_PATH = "models/tiktok_predictor.pkl"


def initialize_api():
    """Initialize the prediction API."""
    global predictor_api
    try:
        predictor_api = TikTokPredictionAPI(MODEL_PATH if Path(MODEL_PATH).exists() else None)
        logger.info("Prediction API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API: {e}")
        predictor_api = TikTokPredictionAPI()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'model_loaded': predictor_api.predictor.is_trained if predictor_api else False
    })


@app.route('/info', methods=['GET'])
def model_info():
    """Get model information."""
    if not predictor_api:
        return jsonify({'error': 'API not initialized'}), 500
    
    info = predictor_api.get_model_info()
    return jsonify(info)


@app.route('/train', methods=['POST'])
def train_model():
    """Train the prediction model."""
    if not predictor_api:
        return jsonify({'error': 'API not initialized'}), 500
    
    try:
        data = request.get_json()
        
        # Get training parameters
        data_path = data.get('data_path', 'master2.json')
        model_path = data.get('model_path', MODEL_PATH)
        max_samples = data.get('max_samples')
        
        # Validate data file exists
        if not Path(data_path).exists():
            return jsonify({
                'success': False,
                'error': f'Data file not found: {data_path}'
            }), 400
        
        logger.info(f"Training model with data: {data_path}")
        
        # Train model
        result = predictor_api.train_model(data_path, model_path)
        
        if result['success']:
            logger.info("Model training completed successfully")
        else:
            logger.error(f"Model training failed: {result}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Training error: {e}")
        return jsonify({
            'success': False,
            'error': f'Training failed: {str(e)}'
        }), 500


@app.route('/predict', methods=['POST'])
def predict_performance():
    """Predict video performance."""
    if not predictor_api:
        return jsonify({'error': 'API not initialized'}), 500
    
    try:
        data = request.get_json()
        
        # Handle single video prediction
        if 'video_data' in data:
            video_data = data['video_data']
            result = predictor_api.predict_performance(video_data)
            return jsonify(result)
        
        # Handle batch prediction
        elif 'videos' in data:
            videos = data['videos']
            results = predictor_api.batch_predict(videos)
            return jsonify({
                'success': True,
                'predictions': results,
                'count': len(results)
            })
        
        else:
            return jsonify({
                'success': False,
                'error': 'Missing video_data or videos in request'
            }), 400
            
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({
            'success': False,
            'error': f'Prediction failed: {str(e)}'
        }), 500


@app.route('/predict/sample', methods=['GET'])
def predict_sample():
    """Predict performance for a sample video from the dataset."""
    if not predictor_api:
        return jsonify({'error': 'API not initialized'}), 500
    
    try:
        # Load a sample video from the dataset
        with open('master2.json', 'r') as f:
            data = json.load(f)
        
        # Get random sample or specific index
        index = request.args.get('index', 0, type=int)
        index = min(max(index, 0), len(data) - 1)
        
        sample_video = data[index]
        
        # Make prediction
        result = predictor_api.predict_performance(sample_video)
        
        if result['success']:
            # Add actual values for comparison
            actual_views = sample_video.get('view_count', 0)
            actual_likes = sample_video.get('like_count', 0)
            actual_engagement = actual_likes / max(actual_views, 1)
            
            result['actual'] = {
                'views': actual_views,
                'likes': actual_likes,
                'engagement_rate': actual_engagement
            }
            
            result['video_info'] = {
                'title': sample_video.get('title', ''),
                'duration': sample_video.get('duration', 0),
                'uploader': sample_video.get('uploader', ''),
                'upload_date': sample_video.get('upload_date', ''),
                'video_id': sample_video.get('video_id', '')
            }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Sample prediction error: {e}")
        return jsonify({
            'success': False,
            'error': f'Sample prediction failed: {str(e)}'
        }), 500


@app.route('/benchmark', methods=['GET'])
def benchmark_performance():
    """Benchmark the prediction model performance."""
    if not predictor_api:
        return jsonify({'error': 'API not initialized'}), 500
    
    if not predictor_api.predictor.is_trained:
        return jsonify({'error': 'Model not trained'}), 400
    
    try:
        # Load test data
        with open('master2.json', 'r') as f:
            data = json.load(f)
        
        # Benchmark on first 50 videos
        test_data = data[:50]
        
        start_time = time.time()
        results = predictor_api.batch_predict(test_data)
        total_time = time.time() - start_time
        
        # Calculate statistics
        successful = sum(1 for r in results if r['success'])
        avg_time_ms = (total_time / len(test_data)) * 1000
        
        processing_times = []
        for result in results:
            if result['success']:
                processing_times.append(result['prediction']['processing_time_ms'])
        
        return jsonify({
            'benchmark': {
                'total_videos': len(test_data),
                'successful_predictions': successful,
                'success_rate': successful / len(test_data) * 100,
                'total_time_seconds': total_time,
                'average_time_per_video_ms': avg_time_ms,
                'average_processing_time_ms': sum(processing_times) / len(processing_times) if processing_times else 0,
                'min_processing_time_ms': min(processing_times) if processing_times else 0,
                'max_processing_time_ms': max(processing_times) if processing_times else 0,
                'target_achieved': avg_time_ms < 5.0
            }
        })
        
    except Exception as e:
        logger.error(f"Benchmark error: {e}")
        return jsonify({
            'error': f'Benchmark failed: {str(e)}'
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            'GET /health',
            'GET /info',
            'POST /train',
            'POST /predict',
            'GET /predict/sample',
            'GET /benchmark'
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='TikTok Performance Predictor API')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--model-path', default=MODEL_PATH, help='Path to model file')
    
    args = parser.parse_args()
    
    # Update global model path
    MODEL_PATH = args.model_path
    
    # Initialize API
    initialize_api()
    
    print(f"🚀 TikTok Performance Predictor API")
    print(f"📡 Starting server on http://{args.host}:{args.port}")
    print(f"💾 Model path: {MODEL_PATH}")
    print(f"🤖 Model loaded: {predictor_api.predictor.is_trained if predictor_api else False}")
    print("\n📋 Available endpoints:")
    print("  GET  /health          - Health check")
    print("  GET  /info            - Model information")
    print("  POST /train           - Train model")
    print("  POST /predict         - Predict performance")
    print("  GET  /predict/sample  - Predict sample video")
    print("  GET  /benchmark       - Benchmark performance")
    
    # Start Flask app
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )