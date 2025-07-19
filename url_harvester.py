#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok URL Harvester
Collects TikTok video URLs using multiple methods: trending, hashtags, users, and searches
Uses existing TikTokApi infrastructure with ms_token authentication
"""

import asyncio
import json
import time
import random
import re
from pathlib import Path
from datetime import datetime
from TikTokApi import TikTokApi
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import MS_TOKEN from comment_extractor
from comment_extractor import MS_TOKEN

class TikTokURLHarvester:
    """
    Harvest TikTok URLs using multiple collection strategies
    """
    
    def __init__(self, ms_token=MS_TOKEN, max_urls_per_method=500):
        self.ms_token = ms_token
        self.max_urls_per_method = max_urls_per_method
        self.collected_urls = set()  # Use set to avoid duplicates
        self.url_metadata = []  # Store URLs with metadata
        
        # Popular hashtags for harvesting
        self.trending_hashtags = [
            'fyp', 'foryou', 'viral', 'trending', 'xyzbca', 'foryoupage',
            'comedy', 'funny', 'meme', 'relatable', 'storytime', 'pov',
            'aesthetic', 'lifestyle', 'motivation', 'inspiration', 'facts',
            'relationship', 'dating', 'love', 'breakup', 'toxic', 'redflags',
            'cooking', 'recipe', 'food', 'foodtok', 'health', 'fitness',
            'skincare', 'makeup', 'fashion', 'ootd', 'style', 'haul',
            'diy', 'crafts', 'lifehack', 'tips', 'howto', 'tutorial',
            'dance', 'music', 'singing', 'art', 'drawing', 'painting',
            'gaming', 'twitch', 'anime', 'marvel', 'disney', 'movies',
            'books', 'booktok', 'reading', 'writing', 'poetry', 'quotes',
            'school', 'college', 'work', 'career', 'money', 'business',
            'travel', 'adventure', 'nature', 'photography', 'sunset',
            'pets', 'dogs', 'cats', 'animals', 'cute', 'wholesome',
            'mystery', 'scary', 'horror', 'paranormal', 'conspiracy',
            'reddit', 'askreddit', 'storytime', 'drama', 'tea', 'gossip'
        ]
        
        # Popular search terms
        self.search_terms = [
            'viral video', 'funny moment', 'epic fail', 'plot twist',
            'satisfying', 'oddly satisfying', 'life hack', 'mind blown',
            'you won\'t believe', 'wait for it', 'watch till the end',
            'part 2', 'story time', 'green screen', 'duet this',
            'try not to laugh', 'reaction', 'behind the scenes',
            'day in my life', 'get ready with me', 'what I eat',
            'morning routine', 'night routine', 'self care',
            'transformation', 'before and after', 'glow up',
            'outfit of the day', 'room tour', 'apartment tour',
            'cooking with me', 'baking', 'recipe', 'food review',
            'product review', 'unboxing', 'haul', 'try on',
            'workout', 'gym', 'fitness motivation', 'weight loss',
            'skincare routine', 'makeup tutorial', 'hair care',
            'study with me', 'productivity', 'motivation', 'success',
            'small business', 'entrepreneur', 'side hustle', 'passive income'
        ]
        
        # Target user types (we'll search for these patterns)
        self.user_patterns = [
            'comedy', 'funny', 'meme', 'viral', 'trending',
            'lifestyle', 'aesthetic', 'motivation', 'inspiration',
            'food', 'cooking', 'recipe', 'chef', 'baker',
            'fashion', 'style', 'outfit', 'ootd', 'haul',
            'beauty', 'makeup', 'skincare', 'hair', 'nails',
            'fitness', 'gym', 'workout', 'health', 'wellness',
            'dance', 'music', 'singing', 'art', 'creative',
            'gaming', 'gamer', 'streamer', 'anime', 'nerd',
            'book', 'reading', 'writer', 'poetry', 'quotes',
            'travel', 'adventure', 'nature', 'photography',
            'pets', 'dogs', 'cats', 'animals', 'cute',
            'mystery', 'horror', 'scary', 'paranormal',
            'reddit', 'story', 'drama', 'tea', 'gossip'
        ]

    async def collect_trending_urls(self, count=200):
        """
        Collect URLs from trending videos
        """
        print(f"🔥 Collecting {count} trending video URLs...")
        collected = 0
        
        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                )
                
                async for video in api.trending.videos(count=count):
                    if collected >= count:
                        break
                        
                    url = f"https://www.tiktok.com/@{video.author.username}/video/{video.id}"
                    
                    if url not in self.collected_urls:
                        self.collected_urls.add(url)
                        
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
                            'collection_method': 'trending',
                            'collected_at': datetime.now().isoformat()
                        }
                        self.url_metadata.append(metadata)
                        collected += 1
                        
                        if collected % 50 == 0:
                            print(f"   ✅ Collected {collected} trending URLs")
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            print(f"❌ Error collecting trending URLs: {e}")
        
        print(f"✅ Collected {collected} trending URLs")
        return collected

    async def collect_hashtag_urls(self, count=300):
        """
        Collect URLs from popular hashtags
        """
        print(f"#️⃣ Collecting {count} hashtag video URLs...")
        collected = 0
        hashtags_used = 0
        
        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                )
                
                # Shuffle hashtags for variety
                hashtags = random.sample(self.trending_hashtags, min(len(self.trending_hashtags), 20))
                
                for hashtag in hashtags:
                    if collected >= count:
                        break
                        
                    hashtags_used += 1
                    hashtag_collected = 0
                    target_per_hashtag = min(25, (count - collected))
                    
                    print(f"   🔍 Harvesting #{hashtag} (target: {target_per_hashtag})")
                    
                    try:
                        async for video in api.hashtag(name=hashtag).videos(count=target_per_hashtag):
                            if collected >= count or hashtag_collected >= target_per_hashtag:
                                break
                                
                            url = f"https://www.tiktok.com/@{video.author.username}/video/{video.id}"
                            
                            if url not in self.collected_urls:
                                self.collected_urls.add(url)
                                
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
                                    'collection_method': f'hashtag_{hashtag}',
                                    'hashtag': hashtag,
                                    'collected_at': datetime.now().isoformat()
                                }
                                self.url_metadata.append(metadata)
                                collected += 1
                                hashtag_collected += 1
                            
                            await asyncio.sleep(0.1)
                            
                    except Exception as e:
                        print(f"   ⚠️ Error with hashtag #{hashtag}: {e}")
                        continue
                    
                    print(f"   ✅ Got {hashtag_collected} URLs from #{hashtag}")
                    
                    # Delay between hashtags
                    await asyncio.sleep(random.uniform(2, 5))
                    
        except Exception as e:
            print(f"❌ Error collecting hashtag URLs: {e}")
        
        print(f"✅ Collected {collected} hashtag URLs from {hashtags_used} hashtags")
        return collected

    async def collect_search_urls(self, count=200):
        """
        Collect URLs from search terms
        """
        print(f"🔍 Collecting {count} search result URLs...")
        collected = 0
        searches_used = 0
        
        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                )
                
                # Shuffle search terms for variety
                search_terms = random.sample(self.search_terms, min(len(self.search_terms), 15))
                
                for term in search_terms:
                    if collected >= count:
                        break
                        
                    searches_used += 1
                    search_collected = 0
                    target_per_search = min(20, (count - collected))
                    
                    print(f"   🔍 Searching '{term}' (target: {target_per_search})")
                    
                    try:
                        async for video in api.search.videos(term, count=target_per_search):
                            if collected >= count or search_collected >= target_per_search:
                                break
                                
                            url = f"https://www.tiktok.com/@{video.author.username}/video/{video.id}"
                            
                            if url not in self.collected_urls:
                                self.collected_urls.add(url)
                                
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
                                    'collection_method': f'search_{term.replace(" ", "_")}',
                                    'search_term': term,
                                    'collected_at': datetime.now().isoformat()
                                }
                                self.url_metadata.append(metadata)
                                collected += 1
                                search_collected += 1
                            
                            await asyncio.sleep(0.1)
                            
                    except Exception as e:
                        print(f"   ⚠️ Error with search '{term}': {e}")
                        continue
                    
                    print(f"   ✅ Got {search_collected} URLs from '{term}'")
                    
                    # Delay between searches
                    await asyncio.sleep(random.uniform(3, 6))
                    
        except Exception as e:
            print(f"❌ Error collecting search URLs: {e}")
        
        print(f"✅ Collected {collected} search URLs from {searches_used} terms")
        return collected

    async def collect_user_urls(self, count=200):
        """
        Collect URLs from user profiles (find users via search then get their videos)
        """
        print(f"👤 Collecting {count} user video URLs...")
        collected = 0
        users_processed = 0
        
        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                )
                
                # Find users through hashtag searches, then get their videos
                target_hashtags = random.sample(['fyp', 'viral', 'funny', 'lifestyle', 'food'], 5)
                
                for hashtag in target_hashtags:
                    if collected >= count:
                        break
                        
                    print(f"   🔍 Finding users from #{hashtag}")
                    users_found = set()
                    
                    try:
                        # Get some videos from hashtag to find users
                        async for video in api.hashtag(name=hashtag).videos(count=30):
                            username = video.author.username
                            if username not in users_found and len(users_found) < 10:
                                users_found.add(username)
                        
                        # Now get videos from these users
                        for username in users_found:
                            if collected >= count:
                                break
                                
                            users_processed += 1
                            user_collected = 0
                            target_per_user = min(10, (count - collected))
                            
                            print(f"   👤 Getting videos from @{username} (target: {target_per_user})")
                            
                            try:
                                async for video in api.user(username=username).videos(count=target_per_user):
                                    if collected >= count or user_collected >= target_per_user:
                                        break
                                        
                                    url = f"https://www.tiktok.com/@{username}/video/{video.id}"
                                    
                                    if url not in self.collected_urls:
                                        self.collected_urls.add(url)
                                        
                                        # Store metadata
                                        metadata = {
                                            'url': url,
                                            'video_id': video.id,
                                            'username': username,
                                            'description': video.as_dict.get('desc', ''),
                                            'view_count': video.stats.get('playCount', 0),
                                            'like_count': video.stats.get('diggCount', 0),
                                            'comment_count': video.stats.get('commentCount', 0),
                                            'share_count': video.stats.get('shareCount', 0),
                                            'collection_method': f'user_profile',
                                            'source_hashtag': hashtag,
                                            'collected_at': datetime.now().isoformat()
                                        }
                                        self.url_metadata.append(metadata)
                                        collected += 1
                                        user_collected += 1
                                    
                                    await asyncio.sleep(0.1)
                                    
                            except Exception as e:
                                print(f"   ⚠️ Error getting videos from @{username}: {e}")
                                continue
                            
                            print(f"   ✅ Got {user_collected} URLs from @{username}")
                            await asyncio.sleep(random.uniform(2, 4))
                            
                    except Exception as e:
                        print(f"   ⚠️ Error processing hashtag #{hashtag}: {e}")
                        continue
                    
                    await asyncio.sleep(random.uniform(3, 6))
                    
        except Exception as e:
            print(f"❌ Error collecting user URLs: {e}")
        
        print(f"✅ Collected {collected} user URLs from {users_processed} users")
        return collected

    def save_urls(self, output_file="harvested_urls.json"):
        """
        Save collected URLs and metadata to file
        """
        output_data = {
            'collection_summary': {
                'total_urls': len(self.collected_urls),
                'total_with_metadata': len(self.url_metadata),
                'collection_date': datetime.now().isoformat(),
                'methods_used': list(set([item['collection_method'] for item in self.url_metadata]))
            },
            'urls': list(self.collected_urls),
            'url_metadata': self.url_metadata
        }
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved {len(self.collected_urls)} URLs to {output_path}")
        return output_path

    def save_urls_txt(self, output_file="harvested_urls.txt"):
        """
        Save URLs to simple text file (one URL per line)
        """
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            for url in sorted(self.collected_urls):
                f.write(url + '\n')
        
        print(f"📝 Saved {len(self.collected_urls)} URLs to {output_path}")
        return output_path

    async def harvest_all(self, trending=200, hashtags=300, searches=200, users=200):
        """
        Run all harvesting methods
        """
        print("🚀 Starting TikTok URL harvesting...")
        print(f"Target: {trending + hashtags + searches + users} total URLs")
        
        start_time = time.time()
        
        # Collect from different sources
        trending_count = await self.collect_trending_urls(trending)
        await asyncio.sleep(random.uniform(5, 10))
        
        hashtag_count = await self.collect_hashtag_urls(hashtags)
        await asyncio.sleep(random.uniform(5, 10))
        
        search_count = await self.collect_search_urls(searches)
        await asyncio.sleep(random.uniform(5, 10))
        
        user_count = await self.collect_user_urls(users)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Summary
        print(f"\n🎉 Harvesting completed in {duration/60:.1f} minutes!")
        print(f"📊 Collection Summary:")
        print(f"   🔥 Trending: {trending_count} URLs")
        print(f"   #️⃣ Hashtags: {hashtag_count} URLs")
        print(f"   🔍 Searches: {search_count} URLs")
        print(f"   👤 Users: {user_count} URLs")
        print(f"   📝 Total unique URLs: {len(self.collected_urls)}")
        
        # Save results
        json_file = self.save_urls()
        txt_file = self.save_urls_txt()
        
        return {
            'total_urls': len(self.collected_urls),
            'trending': trending_count,
            'hashtags': hashtag_count,
            'searches': search_count,
            'users': user_count,
            'json_file': str(json_file),
            'txt_file': str(txt_file),
            'duration_minutes': duration/60
        }

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Harvest TikTok video URLs")
    parser.add_argument("-t", "--trending", type=int, default=200,
                       help="Number of trending URLs to collect (default: 200)")
    parser.add_argument("--hashtags", type=int, default=300,
                       help="Number of hashtag URLs to collect (default: 300)")
    parser.add_argument("-s", "--searches", type=int, default=200,
                       help="Number of search URLs to collect (default: 200)")
    parser.add_argument("-u", "--users", type=int, default=200,
                       help="Number of user URLs to collect (default: 200)")
    parser.add_argument("-o", "--output", default="harvested_urls",
                       help="Output filename prefix (default: harvested_urls)")
    
    args = parser.parse_args()
    
    # Check MS_TOKEN
    if MS_TOKEN == "your_ms_token_here":
        print("❌ Error: You must set your ms_token in comment_extractor.py!")
        return
    
    # Create harvester
    harvester = TikTokURLHarvester()
    
    # Run harvesting
    results = await harvester.harvest_all(
        trending=args.trending,
        hashtags=args.hashtags, 
        searches=args.searches,
        users=args.users
    )
    
    # Save with custom filename
    if args.output != "harvested_urls":
        json_file = f"{args.output}.json"
        txt_file = f"{args.output}.txt"
        harvester.save_urls(json_file)
        harvester.save_urls_txt(txt_file)
    
    print(f"\n✅ Successfully harvested {results['total_urls']} unique TikTok URLs!")

if __name__ == "__main__":
    asyncio.run(main())