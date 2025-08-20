- we had a lot of stuff in this codebase and it was mostly clutter, I am trying to rebuild the system to match the diagram.png image contained here [Image #1], the pipeline will be as follows

firefox extension -> urls.txt -> robust_master_downloader (collector.py) -> master2.json -> clean data -> get insights and train ML model

- the goal is to move everything out of keep/ to a permanent project layout, a system that is simply dockerized so this system can be portable. The purpose of this system should be able to run nearly everything automatically, with the only input being the urls from the users extension. The output being the updated snoo model, and the data and insights that come from it

the ideal layout:

extension/
    (contains the firefox_extension/ stuff)
model/
    api.py
    start_api.sh
    models/
        snoo.pkl
data/
    urls.txt
    master2.json
scripts/
    collector.py
    train_ml.py
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

as we develop this out, ensure that the changes are respecting this, it should remain very clean throughout

## TESTING REQUIREMENTS

**IMPORTANT**: Whenever you modify `robust_master_downloader.py`, you MUST:

1. **Run the test script** immediately after making changes:
   ```bash
   cd tests
   python test_robust_downloader.py
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

**Never consider robust_master_downloader.py changes complete until the test passes.**

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

use the codebase-structure-analyzer when analyzing large files to get quick insights of codebase **USE THIS AGENT VERY FREQUENTLY**