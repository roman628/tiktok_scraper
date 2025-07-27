#!/usr/bin/env python3
"""
Unified exception handling for TikTok scraper
"""

import traceback
from typing import Optional, Any
from datetime import datetime


class TikTokScraperException(Exception):
    """Base exception for TikTok scraper operations"""
    
    def __init__(self, message: str, error_code: str = None, original_error: Exception = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.original_error = original_error
        self.timestamp = datetime.now()


class DownloadException(TikTokScraperException):
    """Video download related errors"""
    pass


class CommentExtractionException(TikTokScraperException):
    """Comment extraction related errors"""
    pass


class TokenException(TikTokScraperException):
    """MS_TOKEN related errors"""
    pass


class StorageException(TikTokScraperException):
    """File storage and JSON operations errors"""
    pass


class ValidationException(TikTokScraperException):
    """Data validation errors"""
    pass


class ErrorHandler:
    """Unified error handling and logging"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.error_count = 0
        self.errors = []
    
    def handle_error(self, error: Exception, context: str = "", 
                    critical: bool = False) -> Optional[str]:
        """Handle error with consistent formatting and logging"""
        self.error_count += 1
        
        # Determine error type and message
        if isinstance(error, TikTokScraperException):
            error_msg = f"{error.error_code}: {error.message}" if error.error_code else error.message
            if error.original_error and self.verbose:
                error_msg += f" (Original: {error.original_error})"
        else:
            error_msg = str(error)
        
        # Format the error message
        if context:
            full_message = f"{context}: {error_msg}"
        else:
            full_message = error_msg
        
        # Store error for reporting
        error_record = {
            'timestamp': datetime.now().isoformat(),
            'type': type(error).__name__,
            'message': full_message,
            'critical': critical
        }
        
        if self.verbose and hasattr(error, '__traceback__'):
            error_record['traceback'] = traceback.format_exception(
                type(error), error, error.__traceback__
            )
        
        self.errors.append(error_record)
        
        # Print error with appropriate icon
        icon = "🚨" if critical else "❌"
        print(f"{icon} {full_message}")
        
        if self.verbose and not isinstance(error, TikTokScraperException):
            print(f"   Details: {traceback.format_exc()}")
        
        return full_message
    
    def handle_warning(self, message: str, context: str = ""):
        """Handle warnings with consistent formatting"""
        full_message = f"{context}: {message}" if context else message
        print(f"⚠️  {full_message}")
        
        warning_record = {
            'timestamp': datetime.now().isoformat(),
            'type': 'Warning',
            'message': full_message,
            'critical': False
        }
        self.errors.append(warning_record)
    
    def handle_success(self, message: str, context: str = ""):
        """Handle success messages with consistent formatting"""
        full_message = f"{context}: {message}" if context else message
        print(f"✅ {full_message}")
    
    def handle_info(self, message: str, context: str = ""):
        """Handle info messages with consistent formatting"""
        full_message = f"{context}: {message}" if context else message
        print(f"ℹ️  {full_message}")
    
    def get_error_summary(self) -> dict:
        """Get summary of all errors encountered"""
        critical_errors = [e for e in self.errors if e.get('critical', False)]
        warnings = [e for e in self.errors if e['type'] == 'Warning']
        other_errors = [e for e in self.errors if not e.get('critical', False) and e['type'] != 'Warning']
        
        return {
            'total_errors': self.error_count,
            'critical_errors': len(critical_errors),
            'warnings': len(warnings),
            'other_errors': len(other_errors),
            'errors': self.errors
        }
    
    def clear_errors(self):
        """Clear error history"""
        self.error_count = 0
        self.errors = []


def safe_execute(func, *args, error_handler: ErrorHandler = None, 
                context: str = "", default_return: Any = None, **kwargs):
    """Safely execute function with unified error handling"""
    if error_handler is None:
        error_handler = ErrorHandler()
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_handler.handle_error(e, context)
        return default_return


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, 
                    backoff_multiplier: float = 2.0):
    """Decorator for retrying operations with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            error_handler = kwargs.get('error_handler', ErrorHandler())
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:  # Last attempt
                        error_handler.handle_error(
                            e, f"Failed after {max_attempts} attempts"
                        )
                        raise
                    else:
                        error_handler.handle_warning(
                            f"Attempt {attempt + 1} failed, retrying in {current_delay}s: {e}"
                        )
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
            
        return wrapper
    return decorator