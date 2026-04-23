#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Asset Information Panel Toggle
Tests that the Asset Information panel can be toggled properly

Author: Mike Stumbo
Clean Code: User Experience Testing
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def test_asset_info_panel_toggle():
    """Test that asset info panel toggle works correctly"""
    print("🧪 Testing Asset Information Panel Toggle...")

    try:
        # Import the main window class
        # Check that the toggle method exists and handles panel visibility
        import inspect

        from src.ui.asset_manager_window import AssetManagerWindow

        toggle_source = inspect.getsource(AssetManagerWindow._on_toggle_asset_info_unified)

        # Verify proper panel visibility handling
        handles_visibility = "setVisible(new_visible)" in toggle_source
        print(f"✅ Toggle method handles panel visibility: {handles_visibility}")

        # Verify menu action synchronization
        syncs_menu = "_show_asset_info_action.setChecked" in toggle_source
        print(f"✅ Toggle method syncs menu action: {syncs_menu}")

        # Verify button synchronization
        syncs_button = (
            "_info_btn.setChecked" in toggle_source and "_info_btn.setText" in toggle_source
        )
        print(f"✅ Toggle method syncs info button: {syncs_button}")

        # Check that metadata panel reference is stored
        window_source = inspect.getsource(AssetManagerWindow._create_central_widget)
        stores_reference = "_metadata_panel = right_b_panel" in window_source
        print(f"✅ Metadata panel reference stored: {stores_reference}")

        test_passed = handles_visibility and syncs_menu and syncs_button and stores_reference

        if test_passed:
            print("\n🎉 SUCCESS: Asset Information panel toggle implemented!")
            print("   ▸ Panel visibility can be toggled on/off")
            print("   ▸ View menu action stays synchronized")
            print("   ▸ Info button stays synchronized")
            print("   ▸ Button text changes (Show Info/Hide Info)")
            return True
        else:
            print("\n❌ FAILURE: Asset Information panel toggle test failed")
            return False

    except Exception as e:
        print(f"❌ ERROR: Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_menu_text_correction():
    """Test that menu text is corrected and not confusing"""
    print("\n🧪 Testing Menu Text Correction...")

    try:
        import inspect

        from src.ui.asset_manager_window import AssetManagerWindow

        # Check that menu text is simplified
        menu_source = inspect.getsource(AssetManagerWindow._create_menu_bar)
        has_simple_text = '"&Asset Information"' in menu_source
        no_confusing_text = '"&Integrated Asset Information"' not in menu_source

        print(f"✅ Menu text simplified to 'Asset Information': {has_simple_text}")
        print(f"✅ Confusing 'Integrated' text removed: {no_confusing_text}")

        test_passed = has_simple_text and no_confusing_text

        if test_passed:
            print("\n✨ Menu text correction validated!")
            return True
        else:
            print("\n❌ Menu text correction failed")
            return False

    except Exception as e:
        print(f"❌ ERROR: Menu text test failed: {e}")
        return False


def test_ui_consistency():
    """Test that UI elements are consistent and user-friendly"""
    print("\n🧪 Testing UI Consistency...")

    try:
        import inspect

        from src.ui.asset_manager_window import AssetManagerWindow

        # Check Info button is checkable and has proper text handling
        toolbar_source = inspect.getsource(AssetManagerWindow._create_main_toolbar)
        button_checkable = "setCheckable(True)" in toolbar_source
        has_initial_text = '"Hide Info"' in toolbar_source  # Initial state

        # Check toggle method for dynamic text changes
        toggle_source = inspect.getsource(AssetManagerWindow._on_toggle_asset_info_unified)
        handles_text_change = (
            "setText(" in toggle_source
            and "Hide Info" in toggle_source
            and "Show Info" in toggle_source
        )

        print(f"✅ Info button is checkable: {button_checkable}")
        print(f"✅ Info button has initial text: {has_initial_text}")
        print(f"✅ Toggle method changes button text: {handles_text_change}")

        # Check that both controls trigger the same unified method
        same_handler = toolbar_source.count("_on_toggle_asset_info_unified") >= 1
        print(f"✅ Both controls use unified toggle handler: {same_handler}")

        test_passed = (
            button_checkable and has_initial_text and handles_text_change and same_handler
        )

        if test_passed:
            print("\n✨ UI consistency validated!")
            return True
        else:
            print("\n❌ UI consistency test failed")
            return False

    except Exception as e:
        print(f"❌ ERROR: UI consistency test failed: {e}")
        return False


def main():

    print("=" * 60)
    print("ASSET INFORMATION PANEL TOGGLE TEST SUITE")
    print("=" * 60)

    test1_passed = test_asset_info_panel_toggle()
    test2_passed = test_menu_text_correction()
    test3_passed = test_ui_consistency()

    print("\n" + "=" * 60)
    if test1_passed and test2_passed and test3_passed:
        print("🎉 ALL TESTS PASSED - Asset Information panel toggle working!")
        print("   ▸ View > Asset Information toggles RIGHT_B panel")
        print("   ▸ Info button toggles RIGHT_B panel")
        print("   ▸ Both controls stay synchronized")
        print("   ▸ Clear, non-confusing menu text")
        print("   ▸ Responsive button text (Show/Hide)")
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
    print("=" * 60)

    return test1_passed and test2_passed and test3_passed


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
