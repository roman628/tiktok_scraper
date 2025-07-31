#!/bin/bash

# Video Analysis - Automation Script
# Handles video transcription, analysis, and cleanup operations

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_FILE="$PROJECT_ROOT/master2.json"
REPORTS_DIR="$SCRIPT_DIR/reports"
TRANSCRIPTIONS_DIR="$SCRIPT_DIR/transcriptions"
SCORES_DIR="$SCRIPT_DIR/scores"
TEST_OUTPUT_DIR="$SCRIPT_DIR/test_output"
LOG_FILE="$SCRIPT_DIR/video_analysis.log"

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
    
    if [[ ! -f "$DATA_FILE" ]]; then
        error "Data file not found: $DATA_FILE"
        exit 1
    fi
    
    # Check for required Python packages
    python -c "import json, pandas, numpy" 2>/dev/null || {
        error "Missing Python dependencies. Please install: pip install pandas numpy"
        exit 1
    }
    
    success "Dependencies check passed"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$REPORTS_DIR"
    mkdir -p "$TRANSCRIPTIONS_DIR"
    mkdir -p "$SCORES_DIR"
    mkdir -p "$TEST_OUTPUT_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"
    
    success "Directories ready"
}

# Run video transcription analysis
run_transcription_analysis() {
    log "Running video transcription analysis..."
    
    if [[ ! -f "$SCRIPT_DIR/video_transcriber.py" ]]; then
        error "Video transcriber script not found: $SCRIPT_DIR/video_transcriber.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python video_transcriber.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Video transcription analysis completed"
        return 0
    else
        error "Video transcription analysis failed"
        return 1
    fi
}

# Analyze user videos from input directory
analyze_user_videos() {
    local input_dir="${1:-input_videos}"
    local output_dir="${2:-results}"
    local model_size="${3:-base}"
    local max_videos="${4:-}"
    
    log "Analyzing user videos..."
    log "Input directory: $input_dir"
    log "Output directory: $output_dir"
    log "Model size: $model_size"
    
    if [[ ! -f "$SCRIPT_DIR/analyze_videos.py" ]]; then
        error "Video analysis script not found: $SCRIPT_DIR/analyze_videos.py"
        return 1
    fi
    
    local args=(
        --input-dir "$input_dir"
        --output-dir "$output_dir"
        --model-size "$model_size"
    )
    
    if [[ -n "$max_videos" ]]; then
        args+=(--max-videos "$max_videos")
    fi
    
    cd "$SCRIPT_DIR"
    python analyze_videos.py "${args[@]}" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "User video analysis completed"
        return 0
    else
        error "User video analysis failed"
        return 1
    fi
}

# Run intelligent cleanup
run_intelligent_cleanup() {
    local backup="${1:-true}"
    
    log "Running intelligent cleanup..."
    log "Backup enabled: $backup"
    
    if [[ ! -f "$SCRIPT_DIR/intelligent_cleanup.py" ]]; then
        warning "Intelligent cleanup script not found, skipping..."
        return 0
    fi
    
    # Backup original data if requested
    if [[ "$backup" == "true" ]]; then
        local backup_file="$PROJECT_ROOT/master2.json.backup_$(date '+%Y%m%d_%H%M%S')"
        log "Creating backup: $backup_file"
        cp "$DATA_FILE" "$backup_file"
    fi
    
    cd "$SCRIPT_DIR"
    python intelligent_cleanup.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Intelligent cleanup completed"
        return 0
    else
        error "Intelligent cleanup failed"
        return 1
    fi
}

# Test single video analysis
test_single_video() {
    local video_id="${1:-}"
    
    if [[ -z "$video_id" ]]; then
        # Get a random video ID from the data
        video_id=$(python -c "
import json
import random

try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    # Get a video with transcription if possible
    videos_with_transcription = [v for v in data if v.get('whisper_transcription')]
    
    if videos_with_transcription:
        video = random.choice(videos_with_transcription)
    else:
        video = random.choice(data)
    
    video_id = video.get('video_id', str(random.randint(0, len(data)-1)))
    print(video_id)
    
except:
    print('0')
")
    fi
    
    log "Testing single video analysis for video: $video_id"
    
    if [[ ! -f "$SCRIPT_DIR/test_single_video.py" ]]; then
        error "Single video test script not found: $SCRIPT_DIR/test_single_video.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python test_single_video.py "$video_id" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Single video test completed for: $video_id"
        return 0
    else
        error "Single video test failed"
        return 1
    fi
}

# Generate analysis report
generate_analysis_report() {
    log "Generating video analysis report..."
    
    local report_file="$REPORTS_DIR/video_analysis_report_$(date '+%Y%m%d_%H%M%S').md"
    
    # Get basic statistics
    local stats=$(python -c "
import json
import os

try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    total_videos = len(data)
    with_transcription = sum(1 for v in data if v.get('whisper_transcription'))
    with_comments = sum(1 for v in data if v.get('top_comments'))
    
    # Get file sizes for user video analysis results
    results_dir = '$SCRIPT_DIR/results'
    analysis_files = 0
    if os.path.exists(results_dir):
        analysis_files = len([f for f in os.listdir(results_dir) if f.endswith('.json')])
    
    print(f'{total_videos},{with_transcription},{with_comments},{analysis_files}')
    
except Exception as e:
    print('0,0,0,0')
")
    
    IFS=',' read -r total_videos with_transcription with_comments analysis_files <<< "$stats"
    
    cat > "$report_file" << EOF
# Video Analysis Report

Generated on: $(date '+%Y-%m-%d %H:%M:%S')

## Analysis Summary

### Data Overview
- **Total Videos**: $total_videos
- **Videos with Transcription**: $with_transcription
- **Videos with Comments**: $with_comments
- **User Video Analysis Files**: $analysis_files

### Analysis Components

#### 1. Video Transcription Analysis
- **Script**: video_transcriber.py
- **Output Directory**: $TRANSCRIPTIONS_DIR
- **Description**: Processes video transcriptions for content analysis

#### 2. User Video Analysis
- **Script**: analyze_videos.py
- **Input Directory**: input_videos/
- **Output Directory**: results/
- **Description**: Portable video analysis for user-provided videos

#### 3. Intelligent Cleanup
- **Script**: intelligent_cleanup.py
- **Output Directory**: reports/
- **Description**: Automated data cleaning and quality improvement

#### 4. Single Video Testing
- **Script**: test_single_video.py
- **Output Directory**: $TEST_OUTPUT_DIR
- **Description**: Test framework for individual video analysis

## Directory Structure

- **Reports**: $REPORTS_DIR
- **Transcriptions**: $TRANSCRIPTIONS_DIR
- **Scores**: $SCORES_DIR
- **Test Output**: $TEST_OUTPUT_DIR

## Available Analysis Files

### User Video Analysis Results
EOF
    
    # Add user video results if they exist
    if [[ -d "$SCRIPT_DIR/results" ]]; then
        find "$SCRIPT_DIR/results" -name "*.json" | head -10 | while read -r file; do
            basename "$file" >> "$report_file"
        done
    fi
    
    cat >> "$report_file" << EOF

### Cleanup Reports
EOF
    
    # Add cleanup reports if they exist
    if [[ -f "$SCRIPT_DIR/reports/cleanup_report.json" ]]; then
        echo "- cleanup_report.json" >> "$report_file"
    fi
    
    cat >> "$report_file" << EOF

## Key Metrics

- **Transcription Coverage**: $(( with_transcription * 100 / total_videos ))%
- **Comment Coverage**: $(( with_comments * 100 / total_videos ))%
- **Analysis Completion**: Available in individual result files

## Recommendations

1. **For videos without transcription**: Consider generating automated transcripts
2. **For low-performing content**: Review Ubuntu analysis insights
3. **Data quality**: Use intelligent cleanup to improve dataset quality
4. **Testing**: Use single video tests for debugging analysis issues

## Next Steps

1. Review individual analysis files in results/
2. Check cleanup recommendations in cleanup_report.json
3. Run additional analyses on specific video subsets
4. Integrate insights with keyword scoring and performance prediction

---

Log file: $LOG_FILE
Data file: $DATA_FILE
EOF
    
    success "Analysis report generated: $report_file"
}

# Run comprehensive analysis
run_comprehensive_analysis() {
    log "Running comprehensive video analysis..."
    
    setup_directories
    
    local success_count=0
    local total_analyses=3
    
    # Run transcription analysis
    if run_transcription_analysis; then
        success_count=$((success_count + 1))
    fi
    
    # Run user video analysis
    if analyze_user_videos "input_videos" "comprehensive_results" "base"; then
        success_count=$((success_count + 1))
    fi
    
    # Test single video
    if test_single_video; then
        success_count=$((success_count + 1))
    fi
    
    # Generate report
    generate_analysis_report
    
    log "Comprehensive analysis completed: $success_count/$total_analyses analyses successful"
    
    if [[ $success_count -gt 0 ]]; then
        success "Comprehensive analysis completed successfully"
        return 0
    else
        error "All analyses failed"
        return 1
    fi
}

# Quick analysis (subset of features)
run_quick_analysis() {
    log "Running quick video analysis..."
    
    setup_directories
    
    # Just run the most important analyses
    if test_single_video; then
        success "Quick analysis: Single video test completed"
    fi
    
    # Try user video analysis if available
    if analyze_user_videos "input_videos" "quick_results" "base" 5; then
        success "Quick analysis: User video analysis completed"
    fi
    
    generate_analysis_report
    success "Quick analysis completed"
}

# Clean old analysis results
clean_old_results() {
    local days="${1:-7}"
    
    log "Cleaning analysis results older than $days days..."
    
    # Clean reports
    if [[ -d "$REPORTS_DIR" ]]; then
        find "$REPORTS_DIR" -name "*.md" -type f -mtime +$days -delete
        find "$REPORTS_DIR" -name "*.json" -type f -mtime +$days -delete
    fi
    
    # Clean test outputs
    if [[ -d "$TEST_OUTPUT_DIR" ]]; then
        find "$TEST_OUTPUT_DIR" -name "*.json" -type f -mtime +$days -delete
    fi
    
    # Clean transcriptions (be more careful with these)
    if [[ -d "$TRANSCRIPTIONS_DIR" ]]; then
        find "$TRANSCRIPTIONS_DIR" -name "*.txt" -type f -mtime +$days -delete
    fi
    
    success "Old results cleaned"
}

# Show directory contents
show_results() {
    log "Showing analysis results..."
    
    echo
    echo "=== ANALYSIS RESULTS ==="
    
    if [[ -d "$REPORTS_DIR" ]]; then
        echo
        echo "📊 Reports Directory ($REPORTS_DIR):"
        ls -la "$REPORTS_DIR" 2>/dev/null || echo "  (empty)"
        
        if [[ -d "$SCRIPT_DIR/results" ]]; then
            echo
            echo "🎥 User Video Analysis Results:"
            ls -la "$SCRIPT_DIR/results" | head -10 || echo "  (empty)"
        fi
    fi
    
    if [[ -d "$TEST_OUTPUT_DIR" ]]; then
        echo
        echo "🧪 Test Output Directory ($TEST_OUTPUT_DIR):"
        ls -la "$TEST_OUTPUT_DIR" 2>/dev/null || echo "  (empty)"
    fi
    
    if [[ -d "$TRANSCRIPTIONS_DIR" ]]; then
        echo
        echo "📝 Transcriptions Directory ($TRANSCRIPTIONS_DIR):"
        ls -la "$TRANSCRIPTIONS_DIR" 2>/dev/null || echo "  (empty)"
    fi
    
    echo
    echo "💾 Log file: $LOG_FILE"
    echo "========================"
}

# Show usage
show_usage() {
    cat << EOF
Video Analysis Automation Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    comprehensive
        Run all video analysis components

    quick
        Run essential analysis components only

    transcription
        Run video transcription analysis

    analyze [input_dir] [output_dir] [model_size] [max_videos]
        Analyze user videos from input directory
        input_dir: Input directory with videos (default: input_videos)
        output_dir: Output directory for results (default: results)
        model_size: Whisper model size (tiny/base/small/medium/large, default: base)
        max_videos: Maximum videos to process (optional)

    cleanup [backup]
        Run intelligent cleanup (backup: true/false, default: true)

    test [video_id]
        Test single video analysis (random video if no ID provided)

    report
        Generate analysis report from existing data

    clean [days]
        Clean results older than specified days (default: 7)

    results
        Show current analysis results

Examples:
    $0 comprehensive
    $0 quick
    $0 analyze my_videos my_results base 10
    $0 cleanup false
    $0 test video123
    $0 clean 14
    $0 results

Output Directories:
    - Reports: $REPORTS_DIR
    - Transcriptions: $TRANSCRIPTIONS_DIR
    - Test Output: $TEST_OUTPUT_DIR

EOF
}

# Main script logic
main() {
    # Create log file directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting Video Analysis"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "comprehensive")
            run_comprehensive_analysis
            ;;
        "quick")
            run_quick_analysis
            ;;
        "transcription")
            setup_directories
            run_transcription_analysis
            ;;
        "analyze")
            setup_directories
            analyze_user_videos "${2:-input_videos}" "${3:-results}" "${4:-base}" "${5:-}"
            ;;
        "cleanup")
            setup_directories
            run_intelligent_cleanup "${2:-true}"
            ;;
        "test")
            setup_directories
            test_single_video "$2"
            ;;
        "report")
            generate_analysis_report
            ;;
        "clean")
            clean_old_results "${2:-7}"
            ;;
        "results")
            show_results
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Running quick analysis..."
            run_quick_analysis
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Video analysis completed"
}

# Run main function with all arguments
main "$@"