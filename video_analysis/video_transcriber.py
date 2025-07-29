#!/usr/bin/env python3
"""
Video Transcription and Virality Scoring System

This script processes TikTok videos to:
1. Extract audio and transcribe using Whisper
2. Apply virality scoring based on the keyword scoring system
3. Generate analysis reports for each video
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess
import tempfile
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class VideoAnalysis:
    """Represents analysis results for a single video."""
    video_path: str
    filename: str
    transcription: str
    virality_score: float
    keyword_scores: Dict[str, float]
    sentiment_score: float
    readability_score: float
    hook_strength: float
    emotional_triggers: List[str]
    content_category: str
    processing_time: float
    error: Optional[str] = None


class VideoTranscriber:
    """Handles video to audio conversion and transcription."""
    
    def __init__(self, model_size: str = "base"):
        """
        Initialize the transcriber.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are installed."""
        try:
            # Try faster-whisper first (it's faster and uses less memory)
            from faster_whisper import WhisperModel
            self.use_faster_whisper = True
            self.WhisperModel = WhisperModel
            logger.info("Using faster-whisper for transcription")
        except ImportError:
            try:
                import whisper
                self.whisper = whisper
                self.use_faster_whisper = False
                logger.info("Using openai-whisper for transcription")
            except ImportError:
                logger.error("No whisper implementation found. Run: pip install faster-whisper or pip install openai-whisper")
                raise
        
        # Check for ffmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("ffmpeg not installed. Please install ffmpeg.")
            raise
    
    def extract_audio(self, video_path: str, audio_path: str) -> bool:
        """
        Extract audio from video file.
        
        Args:
            video_path: Path to video file
            audio_path: Path to save audio file
            
        Returns:
            Success status
        """
        try:
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le',
                '-ar', '16000', '-ac', '1',
                audio_path, '-y'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return False
    
    def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio using Whisper.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcription text or None if failed
        """
        try:
            if self.use_faster_whisper:
                # Use faster-whisper
                logger.info(f"Loading Whisper model: {self.model_size}")
                model = self.WhisperModel(self.model_size, device="cpu", compute_type="int8")
                
                logger.info("Transcribing audio with faster-whisper...")
                segments, info = model.transcribe(audio_path, beam_size=5)
                
                # Combine all segments
                text = " ".join([segment.text.strip() for segment in segments])
                return text.strip()
            else:
                # Use openai-whisper
                logger.info(f"Loading Whisper model: {self.model_size}")
                model = self.whisper.load_model(self.model_size)
                
                logger.info("Transcribing audio with openai-whisper...")
                result = model.transcribe(audio_path)
                
                return result["text"].strip()
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None
    
    def transcribe_video(self, video_path: str) -> Optional[str]:
        """
        Transcribe video by extracting audio first.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Transcription text or None if failed
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            try:
                # Extract audio
                if not self.extract_audio(video_path, tmp_audio.name):
                    return None
                
                # Transcribe
                transcription = self.transcribe_audio(tmp_audio.name)
                
                return transcription
                
            finally:
                # Clean up
                if os.path.exists(tmp_audio.name):
                    os.unlink(tmp_audio.name)


class ViralityScorer:
    """Calculates virality scores based on content analysis."""
    
    def __init__(self):
        """Initialize the virality scorer."""
        self._load_keyword_scores()
        self._load_viral_patterns()
    
    def _load_keyword_scores(self):
        """Load keyword scores from existing system."""
        score_path = Path("/Users/ethan/tiktok_scraper/keyword_score_map.json")
        
        if score_path.exists():
            with open(score_path, 'r') as f:
                self.keyword_scores = json.load(f)
        else:
            logger.warning("Keyword score map not found, using defaults")
            self.keyword_scores = {}
    
    def _load_viral_patterns(self):
        """Define viral content patterns."""
        self.viral_patterns = {
            'hooks': {
                'question': r'^(what|why|how|when|where|who)\s',
                'number': r'^\d+\s+(ways|tips|reasons|things)',
                'shocking': r'^(you won\'t believe|shocking|crazy|wild|insane)',
                'personal': r'^(my|i|we)\s+(just|finally|never)',
                'challenge': r'(challenge|dare|try this)',
            },
            'emotional_triggers': {
                'fear': ['terrifying', 'scary', 'afraid', 'nightmare', 'horror'],
                'anger': ['angry', 'furious', 'outraged', 'disgusted', 'hate'],
                'joy': ['amazing', 'incredible', 'awesome', 'fantastic', 'love'],
                'surprise': ['shocking', 'unbelievable', 'mind-blown', 'unexpected'],
                'sadness': ['heartbreaking', 'crying', 'tragic', 'devastating'],
            },
            'engagement_words': [
                'comment', 'share', 'follow', 'like', 'subscribe',
                'tell me', 'let me know', 'drop', 'tag', 'duet'
            ]
        }
    
    def calculate_hook_strength(self, text: str) -> float:
        """
        Calculate the strength of the opening hook.
        
        Args:
            text: Transcription text
            
        Returns:
            Hook strength score (0-1)
        """
        if not text:
            return 0.0
        
        # Get first sentence
        first_sentence = text.split('.')[0].lower()
        
        score = 0.0
        
        # Check hook patterns
        for hook_type, pattern in self.viral_patterns['hooks'].items():
            if re.search(pattern, first_sentence, re.IGNORECASE):
                score += 0.2
        
        # Length bonus (short hooks are better)
        if len(first_sentence.split()) < 10:
            score += 0.1
        
        return min(1.0, score)
    
    def identify_emotional_triggers(self, text: str) -> List[str]:
        """
        Identify emotional triggers in the content.
        
        Args:
            text: Transcription text
            
        Returns:
            List of identified emotional triggers
        """
        if not text:
            return []
        
        text_lower = text.lower()
        triggers = []
        
        for emotion, keywords in self.viral_patterns['emotional_triggers'].items():
            for keyword in keywords:
                if keyword in text_lower:
                    triggers.append(emotion)
                    break
        
        return list(set(triggers))
    
    def calculate_keyword_score(self, text: str) -> Tuple[float, Dict[str, float]]:
        """
        Calculate score based on viral keywords.
        
        Args:
            text: Transcription text
            
        Returns:
            Tuple of (total_score, keyword_scores)
        """
        if not text:
            return 0.0, {}
        
        text_lower = text.lower()
        words = text_lower.split()
        
        keyword_matches = {}
        total_score = 0.0
        
        # Check loaded keyword scores
        for keyword, score in self.keyword_scores.items():
            if keyword.lower() in text_lower:
                keyword_matches[keyword] = score
                total_score += score
        
        # Check engagement words
        for word in self.viral_patterns['engagement_words']:
            if word in text_lower:
                keyword_matches[word] = 0.5
                total_score += 0.5
        
        # Normalize by text length
        if len(words) > 0:
            total_score = total_score / (len(words) ** 0.5)
        
        return min(1.0, total_score), keyword_matches
    
    def calculate_readability(self, text: str) -> float:
        """
        Calculate readability score (simpler is better for TikTok).
        
        Args:
            text: Transcription text
            
        Returns:
            Readability score (0-1)
        """
        if not text:
            return 0.0
        
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        # Average words per sentence
        avg_words_per_sentence = len(words) / len(sentences)
        
        # Simple words (less than 7 characters)
        simple_words = sum(1 for word in words if len(word) < 7)
        simple_ratio = simple_words / len(words)
        
        # Score calculation (prefer short sentences and simple words)
        sentence_score = 1.0 - min(1.0, avg_words_per_sentence / 20)
        
        return (sentence_score + simple_ratio) / 2
    
    def calculate_sentiment(self, text: str) -> float:
        """
        Calculate sentiment score.
        
        Args:
            text: Transcription text
            
        Returns:
            Sentiment score (-1 to 1)
        """
        try:
            from textblob import TextBlob
            blob = TextBlob(text)
            return blob.sentiment.polarity
        except ImportError:
            logger.warning("TextBlob not installed, using simple sentiment")
            
            # Simple positive/negative word counting
            positive_words = ['love', 'amazing', 'great', 'awesome', 'fantastic', 'best']
            negative_words = ['hate', 'terrible', 'worst', 'awful', 'horrible', 'bad']
            
            text_lower = text.lower()
            pos_count = sum(1 for word in positive_words if word in text_lower)
            neg_count = sum(1 for word in negative_words if word in text_lower)
            
            if pos_count + neg_count == 0:
                return 0.0
            
            return (pos_count - neg_count) / (pos_count + neg_count)
    
    def categorize_content(self, text: str) -> str:
        """
        Categorize content type.
        
        Args:
            text: Transcription text
            
        Returns:
            Content category
        """
        if not text:
            return 'unknown'
        
        text_lower = text.lower()
        
        categories = {
            'story': ['story', 'happened', 'told', 'remember', 'once'],
            'tutorial': ['how to', 'step', 'first', 'then', 'tutorial'],
            'comedy': ['funny', 'joke', 'laugh', 'hilarious', 'comedy'],
            'motivational': ['believe', 'achieve', 'success', 'motivation', 'inspire'],
            'educational': ['learn', 'fact', 'know', 'science', 'history'],
            'reaction': ['react', 'response', 'reply', 'duet', 'stitch'],
        }
        
        scores = {}
        for category, keywords in categories.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[category] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return 'general'
    
    def calculate_virality_score(self, text: str) -> Dict[str, any]:
        """
        Calculate comprehensive virality score.
        
        Args:
            text: Transcription text
            
        Returns:
            Dictionary with scoring details
        """
        # Calculate individual components
        hook_strength = self.calculate_hook_strength(text)
        keyword_score, keyword_matches = self.calculate_keyword_score(text)
        readability = self.calculate_readability(text)
        sentiment = self.calculate_sentiment(text)
        emotional_triggers = self.identify_emotional_triggers(text)
        content_category = self.categorize_content(text)
        
        # Weight components for final score
        weights = {
            'hook': 0.25,
            'keywords': 0.30,
            'readability': 0.15,
            'sentiment': 0.10,
            'emotions': 0.20
        }
        
        emotion_score = len(emotional_triggers) / 5.0  # Normalize to 0-1
        
        final_score = (
            hook_strength * weights['hook'] +
            keyword_score * weights['keywords'] +
            readability * weights['readability'] +
            abs(sentiment) * weights['sentiment'] +
            emotion_score * weights['emotions']
        )
        
        return {
            'final_score': min(1.0, final_score),
            'hook_strength': hook_strength,
            'keyword_score': keyword_score,
            'keyword_matches': keyword_matches,
            'readability': readability,
            'sentiment': sentiment,
            'emotional_triggers': emotional_triggers,
            'content_category': content_category
        }


class VideoAnalyzer:
    """Main class for analyzing videos."""
    
    def __init__(self, transcriber: VideoTranscriber, scorer: ViralityScorer):
        """
        Initialize the analyzer.
        
        Args:
            transcriber: VideoTranscriber instance
            scorer: ViralityScorer instance
        """
        self.transcriber = transcriber
        self.scorer = scorer
    
    def analyze_video(self, video_path: str) -> VideoAnalysis:
        """
        Analyze a single video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            VideoAnalysis object
        """
        start_time = datetime.now()
        filename = os.path.basename(video_path)
        
        try:
            # Transcribe video
            logger.info(f"Processing: {filename}")
            transcription = self.transcriber.transcribe_video(video_path)
            
            if not transcription:
                raise ValueError("Transcription failed")
            
            # Calculate virality scores
            scores = self.scorer.calculate_virality_score(transcription)
            
            # Create analysis object
            analysis = VideoAnalysis(
                video_path=video_path,
                filename=filename,
                transcription=transcription,
                virality_score=scores['final_score'],
                keyword_scores=scores['keyword_matches'],
                sentiment_score=scores['sentiment'],
                readability_score=scores['readability'],
                hook_strength=scores['hook_strength'],
                emotional_triggers=scores['emotional_triggers'],
                content_category=scores['content_category'],
                processing_time=(datetime.now() - start_time).total_seconds()
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing {filename}: {e}")
            
            return VideoAnalysis(
                video_path=video_path,
                filename=filename,
                transcription="",
                virality_score=0.0,
                keyword_scores={},
                sentiment_score=0.0,
                readability_score=0.0,
                hook_strength=0.0,
                emotional_triggers=[],
                content_category="unknown",
                processing_time=(datetime.now() - start_time).total_seconds(),
                error=str(e)
            )
    
    def analyze_directory(self, directory: str, output_dir: str) -> List[VideoAnalysis]:
        """
        Analyze all videos in a directory.
        
        Args:
            directory: Directory containing videos
            output_dir: Directory to save results
            
        Returns:
            List of VideoAnalysis objects
        """
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        
        # Find all video files
        video_files = []
        for ext in video_extensions:
            video_files.extend(Path(directory).rglob(f"*{ext}"))
        
        logger.info(f"Found {len(video_files)} videos to analyze")
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Analyze each video
        results = []
        for i, video_path in enumerate(video_files, 1):
            logger.info(f"Analyzing video {i}/{len(video_files)}")
            
            analysis = self.analyze_video(str(video_path))
            results.append(analysis)
            
            # Save individual result
            self._save_individual_result(analysis, output_dir)
        
        # Save summary
        self._save_summary(results, output_dir)
        
        return results
    
    def _save_individual_result(self, analysis: VideoAnalysis, output_dir: str):
        """Save individual video analysis result."""
        # Create safe filename (truncate if too long)
        base_name = os.path.splitext(analysis.filename)[0]
        safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name)
        
        # Truncate to reasonable length to avoid OS errors
        if len(safe_filename) > 100:
            safe_filename = safe_filename[:100]
        
        # Add timestamp to ensure uniqueness
        import hashlib
        file_hash = hashlib.md5(analysis.filename.encode()).hexdigest()[:8]
        output_filename = f"{safe_filename}_{file_hash}_analysis.json"
        
        output_path = Path(output_dir) / output_filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(analysis), f, indent=2, ensure_ascii=False)
    
    def _save_summary(self, results: List[VideoAnalysis], output_dir: str):
        """Save summary of all analyses."""
        summary = {
            'total_videos': len(results),
            'successful_analyses': sum(1 for r in results if r.error is None),
            'failed_analyses': sum(1 for r in results if r.error is not None),
            'average_virality_score': sum(r.virality_score for r in results) / len(results) if results else 0,
            'timestamp': datetime.now().isoformat(),
            'videos': []
        }
        
        # Sort by virality score
        sorted_results = sorted(results, key=lambda x: x.virality_score, reverse=True)
        
        for result in sorted_results:
            summary['videos'].append({
                'filename': result.filename,
                'virality_score': result.virality_score,
                'hook_strength': result.hook_strength,
                'sentiment': result.sentiment_score,
                'category': result.content_category,
                'emotional_triggers': result.emotional_triggers,
                'top_keywords': sorted(
                    result.keyword_scores.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5],
                'transcription_preview': result.transcription[:200] + '...' if len(result.transcription) > 200 else result.transcription,
                'error': result.error
            })
        
        # Save summary
        summary_path = Path(output_dir) / 'analysis_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Create markdown report
        self._create_markdown_report(sorted_results, output_dir)
    
    def _create_markdown_report(self, results: List[VideoAnalysis], output_dir: str):
        """Create a markdown report of the analysis."""
        report_path = Path(output_dir) / 'analysis_report.md'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Video Analysis Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total Videos Analyzed: {len(results)}\n\n")
            
            # Summary statistics
            f.write("## Summary Statistics\n\n")
            successful = [r for r in results if r.error is None]
            if successful:
                avg_score = sum(r.virality_score for r in successful) / len(successful)
                f.write(f"- Average Virality Score: {avg_score:.3f}\n")
                f.write(f"- Highest Score: {successful[0].virality_score:.3f}\n")
                f.write(f"- Lowest Score: {successful[-1].virality_score:.3f}\n")
                
                # Category breakdown
                categories = {}
                for r in successful:
                    categories[r.content_category] = categories.get(r.content_category, 0) + 1
                
                f.write("\n### Content Categories\n")
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"- {cat}: {count} videos\n")
            
            # Top performing videos
            f.write("\n## Top 10 Videos by Virality Score\n\n")
            for i, result in enumerate(results[:10], 1):
                if result.error:
                    continue
                    
                f.write(f"### {i}. {result.filename}\n\n")
                f.write(f"**Virality Score: {result.virality_score:.3f}**\n\n")
                f.write(f"- Hook Strength: {result.hook_strength:.2f}\n")
                f.write(f"- Sentiment: {result.sentiment_score:.2f}\n")
                f.write(f"- Readability: {result.readability_score:.2f}\n")
                f.write(f"- Category: {result.content_category}\n")
                f.write(f"- Emotional Triggers: {', '.join(result.emotional_triggers) or 'None'}\n")
                
                if result.keyword_scores:
                    f.write(f"- Top Keywords: ")
                    top_keywords = sorted(result.keyword_scores.items(), key=lambda x: x[1], reverse=True)[:5]
                    f.write(', '.join([f"{k} ({v:.2f})" for k, v in top_keywords]))
                    f.write("\n")
                
                f.write(f"\n**Transcription Preview:**\n> {result.transcription[:300]}...\n\n")
                f.write("---\n\n")
            
            # Failed analyses
            failed = [r for r in results if r.error is not None]
            if failed:
                f.write(f"\n## Failed Analyses ({len(failed)} videos)\n\n")
                for result in failed:
                    f.write(f"- {result.filename}: {result.error}\n")


def main():
    """Main function to run the video analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze TikTok videos for virality')
    parser.add_argument('input_dir', help='Directory containing videos')
    parser.add_argument('--output', '-o', default='video_analysis/reports', 
                       help='Output directory for results')
    parser.add_argument('--model', '-m', default='base',
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Whisper model size')
    
    args = parser.parse_args()
    
    # Initialize components
    transcriber = VideoTranscriber(model_size=args.model)
    scorer = ViralityScorer()
    analyzer = VideoAnalyzer(transcriber, scorer)
    
    # Run analysis
    results = analyzer.analyze_directory(args.input_dir, args.output)
    
    logger.info(f"Analysis complete! Results saved to {args.output}")
    print(f"\nAnalyzed {len(results)} videos")
    print(f"Results saved to: {args.output}/analysis_summary.json")
    print(f"Detailed report: {args.output}/analysis_report.md")


if __name__ == '__main__':
    main()