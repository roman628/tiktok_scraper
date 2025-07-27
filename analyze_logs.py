#!/usr/bin/env python3
"""
Log Analysis Tool for Multiprocessing Transcription Issues
Analyzes worker logs to identify transcription problems
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path


def analyze_worker_logs():
    """Analyze all worker logs for transcription issues"""
    
    log_dir = "multiprocess-logs"
    if not os.path.exists(log_dir):
        print("❌ No multiprocess-logs directory found")
        print("   Run the scraper with --workers > 1 first to generate logs")
        return
    
    # Find all worker log files
    worker_logs = []
    for file in os.listdir(log_dir):
        if file.startswith("worker_") and file.endswith(".log"):
            worker_logs.append(os.path.join(log_dir, file))
    
    if not worker_logs:
        print("❌ No worker log files found")
        return
    
    print(f"🔍 Analyzing {len(worker_logs)} worker log files...")
    print("=" * 60)
    
    transcription_stats = {
        'total_workers': len(worker_logs),
        'workers_with_whisper': 0,
        'workers_with_transcription_attempts': 0,
        'workers_with_successful_transcriptions': 0,
        'workers_with_errors': 0,
        'common_errors': {},
        'transcription_times': []
    }
    
    for log_file in sorted(worker_logs):
        worker_id = re.search(r'worker_(\d+)\.log', log_file).group(1)
        print(f"\n📋 WORKER {worker_id} ANALYSIS:")
        print(f"   Log file: {log_file}")
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Analyze Whisper model loading
            whisper_loaded = "Whisper model loaded" in content
            whisper_failed = "Failed to load whisper model" in content or "Whisper model: ❌" in content
            
            if whisper_loaded:
                transcription_stats['workers_with_whisper'] += 1
                print("   ✅ Whisper model loaded successfully")
            elif whisper_failed:
                print("   ❌ Whisper model failed to load")
                transcription_stats['workers_with_errors'] += 1
            else:
                print("   ⚠️  No clear Whisper loading status")
            
            # Analyze transcription attempts
            transcription_attempts = content.count("Starting Whisper transcription")
            if transcription_attempts > 0:
                transcription_stats['workers_with_transcription_attempts'] += 1
                print(f"   🎤 Transcription attempts: {transcription_attempts}")
            
            # Analyze successful transcriptions
            successful_transcriptions = content.count("TRANSCRIPTION SUCCESS")
            if successful_transcriptions > 0:
                transcription_stats['workers_with_successful_transcriptions'] += 1
                print(f"   ✅ Successful transcriptions: {successful_transcriptions}")
            
            # Look for transcription errors
            error_patterns = [
                (r"Transcription failed: (.+)", "Transcription failure"),
                (r"Transcription timeout after (\d+)s", "Timeout"),
                (r"No audio file found for transcription", "Missing audio file"),
                (r"Audio file not found: (.+)", "Audio file not found"),
                (r"Whisper initialization failed: (.+)", "Whisper init failure"),
                (r"❌ Worker \d+ error: (.+)", "Worker error")
            ]
            
            errors_found = []
            for pattern, error_type in error_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    errors_found.append(f"{error_type}: {len(matches)} occurrences")
                    if error_type not in transcription_stats['common_errors']:
                        transcription_stats['common_errors'][error_type] = 0
                    transcription_stats['common_errors'][error_type] += len(matches)
            
            if errors_found:
                print("   ❌ Errors found:")
                for error in errors_found:
                    print(f"      - {error}")
                transcription_stats['workers_with_errors'] += 1
            
            # Look for transcription timing info
            timing_matches = re.findall(r"Transcription completed in ([\d.]+)s for ([\d.]+)s audio", content)
            if timing_matches:
                for completion_time, audio_duration in timing_matches:
                    ratio = float(completion_time) / float(audio_duration)
                    transcription_stats['transcription_times'].append({
                        'completion_time': float(completion_time),
                        'audio_duration': float(audio_duration),
                        'ratio': ratio
                    })
                    print(f"   ⏱️  Transcription timing: {completion_time}s for {audio_duration}s audio (ratio: {ratio:.1f}x)")
            
            # Look for partial transcriptions
            partial_transcriptions = content.count("Saved partial transcription")
            if partial_transcriptions > 0:
                print(f"   📝 Partial transcriptions saved: {partial_transcriptions}")
            
            # Check for download directory issues
            download_dir_issues = content.count("Download directory does not exist")
            if download_dir_issues > 0:
                print(f"   ⚠️  Download directory issues: {download_dir_issues}")
        
        except Exception as e:
            print(f"   ❌ Error reading log file: {e}")
    
    # Print overall statistics
    print("\n" + "=" * 60)
    print("📊 OVERALL TRANSCRIPTION ANALYSIS:")
    print("=" * 60)
    print(f"Total workers: {transcription_stats['total_workers']}")
    print(f"Workers with Whisper loaded: {transcription_stats['workers_with_whisper']}")
    print(f"Workers with transcription attempts: {transcription_stats['workers_with_transcription_attempts']}")
    print(f"Workers with successful transcriptions: {transcription_stats['workers_with_successful_transcriptions']}")
    print(f"Workers with errors: {transcription_stats['workers_with_errors']}")
    
    if transcription_stats['common_errors']:
        print("\n🚨 COMMON ERRORS:")
        for error_type, count in sorted(transcription_stats['common_errors'].items(), key=lambda x: x[1], reverse=True):
            print(f"  - {error_type}: {count} occurrences")
    
    if transcription_stats['transcription_times']:
        times = transcription_stats['transcription_times']
        avg_ratio = sum(t['ratio'] for t in times) / len(times)
        print(f"\n⏱️  TRANSCRIPTION PERFORMANCE:")
        print(f"  - Average processing ratio: {avg_ratio:.1f}x real-time")
        print(f"  - Total transcriptions analyzed: {len(times)}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if transcription_stats['workers_with_whisper'] == 0:
        print("  ❌ No workers successfully loaded Whisper models")
        print("     - Check faster-whisper installation")
        print("     - Verify virtual environment activation")
        print("     - Try --force-cpu flag")
    elif transcription_stats['workers_with_whisper'] < transcription_stats['total_workers']:
        print("  ⚠️  Some workers failed to load Whisper models")
        print("     - GPU context conflicts likely")
        print("     - Consider using --force-cpu for all workers")
    
    if transcription_stats['workers_with_transcription_attempts'] == 0:
        print("  ❌ No transcription attempts found")
        print("     - Check --whisper flag is enabled")
        print("     - Verify audio files are being downloaded")
    elif transcription_stats['workers_with_successful_transcriptions'] == 0:
        print("  ❌ No successful transcriptions despite attempts")
        print("     - Check individual worker logs for specific errors")
        print("     - Audio file path issues likely")
    
    print("\n📁 LOG FILES:")
    print(f"  Master logs: {log_dir}/master_*.log")
    print(f"  Worker logs: {log_dir}/worker_*.log")
    print("  Analyze these files for detailed debugging information")


def check_master_json_transcriptions():
    """Check master2.json for actual transcription results"""
    
    master_file = "master2.json"
    if not os.path.exists(master_file):
        print(f"❌ {master_file} not found")
        return
    
    try:
        with open(master_file, 'r') as f:
            data = json.load(f)
        
        if not data:
            print("❌ master2.json is empty")
            return
        
        print(f"\n📊 MASTER2.JSON TRANSCRIPTION ANALYSIS:")
        print("=" * 60)
        print(f"Total entries: {len(data)}")
        
        with_whisper = 0
        with_transcription = 0
        with_subtitles = 0
        
        for entry in data:
            if entry.get('whisper_transcription') and len(entry['whisper_transcription']) > 10:
                with_whisper += 1
            
            if entry.get('transcription') and len(entry['transcription']) > 10:
                with_transcription += 1
            
            if (entry.get('subtitle') and len(entry['subtitle']) > 10) or \
               (entry.get('automatic_captions') and len(entry['automatic_captions']) > 10):
                with_subtitles += 1
        
        print(f"Entries with Whisper transcription: {with_whisper}")
        print(f"Entries with general transcription: {with_transcription}")
        print(f"Entries with subtitles/captions: {with_subtitles}")
        
        if with_whisper == 0 and len(data) > 0:
            print("\n❌ NO WHISPER TRANSCRIPTIONS FOUND IN RESULTS")
            print("   This confirms the transcription pipeline is failing")
            print("   Check worker logs for specific failure reasons")
        elif with_whisper > 0:
            print(f"\n✅ {with_whisper} successful Whisper transcriptions found")
            print(f"   Success rate: {(with_whisper/len(data)*100):.1f}%")
    
    except Exception as e:
        print(f"❌ Error reading master2.json: {e}")


if __name__ == "__main__":
    print("🔍 MULTIPROCESSING TRANSCRIPTION LOG ANALYZER")
    print("=" * 60)
    
    analyze_worker_logs()
    check_master_json_transcriptions()