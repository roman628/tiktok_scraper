#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Reddit hashtag harvester
Specifically collects TikTok URLs from #reddit hashtag
"""

import asyncio
import json
import time
import random
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import MS_TOKEN from comment_extractor
from comment_extractor import MS_TOKEN

async def harvest_reddit_hashtag(target_count=300):
    """
    Harvest URLs specifically from #reddit hashtag
    """
    print(f"🔍 Harvesting {target_count} URLs from #reddit hashtag...")
    
    collected_urls = set()
    url_metadata = []
    
    try:
        async with TikTokApi() as api:
            await api.create_sessions(
                ms_tokens=[MS_TOKEN], 
                num_sessions=1, 
                sleep_after=1,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            
            collected = 0
            async for video in api.hashtag(name="reddit").videos(count=target_count):
                if collected >= target_count:
                    break
                    
                url = f"https://www.tiktok.com/@{video.author.username}/video/{video.id}"
                
                if url not in collected_urls:
                    collected_urls.add(url)
                    
                    # Store metadata
                    metadata = {
                        'url': url,
                        'video_id': video.id,
                        'username': video.author.username,
                        'description': video.as_dict.get('desc', ''),
                        'view_count': video.stats.get('playCount', 0),
                        'like_count': video.stats.get('diggCount', 0),
                        'comment_count': video.stats.get('commentCount', 0),
                        'share_count': video.stats.get('shareCount', 0),
                        'collection_method': 'hashtag_reddit',
                        'hashtag': 'reddit',
                        'collected_at': datetime.now().isoformat()
                    }
                    url_metadata.append(metadata)
                    collected += 1
                    
                    if collected % 25 == 0:
                        print(f"   ✅ Collected {collected} URLs from #reddit")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
                
    except Exception as e:
        print(f"❌ Error collecting from #reddit: {e}")
        return collected_urls, url_metadata
    
    print(f"✅ Successfully collected {len(collected_urls)} URLs from #reddit")
    return collected_urls, url_metadata

def save_results(urls, metadata, prefix="reddit_urls"):
    """
    Save collected URLs and metadata
    """
    # Save JSON with metadata
    json_data = {
        'collection_summary': {
            'total_urls': len(urls),
            'hashtag': 'reddit',
            'collection_date': datetime.now().isoformat()
        },
        'urls': list(urls),
        'url_metadata': metadata
    }
    
    json_file = f"{prefix}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    # Save simple text file
    txt_file = f"{prefix}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for url in sorted(urls):
            f.write(url + '\n')
    
    print(f"💾 Saved {len(urls)} URLs to {json_file} and {txt_file}")
    return json_file, txt_file

async def main():
    if MS_TOKEN == "your_ms_token_here":
        print("❌ Error: You must set your ms_token in comment_extractor.py!")
        return
    
    start_time = time.time()
    
    # Harvest reddit URLs
    urls, metadata = await harvest_reddit_hashtag(300)
    
    # Save results
    json_file, txt_file = save_results(urls, metadata)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n🎉 Completed in {duration/60:.1f} minutes!")
    print(f"📊 Total unique URLs: {len(urls)}")
    print(f"📝 Files created: {json_file}, {txt_file}")

if __name__ == "__main__":
    asyncio.run(main())