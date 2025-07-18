#!/usr/bin/env python3
"""
Test script to understand the current TikTokApi structure
"""

import asyncio
from TikTokApi import TikTokApi

MS_TOKEN = "cwekmq1ZxFChpLaKF4Ww9jeIhoK4-ZsnjwGgIzn0AkFuybnGd5mrrSs1wpGaKhb3sqmr9b_Z_QEaYjuZgbCT7q4YIHPAutbDEmQ3PgZ-UfBNO1CPOnm2RhQcanaBhFuu5dtVZG_mNdnOAAB0dVn84dPb"

async def test_api():
    api = TikTokApi()
    
    try:
        # Create sessions
        await api.create_sessions(ms_tokens=[MS_TOKEN], num_sessions=1, sleep_after=3)
        
        # Test getting a video
        video_id = "7517900243405376773"
        video = api.video(id=video_id)
        
        print("Video object created successfully")
        print(f"Video methods: {[method for method in dir(video) if not method.startswith('_')]}")
        
        # Test getting video info
        try:
            video_info = await video.info()
            print("Video info retrieved successfully")
            print(f"Video info keys: {list(video_info.keys()) if isinstance(video_info, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"Error getting video info: {e}")
        
        # Test getting comments
        try:
            comments = []
            comment_count = 0
            async for comment in video.comments():
                print(f"Comment object: {type(comment)}")
                print(f"Comment attributes: {[attr for attr in dir(comment) if not attr.startswith('_')]}")
                
                if hasattr(comment, 'id'):
                    print(f"Comment ID: {comment.id}")
                if hasattr(comment, 'text'):
                    print(f"Comment text: {comment.text}")
                
                comment_count += 1
                if comment_count >= 2:  # Just get first 2 for testing
                    break
                    
        except Exception as e:
            print(f"Error getting comments: {e}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            await api.close_sessions()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_api())