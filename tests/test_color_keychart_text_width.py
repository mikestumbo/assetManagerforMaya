#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Color Keychart Text Width Validation
Specific test for "Maya Scene" and "3D Model" text display

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import sys
from pathlib import Path

def test_text_width_requirements():
    """Test that the widget width can accommodate longer asset type names"""
    
    print("📏 Color Keychart Text Width Validation")
    print("=" * 45)
    
    # Asset types that need to display properly
    asset_types = [
        "Maya Scene",    # 10 characters
        "3D Model",      # 8 characters
        "Image",         # 5 characters
        "Video",         # 5 characters  
        "Material",      # 8 characters
        "Archive"        # 7 characters
    ]
    
    print("\n📝 ASSET TYPE TEXT ANALYSIS:")
    print("-" * 30)
    
    longest_text = ""
    max_length = 0
    
    for asset_type in asset_types:
        length = len(asset_type)
        print(f"• {asset_type:12s}: {length:2d} characters")
        if length > max_length:
            max_length = length
            longest_text = asset_type
    
    print(f"\n🎯 LONGEST TEXT: '{longest_text}' ({max_length} characters)")
    
    # Calculate required width
    # Assumptions based on Arial 9pt font:
    # - Average character width: ~7px
    # - Color swatch: 14px
    # - Grid spacing: 6px between swatch and text
    # - 2-column layout
    # - Widget margins: 6px left + 6px right = 12px
    
    char_width = 7  # pixels per character (Arial 9pt estimate)
    swatch_width = 14
    spacing = 6
    margins = 12
    columns = 2
    
    text_width_needed = max_length * char_width
    column_width_needed = swatch_width + spacing + text_width_needed
    total_width_needed = (column_width_needed * columns) + margins
    
    print(f"\n🧮 WIDTH CALCULATION:")
    print(f"   Text width needed: {text_width_needed}px ({max_length} chars × {char_width}px)")
    print(f"   Per column: {column_width_needed}px (swatch + spacing + text)")
    print(f"   Total for 2 columns: {total_width_needed}px")
    print(f"   With safety margin: {total_width_needed + 40}px")
    
    # Check current widget width
    keychart_file = "src/ui/widgets/color_coding_keychart_widget.py"
    if not Path(keychart_file).exists():
        print("❌ Color keychart file not found")
        return False
    
    with open(keychart_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"\n📐 WIDGET WIDTH CHECK:")
    print("-" * 22)
    
    # Extract current width setting
    current_width = None
    if "setMaximumWidth(340)" in content:
        current_width = 340
    elif "setMaximumWidth(280)" in content:
        current_width = 280
    elif "setMaximumWidth(220)" in content:
        current_width = 220
    
    if current_width:
        print(f"✅ Current width: {current_width}px")
        
        if current_width >= total_width_needed + 40:
            print(f"✅ Width is sufficient ({current_width}px >= {total_width_needed + 40}px)")
            width_adequate = True
        elif current_width >= total_width_needed:
            print(f"⚠️  Width is minimal ({current_width}px >= {total_width_needed}px)")
            width_adequate = True
        else:
            print(f"❌ Width is insufficient ({current_width}px < {total_width_needed}px)")
            width_adequate = False
    else:
        print("❌ No width constraint found")
        width_adequate = False
    
    print(f"\n📊 TEXT WIDTH VALIDATION: {'PASSED' if width_adequate else 'FAILED'}")
    
    if width_adequate:
        print("\n🎉 TEXT DISPLAY REQUIREMENTS MET!")
        print("\n✨ BENEFITS:")
        print("   📄 All asset type names display completely")
        print("   👁️  No text truncation or cut-off")
        print("   🎯 Professional appearance maintained")
        print("   📏 Accommodates longest text: 'Maya Scene'")
        return True
    else:
        print(f"\n⚠️  RECOMMENDATION: Increase width to at least {total_width_needed + 40}px")
        return False

if __name__ == "__main__":
    success = test_text_width_requirements()
    sys.exit(0 if success else 1)
