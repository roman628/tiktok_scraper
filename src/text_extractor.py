"""
OCR text extraction from video frames.
Extracts on-screen text from TikTok videos (captions, overlays, etc.)
"""

import cv2
import numpy as np
from pathlib import Path
import logging
import subprocess
import sys
from typing import Optional, Tuple, List

# Try to import easyocr, install if needed
try:
    import easyocr
except ImportError:
    print("Installing EasyOCR for text extraction...")
    subprocess.run([sys.executable, "-m", "pip", "install", "easyocr", "-q"])
    import easyocr

logger = logging.getLogger(__name__)

class TextExtractor:
    """Extract on-screen text from video frames using OCR."""
    
    def __init__(self):
        """Initialize the text extractor with EasyOCR."""
        self.reader = None
        self.initialized = False
        
    def _initialize_reader(self):
        """Lazy initialization of EasyOCR reader."""
        if not self.initialized:
            try:
                # Check for GPU availability
                import torch
                use_gpu = torch.cuda.is_available() or torch.backends.mps.is_available()
                
                # Use English reader with GPU if available
                self.reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False)
                self.initialized = True
                device_type = "GPU" if use_gpu else "CPU"
                logger.info(f"EasyOCR reader initialized successfully using {device_type}")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                raise
    
    def extract_frame(self, video_path: str, frame_position: float = 0.0) -> Optional[np.ndarray]:
        """
        Extract a single frame from video.
        
        Args:
            video_path: Path to video file
            frame_position: Position in video (0.0 = start, 0.5 = middle, 1.0 = end)
            
        Returns:
            Frame as numpy array or None if extraction fails
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            # Get total frames
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames == 0:
                logger.warning(f"Could not read frames from {video_path}")
                return None
            
            # Calculate target frame
            target_frame = int(total_frames * min(max(frame_position, 0.0), 1.0))
            
            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            # Read frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return frame
            else:
                logger.warning(f"Could not extract frame at position {frame_position} from {video_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting frame from {video_path}: {e}")
            return None
    
    def extract_text_from_frame(self, frame: np.ndarray, confidence_threshold: float = 0.5) -> Tuple[str, List[dict]]:
        """
        Extract text from a single frame using OCR.
        
        Args:
            frame: Frame as numpy array (BGR format from OpenCV)
            confidence_threshold: Minimum confidence for text detection
            
        Returns:
            Tuple of (combined_text, text_regions)
        """
        if not self.initialized:
            self._initialize_reader()
        
        try:
            # Convert BGR to RGB for EasyOCR
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Run OCR
            results = self.reader.readtext(frame_rgb)
            
            # Filter by confidence and extract text
            text_regions = []
            text_parts = []
            
            for (bbox, text, confidence) in results:
                if confidence >= confidence_threshold:
                    text_regions.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': bbox
                    })
                    text_parts.append(text)
            
            # Combine all text with spaces
            combined_text = ' '.join(text_parts) if text_parts else ''
            
            return combined_text, text_regions
            
        except Exception as e:
            logger.error(f"Error during OCR: {e}")
            return '', []
    
    def extract_text_from_video(self, video_path: str, 
                               frame_positions: List[float] = None,
                               confidence_threshold: float = 0.5) -> dict:
        """
        Extract text from video frames.
        
        Args:
            video_path: Path to video file
            frame_positions: List of positions to sample (default: [0.0] for first frame ONLY)
            confidence_threshold: Minimum confidence for text detection
            
        Returns:
            Dictionary with extracted text and metadata
        """
        if frame_positions is None:
            # Default: ONLY first frame (where most overlays are)
            frame_positions = [0.0]
        
        all_texts = []
        all_regions = []
        has_text = False
        
        for position in frame_positions:
            # Extract frame
            frame = self.extract_frame(video_path, position)
            if frame is None:
                continue
            
            # Extract text
            text, regions = self.extract_text_from_frame(frame, confidence_threshold)
            
            if text:
                all_texts.append(text)
                all_regions.extend(regions)
                has_text = True
        
        # Combine unique texts (avoid duplicates from multiple frames)
        unique_texts = []
        seen = set()
        for text in all_texts:
            if text and text not in seen:
                unique_texts.append(text)
                seen.add(text)
        
        combined_text = ' '.join(unique_texts)
        
        # Calculate average confidence
        avg_confidence = 0.0
        if all_regions:
            avg_confidence = sum(r['confidence'] for r in all_regions) / len(all_regions)
        
        return {
            'onscreen_text': combined_text,
            'has_text_overlay': has_text,
            'confidence': avg_confidence,
            'num_text_regions': len(all_regions),
            'frame_positions_checked': frame_positions
        }
    
    def extract_text_quick(self, video_path: str) -> Tuple[str, bool]:
        """
        Quick text extraction for integration into collector.py.
        Only checks first frame for speed.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (text, has_text_overlay)
        """
        result = self.extract_text_from_video(
            video_path, 
            frame_positions=[0.0],  # Just first frame
            confidence_threshold=0.6  # Higher threshold for speed/accuracy
        )
        
        return result['onscreen_text'], result['has_text_overlay']


# Singleton instance for reuse
_text_extractor = None

def get_text_extractor() -> TextExtractor:
    """Get or create singleton TextExtractor instance."""
    global _text_extractor
    if _text_extractor is None:
        _text_extractor = TextExtractor()
    return _text_extractor