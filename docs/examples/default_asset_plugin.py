# -*- coding: utf-8 -*-
"""
Default Asset Plugin - Basic asset management functionality for Asset Manager v1.2.3

This plugin provides core asset management capabilities including:
- Basic asset importing
- File type support for common 3D formats
- Simple asset validation

Author: Mike Stumbo
Version: 1.0.0
Created: August 21, 2025
"""

import os
import json
from typing import Dict, List, Any, Optional


class DefaultAssetPlugin:
    """
    Default plugin providing basic asset management functionality.
    
    Follows Single Responsibility Principle - handles basic asset operations only.
    """
    
    def __init__(self):
        self.name = "Default Asset Plugin"
        self.version = "1.0.0"
        self.description = "Provides basic asset management functionality"
        self.author = "Mike Stumbo"
        
        # Supported file types
        self.supported_extensions = [
            '.ma', '.mb',           # Maya files
            '.obj', '.fbx',         # 3D models
            '.jpg', '.png', '.tga', # Textures
            '.mov', '.mp4',         # Videos
            '.json', '.xml'         # Data files
        ]
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """Return plugin information"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'supported_extensions': self.supported_extensions
        }
    
    def can_handle_asset(self, asset_path: str) -> bool:
        """Check if this plugin can handle the given asset"""
        if not os.path.exists(asset_path):
            return False
        
        file_ext = os.path.splitext(asset_path)[1].lower()
        return file_ext in self.supported_extensions
    
    def import_asset(self, asset_path: str, options: Optional[Dict] = None) -> bool:
        """Import an asset (basic implementation)"""
        try:
            if not self.can_handle_asset(asset_path):
                return False
            
            # Basic validation
            if not os.path.exists(asset_path):
                print(f"❌ Asset not found: {asset_path}")
                return False
            
            file_size = os.path.getsize(asset_path)
            if file_size == 0:
                print(f"❌ Asset file is empty: {asset_path}")
                return False
            
            print(f"✅ Default Plugin: Asset import successful - {os.path.basename(asset_path)}")
            return True
            
        except Exception as e:
            print(f"❌ Default Plugin: Import failed - {e}")
            return False
    
    def validate_asset(self, asset_path: str) -> Dict[str, Any]:
        """Validate an asset and return validation results"""
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'info': {}
        }
        
        try:
            if not os.path.exists(asset_path):
                result['errors'].append("File does not exist")
                return result
            
            # Basic file validation
            file_size = os.path.getsize(asset_path)
            file_ext = os.path.splitext(asset_path)[1].lower()
            
            result['info'] = {
                'file_size': file_size,
                'file_extension': file_ext,
                'file_name': os.path.basename(asset_path)
            }
            
            if file_size == 0:
                result['errors'].append("File is empty")
            elif file_ext not in self.supported_extensions:
                result['warnings'].append(f"File type {file_ext} may not be fully supported")
            else:
                result['valid'] = True
            
        except Exception as e:
            result['errors'].append(f"Validation error: {str(e)}")
        
        return result
    
    def get_asset_metadata(self, asset_path: str) -> Dict[str, Any]:
        """Extract basic metadata from an asset"""
        metadata = {
            'file_path': asset_path,
            'file_name': os.path.basename(asset_path),
            'file_size': 0,
            'file_extension': '',
            'created_date': None,
            'modified_date': None
        }
        
        try:
            if os.path.exists(asset_path):
                stat = os.stat(asset_path)
                metadata.update({
                    'file_size': stat.st_size,
                    'file_extension': os.path.splitext(asset_path)[1].lower(),
                    'created_date': stat.st_ctime,
                    'modified_date': stat.st_mtime
                })
        except Exception as e:
            print(f"⚠️  Metadata extraction failed: {e}")
        
        return metadata


# Plugin entry point - required by the plugin system
def get_plugin_class():
    """Return the plugin class for the plugin system"""
    return DefaultAssetPlugin


# Plugin manifest data - used by discovery system
PLUGIN_MANIFEST = {
    'name': 'Default Asset Plugin',
    'version': '1.0.0',
    'description': 'Provides basic asset management functionality',
    'author': 'Mike Stumbo',
    'plugin_class': 'DefaultAssetPlugin',
    'entry_point': 'get_plugin_class',
    'supported_extensions': ['.ma', '.mb', '.obj', '.fbx', '.jpg', '.png', '.tga', '.mov', '.mp4', '.json', '.xml'],
    'dependencies': [],
    'category': 'Core'
}


# Test function for development
if __name__ == "__main__":
    plugin = DefaultAssetPlugin()
    print("🔌 Default Asset Plugin Test")
    print(f"📋 Plugin Info: {plugin.get_plugin_info()}")
    
    # Test with a sample file
    test_file = __file__  # Use this plugin file itself for testing
    print(f"🧪 Testing with: {test_file}")
    print(f"📝 Can handle: {plugin.can_handle_asset(test_file)}")
    print(f"✅ Validation: {plugin.validate_asset(test_file)}")
    print(f"📊 Metadata: {plugin.get_asset_metadata(test_file)}")
