"""Services for Django server to interact with collector.py"""

import subprocess
import os
import sys
import json
import logging
import psutil
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
    def is_collector_running() -> bool:
        """
        Check if collector.py is currently running.
        In Docker, the collector service is always running as a separate container.
        
        Returns:
            True if collector service is healthy, False otherwise
        """
        # In Docker environment, collector runs as separate service
        if os.environ.get('DOCKER_CONTAINER'):
            # Could check container health via Docker API if needed
            # For now, assume it's running if we're in Docker
            return True
        
        # Local environment - check if collector.py process exists
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'collector.py' in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return False
    
    @staticmethod
    def trigger_processing():
        """
        In the new architecture, the collector runs continuously as a service.
        This method now just logs that URLs have been queued.
        """
        pending_count = QueuedURL.objects.filter(status='pending').count()
        
        if pending_count > 0:
            logger.info(f"📋 {pending_count} URL(s) queued for processing")
            logger.info("Collector service will process them automatically")
        else:
            logger.info("No pending URLs to process")
    
    @staticmethod
    def mark_completed(url: str):
        """Mark a URL as completed"""
        from django.utils import timezone
        QueuedURL.objects.filter(url=url).update(
            status='completed',
            processed_at=timezone.now()
        )
    
    @staticmethod
    def get_collector_stats() -> dict:
        """Get collector statistics"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get queue statistics
        pending = QueuedURL.objects.filter(status='pending').count()
        processing = QueuedURL.objects.filter(status='processing').count()
        completed_today = QueuedURL.objects.filter(
            status='completed',
            processed_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Try to get collector status from database
        try:
            from .models import CollectorStatus
            collector_status = CollectorStatus.objects.get(id=1)
            started_at = collector_status.started_at
            urls_processed = collector_status.urls_processed
            pid = collector_status.pid
        except:
            started_at = None
            urls_processed = 0
            pid = None

        return {
            'status': 'running' if CollectorService.is_collector_running() else 'stopped',
            'pending': pending,
            'processing': processing,
            'completed_today': completed_today,
            'last_activity': timezone.now(),
            'started_at': started_at,
            'urls_processed': urls_processed,
            'pid': pid
        }
    
    @staticmethod
    def get_latest_log():
        """Get the latest collector log file content"""
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        if not os.path.exists(log_dir):
            return None
            
        # Find the most recent collector log file
        log_files = [f for f in os.listdir(log_dir) if f.startswith('collector_') and f.endswith('.log')]
        if not log_files:
            return None
            
        latest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
        log_path = os.path.join(log_dir, latest_log)
        
        try:
            # Read last 100 lines
            with open(log_path, 'r') as f:
                lines = f.readlines()
                return ''.join(lines[-100:])
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return None
    
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