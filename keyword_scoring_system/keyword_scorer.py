#!/usr/bin/env python3
"""
Keyword Scoring System for TikTok Content Analysis

This script processes TikTok video data to extract and score keywords based on their
correlation with video performance metrics. It combines NLP techniques, sentiment
analysis, and engagement metrics to identify high-performing keywords.

Usage:
    python keyword_scorer.py /path/to/master2.json --output results/keyword_scores
    python keyword_scorer.py /path/to/master2.json --max-videos 1000 --methods rake textrank
    python keyword_scorer.py /path/to/master2.json --sentiment --min-engagement 0.01
"""

import click
import logging
import sys
from pathlib import Path
from typing import List, Optional
import json
import time

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.data_loader import TikTokDataLoader
from src.keyword_extractor import TikTokKeywordExtractor
from src.sentiment_analyzer import TikTokSentimentAnalyzer
from src.scoring_engine import KeywordScoringEngine, score_keywords

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('keyword_scoring.log')
    ]
)

logger = logging.getLogger(__name__)


@click.command()
@click.argument('json_path', type=click.Path(exists=True), required=True)
@click.option('--output', '-o', default='output/keyword_scores', 
              help='Output path for results (without extension)')
@click.option('--max-videos', '-n', type=int, default=None,
              help='Maximum number of videos to process')
@click.option('--methods', '-m', multiple=True, 
              type=click.Choice(['rake', 'textrank', 'tfidf', 'yake']),
              default=['rake', 'textrank', 'yake'],
              help='Keyword extraction methods to use')
@click.option('--sentiment/--no-sentiment', default=True,
              help='Enable or disable sentiment analysis')
@click.option('--min-engagement', type=float, default=0.0,
              help='Minimum engagement score for videos')
@click.option('--min-keyword-score', type=float, default=0.1,
              help='Minimum keyword extraction score')
@click.option('--min-video-count', type=int, default=2,
              help='Minimum videos a keyword must appear in')
@click.option('--batch-size', type=int, default=100,
              help='Batch size for processing')
@click.option('--require-transcription/--no-require-transcription', default=False,
              help='Only process videos with transcription')
@click.option('--require-comments/--no-require-comments', default=False,
              help='Only process videos with comments')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv', 'both']),
              default='both', help='Output format')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def main(json_path: str,
         output: str,
         max_videos: Optional[int],
         methods: List[str],
         sentiment: bool,
         min_engagement: float,
         min_keyword_score: float,
         min_video_count: int,
         batch_size: int,
         require_transcription: bool,
         require_comments: bool,
         output_format: str,
         verbose: bool):
    """
    Process TikTok video data to extract and score keywords.
    
    JSON_PATH: Path to the master2.json file containing TikTok video data
    """
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting TikTok Keyword Scoring System")
    logger.info(f"Input file: {json_path}")
    logger.info(f"Output path: {output}")
    logger.info(f"Max videos: {max_videos or 'All'}")
    logger.info(f"Extraction methods: {list(methods)}")
    logger.info(f"Sentiment analysis: {sentiment}")
    
    start_time = time.time()
    
    try:
        # Create output directory
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load data
        logger.info("Loading TikTok data...")
        data_loader = TikTokDataLoader(json_path)
        data_loader.load_data(
            max_videos=max_videos,
            min_engagement=min_engagement,
            require_transcription=require_transcription,
            require_comments=require_comments
        )
        
        # Get data statistics
        stats = data_loader.get_statistics()
        logger.info(f"Loaded {stats['total_videos']} videos")
        logger.info(f"Average engagement: {stats['avg_engagement']:.6f}")
        logger.info(f"Videos with transcription: {stats['videos_with_transcription']}")
        logger.info(f"Videos with comments: {stats['videos_with_comments']}")
        
        # Initialize scoring engine
        logger.info("Initializing keyword scoring engine...")
        scoring_engine = KeywordScoringEngine(
            extraction_methods=list(methods),
            sentiment_analysis=sentiment
        )
        
        # Process dataset
        logger.info("Processing videos and extracting keywords...")
        keyword_scores = scoring_engine.process_dataset(
            data_loader=data_loader,
            batch_size=batch_size,
            min_keyword_score=min_keyword_score
        )
        
        # Filter by minimum video count
        keyword_scores = [
            score for score in keyword_scores 
            if score.video_count >= min_video_count
        ]
        
        logger.info(f"Generated scores for {len(keyword_scores)} keywords")
        
        # Save results
        logger.info(f"Saving results to {output_path}")
        scoring_engine.save_results(
            keyword_scores=keyword_scores,
            output_path=output_path,
            format=output_format
        )
        
        # Print summary statistics
        processing_stats = scoring_engine.get_statistics()
        print_summary(keyword_scores, processing_stats, time.time() - start_time)
        
        # Print top keywords
        print_top_keywords(keyword_scores[:20])
        
        logger.info("Keyword scoring completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise click.ClickException(f"Processing failed: {e}")


def print_summary(keyword_scores: List, processing_stats: dict, elapsed_time: float):
    """Print summary statistics."""
    
    print("\n" + "="*60)
    print("KEYWORD SCORING SUMMARY")
    print("="*60)
    
    print(f"Processing time: {elapsed_time:.2f} seconds")
    print(f"Videos processed: {processing_stats['processed_videos']}")
    print(f"Keywords identified: {processing_stats['total_keywords']}")
    print(f"Keywords with scores: {len(keyword_scores)}")
    print(f"Avg keywords per video: {processing_stats['avg_keywords_per_video']:.2f}")
    print(f"Unique content contexts: {processing_stats['unique_contexts']}")
    
    if keyword_scores:
        scores = [k.final_score for k in keyword_scores]
        print(f"Score range: {min(scores):.4f} - {max(scores):.4f}")
        print(f"Average score: {sum(scores)/len(scores):.4f}")


def print_top_keywords(top_keywords: List):
    """Print top performing keywords."""
    
    print("\n" + "="*60)
    print("TOP 20 PERFORMING KEYWORDS")
    print("="*60)
    
    print(f"{'Rank':<4} {'Keyword':<20} {'Score':<8} {'Videos':<7} {'Avg Eng':<8} {'Sentiment':<9}")
    print("-" * 60)
    
    for i, keyword in enumerate(top_keywords[:20], 1):
        print(f"{i:<4} {keyword.keyword:<20} {keyword.final_score:<8.3f} "
              f"{keyword.video_count:<7} {keyword.avg_engagement:<8.5f} "
              f"{keyword.sentiment_score:<9.3f}")


@click.command()
@click.argument('results_path', type=click.Path(exists=True))
@click.option('--top-k', '-k', type=int, default=50, help='Number of top keywords to show')
@click.option('--filter-context', type=str, help='Filter by content context')
@click.option('--min-videos', type=int, default=1, help='Minimum video count')
def analyze_results(results_path: str, top_k: int, filter_context: str, min_videos: int):
    """
    Analyze and display keyword scoring results.
    
    RESULTS_PATH: Path to the JSON results file
    """
    
    logger.info(f"Loading results from {results_path}")
    
    try:
        with open(results_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        keywords = data['keywords']
        metadata = data['metadata']
        
        # Filter keywords
        filtered_keywords = []
        for keyword in keywords:
            if keyword['video_count'] < min_videos:
                continue
            
            if filter_context:
                if filter_context not in keyword['context_categories']:
                    continue
            
            filtered_keywords.append(keyword)
        
        # Sort by final score
        filtered_keywords.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Display results
        print(f"\nAnalysis of {len(filtered_keywords)} keywords")
        print(f"Original dataset: {metadata['processed_videos']} videos")
        print(f"Extraction methods: {', '.join(metadata['extraction_methods'])}")
        
        if filter_context:
            print(f"Filtered by context: {filter_context}")
        
        print(f"\nTop {min(top_k, len(filtered_keywords))} keywords:")
        print("-" * 80)
        
        for i, keyword in enumerate(filtered_keywords[:top_k], 1):
            contexts = ', '.join(keyword['context_categories'][:3])
            print(f"{i:2d}. {keyword['keyword']:<25} "
                  f"Score: {keyword['final_score']:7.3f} "
                  f"Videos: {keyword['video_count']:3d} "
                  f"Contexts: {contexts}")
        
    except Exception as e:
        logger.error(f"Error analyzing results: {e}")
        raise click.ClickException(f"Analysis failed: {e}")


@click.group()
def cli():
    """TikTok Keyword Scoring System CLI"""
    pass


cli.add_command(main, name='score')
cli.add_command(analyze_results, name='analyze')


if __name__ == '__main__':
    cli()