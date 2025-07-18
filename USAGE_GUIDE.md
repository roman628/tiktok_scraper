# Robust TikTok Downloader - Usage Guide

## ✅ **All Contingencies Implemented**

### **1. Duplicate Detection & Skipping**
- ✅ **Automatic detection** of already processed URLs from `master2.json`
- ✅ **Smart skipping** - won't redownload existing videos
- ✅ **Progress reporting** - shows how many duplicates were skipped

### **2. MS_TOKEN Management**
- ✅ **Interactive prompting** for MS_TOKEN on startup
- ✅ **Multiple input methods**: argument, environment variable, or interactive
- ✅ **Token validation** before starting
- ✅ **Automatic expiry detection** and re-prompting
- ✅ **Graceful fallback** to video-only mode if token fails

### **3. Resume Functionality**
- ✅ **Progress tracking** in `download_progress.json`
- ✅ **Automatic resume** - skips already processed URLs
- ✅ **Failed URL tracking** - retries failed downloads on restart
- ✅ **Interrupt recovery** - saves progress on Ctrl+C

### **4. Robust Error Handling**
- ✅ **Network timeout recovery**
- ✅ **API rate limit handling**
- ✅ **Partial failure recovery** - continues processing other URLs
- ✅ **Batch saving** - regular progress saves every N videos

---

## 🚀 **Usage Examples**

### **Basic Usage (with all safety features)**
```bash
# Process all URLs with interactive MS_TOKEN input
./robust_master_downloader.py --from-file urls.txt --mp3

# Skip comment extraction (faster)
echo "skip" | ./robust_master_downloader.py --from-file urls.txt --mp3
```

### **Advanced Options**
```bash
# With custom batch size and rate limiting
./robust_master_downloader.py --from-file urls.txt --mp3 \
    --batch-size 5 --delay 3 --max-comments 15

# Using environment variable for MS_TOKEN
export TIKTOK_MS_TOKEN="your_token_here"
./robust_master_downloader.py --from-file urls.txt --mp3

# Force redownload everything (ignore duplicates)
./robust_master_downloader.py --from-file urls.txt --mp3 --force-redownload

# Clean slate start
./robust_master_downloader.py --from-file urls.txt --mp3 --clean-progress
```

### **Testing & Development**
```bash
# Test on small sample
./robust_master_downloader.py --from-file urls.txt --mp3 --limit 5

# Single URL with debugging
./robust_master_downloader.py "https://www.tiktok.com/@user/video/123" --mp3
```

---

## 🔑 **MS_TOKEN Setup Instructions**

1. **Open TikTok in your browser** and log in
2. **Open Developer Tools** (F12 or Cmd+Option+I)
3. **Go to Application tab** (Chrome) or Storage tab (Firefox)
4. **Find Cookies** → `tiktok.com` → **Look for `msToken`**
5. **Copy the token value** (long string)
6. **Paste when prompted** or set as environment variable

### **Environment Variable Method**
```bash
export TIKTOK_MS_TOKEN="E5YjZRblKUKYUznFcdR_Q1REZ79PHQ4C1HU1lOXytVIXxhE..."
./robust_master_downloader.py --from-file urls.txt --mp3
```

---

## 📊 **Progress & Recovery Features**

### **Automatic Resume**
If the script is interrupted or fails:
```bash
# Simply run the same command again
./robust_master_downloader.py --from-file urls.txt --mp3
# It will automatically skip already processed URLs
```

### **Progress Files**
- **`master2.json`** - Contains all successfully processed videos with metadata
- **`download_progress.json`** - Tracks current session progress and failed URLs

### **Clean Start**
```bash
# Remove progress and start fresh
./robust_master_downloader.py --from-file urls.txt --mp3 --clean-progress
```

---

## 🚨 **Error Scenarios & Handling**

### **MS_TOKEN Expires During Processing**
- ✅ **Auto-detection** of expired token
- ✅ **Interactive re-prompting** for new token
- ✅ **Graceful fallback** to video-only if token not provided
- ✅ **Seamless continuation** of processing

### **Network Interruptions**
- ✅ **Individual URL failures** don't stop the batch
- ✅ **Progress saved** every 5 videos
- ✅ **Resume capability** on restart

### **Disk Space Issues**
- ✅ **Clear error messages**
- ✅ **Progress preservation** - can resume after freeing space

### **Rate Limiting**
- ✅ **Configurable delays** between requests (`--delay N`)
- ✅ **Respectful default** timing (2 seconds)

---

## 🎯 **Production Usage Recommendations**

### **For Large Batches (100+ URLs)**
```bash
./robust_master_downloader.py --from-file urls.txt --mp3 \
    --batch-size 10 \
    --delay 3 \
    --max-comments 10
```

### **For Maximum Speed (no comments)**
```bash
echo "skip" | ./robust_master_downloader.py --from-file urls.txt --mp3 \
    --batch-size 20 \
    --delay 1
```

### **For Maximum Data Collection**
```bash
./robust_master_downloader.py --from-file urls.txt \
    --max-comments 25 \
    --whisper \
    --batch-size 5 \
    --delay 4
```

---

## 📈 **Output & Results**

### **Files Created**
- **`downloads/`** - Individual video folders with files
- **`master2.json`** - Unified database of all videos + metadata + comments
- **`download_progress.json`** - Session progress and recovery data

### **Master2.json Structure**
```json
[
  {
    "title": "Video Title",
    "url": "https://www.tiktok.com/@user/video/123",
    "uploader": "@username",
    "view_count": 1000000,
    "like_count": 50000,
    "comment_count": 1500,
    "subtitle_transcription": "Auto-generated captions...",
    "custom_transcription": "Whisper AI transcription...",
    "top_comments": [
      {
        "comment_id": "123456789",
        "username": "commenter",
        "comment_text": "Great video!",
        "like_count": 25,
        "timestamp": 1642123456
      }
    ],
    "comments_extracted": true,
    "downloaded_at": "2024-01-01T12:00:00",
    "folder": "downloads/Video Title/"
  }
]
```

---

## 🔧 **Troubleshooting**

### **Script Won't Start**
```bash
# Check permissions
chmod +x robust_master_downloader.py

# Check Python environment
./venv/bin/python --version
```

### **Token Issues**
```bash
# Test token validation
./venv/bin/python test_token_validation.py

# Check environment variable
echo $TIKTOK_MS_TOKEN
```

### **Progress Issues**
```bash
# Check progress file
cat download_progress.json

# Clean and restart
./robust_master_downloader.py --clean-progress --from-file urls.txt --mp3
```

---

## ✨ **Key Benefits**

1. **🛡️ Bulletproof** - Handles all common failure scenarios
2. **⚡ Efficient** - Skips duplicates automatically
3. **🔄 Resumable** - Never lose progress
4. **📊 Complete** - Videos + metadata + comments in one file
5. **🎛️ Configurable** - Tune for speed vs. data completeness
6. **🤖 Unattended** - Can run overnight safely

**Ready for production use on your 807 URLs!** 🚀