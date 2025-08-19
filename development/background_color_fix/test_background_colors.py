#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Background Color Fix Validation Test for Asset Manager v1.2.0
Tests that asset type background colors are now visible in the UI
"""

import os
import sys

def test_background_color_css_fix():
    """Test that CSS stylesheets no longer override background colors"""
    print("🔍 Testing Background Color CSS Fix...")
    
    # Check if the file exists
    asset_manager_path = "assetManager.py"
    if not os.path.exists(asset_manager_path):
        print("❌ assetManager.py not found!")
        return False
    
    # Read the file content
    with open(asset_manager_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Test 1: Check that "background: transparent" has been removed/commented from main asset list
    # Look for the specific section more precisely
    main_style_start = content.find("self.asset_list.setStyleSheet(")
    main_style_end = content.find('""")', main_style_start) + 4
    
    if main_style_start != -1 and main_style_end != -1:
        main_list_style_section = content[main_style_start:main_style_end]
        
        # Count only actual CSS declarations, not comments
        lines = main_list_style_section.split('\n')
        transparent_count = 0
        for line in lines:
            if 'background: transparent;' in line and not line.strip().startswith('/*') and not line.strip().startswith('//'):
                transparent_count += 1
        
        if transparent_count > 0:
            print(f"❌ Found {transparent_count} active 'background: transparent' declarations in main asset list styling")
            # Show the problematic lines
            for line_num, line in enumerate(lines):
                if 'background: transparent;' in line and not line.strip().startswith('/*'):
                    print(f"   Line {line_num}: {line.strip()}")
            return False
        else:
            print("✅ Main asset list styling no longer overrides background colors")
    
    # Test 2: Check collection tab styling
    collection_style_start = content.find("collection_asset_list.setStyleSheet(")
    if collection_style_start != -1:
        collection_style_end = content.find('""")', collection_style_start) + 4
        collection_style_section = content[collection_style_start:collection_style_end]
        
        lines = collection_style_section.split('\n')
        collection_transparent_count = 0
        for line in lines:
            if 'background: transparent;' in line and not line.strip().startswith('/*') and not line.strip().startswith('//'):
                collection_transparent_count += 1
        
        if collection_transparent_count > 0:
            print(f"❌ Found {collection_transparent_count} active 'background: transparent' declarations in collection tab styling")
            return False
        else:
            print("✅ Collection tab styling no longer overrides background colors")
    
    # Test 3: Check dialog styling  
    dialog_style_start = content.find("asset_list_widget.setStyleSheet(")
    if dialog_style_start != -1:
        dialog_style_end = content.find('""")', dialog_style_start) + 4
        dialog_style_section = content[dialog_style_start:dialog_style_end]
        
        lines = dialog_style_section.split('\n')
        dialog_transparent_count = 0
        for line in lines:
            if 'background: transparent;' in line and not line.strip().startswith('/*') and not line.strip().startswith('//'):
                dialog_transparent_count += 1
        
        if dialog_transparent_count > 0:
            print(f"❌ Found {dialog_transparent_count} active 'background: transparent' declarations in dialog styling")
            return False
        else:
            print("✅ Dialog styling no longer overrides background colors")
    
    # Test 4: Check that background color application is still present
    if "item.setBackground(QBrush(type_color))" in content:
        print("✅ Background color application code is present")
    else:
        print("❌ Background color application code not found")
        return False
    
    # Test 5: Check for the revolutionary asset type color selection method
    if "_apply_asset_type_selection_colors" in content:
        print("✅ Asset type color selection method is present")
    else:
        print("❌ Asset type color selection method not found")
        return False
    
    # Test 6: Check that the method is called in selection handler
    if "self._apply_asset_type_selection_colors(current_list)" in content:
        print("✅ Asset type color selection is called in selection handler")
    else:
        print("❌ Asset type color selection not called in selection handler")
        return False
    
    return True

def test_css_comments_and_fixes():
    """Test that CSS fixes include proper comments explaining the changes"""
    print("\n🔍 Testing CSS Fix Documentation...")
    
    asset_manager_path = "assetManager.py"
    with open(asset_manager_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the comment explaining the background fix
    if "/* Removed 'background: transparent' to allow asset type colors */" in content:
        print("✅ CSS fix is properly documented with explanatory comments")
        return True
    else:
        print("❌ CSS fix documentation comment not found")
        return False

def main():
    """Run all background color fix tests"""
    print("🎨 Asset Manager v1.2.0 Background Color Fix Validation")
    print("=" * 60)
    
    test_results = []
    
    # Test the CSS fixes
    test_results.append(test_background_color_css_fix())
    test_results.append(test_css_comments_and_fixes())
    
    # Summary
    print("\n" + "=" * 60)
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    if passed_tests == total_tests:
        print(f"🎯 SUCCESS: All {total_tests}/{total_tests} background color tests passed!")
        print("\n🎨 Asset type background colors should now be visible in the UI!")
        print("💡 The fix removes CSS 'background: transparent' declarations that were")
        print("   overriding the programmatically set asset type colors.")
        return True
    else:
        print(f"❌ FAILED: {passed_tests}/{total_tests} tests passed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
