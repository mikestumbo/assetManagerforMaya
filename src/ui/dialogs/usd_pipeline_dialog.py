# -*- coding: utf-8 -*-
"""
USD Pipeline Dialog
Main UI for Maya → USD export workflow

Author: Mike Stumbo
Version: 1.4.0
"""

from pathlib import Path
from typing import Optional
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QCheckBox, QRadioButton,
    QProgressBar, QTextEdit, QFileDialog, QSpinBox, QComboBox,
    QButtonGroup, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

# Import our services
from ...core.interfaces.usd_export_service import USDExportOptions
from ...services.usd import USDExportServiceImpl, MayaSceneParserImpl, USDRigConverterImpl

logger = logging.getLogger(__name__)


class USDPipelineDialog(QDialog):  # type: ignore
    """
    USD Pipeline Creator Dialog
    
    Clean Code: Single Responsibility - USD export UI
    """
    
    # Signals
    export_started = Signal()
    export_completed = Signal(bool, str)  # success, message
    
    def __init__(self, parent=None):  # type: ignore
        super().__init__(parent)
        
        # Services
        self._scene_parser: Optional[MayaSceneParserImpl] = None
        self._export_service: Optional[USDExportServiceImpl] = None
        self._rig_converter: Optional[USDRigConverterImpl] = None
        
        # State
        self._is_exporting = False
        self._progress_timer: Optional[QTimer] = None
        
        # Initialize services
        self._init_services()
        
        # Setup UI
        self._setup_window()
        self._create_ui()
        
        logger.info("USD Pipeline Dialog initialized")
    
    def _setup_window(self) -> None:
        """Setup window properties"""
        self.setWindowTitle("USD Pipeline Creator")
        self.setMinimumSize(700, 800)
        self.resize(750, 850)
        
        # Set window flags for Maya integration
        if self.parent() is not None:
            self.setWindowFlags(
                Qt.WindowType.Dialog |
                Qt.WindowType.WindowCloseButtonHint |
                Qt.WindowType.WindowStaysOnTopHint
            )
    
    def _init_services(self) -> None:
        """Initialize USD pipeline services"""
        try:
            # Create scene parser
            self._scene_parser = MayaSceneParserImpl()
            
            # Create rig converter
            self._rig_converter = USDRigConverterImpl()
            
            # Create export service with dependencies
            self._export_service = USDExportServiceImpl(
                scene_parser=self._scene_parser,
                material_converter=None,  # TODO: Material converter
                rig_converter=self._rig_converter
            )
            
            logger.info("USD pipeline services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            QMessageBox.warning(
                self,
                "Service Initialization Error",
                f"Failed to initialize USD pipeline services:\n{e}\n\nSome features may not work."
            )
    
    def _create_ui(self) -> None:
        """Create the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Title
        title_label = QLabel("USD PIPELINE CREATOR")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Section 1: Source Selection
        source_group = self._create_source_section()
        main_layout.addWidget(source_group)
        
        # Section 2: USD Options
        options_group = self._create_options_section()
        main_layout.addWidget(options_group)
        
        # Section 3: Validation
        validation_group = self._create_validation_section()
        main_layout.addWidget(validation_group)
        
        # Progress section
        progress_group = self._create_progress_section()
        main_layout.addWidget(progress_group)
        
        # Buttons
        button_layout = self._create_button_section()
        main_layout.addLayout(button_layout)
        
        main_layout.addStretch()
    
    def _create_source_section(self) -> QGroupBox:
        """Create source selection section"""
        group = QGroupBox("Source Selection")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # Maya scene file
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Source Maya Scene:"))
        self._source_file_edit = QLineEdit()
        self._source_file_edit.setPlaceholderText("Select a Maya scene file (.ma or .mb)")
        file_layout.addWidget(self._source_file_edit, 1)
        
        self._browse_source_btn = QPushButton("Browse...")
        self._browse_source_btn.clicked.connect(self._on_browse_source)
        file_layout.addWidget(self._browse_source_btn)
        
        layout.addLayout(file_layout)
        
        # Include options
        self._include_geometry_cb = QCheckBox("Include Geometry")
        self._include_geometry_cb.setChecked(True)
        layout.addWidget(self._include_geometry_cb)
        
        self._include_rigging_cb = QCheckBox("Include Rigging (Skin Clusters)")
        self._include_rigging_cb.setChecked(True)
        layout.addWidget(self._include_rigging_cb)
        
        self._include_materials_cb = QCheckBox("Include Materials (RenderMan)")
        self._include_materials_cb.setChecked(True)
        layout.addWidget(self._include_materials_cb)
        
        self._include_animation_cb = QCheckBox("Include Animation")
        self._include_animation_cb.setChecked(False)
        layout.addWidget(self._include_animation_cb)
        
        return group
    
    def _create_options_section(self) -> QGroupBox:
        """Create USD options section"""
        group = QGroupBox("USD Options")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        # USD format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("USD Format:"))
        
        self._format_group = QButtonGroup(self)
        self._usda_radio = QRadioButton(".usda (ASCII)")
        self._usda_radio.setChecked(True)
        self._format_group.addButton(self._usda_radio, 0)
        format_layout.addWidget(self._usda_radio)
        
        self._usdc_radio = QRadioButton(".usdc (Binary)")
        self._format_group.addButton(self._usdc_radio, 1)
        format_layout.addWidget(self._usdc_radio)
        
        self._usdz_radio = QRadioButton(".usdz (Package)")
        self._format_group.addButton(self._usdz_radio, 2)
        format_layout.addWidget(self._usdz_radio)
        
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Output path
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Path:"))
        self._output_path_edit = QLineEdit()
        self._output_path_edit.setPlaceholderText("Select output USD file path")
        output_layout.addWidget(self._output_path_edit, 1)
        
        self._browse_output_btn = QPushButton("Browse...")
        self._browse_output_btn.clicked.connect(self._on_browse_output)
        output_layout.addWidget(self._browse_output_btn)
        
        layout.addLayout(output_layout)
        
        # Material conversion
        material_label = QLabel("Material Conversion:")
        material_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(material_label)
        
        self._material_group = QButtonGroup(self)
        self._preview_surface_radio = QRadioButton("UsdPreviewSurface (Universal)")
        self._preview_surface_radio.setChecked(True)
        self._material_group.addButton(self._preview_surface_radio, 0)
        layout.addWidget(self._preview_surface_radio)
        
        self._renderman_radio = QRadioButton("Preserve RenderMan (Disney/Pixar)")
        self._material_group.addButton(self._renderman_radio, 1)
        layout.addWidget(self._renderman_radio)
        
        # Rigging options
        rigging_label = QLabel("Rigging Options:")
        rigging_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(rigging_label)
        
        self._create_usdskel_cb = QCheckBox("Create UsdSkel structure")
        self._create_usdskel_cb.setChecked(True)
        layout.addWidget(self._create_usdskel_cb)
        
        self._preserve_weights_cb = QCheckBox("Preserve skin weights")
        self._preserve_weights_cb.setChecked(True)
        layout.addWidget(self._preserve_weights_cb)
        
        self._include_bind_pose_cb = QCheckBox("Include bind pose")
        self._include_bind_pose_cb.setChecked(True)
        layout.addWidget(self._include_bind_pose_cb)
        
        # Max influences
        influences_layout = QHBoxLayout()
        influences_layout.addWidget(QLabel("Max Influences:"))
        self._max_influences_spin = QSpinBox()
        self._max_influences_spin.setMinimum(1)
        self._max_influences_spin.setMaximum(16)
        self._max_influences_spin.setValue(4)
        influences_layout.addWidget(self._max_influences_spin)
        influences_layout.addStretch()
        layout.addLayout(influences_layout)
        
        return group
    
    def _create_validation_section(self) -> QGroupBox:
        """Create validation section"""
        group = QGroupBox("Pre-Export Validation")
        layout = QVBoxLayout(group)
        
        self._validation_text = QTextEdit()
        self._validation_text.setReadOnly(True)
        self._validation_text.setMaximumHeight(120)
        self._validation_text.setPlaceholderText("Validation results will appear here...")
        layout.addWidget(self._validation_text)
        
        return group
    
    def _create_progress_section(self) -> QGroupBox:
        """Create progress section"""
        group = QGroupBox("Export Progress")
        layout = QVBoxLayout(group)
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)
        
        # Status label
        self._status_label = QLabel("Ready")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)
        
        return group
    
    def _create_button_section(self) -> QHBoxLayout:
        """Create button section"""
        layout = QHBoxLayout()
        
        # Validate button
        self._validate_btn = QPushButton("Validate Only")
        self._validate_btn.clicked.connect(self._on_validate)
        layout.addWidget(self._validate_btn)
        
        layout.addStretch()
        
        # Export button
        self._export_btn = QPushButton("Convert to USD")
        self._export_btn.setDefault(True)
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        layout.addWidget(self._export_btn)
        
        # Cancel button
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn)
        
        # Close button
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)
        layout.addWidget(self._close_btn)
        
        return layout
    
    # ==================== Event Handlers ====================
    
    def _on_browse_source(self) -> None:
        """Browse for source Maya file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Source Maya Scene",
            "",
            "Maya Files (*.ma *.mb);;All Files (*.*)"
        )
        
        if file_path:
            self._source_file_edit.setText(file_path)
    
    def _on_browse_output(self) -> None:
        """Browse for output USD file"""
        # Get format from radio buttons
        if self._usda_radio.isChecked():
            format_filter = "USD ASCII (*.usda)"
            extension = ".usda"
        elif self._usdc_radio.isChecked():
            format_filter = "USD Binary (*.usdc)"
            extension = ".usdc"
        else:
            format_filter = "USD Package (*.usdz)"
            extension = ".usdz"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output USD File",
            "",
            f"{format_filter};;All Files (*.*)"
        )
        
        if file_path:
            # Ensure proper extension
            path = Path(file_path)
            if path.suffix != extension:
                file_path = str(path.with_suffix(extension))
            
            self._output_path_edit.setText(file_path)
    
    def _on_validate(self) -> None:
        """Validate export options"""
        self._validation_text.clear()
        
        # Get options
        options = self._build_export_options()
        if not options:
            return
        
        # Validate source file
        source_file = Path(self._source_file_edit.text())
        if not source_file.exists():
            self._validation_text.append("❌ Source file does not exist")
            return
        
        # Validate with export service
        if self._export_service:
            is_valid, error_msg = self._export_service.validate_export_options(options)
            
            if is_valid:
                self._validation_text.append("✅ Export options are valid")
                
                # Try to parse scene for additional info
                try:
                    scene_data = self._scene_parser.parse_maya_file(source_file)  # type: ignore
                    self._validation_text.append(f"✅ Meshes found: {len(scene_data.meshes)}")
                    self._validation_text.append(f"✅ Materials found: {len(scene_data.materials)}")
                    
                    if scene_data.joints:
                        self._validation_text.append(f"✅ Joints found: {len(scene_data.joints)}")
                    
                    if scene_data.skin_clusters:
                        self._validation_text.append(f"✅ Skin clusters detected: {len(scene_data.skin_clusters)}")
                    
                    if not scene_data.meshes:
                        self._validation_text.append("⚠️ Warning: No meshes found in scene")
                    
                except Exception as e:
                    self._validation_text.append(f"⚠️ Warning: Could not parse scene: {e}")
            else:
                self._validation_text.append(f"❌ Validation failed: {error_msg}")
        else:
            self._validation_text.append("❌ Export service not available")
    
    def _on_export(self) -> None:
        """Start USD export"""
        if self._is_exporting:
            QMessageBox.warning(self, "Export in Progress", "An export is already in progress.")
            return
        
        # Build options
        options = self._build_export_options()
        if not options:
            return
        
        # Validate
        source_file = Path(self._source_file_edit.text())
        if not source_file.exists():
            QMessageBox.critical(self, "Invalid Source", "Source Maya file does not exist.")
            return
        
        if not self._export_service:
            QMessageBox.critical(self, "Service Error", "Export service is not available.")
            return
        
        # Start export
        self._is_exporting = True
        self._export_btn.setEnabled(False)
        self._validate_btn.setEnabled(False)
        self._browse_source_btn.setEnabled(False)
        self._browse_output_btn.setEnabled(False)
        
        self._status_label.setText("Starting export...")
        self._progress_bar.setValue(0)
        
        self.export_started.emit()
        
        # Start progress timer
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start(100)  # Update every 100ms
        
        # Run export in background (simplified for now)
        try:
            success = self._export_service.export_maya_scene(source_file, options)
            
            self._progress_timer.stop()
            self._is_exporting = False
            
            if success:
                self._progress_bar.setValue(100)
                self._status_label.setText("Export complete!")
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"USD file exported successfully:\n{options.output_path}"
                )
                self.export_completed.emit(True, "Export successful")
            else:
                error_msg = self._export_service.get_last_error() or "Unknown error"
                self._status_label.setText(f"Export failed: {error_msg}")
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    f"USD export failed:\n{error_msg}"
                )
                self.export_completed.emit(False, error_msg)
        
        except Exception as e:
            self._progress_timer.stop()
            self._is_exporting = False
            self._status_label.setText(f"Export error: {e}")
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{e}")
            self.export_completed.emit(False, str(e))
        
        finally:
            self._export_btn.setEnabled(True)
            self._validate_btn.setEnabled(True)
            self._browse_source_btn.setEnabled(True)
            self._browse_output_btn.setEnabled(True)
    
    def _on_cancel(self) -> None:
        """Cancel export"""
        if self._is_exporting and self._export_service:
            self._export_service.cancel_export()
            self._status_label.setText("Cancelling...")
    
    def _update_progress(self) -> None:
        """Update progress display"""
        if self._export_service and self._is_exporting:
            percentage, stage = self._export_service.get_export_progress()
            self._progress_bar.setValue(percentage)
            self._status_label.setText(stage)
    
    def _build_export_options(self) -> Optional[USDExportOptions]:
        """Build export options from UI"""
        # Validate inputs
        source_path = self._source_file_edit.text().strip()
        output_path = self._output_path_edit.text().strip()
        
        if not source_path:
            QMessageBox.warning(self, "Missing Source", "Please select a source Maya scene file.")
            return None
        
        if not output_path:
            QMessageBox.warning(self, "Missing Output", "Please select an output USD file path.")
            return None
        
        # Determine format
        if self._usda_radio.isChecked():
            file_format = "usda"
        elif self._usdc_radio.isChecked():
            file_format = "usdc"
        else:
            file_format = "usdz"
        
        # Build options
        options = USDExportOptions(
            output_path=Path(output_path),
            file_format=file_format,
            export_meshes=self._include_geometry_cb.isChecked(),
            export_materials=self._include_materials_cb.isChecked(),
            export_skeleton=self._include_rigging_cb.isChecked(),
            export_skin_weights=self._preserve_weights_cb.isChecked(),
            preserve_bind_pose=self._include_bind_pose_cb.isChecked(),
            export_animation=self._include_animation_cb.isChecked(),
            convert_renderman=self._preview_surface_radio.isChecked()
        )
        
        return options
