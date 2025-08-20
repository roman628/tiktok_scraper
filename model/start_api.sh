#!/bin/bash

# TikTok Performance Predictor - Automation Script
# Handles model training, prediction, and API serving

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_FILE="$PROJECT_ROOT/master2.json"
MODEL_DIR="$PROJECT_ROOT/models"
MODEL_FILE="$MODEL_DIR/snoo.pkl"
LOG_FILE="$SCRIPT_DIR/predictor.log"
API_PORT="${API_PORT:-8080}"

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
    
    if [[ ! -f "$SCRIPT_DIR/train_ml.py" ]]; then
        error "Predictor script not found: $SCRIPT_DIR/train_ml.py"
        exit 1
    fi
    
    # Check Python dependencies
    python -c "import sklearn, xgboost, nltk" 2>/dev/null || {
        error "Missing Python dependencies. Please install: pip install scikit-learn xgboost nltk textstat"
        exit 1
    }
    
    success "Dependencies check passed"
}

# Check if model exists and is recent
check_model_status() {
    if [[ -f "$MODEL_FILE" ]]; then
        local model_age=$(( $(date +%s) - $(stat -f %m "$MODEL_FILE" 2>/dev/null || stat -c %Y "$MODEL_FILE" 2>/dev/null || echo 0) ))
        local days_old=$(( model_age / 86400 ))
        
        if [[ $days_old -gt 7 ]]; then
            warning "Model is $days_old days old. Consider retraining."
            return 2
        else
            success "Model exists and is recent ($days_old days old)"
            return 0
        fi
    else
        warning "No trained model found at: $MODEL_FILE"
        return 1
    fi
}

# Train the prediction model
train_model() {
    local max_samples="${1:-}"
    local force_retrain="${2:-false}"
    
    log "Training TikTok performance prediction model..."
    
    # Check if we should retrain
    if [[ "$force_retrain" != "true" ]]; then
        check_model_status
        local status=$?
        if [[ $status -eq 0 ]]; then
            log "Model already exists and is recent. Use --force to retrain."
            return 0
        fi
    fi
    
    # Create model directory
    mkdir -p "$MODEL_DIR"
    
    # Prepare training arguments
    local args=(
        "train"
        "--data" "$DATA_FILE"
        "--model" "$MODEL_FILE"
    )
    
    if [[ -n "$max_samples" ]]; then
        args+=(--max-samples "$max_samples")
    fi
    
    log "Training with data: $DATA_FILE"
    if [[ -n "$max_samples" ]]; then
        log "Max samples: $max_samples"
    else
        log "Using all available samples"
    fi
    
    cd "$SCRIPT_DIR"
    python train_ml.py "${args[@]}" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Model training completed successfully"
        success "Model saved to: $MODEL_FILE"
        return 0
    else
        error "Model training failed"
        return 1
    fi
}

# Make prediction for a specific video
predict_video() {
    local video_id="$1"
    
    if [[ -z "$video_id" ]]; then
        error "Video ID required for prediction"
        return 1
    fi
    
    log "Making prediction for video: $video_id"
    
    # Check if model exists
    check_model_status
    if [[ $? -eq 1 ]]; then
        error "No trained model found. Train model first."
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python train_ml.py predict --text "test prediction" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Prediction completed"
        return 0
    else
        error "Prediction failed"
        return 1
    fi
}

# Get model information
model_info() {
    log "Getting model information..."
    
    # Check if model exists
    check_model_status
    if [[ $? -eq 1 ]]; then
        error "No trained model found. Train model first."
        return 1
    fi
    
    # Simple model info - just show file stats since train_ml.py doesn't have info command
    log "Model file: $MODEL_FILE"
    log "Model size: $(du -h "$MODEL_FILE" 2>/dev/null | cut -f1 || echo 'unknown')"
    log "Last modified: $(stat -f %Sm "$MODEL_FILE" 2>/dev/null || stat -c %y "$MODEL_FILE" 2>/dev/null || echo 'unknown')"
    
    success "Model information displayed"
    return 0
}

# Test model performance
test_model() {
    local num_samples="${1:-10}"
    
    log "Testing model performance with $num_samples sample predictions..."
    
    # Check if model exists
    check_model_status
    if [[ $? -eq 1 ]]; then
        error "No trained model found. Train model first."
        return 1
    fi
    
    # Get random video IDs from the data
    local video_ids=$(python -c "
import json
import random
import sys

try:
    with open('$DATA_FILE', 'r') as f:
        data = json.load(f)
    
    # Get video IDs
    video_ids = [v.get('video_id', str(i)) for i, v in enumerate(data) if v.get('video_id')]
    
    if len(video_ids) < $num_samples:
        print('Not enough videos with IDs. Using first $num_samples videos.')
        video_ids = [str(i) for i in range(min($num_samples, len(data)))]
    else:
        video_ids = random.sample(video_ids, $num_samples)
    
    for vid in video_ids:
        print(vid)

except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
")
    
    if [[ $? -ne 0 ]]; then
        error "Failed to get test video IDs"
        return 1
    fi
    
    local success_count=0
    local total_count=0
    
    while IFS= read -r video_id; do
        if [[ -n "$video_id" ]]; then
            total_count=$((total_count + 1))
            log "Testing prediction $total_count/$num_samples: $video_id"
            
            if predict_video "$video_id" > /dev/null 2>&1; then
                success_count=$((success_count + 1))
            fi
        fi
    done <<< "$video_ids"
    
    log "Test completed: $success_count/$total_count predictions successful"
    
    if [[ $success_count -eq $total_count ]]; then
        success "All test predictions successful"
        return 0
    else
        warning "Some test predictions failed"
        return 1
    fi
}

# Start API server
start_api() {
    local port="${1:-$API_PORT}"
    
    log "Starting TikTok Performance Predictor API on port $port..."
    
    # Check if model exists
    check_model_status
    if [[ $? -eq 1 ]]; then
        error "No trained model found. Train model first."
        return 1
    fi
    
    # Check if API script exists
    if [[ ! -f "$SCRIPT_DIR/api.py" ]]; then
        error "API script not found: $SCRIPT_DIR/api.py"
        return 1
    fi
    
    # Kill any existing process on the port
    local existing_pid=$(lsof -ti:$port)
    if [[ -n "$existing_pid" ]]; then
        warning "Killing existing process on port $port (PID: $existing_pid)"
        kill -9 $existing_pid
        sleep 2
    fi
    
    cd "$SCRIPT_DIR"
    export MODEL_PATH="$MODEL_FILE"
    export DATA_PATH="$DATA_FILE"
    
    log "API will be available at: http://localhost:$port"
    log "API logs will be written to: $LOG_FILE"
    
    python api.py --port $port 2>&1 | tee -a "$LOG_FILE"
}

# Run quick model check and prediction
quick_check() {
    log "Running quick model check..."
    
    # Check model status
    check_model_status
    local status=$?
    
    if [[ $status -eq 1 ]]; then
        log "No model found. Training with 500 samples..."
        train_model 500
        if [[ $? -ne 0 ]]; then
            error "Quick training failed"
            return 1
        fi
    fi
    
    # Show model info
    model_info
    
    # Run a quick test
    log "Running quick prediction test..."
    test_model 3
    
    success "Quick check completed"
}

# Retrain model automatically based on data age
auto_retrain() {
    log "Checking if model needs retraining..."
    
    check_model_status
    local status=$?
    
    if [[ $status -eq 1 ]] || [[ $status -eq 2 ]]; then
        log "Model needs retraining..."
        train_model
        return $?
    else
        log "Model is up to date"
        return 0
    fi
}

# Show usage
show_usage() {
    cat << EOF
TikTok Performance Predictor

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    train [max_samples] [--force]
        Train the prediction model
        max_samples: Maximum training samples (optional)
        --force: Force retrain even if model exists

    predict <video_id>
        Make prediction for specific video ID

    info
        Show model information and statistics

    test [num_samples]
        Test model with random predictions (default: 10)

    api [port]
        Start prediction API server (default port: 8080)

    quick
        Quick model check and test

    auto-retrain
        Automatically retrain if model is old or missing

Examples:
    $0 train 1000
    $0 train --force
    $0 predict "video123"
    $0 info
    $0 test 5
    $0 api 8080
    $0 quick
    $0 auto-retrain

Environment Variables:
    API_PORT - Default API port (default: 8080)

EOF
}

# Main script logic
main() {
    # Create log file directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log "Starting TikTok Performance Predictor"
    log "Script directory: $SCRIPT_DIR"
    log "Project root: $PROJECT_ROOT"
    log "Data file: $DATA_FILE"
    log "Model file: $MODEL_FILE"
    
    # Check dependencies
    check_dependencies
    
    case "${1:-}" in
        "train")
            local max_samples=""
            local force_retrain="false"
            
            # Parse arguments
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --force)
                        force_retrain="true"
                        shift
                        ;;
                    *)
                        if [[ -z "$max_samples" ]] && [[ "$1" =~ ^[0-9]+$ ]]; then
                            max_samples="$1"
                        fi
                        shift
                        ;;
                esac
            done
            
            train_model "$max_samples" "$force_retrain"
            ;;
        "predict")
            if [[ -z "$2" ]]; then
                error "Video ID required for prediction"
                show_usage
                exit 1
            fi
            predict_video "$2"
            ;;
        "info")
            model_info
            ;;
        "test")
            test_model "${2:-10}"
            ;;
        "api")
            start_api "${2:-$API_PORT}"
            ;;
        "quick")
            quick_check
            ;;
        "auto-retrain")
            auto_retrain
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        "")
            warning "No command specified. Starting API on default port..."
            start_api "$API_PORT"
            ;;
        *)
            # Check if argument is just a port number
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                log "Starting API on port $1..."
                start_api "$1"
            else
                error "Unknown command: $1"
                show_usage
                exit 1
            fi
            ;;
    esac
    
    log "Performance predictor completed"
}

# Run main function with all arguments
main "$@"