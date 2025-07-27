#!/usr/bin/env python3
"""
Simple test of the keyword scoring system with minimal dependencies.
This demonstrates the core functionality without requiring external NLP libraries.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

def test_data_loading():
    """Test data loading functionality."""
    print("🔍 Testing data loading...")
    
    try:
        from src.data_loader import TikTokDataLoader
        
        # Test with master2.json
        loader = TikTokDataLoader('/Users/ethan/tiktok_scraper/master2.json')
        loader.load_data(max_videos=3)
        
        videos = loader.get_videos()
        stats = loader.get_statistics()
        
        print(f"✅ Loaded {len(videos)} videos successfully")
        print(f"   Sample video: {videos[0].title[:50]}...")
        print(f"   Average engagement: {stats['avg_engagement']:.6f}")
        print(f"   Videos with transcription: {stats['videos_with_transcription']}")
        
        return videos
        
    except Exception as e:
        print(f"❌ Data loading failed: {e}")
        return None

def test_keyword_extraction_fallback():
    """Test keyword extraction with fallback method."""
    print("\n🔍 Testing keyword extraction (fallback mode)...")
    
    try:
        from src.keyword_extractor import TikTokKeywordExtractor
        
        # This will use fallback extraction since spaCy isn't available
        extractor = TikTokKeywordExtractor()
        
        test_text = "This amazing dance video shows incredible choreography and fantastic moves"
        keywords = extractor.extract_keywords(test_text, top_k=5)
        
        print(f"✅ Extracted {len(keywords)} keywords")
        for i, kw in enumerate(keywords[:3], 1):
            print(f"   {i}. {kw['keyword']} (score: {kw['score']:.2f})")
        
        return keywords
        
    except Exception as e:
        print(f"❌ Keyword extraction failed: {e}")
        return None

def test_basic_scoring():
    """Test basic scoring functionality."""
    print("\n🔍 Testing basic scoring engine...")
    
    try:
        from src.scoring_engine import KeywordScoringEngine
        from src.data_loader import VideoData
        
        # Create test videos
        test_videos = [
            VideoData(
                video_id="1",
                title="Amazing dance tutorial",
                description="Learn this incredible dance routine",
                uploader="dancer",
                view_count=10000,
                like_count=1000,
                comment_count=100,
                repost_count=50,
                duration=30,
                upload_date="20240101",
                top_comments=[{"comment_text": "So good!", "like_count": 10}]
            ),
            VideoData(
                video_id="2", 
                title="Another dance video",
                description="More amazing dance moves",
                uploader="dancer2",
                view_count=5000,
                like_count=500,
                comment_count=50,
                repost_count=25,
                duration=45,
                upload_date="20240102",
                top_comments=[{"comment_text": "Love it!", "like_count": 5}]
            )
        ]
        
        # Initialize scoring engine without sentiment analysis
        engine = KeywordScoringEngine(
            extraction_methods=['rake'],  # Use only RAKE to avoid dependency issues
            sentiment_analysis=False
        )
        
        # Process videos
        engine.process_video_batch(test_videos)
        keyword_scores = engine.calculate_keyword_scores(min_video_count=1)
        
        print(f"✅ Generated scores for {len(keyword_scores)} keywords")
        for i, score in enumerate(keyword_scores[:5], 1):
            print(f"   {i}. {score.keyword} (score: {score.final_score:.3f}, videos: {score.video_count})")
        
        return keyword_scores
        
    except Exception as e:
        print(f"❌ Basic scoring failed: {e}")
        return None

def test_with_real_data():
    """Test with real TikTok data."""
    print("\n🔍 Testing with real TikTok data...")
    
    try:
        videos = test_data_loading()
        if not videos:
            return False
        
        from src.scoring_engine import KeywordScoringEngine
        
        # Use real video data
        engine = KeywordScoringEngine(
            extraction_methods=['rake'],  # Simple method only
            sentiment_analysis=False  # Disable to avoid dependencies
        )
        
        # Process real videos
        engine.process_video_batch(videos)
        keyword_scores = engine.calculate_keyword_scores(min_video_count=1)
        
        print(f"✅ Processed {len(videos)} real videos")
        print(f"✅ Generated scores for {len(keyword_scores)} keywords")
        
        if keyword_scores:
            print("   Top keywords from real data:")
            for i, score in enumerate(keyword_scores[:3], 1):
                print(f"   {i}. '{score.keyword}' - Score: {score.final_score:.3f}")
                print(f"      Videos: {score.video_count}, Avg engagement: {score.avg_engagement:.6f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Real data test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 TikTok Keyword Scoring System - Simple Test")
    print("=" * 60)
    
    # Test individual components
    videos = test_data_loading()
    keywords = test_keyword_extraction_fallback()
    scores = test_basic_scoring()
    
    # Test with real data
    real_test = test_with_real_data()
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    results = {
        "Data Loading": "✅ PASS" if videos else "❌ FAIL",
        "Keyword Extraction": "✅ PASS" if keywords else "❌ FAIL", 
        "Basic Scoring": "✅ PASS" if scores else "❌ FAIL",
        "Real Data Processing": "✅ PASS" if real_test else "❌ FAIL"
    }
    
    for test, result in results.items():
        print(f"{test:<25}: {result}")
    
    all_passed = all("✅" in result for result in results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! The keyword scoring system is working correctly.")
        print("\nNext steps:")
        print("1. Install full dependencies for advanced features:")
        print("   pip install vaderSentiment spacy nltk")
        print("2. Run the full system:")
        print("   python keyword_scorer.py /path/to/master2.json --output results")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)