#!/bin/bash

# TikTok Insights Dashboard - Automation Script
# Generates comprehensive TikTok performance insights and visualizations

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_FILE="$PROJECT_ROOT/master2.json"
CHARTS_DIR="$SCRIPT_DIR/charts"
OUTPUTS_DIR="$SCRIPT_DIR/outputs"
REPORTS_DIR="$SCRIPT_DIR/reports"
LOG_FILE="$SCRIPT_DIR/insights.log"

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
    python -c "import matplotlib, seaborn, pandas, numpy" 2>/dev/null || {
        error "Missing Python dependencies. Please install: pip install matplotlib seaborn pandas numpy"
        exit 1
    }
    
    success "Dependencies check passed"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$CHARTS_DIR"
    mkdir -p "$OUTPUTS_DIR" 
    mkdir -p "$REPORTS_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"
    
    success "Directories ready"
}

# Run improved dashboard
run_improved_dashboard() {
    log "Running improved TikTok insights dashboard..."
    
    if [[ ! -f "$SCRIPT_DIR/scripts/improved_dashboard.py" ]]; then
        error "Improved dashboard script not found: $SCRIPT_DIR/scripts/improved_dashboard.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR/scripts"
    python improved_dashboard.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Improved dashboard completed"
        return 0
    else
        error "Improved dashboard failed"
        return 1
    fi
}

# Generate optimal posting times analysis
analyze_posting_times() {
    log "Analyzing optimal posting times..."
    
    if [[ ! -f "$SCRIPT_DIR/scripts/optimal_posting_times.py" ]]; then
        warning "Optimal posting times script not found, skipping..."
        return 0
    fi
    
    cd "$SCRIPT_DIR/scripts"
    python optimal_posting_times.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Posting times analysis completed"
        return 0
    else
        error "Posting times analysis failed"
        return 1
    fi
}

# Generate genre performance analysis
analyze_genre_performance() {
    log "Analyzing genre performance..."
    
    if [[ ! -f "$SCRIPT_DIR/scripts/genre_performance.py" ]]; then
        warning "Genre performance script not found, skipping..."
        return 0
    fi
    
    cd "$SCRIPT_DIR/scripts"
    python genre_performance.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Genre performance analysis completed"
        return 0
    else
        error "Genre performance analysis failed"
        return 1
    fi
}

# Generate posting frequency analysis
analyze_posting_frequency() {
    log "Analyzing posting frequency patterns..."
    
    if [[ ! -f "$SCRIPT_DIR/scripts/posting_frequency.py" ]]; then
        warning "Posting frequency script not found, skipping..."
        return 0
    fi
    
    cd "$SCRIPT_DIR/scripts"
    python posting_frequency.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Posting frequency analysis completed"
        return 0
    else
        error "Posting frequency analysis failed"
        return 1
    fi
}

# Run basic dashboard (fallback)
run_basic_dashboard() {
    log "Running basic dashboard..."
    
    if [[ ! -f "$SCRIPT_DIR/scripts/dashboard.py" ]]; then
        warning "Basic dashboard script not found, skipping..."
        return 0
    fi
    
    cd "$SCRIPT_DIR/scripts"
    python dashboard.py 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Basic dashboard completed"
        return 0
    else
        error "Basic dashboard failed"
        return 1
    fi
}

# Generate comprehensive report
generate_report() {
    log "Generating comprehensive insights report..."
    
    local report_file="$REPORTS_DIR/insights_report_$(date '+%Y%m%d_%H%M%S').md"
    
    cat > "$report_file" << EOF
# TikTok Insights Report

Generated on: $(date '+%Y-%m-%d %H:%M:%S')

## Analysis Overview

This report contains comprehensive insights from your TikTok video data analysis.

### Data Summary
- Data file: $DATA_FILE
- Charts directory: $CHARTS_DIR
- Outputs directory: $OUTPUTS_DIR

### Available Analyses

#### 1. Improved Dashboard
- **File**: charts/improved_tiktok_dashboard.png
- **Description**: Comprehensive dashboard showing optimal posting times, genre performance, and trending topics
- **Key Features**: 
  - Heatmap of best posting times by day and hour
  - Genre distribution and performance metrics
  - Top topics and hashtags by performance

#### 2. Optimal Posting Times
- **Files**: outputs/optimal_posting_times.png, outputs/posting_frequency_report.json
- **Description**: Analysis of when to post for maximum engagement
- **Insights**: Hour-by-hour and day-by-day performance breakdown

#### 3. Genre Performance Analysis
- **File**: outputs/genre_performance_analysis.png
- **Description**: Comparison of different content genres
- **Metrics**: Average views, engagement rates, performance scores by genre

#### 4. Posting Frequency Analysis
- **File**: outputs/posting_frequency_analysis.png
- **Description**: Impact of posting frequency on performance
- **Insights**: Optimal posting schedules and consistency patterns

## Key Takeaways

1. **Timing Matters**: Post during peak hours for your target audience
2. **Genre Selection**: Choose high-performing content categories
3. **Consistency**: Maintain regular posting schedules
4. **Trending Topics**: Incorporate popular themes and hashtags

## Next Steps

1. Review all generated charts and analyses
2. Implement recommendations in your content strategy
3. Monitor performance improvements
4. Re-run analysis periodically to identify new trends

---

For questions or issues, check the log file: $LOG_FILE
EOF
    
    success "Report generated: $report_file"
    
    # Also create a simple summary
    create_summary_stats
}

# Create summary statistics
create_summary_stats() {
    log "Creating summary statistics..."
    
    local summary_file="$OUTPUTS_DIR/summary_stats.json"
    
    # Use Python to generate basic stats
    python -c "
import json
import os
from datetime import datetime

try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    # Basic statistics
    total_videos = len(data)
    total_views = sum(video.get('view_count', 0) for video in data)
    total_likes = sum(video.get('like_count', 0) for video in data)
    total_comments = sum(video.get('comment_count', 0) for video in data)
    
    avg_views = total_views / total_videos if total_videos > 0 else 0
    avg_likes = total_likes / total_videos if total_videos > 0 else 0
    avg_comments = total_comments / total_videos if total_videos > 0 else 0
    
    # Engagement rate
    avg_engagement = (total_likes + total_comments) / total_views if total_views > 0 else 0
    
    summary = {
        'generated_at': datetime.now().isoformat(),
        'data_file': '$DATA_FILE',
        'total_videos': total_videos,
        'total_views': total_views,
        'total_likes': total_likes,
        'total_comments': total_comments,
        'averages': {
            'views_per_video': round(avg_views, 2),
            'likes_per_video': round(avg_likes, 2),
            'comments_per_video': round(avg_comments, 2),
            'engagement_rate': round(avg_engagement * 100, 4)
        },
        'files_generated': {
            'charts_dir': '$CHARTS_DIR',
            'outputs_dir': '$OUTPUTS_DIR',
            'reports_dir': '$REPORTS_DIR'
        }
    }
    
    with open('$summary_file', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f'Summary statistics saved to: $summary_file')
    print(f'Total videos analyzed: {total_videos:,}')
    print(f'Average views per video: {avg_views:,.0f}')
    print(f'Average engagement rate: {avg_engagement*100:.2f}%')
    
except Exception as e:
    print(f'Error generating summary: {e}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Summary statistics created"
    else
        warning "Failed to create summary statistics"
    fi
}

# Open generated files (macOS/Linux)
open_results() {
    log "Opening generated results..."
    
    # Find the most recent dashboard
    local dashboard=$(find "$CHARTS_DIR" -name "improved_tiktok_dashboard.png" -o -name "*dashboard*.png" | head -n 1)
    
    if [[ -n "$dashboard" ]] && [[ -f "$dashboard" ]]; then
        log "Opening dashboard: $dashboard"
        
        # Try different open commands based on OS
        if command -v open >/dev/null 2>&1; then
            # macOS
            open "$dashboard"
        elif command -v xdg-open >/dev/null 2>&1; then
            # Linux
            xdg-open "$dashboard"
        elif command -v start >/dev/null 2>&1; then
            # Windows (Git Bash)
            start "$dashboard"
        else
            warning "Cannot auto-open files. Please manually check: $dashboard"
        fi
    else
        warning "No dashboard files found to open"
    fi
    
    # Open outputs directory
    if [[ -d "$OUTPUTS_DIR" ]]; then
        log "Results available in: $OUTPUTS_DIR"
        log "Charts available in: $CHARTS_DIR"
    fi
}

# Clean old results
clean_old_results() {
    local days="${1:-7}"
    
    log "Cleaning results older than $days days..."
    
    # Clean old charts
    if [[ -d "$CHARTS_DIR" ]]; then
        find "$CHARTS_DIR" -name "*.png" -type f -mtime +$days -delete
    fi
    
    # Clean old outputs
    if [[ -d "$OUTPUTS_DIR" ]]; then
        find "$OUTPUTS_DIR" -name "*.png" -type f -mtime +$days -delete
        find "$OUTPUTS_DIR" -name "*.json" -type f -mtime +$days -delete
    fi
    
    # Clean old reports
    if [[ -d "$REPORTS_DIR" ]]; then
        find "$REPORTS_DIR" -name "*.md" -type f -mtime +$days -delete
    fi
    
    success "Old results cleaned"
}

# Run quick analysis
quick_analysis() {
    log "Running quick TikTok insights analysis..."
    
    setup_directories
    
    # Try improved dashboard first
    if run_improved_dashboard; then
        success "Quick analysis completed with improved dashboard"
    else
        warning "Improved dashboard failed, trying basic dashboard..."
        if run_basic_dashboard; then
            success "Quick analysis completed with basic dashboard"
        else
            error "Both dashboard attempts failed"
            return 1
        fi
    fi
    
    create_summary_stats
    generate_report
    
    success "Quick analysis completed"
}

# Run full analysis
full_analysis() {
    log "Running comprehensive TikTok insights analysis..."
    
    setup_directories
    
    local success_count=0
    local total_analyses=4
    
    # Run all analyses
    if run_improved_dashboard; then
        success_count=$((success_count + 1))
    fi
    
    if analyze_posting_times; then
        success_count=$((success_count + 1))
    fi
    
    if analyze_genre_performance; then
        success_count=$((success_count + 1))
    fi
    
    if analyze_posting_frequency; then
        success_count=$((success_count + 1))
    fi
    
    # Generate report regardless
    create_summary_stats
    generate_report
    
    log "Full analysis completed: $success_count/$total_analyses analyses successful"
    
    if [[ $success_count -gt 0 ]]; then
        success "Full analysis completed with $success_count successful analyses"
        return 0
    else
        error "All analyses failed"
        return 1
    fi
}

# Show usage
show_usage() {
    cat << EOF
TikTok Insights Dashboard

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    quick
        Run quick analysis with improved dashboard

    full
        Run comprehensive analysis with all insights

    dashboard
        Run improved dashboard only

    posting-times
        Analyze optimal posting times

    genres
        Analyze genre performance

    frequency
        Analyze posting frequency patterns

    basic
        Run basic dashboard (fallback)

    report
        Generate insights report from existing data

    clean [days]
        Clean results older than specified days (default: 7)

    open
        Open generated results

Examples:
    $0 quick
    $0 full
    $0 dashboard
    $0 posting-times
    $0 clean 14
    $0 open

Files Generated:
    - Charts: $CHARTS_DIR/
    - Data: $OUTPUTS_DIR/
    - Reports: $REPORTS_DIR/

EOF
}

# Main script logic
main() {
    # Create log file directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting TikTok Insights Dashboard"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "quick")
            quick_analysis
            ;;
        "full")
            full_analysis
            ;;
        "dashboard")
            setup_directories
            run_improved_dashboard
            ;;
        "posting-times")
            setup_directories
            analyze_posting_times
            ;;
        "genres")
            setup_directories
            analyze_genre_performance
            ;;
        "frequency")
            setup_directories
            analyze_posting_frequency
            ;;
        "basic")
            setup_directories
            run_basic_dashboard
            ;;
        "report")
            generate_report
            ;;
        "clean")
            clean_old_results "${2:-7}"
            ;;
        "open")
            open_results
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Running quick analysis..."
            quick_analysis
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "TikTok insights dashboard completed"
}

# Run main function with all arguments
main "$@"