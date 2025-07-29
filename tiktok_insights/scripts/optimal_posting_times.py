#!/usr/bin/env python3
"""
Optimal Posting Times Analysis for TikTok Videos
Analyzes the best times and days to post based on video performance metrics
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import os

class PostingTimeAnalyzer:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = []
        self.df = None
        
    def load_data(self):
        """Load and process TikTok data from JSON file"""
        print("Loading TikTok data...")
        with open(self.data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Convert to DataFrame
        processed_data = []
        for video in self.data:
            if all(k in video for k in ['upload_date', 'view_count', 'like_count', 'comment_count']):
                try:
                    # Parse upload date
                    upload_date = datetime.strptime(video['upload_date'], '%Y%m%d')
                    
                    # Calculate engagement rate
                    views = video.get('view_count', 0) or 0
                    likes = video.get('like_count', 0) or 0
                    comments = video.get('comment_count', 0) or 0
                    
                    engagement_rate = (likes + comments) / max(views, 1) * 100
                    
                    # Performance score (weighted combination)
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
                        'day_of_week': upload_date.strftime('%A'),
                        'day_number': upload_date.weekday(),  # 0=Monday, 6=Sunday
                        'hour': upload_date.hour,
                        'view_count': views,
                        'like_count': likes,
                        'comment_count': comments,
                        'engagement_rate': engagement_rate,
                        'performance_score': performance_score,
                        'uploader': video.get('uploader', 'Unknown')
                    })
                except Exception as e:
                    print(f"Error processing video: {e}")
                    continue
        
        self.df = pd.DataFrame(processed_data)
        print(f"Processed {len(self.df)} videos successfully")
        
    def analyze_optimal_days(self, top_percentile=20):
        """Analyze optimal days of the week for posting"""
        print(f"\nAnalyzing optimal posting days (top {top_percentile}% performers)...")
        
        # Define performance threshold
        threshold = np.percentile(self.df['performance_score'], 100 - top_percentile)
        top_performers = self.df[self.df['performance_score'] >= threshold]
        
        # Group by day of week
        day_stats = self.df.groupby('day_of_week').agg({
            'performance_score': ['mean', 'median', 'count'],
            'view_count': 'mean',
            'engagement_rate': 'mean'
        }).round(2)
        
        # Top performer distribution by day
        top_day_distribution = top_performers['day_of_week'].value_counts()
        top_day_percentage = (top_day_distribution / len(top_performers) * 100).round(1)
        
        # Order by weekday
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        results = {
            'overall_stats': day_stats,
            'top_performer_distribution': top_day_distribution.reindex(day_order, fill_value=0),
            'top_performer_percentage': top_day_percentage.reindex(day_order, fill_value=0),
            'recommendations': self._generate_day_recommendations(day_stats, top_day_percentage, day_order)
        }
        
        return results
    
    def analyze_optimal_hours(self, top_percentile=20):
        """Analyze optimal hours for posting"""
        print(f"\nAnalyzing optimal posting hours (top {top_percentile}% performers)...")
        
        # Define performance threshold
        threshold = np.percentile(self.df['performance_score'], 100 - top_percentile)
        top_performers = self.df[self.df['performance_score'] >= threshold]
        
        # Group by hour
        hour_stats = self.df.groupby('hour').agg({
            'performance_score': ['mean', 'median', 'count'],
            'view_count': 'mean',
            'engagement_rate': 'mean'
        }).round(2)
        
        # Top performer distribution by hour
        top_hour_distribution = top_performers['hour'].value_counts().sort_index()
        top_hour_percentage = (top_hour_distribution / len(top_performers) * 100).round(1)
        
        results = {
            'hour_stats': hour_stats,
            'top_performer_distribution': top_hour_distribution,
            'top_performer_percentage': top_hour_percentage,
            'recommendations': self._generate_hour_recommendations(hour_stats, top_hour_percentage)
        }
        
        return results
    
    def _generate_day_recommendations(self, day_stats, top_percentages, day_order):
        """Generate day-based recommendations"""
        # Get mean performance scores
        mean_scores = day_stats['performance_score']['mean']
        
        # Sort days by performance
        best_days = mean_scores.reindex(day_order).sort_values(ascending=False)
        
        recommendations = {
            'best_days': best_days.head(3).index.tolist(),
            'worst_days': best_days.tail(2).index.tolist(),
            'top_3_explanation': f"Top 3 days: {', '.join(best_days.head(3).index)} show highest average performance scores",
            'avoid_explanation': f"Avoid: {', '.join(best_days.tail(2).index)} show lowest performance"
        }
        
        return recommendations
    
    def _generate_hour_recommendations(self, hour_stats, top_percentages):
        """Generate hour-based recommendations"""
        # Get mean performance scores
        mean_scores = hour_stats['performance_score']['mean']
        
        # Sort hours by performance
        best_hours = mean_scores.sort_values(ascending=False)
        
        # Group into time periods
        morning = best_hours[best_hours.index.isin(range(6, 12))]
        afternoon = best_hours[best_hours.index.isin(range(12, 18))]
        evening = best_hours[best_hours.index.isin(range(18, 24))]
        night = best_hours[best_hours.index.isin(list(range(0, 6)))]
        
        recommendations = {
            'best_hours': best_hours.head(5).index.tolist(),
            'best_morning': morning.head(2).index.tolist() if len(morning) > 0 else [],
            'best_afternoon': afternoon.head(2).index.tolist() if len(afternoon) > 0 else [],
            'best_evening': evening.head(2).index.tolist() if len(evening) > 0 else [],
            'peak_time_explanation': f"Peak hours: {best_hours.head(3).index.tolist()} show highest performance"
        }
        
        return recommendations
    
    def create_visualizations(self, day_results, hour_results, output_dir):
        """Create visualization charts"""
        print("\nCreating visualizations...")
        
        # Set style
        plt.style.use('seaborn-v0_8')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Performance by Day of Week
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_means = day_results['overall_stats']['performance_score']['mean'].reindex(day_order)
        
        bars1 = ax1.bar(day_order, day_means, color='skyblue', alpha=0.7)
        ax1.set_title('Average Performance Score by Day of Week', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Performance Score')
        ax1.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom')
        
        # 2. Top Performer Distribution by Day
        top_day_dist = day_results['top_performer_percentage'].reindex(day_order)
        bars2 = ax2.bar(day_order, top_day_dist, color='lightcoral', alpha=0.7)
        ax2.set_title('Top 20% Performers Distribution by Day', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Percentage of Top Performers (%)')
        ax2.tick_params(axis='x', rotation=45)
        
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom')
        
        # 3. Performance by Hour
        hour_means = hour_results['hour_stats']['performance_score']['mean']
        ax3.plot(hour_means.index, hour_means.values, marker='o', linewidth=2, markersize=6, color='green')
        ax3.set_title('Average Performance Score by Hour of Day', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Hour of Day')
        ax3.set_ylabel('Performance Score')
        ax3.grid(True, alpha=0.3)
        ax3.set_xticks(range(0, 24, 2))
        
        # 4. Heatmap: Day vs Hour
        pivot_data = self.df.groupby(['day_number', 'hour'])['performance_score'].mean().unstack(fill_value=0)
        day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        sns.heatmap(pivot_data, annot=False, cmap='YlOrRd', ax=ax4, 
                   yticklabels=day_labels, cbar_kws={'label': 'Performance Score'})
        ax4.set_title('Performance Heatmap: Day vs Hour', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Hour of Day')
        ax4.set_ylabel('Day of Week')
        
        plt.tight_layout()
        
        # Save plot
        chart_path = os.path.join(output_dir, 'optimal_posting_times.png')
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"Chart saved to: {chart_path}")
        
        plt.show()
        
        return chart_path
    
    def generate_report(self, day_results, hour_results, output_dir):
        """Generate comprehensive report"""
        print("\nGenerating report...")
        
        report = {
            'analysis_type': 'Optimal Posting Times Analysis',
            'generated_at': datetime.now().isoformat(),
            'total_videos_analyzed': len(self.df),
            'date_range': {
                'start': self.df['upload_date'].min().strftime('%Y-%m-%d'),
                'end': self.df['upload_date'].max().strftime('%Y-%m-%d')
            },
            'day_analysis': {
                'best_days': day_results['recommendations']['best_days'],
                'worst_days': day_results['recommendations']['worst_days'],
                'explanation': day_results['recommendations']['top_3_explanation'],
                'detailed_stats': day_results['overall_stats'].to_dict()
            },
            'hour_analysis': {
                'best_hours': hour_results['recommendations']['best_hours'],
                'best_morning_hours': hour_results['recommendations']['best_morning'],
                'best_afternoon_hours': hour_results['recommendations']['best_afternoon'],
                'best_evening_hours': hour_results['recommendations']['best_evening'],
                'explanation': hour_results['recommendations']['peak_time_explanation']
            },
            'key_insights': [
                f"Best posting days: {', '.join(day_results['recommendations']['best_days'])}",
                f"Optimal hours: {', '.join(map(str, hour_results['recommendations']['best_hours'][:3]))}",
                f"Avoid posting on: {', '.join(day_results['recommendations']['worst_days'])}",
                f"Peak performance time: {hour_results['recommendations']['best_hours'][0]}:00"
            ]
        }
        
        # Save report
        report_path = os.path.join(output_dir, 'posting_times_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Report saved to: {report_path}")
        return report_path
    
    def run_analysis(self, output_dir='../outputs'):
        """Run complete posting time analysis"""
        print("🎯 Starting Optimal Posting Times Analysis...")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load data
        self.load_data()
        
        if len(self.df) == 0:
            print("❌ No valid data found!")
            return None
        
        # Analyze optimal days and hours
        day_results = self.analyze_optimal_days()
        hour_results = self.analyze_optimal_hours()
        
        # Create visualizations
        chart_path = self.create_visualizations(day_results, hour_results, output_dir)
        
        # Generate report
        report_path = self.generate_report(day_results, hour_results, output_dir)
        
        print("\n✅ Analysis Complete!")
        print(f"📊 Chart: {chart_path}")
        print(f"📋 Report: {report_path}")
        
        return {
            'day_results': day_results,
            'hour_results': hour_results,
            'chart_path': chart_path,
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
    analyzer = PostingTimeAnalyzer(data_file)
    results = analyzer.run_analysis(output_dir)
    
    if results:
        print("\n🎯 Key Recommendations:")
        print(f"📅 Best Days: {', '.join(results['day_results']['recommendations']['best_days'])}")
        print(f"⏰ Best Hours: {', '.join(map(str, results['hour_results']['recommendations']['best_hours'][:3]))}")

if __name__ == "__main__":
    main()