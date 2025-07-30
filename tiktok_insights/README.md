# TikTok Insights Analysis Suite

A comprehensive analysis toolkit for TikTok video performance data, providing insights on optimal posting times, frequency strategies, and content performance by genre/topic.

## 🎯 What This Tool Analyzes

### 1. Optimal Posting Times (`optimal_posting_times.py`)
- **Best days of the week** to post based on video performance metrics
- **Optimal hours** for maximum engagement
- **Day vs Hour heatmaps** showing performance patterns
- **Performance-based recommendations** for scheduling content

### 2. Posting Frequency Analysis (`posting_frequency.py`)
- **Optimal posting frequency** per week/month
- **Impact of posting consistency** on performance
- **Multiple posts per day** analysis
- **Creator-specific frequency patterns**

### 3. Genre/Topic Performance (`genre_performance.py`)
- **Top-performing content genres** (comedy, education, lifestyle, etc.)
- **Trending topics** and keyword analysis
- **Hashtag performance** metrics
- **Content strategy recommendations**

## 📁 Project Structure

```
tiktok_insights/
├── scripts/
│   ├── optimal_posting_times.py    # Timing analysis
│   ├── posting_frequency.py        # Frequency analysis
│   ├── genre_performance.py        # Content analysis
│   └── dashboard.py                # Main runner script
├── outputs/                        # Generated reports (JSON)
├── charts/                         # Generated visualizations (PNG)
├── data/                          # Input data directory
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd tiktok_insights
pip install -r requirements.txt
```

### 2. Prepare Your Data

Ensure your `master2.json` file is in the parent directory with the following structure:
```json
[
  {
    "title": "Video title",
    "description": "Video description", 
    "upload_date": "20240101",
    "view_count": 1000000,
    "like_count": 50000,
    "comment_count": 5000,
    "uploader": "creator_name",
    "whisper_transcription": "Video transcript..."
  }
]
```

### 3. Run Analysis

#### Option A: Complete Dashboard (Recommended)
```bash
cd tiktok_insights/scripts
python dashboard.py
```

#### Option B: Individual Analysis Scripts
```bash
cd scripts

# Analyze optimal posting times
python optimal_posting_times.py

# Analyze posting frequency
python posting_frequency.py

# Analyze genre performance
python genre_performance.py
```

## 📊 Output Files

### Reports (JSON format in `outputs/`)
- `posting_times_report.json` - Optimal timing insights
- `posting_frequency_report.json` - Frequency strategy recommendations  
- `genre_performance_report.json` - Content strategy insights
- `executive_summary.json` - Complete analysis summary

### Visualizations (PNG format in `charts/`)
- `optimal_posting_times.png` - Timing analysis charts
- `posting_frequency_analysis.png` - Frequency analysis charts
- `genre_performance_analysis.png` - Content performance charts
- `trending_topics_wordcloud.png` - Word cloud of popular topics
- `tiktok_insights_dashboard.png` - Summary dashboard

## 🎯 Key Features

### Posting Time Analysis
- **Performance scoring** using views, likes, comments, and engagement rate
- **Statistical analysis** of top 20% performers
- **Day-of-week recommendations** with performance rankings
- **Hour-by-hour optimization** for maximum reach
- **Heatmap visualizations** showing optimal posting windows

### Frequency Analysis  
- **Creator-level frequency analysis** with performance correlation
- **Optimal posting frequency** determination
- **Consistency impact** measurement
- **Daily posting patterns** analysis
- **Performance vs frequency** correlation studies

### Genre/Content Analysis
- **Automated genre classification** using keyword matching
- **20+ content categories** (comedy, education, lifestyle, etc.)
- **Trending topics extraction** from titles and transcriptions
- **Hashtag performance** analysis
- **Content strategy recommendations** based on top performers

## 📈 Performance Metrics

The analysis uses a composite **Performance Score** calculated as:
```
Performance Score = (
    log(views + 1) × 0.4 +
    log(likes + 1) × 0.3 + 
    log(comments + 1) × 0.2 +
    engagement_rate × 0.1
)
```

Where `engagement_rate = (likes + comments) / views × 100`

## 🛠️ Customization

### Modify Genre Categories
Edit the `genre_keywords` dictionary in `genre_performance.py`:
```python
self.genre_keywords = {
    'your_genre': ['keyword1', 'keyword2', 'keyword3'],
    # Add more genres as needed
}
```

### Adjust Performance Thresholds
Modify the `top_percentile` parameter in analysis functions:
```python
# Analyze top 10% instead of top 20%
day_results = self.analyze_optimal_days(top_percentile=10)
```

### Change Output Directories
Update paths in the main functions:
```python
output_dir = '/your/custom/output/path'
```

## 📋 Requirements

### Python Dependencies
- pandas >= 1.5.0
- numpy >= 1.21.0  
- matplotlib >= 3.5.0
- seaborn >= 0.11.0
- wordcloud >= 1.9.0
- textblob >= 0.17.0

### Data Requirements
- **Minimum 100 videos** for reliable analysis
- **Upload dates** in YYYYMMDD format
- **Complete engagement metrics** (views, likes, comments)
- **Text content** (titles, descriptions, transcriptions)

## 🎨 Visualization Examples

### Dashboard Overview
- Combined insights from all three analyses
- Key recommendations in visual format
- Executive summary charts

### Posting Times Charts
- Bar charts showing performance by day/hour
- Heatmaps of day vs hour performance
- Performance score distributions

### Frequency Analysis
- Performance vs posting frequency correlations
- Consistency impact visualizations
- Creator frequency distributions

### Genre Performance
- Top genres by average views
- Genre distribution pie charts
- Trending topics word clouds
- Hashtag performance rankings

## 🚀 Advanced Usage

### Batch Processing
```python
from dashboard import TikTokInsightsDashboard

# Process multiple datasets
datasets = ['master1.json', 'master2.json', 'master3.json']
for dataset in datasets:
    dashboard = TikTokInsightsDashboard(dataset)
    dashboard.run_complete_analysis()
```

### Custom Analysis
```python
from optimal_posting_times import PostingTimeAnalyzer

analyzer = PostingTimeAnalyzer('your_data.json')
analyzer.load_data()

# Custom analysis with different parameters
day_results = analyzer.analyze_optimal_days(top_percentile=15)
hour_results = analyzer.analyze_optimal_hours(top_percentile=25)
```

## 🔧 Troubleshooting

### Common Issues

**"No valid data found"**
- Check JSON file format and required fields
- Ensure upload_date is in YYYYMMDD format
- Verify numeric fields are not null/zero

**"WordCloud import error"**
- Install wordcloud: `pip install wordcloud`
- On some systems: `pip install wordcloud==1.9.2`

**Memory issues with large datasets**
- Process data in chunks
- Use sampling for initial analysis
- Consider using Dask for very large files

**Missing visualizations**
- Check matplotlib backend: `matplotlib.use('Agg')`
- Ensure output directories exist
- Verify write permissions

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify your data format matches the requirements
3. Ensure all dependencies are installed correctly

## 📄 License

This analysis toolkit is provided as-is for educational and analytical purposes.

---

**🎬 Start optimizing your TikTok strategy with data-driven insights!**