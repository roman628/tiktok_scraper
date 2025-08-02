#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Connect to existing Firefox browser and collect TikTok URLs from #reddit
"""

import time
import json
import re
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import subprocess
import psutil

def find_firefox_process():
    """Find if Firefox is already running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'firefox' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def start_firefox_with_remote_debugging():
    """Start Firefox with remote debugging if not already running"""
    if not find_firefox_process():
        print("🔥 Starting Firefox with remote debugging...")
        # Start Firefox with remote debugging enabled
        subprocess.Popen([
            '/Applications/Firefox.app/Contents/MacOS/firefox',
            '--remote-debugging-port=9222',
            '--new-instance'
        ])
        time.sleep(3)
    else:
        print("✅ Firefox already running")

def connect_to_existing_firefox():
    """Connect to existing Firefox session"""
    try:
        print("🔗 Attempting to connect to existing Firefox...")
        
        # Firefox options
        options = Options()
        options.add_argument("--profile")  # Use default profile
        
        # Create driver (this will open a new Firefox window but with your profile)
        driver = webdriver.Firefox(options=options)
        print("✅ Connected to Firefox successfully")
        
        return driver
        
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return None

def navigate_to_reddit_hashtag(driver):
    """Navigate to TikTok #reddit hashtag"""
    try:
        url = "https://www.tiktok.com/tag/reddit"
        print(f"🌐 Navigating to: {url}")
        driver.get(url)
        
        # Wait for page to load
        time.sleep(5)
        
        # Handle any popups
        handle_popups(driver)
        
        return True
        
    except Exception as e:
        print(f"❌ Navigation failed: {e}")
        return False

def handle_popups(driver):
    """Handle TikTok popups and consent forms"""
    try:
        popup_selectors = [
            'button[data-e2e="close-button"]',
            'button[aria-label="Close"]',
            'div[data-e2e="modal-close-inner-button"]',
            'button[class*="close"]',
            'svg[data-e2e="close-icon"]'
        ]
        
        for selector in popup_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        element.click()
                        print("✅ Closed popup")
                        time.sleep(1)
                        return
            except:
                continue
                
    except Exception as e:
        print(f"⚠️  Popup handling: {e}")

def scroll_and_collect_urls(driver, max_videos=200):
    """Scroll through TikTok and collect video URLs"""
    print(f"📜 Starting to collect {max_videos} video URLs from #reddit...")
    
    collected_urls = set()
    video_data = []
    scroll_count = 0
    last_height = 0
    no_new_content_count = 0
    
    start_time = time.time()
    
    try:
        while len(collected_urls) < max_videos:
            # Extract URLs from current view
            new_urls = extract_urls_from_page(driver)
            
            for url_data in new_urls:
                if url_data['url'] not in collected_urls:
                    collected_urls.add(url_data['url'])
                    video_data.append(url_data)
            
            # Progress update
            if len(collected_urls) > 0 and len(collected_urls) % 25 == 0:
                elapsed = (time.time() - start_time) / 60
                print(f"   📊 Collected {len(collected_urls)} URLs ({elapsed:.1f}m)")
            
            # Scroll down
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
            scroll_count += 1
            
            # Human-like delay
            delay = random.uniform(2, 4)
            time.sleep(delay)
            
            # Check if we've reached the bottom
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_new_content_count += 1
                if no_new_content_count >= 5:
                    print("⚠️  No new content detected, stopping...")
                    break
            else:
                no_new_content_count = 0
                last_height = new_height
            
            # Occasional longer pause
            if scroll_count % 20 == 0:
                print("   ⏸️  Taking a break...")
                time.sleep(random.uniform(8, 15))
        
        print(f"✅ Collection completed: {len(collected_urls)} URLs")
        return collected_urls, video_data
        
    except Exception as e:
        print(f"❌ Error during scrolling: {e}")
        return collected_urls, video_data

def extract_urls_from_page(driver):
    """Extract video URLs from current page"""
    urls_data = []
    
    try:
        # Look for TikTok video links
        link_selectors = [
            'a[href*="/video/"]',
            'a[href*="@"][href*="/video/"]',
            '[data-e2e="user-post-item"] a',
            'div[data-e2e="user-post-item-desc"] a'
        ]
        
        for selector in link_selectors:
            try:
                links = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for link in links:
                    href = link.get_attribute('href')
                    if href and '/video/' in href and '@' in href:
                        # Clean URL
                        clean_url = href.split('?')[0]
                        
                        # Extract metadata
                        try:
                            # Try to find description or title
                            description = ""
                            username = ""
                            
                            # Extract username from URL
                            username_match = re.search(r'@([^/]+)', clean_url)
                            if username_match:
                                username = username_match.group(1)
                            
                            # Try to find description text nearby
                            try:
                                parent = link.find_element(By.XPATH, "./ancestor::div[contains(@data-e2e, 'user-post')]")
                                description = parent.text[:200] if parent else ""
                            except:
                                description = link.text[:200] if link.text else ""
                            
                            url_data = {
                                'url': clean_url,
                                'username': username,
                                'description': description,
                                'collection_method': 'browser_scroll_reddit',
                                'collected_at': datetime.now().isoformat()
                            }
                            
                            urls_data.append(url_data)
                            
                        except Exception:
                            # Minimal data if extraction fails
                            urls_data.append({
                                'url': clean_url,
                                'username': '',
                                'description': '',
                                'collection_method': 'browser_scroll_reddit',
                                'collected_at': datetime.now().isoformat()
                            })
                
            except Exception:
                continue
                
    except Exception as e:
        print(f"⚠️  URL extraction error: {e}")
    
    return urls_data

def save_results(urls, video_data, filename="reddit_hashtag_urls"):
    """Save collected URLs and metadata"""
    if not urls:
        print("❌ No URLs to save")
        return
    
    # Save JSON with metadata
    data = {
        'collection_summary': {
            'total_urls': len(urls),
            'hashtag': 'reddit',
            'collection_method': 'browser_selenium_firefox',
            'collection_date': datetime.now().isoformat()
        },
        'urls': list(urls),
        'video_metadata': video_data
    }
    
    json_file = f"{filename}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Save simple URL list
    txt_file = f"{filename}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for url in sorted(urls):
            f.write(url + '\n')
    
    print(f"💾 Saved {len(urls)} URLs to {json_file} and {txt_file}")
    return json_file, txt_file

def main():
    print("🚀 TikTok #reddit URL Collector")
    print("=" * 50)
    
    # Connect to Firefox
    driver = connect_to_existing_firefox()
    if not driver:
        print("❌ Cannot proceed without browser connection")
        return
    
    try:
        # Navigate to reddit hashtag
        if not navigate_to_reddit_hashtag(driver):
            print("❌ Cannot proceed without navigation")
            return
        
        print("🎯 Ready to collect URLs from #reddit hashtag")
        print("📜 Starting automatic scrolling...")
        
        # Collect URLs
        urls, video_data = scroll_and_collect_urls(driver, max_videos=200)
        
        # Save results
        if urls:
            save_results(urls, video_data)
            print(f"🎉 Success! Collected {len(urls)} URLs from #reddit")
        else:
            print("❌ No URLs collected")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        
    finally:
        try:
            driver.quit()
            print("🔚 Browser closed")
        except:
            pass

if __name__ == "__main__":
    main()