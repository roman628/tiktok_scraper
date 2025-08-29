#!/bin/bash

# TikTok Scraper Intelligent Setup Script
# Zero-argument setup with automatic environment detection and configuration
# Usage: ./setup.sh [--migrate]

set -e

# Script version
SETUP_VERSION="2.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Setup state file to track progress
SETUP_STATE_FILE=".setup_state"
SETUP_LOG="setup_$(date +%Y%m%d_%H%M%S).log"

# Platform detection
OS="unknown"
ARCH="unknown"
PACKAGE_MANAGER="unknown"
PYTHON_CMD="python3"
PIP_CMD="pip3"
VENV_DIR="venv"

# Database defaults
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="tiktok_scraper"
DB_USER="$(whoami)"
DB_PASSWORD=""

# Progress tracking
TOTAL_STEPS=10
CURRENT_STEP=0

# ================== Helper Functions ==================

print_msg() {
    local color=$1
    shift
    echo -e "${color}$@${NC}" | tee -a "$SETUP_LOG"
}

print_header() {
    echo | tee -a "$SETUP_LOG"
    print_msg $BOLD "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_msg $CYAN "  $1"
    print_msg $BOLD "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo | tee -a "$SETUP_LOG"
}

print_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    local percentage=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    local filled=$((CURRENT_STEP * 50 / TOTAL_STEPS))
    local empty=$((50 - filled))
    
    printf "\r${CYAN}[${GREEN}"
    printf '█%.0s' $(seq 1 $filled)
    printf "${CYAN}"
    printf '░%.0s' $(seq 1 $empty)
    printf "] ${percentage}%% - $1${NC}\n"
}

save_state() {
    local phase=$1
    local status=$2
    echo "$phase=$status" >> "$SETUP_STATE_FILE"
}

check_state() {
    local phase=$1
    if [ -f "$SETUP_STATE_FILE" ]; then
        grep -q "^$phase=completed$" "$SETUP_STATE_FILE" 2>/dev/null
        return $?
    fi
    return 1
}

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

detect_gpu() {
    local gpu_type="none"
    
    # Check for NVIDIA GPU (CUDA)
    if check_command nvidia-smi; then
        if nvidia-smi &>/dev/null; then
            gpu_type="cuda"
            print_msg $GREEN "  ✓ NVIDIA GPU detected (CUDA support available)"
        fi
    fi
    
    # Check for Apple Silicon (MPS)
    if [ "$OS" = "darwin" ]; then
        if sysctl -n machdep.cpu.brand_string 2>/dev/null | grep -q "Apple"; then
            gpu_type="mps"
            print_msg $GREEN "  ✓ Apple Silicon detected (MPS support available)"
        fi
    fi
    
    if [ "$gpu_type" = "none" ]; then
        print_msg $YELLOW "  ⚠ No GPU detected, will use CPU for Whisper transcription"
    fi
    
    echo "$gpu_type"
}

# ================== Phase 1: Environment Detection ==================

detect_environment() {
    print_header "Phase 1: Environment Detection"
    
    if check_state "environment"; then
        print_msg $GREEN "✓ Environment already detected (cached)"
        print_progress "Environment detected"
        return 0
    fi
    
    # Detect OS
    case "$(uname -s)" in
        Linux*)
            OS="linux"
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                if [[ "$ID" == "ubuntu" ]] || [[ "$ID_LIKE" == *"debian"* ]]; then
                    PACKAGE_MANAGER="apt"
                elif [[ "$ID" == "fedora" ]] || [[ "$ID" == "rhel" ]] || [[ "$ID" == "centos" ]]; then
                    PACKAGE_MANAGER="yum"
                elif [[ "$ID" == "arch" ]] || [[ "$ID_LIKE" == *"arch"* ]]; then
                    PACKAGE_MANAGER="pacman"
                fi
            fi
            ;;
        Darwin*)
            OS="darwin"
            PACKAGE_MANAGER="brew"
            ;;
        MINGW*|CYGWIN*|MSYS*)
            OS="windows"
            print_msg $YELLOW "  ⚠ Windows detected - please use WSL2 for best compatibility"
            ;;
        *)
            print_msg $RED "  ✗ Unsupported OS: $(uname -s)"
            exit 1
            ;;
    esac
    
    # Detect architecture
    ARCH="$(uname -m)"
    
    print_msg $GREEN "  ✓ Operating System: $OS ($ARCH)"
    print_msg $GREEN "  ✓ Package Manager: $PACKAGE_MANAGER"
    
    # Check for sudo/admin access
    if [ "$OS" != "darwin" ]; then
        if ! sudo -n true 2>/dev/null; then
            print_msg $YELLOW "  ⚠ This script may need sudo access for system packages"
            print_msg $YELLOW "    You may be prompted for your password"
        fi
    fi
    
    # Detect Python
    if check_command python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_msg $GREEN "  ✓ Python $PYTHON_VERSION detected"
        else
            print_msg $RED "  ✗ Python 3.8+ required (found $PYTHON_VERSION)"
            exit 1
        fi
    else
        print_msg $RED "  ✗ Python 3 not found"
        exit 1
    fi
    
    # Detect GPU capabilities
    GPU_TYPE=$(detect_gpu)
    
    save_state "environment" "completed"
    print_progress "Environment detected"
}

# ================== Phase 2: System Dependencies ==================

install_system_deps() {
    print_header "Phase 2: System Dependencies"
    
    if check_state "system_deps"; then
        print_msg $GREEN "✓ System dependencies already installed (cached)"
        print_progress "System dependencies ready"
        return 0
    fi
    
    local deps_needed=false
    
    # Check ffmpeg
    if ! check_command ffmpeg; then
        print_msg $YELLOW "  ⚠ ffmpeg not found - required for video processing"
        deps_needed=true
    else
        print_msg $GREEN "  ✓ ffmpeg installed"
    fi
    
    # Check PostgreSQL
    if ! check_command psql; then
        print_msg $YELLOW "  ⚠ PostgreSQL not found - required for database"
        deps_needed=true
    else
        PSQL_VERSION=$(psql --version | grep -oE '[0-9]+\.[0-9]+')
        print_msg $GREEN "  ✓ PostgreSQL $PSQL_VERSION installed"
    fi
    
    # Check git
    if ! check_command git; then
        print_msg $YELLOW "  ⚠ git not found"
        deps_needed=true
    else
        print_msg $GREEN "  ✓ git installed"
    fi
    
    # Install missing dependencies
    if [ "$deps_needed" = true ]; then
        print_msg $CYAN "\nInstalling missing system dependencies..."
        
        case "$PACKAGE_MANAGER" in
            brew)
                # macOS
                if ! check_command brew; then
                    print_msg $YELLOW "Installing Homebrew..."
                    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                fi
                
                print_msg $YELLOW "Installing packages via Homebrew..."
                brew install ffmpeg postgresql@15 git || true
                brew services start postgresql@15 || true
                ;;
                
            apt)
                # Ubuntu/Debian
                print_msg $YELLOW "Updating package lists..."
                sudo apt update
                
                print_msg $YELLOW "Installing packages via apt..."
                sudo apt install -y ffmpeg postgresql postgresql-contrib git python3-venv || true
                sudo systemctl start postgresql || true
                sudo systemctl enable postgresql || true
                ;;
                
            yum)
                # RHEL/CentOS/Fedora
                print_msg $YELLOW "Installing packages via yum..."
                sudo yum install -y ffmpeg postgresql-server postgresql-contrib git python3-venv || true
                sudo postgresql-setup initdb || true
                sudo systemctl start postgresql || true
                sudo systemctl enable postgresql || true
                ;;
                
            pacman)
                # Arch Linux
                print_msg $YELLOW "Installing packages via pacman..."
                sudo pacman -S --noconfirm ffmpeg postgresql git python-virtualenv || true
                sudo systemctl start postgresql || true
                sudo systemctl enable postgresql || true
                ;;
                
            *)
                print_msg $YELLOW "Please install the following manually:"
                print_msg $YELLOW "  - ffmpeg"
                print_msg $YELLOW "  - postgresql"
                print_msg $YELLOW "  - git"
                print_msg $YELLOW "Then run this script again."
                exit 1
                ;;
        esac
    fi
    
    save_state "system_deps" "completed"
    print_progress "System dependencies installed"
}

# ================== Phase 3: Python Environment ==================

setup_python_env() {
    print_header "Phase 3: Python Environment"
    
    if check_state "python_env"; then
        print_msg $GREEN "✓ Python environment already configured (cached)"
        print_progress "Python environment ready"
        # Still need to activate it for the rest of the script
        if [ -f "$VENV_DIR/bin/activate" ]; then
            source "$VENV_DIR/bin/activate"
        fi
        return 0
    fi
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        print_msg $YELLOW "Creating virtual environment..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        print_msg $GREEN "  ✓ Virtual environment created"
    else
        print_msg $GREEN "  ✓ Virtual environment exists"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    print_msg $GREEN "  ✓ Virtual environment activated"
    
    # Upgrade pip
    print_msg $YELLOW "Upgrading pip..."
    pip install --upgrade pip --quiet
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        print_msg $YELLOW "Installing Python dependencies from requirements.txt..."
        print_msg $CYAN "  This may take a few minutes..."
        
        # Upgrade pip and essential build tools first
        pip install --upgrade pip wheel setuptools --quiet
        
        # Install all dependencies from requirements.txt
        # Handle PyTorch separately based on GPU type
        if [ "$GPU_TYPE" = "cuda" ]; then
            print_msg $CYAN "  Installing with CUDA support for PyTorch..."
            # Install PyTorch with CUDA before other requirements
            pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 --quiet
            # Install everything else from requirements.txt (excluding torch lines)
            grep -v "^torch" requirements.txt | pip install -r /dev/stdin --quiet
        elif [ "$GPU_TYPE" = "mps" ]; then
            print_msg $CYAN "  Installing with MPS support for PyTorch..."
            # Install PyTorch with MPS support
            pip install torch torchvision torchaudio --quiet
            # Install everything else from requirements.txt (excluding torch lines)
            grep -v "^torch" requirements.txt | pip install -r /dev/stdin --quiet
        else
            print_msg $CYAN "  Installing with CPU-only PyTorch..."
            # Install PyTorch CPU-only version
            pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
            # Install everything else from requirements.txt (excluding torch lines)
            grep -v "^torch" requirements.txt | pip install -r /dev/stdin --quiet
        fi
        
        # Now install the full requirements.txt to catch any missing dependencies
        # This will skip already installed packages
        print_msg $CYAN "  Verifying all dependencies..."
        pip install -r requirements.txt --quiet 2>/dev/null || true
        
        print_msg $GREEN "  ✓ All Python dependencies installed from requirements.txt"
    else
        print_msg $YELLOW "  ⚠ requirements.txt not found, skipping Python packages"
    fi
    
    save_state "python_env" "completed"
    print_progress "Python environment configured"
}

# ================== Phase 4: Database Setup ==================

setup_database() {
    print_header "Phase 4: Database Setup"
    
    # Check for --migrate flag
    if [ "$1" = "--migrate" ]; then
        migrate_database
        return 0
    fi
    
    if check_state "database"; then
        print_msg $GREEN "✓ Database already configured (cached)"
        print_progress "Database ready"
        return 0
    fi
    
    # Ensure PostgreSQL is running
    if ! pg_isready &>/dev/null; then
        print_msg $YELLOW "Starting PostgreSQL..."
        if [ "$OS" = "darwin" ]; then
            brew services start postgresql@15 2>/dev/null || brew services start postgresql 2>/dev/null || true
        else
            sudo systemctl start postgresql 2>/dev/null || sudo service postgresql start 2>/dev/null || true
        fi
        sleep 2
    fi
    
    if pg_isready &>/dev/null; then
        print_msg $GREEN "  ✓ PostgreSQL is running"
    else
        print_msg $RED "  ✗ Failed to start PostgreSQL"
        print_msg $YELLOW "    Please start it manually and run setup again"
        exit 1
    fi
    
    # Create database and user
    print_msg $YELLOW "Setting up database..."
    
    # Try to create user and database
    if [ "$OS" = "linux" ]; then
        # On Linux, use sudo -u postgres
        sudo -u postgres psql <<EOF 2>/dev/null || true
CREATE USER $DB_USER;
ALTER USER $DB_USER CREATEDB;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF
    else
        # On macOS, use current user
        psql postgres <<EOF 2>/dev/null || true
CREATE USER $DB_USER;
ALTER USER $DB_USER CREATEDB;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF
    fi
    
    # Test connection
    if PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -c "SELECT 1;" &>/dev/null; then
        print_msg $GREEN "  ✓ Database '$DB_NAME' created and accessible"
    else
        print_msg $YELLOW "  ⚠ Database may already exist or have different credentials"
    fi
    
    # Apply schema
    if [ -f "database/schema.sql" ]; then
        print_msg $YELLOW "Applying database schema..."
        PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -f database/schema.sql 2>&1 | \
            grep -v "already exists" | grep -v "NOTICE:" || true
        print_msg $GREEN "  ✓ Database schema applied"
        
        # Check for medallion architecture
        print_msg $YELLOW "Setting up medallion architecture..."
        PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME <<EOF 2>/dev/null || true
-- Ensure schemas exist
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Run migration if needed
SELECT migrate_to_medallion();

-- Compute ML features
SELECT etl_silver_to_gold();
EOF
        print_msg $GREEN "  ✓ Medallion architecture configured"
    fi
    
    # Import from master2.json if exists and database is empty
    if [ -f "data/master2.json" ]; then
        VIDEO_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
            "SELECT COUNT(*) FROM videos;" 2>/dev/null || echo "0")
        
        if [ "$VIDEO_COUNT" = "0" ]; then
            print_msg $YELLOW "Found master2.json with existing data..."
            print_msg $CYAN "  Importing data to PostgreSQL..."
            python database/migrate_json_to_postgres.py data/master2.json 2>/dev/null || \
                print_msg $YELLOW "  ⚠ Import may need manual attention"
        fi
    fi
    
    save_state "database" "completed"
    print_progress "Database configured"
}

migrate_database() {
    print_msg $CYAN "\n=== Database Migration Mode ==="
    
    if [ ! -f "database/schema.sql" ]; then
        print_msg $RED "  ✗ database/schema.sql not found"
        exit 1
    fi
    
    # Create backup
    BACKUP_FILE="database/backup_$(date +%Y%m%d_%H%M%S).sql"
    print_msg $YELLOW "Creating database backup..."
    PGPASSWORD=$DB_PASSWORD pg_dump -U $DB_USER -d $DB_NAME > "$BACKUP_FILE" 2>/dev/null
    
    if [ -s "$BACKUP_FILE" ]; then
        print_msg $GREEN "  ✓ Backup saved to $BACKUP_FILE"
    else
        print_msg $YELLOW "  ⚠ Backup may be empty (new database?)"
    fi
    
    # Apply schema changes
    print_msg $YELLOW "Applying schema updates..."
    PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -f database/schema.sql 2>&1 | \
        grep -v "already exists" | grep -v "NOTICE:" || true
    
    # Run migration functions
    print_msg $YELLOW "Running data migrations..."
    PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME <<EOF 2>/dev/null || true
-- Migrate to medallion architecture
SELECT migrate_to_medallion();

-- Update ML features
SELECT etl_silver_to_gold();

-- Analyze tables for optimization
ANALYZE;
EOF
    
    # Show statistics
    print_msg $CYAN "\nDatabase Statistics:"
    PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME <<EOF 2>/dev/null || true
SELECT 
    'Videos (Public)' as table_name, COUNT(*) as count FROM public.videos
UNION ALL
SELECT 'Videos (Silver)', COUNT(*) FROM silver.videos
UNION ALL
SELECT 'ML Features (Gold)', COUNT(*) FROM gold.ml_features
UNION ALL
SELECT 'Transcriptions', COUNT(*) FROM public.transcriptions
UNION ALL
SELECT 'Comments', COUNT(*) FROM public.comments;
EOF
    
    print_msg $GREEN "\n✓ Migration completed successfully"
}

# ================== Phase 5: Configuration ==================

setup_configuration() {
    print_header "Phase 5: Project Configuration"
    
    if check_state "configuration"; then
        print_msg $GREEN "✓ Configuration already set up (cached)"
        print_progress "Configuration ready"
        return 0
    fi
    
    # Create directories
    print_msg $YELLOW "Creating project directories..."
    mkdir -p data downloads src utils database ml extension server tests logs
    mkdir -p downloads/audio downloads/video
    print_msg $GREEN "  ✓ Directories created"
    
    # Create config.toml if it doesn't exist
    if [ ! -f "config.toml" ]; then
        if [ -f "assets/config.template.toml" ]; then
            print_msg $YELLOW "Creating config.toml..."
            cp assets/config.template.toml config.toml
            
            # Update database settings
            sed -i.bak -e "/\[database\]/,/\[.*\]/{
                s/enabled = .*/enabled = true/
                s/host = .*/host = \"$DB_HOST\"/
                s/port = .*/port = $DB_PORT/
                s/database = .*/database = \"$DB_NAME\"/
                s/user = .*/user = \"$DB_USER\"/
                s/password = .*/password = \"$DB_PASSWORD\"/
            }" config.toml
            
            # Update GPU settings based on detection
            if [ "$GPU_TYPE" = "cuda" ] || [ "$GPU_TYPE" = "mps" ]; then
                sed -i.bak "s/force_cpu = .*/force_cpu = false/" config.toml
            else
                sed -i.bak "s/force_cpu = .*/force_cpu = true/" config.toml
            fi
            
            rm -f config.toml.bak
            print_msg $GREEN "  ✓ config.toml created with sensible defaults"
        else
            print_msg $YELLOW "  ⚠ config.template.toml not found, skipping config creation"
        fi
    else
        print_msg $GREEN "  ✓ config.toml already exists"
    fi
    
    # Create test config if needed
    if [ ! -f "tests/test_config.toml" ] && [ -f "assets/test_config.template.toml" ]; then
        print_msg $YELLOW "Creating test configuration..."
        cp assets/test_config.template.toml tests/test_config.toml
        print_msg $GREEN "  ✓ tests/test_config.toml created"
    fi
    
    # Download Whisper model if needed
    if [ "$GPU_TYPE" != "none" ] || [ ! -f "$HOME/.cache/whisper/large-v3.pt" ]; then
        print_msg $YELLOW "Downloading Whisper model (this may take a while)..."
        python -c "from faster_whisper import WhisperModel; WhisperModel('base')" 2>/dev/null || true
        print_msg $GREEN "  ✓ Whisper model ready"
    fi
    
    save_state "configuration" "completed"
    print_progress "Configuration complete"
}

# ================== Phase 6: Extension Setup ==================

setup_extension() {
    print_header "Phase 6: Firefox Extension"
    
    if check_state "extension"; then
        print_msg $GREEN "✓ Extension setup already shown (cached)"
        print_progress "Extension configured"
        return 0
    fi
    
    if [ -d "extension" ]; then
        print_msg $CYAN "Firefox Extension Setup Instructions:"
        print_msg $YELLOW "  1. Open Firefox and navigate to: about:debugging"
        print_msg $YELLOW "  2. Click 'This Firefox' in the left sidebar"
        print_msg $YELLOW "  3. Click 'Load Temporary Add-on'"
        print_msg $YELLOW "  4. Navigate to: $(pwd)/extension"
        print_msg $YELLOW "  5. Select manifest.json"
        print_msg $YELLOW "  6. The extension icon will appear in your toolbar"
        print_msg $YELLOW "  7. Click the extension icon to configure settings"
        
        # Create start script for extension server
        if [ ! -f "start_extension_server.sh" ]; then
            cat > start_extension_server.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python extension/url_server.py
EOF
            chmod +x start_extension_server.sh
            print_msg $GREEN "  ✓ Created start_extension_server.sh"
        fi
        
        print_msg $CYAN "\nTo start the URL collection server:"
        print_msg $BLUE "  ./start_extension_server.sh"
    else
        print_msg $YELLOW "  ⚠ Extension directory not found"
    fi
    
    save_state "extension" "completed"
    print_progress "Extension setup complete"
}

# ================== Phase 7: ML Model Setup ==================

setup_ml_model() {
    print_header "Phase 7: Machine Learning Model"
    
    if check_state "ml_model"; then
        print_msg $GREEN "✓ ML model already configured (cached)"
        print_progress "ML model ready"
        return 0
    fi
    
    # Create ML directories
    mkdir -p ml/models ml/data
    
    # Check if we have enough data to train
    if [ -f "database/schema.sql" ]; then
        VIDEO_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
            "SELECT COUNT(*) FROM gold.ml_features;" 2>/dev/null || echo "0")
        
        if [ "$VIDEO_COUNT" -gt 100 ]; then
            print_msg $YELLOW "Found $VIDEO_COUNT videos with features"
            print_msg $CYAN "  You can train the ML model with:"
            print_msg $BLUE "  python ml/train_ml.py"
        else
            print_msg $YELLOW "  ⚠ Need more data for ML training (have $VIDEO_COUNT, need 100+)"
        fi
    fi
    
    # Download NLTK data
    print_msg $YELLOW "Downloading NLTK data..."
    python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('vader_lexicon', quiet=True)" 2>/dev/null || true
    print_msg $GREEN "  ✓ NLTK data downloaded"
    
    # Check for categories and run categorize_videos if needed
    CATEGORY_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
        "SELECT COUNT(*) FROM categories;" 2>/dev/null || echo "0")
    
    if [ "$CATEGORY_COUNT" -eq 0 ]; then
        print_msg $YELLOW "\nNo categories found in database. Category discovery is needed for content identification."
        
        # Check if we have videos with transcripts to categorize
        TRANSCRIPT_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
            "SELECT COUNT(*) FROM transcriptions WHERE whisper_transcription IS NOT NULL;" 2>/dev/null || echo "0")
        
        if [ "$TRANSCRIPT_COUNT" -gt 0 ]; then
            print_msg $CYAN "Found $TRANSCRIPT_COUNT videos with transcripts to analyze."
            
            # First check if API key is in config
            if [ -f config.toml ]; then
                GEMINI_API_KEY=$(python -c "
import tomllib
with open('config.toml', 'rb') as f:
    config = tomllib.load(f)
    print(config.get('setup', {}).get('gemini_api_key', ''))
" 2>/dev/null || echo "")
            fi
            
            # If API key exists in config, run automatically
            if [ ! -z "$GEMINI_API_KEY" ]; then
                print_msg $GREEN "  ✓ Found Gemini API key in config.toml"
                print_msg $YELLOW "\nRunning category discovery automatically..."
                RUN_DISCOVERY="y"
            else
                # Otherwise ask
                print_msg $YELLOW "\nWould you like to run category discovery using Google Gemini API?"
                print_msg $CYAN "This will analyze your videos and create content categories."
                read -p "Run category discovery? (y/n): " -n 1 -r
                echo
                RUN_DISCOVERY=$REPLY
            fi
            
            if [[ $RUN_DISCOVERY =~ ^[Yy]$ ]]; then
                # If not in config, ask for it
                if [ -z "$GEMINI_API_KEY" ]; then
                    print_msg $YELLOW "\nPlease enter your Google Gemini API key:"
                    print_msg $CYAN "Get one free at: https://makersuite.google.com/app/apikey"
                    read -s -p "API Key: " GEMINI_API_KEY
                fi
                echo
                
                if [ ! -z "$GEMINI_API_KEY" ]; then
                    print_msg $YELLOW "\nRunning category discovery..."
                    python utility/categorize_videos.py --api-key "$GEMINI_API_KEY" 2>&1 | \
                        while IFS= read -r line; do
                            print_msg $CYAN "  $line"
                        done
                    
                    # Check if categories were created
                    NEW_CATEGORY_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
                        "SELECT COUNT(*) FROM categories;" 2>/dev/null || echo "0")
                    
                    if [ "$NEW_CATEGORY_COUNT" -gt 0 ]; then
                        print_msg $GREEN "  ✓ Created $NEW_CATEGORY_COUNT content categories"
                        
                        # Now run context identification
                        print_msg $YELLOW "\nRunning context identification on all videos..."
                        python src/identify_context.py 2>&1 | \
                            while IFS= read -r line; do
                                print_msg $CYAN "  $line"
                            done
                        
                        CATEGORIZED_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
                            "SELECT COUNT(DISTINCT video_id) FROM video_categories;" 2>/dev/null || echo "0")
                        print_msg $GREEN "  ✓ Categorized $CATEGORIZED_COUNT videos"
                    else
                        print_msg $YELLOW "  ⚠ Category discovery did not create categories"
                    fi
                else
                    print_msg $YELLOW "  ⚠ Skipping category discovery (no API key provided)"
                fi
            else
                print_msg $YELLOW "  ⚠ Skipping category discovery"
                print_msg $CYAN "  You can run it later with: python utility/categorize_videos.py --api-key YOUR_KEY"
            fi
        else
            print_msg $YELLOW "  ⚠ No videos with transcripts found for category discovery"
            print_msg $CYAN "  Run the collector with --whisper flag first to generate transcripts"
        fi
    else
        print_msg $GREEN "  ✓ Found $CATEGORY_COUNT existing categories"
        
        # Check if videos need categorization
        UNCATEGORIZED_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -tAc \
            "SELECT COUNT(*) FROM videos v 
             WHERE EXISTS (SELECT 1 FROM transcriptions t WHERE t.video_id = v.id)
             AND NOT EXISTS (SELECT 1 FROM video_categories vc WHERE vc.video_id = v.id);" 2>/dev/null || echo "0")
        
        if [ "$UNCATEGORIZED_COUNT" -gt 0 ]; then
            print_msg $YELLOW "  Found $UNCATEGORIZED_COUNT uncategorized videos with transcripts"
            print_msg $CYAN "  You can categorize them with: python src/identify_context.py"
        fi
    fi
    
    save_state "ml_model" "completed"
    print_progress "ML model configured"
}

# ================== Phase 8: Django Setup ==================

setup_django() {
    print_header "Phase 8: Django Web Interface"
    
    if check_state "django"; then
        print_msg $GREEN "✓ Django already configured (cached)"
        print_progress "Django ready"
        return 0
    fi
    
    if [ -f "manage.py" ]; then
        print_msg $YELLOW "Configuring Django..."
        
        # Update Django settings with database config
        if [ -f "tiktok_scraper/settings.py" ]; then
            python -c "
import re
with open('tiktok_scraper/settings.py', 'r') as f:
    content = f.read()
content = re.sub(r'\"NAME\": \".*?\"', f'\"NAME\": \"$DB_NAME\"', content)
content = re.sub(r'\"USER\": \".*?\"', f'\"USER\": \"$DB_USER\"', content)
content = re.sub(r'\"PASSWORD\": \".*?\"', f'\"PASSWORD\": \"$DB_PASSWORD\"', content)
content = re.sub(r'\"HOST\": \".*?\"', f'\"HOST\": \"$DB_HOST\"', content)
content = re.sub(r'\"PORT\": \".*?\"', f'\"PORT\": \"$DB_PORT\"', content)
with open('tiktok_scraper/settings.py', 'w') as f:
    f.write(content)
" 2>/dev/null || print_msg $YELLOW "  ⚠ Manual Django config may be needed"
        fi
        
        # Run migrations
        print_msg $YELLOW "Running Django migrations..."
        python manage.py migrate --run-syncdb 2>/dev/null || true
        print_msg $GREEN "  ✓ Django configured"
        
        print_msg $CYAN "\nTo start Django server:"
        print_msg $BLUE "  python manage.py runserver"
    else
        print_msg $YELLOW "  ⚠ Django project not found"
    fi
    
    save_state "django" "completed"
    print_progress "Django configured"
}

# ================== Phase 9: Health Checks ==================

run_health_checks() {
    print_header "Phase 9: System Health Checks"
    
    local all_good=true
    
    # Check Python environment
    if [ -f "$VENV_DIR/bin/activate" ]; then
        print_msg $GREEN "  ✓ Python virtual environment"
    else
        print_msg $RED "  ✗ Python virtual environment missing"
        all_good=false
    fi
    
    # Check database connection
    if PGPASSWORD=$DB_PASSWORD psql -U $DB_USER -d $DB_NAME -c "SELECT 1;" &>/dev/null; then
        print_msg $GREEN "  ✓ Database connection"
    else
        print_msg $RED "  ✗ Database connection failed"
        all_good=false
    fi
    
    # Check ffmpeg
    if check_command ffmpeg; then
        print_msg $GREEN "  ✓ ffmpeg available"
    else
        print_msg $RED "  ✗ ffmpeg not found"
        all_good=false
    fi
    
    # Check main script
    if [ -f "collector.py" ]; then
        print_msg $GREEN "  ✓ collector.py found"
    else
        print_msg $RED "  ✗ collector.py not found"
        all_good=false
    fi
    
    # Check config
    if [ -f "config.toml" ]; then
        print_msg $GREEN "  ✓ config.toml exists"
    else
        print_msg $RED "  ✗ config.toml missing"
        all_good=false
    fi
    
    # Check critical Python imports
    python -c "import yt_dlp, psycopg2, rich, faster_whisper" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_msg $GREEN "  ✓ Core Python packages"
    else
        print_msg $RED "  ✗ Some Python packages missing"
        all_good=false
    fi
    
    if [ "$all_good" = true ]; then
        print_msg $GREEN "\n✅ All health checks passed!"
    else
        print_msg $YELLOW "\n⚠ Some health checks failed - review above"
    fi
    
    print_progress "Health checks complete"
}

# ================== Phase 10: Summary ==================

show_summary() {
    print_header "Setup Complete! 🎉"
    
    print_msg $GREEN "Your TikTok Scraper is ready to use!"
    
    print_msg $CYAN "\n📋 Quick Start Commands:"
    print_msg $YELLOW "  Activate environment:  ${BLUE}source venv/bin/activate"
    print_msg $YELLOW "  Process URLs:          ${BLUE}python collector.py --from-file data/urls.txt"
    print_msg $YELLOW "  Start Django:          ${BLUE}python manage.py runserver"
    print_msg $YELLOW "  Start Extension Server:${BLUE}./start_extension_server.sh"
    print_msg $YELLOW "  Train ML Model:        ${BLUE}python ml/train_ml.py"
    
    print_msg $CYAN "\n🔧 Configuration:"
    print_msg $YELLOW "  Main config:    ${BLUE}config.toml"
    print_msg $YELLOW "  Test config:    ${BLUE}tests/test_config.toml"
    print_msg $YELLOW "  Database:       ${BLUE}$DB_NAME @ $DB_HOST:$DB_PORT"
    
    if [ "$GPU_TYPE" != "none" ]; then
        print_msg $CYAN "\n🚀 GPU Acceleration:"
        if [ "$GPU_TYPE" = "cuda" ]; then
            print_msg $GREEN "  NVIDIA CUDA enabled for Whisper transcription"
        elif [ "$GPU_TYPE" = "mps" ]; then
            print_msg $GREEN "  Apple MPS enabled for Whisper transcription"
        fi
    fi
    
    print_msg $CYAN "\n📚 Documentation:"
    print_msg $YELLOW "  README:         ${BLUE}README.md"
    print_msg $YELLOW "  Claude Guide:   ${BLUE}CLAUDE.md"
    print_msg $YELLOW "  Database Docs:  ${BLUE}database/README.md"
    
    print_msg $CYAN "\n💡 Next Steps:"
    print_msg $YELLOW "  1. Add TikTok URLs to ${BLUE}data/urls.txt"
    print_msg $YELLOW "  2. (Optional) Get MS_TOKEN for comments and add to config.toml"
    print_msg $YELLOW "  3. Run ${BLUE}python collector.py${YELLOW} to start scraping"
    print_msg $YELLOW "  4. View data in Django admin at ${BLUE}http://localhost:8000/admin"
    
    print_msg $GREEN "\n✨ Setup completed in $(date -u -d @$SECONDS '+%M minutes %S seconds')"
    print_msg $CYAN "Log saved to: ${BLUE}$SETUP_LOG"
    
    print_progress "Setup complete!"
}

# ================== Main Execution ==================

main() {
    # Banner
    clear
    echo
    print_msg $BOLD "╔══════════════════════════════════════════════════════════╗"
    print_msg $BOLD "║                                                          ║"
    print_msg $BOLD "║        ${CYAN}TikTok Scraper Intelligent Setup v$SETUP_VERSION${NC}${BOLD}        ║"
    print_msg $BOLD "║                                                          ║"
    print_msg $BOLD "╚══════════════════════════════════════════════════════════╝"
    echo
    
    # Check for migration flag
    if [ "$1" = "--migrate" ]; then
        print_msg $CYAN "Starting database migration..."
        setup_database --migrate
        exit 0
    fi
    
    # Check if this is a fresh setup or resume
    if [ -f "$SETUP_STATE_FILE" ]; then
        print_msg $YELLOW "Found previous setup state, resuming..."
        echo
    else
        print_msg $CYAN "Starting fresh setup..."
        echo > "$SETUP_STATE_FILE"
    fi
    
    # Record start time
    SECONDS=0
    
    # Run all phases
    detect_environment
    install_system_deps
    setup_python_env
    setup_database
    setup_configuration
    setup_extension
    setup_ml_model
    setup_django
    run_health_checks
    show_summary
    
    # Mark setup as complete
    save_state "setup_complete" "completed"
}

# ================== Script Entry Point ==================

# Trap errors
trap 'print_msg $RED "\n❌ Setup failed! Check $SETUP_LOG for details"; exit 1' ERR

# Run main function with all arguments
main "$@"