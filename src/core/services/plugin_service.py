"""
Plugin Service Implementation
Concrete implementation of IPluginService for Asset Manager.
"""

import maya.cmds as cmds  # type: ignore
from ..interfaces.iplugin_service import IPluginService


class PluginService(IPluginService):
    """
    Concrete implementation of plugin service.
    Handles Maya-specific plugin operations.
    """
    
    def __init__(self):
        """Initialize the plugin service."""
        self._version = "1.3.0"
        self._is_initialized = False
        self._asset_manager_window = None
    
    def initialize(self) -> bool:
        """
        Initialize the plugin service.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Clean up any existing UI
            if cmds.window("assetManagerUI", exists=True):
                cmds.deleteUI("assetManagerUI")
            
            # Create the main UI
            self._create_main_ui()
            self._is_initialized = True
            return True
            
        except Exception as e:
            print(f"❌ Plugin service initialization failed: {e}")
            return False
    
    def shutdown(self) -> bool:
        """
        Shutdown the plugin service.
        
        Returns:
            bool: True if shutdown successful
        """
        try:
            # Clean up UI
            if cmds.window("assetManagerUI", exists=True):
                cmds.deleteUI("assetManagerUI")
            
            self._is_initialized = False
            return True
            
        except Exception as e:
            print(f"⚠️ Plugin service shutdown warning: {e}")
            return False
    
    def get_version(self) -> str:
        """
        Get the plugin version.
        
        Returns:
            str: Version string
        """
        return self._version
    
    def _create_main_ui(self) -> None:
        """Create the main Asset Manager UI using EMSA architecture."""
        try:
            print("🚀 Attempting to launch Asset Manager v1.3.0 UI...")
            
            # Try to launch using the maya module command first
            import maya.cmds as cmds # type: ignore
            
            # Use Maya's built-in command to run the asset manager
            try:
                cmds.assetManager()
                print("🚀 Asset Manager v1.3.0 main UI launched via Maya command!")
                return
            except:
                print("⚠️ Maya command not available, trying direct import...")
            
            # Fallback to direct UI import
            import sys
            import os
            
            # For now, skip the complex UI and go straight to fallback
            # This ensures the plugin loads successfully while we resolve UI import issues
            print("⚠️ Using Maya-native UI for compatibility")
            self._create_fallback_ui()
            return
            
        except ImportError as e:
            print(f"⚠️ Could not launch full UI: {e}")
            self._create_fallback_ui()
        except Exception as e:
            print(f"❌ Error launching Asset Manager UI: {e}")
            self._create_fallback_ui()
    
    def _create_fallback_ui(self) -> None:
        """Create fallback Maya-native UI if PySide6 UI fails."""
        window = cmds.window(
            "assetManagerUI",
            title=f"Asset Manager v{self._version} - Basic Mode",
            widthHeight=(400, 300),
            sizeable=True
        )
        
        cmds.columnLayout(
            adjustableColumn=True, 
            rowSpacing=10,
            columnOffset=("left", 15)
        )
        
        # Header
        cmds.text(label=f"Asset Manager v{self._version}", font="boldLabelFont")
        cmds.separator(height=15)
        
        # Status
        cmds.text(label="🏗️ EMSA Architecture Active", align="left")
        cmds.text(label="📦 Maya Module System Enabled", align="left")
        cmds.text(label="⚠️  Basic Mode - PySide6 UI unavailable", align="left")
        
        cmds.separator(height=15)
        
        # Fallback buttons
        cmds.button(label="Launch Full UI", height=35, 
                   command=lambda x: self._try_launch_full_ui())
        
        cmds.separator(height=15)
        cmds.button(label="Close", command=f'cmds.deleteUI("{window}")')
        
        cmds.showWindow(window)
    
    def _try_launch_full_ui(self) -> None:
        """Attempt to launch the full PySide6 UI."""
        try:
            # For now, show message that full UI is not available
            # This prevents the relative import error
            print("⚠️ Full PySide6 UI is temporarily disabled for compatibility")
            print("🔧 Using Maya-native UI for optimal stability")
            cmds.confirmDialog(
                title="Asset Manager UI",
                message="Full PySide6 UI is temporarily disabled for compatibility.\nUsing Maya-native UI for optimal stability.",
                button=["OK"]
            )
        except Exception as e:
            print(f"❌ Could not launch full UI: {e}")
