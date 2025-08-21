"""Comment extraction from TikTok videos using API."""

import os
import asyncio
import time
from typing import List, Dict, Any, Optional, Set
from TikTokApi import TikTokApi
from src.models import Comment
from src.url_processor import URLProcessor
from src.resource_manager import ResourceManager

try:
    import tomllib
except ImportError:
    import tomli as tomllib

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
        self.browser_pids: Set[int] = set()  # Track browser process PIDs
        
        if not self.ms_token:
            print("Warning: MS_TOKEN not provided. Comment extraction may fail.")
    
    def _reload_ms_token(self) -> Optional[str]:
        """Reload MS_TOKEN from config file.
        
        Returns:
            Current MS_TOKEN from config or None
        """
        config_path = "config.toml"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'rb') as f:
                    config = tomllib.load(f)
                    return config.get('tiktok', {}).get('ms_token')
            except Exception:
                pass
        return None
    
    async def _initialize_api(self, force_new: bool = False):
        """Initialize TikTok API with browser session.
        
        Args:
            force_new: Force creation of new session even if one exists
        """
        # Clean up existing session if forcing new one
        if force_new and self.api:
            try:
                await self.api.close_sessions()
            except:
                pass
            self.api = None
            self.session = None
            # Kill any tracked browser processes
            if self.browser_pids:
                ResourceManager.kill_browser_processes(list(self.browser_pids))
                self.browser_pids.clear()
        
        if self.api is None:
            # Get current browser PIDs before creating new session
            pids_before = ResourceManager.get_browser_pids()
            
            self.api = TikTokApi()
            await self.api.create_sessions(
                ms_tokens=[self.ms_token],
                num_sessions=1,
                sleep_after=1,
                headless=True,  # Run with visible browser to avoid bot detection
                browser="webkit"  # Use webkit as suggested by TikTok error
            )
            self.session = self.api.sessions[0]
            
            # Track new browser PIDs created by this session
            pids_after = ResourceManager.get_browser_pids()
            self.browser_pids = pids_after - pids_before
            if self.browser_pids:
                print(f"CommentExtractor: Tracking {len(self.browser_pids)} new browser PIDs: {list(self.browser_pids)}")
    
    async def extract_comments(self, url: str) -> List[Comment]:
        """Extract comments from TikTok video.
        
        Args:
            url: TikTok video URL
            
        Returns:
            List of Comment objects with replies
        """
        print(f"\n[CommentExtractor] Starting extraction for: {url}")
        initial_browser_count = len(ResourceManager.get_browser_pids())
        print(f"[CommentExtractor] Initial browser process count: {initial_browser_count}")
        
        video_id = URLProcessor.extract_video_id(url)
        if not video_id:
            print(f"Could not extract video ID from URL: {url}")
            return []
        
        try:
            # Reload MS_TOKEN from config to check for updates
            current_token = self._reload_ms_token()
            if current_token and current_token != self.ms_token:
                print(f"MS_TOKEN updated, creating new session...")
                self.ms_token = current_token
                # Force re-initialization with new token
                await self._initialize_api(force_new=True)
            else:
                # Normal initialization
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
                
                # Rate limiting - increased to avoid bot detection
                await asyncio.sleep(1.0)
            
            # ALWAYS clean up session after extraction to avoid accumulation
            print(f"[CommentExtractor] Extracted {len(comments)} comments, forcing cleanup...")
            await self.cleanup(force=True)
            
            final_browser_count = len(ResourceManager.get_browser_pids())
            print(f"[CommentExtractor] Final browser process count: {final_browser_count}")
            if final_browser_count > initial_browser_count:
                print(f"[CommentExtractor] WARNING: Browser process leak detected! {final_browser_count - initial_browser_count} processes accumulated")
            
            return comments
            
        except Exception as e:
            print(f"Error extracting comments: {e}")
            # Ensure cleanup even on error
            await self.cleanup(force=True)
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
    
    async def cleanup(self, force: bool = False):
        """Clean up API resources.
        
        Args:
            force: Force immediate cleanup with process killing
        """
        cleanup_success = False
        
        if self.api:
            try:
                # Try graceful cleanup first
                if hasattr(self.api, 'browser'):
                    await self.api.browser.close()
                await self.api.close_sessions()
                cleanup_success = True
            except Exception as e:
                print(f"Warning: Graceful cleanup failed: {e}")
            finally:
                self.api = None
                self.session = None
        
        # Force kill browser processes if requested or cleanup failed
        if force or not cleanup_success:
            if self.browser_pids:
                killed = ResourceManager.kill_browser_processes(list(self.browser_pids))
                if killed > 0:
                    print(f"Force killed {killed} tracked browser processes")
                self.browser_pids.clear()
            else:
                # Kill all browser processes as fallback
                killed = ResourceManager.kill_browser_processes()
                if killed > 0:
                    print(f"Killed {killed} browser processes (fallback)")
        
        # Verify cleanup success
        remaining_pids = ResourceManager.get_browser_pids()
        if remaining_pids:
            print(f"WARNING: {len(remaining_pids)} browser processes still running after cleanup")
            # Force kill remaining processes
            ResourceManager.kill_browser_processes(list(remaining_pids))
        else:
            print("Browser cleanup verified: no processes remaining")
    
    def cleanup_sync(self):
        """Synchronous cleanup with proper timeout and fallback."""
        if not self.api:
            return
        
        try:
            # Try async cleanup with strict timeout
            loop = None
            try:
                # Create new event loop for cleanup
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run cleanup with timeout and force flag
                future = loop.create_task(self.cleanup(force=True))
                loop.run_until_complete(asyncio.wait_for(future, timeout=3.0))
                
            except asyncio.TimeoutError:
                print("Warning: Async cleanup timed out, forcing browser kill")
                self._force_cleanup()
            except Exception as e:
                print(f"Warning: Async cleanup failed: {e}, forcing browser kill")
                self._force_cleanup()
            finally:
                if loop and not loop.is_closed():
                    try:
                        # Give Playwright tasks a moment to finish
                        loop.run_until_complete(asyncio.sleep(0.1))
                        loop.close()
                    except:
                        pass
                    
        except Exception as e:
            print(f"Warning: Critical error in cleanup: {e}")
            self._force_cleanup()
    
    def _force_cleanup(self):
        """Force cleanup by killing browser processes."""
        try:
            # Kill tracked PIDs first, then scan for any remaining
            if self.browser_pids:
                ResourceManager.kill_browser_processes(list(self.browser_pids))
                self.browser_pids.clear()
            else:
                ResourceManager.kill_browser_processes()
        except Exception as e:
            print(f"Warning: Failed to kill browser processes: {e}")
        finally:
            self.api = None
            self.session = None