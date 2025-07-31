#!/usr/bin/env python3
"""
Generic Video Analysis Script - Portable Video Analyzer

This script analyzes videos from a local input directory within the video_analysis folder,
making it easy for users to add their own videos for analysis.

Usage:
    python analyze_videos.py [--input-dir INPUT_DIR] [--output-dir OUTPUT_DIR] [--model-size MODEL_SIZE]
    
Examples:
    python analyze_videos.py
    python analyze_videos.py --input-dir my_videos --model-size large
    python analyze_videos.py --input-dir custom_videos --output-dir custom_results
"""

import sys
import os
import argparse
from pathlib import Path
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from video_analysis.video_transcriber import VideoTranscriber, ViralityScorer, VideoAnalyzer
except ImportError:
    # Fallback if the module structure is different
    try:
        from video_transcriber import VideoTranscriber, ViralityScorer, VideoAnalyzer
    except ImportError:
        print("Error: Could not import video analysis modules.")
        print("Please ensure video_transcriber.py is available in the video_analysis directory.")
        sys.exit(1)

# Setup logging
def setup_logging(log_level=logging.INFO):
    """Setup logging configuration."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=log_level, format=log_format)
    
    # Also log to file
    script_dir = Path(__file__).parent
    log_file = script_dir / f"video_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Add file handler to root logger
    logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger(__name__)


def create_directories(input_dir: Path, output_dir: Path) -> bool:
    """Create necessary directories and validate setup."""
    
    # Create input directory if it doesn't exist
    if not input_dir.exists():
        print(f"📁 Creating input directory: {input_dir}")
        input_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a README file in the input directory
        readme_content = f"""# Video Input Directory

Place your video files in this directory for analysis.

## Supported Formats
- MP4 (.mp4)
- WebM (.webm)
- MOV (.mov)
- AVI (.avi)
- MKV (.mkv)

## Usage
1. Copy your video files to this directory
2. Run: python analyze_videos.py
3. Check results in: {output_dir}

## Example Files
You can test with sample videos by placing them here.
The analyzer will process all supported video files automatically.

Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        readme_file = input_dir / "README.md"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"📝 Created README file: {readme_file}")
        print(f"ℹ️  Please add video files to {input_dir} and run the script again.")
        return False
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return True


def find_video_files(input_dir: Path) -> list:
    """Find all video files in the input directory."""
    
    video_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v'}
    video_files = []
    
    for file_path in input_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in video_extensions:
            video_files.append(file_path)
    
    return sorted(video_files)


def validate_requirements():
    """Check if required dependencies are available."""
    try:
        import whisper
        import torch
        return True
    except ImportError:
        print("❌ Missing required dependencies for video analysis.")
        print("\nTo install dependencies, run:")
        print("pip install whisper-openai torch torchvision torchaudio")
        print("\nFor CPU-only installation:")
        print("pip install whisper-openai torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")
        return False


def print_analysis_summary(results: list, output_dir: Path, logger):
    """Print a comprehensive analysis summary."""
    
    print("\n" + "="*80)
    print("🎬 VIDEO ANALYSIS COMPLETE")
    print("="*80)
    
    total_videos = len(results)
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]
    
    print(f"📊 Analysis Summary:")
    print(f"   Total videos processed: {total_videos}")
    print(f"   ✅ Successful analyses: {len(successful)}")
    print(f"   ❌ Failed analyses: {len(failed)}")
    
    if failed:
        print(f"\n⚠️  Failed Videos:")
        for video in failed[:5]:  # Show first 5 failures
            print(f"   - {video.filename}: {video.error}")
        if len(failed) > 5:
            print(f"   ... and {len(failed) - 5} more")
    
    if successful:
        # Sort by virality score
        successful.sort(key=lambda x: x.virality_score, reverse=True)
        
        print(f"\n🏆 Top Performing Videos (by Virality Score):")
        print("-" * 80)
        
        for i, video in enumerate(successful[:10], 1):  # Show top 10
            print(f"{i:2d}. {video.filename}")
            print(f"    📈 Virality Score: {video.virality_score:.3f}")
            print(f"    🎯 Category: {video.content_category}")
            print(f"    🪝 Hook Strength: {video.hook_strength:.2f}")
            print(f"    😊 Emotions: {', '.join(video.emotional_triggers) if video.emotional_triggers else 'None'}")
            if hasattr(video, 'transcription') and video.transcription:
                preview = video.transcription[:100].replace('\n', ' ')
                print(f"    💬 Preview: {preview}...")
            print()
        
        # Category breakdown
        if successful:
            categories = {}
            for video in successful:
                cat = video.content_category or 'Unknown'
                categories[cat] = categories.get(cat, 0) + 1
            
            print(f"📂 Content Categories:")
            for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(successful)) * 100
                print(f"   {category}: {count} videos ({percentage:.1f}%)")
        
        # Average scores
        avg_virality = sum(v.virality_score for v in successful) / len(successful)
        avg_hook = sum(v.hook_strength for v in successful) / len(successful)
        
        print(f"\n📊 Average Metrics:")
        print(f"   Virality Score: {avg_virality:.3f}")
        print(f"   Hook Strength: {avg_hook:.3f}")
    
    print(f"\n📁 Results Location:")
    print(f"   Output Directory: {output_dir}")
    print(f"   Summary Report: {output_dir}/analysis_summary.json")
    print(f"   Detailed Report: {output_dir}/analysis_report.md")
    print(f"   Individual Results: {output_dir}/<video_name>_analysis.json")
    
    # Log file location
    log_files = list(Path(__file__).parent.glob("video_analysis_*.log"))
    if log_files:
        latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
        print(f"   Log File: {latest_log}")
    
    print("="*80)


def main():
    """Main analysis function."""
    
    parser = argparse.ArgumentParser(
        description="Analyze videos for content insights and virality potential",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_videos.py
  python analyze_videos.py --input-dir my_videos
  python analyze_videos.py --input-dir test_videos --model-size large
  python analyze_videos.py --output-dir custom_results --verbose
        """
    )
    
    parser.add_argument(
        '--input-dir', '-i',
        type=str,
        default='input_videos',
        help='Input directory containing videos to analyze (default: input_videos)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='results',
        help='Output directory for analysis results (default: results)'
    )
    
    parser.add_argument(
        '--model-size', '-m',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        default='base',
        help='Whisper model size for transcription (default: base)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--max-videos',
        type=int,
        default=None,
        help='Maximum number of videos to process (default: all)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(log_level)
    
    # Setup paths relative to script location
    script_dir = Path(__file__).parent
    input_dir = script_dir / args.input_dir
    output_dir = script_dir / args.output_dir
    
    logger.info("🎬 Starting Video Analysis")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Model size: {args.model_size}")
    
    # Validate requirements
    if not validate_requirements():
        sys.exit(1)
    
    # Create and validate directories
    if not create_directories(input_dir, output_dir):
        # Input directory was created but is empty
        sys.exit(0)
    
    # Find video files
    video_files = find_video_files(input_dir)
    
    if not video_files:
        print(f"❌ No video files found in {input_dir}")
        print(f"📁 Supported formats: .mp4, .webm, .mov, .avi, .mkv, .flv, .wmv, .m4v")
        print(f"💡 Add video files to {input_dir} and run again.")
        sys.exit(1)
    
    # Limit videos if specified
    if args.max_videos and len(video_files) > args.max_videos:
        logger.info(f"Limiting analysis to first {args.max_videos} videos")
        video_files = video_files[:args.max_videos]
    
    print(f"🎥 Found {len(video_files)} video files to analyze")
    for i, video_file in enumerate(video_files, 1):
        print(f"   {i:2d}. {video_file.name}")
    print()
    
    # Initialize components
    try:
        logger.info("🔧 Initializing video analyzer components...")
        transcriber = VideoTranscriber(model_size=args.model_size)
        scorer = ViralityScorer()
        analyzer = VideoAnalyzer(transcriber, scorer)
        logger.info("✅ Video analyzer initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize video analyzer: {e}")
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)
    
    # Run analysis
    try:
        logger.info("🚀 Starting video analysis process...")
        print("🔄 Analyzing videos... (this may take a while)")
        
        results = analyzer.analyze_directory(str(input_dir), str(output_dir))
        
        logger.info(f"✅ Analysis complete: {len(results)} videos processed")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)
    
    # Print summary
    print_analysis_summary(results, output_dir, logger)
    
    # Success message
    print("\n🎉 Video analysis completed successfully!")
    print(f"💡 Review the results in {output_dir} for detailed insights.")


if __name__ == '__main__':
    main()