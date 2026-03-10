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
import os
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


