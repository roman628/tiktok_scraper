- NEVER write fallbacks
- Design personal diagnostic tools to comprehensively understand system mechanics:
  * Create step-by-step tracing mechanisms
  * Implement verbose logging for each component
  * Build interactive debug interfaces
  * Develop recursive error analysis tools
  * Construct dependency mapping visualizations

# TikTok Scraper Commands

## Main Download Command
```bash
./robust_master_downloader.py --from-file urls.txt --mp3 --batch-size 10 --delay 2 --max-comments 10 --whisper
```

## Maintenance Scripts
```bash
# Count entries in master2.json
./count_master.py

# Fix corrupted JSON (creates automatic backup)
./fix_json.py master2.json

# Remove duplicate URLs (creates automatic backup)
./remove_duplicates.py master2.json

# Remove entries with no transcription (creates automatic backup)
./clean_no_transcription.py --dry-run  # Preview what would be removed
./clean_no_transcription.py --force master2.json  # Remove without confirmation
```

## Notes
- Master database: `master2.json` (currently 959 entries)
- Duplicate checking happens automatically during initialization
- Ctrl+C works properly (signal handler disabled in tiktok_scraper.py)
- Memory management: Aggressive garbage collection enabled