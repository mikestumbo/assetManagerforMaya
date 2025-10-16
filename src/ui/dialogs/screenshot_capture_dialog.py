# -*- coding: utf-8 -*-
"""
Screenshot Capture Dialog
Manual screenshot capture UI with Maya viewport integration
Follows Clean Code principles with Single Responsibility

Author: Mike Stumbo
EMSA Integration: Enhanced User Experience
"""

from typing import Optional, Callable
from pathlib import Path
import tempfile
import shutil
import os
import time

# PySide6 for Maya 2025+
try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
        QPushButton, QCheckBox, QWidget, QMessageBox
    )
    from PySide6.QtCore import Qt
    PYSIDE_AVAILABLE = True
except ImportError:
    print("❌ PySide6 not available - Screenshot dialog disabled")
    PYSIDE_AVAILABLE = False
    # Fallback definitions
    QDialog = QVBoxLayout = QHBoxLayout = QLabel = QComboBox = None
    QPushButton = QCheckBox = QWidget = QMessageBox = Qt = None

# Import core models - suppress import warnings for standalone testing
try:
    from ...core.models.asset import Asset  # type: ignore
    from ...core.interfaces.thumbnail_service import IThumbnailService  # type: ignore
    from ...core.container import get_container  # type: ignore
except ImportError:
    # Fallback definitions for when imports fail
    class Asset:  # type: ignore
        def __init__(self):
            self.file_path = None
    
    class IThumbnailService:  # type: ignore
        pass
    
    def get_container():  # type: ignore
        return None


if PYSIDE_AVAILABLE and QDialog is not None:
    class ScreenshotCaptureDialog(QDialog):  # type: ignore
        """
        Professional Screenshot Capture Dialog
        Manual Maya viewport screenshot with advanced options
        Single Responsibility: Screenshot capture UI only
        """
        
        def __init__(self, asset: Asset, parent=None):
            super().__init__(parent)
            
            # Validate asset parameter - handle both Asset objects and strings
            if isinstance(asset, str):
                raise TypeError(f"ScreenshotCaptureDialog requires Asset object, got string: {asset}")
            if not hasattr(asset, 'file_path'):
                raise TypeError(f"ScreenshotCaptureDialog requires Asset object with file_path attribute")
            
            # Dependency injection
            container = get_container()  # type: ignore
            self._thumbnail_service = container.resolve(IThumbnailService)  # type: ignore
            
            # State
            self._asset = asset
            self._callback_refresh: Optional[Callable] = None
            
            # UI components
            self._res_combo: Optional[QComboBox] = None  # type: ignore
            self._quality_combo: Optional[QComboBox] = None  # type: ignore
            self._smooth_shading: Optional[QCheckBox] = None  # type: ignore
            self._wireframe_on_shaded: Optional[QCheckBox] = None  # type: ignore
            self._show_grid: Optional[QCheckBox] = None  # type: ignore
            
            # Setup
            self._create_ui()
            self._setup_dialog()
        
        def set_refresh_callback(self, callback: Callable) -> None:
            """Set callback to refresh thumbnail after capture - Dependency Injection pattern"""
            self._callback_refresh = callback
        
        def _setup_dialog(self) -> None:
            """Setup dialog properties - Single Responsibility"""
            self.setWindowTitle("Capture Maya Screenshot")
            self.setModal(True)
            self.resize(420, 400)
            
            # Set custom window icon
            try:
                icon_path = self._get_screenshot_icon_path()
                if icon_path:
                    from PySide6.QtGui import QIcon
                    self.setWindowIcon(QIcon(icon_path))
                    print(f"✅ Set custom screenshot dialog icon: {icon_path}")
                else:
                    print(f"⚠️ Screenshot icon not found, using default")
            except Exception as e:
                print(f"⚠️ Could not set custom screenshot dialog icon: {e}")
            
            # Center on parent
            if self.parent():
                parent_geo = self.parent().geometry()  # type: ignore
                x = parent_geo.x() + (parent_geo.width() - self.width()) // 2  # type: ignore
                y = parent_geo.y() + (parent_geo.height() - self.height()) // 2  # type: ignore
                self.move(x, y)  # type: ignore
        
        def _create_ui(self) -> None:
            """Create the user interface - Single Responsibility"""
            layout = QVBoxLayout(self)  # type: ignore
            layout.setContentsMargins(15, 15, 15, 15)  # type: ignore
            layout.setSpacing(12)  # type: ignore
            
            # Instructions header
            self._create_instructions_section(layout)
            
            # Resolution options
            self._create_resolution_section(layout)
            
            # Quality options
            self._create_quality_section(layout)
            
            # Viewport settings
            self._create_viewport_section(layout)
            
            # Action buttons
            self._create_buttons_section(layout)
        
        def _create_instructions_section(self, layout) -> None:
            """Create instructions section - Single Responsibility"""
            asset_name = Path(self._asset.file_path).name if self._asset.file_path else "Unknown Asset"
            
            info_label = QLabel(f"📋 Capture Screenshot Instructions:\n\n"  # type: ignore
                               f"🎯 Asset: {asset_name}\n"
                               f"1. Position your asset in Maya's viewport\n"
                               f"2. Choose resolution and quality settings\n"
                               f"3. Click 'Capture Screenshot' to save as thumbnail\n"
                               f"4. The new thumbnail will replace the current preview")
            
            info_label.setWordWrap(True)  # type: ignore
            info_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f8ff;
                    border: 2px solid #4A90E2;
                    border-radius: 8px;
                    padding: 12px;
                    margin: 5px 0;
                    font-size: 11px;
                    line-height: 1.4;
                }
            """)  # type: ignore
            layout.addWidget(info_label)  # type: ignore
        
        def _create_resolution_section(self, layout) -> None:
            """Create resolution options section - Single Responsibility"""
            res_group = QWidget()  # type: ignore
            res_layout = QVBoxLayout(res_group)  # type: ignore
            res_layout.addWidget(QLabel("🖼️ Screenshot Resolution:"))  # type: ignore
            
            self._res_combo = QComboBox()  # type: ignore
            resolution_options = [
                ("Standard Quality (256×256)", 256),
                ("High Quality (512×512)", 512), 
                ("Ultra HD (1024×1024)", 1024),
                ("Maximum Quality (2048×2048)", 2048)
            ]
            
            for name, size in resolution_options:
                self._res_combo.addItem(name, size)  # type: ignore
            
            self._res_combo.setCurrentIndex(2)  # Default to Ultra HD  # type: ignore
            if self._res_combo:
                self._res_combo.setStyleSheet("""
                    QComboBox {
                        padding: 6px;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        font-size: 11px;
                    }
                """)  # type: ignore
            
            res_layout.addWidget(self._res_combo)  # type: ignore
            layout.addWidget(res_group)  # type: ignore
        
        def _create_quality_section(self, layout) -> None:
            """Create quality options section - Single Responsibility"""
            quality_group = QWidget()  # type: ignore
            quality_layout = QVBoxLayout(quality_group)  # type: ignore
            quality_layout.addWidget(QLabel("✨ Image Quality:"))  # type: ignore
            
            self._quality_combo = QComboBox()  # type: ignore
            self._quality_combo.addItem("High Quality (PNG)", "png")  # type: ignore
            self._quality_combo.addItem("Maximum Quality (TIFF)", "tiff")  # type: ignore
            
            if self._quality_combo:
                self._quality_combo.setStyleSheet("""
                    QComboBox {
                        padding: 6px;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        font-size: 11px;
                    }
                """)  # type: ignore
            
            quality_layout.addWidget(self._quality_combo)  # type: ignore
            layout.addWidget(quality_group)  # type: ignore
        
        def _create_viewport_section(self, layout) -> None:
            """Create viewport settings section - Single Responsibility"""
            viewport_group = QWidget()  # type: ignore
            viewport_layout = QVBoxLayout(viewport_group)  # type: ignore
            viewport_layout.addWidget(QLabel("🔧 Viewport Settings:"))  # type: ignore
            
            # Viewport options with professional defaults
            self._smooth_shading = QCheckBox("Smooth Shading")  # type: ignore
            self._smooth_shading.setChecked(True)  # type: ignore
            self._smooth_shading.setToolTip("Enable smooth shading for professional quality")  # type: ignore
            
            self._wireframe_on_shaded = QCheckBox("Wireframe on Shaded")  # type: ignore
            self._wireframe_on_shaded.setChecked(False)  # type: ignore
            self._wireframe_on_shaded.setToolTip("Show wireframe overlay on shaded geometry")  # type: ignore
            
            self._show_grid = QCheckBox("Show Grid")  # type: ignore
            self._show_grid.setChecked(False)  # type: ignore
            self._show_grid.setToolTip("Display Maya's grid in the screenshot")  # type: ignore
            
            # Style checkboxes
            checkbox_style = """
                QCheckBox {
                    font-size: 11px;
                    padding: 4px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }
                QCheckBox::indicator:checked {
                    background-color: #4A90E2;
                    border: 1px solid #4A90E2;
                    border-radius: 3px;
                }
            """
            
            for checkbox in [self._smooth_shading, self._wireframe_on_shaded, self._show_grid]:
                checkbox.setStyleSheet(checkbox_style)  # type: ignore
                viewport_layout.addWidget(checkbox)  # type: ignore
            
            layout.addWidget(viewport_group)  # type: ignore
        
        def _create_buttons_section(self, layout) -> None:
            """Create action buttons section - Single Responsibility"""
            button_layout = QHBoxLayout()  # type: ignore
            
            # Preview settings button
            preview_btn = QPushButton("🔍 Preview Settings")  # type: ignore
            preview_btn.setToolTip("Apply viewport settings to see live preview")  # type: ignore
            preview_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 1px solid #ccc;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border-color: #999;
                }
            """)  # type: ignore
            preview_btn.clicked.connect(self._apply_viewport_settings)  # type: ignore
            
            # Capture screenshot button (primary action)
            capture_btn = QPushButton("📸 Capture Screenshot")  # type: ignore
            capture_btn.setToolTip("Capture high-resolution screenshot and save as asset thumbnail")  # type: ignore
            capture_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)  # type: ignore
            capture_btn.clicked.connect(self._capture_screenshot)  # type: ignore
            
            # Cancel button
            cancel_btn = QPushButton("Cancel")  # type: ignore
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 1px solid #ccc;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border-color: #999;
                }
            """)  # type: ignore
            cancel_btn.clicked.connect(self.reject)  # type: ignore
            
            # Layout buttons
            button_layout.addWidget(preview_btn)  # type: ignore
            button_layout.addStretch()  # type: ignore
            button_layout.addWidget(capture_btn)  # type: ignore
            button_layout.addWidget(cancel_btn)  # type: ignore
            
            layout.addLayout(button_layout)  # type: ignore
        
        def _apply_viewport_settings(self) -> None:
            """Apply viewport settings for preview - Maya Integration"""
            try:
                import maya.cmds as cmds  # pyright: ignore[reportMissingImports]
                
                # Get active viewport
                active_panel = cmds.getPanel(withFocus=True)
                if not cmds.getPanel(typeOf=active_panel) == 'modelPanel':
                    model_panels = cmds.getPanel(type='modelPanel')
                    if model_panels:
                        active_panel = model_panels[0]
                    else:
                        QMessageBox.warning(self, "No Viewport", "No Maya viewport found for preview.")  # type: ignore
                        return
                
                # Apply viewport settings
                if self._smooth_shading and self._smooth_shading.isChecked():  # type: ignore
                    cmds.modelEditor(active_panel, edit=True, displayAppearance='smoothShaded')
                else:
                    cmds.modelEditor(active_panel, edit=True, displayAppearance='wireframe')
                
                if self._wireframe_on_shaded:  # type: ignore
                    cmds.modelEditor(active_panel, edit=True, 
                                   wireframeOnShaded=self._wireframe_on_shaded.isChecked())  # type: ignore
                
                if self._show_grid:  # type: ignore
                    cmds.modelEditor(active_panel, edit=True, 
                                   grid=self._show_grid.isChecked())  # type: ignore
                
                print("✅ Viewport settings applied for screenshot preview")
                
            except Exception as e:
                print(f"Error applying viewport settings: {e}")
                QMessageBox.warning(self, "Settings Error",   # type: ignore
                                  f"Failed to apply viewport settings:\n{str(e)}")
        
        def _capture_screenshot(self) -> None:
            """Capture screenshot using Maya playblast - Main Action"""
            try:
                import maya.cmds as cmds  # pyright: ignore[reportMissingImports]
                
                # Validate asset
                if not self._asset or not self._asset.file_path:
                    raise Exception("No asset selected for screenshot")
                
                # Get settings from UI
                resolution = self._res_combo.currentData() if self._res_combo else 1024  # type: ignore
                file_format = self._quality_combo.currentData() if self._quality_combo else "png"  # type: ignore
                
                # Get active viewport
                active_panel = cmds.getPanel(withFocus=True)
                if not cmds.getPanel(typeOf=active_panel) == 'modelPanel':
                    model_panels = cmds.getPanel(type='modelPanel')
                    if model_panels:
                        active_panel = model_panels[0]
                    else:
                        raise Exception("No Maya viewport found for screenshot")
                
                # Apply final viewport settings
                self._apply_viewport_settings()
                
                # Create temporary file
                temp_dir = tempfile.mkdtemp()
                temp_filename = f"maya_screenshot_{int(time.time())}.{file_format}"
                temp_path = os.path.join(temp_dir, temp_filename)
                
                # Capture screenshot with Maya playblast
                print(f"📸 Capturing screenshot: {resolution}x{resolution} {file_format.upper()}")
                
                result = cmds.playblast(
                    filename=temp_path,
                    format='image',
                    compression=file_format,
                    quality=100,
                    percent=100,
                    width=resolution,
                    height=resolution,
                    viewer=False,
                    showOrnaments=False,
                    offScreen=True,
                    frame=cmds.currentTime(query=True),
                    completeFilename=temp_path
                )
                
                # Maya adds frame number to filename, find the actual file
                actual_files = [f for f in os.listdir(temp_dir) if f.startswith("maya_screenshot_")]
                if not actual_files:
                    raise Exception("Screenshot file not created")
                
                actual_temp_path = os.path.join(temp_dir, actual_files[0])
                
                # Save screenshot as asset thumbnail using EMSA thumbnail service
                self._save_screenshot_as_thumbnail(actual_temp_path, file_format, resolution)
                
                # Cleanup
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Success feedback
                QMessageBox.information(self, "Screenshot Captured! 📸",   # type: ignore
                                      f"High-resolution screenshot saved successfully!\n\n"
                                      f"Resolution: {resolution}×{resolution}\n"
                                      f"Format: {file_format.upper()}\n"
                                      f"Asset: {Path(self._asset.file_path).name}\n\n"
                                      f"The asset thumbnail has been updated automatically.")
                
                # Trigger refresh callback
                if self._callback_refresh:
                    self._callback_refresh()
                
                # Close dialog
                self.accept()  # type: ignore
                
                print(f"✅ Screenshot captured successfully: {resolution}x{resolution} {file_format.upper()}")
                
            except Exception as e:
                print(f"❌ Screenshot capture error: {e}")
                QMessageBox.warning(self, "Capture Failed",   # type: ignore
                                  f"Failed to capture screenshot:\n{str(e)}")
        
        def _save_screenshot_as_thumbnail(self, temp_path: str, file_format: str, resolution: int) -> None:
            """Save screenshot as asset thumbnail using EMSA service - Single Responsibility"""
            try:
                # Validate asset file path
                if not self._asset.file_path:
                    raise Exception("Asset file path is not available")
                
                # Create thumbnail directory for this asset
                asset_dir = Path(self._asset.file_path).parent
                asset_name = Path(self._asset.file_path).stem
                thumbnail_dir = asset_dir / ".thumbnails"
                thumbnail_dir.mkdir(exist_ok=True)
                
                # Save screenshot as asset thumbnail
                thumbnail_path = thumbnail_dir / f"{asset_name}_screenshot.{file_format}"
                shutil.copy2(temp_path, str(thumbnail_path))
                
                # Invalidate EMSA thumbnail cache for this asset
                if self._thumbnail_service:
                    # Force regeneration by clearing cache using EMSA interface
                    try:
                        asset_path = Path(self._asset.file_path)
                        self._thumbnail_service.clear_cache_for_file(asset_path)  # type: ignore
                        print(f"✅ EMSA thumbnail cache cleared for {asset_name}")
                    except AttributeError:
                        # Fallback: Assume cache will be invalidated automatically
                        print(f"✅ Screenshot saved, cache will update automatically")
                    except Exception as cache_error:
                        print(f"Note: Cache clearing error: {cache_error}")
                
                print(f"✅ Thumbnail saved: {thumbnail_path}")
                
            except Exception as e:
                print(f"❌ Error saving thumbnail: {e}")
                raise Exception(f"Failed to save thumbnail: {str(e)}")
        
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
                root_dir = current_file.parent.parent.parent
                icon_path = root_dir / "icons" / "screen-shot_icon.png"
                
                if icon_path.exists():
                    return str(icon_path)
                
                # Method 3: Try to find Maya scripts directory with our icon
                try:
                    home = Path.home()
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

else:
    # PySide6 not available; provide fallback class
    class ScreenshotCaptureDialog:  # type: ignore
        def __init__(self, asset, parent=None):
            print("PySide6 not available - Screenshot capture dialog disabled")
        
        def set_refresh_callback(self, callback):
            pass
        
        def exec(self):
            return False
