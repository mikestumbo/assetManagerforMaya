# -*- coding: utf-8 -*-
"""
Asset Manager v1.3.0 - Maya 2025+ Exclusive (NO PLUGIN REGISTRATION)
Pure UI Module - No Maya Node Registration to Avoid Unknown Data Issues

Author: Mike Stumbo
Version: 1.3.0
Maya Version: 2025.3+
"""

import sys
from pathlib import Path


def _ensure_path_for_imports():
    """
    Safely ensure src directory is available for imports.
    Returns original path for restoration.
    """
    plugin_dir = Path(__file__).parent
    src_dir = plugin_dir / "src"
    
    # Store original path for restoration
    original_path = sys.path[:]
    
    # Add both plugin directory and src directory to Python path temporarily
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    return original_path


def show_asset_manager():
    """Show Asset Manager UI - Main entry point (NO PLUGIN REGISTRATION)"""
    original_path = None
    try:
        print("🎨 Launching Asset Manager v1.3.0 UI...")
        
        # Safely add paths for import
        original_path = _ensure_path_for_imports()
        
        # Check PySide6 availability
        try:
            from PySide6.QtWidgets import QApplication
            print("✅ Using PySide6 (Maya 2025+)")
        except ImportError:
            print("❌ PySide6 is not available")
            print("💡 Asset Manager requires PySide6 (Maya 2025+)")
            return None
        
        # Create Qt application if needed
        app = QApplication.instance()
        if app is None:
            print("⚠️ Creating QApplication outside Maya - may cause issues")
            app = QApplication(sys.argv)
        
        # Launch with Maya parent for proper Z-order while maintaining safety
        # Using Maya parent but ensuring no scene contamination through cleanup
        try:
            import maya.OpenMayaUI as omui # type: ignore
            from PySide6.QtWidgets import QWidget
            import shiboken6
            
            # Get Maya main window as parent for proper Z-order
            maya_main_window_ptr = omui.MQtUtil.mainWindow()
            if maya_main_window_ptr:
                parent = shiboken6.wrapInstance(int(maya_main_window_ptr), QWidget)
                print("✅ Maya parent window obtained for proper Z-order")
            else:
                parent = None
                print("⚠️ Maya main window not available - using standalone")
            
        except Exception as e:
            print(f"⚠️ Maya parent window error: {e}")
            parent = None
        
        # Configure services
        try:
            from src.core.container import configure_services
            configure_services()
            print("✅ Services configured")
        except Exception as e:
            print(f"⚠️ Service configuration failed: {e}")
        
        # Import and show UI with singleton management
        try:
            from src.ui.asset_manager_window import AssetManagerWindow
            
            # Singleton window management - prevent duplicates
            global _asset_manager_window
            if '_asset_manager_window' not in globals():
                _asset_manager_window = None
            
            # Check if window already exists
            if _asset_manager_window is not None:
                try:
                    # Bring existing window to front
                    if _asset_manager_window.isVisible():
                        _asset_manager_window.raise_()
                        _asset_manager_window.activateWindow()
                        _asset_manager_window.showNormal()
                        print("✅ Brought existing Asset Manager to front")
                        return _asset_manager_window
                except RuntimeError:
                    # Window was deleted - clear reference
                    _asset_manager_window = None
            
            # Create new window
            _asset_manager_window = AssetManagerWindow(parent=parent)
            _asset_manager_window.show()
            
            # Ensure it comes to front
            _asset_manager_window.raise_()
            _asset_manager_window.activateWindow()
            
            print("🎉 Asset Manager v1.3.0 launched successfully!")
            return _asset_manager_window
            
        except Exception as e:
            print(f"❌ Failed to create Asset Manager window: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    except Exception as e:
        print(f"❌ Failed to launch Asset Manager: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Restore original path for security
        if original_path is not None:
            sys.path[:] = original_path


# Entry point for development/testing
if __name__ == "__main__":
    show_asset_manager()