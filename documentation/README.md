# TikTok Scraper Documentation

This directory contains comprehensive documentation for the TikTok Scraper project and its keyword scoring system.

## 📚 Documentation Index

### Core Documentation
- **[USAGE_GUIDE.md](./USAGE_GUIDE.md)** - Complete usage guide for the TikTok scraper
- **[theplan.md](./theplan.md)** - Original project planning document

### Keyword Scoring System
- **[keyword_scoring_algorithm_specification.md](./keyword_scoring_algorithm_specification.md)** - Technical algorithm specification
- **[keyword_scoring_implementation_plan.md](./keyword_scoring_implementation_plan.md)** - Implementation roadmap and plan
- **[data_structure_analysis.md](./data_structure_analysis.md)** - Analysis of master2.json data structure

### Research Documents
- **[AI_RESEARCH_PROJECT.md](./AI_RESEARCH_PROJECT.md)** - AI research project overview
- **[AI_ML_Research_Document.md](./AI_ML_Research_Document.md)** - Machine learning research documentation

## 🎯 Quick Reference

### Keyword Scoring System
The keyword scoring system analyzes TikTok video data to identify high-performing keywords based on:
- **Engagement metrics** (views, likes, comments, reposts)
- **Sentiment analysis** from comment data
- **Content categorization** and viral potential
- **Comprehensive stopword filtering** to remove noise and personal names

### Main Components
1. **Data Analysis** - Understanding master2.json structure (1,774 videos)
2. **Keyword Extraction** - Multi-method NLP approach (RAKE, TextRank, YAKE, TF-IDF)
3. **Scoring Algorithm** - Engagement-weighted performance correlation
4. **Clean Filtering** - 629+ stopwords including names and platform noise

### Output
- **keyword_score_map.txt** - Complete keyword-to-score mapping (13,041+ keywords)
- **keyword_scoring_system/** - Full implementation with Python modules

## 🔧 Implementation

See the keyword scoring system in the `/keyword_scoring_system/` directory for:
- Production-ready Python implementation
- CLI interface and batch processing
- Comprehensive testing suite
- Integration with existing codebase

## 📊 Results

The system successfully processes all TikTok video data and identifies top-performing keywords like:
- **couplegoals** (Score: 10.17) - Relationship content
- **takeover** (Score: 9.19) - Business/success themes
- **enterprise** (Score: 8.12) - Professional content
- **innovative** (Score: 7.37) - Creative/tech content

All results are clean of personal names and focused on meaningful content themes for viral prediction and content optimization.