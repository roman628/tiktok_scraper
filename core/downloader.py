#!/usr/bin/env python3
"""
Unified video downloader for TikTok scraper
Consolidates all download functionality into a single class
"""

import os
import subprocess
import json
import gc
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from .models import VideoMetadata, ProcessingStatus
from .utils import URLUtils, FileUtils, extract_title_for_display
from .exceptions import DownloadException, ErrorHandler, retry_on_failure


class VideoDownloader:
    """Unified video downloader combining all download methods"""
    
    def __init__(self, config, error_handler: ErrorHandler = None):
        self.config = config
        self.error_handler = error_handler or ErrorHandler()
        self.whisper_model = None
        self.whisper_device = "CPU"
        
        # Initialize whisper if requested
        if config.use_whisper:
            self._load_whisper_model()
    
    def _load_whisper_model(self):
        """Load whisper model for transcription with improved worker process support"""
        try:
            from faster_whisper import WhisperModel
            import multiprocessing as mp
            
            # Determine if we're in a worker process
            is_worker_process = mp.current_process().name != 'MainProcess'
            
            # Determine device - force CPU in worker processes to avoid conflicts
            if self.config.force_cpu or is_worker_process:
                device = "cpu"
                compute_type = "int8"
                reason = "forced" if self.config.force_cpu else "worker process"
                self.error_handler.handle_info(
                    f"Using CPU mode for Whisper ({reason})",
                    "Transcription Setup"
                )
            else:
                try:
                    import torch
                    if torch.cuda.is_available():
                        device = "cuda"
                        compute_type = "float16"
                    else:
                        device = "cpu"
                        compute_type = "int8"
                except ImportError:
                    device = "cpu"
                    compute_type = "int8"
            
            self.whisper_device = device.upper()
            
            # Load model with retry mechanism for worker processes
            model_size = "base"  # Configurable if needed
            max_attempts = 3 if is_worker_process else 1
            
            for attempt in range(max_attempts):
                try:
                    self.whisper_model = WhisperModel(
                        model_size, 
                        device=device, 
                        compute_type=compute_type,
                        num_workers=1  # Limit threads in worker processes
                    )
                    break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        self.error_handler.handle_warning(
                            f"Whisper model load attempt {attempt + 1} failed, retrying: {e}",
                            "Transcription Setup"
                        )
                        import time
                        time.sleep(1)  # Brief delay before retry
                    else:
                        raise
            
            process_info = f" (Worker {mp.current_process().name})" if is_worker_process else ""
            self.error_handler.handle_success(
                f"Whisper model loaded on {self.whisper_device}{process_info}", 
                "Transcription"
            )
            
        except ImportError:
            self.error_handler.handle_warning(
                "faster-whisper not installed - transcription disabled. Install with: pip install faster-whisper",
                "Transcription Setup"
            )
            self.whisper_model = None
            self.config.use_whisper = False
        except Exception as e:
            process_info = f" in {mp.current_process().name}" if mp.current_process().name != 'MainProcess' else ""
            self.error_handler.handle_error(
                DownloadException(f"Failed to load whisper model{process_info}", original_error=e),
                "Transcription Setup"
            )
            self.whisper_model = None
            # Don't disable transcription globally in worker processes
            if mp.current_process().name == 'MainProcess':
                self.config.use_whisper = False
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def download_video(self, url: str) -> VideoMetadata:
        """Download video and extract metadata"""
        # Validate URL
        if not URLUtils.is_valid_tiktok_url(url):
            raise DownloadException(f"Invalid TikTok URL: {url}")
        
        video_id = URLUtils.extract_video_id(url)
        if not video_id:
            raise DownloadException(f"Could not extract video ID from URL: {url}")
        
        # Create metadata object
        metadata = VideoMetadata(
            url=URLUtils.clean_url(url),
            video_id=video_id,
            audio_only=self.config.audio_only,
            quality=self.config.quality
        )
        
        try:
            metadata.update_status(ProcessingStatus.DOWNLOADING)
            
            # Build yt-dlp command
            ydl_opts = self._build_ydl_options()
            
            # Execute download
            result = self._execute_download(url, ydl_opts)
            
            if not result['success']:
                raise DownloadException(result.get('error', 'Download failed'))
            
            # Update metadata from yt-dlp results
            self._update_metadata_from_ytdl(metadata, result.get('info', {}))
            
            # Perform transcription BEFORE cleanup if requested
            transcription_completed = False
            
            # DEBUG: Log transcription configuration with worker process info
            import multiprocessing as mp
            process_info = f" ({mp.current_process().name})" if mp.current_process().name != 'MainProcess' else ""
            self.error_handler.handle_info(
                f"Transcription config{process_info} - use_whisper: {self.config.use_whisper}, whisper_model loaded: {self.whisper_model is not None}",
                "Transcription Debug"
            )
            
            # Retry Whisper model loading if needed in worker processes
            if self.config.use_whisper and not self.whisper_model:
                import multiprocessing as mp
                if mp.current_process().name != 'MainProcess':
                    self.error_handler.handle_info(
                        "Attempting to reload Whisper model in worker process",
                        "Transcription Debug"
                    )
                    self._load_whisper_model()
            
            if self.config.use_whisper and self.whisper_model:
                metadata.update_status(ProcessingStatus.TRANSCRIBING)
                audio_file = result.get('downloaded_file')
                
                self.error_handler.handle_info(
                    f"Original audio file path from yt-dlp: {audio_file}",
                    "Transcription Debug"
                )
                
                # Handle yt-dlp path normalization issues
                if audio_file:
                    # yt-dlp might use different path separators
                    if not os.path.exists(audio_file):
                        # Try converting path separators
                        alt_audio_file = audio_file.replace('⧸', '/').replace('/', os.sep)
                        if os.path.exists(alt_audio_file):
                            audio_file = alt_audio_file
                            self.error_handler.handle_success(
                                f"Fixed audio file path: {audio_file}",
                                "Transcription Debug"
                            )
                
                # If audio file path is still invalid, do comprehensive search
                if not audio_file or not os.path.exists(audio_file):
                    self.error_handler.handle_warning(
                        f"Direct audio file path not found: {audio_file}",
                        "Transcription"
                    )
                    # Try to find audio file using robust search
                    audio_file = self._find_audio_file(metadata.title)
                    self.error_handler.handle_info(
                        f"Comprehensive audio file search result: {audio_file}",
                        "Transcription Debug"
                    )
                
                if audio_file and os.path.exists(audio_file):
                    self.error_handler.handle_info(
                        f"Starting transcription for: {audio_file}",
                        "Transcription"
                    )
                    # Add file size info for debugging
                    file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
                    self.error_handler.handle_info(
                        f"Audio file size: {file_size} bytes",
                        "Transcription Debug"
                    )
                    
                    # Wrap transcription in try-except to ensure we don't fail silently
                    try:
                        import asyncio
                        # Add timeout based on file duration (more generous for long videos)
                        max_duration = metadata.duration if metadata.duration else 600
                        # Use 20x real-time for very long videos, with minimum 300s
                        timeout = max(max_duration * 20, 300)
                        # No maximum timeout - let long videos complete
                        # timeout = min(timeout, 3600)  # Removed 1 hour limit
                        
                        self.error_handler.handle_info(
                            f"Transcription timeout set to {timeout}s for {max_duration}s audio",
                            "Transcription Debug"
                        )
                        
                        # Run transcription with timeout protection
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(self._transcribe_audio, metadata, audio_file)
                            try:
                                future.result(timeout=timeout)
                                transcription_completed = True
                                self.error_handler.handle_success(
                                    "Transcription completed - now safe to cleanup",
                                    "Transcription"
                                )
                            except concurrent.futures.TimeoutError:
                                self.error_handler.handle_error(
                                    DownloadException(f"Transcription timeout after {timeout}s"),
                                    "Transcription"
                                )
                                # Still mark as completed to allow cleanup
                                transcription_completed = True
                    except Exception as e:
                        self.error_handler.handle_error(
                            DownloadException(f"Transcription failed: {str(e)}", original_error=e),
                            "Transcription"
                        )
                        # Mark as completed even on error to prevent hanging
                        transcription_completed = True
                else:
                    self.error_handler.handle_warning(
                        f"No audio file found for transcription: {metadata.title}",
                        "Transcription"
                    )
                    
                    # DEBUG: List files in download directory
                    try:
                        download_dir = os.path.join(self.config.output_dir, metadata.title)
                        if os.path.exists(download_dir):
                            files = os.listdir(download_dir)
                            self.error_handler.handle_info(
                                f"Files in download directory: {files}",
                                "Transcription Debug"
                            )
                        else:
                            self.error_handler.handle_warning(
                                f"Download directory does not exist: {download_dir}",
                                "Transcription Debug"
                            )
                    except Exception as e:
                        self.error_handler.handle_warning(
                            f"Could not list download directory: {e}",
                            "Transcription Debug"
                        )
                        
            elif self.config.use_whisper and not self.whisper_model:
                self.error_handler.handle_warning(
                    "Whisper model not loaded - skipping transcription",
                    "Transcription"
                )
            elif not self.config.use_whisper:
                self.error_handler.handle_info(
                    "Whisper transcription disabled in configuration",
                    "Transcription Debug"
                )
            
            # Clean up downloaded file ONLY AFTER transcription is complete
            if self.config.audio_only:
                if transcription_completed or not self.config.use_whisper:
                    self._cleanup_download_directory(metadata.title)
                else:
                    self.error_handler.handle_info(
                        "Keeping audio files (transcription skipped)",
                        "Cleanup"
                    )
            
            metadata.update_status(ProcessingStatus.COMPLETED)
            
            self.error_handler.handle_success(
                f"Downloaded: {extract_title_for_display(url)}",
                "Download"
            )
            
            return metadata
            
        except Exception as e:
            error_msg = str(e)
            metadata.update_status(ProcessingStatus.FAILED, error_msg)
            
            self.error_handler.handle_error(
                DownloadException(f"Download failed for {url}", original_error=e),
                "Download"
            )
            
            # Clean up on failure
            if hasattr(metadata, 'title') and metadata.title:
                self._cleanup_download_directory(metadata.title)
            
            raise DownloadException(error_msg, original_error=e)
    
    def _build_ydl_options(self) -> Dict[str, Any]:
        """Build yt-dlp options based on configuration"""
        opts = {
            'outtmpl': os.path.join(self.config.output_dir, '%(title)s', '%(title)s.%(ext)s'),
            'writeinfojson': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US'],
            'ignoreerrors': False,
            'no_warnings': True
        }
        
        # Quality settings
        if self.config.audio_only:
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            })
        else:
            # Video quality mapping
            quality_map = {
                'best': 'best[height<=1080]',
                'worst': 'worst',
                '720p': 'best[height<=720]',
                '480p': 'best[height<=480]', 
                '360p': 'best[height<=360]'
            }
            opts['format'] = quality_map.get(self.config.quality, 'best')
        
        # Proxy settings
        if self.config.proxy:
            opts['proxy'] = self.config.proxy
        
        return opts
    
    def _execute_download(self, url: str, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        """Execute yt-dlp download"""
        try:
            import yt_dlp
            
            # Capture info and download status
            downloaded_file = None
            info_dict = None
            
            class InfoCapture:
                def __init__(self):
                    self.info = None
                    self.downloaded_file = None
                
                def progress_hook(self, d):
                    if d['status'] == 'finished':
                        self.downloaded_file = d['filename']
                
                def info_hook(self, info):
                    self.info = info
            
            capture = InfoCapture()
            ydl_opts['progress_hooks'] = [capture.progress_hook]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info_dict = ydl.extract_info(url, download=False)
                capture.info = info_dict
                
                # Then download
                ydl.download([url])
            
            return {
                'success': True,
                'info': capture.info or info_dict,
                'downloaded_file': capture.downloaded_file
            }
            
        except ImportError:
            return {
                'success': False,
                'error': 'yt-dlp not installed. Please install with: pip install yt-dlp',
                'info': None,
                'downloaded_file': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'info': None,
                'downloaded_file': None
            }
    
    def _update_metadata_from_ytdl(self, metadata: VideoMetadata, info: Dict[str, Any]):
        """Update metadata from yt-dlp info"""
        if not info:
            return
        
        # Basic metadata
        metadata.title = info.get('title', '')
        metadata.description = info.get('description', '')
        metadata.uploader = info.get('uploader', '')
        metadata.upload_date = info.get('upload_date', '')
        
        # Media properties
        metadata.duration = info.get('duration')
        metadata.width = info.get('width')
        metadata.height = info.get('height')
        metadata.filesize = info.get('filesize')
        
        # Statistics
        metadata.view_count = info.get('view_count')
        metadata.like_count = info.get('like_count')
        metadata.comment_count = info.get('comment_count')
        
        # Format info
        metadata.format_id = info.get('format_id')
        
        # Subtitles/captions
        if 'automatic_captions' in info:
            auto_caps = info['automatic_captions']
            if 'en' in auto_caps and auto_caps['en']:
                # Extract text from first English subtitle
                try:
                    subtitle_text = self._extract_subtitle_text(auto_caps['en'][0])
                    metadata.automatic_captions = subtitle_text
                except:
                    pass
        
        if 'subtitles' in info:
            subtitles = info['subtitles']
            if 'en' in subtitles and subtitles['en']:
                try:
                    subtitle_text = self._extract_subtitle_text(subtitles['en'][0])
                    metadata.subtitle = subtitle_text
                except:
                    pass
    
    def _extract_subtitle_text(self, subtitle_info: Dict[str, Any]) -> str:
        """Extract text from subtitle information"""
        # This is a simplified version - in practice you might want to
        # download and parse the subtitle file
        return subtitle_info.get('url', '')
    
    def _transcribe_audio(self, metadata: VideoMetadata, audio_file: str):
        """Transcribe audio using whisper"""
        if not self.whisper_model:
            self.error_handler.handle_warning("No whisper model available", "Transcription")
            return
        if not audio_file:
            self.error_handler.handle_warning("No audio file provided", "Transcription")
            return
        if not os.path.exists(audio_file):
            self.error_handler.handle_warning(f"Audio file not found: {audio_file}", "Transcription")
            return
        
        try:
            self.error_handler.handle_info(
                f"Starting Whisper transcription on {audio_file}",
                "Transcription Debug"
            )
            
            # Get file duration for timeout estimation
            import time
            start_time = time.time()
            
            # Single transcription call with progress monitoring
            segments, info = self.whisper_model.transcribe(
                audio_file,
                beam_size=5,
                language='en',  # Could be configurable
                vad_filter=True,  # Voice activity detection to skip silence
                vad_parameters=dict(min_silence_duration_ms=1000)
            )
            
            self.error_handler.handle_info(
                f"Whisper detected language: {info.language}, duration: {info.duration:.1f}s",
                "Transcription Debug"
            )
            
            # Combine all segments with progress tracking
            transcription_parts = []
            segment_count = 0
            last_save_count = 0
            
            for segment in segments:
                segment_count += 1
                text = segment.text.strip()
                if text:
                    transcription_parts.append(text)
                
                # Log progress every 10 segments for long videos
                if segment_count % 10 == 0:
                    elapsed = time.time() - start_time
                    self.error_handler.handle_info(
                        f"Processing segment {segment_count}, elapsed: {elapsed:.1f}s",
                        "Transcription Progress"
                    )
                
                # Save partial transcription every 50 segments for very long videos
                if segment_count % 50 == 0 and segment_count > last_save_count:
                    partial_transcription = ' '.join(transcription_parts)
                    metadata.whisper_transcription = partial_transcription
                    self.error_handler.handle_info(
                        f"Saved partial transcription: {len(partial_transcription)} chars after {segment_count} segments",
                        "Transcription Progress"
                    )
                    last_save_count = segment_count
            
            # Final transcription
            transcription = ' '.join(transcription_parts)
            metadata.whisper_transcription = transcription
            
            # Log completion time
            total_time = time.time() - start_time
            self.error_handler.handle_info(
                f"Transcription completed in {total_time:.1f}s for {info.duration:.1f}s audio ({segment_count} segments)",
                "Transcription Debug"
            )
            
            self.error_handler.handle_success(
                f"✅ TRANSCRIPTION SUCCESS: {len(transcription)} chars - '{transcription[:200]}{'...' if len(transcription) > 200 else ''}'",
                "Transcription"
            )
            
            # Also debug log the full transcription
            self.error_handler.handle_info(
                f"FULL TRANSCRIPTION: {transcription}",
                "Transcription Debug"
            )
            
        except Exception as e:
            self.error_handler.handle_error(
                DownloadException("Transcription failed", original_error=e),
                "Transcription"
            )
    
    def _find_audio_file(self, title: str) -> str:
        """Find audio file based on video title with robust path handling"""
        if not title:
            return None
        
        # Normalize title to handle yt-dlp's path character replacements
        # yt-dlp replaces forward slashes with ⧸ (U+29F8) 
        normalized_title = title.replace('/', '⧸')
        
        # Try multiple possible directory paths
        possible_dirs = [
            os.path.join(self.config.output_dir, title),           # Original title
            os.path.join(self.config.output_dir, normalized_title), # yt-dlp normalized
        ]
        
        # Also try with common character replacements
        safe_title = title.replace('/', '_').replace('\\', '_').replace(':', '_')
        possible_dirs.append(os.path.join(self.config.output_dir, safe_title))
        
        self.error_handler.handle_info(
            f"Searching for audio file with title: '{title}'",
            "Transcription Debug"
        )
        
        for i, download_dir in enumerate(possible_dirs):
            self.error_handler.handle_info(
                f"Checking directory {i+1}: {download_dir}",
                "Transcription Debug"
            )
            
            if not os.path.exists(download_dir):
                self.error_handler.handle_info(
                    f"Directory {i+1} does not exist: {download_dir}",
                    "Transcription Debug"
                )
                continue
            
            # List contents for debugging
            try:
                contents = os.listdir(download_dir)
                self.error_handler.handle_info(
                    f"Directory {i+1} contents: {contents}",
                    "Transcription Debug"
                )
            except Exception as e:
                self.error_handler.handle_warning(
                    f"Could not list directory {download_dir}: {e}",
                    "Transcription Debug"
                )
                continue
            
            # Look for common audio file extensions
            audio_extensions = ['.mp3', '.m4a', '.wav', '.opus', '.webm']
            
            # Try exact title match first
            for ext in audio_extensions:
                for possible_title in [title, normalized_title, safe_title]:
                    audio_file = os.path.join(download_dir, f"{possible_title}{ext}")
                    if os.path.exists(audio_file):
                        self.error_handler.handle_success(
                            f"Found audio file: {audio_file}",
                            "Transcription Debug"
                        )
                        return audio_file
            
            # If exact match not found, look for any audio file in the directory
            for file in contents:
                if any(file.endswith(ext) for ext in audio_extensions):
                    audio_file = os.path.join(download_dir, file)
                    self.error_handler.handle_success(
                        f"Found audio file (wildcard): {audio_file}",
                        "Transcription Debug"
                    )
                    return audio_file
        
        # Final fallback: search entire output directory for any matching audio files
        self.error_handler.handle_info(
            f"Fallback: Searching entire output directory for audio files containing '{title[:30]}'...",
            "Transcription Debug"
        )
        
        try:
            for root, dirs, files in os.walk(self.config.output_dir):
                for file in files:
                    if any(file.endswith(ext) for ext in ['.mp3', '.m4a', '.wav', '.opus', '.webm']):
                        # Check if filename contains part of the title
                        title_words = title.replace('/', ' ').replace('⧸', ' ').split()[:5]  # First 5 words
                        if any(word.lower() in file.lower() for word in title_words if len(word) > 3):
                            audio_file = os.path.join(root, file)
                            self.error_handler.handle_success(
                                f"Found audio file (deep search): {audio_file}",
                                "Transcription Debug"
                            )
                            return audio_file
        except Exception as e:
            self.error_handler.handle_warning(
                f"Deep search failed: {e}",
                "Transcription Debug"
            )
        
        self.error_handler.handle_warning(
            f"No audio file found for title: {title}",
            "Transcription Debug"
        )
        return None
    
    def _cleanup_download_directory(self, title: str):
        """Clean up download directory after processing"""
        if not title:
            return
        
        try:
            download_dir = os.path.join(self.config.output_dir, title)
            if os.path.exists(download_dir):
                import shutil
                import time
                
                # Retry cleanup with delay if files are in use
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        shutil.rmtree(download_dir)
                        self.error_handler.handle_info(
                            f"Cleaned up directory: {title}",
                            "Cleanup"
                        )
                        break
                    except OSError as e:
                        if attempt < max_retries - 1:
                            self.error_handler.handle_warning(
                                f"Cleanup attempt {attempt + 1} failed, retrying: {e}",
                                "Cleanup"
                            )
                            time.sleep(1)  # Wait 1 second before retry
                        else:
                            raise
                            
        except Exception as e:
            self.error_handler.handle_warning(
                f"Failed to cleanup directory {title}: {e}",
                "Cleanup"
            )
    
    def cleanup_all_downloads(self):
        """Clean up all remaining download directories"""
        try:
            if not os.path.exists(self.config.output_dir):
                return
            
            import shutil
            
            # Get all subdirectories in output directory
            subdirs = [d for d in os.listdir(self.config.output_dir) 
                      if os.path.isdir(os.path.join(self.config.output_dir, d))]
            
            if subdirs:
                self.error_handler.handle_info(
                    f"Cleaning up {len(subdirs)} remaining download directories",
                    "Final Cleanup"
                )
                
                for subdir in subdirs:
                    subdir_path = os.path.join(self.config.output_dir, subdir)
                    try:
                        shutil.rmtree(subdir_path)
                    except Exception as e:
                        self.error_handler.handle_warning(
                            f"Failed to cleanup {subdir}: {e}",
                            "Final Cleanup"
                        )
                
                self.error_handler.handle_success(
                    "Final download cleanup completed",
                    "Final Cleanup"
                )
                
        except Exception as e:
            self.error_handler.handle_warning(
                f"Final cleanup failed: {e}",
                "Final Cleanup"
            )
    
    def cleanup_resources(self):
        """Cleanup downloader resources"""
        # Clean up any remaining downloads if audio-only mode
        if self.config.audio_only:
            self.cleanup_all_downloads()
        
        # Clear whisper model
        if self.whisper_model:
            del self.whisper_model
            self.whisper_model = None
            gc.collect()
    
    def __del__(self):
        """Cleanup on destruction"""
        self.cleanup_resources()