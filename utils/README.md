# TikTok Data Collection - Utility Modules

This directory contains utility and helper modules that provide infrastructure support for the TikTok data collection pipeline. These modules handle system-level operations, resource management, and UI components.

## Module Overview (7 Total)

### 📊 collector_registry.py
**Worker registry and configuration management**
- Centralized registry for collector instances across processes
- Configuration dataclass for collector settings
- Thread-safe singleton pattern
- Worker state tracking and management
- Shared configuration distribution

### 💾 data_manager.py
**JSON operations and data persistence**
- Memory-efficient streaming JSON append
- Cross-platform file locking (`FileLock` class)
- Duplicate URL detection and filtering
- Automatic JSON repair for corrupted files
- Atomic write operations
- Progress tracking and resumption support

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
- Per-worker progress tracking with panels
- Real-time log streaming with color coding
- Flash animations for completed URLs (3x green flash)
- TTY detection with fallback to simple mode
- Visual feedback (grey/blue/green/red borders)
- Automatic layout adjustment based on terminal width

### 🧹 resource_manager.py
**System resource and memory management**
- Memory usage monitoring with automatic cleanup
- Browser process killing (for comment extraction)
- Signal handler registration for graceful shutdown
- Directory and file cleanup utilities
- Process tree management
- Forced exit capabilities

### 🛑 shutdown_manager.py
**Centralized graceful shutdown handling**
- Unified signal handling across processes
- Cleanup handler registration with timeout protection
- Protected sections for critical operations
- Double Ctrl+C for forced termination
- Supports multiprocessing architecture
- Thread-safe shutdown event management

### 📈 worker_progress.py
**Progress tracking for worker processes**
- 6 weighted stages with percentage calculations:
  - Validating (0-5%): URL validation
  - Downloading (5-35%): Video/audio download
  - Metadata (35-45%): Metadata extraction
  - Transcribing (45-85%): Whisper transcription
  - Comments (85-95%): Comment extraction
  - Saving (95-100%): Save to JSON
- Granular progress reporting within each stage
- Multiprocessing queue communication
- Helper methods for common operations

## Usage

These utility modules are imported by the main `collector.py` script and core modules in the `src/` directory:

```python
from utils.data_manager import DataManager
from utils.device_manager import DeviceManager
from utils.display_manager import create_display
from utils.resource_manager import ResourceManager
from utils.shutdown_manager import shutdown_manager
from utils.worker_progress import WorkerProgress
from utils.collector_registry import CollectorRegistry, CollectorConfig

# Example: Setup display for multiprocessing
display = create_display(
    num_workers=4,
    display_mode="rich",
    progress_queue=queue
)
display.start()

# Example: Check GPU availability
device_manager = DeviceManager()
best_device = device_manager.get_best_device(force_cpu=False)
print(f"Using device: {best_device}")

# Example: Register shutdown handlers
shutdown_manager.register_signal_handlers(force_exit_on_double=True)
shutdown_manager.register_cleanup_handler(cleanup_function)
```

## Key Features

### Cross-Platform Support
All utilities are designed to work seamlessly across Windows, macOS, and Linux with platform-specific optimizations.

### Multiprocessing Safe
These modules are built to handle Python's multiprocessing quirks, with proper queue communication, shared state management, and process synchronization.

### Resource Efficiency
- Memory monitoring prevents OOM errors
- Automatic cleanup of temporary files
- Proper process termination
- File locking prevents corruption

### Rich UI Experience
The display manager provides a professional terminal UI that adapts to different terminal sizes and capabilities, with fallback to simple output for non-TTY environments.

### Graceful Shutdown
Comprehensive shutdown handling ensures data integrity and proper cleanup even when interrupted, with protection for critical operations.

## Dependencies

- `rich`: Terminal UI components
- `psutil`: System resource monitoring
- `filelock`: Cross-platform file locking
- Standard library: `multiprocessing`, `threading`, `signal`, `queue`

## Testing

Test the display system:
```bash
python tests/test_display_visual.py --workers 4 --urls 20
```

## Architecture Notes

These utility modules follow a separation of concerns principle:
- **Utils**: Infrastructure, system operations, UI (this directory)
- **Src**: Core business logic, data extraction, processing

This separation makes the codebase more maintainable and allows utilities to be reused across different components without circular dependencies.