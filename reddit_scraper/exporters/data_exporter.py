"""
Data export functionality for Reddit scraper results.
"""
import json
import csv
import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from ..core.models import UserAnalysis, RedditPost, SubredditData, ExportConfig


class DataExporter:
    """Export Reddit scraping results in various formats."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def export_analysis(
        self, 
        analysis: UserAnalysis, 
        config: ExportConfig
    ) -> str:
        """Export user analysis in specified format."""
        
        # Prepare data for export
        export_data = self._prepare_export_data(analysis, config)
        
        # Export based on format
        if config.format.lower() == 'json':
            return self._export_json(export_data, config)
        elif config.format.lower() == 'csv':
            return self._export_csv(export_data, config)
        elif config.format.lower() == 'excel':
            return self._export_excel(export_data, config)
        else:
            raise ValueError(f"Unsupported export format: {config.format}")
    
    def _prepare_export_data(self, analysis: UserAnalysis, config: ExportConfig) -> Dict[str, Any]:
        """Prepare data structure for export."""
        
        export_data = {}
        
        # User profile information
        user_data = {
            'username': analysis.user.username,
            'user_id': analysis.user.id,
            'account_created': analysis.user.created_utc.isoformat() if analysis.user.created_utc else None,
            'comment_karma': analysis.user.comment_karma,
            'link_karma': analysis.user.link_karma,
            'total_karma': analysis.user.total_karma,
            'account_age_days': analysis.user.account_age_days,
            'is_verified': analysis.user.verified,
            'has_gold': analysis.user.is_gold
        }
        export_data['user_profile'] = user_data
        
        # Analysis metadata
        export_data['analysis_metadata'] = {
            'total_posts_analyzed': analysis.total_posts_analyzed,
            'analysis_timeframe': analysis.analysis_timeframe,
            'export_timestamp': datetime.utcnow().isoformat(),
            'avg_post_score': analysis.avg_post_score,
            'total_score': analysis.total_score,
            'success_rate': analysis.success_rate,
            'diversity_score': analysis.diversity_score
        }
        
        # Include posts if requested
        if config.include_posts and analysis.top_posts:
            posts_data = []
            for post in analysis.top_posts:
                if self._should_include_post(post, config):
                    post_data = {
                        'post_id': post.id,
                        'title': post.title,
                        'subreddit': post.subreddit,
                        'score': post.score,
                        'upvote_ratio': post.upvote_ratio,
                        'num_comments': post.num_comments,
                        'created_utc': post.created_utc.isoformat(),
                        'url': post.url,
                        'is_self': post.is_self,
                        'link_flair': post.link_flair_text,
                        'gilded': post.gilded,
                        'total_awards': post.total_awards_received,
                        'popularity_score': post.popularity_score,
                        'engagement_rate': post.engagement_rate,
                        'age_hours': post.age_hours
                    }
                    
                    # Include post content if it's a self post and not too long
                    if post.is_self and len(post.selftext) < 1000:
                        post_data['content_preview'] = post.selftext[:500] + '...' if len(post.selftext) > 500 else post.selftext
                    
                    posts_data.append(post_data)
            
            export_data['posts'] = posts_data
        
        # Include subreddit analysis if requested
        if config.include_subreddits and analysis.subreddit_activity:
            subreddits_data = {}
            for subreddit_name, subreddit_data in analysis.subreddit_activity.items():
                sr_data = {
                    'display_name': subreddit_data.display_name,
                    'title': subreddit_data.title,
                    'subscribers': subreddit_data.subscribers,
                    'over18': subreddit_data.over18,
                    'user_post_count': subreddit_data.user_post_count,
                    'user_total_score': subreddit_data.user_total_score,
                    'user_avg_score': subreddit_data.user_avg_score,
                    'user_activity_percentage': subreddit_data.user_activity_percentage
                }
                
                # Include top posts from this subreddit
                if len(subreddit_data.user_posts) > 0:
                    top_posts = sorted(subreddit_data.user_posts, key=lambda p: p.score, reverse=True)
                    sr_data['top_posts'] = []
                    for post in top_posts[:config.max_posts_per_subreddit]:
                        if self._should_include_post(post, config):
                            sr_data['top_posts'].append({
                                'title': post.title,
                                'score': post.score,
                                'comments': post.num_comments,
                                'url': post.url,
                                'created': post.created_utc.isoformat()
                            })
                
                subreddits_data[subreddit_name] = sr_data
            
            export_data['subreddit_activity'] = subreddits_data
        
        # Include activity patterns if requested
        if config.include_analysis:
            patterns_data = {
                'most_active_subreddits': analysis.most_active_subreddits[:10],
                'posting_frequency': analysis.posting_frequency,
                'posting_times': analysis.posting_times,
                'posting_days': analysis.posting_days,
                'best_performing_posts': [
                    {
                        'title': post.title,
                        'subreddit': post.subreddit,
                        'score': post.score,
                        'popularity_score': post.popularity_score,
                        'url': post.url
                    }
                    for post in analysis.best_performing_posts[:10]
                ]
            }
            export_data['activity_patterns'] = patterns_data
        
        return export_data
    
    def _should_include_post(self, post: RedditPost, config: ExportConfig) -> bool:
        """Check if post should be included based on config filters."""
        
        # Score threshold
        if post.score < config.min_score_threshold:
            return False
        
        # NSFW filter
        if config.exclude_nsfw and hasattr(post, 'over_18') and post.over_18:
            return False
        
        # Date range filter
        if config.date_range:
            start_date, end_date = config.date_range
            if not (start_date <= post.created_utc <= end_date):
                return False
        
        return True
    
    def _export_json(self, data: Dict[str, Any], config: ExportConfig) -> str:
        """Export data as JSON."""
        
        output_file = config.output_file or f"reddit_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            if config.pretty_print:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        
        self.logger.info(f"Data exported to JSON: {output_file}")
        return output_file
    
    def _export_csv(self, data: Dict[str, Any], config: ExportConfig) -> str:
        """Export data as CSV (flattened structure)."""
        
        output_file = config.output_file or f"reddit_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Flatten data for CSV
        rows = []
        
        # Add user profile row
        user_row = {'type': 'user_profile'}
        user_row.update(data.get('user_profile', {}))
        rows.append(user_row)
        
        # Add posts
        if 'posts' in data:
            for post in data['posts']:
                post_row = {'type': 'post'}
                post_row.update(post)
                rows.append(post_row)
        
        # Add subreddit data
        if 'subreddit_activity' in data:
            for sr_name, sr_data in data['subreddit_activity'].items():
                sr_row = {'type': 'subreddit', 'subreddit_name': sr_name}
                # Add basic subreddit info (exclude nested posts)
                for key, value in sr_data.items():
                    if key != 'top_posts':
                        sr_row[key] = value
                rows.append(sr_row)
        
        if rows:
            # Get all possible columns
            all_columns = set()
            for row in rows:
                all_columns.update(row.keys())
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_columns))
                writer.writeheader()
                writer.writerows(rows)
        
        self.logger.info(f"Data exported to CSV: {output_file}")
        return output_file
    
    def _export_excel(self, data: Dict[str, Any], config: ExportConfig) -> str:
        """Export data as Excel with multiple sheets."""
        
        output_file = config.output_file or f"reddit_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            
            # User profile sheet
            if 'user_profile' in data:
                user_df = pd.DataFrame([data['user_profile']])
                user_df.to_excel(writer, sheet_name='User_Profile', index=False)
            
            # Posts sheet
            if 'posts' in data and data['posts']:
                posts_df = pd.DataFrame(data['posts'])
                posts_df.to_excel(writer, sheet_name='Posts', index=False)
            
            # Subreddits sheet
            if 'subreddit_activity' in data:
                subreddit_rows = []
                for sr_name, sr_data in data['subreddit_activity'].items():
                    row = {'subreddit_name': sr_name}
                    for key, value in sr_data.items():
                        if key != 'top_posts':
                            row[key] = value
                    subreddit_rows.append(row)
                
                if subreddit_rows:
                    subreddit_df = pd.DataFrame(subreddit_rows)
                    subreddit_df.to_excel(writer, sheet_name='Subreddits', index=False)
            
            # Activity patterns sheet
            if 'activity_patterns' in data:
                patterns = data['activity_patterns']
                
                # Create summary data
                summary_data = []
                for key, value in patterns.items():
                    if isinstance(value, (list, dict)):
                        continue  # Skip complex structures
                    summary_data.append({'metric': key, 'value': value})
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Activity_Summary', index=False)
        
        self.logger.info(f"Data exported to Excel: {output_file}")
        return output_file
    
    def export_posts_only(
        self, 
        posts: List[RedditPost], 
        filename: Optional[str] = None,
        format: str = 'json'
    ) -> str:
        """Export only posts data in specified format."""
        
        if not filename:
            filename = f"reddit_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        posts_data = []
        for post in posts:
            post_data = {
                'id': post.id,
                'title': post.title,
                'author': post.author,
                'subreddit': post.subreddit,
                'score': post.score,
                'upvote_ratio': post.upvote_ratio,
                'num_comments': post.num_comments,
                'created_utc': post.created_utc.isoformat(),
                'url': post.url,
                'popularity_score': post.popularity_score,
                'engagement_rate': post.engagement_rate
            }
            posts_data.append(post_data)
        
        if format.lower() == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(posts_data, f, indent=2, ensure_ascii=False)
        elif format.lower() == 'csv':
            if posts_data:
                df = pd.DataFrame(posts_data)
                df.to_csv(filename, index=False, encoding='utf-8')
        
        self.logger.info(f"Posts exported to: {filename}")
        return filename
    
    def create_summary_report(self, analysis: UserAnalysis) -> str:
        """Create a human-readable summary report."""
        
        report_lines = []
        report_lines.append(f"Reddit User Analysis Report")
        report_lines.append(f"=" * 50)
        report_lines.append(f"")
        
        # User profile
        user = analysis.user
        report_lines.append(f"User: u/{user.username}")
        report_lines.append(f"Account Age: {user.account_age_days} days")
        report_lines.append(f"Total Karma: {user.total_karma:,} (Link: {user.link_karma:,}, Comment: {user.comment_karma:,})")
        report_lines.append(f"")
        
        # Analysis summary
        report_lines.append(f"Analysis Summary:")
        report_lines.append(f"- Posts Analyzed: {analysis.total_posts_analyzed}")
        report_lines.append(f"- Average Score: {analysis.avg_post_score:.1f}")
        report_lines.append(f"- Total Score: {analysis.total_score:,}")
        report_lines.append(f"- Success Rate: {analysis.success_rate:.1f}%")
        report_lines.append(f"- Active Subreddits: {analysis.diversity_score}")
        report_lines.append(f"")
        
        # Top subreddits
        if analysis.most_active_subreddits:
            report_lines.append(f"Most Active Subreddits:")
            for i, subreddit in enumerate(analysis.most_active_subreddits[:5], 1):
                post_count = analysis.posting_frequency.get(subreddit, 0)
                report_lines.append(f"{i}. r/{subreddit} ({post_count} posts)")
            report_lines.append(f"")
        
        # Best posts
        if analysis.best_performing_posts:
            report_lines.append(f"Top Performing Posts:")
            for i, post in enumerate(analysis.best_performing_posts[:3], 1):
                report_lines.append(f"{i}. {post.title[:60]}...")
                report_lines.append(f"   r/{post.subreddit} | {post.score} points | {post.num_comments} comments")
            report_lines.append(f"")
        
        report_text = "\n".join(report_lines)
        
        # Save report
        filename = f"reddit_summary_{analysis.user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        self.logger.info(f"Summary report created: {filename}")
        return filename