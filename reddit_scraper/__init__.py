"""
Reddit User Profile Scraper

A comprehensive tool for extracting Reddit user profiles, analyzing their most 
popular posts, and understanding their activity patterns across subreddits.
"""

__version__ = "1.0.0"
__author__ = "Reddit Scraper Team"
__description__ = "Comprehensive Reddit user profile analysis tool"

from .core.models import (
    RedditUser,
    RedditPost, 
    SubredditData,
    UserAnalysis,
    PostSortMethod,
    TimeFilter,
    ExportConfig
)

from .core.reddit_client import RedditAPIClient
from .services.profile_extractor import ProfileExtractor
from .exporters.data_exporter import DataExporter

__all__ = [
    'RedditUser',
    'RedditPost',
    'SubredditData', 
    'UserAnalysis',
    'PostSortMethod',
    'TimeFilter',
    'ExportConfig',
    'RedditAPIClient',
    'ProfileExtractor',
    'DataExporter'
]