#!/bin/bash

# TikTok Performance Predictor - Professional API Launcher
# Supports multiple deployment modes with automatic configuration discovery

set -e  # Exit on any error

# ====================================================================
# ENVIRONMENT DETECTION
# ====================================================================

# Detect if running in Docker container
is_docker() {
    [[ -f /.dockerenv ]] || [[ -n "${DOCKER_CONTAINER:-}" ]]
}

# Detect deployment environment
detect_environment() {
    if [[ -n "${DEPLOYMENT_ENV:-}" ]]; then
        echo "$DEPLOYMENT_ENV"
    elif is_docker; then
        echo "docker"
    elif [[ -n "${CI:-}" ]]; then
        echo "ci"
    elif [[ -f ".env.production" ]] && [[ "${USE_PRODUCTION:-}" == "true" ]]; then
        echo "production"
    elif [[ -f ".env.development" ]]; then
        echo "development"
    else
        echo "local"
    fi
}

# ====================================================================
# CONFIGURATION MANAGEMENT
# ====================================================================

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Deployment environment
ENVIRONMENT="$(detect_environment)"
ENV_FILE=""

# Load environment file if exists
load_env_file() {
    local env_file="$1"
    if [[ -f "$env_file" ]]; then
        echo "Loading configuration from: $env_file"
        set -a  # Export all variables
        source "$env_file"
        set +a
        return 0
    fi
    return 1
}

# Load environment-specific configuration
case "$ENVIRONMENT" in
    "production")
        ENV_FILE="$SCRIPT_DIR/.env.production"
        ;;
    "development")
        ENV_FILE="$SCRIPT_DIR/.env.development"
        ;;
    "docker")
        ENV_FILE="$SCRIPT_DIR/.env.docker"
        ;;
    *)
        ENV_FILE="$SCRIPT_DIR/.env"
        ;;
esac

# Try loading environment files in order of precedence
load_env_file "$ENV_FILE" || load_env_file "$SCRIPT_DIR/.env" || true

# ====================================================================
# PATH DISCOVERY
# ====================================================================

# Function to find data file
find_data_file() {
    local search_paths=(
        "${DATA_PATH:-}"                          # Environment variable
        "$PROJECT_ROOT/data/master2.json"         # Standard project structure
        "$PROJECT_ROOT/master2.json"              # Root level
        "./data/master2.json"                     # Relative to current dir
        "./master2.json"                          # Current directory
        "/app/data/master2.json"                  # Docker standard
        "/data/master2.json"                      # Docker volume mount
        "${DATA_VOLUME:-/mnt/data}/master2.json"  # Configurable volume
    )
    
    for path in "${search_paths[@]}"; do
        if [[ -n "$path" ]] && [[ -f "$path" ]]; then
            echo "$path"
            return 0
        fi
    done
    
    return 1
}

# Function to find model file
find_model_file() {
    local model_name="${MODEL_NAME:-snoo.pkl}"
    local search_paths=(
        "${MODEL_PATH:-}"                         # Environment variable
        "$PROJECT_ROOT/models/$model_name"        # Standard project structure
        "$PROJECT_ROOT/ml/models/$model_name"     # ML subdirectory
        "./models/$model_name"                    # Relative to current
        "/app/models/$model_name"                 # Docker standard
        "/models/$model_name"                     # Docker volume mount
        "${MODEL_VOLUME:-/mnt/models}/$model_name" # Configurable volume
    )
    
    for path in "${search_paths[@]}"; do
        if [[ -n "$path" ]] && [[ -f "$path" ]]; then
            echo "$path"
            return 0
        fi
    done
    
    # If model doesn't exist, return the preferred location for creation
    echo "${MODEL_PATH:-$PROJECT_ROOT/models/$model_name}"
    return 1
}

# ====================================================================
# CONFIGURATION DEFAULTS & OVERRIDES
# ====================================================================

# API Configuration
API_PORT="${API_PORT:-8080}"
API_HOST="${API_HOST:-0.0.0.0}"
API_WORKERS="${API_WORKERS:-4}"
API_TIMEOUT="${API_TIMEOUT:-300}"
API_MAX_REQUESTS="${API_MAX_REQUESTS:-1000}"

# Model Configuration
MODEL_NAME="${MODEL_NAME:-snoo.pkl}"
MODEL_VERSION="${MODEL_VERSION:-latest}"
MODEL_AUTO_RELOAD="${MODEL_AUTO_RELOAD:-false}"
MODEL_CACHE_SIZE="${MODEL_CACHE_SIZE:-100}"

# Logging Configuration
LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_FORMAT="${LOG_FORMAT:-json}"
LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/api.log}"
LOG_MAX_SIZE="${LOG_MAX_SIZE:-100M}"
LOG_BACKUP_COUNT="${LOG_BACKUP_COUNT:-5}"

# Health Check Configuration
HEALTH_CHECK_ENABLED="${HEALTH_CHECK_ENABLED:-true}"
HEALTH_CHECK_PATH="${HEALTH_CHECK_PATH:-/health}"
READINESS_CHECK_PATH="${READINESS_CHECK_PATH:-/ready}"
LIVENESS_CHECK_PATH="${LIVENESS_CHECK_PATH:-/alive}"

# Performance Configuration
CACHE_ENABLED="${CACHE_ENABLED:-true}"
CACHE_TTL="${CACHE_TTL:-3600}"
REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-30}"
MAX_CONTENT_LENGTH="${MAX_CONTENT_LENGTH:-16777216}"  # 16MB

# ====================================================================
# LOGGING FUNCTIONS
# ====================================================================

# Colors for output (disabled in production/CI)
if [[ "$ENVIRONMENT" == "production" ]] || [[ -n "${CI:-}" ]] || [[ "${NO_COLOR:-}" == "true" ]]; then
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    CYAN=""
    MAGENTA=""
    NC=""
else
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    MAGENTA='\033[0;35m'
    NC='\033[0m'
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Structured logging function
log_message() {
    local level="$1"
    local message="$2"
    local timestamp="$(date -u '+%Y-%m-%dT%H:%M:%S.%3NZ')"
    
    if [[ "$LOG_FORMAT" == "json" ]]; then
        echo "{\"timestamp\":\"$timestamp\",\"level\":\"$level\",\"message\":\"$message\",\"environment\":\"$ENVIRONMENT\"}" | tee -a "$LOG_FILE"
    else
        local color=""
        case "$level" in
            ERROR) color="$RED" ;;
            WARN) color="$YELLOW" ;;
            INFO) color="$BLUE" ;;
            DEBUG) color="$CYAN" ;;
            SUCCESS) color="$GREEN" ;;
        esac
        echo -e "${color}[$timestamp] [$level]${NC} $message" | tee -a "$LOG_FILE"
    fi
}

log() { log_message "INFO" "$1"; }
error() { log_message "ERROR" "$1"; }
warning() { log_message "WARN" "$1"; }
success() { log_message "SUCCESS" "$1"; }
debug() { [[ "$LOG_LEVEL" == "DEBUG" ]] && log_message "DEBUG" "$1"; }

# ====================================================================
# VALIDATION FUNCTIONS
# ====================================================================

# Comprehensive dependency check
check_dependencies() {
    log "Validating dependencies and configuration..."
    
    local errors=()
    local warnings=()
    
    # Check Python
    if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
        errors+=("Python not found. Please install Python 3.8+")
    else
        PYTHON_CMD="${PYTHON_CMD:-$(command -v python3 || command -v python)}"
        local python_version=$($PYTHON_CMD --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        log "Python version: $python_version"
    fi
    
    # Check required Python packages
    local required_packages=("sklearn" "xgboost" "nltk" "textstat" "flask" "gunicorn")
    for package in "${required_packages[@]}"; do
        if ! $PYTHON_CMD -c "import $package" 2>/dev/null; then
            warnings+=("Python package '$package' not found")
        fi
    done
    
    # Check data file
    DATA_FILE="$(find_data_file)"
    if [[ -z "$DATA_FILE" ]] || [[ ! -f "$DATA_FILE" ]]; then
        errors+=("Data file not found. Searched standard locations. Set DATA_PATH environment variable.")
    else
        success "Data file found: $DATA_FILE"
        
        # Validate JSON format
        if ! $PYTHON_CMD -c "import json; json.load(open('$DATA_FILE'))" 2>/dev/null; then
            errors+=("Data file is not valid JSON: $DATA_FILE")
        else
            local file_size=$(du -h "$DATA_FILE" 2>/dev/null | cut -f1)
            log "Data file size: $file_size"
        fi
    fi
    
    # Check model file
    MODEL_FILE="$(find_model_file)"
    if [[ -f "$MODEL_FILE" ]]; then
        success "Model file found: $MODEL_FILE"
        
        # Check model age
        local model_age=$(( $(date +%s) - $(stat -f %m "$MODEL_FILE" 2>/dev/null || stat -c %Y "$MODEL_FILE" 2>/dev/null || echo 0) ))
        local days_old=$(( model_age / 86400 ))
        if [[ $days_old -gt 7 ]]; then
            warnings+=("Model is $days_old days old. Consider retraining.")
        fi
    else
        warnings+=("Model file not found at: $MODEL_FILE. Will need to train before serving.")
    fi
    
    # Check API script
    if [[ ! -f "$SCRIPT_DIR/api.py" ]]; then
        errors+=("API script not found: $SCRIPT_DIR/api.py")
    fi
    
    # Check port availability
    if command -v lsof &> /dev/null; then
        if lsof -Pi :$API_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            warnings+=("Port $API_PORT is already in use")
        fi
    fi
    
    # Print validation results
    if [[ ${#warnings[@]} -gt 0 ]]; then
        warning "Validation warnings:"
        for warn in "${warnings[@]}"; do
            warning "  - $warn"
        done
    fi
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        error "Validation failed with errors:"
        for err in "${errors[@]}"; do
            error "  - $err"
        done
        return 1
    fi
    
    success "Validation completed successfully"
    return 0
}

# ====================================================================
# HEALTH CHECK FUNCTIONS
# ====================================================================

# Create health check endpoint
create_health_check() {
    cat > "$SCRIPT_DIR/health_check.py" << 'EOF'
import sys
import json
import os
from datetime import datetime

def check_health():
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "checks": {}
    }
    
    # Check model file
    model_path = os.environ.get("MODEL_FILE", "")
    if os.path.exists(model_path):
        health["checks"]["model"] = "ok"
    else:
        health["checks"]["model"] = "missing"
        health["status"] = "degraded"
    
    # Check data file
    data_path = os.environ.get("DATA_FILE", "")
    if os.path.exists(data_path):
        health["checks"]["data"] = "ok"
    else:
        health["checks"]["data"] = "missing"
        health["status"] = "unhealthy"
    
    return health

if __name__ == "__main__":
    result = check_health()
    print(json.dumps(result))
    sys.exit(0 if result["status"] == "healthy" else 1)
EOF
}

# Run health check
run_health_check() {
    if [[ "$HEALTH_CHECK_ENABLED" != "true" ]]; then
        return 0
    fi
    
    create_health_check
    
    export MODEL_FILE="$MODEL_FILE"
    export DATA_FILE="$DATA_FILE"
    export ENVIRONMENT="$ENVIRONMENT"
    
    local health_output=$($PYTHON_CMD "$SCRIPT_DIR/health_check.py" 2>&1)
    local health_status=$?
    
    if [[ $health_status -eq 0 ]]; then
        success "Health check passed: $health_output"
        return 0
    else
        error "Health check failed: $health_output"
        return 1
    fi
}

# ====================================================================
# MODEL MANAGEMENT
# ====================================================================

# Train model with enhanced configuration
train_model() {
    local max_samples="${1:-}"
    local force_retrain="${2:-false}"
    
    log "Training model with environment: $ENVIRONMENT"
    
    # Create model directory
    local model_dir="$(dirname "$MODEL_FILE")"
    mkdir -p "$model_dir"
    
    # Prepare training arguments
    local args=(
        "train"
        "--data" "$DATA_FILE"
        "--model" "$MODEL_FILE"
    )
    
    if [[ -n "$max_samples" ]]; then
        args+=(--max-samples "$max_samples")
    fi
    
    # Add environment-specific training parameters
    if [[ "$ENVIRONMENT" == "production" ]]; then
        args+=(--optimize --validate)
    fi
    
    cd "$SCRIPT_DIR"
    $PYTHON_CMD train_ml.py "${args[@]}" 2>&1 | tee -a "$LOG_FILE"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        success "Model training completed"
        
        # Tag model with version
        if [[ -n "$MODEL_VERSION" ]] && [[ "$MODEL_VERSION" != "latest" ]]; then
            local versioned_model="${MODEL_FILE%.pkl}_${MODEL_VERSION}.pkl"
            cp "$MODEL_FILE" "$versioned_model"
            log "Model versioned as: $versioned_model"
        fi
        
        return 0
    else
        error "Model training failed"
        return 1
    fi
}

# ====================================================================
# API SERVER MANAGEMENT
# ====================================================================

# Start API server with production-ready configuration
start_api() {
    log "Starting API server"
    log "Environment: $ENVIRONMENT"
    log "Configuration:"
    log "  - Host: $API_HOST:$API_PORT"
    log "  - Workers: $API_WORKERS"
    log "  - Data: $DATA_FILE"
    log "  - Model: $MODEL_FILE"
    log "  - Logs: $LOG_FILE"
    
    # Run validation
    if ! check_dependencies; then
        error "Dependency validation failed. Please fix errors before starting."
        exit 1
    fi
    
    # Run health check
    if ! run_health_check; then
        if [[ "$ENVIRONMENT" == "production" ]]; then
            error "Health check failed. Cannot start in production mode."
            exit 1
        else
            warning "Health check failed. Starting in degraded mode."
        fi
    fi
    
    # Check if API script exists
    if [[ ! -f "$SCRIPT_DIR/api.py" ]]; then
        error "API script not found: $SCRIPT_DIR/api.py"
        error "Please ensure api.py exists in the ml/ directory"
        exit 1
    fi
    
    # Export all configuration as environment variables
    export MODEL_FILE DATA_FILE ENVIRONMENT API_PORT API_HOST
    export LOG_LEVEL LOG_FORMAT CACHE_ENABLED CACHE_TTL
    export HEALTH_CHECK_PATH READINESS_CHECK_PATH LIVENESS_CHECK_PATH
    export MODEL_AUTO_RELOAD MODEL_CACHE_SIZE
    export REQUEST_TIMEOUT MAX_CONTENT_LENGTH
    
    cd "$SCRIPT_DIR"
    
    # Use appropriate server based on environment
    if [[ "$ENVIRONMENT" == "production" ]] || [[ "$ENVIRONMENT" == "docker" ]]; then
        # Production: Use Gunicorn with optimized settings
        log "Starting production server with Gunicorn..."
        
        if ! command -v gunicorn &> /dev/null; then
            error "Gunicorn not installed. Installing..."
            pip install gunicorn
        fi
        
        exec gunicorn \
            --bind "$API_HOST:$API_PORT" \
            --workers "$API_WORKERS" \
            --timeout "$API_TIMEOUT" \
            --max-requests "$API_MAX_REQUESTS" \
            --max-requests-jitter 50 \
            --access-logfile "$LOG_DIR/access.log" \
            --error-logfile "$LOG_DIR/error.log" \
            --log-level "$LOG_LEVEL" \
            --worker-class sync \
            --preload \
            api:app
    else
        # Development: Use Flask development server
        log "Starting development server..."
        log "API available at: http://localhost:$API_PORT"
        log "Health check: http://localhost:$API_PORT$HEALTH_CHECK_PATH"
        
        $PYTHON_CMD api.py \
            --host "$API_HOST" \
            --port "$API_PORT" \
            --debug 2>&1 | tee -a "$LOG_FILE"
    fi
}

# ====================================================================
# DOCKER SUPPORT
# ====================================================================

# Generate Docker environment file
generate_docker_env() {
    cat > "$SCRIPT_DIR/.env.docker" << EOF
# Docker Environment Configuration
# Auto-generated on $(date)

ENVIRONMENT=docker
API_PORT=8080
API_HOST=0.0.0.0
API_WORKERS=4

# Paths (Docker volumes)
DATA_PATH=/data/master2.json
MODEL_PATH=/models/snoo.pkl
LOG_DIR=/logs

# Performance
CACHE_ENABLED=true
MODEL_AUTO_RELOAD=false

# Health checks
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_PATH=/health
EOF
    success "Generated Docker environment file: $SCRIPT_DIR/.env.docker"
}

# ====================================================================
# CLI INTERFACE
# ====================================================================

# Show configuration
show_config() {
    echo "Current Configuration:"
    echo "====================="
    echo "Environment: $ENVIRONMENT"
    echo "Data File: ${DATA_FILE:-NOT FOUND}"
    echo "Model File: ${MODEL_FILE:-NOT SET}"
    echo "API Port: $API_PORT"
    echo "API Host: $API_HOST"
    echo "Workers: $API_WORKERS"
    echo "Log Level: $LOG_LEVEL"
    echo "Log Format: $LOG_FORMAT"
    echo "Cache: $CACHE_ENABLED (TTL: ${CACHE_TTL}s)"
    echo "Health Checks: $HEALTH_CHECK_ENABLED"
}

# Show usage
show_usage() {
    cat << EOF
TikTok Performance Predictor API

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    start, api          Start the API server (default)
    train              Train the model
    validate           Run validation checks
    health             Run health check
    config             Show current configuration
    init               Initialize environment files
    help               Show this help message

Options:
    --env=ENV          Set environment (local|development|production|docker)
    --port=PORT        Override API port
    --data=PATH        Override data file path
    --model=PATH       Override model file path
    --workers=N        Number of API workers
    --force            Force operation (e.g., retrain)

Environment Variables:
    DATA_PATH          Path to data file
    MODEL_PATH         Path to model file
    API_PORT           API server port (default: 8080)
    API_HOST           API server host (default: 0.0.0.0)
    ENVIRONMENT        Deployment environment
    LOG_LEVEL          Logging level (DEBUG|INFO|WARN|ERROR)

Examples:
    $0                                    # Start API with auto-discovery
    $0 --env=production --port=8000      # Production mode on port 8000
    $0 train --force                      # Force retrain model
    $0 validate                           # Check configuration
    DATA_PATH=/custom/data.json $0       # Use custom data path

Environment Files:
    .env               Default configuration
    .env.development   Development settings
    .env.production    Production settings
    .env.docker        Docker container settings

EOF
}

# ====================================================================
# MAIN EXECUTION
# ====================================================================

main() {
    # Parse command line arguments
    COMMAND=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env=*)
                ENVIRONMENT="${1#*=}"
                shift
                ;;
            --port=*)
                API_PORT="${1#*=}"
                shift
                ;;
            --data=*)
                DATA_PATH="${1#*=}"
                shift
                ;;
            --model=*)
                MODEL_PATH="${1#*=}"
                shift
                ;;
            --workers=*)
                API_WORKERS="${1#*=}"
                shift
                ;;
            --force)
                FORCE="true"
                shift
                ;;
            --help|-h|help)
                show_usage
                exit 0
                ;;
            *)
                if [[ -z "$COMMAND" ]]; then
                    COMMAND="$1"
                fi
                shift
                ;;
        esac
    done
    
    # Set default command
    COMMAND="${COMMAND:-start}"
    
    # Execute command
    case "$COMMAND" in
        start|api)
            start_api
            ;;
        train)
            DATA_FILE="$(find_data_file)" || { error "Data file not found"; exit 1; }
            MODEL_FILE="$(find_model_file)"
            train_model "" "${FORCE:-false}"
            ;;
        validate)
            check_dependencies
            ;;
        health)
            DATA_FILE="$(find_data_file)" || true
            MODEL_FILE="$(find_model_file)" || true
            run_health_check
            ;;
        config)
            DATA_FILE="$(find_data_file)" || true
            MODEL_FILE="$(find_model_file)" || true
            show_config
            ;;
        init)
            generate_docker_env
            # Create other environment files if needed
            ;;
        *)
            error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"