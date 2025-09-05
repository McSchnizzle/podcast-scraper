#!/usr/bin/env python3
"""
CI guard to prevent legacy OpenAIScorer imports in production code.
This ensures the codebase migrates to the new naming convention.

Run with: python3 tests/test_no_legacy_imports.py
"""
import pathlib
import re
import sys
import os

# Pattern to detect legacy imports
LEGACY_IMPORT_PATTERN = re.compile(
    r"from\s+openai_scorer\s+import\s+.*\bOpenAIScorer\b"
)

def test_no_legacy_imports():
    """Ensure no production code uses legacy OpenAIScorer import"""
    root = pathlib.Path(__file__).resolve().parents[1]
    
    # Files/dirs allowed to have legacy imports
    allowed_patterns = [
        'tests/legacy_compat',
        'openai_scorer_compat.py',
        'phase3_',  # Phase 3 documentation
        '.git',
        '__pycache__',
        'long-log-file',  # Old log files
        'github-workflow-log.txt',  # Old workflow logs
        'PHASED_REMEDIATION_TASKS.md',  # Documentation files
        'VERIFICATION_AND_TEST_PLAN.md',
        'action_plan',  # Planning files
        'topic-refactor/',  # Old refactor files
    ]
    
    offenders = []
    files_checked = 0
    
    for py_file in root.rglob("*.py"):
        # Skip allowed locations
        rel_path = py_file.relative_to(root)
        if any(pattern in str(rel_path) for pattern in allowed_patterns):
            continue
            
        try:
            content = py_file.read_text(encoding="utf-8")
            files_checked += 1
            
            if LEGACY_IMPORT_PATTERN.search(content):
                # Get line number for better reporting
                for i, line in enumerate(content.split('\n'), 1):
                    if LEGACY_IMPORT_PATTERN.search(line):
                        offenders.append(f"{rel_path}:{i} - {line.strip()}")
        except Exception as e:
            print(f"Warning: Could not read {py_file}: {e}")
    
    print(f"✅ Checked {files_checked} Python files for legacy imports")
    
    if offenders:
        print("❌ Legacy OpenAIScorer imports found in:")
        for location in offenders:
            print(f"  - {location}")
        print("\nPlease update to: from openai_scorer import OpenAITopicScorer")
        print("Or use the compatibility shim: from openai_scorer_compat import OpenAIScorer")
        return False
    else:
        print("✅ No legacy imports found in production code")
        return True

def test_compatibility_shim_exists():
    """Ensure compatibility shim exists for legacy code"""
    root = pathlib.Path(__file__).resolve().parents[1]
    compat_file = root / "openai_scorer_compat.py"
    
    if not compat_file.exists():
        print("❌ Compatibility shim openai_scorer_compat.py not found")
        return False
        
    print("✅ Compatibility shim exists")
    return True

def test_new_class_available():
    """Test that the new class name is importable"""
    try:
        # Add project root to path
        root = pathlib.Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        
        from openai_scorer import OpenAITopicScorer
        assert OpenAITopicScorer is not None
        print("✅ OpenAITopicScorer import works")
        return True
    except ImportError as e:
        print(f"❌ Cannot import OpenAITopicScorer: {e}")
        return False

def main():
    """Run all legacy import checks"""
    print("=" * 60)
    print("PHASE 3 CI GUARD - LEGACY IMPORT CHECKER")
    print("=" * 60)
    
    tests = [
        ("Legacy Imports Check", test_no_legacy_imports),
        ("Compatibility Shim Check", test_compatibility_shim_exists),
        ("New Class Import Check", test_new_class_available)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    if all(r[1] for r in results):
        print("\n🎉 ALL CI GUARD TESTS PASSED!")
        return 0
    else:
        print("\n❌ CI GUARD TESTS FAILED - Legacy imports detected!")
        return 1

if __name__ == "__main__":
    sys.exit(main())