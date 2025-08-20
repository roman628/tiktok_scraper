#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok URL Harvester using existing Firefox browser
Connects to your open Firefox browser and scrolls to collect URLs
"""

import time
import json
import re
import random
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import sys

class TikTokBrowserHarvester:
    """
    Harvest TikTok URLs by connecting to existing Firefox browser
    """
    
    def __init__(self, debug_port=9222):
        self.debug_port = debug_port
        self.driver = None
        self.collected_urls = set()
        self.video_data = []
        
    def connect_to_browser(self):
        """
        Connect to existing Firefox browser
        """
        print("🔗 Connecting to existing Firefox browser...")
        
        try:
            # Firefox options for connecting to existing browser
            options = Options()
            options.add_argument(f"--remote-debugging-port={self.debug_port}")
            options.add_argument("--remote-allow-hosts=localhost")
            
            # Try to connect to existing browser
            # Note: Firefox remote debugging works differently than Chrome
            # You may need to start Firefox with: firefox --remote-debugging-port=9222
            
            # For now, let's use a regular Firefox instance with your profile
            # This will open a new Firefox window but use your default profile
            options.add_argument("--profile")  # Use default profile
            
            self.driver = webdriver.Firefox(options=options)
            print("✅ Connected to Firefox successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to Firefox: {e}")
            print("💡 Make sure Firefox is installed and try again")
            return False
    
    def navigate_to_tiktok(self, search_term="reddit"):
        """
        Navigate to TikTok search page
        """
        try:
            if search_term.startswith('#'):
                # Hashtag search
                url = f"https://www.tiktok.com/tag/{search_term[1:]}"
            else:
                # General search
                url = f"https://www.tiktok.com/search?q={search_term}"
            
            print(f"🌐 Navigating to: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Handle any popups or consent forms
            self._handle_popups()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to navigate to TikTok: {e}")
            return False
    
    def _handle_popups(self):
        """
        Handle TikTok popups, consent forms, login prompts
        """
        try:
            # Look for common popup elements and close them
            popup_selectors = [
                '[data-e2e="close-button"]',
                '[data-e2e="modal-close-inner-button"]',
                'button[aria-label="Close"]',
                '.TikTokLogoConsentCard__content button',
                '[data-testid="close-button"]'
            ]
            
            for selector in popup_selectors:
                try:
                    popup = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if popup.is_displayed():
                        popup.click()
                        print("✅ Closed popup")
                        time.sleep(1)
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️  Popup handling: {e}")
    
    def scroll_and_collect(self, max_videos=200, scroll_duration=30):
        """
        Scroll through TikTok feed and collect video URLs
        """
        print(f"📜 Scrolling to collect up to {max_videos} video URLs...")
        
        scroll_count = 0
        last_height = 0
        start_time = time.time()
        
        try:
            while (len(self.collected_urls) < max_videos and 
                   time.time() - start_time < scroll_duration * 60):  # Convert to seconds
                
                # Extract URLs from current view
                self._extract_urls_from_page()
                
                # Scroll down
                self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                scroll_count += 1
                
                # Random delay between scrolls (human-like behavior)
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
                
                # Check if we've reached the bottom or no new content
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    print("⚠️  Reached bottom of feed or no new content")
                    break
                last_height = new_height
                
                # Progress update
                if scroll_count % 10 == 0:
                    elapsed = (time.time() - start_time) / 60
                    print(f"   📊 Scrolled {scroll_count} times, collected {len(self.collected_urls)} URLs ({elapsed:.1f}m)")
                
                # Occasionally pause longer to seem more human
                if scroll_count % 25 == 0:
                    print("   ⏸️  Taking a human-like break...")
                    time.sleep(random.uniform(5, 10))
            
            print(f"✅ Scrolling completed: {len(self.collected_urls)} URLs collected")
            
        except Exception as e:
            print(f"❌ Error during scrolling: {e}")
    
    def _extract_urls_from_page(self):
        """
        Extract video URLs from current page view
        """
        try:
            # TikTok video link patterns
            link_selectors = [
                'a[href*="/video/"]',  # General video links
                '[data-e2e="user-post-item"] a',  # User post items
                '.tiktok-item a',  # TikTok items
                'a[href*="@"]'  # Profile/video links
            ]
            
            for selector in link_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for link in links:
                        href = link.get_attribute('href')
                        if href and '/video/' in href and '@' in href:
                            # Clean URL
                            clean_url = href.split('?')[0]  # Remove query parameters
                            
                            if clean_url not in self.collected_urls:
                                self.collected_urls.add(clean_url)
                                
                                # Try to extract additional metadata
                                video_data = self._extract_video_metadata(link)
                                video_data['url'] = clean_url
                                video_data['collected_at'] = datetime.now().isoformat()
                                self.video_data.append(video_data)
                
                except Exception as e:
                    continue  # Try next selector
                    
        except Exception as e:
            print(f"⚠️  URL extraction error: {e}")
    
    def _extract_video_metadata(self, link_element):
        """
        Extract metadata from video element
        """
        metadata = {
            'title': '',
            'username': '',
            'description': '',
            'collection_method': 'browser_scroll'
        }
        
        try:
            # Try to find parent container with more info
            parent = link_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'item') or contains(@data-e2e, 'post')]")
            
            # Extract text content
            text_content = parent.text if parent else link_element.text
            metadata['description'] = text_content[:200] if text_content else ''
            
            # Extract username from href
            href = link_element.get_attribute('href')
            if href and '@' in href:
                username_match = re.search(r'@([^/]+)', href)
                if username_match:
                    metadata['username'] = username_match.group(1)
            
        except Exception:
            pass  # Metadata extraction is optional
        
        return metadata
    
    def save_results(self, filename="browser_harvested_urls"):
        """
        Save collected URLs and metadata
        """
        if not self.collected_urls:
            print("❌ No URLs to save")
            return
        
        # Save JSON with metadata
        data = {
            'collection_summary': {
                'total_urls': len(self.collected_urls),
                'collection_method': 'browser_selenium',
                'collection_date': datetime.now().isoformat(),
                'browser_used': 'firefox'
            },
            'urls': list(self.collected_urls),
            'video_metadata': self.video_data
        }
        
        json_file = f"{filename}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Save simple URL list
        txt_file = f"{filename}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            for url in sorted(self.collected_urls):
                f.write(url + '\n')
        
        print(f"💾 Saved {len(self.collected_urls)} URLs to {json_file} and {txt_file}")
        return json_file, txt_file
    
    def close(self):
        """
        Close the browser connection
        """
        if self.driver:
            try:
                self.driver.quit()
                print("🔚 Browser connection closed")
            except Exception as e:
                print(f"⚠️  Error closing browser: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Harvest TikTok URLs using browser automation")
    parser.add_argument("-s", "--search", default="reddit",
                       help="Search term or hashtag (default: reddit)")
    parser.add_argument("-m", "--max-videos", type=int, default=200,
                       help="Maximum videos to collect (default: 200)")
    parser.add_argument("-d", "--duration", type=int, default=30,
                       help="Max scroll duration in minutes (default: 30)")
    parser.add_argument("-o", "--output", default="browser_harvested_urls",
                       help="Output filename prefix (default: browser_harvested_urls)")
    
    args = parser.parse_args()
    
    harvester = TikTokBrowserHarvester()
    
    try:
        # Connect to browser
        if not harvester.connect_to_browser():
            print("❌ Cannot proceed without browser connection")
            return
        
        # Navigate to TikTok
        if not harvester.navigate_to_tiktok(args.search):
            print("❌ Cannot proceed without TikTok navigation")
            return
        
        print(f"🎯 Starting collection for: {args.search}")
        print(f"📊 Target: {args.max_videos} videos, max {args.duration} minutes")
        print("👆 You can manually scroll or interact with the page too!")
        
        # Start collecting
        harvester.scroll_and_collect(args.max_videos, args.duration)
        
        # Save results
        if harvester.collected_urls:
            harvester.save_results(args.output)
            print(f"🎉 Successfully collected {len(harvester.collected_urls)} URLs!")
        else:
            print("❌ No URLs collected. Try adjusting search terms or duration.")
        
    except KeyboardInterrupt:
        print("\n⏹️  Collection stopped by user")
        if harvester.collected_urls:
            harvester.save_results(args.output)
            print(f"💾 Saved {len(harvester.collected_urls)} URLs before stopping")
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    finally:
        harvester.close()

if __name__ == "__main__":
    main()