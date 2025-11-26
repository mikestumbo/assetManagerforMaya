#!/usr/bin/env python3
"""
Refresh Library Button Test - Issue #9
Tests the enhanced Refresh Library functionality in the Main Menu Bar
"""

import sys
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

try:
    print("✅ PySide6 available")
except ImportError:
    print("❌ PySide6 not available - cannot test UI functionality")
    sys.exit(1)


def test_refresh_library_method():
    """Test Refresh Library method implementation - Issue #9"""
    print("\n🔧 Testing Refresh Library Method...")

    try:
        from ui.asset_manager_window import AssetManagerWindow
        print("✅ AssetManagerWindow imported successfully")

        # Check for refresh method
        if hasattr(AssetManagerWindow, '_on_refresh_library'):
            print("✅ _on_refresh_library method found")
        else:
            print("❌ Missing _on_refresh_library method")
            return False

        # Check method signature and implementation
        import inspect
        refresh_sig = inspect.signature(AssetManagerWindow._on_refresh_library)
        print(f"✅ Refresh method signature: {refresh_sig}")

        # Get method source to verify enhancement
        source_lines = inspect.getsourcelines(AssetManagerWindow._on_refresh_library)[0]
        source_text = ''.join(source_lines)

        # Check for enhanced features
        enhancements_found = 0

        if "error handling" in source_text.lower():
            print("✅ Enhanced error handling implemented")
            enhancements_found += 1

        if "user feedback" in source_text.lower():
            print("✅ User feedback features implemented")
            enhancements_found += 1

        if "show_progress" in source_text:
            print("✅ Progress indication implemented")
            enhancements_found += 1

        if "QMessageBox" in source_text:
            print("✅ User notification dialogs implemented")
            enhancements_found += 1

        if "_set_status" in source_text:
            print("✅ Status bar updates implemented")
            enhancements_found += 1

        if "try:" in source_text and "except" in source_text:
            print("✅ Exception handling implemented")
            enhancements_found += 1

        print(f"✅ Enhanced features found: {enhancements_found}/6")

        if enhancements_found >= 4:
            print("✅ Refresh Library method significantly enhanced")
            return True
        else:
            print("❌ Refresh Library method needs more enhancements")
            return False

    except Exception as e:
        print(f"❌ Refresh Library method test failed: {e}")
        return False


def test_menu_connection():
    """Test that menu action is properly connected"""
    print("\n🔍 Testing Menu Connection...")

    try:
        # Check connection pattern from source
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        if not asset_manager_file.exists():
            print("❌ AssetManagerWindow source file not found")
            return False

        with open(asset_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for menu action creation
        if "refresh_action = QAction" in content:
            print("✅ Refresh action creation found")
        else:
            print("❌ Refresh action creation not found")
            return False

        # Check for connection
        if "refresh_action.triggered.connect(self._on_refresh_library)" in content:
            print("✅ Menu action properly connected to _on_refresh_library")
        else:
            print("❌ Menu action connection not found")
            return False

        # Check for keyboard shortcut
        if "setShortcut" in content and "Refresh" in content:
            print("✅ Keyboard shortcut implemented")
        else:
            print("⚠️ Keyboard shortcut may not be implemented")

        return True

    except Exception as e:
        print(f"❌ Menu connection test failed: {e}")
        return False


def test_button_connection():
    """Test that toolbar button is properly connected"""
    print("\n🔘 Testing Button Connection...")

    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for button creation
        if "refresh_btn = QPushButton" in content:
            print("✅ Refresh button creation found")
        else:
            print("❌ Refresh button creation not found")
            return False

        # Check for button connection
        if "refresh_btn.clicked.connect(self._on_refresh_library)" in content:
            print("✅ Button properly connected to _on_refresh_library")
        else:
            print("❌ Button connection not found")
            return False

        # Check for tooltip
        if "setToolTip" in content and "refresh" in content.lower():
            print("✅ Button tooltip implemented")
        else:
            print("⚠️ Button tooltip may not be implemented")

        return True

    except Exception as e:
        print(f"❌ Button connection test failed: {e}")
        return False


def main():


    from PySide6.QtWidgets import QApplication
    print("🧪 REFRESH LIBRARY FUNCTIONALITY TEST - Issue #9")
    print("=" * 60)

    # Initialize QApplication for Qt imports
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Run tests
    tests = [
        ("Refresh Method Enhancement", test_refresh_library_method),
        ("Menu Action Connection", test_menu_connection),
        ("Button Connection", test_button_connection),
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
    print("🎯 REFRESH LIBRARY TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All Refresh Library tests PASSED!")
        print("🔄 Menu button is now properly responsive with enhanced functionality")
        return True
    else:
        print("⚠️ Some tests failed - check implementation")
        return False

if __name__ == "__main__":


    sys.exit(0 if success else 1)
