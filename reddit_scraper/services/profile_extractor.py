"""
Profile extraction service for comprehensive Reddit user analysis.
"""
import asyncio
import logging
import json
import re
from typing import List, Dict, Optional
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

from ..core.models import (
    RedditUser, RedditPost, SubredditData, UserAnalysis, 
    PostSortMethod, TimeFilter, PopularityScore, SubredditDiscovery, TikTokDataExtraction
)
from ..core.reddit_client import RedditAPIClient


class PopularityScorer:
    """Advanced popularity scoring system for Reddit posts."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_popularity_score(self, post: RedditPost, context_posts: List[RedditPost] = None) -> PopularityScore:
        """Calculate comprehensive popularity score for a post."""
        
        # Base metrics
        raw_score = post.score
        comments_score = post.num_comments
        age_hours = post.age_hours
        awards_count = post.total_awards_received
        upvote_ratio = post.upvote_ratio
        
        # Normalize scores (0-1 scale)
        if context_posts:
            max_score = max(p.score for p in context_posts) or 1
            max_comments = max(p.num_comments for p in context_posts) or 1
            max_awards = max(p.total_awards_received for p in context_posts) or 1
        else:
            max_score = max(raw_score, 100)
            max_comments = max(comments_score, 50)
            max_awards = max(awards_count, 1)
        
        # Component scores (0-1 scale)
        upvote_component = min(raw_score / max_score, 1.0)
        comment_component = min(comments_score / max_comments, 1.0)
        awards_component = min(awards_count / max_awards, 1.0) if max_awards > 0 else 0
        ratio_component = upvote_ratio
        
        # Time decay factor (posts lose value over time)
        time_decay = 1.0 / (1.0 + age_hours / 24.0)  # Decay over days
        time_component = time_decay
        
        # Weighted composite score
        weights = {
            'upvotes': 0.4,
            'comments': 0.25,
            'awards': 0.15,
            'ratio': 0.1,
            'time': 0.1
        }
        
        composite_score = (
            weights['upvotes'] * upvote_component +
            weights['comments'] * comment_component +
            weights['awards'] * awards_component +
            weights['ratio'] * ratio_component +
            weights['time'] * time_component
        )
        
        # Calculate percentile rank if context provided
        percentile_rank = 0.0
        if context_posts:
            better_posts = sum(1 for p in context_posts if p.score > raw_score)
            percentile_rank = (len(context_posts) - better_posts) / len(context_posts) * 100
        
        return PopularityScore(
            raw_score=raw_score,
            normalized_score=upvote_component,
            time_adjusted_score=composite_score,
            engagement_score=comment_component,
            awards_score=awards_component,
            composite_score=composite_score,
            percentile_rank=percentile_rank,
            upvote_component=upvote_component,
            comment_component=comment_component,
            time_component=time_component,
            awards_component=awards_component,
            ratio_component=ratio_component
        )


class ProfileExtractor:
    """Extract and analyze comprehensive Reddit user profiles."""
    
    def __init__(self, reddit_client: RedditAPIClient):
        self.reddit_client = reddit_client
        self.popularity_scorer = PopularityScorer()
        self.logger = logging.getLogger(__name__)
    
    async def extract_full_profile(
        self, 
        username: str, 
        max_posts: int = 100,
        sort_method: PostSortMethod = PostSortMethod.TOP,
        time_filter: TimeFilter = TimeFilter.ALL
    ) -> Optional[UserAnalysis]:
        """Extract comprehensive user profile with analysis."""
        
        self.logger.info(f"Starting profile extraction for user: {username}")
        
        # Get user profile
        user_profile = await self.reddit_client.get_user_profile(username)
        if not user_profile:
            self.logger.error(f"Could not retrieve profile for user: {username}")
            return None
        
        # Get user posts
        user_posts = await self.reddit_client.get_user_posts(
            username, limit=max_posts, sort_method=sort_method, time_filter=time_filter
        )
        
        if not user_posts:
            self.logger.warning(f"No posts found for user: {username}")
            return UserAnalysis(
                user=user_profile,
                total_posts_analyzed=0,
                analysis_timeframe=f"{sort_method.value}_{time_filter.value}"
            )
        
        # Analyze posts and calculate popularity scores
        await self._calculate_popularity_scores(user_posts)
        
        # Group posts by subreddit
        subreddit_posts = self._group_posts_by_subreddit(user_posts)
        
        # Get subreddit information
        subreddit_data = await self._get_subreddit_data(subreddit_posts)
        
        # Create comprehensive analysis
        analysis = UserAnalysis(
            user=user_profile,
            total_posts_analyzed=len(user_posts),
            analysis_timeframe=f"{sort_method.value}_{time_filter.value}",
            top_posts=sorted(user_posts, key=lambda p: p.popularity_score, reverse=True)[:20],
            subreddit_activity=subreddit_data
        )
        
        # Calculate statistics and patterns
        self._calculate_user_statistics(analysis, user_posts)
        self._analyze_posting_patterns(analysis, user_posts)
        
        self.logger.info(f"Profile extraction completed for user: {username}")
        return analysis
    
    async def _calculate_popularity_scores(self, posts: List[RedditPost]):
        """Calculate popularity scores for all posts."""
        for post in posts:
            popularity_score = self.popularity_scorer.calculate_popularity_score(post, posts)
            post.popularity_score = popularity_score.composite_score
    
    def _group_posts_by_subreddit(self, posts: List[RedditPost]) -> Dict[str, List[RedditPost]]:
        """Group posts by subreddit."""
        subreddit_posts = defaultdict(list)
        for post in posts:
            subreddit_posts[post.subreddit].append(post)
        return dict(subreddit_posts)
    
    async def _get_subreddit_data(self, subreddit_posts: Dict[str, List[RedditPost]]) -> Dict[str, SubredditData]:
        """Get detailed information for each subreddit."""
        subreddit_data = {}
        
        for subreddit_name, posts in subreddit_posts.items():
            # Get subreddit info
            subreddit_info = await self.reddit_client.get_subreddit_info(subreddit_name)
            
            if subreddit_info:
                # Add user activity data
                subreddit_info.user_posts = posts
                subreddit_info.calculate_user_stats()
                subreddit_data[subreddit_name] = subreddit_info
            else:
                # Create minimal subreddit data
                subreddit_data[subreddit_name] = SubredditData(
                    name=subreddit_name,
                    display_name=subreddit_name,
                    title=subreddit_name,
                    description="",
                    subscribers=0,
                    created_utc=datetime.utcnow(),
                    user_posts=posts
                )
                subreddit_data[subreddit_name].calculate_user_stats()
        
        return subreddit_data
    
    def _calculate_user_statistics(self, analysis: UserAnalysis, posts: List[RedditPost]):
        """Calculate user statistics and performance metrics."""
        if not posts:
            return
        
        # Basic statistics
        total_score = sum(post.score for post in posts)
        avg_score = total_score / len(posts)
        
        analysis.total_score = total_score
        analysis.avg_post_score = avg_score
        
        # Success rate (posts above average)
        above_avg_posts = sum(1 for post in posts if post.score > avg_score)
        analysis.success_rate = (above_avg_posts / len(posts)) * 100
        
        # Diversity score (unique subreddits)
        analysis.diversity_score = len(analysis.subreddit_activity)
        
        # Most active subreddits
        subreddit_counts = Counter(post.subreddit for post in posts)
        analysis.most_active_subreddits = [sr for sr, _ in subreddit_counts.most_common(10)]
        
        # Best performing posts
        analysis.best_performing_posts = sorted(
            posts, key=lambda p: p.popularity_score, reverse=True
        )[:10]
        
        # Posting frequency analysis
        analysis.posting_frequency = dict(subreddit_counts)
    
    def _analyze_posting_patterns(self, analysis: UserAnalysis, posts: List[RedditPost]):
        """Analyze temporal posting patterns."""
        if not posts:
            return
        
        # Posting times (hour of day)
        posting_times = defaultdict(int)
        posting_days = defaultdict(int)
        
        for post in posts:
            hour = post.created_utc.hour
            day_of_week = post.created_utc.weekday()  # 0=Monday, 6=Sunday
            
            posting_times[hour] += 1
            posting_days[day_of_week] += 1
        
        analysis.posting_times = dict(posting_times)
        analysis.posting_days = dict(posting_days)
    
    async def get_top_posts_by_subreddit(
        self, 
        username: str, 
        subreddit_name: str, 
        limit: int = 20
    ) -> List[RedditPost]:
        """Get user's top posts from a specific subreddit."""
        
        all_posts = await self.reddit_client.get_user_posts(username, limit=500)
        subreddit_posts = [post for post in all_posts if post.subreddit.lower() == subreddit_name.lower()]
        
        # Sort by popularity score
        await self._calculate_popularity_scores(subreddit_posts)
        return sorted(subreddit_posts, key=lambda p: p.popularity_score, reverse=True)[:limit]
    
    async def compare_user_performance(
        self, 
        username: str, 
        subreddit_name: str, 
        limit: int = 50
    ) -> Dict[str, any]:
        """Compare user's performance against subreddit averages."""
        
        # Get user's posts in subreddit
        user_posts = await self.get_top_posts_by_subreddit(username, subreddit_name, limit)
        
        # Get popular posts from subreddit for comparison
        subreddit_posts = await self.reddit_client.get_popular_posts_from_subreddit(
            subreddit_name, limit=100
        )
        
        if not user_posts or not subreddit_posts:
            return {}
        
        # Calculate averages
        user_avg_score = sum(p.score for p in user_posts) / len(user_posts)
        user_avg_comments = sum(p.num_comments for p in user_posts) / len(user_posts)
        
        sub_avg_score = sum(p.score for p in subreddit_posts) / len(subreddit_posts)
        sub_avg_comments = sum(p.num_comments for p in subreddit_posts) / len(subreddit_posts)
        
        return {
            'user_performance': {
                'avg_score': user_avg_score,
                'avg_comments': user_avg_comments,
                'total_posts': len(user_posts),
                'best_post_score': max(p.score for p in user_posts) if user_posts else 0
            },
            'subreddit_average': {
                'avg_score': sub_avg_score,
                'avg_comments': sub_avg_comments,
                'sample_size': len(subreddit_posts)
            },
            'comparison': {
                'score_ratio': user_avg_score / sub_avg_score if sub_avg_score > 0 else 0,
                'comment_ratio': user_avg_comments / sub_avg_comments if sub_avg_comments > 0 else 0,
                'performance_percentile': self._calculate_percentile(user_posts, subreddit_posts)
            }
        }
    
    def _calculate_percentile(self, user_posts: List[RedditPost], reference_posts: List[RedditPost]) -> float:
        """Calculate user's performance percentile compared to reference posts."""
        if not user_posts or not reference_posts:
            return 0.0
        
        user_avg = sum(p.score for p in user_posts) / len(user_posts)
        better_posts = sum(1 for p in reference_posts if p.score < user_avg)
        
        return (better_posts / len(reference_posts)) * 100


class TikTokRedditExtractor:
    """Extract Reddit usernames from TikTok data and discover popular subreddits."""
    
    def __init__(self, reddit_client: RedditAPIClient):
        self.reddit_client = reddit_client
        self.profile_extractor = ProfileExtractor(reddit_client)
        self.logger = logging.getLogger(__name__)
    
    def extract_reddit_usernames_from_tiktok_data(self, tiktok_json_path: str) -> TikTokDataExtraction:
        """Extract Reddit usernames mentioned in TikTok video data."""
        
        self.logger.info(f"Extracting Reddit usernames from: {tiktok_json_path}")
        
        extraction_result = TikTokDataExtraction()
        
        try:
            with open(tiktok_json_path, 'r', encoding='utf-8') as f:
                tiktok_data = json.load(f)
            
            if not isinstance(tiktok_data, list):
                self.logger.error("TikTok data is not a list format")
                return extraction_result
            
            extraction_result.total_videos_analyzed = len(tiktok_data)
            
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
            
            for video in tiktok_data:
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
                    self.logger.warning(f"Error processing video: {e}")
                    extraction_result.failed_extractions += 1
                    continue
            
            extraction_result.reddit_usernames_found = list(found_usernames)
            extraction_result.unique_usernames = len(found_usernames)
            extraction_result.extraction_patterns = dict(pattern_counts)
            
            self.logger.info(f"Extraction complete: {len(found_usernames)} unique Reddit usernames found")
            return extraction_result
            
        except Exception as e:
            self.logger.error(f"Error reading TikTok data: {e}")
            return extraction_result
    
    async def discover_subreddits_from_users(
        self, 
        usernames: List[str], 
        max_posts_per_user: int = 50,
        min_users_per_subreddit: int = 2
    ) -> List[SubredditDiscovery]:
        """Analyze Reddit users to discover popular subreddits."""
        
        self.logger.info(f"Discovering subreddits from {len(usernames)} users")
        
        subreddit_activity = defaultdict(lambda: {
            'users': set(),
            'total_posts': 0,
            'total_score': 0,
            'subreddit_info': None
        })
        
        processed_users = 0
        failed_users = 0
        
        for username in usernames:
            try:
                self.logger.info(f"Analyzing user: {username} ({processed_users + 1}/{len(usernames)})")
                
                # Get user posts
                user_posts = await self.reddit_client.get_user_posts(
                    username=username,
                    limit=max_posts_per_user,
                    sort_method=PostSortMethod.TOP,
                    time_filter=TimeFilter.YEAR
                )
                
                if user_posts:
                    processed_users += 1
                    
                    # Group posts by subreddit
                    for post in user_posts:
                        subreddit_name = post.subreddit.lower()
                        subreddit_activity[subreddit_name]['users'].add(username)
                        subreddit_activity[subreddit_name]['total_posts'] += 1
                        subreddit_activity[subreddit_name]['total_score'] += post.score
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.warning(f"Failed to analyze user {username}: {e}")
                failed_users += 1
                continue
        
        self.logger.info(f"User analysis complete: {processed_users} processed, {failed_users} failed")
        
        # Create SubredditDiscovery objects
        discoveries = []
        
        for subreddit_name, activity in subreddit_activity.items():
            user_count = len(activity['users'])
            
            # Skip subreddits with too few users
            if user_count < min_users_per_subreddit:
                continue
            
            avg_score = activity['total_score'] / activity['total_posts'] if activity['total_posts'] > 0 else 0
            
            discovery = SubredditDiscovery(
                subreddit_name=subreddit_name,
                discovered_from_users=list(activity['users']),
                user_count=user_count,
                total_user_posts=activity['total_posts'],
                avg_user_score=avg_score
            )
            
            # Calculate activity score for ranking
            discovery.calculate_activity_score()
            
            discoveries.append(discovery)
        
        # Sort by activity score
        discoveries.sort(key=lambda x: x.activity_score, reverse=True)
        
        # Assign popularity ranks
        for i, discovery in enumerate(discoveries, 1):
            discovery.popularity_rank = i
        
        self.logger.info(f"Subreddit discovery complete: {len(discoveries)} subreddits found")
        return discoveries
    
    async def enhance_subreddit_discoveries(
        self, 
        discoveries: List[SubredditDiscovery]
    ) -> List[SubredditDiscovery]:
        """Enhance subreddit discoveries with additional metadata."""
        
        self.logger.info(f"Enhancing {len(discoveries)} subreddit discoveries")
        
        enhanced_discoveries = []
        
        for discovery in discoveries:
            try:
                # Get subreddit info
                subreddit_info = await self.reddit_client.get_subreddit_info(discovery.subreddit_name)
                
                if subreddit_info:
                    discovery.subscriber_count = subreddit_info.subscribers
                    
                    # Categorize subreddit based on name and description
                    discovery.category = self._categorize_subreddit(
                        discovery.subreddit_name, 
                        subreddit_info.description
                    )
                
                enhanced_discoveries.append(discovery)
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Failed to enhance subreddit {discovery.subreddit_name}: {e}")
                # Still include it without enhancement
                enhanced_discoveries.append(discovery)
                continue
        
        return enhanced_discoveries
    
    def _categorize_subreddit(self, name: str, description: str) -> str:
        """Categorize subreddit based on name and description."""
        
        name_lower = name.lower()
        desc_lower = description.lower() if description else ""
        
        # Category keywords
        categories = {
            'gaming': ['gaming', 'game', 'video', 'steam', 'nintendo', 'xbox', 'playstation', 'pc', 'fps'],
            'technology': ['tech', 'programming', 'software', 'computer', 'coding', 'dev', 'linux', 'android'],
            'entertainment': ['movie', 'tv', 'show', 'netflix', 'film', 'entertainment', 'celebrity', 'music'],
            'lifestyle': ['food', 'fitness', 'health', 'fashion', 'travel', 'cooking', 'diy', 'home'],
            'education': ['science', 'history', 'learn', 'education', 'university', 'study', 'academic'],
            'discussion': ['askreddit', 'discussion', 'talk', 'chat', 'advice', 'help', 'support'],
            'creative': ['art', 'design', 'photography', 'writing', 'creative', 'draw', 'craft'],
            'news': ['news', 'politics', 'world', 'current', 'events', 'breaking'],
            'humor': ['funny', 'meme', 'joke', 'humor', 'comedy', 'wtf', 'facepalm'],
            'sports': ['sport', 'football', 'basketball', 'soccer', 'baseball', 'hockey', 'nfl', 'nba']
        }
        
        # Check name and description against categories
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in name_lower or keyword in desc_lower:
                    return category
        
        return 'general'
    
    async def scrape_posts_from_discovered_subreddits(
        self,
        discoveries: List[SubredditDiscovery],
        posts_per_subreddit: int = 25,
        time_filter: TimeFilter = TimeFilter.WEEK
    ) -> Dict[str, List[RedditPost]]:
        """Scrape popular posts from discovered subreddits."""
        
        self.logger.info(f"Scraping posts from {len(discoveries)} discovered subreddits")
        
        subreddit_posts = {}
        
        for discovery in discoveries[:20]:  # Limit to top 20 subreddits
            try:
                self.logger.info(f"Scraping r/{discovery.subreddit_name}")
                
                posts = await self.reddit_client.get_popular_posts_from_subreddit(
                    subreddit_name=discovery.subreddit_name,
                    limit=posts_per_subreddit,
                    time_filter=time_filter
                )
                
                if posts:
                    subreddit_posts[discovery.subreddit_name] = posts
                    self.logger.info(f"Retrieved {len(posts)} posts from r/{discovery.subreddit_name}")
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.warning(f"Failed to scrape r/{discovery.subreddit_name}: {e}")
                continue
        
        total_posts = sum(len(posts) for posts in subreddit_posts.values())
        self.logger.info(f"Post scraping complete: {total_posts} posts from {len(subreddit_posts)} subreddits")
        
        return subreddit_posts