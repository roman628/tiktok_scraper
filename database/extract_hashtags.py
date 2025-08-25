#!/usr/bin/env python3
"""
Extract hashtags from video titles and descriptions and populate the hashtags tables.
Can be run as a one-time migration or integrated into the pipeline.
"""

import re
import psycopg2
from psycopg2.extras import RealDictCursor
import tomllib
from pathlib import Path
from typing import List, Set

def extract_hashtags_from_text(text: str) -> List[str]:
    """Extract hashtags from text using regex."""
    if not text:
        return []
    
    # Find all hashtags (# followed by word characters, allowing Unicode)
    # This regex captures hashtags while handling edge cases
    hashtag_pattern = r'#[A-Za-z0-9_\u00C0-\u00FF\u0100-\u017F\u0180-\u024F\u1E00-\u1EFF]+'
    hashtags = re.findall(hashtag_pattern, text)
    
    # Clean and dedupe
    cleaned_hashtags = []
    seen = set()
    for tag in hashtags:
        # Remove the # and convert to lowercase for deduplication
        tag_lower = tag[1:].lower()
        if tag_lower and tag_lower not in seen:
            cleaned_hashtags.append(tag[1:])  # Store without #
            seen.add(tag_lower)
    
    return cleaned_hashtags

def get_database_connection():
    """Get database connection from config.toml."""
    config_path = Path(__file__).parent.parent / 'config.toml'
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    
    db_config = config['database']
    return psycopg2.connect(
        host=db_config['host'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config.get('password', ''),
        cursor_factory=RealDictCursor
    )

def process_video_hashtags(cursor, video_id: int, hashtags: List[str]):
    """Insert hashtags and link them to the video."""
    if not hashtags:
        return
    
    for hashtag in hashtags:
        # Insert hashtag if it doesn't exist
        cursor.execute("""
            INSERT INTO hashtags (tag) 
            VALUES (%s) 
            ON CONFLICT (tag) DO NOTHING
            RETURNING id
        """, (hashtag,))
        
        result = cursor.fetchone()
        if result:
            hashtag_id = result['id']
        else:
            # Hashtag already exists, get its ID
            cursor.execute("SELECT id FROM hashtags WHERE tag = %s", (hashtag,))
            hashtag_id = cursor.fetchone()['id']
        
        # Link video to hashtag
        cursor.execute("""
            INSERT INTO video_hashtags (video_id, hashtag_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (video_id, hashtag_id))

def extract_all_hashtags():
    """Extract hashtags from all videos in the database."""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    try:
        # Get all videos
        print("Fetching all videos...")
        cursor.execute("""
            SELECT id, title, description 
            FROM videos 
            ORDER BY id
        """)
        videos = cursor.fetchall()
        print(f"Found {len(videos)} videos to process")
        
        # Process each video
        processed = 0
        hashtags_found = 0
        
        for video in videos:
            # Combine title and description for hashtag extraction
            combined_text = f"{video['title'] or ''} {video['description'] or ''}"
            hashtags = extract_hashtags_from_text(combined_text)
            
            if hashtags:
                process_video_hashtags(cursor, video['id'], hashtags)
                hashtags_found += len(hashtags)
                
            processed += 1
            if processed % 100 == 0:
                conn.commit()  # Commit periodically
                print(f"Processed {processed}/{len(videos)} videos, found {hashtags_found} hashtag instances")
        
        # Final commit
        conn.commit()
        
        # Get statistics
        cursor.execute("SELECT COUNT(DISTINCT tag) FROM hashtags")
        unique_hashtags = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) FROM video_hashtags")
        total_links = cursor.fetchone()['count']
        
        print("\n" + "="*60)
        print("Hashtag Extraction Complete!")
        print("="*60)
        print(f"Videos processed: {processed}")
        print(f"Unique hashtags: {unique_hashtags}")
        print(f"Total video-hashtag links: {total_links}")
        
        # Show top hashtags
        print("\nTop 10 hashtags:")
        cursor.execute("""
            SELECT h.tag, COUNT(vh.video_id) as video_count
            FROM hashtags h
            JOIN video_hashtags vh ON h.id = vh.hashtag_id
            GROUP BY h.id, h.tag
            ORDER BY video_count DESC
            LIMIT 10
        """)
        
        for row in cursor.fetchall():
            print(f"  #{row['tag']}: {row['video_count']} videos")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def extract_and_save_hashtags_for_video(cursor, video_id: int, title: str, description: str) -> List[str]:
    """
    Extract hashtags for a single video and save to database.
    For integration into collector.py.
    
    Args:
        cursor: Database cursor
        video_id: Database video ID (not TikTok video ID)
        title: Video title
        description: Video description
        
    Returns:
        List of hashtags found
    """
    combined_text = f"{title or ''} {description or ''}"
    hashtags = extract_hashtags_from_text(combined_text)
    
    if hashtags:
        process_video_hashtags(cursor, video_id, hashtags)
    
    return hashtags

if __name__ == "__main__":
    extract_all_hashtags()