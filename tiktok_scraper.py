#!/usr/bin/env python3
"""
Enhanced TikTok Video Downloader
Downloads TikTok videos with metadata extraction and organized folder structure
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed.")
    print("Install it with: pip install yt-dlp")
    sys.exit(1)


def sanitize_filename(filename):
    """
    Sanitize filename for filesystem compatibility
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove extra whitespace and dots
    filename = re.sub(r'\s+', ' ', filename).strip()
    filename = filename.strip('.')
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    return filename


def extract_metadata(info_dict):
    """
    Extract and organize metadata from yt-dlp info dictionary
    """
    metadata = {
        # Basic video info
        "title": info_dict.get('title', 'Unknown'),
        "description": info_dict.get('description', ''),
        "duration": info_dict.get('duration', 0),
        "video_id": info_dict.get('id', ''),
        "url": info_dict.get('webpage_url', ''),
        
        # Creator info
        "uploader": info_dict.get('uploader', 'Unknown'),
        "uploader_id": info_dict.get('uploader_id', ''),
        "uploader_url": info_dict.get('uploader_url', ''),
        
        # Engagement metrics
        "view_count": info_dict.get('view_count', 0),
        "like_count": info_dict.get('like_count', 0),
        "comment_count": info_dict.get('comment_count', 0),
        "repost_count": info_dict.get('repost_count', 0),
        
        # Content details
        "hashtags": info_dict.get('tags', []),
        "upload_date": info_dict.get('upload_date', ''),
        "timestamp": info_dict.get('timestamp', 0),
        
        # Technical details
        "width": info_dict.get('width', 0),
        "height": info_dict.get('height', 0),
        "fps": info_dict.get('fps', 0),
        "filesize": info_dict.get('filesize', 0),
        "format": info_dict.get('format', ''),
        
        # Captions/Subtitles (if available)
        "automatic_captions": {},
        "subtitles": {},
        
        # Placeholder for future transcription
        "custom_transcription": "",
        "transcription_timestamp": "",
        
        # Download metadata
        "downloaded_at": datetime.now().isoformat(),
        "downloaded_with": "Enhanced TikTok Downloader v1.0"
    }
    
    # Extract automatic captions if available
    if 'automatic_captions' in info_dict:
        for lang, captions in info_dict['automatic_captions'].items():
            if captions:
                metadata["automatic_captions"][lang] = captions
    
    # Extract subtitles if available
    if 'subtitles' in info_dict:
        for lang, subs in info_dict['subtitles'].items():
            if subs:
                metadata["subtitles"][lang] = subs
    
    return metadata


def download_tiktok_video(url, output_dir="downloads", quality="best", audio_only=False):
    """
    Download a TikTok video with metadata extraction and organized storage
    
    Args:
        url (str): TikTok video URL
        output_dir (str): Base directory to save the video
        quality (str): Video quality preference
        audio_only (bool): If True, download only audio as MP3
    """
    
    # Create base output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # First, extract info without downloading to get metadata
    print("Extracting video information...")
    
    temp_ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(temp_ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # Extract metadata
        metadata = extract_metadata(info)
        
        # Create folder name from video title
        folder_name = sanitize_filename(metadata['title'])
        video_folder = Path(output_dir) / folder_name
        video_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Created folder: {folder_name}")
        print(f"📊 Video Info:")
        print(f"   Title: {metadata['title']}")
        print(f"   Creator: @{metadata['uploader']}")
        print(f"   Duration: {metadata['duration']} seconds")
        print(f"   Views: {metadata['view_count']:,}")
        print(f"   Likes: {metadata['like_count']:,}")
        print(f"   Comments: {metadata['comment_count']:,}")
        
        # Configure yt-dlp options for actual download
        ydl_opts = {
            'outtmpl': str(video_folder / f"{folder_name}.%(ext)s"),
            'noplaylist': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
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
            print("🎵 Mode: Audio-only (MP3)")
        else:
            ydl_opts['format'] = quality
            print("🎬 Mode: Video download")
        
        # Download the video/audio
        print("⬇️  Starting download...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Save metadata to JSON file
        metadata_file = video_folder / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully downloaded {'audio' if audio_only else 'video'}: {metadata['title']}")
        print(f"📄 Metadata saved to: {metadata_file}")
        print(f"📂 All files saved in: {video_folder}")
        
        # Show folder contents
        print("\n📋 Downloaded files:")
        for file in video_folder.iterdir():
            if file.is_file():
                print(f"   - {file.name}")
                
        return str(video_folder)
        
    except yt_dlp.utils.DownloadError as e:
        print(f"❌ Download error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Download TikTok videos with metadata")
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
    
    result = download_tiktok_video(args.url, args.output, args.quality, args.mp3)
    if result:
        print(f"\n🎉 Download completed successfully!")
        print(f"📁 Files saved to: {result}")


if __name__ == "__main__":
    # If running directly, you can also use it interactively
    if len(sys.argv) == 1:
        print("Enhanced TikTok Video Downloader")
        print("=" * 40)
        print("Features: Video + Metadata + Organized Folders")
        print()
        
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
            
        result = download_tiktok_video(url, output_dir, quality, audio_only)
        if result:
            print(f"\n🎉 Download completed successfully!")
            print(f"📁 Files saved to: {result}")
    else:
        main()