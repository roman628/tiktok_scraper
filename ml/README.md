# TikTok Performance Predictor Model

A machine learning model that predicts TikTok video performance scores (0-100) based on transcript analysis and viral pattern recognition.

## 🎯 Overview

The predictor uses an ensemble approach combining Random Forest, XGBoost, and Ridge Regression to analyze transcript features and predict performance. It learns from real TikTok data including views, likes, comments, and engagement patterns.

## 🚀 Quick Start

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install scikit-learn xgboost joblib nltk textstat

# Train the model
python train_ml.py train
```

### Usage

#### Command Line
```bash
# Train model with custom data
python train_ml.py train --data ../data/master2.json --model models/snoo.pkl

# Make a prediction
python train_ml.py predict --text "Your TikTok transcript here"
```

#### Python API
```python
from train_ml import TikTokPerformancePredictor

# Load trained model
predictor = TikTokPerformancePredictor()
predictor.load_model("models/snoo.pkl")

# Predict performance (0-100 score)
score = predictor.predict_score("Your transcript text here...")
print(f"Performance score: {score:.1f}")
```

#### REST API
```bash
# Start the API server
python api.py --port 8080

# Make a prediction
curl -X POST "http://localhost:8080/predict" \
     -H "Content-Type: application/json" \
     -d '{"text": "Your transcript here"}'
```

## 📊 How It Works

### Feature Extraction
The model analyzes transcripts for:
- **Hook Analysis**: First 5 seconds weighted heavily (critical for viewer retention)
- **Emotional Patterns**: Sentiment intensity and emotional journey
- **Viral Phrases**: Learned from high-performing content
- **Story Structure**: Personal narratives, time markers, dialogue
- **Linguistic Features**: Questions, exclamations, readability
- **Comment Alignment**: Patterns that drive engagement

### Performance Scoring
Scores range from 0-100 based on:
- **90-100**: Viral potential (10M+ views)
- **60-89**: High performance (1M-10M views)
- **30-59**: Good performance (100K-1M views)
- **0-29**: Average performance (<100K views)

### Model Architecture
- **Ensemble Model**: Combines 3 algorithms for robustness
- **Feature Engineering**: 140+ features extracted from text
- **Pattern Learning**: Discovers viral patterns from training data
- **TF-IDF Analysis**: Identifies important content themes

## 🛠️ API Endpoints

### POST /predict
Predict performance for a single transcript
```json
{
  "text": "Your transcript text"
}
```

### POST /batch_predict
Predict performance for multiple transcripts
```json
["transcript1", "transcript2", "transcript3"]
```

### GET /health
Check if model is loaded and ready

## 📁 File Structure

```
model/
├── train_ml.py      # Main training and prediction logic
├── api.py          # FastAPI server
├── models/
│   └── snoo.pkl    # Trained model file
└── README.md       # This file
```

## 🔧 Requirements

- Python 3.8+
- 1GB RAM minimum
- Training data in JSON format with TikTok video metadata

## 📝 Notes

- The model learns from actual TikTok performance data
- Predictions improve with more diverse training data
- Hook quality (first 5 seconds) is the strongest predictor
- Model updates automatically discover new viral patterns