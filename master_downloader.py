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
import argparse
import site
import glob
import warnings
import logging
from pathlib import Path
from datetime import datetime

# Completely suppress all warnings and resource warnings
warnings.filterwarnings("ignore")
warnings.simplefilter("ignore", ResourceWarning)

# Suppress asyncio debug messages
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

def setup_unraisable_hook():
    """Set up sys.unraisablehook to suppress transport exceptions"""
    def suppress_unraisable(unraisable):
        """Custom unraisable exception handler to suppress transport errors"""
        # Check if this is a transport-related exception
        if hasattr(unraisable, 'exc_value') and unraisable.exc_value:
            exc_str = str(unraisable.exc_value).lower()
            if any(phrase in exc_str for phrase in [
                'i/o operation on closed pipe',
                'closed pipe',
                'unclosed transport',
                'unclosed connector'
            ]):
                return  # Suppress transport-related exceptions
        
        # Check if the object is transport-related
        if hasattr(unraisable, 'object') and unraisable.object:
            obj_str = str(type(unraisable.object)).lower()
            if any(phrase in obj_str for phrase in [
                'proactorbasepipetransport',
                'basesubprocesstransport',
                '_proactorsockettransport',
                'sslprotocoltransport'
            ]):
                return  # Suppress transport object exceptions
        
        # For any other unraisable exceptions, use the default behavior
        # but don't print them (since they're usually not critical)
        pass
    
    # Set the custom hook
    sys.unraisablehook = suppress_unraisable

# Apply the unraisable hook immediately
setup_unraisable_hook()

def setup_signal_handlers():
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        """Handle Ctrl+C and other termination signals gracefully"""
        global shutdown_requested
        shutdown_requested = True
        if console:
            console.print("\n🛑 [yellow]Shutdown requested... cleaning up...[/yellow]")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def find_nvidia_paths():
    """Find NVIDIA CUDA/cuDNN paths across different systems and platforms"""
    import site
    import glob
    
    cuda_paths = []
    
    # Get all possible Python site-packages directories
    all_site_dirs = []
    
    # 1. Standard site-packages
    all_site_dirs.extend(site.getsitepackages())
    
    # 2. User site-packages (THIS IS KEY - where your libraries are!)
    if hasattr(site, 'getusersitepackages'):
        user_site = site.getusersitepackages()
        if user_site:
            all_site_dirs.append(user_site)
    
    # 3. Current virtual environment
    if hasattr(sys, 'prefix'):
        all_site_dirs.extend([
            os.path.join(sys.prefix, 'lib', 'python*', 'site-packages'),
            os.path.join(sys.prefix, 'Lib', 'site-packages'),  # Windows
        ])
    
    # 4. Conda environment paths if in conda
    if 'CONDA_PREFIX' in os.environ:
        conda_prefix = os.environ['CONDA_PREFIX']
        all_site_dirs.extend([
            os.path.join(conda_prefix, 'lib', 'python*', 'site-packages'),
            os.path.join(conda_prefix, 'Lib', 'site-packages'),  # Windows
        ])
    
    # 5. Add specific user AppData paths (where your libraries actually are!)
    if sys.platform.startswith('win'):
        appdata_roaming = os.environ.get('APPDATA', '')
        if appdata_roaming:
            python_version = f"Python{sys.version_info.major}{sys.version_info.minor}"
            user_packages = os.path.join(appdata_roaming, 'Python', python_version, 'site-packages')
            all_site_dirs.append(user_packages)
    
    # Expand glob patterns and get unique directories
    expanded_dirs = set()
    for dir_pattern in all_site_dirs:
        if '*' in dir_pattern:
            expanded_dirs.update(glob.glob(dir_pattern))
        elif dir_pattern and os.path.exists(dir_pattern):
            expanded_dirs.add(dir_pattern)
    
    # Look for NVIDIA packages in each site-packages directory
    nvidia_packages = ['nvidia*']
    
    for site_dir in expanded_dirs:
        if not os.path.exists(site_dir):
            continue
            
        # Look for nvidia packages
        for nvidia_pkg in nvidia_packages:
            nvidia_pattern = os.path.join(site_dir, nvidia_pkg)
            
            for nvidia_dir in glob.glob(nvidia_pattern):
                if os.path.isdir(nvidia_dir):
                    # Look for bin directories (Windows) or lib directories (Linux)
                    potential_paths = [
                        os.path.join(nvidia_dir, 'bin'),           # Windows DLLs
                        os.path.join(nvidia_dir, 'lib'),          # Linux .so files  
                        os.path.join(nvidia_dir, 'lib64'),        # Linux 64-bit
                    ]
                    
                    for path in potential_paths:
                        if os.path.exists(path) and path not in cuda_paths:
                            cuda_paths.append(path)
    
    # Also search for the specific paths we know work (from your diagnostic)
    known_working_paths = [
        r"C:\Users\roman\AppData\Roaming\Python\Python313\site-packages\nvidia\cublas\bin",
        r"C:\Users\roman\AppData\Roaming\Python\Python313\site-packages\nvidia\cudnn\bin"
    ]
    
    # Make these paths generic for other users
    username = os.environ.get('USERNAME', 'user')
    python_version = f"Python{sys.version_info.major}{sys.version_info.minor}"
    
    generic_working_paths = [
        os.path.join(os.environ.get('APPDATA', ''), 'Python', python_version, 'site-packages', 'nvidia', 'cublas', 'bin'),
        os.path.join(os.environ.get('APPDATA', ''), 'Python', python_version, 'site-packages', 'nvidia', 'cudnn', 'bin'),
        os.path.join(os.environ.get('APPDATA', ''), 'Python', python_version, 'site-packages', 'ctranslate2')
    ]
    
    for path in generic_working_paths:
        if os.path.exists(path) and path not in cuda_paths:
            cuda_paths.append(path)
    
    # Also check system-wide CUDA installations
    system_cuda_paths = []
    
    if sys.platform.startswith('win'):
        # Windows system paths
        program_files = [
            os.environ.get('PROGRAMFILES', r'C:\Program Files'),
            os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'),
        ]
        
        for pf in program_files:
            system_cuda_paths.extend([
                os.path.join(pf, 'NVIDIA GPU Computing Toolkit', 'CUDA', 'v*', 'bin'),
                os.path.join(pf, 'NVIDIA', 'CUDNN', 'v*', 'bin'),
            ])
    else:
        # Linux/Unix system paths
        system_cuda_paths.extend([
            '/usr/local/cuda*/lib64',
            '/usr/local/cuda*/lib',
            '/opt/cuda*/lib64',
            '/opt/cuda*/lib',
            '/usr/lib/x86_64-linux-gnu',  # Ubuntu/Debian
            '/usr/lib64',                  # CentOS/RHEL
        ])
    
    # Expand system paths and add existing ones
    for path_pattern in system_cuda_paths:
        for path in glob.glob(path_pattern):
            if os.path.exists(path) and path not in cuda_paths:
                cuda_paths.append(path)
    
    return cuda_paths

def verify_cuda_libraries(cuda_paths):
    """Verify that essential CUDA libraries can be found"""
    essential_libs = {
        'windows': ['cudnn_ops64_9.dll', 'cudnn64_9.dll', 'cublas64_12.dll'],
        'linux': ['libcudnn_ops.so.9', 'libcudnn.so.9', 'libcublas.so.12']
    }
    
    platform_key = 'windows' if sys.platform.startswith('win') else 'linux'
    required_libs = essential_libs[platform_key]
    
    found_libs = {}
    missing_libs = []
    
    for lib in required_libs:
        found = False
        for path in cuda_paths:
            lib_path = os.path.join(path, lib)
            if os.path.exists(lib_path):
                found_libs[lib] = lib_path
                found = True
                break
        
        if not found:
            missing_libs.append(lib)
    
    return found_libs, missing_libs

def diagnose_cuda_installation():
    """Comprehensive CUDA installation diagnosis"""
    print("\n🔍 Diagnosing CUDA installation...")
    
    # Find all nvidia packages
    cuda_paths = find_nvidia_paths()
    print(f"📁 Found {len(cuda_paths)} potential CUDA paths:")
    for i, path in enumerate(cuda_paths[:10]):  # Show first 10
        print(f"   {i+1}. {path}")
    if len(cuda_paths) > 10:
        print(f"   ... and {len(cuda_paths) - 10} more")
    
    if not cuda_paths:
        print("❌ No NVIDIA packages found!")
        return False
    
    # Verify essential libraries
    found_libs, missing_libs = verify_cuda_libraries(cuda_paths)
    
    print(f"\n📚 Library status:")
    for lib, path in found_libs.items():
        print(f"   ✅ {lib} -> {path}")
    
    for lib in missing_libs:
        print(f"   ❌ {lib} -> NOT FOUND")
    
    # Try to find missing libraries in more locations
    if missing_libs:
        print(f"\n🔍 Searching for missing libraries...")
        for lib in missing_libs:
            alternative_paths = find_library_alternatives(lib)
            if alternative_paths:
                print(f"   💡 {lib} found at:")
                for alt_path in alternative_paths[:3]:
                    print(f"      📁 {alt_path}")
    
    return len(missing_libs) == 0

def find_library_alternatives(library_name):
    """Find alternative locations for a missing library"""
    import glob
    
    search_patterns = []
    
    if sys.platform.startswith('win'):
        # Windows search patterns
        search_patterns = [
            f"C:\\**\\{library_name}",
            f"{os.environ.get('PROGRAMFILES', '')}\\**\\{library_name}",
            f"{os.environ.get('LOCALAPPDATA', '')}\\**\\{library_name}",
            f"{os.environ.get('APPDATA', '')}\\**\\{library_name}",
        ]
    else:
        # Linux search patterns
        search_patterns = [
            f"/usr/**/lib*{library_name}*",
            f"/opt/**/lib*{library_name}*",
            f"/usr/local/**/lib*{library_name}*",
        ]
    
    found_paths = []
    for pattern in search_patterns:
        try:
            matches = glob.glob(pattern, recursive=True)
            found_paths.extend(matches)
        except:
            continue
    
    return found_paths[:5]  # Return first 5 matches

def setup_cuda_paths():
    """Set up CUDA paths with automatic detection and simple verification"""
    cuda_paths = find_nvidia_paths()
    
    if not cuda_paths:
        print("⚠️ No NVIDIA CUDA paths found - will try CPU")
        return False
    
    # Add to PATH with HIGH PRIORITY (at the beginning)
    current_path = os.environ.get('PATH', '')
    path_separator = ';' if sys.platform.startswith('win') else ':'
    
    added_paths = []
    for cuda_path in cuda_paths:
        if cuda_path not in current_path:
            # Add at the BEGINNING of PATH for priority
            os.environ['PATH'] = cuda_path + path_separator + os.environ['PATH']
            added_paths.append(cuda_path)
    
    if added_paths:
        print(f"✅ Added {len(added_paths)} CUDA paths to PATH:")
        for path in added_paths[:3]:  # Show first 3 paths
            print(f"   📁 {path}")
        if len(added_paths) > 3:
            print(f"   ... and {len(added_paths) - 3} more")
    else:
        print("ℹ️ CUDA paths already in PATH")
    
    # Quick verification - check if essential DLLs are now accessible
    essential_libs = ['cudnn_ops64_9.dll', 'cudnn64_9.dll'] if sys.platform.startswith('win') else ['libcudnn_ops.so.9', 'libcudnn.so.9']
    
    found_essential = 0
    for lib in essential_libs:
        for path in cuda_paths:
            if os.path.exists(os.path.join(path, lib)):
                found_essential += 1
                break
    
    success = found_essential >= len(essential_libs) // 2  # At least half the essential libs found
    
    if success:
        print(f"✅ Found {found_essential}/{len(essential_libs)} essential CUDA libraries")
    else:
        print(f"⚠️ Only found {found_essential}/{len(essential_libs)} essential CUDA libraries")
    
    return success

# Setup CUDA before importing faster-whisper (but only do basic setup)
# Full verification will happen later in load_whisper_model()

try:
    import yt_dlp
    from faster_whisper import WhisperModel
    from TikTokApi import TikTokApi
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, TaskID
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich.status import Status
except ImportError as e:
    print(f"❌ Missing required dependency: {e}")
    print("Install with: pip install -r requirements.txt")
    sys.exit(1)

# Global variables
console = None  # Will be initialized after imports
shutdown_requested = False
processed_videos = []
ms_token = ""
start_time = time.time()
active_apis = []  # Track active TikTok API instances for cleanup

def signal_handler(signum, frame):
    """Handle Ctrl+C and other termination signals gracefully"""
    global shutdown_requested
    shutdown_requested = True
    if console:
        console.print("\n🛑 [yellow]Shutdown requested... cleaning up...[/yellow]")

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
    """Detect if GPU is available and working with more thorough checks"""
    try:
        # First try torch-based check
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return True, f"CUDA ({gpu_name})"
    except ImportError:
        pass
    
    # Try direct CTranslate2 check
    try:
        from ctranslate2 import get_cuda_device_count
        if get_cuda_device_count() > 0:
            return True, "CUDA (via CTranslate2)"
    except:
        pass
    
    # Try basic CUDA check
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, "NVIDIA GPU detected"
    except:
        pass
    
    return False, "No GPU detected"

def load_whisper_model(model_size="small.en"):
    """Load faster-whisper model with smart GPU detection and fallback"""
    
    # First, verify CUDA setup
    cuda_ok = setup_cuda_paths()
    
    gpu_available, gpu_info = detect_gpu_support()
    
    with console.status(f"[bold green]Loading Whisper model... ({gpu_info})"):
        
        # Only try GPU if CUDA libraries are properly set up
        if gpu_available and cuda_ok:
            try:
                # Try GPU with float16 first for best accuracy
                console.print("🚀 Attempting GPU model with float16...")
                model = WhisperModel(
                    model_size,
                    device="cuda",
                    compute_type="float16",
                    download_root=str(Path.home() / ".cache" / "whisper"))
                console.print(f"✅ [bold green]GPU Whisper loaded[/bold green] - {gpu_info} (float16)")
                return model, "GPU (float16)"
            except Exception as e:
                console.print(f"⚠️ [yellow]GPU float16 failed: {str(e)[:100]}...[/yellow]")
                try:
                    console.print("🔄 Trying GPU with float32...")
                    model = WhisperModel(
                        model_size,
                        device="cuda",
                        compute_type="float32",
                        download_root=str(Path.home() / ".cache" / "whisper"))
                    console.print(f"✅ [bold green]GPU Whisper loaded[/bold green] - {gpu_info} (float32)")
                    return model, "GPU (float32)"
                except Exception as e:
                    console.print(f"⚠️ [yellow]GPU float32 failed: {str(e)[:100]}...[/yellow]")
        elif gpu_available and not cuda_ok:
            console.print("⚠️ [yellow]GPU detected but CUDA libraries incomplete - using CPU[/yellow]")
        
        # CPU fallback with best available compute type
        console.print("🔄 Loading CPU model...")
        try:
            # Try int8 first (fastest CPU option)
            model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(Path.home() / ".cache" / "whisper"))
            console.print(f"✅ [bold blue]CPU Whisper loaded[/bold blue] - {gpu_info} (int8)")
            return model, "CPU (int8)"
        except Exception as e:
            console.print(f"⚠️ [yellow]CPU int8 failed: {str(e)[:50]}... Trying default...[/yellow]")
            try:
                # Fallback to default compute type
                model = WhisperModel(
                    model_size,
                    device="cpu",
                    download_root=str(Path.home() / ".cache" / "whisper"))
                console.print(f"✅ [bold blue]CPU Whisper loaded[/bold blue] - {gpu_info} (default)")
                return model, "CPU (default)"
            except Exception as e:
                console.print(f"❌ [bold red]Failed to load Whisper: {e}[/bold red]")
                sys.exit(1)

def setup_directories(assets_path=None, downloads_path=None):
    """Setup required directories with optional custom paths"""
    assets_dir = Path(assets_path) if assets_path else Path("./assets")
    downloads_dir = Path(downloads_path) if downloads_path else Path("./downloads")
    
    assets_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    
    return assets_dir, downloads_dir

def validate_urls_file(assets_dir, urls_file=None):
    """Validate that urls.txt exists with optional custom path"""
    urls_file_path = Path(urls_file) if urls_file else assets_dir / "urls.txt"
    if not urls_file_path.exists():
        console.print(f"❌ [bold red]Error: {urls_file_path} not found![/bold red]")
        console.print(f"📝 Please create {urls_file_path} and add TikTok URLs (one per line)")
        sys.exit(1)
    return urls_file_path

def load_master_json(assets_dir, master_file=None):
    """Load or create master.json with optional custom path"""
    master_file_path = Path(master_file) if master_file else assets_dir / "master.json"
    
    if master_file_path.exists():
        try:
            with open(master_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]
            return data, master_file_path
        except json.JSONDecodeError:
            console.print(f"⚠️ [yellow]Invalid {master_file_path}, creating new one[/yellow]")
    
    return [], master_file_path

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

async def cleanup_active_apis():
    """Clean up all active TikTok API instances"""
    global active_apis
    for api in active_apis[:]:  # Copy list to avoid modification during iteration
        try:
            await api.close_sessions()
            active_apis.remove(api)
        except Exception:
            pass
    active_apis.clear()

async def validate_ms_token(token):
    """Validate MS token by testing TikTok API"""
    global active_apis
    api = None
    try:
        api = TikTokApi()
        active_apis.append(api)
        await api.create_sessions(ms_tokens=[token], num_sessions=1, sleep_after=1)
        return True
    except Exception:
        return False
    finally:
        if api and api in active_apis:
            try:
                await api.close_sessions()
                active_apis.remove(api)
            except Exception:
                pass

async def extract_comments(video_url, max_comments=10):
    """Extract top comments from TikTok video"""
    global active_apis
    api = None
    try:
        if shutdown_requested:
            return []
            
        video_id = extract_video_id_from_url(video_url)
        if not video_id:
            return []
        
        api = TikTokApi()
        active_apis.append(api)
        await api.create_sessions(ms_tokens=[ms_token], num_sessions=1, sleep_after=1)
        
        video = api.video(id=video_id)
        comments_data = []
        
        comment_count = 0
        async for comment in video.comments():
            if shutdown_requested or comment_count >= max_comments:
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
        
        return comments_data
        
    except Exception:
        return []
    finally:
        # Proper cleanup to avoid pipe transport exceptions
        if api and api in active_apis:
            try:
                await api.close_sessions()
                active_apis.remove(api)
            except Exception:
                pass

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

def transcribe_audio(audio_file, whisper_model, progress: Progress):
    """Transcribe audio with faster-whisper and show progress"""
    try:
        # Create progress task
        task_id = progress.add_task("[cyan]Transcribing...", total=None)
        
        # Start transcription - use simpler parameters like the working script
        segments, info = whisper_model.transcribe(
            audio_file,
            beam_size=1,  # Use 1 like in working script for speed
            language="en"
            # Removed additional parameters that might cause issues
        )
        
        # Convert generator to list and collect text
        transcription_segments = []
        for segment in segments:
            if segment.text.strip():
                transcription_segments.append(segment.text.strip())
                # Update progress with segment text
                progress.update(task_id, description=f"[cyan]Transcribing: {segment.text[:30]}...")
        
        # Complete progress task
        progress.update(task_id, visible=False)
        
        # Join all segments into final transcription
        full_transcription = ' '.join(transcription_segments)
        
        return full_transcription, info
    except Exception as e:
        progress.update(task_id, visible=False)
        console.print(f"⚠️ [yellow]Transcription error: {str(e)[:100]}[/yellow]")
        return "", None

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
        temp_file = master_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        
        # Atomic replace
        if sys.platform == 'win32':
            # Windows doesn't support atomic replace, just rename
            temp_file.replace(master_file)
        else:
            # Unix-like systems can use atomic replace
            os.replace(temp_file, master_file)
        
        return True
    except Exception as e:
        console.print(f"⚠️ [yellow]Failed to save master.json: {str(e)[:100]}[/yellow]")
        return False

async def process_video(url, downloads_dir, whisper_model, device_type, master_data, master_file, video_num, total_videos, progress, console):
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
    
    # Create a task for current video steps
    current_task = progress.add_task(f"[cyan]Video {video_num}/{total_videos}[/cyan]", total=5)
    
    def update_step(step_name, status):
        """Update step status and progress display"""
        steps[step_name] = status
        step_display = []
        completed = 0
        for step, stat in steps.items():
            if stat == "done":
                step_display.append(f"[green]{step}[/green]")
                completed += 1
            elif stat == "running":
                step_display.append(f"[yellow]{step}[/yellow]")
            elif stat == "failed":
                step_display.append(f"[red]{step}[/red]")
                completed += 1
            elif stat == "skipped":
                step_display.append(f"[blue]{step}[/blue]")
                completed += 1
            else:
                step_display.append(f"[dim]{step}[/dim]")
        
        progress.update(current_task, 
                       description=f"[cyan]Video {video_num}/{total_videos}[/cyan] - " + " | ".join(step_display),
                       completed=completed)
    
    try:
        # Step 1: Check if URL exists
        update_step("🔍 Checking URL", "running")
        if url_exists_in_master(url, master_data):
            update_step("🔍 Checking URL", "skipped")
            status_parts.append("[yellow]Already exists[/yellow]")
            duration = time.time() - start_time
            
            # Complete the task and remove it
            progress.update(current_task, completed=5)
            progress.remove_task(current_task)
            
            # Add to completed list and print immediately
            processed_videos.append({
                "title": "Already processed",
                "duration": duration,
                "status": " | ".join(status_parts)
            })
            console.print(f"[yellow]✓[/yellow] Video {video_num}: Already processed ({duration:.1f}s)")
            return True
        
        update_step("🔍 Checking URL", "done")
        
        # Step 2: Download audio
        update_step("⬇️ Downloading", "running")
        audio_file, info = download_audio(url, downloads_dir)
        
        if not audio_file or not info:
            update_step("⬇️ Downloading", "failed")
            status_parts.append("[red]Download failed[/red]")
            duration = time.time() - start_time
            
            progress.update(current_task, completed=5)
            progress.remove_task(current_task)
            
            processed_videos.append({
                "title": "Download failed",
                "duration": duration,
                "status": " | ".join(status_parts)
            })
            console.print(f"[red]✗[/red] Video {video_num}: Download failed ({duration:.1f}s)")
            return False
        
        update_step("⬇️ Downloading", "done")
        title = info.get('title', 'Unknown')[:30]
        
        # Step 3: Transcribe audio
        update_step("🎤 Transcribing", "running")
        transcription, transcribe_info = transcribe_audio(audio_file, whisper_model, progress)
        if transcription:
            update_step("🎤 Transcribing", "done")
            status_parts.append(f"[green]Transcribed ({len(transcription)} chars)[/green]")
        else:
            update_step("🎤 Transcribing", "failed")
            status_parts.append("[yellow]No transcription[/yellow]")
        
        # Step 4: Extract comments
        update_step("💬 Comments", "running")
        top_comments = await extract_comments(url)
        if top_comments:
            update_step("💬 Comments", "done")
            status_parts.append(f"[green]{len(top_comments)} comments[/green]")
        else:
            update_step("💬 Comments", "failed")
            status_parts.append("[yellow]No comments[/yellow]")
        
        # Step 5: Save to master.json
        update_step("💾 Saving", "running")
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
            update_step("💾 Saving", "done")
            status_parts.append("[green]Saved[/green]")
        else:
            update_step("💾 Saving", "failed")
            status_parts.append("[red]Save failed[/red]")
        
        duration = time.time() - start_time
        
        # Complete the task and remove it
        progress.update(current_task, completed=5)
        progress.remove_task(current_task)
        
        processed_videos.append({
            "title": title,
            "duration": duration,
            "status": " | ".join(status_parts)
        })
        
        # Print completion immediately
        console.print(f"[green]✓[/green] Video {video_num}: {title} ({duration:.1f}s) - {' | '.join(status_parts)}")
        
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        
        # Mark all remaining steps as failed
        for step_name, status in steps.items():
            if status == "pending" or status == "running":
                update_step(step_name, "failed")
        
        progress.update(current_task, completed=5)
        progress.remove_task(current_task)
        
        processed_videos.append({
            "title": title,
            "duration": duration,
            "status": f"[red]Error: {str(e)[:30]}...[/red]"
        })
        console.print(f"[red]✗[/red] Video {video_num}: Error - {str(e)[:50]} ({duration:.1f}s)")
        return False
    finally:
        clean_downloads(downloads_dir)

async def main():
    """Main processing function with rich UI"""
    global ms_token, start_time, console
    
    # Initialize console here after imports
    console = Console()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Master TikTok Downloader')
    parser.add_argument('--urls', type=str, help='Path to custom urls.txt file')
    parser.add_argument('--master', type=str, help='Path to custom master.json file')
    parser.add_argument('--assets', type=str, help='Path to custom assets directory')
    parser.add_argument('--downloads', type=str, help='Path to custom downloads directory')
    parser.add_argument('--model', type=str, default="small.en", 
                       help='Whisper model size (tiny.en, base.en, small.en, medium.en, large-v3)')
    parser.add_argument('--token', type=str, help='TikTok ms_token (avoids manual input)')
    args = parser.parse_args()
    
    # Setup signal handlers
    setup_signal_handlers()
    
    try:
        console.print(Panel.fit("🚀 [bold blue]Master TikTok Downloader[/bold blue]", 
                               subtitle="Audio + Transcription + Comments"))
        
        # Get MS_TOKEN from user or command line
        if args.token:
            ms_token = args.token
            console.print(f"🔑 [bold green]Using MS token from command line[/bold green]")
        else:
            ms_token = console.input("🔑 [bold yellow]Enter your TikTok ms_token:[/bold yellow] ")
        
        if not ms_token:
            console.print("❌ [bold red]MS_TOKEN is required for comment extraction[/bold red]")
            return
        
        # Validate token
        if not shutdown_requested:
            with console.status("[bold green]Validating MS Token..."):
                token_valid = await validate_ms_token(ms_token)
                if token_valid:
                    console.print("✅ [bold green]MS Token validated successfully[/bold green]")
                else:
                    console.print("⚠️ [yellow]MS Token validation failed - comments may not work[/yellow]")
        
        if shutdown_requested:
            return
        
        # Setup directories
        assets_dir, downloads_dir = setup_directories(args.assets, args.downloads)
        
        # Validate urls.txt
        urls_file = validate_urls_file(assets_dir, args.urls)
        
        # Load URLs
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
        
        if not urls:
            console.print("❌ [bold red]No valid TikTok URLs found in urls file[/bold red]")
            return
        
        total_videos = len(urls)
        console.print(f"📋 Found [bold cyan]{total_videos}[/bold cyan] URLs to process")
        
        if shutdown_requested:
            return
        
        # Load master.json
        master_data, master_file = load_master_json(assets_dir, args.master)
        
        # Load whisper model
        whisper_model, device_type = load_whisper_model(args.model)
        
        if shutdown_requested:
            return
        
        # Process each URL
        start_time = time.time()
        successful = 0
        failed = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
            transient=False  # Keep the progress visible
        ) as progress:
            
            overall_task = progress.add_task("Processing videos...", total=total_videos)
            
            for i, url in enumerate(urls, 1):
                if shutdown_requested:
                    console.print(f"\n🛑 [yellow]Stopping at video {i-1}/{total_videos} due to shutdown request[/yellow]")
                    break
                
                progress.update(overall_task, description=f"Overall Progress ({i-1}/{total_videos})")
                
                success = await process_video(url, downloads_dir, whisper_model, device_type, 
                                            master_data, master_file, i, total_videos, progress, console)
                
                if success:
                    successful += 1
                else:
                    failed += 1
                
                progress.update(overall_task, advance=1)
                
                # Check for shutdown after each video
                if shutdown_requested:
                    console.print(f"\n🛑 [yellow]Stopping at video {i}/{total_videos} due to shutdown request[/yellow]")
                    break
        
        # Clean up any remaining APIs
        await cleanup_active_apis()
        
        # Final summary
        elapsed = time.time() - start_time
        rate = (successful + failed) / elapsed * 60 if elapsed > 0 else 0
        
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
        
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Interrupted by user[/yellow]")
    except Exception as e:
        if console:
            console.print(f"\n❌ [bold red]Unexpected error: {e}[/bold red]")
    finally:
        # Clean up any remaining APIs
        await cleanup_active_apis()
        
        # Final cleanup
        downloads_dir = Path("./downloads")
        if downloads_dir.exists():
            clean_downloads(downloads_dir)

if __name__ == "__main__":
    async def run_with_cleanup():
        """Run main with proper cleanup"""
        try:
            await main()
        except KeyboardInterrupt:
            if console:
                console.print("\n🛑 [yellow]Interrupted by user[/yellow]")
        except Exception as e:
            if console:
                console.print(f"\n❌ [bold red]Unexpected error: {e}[/bold red]")
        finally:
            # Clean up any remaining APIs
            await cleanup_active_apis()
            
            # Final cleanup
            downloads_dir = Path("./downloads")
            if downloads_dir.exists():
                clean_downloads(downloads_dir)
            
            # Force cleanup of any remaining asyncio tasks
            try:
                current_task = asyncio.current_task()
                all_tasks = [task for task in asyncio.all_tasks() if task != current_task]
                
                if all_tasks:
                    # Cancel remaining tasks
                    for task in all_tasks:
                        if not task.done():
                            task.cancel()
                    
                    # Wait briefly for cancellation
                    try:
                        await asyncio.wait_for(asyncio.gather(*all_tasks, return_exceptions=True), timeout=0.3)
                    except asyncio.TimeoutError:
                        pass  # Some tasks didn't finish in time, that's okay
            except Exception:
                pass  # Ignore any cleanup errors
    
    # Run with sys.unraisablehook suppression
    try:
        # Use ProactorEventLoop on Windows (as it should be)
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Run the main coroutine
        asyncio.run(run_with_cleanup())
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # Brief pause to let garbage collection finish quietly
        time.sleep(0.1)