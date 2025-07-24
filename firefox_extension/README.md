# TikTok URL Collector Firefox Extension

Automatically captures TikTok video URLs and adds them to `urls.txt` for use with the TikTok scraper.

## Installation

1. **Install the native messaging host:**
   ```bash
   cd firefox_extension
   ./install_native_host.sh
   ```

2. **Load the extension in Firefox:**
   - Open Firefox
   - Go to `about:debugging`
   - Click "This Firefox"
   - Click "Load Temporary Add-on"
   - Select `manifest.json` from the `firefox_extension` directory

## How it Works

- **Automatic Detection**: When you visit a TikTok video page, the extension automatically detects the URL and adds it to `urls.txt`
- **Visual Feedback**: Shows notifications when URLs are captured
- **Duplicate Prevention**: Won't add the same URL twice
- **Manual Capture**: Click the extension icon to manually add the current TikTok video URL

## Features

- Detects TikTok video URLs (format: `https://www.tiktok.com/@username/video/123456789`)
- Automatically adds URLs to your existing `urls.txt` file
- Shows success/error notifications
- Popup interface for manual URL capture
- Prevents duplicate entries

## Files

- `manifest.json` - Extension manifest
- `background.js` - Background script handling messaging
- `content.js` - Content script for TikTok page detection
- `popup.html/js` - Extension popup interface
- `native_host.py` - Native messaging host for file writing
- `tiktok_url_collector.json` - Native host manifest
- `install_native_host.sh` - Installation script

## Usage with TikTok Scraper

Once URLs are collected in `urls.txt`, use your existing scraper command:

```bash
./robust_master_downloader.py --from-file urls.txt --mp3 --batch-size 10 --delay 2 --max-comments 10 --whisper
```