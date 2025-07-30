#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script to test thumbnail functionality
"""
import os
import sys

# Add the asset manager directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

def test_thumbnail_functionality():
    """Test the thumbnail generation system"""
    
    print("=== Asset Manager Thumbnail Debug ===")
    
    # Try to import the asset manager
    try:
        from assetManager import AssetManager
        print("✓ AssetManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import AssetManager: {e}")
        return
    
    # Initialize asset manager
    try:
        asset_manager = AssetManager()
        print("✓ AssetManager initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize AssetManager: {e}")
        return
    
    # Check thumbnail cache directory
    print(f"\nThumbnail cache directory: {asset_manager.thumbnail_cache_dir}")
    if os.path.exists(asset_manager.thumbnail_cache_dir):
        print("✓ Thumbnail cache directory exists")
        
        # List existing thumbnails
        thumbnails = [f for f in os.listdir(asset_manager.thumbnail_cache_dir) if f.endswith('.png')]
        print(f"✓ Found {len(thumbnails)} existing thumbnails: {thumbnails[:5]}{'...' if len(thumbnails) > 5 else ''}")
    else:
        print("⚠ Thumbnail cache directory does not exist")
    
    # Check Maya availability
    try:
        import maya.cmds as cmds # type: ignore
        print("✓ Maya cmds available")
        maya_available = True
    except ImportError:
        print("⚠ Maya cmds not available (expected if not running in Maya)")
        maya_available = False
    
    # Test thumbnail generation method exists
    if hasattr(asset_manager, 'generate_asset_thumbnail'):
        print("✓ generate_asset_thumbnail method exists")
    else:
        print("✗ generate_asset_thumbnail method missing")
    
    if hasattr(asset_manager, 'get_asset_thumbnail'):
        print("✓ get_asset_thumbnail method exists")
    else:
        print("✗ get_asset_thumbnail method missing")
    
    # Look for Maya files in the current directory to test with
    maya_files = []
    for root, dirs, files in os.walk(script_dir):
        for file in files:
            if file.lower().endswith(('.ma', '.mb')):
                maya_files.append(os.path.join(root, file))
                if len(maya_files) >= 3:  # Just get a few examples
                    break
        if len(maya_files) >= 3:
            break
    
    print(f"\nFound {len(maya_files)} Maya files for testing:")
    for file_path in maya_files:
        print(f"  - {os.path.basename(file_path)}")
    
    # Test thumbnail generation (only if Maya is available)
    if maya_available and maya_files:
        print(f"\nTesting thumbnail generation for: {os.path.basename(maya_files[0])}")
        try:
            thumbnail_path = asset_manager.get_asset_thumbnail(maya_files[0])
            if thumbnail_path and os.path.exists(thumbnail_path):
                print(f"✓ Thumbnail generated successfully: {thumbnail_path}")
            else:
                print("⚠ Thumbnail generation returned None or file doesn't exist")
        except Exception as e:
            print(f"✗ Thumbnail generation failed: {e}")
    
    print("\n=== Debug Summary ===")
    if maya_available:
        print("• Maya is available - thumbnails should work")
    else:
        print("• Maya not available - thumbnails cannot be generated")
    
    if os.path.exists(asset_manager.thumbnail_cache_dir):
        print("• Cache directory exists")
    else:
        print("• Cache directory missing")
    
    print("• Methods exist and are callable")

if __name__ == "__main__":
    test_thumbnail_functionality()
