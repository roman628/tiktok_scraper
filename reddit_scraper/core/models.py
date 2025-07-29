"""
Data models for Reddit scraper system.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class PostSortMethod(Enum):
    """Post sorting methods for popularity analysis."""
    HOT = "hot"
    TOP = "top"
    NEW = "new"
    RISING = "rising"
    CONTROVERSIAL = "controversial"


class TimeFilter(Enum):
    """Time filters for post analysis."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL = "all"


@dataclass
class RedditUser:
    """Reddit user profile data model."""
    username: str
    id: str = ""
    created_utc: Optional[datetime] = None
    comment_karma: int = 0
    link_karma: int = 0
    total_karma: int = 0
    is_gold: bool = False
    is_mod: bool = False
    verified: bool = False
    has_verified_email: bool = False
    icon_img: str = ""
    subreddit_name: Optional[str] = None
    subreddit_title: Optional[str] = None
    account_age_days: int = 0
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.created_utc:
            self.account_age_days = (datetime.utcnow() - self.created_utc).days
        self.total_karma = self.comment_karma + self.link_karma


@dataclass
class RedditPost:
    """Reddit post data model."""
    id: str
    title: str
    author: str
    subreddit: str
    score: int
    upvote_ratio: float
    num_comments: int
    created_utc: datetime
    url: str
    selftext: str = ""
    link_flair_text: Optional[str] = None
    is_self: bool = False
    is_video: bool = False
    domain: str = ""
    permalink: str = ""
    gilded: int = 0
    all_awardings: List[Dict] = field(default_factory=list)
    total_awards_received: int = 0
    
    # Calculated fields
    popularity_score: float = 0.0
    engagement_rate: float = 0.0
    age_hours: float = 0.0
    awards_value: int = 0
    
    def __post_init__(self):
        """Calculate derived metrics."""
        self.age_hours = (datetime.utcnow() - self.created_utc).total_seconds() / 3600
        self.awards_value = sum(award.get('coin_reward', 0) for award in self.all_awardings)
        if self.score > 0 and self.age_hours > 0:
            self.engagement_rate = (self.num_comments + self.gilded * 10) / max(self.score, 1)


@dataclass
class SubredditData:
    """Subreddit information and statistics."""
    name: str
    display_name: str
    title: str
    description: str
    subscribers: int
    created_utc: datetime
    over18: bool = False
    public_description: str = ""
    lang: str = "en"
    subreddit_type: str = "public"
    
    # User activity in this subreddit
    user_posts: List[RedditPost] = field(default_factory=list)
    user_post_count: int = 0
    user_total_score: int = 0
    user_avg_score: float = 0.0
    user_activity_percentage: float = 0.0
    
    def calculate_user_stats(self):
        """Calculate user activity statistics for this subreddit."""
        if self.user_posts:
            self.user_post_count = len(self.user_posts)
            self.user_total_score = sum(post.score for post in self.user_posts)
            self.user_avg_score = self.user_total_score / self.user_post_count


@dataclass
class PopularityScore:
    """Comprehensive popularity scoring for posts."""
    raw_score: int
    normalized_score: float
    time_adjusted_score: float
    engagement_score: float
    awards_score: float
    composite_score: float
    percentile_rank: float = 0.0
    
    # Score components breakdown
    upvote_component: float = 0.0
    comment_component: float = 0.0
    time_component: float = 0.0
    awards_component: float = 0.0
    ratio_component: float = 0.0


@dataclass
class UserAnalysis:
    """Comprehensive user analysis results."""
    user: RedditUser
    total_posts_analyzed: int
    analysis_timeframe: str
    top_posts: List[RedditPost] = field(default_factory=list)
    subreddit_activity: Dict[str, SubredditData] = field(default_factory=dict)
    
    # Activity patterns
    most_active_subreddits: List[str] = field(default_factory=list)
    posting_frequency: Dict[str, int] = field(default_factory=dict)
    best_performing_posts: List[RedditPost] = field(default_factory=list)
    
    # Statistics
    avg_post_score: float = 0.0
    total_score: int = 0
    success_rate: float = 0.0  # Posts above average
    diversity_score: float = 0.0  # Number of different subreddits
    
    # Temporal analysis
    posting_times: Dict[int, int] = field(default_factory=dict)  # Hour -> count
    posting_days: Dict[int, int] = field(default_factory=dict)   # Day of week -> count
    
    def calculate_statistics(self):
        """Calculate derived statistics."""
        if self.top_posts:
            self.total_score = sum(post.score for post in self.top_posts)
            self.avg_post_score = self.total_score / len(self.top_posts)
            above_avg = sum(1 for post in self.top_posts if post.score > self.avg_post_score)
            self.success_rate = above_avg / len(self.top_posts) * 100
            self.diversity_score = len(self.subreddit_activity)


@dataclass
class ScrapingJob:
    """Scraping job configuration and status."""
    job_id: str
    username: str
    max_posts: int = 100
    sort_method: PostSortMethod = PostSortMethod.TOP
    time_filter: TimeFilter = TimeFilter.ALL
    include_comments: bool = False
    
    # Status tracking
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Results
    user_data: Optional[RedditUser] = None
    posts_scraped: List[RedditPost] = field(default_factory=list)
    analysis_result: Optional[UserAnalysis] = None


@dataclass
class SubredditDiscovery:
    """Subreddit discovery results from TikTok data analysis."""
    subreddit_name: str
    discovered_from_users: List[str] = field(default_factory=list)
    user_count: int = 0
    total_user_posts: int = 0
    avg_user_score: float = 0.0
    popularity_rank: int = 0
    category: str = "general"
    subscriber_count: int = 0
    activity_score: float = 0.0
    
    def calculate_activity_score(self):
        """Calculate overall activity score for ranking."""
        # Weight: user count (40%) + avg score (30%) + post count (30%)
        normalized_users = min(self.user_count / 10.0, 1.0)  # Cap at 10 users
        normalized_score = min(self.avg_user_score / 1000.0, 1.0)  # Cap at 1000 avg
        normalized_posts = min(self.total_user_posts / 100.0, 1.0)  # Cap at 100 posts
        
        self.activity_score = (
            0.4 * normalized_users +
            0.3 * normalized_score +
            0.3 * normalized_posts
        )


@dataclass
class TikTokDataExtraction:
    """Results from extracting Reddit usernames from TikTok data."""
    total_videos_analyzed: int = 0
    reddit_usernames_found: List[str] = field(default_factory=list)
    unique_usernames: int = 0
    extraction_patterns: Dict[str, int] = field(default_factory=dict)
    failed_extractions: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExportConfig:
    """Export configuration options."""
    format: str = "json"  # json, csv, excel, pdf
    include_posts: bool = True
    include_subreddits: bool = True
    include_analysis: bool = True
    max_posts_per_subreddit: int = 50
    
    # Filtering options
    min_score_threshold: int = 0
    exclude_nsfw: bool = True
    date_range: Optional[tuple] = None
    
    # Output options
    output_file: Optional[str] = None
    pretty_print: bool = True
    include_metadata: bool = True