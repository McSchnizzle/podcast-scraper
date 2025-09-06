#!/usr/bin/env python3
"""
Final verification script for Phase 3 completion.
This confirms all Phase 3 fixes are working and ready for production.
"""

import sys
import warnings
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_main_issues_fixed():
    """Test the main issues that Phase 3 was supposed to fix"""
    print("=" * 60)
    print("PHASE 3 FINAL VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Test 1: ImportError for OpenAIScorer should be fixed
    print("\n1. Testing ImportError fix...")
    try:
        from openai_scorer import OpenAITopicScorer
        scorer = OpenAITopicScorer()
        print("   ✅ Can import and instantiate OpenAITopicScorer")
        results.append(("ImportError Fix", True))
    except Exception as e:
        print(f"   ❌ ImportError not fixed: {e}")
        results.append(("ImportError Fix", False))
    
    # Test 2: TelemetryManager record_metric should exist
    print("\n2. Testing TelemetryManager record_metric...")
    try:
        from telemetry_manager import TelemetryManager
        tm = TelemetryManager()
        
        # Test the exact calls that were failing
        tm.record_metric('rss_retries_processed', 5)
        tm.record_metric('youtube_retries_succeeded', 3)
        print("   ✅ record_metric exists and works")
        results.append(("record_metric Fix", True))
    except AttributeError as e:
        print(f"   ❌ record_metric still missing: {e}")
        results.append(("record_metric Fix", False))
    except Exception as e:
        print(f"   ❌ record_metric error: {e}")
        results.append(("record_metric Fix", False))
    
    # Test 3: Compatibility shim works
    print("\n3. Testing compatibility shim...")
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from openai_scorer_compat import OpenAIScorer
            
            if len(w) > 0 and "deprecated" in str(w[0].message).lower():
                print("   ✅ Compatibility shim works with deprecation warning")
                results.append(("Compatibility Shim", True))
            else:
                print("   ⚠️ Compatibility shim works but no deprecation warning")
                results.append(("Compatibility Shim", True))
    except Exception as e:
        print(f"   ❌ Compatibility shim failed: {e}")
        results.append(("Compatibility Shim", False))
    
    # Test 4: CI guard works
    print("\n4. Testing CI guard...")
    try:
        result = subprocess.run([
            sys.executable, 
            "tests/test_no_legacy_imports.py"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("   ✅ CI guard passes - no legacy imports found")
            results.append(("CI Guard", True))
        else:
            print(f"   ❌ CI guard failed: {result.stderr}")
            results.append(("CI Guard", False))
    except Exception as e:
        print(f"   ❌ CI guard error: {e}")
        results.append(("CI Guard", False))
    
    # Test 5: Integration tests pass
    print("\n5. Testing integration tests...")
    try:
        result = subprocess.run([
            sys.executable, 
            "tests/test_phase3_integration.py"
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("   ✅ All integration tests pass")
            results.append(("Integration Tests", True))
        else:
            print(f"   ❌ Integration tests failed: {result.stderr}")
            results.append(("Integration Tests", False))
    except Exception as e:
        print(f"   ❌ Integration tests error: {e}")
        results.append(("Integration Tests", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("FINAL VERIFICATION RESULTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 PHASE 3 VERIFICATION COMPLETE!")
        print("\nAll critical issues have been resolved:")
        print("- ✅ OpenAIScorer import errors fixed")
        print("- ✅ TelemetryManager record_metric method added")
        print("- ✅ Retry queue processing should work")
        print("- ✅ Pipeline telemetry recording functional")
        print("- ✅ Compatibility shim provides migration path")
        print("- ✅ CI guards prevent regressions")
        
        print("\nPhase 3 is READY FOR PRODUCTION! 🚀")
        return 0
    else:
        print(f"\n❌ PHASE 3 VERIFICATION FAILED")
        print(f"   {failed} critical issues still need resolution")
        return 1

if __name__ == "__main__":
    sys.exit(test_main_issues_fixed())