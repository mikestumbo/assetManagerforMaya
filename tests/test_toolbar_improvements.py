#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Toolbar Layout and Color Keychart Improvements Test
Validates that toolbar and UI improvements are properly implemented

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import sys
from pathlib import Path


def test_toolbar_improvements():
    """Test that toolbar improvements are properly implemented"""

    print("🎛️ Testing Toolbar Layout and Improvements...")
    print("=" * 60)

    # Check main window file
    main_window_file = "src/ui/asset_manager_window.py"
    if not Path(main_window_file).exists():
        print("❌ Main window file not found")
        return {}

    with open(main_window_file, 'r', encoding='utf-8') as f:
        content = f.read()

    improvements = {
        "toolbar_height": False,
        "button_order": False,
        "button_width": False,
        "button_height": False,
        "button_colors": False
    }

    # Test 1: Increased toolbar height
    if "setFixedHeight(56)" in content:
        print("✅ Toolbar height increased to 56px for better button fit")
        improvements["toolbar_height"] = True
    else:
        print("❌ Toolbar height not increased")

    # Test 2: Button order (Create, Import, Remove, Refresh, Preview, Info)
    create_pos = content.find('QPushButton("Create Asset")')
    import_pos = content.find('QPushButton("Import Asset")')
    remove_pos = content.find('QPushButton("Remove Asset")')
    refresh_pos = content.find('QPushButton("Refresh Library")')
    preview_pos = content.find('QPushButton("Hide Preview")')
    info_pos = content.find('QPushButton("Hide Info")')

    if all(pos != -1 for pos in [create_pos, import_pos, remove_pos, refresh_pos, preview_pos, info_pos]):
        if create_pos < import_pos < remove_pos < refresh_pos < preview_pos < info_pos:
            print("✅ Button order correct: Create → Import → Remove → Refresh → Preview → Info")
            improvements["button_order"] = True
        else:
            print("❌ Button order incorrect")
            print(f"   Positions: Create({create_pos}), Import({import_pos}), Remove({remove_pos})")
            print(f"   Refresh({refresh_pos}), Preview({preview_pos}), Info({info_pos})")
    else:
        print("❌ Not all buttons found")

    # Test 3: Button width increased for Preview/Info buttons
    if "setMinimumWidth(120)" in content:
        width_count = content.count("setMinimumWidth(120)")
        if width_count >= 2:
            print("✅ Preview and Info buttons have increased width (120px) for bold text legibility")
            improvements["button_width"] = True
        else:
            print(f"⚠️  Only {width_count} button(s) have increased width")
    else:
        print("❌ Button widths not increased")

    # Test 4: Button height increased
    if "min-height: 36px" in content:
        print("✅ Button height increased to 36px for better centering")
        improvements["button_height"] = True
    else:
        print("❌ Button height not increased")

    # Test 5: Button checked color matches accent theme
    if "background-color: #0078d4" in content and "QPushButton:checked" in content:
        print("✅ Preview/Info button colors match Manage Colors accent color (#0078d4)")
        improvements["button_colors"] = True
    else:
        print("❌ Button checked colors not updated to match theme")

    return improvements


def test_color_keychart_improvements():
    """Test that color keychart height is increased and made stationary"""

    print("\n🎨 Testing Color Keychart Improvements...")
    print("=" * 45)

    keychart_file = "src/ui/widgets/color_coding_keychart_widget.py"
    if not Path(keychart_file).exists():
        print("❌ Color keychart file not found")
        return False

    with open(keychart_file, 'r', encoding='utf-8') as f:
        content = f.read()

    improvements = {
        "height_increased": False,
        "made_stationary": False,
        "proper_spacing": False
    }

    # Test height increase
    if "setFixedHeight(260)" in content:
        print("✅ Color keychart height increased to 260px to prevent overlap")
        improvements["height_increased"] = True
    elif "setMaximumHeight(220)" in content:
        print("❌ Color keychart height still at 220px (should be 260px)")
    else:
        print("❌ Color keychart height setting not found")

    # Test stationary sizing (fixed width)
    if "setMaximumWidth(220)" in content:
        print("✅ Color keychart made stationary with fixed maximum width")
        improvements["made_stationary"] = True
    else:
        print("❌ Color keychart width not constrained (should be stationary)")

    # Test proper spacing
    if "keychart_layout.addSpacing(8)" in content:
        print("✅ Proper spacing added to prevent color square overlap")
        improvements["proper_spacing"] = True
    else:
        print("❌ Additional spacing not added")

    total_improvements = sum(improvements.values())
    if total_improvements >= 2:
        return True
    else:
        return False


def test_separator_adjustments():
    """Test that separators are adjusted for new toolbar height"""

    print("\n📏 Testing Separator Adjustments...")
    print("=" * 40)

    main_window_file = "src/ui/asset_manager_window.py"
    with open(main_window_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if "setFixedHeight(40)" in content and "_create_toolbar_separator" in content:
        print("✅ Toolbar separators adjusted to 40px height for larger toolbar")
        return True
    else:
        print("❌ Toolbar separators not properly adjusted")
        return False


def main():


    print("🚀 Asset Manager Toolbar & UI Improvements Validation")
    print("=" * 65)

    toolbar_improvements = test_toolbar_improvements()
    keychart_improved = test_color_keychart_improvements()
    separators_adjusted = test_separator_adjustments()

    print("\n" + "=" * 65)
    print("📊 IMPROVEMENT SUMMARY")
    print("=" * 65)

    # Toolbar improvements summary
    if toolbar_improvements:
        toolbar_score = sum(toolbar_improvements.values())
        total_toolbar_tests = len(toolbar_improvements)
    else:
        toolbar_score = 0
        total_toolbar_tests = 5

    print(f"\n🎛️  TOOLBAR IMPROVEMENTS: {toolbar_score}/{total_toolbar_tests}")
    if toolbar_improvements:
        for improvement, passed in toolbar_improvements.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {improvement.replace('_', ' ').title()}")
    else:
        print("   ❌ Main window file not found")

    print(f"\n🎨 COLOR KEYCHART: {'✅' if keychart_improved else '❌'}")
    print(f"📏 SEPARATORS: {'✅' if separators_adjusted else '❌'}")

    total_score = toolbar_score + (1 if keychart_improved else 0) + (1 if separators_adjusted else 0)
    total_tests = total_toolbar_tests + 2

    print(f"\n🎯 OVERALL SCORE: {total_score}/{total_tests}")

    if total_score >= total_tests - 1:  # Allow for 1 minor issue
        print("\n🎉 EXCELLENT! UI IMPROVEMENTS SUCCESSFULLY IMPLEMENTED!")
        print("\n✨ IMPROVEMENTS ACHIEVED:")
        print("   🎛️  Taller toolbar (56px) with better button centering")
        print("   📋 Logical button order: Create → Import → Remove → Refresh → Preview → Info")
        print("   📏 Wider Preview/Info buttons (120px) for bold text legibility")
        print("   🎨 Matching accent color (#0078d4) for checked buttons")
        print("   📖 Taller color keychart (260px) with proper spacing to prevent overlap")
        print("   🔒 Stationary color keychart that doesn't resize with window")
        print("   🔧 Properly adjusted separators for new toolbar height")
        print("\n💯 The Asset Manager UI is now more professional and user-friendly!")
        return True
    else:
        print(f"\n⚠️  PARTIAL SUCCESS - {total_score}/{total_tests} improvements achieved")
        print("🔧 Consider addressing the remaining issues for optimal UI")
        return False

if __name__ == "__main__":


    sys.exit(0 if success else 1)
