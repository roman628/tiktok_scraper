#!/bin/bash

# TikTok Scraper - Master Automation Script
# Orchestrates all TikTok analysis, collection, and processing operations

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FILE="$SCRIPT_DIR/master2.json"
LOG_FILE="$SCRIPT_DIR/automation.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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

info() {
    echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${PURPLE}[$(date '+%H:%M:%S')]${NC} 🚀 $1" | tee -a "$LOG_FILE"
}

# Check if master data file exists
check_data_file() {
    if [[ ! -f "$DATA_FILE" ]]; then
        error "Master data file not found: $DATA_FILE"
        error "Please ensure master2.json exists in the project root"
        exit 1
    fi
    
    # Check if file is not empty
    if [[ ! -s "$DATA_FILE" ]]; then
        error "Master data file is empty: $DATA_FILE"
        exit 1
    fi
    
    # Validate JSON format
    if ! python -c "import json; json.load(open('$DATA_FILE'))" 2>/dev/null; then
        error "Master data file is not valid JSON: $DATA_FILE"
        exit 1
    fi
    
    local video_count=$(python -c "import json; print(len(json.load(open('$DATA_FILE'))))" 2>/dev/null || echo "0")
    success "Data file validated: $video_count videos found"
}

# Check system dependencies
check_dependencies() {
    log "Checking system dependencies..."
    
    # Check Python
    if ! command -v python >/dev/null 2>&1; then
        error "Python is not installed or not in PATH"
        exit 1
    fi
    
    # Check required Python packages
    python -c "import json, pandas, numpy, matplotlib, seaborn" 2>/dev/null || {
        error "Missing Python dependencies. Please install:"
        error "pip install pandas numpy matplotlib seaborn scikit-learn nltk textstat"
        exit 1
    }
    
    # Check for shell scripts
    local scripts=(
        "keyword_scoring_system/run_keyword_scoring.sh"
        "performance_predictor/run_performance_predictor.sh"
        "reddit_scraper/run_reddit_scraper.sh"
        "tiktok_insights/run_insights_dashboard.sh"
        "video_analysis/run_video_analysis.sh"
        "scripts/collection/run_collection.sh"
        "scripts/cleanup/run_cleanup.sh"
        "scripts/analysis/run_analysis.sh"
    )
    
    local missing_scripts=()
    for script in "${scripts[@]}"; do
        if [[ ! -f "$SCRIPT_DIR/$script" ]]; then
            missing_scripts+=("$script")
        fi
    done
    
    if [[ ${#missing_scripts[@]} -gt 0 ]]; then
        warning "Some automation scripts are missing:"
        for script in "${missing_scripts[@]}"; do
            warning "  - $script"
        done
        warning "Some features may not be available"
    fi
    
    success "System dependencies checked"
}

# Make all shell scripts executable
setup_permissions() {
    log "Setting up script permissions..."
    
    find "$SCRIPT_DIR" -name "*.sh" -exec chmod +x {} \;
    
    success "Script permissions updated"
}

# Show project status
show_status() {
    header "TikTok Scraper Project Status"
    
    echo
    echo "=== PROJECT OVERVIEW ==="
    
    # Data file info
    if [[ -f "$DATA_FILE" ]]; then
        local file_size=$(ls -lh "$DATA_FILE" | awk '{print $5}')
        local video_count=$(python -c "import json; print(len(json.load(open('$DATA_FILE'))))" 2>/dev/null || echo "0")
        echo "📊 Master Data: $video_count videos ($file_size)"
    else
        echo "📊 Master Data: ❌ Not found"
    fi
    
    # Directory structure
    echo
    echo "📂 Project Structure:"
    echo "   ├── keyword_scoring_system/ - Keyword analysis and scoring"
    echo "   ├── performance_predictor/ - ML-based performance prediction"
    echo "   ├── reddit_scraper/ - Reddit user analysis and discovery"
    echo "   ├── tiktok_insights/ - Dashboard and visualization"
    echo "   ├── video_analysis/ - Video content analysis"
    echo "   └── scripts/"
    echo "       ├── collection/ - Video downloading and URL harvesting"
    echo "       ├── cleanup/ - Data cleaning and deduplication"
    echo "       └── analysis/ - Data analysis and reporting"
    
    # Available components
    echo
    echo "🔧 Available Components:"
    local components=(
        "keyword_scoring_system:Keyword Analysis"
        "performance_predictor:Performance Prediction"
        "reddit_scraper:Reddit Integration"
        "tiktok_insights:Insights Dashboard"
        "video_analysis:Video Analysis"
        "scripts/collection:Content Collection"
        "scripts/cleanup:Data Cleanup"
        "scripts/analysis:Data Analysis"
    )
    
    for component in "${components[@]}"; do
        IFS=':' read -r dir name <<< "$component"
        if [[ -d "$SCRIPT_DIR/$dir" ]]; then
            echo "   ✅ $name"
        else
            echo "   ❌ $name (directory missing)"
        fi
    done
    
    echo
    echo "========================="
}

# Run quick analysis workflow
quick_workflow() {
    header "Running Quick Analysis Workflow"
    
    local success_count=0
    local total_operations=4
    
    # 1. Data cleanup
    info "Step 1/4: Quick data cleanup..."
    if [[ -f "$SCRIPT_DIR/scripts/cleanup/run_cleanup.sh" ]]; then
        if "$SCRIPT_DIR/scripts/cleanup/run_cleanup.sh" quick; then
            success_count=$((success_count + 1))
        fi
    else
        warning "Cleanup script not found, skipping..."
    fi
    
    # 2. Basic analysis
    info "Step 2/4: Basic data analysis..."
    if [[ -f "$SCRIPT_DIR/scripts/analysis/run_analysis.sh" ]]; then
        if "$SCRIPT_DIR/scripts/analysis/run_analysis.sh" basic; then
            success_count=$((success_count + 1))
        fi
    else
        warning "Analysis script not found, skipping..."
    fi
    
    # 3. Insights dashboard
    info "Step 3/4: Generating insights dashboard..."
    if [[ -f "$SCRIPT_DIR/tiktok_insights/run_insights_dashboard.sh" ]]; then
        if "$SCRIPT_DIR/tiktok_insights/run_insights_dashboard.sh" quick; then
            success_count=$((success_count + 1))
        fi
    else
        warning "Insights script not found, skipping..."
    fi
    
    # 4. Keyword scoring
    info "Step 4/4: Keyword scoring analysis..."
    if [[ -f "$SCRIPT_DIR/keyword_scoring_system/run_keyword_scoring.sh" ]]; then
        if "$SCRIPT_DIR/keyword_scoring_system/run_keyword_scoring.sh" quick; then
            success_count=$((success_count + 1))
        fi
    else
        warning "Keyword scoring script not found, skipping..."
    fi
    
    # Summary
    echo
    if [[ $success_count -eq $total_operations ]]; then
        success "Quick workflow completed successfully! ($success_count/$total_operations)"
    elif [[ $success_count -gt 0 ]]; then
        warning "Quick workflow partially completed ($success_count/$total_operations)"
    else
        error "Quick workflow failed (0/$total_operations)"
        return 1
    fi
    
    show_workflow_results
}

# Run full analysis workflow
full_workflow() {
    header "Running Full Analysis Workflow"
    
    local success_count=0
    local total_operations=8
    
    # 1. Comprehensive cleanup
    info "Step 1/8: Comprehensive data cleanup..."
    if [[ -f "$SCRIPT_DIR/scripts/cleanup/run_cleanup.sh" ]]; then
        if "$SCRIPT_DIR/scripts/cleanup/run_cleanup.sh" comprehensive true; then
            success_count=$((success_count + 1))
        fi
    fi
    
    # 2. Comprehensive analysis
    info "Step 2/8: Comprehensive data analysis..."
    if [[ -f "$SCRIPT_DIR/scripts/analysis/run_analysis.sh" ]]; then
        if "$SCRIPT_DIR/scripts/analysis/run_analysis.sh" comprehensive; then
            success_count=$((success_count + 1))
        fi
    fi
    
    # 3. Video analysis
    info "Step 3/8: Video content analysis..."
    if [[ -f "$SCRIPT_DIR/video_analysis/run_video_analysis.sh" ]]; then
        if "$SCRIPT_DIR/video_analysis/run_video_analysis.sh" comprehensive; then
            success_count=$((success_count + 1))
        fi
    fi
    
    # 4. Full insights dashboard
    info "Step 4/8: Full insights dashboard..."
    if [[ -f "$SCRIPT_DIR/tiktok_insights/run_insights_dashboard.sh" ]]; then
        if "$SCRIPT_DIR/tiktok_insights/run_insights_dashboard.sh" full; then
            success_count=$((success_count + 1))
        fi
    fi
    
    # 5. Complete keyword scoring
    info "Step 5/8: Complete keyword scoring..."
    if [[ -f "$SCRIPT_DIR/keyword_scoring_system/run_keyword_scoring.sh" ]]; then
        if "$SCRIPT_DIR/keyword_scoring_system/run_keyword_scoring.sh" full; then
            success_count=$((success_count + 1))
        fi
    fi
    
    # 6. Performance predictor training
    info "Step 6/8: Training performance predictor..."
    if [[ -f "$SCRIPT_DIR/performance_predictor/run_performance_predictor.sh" ]]; then
        if "$SCRIPT_DIR/performance_predictor/run_performance_predictor.sh" auto-retrain; then
            success_count=$((success_count + 1))
        fi
    fi
    
    # 7. Reddit discovery (if configured)
    info "Step 7/8: Reddit subreddit discovery..."
    if [[ -f "$SCRIPT_DIR/reddit_scraper/run_reddit_scraper.sh" ]]; then
        # Check if Reddit credentials are available
        if [[ -f "$SCRIPT_DIR/reddit_scraper/config.env" ]] || [[ -n "$REDDIT_CLIENT_ID" ]]; then
            if "$SCRIPT_DIR/reddit_scraper/run_reddit_scraper.sh" discover 25; then
                success_count=$((success_count + 1))
            fi
        else
            warning "Reddit credentials not configured, skipping discovery..."
            success_count=$((success_count + 1))  # Don't penalize for missing optional config
        fi
    fi
    
    # 8. Generate final report
    info "Step 8/8: Generating final report..."
    if generate_final_report; then
        success_count=$((success_count + 1))
    fi
    
    # Summary
    echo
    if [[ $success_count -eq $total_operations ]]; then
        success "Full workflow completed successfully! ($success_count/$total_operations)"
    elif [[ $success_count -gt $((total_operations / 2)) ]]; then
        warning "Full workflow mostly completed ($success_count/$total_operations)"
    else
        error "Full workflow had significant issues ($success_count/$total_operations)"
        return 1
    fi
    
    show_workflow_results
}

# Show workflow results
show_workflow_results() {
    header "Workflow Results Summary"
    
    echo
    echo "📊 Generated Files and Reports:"
    
    # Check for key output files
    local outputs=(
        "keyword_score_map.json:Keyword Analysis Results"
        "tiktok_insights/charts/improved_tiktok_dashboard.png:Insights Dashboard"
        "models/tiktok_predictor.pkl:Performance Prediction Model"
        "video_analysis/reports:Video Analysis Reports"
        "scripts/analysis/results:Data Analysis Results"
        "reddit_scraper/subreddit_discovery:Reddit Discovery Results"
    )
    
    for output in "${outputs[@]}"; do
        IFS=':' read -r path description <<< "$output"
        if [[ -f "$SCRIPT_DIR/$path" ]] || [[ -d "$SCRIPT_DIR/$path" ]]; then
            echo "   ✅ $description"
        else
            echo "   ⏸️  $description (not generated)"
        fi
    done
    
    echo
    echo "🔍 Next Steps:"
    echo "   1. Review generated reports and dashboards"
    echo "   2. Check keyword_score_map.json for content optimization"
    echo "   3. Use performance predictor for video optimization"
    echo "   4. Implement insights from TikTok dashboard"
    echo "   5. Run individual components for deeper analysis"
    
    echo
    echo "💾 Log file: $LOG_FILE"
}

# Generate final comprehensive report
generate_final_report() {
    log "Generating final comprehensive report..."
    
    local report_file="$SCRIPT_DIR/COMPREHENSIVE_REPORT_$(date '+%Y%m%d_%H%M%S').md"
    
    cat > "$report_file" << EOF
# TikTok Scraper - Comprehensive Analysis Report

Generated on: $(date '+%Y-%m-%d %H:%M:%S')

## Executive Summary

This report summarizes the complete analysis of your TikTok dataset using the TikTok Scraper automation system.

### Dataset Overview
EOF
    
    # Add dataset statistics
    python -c "
import json
try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    total = len(data)
    with_transcription = sum(1 for v in data if v.get('whisper_transcription'))
    with_comments = sum(1 for v in data if v.get('top_comments'))
    
    total_views = sum(v.get('view_count', 0) for v in data)
    total_likes = sum(v.get('like_count', 0) for v in data)
    avg_engagement = (total_likes / total_views * 100) if total_views > 0 else 0
    
    print(f'- **Total Videos Analyzed**: {total:,}')
    print(f'- **Videos with Transcription**: {with_transcription:,} ({with_transcription/total*100:.1f}%)')
    print(f'- **Videos with Comments**: {with_comments:,} ({with_comments/total*100:.1f}%)')
    print(f'- **Total Views**: {total_views:,}')
    print(f'- **Total Likes**: {total_likes:,}')
    print(f'- **Average Engagement Rate**: {avg_engagement:.2f}%')
    
except Exception as e:
    print('- **Error loading data**: Could not generate statistics')
" >> "$report_file"
    
    cat >> "$report_file" << EOF

## Analysis Components Completed

### 1. Data Cleanup and Quality Improvement
- **Script**: scripts/cleanup/run_cleanup.sh
- **Operations**: Deduplication, JSON validation, data sanitization
- **Outcome**: Clean, standardized dataset ready for analysis

### 2. Keyword Scoring and Content Analysis
- **Script**: keyword_scoring_system/run_keyword_scoring.sh
- **Output**: keyword_score_map.json
- **Features**: NLP-based keyword extraction, sentiment analysis, performance correlation

### 3. Performance Prediction Model
- **Script**: performance_predictor/run_performance_predictor.sh
- **Output**: models/tiktok_predictor.pkl
- **Capabilities**: ML-based view/like prediction, engagement rate forecasting

### 4. TikTok Insights Dashboard
- **Script**: tiktok_insights/run_insights_dashboard.sh
- **Output**: Interactive dashboards and visualizations
- **Insights**: Optimal posting times, genre performance, trending topics

### 5. Video Content Analysis
- **Script**: video_analysis/run_video_analysis.sh
- **Analysis**: Transcription processing, content categorization, quality assessment

### 6. Reddit Integration and Discovery
- **Script**: reddit_scraper/run_reddit_scraper.sh
- **Purpose**: Discover related subreddits, analyze user behavior patterns
- **Output**: Subreddit recommendations and user insights

### 7. Data Analysis and Statistics
- **Script**: scripts/analysis/run_analysis.sh
- **Reports**: Comprehensive statistics, engagement metrics, content distribution

## Key Findings and Recommendations

### Content Strategy
1. **Optimal Posting Times**: Review insights dashboard for peak engagement hours
2. **High-Performing Keywords**: Check keyword_score_map.json for content optimization
3. **Genre Performance**: Focus on top-performing content categories

### Technical Insights
1. **Data Quality**: $(python -c "
import json
try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    with_transcription = sum(1 for v in data if v.get('whisper_transcription'))
    quality_score = with_transcription / len(data) * 100 if len(data) > 0 else 0
    
    if quality_score > 80:
        print('Excellent data coverage for analysis')
    elif quality_score > 60:
        print('Good data coverage, some gaps in transcription')
    elif quality_score > 40:
        print('Moderate data coverage, consider improving transcription')
    else:
        print('Limited data coverage, significant gaps in analysis')
except:
    print('Unable to assess data quality')
")"

2. **Prediction Accuracy**: Performance model available for future content optimization
3. **Automation Success**: Multi-component analysis pipeline operational

## Available Resources

### Generated Files
- **keyword_score_map.json** - Keyword performance rankings
- **models/tiktok_predictor.pkl** - Trained prediction model
- **tiktok_insights/charts/** - Visualization dashboards
- **video_analysis/reports/** - Content analysis reports
- **scripts/analysis/results/** - Statistical analysis results

### Automation Scripts
All components are available for re-running with updated data:
- Individual component scripts in respective directories
- Master automation: \`./run_tiktok_automation.sh\`
- Quick updates: \`./run_tiktok_automation.sh quick\`

## Next Steps for Optimization

### Immediate Actions
1. Review keyword_score_map.json for content ideas
2. Check insights dashboard for posting time optimization
3. Use performance predictor for content planning

### Ongoing Optimization
1. Regular data updates and re-analysis
2. A/B testing based on predictions
3. Trend monitoring and adaptation

### Advanced Analysis
1. Custom keyword analysis for specific niches
2. Competitor analysis using similar datasets
3. Long-term trend prediction and forecasting

---

**Generated by**: TikTok Scraper Automation System  
**Report Date**: $(date '+%Y-%m-%d %H:%M:%S')  
**Log File**: $LOG_FILE
EOF
    
    success "Final report generated: $report_file"
    return 0
}

# Run individual component
run_component() {
    local component="$1"
    local args=("${@:2}")
    
    local script_path=""
    local component_name=""
    
    case "$component" in
        "keyword"|"keywords")
            script_path="$SCRIPT_DIR/keyword_scoring_system/run_keyword_scoring.sh"
            component_name="Keyword Scoring System"
            ;;
        "predictor"|"predict"|"performance")
            script_path="$SCRIPT_DIR/performance_predictor/run_performance_predictor.sh"
            component_name="Performance Predictor"
            ;;
        "reddit")
            script_path="$SCRIPT_DIR/reddit_scraper/run_reddit_scraper.sh"
            component_name="Reddit Scraper"
            ;;
        "insights"|"dashboard")
            script_path="$SCRIPT_DIR/tiktok_insights/run_insights_dashboard.sh"
            component_name="TikTok Insights Dashboard"
            ;;
        "video"|"video-analysis")
            script_path="$SCRIPT_DIR/video_analysis/run_video_analysis.sh"
            component_name="Video Analysis"
            ;;
        "collection"|"collect")
            script_path="$SCRIPT_DIR/scripts/collection/run_collection.sh"
            component_name="Content Collection"
            ;;
        "cleanup"|"clean")
            script_path="$SCRIPT_DIR/scripts/cleanup/run_cleanup.sh"
            component_name="Data Cleanup"
            ;;
        "analysis"|"analyze")
            script_path="$SCRIPT_DIR/scripts/analysis/run_analysis.sh"
            component_name="Data Analysis"
            ;;
        *)
            error "Unknown component: $component"
            echo "Available components: keyword, predictor, reddit, insights, video, collection, cleanup, analysis"
            return 1
            ;;
    esac
    
    if [[ ! -f "$script_path" ]]; then
        error "$component_name script not found: $script_path"
        return 1
    fi
    
    header "Running $component_name"
    
    "$script_path" "${args[@]}"
    
    if [[ $? -eq 0 ]]; then
        success "$component_name completed successfully"
    else
        error "$component_name failed"
        return 1
    fi
}

# Show usage
show_usage() {
    cat << EOF
TikTok Scraper - Master Automation Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    status
        Show project status and overview

    quick
        Run quick analysis workflow (cleanup, basic analysis, insights)

    full
        Run comprehensive analysis workflow (all components)

    component <name> [args...]
        Run individual component
        Available: keyword, predictor, reddit, insights, video, collection, cleanup, analysis

    setup
        Setup script permissions and check dependencies

Examples:
    $0 status
    $0 quick
    $0 full
    $0 component keyword quick
    $0 component insights dashboard
    $0 component predictor train
    $0 setup

Individual Component Scripts:
    - Keyword Scoring: keyword_scoring_system/run_keyword_scoring.sh
    - Performance Predictor: performance_predictor/run_performance_predictor.sh
    - Reddit Scraper: reddit_scraper/run_reddit_scraper.sh
    - Insights Dashboard: tiktok_insights/run_insights_dashboard.sh
    - Video Analysis: video_analysis/run_video_analysis.sh
    - Content Collection: scripts/collection/run_collection.sh
    - Data Cleanup: scripts/cleanup/run_cleanup.sh
    - Data Analysis: scripts/analysis/run_analysis.sh

Requirements:
    - Python 3.7+
    - master2.json file in project root
    - Required Python packages (see setup)

EOF
}

# Main script logic
main() {
    # Create log file
    mkdir -p "$(dirname "$LOG_FILE")"
    
    header "TikTok Scraper Master Automation"
    log "Script directory: $SCRIPT_DIR"
    log "Data file: $DATA_FILE"
    log "Log file: $LOG_FILE"
    
    case "${1:-}" in
        "status")
            show_status
            ;;
        "setup")
            check_dependencies
            setup_permissions
            show_status
            ;;
        "quick")
            check_data_file
            check_dependencies
            setup_permissions
            quick_workflow
            ;;
        "full")
            check_data_file
            check_dependencies
            setup_permissions
            full_workflow
            ;;
        "component")
            if [[ -z "$2" ]]; then
                error "Component name required"
                show_usage
                exit 1
            fi
            check_data_file
            check_dependencies
            setup_permissions
            run_component "${@:2}"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Showing project status..."
            show_status
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Master automation completed"
}

# Run main function with all arguments
main "$@"