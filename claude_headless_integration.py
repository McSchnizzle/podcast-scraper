#!/usr/bin/env python3
"""
Claude Code Headless Integration - Phase 2.75 Implementation
Automated daily digest generation using Claude Code in headless mode
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from utils.datetime_utils import now_utc
from utils.logging_setup import configure_logging
from typing import Dict, List, Optional, Tuple
import sqlite3
import tempfile

configure_logging()
logger = logging.getLogger(__name__)

class ClaudeHeadlessIntegration:
    def __init__(self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        self.claude_cmd = "claude"
        
        # Verify Claude Code availability
        self.claude_available = self._check_claude_availability()

    def _check_claude_availability(self) -> bool:
        """Check if Claude Code CLI is available"""
        try:
            result = subprocess.run([self.claude_cmd, '--help'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Claude Code CLI not available: {e}")
            return False

    def get_transcripts_for_analysis(self) -> List[Dict]:
        """Get transcripts ready for Claude Code analysis"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Only get episodes with status='transcribed' to match pipeline behavior
            query = """
            SELECT id, title, transcript_path, episode_id, published_date, status
            FROM episodes 
            WHERE transcript_path IS NOT NULL 
            AND status = 'transcribed'
            AND published_date >= date('now', '-7 days')
            ORDER BY published_date DESC
            LIMIT 10
            """
            
            logger.info(f"Executing query: {query}")
            cursor.execute(query)
            transcripts = []
            
            all_rows = cursor.fetchall()
            logger.info(f"Query returned {len(all_rows)} rows")
            
            for row in all_rows:
                episode_id, title, transcript_path, episode_id_field, published_date, status = row
                logger.info(f"Processing episode {episode_id}: '{title}' (status: {status}, transcript: {transcript_path})")
                
                if transcript_path and Path(transcript_path).exists():
                    transcripts.append({
                        'id': episode_id,
                        'title': title,
                        'transcript_path': transcript_path,
                        'episode_id': episode_id_field,
                        'published_date': published_date
                    })
                    logger.info(f"✅ Added episode {episode_id} to transcripts list")
                else:
                    logger.warning(f"❌ Transcript file not found for episode {episode_id}: {transcript_path}")
            
            conn.close()
            logger.info(f"Found {len(transcripts)} transcripts for Claude analysis")
            return transcripts
            
        except Exception as e:
            logger.error(f"Error retrieving transcripts: {e}")
            return []

    def prepare_claude_input(self, transcripts: List[Dict]) -> str:
        """Prepare input for Claude Code headless analysis"""
        
        # Create comprehensive input for Claude analysis
        input_parts = []
        
        # Load instructions from file (same as TTS generator)
        try:
            with open('claude_digest_instructions.md', 'r', encoding='utf-8') as f:
                instructions = f.read()
        except Exception as e:
            logger.warning(f"Could not load instructions file: {e}")
            instructions = "Generate a professional daily podcast digest focusing on cross-episode synthesis and optimized for audio consumption."
        
        prompt_header = f"""
You are tasked with creating a professional daily podcast digest. Follow these instructions precisely:

{instructions}

Now analyze the following {len(transcripts)} podcast episodes and CREATE the daily digest. Do not just list requirements - actually write the complete digest following the format specified above.

TRANSCRIPTS TO ANALYZE:
"""
        input_parts.append(prompt_header)
        
        # Add transcript data
        for transcript in transcripts:
            input_parts.append(f"\n=== EPISODE {transcript['id']}: {transcript['title']} ===")
            
            # Load transcript content
            try:
                with open(transcript['transcript_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                # Truncate very long transcripts for token efficiency
                if len(content) > 5000:
                    content = content[:5000] + "\n[CONTENT TRUNCATED FOR ANALYSIS]"
                input_parts.append(content)
            except Exception as e:
                logger.error(f"Error loading transcript {transcript['transcript_path']}: {e}")
                input_parts.append("[TRANSCRIPT NOT AVAILABLE]")
        
        return "\n".join(input_parts)

    def run_claude_analysis(self, input_text: str, output_format: str = "text") -> Optional[str]:
        """Run Claude Code in headless mode for transcript analysis"""
        
        if not self.claude_available:
            logger.error("Claude Code CLI not available")
            return None
        
        try:
            # Use temporary file for large input
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(input_text)
                temp_file_path = temp_file.name
            
            # Run Claude Code in headless mode
            cmd = [
                self.claude_cmd, 
                '-p',  # Print mode
                '--output-format', output_format,
                'Generate topic-organized daily digest from these podcast transcripts'
            ]
            
            # Run with input from file
            with open(temp_file_path, 'r') as input_file:
                result = subprocess.run(
                    cmd, 
                    stdin=input_file,
                    capture_output=True, 
                    text=True, 
                    timeout=300  # 5 minute timeout
                )
            
            # Cleanup temp file
            Path(temp_file_path).unlink()
            
            if result.returncode == 0:
                logger.info("Claude Code analysis completed successfully")
                return result.stdout
            else:
                logger.error(f"Claude Code analysis failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Claude Code analysis timed out")
            return None
        except Exception as e:
            logger.error(f"Error running Claude Code analysis: {e}")
            return None

    def detect_cross_references(self, transcripts: List[Dict]) -> Dict:
        """Use Claude Code to detect cross-references between episodes"""
        
        # Prepare focused input for cross-reference detection
        cross_ref_input = """
Analyze these podcast episode titles and content excerpts to identify cross-references and recurring themes.

TASK: Identify topics that appear across multiple episodes and rank by importance.

OUTPUT: JSON format with topics, episode IDs, and strength scores.

EPISODES:
"""
        
        for transcript in transcripts:
            # Load just a preview for cross-ref analysis
            try:
                with open(transcript['transcript_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                preview = content[:1000]  # First 1000 chars
                
                cross_ref_input += f"""
Episode {transcript['id']}: {transcript['title']}
Preview: {preview}...
---
"""
            except Exception as e:
                logger.error(f"Error loading transcript for cross-ref: {e}")
        
        # Run Claude analysis for cross-references
        result = self.run_claude_analysis(cross_ref_input, output_format="json")
        
        if result:
            try:
                cross_refs = json.loads(result)
                logger.info(f"Cross-reference analysis completed")
                return cross_refs
            except json.JSONDecodeError:
                logger.error("Failed to parse Claude cross-reference analysis")
                return {}
        else:
            return {}

    def generate_claude_daily_digest(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Generate daily digest using Claude Code headless mode"""
        
        logger.info("🧠 Starting Claude Code headless digest generation")
        
        if not self.claude_available:
            logger.error("Claude Code CLI not available - cannot generate Claude digest")
            return False, None, None
        
        # Get transcripts
        transcripts = self.get_transcripts_for_analysis()
        if not transcripts:
            logger.error("No transcripts available for Claude analysis")
            return False, None, None
        
        logger.info(f"📊 Preparing {len(transcripts)} transcripts for Claude analysis")
        
        # Prepare input
        claude_input = self.prepare_claude_input(transcripts)
        
        # Run Claude analysis
        claude_output = self.run_claude_analysis(claude_input)
        
        if not claude_output:
            logger.error("Claude Code analysis failed")
            return False, None, None
        
        # Save Claude-generated digest
        timestamp = now_utc().strftime('%Y%m%d_%H%M%S')
        digest_path = f"claude_daily_digest_{timestamp}.md"
        
        try:
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(claude_output)
            
            logger.info(f"✅ Claude-generated digest saved: {digest_path}")
            
            # Generate cross-reference analysis
            cross_refs = self.detect_cross_references(transcripts)
            
            cross_refs_path = f"claude_cross_references_{timestamp}.json"
            with open(cross_refs_path, 'w', encoding='utf-8') as f:
                json.dump(cross_refs, f, indent=2, default=str)
            
            logger.info(f"✅ Cross-reference analysis saved: {cross_refs_path}")
            
            return True, digest_path, cross_refs_path
            
        except Exception as e:
            logger.error(f"Error saving Claude digest: {e}")
            return False, None, None

    def integrate_with_pipeline(self) -> bool:
        """Integrate Claude headless into existing pipeline.py"""
        
        logger.info("🔧 Integrating Claude headless into pipeline.py")
        
        # This would modify pipeline.py to include Claude Code calls
        # For now, we'll create a separate enhanced pipeline
        
        try:
            # Read current pipeline
            with open('pipeline.py', 'r') as f:
                pipeline_content = f.read()
            
            # Check if Claude integration already exists
            if 'claude_headless_integration' in pipeline_content.lower():
                logger.info("Claude integration already exists in pipeline.py")
                return True
            
            # Create enhanced pipeline with Claude integration
            enhanced_pipeline_path = "enhanced_pipeline.py"
            
            enhanced_content = pipeline_content + """

# Phase 2.75: Claude Code Headless Integration
from claude_headless_integration import ClaudeHeadlessIntegration

def run_claude_enhanced_pipeline():
    \"\"\"Enhanced pipeline with Claude Code headless integration\"\"\"
    print("🧠 Enhanced Pipeline with Claude Code Integration")
    print("=" * 55)
    
    # Initialize Claude integration
    claude_integration = ClaudeHeadlessIntegration()
    
    # Generate Claude-powered digest
    success, digest_path, cross_refs_path = claude_integration.generate_claude_daily_digest()
    
    if success:
        print(f"✅ Claude-generated digest: {digest_path}")
        print(f"✅ Cross-references: {cross_refs_path}")
        return True
    else:
        print("❌ Claude digest generation failed")
        return False

# Add to main function
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "claude":
        run_claude_enhanced_pipeline()
    else:
        main()
"""
            
            with open(enhanced_pipeline_path, 'w') as f:
                f.write(enhanced_content)
            
            logger.info(f"✅ Enhanced pipeline created: {enhanced_pipeline_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error integrating with pipeline: {e}")
            return False


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Headless Integration")
    parser.add_argument('--test', action='store_true', help='Test Claude Code availability')
    parser.add_argument('--analyze', action='store_true', help='Run cross-reference analysis')
    parser.add_argument('--digest', action='store_true', help='Generate Claude digest')
    args = parser.parse_args()
    
    integration = ClaudeHeadlessIntegration()
    
    print("🧠 Claude Code Headless Integration - Phase 2.75")
    print("=" * 50)
    
    if args.test:
        if integration.claude_available:
            print("✅ Claude Code CLI available")
            return 0
        else:
            print("❌ Claude Code CLI not found")
            return 1
    
    if args.analyze:
        transcripts = integration.get_transcripts_for_analysis()
        if transcripts:
            print(f"📊 Analyzing {len(transcripts)} transcripts for cross-references...")
            cross_refs = integration.detect_cross_references(transcripts)
            print(f"✅ Found cross-reference data: {len(cross_refs) if isinstance(cross_refs, dict) else 'analysis complete'}")
        return 0
    
    if args.digest:
        success, digest_path, cross_refs_path = integration.generate_claude_daily_digest()
        if success:
            print(f"✅ Claude digest generated: {digest_path}")
            print(f"✅ Cross-references: {cross_refs_path}")
            return 0
        else:
            print("❌ Claude digest generation failed")
            return 1
    
    # Default: show available transcripts
    transcripts = integration.get_transcripts_for_analysis()
    print(f"📊 Found {len(transcripts)} transcripts ready for Claude analysis")
    print("Use --digest to generate Claude-powered daily digest")
    print("Use --analyze for cross-reference detection")
    
    return 0


if __name__ == "__main__":
    exit(main())