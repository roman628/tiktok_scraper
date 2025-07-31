#!/bin/bash

# TikTok Data Cleanup Scripts - Automation Script
# Handles data cleaning, deduplication, and quality improvement

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DATA_FILE="$PROJECT_ROOT/master2.json"
BACKUP_DIR="$PROJECT_ROOT/backups"
LOG_FILE="$PROJECT_ROOT/cleanup.log"

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
    python -c "import json, pandas" 2>/dev/null || {
        error "Missing Python dependencies. Please install: pip install pandas"
        exit 1
    }
    
    success "Dependencies check passed"
}

# Create backup
create_backup() {
    local backup_name="${1:-$(date '+%Y%m%d_%H%M%S')}"
    
    log "Creating backup: $backup_name"
    
    mkdir -p "$BACKUP_DIR"
    local backup_file="$BACKUP_DIR/master2.json.backup_$backup_name"
    
    cp "$DATA_FILE" "$backup_file"
    
    success "Backup created: $backup_file"
    echo "$backup_file"
}

# Remove duplicates
remove_duplicates() {
    local backup="${1:-true}"
    local method="${2:-video_id}"
    
    log "Removing duplicates..."
    log "Backup enabled: $backup"
    log "Deduplication method: $method"
    
    # Create backup if requested
    if [[ "$backup" == "true" ]]; then
        create_backup "before_dedupe"
    fi
    
    if [[ ! -f "$SCRIPT_DIR/remove_duplicates.py" ]]; then
        error "Remove duplicates script not found: $SCRIPT_DIR/remove_duplicates.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python remove_duplicates.py \
        --input "$DATA_FILE" \
        --method "$method" \
        --backup "$backup" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Duplicate removal completed"
        return 0
    else
        error "Duplicate removal failed"
        return 1
    fi
}

# Deduplicate using advanced method
deduplicate_advanced() {
    local threshold="${1:-0.95}"
    local backup="${2:-true}"
    
    log "Running advanced deduplication..."
    log "Similarity threshold: $threshold"
    log "Backup enabled: $backup"
    
    # Create backup if requested
    if [[ "$backup" == "true" ]]; then
        create_backup "before_advanced_dedupe"
    fi
    
    if [[ ! -f "$SCRIPT_DIR/deduplicate.py" ]]; then
        error "Advanced deduplicate script not found: $SCRIPT_DIR/deduplicate.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python deduplicate.py \
        --input "$DATA_FILE" \
        --threshold "$threshold" \
        --backup "$backup" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Advanced deduplication completed"
        return 0
    else
        error "Advanced deduplication failed"
        return 1
    fi
}

# Fix JSON formatting issues
fix_json() {
    local backup="${1:-true}"
    local validate="${2:-true}"
    
    log "Fixing JSON formatting issues..."
    log "Backup enabled: $backup"
    log "Validation enabled: $validate"
    
    # Create backup if requested
    if [[ "$backup" == "true" ]]; then
        create_backup "before_json_fix"
    fi
    
    if [[ ! -f "$SCRIPT_DIR/fix_json.py" ]]; then
        error "JSON fix script not found: $SCRIPT_DIR/fix_json.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python fix_json.py \
        --input "$DATA_FILE" \
        --validate "$validate" \
        --backup "$backup" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "JSON fix completed"
        return 0
    else
        error "JSON fix failed"
        return 1
    fi
}

# Sanitize JSON data
sanitize_json() {
    local backup="${1:-true}"
    local remove_nulls="${2:-true}"
    local clean_text="${3:-true}"
    
    log "Sanitizing JSON data..."
    log "Backup enabled: $backup"
    log "Remove nulls: $remove_nulls"
    log "Clean text: $clean_text"
    
    # Create backup if requested
    if [[ "$backup" == "true" ]]; then
        create_backup "before_sanitize"
    fi
    
    if [[ ! -f "$SCRIPT_DIR/sanitize_json.py" ]]; then
        error "JSON sanitize script not found: $SCRIPT_DIR/sanitize_json.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python sanitize_json.py \
        --input "$DATA_FILE" \
        --remove-nulls "$remove_nulls" \
        --clean-text "$clean_text" \
        --backup "$backup" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "JSON sanitization completed"
        return 0
    else
        error "JSON sanitization failed"
        return 1
    fi
}

# Clean videos without transcription
clean_no_transcription() {
    local backup="${1:-true}"
    local keep_ratio="${2:-0.3}"
    
    log "Cleaning videos without transcription..."
    log "Backup enabled: $backup"
    log "Keep ratio: $keep_ratio"
    
    # Create backup if requested
    if [[ "$backup" == "true" ]]; then
        create_backup "before_clean_no_transcription"
    fi
    
    if [[ ! -f "$SCRIPT_DIR/clean_no_transcription.py" ]]; then
        error "Clean no transcription script not found: $SCRIPT_DIR/clean_no_transcription.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python clean_no_transcription.py \
        --input "$DATA_FILE" \
        --keep-ratio "$keep_ratio" \
        --backup "$backup" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "No transcription cleanup completed"
        return 0
    else
        error "No transcription cleanup failed"
        return 1
    fi
}

# Run comprehensive cleanup
comprehensive_cleanup() {
    local create_backups="${1:-true}"
    
    log "Running comprehensive cleanup workflow..."
    
    local success_count=0
    local total_operations=5
    
    # Step 1: Fix JSON formatting
    log "Step 1/5: Fixing JSON formatting..."
    if fix_json "$create_backups" true; then
        success_count=$((success_count + 1))
    fi
    
    # Step 2: Sanitize data
    log "Step 2/5: Sanitizing data..."
    if sanitize_json "$create_backups" true true; then
        success_count=$((success_count + 1))
    fi
    
    # Step 3: Remove basic duplicates
    log "Step 3/5: Removing basic duplicates..."
    if remove_duplicates "$create_backups" "video_id"; then
        success_count=$((success_count + 1))
    fi
    
    # Step 4: Advanced deduplication
    log "Step 4/5: Advanced deduplication..."
    if deduplicate_advanced 0.95 "$create_backups"; then
        success_count=$((success_count + 1))
    fi
    
    # Step 5: Clean videos without transcription
    log "Step 5/5: Cleaning videos without transcription..."
    if clean_no_transcription "$create_backups" 0.2; then
        success_count=$((success_count + 1))
    fi
    
    log "Comprehensive cleanup completed: $success_count/$total_operations operations successful"
    
    # Generate cleanup report
    generate_cleanup_report
    
    if [[ $success_count -gt 0 ]]; then
        success "Comprehensive cleanup completed successfully"
        return 0
    else
        error "All cleanup operations failed"
        return 1
    fi
}

# Quick cleanup (essential operations only)
quick_cleanup() {
    log "Running quick cleanup..."
    
    # Create a single backup for the quick cleanup
    create_backup "before_quick_cleanup"
    
    local success_count=0
    
    # Fix JSON and remove basic duplicates
    if fix_json false true; then
        success_count=$((success_count + 1))
    fi
    
    if remove_duplicates false "video_id"; then
        success_count=$((success_count + 1))
    fi
    
    log "Quick cleanup completed: $success_count/2 operations successful"
    
    if [[ $success_count -gt 0 ]]; then
        success "Quick cleanup completed"
        return 0
    else
        error "Quick cleanup failed"
        return 1
    fi
}

# Generate cleanup report
generate_cleanup_report() {
    log "Generating cleanup report..."
    
    local report_file="$PROJECT_ROOT/cleanup_report_$(date '+%Y%m%d_%H%M%S').json"
    
    # Get statistics
    python -c "
import json
import os
from datetime import datetime

try:
    # Load current data
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    # Basic statistics
    total_videos = len(data)
    with_transcription = sum(1 for v in data if v.get('whisper_transcription'))
    with_comments = sum(1 for v in data if v.get('top_comments'))
    with_video_id = sum(1 for v in data if v.get('video_id'))
    
    # Check for potential issues
    missing_fields = []
    required_fields = ['title', 'view_count', 'like_count']
    for field in required_fields:
        missing = sum(1 for v in data if not v.get(field))
        if missing > 0:
            missing_fields.append({'field': field, 'missing_count': missing})
    
    # Backup information
    backup_files = []
    if os.path.exists('$BACKUP_DIR'):
        backup_files = [f for f in os.listdir('$BACKUP_DIR') if f.startswith('master2.json.backup_')]
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'data_file': '$DATA_FILE',
        'statistics': {
            'total_videos': total_videos,
            'videos_with_transcription': with_transcription,
            'videos_with_comments': with_comments,
            'videos_with_id': with_video_id,
            'transcription_coverage': round(with_transcription / total_videos * 100, 2) if total_videos > 0 else 0,
            'comment_coverage': round(with_comments / total_videos * 100, 2) if total_videos > 0 else 0
        },
        'data_quality': {
            'missing_fields': missing_fields,
            'potential_issues': len(missing_fields)
        },
        'backups': {
            'backup_directory': '$BACKUP_DIR',
            'backup_count': len(backup_files),
            'recent_backups': sorted(backup_files)[-5:] if backup_files else []
        }
    }
    
    with open('$report_file', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f'Cleanup report generated: $report_file')
    print(f'Total videos: {total_videos:,}')
    print(f'Transcription coverage: {report[\"statistics\"][\"transcription_coverage\"]}%')
    print(f'Data quality issues: {len(missing_fields)}')
    
except Exception as e:
    print(f'Error generating report: {e}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Cleanup report generated: $report_file"
    else
        warning "Failed to generate cleanup report"
    fi
}

# Show data statistics
show_stats() {
    log "Showing data statistics..."
    
    python -c "
import json

try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    total = len(data)
    with_transcription = sum(1 for v in data if v.get('whisper_transcription'))
    with_comments = sum(1 for v in data if v.get('top_comments'))
    with_video_id = sum(1 for v in data if v.get('video_id'))
    
    # View statistics
    views = [v.get('view_count', 0) for v in data if v.get('view_count')]
    avg_views = sum(views) / len(views) if views else 0
    
    print()
    print('=== DATA STATISTICS ===')
    print(f'Total videos: {total:,}')
    print(f'With transcription: {with_transcription:,} ({with_transcription/total*100:.1f}%)')
    print(f'With comments: {with_comments:,} ({with_comments/total*100:.1f}%)')
    print(f'With video ID: {with_video_id:,} ({with_video_id/total*100:.1f}%)')
    print(f'Average views: {avg_views:,.0f}')
    print('========================')
    
except Exception as e:
    print(f'Error: {e}')
" 2>&1 | tee -a "$LOG_FILE"
    
    # Show backup information
    if [[ -d "$BACKUP_DIR" ]]; then
        echo
        echo "=== BACKUP FILES ==="
        ls -la "$BACKUP_DIR" | tail -5
        echo "===================="
    fi
}

# Restore from backup
restore_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        # Show available backups
        log "Available backups:"
        if [[ -d "$BACKUP_DIR" ]]; then
            ls -la "$BACKUP_DIR"
        else
            error "No backup directory found"
        fi
        return 1
    fi
    
    # Handle relative paths
    if [[ ! "$backup_file" = /* ]]; then
        backup_file="$BACKUP_DIR/$backup_file"
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        error "Backup file not found: $backup_file"
        return 1
    fi
    
    log "Restoring from backup: $backup_file"
    
    # Create backup of current state
    create_backup "before_restore"
    
    # Restore from backup
    cp "$backup_file" "$DATA_FILE"
    
    success "Restore completed from: $backup_file"
}

# Clean old backups
clean_backups() {
    local days="${1:-30}"
    local keep_count="${2:-10}"
    
    log "Cleaning old backups..."
    log "Remove backups older than $days days"
    log "Keep at least $keep_count most recent backups"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        warning "No backup directory found"
        return 0
    fi
    
    # Remove old backups
    find "$BACKUP_DIR" -name "master2.json.backup_*" -type f -mtime +$days -delete
    
    # Keep only the most recent backups
    local backup_count=$(ls -1 "$BACKUP_DIR"/master2.json.backup_* 2>/dev/null | wc -l)
    
    if [[ $backup_count -gt $keep_count ]]; then
        local to_remove=$((backup_count - keep_count))
        ls -1t "$BACKUP_DIR"/master2.json.backup_* | tail -n $to_remove | xargs -r rm
        log "Removed $to_remove old backups"
    fi
    
    success "Backup cleanup completed"
}

# Show usage
show_usage() {
    cat << EOF
TikTok Data Cleanup Scripts

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    remove-duplicates [backup] [method]
        Remove duplicate videos
        backup: Create backup (true/false, default: true)
        method: Deduplication method (video_id/title, default: video_id)

    deduplicate [threshold] [backup]
        Advanced deduplication with similarity threshold
        threshold: Similarity threshold 0-1 (default: 0.95)
        backup: Create backup (true/false, default: true)

    fix-json [backup] [validate]
        Fix JSON formatting issues
        backup: Create backup (true/false, default: true)
        validate: Validate JSON (true/false, default: true)

    sanitize [backup] [remove_nulls] [clean_text]
        Sanitize JSON data
        backup: Create backup (true/false, default: true)
        remove_nulls: Remove null values (true/false, default: true)
        clean_text: Clean text fields (true/false, default: true)

    clean-no-transcription [backup] [keep_ratio]
        Clean videos without transcription
        backup: Create backup (true/false, default: true)
        keep_ratio: Ratio of videos to keep (default: 0.3)

    comprehensive [backup]
        Run all cleanup operations
        backup: Create backups for each step (true/false, default: true)

    quick
        Run quick cleanup (essential operations only)

    backup [name]
        Create manual backup
        name: Backup name (default: timestamp)

    restore <backup_file>
        Restore from backup file

    stats
        Show data statistics

    report
        Generate cleanup report

    clean-backups [days] [keep_count]
        Clean old backup files
        days: Remove backups older than X days (default: 30)
        keep_count: Keep X most recent backups (default: 10)

Examples:
    $0 comprehensive true
    $0 quick
    $0 remove-duplicates true video_id
    $0 fix-json true true
    $0 backup pre_cleanup
    $0 restore master2.json.backup_20240101_120000
    $0 stats
    $0 clean-backups 14 5

Files:
    - Data: $DATA_FILE
    - Backups: $BACKUP_DIR
    - Log: $LOG_FILE

EOF
}

# Main script logic
main() {
    # Create log and backup directories
    mkdir -p "$(dirname "$LOG_FILE")"
    mkdir -p "$BACKUP_DIR"
    
    log "Starting TikTok Data Cleanup"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    log "Backup directory: $BACKUP_DIR"
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "remove-duplicates")
            remove_duplicates "${2:-true}" "${3:-video_id}"
            ;;
        "deduplicate")
            deduplicate_advanced "${2:-0.95}" "${3:-true}"
            ;;
        "fix-json")
            fix_json "${2:-true}" "${3:-true}"
            ;;
        "sanitize")
            sanitize_json "${2:-true}" "${3:-true}" "${4:-true}"
            ;;
        "clean-no-transcription")
            clean_no_transcription "${2:-true}" "${3:-0.3}"
            ;;
        "comprehensive")
            comprehensive_cleanup "${2:-true}"
            ;;
        "quick")
            quick_cleanup
            ;;
        "backup")
            create_backup "${2:-$(date '+%Y%m%d_%H%M%S')}"
            ;;
        "restore")
            if [[ -z "$2" ]]; then
                error "Backup file required for restore"
                show_usage
                exit 1
            fi
            restore_backup "$2"
            ;;
        "stats")
            show_stats
            ;;
        "report")
            generate_cleanup_report
            ;;
        "clean-backups")
            clean_backups "${2:-30}" "${3:-10}"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Showing data statistics..."
            show_stats
            ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
    
    log "Cleanup scripts completed"
}

# Run main function with all arguments
main "$@"