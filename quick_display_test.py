#!/usr/bin/env python3
"""
Quick visual test for the display manager - simpler version for rapid testing.
"""

import time
import random
import multiprocessing as mp
from multiprocessing import Queue, Process
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.display_manager import create_display
from src.worker_progress import WorkerProgress


def quick_worker(worker_id: int, display_queue: Queue, num_urls: int):
    """Simplified worker for quick testing."""
    progress = WorkerProgress(worker_id, display_queue, num_urls)
    
    # Process URLs
    for i in range(num_urls):
        url = f"https://tiktok.com/@user{worker_id}/video/{7234567890 + i}"
        
        # Start URL
        progress.start_url(url)
        
        # Quick progression through stages
        stages = [
            ('validating', 'Validating URL'),
            ('downloading', 'Downloading video'), 
            ('metadata', 'Extracting metadata'),
            ('transcribing', 'Transcribing audio'),
            ('comments', 'Fetching comments'),
            ('saving', 'Saving to JSON')
        ]
        
        for stage, message in stages:
            # Send some logs
            progress.send_log(message, 'progress')
            
            # Animate progress
            for p in range(0, 101, 20):
                progress.send_progress(stage, p)
                time.sleep(random.uniform(0.1, 0.3))
            
            # Complete stage with success message
            if stage == 'downloading':
                progress.complete_download(
                    random.uniform(10, 30),
                    random.uniform(2, 5)
                )
            elif stage == 'metadata':
                progress.complete_metadata(
                    random.randint(10000, 100000),
                    random.randint(100, 1000)
                )
            elif stage == 'transcribing':
                progress.complete_transcription(random.randint(30, 90))
            elif stage == 'comments':
                progress.complete_comments(random.randint(50, 200))
            
            # Random log messages
            if random.random() < 0.3:
                progress.send_log(f"Stage {stage} info: Processing...", 'info')
        
        # Complete URL
        progress.complete_url()
        time.sleep(0.5)
    
    progress.send_status('completed')


def quick_test(workers=4, urls_per_worker=3):
    """Run a quick display test."""
    print(f"\nQuick Display Test: {workers} workers, {urls_per_worker} URLs each")
    print("="*50)
    
    # Setup
    manager = mp.Manager()
    display_queue = manager.Queue()
    total_urls = workers * urls_per_worker
    
    # Create display
    display = create_display(workers, total_urls, mode='rich')
    display.start()
    
    # Start workers
    processes = []
    for i in range(workers):
        p = Process(target=quick_worker, args=(i, display_queue, urls_per_worker))
        p.start()
        processes.append(p)
    
    # Monitor updates
    try:
        completed = 0
        while completed < total_urls:
            # Process queue
            try:
                while True:
                    update = display_queue.get_nowait()
                    display.process_update(update)
                    if update.get('type') == 'complete':
                        completed += 1
            except:
                pass
            
            display.update()
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        display.stop()
        for p in processes:
            p.terminate()
            p.join()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Quick display test")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Number of workers")
    parser.add_argument("-u", "--urls", type=int, default=3, help="URLs per worker")
    
    args = parser.parse_args()
    quick_test(args.workers, args.urls)