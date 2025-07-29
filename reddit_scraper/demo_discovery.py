#!/usr/bin/env python3
"""
Demo version of subreddit discovery using public Reddit JSON endpoints.
This doesn't require Reddit API credentials but has more limitations.
"""

import asyncio
import json
import re
import os
import requests
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

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
        
        return list(found_usernames)
        
    except Exception as e:
        print(f"❌ Error reading TikTok data: {e}")
        return []

def get_user_subreddits_public(username: str, limit: int = 25):
    """Get user's subreddits using public Reddit JSON API."""
    
    try:
        url = f"https://www.reddit.com/user/{username}/submitted.json?limit={limit}"
        headers = {'User-Agent': 'SubredditDiscovery/1.0'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            subreddits = set()
            
            if 'data' in data and 'children' in data['data']:
                for post in data['data']['children']:
                    if 'data' in post and 'subreddit' in post['data']:
                        subreddit = post['data']['subreddit'].lower()
                        subreddits.add(subreddit)
            
            return list(subreddits)
        
        elif response.status_code == 404:
            return None  # User not found
        else:
            print(f"  ⚠️ HTTP {response.status_code} for user {username}")
            return []
            
    except Exception as e:
        print(f"  ❌ Error fetching user {username}: {e}")
        return []

def discover_subreddits_from_users(usernames, max_users_to_check=30):
    """Discover subreddits from a list of Reddit usernames."""
    
    print(f"\n🏘️ Discovering subreddits from {min(len(usernames), max_users_to_check)} users...")
    
    subreddit_counts = defaultdict(set)  # subreddit -> set of users
    successful_users = []
    failed_users = []
    
    usernames_to_check = usernames[:max_users_to_check]
    
    for i, username in enumerate(usernames_to_check, 1):
        print(f"  📊 Checking user {i}/{len(usernames_to_check)}: u/{username}")
        
        user_subreddits = get_user_subreddits_public(username)
        
        if user_subreddits is None:
            failed_users.append(f"{username} (not found)")
        elif user_subreddits:
            successful_users.append(username)
            for subreddit in user_subreddits:
                subreddit_counts[subreddit].add(username)
        else:
            failed_users.append(f"{username} (no posts/private)")
        
        # Rate limiting - be nice to Reddit
        time.sleep(1)
    
    print(f"\n📈 Discovery Results:")
    print(f"  - Successful users: {len(successful_users)}")
    print(f"  - Failed users: {len(failed_users)}")
    print(f"  - Unique subreddits found: {len(subreddit_counts)}")
    
    # Create subreddit rankings
    subreddit_rankings = []
    for subreddit, users in subreddit_counts.items():
        if len(users) >= 2:  # Only include subreddits with 2+ users
            subreddit_rankings.append({
                'subreddit': subreddit,
                'user_count': len(users),
                'users': list(users)
            })
    
    # Sort by user count
    subreddit_rankings.sort(key=lambda x: x['user_count'], reverse=True)
    
    return subreddit_rankings, successful_users, failed_users

def categorize_subreddit(subreddit_name):
    """Categorize subreddit based on name."""
    
    name_lower = subreddit_name.lower()
    
    # Category keywords
    categories = {
        'relationships': ['relationship', 'dating', 'marriage', 'amitheasshole', 'tifu', 'offmychest'],
        'advice': ['advice', 'askreddit', 'nostupidquestions', 'explainlikeimfive', 'legaladvice'],
        'mental_health': ['anxiety', 'depression', 'mentalhealth', 'therapy', 'ptsd'],
        'entertainment': ['movie', 'tv', 'netflix', 'entertainment', 'celebrity', 'music'],
        'gaming': ['gaming', 'games', 'steam', 'nintendo', 'xbox', 'playstation'],
        'technology': ['technology', 'programming', 'coding', 'computers', 'android', 'apple'],
        'lifestyle': ['food', 'fitness', 'fashion', 'travel', 'diy', 'cooking'],
        'humor': ['funny', 'meme', 'dankmemes', 'cursedcomments', 'holup'],
        'creative': ['art', 'photography', 'writing', 'design', 'crafts'],
        'educational': ['todayilearned', 'science', 'history', 'explainlikeimfive'],
        'support': ['support', 'help', 'mentalhealth', 'depression', 'anxiety']
    }
    
    # Check name against categories
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in name_lower:
                return category
    
    return 'general'

def create_discovery_report(subreddit_rankings, successful_users, failed_users, output_dir="subreddit_discovery_demo"):
    """Create comprehensive discovery report."""
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Add categories to rankings
    for ranking in subreddit_rankings:
        ranking['category'] = categorize_subreddit(ranking['subreddit'])
    
    # Create JSON report
    report_data = {
        'discovery_summary': {
            'total_usernames_extracted': len(successful_users) + len(failed_users),
            'successful_users': len(successful_users),
            'failed_users': len(failed_users),
            'subreddits_discovered': len(subreddit_rankings),
            'timestamp': datetime.now().isoformat()
        },
        'top_subreddits': subreddit_rankings,
        'successful_users': successful_users,
        'failed_users': failed_users
    }
    
    json_file = os.path.join(output_dir, "subreddit_discovery_results.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    # Create human-readable summary
    summary_lines = []
    summary_lines.append("🎯 Reddit Subreddit Discovery Report (Demo)")
    summary_lines.append("=" * 60)
    summary_lines.append("")
    
    summary_lines.append(f"📊 Discovery Summary:")
    summary_lines.append(f"- Total usernames checked: {len(successful_users) + len(failed_users)}")
    summary_lines.append(f"- Successful users: {len(successful_users)}")
    summary_lines.append(f"- Failed users: {len(failed_users)}")
    summary_lines.append(f"- Unique subreddits discovered: {len(subreddit_rankings)}")
    summary_lines.append("")
    
    if subreddit_rankings:
        summary_lines.append(f"🏆 Top Discovered Subreddits:")
        for i, ranking in enumerate(subreddit_rankings[:15], 1):
            summary_lines.append(f"{i:2d}. r/{ranking['subreddit']} ({ranking['category']})")
            summary_lines.append(f"    👥 {ranking['user_count']} users: {', '.join(ranking['users'])}")
        summary_lines.append("")
        
        # Category breakdown
        category_counts = Counter(r['category'] for r in subreddit_rankings)
        summary_lines.append(f"📂 Categories Found:")
        for category, count in category_counts.most_common():
            summary_lines.append(f"- {category}: {count} subreddits")
        summary_lines.append("")
    
    if failed_users:
        summary_lines.append(f"❌ Failed Users (sample):")
        for user in failed_users[:10]:
            summary_lines.append(f"- {user}")
        if len(failed_users) > 10:
            summary_lines.append(f"... and {len(failed_users) - 10} more")
        summary_lines.append("")
    
    summary_lines.append(f"⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append("")
    summary_lines.append(f"💡 Next Steps:")
    summary_lines.append(f"- Set up Reddit API credentials for deeper analysis")
    summary_lines.append(f"- Scrape popular posts from discovered subreddits")
    summary_lines.append(f"- Analyze posting patterns and engagement metrics")
    
    summary_file = os.path.join(output_dir, "discovery_summary.txt")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(summary_lines))
    
    print(f"📁 Reports saved to {output_dir}/")
    print(f"- JSON data: {json_file}")
    print(f"- Summary: {summary_file}")
    
    return json_file

def main():
    """Run the demo subreddit discovery."""
    
    print("🚀 Reddit Subreddit Discovery Demo")
    print("=" * 60)
    print("📝 This demo uses public Reddit endpoints (no API key needed)")
    print("⚠️  Limited to public posts and basic info")
    print("")
    
    # Path to TikTok data
    tiktok_data_path = "/Users/ethan/tiktok_scraper/master2.json"
    
    if not os.path.exists(tiktok_data_path):
        print(f"❌ ERROR: TikTok data file not found: {tiktok_data_path}")
        return
    
    try:
        # Step 1: Extract Reddit usernames
        print("Step 1: Extracting Reddit usernames from TikTok data...")
        usernames = extract_reddit_usernames_from_tiktok_data(tiktok_data_path)
        
        if not usernames:
            print("❌ No Reddit usernames found!")
            return
        
        print(f"✅ Found {len(usernames)} unique Reddit usernames")
        
        # Step 2: Discover subreddits
        print("\nStep 2: Discovering subreddits from Reddit users...")
        print("⏱️  This will take a few minutes with rate limiting...")
        
        subreddit_rankings, successful_users, failed_users = discover_subreddits_from_users(
            usernames, max_users_to_check=25  # Limit for demo
        )
        
        if not subreddit_rankings:
            print("❌ No subreddits discovered!")
            return
        
        # Step 3: Create reports
        print(f"\nStep 3: Creating discovery reports...")
        report_file = create_discovery_report(subreddit_rankings, successful_users, failed_users)
        
        # Show preview
        print(f"\n🎯 Discovery Preview:")
        print(f"Top 10 discovered subreddits:")
        for i, ranking in enumerate(subreddit_rankings[:10], 1):
            print(f"{i:2d}. r/{ranking['subreddit']} - {ranking['user_count']} users ({ranking['category']})")
        
        print(f"\n✅ Discovery completed successfully!")
        print(f"📄 Full results: {report_file}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Discovery interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during discovery: {e}")

if __name__ == "__main__":
    main()