"""Services for Django server to interact with collector.py"""

import subprocess
import os
import json
import logging
from typing import List, Optional
from django.conf import settings
from .models import QueuedURL

logger = logging.getLogger(__name__)


class CollectorService:
    """Service to manage collector.py execution"""
    
    @staticmethod
    def queue_url(url: str) -> QueuedURL:
        """
        Queue a URL for processing.
        
        Args:
            url: TikTok URL to process
            
        Returns:
            QueuedURL model instance
        """
        queued_url, created = QueuedURL.objects.get_or_create(
            url=url,
            defaults={'status': 'pending'}
        )
        return queued_url
    
    @staticmethod
    def queue_multiple_urls(urls: List[str]) -> List[QueuedURL]:
        """
        Queue multiple URLs for processing.
        
        Args:
            urls: List of TikTok URLs to process
            
        Returns:
            List of QueuedURL model instances
        """
        queued_urls = []
        for url in urls:
            queued_url = CollectorService.queue_url(url)
            queued_urls.append(queued_url)
        return queued_urls
    
    @staticmethod
    def get_pending_urls(limit: Optional[int] = None) -> List[str]:
        """
        Get pending URLs from queue.
        
        Args:
            limit: Maximum number of URLs to return
            
        Returns:
            List of pending URLs
        """
        query = QueuedURL.objects.filter(status='pending').order_by('added_at')
        if limit:
            query = query[:limit]
        return list(query.values_list('url', flat=True))
    
    @staticmethod
    def trigger_processing(urls: Optional[List[str]] = None, workers: int = 1) -> subprocess.Popen:
        """
        Trigger collector.py to process URLs.
        
        Args:
            urls: Specific URLs to process (if None, processes all pending)
            workers: Number of worker processes
            
        Returns:
            Subprocess instance
        """
        # Get URLs if not provided
        if urls is None:
            urls = CollectorService.get_pending_urls()
        
        if not urls:
            logger.info("No URLs to process")
            return None
        
        # Log collector start
        logger.info(f"🚀 Starting collector.py with {len(urls)} URL(s) and {workers} worker(s)")
        logger.info(f"Processing URLs: {', '.join(urls[:3])}{'...' if len(urls) > 3 else ''}")
        
        # Mark URLs as processing
        QueuedURL.objects.filter(url__in=urls).update(status='processing')
        
        # Build command
        cmd = [
            'python', 'collector.py',
            '--url', ','.join(urls),
            '--workers', str(workers)
        ]
        
        # Add whisper and mp3 flags if configured
        if getattr(settings, 'TIKTOK_USE_WHISPER', True):
            cmd.append('--whisper')
        if getattr(settings, 'TIKTOK_AUDIO_ONLY', True):
            cmd.append('--mp3')
        
        # Log full command
        logger.info(f"Command: {' '.join(cmd)}")
        
        # Since database is enabled, don't write to JSON
        # The collector will read from config.toml and see database.enabled = true
        
        # Run collector.py in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=settings.BASE_DIR  # Run from project root
        )
        
        logger.info(f"Collector started with PID: {process.pid}")
        
        return process
    
    @staticmethod
    def batch_process(batch_size: int = 10, workers: int = 4) -> Optional[subprocess.Popen]:
        """
        Process a batch of pending URLs.
        
        Args:
            batch_size: Number of URLs to process
            workers: Number of worker processes
            
        Returns:
            Subprocess instance or None if no URLs
        """
        urls = CollectorService.get_pending_urls(limit=batch_size)
        if urls:
            return CollectorService.trigger_processing(urls, workers)
        return None
    
    @staticmethod
    def mark_completed(url: str):
        """Mark a URL as completed"""
        from django.utils import timezone
        QueuedURL.objects.filter(url=url).update(
            status='completed',
            processed_at=timezone.now()
        )
    
    @staticmethod
    def mark_failed(url: str, error_message: str):
        """Mark a URL as failed with error message"""
        queued_url = QueuedURL.objects.get(url=url)
        queued_url.status = 'failed'
        queued_url.error_message = error_message
        queued_url.retry_count += 1
        queued_url.save()


class MLService:
    """Service to interact with ML API"""
    
    def __init__(self):
        # Import the predictor directly instead of using HTTP
        from ml.train_ml import TikTokPerformancePredictor
        import os
        
        self.predictor = None
        self.load_model()
    
    def load_model(self):
        """Load the ML model"""
        from ml.train_ml import TikTokPerformancePredictor
        
        # Look for model file
        possible_paths = [
            "ml/models/snoo.pkl",
            "models/snoo.pkl"
        ]
        
        model_path = None
        for path in possible_paths:
            full_path = os.path.join(settings.BASE_DIR, path)
            if os.path.exists(full_path):
                model_path = full_path
                break
        
        if model_path:
            self.predictor = TikTokPerformancePredictor()
            self.predictor.load_model(model_path)
    
    def predict(self, text: str) -> dict:
        """
        Get prediction for text.
        
        Args:
            text: Transcript text to analyze
            
        Returns:
            Dictionary with score and confidence
        """
        if not self.predictor:
            return {'error': 'Model not loaded'}
        
        try:
            score = self.predictor.predict_score(text.strip())
            
            # Determine confidence
            text_length = len(text.split())
            if text_length < 10:
                confidence = "low"
            elif text_length < 50:
                confidence = "medium"
            else:
                confidence = "high"
            
            return {
                'score': round(score, 1),
                'confidence': confidence,
                'text_length': text_length
            }
        except Exception as e:
            return {'error': str(e)}