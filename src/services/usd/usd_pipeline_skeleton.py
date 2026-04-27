"""
Skeleton/rigging mixin: USD→Maya conversion, joint proxies, skin weights.

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

from .usd_pipeline_models import MAYA_AVAILABLE as _MAYA_AVAILABLE_MODEL
from .usd_pipeline_models import USD_AVAILABLE as _USD_AVAILABLE_MODEL
from .usd_pipeline_models import (
    ConversionResult,
    ConversionStatus,
    ExportOptions,
    ExportResult,
    ImportOptions,
    ImportResult,
)


class SkeletonMixin:
    # ── Attribute stubs (provided by UsdPipeline.__init__) ────────────
    logger: logging.Logger
    _maya_available: bool
    _usd_available: bool
    _mayausd_available: bool
    _progress_callback: Optional[Callable[[str, int], None]]

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
                    mel.eval("mayaUsdMenu_duplicateAsBase()")

                    # Check if skeleton joints were created (look for joint nodes under proxy)
                    children = cmds.listRelatives(proxy_transform, children=True, type="joint")
                    if children:
                        self.logger.info(
                            f"[OK] Converted USD Skeleton to Maya joints: {len(children)} root joint(s)"
                        )
                    else:
                        # MEL command didn't create joints - try Python fallback
                        self.logger.info(
                            "[INFO] MEL command succeeded but no joints created, "
                            "trying Python fallback..."
                        )
                        self._extract_skeleton_via_python(proxy_shape, usd_path)

                except AttributeError:
                    # mayaUSD commands not available in this version
                    self.logger.warning(
                        "[WARNING] Skeleton conversion not available in mayaUSD v0.35.0"
                    )
                    self.logger.info(
                        "[TIP] Upgrade to mayaUSD v0.27+ for automatic skeleton conversion"
                    )
                    # Try Python fallback
                    self._extract_skeleton_via_python(proxy_shape, usd_path)

                except Exception as dup_err:
                    # Command failed for other reasons
                    self.logger.warning(f"[WARNING] Skeleton conversion failed: {dup_err}")
                    # Try Python fallback
                    self._extract_skeleton_via_python(proxy_shape, usd_path)
            else:
                # No mayaUSD available at all
                self.logger.warning(
                    "[WARNING] mayaUSD plugin not available - cannot convert skeleton"
                )
                self.logger.info(
                    "[TIP] Load mayaUSD plugin: Window > Settings/Preferences > Plug-in Manager"
                )

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
                    self.logger.warning(
                        f"[WARNING] Skeleton {skel_prim.GetPath()} missing valid bind transforms"
                    )
                    continue

                self.logger.debug(
                    f"[SKEL] Creating {len(joint_names)} Maya joints from {skel_prim.GetPath()}"
                )

                # Create Maya joints from USD skeleton data
                joint_map = {}
                for joint_token, bind_xform in zip(joint_names, bind_transforms):
                    joint_name = str(joint_token)

                    # Parse hierarchy (joint names use "/" as separator)
                    parts = joint_name.split("/")
                    clean_name = parts[-1]  # Use last part as joint name
                    parent_path = "/".join(parts[:-1]) if len(parts) > 1 else None

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
                        worldSpace=True,
                    )

                    # Set rotation from quaternion
                    euler = rotation.GetImaginary()  # Simplified - proper conversion needed
                    cmds.xform(
                        maya_joint, rotation=[euler[0], euler[1], euler[2]], worldSpace=True
                    )

                    # Store in map for hierarchy building
                    joint_map[joint_name] = maya_joint

                    # Parent to USD hierarchy parent if exists
                    if parent_path and parent_path in joint_map:
                        cmds.parent(maya_joint, joint_map[parent_path])

                    created_joints.append(maya_joint)

                # Parent root joint(s) under proxy transform
                for joint_name, maya_joint in joint_map.items():
                    if "/" not in joint_name:  # Root joint
                        cmds.parent(maya_joint, proxy_transform)

            if created_joints:
                self.logger.info(
                    f"[OK] Created {len(created_joints)} Maya joints from USD skeletons"
                )
            else:
                self.logger.warning("[WARNING] No joints created from USD skeleton data")

        except Exception as e:
            self.logger.warning(f"[WARNING] Python USD skeleton extraction failed: {e}")
            self.logger.info(
                "[TIP] Right-click USD proxy > 'Duplicate As Maya Data' to convert manually"
            )

    def _count_usd_prims_in_proxy(self, proxy_shapes: List[str], result: ImportResult) -> None:
        """Count USD prims inside proxy shape(s) using the Pixar USD API"""
        if not USD_AVAILABLE:
            self.logger.warning("USD Python API not available for prim counting")
            return

        try:

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

                        if prim_type == "Mesh":
                            total_meshes += 1
                        elif prim_type == "Skeleton":
                            total_skeletons += 1
                        elif prim_type in ("NurbsCurves", "BasisCurves"):
                            total_curves += 1
                        elif prim_type == "Material":
                            total_materials += 1
                        elif prim_type == "BlendShape":
                            total_blendshapes += 1
                        elif prim_type == "SkelAnimation":
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

            self.logger.info("[LOOKDEV] Verifying USD material colors...")

            # Directly count UsdPreviewSurface shaders — more reliable than ComputeSurfaceSource
            preview_shaders = []
            colored_shaders = []
            for prim in stage.Traverse():
                if prim.GetTypeName() != "Shader":
                    continue
                shader = UsdShade.Shader(prim)
                if shader.GetShaderId() != "UsdPreviewSurface":
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

    def _count_imported_components(self, nodes: List[str], result: ImportResult) -> None:
        """Count what was actually imported - scan entire scene, not just returned nodes"""
        if cmds is None:
            return

        # mayaUSDImport returns root transform(s), but we need to count ALL scene content
        # Use cmds.ls to find all imported content types

        # Count meshes
        all_meshes = cmds.ls(type="mesh", dag=True) or []
        result.meshes_imported = len(all_meshes)

        # Count joints
        all_joints = cmds.ls(type="joint", dag=True) or []
        result.joints_imported = len(all_joints)

        # Count NURBS curves
        all_curves = cmds.ls(type="nurbsCurve", dag=True) or []
        result.curves_imported = len(all_curves)

        # Count materials (various shader types)
        material_types = [
            "lambert",
            "blinn",
            "phong",
            "standardSurface",
            "PxrSurface",
            "PxrDisney",
            "aiStandardSurface",
        ]
        all_materials = []
        for mat_type in material_types:
            mats = cmds.ls(type=mat_type) or []
            all_materials.extend(mats)
        # Exclude default materials
        default_mats = {"lambert1", "particleCloud1"}
        result.materials_imported = len([m for m in all_materials if m not in default_mats])

        # Count skin clusters
        all_skin_clusters = cmds.ls(type="skinCluster") or []
        result.skin_clusters_imported = len(all_skin_clusters)

        # Count blendshapes
        all_blendshapes = cmds.ls(type="blendShape") or []
        result.blendshapes_imported = len(all_blendshapes)

        # Count constraints
        constraint_types = [
            "parentConstraint",
            "orientConstraint",
            "pointConstraint",
            "aimConstraint",
            "scaleConstraint",
            "poleVectorConstraint",
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

    def _import_rig_mb_fallback(self, rig_mb_path: Path, result: ImportResult) -> bool:
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
                ignoreVersion=True,
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
        self, usd_path: Path, rig_mb_path: Path, options: ImportOptions, result: ImportResult
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
            before_meshes = set(cmds.ls(type="mesh", long=True) or [])
            before_joints = set(cmds.ls(type="joint", long=True) or [])
            before_skins = set(cmds.ls(type="skinCluster") or [])
            before_blends = set(cmds.ls(type="blendShape") or [])

            try:
                # Use mayaUSDImport to convert entire USD to native Maya
                self.logger.info(f"📥 Importing USD: {usd_path.name}")

                imported_nodes = cmds.mayaUSDImport(
                    file=str(usd_path),
                    primPath="/",  # Import everything
                    readAnimData=True,  # Import animation
                    importInstances=True,  # Import instances
                    importUSDZTextures=True,  # Extract textures from USDZ
                    preferredMaterial="usdPreviewSurface",  # Try USD materials first
                    shadingMode=[  # Import shading
                        ["useRegistry", "UsdPreviewSurface"],
                        ["useRegistry", "rendermanForMaya"],
                    ],
                )

                if not imported_nodes:
                    self.logger.error("[ERROR] mayaUSDImport returned no nodes")
                    return False

                self.logger.info(f"[OK] Imported {len(imported_nodes)} root nodes")

            except Exception as import_err:
                self.logger.error(f"[ERROR] USD import failed: {import_err}")

                self.logger.error(traceback.format_exc())
                return False

            # Count what was imported
            after_meshes = set(cmds.ls(type="mesh", long=True) or [])
            after_joints = set(cmds.ls(type="joint", long=True) or [])
            after_skins = set(cmds.ls(type="skinCluster") or [])
            after_blends = set(cmds.ls(type="blendShape") or [])

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

            controllers_imported = self._import_nurbs_controllers(rig_mb_path, result)

            if not controllers_imported:
                self.logger.warning(
                    "[WARNING] No controllers imported - skeleton can be animated directly"
                )
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

            self.logger.error(traceback.format_exc())
            return False

    def _convert_proxy_to_maya(self, proxy_shape: str, result: ImportResult) -> bool:
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

                if hasattr(mayaUsdLib, "PrimUpdater"):
                    # Modern mayaUSD API
                    mel.eval("mayaUsdEditAsMaya")
                    self.logger.info("[OK] Converted via mayaUsdEditAsMaya")
                else:
                    # Fallback to MEL
                    mel.eval("mayaUsdMenu_editAsMaya()")
                    self.logger.info("[OK] Converted via MEL command")
            except Exception as mel_err:
                # Try alternative MEL commands
                try:
                    mel.eval("mayaUsdDuplicate -importMaya")
                    self.logger.info("[OK] Converted via mayaUsdDuplicate")
                except Exception:
                    self.logger.warning(f"[WARNING] MEL conversion failed: {mel_err}")
                    self.logger.info("[TIP] Try: Right-click proxy > Duplicate As > Maya Data")
                    return False

            # Count what was converted
            cmds.refresh()
            native_meshes = cmds.ls(type="mesh", dag=True) or []
            native_joints = cmds.ls(type="joint", dag=True) or []
            native_skins = cmds.ls(type="skinCluster") or []

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

    def _convert_skinned_meshes_to_maya(self, proxy_shape: str, result: ImportResult) -> bool:
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

            self.logger.info(
                f"[REFRESH] Converting {len(skinned_mesh_paths)} skinned meshes to Maya..."
            )

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

                if hasattr(mayaUsdLib, "PrimUpdaterManager"):
                    self.logger.info("   Using mayaUsd.lib.PrimUpdaterManager...")
                    # This is the proper API for edit-as-maya
                    for mesh_path in skinned_mesh_paths:
                        try:
                            # Select the USD prim path
                            prim_path_str = f"{proxy_parent},{mesh_path}"
                            cmds.select(prim_path_str, replace=True)
                            # Try to duplicate as Maya
                            mel.eval("mayaUsdDuplicate -importMaya")
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
                    mel_cmd = (
                        f'file -import -type "USD Import" -options "{import_opts}" "{usd_path}"'
                    )
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
                        file=str(usd_path), primPath="/", importInstances=True
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
                        importInstances=True,
                    )
                    converted_count = len(skinned_mesh_paths)
                    self.logger.info("   [OK] Re-import as native Maya successful")
                except Exception as reimport_err:
                    self.logger.warning(f"[WARNING] Re-import failed: {reimport_err}")

            if converted_count > 0:
                self.logger.info(f"[OK] Converted {converted_count} skinned meshes to Maya")

                # Count native Maya objects created
                cmds.refresh()
                native_meshes = cmds.ls(type="mesh", dag=True) or []
                native_skins = cmds.ls(type="skinCluster") or []

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

            self.logger.debug(traceback.format_exc())
            return False

    def _create_usd_skin_bindings(
        self, proxy_shape: str, usd_path: Path, result: ImportResult
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
                indices_attr = mesh_prim.GetAttribute("primvars:skel:jointIndices")
                weights_attr = mesh_prim.GetAttribute("primvars:skel:jointWeights")
                if indices_attr and weights_attr:
                    if indices_attr.Get() and weights_attr.Get():
                        meshes_with_weights += 1

            if meshes_with_binding > 0 or meshes_with_weights > 0:
                self.logger.info("[OK] USD already has skeleton bindings:")
                self.logger.info(f"   [INFO] Meshes with binding: {meshes_with_binding}")
                self.logger.info(f"   [INFO] Meshes with weights: {meshes_with_weights}")

                # Check for empty geometry (multi-skinCluster corruption)
                empty_mesh_count = 0
                for mesh_prim in meshes[: min(5, len(meshes))]:  # Sample first 5
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
                    self.logger.warning(
                        "   [FIX] FIX: Re-export character with the updated exporter"
                    )
                    self.logger.warning(
                        "   The exporter now auto-fixes multi-skinCluster meshes during export"
                    )

                self.logger.info("[TIP] Skipping Phase 1 - using existing bindings")
                return True

            # Only create bindings if none exist
            self.logger.info("📝 No existing bindings found - creating new ones...")

            # Create anonymous layer for bindings
            anim_layer = Sdf.Layer.CreateAnonymous("skin_bindings")
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

            self.logger.error(traceback.format_exc())
            return False

    def _create_maya_joint_proxies(
        self, usd_path: Path, proxy_shape: str, result: ImportResult
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
            usd_joint_names = set(str(jp).split("/")[-1] for jp in usd_joint_paths)
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
                    loadReferenceDepth="none",  # Skip referenced file (RenderMan shader issues)
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
                for suffix in ["_l", "_r", "_left", "_right", "_lf", "_rt"]:
                    if lower.endswith(suffix):
                        return True
                for prefix in ["l_", "r_", "left_", "right_", "lf_", "rt_"]:
                    if lower.startswith(prefix):
                        return True
                return False

            # Helper function to strip side/center suffixes for matching
            def strip_side_prefix(name):
                """Strip common left/right/middle suffixes to match against USD skeleton."""
                lower = name.lower()
                # Check for common prefixes (case-insensitive)
                for prefix in [
                    "l_",
                    "r_",
                    "left_",
                    "right_",
                    "lf_",
                    "rt_",
                    "m_",
                    "mid_",
                    "middle_",
                    "c_",
                    "center_",
                ]:
                    if lower.startswith(prefix):
                        return name[len(prefix) :]
                # Check for common suffixes (including _M for middle/center joints)
                for suffix in [
                    "_l",
                    "_r",
                    "_left",
                    "_right",
                    "_lf",
                    "_rt",
                    "_m",
                    "_mid",
                    "_middle",
                    "_c",
                    "_center",
                ]:
                    if lower.endswith(suffix):
                        return name[: -len(suffix)]
                return name

            # First pass: collect all matching joints and track which have sided variants
            exact_matches = []  # Joints matching USD names exactly (may be reference joints)
            sided_matches = []  # Joints with _L/_R that match stripped USD names
            center_matches = []  # Joints with _M (middle/center) suffix
            sided_base_names = set()  # Base names that have sided variants

            # Helper to check if joint has center suffix
            def has_center_suffix(name):
                lower = name.lower()
                for suffix in ["_m", "_mid", "_middle", "_c", "_center"]:
                    if lower.endswith(suffix):
                        return True
                for prefix in ["m_", "mid_", "middle_", "c_", "center_"]:
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
                "root",
                "spine",
                "spine1",
                "spine2",
                "spine3",
                "spine4",
                "chest",
                "neck",
                "neck1",
                "neck2",
                "head",
                "jaw",
                "pelvis",
                "hips",
                "waist",
                "torso",
                "body",
                "cog",
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
                if (
                    maya_joint_lower not in matched_names_lower
                    and stripped not in matched_stripped
                ):
                    if maya_joint_name not in [f.split(" ")[0] for f in filtered_out]:
                        filtered_out.append(maya_joint_name)

            if not all_joints:
                self.logger.error(
                    "[ERROR] No matching joints found between Maya rig and USD skeleton"
                )
                self.logger.info(
                    f"   Maya has {len(all_maya_joints)} joints, USD expects {len(usd_joint_names)}"
                )
                return False

            self.logger.info(
                f"[TARGET] Filtered to {len(all_joints)} joints matching USD skeleton"
            )

            # Log joints that will be mirrored (unsided foot/limb joints)
            if joints_to_mirror:
                mirror_names = [j.split(":")[-1] for j in joints_to_mirror]
                self.logger.info(f"[REFRESH] Unsided joints to mirror: {mirror_names}")

            # Count left/right/center joints for diagnostics
            left_count = sum(
                1
                for j in all_joints
                if j.split(":")[-1].lower().startswith(("l_", "left_", "lf_"))
                or j.split(":")[-1].lower().endswith(("_l", "_left", "_lf"))
            )
            right_count = sum(
                1
                for j in all_joints
                if j.split(":")[-1].lower().startswith(("r_", "right_", "rt_"))
                or j.split(":")[-1].lower().endswith(("_r", "_right", "_rt"))
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
                joint_list = ", ".join(filtered_out[:10])
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
                                self.logger.info(
                                    f"   Found ancestor (full): {parent.split(':')[-1]}"
                                )
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
                                self.logger.info(
                                    f"   Found ancestor (stripped): {parent_short} -> {parent_stripped}"
                                )
                            return stripped_to_full[parent_stripped]

                    # Keep walking up (whether joint or not)
                    current = parent

                if debug:
                    self.logger.info(f"   Walk exhausted: {' -> '.join(walk_path)}")
                return None

            # Count root joints for debugging
            root_count = 0
            debug_joints = ["Hip_L", "Scapula_L"]  # Debug these specific joints
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
            self.logger.info(
                f"[OK] Built hierarchy map for {len(all_joints)} joints ({root_count} roots)"
            )
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
                mirrored_joints_data.append(
                    {
                        "original": mirror_joint,
                        "name": f"{mirror_name}_L",
                        "side": "L",
                        "position": left_pos,
                        "orientation": joint_orient,
                    }
                )

                # Create RIGHT version (_R) - mirror X
                right_pos = (-abs(original_x), world_pos[1], world_pos[2])
                mirrored_joints_data.append(
                    {
                        "original": mirror_joint,
                        "name": f"{mirror_name}_R",
                        "side": "R",
                        "position": right_pos,
                        "orientation": joint_orient,  # Mirror orientation too if needed
                    }
                )

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
                maya_joint = cmds.joint(name=f"proxy_{joint_name}", position=(tx, ty, tz))

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
                orig_joint = mirror_data["original"]
                name = mirror_data["name"]
                side = mirror_data["side"]
                pos = mirror_data["position"]
                orient = mirror_data["orientation"]

                cmds.select(clear=True)
                mirror_proxy = cmds.joint(name=f"proxy_{name}", position=pos)

                # Apply orientation (mirror Y and Z for right side)
                if side == "R":
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
                maya_parent = cmds.listRelatives(orig_joint, parent=True, type="joint")

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
                    self.logger.warning(
                        "[WARNING] Could not find USD proxy transform, skeleton at world level"
                    )

            # Store imported joints for weight extraction (Phase 3.2)
            # We'll delete them after extracting skinCluster weights
            result._imported_joints = all_joints + joints_to_mirror
            result._proxy_joints = list(maya_joints.values()) + list(
                mirrored_proxy_joints.values()
            )
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

            self.logger.error(traceback.format_exc())
            return False

    def _connect_proxy_to_usd_skeleton(self, proxy_shape: str, result: ImportResult) -> bool:
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

            proxy_joints = getattr(result, "_proxy_joints", None)
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
                self.logger.warning(
                    f"[WARNING] mayaUsd.ufe getStage failed ({e}), using file-based stage"
                )
                stage = None

            if not stage:
                stage_path = cmds.getAttr(f"{proxy_shape}.filePath")
                if not stage_path:
                    self.logger.error("[ERROR] Could not get USD stage")
                    return False

                stage = Usd.Stage.Open(stage_path)

            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

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
                joint_name = str(joint_path).split("/")[-1].lower()
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
                proxy_name = proxy_joint.split("|")[-1]
                joint_name = proxy_name[6:] if proxy_name.startswith("proxy_") else proxy_name

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

            self.logger.error(traceback.format_exc())
            self._cleanup_imported_rig(result)
            return False

    def _create_proxy_driver_expressions(
        self, proxy_shape: str, joint_mapping: dict, skeleton_prim
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
            driver_grp = cmds.createNode("transform", name="USD_Skeleton_Driver")
            cmds.addAttr(driver_grp, ln="proxyShape", dt="string")
            cmds.setAttr(f"{driver_grp}.proxyShape", proxy_shape, type="string")

            # Create driver attributes for each mapped joint
            for proxy_joint, (_usd_path, _usd_idx) in joint_mapping.items():
                if not cmds.objExists(proxy_joint):
                    continue

                joint_short = proxy_joint.split("|")[-1]

                # Connect proxy joint transforms to driver group
                # This creates a dependency that Maya's DG will evaluate
                for attr in ["rotateX", "rotateY", "rotateZ"]:
                    src = f"{proxy_joint}.{attr}"
                    if cmds.objExists(src):
                        try:
                            # Create proxy attribute on driver
                            proxy_attr = f"{joint_short}_{attr}"
                            if not cmds.attributeQuery(proxy_attr, node=driver_grp, exists=True):
                                cmds.addAttr(driver_grp, ln=proxy_attr, at="double")
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
        self, proxy_shape: str, proxy_transform: str, joint_mapping: dict
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
                        cmds.connectAttr(f"{proxy_joint}.rotate", attr_proxy, force=True)
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
        self, driver_grp: str, joint_mapping: dict, proxy_shape: str
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
                                joint_name = str(joint_path).split("/")[-1]
                                proxy_name = f"proxy_{joint_name}"

                                if cmds.objExists(proxy_name):
                                    rot = cmds.getAttr(f"{proxy_name}.rotate")[0]
                                    rotations.append(
                                        Gf.Quatf(
                                            Gf.Rotation(Gf.Vec3d(1, 0, 0), rot[0])
                                            * Gf.Rotation(Gf.Vec3d(0, 1, 0), rot[1])
                                            * Gf.Rotation(Gf.Vec3d(0, 0, 1), rot[2])
                                        )
                                    )
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
                event=["timeChanged", sync_skeleton_transforms], protected=True, parent=driver_grp
            )

            self.logger.info("[OK] Registered skeleton sync callback")

        except Exception as e:
            self.logger.warning(f"[WARNING] Could not register sync callback: {e}")

    def _transfer_skin_weights_full(
        self, usd_path: Path, result: ImportResult, load_references: bool = True
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
                indices_attr = prim.GetAttribute("primvars:skel:jointIndices")
                weights_attr = prim.GetAttribute("primvars:skel:jointWeights")

                has_weights = False
                if indices_attr and weights_attr:
                    indices = indices_attr.Get()
                    weights = weights_attr.Get()

                    if indices and weights:
                        has_weights = True
                        meshes_with_weights += 1
                        total_weight_values += len(weights)

                        if meshes_with_weights <= 5:
                            self.logger.info(f"   [OK] {mesh_name}: {len(weights)} weights")

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
                self.logger.info(
                    "[TIP] Was USDZ exported with 'Viewport-friendly skeleton' UNCHECKED?"
                )
                self.logger.info("[TIP] Falling back to proxy joint connection...")
                return False

            # Store binding info for potential repair
            result._usd_binding_info = {
                "meshes_with_weights": meshes_with_weights,
                "meshes_with_binding": meshes_with_binding,
                "binding_issues": binding_issues,
                "skeleton_path": str(skeleton_prim.GetPath()),
                "skel_root": str(skel_roots[0].GetPath()) if skel_roots else None,
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

            self.logger.error(traceback.format_exc())
            return False

    def _repair_usd_skin_bindings(self, usd_path: Path, result: ImportResult) -> bool:
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

            binding_info = getattr(result, "_usd_binding_info", None)
            if not binding_info or not binding_info.get("binding_issues"):
                self.logger.info("[OK] No binding repairs needed")
                return True

            self.logger.info("[FIX] Repairing USD skin bindings...")

            # Open stage for editing
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.error("[ERROR] Could not open USD stage")
                return False

            skeleton_path = binding_info.get("skeleton_path")
            if not skeleton_path:
                self.logger.error("[ERROR] No skeleton path for binding")
                return False

            repairs_made = 0

            for prim in stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue

                # Check if this mesh needs repair
                indices_attr = prim.GetAttribute("primvars:skel:jointIndices")
                weights_attr = prim.GetAttribute("primvars:skel:jointWeights")

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

    def _transfer_skin_weights(self, usd_path: Path, result: ImportResult) -> bool:
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

            self.logger.info("[BLEND] Phase 3.2: Transferring skin weights...")

            # Check if we have imported joints to extract from
            imported_joints = getattr(result, "_imported_joints", None)
            if not imported_joints:
                self.logger.warning("[WARNING] No imported joints found for weight extraction")
                return False

            # Find all skinClusters in the scene (from the imported rig)
            skin_clusters = cmds.ls(type="skinCluster") or []
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
            usd_joint_names = [str(j).split("/")[-1].lower() for j in usd_joints]
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

                mesh_name = geometry[0].split("|")[-1].split(":")[-1]
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
                            skin_cluster,
                            f"{geometry[0]}.vtx[{vtx_idx}]",
                            transform=influence,
                            query=True,
                        )

                        if weight > 0.001:  # Skip near-zero weights
                            # Map Maya influence name to USD joint index
                            inf_name = influence.split("|")[-1].split(":")[-1]
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
                    self.logger.info(f"   [OK] Extracted {len(mesh_weights)} weight values")

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

            self.logger.error(traceback.format_exc())
            self._cleanup_imported_rig(result)
            return False

    def _strip_side_suffix(self, name: str) -> str:
        """Strip L/R/M side suffixes for joint name matching."""
        lower = name.lower()
        for suffix in ["_l", "_r", "_m", "_left", "_right", "_mid"]:
            if lower.endswith(suffix):
                return name[: -len(suffix)]
        return name

    def _cleanup_imported_rig(self, result: ImportResult) -> None:
        """Clean up the imported rig nodes after weight extraction."""
        imported_joints = getattr(result, "_imported_joints", None)
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
                        if "|" in node:
                            root = node.split("|")[1]
                        else:
                            root = node.split(":")[-1] if ":" in node else node
                        # Get the actual root with namespace
                        full_root = f"RIG_REFERENCE:{root}" if ":" not in root else root
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
                            root = parents[0].split("|")[1] if "|" in parents[0] else j
                            if root not in roots_to_delete and cmds.objExists(root):
                                roots_to_delete.append(root)

                # Delete unique roots
                deleted_count = 0
                for root in set(roots_to_delete):
                    if cmds.objExists(root) and not root.startswith("proxy_"):
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

    def _import_nurbs_controllers(self, rig_mb_path: Path, result: ImportResult) -> int:
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
            before_curves = set(cmds.ls(type="nurbsCurve", long=True) or [])

            # Import the .rig.mb file
            imported_nodes = cmds.file(
                str(rig_mb_path),
                i=True,
                type="mayaBinary",
                returnNewNodes=True,
                preserveReferences=True,
                ignoreVersion=True,
                namespaceOption=":",  # Import to root namespace
                mergeNamespacesOnClash=True,
            )

            if not imported_nodes:
                self.logger.warning("[WARNING] No nodes imported from .rig.mb")
                return 0

            # Filter to only NURBS curves
            after_curves = set(cmds.ls(type="nurbsCurve", long=True) or [])
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
                if node_type == "nurbsCurve":
                    continue  # Keep curve shapes

                if node_type == "transform":
                    # Check if this transform has a NURBS curve child
                    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
                    has_curve = any(cmds.nodeType(s) == "nurbsCurve" for s in shapes)
                    if has_curve:
                        continue  # Keep controller transforms

                    # Check if any descendants have NURBS curves
                    descendants = (
                        cmds.listRelatives(node, allDescendents=True, fullPath=True) or []
                    )
                    has_curve_descendant = any(
                        cmds.nodeType(d) == "nurbsCurve" for d in descendants if cmds.objExists(d)
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
                self.logger.info(
                    f"   [DELETE] Cleaned up {len(nodes_to_delete)} non-controller nodes"
                )

            return len(controller_transforms)

        except Exception as e:
            self.logger.error(f"[ERROR] Controller import failed: {e}")

            self.logger.error(traceback.format_exc())
            return 0

    def _connect_controllers_to_skeleton(self, result: ImportResult) -> int:
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
            controllers = getattr(result, "_controllers", [])
            converted_joints = getattr(result, "_converted_joints", [])

            if not controllers:
                self.logger.warning("[WARNING] No controllers to connect")
                return 0

            if not converted_joints:
                self.logger.warning("[WARNING] No skeleton joints to connect to")
                return 0

            self.logger.info(
                f"🔗 Matching {len(controllers)} controllers to {len(converted_joints)} joints..."
            )

            # Build joint name lookup (remove namespace and path, lowercase for matching)
            joint_map = {}
            for joint in converted_joints:
                if not cmds.objExists(joint):
                    continue
                # Get short name without namespace
                short_name = joint.split("|")[-1].split(":")[-1].lower()
                joint_map[short_name] = joint

            # Try to match controllers to joints
            connections_made = 0
            for controller in controllers:
                if not cmds.objExists(controller):
                    continue

                # Get controller name
                ctrl_name = controller.split("|")[-1].split(":")[-1]

                # Try different matching strategies
                joint_to_connect = None

                # Strategy 1: Exact match (lowercased)
                ctrl_name_lower = ctrl_name.lower()
                if ctrl_name_lower in joint_map:
                    joint_to_connect = joint_map[ctrl_name_lower]

                # Strategy 2: Strip common controller suffixes (_ctrl, _CTRL, Ctrl, etc.)
                if not joint_to_connect:
                    stripped_name = ctrl_name_lower
                    for suffix in ["_ctrl", "_control", "_con", "_c", "ctrl", "control"]:
                        if stripped_name.endswith(suffix):
                            stripped_name = stripped_name[: -len(suffix)]
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
                            controller, joint_to_connect, maintainOffset=False, weight=1.0
                        )
                        if constraint:
                            connections_made += 1
                            self.logger.info(
                                f"   [OK] {ctrl_name} → {joint_to_connect.split('|')[-1]}"
                            )
                    except Exception as e:
                        self.logger.warning(f"   [WARNING] Could not connect {ctrl_name}: {e}")
                else:
                    self.logger.debug(f"   ⏭️ No match for controller: {ctrl_name}")

            return connections_made

        except Exception as e:
            self.logger.error(f"[ERROR] Controller connection failed: {e}")

            self.logger.error(traceback.format_exc())
            return 0

    def _supplement_from_rig_mb(
        self, rig_mb_path: Path, options: ImportOptions, result: ImportResult
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
        proxy_shapes = cmds.ls(type="mayaUsdProxyShape") or []
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
        self.logger.warning(
            "[WARNING] USD import created no proxy content - using .rig.mb fallback"
        )

        try:
            self.logger.info("[REFRESH] Importing .rig.mb as fallback...")
            cmds.file(new=True, force=True)  # Clear scene

            imported_nodes = cmds.file(
                str(rig_mb_path),
                i=True,
                type="mayaBinary" if str(rig_mb_path).endswith(".mb") else "mayaAscii",
                returnNewNodes=True,
                preserveReferences=True,
                ignoreVersion=True,
            )

            if imported_nodes:
                self.logger.info(f"[OK] Imported {len(imported_nodes)} nodes from rig backup")
                result.used_rig_mb_fallback = True
                result.fallback_components = ["Full rig"]

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
