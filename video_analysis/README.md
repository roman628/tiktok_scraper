# Video Analysis System

This system transcribes TikTok videos and analyzes them for virality potential using a comprehensive scoring algorithm.

## Features

- **Video Transcription**: Uses Whisper AI to transcribe video content
- **Virality Scoring**: Analyzes content for viral potential based on:
  - Hook strength (opening impact)
  - Keyword matches (viral keywords from existing data)
  - Readability (simpler content performs better)
  - Sentiment analysis
  - Emotional triggers
  - Content categorization
- **Batch Processing**: Analyze entire directories of videos
- **Detailed Reports**: Generate both JSON and Markdown reports

## Installation

The system uses packages already installed in your virtual environment:
- `faster-whisper` for transcription
- `textblob` for sentiment analysis
- `ffmpeg` for audio extraction (must be installed separately)

## Usage

### Test Single Video

To test the system with a single video:

```bash
cd /Users/ethan/tiktok_scraper
source venv/bin/activate
python video_analysis/test_single_video.py
```

### Analyze All Ubuntu Videos

To analyze all videos in the ubuntu-results directory:

```bash
cd /Users/ethan/tiktok_scraper
source venv/bin/activate
python video_analysis/analyze_ubuntu_videos.py
```

### Custom Analysis

To analyze a custom directory:

```bash
python video_analysis/video_transcriber.py /path/to/videos --output /path/to/results
```

## Output Structure

The system creates the following outputs in the specified directory:

```
output_dir/
├── analysis_summary.json       # Summary of all videos with scores
├── analysis_report.md          # Markdown report with top videos
└── <video_name>_analysis.json  # Individual analysis for each video
```

## Virality Score Components

The virality score (0-1) is calculated based on:

1. **Hook Strength (25%)**: How compelling the opening is
2. **Keywords (30%)**: Presence of high-performing keywords
3. **Readability (15%)**: How easy the content is to understand
4. **Sentiment (10%)**: Emotional polarity of content
5. **Emotional Triggers (20%)**: Presence of emotional keywords

## Results Interpretation

- **Score > 0.7**: High viral potential
- **Score 0.5-0.7**: Good viral potential
- **Score 0.3-0.5**: Average potential
- **Score < 0.3**: Low viral potential

## Troubleshooting

1. **FFmpeg not found**: Install ffmpeg using `brew install ffmpeg`
2. **Out of memory**: Use a smaller Whisper model (tiny or base)
3. **Slow processing**: The base model balances speed and accuracy. Use 'tiny' for faster processing

## Example Output

```json
{
  "filename": "example_video.mp4",
  "virality_score": 0.752,
  "hook_strength": 0.8,
  "sentiment": 0.65,
  "category": "story",
  "emotional_triggers": ["surprise", "joy"],
  "top_keywords": [
    ["crazy", 0.85],
    ["unbelievable", 0.72],
    ["story", 0.68]
  ]
}
```