#!/usr/bin/env python3
"""
Multiprocessing coordinator for parallel TikTok processing
Simplified replacement for the complex multiprocessing in main script
"""

import asyncio
import multiprocessing as mp
import threading
import time
import signal
import sys
import io
import contextlib
import os
from typing import List, Dict, Any
from datetime import datetime

from .config import TikTokConfig
from .models import ProcessingSummary, WorkerStats, ProcessingJob
from .processor import TikTokProcessor
from .storage import StorageManager
from .exceptions import ErrorHandler

# Ubuntu environment fixes for multiprocessing
if not os.environ.get('TERM'):
    os.environ['TERM'] = 'xterm-256color'
if not os.environ.get('LANG'):
    os.environ['LANG'] = 'en_US.UTF-8'
if not os.environ.get('LC_ALL'):
    os.environ['LC_ALL'] = 'C.UTF-8'
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# Configure multiprocessing method for Ubuntu
try:
    # Use 'fork' method on Ubuntu for better compatibility
    if sys.platform.startswith('linux'):
        mp.set_start_method('fork', force=True)
    else:
        mp.set_start_method('spawn', force=True)
except RuntimeError:
    pass  # Method already set


class OutputCapture:
    """Capture stdout/stderr for worker processes with comprehensive logging"""
    
    def __init__(self, worker_id: int, shared_state: Dict):
        self.worker_id = worker_id
        self.shared_state = shared_state
        self.captured_lines = []
        self.max_lines = 3
        
        # Create worker-specific log file
        self.log_dir = "multiprocess-logs"
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"worker_{worker_id}.log")
        
        # Open log file for writing
        try:
            self.log_handle = open(self.log_file, 'w', encoding='utf-8')
            self.log_handle.write(f"=== Worker {worker_id} Log Started at {datetime.now().isoformat()} ===\n")
            self.log_handle.flush()
        except Exception as e:
            print(f"Warning: Could not create log file for worker {worker_id}: {e}")
            self.log_handle = None
    
    def write(self, text):
        """Capture written text with comprehensive logging"""
        if text.strip():  # Only capture non-empty lines
            # Log EVERYTHING to file for analysis
            if self.log_handle:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.log_handle.write(f"[{timestamp}] {text}\n")
                self.log_handle.flush()
            
            # Clean up the text (remove ANSI codes, etc.) for display
            clean_text = text.strip()
            
            # Filter out carriage returns and progress indicators for display only
            if (clean_text and 
                not clean_text.startswith('\r') and 
                not clean_text.startswith('[download]') and
                len(clean_text) > 5):  # Ignore very short messages for display
                
                # Better truncation - calculate based on terminal width
                try:
                    import os
                    terminal_width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
                    # Reserve space for worker info and formatting (about 20 chars)
                    max_text_width = terminal_width - 25
                    
                    if len(clean_text) > max_text_width:
                        clean_text = clean_text[:max_text_width-3] + "..."
                except:
                    # Fallback to fixed width
                    if len(clean_text) > 70:
                        clean_text = clean_text[:67] + "..."
                
                # Avoid duplicate consecutive messages
                if not self.captured_lines or self.captured_lines[-1] != clean_text:
                    self.captured_lines.append(clean_text)
                    if len(self.captured_lines) > self.max_lines:
                        self.captured_lines.pop(0)
                
                # Update shared state
                try:
                    if 'worker_logs' not in self.shared_state:
                        self.shared_state['worker_logs'] = {}
                    self.shared_state['worker_logs'][self.worker_id] = list(self.captured_lines)
                except:
                    pass
    
    def flush(self):
        if self.log_handle:
            self.log_handle.flush()
    
    def close(self):
        """Close the log file"""
        if self.log_handle:
            self.log_handle.write(f"=== Worker {self.worker_id} Log Ended at {datetime.now().isoformat()} ===\n")
            self.log_handle.close()
            self.log_handle = None


class SimplifiedWorkerProcess:
    """Simplified worker process based on legacy patterns"""
    
    def __init__(self, worker_id: int, config: TikTokConfig, shared_state: Dict):
        self.worker_id = worker_id
        self.config = config
        self.shared_state = shared_state
        self.stats = WorkerStats(worker_id)
        self.shutdown_event = None
        self.whisper_model = None
        self.whisper_device = "CPU"
        
        # Load Whisper model directly like legacy code
        if config.use_whisper:
            self._load_whisper_model_legacy_style()
        
        # Simple progress tracking like legacy
        self.successful_count = 0
        self.failed_count = 0
        
        print(f"Worker {worker_id}: Initialized successfully")
    
    def _load_whisper_model_legacy_style(self):
        """Load Whisper model using legacy approach"""
        try:
            print(f"Worker {self.worker_id}: Loading Whisper model...")
            
            # Force CPU for worker processes (legacy pattern)
            original_force_cpu = self.config.force_cpu
            self.config.force_cpu = True
            
            # Import and use the proven legacy loading function
            import sys
            import os
            # Add the parent directory to path to access scripts
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            
            try:
                from scripts.collection.tiktok_scraper import load_whisper_model
                self.whisper_model, self.whisper_device = load_whisper_model(force_cpu=True)
                
                if self.whisper_model:
                    print(f"Worker {self.worker_id}: Whisper model loaded on {self.whisper_device}")
                else:
                    print(f"Worker {self.worker_id}: Failed to load Whisper model")
                    self.config.use_whisper = False
                    
            except ImportError as e:
                print(f"Worker {self.worker_id}: Could not import legacy Whisper loader: {e}")
                print(f"Worker {self.worker_id}: Falling back to built-in loader...")
                
                # Fallback to built-in loading
                from ..downloader import VideoDownloader
                temp_downloader = VideoDownloader(self.config, None)
                temp_downloader._load_whisper_model()
                self.whisper_model = temp_downloader.whisper_model
                
                if self.whisper_model:
                    self.whisper_device = "CPU"
                    print(f"Worker {self.worker_id}: Whisper model loaded via fallback")
                else:
                    self.config.use_whisper = False
            
            finally:
                # Restore original setting
                self.config.force_cpu = original_force_cpu
                
        except Exception as e:
            print(f"Worker {self.worker_id}: Whisper loading failed: {e}")
            self.config.use_whisper = False
    
    async def process_urls(self, urls: List[str]) -> WorkerStats:
        """Process URLs using simplified legacy patterns"""
        try:
            print(f"Worker {self.worker_id}: Creating TikTokProcessor")
            
            # Create processor like legacy code
            processor = TikTokProcessor(self.config)
            
            # Initialize processor
            print(f"Worker {self.worker_id}: Initializing processor...")
            if not await processor.initialize():
                print(f"Worker {self.worker_id}: ❌ Processor initialization failed")
                self.stats.status = "failed_init"
                return self.stats
            
            # Use our pre-loaded Whisper model if available
            if self.config.use_whisper and self.whisper_model:
                print(f"Worker {self.worker_id}: Using pre-loaded Whisper model")
                processor.downloader.whisper_model = self.whisper_model
            
            print(f"Worker {self.worker_id}: ✅ Ready to process {len(urls)} URLs")
            self.stats.update_activity("processing")
            
            # Process each URL with simple progress tracking
            for i, url in enumerate(urls, 1):
                # Check for shutdown
                if self.shutdown_event and self.shutdown_event.is_set():
                    self.stats.update_activity("shutdown")
                    break
                
                # Update current job
                job = ProcessingJob(url=url, video_id=url.split('/')[-1])
                self.stats.update_activity("processing", job)
                
                # Simple progress message
                video_title = url.split('/')[-1][:30] + "..." if len(url.split('/')[-1]) > 30 else url.split('/')[-1]
                print(f"Worker {self.worker_id}: Processing {i}/{len(urls)}: {video_title}")
                
                # Process video
                metadata = await processor.process_single_video(url)
                
                if metadata:
                    # Save immediately
                    processor.storage.append_single_video(metadata)
                    self.successful_count += 1
                    self.stats.increment_completed()
                    print(f"Worker {self.worker_id}: ✅ Completed: {video_title}")
                else:
                    self.failed_count += 1
                    self.stats.increment_failed()
                    print(f"Worker {self.worker_id}: ❌ Failed: {video_title}")
                
                # Update shared state (legacy pattern)
                self._update_shared_state_simple()
                
                # Add delay
                if i < len(urls) and self.config.delay > 0:
                    self.stats.update_activity("waiting")
                    await asyncio.sleep(self.config.delay)
            
            # Cleanup
            await processor.cleanup()
            
            self.stats.update_activity("completed")
            print(f"Worker {self.worker_id}: 🎉 Completed {self.successful_count}/{len(urls)} URLs")
            
            return self.stats
            
        except Exception as e:
            self.stats.update_activity("error")
            print(f"❌ Worker {self.worker_id} error: {e}")
            return self.stats
    
    def _update_shared_state_simple(self):
        """Simple shared state update like legacy code"""
        try:
            if 'workers' not in self.shared_state:
                self.shared_state['workers'] = {}
            
            # Simple worker data like legacy
            self.shared_state['workers'][self.worker_id] = {
                'completed': self.successful_count,
                'failed': self.failed_count,
                'status': self.stats.status,
                'transcription_enabled': self.config.use_whisper
            }
            
            # Update totals
            workers = self.shared_state.get('workers', {})
            total_completed = sum(w.get('completed', 0) for w in workers.values())
            total_failed = sum(w.get('failed', 0) for w in workers.values())
            
            self.shared_state['total_completed'] = total_completed
            self.shared_state['total_failed'] = total_failed
            
        except Exception:
            pass  # Ignore shared state update errors
    
    def _update_shared_state(self):
        """Update shared state with worker progress"""
        try:
            if 'workers' not in self.shared_state:
                self.shared_state['workers'] = {}
            
            # Include transcription capability status
            worker_data = {
                'completed': self.stats.completed_count,
                'failed': self.stats.failed_count,
                'skipped': self.stats.skipped_count,
                'status': self.stats.status,
                'last_activity': self.stats.last_activity,
                'transcription_enabled': self.config.use_whisper
            }
            
            self.shared_state['workers'][self.worker_id] = worker_data
            
            # Update totals
            total_completed = sum(
                w.get('completed', 0) for w in self.shared_state['workers'].values()
            )
            total_failed = sum(
                w.get('failed', 0) for w in self.shared_state['workers'].values()
            )
            
            self.shared_state['total_completed'] = total_completed
            self.shared_state['total_failed'] = total_failed
            
        except Exception:
            pass  # Ignore shared state update errors


def worker_function(worker_id: int, urls: List[str], config_dict: Dict[str, Any], 
                   shutdown_event: mp.Event, shared_state: Dict) -> WorkerStats:
    """Simplified worker function based on legacy patterns"""
    output_capture = None
    try:
        # Ubuntu environment fixes - applied early like legacy code
        import os
        import sys
        
        # Set environment variables first (legacy pattern)
        if not os.environ.get('TERM'):
            os.environ['TERM'] = 'xterm-256color'
        if not os.environ.get('LANG'):
            os.environ['LANG'] = 'en_US.UTF-8'
        if not os.environ.get('LC_ALL'):
            os.environ['LC_ALL'] = 'C.UTF-8'
        os.environ['PYTHONUNBUFFERED'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        
        # Setup output capture for this worker process
        output_capture = OutputCapture(worker_id, shared_state)
        
        # Redirect stdout and stderr to capture all output
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = output_capture
        sys.stderr = output_capture
        
        # Simple asyncio setup (legacy pattern)
        import asyncio
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Create new event loop for this worker (cleaner than trying to reuse)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Reconstruct config from dict
            config = TikTokConfig()
            for key, value in config_dict.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # Create simplified worker using legacy patterns
            worker = SimplifiedWorkerProcess(worker_id, config, shared_state)
            worker.shutdown_event = shutdown_event
            
            # Run processing
            result = loop.run_until_complete(worker.process_urls(urls))
            
            # Restore original stdout/stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            return result
            
        finally:
            loop.close()
        
    except Exception as e:
        # Simple error handling like legacy
        print(f"❌ Worker {worker_id} fatal error: {e}")
        stats = WorkerStats(worker_id)
        stats.status = "fatal_error"
        return stats
    finally:
        # Ensure output capture is closed
        if output_capture:
            output_capture.close()


class LiveMonitor:
    """Live progress monitor for multiprocessing"""
    
    def __init__(self, num_workers: int, total_urls: int, error_handler=None, master_log=None):
        self.num_workers = num_workers
        self.total_urls = total_urls
        self.start_time = time.time()
        self.running = False
        self.error_handler = error_handler
        self.master_log = master_log
    
    def start_monitoring(self, shared_state: Dict):
        """Start live monitoring in separate thread"""
        self.running = True
        
        def monitor_loop():
            while self.running:
                try:
                    self._display_progress(shared_state)
                    time.sleep(2)  # Update every 2 seconds
                except Exception:
                    pass
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        return monitor_thread
    
    def stop_monitoring(self):
        """Stop live monitoring"""
        self.running = False
    
    def _display_progress(self, shared_state: Dict):
        """Display current progress"""
        try:
            import os
            
            # Clear screen
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Calculate stats
            elapsed = time.time() - self.start_time
            total_completed = shared_state.get('total_completed', 0)
            total_failed = shared_state.get('total_failed', 0)
            
            rate = (total_completed * 60 / elapsed) if elapsed > 0 else 0
            elapsed_seconds = int(elapsed)
            hours = elapsed_seconds // 3600
            minutes = (elapsed_seconds % 3600) // 60
            seconds = elapsed_seconds % 60
            
            # Format elapsed time as HH:MM:SS or MM:SS
            if hours > 0:
                elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                elapsed_str = f"{minutes:02d}:{seconds:02d}"
            
            # Calculate total per worker for display
            urls_per_worker = self.total_urls // self.num_workers
            remaining_urls = self.total_urls % self.num_workers
            
            # Top progress section
            print("🚀 TikTok Scraper - Multiprocess Mode")
            print("="*60)
            print(f"Progress: {total_completed + total_failed}/{self.total_urls}")
            print(f"✅ Completed: {total_completed}  ❌ Failed: {total_failed}")
            print(f"📈 Rate: {rate:.1f} videos/min  ⏱️  Elapsed: {elapsed_str}")
            print("="*60)
            
            # Worker status with console output and transcription info
            workers = shared_state.get('workers', {})
            worker_logs = shared_state.get('worker_logs', {})
            for i in range(self.num_workers):
                worker_data = workers.get(i, {})
                completed = worker_data.get('completed', 0)
                failed = worker_data.get('failed', 0)
                transcription_enabled = worker_data.get('transcription_enabled', False)
                
                # Calculate total for this worker
                worker_total = urls_per_worker + (1 if i < remaining_urls else 0)
                worker_processed = completed + failed
                
                # Show transcription status
                transcription_icon = "🎤" if transcription_enabled else "🔇"
                print(f"Worker {i}: ({worker_processed}/{worker_total}) {transcription_icon}")
                
                # Show recent activity logs
                logs = worker_logs.get(i, [])
                if logs and len(logs) > 0:
                    # Show up to 3 most recent logs, most recent first
                    recent_logs = logs[-3:] if len(logs) >= 3 else logs
                    for j, log in enumerate(reversed(recent_logs)):
                        if j == 0:
                            # First line gets the tree symbol
                            print(f"⎿ {log}")
                        else:
                            # Subsequent lines get proper spacing alignment
                            print(f"  {log}")
                else:
                    status = worker_data.get('status', 'idle')
                    print(f"⎿ Status: {status}")
                print()  # Add spacing between workers
            
            print("="*60)
            
            # Errors section at the bottom
            if self.error_handler and self.error_handler.errors:
                print("=[Errors]=================================================")
                # Show last 5 errors/warnings
                recent_errors = self.error_handler.errors[-5:]
                for error in recent_errors:
                    timestamp = error['timestamp'][:19]  # Remove microseconds
                    icon = "🚨" if error.get('critical') else "⚠️" if error['type'] == 'Warning' else "❌"
                    print(f"{icon} [{timestamp}] {error['message']}")
                print("="*60)
            
        except Exception:
            pass
    
    def show_final_summary(self, shared_state: Dict, summary: ProcessingSummary):
        """Show final completion summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("🎉 MULTIPROCESS PROCESSING COMPLETE")
        print("="*60)
        print(f"✅ Successful: {summary.successful_count}")
        print(f"❌ Failed: {summary.failed_count}")
        print(f"⏭️  Skipped: {summary.skipped_count}")
        print(f"📊 Total: {summary.total_urls}")
        print(f"⏱️  Time: {elapsed/60:.1f} minutes")
        print(f"📈 Rate: {(summary.successful_count * 60 / elapsed):.1f} videos/min")
        print(f"🎯 Success Rate: {summary.success_rate:.1f}%")
        
        # Show transcription worker summary
        workers = shared_state.get('workers', {})
        transcription_workers = sum(1 for w in workers.values() if w.get('transcription_enabled', False))
        print(f"🎤 Transcription Workers: {transcription_workers}/{len(workers)}")
        print("="*60)
        
        # Log final summary to master log
        try:
            with open(self.master_log, 'a') as f:
                f.write(f"\n=== Final Summary at {datetime.now().isoformat()} ===\n")
                f.write(f"Successful: {summary.successful_count}\n")
                f.write(f"Failed: {summary.failed_count}\n")
                f.write(f"Skipped: {summary.skipped_count}\n")
                f.write(f"Total: {summary.total_urls}\n")
                f.write(f"Time: {elapsed/60:.1f} minutes\n")
                f.write(f"Success Rate: {summary.success_rate:.1f}%\n")
                f.write(f"Transcription Workers: {transcription_workers}/{len(workers)}\n")
                f.write("\nWorker Log Files Created:\n")
                for i in range(len(workers)):
                    worker_log = os.path.join("multiprocess-logs", f"worker_{i}.log")
                    if os.path.exists(worker_log):
                        f.write(f"  - {worker_log}\n")
                f.write("\nCheck individual worker logs for detailed transcription debugging.\n")
        except Exception as e:
            print(f"Warning: Could not write to master log: {e}")


class MultiprocessCoordinator:
    """Coordinates multiple worker processes with comprehensive logging"""
    
    def __init__(self, config: TikTokConfig, error_handler: ErrorHandler = None):
        self.config = config
        self.error_handler = error_handler or ErrorHandler()
        self.num_workers = config.workers
        self.shutdown_event = mp.Event()
        self.manager = mp.Manager()
        self.shared_state = self.manager.dict()
        self.monitor = None
        
        # Initialize shared state
        self.shared_state['workers'] = self.manager.dict()
        self.shared_state['worker_logs'] = self.manager.dict()
        self.shared_state['total_completed'] = 0
        self.shared_state['total_failed'] = 0
        
        # Create master log file for coordination events
        self.log_dir = "multiprocess-logs"
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.master_log = os.path.join(self.log_dir, f"master_{timestamp}.log")
        
        try:
            with open(self.master_log, 'w') as f:
                f.write(f"=== Multiprocess Coordinator Log Started at {datetime.now().isoformat()} ===\n")
                f.write(f"Workers: {self.num_workers}\n")
                f.write(f"Whisper enabled: {config.use_whisper}\n")
                f.write(f"Force CPU: {config.force_cpu}\n")
                f.write("\n")
        except Exception as e:
            print(f"Warning: Could not create master log file: {e}")
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        self.shutdown_count = 0
        
        def signal_handler(signum, frame):
            """Handle SIGINT (Ctrl+C) - graceful then force shutdown"""
            self.shutdown_count += 1
            self.shutdown_event.set()
            
            if self.shutdown_count == 1:
                print(f"\n🛑 Graceful shutdown initiated...")
                print("   Workers will finish current tasks and exit")
                print("   Press Ctrl+C again for immediate force termination")
            else:
                print(f"\n🚨 FORCE SHUTDOWN - Terminating all workers immediately...")
                
                # Force kill all processes immediately
                if hasattr(self, '_current_processes'):
                    for i, process in enumerate(self._current_processes):
                        if process.is_alive():
                            print(f"   Force killing worker {i}...")
                            process.kill()
                            process.join(timeout=1)
                
                print("✅ All workers terminated. Exiting...")
                import sys
                sys.exit(0)
                
        signal.signal(signal.SIGINT, signal_handler)
    
    def _handle_graceful_shutdown(self, processes, summary):
        """Handle graceful shutdown with escalating force"""
        print(f"\n🛑 Shutdown detected (attempt {self.shutdown_count}) - initiating shutdown...")
        
        # Ensure shutdown event is set
        self.shutdown_event.set()
        
        # Stop monitoring immediately
        if self.monitor:
            self.monitor.stop_monitoring()
        
        # Clear screen and show shutdown message
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        
        if self.shutdown_count == 1:
            print("🛑 Shutting down TikTok Scraper...")
            print("⏳ Waiting for workers to finish current tasks...")
            print("   (Press Ctrl+C again for immediate termination)")
            
            # Give workers time to finish gracefully
            for i, process in enumerate(processes):
                if process.is_alive():
                    print(f"   Stopping worker {i}...")
                    process.join(timeout=5)  # Longer timeout for graceful shutdown
                    if process.is_alive():
                        print(f"   Terminating worker {i}...")
                        process.terminate()
                        process.join(timeout=2)
                        if process.is_alive():
                            print(f"   Force killing worker {i}...")
                            process.kill()
        else:
            # Second Ctrl+C - immediate hard shutdown
            print("🚨 IMMEDIATE SHUTDOWN REQUESTED")
            print("⚡ Force terminating all workers...")
            
            for i, process in enumerate(processes):
                if process.is_alive():
                    print(f"   Force killing worker {i}...")
                    process.kill()
                    process.join(timeout=1)
        
        print("✅ All workers stopped. Shutdown complete.")
        return summary
    
    def distribute_urls(self, urls: List[str]) -> List[List[str]]:
        """Distribute URLs among workers"""
        if self.num_workers == 1:
            return [urls]
        
        chunk_size = len(urls) // self.num_workers
        url_chunks = []
        
        for i in range(self.num_workers):
            start_idx = i * chunk_size
            if i == self.num_workers - 1:  # Last worker gets remaining URLs
                end_idx = len(urls)
            else:
                end_idx = (i + 1) * chunk_size
            
            chunk = urls[start_idx:end_idx]
            if chunk:  # Only add non-empty chunks
                url_chunks.append(chunk)
        
        return url_chunks
    
    async def process_urls_multiprocess(self, urls: List[str]) -> ProcessingSummary:
        """Process URLs using multiple worker processes"""
        summary = ProcessingSummary()
        summary.total_urls = len(urls)
        summary.started_at = datetime.now().isoformat()
        
        try:
            self.error_handler.handle_info(
                f"Starting multiprocess processing with {self.num_workers} workers",
                "Multiprocess"
            )
            
            # Distribute URLs
            url_chunks = self.distribute_urls(urls)
            actual_workers = len(url_chunks)
            
            # Start live monitoring
            self.monitor = LiveMonitor(actual_workers, len(urls), self.error_handler, self.master_log)
            monitor_thread = self.monitor.start_monitoring(self.shared_state)
            
            # Start worker processes
            processes = []
            config_dict = self.config.__dict__.copy()  # Convert to dict for multiprocessing
            
            for i, chunk in enumerate(url_chunks):
                process = mp.Process(
                    target=worker_function,
                    args=(i, chunk, config_dict, self.shutdown_event, self.shared_state)
                )
                process.start()
                processes.append(process)
            
            # Store processes for signal handler access
            self._current_processes = processes
            
            # Wait for processes to complete
            while any(p.is_alive() for p in processes):
                # Check for shutdown signal
                if self.shutdown_event.is_set():
                    # Stop monitoring
                    if self.monitor:
                        self.monitor.stop_monitoring()
                    
                    print("\n🛑 Graceful shutdown in progress...")
                    print("   Waiting for workers to finish current tasks...")
                    
                    # Give workers reasonable time to finish gracefully
                    import time
                    start_time = time.time()
                    timeout = 30  # 30 seconds for graceful shutdown
                    
                    while any(p.is_alive() for p in processes) and (time.time() - start_time) < timeout:
                        remaining = int(timeout - (time.time() - start_time))
                        alive_workers = [i for i, p in enumerate(processes) if p.is_alive()]
                        print(f"   Waiting for workers {alive_workers} to finish... ({remaining}s remaining)")
                        
                        for process in processes:
                            process.join(timeout=2)
                        
                        time.sleep(1)
                    
                    # If workers are still alive after timeout, terminate them
                    remaining_workers = [i for i, p in enumerate(processes) if p.is_alive()]
                    if remaining_workers:
                        print(f"   Timeout reached. Terminating workers {remaining_workers}...")
                        for i, process in enumerate(processes):
                            if process.is_alive():
                                process.terminate()
                                process.join(timeout=3)
                                if process.is_alive():
                                    print(f"   Force killing worker {i}...")
                                    process.kill()
                    
                    print("✅ Graceful shutdown completed.")
                    return summary
                
                # Brief wait and check processes
                for process in processes:
                    process.join(timeout=0.1)  # Check every 0.1 seconds for faster response
            
            # Stop monitoring
            self.monitor.stop_monitoring()
            monitor_thread.join(timeout=2)
            
            # Aggregate results
            summary.successful_count = self.shared_state.get('total_completed', 0)
            summary.failed_count = self.shared_state.get('total_failed', 0)
            summary.finalize()
            
            # Show final summary
            self.monitor.show_final_summary(self.shared_state, summary)
            
            # Print log file locations for analysis
            print("\n📁 ANALYSIS LOGS CREATED:")
            print(f"  Master Log: {self.master_log}")
            for i in range(self.num_workers):
                worker_log = os.path.join(self.log_dir, f"worker_{i}.log")
                if os.path.exists(worker_log):
                    print(f"  Worker {i}: {worker_log}")
            print("\nThese logs contain ALL console output for debugging transcription issues.")
            print("Check worker logs for detailed Whisper transcription processes.\n")
            
            # Perform cleanup
            storage = StorageManager(self.config.master_file, self.error_handler)
            storage.auto_cleanup()
            
            return summary
            
        except Exception as e:
            self.error_handler.handle_error(e, "Multiprocess", critical=True)
            summary.finalize()
            return summary


async def run_multiprocess_processing(config: TikTokConfig) -> ProcessingSummary:
    """Run multiprocess processing workflow"""
    error_handler = ErrorHandler(verbose=config.verbose)
    
    # Check for MS_TOKEN and prompt if needed
    if not config.ms_token:
        from .comments import CommentExtractor
        comment_extractor = CommentExtractor(None, error_handler)
        token = comment_extractor.get_interactive_token()
        if token:
            config.ms_token = token
            error_handler.handle_success("MS_TOKEN configured for multiprocess mode", "Setup")
        else:
            error_handler.handle_info("Proceeding without comment extraction", "Setup")
    
    coordinator = MultiprocessCoordinator(config, error_handler)
    
    # Load URLs
    processor = TikTokProcessor(config)
    await processor.initialize()
    urls = processor.load_urls_to_process()
    
    if not urls:
        error_handler.handle_warning("No URLs to process", "Multiprocess")
        return ProcessingSummary()
    
    # Process with multiprocessing
    return await coordinator.process_urls_multiprocess(urls)