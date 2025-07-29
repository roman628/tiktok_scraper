"""
Reddit API client with rate limiting and error handling.
"""
import praw
import time
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from praw.exceptions import RedditAPIException
from .models import RedditUser, RedditPost, SubredditData, PostSortMethod, TimeFilter


class RateLimitManager:
    """Intelligent rate limiting for Reddit API."""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.call_times = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make an API call."""
        async with self.lock:
            now = time.time()
            # Remove calls older than 1 minute
            self.call_times = [t for t in self.call_times if now - t < 60]
            
            if len(self.call_times) >= self.calls_per_minute:
                # Need to wait
                sleep_time = 60 - (now - self.call_times[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    return await self.acquire()
            
            self.call_times.append(now)


class RedditAPIClient:
    """Reddit API client with authentication and rate limiting."""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.rate_limiter = RateLimitManager()
        self.logger = logging.getLogger(__name__)
        
        # Test authentication
        try:
            self.reddit.user.me()
            self.logger.info("Reddit API authentication successful")
        except Exception as e:
            self.logger.warning(f"Reddit API authentication failed: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(RedditAPIException)
    )
    async def get_user_profile(self, username: str) -> Optional[RedditUser]:
        """Get Reddit user profile information."""
        await self.rate_limiter.acquire()
        
        try:
            redditor = self.reddit.redditor(username)
            
            # Check if user exists and is accessible
            try:
                _ = redditor.created_utc
            except Exception:
                self.logger.warning(f"User {username} not found or private")
                return None
            
            user_data = RedditUser(
                username=redditor.name,
                id=redditor.id,
                created_utc=datetime.utcfromtimestamp(redditor.created_utc),
                comment_karma=getattr(redditor, 'comment_karma', 0),
                link_karma=getattr(redditor, 'link_karma', 0),
                is_gold=getattr(redditor, 'is_gold', False),
                is_mod=getattr(redditor, 'is_mod', False),
                verified=getattr(redditor, 'verified', False),
                has_verified_email=getattr(redditor, 'has_verified_email', False),
                icon_img=getattr(redditor, 'icon_img', ''),
                subreddit_name=getattr(redditor.subreddit, 'display_name', None) if hasattr(redditor, 'subreddit') else None,
                subreddit_title=getattr(redditor.subreddit, 'title', None) if hasattr(redditor, 'subreddit') else None
            )
            
            self.logger.info(f"Retrieved profile for user: {username}")
            return user_data
            
        except Exception as e:
            self.logger.error(f"Error fetching user profile for {username}: {e}")
            return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_user_posts(
        self, 
        username: str, 
        limit: int = 100,
        sort_method: PostSortMethod = PostSortMethod.TOP,
        time_filter: TimeFilter = TimeFilter.ALL
    ) -> List[RedditPost]:
        """Get user's posts with specified sorting and filtering."""
        await self.rate_limiter.acquire()
        
        try:
            redditor = self.reddit.redditor(username)
            posts = []
            
            # Get submissions based on sort method
            if sort_method == PostSortMethod.TOP:
                submissions = redditor.submissions.top(time_filter=time_filter.value, limit=limit)
            elif sort_method == PostSortMethod.HOT:
                submissions = redditor.submissions.hot(limit=limit)
            elif sort_method == PostSortMethod.NEW:
                submissions = redditor.submissions.new(limit=limit)
            else:
                submissions = redditor.submissions.top(time_filter=time_filter.value, limit=limit)
            
            for submission in submissions:
                try:
                    post = RedditPost(
                        id=submission.id,
                        title=submission.title,
                        author=submission.author.name if submission.author else '[deleted]',
                        subreddit=submission.subreddit.display_name,
                        score=submission.score,
                        upvote_ratio=getattr(submission, 'upvote_ratio', 0.0),
                        num_comments=submission.num_comments,
                        created_utc=datetime.utcfromtimestamp(submission.created_utc),
                        url=submission.url,
                        selftext=getattr(submission, 'selftext', ''),
                        link_flair_text=getattr(submission, 'link_flair_text', None),
                        is_self=submission.is_self,
                        is_video=getattr(submission, 'is_video', False),
                        domain=getattr(submission, 'domain', ''),
                        permalink=submission.permalink,
                        gilded=getattr(submission, 'gilded', 0),
                        all_awardings=getattr(submission, 'all_awardings', []),
                        total_awards_received=getattr(submission, 'total_awards_received', 0)
                    )
                    posts.append(post)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing post {submission.id}: {e}")
                    continue
            
            self.logger.info(f"Retrieved {len(posts)} posts for user: {username}")
            return posts
            
        except Exception as e:
            self.logger.error(f"Error fetching posts for {username}: {e}")
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_subreddit_info(self, subreddit_name: str) -> Optional[SubredditData]:
        """Get subreddit information and statistics."""
        await self.rate_limiter.acquire()
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            subreddit_data = SubredditData(
                name=subreddit.display_name,
                display_name=subreddit.display_name,
                title=getattr(subreddit, 'title', ''),
                description=getattr(subreddit, 'description', ''),
                subscribers=getattr(subreddit, 'subscribers', 0),
                created_utc=datetime.utcfromtimestamp(subreddit.created_utc),
                over18=getattr(subreddit, 'over18', False),
                public_description=getattr(subreddit, 'public_description', ''),
                lang=getattr(subreddit, 'lang', 'en'),
                subreddit_type=getattr(subreddit, 'subreddit_type', 'public')
            )
            
            self.logger.info(f"Retrieved info for subreddit: {subreddit_name}")
            return subreddit_data
            
        except Exception as e:
            self.logger.error(f"Error fetching subreddit info for {subreddit_name}: {e}")
            return None
    
    async def get_popular_posts_from_subreddit(
        self, 
        subreddit_name: str, 
        limit: int = 25,
        time_filter: TimeFilter = TimeFilter.WEEK
    ) -> List[RedditPost]:
        """Get popular posts from a specific subreddit."""
        await self.rate_limiter.acquire()
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for submission in subreddit.top(time_filter=time_filter.value, limit=limit):
                try:
                    post = RedditPost(
                        id=submission.id,
                        title=submission.title,
                        author=submission.author.name if submission.author else '[deleted]',
                        subreddit=submission.subreddit.display_name,
                        score=submission.score,
                        upvote_ratio=getattr(submission, 'upvote_ratio', 0.0),
                        num_comments=submission.num_comments,
                        created_utc=datetime.utcfromtimestamp(submission.created_utc),
                        url=submission.url,
                        selftext=getattr(submission, 'selftext', ''),
                        link_flair_text=getattr(submission, 'link_flair_text', None),
                        is_self=submission.is_self,
                        is_video=getattr(submission, 'is_video', False),
                        domain=getattr(submission, 'domain', ''),
                        permalink=submission.permalink,
                        gilded=getattr(submission, 'gilded', 0),
                        all_awardings=getattr(submission, 'all_awardings', []),
                        total_awards_received=getattr(submission, 'total_awards_received', 0)
                    )
                    posts.append(post)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing post {submission.id}: {e}")
                    continue
            
            return posts
            
        except Exception as e:
            self.logger.error(f"Error fetching popular posts from {subreddit_name}: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check if Reddit API is accessible."""
        try:
            await self.rate_limiter.acquire()
            # Try to access a known subreddit
            subreddit = self.reddit.subreddit('announcements')
            _ = subreddit.display_name
            return True
        except Exception as e:
            self.logger.error(f"Reddit API health check failed: {e}")
            return False