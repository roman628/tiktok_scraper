#!/usr/bin/env python3
"""
Process a single video for comments and update master.json
"""

import asyncio
import json
import sys
import time
import random
import re
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi

MS_TOKEN = "cwekmq1ZxFChpLaKF4Ww9jeIhoK4-ZsnjwGgIzn0AkFuybnGd5mrrSs1wpGaKhb3sqmr9b_Z_QEaYjuZgbCT7q4YIHPAutbDEmQ3PgZ-UfBNO1CPOnm2RhQcanaBhFuu5dtVZG_mNdnOAAB0dVn84dPb"

def extract_video_id_from_url(url):
    """Extract video ID from TikTok URL"""
    patterns = [
        r'/video/(\d+)',
        r'@[\w\.-]+/video/(\d+)',
        r'vm\.tiktok\.com/([A-Za-z0-9]+)',
        r'vt\.tiktok\.com/([A-Za-z0-9]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

async def extract_video_comments(video_url, max_comments=30):
    """Extract comments from a single TikTok video"""
    
    video_id = extract_video_id_from_url(video_url)
    if not video_id:
        print(f"Could not extract video ID from URL: {video_url}")
        return []
    
    try:
        api = TikTokApi()
        await api.create_sessions(ms_tokens=[MS_TOKEN], num_sessions=1, sleep_after=1)
        video = api.video(id=video_id)
        
        comments_data = []
        comment_count = 0
        
        async for comment in video.comments():
            comment_data = {
                'comment_id': comment.id,
                'username': comment.author.username if hasattr(comment.author, 'username') else 'unknown',
                'display_name': comment.author.nickname if hasattr(comment.author, 'nickname') else 'unknown',
                'comment_text': comment.text,
                'like_count': comment.likes_count,
                'timestamp': getattr(comment, 'create_time', int(time.time())),
            }
            comments_data.append(comment_data)
            comment_count += 1
            
            if comment_count >= max_comments:
                break
        
        await api.close_sessions()
        return comments_data
        
    except Exception as e:
        print(f"Failed to extract comments: {e}")
        return []

async def update_single_video_in_master(video_index, master_json_path="master.json"):
    """Update a single video in master.json with comment data"""
    
    # Load master.json
    master_path = Path(master_json_path)
    if not master_path.exists():
        print(f"❌ {master_json_path} not found!")
        return
    
    with open(master_path, 'r', encoding='utf-8') as f:
        master_data = json.load(f)
    
    if not isinstance(master_data, list) or video_index >= len(master_data):
        print(f"❌ Invalid video index {video_index}")
        return
    
    video_data = master_data[video_index]
    video_url = video_data.get('url', '')
    video_title = video_data.get('title', 'Unknown')
    
    print(f"🔄 Processing video {video_index}: {video_title[:50]}...")
    
    if not video_url:
        print("❌ No URL found for video")
        return
    
    # Check if comments already exist
    if 'comments' in video_data and video_data['comments']:
        print(f"✅ Comments already exist ({len(video_data['comments'])} comments)")
        return
    
    try:
        comments = await extract_video_comments(video_url, max_comments=30)
        
        if comments:
            video_data['comments'] = comments
            video_data['comments_extracted_at'] = datetime.now().isoformat()
            video_data['comments_count_extracted'] = len(comments)
            print(f"✅ Extracted {len(comments)} comments")
        else:
            video_data['comments'] = []
            video_data['comments_extracted_at'] = datetime.now().isoformat()
            video_data['comments_count_extracted'] = 0
            print("❌ No comments extracted")
        
        # Save updated master.json
        with open(master_path, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Updated {master_json_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python process_single_video.py <video_index>")
        print("Example: python process_single_video.py 0")
        return
    
    try:
        video_index = int(sys.argv[1])
        asyncio.run(update_single_video_in_master(video_index))
    except ValueError:
        print("Video index must be a number")

if __name__ == "__main__":
    main()