#!/usr/bin/env python3
"""
Enhanced TikTok Video Downloader
Downloads TikTok videos with comprehensive metadata extraction, batch processing, and transcription
Cross-platform support: Windows, macOS, Linux
"""

import os
import sys
import json
import argparse
import re
import platform
from pathlib import Path
from datetime import datetime
import shutil
import site

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed.")
    print("Install it with: pip install yt-dlp")
    sys.exit(1)

try:
    from comment_scraper import scrape_tiktok_comments
except ImportError:
    print("⚠️  Comment scraper not available. Comments will not be extracted.")
    def scrape_tiktok_comments(url, max_comments=5):
        return []


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
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return sys.prefix
    return None


def find_nvidia_libraries():
    """Find NVIDIA CUDA libraries across different platforms and installation methods"""
    platform_info = get_platform_info()
    possible_locations = []
    
    # Virtual environment paths (highest priority)
    venv_path = find_venv_path()
    if venv_path:
        if platform_info['is_windows']:
            venv_site_packages = os.path.join(venv_path, "Lib", "site-packages")
        else:
            # Find the actual site-packages directory in venv
            for path in site.getsitepackages():
                if venv_path in path:
                    venv_site_packages = path
                    break
            else:
                # Fallback for virtual environments
                python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
                venv_site_packages = os.path.join(venv_path, "lib", python_version, "site-packages")
        
        nvidia_venv_path = os.path.join(venv_site_packages, "nvidia")
        if os.path.exists(nvidia_venv_path):
            possible_locations.append(("VENV", nvidia_venv_path))
    
    # System-wide installation paths
    for site_path in site.getsitepackages():
        nvidia_path = os.path.join(site_path, "nvidia")
        if os.path.exists(nvidia_path):
            possible_locations.append(("SYSTEM", nvidia_path))
    
    # User installation paths
    user_site = site.getusersitepackages()
    if user_site:
        nvidia_user_path = os.path.join(user_site, "nvidia")
        if os.path.exists(nvidia_user_path):
            possible_locations.append(("USER", nvidia_user_path))
    
    # Platform-specific system locations
    if platform_info['is_linux']:
        linux_paths = [
            "/usr/local/cuda/lib64",
            "/usr/lib/x86_64-linux-gnu",
            "/opt/cuda/lib64"
        ]
        for path in linux_paths:
            if os.path.exists(path):
                possible_locations.append(("SYSTEM_LINUX", path))
    
    elif platform_info['is_mac']:
        mac_paths = [
            "/usr/local/cuda/lib",
            "/opt/homebrew/lib",
            "/usr/local/lib"
        ]
        for path in mac_paths:
            if os.path.exists(path):
                possible_locations.append(("SYSTEM_MAC", path))
    
    return possible_locations


def setup_cuda_paths():
    """Set up CUDA paths for faster-whisper across platforms"""
    platform_info = get_platform_info()
    nvidia_locations = find_nvidia_libraries()
    
    cuda_paths = []
    
    for location_type, base_path in nvidia_locations:
        # For pip-installed nvidia packages
        if "nvidia" in base_path:
            potential_subdirs = ["cublas", "cudnn", "cufft", "curand", "cusparse"]
            for subdir in potential_subdirs:
                if platform_info['is_windows']:
                    lib_path = os.path.join(base_path, subdir, "bin")
                else:
                    lib_path = os.path.join(base_path, subdir, "lib")
                
                if os.path.exists(lib_path):
                    cuda_paths.append(lib_path)
        else:
            # For system-wide CUDA installations
            if os.path.exists(base_path):
                cuda_paths.append(base_path)
    
    # Add paths to environment
    if cuda_paths:
        current_path = os.environ.get('PATH', '')
        if platform_info['is_windows']:
            ld_var = 'PATH'
            separator = ';'
        else:
            ld_var = 'LD_LIBRARY_PATH'
            separator = ':'
            # Also set PATH for some systems
            current_ld = os.environ.get('LD_LIBRARY_PATH', '')
        
        # Update PATH
        for cuda_path in cuda_paths:
            if cuda_path not in current_path:
                os.environ['PATH'] = cuda_path + platform_info['path_sep'] + os.environ['PATH']
        
        # Update LD_LIBRARY_PATH on Unix systems
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
    try:
        from faster_whisper import WhisperModel
        
        if not force_cpu:
            # Setup CUDA paths before trying GPU
            cuda_paths = setup_cuda_paths()
            if cuda_paths:
                print(f"✅ CUDA paths configured: {len(cuda_paths)} paths found")
            
            try:
                print("🚀 Loading GPU whisper model...")
                model = WhisperModel("small.en", device="cuda", compute_type="float16")
                print("✅ GPU model loaded!")
                return model, "GPU"
            except Exception as e:
                print(f"⚠️  GPU failed during loading: {e}")
                print("🔄 Falling back to CPU model...")
        else:
            print("🔄 Using CPU mode (forced)...")
        
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        print("✅ CPU model loaded!")
        return model, "CPU"
            
    except ImportError:
        print("❌ faster-whisper not installed. Install with: pip install faster-whisper numpy")
        return None, None


def diagnose_cuda_environment():
    """Diagnose CUDA environment for debugging across platforms"""
    platform_info = get_platform_info()
    
    print(f"\n🔍 CUDA Environment Diagnostic ({platform_info['system'].title()}):")
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Python prefix: {sys.prefix}")
    
    # Check if in virtual environment
    venv_path = find_venv_path()
    if venv_path:
        print(f"🌐 Virtual environment: {venv_path}")
    else:
        print("🌐 Not in virtual environment")
    
    # Find NVIDIA libraries
    nvidia_locations = find_nvidia_libraries()
    
    if nvidia_locations:
        print("\n📦 NVIDIA Libraries Found:")
        for location_type, base_path in nvidia_locations:
            print(f"   ✅ {location_type}: {base_path}")
            
            # Check specific components for pip installations
            if "nvidia" in base_path:
                components = ["cublas", "cudnn", "cufft", "curand", "cusparse"]
                for component in components:
                    if platform_info['is_windows']:
                        comp_path = os.path.join(base_path, component, "bin")
                        dll_pattern = "*.dll"
                    else:
                        comp_path = os.path.join(base_path, component, "lib")
                        dll_pattern = "*.so*"
                    
                    if os.path.exists(comp_path):
                        try:
                            if platform_info['is_windows']:
                                files = [f for f in os.listdir(comp_path) if f.endswith('.dll')]
                            else:
                                files = [f for f in os.listdir(comp_path) if '.so' in f]
                            print(f"      ✅ {component}: {len(files)} libraries")
                            
                            # Check for specific cuDNN library that commonly fails
                            if component == "cudnn":
                                if platform_info['is_windows']:
                                    critical_files = [f for f in files if 'cudnn_ops' in f]
                                else:
                                    critical_files = [f for f in files if 'libcudnn_ops' in f]
                                if critical_files:
                                    print(f"         ✅ Critical cuDNN ops library found")
                                else:
                                    print(f"         ⚠️  cuDNN ops library not found")
                        except Exception as e:
                            print(f"      ❌ Error reading {component}: {e}")
                    else:
                        print(f"      ❌ {component}: Not found")
    else:
        print("\n❌ No NVIDIA libraries found")
        print("💡 Try installing: pip install nvidia-cudnn-cu12 nvidia-cublas-cu12")
    
    # Check current environment variables
    current_path = os.environ.get('PATH', '')
    cuda_in_path = any('nvidia' in path.lower() or 'cuda' in path.lower() 
                      for path in current_path.split(platform_info['path_sep']))
    if cuda_in_path:
        print("✅ CUDA-related paths detected in PATH")
    else:
        print("⚠️  No CUDA paths in PATH")
    
    if not platform_info['is_windows']:
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if ld_path and ('nvidia' in ld_path.lower() or 'cuda' in ld_path.lower()):
            print("✅ CUDA-related paths in LD_LIBRARY_PATH")
        else:
            print("⚠️  No CUDA paths in LD_LIBRARY_PATH")
    
    # Test CUDA setup
    print("\n🧪 Testing CUDA setup...")
    setup_cuda_paths()
    print("✅ CUDA paths configured for this session")
    
    # Check for common ML frameworks
    frameworks = [
        ('torch', 'PyTorch'),
        ('tensorflow', 'TensorFlow'),
        ('faster_whisper', 'Faster-Whisper')
    ]
    
    print("\n🧠 ML Framework Check:")
    for module, name in frameworks:
        try:
            __import__(module)
            print(f"   ✅ {name} installed")
            
            # Special check for PyTorch CUDA
            if module == 'torch':
                torch = __import__(module)
                if hasattr(torch, 'cuda') and torch.cuda.is_available():
                    try:
                        device_name = torch.cuda.get_device_name()
                        print(f"      ✅ CUDA available: {device_name}")
                    except:
                        print(f"      ✅ CUDA available: Device name unavailable")
                else:
                    print(f"      ❌ CUDA not available")
        except ImportError:
            print(f"   ❌ {name} not installed")
    
    print()  # Empty line for readability


def sanitize_filename(filename):
    """Sanitize filename for filesystem compatibility across platforms"""
    # Remove or replace invalid characters (more comprehensive for cross-platform)
    if platform.system() == 'Windows':
        invalid_chars = r'[<>:"/\\|?*]'
    else:
        invalid_chars = r'[/]'  # Unix systems mainly restrict forward slash
    
    filename = re.sub(invalid_chars, '_', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    filename = filename.strip('.')
    
    # Limit length (filesystem limits)
    max_length = 200 if platform.system() == 'Windows' else 255
    if len(filename) > max_length:
        filename = filename[:max_length]
    
    return filename


def extract_subtitles_text(info_dict):
    """Extract subtitles and convert to plain text paragraph"""
    subtitle_text = ""
    
    # Try automatic captions first
    if 'automatic_captions' in info_dict:
        for lang, captions in info_dict['automatic_captions'].items():
            if captions and isinstance(captions, list):
                for caption in captions:
                    if caption.get('ext') == 'vtt' and caption.get('url'):
                        try:
                            import urllib.request
                            with urllib.request.urlopen(caption['url']) as response:
                                vtt_content = response.read().decode('utf-8')
                                # Simple VTT parsing - extract text lines
                                lines = vtt_content.split('\n')
                                text_lines = []
                                for line in lines:
                                    line = line.strip()
                                    # Skip VTT headers, timestamps, and empty lines
                                    if (line and not line.startswith('WEBVTT') and 
                                        not line.startswith('NOTE') and
                                        not '-->' in line and
                                        not line.isdigit()):
                                        # Remove VTT formatting tags
                                        clean_line = re.sub(r'<[^>]+>', '', line)
                                        if clean_line:
                                            text_lines.append(clean_line)
                                
                                subtitle_text = ' '.join(text_lines)
                                break
                        except Exception as e:
                            print(f"⚠️  Failed to download subtitles: {e}")
                
                if subtitle_text:
                    break
    
    # Try regular subtitles if automatic captions failed
    if not subtitle_text and 'subtitles' in info_dict:
        for lang, subs in info_dict['subtitles'].items():
            if subs and isinstance(subs, list):
                for sub in subs:
                    if sub.get('ext') == 'vtt' and sub.get('url'):
                        try:
                            import urllib.request
                            with urllib.request.urlopen(sub['url']) as response:
                                vtt_content = response.read().decode('utf-8')
                                lines = vtt_content.split('\n')
                                text_lines = []
                                for line in lines:
                                    line = line.strip()
                                    if (line and not line.startswith('WEBVTT') and 
                                        not line.startswith('NOTE') and
                                        not '-->' in line and
                                        not line.isdigit()):
                                        clean_line = re.sub(r'<[^>]+>', '', line)
                                        if clean_line:
                                            text_lines.append(clean_line)
                                
                                subtitle_text = ' '.join(text_lines)
                                break
                        except Exception as e:
                            print(f"⚠️  Failed to download subtitles: {e}")
                
                if subtitle_text:
                    break
    
    return subtitle_text.strip()


def extract_metadata(info_dict, url=None, scrape_comments=False):
    """Extract and organize metadata from yt-dlp info dictionary"""
    
    # Extract subtitle text
    subtitle_text = extract_subtitles_text(info_dict)
    
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
        
        # Engagement metrics (what yt-dlp can extract)
        "view_count": info_dict.get('view_count', 0),
        "like_count": info_dict.get('like_count', 0),
        "comment_count": info_dict.get('comment_count', 0),
        "repost_count": info_dict.get('repost_count', 0),
        
        # Note: yt-dlp typically cannot extract these from TikTok
        "save_count": info_dict.get('save_count', 0),  # Usually not available
        "share_count": info_dict.get('share_count', 0),  # Usually not available
        
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
        
        # Transcription data
        "subtitle_transcription": subtitle_text,
        "custom_transcription": "",
        "transcription_timestamp": "",
        
        # Comments (yt-dlp limitation - usually empty for TikTok)
        "top_comments": [],  # Will be populated by web scraping if enabled
        
        # Download metadata
        "downloaded_at": datetime.now().isoformat(),
        "downloaded_with": f"Enhanced TikTok Downloader v2.1 ({platform.system()})",
        "platform": platform.system()
    }
    
    # Scrape comments if enabled and URL is provided
    if scrape_comments and url:
        try:
            print("🔍 Scraping comments...")
            comments = scrape_tiktok_comments(url, 10)
            metadata["top_comments"] = comments
            if comments:
                print(f"✅ Successfully scraped {len(comments)} comments")
            else:
                print("⚠️  No comments scraped")
        except Exception as e:
            print(f"❌ Error scraping comments: {e}")
            metadata["top_comments"] = []
    
    return metadata


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
        error_msg = str(e).lower()
        print(f"❌ Whisper transcription failed on {device_type}: {e}")
        
        # Check for specific GPU-related errors that indicate we should fallback
        gpu_errors = [
            'cudnn', 'cuda', 'gpu', 'invalid handle', 'cannot load symbol',
            'could not locate', 'dll', 'library', 'device', 'out of memory'
        ]
        
        is_gpu_error = any(gpu_keyword in error_msg for gpu_keyword in gpu_errors)
        
        # If GPU failed with GPU-related error, try CPU fallback
        if device_type == "GPU" and is_gpu_error:
            print("🔄 GPU error detected, attempting CPU fallback...")
            try:
                from faster_whisper import WhisperModel
                print("📥 Loading CPU fallback model...")
                cpu_model = WhisperModel("small.en", device="cpu", compute_type="int8")
                print("✅ CPU fallback model loaded!")
                
                print("🎤 Transcribing with CPU fallback...")
                segments, info = cpu_model.transcribe(video_path, beam_size=1, language="en")
                text_segments = []
                for segment in segments:
                    if segment.text.strip():
                        text_segments.append(segment.text.strip())
                
                transcription = ' '.join(text_segments)
                print("✅ CPU fallback transcription completed!")
                return transcription.strip()
                
            except Exception as cpu_error:
                print(f"❌ CPU fallback also failed: {cpu_error}")
                return ""
        
        return ""


def download_tiktok_video(url, output_dir="downloads", quality="best", audio_only=False, 
                         use_whisper=False, whisper_model=None, whisper_device="CPU", scrape_comments=False):
    """
    Download a TikTok video with comprehensive metadata extraction
    """
    
    # Create base output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # First, extract info without downloading to get metadata
    print("📊 Extracting video information...")
    
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
        metadata = extract_metadata(info, url, scrape_comments)
        
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
        
        if metadata['subtitle_transcription']:
            print(f"   Subtitles: Found ({len(metadata['subtitle_transcription'])} chars)")
        
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
        
        # Find the downloaded video file for whisper transcription
        video_file = None
        if use_whisper and whisper_model and not audio_only:
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
        
        # Save metadata to JSON file
        metadata_file = video_folder / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully downloaded {'audio' if audio_only else 'video'}: {metadata['title']}")
        print(f"📄 Metadata saved to: {metadata_file}")
        print(f"📂 All files saved in: {video_folder}")
        
        return {
            'success': True,
            'folder': str(video_folder),
            'metadata': metadata,
            'metadata_file': str(metadata_file)
        }
        
    except yt_dlp.utils.DownloadError as e:
        print(f"❌ Download error: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {'success': False, 'error': str(e)}


def process_from_file(file_path, **kwargs):
    """Process multiple URLs from a text file"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
    
    if not urls:
        print("❌ No valid TikTok URLs found in file")
        return []
    
    print(f"🔄 Processing {len(urls)} URLs from {file_path}")
    results = []
    batch_metadata = []  # Store metadata for batch processing
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*50}")
        print(f"Processing {i}/{len(urls)}: {url}")
        print(f"{'='*50}")
        
        result = download_tiktok_video(url, **kwargs)
        results.append(result)
        
        if result['success']:
            print(f"✅ {i}/{len(urls)} completed successfully")
            batch_metadata.append(result['metadata'])
        else:
            print(f"❌ {i}/{len(urls)} failed: {result.get('error', 'Unknown error')}")
        
        # Auto-append to master2.json every 10 successful downloads
        if len(batch_metadata) >= 10:
            print(f"\n💾 Auto-saving batch of {len(batch_metadata)} videos to master2.json...")
            append_batch_to_master_json(batch_metadata, "master2.json")
            batch_metadata = []  # Reset batch
    
    # Save any remaining metadata at the end
    if batch_metadata:
        print(f"\n💾 Saving final batch of {len(batch_metadata)} videos to master2.json...")
        append_batch_to_master_json(batch_metadata, "master2.json")
    
    return results


def append_batch_to_master_json(metadata_list, master_file_path):
    """Append batch of metadata to master JSON file"""
    master_path = Path(master_file_path)
    
    # Load existing data or create new list
    if master_path.exists():
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            if not isinstance(master_data, list):
                master_data = [master_data]  # Convert single object to list
        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON in {master_path}, creating new file")
            master_data = []
    else:
        master_data = []
    
    # Append new metadata batch
    master_data.extend(metadata_list)
    
    # Save updated data
    with open(master_path, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2, ensure_ascii=False)
    
    print(f"📎 Appended batch to master file: {master_path} (+{len(metadata_list)} videos, total: {len(master_data)} videos)")


def append_to_master_json(metadata, master_file_path):
    """Append metadata to master JSON file"""
    master_path = Path(master_file_path)
    
    # Load existing data or create new list
    if master_path.exists():
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            if not isinstance(master_data, list):
                master_data = [master_data]  # Convert single object to list
        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON in {master_path}, creating new file")
            master_data = []
    else:
        master_data = []
    
    # Append new metadata
    master_data.append(metadata)
    
    # Save updated data
    with open(master_path, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2, ensure_ascii=False)
    
    print(f"📎 Appended to master file: {master_path} (total: {len(master_data)} videos)")


def cleanup_folders(results, output_dir):
    """Clean up individual video folders after processing"""
    cleaned_count = 0
    
    for result in results:
        if result['success'] and 'folder' in result:
            folder_path = Path(result['folder'])
            if folder_path.exists():
                try:
                    shutil.rmtree(folder_path)
                    cleaned_count += 1
                    print(f"🗑️  Cleaned: {folder_path.name}")
                except Exception as e:
                    print(f"❌ Failed to clean {folder_path}: {e}")
    
    print(f"✅ Cleaned up {cleaned_count} folders")


def main():
    parser = argparse.ArgumentParser(description="Enhanced TikTok downloader with metadata and batch processing")
    parser.add_argument("url", nargs='?', help="TikTok video URL (not needed with --from-file)")
    parser.add_argument("-o", "--output", default="downloads", 
                       help="Output directory (default: downloads)")
    parser.add_argument("-q", "--quality", default="best",
                       choices=["best", "worst", "720p", "480p", "360p"],
                       help="Video quality (default: best)")
    parser.add_argument("--mp3", action="store_true",
                       help="Download audio only as MP3 instead of video")
    parser.add_argument("--whisper", action="store_true",
                       help="Use faster-whisper for additional transcription")
    parser.add_argument("--force-cpu", action="store_true",
                       help="Force CPU mode for whisper (bypass GPU issues)")
    parser.add_argument("--scrape-comments", action="store_true",
                       help="Scrape top 5 comments from TikTok videos")
    parser.add_argument("--diagnose", action="store_true",
                       help="Diagnose CUDA environment and exit")
    parser.add_argument("--from-file", "-ff", type=str,
                       help="Batch process URLs from text file")
    parser.add_argument("--append", type=str,
                       help="Append metadata to master JSON file")
    parser.add_argument("--clean", action="store_true",
                       help="Clean up individual folders after processing (use with --append)")
    
    args = parser.parse_args()
    
    # Handle diagnostic mode
    if args.diagnose:
        diagnose_cuda_environment()
        return
    
    # Validate arguments
    if not args.url and not args.from_file:
        print("❌ Either provide a URL or use --from-file")
        sys.exit(1)
    
    if args.url and "tiktok.com" not in args.url:
        print("❌ Please provide a valid TikTok URL")
        sys.exit(1)
    
    # Load whisper model if requested
    whisper_model = None
    whisper_device = "CPU"
    if args.whisper:
        print("🎤 Loading faster-whisper model...")
        whisper_model, whisper_device = load_whisper_model(force_cpu=args.force_cpu)
        if not whisper_model:
            print("❌ Failed to load whisper model")
            sys.exit(1)
        print(f"✅ Whisper model loaded on {whisper_device}")
    
    # Prepare kwargs for download function
    download_kwargs = {
        'output_dir': args.output,
        'quality': args.quality,
        'audio_only': args.mp3,
        'use_whisper': args.whisper,
        'whisper_model': whisper_model,
        'whisper_device': whisper_device,
        'scrape_comments': args.scrape_comments
    }
    
    # Process videos
    results = []
    
    if args.from_file:
        # Batch processing
        results = process_from_file(args.from_file, **download_kwargs)
    else:
        # Single video
        result = download_tiktok_video(args.url, **download_kwargs)
        results = [result]
    
    # Append to master JSON if requested
    if args.append:
        print(f"\n📎 Appending metadata to master file...")
        for result in results:
            if result['success']:
                append_to_master_json(result['metadata'], args.append)
    
    # Clean up folders if requested
    if args.clean:
        print(f"\n🗑️  Cleaning up folders...")
        cleanup_folders(results, args.output)
    
    # Summary
    successful = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"\n🎉 Processing completed!")
    print(f"✅ Successful: {successful}/{total}")
    if successful < total:
        print(f"❌ Failed: {total - successful}/{total}")


if __name__ == "__main__":
    # Interactive mode if no arguments
    if len(sys.argv) == 1:
        platform_info = get_platform_info()
        print("Enhanced TikTok Video Downloader v2.1")
        print("=" * 50)
        print(f"Platform: {platform_info['system'].title()}")
        print("Features:")
        print("• Video + Comprehensive Metadata")
        print("• Subtitle Extraction") 
        print("• Optional Whisper Transcription")
        print("• Batch Processing")
        print("• Master JSON Compilation")
        print("• Cross-platform Support")
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
        
        use_whisper = input("Use faster-whisper transcription? (y/n, press Enter for 'n'): ").strip().lower()
        use_whisper = use_whisper in ['y', 'yes', '1', 'true']
        
        scrape_comments = input("Scrape top 5 comments? (y/n, press Enter for 'n'): ").strip().lower()
        scrape_comments = scrape_comments in ['y', 'yes', '1', 'true']
        
        whisper_model = None
        whisper_device = "CPU"
        if use_whisper:
            print("🎤 Loading faster-whisper model...")
            whisper_model, whisper_device = load_whisper_model(force_cpu=False)
            if whisper_model:
                print(f"✅ Whisper model loaded on {whisper_device}")
            else:
                use_whisper = False
        
        result = download_tiktok_video(url, output_dir, quality, audio_only, use_whisper, whisper_model, whisper_device, scrape_comments)
        if result['success']:
            print(f"\n🎉 Download completed successfully!")
            print(f"📁 Files saved to: {result['folder']}")
    else:
        main()