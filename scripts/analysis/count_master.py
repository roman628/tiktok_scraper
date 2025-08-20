#!/usr/bin/env python3
"""
Count entries in master2.json and show statistics
Can handle corrupted JSON files and attempt repairs
"""

import json
import os
import re
from datetime import datetime
from collections import Counter

def fix_json_file(file_path):
    """Attempt to fix common JSON issues"""
    print(f"🔧 Attempting to fix JSON issues in {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count entries by counting opening braces at start of line
    entry_count = len(re.findall(r'^\s*{', content, re.MULTILINE))
    print(f"📊 Estimated entries from structure: {entry_count}")
    
    # Try to extract URLs using regex
    url_pattern = r'"url":\s*"(https://www\.tiktok\.com/[^"]+)"'
    urls = re.findall(url_pattern, content)
    
    print(f"🔗 URLs found with regex: {len(urls)}")
    
    if urls:
        unique_urls = len(set(urls))
        duplicates = len(urls) - unique_urls
        print(f"✅ Unique URLs: {unique_urls}")
        if duplicates > 0:
            print(f"⚠️  Duplicate URLs: {duplicates}")
        
        # Show first few URLs
        print(f"\n📝 First 5 URLs:")
        for i, url in enumerate(urls[:5], 1):
            print(f"   {i}. {url}")
    
    return len(urls)

def count_master_entries(file_path="master2.json"):
    """Count and analyze entries in master JSON file"""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    # File size info first
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    print(f"💾 File: {file_path}")
    print(f"💾 File size: {file_size_mb:.1f} MB")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print("❌ JSON file is not an array")
            return
        
        total_entries = len(data)
        
        # Separate video entries from other entries
        video_entries = []
        other_entries = []
        
        for entry in data:
            if isinstance(entry, dict) and 'url' in entry:
                video_entries.append(entry)
            else:
                other_entries.append(entry)
        
        print(f"📊 Total entries in file: {total_entries}")
        print(f"🎥 Video entries: {len(video_entries)}")
        print(f"📝 Other entries (comments/metadata): {len(other_entries)}")
        
        if len(video_entries) == 0:
            print("📝 No video entries found")
            return
        
        # Count by uploader (only for video entries)
        uploaders = Counter()
        urls_with_comments = 0
        successful_downloads = 0
        videos_with_transcription = 0
        urls = []
        
        for entry in video_entries:
            # Count by uploader
            uploader = entry.get('uploader', 'unknown')
            uploaders[uploader] += 1
            
            # Count comments
            if entry.get('comments_extracted') is True:
                urls_with_comments += 1
            
            # Count successful downloads
            if 'downloaded_at' in entry:
                successful_downloads += 1
            
            # Count transcriptions
            if (entry.get('whisper_transcription') or 
                entry.get('transcription') or 
                entry.get('subtitle') or 
                entry.get('custom_transcription')):
                videos_with_transcription += 1
            
            # Collect URLs
            urls.append(entry['url'])
        
        print(f"✅ Successful downloads: {successful_downloads}")
        print(f"💬 Videos with comments: {urls_with_comments}")
        print(f"🎤 Videos with transcription: {videos_with_transcription}")
        print(f"👤 Unique uploaders: {len(uploaders)}")
        
        # Show top uploaders
        if uploaders:
            print(f"\n🔝 Top 10 uploaders:")
            for uploader, count in uploaders.most_common(10):
                print(f"   {count:3d} - @{uploader}")
        
        # Check for duplicates
        unique_urls = len(set(urls))
        duplicates = len(urls) - unique_urls
        
        if duplicates > 0:
            print(f"\n⚠️  Found {duplicates} duplicate URLs")
        else:
            print(f"\n✅ No duplicate URLs found")
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error at line {getattr(e, 'lineno', '?')}: {e}")
        print("🔧 Trying alternative counting method...")
        fix_json_file(file_path)
    except Exception as e:
        print(f"❌ Error reading file: {e}")

if __name__ == "__main__":
    import sys
    
    file_path = sys.argv[1] if len(sys.argv) > 1 else "master2.json"
    count_master_entries(file_path)