# TikTok Scraper Database Analysis - master2.json

## Database Overview
- **Total Videos**: 1,774 entries
- **File Size**: 15.7MB
- **Format**: JSON array of video objects
- **Date Range**: Based on upload_date field analysis

## Video Data Structure

### Core Video Metadata
| Field | Type | Availability | Description |
|-------|------|--------------|-------------|
| `video_id` | string | 100% | Unique TikTok video identifier |
| `url` | string | 100% | Full TikTok video URL |
| `title` | string | 100% | Video title/caption |
| `description` | string | 99.3% | Extended video description |
| `uploader` | string | 82.6% | TikTok username of creator |
| `uploader_id` | string | 82.6% | Unique user identifier |
| `uploader_url` | string | 82.6% | Creator's profile URL |

### Video Technical Properties
| Field | Type | Availability | Description |
|-------|------|--------------|-------------|
| `duration` | integer | 100% | Video length in seconds |
| `width` | integer | 100% | Video width in pixels |
| `height` | integer | 100% | Video height in pixels |
| `fps` | integer | 82.6% | Frames per second |
| `filesize` | integer | 100% | File size in bytes |
| `format` | string | 82.6% | Video encoding format |

### Engagement Metrics (Primary Scoring Data)
| Field | Type | Availability | Description | Keyword Scoring Relevance |
|-------|------|--------------|-------------|---------------------------|
| `view_count` | integer | 100% | Total video views | **HIGH** - Viral content indicator |
| `like_count` | integer | 100% | Number of likes | **HIGH** - Positive engagement |
| `comment_count` | integer | 100% | Number of comments | **HIGH** - Discussion driver |
| `repost_count` | integer | 82.6% | Number of shares/reposts | **MEDIUM** - Shareability |
| `save_count` | integer | 36.6% | Number of saves | **MEDIUM** - Content value |
| `share_count` | integer | 36.6% | External shares | **MEDIUM** - Cross-platform appeal |

### Text Content for Keyword Extraction
| Field | Type | Availability | Content Quality | Keyword Extraction Value |
|-------|------|--------------|-----------------|-------------------------|
| `title` | string | 100% | High | **CRITICAL** - Primary keyword source |
| `description` | string | 99.3% | High | **CRITICAL** - Hashtags and context |
| `whisper_transcription` | string | 63.2% | Medium-High | **HIGH** - Spoken content analysis |
| `custom_transcription` | string | 30.7% | High | **HIGH** - Manual transcription |
| `subtitle_transcription` | string | 32.1% | Medium | **MEDIUM** - Auto-generated subtitles |

### Temporal Data
| Field | Type | Description |
|-------|------|-------------|
| `upload_date` | string | Original upload date (YYYYMMDD format) |
| `timestamp` | integer | Unix timestamp of upload |
| `downloaded_at` | string | Scraping timestamp |
| `transcription_timestamp` | string | When transcription was processed |

### Hashtag Data
| Field | Type | Availability | Status |
|-------|------|--------------|--------|
| `hashtags` | array | 100% | **EMPTY** - All entries are empty arrays |

**Note**: The hashtag field exists but contains no data. Hashtags must be extracted from title/description text.

## Comment Data Structure

### Comment Extraction Status
- **Videos with Comments**: 783/1,774 (44.1%)
- **Total Comments Available**: 12,086 comments
- **Average Comments per Video**: ~15.4 comments (when available)

### Comment Object Schema
| Field | Type | Description | Keyword Scoring Value |
|-------|------|-------------|----------------------|
| `comment_id` | string | Unique comment identifier | N/A |
| `username` | string | Commenter's username | **LOW** - User context |
| `display_name` | string | Commenter's display name | **LOW** - User context |
| `comment_text` | string | Comment content | **HIGH** - Sentiment/keyword analysis |
| `like_count` | integer | Comment likes | **MEDIUM** - Comment quality indicator |
| `timestamp` | integer | Comment posting time | **LOW** - Temporal analysis |

### Comment Sentiment Analysis
**Current Status**: No sentiment scores present in data
**Available for Analysis**: 12,086 comment texts ready for sentiment processing

## Keyword Scoring Data Relationships

### Primary Text Sources (Priority Order)
1. **Title** (100% coverage) - Most important for keyword extraction
2. **Description** (99.3% coverage) - Contains hashtags and extended context
3. **Whisper Transcription** (63.2% coverage) - Spoken content analysis
4. **Comment Text** (44.1% of videos have comments) - User sentiment and reactions

### Engagement Metrics for Scoring Algorithm
```
Engagement Score = f(
    view_count,      # Reach multiplier
    like_count,      # Positive sentiment
    comment_count,   # Discussion factor
    repost_count,    # Shareability
    engagement_ratio = like_count / view_count  # Quality metric
)
```

### Sample Engagement Ratios
- Video 1: 14.71% (2M likes / 13.6M views)
- Video 2: 19.59% (1.9M likes / 9.7M views)  
- Video 3: 16.47% (1.4M likes / 8.5M views)
- Average Range: 9.55% - 19.59%

## Transcription Type Distribution
- **Whisper Only**: 63.2% (automated speech-to-text)
- **Multiple Types**: 26.2% (multiple transcription sources)
- **Custom Only**: 4.5% (manually created)
- **Subtitle Only**: 5.9% (auto-generated subtitles)
- **No Transcription**: 0.1% (minimal data loss)

## Data Quality Assessment

### High Quality Fields (>95% coverage)
- Video metadata (title, description, technical specs)
- Engagement metrics (views, likes, comments)
- Temporal data

### Medium Quality Fields (30-85% coverage)
- Transcription data (63-32% depending on type)
- Comment data (44% of videos)
- Technical metadata (82.6%)

### Missing/Empty Fields
- **Hashtags**: Present but empty (extraction needed from text)
- **Save/Share counts**: Only 36.6% coverage

## Recommended Keyword Scoring Algorithm Architecture

### Data Processing Pipeline
1. **Text Extraction**: Combine title + description + transcriptions
2. **Hashtag Extraction**: Parse hashtags from title/description text
3. **Sentiment Analysis**: Process comment texts for sentiment scores
4. **Engagement Weighting**: Apply engagement metrics as multipliers
5. **Keyword Scoring**: TF-IDF or similar with engagement weighting

### Scoring Formula Structure
```
Keyword_Score = TF-IDF_Score × Engagement_Multiplier × Sentiment_Boost

Where:
Engagement_Multiplier = normalize(view_count × engagement_ratio)
Sentiment_Boost = avg(comment_sentiment_scores) if comments exist
```

### Missing Data Handling
- **No Comments**: Use only video-level engagement metrics
- **No Transcription**: Rely on title/description only
- **Missing Hashtags**: Extract from description text using regex
- **Missing Engagement**: Use median values for normalization

## Conclusion

The master2.json database provides comprehensive data for keyword scoring with strong coverage of essential fields. The combination of video metadata, engagement metrics, and text content creates a robust foundation for viral content analysis. The main gaps are in sentiment analysis (needs to be computed) and hashtag extraction (needs text parsing).

**Next Steps for Keyword Scoring Implementation**:
1. Implement sentiment analysis on comment texts
2. Extract hashtags from title/description fields  
3. Develop engagement-weighted keyword scoring algorithm
4. Create content classification system based on extracted features