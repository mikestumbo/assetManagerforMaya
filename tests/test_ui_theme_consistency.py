#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Theme Consistency Test for Asset Manager
Tests that all UI components use unified theme styling

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import sys
from pathlib import Path


def test_theme_import_consistency():
    """Test that all UI components import and use the unified theme"""

    # Files that should use unified theme
    ui_files = [
        "src/ui/dialogs/color_coding_manager_dialog.py",
        "src/ui/dialogs/tag_manager_dialog.py",
        "src/ui/collection_manager_dialog.py",
        "src/ui/widgets/color_coding_keychart_widget.py"
    ]

    print("🎨 Testing UI Theme Consistency...")
    print("=" * 50)

    success = True

    for file_path in ui_files:
        print(f"\n📁 Testing: {file_path}")

        if not Path(file_path).exists():
            print(f"❌ File not found: {file_path}")
            success = False
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Test 1: Theme import
        if "from ..theme import UITheme" in content or "from .theme import UITheme" in content:
            print("✅ UITheme imported")
        else:
            print("❌ UITheme not imported")
            success = False

        # Test 2: Dialog stylesheet usage
        if "UITheme.get_dialog_stylesheet()" in content:
            print("✅ Unified dialog stylesheet applied")
        else:
            print("⚠️  Unified dialog stylesheet not found (may be widget-only)")

        # Test 3: Property-based styling
        if 'setProperty("title", True)' in content or 'setProperty("accent", True)' in content:
            print("✅ Theme property styling used")
        else:
            print("⚠️  Theme property styling not found")

        # Test 4: Legacy styling removed
        legacy_patterns = [
            "color: #2c3e50",
            "color: #7f8c8d",
            "background-color: #3498db",
            "background-color: #f8f9fa"
        ]

        legacy_found = False
        for pattern in legacy_patterns:
            if pattern in content:
                print(f"❌ Legacy styling found: {pattern}")
                legacy_found = True
                success = False

        if not legacy_found:
            print("✅ No legacy styling found")

    # Test 5: Theme constants file exists
    print("\n📁 Testing: src/ui/theme.py")
    if Path("src/ui/theme.py").exists():
        print("✅ UITheme constants file exists")

        with open("src/ui/theme.py", 'r', encoding='utf-8') as f:
            theme_content = f.read()

        # Check for required theme components
        required_components = [
            "class UITheme:",
            "PRIMARY_BG = \"#4a4a4a\"",
            "TEXT_PRIMARY = \"#ffffff\"",
            "get_dialog_stylesheet",
            "get_color_preview_style"
        ]

        for component in required_components:
            if component in theme_content:
                print(f"✅ Theme component: {component}")
            else:
                print(f"❌ Missing theme component: {component}")
                success = False
    else:
        print("❌ UITheme constants file missing")
        success = False

    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL UI THEME TESTS PASSED!")
        print("✨ UI components now have consistent, professional styling")
        print("🎨 All dialogs match the main Asset Manager theme")
    else:
        print("❌ Some UI theme tests failed")
        print("🔧 Please review the issues above")

    return success


def test_color_scheme_consistency():
    """Test that color schemes are consistent across components"""

    print("\n🌈 Testing Color Scheme Consistency...")
    print("=" * 50)

    theme_file = "src/ui/theme.py"
    if not Path(theme_file).exists():
        print("❌ Theme file not found")
        return False

    with open(theme_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check for main color consistency
    expected_colors = {
        "#4a4a4a": "Primary background",
        "#5a5a5a": "Secondary background",
        "#ffffff": "Primary text",
        "#cccccc": "Secondary text",
        "#666666": "Border color",
        "#0078d4": "Accent color"
    }

    success = True
    for color, description in expected_colors.items():
        if color in content:
            print(f"✅ {description}: {color}")
        else:
            print(f"❌ Missing {description}: {color}")
            success = False

    return success


def main():


    print("🚀 Asset Manager UI Theme Consistency Validation")
    print("=" * 60)

    test1_success = test_theme_import_consistency()
    test2_success = test_color_scheme_consistency()

    overall_success = test1_success and test2_success

    print("\n" + "=" * 60)
    if overall_success:
        print("🎉 ALL UI THEME CONSISTENCY TESTS PASSED!")
        print("\n🎯 Benefits Achieved:")
        print("  ✅ Unified professional dark theme")
        print("  ✅ Consistent colors across all dialogs")
        print("  ✅ Cohesive user experience")
        print("  ✅ Maintainable centralized styling")
        print("  ✅ Professional Asset Manager appearance")
    else:
        print("❌ SOME TESTS FAILED - Please review the issues above")

    return overall_success

if __name__ == "__main__":
    success = run_ui_theme_tests()
    sys.exit(0 if success else 1)
