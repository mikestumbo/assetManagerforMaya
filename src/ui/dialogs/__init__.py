# -*- coding: utf-8 -*-
"""
UI Dialogs Package
Collection of dialog windows for the Asset Manager
Enhanced with Screenshot Capture functionality
"""

from .create_asset_dialog import CreateAssetDialog
from .screenshot_capture_dialog import ScreenshotCaptureDialog

__all__ = [
    'CreateAssetDialog',
    'ScreenshotCaptureDialog',
]
