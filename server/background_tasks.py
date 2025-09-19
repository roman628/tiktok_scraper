"""
Background Task Manager for TikTok Scraper
Manages collector and ML training processes within the Django container
"""

import subprocess
import threading
import os
import signal
import logging
import toml
import time
from pathlib import Path
from typing import Optional, Dict, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background processes for collector and ML training"""

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure only one manager exists"""
        if cls._instance is None:
            cls._instance = super(BackgroundTaskManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return

        self.collector_process: Optional[subprocess.Popen] = None
        self.ml_process: Optional[subprocess.Popen] = None
        self.collector_thread: Optional[threading.Thread] = None
        self.base_dir = Path(__file__).parent.parent
        self.config_path = self.base_dir / 'config.toml'
        self.initialized = True

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from config.toml"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'rb') as f:
                    import tomllib
                    return tomllib.load(f)
            else:
                logger.warning(f"Config file not found at {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def start_collector(self, workers: Optional[int] = None) -> dict:
        """
        Start collector process with dynamic worker count
        Reads worker count from config.toml if not specified
        Returns dict with 'success' and optional 'pid' and 'message'
        """
        try:
            # Check if already running
            if self.collector_process and self.collector_process.poll() is None:
                logger.info("Collector is already running")
                return {'success': False, 'message': 'Collector is already running', 'pid': self.collector_process.pid}

            # Load config to get worker count
            config = self.load_config()

            # Use provided workers or get from config or default to 4
            if workers is None:
                workers = config.get('processing', {}).get('workers', 4)

            logger.info(f"Starting collector with {workers} workers")

            # Build command
            # Collector auto-detects database mode when no --url or --from-file is provided
            cmd = ['python', 'collector.py', '--workers', str(workers)]

            # Start collector process
            self.collector_process = subprocess.Popen(
                cmd,
                cwd=str(self.base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ}  # Pass current environment
            )

            # Start thread to monitor output
            self.collector_thread = threading.Thread(
                target=self._monitor_collector_output,
                daemon=True
            )
            self.collector_thread.start()

            logger.info(f"Collector started with PID: {self.collector_process.pid}")
            return {'success': True, 'pid': self.collector_process.pid, 'message': 'Collector started successfully'}

        except Exception as e:
            logger.error(f"Error starting collector: {e}")
            return {'success': False, 'message': str(e)}

    def is_collector_running(self) -> bool:
        """Check if collector process is running"""
        return self.collector_process and self.collector_process.poll() is None

    def stop_collector(self) -> bool:
        """Stop collector process gracefully"""
        try:
            if not self.collector_process:
                logger.info("No collector process to stop")
                return True

            if self.collector_process.poll() is not None:
                logger.info("Collector process already stopped")
                self.collector_process = None
                return True

            collector_pid = self.collector_process.pid

            # First, try to find and terminate any worker processes
            try:
                import psutil
                parent = psutil.Process(collector_pid)
                children = parent.children(recursive=True)

                if children:
                    logger.info(f"Found {len(children)} child worker processes to terminate")
                    for child in children:
                        try:
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            except Exception as e:
                logger.warning(f"Could not check for child processes: {e}")

            # Send SIGTERM for graceful shutdown
            logger.info(f"Stopping collector PID: {collector_pid}")
            self.collector_process.terminate()

            # Wait up to 10 seconds for process to terminate
            try:
                self.collector_process.wait(timeout=10)
                logger.info("Collector stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if not terminated
                logger.warning("Collector didn't stop gracefully, forcing kill")

                # Kill any remaining child processes first
                try:
                    import psutil
                    parent = psutil.Process(collector_pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            child.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except:
                    pass

                # Then kill the parent
                self.collector_process.kill()
                self.collector_process.wait()

            self.collector_process = None
            return True

        except Exception as e:
            logger.error(f"Error stopping collector: {e}")
            return False

    def start_ml_training(self) -> bool:
        """Start ML training process"""
        try:
            # Check if already running
            if self.ml_process and self.ml_process.poll() is None:
                logger.info("ML training is already running")
                return False

            logger.info("Starting ML training")

            # Build command
            cmd = ['python', 'ml/train_ml.py', 'train']

            # Start ML process
            self.ml_process = subprocess.Popen(
                cmd,
                cwd=str(self.base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ}
            )

            # Start thread to monitor output
            threading.Thread(
                target=self._monitor_ml_output,
                daemon=True
            ).start()

            logger.info(f"ML training started with PID: {self.ml_process.pid}")
            return True

        except Exception as e:
            logger.error(f"Error starting ML training: {e}")
            return False

    def stop_ml_training(self) -> bool:
        """Stop ML training process"""
        try:
            if not self.ml_process:
                logger.info("No ML process to stop")
                return True

            if self.ml_process.poll() is not None:
                logger.info("ML process already stopped")
                self.ml_process = None
                return True

            # Send SIGTERM for graceful shutdown
            logger.info(f"Stopping ML training PID: {self.ml_process.pid}")
            self.ml_process.terminate()

            # Wait for process to terminate
            self.ml_process.wait(timeout=10)
            logger.info("ML training stopped")

            self.ml_process = None
            return True

        except Exception as e:
            logger.error(f"Error stopping ML training: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get status of all managed processes"""
        status = {
            'collector': {
                'running': False,
                'pid': None,
                'status': 'stopped'
            },
            'ml_training': {
                'running': False,
                'pid': None,
                'status': 'stopped'
            }
        }

        # Check collector status
        if self.collector_process:
            if self.collector_process.poll() is None:
                status['collector']['running'] = True
                status['collector']['pid'] = self.collector_process.pid
                status['collector']['status'] = 'running'
            else:
                # Process ended
                self.collector_process = None

        # Check ML status
        if self.ml_process:
            if self.ml_process.poll() is None:
                status['ml_training']['running'] = True
                status['ml_training']['pid'] = self.ml_process.pid
                status['ml_training']['status'] = 'running'
            else:
                # Process ended
                self.ml_process = None

        return status

    def _monitor_collector_output(self):
        """Monitor collector process output"""
        if not self.collector_process:
            return

        try:
            for line in self.collector_process.stdout:
                logger.info(f"[Collector] {line.strip()}")

            # Wait for process to complete
            self.collector_process.wait()
            logger.info(f"Collector process ended with code: {self.collector_process.returncode}")

        except Exception as e:
            logger.error(f"Error monitoring collector: {e}")

    def _monitor_ml_output(self):
        """Monitor ML training process output"""
        if not self.ml_process:
            return

        try:
            for line in self.ml_process.stdout:
                logger.info(f"[ML] {line.strip()}")

            # Wait for process to complete
            self.ml_process.wait()
            logger.info(f"ML process ended with code: {self.ml_process.returncode}")

        except Exception as e:
            logger.error(f"Error monitoring ML: {e}")

    def cleanup(self):
        """Clean up all processes on shutdown"""
        logger.info("Cleaning up background processes")
        self.stop_collector()
        self.stop_ml_training()


# Global instance
task_manager = BackgroundTaskManager()