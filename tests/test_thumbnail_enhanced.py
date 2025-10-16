#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Thumbnail Generation Diagnostic
Tests thumbnail generation with proper Qt context and debugging

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

def test_with_qt_application():
    """Test thumbnail generation with proper Qt application context"""
    print("🔧 Testing with Qt Application Context...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPixmap, QPainter, QColor
        from PySide6.QtCore import Qt
        
        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            created_app = True
            print("✅ Created new QApplication instance")
        else:
            created_app = False
            print("✅ Using existing QApplication instance")
        
        try:
            from src.services.thumbnail_service_impl import ThumbnailServiceImpl
            
            # Create thumbnail service instance
            service = ThumbnailServiceImpl()
            print("✅ ThumbnailServiceImpl created successfully")
            
            # Create a test image file
            test_file = Path(tempfile.gettempdir()) / "test_asset_debug.png"
            
            # Create a simple test image
            pixmap = QPixmap(100, 100)
            pixmap.fill(QColor(100, 150, 255))  # Blue background
            
            painter = QPainter(pixmap)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(20, 50, "TEST")
            painter.end()
            
            # Save test file
            if pixmap.save(str(test_file), 'PNG'):
                print(f"✅ Created test file: {test_file}")
                print(f"📊 Test file size: {test_file.stat().st_size} bytes")
                
                # Test different thumbnail sizes
                sizes = [(64, 64), (128, 128), (256, 256)]
                
                for size in sizes:
                    print(f"\n🔧 Testing size {size}...")
                    
                    # Test thumbnail generation
                    thumbnail_path = service.generate_thumbnail(test_file, size=size)
                    
                    if thumbnail_path:
                        print(f"✅ Thumbnail generated: {thumbnail_path}")
                        thumb_file = Path(thumbnail_path)
                        if thumb_file.exists():
                            print(f"📊 Thumbnail file size: {thumb_file.stat().st_size} bytes")
                            
                            # Test cache retrieval
                            cached_path = service.get_cached_thumbnail(test_file, size=size)
                            if cached_path:
                                print(f"✅ Cache hit: {cached_path}")
                            else:
                                print("❌ Cache miss - this is a problem!")
                        else:
                            print(f"❌ Thumbnail file does not exist: {thumbnail_path}")
                    else:
                        print(f"❌ Thumbnail generation failed for size {size}")
                
                # Cleanup test file
                test_file.unlink(missing_ok=True)
                
                # Clean up generated thumbnails
                for size in sizes:
                    cache_key = service._generate_cache_key(test_file, size)
                    cache_path = service._get_cache_path(cache_key)
                    cache_path.unlink(missing_ok=True)
            else:
                print("❌ Failed to create test file")
                
        except Exception as e:
            print(f"❌ Error in Qt testing: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Don't quit the app if we didn't create it
            if created_app:
                app.quit()
    
    except Exception as e:
        print(f"❌ Error setting up Qt application: {e}")
        import traceback
        traceback.print_exc()

def check_thumbnail_cache_keys():
    """Debug cache key generation and path resolution"""
    print("\n🔧 Testing Cache Key Generation...")
    
    try:
        from src.services.thumbnail_service_impl import ThumbnailServiceImpl
        
        service = ThumbnailServiceImpl()
        
        # Test with some example paths
        test_paths = [
            Path("C:/test/asset.ma"),
            Path("C:\\test\\asset.ma"),
            Path("./test/asset.ma"),
            Path("test/asset.obj")
        ]
        
        for test_path in test_paths:
            print(f"\n📝 Testing path: {test_path}")
            print(f"   Resolved: {test_path.resolve()}")
            
            # Test cache key generation (this might fail for non-existent files)
            try:
                # Create a temporary file to test with
                temp_file = Path(tempfile.gettempdir()) / "cache_test.txt"
                temp_file.write_text("test content")
                
                cache_key = service._generate_cache_key(temp_file, (64, 64))
                cache_path = service._get_cache_path(cache_key)
                
                print(f"   Cache key: {cache_key}")
                print(f"   Cache path: {cache_path}")
                
                temp_file.unlink()
                
            except Exception as e:
                print(f"   ❌ Cache key error: {e}")
    
    except Exception as e:
        print(f"❌ Error testing cache keys: {e}")

def debug_asset_library_thumbnail_loading():
    """Debug the thumbnail loading process in asset library"""
    print("\n🔧 Debugging Asset Library Thumbnail Loading...")
    
    try:
        # Look for actual asset files in the workspace
        workspace_path = Path(__file__).parent
        asset_files = []
        
        # Search for common asset file types
        for pattern in ["**/*.ma", "**/*.mb", "**/*.obj", "**/*.png", "**/*.jpg"]:
            asset_files.extend(workspace_path.glob(pattern))
        
        print(f"📁 Found {len(asset_files)} potential asset files in workspace")
        
        if asset_files:
            from src.services.thumbnail_service_impl import ThumbnailServiceImpl
            service = ThumbnailServiceImpl()
            
            # Test with first few files
            for asset_file in asset_files[:3]:
                print(f"\n📄 Testing asset: {asset_file.name}")
                print(f"   Path: {asset_file}")
                print(f"   Exists: {asset_file.exists()}")
                print(f"   Extension: {asset_file.suffix}")
                print(f"   Supported: {service.is_thumbnail_supported(asset_file)}")
                
                # Check if there's already a cached thumbnail
                cached_thumb = service.get_cached_thumbnail(asset_file, size=(64, 64))
                if cached_thumb:
                    print(f"   ✅ Cached thumbnail exists: {cached_thumb}")
                else:
                    print(f"   ❌ No cached thumbnail found")
        
    except Exception as e:
        print(f"❌ Error debugging asset library: {e}")

def main():
    """Main enhanced diagnostic function"""
    print("=" * 70)
    print("🔍 ENHANCED THUMBNAIL GENERATION DIAGNOSTIC")
    print("=" * 70)
    
    check_thumbnail_cache_keys()
    debug_asset_library_thumbnail_loading()
    test_with_qt_application()
    
    print("\n" + "=" * 70)
    print("🏁 ENHANCED DIAGNOSTIC COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
