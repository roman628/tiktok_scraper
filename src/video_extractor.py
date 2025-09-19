"""Video extraction and metadata collection using yt-dlp."""

import os
import gc
import time
import json
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import yt_dlp
from utils.resource_manager import ResourceManager
from src.transcript_extractor import TranscriptExtractor
from utils.device_manager import DeviceManager

class VideoExtractor:
    """Handles video downloading and metadata extraction."""
    
    def __init__(self, output_dir: str = "downloads", quality: str = "best", proxy: Optional[str] = None):
        """Initialize video extractor.
        
        Args:
            output_dir: Directory for downloads
            quality: Video quality setting
            proxy: Optional proxy URL
        """
        self.output_dir = output_dir
        self.quality = quality
        self.proxy = proxy
        self.transcript_extractor = None
        self.shutdown_requested = False
        self.shutdown_event = None  # Will be set from worker process
    
    def set_shutdown(self, value: bool = True):
        """Set shutdown flag for graceful termination."""
        self.shutdown_requested = value
    
    def download_single_video(self, url: str, audio_only: bool = False, 
                            use_whisper: bool = False, whisper_model: Any = None,
                            whisper_device: str = "CPU", 
                            shutdown_event=None, progress_callback=None,
                            metadata_only: bool = False) -> Dict[str, Any]:
        """Download a single TikTok video with metadata.
        
        Args:
            url: TikTok video URL
            audio_only: Extract audio only
            use_whisper: Enable transcription
            whisper_model: Pre-loaded Whisper model
            whisper_device: Device for Whisper
            shutdown_event: Event to check for shutdown requests
            metadata_only: Only extract metadata, don't download video
            
        Returns:
            Dictionary with success status and metadata
        """
        # Check both shutdown mechanisms
        if self.shutdown_requested or (shutdown_event and shutdown_event.is_set()):
            return {'success': False, 'error': 'Shutdown requested', 'url': url}
        
        # Store shutdown event for use in download hooks
        if shutdown_event:
            self.shutdown_event = shutdown_event
        
        try:
            # Check shutdown before metadata extraction
            if shutdown_event and shutdown_event.is_set():
                return {'success': False, 'error': 'Shutdown during metadata', 'url': url}
                
            # Extract metadata first
            if progress_callback:
                progress_callback.send_progress('downloading', 10)
                progress_callback.send_log("Extracting video metadata...", 'progress')
            
            metadata = self._extract_metadata(url)
            if not metadata:
                return {'success': False, 'error': 'Failed to extract metadata', 'url': url}
            
            # Check if video is deleted/private
            if isinstance(metadata, dict) and metadata.get('deleted'):
                return {'success': False, 'error': metadata.get('error'), 'deleted': True, 'url': url}
            
            if progress_callback:
                progress_callback.send_progress('downloading', 30)
                progress_callback.send_log("Metadata extracted successfully", 'success')
            
            # If metadata_only, return early without downloading
            if metadata_only:
                if progress_callback:
                    progress_callback.send_progress('downloading', 100)
                    progress_callback.send_log("Metadata-only extraction completed", 'success')
                
                return {
                    'success': True,
                    'metadata': metadata,
                    'file_path': None,
                    'url': url
                }
            
            # Check shutdown before download
            if shutdown_event and shutdown_event.is_set():
                return {'success': False, 'error': 'Shutdown before download', 'url': url}
            
            # Create download folder
            folder_name = self._sanitize_filename(metadata['title'])[:100]
            video_folder = Path(self.output_dir) / folder_name
            video_folder.mkdir(parents=True, exist_ok=True)
            
            # Download video/audio with shutdown event
            if progress_callback:
                progress_callback.send_progress('downloading', 50)
                progress_callback.send_log("Downloading video content...", 'progress')
            
            download_path = self._download_content(url, video_folder, folder_name, audio_only, use_whisper)
            if not download_path:
                return {'success': False, 'error': 'Download failed', 'url': url}
            
            if progress_callback:
                progress_callback.send_progress('downloading', 90)
                progress_callback.send_log("Download completed", 'success')
            
            # Check shutdown before transcription
            if shutdown_event and shutdown_event.is_set():
                return {'success': False, 'error': 'Shutdown before transcription', 'url': url}
                
            # Transcribe if requested
            if use_whisper:
                if progress_callback:
                    progress_callback.start_transcription('small.en' if whisper_model else 'base')
                
                transcript = self._transcribe_video(download_path, whisper_model, whisper_device, progress_callback)
                if transcript:
                    metadata['whisper_transcription'] = transcript
                    metadata['transcription_timestamp'] = datetime.now().isoformat()
                    
                    if progress_callback:
                        # Use complete_transcription which handles progress and logging
                        duration = metadata.get('duration', 0)
                        progress_callback.complete_transcription(duration)
            
            # Save metadata
            metadata_path = video_folder / 'metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # Cleanup
            ResourceManager.cleanup_memory()
            
            return {
                'success': True,
                'folder': str(video_folder),
                'metadata': metadata,
                'metadata_file': str(metadata_path),
                'url': url
            }
            
        except Exception as e:
            ResourceManager.cleanup_memory()
            ResourceManager.kill_browser_processes()
            return {'success': False, 'error': str(e), 'url': url}
    
    def _extract_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract video metadata without downloading."""
        temp_ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'socket_timeout': 30,
            'retries': 2,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        if self.proxy:
            temp_ydl_opts['proxy'] = self.proxy
        
        try:
            with yt_dlp.YoutubeDL(temp_ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                
                # Get upload timestamp
                timestamp = info_dict.get('timestamp', 0)
                
                metadata = {
                    "title": info_dict.get('title', 'Unknown'),
                    "description": info_dict.get('description', ''),
                    "duration": info_dict.get('duration', 0),
                    "video_id": info_dict.get('id', ''),
                    "url": info_dict.get('webpage_url', url),
                    "uploader": info_dict.get('uploader', 'Unknown'),
                    "uploader_id": info_dict.get('uploader_id', ''),
                    "uploader_url": info_dict.get('uploader_url', ''),
                    "view_count": info_dict.get('view_count', 0),
                    "like_count": info_dict.get('like_count', 0),
                    "comment_count": info_dict.get('comment_count', 0),
                    "repost_count": info_dict.get('repost_count', 0),
                    "hashtags": info_dict.get('tags', []),
                    "upload_date": info_dict.get('upload_date', ''),
                    "timestamp": timestamp,
                    "width": info_dict.get('width', 0),
                    "height": info_dict.get('height', 0),
                    "filesize": info_dict.get('filesize', 0),
                    "format": info_dict.get('format', ''),
                    "track_name": info_dict.get('track', None),
                    "track_artist": info_dict.get('artist', None),
                    "downloaded_at": datetime.now().isoformat(),
                    "downloaded_with": f"Robust TikTok Scraper v3.0 ({platform.system()})",
                    "platform": platform.system()
                }
                
                return metadata
                
        except Exception as e:
            error_str = str(e)
            print(f"Metadata extraction error: {error_str}")
            
            # Check if this is a deleted/private video
            from src.url_processor import URLProcessor
            if URLProcessor.is_deleted_video_error(error_str):
                # Return special marker for deleted video
                return {"deleted": True, "error": error_str}
            
            return None
    
    def _download_content(self, url: str, video_folder: Path, folder_name: str, 
                         audio_only: bool, use_whisper: bool) -> Optional[Path]:
        """Download video or audio content with shutdown checking."""
        
        # Define shutdown-aware progress hook
        def progress_hook(d):
            if self.shutdown_event and self.shutdown_event.is_set():
                raise yt_dlp.utils.DownloadError("Shutdown requested during download")
        
        ydl_opts = {
            'outtmpl': str(video_folder / f"{folder_name}.%(ext)s"),
            'noplaylist': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'socket_timeout': 30,
            'retries': 1,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            'progress_hooks': [progress_hook] if self.shutdown_event else []
        }
        
        if self.proxy:
            ydl_opts['proxy'] = self.proxy
        
        if audio_only:
            # Extract audio only - no video download at all
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }]
            # Never keep video files in audio_only mode
            ydl_opts['keepvideo'] = False
        else:
            # Download video
            ydl_opts['format'] = self.quality
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            for file in video_folder.iterdir():
                if file.is_file() and file.stem == folder_name:
                    return file
            
            return None
            
        except Exception as e:
            print(f"Download error: {e}")
            return None
    
    def _transcribe_video(self, video_path: Path, whisper_model: Any, device: str, progress_callback=None) -> str:
        """Transcribe video using local Whisper model with progress tracking."""
        if whisper_model:
            # Use provided model directly (faster-whisper only)
            try:
                segments, info = whisper_model.transcribe(
                    str(video_path),
                    beam_size=5,
                    language="en",
                    condition_on_previous_text=False
                )
                
                # Get total duration for progress calculation
                total_duration = info.duration if hasattr(info, 'duration') else 0
                current_time = 0.0
                segments_list = []
                
                # Process segments incrementally with progress updates
                for segment in segments:
                    segments_list.append(segment.text.strip())
                    
                    # Update progress based on segment end time
                    if progress_callback and total_duration > 0:
                        current_time = segment.end
                        progress_callback.update_transcription(current_time, total_duration)
                
                # Ensure we report 100% completion
                if progress_callback and total_duration > 0:
                    progress_callback.update_transcription(total_duration, total_duration)
                
                return " ".join(segments_list)
            except Exception as e:
                print(f"Transcription error with provided model: {e}")
                return ""
        else:
            # Use TranscriptExtractor with progress callback
            if not self.transcript_extractor:
                # Check config for whether to use OpenAI Whisper
                use_openai_whisper = False
                try:
                    import toml
                    with open('config.toml', 'r') as f:
                        config = toml.load(f)
                        # Use OpenAI Whisper if explicitly configured
                        use_openai_whisper = config.get('download', {}).get('use_openai_whisper', False)
                except:
                    pass

                self.transcript_extractor = TranscriptExtractor(
                    device=device.lower(),
                    shutdown_event=self.shutdown_event,
                    use_openai_whisper=use_openai_whisper
                )
            return self.transcript_extractor.extract_transcript(str(video_path), progress_callback)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Universal invalid characters (safe for all filesystems including Docker)
        # Include # to prevent hashtag issues
        invalid_chars = '<>:"/\\|?*\x00#'

        # Additional problematic sequences
        problematic_patterns = [
            ('||', '_'),  # Double pipes
            ('...', '_'), # Triple dots
            ('  ', ' '),  # Multiple spaces to single
        ]

        # Apply pattern replacements first
        for pattern, replacement in problematic_patterns:
            filename = filename.replace(pattern, replacement)

        # Remove invalid characters
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Remove control characters (anything below ASCII 32)
        filename = ''.join(char for char in filename if ord(char) >= 32)

        # Remove leading/trailing dots and spaces (problematic on Windows)
        filename = filename.strip('. ')

        # Ensure filename isn't empty
        if not filename:
            filename = "untitled"

        # Cross-platform safe length
        max_length = 200
        return filename[:max_length].strip()
    
    def cleanup(self):
        """Clean up resources."""
        if self.transcript_extractor:
            self.transcript_extractor.cleanup()
        ResourceManager.cleanup_memory()
        ResourceManager.kill_browser_processes()

def load_whisper_model(force_cpu: bool = False):
    """Load Whisper model for transcription.
    
    Args:
        force_cpu: Force CPU usage even if GPU available
        
    Returns:
        Tuple of (model, device_string)
    """
    # Use DeviceManager for device selection
    device, compute_type = DeviceManager.get_whisper_device_config(force_cpu)
    
    # Force CPU for MPS devices for better compatibility
    if device == "mps":
        print("MPS detected, using CPU for better compatibility with faster-whisper")
        device = "cpu"
        compute_type = "int8"
    
    print(f"Loading Whisper model on {device.upper()}...")
    
    # Use faster-whisper only
    from faster_whisper import WhisperModel
    
    try:
        # Load model - will automatically use HF cache if already downloaded
        model = WhisperModel(
            model_size_or_path="small.en",
            device=device,
            compute_type=compute_type
        )
        print(f"✓ Whisper model loaded on {device.upper()}")
        return model, device.upper()
    except Exception as e:
        print(f"Failed to load Whisper model on {device}: {e}")
        if device != "cpu":
            print("Falling back to CPU")
            try:
                model = WhisperModel("small.en", device="cpu", compute_type="int8")
                return model, "CPU"
            except Exception as cpu_err:
                print(f"Failed to load on CPU: {cpu_err}")
                return None, "CPU"
        return None, "CPU"

def get_memory_usage():
    """Get current memory usage in MB."""
    return ResourceManager.get_memory_usage_mb()