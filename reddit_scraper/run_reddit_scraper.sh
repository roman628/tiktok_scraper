#!/bin/bash

# Reddit Scraper - Automation Script
# Handles Reddit user profiling, subreddit discovery, and batch processing

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIKTOK_DATA="$PROJECT_ROOT/master2.json"
OUTPUT_DIR="$SCRIPT_DIR/results"
LOG_FILE="$SCRIPT_DIR/reddit_scraper.log"
VENV_PATH="$SCRIPT_DIR/reddit_env"
CONFIG_FILE="$SCRIPT_DIR/config.env"

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

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        log "Loading configuration from: $CONFIG_FILE"
        source "$CONFIG_FILE"
    else
        warning "Configuration file not found: $CONFIG_FILE"
        warning "Please create config.env with Reddit API credentials"
        
        # Check for environment variables
        if [[ -z "$REDDIT_CLIENT_ID" ]] || [[ -z "$REDDIT_CLIENT_SECRET" ]]; then
            error "Reddit API credentials not found"
            error "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables"
            error "Or create $CONFIG_FILE with these variables"
            exit 1
        fi
    fi
    
    # Verify required variables
    if [[ -z "$REDDIT_CLIENT_ID" ]] || [[ -z "$REDDIT_CLIENT_SECRET" ]]; then
        error "Missing Reddit API credentials"
        exit 1
    fi
    
    # Set defaults
    REDDIT_USER_AGENT="${REDDIT_USER_AGENT:-TikTokRedditScraper/1.0}"
    
    success "Configuration loaded successfully"
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    if [[ ! -f "$SCRIPT_DIR/main.py" ]]; then
        error "Main script not found: $SCRIPT_DIR/main.py"
        exit 1
    fi
    
    # Check Python dependencies
    python -c "import asyncio, aiohttp, praw" 2>/dev/null || {
        error "Missing Python dependencies. Setting up virtual environment..."
        setup_venv
    }
    
    success "Dependencies check passed"
}

# Setup virtual environment
setup_venv() {
    log "Setting up Python virtual environment..."
    
    if [[ ! -d "$VENV_PATH" ]]; then
        log "Creating virtual environment at $VENV_PATH"
        python3 -m venv "$VENV_PATH"
    fi
    
    source "$VENV_PATH/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip > /dev/null 2>&1
    
    # Install requirements
    if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
        log "Installing requirements from requirements.txt"
        pip install -r "$SCRIPT_DIR/requirements.txt" > /dev/null 2>&1
    else
        log "Installing basic requirements"
        pip install asyncio aiohttp praw pandas openpyxl > /dev/null 2>&1
    fi
    
    success "Virtual environment ready"
}

# Test Reddit API connection
test_api_connection() {
    log "Testing Reddit API connection..."
    
    source "$VENV_PATH/bin/activate" 2>/dev/null || true
    
    python -c "
import praw
import sys

try:
    reddit = praw.Reddit(
        client_id='$REDDIT_CLIENT_ID',
        client_secret='$REDDIT_CLIENT_SECRET',
        user_agent='$REDDIT_USER_AGENT'
    )
    
    # Test connection
    subreddit = reddit.subreddit('test')
    print(f'Connected to Reddit API. Test subreddit: {subreddit.display_name}')
    print('API connection successful')
    
except Exception as e:
    print(f'API connection failed: {e}')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Reddit API connection successful"
        return 0
    else
        error "Reddit API connection failed"
        return 1
    fi
}

# Scrape single user
scrape_user() {
    local username="$1"
    local max_posts="${2:-100}"
    local format="${3:-json}"
    
    if [[ -z "$username" ]]; then
        error "Username required for user scraping"
        return 1
    fi
    
    log "Scraping Reddit user: $username"
    log "Max posts: $max_posts"
    log "Format: $format"
    
    mkdir -p "$OUTPUT_DIR"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    python main.py \
        --client-id "$REDDIT_CLIENT_ID" \
        --client-secret "$REDDIT_CLIENT_SECRET" \
        --user-agent "$REDDIT_USER_AGENT" \
        --username "$username" \
        --max-posts "$max_posts" \
        --format "$format" \
        --include-analysis \
        --output-dir "$OUTPUT_DIR" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "User scraping completed for: $username"
        return 0
    else
        error "User scraping failed for: $username"
        return 1
    fi
}

# Batch scrape multiple users
batch_scrape() {
    local users_file="$1"
    local max_posts="${2:-50}"
    local format="${3:-json}"
    
    if [[ -z "$users_file" ]] || [[ ! -f "$users_file" ]]; then
        error "Users file required and must exist: $users_file"
        return 1
    fi
    
    log "Batch scraping users from: $users_file"
    log "Max posts per user: $max_posts"
    log "Format: $format"
    
    mkdir -p "$OUTPUT_DIR"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    python main.py \
        --client-id "$REDDIT_CLIENT_ID" \
        --client-secret "$REDDIT_CLIENT_SECRET" \
        --user-agent "$REDDIT_USER_AGENT" \
        --batch "$users_file" \
        --max-posts "$max_posts" \
        --format "$format" \
        --output-dir "$OUTPUT_DIR" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Batch scraping completed"
        return 0
    else
        error "Batch scraping failed"
        return 1
    fi
}

# Discover subreddits from TikTok data
discover_subreddits() {
    local max_users="${1:-50}"
    local output_dir="${2:-subreddit_discovery}"
    
    if [[ ! -f "$TIKTOK_DATA" ]]; then
        error "TikTok data file not found: $TIKTOK_DATA"
        return 1
    fi
    
    log "Discovering subreddits from TikTok data"
    log "TikTok data: $TIKTOK_DATA"
    log "Max users to analyze: $max_users"
    log "Output directory: $output_dir"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    python main.py \
        --client-id "$REDDIT_CLIENT_ID" \
        --client-secret "$REDDIT_CLIENT_SECRET" \
        --user-agent "$REDDIT_USER_AGENT" \
        --discover-from-tiktok "$TIKTOK_DATA" \
        --max-users "$max_users" \
        --discovery-output "$output_dir" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Subreddit discovery completed"
        success "Results saved to: $output_dir"
        return 0
    else
        error "Subreddit discovery failed"
        return 1
    fi
}

# Analyze user performance in specific subreddit
analyze_user_subreddit() {
    local username="$1"
    local subreddit="$2"
    local comparison="${3:-true}"
    
    if [[ -z "$username" ]] || [[ -z "$subreddit" ]]; then
        error "Username and subreddit required for analysis"
        return 1
    fi
    
    log "Analyzing user $username in r/$subreddit"
    log "Include comparison: $comparison"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    local args=(
        --client-id "$REDDIT_CLIENT_ID"
        --client-secret "$REDDIT_CLIENT_SECRET"
        --user-agent "$REDDIT_USER_AGENT"
        --subreddit-analysis "$username" "$subreddit"
    )
    
    if [[ "$comparison" == "true" ]]; then
        args+=(--comparison)
    fi
    
    python main.py "${args[@]}" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Subreddit analysis completed"
        return 0
    else
        error "Subreddit analysis failed"
        return 1
    fi
}

# Extract Reddit usernames from TikTok data
extract_usernames() {
    local output_file="${1:-extracted_reddit_usernames.txt}"
    
    if [[ ! -f "$TIKTOK_DATA" ]]; then
        error "TikTok data file not found: $TIKTOK_DATA"
        return 1
    fi
    
    log "Extracting Reddit usernames from TikTok data"
    log "Output file: $output_file"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    python extract_usernames_test.py "$TIKTOK_DATA" "$output_file" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Username extraction completed"
        success "Usernames saved to: $output_file"
        
        # Show stats
        if [[ -f "$output_file" ]]; then
            local count=$(wc -l < "$output_file")
            log "Extracted $count unique Reddit usernames"
        fi
        
        return 0
    else
        error "Username extraction failed"
        return 1
    fi
}

# Run subreddit discovery demo
discovery_demo() {
    log "Running subreddit discovery demo..."
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    if [[ -f "demo_discovery.py" ]]; then
        python demo_discovery.py 2>&1 | tee -a "$LOG_FILE"
    else
        warning "Demo script not found. Running regular discovery with limited data..."
        discover_subreddits 10 "demo_discovery_results"
    fi
    
    return $?
}

# Clean old results
clean_results() {
    local days="${1:-7}"
    
    log "Cleaning results older than $days days..."
    
    if [[ -d "$OUTPUT_DIR" ]]; then
        find "$OUTPUT_DIR" -name "*.json" -type f -mtime +$days -delete
        find "$OUTPUT_DIR" -name "*.csv" -type f -mtime +$days -delete
        find "$OUTPUT_DIR" -name "*.xlsx" -type f -mtime +$days -delete
        success "Old results cleaned"
    fi
    
    # Clean subreddit discovery results
    find "$SCRIPT_DIR" -name "subreddit_discovery_*" -type d -mtime +$days -exec rm -rf {} + 2>/dev/null || true
    
    success "Cleanup completed"
}

# Show usage
show_usage() {
    cat << EOF
Reddit Scraper Automation Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    test-api
        Test Reddit API connection

    user <username> [max_posts] [format]
        Scrape single Reddit user
        username: Reddit username (required)
        max_posts: Maximum posts to analyze (default: 100)
        format: Output format (json/csv/excel) (default: json)

    batch <users_file> [max_posts] [format]
        Batch scrape multiple users
        users_file: File with usernames (one per line)
        max_posts: Maximum posts per user (default: 50)
        format: Output format (default: json)

    discover [max_users] [output_dir]
        Discover subreddits from TikTok data
        max_users: Maximum Reddit users to analyze (default: 50)
        output_dir: Output directory (default: subreddit_discovery)

    analyze <username> <subreddit> [comparison]
        Analyze user performance in specific subreddit
        username: Reddit username
        subreddit: Subreddit name (without r/)
        comparison: Include performance comparison (true/false, default: true)

    extract-usernames [output_file]
        Extract Reddit usernames from TikTok data
        output_file: Output filename (default: extracted_reddit_usernames.txt)

    demo
        Run subreddit discovery demo

    clean [days]
        Clean results older than specified days (default: 7)

Examples:
    $0 test-api
    $0 user spez 50 json
    $0 batch users.txt 100 excel
    $0 discover 25 my_discovery
    $0 analyze gallowboob funny true
    $0 extract-usernames reddit_users.txt
    $0 demo
    $0 clean 14

Configuration:
    Create config.env with:
    REDDIT_CLIENT_ID=your_client_id
    REDDIT_CLIENT_SECRET=your_client_secret
    REDDIT_USER_AGENT=YourApp/1.0

EOF
}

# Main script logic
main() {
    # Create log file directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting Reddit Scraper"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "TikTok data: $TIKTOK_DATA"
    log "Output directory: $OUTPUT_DIR"
    
    # Load configuration
    load_config
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "test-api")
            test_api_connection
            ;;
        "user")
            if [[ -z "$2" ]]; then
                error "Username required for user scraping"
                show_usage
                exit 1
            fi
            scrape_user "$2" "${3:-100}" "${4:-json}"
            ;;
        "batch")
            if [[ -z "$2" ]]; then
                error "Users file required for batch scraping"
                show_usage
                exit 1
            fi
            batch_scrape "$2" "${3:-50}" "${4:-json}"
            ;;
        "discover")
            discover_subreddits "${2:-50}" "${3:-subreddit_discovery}"
            ;;
        "analyze")
            if [[ -z "$2" ]] || [[ -z "$3" ]]; then
                error "Username and subreddit required for analysis"
                show_usage
                exit 1
            fi
            analyze_user_subreddit "$2" "$3" "${4:-true}"
            ;;
        "extract-usernames")
            extract_usernames "${2:-extracted_reddit_usernames.txt}"
            ;;
        "demo")
            discovery_demo
            ;;
        "clean")
            clean_results "${2:-7}"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Testing API connection..."
            test_api_connection
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Reddit scraper completed"
}

# Run main function with all arguments
main "$@"