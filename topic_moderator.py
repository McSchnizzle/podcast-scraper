#!/usr/bin/env python3
"""
Topic Moderator - Review and Manage Topic Assignments
CLI tool for reviewing and adjusting topic assignments before digest generation
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from utils.datetime_utils import now_utc
from utils.logging_setup import configure_logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from openai_scorer import OpenAITopicScorer
import argparse

configure_logging()
logger = logging.getLogger(__name__)

class TopicModerator:
    """
    Interface for reviewing and managing topic assignments
    """
    
    RELEVANCE_THRESHOLD = 0.6  # Minimum score to include in topic digest
    
    def __init__(self):
        self.databases = {
            'RSS': 'podcast_monitor.db',
            'YouTube': 'youtube_transcripts.db'
        }
        self.scorer = OpenAITopicScorer()
    
    def get_episodes_pending_digest(self, days_back: int = 7) -> Dict[str, List[Dict]]:
        """
        Get episodes that are ready for digest (transcribed but not digested)
        """
        cutoff_date = now_utc() - timedelta(days=days_back)
        all_episodes = {'RSS': [], 'YouTube': []}
        
        for db_type, db_path in self.databases.items():
            if not os.path.exists(db_path):
                logger.warning(f"Database not found: {db_path}")
                continue
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get transcribed episodes that haven't been digested
                cursor.execute("""
                    SELECT e.id, e.episode_id, e.title, e.published_date, e.transcript_path,
                           e.topic_relevance_json, e.digest_topic, e.status, f.title as feed_title
                    FROM episodes e
                    LEFT JOIN feeds f ON e.feed_id = f.id
                    WHERE e.status = 'transcribed' 
                    AND e.topic_relevance_json IS NOT NULL
                    AND e.topic_relevance_json != ''
                    AND (e.published_date IS NULL OR e.published_date >= ?)
                    ORDER BY e.published_date DESC, e.id DESC
                """, (cutoff_date.isoformat(),))
                
                episodes = []
                for row in cursor.fetchall():
                    db_id, episode_id, title, pub_date, transcript_path, scores_json, digest_topic, status, feed_title = row
                    
                    try:
                        scores = json.loads(scores_json) if scores_json else {}
                        
                        # Find the top topic and score
                        topic_scores = {}
                        for topic in ['AI News', 'Tech Product Releases', 'Tech News and Tech Culture', 'Community Organizing', 'Social Justice', 'Societal Culture Change']:
                            if topic in scores and isinstance(scores[topic], (int, float)):
                                topic_scores[topic] = scores[topic]
                        
                        if not topic_scores:
                            continue
                            
                        # Get the highest scoring topic
                        top_topic = max(topic_scores.items(), key=lambda x: x[1])
                        
                        episode_data = {
                            'db_id': db_id,
                            'episode_id': episode_id,
                            'title': title,
                            'feed_title': feed_title,
                            'published_date': pub_date,
                            'transcript_path': transcript_path,
                            'scores': scores,
                            'topic_scores': topic_scores,
                            'top_topic': top_topic[0],
                            'top_score': top_topic[1],
                            'digest_topic': digest_topic,
                            'status': status,
                            'qualifies': top_topic[1] >= self.RELEVANCE_THRESHOLD,
                            'moderation_flag': scores.get('moderation_flag', False),
                            'db_type': db_type
                        }
                        episodes.append(episode_data)
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Error parsing scores for episode {episode_id}: {e}")
                        continue
                
                all_episodes[db_type] = episodes
                conn.close()
                
            except Exception as e:
                logger.error(f"Error querying {db_path}: {e}")
                continue
        
        return all_episodes
    
    def display_episodes_by_topic(self, episodes_data: Dict[str, List[Dict]]):
        """
        Display episodes organized by their predicted topic
        """
        # Combine all episodes and organize by topic
        all_episodes = []
        for db_type, episodes in episodes_data.items():
            all_episodes.extend(episodes)
        
        # Group by topic
        topics = {}
        flagged_episodes = []
        
        for episode in all_episodes:
            if episode['moderation_flag']:
                flagged_episodes.append(episode)
                continue
                
            if not episode['qualifies']:
                continue
                
            topic = episode['top_topic']
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(episode)
        
        # Display results
        print("\n" + "="*80)
        print("EPISODES PENDING DIGEST REVIEW")
        print("="*80)
        
        total_qualifying = sum(len(eps) for eps in topics.values())
        total_episodes = len(all_episodes)
        
        print(f"Found {total_episodes} transcribed episodes")
        print(f"{total_qualifying} episodes qualify for digest (≥{self.RELEVANCE_THRESHOLD} relevance)")
        print(f"{len(flagged_episodes)} episodes flagged for moderation review")
        
        # Show episodes by topic
        for topic in ['AI News', 'Tech Product Releases', 'Tech News and Tech Culture', 'Community Organizing', 'Social Justice', 'Societal Culture Change']:
            if topic not in topics:
                continue
                
            episodes = topics[topic]
            print(f"\n📂 {topic.upper()} ({len(episodes)} episodes)")
            print("-" * 60)
            
            # Sort by score descending
            episodes.sort(key=lambda x: x['top_score'], reverse=True)
            
            for i, episode in enumerate(episodes, 1):
                status_icon = "✅" if episode.get('digest_topic') else "⏳"
                score_display = f"[{episode['top_score']:.2f}]"
                
                # Show top 2 topics if there are close scores
                other_topics = []
                for t, s in episode['topic_scores'].items():
                    if t != episode['top_topic'] and s >= 0.4:
                        other_topics.append(f"{t}:{s:.2f}")
                
                other_display = f" (also: {', '.join(other_topics)})" if other_topics else ""
                
                print(f"{i:2}. {status_icon} {score_display} \"{episode['title'][:50]}{'...' if len(episode['title']) > 50 else ''}\"")
                print(f"     {episode['db_type']} | {episode['feed_title'] or 'Unknown Feed'}{other_display}")
                print(f"     ID: {episode['episode_id']}")
                print()
        
        # Show flagged episodes
        if flagged_episodes:
            print(f"\n🚨 MODERATION REVIEW REQUIRED ({len(flagged_episodes)} episodes)")
            print("-" * 60)
            for episode in flagged_episodes:
                reason = episode['scores'].get('moderation_reason', 'Unknown')
                print(f"⚠️  \"{episode['title'][:50]}\" - {reason}")
                print(f"     ID: {episode['episode_id']}")
                print()
        
        return topics, flagged_episodes
    
    def reassign_episode_topic(self, episode_id: str, new_topic: str, db_type: str = None) -> bool:
        """
        Manually reassign an episode to a different topic
        """
        if new_topic not in ['AI News', 'Tech Product Releases', 'Tech News and Tech Culture', 'Community Organizing', 'Social Justice', 'Societal Culture Change', 'EXCLUDE']:
            print(f"❌ Invalid topic: {new_topic}")
            print("Valid topics: AI News, Tech Product Releases, Tech News and Tech Culture, Community Organizing, Social Justice, Societal Culture Change, EXCLUDE")
            return False
        
        # Try both databases if db_type not specified
        databases_to_try = []
        if db_type:
            if db_type.upper() in self.databases:
                databases_to_try = [(db_type.upper(), self.databases[db_type.upper()])]
            else:
                print(f"❌ Invalid database type: {db_type}")
                return False
        else:
            databases_to_try = list(self.databases.items())
        
        for db_name, db_path in databases_to_try:
            if not os.path.exists(db_path):
                continue
                
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check if episode exists
                cursor.execute("SELECT id, title, topic_relevance_json FROM episodes WHERE episode_id = ?", (episode_id,))
                result = cursor.fetchone()
                
                if result:
                    db_id, title, scores_json = result
                    
                    # Update the digest_topic assignment
                    if new_topic == 'EXCLUDE':
                        cursor.execute("UPDATE episodes SET digest_topic = NULL WHERE id = ?", (db_id,))
                        print(f"✅ Episode excluded from digest: \"{title[:50]}\"")
                    else:
                        cursor.execute("UPDATE episodes SET digest_topic = ? WHERE id = ?", (new_topic, db_id))
                        print(f"✅ Episode reassigned to {new_topic}: \"{title[:50]}\"")
                    
                    conn.commit()
                    conn.close()
                    return True
                
                conn.close()
                
            except Exception as e:
                logger.error(f"Error updating episode {episode_id} in {db_path}: {e}")
                continue
        
        print(f"❌ Episode {episode_id} not found in any database")
        return False
    
    def approve_topic_assignments(self, topic: str = None) -> int:
        """
        Approve episodes for digest generation by setting digest_topic
        """
        approved_count = 0
        
        for db_name, db_path in self.databases.items():
            if not os.path.exists(db_path):
                continue
                
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                if topic:
                    # Approve specific topic
                    cursor.execute("""
                        UPDATE episodes 
                        SET digest_topic = ?
                        WHERE status = 'transcribed' 
                        AND topic_relevance_json IS NOT NULL
                        AND digest_topic IS NULL
                        AND JSON_EXTRACT(topic_relevance_json, '$.' || ?) >= ?
                    """, (topic, topic, self.RELEVANCE_THRESHOLD))
                else:
                    # Approve all qualifying episodes
                    cursor.execute("""
                        SELECT id, episode_id, topic_relevance_json 
                        FROM episodes 
                        WHERE status = 'transcribed' 
                        AND topic_relevance_json IS NOT NULL
                        AND digest_topic IS NULL
                    """)
                    
                    episodes_to_approve = cursor.fetchall()
                    for db_id, episode_id, scores_json in episodes_to_approve:
                        try:
                            scores = json.loads(scores_json)
                            
                            # Find best topic
                            best_topic = None
                            best_score = 0
                            
                            for t in ['AI News', 'Tech Product Releases', 'Tech News and Tech Culture', 'Community Organizing', 'Social Justice', 'Societal Culture Change']:
                                if t in scores and isinstance(scores[t], (int, float)):
                                    if scores[t] > best_score and scores[t] >= self.RELEVANCE_THRESHOLD:
                                        best_topic = t
                                        best_score = scores[t]
                            
                            if best_topic and not scores.get('moderation_flag', False):
                                cursor.execute("UPDATE episodes SET digest_topic = ? WHERE id = ?", (best_topic, db_id))
                        
                        except (json.JSONDecodeError, KeyError):
                            continue
                
                changes = cursor.rowcount
                approved_count += changes
                conn.commit()
                conn.close()
                
                if changes > 0:
                    topic_str = f" for {topic}" if topic else ""
                    print(f"✅ Approved {changes} episodes{topic_str} in {db_name} database")
                
            except Exception as e:
                logger.error(f"Error approving episodes in {db_path}: {e}")
                continue
        
        return approved_count
    
    def show_episode_details(self, episode_id: str):
        """
        Show detailed information about a specific episode
        """
        for db_name, db_path in self.databases.items():
            if not os.path.exists(db_path):
                continue
                
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT e.episode_id, e.title, e.published_date, e.transcript_path,
                           e.topic_relevance_json, e.digest_topic, e.status, f.title as feed_title
                    FROM episodes e
                    LEFT JOIN feeds f ON e.feed_id = f.id
                    WHERE e.episode_id = ?
                """, (episode_id,))
                
                result = cursor.fetchone()
                if result:
                    episode_id, title, pub_date, transcript_path, scores_json, digest_topic, status, feed_title = result
                    
                    print(f"\n📄 EPISODE DETAILS")
                    print("=" * 60)
                    print(f"ID: {episode_id}")
                    print(f"Title: {title}")
                    print(f"Feed: {feed_title}")
                    print(f"Published: {pub_date}")
                    print(f"Status: {status}")
                    print(f"Assigned Topic: {digest_topic or 'None'}")
                    print(f"Database: {db_name}")
                    
                    if scores_json:
                        try:
                            scores = json.loads(scores_json)
                            print(f"\n📊 TOPIC RELEVANCE SCORES:")
                            
                            # Sort topics by score
                            topic_scores = []
                            for topic in ['AI News', 'Tech Product Releases', 'Tech News and Tech Culture', 'Community Organizing', 'Social Justice', 'Societal Culture Change']:
                                if topic in scores and isinstance(scores[topic], (int, float)):
                                    topic_scores.append((topic, scores[topic]))
                            
                            topic_scores.sort(key=lambda x: x[1], reverse=True)
                            
                            for topic, score in topic_scores:
                                status_icon = "✅" if score >= self.RELEVANCE_THRESHOLD else "❌"
                                print(f"  {status_icon} {topic}: {score:.2f}")
                            
                            if scores.get('moderation_flag'):
                                print(f"\n🚨 MODERATION FLAG: {scores.get('moderation_reason', 'Unknown reason')}")
                            
                            print(f"\nModel: {scores.get('model', 'unknown')}")
                            print(f"Confidence: {scores.get('confidence', 'unknown')}")
                            print(f"Reasoning: {scores.get('reasoning', 'N/A')}")
                            
                        except json.JSONDecodeError:
                            print("❌ Invalid scores data")
                    
                    # Show transcript preview if available
                    if transcript_path and os.path.exists(transcript_path):
                        try:
                            with open(transcript_path, 'r') as f:
                                transcript_preview = f.read()[:500]
                            print(f"\n📝 TRANSCRIPT PREVIEW:")
                            print("-" * 40)
                            print(transcript_preview + "..." if len(transcript_preview) == 500 else transcript_preview)
                        except:
                            print("❌ Could not read transcript file")
                    
                    conn.close()
                    return True
                
                conn.close()
                
            except Exception as e:
                logger.error(f"Error getting episode details from {db_path}: {e}")
                continue
        
        print(f"❌ Episode {episode_id} not found")
        return False


def main():
    parser = argparse.ArgumentParser(description='Topic Moderator - Review and manage episode topic assignments')
    parser.add_argument('--review', action='store_true', help='Review episodes pending digest')
    parser.add_argument('--reassign', nargs=2, metavar=('EPISODE_ID', 'TOPIC'), 
                       help='Reassign episode to topic (Technology, Business, Philosophy, Politics, Culture, EXCLUDE)')
    parser.add_argument('--approve', nargs='?', const='all', metavar='TOPIC',
                       help='Approve episodes for digest (all or specific topic)')
    parser.add_argument('--details', metavar='EPISODE_ID', help='Show detailed episode information')
    parser.add_argument('--days', type=int, default=7, help='Days back to look for episodes (default: 7)')
    
    args = parser.parse_args()
    
    moderator = TopicModerator()
    
    if args.review:
        episodes_data = moderator.get_episodes_pending_digest(args.days)
        topics, flagged = moderator.display_episodes_by_topic(episodes_data)
        
        print("\n" + "="*80)
        print("MODERATION COMMANDS:")
        print("="*80)
        print("python topic_moderator.py --reassign <episode_id> <topic>")
        print("python topic_moderator.py --approve [topic]")
        print("python topic_moderator.py --details <episode_id>")
        print("python topic_moderator.py --exclude <episode_id>")
        print("\nValid topics: AI News, Tech Product Releases, Tech News and Tech Culture, Community Organizing, Social Justice, Societal Culture Change, EXCLUDE")
    
    elif args.reassign:
        episode_id, topic = args.reassign
        moderator.reassign_episode_topic(episode_id, topic)
    
    elif args.approve:
        if args.approve == 'all':
            approved = moderator.approve_topic_assignments()
            print(f"✅ Approved {approved} episodes total for digest generation")
        else:
            approved = moderator.approve_topic_assignments(args.approve)
            print(f"✅ Approved {approved} {args.approve} episodes for digest generation")
    
    elif args.details:
        moderator.show_episode_details(args.details)
    
    else:
        print("Topic Moderator - Review and manage episode topic assignments")
        print("\nUsage:")
        print("  python topic_moderator.py --review           # Review pending episodes")
        print("  python topic_moderator.py --approve          # Approve all qualifying episodes")  
        print("  python topic_moderator.py --approve Tech     # Approve Technology episodes only")
        print("  python topic_moderator.py --reassign <id> <topic>  # Reassign episode")
        print("  python topic_moderator.py --details <id>     # Show episode details")


if __name__ == '__main__':
    main()