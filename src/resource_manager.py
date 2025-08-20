"""Resource management and cleanup utilities."""

import gc
import os
import psutil
import signal
import shutil
import subprocess
import sys
from typing import Optional, List
from pathlib import Path

class ResourceManager:
    """Manages system resources, memory, and process cleanup."""
    
    MEMORY_THRESHOLD_MB = 2000  # Trigger cleanup above this threshold
    BROWSER_PROCESSES = ['chrome', 'chromium', 'chromedriver', 'google-chrome']
    
    def __init__(self):
        self.original_sigint_handler = None
        self.cleanup_handlers = []
        
    def register_signal_handlers(self, cleanup_callback=None):
        """Register signal handlers for graceful shutdown."""
        if cleanup_callback:
            self.cleanup_handlers.append(cleanup_callback)
        
        def signal_handler(signum, frame):
            print("\n\nGraceful shutdown initiated...")
            for handler in self.cleanup_handlers:
                try:
                    handler()
                except Exception as e:
                    print(f"Error in cleanup handler: {e}")
            sys.exit(0)
        
        self.original_sigint_handler = signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def restore_signal_handlers(self):
        """Restore original signal handlers."""
        if self.original_sigint_handler:
            signal.signal(signal.SIGINT, self.original_sigint_handler)
    
    @staticmethod
    def cleanup_memory():
        """Force garbage collection and clear memory."""
        gc.collect()
        gc.collect()  # Second collection for circular references
        gc.collect()  # Third for good measure
    
    @staticmethod
    def get_memory_usage_mb() -> float:
        """Get current process memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    
    @classmethod
    def check_memory_and_cleanup(cls) -> bool:
        """Check memory usage and cleanup if needed."""
        memory_mb = cls.get_memory_usage_mb()
        if memory_mb > cls.MEMORY_THRESHOLD_MB:
            print(f"Memory usage high ({memory_mb:.1f}MB), performing cleanup...")
            cls.cleanup_memory()
            return True
        return False
    
    @classmethod
    def kill_browser_processes(cls):
        """Kill any lingering browser processes."""
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                process_name = proc.info['name'].lower()
                if any(browser in process_name for browser in cls.BROWSER_PROCESSES):
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue
        
        if killed_count > 0:
            print(f"Killed {killed_count} browser processes")
    
    @staticmethod
    def cleanup_directory(directory: str):
        """Remove directory and all contents."""
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
            except Exception as e:
                print(f"Error cleaning up directory {directory}: {e}")
    
    @staticmethod
    def cleanup_file(file_path: str):
        """Remove a single file."""
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")
    
    @classmethod
    def full_cleanup(cls, directories: List[str] = None, files: List[str] = None):
        """Perform full system cleanup."""
        # Kill browser processes
        cls.kill_browser_processes()
        
        # Clean up directories
        if directories:
            for directory in directories:
                cls.cleanup_directory(directory)
        
        # Clean up files
        if files:
            for file in files:
                cls.cleanup_file(file)
        
        # Force memory cleanup
        cls.cleanup_memory()
        
    @staticmethod
    def ensure_cuda_available() -> bool:
        """Check if CUDA is available for GPU acceleration."""
        try:
            result = subprocess.run(
                ['nvidia-smi'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False