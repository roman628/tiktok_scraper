#!/usr/bin/env python3
"""
Example usage of the Reddit User Profile Scraper.

This script demonstrates various ways to use the Reddit scraper to analyze
user profiles, extract popular posts, and generate reports.
"""

import asyncio
import os
from datetime import datetime

from core.models import PostSortMethod, TimeFilter, ExportConfig
from core.reddit_client import RedditAPIClient
from services.profile_extractor import ProfileExtractor
from exporters.data_exporter import DataExporter


async def example_single_user_analysis():
    """Example: Analyze a single Reddit user's profile."""
    
    print("🎯 Single User Analysis Example")
    print("=" * 50)
    
    # Initialize Reddit client (you need to provide real credentials)
    reddit_client = RedditAPIClient(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET", 
        user_agent="RedditScraperExample/1.0"
    )
    
    # Initialize services
    profile_extractor = ProfileExtractor(reddit_client)
    data_exporter = DataExporter()
    
    # Analyze a user (using a well-known Reddit user as example)
    username = "spez"  # Reddit CEO - public profile with lots of activity
    
    print(f"Analyzing user: u/{username}")
    
    try:
        # Extract full profile analysis
        analysis = await profile_extractor.extract_full_profile(
            username=username,
            max_posts=50,  # Analyze top 50 posts
            sort_method=PostSortMethod.TOP,
            time_filter=TimeFilter.ALL
        )
        
        if analysis:
            print(f"\n✅ Analysis completed!")
            print(f"📊 Posts analyzed: {analysis.total_posts_analyzed}")
            print(f"🏆 Average score: {analysis.avg_post_score:.1f}")
            print(f"📈 Success rate: {analysis.success_rate:.1f}%") 
            print(f"🌐 Active subreddits: {analysis.diversity_score}")
            
            # Show top subreddits
            if analysis.most_active_subreddits:
                print(f"\n🏘️ Most active subreddits:")
                for i, subreddit in enumerate(analysis.most_active_subreddits[:5], 1):
                    count = analysis.posting_frequency.get(subreddit, 0)
                    print(f"   {i}. r/{subreddit} ({count} posts)")
            
            # Show best posts
            if analysis.best_performing_posts:
                print(f"\n🎯 Top performing posts:")
                for i, post in enumerate(analysis.best_performing_posts[:3], 1):
                    print(f"   {i}. {post.title[:60]}...")
                    print(f"      r/{post.subreddit} | {post.score} points | {post.num_comments} comments")
            
            # Export results
            export_config = ExportConfig(
                format="json",
                include_posts=True,
                include_subreddits=True,
                include_analysis=True,
                pretty_print=True
            )
            
            export_path = data_exporter.export_analysis(analysis, export_config)
            summary_path = data_exporter.create_summary_report(analysis)
            
            print(f"\n📤 Results exported:")
            print(f"   Data: {export_path}")
            print(f"   Summary: {summary_path}")
            
        else:
            print(f"❌ Failed to analyze user: {username}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def example_subreddit_analysis():
    """Example: Analyze how a user performs in a specific subreddit."""
    
    print("\n🏘️ Subreddit-Specific Analysis Example")
    print("=" * 50)
    
    reddit_client = RedditAPIClient(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        user_agent="RedditScraperExample/1.0"  
    )
    
    profile_extractor = ProfileExtractor(reddit_client)
    
    username = "PoemForYourSprog"  # Famous Reddit poet
    subreddit = "AskReddit"  # Popular subreddit
    
    print(f"Analyzing u/{username} performance in r/{subreddit}")
    
    try:
        # Get user's posts in specific subreddit
        subreddit_posts = await profile_extractor.get_top_posts_by_subreddit(
            username, subreddit, limit=20
        )
        
        if subreddit_posts:
            print(f"\n✅ Found {len(subreddit_posts)} posts in r/{subreddit}")
            
            # Show top posts
            print(f"\n🎯 Top posts in r/{subreddit}:")
            for i, post in enumerate(subreddit_posts[:5], 1):
                print(f"   {i}. {post.title[:50]}...")
                print(f"      {post.score} points | {post.num_comments} comments")
                print(f"      Popularity score: {post.popularity_score:.3f}")
            
            # Performance comparison
            comparison = await profile_extractor.compare_user_performance(
                username, subreddit, limit=50
            )
            
            if comparison:
                user_perf = comparison['user_performance']
                sub_avg = comparison['subreddit_average']
                comp = comparison['comparison']
                
                print(f"\n📈 Performance Comparison:")
                print(f"   User average score: {user_perf['avg_score']:.1f}")
                print(f"   Subreddit average: {sub_avg['avg_score']:.1f}")
                print(f"   Performance ratio: {comp['score_ratio']:.2f}x")
                print(f"   Percentile rank: {comp['performance_percentile']:.1f}%")
        
        else:
            print(f"❌ No posts found for u/{username} in r/{subreddit}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def example_batch_analysis():
    """Example: Analyze multiple users in batch."""
    
    print("\n👥 Batch Analysis Example") 
    print("=" * 50)
    
    reddit_client = RedditAPIClient(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        user_agent="RedditScraperExample/1.0"
    )
    
    profile_extractor = ProfileExtractor(reddit_client)
    data_exporter = DataExporter()
    
    # List of users to analyze
    usernames = [
        "spez",           # Reddit CEO
        "kn0thing",       # Reddit co-founder  
        "PoemForYourSprog" # Famous Reddit poet
    ]
    
    print(f"Analyzing {len(usernames)} users:")
    
    results = {}
    
    for i, username in enumerate(usernames, 1):
        print(f"\n📊 Processing {i}/{len(usernames)}: u/{username}")
        
        try:
            analysis = await profile_extractor.extract_full_profile(
                username=username,
                max_posts=25,  # Smaller sample for batch processing
                sort_method=PostSortMethod.TOP,
                time_filter=TimeFilter.YEAR  # Last year only
            )
            
            if analysis:
                results[username] = analysis
                print(f"   ✅ Success: {analysis.total_posts_analyzed} posts, avg score {analysis.avg_post_score:.1f}")
            else:
                print(f"   ❌ Failed to analyze u/{username}")
            
            # Be nice to Reddit's servers
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"   ❌ Error analyzing u/{username}: {e}")
    
    # Generate comparison report
    if results:
        print(f"\n📈 Batch Analysis Summary:")
        print(f"{'User':<20} {'Posts':<8} {'Avg Score':<12} {'Success Rate':<12} {'Subreddits':<12}")
        print("-" * 64)
        
        for username, analysis in results.items():
            print(f"{username:<20} {analysis.total_posts_analyzed:<8} {analysis.avg_post_score:<12.1f} {analysis.success_rate:<12.1f}% {analysis.diversity_score:<12}")
        
        # Export each analysis
        for username, analysis in results.items():
            export_config = ExportConfig(
                format="json",
                output_file=f"batch_{username}_analysis.json",
                include_posts=True,
                include_subreddits=True
            )
            
            export_path = data_exporter.export_analysis(analysis, export_config)
            print(f"📤 Exported {username}: {export_path}")


async def example_export_formats():
    """Example: Demonstrate different export formats."""
    
    print("\n📤 Export Formats Example")
    print("=" * 50)
    
    reddit_client = RedditAPIClient(
        client_id="YOUR_CLIENT_ID", 
        client_secret="YOUR_CLIENT_SECRET",
        user_agent="RedditScraperExample/1.0"
    )
    
    profile_extractor = ProfileExtractor(reddit_client)
    data_exporter = DataExporter()
    
    username = "gallowboob"  # User known for high-karma posts
    
    print(f"Analyzing u/{username} for export format demonstration")
    
    try:
        analysis = await profile_extractor.extract_full_profile(
            username=username,
            max_posts=30,
            sort_method=PostSortMethod.TOP,
            time_filter=TimeFilter.MONTH
        )
        
        if analysis:
            print(f"✅ Analysis complete. Demonstrating export formats:")
            
            # JSON export
            json_config = ExportConfig(
                format="json",
                output_file=f"{username}_export_demo.json",
                include_posts=True,
                include_subreddits=True,
                include_analysis=True,
                pretty_print=True
            )
            json_path = data_exporter.export_analysis(analysis, json_config)
            print(f"   📄 JSON: {json_path}")
            
            # CSV export  
            csv_config = ExportConfig(
                format="csv",
                output_file=f"{username}_export_demo.csv",
                include_posts=True,
                min_score_threshold=100  # Only posts with 100+ score
            )
            csv_path = data_exporter.export_analysis(analysis, csv_config)
            print(f"   📊 CSV: {csv_path}")
            
            # Excel export
            excel_config = ExportConfig(
                format="excel",
                output_file=f"{username}_export_demo.xlsx",
                include_posts=True,
                include_subreddits=True,
                include_analysis=True,
                exclude_nsfw=True
            )
            excel_path = data_exporter.export_analysis(analysis, excel_config)
            print(f"   📈 Excel: {excel_path}")
            
            # Summary report
            summary_path = data_exporter.create_summary_report(analysis)
            print(f"   📝 Summary: {summary_path}")
            
            # Posts-only export
            posts_path = data_exporter.export_posts_only(
                analysis.top_posts, 
                filename=f"{username}_posts_only.json",
                format="json"
            )
            print(f"   🎯 Posts only: {posts_path}")
            
        else:
            print(f"❌ Failed to analyze u/{username}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all examples."""
    
    print("🚀 Reddit User Profile Scraper - Example Usage")
    print("=" * 60)
    print()
    print("⚠️  Note: You need to set up Reddit API credentials first!")
    print("   1. Go to https://www.reddit.com/prefs/apps/")
    print("   2. Create a new 'script' application") 
    print("   3. Replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET in this file")
    print()
    
    # Check if credentials are set
    if "YOUR_CLIENT_ID" in open(__file__).read():
        print("❌ Please set up your Reddit API credentials before running examples!")
        print("   Edit this file and replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET")
        return
    
    try:
        # Run examples
        await example_single_user_analysis()
        await example_subreddit_analysis() 
        await example_batch_analysis()
        await example_export_formats()
        
        print("\n🎉 All examples completed successfully!")
        print("\nNext steps:")
        print("- Try the command line interface: python main.py --help")
        print("- Customize the analysis parameters for your needs")
        print("- Explore the exported data files")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("\nTroubleshooting:")
        print("- Check your Reddit API credentials")
        print("- Ensure you have internet connectivity")
        print("- Try with different usernames")


if __name__ == "__main__":
    asyncio.run(main())