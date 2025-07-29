#!/usr/bin/env python3
"""
Script to analyze videos from ubuntu-results directory
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video_analysis.video_transcriber import VideoTranscriber, ViralityScorer, VideoAnalyzer
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    # Directories
    input_dir = "/Users/ethan/Downloads/ubuntu-results"
    output_dir = "/Users/ethan/tiktok_scraper/video_analysis/reports/ubuntu_results"
    
    logger.info(f"Starting analysis of videos in: {input_dir}")
    logger.info(f"Results will be saved to: {output_dir}")
    
    # Initialize components
    logger.info("Initializing video analyzer...")
    transcriber = VideoTranscriber(model_size="base")  # Using base model for balance of speed/accuracy
    scorer = ViralityScorer()
    analyzer = VideoAnalyzer(transcriber, scorer)
    
    # Run analysis
    logger.info("Starting video analysis...")
    results = analyzer.analyze_directory(input_dir, output_dir)
    
    # Print summary
    print("\n" + "="*60)
    print("VIDEO ANALYSIS COMPLETE")
    print("="*60)
    print(f"Total videos analyzed: {len(results)}")
    
    successful = [r for r in results if r.error is None]
    if successful:
        print(f"Successful analyses: {len(successful)}")
        print(f"Failed analyses: {len(results) - len(successful)}")
        
        # Sort by score
        successful.sort(key=lambda x: x.virality_score, reverse=True)
        
        print("\nTop 5 Videos by Virality Score:")
        print("-"*60)
        for i, video in enumerate(successful[:5], 1):
            print(f"{i}. {video.filename[:50]}...")
            print(f"   Score: {video.virality_score:.3f}")
            print(f"   Category: {video.content_category}")
            print(f"   Hook: {video.hook_strength:.2f}")
            print(f"   Emotions: {', '.join(video.emotional_triggers) or 'None'}")
            print()
    
    print(f"\nFull results saved to:")
    print(f"- Summary: {output_dir}/analysis_summary.json")
    print(f"- Report: {output_dir}/analysis_report.md")
    print(f"- Individual analyses: {output_dir}/<video>_analysis.json")


if __name__ == '__main__':
    main()