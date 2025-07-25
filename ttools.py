#!/usr/bin/env python3

import os
import subprocess
import sys
import importlib.util

def get_script_info(script_path):
    """Returns description for known scripts."""
    script_descriptions = {
        # Analysis scripts
        "comment_extractor.py": "Extract comments from TikTok videos and update master.json",
        "count.py": "Count posts and comments from master JSON files",
        "count_master.py": "Analyze entries in master2.json with error recovery",
        
        # Cleanup scripts
        "sanitize_json.py": "Extract videos with transcriptions > 40 chars",
        "fix_json.py": "Fix corrupted JSON files by extracting valid objects",
        "remove_duplicates.py": "Remove duplicate URLs keeping most complete data",
        "clean_no_transcription.py": "Remove entries without transcriptions",
        "deduplicate.py": "Remove duplicate URLs from text files",
        
        # Collection scripts
        "browser_harvester.py": "Harvest URLs from existing Firefox browser",
        "tiktok_url_collector.py": "Collect URLs with stealth browser mode",
        "url_harvester.py": "Harvest URLs from trending/hashtags/users/searches",
        "update_comments_v2.py": "Update master2.json with video comments",
        "master_download_and_comment.py": "Download videos and extract comments",
        "tiktok_scraper.py": "Multi-process downloader with resume capability",
        "tiktok_downloader.py": "Simple video downloader using yt-dlp",
        
        # Utils scripts
        "connect_existing_firefox.py": "Connect to Firefox for remote debugging",
        "memory_efficient_append.py": "Stream append JSON without loading all data",
        "process_single_video.py": "Extract comments from a single video"
    }
    
    script_name = os.path.basename(script_path)
    return script_descriptions.get(script_name, "No description available.")

def find_scripts(directory="scripts"):
    """Finds all Python scripts in the given directory and its subdirectories, ignoring __init__.py."""
    scripts = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                scripts.append(os.path.join(root, file))
    return scripts

def main():
    """Main function to display and run scripts."""
    scripts = find_scripts()
    if not scripts:
        print("No scripts found.")
        return

    print("Available scripts:")
    for i, script in enumerate(scripts):
        script_name = os.path.basename(script).replace('.py', '')
        description = get_script_info(script)
        print(f"{i + 1}. {script_name}: {description}")

    try:
        choice = int(input("Enter the number of the script to run: "))
        if 1 <= choice <= len(scripts):
            script_path = scripts[choice - 1]
            print(f"Running {script_path}...")
            subprocess.run([sys.executable, script_path])
        else:
            print("Invalid choice.")
    except ValueError:
        print("Invalid input. Please enter a number.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")

if __name__ == "__main__":
    main()
