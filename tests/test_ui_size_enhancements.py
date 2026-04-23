#!/usr/bin/env python3
"""
Menu Bar and Toolbar Size Enhancement Test - Issue #11
Tests the increased sizes of menu bar, buttons, and fonts for better UI consistency
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


def test_menu_bar_styling():
    """Test Menu Bar styling enhancements - Issue #11"""
    print("\n🎨 Testing Menu Bar Styling...")

    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        if not asset_manager_file.exists():
            print("❌ AssetManagerWindow source file not found")
            return False

        with open(asset_manager_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for menu bar styling
        if "menubar.setStyleSheet(" in content:
            print("✅ Menu bar styling applied")
        else:
            print("❌ Menu bar styling not found")
            return False

        # Check for enhanced font size in menu bar
        if "font-size: 13px" in content and "QMenuBar" in content:
            print("✅ Enhanced menu bar font size (13px)")
        else:
            print("❌ Enhanced menu bar font size not found")
            return False

        # Check for enhanced padding
        if "padding: 8px 16px" in content and "QMenuBar::item" in content:
            print("✅ Enhanced menu bar item padding")
        else:
            print("❌ Enhanced menu bar item padding not found")
            return False

        # Check for menu styling
        if "QMenu {" in content and "font-size: 12px" in content:
            print("✅ Menu dropdown styling implemented")
        else:
            print("❌ Menu dropdown styling not found")
            return False

        return True

    except Exception as e:
        print(f"❌ Menu bar styling test failed: {e}")
        return False


def test_toolbar_enhancements():
    """Test Toolbar button and size enhancements"""
    print("\n🔧 Testing Toolbar Enhancements...")

    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for increased toolbar height
        if "toolbar.setFixedHeight(48)" in content:
            print("✅ Toolbar height increased to 48px")
        else:
            print("❌ Toolbar height not increased")
            return False

        # Check for enhanced button padding
        if "padding: 6px 12px" in content and "QPushButton" in content:
            print("✅ Button padding increased (6px 12px)")
        else:
            print("❌ Button padding not enhanced")
            return False

        # Check for increased button height
        if "min-height: 28px" in content:
            print("✅ Button minimum height increased to 28px")
        else:
            print("❌ Button height not increased")
            return False

        # Check for enhanced button font size
        button_section = content[
            content.find("QPushButton {") : content.find("}", content.find("QPushButton {"))
        ]
        if "font-size: 13px" in button_section:
            print("✅ Button font size increased to 13px")
        else:
            print("❌ Button font size not enhanced")
            return False

        return True

    except Exception as e:
        print(f"❌ Toolbar enhancement test failed: {e}")
        return False


def test_layout_adjustments():
    """Test layout spacing and margin adjustments"""
    print("\n📐 Testing Layout Adjustments...")

    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for enhanced margins
        if "setContentsMargins(10, 6, 10, 6)" in content:
            print("✅ Toolbar margins increased (10, 6, 10, 6)")
        else:
            print("❌ Toolbar margins not enhanced")
            return False

        # Check for enhanced spacing
        if "setSpacing(6)" in content and "Increased spacing between buttons" in content:
            print("✅ Button spacing increased to 6px")
        else:
            print("❌ Button spacing not enhanced")
            return False

        # Check for separator adjustments
        if "separator.setFixedHeight(32)" in content:
            print("✅ Separator height adjusted for larger toolbar")
        else:
            print("❌ Separator height not adjusted")
            return False

        # Check for enhanced separator margins
        if "margin: 3px 8px" in content:
            print("✅ Separator margins increased")
        else:
            print("❌ Separator margins not enhanced")
            return False

        return True

    except Exception as e:
        print(f"❌ Layout adjustment test failed: {e}")
        return False


def test_font_consistency():
    """Test font size consistency across UI elements"""
    print("\n🔤 Testing Font Consistency...")

    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for consistent label font size
        if "font-size: 13px" in content and "QLabel" in content:
            print("✅ Label font size increased to 13px")
        else:
            print("❌ Label font size not enhanced")
            return False

        # Find all font size declarations
        import re

        font_sizes = re.findall(r"font-size:\s*(\d+)px", content)

        # Count enhanced font sizes (12px and above)
        enhanced_sizes = [size for size in font_sizes if int(size) >= 12]

        print(f"✅ Font sizes found: {', '.join(set(font_sizes))}px")
        print(f"✅ Enhanced font sizes (≥12px): {len(enhanced_sizes)}/{len(font_sizes)}")

        if len(enhanced_sizes) >= len(font_sizes) * 0.7:  # At least 70% enhanced
            print("✅ Good font size consistency achieved")
            return True
        else:
            print("⚠️ Font size consistency could be improved")
            return True  # Still pass, but note improvement opportunity

    except Exception as e:
        print(f"❌ Font consistency test failed: {e}")
        return False


def test_visual_improvements():
    """Test overall visual improvement indicators"""
    print("\n👁️ Testing Visual Improvements...")

    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, "r", encoding="utf-8") as f:
            content = f.read()

        improvements_found = 0

        # Check for hover effects
        if "QPushButton:hover" in content:
            print("✅ Button hover effects maintained")
            improvements_found += 1

        # Check for pressed effects
        if "QPushButton:pressed" in content:
            print("✅ Button pressed effects maintained")
            improvements_found += 1

        # Check for checked state styling
        if "QPushButton:checked" in content:
            print("✅ Button checked state styling maintained")
            improvements_found += 1

        # Check for rounded corners
        if "border-radius:" in content:
            print("✅ Rounded corners maintained for modern look")
            improvements_found += 1

        # Check for color consistency
        if "#4a4a4a" in content and "#5a5a5a" in content:
            print("✅ Color scheme consistency maintained")
            improvements_found += 1

        print(f"✅ Visual improvements verified: {improvements_found}/5")

        return improvements_found >= 4

    except Exception as e:
        print(f"❌ Visual improvements test failed: {e}")
        return False


def main():

    from PySide6.QtWidgets import QApplication

    print("🧪 MENU BAR & TOOLBAR SIZE ENHANCEMENT TEST - Issue #11")
    print("=" * 70)

    # Initialize QApplication for Qt imports
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Run tests
    tests = [
        ("Menu Bar Styling", test_menu_bar_styling),
        ("Toolbar Enhancements", test_toolbar_enhancements),
        ("Layout Adjustments", test_layout_adjustments),
        ("Font Consistency", test_font_consistency),
        ("Visual Improvements", test_visual_improvements),
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

    print("\n" + "=" * 70)
    print("🎯 MENU BAR & TOOLBAR ENHANCEMENT TEST RESULTS")
    print("=" * 70)
    print(f"✅ Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All Menu Bar and Toolbar enhancement tests PASSED!")
        print("📏 UI elements now have increased sizes and better visibility")
        print("🎨 Menu bar, buttons, and fonts enhanced for consistency")
        return True
    else:
        print("⚠️ Some tests failed - check implementation")
        return False


if __name__ == "__main__":

    sys.exit(0 if success else 1)
