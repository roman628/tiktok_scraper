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
            user=self.db_config.get('user', 'ethan'),
            password=self.db_config.get('password', ''),
            cursor_factory=RealDictCursor
        )
    
    def init_worker_tracking_table(self):
        """Create worker tracking table if it doesn't exist"""
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
    
    def cleanup_stuck_urls(self):
        """Reset stuck 'processing' URLs to 'pending' on startup"""
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
    
    def register_worker(self, worker_id: int):
        """Register a new worker in the database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO worker_status (worker_id, status, last_heartbeat)
                    VALUES (%s, 'starting', NOW())
                    ON CONFLICT (worker_id) 
                    DO UPDATE SET status = 'starting', last_heartbeat = NOW()
                """, (worker_id,))
                conn.commit()
    
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
    
    def mark_worker_complete(self, worker_id: int):
        """Mark a worker as complete in the database"""
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
    
    def check_worker_health(self) -> Dict[int, str]:
        """Check health of all workers based on heartbeats"""
        worker_health = {}
        current_time = time.time()
        # Different timeouts for different states
        default_timeout = 30  # Normal operations
        transcription_timeout = 300  # 5 minutes for transcription
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT worker_id, status, 
                           EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat,
                           current_url
                    FROM worker_status
                    WHERE status NOT IN ('completed', 'failed')
                """)
                workers = cur.fetchall()
                
                for worker in workers:
                    worker_id = worker['worker_id']
                    seconds_since = worker['seconds_since_heartbeat']
                    status = worker['status']
                    
                    # Use longer timeout for transcription
                    timeout = transcription_timeout if status == 'transcribing' else default_timeout
                    
                    if seconds_since > timeout:
                        worker_health[worker_id] = 'dead'
                        # Mark as failed in database
                        cur.execute("""
                            UPDATE worker_status 
                            SET status = 'failed' 
                            WHERE worker_id = %s
                        """, (worker_id,))
                    elif status == 'idle' and seconds_since > 10:
                        worker_health[worker_id] = 'possibly_done'
                    else:
                        worker_health[worker_id] = status
                
                conn.commit()
        
        return worker_health
    
    def get_active_worker_count(self) -> int:
        """Get count of active workers from database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM worker_status
                    WHERE status IN ('active', 'starting', 'idle')
                    AND EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) < 30
                """)
                result = cur.fetchone()
                return result['count'] if result else 0
    
    def get_completed_worker_count(self) -> int:
        """Get count of completed workers from database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM worker_status
                    WHERE status = 'completed'
                """)
                result = cur.fetchone()
                return result['count'] if result else 0
    
    def process_status_updates(self, timeout: float = 0.1) -> List[dict]:
        """Process status updates from the status queue"""
        updates = []
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                    
                update = self.status_queue.get(timeout=min(remaining, 0.01))
                updates.append(update)
                
                # Process the update
                if update['type'] == 'heartbeat':
                    self.update_worker_heartbeat(
                        update['worker_id'], 
                        update.get('status', 'active'),
                        update.get('current_url')
                    )
                elif update['type'] == 'complete':
                    self.mark_worker_complete(update['worker_id'])
                    
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing status update: {e}")
                
        return updates
    
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
    """Enhanced worker process with heartbeat and status reporting"""
    import asyncio
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
        # Import required modules
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from src.video_extractor import VideoExtractor, load_whisper_model
        from src.comment_extractor import CommentExtractor
        from src.transcript_extractor import TranscriptExtractor
        from src.database_manager import DatabaseOrJsonManager
        
        # Setup extractors
        video_extractor = VideoExtractor()
        comment_extractor = None
        if ms_token:
            comment_extractor = CommentExtractor(ms_token=ms_token)
        
        whisper_model = None
        if whisper_config:
            whisper_model = load_whisper_model(
                model_size=whisper_config.get('model_size', 'base'),
                device=whisper_config.get('device', 'cpu'),
                compute_type=whisper_config.get('compute_type', 'int8')
            )
        
        # Setup database manager
        db_manager = DatabaseOrJsonManager(config=config)
        
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
                
            # Mark URL as processing in database when worker claims it
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=config.get('database', {}).get('host', 'localhost'),
                    database=config.get('database', {}).get('database', 'tiktok_scraper'),
                    user=config.get('database', {}).get('user', 'ethan')
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
            except:
                pass  # Continue even if DB update fails
            
            # Update status to active
            status_queue.put({
                'type': 'heartbeat',
                'worker_id': worker_id,
                'status': 'active',
                'current_url': url
            })
            last_heartbeat = time.time()
            
            # Process URL using the worker process logic from collector.py
            progress.start_url(url)
            
            try:
                # Check for duplicate
                if db_manager.is_duplicate(url):
                    progress.complete_url()
                    # Mark as completed in database
                    try:
                        import psycopg2
                        conn = psycopg2.connect(
                            host=config.get('database', {}).get('host', 'localhost'),
                            database=config.get('database', {}).get('database', 'tiktok_scraper'),
                            user=config.get('database', {}).get('user', 'ethan')
                        )
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE queued_urls 
                                SET status = 'completed'
                                WHERE url = %s
                            """, (url,))
                            conn.commit()
                        conn.close()
                    except:
                        pass
                    continue
                
                # Download video
                progress.update_stage('downloading')
                video_data = video_extractor.download_single_video(url, **download_kwargs)
                
                if video_data:
                    # Transcribe if needed with progress callbacks
                    if whisper_model:
                        progress.update_stage('transcribing')
                        
                        # Send transcription status
                        status_queue.put({
                            'type': 'heartbeat',
                            'worker_id': worker_id,
                            'status': 'transcribing',
                            'current_url': url
                        })
                        last_heartbeat = time.time()
                        
                        # Create progress callback for transcription
                        def transcription_progress(percent_complete, time_processed, total_duration):
                            nonlocal last_heartbeat
                            # Send heartbeat every 5 seconds during transcription
                            if time.time() - last_heartbeat > 5:
                                status_queue.put({
                                    'type': 'heartbeat',
                                    'worker_id': worker_id,
                                    'status': 'transcribing',
                                    'current_url': url,
                                    'progress': f"{percent_complete:.1f}% ({time_processed:.0f}s/{total_duration:.0f}s)"
                                })
                                last_heartbeat = time.time()
                                # Also update display
                                progress.send_log(f"Transcribing: {percent_complete:.1f}% ({time_processed:.0f}/{total_duration:.0f}s)")
                        
                        # Extract transcript with progress callback
                        transcriptor = TranscriptExtractor(
                            model_size=whisper_config.get('model_size', 'base'),
                            device=whisper_config.get('device', 'cpu')
                        )
                        transcript = transcriptor.extract_transcript(
                            video_data.get('requested_downloads', [{}])[0].get('filepath'),
                            progress_callback=transcription_progress
                        )
                        video_data['whisper_transcription'] = transcript
                    
                    # Extract comments if possible
                    if comment_extractor:
                        progress.update_stage('comments')
                        comments = asyncio.run(comment_extractor.extract_comments(url))
                        video_data['comments'] = comments
                    
                    # Save to database
                    progress.update_stage('saving')
                    db_manager.add_video(video_data)
                    
                    # Mark URL as completed in database
                    try:
                        import psycopg2
                        conn = psycopg2.connect(
                            host=config.get('database', {}).get('host', 'localhost'),
                            database=config.get('database', {}).get('database', 'tiktok_scraper'),
                            user=config.get('database', {}).get('user', 'ethan')
                        )
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE queued_urls 
                                SET status = 'completed'
                                WHERE url = %s
                            """, (url,))
                            conn.commit()
                        conn.close()
                    except:
                        pass
                    
                    result_queue.put({'success': True, 'data': video_data})
                else:
                    # Mark URL as failed in database
                    try:
                        import psycopg2
                        conn = psycopg2.connect(
                            host=config.get('database', {}).get('host', 'localhost'),
                            database=config.get('database', {}).get('database', 'tiktok_scraper'),
                            user=config.get('database', {}).get('user', 'ethan')
                        )
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE queued_urls 
                                SET status = 'failed',
                                    error_message = 'Failed to download video'
                                WHERE url = %s
                            """, (url,))
                            conn.commit()
                        conn.close()
                    except:
                        pass
                    
                    result_queue.put({
                        'success': False,
                        'error': 'Failed to download video',
                        'url': url
                    })
                    
            except Exception as e:
                # Mark URL as failed in database
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host=config.get('database', {}).get('host', 'localhost'),
                        database=config.get('database', {}).get('database', 'tiktok_scraper'),
                        user=config.get('database', {}).get('user', 'ethan')
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
            
            progress.complete_url()
            
    except Exception as e:
        print(f"Worker {worker_id} error: {e}")
        
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