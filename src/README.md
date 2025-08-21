# TikTok Data Collection - Core Modules

This directory contains the modular components that power the TikTok data collection pipeline. Each module has a specific responsibility and clean interface, working together to extract video metadata, transcripts, and comments.

## Module Overview (11 Total)

### 📊 models.py
**Data structures and type definitions**
- `VideoData`: Complete video metadata structure (views, likes, shares, etc.)
- `Comment`: Comment and reply data structure with nested relationships
- `ProcessingState`: Tracks processing status with percentage calculations
- Type-safe dataclasses with automatic serialization
- Built-in validation methods (`is_complete()`)

### 🎥 video_extractor.py
**Video downloading and metadata extraction**
- Interfaces with yt-dlp for robust video downloading
- Extracts comprehensive metadata (title, description, stats, timestamps)
- Audio-only mode for Whisper processing
- Cross-platform filename sanitization
- Shutdown event handling during downloads
- Integration with DeviceManager for GPU detection

### 💬 comment_extractor.py
**TikTok API comment extraction (Currently Non-functional)**
- **Status**: Broken due to TikTok API changes (as of 8/20/2025)
- Async/await pattern for API calls
- MS_TOKEN authentication with dynamic reload
- Nested comment/reply structure handling
- Rate limiting and bot detection avoidance

### 🎙️ transcript_extractor.py
**AI-powered video transcription**
- Uses `faster-whisper` for improved performance
- Supports CUDA, MPS (Apple Silicon), and CPU
- Chunked processing with shutdown checks
- Audio extraction via FFmpeg
- Device selection through DeviceManager
- Enhanced error recovery and fallback options

### 💾 data_manager.py
**JSON operations and data persistence**
- Memory-efficient streaming JSON append
- Cross-platform file locking (`FileLock` class)
- Duplicate URL detection and filtering
- Automatic JSON repair for corrupted files
- Atomic write operations
- Progress tracking and resumption support

### 🔗 url_processor.py
**URL validation and parsing**
- Extracts video IDs from various TikTok URL formats
- Validates URLs with regex patterns
- Normalizes URLs for consistency
- Detects deleted/private video errors
- Manages URL file maintenance
- Automatic URL cleanup from files

### 🧹 resource_manager.py
**System resource and memory management**
- Memory usage monitoring with automatic cleanup
- Browser process killing (for comment extraction)
- Signal handler registration for graceful shutdown
- Directory and file cleanup utilities
- Forced exit capabilities

### 🖥️ device_manager.py
**GPU/CPU detection and configuration**
- CUDA (NVIDIA) GPU detection
- MPS (Apple Silicon) support
- Optimal compute type selection
- Device capability reporting
- Whisper-specific device configuration
- Compatibility warnings and performance optimization

### 🎨 display_manager.py
**Rich terminal UI for multiprocessing**
- Responsive grid layout adapting to terminal size
- Per-worker progress tracking
- Real-time log streaming with color coding
- Flash animations for completed URLs
- TTY detection with fallback to simple mode
- Visual feedback (grey/blue/green/red borders)

### 📈 worker_progress.py
**Progress tracking for worker processes**
- 6 weighted stages: validating (5%), downloading (30%), metadata (10%), transcribing (40%), comments (10%), saving (5%)
- Granular progress reporting within each stage
- Multiprocessing queue communication
- Helper methods for common operations

### 🛑 shutdown_manager.py
**Centralized graceful shutdown handling**
- Unified signal handling across processes
- Cleanup handler registration with timeout protection
- Protected sections for critical operations
- Double Ctrl+C for forced termination
- Supports multiprocessing architecture

## Data Flow

```
Input URL → url_processor (validate)
         ↓
    video_extractor (download & metadata)
         ↓           ↓
    device_manager → transcript_extractor (Whisper AI)
         ↓
    comment_extractor (API fetch - currently broken)
         ↓
    data_manager (save to JSON)
         ↓
    resource_manager (cleanup)
         ↑
    shutdown_manager (graceful termination)

Parallel Processing:
    display_manager + worker_progress (real-time UI)
```

## Usage

These modules are orchestrated by the main `collector.py` script in the parent directory. They can also be imported and used independently:

```python
from src.video_extractor import VideoExtractor
from utils.data_manager import DataManager
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
6. **Multiprocessing Support**: Scalable architecture with worker coordination
7. **Cross-platform**: Windows, macOS, Linux with platform-specific optimizations
8. **Production Ready**: Robust error handling, signal management, and resource cleanup

## Dependencies

- **Core**: `yt-dlp`, `filelock`, `psutil`, `torch`
- **AI**: `faster-whisper`, `openai-whisper`
- **API**: `TikTokApi` (currently broken)
- **Display**: `rich` (for terminal UI)
- **Config**: `tomllib`/`tomli` for TOML parsing
- Standard library modules for async operations, JSON processing, and file operations

## Testing

Each module can be tested independently using the test suite in `../tests/`. The main test script validates the entire pipeline:

```bash
cd ../tests
python test_robust_downloader.py --with ../collector.py
```

This ensures all modules work correctly together and maintain the expected data format.