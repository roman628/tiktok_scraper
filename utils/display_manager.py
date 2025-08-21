"""
Enhanced display manager for TikTok scraper with rich text output.
Provides responsive grid layout for multiple workers with individual progress tracking.
"""

import math
import signal
import shutil
import time
import threading
from collections import deque
from datetime import datetime
from multiprocessing import Queue
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.columns import Columns
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.table import Table


@dataclass
class WorkerState:
    """State information for a single worker"""
    worker_id: int
    status: str = 'idle'  # idle, processing, completed, error
    current_url: Optional[str] = None
    completed_urls: int = 0
    total_urls: int = 0
    current_stage: str = 'Waiting'
    current_url_progress: float = 0.0  # 0-100 for current URL
    log_buffer: deque = field(default_factory=lambda: deque(maxlen=20))
    last_update: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    stage_details: Optional[str] = None
    flash_complete: bool = False
    flash_count: int = 0
    flash_time: float = 0


class DisplayManager:
    """Manages rich text display for multiple worker processes"""
    
    # Processing stages with their weight percentages
    URL_STAGES = [
        ('validating', 5),
        ('downloading', 30),
        ('metadata', 10),
        ('transcribing', 40),
        ('comments', 10),
        ('saving', 5),
    ]
    
    # Minimum dimensions for worker panels
    MIN_WORKER_WIDTH = 40
    MAX_WORKER_WIDTH = 80
    MIN_WORKER_HEIGHT = 3
    MAX_WORKER_HEIGHT = 12
    
    def __init__(self, num_workers: int, total_urls: int, 
                 raw_log_path: Optional[str] = None,
                 refresh_rate: int = 10):
        """
        Initialize the display manager.
        
        Args:
            num_workers: Number of worker processes
            total_urls: Total number of URLs to process
            raw_log_path: Optional path for raw log output
            refresh_rate: Display refresh rate in Hz
        """
        self.console = Console()
        self.num_workers = num_workers
        self.total_urls = total_urls
        self.refresh_rate = refresh_rate
        self.lock = threading.Lock()
        
        # Calculate URLs per worker
        base_urls_per_worker = total_urls // num_workers
        extra_urls = total_urls % num_workers
        
        # Initialize worker states with correct URL counts
        self.workers: Dict[int, WorkerState] = {}
        for i in range(num_workers):
            # Each worker gets base amount plus one extra if needed
            worker_url_count = base_urls_per_worker + (1 if i < extra_urls else 0)
            self.workers[i] = WorkerState(
                worker_id=i,
                total_urls=worker_url_count  # This worker's allocation, not global total
            )
        
        # Raw logging setup
        self.raw_log = None
        if raw_log_path:
            self.raw_log = open(raw_log_path, 'w')
            self.write_raw_log(f"Display Manager initialized with {num_workers} workers")
            self.write_raw_log(f"Processing {total_urls} URLs")
        
        # Terminal dimensions tracking
        self.last_dimensions = (0, 0)
        self.layout_config = None
        self.resize_pending = False  # Flag for pending resize
        
        # Live display
        self.live = None
        
        # Setup resize handler
        try:
            signal.signal(signal.SIGWINCH, self.handle_resize)
        except:
            pass  # Windows doesn't support SIGWINCH
    
    def write_raw_log(self, message: str):
        """Write to raw log file if enabled"""
        if self.raw_log:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            self.raw_log.write(f"[{timestamp}] {message}\n")
            self.raw_log.flush()
    
    def calculate_layout(self, terminal_width: int, terminal_height: int) -> Dict:
        """
        Calculate optimal grid layout for worker panels.
        
        Returns:
            Dictionary with layout configuration
        """
        # Calculate possible columns
        max_columns = terminal_width // self.MIN_WORKER_WIDTH
        optimal_columns = min(max_columns, self.num_workers)
        
        # Ensure at least 1 column
        if optimal_columns < 1:
            optimal_columns = 1
        
        # Calculate panel width
        panel_width = min(
            terminal_width // optimal_columns - 2,  # Account for padding
            self.MAX_WORKER_WIDTH
        )
        
        # Calculate rows needed
        rows_needed = math.ceil(self.num_workers / optimal_columns)
        
        # Calculate panel height
        available_height = terminal_height - 3  # Reserve for header/footer
        panel_height = min(
            available_height // rows_needed,
            self.MAX_WORKER_HEIGHT
        )
        
        # Adjust if panels are too short and we can reduce columns
        if panel_height < self.MIN_WORKER_HEIGHT and optimal_columns > 1:
            # Try with fewer columns
            optimal_columns -= 1
            rows_needed = math.ceil(self.num_workers / optimal_columns)
            panel_width = min(
                terminal_width // optimal_columns - 2,
                self.MAX_WORKER_WIDTH
            )
            panel_height = min(
                available_height // rows_needed,
                self.MAX_WORKER_HEIGHT
            )
        
        # Ensure minimum height
        panel_height = max(panel_height, self.MIN_WORKER_HEIGHT)
        
        return {
            'columns': optimal_columns,
            'rows': rows_needed,
            'panel_width': panel_width,
            'panel_height': panel_height,
            'console_lines': self.calculate_console_lines(panel_height)
        }
    
    def calculate_console_lines(self, panel_height: int) -> int:
        """Calculate how many console output lines to show"""
        RESERVED_LINES = 3  # URL line, progress bar, minimum spacing
        
        available = panel_height - RESERVED_LINES
        
        if available <= 0:
            return 0
        elif available <= 3:
            return available
        else:
            return min(available, 10)
    
    def create_progress_bar(self, progress: float, width: int = 20) -> str:
        """Create a text-based progress bar"""
        filled = int(progress * width / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
    
    def format_worker_panel(self, worker: WorkerState, 
                           panel_width: int, console_lines: int) -> Panel:
        """
        Format a single worker's display panel.
        
        Args:
            worker: Worker state information
            panel_width: Width of the panel
            console_lines: Number of console output lines to show
        
        Returns:
            Rich Panel object
        """
        lines = []
        
        # Line 1: URL (without counter since it's in header now)
        if worker.current_url:
            # Use full available panel width
            max_url_length = panel_width - 4  # Just leave some padding
            
            url_display = worker.current_url
            if len(url_display) > max_url_length:
                # Only truncate if absolutely necessary
                url_display = url_display[:max_url_length]
            
            # Create URL line
            url_line = Text()
            url_line.append(url_display, style="bright_blue")
            lines.append(url_line)
        else:
            lines.append(Text("Waiting for URL", style="dim"))
        
        # Line 2: Progress bar + percentage + stage
        progress_bar = self.create_progress_bar(worker.current_url_progress)
        progress_text = Text()
        progress_text.append(progress_bar, style="cyan")
        progress_text.append(f" {worker.current_url_progress:.0f}% ", style="bright_yellow")
        progress_text.append(worker.current_stage, style="white")
        lines.append(progress_text)
        
        # Console output lines (newest at bottom)
        if console_lines > 0 and worker.log_buffer:
            # Get the most recent entries (newest last)
            recent_logs = list(worker.log_buffer)
            if len(recent_logs) > console_lines:
                # Take only the most recent ones
                recent_logs = recent_logs[-console_lines:]
            
            for i, log_entry in enumerate(recent_logs):
                # Format log entries with proper indentation
                if isinstance(log_entry, dict):
                    level = log_entry.get('level', 'info')
                    message = log_entry.get('message', '')
                    
                    log_line = Text()
                    
                    # First line uses ╰, rest use proper spacing
                    if i == 0:
                        if level == 'success':
                            log_line.append("╰ ✓ ", style="green")
                            log_line.append(message, style="dim green")
                        elif level == 'error':
                            log_line.append("╰ ✗ ", style="red")
                            log_line.append(message, style="dim red")
                        elif level == 'progress':
                            log_line.append("╰ ⟳ ", style="yellow")
                            log_line.append(message, style="dim yellow")
                        else:
                            log_line.append("╰ ", style="dim")
                            log_line.append(message, style="dim")
                    else:
                        # Subsequent lines are indented to align
                        if level == 'success':
                            log_line.append("  ✓ ", style="green")
                            log_line.append(message, style="dim green")
                        elif level == 'error':
                            log_line.append("  ✗ ", style="red")
                            log_line.append(message, style="dim red")
                        elif level == 'progress':
                            log_line.append("  ⟳ ", style="yellow")
                            log_line.append(message, style="dim yellow")
                        else:
                            log_line.append("    ", style="dim")
                            log_line.append(message, style="dim")
                    
                    lines.append(log_line)
                else:
                    # Plain text entry
                    if i == 0:
                        lines.append(Text("╰ " + str(log_entry), style="dim"))
                    else:
                        lines.append(Text("  " + str(log_entry), style="dim"))
        
        # Determine border style based on status (default to grey)
        # Check if we should flash green (URL just completed)
        if hasattr(worker, 'flash_complete') and worker.flash_complete:
            # Flash green for recently completed URLs
            border_style = "green"
        elif worker.status == 'processing':
            border_style = "bright_blue"
        elif worker.status == 'completed':
            border_style = "green"
        elif worker.status == 'error':
            border_style = "red"
        else:
            # Default to a darker grey (not purple)
            border_style = "bright_black"  # This gives a true grey color
        
        # Create panel with counter in title
        title = f"Worker {worker.worker_id + 1} ({worker.completed_urls}/{worker.total_urls})"
        panel_content = "\n".join(str(line) for line in lines)
        return Panel(
            panel_content,
            title=title,
            title_align="left",  # Align title to the left
            border_style=border_style,
            width=panel_width,
            height=self.layout_config['panel_height'] if self.layout_config else None
        )
    
    def render_display(self) -> Columns:
        """Render the complete display with all worker panels"""
        # Update layout configuration
        terminal_size = shutil.get_terminal_size()
        self.layout_config = self.calculate_layout(
            terminal_size.columns,
            terminal_size.lines
        )
        
        # Create panels for each worker
        panels = []
        for worker_id in sorted(self.workers.keys()):
            worker = self.workers[worker_id]
            panel = self.format_worker_panel(
                worker,
                self.layout_config['panel_width'],
                self.layout_config['console_lines']
            )
            panels.append(panel)
        
        # Use Columns for automatic wrapping
        if self.layout_config['columns'] > 1:
            columns = Columns(
                panels,
                equal=True,
                expand=False,
                column_first=True  # Fill left to right, then top to bottom
            )
            return columns
        else:
            # Single column - return as group
            return Group(*panels)
    
    def handle_resize(self, signum, frame):
        """Handle terminal resize events"""
        # Just set a flag - don't try to refresh directly from signal handler
        self.resize_pending = True
    
    def process_update(self, update: Dict[str, Any]):
        """
        Process an update message from a worker.
        
        Args:
            update: Dictionary containing update information
        """
        with self.lock:
            update_type = update.get('type')
            worker_id = update.get('worker_id')
            
            if worker_id is None or worker_id not in self.workers:
                return
            
            worker = self.workers[worker_id]
            
            # Write to raw log
            self.write_raw_log(f"[Worker {worker_id}] {update}")
            
            if update_type == 'start':
                worker.status = 'processing'
                worker.current_url = update.get('url')
                worker.current_stage = 'Starting'
            
            elif update_type == 'status':
                worker.status = update.get('status', worker.status)
                if update.get('stage'):
                    worker.current_stage = update['stage']
            
            elif update_type == 'progress':
                worker.current_url_progress = update.get('progress', 0)
                if 'completed_urls' in update:
                    worker.completed_urls = update['completed_urls']
                if 'stage' in update:
                    worker.current_stage = update['stage']
                if 'stage_details' in update:
                    worker.stage_details = update['stage_details']
            
            elif update_type == 'log':
                log_entry = {
                    'level': update.get('level', 'info'),
                    'message': update.get('message', ''),
                    'timestamp': time.time()
                }
                worker.log_buffer.append(log_entry)
            
            elif update_type == 'error':
                worker.status = 'error'
                worker.error_message = update.get('error', 'Unknown error')
                worker.log_buffer.append({
                    'level': 'error',
                    'message': worker.error_message
                })
            
            elif update_type == 'complete':
                worker.completed_urls = update.get('completed_urls', worker.completed_urls)
                worker.current_url_progress = 100
                worker.log_buffer.append({
                    'level': 'success',
                    'message': f"Completed URL {worker.completed_urls}/{worker.total_urls}"
                })
                # Start flash animation
                worker.flash_complete = True
                worker.flash_count = 6  # Flash 3 times (on/off = 6 transitions)
                worker.flash_time = time.time()
                # Reset for next URL
                worker.current_url = None
                worker.current_url_progress = 0
                worker.current_stage = 'Waiting for next URL'
            
            worker.last_update = time.time()
    
    def start(self):
        """Start the live display"""
        self.live = Live(
            self.render_display(),
            console=self.console,
            refresh_per_second=self.refresh_rate,
            transient=False
        )
        self.live.start()
        self.write_raw_log("Display started")
    
    def stop(self):
        """Stop the live display"""
        if self.live:
            self.live.stop()
            self.write_raw_log("Display stopped")
        
        if self.raw_log:
            self.raw_log.close()
    
    def update(self):
        """Update the display (call after processing updates)"""
        with self.lock:
            if self.live:
                # Check if terminal was resized
                if self.resize_pending:
                    terminal_size = shutil.get_terminal_size()
                    new_dimensions = (terminal_size.columns, terminal_size.lines)
                    
                    if new_dimensions != self.last_dimensions:
                        self.last_dimensions = new_dimensions
                        # Force layout recalculation on next render
                        self.layout_config = None
                    
                    self.resize_pending = False
                
                # Handle flash animations
                current_time = time.time()
                for worker in self.workers.values():
                    if worker.flash_complete and worker.flash_count > 0:
                        # Flash every 0.15 seconds
                        if current_time - worker.flash_time > 0.15:
                            worker.flash_count -= 1
                            worker.flash_time = current_time
                            # Toggle flash state
                            worker.flash_complete = not worker.flash_complete if worker.flash_count > 0 else False
                
                # Update display with new content
                self.live.update(self.render_display())
    
    def get_summary(self) -> Dict:
        """Get summary statistics of all workers"""
        total_completed = sum(w.completed_urls for w in self.workers.values())
        active_workers = sum(1 for w in self.workers.values() if w.status == 'processing')
        error_count = sum(1 for w in self.workers.values() if w.status == 'error')
        
        return {
            'total_completed': total_completed,
            'total_urls': self.total_urls,
            'active_workers': active_workers,
            'error_count': error_count,
            'workers': self.num_workers
        }


class SimpleDisplay:
    """Fallback simple display for non-TTY environments"""
    
    def __init__(self, num_workers: int, total_urls: int, 
                 raw_log_path: Optional[str] = None):
        self.num_workers = num_workers
        self.total_urls = total_urls
        
        # Calculate URLs per worker
        base_urls_per_worker = total_urls // num_workers
        extra_urls = total_urls % num_workers
        
        # Track each worker's allocation
        self.workers = {}
        for i in range(num_workers):
            worker_url_count = base_urls_per_worker + (1 if i < extra_urls else 0)
            self.workers[i] = {'total': worker_url_count, 'completed': 0}
        
        self.last_print_time = 0
        self.print_interval = 2.0  # Seconds between status prints
        
        self.raw_log = None
        if raw_log_path:
            self.raw_log = open(raw_log_path, 'w')
    
    def process_update(self, update: Dict[str, Any]):
        """Process updates in simple mode"""
        worker_id = update.get('worker_id')
        update_type = update.get('type')
        
        if update_type == 'log':
            message = update.get('message', '')
            level = update.get('level', 'info')
            print(f"[Worker {worker_id}] [{level.upper()}] {message}")
            
            if self.raw_log:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.raw_log.write(f"[{timestamp}] [Worker {worker_id}] [{level}] {message}\n")
                self.raw_log.flush()
        
        elif update_type == 'progress':
            # Print progress updates periodically
            current_time = time.time()
            if current_time - self.last_print_time > self.print_interval:
                progress = update.get('progress', 0)
                stage = update.get('stage', 'Processing')
                completed = update.get('completed_urls', 0)
                worker_total = self.workers[worker_id]['total'] if worker_id in self.workers else 0
                print(f"[Worker {worker_id}] {stage} - {progress:.0f}% ({completed}/{worker_total})")
                self.last_print_time = current_time
    
    def start(self):
        """Start simple display (no-op)"""
        print(f"Starting processing with {self.num_workers} workers...")
    
    def stop(self):
        """Stop simple display"""
        if self.raw_log:
            self.raw_log.close()
    
    def update(self):
        """Update simple display (no-op)"""
        pass


def create_display(num_workers: int, total_urls: int, 
                   mode: str = 'auto', 
                   raw_log_path: Optional[str] = None) -> Any:
    """
    Factory function to create appropriate display manager.
    
    Args:
        num_workers: Number of worker processes
        total_urls: Total URLs to process
        mode: Display mode ('rich', 'simple', 'auto')
        raw_log_path: Optional path for raw log output
    
    Returns:
        DisplayManager or SimpleDisplay instance
    """
    if mode == 'simple':
        return SimpleDisplay(num_workers, total_urls, raw_log_path)
    elif mode == 'rich':
        return DisplayManager(num_workers, total_urls, raw_log_path)
    else:  # auto
        # Check if we're in a TTY
        import sys
        if sys.stdout.isatty():
            try:
                return DisplayManager(num_workers, total_urls, raw_log_path)
            except:
                return SimpleDisplay(num_workers, total_urls, raw_log_path)
        else:
            return SimpleDisplay(num_workers, total_urls, raw_log_path)
