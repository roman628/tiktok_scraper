# Comprehensive Stopword Analysis for TikTok Content Keyword Scoring

## Executive Summary

This research provides a comprehensive analysis of stopword filtering techniques for TikTok content analysis, including extended stopword lists, keyword extraction methods, and platform-specific considerations. The goal is to optimize keyword extraction by removing noise words while preserving meaningful content indicators.

## 1. Standard Stopword Libraries Comparison

### Library Comparison (2024)
- **NLTK**: 179 English stopwords (baseline set)
- **spaCy**: More comprehensive than NLTK, includes contractions like 'n't', ''d', ''s'
- **Gensim**: 337 stopwords (largest set), includes domain-specific terms

### Key Differences
- **Gensim Extra Words**: 'hasnt', 'thick', 'interest', 'eg', 'computer', 'couldnt', 'co', 'system', 'bill', 'kg', 'mill', 'un', 'don', 'thin', 'detail', 'de', 'found', 'cry', 'ltd', 'find', 'etc', 'inc', 'fire', 'con', 'cant', 'doesn', 'fill', 'amoungst', 'ie', 'describe', 'km', 'sincere'
- **spaCy Contractions**: "'d", ''d', "'s", "'re", 'n't', ''d', ''m', ''m', "'m", 'n't', ''re', ''ll', ''re', "'ll", "'ve", "n't", ''s', ''s', ''ve', ''ll', 'ca', ''ve'

## 2. TikTok-Specific Stopwords

### Platform Terms
- **FYP/FVP**: "For You Page" 
- **POV**: "Point of View"
- **GRWM**: "Get ready with me"
- **IYKYK**: "If you know you know"
- **OOTD**: "Outfit of the day"
- **NPC**: "Non playable character"
- **NSFW**: "Not safe for work"
- **CEO**: "CEO of [something]" (meaning best at something)

### Contemporary Slang (2024-2025)
- **brain rot**: Low-quality content consumption
- **brat**: Cultural phenomenon from Charli XCX
- **demure**: Being mindful and subtle
- **delulu**: Delusional/unreasonably optimistic
- **rizz**: Ability to flirt/attract
- **skibidi**: Bad or evil (Gen Alpha slang)
- **periodt**: Definitive statement closer
- **bestie**: Friend or formal address
- **sus**: Suspicious
- **dead/💀**: Extremely funny
- **gyat**: Appreciating body shape
- **heather**: The "it girl"

### Algospeak/Censorship Avoidance
- **unalive**: Dead/killed
- **seggs**: Sex
- **SA**: Sexual assault
- **spicy eggplant**: Vibrator
- **nip nops**: Nipples
- **cornucopia**: Homophobia
- **leg booty**: LGBTQ community
- **le$bian, g@y, qu3er**: LGBTQ terms with symbols
- **dis@bled, 80HD**: Disabled, ADHD
- **TigTog, Clock App**: TikTok platform references

### Common Abbreviations
- **BDE**: Big Dick Energy
- **L**: Loss
- **W**: Win
- **TFW**: That feeling when
- **MFW**: My face when
- **OOMF**: One of my followers/friends

## 3. Social Media Noise Words

### Platform References
- tiktok, instagram, twitter, facebook, youtube
- app, platform, social, media
- post, share, like, follow, comment
- viral, trend, trending, algorithm

### Technical Terms
- hashtag, tag, mention, handle
- retweet, rt, dm, pm
- story, reel, video, clip
- live, stream, broadcast

### Engagement Terms
- smash, hit, bang, fire (when used as generic intensifiers)
- literally, basically, actually (overused qualifiers)
- random, weird, crazy (non-specific descriptors)

## 4. Extended Stopword Categories

### Short Words (≤2 characters)
- All single letters: a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z
- Common two-letter words: an, as, at, be, by, do, go, he, if, in, is, it, me, my, no, of, on, or, so, to, up, us, we

### Filler Words
- like, um, uh, er, ah, well, you know, I mean
- basically, literally, actually, obviously, definitely
- really, very, quite, pretty, kinda, sorta

### Temporal References (Low Content Value)
- today, yesterday, tomorrow, now, then, later
- morning, afternoon, evening, night
- monday, tuesday, wednesday, thursday, friday, saturday, sunday

## 5. Keyword Extraction Method Analysis

### RAKE (Rapid Automatic Keyword Extraction)
- **Best for**: Multi-word phrases and compound terms
- **Mechanism**: Uses stopwords as delimiters to identify candidate phrases
- **Advantage**: Fast processing, good for social media's short content
- **Limitation**: May extract overly long phrases

### TextRank
- **Best for**: Understanding word relationships and thematic content
- **Mechanism**: Graph-based approach analyzing word co-occurrence
- **Advantage**: Considers semantic relationships between words
- **Limitation**: More computationally intensive

### TF-IDF (Term Frequency-Inverse Document Frequency)
- **Best for**: Identifying unique terms across document collections
- **Mechanism**: Balances word frequency with document uniqueness
- **Advantage**: Well-established, interpretable scores
- **Limitation**: Struggles with very short texts like TikTok captions

### YAKE (Yet Another Keyword Extractor)
- **Best for**: Single document analysis, domain-independent extraction
- **Mechanism**: Statistical features without external corpus dependency
- **Advantage**: Works with individual posts, handles multi-word expressions
- **Limitation**: May miss contextual relationships

## 6. Recommended Stopword Strategy for TikTok

### Core Implementation Approach

1. **Base Library**: Start with spaCy stopwords (most comprehensive contractions)
2. **Platform Enhancement**: Add TikTok-specific terms and slang
3. **Dynamic Updates**: Regular review of emerging slang and algospeak
4. **Context Preservation**: Maintain sentiment-critical words (negations)

### Multi-Tier Filtering Strategy

#### Tier 1: Essential Stopwords (Always Remove)
- Standard grammatical words (articles, prepositions, pronouns)
- Platform navigation terms (fyp, pov, grwm)
- Generic social media engagement words

#### Tier 2: Context-Dependent Stopwords (Conditional Removal)
- Trending slang that may become meaningful keywords
- Brand/influencer names (depending on analysis focus)
- Temporal references (unless time-series analysis)

#### Tier 3: Preserve for Analysis
- Sentiment indicators (not, never, don't, can't)
- Intensity modifiers (very, extremely, totally)
- Emotional expressions (love, hate, amazing, terrible)

### Implementation Code Structure

```python
# Base stopwords from spaCy
base_stopwords = set(spacy.lang.en.stop_words.STOP_WORDS)

# TikTok-specific additions
tiktok_stopwords = {
    'fyp', 'fvp', 'pov', 'grwm', 'iykyk', 'ootd', 'npc', 'nsfw',
    'rizz', 'skibidi', 'delulu', 'demure', 'periodt', 'bestie',
    'unalive', 'seggs', 'gyat', 'sus', 'dead', 'ceo'
}

# Platform noise words
platform_noise = {
    'tiktok', 'instagram', 'twitter', 'app', 'platform',
    'viral', 'trending', 'algorithm', 'hashtag', 'like',
    'follow', 'share', 'comment'
}

# Combine all stopword sets
comprehensive_stopwords = base_stopwords | tiktok_stopwords | platform_noise
```

### Quality Assurance Metrics

1. **Keyword Relevance**: Measure semantic coherence of extracted keywords
2. **Noise Reduction**: Track removal of meaningless terms
3. **Content Preservation**: Ensure important sentiment/topic words remain
4. **Processing Speed**: Optimize for real-time content analysis

## 7. Best Practices for Implementation

### Regular Updates
- Monthly review of emerging TikTok slang
- Quarterly assessment of stopword effectiveness
- Monitoring for new algospeak terms

### A/B Testing Framework
- Compare keyword extraction quality with/without custom stopwords
- Test different algorithms (RAKE vs. YAKE vs. TextRank)
- Measure impact on downstream tasks (sentiment analysis, topic modeling)

### Performance Optimization
- Cache compiled stopword sets for faster processing
- Use set operations for O(1) lookup performance
- Consider memory usage with large custom stopword lists

## 8. Conclusions and Recommendations

1. **Hybrid Approach**: Combine spaCy's comprehensive base with TikTok-specific additions
2. **Algorithmic Choice**: YAKE recommended for single-document TikTok posts, TextRank for relationship analysis
3. **Dynamic Maintenance**: Implement automated monitoring for new slang terms
4. **Context Awareness**: Preserve sentiment-critical terms while removing noise
5. **Performance Balance**: Optimize for both accuracy and processing speed

This comprehensive stopword strategy will significantly improve keyword extraction quality for TikTok content analysis while maintaining the semantic meaning necessary for effective content scoring and trend identification.