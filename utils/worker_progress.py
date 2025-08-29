"""
Progress tracking utilities for worker processes.
Provides stage-based progress calculation and update message formatting.
"""

from typing import Dict, Optional, Tuple, Any
from multiprocessing import Queue


class WorkerProgress:
    """Helper class for tracking and reporting worker progress"""
    
    # Processing stages with their weight percentages
    STAGES = [
        ('validating', 5),
        ('downloading', 25),
        ('metadata', 10),
        ('transcribing', 35),
        ('context', 10),
        ('comments', 10),
        ('saving', 5),
    ]
    
    def __init__(self, worker_id: int, display_queue: Queue, total_urls: int):
        """
        Initialize progress tracker.
        
        Args:
            worker_id: ID of this worker
            display_queue: Queue for sending display updates
            total_urls: Total number of URLs assigned to this worker
        """
        self.worker_id = worker_id
        self.display_queue = display_queue
        self.total_urls = total_urls
        self.completed_urls = 0
        self.current_url = None
        self.current_stage = None
        self.current_stage_progress = 0
    
    def calculate_url_progress(self, stage: str, stage_progress: float = 0) -> float:
        """
        Calculate overall progress for current URL.
        
        Args:
            stage: Current stage name
            stage_progress: Progress within current stage (0-100)
        
        Returns:
            Overall URL progress (0-100)
        """
        completed_weight = 0
        
        for stage_name, weight in self.STAGES:
            if stage_name == stage:
                # Add partial progress of current stage
                return completed_weight + (stage_progress * weight / 100)
            else:
                # This stage is complete
                completed_weight += weight
        
        return min(100, completed_weight)
    
    def send_status(self, status: str):
        """Send status update to display"""
        self.display_queue.put({
            'type': 'status',
            'worker_id': self.worker_id,
            'status': status
        })
    
    def send_progress(self, stage: str, stage_progress: float = 0, 
                     stage_details: Optional[str] = None):
        """
        Send progress update to display.
        
        Args:
            stage: Current stage name
            stage_progress: Progress within stage (0-100)
            stage_details: Optional details about current operation
        """
        self.current_stage = stage
        self.current_stage_progress = stage_progress
        
        overall_progress = self.calculate_url_progress(stage, stage_progress)
        
        update = {
            'type': 'progress',
            'worker_id': self.worker_id,
            'progress': overall_progress,
            'completed_urls': self.completed_urls,
            'stage': self.get_stage_display_name(stage),
        }
        
        if stage_details:
            update['stage_details'] = stage_details
        
        self.display_queue.put(update)
    
    def send_log(self, message: str, level: str = 'info'):
        """
        Send log message to display.
        
        Args:
            message: Log message
            level: Log level (info, success, error, progress)
        """
        self.display_queue.put({
            'type': 'log',
            'worker_id': self.worker_id,
            'message': message,
            'level': level
        })
    
    def send_error(self, error: str, traceback: Optional[str] = None):
        """Send error message to display"""
        update = {
            'type': 'error',
            'worker_id': self.worker_id,
            'error': error
        }
        if traceback:
            update['traceback'] = traceback
        
        self.display_queue.put(update)
    
    def complete_url(self):
        """Mark current URL as completed"""
        self.completed_urls += 1
        self.display_queue.put({
            'type': 'complete',
            'worker_id': self.worker_id,
            'completed_urls': self.completed_urls
        })
        self.current_url = None
        self.current_stage = None
        self.current_stage_progress = 0
    
    def get_stage_display_name(self, stage: str) -> str:
        """Get display-friendly name for stage"""
        stage_names = {
            'validating': 'Validating URL',
            'downloading': 'Downloading video',
            'metadata': 'Extracting metadata',
            'transcribing': 'Transcribing audio',
            'context': 'Identifying context',
            'comments': 'Fetching comments',
            'saving': 'Saving to JSON'
        }
        return stage_names.get(stage, stage.capitalize())
    
    # Convenience methods for common operations
    
    def start_url(self, url: str):
        """Start processing a new URL"""
        self.current_url = url
        self.display_queue.put({
            'type': 'start',
            'worker_id': self.worker_id,
            'url': url
        })
        self.send_progress('validating', 0)
        self.send_log('URL validation started', 'info')
    
    def start_download(self):
        """Start download stage"""
        self.send_progress('downloading', 0)
        self.send_log('Download started', 'info')
    
    def update_download(self, bytes_downloaded: int, total_bytes: int):
        """Update download progress"""
        if total_bytes > 0:
            progress = (bytes_downloaded / total_bytes) * 100
            mb_downloaded = bytes_downloaded / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            
            self.send_progress(
                'downloading', 
                progress,
                f"Downloaded {mb_downloaded:.1f}/{mb_total:.1f} MB"
            )
    
    def complete_download(self, file_size_mb: float, duration: float):
        """Mark download as complete"""
        self.send_progress('downloading', 100)
        self.send_log(
            f"Downloaded {file_size_mb:.1f} MB in {duration:.1f}s",
            'success'
        )
    
    def start_metadata_extraction(self):
        """Start metadata extraction"""
        self.send_progress('metadata', 0)
        self.send_log('Extracting metadata', 'progress')
    
    def complete_metadata(self, likes: int, comments: int):
        """Complete metadata extraction"""
        self.send_progress('metadata', 100)
        self.send_log(
            f"Extracted metadata ({likes:,} likes, {comments:,} comments)",
            'success'
        )
    
    def start_transcription(self, model: str = 'base'):
        """Start transcription"""
        self._last_logged_percent = 0  # Reset for new transcription
        self.send_progress('transcribing', 0)
        self.send_log(f'Starting transcription with Whisper {model}', 'progress')
    
    def update_transcription(self, current_time: float, total_time: float):
        """Update transcription progress"""
        if total_time > 0:
            progress = (current_time / total_time) * 100
            self.send_progress(
                'transcribing',
                progress,
                f"Progress: {current_time:.0f}/{total_time:.0f} seconds"
            )
            
            # Also send console log every 10% progress
            progress_int = int(progress)
            if progress_int > 0 and progress_int % 10 == 0:
                # Check if we haven't already logged this percentage
                if not hasattr(self, '_last_logged_percent') or self._last_logged_percent < progress_int:
                    self._last_logged_percent = progress_int
                    self.send_log(
                        f"Transcribing: {progress_int}% ({current_time:.0f}/{total_time:.0f}s)",
                        'progress'
                    )
    
    def complete_transcription(self, duration: float):
        """Complete transcription"""
        self.send_progress('transcribing', 100)
        self.send_log(
            f"Transcription complete ({duration:.0f}s audio)",
            'success'
        )
    
    def skip_transcription(self, reason: str = "Whisper not enabled"):
        """Skip transcription stage"""
        self.send_log(f"Skipping transcription: {reason}", 'info')
    
    def start_context(self):
        """Start context identification"""
        self.send_progress('context', 0)
        self.send_log('Identifying context', 'progress')
    
    def complete_context(self, categories: int = 0):
        """Complete context identification"""
        self.send_progress('context', 100)
        if categories > 0:
            self.send_log(f"Identified {categories} categories", 'success')
        else:
            self.send_log('Context identification complete', 'success')
    
    def skip_context(self, reason: str = "Context identification not enabled"):
        """Skip context identification stage"""
        self.send_log(f"Skipping context: {reason}", 'info')
    
    def start_comments(self):
        """Start comment extraction"""
        self.send_progress('comments', 0)
        self.send_log('Fetching comments', 'progress')
    
    def complete_comments(self, count: int):
        """Complete comment extraction"""
        self.send_progress('comments', 100)
        self.send_log(f"Fetched {count} comments", 'success')
    
    def skip_comments(self, reason: str = "No MS_TOKEN"):
        """Skip comment extraction"""
        self.send_log(f"Skipping comments: {reason}", 'info')
    
    def start_saving(self):
        """Start saving to database"""
        self.send_progress('saving', 0)
        self.send_log('Saving to database', 'progress')
    
    def complete_saving(self):
        """Complete saving"""
        self.send_progress('saving', 100)
        self.send_log('Saved successfully', 'success')
    
    def report_error(self, stage: str, error: str):
        """Report an error during processing"""
        self.send_log(f"Error in {stage}: {error}", 'error')
        self.send_error(error)
    
    def report_retry(self, attempt: int, max_attempts: int, reason: str):
        """Report a retry attempt"""
        self.send_log(
            f"Retry {attempt}/{max_attempts}: {reason}",
            'progress'
        )


class ProgressCalculator:
    """Static utility for progress calculations"""
    
    @staticmethod
    def get_stage_weight(stage: str) -> int:
        """Get the weight of a specific stage"""
        for stage_name, weight in WorkerProgress.STAGES:
            if stage_name == stage:
                return weight
        return 0
    
    @staticmethod
    def calculate_overall_progress(completed_urls: int, total_urls: int,
                                  current_url_progress: float = 0) -> float:
        """
        Calculate overall worker progress.
        
        Args:
            completed_urls: Number of completed URLs
            total_urls: Total URLs to process
            current_url_progress: Progress on current URL (0-100)
        
        Returns:
            Overall progress percentage
        """
        if total_urls == 0:
            return 0
        
        completed_weight = (completed_urls / total_urls) * 100
        current_weight = (current_url_progress / total_urls) if total_urls > 0 else 0
        
        return min(100, completed_weight + current_weight)