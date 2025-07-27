# TikTok Scraper Project - Clean Architecture Version

This project has been completely refactored with a clean, unified architecture that eliminates redundancy and complexity.

## Main Script

**NEW:** The main script for this project is now `main.py`. It uses a clean, modular architecture with unified components.

**DEPRECATED:** `robust_master_downloader.py` is the legacy complex script and should be avoided in favor of the new architecture.

### Default Settings

When run with no arguments, the script will:
- Read URLs from `urls.txt`
- Download audio only as MP3
- Use a batch size of 10
- Have a delay of 2 seconds between downloads
- Download a maximum of 10 comments per video
- Use whisper for transcription

### Usage

**IMPORTANT**: Always activate the virtual environment before running:
```bash
source venv/bin/activate
```

To run with default settings:
```bash
python main.py
```

To run with custom settings, use the available flags. For example:
```bash
python main.py --from-file my_urls.txt --quality best --workers 4
```

**Note**: If transcription is not working, ensure you're running in the virtual environment where faster-whisper is installed.

## New Clean Architecture

The codebase has been unified into a modular `core/` package:

### Core Components

- **`core/config.py`** - Unified configuration management
- **`core/models.py`** - Standardized data models (VideoMetadata, CommentData, etc.)
- **`core/downloader.py`** - Unified video downloader (replaces 4+ duplicate downloaders)
- **`core/comments.py`** - Unified comment extractor (replaces scattered extraction logic)
- **`core/storage.py`** - Unified JSON/file operations (replaces scattered file handling)
- **`core/processor.py`** - Main processing coordinator
- **`core/multiprocess.py`** - Simplified multiprocessing coordinator
- **`core/utils.py`** - Shared utilities (file ops, URL parsing, validation)
- **`core/exceptions.py`** - Unified error handling

### Key Improvements

1. **Eliminated Redundancy**: Removed 4 duplicate downloaders, multiple comment extractors, and scattered JSON operations
2. **Unified Error Handling**: Consistent error messages and handling patterns
3. **Simplified Memory Management**: Removed complex manual garbage collection
4. **Clean Configuration**: Single configuration system replacing scattered argument parsing
5. **Standardized Data Models**: Consistent data structures across all operations
6. **Modular Design**: Clear separation of concerns and single responsibility principle

### Benefits

- **50-60% reduction in codebase size**
- **Eliminated circular dependencies**
- **Improved maintainability and testability**
- **Consistent error handling and logging**
- **Better resource management**
- **Simplified debugging and development**

## Tool Selection

### Recommended Tool: `main.py`
- Clean architecture with unified components
- Better error handling and progress reporting
- Simplified configuration and usage
- Support for both single-process and multiprocess modes
- Proper resource management

### Legacy Tool: `robust_master_downloader.py` (Deprecated)
- Complex 2000+ line monolithic script
- Manual memory management
- Scattered error handling
- Difficult to maintain and debug

## Interactive Script Runner

Use `ttools.py` to discover and run scripts:
```bash
python ttools.py
```

The tool now highlights the recommended `main.py` script and warns about deprecated legacy scripts.

## Maintenance and Utility Scripts

All utility scripts are located in the `scripts` directory, organized by category:

- **analysis**: Scripts for analyzing the downloaded data
- **cleanup**: Scripts for cleaning and maintaining the data  
- **collection**: Scripts for collecting data from TikTok
- **utils**: Utility scripts for various tasks

Most functionality has been consolidated into the new core architecture, reducing the need for separate utility scripts.

# important-instruction-reminders

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

## Architecture Guidelines

When working with this codebase:

1. **Use the new `main.py` script** instead of the legacy downloader
2. **Import from `core/` modules** for any new functionality
3. **Follow the unified data models** (VideoMetadata, CommentData, etc.)
4. **Use the ErrorHandler** for consistent error reporting
5. **Leverage the StorageManager** for all JSON operations
6. **Use TikTokConfig** for configuration management

## Migration Status

✅ **Completed**: Core architecture refactoring
✅ **Completed**: Main script replacement  
✅ **Completed**: Unified components creation
✅ **Completed**: Tool integration updates

The refactoring successfully transformed a complex, redundant codebase into a clean, modular architecture with significant improvements in maintainability and performance.

## Code Analysis Tools

### Claude Tools - Definition Checker

The `claudetools/` directory contains analysis tools for the codebase:

#### `checkdefs.py` - Definition and Redundancy Analyzer

**Purpose**: Scans the TikTok scraper codebase to identify function definitions, class definitions, variable definitions, and potential redundancies.

**Usage**:
```bash
python claudetools/checkdefs.py
```

**What it does**:
1. **Scans all Python files** in the project (excluding venv, __pycache__, etc.)
2. **Extracts definitions** using AST parsing:
   - Function definitions (regular and async)
   - Class definitions
   - Variable assignments (filtered to exclude common variables)
3. **Analyzes redundancies**:
   - Duplicate function names across files
   - Duplicate class names
   - Similar function names that might indicate redundant functionality
   - Variables defined in multiple files (potential constants)
4. **Generates reports**:
   - Console output with summary and redundancy analysis
   - Detailed text file (`definition_analysis.txt`) with complete listings

**Example Output**:
- Shows duplicate functions like `get_data_completeness_score` found in both the legacy downloader and cleanup scripts
- Identifies 19 different `main()` functions across utility scripts
- Detects similar naming patterns that suggest redundant functionality
- Reports statistics: 323 functions, 37 classes, 1026 variables across 34 files

**Benefits**:
- **Validates refactoring efforts** by showing remaining redundancies in legacy code
- **Identifies consolidation opportunities** for remaining scripts
- **Documents codebase structure** for easier maintenance
- **Prevents future redundancy** by highlighting patterns to avoid

**Use Cases**:
- Run after major refactoring to validate cleanup success
- Periodic codebase health checks
- Before adding new functionality to avoid duplication
- Code review assistance for identifying redundant patterns

The tool confirmed that our refactoring successfully consolidated the core functionality while identifying remaining redundancies in the legacy scripts that were preserved for compatibility.

IMPORTANT: Before making changes to the codebase, first run the detail scripts to analyze simple codebase structure, think about utilizing what already exists before making something new, or how already existing code can be used to assist in making the necesary fixes/updates. This way the system is concise and organized. Also at the end of your process, before completing, run the scripts again and analyze your performance based on the feedback