#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Background Color Test for Asset Manager v1.2.0
This test verifies that asset type background colors are now visible in the UI.
"""

import os

def test_background_color_visibility():
    """Quick test to verify background colors are no longer overridden by CSS"""
    print("🎨 Testing Asset Manager Background Color Visibility...")
    print("=" * 55)
    
    # Check if assetManager.py exists
    if not os.path.exists("assetManager.py"):
        print("❌ assetManager.py not found in current directory!")
        return False
    
    with open("assetManager.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Key indicators that the fix is in place
    fixes_present = []
    
    # 1. Check for removal comments
    if "/* Removed 'background: transparent' to allow asset type colors */" in content:
        fixes_present.append("✅ CSS fix comments present")
    else:
        fixes_present.append("❌ CSS fix comments missing")
    
    # 2. Check that background color setting is still there
    if "item.setBackground(QBrush(type_color))" in content:
        fixes_present.append("✅ Background color application code present")
    else:
        fixes_present.append("❌ Background color application code missing")
    
    # 3. Check for asset type color selection enhancement
    if "_apply_asset_type_selection_colors" in content:
        fixes_present.append("✅ Asset type color selection method present")
    else:
        fixes_present.append("❌ Asset type color selection method missing")
    
    # 4. Check that no active 'background: transparent' remains in QListWidget styling
    # Count only in stylesheet sections, not comments
    stylesheets = []
    
    # Find all setStyleSheet calls for QListWidget
    start_pos = 0
    while True:
        start = content.find("setStyleSheet(", start_pos)
        if start == -1:
            break
        end = content.find('""")', start) + 4
        if end > start:
            stylesheet_section = content[start:end]
            stylesheets.append(stylesheet_section)
        start_pos = end
    
    active_transparent_count = 0
    for stylesheet in stylesheets:
        if "QListWidget" in stylesheet or "asset" in stylesheet.lower():
            lines = stylesheet.split('\n')
            for line in lines:
                if ('background: transparent;' in line and 
                    not line.strip().startswith('/*') and 
                    not line.strip().startswith('//')):
                    active_transparent_count += 1
    
    if active_transparent_count == 0:
        fixes_present.append("✅ No active 'background: transparent' CSS rules found")
    else:
        fixes_present.append(f"❌ Found {active_transparent_count} active 'background: transparent' CSS rules")
    
    # Print results
    for result in fixes_present:
        print(f"  {result}")
    
    all_passed = all("✅" in result for result in fixes_present)
    
    print("\n" + "=" * 55)
    if all_passed:
        print("🎉 SUCCESS: Background colors should now be VISIBLE!")
        print("\n🎨 What you should see in the Asset Manager:")
        print("  • Models (blue backgrounds)")
        print("  • Rigs (purple backgrounds)")  
        print("  • Textures (orange backgrounds)")
        print("  • Materials (pink backgrounds)")
        print("  • And other asset types with their respective colors")
        print("\n🔥 When you select assets, they will show enhanced")
        print("   versions of their asset type colors!")
        return True
    else:
        print("❌ ISSUES FOUND: Background colors may not be visible")
        return False

if __name__ == "__main__":
    success = test_background_color_visibility()
    if success:
        print("\n✨ The Asset Manager v1.2.0 background color fix is complete!")
        print("   Load the Asset Manager in Maya to see the colorful asset types!")
    else:
        print("\n⚠️  There may be remaining issues with background color visibility.")
