#!/bin/bash

# TikTok Keyword Scoring System - Automation Script
# Generates keyword maps and analysis for TikTok content optimization

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_FILE="$PROJECT_ROOT/master2.json"
OUTPUT_DIR="$SCRIPT_DIR/output"
LOG_FILE="$SCRIPT_DIR/keyword_scoring.log"
VENV_PATH="$SCRIPT_DIR/keyword_env"

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

# Check if required files exist
check_dependencies() {
    log "Checking dependencies..."
    
    if [[ ! -f "$DATA_FILE" ]]; then
        error "Data file not found: $DATA_FILE"
        exit 1
    fi
    
    if [[ ! -f "$SCRIPT_DIR/keyword_scorer.py" ]]; then
        error "Keyword scorer script not found: $SCRIPT_DIR/keyword_scorer.py"
        exit 1
    fi
    
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
        pip install nltk scikit-learn pandas numpy click > /dev/null 2>&1
    fi
    
    success "Virtual environment ready"
}

# Run keyword extraction and scoring
run_keyword_scoring() {
    local max_videos="${1:-1000}"
    local methods="${2:-rake,textrank,yake}"
    local sentiment="${3:-true}"
    local output_format="${4:-both}"
    
    log "Running keyword scoring analysis..."
    log "Max videos: $max_videos"
    log "Methods: $methods"
    log "Sentiment analysis: $sentiment"
    log "Output format: $output_format"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Activate virtual environment
    source "$VENV_PATH/bin/activate"
    
    # Prepare arguments
    local args=(
        "$DATA_FILE"
        --output "$OUTPUT_DIR/keyword_scores_$(date '+%Y%m%d_%H%M%S')"
        --max-videos "$max_videos"
        --format "$output_format"
        --batch-size 50
        --min-video-count 2
        --verbose
    )
    
    # Add methods
    IFS=',' read -ra METHOD_ARRAY <<< "$methods"
    for method in "${METHOD_ARRAY[@]}"; do
        args+=(--methods "$method")
    done
    
    # Add sentiment flag
    if [[ "$sentiment" == "true" ]]; then
        args+=(--sentiment)
    else
        args+=(--no-sentiment)
    fi
    
    # Run the scoring
    cd "$SCRIPT_DIR"
    python keyword_scorer.py score "${args[@]}" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Keyword scoring completed successfully"
        return 0
    else
        error "Keyword scoring failed"
        return 1
    fi
}

# Analyze existing results
analyze_results() {
    local results_file="$1"
    local top_k="${2:-50}"
    
    if [[ ! -f "$results_file" ]]; then
        error "Results file not found: $results_file"
        return 1
    fi
    
    log "Analyzing results from: $results_file"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    python keyword_scorer.py analyze "$results_file" --top-k "$top_k" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Results analysis completed"
        return 0
    else
        error "Results analysis failed"
        return 1
    fi
}

# Generate keyword map for the project
generate_keyword_map() {
    log "Generating keyword map for project..."
    
    # Find the most recent keyword scores file
    local latest_json=$(find "$OUTPUT_DIR" -name "keyword_scores_*.json" -type f -exec ls -t {} + | head -n 1)
    
    if [[ -z "$latest_json" ]]; then
        error "No keyword scores JSON file found. Run scoring first."
        return 1
    fi
    
    log "Using results from: $latest_json"
    
    # Generate map file
    local map_file="$PROJECT_ROOT/keyword_score_map.json"
    
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    
    # Extract top keywords and create a simplified map
    python -c "
import json
import sys

try:
    with open('$latest_json', 'r') as f:
        data = json.load(f)
    
    # Create simplified keyword map
    keyword_map = {}
    for keyword in data.get('keywords', [])[:100]:  # Top 100 keywords
        keyword_map[keyword['keyword']] = {
            'score': keyword['final_score'],
            'video_count': keyword['video_count'],
            'avg_engagement': keyword['avg_engagement'],
            'sentiment': keyword['sentiment_score']
        }
    
    # Save to project root
    with open('$map_file', 'w') as f:
        json.dump({
            'generated_at': data.get('metadata', {}).get('generated_at', ''),
            'total_keywords': len(keyword_map),
            'extraction_methods': data.get('metadata', {}).get('extraction_methods', []),
            'keywords': keyword_map
        }, f, indent=2)
    
    print('Keyword map generated successfully')
    
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Keyword map saved to: $map_file"
        return 0
    else
        error "Failed to generate keyword map"
        return 1
    fi
}

# Clean old results
clean_old_results() {
    local days="${1:-7}"
    
    log "Cleaning results older than $days days..."
    
    if [[ -d "$OUTPUT_DIR" ]]; then
        find "$OUTPUT_DIR" -name "keyword_scores_*" -type f -mtime +$days -delete
        success "Old results cleaned"
    fi
}

# Show usage
show_usage() {
    cat << EOF
TikTok Keyword Scoring System

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    score [max_videos] [methods] [sentiment] [format]
        Run keyword scoring analysis
        max_videos: Maximum videos to process (default: 1000)
        methods: Comma-separated list (rake,textrank,yake) (default: rake,textrank,yake)
        sentiment: Enable sentiment analysis (true/false) (default: true)
        format: Output format (json/csv/both) (default: both)

    analyze <results_file> [top_k]
        Analyze existing results file
        results_file: Path to JSON results file
        top_k: Number of top keywords to show (default: 50)

    generate-map
        Generate keyword map from latest results

    clean [days]
        Clean results older than specified days (default: 7)

    quick
        Quick analysis with default settings (500 videos)

    full  
        Full analysis with all videos

Examples:
    $0 score 500 "rake,textrank" true json
    $0 analyze output/keyword_scores_20240101_120000.json 100
    $0 generate-map
    $0 clean 14
    $0 quick
    $0 full

EOF
}

# Main script logic
main() {
    # Create log file
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting TikTok Keyword Scoring System"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    
    # Check dependencies
    check_dependencies
    
    # Setup environment
    setup_venv
    
    case "${1:-}" in
        "score")
            run_keyword_scoring "${2:-1000}" "${3:-rake,textrank,yake}" "${4:-true}" "${5:-both}"
            if [[ $? -eq 0 ]]; then
                generate_keyword_map
            fi
            ;;
        "analyze")
            if [[ -z "$2" ]]; then
                error "Results file required for analyze command"
                show_usage
                exit 1
            fi
            analyze_results "$2" "${3:-50}"
            ;;
        "generate-map")
            generate_keyword_map
            ;;
        "clean")
            clean_old_results "${2:-7}"
            ;;
        "quick")
            log "Running quick analysis (500 videos)..."
            run_keyword_scoring 500 "rake,textrank" true json
            if [[ $? -eq 0 ]]; then
                generate_keyword_map
            fi
            ;;
        "full")
            log "Running full analysis (all videos)..."
            run_keyword_scoring "" "rake,textrank,yake" true both
            if [[ $? -eq 0 ]]; then
                generate_keyword_map
            fi
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Running quick analysis..."
            run_keyword_scoring 500 "rake,textrank" true json
            if [[ $? -eq 0 ]]; then
                generate_keyword_map
            fi
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Keyword scoring system completed"
}

# Run main function with all arguments
main "$@"