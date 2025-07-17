# TikTok Scraper

Enhanced TikTok video downloader with metadata extraction, transcription, and batch processing.

## Installation

```bash
pip install yt-dlp faster-whisper numpy
```

Optional for GPU transcription:
```bash
pip install nvidia-cudnn-cu12 nvidia-cublas-cu12
```

## Quick Start

**Single video:**
```bash
python tiktok_scraper.py "https://www.tiktok.com/@user/video/123"
```

**Batch processing:**
```bash
# Create urls.txt with one URL per line
python tiktok_scraper.py --from-file urls.txt --append master.json --clean
```

**With transcription:**
```bash
python tiktok_scraper.py --from-file urls.txt --whisper --append master.json --clean
```

## Features

- Download videos with comprehensive metadata (views, likes, comments, etc.)
- Extract TikTok's built-in subtitles  
- Optional AI transcription with faster-whisper
- Batch processing from URL files
- Master JSON compilation for data analysis
- Cross-platform support (Windows, macOS, Linux)

## Usage

Run `python tiktok_scraper.py -h` for all options.

**Key flags:**
- `--from-file urls.txt` - Batch process URLs from file
- `--whisper` - Add AI transcription  
- `--append master.json` - Compile all metadata to one file
- `--clean` - Remove individual folders (keep only master JSON)
- `--mp3` - Download audio only
- `--diagnose` - Check system setup

## Example Workflow

1. Create `urls.txt` with TikTok URLs
2. Run: `python tiktok_scraper.py --from-file urls.txt --whisper --append data.json --clean`
3. Result: `data.json` contains all video metadata and transcriptions