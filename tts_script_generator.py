#!/usr/bin/env python3
"""
TTS Script Generator with Emphasis Markers and Audio Cues
Phase 3: Professional podcast script generation for ElevenLabs TTS
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
from topic_compiler import TopicCompiler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSScriptGenerator:
    def __init__(self, output_dir: str = "daily_digests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.topic_compiler = TopicCompiler()
        
        # Audio cue definitions
        self.audio_cues = {
            "intro_music": "[INTRO_MUSIC:energetic_news_theme:15s:fade_in]",
            "intro_music_out": "[INTRO_MUSIC:fade_out:3s]",
            "topic_transition": "[TRANSITION_MUSIC:soft_ambient:8s:fade_in_out]", 
            "emphasis_sting": "[EMPHASIS_STING:attention:0.5s]",
            "conclusion_music": "[OUTRO_MUSIC:warm_conclusion:12s:fade_in]",
            "conclusion_music_out": "[OUTRO_MUSIC:fade_out:4s]",
            "pause_short": "[PAUSE:800ms]",
            "pause_medium": "[PAUSE:1200ms]", 
            "pause_long": "[PAUSE:2000ms]"
        }
        
        # TTS emphasis markers
        self.emphasis_markers = {
            "strong": {"start": "[EMPHASIS:strong]", "end": "[/EMPHASIS:strong]"},
            "moderate": {"start": "[EMPHASIS]", "end": "[/EMPHASIS]"},
            "subtle": {"start": "[TONE:confident]", "end": "[/TONE]"},
            "important": {"start": "[IMPORTANT]", "end": "[/IMPORTANT]"},
            "quote": {"start": "[QUOTE]", "end": "[/QUOTE]"}
        }
        
        # Voice pacing instructions
        self.pacing_cues = {
            "slow_down": "[PACE:slow]",
            "speed_up": "[PACE:fast]", 
            "normal": "[PACE:normal]",
            "dramatic_pause": "[DRAMATIC_PAUSE:1500ms]",
            "breath": "[BREATH]"
        }

    def generate_full_tts_script(self, episodes: List[Dict] = None) -> Tuple[str, Dict]:
        """Generate complete TTS script with all audio cues and emphasis"""
        
        if episodes is None:
            episodes = self.topic_compiler.get_processed_episodes()
        
        if not episodes:
            logger.error("No episodes available for script generation")
            return "", {}
        
        # Get topic compilation
        compilation = self.topic_compiler.generate_tts_optimized_compilation(episodes)
        
        script_parts = []
        
        # Generate introduction
        intro = self._generate_introduction(compilation)
        script_parts.append(intro)
        
        # Generate topic sections
        for topic_key, topic_data in compilation["topics"].items():
            topic_section = self._generate_topic_section(topic_key, topic_data)
            script_parts.append(topic_section)
        
        # Generate conclusion
        conclusion = self._generate_conclusion(compilation)
        script_parts.append(conclusion)
        
        # Combine full script
        full_script = "\n\n".join(script_parts)
        
        # Add production notes
        production_notes = self._generate_production_notes(compilation)
        
        return full_script, production_notes

    def _generate_introduction(self, compilation: Dict) -> str:
        """Generate podcast introduction with audio cues"""
        
        metadata = compilation["metadata"]
        date_str = datetime.now().strftime('%A, %B %d, %Y')
        
        intro = f"""
{self.audio_cues["intro_music"]}

{self.emphasis_markers["strong"]["start"]}Welcome to your Daily Podcast Digest for {date_str}.{self.emphasis_markers["strong"]["end"]}

{self.audio_cues["intro_music_out"]}

I'm your AI host, bringing you synthesized insights from {metadata["total_episodes"]} podcast episodes, 
intelligently organized by themes rather than individual shows.

{self.pacing_cues["normal"]}

Today we'll explore {metadata["topics_covered"]} key areas where significant developments are emerging 
across the podcast landscape. From artificial intelligence breakthroughs to creative innovations, 
we'll synthesize the most important insights in approximately {metadata["estimated_audio_duration"]}.

{self.audio_cues["pause_medium"]}

Let's begin with today's most significant themes.

{self.audio_cues["pause_short"]}
"""
        
        return intro.strip()

    def _generate_topic_section(self, topic_key: str, topic_data: Dict) -> str:
        """Generate complete topic section with audio cues"""
        
        display_name = topic_data["display_name"]
        episode_count = topic_data["episode_count"]
        synthesis = topic_data["synthesis"]
        
        section_parts = []
        
        # Topic header with transition
        header = f"""
{self.audio_cues["topic_transition"]}

## {display_name}

{self.emphasis_markers["moderate"]["start"]}In {display_name.lower()}, we're tracking significant developments 
across {episode_count} episode{"s" if episode_count > 1 else ""}.{self.emphasis_markers["moderate"]["end"]}

{self.audio_cues["pause_short"]}
"""
        section_parts.append(header.strip())
        
        # Main content synthesis
        tts_script = topic_data["tts_script"]
        
        # Enhance script with proper emphasis and pacing
        enhanced_script = self._enhance_script_with_cues(tts_script, topic_key)
        section_parts.append(enhanced_script)
        
        # Key insights with emphasis
        if synthesis["key_insights"]:
            insights_intro = f"""
{self.audio_cues["pause_medium"]}

{self.emphasis_markers["important"]["start"]}Key takeaways from this analysis:{self.emphasis_markers["important"]["end"]}
"""
            section_parts.append(insights_intro.strip())
            
            for i, insight in enumerate(synthesis["key_insights"][:3], 1):
                # Clean and optimize insight for TTS
                clean_insight = self._optimize_for_speech(insight)
                insight_text = f"\n{i}. {clean_insight}"
                section_parts.append(insight_text)
        
        # Section conclusion
        conclusion = f"""
{self.audio_cues["pause_medium"]}

This {display_name.lower()} analysis reveals the rapid pace of change and its practical implications 
for creators and consumers alike.

{self.audio_cues["pause_short"]}
"""
        section_parts.append(conclusion.strip())
        
        return "\n".join(section_parts)

    def _enhance_script_with_cues(self, script: str, topic_key: str) -> str:
        """Enhance script with topic-appropriate audio cues"""
        
        # Apply topic-specific enhancements
        if topic_key == "ai_tools":
            # Technical content gets precise emphasis
            script = re.sub(r'\*\*(.*?)\*\*', rf'{self.emphasis_markers["moderate"]["start"]}\1{self.emphasis_markers["moderate"]["end"]}', script)
            
        elif topic_key == "product_launches":
            # Product launches get energetic emphasis
            script = re.sub(r'\*\*(.*?)\*\*', rf'{self.emphasis_markers["strong"]["start"]}\1{self.emphasis_markers["strong"]["end"]}', script)
            
        elif topic_key == "creative_applications":
            # Creative content gets warm, inspiring emphasis
            script = re.sub(r'\*\*(.*?)\*\*', rf'{self.emphasis_markers["subtle"]["start"]}\1{self.emphasis_markers["subtle"]["end"]}', script)
        
        # Add appropriate pauses
        script = re.sub(r'(\. )([A-Z])', rf'\1{self.audio_cues["pause_short"]} \2', script)
        
        return script

    def _optimize_for_speech(self, text: str) -> str:
        """Optimize text for natural speech synthesis"""
        
        # Handle numbers and abbreviations
        text = re.sub(r'\b(\d+)%', r'\1 percent', text)
        text = re.sub(r'\$(\d+)', r'\1 dollars', text)
        text = re.sub(r'\b(\d+)K\b', r'\1 thousand', text)
        text = re.sub(r'\b(\d+)M\b', r'\1 million', text)
        
        # Handle common tech abbreviations
        replacements = {
            "AI": "artificial intelligence",
            "ML": "machine learning", 
            "API": "A P I",
            "UI": "user interface",
            "UX": "user experience",
            "CEO": "C E O",
            "CTO": "C T O",
            "vs": "versus",
            "etc": "etcetera"
        }
        
        for abbrev, expansion in replacements.items():
            text = re.sub(rf'\b{re.escape(abbrev)}\b', expansion, text, flags=re.IGNORECASE)
        
        # Clean up punctuation for speech
        text = re.sub(r'([.!?])\s*([.!?])', r'\1', text)  # Remove double punctuation
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        return text.strip()

    def _generate_conclusion(self, compilation: Dict) -> str:
        """Generate podcast conclusion with audio cues"""
        
        metadata = compilation["metadata"]
        topics_list = list(compilation["topics"].keys())
        
        conclusion = f"""
{self.audio_cues["conclusion_music"]}

{self.emphasis_markers["moderate"]["start"]}That concludes today's Daily Podcast Digest.{self.emphasis_markers["moderate"]["end"]}

{self.pacing_cues["slow_down"]}

We've synthesized insights from {metadata["total_episodes"]} episodes across {metadata["topics_covered"]} 
major themes, focusing on cross-episode connections rather than individual show summaries.

{self.audio_cues["pause_medium"]}

{self.emphasis_markers["subtle"]["start"]}Tomorrow's digest will continue tracking these evolving themes 
while introducing new developments from across the podcast landscape.{self.emphasis_markers["subtle"]["end"]}

{self.audio_cues["pause_long"]}

Thanks for listening to your Daily Podcast Digest. 
Stay curious, stay informed.

{self.audio_cues["conclusion_music_out"]}
"""
        
        return conclusion.strip()

    def _generate_production_notes(self, compilation: Dict) -> Dict:
        """Generate production notes for audio engineers"""
        
        return {
            "generation_metadata": {
                "timestamp": compilation["metadata"]["generation_time"],
                "episode_count": compilation["metadata"]["total_episodes"],
                "estimated_duration": compilation["metadata"]["estimated_audio_duration"]
            },
            "audio_requirements": {
                "intro_music": "15-second energetic news theme with fade-in",
                "topic_transitions": "8-second ambient music with fade in/out",
                "conclusion_music": "12-second warm conclusion theme with fade-in",
                "voice_settings": "Professional podcast quality, normalized audio levels"
            },
            "voice_instructions": {
                topic_key: compilation["topics"][topic_key]["voice_instructions"] 
                for topic_key in compilation["topics"]
            },
            "script_structure": compilation["script_structure"],
            "post_processing": {
                "audio_normalization": "Target -16 LUFS for podcast distribution",
                "noise_reduction": "Apply gentle noise reduction",
                "eq_settings": "Enhance voice clarity in 1-4kHz range",
                "compression": "Light compression for consistent levels"
            }
        }

    def export_for_tts_production(self, episodes: List[Dict] = None) -> Tuple[str, str]:
        """Export complete TTS production package"""
        
        # Generate script and production notes
        script, production_notes = self.generate_full_tts_script(episodes)
        
        if not script:
            return "", ""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save TTS script
        script_path = self.output_dir / f"tts_script_{timestamp}.txt"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script)
        
        # Save production notes
        notes_path = self.output_dir / f"production_notes_{timestamp}.json"
        with open(notes_path, 'w', encoding='utf-8') as f:
            json.dump(production_notes, f, indent=2, default=str)
        
        logger.info(f"TTS production package exported:")
        logger.info(f"  Script: {script_path}")
        logger.info(f"  Notes: {notes_path}")
        
        return str(script_path), str(notes_path)


def main():
    """CLI entry point for TTS script generation"""
    
    generator = TTSScriptGenerator()
    
    print("📝 TTS Script Generator with Audio Cues")
    print("=" * 42)
    
    # Generate production package
    script_path, notes_path = generator.export_for_tts_production()
    
    if script_path and notes_path:
        print("✅ TTS production package generated:")
        print(f"   📄 Script: {script_path}")
        print(f"   📋 Notes: {notes_path}")
        
        # Show script preview
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"\n📖 Script Preview ({len(content)} characters):")
            print("-" * 50)
            print(content[:800])
            if len(content) > 800:
                print("\n... (script continues)")
        except Exception as e:
            print(f"Error reading script preview: {e}")
        
        return 0
    else:
        print("❌ Failed to generate TTS script")
        return 1


if __name__ == "__main__":
    exit(main())