# -*- coding: utf-8 -*-
"""
UI Widgets Package
Reusable UI components following Single Responsibility Principle

Author: Mike Stumbo
"""

# Import all available widgets
try:
    from .collections_widget import CollectionsDisplayWidget  # noqa: F401
    from .asset_library_widget import AssetLibraryWidget  # noqa: F401
    from .asset_preview_widget import AssetPreviewWidget  # noqa: F401
    from .color_coding_keychart_widget import ColorCodingKeychartWidget  # noqa: F401
    from .enhanced_asset_info_widget import EnhancedAssetInfoWidget  # noqa: F401

    __all__ = [
        "CollectionsDisplayWidget",
        "AssetLibraryWidget",
        "AssetPreviewWidget",
        "ColorCodingKeychartWidget",
        "EnhancedAssetInfoWidget",
    ]

except ImportError as e:
    # Graceful degradation if widgets can't be imported
    print(f"Warning: Some widgets could not be imported: {e}")
    __all__ = []
