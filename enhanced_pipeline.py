#!/usr/bin/env python3
"""
Enhanced Pipeline - Phase 2.75 + Phase 3 Complete Integration
Combines Claude Code headless analysis with TTS generation
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Import all pipeline components
from pipeline import PipelineOrchestrator
from claude_headless_integration import ClaudeHeadlessIntegration
from claude_tts_generator import ClaudeTTSGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedPipelineOrchestrator:
    def __init__(self, db_path: str = "podcast_monitor.db"):
        self.db_path = db_path
        
        # Initialize all components
        self.base_pipeline = PipelineOrchestrator(db_path)
        self.claude_integration = ClaudeHeadlessIntegration(db_path)
        self.tts_generator = ClaudeTTSGenerator()

    def run_complete_pipeline(self, include_claude: bool = True, include_tts: bool = True) -> dict:
        """Run complete enhanced pipeline with all phases"""
        
        print("🚀 Enhanced Daily Podcast Pipeline")
        print("Phase 2 + Phase 2.75 + Phase 3 Integration")
        print("=" * 55)
        
        results = {
            "start_time": datetime.now(),
            "base_pipeline": None,
            "claude_analysis": None,
            "tts_audio": None,
            "success": False
        }
        
        # Phase 1 & 2: Base pipeline (existing episodes)
        print("📊 Phase 1-2: Base Content Processing")
        try:
            # Check if we have processed episodes
            episodes = self.claude_integration.get_transcripts_for_analysis()
            if episodes:
                print(f"✅ Found {len(episodes)} processed episodes ready")
                results["base_pipeline"] = {"episodes_ready": len(episodes)}
            else:
                print("❌ No processed episodes found")
                return results
        except Exception as e:
            print(f"❌ Base pipeline check failed: {e}")
            return results
        
        # Phase 2.75: Claude Code Analysis
        if include_claude:
            print("\n🧠 Phase 2.75: Claude Code Headless Analysis")
            try:
                success, digest_path, cross_refs_path = self.claude_integration.generate_claude_daily_digest()
                if success:
                    print(f"✅ Claude analysis complete: {Path(digest_path).name}")
                    results["claude_analysis"] = {
                        "digest_path": digest_path,
                        "cross_refs_path": cross_refs_path
                    }
                else:
                    print("⚠️  Claude analysis failed - continuing without it")
            except Exception as e:
                print(f"⚠️  Claude analysis error: {e}")
        else:
            print("⏭️  Skipping Claude Code analysis")
        
        # Phase 3: TTS Generation
        if include_tts:
            print("\n🎙️ Phase 3: TTS Audio Generation")
            try:
                success, audio_path = self.tts_generator.run_topic_based_workflow()
                if audio_path:
                    file_size = Path(audio_path).stat().st_size / 1024 / 1024
                    print(f"✅ TTS audio generated: {Path(audio_path).name} ({file_size:.1f}MB)")
                    results["tts_audio"] = {
                        "audio_path": audio_path,
                        "file_size_mb": file_size
                    }
                else:
                    print("❌ TTS generation failed")
                    return results
            except Exception as e:
                print(f"❌ TTS generation error: {e}")
                return results
        else:
            print("⏭️  Skipping TTS generation")
        
        # Success
        results["success"] = True
        results["end_time"] = datetime.now()
        execution_time = (results["end_time"] - results["start_time"]).total_seconds()
        
        print(f"\n🎉 Enhanced pipeline completed in {execution_time:.1f} seconds")
        return results

    def validate_phase_completion(self) -> dict:
        """Validate completion status of all phases"""
        
        validation = {
            "phase_1": {"status": "unknown", "components": []},
            "phase_2": {"status": "unknown", "components": []},
            "phase_2_75": {"status": "unknown", "components": []},
            "phase_3": {"status": "unknown", "components": []}
        }
        
        # Check Phase 1: Feed Monitoring
        try:
            episodes = self.claude_integration.get_transcripts_for_analysis()
            if episodes:
                validation["phase_1"]["status"] = "complete"
                validation["phase_1"]["components"] = [f"{len(episodes)} episodes monitored and stored"]
        except:
            validation["phase_1"]["status"] = "incomplete"
        
        # Check Phase 2: Content Processing
        transcribed_count = len([ep for ep in episodes if Path(ep['transcript_path']).exists()])
        if transcribed_count > 0:
            validation["phase_2"]["status"] = "complete" 
            validation["phase_2"]["components"] = [f"{transcribed_count} episodes transcribed"]
        else:
            validation["phase_2"]["status"] = "incomplete"
        
        # Check Phase 2.75: Claude Integration
        if self.claude_integration.claude_available:
            validation["phase_2_75"]["status"] = "ready"
            validation["phase_2_75"]["components"] = ["Claude Code CLI available", "Headless integration implemented"]
        else:
            validation["phase_2_75"]["status"] = "incomplete"
            validation["phase_2_75"]["components"] = ["Claude Code CLI not found"]
        
        # Check Phase 3: TTS
        tts_files = list(Path("daily_digests").glob("simple_daily_digest_*.mp3"))
        if tts_files:
            validation["phase_3"]["status"] = "complete"
            validation["phase_3"]["components"] = [f"TTS system working", f"{len(tts_files)} audio files generated"]
        else:
            validation["phase_3"]["status"] = "incomplete"
        
        return validation


def main():
    """CLI entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Pipeline Orchestrator")
    parser.add_argument('--validate', action='store_true', help='Validate all phases')
    parser.add_argument('--run', action='store_true', help='Run complete pipeline')
    parser.add_argument('--no-claude', action='store_true', help='Skip Claude analysis')
    parser.add_argument('--no-tts', action='store_true', help='Skip TTS generation')
    args = parser.parse_args()
    
    orchestrator = EnhancedPipelineOrchestrator()
    
    if args.validate:
        print("🔍 Phase Completion Validation")
        print("=" * 35)
        
        validation = orchestrator.validate_phase_completion()
        
        for phase, data in validation.items():
            status_icon = "✅" if data["status"] == "complete" else "🔄" if data["status"] == "ready" else "❌"
            print(f"\n{status_icon} {phase.upper()}: {data['status']}")
            for component in data["components"]:
                print(f"    - {component}")
        
        return 0
    
    if args.run:
        results = orchestrator.run_complete_pipeline(
            include_claude=not args.no_claude,
            include_tts=not args.no_tts
        )
        
        return 0 if results["success"] else 1
    
    # Default: show status
    validation = orchestrator.validate_phase_completion()
    
    print("🎙️ Enhanced Daily Podcast Pipeline Status")
    print("=" * 45)
    
    all_complete = all(data["status"] in ["complete", "ready"] for data in validation.values())
    
    if all_complete:
        print("✅ All phases ready for Phase 4")
        print("Use --run to execute complete pipeline")
    else:
        print("⚠️  Some phases need attention")
        print("Use --validate for detailed status")
    
    return 0


if __name__ == "__main__":
    exit(main())