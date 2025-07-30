#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Asset Manager Customization Features
Demonstrates how to use the new user customization capabilities
"""

import sys
import os

# Add the plugin directory to path
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

try:
    from assetManager import AssetManager, AssetTypeCustomizationDialog, AssetManagerUI
    from PySide6.QtWidgets import QApplication
    print("✓ Asset Manager modules imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

def test_asset_manager_customization():
    """Test the Asset Manager customization features"""
    
    print("\n=== Asset Manager Customization Test ===\n")
    
    # Create asset manager instance
    asset_manager = AssetManager()
    print("✓ Asset Manager instance created")
    
    # Test 1: Default asset types
    print("\n1. Testing default asset types:")
    default_types = asset_manager.get_asset_type_list()
    print(f"   Default types: {default_types}")
    
    # Test 2: Add custom asset type
    print("\n2. Testing custom asset type addition:")
    success = asset_manager.add_custom_asset_type(
        type_id='environments',
        name='Environments',
        color=[100, 200, 100],
        priority=8,
        extensions=['.ma', '.mb', '.obj'],
        description='Environment and scene assets'
    )
    if success:
        print("   ✓ Custom asset type 'environments' added successfully")
        updated_types = asset_manager.get_asset_type_list()
        print(f"   Updated types: {updated_types}")
    else:
        print("   ✗ Failed to add custom asset type")
    
    # Test 3: Update existing asset type
    print("\n3. Testing asset type modification:")
    success = asset_manager.update_asset_type(
        type_id='models',
        color=[255, 100, 50],  # Change color to orange-red
        description='Updated 3D models and geometry with new color'
    )
    if success:
        print("   ✓ Models asset type updated successfully")
        print(f"   New models color: {asset_manager.asset_types['models']['color']}")
    else:
        print("   ✗ Failed to update models asset type")
    
    # Test 4: Test color cache update
    print("\n4. Testing color cache:")
    models_color = asset_manager.asset_type_colors.get('models')
    environments_color = asset_manager.asset_type_colors.get('environments')
    
    if models_color:
        print(f"   Models QColor: RGB({models_color.red()}, {models_color.green()}, {models_color.blue()})")
    else:
        print("   Models color not found")
        
    if environments_color:
        print(f"   Environments QColor: RGB({environments_color.red()}, {environments_color.green()}, {environments_color.blue()})")  
    else:
        print("   Environments color not found")
    
    # Test 5: Export/Import configuration
    print("\n5. Testing configuration export/import:")
    export_path = os.path.join(plugin_dir, "test_asset_types.json")
    
    if asset_manager.export_asset_type_config(export_path):
        print(f"   ✓ Configuration exported to: {export_path}")
        
        # Create new instance and import
        test_manager = AssetManager()
        if test_manager.import_asset_type_config(export_path):
            print("   ✓ Configuration imported successfully")
            
            # Verify import worked
            if 'environments' in test_manager.asset_types:
                print("   ✓ Custom 'environments' type found in imported config")
            else:
                print("   ✗ Custom type not found in imported config")
        else:
            print("   ✗ Failed to import configuration")
        
        # Clean up test file
        try:
            os.remove(export_path)
            print("   ✓ Test file cleaned up")
        except:
            print("   ! Could not clean up test file")
    else:
        print("   ✗ Failed to export configuration")
    
    # Test 6: Reset to defaults
    print("\n6. Testing reset to defaults:")
    asset_manager.reset_asset_types_to_default()
    reset_types = asset_manager.get_asset_type_list()
    print(f"   Types after reset: {reset_types}")
    
    if 'environments' not in reset_types:
        print("   ✓ Custom types removed after reset")
    else:
        print("   ✗ Custom types still present after reset")
    
    print("\n=== Asset Manager Customization Test Complete ===")
    return True

def demo_ui_customization():
    """Demonstrate the UI customization dialog"""
    
    print("\n=== UI Customization Demo ===")
    print("This demo would show the Asset Type Customization Dialog.")
    print("In Maya, you can access this via: Tools → Customize Asset Types...")
    print("\nFeatures available in the dialog:")
    print("• Add new custom asset types")
    print("• Modify existing type colors and properties")
    print("• Set priority ordering")
    print("• Define file extensions for auto-detection")
    print("• Export/import configurations")
    print("• Reset to defaults")
    print("• Real-time preview of changes")
    
    # If running with GUI, could show the dialog:
    # app = QApplication.instance() or QApplication(sys.argv)
    # asset_manager = AssetManager()
    # dialog = AssetTypeCustomizationDialog(asset_manager)
    # dialog.show()
    # app.exec()

if __name__ == "__main__":
    print("Asset Manager Customization Test Script")
    print("=" * 50)
    
    try:
        test_asset_manager_customization()
        demo_ui_customization()
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
