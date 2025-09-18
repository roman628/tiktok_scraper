from django.db import models
from django.utils import timezone


class Video(models.Model):
    """Django model matching existing PostgreSQL videos table"""
    id = models.AutoField(primary_key=True)
    video_id = models.CharField(max_length=100, unique=True)
    url = models.TextField(unique=True)
    title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    duration = models.IntegerField(null=True, blank=True)
    uploader = models.CharField(max_length=255, blank=True, null=True)
    uploader_id = models.CharField(max_length=100, blank=True, null=True)
    uploader_url = models.TextField(blank=True, null=True)
    view_count = models.BigIntegerField(null=True, blank=True)
    like_count = models.BigIntegerField(null=True, blank=True)
    comment_count = models.BigIntegerField(null=True, blank=True)
    repost_count = models.BigIntegerField(null=True, blank=True)
    save_count = models.BigIntegerField(null=True, blank=True)
    share_count = models.BigIntegerField(null=True, blank=True)
    upload_date = models.DateField(null=True, blank=True)
    timestamp = models.BigIntegerField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    fps = models.IntegerField(null=True, blank=True)
    filesize = models.BigIntegerField(null=True, blank=True)
    format = models.CharField(max_length=50, blank=True, null=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    downloaded_with = models.CharField(max_length=100, blank=True, null=True)
    platform = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'videos'  # Use existing table
        managed = False  # Don't create migrations for existing table

    def __str__(self):
        return f"{self.title or self.video_id}"


class QueuedURL(models.Model):
    """New table for URL queue (replaces urls.txt)"""
    url = models.URLField(unique=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    added_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'queued_urls'
        ordering = ['added_at']

    def __str__(self):
        return f"{self.url} ({self.status})"


class CollectorRun(models.Model):
    """Track collector runs for dashboard statistics"""
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped')
    ], default='running')
    urls_processed = models.IntegerField(default=0)
    urls_failed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'collector_runs'
        ordering = ['-started_at']

    def __str__(self):
        return f"Run {self.started_at.strftime('%Y-%m-%d %H:%M')} ({self.status})"


class MLTrainingRun(models.Model):
    """Track ML model training runs"""
    trained_at = models.DateTimeField(auto_now_add=True)
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=20, blank=True, null=True)
    accuracy = models.FloatField(null=True, blank=True)
    training_samples = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='running')
    model_path = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # New ML performance metrics
    r2_score = models.FloatField(null=True, blank=True)
    mae = models.FloatField(null=True, blank=True)
    rmse = models.FloatField(null=True, blank=True)
    prediction_range = models.FloatField(null=True, blank=True)
    prediction_std = models.FloatField(null=True, blank=True)
    cv_mean = models.FloatField(null=True, blank=True)
    cv_std = models.FloatField(null=True, blank=True)
    effectiveness_score = models.FloatField(null=True, blank=True)
    
    # Test predictions JSON field
    test_predictions = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'ml_training_runs'
        ordering = ['-trained_at']

    def __str__(self):
        return f"Training {self.trained_at.strftime('%Y-%m-%d %H:%M')} - {self.model_name}"
    
    def calculate_effectiveness(self):
        """Calculate composite effectiveness score (0-100)"""
        if not all([self.r2_score is not None, self.mae is not None, self.rmse is not None]):
            return None
        
        # Normalize R² (0-1 → 0-40 points)
        r2_points = max(0, min(40, self.r2_score * 40))
        
        # Normalize MAE (lower is better, assume 0-100 range → 30-0 points)
        mae_points = max(0, 30 - (min(100, self.mae) / 100 * 30))
        
        # Normalize RMSE (lower is better, assume 0-100 range → 30-0 points)
        rmse_points = max(0, 30 - (min(100, self.rmse) / 100 * 30))
        
        return r2_points + mae_points + rmse_points


class CollectorStatus(models.Model):
    """Legacy collector status table - kept for compatibility"""
    id = models.IntegerField(primary_key=True, default=1)
    status = models.CharField(max_length=20, default='stopped')
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    urls_processed = models.IntegerField(default=0)
    pid = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'collector_status'
        
    def __str__(self):
        return f"Collector Status: {self.status}"


class Transcription(models.Model):
    """Django model for transcriptions table"""
    id = models.AutoField(primary_key=True)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, db_column='video_id', related_name='transcriptions')
    whisper_transcription = models.TextField(blank=True, null=True)
    transcription_timestamp = models.DateTimeField(null=True, blank=True)
    model_used = models.CharField(max_length=50, blank=True, null=True)
    language = models.CharField(max_length=10, blank=True, null=True)
    confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'transcriptions'
        managed = False  # Don't create migrations for existing table

    def __str__(self):
        return f"Transcription for {self.video.video_id}"
