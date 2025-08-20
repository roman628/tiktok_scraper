- we had a lot of stuff in this codebase and it was mostly clutter, I am trying to rebuild the system to match the diagram.png image contained here [Image #1], the pipeline will be as follows

firefox extension -> urls.txt -> collector.py -> master2.json -> clean data -> get insights and train ML model

- the goal is to move everything out of keep/ to a permanent project layout, a system that is simply dockerized so this system can be portable. The purpose of this system should be able to run nearly everything automatically, with the only input being the urls from the users extension. The output being the updated snoo model, and the data and insights that come from it

the ideal layout:

extension/
    (contains the firefox_extension/ stuff)
ml/
    api.py
    train_ml.py
    start_api.sh
    models/
        snoo.pkl
data/
    urls.txt
    master2.json
src/
    video_extractor.py
    comment_extractor.py
    transcript_extractor.py
    data_manager.py (includes fix_json functionality)
    url_processor.py
    resource_manager.py
    models.py
dashboard/
    frontend stuff for the dashboard
tests/
    (testing stuff)
docker-compose
docker
requirements.txt
README.md
diagram.png
.gitignore
collector.py

as we develop this out, ensure that the changes are respecting this, it should remain very clean throughout

## TESTING REQUIREMENTS

**IMPORTANT**: Whenever you modify `collector.py` or its src/ modules, you MUST:

1. **Run the test script** immediately after making changes:
   ```bash
   cd tests
   python test_robust_downloader.py
   
   # To test a different script (e.g., when developing the optimized collector.py):
   python test_robust_downloader.py --with ../collector.py
   
   # The --with flag allows testing any script with the same argument interface
   python test_robust_downloader.py --with ../src/collector.py
   ```

2. **Read and analyze the test report** at `test_report.json` to verify:
   - JSON format is valid (no missing commas between entries)
   - Duplicate detection is working (duplicates should be skipped)
   - All expected fields are present in the output
   - The process completes without errors (exit code 0)
   - Expected values match for the test video

3. **Check the test summary** for these critical indicators:
   - ✅ Valid JSON output
   - ✅ Correct number of unique entries (no duplicates)
   - ✅ No missing method errors
   - ✅ Process exits cleanly

4. **Review specific failures** in the report:
   - JSON format errors (e.g., missing commas at specific line numbers)
   - Duplicate entries that weren't skipped
   - Missing attributes or methods
   - Any unexpected errors in logs

The test uses `test_urls.txt` which contains both unique and duplicate URLs to validate duplicate detection. The test framework will automatically backup existing files and generate a comprehensive report showing exactly what's working and what's failing.

**Test Framework Features:**
- **--with flag**: Test different scripts without modifying the test framework (e.g., `--with ../collector.py`)
- Validates the same argument interface across all collector implementations
- Allows parallel development of optimized versions while keeping the original working

**Never consider script changes complete until the test passes.**

## Collector.py and Modular Architecture Overview

The data collection system has been successfully refactored from a monolithic 1,977-line script into a clean, modular architecture with the following components:

### Main Orchestrator:
- **collector.py** (~524 lines) - Main orchestrator that coordinates the entire pipeline
  - `RobustTikTokProcessor` class: Single URL processing with all extraction capabilities
  - `MultiprocessCoordinator` class: Manages parallel processing across multiple workers
  - Handles MS_TOKEN validation, duplicate detection, and graceful shutdown

### Modular Components in src/:
1. **video_extractor.py** - Handles video downloading and metadata extraction via yt-dlp
2. **comment_extractor.py** - Manages TikTok API comment extraction with token handling
3. **transcript_extractor.py** - Whisper AI transcription processing
4. **data_manager.py** - Consolidated JSON operations (streaming, validation, duplicate detection)
5. **url_processor.py** - Unified URL validation and video ID extraction
6. **resource_manager.py** - Memory and process cleanup utilities
7. **models.py** - Clean data classes (VideoData, Comment, ProcessingState)

### What the System Extracts:
1. Video metadata (likes, comment count, share count, description, title, duration, post time)
2. Video transcripts (via Whisper AI)
3. Video comments (with nested replies)
4. All data flattened into clean JSON structure in master2.json

### Key Architectural Improvements:
- **73% code reduction**: From ~3,200 lines to ~1,140 lines total
- **Clean separation**: Each module has a single, well-defined responsibility
- **Scalable processing**: Both single-process and multi-process execution modes
- **Robust data handling**: File locking, streaming operations, duplicate detection
- **Resource management**: Automatic cleanup between operations

### Processing Flow:
```
URLs → Filter Duplicates → Process (Single/Multi) → {
    Video Download (VideoExtractor)
    → Metadata Extraction
    → Whisper Transcription (optional)
    → Comment Extraction (if MS_TOKEN)
} → Flatten Data → Save to master2.json → Cleanup
```

### Key Requirements Maintained:
- Appends data to master2.json after each successful fetch
- Implements memory/resource cleanup between operations
- Supports multi-worker processing for scalable performance
- Maintains continuous operation stability
- Cross-platform file locking for data integrity

use the codebase-structure-analyzer when analyzing large files to get quick insights of codebase **USE THIS AGENT VERY FREQUENTLY**

more about how the class structure should be designed can be found here: /Users/ethan/tiktok_scraper-1/tiktok_data_collection_uml_analysis.md

