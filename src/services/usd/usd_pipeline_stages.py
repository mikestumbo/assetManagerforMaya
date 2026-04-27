"""
USD-stage manipulation mixin: merge skeleton prims, animation layers, blendshapes.

Auto-generated mixin — do not edit directly; edit usd_pipeline.py then re-split.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

# ── Optional Maya imports (same guards as original) ──────────────────────────
try:
    import maya.cmds as cmds  # type: ignore[import-unresolved]
    import maya.mel as mel  # type: ignore[import-unresolved]

    MAYA_AVAILABLE = True
except ImportError:
    cmds = None  # type: ignore[assignment]
    mel = None  # type: ignore[assignment]
    MAYA_AVAILABLE = False

# ── Optional USD imports ──────────────────────────────────────────────────────
try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt  # type: ignore

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

from .usd_pipeline_models import (
    ConversionResult,
    ConversionStatus,
    ExportOptions,
    ExportResult,
    ImportOptions,
    ImportResult,
    MAYA_AVAILABLE as _MAYA_AVAILABLE_MODEL,
    USD_AVAILABLE as _USD_AVAILABLE_MODEL,
)


class StagesMixin:
    # ── Attribute stubs (provided by UsdPipeline.__init__) ────────────
    logger: logging.Logger
    _maya_available: bool
    _usd_available: bool
    _mayausd_available: bool
    _progress_callback: Optional[Callable[[str, int], None]]

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

            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("Could not open USD stage for skeleton merge")
                return False

            # Find all existing Skeleton prims
            all_skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]

            if len(all_skeletons) <= 1:
                self.logger.info("[OK] Single or no skeleton - merge not needed")
                return True

            self.logger.info(
                f"[SKEL] Merging {len(all_skeletons)} Skeleton prims into unified skeleton..."
            )

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
                    joint_name = str(joint).split("/")[-1] if "/" in str(joint) else str(joint)

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
                    rotations.append(
                        Gf.Quatf(
                            quat.GetReal(),
                            quat.GetImaginary()[0],
                            quat.GetImaginary()[1],
                            quat.GetImaginary()[2],
                        )
                    )

                    # Default scale
                    scales.append(Gf.Vec3h(1.0, 1.0, 1.0))

                unified_anim.GetTranslationsAttr().Set(Vt.Vec3fArray(translations))
                unified_anim.GetRotationsAttr().Set(Vt.QuatfArray(rotations))
                unified_anim.GetScalesAttr().Set(Vt.Vec3hArray(scales))

            self.logger.info(f"   [OK] Created unified animation: {unified_anim_path}")

            # Update all skin bindings to reference unified skeleton
            binding_count = 0
            for prim in stage.Traverse():
                if prim.GetTypeName() == "Mesh":
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

            self.logger.error(traceback.format_exc())
            return False

    def _create_animation_layers(
        self, base_usd_path: Path, options: ExportOptions, result: ExportResult
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
                "Skeleton",
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

                self.logger.info(
                    f"   [SKEL] Using skeleton with most joints: {deform_skeleton_path}"
                )
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
                            self.logger.info(
                                f"   [ANIMATION] Found deformation animation: {anim_path_str}"
                            )
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
                            self.logger.info(
                                f"   [ANIMATION] Found matching animation: {prim.GetPath()}"
                            )
                            break

            # ================================================================
            # Step 3: Update all skin bindings to point to deformation skeleton
            # ================================================================
            binding_updates = 0

            for prim in stage.Traverse():
                if prim.GetTypeName() == "Mesh":
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

            self.logger.info(
                f"   [DELETE]  Deleted {deleted_count} unused skeleton/animation prims"
            )

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
                self.logger.info(
                    f"[SUCCESS] Added geomBindTransform to {fixed_count} skinned meshes"
                )
            else:
                self.logger.info("[SUCCESS] All skinned meshes already have geomBindTransform")

            return True

        except Exception as e:
            self.logger.warning(f"[WARNING] geomBindTransform fix failed (non-fatal): {e}")

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
            blendshape_nodes = cmds.ls(type="blendShape") or []
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
                    if cmds.nodeType(base_mesh) != "mesh":
                        self.logger.debug(
                            f"   Skipping non-mesh geometry: {base_mesh} ({cmds.nodeType(base_mesh)})"
                        )
                        continue

                    # Find corresponding USD mesh
                    # Strip namespace and 'Shape' suffix from Maya name
                    mesh_short_name = base_mesh.split("|")[-1]  # Remove path
                    mesh_short_name = mesh_short_name.split(":")[-1]  # Remove namespace
                    if mesh_short_name.endswith("Shape"):
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
                    elif mesh_short_name.endswith("_Geo") and mesh_short_name[:-4] in usd_mesh_map:
                        usd_mesh = usd_mesh_map[mesh_short_name[:-4]]

                    # Strategy 4: Try transform parent name
                    if not usd_mesh:
                        parent_transform = cmds.listRelatives(base_mesh, parent=True)
                        if parent_transform:
                            transform_short_name = (
                                parent_transform[0].split("|")[-1].split(":")[-1]
                            )
                            if transform_short_name in usd_mesh_map:
                                usd_mesh = usd_mesh_map[transform_short_name]

                    # Strategy 5: Partial match (contains)
                    if not usd_mesh:
                        for usd_name, usd_prim in usd_mesh_map.items():
                            if mesh_short_name in usd_name or usd_name in mesh_short_name:
                                usd_mesh = usd_prim
                                break

                    if not usd_mesh:
                        self.logger.warning(
                            f"   Could not find USD mesh for {base_mesh} (searched: {mesh_short_name})"
                        )
                        continue

                    # Get blendShape targets (aliases)
                    alias_list = cmds.aliasAttr(bs_node, query=True) or []
                    # aliasAttr returns pairs: [alias1, attr1, alias2, attr2, ...]
                    target_aliases = {}
                    for i in range(0, len(alias_list), 2):
                        alias_name = alias_list[i]
                        weight_attr = alias_list[i + 1]
                        # Extract index from weight attribute (e.g., "weight[0]" -> 0)
                        if "weight[" in weight_attr:
                            target_idx = int(weight_attr.split("[")[1].split("]")[0])
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
                            sanitized_name = target_name.replace(".", "_").replace(":", "_")
                            blend_shape_path = blend_shapes_path.AppendChild(sanitized_name)
                            blend_shape_prim = UsdSkel.BlendShape.Define(stage, blend_shape_path)

                            # Write offsets as Vec3fArray
                            offsets_vt = Vt.Vec3fArray(
                                [
                                    Gf.Vec3f(offsets[i], offsets[i + 1], offsets[i + 2])
                                    for i in range(0, len(offsets), 3)
                                ]
                            )

                            blend_shape_prim.CreateOffsetsAttr(offsets_vt)

                            # TODO: Export normal offsets if needed (optional)
                            # blend_shape_prim.CreateNormalOffsetsAttr(normal_offsets_vt)

                            # Link blendShape to mesh via skel:blendShapes relationship
                            # Use core relationship API (compatible with all USD versions)
                            blend_shapes_rel = usd_mesh.GetPrim().CreateRelationship(
                                "skel:blendShapes"
                            )
                            blend_shapes_rel.AddTarget(blend_shape_path)

                            total_targets += 1
                            self.logger.info(f"      [SUCCESS] Exported: {target_name}")

                        except Exception as target_error:
                            error_msg = f"      [WARNING] Failed to export target {target_name}: {target_error}"
                            self.logger.warning(error_msg)
                            continue

                except Exception as bs_error:
                    self.logger.warning(
                        f"   [WARNING] Failed blendShape node {bs_node}: {bs_error}"
                    )
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

            self.logger.debug(traceback.format_exc())
            return 0

    def _validate_usd_export(
        self,
        usd_path: Path,
        options: ExportOptions,
        result: ExportResult,
        num_skin_clusters: int = 0,
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
        self.logger.info(
            f"[INFO] USD_AVAILABLE: {USD_AVAILABLE}, file exists: {usd_path.exists()}"
        )

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
                meshes = [p for p in stage.Traverse() if p.GetTypeName() == "Mesh"]
                result.conversions["Geometry"] = ConversionResult(
                    component_type="Geometry",
                    status=ConversionStatus.SUCCESS if meshes else ConversionStatus.FAILED,
                    usd_count=len(meshes),
                    message=f"{len(meshes)} meshes exported",
                )
                self.logger.info(f"[INFO] Found {len(meshes)} meshes in USD")

            # Count NURBS curves - check for NurbsCurves or BasisCurves types
            if options.export_nurbs_curves:
                curves = [
                    p
                    for p in stage.Traverse()
                    if p.GetTypeName() in ("NurbsCurves", "BasisCurves")
                ]
                result.conversions["NURBS Curves"] = ConversionResult(
                    component_type="NURBS Curves",
                    status=ConversionStatus.SUCCESS if curves else ConversionStatus.FALLBACK,
                    usd_count=len(curves),
                    fallback_count=0 if curves else 1,  # Will use .rig.mb
                    message=f"{len(curves)} curves exported",
                )
                self.logger.info(f"[INFO] Found {len(curves)} NURBS curves in USD")

            # Count skeleton joints - check for Skeleton type
            if options.export_skeleton:
                skeletons = [p for p in stage.Traverse() if p.GetTypeName() == "Skeleton"]
                joint_count = 0
                for skel_prim in skeletons:
                    skel = UsdSkel.Skeleton(skel_prim)
                    joints = skel.GetJointsAttr().Get()
                    if joints:
                        joint_count += len(joints)

                result.conversions["Skeleton"] = ConversionResult(
                    component_type="Skeleton",
                    status=(
                        ConversionStatus.SUCCESS if joint_count > 0 else ConversionStatus.FALLBACK
                    ),
                    usd_count=joint_count,
                    message=f"{joint_count} joints in {len(skeletons)} skeleton(s)",
                )
                self.logger.info(
                    f"[INFO] Found {joint_count} joints in {len(skeletons)} skeleton(s)"
                )

                # Log SkelRoot scope (critical for deformation)
                skel_roots = [p for p in stage.Traverse() if p.GetTypeName() == "SkelRoot"]
                for sr in skel_roots:
                    self.logger.info(f"[INFO] SkelRoot: {sr.GetPath()}")
                    # List children under SkelRoot to show scope
                    children = [c.GetName() for c in sr.GetChildren()]
                    if children:
                        self.logger.info(
                            f"   Children: {children[:5]}{'...' if len(children) > 5 else ''}"
                        )

                # Count skin bindings - meshes with UsdSkelBindingAPI
                skin_binding_count = 0
                for prim in stage.Traverse():
                    if prim.GetTypeName() == "Mesh":
                        binding = UsdSkel.BindingAPI(prim)
                        if binding:
                            # Check if mesh has actual skin weight primvars
                            indices_attr = prim.GetAttribute("primvars:skel:jointIndices")
                            weights_attr = prim.GetAttribute("primvars:skel:jointWeights")
                            if (
                                indices_attr
                                and indices_attr.HasValue()
                                and weights_attr
                                and weights_attr.HasValue()
                            ):
                                skin_binding_count += 1

                # Determine skin status based on viewport_friendly option
                if options.viewport_friendly_skeleton:
                    # Viewport-friendly: skin preserved in .rig.mb fallback
                    result.conversions["Skin"] = ConversionResult(
                        component_type="Skin",
                        status=(
                            ConversionStatus.FALLBACK
                            if skin_binding_count == 0
                            else ConversionStatus.SUCCESS
                        ),
                        usd_count=skin_binding_count,
                        fallback_count=num_skin_clusters if skin_binding_count == 0 else 0,
                        message=f"Viewport-friendly: {num_skin_clusters} skinClusters in .rig.mb",
                    )
                else:
                    # Full export: skin bindings in USD
                    result.conversions["Skin"] = ConversionResult(
                        component_type="Skin",
                        status=(
                            ConversionStatus.SUCCESS
                            if skin_binding_count > 0
                            else ConversionStatus.FALLBACK
                        ),
                        usd_count=skin_binding_count,
                        fallback_count=0,
                        message=f"{skin_binding_count} skin bindings exported",
                    )
                self.logger.info(f"[INFO] Found {skin_binding_count} skin bindings in USD")

            # Count materials - check for Material type
            if options.export_materials:
                materials = [p for p in stage.Traverse() if p.GetTypeName() == "Material"]
                result.conversions["Materials"] = ConversionResult(
                    component_type="Materials",
                    status=ConversionStatus.SUCCESS if materials else ConversionStatus.FALLBACK,
                    usd_count=len(materials),
                    message=f"{len(materials)} materials exported",
                )
                self.logger.info(f"[INFO] Found {len(materials)} materials in USD")

            # Count blendshapes (Maya 2026) - check for BlendShape type
            if options.export_blendshapes:
                blendshapes = [p for p in stage.Traverse() if p.GetTypeName() == "BlendShape"]
                result.conversions["Blendshapes"] = ConversionResult(
                    component_type="Blendshapes",
                    status=ConversionStatus.SUCCESS if blendshapes else ConversionStatus.FALLBACK,
                    usd_count=len(blendshapes),
                    message=f"{len(blendshapes)} blendshapes exported",
                )
                self.logger.info(f"[INFO] Found {len(blendshapes)} blendshapes in USD")

            # Count animation - SkelAnimation prims (USD's native skeletal animation)
            # Note: USD uses SkelAnimation for rigging, while Alembic (.abc) is often
            # used for baked deformation caches. mayaUSD exports to SkelAnimation.
            # SkelAnimation prims exist even without explicit animation (rest pose)
            skel_animations = [p for p in stage.Traverse() if p.GetTypeName() == "SkelAnimation"]

            # Get frame range from stage
            frame_range = (0, 0)
            has_time_samples = False
            start_time = stage.GetStartTimeCode()
            end_time = stage.GetEndTimeCode()
            if start_time != float("inf") and end_time != float("-inf"):
                frame_range = (int(start_time), int(end_time))
                has_time_samples = (frame_range[1] - frame_range[0]) > 0

            if options.export_animation and has_time_samples:
                # Actual animation was exported
                result.conversions["Animation"] = ConversionResult(
                    component_type="Animation",
                    status=ConversionStatus.SUCCESS,
                    usd_count=len(skel_animations),
                    message=f"{len(skel_animations)} SkelAnimation(s), "
                    f"frames {frame_range[0]}-{frame_range[1]}",
                )
                self.logger.info(
                    f"[INFO] Found {len(skel_animations)} SkelAnimation prims "
                    f"(frames {frame_range[0]}-{frame_range[1]})"
                )
            elif skel_animations:
                # Rest pose only (no animation checkbox or no time samples)
                result.conversions["Animation"] = ConversionResult(
                    component_type="Animation",
                    status=ConversionStatus.PARTIAL,
                    usd_count=len(skel_animations),
                    message=f"{len(skel_animations)} SkelAnimation(s) (rest pose only)",
                )
                self.logger.info(
                    f"[INFO] Found {len(skel_animations)} SkelAnimation prims (rest pose only)"
                )
            else:
                # No animation data at all
                result.conversions["Animation"] = ConversionResult(
                    component_type="Animation",
                    status=ConversionStatus.SKIPPED,
                    usd_count=0,
                    message="No animation exported",
                )
                self.logger.info("[INFO] No SkelAnimation prims in USD")

            # Log all prim types found for debugging
            all_types = set(p.GetTypeName() for p in stage.Traverse() if p.GetTypeName())
            self.logger.info(f"[INFO] All prim types in USD: {all_types}")

            self.logger.info("[INFO] USD validation complete")

        except Exception as e:
            self.logger.warning(f"USD validation error: {e}")

            self.logger.warning(f"USD validation traceback: {traceback.format_exc()}")
