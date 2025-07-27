#!/usr/bin/env python3
"""
Unified comment extraction for TikTok scraper
Consolidates all comment extraction functionality
"""

import asyncio
import gc
from typing import List, Optional
from datetime import datetime

from .models import CommentData, VideoMetadata, ProcessingStatus
from .utils import URLUtils
from .exceptions import CommentExtractionException, TokenException, ErrorHandler, retry_on_failure


class CommentExtractor:
    """Unified comment extractor combining all extraction methods"""
    
    def __init__(self, ms_token: str = None, error_handler: ErrorHandler = None):
        self.ms_token = ms_token
        self.error_handler = error_handler or ErrorHandler()
        self._api_session = None
        self._session_created_at = None
        
    async def validate_token(self) -> bool:
        """Validate MS_TOKEN by making a test API call"""
        if not self.ms_token:
            self.error_handler.handle_warning("No MS_TOKEN provided", "Token Validation")
            return False
        
        try:
            from TikTokApi import TikTokApi
            
            self.error_handler.handle_info("Validating MS_TOKEN...", "Token Validation")
            
            api = TikTokApi()
            await api.create_sessions(
                ms_tokens=[self.ms_token], 
                num_sessions=1, 
                sleep_after=1,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            
            # Test with a known video ID pattern (won't exist but validates token format)
            test_video_id = "7000000000000000000"
            
            try:
                video = api.video(id=test_video_id)
                await video.info()
            except Exception:
                # Expected to fail for non-existent video, but validates token worked
                pass
                
            await api.close_sessions()
            
            self.error_handler.handle_success("MS_TOKEN validated successfully", "Token Validation")
            return True
        
        except ImportError:
            self.error_handler.handle_warning(
                "TikTokApi not installed - comment extraction disabled",
                "Token Validation"
            )
            return False
        except Exception as e:
            self.error_handler.handle_error(
                TokenException("MS_TOKEN validation failed", original_error=e),
                "Token Validation"
            )
            return False
    
    async def extract_comments(self, url: str, max_comments: int = 10) -> List[CommentData]:
        """Extract comments from TikTok video"""
        if not self.ms_token:
            self.error_handler.handle_warning(
                "No MS_TOKEN available for comment extraction", 
                "Comment Extraction"
            )
            return []
        
        video_id = URLUtils.extract_video_id(url)
        if not video_id:
            raise CommentExtractionException(f"Could not extract video ID from URL: {url}")
        
        try:
            # Create fresh session for each extraction to avoid browser issues
            await self._create_api_session()
            
            comments = await self._extract_comments_from_api(video_id, max_comments)
            
            await self._cleanup_api_session()
            
            self.error_handler.handle_success(
                f"Extracted {len(comments)} comments",
                "Comment Extraction"
            )
            
            return comments
            
        except Exception as e:
            await self._cleanup_api_session()
            
            # Check for token expiry indicators
            error_msg = str(e).lower()
            if any(indicator in error_msg for indicator in ['token', 'auth', 'forbidden', 'unauthorized']):
                raise TokenException("MS_TOKEN appears to be expired or invalid", original_error=e)
            else:
                raise CommentExtractionException(f"Comment extraction failed: {e}", original_error=e)
    
    async def _create_api_session(self):
        """Create TikTokApi session"""
        try:
            from TikTokApi import TikTokApi
            
            await self._cleanup_api_session()  # Clean up any existing session
            
            self._api_session = TikTokApi()
            
            await asyncio.wait_for(
                self._api_session.create_sessions(
                    ms_tokens=[self.ms_token], 
                    num_sessions=1, 
                    sleep_after=1,
                    suppress_resource_load_types=["image", "media", "font", "stylesheet"]
                ),
                timeout=30
            )
            
            self._session_created_at = datetime.now()
            
        except ImportError:
            raise CommentExtractionException("TikTokApi not installed. Please install with: pip install TikTokApi")
        except asyncio.TimeoutError:
            raise CommentExtractionException("Session creation timed out")
        except Exception as e:
            raise CommentExtractionException(f"Failed to create API session: {e}", original_error=e)
    
    async def _extract_comments_from_api(self, video_id: str, max_comments: int) -> List[CommentData]:
        """Extract comments using TikTokApi"""
        if not self._api_session:
            raise CommentExtractionException("No active API session")
        
        comments = []
        
        try:
            comment_iter = self._api_session.video(id=video_id).comments(count=max_comments)
            
            async for comment in comment_iter:
                comment_data = await self._parse_comment(comment)
                if comment_data:
                    comments.append(comment_data)
                
                if len(comments) >= max_comments:
                    break
                
                # Clean up comment object to save memory
                del comment
                
        except Exception as e:
            raise CommentExtractionException(f"Failed to extract comments: {e}", original_error=e)
        
        return comments
    
    async def _parse_comment(self, comment) -> Optional[CommentData]:
        """Parse TikTok comment object into CommentData"""
        try:
            comment_dict = comment.as_dict
            user_dict = comment_dict.get("user", {})
            
            comment_data = CommentData(
                comment_id=comment.id,
                username=user_dict.get("unique_id", "unknown"),
                display_name=user_dict.get("nickname", "unknown"),
                text=comment_dict.get("text", ""),
                like_count=comment_dict.get("digg_count", 0),
                timestamp=comment_dict.get("create_time", 0)
            )
            
            # Extract replies if they exist (limit to save memory and time)
            reply_count = comment_dict.get("reply_comment_count", 0)
            if reply_count > 0:
                replies = await self._extract_comment_replies(comment, max_replies=2)
                comment_data.replies = replies
                comment_data.reply_count = len(replies)
            
            return comment_data
            
        except Exception as e:
            self.error_handler.handle_warning(
                f"Failed to parse comment: {e}",
                "Comment Parsing"
            )
            return None
    
    async def _extract_comment_replies(self, comment, max_replies: int = 2) -> List[CommentData]:
        """Extract replies to a comment"""
        replies = []
        
        try:
            reply_iter = comment.replies(count=max_replies)
            
            async for reply in reply_iter:
                reply_data = await self._parse_comment(reply)
                if reply_data:
                    replies.append(reply_data)
                
                if len(replies) >= max_replies:
                    break
                
                # Clean up reply object
                del reply
                
        except Exception as e:
            self.error_handler.handle_warning(
                f"Failed to extract comment replies: {e}",
                "Reply Extraction"
            )
        
        return replies
    
    async def _cleanup_api_session(self):
        """Cleanup TikTokApi session"""
        if self._api_session:
            try:
                await asyncio.wait_for(self._api_session.close_sessions(), timeout=10)
                if hasattr(self._api_session, 'playwright') and self._api_session.playwright:
                    await asyncio.wait_for(self._api_session.playwright.stop(), timeout=10)
            except (Exception, asyncio.TimeoutError):
                pass  # Ignore cleanup errors and timeouts
            finally:
                self._api_session = None
                self._session_created_at = None
                gc.collect()
    
    async def handle_token_expiry(self, new_token: str = None) -> bool:
        """Handle MS_TOKEN expiry and update token"""
        if new_token:
            self.ms_token = new_token
            
            # Validate new token
            if await self.validate_token():
                self.error_handler.handle_success(
                    "New MS_TOKEN validated and updated",
                    "Token Update"
                )
                return True
            else:
                self.error_handler.handle_error(
                    TokenException("New MS_TOKEN validation failed"),
                    "Token Update"
                )
                return False
        else:
            self.error_handler.handle_warning(
                "MS_TOKEN expired and no replacement provided",
                "Token Expiry"
            )
            self.ms_token = None
            return False
    
    def get_interactive_token(self) -> Optional[str]:
        """Get MS_TOKEN from user input interactively"""
        print("\n🔑 MS_TOKEN Required for Comment Extraction")
        print("="*50)
        print("To extract comments, you need a valid MS_TOKEN from your browser.")
        print("Instructions:")
        print("1. Open TikTok in your browser and log in")
        print("2. Open Developer Tools (F12)")
        print("3. Go to Application/Storage tab")
        print("4. Find 'msToken' cookie and copy its value")
        print("="*50)
        
        import sys
        if sys.stdout.isatty():
            while True:
                token = input("Enter your MS_TOKEN (or 'skip' to continue without comments): ").strip()
                
                if token.lower() == 'skip':
                    self.error_handler.handle_info(
                        "Skipping comment extraction",
                        "Token Input"
                    )
                    return None
                
                if len(token) > 50:  # Basic validation
                    return token
                else:
                    print("❌ Invalid token format. Please try again.")
        else:
            self.error_handler.handle_warning(
                "Not in interactive terminal - cannot get MS_TOKEN",
                "Token Input"
            )
            return None
    
    async def extract_and_update_metadata(self, metadata: VideoMetadata, max_comments: int = 10):
        """Extract comments and update VideoMetadata object"""
        if not self.ms_token:
            metadata.comments_extracted = False
            metadata.top_comments = []
            return
        
        try:
            metadata.processing_status = ProcessingStatus.EXTRACTING_COMMENTS
            
            comments = await self.extract_comments(metadata.url, max_comments)
            
            metadata.top_comments = comments
            metadata.comments_extracted = True
            metadata.comments_extracted_at = datetime.now().isoformat()
            
        except TokenException as e:
            self.error_handler.handle_error(e, "Comment Extraction")
            metadata.comments_extracted = False
            metadata.top_comments = []
            metadata.error_message = str(e)
        except CommentExtractionException as e:
            self.error_handler.handle_error(e, "Comment Extraction")
            metadata.comments_extracted = False
            metadata.top_comments = []
            metadata.error_message = str(e)
    
    async def cleanup(self):
        """Cleanup extractor resources"""
        await self._cleanup_api_session()
    
    def __del__(self):
        """Cleanup on destruction"""
        if self._api_session:
            # Can't use async in __del__, so we'll just delete the reference
            self._api_session = None