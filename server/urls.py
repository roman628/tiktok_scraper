from django.urls import path, re_path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.dashboard_view, name='home'),
    
    # URL submission endpoints (replaces url_server.py)
    path('api/submit-url/', views.URLSubmitView.as_view(), name='submit-url'),
    path('api/batch-submit/', views.BatchURLSubmitView.as_view(), name='batch-submit'),
    
    # Status and monitoring
    path('api/status/', views.ProcessingStatusView.as_view(), name='processing-status'),
    path('api/videos/', views.VideoListView.as_view(), name='video-list'),
    
    # ML prediction (replaces ml/api.py)
    re_path(r'^predict/?', views.MLPredictView.as_view(), name='ml-predict'),
    
    # Health check
    path('health/', views.HealthCheckView.as_view(), name='health-check-legacy'),
    path('api/health/', views.HealthCheckView.as_view(), name='health-check'),
    
    # MS_TOKEN update
    path('api/update-token/', views.UpdateTokenView.as_view(), name='update-token'),
    
    # Collector completion notification
    path('api/collector-complete/', views.CollectorCompleteView.as_view(), name='collector-complete'),
    
    # ML training status signals
    path('api/ml/start/', views.MLTrainingStartView.as_view(), name='ml-training-start'),
    path('api/ml/end/', views.MLTrainingEndView.as_view(), name='ml-training-end'),
    
    # ML metrics endpoints
    path('api/ml/metrics/', views.MLMetricsView.as_view(), name='ml-metrics'),
    path('api/ml/history/', views.MLHistoryView.as_view(), name='ml-history'),

    # Config management endpoints
    path('api/config/', views.ConfigView.as_view(), name='config-get'),
    path('api/config/update/', views.ConfigUpdateView.as_view(), name='config-update'),
    path('api/config/validate/', views.ConfigValidateView.as_view(), name='config-validate'),

    # Service control endpoints
    path('api/services/collector/start/', views.CollectorStartView.as_view(), name='collector-start'),
    path('api/services/collector/stop/', views.CollectorStopView.as_view(), name='collector-stop'),
    path('api/services/collector/restart/', views.CollectorRestartView.as_view(), name='collector-restart'),
    path('api/services/collector/status/', views.CollectorStatusView.as_view(), name='collector-status'),

    path('api/services/ml/start/', views.MLServiceStartView.as_view(), name='ml-service-start'),
    path('api/services/ml/stop/', views.MLServiceStopView.as_view(), name='ml-service-stop'),
    path('api/services/ml/status/', views.MLServiceStatusView.as_view(), name='ml-service-status'),

    # Container management endpoints (for Docker)
    path('api/services/container/status/', views.ContainerStatusView.as_view(), name='container-status'),
    path('api/services/container/scale/', views.ContainerScaleView.as_view(), name='container-scale'),
]