# TikTok Scraper - Clean Modular Architecture

## Project Overview
**Pipeline**: `firefox extension → urls.txt → collector.py → master2.json → clean data → ML model`

**Goal**: Dockerized portable system running automatically with URL input from extension, outputting trained model and insights.

## Project Structure
```
extension/        # Firefox extension
ml/              # ML training and API
data/            # urls.txt, master2.json
src/             # Modular components
dashboard/       # Frontend
tests/           # Testing framework
collector.py     # Main orchestrator
config.toml      # Configuration
```

## Testing Requirements

**CRITICAL**: After ANY changes to `collector.py` or `src/` modules:

```bash
cd tests
python test_robust_downloader.py
```

Test report validates:
- ✅ Valid JSON output (no missing commas)
- ✅ Duplicate detection working
- ✅ All expected fields present
- ✅ Clean exit (code 0)

**Never consider changes complete until tests pass.**

## Architecture Overview

### Modular System (73% code reduction: 3,200 → 1,140 lines)
- **collector.py** (~524 lines) - Main orchestrator
  - `RobustTikTokProcessor`: Single URL processing 
  - `MultiprocessCoordinator`: Parallel processing
- **src/** - Clean separation of concerns:
  - `video_extractor.py` - yt-dlp downloads & metadata
  - `comment_extractor.py` - TikTok API with MS_TOKEN
  - `transcript_extractor.py` - Whisper AI transcription
  - `data_manager.py` - JSON streaming & duplicate detection
  - `url_processor.py` - URL validation & ID extraction
  - `resource_manager.py` - Memory/process cleanup
  - `device_manager.py` - GPU/CPU detection
  - `models.py` - Data structures

### Processing Pipeline
```
URLs → Filter Duplicates → Process → {
    Video Download + Metadata
    → Whisper Transcription
    → Comment Extraction
} → Flatten Data → Save to master2.json → Cleanup
```

### Key Features
- **Robust Data Handling**: File locking, streaming, duplicate detection
- **Scalable Processing**: Single/multi-process modes
- **Resource Management**: Automatic cleanup between operations
- **Cross-platform**: Windows/macOS/Linux support
- **Error Recovery**: Graceful degradation, retry logic

### What System Extracts
1. **Video metadata** (likes, comments, shares, duration, timestamps)
2. **Transcripts** (Whisper AI)
3. **Comments** (with nested replies)
4. **Flattened JSON** output in master2.json

## Configuration

### CLI Arguments
- `--from-file` / `--url` - Input source
- `--whisper` / `--force-cpu` - Transcription settings
- `--ms-token` / `--max-comments` - Comment extraction
- `--workers` / `--batch-size` - Processing control
- `--json-output` - Output file

### config.toml Sections
```toml
[tiktok]      # ms_token
[download]    # quality, whisper settings
[processing]  # batch_size, delay, workers
[output]      # json_output file
```

## Development Guidelines
- Use `codebase-structure-analyzer` agent frequently for large file analysis
- Maintain clean modular separation
- Follow existing patterns and conventions
- Run tests after every change
- See `/Users/ethan/tiktok_scraper-1/tiktok_data_collection_uml_analysis.md` for class structure

**NOTE** comment extraction has been patched indefinitely and there is nothing we can do as of 8/20/2025 to fix it 