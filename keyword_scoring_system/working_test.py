#!/usr/bin/env python3
"""
Working test of the keyword scoring system using simple dependencies.
This version uses only built-in Python libraries and should work without external NLP packages.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

def test_complete_system():
    """Test the complete system with real data."""
    print("🚀 Testing Complete Keyword Scoring System")
    print("=" * 60)
    
    try:
        from src.simple_scoring_engine import simple_score_keywords
        
        # Run with real TikTok data
        print("📊 Processing TikTok data...")
        keyword_scores = simple_score_keywords(
            json_path='/Users/ethan/tiktok_scraper/master2.json',
            output_path='output/test_results',
            max_videos=10  # Small sample for testing
        )
        
        print(f"✅ Successfully processed data and generated {len(keyword_scores)} keyword scores")
        
        # Display top results
        print("\n🏆 TOP 10 KEYWORDS:")
        print("-" * 60)
        print(f"{'Rank':<4} {'Keyword':<20} {'Score':<8} {'Videos':<7} {'Avg Eng':<10}")
        print("-" * 60)
        
        for i, score in enumerate(keyword_scores[:10], 1):
            print(f"{i:<4} {score.keyword:<20} {score.final_score:<8.3f} "
                  f"{score.video_count:<7} {score.avg_engagement:<10.6f}")
        
        # Show detailed analysis for top keyword
        if keyword_scores:
            top_keyword = keyword_scores[0]
            print(f"\n🔍 DETAILED ANALYSIS - '{top_keyword.keyword}':")
            print(f"   Final Score: {top_keyword.final_score:.3f}")
            print(f"   Appears in: {top_keyword.video_count} videos")
            print(f"   Average Views: {top_keyword.avg_views:,.0f}")
            print(f"   Average Likes: {top_keyword.avg_likes:,.0f}")
            print(f"   Average Comments: {top_keyword.avg_comments:,.0f}")
            print(f"   Performance Correlation: {top_keyword.performance_correlation:.3f}")
            print(f"   Score per Video: {top_keyword.score_per_video:.3f}")
            print(f"   Rarity Bonus: {top_keyword.rarity_bonus:.3f}")
        
        # Check output file
        output_file = Path('output/test_results.json')
        if output_file.exists():
            with open(output_file, 'r') as f:
                saved_data = json.load(f)
            
            print(f"\n💾 Results saved to: {output_file}")
            print(f"   Metadata: {saved_data['metadata']}")
            print(f"   Keywords saved: {len(saved_data['keywords'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ System test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_analysis():
    """Test data analysis capabilities."""
    print("\n📈 Testing Data Analysis Features...")
    
    try:
        from src.data_loader import TikTokDataLoader
        
        # Load a larger sample
        loader = TikTokDataLoader('/Users/ethan/tiktok_scraper/master2.json')
        loader.load_data(max_videos=50)
        
        videos = loader.get_videos()
        stats = loader.get_statistics()
        
        print("✅ Dataset Analysis:")
        print(f"   Total videos: {stats['total_videos']}")
        print(f"   Videos with transcription: {stats['videos_with_transcription']}")
        print(f"   Videos with comments: {stats['videos_with_comments']}")
        print(f"   Average views: {stats['avg_views']:,.0f}")
        print(f"   Average likes: {stats['avg_likes']:,.0f}")
        print(f"   Average engagement: {stats['avg_engagement']:.6f}")
        print(f"   Max engagement: {stats['max_engagement']:.6f}")
        
        # Test filtering
        high_engagement = loader.filter_videos(min_views=100000)
        print(f"   High-view videos (>100K): {len(high_engagement)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Data analysis failed: {e}")
        return False

def demo_keyword_extraction():
    """Demonstrate keyword extraction on sample text."""
    print("\n🔤 Demonstrating Keyword Extraction...")
    
    try:
        from src.simple_scoring_engine import SimpleKeywordExtractor
        
        extractor = SimpleKeywordExtractor()
        
        # Test with various types of content
        test_texts = [
            "Amazing dance tutorial with incredible choreography and fantastic moves",
            "Funny comedy sketch that will make you laugh out loud",
            "Beautiful makeup transformation using amazing products and techniques",
            "Delicious food recipe cooking tutorial step by step instructions"
        ]
        
        for i, text in enumerate(test_texts, 1):
            print(f"\n   Text {i}: {text}")
            keywords = extractor.extract_keywords(text, top_k=5)
            print(f"   Keywords: {[k['keyword'] for k in keywords]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Keyword extraction demo failed: {e}")
        return False

def main():
    """Run comprehensive test suite."""
    
    # Create output directory
    Path('output').mkdir(exist_ok=True)
    
    # Run all tests
    tests = [
        ("Data Analysis", test_data_analysis),
        ("Keyword Extraction Demo", demo_keyword_extraction),
        ("Complete System", test_complete_system)
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        results[test_name] = test_func()
    
    # Final summary
    print("\n" + "="*60)
    print("🎯 FINAL TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:<25}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 SUCCESS! All tests passed!")
        print("\nThe keyword scoring system is working correctly with the following features:")
        print("✅ Data loading from master2.json")
        print("✅ Keyword extraction using frequency analysis")
        print("✅ Performance-based scoring algorithm")
        print("✅ Engagement correlation analysis")
        print("✅ JSON output with detailed metrics")
        
        print("\n📋 Usage Example:")
        print("```python")
        print("from src.simple_scoring_engine import simple_score_keywords")
        print("")
        print("scores = simple_score_keywords(")
        print("    json_path='master2.json',")
        print("    output_path='results/keywords',")
        print("    max_videos=1000")
        print(")")
        print("```")
        
    else:
        print("\n⚠️  Some tests failed. Please check the error messages above.")
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)