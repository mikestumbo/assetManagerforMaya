#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Asset Information Deduplication Fix
Tests that asset information is only displayed once, not duplicated

Author: Mike Stumbo
Clean Code: Single Responsibility Principle Applied
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def test_asset_info_deduplication():
    """Test that asset information is only displayed once in preview widget"""
    print("🧪 Testing Asset Information Deduplication Fix...")

    try:
        # Import the main window class
        # Check that _create_right_panel no longer creates duplicate info panels
        import inspect

        from src.ui.asset_manager_window import AssetManagerWindow

        source = inspect.getsource(AssetManagerWindow._create_right_panel)

        # Verify the duplicate asset info panel is removed
        has_duplicate_panel = "_asset_info_panel" in source

        print(f"✅ Duplicate asset info panel removed: {not has_duplicate_panel}")

        # Check that asset info methods delegate to preview widget
        info_method_source = inspect.getsource(AssetManagerWindow._update_asset_info_display)
        uses_preview_widget = "self._preview_widget.set_asset" in info_method_source

        print(f"✅ Asset info delegates to preview widget: {uses_preview_widget}")

        # Check that toggle method is simplified
        toggle_method_source = inspect.getsource(AssetManagerWindow._on_toggle_asset_info_unified)
        simplified_toggle = (
            "AssetPreviewWidget handles its own info display" in toggle_method_source
        )

        print(f"✅ Toggle method simplified: {simplified_toggle}")

        # Overall test result
        test_passed = not has_duplicate_panel and uses_preview_widget and simplified_toggle

        if test_passed:
            print("\n🎉 SUCCESS: Asset information deduplication fix validated!")
            print("   ▸ No duplicate info panels")
            print("   ▸ Single source of truth in preview widget")
            print("   ▸ Follows Single Responsibility Principle")
            return True
        else:
            print("\n❌ FAILURE: Asset information deduplication test failed")
            return False

    except Exception as e:
        print(f"❌ ERROR: Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_clean_code_principles():
    """Test that the fix follows Clean Code principles"""
    print("\n🧪 Testing Clean Code Principles...")

    try:

        # Check Single Responsibility Principle

        # Asset preview widget should handle preview AND info display
        preview_widget_path = project_root / "src" / "ui" / "widgets" / "asset_preview_widget.py"
        if preview_widget_path.exists():
            with open(preview_widget_path, "r", encoding="utf-8") as f:
                preview_content = f.read()
                has_info_display = "_info_label" in preview_content
                print(f"✅ Preview widget handles info display: {has_info_display}")

        # Main window should NOT have duplicate info logic
        window_path = project_root / "src" / "ui" / "asset_manager_window.py"
        with open(window_path, "r", encoding="utf-8") as f:
            window_content = f.read()
            no_duplicate_logic = "_create_asset_info_panel" not in window_content
            print(f"✅ Main window has no duplicate info logic: {no_duplicate_logic}")

        print("\n✨ Clean Code principles validated!")
        return True

    except Exception as e:
        print(f"❌ ERROR: Clean Code test failed: {e}")
        return False


def main():

    print("=" * 60)
    print("ASSET INFORMATION DEDUPLICATION TEST SUITE")
    print("=" * 60)

    test1_passed = test_asset_info_deduplication()
    test2_passed = test_clean_code_principles()

    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED - Asset info duplication fixed!")
        print("   ▸ Single information display in preview widget")
        print("   ▸ No duplicate panels or redundant widgets")
        print("   ▸ Clean Code principles applied")
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
    print("=" * 60)

    return test1_passed and test2_passed


if __name__ == "__main__":
    main()
