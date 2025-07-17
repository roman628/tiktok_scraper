#!/usr/bin/env python3
"""
TikTok Video Downloader
A simple script to download TikTok videos using yt-dlp
"""

import os
import sys
import argparse
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed.")
    print("Install it with: pip install yt-dlp")
    sys.exit(1)


def download_tiktok_video(url, output_dir="downloads", quality="best", audio_only=False):
    """
    Download a TikTok video from the given URL
    
    Args:
        url (str): TikTok video URL
        output_dir (str): Directory to save the video
        quality (str): Video quality preference
        audio_only (bool): If True, download only audio as MP3
    """
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Configure yt-dlp options
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        # Add some user agent to avoid blocks
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    }
    
    # Configure format and post-processing based on audio_only flag
    if audio_only:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        print("Mode: Audio-only (MP3)")
    else:
        ydl_opts['format'] = quality
        print("Mode: Video download")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading video from: {url}")
            
            # Get video info first
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown')
            
            print(f"Title: {title}")
            print(f"Uploader: {uploader}")
            print(f"Duration: {duration} seconds")
            print("Starting download...")
            
            # Download the video/audio
            ydl.download([url])
            if audio_only:
                print(f"✅ Successfully downloaded audio: {title}.mp3")
            else:
                print(f"✅ Successfully downloaded: {title}")
            
    except yt_dlp.utils.DownloadError as e:
        print(f"❌ Download error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Download TikTok videos")
    parser.add_argument("url", help="TikTok video URL")
    parser.add_argument("-o", "--output", default="downloads", 
                       help="Output directory (default: downloads)")
    parser.add_argument("-q", "--quality", default="best",
                       choices=["best", "worst", "720p", "480p", "360p"],
                       help="Video quality (default: best)")
    parser.add_argument("--mp3", action="store_true",
                       help="Download audio only as MP3 instead of video")
    
    args = parser.parse_args()
    
    # Validate URL
    if "tiktok.com" not in args.url:
        print("❌ Please provide a valid TikTok URL")
        sys.exit(1)
    
    download_tiktok_video(args.url, args.output, args.quality, args.mp3)


if __name__ == "__main__":
    # If running directly, you can also use it interactively
    if len(sys.argv) == 1:
        print("TikTok Video Downloader")
        print("=" * 30)
        
        url = input("Enter TikTok URL: ").strip()
        if not url:
            print("No URL provided. Exiting.")
            sys.exit(1)
            
        if "tiktok.com" not in url:
            print("❌ Please provide a valid TikTok URL")
            sys.exit(1)
        
        output_dir = input("Output directory (press Enter for 'downloads'): ").strip()
        if not output_dir:
            output_dir = "downloads"
            
        quality = input("Quality (best/worst/720p/480p/360p, press Enter for 'best'): ").strip()
        if not quality:
            quality = "best"
        
        audio_only = input("Download audio only as MP3? (y/n, press Enter for 'n'): ").strip().lower()
        audio_only = audio_only in ['y', 'yes', '1', 'true']
            
        download_tiktok_video(url, output_dir, quality, audio_only)
    else:
        main()