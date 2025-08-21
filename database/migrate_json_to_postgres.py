#!/usr/bin/env python3
"""
Migration script to import existing master2.json data into PostgreSQL database
Handles large JSON files efficiently with streaming and batch processing
"""

import json
import sys
import os
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2 import pool
from tqdm import tqdm
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JsonToPostgresMigrator:
    """Migrates TikTok data from JSON to PostgreSQL"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize migrator
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
        self.stats = {
            'total_records': 0,
            'successful_imports': 0,
            'duplicates_skipped': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def load_json_data(self, json_file: str) -> List[Dict]:
        """
        Load JSON data from file
        
        Args:
            json_file: Path to JSON file
            
        Returns:
            List of video dictionaries
        """
        logger.info(f"Loading data from {json_file}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                logger.error("JSON file does not contain a list")
                return []
            
            logger.info(f"Loaded {len(data)} records from JSON")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return []
        except FileNotFoundError:
            logger.error(f"File not found: {json_file}")
            return []
        except Exception as e:
            logger.error(f"Error loading JSON: {e}")
            return []
    
    def validate_and_clean_record(self, record: Dict) -> Dict:
        """
        Validate and clean a single record for database insertion
        
        Args:
            record: Raw video record from JSON
            
        Returns:
            Cleaned record ready for database
        """
        cleaned = {}
        
        # Required fields
        required_fields = ['video_id', 'url']
        for field in required_fields:
            if field not in record or not record[field]:
                raise ValueError(f"Missing required field: {field}")
            cleaned[field] = record[field]
        
        # Text fields (handle None and convert to string)
        text_fields = ['title', 'description', 'uploader', 'uploader_id', 
                      'uploader_url', 'format', 'downloaded_with', 'platform',
                      'whisper_transcription']
        for field in text_fields:
            value = record.get(field)
            if value is not None:
                cleaned[field] = str(value)
            else:
                cleaned[field] = None
        
        # Integer fields
        int_fields = ['duration', 'view_count', 'like_count', 'comment_count',
                     'repost_count', 'save_count', 'share_count', 'timestamp',
                     'width', 'height', 'fps', 'filesize']
        for field in int_fields:
            value = record.get(field)
            if value is not None:
                try:
                    cleaned[field] = int(value)
                except (ValueError, TypeError):
                    cleaned[field] = None
            else:
                cleaned[field] = None
        
        # Date fields
        upload_date = record.get('upload_date')
        if upload_date:
            # Already in YYYYMMDD format
            cleaned['upload_date'] = str(upload_date)
        else:
            cleaned['upload_date'] = None
        
        # Timestamp fields
        timestamp_fields = ['downloaded_at', 'transcription_timestamp', 'comments_extracted_at']
        for field in timestamp_fields:
            value = record.get(field)
            if value:
                cleaned[field] = value
            else:
                cleaned[field] = None
        
        # Array fields
        cleaned['hashtags'] = record.get('hashtags', [])
        cleaned['top_comments'] = record.get('top_comments', [])
        
        # Boolean fields
        cleaned['comments_extracted'] = record.get('comments_extracted', False)
        
        return cleaned
    
    def migrate_batch(self, records: List[Dict], batch_size: int = 100) -> Dict[str, int]:
        """
        Migrate a batch of records
        
        Args:
            records: List of video records
            batch_size: Number of records to process at once
            
        Returns:
            Statistics dictionary
        """
        batch_stats = {
            'processed': 0,
            'successful': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        for record in records:
            try:
                # Clean and validate record
                cleaned_record = self.validate_and_clean_record(record)
                
                # Insert into database
                video_id = self.db_manager.insert_video(cleaned_record)
                
                if video_id:
                    batch_stats['successful'] += 1
                else:
                    batch_stats['duplicates'] += 1
                
                batch_stats['processed'] += 1
                
            except Exception as e:
                logger.debug(f"Error processing record {record.get('video_id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
                batch_stats['processed'] += 1
        
        return batch_stats
    
    def migrate(self, json_file: str, batch_size: int = 100, 
                skip_duplicates: bool = True, dry_run: bool = False):
        """
        Main migration method
        
        Args:
            json_file: Path to JSON file
            batch_size: Number of records to process at once
            skip_duplicates: Whether to skip duplicate URLs
            dry_run: If True, only validate without inserting
        """
        self.stats['start_time'] = datetime.now()
        
        # Load JSON data
        records = self.load_json_data(json_file)
        if not records:
            logger.error("No records to migrate")
            return
        
        self.stats['total_records'] = len(records)
        
        if dry_run:
            logger.info("DRY RUN MODE - No data will be inserted")
            # Just validate all records
            valid_count = 0
            invalid_count = 0
            for record in tqdm(records, desc="Validating"):
                try:
                    self.validate_and_clean_record(record)
                    valid_count += 1
                except Exception as e:
                    invalid_count += 1
                    logger.debug(f"Invalid record: {e}")
            
            logger.info(f"Validation complete: {valid_count} valid, {invalid_count} invalid")
            return
        
        # Initialize database cache for duplicate detection
        if skip_duplicates:
            logger.info("Initializing duplicate detection cache...")
            self.db_manager.initialize_cache()
        
        # Process records in batches
        logger.info(f"Starting migration of {len(records)} records...")
        
        with tqdm(total=len(records), desc="Migrating") as pbar:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                batch_stats = self.migrate_batch(batch, batch_size)
                
                self.stats['successful_imports'] += batch_stats['successful']
                self.stats['duplicates_skipped'] += batch_stats['duplicates']
                self.stats['errors'] += batch_stats['errors']
                
                pbar.update(len(batch))
                
                # Log progress periodically
                if (i + batch_size) % 1000 == 0:
                    logger.info(f"Progress: {i + batch_size}/{len(records)} records processed")
        
        self.stats['end_time'] = datetime.now()
        self.print_summary()
    
    def print_summary(self):
        """Print migration summary"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print("\n" + "="*50)
        print("MIGRATION SUMMARY")
        print("="*50)
        print(f"Total records:       {self.stats['total_records']:,}")
        print(f"Successfully imported: {self.stats['successful_imports']:,}")
        print(f"Duplicates skipped:  {self.stats['duplicates_skipped']:,}")
        print(f"Errors:              {self.stats['errors']:,}")
        print(f"Duration:            {duration:.2f} seconds")
        
        if duration > 0:
            rate = self.stats['total_records'] / duration
            print(f"Processing rate:     {rate:.2f} records/second")
        
        print("="*50)
        
        # Get database statistics
        db_stats = self.db_manager.get_statistics()
        if db_stats:
            print("\nDATABASE STATISTICS:")
            print(f"Total videos:        {db_stats.get('total_videos', 0):,}")
            print(f"Total comments:      {db_stats.get('total_comments', 0):,}")
            print(f"Total transcriptions: {db_stats.get('total_transcriptions', 0):,}")
            print(f"Unique hashtags:     {db_stats.get('unique_hashtags', 0):,}")
            print(f"Database size:       {db_stats.get('database_size', 'Unknown')}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate TikTok data from JSON to PostgreSQL"
    )
    parser.add_argument(
        'json_file',
        help='Path to master2.json file'
    )
    parser.add_argument(
        '--host',
        default='localhost',
        help='Database host (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5432,
        help='Database port (default: 5432)'
    )
    parser.add_argument(
        '--database',
        default='tiktok_scraper',
        help='Database name (default: tiktok_scraper)'
    )
    parser.add_argument(
        '--user',
        default='postgres',
        help='Database user (default: postgres)'
    )
    parser.add_argument(
        '--password',
        default='',
        help='Database password (or set DB_PASSWORD env var)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of records to process at once (default: 100)'
    )
    parser.add_argument(
        '--no-skip-duplicates',
        action='store_true',
        help='Do not skip duplicate URLs'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate data without inserting into database'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if JSON file exists
    if not os.path.exists(args.json_file):
        logger.error(f"File not found: {args.json_file}")
        sys.exit(1)
    
    # Initialize database manager
    try:
        db_manager = DatabaseManager(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password or os.environ.get('DB_PASSWORD', '')
        )
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    # Create migrator and run migration
    migrator = JsonToPostgresMigrator(db_manager)
    
    try:
        migrator.migrate(
            args.json_file,
            batch_size=args.batch_size,
            skip_duplicates=not args.no_skip_duplicates,
            dry_run=args.dry_run
        )
    except KeyboardInterrupt:
        logger.info("\nMigration interrupted by user")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        db_manager.close()


if __name__ == "__main__":
    main()