from django.urls import path, re_path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
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
]