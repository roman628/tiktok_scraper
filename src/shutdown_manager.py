"""Centralized shutdown management for graceful termination."""

import signal
import threading
import multiprocessing as mp
from typing import List, Callable, Optional, Any
from contextlib import contextmanager
import time
import sys
import os

class ShutdownManager:
    """Manages graceful shutdown across all process types."""
    
    def __init__(self):
        self.shutdown_event = mp.Event()
        self.cleanup_handlers = []
        self.shutdown_lock = threading.Lock()
        self.shutdown_initiated = False
        self._original_handlers = {}
        
    def register_cleanup_handler(self, handler: Callable):
        """Register a cleanup handler to be called during shutdown."""
        self.cleanup_handlers.append(handler)
    
    def register_signal_handlers(self, force_exit_on_double: bool = True):
        """Register unified signal handlers.
        
        Args:
            force_exit_on_double: If True, second Ctrl+C forces immediate exit
        """
        self._force_exit_count = 0
        
        def signal_handler(signum, frame):
            with self.shutdown_lock:
                if self.shutdown_initiated:
                    self._force_exit_count += 1
                    if force_exit_on_double and self._force_exit_count >= 2:
                        print("\nForced exit requested. Terminating immediately.")
                        os._exit(1)
                    print("\nShutdown already in progress, please wait...")
                    return
                self.shutdown_initiated = True
            
            print(f"\nReceived signal {signum}, initiating graceful shutdown...")
            print("Press Ctrl+C again to force immediate termination.")
            self.shutdown_event.set()
            
            # Run cleanup handlers with timeout protection
            for handler in self.cleanup_handlers:
                try:
                    # Use threading timer for timeout since we can't use signals in signal handler
                    cleanup_thread = threading.Thread(target=handler)
                    cleanup_thread.daemon = True
                    cleanup_thread.start()
                    cleanup_thread.join(timeout=5.0)
                    if cleanup_thread.is_alive():
                        print(f"Warning: Cleanup handler timed out")
                except Exception as e:
                    print(f"Warning: Error in cleanup handler: {e}")
            
            print("Graceful shutdown completed")
            sys.exit(0)
        
        # Store original handlers
        self._original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, signal_handler)
        self._original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, signal_handler)
    
    def restore_original_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_event.is_set()
    
    def request_shutdown(self):
        """Programmatically request shutdown."""
        self.shutdown_event.set()
    
    @contextmanager
    def protected_section(self):
        """Context manager to protect critical sections from interruption."""
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            yield
        finally:
            signal.signal(signal.SIGINT, old_handler)

# Global shutdown manager instance
shutdown_manager = ShutdownManager()


class WorkerShutdownHandler:
    """Handles shutdown for worker processes."""
    
    def __init__(self, worker_id: int, shutdown_event: mp.Event):
        self.worker_id = worker_id
        self.shutdown_event = shutdown_event
        self.cleanup_handlers = []
        
    def register_cleanup(self, handler: Callable):
        """Register a cleanup handler for this worker."""
        self.cleanup_handlers.append(handler)
        
    def setup_signal_handling(self):
        """Set up signal handling for worker process."""
        def worker_signal_handler(signum, frame):
            print(f"Worker {self.worker_id} received shutdown signal")
            self.shutdown_event.set()
            
            # Run worker-specific cleanup
            for handler in self.cleanup_handlers:
                try:
                    handler()
                except Exception as e:
                    print(f"Worker {self.worker_id} cleanup error: {e}")
            
            # Don't exit immediately - let the worker loop handle it
        
        signal.signal(signal.SIGINT, worker_signal_handler)
        signal.signal(signal.SIGTERM, worker_signal_handler)