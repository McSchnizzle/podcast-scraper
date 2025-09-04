#!/usr/bin/env python3
"""
Configuration Validation Script
Ensures all config environments have consistent OPENAI_SETTINGS structure
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Any

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

def main():
    """Main validation function"""
    success = validate_config_consistency()
    
    if not success:
        print("\n⚠️  Configuration validation failed!")
        print("💡 Recommendation: Update production config to match main config structure")
        sys.exit(1)
    else:
        print("\n✅ All configuration validations passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()