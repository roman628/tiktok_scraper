#!/usr/bin/env python3
"""
Reddit User Profile Scraper

A comprehensive Reddit scraper that extracts user profiles, identifies their most
popular posts, and provides detailed subreddit activity analysis.

Usage:
    python main.py --username <username> [options]
    python main.py --config config.json
    python main.py --batch users.txt

Examples:
    python main.py --username spez --max-posts 50 --format json
    python main.py --username gallowboob --export-format excel --include-analysis
    python main.py --batch users.txt --max-posts 100 --output-dir results/
"""

import asyncio
import logging
import argparse
import json
import os
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from core.models import PostSortMethod, TimeFilter, ExportConfig
from core.reddit_client import RedditAPIClient
from services.profile_extractor import ProfileExtractor, TikTokRedditExtractor
from exporters.data_exporter import DataExporter


class RedditScraperApp:
    """Main Reddit scraper application."""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """Initialize the Reddit scraper with API credentials."""
        self.reddit_client = RedditAPIClient(client_id, client_secret, user_agent)
        self.profile_extractor = ProfileExtractor(self.reddit_client)
        self.tiktok_extractor = TikTokRedditExtractor(self.reddit_client)
        self.data_exporter = DataExporter()
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'reddit_scraper_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    async def scrape_user(
        self,
        username: str,
        max_posts: int = 100,
        sort_method: PostSortMethod = PostSortMethod.TOP,
        time_filter: TimeFilter = TimeFilter.ALL,
        export_config: Optional[ExportConfig] = None
    ) -> Optional[str]:
        """
        Scrape a single user's profile and posts.
        
        Args:
            username: Reddit username to scrape
            max_posts: Maximum number of posts to analyze
            sort_method: How to sort posts (top, hot, new, etc.)
            time_filter: Time period filter (all, year, month, etc.)
            export_config: Export configuration options
            
        Returns:
            Path to exported file or None if failed
        """
        
        self.logger.info(f"Starting scrape for user: {username}")
        
        try:
            # Check API health
            if not await self.reddit_client.health_check():
                self.logger.error("Reddit API is not accessible")
                return None
            
            # Extract user profile and analysis
            analysis = await self.profile_extractor.extract_full_profile(
                username=username,
                max_posts=max_posts,
                sort_method=sort_method,
                time_filter=time_filter
            )
            
            if not analysis:
                self.logger.error(f"Failed to extract profile for user: {username}")
                return None
            
            # Export results
            if not export_config:
                export_config = ExportConfig(format="json", include_analysis=True)
            
            export_path = self.data_exporter.export_analysis(analysis, export_config)
            
            # Also create a summary report
            summary_path = self.data_exporter.create_summary_report(analysis)
            
            self.logger.info(f"Scraping completed successfully for user: {username}")
            self.logger.info(f"Data exported to: {export_path}")
            self.logger.info(f"Summary report: {summary_path}")
            
            return export_path
            
        except Exception as e:
            self.logger.error(f"Error scraping user {username}: {e}")
            return None
    
    async def scrape_multiple_users(
        self,
        usernames: List[str],
        max_posts: int = 50,
        output_dir: str = "results",
        export_format: str = "json"
    ) -> List[str]:
        """
        Scrape multiple users' profiles.
        
        Args:
            usernames: List of Reddit usernames to scrape
            max_posts: Maximum posts per user
            output_dir: Directory to save results
            export_format: Export format (json, csv, excel)
            
        Returns:
            List of export file paths
        """
        
        self.logger.info(f"Starting batch scrape for {len(usernames)} users")
        
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        
        results = []
        
        for i, username in enumerate(usernames, 1):
            self.logger.info(f"Processing user {i}/{len(usernames)}: {username}")
            
            try:
                # Configure export for this user
                export_config = ExportConfig(
                    format=export_format,
                    output_file=os.path.join(output_dir, f"{username}_analysis.{export_format}"),
                    include_posts=True,
                    include_subreddits=True,
                    include_analysis=True
                )
                
                # Scrape user
                result_path = await self.scrape_user(
                    username=username,
                    max_posts=max_posts,
                    export_config=export_config
                )
                
                if result_path:
                    results.append(result_path)
                
                # Add delay between users to be respectful
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Failed to process user {username}: {e}")
                continue
        
        self.logger.info(f"Batch scraping completed. {len(results)} users processed successfully.")
        return results
    
    async def analyze_user_in_subreddit(
        self,
        username: str,
        subreddit_name: str,
        comparison: bool = True
    ) -> Optional[dict]:
        """
        Analyze a user's performance in a specific subreddit.
        
        Args:
            username: Reddit username
            subreddit_name: Subreddit to analyze
            comparison: Whether to compare against subreddit averages
            
        Returns:
            Analysis results dictionary
        """
        
        self.logger.info(f"Analyzing user {username} in r/{subreddit_name}")
        
        try:
            # Get user's posts in the subreddit
            user_posts = await self.profile_extractor.get_top_posts_by_subreddit(
                username, subreddit_name, limit=50
            )
            
            if not user_posts:
                self.logger.warning(f"No posts found for {username} in r/{subreddit_name}")
                return None
            
            analysis_result = {
                'username': username,
                'subreddit': subreddit_name,
                'total_posts': len(user_posts),
                'posts': [
                    {
                        'title': post.title,
                        'score': post.score,
                        'comments': post.num_comments,
                        'created': post.created_utc.isoformat(),
                        'url': post.url,
                        'popularity_score': post.popularity_score
                    }
                    for post in user_posts[:20]  # Top 20 posts
                ]
            }
            
            # Add comparison data if requested
            if comparison:
                comparison_data = await self.profile_extractor.compare_user_performance(
                    username, subreddit_name
                )
                analysis_result['performance_comparison'] = comparison_data
            
            # Export results
            filename = f"{username}_in_{subreddit_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Subreddit analysis exported to: {filename}")
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Error analyzing user {username} in r/{subreddit_name}: {e}")
            return None
    
    async def discover_subreddits_from_tiktok(
        self,
        tiktok_json_path: str,
        max_users_to_analyze: int = 50,
        output_dir: str = "subreddit_discovery"
    ) -> Optional[str]:
        """
        Discover popular subreddits from TikTok data analysis.
        
        Args:
            tiktok_json_path: Path to TikTok JSON data file
            max_users_to_analyze: Maximum Reddit users to analyze
            output_dir: Directory to save discovery results
            
        Returns:
            Path to discovery results or None if failed
        """
        
        self.logger.info(f"Starting subreddit discovery from TikTok data: {tiktok_json_path}")
        
        try:
            # Create output directory
            Path(output_dir).mkdir(exist_ok=True)
            
            # Step 1: Extract Reddit usernames from TikTok data
            self.logger.info("Step 1: Extracting Reddit usernames from TikTok data...")
            extraction_result = self.tiktok_extractor.extract_reddit_usernames_from_tiktok_data(
                tiktok_json_path
            )
            
            if not extraction_result.reddit_usernames_found:
                self.logger.error("No Reddit usernames found in TikTok data")
                return None
            
            self.logger.info(f"Found {extraction_result.unique_usernames} unique Reddit usernames")
            
            # Save extraction results
            extraction_file = os.path.join(output_dir, "reddit_usernames_extracted.json")
            with open(extraction_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_videos_analyzed': extraction_result.total_videos_analyzed,
                    'unique_usernames': extraction_result.unique_usernames,
                    'extraction_patterns': extraction_result.extraction_patterns,
                    'failed_extractions': extraction_result.failed_extractions,
                    'usernames': extraction_result.reddit_usernames_found,
                    'timestamp': extraction_result.timestamp.isoformat()
                }, f, indent=2)
            
            # Step 2: Analyze users to discover subreddits
            self.logger.info("Step 2: Analyzing Reddit users to discover subreddits...")
            usernames_to_analyze = extraction_result.reddit_usernames_found[:max_users_to_analyze]
            
            discoveries = await self.tiktok_extractor.discover_subreddits_from_users(
                usernames=usernames_to_analyze,
                max_posts_per_user=30,
                min_users_per_subreddit=2
            )
            
            if not discoveries:
                self.logger.error("No subreddits discovered from user analysis")
                return None
            
            self.logger.info(f"Discovered {len(discoveries)} popular subreddits")
            
            # Step 3: Enhance discoveries with metadata
            self.logger.info("Step 3: Enhancing subreddit discoveries with metadata...")
            enhanced_discoveries = await self.tiktok_extractor.enhance_subreddit_discoveries(
                discoveries[:25]  # Limit to top 25 for metadata enhancement
            )
            
            # Step 4: Export discovery results
            discovery_data = {
                'extraction_summary': {
                    'tiktok_videos_analyzed': extraction_result.total_videos_analyzed,
                    'reddit_usernames_found': extraction_result.unique_usernames,
                    'users_analyzed': len(usernames_to_analyze),
                    'subreddits_discovered': len(enhanced_discoveries)
                },
                'top_subreddits': []
            }
            
            for discovery in enhanced_discoveries:
                discovery_data['top_subreddits'].append({
                    'rank': discovery.popularity_rank,
                    'subreddit': discovery.subreddit_name,
                    'category': discovery.category,
                    'discovered_from_users': discovery.discovered_from_users,
                    'user_count': discovery.user_count,
                    'total_posts': discovery.total_user_posts,
                    'avg_score': discovery.avg_user_score,
                    'activity_score': discovery.activity_score,
                    'subscribers': discovery.subscriber_count
                })
            
            discovery_file = os.path.join(output_dir, "subreddit_discovery_results.json")
            with open(discovery_file, 'w', encoding='utf-8') as f:
                json.dump(discovery_data, f, indent=2, ensure_ascii=False)
            
            # Step 5: Scrape posts from top discovered subreddits
            self.logger.info("Step 5: Scraping posts from discovered subreddits...")
            subreddit_posts = await self.tiktok_extractor.scrape_posts_from_discovered_subreddits(
                discoveries=enhanced_discoveries[:10],  # Top 10 subreddits
                posts_per_subreddit=20,
                time_filter=TimeFilter.WEEK
            )
            
            # Save scraped posts
            posts_file = os.path.join(output_dir, "discovered_subreddit_posts.json")
            posts_data = {}
            for subreddit, posts in subreddit_posts.items():
                posts_data[subreddit] = [
                    {
                        'title': post.title,
                        'author': post.author,
                        'score': post.score,
                        'comments': post.num_comments,
                        'url': post.url,
                        'created': post.created_utc.isoformat(),
                        'popularity_score': post.popularity_score
                    }
                    for post in posts
                ]
            
            with open(posts_file, 'w', encoding='utf-8') as f:
                json.dump(posts_data, f, indent=2, ensure_ascii=False)
            
            # Create summary report
            self._create_discovery_summary_report(
                discovery_data, 
                subreddit_posts, 
                os.path.join(output_dir, "discovery_summary.txt")
            )
            
            self.logger.info(f"Subreddit discovery completed successfully!")
            self.logger.info(f"Results saved to: {output_dir}/")
            self.logger.info(f"- Usernames: {extraction_file}")
            self.logger.info(f"- Discoveries: {discovery_file}")
            self.logger.info(f"- Posts: {posts_file}")
            
            return discovery_file
            
        except Exception as e:
            self.logger.error(f"Error in subreddit discovery: {e}")
            return None
    
    def _create_discovery_summary_report(
        self, 
        discovery_data: dict, 
        subreddit_posts: dict, 
        output_file: str
    ):
        """Create a human-readable summary of the discovery process."""
        
        lines = []
        lines.append("🎯 Reddit Subreddit Discovery Report")
        lines.append("=" * 50)
        lines.append("")
        
        # Summary stats
        summary = discovery_data['extraction_summary']
        lines.append(f"📊 Discovery Summary:")
        lines.append(f"- TikTok videos analyzed: {summary['tiktok_videos_analyzed']:,}")
        lines.append(f"- Reddit usernames found: {summary['reddit_usernames_found']}")
        lines.append(f"- Users analyzed: {summary['users_analyzed']}")
        lines.append(f"- Subreddits discovered: {summary['subreddits_discovered']}")
        lines.append("")
        
        # Top subreddits
        lines.append(f"🏆 Top Discovered Subreddits:")
        for subreddit in discovery_data['top_subreddits'][:10]:
            lines.append(f"{subreddit['rank']:2d}. r/{subreddit['subreddit']} ({subreddit['category']})")
            lines.append(f"    👥 {subreddit['user_count']} users | 📊 {subreddit['avg_score']:.1f} avg score")
            lines.append(f"    📈 {subreddit['subscribers']:,} subscribers | ⭐ {subreddit['activity_score']:.3f} activity")
        lines.append("")
        
        # Posts scraped
        if subreddit_posts:
            total_posts = sum(len(posts) for posts in subreddit_posts.values())
            lines.append(f"📝 Posts Scraped: {total_posts} posts from {len(subreddit_posts)} subreddits")
            
            for subreddit, posts in list(subreddit_posts.items())[:5]:
                lines.append(f"- r/{subreddit}: {len(posts)} posts")
                if posts:
                    top_post = max(posts, key=lambda p: p.score)
                    lines.append(f"  Top: {top_post.title[:50]}... ({top_post.score} points)")
        
        lines.append("")
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        self.logger.info(f"Discovery summary report created: {output_file}")


def load_config_file(config_path: str) -> dict:
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def load_usernames_from_file(file_path: str) -> List[str]:
    """Load usernames from text file (one per line)."""
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


async def main():
    """Main application entry point."""
    
    parser = argparse.ArgumentParser(
        description="Reddit User Profile Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --username spez --max-posts 50
  python main.py --username gallowboob --format excel --include-analysis
  python main.py --batch users.txt --output-dir results/
  python main.py --subreddit-analysis spez python --comparison
        """
    )
    
    # Authentication (required)
    parser.add_argument('--client-id', required=True, help='Reddit API client ID')
    parser.add_argument('--client-secret', required=True, help='Reddit API client secret')
    parser.add_argument('--user-agent', default='RedditScraper/1.0', help='User agent string')
    
    # Single user scraping
    parser.add_argument('--username', help='Reddit username to scrape')
    parser.add_argument('--max-posts', type=int, default=100, help='Maximum posts to analyze')
    parser.add_argument('--sort-method', choices=['top', 'hot', 'new', 'rising'], default='top')
    parser.add_argument('--time-filter', choices=['hour', 'day', 'week', 'month', 'year', 'all'], default='all')
    
    # Batch processing
    parser.add_argument('--batch', help='File containing usernames (one per line)')
    parser.add_argument('--output-dir', default='results', help='Output directory for batch processing')
    
    # Export options
    parser.add_argument('--format', choices=['json', 'csv', 'excel'], default='json', help='Export format')
    parser.add_argument('--include-posts', action='store_true', default=True, help='Include posts in export')
    parser.add_argument('--include-subreddits', action='store_true', default=True, help='Include subreddit analysis')
    parser.add_argument('--include-analysis', action='store_true', default=True, help='Include activity analysis')
    parser.add_argument('--min-score', type=int, default=0, help='Minimum post score to include')
    parser.add_argument('--exclude-nsfw', action='store_true', help='Exclude NSFW content')
    
    # Subreddit-specific analysis
    parser.add_argument('--subreddit-analysis', nargs=2, metavar=('USERNAME', 'SUBREDDIT'),
                        help='Analyze user performance in specific subreddit')
    parser.add_argument('--comparison', action='store_true', help='Compare against subreddit averages')
    
    # TikTok data discovery
    parser.add_argument('--discover-from-tiktok', help='Path to TikTok JSON data file for subreddit discovery')
    parser.add_argument('--max-users', type=int, default=50, help='Maximum Reddit users to analyze for discovery')
    parser.add_argument('--discovery-output', default='subreddit_discovery', help='Output directory for discovery results')
    
    # Configuration file
    parser.add_argument('--config', help='Load settings from JSON config file')
    
    args = parser.parse_args()
    
    # Load config file if provided
    if args.config:
        config = load_config_file(args.config)
        # Override args with config values
        for key, value in config.items():
            if hasattr(args, key) and getattr(args, key) is None:
                setattr(args, key, value)
    
    # Initialize scraper
    scraper = RedditScraperApp(
        client_id=args.client_id,
        client_secret=args.client_secret,
        user_agent=args.user_agent
    )
    
    # Configure export options
    export_config = ExportConfig(
        format=args.format,
        include_posts=args.include_posts,
        include_subreddits=args.include_subreddits,
        include_analysis=args.include_analysis,
        min_score_threshold=args.min_score,
        exclude_nsfw=args.exclude_nsfw
    )
    
    # Convert string enums
    sort_method = PostSortMethod(args.sort_method)
    time_filter = TimeFilter(args.time_filter)
    
    try:
        if args.discover_from_tiktok:
            # TikTok subreddit discovery
            await scraper.discover_subreddits_from_tiktok(
                tiktok_json_path=args.discover_from_tiktok,
                max_users_to_analyze=args.max_users,
                output_dir=args.discovery_output
            )
            
        elif args.subreddit_analysis:
            # Subreddit-specific analysis
            username, subreddit = args.subreddit_analysis
            await scraper.analyze_user_in_subreddit(username, subreddit, args.comparison)
            
        elif args.batch:
            # Batch processing
            usernames = load_usernames_from_file(args.batch)
            await scraper.scrape_multiple_users(
                usernames=usernames,
                max_posts=args.max_posts,
                output_dir=args.output_dir,
                export_format=args.format
            )
            
        elif args.username:
            # Single user scraping
            await scraper.scrape_user(
                username=args.username,
                max_posts=args.max_posts,
                sort_method=sort_method,
                time_filter=time_filter,
                export_config=export_config
            )
            
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        logging.error(f"Application error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())