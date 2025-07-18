# 🎯 **TikTok URL Collector**

A Node.js tool that **collects TikTok video URLs** from hashtags, users, and trending pages. Perfect for gathering URLs for batch processing with your existing video scrapers.

## 🚀 **Setup Instructions (New System)**

### **1. Prerequisites**
```bash
# Install Node.js 16+ (if not installed)
# Download from: https://nodejs.org/

# Install Chrome/Chromium browser (required for Puppeteer)
# Ubuntu/Debian:
sudo apt update && sudo apt install -y chromium-browser

# Or install Chrome manually from: https://www.google.com/chrome/
```

### **2. Clone & Install**
```bash
# Clone or download this project
git clone <your-repo-url>
cd url_scraper

# Install dependencies
npm install
```

### **3. Test Installation**
```bash
# Quick test - collect 5 URLs from #funny hashtag
npm test

# Or run manually:
node url_collector.js hashtag funny -c 5 -f all
```

### **4. Ready to Use!**
```bash
# Collect 100 URLs from trending hashtag
node url_collector.js hashtag trending -c 100 -f txt

# Collect 50 URLs from a user profile  
node url_collector.js user zachking -c 50 -f json
```

---

## 📊 **What This Does**

✅ **Collects TikTok URLs** - Gathers video URLs, NOT metadata  
✅ **Multiple Sources** - Hashtags, user profiles, trending  
✅ **Multiple Output Formats** - JSON, CSV, TXT files  
✅ **Batch Processing Ready** - Perfect for feeding into other scrapers  
✅ **Anti-Detection** - Uses real browser with proper headers  
✅ **Scalable** - Can collect hundreds/thousands of URLs  

## 🎯 **Usage Examples**

### **Collect URLs from Hashtag**
```bash
node url_collector.js hashtag funny -c 100 -f all
# Output: 100 TikTok URLs from #funny hashtag
```

### **Collect URLs from User**
```bash
node url_collector.js user zachking -c 50 -f txt
# Output: 50 TikTok URLs from @zachking profile
```

### **Collect URLs from Trending**
```bash
node url_collector.js trending -c 200 -f json
# Output: 200 TikTok URLs from trending/for you page
```

### **Available Options**
- `-c, --count <number>` - Number of URLs to collect (default: 50)
- `-o, --output <directory>` - Output directory (default: output)
- `-f, --format <format>` - Output format: json, csv, txt, all
- `--headless` - Run browser in headless mode (default: true)

## 📁 **Output Files**

The tool generates clean URL lists:

### **TXT Format** (Perfect for other scrapers)
```
https://www.tiktok.com/@user1/video/7342262590606921006
https://www.tiktok.com/@user2/video/7488157305457102126
https://www.tiktok.com/@user3/video/7488724370928553258
```

### **JSON Format** (With metadata)
```json
[
  {
    "url": "https://www.tiktok.com/@user1/video/7342262590606921006",
    "source": "hashtag",
    "query": "funny",
    "collectedAt": "2025-07-18T20:51:14.824Z"
  }
]
```

### **CSV Format** (For spreadsheets)
```csv
TikTok URL,Source Type,Query/Source,Collected At
https://www.tiktok.com/@user1/video/7342262590606921006,hashtag,funny,2025-07-18T20:51:14.824Z
```

## 📝 **Real World Example**

Let's say you want 500 funny TikTok URLs for your video compilation:

```bash
# Step 1: Collect URLs
node url_collector.js hashtag funny -c 500 -f txt

# Step 2: Use the generated URL list with your existing scraper
# The output/tiktok_urls_[timestamp].txt file contains clean URLs
```

## 🔗 **Integration with Other Tools**

Perfect for feeding URLs into:
- yt-dlp for video downloads
- Your existing TikTok metadata scrapers
- Batch processing pipelines
- Video compilation workflows

## 📞 **Troubleshooting**

### **Common Issues:**

1. **"Browser launch failed"**
   ```bash
   # Install Chrome/Chromium
   sudo apt install chromium-browser
   ```

2. **"Waiting for selector failed"**
   - TikTok page structure changed or blocking
   - Try different hashtags or reduce count

3. **"Permission errors"**
   ```bash
   # Fix output directory permissions
   chmod 755 output/
   ```

4. **"Module not found"**
   ```bash
   # Reinstall dependencies
   rm -rf node_modules package-lock.json
   npm install
   ```

## ⚠️ **Important Notes**

1. **URL Collection Only** - This tool collects URLs, not video metadata
2. **Rate Limiting** - Built-in delays to avoid being blocked
3. **Browser Required** - Uses Puppeteer for realistic web browsing
4. **TikTok Changes** - Selectors may need updates if TikTok changes
5. **Legal Use** - Respect TikTok's terms of service

## 🎉 **Success Example**

```bash
$ npm test

📊 URL COLLECTION REPORT
══════════════════════════════════════════════════
✅ Total URLs Collected: 10
❌ Failed Requests: 0

📋 Source Breakdown:
  hashtag: 10 URLs

🔗 Sample URLs:
1. https://www.tiktok.com/@user1/video/7342262590606921006 (from hashtag: funny)
2. https://www.tiktok.com/@user2/video/7488157305457102126 (from hashtag: funny)
...

✅ URL collection completed successfully!
```

---

**🎯 Ready to collect TikTok URLs for your projects!**

Run: `node url_collector.js hashtag trending -c 100 -f txt`