#!/bin/bash

# Reddit Subreddit Discovery Script
# Automatically discovers popular subreddits from TikTok data
# Usage: ./discover_subreddits.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIKTOK_DATA_PATH="../master2.json"
OUTPUT_DIR="subreddit_discovery_results"
MAX_USERS_TO_CHECK=30

# Function to print colored output
print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

print_step() {
    echo -e "${CYAN}[STEP $1]${NC} $2"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if TikTok data file exists
check_tiktok_data() {
    print_step "1" "Checking TikTok data file..."
    
    if [ ! -f "$TIKTOK_DATA_PATH" ]; then
        print_error "TikTok data file not found: $TIKTOK_DATA_PATH"
        echo "Please ensure master2.json exists in the parent directory."
        exit 1
    fi
    
    # Get file size and record count
    file_size=$(du -h "$TIKTOK_DATA_PATH" | cut -f1)
    record_count=$(python3 -c "import json; data=json.load(open('$TIKTOK_DATA_PATH')); print(len(data))" 2>/dev/null || echo "unknown")
    
    print_success "Found TikTok data file ($file_size, $record_count videos)"
}

# Check Python dependencies
check_dependencies() {
    print_step "2" "Checking dependencies..."
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check required Python modules
    python3 -c "import json, re, requests, time" 2>/dev/null || {
        print_warning "Installing requests module..."
        pip3 install requests --break-system-packages --quiet || {
            print_error "Failed to install requests. Please install manually: pip3 install requests"
            exit 1
        }
    }
    
    print_success "Dependencies OK"
}

# Create the discovery Python script
create_discovery_script() {
    print_step "3" "Creating discovery script..."
    
    cat > "$SCRIPT_DIR/auto_discovery.py" << 'EOF'
#!/usr/bin/env python3
"""
Automated Reddit subreddit discovery from TikTok data.
"""

import json
import re
import os
import sys
import requests
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

def extract_reddit_usernames(tiktok_json_path):
    """Extract Reddit usernames from TikTok data."""
    
    print(f"🔍 Analyzing TikTok data: {tiktok_json_path}")
    
    with open(tiktok_json_path, 'r', encoding='utf-8') as f:
        tiktok_data = json.load(f)
    
    total_videos = len(tiktok_data)
    print(f"📊 Total videos to analyze: {total_videos:,}")
    
    # Reddit username patterns
    patterns = {
        'u_slash': re.compile(r'u/([a-zA-Z0-9_-]{3,20})', re.IGNORECASE),
        'user_colon': re.compile(r'reddit user[:\s]+"?([a-zA-Z0-9_-]{3,20})"?', re.IGNORECASE),
        'source_reddit': re.compile(r'source[:\s]+reddit[:\s]+([a-zA-Z0-9_-]{3,20})', re.IGNORECASE),
        'reddit_username': re.compile(r'reddit.*?username[:\s]+([a-zA-Z0-9_-]{3,20})', re.IGNORECASE),
        'posted_by': re.compile(r'posted by[:\s]+([a-zA-Z0-9_-]{3,20})', re.IGNORECASE)
    }
    
    found_usernames = set()
    pattern_counts = defaultdict(int)
    
    for i, video in enumerate(tiktok_data):
        if i % 500 == 0:
            print(f"  📹 Progress: {i:,}/{total_videos:,} videos ({i/total_videos*100:.1f}%)")
        
        try:
            # Search in all text fields
            search_fields = []
            for field in ['title', 'description', 'whisper_transcription']:
                if field in video and video[field]:
                    search_fields.append(video[field])
            
            # Search in comments
            if 'top_comments' in video and video['top_comments']:
                for comment in video['top_comments']:
                    if 'comment_text' in comment and comment['comment_text']:
                        search_fields.append(comment['comment_text'])
            
            # Apply patterns
            for text in search_fields:
                for pattern_name, pattern in patterns.items():
                    matches = pattern.findall(text)
                    for username in matches:
                        username = username.lower().strip()
                        if len(username) >= 3 and username not in ['reddit', 'user', 'source', 'posted']:
                            found_usernames.add(username)
                            pattern_counts[pattern_name] += 1
        
        except Exception:
            continue
    
    print(f"✅ Extraction complete!")
    print(f"  - Unique usernames: {len(found_usernames)}")
    print(f"  - Total matches: {sum(pattern_counts.values())}")
    
    return list(found_usernames)

def get_user_subreddits(username, limit=25):
    """Get user's subreddits using public Reddit API."""
    
    try:
        url = f"https://www.reddit.com/user/{username}/submitted.json?limit={limit}"
        headers = {'User-Agent': 'SubredditDiscovery/1.0'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            subreddits = set()
            
            if 'data' in data and 'children' in data['data']:
                for post in data['data']['children']:
                    if 'data' in post and 'subreddit' in post['data']:
                        subreddit = post['data']['subreddit'].lower()
                        subreddits.add(subreddit)
            
            return list(subreddits)
        
        elif response.status_code == 404:
            return None  # User not found
        else:
            return []
            
    except Exception:
        return []

def discover_subreddits(usernames, max_users):
    """Discover subreddits from usernames."""
    
    print(f"\n🏘️ Discovering subreddits from up to {max_users} users...")
    
    subreddit_counts = defaultdict(set)
    successful_users = []
    failed_count = 0
    
    usernames_to_check = usernames[:max_users]
    
    for i, username in enumerate(usernames_to_check, 1):
        print(f"  📊 User {i:2d}/{len(usernames_to_check)}: u/{username:<20}", end=" ")
        
        user_subreddits = get_user_subreddits(username)
        
        if user_subreddits is None:
            print("(not found)")
            failed_count += 1
        elif user_subreddits:
            print(f"({len(user_subreddits)} subreddits)")
            successful_users.append(username)
            for subreddit in user_subreddits:
                subreddit_counts[subreddit].add(username)
        else:
            print("(no posts/private)")
            failed_count += 1
        
        # Rate limiting
        time.sleep(1)
    
    print(f"\n📈 Discovery Results:")
    print(f"  - Successful: {len(successful_users)} users")
    print(f"  - Failed: {failed_count} users")
    print(f"  - Raw subreddits found: {len(subreddit_counts)}")
    
    # Filter subreddits with 2+ users
    filtered_subreddits = []
    for subreddit, users in subreddit_counts.items():
        if len(users) >= 2:
            filtered_subreddits.append({
                'subreddit': subreddit,
                'user_count': len(users),
                'users': sorted(list(users))
            })
    
    # Sort by user count
    filtered_subreddits.sort(key=lambda x: x['user_count'], reverse=True)
    
    print(f"  - Filtered subreddits (2+ users): {len(filtered_subreddits)}")
    
    return filtered_subreddits, successful_users, failed_count

def categorize_subreddit(name):
    """Categorize subreddit."""
    
    name_lower = name.lower()
    
    categories = {
        'relationships': ['relationship', 'dating', 'marriage', 'aitah', 'amitheasshole', 'tifu', 'offmychest'],
        'advice': ['advice', 'askreddit', 'nostupidquestions', 'explainlikeimfive', 'legaladvice'],
        'mental_health': ['anxiety', 'depression', 'mentalhealth', 'therapy', 'ptsd'],
        'entertainment': ['movie', 'tv', 'netflix', 'entertainment', 'celebrity', 'music'],
        'gaming': ['gaming', 'games', 'steam', 'nintendo', 'xbox', 'playstation'],
        'technology': ['technology', 'programming', 'coding', 'computers', 'android', 'apple'],
        'lifestyle': ['food', 'fitness', 'fashion', 'travel', 'diy', 'cooking'],
        'humor': ['funny', 'meme', 'dankmemes', 'cursed', 'holup'],
        'creative': ['art', 'photography', 'writing', 'design', 'crafts'],
        'educational': ['todayilearned', 'science', 'history', 'explainlikeimfive'],
        'support': ['support', 'help', 'mentalhealth', 'depression', 'anxiety']
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in name_lower:
                return category
    
    return 'general'

def create_reports(subreddit_rankings, successful_users, failed_count, output_dir):
    """Create comprehensive reports."""
    
    print(f"\n📄 Creating reports in {output_dir}/...")
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Add categories
    for ranking in subreddit_rankings:
        ranking['category'] = categorize_subreddit(ranking['subreddit'])
    
    # JSON report
    report_data = {
        'discovery_summary': {
            'total_usernames_checked': len(successful_users) + failed_count,
            'successful_users': len(successful_users),
            'failed_users': failed_count,
            'subreddits_discovered': len(subreddit_rankings),
            'timestamp': datetime.now().isoformat()
        },
        'discovered_subreddits': subreddit_rankings,
        'successful_users': successful_users
    }
    
    json_file = os.path.join(output_dir, "discovery_results.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    # Create summary report
    summary_lines = [
        "🎯 Reddit Subreddit Discovery Results",
        "=" * 50,
        "",
        f"📊 Discovery Summary:",
        f"- Total usernames checked: {len(successful_users) + failed_count}",
        f"- Successful users: {len(successful_users)}",
        f"- Failed users: {failed_count}",
        f"- Unique subreddits discovered: {len(subreddit_rankings)}",
        ""
    ]
    
    if subreddit_rankings:
        summary_lines.extend([
            "🏆 Discovered Subreddits (Ranked by Activity):",
            ""
        ])
        
        for i, ranking in enumerate(subreddit_rankings, 1):
            summary_lines.extend([
                f"{i:2d}. r/{ranking['subreddit']} ({ranking['category']})",
                f"    👥 {ranking['user_count']} users: {', '.join(ranking['users'][:5])}{'...' if len(ranking['users']) > 5 else ''}",
                ""
            ])
        
        # Category breakdown
        categories = Counter(r['category'] for r in subreddit_rankings)
        summary_lines.extend([
            "📂 Categories Found:",
            ""
        ])
        for category, count in categories.most_common():
            summary_lines.append(f"- {category}: {count} subreddits")
        
        summary_lines.extend([
            "",
            "🎯 FINAL SUBREDDIT LIST (No Duplicates):",
            ""
        ])
        
        for i, ranking in enumerate(subreddit_rankings, 1):
            summary_lines.append(f"{i}. r/{ranking['subreddit']}")
    
    summary_lines.extend([
        "",
        f"⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "💡 Next Steps:",
        "- Use these subreddits for content monitoring",
        "- Set up Reddit API for deeper post scraping",
        "- Track popular posts from these communities"
    ])
    
    summary_file = os.path.join(output_dir, "DISCOVERED_SUBREDDITS.txt")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(summary_lines))
    
    print(f"✅ Reports created:")
    print(f"  - JSON data: {json_file}")
    print(f"  - Summary: {summary_file}")
    
    return subreddit_rankings

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 auto_discovery.py <tiktok_json> <output_dir> <max_users>")
        sys.exit(1)
    
    tiktok_json_path = sys.argv[1]
    output_dir = sys.argv[2]
    max_users = int(sys.argv[3])
    
    print("🚀 Automated Reddit Subreddit Discovery")
    print("=" * 50)
    
    # Step 1: Extract usernames
    usernames = extract_reddit_usernames(tiktok_json_path)
    if not usernames:
        print("❌ No Reddit usernames found!")
        return
    
    # Step 2: Discover subreddits
    subreddit_rankings, successful_users, failed_count = discover_subreddits(usernames, max_users)
    if not subreddit_rankings:
        print("❌ No subreddits discovered!")
        return
    
    # Step 3: Create reports
    create_reports(subreddit_rankings, successful_users, failed_count, output_dir)
    
    # Show preview
    print(f"\n🎯 DISCOVERY COMPLETE!")
    print(f"Top {min(10, len(subreddit_rankings))} discovered subreddits:")
    for i, ranking in enumerate(subreddit_rankings[:10], 1):
        print(f"{i:2d}. r/{ranking['subreddit']} - {ranking['user_count']} users ({ranking['category']})")

if __name__ == "__main__":
    main()
EOF
    
    print_success "Discovery script created"
}

# Run the discovery process
run_discovery() {
    print_step "4" "Running subreddit discovery..."
    print_info "This will take a few minutes with rate limiting..."
    echo ""
    
    cd "$SCRIPT_DIR"
    
    python3 auto_discovery.py "$TIKTOK_DATA_PATH" "$OUTPUT_DIR" "$MAX_USERS_TO_CHECK"
    
    if [ $? -eq 0 ]; then
        print_success "Discovery completed successfully!"
    else
        print_error "Discovery failed"
        exit 1
    fi
}

# Display results
show_results() {
    print_step "5" "Displaying results..."
    
    if [ -f "$OUTPUT_DIR/DISCOVERED_SUBREDDITS.txt" ]; then
        echo ""
        echo -e "${PURPLE}📄 SUMMARY REPORT:${NC}"
        echo ""
        head -n 50 "$OUTPUT_DIR/DISCOVERED_SUBREDDITS.txt"
        echo ""
        print_info "Full report: $OUTPUT_DIR/DISCOVERED_SUBREDDITS.txt"
        print_info "JSON data: $OUTPUT_DIR/discovery_results.json"
    else
        print_warning "Summary report not found"
    fi
}

# Cleanup function
cleanup() {
    print_step "6" "Cleaning up..."
    
    # Remove temporary script
    if [ -f "$SCRIPT_DIR/auto_discovery.py" ]; then
        rm "$SCRIPT_DIR/auto_discovery.py"
        print_success "Temporary files cleaned up"
    fi
}

# Main execution
main() {
    print_header "🎯 REDDIT SUBREDDIT DISCOVERY"
    echo ""
    print_info "This script will analyze your TikTok data to discover relevant subreddits"
    print_info "TikTok data: $TIKTOK_DATA_PATH"
    print_info "Output directory: $OUTPUT_DIR"
    print_info "Max users to check: $MAX_USERS_TO_CHECK"
    echo ""
    
    # Run all steps
    check_tiktok_data
    check_dependencies
    create_discovery_script
    run_discovery
    show_results
    cleanup
    
    echo ""
    print_header "✅ DISCOVERY COMPLETE!"
    echo ""
    print_success "Subreddit discovery completed successfully!"
    print_info "Results saved to: $OUTPUT_DIR/"
    echo ""
    print_info "To run again: ./discover_subreddits.sh"
    echo ""
}

# Handle interrupts
trap 'echo -e "\n${RED}❌ Discovery interrupted by user${NC}"; cleanup; exit 1' INT TERM

# Run main function
main "$@"