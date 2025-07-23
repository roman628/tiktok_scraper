#!/usr/bin/env python3
"""
Robust Multi-Process TikTok Video Downloader
Features:
- Resume capability (marks processed URLs with '-')
- Graceful Ctrl+C handling
- Real-time JSON appending
- Multi-process downloading (--multi flag)
- Comprehensive timing
- Memory optimization
"""

import os
import sys
import json
import argparse
import re
import platform
import gc
import time
import psutil
import signal
import threading
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
import shutil
import site
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed.")
    print("Install it with: pip install yt-dlp")
    sys.exit(1)

# Try to import faster-whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Global variables for graceful shutdown
shutdown_requested = False
lock = threading.Lock()

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    with lock:
        if not shutdown_requested:
            shutdown_requested = True
            print(f"\n🛑 Graceful shutdown requested (signal {signum})")
            print("⏳ Finishing current downloads and saving progress...")
            print("🚫 Cleaning disabled to preserve progress")

# Register signal handlers - DISABLED to prevent Ctrl+C interference in robust_master_downloader
# signal.signal(signal.SIGINT, signal_handler)
# if platform.system() != 'Windows':
#     signal.signal(signal.SIGTERM, signal_handler)


def get_platform_info():
    """Get platform-specific information"""
    system = platform.system().lower()
    return {
        'system': system,
        'is_windows': system == 'windows',
        'is_mac': system == 'darwin',
        'is_linux': system == 'linux',
        'path_sep': ';' if system == 'windows' else ':',
        'exe_ext': '.exe' if system == 'windows' else ''
    }


def find_venv_path():
    """Dynamically find the virtual environment path"""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return sys.prefix
    return None


def find_nvidia_libraries():
    """Find NVIDIA CUDA libraries across different platforms"""
    platform_info = get_platform_info()
    possible_locations = []
    
    venv_path = find_venv_path()
    if venv_path:
        if platform_info['is_windows']:
            venv_site_packages = os.path.join(venv_path, "Lib", "site-packages")
        else:
            for path in site.getsitepackages():
                if venv_path in path:
                    venv_site_packages = path
                    break
            else:
                python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
                venv_site_packages = os.path.join(venv_path, "lib", python_version, "site-packages")
        
        nvidia_venv_path = os.path.join(venv_site_packages, "nvidia")
        if os.path.exists(nvidia_venv_path):
            possible_locations.append(("VENV", nvidia_venv_path))
    
    for site_path in site.getsitepackages():
        nvidia_path = os.path.join(site_path, "nvidia")
        if os.path.exists(nvidia_path):
            possible_locations.append(("SYSTEM", nvidia_path))
    
    return possible_locations


def setup_cuda_paths():
    """Set up CUDA paths for faster-whisper"""
    platform_info = get_platform_info()
    nvidia_locations = find_nvidia_libraries()
    
    cuda_paths = []
    
    for location_type, base_path in nvidia_locations:
        if "nvidia" in base_path:
            potential_subdirs = ["cublas", "cudnn", "cufft", "curand", "cusparse"]
            for subdir in potential_subdirs:
                if platform_info['is_windows']:
                    lib_path = os.path.join(base_path, subdir, "bin")
                else:
                    lib_path = os.path.join(base_path, subdir, "lib")
                
                if os.path.exists(lib_path):
                    cuda_paths.append(lib_path)
    
    if cuda_paths:
        for cuda_path in cuda_paths:
            if cuda_path not in os.environ.get('PATH', ''):
                os.environ['PATH'] = cuda_path + platform_info['path_sep'] + os.environ.get('PATH', '')
        
        if not platform_info['is_windows']:
            current_ld = os.environ.get('LD_LIBRARY_PATH', '')
            for cuda_path in cuda_paths:
                if cuda_path not in current_ld:
                    if current_ld:
                        os.environ['LD_LIBRARY_PATH'] = cuda_path + ':' + current_ld
                    else:
                        os.environ['LD_LIBRARY_PATH'] = cuda_path
    
    return cuda_paths


def load_whisper_model(force_cpu=False):
    """Load faster-whisper model for transcription"""
    if not WHISPER_AVAILABLE:
        print("❌ faster-whisper not available. Install with: pip install faster-whisper")
        return None, None
    
    try:
        if not force_cpu:
            cuda_paths = setup_cuda_paths()
            if cuda_paths:
                print(f"✅ CUDA paths configured: {len(cuda_paths)} paths found")
            
            try:
                print("🚀 Loading GPU whisper model...")
                model = WhisperModel("small.en", device="cuda", compute_type="float16")
                print("✅ GPU model loaded!")
                return model, "GPU"
            except Exception as e:
                print(f"⚠️  GPU failed: {e}")
                print("🔄 Falling back to CPU model...")
        
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        print("✅ CPU model loaded!")
        return model, "CPU"
        
    except Exception as e:
        print(f"❌ Failed to load whisper model: {e}")
        return None, None


def transcribe_with_whisper(video_path, whisper_model, device_type):
    """Transcribe video file using faster-whisper"""
    try:
        print(f"🎤 Transcribing with faster-whisper ({device_type})...")
        segments, info = whisper_model.transcribe(video_path, beam_size=1, language="en")
        
        text_segments = []
        for segment in segments:
            if segment.text.strip():
                text_segments.append(segment.text.strip())
        
        transcription = ' '.join(text_segments)
        return transcription.strip()
        
    except Exception as e:
        print(f"❌ Whisper transcription failed: {e}")
        return ""


def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def cleanup_memory():
    """Force garbage collection and memory cleanup"""
    gc.collect()
    time.sleep(0.1)


def kill_browser_processes():
    """Kill only browser processes spawned by yt-dlp (our child processes)"""
    current_pid = os.getpid()
    our_children = set()
    
    try:
        # Get all our direct children first
        current_process = psutil.Process(current_pid)
        for child in current_process.children(recursive=True):
            our_children.add(child.pid)
        
        # Only kill browser processes that are our descendants
        for proc in psutil.process_iter(['pid', 'name', 'ppid']):
            try:
                proc_info = proc.info
                proc_name = proc_info['name'].lower()
                
                # Check if it's a browser process AND one of our children
                if (any(browser in proc_name for browser in ['chromium', 'chrome', 'firefox', 'edge']) and
                    proc_info['pid'] in our_children):
                    
                    print(f"🧹 Cleaning up yt-dlp browser process: {proc_name} (PID: {proc_info['pid']})")
                    proc.kill()
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
    except Exception as e:
        # If we can't safely identify our children, don't kill anything
        print(f"⚠️  Skipping browser cleanup due to error: {e}")
        pass


def sanitize_filename(filename):
    """Sanitize filename for filesystem compatibility"""
    if platform.system() == 'Windows':
        invalid_chars = r'[<>:"/\\|?*]'
    else:
        invalid_chars = r'[/]'
    
    filename = re.sub(invalid_chars, '_', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    filename = filename.strip('.')
    
    max_length = 200 if platform.system() == 'Windows' else 255
    if len(filename) > max_length:
        filename = filename[:max_length]
    
    return filename


def extract_metadata_minimal(info_dict):
    """Extract minimal metadata to save memory"""
    metadata = {
        "title": info_dict.get('title', 'Unknown'),
        "description": info_dict.get('description', ''),
        "duration": info_dict.get('duration', 0),
        "video_id": info_dict.get('id', ''),
        "url": info_dict.get('webpage_url', ''),
        "uploader": info_dict.get('uploader', 'Unknown'),
        "uploader_id": info_dict.get('uploader_id', ''),
        "uploader_url": info_dict.get('uploader_url', ''),
        "view_count": info_dict.get('view_count', 0),
        "like_count": info_dict.get('like_count', 0),
        "comment_count": info_dict.get('comment_count', 0),
        "repost_count": info_dict.get('repost_count', 0),
        "hashtags": info_dict.get('tags', []),
        "upload_date": info_dict.get('upload_date', ''),
        "timestamp": info_dict.get('timestamp', 0),
        "width": info_dict.get('width', 0),
        "height": info_dict.get('height', 0),
        "fps": info_dict.get('fps', 0),
        "filesize": info_dict.get('filesize', 0),
        "format": info_dict.get('format', ''),
        "downloaded_at": datetime.now().isoformat(),
        "downloaded_with": f"Robust TikTok Scraper v3.0 ({platform.system()})",
        "platform": platform.system()
    }
    return metadata


def download_single_video(url, output_dir="downloads", quality="best", audio_only=False, 
                         use_whisper=False, whisper_model=None, whisper_device="CPU"):
    """Download a single TikTok video with memory optimization"""
    global shutdown_requested
    
    if shutdown_requested:
        return {'success': False, 'error': 'Shutdown requested', 'url': url}
    
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Memory-optimized yt-dlp options
        temp_ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writesubtitles': False,  # Skip to save memory
            'writeautomaticsub': False,
            'socket_timeout': 30,
            'retries': 2,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        # Extract info
        with yt_dlp.YoutubeDL(temp_ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        metadata = extract_metadata_minimal(info)
        
        # Create output folder
        folder_name = sanitize_filename(metadata['title'])[:100]
        video_folder = Path(output_dir) / folder_name
        video_folder.mkdir(parents=True, exist_ok=True)
        
        # Configure download options
        ydl_opts = {
            'outtmpl': str(video_folder / f"{folder_name}.%(ext)s"),
            'noplaylist': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'socket_timeout': 30,
            'retries': 1,
            'http_headers': temp_ydl_opts['http_headers'],
        }
        
        if audio_only:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }]
        else:
            ydl_opts['format'] = quality
        
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Whisper transcription if requested
        if use_whisper and whisper_model and not audio_only:
            video_file = None
            for file in video_folder.iterdir():
                if file.suffix.lower() in ['.mp4', '.webm', '.mkv']:
                    video_file = file
                    break
            
            if video_file:
                custom_transcription = transcribe_with_whisper(str(video_file), whisper_model, whisper_device)
                if custom_transcription:
                    metadata['custom_transcription'] = custom_transcription
                    metadata['transcription_timestamp'] = datetime.now().isoformat()
                    print(f"✅ Whisper transcription completed ({len(custom_transcription)} chars)")
        
        # Save metadata
        metadata_file = video_folder / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Cleanup
        cleanup_memory()
        kill_browser_processes()
        
        return {
            'success': True,
            'folder': str(video_folder),
            'metadata': metadata,
            'metadata_file': str(metadata_file),
            'url': url
        }
        
    except Exception as e:
        cleanup_memory()
        kill_browser_processes()
        return {'success': False, 'error': str(e), 'url': url}


def mark_url_processed(file_path, url):
    """Mark URL as processed by adding '-' prefix"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in lines:
                stripped = line.strip()
                if stripped == url:
                    f.write(f"-{line}")
                else:
                    f.write(line)
        
        return True
    except Exception as e:
        print(f"❌ Failed to mark URL as processed: {e}")
        return False


def append_to_master_json(metadata, master_file_path):
    """Thread-safe append to master JSON file"""
    try:
        master_path = Path(master_file_path)
        
        # Use file locking for thread safety
        lock_file = Path(f"{master_file_path}.lock")
        
        # Wait for lock
        while lock_file.exists():
            time.sleep(0.1)
        
        # Create lock
        lock_file.touch()
        
        try:
            # Load existing data
            if master_path.exists():
                try:
                    with open(master_path, 'r', encoding='utf-8') as f:
                        master_data = json.load(f)
                    if not isinstance(master_data, list):
                        master_data = [master_data]
                except json.JSONDecodeError:
                    master_data = []
            else:
                master_data = []
            
            # Append new metadata
            master_data.append(metadata)
            
            # Save updated data
            with open(master_path, 'w', encoding='utf-8') as f:
                json.dump(master_data, f, indent=2, ensure_ascii=False)
            
            print(f"📎 Appended to {master_path.name} (total: {len(master_data)} videos)")
            
        finally:
            # Remove lock
            if lock_file.exists():
                lock_file.unlink()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to append to master JSON: {e}")
        if lock_file.exists():
            lock_file.unlink()
        return False


def get_existing_urls(output_dir):
    """Scan existing downloads and get processed URLs"""
    existing_urls = set()
    downloads_path = Path(output_dir)
    
    if not downloads_path.exists():
        return existing_urls
    
    print("🔍 Scanning existing downloads...")
    
    for folder in downloads_path.iterdir():
        if folder.is_dir():
            metadata_file = folder / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    url = metadata.get('url', '')
                    if url:
                        existing_urls.add(url)
                except Exception as e:
                    print(f"⚠️  Failed to read {metadata_file}: {e}")
    
    print(f"✅ Found {len(existing_urls)} existing downloads")
    return existing_urls


def load_urls_from_file(file_path):
    """Load URLs from file, excluding those marked as processed"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return [], []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    unprocessed_urls = []
    processed_urls = []
    
    for line in lines:
        if line.startswith('-') and 'tiktok.com' in line[1:]:
            processed_urls.append(line[1:])  # Remove the '-' prefix
        elif 'tiktok.com' in line and not line.startswith('-'):
            unprocessed_urls.append(line)
    
    print(f"📋 File contains {len(unprocessed_urls)} unprocessed and {len(processed_urls)} processed URLs")
    return unprocessed_urls, processed_urls


def worker_process(args_tuple):
    """Worker function for multiprocessing"""
    url, output_dir, quality, audio_only, append_file, use_whisper, whisper_device = args_tuple
    
    try:
        # Load whisper model in worker process if needed
        whisper_model = None
        if use_whisper and WHISPER_AVAILABLE:
            whisper_model, actual_device = load_whisper_model(force_cpu=(whisper_device == "CPU"))
            if whisper_model:
                whisper_device = actual_device
        
        result = download_single_video(url, output_dir, quality, audio_only, use_whisper, whisper_model, whisper_device)
        
        if result['success'] and append_file:
            append_to_master_json(result['metadata'], append_file)
        
        return result
    except Exception as e:
        return {'success': False, 'error': str(e), 'url': url}


def process_urls_multi(urls, output_dir, quality, audio_only, append_file, url_file, num_processes=10, 
                      use_whisper=False, whisper_device="CPU"):
    """Process URLs using multiple processes"""
    global shutdown_requested
    
    if not urls:
        return []
    
    print(f"🚀 Starting multi-process download with {num_processes} workers")
    print(f"📊 Processing {len(urls)} URLs")
    
    start_time = time.time()
    results = []
    processed_count = 0
    
    # Prepare arguments for workers
    worker_args = [(url, output_dir, quality, audio_only, append_file, use_whisper, whisper_device) for url in urls]
    
    try:
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            # Submit all jobs
            future_to_url = {
                executor.submit(worker_process, args): args[0] 
                for args in worker_args
            }
            
            # Process completed jobs
            for future in as_completed(future_to_url):
                if shutdown_requested:
                    print("🛑 Cancelling remaining downloads...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                url = future_to_url[future]
                
                try:
                    result = future.result(timeout=300)  # 5-minute timeout per video
                    results.append(result)
                    processed_count += 1
                    
                    if result['success']:
                        # Mark URL as processed
                        if url_file:
                            mark_url_processed(url_file, url)
                        
                        print(f"✅ [{processed_count}/{len(urls)}] {result['metadata']['title'][:50]}...")
                    else:
                        print(f"❌ [{processed_count}/{len(urls)}] Failed: {result.get('error', 'Unknown error')}")
                        
                        # Still mark as processed (attempted)
                        if url_file:
                            mark_url_processed(url_file, url)
                
                except Exception as e:
                    print(f"❌ [{processed_count + 1}/{len(urls)}] Worker error: {e}")
                    results.append({'success': False, 'error': str(e), 'url': url})
                    processed_count += 1
                    
                    # Mark as processed (attempted)
                    if url_file:
                        mark_url_processed(url_file, url)
    
    except KeyboardInterrupt:
        print("🛑 Multi-process interrupted")
        shutdown_requested = True
    
    end_time = time.time()
    duration = end_time - start_time
    
    successful = sum(1 for r in results if r.get('success', False))
    
    print(f"\n⏱️  Multi-process timing:")
    print(f"   Total time: {duration:.2f} seconds ({duration/60:.1f} minutes)")
    print(f"   Videos processed: {processed_count}/{len(urls)}")
    print(f"   Successful downloads: {successful}")
    print(f"   Average time per video: {duration/max(processed_count, 1):.2f} seconds")
    
    return results


def process_urls_sequential(urls, output_dir, quality, audio_only, append_file, url_file, use_whisper=False, whisper_model=None, whisper_device="CPU"):
    """Process URLs sequentially"""
    global shutdown_requested
    
    if not urls:
        return []
    
    print(f"🔄 Processing {len(urls)} URLs sequentially")
    
    start_time = time.time()
    results = []
    
    for i, url in enumerate(urls, 1):
        if shutdown_requested:
            print(f"🛑 Stopping at {i-1}/{len(urls)} due to shutdown request")
            break
        
        print(f"\n[{i}/{len(urls)}] Processing: {url}")
        mem_before = get_memory_usage()
        
        # Download video
        result = download_single_video(url, output_dir, quality, audio_only, use_whisper, whisper_model, whisper_device)
        results.append(result)
        
        if result['success']:
            # Append to master JSON if requested
            if append_file:
                append_to_master_json(result['metadata'], append_file)
            
            # Mark URL as processed
            if url_file:
                mark_url_processed(url_file, url)
            
            print(f"✅ [{i}/{len(urls)}] Success: {result['metadata']['title'][:50]}...")
        else:
            print(f"❌ [{i}/{len(urls)}] Failed: {result.get('error', 'Unknown error')}")
            
            # Still mark as processed (attempted)
            if url_file:
                mark_url_processed(url_file, url)
        
        # Memory monitoring
        mem_after = get_memory_usage()
        if mem_after > 8000:  # 8GB threshold
            print(f"⚠️  High memory usage ({mem_after:.1f} MB), forcing cleanup...")
            cleanup_memory()
            kill_browser_processes()
        
        # Brief pause between downloads
        time.sleep(1)
    
    end_time = time.time()
    duration = end_time - start_time
    
    successful = sum(1 for r in results if r.get('success', False))
    processed = len(results)
    
    print(f"\n⏱️  Sequential processing timing:")
    print(f"   Total time: {duration:.2f} seconds ({duration/60:.1f} minutes)")
    print(f"   Videos processed: {processed}/{len(urls)}")
    print(f"   Successful downloads: {successful}")
    print(f"   Average time per video: {duration/max(processed, 1):.2f} seconds")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Robust TikTok downloader with multi-process support")
    parser.add_argument("url", nargs='?', help="TikTok video URL (not needed with --from-file)")
    parser.add_argument("-o", "--output", default="downloads", help="Output directory")
    parser.add_argument("-q", "--quality", default="best", choices=["best", "worst", "720p", "480p", "360p"])
    parser.add_argument("--mp3", action="store_true", help="Download audio only as MP3")
    parser.add_argument("--from-file", "-ff", type=str, help="Process URLs from text file")
    parser.add_argument("--append", type=str, help="Append metadata to master JSON file (real-time)")
    parser.add_argument("--clean", action="store_true", help="Clean up individual folders after ALL processing")
    parser.add_argument("--whisper", action="store_true", help="Use faster-whisper for transcription")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU mode for whisper")
    parser.add_argument("--multi", action="store_true", help="Enable multi-process downloading (10 workers)")
    parser.add_argument("--processes", type=int, default=10, help="Number of worker processes (default: 10)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.url and not args.from_file:
        print("❌ Either provide a URL or use --from-file")
        sys.exit(1)
    
    print("🚀 Robust TikTok Scraper v3.0")
    print("=" * 50)
    print(f"Platform: {platform.system()}")
    print(f"Memory usage: {get_memory_usage():.1f} MB")
    
    if args.url and "tiktok.com" not in args.url:
        print("❌ Please provide a valid TikTok URL")
        sys.exit(1)
    
    # Initialize whisper variables
    whisper_model = None
    whisper_device = "CPU"
    
    # Load whisper model if needed (only for sequential processing)
    if args.whisper and not args.multi:
        if WHISPER_AVAILABLE:
            print("🎤 Loading Whisper model...")
            whisper_model, whisper_device = load_whisper_model(force_cpu=args.force_cpu)
            if not whisper_model:
                print("❌ Failed to load Whisper model, transcription disabled")
                args.whisper = False
        else:
            print("❌ faster-whisper not available, transcription disabled")
            args.whisper = False
    elif args.whisper and args.multi:
        # For multi-processing, whisper models are loaded in worker processes
        if not WHISPER_AVAILABLE:
            print("❌ faster-whisper not available, transcription disabled")
            args.whisper = False
        else:
            whisper_device = "CPU" if args.force_cpu else "AUTO"
    
    overall_start_time = time.time()
    results = []
    
    if args.from_file:
        # Load URLs from file
        unprocessed_urls, processed_urls = load_urls_from_file(args.from_file)
        
        if not unprocessed_urls:
            print("✅ All URLs in file have been processed!")
            return
        
        # Check against existing downloads
        existing_urls = get_existing_urls(args.output)
        urls_to_process = [url for url in unprocessed_urls if url not in existing_urls]
        
        if len(urls_to_process) < len(unprocessed_urls):
            skipped = len(unprocessed_urls) - len(urls_to_process)
            print(f"⏭️  Skipping {skipped} URLs (already downloaded)")
        
        if not urls_to_process:
            print("✅ All unprocessed URLs have already been downloaded!")
            return
        
        # Process URLs
        if args.multi:
            results = process_urls_multi(
                urls_to_process, args.output, args.quality, args.mp3, 
                args.append, args.from_file, args.processes, args.whisper, whisper_device
            )
        else:
            results = process_urls_sequential(
                urls_to_process, args.output, args.quality, args.mp3, 
                args.append, args.from_file, args.whisper, whisper_model, whisper_device
            )
    else:
        # Single URL
        print("📱 Single URL mode")
        start_time = time.time()
        
        result = download_single_video(args.url, args.output, args.quality, args.mp3, 
                                     args.whisper, whisper_model, whisper_device)
        results = [result]
        
        if result['success'] and args.append:
            append_to_master_json(result['metadata'], args.append)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n⏱️  Single URL timing: {duration:.2f} seconds")
        
        if result['success']:
            print(f"✅ Downloaded: {result['metadata']['title']}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
    
    # Overall timing
    overall_end_time = time.time()
    overall_duration = overall_end_time - overall_start_time
    
    # Summary
    successful = sum(1 for r in results if r.get('success', False))
    total = len(results)
    
    print(f"\n🎉 Processing completed!")
    print(f"⏱️  Total execution time: {overall_duration:.2f} seconds ({overall_duration/60:.1f} minutes)")
    print(f"✅ Successful: {successful}/{total}")
    if successful < total:
        print(f"❌ Failed: {total - successful}/{total}")
    
    # Clean up only if ALL processing is complete and not interrupted
    if args.clean and not shutdown_requested and args.from_file:
        # Verify all URLs have been processed
        unprocessed_urls, _ = load_urls_from_file(args.from_file)
        if not unprocessed_urls:
            print(f"\n🗑️  All URLs processed. Cleaning up downloads folder...")
            try:
                shutil.rmtree(args.output)
                print(f"✅ Cleaned up: {args.output}")
            except Exception as e:
                print(f"❌ Cleanup failed: {e}")
        else:
            print(f"\n🚫 Cleanup skipped: {len(unprocessed_urls)} URLs still unprocessed")
    elif args.clean and shutdown_requested:
        print("\n🚫 Cleanup skipped due to interrupted execution")
    
    print(f"\n💾 Final memory usage: {get_memory_usage():.1f} MB")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)