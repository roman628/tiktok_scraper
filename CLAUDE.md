# TikTok Scraper - Clean Modular Architecture

## Project Overview
**Pipeline**: `firefox extension → urls.txt → collector.py → PostgreSQL/master2.json → clean data → ML model`

**Goal**: Dockerized portable system running automatically with URL input from extension, outputting trained model and insights.

## Project Structure
```
extension/        # Firefox extension
ml/              # ML training and API
data/            # urls.txt, master2.json (legacy)
database/        # PostgreSQL schema and migration tools
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
- **src/** - Clean separation of concerns (12 modules):
  - `video_extractor.py` - yt-dlp downloads & metadata extraction
  - `comment_extractor.py` - TikTok API with MS_TOKEN (currently non-functional)
  - `transcript_extractor.py` - Whisper AI transcription with GPU/CPU support
  - `database_manager.py` - PostgreSQL operations with connection pooling & caching
  - `data_manager.py` - JSON streaming, file locking & duplicate detection (legacy)
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
} → Flatten Data → Save to PostgreSQL/master2.json → Cleanup
```

### Key Features
- **PostgreSQL Database**: Primary storage with ACID transactions, indexed queries, concurrent writes
- **Robust Data Handling**: File locking, streaming JSON, duplicate detection, atomic writes
- **Unified Processing**: Always uses worker processes (1 to N) with consistent output
- **Scalable Processing**: Seamless scaling from 1 to multiple workers
- **Resource Management**: Memory monitoring, automatic cleanup, signal handling
- **Cross-platform**: Windows/macOS/Linux with platform-specific optimizations
- **Error Recovery**: Graceful degradation, retry logic, connection pooling
- **Rich Terminal UI**: Real-time progress tracking with responsive grid layout
- **Stage-based Progress**: 6-stage weighted progress reporting per URL
- **GPU Acceleration**: CUDA & MPS support with automatic fallback to CPU

### What System Extracts
1. **Video metadata** (views, likes, shares, duration, timestamps, author info)
2. **Transcripts** (Whisper AI with GPU acceleration)
3. **Comments** (with nested replies - currently unavailable)
4. **PostgreSQL storage** with normalized schema (primary storage)

## Configuration

### CLI Arguments
- `--from-file` / `--url` - Input source
- `--whisper` / `--force-cpu` - Transcription settings
- `--ms-token` / `--max-comments` - Comment extraction
- `--workers` / `--batch-size` - Processing control
- `--display-mode` - Display mode (rich/simple/auto)
- `--raw-log` - Save raw output to timestamped log file

### config.toml Sections
```toml
[tiktok]      # ms_token
[download]    # quality, whisper settings
[processing]  # batch_size, delay, workers
[display]     # mode, raw_log, refresh_rate, console_lines
[database]    # PostgreSQL connection settings (always used)
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
6. **Saving** (95-100%): Save to PostgreSQL database

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

## Database System (PostgreSQL)

### Overview
The system now uses PostgreSQL as primary storage (enabled by default in config.toml):
- **3,916 videos** migrated from master2.json
- **Normalized schema** with 6 tables (videos, comments, transcriptions, hashtags, etc.)
- **Indexed queries** for O(1) duplicate detection vs O(n) JSON scanning
- **Concurrent writes** from multiple workers without file locking
- **ACID transactions** ensure data integrity

### Database Schema

#### videos table
Primary table storing video metadata:
- `id` (SERIAL PRIMARY KEY) - Auto-incrementing integer ID
- `video_id` (VARCHAR(100)) - TikTok video ID string (e.g., "7532447162072894775")
- `url` (TEXT) - Full TikTok URL
- `title` (TEXT) - Video title
- `description` (TEXT) - Video description
- `uploader` (VARCHAR(255)) - Username
- `uploader_id` (VARCHAR(255)) - User ID
- `uploader_url` (TEXT) - User profile URL
- `view_count` (BIGINT) - View count
- `like_count` (BIGINT) - Like count
- `comment_count` (BIGINT) - Comment count
- `repost_count` (BIGINT) - Repost count
- `save_count` (BIGINT) - Save count
- `share_count` (BIGINT) - Share count
- `upload_date` (DATE) - Original upload date
- `timestamp` (BIGINT) - Unix timestamp
- `duration` (INTEGER) - Duration in seconds
- `width` (INTEGER) - Video width
- `height` (INTEGER) - Video height
- `fps` (INTEGER) - Frames per second
- `filesize` (BIGINT) - File size in bytes
- `format` (TEXT) - Video format string
- `downloaded_at` (TIMESTAMP) - When we downloaded it
- `downloaded_with` (TEXT) - Scraper version info
- `platform` (VARCHAR(50)) - OS platform
- `created_at` (TIMESTAMP) - Database insertion time

#### transcriptions table
Stores Whisper AI transcriptions:
- `id` (SERIAL PRIMARY KEY) - Auto-incrementing ID
- `video_id` (INTEGER REFERENCES videos(id)) - **Links to videos.id NOT videos.video_id!**
- `whisper_transcription` (TEXT) - Full transcription text
- `transcription_timestamp` (TIMESTAMP) - When transcribed
- `model_used` (VARCHAR(50)) - Whisper model name

#### comments table
Stores video comments:
- `id` (SERIAL PRIMARY KEY) - Auto-incrementing ID
- `video_id` (INTEGER REFERENCES videos(id)) - **Links to videos.id NOT videos.video_id!**
- `comment_id` (VARCHAR(100)) - TikTok comment ID
- `username` (VARCHAR(255)) - Commenter username
- `display_name` (VARCHAR(255)) - Display name
- `comment_text` (TEXT) - Comment content
- `like_count` (INTEGER) - Comment likes
- `timestamp` (TIMESTAMP) - Comment timestamp
- `is_top_comment` (BOOLEAN) - Top comment flag
- `extracted_at` (TIMESTAMP) - When extracted

#### hashtags table
Normalized hashtag storage:
- `id` (SERIAL PRIMARY KEY) - Auto-incrementing ID
- `tag` (VARCHAR(255) UNIQUE) - Hashtag text

#### video_hashtags table
Many-to-many relationship:
- `video_id` (INTEGER REFERENCES videos(id)) - **Links to videos.id**
- `hashtag_id` (INTEGER REFERENCES hashtags(id))

#### processing_status table
Tracks processing status:
- `video_id` (INTEGER REFERENCES videos(id)) - **Links to videos.id**
- `comments_extracted` (BOOLEAN) - Comments extraction flag
- `comments_extracted_at` (TIMESTAMP) - When comments extracted
- `transcription_completed` (BOOLEAN) - Transcription flag
- `transcription_completed_at` (TIMESTAMP) - When transcribed
- `created_at` (TIMESTAMP) - Creation time
- `updated_at` (TIMESTAMP) - Last update

#### queued_urls table
URL processing queue:
- `id` (SERIAL PRIMARY KEY) - Auto-incrementing ID
- `url` (TEXT UNIQUE) - TikTok URL to process
- `status` (VARCHAR(20)) - 'pending', 'processing', 'completed', 'failed'
- `added_at` (TIMESTAMP) - When added to queue
- `processed_at` (TIMESTAMP) - When processed
- `error_message` (TEXT) - Error details if failed
- `retry_count` (INTEGER DEFAULT 0) - Retry attempts

### Important JOIN Relationships

**CRITICAL**: When joining tables, remember that foreign keys reference `videos.id` (INTEGER), not `videos.video_id` (VARCHAR):

```sql
-- CORRECT: Join on videos.id
SELECT v.video_id, v.url, t.whisper_transcription
FROM videos v
LEFT JOIN transcriptions t ON v.id = t.video_id

-- WRONG: Don't join on videos.video_id
-- This won't work: ON v.video_id = t.video_id
```

### Database Operations
```bash
# Check database statistics
psql -U $USER -d tiktok_scraper -c "SELECT * FROM database_statistics;"

# Export to JSON if needed
python -c "from src.database_manager import DatabaseManager; 
db = DatabaseManager(user='postgres', database='tiktok_scraper'); 
db.export_to_json('export.json')"

# Migration from JSON
python database/migrate_json_to_postgres.py data/master2.json
```

### Configuration
```toml
[database]
enabled = true    # Use PostgreSQL (recommended)
host = "localhost"
database = "tiktok_scraper"
user = "postgres"
```

## Development Guidelines
- Use `codebase-structure-analyzer` agent frequently for large file analysis
- Maintain clean modular separation
- Follow existing patterns and conventions
- Run tests after every change
- See `/Users/ethan/tiktok_scraper-1/tiktok_data_collection_uml_analysis.md` for class structure
- See `/Users/ethan/tiktok_scraper-1/database/README.md` for database setup and operations

## Important Implementation Notes

### Database-Only Storage (as of 8/21/2025)
The system has been fully migrated to PostgreSQL as the primary storage mechanism. All legacy JSON output code has been removed:
- The `--json-output` CLI flag no longer exists
- The `[output]` section in config.toml has been removed
- `DatabaseOrJsonManager` now always uses PostgreSQL (no fallback to JSON)
- The `master2.json` file is no longer created or updated
- When testing, use `--force-redownload` to bypass duplicate detection
- Test scripts export from database using `DatabaseManager.export_to_json()` for validation
- Default database user is 'postgres'
- The system will error if database connection fails - there's no JSON fallback

**NOTE** comment extraction has been patched indefinitely and there is nothing we can do as of 8/20/2025 to fix it 
- any new additions to the config.toml should be added to the config.template.toml