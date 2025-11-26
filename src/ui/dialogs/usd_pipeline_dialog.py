# -*- coding: utf-8 -*-
"""
USD Pipeline Dialog
Main UI for Maya → USD export workflow

Compatibility:
- Maya 2026.3
- MayaUSD 0.34.5
- RenderMan 27

Author: Mike Stumbo
Version: 1.5.0 - Added NURBS Curves Support!
"""

from pathlib import Path
from typing import Optional
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QCheckBox, QRadioButton,
    QProgressBar, QTextEdit, QFileDialog, QSpinBox,
    QButtonGroup, QWidget, QMessageBox, QTabWidget
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

# Import our services
from ...core.interfaces.usd_export_service import USDExportOptions
from ...services.usd import USDExportServiceImpl, MayaSceneParserImpl, USDRigConverterImpl
from ...services.usd.usd_material_converter_impl import USDMaterialConverterImpl

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

        # Restore window geometry if available
        self._restore_geometry()

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

            # Create material converter
            self._material_converter = USDMaterialConverterImpl()

            # Create USD service for plugin availability checks
            from ...services.usd_service_impl import UsdService
            self._usd_service = UsdService()

            # Create rig converter
            self._rig_converter = USDRigConverterImpl()

            # Create export service with dependencies
            self._export_service = USDExportServiceImpl(
                scene_parser=self._scene_parser,
                material_converter=self._material_converter,
                rig_converter=self._rig_converter,
                usd_service=self._usd_service
            )

            # Create import service
            from ...services.usd.usd_import_service_impl import UsdImportServiceImpl
            self._import_service = UsdImportServiceImpl()

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

        # Create tab widget for Export/Import modes
        self._tab_widget = QTabWidget()
        main_layout.addWidget(self._tab_widget)

        # Export Tab
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(12)

        # Section 1: Source Selection
        source_group = self._create_source_section()
        export_layout.addWidget(source_group)

        # Section 2: USD Export Options
        options_group = self._create_export_options_section()
        export_layout.addWidget(options_group)

        # Section 3: Validation
        validation_group = self._create_validation_section()
        export_layout.addWidget(validation_group)

        # Progress section
        progress_group = self._create_progress_section()
        export_layout.addWidget(progress_group)

        export_layout.addStretch()
        self._tab_widget.addTab(export_tab, "Export to USD")

        # Import Tab
        import_tab = QWidget()
        import_layout = QVBoxLayout(import_tab)
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_layout.setSpacing(12)

        # Import sections
        import_source_group = self._create_import_source_section()
        import_layout.addWidget(import_source_group)

        import_options_group = self._create_import_options_section()
        import_layout.addWidget(import_options_group)

        import_validation_group = self._create_import_validation_section()
        import_layout.addWidget(import_validation_group)

        # Import progress section
        import_progress_group = self._create_import_progress_section()
        import_layout.addWidget(import_progress_group)

        import_layout.addStretch()
        self._tab_widget.addTab(import_tab, "Import from USD")

        # Buttons (shared between tabs)
        button_layout = self._create_button_section()
        main_layout.addLayout(button_layout)

    def _create_source_section(self) -> QGroupBox:
        """Create source selection section"""
        group = QGroupBox("Source Selection")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Source type selection
        source_type_layout = QHBoxLayout()
        source_type_layout.addWidget(QLabel("Export From:"))

        self._source_type_group = QButtonGroup(self)
        self._current_scene_radio = QRadioButton("Current Scene")
        self._current_scene_radio.setChecked(True)
        self._current_scene_radio.toggled.connect(self._on_source_type_changed)
        self._source_type_group.addButton(self._current_scene_radio, 0)
        source_type_layout.addWidget(self._current_scene_radio)

        self._file_radio = QRadioButton("Maya File")
        self._file_radio.toggled.connect(self._on_source_type_changed)
        self._source_type_group.addButton(self._file_radio, 1)
        source_type_layout.addWidget(self._file_radio)
        source_type_layout.addStretch()

        layout.addLayout(source_type_layout)

        # Maya scene file (initially disabled)
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Source Maya Scene:"))
        self._source_file_edit = QLineEdit()
        self._source_file_edit.setPlaceholderText("Select a Maya scene file (.ma or .mb)")
        self._source_file_edit.setEnabled(False)
        file_layout.addWidget(self._source_file_edit, 1)

        self._browse_source_btn = QPushButton("Browse...")
        self._browse_source_btn.clicked.connect(self._on_browse_source)
        self._browse_source_btn.setEnabled(False)
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

    def _create_export_options_section(self) -> QGroupBox:
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

        self._include_nurbs_cb = QCheckBox(
            "Include Rig Controls (NURBS) - INDUSTRY FIRST! ✨"
        )
        self._include_nurbs_cb.setChecked(True)
        self._include_nurbs_cb.setToolTip(
            "Export NURBS curves for full character rig with controls.\n"
            "This is groundbreaking - no one else does this!"
        )
        self._include_nurbs_cb.setStyleSheet("font-weight: bold; color: #4CAF50;")
        layout.addWidget(self._include_nurbs_cb)

        self._nurbs_renderable_cb = QCheckBox("Make NURBS curves renderable")
        self._nurbs_renderable_cb.setChecked(False)
        self._nurbs_renderable_cb.setToolTip(
            "If checked, NURBS curves will be renderable geometry.\n"
            "If unchecked (default), they will be guide geometry (non-renderable)."
        )
        layout.addWidget(self._nurbs_renderable_cb)

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

        # Validate button (for export tab)
        self._validate_btn = QPushButton("Validate Only")
        self._validate_btn.clicked.connect(self._on_validate)
        layout.addWidget(self._validate_btn)

        layout.addStretch()

        # Export button (for export tab)
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

        # Import button (for import tab)
        self._import_btn = QPushButton("Import from USD")
        self._import_btn.clicked.connect(self._perform_import)
        self._import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        layout.addWidget(self._import_btn)

        # Cancel button
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn)

        # Close button
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)
        layout.addWidget(self._close_btn)

        # Connect tab change signal to update button visibility
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(0)  # Initialize for first tab

        return layout

    # ==================== Event Handlers ====================

    def _on_source_type_changed(self) -> None:
        """Handle source type radio button change"""
        use_file = self._file_radio.isChecked()
        self._source_file_edit.setEnabled(use_file)
        self._browse_source_btn.setEnabled(use_file)

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

        # Check if using current scene or file
        use_current_scene = self._current_scene_radio.isChecked()
        source_file: Optional[Path] = None

        if use_current_scene:
            # Validate current scene mode
            self._validation_text.append("✅ Using current Maya scene")
            source_file = None
        else:
            # Validate file mode
            source_file = Path(self._source_file_edit.text())
            if not source_file.exists():
                self._validation_text.append("❌ Source file does not exist")
                return
            self._validation_text.append(f"✅ Source file: {source_file.name}")

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

        # Validate source
        use_current_scene = self._current_scene_radio.isChecked()
        source_file: Optional[Path] = None

        if use_current_scene:
            # Export from current Maya scene - no file path needed
            source_file = None
        else:
            # Export from file
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
        use_current_scene = self._current_scene_radio.isChecked()
        source_path = self._source_file_edit.text().strip()
        output_path = self._output_path_edit.text().strip()

        # Only check source path if using file mode
        if not use_current_scene and not source_path:
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
            export_nurbs_curves=self._include_nurbs_cb.isChecked(),  # NEW: NURBS support!
            nurbs_curves_renderable=self._nurbs_renderable_cb.isChecked(),  # NEW: NURBS renderability control
            export_animation=self._include_animation_cb.isChecked(),
            convert_renderman=self._preview_surface_radio.isChecked()
        )

        return options

    def _create_import_source_section(self) -> QGroupBox:
        """Create import source selection section"""
        group = QGroupBox("USD Source")
        layout = QVBoxLayout(group)

        # USD file selection
        usd_layout = QHBoxLayout()
        usd_layout.addWidget(QLabel("USD File:"))
        self._usd_file_edit = QLineEdit()
        self._usd_file_edit.setPlaceholderText("Select USD file to import...")
        usd_layout.addWidget(self._usd_file_edit)

        self._usd_browse_btn = QPushButton("Browse...")
        self._usd_browse_btn.clicked.connect(self._browse_usd_file)
        usd_layout.addWidget(self._usd_browse_btn)
        layout.addLayout(usd_layout)

        # Namespace
        namespace_layout = QHBoxLayout()
        namespace_layout.addWidget(QLabel("Namespace:"))
        self._namespace_edit = QLineEdit()
        self._namespace_edit.setPlaceholderText("Optional namespace for imported objects")
        namespace_layout.addWidget(self._namespace_edit)
        layout.addLayout(namespace_layout)

        return group

    def _create_import_options_section(self) -> QGroupBox:
        """Create import options section"""
        group = QGroupBox("Import Options")
        layout = QVBoxLayout(group)

        # What to import
        self._import_geometry_cb = QCheckBox("Import Geometry")
        self._import_geometry_cb.setChecked(True)
        layout.addWidget(self._import_geometry_cb)

        self._import_materials_cb = QCheckBox("Import Materials")
        self._import_materials_cb.setChecked(True)
        layout.addWidget(self._import_materials_cb)

        self._import_skeleton_cb = QCheckBox("Import Skeleton & Rigging")
        self._import_skeleton_cb.setChecked(True)
        layout.addWidget(self._import_skeleton_cb)

        self._import_skin_weights_cb = QCheckBox("Apply Skin Weights (Auto-create skinClusters)")
        self._import_skin_weights_cb.setChecked(True)
        self._import_skin_weights_cb.setToolTip("Automatically create Maya skinClusters from USD skeleton data")
        layout.addWidget(self._import_skin_weights_cb)

        self._import_nurbs_cb = QCheckBox("Import NURBS Curves")
        self._import_nurbs_cb.setChecked(True)
        layout.addWidget(self._import_nurbs_cb)

        self._import_connections_cb = QCheckBox("Reconstruct Rig Connections")
        self._import_connections_cb.setChecked(True)
        self._import_connections_cb.setToolTip("Rebuild functional rig connections from USD metadata")
        layout.addWidget(self._import_connections_cb)

        return group

    def _create_import_validation_section(self) -> QGroupBox:
        """Create import validation section"""
        group = QGroupBox("Validation")
        layout = QVBoxLayout(group)

        self._validate_usd_btn = QPushButton("Validate USD File")
        self._validate_usd_btn.clicked.connect(self._validate_usd_file)
        layout.addWidget(self._validate_usd_btn)

        self._usd_info_label = QLabel("Select a USD file to see validation results")
        self._usd_info_label.setWordWrap(True)
        layout.addWidget(self._usd_info_label)

        return group

    def _create_import_progress_section(self) -> QGroupBox:
        """Create import progress section"""
        group = QGroupBox("Import Progress")
        layout = QVBoxLayout(group)

        self._import_progress_bar = QProgressBar()
        self._import_progress_bar.setVisible(False)
        layout.addWidget(self._import_progress_bar)

        self._import_status_label = QLabel("Ready to import")
        layout.addWidget(self._import_status_label)

        return group

    def _browse_usd_file(self) -> None:
        """Browse for USD file to import"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select USD File",
            "",
            "USD Files (*.usd *.usda *.usdc *.usdz);;All Files (*)"
        )
        if file_path:
            self._usd_file_edit.setText(file_path)
            self._validate_usd_file()

    def _validate_usd_file(self) -> None:
        """Validate the selected USD file"""
        usd_path = self._usd_file_edit.text().strip()
        if not usd_path:
            self._usd_info_label.setText("No USD file selected")
            return

        try:
            from pathlib import Path
            path = Path(usd_path)
            if not path.exists():
                self._usd_info_label.setText(f"❌ File does not exist: {usd_path}")
                return

            # Basic validation
            self._usd_info_label.setText(f"✅ USD file found: {path.name}\nValidating contents...")

            # TODO: Add more detailed USD validation

        except Exception as e:
            self._usd_info_label.setText(f"❌ Error validating USD file: {e}")

    def _perform_import(self) -> None:
        """Perform USD import operation"""
        usd_path = self._usd_file_edit.text().strip()
        if not usd_path:
            QMessageBox.warning(self, "Missing Source", "Please select a USD file to import.")
            return

        try:
            from pathlib import Path
            from ...core.interfaces.usd_import_service import UsdImportOptions

            # Build import options
            options = UsdImportOptions(
                import_geometry=self._import_geometry_cb.isChecked(),
                import_materials=self._import_materials_cb.isChecked(),
                import_skeleton=self._import_skeleton_cb.isChecked(),
                apply_skin_weights=self._import_skin_weights_cb.isChecked(),
                import_nurbs_curves=self._import_nurbs_cb.isChecked(),
                import_rig_connections=self._import_connections_cb.isChecked(),
                namespace=self._namespace_edit.text().strip() or None
            )

            # Show progress
            self._import_progress_bar.setVisible(True)
            self._import_status_label.setText("Importing USD file...")
            self._import_progress_bar.setRange(0, 0)  # Indeterminate progress

            # Perform import
            result = self._import_service.import_usd_file(Path(usd_path), options)

            # Hide progress
            self._import_progress_bar.setVisible(False)

            if result.success:
                self._import_status_label.setText("✅ Import completed successfully!")
                QMessageBox.information(self, "Import Complete", "USD file imported successfully!")
            else:
                error_msg = result.error_message or "Unknown error"
                self._import_status_label.setText(f"❌ Import failed: {error_msg}")
                QMessageBox.warning(self, "Import Failed", f"Failed to import USD file:\n{error_msg}")

        except Exception as e:
            self._import_progress_bar.setVisible(False)
            self._import_status_label.setText(f"❌ Import error: {e}")
            QMessageBox.critical(self, "Import Error", f"An error occurred during import:\n{e}")

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change to show appropriate buttons"""
        is_export_tab = index == 0

        # Show/hide buttons based on current tab
        self._validate_btn.setVisible(is_export_tab)
        self._export_btn.setVisible(is_export_tab)
        self._import_btn.setVisible(not is_export_tab)

        # Update default button
        if is_export_tab:
            self._export_btn.setDefault(True)
            self._import_btn.setDefault(False)
        else:
            self._export_btn.setDefault(False)
            self._import_btn.setDefault(True)

    def _restore_geometry(self) -> None:
        """Restore dialog geometry from settings"""
        try:
            from PySide6.QtCore import QSettings

            settings = QSettings("MikeStumbo", "USDPipeline")

            # Restore window geometry (size and position)
            geometry = settings.value("geometry")
            if geometry:
                success = self.restoreGeometry(geometry)
                if success:
                    logger.info(f"✅ USD Pipeline geometry restored: {self.size().width()}x{self.size().height()}")
                else:
                    logger.warning("⚠️ Failed to restore USD Pipeline geometry, using defaults")
            else:
                logger.info("ℹ️ No saved USD Pipeline geometry found, using defaults")

        except Exception as e:
            logger.warning(f"⚠️ Error restoring USD Pipeline geometry: {e}")

    def closeEvent(self, event) -> None:
        """Handle dialog close event - save geometry"""
        try:
            from PySide6.QtCore import QSettings

            settings = QSettings("MikeStumbo", "USDPipeline")
            settings.setValue("geometry", self.saveGeometry())
            logger.info(f"✅ USD Pipeline geometry saved: {self.size().width()}x{self.size().height()}")

        except Exception as e:
            logger.warning(f"⚠️ Error saving USD Pipeline geometry: {e}")

        # Call parent close event
        super().closeEvent(event)
