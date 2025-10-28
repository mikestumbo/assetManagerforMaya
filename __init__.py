"""
Asset Manager Package Initialization v1.4.0
Exposes the main show_asset_manager function for easy access.
"""

# Import the main function from the assetManager module
try:
    from .assetManager import show_asset_manager  # type: ignore
    
    # Make it available at package level
    __all__ = ['show_asset_manager']
    
except ImportError as e:
    print(f"Warning: Could not import show_asset_manager: {e}")
    
    # Fallback function with error handling
    def show_asset_manager():
        import maya.cmds as cmds # type: ignore
        cmds.confirmDialog(
            title='Asset Manager - Import Error',
            message='Failed to import Asset Manager components.\nPlease reinstall using DRAG&DROP.mel',
            button='OK',
            icon='critical'
        )
        return None