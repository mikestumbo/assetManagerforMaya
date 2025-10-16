# -*- coding: utf-8 -*-
"""
UI Widgets Package
Reusable UI components following Single Responsibility Principle

Author: Mike Stumbo
"""

# Import all available widgets
try:
    from .collections_widget import CollectionsDisplayWidget
    from .asset_library_widget import AssetLibraryWidget
    from .asset_preview_widget import AssetPreviewWidget
    from .color_coding_keychart_widget import ColorCodingKeychartWidget
    from .enhanced_asset_info_widget import EnhancedAssetInfoWidget
    
    __all__ = [
        'CollectionsDisplayWidget',
        'AssetLibraryWidget', 
        'AssetPreviewWidget',
        'ColorCodingKeychartWidget',
        'EnhancedAssetInfoWidget'
    ]
    
except ImportError as e:
    # Graceful degradation if widgets can't be imported
    print(f"Warning: Some widgets could not be imported: {e}")
    __all__ = []
