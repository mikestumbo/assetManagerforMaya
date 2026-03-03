# -*- coding: utf-8 -*-
"""
USD Pipeline Dialog
Main UI for Maya → USD export workflow

Compatibility:
- Maya 2026.3
- MayaUSD 0.34.5
- RenderMan 27

Author: Mike Stumbo
USD Pipeline Dialog - Clean Architecture

Features:
- Uses mayaUSD for native USD export/import
- .rig.mb bundled in USDZ for Maya-specific features
- USD prims in proxy shapes (Disney workflow)
- USD Layers support (geometry, skeleton, materials, animation)
- Progress callback support
- Validation pass before export
- Undo support for imports
"""

from pathlib import Path
from typing import Optional
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QCheckBox, QRadioButton,
    QProgressBar, QTextEdit, QFileDialog, QSpinBox,
    QButtonGroup, QWidget, QMessageBox, QTabWidget, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

# Import our services
from ...core.interfaces.usd_export_service import USDExportOptions
from ...services.usd import USDExportServiceImpl, MayaSceneParserImpl, USDRigConverterImpl
from ...services.usd.usd_material_converter_impl import USDMaterialConverterImpl
from ...services.usd.maya_rig_exporter import MayaRigExporter
from ...services.usd.usdz_packager import UsdzPackager
# Clean Architecture Pipeline
from ...services.usd.usd_pipeline import (
    UsdPipeline, ExportOptions
)

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
        # Clean Architecture Pipeline
        self._pipeline: Optional[UsdPipeline] = None

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

            # Clean Architecture Pipeline
            self._pipeline = UsdPipeline()
            logger.info("[OK] USD Pipeline initialized")

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

        # USD Animation Layers section (Phase 3.3)
        usd_animation_group = self._create_usd_animation_layers_section()
        import_layout.addWidget(usd_animation_group)

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

        # XGen mesh filtering
        self._exclude_xgen_cb = QCheckBox("Exclude XGen/Hair Meshes")
        self._exclude_xgen_cb.setChecked(True)
        self._exclude_xgen_cb.setToolTip(
            "[LOOKDEV] XGen/Hair Mesh Filtering\n\n"
            "Excludes scalp meshes, hair guides, and groom geometry\n"
            "from the USD export.\n\n"
            "These meshes are typically:\n"
            "• Scalp geometry used by XGen\n"
            "• Hair guide curves converted to mesh\n"
            "• Groom/fur placeholder geometry\n\n"
            "Patterns matched: _scalp, _xgen, _hair, _fur, _guide, _groom"
        )
        layout.addWidget(self._exclude_xgen_cb)

        self._include_nurbs_cb = QCheckBox("Include NURBS Curves (Controllers)")
        self._include_nurbs_cb.setChecked(True)
        self._include_nurbs_cb.setToolTip("Export NURBS curves to USD (rig controllers)")
        layout.addWidget(self._include_nurbs_cb)

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

        # Export preset dropdown
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Export Preset:")
        preset_label.setStyleSheet("font-weight: bold;")
        preset_layout.addWidget(preset_label)

        self._export_preset_combo = QComboBox()
        self._export_preset_combo.addItem("Full Rig (Animation)", "full_rig")
        self._export_preset_combo.addItem("Geometry + Materials Only (Texturing)", "geo_materials")
        self._export_preset_combo.setToolTip(
            "Quick presets for common workflows:\n\n"
            "• Full Rig: Export everything for animation\n"
            "• Geometry + Materials: For texture painting in Substance 3D, Mari, etc.\n"
            "  (No skeleton, animation, or controllers - just meshes + UVs + shaders)"
        )
        self._export_preset_combo.currentIndexChanged.connect(self._on_export_preset_changed)
        preset_layout.addWidget(self._export_preset_combo, 1)
        layout.addLayout(preset_layout)

        # Separator
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #555;")
        layout.addWidget(separator)

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
            "• .rig.mb Maya rig file (bundled automatically)\n"
            "• Referenced textures (optional)\n\n"
            "Benefits:\n"
            "• Single-file distribution - no lost files!\n"
            "• Import automatically extracts .rig.mb\n"
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

        # Viewport-friendly skeleton option (default OFF for testing multi-skinCluster fix)
        self._viewport_friendly_cb = QCheckBox("Viewport-friendly skeleton")
        self._viewport_friendly_cb.setChecked(False)
        self._viewport_friendly_cb.setToolTip(
            "[VIEWPORT] Viewport-Friendly Mode (DEFAULT: OFF)\n\n"
            "Exports skeleton hierarchy WITHOUT USD skin bindings.\n\n"
            "[OK] CHECKED:\n"
            "• Meshes visible in USD viewport\n"
            "• Materials and textures display correctly\n"
            "• Full skinning preserved in .rig.mb backup\n"
            "• Import uses Maya proxy joints\n\n"
            "[ERROR] UNCHECKED (default - for USD skin deformation):\n"
            "• Writes jointIndices/jointWeights to USD meshes\n"
            "• Enables native USD skeleton deformation\n"
            "• Auto-fixes multi-skinCluster meshes\n"
            "• Required for 'Extract Full Skin Weights' import option\n"
            "• May cause viewport display issues with complex rigs\n\n"
            "Check this option for viewport compatibility (skips skinning)."
        )
        layout.addWidget(self._viewport_friendly_cb)

        self._include_bind_pose_cb = QCheckBox("Include bind pose")
        self._include_bind_pose_cb.setChecked(True)
        layout.addWidget(self._include_bind_pose_cb)

        # USD Animation Layers (Phase 3.3 - Disney Workflow)
        anim_layers_label = QLabel("USD Animation Layers (Disney Workflow):")
        anim_layers_label.setStyleSheet("font-weight: bold; margin-top: 8px; color: #FF9800;")
        layout.addWidget(anim_layers_label)

        self._export_merge_skeletons_cb = QCheckBox("[SKELETON] Merge Skeletons (unified animation)")
        self._export_merge_skeletons_cb.setChecked(False)
        self._export_merge_skeletons_cb.setToolTip(
            "[SKELETON] Merge Skeletons for USD-Native Animation\n\n"
            "Creates a unified skeleton for direct USD animation:\n"
            "• All 121+ Skeleton prims → 1 UnifiedSkeleton\n"
            "• Enables keyframing skeleton joints directly\n"
            "• Deforming meshes display in viewport\n\n"
            "Uses USD Layers to preserve mesh data:\n"
            "   geometry.usdc - meshes (untouched)\n"
            "   animation.usda - unified skeleton + keyframes\n"
            "   character.usda - root layer"
        )
        self._export_merge_skeletons_cb.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._export_merge_skeletons_cb)

        self._export_usd_layers_cb = QCheckBox("[PACKAGE] Use USD Layers (non-destructive)")
        self._export_usd_layers_cb.setChecked(True)
        self._export_usd_layers_cb.setToolTip(
            "[PACKAGE] USD Layers Export (RECOMMENDED)\n\n"
            "Creates separate layers for clean organization:\n"
            "• geometry.usdc - all meshes (read-only)\n"
            "• animation.usda - keyframes (editable)\n"
            "• character.usda - root composition\n\n"
            "Benefits:\n"
            "• Mesh data never corrupted\n"
            "• Non-destructive animation editing\n"
            "• Team collaboration (different layers)\n"
            "• Swap animations without re-exporting geometry"
        )
        layout.addWidget(self._export_usd_layers_cb)

        # Connect merge skeletons to auto-enable layers
        self._export_merge_skeletons_cb.toggled.connect(
            lambda checked: self._export_usd_layers_cb.setChecked(True) if checked else None
        )

        # Export Rig File (Maya Binary/ASCII)
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

        # Organize in subfolder checkbox
        self._organize_subfolder_cb = QCheckBox("Organize in subfolder (AssetName_USD/)")
        self._organize_subfolder_cb.setChecked(False)
        self._organize_subfolder_cb.setToolTip(
            "Put all export files in an organized subfolder.\n"
            "Example: Veteran_USD/Veteran.usdz, Veteran.usdc, Veteran.rig.mb\n"
            "Keeps your asset directory clean and organized."
        )
        layout.addWidget(self._organize_subfolder_cb)

        # Cleanup intermediate files checkbox
        self._cleanup_intermediates_cb = QCheckBox("Clean up intermediate files")
        self._cleanup_intermediates_cb.setChecked(True)
        self._cleanup_intermediates_cb.setToolTip(
            "Delete .usdc and .rig.mb files after bundling into USDZ.\n"
            "The USDZ package contains everything needed.\n"
            "Uncheck to keep the separate files alongside the USDZ."
        )
        layout.addWidget(self._cleanup_intermediates_cb)

        # Create ZIP archive checkbox
        self._create_zip_cb = QCheckBox("Create ZIP archive")
        self._create_zip_cb.setChecked(False)
        self._create_zip_cb.setToolTip(
            "Create a compressed ZIP archive of all export files.\n"
            "Better compression and protection for asset distribution.\n"
            "Great for sharing or archiving assets."
        )
        layout.addWidget(self._create_zip_cb)

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

    def _on_export_preset_changed(self, index: int) -> None:
        """Handle export preset selection"""
        preset = self._export_preset_combo.itemData(index)

        if preset == "full_rig":
            # Full Rig preset - export everything
            self._include_rigging_cb.setChecked(True)
            self._create_usdskel_cb.setChecked(True)
            self._preserve_weights_cb.setChecked(True)
            self._include_bind_pose_cb.setChecked(True)
            self._export_rig_cb.setChecked(True)
            self._include_animation_cb.setChecked(False)  # Usually off by default

        elif preset == "geo_materials":
            # Geometry + Materials Only preset - for texture painting
            # Perfect for Substance 3D Painter, Mari, etc.
            self._include_rigging_cb.setChecked(False)  # No skeleton/blendshapes
            self._create_usdskel_cb.setChecked(False)
            self._preserve_weights_cb.setChecked(False)
            self._include_bind_pose_cb.setChecked(False)
            self._export_rig_cb.setChecked(False)  # No .rig.mb file
            self._include_animation_cb.setChecked(False)  # No animation
            self._viewport_friendly_cb.setChecked(False)
            # Disable layer-based export (not needed for static geo)
            self._export_merge_skeletons_cb.setChecked(False)
            self._export_usd_layers_cb.setChecked(False)

            # Log preset selection
            print("[LOOKDEV] Export preset: Geometry + Materials Only (for texture painting)")
            print("[INFO] Disabled: Rigging, Animation, Controllers - Pure geo + UVs + shaders")

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
            is_valid, error_msg = self._export_service.validate_export_options(options)

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
        """Start USD export using Clean Architecture Pipeline"""
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

        if not self._pipeline:
            QMessageBox.critical(self, "Service Error", "USD Pipeline is not available.")
            return

        # Start export
        self._is_exporting = True
        self._completion_dialog_shown = False  # Reset for new export
        self._export_btn.setEnabled(False)
        self._validate_btn.setEnabled(False)
        self._browse_source_btn.setEnabled(False)
        self._browse_output_btn.setEnabled(False)

        self._status_label.setText("[START] Starting USD export...")
        self._progress_bar.setValue(0)

        self.export_started.emit()

        # Start progress timer
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start(100)  # Update every 100ms

        # Run export using Clean Architecture pipeline
        try:
            # Build export options
            export_options = ExportOptions(
                output_format="usdz" if options.file_format == "usdz" else "usdc",
                create_rig_mb_backup=self._export_rig_cb.isChecked(),
                cleanup_intermediate_files=self._cleanup_intermediates_cb.isChecked(),
                organize_in_subfolder=self._organize_subfolder_cb.isChecked(),
                create_zip_archive=self._create_zip_cb.isChecked(),
                export_geometry=self._include_geometry_cb.isChecked(),
                export_nurbs_curves=self._include_nurbs_cb.isChecked(),
                export_skeleton=self._include_rigging_cb.isChecked(),
                export_skin_weights=self._include_rigging_cb.isChecked(),
                export_blendshapes=self._include_rigging_cb.isChecked(),
                export_materials=self._include_materials_cb.isChecked(),
                export_renderman=self._include_materials_cb.isChecked(),
                export_animation=False,  # Animation support later
                include_namespaces=True,
                viewport_friendly_skeleton=self._viewport_friendly_cb.isChecked(),
                exclude_xgen_meshes=self._exclude_xgen_cb.isChecked(),
                # USD Animation Layers (Phase 3.3)
                merge_skeletons=self._export_merge_skeletons_cb.isChecked(),
                usd_layers_for_animation=self._export_usd_layers_cb.isChecked(),
            )

            # Set up progress callback
            def progress_callback(stage: str, percent: int) -> None:
                self._progress_bar.setValue(percent)
                self._status_label.setText(f"{stage}")

            self._pipeline.set_progress_callback(progress_callback)

            # Execute export
            self._status_label.setText("[START] Exporting with mayaUSD (maximum conversion)...")
            result = self._pipeline.export(
                source_path=source_file if source_file else Path("current_scene"),
                output_path=options.output_path,
                options=export_options
            )

            self._progress_timer.stop()
            self._is_exporting = False

            if result.success:
                self._progress_bar.setValue(100)

                # Build success message from result
                message_parts = [result.get_summary()]

                self._status_label.setText("[OK] Export complete!")

                # Show completion dialog
                if not self._completion_dialog_shown:
                    self._completion_dialog_shown = True
                    import re
                    clean_msg = "\n".join(message_parts)
                    clean_msg = re.sub(r'[^\x00-\x7F]+', '', clean_msg).strip()
                    if not clean_msg:
                        clean_msg = "Export completed successfully!"
                    self._deferred_message = clean_msg
                    self._deferred_title = "Export Complete"
                    self._deferred_success = True
                    QTimer.singleShot(100, self._show_deferred_dialog)
                self.export_completed.emit(True, "Export successful")
            else:
                error_msg = result.error_message or "Unknown error"
                self._status_label.setText(f"[ERROR] Export failed: {error_msg}")

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
            self._status_label.setText(f"[ERROR] Export error: {e}")

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

    def _on_export_legacy(self) -> None:
        """Legacy export method (v2.0) - kept for reference"""
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

            # Step 2: Export Rig File (Maya Binary/ASCII)
            rig_path: Optional[Path] = None
            rig_success = True
            rig_message = ""

            if success and self._export_rig_cb.isChecked():
                # Determine rig file format
                use_binary = self._rig_mb_radio.isChecked()
                rig_ext = '.rig.mb' if use_binary else '.rig.ma'
                rig_type = 'mayaBinary' if use_binary else 'mayaAscii'

                self._status_label.setText(f"Exporting rig file ({rig_ext})...")
                self._progress_bar.setValue(75)

                # Create rig path (same name as USD, different extension)
                rig_path = options.output_path.with_suffix(rig_ext)

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

                    rig_success, rig_message = rig_exporter.export_rig(
                        output_path=rig_path,
                        skeleton_root=skeleton_root,
                        options=rig_options,
                        progress_callback=rig_progress
                    )

                    if not rig_success:
                        logger.warning(f"Rig export warning: {rig_message}")

                except Exception as e:
                    rig_success = False
                    rig_message = str(e)
                    logger.error(f"Rig export error: {e}")

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
                    # Now package it with rig file
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

                    # Package with rig file (.rig.mb/.rig.ma)
                    pkg_success, pkg_message = packager.create_package(
                        output_path=usdz_path,
                        usd_file=temp_usd_path,
                        mrig_file=None,  # No longer using .mrig
                        rig_file=rig_path if rig_success and rig_path and rig_path.exists() else None
                    )

                    if pkg_success:
                        usdz_packaged = True
                        if rig_path and rig_success:
                            logger.info(f"[PACKAGE] Created USDZ package with rig file: {usdz_path}")
                        else:
                            logger.info(f"[PACKAGE] Created USDZ package: {usdz_path}")

                        # Clean up separate files (they're now in the package)
                        if temp_usd_path.exists():
                            temp_usd_path.unlink()
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
                    if rig_success and rig_path:
                        message_parts = [
                            f"[PACKAGE] USDZ package created:\n{usdz_path}",
                            "\n[OK] Contains USD geometry + .rig.mb in one file!"
                        ]
                    else:
                        message_parts = [
                            f"[PACKAGE] USDZ package created:\n{usdz_path}",
                            "\n[OK] Contains USD geometry in a single portable package."
                        ]
                else:
                    message_parts = [f"USD file exported successfully:\n{options.output_path}"]

                    # Report rig file export status
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
            export_nurbs_curves=False,  # NURBS come from .rig.mb bundled in USDZ
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

        # ============ IMPORT WORKFLOW SELECTION ============
        workflow_label = QLabel("Import Workflow:")
        workflow_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(workflow_label)

        self._import_workflow_group = QButtonGroup(self)

        # Option 1: Look-Dev / Layout (USD Proxy)
        self._lookdev_workflow_radio = QRadioButton("[LOOKDEV] Look-Dev / Layout (USD Proxy)")
        self._lookdev_workflow_radio.setChecked(True)
        self._lookdev_workflow_radio.setToolTip(
            "[LOOKDEV] LOOK-DEV / LAYOUT WORKFLOW\n\n"
            "Creates a mayaUsdProxyShape containing USD data:\n"
            "• Meshes display in viewport (static geometry)\n"
            "• Materials and textures visible\n"
            "• Skeleton hierarchy for reference\n"
            "• Fast loading, non-destructive\n\n"
            "Best for: Lighting, rendering, layout, look development\n"
            "Note: No live deformation (meshes are static poses)"
        )
        self._import_workflow_group.addButton(self._lookdev_workflow_radio, 0)
        layout.addWidget(self._lookdev_workflow_radio)

        # Option 2: USD Animation (Experimental - Keep USD Native)
        self._usd_animation_radio = QRadioButton("[ANIMATION] USD Animation - Experimental [WARNING]")
        self._usd_animation_radio.setToolTip(
            "[ANIMATION] USD ANIMATION (EXPERIMENTAL)\n\n"
            "Pure USD workflow - keeps USD proxy reference:\n"
            "• Preserves USD for pipeline integration\n"
            "• USD Layer system support\n"
            "• Asset Resolver compatible\n"
            "• Non-destructive editing\n\n"
            "[WARNING] KNOWN ISSUES (Maya 2026):\n"
            "• Display bugs with complex skeletons (>100 joints)\n"
            "• Meshes may not deform in viewport\n"
            "• Fixed in mayaUSD v0.25.0+\n\n"
            "Best for: Simple rigs, pipeline testing, future mayaUSD versions"
        )
        self._import_workflow_group.addButton(self._usd_animation_radio, 1)
        layout.addWidget(self._usd_animation_radio)

        # Option 3: Hybrid Animation (Recommended - Convert USD to Maya)
        self._hybrid_workflow_radio = QRadioButton("[HYBRID] Hybrid Animation - Recommended [OK]")
        self._hybrid_workflow_radio.setToolTip(
            "[HYBRID] HYBRID ANIMATION (RECOMMENDED)\n\n"
            "Converts USD to Maya + adds NURBS controllers:\n"
            "• USD meshes → Native Maya meshes\n"
            "• UsdSkel → Maya joints + skinClusters\n"
            "• Materials → RenderMan/Maya shaders\n"
            "• NURBS controllers from .rig.mb\n\n"
            "[OK] ADVANTAGES:\n"
            "• Works with complex skeletons\n"
            "• Full deformation support\n"
            "• All Maya tools available\n"
            "• No viewport bugs\n\n"
            "Best for: Animation production work TODAY"
        )
        self._import_workflow_group.addButton(self._hybrid_workflow_radio, 2)
        layout.addWidget(self._hybrid_workflow_radio)

        # Option 4: Full Maya Rig (.rig.mb only)
        self._animation_workflow_radio = QRadioButton("[PACKAGE] Full Maya Rig (.rig.mb)")
        self._animation_workflow_radio.setToolTip(
            "[PACKAGE] FULL MAYA RIG (FALLBACK)\n\n"
            "Ignores USD, imports .rig.mb backup only:\n"
            "• Complete original Maya rig\n"
            "• All constraints and IK systems\n"
            "• BlendShapes and Set Driven Keys\n"
            "• NURBS controllers\n"
            "• Custom attributes\n\n"
            "Best for: When USD export had issues, or traditional Maya workflow"
        )
        self._import_workflow_group.addButton(self._animation_workflow_radio, 3)
        layout.addWidget(self._animation_workflow_radio)

        # Set Hybrid as default (most reliable)
        self._hybrid_workflow_radio.setChecked(True)

        # Connect workflow change to update options visibility
        self._lookdev_workflow_radio.toggled.connect(self._on_import_workflow_changed)
        self._usd_animation_radio.toggled.connect(self._on_import_workflow_changed)
        self._hybrid_workflow_radio.toggled.connect(self._on_import_workflow_changed)
        self._animation_workflow_radio.toggled.connect(self._on_import_workflow_changed)

        # Namespace
        namespace_layout = QHBoxLayout()
        namespace_layout.addWidget(QLabel("Namespace:"))
        self._namespace_edit = QLineEdit()
        self._namespace_edit.setPlaceholderText("Optional namespace for imported objects")
        namespace_layout.addWidget(self._namespace_edit)
        layout.addLayout(namespace_layout)

        # Advanced: Full weight extraction option
        layout.addWidget(QLabel(""))  # Spacer
        self._extract_full_weights_cb = QCheckBox("🔬 Extract Full Skin Weights from USD")
        self._extract_full_weights_cb.setChecked(False)
        self._extract_full_weights_cb.setToolTip(
            "🔬 Extract Full Skin Weights from USD\n\n"
            "Reads jointIndices/jointWeights primvars from USD meshes.\n\n"
            "[WARNING] REQUIRES: USDZ exported with 'Viewport-friendly skeleton' UNCHECKED\n\n"
            "[OK] CHECKED:\n"
            "• Reads USD skin binding data directly\n"
            "• Creates Maya skinClusters from USD weights\n"
            "• Best for self-contained USDZ pipelines\n\n"
            "[ERROR] UNCHECKED (default):\n"
            "• Uses proxy joint connection (faster)\n"
            "• Animate proxy joints to drive USD skeleton\n"
            "• Works with all USDZ files"
        )
        layout.addWidget(self._extract_full_weights_cb)

        return group

    def _create_usd_animation_layers_section(self) -> QGroupBox:
        """Create USD Animation Layers info section for the Import tab."""
        group = QGroupBox("[ANIMATION] USD Layered Stage (Disney Workflow)")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #FF9800;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #FF9800;
            }
        """)
        layout = QVBoxLayout(group)

        # Info label
        info_label = QLabel(
            "When importing via the Animation workflow, a layered USD stage\n"
            "is built automatically. Each layer is editable independently\n"
            "and the original asset is never modified."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info_label)

        # Layer structure visualization — matches _build_layered_stage output
        structure_label = QLabel(
            "Import Layer Structure:\n"
            "   character.root.usda\n"
            "   ├── animation.usda      (keyframes — strongest)\n"
            "   ├── controllers.usda    (NURBS curves from .rig.mb)\n"
            "   ├── materials.usda      (shader overrides)\n"
            "   ├── skeleton.usda       (joint metadata & mappings)\n"
            "   ├── geometry.usda       (geo overrides)\n"
            "   └── character.usdc      (base asset — read-only)"
        )
        structure_label.setStyleSheet(
            "font-family: monospace; background: #2d2d2d; "
            "padding: 8px; border-radius: 4px; color: #4CAF50;"
        )
        layout.addWidget(structure_label)

        # Rig.mb integration note
        rig_note = QLabel(
            "If the USDZ contains a .rig.mb, NURBS controllers and\n"
            "controller-to-joint mappings are extracted into the\n"
            "controllers and skeleton sublayers automatically."
        )
        rig_note.setWordWrap(True)
        rig_note.setStyleSheet("color: #FF9800; font-size: 11px; margin-top: 8px;")
        layout.addWidget(rig_note)

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

        self._convert_skeleton_to_maya_cb = QCheckBox("Convert USD Skeleton to Maya Joints")
        self._convert_skeleton_to_maya_cb.setChecked(False)
        self._convert_skeleton_to_maya_cb.setToolTip(
            "Extracts UsdSkel as standard Maya joints for direct manipulation.\n\n"
            "Leave unchecked for the Animation workflow \u2014 the USD proxy displays\n"
            "the skeleton via UsdSkelImaging without needing Maya joints.\n\n"
            "Enable only if you need to keyframe joints directly in Maya\n"
            "(e.g. for non-USD animation pipelines)."
        )
        layout.addWidget(self._convert_skeleton_to_maya_cb)

        self._import_skin_weights_cb = QCheckBox("Apply Skin Weights (Auto-create skinClusters)")
        self._import_skin_weights_cb.setChecked(True)
        self._import_skin_weights_cb.setToolTip(
            "Applies USD skin weights as Maya skinClusters (Animation/.rig.mb workflow only).\n\n"
            "Not used in USD Proxy mode \u2014 UsdSkelImaging handles skin deformation\n"
            "natively inside the proxy shape without needing Maya skinClusters."
        )
        layout.addWidget(self._import_skin_weights_cb)

        # Maya Rig Fallback Options (from .rig.mb bundled in USDZ)
        rig_label = QLabel("Rig Data Import (.rig.mb fallback):")
        rig_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(rig_label)

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
            "• Root group containing USD geometry and rig controls\n"
            "• Organized hierarchy: GEO_GRP, CTRL_GRP, SKELETON_GRP\n"
            "• All connections preserved between controls and skeleton\n"
            "• Ready for animation!"
        )
        layout.addWidget(self._create_unified_rig_cb)

        # ── Animation Authoring Method (only visible in USD Animation proxy mode) ──
        authoring_label = QLabel("Animation Authoring Method:")
        authoring_label.setStyleSheet("font-weight: bold; margin-top: 8px;")

        self._edit_as_maya_rb = QRadioButton("Edit As Maya Data  (Option A)")
        self._edit_as_maya_rb.setToolTip(
            "After the USD stage loads, the proxy prims can be duplicated as live\n"
            "Maya joints/meshes via  USD > Edit As Maya Data.\n\n"
            "Use when you need to keyframe joints or apply Maya-native deformers.\n"
            "(You can do this manually from the menu at any time.)"
        )

        self._open_layer_editor_rb = QRadioButton("USD Layer Editor  (Option B)")
        self._open_layer_editor_rb.setChecked(True)
        self._open_layer_editor_rb.setToolTip(
            "After the USD stage loads, opens the mayaUSD Layer Editor so you can\n"
            "author a new animation layer non-destructively on top of the stage.\n\n"
            "This is the Disney/Pixar pipeline approach — edits are stored as a\n"
            "lightweight USD layer and the original asset is never modified."
        )

        self._authoring_method_group = QButtonGroup(self)
        self._authoring_method_group.addButton(self._edit_as_maya_rb)
        self._authoring_method_group.addButton(self._open_layer_editor_rb)

        # Wrap in a container so show/hide doesn't leave orphan label
        self._anim_authoring_container = QWidget()
        authoring_inner = QVBoxLayout(self._anim_authoring_container)
        authoring_inner.setContentsMargins(0, 0, 0, 0)
        authoring_inner.addWidget(authoring_label)
        authoring_inner.addWidget(self._edit_as_maya_rb)
        authoring_inner.addWidget(self._open_layer_editor_rb)

        layout.addWidget(self._anim_authoring_container)
        self._anim_authoring_container.setVisible(False)   # shown only for USD Animation mode

        return group

    def _on_import_workflow_changed(self, is_lookdev: bool) -> None:
        """Handle import workflow selection change"""
        # Look-Dev workflow: USD proxy, minimal Maya options needed
        # Animation workflow: Full Maya rig, all options relevant

        is_animation = not is_lookdev

        # USD-specific options (more relevant for look-dev)
        # These still apply but behave differently
        if hasattr(self, '_import_skin_weights_cb'):
            self._import_skin_weights_cb.setEnabled(is_animation)
            if not is_animation:
                self._import_skin_weights_cb.setChecked(False)
            else:
                self._import_skin_weights_cb.setChecked(True)

        # Rig fallback options (only for animation workflow)
        rig_widgets = [
            '_import_controllers_cb',
            '_import_constraints_cb',
            '_import_space_switches_cb',
            '_import_blendshapes_cb',
            '_import_custom_attrs_cb',
            '_create_unified_rig_cb'
        ]
        for widget_name in rig_widgets:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                widget.setEnabled(is_animation)
                if is_animation:
                    widget.setChecked(True)

        # Update info label
        if hasattr(self, '_usd_info_label'):
            if is_lookdev:
                self._usd_info_label.setText(
                    "[LOOKDEV] Look-Dev Mode: USD will be loaded as proxy shape.\n"
                    "Meshes display as static geometry. Fast and non-destructive."
                )
            else:
                self._usd_info_label.setText(
                    "[ANIMATION] Animation Mode: .rig.mb will be extracted for full Maya rig.\n"
                    "Live skinning, constraints, and controllers available."
                )

        # Show animation authoring method only when USD Animation (proxy) mode is selected
        if hasattr(self, '_anim_authoring_container') and hasattr(self, '_usd_animation_radio'):
            is_usd_proxy = self._usd_animation_radio.isChecked()
            self._anim_authoring_container.setVisible(is_usd_proxy)

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

            # Check if this is a USDZ package that might contain .rig.mb
            usd_path = Path(file_path)
            if usd_path.suffix.lower() == '.usdz':
                try:
                    packager = UsdzPackager()
                    pkg_info = packager.get_package_info(usd_path)

                    if pkg_info.get('has_rig'):
                        self._usd_info_label.setText(
                            self._usd_info_label.text() +
                            "\n[PACKAGE] Package contains .rig.mb Maya rig file!"
                        )
                except Exception as e:
                    logger.debug(f"Could not check USDZ package: {e}")

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
        """Perform USD import using Clean Architecture Pipeline"""
        usd_path = self._usd_file_edit.text().strip()
        if not usd_path:
            QMessageBox.warning(self, "Missing Source", "Please select a USD file to import.")
            return

        if not self._pipeline:
            QMessageBox.warning(self, "Service Error", "USD Pipeline is not available.")
            return

        # Determine workflow mode
        is_lookdev_mode = self._lookdev_workflow_radio.isChecked()
        is_usd_animation_mode = self._usd_animation_radio.isChecked()
        is_hybrid_mode = self._hybrid_workflow_radio.isChecked()
        is_animation_mode = self._animation_workflow_radio.isChecked()

        try:
            # Import import options
            from ...services.usd.usd_pipeline import ImportOptions

            # Show progress
            self._import_progress_bar.setVisible(True)
            self._import_progress_bar.setRange(0, 100)
            self._import_progress_bar.setValue(0)

            if is_lookdev_mode:
                # ============ LOOK-DEV WORKFLOW ============
                # Create USD proxy shape - fast, non-destructive
                self._import_status_label.setText("[LOOKDEV] Look-Dev Mode: Creating USD proxy shape...")

                import_options = ImportOptions(
                    import_geometry=True,
                    import_nurbs_curves=False,  # NURBS in .rig.mb for animation
                    import_skeleton=True,       # Skeleton for reference
                    import_skin_weights=False,  # No skin bindings (viewport-friendly)
                    import_blendshapes=False,   # Blendshapes in .rig.mb
                    import_materials=True,
                    import_constraints=False,
                    use_rig_mb_fallback=False,  # Don't use .rig.mb for look-dev
                    prefer_usd=True,
                    namespace=self._namespace_edit.text().strip() or None,
                    import_animation=False      # Static for look-dev
                )

            elif is_usd_animation_mode:
                # ============ USD ANIMATION (EXPERIMENTAL) ============
                # Keep USD as proxy - for pipeline integration with USD Layers
                self._import_status_label.setText("[ANIMATION] USD Animation: Creating USD stage in Maya...")

                import_options = ImportOptions(
                    import_geometry=True,
                    import_nurbs_curves=False,  # Keep in USD
                    import_skeleton=True,
                    import_skin_weights=False,   # Proxy mode: UsdSkelImaging handles deformation natively
                    import_blendshapes=True,    # USD blendShapes preserved
                    import_materials=True,
                    import_constraints=False,
                    use_rig_mb_fallback=False,  # Pure USD workflow
                    prefer_usd=True,
                    namespace=self._namespace_edit.text().strip() or None,
                    import_animation=False,
                    usd_proxy_mode=True,        # Keep as USD proxy (mayaUSD v0.35.0)
                    convert_skeleton_to_maya=self._convert_skeleton_to_maya_cb.isChecked(),
                    open_layer_editor=self._open_layer_editor_rb.isChecked()
                )

            elif is_hybrid_mode:
                # ============ HYBRID WORKFLOW (RECOMMENDED) ============
                # Convert USD to Maya + import controllers
                self._import_status_label.setText("[HYBRID] Hybrid Mode: Converting USD to Maya + controllers...")

                import_options = ImportOptions(
                    import_geometry=True,
                    import_nurbs_curves=True,   # Import controllers from .rig.mb
                    import_skeleton=True,
                    import_skin_weights=True,   # Convert USD bindings to Maya
                    import_blendshapes=True,
                    import_materials=True,
                    import_constraints=True,    # Import constraints for controllers
                    use_rig_mb_fallback=True,   # Use .rig.mb for controllers
                    prefer_usd=True,            # Prefer USD for meshes
                    namespace=self._namespace_edit.text().strip() or None,
                    import_animation=False,
                    hybrid_mode=True,           # Special flag for hybrid import
                    extract_full_weights=self._extract_full_weights_cb.isChecked()  # Advanced option
                )

            elif is_animation_mode:
                # ============ ANIMATION WORKFLOW ============
                # Extract .rig.mb for full Maya functionality
                self._import_status_label.setText("[ANIMATION] Animation Mode: Extracting full Maya rig...")

                import_options = ImportOptions(
                    import_geometry=self._import_geometry_cb.isChecked(),
                    import_nurbs_curves=True,   # Controllers from .rig.mb
                    import_skeleton=self._import_skeleton_cb.isChecked(),
                    import_skin_weights=self._import_skin_weights_cb.isChecked(),
                    import_blendshapes=self._import_blendshapes_cb.isChecked(),
                    import_materials=self._import_materials_cb.isChecked(),
                    import_constraints=self._import_constraints_cb.isChecked(),
                    use_rig_mb_fallback=True,   # Use .rig.mb for full rig!
                    prefer_usd=False,           # Prefer .rig.mb data for animation
                    namespace=self._namespace_edit.text().strip() or None,
                    import_animation=True
                )

            # Set up progress callback
            def progress_callback(stage: str, percent: int) -> None:
                self._import_progress_bar.setValue(percent)
                self._import_status_label.setText(f"{stage}")

            self._pipeline.set_progress_callback(progress_callback)

            # Execute import
            self._import_status_label.setText("[START] Importing with mayaUSD...")
            result = self._pipeline.import_usd(
                usd_path=Path(usd_path),
                options=import_options
            )

            self._import_progress_bar.setValue(100)
            self._import_progress_bar.setVisible(False)

            if result.success:
                # Build success message
                message = result.get_summary()
                self._import_status_label.setText("[OK] Import complete!")
                QMessageBox.information(self, "Import Complete", message)
            else:
                error_msg = result.error_message or "Unknown error"
                self._import_status_label.setText(f"[ERROR] Import failed: {error_msg}")
                QMessageBox.warning(self, "Import Failed", f"USD import failed:\n{error_msg}")

        except Exception as e:
            self._import_progress_bar.setVisible(False)
            self._import_status_label.setText(f"[ERROR] Import error: {e}")
            QMessageBox.critical(self, "Import Error", f"An error occurred:\n{e}")
            logger.error(f"Import error: {e}")
            import traceback
            traceback.print_exc()

    def _create_unified_rig_structure(self, usd_path: str, rig_path: str) -> bool:
        """
        Create a unified rig structure combining USD geometry and rig controls

        Creates hierarchy:
        - {character}_RIG
          - GEO_GRP (USD geometry)
          - CTRL_GRP (rig controllers)
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
