#!/usr/bin/env python3
"""
Test script to verify database integration with collector.py
"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database_manager import DatabaseManager, DatabaseOrJsonManager

def test_database_manager():
    """Test direct database operations"""
    print("Testing DatabaseManager...")
    
    # Initialize database manager
    db = DatabaseManager(
        host="localhost",
        database="tiktok_scraper",
        user=os.environ.get('USER')
    )
    
    # Get statistics
    stats = db.get_statistics()
    print(f"Database Statistics:")
    print(f"  Total videos: {stats.get('total_videos', 0):,}")
    print(f"  Total comments: {stats.get('total_comments', 0):,}")
    print(f"  Total transcriptions: {stats.get('total_transcriptions', 0):,}")
    print(f"  Database size: {stats.get('database_size', 'Unknown')}")
    
    # Test duplicate detection
    test_url = "https://www.tiktok.com/@test/video/7352292119232433451"
    is_dup = db.is_duplicate(test_url)
    print(f"\nDuplicate check for known URL: {is_dup}")
    
    # Test fetching some data
    videos = db.get_videos_for_ml(limit=2)
    print(f"\nFetched {len(videos)} videos for ML")
    if videos:
        print(f"  First video: {videos[0].get('title', 'No title')[:50]}...")
    
    db.close()
    print("\n✓ DatabaseManager test completed")

def test_database_or_json_manager():
    """Test the wrapper that switches between database and JSON"""
    print("\nTesting DatabaseOrJsonManager...")
    
    # Test with database enabled
    config_db = {
        'database': {
            'enabled': True,
            'host': 'localhost',
            'database': 'tiktok_scraper',
            'user': os.environ.get('USER')
        }
    }
    
    manager_db = DatabaseOrJsonManager(config_db)
    print(f"Database mode - is_duplicate check: {manager_db.is_duplicate('test_url')}")
    
    # Test with JSON mode
    config_json = {
        'database': {'enabled': False},
        'output': {'json_output': 'data/master2.json'}
    }
    
    manager_json = DatabaseOrJsonManager(config_json)
    print(f"JSON mode - existing URLs count: {len(manager_json.get_existing_urls())}")
    
    print("\n✓ DatabaseOrJsonManager test completed")

def test_config_integration():
    """Test loading config and using it with database manager"""
    print("\nTesting config integration...")
    
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    
    # Load actual config
    with open('config.toml', 'rb') as f:
        config = tomllib.load(f)
    
    print(f"Database enabled in config: {config.get('database', {}).get('enabled', False)}")
    
    # Create manager based on config
    manager = DatabaseOrJsonManager(config)
    
    if config.get('database', {}).get('enabled', False):
        print("Using PostgreSQL database")
        if hasattr(manager.manager, 'get_statistics'):
            stats = manager.manager.get_statistics()
            print(f"  Videos in DB: {stats.get('total_videos', 0):,}")
    else:
        print("Using JSON file storage")
        print(f"  JSON file: {config.get('output', {}).get('json_output', 'Unknown')}")
    
    print("\n✓ Config integration test completed")

if __name__ == "__main__":
    print("="*50)
    print("TikTok Scraper Database Integration Test")
    print("="*50)
    
    try:
        test_database_manager()
        test_database_or_json_manager()
        test_config_integration()
        
        print("\n" + "="*50)
        print("ALL TESTS PASSED ✓")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)