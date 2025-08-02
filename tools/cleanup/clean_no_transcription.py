#!/usr/bin/env python3
"""
Remove entries from master2.json that have no subtitle/transcription
"""

import json
import os
import sys
from datetime import datetime

def has_transcription(entry):
    """Check if entry has any form of transcription or subtitle"""
    if not isinstance(entry, dict):
        return False
    
    # Check for transcription field
    if entry.get('transcription') and entry['transcription'].strip():
        return True
    
    # Check for subtitle field
    if entry.get('subtitle') and entry['subtitle'].strip():
        return True
    
    # Check for subtitles field (plural)
    if entry.get('subtitles') and entry['subtitles'].strip():
        return True
    
    # Check for whisper_transcription field
    if entry.get('whisper_transcription') and entry['whisper_transcription'].strip():
        return True
    
    # Check for any field containing 'transcript'
    for key, value in entry.items():
        if 'transcript' in key.lower() and value and str(value).strip():
            return True
    
    return False

def clean_no_transcription(input_file, output_file=None, dry_run=False, force=False):
    """Remove entries without transcription from JSON file"""
    
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    print(f"📖 Reading {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print("💡 Please run fix_json.py first to repair the JSON file")
        return False
    
    if not isinstance(data, list):
        print(f"❌ JSON file is not an array")
        return False
    
    print(f"📊 Total entries: {len(data)}")
    
    # Separate entries with and without transcription
    entries_with_transcription = []
    entries_without_transcription = []
    entries_without_url = []
    
    for entry in data:
        if isinstance(entry, dict):
            if 'url' not in entry:
                entries_without_url.append(entry)
            elif has_transcription(entry):
                entries_with_transcription.append(entry)
            else:
                entries_without_transcription.append(entry)
        else:
            # Non-dict entries
            entries_without_url.append(entry)
    
    print(f"\n📊 Analysis:")
    print(f"   ✅ Entries with transcription: {len(entries_with_transcription)}")
    print(f"   ❌ Entries without transcription: {len(entries_without_transcription)}")
    print(f"   ⚠️  Entries without URL: {len(entries_without_url)}")
    
    if dry_run:
        print(f"\n🔍 Dry run mode - showing what would be removed:")
        print(f"\n📝 First 10 entries that would be removed:")
        for i, entry in enumerate(entries_without_transcription[:10], 1):
            url = entry.get('url', 'No URL')
            title = entry.get('title', 'No title')[:50] + '...' if entry.get('title') and len(entry.get('title', '')) > 50 else entry.get('title', 'No title')
            print(f"   {i}. {url}")
            print(f"      Title: {title}")
        
        if len(entries_without_transcription) > 10:
            print(f"   ... and {len(entries_without_transcription) - 10} more")
        
        return True
    
    # Ask for confirmation (skip if forced or non-interactive)
    if entries_without_transcription and not force:
        print(f"\n⚠️  This will remove {len(entries_without_transcription)} entries without transcription.")
        try:
            response = input("Continue? (y/n): ").strip().lower()
            if response not in ['y', 'yes']:
                print("❌ Operation cancelled")
                return False
        except EOFError:
            print("📋 Running in non-interactive mode, proceeding...")
    
    # Keep only entries with transcription (and entries without URL)
    cleaned_data = entries_with_transcription + entries_without_url
    
    # Sort by URL for consistency
    cleaned_data.sort(key=lambda x: x.get('url', ''))
    
    # Save output
    if output_file is None:
        # Create backup first
        backup_file = f"{input_file}.before_clean_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(input_file, backup_file)
        output_file = input_file
        print(f"\n💾 Created backup: {backup_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved cleaned data to: {output_file}")
    print(f"📊 Final entries: {len(cleaned_data)}")
    print(f"🗑️  Removed: {len(entries_without_transcription)} entries")
    
    # Show some stats about what we kept
    if entries_with_transcription:
        total_chars = sum(len(entry.get('transcription', '') or 
                             entry.get('subtitle', '') or 
                             entry.get('subtitles', '') or 
                             entry.get('whisper_transcription', '')) 
                         for entry in entries_with_transcription)
        avg_length = total_chars // len(entries_with_transcription)
        print(f"\n📊 Transcription stats:")
        print(f"   Average transcription length: {avg_length} characters")
    
    return True

def main():
    if len(sys.argv) > 1:
        dry_run = False
        force = False
        args = sys.argv[1:]
        
        # Parse flags
        if '--dry-run' in args:
            dry_run = True
            args.remove('--dry-run')
        if '--force' in args:
            force = True
            args.remove('--force')
        
        input_file = args[0] if args else "master2.json"
        output_file = args[1] if len(args) > 1 else None
        
        clean_no_transcription(input_file, output_file, dry_run=dry_run, force=force)
    else:
        print("Usage:")
        print("  ./clean_no_transcription.py [--dry-run] [--force] [input_file] [output_file]")
        print("")
        print("Options:")
        print("  --dry-run    Show what would be removed without actually removing")
        print("  --force      Skip confirmation prompt")
        print("")
        print("Examples:")
        print("  ./clean_no_transcription.py --dry-run")
        print("  ./clean_no_transcription.py --force master2.json")
        print("  ./clean_no_transcription.py master2.json cleaned.json")

if __name__ == "__main__":
    main()