from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
import logging
import os
import subprocess
from datetime import datetime
import toml
import signal
import time

# Optional Docker import - won't break if not installed
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

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
        
        # Get last collector run
        last_collector_run = None
        last_run_urls_processed = 0
        try:
            # Get last two runs to calculate the difference
            last_runs = list(CollectorRun.objects.filter(status__in=['completed', 'stopped']).order_by('-ended_at')[:2])
            if last_runs:
                last_run = last_runs[0]
                last_collector_run = last_run.ended_at.isoformat() if last_run.ended_at else None
                
                # Calculate URLs processed in the last run (difference from previous)
                if len(last_runs) > 1:
                    previous_run = last_runs[1]
                    last_run_urls_processed = last_run.urls_processed - previous_run.urls_processed
                else:
                    # First run, all URLs are new
                    last_run_urls_processed = last_run.urls_processed
        except:
            pass
        
        # Get last ML training run and check if currently training
        last_ml_training = None
        ml_training_active = False
        ml_training_started_at = None
        
        try:
            # Check for active training
            active_training = MLTrainingRun.objects.filter(status='running').order_by('-trained_at').first()
            if active_training:
                ml_training_active = True
                ml_training_started_at = active_training.trained_at.isoformat() if active_training.trained_at else None
            
            # Get last completed training
            last_training = MLTrainingRun.objects.filter(status='completed').order_by('-trained_at').first()
            if last_training:
                last_ml_training = last_training.trained_at.isoformat() if last_training.trained_at else None
        except:
            pass
        
        # Get total video count
        from .models import Video
        total_videos = Video.objects.count()
        
        response_data = {
            'collector_running': collector_running,
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'total': pending + processing + completed + failed,
            'total_videos': total_videos,
            'last_collector_run': last_collector_run,
            'last_run_urls_processed': last_run_urls_processed,
            'last_ml_training': last_ml_training,
            'ml_training_active': ml_training_active,
            'ml_training_started_at': ml_training_started_at
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
            
            # Create CollectorRun record for dashboard
            try:
                from django.utils import timezone
                CollectorRun.objects.create(
                    started_at=datetime.fromisoformat(started_at) if started_at else timezone.now(),
                    ended_at=datetime.fromisoformat(stopped_at) if stopped_at else timezone.now(),
                    urls_processed=urls_processed,  # Store cumulative total for consistency
                    status='completed' if reason == 'completed' else 'stopped'
                )
                logger.info("✅ CollectorRun record created for dashboard")
            except Exception as e:
                logger.warning(f"Could not create CollectorRun record: {e}")
            
            # Check if auto ML training is enabled in config
            auto_train_enabled = False
            try:
                import tomllib
                config_path = os.path.join(settings.BASE_DIR, 'config.toml')
                if os.path.exists(config_path):
                    with open(config_path, 'rb') as f:
                        config = tomllib.load(f)
                        ml_config = config.get('ml', {})
                        auto_train_enabled = ml_config.get('auto_train_after_collection', False)
                        
                    if not auto_train_enabled:
                        logger.info("ℹ️  ML auto-training is disabled in config.toml")
                        logger.info("   To enable: set [ml] auto_train_after_collection = true")
            except Exception as e:
                logger.warning(f"Could not check auto-training config: {e}")
            
            # Trigger ML training if new data was processed AND auto-training is enabled
            if urls_processed > 0 and auto_train_enabled:
                try:
                    # Run ML training asynchronously
                    import subprocess
                    import threading
                    
                    def train_ml_async():
                        try:
                            logger.info("🧠 Starting ML model training after collector completion...")
                            
                            # First, run ETL to update gold layer features
                            from django.db import connection
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT etl_silver_to_gold();")
                                cursor.execute("SELECT refresh_ml_training_view();")
                            
                            # Then run ML training
                            # Use venv Python to ensure all dependencies are available
                            venv_python = os.path.join(settings.BASE_DIR, 'venv', 'bin', 'python')
                            result = subprocess.run(
                                [venv_python, 'ml/train_ml.py', 'train'],
                                capture_output=True,
                                text=True,
                                cwd=settings.BASE_DIR
                            )
                            
                            if result.returncode == 0:
                                logger.info("✅ ML model training completed successfully")
                                
                                # Update MLTrainingRun model
                                MLTrainingRun.objects.create(
                                    model_name='TikTokPerformancePredictor',
                                    model_version='1.0',
                                    training_samples=urls_processed,
                                    status='completed'
                                )
                            else:
                                logger.error(f"❌ ML training failed: {result.stderr}")
                                MLTrainingRun.objects.create(
                                    model_name='TikTokPerformancePredictor',
                                    model_version='1.0',
                                    training_samples=urls_processed,
                                    status='failed',
                                    notes=result.stderr[:500]  # Store first 500 chars of error
                                )
                        except Exception as e:
                            logger.error(f"❌ Error during ML training: {e}")
                    
                    # Start training in background thread
                    training_thread = threading.Thread(target=train_ml_async)
                    training_thread.daemon = True
                    training_thread.start()
                    
                    logger.info(f"🚀 ML training triggered for {urls_processed} new videos")
                    
                except Exception as e:
                    logger.warning(f"Could not trigger ML training: {e}")
            
            return JsonResponse({
                'status': 'acknowledged',
                'pending_urls': pending_count,
                'ml_training_triggered': urls_processed > 0 and auto_train_enabled,
                'ml_auto_train_enabled': auto_train_enabled
            })
        except Exception as e:
            logger.error(f"Error processing collector completion: {e}")
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MLTrainingStartView(View):
    """Signal that ML training has started"""
    
    def post(self, request):
        try:
            # Create or update MLTrainingRun record
            training_run = MLTrainingRun.objects.create(
                model_name='snoo',
                status='running',
                trained_at=datetime.now()
            )
            
            logger.info("🎯 ML training started signal received")
            
            return JsonResponse({
                'status': 'acknowledged',
                'training_id': training_run.id
            })
        except Exception as e:
            logger.error(f"Error processing ML start signal: {e}")
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MLTrainingEndView(View):
    """Signal that ML training has ended"""
    
    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
            metrics = data.get('metrics', {})
            test_predictions = data.get('test_predictions', [])
            
            # Get the most recent running training
            training_run = MLTrainingRun.objects.filter(status='running').order_by('-trained_at').first()
            
            if training_run:
                # Update with metrics
                training_run.status = 'completed'
                training_run.r2_score = metrics.get('r2_score')
                training_run.mae = metrics.get('mae')
                training_run.rmse = metrics.get('rmse')
                training_run.prediction_range = metrics.get('prediction_range')
                training_run.prediction_std = metrics.get('prediction_std')
                training_run.cv_mean = metrics.get('cv_mean')
                training_run.cv_std = metrics.get('cv_std')
                training_run.test_predictions = test_predictions
                
                # Calculate effectiveness score
                effectiveness = training_run.calculate_effectiveness()
                training_run.effectiveness_score = effectiveness
                
                training_run.save()
                logger.info(f"✅ ML training completed with metrics for training {training_run.id}")
            else:
                # Create a completed entry if no running one exists
                training_run = MLTrainingRun.objects.create(
                    model_name='snoo',
                    status='completed',
                    trained_at=datetime.now(),
                    r2_score=metrics.get('r2_score'),
                    mae=metrics.get('mae'),
                    rmse=metrics.get('rmse'),
                    prediction_range=metrics.get('prediction_range'),
                    prediction_std=metrics.get('prediction_std'),
                    cv_mean=metrics.get('cv_mean'),
                    cv_std=metrics.get('cv_std'),
                    test_predictions=test_predictions
                )
                effectiveness = training_run.calculate_effectiveness()
                training_run.effectiveness_score = effectiveness
                training_run.save()
                logger.info("✅ ML training completed with metrics (no prior start signal)")
            
            return JsonResponse({
                'status': 'acknowledged',
                'training_id': training_run.id if training_run else None
            })
        except Exception as e:
            logger.error(f"Error processing ML end signal: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class MLMetricsView(APIView):
    """Get current and historical ML metrics"""
    
    def get(self, request):
        try:
            # Get latest completed training run
            latest_run = MLTrainingRun.objects.filter(status='completed').order_by('-trained_at').first()
            
            if not latest_run:
                return Response({
                    'error': 'No completed training runs found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get previous run for comparison
            previous_run = MLTrainingRun.objects.filter(
                status='completed',
                trained_at__lt=latest_run.trained_at
            ).order_by('-trained_at').first()
            
            # Calculate percentage changes for all metrics
            change = None
            r2_change = None
            mae_change = None
            rmse_change = None
            
            if previous_run:
                if previous_run.effectiveness_score and latest_run.effectiveness_score:
                    change = ((latest_run.effectiveness_score - previous_run.effectiveness_score) / 
                             previous_run.effectiveness_score * 100)
                
                if previous_run.r2_score and latest_run.r2_score:
                    r2_change = ((latest_run.r2_score - previous_run.r2_score) / 
                                abs(previous_run.r2_score) * 100) if previous_run.r2_score != 0 else None
                
                if previous_run.mae and latest_run.mae:
                    # MAE: lower is better, so negative change is good
                    mae_change = ((latest_run.mae - previous_run.mae) / 
                                 previous_run.mae * 100) if previous_run.mae != 0 else None
                
                if previous_run.rmse and latest_run.rmse:
                    # RMSE: lower is better, so negative change is good
                    rmse_change = ((latest_run.rmse - previous_run.rmse) / 
                                  previous_run.rmse * 100) if previous_run.rmse != 0 else None
            
            # Get historical data for chart (last 10 runs)
            history = []
            historical_runs = MLTrainingRun.objects.filter(
                status='completed',
                effectiveness_score__isnull=False
            ).order_by('-trained_at')[:10]
            
            for run in reversed(historical_runs):
                history.append({
                    'date': run.trained_at.isoformat(),
                    'effectiveness': run.effectiveness_score,
                    'r2': run.r2_score,
                    'mae': run.mae,
                    'rmse': run.rmse
                })
            
            return Response({
                'effectiveness': latest_run.effectiveness_score or 0,
                'r2_score': latest_run.r2_score or 0,
                'mae': latest_run.mae or 0,
                'rmse': latest_run.rmse or 0,
                'change': change,
                'r2_change': r2_change,
                'mae_change': mae_change,
                'rmse_change': rmse_change,
                'test_predictions': latest_run.test_predictions or [],
                'history': history,
                'trained_at': latest_run.trained_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting ML metrics: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLHistoryView(APIView):
    """Get ML training history for charting"""
    
    def get(self, request):
        try:
            # Get all completed runs with effectiveness scores
            runs = MLTrainingRun.objects.filter(
                status='completed',
                effectiveness_score__isnull=False
            ).order_by('trained_at')
            
            history = []
            for run in runs:
                history.append({
                    'date': run.trained_at.isoformat(),
                    'effectiveness': run.effectiveness_score,
                    'r2': run.r2_score,
                    'mae': run.mae,
                    'rmse': run.rmse,
                    'id': run.id
                })
            
            return Response({
                'history': history,
                'count': len(history)
            })
            
        except Exception as e:
            logger.error(f"Error getting ML history: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def dashboard_enhanced_view(request):
    """Enhanced dashboard with settings and service controls"""
    # Reuse same context as original dashboard
    return dashboard_view(request, template='dashboard.html')


def dashboard_view(request, template='dashboard.html'):
    """Dashboard view showing database statistics"""

    # Check if collector is running
    collector_running = False
    try:
        # Check if collector.py process is running
        result = subprocess.run(['pgrep', '-f', 'collector.py'], capture_output=True, text=True)
        collector_running = bool(result.stdout.strip())
    except:
        pass

    # Get last collector run from database or Django model
    last_collector_date = None
    last_run_urls_processed = 0
    try:
        # Get last two runs to calculate the difference
        last_runs = list(CollectorRun.objects.filter(status__in=['completed', 'failed', 'stopped']).order_by('-ended_at')[:2])
        if last_runs:
            last_collector_run = last_runs[0]
            last_collector_date = last_collector_run.ended_at

            # Calculate URLs processed in the last run (difference from previous)
            if len(last_runs) > 1:
                previous_run = last_runs[1]
                last_run_urls_processed = last_collector_run.urls_processed - previous_run.urls_processed
            else:
                # First run, all URLs are new
                last_run_urls_processed = last_collector_run.urls_processed
        else:
            # Fallback to direct database query
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT stopped_at FROM collector_status
                    WHERE id = 1 AND stopped_at IS NOT NULL
                """)
                result = cursor.fetchone()
                if result:
                    last_collector_date = result[0]
    except Exception as e:
        logger.debug(f"Could not get last collector run: {e}")

    # Get last ML training run
    last_ml_date = None
    try:
        # Try Django model first
        last_ml_run = MLTrainingRun.objects.order_by('-trained_at').first()
        if last_ml_run:
            last_ml_date = last_ml_run.trained_at
        else:
            # Check if model file exists as fallback
            import os
            model_path = os.path.join(settings.BASE_DIR, 'ml', 'models', 'snoo.pkl')
            if os.path.exists(model_path):
                from datetime import datetime
                last_ml_date = datetime.fromtimestamp(os.path.getmtime(model_path))
    except Exception as e:
        logger.debug(f"Could not get last ML run: {e}")

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
        'last_run_urls_processed': last_run_urls_processed,
        'last_ml_date': last_ml_date,
        'video_count': video_count,
        'url_count': url_count,
        'pending_urls': pending_urls,
        'completed_urls': completed_urls,
        'failed_urls': failed_urls,
        'recent_videos': recent_videos,
    }

    return render(request, template, context)


# Config Management Views
class ConfigView(APIView):
    """Get current configuration"""

    def get(self, request):
        """Return current config.toml as JSON"""
        try:
            config_path = os.path.join(settings.BASE_DIR, 'config.toml')

            if not os.path.exists(config_path):
                return Response({
                    'error': 'config.toml not found'
                }, status=status.HTTP_404_NOT_FOUND)

            with open(config_path, 'rb') as f:
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib
                config = tomllib.load(f)

            # Get template for defaults and structure
            template_path = os.path.join(settings.BASE_DIR, 'assets', 'config.template.toml')
            template = {}
            if os.path.exists(template_path):
                with open(template_path, 'rb') as f:
                    template = tomllib.load(f)

            return Response({
                'config': config,
                'template': template,
                'sections': list(config.keys())
            })

        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigUpdateView(APIView):
    """Update configuration"""

    def post(self, request):
        """Update config.toml with new values"""
        try:
            section = request.data.get('section')
            key = request.data.get('key')
            value = request.data.get('value')

            if not section or not key:
                return Response({
                    'error': 'section and key are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            config_path = os.path.join(settings.BASE_DIR, 'config.toml')

            # Read existing config
            with open(config_path, 'rb') as f:
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib
                config = tomllib.load(f)

            # Update value
            if section not in config:
                config[section] = {}
            config[section][key] = value

            # Write back
            with open(config_path, 'w') as f:
                toml.dump(config, f)

            logger.info(f"Config updated: [{section}] {key} = {value}")

            return Response({
                'success': True,
                'message': f'Updated [{section}] {key}',
                'config': config
            })

        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigValidateView(APIView):
    """Validate configuration values"""

    def post(self, request):
        """Validate config values before saving"""
        try:
            section = request.data.get('section')
            key = request.data.get('key')
            value = request.data.get('value')

            # Validation rules
            validation_rules = {
                'processing': {
                    'workers': lambda v: 1 <= v <= 32,
                    'batch_size': lambda v: 1 <= v <= 100,
                    'delay': lambda v: v >= 0
                },
                'database': {
                    'port': lambda v: 1 <= v <= 65535
                },
                'display': {
                    'mode': lambda v: v in ['rich', 'simple', 'auto'],
                    'refresh_rate': lambda v: 0.1 <= v <= 10
                }
            }

            # Check if validation rule exists
            if section in validation_rules and key in validation_rules[section]:
                rule = validation_rules[section][key]
                is_valid = rule(value)

                return Response({
                    'valid': is_valid,
                    'message': 'Valid' if is_valid else f'Invalid value for [{section}] {key}'
                })

            # No specific validation rule - accept
            return Response({
                'valid': True,
                'message': 'No validation rules - accepting value'
            })

        except Exception as e:
            return Response({
                'valid': False,
                'message': str(e)
            })


# Service Control Views
class CollectorStartView(APIView):
    """Start collector service"""

    def post(self, request):
        """Start the collector"""
        try:
            # Check if running in Docker
            if os.environ.get('DOCKER_CONTAINER') and DOCKER_AVAILABLE:
                # Use Docker API to start container
                client = docker.from_env()
                try:
                    container = client.containers.get('tiktok_scraper_collector')
                    if container.status != 'running':
                        container.start()
                        logger.info("Started collector container")
                    return Response({'success': True, 'mode': 'docker'})
                except docker.errors.NotFound:
                    # Create and start container
                    subprocess.run(['docker-compose', 'up', '-d', 'collector'],
                                 cwd=settings.BASE_DIR)
                    return Response({'success': True, 'mode': 'docker-compose'})
            else:
                # Start collector process directly
                venv_python = os.path.join(settings.BASE_DIR, 'venv', 'bin', 'python')
                process = subprocess.Popen(
                    [venv_python, 'collector.py', '--from-queue'],
                    cwd=settings.BASE_DIR
                )

                # Store process info
                CollectorRun.objects.create(
                    started_at=datetime.now(),
                    status='running'
                )

                return Response({
                    'success': True,
                    'pid': process.pid,
                    'mode': 'local'
                })

        except Exception as e:
            logger.error(f"Error starting collector: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CollectorStopView(APIView):
    """Stop collector service"""

    def post(self, request):
        """Stop the collector"""
        try:
            if os.environ.get('DOCKER_CONTAINER') and DOCKER_AVAILABLE:
                # Stop Docker container
                client = docker.from_env()
                try:
                    container = client.containers.get('tiktok_scraper_collector')
                    container.stop()
                    return Response({'success': True, 'mode': 'docker'})
                except docker.errors.NotFound:
                    return Response({'success': True, 'message': 'Container not running'})
            else:
                # Stop local process
                result = subprocess.run(['pkill', '-f', 'collector.py'],
                                      capture_output=True)

                # Update status
                CollectorRun.objects.filter(status='running').update(
                    status='stopped',
                    ended_at=datetime.now()
                )

                return Response({
                    'success': True,
                    'mode': 'local'
                })

        except Exception as e:
            logger.error(f"Error stopping collector: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CollectorRestartView(APIView):
    """Restart collector service"""

    def post(self, request):
        """Restart the collector"""
        try:
            # Stop first
            stop_view = CollectorStopView()
            stop_response = stop_view.post(request)

            # Wait a moment
            time.sleep(2)

            # Start again
            start_view = CollectorStartView()
            start_response = start_view.post(request)

            return Response({
                'success': True,
                'message': 'Collector restarted'
            })

        except Exception as e:
            logger.error(f"Error restarting collector: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CollectorStatusView(APIView):
    """Get detailed collector status"""

    def get(self, request):
        """Get collector status"""
        try:
            status_info = CollectorService.get_collector_stats()

            # Add container info if in Docker
            if os.environ.get('DOCKER_CONTAINER') and DOCKER_AVAILABLE:
                try:
                    client = docker.from_env()
                    container = client.containers.get('tiktok_scraper_collector')
                    status_info['container'] = {
                        'id': container.short_id,
                        'status': container.status,
                        'created': container.attrs['Created'],
                        'state': container.attrs['State']
                    }
                except:
                    pass

            return Response(status_info)

        except Exception as e:
            logger.error(f"Error getting collector status: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLServiceStartView(APIView):
    """Start ML training"""

    def post(self, request):
        """Start ML training"""
        try:
            # Run ML training
            venv_python = os.path.join(settings.BASE_DIR, 'venv', 'bin', 'python')
            process = subprocess.Popen(
                [venv_python, 'ml/train_ml.py', 'train'],
                cwd=settings.BASE_DIR
            )

            # Create training run record
            MLTrainingRun.objects.create(
                model_name='TikTokPerformancePredictor',
                status='running',
                trained_at=datetime.now()
            )

            return Response({
                'success': True,
                'pid': process.pid
            })

        except Exception as e:
            logger.error(f"Error starting ML training: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLServiceStopView(APIView):
    """Stop ML training"""

    def post(self, request):
        """Stop ML training"""
        try:
            # Kill ML training process
            subprocess.run(['pkill', '-f', 'train_ml.py'])

            # Update status
            MLTrainingRun.objects.filter(status='running').update(
                status='stopped'
            )

            return Response({'success': True})

        except Exception as e:
            logger.error(f"Error stopping ML training: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLServiceStatusView(APIView):
    """Get ML service status"""

    def get(self, request):
        """Get ML training status"""
        try:
            # Check if training is running
            result = subprocess.run(['pgrep', '-f', 'train_ml.py'],
                                  capture_output=True, text=True)
            is_running = bool(result.stdout.strip())

            # Get latest training run
            latest_run = MLTrainingRun.objects.order_by('-trained_at').first()

            return Response({
                'running': is_running,
                'latest_run': {
                    'id': latest_run.id,
                    'status': latest_run.status,
                    'trained_at': latest_run.trained_at,
                    'r2_score': latest_run.r2_score,
                    'effectiveness_score': latest_run.effectiveness_score
                } if latest_run else None
            })

        except Exception as e:
            logger.error(f"Error getting ML status: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Container Management Views
class ContainerStatusView(APIView):
    """Get container status for auto-scaling"""

    def get(self, request):
        """Get container and queue status"""
        try:
            pending = QueuedURL.objects.filter(status='pending').count()
            processing = QueuedURL.objects.filter(status='processing').count()

            container_status = {
                'queue_depth': pending,
                'processing': processing,
                'should_scale_up': pending > 10,  # Configurable threshold
                'should_scale_down': pending == 0 and processing == 0
            }

            # Check container status if in Docker
            if os.environ.get('DOCKER_CONTAINER') and DOCKER_AVAILABLE:
                try:
                    client = docker.from_env()
                    container = client.containers.get('tiktok_scraper_collector')
                    container_status['container'] = {
                        'running': container.status == 'running',
                        'status': container.status
                    }
                except docker.errors.NotFound:
                    container_status['container'] = {
                        'running': False,
                        'status': 'not_found'
                    }

            return Response(container_status)

        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContainerScaleView(APIView):
    """Scale collector container based on queue"""

    def post(self, request):
        """Scale container up or down"""
        try:
            action = request.data.get('action', 'auto')
            workers = request.data.get('workers', None)

            if action == 'auto':
                # Auto-scale based on queue
                pending = QueuedURL.objects.filter(status='pending').count()

                if pending > 50:
                    workers = 8
                elif pending > 20:
                    workers = 4
                elif pending > 10:
                    workers = 2
                elif pending > 0:
                    workers = 1
                else:
                    # No pending URLs - stop container
                    if os.environ.get('DOCKER_CONTAINER') and DOCKER_AVAILABLE:
                        client = docker.from_env()
                        try:
                            container = client.containers.get('tiktok_scraper_collector')
                            container.stop()
                        except:
                            pass

                    return Response({
                        'success': True,
                        'action': 'stopped',
                        'reason': 'no_pending_urls'
                    })

            # Update worker count in config
            if workers:
                config_path = os.path.join(settings.BASE_DIR, 'config.toml')
                with open(config_path, 'rb') as f:
                    try:
                        import tomllib
                    except ImportError:
                        import tomli as tomllib
                    config = tomllib.load(f)

                if 'processing' not in config:
                    config['processing'] = {}
                config['processing']['workers'] = workers

                with open(config_path, 'w') as f:
                    toml.dump(config, f)

                # Restart collector with new worker count
                restart_view = CollectorRestartView()
                restart_view.post(request)

                return Response({
                    'success': True,
                    'action': 'scaled',
                    'workers': workers
                })

            return Response({'success': True})

        except Exception as e:
            logger.error(f"Error scaling container: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
