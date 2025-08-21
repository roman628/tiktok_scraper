#!/usr/bin/env python3
"""
Visual test for the display manager with simulated workers.
Tests the display layout with different worker counts and fake progress updates.
"""

import time
import random
import threading
import multiprocessing as mp
from multiprocessing import Queue, Process
from datetime import datetime
import argparse
import sys
import os
import signal
import queue

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.display_manager import create_display
from src.worker_progress import WorkerProgress


# Sample TikTok URLs for simulation
SAMPLE_URLS = [
    "https://www.tiktok.com/@charlidamelio/video/7234567890123456789",
    "https://www.tiktok.com/@khaby.lame/video/7234567890123456790",
    "https://www.tiktok.com/@zachking/video/7234567890123456791",
    "https://www.tiktok.com/@bellapoarch/video/7234567890123456792",
    "https://www.tiktok.com/@addisonre/video/7234567890123456793",
    "https://www.tiktok.com/@spencerx/video/7234567890123456794",
    "https://www.tiktok.com/@cznburak/video/7234567890123456795",
    "https://www.tiktok.com/@kimberly.loaiza/video/7234567890123456796",
    "https://www.tiktok.com/@therock/video/7234567890123456797",
    "https://www.tiktok.com/@willsmith/video/7234567890123456798",
    "https://www.tiktok.com/@jasonderulo/video/7234567890123456799",
    "https://www.tiktok.com/@bts_official_bighit/video/7234567890123456800",
    "https://www.tiktok.com/@justinbieber/video/7234567890123456801",
    "https://www.tiktok.com/@arianagrande/video/7234567890123456802",
    "https://www.tiktok.com/@selenagomez/video/7234567890123456803",
    "https://www.tiktok.com/@katyperry/video/7234567890123456804",
    "https://www.tiktok.com/@dualipa/video/7234567890123456805",
    "https://www.tiktok.com/@jlo/video/7234567890123456806",
    "https://www.tiktok.com/@nickiminaj/video/7234567890123456807",
    "https://www.tiktok.com/@cardib/video/7234567890123456808",
]

# Stages with realistic timings (in seconds)
STAGES = [
    ('validating', 0.5, 1.0),      # Stage name, min time, max time
    ('downloading', 2.0, 5.0),
    ('metadata', 0.5, 1.5),
    ('transcribing', 3.0, 8.0),
    ('comments', 1.0, 3.0),
    ('saving', 0.3, 0.8),
]

# Sample log messages for each stage
STAGE_LOGS = {
    'validating': [
        ('info', 'Checking URL format'),
        ('success', 'URL validated'),
    ],
    'downloading': [
        ('info', 'Connecting to TikTok CDN'),
        ('progress', 'Downloading video stream'),
        ('info', 'Video size: {:.1f} MB'),
        ('success', 'Download complete'),
    ],
    'metadata': [
        ('progress', 'Extracting video metadata'),
        ('info', 'Duration: {} seconds'),
        ('success', 'Metadata extracted ({} likes, {} comments)'),
    ],
    'transcribing': [
        ('info', 'Loading Whisper model'),
        ('progress', 'Transcribing audio with Whisper base'),
        ('progress', 'Processing audio segments'),
        ('success', 'Transcription complete'),
    ],
    'comments': [
        ('info', 'Fetching comments from API'),
        ('progress', 'Processing comment threads'),
        ('success', 'Retrieved {} comments'),
    ],
    'saving': [
        ('progress', 'Writing to master2.json'),
        ('success', 'Data saved successfully'),
    ],
}


def simulate_worker(worker_id: int, url_queue: Queue, display_queue: Queue, 
                   shutdown_event, total_urls: int, speed_multiplier: float = 1.0,
                   error_rate: float = 0.1):
    """
    Simulate a worker processing URLs with fake progress updates.
    
    Args:
        worker_id: Worker identifier
        url_queue: Queue of URLs to process
        display_queue: Queue for display updates
        shutdown_event: Event to signal shutdown
        total_urls: Total URLs assigned to this worker
        speed_multiplier: Speed up/slow down processing (1.0 = normal)
        error_rate: Probability of error (0.0 to 1.0)
    """
    # Ignore interrupt signals in worker processes
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    # Initialize progress tracker
    progress = WorkerProgress(worker_id, display_queue, total_urls)
    progress.send_status('initializing')
    
    # Simulate initialization
    time.sleep(0.5 / speed_multiplier)
    progress.send_log('Worker initialized', 'success')
    progress.send_status('idle')
    
    completed = 0
    
    while not shutdown_event.is_set():
        try:
            # Get URL from queue
            url = url_queue.get(timeout=0.5)
            if url is None:  # Poison pill
                break
                
            completed += 1
            progress.start_url(url)
            
            # Randomly determine if this URL will fail
            will_fail = random.random() < error_rate
            fail_at_stage = random.choice(['downloading', 'transcribing']) if will_fail else None
            
            # Process through stages
            for stage_name, min_time, max_time in STAGES:
                if shutdown_event.is_set():
                    break
                
                # Check if we should fail at this stage
                if fail_at_stage == stage_name:
                    progress.send_log(f"Error in {stage_name}", 'error')
                    progress.report_error(stage_name, f"Failed to process {stage_name}")
                    time.sleep(1.0 / speed_multiplier)
                    
                    # Retry logic
                    for retry in range(1, 4):
                        progress.report_retry(retry, 3, f"Connection timeout")
                        time.sleep(0.5 / speed_multiplier)
                        if random.random() > 0.3:  # 70% chance of success on retry
                            progress.send_log(f"Retry successful", 'success')
                            break
                    else:
                        progress.send_log(f"Max retries exceeded, skipping URL", 'error')
                        break
                
                # Normal processing
                stage_duration = random.uniform(min_time, max_time) / speed_multiplier
                
                # Send stage-specific logs
                stage_log_messages = STAGE_LOGS.get(stage_name, [])
                
                # Start of stage
                if stage_name == 'downloading':
                    progress.start_download()
                elif stage_name == 'metadata':
                    progress.start_metadata_extraction()
                elif stage_name == 'transcribing':
                    progress.start_transcription('base')
                elif stage_name == 'comments':
                    progress.start_comments()
                elif stage_name == 'saving':
                    progress.start_saving()
                else:
                    progress.send_progress(stage_name, 0)
                
                # Simulate progress within stage
                steps = random.randint(3, 8)
                for step in range(steps):
                    if shutdown_event.is_set():
                        break
                    
                    step_progress = (step + 1) / steps * 100
                    
                    # Special handling for different stages
                    if stage_name == 'downloading':
                        # Simulate download progress
                        total_mb = random.uniform(10, 50)
                        downloaded_mb = total_mb * step_progress / 100
                        progress.update_download(
                            int(downloaded_mb * 1024 * 1024),
                            int(total_mb * 1024 * 1024)
                        )
                    elif stage_name == 'transcribing':
                        # Simulate transcription progress
                        total_seconds = random.randint(30, 120)
                        current_seconds = total_seconds * step_progress / 100
                        progress.update_transcription(current_seconds, total_seconds)
                    else:
                        progress.send_progress(stage_name, step_progress)
                    
                    # Occasionally send log messages
                    if random.random() < 0.3 and stage_log_messages:
                        log_level, log_msg = random.choice(stage_log_messages)
                        
                        # Format message with random values
                        if '{}' in log_msg:
                            if 'MB' in log_msg:
                                log_msg = log_msg.format(random.uniform(5, 50))
                            elif 'seconds' in log_msg:
                                log_msg = log_msg.format(random.randint(15, 180))
                            elif 'likes' in log_msg:
                                log_msg = log_msg.format(
                                    random.randint(1000, 1000000),
                                    random.randint(10, 10000)
                                )
                            elif 'comments' in log_msg and stage_name == 'comments':
                                log_msg = log_msg.format(random.randint(5, 500))
                            else:
                                log_msg = log_msg.format(random.randint(1, 100))
                        
                        progress.send_log(log_msg, log_level)
                    
                    time.sleep(stage_duration / steps)
                
                # Complete stage
                if stage_name == 'downloading':
                    progress.complete_download(
                        random.uniform(10, 50),
                        random.uniform(2, 10)
                    )
                elif stage_name == 'metadata':
                    progress.complete_metadata(
                        random.randint(1000, 1000000),
                        random.randint(10, 10000)
                    )
                elif stage_name == 'transcribing':
                    progress.complete_transcription(random.randint(30, 120))
                elif stage_name == 'comments':
                    progress.complete_comments(random.randint(10, 500))
                elif stage_name == 'saving':
                    progress.complete_saving()
                
            # Complete URL processing
            if not will_fail:
                progress.complete_url()
                progress.send_log(f"Successfully processed URL {completed}/{total_urls}", 'success')
            
        except queue.Empty:
            continue  # Normal timeout, just continue
        except Exception as e:
            # Only log if we're not shutting down
            try:
                if not shutdown_event.is_set():
                    progress.send_log(f"Worker error: {str(e)[:50]}", 'error')
            except:
                pass  # Ignore errors during shutdown
    
    # Clean shutdown
    try:
        progress.send_status('completed')
        progress.send_log('Worker shutting down', 'info')
    except:
        pass  # Ignore errors during final logging


def run_display_test(num_workers: int = 4, num_urls: int = 20, 
                     speed: float = 1.0, error_rate: float = 0.1,
                     display_mode: str = 'rich', raw_log: bool = False):
    """
    Run the display test with simulated workers.
    
    Args:
        num_workers: Number of worker processes
        num_urls: Total number of URLs to process
        speed: Speed multiplier (higher = faster)
        error_rate: Error rate (0.0 to 1.0)
        display_mode: Display mode (rich, simple, auto)
        raw_log: Whether to save raw log
    """
    print(f"\n{'='*60}")
    print(f"Display Manager Visual Test")
    print(f"{'='*60}")
    print(f"Workers: {num_workers}")
    print(f"URLs: {num_urls}")
    print(f"Speed: {speed}x")
    print(f"Error Rate: {error_rate*100:.0f}%")
    print(f"Display Mode: {display_mode}")
    print(f"Raw Log: {raw_log}")
    print(f"{'='*60}\n")
    
    # Wait for user to be ready
    input("Press Enter to start the test...")
    print("\nStarting in 3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    
    # Create queues and events
    manager = mp.Manager()
    url_queue = manager.Queue()
    display_queue = manager.Queue()
    shutdown_event = manager.Event()
    
    # Prepare URLs
    urls = []
    for i in range(num_urls):
        urls.append(SAMPLE_URLS[i % len(SAMPLE_URLS)])
    
    # Add URLs to queue
    for url in urls:
        url_queue.put(url)
    
    # Create display manager
    raw_log_path = None
    if raw_log:
        raw_log_path = f"test_display_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    display_manager = create_display(
        num_workers,
        num_urls,
        mode=display_mode,
        raw_log_path=raw_log_path
    )
    
    # Calculate URLs per worker
    urls_per_worker = num_urls // num_workers
    extra_urls = num_urls % num_workers
    
    # Start display
    display_manager.start()
    
    # Start worker processes
    workers = []
    for i in range(num_workers):
        worker_urls = urls_per_worker + (1 if i < extra_urls else 0)
        
        worker = Process(
            target=simulate_worker,
            args=(i, url_queue, display_queue, shutdown_event, 
                  worker_urls, speed, error_rate)
        )
        worker.start()
        workers.append(worker)
    
    # Monitor display updates
    try:
        processed = 0
        while processed < num_urls:
            # Process display updates
            try:
                while True:
                    update = display_queue.get_nowait()
                    display_manager.process_update(update)
                    
                    # Check if URL was completed
                    if update.get('type') == 'complete':
                        processed += 1
            except:
                pass
            
            # Update display
            display_manager.update()
            
            # Small delay to prevent CPU spinning
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\nShutting down test...")
        shutdown_event.set()
    
    finally:
        # Signal shutdown
        shutdown_event.set()
        
        # Stop display first
        try:
            display_manager.stop()
        except:
            pass
        
        # Send poison pills to wake up workers
        for _ in range(num_workers):
            try:
                url_queue.put_nowait(None)
            except:
                pass
        
        # Give workers a moment to exit cleanly
        time.sleep(0.5)
        
        # Terminate any remaining workers
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=1)
                if worker.is_alive():
                    try:
                        worker.kill()
                    except:
                        pass
        
        # Print summary
        try:
            summary = display_manager.get_summary()
            print(f"\n{'='*60}")
            print(f"Test Complete!")
            print(f"{'='*60}")
            print(f"Total Completed: {summary['total_completed']}/{summary['total_urls']}")
            print(f"Active Workers: {summary['active_workers']}")
            print(f"Errors: {summary['error_count']}")
            if raw_log_path:
                print(f"Raw log saved to: {raw_log_path}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"\nTest ended (unable to get summary: {e})")


def main():
    """Main entry point for the display test."""
    parser = argparse.ArgumentParser(
        description="Visual test for TikTok scraper display manager"
    )
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)"
    )
    
    parser.add_argument(
        "--urls", "-u",
        type=int,
        default=20,
        help="Number of URLs to process (default: 20)"
    )
    
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=1.0,
        help="Speed multiplier - higher is faster (default: 1.0)"
    )
    
    parser.add_argument(
        "--error-rate", "-e",
        type=float,
        default=0.1,
        help="Error rate from 0.0 to 1.0 (default: 0.1)"
    )
    
    parser.add_argument(
        "--display-mode", "-d",
        choices=["rich", "simple", "auto"],
        default="rich",
        help="Display mode (default: rich)"
    )
    
    parser.add_argument(
        "--raw-log", "-r",
        action="store_true",
        help="Save raw log to file"
    )
    
    parser.add_argument(
        "--continuous", "-c",
        action="store_true",
        help="Run continuous tests with different worker counts"
    )
    
    args = parser.parse_args()
    
    if args.continuous:
        # Run tests with different worker counts
        worker_counts = [1, 2, 3, 4, 6, 8, 10]
        for count in worker_counts:
            print(f"\n{'#'*60}")
            print(f"# Testing with {count} workers")
            print(f"{'#'*60}")
            
            run_display_test(
                num_workers=count,
                num_urls=count * 5,  # 5 URLs per worker
                speed=args.speed,
                error_rate=args.error_rate,
                display_mode=args.display_mode,
                raw_log=args.raw_log
            )
            
            if count < worker_counts[-1]:
                print("\nNext test starting in 5 seconds...")
                print("Press Ctrl+C to stop")
                try:
                    time.sleep(5)
                except KeyboardInterrupt:
                    print("\nTest suite stopped by user")
                    break
    else:
        # Run single test
        run_display_test(
            num_workers=args.workers,
            num_urls=args.urls,
            speed=args.speed,
            error_rate=args.error_rate,
            display_mode=args.display_mode,
            raw_log=args.raw_log
        )


if __name__ == "__main__":
    main()