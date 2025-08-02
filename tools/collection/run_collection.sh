#!/bin/bash

# TikTok Collection Scripts - Automation Script
# Handles video downloading, URL collection, and content harvesting

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DATA_FILE="$PROJECT_ROOT/master2.json"
URLS_FILE="$PROJECT_ROOT/urls.txt"
OUTPUT_DIR="$PROJECT_ROOT/output"
DOWNLOADS_DIR="$PROJECT_ROOT/downloads"
TEMP_DOWNLOADS_DIR="$PROJECT_ROOT/temp_downloads"
LOG_FILE="$PROJECT_ROOT/collection.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    # Check if required Python packages are available
    python -c "import json, requests" 2>/dev/null || {
        error "Missing Python dependencies. Please install: pip install requests"
        exit 1
    }
    
    # Check for Node.js if URL collector is available
    if [[ -f "$PROJECT_ROOT/broken/url_collector.js" ]]; then
        node --version >/dev/null 2>&1 || {
            warning "Node.js not found. URL collector will not be available."
        }
    fi
    
    success "Dependencies check passed"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$DOWNLOADS_DIR"
    mkdir -p "$TEMP_DOWNLOADS_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"
    
    success "Directories ready"
}

# Collect TikTok URLs
collect_urls() {
    local hashtag="${1:-funny}"
    local count="${2:-50}"
    local format="${3:-txt}"
    
    log "Collecting TikTok URLs..."
    log "Hashtag: #$hashtag"
    log "Count: $count"
    log "Format: $format"
    
    if [[ ! -f "$SCRIPT_DIR/tiktok_url_collector.py" ]]; then
        error "URL collector script not found: $SCRIPT_DIR/tiktok_url_collector.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python tiktok_url_collector.py \
        --hashtag "$hashtag" \
        --count "$count" \
        --format "$format" \
        --output "$URLS_FILE" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "URL collection completed"
        if [[ -f "$URLS_FILE" ]]; then
            local url_count=$(wc -l < "$URLS_FILE")
            log "Collected $url_count URLs"
        fi
        return 0
    else
        error "URL collection failed"
        return 1
    fi
}

# Harvest URLs using browser automation
harvest_urls() {
    local method="${1:-selenium}"
    local headless="${2:-true}"
    
    log "Harvesting URLs using browser automation..."
    log "Method: $method"
    log "Headless: $headless"
    
    if [[ ! -f "$SCRIPT_DIR/url_harvester.py" ]]; then
        error "URL harvester script not found: $SCRIPT_DIR/url_harvester.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python url_harvester.py \
        --method "$method" \
        --headless "$headless" \
        --output "$URLS_FILE" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "URL harvesting completed"
        return 0
    else
        error "URL harvesting failed"
        return 1
    fi
}

# Download TikTok videos
download_videos() {
    local max_videos="${1:-10}"
    local quality="${2:-best}"
    local with_comments="${3:-true}"
    
    log "Downloading TikTok videos..."
    log "Max videos: $max_videos"
    log "Quality: $quality"
    log "Include comments: $with_comments"
    
    # Check if URLs file exists
    if [[ ! -f "$URLS_FILE" ]]; then
        error "URLs file not found: $URLS_FILE"
        error "Run URL collection first"
        return 1
    fi
    
    # Use the appropriate downloader
    local downloader_script=""
    if [[ -f "$SCRIPT_DIR/tiktok_downloader.py" ]]; then
        downloader_script="$SCRIPT_DIR/tiktok_downloader.py"
    elif [[ -f "$SCRIPT_DIR/tiktok_scraper.py" ]]; then
        downloader_script="$SCRIPT_DIR/tiktok_scraper.py"
    else
        error "No downloader script found"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python "$(basename "$downloader_script")" \
        --input "$URLS_FILE" \
        --output "$DATA_FILE" \
        --max-videos "$max_videos" \
        --quality "$quality" \
        --downloads-dir "$DOWNLOADS_DIR" \
        --temp-dir "$TEMP_DOWNLOADS_DIR" \
        $([ "$with_comments" = "true" ] && echo "--comments") \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Video downloading completed"
        return 0
    else
        error "Video downloading failed"
        return 1
    fi
}

# Run master download and comment extraction
master_download() {
    local batch_size="${1:-5}"
    local delay="${2:-2}"
    
    log "Running master download with comment extraction..."
    log "Batch size: $batch_size"
    log "Delay between batches: ${delay}s"
    
    if [[ ! -f "$SCRIPT_DIR/master_download_and_comment.py" ]]; then
        error "Master download script not found: $SCRIPT_DIR/master_download_and_comment.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python master_download_and_comment.py \
        --batch-size "$batch_size" \
        --delay "$delay" \
        --output "$DATA_FILE" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Master download completed"
        return 0
    else
        error "Master download failed"
        return 1
    fi
}

# Update comments for existing videos
update_comments() {
    local max_videos="${1:-100}"
    
    log "Updating comments for existing videos..."
    log "Max videos to update: $max_videos"
    
    if [[ ! -f "$SCRIPT_DIR/update_comments_v2.py" ]]; then
        error "Comment update script not found: $SCRIPT_DIR/update_comments_v2.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python update_comments_v2.py \
        --input "$DATA_FILE" \
        --max-videos "$max_videos" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Comment update completed"
        return 0
    else
        error "Comment update failed"
        return 1
    fi
}

# Run browser harvester
browser_harvest() {
    local browser="${1:-chrome}"
    local timeout="${2:-30}"
    
    log "Running browser-based harvesting..."
    log "Browser: $browser"
    log "Timeout: ${timeout}s"
    
    if [[ ! -f "$SCRIPT_DIR/browser_harvester.py" ]]; then
        error "Browser harvester script not found: $SCRIPT_DIR/browser_harvester.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python browser_harvester.py \
        --browser "$browser" \
        --timeout "$timeout" \
        --output "$URLS_FILE" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Browser harvesting completed"
        return 0
    else
        error "Browser harvesting failed"
        return 1
    fi
}

# Quick collection workflow
quick_collect() {
    local hashtag="${1:-trending}"
    local count="${2:-20}"
    
    log "Running quick collection workflow..."
    
    setup_directories
    
    # Step 1: Collect URLs
    if collect_urls "$hashtag" "$count" "txt"; then
        success "URLs collected successfully"
    else
        error "URL collection failed, trying browser harvest..."
        if ! browser_harvest "chrome" 30; then
            error "All URL collection methods failed"
            return 1
        fi
    fi
    
    # Step 2: Download videos
    if download_videos 10 "best" true; then
        success "Videos downloaded successfully"
    else
        error "Video download failed"
        return 1
    fi
    
    # Step 3: Update comments if needed
    if update_comments 10; then
        success "Comments updated successfully"
    else
        warning "Comment update failed, but videos were downloaded"
    fi
    
    success "Quick collection completed"
    show_collection_stats
}

# Full collection workflow
full_collect() {
    local hashtag="${1:-viral}"
    local count="${2:-100}"
    local batch_size="${3:-10}"
    
    log "Running full collection workflow..."
    
    setup_directories
    
    # Step 1: Collect URLs from multiple sources
    log "Phase 1: URL Collection"
    collect_urls "$hashtag" "$count" "txt"
    
    # Try browser harvest as backup
    if [[ ! -f "$URLS_FILE" ]] || [[ $(wc -l < "$URLS_FILE") -lt 10 ]]; then
        warning "Limited URLs collected, trying browser harvest..."
        browser_harvest "chrome" 45
    fi
    
    # Step 2: Download videos in batches
    log "Phase 2: Video Download"
    if download_videos "$count" "best" true; then
        success "Initial download completed"
    else
        warning "Initial download had issues, trying master download..."
        master_download "$batch_size" 3
    fi
    
    # Step 3: Update comments for all videos
    log "Phase 3: Comment Updates"
    update_comments "$count"
    
    # Step 4: Harvest additional content
    log "Phase 4: Additional Harvesting" 
    harvest_urls "selenium" true
    
    success "Full collection completed"
    show_collection_stats
}

# Show collection statistics
show_collection_stats() {
    log "Generating collection statistics..."
    
    echo
    echo "=== COLLECTION STATISTICS ==="
    
    # URLs collected
    if [[ -f "$URLS_FILE" ]]; then
        local url_count=$(wc -l < "$URLS_FILE" 2>/dev/null || echo "0")
        echo "📋 URLs collected: $url_count"
    else
        echo "📋 URLs collected: 0 (file not found)"
    fi
    
    # Videos in master2.json
    if [[ -f "$DATA_FILE" ]]; then
        local video_count=$(python -c "
import json
try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    print(len(data))
except:
    print(0)
" 2>/dev/null || echo "0")
        echo "🎥 Videos in database: $video_count"
        
        # Videos with comments
        local with_comments=$(python -c "
import json
try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    count = sum(1 for v in data if v.get('top_comments'))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")
        echo "💬 Videos with comments: $with_comments"
        
        # Videos with transcriptions
        local with_transcription=$(python -c "
import json
try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    count = sum(1 for v in data if v.get('whisper_transcription'))
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")
        echo "📝 Videos with transcription: $with_transcription"
    else
        echo "🎥 Videos in database: 0 (file not found)"
    fi
    
    # Downloaded files
    if [[ -d "$DOWNLOADS_DIR" ]]; then
        local downloaded_files=$(find "$DOWNLOADS_DIR" -name "*.mp4" -o -name "*.webm" | wc -l 2>/dev/null || echo "0")
        echo "💾 Downloaded video files: $downloaded_files"
    else
        echo "💾 Downloaded video files: 0 (directory not found)"
    fi
    
    # Disk usage
    if [[ -d "$DOWNLOADS_DIR" ]]; then
        local disk_usage=$(du -sh "$DOWNLOADS_DIR" 2>/dev/null | cut -f1 || echo "0B")
        echo "💽 Downloads disk usage: $disk_usage"
    fi
    
    echo "📄 Log file: $LOG_FILE"
    echo "============================="
}

# Clean old downloads and temporary files
clean_downloads() {
    local days="${1:-7}"
    local keep_master="${2:-true}"
    
    log "Cleaning downloads older than $days days..."
    log "Keep master2.json: $keep_master"
    
    # Clean temp downloads
    if [[ -d "$TEMP_DOWNLOADS_DIR" ]]; then
        find "$TEMP_DOWNLOADS_DIR" -type f -mtime +$days -delete
        success "Temp downloads cleaned"
    fi
    
    # Clean old video files (be careful!)
    if [[ -d "$DOWNLOADS_DIR" ]] && [[ "$keep_master" != "true" ]]; then
        find "$DOWNLOADS_DIR" -name "*.mp4" -type f -mtime +$days -delete
        find "$DOWNLOADS_DIR" -name "*.webm" -type f -mtime +$days -delete
        success "Old video files cleaned"
    fi
    
    # Clean output logs
    if [[ -d "$OUTPUT_DIR" ]]; then
        find "$OUTPUT_DIR" -name "*.log" -type f -mtime +$days -delete
        find "$OUTPUT_DIR" -name "url_collection_log*.txt" -type f -mtime +$days -delete
        success "Old logs cleaned"
    fi
}

# Show usage
show_usage() {
    cat << EOF
TikTok Collection Scripts

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    collect-urls <hashtag> [count] [format]
        Collect TikTok URLs from hashtag
        hashtag: Hashtag to search (default: funny)
        count: Number of URLs (default: 50)
        format: Output format txt/json (default: txt)

    harvest-urls [method] [headless]
        Harvest URLs using browser automation
        method: selenium/playwright (default: selenium)
        headless: true/false (default: true)

    download [max_videos] [quality] [comments]
        Download videos from collected URLs
        max_videos: Maximum videos to download (default: 10)
        quality: Video quality (default: best)
        comments: Include comments true/false (default: true)

    master-download [batch_size] [delay]
        Run master download with comments
        batch_size: Videos per batch (default: 5)
        delay: Delay between batches in seconds (default: 2)

    update-comments [max_videos]
        Update comments for existing videos
        max_videos: Maximum videos to update (default: 100)

    browser-harvest [browser] [timeout]
        Browser-based URL harvesting
        browser: chrome/firefox (default: chrome)
        timeout: Timeout in seconds (default: 30)

    quick [hashtag] [count]
        Quick collection workflow
        hashtag: Target hashtag (default: trending)
        count: Number of URLs (default: 20)

    full [hashtag] [count] [batch_size]
        Full collection workflow
        hashtag: Target hashtag (default: viral)
        count: Number of URLs (default: 100)
        batch_size: Download batch size (default: 10)

    stats
        Show collection statistics

    clean [days] [keep_master]
        Clean old downloads and files
        days: Files older than X days (default: 7)
        keep_master: Keep master2.json (default: true)

Examples:
    $0 collect-urls funny 100 txt
    $0 download 20 best true
    $0 quick trending 30
    $0 full viral 200 15
    $0 stats
    $0 clean 14 true

Output Files:
    - URLs: $URLS_FILE
    - Video Data: $DATA_FILE
    - Downloads: $DOWNLOADS_DIR
    - Logs: $LOG_FILE

EOF
}

# Main script logic
main() {
    # Create log file directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting TikTok Collection Scripts"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "collect-urls")
            setup_directories
            collect_urls "${2:-funny}" "${3:-50}" "${4:-txt}"
            ;;
        "harvest-urls")
            setup_directories
            harvest_urls "${2:-selenium}" "${3:-true}"
            ;;
        "download")
            setup_directories
            download_videos "${2:-10}" "${3:-best}" "${4:-true}"
            ;;
        "master-download")
            setup_directories
            master_download "${2:-5}" "${3:-2}"
            ;;
        "update-comments")
            setup_directories
            update_comments "${2:-100}"
            ;;
        "browser-harvest")
            setup_directories
            browser_harvest "${2:-chrome}" "${3:-30}"
            ;;
        "quick")
            quick_collect "${2:-trending}" "${3:-20}"
            ;;
        "full")
            full_collect "${2:-viral}" "${3:-100}" "${4:-10}"
            ;;
        "stats")
            show_collection_stats
            ;;
        "clean")
            clean_downloads "${2:-7}" "${3:-true}"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Showing collection statistics..."
            show_collection_stats
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Collection scripts completed"
}

# Run main function with all arguments
main "$@"