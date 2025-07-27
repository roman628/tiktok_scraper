# TikTok Keyword Scoring System

A comprehensive keyword extraction and scoring system designed specifically for TikTok content analysis. This system processes TikTok video data to identify high-performing keywords based on their correlation with engagement metrics, sentiment analysis, and content performance.

## Features

### 🎯 Core Functionality
- **Multi-method keyword extraction** using RAKE, TextRank, TF-IDF, and YAKE algorithms
- **TikTok-optimized sentiment analysis** with platform-specific vocabulary and emoji handling
- **Engagement-weighted scoring** that correlates keywords with video performance metrics
- **Comprehensive stopword filtering** with TikTok-specific terms and contemporary slang
- **Batch processing** for large datasets with memory-efficient streaming

### 🧠 Advanced Features
- **Context-aware analysis** that categorizes content (comedy, dance, education, etc.)
- **Sentiment-keyword correlation** to identify emotionally resonant terms
- **Performance prediction** based on keyword presence and scores
- **Multi-format output** (JSON, CSV) with detailed metadata
- **Comprehensive testing suite** with integration tests

### 📊 Scoring Methodology
The system uses a sophisticated scoring algorithm that combines:
- **Extraction scores** from multiple NLP methods
- **Engagement correlation** (views, likes, comments, reposts)
- **Sentiment weighting** based on comment analysis
- **Frequency normalization** with rarity bonuses
- **Context categorization** for domain-specific insights

## Installation

### Prerequisites
- Python 3.8+
- Required packages listed in `requirements.txt`

### Setup
```bash
# Navigate to the keyword scoring system directory
cd keyword_scoring_system

# Install dependencies
pip install -r requirements.txt

# Download required NLTK data (if needed)
python -c "import nltk; nltk.download('punkt')"

# Install spaCy model (if using advanced extraction)
python -m spacy download en_core_web_sm
```

## Usage

### Command Line Interface

#### Basic Usage
```bash
# Process TikTok data with default settings
python keyword_scorer.py /path/to/master2.json --output results/keyword_scores

# Process limited dataset
python keyword_scorer.py /path/to/master2.json --max-videos 1000 --output results/sample_scores

# Use specific extraction methods
python keyword_scorer.py /path/to/master2.json --methods rake textrank --output results/rake_textrank_scores
```

#### Advanced Options
```bash
# Full feature analysis
python keyword_scorer.py /path/to/master2.json \
    --output results/full_analysis \
    --sentiment \
    --min-engagement 0.01 \
    --min-keyword-score 0.2 \
    --require-transcription \
    --format both

# High-quality dataset processing
python keyword_scorer.py /path/to/master2.json \
    --output results/high_quality \
    --min-video-count 5 \
    --require-comments \
    --batch-size 50
```

#### Analyze Results
```bash
# View top keywords
python keyword_scorer.py analyze results/keyword_scores.json --top-k 50

# Filter by context
python keyword_scorer.py analyze results/keyword_scores.json --filter-context comedy --top-k 20

# High-frequency keywords only
python keyword_scorer.py analyze results/keyword_scores.json --min-videos 10
```

### Python API

#### Basic Processing
```python
from src.scoring_engine import score_keywords

# Simple keyword scoring
keyword_scores = score_keywords(
    json_path='master2.json',
    output_path='results/keywords',
    max_videos=1000
)

# Print top keywords
for i, score in enumerate(keyword_scores[:10], 1):
    print(f"{i}. {score.keyword}: {score.final_score:.3f}")
```

#### Advanced Processing
```python
from src.data_loader import TikTokDataLoader
from src.scoring_engine import KeywordScoringEngine

# Load data with filtering
loader = TikTokDataLoader('master2.json')
loader.load_data(
    max_videos=5000,
    min_engagement=0.005,
    require_transcription=True
)

# Initialize scoring engine
engine = KeywordScoringEngine(
    extraction_methods=['rake', 'textrank', 'yake'],
    sentiment_analysis=True,
    performance_weights={
        'engagement_score': 3.0,
        'view_count': 1.0,
        'like_count': 2.0,
        'comment_count': 2.5,
        'repost_count': 1.5
    }
)

# Process dataset
keyword_scores = engine.process_dataset(loader)

# Save results
engine.save_results(keyword_scores, 'results/advanced_analysis', format='both')
```

#### Individual Component Usage
```python
from src.keyword_extractor import TikTokKeywordExtractor
from src.sentiment_analyzer import TikTokSentimentAnalyzer
from src.data_loader import VideoData

# Keyword extraction
extractor = TikTokKeywordExtractor(methods=['rake', 'textrank'])
keywords = extractor.extract_keywords("Amazing dance tutorial video", top_k=10)

# Sentiment analysis
analyzer = TikTokSentimentAnalyzer()
sentiment = analyzer.analyze_text("This video is absolutely amazing! So good!")
print(f"Sentiment: {sentiment.label} (score: {sentiment.compound:.3f})")

# Comment analysis
comments = [
    {"comment_text": "Love this!", "like_count": 10},
    {"comment_text": "Amazing content", "like_count": 5}
]
comment_sentiment = analyzer.analyze_comments(comments)
```

## Output Format

### JSON Output Structure
```json
{
  "metadata": {
    "total_keywords": 1250,
    "processed_videos": 5000,
    "extraction_methods": ["rake", "textrank", "yake"],
    "performance_weights": {...}
  },
  "keywords": [
    {
      "keyword": "amazing dance",
      "total_score": 45.67,
      "final_score": 52.34,
      "frequency": 78,
      "video_count": 45,
      "avg_engagement": 0.085,
      "avg_views": 125430,
      "avg_likes": 8456,
      "avg_comments": 234,
      "sentiment_score": 0.72,
      "performance_correlation": 0.89,
      "score_per_video": 1.01,
      "rarity_bonus": 0.15,
      "top_videos": ["video_id_1", "video_id_2", ...],
      "context_categories": ["dance", "tutorial"]
    }
  ]
}
```

### Key Metrics Explained

- **total_score**: Raw scoring based on extraction methods and performance
- **final_score**: Adjusted score including sentiment and rarity bonuses
- **frequency**: Total number of times keyword appears across all videos
- **video_count**: Number of unique videos containing the keyword
- **avg_engagement**: Average engagement score of videos with this keyword
- **sentiment_score**: Average sentiment of content containing this keyword
- **performance_correlation**: How strongly this keyword correlates with high performance
- **rarity_bonus**: Bonus for keywords that are rare but highly effective

## Configuration

### Extraction Methods
- **rake**: Rapid Automatic Keyword Extraction - good for phrases
- **textrank**: Graph-based algorithm - identifies central concepts
- **tfidf**: Term frequency-inverse document frequency - finds distinctive terms
- **yake**: Yet Another Keyword Extractor - single-document focused

### Performance Weights
Customize how different metrics influence keyword scoring:
```python
performance_weights = {
    'engagement_score': 3.0,    # Overall engagement (likes+comments+reposts)/views
    'view_count': 1.0,          # Raw view count
    'like_count': 2.0,          # Like count
    'comment_count': 2.5,       # Comment count (highest weight)
    'repost_count': 1.5         # Repost/share count
}
```

### Filtering Options
- **min_engagement**: Minimum engagement rate (default: 0.0)
- **min_keyword_score**: Minimum extraction score (default: 0.1)
- **min_video_count**: Minimum videos per keyword (default: 2)
- **require_transcription**: Only videos with transcription (default: False)
- **require_comments**: Only videos with comments (default: False)

## Testing

### Run Test Suite
```bash
# Run all tests
pytest tests/test_keyword_scoring.py -v

# Run with coverage
pytest tests/test_keyword_scoring.py --cov=src --cov-report=html

# Run specific test class
pytest tests/test_keyword_scoring.py::TestScoringEngine -v
```

### Test Coverage
The test suite covers:
- Data loading and parsing
- Keyword extraction algorithms
- Sentiment analysis accuracy
- Scoring engine functionality
- End-to-end integration
- Error handling and edge cases

## Performance Considerations

### Memory Usage
- **Batch processing**: Use `--batch-size` to control memory usage
- **Streaming**: Large datasets are processed in chunks
- **Filtering**: Apply filters early to reduce processing load

### Processing Speed
- **Method selection**: Fewer extraction methods = faster processing
- **Sentiment analysis**: Disable with `--no-sentiment` for speed
- **Dataset size**: Use `--max-videos` for testing and development

### Optimization Tips
```bash
# Fast processing (trade accuracy for speed)
python keyword_scorer.py data.json --methods rake --no-sentiment --batch-size 200

# Balanced processing
python keyword_scorer.py data.json --methods rake textrank --batch-size 100

# High accuracy (slower)
python keyword_scorer.py data.json --methods rake textrank yake tfidf --sentiment
```

## Troubleshooting

### Common Issues

1. **ImportError for existing modules**
   ```bash
   # Ensure the parent src directory is accessible
   export PYTHONPATH="${PYTHONPATH}:/path/to/tiktok_scraper/src"
   ```

2. **Memory errors with large datasets**
   ```bash
   # Reduce batch size and enable filtering
   python keyword_scorer.py data.json --batch-size 50 --max-videos 1000
   ```

3. **spaCy model not found**
   ```bash
   python -m spacy download en_core_web_sm
   ```

4. **NLTK data missing**
   ```python
   import nltk
   nltk.download('punkt')
   nltk.download('vader_lexicon')
   ```

### Performance Issues
- Use fewer extraction methods for speed
- Disable sentiment analysis for large datasets
- Increase `min_keyword_score` to reduce noise
- Filter videos by engagement to focus on high-quality content

## API Reference

### Main Classes

#### `KeywordScoringEngine`
The main orchestrator for keyword scoring analysis.

**Methods:**
- `process_dataset(data_loader, batch_size=100)` - Process entire dataset
- `calculate_keyword_scores(min_video_count=2)` - Calculate final scores
- `save_results(keyword_scores, output_path, format='json')` - Save results

#### `TikTokDataLoader`
Handles loading and filtering of TikTok JSON data.

**Methods:**
- `load_data(max_videos=None, min_engagement=0.0)` - Load filtered data
- `get_videos()` - Get loaded video list
- `filter_videos(**criteria)` - Apply additional filters
- `get_statistics()` - Get dataset statistics

#### `TikTokKeywordExtractor`
Extracts keywords using multiple NLP methods.

**Methods:**
- `extract_keywords(text, top_k=20)` - Extract from text
- `extract_content_keywords(video_data, top_k=15)` - Extract from video
- `merge_keyword_scores(keyword_results)` - Combine results

#### `TikTokSentimentAnalyzer`
Analyzes sentiment with TikTok-specific optimizations.

**Methods:**
- `analyze_text(text)` - Analyze single text
- `analyze_comments(comments)` - Analyze comment batch
- `analyze_content_sentiment(video_data)` - Full video analysis

## Contributing

### Development Setup
```bash
git clone <repository>
cd keyword_scoring_system
pip install -r requirements.txt
pip install -e .
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings for all public methods
- Write tests for new functionality

### Testing
- Run full test suite before committing
- Add tests for new features
- Ensure 80%+ code coverage
- Test with various dataset sizes

## License

This project is part of the TikTok Scraper system and follows the same licensing terms.

## Changelog

### v1.0.0 (Current)
- Initial implementation with multi-method keyword extraction
- TikTok-optimized sentiment analysis with platform-specific vocabulary
- Engagement-weighted scoring algorithm
- Comprehensive stopword filtering system
- CLI interface with extensive configuration options
- Full test suite with integration tests
- JSON and CSV output formats
- Batch processing for large datasets