"""Transcript extraction using Whisper AI."""

import os
import subprocess
from typing import Optional, Tuple, Any
from utils.resource_manager import ResourceManager
from utils.device_manager import DeviceManager

class TranscriptExtractor:
    """Handles video transcription using Whisper AI."""
    
    def __init__(self, model_size: str = "base", device: str = "auto", shutdown_event=None):
        """Initialize Whisper model.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to use (auto, cuda, mps, cpu)
            shutdown_event: Event for graceful shutdown
        """
        self.model_size = model_size
        self.shutdown_event = shutdown_event
        
        # Use DeviceManager for device selection
        if device == "auto":
            self.device = DeviceManager.get_best_device()
        else:
            self.device = device
        
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model with appropriate settings."""
        # Force CPU for MPS devices for better compatibility
        if self.device == "mps":
            print("MPS detected, using CPU for better compatibility with faster-whisper")
            self.device = "cpu"
        
        # Use faster-whisper only
        from faster_whisper import WhisperModel
        compute_type = DeviceManager.get_compute_type(self.device)
        
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type
            )
            print(f"Loaded faster-whisper model: {self.model_size} on {self.device.upper()}")
        except Exception as e:
            print(f"Failed to load model on {self.device}: {e}")
            if self.device != "cpu":
                print("Falling back to CPU...")
                self.device = "cpu"
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                print(f"Loaded faster-whisper model: {self.model_size} on CPU")
    
    def extract_transcript(self, video_path: str, progress_callback=None) -> str:
        """Extract transcript from video file with progress tracking.
        
        Args:
            video_path: Path to the video file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Transcript text or empty string if extraction fails
        """
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return ""
        
        try:
            # Extract audio if needed
            audio_path = self._extract_audio(video_path)
            if not audio_path:
                return ""
            
            # faster-whisper transcription with chunked processing
            segments_list = []
            segments, info = self.model.transcribe(
                audio_path,
                beam_size=5,
                language="en",
                condition_on_previous_text=False
            )
            
            # Get total duration for progress calculation
            total_duration = info.duration if hasattr(info, 'duration') else 0
            current_time = 0.0
            
            # Process segments incrementally with progress updates
            for i, segment in enumerate(segments):
                # Check shutdown every 10 segments
                if i % 10 == 0 and self.shutdown_event and self.shutdown_event.is_set():
                    print(f"Transcription interrupted at segment {i} due to shutdown")
                    break
                
                segments_list.append(segment.text.strip())
                
                # Update progress based on segment end time
                if progress_callback and total_duration > 0 and hasattr(segment, 'end'):
                    current_time = segment.end
                    percent_complete = (current_time / total_duration) * 100
                    # Call with percent, current_time, total_duration
                    progress_callback(percent_complete, current_time, total_duration)
            
            # Ensure we report 100% completion
            if progress_callback and total_duration > 0:
                progress_callback(100.0, total_duration, total_duration)
            
            # Combine segments into full transcript
            transcript = " ".join(segments_list)
            
            # Cleanup audio file
            if audio_path != video_path and os.path.exists(audio_path):
                os.remove(audio_path)
            
            return transcript.strip()
            
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def _extract_audio(self, video_path: str) -> Optional[str]:
        """Extract audio from video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Path to extracted audio file or None if extraction fails
        """
        # Check if input is already audio
        if video_path.endswith(('.mp3', '.wav', '.m4a', '.aac')):
            return video_path
        
        audio_path = video_path.replace('.mp4', '.m4a')
        
        try:
            # Use ffmpeg to extract audio
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # No video
                '-acodec', 'copy',  # Copy audio codec
                '-y',  # Overwrite output
                audio_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                return audio_path
            
            # Fallback: try different codec
            cmd[4] = 'libmp3lame'  # Use MP3 codec
            audio_path = video_path.replace('.mp4', '.mp3')
            cmd[-1] = audio_path
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                return audio_path
            
        except subprocess.TimeoutExpired:
            print("Audio extraction timed out")
        except Exception as e:
            print(f"Audio extraction error: {e}")
        
        return None
    
    def cleanup(self):
        """Clean up resources."""
        if self.model:
            del self.model
            self.model = None
        ResourceManager.cleanup_memory()