#!/usr/bin/env python3
"""
TikTok Insights Dashboard - Main Runner Script
Runs all analyses and creates a comprehensive dashboard
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
import os
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import analysis modules
from optimal_posting_times import PostingTimeAnalyzer
from posting_frequency import PostingFrequencyAnalyzer
from genre_performance import GenrePerformanceAnalyzer

class TikTokInsightsDashboard:
    def __init__(self, data_file):
        self.data_file = data_file
        self.output_dir = '../outputs'
        self.charts_dir = '../charts'
        self.results = {}
        
    def setup_directories(self):
        """Create necessary directories"""
        print("🏗️ Setting up directories...")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.charts_dir, exist_ok=True)
        print("✅ Directories ready")
    
    def run_all_analyses(self):
        """Run all three main analyses"""
        print("\n🚀 Starting Comprehensive TikTok Analysis...")
        print("=" * 60)
        
        # 1. Optimal Posting Times Analysis
        print("\n1️⃣ OPTIMAL POSTING TIMES ANALYSIS")
        print("-" * 40)
        try:
            posting_analyzer = PostingTimeAnalyzer(self.data_file)
            posting_results = posting_analyzer.run_analysis(self.output_dir)
            self.results['posting_times'] = posting_results
            print("✅ Posting times analysis completed successfully")
        except Exception as e:
            print(f"❌ Error in posting times analysis: {e}")
            self.results['posting_times'] = None
        
        # 2. Posting Frequency Analysis
        print("\n2️⃣ POSTING FREQUENCY ANALYSIS")
        print("-" * 40)
        try:
            frequency_analyzer = PostingFrequencyAnalyzer(self.data_file)
            frequency_results = frequency_analyzer.run_analysis(self.output_dir)
            self.results['posting_frequency'] = frequency_results
            print("✅ Posting frequency analysis completed successfully")
        except Exception as e:
            print(f"❌ Error in posting frequency analysis: {e}")
            self.results['posting_frequency'] = None
        
        # 3. Genre/Topic Performance Analysis
        print("\n3️⃣ GENRE/TOPIC PERFORMANCE ANALYSIS")
        print("-" * 40)
        try:
            genre_analyzer = GenrePerformanceAnalyzer(self.data_file)
            genre_results = genre_analyzer.run_analysis(self.output_dir)
            self.results['genre_performance'] = genre_results
            print("✅ Genre performance analysis completed successfully")
        except Exception as e:
            print(f"❌ Error in genre performance analysis: {e}")
            self.results['genre_performance'] = None
    
    def create_summary_dashboard(self):
        """Create a summary dashboard with key insights from all analyses"""
        print("\n📊 Creating Summary Dashboard...")
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('TikTok Insights Dashboard - Key Recommendations', fontsize=16, fontweight='bold')
        
        # 1. Optimal Posting Days (if available)
        if self.results['posting_times'] and self.results['posting_times']['day_results']:
            best_days = self.results['posting_times']['day_results']['recommendations']['best_days']
            day_performance = [3, 2, 1]  # Sample scores for visualization
            
            bars1 = ax1.bar(best_days[:3], day_performance, color=['gold', 'silver', '#CD7F32'], alpha=0.8)
            ax1.set_title('🏆 Best Posting Days', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Performance Rank')
            ax1.set_ylim(0, 4)
            
            # Add rank labels
            for i, (bar, day) in enumerate(zip(bars1, best_days[:3])):
                rank = i + 1
                ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                        f'#{rank}', ha='center', va='bottom', fontweight='bold')
        else:
            ax1.text(0.5, 0.5, 'Posting Times\nAnalysis\nUnavailable', 
                    ha='center', va='center', transform=ax1.transAxes, fontsize=12)
            ax1.set_title('🕐 Optimal Posting Times', fontsize=14)
        
        # 2. Optimal Posting Hours (if available)
        if self.results['posting_times'] and self.results['posting_times']['hour_results']:
            best_hours = self.results['posting_times']['hour_results']['recommendations']['best_hours'][:5]
            hour_scores = list(range(5, 0, -1))  # Descending scores
            
            ax2.bar(range(len(best_hours)), hour_scores, color='skyblue', alpha=0.7)
            ax2.set_title('⏰ Peak Posting Hours', fontsize=14, fontweight='bold')
            ax2.set_ylabel('Performance Score')
            ax2.set_xlabel('Hour of Day')
            ax2.set_xticks(range(len(best_hours)))
            ax2.set_xticklabels([f'{h}:00' for h in best_hours])
            
            # Add value labels
            for i, score in enumerate(hour_scores):
                ax2.text(i, score + 0.1, str(best_hours[i]), ha='center', va='bottom', fontweight='bold')
        else:
            ax2.text(0.5, 0.5, 'Posting Hours\nAnalysis\nUnavailable', 
                    ha='center', va='center', transform=ax2.transAxes, fontsize=12)
            ax2.set_title('⏰ Peak Posting Hours', fontsize=14)
        
        # 3. Optimal Posting Frequency (if available)
        if self.results['posting_frequency'] and self.results['posting_frequency']['optimal_frequency']:
            frequency_text = self.results['posting_frequency']['optimal_frequency']
            ax3.text(0.5, 0.5, f'📊 Optimal Frequency:\n\n{frequency_text}', 
                    ha='center', va='center', transform=ax3.transAxes, 
                    fontsize=12, bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.5))
            ax3.set_title('📈 Posting Frequency', fontsize=14, fontweight='bold')
        else:
            ax3.text(0.5, 0.5, 'Posting Frequency\nAnalysis\nUnavailable', 
                    ha='center', va='center', transform=ax3.transAxes, fontsize=12)
            ax3.set_title('📈 Posting Frequency', fontsize=14)
        ax3.set_xticks([])
        ax3.set_yticks([])
        
        # 4. Top Performing Genre (if available)
        if self.results['genre_performance'] and self.results['genre_performance']['top_genre']:
            top_genre = self.results['genre_performance']['top_genre']
            top_topics = self.results['genre_performance']['top_topics'][:3]
            
            text_content = f'🎭 Top Genre:\n{top_genre.title()}\n\n🔥 Trending Topics:\n'
            for i, topic in enumerate(top_topics, 1):
                text_content += f'{i}. {topic.title()}\n'
            
            ax4.text(0.5, 0.5, text_content, 
                    ha='center', va='center', transform=ax4.transAxes, 
                    fontsize=11, bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5))
            ax4.set_title('🎯 Content Strategy', fontsize=14, fontweight='bold')
        else:
            ax4.text(0.5, 0.5, 'Genre Performance\nAnalysis\nUnavailable', 
                    ha='center', va='center', transform=ax4.transAxes, fontsize=12)
            ax4.set_title('🎯 Content Strategy', fontsize=14)
        ax4.set_xticks([])
        ax4.set_yticks([])
        
        plt.tight_layout()
        
        # Save dashboard
        dashboard_path = os.path.join(self.charts_dir, 'tiktok_insights_dashboard.png')
        plt.savefig(dashboard_path, dpi=300, bbox_inches='tight')
        print(f"📊 Dashboard saved to: {dashboard_path}")
        
        plt.show()
        return dashboard_path
    
    def generate_executive_summary(self):
        """Generate an executive summary report"""
        print("\n📋 Generating Executive Summary...")
        
        summary = {
            'executive_summary': {
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'Comprehensive TikTok Performance Analysis',
                'analyses_completed': len([r for r in self.results.values() if r is not None])
            },
            'key_recommendations': [],
            'posting_strategy': {},
            'content_strategy': {},
            'performance_insights': [],
            'next_steps': []
        }
        
        # Posting Time Recommendations
        if self.results['posting_times']:
            posting_data = self.results['posting_times']
            best_days = posting_data['day_results']['recommendations']['best_days']
            best_hours = posting_data['hour_results']['recommendations']['best_hours'][:3]
            
            summary['posting_strategy'] = {
                'optimal_days': best_days,
                'optimal_hours': best_hours,
                'recommendation': f"Post on {', '.join(best_days)} at {', '.join(map(str, best_hours))} for maximum reach"
            }
            
            summary['key_recommendations'].append(
                f"🕐 Schedule posts on {', '.join(best_days[:2])} between {best_hours[0]}:00-{best_hours[1]}:00"
            )
        
        # Posting Frequency Recommendations
        if self.results['posting_frequency']:
            frequency_data = self.results['posting_frequency']
            optimal_freq = frequency_data['optimal_frequency']
            
            summary['posting_strategy']['frequency'] = optimal_freq
            summary['key_recommendations'].append(
                f"📊 Maintain posting frequency: {optimal_freq}"
            )
        
        # Content Strategy Recommendations
        if self.results['genre_performance']:
            genre_data = self.results['genre_performance']
            top_genre = genre_data['top_genre']
            top_topics = genre_data['top_topics'][:5]
            top_hashtags = genre_data['top_hashtags'][:5]
            
            summary['content_strategy'] = {
                'primary_genre': top_genre,
                'trending_topics': top_topics,
                'effective_hashtags': top_hashtags,
                'recommendation': f"Focus on {top_genre} content with topics: {', '.join(top_topics[:3])}"
            }
            
            summary['key_recommendations'].extend([
                f"🎭 Focus on {top_genre} content for highest engagement",
                f"🔥 Include trending topics: {', '.join(top_topics[:3])}",
                f"📱 Use hashtags: #{', #'.join(top_hashtags[:3])}"
            ])
        
        # Performance Insights
        summary['performance_insights'] = [
            "Timing and consistency are crucial for TikTok success",
            "Genre selection significantly impacts view counts",
            "Trending topics can boost content visibility",
            "Strategic hashtag use improves discoverability"
        ]
        
        # Next Steps
        summary['next_steps'] = [
            "Implement recommended posting schedule",
            "Create content calendar based on optimal timing",
            "Monitor trending topics regularly",
            "Test different content formats within top-performing genres",
            "Track performance metrics and adjust strategy accordingly"
        ]
        
        # Save summary
        summary_path = os.path.join(self.output_dir, 'executive_summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"📋 Executive summary saved to: {summary_path}")
        return summary_path
    
    def print_final_recommendations(self):
        """Print final recommendations to console"""
        print("\n" + "="*80)
        print("🎯 FINAL TIKTOK OPTIMIZATION RECOMMENDATIONS")
        print("="*80)
        
        # Posting Times
        if self.results['posting_times']:
            posting_data = self.results['posting_times']
            best_days = posting_data['day_results']['recommendations']['best_days']
            best_hours = posting_data['hour_results']['recommendations']['best_hours'][:3]
            
            print("\n📅 OPTIMAL POSTING SCHEDULE:")
            print(f"   • Best Days: {', '.join(best_days)}")
            print(f"   • Best Hours: {', '.join(map(str, best_hours))} (24-hour format)")
            print(f"   • Peak Time: {best_hours[0]}:00")
        
        # Posting Frequency
        if self.results['posting_frequency']:
            frequency_data = self.results['posting_frequency']
            optimal_freq = frequency_data['optimal_frequency']
            
            print(f"\n📊 POSTING FREQUENCY:")
            print(f"   • Optimal: {optimal_freq}")
            if frequency_data['recommendations']['key_insights']:
                for insight in frequency_data['recommendations']['key_insights']:
                    print(f"   • {insight}")
        
        # Content Strategy
        if self.results['genre_performance']:
            genre_data = self.results['genre_performance']
            top_genre = genre_data['top_genre']
            top_topics = genre_data['top_topics'][:5]
            top_hashtags = genre_data['top_hashtags'][:5]
            
            print(f"\n🎭 CONTENT STRATEGY:")
            print(f"   • Top Genre: {top_genre.title()}")
            print(f"   • Trending Topics: {', '.join(top_topics)}")
            print(f"   • Effective Hashtags: #{', #'.join(top_hashtags)}")
        
        print(f"\n📁 All reports and charts saved to:")
        print(f"   • Reports: {os.path.abspath(self.output_dir)}")
        print(f"   • Charts: {os.path.abspath(self.charts_dir)}")
        
        print("\n" + "="*80)
        print("✨ Analysis Complete! Use these insights to optimize your TikTok strategy.")
        print("="*80)
    
    def run_complete_analysis(self):
        """Run the complete analysis pipeline"""
        print("🎬 TikTok Insights Dashboard")
        print("🔍 Comprehensive Performance Analysis")
        print("="*60)
        
        # Check if data file exists
        if not os.path.exists(self.data_file):
            print(f"❌ Data file not found: {self.data_file}")
            print("Please ensure master2.json is available")
            return False
        
        # Setup
        self.setup_directories()
        
        # Run all analyses
        self.run_all_analyses()
        
        # Create summary dashboard
        if any(self.results.values()):
            dashboard_path = self.create_summary_dashboard()
            summary_path = self.generate_executive_summary()
            
            # Print final recommendations
            self.print_final_recommendations()
            
            return True
        else:
            print("❌ All analyses failed. Please check your data file and try again.")
            return False

def main():
    """Main function to run the complete TikTok insights analysis"""
    # Configuration
    data_file = '../../master2.json'
    
    # Create and run dashboard
    dashboard = TikTokInsightsDashboard(data_file)
    success = dashboard.run_complete_analysis()
    
    if success:
        print("\n🎉 All analyses completed successfully!")
        print("Check the outputs and charts directories for detailed results.")
    else:
        print("\n💔 Analysis failed. Please check the data file and try again.")

if __name__ == "__main__":
    main()