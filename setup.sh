#!/bin/bash

# TikTok Scraper Configuration Setup Script
# This script creates config.toml files from templates with user input

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_msg() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Function to read user input with optional default
read_input() {
    local prompt=$1
    local default=$2
    local optional=$3
    local result=""
    
    if [ "$optional" = "true" ]; then
        if [ -n "$default" ]; then
            printf "%s [${YELLOW}%s${NC}] (optional, press Enter to skip): " "$prompt" "$default" >&2
        else
            printf "%s (optional, press Enter to skip): " "$prompt" >&2
        fi
    else
        if [ -n "$default" ]; then
            printf "%s [${YELLOW}%s${NC}]: " "$prompt" "$default" >&2
        else
            printf "%s (required): " "$prompt" >&2
        fi
    fi
    
    read result
    
    if [ -z "$result" ]; then
        if [ "$optional" = "true" ]; then
            echo ""  # Return empty for optional fields
        else
            if [ -n "$default" ]; then
                echo "$default"
            else
                # Required field with no default - ask again
                print_msg $RED "This field is required. Please provide a value." >&2
                read_input "$prompt" "$default" "$optional"
            fi
        fi
    else
        echo "$result"
    fi
}

# Function to read boolean input
read_bool() {
    local prompt=$1
    local default=$2
    
    local default_display=""
    if [ "$default" = "true" ]; then
        default_display="Y/n"
    else
        default_display="y/N"
    fi
    
    printf "%s [${YELLOW}%s${NC}]: " "$prompt" "$default_display" >&2
    read result
    
    case "$result" in
        [Yy]|[Yy][Ee][Ss]|[Tt][Rr][Uu][Ee])
            echo "true"
            ;;
        [Nn]|[Nn][Oo]|[Ff][Aa][Ll][Ss][Ee])
            echo "false"
            ;;
        "")
            echo "$default"
            ;;
        *)
            print_msg $RED "Please answer yes or no." >&2
            read_bool "$prompt" "$default"
            ;;
    esac
}

# Function to create main config.toml
create_main_config() {
    print_msg $BLUE "\n=== Setting up Main Configuration (config.toml) ==="
    
    # Check if config.toml already exists
    if [ -f "config.toml" ]; then
        print_msg $YELLOW "config.toml already exists."
        backup_choice=$(read_bool "Do you want to backup and recreate it?" "true")
        if [ "$backup_choice" = "true" ]; then
            backup_file="config.toml.backup.$(date +%Y%m%d_%H%M%S)"
            mv config.toml "$backup_file"
            print_msg $GREEN "Existing config backed up to: $backup_file"
        else
            print_msg $YELLOW "Keeping existing config.toml"
            return
        fi
    fi
    
    print_msg $GREEN "\nCreating config.toml from template..."
    cp assets/config.template.toml config.toml
    
    # TikTok settings
    print_msg $BLUE "\n--- TikTok API Settings ---"
    print_msg $YELLOW "MS Token is required for comment extraction."
    print_msg $YELLOW "To get it: Open TikTok in browser → DevTools → Application → Cookies → find 'msToken'"
    ms_token=$(read_input "Enter MS_TOKEN" "" "true")
    if [ -n "$ms_token" ]; then
        sed -i .bak "s|ms_token = \"YOUR_MS_TOKEN_HERE\"|ms_token = \"$ms_token\"|" config.toml
    fi
    
    # Input settings
    print_msg $BLUE "\n--- Input Settings ---"
    urls_file=$(read_input "Default URLs file path" "data/urls.txt" "true")
    if [ -n "$urls_file" ]; then
        sed -i .bak "s|default_urls_file = \"data/urls.txt\"|default_urls_file = \"$urls_file\"|" config.toml
    fi
    
    limit=$(read_input "URL processing limit (0 = no limit)" "0" "true")
    if [ -n "$limit" ]; then
        sed -i .bak "s|limit = 0|limit = $limit|" config.toml
    fi
    
    # Download settings
    print_msg $BLUE "\n--- Download Settings ---"
    output_dir=$(read_input "Output directory" "downloads" "true")
    if [ -n "$output_dir" ]; then
        sed -i .bak "s|output_dir = \"downloads\"|output_dir = \"$output_dir\"|" config.toml
    fi
    
    quality=$(read_input "Video quality (best/worst/720p/480p/360p)" "best" "true")
    if [ -n "$quality" ]; then
        sed -i .bak "s|quality = \"best\"|quality = \"$quality\"|" config.toml
    fi
    
    audio_only=$(read_bool "Download audio only as MP3?" "false")
    sed -i .bak "s|audio_only = false|audio_only = $audio_only|" config.toml
    
    use_whisper=$(read_bool "Use Whisper for transcription?" "true")
    sed -i .bak "s|use_whisper = true|use_whisper = $use_whisper|" config.toml
    
    if [ "$use_whisper" = "true" ]; then
        force_cpu=$(read_bool "Force CPU for Whisper (disable GPU)?" "false")
        sed -i .bak "s|force_cpu = false|force_cpu = $force_cpu|" config.toml
    fi
    
    # Comments settings
    print_msg $BLUE "\n--- Comments Settings ---"
    max_comments=$(read_input "Maximum comments per video (0 = all)" "10" "true")
    if [ -n "$max_comments" ]; then
        sed -i .bak "s|max_comments = 10|max_comments = $max_comments|" config.toml
    fi
    
    # Processing settings
    print_msg $BLUE "\n--- Processing Settings ---"
    batch_size=$(read_input "Batch size (save every N videos)" "10" "true")
    if [ -n "$batch_size" ]; then
        sed -i .bak "s|batch_size = 10|batch_size = $batch_size|" config.toml
    fi
    
    delay=$(read_input "Delay between requests (seconds)" "2" "true")
    if [ -n "$delay" ]; then
        sed -i .bak "s|delay = 2|delay = $delay|" config.toml
    fi
    
    workers=$(read_input "Number of worker processes" "1" "true")
    if [ -n "$workers" ]; then
        sed -i .bak "s|workers = 1|workers = $workers|" config.toml
    fi
    
    # Output settings
    print_msg $BLUE "\n--- Output Settings ---"
    json_output=$(read_input "JSON output file" "data/master2.json" "true")
    if [ -n "$json_output" ]; then
        sed -i .bak "s|json_output = \"data/master2.json\"|json_output = \"$json_output\"|" config.toml
    fi
    
    # Network settings
    print_msg $BLUE "\n--- Network Settings (Optional) ---"
    proxy=$(read_input "Proxy URL (e.g., http://proxy:port)" "" "true")
    if [ -n "$proxy" ]; then
        sed -i .bak "s|proxy = \"\"|proxy = \"$proxy\"|" config.toml
    fi
    
    # Clean up backup files
    rm -f config.toml.bak
    
    print_msg $GREEN "\n✓ config.toml created successfully!"
}

# Function to setup PostgreSQL database
setup_database() {
    print_msg $BLUE "\n=== Setting up PostgreSQL Database ==="
    
    # Detect OS
    OS="$(uname -s)"
    
    # Check if PostgreSQL is installed
    if ! command -v psql &> /dev/null; then
        print_msg $YELLOW "PostgreSQL is not installed."
        install_choice=$(read_bool "Would you like instructions to install it?" "true")
        
        if [ "$install_choice" = "true" ]; then
            case "$OS" in
                Linux*)
                    print_msg $GREEN "\n--- Ubuntu/Debian Installation ---"
                    print_msg $YELLOW "Run the following commands:"
                    print_msg $BLUE "sudo apt update"
                    print_msg $BLUE "sudo apt install postgresql postgresql-contrib"
                    print_msg $BLUE "sudo systemctl start postgresql"
                    print_msg $BLUE "sudo systemctl enable postgresql"
                    ;;
                Darwin*)
                    print_msg $GREEN "\n--- macOS Installation ---"
                    print_msg $YELLOW "Using Homebrew:"
                    print_msg $BLUE "brew install postgresql@15"
                    print_msg $BLUE "brew services start postgresql@15"
                    ;;
                *)
                    print_msg $RED "Unsupported OS: $OS"
                    ;;
            esac
            print_msg $YELLOW "\nAfter installation, run this setup script again."
            exit 0
        fi
    else
        print_msg $GREEN "✓ PostgreSQL is installed"
        
        # Check if PostgreSQL is running
        if ! pg_isready &> /dev/null; then
            print_msg $YELLOW "PostgreSQL is not running."
            start_choice=$(read_bool "Would you like to start it?" "true")
            
            if [ "$start_choice" = "true" ]; then
                case "$OS" in
                    Linux*)
                        sudo systemctl start postgresql
                        ;;
                    Darwin*)
                        brew services start postgresql
                        ;;
                esac
                sleep 2
                
                if pg_isready &> /dev/null; then
                    print_msg $GREEN "✓ PostgreSQL started successfully"
                else
                    print_msg $RED "Failed to start PostgreSQL. Please start it manually."
                    exit 1
                fi
            fi
        else
            print_msg $GREEN "✓ PostgreSQL is running"
        fi
        
        # Setup database and user
        print_msg $BLUE "\n--- Database Configuration ---"
        
        # Get current user
        CURRENT_USER=$(whoami)
        
        db_user=$(read_input "Database username" "$CURRENT_USER")
        db_name=$(read_input "Database name" "tiktok_scraper")
        db_password=$(read_input "Database password (leave empty for no password)" "" "true")
        
        print_msg $YELLOW "\nCreating database and user..."
        
        # Create user and database
        if [ "$OS" = "Linux" ]; then
            # On Linux, we need to use sudo -u postgres
            sudo -u postgres psql <<EOF 2>/dev/null || true
CREATE USER $db_user WITH PASSWORD '$db_password';
ALTER USER $db_user CREATEDB;
CREATE DATABASE $db_name OWNER $db_user;
GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;
EOF
        else
            # On macOS, use current user
            psql postgres <<EOF 2>/dev/null || true
CREATE USER $db_user WITH PASSWORD '$db_password';
ALTER USER $db_user CREATEDB;
CREATE DATABASE $db_name OWNER $db_user;
GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;
EOF
        fi
        
        # Test connection
        if PGPASSWORD=$db_password psql -U $db_user -d $db_name -c "SELECT 1;" &> /dev/null; then
            print_msg $GREEN "✓ Database setup successful!"
            
            # Update config.toml if it exists
            if [ -f "config.toml" ]; then
                update_config=$(read_bool "Update config.toml with database settings?" "true")
                if [ "$update_config" = "true" ]; then
                    # Update database section in config.toml
                    sed -i.bak -e "/\[database\]/,/\[.*\]/{
                        s/enabled = .*/enabled = true/
                        s/host = .*/host = \"localhost\"/
                        s/port = .*/port = 5432/
                        s/database = .*/database = \"$db_name\"/
                        s/user = .*/user = \"$db_user\"/
                        s/password = .*/password = \"$db_password\"/
                    }" config.toml
                    rm -f config.toml.bak
                    print_msg $GREEN "✓ config.toml updated with database settings"
                fi
            fi
            
            # Run database migrations and schema setup
            if [ -f "database/schema.sql" ]; then
                migrate_choice=$(read_bool "Run database migrations to create/update tables?" "true")
                if [ "$migrate_choice" = "true" ]; then
                    print_msg $YELLOW "Creating/updating database schema..."
                    
                    # Apply the main schema (safe to run multiple times due to IF NOT EXISTS)
                    PGPASSWORD=$db_password psql -U $db_user -d $db_name -f database/schema.sql 2>&1 | \
                        grep -v "already exists" | grep -v "NOTICE:" || true
                    
                    print_msg $GREEN "✓ Database schema applied"
                    
                    # Check if medallion migration is needed
                    print_msg $YELLOW "Checking medallion architecture..."
                    
                    # Check if data needs migration to medallion architecture
                    NEED_MIGRATION=$(PGPASSWORD=$db_password psql -U $db_user -d $db_name -tAc \
                        "SELECT COUNT(*) FROM public.videos WHERE NOT EXISTS 
                         (SELECT 1 FROM silver.videos WHERE silver.videos.video_id = public.videos.video_id);" 2>/dev/null || echo "0")
                    
                    if [ "$NEED_MIGRATION" -gt 0 ]; then
                        print_msg $YELLOW "Found $NEED_MIGRATION videos to migrate to medallion architecture"
                        
                        # Run migration function
                        PGPASSWORD=$db_password psql -U $db_user -d $db_name -c \
                            "SELECT migrate_to_medallion();" 2>/dev/null || \
                            print_msg $YELLOW "Migration function will be available after schema is applied"
                        
                        print_msg $GREEN "✓ Data migrated to medallion architecture"
                    else
                        print_msg $GREEN "✓ Medallion architecture is up to date"
                    fi
                    
                    # Compute ML features
                    print_msg $YELLOW "Computing ML features in gold layer..."
                    FEATURES_COMPUTED=$(PGPASSWORD=$db_password psql -U $db_user -d $db_name -tAc \
                        "SELECT etl_silver_to_gold();" 2>/dev/null || echo "0")
                    
                    if [ "$FEATURES_COMPUTED" -gt 0 ]; then
                        print_msg $GREEN "✓ Computed features for $FEATURES_COMPUTED videos"
                    else
                        print_msg $GREEN "✓ ML features up to date"
                    fi
                    
                    # Display database statistics
                    print_msg $BLUE "\n--- Database Statistics ---"
                    PGPASSWORD=$db_password psql -U $db_user -d $db_name <<EOF 2>/dev/null || true
SELECT 
    'Public Videos' as layer, COUNT(*) as count FROM public.videos
UNION ALL
SELECT 'Silver Videos', COUNT(*) FROM silver.videos
UNION ALL
SELECT 'Gold Features', COUNT(*) FROM gold.ml_features
UNION ALL
SELECT 'Transcriptions', COUNT(*) FROM public.transcriptions;
EOF
                    
                    # Legacy migration if master2.json exists
                    if [ -f "data/master2.json" ]; then
                        json_migrate=$(read_bool "Import data from master2.json?" "false")
                        if [ "$json_migrate" = "true" ]; then
                            print_msg $YELLOW "Importing from master2.json..."
                            python database/migrate_json_to_postgres.py data/master2.json || \
                                print_msg $YELLOW "JSON migration may need manual attention"
                        fi
                    fi
                fi
            fi
            
        else
            print_msg $YELLOW "Database created but connection test failed."
            print_msg $YELLOW "You may need to configure pg_hba.conf for authentication."
            print_msg $YELLOW "Location: /etc/postgresql/*/main/pg_hba.conf (Linux) or /usr/local/var/postgres/pg_hba.conf (macOS)"
        fi
    fi
}

# Function to setup Django server
setup_django() {
    print_msg $BLUE "\n=== Setting up Django Server ==="
    
    # Check if Django is installed
    if ! python -c "import django" 2>/dev/null; then
        print_msg $YELLOW "Django is not installed."
        install_choice=$(read_bool "Install Django and dependencies?" "true")
        
        if [ "$install_choice" = "true" ]; then
            print_msg $YELLOW "Installing Django dependencies..."
            pip install django djangorestframework django-cors-headers psycopg2-binary
            print_msg $GREEN "✓ Django dependencies installed"
        else
            print_msg $RED "Django is required for the server. Exiting."
            exit 1
        fi
    else
        print_msg $GREEN "✓ Django is installed"
    fi
    
    # Configure Django settings
    if [ -f "tiktok_scraper/settings.py" ]; then
        print_msg $BLUE "\n--- Django Configuration ---"
        
        # Get database settings
        db_user=$(read_input "Database username" "$(whoami)")
        db_name=$(read_input "Database name" "tiktok_scraper")
        db_password=$(read_input "Database password (leave empty for no password)" "" "true")
        db_host=$(read_input "Database host" "localhost")
        db_port=$(read_input "Database port" "5432")
        
        # Update Django settings
        print_msg $YELLOW "Updating Django settings..."
        
        # Update database settings in Django
        python -c "
import re

with open('tiktok_scraper/settings.py', 'r') as f:
    content = f.read()

# Update database settings
content = re.sub(
    r'\"NAME\": \".*?\"',
    f'\"NAME\": \"$db_name\"',
    content
)
content = re.sub(
    r'\"USER\": \".*?\"',
    f'\"USER\": \"$db_user\"',
    content
)
content = re.sub(
    r'\"PASSWORD\": \".*?\"',
    f'\"PASSWORD\": \"$db_password\"',
    content
)
content = re.sub(
    r'\"HOST\": \".*?\"',
    f'\"HOST\": \"$db_host\"',
    content
)
content = re.sub(
    r'\"PORT\": \".*?\"',
    f'\"PORT\": \"$db_port\"',
    content
)

with open('tiktok_scraper/settings.py', 'w') as f:
    f.write(content)
" || print_msg $YELLOW "Manual update of settings.py may be needed"
        
        print_msg $GREEN "✓ Django settings updated"
        
        # Run migrations
        migrate_choice=$(read_bool "Run Django migrations?" "true")
        if [ "$migrate_choice" = "true" ]; then
            print_msg $YELLOW "Running Django migrations..."
            python manage.py makemigrations
            python manage.py migrate
            print_msg $GREEN "✓ Migrations completed"
        fi
        
        # Create superuser
        superuser_choice=$(read_bool "Create Django superuser account?" "true")
        if [ "$superuser_choice" = "true" ]; then
            print_msg $YELLOW "Creating superuser..."
            python manage.py createsuperuser
        fi
        
        # Network configuration
        print_msg $BLUE "\n--- Network Configuration ---"
        network_choice=$(read_bool "Configure for network access (not just localhost)?" "true")
        if [ "$network_choice" = "true" ]; then
            print_msg $GREEN "✓ Server configured for network access"
            print_msg $YELLOW "\nTo start the Django server with network access:"
            print_msg $BLUE "python manage.py runserver 0.0.0.0:8000"
            print_msg $YELLOW "\nOther devices can connect using your IP address:"
            if command -v ip &> /dev/null; then
                IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v 127.0.0.1 | head -1)
            elif command -v ifconfig &> /dev/null; then
                IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
            else
                IP="<your-ip-address>"
            fi
            print_msg $BLUE "http://$IP:8000"
        else
            print_msg $YELLOW "\nTo start the Django server (localhost only):"
            print_msg $BLUE "python manage.py runserver"
        fi
        
    else
        print_msg $RED "Django project not found. Please ensure you're in the project directory."
        exit 1
    fi
}

# Function to create test config.toml
create_test_config() {
    print_msg $BLUE "\n=== Setting up Test Configuration (tests/test_config.toml) ==="
    
    # Check if test_config.toml already exists
    if [ -f "tests/test_config.toml" ]; then
        print_msg $YELLOW "tests/test_config.toml already exists."
        backup_choice=$(read_bool "Do you want to backup and recreate it?" "true")
        if [ "$backup_choice" = "true" ]; then
            backup_file="tests/test_config.toml.backup.$(date +%Y%m%d_%H%M%S)"
            mv tests/test_config.toml "$backup_file"
            print_msg $GREEN "Existing config backed up to: $backup_file"
        else
            print_msg $YELLOW "Keeping existing tests/test_config.toml"
            return
        fi
    fi
    
    print_msg $GREEN "\nCreating tests/test_config.toml from template..."
    cp assets/test_config.template.toml tests/test_config.toml
    
    # TikTok settings
    print_msg $BLUE "\n--- Test TikTok API Settings ---"
    print_msg $YELLOW "You can use the same MS Token as the main config or a different one for testing."
    test_ms_token=$(read_input "Enter MS_TOKEN for tests" "" "true")
    if [ -n "$test_ms_token" ]; then
        sed -i .bak "s|ms_token = \"YOUR_MS_TOKEN_HERE\"|ms_token = \"$test_ms_token\"|" tests/test_config.toml
    fi
    
    # Test settings
    print_msg $BLUE "\n--- Test Settings ---"
    test_url_count=$(read_input "Number of URLs to test" "3" "true")
    if [ -n "$test_url_count" ]; then
        sed -i .bak "s|test_url_count = 3|test_url_count = $test_url_count|" tests/test_config.toml
    fi
    
    timeout=$(read_input "Timeout per video (seconds)" "120" "true")
    if [ -n "$timeout" ]; then
        sed -i .bak "s|timeout_per_video = 120|timeout_per_video = $timeout|" tests/test_config.toml
    fi
    
    verbose=$(read_bool "Enable verbose logging for tests?" "true")
    sed -i .bak "s|verbose = true|verbose = $verbose|" tests/test_config.toml
    
    cleanup=$(read_bool "Clean up test files after completion?" "false")
    sed -i .bak "s|cleanup_after_test = false|cleanup_after_test = $cleanup|" tests/test_config.toml
    
    # Clean up backup files
    rm -f tests/test_config.toml.bak
    
    print_msg $GREEN "\n✓ tests/test_config.toml created successfully!"
}

# Main script
print_msg $GREEN "========================================="
print_msg $GREEN "  TikTok Scraper Configuration Setup"
print_msg $GREEN "========================================="

# Check if templates exist
if [ ! -f "assets/config.template.toml" ]; then
    print_msg $RED "Error: assets/config.template.toml not found!"
    exit 1
fi

if [ ! -f "assets/test_config.template.toml" ]; then
    print_msg $RED "Error: assets/test_config.template.toml not found!"
    exit 1
fi

# Ask which configs to set up
print_msg $BLUE "\nWhich configuration files would you like to set up?"
print_msg $YELLOW "1) Main config only (config.toml)"
print_msg $YELLOW "2) Test config only (tests/test_config.toml)"
print_msg $YELLOW "3) Both configs"
print_msg $YELLOW "4) Database setup (PostgreSQL)"
print_msg $YELLOW "5) Django server setup"
echo -n "Enter your choice [1-5]: "
read choice

case "$choice" in
    1)
        create_main_config
        ;;
    2)
        create_test_config
        ;;
    3)
        create_main_config
        create_test_config
        ;;
    4)
        setup_database
        ;;
    5)
        setup_django
        ;;
    *)
        print_msg $RED "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Create necessary directories
print_msg $BLUE "\nCreating required directories..."
mkdir -p data downloads src tests logs

# Final message
print_msg $GREEN "\n========================================="
print_msg $GREEN "  Setup Complete!"
print_msg $GREEN "========================================="
print_msg $YELLOW "\nNext steps:"
print_msg $YELLOW "1. Review your configuration file(s)"
print_msg $YELLOW "2. Add URLs to data/urls.txt (or your configured path)"
print_msg $YELLOW "3. Run: python collector.py"
print_msg $YELLOW "4. To test: cd tests && python test_robust_downloader.py"

# Make the script executable
chmod +x setup.sh 2>/dev/null || true