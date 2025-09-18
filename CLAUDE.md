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

## Critical Environment and Configuration Requirements

## Critical Configuration Requirements

**DATABASE USER CONFIGURATION - CRITICAL**: 
- **NEVER use 'root' as a default database user** - this has caused persistent connection issues
- All database connections MUST use the configured user from `config.toml`
- Default database user should be 'postgres' to align with PostgreSQL standards
- The `[database]` section in config.toml must specify the correct user:
  ```toml
  [database]
  user = "your_actual_postgres_user"  # Often 'postgres' or your system username
  ```
- This applies to ALL files that connect to the database, especially:
  - `utils/worker_manager.py`
  - `src/database_manager.py`
  - `collector.py`

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
- **src/** - Core processing modules (data extraction, database):
  - `video_extractor.py` - yt-dlp downloads & metadata extraction (including music/artist/timestamps)
  - `comment_extractor.py` - TikTok API with MS_TOKEN (currently non-functional)
  - `transcript_extractor.py` - Whisper AI transcription with GPU/CPU support
  - `text_extractor.py` - OCR text extraction from video frames using EasyOCR (GPU/CPU)
  - `database_manager.py` - PostgreSQL operations with connection pooling & caching
  - `data_manager.py` - JSON streaming, file locking & duplicate detection (legacy)
  - `url_processor.py` - URL validation, normalization & ID extraction
  - `models.py` - Type-safe data structures (Comment, VideoData, ProcessingState)
  - `recalibrator.py` - Batch processing for adding new attributes to existing videos
- **utils/** - System utilities and resource management:
  - `resource_manager.py` - Memory monitoring, process cleanup, file/directory cleanup
  - `device_manager.py` - CUDA/MPS/CPU detection & configuration for all AI operations
  - `display_manager.py` - Rich terminal UI with responsive grid layout
  - `worker_progress.py` - Stage-based progress reporting (6 weighted stages)
  - `worker_manager.py` - Multi-worker orchestration and task distribution
  - `shutdown_manager.py` - Centralized graceful shutdown handling
  - `collector_registry.py` - Process tracking and management
  - `data_manager.py` - Legacy JSON data management (being phased out)

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

### Device Management System
The `DeviceManager` class (`utils/device_manager.py`) automatically handles all GPU/CPU detection and configuration system-wide. It detects CUDA (NVIDIA), MPS (Apple Silicon), and CPU availability, selecting the best available device without user configuration. The system uses this unified device manager for all AI operations (Whisper, CLIP, future models).

**Important**: Some AI features may not support CPU-only fallback due to computational requirements. When a feature requires GPU but none is available, the system will:
1. Display a clear warning in both Rich UI panels and standard console output
2. Log that the feature was skipped due to hardware limitations
3. Continue processing other features without stalling
4. Mark the feature as "skipped_no_gpu" in the database for potential future reprocessing

This ensures the pipeline never hangs on impossible operations while maintaining transparency about what was and wasn't processed.

### What System Extracts
1. **Video metadata** (views, likes, shares, duration, timestamps, author info)
   - **Music/Audio**: Track name and artist from TikTok sounds
   - **Precise timestamps**: Hour and minute of upload extracted from Unix timestamp
2. **Transcripts** (Whisper AI with GPU acceleration)
3. **On-screen text** (OCR extraction from first frame using EasyOCR)
4. **Hashtags** (Automatically extracted from titles/descriptions into normalized tables)
5. **Comments** (with nested replies - currently unavailable due to API restrictions)
6. **PostgreSQL storage** with normalized schema (primary storage)

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
[tiktok]           # ms_token
[download]         # quality, whisper settings
[processing]       # batch_size, delay, workers
[display]          # mode, raw_log, refresh_rate, console_lines
[data_collection]  # Enable/disable hashtags, OCR, transcription, etc.
[database]         # PostgreSQL connection settings (always used)
```

**Auto-Config Updates**: The collector automatically detects missing configuration settings by comparing `config.toml` with `assets/config.template.toml`. Any missing settings are added with default values and a warning is displayed, ensuring the system always has required configuration without manual intervention.

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

The processing pipeline is sequential per worker, with each stage completing before the next begins. This allows GPU memory to be cleared between GPU-intensive operations (like Whisper transcription and CLIP analysis). Each stage can be independently enabled/disabled via config.toml settings, and new analysis stages can be inserted into the pipeline without disrupting existing functionality.

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

**Important**: All database schema changes should be directly added to `database/schema.sql` to maintain a single source of truth for the database structure.

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

### Setup Script
The project includes an intelligent setup script (`setup.sh`) that automatically configures the entire environment with zero arguments required. It detects your OS (macOS/Linux), installs system dependencies (ffmpeg, PostgreSQL), creates a Python virtual environment, installs all Python packages with appropriate GPU support (CUDA/MPS/CPU), sets up the PostgreSQL database with the medallion architecture, and configures all project files. The script maintains state between runs, allowing it to resume if interrupted.

The `--migrate` flag is particularly important for database updates: running `./setup.sh --migrate` will apply any new schema changes from `database/schema.sql` to your existing database, create a timestamped backup before migration, run medallion architecture migrations, and update ML features in the gold layer. This makes it safe to update the database structure without losing data.

## Dashboard System

### Live Polling Mechanism
The dashboard (`dashboard/`) uses automatic polling to display real-time status updates:

#### Polling Architecture
- **Endpoint**: `/api/status/` - Returns combined status from multiple sources
- **Interval**: Every 3 seconds (configured in `dashboard.html`)
- **JavaScript Function**: `updateDashboard()` fetches and updates UI elements
- **Animation**: Pulse effect on changed values for visual feedback

#### Status Data Sources
1. **Collector Status**: 
   - Database table `collector_status`
   - Process checking via `pgrep`
   - Django model `CollectorRun`

2. **ML Training Status**:
   - Django model `MLTrainingRun` with status field
   - Signals from `train_ml.py` via `/api/ml/start/` and `/api/ml/end/`
   - Training runs independently - dashboard updates only if server is running

3. **URL Processing**:
   - `QueuedURL` model tracks pending/processing/completed/failed
   - Real-time counts update automatically

#### ML Training Integration
The ML training script (`ml/train_ml.py`) sends HTTP signals to the dashboard:
- **Start Signal**: POST to `/api/ml/start/` when training begins
- **End Signal**: POST to `/api/ml/end/` when training completes
- **Fault Tolerant**: Training continues even if server is down (signals fail silently)
- **Status Display**: Shows "Training" or "Idle" with green/grey indicator

#### Key Features
- **Non-blocking**: Polling doesn't interfere with operations
- **Responsive**: Updates within 3 seconds of state changes
- **Visual Feedback**: Pulse animations highlight changes
- **Graceful Degradation**: Works even if some services are unavailable

## Content Categorization System

### Overview
The project includes a sophisticated two-phase content categorization system that automatically identifies and assigns contextual categories to TikTok videos based on their transcript content. This system consists of two main components: `utils/categorize_videos.py` for category discovery and `src/identify_context.py` for category assignment. The system has successfully discovered 1,861 unique content categories and categorized 2,456 videos based purely on their transcript content.

### Phase 1: Category Discovery (`utils/categorize_videos.py`)
The category discovery tool leverages Google's Gemini 1.5 Flash API to analyze thousands of videos in batches and discover content categories. It processes videos in batches of approximately 200,000 tokens (staying under the free tier limit of 250K tokens/minute), using tiktoken for accurate token counting. The script truncates titles to 500 characters and transcripts to 500 words to fit within token limits while maximizing content analysis. It automatically discovers between 200-500 distinct categories per batch by analyzing the collective content patterns across all videos. Categories are saved incrementally after each successful batch to prevent data loss, with automatic deduplication handled at the database level through PostgreSQL's `ON CONFLICT DO NOTHING` clause. The system includes a 60-second delay between API calls for rate limiting on the free tier. Running this tool populated the database with 1,861 unique content categories ranging from broad genres like "storytime" and "tutorial" to specific niches like "family drama", "reddit stories", and "relationship advice". Usage is simple: `python utils/categorize_videos.py --api-key YOUR_KEY`.

### Phase 2: Context Identification (`src/identify_context.py`)
Once categories are discovered, the context identification system uses lightweight sentence transformers (BERT-based models like all-MiniLM-L6-v2) to efficiently assign categories to individual videos. This system runs entirely locally on GPU/MPS/CPU without any API costs, processing videos at ~200-500 videos per second on modern hardware. Critically, it uses ONLY the video transcripts for categorization, completely ignoring titles and descriptions to avoid bias - for example, a video titled "#fyp #viral" gets categorized as "saving money" based on its actual content about holiday savings, not the generic title. The system employs cosine similarity between video transcript embeddings and category embeddings to find the best matches, assigning up to 5 categories per video with confidence scores ranging from 0.0 to 1.0. Each category is expanded with contextual keywords for better matching accuracy - for example, "tutorial" categories are expanded with terms like "how to guide teaching learn instruction". The system processes videos in configurable batches (default 32) for optimal GPU utilization and saves results directly to the `video_categories` junction table with confidence scores and model attribution.

### Integration and Database Schema
The categorization system seamlessly integrates with the existing PostgreSQL database through two new tables: `categories` (storing unique category names) and `video_categories` (a junction table storing video-to-category relationships with confidence scores). After initial category discovery, all videos with transcripts can be categorized using `python src/identify_context.py`, with options for batch size (`--batch-size`), confidence threshold (`--threshold`), and processing limits (`--limit`). The system maintains proper foreign key relationships and indexes for fast querying. For pipeline integration, the identify_context functionality can be called directly after the transcription step in `collector.py`, ensuring every new video gets automatically categorized based on its content. The categorization adds minimal overhead to the pipeline while providing valuable content classification that can be used for ML training, content filtering, and trend analysis.

## Docker Deployment System

The project includes a comprehensive Docker setup for easy deployment and portability. The system uses a single Dockerfile based on `nvidia/cuda:12.1.0-runtime-ubuntu22.04` that supports both GPU and CPU environments - PyTorch automatically detects CUDA availability at runtime and falls back to CPU if no GPU is present. The image includes all dependencies (Python 3.11, ffmpeg, PostgreSQL client) and pre-downloads ML models during build. This unified approach ensures full GPU utilization for Whisper transcription, OCR, and ML training when NVIDIA hardware is available, while maintaining compatibility with CPU-only systems.

The `docker-compose.yml` orchestrates three main services: a PostgreSQL 15 database container with automatic schema initialization, a Django web service on port 8000 with auto-migration, and an optional collector service for batch processing. Configuration is handled through environment variables (`.env` file) and mounted volumes for `config.toml`, data persistence, and model storage. To deploy, simply run `docker-compose up -d postgres web` to start the main services, then access the dashboard at `http://localhost:8000`. The collector can be triggered via the web interface or run manually with `docker-compose run --rm collector`. This containerized approach ensures consistent environments across different machines while preserving the system's adaptive GPU/CPU detection capabilities.

## Development Guidelines
- Use `codebase-structure-analyzer` agent frequently for large file analysis
- Maintain clean modular separation
- Follow existing patterns and conventions
- Run tests after every change
- See `/Users/ethan/tiktok_scraper-1/tiktok_data_collection_uml_analysis.md` for class structure
- See `/Users/ethan/tiktok_scraper-1/database/README.md` for database setup and operations

## Python Dependencies Management
**CRITICAL**: ALL Python packages must be added to `requirements.txt` ONLY
- Never install packages individually via pip in setup scripts
- Never hardcode pip install commands outside of requirements.txt
- The setup.sh script should ONLY run: `pip install -r requirements.txt`
- When adding new dependencies, update requirements.txt first
- This ensures reproducible builds and consistent environments
- GPU-specific packages (torch with CUDA/MPS) should be handled via conditional logic reading from requirements.txt

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

### Future Video Attributes & Recalibration System
The system is designed to support adding new analysis capabilities to existing videos without re-downloading content. New attributes like visual analysis (CLIP, BLIP), audio features, or enhanced metadata are stored in separate normalized tables linked by video ID, similar to how transcriptions and comments are handled. This modular database design allows different AI models to contribute their own specialized insights without modifying the core videos table.

When new analysis capabilities are added, the `--recalibrate` flag (see `src/recalibrator.py`) allows batch processing of existing videos to add missing attributes. For example, `--recalibrate visual` would run CLIP analysis on all videos lacking visual embeddings, while `--recalibrate transcripts` re-processes videos needing transcription updates. The recalibrator automatically identifies which videos need processing, manages batch sizes for GPU memory constraints, and updates only the relevant analysis tables without touching existing data.

**NOTE** comment extraction has been patched indefinitely and there is nothing we can do as of 8/20/2025 to fix it 
- any new additions to the config.toml should be added to the config.template.toml

### Worker Architecture and Context Identification (as of 8/29/2025)

**CRITICAL**: The system uses two different worker implementations depending on how the collector is started:
1. **Direct execution** (`python collector.py`): Uses `worker_process_single` from `collector.py`
2. **Normal execution** (via Django or direct): Uses `enhanced_worker_process` from `utils/worker_manager.py`

The `enhanced_worker_process` is the primary worker implementation that includes:
- Context identification initialization and cleanup
- Heartbeat monitoring and status reporting  
- Database-based URL queue management
- Proper resource cleanup in finally blocks

**Context Identification Integration**:
- Context identification requires the virtual environment to be active (for psycopg2 and sentence-transformers)
- The context identifier is initialized per worker with lazy loading to defer model loading
- It only runs when a transcript is available (requires `transcript=True`)
- Uses the `src/identify_context.py` module with BERT-based sentence transformers
- Saves categories to the `video_categories` junction table with confidence scores

**Worker Lifecycle and Completion Detection**:
- Workers run in a continuous loop checking for URLs from the queue
- The `detect_completion` method in `WorkerManager` checks database for pending/processing URLs
- **IMPORTANT**: Do NOT add sentinel values (None) to the URL queue prematurely - this causes workers to exit before completing transcription
- Workers send heartbeat signals with status ('idle', 'active', 'starting', 'completed')
- Completion is detected when: no pending URLs exist AND all workers are idle or completed
- The shutdown_event is set only after all processing is confirmed complete

**Common Issues and Solutions**:
1. **"Context identifier not initialized"**: Ensure virtual environment is active and imports succeed
2. **Transcription interrupted**: Check that sentinel values aren't added to queue too early
3. **Workers exit prematurely**: Verify `detect_completion` logic checks for pending URLs in database
4. **Context identification skipped**: Ensure transcript is available and not empty
- under no circumstances should we ever do a 'CPU only' approach

## Docker Service Architecture (Simplified 2025-09-12)

### Overview
System uses **separate Docker containers** for each service, avoiding subprocess complexity:
- **postgres**: PostgreSQL database (port 5432)
- **web**: Django API and dashboard (port 8000)
- **collector**: Continuous URL processor (uses database queue)

### Architecture Benefits
- **Simple**: Each container does one thing well
- **Reliable**: Containers restart automatically if they crash
- **Scalable**: Adjust `COLLECTOR_WORKERS` env var for parallel processing
- **Observable**: Standard Docker logs for monitoring
- **Resource Efficient**: Collector only runs when URLs are pending

### How It Works
1. Extension adds URL → Saved to `queued_urls` table
2. Django API logs the queue status
3. Collector service polls database every few seconds
4. When URLs found → Processes with configured workers
5. Updates database → Continues polling

### Docker Commands
```bash
# Start all services
docker-compose up -d

# Monitor collector in real-time
docker-compose logs -f collector

# Scale collector workers (via environment)
COLLECTOR_WORKERS=8 docker-compose up -d collector

# Restart collector if needed
docker-compose restart collector

# Check service health
docker-compose ps
```

### Key Configuration
The collector service in `docker-compose.yml`:
- Runs continuously with `--from-queue` flag
- Uses `COLLECTOR_WORKERS` environment variable
- Connects to PostgreSQL for queue management
- Has GPU access for transcription/OCR
- Restarts automatically on failure