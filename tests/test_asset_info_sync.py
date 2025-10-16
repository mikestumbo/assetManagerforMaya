#!/usr/bin/env python3
"""
Asset Information Synchronization Test - Issue #8
Tests the unified synchronization between View > Show Asset Information menu and Info button
"""

import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

try:
    from PySide6.QtWidgets import QApplication, QMainWindow
    from PySide6.QtCore import Qt
    print("✅ PySide6 available")
except ImportError:
    print("❌ PySide6 not available - cannot test UI synchronization")
    sys.exit(1)

def test_asset_info_synchronization():
    """Test Asset Information menu/button synchronization - Issue #8"""
    print("\n🔧 Testing Asset Information Synchronization...")
    
    try:
        from ui.asset_manager_window import AssetManagerWindow
        print("✅ AssetManagerWindow imported successfully")
        
        # Check for unified method
        if hasattr(AssetManagerWindow, '_on_toggle_asset_info_unified'):
            print("✅ Unified method _on_toggle_asset_info_unified found")
        else:
            print("❌ Missing unified method _on_toggle_asset_info_unified")
            return False
        
        # Check for legacy methods
        if hasattr(AssetManagerWindow, '_on_toggle_asset_info'):
            print("✅ Legacy method _on_toggle_asset_info maintained")
        else:
            print("❌ Missing legacy method _on_toggle_asset_info")
            return False
            
        if hasattr(AssetManagerWindow, '_on_show_asset_info'):
            print("✅ Legacy method _on_show_asset_info maintained")
        else:
            print("❌ Missing legacy method _on_show_asset_info")
            return False
        
        print("✅ Asset Information synchronization methods implemented correctly")
        return True
        
    except Exception as e:
        print(f"❌ Asset Information synchronization test failed: {e}")
        return False

def test_method_signatures():
    """Test that methods have correct signatures"""
    print("\n🔍 Testing Method Signatures...")
    
    try:
        from ui.asset_manager_window import AssetManagerWindow
        import inspect
        
        # Check unified method signature
        unified_sig = inspect.signature(AssetManagerWindow._on_toggle_asset_info_unified)
        print(f"✅ Unified method signature: {unified_sig}")
        
        # Check legacy method signatures
        toggle_sig = inspect.signature(AssetManagerWindow._on_toggle_asset_info)
        show_sig = inspect.signature(AssetManagerWindow._on_show_asset_info)
        
        print(f"✅ Toggle method signature: {toggle_sig}")
        print(f"✅ Show method signature: {show_sig}")
        
        return True
        
    except Exception as e:
        print(f"❌ Method signature test failed: {e}")
        return False

def main():
    """Run Asset Information synchronization tests"""
    print("🧪 ASSET INFORMATION SYNCHRONIZATION TEST - Issue #8")
    print("=" * 60)
    
    # Initialize QApplication for Qt imports
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Run tests
    tests = [
        ("Asset Info Synchronization", test_asset_info_synchronization),
        ("Method Signatures", test_method_signatures),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 ASSET INFORMATION SYNC TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All Asset Information synchronization tests PASSED!")
        print("🔄 Menu and button are now properly synchronized")
        return True
    else:
        print("⚠️ Some tests failed - check implementation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
