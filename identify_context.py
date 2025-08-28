#!/usr/bin/env python3
"""
Context Identification for TikTok Videos
Uses lightweight sentence transformers to match videos to existing categories
Processes full transcripts efficiently on GPU/CPU
"""

import argparse
import os
import sys
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import time

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    print("Error: Required packages not installed")
    print("Install with: pip install sentence-transformers scikit-learn")
    sys.exit(1)

try:
    import torch
    DEVICE = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    print(f"Using device: {DEVICE}")
except ImportError:
    print("Warning: PyTorch not found, using CPU")
    DEVICE = 'cpu'


@dataclass
class Config:
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tiktok_scraper"
    db_user: str = os.environ.get('USER', 'postgres')
    db_password: str = ""
    
    # Model settings
    model_name: str = "all-MiniLM-L6-v2"  # Fast and efficient
    batch_size: int = 32
    max_categories_per_video: int = 5
    confidence_threshold: float = 0.3
    
    # Processing
    process_uncategorized_only: bool = True
    limit: Optional[int] = None


class DatabaseManager:
    """Handles database operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.pool = SimpleConnectionPool(
            1, 10,
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password or None
        )
    
    def get_categories(self) -> List[Dict]:
        """Get all categories from database"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name 
                    FROM categories 
                    ORDER BY name
                """)
                return cur.fetchall()
        finally:
            self.pool.putconn(conn)
    
    def get_videos_to_process(self, uncategorized_only: bool = True, 
                            limit: Optional[int] = None) -> List[Dict]:
        """Get videos that need categorization"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if uncategorized_only:
                    query = """
                    SELECT 
                        v.id,
                        v.video_id,
                        v.title,
                        t.whisper_transcription
                    FROM videos v
                    INNER JOIN transcriptions t ON t.video_id = v.id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM video_categories vc WHERE vc.video_id = v.id
                    )
                    AND t.whisper_transcription IS NOT NULL
                    AND LENGTH(t.whisper_transcription) > 10
                    ORDER BY v.id
                    """
                else:
                    query = """
                    SELECT 
                        v.id,
                        v.video_id,
                        v.title,
                        t.whisper_transcription
                    FROM videos v
                    INNER JOIN transcriptions t ON t.video_id = v.id
                    WHERE t.whisper_transcription IS NOT NULL
                    AND LENGTH(t.whisper_transcription) > 10
                    ORDER BY v.id
                    """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cur.execute(query)
                return cur.fetchall()
        finally:
            self.pool.putconn(conn)
    
    def save_video_categories(self, video_id: int, category_ids: List[int], 
                            confidences: List[float]):
        """Save video-category associations"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Clear existing categories
                cur.execute("DELETE FROM video_categories WHERE video_id = %s", (video_id,))
                
                # Insert new categories
                for cat_id, confidence in zip(category_ids, confidences):
                    cur.execute("""
                        INSERT INTO video_categories 
                        (video_id, category_id, confidence_score, model_used, categorized_at)
                        VALUES (%s, %s, %s, 'sentence-transformer', NOW())
                    """, (video_id, cat_id, confidence))
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Error saving categories for video {video_id}: {e}")
        finally:
            self.pool.putconn(conn)
    
    def get_statistics(self) -> Dict:
        """Get categorization statistics"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                stats = {}
                
                cur.execute("SELECT COUNT(*) FROM videos")
                stats['total_videos'] = cur.fetchone()['count']
                
                cur.execute("""
                    SELECT COUNT(DISTINCT video_id) 
                    FROM video_categories
                """)
                stats['categorized_videos'] = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) FROM categories")
                stats['total_categories'] = cur.fetchone()['count']
                
                return stats
        finally:
            self.pool.putconn(conn)


class ContextIdentifier:
    """Identifies video context using sentence transformers"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db = DatabaseManager(config)
        
        print(f"Loading model: {config.model_name}...")
        self.model = SentenceTransformer(config.model_name, device=DEVICE)
        
        # Load and encode categories
        self.categories = []
        self.category_ids = []
        self.category_embeddings = None
        self.load_categories()
    
    def load_categories(self):
        """Load and encode all categories"""
        print("Loading categories from database...")
        categories_data = self.db.get_categories()
        
        if not categories_data:
            print("Error: No categories found in database")
            print("Run utility/categorize_videos.py first to discover categories")
            sys.exit(1)
        
        self.categories = [cat['name'] for cat in categories_data]
        self.category_ids = [cat['id'] for cat in categories_data]
        
        print(f"Encoding {len(self.categories)} categories...")
        
        # Expand category names for better matching
        expanded_categories = []
        for cat in self.categories:
            # Repeat category name for emphasis and add variations
            expanded = f"{cat} {cat} {cat}"
            
            # Add contextual expansions for common patterns
            if "story" in cat or "stories" in cat:
                expanded += " narrative tale personal experience"
            elif "tutorial" in cat:
                expanded += " how to guide teaching learn instruction"
            elif "review" in cat:
                expanded += " opinion analysis critique feedback"
            elif "comedy" in cat or "funny" in cat:
                expanded += " humor joke laugh entertainment"
            elif "dance" in cat:
                expanded += " dancing choreography movement music"
            
            expanded_categories.append(expanded)
        
        # Encode categories
        self.category_embeddings = self.model.encode(
            expanded_categories,
            convert_to_tensor=True,
            device=DEVICE,
            show_progress_bar=True
        )
        
        print(f"✓ Categories loaded and encoded")
    
    def prepare_video_text(self, video: Dict) -> str:
        """Prepare video text for encoding - TRANSCRIPT ONLY"""
        # Use ONLY the transcript for unbiased categorization
        transcript = video.get('whisper_transcription', '') or ''
        
        # Return transcript or placeholder if empty
        return transcript.strip() or "no transcript available"
    
    def identify_categories(self, video: Dict) -> Tuple[List[int], List[float], List[str]]:
        """Identify categories for a single video"""
        # Prepare and encode video text
        video_text = self.prepare_video_text(video)
        video_embedding = self.model.encode(
            [video_text],
            convert_to_tensor=True,
            device=DEVICE
        )
        
        # Calculate similarities with all categories
        similarities = cosine_similarity(
            video_embedding.cpu().numpy(),
            self.category_embeddings.cpu().numpy()
        )[0]
        
        # Get top categories above threshold
        top_indices = np.argsort(similarities)[::-1][:self.config.max_categories_per_video]
        
        selected_ids = []
        selected_scores = []
        selected_names = []
        
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= self.config.confidence_threshold:
                selected_ids.append(self.category_ids[idx])
                selected_scores.append(score)
                selected_names.append(self.categories[idx])
        
        # Ensure at least one category
        if not selected_ids and len(top_indices) > 0:
            idx = top_indices[0]
            selected_ids = [self.category_ids[idx]]
            selected_scores = [float(similarities[idx])]
            selected_names = [self.categories[idx]]
        
        return selected_ids, selected_scores, selected_names
    
    def process_batch(self, videos: List[Dict]) -> Tuple[int, int]:
        """Process a batch of videos"""
        successful = 0
        failed = 0
        
        # Prepare all video texts
        video_texts = [self.prepare_video_text(v) for v in videos]
        
        # Batch encode for efficiency
        print(f"  Encoding {len(videos)} videos...")
        video_embeddings = self.model.encode(
            video_texts,
            convert_to_tensor=True,
            device=DEVICE,
            show_progress_bar=False,
            batch_size=self.config.batch_size
        )
        
        # Calculate similarities for all videos
        similarities_matrix = cosine_similarity(
            video_embeddings.cpu().numpy(),
            self.category_embeddings.cpu().numpy()
        )
        
        # Process each video
        for i, video in enumerate(videos):
            similarities = similarities_matrix[i]
            
            # Get top categories
            top_indices = np.argsort(similarities)[::-1][:self.config.max_categories_per_video]
            
            selected_ids = []
            selected_scores = []
            selected_names = []
            
            for idx in top_indices:
                score = float(similarities[idx])
                if score >= self.config.confidence_threshold:
                    selected_ids.append(self.category_ids[idx])
                    selected_scores.append(score)
                    selected_names.append(self.categories[idx])
            
            # Ensure at least one category
            if not selected_ids and len(top_indices) > 0:
                idx = top_indices[0]
                selected_ids = [self.category_ids[idx]]
                selected_scores = [float(similarities[idx])]
                selected_names = [self.categories[idx]]
            
            # Save to database
            try:
                self.db.save_video_categories(video['id'], selected_ids, selected_scores)
                successful += 1
                
                # Log sample results
                if successful <= 3:
                    print(f"    Video {video['video_id']}: {', '.join(selected_names[:3])}")
                
            except Exception as e:
                failed += 1
                logging.error(f"Failed to save categories for video {video['id']}: {e}")
        
        return successful, failed
    
    def run(self):
        """Run the context identification process"""
        print("\n" + "="*60)
        print("CONTEXT IDENTIFICATION")
        print("="*60)
        
        # Get initial statistics
        stats = self.db.get_statistics()
        print(f"Database: {stats['total_videos']} videos, {stats['total_categories']} categories")
        print(f"Already categorized: {stats['categorized_videos']} videos")
        
        # Get videos to process
        print(f"\nLoading videos to process...")
        videos = self.db.get_videos_to_process(
            self.config.process_uncategorized_only,
            self.config.limit
        )
        
        if not videos:
            print("No videos to process")
            return
        
        print(f"Found {len(videos)} videos to categorize")
        
        # Process in batches
        batch_size = self.config.batch_size
        total_successful = 0
        total_failed = 0
        
        for i in range(0, len(videos), batch_size):
            batch = videos[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(videos) + batch_size - 1) // batch_size
            
            print(f"\n--- Batch {batch_num}/{total_batches} ---")
            print(f"  Processing {len(batch)} videos...")
            
            start_time = time.time()
            successful, failed = self.process_batch(batch)
            elapsed = time.time() - start_time
            
            total_successful += successful
            total_failed += failed
            
            print(f"  ✓ Processed in {elapsed:.1f}s")
            print(f"  Successful: {successful}, Failed: {failed}")
            
            # Show progress
            progress = (i + len(batch)) / len(videos) * 100
            print(f"  Overall progress: {progress:.1f}%")
        
        # Final statistics
        print("\n" + "="*60)
        print("COMPLETE")
        print("="*60)
        print(f"Total processed: {total_successful + total_failed}")
        print(f"Successful: {total_successful}")
        print(f"Failed: {total_failed}")
        
        # Updated statistics
        stats = self.db.get_statistics()
        print(f"\nDatabase now has {stats['categorized_videos']} categorized videos")
        
        uncategorized = stats['total_videos'] - stats['categorized_videos']
        if uncategorized > 0:
            print(f"Remaining uncategorized: {uncategorized}")


def main():
    parser = argparse.ArgumentParser(
        description="Identify context/categories for TikTok videos using sentence transformers"
    )
    
    # Optional arguments
    parser.add_argument('--model', default='all-MiniLM-L6-v2',
                       help='Sentence transformer model name')
    parser.add_argument('--batch-size', type=int, default=32,
                       help='Batch size for processing')
    parser.add_argument('--threshold', type=float, default=0.3,
                       help='Minimum confidence threshold')
    parser.add_argument('--max-categories', type=int, default=5,
                       help='Maximum categories per video')
    parser.add_argument('--limit', type=int,
                       help='Limit number of videos to process')
    parser.add_argument('--all', action='store_true',
                       help='Process all videos, not just uncategorized')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler('context_identification.log')]
    )
    
    # Create config
    config = Config(
        model_name=args.model,
        batch_size=args.batch_size,
        confidence_threshold=args.threshold,
        max_categories_per_video=args.max_categories,
        process_uncategorized_only=not args.all,
        limit=args.limit
    )
    
    # Run identification
    try:
        identifier = ContextIdentifier(config)
        identifier.run()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()