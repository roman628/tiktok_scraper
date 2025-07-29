#!/usr/bin/env python3
"""
Genre/Topic Performance Analysis for TikTok Videos
Analyzes which genres and topics get the most views and engagement
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
from collections import defaultdict, Counter
import re
import os
from wordcloud import WordCloud
from textblob import TextBlob

class GenrePerformanceAnalyzer:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = []
        self.df = None
        
        # Predefined genre categories based on common TikTok content
        self.genre_keywords = {
            'comedy': ['funny', 'humor', 'laugh', 'comedy', 'joke', 'hilarious', 'meme', 'lol'],
            'story_time': ['story', 'storytime', 'told', 'happened', 'experience', 'time', 'story time'],
            'educational': ['learn', 'education', 'teach', 'tutorial', 'how to', 'tips', 'facts', 'knowledge'],
            'lifestyle': ['life', 'daily', 'routine', 'lifestyle', 'living', 'habits', 'morning', 'evening'],
            'relationship': ['relationship', 'dating', 'love', 'boyfriend', 'girlfriend', 'marriage', 'couple'],
            'food': ['food', 'recipe', 'cooking', 'eat', 'restaurant', 'meal', 'kitchen', 'taste'],
            'fitness': ['workout', 'fitness', 'gym', 'exercise', 'health', 'training', 'muscle', 'weight'],
            'travel': ['travel', 'trip', 'vacation', 'journey', 'adventure', 'explore', 'destination'],
            'music': ['music', 'song', 'sing', 'dance', 'artist', 'album', 'concert', 'musician'],
            'beauty': ['makeup', 'beauty', 'skincare', 'hair', 'fashion', 'style', 'outfit', 'cosmetics'],
            'tech': ['technology', 'tech', 'app', 'phone', 'computer', 'software', 'digital', 'ai'],
            'gaming': ['game', 'gaming', 'play', 'gamer', 'video game', 'stream', 'console'],
            'motivational': ['motivation', 'inspire', 'success', 'goals', 'mindset', 'positive', 'growth'],
            'news': ['news', 'current', 'event', 'politics', 'world', 'breaking', 'update', 'today'],
            'diy': ['diy', 'craft', 'handmade', 'create', 'build', 'make', 'project', 'tutorial'],
            'pets': ['pet', 'dog', 'cat', 'animal', 'puppy', 'kitten', 'cute', 'funny animal'],
            'family': ['family', 'mom', 'dad', 'parent', 'child', 'kids', 'sibling', 'baby'],
            'sports': ['sport', 'football', 'basketball', 'soccer', 'baseball', 'tennis', 'athletic'],
            'business': ['business', 'entrepreneur', 'money', 'finance', 'career', 'job', 'work'],
            'art': ['art', 'artist', 'creative', 'drawing', 'painting', 'design', 'artistic']
        }
        
    def load_data(self):
        """Load and process TikTok data from JSON file"""
        print("Loading TikTok data for genre analysis...")
        with open(self.data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Convert to DataFrame
        processed_data = []
        for video in self.data:
            if all(k in video for k in ['title', 'view_count', 'like_count', 'comment_count']):
                try:
                    # Parse upload date if available
                    upload_date = None
                    if 'upload_date' in video and video['upload_date']:
                        upload_date = datetime.strptime(video['upload_date'], '%Y%m%d')
                    
                    # Calculate engagement metrics
                    views = video.get('view_count', 0) or 0
                    likes = video.get('like_count', 0) or 0
                    comments = video.get('comment_count', 0) or 0
                    
                    engagement_rate = (likes + comments) / max(views, 1) * 100
                    
                    # Performance score
                    performance_score = (
                        np.log1p(views) * 0.4 + 
                        np.log1p(likes) * 0.3 + 
                        np.log1p(comments) * 0.2 + 
                        engagement_rate * 0.1
                    )
                    
                    # Extract text content for analysis
                    title = video.get('title', '')
                    description = video.get('description', '')
                    transcription = video.get('whisper_transcription', '')
                    
                    # Combine all text
                    combined_text = f"{title} {description} {transcription}".lower()
                    
                    processed_data.append({
                        'video_id': video.get('video_id', ''),
                        'title': title,
                        'description': description,
                        'transcription': transcription[:200] + '...' if len(transcription) > 200 else transcription,
                        'combined_text': combined_text,
                        'upload_date': upload_date,
                        'uploader': video.get('uploader', 'Unknown'),
                        'view_count': views,
                        'like_count': likes,
                        'comment_count': comments,
                        'engagement_rate': engagement_rate,
                        'performance_score': performance_score,
                        'duration': video.get('duration', 0) or 0
                    })
                except Exception as e:
                    print(f"Error processing video: {e}")
                    continue
        
        self.df = pd.DataFrame(processed_data)
        print(f"Processed {len(self.df)} videos successfully")
        
    def classify_genres(self):
        """Classify videos into genres based on content"""
        print("\nClassifying videos by genre...")
        
        genre_classifications = []
        
        for _, video in self.df.iterrows():
            text = video['combined_text']
            video_genres = []
            genre_scores = {}
            
            # Score each genre based on keyword matches
            for genre, keywords in self.genre_keywords.items():
                score = 0
                for keyword in keywords:
                    # Count keyword occurrences (case insensitive)
                    occurrences = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text))
                    score += occurrences
                
                if score > 0:
                    genre_scores[genre] = score
                    video_genres.append(genre)
            
            # Determine primary genre (highest score)
            primary_genre = max(genre_scores.keys(), key=genre_scores.get) if genre_scores else 'uncategorized'
            
            genre_classifications.append({
                'video_id': video['video_id'],
                'primary_genre': primary_genre,
                'all_genres': video_genres,
                'genre_scores': genre_scores,
                'genre_count': len(video_genres)
            })
        
        # Add genre info to main DataFrame
        genre_df = pd.DataFrame(genre_classifications)
        self.df = self.df.merge(genre_df, on='video_id', how='left')
        
        print(f"Genre classification complete. Found {self.df['primary_genre'].nunique()} unique genres")
        
    def analyze_genre_performance(self):
        """Analyze performance metrics by genre"""
        print("\nAnalyzing genre performance...")
        
        # Group by primary genre
        genre_stats = self.df.groupby('primary_genre').agg({
            'view_count': ['mean', 'median', 'sum', 'count'],
            'like_count': ['mean', 'median', 'sum'],
            'comment_count': ['mean', 'median', 'sum'],
            'engagement_rate': ['mean', 'median'],
            'performance_score': ['mean', 'median'],
            'duration': 'mean'
        }).round(2)
        
        # Flatten column names
        genre_stats.columns = ['_'.join(col).strip() for col in genre_stats.columns]
        
        # Sort by average views
        genre_stats = genre_stats.sort_values('view_count_mean', ascending=False)
        
        # Calculate percentages
        total_videos = len(self.df)
        genre_stats['percentage_of_videos'] = (genre_stats['view_count_count'] / total_videos * 100).round(1)
        
        # Top performers in each genre
        top_performers_by_genre = {}
        for genre in self.df['primary_genre'].unique():
            genre_videos = self.df[self.df['primary_genre'] == genre]
            if len(genre_videos) > 0:
                top_video = genre_videos.loc[genre_videos['performance_score'].idxmax()]
                top_performers_by_genre[genre] = {
                    'title': top_video['title'][:60] + '...',
                    'views': top_video['view_count'],
                    'engagement_rate': top_video['engagement_rate'],
                    'performance_score': top_video['performance_score']
                }
        
        return genre_stats, top_performers_by_genre
    
    def analyze_trending_topics(self, min_frequency=5):
        """Extract and analyze trending topics from titles and descriptions"""
        print(f"\nAnalyzing trending topics (min frequency: {min_frequency})...")
        
        # Extract keywords from titles and descriptions
        all_text = ' '.join(self.df['title'].fillna('') + ' ' + self.df['description'].fillna(''))
        
        # Clean and tokenize
        words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text.lower())
        
        # Remove common stopwords
        stopwords = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'way', 'oil', 'sit', 'set', 'run', 'eat', 'far', 'sea', 'eye', 'ago', 'air', 'big', 'end', 'why', 'ask', 'men', 'change', 'went', 'light', 'kind', 'off', 'need', 'house', 'picture', 'try', 'again', 'animal', 'point', 'mother', 'world', 'near', 'build', 'self', 'earth', 'father', 'head', 'stand', 'own', 'page', 'should', 'country', 'found', 'answer', 'school', 'grow', 'study', 'still', 'learn', 'plant', 'cover', 'food', 'sun', 'four', 'between', 'state', 'keep', 'start', 'thought', 'city', 'tree', 'cross', 'farm', 'hard', 'begin', 'might', 'story', 'saw', 'left', 'don', 'few', 'while', 'along', 'close', 'something', 'seem', 'next', 'white', 'children', 'open', 'got', 'walk', 'example', 'begin', 'life', 'always', 'those', 'both', 'paper', 'together', 'took', 'important', 'until', 'without', 'second', 'late', 'look', 'government', 'into', 'year', 'public', 'also', 'think', 'little', 'help', 'long', 'here', 'would', 'make', 'come', 'this', 'time', 'work', 'first', 'well', 'water', 'been', 'call', 'have', 'after', 'back', 'other', 'many', 'than', 'then', 'them', 'these', 'some', 'what', 'were', 'take', 'when', 'much', 'more', 'very', 'will', 'said', 'each', 'tell', 'does', 'most', 'know', 'just', 'name', 'good', 'sentence', 'man', 'think', 'say', 'great', 'where', 'through', 'much', 'before', 'line', 'right', 'too', 'means', 'old', 'any', 'same', 'tell', 'boy', 'follow', 'came', 'want', 'show', 'also', 'around', 'form', 'three', 'small', 'put', 'end', 'does', 'another', 'well', 'large', 'must', 'big', 'even', 'such', 'because', 'turn', 'here', 'why', 'asked', 'went', 'men', 'read', 'need', 'land', 'different', 'home', 'move', 'try', 'kind', 'hand', 'picture', 'again', 'change', 'off', 'play', 'spell', 'air', 'away', 'animal', 'house', 'point', 'page', 'letter', 'mother', 'answer', 'found', 'study', 'still', 'learn', 'should', 'america', 'world'
        }
        
        # Filter words
        filtered_words = [word for word in words if word not in stopwords and len(word) > 3]
        
        # Count frequency
        word_freq = Counter(filtered_words)
        trending_topics = {word: count for word, count in word_freq.items() if count >= min_frequency}
        
        # Analyze performance by topic
        topic_performance = {}
        for topic, frequency in list(trending_topics.items())[:20]:  # Top 20 topics
            # Find videos containing this topic
            topic_videos = self.df[self.df['combined_text'].str.contains(topic, case=False, na=False)]
            
            if len(topic_videos) > 0:
                topic_performance[topic] = {
                    'frequency': frequency,
                    'video_count': len(topic_videos),
                    'avg_views': topic_videos['view_count'].mean(),
                    'avg_engagement_rate': topic_videos['engagement_rate'].mean(),
                    'avg_performance_score': topic_videos['performance_score'].mean()
                }
        
        # Sort by performance score
        sorted_topics = sorted(topic_performance.items(), 
                             key=lambda x: x[1]['avg_performance_score'], reverse=True)
        
        return dict(sorted_topics[:15]), word_freq  # Top 15 performing topics
    
    def analyze_hashtag_performance(self):
        """Analyze hashtag performance if available"""
        print("\nAnalyzing hashtag performance...")
        
        hashtag_performance = {}
        
        # Extract hashtags from titles and descriptions
        for _, video in self.df.iterrows():
            text = video['title'] + ' ' + str(video['description'])
            hashtags = re.findall(r'#(\w+)', text)
            
            for hashtag in hashtags:
                hashtag = hashtag.lower()
                if hashtag not in hashtag_performance:
                    hashtag_performance[hashtag] = {
                        'count': 0,
                        'total_views': 0,
                        'total_likes': 0,
                        'total_comments': 0,
                        'total_performance': 0
                    }
                
                hashtag_performance[hashtag]['count'] += 1
                hashtag_performance[hashtag]['total_views'] += video['view_count']
                hashtag_performance[hashtag]['total_likes'] += video['like_count']
                hashtag_performance[hashtag]['total_comments'] += video['comment_count']
                hashtag_performance[hashtag]['total_performance'] += video['performance_score']
        
        # Calculate averages and filter by minimum frequency
        min_frequency = 3
        filtered_hashtags = {}
        
        for hashtag, stats in hashtag_performance.items():
            if stats['count'] >= min_frequency:
                filtered_hashtags[hashtag] = {
                    'frequency': stats['count'],
                    'avg_views': stats['total_views'] / stats['count'],
                    'avg_likes': stats['total_likes'] / stats['count'],
                    'avg_comments': stats['total_comments'] / stats['count'],
                    'avg_performance_score': stats['total_performance'] / stats['count']
                }
        
        # Sort by performance
        sorted_hashtags = sorted(filtered_hashtags.items(), 
                               key=lambda x: x[1]['avg_performance_score'], reverse=True)
        
        return dict(sorted_hashtags[:10])  # Top 10 hashtags
    
    def create_visualizations(self, genre_stats, topic_performance, hashtag_performance, output_dir):
        """Create comprehensive visualizations"""
        print("\nCreating genre performance visualizations...")
        
        plt.style.use('seaborn-v0_8')
        fig = plt.figure(figsize=(20, 16))
        
        # 1. Genre Performance (Views)
        ax1 = plt.subplot(2, 3, 1)
        top_genres = genre_stats.head(10)
        bars1 = ax1.bar(range(len(top_genres)), top_genres['view_count_mean'], 
                       color='skyblue', alpha=0.7)
        ax1.set_title('Average Views by Genre', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Average Views')
        ax1.set_xlabel('Genre')
        ax1.set_xticks(range(len(top_genres)))
        ax1.set_xticklabels(top_genres.index, rotation=45, ha='right')
        
        # Add value labels
        for i, bar in enumerate(bars1):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height/1000:.0f}K', ha='center', va='bottom')
        
        # 2. Genre Distribution
        ax2 = plt.subplot(2, 3, 2)
        genre_counts = self.df['primary_genre'].value_counts().head(8)
        colors = plt.cm.Set3(np.linspace(0, 1, len(genre_counts)))
        ax2.pie(genre_counts.values, labels=genre_counts.index, autopct='%1.1f%%', 
               colors=colors, startangle=90)
        ax2.set_title('Video Distribution by Genre', fontsize=14, fontweight='bold')
        
        # 3. Engagement Rate by Genre
        ax3 = plt.subplot(2, 3, 3)
        engagement_data = genre_stats['engagement_rate_mean'].head(10)
        bars3 = ax3.bar(range(len(engagement_data)), engagement_data, 
                       color='lightcoral', alpha=0.7)
        ax3.set_title('Average Engagement Rate by Genre', fontsize=14, fontweight='bold')
        ax3.set_ylabel('Engagement Rate (%)')
        ax3.set_xlabel('Genre')
        ax3.set_xticks(range(len(engagement_data)))
        ax3.set_xticklabels(engagement_data.index, rotation=45, ha='right')
        
        for i, bar in enumerate(bars3):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom')
        
        # 4. Top Topics Performance
        ax4 = plt.subplot(2, 3, 4)
        if topic_performance:
            topic_names = list(topic_performance.keys())[:10]
            topic_scores = [topic_performance[topic]['avg_performance_score'] for topic in topic_names]
            bars4 = ax4.barh(range(len(topic_names)), topic_scores, color='lightgreen', alpha=0.7)
            ax4.set_title('Top Topics by Performance', fontsize=14, fontweight='bold')
            ax4.set_xlabel('Average Performance Score')
            ax4.set_yticks(range(len(topic_names)))
            ax4.set_yticklabels(topic_names)
            
            for i, bar in enumerate(bars4):
                width = bar.get_width()
                ax4.text(width, bar.get_y() + bar.get_height()/2.,
                        f'{width:.1f}', ha='left', va='center')
        
        # 5. Hashtag Performance
        ax5 = plt.subplot(2, 3, 5)
        if hashtag_performance:
            hashtag_names = list(hashtag_performance.keys())[:8]
            hashtag_scores = [hashtag_performance[ht]['avg_performance_score'] for ht in hashtag_names]
            bars5 = ax5.bar(range(len(hashtag_names)), hashtag_scores, color='orange', alpha=0.7)
            ax5.set_title('Top Hashtags by Performance', fontsize=14, fontweight='bold')
            ax5.set_ylabel('Average Performance Score')
            ax5.set_xlabel('Hashtag')
            ax5.set_xticks(range(len(hashtag_names)))
            ax5.set_xticklabels([f'#{ht}' for ht in hashtag_names], rotation=45, ha='right')
            
            for i, bar in enumerate(bars5):
                height = bar.get_height()
                ax5.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}', ha='center', va='bottom')
        
        # 6. Performance Score Distribution
        ax6 = plt.subplot(2, 3, 6)
        ax6.hist(self.df['performance_score'], bins=30, color='purple', alpha=0.7, edgecolor='black')
        ax6.set_title('Performance Score Distribution', fontsize=14, fontweight='bold')
        ax6.set_xlabel('Performance Score')
        ax6.set_ylabel('Number of Videos')
        ax6.axvline(self.df['performance_score'].mean(), color='red', linestyle='--', 
                   label=f'Mean: {self.df["performance_score"].mean():.1f}')
        ax6.legend()
        
        plt.tight_layout()
        
        # Save plot
        chart_path = os.path.join(output_dir, 'genre_performance_analysis.png')
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"Chart saved to: {chart_path}")
        
        plt.show()
        return chart_path
    
    def create_word_cloud(self, word_freq, output_dir):
        """Create word cloud of trending topics"""
        print("\nCreating word cloud...")
        
        try:
            # Create word cloud
            wordcloud = WordCloud(width=800, height=400, 
                                background_color='white',
                                max_words=100,
                                colormap='viridis').generate_from_frequencies(word_freq)
            
            plt.figure(figsize=(12, 6))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.title('Trending Topics Word Cloud', fontsize=16, fontweight='bold', pad=20)
            
            # Save word cloud
            wordcloud_path = os.path.join(output_dir, 'trending_topics_wordcloud.png')
            plt.savefig(wordcloud_path, dpi=300, bbox_inches='tight')
            print(f"Word cloud saved to: {wordcloud_path}")
            
            plt.show()
            return wordcloud_path
        except Exception as e:
            print(f"Error creating word cloud: {e}")
            return None
    
    def generate_report(self, genre_stats, topic_performance, hashtag_performance, output_dir):
        """Generate comprehensive genre analysis report"""
        print("\nGenerating genre performance report...")
        
        # Top performers
        top_genre = genre_stats.index[0] if len(genre_stats) > 0 else 'Unknown'
        top_views = genre_stats.iloc[0]['view_count_mean'] if len(genre_stats) > 0 else 0
        
        report = {
            'analysis_type': 'Genre/Topic Performance Analysis',
            'generated_at': datetime.now().isoformat(),
            'total_videos_analyzed': len(self.df),
            'unique_genres_found': self.df['primary_genre'].nunique(),
            'genre_performance': {
                'top_performing_genre': top_genre,
                'top_genre_avg_views': top_views,
                'genre_breakdown': genre_stats.head(10).to_dict('index')
            },
            'trending_topics': {
                'top_topics': dict(list(topic_performance.items())[:10]),
                'explanation': 'Topics ranked by average performance score of videos containing them'
            },
            'hashtag_analysis': {
                'top_hashtags': hashtag_performance,
                'explanation': 'Hashtags ranked by average performance score (minimum 3 occurrences)'
            },
            'key_insights': [
                f"'{top_genre}' is the top-performing genre with {top_views:.0f} average views",
                f"Found {len(topic_performance)} trending topics across all videos",
                f"Analyzed {len(hashtag_performance)} popular hashtags",
                f"Most common genre: {self.df['primary_genre'].mode().iloc[0] if len(self.df) > 0 else 'Unknown'}"
            ],
            'recommendations': [
                f"Focus on {top_genre} content for maximum reach",
                f"Incorporate trending topics: {', '.join(list(topic_performance.keys())[:3])}",
                f"Use high-performing hashtags: #{', #'.join(list(hashtag_performance.keys())[:3])}"
            ]
        }
        
        # Save report
        report_path = os.path.join(output_dir, 'genre_performance_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Report saved to: {report_path}")
        return report_path
    
    def run_analysis(self, output_dir='../outputs'):
        """Run complete genre performance analysis"""
        print("🎭 Starting Genre/Topic Performance Analysis...")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load data
        self.load_data()
        
        if len(self.df) == 0:
            print("❌ No valid data found!")
            return None
        
        # Classify genres
        self.classify_genres()
        
        # Analyze genre performance
        genre_stats, top_performers = self.analyze_genre_performance()
        
        # Analyze trending topics
        topic_performance, word_freq = self.analyze_trending_topics()
        
        # Analyze hashtag performance
        hashtag_performance = self.analyze_hashtag_performance()
        
        # Create visualizations
        chart_path = self.create_visualizations(
            genre_stats, topic_performance, hashtag_performance, output_dir
        )
        
        # Create word cloud
        wordcloud_path = self.create_word_cloud(word_freq, output_dir)
        
        # Generate report
        report_path = self.generate_report(
            genre_stats, topic_performance, hashtag_performance, output_dir
        )
        
        print("\n✅ Genre Analysis Complete!")
        print(f"📊 Chart: {chart_path}")
        if wordcloud_path:
            print(f"☁️ Word Cloud: {wordcloud_path}")
        print(f"📋 Report: {report_path}")
        
        return {
            'top_genre': genre_stats.index[0] if len(genre_stats) > 0 else 'Unknown',
            'top_topics': list(topic_performance.keys())[:5],
            'top_hashtags': list(hashtag_performance.keys())[:5],
            'chart_path': chart_path,
            'wordcloud_path': wordcloud_path,
            'report_path': report_path
        }

def main():
    # Configuration
    data_file = '../master2.json'
    output_dir = '../outputs'
    
    if not os.path.exists(data_file):
        print(f"❌ Data file not found: {data_file}")
        print("Please ensure master2.json is in the parent directory")
        return
    
    # Run analysis
    analyzer = GenrePerformanceAnalyzer(data_file)
    results = analyzer.run_analysis(output_dir)
    
    if results:
        print("\n🎭 Key Findings:")
        print(f"🏆 Top Genre: {results['top_genre']}")
        print(f"🔥 Trending Topics: {', '.join(results['top_topics'])}")
        print(f"📱 Top Hashtags: #{', #'.join(results['top_hashtags'])}")

if __name__ == "__main__":
    main()