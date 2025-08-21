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
- **collector.py** (~600 lines) - Main orchestrator
  - `RobustTikTokProcessor`: Unified processor for all worker modes
  - `process_tiktok_url`: Core URL processing function with consistent flattened output
- **src/** - Clean separation of concerns (11 modules):
  - `video_extractor.py` - yt-dlp downloads & metadata extraction
  - `comment_extractor.py` - TikTok API with MS_TOKEN (currently non-functional)
  - `transcript_extractor.py` - Whisper AI transcription with GPU/CPU support
  - `data_manager.py` - JSON streaming, file locking & duplicate detection
  - `url_processor.py` - URL validation, normalization & ID extraction
  - `resource_manager.py` - Memory monitoring & process cleanup
  - `device_manager.py` - CUDA/MPS/CPU detection & configuration
  - `models.py` - Type-safe data structures (Comment, VideoData, ProcessingState)
  - `display_manager.py` - Rich terminal UI with responsive grid layout
  - `worker_progress.py` - Stage-based progress reporting (6 weighted stages)
  - `shutdown_manager.py` - Centralized graceful shutdown handling

### Processing Pipeline
```
URLs → Filter Duplicates → Process → {
    Video Download + Metadata
    → Whisper Transcription
    → Comment Extraction
} → Flatten Data → Save to master2.json → Cleanup
```

### Key Features
- **Robust Data Handling**: File locking, streaming JSON, duplicate detection, atomic writes
- **Unified Processing**: Always uses worker processes (1 to N) with consistent output
- **Scalable Processing**: Seamless scaling from 1 to multiple workers
- **Resource Management**: Memory monitoring, automatic cleanup, signal handling
- **Cross-platform**: Windows/macOS/Linux with platform-specific optimizations
- **Error Recovery**: Graceful degradation, retry logic, JSON repair
- **Rich Terminal UI**: Real-time progress tracking with responsive grid layout
- **Stage-based Progress**: 6-stage weighted progress reporting per URL
- **GPU Acceleration**: CUDA & MPS support with automatic fallback to CPU

### What System Extracts
1. **Video metadata** (views, likes, shares, duration, timestamps, author info)
2. **Transcripts** (Whisper AI with GPU acceleration)
3. **Comments** (with nested replies - currently unavailable)
4. **Flattened JSON** output in master2.json with validation

## Configuration

### CLI Arguments
- `--from-file` / `--url` - Input source
- `--whisper` / `--force-cpu` - Transcription settings
- `--ms-token` / `--max-comments` - Comment extraction
- `--workers` / `--batch-size` - Processing control
- `--json-output` - Output file
- `--display-mode` - Display mode (rich/simple/auto)
- `--raw-log` - Save raw output to timestamped log file

### config.toml Sections
```toml
[tiktok]      # ms_token
[download]    # quality, whisper settings
[processing]  # batch_size, delay, workers
[output]      # json_output file
[display]     # mode, raw_log, refresh_rate, console_lines
```

## Enhanced Display System

### Rich Terminal UI
The system now includes a sophisticated terminal display with:
- **Responsive Grid Layout**: Automatically adapts to terminal width
  - Horizontal layout when space permits
  - Wraps to multiple rows when needed
- **Per-Worker Progress**: Each worker shows:
  - Current URL being processed
  - Progress bar (0-100%) for current URL
  - Stage indicator (downloading, transcribing, etc.)
  - Console output with success/error indicators
  - Counter showing (completed/total) in header
- **Visual Feedback**:
  - Grey borders for idle workers
  - Blue borders for active processing
  - Green flash animation (3x) when URL completes
  - Red borders for errors

### Progress Stages
Each URL progresses through weighted stages:
1. **Validating** (0-5%): URL validation
2. **Downloading** (5-35%): Video/audio download
3. **Metadata** (35-45%): Metadata extraction
4. **Transcribing** (45-85%): Whisper transcription (if enabled)
5. **Comments** (85-95%): Comment extraction (if MS_TOKEN available)
6. **Saving** (95-100%): Save to master2.json

### Display Modes
- **Rich Mode**: Full visual display with panels and progress bars
- **Simple Mode**: Basic line-by-line output for non-TTY environments
- **Auto Mode**: Automatically detects TTY and chooses appropriate mode

### Testing Display
```bash
# Test with simulated workers
python test_display_visual.py --workers 4 --urls 20

# Quick test
python quick_display_test.py -w 4 -u 5
```

## Development Guidelines
- Use `codebase-structure-analyzer` agent frequently for large file analysis
- Maintain clean modular separation
- Follow existing patterns and conventions
- Run tests after every change
- See `/Users/ethan/tiktok_scraper-1/tiktok_data_collection_uml_analysis.md` for class structure

**NOTE** comment extraction has been patched indefinitely and there is nothing we can do as of 8/20/2025 to fix it 