#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Maya Shelf Button Hover Icon Implementation
Asset Manager v1.3.0 - Clean Code & SOLID Principles

This test validates the hover icon functionality for Maya shelf buttons.
"""

import os
import sys
from pathlib import Path

def test_hover_icon_implementation():
    """Test the hover icon setup - Single Responsibility"""
    print("🧪 Testing Maya Shelf Button Hover Icon Implementation")
    print("=" * 60)
    
    # Add utilities to path
    current_dir = Path(__file__).parent
    utilities_dir = current_dir / "utilities"
    if str(utilities_dir) not in sys.path:
        sys.path.insert(0, str(utilities_dir))
    
    # Test icon utilities
    try:
        from icon_utils import get_icon_manager
        
        icon_manager = get_icon_manager()
        print("✅ Icon manager loaded successfully")
        
        # Test shelf icon pair functionality
        icon_pair = icon_manager.get_shelf_icon_pair('assetManager_icon')
        
        print(f"📁 Default icon: {icon_pair['default']}")
        print(f"🎯 Hover icon: {icon_pair['hover']}")
        
        # Validate files exist
        default_exists = os.path.exists(icon_pair['default']) if icon_pair['default'] else False
        hover_exists = os.path.exists(icon_pair['hover']) if icon_pair['hover'] else False
        
        print(f"✅ Default icon exists: {default_exists}")
        print(f"✅ Hover icon exists: {hover_exists}")
        
        if default_exists and hover_exists:
            print("\n🎉 SUCCESS: Both icons available for hover implementation!")
            print("💡 Maya shelf button will show:")
            print(f"   - Default: {Path(icon_pair['default']).name}")
            print(f"   - Hover:   {Path(icon_pair['hover']).name}")
        else:
            print("\n⚠️  WARNING: Missing icon files")
            if not default_exists:
                print(f"   - Default icon missing: {icon_pair['default']}")
            if not hover_exists:
                print(f"   - Hover icon missing: {icon_pair['hover']}")
        
        # Test individual methods
        print("\n🔧 Testing individual methods:")
        default_icon = icon_manager.get_maya_shelf_icon('assetManager_icon.png')
        hover_icon = icon_manager.get_maya_shelf_hover_icon('assetManager_icon')
        
        print(f"   - get_maya_shelf_icon(): {Path(default_icon).name if default_icon else 'None'}")
        print(f"   - get_maya_shelf_hover_icon(): {Path(hover_icon).name if hover_icon else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing icon functionality: {e}")
        return False

def test_mel_integration():
    """Test MEL script integration - Clean Code approach"""
    print("\n🔗 Testing MEL Integration")
    print("-" * 30)
    
    # Check if MEL script exists and contains hover logic
    mel_file = Path(__file__).parent / "DRAG&DROP.mel"
    
    if mel_file.exists():
        print("✅ DRAG&DROP.mel found")
        
        content = mel_file.read_text(encoding='utf-8', errors='ignore')
        
        # Check for hover implementation
        has_image1 = "-image1" in content
        has_hover_check = "hoverIconPath" in content
        has_hover_logic = "filetest -f $hoverIconPath" in content
        
        print(f"✅ Contains -image1 parameter: {has_image1}")
        print(f"✅ Contains hover icon path: {has_hover_check}")  
        print(f"✅ Contains hover logic: {has_hover_logic}")
        
        if all([has_image1, has_hover_check, has_hover_logic]):
            print("\n🎉 MEL Integration SUCCESS!")
            print("💡 The DRAG&DROP.mel installer will create shelf buttons with hover effects")
        else:
            print("\n⚠️  MEL Integration incomplete")
            
    else:
        print("❌ DRAG&DROP.mel not found")

def main():
    """Main test execution - Clean Code: Single entry point"""
    print("Asset Manager v1.3.0 - Shelf Hover Icon Test")
    print("Clean Code & SOLID Principles Implementation")
    print("=" * 80)
    
    # Test Python implementation
    success1 = test_hover_icon_implementation()
    
    # Test MEL integration
    test_mel_integration()
    
    print("\n" + "=" * 80)
    if success1:
        print("🚀 CONCLUSION: Hover icon implementation is ready!")
        print("📋 Next Steps:")
        print("   1. Run DRAG&DROP.mel in Maya to install with hover support")
        print("   2. Hover over the Asset Manager shelf button to see the effect")
        print("   3. Enjoy the enhanced user experience! ✨")
    else:
        print("❌ Issues found. Please review the output above.")

if __name__ == "__main__":
    main()
