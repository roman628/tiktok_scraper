# TikTok Scraper Project

This project is designed to download and process TikTok videos.

## Main Script

The main script for this project is `robust_master_downloader.py`. It can be run with specific arguments, or with no arguments to use the default settings.

### Default Settings

When run with no arguments, the script will:
- Read URLs from `urls.txt`
- Download audio only as MP3
- Use a batch size of 10
- Have a delay of 2 seconds between downloads
- Download a maximum of 10 comments per video
- Use whisper for transcription

### Usage

To run with default settings:
```bash
./robust_master_downloader.py
```

To run with custom settings, use the available flags. For example:
```bash
./robust_master_downloader.py --from-file my_urls.txt --quality best
```

## Maintenance and Utility Scripts

All other scripts are located in the `scripts` directory, organized by category.

To run any of these scripts, use the `ttools.py` interactive script:
```bash
python ttools.py
```
This will display a list of available scripts and allow you to choose which one to run.

### Script Categories

- **analysis**: Scripts for analyzing the downloaded data.
- **cleanup**: Scripts for cleaning and maintaining the data.
- **collection**: Scripts for collecting data from TikTok.
- **utils**: Utility scripts for various tasks.
