#!/usr/bin/env python
"""
Test script to verify AssetPreviewWidget has all required methods
"""

import sys
import os

def test_asset_preview_widget_methods():
    """Test that AssetPreviewWidget has all required methods"""
    print("🔍 Testing AssetPreviewWidget Methods")
    print("=" * 60)
    
    try:
        import assetManager
        print("✅ Successfully imported assetManager module")
        
        # Check if AssetPreviewWidget class exists
        AssetPreviewWidget = getattr(assetManager, 'AssetPreviewWidget', None)
        if AssetPreviewWidget is None:
            print("❌ AssetPreviewWidget class not found")
            return False
            
        print("✅ AssetPreviewWidget class found")
        
        # Check for required methods
        required_methods = [
            'start_asset_comparison',
            'close_asset_comparison', 
            '_get_suitable_viewport_panel',
            'load_asset',
            'preview_asset',
            'clear_preview'
        ]
        
        all_methods_present = True
        for method_name in required_methods:
            if hasattr(AssetPreviewWidget, method_name):
                print(f"✅ Method {method_name} found")
            else:
                print(f"❌ Method {method_name} missing")
                all_methods_present = False
        
        if all_methods_present:
            print("\n🎉 All required methods are present!")
            print("✅ AssetPreviewWidget should work correctly in Maya")
            return True
        else:
            print("\n❌ Some methods are missing")
            return False
            
    except Exception as e:
        print(f"❌ Error testing AssetPreviewWidget: {e}")
        return False

def main():
    """Main test function"""
    print("Asset Manager - AssetPreviewWidget Method Verification")
    print("Testing for methods needed after UI separation")
    print()
    
    success = test_asset_preview_widget_methods()
    
    if success:
        print("\n🎉 Method verification completed successfully!")
        print("The AssetPreviewWidget should now work in Maya without errors.")
    else:
        print("\n❌ Method verification failed - check error messages above")
        
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
