#!/usr/bin/env python3
"""
TikTok Comment Extractor using TikTokApi
Extracts comments from TikTok videos and updates master.json
"""

import asyncio
import json
import time
import random
import re
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi

# You must get this from your browser - see instructions in comments
MS_TOKEN = "E5YjZRblKUKYUznFcdR_Q1REZ79PHQ4C1HU1lOXytVIXxhE3sUfcuHgbKqdSIGK0w5JAsIJuIS_n0TZ4cYwKIgze_uSyIc2ciI8g4sWlwujWt2ACAtaAbdqhOmseR4LhGF--DHs8Jx1K_UjCSnZifnb-"

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

async def extract_comment_replies(comment, max_replies=5):
    """Extract replies to a comment (limited by TikTok API)"""
    replies = []
    try:
        reply_count = 0
        async for reply in comment.replies():
            reply_data = {
                'reply_id': reply.id,
                'username': reply.author.username if hasattr(reply.author, 'username') else 'unknown',
                'display_name': reply.author.nickname if hasattr(reply.author, 'nickname') else 'unknown',
                'reply_text': reply.text,
                'like_count': reply.likes_count,
                'timestamp': getattr(reply, 'create_time', int(time.time())),
                'replying_to': getattr(reply, 'reply_to_reply_id', "")
            }
            replies.append(reply_data)
            reply_count += 1
            
            if reply_count >= max_replies:
                break
                
    except Exception as e:
        print(f"Failed to get replies: {e}")
    
    return replies

async def extract_video_comments(video_url, max_comments=50):
    """
    Extract comments from a single TikTok video
    
    Args:
        video_url: Full TikTok video URL
        max_comments: Maximum comments to extract (TikTok typically limits to ~50)
    
    Returns:
        List of comment dictionaries
    """
    
    # Extract video ID from URL
    video_id = extract_video_id_from_url(video_url)
    if not video_id:
        print(f"Could not extract video ID from URL: {video_url}")
        return []
    
    try:
        # Initialize API with browser automation
        api = TikTokApi()
        
        # Create session with ms_token
        await api.create_sessions(
            ms_tokens=[MS_TOKEN], 
            num_sessions=1, 
            sleep_after=1
        )
        
        # Get video object
        video = api.video(id=video_id)
        
        # Extract comments with retry logic
        comments_data = []
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                comment_count = 0
                async for comment in video.comments():
                    comment_data = {
                        'video_id': video_id,
                        'video_url': video_url,
                        'comment_id': comment.id,
                        'username': comment.author.username if hasattr(comment.author, 'username') else 'unknown',
                        'display_name': comment.author.nickname if hasattr(comment.author, 'nickname') else 'unknown',
                        'profile_pic_url': getattr(comment.author, 'avatar_thumb', {}).get('url_list', [''])[0] if hasattr(comment.author, 'avatar_thumb') else "",
                        'comment_text': comment.text,
                        'like_count': comment.likes_count,
                        'reply_count': getattr(comment, 'reply_comment_total', 0),
                        'timestamp': getattr(comment, 'create_time', int(time.time())),
                        'is_verified': getattr(comment.author, 'verification_type', 0) > 0 if hasattr(comment, 'author') else False,
                        'follower_count': getattr(comment.author, 'follower_count', 0) if hasattr(comment, 'author') else 0,
                        'following_count': getattr(comment.author, 'following_count', 0) if hasattr(comment, 'author') else 0,
                        'total_favorited': getattr(comment.author, 'total_favorited', 0) if hasattr(comment, 'author') else 0,
                    }
                    
                    # Get replies if they exist (limited to ~5 per comment)
                    try:
                        comment_data['replies'] = await extract_comment_replies(comment)
                    except:
                        comment_data['replies'] = []
                    
                    comments_data.append(comment_data)
                    comment_count += 1
                    
                    if comment_count >= max_comments:
                        break
                
                break  # Success, exit retry loop
                
            except Exception as e:
                retry_count += 1
                print(f"Retry {retry_count} for {video_url}: {e}")
                await asyncio.sleep(random.uniform(2, 5))
        
        await api.close_sessions()
        return comments_data
        
    except Exception as e:
        print(f"Failed to extract comments from {video_url}: {e}")
        return []

async def update_master_json_with_comments(master_json_path="master.json", max_comments=50):
    """
    Update master.json with comment data for each video
    """
    
    # Check if MS_TOKEN is set
    if MS_TOKEN == "your_ms_token_here":
        print("❌ Error: You must set your ms_token in the script!")
        print("🔧 Instructions:")
        print("1. Open Chrome/Firefox and go to tiktok.com")
        print("2. Open Developer Tools (F12)")
        print("3. Go to Application/Storage tab > Cookies > https://www.tiktok.com")
        print("4. Find 'msToken' cookie and copy its value")
        print("5. Replace MS_TOKEN in this script with the copied value")
        return
    
    # Load existing master.json
    master_path = Path(master_json_path)
    if not master_path.exists():
        print(f"❌ {master_json_path} not found!")
        return
    
    try:
        with open(master_path, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
        
        if not isinstance(master_data, list):
            print("❌ master.json should contain a list of video metadata")
            return
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {master_json_path}: {e}")
        return
    
    print(f"📊 Processing {len(master_data)} videos from {master_json_path}")
    
    updated_count = 0
    failed_count = 0
    
    # Process each video
    for i, video_data in enumerate(master_data):
        video_url = video_data.get('url', '')
        video_title = video_data.get('title', 'Unknown')
        
        print(f"\n🔄 Processing {i+1}/{len(master_data)}: {video_title[:50]}...")
        
        if not video_url:
            print(f"   ⚠️  No URL found for video")
            failed_count += 1
            continue
        
        # Check if comments already exist
        if 'comments' in video_data and video_data['comments']:
            print(f"   ✅ Comments already exist ({len(video_data['comments'])} comments), skipping")
            continue
        
        try:
            # Extract comments
            comments = await extract_video_comments(video_url, max_comments)
            
            if comments:
                video_data['comments'] = comments
                video_data['comments_extracted_at'] = datetime.now().isoformat()
                video_data['comments_count_extracted'] = len(comments)
                updated_count += 1
                print(f"   ✅ Extracted {len(comments)} comments")
            else:
                video_data['comments'] = []
                video_data['comments_extracted_at'] = datetime.now().isoformat()
                video_data['comments_count_extracted'] = 0
                failed_count += 1
                print(f"   ❌ No comments extracted")
            
            # Save progress after each video
            with open(master_path, 'w', encoding='utf-8') as f:
                json.dump(master_data, f, indent=2, ensure_ascii=False)
            
            # Random delay between videos (5-12 seconds)
            delay = random.uniform(5, 12)
            print(f"   ⏳ Waiting {delay:.1f} seconds...")
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"   ❌ Error extracting comments: {e}")
            video_data['comments'] = []
            video_data['comments_extracted_at'] = datetime.now().isoformat()
            video_data['comments_error'] = str(e)
            failed_count += 1
    
    # Final save
    with open(master_path, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Comment extraction completed!")
    print(f"✅ Successfully updated: {updated_count} videos")
    print(f"❌ Failed: {failed_count} videos")
    print(f"📄 Updated file: {master_path}")

async def extract_comments_for_single_video(video_url, max_comments=50):
    """
    Extract comments for a single video URL (for testing)
    """
    
    if MS_TOKEN == "your_ms_token_here":
        print("❌ Error: You must set your ms_token in the script!")
        return []
    
    print(f"🔍 Extracting comments from: {video_url}")
    comments = await extract_video_comments(video_url, max_comments)
    
    if comments:
        print(f"✅ Extracted {len(comments)} comments")
        # Save to file for inspection
        output_file = f"comments_{int(time.time())}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comments, f, indent=2, ensure_ascii=False)
        print(f"📄 Comments saved to: {output_file}")
    else:
        print("❌ No comments extracted")
    
    return comments

def main():
    """Main function - choose your operation"""
    import sys
    
    if len(sys.argv) > 1:
        # Single video mode
        video_url = sys.argv[1]
        asyncio.run(extract_comments_for_single_video(video_url))
    else:
        # Update master.json mode
        asyncio.run(update_master_json_with_comments())

if __name__ == "__main__":
    main()