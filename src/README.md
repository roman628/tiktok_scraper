# TikTok Data Collection - Core Modules

This directory contains the modular components that power the TikTok data collection pipeline. Each module has a specific responsibility and clean interface, working together to extract video metadata, transcripts, and comments.

## Module Overview

### 📊 models.py
**Data structures and type definitions**
- `VideoData`: Complete video metadata structure (likes, shares, comments, etc.)
- `Comment`: Comment and reply data structure with nested relationships
- `ProcessingState`: Tracks processing status and progress
- Provides clean, typed interfaces for data passing between modules

### 🎥 video_extractor.py
**Video downloading and metadata extraction**
- Interfaces with yt-dlp for robust video downloading
- Extracts comprehensive metadata (title, description, stats, timestamps)
- Handles various video quality options and formats
- Manages temporary download directories
- Returns structured `VideoData` objects

### 💬 comment_extractor.py
**TikTok API comment extraction**
- Fetches comments and replies using TikTok's internal API
- Handles MS_TOKEN authentication for API access
- Implements pagination for large comment threads
- Structures nested comment relationships
- Returns list of `Comment` objects with full thread hierarchy

### 🎙️ transcript_extractor.py
**AI-powered video transcription**
- Integrates OpenAI's Whisper model for speech-to-text
- Supports multiple Whisper model sizes (tiny, base, small, medium, large)
- Handles audio extraction from videos
- Provides timestamp-aligned transcriptions
- Manages model loading and GPU/CPU inference

### 💾 data_manager.py
**JSON operations and data persistence**
- Memory-efficient streaming JSON append operations
- Atomic file writes with cross-platform file locking
- Duplicate URL detection and filtering
- JSON validation and repair capabilities
- Progress tracking and resumption support
- Consolidates all file I/O operations

### 🔗 url_processor.py
**URL validation and parsing**
- Validates TikTok URL formats
- Extracts video IDs from various URL patterns
- Handles short URLs and redirects
- Normalizes URLs for consistent processing
- Provides URL deduplication utilities

### 🧹 resource_manager.py
**System resource and memory management**
- Monitors memory usage and triggers cleanup
- Manages temporary file cleanup
- Handles process lifecycle and graceful shutdowns
- Implements resource limits for stability
- Provides cross-platform resource utilities

## Data Flow

```
Input URL → url_processor (validate)
         ↓
    video_extractor (download & metadata)
         ↓
    transcript_extractor (Whisper AI)
         ↓
    comment_extractor (API fetch)
         ↓
    data_manager (save to JSON)
         ↓
    resource_manager (cleanup)
```

## Usage

These modules are orchestrated by the main `collector.py` script in the parent directory. They can also be imported and used independently:

```python
from src.video_extractor import VideoExtractor
from src.data_manager import DataManager
from src.models import VideoData

# Example: Extract video and save
extractor = VideoExtractor()
data = extractor.extract_video_data(url)
manager = DataManager("output.json")
manager.append_data(data)
```

## Key Design Principles

1. **Single Responsibility**: Each module handles one specific aspect of data collection
2. **Clean Interfaces**: Well-defined input/output contracts between modules
3. **Error Resilience**: Graceful degradation when individual components fail
4. **Resource Efficiency**: Memory-conscious design for processing large datasets
5. **Type Safety**: Structured data classes ensure consistency across the pipeline

## Dependencies

- **yt-dlp**: Video downloading and metadata extraction
- **openai-whisper**: Speech-to-text transcription
- **filelock**: Cross-platform file locking for concurrent access
- **psutil**: System resource monitoring
- Standard library modules for HTTP requests, JSON processing, and file operations

## Testing

Each module can be tested independently using the test suite in `../tests/`. The main test script validates the entire pipeline:

```bash
cd ../tests
python test_robust_downloader.py --with ../collector.py
```

This ensures all modules work correctly together and maintain the expected data format.