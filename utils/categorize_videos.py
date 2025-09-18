#!/usr/bin/env python3
"""
Category Discovery Tool
Uses Gemini API to discover categories from large batches of TikTok videos
"""

import argparse
import logging
import os
import sys
import time
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import google.generativeai as genai
except ImportError:
    print("Error: google-generativeai not installed")
    print("Install with: pip install google-generativeai")
    sys.exit(1)

try:
    import tiktoken
except ImportError:
    print("Error: tiktoken not installed")
    print("Install with: pip install tiktoken")
    sys.exit(1)


@dataclass
class Config:
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tiktok_scraper"
    db_user: str = os.environ.get('USER', 'postgres')
    db_password: str = ""
    
    # API settings
    api_key: str = ""
    model_name: str = "gemini-1.5-flash"
    
    # Token management
    max_input_tokens: int = 1000000  # Paid tier limit for 1.5 Flash
    
    # Batch settings
    title_max_chars: int = 500
    transcript_max_words: int = 500
    min_categories: int = 200
    max_categories: int = 500


class TokenCalculator:
    """Accurate token counting using tiktoken"""
    
    def __init__(self):
        self.encoder = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))


class DatabaseManager:
    """Handles database operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.pool = SimpleConnectionPool(
            1, 5,
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password or None
        )
    
    def get_all_videos_with_content(self) -> List[Dict]:
        """Get all videos that have either title or transcript"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                SELECT 
                    v.id,
                    v.video_id,
                    v.title,
                    t.whisper_transcription,
                    ARRAY_AGG(DISTINCT h.tag) FILTER (WHERE h.tag IS NOT NULL) as hashtags
                FROM videos v
                LEFT JOIN transcriptions t ON t.video_id = v.id
                LEFT JOIN video_hashtags vh ON vh.video_id = v.id
                LEFT JOIN hashtags h ON h.id = vh.hashtag_id
                WHERE v.title IS NOT NULL OR t.whisper_transcription IS NOT NULL
                GROUP BY v.id, v.video_id, v.title, t.whisper_transcription
                ORDER BY v.id
                """
                cur.execute(query)
                return cur.fetchall()
        finally:
            self.pool.putconn(conn)
    
    def save_categories(self, categories: List[str]) -> int:
        """Save categories to database and return count saved"""
        conn = self.pool.getconn()
        saved_count = 0
        
        try:
            with conn.cursor() as cur:
                for category in categories:
                    category = category.strip().lower()
                    if not category or len(category.split()) > 3:
                        continue
                    
                    cur.execute("""
                        INSERT INTO categories (name)
                        VALUES (%s)
                        ON CONFLICT (name) DO NOTHING
                        RETURNING id
                    """, (category,))
                    
                    if cur.fetchone():
                        saved_count += 1
                
                conn.commit()
                if saved_count > 0:
                    print(f"  ✓ Saved {saved_count} new categories to database")
        except Exception as e:
            conn.rollback()
            logging.error(f"Error saving categories: {e}")
        finally:
            self.pool.putconn(conn)
        
        return saved_count
    
    def save_batch_info(self, batch_number: int, video_count: int, 
                       token_count: int, categories_generated: int):
        """Save batch processing information"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS categorization_batches (
                        id SERIAL PRIMARY KEY,
                        batch_number INTEGER,
                        video_count INTEGER,
                        token_count INTEGER,
                        categories_generated INTEGER,
                        processed_at TIMESTAMP DEFAULT NOW(),
                        phase VARCHAR(20),
                        status VARCHAR(20)
                    )
                """)
                
                cur.execute("""
                    INSERT INTO categorization_batches 
                    (batch_number, video_count, token_count, categories_generated, phase, status)
                    VALUES (%s, %s, %s, %s, 'discovery', 'success')
                """, (batch_number, video_count, token_count, categories_generated))
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Error saving batch info: {e}")
        finally:
            self.pool.putconn(conn)


class CategoryDiscovery:
    """Discover categories from batches of videos"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db = DatabaseManager(config)
        self.token_calc = TokenCalculator()
        
        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(config.model_name)
    
    def prepare_video_text(self, video: Dict) -> Tuple[str, int]:
        """Prepare video text and calculate tokens"""
        title = (video.get('title') or '')[:self.config.title_max_chars]
        transcript = video.get('whisper_transcription') or ''
        
        if transcript:
            words = transcript.split()[:self.config.transcript_max_words]
            transcript = ' '.join(words)
        
        hashtags = ', '.join(video.get('hashtags', [])) if video.get('hashtags') else ''
        
        video_text = f"""Video #{video['id']} [{video['video_id']}]:
Title: {title}
Hashtags: {hashtags}
Transcript: {transcript}
---"""
        
        tokens = self.token_calc.count_tokens(video_text)
        return video_text, tokens
    
    def create_batches(self, videos: List[Dict]) -> List[List[Dict]]:
        """Create batches that fit within token limit"""
        batches = []
        current_batch = []
        current_tokens = 0
        
        # Reserve tokens for prompt overhead
        prompt_overhead = 5000
        usable_tokens = self.config.max_input_tokens - prompt_overhead
        
        for video in videos:
            video_text, tokens = self.prepare_video_text(video)
            video['formatted_text'] = video_text
            video['token_count'] = tokens
            
            if current_tokens + tokens > usable_tokens:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [video]
                current_tokens = tokens
            else:
                current_batch.append(video)
                current_tokens += tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def build_prompt(self, batch: List[Dict]) -> str:
        """Build prompt for category discovery"""
        video_texts = '\n'.join([v['formatted_text'] for v in batch])
        
        return f"""Analyze these {len(batch)} TikTok videos and generate comprehensive content categories.

VIDEO DATA:
{video_texts}

INSTRUCTIONS:
1. Generate between {self.config.min_categories} and {self.config.max_categories} distinct categories
2. Categories must be 1-3 words maximum
3. Categories should be specific enough to be meaningful but general enough to apply to multiple videos
4. Cover all major themes, trends, content types, and topics you observe
5. Include categories for different content styles and formats
6. Make categories lowercase
7. Output ONLY a comma-separated list, nothing else

OUTPUT FORMAT:
category1, category2, category3, category4, category5"""
    
    def parse_response(self, response: str) -> List[str]:
        """Parse categories from LLM response"""
        # Remove markdown formatting
        response = re.sub(r'```[a-z]*\n?', '', response)
        response = re.sub(r'\n```', '', response)
        
        categories = []
        seen = set()
        
        for cat in response.split(','):
            cat = cat.strip().lower()
            
            # Validate category
            if not cat or len(cat) < 2 or len(cat) > 50:
                continue
            if len(cat.split()) > 4:  # Allow up to 4 words
                continue
            # Filter out junk characters and code fragments
            if any(char in cat for char in ['#', '@', '/', '\\', '"', "'", '[', ']', '{', '}', '(', ')', '+', '=', ':', ';', '<', '>', '|', '`']):
                continue
            # Must contain at least one letter
            if not any(c.isalpha() for c in cat):
                continue
            # No pure numbers or codes
            if cat.replace(' ', '').replace('-', '').replace('_', '').isdigit():
                continue
            
            if cat not in seen:
                seen.add(cat)
                categories.append(cat)
        
        return categories
    
    def discover_from_batch(self, batch: List[Dict], retry_on_token_error: bool = True) -> List[str]:
        """Discover categories from a single batch"""
        prompt = self.build_prompt(batch)
        prompt_tokens = self.token_calc.count_tokens(prompt)
        print(f"  Prompt tokens: {prompt_tokens:,}")
        
        try:
            response = self.model.generate_content(prompt)
            categories = self.parse_response(response.text)
            print(f"  Discovered {len(categories)} categories")
            
            # Show sample categories
            sample = categories[:15]
            print(f"  Sample: {', '.join(sample)}{'...' if len(categories) > 15 else ''}")
            
            return categories
        except Exception as e:
            error_str = str(e)
            if "token count" in error_str.lower() and "exceeds" in error_str.lower() and retry_on_token_error:
                # Token limit exceeded, split batch and retry
                print(f"  Token limit exceeded, splitting batch in half...")
                half = len(batch) // 2
                if half > 0:
                    categories = []
                    # Process first half
                    print(f"  Processing first half ({half} videos)...")
                    categories.extend(self.discover_from_batch(batch[:half], retry_on_token_error=True))
                    # Process second half
                    print(f"  Processing second half ({len(batch) - half} videos)...")
                    categories.extend(self.discover_from_batch(batch[half:], retry_on_token_error=True))
                    return categories
            print(f"  Error: {e}")
            return []
    
    def run(self):
        """Run the discovery process"""
        print("\n" + "="*60)
        print("CATEGORY DISCOVERY")
        print("="*60)
        
        # Get videos
        print("Loading videos from database...")
        videos = self.db.get_all_videos_with_content()
        print(f"Found {len(videos)} videos with content")
        
        # Create batches
        print("\nCreating batches...")
        batches = self.create_batches(videos)
        print(f"Created {len(batches)} batches")
        
        total_tokens = sum(sum(v['token_count'] for v in batch) for batch in batches)
        print(f"Total tokens: {total_tokens:,}")
        
        # Process batches
        all_categories = set()
        
        for i, batch in enumerate(batches, 1):
            print(f"\n--- Batch {i}/{len(batches)} ---")
            print(f"  Videos: {len(batch)}")
            batch_tokens = sum(v['token_count'] for v in batch)
            print(f"  Batch tokens: {batch_tokens:,}")
            
            # Discover categories
            categories = self.discover_from_batch(batch)
            
            if categories:
                # Track new categories
                new_cats = set(categories) - all_categories
                all_categories.update(categories)
                
                # Save to database
                saved = self.db.save_categories(categories)
                
                # Save batch info
                self.db.save_batch_info(i, len(batch), batch_tokens, len(new_cats))
                
                print(f"  New unique categories: {len(new_cats)}")
                print(f"  Total categories so far: {len(all_categories)}")
            
            # Rate limiting - reduced for paid tier
            if i < len(batches):
                print(f"\n⏳ Waiting 2 seconds between requests...")
                time.sleep(2)  # Minimal delay for paid tier
        
        print("\n" + "="*60)
        print(f"COMPLETE: Discovered {len(all_categories)} total categories")
        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Discover categories from TikTok videos using Gemini API"
    )
    parser.add_argument('--api-key', help='Gemini API key (defaults to GEMINI_API_KEY env var)')
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key or os.getenv('GEMINI_API_KEY')
    if not api_key:
        parser.error('API key required. Provide --api-key or set GEMINI_API_KEY environment variable')
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler('category_discovery.log')]
    )
    
    # Create config
    config = Config(api_key=api_key)
    
    # Run discovery
    try:
        discovery = CategoryDiscovery(config)
        discovery.run()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()