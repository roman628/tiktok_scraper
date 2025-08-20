# TikTok URL Collector Firefox Extension

Automatically captures TikTok video URLs and saves them to `data/urls.txt`.

**NOTE**: To get this to work on the for you page, open the comments and scroll with comments open. I don't know why this works but it sets the url to the share link, so do this when scrolling the fyp. 

## Files

- `manifest.json` - Extension configuration file
- `background.js` - Handles message passing and server communication
- `content.js` - Detects TikTok video URLs on web pages
- `popup.html` - Extension popup interface
- `popup.js` - Popup functionality and server settings management
- `url_server.py` - Python server that receives URLs and saves to data/urls.txt
- `start_server.sh` - Script to start the URL collection server

## Installation

1. **Load the extension in Firefox:**
   - Open Firefox
   - Go to `about:debugging`
   - Click "This Firefox"
   - Click "Load Temporary Add-on"
   - Select `manifest.json` from this directory

2. **Start the local server:**
   ```bash
   ./start_server.sh
   ```

The extension will automatically detect TikTok video URLs and send them to the server, which saves them to `data/urls.txt`.

## Server Settings

Click the extension icon and expand "Server Settings" to:
- Change the server URL (default: http://localhost)
- Change the server port (default: 8765)
- Test the connection
- Save settings for future use