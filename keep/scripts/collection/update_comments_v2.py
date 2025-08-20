#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update master2.json with comments from TikTok videos
Reads master2.json, extracts URLs, fetches comments, and updates the same file
"""

import json
import sys
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi
import re

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Get MS_TOKEN from comment_extractor
from comment_extractor import MS_TOKEN, extract_video_id_from_url, extract_comment_replies

async def extract_video_comments_no_save(video_url, max_comments=10):
    """
    Extract comments from a TikTok video without saving to file
    """
    try:
        video_id = extract_video_id_from_url(video_url)
        if not video_id:
            print(f"❌ Could not extract video ID from URL: {video_url}")
            return []
        
        async with TikTokApi() as api:
            await api.create_sessions(
                ms_tokens=[MS_TOKEN], 
                num_sessions=1, 
                sleep_after=1,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            
            try:
                comments = []
                async for comment in api.video(id=video_id).comments(count=max_comments):
                    # Extract comment data
                    comment_data = {
                        "comment_id": comment.id,
                        "username": comment.as_dict.get("user", {}).get("unique_id", "unknown"),
                        "display_name": comment.as_dict.get("user", {}).get("nickname", "unknown"),
                        "comment_text": comment.as_dict.get("text", ""),
                        "like_count": comment.as_dict.get("digg_count", 0),
                        "timestamp": comment.as_dict.get("create_time", 0)
                    }
                    
                    # Get replies if they exist
                    reply_count = comment.as_dict.get("reply_comment_count", 0)
                    if reply_count > 0:
                        replies = await extract_comment_replies(comment, max_replies=3)
                        if replies:
                            comment_data["replies"] = replies
                            comment_data["reply_count"] = len(replies)
                    
                    comments.append(comment_data)
                    
                    if len(comments) >= max_comments:
                        break
                
                return comments
                
            except Exception as e:
                print(f"❌ Error fetching comments: {e}")
                return []
    
    except Exception as e:
        print(f"❌ Failed to extract comments: {e}")
        return []

def update_json_with_comments(json_file="master2.json", max_comments=10, delay=2):
    """
    Read JSON file, update each item with comments from its URL
    """
    
    # Load existing data
    file_path = Path(json_file)
    if not file_path.exists():
        print(f"❌ File not found: {json_file}")
        return False
    
    print(f"📂 Loading data from: {json_file}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]  # Convert single object to list
            
        print(f"✅ Loaded {len(data)} videos")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {json_file}: {e}")
        return False
    
    # Process each video
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for i, item in enumerate(data, 1):
        url = item.get('url', '')
        
        if not url:
            print(f"⚠️  [{i}/{len(data)}] No URL found, skipping")
            skipped_count += 1
            continue
        
        # Check if comments already exist
        existing_comments = item.get('top_comments', [])
        if existing_comments and len(existing_comments) > 0:
            print(f"✓ [{i}/{len(data)}] Already has {len(existing_comments)} comments, skipping")
            skipped_count += 1
            continue
        
        print(f"\n🔍 [{i}/{len(data)}] Processing: {url}")
        print(f"   Title: {item.get('title', 'Unknown')[:60]}...")
        
        try:
            # Extract comments (run async function)
            comments = asyncio.run(extract_video_comments_no_save(url, max_comments))
            
            if comments:
                # Update the item with comments
                item['top_comments'] = comments
                print(f"   ✅ Added {len(comments)} comments")
                updated_count += 1
            else:
                print(f"   ⚠️  No comments found")
                item['top_comments'] = []
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            item['top_comments'] = []
            failed_count += 1
        
        # Save progress every 10 videos
        if i % 10 == 0:
            print(f"\n💾 Saving progress (updated {updated_count} so far)...")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Add delay between requests to avoid rate limiting
        if i < len(data):
            print(f"   ⏳ Waiting {delay} seconds...")
            time.sleep(delay)
    
    # Save final data
    print(f"\n💾 Saving final data to: {json_file}")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Summary
    print(f"\n✅ Update complete!")
    print(f"   📊 Total videos: {len(data)}")
    print(f"   ✅ Updated: {updated_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   💾 Updated file: {json_file}")
    
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Update master2.json with TikTok comments")
    parser.add_argument("-f", "--file", default="master2.json", 
                       help="JSON file to update (default: master2.json)")
    parser.add_argument("-c", "--comments", type=int, default=10,
                       help="Maximum comments per video (default: 10)")
    parser.add_argument("-d", "--delay", type=float, default=2,
                       help="Delay between requests in seconds (default: 2)")
    
    args = parser.parse_args()
    
    success = update_json_with_comments(
        json_file=args.file,
        max_comments=args.comments,
        delay=args.delay
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()