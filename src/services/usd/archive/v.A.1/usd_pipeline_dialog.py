# -*- coding: utf-8 -*-
"""
USD Pipeline Dialog
Main UI for Maya → USD export workflow

Compatibility:
- Maya 2026.3
- MayaUSD 0.34.5
- RenderMan 27

Author: Mike Stumbo
Version: 1.5.0 - Enhanced .mrig Rig Export/Import

v1.5.0 Features:
- Removed NURBS controls from USD export (use .mrig instead)
- Progress callback support
- Validation pass before export
- Space switch export/import
- Custom attribute preservation
- Proxy attribute handling
- Undo support for imports
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
try:
    from ....core.interfaces.usd_export_service import USDExportOptions
except ImportError:
    try:
        from src.core.interfaces.usd_export_service import USDExportOptions
    except ImportError:
        raise ImportError("Could not import USDExportOptions from core interfaces")

from ..usd_export_service_impl import USDExportServiceImpl
from ..maya_scene_parser_impl import MayaSceneParserImpl
from ..usd_rig_converter_impl import USDRigConverterImpl
from ..usd_material_converter_impl import USDMaterialConverterImpl
from ..maya_rig_exporter import MayaRigExporter
from ..maya_rig_importer import MayaRigImporter
from ..usdz_packager import UsdzPackager

print("=" * 80)
print("[TARGET][TARGET][TARGET] USD_PIPELINE_DIALOG.PY LOADING - VERSION 3 [TARGET][TARGET][TARGET]")
print("=" * 80)

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
        self._completion_dialog_shown = False  # Prevent duplicate dialogs

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
            from src.services.usd_service_impl import UsdService
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
            from src.services.usd.usd_import_service_impl import UsdImportServiceImpl
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
        self._usdz_radio.setToolTip(
            "[PACKAGE] USDZ Package Format\n\n"
            "Creates a single .usdz file containing:\n"
            "• USD geometry and materials\n"
            "• .mrig rig data (bundled automatically)\n"
            "• Referenced textures (optional)\n\n"
            "Benefits:\n"
            "• Single-file distribution - no lost files!\n"
            "• Import automatically extracts .mrig\n"
            "• Industry-standard AR/mobile format\n\n"
            "Best for sharing rigs and archival."
        )
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

        # v2.0: Export Rig File (Maya Binary/ASCII - replaces .mrig)
        rig_export_label = QLabel("Rig Export:")
        rig_export_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(rig_export_label)

        self._export_rig_cb = QCheckBox("Export Rig File")
        self._export_rig_cb.setChecked(True)
        self._export_rig_cb.setToolTip(
            "Export rig data as a Maya file (fast & reliable).\n\n"
            "Creates a Maya file with:\n"
            "• NURBS controllers\n"
            "• Constraints (parent, orient, point, aim)\n"
            "• IK handles\n"
            "• Set Driven Keys\n"
            "• Blendshapes\n"
            "• Custom attributes\n\n"
            "Imports in ~0.3 seconds regardless of rig complexity!"
        )
        self._export_rig_cb.setStyleSheet("font-weight: bold; color: #4CAF50;")
        layout.addWidget(self._export_rig_cb)

        # Rig format selection (Maya Binary vs ASCII)
        rig_format_layout = QHBoxLayout()
        rig_format_layout.addSpacing(20)  # Indent
        self._rig_format_group = QButtonGroup(self)
        self._rig_mb_radio = QRadioButton("Maya Binary (.mb) - Faster")
        self._rig_mb_radio.setChecked(True)
        self._rig_ma_radio = QRadioButton("Maya ASCII (.ma) - Readable")
        self._rig_format_group.addButton(self._rig_mb_radio, 0)
        self._rig_format_group.addButton(self._rig_ma_radio, 1)
        rig_format_layout.addWidget(self._rig_mb_radio)
        rig_format_layout.addWidget(self._rig_ma_radio)
        rig_format_layout.addStretch()
        layout.addLayout(rig_format_layout)

        # Enable/disable format options based on checkbox
        self._export_rig_cb.toggled.connect(self._rig_mb_radio.setEnabled)
        self._export_rig_cb.toggled.connect(self._rig_ma_radio.setEnabled)

        # Legacy .mrig export (optional metadata) - hidden by default
        self._export_mrig_cb = QCheckBox("Also export .mrig metadata (legacy)")
        self._export_mrig_cb.setChecked(False)
        self._export_mrig_cb.setToolTip(
            "Export additional .mrig JSON metadata file.\n"
            "Not required - the Maya rig file contains everything needed.\n"
            "Only enable for backwards compatibility."
        )
        self._export_mrig_cb.setVisible(False)  # Hidden - advanced option
        layout.addWidget(self._export_mrig_cb)

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
            self._validation_text.append("[OK] Using current Maya scene")
            source_file = None
        else:
            # Validate file mode
            source_file = Path(self._source_file_edit.text())
            if not source_file.exists():
                self._validation_text.append("[ERROR] Source file does not exist")
                return
            self._validation_text.append(f"[OK] Source file: {source_file.name}")

        # Validate with export service
        if self._export_service:
            is_valid, error_msg = self._export_service.validate_export_options(options)  # type: ignore

            if is_valid:
                self._validation_text.append("[OK] Export options are valid")

                # Try to parse scene for additional info
                try:
                    scene_data = self._scene_parser.parse_maya_file(source_file)  # type: ignore
                    self._validation_text.append(f"[OK] Meshes found: {len(scene_data.meshes)}")
                    self._validation_text.append(f"[OK] Materials found: {len(scene_data.materials)}")

                    if scene_data.joints:
                        self._validation_text.append(f"[OK] Joints found: {len(scene_data.joints)}")

                    if scene_data.skin_clusters:
                        self._validation_text.append(f"[OK] Skin clusters detected: {len(scene_data.skin_clusters)}")

                    if not scene_data.meshes:
                        self._validation_text.append("[WARNING] Warning: No meshes found in scene")

                except Exception as e:
                    self._validation_text.append(f"[WARNING] Warning: Could not parse scene: {e}")
            else:
                self._validation_text.append(f"[ERROR] Validation failed: {error_msg}")
        else:
            self._validation_text.append("[ERROR] Export service not available")

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
        self._completion_dialog_shown = False  # Reset for new export
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
            # Step 1: Export USD
            success = self._export_service.export_maya_scene(source_file, options)

            # Step 2: Export Rig File (Maya Binary/ASCII) - v2.0 approach
            rig_path: Optional[Path] = None
            rig_success = True
            rig_message = ""
            mrig_path: Optional[Path] = None  # Legacy .mrig (optional)
            mrig_success = True

            if success and self._export_rig_cb.isChecked():
                # Determine rig file format
                use_binary = self._rig_mb_radio.isChecked()
                rig_ext = '.rig.mb' if use_binary else '.rig.ma'
                rig_type = 'mayaBinary' if use_binary else 'mayaAscii'

                self._status_label.setText(f"Exporting rig file ({rig_ext})...")
                self._progress_bar.setValue(75)

                # Create rig path (same name as USD, different extension)
                if options and options.output_path:
                    rig_path = options.output_path.with_suffix(rig_ext)
                else:
                    rig_path = None

                try:
                    # Create rig exporter
                    rig_exporter = MayaRigExporter()

                    # Define progress callback
                    def rig_progress(stage: str, percent: int) -> None:
                        scaled = 75 + int(percent * 0.20)
                        self._progress_bar.setValue(scaled)
                        self._status_label.setText(f"Rig export: {stage}")

                    # Export options
                    rig_options = {
                        'export_controllers': True,
                        'export_constraints': True,
                        'export_space_switches': True,
                        'export_ik_handles': True,
                        'export_blendshapes': True,
                        'export_sdks': True,
                        'export_custom_attrs': True,
                        'export_proxy_attrs': True,
                        'validate_before_export': True,
                        'rig_format': rig_type,  # v2.0: Maya format
                        'rig_path': rig_path,    # v2.0: Output path for rig file
                    }

                    # Find skeleton root
                    skeleton_root = None
                    if self._include_rigging_cb.isChecked():
                        try:
                            import maya.cmds as cmds  # type: ignore
                            joints = cmds.ls(type='joint') or []
                            if joints:
                                for j in joints:
                                    parent = cmds.listRelatives(j, parent=True)
                                    if not parent or cmds.nodeType(parent[0]) != 'joint':
                                        skeleton_root = j
                                        break
                        except Exception:
                            pass

                    if rig_path is not None:
                        rig_success, rig_message = rig_exporter.export_rig(
                            output_path=rig_path,
                            skeleton_root=skeleton_root,
                            options=rig_options,
                            progress_callback=rig_progress
                        )
                    else:
                        rig_success = False
                        rig_message = "Rig output path is None"

                    if not rig_success:
                        logger.warning(f"Rig export warning: {rig_message}")

                except Exception as e:
                    rig_success = False
                    rig_message = str(e)
                    logger.error(f"Rig export error: {e}")

            # Legacy .mrig export (if enabled - hidden option)
            if success and self._export_mrig_cb.isChecked():
                mrig_path = options.output_path.with_suffix('.mrig')
                # The rig exporter already creates .mrig as part of export_rig
                # Just track the path for USDZ packaging
                if not mrig_path.exists():
                    mrig_success = False

            # Step 3: Package into USDZ if format is usdz
            # USDZ packaging is required because we create .usdc first (USD API limitation)
            usdz_packaged = False
            usdz_path: Optional[Path] = None
            if success and options.file_format == "usdz":
                self._status_label.setText("Packaging into USDZ...")
                self._progress_bar.setValue(95)

                try:
                    packager = UsdzPackager()

                    # The export service created .usdc (because USD API can't create .usdz directly)
                    # Now package it with rig file and optional .mrig
                    temp_usd_path = options.output_path.with_suffix('.usdc')

                    # Fallback checks for other possible extensions
                    if not temp_usd_path.exists():
                        if options.output_path.with_suffix('.usda').exists():
                            temp_usd_path = options.output_path.with_suffix('.usda')
                        elif options.output_path.exists() and options.output_path.suffix == '.usdz':
                            # The file might have been created with wrong extension, rename it
                            temp_usd_path = options.output_path.with_suffix('.usdc')
                            options.output_path.rename(temp_usd_path)

                    if not temp_usd_path.exists():
                        logger.error(f"Could not find intermediate USD file for USDZ packaging: {temp_usd_path}")
                        raise FileNotFoundError(f"Intermediate USD file not found: {temp_usd_path}")

                    usdz_path = options.output_path.with_suffix('.usdz')

                    # v2.0: Package with rig file (.mb/.ma) instead of .mrig
                    # The packager will include the rig file in the USDZ
                    if usdz_path is not None:
                        pkg_success, pkg_message = packager.create_package(
                            output_path=usdz_path,
                            usd_file=temp_usd_path,
                            mrig_file=mrig_path if mrig_success and mrig_path and mrig_path.exists() else None,
                            rig_file=rig_path if rig_success and rig_path and rig_path.exists() else None
                        )
                    else:
                        pkg_success = False
                        pkg_message = "USDZ output path is None"

                    if pkg_success:
                        usdz_packaged = True
                        if rig_path and rig_success:
                            logger.info(f"[PACKAGE] Created USDZ package with rig file: {usdz_path}")
                        elif mrig_path and mrig_success:
                            logger.info(f"[PACKAGE] Created USDZ package with .mrig: {usdz_path}")
                        else:
                            logger.info(f"[PACKAGE] Created USDZ package: {usdz_path}")

                        # Clean up separate files (they're now in the package)
                        if temp_usd_path.exists():
                            temp_usd_path.unlink()
                        if mrig_path and mrig_path.exists():
                            mrig_path.unlink()
                        if rig_path and rig_path.exists():
                            rig_path.unlink()
                    else:
                        logger.warning(f"USDZ packaging failed: {pkg_message}")

                except Exception as e:
                    logger.error(f"USDZ packaging error: {e}")

            self._progress_timer.stop()
            self._is_exporting = False

            if success:
                self._progress_bar.setValue(100)

                # Build success message
                if usdz_packaged and usdz_path:
                    if mrig_success and mrig_path:
                        message_parts = [
                            f"[PACKAGE] USDZ package created:\n{usdz_path}",
                            "\n[OK] Contains USD geometry + .mrig rig data in one file!"
                        ]
                    else:
                        message_parts = [
                            f"[PACKAGE] USDZ package created:\n{usdz_path}",
                            "\n[OK] Contains USD geometry in a single portable package."
                        ]
                else:
                    message_parts = [f"USD file exported successfully:\n{options.output_path}"]

                    # v2.0: Report rig file export status
                    if self._export_rig_cb.isChecked():
                        if rig_success and rig_path and rig_path.exists():
                            message_parts.append(f"\nRig file exported to:\n{rig_path}")
                        elif rig_success and rig_path:
                            # rig was bundled into usdz
                            pass
                        else:
                            message_parts.append(f"\nRig export failed: {rig_message}")

                self._status_label.setText("Export complete!")

                # Show completion dialog after a short delay to let Maya stabilize
                if not self._completion_dialog_shown:
                    self._completion_dialog_shown = True
                    # Store message for deferred dialog
                    import re
                    clean_msg = "\n".join(message_parts)
                    clean_msg = re.sub(r'[^\x00-\x7F]+', '', clean_msg).strip()
                    if not clean_msg:
                        clean_msg = "Export completed successfully!"
                    self._deferred_message = clean_msg
                    self._deferred_title = "Export Complete"
                    self._deferred_success = True
                    # Use QTimer to show dialog after event loop settles
                    QTimer.singleShot(100, self._show_deferred_dialog)
                self.export_completed.emit(True, "Export successful")
            else:
                error_msg = self._export_service.get_last_error() or "Unknown error"
                self._status_label.setText(f"Export failed: {error_msg}")

                if not self._completion_dialog_shown:
                    self._completion_dialog_shown = True
                    import re
                    safe_msg = re.sub(r'[^\x00-\x7F]+', '', str(error_msg))
                    self._deferred_message = f"USD export failed:\n{safe_msg}"
                    self._deferred_title = "Export Failed"
                    self._deferred_success = False
                    QTimer.singleShot(100, self._show_deferred_dialog)
                self.export_completed.emit(False, error_msg)

        except Exception as e:
            self._progress_timer.stop()
            self._is_exporting = False
            self._status_label.setText(f"Export error: {e}")

            if not self._completion_dialog_shown:
                self._completion_dialog_shown = True
                import re
                safe_err = re.sub(r'[^\x00-\x7F]+', '', str(e))
                self._deferred_message = f"An error occurred:\n{safe_err}"
                self._deferred_title = "Export Error"
                self._deferred_success = False
                QTimer.singleShot(100, self._show_deferred_dialog)
            self.export_completed.emit(False, str(e))

        finally:
            self._export_btn.setEnabled(True)
            self._validate_btn.setEnabled(True)
            self._browse_source_btn.setEnabled(True)
            self._browse_output_btn.setEnabled(True)

    def _show_deferred_dialog(self) -> None:
        """Show export completion dialog after event loop settles"""
        try:
            title = getattr(self, '_deferred_title', 'Export')
            message = getattr(self, '_deferred_message', 'Operation complete')
            success = getattr(self, '_deferred_success', True)

            # Use static method - simplest and most reliable
            if success:
                QMessageBox.information(self, title, message)
            else:
                QMessageBox.critical(self, title, message)

        except Exception as e:
            # Fallback to print
            print(f"Dialog display error: {e}")
            print(getattr(self, '_deferred_message', 'Export complete'))

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
            export_nurbs_curves=False,  # v1.5.0: Use .mrig format for rig controls
            nurbs_curves_renderable=False,
            export_animation=self._include_animation_cb.isChecked(),
            convert_renderman=self._preview_surface_radio.isChecked()
        )

        return options

    def _create_import_source_section(self) -> QGroupBox:
        """Create import source selection section"""
        group = QGroupBox("Import Sources")
        layout = QVBoxLayout(group)

        # USD file selection
        usd_layout = QHBoxLayout()
        usd_layout.addWidget(QLabel("USD File:"))
        self._usd_file_edit = QLineEdit()
        self._usd_file_edit.setPlaceholderText("Select USD file (geometry, materials, skeleton)...")
        usd_layout.addWidget(self._usd_file_edit)

        self._usd_browse_btn = QPushButton("Browse...")
        self._usd_browse_btn.clicked.connect(self._browse_usd_file)
        usd_layout.addWidget(self._usd_browse_btn)
        layout.addLayout(usd_layout)

        # .mrig file selection (v1.5.0)
        mrig_layout = QHBoxLayout()
        mrig_layout.addWidget(QLabel(".mrig File:"))
        self._mrig_file_edit = QLineEdit()
        self._mrig_file_edit.setPlaceholderText("Optional: Select .mrig file (rig controls, constraints)...")
        mrig_layout.addWidget(self._mrig_file_edit)

        self._mrig_browse_btn = QPushButton("Browse...")
        self._mrig_browse_btn.clicked.connect(self._browse_mrig_file)
        mrig_layout.addWidget(self._mrig_browse_btn)
        layout.addLayout(mrig_layout)

        # Auto-detect .mrig checkbox
        self._auto_detect_mrig_cb = QCheckBox("Auto-detect .mrig file (same name as USD)")
        self._auto_detect_mrig_cb.setChecked(True)
        self._auto_detect_mrig_cb.setToolTip(
            "Automatically look for a .mrig file with the same name as the USD file.\n"
            "Example: character.usda → character.mrig"
        )
        self._auto_detect_mrig_cb.toggled.connect(self._on_auto_detect_toggled)
        layout.addWidget(self._auto_detect_mrig_cb)

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

        # USD Import Options
        usd_label = QLabel("USD Import:")
        usd_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(usd_label)

        self._import_geometry_cb = QCheckBox("Import Geometry")
        self._import_geometry_cb.setChecked(True)
        layout.addWidget(self._import_geometry_cb)

        self._import_materials_cb = QCheckBox("Import Materials")
        self._import_materials_cb.setChecked(True)
        layout.addWidget(self._import_materials_cb)

        self._import_skeleton_cb = QCheckBox("Import Skeleton (UsdSkel)")
        self._import_skeleton_cb.setChecked(True)
        layout.addWidget(self._import_skeleton_cb)

        self._import_skin_weights_cb = QCheckBox("Apply Skin Weights (Auto-create skinClusters)")
        self._import_skin_weights_cb.setChecked(True)
        self._import_skin_weights_cb.setToolTip("Automatically create Maya skinClusters from USD skeleton data")
        layout.addWidget(self._import_skin_weights_cb)

        # .mrig Import Options (v1.5.0)
        mrig_label = QLabel("Rig Data Import (.mrig):")
        mrig_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(mrig_label)

        self._import_controllers_cb = QCheckBox("Import Controllers (NURBS curves)")
        self._import_controllers_cb.setChecked(True)
        layout.addWidget(self._import_controllers_cb)

        self._import_constraints_cb = QCheckBox("Import Constraints")
        self._import_constraints_cb.setChecked(True)
        layout.addWidget(self._import_constraints_cb)

        self._import_space_switches_cb = QCheckBox("Import Space Switches")
        self._import_space_switches_cb.setChecked(True)
        layout.addWidget(self._import_space_switches_cb)

        self._import_blendshapes_cb = QCheckBox("Import Blendshapes & SDKs")
        self._import_blendshapes_cb.setChecked(True)
        layout.addWidget(self._import_blendshapes_cb)

        self._import_custom_attrs_cb = QCheckBox("Import Custom Attributes")
        self._import_custom_attrs_cb.setChecked(True)
        layout.addWidget(self._import_custom_attrs_cb)

        # Unified Rig Option (v1.5.0)
        unified_label = QLabel("Unified Rig:")
        unified_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(unified_label)

        self._create_unified_rig_cb = QCheckBox("Create Unified Rig Group")
        self._create_unified_rig_cb.setChecked(True)
        self._create_unified_rig_cb.setStyleSheet("font-weight: bold; color: #4CAF50;")
        self._create_unified_rig_cb.setToolTip(
            "Creates a unified rig structure:\n"
            "• Root group containing both USD geometry and .mrig controls\n"
            "• Organized hierarchy: GEO_GRP, CTRL_GRP, SKELETON_GRP\n"
            "• All connections preserved between controls and skeleton\n"
            "• Ready for animation!"
        )
        layout.addWidget(self._create_unified_rig_cb)

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

            # Check if this is a USDZ package that might contain .mrig
            usd_path = Path(file_path)
            if usd_path.suffix.lower() == '.usdz':
                try:
                    packager = UsdzPackager()
                    pkg_info = packager.get_package_info(usd_path)

                    if pkg_info.get('has_mrig'):
                        self._usd_info_label.setText(
                            self._usd_info_label.text() +
                            "\n[PACKAGE] Package contains .mrig rig data!"
                        )
                        # Store info for import - the import will extract it
                        self._mrig_file_edit.setText(f"[bundled in {usd_path.name}]")
                        self._mrig_file_edit.setToolTip(
                            "The .mrig file is bundled inside the USDZ package.\n"
                            "It will be automatically extracted during import."
                        )
                except Exception as e:
                    logger.debug(f"Could not check USDZ package: {e}")

            # Auto-detect .mrig file if enabled (for non-bundled files)
            elif self._auto_detect_mrig_cb.isChecked():
                mrig_path = Path(file_path).with_suffix('.mrig')
                if mrig_path.exists():
                    self._mrig_file_edit.setText(str(mrig_path))
                    self._usd_info_label.setText(
                        self._usd_info_label.text() + f"\n[OK] Auto-detected .mrig: {mrig_path.name}"
                    )

    def _browse_mrig_file(self) -> None:
        """Browse for .mrig file to import"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .mrig File",
            "",
            "Rig Data Files (*.mrig);;JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self._mrig_file_edit.setText(file_path)

    def _on_auto_detect_toggled(self, checked: bool) -> None:
        """Handle auto-detect checkbox toggle"""
        self._mrig_file_edit.setEnabled(not checked)
        self._mrig_browse_btn.setEnabled(not checked)

        if checked:
            # Try to auto-detect from current USD path
            usd_path = self._usd_file_edit.text().strip()
            if usd_path:
                mrig_path = Path(usd_path).with_suffix('.mrig')
                if mrig_path.exists():
                    self._mrig_file_edit.setText(str(mrig_path))
                else:
                    self._mrig_file_edit.clear()

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
                self._usd_info_label.setText(f"[ERROR] File does not exist: {usd_path}")
                return

            # Basic validation
            self._usd_info_label.setText(f"[OK] USD file found: {path.name}\nValidating contents...")

            # TODO: Add more detailed USD validation

        except Exception as e:
            self._usd_info_label.setText(f"[ERROR] Error validating USD file: {e}")

    def _perform_import(self) -> None:
        """Perform unified USD + rig file import operation"""
        usd_path = self._usd_file_edit.text().strip()
        if not usd_path:
            QMessageBox.warning(self, "Missing Source", "Please select a USD file to import.")
            return

        try:
            from ....core.interfaces.usd_import_service import UsdImportOptions
            import tempfile

            # Track temp directory for USDZ extraction cleanup
            temp_extract_dir: Optional[Path] = None
            actual_usd_path = Path(usd_path)
            extracted_mrig_path: Optional[Path] = None
            extracted_rig_file: Optional[Path] = None  # v2.0: .rig.mb or .rig.ma
            extracted_controllers_file: Optional[Path] = None  # Legacy: .controllers.mb

            # Step 0: If USDZ package, extract it first
            if actual_usd_path.suffix.lower() == '.usdz':
                self._import_status_label.setText("[PACKAGE] Extracting USDZ package...")

                try:
                    packager = UsdzPackager()
                    temp_extract_dir = Path(tempfile.mkdtemp(prefix="usdz_import_"))

                    success, info = packager.extract_package(
                        actual_usd_path,
                        temp_extract_dir
                    )

                    if success:
                        usd_file = info.get('usd_file')
                        if usd_file:
                            # Use extracted USD file
                            actual_usd_path = Path(usd_file)
                            extracted_mrig_path = info.get('mrig_file')
                            extracted_rig_file = info.get('rig_file')  # v2.0
                            extracted_controllers_file = info.get('controllers_file')  # Legacy

                            if extracted_mrig_path:
                                logger.info(f"[PACKAGE] Extracted .mrig from package: {extracted_mrig_path.name}")
                            if extracted_rig_file:
                                logger.info(f"🎮 v2.0: Found rig file: {extracted_rig_file.name}")
                            elif extracted_controllers_file:
                                logger.info("🎮 Legacy: Found .controllers.mb")
                        else:
                            raise Exception("No USD file found in extracted package")
                    else:
                        raise Exception(info.get('error', 'Unknown extraction error'))

                except Exception as e:
                    logger.error(f"USDZ extraction failed: {e}")
                    QMessageBox.warning(
                        self,
                        "Package Extraction Failed",
                        f"Failed to extract USDZ package:\n{e}"
                    )
                    return

            # v2.0: If rig file exists, skip USD skin weights (rig file has skinned meshes)
            # Also support legacy .controllers.mb
            has_maya_rig_file = extracted_rig_file is not None or extracted_controllers_file is not None
            # v2.0: Skip USD skinning if we have a Maya rig file
            skip_usd_skinning = has_maya_rig_file
            if skip_usd_skinning:
                if extracted_rig_file:
                    logger.info(f"🎮 v2.0: Skipping USD skin weights (will come from {extracted_rig_file.name})")
                else:
                    logger.info("🎮 Legacy: Skipping USD skin weights (will come from .controllers.mb)")

            # Build USD import options
            usd_options = UsdImportOptions(
                import_geometry=self._import_geometry_cb.isChecked(),
                import_materials=self._import_materials_cb.isChecked(),
                import_skeleton=self._import_skeleton_cb.isChecked(),
                # v2.0: Skip USD skinning if Maya rig file will provide it
                apply_skin_weights=self._import_skin_weights_cb.isChecked() and not skip_usd_skinning,
                import_nurbs_curves=False,  # NURBS come from rig file
                import_rig_connections=False,  # Connections come from rig file
                namespace=self._namespace_edit.text().strip() or None
            )

            # Show progress
            self._import_progress_bar.setVisible(True)
            self._import_progress_bar.setRange(0, 100)
            self._import_progress_bar.setValue(0)
            self._import_status_label.setText("Importing USD file...")

            # Step 1: Import USD (use extracted path if from USDZ)
            usd_result = self._import_service.import_usd_file(actual_usd_path, usd_options)

            if not usd_result.success:
                self._import_progress_bar.setVisible(False)
                error_msg = usd_result.error_message or "Unknown error"
                self._import_status_label.setText(f"[ERROR] USD import failed: {error_msg}")
                QMessageBox.warning(self, "Import Failed", f"Failed to import USD file:\n{error_msg}")
                return

            self._import_progress_bar.setValue(50)
            self._import_status_label.setText("[OK] USD imported, checking for rig file...")

            # Get the USD root node for rig import
            usd_root = getattr(usd_result, 'root_node', None)

            # Step 2: Import rig file
            # Priority: 1) v2.0 .rig.mb/.ma, 2) Legacy .mrig + .controllers.mb, 3) Manual, 4) Auto-detect
            mrig_path_str = ""
            mrig_imported = False
            mrig_message = ""

            # v2.0: Use rig file if available
            if extracted_rig_file and extracted_rig_file.exists():
                mrig_path_str = str(extracted_rig_file)
                logger.info(f"🎮 Using rig file from USDZ: {extracted_rig_file.name}")
            # Legacy: Use extracted .mrig from USDZ package
            elif extracted_mrig_path and extracted_mrig_path.exists():
                mrig_path_str = str(extracted_mrig_path)
                logger.info(f"[PACKAGE] Using .mrig extracted from USDZ: {extracted_mrig_path.name}")
            else:
                # Check manual selection (ignore bundled placeholder)
                manual_mrig = self._mrig_file_edit.text().strip()
                if manual_mrig and not manual_mrig.startswith('[bundled'):
                    mrig_path_str = manual_mrig
                # Auto-detect .mrig if enabled
                elif self._auto_detect_mrig_cb.isChecked():
                    auto_mrig = Path(usd_path).with_suffix('.mrig')
                    if auto_mrig.exists():
                        mrig_path_str = str(auto_mrig)

            if mrig_path_str:
                mrig_path = Path(mrig_path_str)
                if mrig_path.exists():
                    self._import_status_label.setText("Importing rig data (.mrig)...")
                    self._import_progress_bar.setValue(60)

                    try:
                        # Create rig importer
                        rig_importer = MayaRigImporter()

                        # Progress callback
                        def mrig_progress(stage: str, percent: int) -> None:
                            scaled = 60 + int(percent * 0.3)  # Scale to 60-90%
                            self._import_progress_bar.setValue(scaled)
                            self._import_status_label.setText(f"Rig import: {stage}")

                        # .mrig import options
                        mrig_options = {
                            'import_controllers': self._import_controllers_cb.isChecked(),
                            'import_constraints': self._import_constraints_cb.isChecked(),
                            'import_space_switches': self._import_space_switches_cb.isChecked(),
                            'import_blendshapes': self._import_blendshapes_cb.isChecked(),
                            'import_sdks': self._import_blendshapes_cb.isChecked(),
                            'import_ik_handles': True,
                            'import_custom_attrs': self._import_custom_attrs_cb.isChecked(),
                            'import_proxy_attrs': self._import_custom_attrs_cb.isChecked(),
                            'enable_undo': True
                        }

                        mrig_imported, mrig_message = rig_importer.import_rig(
                            mrig_path=mrig_path,
                            usd_root=usd_root,
                            options=mrig_options,
                            progress_callback=mrig_progress
                        )

                    except Exception as e:
                        mrig_message = str(e)
                        logger.error(f"Rig import error: {e}")

            # Step 3: Create unified rig structure if requested
            unified_created = False
            if self._create_unified_rig_cb.isChecked() and mrig_imported:
                self._import_status_label.setText("Creating unified rig structure...")
                self._import_progress_bar.setValue(90)

                try:
                    unified_created = self._create_unified_rig_structure(usd_path, mrig_path_str)
                except Exception as e:
                    logger.error(f"Unified rig creation error: {e}")

            # Complete
            self._import_progress_bar.setValue(100)
            self._import_progress_bar.setVisible(False)

            # Build result message
            message_parts = ["[OK] USD file imported successfully!"]

            if mrig_path_str:
                if mrig_imported:
                    message_parts.append("\n[OK] Rig data (.mrig) imported!")
                    # v1.5.0: Show health report summary
                    if 'rig_importer' in dir() and hasattr(rig_importer, 'get_health_report'):
                        health = rig_importer.get_health_report()
                        if health:
                            message_parts.append(f"\n{health.get_summary()}")
                            if health.warnings:
                                message_parts.append(f"\n[WARNING] {len(health.warnings)} warnings")
                            if health.auto_repairs:
                                message_parts.append(f"\n[TOOL] {len(health.auto_repairs)} auto-repairs")
                else:
                    message_parts.append(f"\n[WARNING] Rig import issue: {mrig_message}")

            if unified_created:
                message_parts.append("\n[OK] Unified rig structure created!")
                message_parts.append("\n\n🎬 Your rig is ready for animation!")

            self._import_status_label.setText("\n".join(message_parts))
            QMessageBox.information(self, "Import Complete", "\n".join(message_parts))

        except Exception as e:
            self._import_progress_bar.setVisible(False)
            self._import_status_label.setText(f"[ERROR] Import error: {e}")
            QMessageBox.critical(self, "Import Error", f"An error occurred during import:\n{e}")

        finally:
            # Cleanup temp extraction directory if we created one
            if temp_extract_dir and temp_extract_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                    logger.debug(f"Cleaned up temp extract dir: {temp_extract_dir}")
                except Exception as cleanup_err:
                    logger.warning(f"Could not clean up temp dir: {cleanup_err}")

    def _create_unified_rig_structure(self, usd_path: str, mrig_path: str) -> bool:
        """
        Create a unified rig structure combining USD geometry and .mrig controls

        Creates hierarchy:
        - {character}_RIG
          - GEO_GRP (USD geometry)
          - CTRL_GRP (.mrig controllers)
          - SKELETON_GRP (joints from USD)
        """
        try:
            import maya.cmds as cmds  # type: ignore

            # Derive rig name from file
            rig_name = Path(usd_path).stem

            # Create main rig group
            rig_grp = cmds.group(empty=True, name=f"{rig_name}_RIG")

            # Create sub-groups
            geo_grp = cmds.group(empty=True, name="GEO_GRP", parent=rig_grp)
            ctrl_grp = cmds.group(empty=True, name="CTRL_GRP", parent=rig_grp)
            skel_grp = cmds.group(empty=True, name="SKELETON_GRP", parent=rig_grp)

            # Find and organize imported nodes
            # Look for geometry (meshes)
            meshes = cmds.ls(type='mesh', long=True) or []
            for mesh in meshes:
                transform = cmds.listRelatives(mesh, parent=True, fullPath=True)
                if transform:
                    # Only parent top-level transforms
                    parent = cmds.listRelatives(transform[0], parent=True)
                    if not parent or parent[0] not in [geo_grp, ctrl_grp, skel_grp, rig_grp]:
                        try:
                            cmds.parent(transform[0], geo_grp)
                        except Exception:
                            pass  # May already be parented

            # Look for NURBS curves (controllers)
            curves = cmds.ls(type='nurbsCurve', long=True) or []
            for curve in curves:
                transform = cmds.listRelatives(curve, parent=True, fullPath=True)
                if transform:
                    parent = cmds.listRelatives(transform[0], parent=True)
                    if not parent or parent[0] not in [geo_grp, ctrl_grp, skel_grp, rig_grp]:
                        try:
                            cmds.parent(transform[0], ctrl_grp)
                        except Exception:
                            pass

            # Look for root joints
            joints = cmds.ls(type='joint') or []
            root_joints = []
            for joint in joints:
                parent = cmds.listRelatives(joint, parent=True, type='joint')
                if not parent:  # No joint parent = root joint
                    root_joints.append(joint)

            for root_joint in root_joints:
                parent = cmds.listRelatives(root_joint, parent=True)
                if not parent or parent[0] not in [geo_grp, ctrl_grp, skel_grp, rig_grp]:
                    try:
                        cmds.parent(root_joint, skel_grp)
                    except Exception:
                        pass

            # Lock and hide groups' transforms
            for grp in [geo_grp, ctrl_grp, skel_grp]:
                for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz']:
                    cmds.setAttr(f"{grp}.{attr}", lock=True, keyable=False)

            logger.info(f"[OK] Created unified rig structure: {rig_grp}")
            return True

        except Exception as e:
            # Non-critical - rig was imported successfully, just couldn't organize into groups
            logger.warning(f"Unified rig structure skipped: {e}")
            return False

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
                    logger.info(f"[OK] USD Pipeline geometry restored: {self.size().width()}x{self.size().height()}")
                else:
                    logger.warning("[WARNING] Failed to restore USD Pipeline geometry, using defaults")
            else:
                logger.info("[INFO] No saved USD Pipeline geometry found, using defaults")

        except Exception as e:
            logger.warning(f"[WARNING] Error restoring USD Pipeline geometry: {e}")

    def closeEvent(self, event) -> None:
        """Handle dialog close event - save geometry"""
        try:
            from PySide6.QtCore import QSettings

            settings = QSettings("MikeStumbo", "USDPipeline")
            settings.setValue("geometry", self.saveGeometry())
            logger.info(f"[OK] USD Pipeline geometry saved: {self.size().width()}x{self.size().height()}")

        except Exception as e:
            logger.warning(f"[WARNING] Error saving USD Pipeline geometry: {e}")

        # Call parent close event
        super().closeEvent(event)
