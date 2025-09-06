#!/usr/bin/env python3
"""
Configuration Validation Script
Ensures all config environments have consistent OPENAI_SETTINGS structure
Supports severity levels (critical vs optional) and warn-only mode for CI smoke tests
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

def load_config_class(config_name: str):
    """Load a specific config class"""
    try:
        if config_name == "main":
            from config import Config
            return Config()
        elif config_name == "production":
            from config.production import ProductionConfig
            return ProductionConfig()
        elif config_name == "staging":
            from config.staging import StagingConfig
            return StagingConfig()
        elif config_name == "development":
            from config.development import DevelopmentConfig
            return DevelopmentConfig()
        else:
            return None
    except ImportError as e:
        print(f"❌ Could not import {config_name} config: {e}")
        return None

def extract_openai_settings_keys(config_obj) -> Set[str]:
    """Extract OPENAI_SETTINGS keys from a config object"""
    if hasattr(config_obj, 'OPENAI_SETTINGS') and isinstance(config_obj.OPENAI_SETTINGS, dict):
        return set(config_obj.OPENAI_SETTINGS.keys())
    return set()

def find_required_keys_in_codebase() -> Set[str]:
    """Find all OPENAI_SETTINGS keys used in the codebase"""
    required_keys = set()
    
    # Files that use OPENAI_SETTINGS
    files_to_check = [
        "openai_digest_integration.py",
        "episode_summary_generator.py",
        "prose_validator.py"
    ]
    
    for file_path in files_to_check:
        if Path(file_path).exists():
            with open(file_path, 'r') as f:
                content = f.read()
                # Find patterns like config.OPENAI_SETTINGS['key']
                import re
                pattern = r"config\.OPENAI_SETTINGS\[[\'\"]([^\'\"]+)[\'\"]"
                matches = re.findall(pattern, content)
                required_keys.update(matches)
                
                # Also check for self.settings['key'] in episode_summary_generator
                if "episode_summary_generator.py" in file_path:
                    pattern = r"self\.settings\[[\'\"]([^\'\"]+)[\'\"]"
                    matches = re.findall(pattern, content)
                    required_keys.update(matches)
    
    return required_keys

def validate_config_consistency():
    """Validate that all config environments have consistent OPENAI_SETTINGS"""
    
    print("🔍 Configuration Validation Report")
    print("=" * 50)
    
    # Load all available configs
    configs = {}
    for config_name in ["main", "production", "staging", "development"]:
        config_obj = load_config_class(config_name)
        if config_obj:
            configs[config_name] = config_obj
    
    if not configs:
        print("❌ No configurations could be loaded!")
        return False
    
    print(f"📚 Loaded configs: {list(configs.keys())}")
    
    # Find required keys from codebase analysis
    required_keys = find_required_keys_in_codebase()
    print(f"🔍 Required keys found in codebase: {sorted(required_keys)}")
    
    # Extract OPENAI_SETTINGS from each config
    config_keys = {}
    for name, config_obj in configs.items():
        keys = extract_openai_settings_keys(config_obj)
        config_keys[name] = keys
        print(f"🔧 {name} config keys: {len(keys)} keys")
    
    # Validation checks
    all_passed = True
    
    print("\n📋 Validation Results:")
    print("-" * 30)
    
    # Check 1: All configs have required keys
    for name, keys in config_keys.items():
        missing = required_keys - keys
        if missing:
            print(f"❌ {name} config missing keys: {sorted(missing)}")
            all_passed = False
        else:
            print(f"✅ {name} config has all required keys")
    
    # Check 2: Consistency between main and production (most important)
    if "main" in config_keys and "production" in config_keys:
        main_keys = config_keys["main"]
        prod_keys = config_keys["production"]
        
        only_in_main = main_keys - prod_keys
        only_in_prod = prod_keys - main_keys
        
        if only_in_main:
            print(f"⚠️  Keys only in main config: {sorted(only_in_main)}")
            
        if only_in_prod:
            print(f"⚠️  Keys only in production config: {sorted(only_in_prod)}")
    
    # Check 3: Specific critical keys
    critical_keys = ['relevance_threshold', 'topics', 'digest_model', 'scoring_model']
    for critical_key in critical_keys:
        print(f"\n🎯 Critical key '{critical_key}':")
        for name, keys in config_keys.items():
            if critical_key in keys:
                config_obj = configs[name]
                value = config_obj.OPENAI_SETTINGS.get(critical_key, "N/A")
                if critical_key == 'topics':
                    value_desc = f"{len(value)} topics" if isinstance(value, dict) else str(value)
                else:
                    value_desc = str(value)
                print(f"  ✅ {name}: {value_desc}")
            else:
                print(f"  ❌ {name}: MISSING")
                all_passed = False
    
    print(f"\n🎯 Overall Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
    
    return all_passed


def redact_secret(value: str) -> str:
    """
    Redact secrets for logging - show only length or last 4 chars.
    
    Args:
        value: Secret value to redact
    
    Returns:
        str: Redacted representation
    """
    if not value:
        return "EMPTY"
    if len(value) <= 4:
        return f"***({len(value)} chars)"
    return f"***{value[-4:]} ({len(value)} chars)"


def validate_critical_config(warn_only: bool = False) -> bool:
    """
    Validate critical configuration that must be present for system operation.
    
    Args:
        warn_only: If True, warnings instead of errors for missing criticals
    
    Returns:
        bool: True if all critical checks pass or warn_only=True
    """
    print("🔍 Critical Configuration Validation")
    print("-" * 40)
    
    critical_issues = 0
    
    # Critical environment variables
    critical_env_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ]
    
    for env_var in critical_env_vars:
        value = os.getenv(env_var)
        if not value:
            msg = f"❌ CRITICAL: {env_var} is missing or empty"
            if warn_only:
                print(f"⚠️  WARN: {env_var} is missing (smoke mode)")
            else:
                print(msg)
                critical_issues += 1
        else:
            print(f"✅ {env_var}: {redact_secret(value)}")
    
    # Critical directories (must be writable)
    critical_dirs = [
        "daily_digests",
        "transcripts",
        "audio_cache"
    ]
    
    for dir_path in critical_dirs:
        path_obj = Path(dir_path)
        try:
            path_obj.mkdir(exist_ok=True)
            if not os.access(path_obj, os.W_OK):
                msg = f"❌ CRITICAL: {dir_path}/ is not writable"
                if warn_only:
                    print(f"⚠️  WARN: {dir_path}/ may not be writable (smoke mode)")
                else:
                    print(msg)
                    critical_issues += 1
            else:
                print(f"✅ {dir_path}/: writable")
        except Exception as e:
            msg = f"❌ CRITICAL: Cannot create {dir_path}/: {e}"
            if warn_only:
                print(f"⚠️  WARN: Cannot verify {dir_path}/ (smoke mode)")
            else:
                print(msg)
                critical_issues += 1
    
    # Database files (must be accessible if they exist)
    db_files = ["podcast_monitor.db", "youtube_transcripts.db"]
    for db_file in db_files:
        if Path(db_file).exists():
            try:
                from utils.db import get_connection
                conn = get_connection(db_file)
                conn.execute("SELECT 1")
                conn.close()
                print(f"✅ {db_file}: accessible")
            except Exception as e:
                msg = f"❌ CRITICAL: Cannot access {db_file}: {e}"
                if warn_only:
                    print(f"⚠️  WARN: Cannot verify {db_file} (smoke mode)")
                else:
                    print(msg)
                    critical_issues += 1
        else:
            print(f"ℹ️  {db_file}: not present (will be created)")
    
    success = critical_issues == 0
    if warn_only:
        print("ℹ️  Critical validation completed in WARN-ONLY mode")
        return True  # Always pass in warn-only mode
    
    return success


def validate_optional_config() -> bool:
    """
    Validate optional configuration - warns but doesn't fail validation.
    
    Returns:
        bool: Always True (warnings only)
    """
    print("\n🔧 Optional Configuration Validation")
    print("-" * 40)
    
    # Optional environment variables
    optional_env_vars = [
        ("ELEVENLABS_API_KEY", "TTS audio generation"),
        ("GITHUB_TOKEN", "GitHub releases deployment"),
        ("FEED_LOOKBACK_HOURS", "RSS feed lookback window"),
        ("PODCAST_BASE_URL", "Podcast RSS feed base URL"),
        ("AUDIO_BASE_URL", "Audio file base URL")
    ]
    
    for env_var, description in optional_env_vars:
        value = os.getenv(env_var)
        if not value:
            print(f"⚠️  OPTIONAL: {env_var} missing - {description} disabled")
        else:
            if "KEY" in env_var or "TOKEN" in env_var:
                print(f"✅ {env_var}: {redact_secret(value)} - {description} enabled")
            else:
                print(f"✅ {env_var}: {value} - {description} configured")
    
    # Optional config validation
    try:
        from config import Config
        config = Config()
        
        # Check for voice/music configuration
        if hasattr(config, 'VOICE_CONFIG'):
            print("✅ Voice configuration: present")
        else:
            print("⚠️  OPTIONAL: Voice configuration missing")
            
        if hasattr(config, 'MUSIC_CONFIG'):
            print("✅ Music configuration: present") 
        else:
            print("⚠️  OPTIONAL: Music configuration missing")
            
    except Exception as e:
        print(f"⚠️  OPTIONAL: Could not load main config: {e}")
    
    return True  # Optional checks never fail validation


def validate_all_config(warn_only: bool = False) -> bool:
    """
    Run all configuration validations.
    
    Args:
        warn_only: If True, critical issues become warnings
    
    Returns:
        bool: True if validation passes
    """
    print("🔍 Complete Configuration Validation")
    print("=" * 50)
    
    # Run critical validation
    critical_ok = validate_critical_config(warn_only=warn_only)
    
    # Run optional validation (always passes)
    validate_optional_config()
    
    # Run existing OPENAI_SETTINGS validation
    openai_ok = validate_config_consistency()
    
    overall_success = critical_ok and openai_ok
    
    print(f"\n🎯 Overall Validation Result: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    if warn_only and not overall_success:
        print("ℹ️  Some issues found but running in WARN-ONLY mode")
        return True
    
    return overall_success


def main():
    """Main validation function with command line argument support"""
    parser = argparse.ArgumentParser(description="Configuration validation for podcast scraper")
    parser.add_argument("--all", action="store_true", 
                       help="Run all validations (critical + optional + OpenAI settings)")
    parser.add_argument("--warn-only", action="store_true",
                       help="Convert critical errors to warnings (for CI smoke tests)")
    
    args = parser.parse_args()
    
    if args.all:
        success = validate_all_config(warn_only=args.warn_only)
    else:
        # Legacy behavior - just OpenAI settings validation
        success = validate_config_consistency()
    
    if not success:
        if not args.warn_only:
            print("\n⚠️  Configuration validation failed!")
            print("💡 Recommendation: Fix critical configuration issues")
            sys.exit(1)
    
    print("\n✅ Configuration validation completed!")
    sys.exit(0)

if __name__ == "__main__":
    main()