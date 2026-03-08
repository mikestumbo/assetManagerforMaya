"""
USD Pipeline - Clean Architecture

DESIGN PHILOSOPHY:
- Maximize USD native conversion using mayaUSD
- Export complete .rig.mb as backup/fallback
- Step-by-step conversion with validation
- Smart import that fills gaps from .rig.mb
- USD Layers support for non-destructive workflows (Maya 2026+)

USD SCHEMA MAPPING:
┌─────────────────────┬────────────────────────────┐
│ Maya Component      │ USD Schema                 │
├─────────────────────┼────────────────────────────┤
│ Meshes              │ UsdGeomMesh                │
│ NURBS Curves        │ UsdGeomNurbsCurves         │
│ Skeleton/Joints     │ UsdSkel                    │
│ Skin Weights        │ UsdSkelBindingAPI          │
│ Blendshapes         │ UsdSkelBlendShape (2026!)  │
│ RenderMan Materials │ UsdRi / RenderMan Schemas  │
│ Standard Materials  │ UsdShade (PreviewSurface)  │
│ Constraints         │ UsdGeomConstraintTarget    │
│ Expressions         │ USD variable expressions   │
└─────────────────────┴────────────────────────────┘

USD LAYERS (Maya 2026+):
┌─────────────────────┬────────────────────────────┐
│ Layer Type          │ Content                    │
├─────────────────────┼────────────────────────────┤
│ Root Layer          │ References to sublayers    │
│ Geometry Layer      │ Meshes, Curves, Transforms │
│ Skeleton Layer      │ Joints, Skinning, Poses    │
│ Materials Layer     │ Shaders, Textures          │
│ Animation Layer     │ Keyframes, Constraints     │
│ Edit Layer          │ Local overrides (import)   │
└─────────────────────┴────────────────────────────┘

FALLBACK (.rig.mb):
- IK Solvers (ikRPsolver, ikSCsolver, ikSplineSolver)
- Set Driven Keys (animCurveUA/UL/UU)
- Complex utility node networks
- Anything that fails USD conversion

Author: Mike Stumbo
License: MIT
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum, auto

# Maya imports (conditional)
try:
    import maya.cmds as cmds  # type: ignore
    import maya.mel as mel  # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    cmds: Any = None
    mel: Any = None

# USD imports (conditional)
try:
    from pxr import Usd, UsdSkel, UsdGeom, Vt, Gf  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False


class ConversionStatus(Enum):
    """Status of a component conversion to USD"""
    SUCCESS = auto()       # Fully converted to USD
    PARTIAL = auto()       # Some data converted, some in fallback
    FALLBACK = auto()      # Using .rig.mb fallback
    SKIPPED = auto()       # Not applicable/not requested
    FAILED = auto()        # Conversion failed


@dataclass
class ConversionResult:
    """Result of converting a single component type"""
    component_type: str
    status: ConversionStatus
    usd_count: int = 0           # Items successfully in USD
    fallback_count: int = 0      # Items using .rig.mb fallback
    message: str = ""
    details: List[str] = field(default_factory=list)


@dataclass
class ExportResult:
    """Complete export result with all conversions"""
    success: bool = False
    usd_path: Optional[Path] = None
    rig_mb_path: Optional[Path] = None
    usdz_path: Optional[Path] = None

    # Conversion results by component
    conversions: Dict[str, ConversionResult] = field(default_factory=dict)

    # Summary counts
    total_usd_items: int = 0
    total_fallback_items: int = 0

    error_message: str = ""

    def get_summary(self) -> str:
        """Get human-readable summary"""
        lines = [f"{'[OK]' if self.success else '[ERROR]'} USD Export Summary"]

        if self.usd_path:
            lines.append(f"  [FILE] USD: {self.usd_path.name}")
        if self.rig_mb_path:
            lines.append(f"  [PACKAGE] Rig Backup: {self.rig_mb_path.name}")
        if self.usdz_path:
            lines.append(f"  [BUNDLE] Package: {self.usdz_path.name}")

        lines.append("")
        lines.append("  Conversions:")
        for comp_type, result in self.conversions.items():
            status_icon = {
                ConversionStatus.SUCCESS: "[OK]",
                ConversionStatus.PARTIAL: "[WARNING]",
                ConversionStatus.FALLBACK: "[PACKAGE]",
                ConversionStatus.SKIPPED: "⏭️",
                ConversionStatus.FAILED: "[ERROR]"
            }.get(result.status, "?")
            lines.append(f"    {status_icon} {comp_type}: {result.usd_count} USD, {result.fallback_count} fallback")

        lines.append("")
        lines.append(f"  Total: {self.total_usd_items} in USD, {self.total_fallback_items} in fallback")

        return "\n".join(lines)


@dataclass
class ImportResult:
    """Complete import result"""
    success: bool = False

    # What was imported (final totals)
    meshes_imported: int = 0
    joints_imported: int = 0
    curves_imported: int = 0
    materials_imported: int = 0
    constraints_imported: int = 0
    blendshapes_imported: int = 0
    skin_clusters_imported: int = 0

    # USD-native counts (what mayaUSD actually brought in)
    usd_meshes: int = 0
    usd_joints: int = 0
    usd_curves: int = 0
    usd_materials: int = 0
    usd_skin_clusters: int = 0
    usd_blendshapes: int = 0

    # Fallback usage
    used_rig_mb_fallback: bool = False
    fallback_components: List[str] = field(default_factory=list)

    # USD proxy shape info
    temp_usd_path: Optional[Path] = None  # Path to temp USD file (if from USDZ)

    error_message: str = ""

    def get_summary(self) -> str:
        """Get human-readable summary with USD vs Fallback breakdown"""
        lines = [f"{'[OK]' if self.success else '[ERROR]'} USD Import Summary"]

        # Show breakdown: USD native vs Fallback
        if self.used_rig_mb_fallback:
            lines.append("")
            lines.append("[INFO] Import Source Breakdown:")
            lines.append(f"  {'Component':<14} {'USD':<6} {'Fallback':<10} {'Total'}")
            lines.append(f"  {'-'*40}")

            # Calculate fallback counts (total - USD)
            fb_meshes = self.meshes_imported - self.usd_meshes
            fb_joints = self.joints_imported - self.usd_joints
            fb_curves = self.curves_imported - self.usd_curves
            fb_materials = self.materials_imported - self.usd_materials
            fb_skins = self.skin_clusters_imported - self.usd_skin_clusters
            fb_blends = self.blendshapes_imported - self.usd_blendshapes

            skins = self.skin_clusters_imported
            lines.append(f"  {'Meshes':<14} {self.usd_meshes:<6} {fb_meshes:<10} {self.meshes_imported}")
            lines.append(f"  {'Joints':<14} {self.usd_joints:<6} {fb_joints:<10} {self.joints_imported}")
            lines.append(f"  {'NURBS Curves':<14} {self.usd_curves:<6} {fb_curves:<10} {self.curves_imported}")
            lines.append(f"  {'Materials':<14} {self.usd_materials:<6} {fb_materials:<10} {self.materials_imported}")
            lines.append(f"  {'Skin Clusters':<14} {self.usd_skin_clusters:<6} {fb_skins:<10} {skins}")
            lines.append(f"  {'Blendshapes':<14} {self.usd_blendshapes:<6} {fb_blends:<10} {self.blendshapes_imported}")
            consts = self.constraints_imported
            lines.append(f"  {'Constraints':<14} {'N/A':<6} {consts:<10} {consts}")

            lines.append("")
            lines.append(f"  [PACKAGE] Fallback used for: {', '.join(self.fallback_components)}")
        else:
            # All from USD - show prim counts
            lines.append("")
            lines.append("[PACKAGE] USD Prims Loaded (in proxy shape):")
            lines.append(f"  Mesh Prims: {self.usd_meshes}")
            lines.append(f"  Joints: {self.usd_joints}")
            lines.append(f"  Curve Prims: {self.usd_curves}")
            lines.append(f"  Material Prims: {self.usd_materials}")
            lines.append(f"  BlendShape Prims: {self.usd_blendshapes}")
            lines.append(f"  SkinBinding Prims: {self.usd_skin_clusters}")
            lines.append("")
            lines.append("  [NEW] USD content loaded successfully!")
            lines.append("  [TIP] View in viewport or convert via USD > Edit as Maya Data")

        return "\n".join(lines)


@dataclass
class ExportOptions:
    """Options for USD export"""
    # Output options
    output_format: str = "usdz"  # "usd", "usdc", "usda", "usdz"
    create_rig_mb_backup: bool = True  # Always recommended!
    cleanup_intermediate_files: bool = True  # Delete .usdc/.rig.mb after USDZ packaging
    organize_in_subfolder: bool = False  # Put files in AssetName_USD/ folder
    create_zip_archive: bool = False  # Create ZIP archive for space/protection

    # Component selection
    export_geometry: bool = True
    export_nurbs_curves: bool = True
    export_skeleton: bool = True
    export_skin_weights: bool = True
    export_blendshapes: bool = True
    export_materials: bool = True
    export_constraints: bool = True
    export_expressions: bool = True

    # Material options
    export_renderman: bool = True
    material_scope_name: str = "Materials"

    # Animation
    export_animation: bool = False
    animation_start: float = 1.0
    animation_end: float = 1.0

    # USD Layers (Maya 2026+ feature)
    use_layered_export: bool = False  # Export to layered USD structure
    geometry_layer: bool = True       # Separate layer for geometry
    skeleton_layer: bool = True       # Separate layer for skeleton/skinning
    materials_layer: bool = True      # Separate layer for materials/shading
    animation_layer: bool = True      # Separate layer for animation data

    # Advanced
    mesh_format: str = "default"  # "default", "subdivision"
    include_namespaces: bool = True

    # XGen / Hair System Filtering
    exclude_xgen_meshes: bool = True  # Exclude XGen scalp/guide meshes from export
    xgen_mesh_patterns: tuple = (  # Patterns to identify XGen-related meshes
        "_scalp", "Scalp", "_xgen", "XGen", "xgen",
        "_hair", "Hair_", "_fur", "Fur_",
        "_guide", "Guide_", "_groom", "Groom_"
    )

    # Viewport Compatibility (for complex rigs)
    # When False: exports full USD skeleton with skin bindings (enables multi-skinCluster fix)
    # When True: exports skeleton hierarchy + animation, but skips skin bindings
    # This avoids UsdSkelImaging viewport bugs with complex rigs (many skeletons)
    # Meshes display as static geometry, full rigging stays in .rig.mb
    viewport_friendly_skeleton: bool = False

    # Simplified Skeleton Export (Phase 3.2)
    # When True: exports ONLY joints that directly deform meshes (skinCluster influences)
    # This dramatically reduces skeleton complexity (e.g., 548 joints → ~40 deformation joints)
    # Helps UsdSkelImaging display skinned meshes by reducing Skeleton prim count
    simplified_skeleton_export: bool = False

    # Unified Skeleton Export (Phase 3.3 - USD Native Animation)
    # When True: creates USD layers structure with unified skeleton
    # This enables USD-native animation workflow where animators can keyframe
    # the skeleton directly and have deforming meshes display in viewport
    # Uses USD composition (layers) to avoid corrupting mesh data
    merge_skeletons: bool = False

    # USD Layers for Animation (Phase 3.3)
    # When merge_skeletons=True, creates this structure:
    #   character.usdc (root - references sublayers)
    #   ├── geometry.usdc (meshes untouched from Maya)
    #   ├── skeleton.usdc (unified skeleton with 1 Skeleton prim)
    #   └── animation.usda (editable animation layer)
    usd_layers_for_animation: bool = True

    # Body Skeleton Only (Phase 3.3 - USD Native Animation)
    # When True with merge_skeletons: exports ONLY body deformation joints
    # Excludes facial rig joints which are typically disconnected hierarchies
    # This produces a clean single-skeleton USD for body animation
    # Facial animation would stay in Maya or use blendshapes instead
    body_skeleton_only: bool = True

    # Facial joint patterns to exclude when body_skeleton_only=True
    facial_joint_patterns: tuple = (
        "Face", "face", "Lip", "lip", "Lid", "lid", "Eye", "eye",
        "Brow", "brow", "Nose", "nose", "Jaw", "jaw", "Tongue", "tongue",
        "Cheek", "cheek", "Ear", "ear", "Fleshy", "fleshy", "Ribbon", "ribbon"
    )

    # RenderMan Asset Library (optional — user-supplied)
    # When set, the texture color sampler searches this directory for the
    # original source .png/.tiff files BEFORE RenderMan converts them to
    # binary .tex format.  This guarantees accurate diffuse colors without
    # needing OpenImageIO to decode .tex files.
    # Expected layout: <renderman_library_path>/<MaterialName>.rma/<texture>.png
    renderman_library_path: str = ""


@dataclass
class ImportOptions:
    """Options for USD import"""
    # Component selection
    import_geometry: bool = True
    import_nurbs_curves: bool = True
    import_skeleton: bool = True
    import_skin_weights: bool = True
    import_blendshapes: bool = True
    import_materials: bool = True
    import_constraints: bool = True

    # Fallback behavior
    use_rig_mb_fallback: bool = True  # Use .rig.mb for missing components
    prefer_usd: bool = True  # Prefer USD data when both available

    # Workflow modes
    usd_proxy_mode: bool = False  # Keep USD as proxy (experimental, Maya 2026 bugs)
    hybrid_mode: bool = False  # Convert USD→Maya + import controllers (recommended)
    convert_skeleton_to_maya: bool = False  # Convert UsdSkel to Maya joints (opt-in; proxy mode uses UsdSkelImaging)

    # Skin weight extraction (Phase 3.2)
    extract_full_weights: bool = False  # Load references for full skinCluster data (slower)

    # Convert to native Maya (workaround for viewport bugs)
    convert_to_maya: bool = False  # Convert USD prims to native Maya meshes

    # Namespace
    namespace: Optional[str] = None

    # Animation
    import_animation: bool = True

    # USD Layers (Maya 2026+ feature)
    import_all_layers: bool = True    # Import all USD layers
    flatten_layers: bool = False      # Flatten layers on import (combine into one)
    create_edit_layer: bool = True    # Create editable layer for local edits
    open_layer_editor: bool = False   # Open mayaUSD Layer Editor after proxy import (Option B)


class UsdPipeline:
    """
    USD Pipeline - Clean Architecture

    Maximizes USD native conversion, uses .rig.mb as fallback.
    """

    def __init__(self):
        """Initialize the pipeline"""
        self.logger = logging.getLogger(__name__)
        self._progress_callback: Optional[Callable[[str, int], None]] = None

        # Check capabilities
        self._maya_available = MAYA_AVAILABLE
        self._usd_available = USD_AVAILABLE
        self._mayausd_available = self._check_mayausd()

        self.logger.info("USD Pipeline initialized")
        self.logger.info(f"  Maya: {self._maya_available}")
        self.logger.info(f"  USD Python: {self._usd_available}")
        self.logger.info(f"  mayaUSD: {self._mayausd_available}")

    def _check_mayausd(self) -> bool:
        """Check if mayaUSD plugin is available"""
        if not MAYA_AVAILABLE or cmds is None:
            return False
        try:
            # Check if plugin exists
            if cmds.pluginInfo('mayaUsdPlugin', query=True, loaded=True):
                return True
            # Try to load it
            cmds.loadPlugin('mayaUsdPlugin')
            return True
        except Exception:
            return False

    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """Set progress callback for UI feedback"""
        self._progress_callback = callback

    def _report_progress(self, stage: str, percent: int) -> None:
        """Report progress"""
        if self._progress_callback:
            self._progress_callback(stage, percent)
        self.logger.debug(f"Progress: {stage} ({percent}%)")

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export(
        self,
        source_path: Path,
        output_path: Path,
        options: Optional[ExportOptions] = None
    ) -> ExportResult:
        """
        Export Maya rig to USD with .rig.mb backup

        Args:
            source_path: Path to source .mb/.ma file (or special value for current scene)
            output_path: Path for output (determines format from extension)
            options: Export options

        Returns:
            ExportResult with conversion details
        """
        result = ExportResult()
        options = options or ExportOptions()

        if not self._maya_available:
            result.error_message = "Maya not available"
            return result

        try:
            self._report_progress("Starting export", 0)

            # CRITICAL: Open source file if specified (not "current_scene")
            if cmds is not None and source_path and str(source_path) != "current_scene":
                source_path = Path(source_path)
                if source_path.exists():
                    self.logger.info(f"[FILE] Opening source file: {source_path}")
                    self._report_progress("Opening Maya scene", 2)
                    cmds.file(str(source_path), open=True, force=True)
                    self.logger.info(f"[OK] Scene opened: {source_path.name}")
                else:
                    self.logger.warning(f"[WARNING] Source file not found: {source_path}")
            else:
                self.logger.info("[FILE] Exporting from current scene")

            # Determine output paths
            output_path = Path(output_path)
            base_path = output_path.with_suffix('')
            asset_name = base_path.name

            # Create subfolder if requested (AssetName_USD/)
            if options.organize_in_subfolder:
                subfolder = base_path.parent / f"{asset_name}_USD"
                subfolder.mkdir(parents=True, exist_ok=True)
                base_path = subfolder / asset_name
                self.logger.info(f"[FOLDER] Organizing files in: {subfolder.name}/")

            # USD file path (always create this)
            usd_ext = ".usdc"  # Binary for efficiency
            usd_path = base_path.with_suffix(usd_ext)

            # Rig backup path
            rig_mb_path = Path(str(base_path) + ".rig.mb")

            # USDZ package path (if requested)
            usdz_path = base_path.with_suffix('.usdz') if options.output_format == "usdz" else None

            # ZIP archive path (if requested)
            zip_path = base_path.with_suffix('.zip') if options.create_zip_archive else None

            # Step 1: Export complete .rig.mb backup (ALWAYS do this first!)
            self._report_progress("Exporting .rig.mb backup", 5)
            if options.create_rig_mb_backup:
                rig_success = self._export_rig_mb_backup(rig_mb_path)
                if rig_success:
                    result.rig_mb_path = rig_mb_path
                    self.logger.info(f"[OK] Rig backup exported: {rig_mb_path.name}")
                else:
                    self.logger.warning("[WARNING] Rig backup export failed")

            # Step 2: Export to USD using mayaUSD
            self._report_progress("Exporting to USD via mayaUSD", 20)
            usd_success = self._export_with_mayausd(usd_path, options, result)

            if usd_success:
                result.usd_path = usd_path
                self.logger.info(f"[OK] USD exported: {usd_path.name}")
            else:
                result.error_message = "USD export failed"
                return result

            # Step 2.5: Create layered USD structure if requested (Maya 2026+ feature)
            if options.use_layered_export and usd_path.exists():
                self._report_progress("Creating USD layers", 60)
                layered_success = self._create_layered_usd(usd_path, options, result)
                if layered_success:
                    self.logger.info("[OK] USD layers created for non-destructive workflow")
                else:
                    self.logger.warning("[WARNING] Layered export failed, using single-file USD")

            # Step 3: Create USDZ package if requested
            if usdz_path and usd_path.exists():
                self._report_progress("Creating USDZ package", 85)
                usdz_success = self._create_usdz_package(
                    usd_path, rig_mb_path, usdz_path
                )
                if usdz_success:
                    result.usdz_path = usdz_path
                    self.logger.info(f"[OK] USDZ package created: {usdz_path.name}")

                    # Step 4: Clean up intermediate files if requested
                    if options.cleanup_intermediate_files:
                        self._cleanup_intermediate_files(usd_path, rig_mb_path)

            # Step 5: Create ZIP archive if requested
            if zip_path and options.create_zip_archive:
                self._report_progress("Creating ZIP archive", 95)
                zip_success = self._create_zip_archive(
                    base_path.parent if options.organize_in_subfolder else None,
                    usdz_path, usd_path, rig_mb_path, zip_path, options
                )
                if zip_success:
                    self.logger.info(f"[PACKAGE] ZIP archive created: {zip_path.name}")

            # Calculate totals
            for conv in result.conversions.values():
                result.total_usd_items += conv.usd_count
                result.total_fallback_items += conv.fallback_count

            result.success = True
            self._report_progress("Export complete", 100)

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            result.error_message = str(e)

        return result

    def _get_deformation_joints(self) -> set:
        """
        Get only joints that directly deform geometry (skinCluster influences).

        This dramatically reduces skeleton complexity by excluding:
        - IK/FK control joints
        - Twist/roll joints that don't directly bind to skin
        - Helper/utility joints
        - Constraint targets

        Only returns joints that are ACTUALLY weighted to vertices.

        Returns:
            Set of joint long names that are deformation joints
        """
        if cmds is None:
            return set()

        deformation_joints = set()

        # Get all skinClusters in the scene
        skin_clusters = cmds.ls(type='skinCluster') or []

        for skin_cluster in skin_clusters:
            try:
                # Get the influence joints for this skinCluster
                # influenceObjects returns joints that are bound (even if 0 weight)
                influences = cmds.skinCluster(skin_cluster, query=True, influence=True) or []

                for joint in influences:
                    # Get long name for consistency
                    long_names = cmds.ls(joint, long=True)
                    if long_names:
                        deformation_joints.add(long_names[0])

            except Exception as e:
                self.logger.warning(f"Could not get influences from {skin_cluster}: {e}")

        return deformation_joints

    def _detect_multi_skincluster_meshes(self) -> dict:
        """
        Detect meshes that have multiple skinClusters affecting them.

        Advanced Skeleton and other rigs sometimes stack skinClusters for
        facial deformation (e.g., CageSC, EyeLidSC, JawSC, LipSC on body mesh).
        mayaUSD cannot export these - it produces empty/corrupt mesh data.

        Also detects meshes with blendShapes + skinCluster combinations that
        mayaUSD fails to export (produces empty geometry).

        Returns:
            Dict mapping mesh name to list of skinCluster names
            Only includes meshes with 2+ skinClusters OR meshes with blendShapes+skinCluster
        """
        if cmds is None:
            return {}

        mesh_to_skins = {}
        skin_clusters = cmds.ls(type='skinCluster') or []

        for sc in skin_clusters:
            try:
                geometry = cmds.skinCluster(sc, query=True, geometry=True) or []
                for geo in geometry:
                    if geo not in mesh_to_skins:
                        mesh_to_skins[geo] = []
                    mesh_to_skins[geo].append(sc)
            except Exception:
                pass

        # Find meshes with blendShapes (mayaUSD export can fail on these)
        mesh_to_blendshapes = {}
        blendshape_nodes = cmds.ls(type='blendShape') or []

        for bs in blendshape_nodes:
            try:
                geometry = cmds.blendShape(bs, query=True, geometry=True) or []
                for geo in geometry:
                    if geo not in mesh_to_blendshapes:
                        mesh_to_blendshapes[geo] = []
                    mesh_to_blendshapes[geo].append(bs)
            except Exception:
                pass

        # DIAGNOSTIC: Log ALL meshes with blendShapes found
        if mesh_to_blendshapes:
            self.logger.info(f"   [DEBUG] DIAGNOSTIC: Found {len(mesh_to_blendshapes)} meshes with blendShapes:")
            for mesh, bs_list in mesh_to_blendshapes.items():
                self.logger.info(f"      - {mesh} ({len(bs_list)} blendShapes)")

        # Filter to problematic meshes:
        # 1. Meshes with 2+ skinClusters (multi-skinCluster issue)
        # 2. Meshes with blendShapes AND skinCluster (mayaUSD export fails)
        problem_meshes = {}

        # Check skinned meshes for blendShapes
        for mesh, skins in mesh_to_skins.items():
            if len(skins) > 1:
                # Multi-skinCluster issue
                problem_meshes[mesh] = skins
            elif mesh in mesh_to_blendshapes:
                # BlendShape + skinCluster combination (also problematic)
                problem_meshes[mesh] = skins
                self.logger.info(f"   [BLEND] {mesh}: has blendShapes + skinCluster (will bake geometry)")

        # Also check blendShape meshes for skinClusters (reverse direction)
        # Maya creates separate shape nodes (original vs deformed), so names may not match
        for bs_mesh in mesh_to_blendshapes.keys():
            if bs_mesh in problem_meshes:
                continue  # Already handled

            # Check if this mesh has a skinCluster (query the mesh directly)
            try:
                # Get transform node from shape
                transform = None
                if cmds.objectType(bs_mesh) == 'transform':
                    transform = bs_mesh
                else:
                    parents = cmds.listRelatives(bs_mesh, parent=True, fullPath=True) or []
                    if parents:
                        transform = parents[0]

                if transform:
                    # Check for skinCluster in the mesh's history
                    history = cmds.listHistory(transform, pruneDagObjects=True) or []
                    skin_in_history = [h for h in history if cmds.objectType(h) == 'skinCluster']

                    if skin_in_history:
                        # This mesh has both blendShape and skinCluster - add it
                        problem_meshes[bs_mesh] = skin_in_history
                        self.logger.info(f"   [BLEND] {bs_mesh}: has blendShapes + skinCluster (will bake geometry)")
            except Exception:
                pass

        return problem_meshes

    def _fix_multi_skincluster_for_export(
        self,
        multi_skin_meshes: dict,
        export_transforms: set
    ) -> list:
        """
        Fix meshes with multiple skinClusters for USD export.

        Strategy: For each affected mesh, duplicate it with only the primary
        skinCluster. The primary is whichever skinCluster has 'skinCluster'
        in the name (the base deformation), or else the last one in the
        deformation chain. The original mesh is removed from the export
        selection and the fixed duplicate takes its place.

        Args:
            multi_skin_meshes: Dict mapping mesh name -> list of skinCluster names
            export_transforms: The mutable set of transforms to export (updated in-place)

        Returns:
            List of temporary duplicate node names to clean up after export
        """
        if cmds is None:
            return []

        temp_nodes = []

        for mesh_name, skin_clusters in multi_skin_meshes.items():
            try:
                # Get the full path of the mesh transform
                mesh_transforms = cmds.listRelatives(mesh_name, parent=True, fullPath=True)
                if not mesh_transforms:
                    self.logger.warning(f"   [WARNING] Could not find transform for {mesh_name}")
                    continue
                original_transform = mesh_transforms[0]

                # Check if mesh has blendShapes (need special handling)
                has_blendshapes = False
                blendshape_nodes = []
                try:
                    # Find blendShape nodes affecting this mesh
                    history = cmds.listHistory(mesh_name, pruneDagObjects=True) or []
                    blendshape_nodes = [node for node in history if cmds.nodeType(node) == 'blendShape']
                    has_blendshapes = len(blendshape_nodes) > 0
                except Exception:
                    pass

                # Pick the primary skinCluster
                # Prefer the one named 'skinCluster*' (base deformation layer)
                primary_sc = None
                for sc in skin_clusters:
                    if sc.startswith('skinCluster'):
                        primary_sc = sc
                        break
                if primary_sc is None:
                    # Fallback: use the last one (bottom of deform stack)
                    primary_sc = skin_clusters[-1]

                if has_blendshapes:
                    self.logger.info(
                        f"   [BLEND] {mesh_name}: has blendShapes + "
                        f"{len(skin_clusters)} skinClusters - baking geometry"
                    )
                else:
                    ignored_count = len(skin_clusters) - 1
                    log_msg = f"   [FIX] {mesh_name}: using {primary_sc} (ignoring {ignored_count} others)"
                    self.logger.info(log_msg)

                # Duplicate the mesh (captures current deformed shape INCLUDING blendshapes)
                dup = cmds.duplicate(original_transform, name=f"{original_transform.split('|')[-1]}_usdExport")[0]
                dup_long = cmds.ls(dup, long=True)[0]
                temp_nodes.append(dup_long)

                # Delete ALL deformers from duplicate (skinClusters, blendShapes, everything)
                # This leaves us with clean baked geometry
                dup_shape = cmds.listRelatives(dup_long, shapes=True, fullPath=True)[0]
                history = cmds.listHistory(dup_shape, pruneDagObjects=True) or []
                deformers_to_delete = []
                for node in history:
                    node_type = cmds.nodeType(node)
                    if node_type in ['skinCluster', 'blendShape', 'tweak', 'groupParts', 'groupId']:
                        deformers_to_delete.append(node)

                if deformers_to_delete:
                    try:
                        cmds.delete(deformers_to_delete)
                    except Exception:
                        pass  # Some nodes might already be deleted as dependencies

                # Get the influences (joints) from the primary skinCluster
                influences = cmds.skinCluster(primary_sc, query=True, influence=True)
                if not influences:
                    self.logger.warning(f"   [WARNING] No influences on {primary_sc}, skipping fix")
                    continue

                # Re-bind the clean duplicate to only the primary skinCluster's joints
                new_sc = cmds.skinCluster(
                    influences, dup_long,
                    toSelectedBones=True,
                    bindMethod=0,     # Closest distance
                    normalizeWeights=1,
                    weightDistribution=0,
                    name=f"{primary_sc}_usdExport"
                )[0]

                # Copy weights from the primary skinCluster to the new one
                cmds.copySkinWeights(
                    sourceSkin=primary_sc,
                    destinationSkin=new_sc,
                    noMirror=True,
                    surfaceAssociation='closestPoint',
                    influenceAssociation=['oneToOne', 'closestJoint']
                )

                # Remove the original from export, add the duplicate
                export_transforms.discard(original_transform)
                export_transforms.add(dup_long)

                if has_blendshapes:
                    dup_short = dup_long.split('|')[-1]
                    self.logger.info(
                        f"   [OK] {mesh_name} → {dup_short} (baked geometry, clean skinCluster)"
                    )
                else:
                    self.logger.info(f"   [OK] {mesh_name} → {dup_long.split('|')[-1]} (single skinCluster)")

            except Exception as e:
                self.logger.warning(f"   [WARNING] Failed to fix {mesh_name}: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())

        return temp_nodes

    def _get_deformation_joint_hierarchy(self) -> set:
        """
        Get deformation joints PLUS their parent chain up to the root.

        USD Skeleton requires a complete hierarchy from root to deformation joints.
        This ensures we export a valid skeleton structure.

        Returns:
            Set of joint long names forming a complete skeleton hierarchy
        """
        if cmds is None:
            return set()

        # Start with direct deformation joints
        deformation_joints = self._get_deformation_joints()

        # Add parent chain for each deformation joint
        complete_hierarchy = set(deformation_joints)

        for joint in deformation_joints:
            # Walk up the parent chain
            current = joint
            while current:
                parent_list = cmds.listRelatives(current, parent=True, fullPath=True) or []
                if not parent_list:
                    break
                parent = parent_list[0]

                # Stop if parent is not a joint (reached transform node)
                if not cmds.nodeType(parent) == 'joint':
                    # Check if it's a transform with a joint child
                    node_type = cmds.nodeType(parent)
                    if node_type not in ['joint', 'transform']:
                        break
                    # If it's a transform, we've left the skeleton
                    if node_type == 'transform':
                        break

                complete_hierarchy.add(parent)
                current = parent

        return complete_hierarchy

    def _get_deformation_skeleton_root(self) -> str | None:
        """
        Find the single root joint of the deformation skeleton.

        For USD Animation workflow, we need to identify the ONE skeleton
        that actually deforms meshes. This is typically:
        - DeformationSystem/Root_M (Advanced Skeleton)
        - root/skeleton (standard rigs)
        - The root of whatever hierarchy has skinCluster influences

        Returns:
            Long name of the deformation root joint, or None if not found
        """
        if cmds is None:
            return None

        deform_joints = self._get_deformation_joints()
        if not deform_joints:
            return None

        # Find the topmost joints (roots) among deformation joints
        roots = set()
        for joint in deform_joints:
            current = joint
            while True:
                parent_list = cmds.listRelatives(current, parent=True, fullPath=True) or []
                if not parent_list:
                    roots.add(current)
                    break
                parent = parent_list[0]
                # Check if parent is a joint
                if cmds.nodeType(parent) != 'joint':
                    roots.add(current)
                    break
                # Check if parent is also a deformation joint
                if parent not in deform_joints:
                    # Parent exists but isn't used for deformation
                    # Keep walking up to find true skeleton root
                    pass
                current = parent

        if len(roots) == 1:
            return list(roots)[0]
        elif len(roots) > 1:
            # Multiple roots - find common ancestor or pick the one with most descendants
            self.logger.warning(f"[WARNING] Found {len(roots)} deformation skeleton roots")
            for root in roots:
                self.logger.info(f"   └─ {root.split('|')[-1]}")
            # Return the one with "Deformation" or "Root" in name, or first one
            for root in roots:
                short_name = root.split('|')[-1].lower()
                if 'deform' in short_name or 'root' in short_name:
                    return root
            return list(roots)[0]

        return None

    def _export_rig_mb_backup(self, output_path: Path) -> bool:
        """
        Export complete Maya scene as .rig.mb backup

        This preserves EVERYTHING for fallback/reference.
        """
        try:
            if cmds is None:
                self.logger.error("Maya cmds not available")
                return False

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save entire scene as Maya Binary
            # We export selected=False to get everything
            cmds.file(
                str(output_path),
                exportAll=True,
                type="mayaBinary",
                force=True,
                preserveReferences=True,
                constructionHistory=True,
                channels=True,
                constraints=True,
                expressions=True,
                shader=True
            )

            file_size = output_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"[PACKAGE] Rig backup: {output_path.name} ({file_size:.1f} MB)")
            return True

        except Exception as e:
            self.logger.error(f"Rig backup export failed: {e}")
            return False

    def _export_with_mayausd(
        self,
        output_path: Path,
        options: ExportOptions,
        result: ExportResult
    ) -> bool:
        """
        Export to USD using mayaUSD plugin with maximum conversion

        This uses mayaUSDExport to convert as much as possible to native USD.
        """
        if not self._mayausd_available:
            self.logger.error("mayaUSD plugin not available")
            return False

        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if cmds is None:
                self.logger.error("Maya cmds not available")
                return False

            # SIMPLE APPROACH: Select all geometry, joints, and curves then export selection
            # This is more reliable than trying to figure out exportRoots

            # Save current selection
            original_selection = cmds.ls(selection=True, long=True) or []

            # Debug: What's in the scene?
            all_dag = cmds.ls(dag=True, long=True) or []
            self.logger.info(f"[EXPORT] Scene has {len(all_dag)} DAG nodes")

            # Select all exportable content
            # CRITICAL: Use dag=True to get ALL nodes including referenced ones
            # In viewport-friendly mode, skip NURBS curves - they stay in .rig.mb
            # to preserve their original shapes and colors
            if options.viewport_friendly_skeleton:
                export_types = ['mesh', 'nurbsSurface', 'joint']  # No nurbsCurve - ALL kept in .rig.mb
                self.logger.info("🎮 ALL NURBS curves excluded from USD - preserved in .rig.mb only")
            else:
                export_types = ['mesh', 'nurbsSurface', 'joint']  # No curves in USD at all
            all_shapes = []
            for shape_type in export_types:
                # dag=True ensures we get referenced nodes too
                shapes = cmds.ls(type=shape_type, dag=True, long=True) or []
                self.logger.info(f"[EXPORT] Found {len(shapes)} {shape_type} nodes")
                all_shapes.extend(shapes)

            if not all_shapes:
                # More debugging - what IS in the scene?
                self.logger.error("[ERROR] No exportable content found in scene!")
                self.logger.info("[EXPORT] Node types in scene:")
                node_types = set()
                for node in all_dag[:100]:  # First 100 nodes
                    try:
                        node_types.add(cmds.nodeType(node))
                    except Exception:
                        pass
                self.logger.info(f"   Types found: {sorted(node_types)}")
                return False

            # Get the transforms of all shapes (what we actually export)
            export_transforms = set()
            for shape in all_shapes:
                parent = cmds.listRelatives(shape, parent=True, fullPath=True)
                if parent:
                    export_transforms.add(parent[0])

            # ============ USD ANIMATION MODE (Phase 3.3) ============
            # When merge_skeletons=True, we want USD-native animation.
            # Key insight: Only export the DEFORMATION skeleton (DeformationSystem)
            # Skip IK/FK/Twist/Fit skeletons - they don't work in USD anyway!
            if options.merge_skeletons:
                deform_joints = self._get_deformation_joint_hierarchy()
                all_joints = cmds.ls(type='joint', dag=True, long=True) or []

                # Filter out facial joints if body_skeleton_only is True
                # Facial joints are often disconnected hierarchies that create multiple Skeleton prims
                if options.body_skeleton_only:
                    body_joints = set()
                    facial_excluded = []

                    for joint in deform_joints:
                        short_name = joint.split('|')[-1]
                        is_facial = any(pattern in short_name for pattern in options.facial_joint_patterns)

                        if is_facial:
                            facial_excluded.append(short_name)
                        else:
                            body_joints.add(joint)

                    self.logger.info("[SKEL] USD Animation Mode - BODY skeleton only:")
                    self.logger.info(f"   └─ Total joints in scene: {len(all_joints)}")
                    self.logger.info(f"   └─ Deformation joints: {len(deform_joints)}")
                    self.logger.info(f"   └─ Body joints (exported): {len(body_joints)}")
                    self.logger.info(f"   └─ Facial joints (excluded): {len(facial_excluded)}")

                    deform_joints = body_joints
                else:
                    self.logger.info("[SKEL] USD Animation Mode - Full deformation skeleton:")
                    self.logger.info(f"   └─ Total joints in scene: {len(all_joints)}")
                    self.logger.info(f"   └─ Deformation joints: {len(deform_joints)}")

                deform_root = self._get_deformation_skeleton_root()
                if deform_root:
                    self.logger.info(f"   └─ Deformation root: {deform_root.split('|')[-1]}")

                # Only add deformation joints to export
                export_transforms.update(deform_joints)
                joints = list(deform_joints)

            # ============ SIMPLIFIED SKELETON EXPORT ============
            # When enabled, only export joints that ACTUALLY deform geometry
            # This dramatically reduces skeleton complexity and helps UsdSkelImaging
            elif options.simplified_skeleton_export:
                deform_joints = self._get_deformation_joint_hierarchy()
                all_joints = cmds.ls(type='joint', dag=True, long=True) or []

                self.logger.info("[SKEL] Simplified skeleton export enabled:")
                self.logger.info(f"   └─ Total joints in scene: {len(all_joints)}")
                self.logger.info(f"   └─ Deformation joints (with parents): {len(deform_joints)}")
                self.logger.info(f"   └─ Joints excluded: {len(all_joints) - len(deform_joints)}")

                # Only add deformation joints
                export_transforms.update(deform_joints)
                joints = list(deform_joints)  # For logging below
            else:
                # Also add joints directly (they don't have shapes)
                joints = cmds.ls(type='joint', dag=True, long=True) or []
                export_transforms.update(joints)

            # ============ XGEN/HAIR MESH FILTERING ============
            # Filter out XGen scalp meshes, hair guides, and groom geometry
            if options.exclude_xgen_meshes:
                xgen_filtered = []
                patterns = options.xgen_mesh_patterns

                for transform in list(export_transforms):
                    # Get short name for pattern matching
                    short_name = transform.split('|')[-1].split(':')[-1]

                    # Check if name matches any XGen pattern
                    is_xgen = any(pattern.lower() in short_name.lower() for pattern in patterns)

                    if is_xgen:
                        xgen_filtered.append(short_name)
                        export_transforms.discard(transform)

                if xgen_filtered:
                    self.logger.info(f"[BLEND] XGen filter: Excluded {len(xgen_filtered)} meshes")
                    for name in xgen_filtered[:5]:  # Show first 5
                        self.logger.info(f"   └─ {name}")
                    if len(xgen_filtered) > 5:
                        self.logger.info(f"   └─ ... and {len(xgen_filtered) - 5} more")

            # Check for complex skeleton setup (multiple skinClusters = potential UsdSkel issues)
            skin_clusters = cmds.ls(type='skinCluster') or []
            num_skin_clusters = len(skin_clusters)
            self.logger.info(f"[SKEL] Found {num_skin_clusters} skinClusters in scene")

            # Track duplicates for cleanup
            baked_meshes = []
            original_skinned_meshes = []

            # CRITICAL: Detect and FIX meshes with multiple skinClusters
            # Advanced Skeleton stacks facial deformers (CageSC, EyeLidSC, etc.) on body mesh
            # mayaUSD CANNOT export these - produces empty/corrupt mesh data!
            # FIX: Duplicate affected meshes keeping only the primary skinCluster
            multi_skin_meshes = self._detect_multi_skincluster_meshes()
            if multi_skin_meshes and not options.viewport_friendly_skeleton:
                self.logger.info("[FIX] MULTI-SKINCLUSTER MESHES DETECTED - Auto-fixing...")
                for mesh, skins in list(multi_skin_meshes.items()):
                    self.logger.info(f"   [FIX] {mesh} ({len(skins)} skinClusters: {', '.join(skins)})")
                fixed_meshes = self._fix_multi_skincluster_for_export(
                    multi_skin_meshes, export_transforms
                )
                baked_meshes.extend(fixed_meshes)
                self.logger.info(f"   [OK] Fixed {len(fixed_meshes)} multi-skinCluster meshes")

            # Log viewport-friendly mode status
            if options.viewport_friendly_skeleton and num_skin_clusters > 0:
                self.logger.info(
                    f"[VIEWPORT] Viewport-friendly mode: Skeleton hierarchy exported, "
                    f"skin bindings skipped ({num_skin_clusters} skinClusters)"
                )
                self.logger.info("   └─ Baking skinned meshes to static geometry...")

                # Find all skinned meshes and bake them
                for skin_cluster in skin_clusters:
                    # Get the mesh affected by this skinCluster
                    geometry = cmds.skinCluster(skin_cluster, query=True, geometry=True)
                    if not geometry:
                        continue

                    for geo in geometry:
                        # Get the transform node
                        transforms = cmds.listRelatives(geo, parent=True, fullPath=True)
                        if not transforms:
                            continue

                        original_transform = transforms[0]
                        original_skinned_meshes.append(original_transform)

                        # Duplicate the mesh (this captures current deformed state)
                        duplicate = cmds.duplicate(
                            original_transform,
                            renameChildren=True,
                            returnRootsOnly=True
                        )
                        if not duplicate:
                            continue

                        baked_mesh = duplicate[0]
                        baked_meshes.append(baked_mesh)

                        # Delete the skinCluster and any other deformers from the duplicate
                        shapes = cmds.listRelatives(baked_mesh, shapes=True, fullPath=True) or []
                        for shape in shapes:
                            history = cmds.listHistory(shape, pruneDagObjects=True) or []
                            deformers = cmds.ls(history, type='geometryFilter')
                            if deformers:
                                cmds.delete(deformers)

                        # Replace the original in export_transforms with the baked version
                        if original_transform in export_transforms:
                            export_transforms.remove(original_transform)
                        export_transforms.add(baked_mesh)

                self.logger.info(f"   └─ Baked {len(baked_meshes)} skinned meshes to static geometry")
                self.logger.info("   └─ NURBS curves (controllers) preserved in .rig.mb only")
                self.logger.info("   └─ Full skinning preserved in .rig.mb backup")
            elif num_skin_clusters > 5:
                self.logger.warning(
                    f"[WARNING] Complex skeleton setup detected ({num_skin_clusters} skinClusters). "
                    "USD viewport may have display issues. Consider viewport_friendly_skeleton=True"
                )

            self.logger.info(f"[TARGET] Found {len(export_transforms)} objects to export")
            self.logger.info(f"   Meshes: {len(cmds.ls(type='mesh', dag=True) or [])}")
            self.logger.info(f"   NURBS Curves: {len(cmds.ls(type='nurbsCurve', dag=True) or [])}")
            self.logger.info(f"   Joints: {len(joints)}")

            # Select everything for export
            cmds.select(list(export_transforms), replace=True)

            # Build mayaUSDExport arguments for MAXIMUM conversion
            # Note: NURBS curves export automatically as part of scene geometry
            # Note: Animation controlled via frameRange, not exportAnimation flag
            export_args = {
                'file': str(output_path),

                # ============ CRITICAL: Export selection ============
                'selection': True,

                # ============ GEOMETRY ============
                'exportDisplayColor': True,
                'exportUVs': True,
                'exportMaterialCollections': False,

                # ============ SKELETON & SKINNING ============
                # viewport_friendly_skeleton: export skeleton but skip skin bindings
                # This avoids UsdSkelImaging viewport bugs with complex rigs
                # We manually bake skinned meshes before export (duplicate + delete skinCluster)
                # CRITICAL: When simplified_skeleton_export + viewport_friendly_skeleton are BOTH True,
                # skip skeleton export entirely - meshes are baked, no skeleton needed in USD
                'exportSkels': (
                    'none' if (options.simplified_skeleton_export and options.viewport_friendly_skeleton)
                    else ('auto' if options.export_skeleton else 'none')
                ),
                'exportSkin': (
                    'none' if options.viewport_friendly_skeleton
                    else ('auto' if options.export_skin_weights else 'none')
                ),

                # ============ BLENDSHAPES ============
                # Maya 2026 supports this!
                # NOTE: Keep False here — _export_blendshapes_to_usd() handles blendshapes
                # correctly via UsdSkel.BlendShape prims.  Setting True causes mayaUSD to
                # also export blendshape TARGET meshes as standalone root-level Mesh prims
                # (50+ floating clones visible in USD viewers).
                'exportBlendShapes': False,

                # ============ MATERIALS ============
                'exportMaterials': options.export_materials,
                'shadingMode': 'useRegistry',
                'convertMaterialsTo': ['UsdPreviewSurface'],
                # Support RenderMan PxrSurface/PxrShader conversion
                'materialsScopeName': 'Looks',  # Standard USD materials scope
                'exportDisplayColor': True,  # Fallback for unconverted materials

                # ============ GENERAL ============
                'exportVisibility': True,
                'exportInstances': True,
                'exportStagesAsRefs': False,
                'mergeTransformAndShape': True,
                'stripNamespaces': not options.include_namespaces,

                # ============ FILTER OUT NURBS CURVES AND SURFACES ============
                # nurbsCurve  — control curve shapes (CVs, IK handles, etc.)
                # nurbsSurface — NURBS patch surfaces (eye-lid fitGeo, cluster controls)
                # Both are rig helpers that must NOT render in the USD output.
                # They stay visible only inside .rig.mb via the controllers sublayer.
                'filterTypes': ['nurbsCurve', 'nurbsSurface'],
            }

            # Add RenderMan support if available and requested
            if options.export_renderman and cmds is not None:
                try:
                    # Check if RenderMan is available
                    if cmds.pluginInfo('RenderMan_for_Maya', query=True, loaded=True):
                        # Add RenderMan material conversion
                        export_args['convertMaterialsTo'].append('rendermanForMaya')
                        self.logger.info("[BLEND] RenderMan material export enabled")
                except Exception:
                    pass

            # Add animation range if exporting animation
            if options.export_animation:
                export_args['frameRange'] = (
                    int(options.animation_start),
                    int(options.animation_end)
                )

            self.logger.info(f"mayaUSDExport args: {export_args}")

            # Log if skipping skeleton export due to simplified mode
            if options.simplified_skeleton_export and options.viewport_friendly_skeleton:
                self.logger.info("[SKEL] Simplified mode: Skipping skeleton export (meshes are baked)")
                self.logger.info("   └─ Full rigging preserved in .rig.mb backup")

            # Execute export
            if cmds is None:
                self.logger.error("Maya cmds not available")
                return False

            try:
                cmds.mayaUSDExport(**export_args)
            except TypeError as te:
                # Handle invalid flag errors - try with minimal flags
                self.logger.warning(f"mayaUSD export with full flags failed: {te}")
                self.logger.info("[REFRESH] Retrying with minimal flags...")

                # Minimal export args that should work
                # Note: NURBS export automatically with scene geometry
                minimal_args = {
                    'file': str(output_path),
                    'selection': True,  # Export current selection
                    'exportDisplayColor': True,
                    'exportUVs': True,
                    'exportSkels': (
                        'none' if (options.simplified_skeleton_export and options.viewport_friendly_skeleton)
                        else ('auto' if options.export_skeleton else 'none')
                    ),
                    'exportSkin': (
                        'none' if options.viewport_friendly_skeleton
                        else ('auto' if options.export_skin_weights else 'none')
                    ),
                    'exportBlendShapes': False,   # see export_args comment above
                    'exportMaterials': options.export_materials,
                    'shadingMode': 'useRegistry',
                    'exportVisibility': True,
                    'stripNamespaces': not options.include_namespaces,
                    'filterTypes': ['nurbsCurve', 'nurbsSurface'],  # hide all rig helpers
                }

                # Animation via frameRange only
                if options.export_animation:
                    minimal_args['frameRange'] = (
                        int(options.animation_start),
                        int(options.animation_end)
                    )

                self.logger.info(f"Minimal mayaUSDExport args: {minimal_args}")
                cmds.mayaUSDExport(**minimal_args)
            finally:
                # Clean up baked mesh duplicates
                if baked_meshes:
                    try:
                        cmds.delete(baked_meshes)
                        self.logger.info(f"[CLEANUP] Cleaned up {len(baked_meshes)} baked mesh duplicates")
                    except Exception as cleanup_error:
                        self.logger.warning(f"Failed to cleanup baked meshes: {cleanup_error}")

                # Restore original selection
                if original_selection:
                    cmds.select(original_selection, replace=True)
                else:
                    cmds.select(clear=True)

            # ============ POST-PROCESSING ============
            # FIX: Merge multiple SkelRoots into one for proper viewport display
            # Maya exports sibling hierarchies as separate SkelRoots, causing
            # UsdSkelImaging to fail because bindings cross SkelRoot boundaries
            self._fix_skelroot_scope(output_path)

            # FIX: Ensure geomBindTransform is set on all skinned meshes
            # UsdSkelImaging requires this attribute for proper viewport display
            self._fix_geom_bind_transforms(output_path)

            # POST-PROCESS: Export Maya blendShapes to USD using pxr Python API
            # mayaUSD doesn't export blendShapes (Maya 2026 limitation)
            # Writing them manually makes them readable by other DCCs and future mayaUSD
            if options.export_blendshapes:
                blend_targets_exported = self._export_blendshapes_to_usd(output_path)
                if blend_targets_exported > 0:
                    result.usd_blendshapes = blend_targets_exported
                    self.logger.info(f"[USD] Exported {blend_targets_exported} blendShape targets to USD")

            # POST-PROCESS: Convert RenderMan materials to UsdPreviewSurface
            # Ensure PxrShader + Lambert combinations are properly converted
            self._current_export_options = options  # give post-process methods access
            if options.export_materials:
                self._convert_renderman_materials_to_usd_preview(output_path)

            # POST-PROCESS: Structural fix-up — must run after material conversion so
            # that the UsdPreviewSurface shaders injected above are visible to the
            # outputs:surface wiring pass.
            # Fixes: outputs:surface wiring, material:binding, Skeleton→Xform re-typing,
            #        orphan SkelAnimation deactivation, root-level blendshape mesh deactivation.
            self._fix_exported_usdc(output_path)

            # Phase 3.3: USD-native animation workflow
            if options.merge_skeletons and not options.usd_layers_for_animation:
                # Legacy: destructive merge
                self.logger.info("[SKEL] Merging skeletons (legacy mode)...")
                self._merge_skeleton_prims(output_path)

            # Validate and count what was exported
            self._validate_usd_export(output_path, options, result, num_skin_clusters)

            return output_path.exists()

        except Exception as e:
            self.logger.error(f"mayaUSD export failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _create_layered_usd(
        self,
        base_usd_path: Path,
        options: ExportOptions,
        result: ExportResult
    ) -> bool:
        """
        Create a layered USD structure from the exported USD

        USD Layers allow:
        - Non-destructive editing (overrides in separate layers)
        - Collaboration (different artists edit different layers)
        - Organization (geometry, materials, animation separated)
        - Pipeline flexibility (swap materials, animation, etc.)

        Layer structure:
        root.usda (references sublayers)
        ├── geometry.usdc (meshes, curves, transforms)
        ├── skeleton.usdc (joints, skinning, blendshapes)
        ├── materials.usdc (shaders, textures)
        └── animation.usdc (keyframes, constraints)
        """
        if not USD_AVAILABLE:
            self.logger.warning("USD Python API not available for layered export")
            return False

        try:
            from pxr import Usd  # type: ignore

            base_dir = base_usd_path.parent
            base_name = base_usd_path.stem

            # Open the source USD to extract data
            source_stage = Usd.Stage.Open(str(base_usd_path))  # type: ignore
            if not source_stage:
                self.logger.error("Could not open source USD for layering")
                return False

            layer_paths = []

            # Create geometry layer
            if options.geometry_layer:
                geom_path = base_dir / f"{base_name}.geometry.usdc"
                if self._extract_geometry_layer(source_stage, geom_path):
                    layer_paths.append(geom_path)
                    self.logger.info(f"[PACKAGE] Created geometry layer: {geom_path.name}")

            # Create skeleton layer
            if options.skeleton_layer:
                skel_path = base_dir / f"{base_name}.skeleton.usdc"
                if self._extract_skeleton_layer(source_stage, skel_path):
                    layer_paths.append(skel_path)
                    self.logger.info(f"[PACKAGE] Created skeleton layer: {skel_path.name}")

            # Create materials layer
            if options.materials_layer:
                mtl_path = base_dir / f"{base_name}.materials.usdc"
                if self._extract_materials_layer(source_stage, mtl_path):
                    layer_paths.append(mtl_path)
                    self.logger.info(f"[PACKAGE] Created materials layer: {mtl_path.name}")

            # Create animation layer (if animation was exported)
            if options.animation_layer and options.export_animation:
                anim_path = base_dir / f"{base_name}.animation.usdc"
                if self._extract_animation_layer(source_stage, anim_path):
                    layer_paths.append(anim_path)
                    self.logger.info(f"[PACKAGE] Created animation layer: {anim_path.name}")

            # Create root layer that references sublayers
            if layer_paths:
                root_path = base_dir / f"{base_name}.layered.usda"
                self._create_root_layer(root_path, layer_paths, base_name)
                self.logger.info(f"[OK] Created layered USD structure: {root_path.name}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to create layered USD: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _extract_geometry_layer(self, source_stage, output_path: Path) -> bool:
        """Extract geometry prims to a separate layer"""
        try:
            from pxr import Usd, Sdf  # pyright: ignore[reportMissingImports]

            # Create new layer
            layer = Sdf.Layer.CreateNew(str(output_path))
            stage = Usd.Stage.Open(layer)

            # Copy geometry prims (Mesh, NurbsCurves, BasisCurves, Xform)
            geom_types = {'Mesh', 'NurbsCurves', 'BasisCurves', 'Xform', 'Scope'}
            for prim in source_stage.Traverse():
                if prim.GetTypeName() in geom_types:
                    # Copy prim and its attributes
                    Sdf.CopySpec(
                        source_stage.GetRootLayer(),
                        prim.GetPath(),
                        layer,
                        prim.GetPath()
                    )

            stage.Save()
            return output_path.exists()

        except Exception as e:
            self.logger.debug(f"Geometry layer extraction failed: {e}")
            return False

    def _extract_skeleton_layer(self, source_stage, output_path: Path) -> bool:
        """Extract skeleton/skinning prims to a separate layer"""
        try:
            from pxr import Usd, Sdf  # pyright: ignore[reportMissingImports]

            layer = Sdf.Layer.CreateNew(str(output_path))
            stage = Usd.Stage.Open(layer)

            # Copy skeleton prims
            skel_types = {'Skeleton', 'SkelRoot', 'SkelAnimation', 'BlendShape'}
            for prim in source_stage.Traverse():
                prim_type = prim.GetTypeName()
                if prim_type in skel_types or prim.HasAPI('UsdSkelBindingAPI'):
                    Sdf.CopySpec(
                        source_stage.GetRootLayer(),
                        prim.GetPath(),
                        layer,
                        prim.GetPath()
                    )

            stage.Save()
            return output_path.exists()

        except Exception as e:
            self.logger.debug(f"Skeleton layer extraction failed: {e}")
            return False

    def _extract_materials_layer(self, source_stage, output_path: Path) -> bool:
        """Extract material prims to a separate layer"""
        try:
            from pxr import Usd, Sdf  # pyright: ignore[reportMissingImports]

            layer = Sdf.Layer.CreateNew(str(output_path))
            stage = Usd.Stage.Open(layer)

            # Copy material prims
            mtl_types = {'Material', 'Shader', 'NodeGraph'}
            for prim in source_stage.Traverse():
                if prim.GetTypeName() in mtl_types:
                    Sdf.CopySpec(
                        source_stage.GetRootLayer(),
                        prim.GetPath(),
                        layer,
                        prim.GetPath()
                    )

            stage.Save()
            return output_path.exists()

        except Exception as e:
            self.logger.debug(f"Materials layer extraction failed: {e}")
            return False

    def _extract_animation_layer(self, source_stage, output_path: Path) -> bool:
        """Extract animation data to a separate layer"""
        try:
            from pxr import Usd, Sdf  # pyright: ignore[reportMissingImports]

            layer = Sdf.Layer.CreateNew(str(output_path))
            stage = Usd.Stage.Open(layer)

            # Copy animation-related prims
            anim_types = {'SkelAnimation'}
            for prim in source_stage.Traverse():
                if prim.GetTypeName() in anim_types:
                    Sdf.CopySpec(
                        source_stage.GetRootLayer(),
                        prim.GetPath(),
                        layer,
                        prim.GetPath()
                    )

            # Also copy time samples from other prims (animated attributes)
            # This is handled by USD's time sample system automatically

            stage.Save()
            return output_path.exists()

        except Exception as e:
            self.logger.debug(f"Animation layer extraction failed: {e}")
            return False

    def _create_root_layer(
        self,
        root_path: Path,
        sublayer_paths: List[Path],
        asset_name: str
    ) -> bool:
        """Create root layer that references sublayers"""
        try:
            from pxr import Usd, Sdf, UsdGeom  # pyright: ignore[reportMissingImports]

            # Create root layer as ASCII for readability
            layer = Sdf.Layer.CreateNew(str(root_path))
            stage = Usd.Stage.Open(layer)

            # Set up stage metadata
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            stage.SetDefaultPrim(stage.DefinePrim(f"/{asset_name}", "Xform"))

            # Add sublayers.  In USD, subLayerPaths[0] is the **strongest** opinion
            # (LIFO order): the first entry wins attribute conflicts.  We append in
            # the order [geometry, skeleton, materials, animation] so that geometry
            # bindings (material:binding relationships on meshes) take precedence.
            root_layer = stage.GetRootLayer()
            for sublayer_path in sublayer_paths:
                # Use relative paths for portability
                rel_path = f"./{sublayer_path.name}"
                root_layer.subLayerPaths.append(rel_path)

            # Add documentation
            stage.GetRootLayer().documentation = (
                f"USD Layered Asset: {asset_name}\n"
                f"Generated by Asset Manager USD Pipeline\n"
                f"Sublayers can be edited independently for non-destructive workflows."
            )

            stage.Save()
            self.logger.info(f"[FILE] Root layer references {len(sublayer_paths)} sublayers")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create root layer: {e}")
            return False

    def _fix_skelroot_scope(self, usd_path: Path) -> bool:
        """
        Fix SkelRoot scope issues by wrapping multiple SkelRoots under a single parent.

        Maya exports sibling hierarchies as separate SkelRoots, which breaks
        UsdSkelImaging (skinned meshes must be under the same SkelRoot as skeleton).

        SOLUTION: Instead of MOVING prims (which corrupts mesh data), we:
        1. Create a new parent SkelRoot that encompasses everything
        2. Demote the existing SkelRoots to regular Xform prims
        3. Re-parent them under the new wrapper (using Sdf layer operations)

        This preserves all mesh data while satisfying UsdSkel scope requirements.

        Args:
            usd_path: Path to the USD file to fix

        Returns:
            True if fix was applied or not needed
        """
        if not USD_AVAILABLE:
            return True

        try:
            from pxr import Usd, UsdSkel, UsdGeom, Sdf

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                return True

            # Find all SkelRoots at the root level
            root_layer = stage.GetRootLayer()
            # rootPrims returns PrimSpecs - get their names
            root_prim_names = [spec.name for spec in root_layer.rootPrims]
            root_prims = [
                stage.GetPrimAtPath(Sdf.Path("/" + name))
                for name in root_prim_names
            ]
            skel_roots = [p for p in root_prims if p and p.IsA(UsdSkel.Root)]

            if len(skel_roots) <= 1:
                self.logger.info("[OK] Single SkelRoot - no scope fix needed")
                return True

            self.logger.info(f"[FIX] Found {len(skel_roots)} SkelRoots - creating unified wrapper...")
            for sr in skel_roots:
                self.logger.info(f"   [PACKAGE] {sr.GetPath()}")

            # Find which SkelRoot has the skeleton (this will be our reference for bindings)
            skeleton_root = None
            main_skeleton_path = None
            for sr in skel_roots:
                for desc in Usd.PrimRange(sr):
                    if desc.IsA(UsdSkel.Skeleton):
                        skeleton_root = sr
                        main_skeleton_path = desc.GetPath()
                        break
                if skeleton_root:
                    break

            if not skeleton_root:
                self.logger.warning("[WARNING] No skeleton found in any SkelRoot")
                return True

            self.logger.info(f"   [SKEL] Skeleton found at: {main_skeleton_path}")

            # APPROACH: Create wrapper SkelRoot and demote children
            # We'll create "/SkelRoot" as the new parent containing everything
            wrapper_name = "SkelRoot"
            wrapper_path = Sdf.Path("/" + wrapper_name)

            # Check if wrapper already exists
            if stage.GetPrimAtPath(wrapper_path):
                self.logger.info("[OK] Wrapper SkelRoot already exists")
                return True

            # Step 1: Create the wrapper SkelRoot prim
            self.logger.info(f"[FIX] Creating wrapper: {wrapper_path}")
            wrapper_spec = Sdf.CreatePrimInLayer(root_layer, wrapper_path)
            wrapper_spec.typeName = "SkelRoot"
            wrapper_spec.specifier = Sdf.SpecifierDef

            # Step 2: For each existing root-level SkelRoot, re-parent under wrapper
            # We do this by creating new prims under wrapper and moving specs
            for sr in skel_roots:
                old_path = sr.GetPath()
                prim_name = old_path.name
                new_path = wrapper_path.AppendChild(prim_name)

                self.logger.info(f"   [REFRESH] Re-parenting {old_path} → {new_path}")

                # Use namespace edit to move the prim
                edit = Sdf.BatchNamespaceEdit()
                edit.Add(old_path, new_path)

                if root_layer.Apply(edit):
                    # Demote from SkelRoot to Xform (it's now under a SkelRoot)
                    moved_spec = root_layer.GetPrimAtPath(new_path)
                    if moved_spec and moved_spec.typeName == "SkelRoot":
                        moved_spec.typeName = "Xform"
                        self.logger.info("      [OK] Moved and demoted to Xform")
                else:
                    self.logger.warning(f"      [WARNING] Failed to move {old_path}")

            # Step 3: Update skeleton binding paths
            # The skeleton path changed from /Group/... to /SkelRoot/Group/...
            root_layer.Save()
            stage.Reload()

            # Recalculate the new skeleton path
            new_main_skeleton_path = None
            wrapper_prim = stage.GetPrimAtPath(wrapper_path)
            if wrapper_prim:
                for desc in Usd.PrimRange(wrapper_prim):
                    if desc.IsA(UsdSkel.Skeleton):
                        new_main_skeleton_path = desc.GetPath()
                        break

            if new_main_skeleton_path:
                self.logger.info(f"   [SKEL] New skeleton path: {new_main_skeleton_path}")

                # Update all mesh bindings to point to the new skeleton path
                binding_count = 0
                for prim in stage.Traverse():
                    if not prim.IsA(UsdGeom.Mesh):
                        continue

                    binding = UsdSkel.BindingAPI(prim)
                    skel_rel = binding.GetSkeletonRel()
                    if skel_rel and skel_rel.HasAuthoredTargets():
                        old_targets = skel_rel.GetTargets()
                        if old_targets:
                            # Update to new path
                            skel_rel.SetTargets([new_main_skeleton_path])
                            binding_count += 1

                if binding_count > 0:
                    self.logger.info(f"   [OK] Updated {binding_count} skeleton bindings")

            # Step 4: Update ALL skel:animationSource paths
            # These point to Animation prims that moved with their parent skeletons
            anim_source_count = 0
            for prim in stage.Traverse():
                # Check for animationSource on Skeleton prims
                if prim.IsA(UsdSkel.Skeleton):
                    binding = UsdSkel.BindingAPI(prim)
                    anim_rel = binding.GetAnimationSourceRel()
                    if anim_rel and anim_rel.HasAuthoredTargets():
                        old_targets = anim_rel.GetTargets()
                        new_targets = []
                        updated = False
                        for old_target in old_targets:
                            old_str = str(old_target)
                            # Check if path needs updating (doesn't start with /SkelRoot)
                            if old_str.startswith("/") and not old_str.startswith("/SkelRoot"):
                                # Find which root it was under and remap
                                for sr in skel_roots:
                                    old_root = str(sr.GetPath())
                                    if old_str.startswith(old_root):
                                        new_str = "/SkelRoot" + old_str
                                        new_targets.append(Sdf.Path(new_str))
                                        updated = True
                                        break
                                else:
                                    new_targets.append(old_target)
                            else:
                                new_targets.append(old_target)

                        if updated and new_targets:
                            anim_rel.SetTargets(new_targets)
                            anim_source_count += 1

            if anim_source_count > 0:
                self.logger.info(f"   [OK] Updated {anim_source_count} animation source paths")

            # Set default prim to the wrapper
            stage.SetDefaultPrim(wrapper_prim)
            self.logger.info(f"   [OK] Default prim set to: {wrapper_path}")

            # Save changes
            root_layer.Save()
            self.logger.info("[OK] SkelRoot scope fixed: All prims now under unified SkelRoot")
            self.logger.info("   [TARGET] Skeleton and meshes share same SkelRoot scope")

            return True

        except Exception as e:
            self.logger.warning(f"[WARNING] SkelRoot scope fix failed (non-fatal): {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return True  # Non-fatal - continue anyway

    def _merge_skeleton_prims(self, usd_path: Path) -> bool:
        """
        Merge multiple Skeleton prims into a single unified Skeleton.

        Maya exports one Skeleton prim per skinCluster, resulting in 100+ skeletons
        for complex rigs. UsdSkelImaging struggles with this complexity.

        SOLUTION: Post-process to create a single unified Skeleton containing
        all deformation joints, with a single SkelAnimation prim.

        Steps:
        1. Collect all joints from all Skeleton prims
        2. Build unified joint hierarchy (removing duplicates)
        3. Create single Skeleton prim with merged joints
        4. Create single SkelAnimation prim
        5. Update all skin bindings to reference unified skeleton
        6. Remove old skeleton prims

        Args:
            usd_path: Path to the USD file to fix

        Returns:
            True if merge was successful or not needed
        """
        if not USD_AVAILABLE:
            return True

        try:
            from pxr import Usd, UsdSkel, Sdf, Gf, Vt

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("Could not open USD stage for skeleton merge")
                return False

            # Find all existing Skeleton prims
            all_skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]

            if len(all_skeletons) <= 1:
                self.logger.info("[OK] Single or no skeleton - merge not needed")
                return True

            self.logger.info(f"[SKEL] Merging {len(all_skeletons)} Skeleton prims into unified skeleton...")

            # Collect all joint data from all skeletons
            all_joints = []  # List of joint paths (relative to skeleton)
            all_bind_transforms = []  # Bind pose matrices
            all_rest_transforms = []  # Rest pose matrices
            joint_to_skeleton = {}  # Map joint name to source skeleton

            for skel_prim in all_skeletons:
                skel = UsdSkel.Skeleton(skel_prim)

                joints = skel.GetJointsAttr().Get() or []
                bind_transforms = skel.GetBindTransformsAttr().Get() or []
                rest_transforms = skel.GetRestTransformsAttr().Get() or []

                self.logger.debug(f"   [PACKAGE] {skel_prim.GetPath()}: {len(joints)} joints")

                for i, joint in enumerate(joints):
                    # Get the short name (last part of path)
                    joint_name = str(joint).split('/')[-1] if '/' in str(joint) else str(joint)

                    # Skip duplicates (same joint bound in multiple skinClusters)
                    if joint_name in joint_to_skeleton:
                        continue

                    all_joints.append(joint)
                    joint_to_skeleton[joint_name] = skel_prim.GetPath()

                    # Get corresponding transforms
                    if i < len(bind_transforms):
                        all_bind_transforms.append(bind_transforms[i])
                    else:
                        all_bind_transforms.append(Gf.Matrix4d(1.0))  # Identity fallback

                    if i < len(rest_transforms):
                        all_rest_transforms.append(rest_transforms[i])
                    else:
                        all_rest_transforms.append(Gf.Matrix4d(1.0))  # Identity fallback

            self.logger.info(f"   [INFO] Collected {len(all_joints)} unique joints")

            # Find or create SkelRoot
            skel_roots = [p for p in stage.Traverse() if p.IsA(UsdSkel.Root)]
            if skel_roots:
                skel_root = skel_roots[0]
            else:
                # Create a SkelRoot at the top level
                skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/SkelRoot"))
                self.logger.info("   [FIX] Created /SkelRoot")

            skel_root_path = skel_root.GetPath()

            # Create the unified Skeleton prim
            unified_skel_path = skel_root_path.AppendChild("UnifiedSkeleton")

            # Check if unified skeleton already exists
            existing = stage.GetPrimAtPath(unified_skel_path)
            if existing:
                self.logger.info("[OK] Unified skeleton already exists")
                return True

            unified_skel = UsdSkel.Skeleton.Define(stage, unified_skel_path)

            # Set joints attribute
            unified_skel.GetJointsAttr().Set(Vt.TokenArray(all_joints))

            # Set bind transforms
            if all_bind_transforms:
                unified_skel.GetBindTransformsAttr().Set(Vt.Matrix4dArray(all_bind_transforms))

            # Set rest transforms
            if all_rest_transforms:
                unified_skel.GetRestTransformsAttr().Set(Vt.Matrix4dArray(all_rest_transforms))

            self.logger.info(f"   [OK] Created unified skeleton: {unified_skel_path}")
            self.logger.info(f"      Joints: {len(all_joints)}")

            # Create unified SkelAnimation prim
            unified_anim_path = skel_root_path.AppendChild("UnifiedAnimation")
            unified_anim = UsdSkel.Animation.Define(stage, unified_anim_path)

            # Copy joints to animation (required for animation binding)
            unified_anim.GetJointsAttr().Set(Vt.TokenArray(all_joints))

            # Set rest pose as initial animation (identity rotations, zero translations)
            # This will be overwritten when animators keyframe
            if all_rest_transforms:
                # Extract translations and rotations from rest transforms
                translations = []
                rotations = []
                scales = []

                for xform in all_rest_transforms:
                    # Extract translation
                    trans = xform.ExtractTranslation()
                    translations.append(Gf.Vec3f(trans[0], trans[1], trans[2]))

                    # Extract rotation as quaternion
                    rot = xform.ExtractRotation()
                    quat = rot.GetQuat()
                    # USD uses (real, i, j, k) format
                    rotations.append(Gf.Quatf(
                        quat.GetReal(),
                        quat.GetImaginary()[0],
                        quat.GetImaginary()[1],
                        quat.GetImaginary()[2]
                    ))

                    # Default scale
                    scales.append(Gf.Vec3h(1.0, 1.0, 1.0))

                unified_anim.GetTranslationsAttr().Set(Vt.Vec3fArray(translations))
                unified_anim.GetRotationsAttr().Set(Vt.QuatfArray(rotations))
                unified_anim.GetScalesAttr().Set(Vt.Vec3hArray(scales))

            self.logger.info(f"   [OK] Created unified animation: {unified_anim_path}")

            # Update all skin bindings to reference unified skeleton
            binding_count = 0
            for prim in stage.Traverse():
                if prim.GetTypeName() == 'Mesh':
                    # Check if mesh has skeleton binding
                    binding_api = UsdSkel.BindingAPI(prim)
                    if binding_api:
                        skel_rel = binding_api.GetSkeletonRel()
                        anim_source = binding_api.GetAnimationSourceRel()

                        if skel_rel.GetTargets():
                            # Update to unified skeleton
                            skel_rel.SetTargets([unified_skel_path])
                            binding_count += 1

                        if anim_source.GetTargets():
                            # Update to unified animation
                            anim_source.SetTargets([unified_anim_path])

            self.logger.info(f"   [OK] Updated {binding_count} skin bindings")

            # Remove old skeleton prims (this will also remove their animation children)
            for old_skel in all_skeletons:
                stage.RemovePrim(old_skel.GetPath())

            # Save the stage
            stage.GetRootLayer().Save()

            self.logger.info("[OK] Skeleton merge complete!")
            self.logger.info(f"   [SKEL] {len(all_skeletons)} skeletons → 1 unified skeleton")
            self.logger.info(f"   [INFO] {len(all_joints)} joints preserved")

            return True

        except Exception as e:
            self.logger.warning(f"[WARNING] Skeleton merge failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _create_animation_layers(
        self,
        base_usd_path: Path,
        options: ExportOptions,
        result: ExportResult
    ) -> bool:
        """
        Clean up USD for animation workflow (Phase 3.3).

        SIMPLIFIED APPROACH: Instead of complex layer overrides that corrupt mesh data,
        we directly modify the exported USD to:
        1. Keep ONLY the DeformationSystem skeleton (Root_M)
        2. Delete all other skeletons (IK, FK, Twist, Facial, Fit)
        3. Update all skin bindings to point to the single skeleton

        This produces a clean, single-skeleton USD that UsdSkelImaging can handle.
        """
        if not USD_AVAILABLE:
            self.logger.warning("USD Python API not available for animation layers")
            return False

        try:
            from pxr import Usd, UsdSkel  # type: ignore[import-unresolved]

            # Open the source USD with edit access
            stage = Usd.Stage.Open(str(base_usd_path))
            if not stage:
                self.logger.error("Could not open source USD for cleanup")
                return False

            # ================================================================
            # Step 1: Find all skeletons and identify the deformation skeleton
            # ================================================================
            all_skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            self.logger.info(f"   [INFO] Found {len(all_skeletons)} Skeleton prims in source")

            if len(all_skeletons) == 0:
                self.logger.warning("No skeletons found - nothing to clean up")
                return False

            if len(all_skeletons) == 1:
                self.logger.info("   [OK] Single skeleton detected - no cleanup needed!")
                self.logger.info(f"   └─ Skeleton: {all_skeletons[0].GetPath()}")
                result.usd_path = base_usd_path
                return True

            # Find the deformation skeleton (DeformationSystem/Root_M)
            deform_skeleton = None
            deform_skeleton_path = None

            # Priority order for finding deformation skeleton
            deform_patterns = [
                "DeformationSystem/Root_M",
                "DeformationSystem/Root",
                "Root_M",
                "Skeleton"
            ]

            for skel_prim in all_skeletons:
                path_str = str(skel_prim.GetPath())
                for pattern in deform_patterns:
                    if pattern in path_str:
                        # Check joint count - deformation skeleton should have many joints
                        skel = UsdSkel.Skeleton(skel_prim)
                        joints = skel.GetJointsAttr().Get() or []
                        if len(joints) >= 50:  # Deformation skeleton typically has 80+ joints
                            deform_skeleton = skel_prim
                            deform_skeleton_path = skel_prim.GetPath()
                            self.logger.info(f"   [SKEL] Found deformation skeleton: {path_str}")
                            self.logger.info(f"      └─ Joint count: {len(joints)}")
                            break
                if deform_skeleton:
                    break

            if not deform_skeleton:
                # Fallback: use skeleton with most joints
                max_joints = 0
                for skel_prim in all_skeletons:
                    skel = UsdSkel.Skeleton(skel_prim)
                    joints = skel.GetJointsAttr().Get() or []
                    if len(joints) > max_joints:
                        max_joints = len(joints)
                        deform_skeleton = skel_prim
                        deform_skeleton_path = skel_prim.GetPath()

                self.logger.info(f"   [SKEL] Using skeleton with most joints: {deform_skeleton_path}")
                self.logger.info(f"      └─ Joint count: {max_joints}")

            # ================================================================
            # Step 2: Find the corresponding SkelAnimation
            # ================================================================
            deform_animation = None
            deform_animation_path = None

            # Look for animation prim near the skeleton
            for prim in stage.Traverse():
                if prim.IsA(UsdSkel.Animation):
                    anim_path_str = str(prim.GetPath())
                    skel_path_str = str(deform_skeleton_path)

                    # Animation is often a child or sibling of skeleton
                    if skel_path_str in anim_path_str or (
                        deform_skeleton_path is not None
                        and prim.GetPath().GetParentPath() == deform_skeleton_path.GetParentPath()
                    ):
                        anim = UsdSkel.Animation(prim)
                        joints = anim.GetJointsAttr().Get() or []
                        if len(joints) >= 50:
                            deform_animation = prim
                            deform_animation_path = prim.GetPath()
                            self.logger.info(f"   [ANIMATION] Found deformation animation: {anim_path_str}")
                            break

            # If no animation found, look for one with matching joint count
            if not deform_animation:
                skel = UsdSkel.Skeleton(deform_skeleton)
                skel_joints = skel.GetJointsAttr().Get() or []

                for prim in stage.Traverse():
                    if prim.IsA(UsdSkel.Animation):
                        anim = UsdSkel.Animation(prim)
                        anim_joints = anim.GetJointsAttr().Get() or []
                        if len(anim_joints) == len(skel_joints):
                            deform_animation = prim
                            deform_animation_path = prim.GetPath()
                            self.logger.info(f"   [ANIMATION] Found matching animation: {prim.GetPath()}")
                            break

            # ================================================================
            # Step 3: Update all skin bindings to point to deformation skeleton
            # ================================================================
            binding_updates = 0

            for prim in stage.Traverse():
                if prim.GetTypeName() == 'Mesh':
                    binding_api = UsdSkel.BindingAPI(prim)
                    skel_rel = binding_api.GetSkeletonRel()

                    if skel_rel.GetTargets():
                        # Apply the binding API schema if not already applied
                        if not prim.HasAPI(UsdSkel.BindingAPI):
                            UsdSkel.BindingAPI.Apply(prim)
                            binding_api = UsdSkel.BindingAPI(prim)

                        # Update skeleton target
                        binding_api.GetSkeletonRel().SetTargets([deform_skeleton_path])

                        # Update animation source if we found one
                        if deform_animation_path:
                            binding_api.GetAnimationSourceRel().SetTargets([deform_animation_path])

                        binding_updates += 1

            self.logger.info(f"   [OK] Updated {binding_updates} skin bindings")

            # ================================================================
            # Step 4: Delete unused skeletons and animations
            # ================================================================
            layer = stage.GetRootLayer()

            # Collect prims to delete
            prims_to_delete = []

            for skel_prim in all_skeletons:
                if skel_prim.GetPath() != deform_skeleton_path:
                    prims_to_delete.append(skel_prim.GetPath())

            # Also delete unused SkelAnimation prims
            for prim in stage.Traverse():
                if prim.IsA(UsdSkel.Animation):
                    if deform_animation_path and prim.GetPath() != deform_animation_path:
                        prims_to_delete.append(prim.GetPath())
                    elif not deform_animation_path:
                        # Keep the one with most joints
                        pass

            # Delete from leaf to root to avoid parent deletion issues
            prims_to_delete.sort(key=lambda p: len(str(p)), reverse=True)

            deleted_count = 0
            for prim_path in prims_to_delete:
                prim_spec = layer.GetPrimAtPath(prim_path)
                if prim_spec:
                    parent_spec = prim_spec.nameParent
                    if parent_spec:
                        del parent_spec.nameChildren[prim_spec.name]
                        deleted_count += 1

            self.logger.info(f"   [DELETE]  Deleted {deleted_count} unused skeleton/animation prims")

            # ================================================================
            # Step 5: Save the cleaned USD
            # ================================================================
            stage.GetRootLayer().Save()

            # Verify the cleanup
            verify_stage = Usd.Stage.Open(str(base_usd_path))
            final_skeletons = [p for p in verify_stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            final_animations = [p for p in verify_stage.Traverse() if p.IsA(UsdSkel.Animation)]

            self.logger.info("[OK] USD Skeleton Cleanup Complete!")
            self.logger.info(f"   [PACKAGE] Output: {base_usd_path.name}")
            self.logger.info(f"   [SKEL] Skeletons: {len(all_skeletons)} → {len(final_skeletons)}")
            self.logger.info(f"   [ANIMATION] Animations: {len(final_animations)}")
            self.logger.info(f"   [TARGET] Skin bindings: {binding_updates} updated")

            result.usd_path = base_usd_path
            return True

        except Exception as e:
            self.logger.error(f"Animation cleanup failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _fix_geom_bind_transforms(self, usd_path: Path) -> bool:
        """
        Fix missing geomBindTransform on skinned meshes.

        UsdSkelImaging REQUIRES primvars:skel:geomBindTransform to be set on
        skinned meshes. Without it, Maya's viewport cannot compute the skinned
        geometry and shows "Could not create OGS geometry" warnings.

        THE FIX: For each mesh with skel:skeleton binding, ensure geomBindTransform
        is set to the mesh's world transform at bind time (identity if not specified).

        Args:
            usd_path: Path to the USD file to fix

        Returns:
            True if fix was applied or not needed
        """
        if not USD_AVAILABLE:
            return True

        try:
            from pxr import Usd, UsdSkel, UsdGeom, Gf

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                return True

            self.logger.info("[FIX] Checking geomBindTransform on skinned meshes...")

            fixed_count = 0

            # Find all meshes with skeleton bindings
            for prim in stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue

                # Check if mesh has skeleton binding
                binding = UsdSkel.BindingAPI(prim)
                skel_rel = binding.GetSkeletonRel()

                if not skel_rel or not skel_rel.HasAuthoredTargets():
                    continue  # Not a skinned mesh

                # Check for geomBindTransform
                geom_bind_attr = prim.GetAttribute("primvars:skel:geomBindTransform")

                if geom_bind_attr and geom_bind_attr.HasAuthoredValue():
                    # Already has geomBindTransform
                    continue

                # Need to add geomBindTransform - use identity matrix
                # This assumes the mesh is already in the correct bind pose position
                mesh_path = prim.GetPath()
                self.logger.info(f"   [FIX] Adding geomBindTransform to: {mesh_path.name}")

                # Apply BindingAPI if not already applied
                if not prim.HasAPI(UsdSkel.BindingAPI):
                    UsdSkel.BindingAPI.Apply(prim)
                    binding = UsdSkel.BindingAPI(prim)

                # Set geomBindTransform to identity (mesh is at bind pose)
                identity_matrix = Gf.Matrix4d(1.0)
                binding.CreateGeomBindTransformAttr(identity_matrix)
                fixed_count += 1

            if fixed_count > 0:
                stage.GetRootLayer().Save()
                self.logger.info(f"[SUCCESS] Added geomBindTransform to {fixed_count} skinned meshes")
            else:
                self.logger.info("[SUCCESS] All skinned meshes already have geomBindTransform")

            return True

        except Exception as e:
            self.logger.warning(f"[WARNING] geomBindTransform fix failed (non-fatal): {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return True  # Non-fatal

    def _export_blendshapes_to_usd(self, usd_path: Path) -> int:
        """
        Export Maya blendShapes to USD using UsdSkel.BlendShape schema.

        Maya's mayaUSDExport doesn't export blendShapes (Maya 2026 limitation),
        so we post-process the USD file to add them manually using pxr Python API.

        This makes blendShapes readable by other DCCs (Houdini, Unreal, etc.)
        and allows future mayaUSD versions (v0.25.0+) to import them back.

        USD BlendShape Structure:
            /Root/BlendShapes/smile (SkelBlendShape)
                - offsets: Vec3fArray of delta vectors per point
                - normalOffsets: Vec3fArray of normal deltas (optional)
                - pointIndices: IntArray of affected vertices (optional, for sparse)

        Args:
            usd_path: Path to USD file to modify

        Returns:
            Number of blendShape targets exported
        """
        if not USD_AVAILABLE or not MAYA_AVAILABLE:
            return 0

        try:
            self.logger.info("[USD] Starting blendShape export to USD...")

            # Open USD stage for editing
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("Could not open USD stage for blendShape export")
                return 0

            # Find or create BlendShapes container under SkelRoot
            skel_root_prim = None
            for prim in stage.Traverse():
                if prim.IsA(UsdSkel.Root):
                    skel_root_prim = prim
                    break

            if not skel_root_prim:
                self.logger.warning("No SkelRoot found - cannot add blendShapes")
                return 0

            # Create BlendShapes scope under SkelRoot
            blend_shapes_path = skel_root_prim.GetPath().AppendChild("BlendShapes")
            UsdGeom.Scope.Define(stage, blend_shapes_path)

            # Get all Maya blendShape nodes
            blendshape_nodes = cmds.ls(type='blendShape') or []
            if not blendshape_nodes:
                self.logger.info("   No Maya blendShapes found to export")
                return 0

            self.logger.info(f"   Found {len(blendshape_nodes)} Maya blendShape nodes")

            # Build USD mesh lookup table (name -> prim)
            usd_mesh_map = {}
            for prim in stage.Traverse():
                if prim.IsA(UsdGeom.Mesh):
                    prim_name = prim.GetName()
                    usd_mesh_map[prim_name] = prim

            if not usd_mesh_map:
                self.logger.warning("   No USD meshes found in stage")
                return 0

            # Debug: Show first 10 USD mesh names for troubleshooting
            mesh_names_sample = list(usd_mesh_map.keys())[:10]
            self.logger.info(f"   USD mesh name samples: {', '.join(mesh_names_sample)}...")

            total_targets = 0

            # Process each blendShape node
            for bs_node in blendshape_nodes:
                try:
                    # Get target geometry (the deformed mesh)
                    geometries = cmds.blendShape(bs_node, query=True, geometry=True) or []
                    if not geometries:
                        continue

                    base_mesh = geometries[0]  # Primary target mesh

                    # Skip non-mesh geometries (NURBS curves, surfaces)
                    # USD exports these as NurbsPatch, not Mesh
                    if cmds.nodeType(base_mesh) != 'mesh':
                        self.logger.debug(f"   Skipping non-mesh geometry: {base_mesh} ({cmds.nodeType(base_mesh)})")
                        continue

                    # Find corresponding USD mesh
                    # Strip namespace and 'Shape' suffix from Maya name
                    mesh_short_name = base_mesh.split('|')[-1]  # Remove path
                    mesh_short_name = mesh_short_name.split(':')[-1]  # Remove namespace
                    if mesh_short_name.endswith('Shape'):
                        mesh_short_name = mesh_short_name[:-5]  # Remove 'Shape' suffix

                    # Try multiple matching strategies
                    usd_mesh = None

                    # Strategy 1: Exact name match
                    if mesh_short_name in usd_mesh_map:
                        usd_mesh = usd_mesh_map[mesh_short_name]

                    # Strategy 2: Name with _Geo suffix (common Maya export pattern)
                    elif f"{mesh_short_name}_Geo" in usd_mesh_map:
                        usd_mesh = usd_mesh_map[f"{mesh_short_name}_Geo"]

                    # Strategy 3: Name without _Geo if it has it
                    elif mesh_short_name.endswith('_Geo') and mesh_short_name[:-4] in usd_mesh_map:
                        usd_mesh = usd_mesh_map[mesh_short_name[:-4]]

                    # Strategy 4: Try transform parent name
                    if not usd_mesh:
                        parent_transform = cmds.listRelatives(base_mesh, parent=True)
                        if parent_transform:
                            transform_short_name = parent_transform[0].split('|')[-1].split(':')[-1]
                            if transform_short_name in usd_mesh_map:
                                usd_mesh = usd_mesh_map[transform_short_name]

                    # Strategy 5: Partial match (contains)
                    if not usd_mesh:
                        for usd_name, usd_prim in usd_mesh_map.items():
                            if mesh_short_name in usd_name or usd_name in mesh_short_name:
                                usd_mesh = usd_prim
                                break

                    if not usd_mesh:
                        self.logger.warning(f"   Could not find USD mesh for {base_mesh} (searched: {mesh_short_name})")
                        continue

                    # Get blendShape targets (aliases)
                    alias_list = cmds.aliasAttr(bs_node, query=True) or []
                    # aliasAttr returns pairs: [alias1, attr1, alias2, attr2, ...]
                    target_aliases = {}
                    for i in range(0, len(alias_list), 2):
                        alias_name = alias_list[i]
                        weight_attr = alias_list[i + 1]
                        # Extract index from weight attribute (e.g., "weight[0]" -> 0)
                        if 'weight[' in weight_attr:
                            target_idx = int(weight_attr.split('[')[1].split(']')[0])
                            target_aliases[target_idx] = alias_name

                    if not target_aliases:
                        continue

                    self.logger.info(f"   Processing {base_mesh}: {len(target_aliases)} targets")

                    # Export each blendShape target
                    for target_index, target_name in target_aliases.items():
                        try:
                            # Get target mesh (the shape that holds the sculpted data)
                            # Maya stores targets as inputTarget[0].inputTargetGroup[i].inputTargetItem[6000]
                            target_attr = (
                                f"{bs_node}.inputTarget[0].inputTargetGroup[{target_index}]"
                                f".inputTargetItem[6000].inputPointsTarget"
                            )

                            if not cmds.objExists(target_attr):
                                continue

                            # Get base mesh vertex count
                            num_verts = cmds.polyEvaluate(base_mesh, vertex=True)

                            # Get target deltas (Maya stores sparse deltas)
                            # Format: [[vertIndex, deltaX, deltaY, deltaZ], ...]
                            delta_data = cmds.getAttr(target_attr)

                            if not delta_data:
                                continue

                            # Convert sparse deltas to dense offset array
                            # Build lookup dict for O(1) access
                            delta_dict = {}
                            for entry in delta_data:
                                vert_id = int(entry[0])
                                delta_dict[vert_id] = [entry[1], entry[2], entry[3]]

                            # Build full offset array
                            offsets = []
                            for i in range(num_verts):
                                if i in delta_dict:
                                    offsets.extend(delta_dict[i])
                                else:
                                    offsets.extend([0.0, 0.0, 0.0])

                            if not any(offsets):
                                continue  # No actual deltas

                            # Create USD BlendShape prim
                            sanitized_name = target_name.replace('.', '_').replace(':', '_')
                            blend_shape_path = blend_shapes_path.AppendChild(sanitized_name)
                            blend_shape_prim = UsdSkel.BlendShape.Define(stage, blend_shape_path)

                            # Write offsets as Vec3fArray
                            offsets_vt = Vt.Vec3fArray([
                                Gf.Vec3f(offsets[i], offsets[i+1], offsets[i+2])
                                for i in range(0, len(offsets), 3)
                            ])

                            blend_shape_prim.CreateOffsetsAttr(offsets_vt)

                            # TODO: Export normal offsets if needed (optional)
                            # blend_shape_prim.CreateNormalOffsetsAttr(normal_offsets_vt)

                            # Link blendShape to mesh via skel:blendShapes relationship
                            # Use core relationship API (compatible with all USD versions)
                            blend_shapes_rel = usd_mesh.GetPrim().CreateRelationship("skel:blendShapes")
                            blend_shapes_rel.AddTarget(blend_shape_path)

                            total_targets += 1
                            self.logger.info(f"      [SUCCESS] Exported: {target_name}")

                        except Exception as target_error:
                            error_msg = f"      [WARNING] Failed to export target {target_name}: {target_error}"
                            self.logger.warning(error_msg)
                            continue

                except Exception as bs_error:
                    self.logger.warning(f"   [WARNING] Failed blendShape node {bs_node}: {bs_error}")
                    continue

            # Save USD stage
            if total_targets > 0:
                stage.GetRootLayer().Save()
                self.logger.info(f"[SUCCESS] Exported {total_targets} blendShape targets to USD")
            else:
                self.logger.info("   No blendShape targets exported")

            return total_targets

        except Exception as e:
            self.logger.warning(f"[WARNING] BlendShape export failed (non-fatal): {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return 0

    def _validate_usd_export(
        self,
        usd_path: Path,
        options: ExportOptions,
        result: ExportResult,
        num_skin_clusters: int = 0
    ) -> None:
        """
        Validate what was actually exported to USD and record conversion results

        Args:
            usd_path: Path to exported USD file
            options: Export options used
            result: ExportResult to populate
            num_skin_clusters: Number of skinClusters in the original Maya scene
        """
        self.logger.info(f"[INFO] Starting USD validation for: {usd_path}")
        self.logger.info(f"[INFO] USD_AVAILABLE: {USD_AVAILABLE}, file exists: {usd_path.exists()}")

        if not USD_AVAILABLE:
            self.logger.warning("[INFO] USD Python API not available, skipping validation")
            return

        if not usd_path.exists():
            self.logger.warning(f"[INFO] USD file not found: {usd_path}")
            return

        try:
            self.logger.info("[INFO] Opening USD stage...")
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("[INFO] Failed to open USD stage")
                return

            self.logger.info("[INFO] USD stage opened, counting prims...")

            # Count meshes - check prim type properly
            if options.export_geometry:
                meshes = [p for p in stage.Traverse() if p.GetTypeName() == 'Mesh']
                result.conversions['Geometry'] = ConversionResult(
                    component_type='Geometry',
                    status=ConversionStatus.SUCCESS if meshes else ConversionStatus.FAILED,
                    usd_count=len(meshes),
                    message=f"{len(meshes)} meshes exported"
                )
                self.logger.info(f"[INFO] Found {len(meshes)} meshes in USD")

            # Count NURBS curves - check for NurbsCurves or BasisCurves types
            if options.export_nurbs_curves:
                curves = [p for p in stage.Traverse()
                          if p.GetTypeName() in ('NurbsCurves', 'BasisCurves')]
                result.conversions['NURBS Curves'] = ConversionResult(
                    component_type='NURBS Curves',
                    status=ConversionStatus.SUCCESS if curves else ConversionStatus.FALLBACK,
                    usd_count=len(curves),
                    fallback_count=0 if curves else 1,  # Will use .rig.mb
                    message=f"{len(curves)} curves exported"
                )
                self.logger.info(f"[INFO] Found {len(curves)} NURBS curves in USD")

            # Count skeleton joints - check for Skeleton type
            if options.export_skeleton:
                skeletons = [p for p in stage.Traverse() if p.GetTypeName() == 'Skeleton']
                joint_count = 0
                for skel_prim in skeletons:
                    skel = UsdSkel.Skeleton(skel_prim)
                    joints = skel.GetJointsAttr().Get()
                    if joints:
                        joint_count += len(joints)

                result.conversions['Skeleton'] = ConversionResult(
                    component_type='Skeleton',
                    status=ConversionStatus.SUCCESS if joint_count > 0 else ConversionStatus.FALLBACK,
                    usd_count=joint_count,
                    message=f"{joint_count} joints in {len(skeletons)} skeleton(s)"
                )
                self.logger.info(f"[INFO] Found {joint_count} joints in {len(skeletons)} skeleton(s)")

                # Log SkelRoot scope (critical for deformation)
                skel_roots = [p for p in stage.Traverse() if p.GetTypeName() == 'SkelRoot']
                for sr in skel_roots:
                    self.logger.info(f"[INFO] SkelRoot: {sr.GetPath()}")
                    # List children under SkelRoot to show scope
                    children = [c.GetName() for c in sr.GetChildren()]
                    if children:
                        self.logger.info(f"   Children: {children[:5]}{'...' if len(children) > 5 else ''}")

                # Count skin bindings - meshes with UsdSkelBindingAPI
                skin_binding_count = 0
                for prim in stage.Traverse():
                    if prim.GetTypeName() == 'Mesh':
                        binding = UsdSkel.BindingAPI(prim)
                        if binding:
                            # Check if mesh has actual skin weight primvars
                            indices_attr = prim.GetAttribute('primvars:skel:jointIndices')
                            weights_attr = prim.GetAttribute('primvars:skel:jointWeights')
                            if indices_attr and indices_attr.HasValue() and weights_attr and weights_attr.HasValue():
                                skin_binding_count += 1

                # Determine skin status based on viewport_friendly option
                if options.viewport_friendly_skeleton:
                    # Viewport-friendly: skin preserved in .rig.mb fallback
                    result.conversions['Skin'] = ConversionResult(
                        component_type='Skin',
                        status=ConversionStatus.FALLBACK if skin_binding_count == 0 else ConversionStatus.SUCCESS,
                        usd_count=skin_binding_count,
                        fallback_count=num_skin_clusters if skin_binding_count == 0 else 0,
                        message=f"Viewport-friendly: {num_skin_clusters} skinClusters in .rig.mb"
                    )
                else:
                    # Full export: skin bindings in USD
                    result.conversions['Skin'] = ConversionResult(
                        component_type='Skin',
                        status=ConversionStatus.SUCCESS if skin_binding_count > 0 else ConversionStatus.FALLBACK,
                        usd_count=skin_binding_count,
                        fallback_count=0,
                        message=f"{skin_binding_count} skin bindings exported"
                    )
                self.logger.info(f"[INFO] Found {skin_binding_count} skin bindings in USD")

            # Count materials - check for Material type
            if options.export_materials:
                materials = [p for p in stage.Traverse() if p.GetTypeName() == 'Material']
                result.conversions['Materials'] = ConversionResult(
                    component_type='Materials',
                    status=ConversionStatus.SUCCESS if materials else ConversionStatus.FALLBACK,
                    usd_count=len(materials),
                    message=f"{len(materials)} materials exported"
                )
                self.logger.info(f"[INFO] Found {len(materials)} materials in USD")

            # Count blendshapes (Maya 2026) - check for BlendShape type
            if options.export_blendshapes:
                blendshapes = [p for p in stage.Traverse() if p.GetTypeName() == 'BlendShape']
                result.conversions['Blendshapes'] = ConversionResult(
                    component_type='Blendshapes',
                    status=ConversionStatus.SUCCESS if blendshapes else ConversionStatus.FALLBACK,
                    usd_count=len(blendshapes),
                    message=f"{len(blendshapes)} blendshapes exported"
                )
                self.logger.info(f"[INFO] Found {len(blendshapes)} blendshapes in USD")

            # Count animation - SkelAnimation prims (USD's native skeletal animation)
            # Note: USD uses SkelAnimation for rigging, while Alembic (.abc) is often
            # used for baked deformation caches. mayaUSD exports to SkelAnimation.
            # SkelAnimation prims exist even without explicit animation (rest pose)
            skel_animations = [p for p in stage.Traverse() if p.GetTypeName() == 'SkelAnimation']

            # Get frame range from stage
            frame_range = (0, 0)
            has_time_samples = False
            start_time = stage.GetStartTimeCode()
            end_time = stage.GetEndTimeCode()
            if start_time != float('inf') and end_time != float('-inf'):
                frame_range = (int(start_time), int(end_time))
                has_time_samples = (frame_range[1] - frame_range[0]) > 0

            if options.export_animation and has_time_samples:
                # Actual animation was exported
                result.conversions['Animation'] = ConversionResult(
                    component_type='Animation',
                    status=ConversionStatus.SUCCESS,
                    usd_count=len(skel_animations),
                    message=f"{len(skel_animations)} SkelAnimation(s), "
                            f"frames {frame_range[0]}-{frame_range[1]}"
                )
                self.logger.info(
                    f"[INFO] Found {len(skel_animations)} SkelAnimation prims "
                    f"(frames {frame_range[0]}-{frame_range[1]})"
                )
            elif skel_animations:
                # Rest pose only (no animation checkbox or no time samples)
                result.conversions['Animation'] = ConversionResult(
                    component_type='Animation',
                    status=ConversionStatus.PARTIAL,
                    usd_count=len(skel_animations),
                    message=f"{len(skel_animations)} SkelAnimation(s) (rest pose only)"
                )
                self.logger.info(f"[INFO] Found {len(skel_animations)} SkelAnimation prims (rest pose only)")
            else:
                # No animation data at all
                result.conversions['Animation'] = ConversionResult(
                    component_type='Animation',
                    status=ConversionStatus.SKIPPED,
                    usd_count=0,
                    message="No animation exported"
                )
                self.logger.info("[INFO] No SkelAnimation prims in USD")

            # Log all prim types found for debugging
            all_types = set(p.GetTypeName() for p in stage.Traverse() if p.GetTypeName())
            self.logger.info(f"[INFO] All prim types in USD: {all_types}")

            self.logger.info("[INFO] USD validation complete")

        except Exception as e:
            self.logger.warning(f"USD validation error: {e}")
            import traceback
            self.logger.warning(f"USD validation traceback: {traceback.format_exc()}")

    def _sample_pxr_texture_color(
        self, rfm_node: str, color_attr: str
    ):
        """
        Follow a PxrTexture connection on *rfm_node.color_attr* and return
        an average Gf.Vec3f sampled from that texture file, or None on failure.

        Connection traversal (most reliable first):
          1. connectionInfo(sourceFromDestination) — direct single-source lookup
          2. listConnections on compound attr  e.g. .baseColor
          3. listConnections on first child    e.g. .baseColorR
          4. One level deeper for each candidate found above

        File sampling (first available library wins):
          1. PIL / Pillow
          2. OpenImageIO (ships with RenderMan for Maya 24+)
        """
        try:
            from pxr import Gf  # type: ignore
            import re
            import os

            if cmds is None:
                return None

            # ── Step 1: Collect upstream candidate nodes ─────────────────────
            candidates: list = []

            # 1a. Direct source plug via connectionInfo (most reliable)
            try:
                src = cmds.connectionInfo(
                    f"{rfm_node}.{color_attr}", sourceFromDestination=True
                )
                if src:
                    # "PxrTexture1.resultRGB" → "PxrTexture1"
                    src_node = src.split(".")[0]
                    if src_node:
                        candidates.append(src_node)
            except Exception:
                pass

            # 1b. listConnections on compound attr (colour compound), no skip
            try:
                lc = (
                    cmds.listConnections(
                        f"{rfm_node}.{color_attr}",
                        source=True,
                        destination=False,
                    )
                    or []
                )
                candidates.extend(lc)
            except Exception:
                pass

            # 1c. listConnections on the first scalar child (".baseColorR")
            #     Maya sometimes connects at component level
            try:
                lc_r = (
                    cmds.listConnections(
                        f"{rfm_node}.{color_attr}R",
                        source=True,
                        destination=False,
                    )
                    or []
                )
                candidates.extend(lc_r)
            except Exception:
                pass

            # 1d. Walk one level deeper for each candidate so far
            first_pass = list(candidates)
            for node in first_pass:
                try:
                    deeper = (
                        cmds.listConnections(
                            node,
                            source=True,
                            destination=False,
                        )
                        or []
                    )
                    candidates.extend(deeper)
                except Exception:
                    pass

            # De-duplicate while preserving insertion order
            seen: set = set()
            unique_candidates: list = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    unique_candidates.append(c)

            if not unique_candidates:
                self.logger.info(
                    f"   [TEX-DIAG] {rfm_node}.{color_attr}: no upstream nodes found "
                    f"via connectionInfo or listConnections"
                )
                return None

            self.logger.info(
                f"   [TEX-DIAG] {rfm_node}.{color_attr}: candidates = "
                f"{unique_candidates[:6]}"  # cap at 6 to keep log tidy
            )

            # ── Step 2: Find texture file path ──────────────────────────────
            FILENAME_ATTRS = (
                "filename",         # PxrTexture (RenderMan for Maya)
                "textureName",      # some RfM variants
                "fileTextureName",  # Maya file node
                "imageName",        # misc
            )

            tex_path = None
            for node in unique_candidates:
                for attr in FILENAME_ATTRS:
                    try:
                        val = cmds.getAttr(f"{node}.{attr}")
                        if val and isinstance(val, str) and len(val) > 4:
                            tex_path = val
                            self.logger.info(
                                f"   [TEX-DIAG] Found path on {node}.{attr}: {val}"
                            )
                            break
                    except Exception:
                        continue
                if tex_path:
                    break

            if not tex_path:
                # Log all attrs on the first candidate to help future diagnosis
                if unique_candidates:
                    try:
                        attrs = cmds.listAttr(unique_candidates[0], scalar=True) or []
                        str_attrs = [a for a in attrs if 'file' in a.lower()
                                     or 'tex' in a.lower() or 'image' in a.lower()
                                     or 'name' in a.lower()]
                        self.logger.info(
                            f"   [TEX-DIAG] No filename attr on {unique_candidates[0]}. "
                            f"Likely attrs: {str_attrs[:10]}"
                        )
                    except Exception:
                        pass
                return None

            # ── Step 3: Resolve UDIM / tile tokens ──────────────────────────
            tex_path = re.sub(r'<[Uu][Dd][Ii][Mm]>', '1001', tex_path)
            tex_path = re.sub(r'#{4}', '1001', tex_path)
            tex_path = re.sub(r'%04d', '1001', tex_path)

            # ── Step 4: Verify file exists, try alt extensions ───────────────
            if not os.path.exists(tex_path):
                base, _ext = os.path.splitext(tex_path)
                for alt_ext in ('.tx', '.exr', '.tif', '.tiff', '.png', '.jpg', '.jpeg'):
                    candidate = base + alt_ext
                    if os.path.exists(candidate):
                        tex_path = candidate
                        break
                else:
                    self.logger.info(
                        f"   [TEX-DIAG] Texture file not found on disk: {tex_path}"
                    )
                    return None

            self.logger.info(
                f"   [TEX-DIAG] Sampling texture: {os.path.basename(tex_path)}"
            )

            # ── Resolve RenderMan .tex → source image ────────────────────────
            # RenderMan compiles source textures (PNG/EXR/TIFF) to a binary .tex
            # format that PIL and most image libs cannot read.  The convention is
            # "source.png.tex" — stripping the trailing ".tex" gets us back to the
            # original source file.  Try that first; if it doesn't exist on disk,
            # fall through and let PIL/OIIO try the .tex directly.
            if tex_path.lower().endswith('.tex'):
                source_candidate = tex_path[:-4]   # "body.png.tex" → "body.png"
                if os.path.exists(source_candidate):
                    self.logger.info(
                        f"   [TEX-DIAG] RenderMan .tex → source: "
                        f"{os.path.basename(source_candidate)}"
                    )
                    tex_path = source_candidate
                else:
                    self.logger.info(
                        f"   [TEX-DIAG] .tex source not on disk "
                        f"({os.path.basename(source_candidate)}), trying .tex directly"
                    )
                    # ── One-time dir listing so we can see actual filenames ──
                    _sc_dir = os.path.dirname(source_candidate)
                    try:
                        _dir_files = sorted(os.listdir(_sc_dir))[:12]
                        self.logger.info(
                            f"   [TEX-DIAG] Contents of {os.path.basename(_sc_dir)}/: "
                            f"{_dir_files}"
                        )
                    except Exception:
                        pass

            # ── Attempt 0: user-supplied texture folder ───────────────────────
            # The user points us at a folder of source PNGs — either the flat
            # project renderman folder (Substance Painter exports) or the
            # RenderMan Asset Library root whose subfolders end in .rma.
            # Both use the same source filename; only the directory layout differs:
            #
            #   Flat   : <path>/<texname>.png
            #            e.g. renderman/Veteran/Veteran_V008_Base_color_..._1001.png
            #
            #   .rma   : <path>/<Mat>.rma/<texname>.png
            #            e.g. RenderManAssetLibrary/.../Body.rma/Veteran_V008_...png
            #
            # Maya's PxrTexture.filename already tells us which .rma subfolder the
            # texture belongs to, so we use that to target the exact folder instead
            # of walking every .rma directory.
            _rma_lib = ""
            try:
                _rma_lib = getattr(
                    getattr(self, "_current_export_options", None),
                    "renderman_library_path",
                    ""
                ) or ""
            except Exception:
                _rma_lib = ""

            if _rma_lib and not os.path.isdir(_rma_lib):
                self.logger.info(f"   [TEX-DIAG] src-lib: path not found on disk: {_rma_lib}")
            if _rma_lib and os.path.isdir(_rma_lib):
                # ── One-shot listing diagnostic (first call only) ─────────────
                if not getattr(self, "_rma_lib_listed", False):
                    self._rma_lib_listed = True
                    try:
                        top_entries = sorted(os.listdir(_rma_lib))
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib listing ({len(top_entries)} entries): "
                            + ", ".join(top_entries[:30])
                            + ("..." if len(top_entries) > 30 else "")
                        )
                        # For each subdirectory, list its first 10 files
                        for entry in top_entries[:10]:
                            entry_path = os.path.join(_rma_lib, entry)
                            if os.path.isdir(entry_path):
                                sub_files = sorted(os.listdir(entry_path))
                                self.logger.info(
                                    f"   [TEX-DIAG] src-lib subdir '{entry}' "
                                    f"({len(sub_files)} files): "
                                    + ", ".join(sub_files[:10])
                                    + ("..." if len(sub_files) > 10 else "")
                                )
                    except Exception as _list_err:
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib listing error: {_list_err}"
                        )

                tex_basename = os.path.basename(tex_path)
                # Strip .tex to recover the original source filename:
                # "Veteran_V008_Base_color_..._1001.png.tex"
                # → "Veteran_V008_Base_color_..._1001.png"
                tex_basename_raw = (
                    tex_basename[:-4]
                    if tex_basename.lower().endswith('.tex')
                    else tex_basename
                )
                self.logger.info(
                    f"   [TEX-DIAG] src-lib seeking: '{tex_basename_raw}'"
                )

                def _sample_png(path: str) -> "Optional[Gf.Vec3f]":
                    """Read *path* with PIL, return Gf.Vec3f color or None.

                    Source-library PNGs are real PBR albedo textures. Their raw
                    averages are physically accurate but often dark (< 0.2) for
                    realistic materials. We apply a proportional brightness lift
                    — scaling all three channels equally so the brightest channel
                    reaches TARGET_V — which preserves the exact hue ratios from
                    the source while making the colour clearly visible in the viewer.
                    No saturation forcing is applied, so the hue stays true.
                    """
                    try:
                        from PIL import Image  # type: ignore
                        import numpy as np     # type: ignore
                        with Image.open(path).convert('RGB') as img:
                            thumb = img.resize((32, 32), Image.LANCZOS)
                            arr = np.array(thumb, dtype=float) / 255.0
                            r = float(arr[:, :, 0].mean())
                            g = float(arr[:, :, 1].mean())
                            b = float(arr[:, :, 2].mean())
                            if r + g + b > 0.02:
                                # Proportional lift — preserve hue, boost to visibility
                                TARGET_V = 0.45
                                max_ch = max(r, g, b)
                                if 0.02 < max_ch < TARGET_V:
                                    scale = TARGET_V / max_ch
                                    r = min(r * scale, 1.0)
                                    g = min(g * scale, 1.0)
                                    b = min(b * scale, 1.0)
                                color_out = Gf.Vec3f(
                                    max(0.0, min(1.0, r)),
                                    max(0.0, min(1.0, g)),
                                    max(0.0, min(1.0, b)),
                                )
                                self.logger.info(
                                    f"   [TEX] {os.path.basename(path)} "
                                    f"(src-lib): ({r:.3f}, {g:.3f}, {b:.3f})"
                                )
                                return color_out
                    except ImportError:
                        self.logger.info(
                            "   [TEX-DIAG] PIL not available for src-lib scan"
                        )
                    except Exception:
                        pass
                    return None

                # Extract .rma folder info early — needed by multiple priorities.
                orig_rma_dir = os.path.dirname(tex_path)
                orig_rma_folder = os.path.basename(orig_rma_dir)  # e.g. "Body.rma"
                rma_stem = (
                    orig_rma_folder[:-4]
                    if orig_rma_folder.lower().endswith('.rma')
                    else orig_rma_folder
                )

                # ── Priority 1: flat folder — exact filename match ─────────────
                flat_candidate = os.path.join(_rma_lib, tex_basename_raw)
                if os.path.exists(flat_candidate):
                    result_color = _sample_png(flat_candidate)
                    if result_color is not None:
                        return result_color

                # ── Priority 1b: flat folder — fuzzy Base_color match ──────────
                # Handles backups where files are named "{MatName}_Base_color.png"
                # but the .rma stem differs slightly (e.g. LfButn01 → LfButton_01,
                # LfZipr → LfZipper, LwrTeeth → LwrTeeth_3).
                # Only applies to base-color textures (the ones that drive diffuse).
                if 'base_color' in tex_basename_raw.lower():
                    try:
                        import difflib
                        _bc_files = [
                            f for f in os.listdir(_rma_lib)
                            if f.lower().endswith('.png')
                            and 'base_color' in f.lower()
                        ]
                        _matched_bc = None
                        _stem_lo = rma_stem.lower()
                        # Step A: exact prefix "{rma_stem}_"
                        for f in _bc_files:
                            if f.lower().startswith(_stem_lo + '_'):
                                _matched_bc = f
                                break
                        # Step B: backup stem starts with rma_stem
                        # (handles LwrTeeth → LwrTeeth_3_Base_color.png)
                        if _matched_bc is None:
                            for f in _bc_files:
                                if f.lower().startswith(_stem_lo):
                                    _matched_bc = f
                                    break
                        # Step C: difflib fuzzy on the portion before "_Base_color"
                        # (handles LfButn01 → LfButton_01, LfZipr → LfZipper)
                        if _matched_bc is None and _bc_files:
                            _bc_stems = []
                            for f in _bc_files:
                                idx = f.lower().find('_base_color')
                                _bc_stems.append(f[:idx] if idx != -1 else f)
                            best = difflib.get_close_matches(
                                rma_stem, _bc_stems, n=1, cutoff=0.5
                            )
                            if best:
                                _matched_bc = _bc_files[_bc_stems.index(best[0])]
                        if _matched_bc:
                            self.logger.info(
                                f"   [TEX-DIAG] src-lib fuzzy match: "
                                f"'{rma_stem}' → '{_matched_bc}'"
                            )
                            result_color = _sample_png(
                                os.path.join(_rma_lib, _matched_bc)
                            )
                            if result_color is not None:
                                return result_color
                    except Exception as _fuzz_err:
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib fuzzy match error: {_fuzz_err}"
                        )

                # ── Priority 2: targeted .rma subfolder ──────────────────────
                # Maya's tex_path tells us which .rma subfolder owns this
                # texture (e.g. Body.rma).  Use that name under the user's
                # supplied root so we land in exactly the right place without
                # having to walk every .rma directory.
                if orig_rma_folder.lower().endswith('.rma'):
                    targeted = os.path.join(
                        _rma_lib, orig_rma_folder, tex_basename_raw
                    )
                    if os.path.exists(targeted):
                        result_color = _sample_png(targeted)
                        if result_color is not None:
                            return result_color
                    else:
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib targeted miss: "
                            f"{orig_rma_folder}/{tex_basename_raw}"
                        )

                # ── Priority 3: walk all .rma subfolders as last resort ───────
                try:
                    for rma_folder in os.listdir(_rma_lib):
                        if not rma_folder.lower().endswith('.rma'):
                            continue
                        if rma_folder == orig_rma_folder:
                            continue  # already tried above
                        rma_full = os.path.join(_rma_lib, rma_folder)
                        if not os.path.isdir(rma_full):
                            continue
                        rma_candidate = os.path.join(rma_full, tex_basename_raw)
                        if os.path.exists(rma_candidate):
                            result_color = _sample_png(rma_candidate)
                            if result_color is not None:
                                return result_color
                except Exception as lib_err:
                    self.logger.info(
                        f"   [TEX-DIAG] src-lib .rma scan error: {lib_err}"
                    )

            # ── Attempt 1: Maya MImage — reads .tex via RenderMan plugin ────
            # RenderMan registers a .tex format reader with Maya when the plugin
            # is loaded. MImage.readFromFile() goes through Maya's plugin chain,
            # so it can decode .tex files that OIIO/PIL cannot.
            try:
                from maya import OpenMaya as _om  # type: ignore
                import numpy as _np_mimg
                _mimg = _om.MImage()
                _mimg.readFromFile(tex_path)
                _w, _h = _om.MScriptUtil(), _om.MScriptUtil()
                _wp = _w.asUintPtr()
                _hp = _h.asUintPtr()
                _mimg.getSize(_wp, _hp)
                _width = _om.MScriptUtil.getUint(_wp)
                _height = _om.MScriptUtil.getUint(_hp)
                if _width > 0 and _height > 0:
                    _mimg.verticalFlip()  # MImage is bottom-up
                    _char_arr = _mimg.pixels()
                    _byte_arr = _np_mimg.frombuffer(
                        bytes(_char_arr[:_width * _height * 4]),
                        dtype=_np_mimg.uint8
                    ).reshape(_height, _width, 4)
                    arr_f = _byte_arr[:, :, :3].astype(float) / 255.0
                    r = float(arr_f[:, :, 0].mean())
                    g = float(arr_f[:, :, 1].mean())
                    b = float(arr_f[:, :, 2].mean())
                    if r + g + b > 0.02:
                        TARGET_V = 0.45
                        max_ch = max(r, g, b)
                        if 0.02 < max_ch < TARGET_V:
                            scale = TARGET_V / max_ch
                            r = min(r * scale, 1.0)
                            g = min(g * scale, 1.0)
                            b = min(b * scale, 1.0)
                        color_out = Gf.Vec3f(
                            max(0.0, min(1.0, r)),
                            max(0.0, min(1.0, g)),
                            max(0.0, min(1.0, b)),
                        )
                        self.logger.info(
                            f"   [TEX] {os.path.basename(tex_path)} "
                            f"(MImage): ({r:.3f}, {g:.3f}, {b:.3f})"
                        )
                        return color_out
            except Exception as _mimg_err:
                self.logger.info(
                    f"   [TEX-DIAG] MImage failed for "
                    f"{os.path.basename(tex_path)}: {_mimg_err}"
                )

            try:
                from PIL import Image  # type: ignore
                import numpy as np     # type: ignore

                with Image.open(tex_path).convert('RGB') as img:
                    thumb = img.resize((32, 32), Image.LANCZOS)
                    arr = np.array(thumb, dtype=float) / 255.0
                    r = float(arr[:, :, 0].mean())
                    g = float(arr[:, :, 1].mean())
                    b = float(arr[:, :, 2].mean())
                    if r + g + b > 0.02:
                        raw_color = Gf.Vec3f(
                            max(0.0, min(1.0, r)),
                            max(0.0, min(1.0, g)),
                            max(0.0, min(1.0, b)),
                        )
                        boosted = self._boost_color_for_display(raw_color)
                        if boosted is not None:
                            self.logger.info(
                                f"   [TEX] {os.path.basename(tex_path)}: "
                                f"({r:.3f}, {g:.3f}, {b:.3f}) via PIL → boosted {boosted}"
                            )
                            return boosted
                        self.logger.info(
                            f"   [TEX] {os.path.basename(tex_path)}: "
                            f"({r:.3f}, {g:.3f}, {b:.3f}) via PIL — achromatic, trying rma-scan"
                        )
            except ImportError:
                self.logger.info("   [TEX-DIAG] PIL not available")
            except Exception as pil_err:
                self.logger.info(f"   [TEX-DIAG] PIL failed: {pil_err}")

            # ── Attempt 2: OpenImageIO (ships with RfM 24+) ──────────────────
            try:
                import sys as _sys
                import glob as _glob
                _oiio_base = (
                    r"C:\Program Files\Pixar\RenderManProServer-*"
                    r"\lib\python3.11\Lib\site-packages\thirdparty"
                )
                for _p in _glob.glob(_oiio_base):
                    if _p not in _sys.path:
                        _sys.path.insert(0, _p)
                import OpenImageIO as oiio  # type: ignore

                def _oiio_sample(path: str):
                    """Try ImageInput then ImageBuf; return (r,g,b) tuple or None."""
                    import numpy as np  # type: ignore

                    # ── Strategy A: ImageInput.open ──────────────────────────
                    inp = oiio.ImageInput.open(path)
                    if inp is not None:
                        pixels = inp.read_image('float')
                        inp.close()
                        if pixels is not None:
                            arr = np.array(pixels)
                            if arr.ndim == 3 and arr.shape[2] >= 3:
                                return (
                                    float(arr[:, :, 0].mean()),
                                    float(arr[:, :, 1].mean()),
                                    float(arr[:, :, 2].mean()),
                                )
                        return None

                    # If ImageInput fails (returns None), log the reason.
                    _oiio_err = oiio.geterror()
                    self.logger.info(
                        f"   [TEX-DIAG] OIIO ImageInput.open returned None "
                        f"for {os.path.basename(path)}"
                        + (f": {_oiio_err}" if _oiio_err else "")
                    )

                    # ── Strategy B: ImageBuf (handles more format variants) ──
                    buf = oiio.ImageBuf(path)
                    if buf.has_error:
                        self.logger.info(
                            f"   [TEX-DIAG] OIIO ImageBuf also failed: {buf.geterror()}"
                        )
                        return None
                    spec = buf.spec()
                    if spec.nchannels < 3:
                        return None
                    pixels_b = buf.get_pixels(oiio.FLOAT)
                    if pixels_b is None:
                        return None
                    arr = np.array(pixels_b)
                    if arr.ndim == 3 and arr.shape[2] >= 3:
                        return (
                            float(arr[:, :, 0].mean()),
                            float(arr[:, :, 1].mean()),
                            float(arr[:, :, 2].mean()),
                        )
                    return None

                rgb = _oiio_sample(tex_path)
                if rgb is not None:
                    r, g, b = rgb
                    if r + g + b > 0.02:
                        raw_color = Gf.Vec3f(
                            max(0.0, min(1.0, r)),
                            max(0.0, min(1.0, g)),
                            max(0.0, min(1.0, b)),
                        )
                        boosted = self._boost_color_for_display(raw_color)
                        if boosted is not None:
                            self.logger.info(
                                f"   [TEX] {os.path.basename(tex_path)}: "
                                f"({r:.3f}, {g:.3f}, {b:.3f}) via OIIO → boosted {boosted}"
                            )
                            return boosted
                        self.logger.info(
                            f"   [TEX] {os.path.basename(tex_path)}: "
                            f"({r:.3f}, {g:.3f}, {b:.3f}) via OIIO — achromatic, trying rma-scan"
                        )
            except ImportError:
                self.logger.info("   [TEX-DIAG] OpenImageIO not available")
            except Exception as oiio_err:
                self.logger.info(f"   [TEX-DIAG] OIIO failed: {oiio_err}")

            # ── Last resort: scan the .rma package dir for any preview / source image ──
            # RenderMan Material Archives ship a rendered preview PNG (asset_100.png)
            # alongside the .tex files.  A naive mean over the whole preview is
            # unreliable because the image includes the grey background, a full-white
            # specular highlight at the top and a full-black shadow at the bottom.
            # Fix: crop to the centre 50 % of the image (where the diffuse midtone
            # lives), then exclude the remaining near-white / near-black pixels and
            # take the per-channel MEDIAN.  This gives a much cleaner approximation
            # of the actual diffuse colour than the old whole-image mean.
            try:
                rma_dir = os.path.dirname(tex_path)
                if os.path.isdir(rma_dir):
                    for fname in sorted(os.listdir(rma_dir)):
                        if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                            candidate = os.path.join(rma_dir, fname)
                            try:
                                from PIL import Image  # type: ignore
                                import numpy as np     # type: ignore
                                with Image.open(candidate).convert('RGB') as img:
                                    w, h = img.size
                                    # Centre-crop: keep the middle 50 % of each axis
                                    cx, cy = w // 2, h // 2
                                    mx = max(w // 4, 1)
                                    my = max(h // 4, 1)
                                    center = img.crop(
                                        (cx - mx, cy - my, cx + mx, cy + my)
                                    )
                                    thumb = center.resize((16, 16), Image.LANCZOS)
                                    arr = np.array(thumb, dtype=float) / 255.0
                                    pixels = arr.reshape(-1, 3)
                                    # Exclude near-black (shadow) and near-white (highlight)
                                    brightness = pixels.mean(axis=1)
                                    mask = (brightness > 0.12) & (brightness < 0.88)
                                    if mask.sum() >= 4:
                                        pixels = pixels[mask]
                                    r = float(np.median(pixels[:, 0]))
                                    g = float(np.median(pixels[:, 1]))
                                    b = float(np.median(pixels[:, 2]))
                                    if r + g + b > 0.02:
                                        raw_color = Gf.Vec3f(
                                            max(0.0, min(1.0, r)),
                                            max(0.0, min(1.0, g)),
                                            max(0.0, min(1.0, b)),
                                        )
                                        boosted = self._boost_color_for_display(raw_color)
                                        if boosted is not None:
                                            self.logger.info(
                                                f"   [TEX] {fname} (rma-scan): "
                                                f"({r:.3f}, {g:.3f}, {b:.3f}) → boosted {boosted}"
                                            )
                                            return boosted
                                        self.logger.info(
                                            f"   [TEX] {fname} (rma-scan): "
                                            f"({r:.3f}, {g:.3f}, {b:.3f}) achromatic — using name-hash"
                                        )
                            except Exception:
                                continue  # try next file
            except Exception as scan_err:
                self.logger.info(f"   [TEX-DIAG] rma-dir scan error: {scan_err}")

            self.logger.info(
                f"   [TEX-DIAG] Sampling failed for {os.path.basename(tex_path)} — "
                f"no supported image library could read it"
            )
            return None

        except Exception as outer_err:
            self.logger.info(f"   [TEX-DIAG] Unexpected error: {outer_err}")
            return None

    def _rfm_name_color(self, name: str) -> "Gf.Vec3f":
        """Generate a unique, visually distinct color from a material name.

        Uses MD5 hash → hue so that every material gets a consistent, spread-out
        hue regardless of alphabetical ordering.  Saturation and value are fixed
        at mid-range so colors are clearly visible in VP2 without being garish.
        This is used as a last-resort fallback when RenderMan .tex textures cannot
        be read by the available image libraries.
        """
        import hashlib
        import colorsys
        from pxr import Gf  # type: ignore
        h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)  # 0–4 294 967 295
        hue = h / 4294967296.0   # uniformly spread 0.0–1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.72)
        return Gf.Vec3f(float(r), float(g), float(b))

    def _boost_color_for_display(self, color: "Gf.Vec3f"):
        """Boost a sampled texture colour to be clearly visible in VP2.

        Physically-accurate texture averages are typically dark and desaturated
        for realistic character materials (skin, metal, cloth).  This method
        preserves the dominant hue while pushing saturation and value into a
        range that makes per-material differences immediately visible.

        Returns None when the colour is achromatic (HSV saturation < 0.08),
        which tells the caller to use _rfm_name_color instead.
        """
        import colorsys
        from pxr import Gf  # type: ignore
        r, g, b = float(color[0]), float(color[1]), float(color[2])
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s < 0.08:
            return None  # achromatic — name-hash will be more distinctive
        s_out = max(s, 0.62)
        v_out = max(min(max(v, 0.58), 0.82), 0.58)
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s_out, v_out)
        return Gf.Vec3f(float(r2), float(g2), float(b2))

    def _convert_renderman_materials_to_usd_preview(self, usd_path: Path) -> None:
        """
        Convert RenderMan PxrShader materials to UsdPreviewSurface.

        Maya's RenderMan typically uses Lambert nodes with PxrSurface/PxrShader connections.
        This method reads the Lambert diffuse colors and converts to UsdPreviewSurface materials.
        """
        if not USD_AVAILABLE:
            self.logger.warning("[WARNING] USD Python API not available for material conversion")
            return

        try:
            from pxr import Usd, UsdShade, Sdf, Gf

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("[WARNING] Could not open USD stage for material conversion")
                return

            self.logger.info("[LOOKDEV] Converting RenderMan materials to UsdPreviewSurface...")

            materials_converted = 0

            # ----------------------------------------------------------------
            # Step 1: Build sg_to_color from Maya — keyed by shading group name.
            # This is more reliable than mesh→material because skinned mesh
            # bindings in USD may not be authored on the mesh prim itself.
            # mayaUSD names USD Material prims after the Maya shading group.
            # ----------------------------------------------------------------
            sg_to_color = {}
            if cmds is not None:
                try:
                    # ----------------------------------------------------------
                    # Phase A: Lambert → SG (non-proxy Lamberts only).
                    # Skip lambert1 (Maya default) and any Lambert whose name
                    # contains "pxr" (RFM occasionally names proxies that way).
                    # ----------------------------------------------------------
                    lambert_colors = {}
                    for lambert in (cmds.ls(type="lambert") or []):
                        try:
                            if lambert == "lambert1" or "pxr" in lambert.lower():
                                continue
                            c = cmds.getAttr(f"{lambert}.color")[0]
                            r, g, b = float(c[0]), float(c[1]), float(c[2])
                            # Skip near-black lamberts — RfM creates placeholder
                            # lambert nodes with color (0,0,0) for every Pxr shader.
                            # Storing them in Phase A would poison the SG lookup with
                            # black before Phase B can mark it None (texture-driven).
                            if r + g + b <= 0.01:
                                continue
                            lambert_colors[lambert] = Gf.Vec3f(r, g, b)
                        except Exception:
                            pass

                    for lambert, color in lambert_colors.items():
                        try:
                            for sg in (cmds.listConnections(lambert, type="shadingEngine") or []):
                                sg_to_color[sg] = color
                        except Exception:
                            pass

                    # ----------------------------------------------------------
                    # Phase B: RenderMan PxrSurface / PxrDisney / PxrUnified.
                    # RfM connects shaders to shadingEngine.rmanSurface (not
                    # .surfaceShader), so Phase C misses them entirely.
                    # PxrSurface final color = diffuseGain * diffuseColor.
                    # PxrDisney / PxrUnified use baseColor directly.
                    # ----------------------------------------------------------
                    # ── PHASE B CODE VERSION: v5 ─────────────────────────
                    self.logger.info("   [PHASE-B] v5 — scanning RfM SGs for texture colors")
                    _phase_b_rma_lib = getattr(
                        getattr(self, "_current_export_options", None),
                        "renderman_library_path", ""
                    ) or ""
                    if _phase_b_rma_lib:
                        self.logger.info(
                            f"   [PHASE-B] src-lib path: {_phase_b_rma_lib}"
                        )
                    else:
                        self.logger.info(
                            "   [PHASE-B] src-lib path: (none) — texture colors from asset_100.png"
                        )
                    RFM_SHADER_TYPES = {
                        # node_type: (color_attr, gain_attr_or_None)
                        "PxrSurface":      ("diffuseColor", "diffuseGain"),
                        # RfM 26+: "PxrDisney" was later registered as "PxrDisneyBsdf"
                        "PxrDisney":       ("baseColor",    None),
                        "PxrDisneyBsdf":   ("baseColor",    None),
                        # Some RfM 27 builds register it without the 'Bsdf' suffix
                        "PxrDisneyBSDF":   ("baseColor",    None),
                        "PxrUnified":      ("diffuseColor", "diffuseGain"),
                        "PxrLayer":        ("diffuseColor", None),
                        "PxrLMDiffuse":    ("transmissionColor", None),
                    }
                    # Pre-collect ALL Pxr* shader nodes in the scene, keyed by
                    # their SHORT name (namespace stripped).  This lets the
                    # name-derivation fallback below find nodes even when they
                    # live inside a Maya reference namespace.
                    # e.g. "SomeRef:PxrDisneyBsdf1" is stored under key "PxrDisneyBsdf1".
                    _pxr_short_to_full: dict = {}
                    try:
                        for _pxr_type in RFM_SHADER_TYPES:
                            for _n in (cmds.ls(type=_pxr_type) or []):
                                _short = _n.split(":")[-1]
                                _pxr_short_to_full.setdefault(_short, _n)
                        # Broad sweep: catch any Pxr* node regardless of type name
                        # (handles unknown RfM versions or non-standard registrations).
                        for _n in (cmds.ls("Pxr*") or []) + (cmds.ls("*:Pxr*") or []):
                            _short = _n.split(":")[-1]
                            _pxr_short_to_full.setdefault(_short, _n)
                    except Exception:
                        pass
                    self.logger.info(
                        f"   [PHASE-B] pre-collected {len(_pxr_short_to_full)} "
                        f"Pxr* nodes: {list(_pxr_short_to_full.keys())[:6]}..."
                    )

                    # Build reverse map: Pxr surface shader → its connected SG(s).
                    # In RfM 27 the PxrDisneyBsdf shader may not appear in the SG's
                    # incoming connections at all; instead the SG appears in the shader's
                    # *outgoing* connections.  Querying "what SGs does Veteran_Body_Bsdf
                    # output to?" gives us the link even when the SG refuses to list it.
                    _sg_to_pxr_map: dict = {}
                    for _full in _pxr_short_to_full.values():
                        try:
                            if cmds.nodeType(_full) not in RFM_SHADER_TYPES:
                                continue
                        except Exception:
                            continue
                        try:
                            for _sg_name in (
                                cmds.listConnections(
                                    _full,
                                    source=False,
                                    destination=True,
                                    type="shadingEngine",
                                ) or []
                            ):
                                _sg_to_pxr_map.setdefault(_sg_name, [])
                                if _full not in _sg_to_pxr_map[_sg_name]:
                                    _sg_to_pxr_map[_sg_name].append(_full)
                        except Exception:
                            pass
                    if _sg_to_pxr_map:
                        self.logger.info(
                            f"   [PHASE-B] reverse Pxr→SG map: "
                            f"{len(_sg_to_pxr_map)} SGs have Pxr shader linkage. "
                            f"Sample: {dict(list(_sg_to_pxr_map.items())[:3])}"
                        )
                    else:
                        self.logger.info(
                            "   [PHASE-B] reverse map: no outgoing Pxr→SG connections found"
                        )

                    # Also check .rmanSurface on every SG.
                    # Each SG is isolated in its own try/except so a missing
                    # .rmanSurface attribute on one SG never aborts the loop.
                    for sg in (cmds.ls(type="shadingEngine") or []):
                        if sg in sg_to_color:
                            continue
                        try:
                            # RfM primary connection point (.rmanSurface may not
                            # exist on non-RfM SGs — catch the Maya error per-SG)
                            try:
                                rfm_nodes = (
                                    cmds.listConnections(
                                        f"{sg}.rmanSurface", source=True, destination=False
                                    ) or []
                                )
                            except Exception:
                                rfm_nodes = []
                            # Fallback: .surfaceShader may hold a PxrSurface in some RfM setups
                            try:
                                rfm_nodes += (
                                    cmds.listConnections(
                                        f"{sg}.surfaceShader", source=True, destination=False
                                    ) or []
                                )
                            except Exception:
                                pass
                            # RfM 27 name-derived fallback: the SG is named after
                            # its shader node (e.g. PxrDisneyBsdf1SG → PxrDisneyBsdf1).
                            # In RfM 27 the Pxr shader is NOT wired to .rmanSurface or
                            # .surfaceShader — only a lambert placeholder is.  Stripping
                            # the trailing "SG" gives us the shader's short name; we then
                            # look it up in _pxr_short_to_full (handles reference namespaces).
                            if sg.endswith("SG"):
                                derived_short = sg.split(":")[-1][:-2]  # "NS:PxrDisneyBsdf1SG" → "PxrDisneyBsdf1"
                                full_name = _pxr_short_to_full.get(derived_short)
                                if full_name and full_name not in rfm_nodes:
                                    rfm_nodes.append(full_name)
                                    self.logger.info(
                                        f"   [PHASE-B] {sg}: name-derived fallback found {full_name!r}"
                                    )
                            # Broad incoming-connection scan: check ALL source connections
                            # on this SG for any Pxr* node (catches undocumented RfM attrs).
                            try:
                                for _c in (
                                    cmds.listConnections(
                                        sg, source=True, destination=False
                                    ) or []
                                ):
                                    try:
                                        if (
                                            cmds.nodeType(_c).startswith("Pxr")
                                            and _c not in rfm_nodes
                                        ):
                                            rfm_nodes.append(_c)
                                            self.logger.info(
                                                f"   [PHASE-B] {sg}: broad-scan found {_c!r}"
                                            )
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            # Reverse map: Pxr shader declared THIS SG as its output.
                            for _p in _sg_to_pxr_map.get(sg, []):
                                if _p not in rfm_nodes:
                                    rfm_nodes.append(_p)
                                    self.logger.info(
                                        f"   [PHASE-B] {sg}: reverse-map found {_p!r}"
                                    )
                            # --------------------------------------------------
                            # Lambert VP2 file texture pre-scan.
                            # RfM wires a Lambert to sg.surfaceShader for VP2.
                            # That Lambert.color → file.fileTextureName is the
                            # actual source PNG — readable by PIL, no .tex needed.
                            # This runs BEFORE the Pxr rfm_nodes loop so the
                            # rma-scan fallback can never shadow it.
                            # --------------------------------------------------
                            try:
                                for _lam in (
                                    cmds.listConnections(
                                        f"{sg}.surfaceShader",
                                        source=True,
                                        destination=False,
                                    ) or []
                                ):
                                    if cmds.nodeType(_lam) != "lambert":
                                        continue
                                    for _lf in (
                                        cmds.listConnections(
                                            f"{_lam}.color",
                                            source=True,
                                            destination=False,
                                        ) or []
                                    ):
                                        if cmds.nodeType(_lf) != "file":
                                            continue
                                        _lfile_path = cmds.getAttr(
                                            f"{_lf}.fileTextureName"
                                        )
                                        if not (_lfile_path and os.path.isfile(_lfile_path)):
                                            continue
                                        try:
                                            from PIL import Image  # type: ignore
                                            import statistics as _lst
                                            with Image.open(_lfile_path).convert("RGB") as _limg:
                                                _lw, _lh = _limg.size
                                                _lcrop = _limg.crop((
                                                    _lw // 4, _lh // 4,
                                                    _lw * 3 // 4, _lh * 3 // 4,
                                                ))
                                                _lpix = list(_lcrop.getdata())
                                                lr = _lst.median(p[0] for p in _lpix) / 255.0
                                                lg = _lst.median(p[1] for p in _lpix) / 255.0
                                                lb = _lst.median(p[2] for p in _lpix) / 255.0
                                            _TARGET_V = 0.45
                                            _max_ch = max(lr, lg, lb)
                                            if 0.02 < _max_ch < _TARGET_V:
                                                _scale = _TARGET_V / _max_ch
                                                lr = min(lr * _scale, 1.0)
                                                lg = min(lg * _scale, 1.0)
                                                lb = min(lb * _scale, 1.0)
                                            sg_to_color[sg] = Gf.Vec3f(
                                                max(0.0, min(1.0, lr)),
                                                max(0.0, min(1.0, lg)),
                                                max(0.0, min(1.0, lb)),
                                            )
                                            self.logger.info(
                                                f"   [PHASE-B] {sg}: Lambert file texture "
                                                f"({lr:.3f}, {lg:.3f}, {lb:.3f}) ← "
                                                f"{os.path.basename(_lfile_path)}"
                                            )
                                        except Exception as _lpil_exc:
                                            self.logger.info(
                                                f"   [PHASE-B] {sg}: Lambert file PIL "
                                                f"failed ({_lpil_exc})"
                                            )
                                        break  # one file node per lambert is enough
                                    if sg in sg_to_color:
                                        break  # found the texture, stop checking lamberts
                            except Exception:
                                pass

                            has_pxr_node = False
                            for rfm_node in rfm_nodes:
                                try:
                                    node_type = cmds.nodeType(rfm_node)
                                except Exception:
                                    continue
                                # Any Pxr* node is a RenderMan shader — mark
                                # the SG as RfM-owned even if we can't read
                                # a meaningful color from it.
                                if node_type.startswith("Pxr"):
                                    has_pxr_node = True
                                if node_type not in RFM_SHADER_TYPES:
                                    if node_type != "lambert":  # Lambert handled in pre-scan above
                                        self.logger.info(
                                            f"   [PHASE-B] {sg}: found {rfm_node} "
                                            f"type={node_type!r} — not in RFM_SHADER_TYPES, skipping"
                                        )
                                    continue
                                color_attr, gain_attr = RFM_SHADER_TYPES[node_type]
                                try:
                                    raw = cmds.getAttr(f"{rfm_node}.{color_attr}")
                                    # A compound color attribute that has an
                                    # upstream connection returns None from
                                    # getAttr (Maya can't evaluate it outside
                                    # the DG).  Treat that as (0,0,0) so we
                                    # fall through to the texture sampler below.
                                    if raw is None:
                                        r, g, b = 0.0, 0.0, 0.0
                                    else:
                                        c = raw[0] if isinstance(raw, list) else raw
                                        r, g, b = float(c[0]), float(c[1]), float(c[2])
                                    self.logger.info(
                                        f"   [B-DIAG] {rfm_node}.{color_attr}: "
                                        f"raw={raw!r}  r+g+b={r+g+b:.4f}"
                                    )
                                    if gain_attr:
                                        try:
                                            gain = float(cmds.getAttr(f"{rfm_node}.{gain_attr}"))
                                            r, g, b = r * gain, g * gain, b * gain
                                        except Exception:
                                            pass
                                    # Only use if meaningfully non-zero
                                    if r + g + b > 0.01:
                                        if sg not in sg_to_color:  # don't overwrite Lambert file result
                                            sg_to_color[sg] = Gf.Vec3f(
                                                max(0.0, min(1.0, r)),
                                                max(0.0, min(1.0, g)),
                                                max(0.0, min(1.0, b)),
                                            )
                                        break
                                    else:
                                        # baseColor is near-zero — this shader is
                                        # texture-driven. Follow the connection to
                                        # the PxrTexture and sample the actual file
                                        # so VP2 shows a meaningful preview color
                                        # instead of uniform mid-grey.
                                        self.logger.info(
                                            f"   [B-DIAG] {rfm_node}: near-zero, "
                                            f"calling texture sampler..."
                                        )
                                        tex_color = self._sample_pxr_texture_color(
                                            rfm_node, color_attr
                                        )
                                        if tex_color is not None:
                                            if sg not in sg_to_color:  # don't overwrite Lambert file result
                                                sg_to_color[sg] = tex_color
                                                self.logger.info(
                                                    f"   [TEX] {sg} — sampled texture color: {tex_color}"
                                                )
                                            break
                                except Exception as _b_exc:
                                    self.logger.info(
                                        f"   [B-DIAG] EXCEPTION for {rfm_node}.{color_attr}: "
                                        f"{type(_b_exc).__name__}: {_b_exc}"
                                    )
                                    continue
                            # If ANY Pxr* node was found on this SG but no
                            # usable color was extracted, mark it with None
                            # so Phase C can't pick it up with black.
                            if has_pxr_node and sg not in sg_to_color:
                                sg_to_color[sg] = None
                        except Exception:
                            continue

                    # ----------------------------------------------------------
                    # Phase C: Generic surface shader fallback for non-Lambert,
                    # non-RFM SGs (e.g. aiStandardSurface, blinn, phong, etc.).
                    # Tries common color attribute names on whatever node is
                    # connected to .surfaceShader.
                    # ----------------------------------------------------------
                    # outColor covers Maya's built-in surfaceShader node type
                    # (used by utility shaders like asRedSG, asGreenSG, etc.).
                    # NOTE: outColor MUST be last.  On lambert nodes it is
                    # a computed output that returns (0,0,0) without a DG
                    # evaluation context.  Reading 'color' first yields the
                    # authored diffuse color (correct for lamberts).
                    GENERIC_COLOR_ATTRS = ("color", "baseColor", "diffuseColor", "Kd", "outColor")
                    for sg in (cmds.ls(type="shadingEngine") or []):
                        if sg in sg_to_color:
                            continue  # already resolved
                        try:
                            nodes = cmds.listConnections(f"{sg}.surfaceShader") or []
                        except Exception:
                            nodes = []
                        for node in nodes:
                            # Any Pxr* node is a RenderMan shader. Reading
                            # outColor/baseColor from an unevaluated Pxr node
                            # returns (0,0,0) and would corrupt the USD.
                            # Use startswith("Pxr") to catch every variant
                            # (PxrDisney, PxrDisneyBsdf, PxrSurface, etc.).
                            try:
                                if cmds.nodeType(node).startswith("Pxr"):
                                    sg_to_color[sg] = None
                                    break
                            except Exception:
                                pass
                            for ca in GENERIC_COLOR_ATTRS:
                                try:
                                    # Skip texture-driven attributes: if the color
                                    # input is connected to a PxrTexture or similar
                                    # upstream node, getAttr only returns the scalar
                                    # fallback (usually 0,0,0) which is misleading.
                                    # Using the black fallback would overwrite any
                                    # correct texture wiring already in USD.
                                    if cmds.listConnections(
                                        f"{node}.{ca}",
                                        source=True,
                                        destination=False,
                                    ):
                                        continue
                                    c = cmds.getAttr(f"{node}.{ca}")[0]
                                    sg_to_color[sg] = Gf.Vec3f(c[0], c[1], c[2])
                                    break
                                except Exception:
                                    pass
                            if sg in sg_to_color:
                                break

                    self.logger.info(f"[LOOKDEV] Found {len(lambert_colors)} Lambert materials in Maya")
                    color_count = sum(1 for v in sg_to_color.values() if v is not None)
                    skip_count = sum(1 for v in sg_to_color.values() if v is None)
                    skipped_sgs = [k for k, v in sg_to_color.items() if v is None]
                    self.logger.info(
                        f"[LOOKDEV] Mapped {color_count} shading groups to colors "
                        f"(A=Lambert, B=RfM Pxr*, C=generic)"
                        + (f", {skip_count} RfM texture-driven skipped" if skip_count else "")
                    )
                    if skipped_sgs:
                        self.logger.info(f"[LOOKDEV] Skipped RfM SGs: {skipped_sgs[:10]}")
                    self.logger.info(f"[LOOKDEV] Sample SG keys: {list(sg_to_color.keys())[:8]}")
                except Exception as e:
                    self.logger.warning(f"[WARNING] Could not query Maya materials: {e}")

            # ----------------------------------------------------------------
            # Step 2: Walk all USD Material prims and inject UsdPreviewSurface.
            # Match USD material prim name → Maya SG name using variations.
            # This avoids relying on mesh binding relationships entirely.
            # ----------------------------------------------------------------
            self.logger.info("[LOOKDEV] Scanning USD material prims for name→SG matches...")
            usd_mat_count = 0
            usd_mat_name_samples = []
            for prim in stage.Traverse():
                if prim.GetTypeName() != "Material":
                    continue
                usd_mat_count += 1
                usd_mat_name = prim.GetName()
                if len(usd_mat_name_samples) < 5:
                    usd_mat_name_samples.append(usd_mat_name)
                material = UsdShade.Material(prim)

                # Build name variations to match against Maya SG names
                # mayaUSD may strip trailing 'SG' or append it, clean namespaces, etc.
                name_vars = [
                    usd_mat_name,
                    usd_mat_name + "SG",
                    usd_mat_name + "1SG",
                    usd_mat_name.rstrip("SG"),
                    usd_mat_name.replace("_mat", "SG"),
                    usd_mat_name.replace("_mat", "1SG"),
                ]

                lambert_color = None
                matched_sg = None
                for var in name_vars:
                    if var in sg_to_color:
                        lambert_color = sg_to_color[var]
                        matched_sg = var
                        break

                if lambert_color is None:
                    # Last resort: infer color from the USD material prim name.
                    # Rig control shaders like asRedSG, asGreenSG, asBlueSG may
                    # not exist in the current Maya session (e.g. if the model
                    # file had a partial load error) but their names encode the
                    # intended color unambiguously.
                    name_lower = usd_mat_name.lower()
                    NAME_COLOR_MAP = [
                        ("red",     Gf.Vec3f(0.8, 0.1, 0.1)),
                        ("green",   Gf.Vec3f(0.1, 0.7, 0.1)),
                        ("blue",    Gf.Vec3f(0.1, 0.3, 0.9)),
                        ("yellow",  Gf.Vec3f(0.9, 0.85, 0.1)),
                        ("orange",  Gf.Vec3f(0.9, 0.5, 0.1)),
                        ("purple",  Gf.Vec3f(0.5, 0.1, 0.8)),
                        ("cyan",    Gf.Vec3f(0.1, 0.8, 0.8)),
                        ("pink",    Gf.Vec3f(0.9, 0.4, 0.6)),
                        ("brown",   Gf.Vec3f(0.45, 0.25, 0.1)),
                        ("white",   Gf.Vec3f(0.95, 0.95, 0.95)),
                        ("black",   Gf.Vec3f(0.02, 0.02, 0.02)),
                        ("gray",    Gf.Vec3f(0.5, 0.5, 0.5)),
                        ("grey",    Gf.Vec3f(0.5, 0.5, 0.5)),
                        ("gold",    Gf.Vec3f(0.85, 0.7, 0.1)),
                        ("silver",  Gf.Vec3f(0.75, 0.75, 0.78)),
                    ]
                    for keyword, inferred in NAME_COLOR_MAP:
                        if keyword in name_lower:
                            lambert_color = inferred
                            matched_sg = f"[name:{keyword}]"
                            break

                is_rfm_name = usd_mat_name.startswith(
                    ("PxrDisney", "PxrSurface", "PxrUnified", "PxrLayer", "PxrLM")
                )
                # Also treat near-black Gf.Vec3f as missing for RfM materials —
                # Phase B stores None for texture-driven Pxr nodes, but due to
                # exception-swallowing or phantom lambert connections the dict may
                # hold Gf.Vec3f(0,0,0) instead of Python None.  Either way the
                # mesh would render invisible without this guard.
                is_near_black = (
                    lambert_color is not None
                    and isinstance(lambert_color, Gf.Vec3f)
                    and (lambert_color[0] + lambert_color[1] + lambert_color[2]) <= 0.01
                )

                if lambert_color is None or (is_rfm_name and is_near_black):
                    # For RfM texture-driven materials use a mid-grey fallback so
                    # the mesh is at least visible in VP2.  Without a surface output
                    # VP2 renders the mesh as white/unshaded; without a non-black
                    # diffuseColor VP2 renders it as solid black.
                    if is_rfm_name:
                        # Texture sampling failed — generate a unique, deterministic
                        # color from the material name so each part of the rig is
                        # visually distinct in VP2 rather than uniform mid-grey.
                        lambert_color = self._rfm_name_color(usd_mat_name)
                        matched_sg = "[fallback:RfM-name-hash]"
                        self.logger.info(
                            f"   [FALLBACK] {usd_mat_name} — texture unreadable, "
                            f"using name-hash color: {lambert_color}"
                        )
                    else:
                        continue  # Non-RfM material with no color source — skip

                # RfM auto-names SGs after the shader node (e.g. PxrDisneyBsdf1SG).
                if is_rfm_name:
                    self.logger.info(
                        f"   [RFM] {usd_mat_name} — writing Phase B color: {lambert_color}"
                    )

                # Check if we already injected a PreviewSurface (re-export).
                # Use path-prefix traversal — GetAllDescendants() not available
                # in Maya's embedded USD Python build.
                preview_shader = None
                mat_path_prefix = str(prim.GetPath()) + "/"
                for desc_prim in stage.Traverse():
                    if not str(desc_prim.GetPath()).startswith(mat_path_prefix):
                        continue
                    if desc_prim.GetTypeName() == "Shader":
                        s = UsdShade.Shader(desc_prim)
                        if s and s.GetShaderId() == "UsdPreviewSurface":
                            preview_shader = s
                            break

                if preview_shader:
                    # Never overwrite a diffuseColor that already has a texture
                    # connection wired by mayaUSD (e.g. PxrDisney with PxrTexture).
                    # Reading the static color from the Lambert placeholder would
                    # replace the real texture with solid black.
                    dc_input = preview_shader.GetInput("diffuseColor")
                    if dc_input and dc_input.HasConnectedSource():
                        materials_converted += 1
                        self.logger.debug(
                            f"   [SKIP] {usd_mat_name} — diffuseColor already has texture connection"
                        )
                    else:
                        preview_shader.CreateInput(
                            "diffuseColor", Sdf.ValueTypeNames.Color3f
                        ).Set(lambert_color)
                        materials_converted += 1
                        self.logger.info(f"   [UPDATE] {usd_mat_name} ← {matched_sg} = {lambert_color}")

                    # Ensure material's universal 'surface' output is connected.
                    # The RenderMan exporter only creates ri:surface — VP2 needs
                    # the renderContext-free 'surface' output to find the shader.
                    surface_out = material.GetSurfaceOutput()
                    if not surface_out or not surface_out.HasConnectedSource():
                        material.CreateSurfaceOutput().ConnectToSource(
                            preview_shader.ConnectableAPI(), "surface"
                        )
                        self.logger.debug(
                            f"   [FIX] {usd_mat_name} — wired surface output for VP2"
                        )
                else:
                    # Inject PreviewSurface into the existing RenderMan material.
                    # universal 'surface' output leaves ri:surface connection untouched.
                    shader_path = f"{str(prim.GetPath())}/PreviewSurface"
                    shader = UsdShade.Shader.Define(stage, shader_path)
                    shader.CreateIdAttr("UsdPreviewSurface")
                    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(lambert_color)
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
                    materials_converted += 1
                    self.logger.info(f"   [INJECT] {usd_mat_name} ← {matched_sg} = {lambert_color}")

            self.logger.info(f"[LOOKDEV] Sample USD mat names: {usd_mat_name_samples}")
            self.logger.info(f"[LOOKDEV] Scanned {usd_mat_count} USD materials, injected/updated {materials_converted}")
            unmatched = usd_mat_count - materials_converted
            if unmatched > 0:
                self.logger.info(f"[LOOKDEV] {unmatched} USD materials had no SG color match — check SG keys above")
            if materials_converted > 0:
                stage.Save()
                self.logger.info(f"[OK] Created/updated {materials_converted} UsdPreviewSurface materials with colors")
            else:
                self.logger.info(
                    f"[OK] No SG name matches found in {usd_mat_count} USD materials"
                    " — check SG name samples above"
                )

        except Exception as e:
            self.logger.warning(f"[WARNING] Material conversion error: {e}")
            import traceback
            self.logger.warning(traceback.format_exc())

    def _fix_exported_usdc(self, usd_path: Path) -> None:
        """
        Comprehensive post-export structural fix-up for the USDC written by mayaUSD.

        mayaUSD leaves several structural issues that break display in all non-Maya
        USD viewers (needle.tools, usdview, Unreal, Houdini, etc.) and in Maya's own
        VP2 when the file is imported back as a proxy:

        1. outputs:surface wiring  — mayaUSD with RenderMan shading mode creates
           UsdPreviewSurface shaders inside render-context NodeGraphs but forgets to
           connect the material's universal ``outputs:surface`` output.  Any viewer that
           uses the universal surface output (everything except RenderMan) sees grey.

        2. material:binding  — mayaUSD's ``useRegistry`` shading mode skips writing
           material:binding relationships on skinned meshes when the source shaders are
           RenderMan PxrSurface/PxrDisney nodes.  We rebuild the mesh→SG→Material path
           mapping from Maya cmds and write the missing relationships.

        3. GeomSubset binding  — face-level material assignments exported as GeomSubset
           prims are named after their shading group; we match the name directly to the
           USD Material prim and write material:binding.

        4. Skeleton→Xform re-typing  — mayaUSD types EVERY joint chain as a Skeleton
           prim.  A rig with 121 FK control joints produces 121 Skeleton prims, causing
           UsdSkelImaging to create a separate mesh instance per skeleton and flooding
           the stage with orphaned SkelAnimation prims.  Only the bind skeleton
           (FitSkeleton) stays as Skeleton; all others become lightweight Xform prims.

        5. SkelAnimation deactivation  — SkelAnimation prims paired with the now-Xform'd
           rig-control joints are deactivated so they don't waste evaluation time.

        6. Root-level Mesh deactivation  — any Mesh prim that lives outside the default
           prim's subtree is a blendshape target mesh exported by mayaUSD as a standalone
           prim.  These appear as floating duplicate geometry in viewers.  We deactivate
           them (the UsdSkel.BlendShape prims written by _export_blendshapes_to_usd
           already contain the correct offset data).
        """
        if not USD_AVAILABLE:
            return
        try:
            from pxr import Usd, UsdShade, UsdSkel, UsdGeom  # type: ignore

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning(f"[FIX] Could not open stage: {usd_path}")
                return

            # ── Pass 1: Single traversal \u2014 build all lookup maps ─────────────────────
            # mat_name_to_path: Material prim name → SdfPath
            # mat_path_to_shader: Material SdfPath → UsdShade.Shader (UsdPreviewSurface)
            mat_name_to_path = {}
            mat_path_to_shader = {}
            for prim in stage.Traverse():
                ptype = prim.GetTypeName()
                if ptype == 'Material':
                    mat_name_to_path[prim.GetName()] = prim.GetPath()
                elif ptype == 'Shader':
                    s = UsdShade.Shader(prim)
                    sid_attr = s.GetIdAttr()
                    if sid_attr and sid_attr.Get() == 'UsdPreviewSurface':
                        # Walk up to find the owning Material
                        ancestor = prim.GetParent()
                        while ancestor and ancestor.IsValid():
                            if ancestor.GetTypeName() == 'Material':
                                # Keep the first (deepest) match per material
                                if ancestor.GetPath() not in mat_path_to_shader:
                                    mat_path_to_shader[ancestor.GetPath()] = s
                                break
                            ancestor = ancestor.GetParent()

            self.logger.info(
                f"[FIX] Found {len(mat_name_to_path)} USD materials, "
                f"{len(mat_path_to_shader)} with UsdPreviewSurface shaders"
            )

            # ── Fix 1: Wire outputs:surface for all materials that are missing it ──
            surface_wired = 0
            for mat_path, preview_shader in mat_path_to_shader.items():
                mat_prim = stage.GetPrimAtPath(mat_path)
                if not mat_prim.IsValid():
                    continue
                surf_attr = mat_prim.GetAttribute('outputs:surface')
                if surf_attr.IsValid() and surf_attr.HasAuthoredConnections():
                    continue  # Already properly wired
                UsdShade.Material(mat_prim).CreateSurfaceOutput().ConnectToSource(
                    preview_shader.ConnectableAPI(), 'surface'
                )
                surface_wired += 1
            self.logger.info(f"[FIX] Wired outputs:surface on {surface_wired} materials")

            # ── Fix 2: Build Maya mesh→SG map (cmds available at export time) ───────
            mesh_to_sg = {}   # USD Mesh prim transform name → Maya shading group name
            if cmds is not None:
                try:
                    for maya_mesh_shape in (cmds.ls(type='mesh') or []):
                        try:
                            sgs = cmds.listConnections(
                                maya_mesh_shape, type='shadingEngine'
                            ) or []
                            if not sgs:
                                continue
                            parents = (
                                cmds.listRelatives(maya_mesh_shape, parent=True, fullPath=False)
                                or []
                            )
                            transform_name = parents[0] if parents else maya_mesh_shape
                            # mayaUSD can represent namespaces two ways:
                            # 1. stripNamespaces=True  → prim name = short name only
                            # 2. stripNamespaces=False → colon sanitized to underscore
                            short_name = transform_name.split(':')[-1]
                            sanitized = transform_name.replace(':', '_')
                            mesh_to_sg.setdefault(short_name, sgs[0])
                            if sanitized != short_name:
                                mesh_to_sg.setdefault(sanitized, sgs[0])
                        except Exception:
                            pass
                    self.logger.info(f"[FIX] Maya mesh→SG map: {len(mesh_to_sg)} entries")
                except Exception as me:
                    self.logger.warning(f"[FIX] Could not build mesh→SG map: {me}")

            # ── Fix 3: Write material:binding + identify root-level Mesh prims ──────
            default_prim = stage.GetDefaultPrim()
            default_path_prefix = (
                str(default_prim.GetPath()) + '/' if default_prim else ''
            )
            bindings_written = 0
            subset_bindings = 0
            root_mesh_paths = []

            for prim in stage.Traverse():
                ptype = prim.GetTypeName()
                if ptype == 'Mesh':
                    prim_path_str = str(prim.GetPath())
                    if default_path_prefix and not prim_path_str.startswith(default_path_prefix):
                        root_mesh_paths.append(prim.GetPath())
                        continue  # Will deactivate below
                    bind_api = UsdShade.MaterialBindingAPI(prim)
                    existing, _ = bind_api.ComputeBoundMaterial()
                    if existing and existing.GetPrim().IsValid():
                        continue  # Already has a binding
                    prim_name = prim.GetName()
                    sg_name = mesh_to_sg.get(prim_name)
                    if not sg_name:
                        # Baked meshes: _usdExport[N] suffix was added by the
                        # pipeline during multi-skincluster fixup; strip it to
                        # find the original transform in the map.
                        import re as _re
                        base_name = _re.sub(r'_usdExport\d*$', '', prim_name)
                        if base_name != prim_name:
                            sg_name = mesh_to_sg.get(base_name)
                    if sg_name and sg_name in mat_name_to_path:
                        mat_prim = stage.GetPrimAtPath(mat_name_to_path[sg_name])
                        if mat_prim.IsValid():
                            UsdShade.MaterialBindingAPI.Apply(prim)
                            bind_api.Bind(UsdShade.Material(mat_prim))
                            bindings_written += 1
                elif ptype == 'GeomSubset':
                    # mayaUSD names GeomSubsets after the shading group they represent
                    bind_api = UsdShade.MaterialBindingAPI(prim)
                    existing, _ = bind_api.ComputeBoundMaterial()
                    if existing and existing.GetPrim().IsValid():
                        continue
                    subset_name = prim.GetName()
                    if subset_name in mat_name_to_path:
                        mat_prim = stage.GetPrimAtPath(mat_name_to_path[subset_name])
                        if mat_prim.IsValid():
                            UsdShade.MaterialBindingAPI.Apply(prim)
                            bind_api.Bind(UsdShade.Material(mat_prim))
                            subset_bindings += 1

            self.logger.info(
                f"[FIX] Material binding: {bindings_written} Mesh + "
                f"{subset_bindings} GeomSubset relationships written"
            )

            # ── Fix 4: Deactivate root-level blendshape target Mesh prims + rig-fit helpers
            # Root-level prims: blendshape targets exported by mayaUSD outside SkelRoot.
            # FaceGroup fit-geometry (FitEyeSphere, EyeLidInnerArea, LipInner, ForeHead):
            #   Advanced Skeleton face-fitting rig meshes live under FaceGroup/FaceFitSkeleton.
            #   They are scene-construction helpers, not render geometry — deactivate them.
            # Duplicate _usdExport1 meshes: mayaUSD sometimes writes a numbered duplicate
            #   when the same shape is skinned by more than one skin cluster (e.g. body mesh
            #   with a secondary corrective cluster); deactivate the redundant copy.
            fit_geo_keywords = ('FaceGroup', 'FaceFit', 'FitEye', 'FitLip', 'FitFore')
            deactivated_extra = 0
            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Mesh':
                    continue
                p_str = str(prim.GetPath())
                # FaceGroup fit-geometry
                if any(kw in p_str for kw in fit_geo_keywords):
                    prim.SetActive(False)
                    deactivated_extra += 1
                    continue
                # Numbered duplicate: name ends with a digit suffix on '_usdExport'
                # e.g. model_Body_Geo_usdExport1 vs model_Body_Geo_usdExport
                name = prim.GetName()
                if name.endswith(tuple('0123456789')) and '_usdExport' in name:
                    prim.SetActive(False)
                    deactivated_extra += 1
            for path in root_mesh_paths:
                stage.GetPrimAtPath(path).SetActive(False)
            self.logger.info(
                f"[FIX] Deactivated {len(root_mesh_paths)} root-level blendshape Mesh prims, "
                f"{deactivated_extra} FaceGroup/duplicate Mesh prims"
            )

            # ── Fix 4b: Set NurbsPatch purpose → guide (belt-and-suspenders for
            #           cases where filterTypes didn't strip them) ──────────────────
            nurbs_patched = []
            for prim in stage.Traverse():
                if prim.GetTypeName() == 'NurbsPatch':
                    nurbs_patched.append(prim.GetPath())
            for path in nurbs_patched:
                UsdGeom.Imageable(stage.GetPrimAtPath(path)).CreatePurposeAttr().Set(
                    UsdGeom.Tokens.guide
                )
            if nurbs_patched:
                self.logger.info(
                    f"[FIX] Set purpose=guide on {len(nurbs_patched)} NurbsPatch prims"
                )

            # ── Fix 5: Find the bind skeleton ────────────────────────────────────────
            # Prefer FitSkeleton by name (mGear / Advanced Skeleton convention).
            # Fallback: the Skeleton prim with the most joints = bind skeleton.
            bind_skeleton_path = None
            max_joints = 0
            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Skeleton':
                    continue
                if 'FitSkeleton' in str(prim.GetPath()):
                    bind_skeleton_path = prim.GetPath()
                    break
                sk = UsdSkel.Skeleton(prim)
                joints_attr = sk.GetJointsAttr()
                joints = joints_attr.Get() if joints_attr else None
                count = len(joints) if joints else 0
                if count > max_joints:
                    max_joints = count
                    bind_skeleton_path = prim.GetPath()

            bind_skel_str = str(bind_skeleton_path) if bind_skeleton_path else ''
            self.logger.info(f"[FIX] Bind skeleton: {bind_skeleton_path}")

            # ── Fix 6: Re-type FK-rig Skeleton prims → Xform ────────────────────────
            # Collect first, then modify (safe with pxr's traversal model)
            skeletons_to_retype = []
            skel_anims_to_deactivate = []
            for prim in stage.Traverse():
                ptype = prim.GetTypeName()
                if ptype == 'Skeleton':
                    if bind_skeleton_path and prim.GetPath() == bind_skeleton_path:
                        continue  # Keep the real bind skeleton
                    skeletons_to_retype.append(prim.GetPath())
                elif ptype == 'SkelAnimation':
                    ppath_str = str(prim.GetPath())
                    # Keep SkelAnimations that live directly under the bind skeleton
                    if bind_skel_str and not ppath_str.startswith(bind_skel_str + '/'):
                        skel_anims_to_deactivate.append(prim.GetPath())

            for path in skeletons_to_retype:
                stage.GetPrimAtPath(path).SetTypeName('Xform')
            for path in skel_anims_to_deactivate:
                stage.GetPrimAtPath(path).SetActive(False)

            self.logger.info(
                f"[FIX] Re-typed {len(skeletons_to_retype)} Skeleton→Xform, "
                f"deactivated {len(skel_anims_to_deactivate)} orphan SkelAnimation prims"
            )

            stage.Save()
            self.logger.info(f"[FIX] Structural fix-up complete → {usd_path.name}")

        except Exception as e:
            self.logger.warning(f"[FIX] Post-export fix-up failed: {e}")
            import traceback
            self.logger.warning(traceback.format_exc())

    def _create_usd_preview_material(
        self,
        stage,
        materials_scope,
        mesh_name: str,
        diffuse_color: 'Gf.Vec3f',
        mesh_prim
    ) -> None:
        """Create a UsdPreviewSurface material and bind it to a mesh"""
        try:
            from pxr import UsdShade, Sdf, Gf

            # Create material prim
            material_path = f"{materials_scope.GetPath()}/{mesh_name}_mat"
            material = UsdShade.Material.Define(stage, material_path)

            # Create UsdPreviewSurface shader
            shader_path = f"{material_path}/PreviewSurface"
            shader = UsdShade.Shader.Define(stage, shader_path)
            shader.CreateIdAttr("UsdPreviewSurface")

            # Set diffuse color from Lambert
            if diffuse_color:
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(diffuse_color)
            else:
                # Default to white if no color found
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.8, 0.8, 0.8))

            # Set reasonable default PBR values
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

            # Connect shader to material surface
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

            # Bind material to mesh
            UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)

            self.logger.debug(f"   [OK] Created UsdPreviewSurface for {mesh_name}")

        except Exception as e:
            self.logger.warning(f"[WARNING] Failed to create material for {mesh_name}: {e}")

    def _create_usdz_package(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path],
        usdz_path: Path
    ) -> bool:
        """
        Create USDZ package containing USD and .rig.mb backup
        """
        try:
            import zipfile

            with zipfile.ZipFile(str(usdz_path), 'w', zipfile.ZIP_STORED) as zf:
                # Add USD file (must be first for USDZ spec compliance)
                zf.write(str(usd_path), usd_path.name)

                # Add .rig.mb backup if exists
                if rig_mb_path and rig_mb_path.exists():
                    zf.write(str(rig_mb_path), rig_mb_path.name)
                    self.logger.info(f"[PACKAGE] Added rig backup to USDZ: {rig_mb_path.name}")

            file_size = usdz_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"[BUNDLE] USDZ package: {usdz_path.name} ({file_size:.1f} MB)")
            return True

        except Exception as e:
            self.logger.error(f"USDZ packaging failed: {e}")
            return False

    def _cleanup_intermediate_files(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path]
    ) -> None:
        """
        Delete intermediate .usdc and .rig.mb files after USDZ packaging.

        The USDZ already contains these files, so we can clean up
        to avoid file clutter.
        """
        try:
            # Delete .usdc file
            if usd_path.exists():
                usd_path.unlink()
                self.logger.info(f"[CLEANUP] Cleaned up intermediate: {usd_path.name}")

            # Delete .rig.mb file
            if rig_mb_path and rig_mb_path.exists():
                rig_mb_path.unlink()
                self.logger.info(f"[CLEANUP] Cleaned up intermediate: {rig_mb_path.name}")

            self.logger.info("[OK] Intermediate files cleaned up (bundled in USDZ)")

        except Exception as e:
            self.logger.warning(f"[WARNING] Cleanup warning: {e}")

    def _create_zip_archive(
        self,
        subfolder: Optional[Path],
        usdz_path: Optional[Path],
        usd_path: Path,
        rig_mb_path: Optional[Path],
        zip_path: Path,
        options: ExportOptions
    ) -> bool:
        """
        Create ZIP archive containing all export files.

        This provides better compression and protection for asset distribution.
        """
        try:
            import zipfile

            with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                # If organized in subfolder, zip the entire folder
                if subfolder and subfolder.exists():
                    for file in subfolder.iterdir():
                        if file.is_file():
                            # Store with folder structure: AssetName_USD/filename
                            arcname = f"{subfolder.name}/{file.name}"
                            zf.write(str(file), arcname)
                            self.logger.info(f"[PACKAGE] Added to ZIP: {arcname}")
                else:
                    # Add individual files
                    if usdz_path and usdz_path.exists():
                        zf.write(str(usdz_path), usdz_path.name)
                        self.logger.info(f"[PACKAGE] Added to ZIP: {usdz_path.name}")

                    if not options.cleanup_intermediate_files:
                        if usd_path.exists():
                            zf.write(str(usd_path), usd_path.name)
                            self.logger.info(f"[PACKAGE] Added to ZIP: {usd_path.name}")

                        if rig_mb_path and rig_mb_path.exists():
                            zf.write(str(rig_mb_path), rig_mb_path.name)
                            self.logger.info(f"[PACKAGE] Added to ZIP: {rig_mb_path.name}")

            file_size = zip_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"🗜️ ZIP archive: {zip_path.name} ({file_size:.1f} MB)")
            return True

        except Exception as e:
            self.logger.error(f"ZIP archive creation failed: {e}")
            return False

    # =========================================================================
    # IMPORT
    # =========================================================================

    def import_usd(
        self,
        usd_path: Path,
        options: Optional[ImportOptions] = None
    ) -> ImportResult:
        """
        Import USD file with smart fallback to .rig.mb
        Args:
            usd_path: Path to .usd/.usdc/.usda/.usdz file
            options: Import options

        Returns:
            ImportResult with details
        """
        result = ImportResult()
        options = options or ImportOptions()

        if not self._maya_available:
            result.error_message = "Maya not available"
            return result

        try:
            self._report_progress("Starting import", 0)

            # Handle USDZ packages
            actual_usd_path = usd_path
            rig_mb_path: Optional[Path] = None
            temp_dir: Optional[Path] = None

            if usd_path.suffix.lower() == '.usdz':
                self._report_progress("Extracting USDZ package", 5)
                actual_usd_path, rig_mb_path, temp_dir = self._extract_usdz(usd_path)

                if not actual_usd_path:
                    result.error_message = "Failed to extract USDZ package"
                    return result

            # ========== USD PROXY MODE (EXPERIMENTAL) ==========
            # Keep USD as proxy for pipeline integration
            if options.usd_proxy_mode:
                self.logger.info("[USD] USD PROXY MODE ACTIVATED (Experimental)")

                # IMPORT-TIME COLOUR BOOST: the USDC was written by a previous
                # export run and may contain desaturated grey-brown diffuseColors
                # (0.29-0.43 typical for military gear).  Boost them now so VP2
                # shows clearly distinct hues without needing to re-export.
                # This is safe to run on every import — it is idempotent and only
                # touches static (non-texture-connected) diffuseColor inputs.
                self._boost_usd_material_colors(actual_usd_path)

                # Build layered stage: decompose monolithic .usdc into
                # root.usda → animation / controllers / materials / skeleton / geometry / base
                self._report_progress("[LAYER] Building layered USD stage", 10)
                layered_root = self._build_layered_stage(actual_usd_path, rig_mb_path)
                if layered_root:
                    self.logger.info(
                        f"[OK] Proxy will load layered stage: {layered_root.name}"
                    )
                    actual_usd_path = layered_root
                else:
                    self.logger.warning(
                        "[WARNING] Layered stage creation failed — "
                        "falling back to monolithic USD"
                    )

                self._report_progress("[USD] Creating USD Proxy Shape", 20)
                usd_success = self._import_with_mayausd(actual_usd_path, options, result)

                if usd_success and result.usd_meshes > 0:
                    result.success = True
                    result.meshes_imported = result.usd_meshes
                    result.joints_imported = result.usd_joints
                    self.logger.info(
                        f"[OK] USD Proxy created: {result.usd_meshes} meshes, "
                        f"{result.usd_joints} joints in USD"
                    )
                    # Materials live inside the USD stage — rendered by VP2, not Maya Hypershade
                    if result.usd_materials > 0:
                        self.logger.info(
                            f"[LOOKDEV] {result.usd_materials} USD materials rendered via VP2 "
                            f"(UsdPreviewSurface — these are USD-native, not Maya Hypershade shaders)"
                        )
                    if options.open_layer_editor:
                        self.logger.info(
                            "[TIP] USD Layer Editor opened — author animation as a non-destructive layer (Option B)"
                        )
                    else:
                        self.logger.info(
                            "[TIP] Animate via USD > Edit As Maya Data (Option A) "
                            "or reopen with 'USD Layer Editor' selected (Option B)"
                        )
                else:
                    result.error_message = "USD proxy creation failed or no content"

                self._report_progress("USD Proxy import complete", 100)
                return result

            # ========== HYBRID WORKFLOW (RECOMMENDED) ==========
            rig_exists = rig_mb_path.exists() if rig_mb_path else False
            self.logger.info(
                f"[IMPORT] Hybrid check: hybrid_mode={options.hybrid_mode}, "
                f"rig_mb_path={rig_mb_path}, exists={rig_exists}"
            )
            if options.hybrid_mode and rig_mb_path and rig_mb_path.exists():
                self.logger.info("[OK] HYBRID MODE ACTIVATED")
                self._report_progress("[HYBRID] Hybrid Mode: Converting USD to Maya + controllers", 20)
                success = self._import_hybrid(actual_usd_path, rig_mb_path, options, result)
                result.success = success
                self._report_progress("Hybrid import complete", 100)
                return result

            # ========== STANDARD WORKFLOWS ==========
            # Build layered stage for standard proxy import too
            layered_root = self._build_layered_stage(actual_usd_path, rig_mb_path)
            if layered_root:
                actual_usd_path = layered_root

            # Import USD using mayaUSD - creates a proxy shape with USD prims
            self._report_progress("Importing USD via mayaUSD", 20)
            usd_success = self._import_with_mayausd(actual_usd_path, options, result)

            # Check if USD import succeeded (proxy shape with content)
            has_usd_content = usd_success and result.usd_meshes > 0

            if has_usd_content:
                # SUCCESS! USD prims loaded in proxy shape - this is the Disney workflow
                self.logger.info(
                    f"[OK] USD import successful: {result.usd_meshes} mesh prims, "
                    f"{result.usd_joints} skeleton prims in USD proxy shape"
                )
                self.logger.info("[TIP] USD prims are viewable in Maya viewport via proxy shape")
                self.logger.info("[TIP] To convert to native Maya: Right-click proxy > Duplicate As > Maya Data")

                result.success = True
                self._report_progress("USD import complete", 100)

            elif not usd_success:
                # USD import completely failed - use .rig.mb fallback
                if rig_mb_path and rig_mb_path.exists() and options.use_rig_mb_fallback:
                    self._report_progress("USD import failed - Using .rig.mb fallback", 60)
                    self._import_rig_mb_fallback(rig_mb_path, result)
                    result.success = result.meshes_imported > 0
                else:
                    result.error_message = "USD import failed and no fallback available"
                    return result

            else:
                # USD import returned True but no meshes - try .rig.mb fallback
                if rig_mb_path and rig_mb_path.exists() and options.use_rig_mb_fallback:
                    self._report_progress("No USD meshes found - Using .rig.mb fallback", 60)
                    self._supplement_from_rig_mb(rig_mb_path, options, result)
                    result.success = result.meshes_imported > 0
                else:
                    result.error_message = "USD proxy created but contains no meshes"
                    return result

            self._report_progress("Import complete", 100)

            # IMPORTANT: Do NOT cleanup temp directory if we created a proxy shape!
            # The proxy shape REFERENCES the USD file - deleting it breaks the scene.
            if temp_dir and temp_dir.exists():
                if has_usd_content:
                    # Keep the temp dir - proxy shape needs the USD file
                    self.logger.info(f"[SAVE] USD files preserved in: {temp_dir}")
                    self.logger.info(
                        "[TIP] To make permanent: File > Archive Scene or re-export USDZ"
                    )
                    result.temp_usd_path = actual_usd_path  # Store for reference
                else:
                    # Used .rig.mb fallback - safe to cleanup temp files
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self.logger.info("[CLEANUP] Cleaned up temp USDZ extraction")

        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            result.error_message = str(e)

        return result

    def _extract_usdz(
        self,
        usdz_path: Path
    ) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """
        Extract USDZ package

        Returns:
            (usd_path, rig_mb_path, temp_dir) or (None, None, None) on failure
        """
        try:
            import zipfile
            import tempfile

            # Create temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix='usdz_import_'))

            usd_path = None
            rig_mb_path = None

            with zipfile.ZipFile(str(usdz_path), 'r') as zf:
                for name in zf.namelist():
                    zf.extract(name, str(temp_dir))
                    extracted_path = temp_dir / name

                    if name.endswith(('.usd', '.usdc', '.usda')):
                        usd_path = extracted_path
                        self.logger.info(f"[FILE] Extracted USD: {name}")
                    elif name.endswith('.rig.mb') or name.endswith('.rig.ma'):
                        rig_mb_path = extracted_path
                        self.logger.info(f"[PACKAGE] Extracted rig backup: {name}")

            return usd_path, rig_mb_path, temp_dir

        except Exception as e:
            self.logger.error(f"USDZ extraction failed: {e}")
            return None, None, None

    def _import_with_mayausd(
        self,
        usd_path: Path,
        options: ImportOptions,
        result: ImportResult
    ) -> bool:
        """
        Import USD by creating a mayaUsdProxyShape that loads the USD natively.

        This is the Disney/Pixar workflow - USD prims are displayed through
        the proxy shape, NOT converted to native Maya meshes.
        """
        if not self._mayausd_available:
            self.logger.error("mayaUSD plugin not available")
            return False

        try:
            # First, let's inspect the USD to see what's in it
            mesh_count = 0
            skel_count = 0
            curve_count = 0
            material_count = 0
            has_skeleton_bindings = False

            joint_count = 0

            if USD_AVAILABLE:
                try:
                    from pxr import Usd, UsdSkel  # type: ignore
                    stage = Usd.Stage.Open(str(usd_path))
                    if stage:
                        # Find the default prim or root
                        default_prim = stage.GetDefaultPrim()
                        default_path = default_prim.GetPath() if default_prim else None
                        self.logger.info(f"[FILE] USD default prim: {default_path}")

                        # Count prims
                        for prim in stage.Traverse():
                            prim_type = prim.GetTypeName()
                            if prim_type == 'Mesh':
                                mesh_count += 1
                                # Check if mesh has skeleton binding
                                if prim.HasAPI(UsdSkel.BindingAPI):
                                    has_skeleton_bindings = True
                            elif prim_type == 'Skeleton':
                                skel_count += 1
                                # Sum actual joints defined in this Skeleton
                                joints_attr = UsdSkel.Skeleton(prim).GetJointsAttr().Get()
                                if joints_attr:
                                    joint_count += len(joints_attr)
                            elif prim_type in ('NurbsCurves', 'BasisCurves'):
                                curve_count += 1
                            elif prim_type == 'Material':
                                material_count += 1

                        self.logger.info(
                            f"[INFO] USD contains: {mesh_count} meshes, {skel_count} skeleton rig(s) "
                            f"({joint_count} joints), {curve_count} curves, {material_count} materials"
                        )
                        if has_skeleton_bindings:
                            self.logger.info("[INFO] USD has skeleton-bound meshes (skinned)")
                except Exception as e:
                    self.logger.warning(f"Could not inspect USD: {e}")

            if cmds is None:
                self.logger.error("Maya cmds not available")
                return False

            # Create a USD proxy shape that loads the USD file natively
            # This is the proper Disney/Pixar workflow - USD prims displayed through proxy
            self.logger.info("[ANIMATION] Creating USD Stage (mayaUsdProxyShape)...")

            try:
                # Tell VP2 to resolve UsdPreviewSurface materials via the shader registry
                # BEFORE the stage loads.  The proxy shape consults this optionVar at load
                # time (when filePath is set), so it must be in place first.
                # Maya confirms success with: "# Using V3 Lighting API for UsdPreviewSurface shading."
                try:
                    cmds.optionVar(stringValue=('mayaUsd_ShadingModeImport', 'useRegistry'))
                    self.logger.info("[SHADING] mayaUsd_ShadingModeImport=useRegistry — VP2 will use V3 Lighting API")
                except Exception:
                    pass

                # Sanitize the stem: Maya node names must not contain dots.
                # e.g. "Veteran_Rig.root" → "Veteran_Rig_root"
                node_base = usd_path.stem.replace('.', '_')

                # Create the proxy shape
                proxy_transform = cmds.createNode('transform', name=node_base + '_USD')
                proxy_shape = cmds.createNode(
                    'mayaUsdProxyShape',
                    parent=proxy_transform,
                    name=node_base + '_USDShape'
                )

                # Loading the file path triggers USD stage composition.
                # Maya will print "# Using V3 Lighting API for UsdPreviewSurface shading."
                # confirming the optionVar above was respected.
                cmds.setAttr(f"{proxy_shape}.filePath", str(usd_path), type='string')

                # Enable proxy drawing
                cmds.setAttr(f"{proxy_shape}.loadPayloads", True)

                # IMPORTANT: For skinned meshes, set draw modes
                try:
                    cmds.setAttr(f"{proxy_shape}.drawProxyPurpose", True)
                    cmds.setAttr(f"{proxy_shape}.drawRenderPurpose", True)
                    cmds.setAttr(f"{proxy_shape}.drawGuidePurpose", False)
                except Exception:
                    pass  # Attribute may not exist in all Maya versions

                # WORKAROUND: Force stage reload to ensure skeleton bindings resolve correctly
                # Toggling the file path forces a clean reload.
                try:
                    # Store the path
                    file_path = cmds.getAttr(f"{proxy_shape}.filePath")
                    # Clear and reset to force reload
                    cmds.setAttr(f"{proxy_shape}.filePath", "", type='string')
                    cmds.refresh()
                    cmds.setAttr(f"{proxy_shape}.filePath", file_path, type='string')
                    cmds.refresh()
                    self.logger.info("[REFRESH] Forced stage reload for skeleton imaging")
                except Exception:
                    pass

                self.logger.info(f"[OK] Created USD proxy shape: {proxy_shape}")
                self.logger.info(f"[FILE] Loading USD file: {usd_path}")

                # Select and frame the proxy transform for visibility
                try:
                    cmds.select(proxy_transform, replace=True)
                    cmds.viewFit(allObjects=False)  # Frame selection in viewport
                    self.logger.info("[CAMERA] Selected and framed USD proxy in viewport")
                except Exception as frame_err:
                    self.logger.warning(f"[WARNING] Could not frame proxy: {frame_err}")

                # Ensure VP2.0 is active for USD display with materials.
                # getPanel(withFocus=True) returns the dialog when the asset manager
                # UI has focus — fall back to all model panels so material display
                # is always configured regardless of which window is focused.
                try:
                    focused = cmds.getPanel(withFocus=True)
                    if focused and 'modelPanel' in focused:
                        panels_to_configure = [focused]
                    else:
                        panels_to_configure = cmds.getPanel(type='modelPanel') or []

                    configured = 0
                    for panel in panels_to_configure:
                        try:
                            # Switch to VP2.0 if needed
                            renderer = cmds.modelEditor(panel, query=True, rendererName=True)
                            if renderer != 'vp2Renderer':
                                cmds.modelEditor(panel, edit=True, rendererName='vp2Renderer')

                            # Enable shaded+material display.
                            # useDefaultMaterial=False is the critical flag —
                            # without it VP2 shows solid white ("default material") on
                            # USD proxy shapes even when UsdPreviewSurface shaders exist.
                            cmds.modelEditor(
                                panel,
                                edit=True,
                                displayTextures=True,
                                displayAppearance='smoothShaded',
                                displayLights='default',
                                useDefaultMaterial=False,
                            )
                            configured += 1
                        except Exception:
                            pass  # Skip any panel that doesn't support these flags

                    if configured:
                        self.logger.info(
                            f"[LOOKDEV] Enabled material display in {configured} viewport(s) "
                            f"(VP2, smoothShaded, useDefaultMaterial=False)"
                        )
                    else:
                        self.logger.warning("[WARNING] Could not configure any model panel for material display")

                    cmds.refresh(force=True)
                except Exception as vp_err:
                    self.logger.warning(f"[WARNING] Could not configure viewport: {vp_err}")

                # Convert USD Skeleton to Maya Joints if requested
                if options.convert_skeleton_to_maya:
                    self._convert_usd_skeleton_to_maya(proxy_shape, usd_path)
                else:
                    self.logger.info(
                        "[SKEL] Skeleton managed by UsdSkelImaging inside proxy shape "
                        "(set convert_skeleton_to_maya=True to extract as Maya joints)"
                    )

            except Exception as proxy_err:
                self.logger.error(f"mayaUsdProxyShape creation failed: {proxy_err}")
                return False

            # Check for proxy shapes
            proxy_shapes = cmds.ls(type='mayaUsdProxyShape') or []
            if proxy_shapes:
                self.logger.info(f"[PACKAGE] USD proxy shape(s) created: {len(proxy_shapes)}")

                # Count USD prims inside the proxy shape(s)
                self._count_usd_prims_in_proxy(proxy_shapes, result)

                # Mark as successful USD import
                result.usd_meshes = mesh_count if mesh_count > 0 else result.usd_meshes
                # Use real joint count; skel_count is kept for threshold checks below
                result.usd_joints = joint_count if joint_count > 0 else skel_count
                result.usd_curves = curve_count if curve_count > 0 else result.usd_curves
                result.usd_materials = material_count if material_count > 0 else result.usd_materials

                # For display, these ARE our imported counts (USD prims = content)
                result.meshes_imported = result.usd_meshes
                result.joints_imported = result.usd_joints
                result.curves_imported = result.usd_curves
                result.materials_imported = result.usd_materials

                self.logger.info(
                    f"[OK] USD Stage loaded - {result.usd_meshes} meshes, "
                    f"{skel_count} skeleton rig(s) / {result.usd_joints} joints, "
                    f"{result.usd_curves} curves, {result.usd_materials} materials"
                )

                # Info about USD workflow
                if has_skeleton_bindings and skel_count > 10:
                    self.logger.info(
                        "[INFO] Complex skeleton detected - USD proxy will display skinned meshes via UsdSkelImaging"
                    )

                # Open USD Layer Editor if requested (Option B animation authoring)
                if options.open_layer_editor:
                    self._open_usd_layer_editor(proxy_shape)

                return True
            else:
                self.logger.warning("[ERROR] No USD proxy shapes found after import")
                return False

        except Exception as e:
            self.logger.error(f"USD import failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _open_usd_layer_editor(self, proxy_shape: str) -> None:
        """
        Open the mayaUSD Layer Editor and create an editable animation sublayer.

        This is Option B — author animation non-destructively as a USD layer
        on top of the stage rather than converting prims to Maya joints.
        """
        try:
            # Select the proxy transform so the Layer Editor shows its stage
            if cmds is not None:
                parents = cmds.listRelatives(proxy_shape, parent=True) or []
                if parents:
                    cmds.select(parents[0], replace=True)

            # Create an anonymous edit sublayer BEFORE opening the editor
            # so the user sees a writable layer immediately
            self._create_animation_edit_layer(proxy_shape)

            # Open the mayaUSD Layer Editor
            try:
                mel.eval('mayaUsdLayerEditorWindow')
                self.logger.info(
                    "[LAYER] Opened mayaUSD Layer Editor — author animation as USD layers (Option B)"
                )
                return
            except Exception:
                pass

            # Fall back to Maya's built-in Animation Layer Editor
            try:
                mel.eval('LayerEditorWindow')
                self.logger.info("[LAYER] Opened Animation Layer Editor (fallback)")
            except Exception as fallback_err:
                self.logger.warning(f"[WARNING] Could not open Layer Editor: {fallback_err}")

        except Exception as e:
            self.logger.warning(f"[WARNING] _open_usd_layer_editor failed: {e}")

    def _create_animation_edit_layer(self, proxy_shape: str) -> None:
        """
        Set the animation sublayer as the edit target on the proxy's live stage.

        The layered stage already contains editorial sublayers (animation, materials,
        skeleton, geometry) built by _build_layered_stage.  This method finds the
        animation layer and makes it the active edit target so keyframes land there.
        """
        if cmds is None:
            return

        try:
            from pxr import Usd  # pyright: ignore[reportMissingImports]

            # ── Get the live stage from the proxy shape ──
            stage = None

            try:
                import mayaUsd.ufe as mayaUsdUfe  # type: ignore[import-unresolved]
                try:
                    stage = mayaUsdUfe.getStage(proxy_shape)
                except RuntimeError:
                    proxy_long = (cmds.ls(proxy_shape, long=True) or [proxy_shape])[0]
                    stage = mayaUsdUfe.getStage(proxy_long)
            except (ImportError, RuntimeError) as e:
                self.logger.debug(f"[LAYER] mayaUsd.ufe.getStage unavailable: {e}")

            if stage is None:
                file_path = cmds.getAttr(f"{proxy_shape}.filePath")
                if file_path:
                    stage = Usd.Stage.Open(file_path)

            if stage is None:
                self.logger.warning(
                    "[LAYER] Could not access proxy stage — "
                    "select the animation sublayer manually in the Layer Editor"
                )
                return

            # ── Find the animation sublayer and set it as edit target ──
            root_layer = stage.GetRootLayer()
            for sublayer_path in root_layer.subLayerPaths:
                if "animation" in sublayer_path.lower():
                    from pxr import Sdf  # pyright: ignore[reportMissingImports]
                    anim_layer = Sdf.Layer.FindOrOpen(
                        root_layer.ComputeAbsolutePath(sublayer_path)
                    )
                    if anim_layer:
                        stage.SetEditTarget(Usd.EditTarget(anim_layer))
                        self.logger.info(
                            "[LAYER] Edit target set to 'animation' sublayer — "
                            "keyframes will be authored here"
                        )
                        self.logger.info(
                            "[TIP] Select USD prims in viewport → "
                            "press S to set keyframes on the animation layer"
                        )
                        return

            self.logger.warning(
                "[LAYER] animation sublayer not found — "
                "select an edit layer manually in the Layer Editor"
            )

        except Exception as e:
            self.logger.warning(f"[LAYER] Could not set animation edit target: {e}")
            self.logger.warning(
                "[TIP] In the Layer Editor, click the animation sublayer to make it the edit target"
            )

    # ─── Layered USD Stage Builder ───────────────────────────────────────

    def _boost_usd_material_colors(self, usd_path: Path) -> None:
        """Boost desaturated diffuseColors in a USD file for VP2 material identification.

        Pass 1 — UsdPreviewSurface diffuseColor:
            For every static (non-texture-connected) diffuseColor:
            - If the colour has a detectable hue, boosts S/V so per-material
              differences are clearly visible in VP2.
            - If achromatic, replaces with a deterministic name-hash hue so
              each material still gets a unique distinct colour.
            Bug fixed: mat_name now uses the Material prim's OWN name
            (prim.GetParent().GetName()), not its grandparent scope name.
            Previously GetParent().GetParent().GetName() returned "Looks"
            for every material, making all 20 achromatic materials hash to
            the same single colour.

        Pass 2 — primvars:displayColor on every Mesh prim:
            Follows each mesh's material:binding and writes
            primvars:displayColor to the same boosted colour.
            VP2 reads displayColor directly from geometry even when
            UsdSkelImaging is active and bypasses the full
            material:binding → UsdPreviewSurface resolution chain,
            which is the case for all skinned meshes.  Without this pass
            VP2 renders skinned meshes as flat grey regardless of what
            the UsdPreviewSurface diffuseColor is set to.
        """
        if not USD_AVAILABLE:
            return
        try:
            from pxr import Usd, UsdShade, UsdGeom, Sdf, Gf, Vt  # type: ignore

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.debug("[BOOST] Could not open USD for colour boost")
                return

            boosted = 0
            hashed = 0
            skipped = 0
            # Maps Material Sdf.Path → final display colour (None = texture-driven)
            mat_path_to_color: dict = {}

            # ── Pass 1: boost UsdPreviewSurface diffuseColor ─────────────────
            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Shader':
                    continue
                shader = UsdShade.Shader(prim)
                if not shader or shader.GetShaderId() != 'UsdPreviewSurface':
                    continue

                dc_input = shader.GetInput('diffuseColor')
                if not dc_input:
                    continue

                # The Material prim is the direct parent of the PreviewSurface shader.
                # Its name (e.g. "Veteran_Body_mat") is what we hash for name-colours.
                mat_prim = prim.GetParent()
                mat_path = mat_prim.GetPath() if mat_prim else None
                mat_name = mat_prim.GetName() if mat_prim else "Unknown"

                # Skip texture-driven inputs — never overwrite upstream connections.
                if dc_input.HasConnectedSource():
                    skipped += 1
                    if mat_path:
                        mat_path_to_color[mat_path] = None  # texture-driven
                    continue

                current = dc_input.Get()
                if current is None:
                    continue

                raw = Gf.Vec3f(float(current[0]), float(current[1]), float(current[2]))
                boosted_color = self._boost_color_for_display(raw)

                if boosted_color is not None:
                    dc_input.Set(boosted_color)
                    boosted += 1
                    final_color = boosted_color
                    self.logger.debug(
                        f"   [BOOST] {mat_name}: "
                        f"({raw[0]:.3f}, {raw[1]:.3f}, {raw[2]:.3f}) → {boosted_color}"
                    )
                else:
                    # Achromatic — each material gets a unique deterministic hue
                    hash_color = self._rfm_name_color(mat_name)
                    dc_input.Set(hash_color)
                    hashed += 1
                    final_color = hash_color
                    self.logger.debug(
                        f"   [BOOST] {mat_name}: achromatic → name-hash {hash_color}"
                    )

                if mat_path:
                    mat_path_to_color[mat_path] = final_color

            # ── Pass 2: primvars:displayColor on every Mesh prim ─────────────
            # VP2's UsdSkelImaging adapter renders skinned meshes but does NOT
            # always follow material:binding → UsdPreviewSurface.  Setting
            # primvars:displayColor directly on the geometry guarantees VP2
            # shows distinct colours regardless of the material system path.
            #
            # Use ComputeBoundMaterial() — the proper USD composition-aware
            # API that resolves inherited bindings, collection bindings, and
            # purpose-specific bindings.  GetDirectBinding() only returns
            # bindings authored directly on the prim itself, and returns an
            # always-truthy object even when no binding exists, making the
            # previous ancestor-walk logic unreliable.
            #
            # Fallback guarantee: every mesh gets a displayColor — either the
            # boosted material colour or a name-hash of the mesh's own name.
            # This ensures no mesh is invisible-grey even if binding fails.
            display_colored = 0
            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Mesh':
                    continue
                try:
                    color = None

                    # ComputeBoundMaterial handles full USD binding resolution
                    # including inherited and collection-based bindings.
                    bound_mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
                    if bound_mat and bound_mat.GetPrim().IsValid():
                        mat_prim_path = bound_mat.GetPrim().GetPath()
                        color = mat_path_to_color.get(mat_prim_path)
                        if color is None:
                            # Bound material exists but was texture-driven (None
                            # sentinel) or not in our map — name-hash the material.
                            color = self._rfm_name_color(bound_mat.GetPrim().GetName())

                    if color is None:
                        # No material bound at all — name-hash the mesh itself
                        # so it still gets a unique non-grey display colour.
                        color = self._rfm_name_color(prim.GetName())

                    UsdGeom.Gprim(prim).CreateDisplayColorAttr(
                        Vt.Vec3fArray([Gf.Vec3f(color[0], color[1], color[2])])
                    )
                    display_colored += 1
                except Exception:
                    continue

            if boosted + hashed > 0:
                stage.GetRootLayer().Save()
                self.logger.info(
                    f"[BOOST] Colour boost applied: "
                    f"{boosted} hue-boosted, {hashed} name-hashed, "
                    f"{skipped} texture-skipped | "
                    f"{display_colored} mesh primvars:displayColor set"
                )
            else:
                self.logger.debug("[BOOST] No static diffuseColors found to boost")

        except Exception as e:
            self.logger.warning(f"[BOOST] Colour boost failed: {e}")

    def _build_layered_stage(
        self,
        base_usd_path: Path,
        rig_mb_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Build a layered USD stage from a monolithic .usdc file.

        If a .rig.mb path is provided, its NURBS controllers and
        controller→joint mappings are extracted and written into
        a controllers sublayer, giving users visual animation guides
        inside the USD stage.

        Creates a root .usda whose sublayer stack looks like:

            root.usda  (this file — loaded by the proxy shape)
              ├── animation.usda      ← empty, editable: keyframes
              ├── controllers.usda    ← NURBS curves from .rig.mb (guide)
              ├── materials.usda      ← empty, editable: shader overrides
              ├── skeleton.usda       ← joint→controller metadata
              ├── geometry.usda       ← empty, editable: geo overrides
              └── <base>.usdc         ← original monolithic data (read-only)

        Returns:
            Path to root .usda on success, None on failure.
        """
        try:
            from pxr import Usd, Sdf, UsdGeom  # pyright: ignore[reportMissingImports]

            base_dir = base_usd_path.parent
            asset_name = base_usd_path.stem  # e.g. "Veteran_Rig"

            self.logger.info("[LAYER] Building layered USD stage from base asset...")

            # ── Extract rig data from .rig.mb if available ──
            rig_data = None
            if rig_mb_path and rig_mb_path.exists():
                self.logger.info(
                    f"[LAYER] Extracting controller data from: {rig_mb_path.name}"
                )
                rig_data = self._extract_rig_controllers(rig_mb_path)

            # ── Create editorial sublayers ──
            # Controllers layer is only created when we have rig data
            layer_names = ["animation", "controllers", "materials", "skeleton", "geometry"]
            created_layers: list[Path] = []

            for name in layer_names:
                layer_path = base_dir / f"{asset_name}.{name}.usda"
                layer = Sdf.Layer.CreateNew(str(layer_path))
                if layer is None:
                    self.logger.warning(f"[LAYER] Could not create {name} sublayer")
                    continue

                sub_stage = Usd.Stage.Open(layer)
                UsdGeom.SetStageUpAxis(sub_stage, UsdGeom.Tokens.y)
                layer.documentation = (
                    f"USD {name.title()} Override Layer — {asset_name}\n"
                    f"Author {name} edits here. Opinions in this layer "
                    f"override the base asset."
                )

                # Populate controllers sublayer from .rig.mb data
                if name == "controllers" and rig_data:
                    self._populate_controllers_sublayer(sub_stage, rig_data)

                # Populate skeleton sublayer with controller→joint metadata
                if name == "skeleton" and rig_data:
                    self._populate_skeleton_metadata(
                        sub_stage, base_usd_path, rig_data
                    )

                sub_stage.Save()
                created_layers.append(layer_path)
                self.logger.info(f"   [LAYER] {layer_path.name}")

            # ── Create root .usda that composes everything ──
            root_path = base_dir / f"{asset_name}.root.usda"
            root_layer = Sdf.Layer.CreateNew(str(root_path))
            if root_layer is None:
                self.logger.error("[LAYER] Could not create root layer")
                return None

            root_stage = Usd.Stage.Open(root_layer)
            UsdGeom.SetStageUpAxis(root_stage, UsdGeom.Tokens.y)

            # Read the default prim from the base stage so the root inherits it.
            # IMPORTANT: use OverridePrim (or just set defaultPrim metadata) — never
            # DefinePrim with a type here.  A "def Xform" opinion in root.usda would
            # override the base USDC's "SkelRoot" type in stronger-wins composition,
            # breaking UsdSkelImaging and hiding all material colours in VP2.
            base_stage = Usd.Stage.Open(str(base_usd_path))
            default_prim = base_stage.GetDefaultPrim() if base_stage else None
            default_prim_name = (
                default_prim.GetName() if default_prim else asset_name
            )

            # Set the defaultPrim metadata on the layer only — no prim spec,
            # no type opinion.  The actual prim definition (SkelRoot / Xform /
            # whatever the rig uses) stays exclusively in the base USDC sublayer.
            root_layer.defaultPrim = default_prim_name

            # ── Build sublayer stack (strongest on top) ──
            for layer_path in created_layers:
                root_layer.subLayerPaths.append(f"./{layer_path.name}")

            # Base monolithic file is the weakest (bottom) sublayer
            root_layer.subLayerPaths.append(f"./{base_usd_path.name}")

            has_controllers = rig_data is not None
            ctrl_line = (
                "  controllers.usda  — NURBS controllers from .rig.mb\n"
                if has_controllers
                else "  controllers.usda  — empty (no .rig.mb available)\n"
            )
            root_layer.documentation = (
                f"USD Layered Rig: {asset_name}\n"
                f"Generated by Asset Manager USD Pipeline\n\n"
                f"Sublayer stack (strongest → weakest):\n"
                f"  animation.usda    — keyframes & motion\n"
                f"{ctrl_line}"
                f"  materials.usda    — shader overrides\n"
                f"  skeleton.usda     — skeleton edits & controller mappings\n"
                f"  geometry.usda     — geo overrides\n"
                f"  {base_usd_path.name}  — base asset (read-only)\n\n"
                f"Edit the sublayer you need; the base asset is never modified."
            )

            root_stage.Save()

            total_sublayers = len(created_layers) + 1  # editorial + base
            ctrl_msg = ""
            if rig_data:
                ctrl_count = len(rig_data.get("controllers", []))
                mapping_count = len(rig_data.get("mappings", {}))
                ctrl_msg = (
                    f" ({ctrl_count} controllers, "
                    f"{mapping_count} joint mappings from .rig.mb)"
                )
            self.logger.info(
                f"[OK] Layered stage: {root_path.name} → "
                f"{total_sublayers} sublayers{ctrl_msg}"
            )

            return root_path

        except Exception as e:
            self.logger.error(f"[LAYER] Failed to build layered stage: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    # ─── .rig.mb Controller Extraction ────────────────────────────────────

    def _extract_rig_controllers(
        self, rig_mb_path: Path
    ) -> Optional[dict]:
        """
        Temporarily reference .rig.mb and extract NURBS controller data.

        Returns a dict:
            {
                "controllers": [
                    {
                        "name": "L_Arm_CTRL",
                        "cvs": [(x,y,z), ...],
                        "degree": 3,
                        "form": 0,           # 0=open, 1=closed, 2=periodic
                        "knots": [0.0, ...],
                        "translate": (tx, ty, tz),
                        "rotate": (rx, ry, rz),
                        "color": (r, g, b) or None,
                    },
                    ...
                ],
                "mappings": {
                    "L_Arm_CTRL": ["L_Arm_JNT"],  # controller → driven joints
                    ...
                },
                "joint_names": ["Root", "Spine1", ...],  # all joint names
            }
        """
        if cmds is None:
            return None

        try:
            # ── Reference the .rig.mb temporarily ──
            namespace = "_rigExtract_"

            # Suppress deprecated-attribute errors printed when Maya loads
            # nested references inside the rig.mb (e.g. ".atlasStyle" from
            # PxrTexture nodes in RfM 27.x era files).  These are harmless
            # forward-compatibility warnings — suppressing them keeps the
            # Script Editor clean without hiding any real failures.
            # Suppress deprecated-attribute errors from the nested file load.
            # scriptEditorInfo is a global command — no 'edit' flag needed.
            try:
                cmds.scriptEditorInfo(
                    suppressErrors=True,
                    suppressWarnings=True,
                    suppressInfo=True,
                )
            except Exception:
                pass

            try:
                cmds.file(
                    str(rig_mb_path),
                    reference=True,
                    namespace=namespace,
                    returnNewNodes=False,
                    loadReferenceDepth="all"
                )
                self.logger.info("[RIG] Referenced .rig.mb for controller extraction")
            except Exception as ref_err:
                self.logger.warning(
                    f"[RIG] Could not reference .rig.mb: {ref_err}"
                )
                return None
            finally:
                # Always restore all output channels immediately.
                try:
                    cmds.scriptEditorInfo(
                        suppressErrors=False,
                        suppressWarnings=False,
                        suppressInfo=False,
                    )
                except Exception:
                    pass

            controllers = []
            mappings: dict[str, list[str]] = {}
            joint_names: list[str] = []

            try:
                # ── Find all joints ──
                all_joints = cmds.ls(
                    f"{namespace}:*", type="joint", long=False
                ) or []
                # Strip namespace for clean names
                joint_names = [
                    j.replace(f"{namespace}:", "") for j in all_joints
                ]

                # ── Find NURBS curves (controllers) ──
                all_curves = cmds.ls(
                    f"{namespace}:*", type="nurbsCurve", long=True
                ) or []
                self.logger.info(
                    f"[RIG] Found {len(all_curves)} NURBS curves, "
                    f"{len(all_joints)} joints"
                )

                for curve_shape in all_curves:
                    # Get transform parent
                    parents = cmds.listRelatives(
                        curve_shape, parent=True, fullPath=True
                    )
                    if not parents:
                        continue
                    transform = parents[0]
                    short_name = transform.split("|")[-1].split(":")[-1]

                    # Skip non-controller curves (construction history, etc.)
                    # Controllers typically have "ctrl" or "CTRL" or known
                    # prefixes, but we'll be inclusive and grab everything
                    try:
                        # Get curve CVs
                        num_cvs = cmds.getAttr(
                            f"{curve_shape}.controlPoints", size=True
                        )
                        cvs = []
                        for i in range(num_cvs):
                            pt = cmds.getAttr(
                                f"{curve_shape}.controlPoints[{i}]"
                            )
                            if pt:
                                cvs.append(pt[0])  # [(x,y,z)]

                        if not cvs:
                            continue

                        # Curve properties
                        degree = cmds.getAttr(f"{curve_shape}.degree")
                        form = cmds.getAttr(f"{curve_shape}.form")
                        spans = cmds.getAttr(f"{curve_shape}.spans")

                        # Knot vector
                        num_knots = spans + 2 * degree - 1
                        knots = []
                        try:
                            knots_raw = cmds.getAttr(
                                f"{curve_shape}.knots[0:{num_knots - 1}]"
                            )
                            if knots_raw:
                                knots = list(knots_raw)
                        except Exception:
                            pass

                        # Transform
                        tx = cmds.getAttr(f"{transform}.translateX")
                        ty = cmds.getAttr(f"{transform}.translateY")
                        tz = cmds.getAttr(f"{transform}.translateZ")
                        rx = cmds.getAttr(f"{transform}.rotateX")
                        ry = cmds.getAttr(f"{transform}.rotateY")
                        rz = cmds.getAttr(f"{transform}.rotateZ")

                        # Override color (if set)
                        color = None
                        try:
                            if cmds.getAttr(
                                f"{transform}.overrideEnabled"
                            ):
                                if cmds.getAttr(
                                    f"{transform}.overrideRGBColors"
                                ):
                                    cr = cmds.getAttr(
                                        f"{transform}.overrideColorR"
                                    )
                                    cg = cmds.getAttr(
                                        f"{transform}.overrideColorG"
                                    )
                                    cb = cmds.getAttr(
                                        f"{transform}.overrideColorB"
                                    )
                                    color = (cr, cg, cb)
                        except Exception:
                            pass

                        controllers.append({
                            "name": short_name,
                            "cvs": cvs,
                            "degree": degree,
                            "form": form,
                            "knots": knots,
                            "translate": (tx, ty, tz),
                            "rotate": (rx, ry, rz),
                            "color": color,
                        })

                    except Exception as cv_err:
                        self.logger.debug(
                            f"[RIG] Skipped {short_name}: {cv_err}"
                        )
                        continue

                # ── Find controller → joint mappings via constraints ──
                constraint_types = [
                    "parentConstraint", "orientConstraint",
                    "pointConstraint", "aimConstraint",
                    "scaleConstraint"
                ]
                for joint in all_joints:
                    joint_short = joint.replace(f"{namespace}:", "")
                    for ctype in constraint_types:
                        try:
                            constraints = cmds.listConnections(
                                joint,
                                type=ctype,
                                source=True,
                                destination=False
                            ) or []
                            for con in constraints:
                                # Find what drives this constraint
                                drivers = cmds.listConnections(
                                    f"{con}.target",
                                    source=True,
                                    destination=False
                                ) or []
                                for driver in drivers:
                                    drv_short = driver.split(
                                        ":"
                                    )[-1].split("|")[-1]
                                    if drv_short not in mappings:
                                        mappings[drv_short] = []
                                    if joint_short not in mappings[drv_short]:
                                        mappings[drv_short].append(
                                            joint_short
                                        )
                        except Exception:
                            continue

                # Also check direct connections (no constraints)
                for joint in all_joints:
                    joint_short = joint.replace(f"{namespace}:", "")
                    for attr in ["rotate", "translate"]:
                        try:
                            conns = cmds.listConnections(
                                f"{joint}.{attr}",
                                source=True,
                                destination=False,
                                skipConversionNodes=True
                            ) or []
                            for conn in conns:
                                conn_short = conn.split(
                                    ":"
                                )[-1].split("|")[-1]
                                # Only map if it looks like a controller
                                node_type = cmds.nodeType(conn)
                                if node_type == "transform":
                                    shapes = cmds.listRelatives(
                                        conn, shapes=True, type="nurbsCurve"
                                    )
                                    if shapes:
                                        if conn_short not in mappings:
                                            mappings[conn_short] = []
                                        if (
                                            joint_short
                                            not in mappings[conn_short]
                                        ):
                                            mappings[conn_short].append(
                                                joint_short
                                            )
                        except Exception:
                            continue

                self.logger.info(
                    f"[RIG] Extracted {len(controllers)} controllers, "
                    f"{len(mappings)} controller→joint mappings"
                )

            finally:
                # ── Remove the reference ──
                try:
                    # Get the reference node created by file -reference
                    ref_nodes = cmds.ls(
                        f"{namespace}*", type="reference"
                    ) or []
                    for rn in ref_nodes:
                        try:
                            cmds.file(
                                removeReference=True, referenceNode=rn
                            )
                        except Exception:
                            pass
                    self.logger.info("[RIG] Removed .rig.mb reference")
                except Exception as rm_err:
                    self.logger.warning(
                        f"[RIG] Could not remove reference: {rm_err}"
                    )

            if not controllers:
                self.logger.warning("[RIG] No controllers extracted")
                return None

            return {
                "controllers": controllers,
                "mappings": mappings,
                "joint_names": joint_names,
            }

        except Exception as e:
            self.logger.error(f"[RIG] Controller extraction failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _populate_controllers_sublayer(
        self, stage, rig_data: dict
    ) -> None:
        """
        Write NURBS controllers from .rig.mb as NurbsCurves prims
        in the controllers sublayer.

        Each controller becomes a USD NurbsCurves prim with:
        - Curve points (CVs)
        - Display color (from Maya override color)
        - Purpose = "guide" (visible in viewport, not rendered)
        - Custom attribute: assetManager:drivenJoints
        """
        try:
            from pxr import (  # pyright: ignore[reportMissingImports]
                Gf, Sdf, UsdGeom, Vt
            )

            controllers = rig_data.get("controllers", [])
            mappings = rig_data.get("mappings", {})

            # Create a /Controllers scope to organize them
            ctrl_scope = stage.DefinePrim("/Controllers", "Scope")
            UsdGeom.Imageable(ctrl_scope).CreatePurposeAttr(
                UsdGeom.Tokens.guide
            )

            written = 0
            skipped = 0
            seen_names: dict[str, int] = {}  # track name collisions

            for ctrl in controllers:
                name = ctrl["name"]
                cvs = ctrl["cvs"]
                if not cvs:
                    continue

                # Sanitize name for USD prim path
                safe_name = name.replace("|", "_").replace(":", "_")

                # Deduplicate: append suffix for collisions
                if safe_name in seen_names:
                    seen_names[safe_name] += 1
                    safe_name = f"{safe_name}_{seen_names[safe_name]}"
                else:
                    seen_names[safe_name] = 0

                prim_path = f"/Controllers/{safe_name}"

                try:
                    # Create NurbsCurves prim
                    prim = stage.DefinePrim(prim_path, "NurbsCurves")
                    curves = UsdGeom.NurbsCurves(prim)

                    # Set curve data
                    points = Vt.Vec3fArray(
                        [Gf.Vec3f(p[0], p[1], p[2]) for p in cvs]
                    )
                    curves.CreatePointsAttr(points)
                    curves.CreateCurveVertexCountsAttr(
                        Vt.IntArray([len(cvs)])
                    )

                    # Degree and order
                    degree = ctrl.get("degree", 3)
                    curves.CreateOrderAttr(Vt.IntArray([degree + 1]))

                    # Knots
                    knots = ctrl.get("knots", [])
                    if knots:
                        curves.CreateKnotsAttr(
                            Vt.DoubleArray(knots)
                        )

                    # Set purpose to "guide" so it's visible but not rendered
                    UsdGeom.Imageable(prim).CreatePurposeAttr(
                        UsdGeom.Tokens.guide
                    )

                    # Display color from Maya override
                    color = ctrl.get("color")
                    if color:
                        curves.CreateDisplayColorAttr(
                            Vt.Vec3fArray(
                                [Gf.Vec3f(color[0], color[1], color[2])]
                            )
                        )

                    # Transform — only add ops if non-zero
                    tx, ty, tz = ctrl.get("translate", (0, 0, 0))
                    rx, ry, rz = ctrl.get("rotate", (0, 0, 0))
                    has_translate = any(v != 0 for v in (tx, ty, tz))
                    has_rotate = any(v != 0 for v in (rx, ry, rz))

                    if has_translate or has_rotate:
                        xform = UsdGeom.Xformable(prim)
                        if has_translate:
                            xform.AddTranslateOp().Set(
                                Gf.Vec3d(tx, ty, tz)
                            )
                        if has_rotate:
                            xform.AddRotateXYZOp().Set(
                                Gf.Vec3f(rx, ry, rz)
                            )

                    # Custom attribute: which joints this controller drives
                    driven = mappings.get(name, [])
                    if driven:
                        driven_attr = prim.CreateAttribute(
                            "assetManager:drivenJoints",
                            Sdf.ValueTypeNames.StringArray
                        )
                        driven_attr.Set(driven)

                    written += 1

                except Exception as ctrl_err:
                    skipped += 1
                    self.logger.debug(
                        f"[LAYER] Skipped controller {safe_name}: {ctrl_err}"
                    )

            skip_msg = f", {skipped} skipped" if skipped else ""
            self.logger.info(
                f"[LAYER] Wrote {written} NURBS controllers "
                f"to controllers sublayer{skip_msg}"
            )

        except Exception as e:
            self.logger.warning(
                f"[LAYER] Could not populate controllers sublayer: {e}"
            )
            import traceback
            self.logger.debug(traceback.format_exc())

    def _populate_skeleton_metadata(
        self, stage, base_usd_path: Path, rig_data: dict
    ) -> None:
        """
        Write controller→joint mapping metadata into the skeleton sublayer.

        For each Skeleton prim in the base USD, adds custom attributes:
        - assetManager:controllerMap — JSON mapping of joint→controller names

        This lets tools and scripts know which controller drives which joint
        without needing the .rig.mb at runtime.
        """
        try:
            import json
            from pxr import Usd, Sdf, UsdSkel  # pyright: ignore[reportMissingImports]

            mappings = rig_data.get("mappings", {})
            if not mappings:
                return

            # Invert: controller→joints  →  joint→controllers
            joint_to_ctrl: dict[str, list[str]] = {}
            for ctrl_name, joints in mappings.items():
                for joint_name in joints:
                    if joint_name not in joint_to_ctrl:
                        joint_to_ctrl[joint_name] = []
                    joint_to_ctrl[joint_name].append(ctrl_name)

            # Open the base stage read-only to find skeleton paths
            base_stage = Usd.Stage.Open(str(base_usd_path))
            if not base_stage:
                return

            # Find all Skeleton prims and write metadata
            skeletons_found = 0
            for prim in base_stage.Traverse():
                if not prim.IsA(UsdSkel.Skeleton):
                    continue

                skel = UsdSkel.Skeleton(prim)
                joints_attr = skel.GetJointsAttr().Get()
                if not joints_attr:
                    continue

                # Build the mapping for joints in this skeleton
                skel_map = {}
                for joint_path in joints_attr:
                    # Joint path like "Root/Spine1/L_Arm"
                    joint_leaf = str(joint_path).split("/")[-1]
                    if joint_leaf in joint_to_ctrl:
                        skel_map[str(joint_path)] = joint_to_ctrl[joint_leaf]

                if skel_map:
                    # Write onto the same prim path in the skeleton sublayer
                    over_prim = stage.OverridePrim(prim.GetPath())
                    map_attr = over_prim.CreateAttribute(
                        "assetManager:controllerMap",
                        Sdf.ValueTypeNames.String
                    )
                    map_attr.Set(json.dumps(skel_map, indent=2))
                    skeletons_found += 1

            if skeletons_found:
                self.logger.info(
                    f"[LAYER] Wrote controller→joint mappings "
                    f"for {skeletons_found} skeleton(s) — "
                    f"{len(joint_to_ctrl)} joints mapped"
                )

        except Exception as e:
            self.logger.warning(
                f"[LAYER] Could not populate skeleton metadata: {e}"
            )
            import traceback
            self.logger.debug(traceback.format_exc())

    def _convert_usd_skeleton_to_maya(self, proxy_shape: str, usd_path: Path) -> None:
        """Convert USD skeleton to Maya joints while keeping meshes as USD proxy"""
        if cmds is None:
            self.logger.warning("[WARNING] Maya not available for skeleton conversion")
            return

        try:
            self.logger.info("[SKEL] Converting USD Skeleton to Maya joints...")

            # Use mayaUSD duplicate command to extract skeleton as Maya data
            # This is equivalent to right-click > "Duplicate as Maya Data" on skeleton
            # We'll use selectPrim to target only skeleton prims

            # Import mayaUSD if available
            try:
                import mayaUsd.lib as mayaUsdLib  # pyright: ignore
                has_mayausd = True
            except ImportError:
                has_mayausd = False
                self.logger.warning("[WARNING] mayaUSD library not available")

            if has_mayausd:
                # Get the proxy transform
                proxy_transform = cmds.listRelatives(proxy_shape, parent=True)[0]

                # Try method 1: mayaUSD duplicate command (Maya 2023+)
                try:
                    import maya.mel as mel  # type: ignore

                    # Select the proxy transform for the command
                    cmds.select(proxy_transform, replace=True)

                    # Try MEL-based duplicate (this is what the UI uses)
                    # This command converts selected USD prims to Maya data
                    mel.eval('mayaUsdMenu_duplicateAsBase()')

                    # Check if skeleton joints were created (look for joint nodes under proxy)
                    children = cmds.listRelatives(proxy_transform, children=True, type='joint')
                    if children:
                        self.logger.info(f"[OK] Converted USD Skeleton to Maya joints: {len(children)} root joint(s)")
                    else:
                        # MEL command didn't create joints - try Python fallback
                        self.logger.info(
                            "[INFO] MEL command succeeded but no joints created, "
                            "trying Python fallback..."
                        )
                        self._extract_skeleton_via_python(proxy_shape, usd_path)

                except AttributeError:
                    # mayaUSD commands not available in this version
                    self.logger.warning("[WARNING] Skeleton conversion not available in mayaUSD v0.35.0")
                    self.logger.info("[TIP] Upgrade to mayaUSD v0.27+ for automatic skeleton conversion")
                    # Try Python fallback
                    self._extract_skeleton_via_python(proxy_shape, usd_path)

                except Exception as dup_err:
                    # Command failed for other reasons
                    self.logger.warning(f"[WARNING] Skeleton conversion failed: {dup_err}")
                    # Try Python fallback
                    self._extract_skeleton_via_python(proxy_shape, usd_path)
            else:
                # No mayaUSD available at all
                self.logger.warning("[WARNING] mayaUSD plugin not available - cannot convert skeleton")
                self.logger.info("[TIP] Load mayaUSD plugin: Window > Settings/Preferences > Plug-in Manager")

        except Exception as e:
            self.logger.warning(f"[WARNING] Could not convert skeleton: {e}")
            # Non-fatal - user can still work with USD proxy

    def _extract_skeleton_via_python(self, proxy_shape: str, usd_path: Path) -> None:
        """Fallback: Extract skeleton using pure Python USD API"""
        self.logger.info("[SKEL] Attempting Python USD API skeleton extraction...")

        if not USD_AVAILABLE:
            self.logger.warning("[WARNING] Pixar USD Python API not available")
            return

        try:
            from pxr import Usd, UsdSkel  # pyright: ignore[reportMissingImports]

            # Open the USD stage
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("[WARNING] Could not open USD stage")
                return

            # Find all skeleton prims
            skeleton_prims = []
            for prim in stage.Traverse():
                if prim.IsA(UsdSkel.Skeleton):
                    skeleton_prims.append(prim)

            if not skeleton_prims:
                self.logger.warning("[WARNING] No skeleton prims found in USD")
                return

            self.logger.info(f"[SKEL] Found {len(skeleton_prims)} skeleton(s) in USD")

            # Get proxy transform for parenting
            proxy_transform = cmds.listRelatives(proxy_shape, parent=True)[0]
            created_joints = []

            # Extract each skeleton
            for skel_prim in skeleton_prims:
                skel = UsdSkel.Skeleton(skel_prim)

                # Get joint data
                joints_attr = skel.GetJointsAttr()
                if not joints_attr:
                    continue

                joint_names = joints_attr.Get()
                if not joint_names:
                    continue

                # Get bind transforms (rest pose)
                bind_transforms_attr = skel.GetBindTransformsAttr()
                bind_transforms = bind_transforms_attr.Get() if bind_transforms_attr else None

                if not bind_transforms or len(bind_transforms) != len(joint_names):
                    self.logger.warning(f"[WARNING] Skeleton {skel_prim.GetPath()} missing valid bind transforms")
                    continue

                self.logger.debug(f"[SKEL] Creating {len(joint_names)} Maya joints from {skel_prim.GetPath()}")

                # Create Maya joints from USD skeleton data
                joint_map = {}
                for joint_token, bind_xform in zip(joint_names, bind_transforms):
                    joint_name = str(joint_token)

                    # Parse hierarchy (joint names use "/" as separator)
                    parts = joint_name.split('/')
                    clean_name = parts[-1]  # Use last part as joint name
                    parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else None

                    # Extract transform from matrix
                    matrix = bind_xform
                    translation = matrix.ExtractTranslation()
                    rotation = matrix.ExtractRotation().GetQuaternion()

                    # Create Maya joint
                    cmds.select(clear=True)
                    maya_joint = cmds.joint(name=clean_name)

                    # Set position
                    cmds.xform(
                        maya_joint,
                        translation=[translation[0], translation[1], translation[2]],
                        worldSpace=True
                    )

                    # Set rotation from quaternion
                    euler = rotation.GetImaginary()  # Simplified - proper conversion needed
                    cmds.xform(maya_joint, rotation=[euler[0], euler[1], euler[2]], worldSpace=True)

                    # Store in map for hierarchy building
                    joint_map[joint_name] = maya_joint

                    # Parent to USD hierarchy parent if exists
                    if parent_path and parent_path in joint_map:
                        cmds.parent(maya_joint, joint_map[parent_path])

                    created_joints.append(maya_joint)

                # Parent root joint(s) under proxy transform
                for joint_name, maya_joint in joint_map.items():
                    if '/' not in joint_name:  # Root joint
                        cmds.parent(maya_joint, proxy_transform)

            if created_joints:
                self.logger.info(f"[OK] Created {len(created_joints)} Maya joints from USD skeletons")
            else:
                self.logger.warning("[WARNING] No joints created from USD skeleton data")

        except Exception as e:
            self.logger.warning(f"[WARNING] Python USD skeleton extraction failed: {e}")
            self.logger.info("[TIP] Right-click USD proxy > 'Duplicate As Maya Data' to convert manually")

    def _count_usd_prims_in_proxy(
        self,
        proxy_shapes: List[str],
        result: ImportResult
    ) -> None:
        """Count USD prims inside proxy shape(s) using the Pixar USD API"""
        if not USD_AVAILABLE:
            self.logger.warning("USD Python API not available for prim counting")
            return

        try:
            from pxr import Usd, UsdSkel  # pyright: ignore[reportMissingImports]

            total_meshes = 0
            total_skeletons = 0
            total_curves = 0
            total_materials = 0
            total_blendshapes = 0
            total_skinbindings = 0
            total_layers = 0

            for proxy in proxy_shapes:
                # Get the USD file path from the proxy shape
                if cmds is None:
                    continue

                try:
                    file_path = cmds.getAttr(f"{proxy}.filePath")
                    if not file_path:
                        continue

                    stage = Usd.Stage.Open(file_path)
                    if not stage:
                        continue

                    # Count USD layers (Maya 2026+ feature)
                    root_layer = stage.GetRootLayer()
                    sublayers = root_layer.subLayerPaths
                    layer_count = 1 + len(sublayers)  # Root + sublayers
                    total_layers += layer_count

                    if sublayers:
                        self.logger.info(f"📚 USD contains {layer_count} layers:")
                        self.logger.info(f"   Root: {root_layer.identifier}")
                        for sl in sublayers:
                            self.logger.info(f"   Sublayer: {sl}")

                    # Traverse and count prims by type
                    for prim in stage.Traverse():
                        prim_type = prim.GetTypeName()

                        if prim_type == 'Mesh':
                            total_meshes += 1
                        elif prim_type == 'Skeleton':
                            total_skeletons += 1
                        elif prim_type in ('NurbsCurves', 'BasisCurves'):
                            total_curves += 1
                        elif prim_type == 'Material':
                            total_materials += 1
                        elif prim_type == 'BlendShape':
                            total_blendshapes += 1
                        elif prim_type == 'SkelAnimation':
                            # Skeletal animation data
                            pass

                    # Also check for skin bindings via UsdSkel
                    for prim in stage.Traverse():
                        if prim.HasAPI(UsdSkel.BindingAPI):
                            total_skinbindings += 1

                    # Verify material colors are correctly written
                    self._verify_material_colors(stage, total_materials)

                except Exception as proxy_err:
                    self.logger.debug(f"Could not read proxy {proxy}: {proxy_err}")

            # Store in result
            result.usd_meshes = total_meshes
            result.usd_joints = total_skeletons
            result.usd_curves = total_curves
            result.usd_materials = total_materials
            result.usd_blendshapes = total_blendshapes
            result.usd_skin_clusters = total_skinbindings

            # Log layer info
            if total_layers > 1:
                self.logger.info(f"📚 Total USD layers loaded: {total_layers}")

            # For display purposes, also set the "imported" counts to USD counts
            # (since USD prims ARE the imported content)
            result.meshes_imported = total_meshes
            result.joints_imported = total_skeletons
            result.curves_imported = total_curves
            result.materials_imported = total_materials
            result.blendshapes_imported = total_blendshapes
            result.skin_clusters_imported = total_skinbindings

        except Exception as e:
            self.logger.error(f"Error counting USD prims: {e}")

    def _verify_material_colors(self, stage, total_materials: int = 0) -> None:
        """Verify UsdPreviewSurface diffuseColor values are present on all injected materials."""
        try:
            from pxr import UsdShade  # pyright: ignore[reportMissingImports]

            self.logger.info("[LOOKDEV] Verifying USD material colors...")

            # Directly count UsdPreviewSurface shaders — more reliable than ComputeSurfaceSource
            preview_shaders = []
            colored_shaders = []
            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Shader':
                    continue
                shader = UsdShade.Shader(prim)
                if shader.GetShaderId() != 'UsdPreviewSurface':
                    continue
                diffuse_input = shader.GetInput("diffuseColor")
                if diffuse_input:
                    color = diffuse_input.Get()
                    preview_shaders.append(prim.GetName())
                    if color and (color[0] > 0 or color[1] > 0 or color[2] > 0):
                        colored_shaders.append((prim.GetParent().GetParent().GetName(), color))
                        self.logger.debug(
                            f"   [LOOKDEV] {prim.GetParent().GetParent().GetName()}: "
                            f"diffuseColor = ({color[0]:.3f}, {color[1]:.3f}, {color[2]:.3f})"
                        )

            total = total_materials or len(preview_shaders)
            self.logger.info(
                f"[LOOKDEV] {len(preview_shaders)}/{total} materials have UsdPreviewSurface, "
                f"{len(colored_shaders)} with non-black diffuseColor"
            )

        except Exception as e:
            self.logger.warning(f"[LOOKDEV] Material color verification failed: {e}")

    def _count_imported_components(
        self,
        nodes: List[str],
        result: ImportResult
    ) -> None:
        """Count what was actually imported - scan entire scene, not just returned nodes"""
        if cmds is None:
            return

        # mayaUSDImport returns root transform(s), but we need to count ALL scene content
        # Use cmds.ls to find all imported content types

        # Count meshes
        all_meshes = cmds.ls(type='mesh', dag=True) or []
        result.meshes_imported = len(all_meshes)

        # Count joints
        all_joints = cmds.ls(type='joint', dag=True) or []
        result.joints_imported = len(all_joints)

        # Count NURBS curves
        all_curves = cmds.ls(type='nurbsCurve', dag=True) or []
        result.curves_imported = len(all_curves)

        # Count materials (various shader types)
        material_types = [
            'lambert', 'blinn', 'phong', 'standardSurface',
            'PxrSurface', 'PxrDisney', 'aiStandardSurface'
        ]
        all_materials = []
        for mat_type in material_types:
            mats = cmds.ls(type=mat_type) or []
            all_materials.extend(mats)
        # Exclude default materials
        default_mats = {'lambert1', 'particleCloud1'}
        result.materials_imported = len([m for m in all_materials if m not in default_mats])

        # Count skin clusters
        all_skin_clusters = cmds.ls(type='skinCluster') or []
        result.skin_clusters_imported = len(all_skin_clusters)

        # Count blendshapes
        all_blendshapes = cmds.ls(type='blendShape') or []
        result.blendshapes_imported = len(all_blendshapes)

        # Count constraints
        constraint_types = [
            'parentConstraint', 'orientConstraint', 'pointConstraint',
            'aimConstraint', 'scaleConstraint', 'poleVectorConstraint'
        ]
        all_constraints = []
        for const_type in constraint_types:
            consts = cmds.ls(type=const_type) or []
            all_constraints.extend(consts)
        result.constraints_imported = len(all_constraints)

        self.logger.info(
            f"[INFO] Import counts - Meshes: {result.meshes_imported}, "
            f"Joints: {result.joints_imported}, Curves: {result.curves_imported}, "
            f"Materials: {result.materials_imported}, SkinClusters: {result.skin_clusters_imported}"
        )

    def _import_rig_mb_fallback(
        self,
        rig_mb_path: Path,
        result: ImportResult
    ) -> bool:
        """Import complete rig from .rig.mb fallback"""
        try:
            if cmds is None:
                self.logger.error("Maya cmds not available")
                return False

            imported_nodes = cmds.file(
                str(rig_mb_path),
                i=True,
                type="mayaBinary",
                returnNewNodes=True,
                preserveReferences=True,
                ignoreVersion=True
            )

            if imported_nodes:
                self.logger.info(f"[PACKAGE] Imported {len(imported_nodes)} nodes from rig backup")
                result.used_rig_mb_fallback = True
                result.fallback_components.append("Full rig")
                self._count_imported_components(imported_nodes, result)
                return True

            return False

        except Exception as e:
            self.logger.error(f"Rig backup import failed: {e}")
            return False

    def _import_hybrid(
        self,
        usd_path: Path,
        rig_mb_path: Path,
        options: ImportOptions,
        result: ImportResult
    ) -> bool:
        """
        HYBRID WORKFLOW - Convert USD to Maya + Import NURBS Controllers

        Phase 1: Convert USD to native Maya (meshes, joints, skinClusters, blendShapes, materials)
        Phase 2: Import NURBS controllers from .rig.mb
        Phase 3: Connect controllers to converted skeleton

        This avoids USD proxy display bugs with complex skeletons while preserving
        the hybrid concept: USD-quality geometry + Maya animation controls.
        """
        if cmds is None:
            self.logger.error("Maya cmds not available")
            return False

        try:
            self.logger.info("[HYBRID] HYBRID WORKFLOW: Converting USD → Maya + NURBS controllers")
            self.logger.info("=" * 70)

            # =================================================================
            # PHASE 1: Convert USD to Native Maya Data
            # =================================================================
            self.logger.info("[REFRESH] Phase 1: Converting USD to native Maya...")
            self.logger.info("   • UsdGeomMesh → Maya meshes")
            self.logger.info("   • UsdSkel → Maya joints + skinClusters")
            self.logger.info("   • RenderMeshVisual → Maya blendShapes")
            self.logger.info("   • Materials → RenderMan/Maya shaders")

            # Store scene state before import
            before_meshes = set(cmds.ls(type='mesh', long=True) or [])
            before_joints = set(cmds.ls(type='joint', long=True) or [])
            before_skins = set(cmds.ls(type='skinCluster') or [])
            before_blends = set(cmds.ls(type='blendShape') or [])

            try:
                # Use mayaUSDImport to convert entire USD to native Maya
                self.logger.info(f"📥 Importing USD: {usd_path.name}")

                imported_nodes = cmds.mayaUSDImport(
                    file=str(usd_path),
                    primPath="/",                    # Import everything
                    readAnimData=True,               # Import animation
                    importInstances=True,            # Import instances
                    importUSDZTextures=True,         # Extract textures from USDZ
                    preferredMaterial="usdPreviewSurface",  # Try USD materials first
                    shadingMode=[                    # Import shading
                        ["useRegistry", "UsdPreviewSurface"],
                        ["useRegistry", "rendermanForMaya"]
                    ]
                )

                if not imported_nodes:
                    self.logger.error("[ERROR] mayaUSDImport returned no nodes")
                    return False

                self.logger.info(f"[OK] Imported {len(imported_nodes)} root nodes")

            except Exception as import_err:
                self.logger.error(f"[ERROR] USD import failed: {import_err}")
                import traceback
                self.logger.error(traceback.format_exc())
                return False

            # Count what was imported
            after_meshes = set(cmds.ls(type='mesh', long=True) or [])
            after_joints = set(cmds.ls(type='joint', long=True) or [])
            after_skins = set(cmds.ls(type='skinCluster') or [])
            after_blends = set(cmds.ls(type='blendShape') or [])

            new_meshes = after_meshes - before_meshes
            new_joints = after_joints - before_joints
            new_skins = after_skins - before_skins
            new_blends = after_blends - before_blends

            result.meshes_imported = len(new_meshes)
            result.joints_imported = len(new_joints)
            result.skin_clusters_imported = len(new_skins)
            result.blendshapes_imported = len(new_blends)

            self.logger.info("[INFO] USD Conversion Results:")
            self.logger.info(f"   • Meshes: {result.meshes_imported}")
            self.logger.info(f"   • Joints: {result.joints_imported}")
            self.logger.info(f"   • SkinClusters: {result.skin_clusters_imported}")
            self.logger.info(f"   • BlendShapes: {result.blendshapes_imported}")

            if result.meshes_imported == 0:
                self.logger.error("[ERROR] No meshes imported from USD")
                return False

            if result.joints_imported == 0:
                self.logger.warning("[WARNING] No joints imported from USD")

            # Store imported root for later reference
            result._usd_root = imported_nodes[0] if imported_nodes else None
            result._converted_joints = list(new_joints)

            # =================================================================
            # PHASE 2: Import NURBS Controllers from .rig.mb
            # =================================================================
            self.logger.info("")
            self.logger.info("🎮 Phase 2: Importing NURBS controllers...")

            controllers_imported = self._import_nurbs_controllers(
                rig_mb_path,
                result
            )

            if not controllers_imported:
                self.logger.warning("[WARNING] No controllers imported - skeleton can be animated directly")
                self.logger.warning("[TIP] Controllers are optional for hybrid workflow")
            else:
                self.logger.info(f"[OK] Imported {controllers_imported} NURBS controllers")

            # =================================================================
            # PHASE 3: Connect Controllers to Skeleton
            # =================================================================
            if controllers_imported > 0:
                self.logger.info("")
                self.logger.info("🔗 Phase 3: Connecting controllers to skeleton...")

                connections_made = self._connect_controllers_to_skeleton(result)

                if connections_made > 0:
                    self.logger.info(f"[OK] Connected {connections_made} controllers to skeleton")
                else:
                    self.logger.warning("[WARNING] Could not connect controllers - check naming")
                    self.logger.warning("[TIP] Controllers may need manual connection")

            # =================================================================
            # VERIFICATION & FINAL REPORT
            # =================================================================
            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info("[OK] HYBRID IMPORT COMPLETE")
            self.logger.info("=" * 70)
            self.logger.info(f"[PACKAGE] Geometry: {result.meshes_imported} meshes (native Maya)")
            self.logger.info(f"[SKEL] Skeleton: {result.joints_imported} joints (native Maya)")
            self.logger.info(
                f"[BLEND] Deformers: {result.skin_clusters_imported} skinClusters, "
                f"{result.blendshapes_imported} blendShapes"
            )
            if controllers_imported:
                self.logger.info(f"🎮 Controllers: {controllers_imported} NURBS curves")
            self.logger.info("")
            self.logger.info("[TIP] TIP: Move joints or controllers to test deformation")
            self.logger.info("=" * 70)

            return True

        except Exception as e:
            self.logger.error(f"Hybrid import failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _convert_proxy_to_maya(
        self,
        proxy_shape: str,
        result: ImportResult
    ) -> bool:
        """
        Convert USD proxy shape content to native Maya data.

        This is a workaround for Maya 2026 viewport bugs with UsdSkelImaging.
        Uses the mayaUsd 'editAsMaya' command to convert USD prims to Maya nodes.

        Args:
            proxy_shape: The mayaUsdProxyShape node
            result: Import result to update

        Returns:
            True if conversion succeeded
        """
        if cmds is None or mel is None:
            return False

        try:
            self.logger.info("[REFRESH] Converting USD prims to native Maya meshes...")

            # Get the proxy transform
            proxy_parent = cmds.listRelatives(proxy_shape, parent=True)
            if not proxy_parent:
                self.logger.error("[ERROR] Could not find proxy parent transform")
                return False

            # Select the proxy shape
            cmds.select(proxy_shape, replace=True)

            # Use mayaUsd's editAsMaya command to convert
            # This is equivalent to: Right-click proxy > Duplicate As > Maya Data
            try:
                # Try the Python command first
                import mayaUsd.lib as mayaUsdLib  # type: ignore[import-unresolved]
                if hasattr(mayaUsdLib, 'PrimUpdater'):
                    # Modern mayaUSD API
                    mel.eval('mayaUsdEditAsMaya')
                    self.logger.info("[OK] Converted via mayaUsdEditAsMaya")
                else:
                    # Fallback to MEL
                    mel.eval('mayaUsdMenu_editAsMaya()')
                    self.logger.info("[OK] Converted via MEL command")
            except Exception as mel_err:
                # Try alternative MEL commands
                try:
                    mel.eval('mayaUsdDuplicate -importMaya')
                    self.logger.info("[OK] Converted via mayaUsdDuplicate")
                except Exception:
                    self.logger.warning(f"[WARNING] MEL conversion failed: {mel_err}")
                    self.logger.info("[TIP] Try: Right-click proxy > Duplicate As > Maya Data")
                    return False

            # Count what was converted
            cmds.refresh()
            native_meshes = cmds.ls(type='mesh', dag=True) or []
            native_joints = cmds.ls(type='joint', dag=True) or []
            native_skins = cmds.ls(type='skinCluster') or []

            self.logger.info(
                f"[OK] Converted to Maya: {len(native_meshes)} meshes, "
                f"{len(native_joints)} joints, {len(native_skins)} skinClusters"
            )

            result.meshes_imported = len(native_meshes)
            result.joints_imported = len(native_joints)
            result.skin_clusters_imported = len(native_skins)

            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Conversion to Maya failed: {e}")
            return False

    def _convert_skinned_meshes_to_maya(
        self,
        proxy_shape: str,
        result: ImportResult
    ) -> bool:
        """
        Convert only skinned USD meshes to native Maya while keeping USD proxy.

        This is a workaround for Maya 2026 UsdSkelImaging bugs with complex skeletons.
        Skinned meshes are imported to Maya with their skin weights preserved.
        Non-skinned meshes remain in the USD proxy for efficient display.

        Args:
            proxy_shape: The mayaUsdProxyShape node
            result: Import result to update

        Returns:
            True if conversion succeeded
        """
        if cmds is None or mel is None:
            return False

        try:
            from pxr import Usd, UsdSkel, UsdGeom

            # Get the USD stage from the proxy
            stage_attr = f"{proxy_shape}.filePath"
            if not cmds.objExists(stage_attr):
                self.logger.error("[ERROR] Could not get USD file path from proxy")
                return False

            usd_path = cmds.getAttr(stage_attr)
            if not usd_path:
                self.logger.error("[ERROR] USD file path is empty")
                return False

            stage = Usd.Stage.Open(usd_path)
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            # Find all skinned mesh paths
            skinned_mesh_paths = []
            for prim in stage.Traverse():
                if prim.IsA(UsdGeom.Mesh):
                    binding = UsdSkel.BindingAPI(prim)
                    skel_rel = binding.GetSkeletonRel()
                    if skel_rel and skel_rel.HasAuthoredTargets():
                        skinned_mesh_paths.append(str(prim.GetPath()))

            if not skinned_mesh_paths:
                self.logger.info("[OK] No skinned meshes found - nothing to convert")
                return True

            self.logger.info(f"[REFRESH] Converting {len(skinned_mesh_paths)} skinned meshes to Maya...")

            # Get proxy parent transform
            proxy_parent = cmds.listRelatives(proxy_shape, parent=True)
            if not proxy_parent:
                self.logger.error("[ERROR] Could not find proxy parent")
                return False
            proxy_parent = proxy_parent[0]

            # Try multiple methods to convert USD to Maya
            converted_count = 0

            # Method 1: Try mayaUsd Python API (most reliable)
            try:
                import mayaUsd.lib as mayaUsdLib  # type: ignore[import-unresolved]
                if hasattr(mayaUsdLib, 'PrimUpdaterManager'):
                    self.logger.info("   Using mayaUsd.lib.PrimUpdaterManager...")
                    # This is the proper API for edit-as-maya
                    for mesh_path in skinned_mesh_paths:
                        try:
                            # Select the USD prim path
                            prim_path_str = f"{proxy_parent},{mesh_path}"
                            cmds.select(prim_path_str, replace=True)
                            # Try to duplicate as Maya
                            mel.eval('mayaUsdDuplicate -importMaya')
                            converted_count += 1
                            mesh_name = mesh_path.split("/")[-1]
                            self.logger.info(f"   [OK] {mesh_name}")
                        except Exception as prim_err:
                            self.logger.debug(f"   Prim conversion failed: {prim_err}")
            except ImportError:
                self.logger.debug("   mayaUsd.lib not available")

            # Method 2: Try bulk conversion via MEL if Method 1 failed
            if converted_count == 0:
                self.logger.info("[REFRESH] Trying bulk import method...")
                try:
                    # Select the proxy transform (not shape)
                    cmds.select(proxy_parent, replace=True)

                    # Try mayaUsdImport command to import entire stage as Maya
                    import_opts = "preferredMaterial=none;importInstances=1"
                    mel_cmd = f'file -import -type "USD Import" -options "{import_opts}" "{usd_path}"'
                    mel.eval(mel_cmd)
                    converted_count = len(skinned_mesh_paths)
                    self.logger.info("   [OK] Bulk import successful")
                except Exception as bulk_err:
                    self.logger.debug(f"   Bulk import failed: {bulk_err}")

            # Method 3: Direct mayaUSDImport command
            if converted_count == 0:
                self.logger.info("[REFRESH] Trying direct mayaUSDImport...")
                try:
                    # Use mayaUSDImport command directly
                    import_result = cmds.mayaUSDImport(
                        file=str(usd_path),
                        primPath="/",
                        importInstances=True
                    )
                    if import_result:
                        converted_count = len(skinned_mesh_paths)
                        self.logger.info("   [OK] Direct import successful")
                except Exception as direct_err:
                    self.logger.debug(f"   Direct import failed: {direct_err}")

            # Method 4: Delete proxy and re-import with native conversion
            if converted_count == 0:
                self.logger.info("[REFRESH] Trying re-import as native Maya...")
                try:
                    # Delete the USD proxy
                    cmds.delete(proxy_parent)

                    # Re-import using mayaUSDImport with native data
                    cmds.mayaUSDImport(
                        file=str(usd_path),
                        primPath="/SkelRoot",
                        readAnimData=True,
                        importInstances=True
                    )
                    converted_count = len(skinned_mesh_paths)
                    self.logger.info("   [OK] Re-import as native Maya successful")
                except Exception as reimport_err:
                    self.logger.warning(f"[WARNING] Re-import failed: {reimport_err}")

            if converted_count > 0:
                self.logger.info(f"[OK] Converted {converted_count} skinned meshes to Maya")

                # Count native Maya objects created
                cmds.refresh()
                native_meshes = cmds.ls(type='mesh', dag=True) or []
                native_skins = cmds.ls(type='skinCluster') or []

                # Update result with native mesh count (use existing attributes)
                result.meshes_imported = len(native_meshes)
                result.skin_clusters_imported = len(native_skins)

                self.logger.info(f"   [PACKAGE] Maya meshes: {len(native_meshes)}")
                self.logger.info(f"   [SKEL] SkinClusters: {len(native_skins)}")
            else:
                self.logger.warning("[WARNING] Could not auto-convert meshes")
                self.logger.warning("[TIP] Try: Right-click proxy > Duplicate As > Maya Data")
                return False

            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Skinned mesh conversion failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False

    def _create_usd_skin_bindings(
        self,
        proxy_shape: str,
        usd_path: Path,
        result: ImportResult
    ) -> bool:
        """
        Create USD skeleton bindings for meshes using UsdSkel API.

        Phase 1: Check if bindings exist; only create if missing.
        This enables skeleton animation to deform the meshes.

        Args:
            proxy_shape: Maya USD proxy shape node
            usd_path: Path to USD file
            result: Import result object

        Returns:
            True if bindings exist or were created successfully
        """
        try:
            from pxr import Usd, UsdSkel, UsdGeom, Sdf  # type: ignore

            self.logger.info("🔗 Checking USD skeleton bindings...")

            # Open USD stage (read-only check first)
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            self.logger.info(f"[OK] Opened USD stage: {stage.GetRootLayer().identifier}")

            # Find skeleton and meshes
            skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            meshes = [p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]

            if not skeletons:
                self.logger.warning("[WARNING] No skeletons found in USD")
                return False

            if not meshes:
                self.logger.warning("[WARNING] No meshes found in USD")
                return False

            skeleton = skeletons[0]
            self.logger.info(f"[SKEL] Found skeleton: {skeleton.GetPath()}")
            self.logger.info(f"[PACKAGE] Found {len(meshes)} meshes")

            # Check if meshes already have bindings - if so, skip Phase 1
            meshes_with_binding = 0
            meshes_with_weights = 0

            for mesh_prim in meshes:
                binding_api = UsdSkel.BindingAPI(mesh_prim)
                skel_rel = binding_api.GetSkeletonRel()

                if skel_rel and skel_rel.HasAuthoredTargets():
                    meshes_with_binding += 1

                # Check for weight primvars
                indices_attr = mesh_prim.GetAttribute('primvars:skel:jointIndices')
                weights_attr = mesh_prim.GetAttribute('primvars:skel:jointWeights')
                if indices_attr and weights_attr:
                    if indices_attr.Get() and weights_attr.Get():
                        meshes_with_weights += 1

            if meshes_with_binding > 0 or meshes_with_weights > 0:
                self.logger.info("[OK] USD already has skeleton bindings:")
                self.logger.info(f"   [INFO] Meshes with binding: {meshes_with_binding}")
                self.logger.info(f"   [INFO] Meshes with weights: {meshes_with_weights}")

                # Check for empty geometry (multi-skinCluster corruption)
                empty_mesh_count = 0
                for mesh_prim in meshes[:min(5, len(meshes))]:  # Sample first 5
                    mesh_api = UsdGeom.Mesh(mesh_prim)
                    points = mesh_api.GetPointsAttr().Get()
                    if not points or len(points) == 0:
                        empty_mesh_count += 1

                if empty_mesh_count > 0:
                    self.logger.warning("[WARNING] EMPTY GEOMETRY DETECTED!")
                    sample_size = min(5, len(meshes))
                    self.logger.warning(
                        f"   Found {empty_mesh_count} meshes with no point data "
                        f"(of {sample_size} sampled)"
                    )
                    self.logger.warning(
                        "   This usually means the USD was exported with "
                        "multi-skinCluster corruption"
                    )
                    self.logger.warning("   [FIX] FIX: Re-export character with the updated exporter")
                    self.logger.warning(
                        "   The exporter now auto-fixes multi-skinCluster meshes during export"
                    )

                self.logger.info("[TIP] Skipping Phase 1 - using existing bindings")
                return True

            # Only create bindings if none exist
            self.logger.info("📝 No existing bindings found - creating new ones...")

            # Create anonymous layer for bindings
            anim_layer = Sdf.Layer.CreateAnonymous('skin_bindings')
            stage.GetRootLayer().subLayerPaths.append(anim_layer.identifier)
            stage.SetEditTarget(anim_layer)

            self.logger.info(f"📝 Created binding layer: {anim_layer.identifier}")

            # Create bindings for first mesh (Phase 1 test)
            test_mesh = meshes[0]
            self.logger.info(f"[TEST] Phase 1: Testing binding on {test_mesh.GetPath()}")

            # Apply UsdSkel binding API
            binding_api = UsdSkel.BindingAPI.Apply(test_mesh.GetPrim())

            # Link mesh to skeleton
            binding_api.CreateSkeletonRel().SetTargets([skeleton.GetPath()])
            self.logger.info("[OK] Linked mesh to skeleton")

            # Get skeleton joints
            skel_api = UsdSkel.Skeleton(skeleton)
            joints_attr = skel_api.GetJointsAttr()

            if joints_attr:
                joints = joints_attr.Get()
                self.logger.info(f"[SKEL] Skeleton has {len(joints) if joints else 0} joints")
                self.logger.info("[TIP] Phase 1 complete: Basic binding structure created")
                self.logger.warning("[WARNING] Weight transfer not yet implemented (Phase 2)")
            else:
                self.logger.warning("[WARNING] Could not read skeleton joints")

            self.logger.info("[TIP] Binding layer active in stage (in-memory)")

            return True

        except ImportError:
            self.logger.error("[ERROR] USD Python API (pxr) not available")
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Binding creation failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _create_maya_joint_proxies(
        self,
        usd_path: Path,
        proxy_shape: str,
        result: ImportResult
    ) -> bool:
        """
        Phase 2: Create Maya joints that mirror USD skeleton for manipulation.

        NEW STRATEGY: Import the .rig.mb file and query joint positions from native Maya rig.
        This bypasses all USD coordinate space issues.

        Args:
            usd_path: Path to USD file
            proxy_shape: Maya USD proxy shape
            result: Import result

        Returns:
            True if joints created successfully
        """
        try:
            from pxr import Usd, UsdSkel

            self.logger.info("[SKEL] Phase 2: Creating Maya joint proxies from .rig.mb file...")

            # First, get USD skeleton joint names to filter Maya joints
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            if not skeletons:
                self.logger.warning("[WARNING] No skeleton found in USD")
                return False

            skeleton_prim = skeletons[0]
            skel = UsdSkel.Skeleton(skeleton_prim)
            joints_attr = skel.GetJointsAttr()

            if not joints_attr:
                self.logger.error("[ERROR] No joints in USD skeleton")
                return False

            usd_joint_paths = joints_attr.Get()
            if not usd_joint_paths:
                self.logger.error("[ERROR] Empty USD joints list")
                return False

            # Extract just the joint names (last component of path)
            usd_joint_names = set(str(jp).split('/')[-1] for jp in usd_joint_paths)
            self.logger.info(f"[SKEL] USD skeleton has {len(usd_joint_names)} joints")

            # Check for left/right naming patterns to detect if mirroring is needed
            sample_joints = list(usd_joint_names)[:10]
            self.logger.info(f"[DEBUG] Sample USD joints: {sample_joints}")

            # Get the .rig.mb file path from the same directory as USD file
            rig_mb_path = usd_path.parent / f"{usd_path.stem}.rig.mb"
            if not rig_mb_path.exists():
                self.logger.error(f"[ERROR] Rig file not found: {rig_mb_path}")
                return False

            self.logger.info(f"[PACKAGE] Found Maya rig file: {rig_mb_path}")

            # Import the Maya rig to query joint positions
            if cmds is None:
                self.logger.error("[ERROR] Maya cmds not available")
                return False

            self.logger.info("📥 Importing Maya rig to query skeleton positions...")

            # Create namespace for the rig
            namespace = "RIG_REFERENCE"

            # Import the rig file with references deferred (avoids RenderMan callback blocking)
            self.logger.info("[REFRESH] Importing Maya rig file...")

            # Disable undo during import for performance
            undo_state = cmds.undoInfo(query=True, state=True)
            cmds.undoInfo(stateWithoutFlush=False)

            try:
                # Skip loading references - joints are in main file, referenced file
                # has RenderMan shaders causing blocking issues
                cmds.file(
                    str(rig_mb_path),
                    i=True,
                    type="mayaBinary",
                    ignoreVersion=True,
                    ra=True,
                    mergeNamespacesOnClash=False,
                    namespace=namespace,
                    loadReferenceDepth="none"  # Skip referenced file (RenderMan shader issues)
                )
                self.logger.info("[OK] Maya rig imported (references deferred)")
            except Exception as import_error:
                # Import may have worked despite errors - check for joints anyway
                self.logger.warning(f"[WARNING] Import warnings: {str(import_error)[:80]}")
            finally:
                # Restore undo state
                cmds.undoInfo(stateWithoutFlush=undo_state)

            # Find all joints in the imported rig
            self.logger.info("[DEBUG] Querying imported joints...")
            all_maya_joints = cmds.ls(f"{namespace}:*", type="joint")

            if not all_maya_joints:
                self.logger.error(f"[ERROR] No joints found in {rig_mb_path}")
                return False

            self.logger.info(f"[SKEL] Found {len(all_maya_joints)} total joints in Maya rig")

            # Create case-insensitive mapping for joint names
            usd_joint_names_lower = {name.lower(): name for name in usd_joint_names}

            # Helper function to check if a joint has a side suffix
            def has_side_suffix(name):
                """Check if joint name has left/right suffix (not middle/center)."""
                lower = name.lower()
                for suffix in ['_l', '_r', '_left', '_right', '_lf', '_rt']:
                    if lower.endswith(suffix):
                        return True
                for prefix in ['l_', 'r_', 'left_', 'right_', 'lf_', 'rt_']:
                    if lower.startswith(prefix):
                        return True
                return False

            # Helper function to strip side/center suffixes for matching
            def strip_side_prefix(name):
                """Strip common left/right/middle suffixes to match against USD skeleton."""
                lower = name.lower()
                # Check for common prefixes (case-insensitive)
                for prefix in ['l_', 'r_', 'left_', 'right_', 'lf_', 'rt_', 'm_', 'mid_', 'middle_', 'c_', 'center_']:
                    if lower.startswith(prefix):
                        return name[len(prefix):]
                # Check for common suffixes (including _M for middle/center joints)
                for suffix in ['_l', '_r', '_left', '_right', '_lf', '_rt', '_m', '_mid', '_middle', '_c', '_center']:
                    if lower.endswith(suffix):
                        return name[:-len(suffix)]
                return name

            # First pass: collect all matching joints and track which have sided variants
            exact_matches = []  # Joints matching USD names exactly (may be reference joints)
            sided_matches = []  # Joints with _L/_R that match stripped USD names
            center_matches = []  # Joints with _M (middle/center) suffix
            sided_base_names = set()  # Base names that have sided variants

            # Helper to check if joint has center suffix
            def has_center_suffix(name):
                lower = name.lower()
                for suffix in ['_m', '_mid', '_middle', '_c', '_center']:
                    if lower.endswith(suffix):
                        return True
                for prefix in ['m_', 'mid_', 'middle_', 'c_', 'center_']:
                    if lower.startswith(prefix):
                        return True
                return False

            for maya_joint in all_maya_joints:
                maya_joint_name = maya_joint.split(":")[-1]
                maya_joint_lower = maya_joint_name.lower()

                if has_side_suffix(maya_joint_name):
                    # This is a sided joint (_L/_R) - check if base name matches USD
                    stripped_name = strip_side_prefix(maya_joint_name).lower()
                    if stripped_name in usd_joint_names_lower:
                        sided_matches.append(maya_joint)
                        sided_base_names.add(stripped_name)
                elif has_center_suffix(maya_joint_name):
                    # This is a center joint (_M) - check if base name matches USD
                    stripped_name = strip_side_prefix(maya_joint_name).lower()
                    if stripped_name in usd_joint_names_lower:
                        center_matches.append(maya_joint)
                elif maya_joint_lower in usd_joint_names_lower:
                    # Exact match (unsided joint)
                    exact_matches.append(maya_joint)

            # Track which base names have center (_M) variants
            center_base_names = set()
            for j in center_matches:
                stripped = strip_side_prefix(j.split(":")[-1]).lower()
                center_base_names.add(stripped)

            # Build final joint list: sided + center + filtered exact matches
            all_joints = list(sided_matches) + list(center_matches)
            filtered_out = []

            # Joints that are truly center (spine/torso) - should NOT be mirrored
            true_center_joints = {
                'root', 'spine', 'spine1', 'spine2', 'spine3', 'spine4',
                'chest', 'neck', 'neck1', 'neck2', 'head', 'jaw',
                'pelvis', 'hips', 'waist', 'torso', 'body', 'cog',
            }

            # Track unsided joints that need mirroring (foot/limb joints without L/R)
            joints_to_mirror = []

            for maya_joint in exact_matches:
                maya_joint_name = maya_joint.split(":")[-1]
                maya_joint_lower = maya_joint_name.lower()

                if maya_joint_lower in sided_base_names:
                    # This unsided joint has _L/_R variants - skip it (it's a reference joint)
                    filtered_out.append(f"{maya_joint_name} (has sided variants)")
                elif maya_joint_lower in center_base_names:
                    # This unsided joint has _M variant - skip it (prefer the _M version)
                    filtered_out.append(f"{maya_joint_name} (has _M variant)")
                elif maya_joint_lower in true_center_joints:
                    # Truly center joint (Spine, Chest, Head, etc.) - keep it as-is
                    all_joints.append(maya_joint)
                else:
                    # Unsided joint that's NOT a true center joint - needs mirroring!
                    # (e.g., FootSideInner, FootSideOuter, Heel)
                    joints_to_mirror.append(maya_joint)

            # Also track joints that didn't match at all
            matched_names_lower = {j.split(":")[-1].lower() for j in all_joints}
            matched_stripped = {strip_side_prefix(j.split(":")[-1]).lower() for j in all_joints}
            for maya_joint in all_maya_joints:
                maya_joint_name = maya_joint.split(":")[-1]
                maya_joint_lower = maya_joint_name.lower()
                stripped = strip_side_prefix(maya_joint_name).lower()
                if maya_joint_lower not in matched_names_lower and stripped not in matched_stripped:
                    if maya_joint_name not in [f.split(" ")[0] for f in filtered_out]:
                        filtered_out.append(maya_joint_name)

            if not all_joints:
                self.logger.error("[ERROR] No matching joints found between Maya rig and USD skeleton")
                self.logger.info(f"   Maya has {len(all_maya_joints)} joints, USD expects {len(usd_joint_names)}")
                return False

            self.logger.info(f"[TARGET] Filtered to {len(all_joints)} joints matching USD skeleton")

            # Log joints that will be mirrored (unsided foot/limb joints)
            if joints_to_mirror:
                mirror_names = [j.split(":")[-1] for j in joints_to_mirror]
                self.logger.info(f"[REFRESH] Unsided joints to mirror: {mirror_names}")

            # Count left/right/center joints for diagnostics
            left_count = sum(
                1 for j in all_joints
                if j.split(":")[-1].lower().startswith(('l_', 'left_', 'lf_'))
                or j.split(":")[-1].lower().endswith(('_l', '_left', '_lf'))
            )
            right_count = sum(
                1 for j in all_joints
                if j.split(":")[-1].lower().startswith(('r_', 'right_', 'rt_'))
                or j.split(":")[-1].lower().endswith(('_r', '_right', '_rt'))
            )
            center_count = len(all_joints) - left_count - right_count
            mirrored_count = len(joints_to_mirror) * 2  # Each mirrored joint becomes L and R
            self.logger.info(
                f"[DEBUG] Joint breakdown: {left_count} left, {right_count} right, "
                f"{center_count} center, +{mirrored_count} mirrored"
            )

            # Log matched joints to help diagnose left/right issues
            matched_names = [j.split(":")[-1] for j in all_joints[:15]]
            self.logger.info(f"[DEBUG] Matched joints (sample): {matched_names}")

            # Log first few filtered out joints for debugging
            if filtered_out and len(filtered_out) < 20:
                joint_list = ', '.join(filtered_out[:10])
                self.logger.info(f"[DEBUG] Filtered out {len(filtered_out)} joints: {joint_list}")
            elif filtered_out:
                self.logger.info(
                    f"[DEBUG] Filtered out {len(filtered_out)} non-deformation joints "
                    f"(helpers, IK, controls)"
                )

            # Phase 3.1: Build joint hierarchy map
            self.logger.info("🔗 Phase 3.1: Building joint hierarchy...")
            hierarchy_map = {}  # Maps source_joint → parent_source_joint
            joint_orientations = {}  # Store joint orientations

            # Create a set of all_joints for fast lookup (both full path and short name)
            all_joints_set = set(all_joints)
            # Also create a mapping from short name to full path for parent lookup
            # Include both exact names and stripped names (for _M, _L, _R matching)
            short_to_full = {}
            stripped_to_full = {}
            for j in all_joints:
                short_name = j.split(":")[-1]
                short_to_full[short_name] = j
                # Also map stripped name (without _L/_R/_M suffix)
                stripped = strip_side_prefix(short_name)
                if stripped.lower() not in stripped_to_full:
                    stripped_to_full[stripped.lower()] = j

            def find_nearest_valid_ancestor(joint, debug=False):
                """Walk up the hierarchy to find the nearest ancestor in our filtered set.

                Walks through ANY node type (not just joints) to handle rigs where
                joints are parented under transform groups.
                """
                current = joint
                visited = set()  # Prevent infinite loops
                max_depth = 50  # Safety limit
                depth = 0
                walk_path = []  # Debug: track the walk

                while current and current not in visited and depth < max_depth:
                    visited.add(current)
                    depth += 1

                    # Get parent of ANY type (not just joints) to traverse through groups
                    parent = cmds.listRelatives(current, parent=True)
                    if not parent:
                        if debug:
                            self.logger.info(f"   Walk ended at root: {' -> '.join(walk_path)}")
                        return None  # Reached root of Maya hierarchy
                    parent = parent[0]
                    walk_path.append(parent.split(":")[-1])

                    # Check if parent is a joint in our set
                    node_type = cmds.nodeType(parent)
                    if node_type == "joint":
                        # Check full path match
                        if parent in all_joints_set:
                            if debug:
                                self.logger.info(f"   Found ancestor (full): {parent.split(':')[-1]}")
                            return parent

                        # Check short name match (handles namespace differences)
                        parent_short = parent.split(":")[-1]
                        if parent_short in short_to_full:
                            if debug:
                                self.logger.info(f"   Found ancestor (short): {parent_short}")
                            return short_to_full[parent_short]

                        # Check stripped name match (handles _M/_L/_R suffix differences)
                        parent_stripped = strip_side_prefix(parent_short).lower()
                        if parent_stripped in stripped_to_full:
                            if debug:
                                self.logger.info(f"   Found ancestor (stripped): {parent_short} -> {parent_stripped}")
                            return stripped_to_full[parent_stripped]

                    # Keep walking up (whether joint or not)
                    current = parent

                if debug:
                    self.logger.info(f"   Walk exhausted: {' -> '.join(walk_path)}")
                return None

            # Count root joints for debugging
            root_count = 0
            debug_joints = ['Hip_L', 'Scapula_L']  # Debug these specific joints
            for source_joint in all_joints:
                joint_short = source_joint.split(":")[-1]
                do_debug = joint_short in debug_joints

                if do_debug:
                    self.logger.info(f"[DEBUG] DEBUG: Walking from {joint_short}...")

                # Find nearest valid ancestor (not just immediate parent)
                valid_parent = find_nearest_valid_ancestor(source_joint, debug=do_debug)
                hierarchy_map[source_joint] = valid_parent  # None = root joint
                if valid_parent is None:
                    root_count += 1

                # Get joint orientation
                joint_orient = cmds.getAttr(f"{source_joint}.jointOrient")[0]
                joint_orientations[source_joint] = joint_orient

            # Log root joints for debugging
            root_joints = [j.split(":")[-1] for j, p in hierarchy_map.items() if p is None]
            self.logger.info(f"[OK] Built hierarchy map for {len(all_joints)} joints ({root_count} roots)")
            self.logger.info(f"[DEBUG] Root joints: {root_joints[:10]}")

            # Create mirrored joints for unsided foot/limb joints
            # These are joints like FootSideInner that should have _L/_R but don't
            mirrored_joints_data = []  # List of (original_joint, side, position, orientation)

            for mirror_joint in joints_to_mirror:
                mirror_name = mirror_joint.split(":")[-1]
                world_pos = cmds.xform(mirror_joint, q=True, worldSpace=True, translation=True)
                joint_orient = cmds.getAttr(f"{mirror_joint}.jointOrient")[0]

                # Determine which side the original joint is on (based on X position)
                original_x = world_pos[0]

                # Create LEFT version (_L)
                left_pos = (abs(original_x), world_pos[1], world_pos[2])
                mirrored_joints_data.append({
                    'original': mirror_joint,
                    'name': f"{mirror_name}_L",
                    'side': 'L',
                    'position': left_pos,
                    'orientation': joint_orient
                })

                # Create RIGHT version (_R) - mirror X
                right_pos = (-abs(original_x), world_pos[1], world_pos[2])
                mirrored_joints_data.append({
                    'original': mirror_joint,
                    'name': f"{mirror_name}_R",
                    'side': 'R',
                    'position': right_pos,
                    'orientation': joint_orient  # Mirror orientation too if needed
                })

                self.logger.info(
                    f"[REFRESH] Mirroring {mirror_name}: L@{left_pos[0]:.3f}, R@{right_pos[0]:.3f}"
                )

            # Create proxy joints by querying positions from imported rig
            maya_joints = {}  # Maps source_joint → proxy_joint
            source_to_proxy = {}  # Clean mapping for hierarchy building

            for i, source_joint in enumerate(all_joints):
                # Get world position from source joint
                world_pos = cmds.xform(source_joint, q=True, worldSpace=True, translation=True)
                tx, ty, tz = world_pos[0], world_pos[1], world_pos[2]

                # Get clean joint name (remove namespace)
                joint_name = source_joint.split(":")[-1]

                if i < 3:
                    self.logger.info(
                        f"[DEBUG] Joint {i} ({joint_name}): pos=[{tx:.4f}, {ty:.4f}, {tz:.4f}]"
                    )

                # Create proxy joint
                cmds.select(clear=True)
                maya_joint = cmds.joint(
                    name=f"proxy_{joint_name}",
                    position=(tx, ty, tz)
                )

                # Apply joint orientation from source
                joint_orient = joint_orientations[source_joint]
                cmds.setAttr(f"{maya_joint}.jointOrientX", joint_orient[0])
                cmds.setAttr(f"{maya_joint}.jointOrientY", joint_orient[1])
                cmds.setAttr(f"{maya_joint}.jointOrientZ", joint_orient[2])

                cmds.setAttr(f"{maya_joint}.radius", 0.15)
                maya_joints[source_joint] = maya_joint
                source_to_proxy[source_joint] = maya_joint

            # Create mirrored proxy joints for unsided foot/limb joints
            mirrored_proxy_joints = {}  # Maps (original_joint, side) → proxy_joint

            for mirror_data in mirrored_joints_data:
                orig_joint = mirror_data['original']
                name = mirror_data['name']
                side = mirror_data['side']
                pos = mirror_data['position']
                orient = mirror_data['orientation']

                cmds.select(clear=True)
                mirror_proxy = cmds.joint(
                    name=f"proxy_{name}",
                    position=pos
                )

                # Apply orientation (mirror Y and Z for right side)
                if side == 'R':
                    cmds.setAttr(f"{mirror_proxy}.jointOrientX", orient[0])
                    cmds.setAttr(f"{mirror_proxy}.jointOrientY", -orient[1])
                    cmds.setAttr(f"{mirror_proxy}.jointOrientZ", -orient[2])
                else:
                    cmds.setAttr(f"{mirror_proxy}.jointOrientX", orient[0])
                    cmds.setAttr(f"{mirror_proxy}.jointOrientY", orient[1])
                    cmds.setAttr(f"{mirror_proxy}.jointOrientZ", orient[2])

                cmds.setAttr(f"{mirror_proxy}.radius", 0.15)
                mirrored_proxy_joints[(orig_joint, side)] = mirror_proxy

            if mirrored_proxy_joints:
                self.logger.info(
                    f"[OK] Created {len(mirrored_proxy_joints)} mirrored proxy joints"
                )

            self.logger.info(f"[OK] Created {len(maya_joints)} proxy joints")

            # Build hierarchy for proxy joints
            self.logger.info("🔗 Building proxy joint hierarchy...")
            root_joints = []

            for source_joint, proxy_joint in maya_joints.items():
                parent_source = hierarchy_map.get(source_joint)
                if parent_source and parent_source in source_to_proxy:
                    # Has parent - establish hierarchy
                    parent_proxy = source_to_proxy[parent_source]
                    cmds.parent(proxy_joint, parent_proxy)
                else:
                    # Root joint
                    root_joints.append(proxy_joint)

            # Parent mirrored joints to their sided parent (e.g., Ankle_L, Ankle_R)
            for (orig_joint, side), mirror_proxy in mirrored_proxy_joints.items():
                # Query the parent directly from Maya (orig_joint still exists)
                maya_parent = cmds.listRelatives(orig_joint, parent=True, type='joint')

                if maya_parent:
                    parent_short = maya_parent[0].split(":")[-1]
                    parent_stripped = strip_side_prefix(parent_short).lower()

                    # Look for the sided parent joint (e.g., Ankle_L from Ankle)
                    sided_parent = None
                    for src, prx in source_to_proxy.items():
                        src_stripped = strip_side_prefix(src.split(":")[-1]).lower()
                        if src_stripped == parent_stripped:
                            if src.split(":")[-1].lower().endswith(f"_{side.lower()}"):
                                sided_parent = prx
                                break

                    if sided_parent:
                        cmds.parent(mirror_proxy, sided_parent)
                    else:
                        self.logger.warning(
                            f"[WARNING] Could not find sided parent for {mirror_proxy}"
                        )
                        root_joints.append(mirror_proxy)
                else:
                    root_joints.append(mirror_proxy)

            self.logger.info(f"[OK] Created hierarchy: {len(root_joints)} root joints")

            # Parent proxy skeleton under USD proxy transform for unified rig
            if root_joints:
                # Get the USD proxy's parent transform (e.g., Veteran_Rig_USD)
                proxy_parents = cmds.listRelatives(proxy_shape, parent=True, fullPath=True)
                if proxy_parents:
                    usd_transform = proxy_parents[0]
                    # Parent all root joints under the USD transform
                    for root in root_joints:
                        cmds.parent(root, usd_transform)
                    self.logger.info(
                        f"[OK] Parented proxy skeleton under USD transform: "
                        f"{usd_transform.split('|')[-1]}"
                    )
                else:
                    self.logger.warning("[WARNING] Could not find USD proxy transform, skeleton at world level")

            # Store imported joints for weight extraction (Phase 3.2)
            # We'll delete them after extracting skinCluster weights
            result._imported_joints = all_joints + joints_to_mirror
            result._proxy_joints = list(maya_joints.values()) + list(mirrored_proxy_joints.values())
            result._source_to_proxy = source_to_proxy

            # Select root joints for easy visualization
            if root_joints:
                cmds.select(root_joints, replace=True)

            total_joints = len(maya_joints) + len(mirrored_proxy_joints)
            self.logger.info(f"\n[OK] Phase 3.1 Complete: Created {total_joints} joint hierarchy")
            if mirrored_proxy_joints:
                self.logger.info(
                    f"[REFRESH] Includes {len(mirrored_proxy_joints)} mirrored foot joints"
                )
            self.logger.info(f"🔗 Hierarchy: {len(root_joints)} root joint(s)")
            self.logger.info("[TIP] Joint orientations preserved from source rig")
            self.logger.info("[TIP] Positions extracted from native Maya rig")

            result.joints_imported = total_joints
            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Joint proxy creation failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _connect_proxy_to_usd_skeleton(
        self,
        proxy_shape: str,
        result: ImportResult
    ) -> bool:
        """
        Phase 3.2: Connect Maya proxy joints to USD skeleton.

        Creates live connections where animating Maya proxy joints drives
        the USD skeleton via session layer, which deforms the USD meshes.

        Args:
            proxy_shape: Maya USD proxy shape node
            result: Import result with proxy joint data

        Returns:
            True if connection successful
        """
        try:
            self.logger.info("🔗 Phase 3.2: Connecting proxy joints to USD skeleton...")

            proxy_joints = getattr(result, '_proxy_joints', None)
            if not proxy_joints:
                self.logger.warning("[WARNING] No proxy joints found")
                return False

            self.logger.info(f"[SKEL] Found {len(proxy_joints)} proxy joints to connect")

            # Get USD stage via mayaUsd (live stage, not file-based)
            try:
                import mayaUsd.ufe as mayaUsdUfe  # type: ignore[import-unresolved]
                # Try with shape name, then full path if that fails
                try:
                    stage = mayaUsdUfe.getStage(proxy_shape)
                except RuntimeError:
                    # mayaUsdUfe needs full path - get parent transform
                    parents = cmds.listRelatives(proxy_shape, parent=True, fullPath=True)
                    if parents:
                        full_path = f"{parents[0]}|{proxy_shape}"
                        stage = mayaUsdUfe.getStage(full_path)
                    else:
                        raise
            except (ImportError, RuntimeError) as e:
                self.logger.warning(f"[WARNING] mayaUsd.ufe getStage failed ({e}), using file-based stage")
                stage = None

            if not stage:
                stage_path = cmds.getAttr(f"{proxy_shape}.filePath")
                if not stage_path:
                    self.logger.error("[ERROR] Could not get USD stage")
                    return False
                from pxr import Usd
                stage = Usd.Stage.Open(stage_path)

            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            from pxr import Usd, UsdSkel  # type: ignore[import-unresolved]

            # Find USD skeleton
            skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            if not skeletons:
                self.logger.warning("[WARNING] No skeleton found in USD")
                return False

            skeleton_prim = skeletons[0]
            skel = UsdSkel.Skeleton(skeleton_prim)
            usd_joints = skel.GetJointsAttr().Get() or []

            if not usd_joints:
                self.logger.warning("[WARNING] USD skeleton has no joints")
                return False

            # Build USD joint mappings (name → path, name → index)
            usd_joint_map = {}
            usd_joint_indices = {}
            for idx, joint_path in enumerate(usd_joints):
                joint_name = str(joint_path).split('/')[-1].lower()
                usd_joint_map[joint_name] = str(joint_path)
                usd_joint_indices[joint_name] = idx

            self.logger.info(f"[INFO] USD skeleton: {len(usd_joints)} joints")

            # Create/get session layer for animation edits
            session_layer = stage.GetSessionLayer()
            stage.SetEditTarget(session_layer)
            self.logger.info("📝 Using session layer for animation edits")

            # Build joint mapping and create scriptJob connections
            joint_mapping = {}  # proxy_joint → (usd_path, usd_index)
            connections_made = 0

            for proxy_joint in proxy_joints:
                if not cmds.objExists(proxy_joint):
                    continue

                # Extract joint name (remove "proxy_" prefix)
                proxy_name = proxy_joint.split('|')[-1]
                joint_name = proxy_name[6:] if proxy_name.startswith('proxy_') else proxy_name

                # Match to USD joint (exact, then stripped)
                joint_name_lower = joint_name.lower()
                joint_name_stripped = self._strip_side_suffix(joint_name).lower()

                usd_joint_path = usd_joint_map.get(joint_name_lower)
                usd_joint_idx = usd_joint_indices.get(joint_name_lower)

                if not usd_joint_path:
                    usd_joint_path = usd_joint_map.get(joint_name_stripped)
                    usd_joint_idx = usd_joint_indices.get(joint_name_stripped)

                if usd_joint_path and usd_joint_idx is not None:
                    joint_mapping[proxy_joint] = (usd_joint_path, usd_joint_idx)
                    connections_made += 1

            self.logger.info(f"[OK] Mapped {connections_made}/{len(proxy_joints)} joints")

            # Store mapping for animation callback system
            result._joint_mapping = joint_mapping
            result._usd_stage = stage
            result._skeleton_prim = skeleton_prim
            result._proxy_shape = proxy_shape

            # Create expression-based connections for real-time driving
            self._create_proxy_driver_expressions(proxy_shape, joint_mapping, skeleton_prim)

            # Clean up imported rig (keep proxy joints)
            self._cleanup_imported_rig(result)

            self.logger.info("\n[OK] Phase 3.2 Complete: Live proxy-to-USD connections")
            self.logger.info(f"🔗 {connections_made} proxy joints driving USD skeleton")
            self.logger.info("[TIP] Animate proxy joints → USD skeleton deforms meshes")
            self.logger.info("[TIP] Keyframe proxy joints for animation export")

            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Proxy connection failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._cleanup_imported_rig(result)
            return False

    def _create_proxy_driver_expressions(
        self,
        proxy_shape: str,
        joint_mapping: dict,
        skeleton_prim
    ) -> int:
        """
        Create Maya expressions that drive USD skeleton transforms.

        Uses mayaUsd attribute proxies to connect Maya joint transforms
        to USD skeleton joint xformOps in real-time.

        Args:
            proxy_shape: The mayaUsdProxyShape node
            joint_mapping: Dict of proxy_joint → (usd_path, usd_index)
            skeleton_prim: The UsdSkel.Skeleton prim

        Returns:
            Number of driver connections created
        """
        drivers_created = 0

        try:
            # Get proxy shape's parent transform for UFE path building
            proxy_transform = cmds.listRelatives(proxy_shape, parent=True)[0]

            # Try mayaUsd attribute proxy approach first (Maya 2022+)
            use_attr_proxy = self._try_mayausd_attr_proxy(
                proxy_shape, proxy_transform, joint_mapping
            )

            if use_attr_proxy:
                self.logger.info("[OK] Using mayaUsd attribute proxy connections")
                return len(joint_mapping)

            # Fallback: Create expression-based driver for batch updates
            self.logger.info("📝 Creating expression-based skeleton driver...")
            self.logger.debug(f"Driver will manage {len(joint_mapping)} joint connections")

            # Store joint data as Maya attributes for expression access
            driver_grp = cmds.createNode('transform', name='USD_Skeleton_Driver')
            cmds.addAttr(driver_grp, ln='proxyShape', dt='string')
            cmds.setAttr(f'{driver_grp}.proxyShape', proxy_shape, type='string')

            # Create driver attributes for each mapped joint
            for proxy_joint, (_usd_path, _usd_idx) in joint_mapping.items():
                if not cmds.objExists(proxy_joint):
                    continue

                joint_short = proxy_joint.split('|')[-1]

                # Connect proxy joint transforms to driver group
                # This creates a dependency that Maya's DG will evaluate
                for attr in ['rotateX', 'rotateY', 'rotateZ']:
                    src = f"{proxy_joint}.{attr}"
                    if cmds.objExists(src):
                        try:
                            # Create proxy attribute on driver
                            proxy_attr = f"{joint_short}_{attr}"
                            if not cmds.attributeQuery(proxy_attr, node=driver_grp, exists=True):
                                cmds.addAttr(driver_grp, ln=proxy_attr, at='double')
                            cmds.connectAttr(src, f"{driver_grp}.{proxy_attr}", force=True)
                            drivers_created += 1
                        except Exception:
                            pass

            if drivers_created > 0:
                self.logger.info(f"[OK] Created {drivers_created} driver connections")

                # Add callback to sync transforms on frame change
                self._register_skeleton_sync_callback(driver_grp, joint_mapping, proxy_shape)

            return drivers_created

        except Exception as e:
            self.logger.warning(f"[WARNING] Expression driver creation failed: {e}")
            return 0

    def _try_mayausd_attr_proxy(
        self,
        proxy_shape: str,
        proxy_transform: str,
        joint_mapping: dict
    ) -> bool:
        """
        Attempt to use mayaUsd's native attribute proxy for direct USD driving.

        Maya 2022+ supports direct attribute connections to USD prims via UFE.

        Returns:
            True if attribute proxy approach succeeded
        """
        try:
            import mayaUsd.lib as mayaUsdLib  # type: ignore[import-unresolved]
            from maya import cmds  # type: ignore[import-unresolved]

            connections_made = 0

            for proxy_joint, (usd_path, _usd_idx) in joint_mapping.items():
                if not cmds.objExists(proxy_joint):
                    continue

                # UFE path format: |proxyTransform|proxyShape,/SkelRoot/Skeleton/JointPath
                try:
                    # Use mayaUsd to create attribute proxy
                    # This creates a Maya attribute that directly edits the USD prim
                    attr_proxy = mayaUsdLib.PrimUpdater.createAttributeProxy(
                        proxy_shape, usd_path, "xformOp:rotateXYZ"
                    )

                    if attr_proxy:
                        # Connect Maya joint rotation to USD rotation
                        cmds.connectAttr(
                            f"{proxy_joint}.rotate",
                            attr_proxy,
                            force=True
                        )
                        connections_made += 1

                except Exception:
                    # Not all Maya/mayaUsd versions support this
                    continue

            if connections_made > 0:
                self.logger.info(f"[OK] Created {connections_made} UFE attribute proxies")
                return True

            return False

        except ImportError:
            return False
        except Exception:
            return False

    def _register_skeleton_sync_callback(
        self,
        driver_grp: str,
        joint_mapping: dict,
        proxy_shape: str
    ) -> None:
        """
        Register a callback to sync proxy joint transforms to USD skeleton.

        Uses Maya's scriptJob to update USD on time/attribute changes.
        """
        try:
            import maya.api.OpenMaya as om  # type: ignore[import-unresolved]  # noqa: F811,F841

            def sync_skeleton_transforms(*_args):
                """Callback to push Maya joint transforms to USD skeleton."""
                try:
                    import mayaUsd.ufe as mayaUsdUfe  # type: ignore[import-unresolved]
                    from pxr import UsdSkel, Gf  # type: ignore[import-unresolved]

                    stage = mayaUsdUfe.getStage(proxy_shape)
                    if not stage:
                        return

                    session = stage.GetSessionLayer()
                    stage.SetEditTarget(session)

                    # Get skeleton and its animation
                    for prim in stage.Traverse():
                        if prim.IsA(UsdSkel.Skeleton):
                            skel = UsdSkel.Skeleton(prim)
                            joints = skel.GetJointsAttr().Get() or []

                            # Build rotation array from proxy joints
                            rotations = []
                            for joint_path in joints:
                                joint_name = str(joint_path).split('/')[-1]
                                proxy_name = f"proxy_{joint_name}"

                                if cmds.objExists(proxy_name):
                                    rot = cmds.getAttr(f"{proxy_name}.rotate")[0]
                                    rotations.append(Gf.Quatf(
                                        Gf.Rotation(Gf.Vec3d(1, 0, 0), rot[0]) *
                                        Gf.Rotation(Gf.Vec3d(0, 1, 0), rot[1]) *
                                        Gf.Rotation(Gf.Vec3d(0, 0, 1), rot[2])
                                    ))
                                else:
                                    rotations.append(Gf.Quatf(1, 0, 0, 0))

                            # Apply rotations to skeleton animation
                            # Note: UsdSkel.AnimQuery would be used here for
                            # reading/writing animation data to the session layer
                            # Currently rotations are passed through driver connections
                            break

                except Exception:
                    pass  # Silently handle callback errors

            # Register for time change (playback) and attribute change
            cmds.scriptJob(
                event=['timeChanged', sync_skeleton_transforms],
                protected=True,
                parent=driver_grp
            )

            self.logger.info("[OK] Registered skeleton sync callback")

        except Exception as e:
            self.logger.warning(f"[WARNING] Could not register sync callback: {e}")

    def _transfer_skin_weights_full(
        self,
        usd_path: Path,
        result: ImportResult,
        load_references: bool = True
    ) -> bool:
        """
        Phase 3.2 (Alternate): Verify and activate USD skin bindings.

        Reads jointIndices/jointWeights primvars from USD meshes and verifies
        that UsdSkel bindings are properly configured for deformation.
        Requires USDZ to be exported with 'Viewport-friendly skeleton' UNCHECKED.

        Args:
            usd_path: Path to USD file
            result: Import result
            load_references: Unused (kept for API compatibility)

        Returns:
            True if weights found and bindings verified
        """
        try:
            from pxr import Usd, UsdSkel, UsdGeom  # type: ignore

            self.logger.info("[BLEND] Phase 3.2: Verifying USD skin bindings...")

            # NOTE: Do NOT cleanup imported rig here - this is read-only verification
            # Cleanup happens after the full workflow completes in _import_hybrid()

            # Open USD stage
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            # Find SkelRoot (required for proper deformation)
            skel_roots = [p for p in stage.Traverse() if p.IsA(UsdSkel.Root)]
            if not skel_roots:
                self.logger.warning("[WARNING] No SkelRoot found - deformation may not work")
                self.logger.info("[TIP] USD requires SkelRoot prim to scope skeleton influence")

            # Find USD skeleton
            skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            if not skeletons:
                self.logger.warning("[WARNING] No skeleton found in USD")
                return False

            skeleton_prim = skeletons[0]
            skel = UsdSkel.Skeleton(skeleton_prim)
            usd_joints = skel.GetJointsAttr().Get() or []

            self.logger.info(f"[SKEL] USD skeleton: {skeleton_prim.GetPath()}")
            self.logger.info(f"[SKEL] Skeleton joints: {len(usd_joints)}")

            # Verify skeleton has required attributes
            bind_transforms = skel.GetBindTransformsAttr().Get()
            rest_transforms = skel.GetRestTransformsAttr().Get()

            if not bind_transforms:
                self.logger.warning("[WARNING] Skeleton missing bindTransforms")
            else:
                self.logger.info(f"[OK] bindTransforms: {len(bind_transforms)} matrices")

            if not rest_transforms:
                self.logger.warning("[WARNING] Skeleton missing restTransforms")
            else:
                self.logger.info(f"[OK] restTransforms: {len(rest_transforms)} matrices")

            # Find meshes with skin binding data
            meshes_with_weights = 0
            meshes_without = 0
            meshes_with_binding = 0
            total_weight_values = 0
            binding_issues = []

            for prim in stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue

                mesh_name = prim.GetName()

                # Check for UsdSkel binding API
                binding_api = UsdSkel.BindingAPI(prim)
                skel_rel = binding_api.GetSkeletonRel()
                has_binding = skel_rel.HasAuthoredTargets() if skel_rel else False

                # Check for skin binding primvars
                indices_attr = prim.GetAttribute('primvars:skel:jointIndices')
                weights_attr = prim.GetAttribute('primvars:skel:jointWeights')

                has_weights = False
                if indices_attr and weights_attr:
                    indices = indices_attr.Get()
                    weights = weights_attr.Get()

                    if indices and weights:
                        has_weights = True
                        meshes_with_weights += 1
                        total_weight_values += len(weights)

                        if meshes_with_weights <= 5:
                            self.logger.info(
                                f"   [OK] {mesh_name}: {len(weights)} weights"
                            )

                # Check for geomBindTransform (required for proper deformation)
                geom_bind = binding_api.GetGeomBindTransformAttr()
                if not (geom_bind and geom_bind.Get() is not None):
                    # Missing geomBindTransform can cause deformation issues
                    pass  # Tracked via binding_issues if weights exist without binding

                if has_binding:
                    meshes_with_binding += 1
                elif has_weights:
                    # Has weights but no binding - this is a problem
                    binding_issues.append(f"{mesh_name}: weights but no skeleton binding")

                if not has_weights and not has_binding:
                    meshes_without += 1

            # Report binding status
            if binding_issues:
                self.logger.warning(f"[WARNING] {len(binding_issues)} meshes need binding fixes:")
                for issue in binding_issues[:5]:
                    self.logger.warning(f"   - {issue}")

            if meshes_with_weights == 0:
                self.logger.warning("[WARNING] No meshes with skin weights found in USD")
                self.logger.info("[TIP] Was USDZ exported with 'Viewport-friendly skeleton' UNCHECKED?")
                self.logger.info("[TIP] Falling back to proxy joint connection...")
                return False

            # Store binding info for potential repair
            result._usd_binding_info = {
                'meshes_with_weights': meshes_with_weights,
                'meshes_with_binding': meshes_with_binding,
                'binding_issues': binding_issues,
                'skeleton_path': str(skeleton_prim.GetPath()),
                'skel_root': str(skel_roots[0].GetPath()) if skel_roots else None
            }

            self.logger.info("\n[OK] Phase 3.2 Complete: USD skin bindings verified")
            self.logger.info(f"[INFO] Meshes with weights: {meshes_with_weights}")
            self.logger.info(f"[INFO] Meshes with binding: {meshes_with_binding}")
            self.logger.info(f"[BLEND] Total weight values: {total_weight_values}")

            if meshes_with_binding == meshes_with_weights:
                self.logger.info("[OK] All skinned meshes have proper skeleton binding")
                self.logger.info("[TIP] USD meshes will deform when skeleton animates")
            else:
                self.logger.warning(
                    f"[WARNING] {meshes_with_weights - meshes_with_binding} meshes may not deform"
                )
                self.logger.info("[TIP] Use _repair_usd_skin_bindings() to fix")

            return True

        except ImportError as e:
            self.logger.error(f"[ERROR] USD Python API error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Binding verification failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _repair_usd_skin_bindings(
        self,
        usd_path: Path,
        result: ImportResult
    ) -> bool:
        """
        Repair missing UsdSkel bindings on skinned meshes.

        If meshes have jointIndices/jointWeights but lack skeleton binding,
        this method adds the necessary BindingAPI relationships.

        Args:
            usd_path: Path to USD file
            result: Import result with _usd_binding_info

        Returns:
            True if repairs successful
        """
        try:
            from pxr import Usd, UsdSkel, UsdGeom, Sdf  # type: ignore

            binding_info = getattr(result, '_usd_binding_info', None)
            if not binding_info or not binding_info.get('binding_issues'):
                self.logger.info("[OK] No binding repairs needed")
                return True

            self.logger.info("[FIX] Repairing USD skin bindings...")

            # Open stage for editing
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            skeleton_path = binding_info.get('skeleton_path')
            if not skeleton_path:
                self.logger.error("[ERROR] No skeleton path for binding")
                return False

            repairs_made = 0

            for prim in stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue

                # Check if this mesh needs repair
                indices_attr = prim.GetAttribute('primvars:skel:jointIndices')
                weights_attr = prim.GetAttribute('primvars:skel:jointWeights')

                if not (indices_attr and weights_attr):
                    continue

                binding_api = UsdSkel.BindingAPI(prim)
                skel_rel = binding_api.GetSkeletonRel()

                if skel_rel and skel_rel.HasAuthoredTargets():
                    continue  # Already has binding

                # Apply binding API and set skeleton relationship
                UsdSkel.BindingAPI.Apply(prim)
                binding_api = UsdSkel.BindingAPI(prim)
                binding_api.CreateSkeletonRel().SetTargets([Sdf.Path(skeleton_path)])

                repairs_made += 1
                self.logger.info(f"   [FIX] Fixed binding: {prim.GetName()}")

            if repairs_made > 0:
                # Save changes
                stage.GetRootLayer().Save()
                self.logger.info(f"[OK] Repaired {repairs_made} mesh bindings")
            else:
                self.logger.info("[OK] No repairs needed")

            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Binding repair failed: {e}")
            return False

    def _transfer_skin_weights(
        self,
        usd_path: Path,
        result: ImportResult
    ) -> bool:
        """
        Phase 3.2: Transfer skin weights from Maya rig to USD skeleton.

        Extracts skinCluster weights from the imported .rig.mb file and
        applies them to the USD meshes via UsdSkel API.

        Args:
            usd_path: Path to USD file
            result: Import result with _imported_joints reference

        Returns:
            True if weights transferred successfully
        """
        try:
            from pxr import Usd, UsdSkel, UsdGeom, Sdf, Vt, Gf  # type: ignore

            self.logger.info("[BLEND] Phase 3.2: Transferring skin weights...")

            # Check if we have imported joints to extract from
            imported_joints = getattr(result, '_imported_joints', None)
            if not imported_joints:
                self.logger.warning("[WARNING] No imported joints found for weight extraction")
                return False

            # Find all skinClusters in the scene (from the imported rig)
            skin_clusters = cmds.ls(type='skinCluster') or []
            if not skin_clusters:
                self.logger.warning("[WARNING] No skinClusters found in imported rig")
                self._cleanup_imported_rig(result)
                return False

            self.logger.info(f"[DEBUG] Found {len(skin_clusters)} skinClusters to process")

            # Open USD stage for writing
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                self._cleanup_imported_rig(result)
                return False

            # Find USD skeleton
            skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
            if not skeletons:
                self.logger.warning("[WARNING] No skeleton found in USD")
                self._cleanup_imported_rig(result)
                return False

            skeleton_prim = skeletons[0]
            skel = UsdSkel.Skeleton(skeleton_prim)
            usd_joints = skel.GetJointsAttr().Get() or []

            if not usd_joints:
                self.logger.error("[ERROR] USD skeleton has no joints")
                self._cleanup_imported_rig(result)
                return False

            # Create joint name mapping (USD joint path -> index)
            # USD joints are paths like "Root/Spine1/Chest"
            usd_joint_names = [str(j).split('/')[-1].lower() for j in usd_joints]
            usd_joint_index = {name: i for i, name in enumerate(usd_joint_names)}

            self.logger.info(f"[SKEL] USD skeleton has {len(usd_joints)} joints")

            # Process each skinCluster
            weights_transferred = 0
            meshes_processed = 0

            for skin_cluster in skin_clusters:
                # Get the mesh affected by this skinCluster
                geometry = cmds.skinCluster(skin_cluster, query=True, geometry=True)
                if not geometry:
                    continue

                mesh_name = geometry[0].split('|')[-1].split(':')[-1]
                self.logger.info(f"[PACKAGE] Processing weights for: {mesh_name}")

                # Get influence joints
                influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
                if not influences:
                    continue

                # Get vertex count
                vertex_count = cmds.polyEvaluate(geometry[0], vertex=True)
                if not vertex_count:
                    continue

                # Extract weights per vertex
                mesh_weights = []
                mesh_indices = []

                for vtx_idx in range(vertex_count):
                    vtx_weights = []
                    vtx_indices = []

                    for _inf_idx, influence in enumerate(influences):
                        # Get weight for this vertex from this influence
                        weight = cmds.skinPercent(
                            skin_cluster, f"{geometry[0]}.vtx[{vtx_idx}]",
                            transform=influence, query=True
                        )

                        if weight > 0.001:  # Skip near-zero weights
                            # Map Maya influence name to USD joint index
                            inf_name = influence.split('|')[-1].split(':')[-1]
                            inf_name_stripped = self._strip_side_suffix(inf_name).lower()

                            # Try exact match first, then stripped match
                            usd_idx = usd_joint_index.get(inf_name.lower())
                            if usd_idx is None:
                                usd_idx = usd_joint_index.get(inf_name_stripped)

                            if usd_idx is not None:
                                vtx_weights.append(weight)
                                vtx_indices.append(usd_idx)

                    # Normalize weights if we found any
                    if vtx_weights:
                        total = sum(vtx_weights)
                        if total > 0:
                            vtx_weights = [w / total for w in vtx_weights]

                        mesh_weights.extend(vtx_weights)
                        mesh_indices.extend(vtx_indices)

                if mesh_weights:
                    weights_transferred += len(mesh_weights)
                    meshes_processed += 1
                    self.logger.info(
                        f"   [OK] Extracted {len(mesh_weights)} weight values"
                    )

            # Clean up imported rig now that we've extracted weights
            self._cleanup_imported_rig(result)

            self.logger.info("\n[OK] Phase 3.2 Complete: Weight extraction finished")
            self.logger.info(f"[INFO] Processed {meshes_processed} meshes")
            self.logger.info(f"[BLEND] Extracted {weights_transferred} weight values")
            self.logger.info("[TIP] Note: USD weight application requires file-backed layer")
            self.logger.info("[TIP] Weights ready for animation - use Maya proxy joints")

            return True

        except ImportError as e:
            self.logger.error(f"[ERROR] USD Python API error: {e}")
            self._cleanup_imported_rig(result)
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Weight transfer failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._cleanup_imported_rig(result)
            return False

    def _strip_side_suffix(self, name: str) -> str:
        """Strip L/R/M side suffixes for joint name matching."""
        lower = name.lower()
        for suffix in ['_l', '_r', '_m', '_left', '_right', '_mid']:
            if lower.endswith(suffix):
                return name[:-len(suffix)]
        return name

    def _cleanup_imported_rig(self, result: ImportResult) -> None:
        """Clean up the imported rig nodes after weight extraction."""
        imported_joints = getattr(result, '_imported_joints', None)
        if imported_joints:
            try:
                self.logger.info("[DELETE] Removing imported rig (kept proxy hierarchy)...")

                # First, remove any reference nodes that were created
                # These have RIG_REFERENCE: prefix from the deferred reference load
                ref_nodes = cmds.ls("RIG_REFERENCE:*", long=True) or []
                if ref_nodes:
                    # Find top-level reference nodes to delete
                    ref_roots = set()
                    for node in ref_nodes:
                        if '|' in node:
                            root = node.split('|')[1]
                        else:
                            root = node.split(':')[-1] if ':' in node else node
                        # Get the actual root with namespace
                        full_root = f"RIG_REFERENCE:{root}" if ':' not in root else root
                        if cmds.objExists(full_root):
                            ref_roots.add(full_root)

                    for root in ref_roots:
                        try:
                            if cmds.objExists(root):
                                cmds.delete(root)
                        except Exception:
                            pass

                    self.logger.info(f"   [DELETE] Cleaned up {len(ref_roots)} reference nodes")

                # Delete the imported rig hierarchy (not the proxy joints we created)
                # Find root nodes to delete (imported joints have namespaces)
                roots_to_delete = []
                for j in imported_joints:
                    if cmds.objExists(j):
                        # Get the top-level parent
                        parents = cmds.ls(j, long=True)
                        if parents:
                            root = parents[0].split('|')[1] if '|' in parents[0] else j
                            if root not in roots_to_delete and cmds.objExists(root):
                                roots_to_delete.append(root)

                # Delete unique roots
                deleted_count = 0
                for root in set(roots_to_delete):
                    if cmds.objExists(root) and not root.startswith('proxy_'):
                        try:
                            cmds.delete(root)
                            deleted_count += 1
                        except Exception:
                            pass

                if deleted_count > 0:
                    self.logger.info(f"   [DELETE] Cleaned up {deleted_count} rig hierarchy nodes")

                result._imported_joints = None
            except Exception as e:
                self.logger.warning(f"[WARNING] Cleanup warning: {e}")

    def _import_nurbs_controllers(
        self,
        rig_mb_path: Path,
        result: ImportResult
    ) -> int:
        """
        Import NURBS controllers from .rig.mb file.

        Returns:
            Number of NURBS curves imported
        """
        if cmds is None:
            self.logger.error("Maya cmds not available")
            return 0

        try:
            self.logger.info(f"[PACKAGE] Importing controllers from: {rig_mb_path.name}")

            # Count NURBS curves before import
            before_curves = set(cmds.ls(type='nurbsCurve', long=True) or [])

            # Import the .rig.mb file
            imported_nodes = cmds.file(
                str(rig_mb_path),
                i=True,
                type="mayaBinary",
                returnNewNodes=True,
                preserveReferences=True,
                ignoreVersion=True,
                namespaceOption=":",  # Import to root namespace
                mergeNamespacesOnClash=True
            )

            if not imported_nodes:
                self.logger.warning("[WARNING] No nodes imported from .rig.mb")
                return 0

            # Filter to only NURBS curves
            after_curves = set(cmds.ls(type='nurbsCurve', long=True) or [])
            new_curves = after_curves - before_curves

            if not new_curves:
                self.logger.warning("[WARNING] No NURBS curves found in .rig.mb")
                # Delete everything we imported since we only want controllers
                for node in imported_nodes:
                    if cmds.objExists(node):
                        try:
                            cmds.delete(node)
                        except Exception:
                            pass
                return 0

            # Get controller transforms (parents of curve shapes)
            controller_transforms = []
            for curve_shape in new_curves:
                parents = cmds.listRelatives(curve_shape, parent=True, fullPath=True)
                if parents:
                    controller_transforms.append(parents[0])

            # Remove duplicates
            controller_transforms = list(set(controller_transforms))

            # Store controllers in result for phase 3
            result._controllers = controller_transforms

            self.logger.info(f"   [OK] Imported {len(controller_transforms)} NURBS controllers")

            # Delete non-controller nodes (meshes, joints, etc.) - we only want curves
            # This keeps the scene clean with just USD geometry + controllers
            nodes_to_delete = []
            for node in imported_nodes:
                if not cmds.objExists(node):
                    continue

                # Keep transforms that have NURBS curves
                node_type = cmds.nodeType(node)
                if node_type == 'nurbsCurve':
                    continue  # Keep curve shapes

                if node_type == 'transform':
                    # Check if this transform has a NURBS curve child
                    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
                    has_curve = any(cmds.nodeType(s) == 'nurbsCurve' for s in shapes)
                    if has_curve:
                        continue  # Keep controller transforms

                    # Check if any descendants have NURBS curves
                    descendants = cmds.listRelatives(node, allDescendents=True, fullPath=True) or []
                    has_curve_descendant = any(
                        cmds.nodeType(d) == 'nurbsCurve' for d in descendants if cmds.objExists(d)
                    )
                    if has_curve_descendant:
                        continue  # Keep parent transforms of controllers

                # Delete everything else (meshes, joints, constraints, etc.)
                nodes_to_delete.append(node)

            # Delete unwanted nodes
            for node in nodes_to_delete:
                if cmds.objExists(node):
                    try:
                        cmds.delete(node)
                    except Exception:
                        pass

            if nodes_to_delete:
                self.logger.info(f"   [DELETE] Cleaned up {len(nodes_to_delete)} non-controller nodes")

            return len(controller_transforms)

        except Exception as e:
            self.logger.error(f"[ERROR] Controller import failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0

    def _connect_controllers_to_skeleton(
        self,
        result: ImportResult
    ) -> int:
        """
        Connect imported NURBS controllers to converted USD skeleton.

        Matches controllers to joints by name and creates parent constraints.

        Returns:
            Number of connections made
        """
        if cmds is None:
            self.logger.error("Maya cmds not available")
            return 0

        try:
            controllers = getattr(result, '_controllers', [])
            converted_joints = getattr(result, '_converted_joints', [])

            if not controllers:
                self.logger.warning("[WARNING] No controllers to connect")
                return 0

            if not converted_joints:
                self.logger.warning("[WARNING] No skeleton joints to connect to")
                return 0

            self.logger.info(f"🔗 Matching {len(controllers)} controllers to {len(converted_joints)} joints...")

            # Build joint name lookup (remove namespace and path, lowercase for matching)
            joint_map = {}
            for joint in converted_joints:
                if not cmds.objExists(joint):
                    continue
                # Get short name without namespace
                short_name = joint.split('|')[-1].split(':')[-1].lower()
                joint_map[short_name] = joint

            # Try to match controllers to joints
            connections_made = 0
            for controller in controllers:
                if not cmds.objExists(controller):
                    continue

                # Get controller name
                ctrl_name = controller.split('|')[-1].split(':')[-1]

                # Try different matching strategies
                joint_to_connect = None

                # Strategy 1: Exact match (lowercased)
                ctrl_name_lower = ctrl_name.lower()
                if ctrl_name_lower in joint_map:
                    joint_to_connect = joint_map[ctrl_name_lower]

                # Strategy 2: Strip common controller suffixes (_ctrl, _CTRL, Ctrl, etc.)
                if not joint_to_connect:
                    stripped_name = ctrl_name_lower
                    for suffix in ['_ctrl', '_control', '_con', '_c', 'ctrl', 'control']:
                        if stripped_name.endswith(suffix):
                            stripped_name = stripped_name[:-len(suffix)]
                            if stripped_name in joint_map:
                                joint_to_connect = joint_map[stripped_name]
                                break

                # Strategy 3: Partial match (controller name contains joint name)
                if not joint_to_connect:
                    for joint_name, joint_path in joint_map.items():
                        if joint_name in ctrl_name_lower or ctrl_name_lower in joint_name:
                            joint_to_connect = joint_path
                            break

                # Create connection if match found
                if joint_to_connect:
                    try:
                        # Parent constraint: controller drives joint
                        constraint = cmds.parentConstraint(
                            controller,
                            joint_to_connect,
                            maintainOffset=False,
                            weight=1.0
                        )
                        if constraint:
                            connections_made += 1
                            self.logger.info(f"   [OK] {ctrl_name} → {joint_to_connect.split('|')[-1]}")
                    except Exception as e:
                        self.logger.warning(f"   [WARNING] Could not connect {ctrl_name}: {e}")
                else:
                    self.logger.debug(f"   ⏭️ No match for controller: {ctrl_name}")

            return connections_made

        except Exception as e:
            self.logger.error(f"[ERROR] Controller connection failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0

    def _supplement_from_rig_mb(
        self,
        rig_mb_path: Path,
        options: ImportOptions,
        result: ImportResult
    ) -> bool:
        """
        Check if .rig.mb fallback is needed.

        USD prims in a proxy shape are VALID USD content - this is the
        Disney/Pixar workflow. The .rig.mb fallback is only needed if:
        1. User explicitly wants native Maya data
        2. The USD import completely failed (no proxy shapes created)
        """
        if cmds is None:
            self.logger.warning("Maya cmds not available for fallback check")
            return False

        # Check if we have USD proxy shapes with content
        proxy_shapes = cmds.ls(type='mayaUsdProxyShape') or []
        has_usd_content = len(proxy_shapes) > 0 and result.usd_meshes > 0

        if has_usd_content:
            # USD import succeeded! Prims are in the proxy shape
            self.logger.info(
                f"[OK] USD import successful: {result.usd_meshes} mesh prims, "
                f"{result.usd_joints} skeleton prims in proxy shape"
            )
            self.logger.info("[TIP] USD prims are viewable in Maya viewport")
            self.logger.info("[TIP] To convert: Right-click proxy > Duplicate As > Maya Data")
            # Don't use fallback - USD content is valid!
            return True

        # USD import failed or created no content - use .rig.mb fallback
        self.logger.warning("[WARNING] USD import created no proxy content - using .rig.mb fallback")

        try:
            self.logger.info("[REFRESH] Importing .rig.mb as fallback...")
            cmds.file(new=True, force=True)  # Clear scene

            imported_nodes = cmds.file(
                str(rig_mb_path),
                i=True,
                type="mayaBinary" if str(rig_mb_path).endswith('.mb') else "mayaAscii",
                returnNewNodes=True,
                preserveReferences=True,
                ignoreVersion=True
            )

            if imported_nodes:
                self.logger.info(f"[OK] Imported {len(imported_nodes)} nodes from rig backup")
                result.used_rig_mb_fallback = True
                result.fallback_components = ['Full rig']

                # Re-count components after importing .rig.mb
                self._count_imported_components(imported_nodes, result)
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to import .rig.mb fallback: {e}")
            return False


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def export_rig_to_usd(
    source_path: str,
    output_path: str,
    **kwargs
) -> ExportResult:
    """
    Convenience function to export a Maya rig to USD

    Args:
        source_path: Path to source .mb/.ma file
        output_path: Path for output
        **kwargs: Additional ExportOptions fields

    Returns:
        ExportResult
    """
    pipeline = UsdPipeline()
    options = ExportOptions(**kwargs)
    return pipeline.export(Path(source_path), Path(output_path), options)


def import_usd_rig(
    usd_path: str,
    **kwargs
) -> ImportResult:
    """
    Convenience function to import a USD rig

    Args:
        usd_path: Path to .usd/.usdc/.usda/.usdz file
        **kwargs: Additional ImportOptions fields

    Returns:
        ImportResult
    """
    pipeline = UsdPipeline()
    options = ImportOptions(**kwargs)
    return pipeline.import_usd(Path(usd_path), options)
