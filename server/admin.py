from django.contrib import admin
from .models import Video, QueuedURL, CollectorRun, MLTrainingRun, Transcription


class TranscriptionInline(admin.TabularInline):
    model = Transcription
    extra = 0
    fields = ['whisper_transcription', 'model_used', 'language', 'confidence', 'transcription_timestamp']
    readonly_fields = ['transcription_timestamp']
    can_delete = False
    max_num = 1
    verbose_name = "Transcription"
    verbose_name_plural = "Transcription"


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['video_id', 'get_title_display', 'uploader', 'view_count', 'like_count', 'has_transcription', 'downloaded_at']
    list_filter = ['downloaded_at', 'platform', 'uploader']
    search_fields = ['video_id', 'title', 'description', 'uploader']
    ordering = ['-id']  # Order by ID since downloaded_at might be null
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 50
    inlines = [TranscriptionInline]
    
    def get_title_display(self, obj):
        if obj.title:
            return obj.title[:60] + '...' if len(obj.title) > 60 else obj.title
        return '-'
    get_title_display.short_description = 'Title'
    
    def has_transcription(self, obj):
        return '✓' if obj.transcriptions.exists() else '✗'
    has_transcription.short_description = 'Transcribed'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('video_id', 'url', 'title', 'description')
        }),
        ('Uploader Information', {
            'fields': ('uploader', 'uploader_id', 'uploader_url')
        }),
        ('Statistics', {
            'fields': ('view_count', 'like_count', 'comment_count', 'repost_count', 'save_count', 'share_count')
        }),
        ('Video Details', {
            'fields': ('duration', 'width', 'height', 'fps', 'filesize', 'format')
        }),
        ('Timestamps', {
            'fields': ('upload_date', 'timestamp', 'downloaded_at', 'created_at', 'updated_at')
        }),
        ('System', {
            'fields': ('downloaded_with', 'platform')
        })
    )


@admin.register(QueuedURL)
class QueuedURLAdmin(admin.ModelAdmin):
    list_display = ['url', 'status', 'added_at', 'processed_at']
    list_filter = ['status', 'added_at', 'processed_at']
    search_fields = ['url']
    ordering = ['-added_at']
    actions = ['mark_as_pending', 'mark_as_failed']
    
    def mark_as_pending(self, request, queryset):
        queryset.update(status='pending')
    mark_as_pending.short_description = "Mark selected URLs as pending"
    
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
    mark_as_failed.short_description = "Mark selected URLs as failed"


@admin.register(CollectorRun)
class CollectorRunAdmin(admin.ModelAdmin):
    list_display = ['started_at', 'status', 'urls_processed', 'urls_failed', 'ended_at']
    list_filter = ['status', 'started_at']
    ordering = ['-started_at']
    readonly_fields = ['started_at']


@admin.register(MLTrainingRun)
class MLTrainingRunAdmin(admin.ModelAdmin):
    list_display = ['trained_at', 'model_name', 'accuracy', 'training_samples']
    list_filter = ['model_name', 'trained_at']
    ordering = ['-trained_at']
    readonly_fields = ['trained_at']