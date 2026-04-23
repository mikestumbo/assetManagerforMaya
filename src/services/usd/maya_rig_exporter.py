"""
Maya Rig Exporter - Export rig data to .mrig format

This module exports Maya rig components (controllers, constraints, blendshapes,
IK handles, SDKs) to a JSON .mrig file that can be applied on top of
USD-imported geometry.

Clean Code: Single Responsibility - Handles only rig data export
SOLID: Open/Closed - Extensible for new rig component types

Author: Mike Stumbo
Version: 1.5.0
License: MIT

Enhancements in v1.5.0:
- Progress callback for UI feedback
- Validation pass before export
- Space switch support
- Custom attribute preservation
- Proxy attribute handling
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict

# Maya imports (conditional)
try:
    import maya.cmds as cmds  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    cmds = None


# Data structures for rig components
@dataclass
class ControllerData:
    """Controller/control curve data"""

    name: str
    transform: Dict[str, List[float]]  # translate, rotate, scale
    shape_type: str  # nurbs, locator
    color: Optional[int]  # override color
    parent: Optional[str]
    curve_data: Optional[Dict]  # CV positions, degree, form for NURBS curves
    custom_attrs: Optional[Dict]  # v1.5.0: Custom attributes
    proxy_attrs: Optional[Dict]  # v1.5.0: Proxy attribute connections


@dataclass
class ConstraintData:
    """Constraint data"""

    name: str
    type: str  # parentConstraint, orientConstraint, etc.
    driven: str
    drivers: List[str]
    maintain_offset: bool
    weights: List[float]
    skip_translate: List[str]
    skip_rotate: List[str]


@dataclass
class SpaceSwitchData:
    """v1.5.0: Space switch configuration"""

    name: str
    control: str
    attribute: str  # The enum attribute for switching
    spaces: List[Dict]  # {name, target, weight_attr}
    constraint: str  # The parent constraint driving this


@dataclass
class IKHandleData:
    """IK handle data"""

    name: str
    start_joint: str
    end_joint: str
    solver: str
    priority: int
    pole_vector: Optional[str]


@dataclass
class BlendShapeData:
    """Blendshape deformer data"""

    name: str
    base_geometry: str
    targets: List[Dict]  # target name, weight, deltas, in-betweens


@dataclass
class BlendShapeConnectionData:
    """Connection driving a blendshape target"""

    blendshape: str
    target: str
    driver: str  # e.g., "Smile_Ctrl.translateY"
    connection_type: str  # "direct", "sdk", "expression"
    sdk_keys: Optional[List[List[float]]]  # [[input, output], ...]


@dataclass
class SetDrivenKeyData:
    """Set Driven Key data"""

    driver: str  # "Control.attribute"
    driven: str  # "Target.attribute"
    keys: List[List[float]]  # [[driver_value, driven_value], ...]


@dataclass
class ValidationResult:
    """v1.5.0: Pre-export validation result"""

    valid: bool
    errors: List[str]
    warnings: List[str]
    unsupported_nodes: List[str]


class MayaRigExporter:
    """
    Export Maya rig data to .mrig format

    Clean Code: Single Responsibility - Rig data export only
    SOLID: Interface Segregation - Focused interface for rig export

    v1.5.0 Enhancements:
    - Progress callback for UI feedback
    - Validation pass before export
    - Space switch support
    - Custom attribute preservation
    - Proxy attribute handling
    """

    def __init__(self):
        """Initialize rig exporter"""
        self.logger = logging.getLogger(__name__)
        self._progress_callback: Optional[Callable[[str, int], None]] = None

    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """
        Set progress callback for UI feedback

        Args:
            callback: Function(stage_name: str, percent: int) -> None
        """
        self._progress_callback = callback

    def _report_progress(self, stage: str, percent: int) -> None:
        """Report progress to callback if set"""
        if self._progress_callback:
            self._progress_callback(stage, percent)
        self.logger.debug(f"Progress: {stage} ({percent}%)")

    def validate_rig(self, skeleton_root: Optional[str] = None) -> ValidationResult:
        """
        v1.5.0: Pre-export validation pass

        Checks for unsupported node types, broken connections, and missing hierarchies.

        Args:
            skeleton_root: Optional skeleton root joint

        Returns:
            ValidationResult with errors, warnings, and unsupported nodes
        """
        if not MAYA_AVAILABLE or cmds is None:
            return ValidationResult(
                valid=False, errors=["Maya not available"], warnings=[], unsupported_nodes=[]
            )

        errors = []
        warnings = []
        unsupported = []

        self._report_progress("Validating rig", 0)

        # Check skeleton root exists
        if skeleton_root and not cmds.objExists(skeleton_root):
            errors.append(f"Skeleton root '{skeleton_root}' not found")

        # Check for unsupported node types
        unsupported_types = ["expression", "script", "unknown", "reference"]
        for node_type in unsupported_types:
            nodes = cmds.ls(type=node_type) or []
            for node in nodes:
                unsupported.append(f"{node} ({node_type})")

        self._report_progress("Checking constraints", 25)

        # Check for broken constraints
        constraint_types = [
            "parentConstraint",
            "orientConstraint",
            "pointConstraint",
            "aimConstraint",
            "scaleConstraint",
        ]
        for ctype in constraint_types:
            constraints = cmds.ls(type=ctype) or []
            for constraint in constraints:
                # Check if constraint has targets
                targets = (
                    cmds.parentConstraint(constraint, q=True, tl=True)
                    if ctype == "parentConstraint"
                    else []
                )
                if not targets:
                    warnings.append(f"Constraint {constraint} may have no valid targets")

        self._report_progress("Checking blendshapes", 50)

        # Check blendshape connections
        blendshapes = cmds.ls(type="blendShape") or []
        for bs in blendshapes:
            # Check if base geometry exists
            geo = cmds.blendShape(bs, q=True, geometry=True) or []
            if not geo:
                warnings.append(f"Blendshape {bs} has no base geometry")

        self._report_progress("Checking IK handles", 75)

        # Check IK handles
        ik_handles = cmds.ls(type="ikHandle") or []
        for ik in ik_handles:
            start = cmds.ikHandle(ik, q=True, startJoint=True)
            end = cmds.ikHandle(ik, q=True, endEffector=True)
            if not start or not end:
                warnings.append(f"IK handle {ik} has missing joints")

        self._report_progress("Validation complete", 100)

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, unsupported_nodes=unsupported
        )

    def export_rig(
        self,
        output_path: Path,
        skeleton_root: Optional[str] = None,
        options: Optional[Dict] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Export rig data to rig file

        v2.0: Supports both Maya Binary/ASCII (.rig.mb/.rig.ma) and legacy .mrig

        Args:
            output_path: Path to write rig file
            skeleton_root: Optional skeleton root joint
            options: Export options dict:
                - rig_format: 'mayaBinary' or 'mayaAscii' (v2.0 - fast Maya file)
                - rig_path: Optional separate path for Maya rig file
                - export_controllers, export_constraints, etc.
            progress_callback: Optional callback for progress updates

        Returns:
            (success: bool, message: str)
        """
        if not MAYA_AVAILABLE:
            return False, "Maya not available"

        # Set progress callback if provided
        if progress_callback:
            self.set_progress_callback(progress_callback)

        # Satisfy type checkers: cmds is guaranteed when MAYA_AVAILABLE is True
        assert cmds is not None

        try:
            options = options or {}

            # v2.0: Check if we're using Maya format (fast) or legacy .mrig (slow)
            rig_format = options.get("rig_format", None)
            rig_path = options.get("rig_path", None)

            # If rig_format is specified, export directly to Maya file
            if rig_format in ("mayaBinary", "mayaAscii"):
                self.logger.info(f"🎮 v2.0: Exporting rig directly to Maya format ({rig_format})")
                return self._export_maya_rig_file(
                    output_path=rig_path or output_path,
                    rig_format=rig_format,
                    skeleton_root=skeleton_root,
                    options=options,
                )

            # Legacy: Export to .mrig JSON format
            self._report_progress("Initializing export", 0)

            # v1.5.0: Run validation if requested
            if options.get("validate_before_export", True):
                self._report_progress("Validating rig", 5)
                validation = self.validate_rig(skeleton_root)
                if not validation.valid:
                    return False, f"Validation failed: {'; '.join(validation.errors)}"
                if validation.warnings:
                    self.logger.warning(f"Validation warnings: {validation.warnings}")

            # Build rig data structure
            rig_data = {
                "version": "1.5.0",  # v1.5.0: Updated version
                "skeleton_root": skeleton_root,
                "controllers": [],
                "constraints": [],
                "space_switches": [],  # v1.5.0: Space switches
                "ik_handles": [],
                "blendshapes": [],
                "blendshape_connections": [],
                "set_driven_keys": [],
                "custom_attributes": [],  # v1.5.0: Custom attrs
            }

            # Extract scene name from current file
            scene_file = cmds.file(query=True, sceneName=True)
            if scene_file:
                rig_data["source_scene"] = Path(scene_file).name

            # Collect rig components based on options
            self.logger.info(f"[TOOL] Exporting rig data to: {output_path}")

            # Extract controllers (NURBS curves, locators) with custom/proxy attrs
            self._report_progress("Extracting controllers", 15)
            if options.get("export_controllers", True):
                controllers = self._extract_controllers(
                    include_custom_attrs=options.get("export_custom_attrs", True),
                    include_proxy_attrs=options.get("export_proxy_attrs", True),
                )
                rig_data["controllers"] = controllers
                self.logger.info(f"     [OK] {len(controllers)} controllers")

            # Extract constraints
            self._report_progress("Extracting constraints", 30)
            if options.get("export_constraints", True):
                constraints = self._extract_constraints()
                rig_data["constraints"] = constraints
                self.logger.info(f"     [OK] {len(constraints)} constraints")

            # v1.5.0: Extract space switches
            self._report_progress("Extracting space switches", 40)
            if options.get("export_space_switches", True):
                space_switches = self._extract_space_switches()
                rig_data["space_switches"] = space_switches
                self.logger.info(f"     [OK] {len(space_switches)} space switches")

            # Extract IK handles
            self._report_progress("Extracting IK handles", 55)
            if options.get("export_ik_handles", True):
                ik_handles = self._extract_ik_handles()
                rig_data["ik_handles"] = ik_handles
                self.logger.info(f"     [OK] {len(ik_handles)} IK handles")

            # Extract blendshapes
            self._report_progress("Extracting blendshapes", 70)
            if options.get("export_blendshapes", True):
                blendshapes, connections = self._extract_blendshapes()
                rig_data["blendshapes"] = blendshapes
                rig_data["blendshape_connections"] = connections
                self.logger.info(
                    f"     [OK] {len(blendshapes)} blendshapes, {len(connections)} connections"
                )

            # Extract Set Driven Keys
            self._report_progress("Extracting SDKs", 85)
            if options.get("export_sdks", True):
                sdks = self._extract_set_driven_keys()
                rig_data["set_driven_keys"] = sdks
                self.logger.info(f"     [OK] {len(sdks)} SDKs")

            # Write to JSON file
            self._report_progress("Writing file", 90)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(rig_data, f, indent=2, default=self._json_encoder)

            # Log success
            file_size = output_path.stat().st_size / 1024  # KB
            self.logger.info(f"[OK] Rig data exported: {output_path} ({file_size:.1f} KB)")

            # v1.5.0: Export controllers to separate .ma file for referencing
            # This avoids trying to recreate NURBS curves from JSON
            self._report_progress("Exporting controllers .ma", 95)
            if options.get("export_controllers", True) and rig_data.get("controllers"):
                ma_path = self._export_controllers_ma(output_path, rig_data["controllers"])
                if ma_path:
                    rig_data["controllers_ma_file"] = ma_path.name
                    # Re-write .mrig with the .ma reference added
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(rig_data, f, indent=2, default=self._json_encoder)
                    self.logger.info(f"[OK] Controllers .ma exported: {ma_path.name}")

            self._report_progress("Export complete", 100)
            return True, f"Exported rig data to {output_path.name}"

        except Exception as e:
            self.logger.error(f"[ERROR] Failed to export rig data: {e}")
            return False, f"Export failed: {e}"

    def _export_maya_rig_file(
        self,
        output_path: Path,
        rig_format: str,
        skeleton_root: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> Tuple[bool, str]:
        """
        v2.0: Export rig directly to Maya Binary/ASCII file

        UNIVERSAL RIG SUPPORT - Works with ANY Maya rig:
        - Advanced Skeleton, mGear, custom rigs, etc.
        - Collects all rig components by NODE TYPE, not by name
        - Maya file preserves everything natively

        Args:
            output_path: Path to write .rig.mb or .rig.ma file
            rig_format: 'mayaBinary' or 'mayaAscii'
            skeleton_root: Optional skeleton root joint (for selecting hierarchy)
            options: Export options dict

        Returns:
            (success: bool, message: str)
        """
        assert cmds is not None
        import maya.mel as mel

        try:
            self._report_progress("Preparing rig export", 5)
            options = options or {}

            # Collect all rig-related nodes to export
            nodes_to_export = []
            node_counts = {}  # Track counts for logging

            # ================================================================
            # CONTROLLERS & CURVES
            # ================================================================
            self._report_progress("Collecting controllers", 10)

            # NURBS curves (most common controller type)
            nurbs_curves = cmds.ls(type="nurbsCurve", long=True) or []
            curve_transforms = []
            for curve in nurbs_curves:
                parents = cmds.listRelatives(curve, parent=True, fullPath=True)
                if parents:
                    curve_transforms.append(parents[0])
            nodes_to_export.extend(curve_transforms)
            node_counts["NURBS Controllers"] = len(curve_transforms)

            # Locators (often used for pole vectors, space targets)
            locators = cmds.ls(type="locator", long=True) or []
            locator_transforms = []
            for loc in locators:
                parents = cmds.listRelatives(loc, parent=True, fullPath=True)
                if parents:
                    locator_transforms.append(parents[0])
            nodes_to_export.extend(locator_transforms)
            node_counts["Locators"] = len(locator_transforms)

            # ================================================================
            # SKELETON
            # ================================================================
            self._report_progress("Collecting skeleton", 20)
            joints = cmds.ls(type="joint", long=True) or []
            nodes_to_export.extend(joints)
            node_counts["Joints"] = len(joints)

            # ================================================================
            # IK SYSTEM
            # ================================================================
            self._report_progress("Collecting IK system", 30)

            # IK handles
            ik_handles = cmds.ls(type="ikHandle", long=True) or []
            nodes_to_export.extend(ik_handles)
            node_counts["IK Handles"] = len(ik_handles)

            # IK effectors
            ik_effectors = cmds.ls(type="ikEffector", long=True) or []
            nodes_to_export.extend(ik_effectors)
            node_counts["IK Effectors"] = len(ik_effectors)

            # Spline IK curves
            # (already captured as nurbsCurve, but ensure ikSplineHandle curves are included)

            # ================================================================
            # CONSTRAINTS
            # ================================================================
            self._report_progress("Collecting constraints", 40)
            constraint_types = [
                "parentConstraint",
                "orientConstraint",
                "pointConstraint",
                "aimConstraint",
                "scaleConstraint",
                "poleVectorConstraint",
                "tangentConstraint",
                "geometryConstraint",
                "normalConstraint",
            ]
            total_constraints = 0
            for ctype in constraint_types:
                constraints = cmds.ls(type=ctype, long=True) or []
                nodes_to_export.extend(constraints)
                total_constraints += len(constraints)
            node_counts["Constraints"] = total_constraints

            # ================================================================
            # DEFORMERS
            # ================================================================
            self._report_progress("Collecting deformers", 50)

            # Blendshapes (facial, correctives)
            blendshapes = cmds.ls(type="blendShape") or []
            nodes_to_export.extend(blendshapes)
            node_counts["Blendshapes"] = len(blendshapes)

            # Clusters (often used in ribbon rigs, face rigs)
            clusters = cmds.ls(type="cluster") or []
            cluster_handles = []
            for cluster in clusters:
                # Get the cluster handle transform
                handle = cmds.listConnections(cluster + ".matrix", source=True)
                if handle:
                    cluster_handles.extend(handle)
            nodes_to_export.extend(clusters)
            nodes_to_export.extend(cluster_handles)
            node_counts["Clusters"] = len(clusters)

            # Lattices (for squash/stretch, bulge effects)
            lattices = cmds.ls(type="lattice", long=True) or []
            ffd_deformers = cmds.ls(type="ffd") or []
            lattice_transforms = []
            for lattice in lattices:
                parents = cmds.listRelatives(lattice, parent=True, fullPath=True)
                if parents:
                    lattice_transforms.append(parents[0])
            nodes_to_export.extend(lattices)
            nodes_to_export.extend(ffd_deformers)
            nodes_to_export.extend(lattice_transforms)
            node_counts["Lattices"] = len(lattices)

            # Wire deformers
            wires = cmds.ls(type="wire") or []
            nodes_to_export.extend(wires)
            node_counts["Wire Deformers"] = len(wires)

            # Wrap deformers
            wraps = cmds.ls(type="wrap") or []
            nodes_to_export.extend(wraps)
            node_counts["Wrap Deformers"] = len(wraps)

            # Non-linear deformers (bend, twist, squash, flare, sine, wave)
            nonlinear_types = [
                "nonLinear",
                "deformBend",
                "deformTwist",
                "deformSquash",
                "deformFlare",
                "deformSine",
                "deformWave",
            ]
            nonlinears = []
            for nltype in nonlinear_types:
                nl = cmds.ls(type=nltype, long=True) or []
                nonlinears.extend(nl)
            nodes_to_export.extend(nonlinears)
            node_counts["Non-Linear Deformers"] = len(nonlinears)

            # Skinning (skinCluster, deltaMush, tension)
            skin_clusters = cmds.ls(type="skinCluster") or []
            nodes_to_export.extend(skin_clusters)
            node_counts["Skin Clusters"] = len(skin_clusters)

            delta_mush = cmds.ls(type="deltaMush") or []
            nodes_to_export.extend(delta_mush)
            node_counts["Delta Mush"] = len(delta_mush)

            tension = cmds.ls(type="tension") or []
            nodes_to_export.extend(tension)
            node_counts["Tension Deformers"] = len(tension)

            # Proximity wrap (Maya 2020+)
            try:
                prox_wrap = cmds.ls(type="proximityWrap") or []
                nodes_to_export.extend(prox_wrap)
                node_counts["Proximity Wrap"] = len(prox_wrap)
            except Exception:
                pass  # Type may not exist in older Maya

            # ================================================================
            # ANIMATION CURVES & SDKs
            # ================================================================
            self._report_progress("Collecting animation/SDKs", 60)

            # SDK animation curves (driven by attributes, not time)
            anim_curves = (
                cmds.ls(type=["animCurveUA", "animCurveUL", "animCurveUT", "animCurveUU"]) or []
            )
            nodes_to_export.extend(anim_curves)
            node_counts["SDK Curves"] = len(anim_curves)

            # Time-based animation curves (if user wants animation)
            if options.get("export_animation", False):
                time_curves = (
                    cmds.ls(type=["animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"])
                    or []
                )
                nodes_to_export.extend(time_curves)
                node_counts["Animation Curves"] = len(time_curves)

            # ================================================================
            # UTILITY NODES
            # ================================================================
            self._report_progress("Collecting utility nodes", 70)

            # Multiply/Divide, Condition, Reverse, Clamp, etc.
            utility_types = [
                "multiplyDivide",
                "plusMinusAverage",
                "reverse",
                "clamp",
                "condition",
                "blendColors",
                "blendTwoAttr",
                "setRange",
                "remapValue",
                "unitConversion",
                "distanceBetween",
                "vectorProduct",
                "pointOnCurveInfo",
                "pointOnSurfaceInfo",
                "closestPointOnSurface",
                "closestPointOnMesh",
                "nearestPointOnCurve",
                "curveInfo",
                "arcLengthDimension",
                "angleBetween",
                "addDoubleLinear",
                "multDoubleLinear",
            ]
            total_utils = 0
            for utype in utility_types:
                utils = cmds.ls(type=utype) or []
                nodes_to_export.extend(utils)
                total_utils += len(utils)
            node_counts["Utility Nodes"] = total_utils

            # Matrix nodes (common in modern rigs)
            matrix_types = [
                "decomposeMatrix",
                "composeMatrix",
                "inverseMatrix",
                "multMatrix",
                "wtAddMatrix",
                "pointMatrixMult",
                "fourByFourMatrix",
                "holdMatrix",
                "aimMatrix",
                "blendMatrix",
            ]
            total_matrix = 0
            for mtype in matrix_types:
                mtx = cmds.ls(type=mtype) or []
                nodes_to_export.extend(mtx)
                total_matrix += len(mtx)
            node_counts["Matrix Nodes"] = total_matrix

            # ================================================================
            # SELECTION SETS
            # ================================================================
            self._report_progress("Collecting sets", 75)

            # Object sets (control sets, deformer sets)
            all_sets = cmds.ls(type="objectSet") or []
            # Filter to rig-related sets (exclude default sets)
            default_sets = [
                "defaultLightSet",
                "defaultObjectSet",
                "initialParticleSE",
                "initialShadingGroup",
                "defaultTextureList1",
            ]
            rig_sets = [
                s
                for s in all_sets
                if s not in default_sets
                and not s.startswith("tweakSet")
                and not cmds.objectType(s, isAType="shadingEngine")
            ]
            nodes_to_export.extend(rig_sets)
            node_counts["Selection Sets"] = len(rig_sets)

            # ================================================================
            # RIG GROUPS & TRANSFORMS
            # ================================================================
            self._report_progress("Collecting rig groups", 80)

            # Get transforms that are likely rig organization groups
            # (transforms with children but no shape)
            all_transforms = cmds.ls(type="transform", long=True) or []
            rig_groups = []
            for xform in all_transforms:
                # Skip if already collected (controller parents, etc.)
                if xform in nodes_to_export:
                    continue
                # Check if it's a group (has children, no shape)
                shapes = cmds.listRelatives(xform, shapes=True, fullPath=True) or []
                children = cmds.listRelatives(xform, children=True) or []
                if children and not shapes:
                    # Check if any child is in our export list (it's a rig group)
                    for child in children:
                        child_long = cmds.ls(child, long=True)
                        if child_long and child_long[0] in nodes_to_export:
                            rig_groups.append(xform)
                            break
            nodes_to_export.extend(rig_groups)
            node_counts["Rig Groups"] = len(rig_groups)

            # Remove duplicates while preserving order
            seen = set()
            unique_nodes = []
            for node in nodes_to_export:
                if node not in seen and cmds.objExists(node):
                    seen.add(node)
                    unique_nodes.append(node)

            if not unique_nodes:
                return False, "No rig components found to export"

            # Log detailed breakdown of collected nodes
            self.logger.info("🎮 UNIVERSAL RIG EXPORT - Collecting rig components:")
            for category, count in node_counts.items():
                if count > 0:
                    self.logger.info(f"     [OK] {category}: {count}")
            self.logger.info(f"     [PACKAGE] TOTAL: {len(unique_nodes)} nodes to export")

            # Select nodes for export
            self._report_progress("Exporting rig file", 85)
            cmds.select(unique_nodes, replace=True, noExpand=True)

            # Suppress warnings during export
            original_warning = mel.eval("scriptEditorInfo -q -suppressWarnings")
            mel.eval("scriptEditorInfo -suppressWarnings true")

            try:
                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Export as Maya file
                self._report_progress("Writing Maya file", 90)
                cmds.file(
                    str(output_path),
                    exportSelected=True,
                    type=rig_format,
                    force=True,
                    preserveReferences=False,
                    constructionHistory=True,  # Keep history for SDKs
                    channels=True,  # Keep animation channels
                    constraints=True,  # Keep constraints
                    expressions=True,  # Keep expressions if any
                    shader=False,  # Don't need shaders
                )

            finally:
                mel.eval(f"scriptEditorInfo -suppressWarnings {original_warning}")
                cmds.select(clear=True)

            # Report success with breakdown
            file_size = output_path.stat().st_size / 1024
            self._report_progress("Export complete", 100)
            self.logger.info(f"[OK] Rig file exported: {output_path.name} ({file_size:.1f} KB)")

            # Build summary message
            summary_parts = []
            for category, count in node_counts.items():
                if count > 0:
                    summary_parts.append(f"{count} {category.lower()}")
            summary = ", ".join(summary_parts[:5])  # First 5 categories
            if len(summary_parts) > 5:
                summary += f" + {len(summary_parts) - 5} more types"

            return True, f"Exported {len(unique_nodes)} nodes ({summary}) to {output_path.name}"

        except Exception as e:
            self.logger.error(f"[ERROR] Failed to export Maya rig file: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return False, f"Maya rig export failed: {e}"

    def _json_encoder(self, obj):
        """Custom JSON encoder for dataclasses"""
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _export_controllers_ma(self, mrig_path: Path, controllers: List[Dict]) -> Optional[Path]:
        """
        v1.5.0: Export controller curves to a separate .ma file for referencing

        This solves the import hang issue - NURBS curves don't transfer well via JSON,
        but reference cleanly as native Maya files.

        Args:
            mrig_path: Path to the .mrig file (used to derive .ma filename)
            controllers: List of controller data dicts

        Returns:
            Path to exported .ma file, or None if export failed
        """
        if cmds is None or not controllers:
            return None

        mb_path = mrig_path.with_suffix(".controllers.mb")

        try:
            # Get list of controller transform names
            controller_names = []
            for ctrl in controllers:
                name = ctrl.get("name")
                if name and cmds.objExists(name):
                    controller_names.append(name)

            if not controller_names:
                self.logger.warning("No existing controllers found to export")
                return None

            self.logger.info(f"Exporting {len(controller_names)} controllers to Maya Binary...")

            # Select controllers for export
            cmds.select(controller_names, replace=True, noExpand=True)

            # Suppress constraint connection warnings during export
            # These occur because controllers may have constraint connections that
            # reference locked attributes - safe to ignore during export
            import maya.mel as mel

            original_warning_level = mel.eval("scriptEditorInfo -q -suppressWarnings")
            original_error_level = mel.eval("scriptEditorInfo -q -suppressErrors")
            mel.eval("scriptEditorInfo -suppressWarnings true")
            mel.eval("scriptEditorInfo -suppressErrors true")

            try:
                # Export directly as Maya Binary with options to exclude connections
                # This is faster than duplicating first
                cmds.file(
                    str(mb_path),
                    exportSelected=True,
                    type="mayaBinary",
                    force=True,
                    preserveReferences=False,
                    constructionHistory=False,
                    channels=False,
                    constraints=False,
                    expressions=False,
                    shader=False,
                )
            finally:
                # Restore original warning/error levels
                mel.eval(
                    f"scriptEditorInfo -suppressWarnings {str(original_warning_level).lower()}"
                )
                mel.eval(f"scriptEditorInfo -suppressErrors {str(original_error_level).lower()}")

            cmds.select(clear=True)

            self.logger.info(f"✓ Exported {len(controller_names)} controllers to {mb_path.name}")
            return mb_path

        except Exception as e:
            self.logger.error(f"Failed to export controllers .mb: {e}")
            return None

    def _extract_controllers(
        self, include_custom_attrs: bool = True, include_proxy_attrs: bool = True
    ) -> List[Dict]:
        """
        Extract controller curves and locators

        Args:
            include_custom_attrs: v1.5.0 - Include user-defined attributes
            include_proxy_attrs: v1.5.0 - Include proxy attribute connections
        """
        if cmds is None:
            return []

        controllers = []

        # Find all NURBS curves (typical controllers)
        nurbs_curves = cmds.ls(type="nurbsCurve") or []

        for curve_shape in nurbs_curves:
            try:
                # Get transform node
                transforms = cmds.listRelatives(curve_shape, parent=True, fullPath=True) or []
                if not transforms:
                    continue

                transform = transforms[0]

                # Get transform data
                translate = cmds.xform(transform, query=True, translation=True, worldSpace=False)
                rotate = cmds.xform(transform, query=True, rotation=True, worldSpace=False)
                scale = cmds.xform(transform, query=True, scale=True, relative=True)

                # Get parent
                parent = None
                parents = cmds.listRelatives(transform, parent=True, fullPath=True) or []
                if parents:
                    parent = parents[0]

                # Get curve data
                curve_data = self._extract_curve_data(curve_shape)

                # Get color override
                color = None
                if cmds.getAttr(f"{transform}.overrideEnabled"):
                    color = cmds.getAttr(f"{transform}.overrideColor")

                # v1.5.0: Extract custom attributes
                custom_attrs = None
                if include_custom_attrs:
                    custom_attrs = self._extract_custom_attributes(transform)

                # v1.5.0: Extract proxy attributes
                proxy_attrs = None
                if include_proxy_attrs:
                    proxy_attrs = self._extract_proxy_attributes(transform)

                controller_data = ControllerData(
                    name=transform.split("|")[-1],  # Short name
                    transform={"translate": translate, "rotate": rotate, "scale": scale},
                    shape_type="nurbs",
                    color=color,
                    parent=parent.split("|")[-1] if parent else None,
                    curve_data=curve_data,
                    custom_attrs=custom_attrs,
                    proxy_attrs=proxy_attrs,
                )

                controllers.append(asdict(controller_data))

            except Exception as e:
                self.logger.debug(f"Skipping curve {curve_shape}: {e}")
                continue

        return controllers

    def _extract_custom_attributes(self, node: str) -> Optional[Dict]:
        """
        v1.5.0: Extract user-defined custom attributes from a node

        Returns dict of {attr_name: {type, value, min, max, enum_names, keyable, channelBox}}
        """
        if cmds is None:
            return None

        custom_attrs = {}

        try:
            # Get user-defined attributes (not standard Maya attrs)
            user_attrs = cmds.listAttr(node, userDefined=True) or []

            for attr in user_attrs:
                try:
                    attr_path = f"{node}.{attr}"

                    # Get attribute type
                    attr_type = cmds.getAttr(attr_path, type=True)

                    # Get value
                    value = cmds.getAttr(attr_path)

                    attr_data = {
                        "type": attr_type,
                        "value": value,
                        "keyable": cmds.getAttr(attr_path, keyable=True),
                        "channelBox": cmds.getAttr(attr_path, channelBox=True),
                    }

                    # Get min/max for numeric types
                    if attr_type in ["double", "float", "long", "short"]:
                        if cmds.attributeQuery(attr, node=node, minExists=True):
                            attr_data["min"] = cmds.attributeQuery(attr, node=node, min=True)[0]
                        if cmds.attributeQuery(attr, node=node, maxExists=True):
                            attr_data["max"] = cmds.attributeQuery(attr, node=node, max=True)[0]

                    # Get enum names for enum type
                    if attr_type == "enum":
                        enum_str = cmds.attributeQuery(attr, node=node, listEnum=True)
                        if enum_str:
                            attr_data["enum_names"] = enum_str[0].split(":")

                    custom_attrs[attr] = attr_data

                except Exception as e:
                    self.logger.debug(f"Skipping custom attr {attr}: {e}")
                    continue

        except Exception as e:
            self.logger.debug(f"Failed to extract custom attrs from {node}: {e}")
            return None

        return custom_attrs if custom_attrs else None

    def _extract_proxy_attributes(self, node: str) -> Optional[Dict]:
        """
        v1.5.0: Extract proxy attribute connections

        Proxy attributes route connections from one control to another
        for organized channel box display.

        Returns dict of {attr_name: {source_node, source_attr}}
        """
        if cmds is None:
            return None

        proxy_attrs = {}

        try:
            # Get all attributes that are proxies (connected from another node)
            user_attrs = cmds.listAttr(node, userDefined=True) or []

            for attr in user_attrs:
                try:
                    attr_path = f"{node}.{attr}"

                    # Check if this attribute is a proxy (has incoming connection)
                    connections = (
                        cmds.listConnections(attr_path, source=True, destination=False, plugs=True)
                        or []
                    )

                    if connections:
                        source = connections[0]
                        source_node, source_attr = source.split(".")
                        proxy_attrs[attr] = {
                            "source_node": source_node,
                            "source_attr": source_attr,
                        }

                except Exception as e:
                    self.logger.debug(f"Skipping proxy check for {attr}: {e}")
                    continue

        except Exception as e:
            self.logger.debug(f"Failed to extract proxy attrs from {node}: {e}")
            return None

        return proxy_attrs if proxy_attrs else None

    def _extract_space_switches(self) -> List[Dict]:
        """
        v1.5.0: Extract space switch setups

        Space switches are typically:
        - An enum attribute on a control (e.g., "space" or "follow")
        - Connected to parent constraint weights via SDKs or direct connections
        """
        if cmds is None:
            return []

        space_switches = []

        # Find parent constraints (most space switches use these)
        parent_constraints = cmds.ls(type="parentConstraint") or []

        for pc in parent_constraints:
            try:
                # Get constraint targets
                targets = cmds.parentConstraint(pc, query=True, targetList=True) or []
                if len(targets) < 2:
                    continue  # Need at least 2 spaces for a switch

                # Get the driven object
                driven = (
                    cmds.listConnections(f"{pc}.constraintParentInverseMatrix", source=True) or []
                )
                if not driven:
                    continue
                driven = driven[0]

                # Look for enum attribute that drives the constraint
                # Check the driven object and its parents for space enum
                space_attr = self._find_space_attribute(driven, pc)

                if space_attr:
                    control, attr_name = space_attr.split(".")

                    # Get enum values
                    enum_str = cmds.attributeQuery(attr_name, node=control, listEnum=True)
                    space_names = enum_str[0].split(":") if enum_str else []

                    # Build space data
                    spaces = []
                    for i, target in enumerate(targets):
                        weight_attr = f"{pc}.{target}W{i}"
                        spaces.append(
                            {
                                "name": space_names[i] if i < len(space_names) else target,
                                "target": target,
                                "weight_attr": weight_attr,
                            }
                        )

                    space_switch = SpaceSwitchData(
                        name=f"{driven}_spaceSwitch",
                        control=control,
                        attribute=attr_name,
                        spaces=spaces,
                        constraint=pc,
                    )
                    space_switches.append(asdict(space_switch))

            except Exception as e:
                self.logger.debug(f"Skipping parent constraint {pc}: {e}")
                continue

        return space_switches

    def _find_space_attribute(self, node: str, constraint: str) -> Optional[str]:
        """Find the enum attribute that drives a space switch constraint"""
        if cmds is None:
            return None

        # Check the node and its parents for space-related enum attrs
        nodes_to_check = [node]

        # Add parent nodes
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        nodes_to_check.extend(parents)

        for check_node in nodes_to_check:
            user_attrs = cmds.listAttr(check_node, userDefined=True) or []

            for attr in user_attrs:
                try:
                    attr_path = f"{check_node}.{attr}"
                    attr_type = cmds.getAttr(attr_path, type=True)

                    if attr_type == "enum":
                        # Check if this enum connects to the constraint weights
                        connections = (
                            cmds.listConnections(attr_path, destination=True, plugs=True) or []
                        )

                        for conn in connections:
                            if constraint in conn:
                                return attr_path

                except Exception:
                    continue

        return None

    def _extract_curve_data(self, curve_shape: str) -> Dict:
        """Extract NURBS curve CV positions, degree, form"""
        if cmds is None:
            return {}

        try:
            # Get curve info
            degree = cmds.getAttr(f"{curve_shape}.degree")
            form = cmds.getAttr(f"{curve_shape}.form")  # 0=open, 1=closed, 2=periodic
            spans = cmds.getAttr(f"{curve_shape}.spans")

            # Get CV positions
            num_cvs = degree + spans
            cvs = []
            for i in range(num_cvs):
                pos = cmds.xform(
                    f"{curve_shape}.cv[{i}]", query=True, translation=True, worldSpace=False
                )
                cvs.append(pos)

            return {"degree": degree, "form": form, "cvs": cvs}

        except Exception as e:
            self.logger.debug(f"Failed to extract curve data: {e}")
            return {}

    def _extract_constraints(self) -> List[Dict]:
        """Extract all constraint data"""
        constraints = []

        # Get all constraint types
        constraint_types = [
            "parentConstraint",
            "orientConstraint",
            "pointConstraint",
            "aimConstraint",
            "scaleConstraint",
            "poleVectorConstraint",
        ]

        for constraint_type in constraint_types:
            constraint_nodes = cmds.ls(type=constraint_type) or []

            for constraint in constraint_nodes:
                try:
                    constraint_data = self._extract_constraint_data(constraint, constraint_type)
                    if constraint_data:
                        constraints.append(asdict(constraint_data))

                except Exception as e:
                    self.logger.debug(f"Skipping constraint {constraint}: {e}")
                    continue

        return constraints

    def _extract_constraint_data(
        self, constraint: str, constraint_type: str
    ) -> Optional[ConstraintData]:
        """Extract data from a single constraint"""
        try:
            # Get driven object (the constrained object)
            driven_list = cmds.listConnections(
                f"{constraint}.constraintParentInverseMatrix", source=True
            )
            if not driven_list:
                return None
            driven = driven_list[0]

            # Get drivers (target objects)
            drivers = []
            weights = []

            # Query targets using constraint command
            if constraint_type == "parentConstraint":
                drivers = cmds.parentConstraint(constraint, query=True, targetList=True) or []
                weights = cmds.parentConstraint(constraint, query=True, weightAliasList=True) or []
                weights = [cmds.getAttr(f"{constraint}.{w}") for w in weights] if weights else []
            elif constraint_type == "orientConstraint":
                drivers = cmds.orientConstraint(constraint, query=True, targetList=True) or []
                weights = cmds.orientConstraint(constraint, query=True, weightAliasList=True) or []
                weights = [cmds.getAttr(f"{constraint}.{w}") for w in weights] if weights else []
            elif constraint_type == "pointConstraint":
                drivers = cmds.pointConstraint(constraint, query=True, targetList=True) or []
                weights = cmds.pointConstraint(constraint, query=True, weightAliasList=True) or []
                weights = [cmds.getAttr(f"{constraint}.{w}") for w in weights] if weights else []
            elif constraint_type == "aimConstraint":
                drivers = cmds.aimConstraint(constraint, query=True, targetList=True) or []
                weights = cmds.aimConstraint(constraint, query=True, weightAliasList=True) or []
                weights = [cmds.getAttr(f"{constraint}.{w}") for w in weights] if weights else []
            elif constraint_type == "scaleConstraint":
                drivers = cmds.scaleConstraint(constraint, query=True, targetList=True) or []
                weights = cmds.scaleConstraint(constraint, query=True, weightAliasList=True) or []
                weights = [cmds.getAttr(f"{constraint}.{w}") for w in weights] if weights else []
            elif constraint_type == "poleVectorConstraint":
                drivers = cmds.poleVectorConstraint(constraint, query=True, targetList=True) or []
                weights = [1.0]  # Pole vector constraints don't have weights

            if not drivers:
                return None

            # Get maintain offset
            maintain_offset = True
            if constraint_type != "poleVectorConstraint":
                offset_attrs = cmds.listAttr(constraint, string="*Offset*") or []
                if offset_attrs:
                    # Check if any offset attribute is non-zero
                    maintain_offset = any(
                        abs(cmds.getAttr(f"{constraint}.{attr}")) > 0.001
                        for attr in offset_attrs
                        if cmds.attributeQuery(attr, node=constraint, attributeType=True)
                        in ["double", "float"]
                    )

            # Get skip translate/rotate
            skip_translate = []
            skip_rotate = []
            if constraint_type in ["parentConstraint", "pointConstraint"]:
                for axis in ["x", "y", "z"]:
                    attr = f"skip{axis.upper()}"
                    if cmds.attributeQuery(attr, node=constraint, exists=True):
                        if cmds.getAttr(f"{constraint}.{attr}"):
                            skip_translate.append(axis)

            if constraint_type in ["parentConstraint", "orientConstraint"]:
                for axis in ["x", "y", "z"]:
                    attr = f"skip{axis.upper()}"
                    if cmds.attributeQuery(attr, node=constraint, exists=True):
                        if cmds.getAttr(f"{constraint}.{attr}"):
                            skip_rotate.append(axis)

            return ConstraintData(
                name=constraint.split("|")[-1],
                type=constraint_type,
                driven=driven.split("|")[-1],
                drivers=[d.split("|")[-1] for d in drivers],
                maintain_offset=maintain_offset,
                weights=weights,
                skip_translate=skip_translate,
                skip_rotate=skip_rotate,
            )

        except Exception as e:
            self.logger.debug(f"Failed to extract constraint {constraint}: {e}")
            return None

    def _extract_ik_handles(self) -> List[Dict]:
        """Extract IK handle data"""
        ik_handles = []

        ik_handle_nodes = cmds.ls(type="ikHandle") or []

        for ik in ik_handle_nodes:
            try:
                # Get start joint
                start_joint = cmds.ikHandle(ik, query=True, startJoint=True)
                # Get end effector
                end_effector = cmds.ikHandle(ik, query=True, endEffector=True)
                # Get end joint from effector
                end_joint = cmds.listConnections(
                    f"{end_effector}.translateX", source=True, destination=False
                )
                if end_joint:
                    end_joint = end_joint[0]

                # Get solver
                solver = cmds.ikHandle(ik, query=True, solver=True)

                # Get priority
                priority = cmds.ikHandle(ik, query=True, priority=True)

                # Get pole vector constraint if exists
                pole_vector = None
                pole_constraints = (
                    cmds.listConnections(
                        f"{ik}.poleVector",
                        source=True,
                        destination=False,
                        type="poleVectorConstraint",
                    )
                    or []
                )
                if pole_constraints:
                    pole_targets = (
                        cmds.poleVectorConstraint(pole_constraints[0], query=True, targetList=True)
                        or []
                    )
                    if pole_targets:
                        pole_vector = pole_targets[0]

                ik_data = IKHandleData(
                    name=ik.split("|")[-1],
                    start_joint=start_joint.split("|")[-1] if start_joint else "",
                    end_joint=end_joint.split("|")[-1] if end_joint else "",
                    solver=solver,
                    priority=priority,
                    pole_vector=pole_vector.split("|")[-1] if pole_vector else None,
                )

                ik_handles.append(asdict(ik_data))

            except Exception as e:
                self.logger.debug(f"Failed to extract IK handle {ik}: {e}")
                continue

        return ik_handles

    def _extract_blendshapes(self) -> Tuple[List[Dict], List[Dict]]:
        """Extract blendshape deformers and their connections"""
        blendshapes = []
        connections = []

        blendshape_nodes = cmds.ls(type="blendShape") or []

        for bs in blendshape_nodes:
            try:
                # Get base geometry
                base_geometry = cmds.blendShape(bs, query=True, geometry=True)
                if not base_geometry:
                    continue
                base_geometry = base_geometry[0]

                # Get all target aliases
                target_aliases = cmds.aliasAttr(bs, query=True) or []
                targets = []

                # Process targets (aliases come in pairs: alias, attribute)
                for i in range(0, len(target_aliases), 2):
                    target_name = target_aliases[i]
                    target_attr = target_aliases[i + 1]

                    try:
                        # Get weight
                        weight = cmds.getAttr(f"{bs}.{target_attr}")

                        # Get target index
                        target_idx = int(target_attr.split("[")[-1].rstrip("]"))

                        # Get target data (deltas) - deferred until full delta extraction is implemented
                        deltas = None  # _get_blendshape_deltas is a placeholder that always returns None

                        # Get in-between targets
                        inbetweens = self._get_blendshape_inbetweens(bs, target_idx)

                        # Check for connections
                        input_connections = (
                            cmds.listConnections(
                                f"{bs}.{target_attr}", source=True, destination=False, plugs=True
                            )
                            or []
                        )
                        for conn in input_connections:
                            # Parse connection: "source.attr" -> blendshape.target
                            driver = conn
                            connection_type = "direct"
                            sdk_keys = None

                            # Check if it's driven by an animCurve (SDK)
                            anim_curve = (
                                cmds.listConnections(conn, source=True, type="animCurve") or []
                            )
                            if anim_curve:
                                connection_type = "sdk"
                                sdk_keys = self._get_anim_curve_keys(anim_curve[0])

                            connection = BlendShapeConnectionData(
                                blendshape=bs.split("|")[-1],
                                target=target_name,
                                driver=driver,
                                connection_type=connection_type,
                                sdk_keys=sdk_keys,
                            )
                            connections.append(asdict(connection))

                        targets.append(
                            {
                                "name": target_name,
                                "weight": weight,
                                "index": target_idx,
                                "deltas": deltas,
                                "inbetweens": inbetweens,
                            }
                        )

                    except Exception as e:
                        self.logger.debug(f"Skipping blendshape target {target_name}: {e}")
                        continue

                bs_data = BlendShapeData(
                    name=bs.split("|")[-1],
                    base_geometry=base_geometry.split("|")[-1],
                    targets=targets,
                )

                blendshapes.append(asdict(bs_data))

            except Exception as e:
                self.logger.debug(f"Failed to extract blendshape {bs}: {e}")
                continue

        return blendshapes, connections

    def _get_blendshape_deltas(
        self, blendshape: str, target_idx: int, base_geometry: str
    ) -> Optional[List]:
        """Get vertex deltas for a blendshape target (simplified - could be stored)"""
        try:
            # For performance, we might skip storing deltas and rely on Maya recreating them
            # from the target geometry. For now, return None to indicate we don't store deltas.
            # Full implementation would query:
            # cmds.getAttr(
            #     f"{blendshape}.inputTarget[0].inputTargetGroup[{target_idx}].targetDeltas"
            # )
            return None

        except Exception as e:
            self.logger.debug(f"Could not get blendshape deltas: {e}")
            return None

    def _get_blendshape_inbetweens(self, blendshape: str, target_idx: int) -> List[Dict]:
        """Get in-between targets for a blendshape target"""
        inbetweens = []

        try:
            # Query in-between weights for this target
            # inputTargetGroup[target_idx].targetItem[*].inputTargetWeights
            target_items = (
                cmds.ls(
                    f"{blendshape}.inputTarget[0].inputTargetGroup[{target_idx}].targetItem[*]",
                    flatten=True,
                )
                or []
            )

            for item in target_items:
                # Extract weight from attribute path
                weight_match = item.split("targetItem[")[-1].split("]")[0]
                if weight_match.isdigit():
                    weight_idx = int(weight_match)
                    # In-between weights are typically at indices like 5000, 6000 (representing 0.5, 0.6, etc.)
                    if weight_idx != 6000:  # 6000 is the main target (weight 1.0)
                        weight_value = weight_idx / 6000.0
                        inbetweens.append({"weight": weight_value, "index": weight_idx})

        except Exception as e:
            self.logger.debug(f"Could not get in-betweens: {e}")

        return inbetweens

    def _extract_set_driven_keys(self) -> List[Dict]:
        """Extract Set Driven Key relationships"""
        sdks = []

        # Find all animCurve nodes (SDKs are stored as animCurves)
        anim_curves = cmds.ls(type="animCurve") or []

        for anim_curve in anim_curves:
            try:
                # Get the driven attribute
                driven_connections = (
                    cmds.listConnections(anim_curve, source=False, destination=True, plugs=True)
                    or []
                )
                if not driven_connections:
                    continue
                driven = driven_connections[0]

                # Get the driver attribute
                driver_connections = (
                    cmds.listConnections(
                        f"{anim_curve}.input", source=True, destination=False, plugs=True
                    )
                    or []
                )
                if not driver_connections:
                    continue
                driver = driver_connections[0]

                # Get keyframe data
                keys = self._get_anim_curve_keys(anim_curve)
                if not keys:
                    continue

                sdk_data = SetDrivenKeyData(driver=driver, driven=driven, keys=keys)

                sdks.append(asdict(sdk_data))

            except Exception as e:
                self.logger.debug(f"Skipping animCurve {anim_curve}: {e}")
                continue

        return sdks

    def _get_anim_curve_keys(self, anim_curve: str) -> List[List[float]]:
        """Get keyframe pairs from an animation curve"""
        keys = []

        try:
            num_keys = cmds.keyframe(anim_curve, query=True, keyframeCount=True) or 0

            for i in range(num_keys):
                # Get input (time/driver value)
                input_val = cmds.keyframe(anim_curve, query=True, index=(i,), floatChange=True)[0]
                # Get output (driven value)
                output_val = cmds.keyframe(anim_curve, query=True, index=(i,), valueChange=True)[0]

                keys.append([input_val, output_val])

        except Exception as e:
            self.logger.debug(f"Could not get anim curve keys: {e}")

        return keys
