# -*- coding: utf-8 -*-
"""
Asset Preview Widget
Displays asset preview and metadata following Single Responsibility

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Optional
from pathlib import Path

# PySide6 for Maya 2022+
try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QHBoxLayout, QPushButton
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QIcon
    PYSIDE_AVAILABLE = True
    PYSIDE_VERSION = "PySide6"
except ImportError as e:
    print(f"❌ PySide6 import failed: {e}")
    print("🔧 Maya 2025+ requires PySide6. Please ensure it's properly installed.")
    PYSIDE_AVAILABLE = False
    PYSIDE_VERSION = None
    # Add these to prevent "possibly unbound" errors
    QWidget = None
    QVBoxLayout = None
    QLabel = None
    QScrollArea = None
    QHBoxLayout = None
    QPushButton = None
    Qt = None
    QPixmap = None
    QIcon = None

# Import core models and interfaces - suppress import warnings for standalone testing
try:
    from ...core.models.asset import Asset  # type: ignore
    from ...core.interfaces.thumbnail_service import IThumbnailService  # type: ignore
    from ...core.container import get_container  # type: ignore
    from ..dialogs.screenshot_capture_dialog import ScreenshotCaptureDialog  # type: ignore
except ImportError:
    # Fallback definitions for when imports fail
    class Asset:  # type: ignore
        def __init__(self):
            self.file_path = None
            self.asset_type = "unknown"
            self.file_size = 0
            self.file_size_mb = 0.0
            self.created_date = None
            self.modified_date = None
            self.display_name = "Unknown"
            self.access_count = 0
            self.tags = []
            self.metadata = {}
    
    class IThumbnailService:  # type: ignore
        pass
    
    class ScreenshotCaptureDialog:  # type: ignore
        def __init__(self, asset, parent=None):
            pass
        def set_refresh_callback(self, callback):
            pass
        def exec(self):
            return False
    
    def get_container():  # type: ignore
        return None


if PYSIDE_AVAILABLE and QWidget is not None:
    class AssetPreviewWidget(QWidget):  # type: ignore
        """
        Asset Preview Widget - Single Responsibility for asset preview
        Displays asset thumbnails and metadata information
        """
        
        def __init__(self, parent=None):
            super().__init__(parent)
            
            # Enhanced dependency injection with better fallback
            self._thumbnail_service = None
            try:
                container = get_container()  # type: ignore
                self._thumbnail_service = container.resolve(IThumbnailService)  # type: ignore
                print("✅ Asset preview widget - container services resolved")
            except Exception as container_error:
                print(f"⚠️ Asset preview container error: {container_error}")
                
                # Try service factory as backup
                try:
                    from ...core.service_factory import get_service_factory
                    factory = get_service_factory()
                    self._thumbnail_service = factory.create_thumbnail_service()
                    if self._thumbnail_service:
                        print("✅ Asset preview widget - factory service resolved")
                    else:
                        raise Exception("Factory returned None")
                except Exception as factory_error:
                    print(f"⚠️ Asset preview factory error: {factory_error}")
                    self._thumbnail_service = self._create_fallback_thumbnail_service()
                    print("✅ Asset preview widget - using fallback service")
            
            # State
            self._current_asset: Optional[Asset] = None
            
            # UI components
            self._preview_label: Optional[QLabel] = None  # type: ignore
            self._zoom_factor: float = 1.0
            self._original_pixmap: Optional[QPixmap] = None  # type: ignore
            self._scroll_area: Optional[QScrollArea] = None  # type: ignore
            
            # Setup UI
            self._create_ui()
        
        def _create_fallback_thumbnail_service(self):
            """Create enhanced fallback thumbnail service for preview widget"""
            class FallbackThumbnailService:
                def __init__(self):
                    self._cache_dir = None
                    try:
                        from pathlib import Path
                        import tempfile
                        self._cache_dir = Path(tempfile.gettempdir()) / "asset_manager_preview"
                        self._cache_dir.mkdir(exist_ok=True)
                    except Exception:
                        pass
                
                def get_cached_thumbnail(self, file_path, size=(256, 256)):
                    # Check if we have a basic file icon we can show
                    return self._create_placeholder_thumbnail(file_path, size)
                    
                def generate_thumbnail(self, file_path, size=(256, 256)):
                    return self._create_placeholder_thumbnail(file_path, size)
                    
                def _create_placeholder_thumbnail(self, file_path, size=(256, 256)):
                    """Create a simple placeholder thumbnail"""
                    try:
                        from pathlib import Path
                        from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
                        from PySide6.QtCore import Qt
                        
                        # Create a simple placeholder pixmap
                        pixmap = QPixmap(size[0], size[1])
                        pixmap.fill(QColor(60, 60, 60))
                        
                        painter = QPainter(pixmap)
                        painter.setPen(QColor(200, 200, 200))
                        painter.setFont(QFont("Arial", 12))
                        
                        # Draw file extension
                        file_ext = Path(file_path).suffix.upper() if hasattr(Path(file_path), 'suffix') else "FILE"
                        painter.drawText(pixmap.rect(), 0x0004, file_ext)  # Qt.AlignCenter equivalent
                        painter.end()
                        
                        # Save to cache if possible
                        if self._cache_dir:
                            cache_file = self._cache_dir / f"fallback_{hash(str(file_path))}_{size[0]}x{size[1]}.png"
                            pixmap.save(str(cache_file))
                            return str(cache_file)
                            
                    except Exception as e:
                        print(f"⚠️ Fallback thumbnail creation error: {e}")
                    return None
                    
                def clear_cache_for_file(self, file_path):
                    pass
                    
            return FallbackThumbnailService()
        
        def _get_screenshot_icon_path(self) -> Optional[str]:
            """Get the path to the custom screenshot icon - Single Responsibility"""
            try:
                # Method 1: Check current Asset Manager installation directory (when running in Maya)
                current_file = Path(__file__)
                
                # If we're running from Maya's assetManager installation
                if "assetManager" in str(current_file):
                    # Navigate up to find the assetManager root directory
                    asset_manager_root = current_file
                    while asset_manager_root.name != "assetManager" and asset_manager_root.parent != asset_manager_root:
                        asset_manager_root = asset_manager_root.parent
                    
                    # Check for icon in the assetManager directory
                    icon_path = asset_manager_root / "screen-shot_icon.png"
                    if icon_path.exists():
                        return str(icon_path)
                
                # Method 2: Check the source icons directory (development/testing)
                root_dir = current_file.parent.parent.parent.parent
                icon_path = root_dir / "icons" / "screen-shot_icon.png"
                
                if icon_path.exists():
                    return str(icon_path)
                
                # Method 3: Try to find Maya scripts directory with our icon
                try:
                    from pathlib import Path as PathLib
                    home = PathLib.home()
                    maya_paths = [
                        home / "OneDrive" / "Documents" / "maya" / "scripts" / "assetManager" / "screen-shot_icon.png",
                        home / "Documents" / "maya" / "scripts" / "assetManager" / "screen-shot_icon.png"
                    ]
                    
                    for maya_path in maya_paths:
                        if maya_path.exists():
                            return str(maya_path)
                            
                except Exception:
                    pass
                
                return None
                
            except Exception as e:
                print(f"🔧 Could not resolve screenshot icon path: {e}")
                return None
        
        def _create_ui(self) -> None:
            """Create the user interface - Single Responsibility"""
            # Prevent multiple initialization
            if self._preview_label is not None:
                return
                
            layout = QVBoxLayout(self)  # type: ignore
            layout.setContentsMargins(4, 4, 4, 4)  # type: ignore
            
            # Preview image
            self._preview_label = QLabel()  # type: ignore
            self._preview_label.setAlignment(Qt.AlignCenter)  # type: ignore
            self._preview_label.setMinimumSize(200, 200)  # type: ignore
            self._preview_label.setStyleSheet("border: none; background: transparent;")  # type: ignore
            self._preview_label.setText("No asset selected")  # type: ignore
            
            # Scroll area for preview with auto-sizing
            self._scroll_area = QScrollArea()  # type: ignore
            self._scroll_area.setWidget(self._preview_label)  # type: ignore
            self._scroll_area.setWidgetResizable(True)  # type: ignore
            self._scroll_area.setAlignment(Qt.AlignCenter)  # type: ignore
            self._scroll_area.setStyleSheet("QScrollArea { border: 1px solid gray; background: #2b2b2b; }")  # type: ignore
            layout.addWidget(self._scroll_area)  # type: ignore
            
            # Zoom controls
            zoom_layout = QHBoxLayout()  # type: ignore
            
            zoom_out_btn = QPushButton("Zoom -")  # type: ignore
            zoom_out_btn.setToolTip("Zoom out to see more of the preview")  # type: ignore
            zoom_out_btn.clicked.connect(self._zoom_out)  # type: ignore
            zoom_layout.addWidget(zoom_out_btn)  # type: ignore
            
            self._zoom_label = QLabel("100%")  # type: ignore
            self._zoom_label.setAlignment(Qt.AlignCenter)  # type: ignore
            self._zoom_label.setMinimumWidth(60)  # type: ignore
            zoom_layout.addWidget(self._zoom_label)  # type: ignore
            
            zoom_in_btn = QPushButton("Zoom +")  # type: ignore
            zoom_in_btn.setToolTip("Zoom in to see more detail")  # type: ignore
            zoom_in_btn.clicked.connect(self._zoom_in)  # type: ignore
            zoom_layout.addWidget(zoom_in_btn)  # type: ignore
            
            zoom_fit_btn = QPushButton("Fit")  # type: ignore
            zoom_fit_btn.setToolTip("Fit preview to window size")  # type: ignore
            zoom_fit_btn.clicked.connect(self._zoom_fit)  # type: ignore
            zoom_layout.addWidget(zoom_fit_btn)  # type: ignore
            
            zoom_100_btn = QPushButton("1:1")  # type: ignore
            zoom_100_btn.setToolTip("Reset zoom to actual size (100%)")  # type: ignore
            zoom_100_btn.clicked.connect(self._zoom_100)  # type: ignore
            zoom_layout.addWidget(zoom_100_btn)  # type: ignore
            
            # Screenshot capture button (Manual screenshot feature)
            screenshot_icon_path = self._get_screenshot_icon_path()
            if screenshot_icon_path:
                # Use custom screenshot icon
                screenshot_btn = QPushButton()  # type: ignore
                icon = QIcon(screenshot_icon_path)  # type: ignore
                screenshot_btn.setIcon(icon)  # type: ignore
                screenshot_btn.setIconSize(screenshot_btn.size())  # type: ignore
                print(f"📸 Using custom screenshot icon: {Path(screenshot_icon_path).name}")
            else:
                # Fallback to emoji if custom icon not found
                screenshot_btn = QPushButton("📸")  # type: ignore
                print("📸 Using emoji fallback for screenshot button")
            
            screenshot_btn.setToolTip("Capture Maya viewport screenshot as asset thumbnail")  # type: ignore
            screenshot_btn.setFixedSize(28, 28)  # type: ignore
            screenshot_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 14px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)  # type: ignore
            screenshot_btn.clicked.connect(self._capture_screenshot)  # type: ignore
            zoom_layout.addWidget(screenshot_btn)  # type: ignore
            
            # Clear Previewer button
            clear_btn = QPushButton("Clear")  # type: ignore
            clear_btn.setToolTip("Clear the preview and reset view")  # type: ignore
            clear_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #c1180a;
                }
            """)  # type: ignore
            clear_btn.clicked.connect(self._on_clear_preview)  # type: ignore
            zoom_layout.addWidget(clear_btn)  # type: ignore
            
            zoom_layout.addStretch()  # type: ignore
            layout.addLayout(zoom_layout)  # type: ignore
            
            # Remove integrated asset information - now handled by dedicated RIGHT_B metadata panel
            # This follows Single Responsibility Principle - preview widget only handles preview
        
        def set_asset(self, asset: Asset) -> None:
            """Set the asset to preview - Single Responsibility (preview only)"""
            self._current_asset = asset
            self._update_preview()
            # Note: Asset info is now handled by separate metadata panel
        
        def clear_preview(self) -> None:
            """Clear the preview - Single Responsibility"""
            self._current_asset = None
            if self._preview_label:
                self._preview_label.clear()  # type: ignore
                self._preview_label.setText("No asset selected")  # type: ignore
        
        def _on_clear_preview(self) -> None:
            """Clear preview and reset zoom/pan - User action handler"""
            # Reset zoom factor
            self._zoom_factor = 1.0
            # Clear the preview (also resets pan offset)
            self.clear_preview()
            # Update zoom label
            self._update_zoom_label()
            print("✅ Preview cleared - zoom and pan reset")
        
        def _update_preview(self) -> None:
            """Update preview image - Single Responsibility"""
            if not self._current_asset or not self._preview_label:
                return
            
            try:
                # Get thumbnail
                thumbnail_path = self._thumbnail_service.get_cached_thumbnail(  # type: ignore
                    self._current_asset.file_path, (256, 256)  # type: ignore
                )
                
                print(f"Asset Preview: thumbnail_path = {thumbnail_path}")
                if thumbnail_path:
                    print(f"Asset Preview: path exists = {Path(thumbnail_path).exists()}")
                
                if not thumbnail_path:
                    # Generate thumbnail
                    thumbnail_path = self._thumbnail_service.generate_thumbnail(  # type: ignore
                        self._current_asset.file_path, (256, 256)  # type: ignore
                    )
                
                if thumbnail_path and Path(thumbnail_path).exists():
                    pixmap = QPixmap(thumbnail_path)  # type: ignore
                    print(f"Asset Preview: pixmap is null = {pixmap.isNull()}")  # type: ignore
                    if not pixmap.isNull():  # type: ignore
                        # Store original pixmap for zooming
                        self._original_pixmap = pixmap
                        
                        # Apply current zoom
                        self._apply_zoom()
                    else:
                        self._show_placeholder()
                else:
                    self._show_placeholder()
                    
            except Exception as e:
                print(f"Error updating preview: {e}")
                self._show_placeholder()
        
        def _show_placeholder(self) -> None:
            """Show placeholder when no preview available - Single Responsibility"""
            if not self._current_asset or not self._preview_label:
                return
            
            asset_type = self._current_asset.asset_type.upper()  # type: ignore
            self._preview_label.clear()  # type: ignore
            self._preview_label.setText(f"{asset_type}\nPREVIEW\nNOT AVAILABLE")  # type: ignore

        # Zoom functionality methods
        def _zoom_in(self) -> None:
            """Zoom in by 25%"""
            self._zoom_factor *= 1.25
            self._apply_zoom()
        
        def _zoom_out(self) -> None:
            """Zoom out by 25%"""
            self._zoom_factor *= 0.8
            self._apply_zoom()
        
        def _zoom_fit(self) -> None:
            """Fit image to view"""
            if self._original_pixmap and self._preview_label:
                # Calculate scale to fit the available space
                label_size = self._preview_label.parent().size()  # type: ignore
                pixmap_size = self._original_pixmap.size()  # type: ignore
                
                scale_x = label_size.width() / pixmap_size.width()  # type: ignore
                scale_y = label_size.height() / pixmap_size.height()  # type: ignore
                self._zoom_factor = min(scale_x, scale_y, 1.0)  # Don't enlarge small images
                self._apply_zoom()
        
        def _zoom_100(self) -> None:
            """Reset zoom to 100% (actual size)"""
            self._zoom_factor = 1.0
            self._apply_zoom()
        
        def _apply_zoom(self) -> None:
            """Apply current zoom factor to the image"""
            if not self._original_pixmap or not self._preview_label:
                return
            
            # Calculate new size
            original_size = self._original_pixmap.size()  # type: ignore
            new_size = original_size * self._zoom_factor  # type: ignore
            
            # Scale the pixmap
            scaled_pixmap = self._original_pixmap.scaled(  # type: ignore
                new_size,
                Qt.KeepAspectRatio,  # type: ignore
                Qt.SmoothTransformation  # type: ignore
            )
            
            # Set pixmap and let scroll area handle sizing
            self._preview_label.setPixmap(scaled_pixmap)  # type: ignore
            
            self._update_zoom_label()
        
        def _update_zoom_label(self) -> None:
            """Update zoom percentage label"""
            if hasattr(self, '_zoom_label'):
                percentage = int(self._zoom_factor * 100)
                self._zoom_label.setText(f"{percentage}%")  # type: ignore
        
        def wheelEvent(self, event) -> None:
            """Handle mouse wheel for zooming - Improved UX"""
            # Always allow wheel zoom (with or without Ctrl)
            delta = event.angleDelta().y()  # type: ignore
            if delta > 0:
                self._zoom_in()
            else:
                self._zoom_out()
            event.accept()  # type: ignore

        def _capture_screenshot(self) -> None:
            """Capture Maya viewport screenshot - Enhanced User Experience"""
            if not self._current_asset:
                # Show user-friendly message
                if hasattr(self, 'parent') and self.parent():
                    try:
                        from PySide6.QtWidgets import QMessageBox  # type: ignore
                        QMessageBox.information(self.parent(), "No Asset Selected",   # type: ignore
                                              "Please select an asset first to capture a screenshot thumbnail.")
                    except ImportError:
                        print("Please select an asset first to capture a screenshot")
                return
            
            try:
                # Validate current asset before opening dialog
                if not hasattr(self._current_asset, 'file_path'):
                    raise TypeError(f"Cannot open screenshot dialog: asset is type {type(self._current_asset)}, not Asset object")
                
                # Create and show screenshot capture dialog
                dialog = ScreenshotCaptureDialog(self._current_asset, self)  # type: ignore
                
                # Set refresh callback to update preview after capture
                dialog.set_refresh_callback(self._refresh_after_screenshot)  # type: ignore
                
                # Show dialog
                dialog.exec()  # type: ignore
                
            except Exception as e:
                import traceback
                print(f"Error opening screenshot dialog: {e}")
                print(f"Asset type: {type(self._current_asset)}")
                print(f"Traceback:\n{traceback.format_exc()}")
                # Fallback: Show error message if available
                if hasattr(self, 'parent') and self.parent():
                    try:
                        from PySide6.QtWidgets import QMessageBox  # type: ignore
                        QMessageBox.warning(self.parent(), "Screenshot Error",   # type: ignore
                                          f"Failed to open screenshot capture:\n{str(e)}")
                    except ImportError:
                        print(f"Screenshot capture error: {e}")
        
        def _refresh_after_screenshot(self) -> None:
            """Refresh preview after screenshot capture - Callback for enhanced UX"""
            try:
                # Force thumbnail regeneration by clearing cache if possible
                if self._thumbnail_service and self._current_asset and self._current_asset.file_path:
                    # Clear cache for this specific asset using EMSA interface
                    try:
                        asset_path = Path(self._current_asset.file_path)
                        self._thumbnail_service.clear_cache_for_file(asset_path)  # type: ignore
                        print(f"✅ EMSA thumbnail cache cleared for {asset_path.name}")
                    except Exception as cache_error:
                        print(f"Note: Could not clear thumbnail cache: {cache_error}")
                
                # Update preview with new thumbnail
                self._update_preview()
                
                print("✅ Preview refreshed after screenshot capture")
                
            except Exception as e:
                print(f"Error refreshing preview after screenshot: {e}")
                # Still try to update preview even if cache clearing failed
                try:
                    self._update_preview()
                except Exception as update_error:
                    print(f"Failed to update preview: {update_error}")

else:
    # PySide6 not available; provide fallback class
    class AssetPreviewWidget:  # type: ignore
        def __init__(self, parent=None):
            print("PySide6 not available - AssetPreviewWidget disabled")
        
        def set_asset(self, asset):
            pass
        
        def clear_preview(self):
            pass
