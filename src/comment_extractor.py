"""Comment extraction from TikTok videos using API."""

import os
import asyncio
import time
from typing import List, Dict, Any, Optional
from TikTokApi import TikTokApi
from src.models import Comment
from src.url_processor import URLProcessor

class CommentExtractor:
    """Handles TikTok comment extraction with API integration."""
    
    def __init__(self, ms_token: Optional[str] = None, max_comments: int = 50):
        """Initialize comment extractor.
        
        Args:
            ms_token: TikTok MS_TOKEN for API authentication
            max_comments: Maximum comments to fetch per video
        """
        self.ms_token = ms_token or os.getenv('MS_TOKEN', '')
        self.max_comments = max_comments
        self.api = None
        self.session = None
        
        if not self.ms_token:
            print("Warning: MS_TOKEN not provided. Comment extraction may fail.")
    
    async def _initialize_api(self):
        """Initialize TikTok API with browser session."""
        if self.api is None:
            self.api = TikTokApi()
            await self.api.create_sessions(
                ms_tokens=[self.ms_token],
                num_sessions=1,
                sleep_after=3,
                headless=True
            )
            self.session = self.api.sessions[0]
    
    async def extract_comments(self, url: str) -> List[Comment]:
        """Extract comments from TikTok video.
        
        Args:
            url: TikTok video URL
            
        Returns:
            List of Comment objects with replies
        """
        video_id = URLProcessor.extract_video_id(url)
        if not video_id:
            print(f"Could not extract video ID from URL: {url}")
            return []
        
        try:
            await self._initialize_api()
            
            # Get video object
            video = self.api.video(id=video_id)
            
            # Fetch comments
            comments = []
            comment_count = 0
            
            async for comment_obj in video.comments(count=self.max_comments):
                if comment_count >= self.max_comments:
                    break
                
                # Create comment object using proper attribute access
                comment = self._parse_comment(comment_obj)
                
                # Fetch replies if they exist (using attribute access)
                reply_count = getattr(comment_obj, 'reply_comment_total', 0)
                if reply_count > 0:
                    replies = await self._fetch_replies(comment_obj)
                    comment.replies = replies
                
                comments.append(comment)
                comment_count += 1
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            return comments
            
        except Exception as e:
            print(f"Error extracting comments: {e}")
            return []
    
    def _parse_comment(self, comment_obj) -> Comment:
        """Parse TikTok API comment object into Comment model."""
        # Use proper attribute access on the TikTok API object
        text = getattr(comment_obj, 'text', '')
        
        # Handle author attributes - try multiple possible fields
        author = getattr(comment_obj, 'author', None)
        if author:
            # Try nickname first, then username, then unique_id
            user = getattr(author, 'nickname', None) or \
                   getattr(author, 'username', None) or \
                   getattr(author, 'unique_id', 'Unknown')
        else:
            user = 'Unknown'
        
        likes = getattr(comment_obj, 'likes_count', 0)
        
        return Comment(
            text=text,
            user=user,
            likes=likes,
            replies=[]
        )
    
    async def _fetch_replies(self, comment_obj, max_replies: int = 10) -> List[Comment]:
        """Fetch replies for a comment using the working legacy pattern.
        
        Args:
            comment_obj: Parent comment object
            max_replies: Maximum replies to fetch
            
        Returns:
            List of reply Comment objects
        """
        replies = []
        
        try:
            reply_count = 0
            async for reply in comment_obj.replies():
                # Parse reply using the same attribute access pattern
                reply_comment = self._parse_comment(reply)
                replies.append(reply_comment)
                reply_count += 1
                if reply_count >= max_replies:
                    break
        except Exception as e:
            print(f"Error fetching replies: {e}")
        
        return replies
    
    def extract_comments_sync(self, url: str) -> List[Comment]:
        """Synchronous wrapper for comment extraction.
        
        Args:
            url: TikTok video URL
            
        Returns:
            List of Comment objects
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            comments = loop.run_until_complete(self.extract_comments(url))
            loop.close()
            return comments
        except Exception as e:
            print(f"Error in sync comment extraction: {e}")
            return []
    
    async def cleanup(self):
        """Clean up API resources."""
        if self.api:
            try:
                await self.api.close_sessions()
            except:
                pass
            self.api = None
            self.session = None
    
    def cleanup_sync(self):
        """Synchronous cleanup wrapper."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.cleanup())
            loop.close()
        except:
            pass