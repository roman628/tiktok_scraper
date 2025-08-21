"""
Database Manager for TikTok Scraper
Handles all PostgreSQL operations with connection pooling, retry logic, and caching
"""

import os
import json
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, extras, sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import time
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_connection_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry database operations on connection errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(f"Database connection failed after {max_retries} attempts")
                        raise
            raise last_exception
        return wrapper
    return decorator


class DatabaseManager:
    """Manages PostgreSQL database operations for TikTok scraper"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "tiktok_scraper",
                 user: str = "postgres",
                 password: str = "",
                 min_connections: int = 2,
                 max_connections: int = 10):
        """
        Initialize database manager with connection pooling
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
        """
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password or os.environ.get('DB_PASSWORD', '')
        }
        
        # Initialize connection pool
        self.pool = None
        self._initialize_pool(min_connections, max_connections)
        
        # Cache for duplicate detection
        self.url_cache: Set[str] = set()
        self.cache_size_limit = 100000  # Limit cache size to avoid memory issues
        self.cache_initialized = False
        
    def _initialize_pool(self, min_conn: int, max_conn: int):
        """Initialize the connection pool"""
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                min_conn,
                max_conn,
                **self.connection_params
            )
            logger.info(f"Database connection pool initialized ({min_conn}-{max_conn} connections)")
        except psycopg2.Error as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """Context manager for database cursors"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    @retry_on_connection_error()
    def initialize_cache(self):
        """Load existing URLs into cache for fast duplicate detection"""
        if self.cache_initialized:
            return
        
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT url FROM videos")
                urls = cursor.fetchall()
                self.url_cache = {url[0] for url in urls}
                self.cache_initialized = True
                logger.info(f"Loaded {len(self.url_cache)} URLs into cache")
        except psycopg2.Error as e:
            logger.error(f"Failed to initialize URL cache: {e}")
            raise
    
    @retry_on_connection_error()
    def insert_video(self, video_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a single video record
        
        Args:
            video_data: Dictionary containing video metadata
            
        Returns:
            Video ID if successful, None otherwise
        """
        # Check for duplicate
        if self.is_duplicate(video_data.get('url')):
            logger.debug(f"Skipping duplicate URL: {video_data.get('url')}")
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Insert main video record
                    video_id = self._insert_video_record(cursor, video_data)
                    
                    # Insert hashtags
                    if video_data.get('hashtags'):
                        self._insert_hashtags(cursor, video_id, video_data['hashtags'])
                    
                    # Insert transcription
                    if video_data.get('whisper_transcription'):
                        self._insert_transcription(cursor, video_id, video_data)
                    
                    # Insert comments
                    if video_data.get('top_comments'):
                        self._insert_comments(cursor, video_id, video_data['top_comments'], 
                                            video_data.get('comments_extracted_at'))
                    
                    # Update processing status
                    self._update_processing_status(cursor, video_id, video_data)
                    
                    # Add to cache
                    self.url_cache.add(video_data['url'])
                    
                    conn.commit()
                    logger.debug(f"Successfully inserted video: {video_data.get('video_id')}")
                    return video_id
                    
        except psycopg2.IntegrityError as e:
            logger.warning(f"Integrity error (likely duplicate): {e}")
            return None
        except psycopg2.Error as e:
            logger.error(f"Failed to insert video: {e}")
            raise
    
    def _insert_video_record(self, cursor, video_data: Dict) -> int:
        """Insert the main video record"""
        insert_query = """
            INSERT INTO videos (
                video_id, url, title, description, duration,
                uploader, uploader_id, uploader_url,
                view_count, like_count, comment_count,
                repost_count, save_count, share_count,
                upload_date, timestamp, width, height, fps,
                filesize, format, downloaded_at, downloaded_with, platform
            ) VALUES (
                %(video_id)s, %(url)s, %(title)s, %(description)s, %(duration)s,
                %(uploader)s, %(uploader_id)s, %(uploader_url)s,
                %(view_count)s, %(like_count)s, %(comment_count)s,
                %(repost_count)s, %(save_count)s, %(share_count)s,
                %(upload_date)s, %(timestamp)s, %(width)s, %(height)s, %(fps)s,
                %(filesize)s, %(format)s, %(downloaded_at)s, %(downloaded_with)s, %(platform)s
            ) RETURNING id
        """
        
        # Prepare data with proper date formatting
        insert_data = video_data.copy()
        if 'upload_date' in insert_data and insert_data['upload_date']:
            # Convert YYYYMMDD string to date
            date_str = str(insert_data['upload_date'])
            insert_data['upload_date'] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        cursor.execute(insert_query, insert_data)
        return cursor.fetchone()[0]
    
    def _insert_hashtags(self, cursor, video_id: int, hashtags: List[str]):
        """Insert hashtags and link them to video"""
        for tag in hashtags:
            # Insert hashtag if not exists
            cursor.execute(
                "INSERT INTO hashtags (tag) VALUES (%s) ON CONFLICT (tag) DO UPDATE SET tag = EXCLUDED.tag RETURNING id",
                (tag,)
            )
            hashtag_id = cursor.fetchone()[0]
            
            # Link to video
            cursor.execute(
                "INSERT INTO video_hashtags (video_id, hashtag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (video_id, hashtag_id)
            )
    
    def _insert_transcription(self, cursor, video_id: int, video_data: Dict):
        """Insert transcription data"""
        cursor.execute("""
            INSERT INTO transcriptions (video_id, whisper_transcription, transcription_timestamp)
            VALUES (%s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE 
            SET whisper_transcription = EXCLUDED.whisper_transcription,
                transcription_timestamp = EXCLUDED.transcription_timestamp
        """, (video_id, video_data.get('whisper_transcription'), 
              video_data.get('transcription_timestamp')))
    
    def _insert_comments(self, cursor, video_id: int, comments: List[Dict], extracted_at: str):
        """Insert comments for a video"""
        for i, comment in enumerate(comments):
            cursor.execute("""
                INSERT INTO comments (
                    video_id, comment_id, username, display_name,
                    comment_text, like_count, timestamp, is_top_comment, extracted_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (comment_id) DO UPDATE
                SET like_count = EXCLUDED.like_count
            """, (
                video_id,
                comment.get('comment_id'),
                comment.get('username'),
                comment.get('display_name'),
                comment.get('comment_text'),
                comment.get('like_count', 0),
                comment.get('timestamp'),
                i < 10,  # Mark top 10 as top comments
                extracted_at
            ))
    
    def _update_processing_status(self, cursor, video_id: int, video_data: Dict):
        """Update processing status for a video"""
        cursor.execute("""
            INSERT INTO processing_status (
                video_id, comments_extracted, comments_extracted_at,
                transcription_completed, transcription_completed_at
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE
            SET comments_extracted = EXCLUDED.comments_extracted,
                comments_extracted_at = EXCLUDED.comments_extracted_at,
                transcription_completed = EXCLUDED.transcription_completed,
                transcription_completed_at = EXCLUDED.transcription_completed_at,
                updated_at = NOW()
        """, (
            video_id,
            video_data.get('comments_extracted', False),
            video_data.get('comments_extracted_at'),
            bool(video_data.get('whisper_transcription')),
            video_data.get('transcription_timestamp')
        ))
    
    @retry_on_connection_error()
    def batch_insert_videos(self, videos: List[Dict[str, Any]]) -> int:
        """
        Batch insert multiple videos using COPY for performance
        
        Args:
            videos: List of video dictionaries
            
        Returns:
            Number of videos inserted
        """
        if not videos:
            return 0
        
        inserted_count = 0
        
        try:
            with self.get_connection() as conn:
                for video_data in videos:
                    if not self.is_duplicate(video_data.get('url')):
                        with conn.cursor() as cursor:
                            video_id = self._insert_video_record(cursor, video_data)
                            if video_id:
                                # Insert related data
                                if video_data.get('hashtags'):
                                    self._insert_hashtags(cursor, video_id, video_data['hashtags'])
                                if video_data.get('whisper_transcription'):
                                    self._insert_transcription(cursor, video_id, video_data)
                                if video_data.get('top_comments'):
                                    self._insert_comments(cursor, video_id, video_data['top_comments'],
                                                        video_data.get('comments_extracted_at'))
                                self._update_processing_status(cursor, video_id, video_data)
                                
                                self.url_cache.add(video_data['url'])
                                inserted_count += 1
                
                conn.commit()
                logger.info(f"Batch inserted {inserted_count} videos")
                return inserted_count
                
        except psycopg2.Error as e:
            logger.error(f"Batch insert failed: {e}")
            raise
    
    def is_duplicate(self, url: str) -> bool:
        """
        Check if URL already exists in database
        
        Args:
            url: Video URL to check
            
        Returns:
            True if duplicate, False otherwise
        """
        if not url:
            return False
        
        # Initialize cache if needed
        if not self.cache_initialized:
            self.initialize_cache()
        
        # Check cache first
        if url in self.url_cache:
            return True
        
        # Double-check database if not in cache
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1 FROM videos WHERE url = %s LIMIT 1", (url,))
                exists = cursor.fetchone() is not None
                
                if exists and len(self.url_cache) < self.cache_size_limit:
                    self.url_cache.add(url)
                
                return exists
        except psycopg2.Error as e:
            logger.error(f"Failed to check duplicate: {e}")
            return False
    
    @retry_on_connection_error()
    def get_existing_urls(self) -> Set[str]:
        """
        Get all existing URLs from database
        
        Returns:
            Set of URLs
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT url FROM videos")
                return {row[0] for row in cursor.fetchall()}
        except psycopg2.Error as e:
            logger.error(f"Failed to get existing URLs: {e}")
            return set()
    
    @retry_on_connection_error()
    def get_videos_for_ml(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get videos for ML training
        
        Args:
            limit: Maximum number of videos to return
            
        Returns:
            List of video dictionaries
        """
        try:
            with self.get_cursor(cursor_factory=extras.RealDictCursor) as cursor:
                query = "SELECT * FROM ml_training_data"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                videos = cursor.fetchall()
                
                # Convert to regular dicts and handle JSON fields
                result = []
                for video in videos:
                    video_dict = dict(video)
                    # Parse JSON fields
                    if video_dict.get('top_comments') and isinstance(video_dict['top_comments'], str):
                        video_dict['top_comments'] = json.loads(video_dict['top_comments'])
                    result.append(video_dict)
                
                return result
                
        except psycopg2.Error as e:
            logger.error(f"Failed to get ML training data: {e}")
            return []
    
    @retry_on_connection_error()
    def update_transcription(self, video_id: int, transcription: str, model_used: str = "whisper"):
        """Update or insert transcription for a video"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO transcriptions (video_id, whisper_transcription, transcription_timestamp, model_used)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (video_id) DO UPDATE
                    SET whisper_transcription = EXCLUDED.whisper_transcription,
                        transcription_timestamp = EXCLUDED.transcription_timestamp,
                        model_used = EXCLUDED.model_used
                """, (video_id, transcription, datetime.now(), model_used))
                
                cursor.execute("""
                    UPDATE processing_status 
                    SET transcription_completed = true, 
                        transcription_completed_at = %s
                    WHERE video_id = %s
                """, (datetime.now(), video_id))
                
        except psycopg2.Error as e:
            logger.error(f"Failed to update transcription: {e}")
            raise
    
    @retry_on_connection_error()
    def add_comments(self, video_id: int, comments: List[Dict]):
        """Add comments to a video"""
        if not comments:
            return
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    self._insert_comments(cursor, video_id, comments, datetime.now())
                    
                    cursor.execute("""
                        UPDATE processing_status 
                        SET comments_extracted = true, 
                            comments_extracted_at = %s
                        WHERE video_id = %s
                    """, (datetime.now(), video_id))
                    
                conn.commit()
                
        except psycopg2.Error as e:
            logger.error(f"Failed to add comments: {e}")
            raise
    
    @retry_on_connection_error()
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_cursor(cursor_factory=extras.RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM database_statistics")
                return dict(cursor.fetchone())
        except psycopg2.Error as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    @retry_on_connection_error()
    def export_to_json(self, output_file: str, limit: Optional[int] = None):
        """
        Export database to JSON format (compatible with master2.json)
        
        Args:
            output_file: Path to output JSON file
            limit: Maximum number of records to export
        """
        videos = self.get_videos_for_ml(limit)
        
        # Convert to master2.json format
        export_data = []
        for video in videos:
            # Flatten the data structure
            video_flat = {
                'video_id': video['video_id'],
                'url': video['url'],
                'title': video['title'],
                'description': video['description'],
                'duration': video['duration'],
                'uploader': video['uploader'],
                'uploader_id': video['uploader_id'],
                'uploader_url': video['uploader_url'],
                'view_count': video['view_count'],
                'like_count': video['like_count'],
                'comment_count': video['comment_count'],
                'repost_count': video['repost_count'],
                'save_count': video['save_count'],
                'share_count': video['share_count'],
                'hashtags': video.get('hashtags', []),
                'upload_date': video['upload_date'].strftime('%Y%m%d') if video['upload_date'] else None,
                'timestamp': video['timestamp'],
                'width': video['width'],
                'height': video['height'],
                'fps': video['fps'],
                'filesize': video['filesize'],
                'format': video['format'],
                'downloaded_at': video['downloaded_at'].isoformat() if video['downloaded_at'] else None,
                'downloaded_with': video['downloaded_with'],
                'platform': video['platform'],
                'whisper_transcription': video.get('whisper_transcription'),
                'transcription_timestamp': video.get('transcription_timestamp').isoformat() if video.get('transcription_timestamp') else None,
                'top_comments': video.get('top_comments', []),
                'comments_extracted': video.get('comments_extracted', False),
                'comments_extracted_at': video.get('comments_extracted_at').isoformat() if video.get('comments_extracted_at') else None
            }
            export_data.append(video_flat)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(export_data)} videos to {output_file}")
    
    def close(self):
        """Close all database connections"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")


class DatabaseOrJsonManager:
    """
    Database manager wrapper - always uses PostgreSQL
    Legacy JSON support removed
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize database manager
        
        Args:
            config: Configuration dictionary
        """
        # Always use database - no longer checking 'enabled' flag
        db_config = config.get('database', {})
        self.manager = DatabaseManager(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            database=db_config.get('database', 'tiktok_scraper'),
            user=db_config.get('user'),  # Use config value, no default
            password=db_config.get('password', ''),
            min_connections=db_config.get('min_connections', 2),
            max_connections=db_config.get('max_connections', 10)
        )
        self.use_database = True  # Always true now
        logger.info("Using PostgreSQL database for storage")
    
    def append_to_master(self, video_data: Dict[str, Any]) -> bool:
        """Append video data to storage"""
        if self.use_database:
            return self.manager.insert_video(video_data) is not None
        else:
            return self.manager.append_to_master(video_data)
    
    def is_duplicate(self, url: str) -> bool:
        """Check if URL is duplicate"""
        return self.manager.is_duplicate(url)
    
    def get_existing_urls(self) -> Set[str]:
        """Get all existing URLs"""
        if self.use_database:
            return self.manager.get_existing_urls()
        else:
            return self.manager.existing_urls
    
    def close(self):
        """Clean up resources"""
        if self.use_database:
            self.manager.close()