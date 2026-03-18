"""
Export-side mixin for UsdPipeline: export(), deformation joints, mayausd export.

Auto-generated mixin — do not edit directly; edit usd_pipeline.py then re-split.
"""
from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Callable, List, Optional

# ── Optional Maya imports (same guards as original) ──────────────────────────
try:
    import maya.cmds as cmds          # type: ignore[import-unresolved]
    import maya.mel as mel            # type: ignore[import-unresolved]
    MAYA_AVAILABLE = True
except ImportError:
    cmds = None   # type: ignore[assignment]
    mel = None    # type: ignore[assignment]
    MAYA_AVAILABLE = False

# ── Optional USD imports ──────────────────────────────────────────────────────
try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

from .usd_pipeline_models import (
    ExportOptions,
    ExportResult,
)


class ExportMixin:
    # ── Attribute stubs (provided by UsdPipeline.__init__) ────────────
    logger: logging.Logger
    _maya_available: bool
    _usd_available: bool
    _mayausd_available: bool
    _progress_callback: Optional[Callable[[str, int], None]]

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
                    # Note: .atlasStyle errors from PxrTexture/PxrNormalMap nodes
                    # (RfM 27 deprecation) are harmless noise — Maya's .ma file
                    # parser emits them through an internal channel that cannot
                    # be suppressed without risking a crash. They do not affect
                    # the export output in any way.
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
            self.logger.error(traceback.format_exc())
            return False

    def _extract_geometry_layer(self, source_stage, output_path: Path) -> bool:
        """Extract geometry prims to a separate layer"""
        try:
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

                # Update skeleton binding paths: translate /OldRoot/... → /SkelRoot/OldRoot/...
                # Use the same prefix-translation pattern as animationSource (Step 4) so that
                # each mesh keeps its OWN skeleton binding — we must NOT overwrite all bindings
                # to a single skeleton path (that was the bug: it forced everything to FitSkeleton).
                # Bindings may live on Mesh prims OR on parent Xform/Scope prims (inherited), so
                # we scan every prim.
                binding_count = 0
                for prim in stage.Traverse():
                    binding = UsdSkel.BindingAPI(prim)
                    skel_rel = binding.GetSkeletonRel()
                    if not (skel_rel and skel_rel.HasAuthoredTargets()):
                        continue
                    old_targets = skel_rel.GetTargets()
                    new_targets = []
                    updated = False
                    for old_t in old_targets:
                        old_str = str(old_t)
                        if old_str.startswith("/") and not old_str.startswith("/SkelRoot"):
                            new_targets.append(Sdf.Path("/SkelRoot" + old_str))
                            updated = True
                        else:
                            new_targets.append(old_t)
                    if updated:
                        skel_rel.SetTargets(new_targets)
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
            self.logger.debug(traceback.format_exc())
            return True  # Non-fatal - continue anyway
