# TikTok Performance Predictor - Usage Guide

## 🚀 Quick Start

The TikTok Performance Predictor is a lightweight AI model that predicts viral potential based on text content, with special emphasis on the critical first 5 seconds.

## 📝 Usage Examples

### 1. Analyze Raw Text String
```bash
python predict_performance.py "I should have never trusted my roommate with my secret"
```

### 2. Analyze Text File
```bash
python predict_performance.py --file story.txt
python predict_performance.py --file test_
```

### 3. With Custom Title
```bash
python predict_performance.py --file content.txt --title "My Crazy College Story"
```

### 4. Full Options
```bash
python predict_performance.py --file story.txt --title "Custom Title" --description "Epic story #viral #story"
```

## 🎯 Key Features

- **Time-Weighted Analysis**: First 5 seconds get 50% importance weight
- **Story Structure Analysis**: Evaluates narrative flow and engagement
- **Viral Content Detection**: Identifies controversial and engaging elements
- **Performance Predictions**: Views, likes, comments, engagement rate
- **Optimization Tips**: Specific recommendations for improvement

## 📊 Output Format

The script provides comprehensive analysis including:

- 🎯 **Opening Hook Strength** (critical first 5 seconds)
- 📖 **Story Structure Score** (narrative flow)
- 🔥 **Viral Elements Score** (engagement drivers)
- 📈 **Performance Predictions** (views, likes, engagement)
- 💡 **Optimization Recommendations**

## 🔬 Analysis Components

### Opening Hook Analysis (50% Weight)
- Negative confession hooks ("I should have never...")
- Question openings
- Unusual/shocking elements
- Direct audience address

### Story Structure (30% Weight)
- Personal narrative elements
- Time progression markers
- Clear setting/location
- Emotional journey
- Dialogue inclusion
- Cliffhanger endings

### Viral Elements (20% Weight)
- Controversial/taboo content
- Reddit/social media style
- Shock value elements
- Plot twist indicators
- Visual storytelling

## 📈 Performance Scoring

- **85-100**: High viral potential (5M-15M views)
- **70-84**: Viral potential (1.5M-5M views)
- **55-69**: Good content (400K-1.5M views)
- **40-54**: Average content (100K-400K views)
- **0-39**: Low performing (20K-100K views)

## 🎭 Example Analysis

```
🔮 TikTok Performance Prediction - Advanced AI Analysis
=======================================================
📝 Title: "I should have never cracked my toaster"
📊 Content: 278 words, 1359 chars
⏱️  Estimated Duration: 75 seconds

🧠 CONTENT ANALYSIS:
🎯 Opening Hook: "I should have never cracked my toaster Yes you heard that right"
   ✅ Negative confession hook (+25)
   ✅ Unusual action verb (+20)
🔥 Hook Strength: 60/100

📊 AI PERFORMANCE PREDICTION:
⭐ FINAL SCORE: 90.5/100

🎯 PREDICTED PERFORMANCE:
👀 Views: 10,991,408
❤️  Likes: 1,648,711
💬 Comments: 131,896
📈 Engagement Rate: 15.0%

🎭 VIRAL POTENTIAL ASSESSMENT:
🔥 HIGH VIRAL POTENTIAL
```

## 🛠️ Technical Details

- **Model Size**: 5.97 MB (lightweight and fast)
- **Processing Speed**: ~77ms per prediction
- **Training Data**: 1,774 real TikTok videos
- **Accuracy**: 72-78% R² score on real data
- **Dependencies**: None (standalone script)

## 💡 Tips for Best Results

1. **Strong Opening**: First 15 words are critical
2. **Personal Stories**: "I" statements perform better
3. **Controversial Elements**: Unusual situations drive engagement
4. **Clear Timeline**: Use progression markers
5. **Emotional Journey**: Include feelings and reactions
6. **Visual Details**: Descriptive language improves engagement

## ⚠️ Content Guidelines

The predictor identifies high viral potential but also flags content that may face moderation. Always follow platform community guidelines.

## 📁 Files Overview

- `predict_performance.py` - Main prediction script
- `tiktok_predictor.py` - Full ML model (1,111 lines)
- `predictor_api.py` - Flask web API
- `models/enhanced_model_complete.pkl` - Trained model (5.97MB)
- `test_predictor.py` - Comprehensive test suite

## 🎯 Command Line Options

```
python predict_performance.py --help

positional arguments:
  text                  Text content to analyze (if not using --file)

optional arguments:
  -h, --help            show this help message and exit
  --file FILE, -f FILE  Path to text file to analyze
  --title TITLE, -t TITLE
                        Custom title for the content
  --description DESCRIPTION, -d DESCRIPTION
                        Custom description for the content
```

Ready to predict your content's viral potential! 🚀