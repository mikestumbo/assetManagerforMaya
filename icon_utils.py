"""
Icon utilities for Asset Manager Plugin v1.1.3
Provides helper functions for loading and managing icons in the UI

Version: 1.1.3
Author: Mike Stumbo
Maya Version: 2025.3+
"""

import os
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSize


class IconManager:
    """Manages icon loading and caching for the Asset Manager plugin"""
    
    def __init__(self):
        self.icon_cache = {}
        self.icon_dir = os.path.join(os.path.dirname(__file__), 'icons')
        
    def get_icon_path(self, icon_name):
        """Get the full path to an icon file"""
        return os.path.join(self.icon_dir, icon_name)
    
    def load_icon(self, icon_name, size=None):
        """
        Load an icon from the icons directory
        
        Args:
            icon_name (str): Name of the icon file (e.g., 'folder-open.png')
            size (QSize, optional): Desired icon size
            
        Returns:
            QIcon: The loaded icon, or None if not found
        """
        # Check cache first
        cache_key = f"{icon_name}_{size}" if size else icon_name
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
        
        icon_path = self.get_icon_path(icon_name)
        
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if size:
                # Create a pixmap with the specified size
                pixmap = icon.pixmap(size)
                icon = QIcon(pixmap)
            
            # Cache the icon
            self.icon_cache[cache_key] = icon
            return icon
        else:
            print(f"Warning: Icon not found: {icon_path}")
            return None
    
    def get_asset_type_icon(self, file_extension):
        """
        Get an appropriate icon based on file extension
        
        Args:
            file_extension (str): File extension (e.g., '.ma', '.obj')
            
        Returns:
            QIcon: Appropriate icon for the file type
        """
        # Map file extensions to icon names
        icon_map = {
            '.ma': 'scene-icon.png',
            '.mb': 'scene-icon.png',
            '.obj': 'model-icon.png',
            '.fbx': 'model-icon.png',
            '.abc': 'model-icon.png',
            '.jpg': 'texture-icon.png',
            '.jpeg': 'texture-icon.png',
            '.png': 'texture-icon.png',
            '.tga': 'texture-icon.png',
            '.exr': 'texture-icon.png',
            '.hdr': 'texture-icon.png',
            '.mov': 'animation-icon.png',
            '.mp4': 'animation-icon.png',
            '.avi': 'animation-icon.png'
        }
        
        icon_name = icon_map.get(file_extension.lower(), 'reference-icon.png')
        return self.load_icon(icon_name)
    
    def get_ui_icon(self, icon_type):
        """
        Get standard UI icons
        
        Args:
            icon_type (str): Type of UI icon ('refresh', 'search', 'settings', etc.)
            
        Returns:
            QIcon: The requested UI icon
        """
        ui_icons = {
            'refresh': 'refresh.png',
            'search': 'search.png',
            'settings': 'settings.png',
            'import': 'import.png',
            'export': 'export.png',
            'delete': 'delete.png',
            'duplicate': 'duplicate.png',
            'rename': 'rename.png',
            'new_project': 'project-new.png',
            'open_project': 'project-open.png',
            'save_project': 'project-save.png',
            'close_project': 'project-close.png',
            'folder_open': 'folder-open.png',
            'logo': 'asset-manager-logo.png',
            'shelf_icon': 'assetManager_icon.png',
            'shelf_icon_hover': 'assetManager_icon2.png'
        }
        
        icon_name = ui_icons.get(icon_type, 'reference-icon.png')
        return self.load_icon(icon_name)
    
    def clear_cache(self):
        """Clear the icon cache"""
        self.icon_cache.clear()


# Global icon manager instance
_icon_manager = None

def get_icon_manager():
    """Get the global icon manager instance"""
    global _icon_manager
    if _icon_manager is None:
        _icon_manager = IconManager()
    return _icon_manager

def load_icon(icon_name, size=None):
    """Convenience function to load an icon"""
    return get_icon_manager().load_icon(icon_name, size)

def get_asset_icon(file_extension):
    """Convenience function to get asset type icon"""
    return get_icon_manager().get_asset_type_icon(file_extension)

def get_ui_icon(icon_type):
    """Convenience function to get UI icon"""
    return get_icon_manager().get_ui_icon(icon_type)
