#!/usr/bin/env python3
"""
Posting Frequency Analysis for TikTok Videos
Analyzes optimal posting frequency based on performance metrics and temporal patterns
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict, Counter
import os

class PostingFrequencyAnalyzer:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = []
        self.df = None
        
    def load_data(self):
        """Load and process TikTok data from JSON file"""
        print("Loading TikTok data for frequency analysis...")
        with open(self.data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Convert to DataFrame
        processed_data = []
        for video in self.data:
            if all(k in video for k in ['upload_date', 'view_count', 'like_count', 'comment_count', 'uploader']):
                try:
                    # Parse upload date
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
                    
                    processed_data.append({
                        'video_id': video.get('video_id', ''),
                        'title': video.get('title', '')[:50] + '...',
                        'upload_date': upload_date,
                        'uploader': video.get('uploader', 'Unknown'),
                        'view_count': views,
                        'like_count': likes,
                        'comment_count': comments,
                        'engagement_rate': engagement_rate,
                        'performance_score': performance_score
                    })
                except Exception as e:
                    print(f"Error processing video: {e}")
                    continue
        
        self.df = pd.DataFrame(processed_data)
        self.df = self.df.sort_values('upload_date')
        print(f"Processed {len(self.df)} videos successfully")
        
    def analyze_creator_frequencies(self, min_videos=5):
        """Analyze posting frequencies of different creators"""
        print(f"\nAnalyzing creator posting frequencies (min {min_videos} videos)...")
        
        creator_stats = []
        
        for creator in self.df['uploader'].unique():
            creator_videos = self.df[self.df['uploader'] == creator].copy()
            
            if len(creator_videos) < min_videos:
                continue
                
            # Calculate posting frequency metrics
            creator_videos = creator_videos.sort_values('upload_date')
            date_range = (creator_videos['upload_date'].max() - creator_videos['upload_date'].min()).days
            
            if date_range <= 0:
                continue
                
            videos_per_day = len(creator_videos) / max(date_range, 1)
            videos_per_week = videos_per_day * 7
            videos_per_month = videos_per_day * 30
            
            # Calculate gaps between posts
            creator_videos['date_diff'] = creator_videos['upload_date'].diff().dt.days
            avg_gap_days = creator_videos['date_diff'].mean()
            median_gap_days = creator_videos['date_diff'].median()
            
            # Performance metrics
            avg_performance = creator_videos['performance_score'].mean()
            avg_views = creator_videos['view_count'].mean()
            avg_engagement = creator_videos['engagement_rate'].mean()
            
            creator_stats.append({
                'creator': creator,
                'total_videos': len(creator_videos),
                'date_range_days': date_range,
                'videos_per_day': videos_per_day,
                'videos_per_week': videos_per_week,
                'videos_per_month': videos_per_month,
                'avg_gap_days': avg_gap_days,
                'median_gap_days': median_gap_days,
                'avg_performance_score': avg_performance,
                'avg_views': avg_views,
                'avg_engagement_rate': avg_engagement
            })
        
        creator_df = pd.DataFrame(creator_stats)
        creator_df = creator_df.sort_values('avg_performance_score', ascending=False)
        
        return creator_df
    
    def analyze_optimal_frequency(self, creator_df):
        """Determine optimal posting frequency based on performance"""
        print("\nAnalyzing optimal posting frequency...")
        
        # Create frequency bins
        frequency_bins = [
            (0, 0.5, 'Very Low (< 0.5/week)'),
            (0.5, 1.5, 'Low (0.5-1.5/week)'),
            (1.5, 3.5, 'Moderate (1.5-3.5/week)'),
            (3.5, 7, 'High (3.5-7/week)'),
            (7, float('inf'), 'Very High (>7/week)')
        ]
        
        frequency_analysis = []
        
        for min_freq, max_freq, label in frequency_bins:
            if max_freq == float('inf'):
                subset = creator_df[creator_df['videos_per_week'] >= min_freq]
            else:
                subset = creator_df[
                    (creator_df['videos_per_week'] >= min_freq) & 
                    (creator_df['videos_per_week'] < max_freq)
                ]
            
            if len(subset) == 0:
                continue
                
            frequency_analysis.append({
                'frequency_range': label,
                'creator_count': len(subset),
                'avg_performance_score': subset['avg_performance_score'].mean(),
                'median_performance_score': subset['avg_performance_score'].median(),
                'avg_views': subset['avg_views'].mean(),
                'avg_engagement_rate': subset['avg_engagement_rate'].mean(),
                'top_performers_count': len(subset[subset['avg_performance_score'] >= subset['avg_performance_score'].quantile(0.8)])
            })
        
        frequency_df = pd.DataFrame(frequency_analysis)
        
        # Find optimal frequency
        if len(frequency_df) > 0:
            optimal_freq = frequency_df.loc[frequency_df['avg_performance_score'].idxmax(), 'frequency_range']
        else:
            optimal_freq = "Unable to determine"
        
        return frequency_df, optimal_freq
    
    def analyze_daily_posting_patterns(self):
        """Analyze patterns of posting multiple times per day"""
        print("\nAnalyzing daily posting patterns...")
        
        # Group by creator and date
        daily_posts = self.df.groupby(['uploader', self.df['upload_date'].dt.date]).agg({
            'video_id': 'count',
            'performance_score': 'mean',
            'view_count': 'mean',
            'engagement_rate': 'mean'
        }).rename(columns={'video_id': 'posts_per_day'})
        
        # Analyze performance by posts per day
        posts_per_day_analysis = daily_posts.groupby('posts_per_day').agg({
            'performance_score': ['mean', 'median', 'count'],
            'view_count': 'mean',
            'engagement_rate': 'mean'
        }).round(2)
        
        # Multiple posts vs single posts comparison
        single_post_days = daily_posts[daily_posts['posts_per_day'] == 1]
        multiple_post_days = daily_posts[daily_posts['posts_per_day'] > 1]
        
        comparison = {
            'single_post_performance': single_post_days['performance_score'].mean(),
            'multiple_post_performance': multiple_post_days['performance_score'].mean(),
            'single_post_engagement': single_post_days['engagement_rate'].mean(),
            'multiple_post_engagement': multiple_post_days['engagement_rate'].mean(),
            'single_post_days_count': len(single_post_days),
            'multiple_post_days_count': len(multiple_post_days)
        }
        
        return posts_per_day_analysis, comparison
    
    def analyze_consistency_impact(self, creator_df):
        """Analyze impact of posting consistency on performance"""
        print("\nAnalyzing posting consistency impact...")
        
        # Calculate consistency score (inverse of gap variance)
        creator_df['gap_variance'] = creator_df.apply(
            lambda row: self._calculate_gap_variance(row['creator']), axis=1
        )
        
        # Consistency score (lower variance = higher consistency)
        creator_df['consistency_score'] = 1 / (1 + creator_df['gap_variance'])
        
        # Analyze correlation between consistency and performance
        consistency_correlation = creator_df['consistency_score'].corr(creator_df['avg_performance_score'])
        
        # Categorize creators by consistency
        consistency_bins = [
            (0, 0.3, 'Low Consistency'),
            (0.3, 0.6, 'Medium Consistency'),
            (0.6, 1.0, 'High Consistency')
        ]
        
        consistency_analysis = []
        for min_cons, max_cons, label in consistency_bins:
            subset = creator_df[
                (creator_df['consistency_score'] >= min_cons) & 
                (creator_df['consistency_score'] <= max_cons)
            ]
            
            if len(subset) == 0:
                continue
                
            consistency_analysis.append({
                'consistency_level': label,
                'creator_count': len(subset),
                'avg_performance_score': subset['avg_performance_score'].mean(),
                'avg_views': subset['avg_views'].mean(),
                'avg_posting_frequency': subset['videos_per_week'].mean()
            })
        
        consistency_df = pd.DataFrame(consistency_analysis)
        
        return consistency_df, consistency_correlation
    
    def _calculate_gap_variance(self, creator):
        """Calculate variance in posting gaps for a creator"""
        creator_videos = self.df[self.df['uploader'] == creator].sort_values('upload_date')
        if len(creator_videos) < 2:
            return 0
        
        gaps = creator_videos['upload_date'].diff().dt.days.dropna()
        return gaps.var() if len(gaps) > 0 else 0
    
    def create_visualizations(self, creator_df, frequency_df, posts_per_day_analysis, consistency_df, output_dir):
        """Create comprehensive visualizations"""
        print("\nCreating frequency analysis visualizations...")
        
        plt.style.use('seaborn-v0_8')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Performance vs Posting Frequency
        if len(frequency_df) > 0:
            ax1.bar(range(len(frequency_df)), frequency_df['avg_performance_score'], 
                   color='lightblue', alpha=0.7)
            ax1.set_title('Performance vs Posting Frequency', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Average Performance Score')
            ax1.set_xlabel('Posting Frequency')
            ax1.set_xticks(range(len(frequency_df)))
            ax1.set_xticklabels(frequency_df['frequency_range'], rotation=45, ha='right')
            
            # Add value labels
            for i, v in enumerate(frequency_df['avg_performance_score']):
                ax1.text(i, v, f'{v:.1f}', ha='center', va='bottom')
        
        # 2. Posts Per Day Analysis
        if len(posts_per_day_analysis) > 0:
            posts_data = posts_per_day_analysis['performance_score']['mean']
            ax2.plot(posts_data.index, posts_data.values, marker='o', linewidth=2, markersize=6, color='red')
            ax2.set_title('Performance vs Posts Per Day', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Posts Per Day')
            ax2.set_ylabel('Average Performance Score')
            ax2.grid(True, alpha=0.3)
        
        # 3. Posting Frequency Distribution
        if len(creator_df) > 0:
            ax3.hist(creator_df['videos_per_week'], bins=20, color='lightgreen', alpha=0.7, edgecolor='black')
            ax3.set_title('Distribution of Posting Frequencies', fontsize=14, fontweight='bold')
            ax3.set_xlabel('Videos Per Week')
            ax3.set_ylabel('Number of Creators')
            ax3.axvline(creator_df['videos_per_week'].mean(), color='red', linestyle='--', 
                       label=f'Mean: {creator_df["videos_per_week"].mean():.1f}')
            ax3.legend()
        
        # 4. Consistency vs Performance
        if len(consistency_df) > 0:
            bars = ax4.bar(consistency_df['consistency_level'], consistency_df['avg_performance_score'], 
                          color='orange', alpha=0.7)
            ax4.set_title('Consistency vs Performance', fontsize=14, fontweight='bold')
            ax4.set_ylabel('Average Performance Score')
            ax4.set_xlabel('Posting Consistency Level')
            
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save plot
        chart_path = os.path.join(output_dir, 'posting_frequency_analysis.png')
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"Chart saved to: {chart_path}")
        
        plt.show()
        return chart_path
    
    def generate_recommendations(self, frequency_df, optimal_freq, posts_per_day_analysis, consistency_df):
        """Generate frequency recommendations"""
        recommendations = {
            'optimal_weekly_frequency': optimal_freq,
            'key_insights': [],
            'daily_posting_advice': '',
            'consistency_advice': ''
        }
        
        # Weekly frequency insights
        if len(frequency_df) > 0:
            best_performer = frequency_df.loc[frequency_df['avg_performance_score'].idxmax()]
            recommendations['key_insights'].append(
                f"Optimal frequency: {best_performer['frequency_range']} shows best performance"
            )
        
        # Daily posting insights
        if len(posts_per_day_analysis) > 0:
            single_day_perf = posts_per_day_analysis.loc[1, 'performance_score']['mean'] if 1 in posts_per_day_analysis.index else 0
            multi_day_perfs = posts_per_day_analysis[posts_per_day_analysis.index > 1]['performance_score']['mean']
            
            if len(multi_day_perfs) > 0 and multi_day_perfs.mean() > single_day_perf:
                recommendations['daily_posting_advice'] = "Multiple posts per day can improve performance"
            else:
                recommendations['daily_posting_advice'] = "Single daily posts appear optimal"
        
        # Consistency insights
        if len(consistency_df) > 0:
            high_consistency = consistency_df[consistency_df['consistency_level'] == 'High Consistency']
            if len(high_consistency) > 0:
                recommendations['consistency_advice'] = "High posting consistency correlates with better performance"
                recommendations['key_insights'].append("Maintain consistent posting schedule for best results")
        
        return recommendations
    
    def generate_report(self, creator_df, frequency_df, optimal_freq, posts_per_day_analysis, 
                       consistency_df, recommendations, output_dir):
        """Generate comprehensive frequency analysis report"""
        print("\nGenerating frequency analysis report...")
        
        report = {
            'analysis_type': 'Posting Frequency Analysis',
            'generated_at': datetime.now().isoformat(),
            'total_videos_analyzed': len(self.df),
            'unique_creators_analyzed': len(creator_df),
            'date_range': {
                'start': self.df['upload_date'].min().strftime('%Y-%m-%d'),
                'end': self.df['upload_date'].max().strftime('%Y-%m-%d')
            },
            'optimal_frequency': {
                'recommended_frequency': optimal_freq,
                'explanation': f"Analysis of {len(creator_df)} creators shows this frequency yields best performance"
            },
            'frequency_breakdown': frequency_df.to_dict('records') if len(frequency_df) > 0 else [],
            'daily_posting_analysis': {
                'posts_per_day_stats': posts_per_day_analysis.to_dict() if len(posts_per_day_analysis) > 0 else {},
                'recommendation': recommendations['daily_posting_advice']
            },
            'consistency_analysis': {
                'consistency_breakdown': consistency_df.to_dict('records') if len(consistency_df) > 0 else [],
                'advice': recommendations['consistency_advice']
            },
            'top_performers': creator_df.head(10)[['creator', 'videos_per_week', 'avg_performance_score']].to_dict('records'),
            'key_recommendations': recommendations['key_insights']
        }
        
        # Save report
        report_path = os.path.join(output_dir, 'posting_frequency_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Report saved to: {report_path}")
        return report_path
    
    def run_analysis(self, output_dir='../outputs'):
        """Run complete posting frequency analysis"""
        print("📊 Starting Posting Frequency Analysis...")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load data
        self.load_data()
        
        if len(self.df) == 0:
            print("❌ No valid data found!")
            return None
        
        # Analyze creator frequencies
        creator_df = self.analyze_creator_frequencies()
        
        if len(creator_df) == 0:
            print("❌ Not enough creator data for analysis!")
            return None
        
        # Analyze optimal frequency
        frequency_df, optimal_freq = self.analyze_optimal_frequency(creator_df)
        
        # Analyze daily posting patterns
        posts_per_day_analysis, daily_comparison = self.analyze_daily_posting_patterns()
        
        # Analyze consistency impact
        consistency_df, consistency_correlation = self.analyze_consistency_impact(creator_df)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(
            frequency_df, optimal_freq, posts_per_day_analysis, consistency_df
        )
        
        # Create visualizations
        chart_path = self.create_visualizations(
            creator_df, frequency_df, posts_per_day_analysis, consistency_df, output_dir
        )
        
        # Generate report
        report_path = self.generate_report(
            creator_df, frequency_df, optimal_freq, posts_per_day_analysis, 
            consistency_df, recommendations, output_dir
        )
        
        print("\n✅ Frequency Analysis Complete!")
        print(f"📊 Chart: {chart_path}")
        print(f"📋 Report: {report_path}")
        
        return {
            'optimal_frequency': optimal_freq,
            'recommendations': recommendations,
            'chart_path': chart_path,
            'report_path': report_path
        }

def main():
    # Configuration
    data_file = '../../master2.json'
    output_dir = '../outputs'
    
    if not os.path.exists(data_file):
        print(f"❌ Data file not found: {data_file}")
        print("Please ensure master2.json is in the parent directory")
        return
    
    # Run analysis
    analyzer = PostingFrequencyAnalyzer(data_file)
    results = analyzer.run_analysis(output_dir)
    
    if results:
        print("\n📊 Key Recommendations:")
        print(f"🎯 Optimal Frequency: {results['optimal_frequency']}")
        for insight in results['recommendations']['key_insights']:
            print(f"💡 {insight}")

if __name__ == "__main__":
    main()