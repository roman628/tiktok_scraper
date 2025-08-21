#!/usr/bin/env python3
"""
Test database write functionality
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database_manager import DatabaseOrJsonManager

def test_database_write():
    """Test writing a new video to database"""
    
    # Create config with database enabled
    config = {
        'database': {
            'enabled': True,
            'host': 'localhost',
            'database': 'tiktok_scraper',
            'user': os.environ.get('USER')
        }
    }
    
    # Initialize manager
    manager = DatabaseOrJsonManager(config)
    
    # Create test video data
    test_video = {
        'video_id': '9999999999999999999',
        'url': 'https://www.tiktok.com/@test/video/9999999999999999999',
        'title': 'Test Video from Database Integration',
        'description': 'This is a test video to verify database write',
        'duration': 30,
        'uploader': 'test_user',
        'uploader_id': 'test_user_id',
        'uploader_url': 'https://www.tiktok.com/@test_user',
        'view_count': 1000,
        'like_count': 100,
        'comment_count': 10,
        'repost_count': 5,
        'save_count': 2,
        'share_count': 3,
        'hashtags': ['test', 'database', 'integration'],
        'upload_date': '20250821',
        'timestamp': 1724259600,
        'width': 1920,
        'height': 1080,
        'fps': 30,
        'filesize': 1000000,
        'format': 'mp4',
        'downloaded_at': datetime.now().isoformat(),
        'downloaded_with': 'test_script',
        'platform': 'test',
        'whisper_transcription': 'This is a test transcription',
        'transcription_timestamp': datetime.now().isoformat(),
        'top_comments': [
            {
                'comment_id': 'test_comment_1',
                'username': 'commenter1',
                'display_name': 'Test Commenter 1',
                'comment_text': 'Great video!',
                'like_count': 5,
                'timestamp': 1724259700
            }
        ],
        'comments_extracted': True,
        'comments_extracted_at': datetime.now().isoformat()
    }
    
    # Check if it's a duplicate
    is_dup = manager.is_duplicate(test_video['url'])
    print(f"Is duplicate: {is_dup}")
    
    if not is_dup:
        # Write to database
        result = manager.append_to_master(test_video)
        print(f"Write successful: {result}")
        
        # Verify it's now in database
        is_dup_after = manager.is_duplicate(test_video['url'])
        print(f"Is duplicate after write: {is_dup_after}")
    else:
        print("Test video already exists in database")
    
    # Get statistics
    if hasattr(manager.manager, 'get_statistics'):
        stats = manager.manager.get_statistics()
        print(f"\nDatabase statistics:")
        print(f"  Total videos: {stats.get('total_videos', 0):,}")
        print(f"  Total comments: {stats.get('total_comments', 0):,}")
        print(f"  Total transcriptions: {stats.get('total_transcriptions', 0):,}")

if __name__ == "__main__":
    test_database_write()