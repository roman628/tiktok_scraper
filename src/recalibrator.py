"""
Recalibration system for retroactively filling missing data in videos.
Extensible component-based architecture for processing incomplete records.
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Component:
    """Represents a data component that can be recalibrated"""
    name: str
    db_check_field: str
    process_method: str
    requires: List[str]
    description: str

class Recalibrator:
    """
    Manages retroactive data filling for videos in the database.
    Extensible system for handling missing transcriptions, comments, metadata, etc.
    """
    
    # Component registry - easily add new components here
    COMPONENTS = {
        'transcripts': Component(
            name='transcripts',
            db_check_field='has_transcription',
            process_method='transcribe_video',
            requires=['whisper'],
            description='Whisper AI transcriptions'
        ),
        'comments': Component(
            name='comments',
            db_check_field='has_comments',
            process_method='extract_comments',
            requires=['ms_token'],
            description='TikTok comments and replies'
        ),
        'metadata': Component(
            name='metadata',
            db_check_field='has_complete_metadata',
            process_method='update_metadata',
            requires=[],
            description='Video metadata (track info, upload time, creator stats)'
        ),
        'ocr': Component(
            name='ocr',
            db_check_field='has_ocr_text',
            process_method='extract_ocr_text',
            requires=['ocr_enabled'],
            description='On-screen text extraction from video frames'
        ),
        'hashtags': Component(
            name='hashtags',
            db_check_field='has_hashtags',
            process_method='extract_hashtags',
            requires=['hashtags_enabled'],
            description='Hashtag extraction from titles/descriptions'
        ),
        # Future components can be added here:
        # 'thumbnails': Component(...),
        # 'analytics': Component(...),
        # 'captions': Component(...),
    }
    
    def __init__(self, db_manager, config):
        self.db_manager = db_manager
        self.config = config
        self.available_components = self._determine_available_components()
    
    def _determine_available_components(self) -> Set[str]:
        """Determine which components can be processed based on config"""
        available = set()
        
        # Always available
        available.add('metadata')
        
        # Check data_collection config
        data_collection = self.config.get('data_collection', {})
        
        # Check for transcription
        if data_collection.get('transcription', False) or self.config.get('download', {}).get('use_whisper', False):
            available.add('transcripts')
        
        # Check for comments (requires MS_TOKEN)
        if data_collection.get('comments', False) and self.config.get('tiktok', {}).get('ms_token'):
            available.add('comments')
        
        # Check for OCR
        if data_collection.get('ocr_text', False):
            available.add('ocr')
        
        # Check for hashtags
        if data_collection.get('hashtags', False):
            available.add('hashtags')
        
        return available
    
    def get_components_to_process(self, requested: Optional[str] = None) -> List[str]:
        """
        Get list of components to process.
        
        Args:
            requested: Comma-separated component names or None for auto-detect
            
        Returns:
            List of component names to process
        """
        if requested:
            # Parse requested components
            requested_set = set(c.strip() for c in requested.split(','))
            
            # Validate against registry
            invalid = requested_set - set(self.COMPONENTS.keys())
            if invalid:
                logger.warning(f"Invalid components requested: {invalid}")
            
            # Filter to available components
            components = list(requested_set & self.available_components)
        else:
            # Auto-detect: use all available components
            components = list(self.available_components)
        
        return components
    
    def get_videos_needing_recalibration(
        self, 
        components: List[str], 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get videos that need recalibration for specified components.
        
        Returns:
            List of dicts with video info and missing components
        """
        videos = self.db_manager.get_incomplete_videos(components, limit)
        
        if not videos:
            return []
        
        # Enrich with component info
        for video in videos:
            video['missing_components'] = []
            
            # Check each component
            for comp_name in components:
                comp = self.COMPONENTS[comp_name]
                
                # Check if this video needs this component
                if comp_name == 'transcripts':
                    if not video.get('has_transcription'):
                        video['missing_components'].append(comp_name)
                elif comp_name == 'comments':
                    if not video.get('has_comments'):
                        video['missing_components'].append(comp_name)
                elif comp_name == 'metadata':
                    # Check for any missing metadata fields
                    if (video.get('track_name') is None or 
                        video.get('track_artist') is None or 
                        video.get('upload_hour') is None or
                        video.get('creator_follower_count') is None):
                        video['missing_components'].append(comp_name)
                elif comp_name == 'ocr':
                    if not video.get('onscreen_text') and not video.get('has_text_overlay'):
                        video['missing_components'].append(comp_name)
                elif comp_name == 'hashtags':
                    if not video.get('has_hashtags'):
                        video['missing_components'].append(comp_name)
        
        # Filter to only videos with missing components
        return [v for v in videos if v['missing_components']]
    
    def prepare_recalibration_batch(
        self, 
        videos: List[Dict], 
        components: List[str]
    ) -> Dict[str, Any]:
        """
        Prepare a batch of videos for recalibration processing.
        
        Returns:
            Dict with processing instructions
        """
        batch = {
            'urls': [v['url'] for v in videos],
            'video_ids': [v['video_id'] for v in videos],
            'components': components,
            'recalibrate_mode': True,
            'skip_download': True,
            'skip_existing_check': False,
        }
        
        # Add component-specific flags
        if 'transcripts' in components:
            batch['use_whisper'] = True
        if 'comments' in components:
            batch['extract_comments'] = True
        if 'metadata' in components:
            batch['update_metadata'] = True
        if 'ocr' in components:
            batch['extract_ocr'] = True
        if 'hashtags' in components:
            batch['extract_hashtags'] = True
        
        return batch
    
    def format_summary(self, videos: List[Dict], components: List[str]) -> str:
        """Format a summary of what will be recalibrated"""
        if not videos:
            return "No videos found needing recalibration"
        
        summary = [f"Found {len(videos)} videos needing recalibration:"]
        
        # Count by component
        component_counts = {}
        for video in videos:
            for comp in video.get('missing_components', []):
                component_counts[comp] = component_counts.get(comp, 0) + 1
        
        for comp_name, count in component_counts.items():
            comp = self.COMPONENTS[comp_name]
            summary.append(f"  • {count} videos need {comp.description}")
        
        summary.append(f"\nComponents to process: {', '.join(components)}")
        
        return '\n'.join(summary)