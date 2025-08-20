"""Transcript extraction using Whisper AI."""

import os
import subprocess
from typing import Optional, Tuple
from faster_whisper import WhisperModel
from src.resource_manager import ResourceManager

class TranscriptExtractor:
    """Handles video transcription using Whisper AI."""
    
    def __init__(self, model_size: str = "base", device: str = "auto"):
        """Initialize Whisper model.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to use (auto, cuda, cpu)
        """
        self.model_size = model_size
        self.device = self._determine_device(device)
        self.model = None
        self._load_model()
    
    def _determine_device(self, device: str) -> str:
        """Determine the best device for Whisper."""
        if device != "auto":
            return device
        
        # Check for CUDA availability
        if ResourceManager.ensure_cuda_available():
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except ImportError:
                pass
        
        return "cpu"
    
    def _load_model(self):
        """Load Whisper model with appropriate settings."""
        compute_type = "float16" if self.device == "cuda" else "int8"
        
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type
            )
            print(f"Loaded Whisper model: {self.model_size} on {self.device}")
        except Exception as e:
            print(f"Failed to load Whisper model, falling back to CPU: {e}")
            self.device = "cpu"
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"
            )
    
    def extract_transcript(self, video_path: str) -> str:
        """Extract transcript from video file.
        
        Args:
            video_path: Path to the video file
            
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
            
            # Transcribe audio
            segments, info = self.model.transcribe(
                audio_path,
                beam_size=5,
                language="en",
                condition_on_previous_text=False
            )
            
            # Combine segments into full transcript
            transcript = " ".join([segment.text.strip() for segment in segments])
            
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