#!/usr/bin/env python3
"""
Unified configuration management for TikTok scraper
Consolidates scattered argument parsing and configuration
"""

import os
import json
import argparse
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from .exceptions import ValidationException


@dataclass
class TikTokConfig:
    """Unified configuration for TikTok scraper operations"""
    
    # Input options
    url: Optional[str] = None
    input_file: Optional[str] = None
    limit: Optional[int] = None
    
    # Download options
    output_dir: str = "downloads"
    quality: str = "best"
    audio_only: bool = False
    proxy: Optional[str] = None
    
    # Transcription options
    use_whisper: bool = False
    force_cpu: bool = False
    
    # Comment options
    max_comments: int = 10
    ms_token: Optional[str] = None
    
    # Processing options
    batch_size: int = 10
    delay: float = 2.0
    workers: int = 1
    
    # Resume options
    force_redownload: bool = False
    clean_progress: bool = False
    clean_old_downloads: bool = False
    
    # System options
    memory_tracking: bool = False
    verbose: bool = False
    debug: bool = False
    
    # File paths
    master_file: str = "master2.json"
    progress_file: str = "download_progress.json"
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'TikTokConfig':
        """Create config from command line arguments"""
        config = cls()
        
        # Map arguments to config fields
        arg_mapping = {
            'url': 'url',
            'from_file': 'input_file', 
            'limit': 'limit',
            'output': 'output_dir',
            'quality': 'quality',
            'mp3': 'audio_only',
            'proxy': 'proxy',
            'whisper': 'use_whisper',
            'force_cpu': 'force_cpu',
            'max_comments': 'max_comments',
            'ms_token': 'ms_token',
            'batch_size': 'batch_size',
            'delay': 'delay',
            'workers': 'workers',
            'force_redownload': 'force_redownload',
            'clean_progress': 'clean_progress',
            'clean_old_downloads': 'clean_old_downloads',
            'memory_tracking': 'memory_tracking',
            'verbose': 'verbose',
            'debug': 'debug'
        }
        
        for arg_name, config_field in arg_mapping.items():
            if hasattr(args, arg_name):
                value = getattr(args, arg_name)
                if value is not None:
                    setattr(config, config_field, value)
        
        return config
    
    @classmethod
    def from_file(cls, config_file: str) -> 'TikTokConfig':
        """Load configuration from JSON file"""
        if not os.path.exists(config_file):
            raise ValidationException(f"Config file not found: {config_file}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = cls()
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            return config
            
        except Exception as e:
            raise ValidationException(f"Failed to load config from {config_file}: {e}")
    
    @classmethod
    def default_config(cls) -> 'TikTokConfig':
        """Create default configuration"""
        return cls(
            input_file='urls.txt',
            audio_only=True,
            use_whisper=True,
            batch_size=10,
            delay=2.0,
            max_comments=10
        )
    
    def save_to_file(self, config_file: str) -> bool:
        """Save configuration to JSON file"""
        try:
            config_data = asdict(self)
            # Remove None values for cleaner output
            config_data = {k: v for k, v in config_data.items() if v is not None}
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to save config to {config_file}: {e}")
            return False
    
    def validate(self) -> bool:
        """Validate configuration parameters"""
        errors = []
        
        # Check input sources
        if not self.url and not self.input_file:
            errors.append("Either 'url' or 'input_file' must be specified")
        
        # Check file paths
        if self.input_file and not os.path.exists(self.input_file):
            errors.append(f"Input file not found: {self.input_file}")
        
        # Check numeric ranges
        if self.max_comments < 0:
            errors.append("max_comments must be non-negative")
        
        if self.batch_size < 1:
            errors.append("batch_size must be at least 1")
        
        if self.delay < 0:
            errors.append("delay must be non-negative")
        
        if self.workers < 1:
            errors.append("workers must be at least 1")
        
        # Check quality option
        valid_qualities = ["best", "worst", "720p", "480p", "360p"]
        if self.quality not in valid_qualities:
            errors.append(f"quality must be one of: {valid_qualities}")
        
        if errors:
            raise ValidationException("Configuration validation failed: " + "; ".join(errors))
        
        return True
    
    def apply_environment_overrides(self):
        """Apply environment variable overrides"""
        env_mappings = {
            'TIKTOK_MS_TOKEN': 'ms_token',
            'TIKTOK_OUTPUT_DIR': 'output_dir',
            'TIKTOK_PROXY': 'proxy',
            'TIKTOK_WORKERS': 'workers',
            'TIKTOK_DELAY': 'delay'
        }
        
        for env_var, config_field in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                # Type conversion based on field type
                current_value = getattr(self, config_field)
                if isinstance(current_value, int):
                    setattr(self, config_field, int(env_value))
                elif isinstance(current_value, float):
                    setattr(self, config_field, float(env_value))
                elif isinstance(current_value, bool):
                    setattr(self, config_field, env_value.lower() in ('true', '1', 'yes'))
                else:
                    setattr(self, config_field, env_value)
    
    def get_download_kwargs(self) -> Dict[str, Any]:
        """Get kwargs for download operations"""
        return {
            'output_dir': self.output_dir,
            'quality': self.quality,
            'audio_only': self.audio_only,
            'use_whisper': self.use_whisper,
            'proxy': self.proxy
        }
    
    def __str__(self) -> str:
        """String representation for logging"""
        config_summary = []
        
        if self.url:
            config_summary.append(f"URL: {self.url}")
        if self.input_file:
            config_summary.append(f"Input file: {self.input_file}")
        
        config_summary.extend([
            f"Output: {self.output_dir}",
            f"Quality: {self.quality}",
            f"Audio only: {self.audio_only}",
            f"Whisper: {self.use_whisper}",
            f"Comments: {self.max_comments}",
            f"Workers: {self.workers}",
            f"Batch size: {self.batch_size}",
            f"Delay: {self.delay}s"
        ])
        
        return " | ".join(config_summary)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create unified argument parser"""
    parser = argparse.ArgumentParser(
        description="TikTok video downloader and comment extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default settings
  %(prog)s --from-file urls.txt --mp3         # Download audio from file
  %(prog)s URL --whisper --max-comments 20    # Single video with transcription
  %(prog)s --from-file urls.txt --workers 4   # Parallel processing
        """
    )
    
    # Input options
    parser.add_argument("url", nargs='?', help="Single TikTok video URL")
    parser.add_argument("--from-file", "-f", type=str, help="Process URLs from text file")
    parser.add_argument("--limit", type=int, help="Limit number of URLs to process")
    
    # Download options
    parser.add_argument("-o", "--output", default="downloads", help="Output directory")
    parser.add_argument("-q", "--quality", default="best", 
                       choices=["best", "worst", "720p", "480p", "360p"],
                       help="Video quality")
    parser.add_argument("--mp3", action="store_true", help="Download audio only as MP3")
    parser.add_argument("--proxy", type=str, help="Proxy URL")
    
    # Transcription options
    parser.add_argument("--whisper", action="store_true", help="Use faster-whisper for transcription")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU mode for whisper")
    
    # Comment options
    parser.add_argument("--max-comments", type=int, default=10, 
                       help="Maximum comments per video")
    parser.add_argument("--ms-token", type=str, help="MS_TOKEN for comment extraction")
    
    # Processing options
    parser.add_argument("--batch-size", type=int, default=10, 
                       help="Save frequency for batch operations")
    parser.add_argument("--delay", type=float, default=2.0, 
                       help="Delay between requests in seconds")
    parser.add_argument("--workers", type=int, default=1, 
                       help="Number of worker processes")
    
    # Resume options
    parser.add_argument("--force-redownload", action="store_true", 
                       help="Redownload all URLs (ignore duplicates)")
    parser.add_argument("--clean-progress", action="store_true", 
                       help="Clean progress file and start fresh")
    parser.add_argument("--clean-old-downloads", action="store_true", 
                       help="Clean up old download directories")
    
    # System options
    parser.add_argument("--memory-tracking", action="store_true", 
                       help="Enable memory usage tracking")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose output")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug logging to debug-logs directory")
    parser.add_argument("--config", type=str, help="Load configuration from file")
    parser.add_argument("--save-config", type=str, help="Save configuration to file")
    
    return parser