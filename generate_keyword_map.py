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

def extract_keywords_fallback(text, stopwords):
    """Extract clean, meaningful keywords"""
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
        
        # Extract comment text if available
        comment_text = ''
        top_comments = video.get('top_comments', [])
        if top_comments:
            comment_texts = [comment.get('comment_text', '') for comment in top_comments if comment.get('comment_text')]
            comment_text = ' '.join(comment_texts)
        
        # Combine transcription and comment content only
        all_text = f"{transcription} {comment_text}"
        
        # Extract clean keywords (no names)
        keywords = extract_keywords_fallback(all_text, stopwords)
        
        # Calculate engagement score
        engagement_score = calculate_engagement_score(video)
        
        # Update keyword data
        for keyword in keywords:
            if keyword not in keyword_data:
                keyword_data[keyword] = {
                    'total_score': 0,
                    'frequency': 0,
                    'total_engagement': 0,
                    'videos': [],
                    'view_counts': [],
                    'like_counts': []
                }
            
            keyword_data[keyword]['frequency'] += 1
            keyword_data[keyword]['total_engagement'] += engagement_score
            keyword_data[keyword]['videos'].append(video.get('video_id', ''))
            keyword_data[keyword]['view_counts'].append(video.get('view_count', 0))
            keyword_data[keyword]['like_counts'].append(video.get('like_count', 0))
            
            # Enhanced scoring: engagement + frequency bonus + viral potential
            base_score = engagement_score * 10  # Scale engagement
            viral_bonus = 1.0
            if engagement_score > 0.2:  # High engagement
                viral_bonus = 1.5
            elif engagement_score > 0.15:  # Medium-high engagement
                viral_bonus = 1.2
            
            keyword_data[keyword]['total_score'] += base_score * viral_bonus
    
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
        
        # Enhanced scoring algorithm
        frequency_score = min(data['frequency'] / 5, 3.0)  # Frequency bonus (cap at 3.0)
        engagement_multiplier = 1 + avg_engagement * 2  # Engagement boost
        
        # Rarity bonus for less common but high-performing keywords
        rarity_bonus = 1.0
        if data['frequency'] < 5 and avg_engagement > 0.15:
            rarity_bonus = 1.3
        elif data['frequency'] < 10 and avg_engagement > 0.12:
            rarity_bonus = 1.1
        
        # Final score calculation
        final_score = (data['total_score'] / data['frequency']) * frequency_score * engagement_multiplier * rarity_bonus
        
        final_keywords.append({
            'keyword': keyword,
            'score': round(final_score, 4),
            'frequency': data['frequency'],
            'avg_engagement': round(avg_engagement, 6),
            'avg_views': round(avg_views, 0),
            'avg_likes': round(avg_likes, 0),
            'video_count': len(set(data['videos']))
        })
    
    # Sort by score (descending)
    final_keywords.sort(key=lambda x: x['score'], reverse=True)
    
    # Generate clean TXT file
    output_file = '/Users/ethan/tiktok_scraper/keyword_score_map.txt'
    
    print(f"Writing transcription & comment keyword map to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 90 + "\n")
        f.write("TIKTOK CLEAN KEYWORD SCORING MAP - TRANSCRIPTIONS & COMMENTS ONLY\n")
        f.write("=" * 90 + "\n")
        f.write(f"Generated from {total_videos} videos in master2.json\n")
        f.write(f"Source: Transcriptions and comment content only (excludes titles/descriptions)\n")
        f.write(f"Total meaningful keywords found: {len(final_keywords)}\n")
        f.write(f"Filtered out names and noise words using {len(stopwords)} stopwords\n")
        f.write("=" * 90 + "\n\n")
        
        f.write("FORMAT: KEYWORD | SCORE | FREQ | AVG_ENGAGEMENT | AVG_VIEWS | AVG_LIKES | VIDEOS\n")
        f.write("-" * 90 + "\n\n")
        
        for i, item in enumerate(final_keywords, 1):
            line = f"{i:4d}. {item['keyword']:<20} | {item['score']:8.4f} | {item['frequency']:4d} | {item['avg_engagement']:10.6f} | {item['avg_views']:9.0f} | {item['avg_likes']:8.0f} | {item['video_count']:3d}\n"
            f.write(line)
        
        f.write("\n" + "=" * 90 + "\n")
        f.write("TOP 30 MEANINGFUL KEYWORDS SUMMARY\n")
        f.write("=" * 90 + "\n")
        
        for i, item in enumerate(final_keywords[:30], 1):
            f.write(f"{i:2d}. {item['keyword']:<18} - Score: {item['score']:8.4f} | Freq: {item['frequency']:3d} | Engagement: {item['avg_engagement']:.4f}\n")
        
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
    
    print(f"✅ Clean keyword map generated successfully!")
    print(f"📍 Output: {output_file}")
    print(f"📊 Total meaningful keywords: {len(final_keywords)}")
    if final_keywords:
        print(f"🏆 Top keyword: '{final_keywords[0]['keyword']}' (Score: {final_keywords[0]['score']:.4f})")
    
    return output_file

if __name__ == "__main__":
    try:
        output_file = generate_keyword_map()
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