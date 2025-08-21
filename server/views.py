from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
import logging
import os
import subprocess
from datetime import datetime

from .models import QueuedURL, Video, CollectorRun, MLTrainingRun
from .services import CollectorService, MLService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class URLSubmitView(View):
    """API endpoint to submit URLs for processing (replaces url_server.py)"""
    
    def post(self, request):
        """Submit a single URL for processing"""
        try:
            data = json.loads(request.body)
            url = data.get('url')
            
            if not url:
                return JsonResponse({'error': 'URL is required'}, status=400)
            
            logger.info(f"📥 Received URL submission: {url}")
            
            # Queue the URL
            queued_url = CollectorService.queue_url(url)
            
            # Trigger processing if collector not already running
            CollectorService.trigger_processing()
            
            return JsonResponse({
                'status': 'queued',
                'url': url,
                'id': queued_url.id
            })
        except Exception as e:
            logger.error(f"Error processing URL submission: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class BatchURLSubmitView(APIView):
    """Submit multiple URLs for processing"""
    
    def post(self, request):
        """Submit batch of URLs"""
        urls = request.data.get('urls', [])
        
        if not urls:
            return Response({'error': 'URLs list is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"📥 Received batch URL submission: {len(urls)} URLs")
        
        # Queue all URLs
        queued_urls = CollectorService.queue_multiple_urls(urls)
        
        # Trigger processing if collector not already running
        CollectorService.trigger_processing()
        
        return Response({
            'status': 'queued',
            'count': len(queued_urls),
            'ids': [q.id for q in queued_urls]
        })


class ProcessingStatusView(APIView):
    """Check processing status of URLs"""
    
    def get(self, request):
        """Get overall processing status"""
        pending = QueuedURL.objects.filter(status='pending').count()
        processing = QueuedURL.objects.filter(status='processing').count()
        completed = QueuedURL.objects.filter(status='completed').count()
        failed = QueuedURL.objects.filter(status='failed').count()
        
        # Check if collector is running
        collector_running = CollectorService.is_collector_running()
        
        # Get collector statistics
        collector_stats = CollectorService.get_collector_stats()
        
        response_data = {
            'collector_running': collector_running,
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'total': pending + processing + completed + failed
        }
        
        # Add collector stats if available
        if collector_stats:
            response_data['collector'] = {
                'status': collector_stats['status'],
                'started_at': collector_stats['started_at'],
                'last_activity': collector_stats['last_activity'],
                'urls_processed_session': collector_stats['urls_processed'],
                'pid': collector_stats['pid']
            }
        
        return Response(response_data)


class VideoListView(APIView):
    """List processed videos"""
    
    def get(self, request):
        """Get list of videos"""
        limit = request.GET.get('limit', 100)
        videos = Video.objects.all().order_by('-created_at')[:limit]
        
        video_data = []
        for video in videos:
            video_data.append({
                'id': video.id,
                'video_id': video.video_id,
                'url': video.url,
                'title': video.title,
                'uploader': video.uploader,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'created_at': video.created_at
            })
        
        return Response({
            'count': len(video_data),
            'videos': video_data
        })


class MLPredictView(APIView):
    """ML prediction endpoint (integrates ml/api.py)"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ml_service = MLService()
    
    def post(self, request):
        """Get performance prediction for text"""
        text = request.data.get('text')
        
        if not text:
            return Response({'error': 'Text is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = self.ml_service.predict(text)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(result)


class HealthCheckView(APIView):
    """Health check endpoint"""
    
    def get(self, request):
        """Check if server is healthy"""
        try:
            # Check database connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return Response({
                'status': 'healthy',
                'database': 'connected'
            })
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'error': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@method_decorator(csrf_exempt, name='dispatch')
class UpdateTokenView(View):
    """Update MS_TOKEN in config.toml"""
    
    def post(self, request):
        """Update the MS_TOKEN"""
        try:
            data = json.loads(request.body)
            ms_token = data.get('ms_token')
            
            if not ms_token:
                return JsonResponse({'error': 'MS_TOKEN is required'}, status=400)
            
            # Update config.toml file
            import os
            from django.conf import settings
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            import toml
            
            config_path = os.path.join(settings.BASE_DIR, 'config.toml')
            
            # Read existing config
            if os.path.exists(config_path):
                with open(config_path, 'rb') as f:
                    config = tomllib.load(f)
            else:
                config = {}
            
            # Update MS_TOKEN
            if 'tiktok' not in config:
                config['tiktok'] = {}
            config['tiktok']['ms_token'] = ms_token
            
            # Write back to file
            with open(config_path, 'w') as f:
                toml.dump(config, f)
            
            print(f"MS_TOKEN updated in config.toml: {ms_token[:20]}...")
            
            return JsonResponse({
                'success': True,
                'message': f'MS_TOKEN updated: {ms_token[:20]}...'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class CollectorCompleteView(View):
    """API endpoint to notify when collector finishes processing"""
    
    def post(self, request):
        """Collector completion notification"""
        try:
            data = json.loads(request.body)
            urls_processed = data.get('urls_processed', 0)
            started_at = data.get('started_at')
            stopped_at = data.get('stopped_at', datetime.now().isoformat())
            reason = data.get('reason', 'idle_timeout')
            
            # Log collector completion with clear visual indicator
            logger.info("=" * 60)
            logger.info("🎉 COLLECTOR COMPLETED PROCESSING")
            logger.info("=" * 60)
            logger.info(f"📊 Total URLs Processed: {urls_processed}")
            logger.info(f"⏱️  Started: {started_at}")
            logger.info(f"⏱️  Stopped: {stopped_at}")
            logger.info(f"📝 Reason: {reason}")
            
            # Check remaining queue
            pending_count = QueuedURL.objects.filter(status='pending').count()
            if pending_count > 0:
                logger.info(f"⚠️  {pending_count} URLs still pending in queue")
            else:
                logger.info("✅ All URLs in queue have been processed!")
            
            logger.info("=" * 60)
            
            # Update collector status in services
            CollectorService._collector_process = None
            
            return JsonResponse({
                'status': 'acknowledged',
                'pending_urls': pending_count
            })
        except Exception as e:
            logger.error(f"Error processing collector completion: {e}")
            return JsonResponse({'error': str(e)}, status=500)


def dashboard_view(request):
    """Dashboard view showing database statistics"""
    
    # Check if collector is running
    collector_running = False
    try:
        # Check if collector.py process is running
        result = subprocess.run(['pgrep', '-f', 'collector.py'], capture_output=True, text=True)
        collector_running = bool(result.stdout.strip())
    except:
        pass
    
    # Get last collector run
    last_collector_run = CollectorRun.objects.filter(status__in=['completed', 'failed', 'stopped']).first()
    last_collector_date = last_collector_run.ended_at if last_collector_run else None
    
    # Get last ML training run
    last_ml_run = MLTrainingRun.objects.first()
    last_ml_date = last_ml_run.trained_at if last_ml_run else None
    
    # Get video count
    video_count = Video.objects.count()
    
    # Get URL count
    url_count = QueuedURL.objects.count()
    
    # Get additional statistics
    pending_urls = QueuedURL.objects.filter(status='pending').count()
    completed_urls = QueuedURL.objects.filter(status='completed').count()
    failed_urls = QueuedURL.objects.filter(status='failed').count()
    
    # Get recent videos
    recent_videos = Video.objects.order_by('-downloaded_at')[:10]
    
    context = {
        'collector_running': collector_running,
        'last_collector_date': last_collector_date,
        'last_ml_date': last_ml_date,
        'video_count': video_count,
        'url_count': url_count,
        'pending_urls': pending_urls,
        'completed_urls': completed_urls,
        'failed_urls': failed_urls,
        'recent_videos': recent_videos,
    }
    
    return render(request, 'dashboard.html', context)
