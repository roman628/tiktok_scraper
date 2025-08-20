- we had a lot of stuff in this codebase and it was mostly clutter, I am trying to rebuild the system to match the diagram.png image contained here [Image #1], the pipeline will be as follows

firefox extension -> urls.txt -> robust_master_downloader (collector.py) -> master2.json -> clean data -> get insights and train ML model

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

**IMPORTANT**: Whenever you modify `robust_master_downloader.py` or develop new collector scripts, you MUST:

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

## robust_master_downloader.py (collector.py) Overview

The data collection system consists of four interconnected scripts that orchestrate the population of the database:
1. **robust_master_downloader.py** - Main orchestrator that coordinates the entire pipeline
2. **tiktok_scraper.py** - Handles video downloading, metadata extraction, and Whisper transcription
3. **comment_extractor.py** - Manages comment extraction with API token handling
4. **memory_efficient_append.py** - Provides streaming JSON operations for large datasets

Together, these scripts extract:
1. Video metadata (likes, comment count, share count, description, title, duration, post time)
2. Video transcripts (via Whisper AI)
3. Video comments (with nested replies)

Key requirements:
- Appends data to master2.json after each successful fetch
- Implements memory/resource cleanup between operations to prevent overload
- Supports multi-worker processing for scalable performance
- Must maintain continuous operation stability

### Cleanup Strategy
These four scripts are currently functional but need refactoring to be more efficient and less bloated:
1. Consolidate duplicate functionality across the scripts
2. Remove workarounds and unnecessary code bloat
3. Design clear class structure with separation of concerns
4. Create comprehensive testing script to validate all functions
5. Optimize for fewer lines while maintaining readability
6. Eliminate redundant JSON handling and URL processing code

## Refactoring Plan: 4 Scripts → 8 Focused Classes

### Current State (Bloated):
1. `robust_master_downloader.py` - **1,977 lines** (doing everything!)
2. `tiktok_scraper.py` - ~800+ lines
3. `comment_extractor.py` - ~300 lines  
4. `memory_efficient_append.py` - ~100 lines
**Total: ~3,200+ lines of messy, duplicated code**

### Target State (Clean):
```python
1. collector.py (~200 lines) - Main orchestrator from robust_master_downloader.py
2. video_extractor.py (~250 lines) - Core video logic 
3. comment_extractor.py (~150 lines) - Comment extraction
4. transcript_extractor.py (~120 lines) - Whisper transcription
5. data_manager.py (~180 lines) - All JSON operations consolidated (includes fix_json, memory_efficient_append functionality)
6. url_processor.py (~80 lines) - URL handling (3 implementations → 1)
7. resource_manager.py (~100 lines) - Memory/process cleanup
8. models.py (~60 lines) - Clean data classes
```
**Target: ~1,140 lines (64% reduction!)**

### Key Consolidations:
- **JSON operations**: 4 different implementations → 1 `DataManager`
  - fix_json.py (JSON repair/recovery)
  - memory_efficient_append.py (streaming operations)
  - JSON validation and duplicate detection
  - All read/write operations
- **URL processing**: 3 scattered implementations → 1 `URLProcessor`
- **Resource cleanup**: Duplicated everywhere → 1 `ResourceManager`
- **Error handling**: Scattered retry logic → Unified approach

The robust_master_downloader.py is currently handling video downloading, comment extraction, transcription, JSON management, URL processing, resource cleanup, worker management, error handling, and progress tracking all in one massive 1,977-line file. This will be split into focused, testable components.

use the codebase-structure-analyzer when analyzing large files to get quick insights of codebase **USE THIS AGENT VERY FREQUENTLY**

more about how the class structure should be designed can be found here: /Users/ethan/tiktok_scraper-1/tiktok_data_collection_uml_analysis.md

