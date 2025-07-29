# Reddit User Profile Scraper

A comprehensive Reddit scraper that extracts user profiles, finds their most popular posts, and analyzes their activity across different subreddits. Perfect for content creators who want to understand successful Reddit users and their posting strategies.

## Features

🎯 **User Profile Analysis**
- Complete user profile extraction (karma, account age, verification status)
- Comprehensive post history analysis with popularity scoring
- Activity patterns across different subreddits
- Posting time and frequency analysis

📊 **Popular Post Identification** 
- Advanced popularity scoring algorithm considering multiple factors:
  - Upvotes and upvote ratio
  - Comment engagement
  - Awards and gilding
  - Time-based decay factors
- Identifies viral content and best-performing posts
- Percentile ranking against user's other posts

🏘️ **Subreddit Activity Analysis**
- Detailed breakdown of user activity by subreddit
- Performance comparison against subreddit averages
- Community engagement patterns
- Success rates in different subreddits

📤 **Flexible Export Options**
- JSON, CSV, and Excel export formats
- Customizable data filtering and inclusion options
- Human-readable summary reports
- Batch processing for multiple users

## Installation

1. Clone or download the scraper:
```bash
git clone <repository-url>
cd reddit_scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Reddit API credentials:
   - Go to https://www.reddit.com/prefs/apps/
   - Create a new application (select "script")
   - Copy your client ID and secret
   - Create a `.env` file based on `config.env.example`

## Quick Start

### Basic Usage

```bash
# Analyze a single user
python main.py --client-id YOUR_CLIENT_ID --client-secret YOUR_SECRET --username spez

# Get top 50 posts in JSON format
python main.py --client-id YOUR_ID --client-secret YOUR_SECRET --username gallowboob --max-posts 50 --format json

# Export to Excel with full analysis
python main.py --client-id YOUR_ID --client-secret YOUR_SECRET --username username --format excel --include-analysis
```

### Batch Processing

```bash
# Create a file with usernames (one per line)
echo -e "spez\\ngallowboob\\nPoemForYourSprog" > users.txt

# Process all users
python main.py --client-id YOUR_ID --client-secret YOUR_SECRET --batch users.txt --output-dir results/
```

### Subreddit-Specific Analysis

```bash
# Analyze how a user performs in a specific subreddit
python main.py --client-id YOUR_ID --client-secret YOUR_SECRET --subreddit-analysis spez announcements --comparison
```

## Configuration Options

### Authentication
- `--client-id`: Reddit API client ID (required)
- `--client-secret`: Reddit API client secret (required)  
- `--user-agent`: User agent string (default: RedditScraper/1.0)

### Scraping Options
- `--username`: Reddit username to scrape
- `--max-posts`: Maximum posts to analyze (default: 100)
- `--sort-method`: How to sort posts (top, hot, new, rising)
- `--time-filter`: Time period (hour, day, week, month, year, all)

### Export Options
- `--format`: Export format (json, csv, excel)
- `--include-posts`: Include individual posts in export
- `--include-subreddits`: Include subreddit analysis
- `--include-analysis`: Include activity patterns
- `--min-score`: Minimum post score to include
- `--exclude-nsfw`: Exclude NSFW content

### Batch Processing
- `--batch`: File containing usernames (one per line)
- `--output-dir`: Output directory for results

## Output Examples

### JSON Export Structure
```json
{
  "user_profile": {
    "username": "spez",
    "account_age_days": 5475,
    "total_karma": 854123,
    "comment_karma": 742891,
    "link_karma": 111232
  },
  "analysis_metadata": {
    "total_posts_analyzed": 100,
    "avg_post_score": 1247.3,
    "success_rate": 67.5,
    "diversity_score": 23
  },
  "posts": [
    {
      "title": "Popular post title",
      "subreddit": "announcements", 
      "score": 45782,
      "num_comments": 3421,
      "popularity_score": 0.89,
      "url": "https://reddit.com/...",
      "created_utc": "2023-01-15T10:30:00"
    }
  ],
  "subreddit_activity": {
    "announcements": {
      "user_post_count": 12,
      "user_avg_score": 3421.5,
      "subscribers": 89234567,
      "top_posts": [...]
    }
  },
  "activity_patterns": {
    "most_active_subreddits": ["announcements", "changelog", "blog"],
    "posting_times": {"14": 23, "15": 18, "16": 31},
    "best_performing_posts": [...]
  }
}
```

### Summary Report
```
Reddit User Analysis Report
==================================================

User: u/spez
Account Age: 5475 days
Total Karma: 854,123 (Link: 111,232, Comment: 742,891)

Analysis Summary:
- Posts Analyzed: 100
- Average Score: 1,247.3
- Total Score: 124,730
- Success Rate: 67.5%
- Active Subreddits: 23

Most Active Subreddits:
1. r/announcements (12 posts)
2. r/changelog (8 posts)
3. r/blog (6 posts)

Top Performing Posts:
1. "We're testing a new feature..."
   r/announcements | 45,782 points | 3,421 comments
```

## API Requirements

### Reddit API Setup
1. Go to https://www.reddit.com/prefs/apps/
2. Click "Create App" or "Create Another App"
3. Choose "script" as the app type
4. Fill in the name and description
5. Copy the client ID (under the app name) and secret

### Rate Limits
- Reddit API allows 60 requests per minute per OAuth client
- The scraper automatically handles rate limiting and retries
- For large batch jobs, consider using multiple API credentials

## Advanced Features

### Custom Popularity Scoring
The scraper uses a sophisticated popularity scoring algorithm that considers:
- **Raw upvotes** (40% weight): Absolute post score
- **Comment engagement** (25% weight): Number of comments relative to upvotes
- **Awards** (15% weight): Reddit awards and gilding
- **Upvote ratio** (10% weight): Percentage of upvotes vs downvotes
- **Time decay** (10% weight): Newer posts get slight boost

### Performance Comparison
When analyzing users in specific subreddits, the scraper can:
- Compare user's average performance vs subreddit averages
- Calculate performance percentiles
- Identify which subreddits work best for the user
- Show engagement patterns across communities

### Batch Processing Features
- Process multiple users efficiently with rate limiting
- Automatic error handling and retry logic
- Progress tracking and logging
- Configurable output organization

## Troubleshooting

### Common Issues

**"Authentication failed"**
- Check your client ID and secret
- Ensure you created a "script" type application
- Verify your user agent string

**"User not found"**
- Username might be incorrect (case sensitive)
- User account might be suspended or deleted
- User profile might be private

**"Rate limit exceeded"**
- The scraper handles this automatically
- For heavy usage, consider multiple API credentials
- Reduce max-posts or add delays between requests

**"No posts found"**
- User might have no posts or only private posts
- Try different time filters (week, month instead of all)
- Check if user posts mainly comments vs submissions

### Logging
All activities are logged to `reddit_scraper_YYYYMMDD.log` with detailed information about:
- API requests and responses
- Rate limiting events
- Errors and retry attempts
- Processing progress

## Legal and Ethical Considerations

⚠️ **Important Disclaimers:**
- This tool is for educational and research purposes
- Respect Reddit's Terms of Service and API guidelines
- Be mindful of user privacy and data usage
- Don't spam or overload Reddit's servers
- Consider reaching out to users before analyzing their data publicly

### Best Practices
- Use reasonable rate limits and delays
- Don't store sensitive user information unnecessarily
- Respect NSFW and private content flags
- Credit original content creators appropriately
- Consider the impact on the users whose data you're analyzing

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Update documentation as needed
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions, issues, or feature requests:
- Check the troubleshooting section above
- Review existing GitHub issues
- Create a new issue with detailed information
- Include log files and error messages when reporting bugs

---

**Happy scraping! 🎯**