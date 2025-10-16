#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test 4-Panel Layout Implementation
Tests the new LEFT | CENTER | RIGHT_A | RIGHT_B panel architecture

Author: Mike Stumbo
Clean Code: Separation of Concerns Applied
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_4_panel_architecture():
    """Test that the 4-panel layout is properly implemented"""
    print("🧪 Testing 4-Panel Layout Architecture...")
    
    try:
        # Import the main window class
        from src.ui.asset_manager_window import AssetManagerWindow
        
        # Check that all 4 panel creation methods exist
        import inspect
        
        # LEFT Panel
        has_left_controls = hasattr(AssetManagerWindow, '_create_left_controls_panel')
        print(f"✅ LEFT controls panel method exists: {has_left_controls}")
        
        # CENTER Panel
        has_center_library = hasattr(AssetManagerWindow, '_create_center_library_panel')
        print(f"✅ CENTER library panel method exists: {has_center_library}")
        
        # RIGHT_A Panel
        has_right_a_preview = hasattr(AssetManagerWindow, '_create_right_a_preview_panel')
        print(f"✅ RIGHT_A preview panel method exists: {has_right_a_preview}")
        
        # RIGHT_B Panel
        has_right_b_metadata = hasattr(AssetManagerWindow, '_create_right_b_metadata_panel')
        print(f"✅ RIGHT_B metadata panel method exists: {has_right_b_metadata}")
        
        # Check that old 2-panel methods are removed
        has_old_left = hasattr(AssetManagerWindow, '_create_left_panel')
        has_old_right = hasattr(AssetManagerWindow, '_create_right_panel')
        print(f"✅ Old left panel method removed: {not has_old_left}")
        print(f"✅ Old right panel method removed: {not has_old_right}")
        
        # Overall test result
        all_panels_exist = (has_left_controls and has_center_library and 
                           has_right_a_preview and has_right_b_metadata)
        old_methods_removed = (not has_old_left and not has_old_right)
        
        test_passed = all_panels_exist and old_methods_removed
        
        if test_passed:
            print("\n🎉 SUCCESS: 4-Panel architecture implemented!")
            print("   ▸ LEFT: Search, Tags, Collections, Color Keychart")
            print("   ▸ CENTER: Asset Library")
            print("   ▸ RIGHT_A: Asset Preview")
            print("   ▸ RIGHT_B: Asset Information/Metadata")
            return True
        else:
            print("\n❌ FAILURE: 4-Panel architecture test failed")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_panel_contents():
    """Test that each panel contains the correct components"""
    print("\n🧪 Testing Panel Contents...")
    
    try:
        from src.ui.asset_manager_window import AssetManagerWindow
        import inspect
        
        # Check LEFT panel contents (search removed to avoid duplication)
        left_source = inspect.getsource(AssetManagerWindow._create_left_controls_panel)
        has_tags = "Tag Management" in left_source
        has_collections = "Collections" in left_source
        has_keychart = "ColorCodingKeychartWidget" in left_source
        no_duplicate_search = "Search Assets" not in left_source
        
        print(f"✅ LEFT panel has tag management: {has_tags}")
        print(f"✅ LEFT panel has collections: {has_collections}")
        print(f"✅ LEFT panel has color keychart: {has_keychart}")
        print(f"✅ LEFT panel avoids duplicate search: {no_duplicate_search}")
        
        # Check CENTER panel contents
        center_source = inspect.getsource(AssetManagerWindow._create_center_library_panel)
        has_library = "AssetLibraryWidget" in center_source
        print(f"✅ CENTER panel has asset library: {has_library}")
        
        # Check RIGHT_A panel contents
        right_a_source = inspect.getsource(AssetManagerWindow._create_right_a_preview_panel)
        has_preview = "AssetPreviewWidget" in right_a_source
        print(f"✅ RIGHT_A panel has preview widget: {has_preview}")
        
        # Check RIGHT_B panel contents
        right_b_source = inspect.getsource(AssetManagerWindow._create_right_b_metadata_panel)
        has_metadata = "_metadata_label" in right_b_source
        print(f"✅ RIGHT_B panel has metadata display: {has_metadata}")
        
        all_contents_correct = (has_tags and has_collections and has_keychart and no_duplicate_search and
                               has_library and has_preview and has_metadata)
        
        if all_contents_correct:
            print("\n✨ Panel contents validated!")
            return True
        else:
            print("\n❌ Some panel contents missing")
            return False
        
    except Exception as e:
        print(f"❌ ERROR: Panel contents test failed: {e}")
        return False

def test_separation_of_concerns():
    """Test that separation of concerns is properly implemented"""
    print("\n🧪 Testing Separation of Concerns...")
    
    try:
        from src.ui.asset_manager_window import AssetManagerWindow
        import inspect
        
        # Check that metadata is handled in RIGHT_B panel
        update_method = inspect.getsource(AssetManagerWindow._update_asset_info_display)
        uses_metadata_label = "_metadata_label" in update_method
        print(f"✅ Metadata updates use dedicated RIGHT_B panel: {uses_metadata_label}")
        
        # Check that asset info request handler uses both panels
        info_method = inspect.getsource(AssetManagerWindow._on_asset_info_requested)
        updates_both = "_preview_widget" in info_method and "_update_asset_info_display" in info_method
        print(f"✅ Asset info handler updates both RIGHT_A and RIGHT_B: {updates_both}")
        
        # Check that layout uses nested splitters for 4-panel design
        window_file = project_root / "src" / "ui" / "asset_manager_window.py"
        with open(window_file, 'r', encoding='utf-8') as f:
            window_content = f.read()
            has_main_splitter = "main_splitter" in window_content
            has_right_splitter = "right_splitter" in window_content
            print(f"✅ Uses nested splitters for 4-panel layout: {has_main_splitter and has_right_splitter}")
        
        test_passed = uses_metadata_label and updates_both and has_main_splitter and has_right_splitter
        
        if test_passed:
            print("\n✨ Separation of concerns validated!")
            return True
        else:
            print("\n❌ Separation of concerns test failed")
            return False
        
    except Exception as e:
        print(f"❌ ERROR: Separation of concerns test failed: {e}")
        return False

def main():
    """Run all 4-panel layout tests"""
    print("=" * 60)
    print("4-PANEL LAYOUT TEST SUITE")
    print("=" * 60)
    
    test1_passed = test_4_panel_architecture()
    test2_passed = test_panel_contents()
    test3_passed = test_separation_of_concerns()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed and test3_passed:
        print("🎉 ALL TESTS PASSED - 4-Panel layout implemented!")
        print("   ▸ LEFT: Controls panel with search, tags, collections, keychart")
        print("   ▸ CENTER: Dedicated asset library panel")
        print("   ▸ RIGHT_A: Asset preview panel")
        print("   ▸ RIGHT_B: Asset information/metadata panel")
        print("   ▸ Clean separation of concerns")
        print("   ▸ Improved UI organization")
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
    print("=" * 60)
    
    return test1_passed and test2_passed and test3_passed

if __name__ == "__main__":
    main()
