from django.db import models
from django.utils import timezone


class Video(models.Model):
    """Django model matching existing PostgreSQL videos table"""
    video_id = models.CharField(max_length=100, unique=True)
    url = models.TextField(unique=True)
    title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    duration = models.IntegerField(null=True)
    uploader = models.CharField(max_length=255, blank=True, null=True)
    uploader_id = models.CharField(max_length=100, blank=True, null=True)
    uploader_url = models.TextField(blank=True, null=True)
    view_count = models.BigIntegerField(null=True)
    like_count = models.BigIntegerField(null=True)
    comment_count = models.BigIntegerField(null=True)
    repost_count = models.BigIntegerField(null=True)
    save_count = models.BigIntegerField(null=True)
    share_count = models.BigIntegerField(null=True)
    upload_date = models.DateField(null=True)
    timestamp = models.BigIntegerField(null=True)
    width = models.IntegerField(null=True)
    height = models.IntegerField(null=True)
    fps = models.IntegerField(null=True)
    filesize = models.BigIntegerField(null=True)
    format = models.CharField(max_length=50, blank=True, null=True)
    downloaded_at = models.DateTimeField(null=True)
    downloaded_with = models.CharField(max_length=100, blank=True, null=True)
    platform = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'videos'  # Use existing table
        managed = False  # Don't create migrations initially

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
