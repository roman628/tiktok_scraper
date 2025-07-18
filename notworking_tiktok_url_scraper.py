#!/usr/bin/env python3
"""
Existing Session TikTok Extractor
Uses your existing logged-in Chrome/Firefox session
"""

import asyncio
import sys
import time
import random
import json
import os
from playwright.async_api import async_playwright
from pathlib import Path

async def connect_to_existing_browser():
    """Connect to your existing browser session"""
    print("🔌 Connecting to Existing Browser Session")
    print("=" * 50)
    print("💡 This uses your existing logged-in browser")
    print()
    
    # Method 1: Try connecting to Chrome with remote debugging
    print("📋 Option 1: Chrome Remote Debugging")
    print("1. Close all Chrome windows")
    print("2. Open command prompt and run:")
    print("   chrome --remote-debugging-port=9222 --user-data-dir=\"C:\\temp\\chrome-debug\"")
    print("3. Chrome will open - log into TikTok normally")
    print("4. Navigate to any TikTok hashtag page")
    print("5. Press ENTER here when ready")
    
    choice = input("\n🚀 Try Chrome remote debugging? (y/n): ").strip().lower()
    
    if choice in ['y', 'yes']:
        try:
            async with async_playwright() as p:
                print("🔌 Attempting to connect to Chrome...")
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                print("✅ Connected to existing Chrome!")
                
                # Get the active page
                contexts = browser.contexts
                if contexts and contexts[0].pages:
                    page = contexts[0].pages[0]
                    print(f"📄 Using existing page: {page.url}")
                    return browser, page
                else:
                    # Create new page in existing browser
                    context = await browser.new_context()
                    page = await context.new_page()
                    print("📄 Created new page in existing browser")
                    return browser, page
                    
        except Exception as e:
            print(f"❌ Chrome connection failed: {e}")
            print("💡 Make sure Chrome is running with remote debugging")
    
    # Method 2: Use existing user data
    print("\n📋 Option 2: Use Existing User Data")
    print("This copies your existing browser session")
    
    choice2 = input("🚀 Try existing user data? (y/n): ").strip().lower()
    
    if choice2 in ['y', 'yes']:
        return await launch_with_existing_data()
    
    return None, None

async def launch_with_existing_data():
    """Launch browser with existing user data"""
    try:
        # Common Chrome user data paths
        user_data_paths = [
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data"),
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default"),
            "C:\\Users\\Default\\AppData\\Local\\Google\\Chrome\\User Data",
        ]
        
        for user_data_path in user_data_paths:
            if os.path.exists(user_data_path):
                print(f"✅ Found Chrome data: {user_data_path}")
                
                async with async_playwright() as p:
                    print("🚀 Launching Chrome with existing data...")
                    
                    # Copy to temp location to avoid conflicts
                    temp_data = "C:\\temp\\chrome-tiktok"
                    
                    browser = await p.chromium.launch(
                        headless=False,
                        user_data_dir=temp_data,
                        args=[
                            '--disable-web-security',
                            '--disable-features=VizDisplayCompositor',
                            '--no-first-run'
                        ]
                    )
                    
                    page = await browser.new_page()
                    print("✅ Browser launched with existing session data")
                    
                    return browser, page
                    
        print("❌ No Chrome user data found")
        return None, None
        
    except Exception as e:
        print(f"❌ User data launch failed: {e}")
        return None, None

async def manual_session_approach():
    """Manual approach - user handles everything"""
    print("\n🔧 Manual Session Approach")
    print("=" * 30)
    print("💡 Simplest method - you do the navigation")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("\n📋 Manual Steps:")
        print("1. Browser opened")
        print("2. Go to tiktok.com and log in normally")
        print("3. Navigate to any hashtag page (e.g., tiktok.com/tag/reddit)")
        print("4. Scroll down manually a few times to load content")
        print("5. Press ENTER here to start automated extraction")
        
        # Wait for manual setup
        input("⏳ Press ENTER when you're logged in and on a hashtag page...")
        
        # Verify setup
        current_url = page.url
        print(f"🌐 Current page: {current_url}")
        
        if "tiktok.com" not in current_url:
            print("❌ Not on TikTok! Please navigate to TikTok first.")
            await browser.close()
            return None, None
        
        # Quick test
        test_urls = await page.evaluate("""
            () => {
                const links = [];
                const videoElements = document.querySelectorAll('a[href*="/video/"]');
                videoElements.forEach(el => {
                    if (el.href && el.href.includes('/video/')) {
                        links.push(el.href);
                    }
                });
                return [...new Set(links)].slice(0, 5);
            }
        """)
        
        if len(test_urls) > 0:
            print(f"✅ Found {len(test_urls)} test URLs - extraction ready!")
            return browser, page
        else:
            print("⚠️ No video URLs found. Make sure you're on a hashtag page with videos.")
            return browser, page

async def advanced_extraction_existing_session(page, target_urls=3000):
    """Extract using existing session"""
    print(f"🎯 Advanced Extraction (Existing Session)")
    print(f"   Target: {target_urls} URLs")
    print(f"   Using your logged-in session")
    
    all_urls = set()
    scroll_count = 0
    start_time = time.time()
    no_new_urls_streak = 0
    
    # Check login status
    login_status = await page.evaluate("""
        () => {
            const loginButton = document.querySelector('text=Log in');
            const profileButton = document.querySelector('[data-e2e="profile-icon"]');
            const uploadButton = document.querySelector('[data-e2e="upload"]');
            
            return {
                hasLoginButton: !!loginButton,
                hasProfileButton: !!profileButton,
                hasUploadButton: !!uploadButton,
                url: window.location.href
            };
        }
    """)
    
    if login_status['hasLoginButton']:
        print("⚠️ Appears to be logged out - may have limited content")
    else:
        print("✅ Appears to be logged in - unlimited content available")
    
    print(f"\n🔄 Starting extraction...")
    
    while len(all_urls) < target_urls and no_new_urls_streak < 50:
        scroll_count += 1
        
        # Varied scrolling patterns
        if scroll_count % 3 == 0:
            # Fast scroll
            scroll_distance = random.randint(1200, 2000)
            delay = random.uniform(0.5, 1.0)
        elif scroll_count % 3 == 1:
            # Medium scroll
            scroll_distance = random.randint(800, 1200)
            delay = random.uniform(1.0, 2.0)
        else:
            # Slow scroll
            scroll_distance = random.randint(400, 800)
            delay = random.uniform(2.0, 3.0)
        
        # Perform scroll
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        await asyncio.sleep(delay)
        
        # Extract URLs every few scrolls
        if scroll_count % 3 == 0:
            new_urls = await page.evaluate("""
                () => {
                    const links = [];
                    const videoElements = document.querySelectorAll('a[href*="/video/"]');
                    videoElements.forEach(el => {
                        if (el.href && el.href.includes('/video/')) {
                            links.push(el.href);
                        }
                    });
                    return [...new Set(links)];
                }
            """)
            
            initial_count = len(all_urls)
            all_urls.update(new_urls)
            new_count = len(all_urls) - initial_count
            
            if new_count == 0:
                no_new_urls_streak += 1
            else:
                no_new_urls_streak = 0
            
            # Progress report
            if scroll_count % 15 == 0:
                elapsed = time.time() - start_time
                rate = len(all_urls) / elapsed * 60 if elapsed > 0 else 0
                print(f"📊 Scroll {scroll_count}: {len(all_urls)} URLs (+{new_count}) | {rate:.1f}/min | No new: {no_new_urls_streak}")
        
        # Advanced techniques
        if scroll_count % 30 == 0:
            print("🔄 Refreshing content...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        
        # Break if hitting limits
        if no_new_urls_streak > 20:
            print("⚠️ Hitting content limits - may need different hashtag")
            break
    
    elapsed = time.time() - start_time
    print(f"\n🏁 Extraction complete!")
    print(f"📊 Results: {len(all_urls)} URLs in {elapsed/60:.1f} minutes")
    
    return list(all_urls)

async def main():
    print("Existing Session TikTok Extractor")
    print("=" * 40)
    
    # Try different connection methods
    browser, page = await connect_to_existing_browser()
    
    if not browser:
        print("\n🔧 Falling back to manual approach...")
        browser, page = await manual_session_approach()
    
    if not browser:
        print("❌ Could not establish browser session")
        return
    
    try:
        # Get target count
        target_input = input("\n🎯 How many URLs to extract? (default: 2000): ").strip()
        target = int(target_input) if target_input else 2000
        
        # Perform extraction
        urls = await advanced_extraction_existing_session(page, target)
        
        if urls:
            # Save results
            filename = f"existing_session_urls_{len(urls)}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                for url in urls:
                    f.write(url + '\n')
            
            print(f"\n💾 Saved {len(urls)} URLs to {filename}")
            print(f"🎉 Ready for your scraper!")
            print(f"💡 Next command:")
            print(f"   python tiktok_scraper.py --from-file {filename} --whisper --append master.json")
        else:
            print("❌ No URLs extracted")
    
    finally:
        input("\n⏳ Press ENTER to close browser...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())