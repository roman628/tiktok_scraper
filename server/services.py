"""Services for Django server to interact with collector.py"""

import subprocess
import os
import json
import logging
import psutil
from typing import List, Optional
from django.conf import settings
from .models import QueuedURL

logger = logging.getLogger(__name__)


class CollectorService:
    """Service to manage collector.py execution"""
    
    _collector_process = None  # Track the running collector process
    
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
    def check_collector_status():
        """Check and log collector status changes"""
        # First check process status
        if CollectorService._collector_process is not None:
            poll_result = CollectorService._collector_process.poll()
            if poll_result is not None:
                # Process has finished
                logger.info(f"✅ Collector process (PID: {CollectorService._collector_process.pid}) has finished with exit code: {poll_result}")
                CollectorService._collector_process = None
                
                # Update database status
                try:
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE collector_status 
                            SET status = 'stopped', stopped_at = NOW()
                            WHERE id = 1
                        """)
                except Exception as e:
                    logger.warning(f"Could not update collector status in database: {e}")
                
                return False
        return CollectorService.is_collector_running()
    
    @staticmethod
    def is_collector_running() -> bool:
        """
        Check if collector.py is currently running.
        First checks tracked process, then verifies via psutil, then checks database.
        
        Returns:
            True if collector is running, False otherwise
        """
        # First check if we have a tracked process
        if CollectorService._collector_process is not None:
            # Check if the tracked process is still alive
            poll_result = CollectorService._collector_process.poll()
            if poll_result is not None:
                # Process has terminated
                logger.debug(f"Tracked collector process (PID: {CollectorService._collector_process.pid}) has terminated")
                CollectorService._collector_process = None
                # Update database
                try:
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE collector_status 
                            SET status = 'stopped', stopped_at = NOW()
                            WHERE id = 1
                        """)
                except Exception as e:
                    logger.warning(f"Could not update collector status in database: {e}")
            else:
                # Process still running according to poll(), verify with psutil
                try:
                    if psutil.pid_exists(CollectorService._collector_process.pid):
                        process = psutil.Process(CollectorService._collector_process.pid)
                        cmdline = ' '.join(process.cmdline())
                        if 'collector.py' in cmdline:
                            return True
                        else:
                            logger.warning(f"Process {CollectorService._collector_process.pid} exists but is not collector.py")
                            CollectorService._collector_process = None
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"Process check failed: {e}")
                    CollectorService._collector_process = None
        
        # No tracked process or it's dead, check database for other instances
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT status, pid, last_activity 
                    FROM collector_status 
                    WHERE id = 1
                """)
                result = cursor.fetchone()
                if result and result[0] == 'running':
                    pid = result[1]
                    if pid:
                        # Verify the PID is actually running collector.py
                        try:
                            if psutil.pid_exists(pid):
                                process = psutil.Process(pid)
                                cmdline = ' '.join(process.cmdline())
                                if 'collector.py' in cmdline:
                                    logger.debug(f"Found running collector from database (PID: {pid})")
                                    return True
                                else:
                                    logger.debug(f"PID {pid} exists but is not running collector.py")
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                            logger.debug(f"Process {pid} check failed: {e}")
                    
                    # PID not alive or not collector.py, update database
                    logger.debug("Updating database: collector no longer running")
                    cursor.execute("""
                        UPDATE collector_status 
                        SET status = 'stopped', stopped_at = NOW()
                        WHERE id = 1
                    """)
        except Exception as e:
            logger.warning(f"Could not check database collector status: {e}")
        
        return False
    
    @staticmethod
    def trigger_processing(urls: Optional[List[str]] = None, workers: int = None) -> subprocess.Popen:
        """
        Trigger collector.py to process URLs from database queue.
        Only starts if not already running.
        
        Args:
            urls: Not used - kept for compatibility
            workers: Not used - uses config.toml settings
            
        Returns:
            Subprocess instance or existing process
        """
        # Perform a fresh check if collector is actually running
        if CollectorService.is_collector_running():
            # Check pending URLs to give accurate feedback
            pending_count = QueuedURL.objects.filter(status='pending').count()
            if pending_count > 0:
                logger.info("📋 Collector already running - %d URL(s) queued and will be processed", pending_count)
            else:
                logger.info("📋 Collector already running - URL will be processed in next cycle")
            return CollectorService._collector_process
        
        # Check if there are pending URLs
        pending_count = QueuedURL.objects.filter(status='pending').count()
        if pending_count == 0:
            logger.info("No pending URLs to process")
            return None
        
        # Log collector start
        logger.info(f"🚀 Starting collector.py in continuous mode to process queue")
        logger.info(f"📊 Current queue: {pending_count} pending URL(s)")
        
        # Build command - no arguments, uses config.toml and database queue
        cmd = ['python', 'collector.py']
        
        # Log full command
        logger.info(f"Command: {' '.join(cmd)}")
        
        # Run collector.py in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=settings.BASE_DIR  # Run from project root
        )
        
        # Store the process reference
        CollectorService._collector_process = process
        
        logger.info(f"Collector started with PID: {process.pid}")
        logger.info("Collector will continuously process the queue until idle")
        
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
    def get_collector_stats() -> dict:
        """Get collector statistics from database"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT status, started_at, stopped_at, last_activity, urls_processed, pid
                    FROM collector_status
                    WHERE id = 1
                """)
                result = cursor.fetchone()
                if result:
                    return {
                        'status': result[0],
                        'started_at': result[1],
                        'stopped_at': result[2],
                        'last_activity': result[3],
                        'urls_processed': result[4],
                        'pid': result[5]
                    }
        except Exception as e:
            logger.warning(f"Could not get collector stats: {e}")
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