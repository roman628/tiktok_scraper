#!/Users/ethan/tiktok_scraper/venv/bin/python
"""
Stealth TikTok URL Collector
Opens a stealth Firefox browser and collects TikTok video URLs as you scroll
"""

import os
import sys
import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re


class TikTokURLCollector:
    def __init__(self, headless=False, debug=False):
        self.headless = headless
        self.debug = debug
        self.collected_urls = set()
        self.driver = None
        self.output_file = "urls.txt"  # Changed to urls.txt
        self.json_output = "collected_metadata.json"
        self.profile_dir = Path.home() / ".tiktok_scraper_profile"  # Profile directory for cookies
        
    def setup_stealth_firefox(self):
        """Setup stealth Firefox with anti-detection measures and persistent profile"""
        print("🚀 Setting up stealth Firefox...")
        
        # Create profile directory if it doesn't exist
        self.profile_dir.mkdir(exist_ok=True)
        print(f"📁 Using profile directory: {self.profile_dir}")
        
        options = Options()
        
        # Set the profile path to use persistent storage
        options.add_argument(f"-profile")
        options.add_argument(str(self.profile_dir))
        
        # Headless mode if requested
        if self.headless:
            options.add_argument("--headless")
        
        # Stealth settings
        options.set_preference("general.useragent.override", 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0")
        
        # Disable automation indicators
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("useAutomationExtension", False)
        
        # Privacy settings
        options.set_preference("privacy.trackingprotection.enabled", True)
        options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
        options.set_preference("media.peerconnection.enabled", False)
        
        # Performance settings
        options.set_preference("javascript.enabled", True)
        options.set_preference("permissions.default.image", 1)  # Allow images for better TikTok experience
        
        # TikTok-specific settings
        options.set_preference("network.http.referer.spoofSource", True)
        
        # Cookie settings
        options.set_preference("network.cookie.cookieBehavior", 0)  # Accept all cookies
        options.set_preference("network.cookie.lifetimePolicy", 0)  # Keep cookies until they expire
        
        try:
            self.driver = webdriver.Firefox(options=options)
            
            # Additional stealth measures
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Stealth Firefox initialized with persistent profile")
            print("🍪 Cookies and login state will be preserved")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup Firefox: {e}")
            print("💡 Make sure geckodriver is installed and in PATH")
            return False
    
    def extract_video_metadata(self, element):
        """Extract basic metadata from video element without navigation"""
        metadata = {
            "url": "",
            "timestamp": time.time(),
            "creator": "",
            "description": "",
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            # Get URL from element
            url = element.get_attribute('href')
            if url:
                metadata["url"] = url
                
            # Try to get creator and description from nearby elements
            parent = element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'DivItemContainerV2') or contains(@class, 'video-feed-item')]")
            
            # Get creator
            try:
                creator_elem = parent.find_element(By.CSS_SELECTOR, "[data-e2e='video-author-uniqueid'], .author-uniqueId, [class*='AuthorTitle']")
                if creator_elem:
                    metadata["creator"] = creator_elem.text.strip()
            except:
                pass
                
            # Get description
            try:
                desc_elem = parent.find_element(By.CSS_SELECTOR, "[data-e2e='video-desc'], [class*='VideoCaption'], [class*='video-meta-title']")
                if desc_elem:
                    metadata["description"] = desc_elem.text.strip()
            except:
                pass
                
        except Exception as e:
            if self.debug:
                print(f"⚠️  Could not extract metadata: {e}")
                
        return metadata
    
    def find_tiktok_urls(self):
        """Find all TikTok video URLs on current page"""
        try:
            found_urls = set()
            
            # Method 1: Find all links and filter TikTok video URLs
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if href and self.is_valid_tiktok_url(href):
                        found_urls.add(href)
                except:
                    pass
            
            # Method 2: Try specific selectors for TikTok's structure
            selectors = [
                "[data-e2e='user-post-item-desc'] a",
                "[data-e2e='browse-video-link']",
                "div[class*='DivWrapper'] a[href*='/video/']",
                "div[class*='DivItemContainer'] a",
                "a[class*='StyledLink'][href*='/@']"
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        href = element.get_attribute('href')
                        if href and self.is_valid_tiktok_url(href):
                            found_urls.add(href)
                except Exception as e:
                    if self.debug:
                        print(f"⚠️  Selector {selector}: {e}")
            
            # Method 3: Extract from data attributes
            try:
                # Some TikTok elements store URLs in data attributes
                elements_with_data = self.driver.find_elements(By.CSS_SELECTOR, "[data-video-id], [data-item-id]")
                for elem in elements_with_data:
                    try:
                        # Try to find associated links
                        parent = elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'DivItemContainer') or contains(@class, 'video-feed')]")
                        links = parent.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            href = link.get_attribute('href')
                            if href and self.is_valid_tiktok_url(href):
                                found_urls.add(href)
                    except:
                        pass
            except:
                pass
            
            if self.debug and found_urls:
                print(f"🔍 Found {len(found_urls)} URLs in current view")
            
            return found_urls
            
        except Exception as e:
            if self.debug:
                print(f"❌ Error finding URLs: {e}")
            return set()
    
    def is_valid_tiktok_url(self, url):
        """Check if URL is a valid TikTok video URL"""
        if not url:
            return False
            
        patterns = [
            r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/\d+',
            r'https?://(?:vm|vt)\.tiktok\.com/[A-Za-z0-9]+',
            r'https?://(?:www\.)?tiktok\.com/t/[A-Za-z0-9]+',
        ]
        
        return any(re.match(pattern, url) for pattern in patterns)
    
    def save_urls(self, new_urls):
        """Save new URLs to file"""
        if not new_urls:
            return
            
        with open(self.output_file, 'a', encoding='utf-8') as f:
            for url in new_urls:
                f.write(f"{url}\n")
        
        print(f"💾 Saved {len(new_urls)} new URLs to {self.output_file}")
    
    def save_metadata(self, metadata_list):
        """Save metadata to JSON file"""
        existing_data = []
        
        # Load existing data if file exists
        if os.path.exists(self.json_output):
            try:
                with open(self.json_output, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
        
        # Append new metadata
        existing_data.extend(metadata_list)
        
        # Save updated data
        with open(self.json_output, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Saved metadata for {len(metadata_list)} videos to {self.json_output}")
    
    def start_collection(self, start_url="https://www.tiktok.com/foryou"):
        """Start the URL collection process"""
        if not self.setup_stealth_firefox():
            return False
        
        # Load existing URLs to avoid duplicates
        if os.path.exists(self.output_file):
            with open(self.output_file, 'r', encoding='utf-8') as f:
                existing_urls = set(line.strip() for line in f if line.strip())
                self.collected_urls.update(existing_urls)
                print(f"📚 Loaded {len(existing_urls)} existing URLs from {self.output_file}")
        
        print(f"🌐 Opening TikTok: {start_url}")
        self.driver.get(start_url)
        
        print("\n" + "="*60)
        print("🎯 TikTok URL Collector Started")
        print("="*60)
        print("Instructions:")
        print("• Scroll through TikTok manually")
        print("• URLs will be automatically collected as you scroll")
        print("• URLs are appended to: urls.txt")
        print("• Press Ctrl+C to stop")
        print("• The browser will stay open for manual navigation")
        print("\n🍪 Profile saved at: ~/.tiktok_scraper_profile")
        print("   (Login state will persist between sessions)")
        print("="*60)
        
        try:
            last_count = len(self.collected_urls)
            check_interval = 1  # Check every second for new content
            
            while True:
                # Find new URLs on current page
                current_urls = self.find_tiktok_urls()
                
                # Also search in page source for hidden URLs
                try:
                    page_source = self.driver.page_source
                    # Find URLs in page source using regex
                    source_urls = re.findall(r'https://www\.tiktok\.com/@[^/]+/video/\d+', page_source)
                    for url in source_urls:
                        if self.is_valid_tiktok_url(url):
                            current_urls.add(url)
                except:
                    pass
                
                new_urls = current_urls - self.collected_urls
                
                if new_urls:
                    self.collected_urls.update(new_urls)
                    self.save_urls(new_urls)
                    
                    # Don't extract metadata to avoid navigation
                    # Just show what we found
                    for url in sorted(new_urls):
                        print(f"   ✅ Found: {url}")
                
                # Status update only when count changes
                current_count = len(self.collected_urls)
                if current_count != last_count:
                    new_count = current_count - last_count
                    print(f"📊 New URLs: +{new_count} | Total: {current_count}")
                    last_count = current_count
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Collection stopped by user")
            print(f"📊 Total URLs collected: {len(self.collected_urls)}")
            print(f"💾 URLs saved to: {self.output_file}")
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            
        finally:
            print("\n🔄 Keeping browser open for manual use...")
            print("Close the browser window when done.")
            
            # Keep browser open
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            
            if self.driver:
                self.driver.quit()
                print("👋 Browser closed")
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect TikTok video URLs while browsing")
    parser.add_argument("--headless", action="store_true", 
                       help="Run browser in headless mode")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug output")
    parser.add_argument("--start-url", default="https://www.tiktok.com/foryou",
                       help="Starting URL (default: TikTok For You page)")
    parser.add_argument("--output", default="urls.txt",
                       help="Output file for URLs (default: urls.txt)")
    parser.add_argument("--json-output", default="collected_metadata.json", 
                       help="Output file for metadata (default: collected_metadata.json)")
    
    args = parser.parse_args()
    
    # Enable debug by default to help diagnose issues
    if not args.debug:
        print("💡 Tip: Use --debug flag to see detailed URL detection info")
    
    # Check if selenium and geckodriver are available
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
    except ImportError:
        print("❌ Selenium not installed. Install with: pip install selenium")
        sys.exit(1)
    
    collector = TikTokURLCollector(headless=args.headless, debug=args.debug)
    collector.output_file = args.output
    collector.json_output = args.json_output
    
    try:
        collector.start_collection(args.start_url)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        collector.cleanup()


if __name__ == "__main__":
    main()