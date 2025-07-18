#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Get TikTok URLs from reddit hashtag using improved detection avoidance
"""

import asyncio
import json
import time
import random
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi
from comment_extractor import MS_TOKEN

async def get_reddit_urls(target_count=200):
    """
    Get URLs from reddit-related content with better stealth
    """
    print(f"🔍 Collecting {target_count} reddit-related TikTok URLs...")
    
    urls = set()
    metadata = []
    
    # Add longer delays and randomization
    base_delay = 3
    max_delay = 8
    
    try:
        async with TikTokApi() as api:
            # Use exact same settings as working comment extractor
            await api.create_sessions(
                ms_tokens=[MS_TOKEN], 
                num_sessions=1, 
                sleep_after=3,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            
            print("✅ Session created successfully")
            
            # Try multiple strategies with delays
            strategies = [
                ("hashtag", "reddit"),
                ("hashtag", "askreddit"), 
                ("hashtag", "redditstories"),
                ("search", "reddit stories"),
                ("search", "askreddit"),
                ("search", "reddit storytime")
            ]
            
            for strategy_type, query in strategies:
                if len(urls) >= target_count:
                    break
                    
                print(f"\n🔍 Trying {strategy_type}: {query}")
                strategy_count = 0
                max_per_strategy = min(50, target_count - len(urls))
                
                try:
                    if strategy_type == "hashtag":
                        video_source = api.hashtag(name=query).videos(count=max_per_strategy)
                    else:  # search
                        # Try different search approaches
                        try:
                            video_source = api.search.videos(query, count=max_per_strategy)
                        except:
                            # Fallback search method
                            continue
                    
                    async for video in video_source:
                        if strategy_count >= max_per_strategy:
                            break
                            
                        try:
                            url = f"https://www.tiktok.com/@{video.author.username}/video/{video.id}"
                            
                            if url not in urls:
                                urls.add(url)
                                
                                # Store metadata
                                meta = {
                                    'url': url,
                                    'video_id': video.id,
                                    'username': video.author.username,
                                    'description': video.as_dict.get('desc', ''),
                                    'view_count': video.stats.get('playCount', 0),
                                    'like_count': video.stats.get('diggCount', 0),
                                    'comment_count': video.stats.get('commentCount', 0),
                                    'collection_method': f"{strategy_type}_{query}",
                                    'collected_at': datetime.now().isoformat()
                                }
                                metadata.append(meta)
                                strategy_count += 1
                                
                                if strategy_count % 10 == 0:
                                    print(f"   ✅ Got {strategy_count} URLs from {query}")
                        
                        except Exception as e:
                            print(f"   ⚠️ Error processing video: {e}")
                            continue
                        
                        # Random delay between videos
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                    print(f"   ✅ Collected {strategy_count} URLs from {strategy_type}: {query}")
                    
                except Exception as e:
                    print(f"   ❌ Strategy failed {strategy_type}:{query} - {e}")
                
                # Longer delay between strategies
                if len(urls) < target_count:
                    delay = random.uniform(base_delay, max_delay)
                    print(f"   ⏳ Waiting {delay:.1f} seconds before next strategy...")
                    await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"❌ Session error: {e}")
    
    print(f"\n✅ Total URLs collected: {len(urls)}")
    return urls, metadata

def save_urls(urls, metadata, filename="reddit_urls"):
    """Save URLs and metadata"""
    
    # Save JSON with metadata
    json_data = {
        'collection_summary': {
            'total_urls': len(urls),
            'target': 'reddit_content',
            'collection_date': datetime.now().isoformat(),
            'methods': list(set([m['collection_method'] for m in metadata]))
        },
        'urls': list(urls),
        'metadata': metadata
    }
    
    json_file = f"{filename}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    # Save simple URL list
    txt_file = f"{filename}.txt"
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
    
    # Get reddit URLs
    urls, metadata = await get_reddit_urls(200)
    
    if urls:
        # Save results
        json_file, txt_file = save_urls(urls, metadata)
        
        duration = time.time() - start_time
        print(f"\n🎉 Success! Collected {len(urls)} reddit URLs in {duration/60:.1f} minutes")
        print(f"📁 Files: {json_file}, {txt_file}")
    else:
        print("❌ No URLs collected. Token might need refreshing or TikTok is blocking requests.")

if __name__ == "__main__":
    asyncio.run(main())