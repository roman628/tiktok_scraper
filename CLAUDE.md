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
config.toml
config.template.toml
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

---

# Complete API Reference Documentation

## Core Architecture

The TikTok scraper system is built around a modular architecture with the following components:

- **collector.py** - Main orchestrator that coordinates the entire pipeline
- **src/ modules** - Specialized components handling specific aspects of data extraction
- **data/ directory** - Input/output data files (urls.txt, master2.json)
- **tests/ directory** - Comprehensive testing framework

## Module Dependency Graph

```
collector.py (Main Orchestrator)
├── src/models.py (Data Structures)
├── src/video_extractor.py (Video Download + Metadata)
│   ├── src/transcript_extractor.py (Whisper AI)
│   └── src/resource_manager.py (Memory/Process Management)
├── src/comment_extractor.py (TikTok API Comments)
│   └── src/url_processor.py (URL Validation)
├── src/data_manager.py (JSON Operations)
│   └── FileLock (Cross-platform file locking)
└── src/resource_manager.py (Cleanup & Resource Management)
```

---

# collector.py - Main Orchestrator

## Classes

### RobustTikTokProcessor
**Main processor for TikTok data collection**

#### Constructor
```python
__init__(self, args)
```
- **args**: Command-line arguments object containing configuration
- **Initializes**: data_manager, video_extractor, resource_manager
- **Sets up**: Signal handlers for graceful shutdown

#### Methods

```python
cleanup(self)
```
Cleanup resources on shutdown
- Sets shutdown_requested flag
- Saves progress
- Cleans up extractors and resources

```python
get_ms_token(self) -> bool
```
Get MS_TOKEN from args or environment
- **Returns**: True if token found, False otherwise

```python
async validate_ms_token(self) -> bool
```
Validate MS_TOKEN by attempting to initialize API
- **Returns**: True if validation successful
- **Side effect**: Initializes comment_extractor if successful

```python
load_existing_progress(self)
```
Load existing URLs from master file for duplicate detection
- Delegates to DataManager
- Prints count of existing URLs

```python
filter_urls(self, urls: List[str]) -> List[str]
```
Filter out already processed URLs
- **urls**: List of URLs to filter
- **Returns**: List of unprocessed URLs

```python
async process_urls(self, urls: List[str], download_kwargs: Dict[str, Any])
```
Process list of URLs with progress tracking
- **urls**: URLs to process
- **download_kwargs**: Configuration for video extraction
- Handles batch saving and memory cleanup

```python
async process_single_url(self, url: str, download_kwargs: Dict[str, Any]) -> bool
```
Process a single TikTok URL through complete pipeline
- **url**: TikTok URL to process
- **download_kwargs**: Extraction configuration
- **Returns**: True if successful, False if failed
- **Pipeline**: Video download → Metadata → Transcription → Comments → Save

```python
async cleanup_api_session(self)
```
Clean up API sessions
- Closes comment extractor sessions

### MultiprocessCoordinator
**Coordinator for multiprocess data collection**

#### Constructor
```python
__init__(self, args, ms_token: Optional[str] = None)
```
- **args**: Command-line arguments
- **ms_token**: Optional MS_TOKEN for API access
- **Initializes**: Multiprocessing queues and shared state

#### Methods

```python
async process_urls_multiprocess(self, urls: List[str], download_kwargs: Dict[str, Any], 
                               master_file: str, source_file: Optional[str])
```
Process URLs using multiple worker processes
- **urls**: URLs to process
- **download_kwargs**: Processing configuration
- **master_file**: Output JSON file
- **source_file**: Input URLs file
- Manages worker processes and result collection

## Standalone Functions

```python
worker_process(worker_id: int, url_queue, result_queue, shutdown_event,
              args, download_kwargs: Dict[str, Any], ms_token: Optional[str])
```
Worker process for parallel data collection
- **worker_id**: Unique identifier for worker
- **url_queue**: Queue of URLs to process
- **result_queue**: Queue for results
- **shutdown_event**: Shutdown coordination
- **args**: Processing arguments
- **download_kwargs**: Video extraction parameters
- **ms_token**: Optional API token

```python
load_urls_from_file(file_path: str) -> List[str]
```
Load URLs from file (delegates to URLProcessor)
- **file_path**: Path to URLs file
- **Returns**: List of valid TikTok URLs

```python
auto_clean_master_json(master_file: str)
```
Auto-clean master JSON file and display stats
- **master_file**: Path to master JSON file
- Prints file statistics

```python
load_config(config_path: str = "config.toml") -> Dict[str, Any]
```
Load configuration from TOML file
- **config_path**: Path to configuration file
- **Returns**: Configuration dictionary

```python
merge_config_with_args(args, config: Dict[str, Any])
```
Merge TOML config with command-line arguments (CLI takes precedence)
- **args**: Argument namespace to modify
- **config**: Configuration dictionary
- **Returns**: Modified args with config applied
- **Handles**: Boolean flags, file paths, processing parameters

---

# src/models.py - Data Structures

## Classes

### Comment
**Represents a TikTok comment with replies**

#### Dataclass Fields
```python
text: str                    # Comment text content
user: str                    # Username of commenter
likes: int                   # Number of likes
replies: List['Comment']     # Nested replies (recursive)
```

#### Methods
```python
to_dict(self) -> Dict[str, Any]
```
Convert to dictionary for JSON serialization
- **Returns**: Dictionary with all fields including serialized replies

### VideoData
**Complete TikTok video data structure**

#### Dataclass Fields
```python
url: str                     # Original TikTok URL
video_id: str               # Extracted video ID
transcript: str             # Whisper AI transcription
metadata: Dict[str, Any]    # Complete video metadata
comments: List[Comment]     # Top-level comments with replies
```

#### Methods
```python
to_dict(self) -> Dict[str, Any]
```
Convert to dictionary for JSON serialization
- **Returns**: Complete data structure as dictionary

```python
is_complete(self) -> bool
```
Check if all essential data is present
- **Returns**: True if url, transcript, metadata, and comments are all present

### ProcessingState
**Tracks processing state for resumable operations**

#### Dataclass Fields
```python
total_urls: int = 0                    # Total URLs to process
processed_urls: int = 0                # Successfully processed URLs
failed_urls: List[str] = []            # List of failed URLs
existing_urls: set = set()             # Set of already processed URLs
start_time: datetime = datetime.now()  # Processing start timestamp
```

#### Properties
```python
@property
progress_percentage(self) -> float
```
Calculate progress percentage
- **Returns**: Percentage (0.0-100.0) of completion

---

# src/video_extractor.py - Video Download & Metadata

## Classes

### VideoExtractor
**Handles video downloading and metadata extraction using yt-dlp**

#### Constructor
```python
__init__(self, output_dir: str = "downloads", quality: str = "best", proxy: Optional[str] = None)
```
- **output_dir**: Directory for downloads
- **quality**: Video quality setting (best, worst, 720p, 480p, 360p)
- **proxy**: Optional proxy URL
- **Initializes**: transcript_extractor, shutdown flag

#### Methods

```python
set_shutdown(self, value: bool = True)
```
Set shutdown flag for graceful termination
- **value**: Shutdown flag state

```python
download_single_video(self, url: str, audio_only: bool = False, 
                    use_whisper: bool = False, whisper_model: Any = None,
                    whisper_device: str = "CPU") -> Dict[str, Any]
```
Download a single TikTok video with metadata
- **url**: TikTok video URL
- **audio_only**: Extract audio only (MP3)
- **use_whisper**: Enable transcription
- **whisper_model**: Pre-loaded Whisper model
- **whisper_device**: Device for Whisper (CPU/CUDA)
- **Returns**: Dictionary with success status, metadata, folder path
- **Pipeline**: Extract metadata → Download content → Transcribe → Save metadata

```python
_extract_metadata(self, url: str) -> Optional[Dict[str, Any]]
```
Extract video metadata without downloading
- **url**: TikTok URL
- **Returns**: Complete metadata dictionary or None if failed
- **Metadata includes**: title, description, duration, counts, timestamps, format info

```python
_download_content(self, url: str, video_folder: Path, folder_name: str, 
                 audio_only: bool, use_whisper: bool) -> Optional[Path]
```
Download video or audio content
- **url**: TikTok URL
- **video_folder**: Target directory
- **folder_name**: Base filename
- **audio_only**: Audio-only mode
- **use_whisper**: Keep video for transcription
- **Returns**: Path to downloaded file or None if failed

```python
_transcribe_video(self, video_path: Path, whisper_model: Any, device: str) -> str
```
Transcribe video using Whisper
- **video_path**: Path to video file
- **whisper_model**: Loaded Whisper model
- **device**: Processing device
- **Returns**: Transcribed text or empty string

```python
_sanitize_filename(self, filename: str) -> str
```
Sanitize filename for filesystem compatibility
- **filename**: Original filename
- **Returns**: Sanitized filename safe for filesystem
- **Handles**: Platform-specific invalid characters, length limits

```python
cleanup(self)
```
Clean up resources
- Cleans up transcript extractor
- Forces memory cleanup
- Kills browser processes

## Standalone Functions

```python
load_whisper_model(force_cpu: bool = False) -> Tuple[Any, str]
```
Load Whisper model for transcription
- **force_cpu**: Force CPU usage even if GPU available
- **Returns**: Tuple of (model, device_string)
- **Auto-detects**: CUDA availability and falls back to CPU

```python
get_memory_usage() -> float
```
Get current memory usage in MB
- **Returns**: Memory usage in megabytes
- Delegates to ResourceManager

---

# src/comment_extractor.py - TikTok API Comments

## Classes

### CommentExtractor
**Handles TikTok comment extraction with API integration**

#### Constructor
```python
__init__(self, ms_token: Optional[str] = None, max_comments: int = 50)
```
- **ms_token**: TikTok MS_TOKEN for API authentication
- **max_comments**: Maximum comments to fetch per video
- **Initializes**: API and session to None (lazy loading)

#### Methods

```python
async _initialize_api(self)
```
Initialize TikTok API with browser session
- Creates TikTokApi instance
- Creates sessions with MS_TOKEN
- Sets up headless browser session

```python
async extract_comments(self, url: str) -> List[Comment]
```
Extract comments from TikTok video
- **url**: TikTok video URL
- **Returns**: List of Comment objects with nested replies
- **Process**: Extract video ID → Get video object → Fetch comments → Parse replies
- **Includes**: Rate limiting and error handling

```python
_parse_comment(self, comment_obj) -> Comment
```
Parse TikTok API comment object into Comment model
- **comment_obj**: Raw API comment object
- **Returns**: Comment dataclass instance
- **Handles**: Multiple author field formats, attribute access patterns

```python
async _fetch_replies(self, comment_obj, max_replies: int = 10) -> List[Comment]
```
Fetch replies for a comment
- **comment_obj**: Parent comment object
- **max_replies**: Maximum replies to fetch
- **Returns**: List of reply Comment objects
- **Features**: Recursive reply parsing, rate limiting

```python
extract_comments_sync(self, url: str) -> List[Comment]
```
Synchronous wrapper for comment extraction
- **url**: TikTok video URL
- **Returns**: List of Comment objects
- **Purpose**: Compatibility with synchronous code (multiprocessing)

```python
async cleanup(self)
```
Clean up API resources
- Closes TikTokApi sessions
- Resets api and session to None

```python
cleanup_sync(self)
```
Synchronous cleanup wrapper
- Runs async cleanup in new event loop
- Exception-safe cleanup

---

# src/transcript_extractor.py - Whisper AI

## Classes

### TranscriptExtractor
**Handles video transcription using Whisper AI**

#### Constructor
```python
__init__(self, model_size: str = "base", device: str = "auto")
```
- **model_size**: Whisper model size (tiny, base, small, medium, large)
- **device**: Device to use (auto, cuda, cpu)
- **Initializes**: Model loading with device detection

#### Methods

```python
_determine_device(self, device: str) -> str
```
Determine the best device for Whisper
- **device**: Requested device (auto, cuda, cpu)
- **Returns**: Optimal device string
- **Auto-detects**: CUDA availability via torch and nvidia-smi

```python
_load_model(self)
```
Load Whisper model with appropriate settings
- **Device-specific**: compute_type (float16 for CUDA, int8 for CPU)
- **Fallback**: Automatically falls back to CPU if CUDA fails
- **Prints**: Model loading confirmation

```python
extract_transcript(self, video_path: str) -> str
```
Extract transcript from video file
- **video_path**: Path to the video file
- **Returns**: Transcript text or empty string if extraction fails
- **Process**: Check file → Extract audio → Transcribe → Combine segments → Cleanup
- **Settings**: beam_size=5, language="en", condition_on_previous_text=False

```python
_extract_audio(self, video_path: str) -> Optional[str]
```
Extract audio from video file using ffmpeg
- **video_path**: Path to video file
- **Returns**: Path to extracted audio file or None if extraction fails
- **Supports**: Direct audio files (mp3, wav, m4a, aac)
- **Fallback**: Tries different codecs if first attempt fails
- **Timeout**: 30-second timeout for extraction

```python
cleanup(self)
```
Clean up resources
- Deletes Whisper model from memory
- Forces memory cleanup

---

# src/data_manager.py - JSON Operations

## Classes

### FileLock
**Cross-platform file locking**

#### Constructor
```python
__init__(self, file_path: str)
```
- **file_path**: File to lock
- **Creates**: Lock file path (.lock suffix)

#### Context Manager Methods
```python
__enter__(self)
```
Acquire file lock (platform-specific)
- **Windows**: Uses msvcrt.locking with retry loop
- **Unix/Linux**: Uses fcntl.flock with exclusive lock

```python
__exit__(self, exc_type, exc_val, exc_tb)
```
Release file lock and cleanup
- **Unlocks**: Platform-specific unlock
- **Cleanup**: Removes lock file

### DataManager
**Manages all JSON operations and data persistence**

#### Constructor
```python
__init__(self, master_file: str = "master2.json")
```
- **master_file**: Path to master JSON file
- **Initializes**: existing_urls set, threading lock
- **Loads**: Existing URLs for duplicate detection

#### Methods

```python
_load_existing_urls(self)
```
Load existing URLs from master file for duplicate detection
- **Reads**: JSON file and extracts all URLs
- **Handles**: Corrupted JSON with automatic repair
- **Populates**: existing_urls set for fast lookup

```python
is_duplicate(self, url: str) -> bool
```
Check if URL already exists in dataset
- **url**: URL to check
- **Returns**: True if URL already processed
- **Performance**: O(1) set lookup

```python
append_to_master(self, data: Dict[str, Any])
```
Append single entry to master JSON file
- **data**: Dictionary to append
- **Delegates**: To append_batch_to_master with single-item list

```python
append_batch_to_master(self, data_list: List[Dict[str, Any]])
```
Memory-efficient batch append to master JSON file
- **data_list**: List of dictionaries to append
- **Thread-safe**: Uses threading lock and file lock
- **Updates**: existing_urls cache
- **Atomic**: Uses temporary file for safe writes

```python
_append_batch_efficient(self, metadata_list: List[Dict[str, Any]])
```
Internal method for efficient JSON streaming append
- **metadata_list**: Data to append
- **Streaming**: Memory-efficient for large files
- **Format**: Maintains valid JSON array format
- **Handles**: Empty files, existing arrays, format conversion

```python
_stream_existing_content(self, original_file, temp_file) -> bool
```
Stream existing JSON array content efficiently
- **original_file**: Source file handle
- **temp_file**: Destination file handle
- **Returns**: True if content was found
- **Memory-efficient**: Streams in 10KB chunks
- **Parser**: Custom JSON streaming parser

```python
_repair_json_file(self) -> bool
```
Repair corrupted JSON file by extracting valid objects
- **Returns**: True if repair successful
- **Strategy**: Extract individual JSON objects from corrupted content
- **Fallback**: Handles missing commas, trailing commas

```python
_extract_json_objects(self, content: str) -> List[Dict[str, Any]]
```
Extract individual JSON objects from corrupted content
- **content**: Raw file content string
- **Returns**: List of valid JSON objects
- **Parser**: Line-by-line brace counting parser
- **Resilient**: Handles multiple corruption patterns

```python
get_stats(self) -> Dict[str, Any]
```
Get statistics about the data
- **Returns**: Dictionary with total_entries, file_size_mb, has_duplicates
- **Performance**: Fast stats from cached data

---

# src/url_processor.py - URL Validation

## Classes

### URLProcessor
**Handles all URL processing, validation, and extraction**

#### Class Variables
```python
TIKTOK_PATTERNS: List[str] = [
    r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)',
    r'https?://(?:vm|vt)\.tiktok\.com/[^\s]+',
    r'https?://(?:www\.)?tiktok\.com/t/[^\s]+'
]
```
Regex patterns for TikTok URL validation

#### Class Methods

```python
@classmethod
extract_video_id(cls, url: str) -> Optional[str]
```
Extract video ID from TikTok URL
- **url**: TikTok URL to parse
- **Returns**: Video ID string or None if not found
- **Strategy**: Pattern matching → URL path parsing → Digit validation

```python
@classmethod
is_valid_tiktok_url(cls, url: str) -> bool
```
Check if URL is a valid TikTok video URL
- **url**: URL to validate
- **Returns**: True if valid TikTok URL
- **Checks**: String type, HTTP(S) protocol, pattern matching

```python
@classmethod
normalize_url(cls, url: str) -> str
```
Normalize TikTok URL to standard format
- **url**: URL to normalize
- **Returns**: Standardized URL format
- **Format**: https://www.tiktok.com/@user/video/{video_id}

```python
@classmethod
load_urls_from_file(cls, file_path: str) -> List[str]
```
Load and validate URLs from file
- **file_path**: Path to URLs file
- **Returns**: List of valid TikTok URLs
- **Filters**: Comments (#), empty lines, invalid URLs
- **Encoding**: UTF-8 with error handling

```python
@classmethod
deduplicate_urls(cls, urls: List[str], existing: Set[str] = None) -> List[str]
```
Remove duplicate URLs
- **urls**: List of URLs to deduplicate
- **existing**: Set of already seen URLs
- **Returns**: List of unique URLs
- **Uses**: Normalized URLs for comparison

---

# src/resource_manager.py - Resource Management

## Classes

### ResourceManager
**Manages system resources, memory, and process cleanup**

#### Class Variables
```python
MEMORY_THRESHOLD_MB: int = 2000    # Trigger cleanup above this threshold
BROWSER_PROCESSES: List[str] = ['chrome', 'chromium', 'chromedriver', 'google-chrome']
```

#### Constructor
```python
__init__(self)
```
- **Initializes**: Signal handlers list, original signal handler storage

#### Methods

```python
register_signal_handlers(self, cleanup_callback=None)
```
Register signal handlers for graceful shutdown
- **cleanup_callback**: Optional cleanup function to call on shutdown
- **Handles**: SIGINT (Ctrl+C), SIGTERM
- **Action**: Calls all registered cleanup handlers and exits

```python
restore_signal_handlers(self)
```
Restore original signal handlers
- **Restores**: Original SIGINT handler
- **Purpose**: Cleanup after resource manager usage

```python
@staticmethod
cleanup_memory()
```
Force garbage collection and clear memory
- **Strategy**: Triple gc.collect() for thorough cleanup
- **Purpose**: Clear circular references, optimize memory

```python
@staticmethod
get_memory_usage_mb() -> float
```
Get current process memory usage in MB
- **Returns**: Memory usage in megabytes
- **Uses**: psutil for accurate memory measurement

```python
@classmethod
check_memory_and_cleanup(cls) -> bool
```
Check memory usage and cleanup if needed
- **Returns**: True if cleanup was performed
- **Threshold**: MEMORY_THRESHOLD_MB (2000MB)
- **Auto-cleanup**: Triggers cleanup_memory() if over threshold

```python
@classmethod
kill_browser_processes(cls)
```
Kill any lingering browser processes
- **Target**: Chrome, Chromium, ChromeDriver processes
- **Method**: Process iteration and termination
- **Reports**: Count of killed processes
- **Safe**: Handles access denied, no such process errors

```python
@staticmethod
cleanup_directory(directory: str)
```
Remove directory and all contents
- **directory**: Path to directory to remove
- **Method**: shutil.rmtree with error handling

```python
@staticmethod
cleanup_file(file_path: str)
```
Remove a single file
- **file_path**: Path to file to remove
- **Safe**: Checks existence before removal

```python
@classmethod
full_cleanup(cls, directories: List[str] = None, files: List[str] = None)
```
Perform full system cleanup
- **directories**: Optional list of directories to remove
- **files**: Optional list of files to remove
- **Process**: Kill browsers → Clean directories → Clean files → Force memory cleanup

```python
@staticmethod
ensure_cuda_available() -> bool
```
Check if CUDA is available for GPU acceleration
- **Returns**: True if nvidia-smi command succeeds
- **Method**: subprocess call to nvidia-smi
- **Timeout**: 5-second timeout
- **Purpose**: GPU availability detection for Whisper

---

# Configuration and Constants

## Command Line Arguments (collector.py)

### Input Options
- `--url`: Single TikTok URL to process
- `--from-file`: File containing URLs (one per line)
- `--limit`: Limit number of URLs to process

### Download Options
- `-o, --output`: Output directory (default: "downloads")
- `-q, --quality`: Video quality (best, worst, 720p, 480p, 360p)
- `--mp3`: Download audio only as MP3
- `--whisper`: Use Whisper for transcription
- `--force-cpu`: Force CPU for Whisper

### Comment Options
- `--max-comments`: Max comments per video (default: 10)
- `--ms-token`: MS_TOKEN for comment extraction

### Batch Options
- `--batch-size`: Save every N videos (default: 10)
- `--delay`: Delay between requests in seconds (default: 2)
- `--json-output`: JSON output file (default: "master2.json")

### Resume Options
- `--force-redownload`: Ignore duplicates
- `--clean-progress`: Start fresh

### System Options
- `--proxy`: Proxy URL
- `--workers`: Number of worker processes (default: 1)

## Configuration File Mapping (config.toml)

### Section Mappings
```toml
[tiktok]
ms_token = "..."              # → --ms-token

[input]
default_urls_file = "..."     # → --from-file
limit = 100                   # → --limit

[download]
output_dir = "downloads"      # → --output
quality = "best"              # → --quality
audio_only = false            # → --mp3
use_whisper = true            # → --whisper
force_cpu = false             # → --force-cpu

[comments]
max_comments = 50             # → --max-comments

[processing]
batch_size = 10               # → --batch-size
delay = 2                     # → --delay
workers = 1                   # → --workers

[output]
json_output = "master2.json"  # → --json-output

[resume]
skip_duplicates = true        # → inverse of --force-redownload
force_redownload = false      # → --force-redownload
clean_start = false           # → --clean-progress

[network]
proxy = "..."                 # → --proxy
```

## File Structure Constants

### Default Paths
- **URLs Input**: `data/urls.txt` or `urls.txt`
- **JSON Output**: `data/master2.json` or `master2.json`
- **Downloads**: `downloads/` directory
- **Configuration**: `config.toml`
- **Test URLs**: `tests/test_urls.txt`
- **Test Output**: `tests/test_output.json`
- **Test Report**: `tests/test_report.json`

### Processing Defaults
- **Whisper Model**: "small.en" for English transcription
- **Memory Threshold**: 2000MB for cleanup trigger
- **Batch Size**: 10 videos per save
- **Delay**: 2 seconds between requests
- **Max Comments**: 10 per video (with 10 replies each)
- **Timeout**: 30 seconds for ffmpeg operations

---

# Data Flow Summary

## Complete Processing Pipeline

1. **Input Processing**
   - Load URLs from file or command line
   - Validate TikTok URL format
   - Filter out duplicates using DataManager

2. **Video Extraction (VideoExtractor)**
   - Extract metadata using yt-dlp
   - Download video/audio content
   - Create organized folder structure

3. **Transcription (TranscriptExtractor)**
   - Load Whisper AI model (GPU/CPU)
   - Extract audio from video
   - Generate transcript with timestamps

4. **Comment Extraction (CommentExtractor)**
   - Initialize TikTok API with MS_TOKEN
   - Fetch comments and nested replies
   - Parse comment data structures

5. **Data Assembly**
   - Flatten all data into single JSON structure
   - Include video metadata, transcript, comments
   - Add processing timestamps

6. **Data Persistence (DataManager)**
   - Stream append to master JSON file
   - Cross-platform file locking
   - Duplicate URL tracking

7. **Resource Cleanup (ResourceManager)**
   - Memory cleanup after each video
   - Browser process termination
   - Temporary file removal

## Error Handling Strategy

- **Graceful Degradation**: Each component fails independently
- **Retry Logic**: Automatic retries for network operations
- **Resource Recovery**: Automatic cleanup on failures
- **Progress Preservation**: Partial results saved immediately
- **Duplicate Prevention**: URL tracking prevents reprocessing

This modular architecture ensures robustness, maintainability, and scalability for the TikTok data collection system.

---

# Complete API Reference Documentation

## Core Architecture

The TikTok scraper system is built around a modular architecture with the following components:

- **collector.py** - Main orchestrator that coordinates the entire pipeline
- **src/ modules** - Specialized components handling specific aspects of data extraction
- **data/ directory** - Input/output data files (urls.txt, master2.json)
- **tests/ directory** - Comprehensive testing framework

## Module Dependency Graph

```
collector.py (Main Orchestrator)
├── src/models.py (Data Structures)
├── src/video_extractor.py (Video Download + Metadata)
│   ├── src/transcript_extractor.py (Whisper AI)
│   └── src/resource_manager.py (Memory/Process Management)
├── src/comment_extractor.py (TikTok API Comments)
│   └── src/url_processor.py (URL Validation)
├── src/data_manager.py (JSON Operations)
│   └── FileLock (Cross-platform file locking)
└── src/resource_manager.py (Cleanup & Resource Management)
```

---

# collector.py - Main Orchestrator

## Classes

### RobustTikTokProcessor
**Main processor for TikTok data collection**

#### Constructor
```python
__init__(self, args)
```
- **args**: Command-line arguments object containing configuration
- **Initializes**: data_manager, video_extractor, resource_manager
- **Sets up**: Signal handlers for graceful shutdown

#### Methods

```python
cleanup(self)
```
Cleanup resources on shutdown
- Sets shutdown_requested flag
- Saves progress
- Cleans up extractors and resources

```python
get_ms_token(self) -> bool
```
Get MS_TOKEN from args or environment
- **Returns**: True if token found, False otherwise

```python
async validate_ms_token(self) -> bool
```
Validate MS_TOKEN by attempting to initialize API
- **Returns**: True if validation successful
- **Side effect**: Initializes comment_extractor if successful

```python
load_existing_progress(self)
```
Load existing URLs from master file for duplicate detection
- Delegates to DataManager
- Prints count of existing URLs

```python
filter_urls(self, urls: List[str]) -> List[str]
```
Filter out already processed URLs
- **urls**: List of URLs to filter
- **Returns**: List of unprocessed URLs

```python
async process_urls(self, urls: List[str], download_kwargs: Dict[str, Any])
```
Process list of URLs with progress tracking
- **urls**: URLs to process
- **download_kwargs**: Configuration for video extraction
- Handles batch saving and memory cleanup

```python
async process_single_url(self, url: str, download_kwargs: Dict[str, Any]) -> bool
```
Process a single TikTok URL through complete pipeline
- **url**: TikTok URL to process
- **download_kwargs**: Extraction configuration
- **Returns**: True if successful, False if failed
- **Pipeline**: Video download → Metadata → Transcription → Comments → Save

```python
async cleanup_api_session(self)
```
Clean up API sessions
- Closes comment extractor sessions

### MultiprocessCoordinator
**Coordinator for multiprocess data collection**

#### Constructor
```python
__init__(self, args, ms_token: Optional[str] = None)
```
- **args**: Command-line arguments
- **ms_token**: Optional MS_TOKEN for API access
- **Initializes**: Multiprocessing queues and shared state

#### Methods

```python
async process_urls_multiprocess(self, urls: List[str], download_kwargs: Dict[str, Any], 
                               master_file: str, source_file: Optional[str])
```
Process URLs using multiple worker processes
- **urls**: URLs to process
- **download_kwargs**: Processing configuration
- **master_file**: Output JSON file
- **source_file**: Input URLs file
- Manages worker processes and result collection

## Standalone Functions

```python
worker_process(worker_id: int, url_queue, result_queue, shutdown_event,
              args, download_kwargs: Dict[str, Any], ms_token: Optional[str])
```
Worker process for parallel data collection
- **worker_id**: Unique identifier for worker
- **url_queue**: Queue of URLs to process
- **result_queue**: Queue for results
- **shutdown_event**: Shutdown coordination
- **args**: Processing arguments
- **download_kwargs**: Video extraction parameters
- **ms_token**: Optional API token

```python
load_urls_from_file(file_path: str) -> List[str]
```
Load URLs from file (delegates to URLProcessor)
- **file_path**: Path to URLs file
- **Returns**: List of valid TikTok URLs

```python
auto_clean_master_json(master_file: str)
```
Auto-clean master JSON file and display stats
- **master_file**: Path to master JSON file
- Prints file statistics

```python
load_config(config_path: str = "config.toml") -> Dict[str, Any]
```
Load configuration from TOML file
- **config_path**: Path to configuration file
- **Returns**: Configuration dictionary

```python
merge_config_with_args(args, config: Dict[str, Any])
```
Merge TOML config with command-line arguments (CLI takes precedence)
- **args**: Argument namespace to modify
- **config**: Configuration dictionary
- **Returns**: Modified args with config applied
- **Handles**: Boolean flags, file paths, processing parameters

---

# src/models.py - Data Structures

## Classes

### Comment
**Represents a TikTok comment with replies**

#### Dataclass Fields
```python
text: str                    # Comment text content
user: str                    # Username of commenter
likes: int                   # Number of likes
replies: List['Comment']     # Nested replies (recursive)
```

#### Methods
```python
to_dict(self) -> Dict[str, Any]
```
Convert to dictionary for JSON serialization
- **Returns**: Dictionary with all fields including serialized replies

### VideoData
**Complete TikTok video data structure**

#### Dataclass Fields
```python
url: str                     # Original TikTok URL
video_id: str               # Extracted video ID
transcript: str             # Whisper AI transcription
metadata: Dict[str, Any]    # Complete video metadata
comments: List[Comment]     # Top-level comments with replies
```

#### Methods
```python
to_dict(self) -> Dict[str, Any]
```
Convert to dictionary for JSON serialization
- **Returns**: Complete data structure as dictionary

```python
is_complete(self) -> bool
```
Check if all essential data is present
- **Returns**: True if url, transcript, metadata, and comments are all present

### ProcessingState
**Tracks processing state for resumable operations**

#### Dataclass Fields
```python
total_urls: int = 0                    # Total URLs to process
processed_urls: int = 0                # Successfully processed URLs
failed_urls: List[str] = []            # List of failed URLs
existing_urls: set = set()             # Set of already processed URLs
start_time: datetime = datetime.now()  # Processing start timestamp
```

#### Properties
```python
@property
progress_percentage(self) -> float
```
Calculate progress percentage
- **Returns**: Percentage (0.0-100.0) of completion

---

# src/video_extractor.py - Video Download & Metadata

## Classes

### VideoExtractor
**Handles video downloading and metadata extraction using yt-dlp**

#### Constructor
```python
__init__(self, output_dir: str = "downloads", quality: str = "best", proxy: Optional[str] = None)
```
- **output_dir**: Directory for downloads
- **quality**: Video quality setting (best, worst, 720p, 480p, 360p)
- **proxy**: Optional proxy URL
- **Initializes**: transcript_extractor, shutdown flag

#### Methods

```python
set_shutdown(self, value: bool = True)
```
Set shutdown flag for graceful termination
- **value**: Shutdown flag state

```python
download_single_video(self, url: str, audio_only: bool = False, 
                    use_whisper: bool = False, whisper_model: Any = None,
                    whisper_device: str = "CPU") -> Dict[str, Any]
```
Download a single TikTok video with metadata
- **url**: TikTok video URL
- **audio_only**: Extract audio only (MP3)
- **use_whisper**: Enable transcription
- **whisper_model**: Pre-loaded Whisper model
- **whisper_device**: Device for Whisper (CPU/CUDA)
- **Returns**: Dictionary with success status, metadata, folder path
- **Pipeline**: Extract metadata → Download content → Transcribe → Save metadata

```python
_extract_metadata(self, url: str) -> Optional[Dict[str, Any]]
```
Extract video metadata without downloading
- **url**: TikTok URL
- **Returns**: Complete metadata dictionary or None if failed
- **Metadata includes**: title, description, duration, counts, timestamps, format info

```python
_download_content(self, url: str, video_folder: Path, folder_name: str, 
                 audio_only: bool, use_whisper: bool) -> Optional[Path]
```
Download video or audio content
- **url**: TikTok URL
- **video_folder**: Target directory
- **folder_name**: Base filename
- **audio_only**: Audio-only mode
- **use_whisper**: Keep video for transcription
- **Returns**: Path to downloaded file or None if failed

```python
_transcribe_video(self, video_path: Path, whisper_model: Any, device: str) -> str
```
Transcribe video using Whisper
- **video_path**: Path to video file
- **whisper_model**: Loaded Whisper model
- **device**: Processing device
- **Returns**: Transcribed text or empty string

```python
_sanitize_filename(self, filename: str) -> str
```
Sanitize filename for filesystem compatibility
- **filename**: Original filename
- **Returns**: Sanitized filename safe for filesystem
- **Handles**: Platform-specific invalid characters, length limits

```python
cleanup(self)
```
Clean up resources
- Cleans up transcript extractor
- Forces memory cleanup
- Kills browser processes

## Standalone Functions

```python
load_whisper_model(force_cpu: bool = False) -> Tuple[Any, str]
```
Load Whisper model for transcription
- **force_cpu**: Force CPU usage even if GPU available
- **Returns**: Tuple of (model, device_string)
- **Auto-detects**: CUDA availability and falls back to CPU

```python
get_memory_usage() -> float
```
Get current memory usage in MB
- **Returns**: Memory usage in megabytes
- Delegates to ResourceManager

---

# src/comment_extractor.py - TikTok API Comments

## Classes

### CommentExtractor
**Handles TikTok comment extraction with API integration**

#### Constructor
```python
__init__(self, ms_token: Optional[str] = None, max_comments: int = 50)
```
- **ms_token**: TikTok MS_TOKEN for API authentication
- **max_comments**: Maximum comments to fetch per video
- **Initializes**: API and session to None (lazy loading)

#### Methods

```python
async _initialize_api(self)
```
Initialize TikTok API with browser session
- Creates TikTokApi instance
- Creates sessions with MS_TOKEN
- Sets up headless browser session

```python
async extract_comments(self, url: str) -> List[Comment]
```
Extract comments from TikTok video
- **url**: TikTok video URL
- **Returns**: List of Comment objects with nested replies
- **Process**: Extract video ID → Get video object → Fetch comments → Parse replies
- **Includes**: Rate limiting and error handling

```python
_parse_comment(self, comment_obj) -> Comment
```
Parse TikTok API comment object into Comment model
- **comment_obj**: Raw API comment object
- **Returns**: Comment dataclass instance
- **Handles**: Multiple author field formats, attribute access patterns

```python
async _fetch_replies(self, comment_obj, max_replies: int = 10) -> List[Comment]
```
Fetch replies for a comment
- **comment_obj**: Parent comment object
- **max_replies**: Maximum replies to fetch
- **Returns**: List of reply Comment objects
- **Features**: Recursive reply parsing, rate limiting

```python
extract_comments_sync(self, url: str) -> List[Comment]
```
Synchronous wrapper for comment extraction
- **url**: TikTok video URL
- **Returns**: List of Comment objects
- **Purpose**: Compatibility with synchronous code (multiprocessing)

```python
async cleanup(self)
```
Clean up API resources
- Closes TikTokApi sessions
- Resets api and session to None

```python
cleanup_sync(self)
```
Synchronous cleanup wrapper
- Runs async cleanup in new event loop
- Exception-safe cleanup

---

# src/transcript_extractor.py - Whisper AI

## Classes

### TranscriptExtractor
**Handles video transcription using Whisper AI**

#### Constructor
```python
__init__(self, model_size: str = "base", device: str = "auto")
```
- **model_size**: Whisper model size (tiny, base, small, medium, large)
- **device**: Device to use (auto, cuda, cpu)
- **Initializes**: Model loading with device detection

#### Methods

```python
_determine_device(self, device: str) -> str
```
Determine the best device for Whisper
- **device**: Requested device (auto, cuda, cpu)
- **Returns**: Optimal device string
- **Auto-detects**: CUDA availability via torch and nvidia-smi

```python
_load_model(self)
```
Load Whisper model with appropriate settings
- **Device-specific**: compute_type (float16 for CUDA, int8 for CPU)
- **Fallback**: Automatically falls back to CPU if CUDA fails
- **Prints**: Model loading confirmation

```python
extract_transcript(self, video_path: str) -> str
```
Extract transcript from video file
- **video_path**: Path to the video file
- **Returns**: Transcript text or empty string if extraction fails
- **Process**: Check file → Extract audio → Transcribe → Combine segments → Cleanup
- **Settings**: beam_size=5, language="en", condition_on_previous_text=False

```python
_extract_audio(self, video_path: str) -> Optional[str]
```
Extract audio from video file using ffmpeg
- **video_path**: Path to video file
- **Returns**: Path to extracted audio file or None if extraction fails
- **Supports**: Direct audio files (mp3, wav, m4a, aac)
- **Fallback**: Tries different codecs if first attempt fails
- **Timeout**: 30-second timeout for extraction

```python
cleanup(self)
```
Clean up resources
- Deletes Whisper model from memory
- Forces memory cleanup

---

# src/data_manager.py - JSON Operations

## Classes

### FileLock
**Cross-platform file locking**

#### Constructor
```python
__init__(self, file_path: str)
```
- **file_path**: File to lock
- **Creates**: Lock file path (.lock suffix)

#### Context Manager Methods
```python
__enter__(self)
```
Acquire file lock (platform-specific)
- **Windows**: Uses msvcrt.locking with retry loop
- **Unix/Linux**: Uses fcntl.flock with exclusive lock

```python
__exit__(self, exc_type, exc_val, exc_tb)
```
Release file lock and cleanup
- **Unlocks**: Platform-specific unlock
- **Cleanup**: Removes lock file

### DataManager
**Manages all JSON operations and data persistence**

#### Constructor
```python
__init__(self, master_file: str = "master2.json")
```
- **master_file**: Path to master JSON file
- **Initializes**: existing_urls set, threading lock
- **Loads**: Existing URLs for duplicate detection

#### Methods

```python
_load_existing_urls(self)
```
Load existing URLs from master file for duplicate detection
- **Reads**: JSON file and extracts all URLs
- **Handles**: Corrupted JSON with automatic repair
- **Populates**: existing_urls set for fast lookup

```python
is_duplicate(self, url: str) -> bool
```
Check if URL already exists in dataset
- **url**: URL to check
- **Returns**: True if URL already processed
- **Performance**: O(1) set lookup

```python
append_to_master(self, data: Dict[str, Any])
```
Append single entry to master JSON file
- **data**: Dictionary to append
- **Delegates**: To append_batch_to_master with single-item list

```python
append_batch_to_master(self, data_list: List[Dict[str, Any]])
```
Memory-efficient batch append to master JSON file
- **data_list**: List of dictionaries to append
- **Thread-safe**: Uses threading lock and file lock
- **Updates**: existing_urls cache
- **Atomic**: Uses temporary file for safe writes

```python
_append_batch_efficient(self, metadata_list: List[Dict[str, Any]])
```
Internal method for efficient JSON streaming append
- **metadata_list**: Data to append
- **Streaming**: Memory-efficient for large files
- **Format**: Maintains valid JSON array format
- **Handles**: Empty files, existing arrays, format conversion

```python
_stream_existing_content(self, original_file, temp_file) -> bool
```
Stream existing JSON array content efficiently
- **original_file**: Source file handle
- **temp_file**: Destination file handle
- **Returns**: True if content was found
- **Memory-efficient**: Streams in 10KB chunks
- **Parser**: Custom JSON streaming parser

```python
_repair_json_file(self) -> bool
```
Repair corrupted JSON file by extracting valid objects
- **Returns**: True if repair successful
- **Strategy**: Extract individual JSON objects from corrupted content
- **Fallback**: Handles missing commas, trailing commas

```python
_extract_json_objects(self, content: str) -> List[Dict[str, Any]]
```
Extract individual JSON objects from corrupted content
- **content**: Raw file content string
- **Returns**: List of valid JSON objects
- **Parser**: Line-by-line brace counting parser
- **Resilient**: Handles multiple corruption patterns

```python
get_stats(self) -> Dict[str, Any]
```
Get statistics about the data
- **Returns**: Dictionary with total_entries, file_size_mb, has_duplicates
- **Performance**: Fast stats from cached data

---

# src/url_processor.py - URL Validation

## Classes

### URLProcessor
**Handles all URL processing, validation, and extraction**

#### Class Variables
```python
TIKTOK_PATTERNS: List[str] = [
    r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)',
    r'https?://(?:vm|vt)\.tiktok\.com/[^\s]+',
    r'https?://(?:www\.)?tiktok\.com/t/[^\s]+'
]
```
Regex patterns for TikTok URL validation

#### Class Methods

```python
@classmethod
extract_video_id(cls, url: str) -> Optional[str]
```
Extract video ID from TikTok URL
- **url**: TikTok URL to parse
- **Returns**: Video ID string or None if not found
- **Strategy**: Pattern matching → URL path parsing → Digit validation

```python
@classmethod
is_valid_tiktok_url(cls, url: str) -> bool
```
Check if URL is a valid TikTok video URL
- **url**: URL to validate
- **Returns**: True if valid TikTok URL
- **Checks**: String type, HTTP(S) protocol, pattern matching

```python
@classmethod
normalize_url(cls, url: str) -> str
```
Normalize TikTok URL to standard format
- **url**: URL to normalize
- **Returns**: Standardized URL format
- **Format**: https://www.tiktok.com/@user/video/{video_id}

```python
@classmethod
load_urls_from_file(cls, file_path: str) -> List[str]
```
Load and validate URLs from file
- **file_path**: Path to URLs file
- **Returns**: List of valid TikTok URLs
- **Filters**: Comments (#), empty lines, invalid URLs
- **Encoding**: UTF-8 with error handling

```python
@classmethod
deduplicate_urls(cls, urls: List[str], existing: Set[str] = None) -> List[str]
```
Remove duplicate URLs
- **urls**: List of URLs to deduplicate
- **existing**: Set of already seen URLs
- **Returns**: List of unique URLs
- **Uses**: Normalized URLs for comparison

---

# src/resource_manager.py - Resource Management

## Classes

### ResourceManager
**Manages system resources, memory, and process cleanup**

#### Class Variables
```python
MEMORY_THRESHOLD_MB: int = 2000    # Trigger cleanup above this threshold
BROWSER_PROCESSES: List[str] = ['chrome', 'chromium', 'chromedriver', 'google-chrome']
```

#### Constructor
```python
__init__(self)
```
- **Initializes**: Signal handlers list, original signal handler storage

#### Methods

```python
register_signal_handlers(self, cleanup_callback=None)
```
Register signal handlers for graceful shutdown
- **cleanup_callback**: Optional cleanup function to call on shutdown
- **Handles**: SIGINT (Ctrl+C), SIGTERM
- **Action**: Calls all registered cleanup handlers and exits

```python
restore_signal_handlers(self)
```
Restore original signal handlers
- **Restores**: Original SIGINT handler
- **Purpose**: Cleanup after resource manager usage

```python
@staticmethod
cleanup_memory()
```
Force garbage collection and clear memory
- **Strategy**: Triple gc.collect() for thorough cleanup
- **Purpose**: Clear circular references, optimize memory

```python
@staticmethod
get_memory_usage_mb() -> float
```
Get current process memory usage in MB
- **Returns**: Memory usage in megabytes
- **Uses**: psutil for accurate memory measurement

```python
@classmethod
check_memory_and_cleanup(cls) -> bool
```
Check memory usage and cleanup if needed
- **Returns**: True if cleanup was performed
- **Threshold**: MEMORY_THRESHOLD_MB (2000MB)
- **Auto-cleanup**: Triggers cleanup_memory() if over threshold

```python
@classmethod
kill_browser_processes(cls)
```
Kill any lingering browser processes
- **Target**: Chrome, Chromium, ChromeDriver processes
- **Method**: Process iteration and termination
- **Reports**: Count of killed processes
- **Safe**: Handles access denied, no such process errors

```python
@staticmethod
cleanup_directory(directory: str)
```
Remove directory and all contents
- **directory**: Path to directory to remove
- **Method**: shutil.rmtree with error handling

```python
@staticmethod
cleanup_file(file_path: str)
```
Remove a single file
- **file_path**: Path to file to remove
- **Safe**: Checks existence before removal

```python
@classmethod
full_cleanup(cls, directories: List[str] = None, files: List[str] = None)
```
Perform full system cleanup
- **directories**: Optional list of directories to remove
- **files**: Optional list of files to remove
- **Process**: Kill browsers → Clean directories → Clean files → Force memory cleanup

```python
@staticmethod
ensure_cuda_available() -> bool
```
Check if CUDA is available for GPU acceleration
- **Returns**: True if nvidia-smi command succeeds
- **Method**: subprocess call to nvidia-smi
- **Timeout**: 5-second timeout
- **Purpose**: GPU availability detection for Whisper

---

# Configuration and Constants

## Command Line Arguments (collector.py)

### Input Options
- `--url`: Single TikTok URL to process
- `--from-file`: File containing URLs (one per line)
- `--limit`: Limit number of URLs to process

### Download Options
- `-o, --output`: Output directory (default: "downloads")
- `-q, --quality`: Video quality (best, worst, 720p, 480p, 360p)
- `--mp3`: Download audio only as MP3
- `--whisper`: Use Whisper for transcription
- `--force-cpu`: Force CPU for Whisper

### Comment Options
- `--max-comments`: Max comments per video (default: 10)
- `--ms-token`: MS_TOKEN for comment extraction

### Batch Options
- `--batch-size`: Save every N videos (default: 10)
- `--delay`: Delay between requests in seconds (default: 2)
- `--json-output`: JSON output file (default: "master2.json")

### Resume Options
- `--force-redownload`: Ignore duplicates
- `--clean-progress`: Start fresh

### System Options
- `--proxy`: Proxy URL
- `--workers`: Number of worker processes (default: 1)

## Configuration File Mapping (config.toml)

### Section Mappings
```toml
[tiktok]
ms_token = "..."              # → --ms-token

[input]
default_urls_file = "..."     # → --from-file
limit = 100                   # → --limit

[download]
output_dir = "downloads"      # → --output
quality = "best"              # → --quality
audio_only = false            # → --mp3
use_whisper = true            # → --whisper
force_cpu = false             # → --force-cpu

[comments]
max_comments = 50             # → --max-comments

[processing]
batch_size = 10               # → --batch-size
delay = 2                     # → --delay
workers = 1                   # → --workers

[output]
json_output = "master2.json"  # → --json-output

[resume]
skip_duplicates = true        # → inverse of --force-redownload
force_redownload = false      # → --force-redownload
clean_start = false           # → --clean-progress

[network]
proxy = "..."                 # → --proxy
```

## File Structure Constants

### Default Paths
- **URLs Input**: `data/urls.txt` or `urls.txt`
- **JSON Output**: `data/master2.json` or `master2.json`
- **Downloads**: `downloads/` directory
- **Configuration**: `config.toml`
- **Test URLs**: `tests/test_urls.txt`
- **Test Output**: `tests/test_output.json`
- **Test Report**: `tests/test_report.json`

### Processing Defaults
- **Whisper Model**: "small.en" for English transcription
- **Memory Threshold**: 2000MB for cleanup trigger
- **Batch Size**: 10 videos per save
- **Delay**: 2 seconds between requests
- **Max Comments**: 10 per video (with 10 replies each)
- **Timeout**: 30 seconds for ffmpeg operations

---

# Data Flow Summary

## Complete Processing Pipeline

1. **Input Processing**
   - Load URLs from file or command line
   - Validate TikTok URL format
   - Filter out duplicates using DataManager

2. **Video Extraction (VideoExtractor)**
   - Extract metadata using yt-dlp
   - Download video/audio content
   - Create organized folder structure

3. **Transcription (TranscriptExtractor)**
   - Load Whisper AI model (GPU/CPU)
   - Extract audio from video
   - Generate transcript with timestamps

4. **Comment Extraction (CommentExtractor)**
   - Initialize TikTok API with MS_TOKEN
   - Fetch comments and nested replies
   - Parse comment data structures

5. **Data Assembly**
   - Flatten all data into single JSON structure
   - Include video metadata, transcript, comments
   - Add processing timestamps

6. **Data Persistence (DataManager)**
   - Stream append to master JSON file
   - Cross-platform file locking
   - Duplicate URL tracking

7. **Resource Cleanup (ResourceManager)**
   - Memory cleanup after each video
   - Browser process termination
   - Temporary file removal

## Error Handling Strategy

- **Graceful Degradation**: Each component fails independently
- **Retry Logic**: Automatic retries for network operations
- **Resource Recovery**: Automatic cleanup on failures
- **Progress Preservation**: Partial results saved immediately
- **Duplicate Prevention**: URL tracking prevents reprocessing

This modular architecture ensures robustness, maintainability, and scalability for the TikTok data collection system.

