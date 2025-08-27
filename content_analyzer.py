#!/usr/bin/env python3
"""
Advanced Content Analysis Pipeline
LLM-powered analysis for news extraction, sentiment analysis, and priority scoring
"""

import sqlite3
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
import requests
from pathlib import Path

class ContentAnalyzer:
    def __init__(self, db_path="podcast_monitor.db"):
        self.db_path = db_path
        
        # Priority keywords by category
        self.high_priority_patterns = {
            'product_launches': [
                r'(?i)(launch|announce|release|unveil|introduce)\s+([^.]{1,50})',
                r'(?i)(new product|new feature|now available)\s+([^.]{1,50})',
                r'(?i)(debuts?|premiers?)\s+([^.]{1,50})'
            ],
            'industry_competition': [
                r'(?i)(vs|versus|competes? with|rivals?)\s+([^.]{1,50})',
                r'(?i)(market share|dominance|leader)\s+([^.]{1,50})',
                r'(?i)(acquisition|merger|partnership)\s+([^.]{1,50})'
            ],
            'social_organizing': [
                r'(?i)(organize|mobilize|advocate|campaign)\s+([^.]{1,50})',
                r'(?i)(community building|grassroots|movement)\s+([^.]{1,50})',
                r'(?i)(strategy|tactics|approach)\s+([^.]{1,50})'
            ]
        }
        
        self.sentiment_indicators = {
            'very_positive': ['revolutionary', 'breakthrough', 'game-changing', 'incredible', 'amazing'],
            'positive': ['exciting', 'impressive', 'great', 'significant', 'important'],
            'neutral': ['announces', 'releases', 'discusses', 'explains', 'covers'],
            'negative': ['disappointing', 'concerning', 'problematic', 'issues', 'problems'],
            'very_negative': ['disaster', 'failure', 'terrible', 'awful', 'catastrophic']
        }
    
    def analyze_episode_content(self, transcript: str, topic_category: str, episode_title: str) -> Dict:
        """Comprehensive content analysis with priority scoring"""
        analysis = {
            'priority_score': 0.0,
            'content_type': 'discussion',
            'sentiment': 'neutral',
            'key_topics': [],
            'announcements': [],
            'insights': [],
            'quotes': [],
            'cross_reference_potential': 0.0,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # Extract announcements and key content
        analysis['announcements'] = self._extract_announcements(transcript)
        analysis['insights'] = self._extract_insights(transcript, topic_category)
        analysis['quotes'] = self._extract_key_quotes(transcript)
        analysis['key_topics'] = self._extract_topics(transcript, episode_title)
        
        # Analyze sentiment
        analysis['sentiment'] = self._analyze_sentiment(transcript)
        
        # Determine content type
        analysis['content_type'] = self._classify_content_type(transcript, episode_title)
        
        # Calculate priority score
        analysis['priority_score'] = self._calculate_priority_score(
            transcript, topic_category, analysis
        )
        
        # Assess cross-reference potential
        analysis['cross_reference_potential'] = self._assess_cross_reference_potential(
            analysis['key_topics'], analysis['announcements']
        )
        
        return analysis
    
    def _extract_announcements(self, transcript: str) -> List[Dict]:
        """Extract product launches and announcements"""
        announcements = []
        
        for category, patterns in self.high_priority_patterns.items():
            if category == 'product_launches':
                for pattern in patterns:
                    matches = re.finditer(pattern, transcript)
                    for match in matches:
                        context = self._get_context_around_match(transcript, match.start(), match.end())
                        announcements.append({
                            'type': 'product_launch',
                            'text': match.group(0),
                            'context': context,
                            'confidence': 0.8
                        })
        
        # Look for specific announcement indicators
        announcement_indicators = [
            r'(?i)today we\'re (announcing|launching|releasing)\s+([^.]{1,100})',
            r'(?i)excited to (announce|share|introduce)\s+([^.]{1,100})',
            r'(?i)(available now|now available|just launched)\s+([^.]{1,100})'
        ]
        
        for pattern in announcement_indicators:
            matches = re.finditer(pattern, transcript)
            for match in matches:
                context = self._get_context_around_match(transcript, match.start(), match.end())
                announcements.append({
                    'type': 'announcement',
                    'text': match.group(0),
                    'context': context,
                    'confidence': 0.9
                })
        
        return announcements
    
    def _extract_insights(self, transcript: str, topic_category: str) -> List[Dict]:
        """Extract actionable insights based on topic category"""
        insights = []
        
        if topic_category == 'social_change':
            insight_patterns = [
                r'(?i)(the key is|the secret is|what works is)\s+([^.]{1,150})',
                r'(?i)(we learned that|we discovered|we found)\s+([^.]{1,150})',
                r'(?i)(the strategy is|the approach is|the method is)\s+([^.]{1,150})'
            ]
        else:
            insight_patterns = [
                r'(?i)(the impact is|this means|the significance is)\s+([^.]{1,150})',
                r'(?i)(what this tells us|this suggests|this indicates)\s+([^.]{1,150})',
                r'(?i)(the takeaway is|the lesson is|the key point is)\s+([^.]{1,150})'
            ]
        
        for pattern in insight_patterns:
            matches = re.finditer(pattern, transcript)
            for match in matches:
                context = self._get_context_around_match(transcript, match.start(), match.end())
                insights.append({
                    'text': match.group(0),
                    'context': context,
                    'category': topic_category,
                    'confidence': 0.7
                })
        
        return insights
    
    def _extract_key_quotes(self, transcript: str) -> List[Dict]:
        """Extract memorable and quotable content"""
        quotes = []
        
        # Look for emphatic statements
        quote_patterns = [
            r'(?i)(this is huge|this is big|this is important)\s*[:.]\s*([^.]{1,200})',
            r'(?i)(the reality is|the truth is|the fact is)\s*[:.]\s*([^.]{1,200})',
            r'(?i)(what we\'re seeing is|what\'s happening is)\s*([^.]{1,200})'
        ]
        
        for pattern in quote_patterns:
            matches = re.finditer(pattern, transcript)
            for match in matches:
                full_quote = match.group(0)
                quotes.append({
                    'text': full_quote,
                    'type': 'emphatic_statement',
                    'length': len(full_quote),
                    'confidence': 0.8
                })
        
        return quotes
    
    def _extract_topics(self, transcript: str, episode_title: str) -> List[str]:
        """Extract key topics from transcript and title"""
        topics = []
        
        # Extract from title
        title_topics = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', episode_title)
        topics.extend(title_topics)
        
        # Extract company/product names (capitalized words)
        company_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b'
        companies = re.findall(company_pattern, transcript)
        
        # Filter out common words
        common_words = {'The', 'This', 'That', 'They', 'We', 'You', 'And', 'But', 'Or', 'So', 'Now', 'Then'}
        filtered_companies = [c for c in companies if c not in common_words]
        
        # Get top mentioned entities
        from collections import Counter
        topic_counts = Counter(filtered_companies)
        topics.extend([topic for topic, count in topic_counts.most_common(10) if count > 1])
        
        return list(set(topics))  # Remove duplicates
    
    def _analyze_sentiment(self, transcript: str) -> str:
        """Analyze overall sentiment of content"""
        transcript_lower = transcript.lower()
        
        sentiment_scores = {
            'very_positive': 0,
            'positive': 0,
            'neutral': 0,
            'negative': 0,
            'very_negative': 0
        }
        
        for sentiment, keywords in self.sentiment_indicators.items():
            for keyword in keywords:
                sentiment_scores[sentiment] += transcript_lower.count(keyword)
        
        # Find dominant sentiment
        max_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        
        # If no clear sentiment, default to neutral
        if sentiment_scores[max_sentiment] == 0:
            return 'neutral'
        
        # Map to simplified sentiment
        sentiment_mapping = {
            'very_positive': 'very_positive',
            'positive': 'positive',
            'neutral': 'neutral',
            'negative': 'negative',
            'very_negative': 'negative'
        }
        
        return sentiment_mapping.get(max_sentiment, 'neutral')
    
    def _classify_content_type(self, transcript: str, episode_title: str) -> str:
        """Classify the type of content"""
        transcript_lower = transcript.lower()
        title_lower = episode_title.lower()
        
        # Check for interviews
        interview_indicators = ['interview', 'conversation', 'chat with', 'talking to', 'guest']
        if any(indicator in transcript_lower or indicator in title_lower for indicator in interview_indicators):
            return 'interview'
        
        # Check for announcements
        announcement_indicators = ['announce', 'launch', 'release', 'unveil', 'introduce']
        if any(indicator in transcript_lower for indicator in announcement_indicators):
            return 'announcement'
        
        # Check for analysis/opinion
        analysis_indicators = ['analysis', 'opinion', 'review', 'breakdown', 'deep dive']
        if any(indicator in transcript_lower or indicator in title_lower for indicator in analysis_indicators):
            return 'analysis'
        
        return 'discussion'
    
    def _calculate_priority_score(self, transcript: str, topic_category: str, analysis: Dict) -> float:
        """Calculate comprehensive priority score (0.0 - 1.0)"""
        score = 0.0
        
        # Base score from announcements
        announcement_score = len(analysis['announcements']) * 0.2
        score += min(announcement_score, 0.6)
        
        # Sentiment multiplier
        sentiment_multipliers = {
            'very_positive': 1.3,
            'positive': 1.1,
            'neutral': 1.0,
            'negative': 0.8,
            'very_negative': 0.6
        }
        sentiment_multiplier = sentiment_multipliers.get(analysis['sentiment'], 1.0)
        
        # Content type bonus
        content_type_bonuses = {
            'announcement': 0.3,
            'interview': 0.2,
            'analysis': 0.15,
            'discussion': 0.1
        }
        score += content_type_bonuses.get(analysis['content_type'], 0.0)
        
        # Topic-specific scoring
        if topic_category == 'tech_news':
            tech_keywords = ['AI', 'artificial intelligence', 'machine learning', 'startup', 'venture capital']
            tech_score = sum(1 for keyword in tech_keywords if keyword.lower() in transcript.lower()) * 0.1
            score += min(tech_score, 0.3)
        
        elif topic_category == 'social_change':
            social_keywords = ['organize', 'movement', 'community', 'action', 'change', 'advocacy']
            social_score = sum(1 for keyword in social_keywords if keyword.lower() in transcript.lower()) * 0.1
            score += min(social_score, 0.3)
        
        # Apply sentiment multiplier
        score *= sentiment_multiplier
        
        # Ensure score is within bounds
        return min(max(score, 0.0), 1.0)
    
    def _assess_cross_reference_potential(self, topics: List[str], announcements: List[Dict]) -> float:
        """Assess potential for cross-referencing with other episodes"""
        # This is a placeholder for cross-reference detection
        # In a full implementation, this would compare against other episodes
        
        # Higher score for topics that commonly appear across sources
        common_cross_ref_topics = [
            'AI', 'OpenAI', 'Google', 'Apple', 'Microsoft', 'Meta', 
            'climate change', 'election', 'policy', 'regulation'
        ]
        
        cross_ref_score = 0.0
        for topic in topics:
            for common_topic in common_cross_ref_topics:
                if common_topic.lower() in topic.lower():
                    cross_ref_score += 0.1
        
        # Boost for multiple announcements (likely to be covered elsewhere)
        if len(announcements) > 1:
            cross_ref_score += 0.2
        
        return min(cross_ref_score, 1.0)
    
    def _get_context_around_match(self, text: str, start: int, end: int, context_chars: int = 200) -> str:
        """Get context around a regex match"""
        context_start = max(0, start - context_chars)
        context_end = min(len(text), end + context_chars)
        return text[context_start:context_end].strip()
    
    def analyze_cross_references(self, min_priority: float = 0.4) -> List[Dict]:
        """Find topics that appear across multiple high-priority episodes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all processed episodes above threshold
        cursor.execute('''
            SELECT e.id, e.title, e.transcript_path, e.priority_score, 
                   f.title as feed_title, f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.status IN ('transcribed', 'digested') AND e.priority_score >= ?
            ORDER BY e.published_date DESC
        ''', (min_priority,))
        
        episodes = cursor.fetchall()
        conn.close()
        
        if len(episodes) < 2:
            return []
        
        # Simple topic overlap detection (would be enhanced with vector similarity)
        topic_episodes = {}
        
        for ep_id, title, transcript_path, priority, feed_title, category in episodes:
            if transcript_path and Path(transcript_path).exists():
                # Read transcript for topic extraction
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                
                # Extract topics from this episode
                topics = self._extract_topics(transcript, title)
                
                for topic in topics:
                    if topic not in topic_episodes:
                        topic_episodes[topic] = []
                    topic_episodes[topic].append({
                        'episode_id': ep_id,
                        'title': title,
                        'feed_title': feed_title,
                        'category': category,
                        'priority': priority
                    })
        
        # Find topics appearing in multiple episodes
        cross_references = []
        for topic, episodes_list in topic_episodes.items():
            if len(episodes_list) > 1:
                # Calculate cross-reference strength
                total_priority = sum(ep['priority'] for ep in episodes_list)
                avg_priority = total_priority / len(episodes_list)
                
                cross_references.append({
                    'topic': topic,
                    'episode_count': len(episodes_list),
                    'episodes': episodes_list,
                    'strength': avg_priority * len(episodes_list),
                    'categories': list(set(ep['category'] for ep in episodes_list))
                })
        
        # Sort by strength
        cross_references.sort(key=lambda x: x['strength'], reverse=True)
        return cross_references
    
    def generate_content_summary(self, episode_ids: List[int], max_length: int = 1000) -> Dict:
        """Generate a summary of content from multiple episodes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        summaries = []
        total_priority = 0.0
        topics_covered = set()
        
        for episode_id in episode_ids:
            cursor.execute('''
                SELECT e.title, e.transcript_path, e.priority_score, e.content_type,
                       f.title as feed_title, f.topic_category
                FROM episodes e
                JOIN feeds f ON e.feed_id = f.id
                WHERE e.id = ?
            ''', (episode_id,))
            
            episode = cursor.fetchone()
            if not episode:
                continue
            
            title, transcript_path, priority, content_type, feed_title, category = episode
            
            # Analyze this episode
            if transcript_path and Path(transcript_path).exists():
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                
                analysis = self.analyze_episode_content(transcript, category, title)
                
                # Extract top insights and announcements
                top_content = []
                top_content.extend(analysis['announcements'][:2])  # Top 2 announcements
                top_content.extend(analysis['insights'][:2])      # Top 2 insights
                
                summaries.append({
                    'episode_title': title,
                    'feed_title': feed_title,
                    'category': category,
                    'priority': priority,
                    'content_type': content_type,
                    'key_content': top_content,
                    'topics': analysis['key_topics'][:5]  # Top 5 topics
                })
                
                total_priority += priority
                topics_covered.update(analysis['key_topics'][:5])
        
        conn.close()
        
        # Calculate aggregate metrics
        avg_priority = total_priority / len(summaries) if summaries else 0.0
        
        return {
            'episode_count': len(summaries),
            'average_priority': avg_priority,
            'total_topics': len(topics_covered),
            'topics_covered': list(topics_covered),
            'summaries': summaries,
            'generated_at': datetime.now().isoformat()
        }
    
    def get_daily_digest_content(self, min_priority: float = 0.4) -> Dict:
        """Get content for daily digest generation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent high-priority episodes
        cursor.execute('''
            SELECT e.id, e.title, e.priority_score, e.content_type,
                   f.title as feed_title, f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.status IN ('transcribed', 'digested') 
            AND e.priority_score >= ?
            AND date(e.published_date) >= date('now', '-1 day')
            ORDER BY e.priority_score DESC
        ''', (min_priority,))
        
        episodes = cursor.fetchall()
        conn.close()
        
        if not episodes:
            return {'episodes': [], 'cross_references': [], 'summary': None}
        
        episode_ids = [ep[0] for ep in episodes]
        
        # Generate content summary
        summary = self.generate_content_summary(episode_ids)
        
        # Find cross-references
        cross_refs = self.analyze_cross_references(min_priority)
        
        return {
            'episodes': episodes,
            'cross_references': cross_refs[:5],  # Top 5 cross-references
            'summary': summary
        }

def main():
    """CLI interface for content analysis"""
    analyzer = ContentAnalyzer()
    
    print("Daily Podcast Digest - Content Analyzer")
    print("=======================================")
    
    # Test with a sample episode
    conn = sqlite3.connect("podcast_monitor.db")
    cursor = conn.cursor()
    
    # Get first processed episode for testing
    cursor.execute('''
        SELECT e.id, e.transcript_path, e.title, f.topic_category
        FROM episodes e
        JOIN feeds f ON e.feed_id = f.id
        WHERE e.transcript_path IS NOT NULL
        LIMIT 1
    ''')
    
    episode = cursor.fetchone()
    if episode:
        ep_id, transcript_path, title, category = episode
        
        if transcript_path and Path(transcript_path).exists():
            print(f"Analyzing: {title}")
            
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            
            analysis = analyzer.analyze_episode_content(transcript, category, title)
            
            print(f"\nAnalysis Results:")
            print(f"Priority Score: {analysis['priority_score']:.2f}")
            print(f"Content Type: {analysis['content_type']}")
            print(f"Sentiment: {analysis['sentiment']}")
            print(f"Key Topics: {', '.join(analysis['key_topics'][:5])}")
            print(f"Announcements: {len(analysis['announcements'])}")
            print(f"Insights: {len(analysis['insights'])}")
            print(f"Cross-Ref Potential: {analysis['cross_reference_potential']:.2f}")
        else:
            print("No transcript available for testing")
    else:
        print("No processed episodes available for testing")
    
    conn.close()
    
    # Show daily digest preview
    print("\n" + "="*50)
    print("Daily Digest Content Preview")
    print("="*50)
    
    digest_content = analyzer.get_daily_digest_content()
    
    if digest_content['episodes']:
        print(f"Found {len(digest_content['episodes'])} high-priority episodes")
        
        for ep in digest_content['episodes'][:3]:  # Show top 3
            print(f"  🎯 {ep[1]} (Priority: {ep[2]:.2f})")
            print(f"     Source: {ep[4]} | Type: {ep[3]}")
        
        if digest_content['cross_references']:
            print(f"\nCross-references found: {len(digest_content['cross_references'])}")
            for ref in digest_content['cross_references'][:2]:
                print(f"  🔗 {ref['topic']} (appears in {ref['episode_count']} episodes)")
    else:
        print("No high-priority content found for digest")

if __name__ == "__main__":
    main()