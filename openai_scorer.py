#!/usr/bin/env python3
"""
OpenAI Topic Relevance Scorer
Scores podcast episode transcripts against multiple topics using OpenAI's API
"""

import os
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import openai
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAITopicScorer:
    """
    Scores episode transcripts against multiple topics using OpenAI's API
    """
    
    # Core topic definitions with scoring prompts
    TOPICS = {
        'Technology': {
            'description': 'Software, AI, hardware, programming, tech industry, startups, digital trends',
            'prompt': 'technology, software development, artificial intelligence, hardware, programming, tech industry, digital innovation, cybersecurity, data science, cloud computing, mobile technology, emerging tech'
        },
        'Business': {
            'description': 'Finance, economics, markets, entrepreneurship, management, corporate strategy',
            'prompt': 'business strategy, finance, economics, markets, entrepreneurship, management, corporate governance, investment, economics policy, trade, industry analysis'
        },
        'Philosophy': {
            'description': 'Ethics, logic, metaphysics, epistemology, moral philosophy, philosophical debates',
            'prompt': 'philosophy, ethics, moral reasoning, logic, metaphysics, epistemology, philosophical arguments, critical thinking, values, meaning of life, consciousness'
        },
        'Politics': {
            'description': 'Government, policy, elections, international relations, political analysis',
            'prompt': 'politics, government policy, elections, international relations, political analysis, governance, public policy, diplomacy, political theory, current affairs'
        },
        'Culture': {
            'description': 'Arts, entertainment, society, media, lifestyle, cultural trends, human interest',
            'prompt': 'culture, arts, entertainment, society, media, lifestyle, cultural trends, human interest stories, social movements, popular culture, creative expression'
        }
    }
    
    SCORING_SYSTEM_PROMPT = """You are an expert content analyzer. You will score how relevant a podcast episode transcript is to specific topics.

Your task:
1. Read the episode transcript carefully
2. Score relevance from 0.0 to 1.0 for each topic (0.0 = not relevant at all, 1.0 = highly relevant)
3. Also check for content moderation issues

Scoring Guidelines:
- 0.9-1.0: Extremely relevant, core focus of the episode
- 0.7-0.8: Highly relevant, significant portion discusses this topic
- 0.5-0.6: Moderately relevant, some discussion of this topic
- 0.3-0.4: Minimally relevant, brief mentions
- 0.0-0.2: Not relevant or only tangentially mentioned

Content Moderation:
- Flag content that is: harmful, hateful, violent, sexual, illegal, or promotes dangerous activities
- Use the "moderation_flag" field to indicate issues

Return your analysis as a JSON object with this exact structure:
{
    "Technology": 0.X,
    "Business": 0.X,
    "Philosophy": 0.X,
    "Politics": 0.X,
    "Culture": 0.X,
    "moderation_flag": false,
    "moderation_reason": null,
    "confidence": 0.X,
    "reasoning": "Brief explanation of scoring rationale"
}"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            self.client = None
            self.api_available = False
        else:
            try:
                self.client = OpenAI(api_key=api_key)
                self.api_available = True
                logger.info("✅ OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
                self.api_available = False
    
    def score_transcript(self, transcript_text: str, episode_id: str = None) -> Dict[str, Any]:
        """
        Score a single transcript against all topics
        """
        if not self.api_available:
            logger.error("OpenAI API not available")
            return self._create_fallback_scores()
        
        try:
            # Truncate transcript if too long (OpenAI has token limits)
            max_chars = 12000  # ~3000 tokens approx
            if len(transcript_text) > max_chars:
                transcript_text = transcript_text[:max_chars] + "\n\n[TRANSCRIPT TRUNCATED FOR ANALYSIS]"
                logger.warning(f"Transcript truncated for episode {episode_id} (original length: {len(transcript_text)} chars)")
            
            user_prompt = f"""Please analyze this podcast episode transcript and score its relevance to each topic:

TRANSCRIPT:
{transcript_text}

TOPICS TO SCORE:
{json.dumps(self.TOPICS, indent=2)}

Provide scores as requested in the system prompt."""

            logger.info(f"Sending transcript to OpenAI for scoring (episode: {episode_id})")
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective model for analysis
                messages=[
                    {"role": "system", "content": self.SCORING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=500,
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            # Parse the response
            scores_json = response.choices[0].message.content.strip()
            scores = json.loads(scores_json)
            
            # Add metadata
            scores['timestamp'] = datetime.now().isoformat()
            scores['model'] = "gpt-4o-mini"
            scores['version'] = "1.0"
            scores['episode_id'] = episode_id
            
            logger.info(f"✅ Successfully scored episode {episode_id}")
            return scores
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON for episode {episode_id}: {e}")
            return self._create_fallback_scores(episode_id)
            
        except Exception as e:
            logger.error(f"Error scoring transcript for episode {episode_id}: {e}")
            return self._create_fallback_scores(episode_id)
    
    def _create_fallback_scores(self, episode_id: str = None) -> Dict[str, Any]:
        """Create neutral fallback scores when API fails"""
        return {
            'Technology': 0.0,
            'Business': 0.0,
            'Philosophy': 0.0,
            'Politics': 0.0,
            'Culture': 0.0,
            'moderation_flag': False,
            'moderation_reason': None,
            'confidence': 0.0,
            'reasoning': 'API unavailable - fallback scores assigned',
            'timestamp': datetime.now().isoformat(),
            'model': 'fallback',
            'version': '1.0',
            'episode_id': episode_id,
            'error': True
        }
    
    def score_episodes_in_database(self, db_path: str, status_filter: str = 'transcribed') -> int:
        """
        Score all episodes with the specified status in a database
        Returns number of episodes scored
        """
        if not os.path.exists(db_path):
            logger.error(f"Database not found: {db_path}")
            return 0
        
        scored_count = 0
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get episodes that need scoring
            cursor.execute("""
                SELECT id, episode_id, title, transcript_path 
                FROM episodes 
                WHERE status = ? AND transcript_path IS NOT NULL 
                AND (topic_relevance_json IS NULL OR topic_relevance_json = '')
                ORDER BY id DESC
            """, (status_filter,))
            
            episodes = cursor.fetchall()
            logger.info(f"Found {len(episodes)} episodes to score in {db_path}")
            
            for episode_data in episodes:
                db_id, episode_id, title, transcript_path = episode_data
                
                # Read transcript file
                transcript_file = Path(transcript_path)
                if not transcript_file.exists():
                    logger.warning(f"Transcript file not found: {transcript_path}")
                    continue
                
                try:
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_text = f.read()
                    
                    if len(transcript_text.strip()) < 100:
                        logger.warning(f"Transcript too short for episode {episode_id}, skipping")
                        continue
                    
                    # Score the transcript
                    logger.info(f"Scoring episode: {title[:50]}...")
                    scores = self.score_transcript(transcript_text, episode_id)
                    
                    # Store scores in database
                    cursor.execute("""
                        UPDATE episodes 
                        SET topic_relevance_json = ?, scores_version = ?
                        WHERE id = ?
                    """, (json.dumps(scores), scores.get('version', '1.0'), db_id))
                    
                    conn.commit()
                    scored_count += 1
                    
                    # Rate limiting - pause between requests
                    if scored_count % 5 == 0:
                        logger.info(f"Processed {scored_count} episodes, pausing briefly...")
                        time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing episode {episode_id}: {e}")
                    continue
            
            conn.close()
            logger.info(f"✅ Successfully scored {scored_count} episodes in {db_path}")
            return scored_count
            
        except Exception as e:
            logger.error(f"Database error in {db_path}: {e}")
            return 0
    
    def get_episode_scores(self, db_path: str, episode_id: str = None) -> List[Dict[str, Any]]:
        """
        Get topic scores for episodes from database
        """
        if not os.path.exists(db_path):
            logger.error(f"Database not found: {db_path}")
            return []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if episode_id:
                cursor.execute("""
                    SELECT episode_id, title, topic_relevance_json, status 
                    FROM episodes 
                    WHERE episode_id = ?
                """, (episode_id,))
            else:
                cursor.execute("""
                    SELECT episode_id, title, topic_relevance_json, status 
                    FROM episodes 
                    WHERE topic_relevance_json IS NOT NULL AND topic_relevance_json != ''
                    ORDER BY id DESC
                """)
            
            results = []
            for row in cursor.fetchall():
                ep_id, title, scores_json, status = row
                try:
                    scores = json.loads(scores_json) if scores_json else {}
                    results.append({
                        'episode_id': ep_id,
                        'title': title,
                        'status': status,
                        'scores': scores
                    })
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in scores for episode {ep_id}")
                    continue
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving scores from {db_path}: {e}")
            return []


def main():
    """CLI interface for the OpenAI scorer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Score podcast episodes using OpenAI')
    parser.add_argument('--db', type=str, help='Database path')
    parser.add_argument('--score-all', action='store_true', help='Score all unscored episodes')
    parser.add_argument('--view-scores', action='store_true', help='View existing scores')
    parser.add_argument('--episode-id', type=str, help='Score specific episode')
    
    args = parser.parse_args()
    
    scorer = OpenAITopicScorer()
    
    if not scorer.api_available:
        print("❌ OpenAI API not available. Set OPENAI_API_KEY environment variable.")
        return
    
    if args.score_all:
        databases = ['podcast_monitor.db', 'youtube_transcripts.db']
        total_scored = 0
        for db_path in databases:
            if os.path.exists(db_path):
                scored = scorer.score_episodes_in_database(db_path)
                total_scored += scored
                print(f"Scored {scored} episodes in {db_path}")
        print(f"\n✅ Total episodes scored: {total_scored}")
    
    elif args.view_scores:
        databases = ['podcast_monitor.db', 'youtube_transcripts.db']
        for db_path in databases:
            if os.path.exists(db_path):
                scores = scorer.get_episode_scores(db_path)
                print(f"\n{db_path} - {len(scores)} episodes with scores:")
                for episode in scores[:5]:  # Show first 5
                    print(f"  {episode['episode_id']}: {episode['title'][:50]}")
                    top_topics = sorted(episode['scores'].items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)[:2]
                    for topic, score in top_topics:
                        if isinstance(score, (int, float)) and score > 0.3:
                            print(f"    {topic}: {score:.2f}")
    
    elif args.episode_id and args.db:
        scores = scorer.get_episode_scores(args.db, args.episode_id)
        if scores:
            episode = scores[0]
            print(f"Episode: {episode['title']}")
            print(f"Status: {episode['status']}")
            print("Topic Scores:")
            for topic, score in episode['scores'].items():
                if isinstance(score, (int, float)):
                    print(f"  {topic}: {score:.2f}")
        else:
            print(f"Episode {args.episode_id} not found or not scored")
    
    else:
        print("Use --score-all to score episodes or --view-scores to see results")
        print("Example: python openai_scorer.py --score-all")


if __name__ == '__main__':
    main()