"""
Worker Manager - Robust worker lifecycle and heartbeat management
"""
import time
import multiprocessing as mp
import queue
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

class WorkerManager:
    """Manages worker processes with heartbeat tracking and database-based completion detection"""
    
    def __init__(self, db_config: dict, worker_count: int = 4):
        self.db_config = db_config
        self.worker_count = worker_count
        self.workers: Dict[int, mp.Process] = {}
        self.worker_states: Dict[int, dict] = {}
        self.status_queue = mp.Queue(maxsize=worker_count * 10)  # Lightweight status queue
        self.last_heartbeats: Dict[int, float] = {}
        
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.db_config.get('host', 'localhost'),
            database=self.db_config.get('database', 'tiktok_scraper'),
            user=self.db_config.get('user', 'root'),
            password=self.db_config.get('password', ''),
            cursor_factory=RealDictCursor
        )
    
    def init_worker_tracking_table(self):
        """Create worker tracking table if it doesn't exist"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS worker_status (
                            worker_id INTEGER PRIMARY KEY,
                            status VARCHAR(20) DEFAULT 'idle',
                            last_heartbeat TIMESTAMP DEFAULT NOW(),
                            urls_processed INTEGER DEFAULT 0,
                            current_url TEXT,
                            started_at TIMESTAMP DEFAULT NOW(),
                            completed_at TIMESTAMP
                        )
                    """)
                    # Clear any stale worker entries
                    cur.execute("TRUNCATE TABLE worker_status")
                    conn.commit()
        except Exception as e:
            print(f"Warning: Could not initialize worker_status table: {e}")
            print("Worker tracking will be limited, but processing will continue")
    
    def cleanup_stuck_urls(self):
        """Reset stuck 'processing' URLs to 'pending' on startup"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Reset any URLs stuck in processing state
                    cur.execute("""
                        UPDATE queued_urls 
                        SET status = 'pending', 
                            error_message = 'Reset from stuck processing state'
                        WHERE status = 'processing'
                        RETURNING url
                    """)
                    stuck_urls = cur.fetchall()
                    if stuck_urls:
                        print(f"✓ Reset {len(stuck_urls)} stuck URLs to pending")
                    conn.commit()
        except Exception as e:
            print(f"Warning: Could not cleanup stuck URLs: {e}")
    
    def register_worker(self, worker_id: int):
        """Register a new worker in the database"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO worker_status (worker_id, status, last_heartbeat)
                        VALUES (%s, 'starting', NOW())
                        ON CONFLICT (worker_id) 
                        DO UPDATE SET status = 'starting', last_heartbeat = NOW()
                    """, (worker_id,))
                    conn.commit()
        except Exception as e:
            print(f"Warning: Could not register worker {worker_id}: {e}")
    
    def update_worker_heartbeat(self, worker_id: int, status: str = 'active', current_url: str = None):
        """Update worker heartbeat in database"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE worker_status 
                        SET last_heartbeat = NOW(), 
                            status = %s,
                            current_url = %s
                        WHERE worker_id = %s
                    """, (status, current_url, worker_id))
                    conn.commit()
            self.last_heartbeats[worker_id] = time.time()
        except Exception as e:
            print(f"Failed to update heartbeat for worker {worker_id}: {e}")
    
    def process_status_updates(self, timeout: float = 0.1) -> List[dict]:
        """Process status updates from the status queue"""
        updates = []
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                update = self.status_queue.get(timeout=0.01)
                updates.append(update)
                
                # Process heartbeat updates
                if update.get('type') == 'heartbeat':
                    worker_id = update.get('worker_id')
                    status = update.get('status', 'active')
                    current_url = update.get('current_url')
                    self.update_worker_heartbeat(worker_id, status, current_url)
                    
                elif update.get('type') == 'complete':
                    worker_id = update.get('worker_id')
                    self.mark_worker_complete(worker_id)
                    
            except queue.Empty:
                break
                
        return updates
    
    def check_worker_health(self, timeout: float = 30.0) -> Dict[int, str]:
        """Check health of all workers based on heartbeats"""
        worker_health = {}
        current_time = time.time()
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT worker_id, status, 
                               EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
                        FROM worker_status
                    """)
                    for row in cur.fetchall():
                        worker_id = row['worker_id']
                        status = row['status']
                        seconds_since = row['seconds_since_heartbeat']
                        
                        if seconds_since > timeout:
                            worker_health[worker_id] = 'dead'
                        else:
                            worker_health[worker_id] = status
        except:
            # If DB fails, use local tracking
            for worker_id, last_time in self.last_heartbeats.items():
                if current_time - last_time > timeout:
                    worker_health[worker_id] = 'dead'
                else:
                    worker_health[worker_id] = self.worker_states.get(worker_id, {}).get('status', 'unknown')
                    
        return worker_health
    
    def get_active_worker_count(self) -> int:
        """Get count of active workers"""
        health = self.check_worker_health()
        return sum(1 for status in health.values() if status in ['active', 'starting', 'idle', 'transcribing', 'downloading'])
    
    def get_completed_worker_count(self) -> int:
        """Get count of completed workers"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM worker_status 
                        WHERE status = 'completed'
                    """)
                    return cur.fetchone()[0]
        except:
            # Fallback to tracking completed workers in memory
            return len([w for w in self.worker_states.values() if w.get('status') == 'completed'])
    
    def cleanup_dead_workers(self, workers: List[mp.Process]) -> List[int]:
        """Cleanup dead workers and reassign their work"""
        dead_workers = []
        worker_health = self.check_worker_health()
        
        for i, worker in enumerate(workers):
            if not worker.is_alive() and worker_health.get(i) != 'completed':
                dead_workers.append(i)
                self._reassign_worker_urls(i)
                
        return dead_workers
    
    def detect_completion(self, workers: List[mp.Process]) -> bool:
        """Detect if all workers have completed using multiple signals"""
        # Check database for completion status
        completed_in_db = self.get_completed_worker_count()
        
        # Check process alive status
        alive_processes = sum(1 for w in workers if w.is_alive())
        
        # Check worker health
        worker_health = self.check_worker_health()
        active_workers = sum(1 for status in worker_health.values() 
                            if status in ['active', 'starting', 'idle'])
        
        # Workers are done if:
        # 1. All marked complete in database, OR
        # 2. No processes alive, OR  
        # 3. All workers idle/dead for extended period
        all_complete = completed_in_db >= self.worker_count
        all_dead = alive_processes == 0
        all_idle = active_workers == 0 and len(worker_health) > 0
        
        return all_complete or (all_dead and all_idle)
    
    def mark_worker_complete(self, worker_id: int):
        """Mark a worker as complete in the database"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE worker_status 
                        SET status = 'completed', 
                            completed_at = NOW(),
                            current_url = NULL
                        WHERE worker_id = %s
                    """, (worker_id,))
                    conn.commit()
        except Exception as e:
            print(f"Warning: Could not mark worker {worker_id} complete: {e}")
            # Track in memory as fallback
            self.worker_states[worker_id] = {'status': 'completed'}
    
    def detect_completion(self, workers: List[mp.Process]) -> bool:
        """Detect if all workers have completed using multiple signals"""
        # Check database for completion status
        completed_in_db = self.get_completed_worker_count()
        
        # Check process alive status
        alive_processes = sum(1 for w in workers if w.is_alive())
        
        # Check worker health
        worker_health = self.check_worker_health()
        active_workers = sum(1 for status in worker_health.values() 
                            if status in ['active', 'starting', 'idle'])
        
        # Workers are done if:
        # 1. All marked complete in database, OR
        # 2. No processes alive, OR  
        # 3. All workers idle/dead for extended period
        all_complete = completed_in_db >= self.worker_count
        all_dead = alive_processes == 0
        all_idle = active_workers == 0 and len(worker_health) > 0
        
        if all_complete or all_dead or all_idle:
            return True
            
        return False
    
    def cleanup_dead_workers(self, workers: List[mp.Process]) -> List[int]:
        """Identify and cleanup dead workers"""
        dead_workers = []
        worker_health = self.check_worker_health()
        
        for i, worker in enumerate(workers):
            if not worker.is_alive() or worker_health.get(i) == 'dead':
                dead_workers.append(i)
                # Reassign their URLs
                self._reassign_worker_urls(i)
                
        return dead_workers
    
    def _reassign_worker_urls(self, worker_id: int):
        """Reassign URLs from a dead worker back to pending"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get the URL the worker was processing
                cur.execute("""
                    SELECT current_url FROM worker_status 
                    WHERE worker_id = %s AND current_url IS NOT NULL
                """, (worker_id,))
                result = cur.fetchone()
                
                if result and result['current_url']:
                    # Reset the URL to pending
                    cur.execute("""
                        UPDATE queued_urls 
                        SET status = 'pending',
                            error_message = 'Worker died, reassigning'
                        WHERE url = %s AND status = 'processing'
                    """, (result['current_url'],))
                    print(f"✓ Reassigned URL from dead worker {worker_id}")
                    
                conn.commit()


def enhanced_worker_process(
    worker_id: int,
    url_queue: mp.Queue,
    result_queue: mp.Queue,
    status_queue: mp.Queue,
    display_queue: mp.Queue,
    shutdown_event: mp.Event,
    args: Any,
    download_kwargs: dict,
    ms_token: Optional[str],
    whisper_config: dict,
    total_urls: int,
    config: dict
):
    """Enhanced worker process wrapper with heartbeat and status reporting"""
    import asyncio
    
    # Create and run the async enhanced worker
    try:
        asyncio.run(async_enhanced_worker(
            worker_id, url_queue, result_queue, status_queue, display_queue,
            shutdown_event, args, download_kwargs, ms_token,
            whisper_config, total_urls, config
        ))
    except KeyboardInterrupt:
        # Let the shutdown event handle termination
        pass


async def async_enhanced_worker(
    worker_id: int,
    url_queue: mp.Queue,
    result_queue: mp.Queue,
    status_queue: mp.Queue,
    display_queue: mp.Queue,
    shutdown_event: mp.Event,
    args: Any,
    download_kwargs: dict,
    ms_token: Optional[str],
    whisper_config: dict,
    total_urls: int,
    config: dict
):
    """Async enhanced worker with heartbeat integration"""
    from utils.worker_progress import WorkerProgress
    
    # Send initial heartbeat
    status_queue.put({
        'type': 'heartbeat',
        'worker_id': worker_id,
        'status': 'starting'
    })
    
    # Create progress tracker
    progress = WorkerProgress(worker_id, display_queue, total_urls)
    
    # Heartbeat interval
    last_heartbeat = time.time()
    heartbeat_interval = 10  # Send heartbeat every 10 seconds
    
    try:
        # Import required modules - reuse from collector.py
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Import the process_tiktok_url function from collector
        from collector import process_tiktok_url
        from src.video_extractor import VideoExtractor
        from src.comment_extractor import CommentExtractor
        from src.database_manager import DatabaseOrJsonManager
        
        # Setup extractors
        video_extractor = VideoExtractor(
            output_dir=args.output,
            quality=args.quality,
            proxy=download_kwargs.get('proxy')
        )
        comment_extractor = None
        if ms_token:
            comment_extractor = CommentExtractor(ms_token=ms_token)
        
        # Setup database manager which acts as data manager
        db_manager = DatabaseOrJsonManager(config=config)
        data_manager = db_manager  # DatabaseOrJsonManager implements the DataManager interface
        
        # Track current URL for heartbeats
        current_url = None
        
        # Enhanced heartbeat sending function
        def send_heartbeat(status: str, extra_info: str = None):
            nonlocal last_heartbeat
            if time.time() - last_heartbeat > 5:
                hb_data = {
                    'type': 'heartbeat',
                    'worker_id': worker_id,
                    'status': status,
                    'current_url': current_url
                }
                if extra_info:
                    hb_data['info'] = extra_info
                status_queue.put(hb_data)
                last_heartbeat = time.time()
        
        while not shutdown_event.is_set():
            # Send periodic heartbeat
            if time.time() - last_heartbeat > heartbeat_interval:
                status_queue.put({
                    'type': 'heartbeat',
                    'worker_id': worker_id,
                    'status': 'idle'
                })
                last_heartbeat = time.time()
            
            try:
                url = url_queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            if url is None:
                break
                
            # Update current URL
            current_url = url
            
            # Mark URL as processing in database when worker claims it
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=config.get('database', {}).get('host', 'localhost'),
                    database=config.get('database', {}).get('database', 'tiktok_scraper'),
                    user=config.get('database', {}).get('user', 'root'),
                    password=config.get('database', {}).get('password', '')
                )
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE queued_urls 
                        SET status = 'processing', 
                            processed_at = NOW()
                        WHERE url = %s
                    """, (url,))
                    conn.commit()
                conn.close()
            except Exception as e:
                print(f"Worker {worker_id}: Failed to update URL status in DB: {e}")
            
            # Update status to active
            status_queue.put({
                'type': 'heartbeat',
                'worker_id': worker_id,
                'status': 'active',
                'current_url': url
            })
            last_heartbeat = time.time()
            
            # Process URL using the existing async function from collector.py
            try:
                # Add periodic heartbeat callbacks to progress
                # Save the original method only once (check if we haven't already wrapped it)
                if not hasattr(progress, '_original_send_progress'):
                    progress._original_send_progress = progress.send_progress
                    def enhanced_send_progress(stage, stage_progress=0, *args, **kwargs):
                        send_heartbeat(stage, f"{stage_progress:.0f}%")
                        return progress._original_send_progress(stage, stage_progress, *args, **kwargs)
                    progress.send_progress = enhanced_send_progress
                
                result = await process_tiktok_url(
                    url=url,
                    video_extractor=video_extractor,
                    comment_extractor=comment_extractor,
                    data_manager=data_manager,
                    progress=progress,
                    download_kwargs=download_kwargs,
                    args=args,
                    ms_token=ms_token,
                    whisper_config=whisper_config,
                    shutdown_event=shutdown_event,
                    config=config
                )
                
                # Update database based on result
                if result.get('success'):
                    # Mark as completed in database
                    try:
                        import psycopg2
                        conn = psycopg2.connect(
                            host=config.get('database', {}).get('host', 'localhost'),
                            database=config.get('database', {}).get('database', 'tiktok_scraper'),
                            user=config.get('database', {}).get('user', 'root'),
                            password=config.get('database', {}).get('password', '')
                        )
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE queued_urls 
                                SET status = 'completed'
                                WHERE url = %s
                            """, (url,))
                            conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"Worker {worker_id}: Failed to mark URL as completed in DB: {e}")
                else:
                    # Mark as failed in database
                    error_msg = result.get('error', 'Unknown error')
                    try:
                        import psycopg2
                        conn = psycopg2.connect(
                            host=config.get('database', {}).get('host', 'localhost'),
                            database=config.get('database', {}).get('database', 'tiktok_scraper'),
                            user=config.get('database', {}).get('user', 'root'),
                            password=config.get('database', {}).get('password', '')
                        )
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE queued_urls 
                                SET status = 'failed',
                                    error_message = %s
                                WHERE url = %s
                            """, (error_msg, url))
                            conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"Worker {worker_id}: Failed to mark URL as failed in DB: {e}")
                
                # Send result to main process
                result_queue.put(result)
                
            except Exception as e:
                print(f"Worker {worker_id} error processing {url}: {e}")
                import traceback
                traceback.print_exc()
                
                # Mark URL as failed in database
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host=config.get('database', {}).get('host', 'localhost'),
                        database=config.get('database', {}).get('database', 'tiktok_scraper'),
                        user=config.get('database', {}).get('user', 'root'),
                        password=config.get('database', {}).get('password', '')
                    )
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE queued_urls 
                            SET status = 'failed',
                                error_message = %s
                            WHERE url = %s
                        """, (str(e), url))
                        conn.commit()
                    conn.close()
                except:
                    pass
                
                result_queue.put({
                    'success': False,
                    'error': str(e),
                    'url': url
                })
            
    except Exception as e:
        print(f"Worker {worker_id} fatal error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Send completion status via status queue (more reliable)
        for attempt in range(5):
            try:
                status_queue.put({
                    'type': 'complete',
                    'worker_id': worker_id
                }, timeout=1.0)
                print(f"Worker {worker_id} sent completion via status queue")
                break
            except:
                if attempt == 4:
                    print(f"Worker {worker_id} failed to send completion after 5 attempts")
                time.sleep(0.2)
        
        # Still try to send None to result queue for backwards compatibility
        try:
            result_queue.put(None, timeout=0.5)
        except:
            pass