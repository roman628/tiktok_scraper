#!/usr/bin/env python3
"""
Generate clean keyword-to-score mapping TXT file (NO NAMES)
Filters out personal names and focuses on content keywords
"""

import json
import sys
import os
import re
from pathlib import Path

def get_comprehensive_stopwords():
    """Get comprehensive stopword list including names"""
    
    # Basic English stopwords
    basic_stops = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'will', 'with', 'you', 'your', 'they', 'them', 'him',
        'her', 'his', 'she', 'we', 'us', 'our', 'this', 'that', 'these',
        'those', 'i', 'me', 'my', 'mine', 'myself', 'so', 'but', 'if',
        'or', 'because', 'as', 'until', 'while', 'all', 'any', 'both',
        'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'than', 'too', 'very',
        'can', 'could', 'would', 'should', 'may', 'might', 'must', 'shall',
        'will', 'do', 'does', 'did', 'have', 'had', 'been', 'being',
        'get', 'got', 'go', 'going', 'gone', 'come', 'came', 'coming',
        'see', 'saw', 'seen', 'look', 'looking', 'take', 'took', 'taken',
        'make', 'made', 'making', 'know', 'knew', 'known', 'think',
        'thought', 'thinking', 'say', 'said', 'saying', 'tell', 'told',
        'give', 'gave', 'given', 'find', 'found', 'work', 'worked',
        'use', 'used', 'using', 'want', 'wanted', 'need', 'needed',
        'try', 'tried', 'trying', 'ask', 'asked', 'asking', 'feel',
        'felt', 'feeling', 'seem', 'seemed', 'become', 'became',
        'leave', 'left', 'call', 'called', 'put', 'putting', 'end',
        'turn', 'turned', 'start', 'started', 'show', 'showed', 'hear',
        'heard', 'play', 'played', 'run', 'ran', 'move', 'moved', 'live',
        'lived', 'believe', 'believed', 'bring', 'brought', 'happen',
        'happened', 'write', 'wrote', 'sit', 'sat', 'stand', 'stood',
        'lose', 'lost', 'pay', 'paid', 'meet', 'met', 'include', 'included'
    }
    
    # TikTok platform specific
    tiktok_stops = {
        'tiktok', 'video', 'watch', 'like', 'comment', 'share', 'follow',
        'viral', 'trending', 'new', 'today', 'now', 'check', 'out', 'up',
        'down', 'back', 'here', 'there', 'when', 'where', 'what', 'how',
        'why', 'who', 'dont', 'doesnt', 'didnt', 'wasnt', 'werent', 'isnt',
        'arent', 'havent', 'hasnt', 'hadnt', 'wont', 'wouldnt', 'couldnt',
        'shouldnt', 'mightnt', 'mustnt', 'im', 'youre', 'hes', 'shes',
        'its', 'were', 'theyre', 'ive', 'youve', 'weve', 'theyve',
        'id', 'youd', 'hed', 'shed', 'wed', 'theyd', 'ill', 'youll',
        'hell', 'shell', 'well', 'theyll', 'lets', 'thats', 'whats',
        'heres', 'wheres', 'theres', 'hows', 'whys'
    }
    
    # Common personal names (English)
    common_names = {
        'aaron', 'adam', 'adrian', 'alan', 'alex', 'alexander', 'andrew',
        'andy', 'anthony', 'antonio', 'arthur', 'austin', 'ben', 'benjamin',
        'bill', 'bob', 'bobby', 'brad', 'brandon', 'brian', 'bruce',
        'bryan', 'carl', 'carlos', 'chad', 'charles', 'charlie', 'chris',
        'christopher', 'chuck', 'craig', 'daniel', 'danny', 'dave', 'david',
        'dean', 'dennis', 'derek', 'don', 'donald', 'doug', 'douglas',
        'drew', 'dylan', 'eddie', 'edward', 'eric', 'ethan', 'frank',
        'fred', 'gary', 'george', 'greg', 'gregory', 'harry', 'henry',
        'jack', 'jackson', 'jacob', 'james', 'jason', 'jay', 'jeff',
        'jeffrey', 'jeremy', 'jerry', 'jesse', 'jim', 'jimmy', 'joe',
        'john', 'johnny', 'jon', 'jonathan', 'jordan', 'jose', 'joseph',
        'josh', 'joshua', 'justin', 'karl', 'keith', 'ken', 'kenneth',
        'kevin', 'kyle', 'larry', 'lawrence', 'lee', 'logan', 'louis',
        'luke', 'marcus', 'mark', 'martin', 'matt', 'matthew', 'max',
        'michael', 'mike', 'nathan', 'nick', 'nicholas', 'noah', 'oscar',
        'patrick', 'paul', 'peter', 'philip', 'richard', 'rick', 'rob',
        'robert', 'roger', 'ron', 'ronald', 'russell', 'ryan', 'sam',
        'samuel', 'scott', 'sean', 'stephen', 'steve', 'steven', 'ted',
        'thomas', 'tim', 'timothy', 'todd', 'tom', 'tommy', 'tony',
        'travis', 'tyler', 'victor', 'walter', 'wayne', 'william', 'willie',
        
        # Female names
        'amanda', 'amy', 'andrea', 'angela', 'anna', 'anne', 'annie',
        'ashley', 'barbara', 'betty', 'beverly', 'brenda', 'brittany',
        'carol', 'carolyn', 'catherine', 'cathy', 'charlotte', 'cheryl',
        'christina', 'christine', 'claire', 'crystal', 'cynthia', 'danielle',
        'dawn', 'deborah', 'debra', 'denise', 'diana', 'diane', 'donna',
        'doris', 'dorothy', 'elizabeth', 'emily', 'emma', 'erin', 'evelyn',
        'frances', 'gloria', 'grace', 'hannah', 'heather', 'helen', 'irene',
        'jacqueline', 'jane', 'janet', 'janice', 'jean', 'jennifer', 'jessica',
        'joan', 'joyce', 'judith', 'judy', 'julia', 'julie', 'karen', 'katherine',
        'kathleen', 'kathryn', 'kathy', 'kelly', 'kimberly', 'laura', 'lauren',
        'linda', 'lisa', 'lori', 'louise', 'margaret', 'maria', 'marie',
        'marilyn', 'martha', 'mary', 'megan', 'melissa', 'michelle', 'nancy',
        'nicole', 'norma', 'olivia', 'pamela', 'patricia', 'paula', 'phyllis',
        'rachel', 'rebecca', 'robin', 'rose', 'ruth', 'sandra', 'sara',
        'sarah', 'sharon', 'shirley', 'stephanie', 'susan', 'tammy', 'teresa',
        'theresa', 'tiffany', 'victoria', 'virginia', 'wanda',
        
        # Common shortened/nickname versions
        'abby', 'ally', 'angie', 'becky', 'beth', 'cindy', 'dee', 'ella',
        'gina', 'haley', 'jackie', 'jenny', 'jess', 'jo', 'kate', 'katie',
        'kay', 'kim', 'liz', 'mandy', 'mary', 'meg', 'molly', 'nat',
        'nikki', 'patty', 'penny', 'sam', 'sandy', 'stacy', 'sue', 'tammy',
        'tina', 'tracy', 'val', 'vicky', 'wendy',
        
        # Male nicknames
        'abe', 'al', 'andy', 'art', 'bart', 'ben', 'bill', 'bob', 'brad',
        'cal', 'chip', 'chuck', 'dan', 'dave', 'ed', 'frank', 'fred',
        'gary', 'gene', 'hank', 'jack', 'jake', 'jay', 'jeff', 'jim',
        'joe', 'josh', 'ken', 'larry', 'len', 'lou', 'mac', 'max', 'mike',
        'nick', 'pat', 'pete', 'phil', 'ray', 'rich', 'rick', 'rob',
        'rod', 'ron', 'russ', 'scott', 'steve', 'ted', 'tim', 'tom',
        'tony', 'vic', 'walt', 'will',
        
        # Modern/Social media names
        'aiden', 'brooklyn', 'carly', 'destiny', 'diamond', 'hunter',
        'jaden', 'jayden', 'madison', 'mason', 'skylar', 'tyler',
        'brandon', 'brittney', 'austin', 'taylor', 'jordan', 'morgan',
        'riley', 'casey', 'jamie', 'alex', 'drew', 'cameron', 'devon',
        'robbie', 'billie', 'jamie', 'leslie', 'kelly', 'terry', 'blake'
    }
    
    # Common usernames/handles that appear in content
    username_patterns = {
        'user', 'username', 'handle', 'account', 'profile', 'creator',
        'tiktoker', 'influencer', 'youtuber', 'streamer', 'content'
    }
    
    # Numbers and short meaningless words
    short_words = {
        'ah', 'eh', 'oh', 'um', 'uh', 'ya', 'yo', 'hi', 'hey', 'ok',
        'okay', 'yes', 'yeah', 'yep', 'nah', 'nope', 'wow', 'omg',
        'lol', 'lmao', 'wtf', 'tbh', 'imo', 'btw', 'fyi', 'aka',
        'etc', 'asap', 'rip', 'diy', 'pov', 'irl', 'ngl', 'smh'
    }
    
    return basic_stops.union(tiktok_stops).union(common_names).union(username_patterns).union(short_words)

def is_meaningful_keyword(word, stopwords):
    """Check if a word is a meaningful keyword"""
    if not word or len(word) < 3:
        return False
    
    if word.lower() in stopwords:
        return False
    
    # Skip if all digits
    if word.isdigit():
        return False
    
    # Skip if looks like a username (@something)
    if word.startswith('@'):
        return False
    
    # Skip if has numbers mixed with letters (likely usernames/codes)
    if re.search(r'\d', word) and re.search(r'[a-zA-Z]', word):
        return False
    
    # Skip very common pattern words
    common_patterns = ['gonna', 'wanna', 'gotta', 'kinda', 'sorta', 'cause']
    if word.lower() in common_patterns:
        return False
    
    return True

def extract_keywords_with_timing(text, stopwords, video_duration=60):
    """Extract keywords with timing information for transcription scoring"""
    if not text:
        return []
    
    # Clean text and extract words with positions
    text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
    words = re.findall(r'\b[a-zA-Z]+\b', text_clean)
    
    # Filter for meaningful keywords and calculate timing scores
    keywords_with_scores = []
    text_length = len(text_clean)
    
    for i, word in enumerate(words):
        if is_meaningful_keyword(word, stopwords):
            # Calculate position in text (0-1 ratio)
            position_ratio = i / len(words) if len(words) > 0 else 0
            
            # Estimate time position (assuming even speech distribution)
            estimated_time = position_ratio * video_duration
            
            # Calculate timing bonus (1.0 for first 5 seconds, decreasing after)
            if estimated_time <= 5:
                timing_bonus = 1.0  # Full bonus for first 5 seconds
            elif estimated_time <= 15:
                timing_bonus = 0.8  # Good bonus for 5-15 seconds
            elif estimated_time <= 30:
                timing_bonus = 0.6  # Medium bonus for 15-30 seconds
            else:
                timing_bonus = 0.4  # Reduced bonus after 30 seconds
            
            keywords_with_scores.append({
                'keyword': word,
                'timing_bonus': timing_bonus,
                'estimated_time': estimated_time
            })
    
    return keywords_with_scores

def extract_keywords_fallback(text, stopwords):
    """Extract clean, meaningful keywords (for comment text without timing)"""
    if not text:
        return []
    
    # Clean text and extract words
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    
    # Filter for meaningful keywords
    keywords = [w for w in words if is_meaningful_keyword(w, stopwords)]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)
    
    return unique_keywords

def calculate_engagement_score(video):
    """Calculate engagement score for a video"""
    views = video.get('view_count', 0)
    likes = video.get('like_count', 0)
    comments = video.get('comment_count', 0)
    reposts = video.get('repost_count', 0) or 0
    
    if views == 0:
        return 0
    
    # Weighted engagement: likes + comments*2 + reposts*1.5
    weighted_engagement = likes + (comments * 2) + (reposts * 1.5)
    engagement_ratio = weighted_engagement / views
    
    return min(engagement_ratio, 1.0)  # Cap at 1.0

def generate_keyword_map():
    """Generate clean keyword mapping without names"""
    
    # Load master2.json
    master_file = '/Users/ethan/tiktok_scraper/master2.json'
    if not os.path.exists(master_file):
        print(f"Error: {master_file} not found")
        return
    
    print("Loading master2.json...")
    with open(master_file, 'r', encoding='utf-8') as f:
        videos = json.load(f)
    
    # Get comprehensive stopwords
    stopwords = get_comprehensive_stopwords()
    print(f"Using {len(stopwords)} stopwords/names for filtering")
    
    keyword_data = {}
    total_videos = len(videos)
    
    print(f"Processing {total_videos} videos for transcription & comment keywords...")
    
    for i, video in enumerate(videos):
        if i % 100 == 0:
            print(f"  Processed {i}/{total_videos} videos...")
        
        # Extract text content - ONLY from transcriptions and comments
        transcription = video.get('whisper_transcription', '') or ''
        video_duration = video.get('duration', 60)  # Default to 60 seconds if not available
        
        # Extract comment text if available
        comment_text = ''
        top_comments = video.get('top_comments', [])
        if top_comments:
            comment_texts = [comment.get('comment_text', '') for comment in top_comments if comment.get('comment_text')]
            comment_text = ' '.join(comment_texts)
        
        # Extract keywords with timing information for transcriptions
        transcription_keywords = extract_keywords_with_timing(transcription, stopwords, video_duration)
        
        # Extract regular keywords from comments (no timing bonus)
        comment_keywords = extract_keywords_fallback(comment_text, stopwords)
        
        # Combine all unique keywords
        all_keywords = {}
        
        # Add transcription keywords with timing bonuses
        for kw_data in transcription_keywords:
            keyword = kw_data['keyword']
            if keyword not in all_keywords:
                all_keywords[keyword] = {
                    'timing_bonus': kw_data['timing_bonus'],
                    'sources': ['transcription'],
                    'estimated_time': kw_data['estimated_time']
                }
            else:
                # If keyword appears multiple times, use the best timing bonus
                all_keywords[keyword]['timing_bonus'] = max(
                    all_keywords[keyword]['timing_bonus'], 
                    kw_data['timing_bonus']
                )
        
        # Add comment keywords (no timing bonus, but still valuable)
        for keyword in comment_keywords:
            if keyword not in all_keywords:
                all_keywords[keyword] = {
                    'timing_bonus': 0.7,  # Standard bonus for comment keywords
                    'sources': ['comment'],
                    'estimated_time': None
                }
            else:
                all_keywords[keyword]['sources'].append('comment')
        
        keywords = list(all_keywords.keys())
        
        # Calculate engagement score
        engagement_score = calculate_engagement_score(video)
        
        # Update keyword data with timing bonuses
        for keyword in keywords:
            if keyword not in keyword_data:
                keyword_data[keyword] = {
                    'total_score': 0,
                    'frequency': 0,
                    'total_engagement': 0,
                    'videos': [],
                    'view_counts': [],
                    'like_counts': [],
                    'timing_bonuses': [],
                    'early_appearances': 0,  # Count of appearances in first 5 seconds
                    'total_appearances': 0
                }
            
            # Get timing bonus for this keyword in this video
            timing_bonus = all_keywords[keyword]['timing_bonus']
            estimated_time = all_keywords[keyword].get('estimated_time')
            
            keyword_data[keyword]['frequency'] += 1
            keyword_data[keyword]['total_engagement'] += engagement_score
            keyword_data[keyword]['videos'].append(video.get('video_id', ''))
            keyword_data[keyword]['view_counts'].append(video.get('view_count', 0))
            keyword_data[keyword]['like_counts'].append(video.get('like_count', 0))
            keyword_data[keyword]['timing_bonuses'].append(timing_bonus)
            keyword_data[keyword]['total_appearances'] += 1
            
            # Track early appearances (first 5 seconds)
            if estimated_time is not None and estimated_time <= 5:
                keyword_data[keyword]['early_appearances'] += 1
            
            # Enhanced scoring: engagement + viral potential + timing bonus
            base_score = engagement_score * 10  # Scale engagement
            viral_bonus = 1.0
            if engagement_score > 0.2:  # High engagement
                viral_bonus = 1.5
            elif engagement_score > 0.15:  # Medium-high engagement
                viral_bonus = 1.2
            
            # Apply timing bonus to the score
            final_score = base_score * viral_bonus * timing_bonus
            keyword_data[keyword]['total_score'] += final_score
    
    print("Calculating final scores and filtering...")
    
    # Calculate final scores and filter
    final_keywords = []
    for keyword, data in keyword_data.items():
        # Skip keywords that appear in very few videos
        if data['frequency'] < 2:
            continue
        
        avg_engagement = data['total_engagement'] / data['frequency']
        avg_views = sum(data['view_counts']) / len(data['view_counts'])
        avg_likes = sum(data['like_counts']) / len(data['like_counts'])
        avg_timing_bonus = sum(data['timing_bonuses']) / len(data['timing_bonuses'])
        early_appearance_ratio = data['early_appearances'] / data['total_appearances']
        
        # Enhanced scoring algorithm with timing consideration
        frequency_score = min(data['frequency'] / 5, 3.0)  # Frequency bonus (cap at 3.0)
        engagement_multiplier = 1 + avg_engagement * 2  # Engagement boost
        
        # Timing multiplier - rewards keywords that appear early
        timing_multiplier = 0.7 + (avg_timing_bonus * 0.3)  # Range: 0.7 to 1.0
        
        # Early appearance bonus - extra boost for keywords that consistently appear early
        early_bonus = 1.0 + (early_appearance_ratio * 0.2)  # Up to 20% bonus
        
        # Rarity bonus for less common but high-performing keywords
        rarity_bonus = 1.0
        if data['frequency'] < 5 and avg_engagement > 0.15:
            rarity_bonus = 1.3
        elif data['frequency'] < 10 and avg_engagement > 0.12:
            rarity_bonus = 1.1
        
        # Final score calculation with timing factors
        final_score = (data['total_score'] / data['frequency']) * frequency_score * engagement_multiplier * timing_multiplier * early_bonus * rarity_bonus
        
        final_keywords.append({
            'keyword': keyword,
            'score': round(final_score, 4),
            'frequency': data['frequency'],
            'avg_engagement': round(avg_engagement, 6),
            'avg_views': round(avg_views, 0),
            'avg_likes': round(avg_likes, 0),
            'video_count': len(set(data['videos'])),
            'avg_timing_bonus': round(avg_timing_bonus, 3),
            'early_appearance_ratio': round(early_appearance_ratio, 3),
            'early_appearances': data['early_appearances']
        })
    
    # Sort by score (descending)
    final_keywords.sort(key=lambda x: x['score'], reverse=True)
    
    # Generate both human-readable TXT file and machine-readable JSON file
    output_file = '/Users/ethan/tiktok_scraper/keyword_score_map.txt'
    json_output_file = '/Users/ethan/tiktok_scraper/keyword_score_map.json'
    
    print(f"Writing transcription & comment keyword map to {output_file}...")
    print(f"Writing machine-readable JSON to {json_output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 90 + "\n")
        f.write("TIKTOK TIMING-AWARE KEYWORD SCORING MAP - TRANSCRIPTIONS & COMMENTS\n")
        f.write("=" * 100 + "\n")
        f.write(f"Generated from {total_videos} videos in master2.json\n")
        f.write(f"Source: Transcriptions and comment content only (excludes titles/descriptions)\n")
        f.write(f"Timing Factor: Keywords in first 5 seconds get highest scores, decreasing over time\n")
        f.write(f"Total meaningful keywords found: {len(final_keywords)}\n")
        f.write(f"Filtered out names and noise words using {len(stopwords)} stopwords\n")
        f.write("=" * 90 + "\n\n")
        
        f.write("FORMAT: KEYWORD | SCORE | FREQ | AVG_ENGAGEMENT | AVG_VIEWS | AVG_LIKES | VIDEOS | TIMING | EARLY%\n")
        f.write("-" * 100 + "\n\n")
        
        for i, item in enumerate(final_keywords, 1):
            line = f"{i:4d}. {item['keyword']:<20} | {item['score']:8.4f} | {item['frequency']:4d} | {item['avg_engagement']:10.6f} | {item['avg_views']:9.0f} | {item['avg_likes']:8.0f} | {item['video_count']:3d} | {item['avg_timing_bonus']:6.3f} | {item['early_appearance_ratio']:5.1%}\n"
            f.write(line)
        
        f.write("\n" + "=" * 90 + "\n")
        f.write("TOP 30 MEANINGFUL KEYWORDS SUMMARY\n")
        f.write("=" * 90 + "\n")
        
        for i, item in enumerate(final_keywords[:30], 1):
            f.write(f"{i:2d}. {item['keyword']:<18} - Score: {item['score']:8.4f} | Freq: {item['frequency']:3d} | Engagement: {item['avg_engagement']:.4f} | Timing: {item['avg_timing_bonus']:.3f} | Early: {item['early_appearance_ratio']:.1%}\n")
        
        f.write("\n" + "=" * 90 + "\n")
        f.write("CONTENT CATEGORIES IDENTIFIED\n")
        f.write("=" * 90 + "\n")
        
        # Categorize keywords
        categories = {
            'Relationships': ['relationship', 'dating', 'love', 'couples', 'marriage', 'boyfriend', 'girlfriend'],
            'Entertainment': ['funny', 'comedy', 'meme', 'joke', 'entertainment', 'humor', 'fun'],
            'Social Media': ['viral', 'trending', 'content', 'social', 'media', 'platform'],
            'Stories': ['story', 'storytime', 'reddit', 'aita', 'drama', 'tea'],
            'Lifestyle': ['life', 'daily', 'routine', 'lifestyle', 'vlog', 'personal'],
            'Educational': ['learn', 'education', 'tutorial', 'howto', 'guide', 'tips']
        }
        
        for category, keywords in categories.items():
            found_keywords = [item for item in final_keywords[:50] if any(kw in item['keyword'].lower() for kw in keywords)]
            if found_keywords:
                f.write(f"\n{category}:\n")
                for item in found_keywords[:5]:
                    f.write(f"  - {item['keyword']} (Score: {item['score']:.4f})\n")
        
        f.write("\n" + "=" * 90 + "\n")
        f.write("TRANSCRIPTION & COMMENT ANALYSIS COMPLETE - NO PERSONAL NAMES\n")
        f.write("Keywords extracted from spoken content and user comments only\n")
        f.write("=" * 90 + "\n")
    
    # Generate machine-readable JSON file for live scoring systems
    print(f"Writing JSON format for automated systems...")
    
    # Create JSON structure optimized for live scoring
    json_data = {
        "metadata": {
            "generated_at": "2025-07-27T02:10:00Z",
            "source": "transcriptions_and_comments_only",
            "total_videos_analyzed": total_videos,
            "total_keywords": len(final_keywords),
            "timing_factor_enabled": True,
            "stopwords_filtered": len(stopwords),
            "description": "TikTok keyword scoring with timing-aware algorithm"
        },
        "scoring_algorithm": {
            "timing_bonuses": {
                "0-5_seconds": 1.0,
                "5-15_seconds": 0.8,
                "15-30_seconds": 0.6,
                "30+_seconds": 0.4,
                "comment_keywords": 0.7
            },
            "engagement_thresholds": {
                "high_engagement": 0.2,
                "medium_engagement": 0.15
            },
            "early_appearance_bonus": 0.2,
            "timing_multiplier_range": [0.7, 1.0]
        },
        "keywords": {}
    }
    
    # Convert keywords to machine-readable format
    for keyword_data in final_keywords:
        keyword = keyword_data['keyword']
        json_data["keywords"][keyword] = {
            "score": keyword_data['score'],
            "frequency": keyword_data['frequency'],
            "video_count": keyword_data['video_count'],
            "metrics": {
                "avg_engagement": keyword_data['avg_engagement'],
                "avg_views": keyword_data['avg_views'],
                "avg_likes": keyword_data['avg_likes']
            },
            "timing": {
                "avg_timing_bonus": keyword_data['avg_timing_bonus'],
                "early_appearance_ratio": keyword_data['early_appearance_ratio'],
                "early_appearances": keyword_data['early_appearances']
            },
            "performance_indicators": {
                "viral_potential": "high" if keyword_data['score'] > 3.0 else "medium" if keyword_data['score'] > 1.5 else "low",
                "timing_preference": "early" if keyword_data['avg_timing_bonus'] > 0.7 else "neutral",
                "consistency": "high" if keyword_data['early_appearance_ratio'] > 0.3 else "medium" if keyword_data['early_appearance_ratio'] > 0.1 else "low"
            }
        }
    
    # Create lookup table for fast keyword scoring
    json_data["lookup_table"] = {
        keyword_data['keyword']: keyword_data['score'] 
        for keyword_data in final_keywords
    }
    
    # Create performance tiers for quick categorization
    json_data["performance_tiers"] = {
        "viral": [kw['keyword'] for kw in final_keywords if kw['score'] > 3.0],
        "high": [kw['keyword'] for kw in final_keywords if 1.5 <= kw['score'] <= 3.0],
        "medium": [kw['keyword'] for kw in final_keywords if 0.8 <= kw['score'] < 1.5],
        "low": [kw['keyword'] for kw in final_keywords if kw['score'] < 0.8]
    }
    
    # Write JSON file
    with open(json_output_file, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, indent=2, ensure_ascii=False)
    
    print(f"✅ Clean keyword map generated successfully!")
    print(f"📍 Human-readable output: {output_file}")
    print(f"🤖 Machine-readable output: {json_output_file}")
    print(f"📊 Total meaningful keywords: {len(final_keywords)}")
    if final_keywords:
        print(f"🏆 Top keyword: '{final_keywords[0]['keyword']}' (Score: {final_keywords[0]['score']:.4f})")
    
    return output_file, json_output_file

if __name__ == "__main__":
    try:
        output_files = generate_keyword_map()
        if isinstance(output_files, tuple):
            output_file, json_output_file = output_files
        else:
            output_file = output_files
            json_output_file = None
        
        if output_file and os.path.exists(output_file):
            # Show preview of first 10 keywords
            print("\n📋 PREVIEW (first 10 clean keywords):")
            print("-" * 60)
            with open(output_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[9:19]:  # Skip header, show first 10 keywords
                    print(line.strip())
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()