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
    from rich.status import Status
except ImportError as e:
    print(f"❌ Missing required dependency: {e}")
    print("Install with: pip install yt-dlp faster-whisper TikTokApi rich")
    sys.exit(1)

# Global variables
console = Console()
shutdown_requested = False
processed_videos = []
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

def create_summary_table():
    """Create a table showing processed videos"""
    table = Table(title="Processed Videos", show_header=True, header_style="bold magenta")
    table.add_column("Video", style="cyan", width=40)
    table.add_column("Time", style="green", width=8)
    table.add_column("Status", style="yellow", width=60)
    
    for video in processed_videos[-10:]:  # Show last 10
        table.add_row(
            video["title"][:35] + "..." if len(video["title"]) > 35 else video["title"],
            f"{video['duration']:.1f}s",
            video["status"]
        )
    
    return table

def detect_gpu_support():
    """Detect if GPU is available and working"""
    try:
        # Try to import torch to check CUDA
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return True, gpu_name
    except ImportError:
        pass
    
    # Check if we're in Docker
    if os.path.exists('/.dockerenv'):
        return False, "Docker environment - using CPU for stability"
    
    # Try basic CUDA check
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, "NVIDIA GPU detected"
    except:
        pass
    
    return False, "No GPU detected"

def load_whisper_model():
    """Load faster-whisper model with smart GPU detection"""
    gpu_available, gpu_info = detect_gpu_support()
    
    with console.status(f"[bold green]Loading Whisper model... ({gpu_info})"):
        if gpu_available and not os.path.exists('/.dockerenv'):
            try:
                model = WhisperModel("small.en", device="cuda", compute_type="float16")
                console.print(f"✅ [bold green]GPU Whisper loaded[/bold green] - {gpu_info}")
                return model, "GPU"
            except Exception as e:
                console.print(f"⚠️ [yellow]GPU failed: {str(e)[:50]}...[/yellow]")
        
        try:
            model = WhisperModel("small.en", device="cpu", compute_type="int8")
            console.print(f"✅ [bold blue]CPU Whisper loaded[/bold blue] - {gpu_info}")
            return model, "CPU"
        except Exception as e:
            console.print(f"❌ [bold red]Failed to load Whisper: {e}[/bold red]")
            sys.exit(1)

def setup_directories():
    """Setup required directories"""
    assets_dir = Path("./assets")
    downloads_dir = Path("./downloads")
    
    assets_dir.mkdir(exist_ok=True)
    downloads_dir.mkdir(exist_ok=True)
    
    return assets_dir, downloads_dir

def validate_urls_file(assets_dir):
    """Validate that urls.txt exists"""
    urls_file = assets_dir / "urls.txt"
    if not urls_file.exists():
        console.print("❌ [bold red]Error: ./assets/urls.txt not found![/bold red]")
        console.print("📝 Please create ./assets/urls.txt and add TikTok URLs (one per line)")
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
            console.print("⚠️ [yellow]Invalid master.json, creating new one[/yellow]")
    
    return [], master_file

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

async def validate_ms_token(token):
    """Validate MS token by testing TikTok API"""
    try:
        api = TikTokApi()
        await api.create_sessions(ms_tokens=[token], num_sessions=1, sleep_after=1)
        await api.close_sessions()
        return True
    except Exception:
        return False

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
        
    except Exception:
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
        
    except Exception:
        return None, None

def transcribe_audio(audio_file, whisper_model):
    """Transcribe audio with faster-whisper"""
    try:
        segments, info = whisper_model.transcribe(audio_file, beam_size=1, language="en")
        text_segments = []
        for segment in segments:
            if segment.text.strip():
                text_segments.append(segment.text.strip())
        return ' '.join(text_segments)
    except Exception:
        return ""

def clean_downloads(downloads_dir):
    """Clean the downloads directory quietly"""
    try:
        for file in downloads_dir.glob("*"):
            if file.is_file():
                file.unlink()
    except Exception:
        pass

def url_exists_in_master(url, master_data):
    """Check if URL already exists in master.json"""
    return any(entry.get('url') == url for entry in master_data)

def save_master_json(master_data, master_file):
    """Save master.json safely"""
    try:
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

async def process_video(url, downloads_dir, whisper_model, device_type, master_data, master_file, video_num, total_videos):
    """Process a single video with detailed progress tracking"""
    start_time = time.time()
    
    steps = {
        "🔍 Checking URL": "pending",
        "⬇️ Downloading": "pending", 
        "🎤 Transcribing": "pending",
        "💬 Comments": "pending",
        "💾 Saving": "pending"
    }
    
    title = f"Video {video_num}/{total_videos}"
    status_parts = []
    
    try:
        # Step 1: Check if URL exists
        steps["🔍 Checking URL"] = "running"
        if url_exists_in_master(url, master_data):
            steps["🔍 Checking URL"] = "skipped"
            status_parts.append("[yellow]Already exists[/yellow]")
            duration = time.time() - start_time
            processed_videos.append({
                "title": "Already processed",
                "duration": duration,
                "status": " | ".join(status_parts)
            })
            return True
        
        steps["🔍 Checking URL"] = "done"
        
        # Step 2: Download audio
        steps["⬇️ Downloading"] = "running"
        audio_file, info = download_audio(url, downloads_dir)
        
        if not audio_file or not info:
            steps["⬇️ Downloading"] = "failed"
            status_parts.append("[red]Download failed[/red]")
            duration = time.time() - start_time
            processed_videos.append({
                "title": "Download failed",
                "duration": duration,
                "status": " | ".join(status_parts)
            })
            return False
        
        steps["⬇️ Downloading"] = "done"
        title = info.get('title', 'Unknown')[:30]
        
        # Step 3: Transcribe audio
        steps["🎤 Transcribing"] = "running"
        transcription = transcribe_audio(audio_file, whisper_model)
        if transcription:
            steps["🎤 Transcribing"] = "done"
            status_parts.append(f"[green]Transcribed ({len(transcription)} chars)[/green]")
        else:
            steps["🎤 Transcribing"] = "failed"
            status_parts.append("[yellow]No transcription[/yellow]")
        
        # Step 4: Extract comments
        steps["💬 Comments"] = "running"
        top_comments = await extract_comments(url)
        if top_comments:
            steps["💬 Comments"] = "done"
            status_parts.append(f"[green]{len(top_comments)} comments[/green]")
        else:
            steps["💬 Comments"] = "failed"
            status_parts.append("[yellow]No comments[/yellow]")
        
        # Step 5: Save to master.json
        steps["💾 Saving"] = "running"
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
        
        master_data.append(metadata)
        if save_master_json(master_data, master_file):
            steps["💾 Saving"] = "done"
            status_parts.append("[green]Saved[/green]")
        else:
            steps["💾 Saving"] = "failed"
            status_parts.append("[red]Save failed[/red]")
        
        duration = time.time() - start_time
        processed_videos.append({
            "title": title,
            "duration": duration,
            "status": " | ".join(status_parts)
        })
        
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        processed_videos.append({
            "title": title,
            "duration": duration,
            "status": f"[red]Error: {str(e)[:30]}...[/red]"
        })
        return False
    finally:
        clean_downloads(downloads_dir)

async def main():
    """Main processing function with rich UI"""
    global ms_token, start_time
    
    # Setup signal handlers
    setup_signal_handlers()
    
    console.print(Panel.fit("🚀 [bold blue]Master TikTok Downloader[/bold blue]", 
                           subtitle="Audio + Transcription + Comments"))
    
    # Get MS_TOKEN from user
    ms_token = console.input("🔑 [bold yellow]Enter your TikTok ms_token:[/bold yellow] ")
    if not ms_token:
        console.print("❌ [bold red]MS_TOKEN is required for comment extraction[/bold red]")
        sys.exit(1)
    
    # Validate token
    with console.status("[bold green]Validating MS Token..."):
        token_valid = await validate_ms_token(ms_token)
        if token_valid:
            console.print("✅ [bold green]MS Token validated successfully[/bold green]")
        else:
            console.print("⚠️ [yellow]MS Token validation failed - comments may not work[/yellow]")
    
    # Setup directories
    assets_dir, downloads_dir = setup_directories()
    
    # Validate urls.txt
    urls_file = validate_urls_file(assets_dir)
    
    # Load URLs
    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
    
    if not urls:
        console.print("❌ [bold red]No valid TikTok URLs found in ./assets/urls.txt[/bold red]")
        sys.exit(1)
    
    total_videos = len(urls)
    console.print(f"📋 Found [bold cyan]{total_videos}[/bold cyan] URLs to process")
    
    # Load master.json
    master_data, master_file = load_master_json(assets_dir)
    
    # Load whisper model
    whisper_model, device_type = load_whisper_model()
    
    # Process each URL
    start_time = time.time()
    successful = 0
    failed = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        
        overall_task = progress.add_task("Processing videos...", total=total_videos)
        
        for i, url in enumerate(urls, 1):
            if shutdown_requested:
                break
            
            progress.update(overall_task, description=f"Processing video {i}/{total_videos}")
            
            success = await process_video(url, downloads_dir, whisper_model, device_type, 
                                        master_data, master_file, i, total_videos)
            
            if success:
                successful += 1
            else:
                failed += 1
            
            progress.update(overall_task, advance=1)
            
            # Show summary table periodically
            if i % 5 == 0 or i == total_videos:
                console.print(create_summary_table())
    
    # Final summary
    elapsed = time.time() - start_time
    rate = total_videos / elapsed * 60 if elapsed > 0 else 0
    
    if shutdown_requested:
        console.print("\n🛑 [yellow]Processing interrupted by user[/yellow]")
    else:
        console.print("\n🎉 [bold green]Processing completed![/bold green]")
    
    summary_table = Table(title="Final Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("✅ Successful", str(successful))
    summary_table.add_row("❌ Failed", str(failed))
    summary_table.add_row("⏱️ Total Time", f"{elapsed:.1f}s")
    summary_table.add_row("⚡ Rate", f"{rate:.1f} videos/min")
    summary_table.add_row("📄 Master DB", str(master_file))
    summary_table.add_row("📊 Total Entries", str(len(master_data)))
    summary_table.add_row("🎤 Transcription", device_type)
    
    console.print(summary_table)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n❌ [bold red]Unexpected error: {e}[/bold red]")
    finally:
        # Final cleanup
        downloads_dir = Path("./downloads")
        if downloads_dir.exists():
            clean_downloads(downloads_dir)