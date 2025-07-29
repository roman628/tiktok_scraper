#!/usr/bin/env python3
"""
Simple test to extract Reddit usernames from TikTok data without requiring Reddit API.
This shows what usernames would be found and which subreddits we could discover.
"""

import json
import re
from collections import defaultdict, Counter
from datetime import datetime

def extract_reddit_usernames_from_tiktok_data(tiktok_json_path: str):
    """Extract Reddit usernames mentioned in TikTok video data."""
    
    print(f"🔍 Extracting Reddit usernames from: {tiktok_json_path}")
    
    try:
        with open(tiktok_json_path, 'r', encoding='utf-8') as f:
            tiktok_data = json.load(f)
        
        if not isinstance(tiktok_data, list):
            print("❌ TikTok data is not a list format")
            return []
        
        total_videos = len(tiktok_data)
        print(f"📊 Total videos to analyze: {total_videos:,}")
        
        # Reddit username patterns
        patterns = {
            'u_slash': re.compile(r'u/([a-zA-Z0-9_-]{3,20})', re.IGNORECASE),
            'user_colon': re.compile(r'reddit user[:\s]+"?([a-zA-Z0-9_-]{3,20})"?', re.IGNORECASE),
            'source_reddit': re.compile(r'source[:\s]+reddit[:\s]+([a-zA-Z0-9_-]{3,20})', re.IGNORECASE),
            'reddit_username': re.compile(r'reddit.*?username[:\s]+([a-zA-Z0-9_-]{3,20})', re.IGNORECASE),
            'posted_by': re.compile(r'posted by[:\s]+([a-zA-Z0-9_-]{3,20})', re.IGNORECASE)
        }
        
        found_usernames = set()
        pattern_counts = defaultdict(int)
        failed_extractions = 0
        
        for i, video in enumerate(tiktok_data):
            if i % 1000 == 0:
                print(f"  📹 Processed {i:,}/{total_videos:,} videos...")
            
            try:
                # Search in title, description, and transcription
                search_fields = []
                if 'title' in video and video['title']:
                    search_fields.append(('title', video['title']))
                if 'description' in video and video['description']:
                    search_fields.append(('description', video['description']))
                if 'whisper_transcription' in video and video['whisper_transcription']:
                    search_fields.append(('transcription', video['whisper_transcription']))
                
                # Also search in comments
                if 'top_comments' in video and video['top_comments']:
                    for comment in video['top_comments']:
                        if 'comment_text' in comment and comment['comment_text']:
                            search_fields.append(('comment', comment['comment_text']))
                
                # Apply patterns to all text fields
                for field_name, text in search_fields:
                    for pattern_name, pattern in patterns.items():
                        matches = pattern.findall(text)
                        for username in matches:
                            # Basic filtering
                            username = username.lower().strip()
                            if len(username) >= 3 and username not in ['reddit', 'user', 'source', 'posted']:
                                found_usernames.add(username)
                                pattern_counts[pattern_name] += 1
            
            except Exception as e:
                failed_extractions += 1
                continue
        
        print(f"✅ Extraction complete!")
        print(f"📊 Results:")
        print(f"  - Unique Reddit usernames found: {len(found_usernames)}")
        print(f"  - Total pattern matches: {sum(pattern_counts.values())}")
        print(f"  - Failed extractions: {failed_extractions}")
        
        print(f"\n🎯 Pattern breakdown:")
        for pattern_name, count in pattern_counts.items():
            print(f"  - {pattern_name}: {count}")
        
        return list(found_usernames), dict(pattern_counts)
        
    except Exception as e:
        print(f"❌ Error reading TikTok data: {e}")
        return [], {}

def show_username_samples(usernames, limit=20):
    """Show sample usernames found."""
    print(f"\n📋 Sample usernames found (showing {min(limit, len(usernames))} of {len(usernames)}):")
    for i, username in enumerate(sorted(usernames)[:limit], 1):
        print(f"  {i:2d}. u/{username}")
    
    if len(usernames) > limit:
        print(f"  ... and {len(usernames) - limit} more")

def create_username_file(usernames, filename="extracted_reddit_usernames.txt"):
    """Create a text file with all extracted usernames."""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# Reddit usernames extracted from TikTok data\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total usernames: {len(usernames)}\n\n")
        
        for username in sorted(usernames):
            f.write(f"{username}\n")
    
    print(f"💾 Saved all usernames to: {filename}")

def main():
    """Run the username extraction test."""
    
    print("🎯 Reddit Username Extraction Test")
    print("=" * 50)
    
    # Path to your TikTok data
    tiktok_data_path = "/Users/ethan/tiktok_scraper/master2.json"
    
    # Check if the file exists
    import os
    if not os.path.exists(tiktok_data_path):
        print(f"❌ ERROR: TikTok data file not found: {tiktok_data_path}")
        return
    
    # Extract usernames
    usernames, pattern_counts = extract_reddit_usernames_from_tiktok_data(tiktok_data_path)
    
    if usernames:
        # Show samples
        show_username_samples(usernames, limit=30)
        
        # Create username file
        create_username_file(usernames)
        
        print(f"\n🚀 Next Steps:")
        print(f"1. Set up Reddit API credentials (https://www.reddit.com/prefs/apps/)")
        print(f"2. These {len(usernames)} usernames would be analyzed to discover subreddits")
        print(f"3. The discovered subreddits would be ranked by activity and popularity")
        print(f"4. Popular posts would be scraped from the top discovered subreddits")
        print(f"\n💡 This process would identify the most relevant subreddits based on")
        print(f"   the Reddit users mentioned in your TikTok content!")
        
    else:
        print(f"\n❌ No Reddit usernames found in the TikTok data.")
        print(f"💡 This could mean:")
        print(f"   - The videos don't reference Reddit content")
        print(f"   - The patterns need to be adjusted")
        print(f"   - The data format is different than expected")

if __name__ == "__main__":
    main()