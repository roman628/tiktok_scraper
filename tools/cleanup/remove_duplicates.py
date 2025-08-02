#!/usr/bin/env python3
"""
Remove duplicate URLs from master2.json while preserving the most complete data
"""

import json
import os
import sys
from datetime import datetime
from collections import OrderedDict

def get_data_completeness_score(entry):
    """Score an entry based on how complete its data is"""
    score = 0
    
    # Basic fields
    basic_fields = ['title', 'description', 'url', 'video_id', 'uploader', 'upload_date']
    for field in basic_fields:
        if field in entry and entry[field]:
            score += 1
    
    # Metadata fields
    metadata_fields = ['view_count', 'like_count', 'comment_count', 'duration', 'width', 'height']
    for field in metadata_fields:
        if field in entry and entry[field] is not None:
            score += 1
    
    # Comments
    if entry.get('comments_extracted') is True:
        score += 10  # High value for having comments
        comments = entry.get('top_comments', [])
        score += min(len(comments), 10)  # Up to 10 points for comments
    
    # Transcription
    if entry.get('transcription'):
        score += 5
    
    # Download info
    if entry.get('downloaded_at'):
        score += 2
    
    return score

def remove_duplicates(input_file, output_file=None):
    """Remove duplicate URLs from JSON file, keeping the most complete entry"""
    
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    print(f"📖 Reading {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print("💡 Please run fix_json.py first to repair the JSON file")
        return False
    
    if not isinstance(data, list):
        print(f"❌ JSON file is not an array")
        return False
    
    print(f"📊 Total entries: {len(data)}")
    
    # Group entries by URL
    url_entries = {}
    entries_without_url = []
    
    for entry in data:
        if isinstance(entry, dict) and 'url' in entry:
            url = entry['url']
            if url not in url_entries:
                url_entries[url] = []
            url_entries[url].append(entry)
        else:
            entries_without_url.append(entry)
    
    # Find duplicates
    duplicate_urls = [url for url, entries in url_entries.items() if len(entries) > 1]
    
    print(f"🔍 Unique URLs: {len(url_entries)}")
    print(f"⚠️  Duplicate URLs: {len(duplicate_urls)}")
    
    if duplicate_urls:
        print(f"\n📝 Duplicate URLs found:")
        for i, url in enumerate(duplicate_urls[:10], 1):
            count = len(url_entries[url])
            print(f"   {i}. {url} ({count} copies)")
        if len(duplicate_urls) > 10:
            print(f"   ... and {len(duplicate_urls) - 10} more")
    
    # For each URL, keep the most complete entry
    unique_entries = []
    total_removed = 0
    
    for url, entries in url_entries.items():
        if len(entries) == 1:
            unique_entries.append(entries[0])
        else:
            # Score each entry and keep the best one
            best_entry = max(entries, key=get_data_completeness_score)
            unique_entries.append(best_entry)
            total_removed += len(entries) - 1
            
            # Show what we're keeping vs removing
            if len(duplicate_urls) <= 10:  # Only show details for small sets
                print(f"\n🔄 For URL: {url}")
                print(f"   Keeping entry with score: {get_data_completeness_score(best_entry)}")
                print(f"   Removing {len(entries) - 1} duplicates")
    
    # Add back entries without URLs
    unique_entries.extend(entries_without_url)
    
    print(f"\n📊 Summary:")
    print(f"   Original entries: {len(data)}")
    print(f"   Duplicates removed: {total_removed}")
    print(f"   Final entries: {len(unique_entries)}")
    
    # Sort entries by URL for consistent output
    unique_entries.sort(key=lambda x: x.get('url', ''))
    
    # Save output
    if output_file is None:
        # Create backup first
        backup_file = f"{input_file}.before_dedup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(input_file, backup_file)
        output_file = input_file
        print(f"\n💾 Created backup: {backup_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_entries, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved deduplicated data to: {output_file}")
    
    # Verify the output
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            verify_data = json.load(f)
        print(f"✅ Verification successful: {len(verify_data)} entries in output file")
        return True
    except:
        print(f"❌ Failed to verify output file")
        return False

def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        input_file = "master2.json"
        output_file = None
    
    remove_duplicates(input_file, output_file)

if __name__ == "__main__":
    main()