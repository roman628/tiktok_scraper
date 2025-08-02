#!/Users/ethan/tiktok_scraper/venv/bin/python
"""
Master TikTok Downloader and Comment Extractor
Combines video downloading with comment extraction into a single master2.json file
"""

import os
import sys
import json
import argparse
import asyncio
import time
from pathlib import Path
from datetime import datetime

# Import the video downloader functions
from tiktok_scraper import (
    download_tiktok_video, 
    append_batch_to_master_json,
    load_whisper_model,
    diagnose_cuda_environment
)

# Import comment extraction function
from update_comments_v2 import extract_video_comments_no_save


async def download_and_extract_comments(url, download_kwargs, max_comments=10):
    """
    Download video and extract comments for a single URL
    Returns combined metadata or None if failed
    """
    try:
        print(f"🎬 Downloading video: {url}")
        
        # Download video first
        result = download_tiktok_video(url, **download_kwargs)
        
        if not result['success']:
            print(f"❌ Video download failed: {result.get('error', 'Unknown error')}")
            return None
        
        metadata = result['metadata']
        print(f"✅ Video downloaded successfully")
        
        # Extract comments
        print(f"💬 Extracting comments...")
        try:
            comments = await extract_video_comments_no_save(url, max_comments)
            if comments:
                metadata['top_comments'] = comments
                metadata['comments_extracted'] = True
                metadata['comments_extracted_at'] = datetime.now().isoformat()
                print(f"✅ Extracted {len(comments)} comments")
            else:
                metadata['top_comments'] = []
                metadata['comments_extracted'] = False
                print(f"⚠️  No comments extracted")
        except Exception as e:
            print(f"❌ Comment extraction failed: {e}")
            metadata['top_comments'] = []
            metadata['comments_extracted'] = False
            metadata['comment_error'] = str(e)
        
        return metadata
        
    except Exception as e:
        print(f"❌ Error processing {url}: {e}")
        return None


async def process_urls_with_comments(urls, download_kwargs, max_comments=10, batch_size=10, delay=2):
    """
    Process multiple URLs with both video download and comment extraction
    """
    print(f"🚀 Starting combined download and comment extraction")
    print(f"📊 Total URLs: {len(urls)}")
    print(f"📦 Batch size: {batch_size}")
    print(f"💬 Max comments per video: {max_comments}")
    print(f"⏱️  Delay between requests: {delay} seconds")
    print("="*60)
    
    successful_count = 0
    failed_count = 0
    batch_metadata = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"Processing {i}/{len(urls)}: {url}")
        print(f"{'='*60}")
        
        # Process single URL
        metadata = await download_and_extract_comments(url, download_kwargs, max_comments)
        
        if metadata:
            batch_metadata.append(metadata)
            successful_count += 1
            print(f"✅ {i}/{len(urls)} completed successfully")
        else:
            failed_count += 1
            print(f"❌ {i}/{len(urls)} failed")
        
        # Auto-save batch every batch_size successful downloads
        if len(batch_metadata) >= batch_size:
            print(f"\n💾 Auto-saving batch of {len(batch_metadata)} videos to master2.json...")
            append_batch_to_master_json(batch_metadata, "master2.json")
            batch_metadata = []  # Reset batch
        
        # Add delay between requests to be respectful
        if i < len(urls):  # Don't delay after the last URL
            print(f"⏱️  Waiting {delay} seconds...")
            time.sleep(delay)
    
    # Save any remaining metadata at the end
    if batch_metadata:
        print(f"\n💾 Saving final batch of {len(batch_metadata)} videos to master2.json...")
        append_batch_to_master_json(batch_metadata, "master2.json")
    
    print(f"\n🎉 Processing completed!")
    print(f"✅ Successful: {successful_count}/{len(urls)}")
    print(f"❌ Failed: {failed_count}/{len(urls)}")
    
    return successful_count, failed_count


def load_urls_from_file(file_path):
    """Load URLs from text file"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
    
    if not urls:
        print("❌ No valid TikTok URLs found in file")
        return []
    
    print(f"📂 Loaded {len(urls)} URLs from {file_path}")
    return urls


async def main():
    parser = argparse.ArgumentParser(description="Combined TikTok video downloader and comment extractor")
    
    # Input options
    parser.add_argument("url", nargs='?', help="Single TikTok video URL (not needed with --from-file)")
    parser.add_argument("--from-file", "-ff", type=str, help="Batch process URLs from text file")
    parser.add_argument("--limit", type=int, help="Limit number of URLs to process (for testing)")
    
    # Download options
    parser.add_argument("-o", "--output", default="downloads", help="Output directory (default: downloads)")
    parser.add_argument("-q", "--quality", default="best", choices=["best", "worst", "720p", "480p", "360p"],
                       help="Video quality (default: best)")
    parser.add_argument("--mp3", action="store_true", help="Download audio only as MP3 instead of video")
    parser.add_argument("--whisper", action="store_true", help="Use faster-whisper for additional transcription")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU mode for whisper (bypass GPU issues)")
    
    # Comment options
    parser.add_argument("--max-comments", type=int, default=10, help="Maximum comments to extract per video (default: 10)")
    parser.add_argument("--batch-size", type=int, default=10, help="Save to master2.json every N videos (default: 10)")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests in seconds (default: 2)")
    
    # System options
    parser.add_argument("--diagnose", action="store_true", help="Diagnose CUDA environment and exit")
    
    args = parser.parse_args()
    
    # Handle diagnostic mode
    if args.diagnose:
        diagnose_cuda_environment()
        return
    
    # Validate arguments
    if not args.url and not args.from_file:
        print("❌ Either provide a URL or use --from-file")
        sys.exit(1)
    
    if args.url and "tiktok.com" not in args.url:
        print("❌ Please provide a valid TikTok URL")
        sys.exit(1)
    
    # Load whisper model if requested
    whisper_model = None
    whisper_device = "CPU"
    if args.whisper:
        print("🎤 Loading faster-whisper model...")
        whisper_model, whisper_device = load_whisper_model(force_cpu=args.force_cpu)
        if not whisper_model:
            print("❌ Failed to load whisper model")
            sys.exit(1)
        print(f"✅ Whisper model loaded on {whisper_device}")
    
    # Prepare download kwargs
    download_kwargs = {
        'output_dir': args.output,
        'quality': args.quality,
        'audio_only': args.mp3,
        'use_whisper': args.whisper,
        'whisper_model': whisper_model,
        'whisper_device': whisper_device,
        'scrape_comments': False  # We handle comments separately
    }
    
    # Get URLs to process
    if args.from_file:
        urls = load_urls_from_file(args.from_file)
        if args.limit:
            urls = urls[:args.limit]
            print(f"🔢 Limited to first {args.limit} URLs")
    else:
        urls = [args.url]
    
    if not urls:
        print("❌ No URLs to process")
        sys.exit(1)
    
    # Process URLs
    try:
        successful, failed = await process_urls_with_comments(
            urls, 
            download_kwargs, 
            max_comments=args.max_comments,
            batch_size=args.batch_size,
            delay=args.delay
        )
        
        print(f"\n📊 Final Summary:")
        print(f"   Total processed: {len(urls)}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Success rate: {successful/len(urls)*100:.1f}%")
        
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())