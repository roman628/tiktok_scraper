#!/Users/ethan/tiktok_scraper/venv/bin/python
"""
Quick test of MS_TOKEN validation functionality
"""

import asyncio
from TikTokApi import TikTokApi

async def test_token(token):
    """Test if MS_TOKEN is valid"""
    try:
        async with TikTokApi() as api:
            await api.create_sessions(
                ms_tokens=[token], 
                num_sessions=1, 
                sleep_after=1,
                suppress_resource_load_types=["image", "media", "font", "stylesheet"]
            )
            print("✅ Token validation successful")
            return True
    except Exception as e:
        print(f"❌ Token validation failed: {e}")
        return False

# Test with dummy token
if __name__ == "__main__":
    dummy_token = "test_token_123"
    print(f"Testing token validation with dummy token...")
    result = asyncio.run(test_token(dummy_token))
    print(f"Result: {result}")