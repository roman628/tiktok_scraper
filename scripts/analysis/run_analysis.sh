#!/bin/bash

# TikTok Analysis Scripts - Automation Script  
# Handles data analysis, counting, and content extraction

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DATA_FILE="$PROJECT_ROOT/master2.json"
RESULTS_DIR="$SCRIPT_DIR/results"
LOG_FILE="$PROJECT_ROOT/analysis.log"

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
    
    # Check Python dependencies
    python -c "import json, pandas, numpy" 2>/dev/null || {
        error "Missing Python dependencies. Please install: pip install pandas numpy"
        exit 1
    }
    
    success "Dependencies check passed"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$RESULTS_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"
    
    success "Directories ready"
}

# Extract comments from videos
extract_comments() {
    local output_file="${1:-comments_extracted.json}"
    local min_comments="${2:-1}"
    
    log "Extracting comments from videos..."
    log "Output file: $output_file"
    log "Minimum comments per video: $min_comments" 
    
    if [[ ! -f "$SCRIPT_DIR/comment_extractor.py" ]]; then
        error "Comment extractor script not found: $SCRIPT_DIR/comment_extractor.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python comment_extractor.py \
        --input "$DATA_FILE" \
        --output "$RESULTS_DIR/$output_file" \
        --min-comments "$min_comments" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Comment extraction completed"
        return 0
    else
        error "Comment extraction failed"
        return 1
    fi
}

# Count videos and statistics
count_videos() {
    local detailed="${1:-true}"
    local by_uploader="${2:-false}"
    
    log "Counting videos and generating statistics..."
    log "Detailed analysis: $detailed"
    log "Group by uploader: $by_uploader"
    
    if [[ ! -f "$SCRIPT_DIR/count.py" ]]; then
        error "Count script not found: $SCRIPT_DIR/count.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python count.py \
        --input "$DATA_FILE" \
        --detailed "$detailed" \
        --by-uploader "$by_uploader" \
        --output "$RESULTS_DIR" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Video counting completed"
        return 0
    else
        error "Video counting failed"
        return 1
    fi
}

# Count master data with comprehensive analysis
count_master() {
    local include_metrics="${1:-true}"
    local export_csv="${2:-true}"
    
    log "Running comprehensive master data analysis..."
    log "Include performance metrics: $include_metrics"
    log "Export to CSV: $export_csv"
    
    if [[ ! -f "$SCRIPT_DIR/count_master.py" ]]; then
        error "Count master script not found: $SCRIPT_DIR/count_master.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python count_master.py \
        --input "$DATA_FILE" \
        --metrics "$include_metrics" \
        --csv "$export_csv" \
        --output-dir "$RESULTS_DIR" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Master data analysis completed"
        return 0
    else
        error "Master data analysis failed"
        return 1
    fi
}

# Run basic analysis
basic_analysis() {
    log "Running basic TikTok data analysis..."
    
    setup_directories
    
    local success_count=0
    
    # Count videos
    if count_videos true false; then
        success_count=$((success_count + 1))
    fi
    
    # Extract comments
    if extract_comments "basic_comments.json" 1; then
        success_count=$((success_count + 1))
    fi
    
    log "Basic analysis completed: $success_count/2 operations successful"
    
    if [[ $success_count -gt 0 ]]; then
        success "Basic analysis completed"
        return 0
    else
        error "Basic analysis failed"
        return 1
    fi
}

# Run comprehensive analysis
comprehensive_analysis() {
    log "Running comprehensive TikTok data analysis..."
    
    setup_directories
    
    local success_count=0
    local total_analyses=3
    
    # Comprehensive counting with uploader analysis
    log "Phase 1: Comprehensive video counting..."
    if count_videos true true; then
        success_count=$((success_count + 1))
    fi
    
    # Master data analysis with metrics
    log "Phase 2: Master data analysis..."
    if count_master true true; then
        success_count=$((success_count + 1))
    fi
    
    # Detailed comment extraction
    log "Phase 3: Detailed comment extraction..."
    if extract_comments "comprehensive_comments.json" 1; then
        success_count=$((success_count + 1))
    fi
    
    # Generate comprehensive report
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

# Generate analysis report
generate_analysis_report() {
    log "Generating analysis report..."
    
    local report_file="$RESULTS_DIR/analysis_report_$(date '+%Y%m%d_%H%M%S').md"
    
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
    
    # Calculate engagement metrics
    total_views = sum(v.get('view_count', 0) for v in data)
    total_likes = sum(v.get('like_count', 0) for v in data)
    total_comments = sum(v.get('comment_count', 0) for v in data)
    
    avg_views = total_views / total_videos if total_videos > 0 else 0
    avg_likes = total_likes / total_videos if total_videos > 0 else 0
    avg_comments = total_comments / total_videos if total_videos > 0 else 0
    
    # Get unique uploaders
    uploaders = set(v.get('uploader', 'Unknown') for v in data)
    unique_uploaders = len(uploaders)
    
    print(f'{total_videos},{with_transcription},{with_comments},{total_views},{total_likes},{total_comments},{unique_uploaders},{avg_views:.0f},{avg_likes:.0f},{avg_comments:.0f}')
    
except Exception as e:
    print('0,0,0,0,0,0,0,0,0,0')
")
    
    IFS=',' read -r total_videos with_transcription with_comments total_views total_likes total_comments unique_uploaders avg_views avg_likes avg_comments <<< "$stats"
    
    cat > "$report_file" << EOF
# TikTok Data Analysis Report

Generated on: $(date '+%Y-%m-%d %H:%M:%S')

## Dataset Overview

### Basic Statistics
- **Total Videos**: $(printf "%'d" $total_videos)
- **Videos with Transcription**: $(printf "%'d" $with_transcription) ($(( with_transcription * 100 / total_videos ))%)
- **Videos with Comments**: $(printf "%'d" $with_comments) ($(( with_comments * 100 / total_videos ))%)
- **Unique Uploaders**: $(printf "%'d" $unique_uploaders)

### Engagement Metrics
- **Total Views**: $(printf "%'d" $total_views)
- **Total Likes**: $(printf "%'d" $total_likes) 
- **Total Comments**: $(printf "%'d" $total_comments)
- **Average Views per Video**: $(printf "%'d" $avg_views)
- **Average Likes per Video**: $(printf "%'d" $avg_likes)
- **Average Comments per Video**: $(printf "%'d" $avg_comments)

## Analysis Components

### 1. Video Counting Analysis
- **Script**: count.py, count_master.py
- **Output Directory**: $RESULTS_DIR
- **Description**: Comprehensive video statistics and uploader analysis

### 2. Comment Extraction
- **Script**: comment_extractor.py  
- **Output Files**: comments_extracted.json, comprehensive_comments.json
- **Description**: Extracts and analyzes video comments for sentiment and engagement

### 3. Master Data Analysis
- **Output**: CSV exports with performance metrics
- **Metrics**: View counts, engagement rates, uploader performance
- **Visualizations**: Charts and graphs (if generated)

## Key Insights

### Content Performance
- **Engagement Rate**: $(python -c "print(f'{($total_likes + $total_comments) / $total_views * 100:.2f}%' if $total_views > 0 else '0%')")
- **Average Video Performance**: $(printf "%'d" $avg_views) views, $(printf "%'d" $avg_likes) likes
- **Content Coverage**: $((with_transcription * 100 / total_videos))% of videos have transcription data

### Data Quality
- **Transcription Coverage**: $((with_transcription * 100 / total_videos))%
- **Comment Coverage**: $((with_comments * 100 / total_videos))%
- **Completeness Score**: $(python -c "
complete_videos = $with_transcription if $with_transcription < $with_comments else $with_comments
print(f'{complete_videos / $total_videos * 100:.1f}%' if $total_videos > 0 else '0%')
")

### Content Distribution
- **Videos per Uploader**: $(python -c "print(f'{$total_videos / $unique_uploaders:.1f}' if $unique_uploaders > 0 else '0')")
- **Top Performing Content**: Available in detailed analysis files

## Available Analysis Files

### Results Directory: $RESULTS_DIR
EOF
    
    # List generated files
    if [[ -d "$RESULTS_DIR" ]]; then
        find "$RESULTS_DIR" -name "*.json" -o -name "*.csv" -o -name "*.txt" | while read -r file; do
            echo "- $(basename "$file")" >> "$report_file"
        done
    fi
    
    cat >> "$report_file" << EOF

## Recommendations

### Data Enhancement
1. **Improve Transcription Coverage**: $((100 - with_transcription * 100 / total_videos))% of videos lack transcription
2. **Comment Analysis**: Focus on high-engagement videos for deeper insights
3. **Content Optimization**: Analyze top-performing uploaders for best practices

### Analysis Opportunities
1. **Temporal Analysis**: Study posting time patterns
2. **Content Categorization**: Genre-based performance analysis  
3. **Engagement Prediction**: Use performance metrics for future content
4. **Trend Identification**: Track viral content patterns

## Next Steps

1. Review detailed analysis files in $RESULTS_DIR
2. Run keyword scoring analysis for content insights
3. Use performance predictor for optimization recommendations
4. Generate visualization dashboards for trend analysis

---

**Data Source**: $DATA_FILE  
**Log File**: $LOG_FILE  
**Analysis Scripts**: $SCRIPT_DIR
EOF
    
    success "Analysis report generated: $report_file"
}

# Show analysis results
show_results() {
    log "Showing analysis results..."
    
    echo
    echo "=== ANALYSIS RESULTS ==="
    
    if [[ -d "$RESULTS_DIR" ]]; then
        echo
        echo "📊 Results Directory ($RESULTS_DIR):"
        ls -la "$RESULTS_DIR" 2>/dev/null || echo "  (empty)"
    fi
    
    # Show basic statistics
    python -c "
import json
try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    total = len(data)
    with_transcription = sum(1 for v in data if v.get('whisper_transcription'))
    with_comments = sum(1 for v in data if v.get('top_comments'))
    
    print()
    print('📈 Quick Statistics:')
    print(f'   Total Videos: {total:,}')
    print(f'   With Transcription: {with_transcription:,} ({with_transcription/total*100:.1f}%)')
    print(f'   With Comments: {with_comments:,} ({with_comments/total*100:.1f}%)')
    
    if total > 0:
        avg_views = sum(v.get('view_count', 0) for v in data) / total
        print(f'   Average Views: {avg_views:,.0f}')
    
except Exception as e:
    print(f'Error loading data: {e}')
"
    
    echo
    echo "💾 Log file: $LOG_FILE"
    echo "========================="
}

# Export analysis data
export_data() {
    local format="${1:-csv}"
    local include_all="${2:-false}"
    
    log "Exporting analysis data..."
    log "Format: $format"
    log "Include all fields: $include_all"
    
    local export_file="$RESULTS_DIR/tiktok_data_export_$(date '+%Y%m%d_%H%M%S').$format"
    
    python -c "
import json
import pandas as pd

try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Select columns based on include_all flag
    if '$include_all' == 'false':
        # Essential columns only
        columns = ['video_id', 'title', 'uploader', 'view_count', 'like_count', 
                  'comment_count', 'upload_date', 'duration']
        df = df[[col for col in columns if col in df.columns]]
    
    # Export based on format
    if '$format' == 'csv':
        df.to_csv('$export_file', index=False)
    elif '$format' == 'json':
        df.to_json('$export_file', orient='records', indent=2)
    elif '$format' == 'excel':
        df.to_excel('$export_file', index=False, engine='openpyxl')
    
    print(f'Data exported to: $export_file')
    print(f'Records exported: {len(df)}')
    print(f'Columns: {len(df.columns)}')
    
except Exception as e:
    print(f'Export failed: {e}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Data export completed: $export_file"
    else
        error "Data export failed"
        return 1
    fi
}

# Clean old analysis results
clean_results() {
    local days="${1:-7}"
    
    log "Cleaning analysis results older than $days days..."
    
    if [[ -d "$RESULTS_DIR" ]]; then
        find "$RESULTS_DIR" -name "*.json" -type f -mtime +$days -delete
        find "$RESULTS_DIR" -name "*.csv" -type f -mtime +$days -delete
        find "$RESULTS_DIR" -name "*.md" -type f -mtime +$days -delete
        find "$RESULTS_DIR" -name "*.xlsx" -type f -mtime +$days -delete
        success "Old results cleaned"
    fi
}

# Show usage
show_usage() {
    cat << EOF
TikTok Analysis Scripts

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    count [detailed] [by_uploader]
        Count videos and generate statistics
        detailed: Include detailed analysis (true/false, default: true)
        by_uploader: Group by uploader (true/false, default: false)

    count-master [include_metrics] [export_csv]
        Comprehensive master data analysis
        include_metrics: Include performance metrics (true/false, default: true)
        export_csv: Export to CSV (true/false, default: true)

    extract-comments [output_file] [min_comments]
        Extract comments from videos
        output_file: Output filename (default: comments_extracted.json)
        min_comments: Minimum comments per video (default: 1)

    basic
        Run basic analysis (counting + comment extraction)

    comprehensive
        Run comprehensive analysis with full reporting

    export [format] [include_all]
        Export data in specified format
        format: csv/json/excel (default: csv)
        include_all: Include all fields (true/false, default: false)

    report
        Generate analysis report from existing data

    results
        Show current analysis results

    clean [days]
        Clean results older than specified days (default: 7)

Examples:
    $0 basic
    $0 comprehensive
    $0 count true true
    $0 extract-comments detailed_comments.json 5
    $0 export csv false
    $0 results
    $0 clean 14

Output Directory:
    - Results: $RESULTS_DIR

EOF
}

# Main script logic
main() {
    # Create log file directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting TikTok Analysis Scripts"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    log "Results directory: $RESULTS_DIR"
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "count")
            setup_directories
            count_videos "${2:-true}" "${3:-false}"
            ;;
        "count-master")
            setup_directories
            count_master "${2:-true}" "${3:-true}"
            ;;
        "extract-comments")
            setup_directories
            extract_comments "${2:-comments_extracted.json}" "${3:-1}"
            ;;
        "basic")
            basic_analysis
            ;;
        "comprehensive")
            comprehensive_analysis
            ;;
        "export")
            setup_directories
            export_data "${2:-csv}" "${3:-false}"
            ;;
        "report")
            generate_analysis_report
            ;;
        "results")
            show_results
            ;;
        "clean")
            clean_results "${2:-7}"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Showing analysis results..."
            show_results
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Analysis scripts completed"
}

# Run main function with all arguments
main "$@"