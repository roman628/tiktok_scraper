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
echo -n "Enter your choice [1-3]: "
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