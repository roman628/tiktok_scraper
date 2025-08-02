#!/usr/bin/env python3
"""
Count comments and posts separately in master2.json
"""

import json
import os

def count_entries():
    """Count comments and posts from separate files"""
    
    # Count posts from master.json
    posts = 0
    if os.path.exists("master.json"):
        try:
            with open("master.json", 'r', encoding='utf-8') as f:
                posts_data = json.load(f)
            posts = len(posts_data) if isinstance(posts_data, list) else 0
            file_size = os.path.getsize("master.json") / (1024 * 1024)
            print(f"📹 Posts: {posts} (master.json, {file_size:.1f} MB)")
        except Exception as e:
            print(f"❌ Error reading master.json: {e}")
    else:
        print("❌ master.json not found")
    
    # Count comments from master2.json  
    comments = 0
    if os.path.exists("master2.json"):
        try:
            with open("master2.json", 'r', encoding='utf-8') as f:
                comments_data = json.load(f)
            comments = len(comments_data) if isinstance(comments_data, list) else 0
            file_size = os.path.getsize("master2.json") / (1024 * 1024)
            print(f"💬 Comments: {comments} (master2.json, {file_size:.1f} MB)")
        except Exception as e:
            print(f"❌ Error reading master2.json: {e}")
    else:
        print("❌ master2.json not found")
    
    print(f"📊 Total: {posts + comments}")

if __name__ == "__main__":
    count_entries()