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

from .models import QueuedURL, Video
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
            
            # Trigger processing in background
            CollectorService.trigger_processing([url])
            
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
        
        # Trigger batch processing
        workers = request.data.get('workers', 4)
        CollectorService.trigger_processing(urls, workers)
        
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
        
        return Response({
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'total': pending + processing + completed + failed
        })


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
