#!/usr/bin/env python3
"""
Intelligent video cleanup based on virality scores.
Keeps top performers and specified protected videos.
"""

import json
import os
import shutil
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_analysis_results():
    """Load the video analysis results."""
    results_path = "/Users/ethan/tiktok_scraper/video_analysis/reports/ubuntu_results/analysis_summary.json"
    
    with open(results_path, 'r') as f:
        data = json.load(f)
    
    return data['videos']

def calculate_cutoff_threshold(videos):
    """Calculate the 75th percentile threshold."""
    scores = [video['virality_score'] for video in videos]
    scores.sort()
    
    # 75th percentile
    index = int(len(scores) * 0.75)
    threshold = scores[index]
    
    logger.info(f"75th percentile threshold: {threshold:.3f}")
    return threshold

def identify_videos_to_keep(videos, threshold):
    """Identify which videos to keep based on threshold and protected list."""
    
    # Protected videos (must keep regardless of score)
    protected_videos = [
        'Yo I cant believe what I just found in my sons room  This is wild af Last one is absolutely insane Might be my final post here idk #fyp #foryou #askreddit #reddit #redditstories #storytime #parenting #teenagers #omg #shocking #wtf.mp4',
        'Yo this is the last part of my toaster saga Cant believe Im sharing this but yall asked for it Buckle up its about to get wild The aftermath was interesting to say the least Lets just say I wont be looking at kitchen appliances the same way again Ser.mp4',
        'Guys I messed up big time You wont believe what I did with my toaster  This is probably my last post before I go into hiding The ending is WILD #fyp #foryou #askreddit #reddit #redditstories #storytime #tifu #whatwasithinking #kitchenfails #toastergo.mp4'
    ]
    
    videos_to_keep = []
    videos_to_remove = []
    
    for video in videos:
        filename = video['filename']
        score = video['virality_score']
        
        # Keep if above threshold OR in protected list
        if score >= threshold or filename in protected_videos:
            videos_to_keep.append(video)
            logger.info(f"KEEP: {filename[:60]}... (Score: {score:.3f})")
        else:
            videos_to_remove.append(video)
            logger.info(f"REMOVE: {filename[:60]}... (Score: {score:.3f})")
    
    return videos_to_keep, videos_to_remove

def delete_videos_permanently(videos_to_remove):
    """Permanently delete videos instead of backing them up."""
    
    base_dirs = [
        "/Users/ethan/Downloads/ubuntu-results/posted",
        "/Users/ethan/Downloads/ubuntu-results/stories"
    ]
    
    deleted_count = 0
    not_found_count = 0
    
    for video_info in videos_to_remove:
        filename = video_info['filename']
        deleted = False
        
        # Search in both directories
        for base_dir in base_dirs:
            video_path = Path(base_dir) / filename
            
            if video_path.exists():
                # Delete the video permanently
                try:
                    os.remove(str(video_path))
                    logger.info(f"Deleted: {filename[:60]}...")
                    deleted_count += 1
                    deleted = True
                    break
                except Exception as e:
                    logger.error(f"Error deleting {filename}: {e}")
        
        if not deleted:
            logger.warning(f"Video not found: {filename[:60]}...")
            not_found_count += 1
    
    return deleted_count, not_found_count

def save_cleanup_report(videos_to_keep, videos_to_remove, deleted_count, not_found_count):
    """Save a report of the cleanup operation."""
    
    report = {
        "cleanup_timestamp": "2025-07-28",
        "total_analyzed": len(videos_to_keep) + len(videos_to_remove),
        "videos_kept": len(videos_to_keep),
        "videos_removed": len(videos_to_remove),
        "successfully_deleted": deleted_count,
        "not_found": not_found_count,
        "kept_videos": [
            {
                "filename": v['filename'],
                "virality_score": v['virality_score'],
                "category": v['category'],
                "reason": "High score" if v['virality_score'] >= 0.168 else "Protected video"
            }
            for v in videos_to_keep
        ],
        "removed_videos": [
            {
                "filename": v['filename'],
                "virality_score": v['virality_score'],
                "category": v['category']
            }
            for v in videos_to_remove
        ]
    }
    
    report_path = "/Users/ethan/tiktok_scraper/video_analysis/reports/cleanup_report.json"
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Cleanup report saved to: {report_path}")
    return report

def main():
    """Main cleanup function."""
    
    logger.info("Starting intelligent video cleanup...")
    
    # Load analysis results
    logger.info("Loading video analysis results...")
    videos = load_analysis_results()
    
    # Calculate threshold (75th percentile)
    threshold = calculate_cutoff_threshold(videos)
    
    # Identify videos to keep/remove
    logger.info("Identifying videos to keep/remove...")
    videos_to_keep, videos_to_remove = identify_videos_to_keep(videos, threshold)
    
    # Summary before action
    print("\n" + "="*60)
    print("CLEANUP SUMMARY")
    print("="*60)
    print(f"Total videos analyzed: {len(videos)}")
    print(f"Videos to keep: {len(videos_to_keep)}")
    print(f"Videos to remove: {len(videos_to_remove)}")
    print(f"Threshold (75th percentile): {threshold:.3f}")
    print(f"Videos will be PERMANENTLY DELETED")
    print("\nProtected videos (kept regardless of score):")
    protected_list = [
        'Yo I cant believe what I just found in my sons room...',
        'Yo this is the last part of my toaster saga...',
        'Guys I messed up big time You wont believe what I did with my toaster...'
    ]
    for protected in protected_list:
        print(f"  - {protected}")
    
    # Auto-proceed (user already approved via the request)
    print("\nProceeding with permanent deletion...")
    response = 'y'
    
    # Delete videos permanently
    logger.info("Permanently deleting low-performing videos...")
    deleted_count, not_found_count = delete_videos_permanently(videos_to_remove)
    
    # Save report
    report = save_cleanup_report(videos_to_keep, videos_to_remove, deleted_count, not_found_count)
    
    # Final summary
    print("\n" + "="*60)
    print("CLEANUP COMPLETE")
    print("="*60)
    print(f"Videos successfully deleted: {deleted_count}")
    print(f"Videos not found: {not_found_count}")
    print(f"Videos remaining: {len(videos_to_keep)}")
    print(f"Cleanup report: /Users/ethan/tiktok_scraper/video_analysis/reports/cleanup_report.json")
    
    # Show top 10 remaining videos
    print("\nTop 10 remaining videos by score:")
    print("-" * 60)
    sorted_kept = sorted(videos_to_keep, key=lambda x: x['virality_score'], reverse=True)
    for i, video in enumerate(sorted_kept[:10], 1):
        filename_short = video['filename'][:50] + "..." if len(video['filename']) > 50 else video['filename']
        print(f"{i:2d}. {filename_short}")
        print(f"    Score: {video['virality_score']:.3f} | Category: {video['category']}")

if __name__ == '__main__':
    main()