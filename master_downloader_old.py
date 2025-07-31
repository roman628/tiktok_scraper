#!/usr/bin/env python3
"""
Master TikTok Downloader
Downloads TikTok videos (audio only), transcribes with faster-whisper, 
extracts comments, and maintains master.json database
"""

import os
import sys
import json
import signal
import time
import asyncio
import re
import shutil
from pathlib import Path
from datetime import datetime

try:
    import yt_dlp
    from faster_whisper import WhisperModel
    from TikTokApi import TikTokApi
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
except ImportError as e:
    print(f"❌ Missing required dependency: {e}")
    print("Install with: pip install yt-dlp faster-whisper TikTokApi rich")
    sys.exit(1)

# Global variables
console = Console()
shutdown_requested = False
processed_videos = []
current_video_info = {"title": "", "status": "", "steps": {}}
ms_token = ""
start_time = time.time()

def signal_handler(signum, frame):
    """Handle Ctrl+C and other termination signals gracefully"""
    global shutdown_requested
    shutdown_requested = True

def setup_signal_handlers():
    """Setup graceful shutdown handlers"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def setup_directories():
    """Setup required directories"""
    assets_dir = Path("./assets")
    downloads_dir = Path("./downloads")
    
    if not assets_dir.exists():
        assets_dir.mkdir(parents=True)
        print("📁 Created ./assets directory")
    
    if not downloads_dir.exists():
        downloads_dir.mkdir(parents=True)
        print("📁 Created ./downloads directory")
    
    return assets_dir, downloads_dir

def validate_urls_file(assets_dir):
    """Validate that urls.txt exists"""
    urls_file = assets_dir / "urls.txt"
    if not urls_file.exists():
        print("❌ Error: ./assets/urls.txt not found!")
        print("📝 Please create ./assets/urls.txt and add TikTok URLs (one per line)")
        sys.exit(1)
    return urls_file

def load_master_json(assets_dir):
    """Load or create master.json"""
    master_file = assets_dir / "master.json"
    
    if master_file.exists():
        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]
            return data, master_file
        except json.JSONDecodeError:
            print("⚠️  Invalid master.json, creating new one")
    
    return [], master_file

def load_whisper_model():
    """Load faster-whisper model with GPU support"""
    # Check if we're in Docker and skip GPU for now
    import os
    if os.path.exists('/.dockerenv'):
        print("🐳 Docker environment detected - using CPU for stability")
        try:
            model = WhisperModel("small.en", device="cpu", compute_type="int8")
            print("✅ CPU whisper model loaded successfully!")
            return model, "CPU"
        except Exception as cpu_e:
            print(f"❌ Failed to load whisper model: {cpu_e}")
            sys.exit(1)
    
    # Try GPU first for non-Docker environments
    try:
        print("🚀 Attempting to load GPU whisper model...")
        model = WhisperModel("small.en", device="cuda", compute_type="float16")
        print("✅ GPU whisper model loaded successfully!")
        return model, "GPU"
    except Exception as e:
        print(f"⚠️  GPU loading failed: {e}")
        try:
            print("🔄 Falling back to CPU whisper model...")
            model = WhisperModel("small.en", device="cpu", compute_type="int8")
            print("✅ CPU whisper model loaded successfully!")
            return model, "CPU"
        except Exception as cpu_e:
            print(f"❌ Failed to load whisper model: {cpu_e}")
            sys.exit(1)

def extract_video_id_from_url(url):
    """Extract video ID from TikTok URL"""
    patterns = [
        r'/video/(\d+)',
        r'@[\w\.-]+/video/(\d+)',
        r'vm\.tiktok\.com/([A-Za-z0-9]+)',
        r'vt\.tiktok\.com/([A-Za-z0-9]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def extract_comments(video_url, max_comments=10):
    """Extract top comments from TikTok video"""
    try:
        video_id = extract_video_id_from_url(video_url)
        if not video_id:
            return []
        
        api = TikTokApi()
        await api.create_sessions(ms_tokens=[ms_token], num_sessions=1, sleep_after=1)
        
        video = api.video(id=video_id)
        comments_data = []
        
        comment_count = 0
        async for comment in video.comments():
            if comment_count >= max_comments:
                break
                
            comment_data = {
                'username': getattr(comment.author, 'username', 'unknown'),
                'display_name': getattr(comment.author, 'nickname', 'unknown'),
                'comment_text': comment.text,
                'like_count': comment.likes_count,
                'timestamp': getattr(comment, 'create_time', int(time.time()))
            }
            comments_data.append(comment_data)
            comment_count += 1
        
        await api.close_sessions()
        return comments_data
        
    except Exception as e:
        print(f"⚠️  Comment extraction failed: {e}")
        return []

def download_audio(url, downloads_dir):
    """Download audio from TikTok video"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(downloads_dir / '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            ydl.download([url])
            
            # Find the downloaded audio file
            for file in downloads_dir.iterdir():
                if file.suffix.lower() == '.mp3':
                    return str(file), info
        
        return None, None
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None, None

def transcribe_audio(audio_file, whisper_model, device_type):
    """Transcribe audio with faster-whisper"""
    try:
        segments, info = whisper_model.transcribe(audio_file, beam_size=1, language="en")
        text_segments = []
        for segment in segments:
            if segment.text.strip():
                text_segments.append(segment.text.strip())
        return ' '.join(text_segments)
    except Exception as e:
        print(f"⚠️  Transcription failed: {e}")
        return ""

def clean_downloads(downloads_dir):
    """Clean the downloads directory"""
    try:
        for file in downloads_dir.glob("*"):
            if file.is_file():
                file.unlink()
        print("🧹 Downloads directory cleaned")
    except Exception as e:
        print(f"⚠️  Failed to clean downloads: {e}")

def url_exists_in_master(url, master_data):
    """Check if URL already exists in master.json"""
    return any(entry.get('url') == url for entry in master_data)

def save_master_json(master_data, master_file):
    """Save master.json safely"""
    try:
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Failed to save master.json: {e}")
        return False

async def process_video(url, downloads_dir, whisper_model, device_type, master_data, master_file):
    """Process a single video: download, transcribe, extract comments, save to master"""
    global current_video_count
    
    if shutdown_requested:
        return False
    
    try:
        # Check if URL already exists
        if url_exists_in_master(url, master_data):
            print(f"\n📋 URL already exists in master.json: {url}")
            return True
        
        # Download audio
        update_progress_display("Downloading...", "Downloading audio")
        audio_file, info = download_audio(url, downloads_dir)
        
        if not audio_file or not info:
            return False
        
        # Transcribe audio
        update_progress_display(info.get('title', 'Unknown'), "Transcribing audio")
        transcription = transcribe_audio(audio_file, whisper_model, device_type)
        
        # Extract comments
        update_progress_display(info.get('title', 'Unknown'), "Extracting comments")
        top_comments = await extract_comments(url)
        
        # Create metadata entry
        metadata = {
            'title': info.get('title', 'Unknown'),
            'description': info.get('description', ''),
            'url': url,
            'video_id': info.get('id', ''),
            'uploader': info.get('uploader', 'Unknown'),
            'uploader_id': info.get('uploader_id', ''),
            'duration': info.get('duration', 0),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'comment_count': info.get('comment_count', 0),
            'repost_count': info.get('repost_count', 0),
            'share_count': info.get('share_count', 0),
            'upload_date': info.get('upload_date', ''),
            'timestamp': info.get('timestamp', 0),
            'hashtags': info.get('tags', []),
            'whisper_transcription': transcription,
            'top_comments': top_comments,
            'downloaded_at': datetime.now().isoformat(),
            'transcription_device': device_type
        }
        
        # Append to master data and save
        master_data.append(metadata)
        if save_master_json(master_data, master_file):
            update_progress_display(info.get('title', 'Unknown'), "Saved to master.json")
            current_video_count += 1
            return True
        
        return False
        
    except Exception as e:
        print(f"\n❌ Error processing video: {e}")
        return False
    finally:
        # Clean downloads after each video
        clean_downloads(downloads_dir)

async def main():
    """Main processing function"""
    global total_videos, ms_token, start_time
    
    # Setup signal handlers
    setup_signal_handlers()
    
    print("🚀 Master TikTok Downloader Starting...")
    
    # Get MS_TOKEN from user
    ms_token = input("🔑 Enter your TikTok ms_token: ").strip()
    if not ms_token:
        print("❌ MS_TOKEN is required for comment extraction")
        sys.exit(1)
    
    # Setup directories
    assets_dir, downloads_dir = setup_directories()
    
    # Validate urls.txt
    urls_file = validate_urls_file(assets_dir)
    
    # Load URLs
    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
    
    if not urls:
        print("❌ No valid TikTok URLs found in ./assets/urls.txt")
        sys.exit(1)
    
    total_videos = len(urls)
    print(f"📋 Found {total_videos} URLs to process")
    
    # Load master.json
    master_data, master_file = load_master_json(assets_dir)
    
    # Load whisper model
    whisper_model, device_type = load_whisper_model()
    print(f"🎤 Using {device_type} for transcription")
    
    # Clean downloads directory
    clean_downloads(downloads_dir)
    
    # Initialize progress display
    start_time = time.time()
    print("\n" * 3)  # Make space for progress display
    
    # Process each URL
    successful = 0
    failed = 0
    
    for url in urls:
        if shutdown_requested:
            break
            
        success = await process_video(url, downloads_dir, whisper_model, device_type, master_data, master_file)
        if success:
            successful += 1
        else:
            failed += 1
    
    # Final cleanup and summary
    print("\n\n\n")  # Clear progress display
    clean_downloads(downloads_dir)
    
    if shutdown_requested:
        print("🛑 Processing interrupted by user")
    else:
        print("🎉 Processing completed!")
    
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📄 Master database: {master_file}")
    print(f"📊 Total entries in master.json: {len(master_data)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # Final cleanup
        downloads_dir = Path("./downloads")
        if downloads_dir.exists():
            clean_downloads(downloads_dir)
        print("🧹 Final cleanup completed")