#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thumbnail Generation Diagnostic Script
Tests and debugs thumbnail generation for imported assets

Author: Mike Stumbo
Clean Code Troubleshooting
"""

import sys
import tempfile
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

def test_thumbnail_service():
    """Test the thumbnail service implementation directly"""
    print("🔧 Testing Thumbnail Service Implementation...")
    
    try:
        from src.services.thumbnail_service_impl import ThumbnailServiceImpl
        
        # Create thumbnail service instance
        service = ThumbnailServiceImpl()
        print("✅ ThumbnailServiceImpl created successfully")
        
        # Check cache directory
        print(f"📁 Cache directory: {service._cache_dir}")
        print(f"📁 Cache directory exists: {service._cache_dir.exists()}")
        
        # Check supported extensions
        print(f"🎯 Supported extensions: {service._supported_extensions}")
        
        # Test with a dummy image file (create a simple test file)
        test_file = Path(tempfile.gettempdir()) / "test_asset.png"
        
        # Create a simple test PNG file
        try:
            from PySide6.QtGui import QPixmap, QPainter, QColor
            from PySide6.QtCore import Qt
            
            # Create a simple test image
            pixmap = QPixmap(100, 100)
            pixmap.fill(QColor(255, 100, 100))  # Red background
            
            painter = QPainter(pixmap)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(10, 50, "TEST")
            painter.end()
            
            # Save test file
            pixmap.save(str(test_file), 'PNG')
            print(f"✅ Created test file: {test_file}")
            
            # Test thumbnail generation
            thumbnail_path = service.generate_thumbnail(test_file, size=(64, 64))
            
            if thumbnail_path:
                print(f"✅ Thumbnail generated successfully: {thumbnail_path}")
                print(f"📁 Thumbnail file exists: {Path(thumbnail_path).exists()}")
                print(f"📊 Thumbnail file size: {Path(thumbnail_path).stat().st_size} bytes")
                
                # Test cache retrieval
                cached_path = service.get_cached_thumbnail(test_file, size=(64, 64))
                if cached_path:
                    print(f"✅ Cache retrieval works: {cached_path}")
                else:
                    print("❌ Cache retrieval failed")
                    
            else:
                print("❌ Thumbnail generation failed")
                
            # Cleanup
            test_file.unlink(missing_ok=True)
            if thumbnail_path:
                Path(thumbnail_path).unlink(missing_ok=True)
            
        except Exception as e:
            print(f"❌ Error testing with Qt: {e}")
            test_file.unlink(missing_ok=True)
    
    except Exception as e:
        print(f"❌ Error testing thumbnail service: {e}")
        import traceback
        traceback.print_exc()

def test_container_integration():
    """Test thumbnail service through dependency injection container"""
    print("\n🔧 Testing Container Integration...")
    
    try:
        from src.core.container import get_container
        from src.core.interfaces.thumbnail_service import IThumbnailService
        
        container = get_container()
        print("✅ Container retrieved successfully")
        
        # Get thumbnail service through container
        thumbnail_service = container.resolve(IThumbnailService)
        print("✅ Thumbnail service resolved from container")
        
        print(f"📋 Service type: {type(thumbnail_service)}")
        
    except Exception as e:
        print(f"❌ Error testing container integration: {e}")
        import traceback
        traceback.print_exc()

def test_asset_library_widget():
    """Test the asset library widget thumbnail loading"""
    print("\n🔧 Testing Asset Library Widget...")
    
    try:
        # This would require a full Qt application context
        print("⚠️ Full widget testing requires Qt application context")
        print("⚠️ Skipping for now - manual testing recommended")
        
    except Exception as e:
        print(f"❌ Error testing asset library widget: {e}")

def check_cache_directory():
    """Check the thumbnail cache directory for existing files"""
    print("\n🔧 Checking Cache Directory...")
    
    try:
        cache_dir = Path(tempfile.gettempdir()) / "assetmanager_thumbnails"
        print(f"📁 Cache directory: {cache_dir}")
        print(f"📁 Exists: {cache_dir.exists()}")
        
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.png"))
            print(f"📊 Cache files found: {len(cache_files)}")
            
            for i, cache_file in enumerate(cache_files[:5]):  # Show first 5
                print(f"  📄 {cache_file.name} ({cache_file.stat().st_size} bytes)")
            
            if len(cache_files) > 5:
                print(f"  ... and {len(cache_files) - 5} more files")
        else:
            print("📁 Cache directory does not exist yet")
            
    except Exception as e:
        print(f"❌ Error checking cache directory: {e}")

def main():
    """Main diagnostic function"""
    print("=" * 60)
    print("🔍 THUMBNAIL GENERATION DIAGNOSTIC")
    print("=" * 60)
    
    check_cache_directory()
    test_thumbnail_service()
    test_container_integration()
    test_asset_library_widget()
    
    print("\n" + "=" * 60)
    print("🏁 DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
