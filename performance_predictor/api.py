#!/usr/bin/env python3
"""
TikTok Performance Predictor API

A simple FastAPI server that serves TikTok performance predictions.
This solves the portability issue by providing a simple HTTP interface.

Usage:
    uvicorn api:app --reload

Example:
    curl -X POST "http://localhost:8000/predict" \
         -H "Content-Type: application/json" \
         -d '{"text": "your transcript here"}'
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from typing import Optional
import os
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import the predictor classes at module level so pickle can find them
from train_mrbeast import TikTokPerformancePredictor, TranscriptFeatureExtractor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TikTok Performance Predictor API",
    description="Predict TikTok video performance from transcript text",
    version="1.0.0"
)

# Global model instance
predictor = None

class PredictionRequest(BaseModel):
    text: str
    
class PredictionResponse(BaseModel):
    score: float
    confidence: str
    text_length: int

@app.on_event("startup")
async def load_model():
    """Load the TikTok predictor model at startup."""
    global predictor
    
    try:
        
        # Look for model file
        possible_paths = [
            "/Users/ethan/tiktok_scraper/models/mrbeast.pkl",
            "./models/mrbeast.pkl",
            "../models/mrbeast.pkl",
            "models/mrbeast.pkl"
        ]
        
        model_path = None
        for path in possible_paths:
            if os.path.exists(path):
                model_path = path
                break
        
        if not model_path:
            raise FileNotFoundError("Could not find model file")
        
        # Load the model
        predictor = TikTokPerformancePredictor()
        predictor.load_model(model_path)
        
        logger.info(f"Model loaded successfully from {model_path}")
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise e

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "message": "TikTok Performance Predictor API",
        "version": "1.0.0",
        "endpoints": {
            "predict": "POST /predict - Get performance prediction for text",
            "health": "GET /health - Check API health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {
        "status": "healthy",
        "model_loaded": True
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict_performance(request: PredictionRequest):
    """Predict TikTok performance from transcript text."""
    
    # Check if model is loaded
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Validate input
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(request.text) > 10000:  # Reasonable limit
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")
    
    try:
        # Get prediction
        score = predictor.predict_score(request.text.strip())
        
        # Determine confidence based on text length and score
        text_length = len(request.text.split())
        
        if text_length < 10:
            confidence = "low"
        elif text_length < 50:
            confidence = "medium"
        else:
            confidence = "high"
            
        # Adjust confidence based on score extremes
        if score < 5 or score > 95:
            confidence = "medium"  # Extreme scores might be less reliable
        
        return PredictionResponse(
            score=round(score, 1),
            confidence=confidence,
            text_length=text_length
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed")

@app.post("/batch_predict")
async def batch_predict(texts: list[str]):
    """Predict performance for multiple texts at once."""
    
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    if len(texts) > 100:  # Reasonable batch limit
        raise HTTPException(status_code=400, detail="Too many texts (max 100)")
    
    results = []
    for i, text in enumerate(texts):
        if not text or not text.strip():
            results.append({"error": "Empty text", "index": i})
            continue
            
        try:
            score = predictor.predict_score(text.strip())
            results.append({
                "score": round(score, 1),
                "index": i,
                "text_length": len(text.split())
            })
        except Exception as e:
            results.append({"error": str(e), "index": i})
    
    return {"predictions": results}

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTok Performance Predictor API")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()
    
    print(f"Starting TikTok Performance Predictor API on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)