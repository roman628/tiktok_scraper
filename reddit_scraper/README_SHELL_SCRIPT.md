# 🚀 One-Click Reddit Subreddit Discovery

## Quick Start

Simply run this command to discover subreddits from your TikTok data:

```bash
./discover_subreddits.sh
```

That's it! The script does everything automatically.

## What It Does

1. **Analyzes your TikTok data** (`../master2.json`) for Reddit username mentions
2. **Extracts Reddit usernames** using advanced pattern matching
3. **Discovers subreddits** by analyzing where those users are active
4. **Ranks communities** by user activity and engagement
5. **Generates reports** with actionable insights

## Latest Results

**🎯 DISCOVERED SUBREDDITS (5 Total)**

1. **r/aitah** (10 users) - Relationships/Advice
2. **r/relationships** (5 users) - Relationship Drama  
3. **r/amitheasshole** (4 users) - Moral Judgment
4. **r/notinteresting** (2 users) - Humor/General
5. **r/relationship_advice** (2 users) - Problem Solving

## Performance Stats

- **TikTok Videos Analyzed**: 1,774 videos
- **Reddit Usernames Found**: 109 unique usernames  
- **Users Successfully Analyzed**: 22 out of 30 checked
- **Discovery Success Rate**: 73%
- **Processing Time**: ~2 minutes with rate limiting

## Output Files

After running, you'll find:

```
subreddit_discovery_results/
├── DISCOVERED_SUBREDDITS.txt    # Human-readable summary
└── discovery_results.json       # Structured data for analysis
```

## Script Features

✅ **Fully Automated** - No manual setup required  
✅ **Smart Pattern Matching** - Finds usernames in multiple formats  
✅ **Rate Limited** - Respects Reddit's API limits  
✅ **Error Handling** - Graceful failure recovery  
✅ **Progress Tracking** - Real-time status updates  
✅ **Colored Output** - Easy to read terminal display  
✅ **Self-Cleaning** - Removes temporary files automatically  

## Customization

To modify the behavior, edit these variables in the script:

```bash
MAX_USERS_TO_CHECK=30        # How many users to analyze
OUTPUT_DIR="results"         # Where to save results
TIKTOK_DATA_PATH="../master2.json"  # Path to your TikTok data
```

## Requirements

- **Python 3** (pre-installed on macOS)
- **requests library** (auto-installed if missing)
- **Internet connection** (for Reddit API calls)

## Troubleshooting

**Script won't run?**
```bash
chmod +x discover_subreddits.sh
```

**Missing TikTok data?**
- Ensure `master2.json` exists in the parent directory
- Check the file path in the script configuration

**Rate limiting errors?**
- The script includes 1-second delays between requests
- Reddit may temporarily block aggressive scraping

## Next Steps

Use the discovered subreddits to:

1. **Monitor for viral content** using Reddit's RSS feeds
2. **Set up content alerts** for popular posts
3. **Analyze posting patterns** for optimal timing
4. **Create content calendars** based on trending topics

## Technical Details

The script creates a temporary Python program that:

- Uses regex patterns to find Reddit usernames in TikTok content
- Queries Reddit's public JSON API (no authentication needed)
- Analyzes user post history to identify active subreddits
- Filters results to show only communities with multiple active users
- Categorizes subreddits by content type (relationships, humor, etc.)

## Re-running

To run the discovery again (e.g., with updated TikTok data):

```bash
./discover_subreddits.sh
```

The script will overwrite previous results and generate fresh data.

---

**🎯 Perfect for:** Content creators who want to identify the most relevant Reddit communities for their TikTok audience based on actual data analysis.