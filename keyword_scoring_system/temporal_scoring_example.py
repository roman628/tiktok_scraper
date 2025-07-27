#!/usr/bin/env python3
"""
Simple example of using the Time-Weighted Gradient Scoring System.

This script demonstrates how to apply temporal weighting to TikTok content analysis.
"""

import sys
import json
from pathlib import Path

# Add the src directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

from temporal_scoring_engine import score_keywords_with_temporal_weighting


def main():
    """Example usage of temporal scoring system."""
    
    print("Time-Weighted Gradient Scoring System - Example Usage")
    print("=" * 60)
    
    # Check if master2.json exists
    data_path = Path(__file__).parent.parent / "master2.json"
    
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        print("Please ensure master2.json is available in the project root.")
        return
    
    # Example 1: Default temporal parameters
    print("\n1. Running with default temporal parameters...")
    print("-" * 50)
    
    try:
        output_path = Path(__file__).parent / "output" / "temporal_results_default"
        output_path.parent.mkdir(exist_ok=True)
        
        temporal_scores = score_keywords_with_temporal_weighting(
            json_path=data_path,
            output_path=output_path,
            max_videos=100,  # Process first 100 videos for this example
            extraction_methods=['rake', 'yake'],
            sentiment_analysis=False  # Disable for faster processing
        )
        
        print(f"✓ Processed successfully!")
        print(f"✓ Total keywords found: {len(temporal_scores)}")
        print(f"✓ Results saved to: {output_path}.json")
        
        # Show top 10 temporal keywords
        print("\nTop 10 Temporal Keywords:")
        print("-" * 40)
        for i, score in enumerate(temporal_scores[:10]):
            print(f"{i+1:2d}. {score.keyword:20s} (Score: {score.temporal_weighted_score:6.2f}, "
                  f"Peak: {score.peak_timing:4.1f}s)")
        
    except Exception as e:
        print(f"✗ Error processing with default parameters: {e}")
    
    # Example 2: Aggressive early weighting
    print("\n2. Running with aggressive early weighting...")
    print("-" * 50)
    
    try:
        aggressive_params = {
            'peak_weight': 4.0,        # Higher peak weight
            'decay_rate': 0.5,         # Faster decay
            'minimum_weight': 0.3      # Lower minimum weight
        }
        
        output_path = Path(__file__).parent / "output" / "temporal_results_aggressive"
        
        temporal_scores_aggressive = score_keywords_with_temporal_weighting(
            json_path=data_path,
            output_path=output_path,
            max_videos=100,
            temporal_params=aggressive_params,
            extraction_methods=['rake', 'yake'],
            sentiment_analysis=False
        )
        
        print(f"✓ Processed successfully with aggressive parameters!")
        print(f"✓ Total keywords found: {len(temporal_scores_aggressive)}")
        print(f"✓ Results saved to: {output_path}.json")
        
        # Show top early keywords
        early_keywords = [s for s in temporal_scores_aggressive if s.peak_timing <= 5.0]
        print(f"\nTop Early Keywords (≤5s): {len(early_keywords)} total")
        print("-" * 40)
        for i, score in enumerate(early_keywords[:8]):
            print(f"{i+1:2d}. {score.keyword:20s} (Score: {score.temporal_weighted_score:6.2f}, "
                  f"Boost: {score.early_presence_boost:4.2f}x)")
        
    except Exception as e:
        print(f"✗ Error processing with aggressive parameters: {e}")
    
    # Example 3: Conservative weighting for longer content
    print("\n3. Running with conservative weighting...")
    print("-" * 50)
    
    try:
        conservative_params = {
            'peak_weight': 2.0,        # Lower peak weight
            'decay_rate': 0.15,        # Slower decay
            'minimum_weight': 0.6      # Higher minimum weight
        }
        
        output_path = Path(__file__).parent / "output" / "temporal_results_conservative"
        
        temporal_scores_conservative = score_keywords_with_temporal_weighting(
            json_path=data_path,
            output_path=output_path,
            max_videos=100,
            temporal_params=conservative_params,
            extraction_methods=['rake', 'yake'],
            sentiment_analysis=False
        )
        
        print(f"✓ Processed successfully with conservative parameters!")
        print(f"✓ Total keywords found: {len(temporal_scores_conservative)}")
        print(f"✓ Results saved to: {output_path}.json")
        
        # Show temporal consistency leaders
        consistent_keywords = sorted(temporal_scores_conservative, 
                                   key=lambda x: x.temporal_consistency, reverse=True)
        print(f"\nMost Temporally Consistent Keywords:")
        print("-" * 40)
        for i, score in enumerate(consistent_keywords[:8]):
            print(f"{i+1:2d}. {score.keyword:20s} (Consistency: {score.temporal_consistency:5.3f}, "
                  f"Peak: {score.peak_timing:4.1f}s)")
        
    except Exception as e:
        print(f"✗ Error processing with conservative parameters: {e}")
    
    # Analysis Summary
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    
    print("\nKey Insights:")
    print("• Default parameters provide balanced temporal weighting")
    print("• Aggressive weighting emphasizes hook effectiveness")
    print("• Conservative weighting maintains content flow quality")
    print("• Early keywords (0-5s) typically receive 1.5-2.0x boost")
    print("• Temporal consistency rewards even keyword distribution")
    
    print("\nOutput Files Generated:")
    output_dir = Path(__file__).parent / "output"
    if output_dir.exists():
        for file_path in output_dir.glob("temporal_results_*.json"):
            print(f"• {file_path.name}")
    
    print("\nRecommendations:")
    print("• Use default parameters for general content analysis")
    print("• Use aggressive parameters for hook optimization")
    print("• Use conservative parameters for longer-form content")
    print("• Combine with engagement metrics for viral prediction")


if __name__ == "__main__":
    main()