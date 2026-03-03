# -*- coding: utf-8 -*-
"""
USD Skeleton Reader Implementation
Reads UsdSkel skeleton and skin weight data from USD stages

Author: Mike Stumbo
Version: 1.5.0
Date: November 2025
"""

import logging
from typing import Optional, List, Any, Tuple
from dataclasses import dataclass

# USD imports (conditional)
try:
    from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf, Vt  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    # Type stubs
    Usd: Any = None  # type: ignore
    UsdGeom: Any = None  # type: ignore
    UsdSkel: Any = None  # type: ignore
    Sdf: Any = None  # type: ignore
    Gf: Any = None  # type: ignore
    Vt: Any = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class UsdSkeletonData:
    """USD skeleton data extracted from stage"""
    skeleton_path: str  # USD path to skeleton prim
    joint_names: List[str]  # Ordered list of joint names (USD paths)
    joint_count: int
    has_animation: bool = False

    def get_joint_short_names(self) -> List[str]:
        """Get short joint names (last component of USD path)"""
        return [name.split('/')[-1] for name in self.joint_names]


@dataclass
class UsdSkinWeightData:
    """Skin weight data for a single mesh"""
    mesh_path: str  # USD path to mesh
    skeleton_path: str  # USD path to bound skeleton

    # Per-vertex data
    joint_indices: List[List[int]]  # Per vertex: list of joint indices
    joint_weights: List[List[float]]  # Per vertex: list of weights
    vertex_count: int
    max_influences: int  # Max joints per vertex

    # CRITICAL: Vertex positions for matching Maya vertices to USD vertices
    vertex_positions: Optional[List[Tuple[float, float, float]]] = None

    # Bind transform data
    geom_bind_transform: Optional[List[float]] = None  # 4x4 matrix as flat list

    # Validation
    is_normalized: bool = False
    has_invalid_weights: bool = False

    def validate(self) -> Tuple[bool, str]:
        """Validate skin weight data"""
        if len(self.joint_indices) != self.vertex_count:
            return False, f"Joint indices count mismatch: {len(self.joint_indices)} vs {self.vertex_count}"

        if len(self.joint_weights) != self.vertex_count:
            return False, f"Joint weights count mismatch: {len(self.joint_weights)} vs {self.vertex_count}"

        # Check weight normalization
        for v_idx, weights in enumerate(self.joint_weights):
            weight_sum = sum(weights)
            if abs(weight_sum - 1.0) > 0.01:  # Allow small tolerance
                self.has_invalid_weights = True
                logger.warning(f"Vertex {v_idx} has non-normalized weights: {weight_sum}")

        self.is_normalized = not self.has_invalid_weights
        return True, ""


class UsdSkeletonReaderImpl:
    """
    USD Skeleton Reader Implementation

    Reads UsdSkel data from USD stages and converts to intermediate format
    for Maya skinCluster creation.

    Clean Code: Single Responsibility - Read USD skeleton data
    """

    def __init__(self):
        """Initialize USD skeleton reader"""
        if not USD_AVAILABLE:
            logger.error("USD Python libraries not available!")

        self.logger = logging.getLogger(__name__)

    def read_skeleton(self, stage: Any, skeleton_path: str) -> Optional[UsdSkeletonData]:
        """
        Read skeleton data from USD stage

        Args:
            stage: USD Stage
            skeleton_path: Path to skeleton prim (e.g., "/Skeleton")

        Returns:
            UsdSkeletonData or None if not found
        """
        if not USD_AVAILABLE:
            self.logger.error("USD not available")
            return None

        try:
            # Get skeleton prim
            skel_prim = stage.GetPrimAtPath(skeleton_path)
            if not skel_prim or not skel_prim.IsValid():
                self.logger.error(f"Skeleton not found at: {skeleton_path}")
                return None

            # Create UsdSkel.Skeleton schema
            skeleton = UsdSkel.Skeleton(skel_prim)
            if not skeleton:
                self.logger.error(f"Invalid skeleton schema at: {skeleton_path}")
                return None

            # Read joint names (topology)
            joints_attr = skeleton.GetJointsAttr()
            if not joints_attr:
                self.logger.error("No joints attribute found")
                return None

            joint_names = joints_attr.Get()
            if not joint_names:
                self.logger.error("Empty joint list")
                return None

            self.logger.info(f"Read skeleton: {len(joint_names)} joints from {skeleton_path}")

            # Check for animation (rest transforms vs animated transforms)
            has_animation = self._check_skeleton_animation(skeleton)

            return UsdSkeletonData(
                skeleton_path=skeleton_path,
                joint_names=list(joint_names),
                joint_count=len(joint_names),
                has_animation=has_animation
            )

        except Exception as e:
            self.logger.error(f"Failed to read skeleton: {e}")
            return None

    def _check_skeleton_animation(self, skel: Any) -> bool:
        """
        Check if skeleton has animation data.

        Looks for UsdSkelAnimation prims and time-varying joint transforms.

        Args:
            skel: UsdSkel.Skeleton object

        Returns:
            True if skeleton has animation tracks
        """
        try:
            from pxr import UsdSkel  # type: ignore

            # Check for animation binding
            binding = UsdSkel.BindingAPI(skel.GetPrim())
            anim_source = binding.GetAnimationSourceRel()

            if anim_source and anim_source.HasAuthoredTargets():
                targets = anim_source.GetTargets()
                if targets:
                    self.logger.debug(f"Found animation source: {targets[0]}")
                    return True

            # Check if joints have time-sampled transforms
            joints_attr = skel.GetJointsAttr()
            if joints_attr:
                # Time sampling indicates animation
                time_samples = joints_attr.GetTimeSamples()
                if time_samples:
                    return True

            return False

        except Exception as e:
            self.logger.debug(f"Animation check failed: {e}")
            return False

    def read_skin_weights(
        self,
        stage: Any,
        mesh_path: str,
        skeleton_data: UsdSkeletonData
    ) -> Optional[UsdSkinWeightData]:
        """
        Read skin weight data from mesh prim

        Args:
            stage: USD Stage
            mesh_path: Path to mesh prim
            skeleton_data: Skeleton data for joint mapping

        Returns:
            UsdSkinWeightData or None if no skinning found
        """
        if not USD_AVAILABLE:
            self.logger.error("USD not available")
            return None

        try:
            # Get mesh prim
            mesh_prim = stage.GetPrimAtPath(mesh_path)
            if not mesh_prim or not mesh_prim.IsValid():
                self.logger.error(f"Mesh not found at: {mesh_path}")
                return None

            # Get UsdSkel binding API
            binding_api = UsdSkel.BindingAPI(mesh_prim)
            if not binding_api:
                self.logger.debug(f"No skinning found on mesh: {mesh_path}")
                return None

            # Get skeleton binding
            skel_rel = binding_api.GetSkeletonRel()
            if not skel_rel:
                self.logger.debug(f"No skeleton relationship on mesh: {mesh_path}")
                return None

            targets = skel_rel.GetTargets()
            if not targets:
                self.logger.debug(f"No skeleton targets on mesh: {mesh_path}")
                return None

            skeleton_path = str(targets[0])
            self.logger.info(f"Reading skin weights: {mesh_path} → {skeleton_path}")

            # Read joint indices primvar
            joint_indices_primvar = binding_api.GetJointIndicesPrimvar()
            if not joint_indices_primvar:
                self.logger.error(f"No joint indices primvar on: {mesh_path}")
                return None

            joint_indices_flat = joint_indices_primvar.Get()
            if not joint_indices_flat:
                self.logger.error(f"Empty joint indices on: {mesh_path}")
                return None

            # Read joint weights primvar
            joint_weights_primvar = binding_api.GetJointWeightsPrimvar()
            if not joint_weights_primvar:
                self.logger.error(f"No joint weights primvar on: {mesh_path}")
                return None

            joint_weights_flat = joint_weights_primvar.Get()
            if not joint_weights_flat:
                self.logger.error(f"Empty joint weights on: {mesh_path}")
                return None

            # Get element size (max influences per vertex)
            element_size = joint_indices_primvar.GetElementSize()
            if element_size <= 0:
                self.logger.error(f"Invalid element size: {element_size}")
                return None

            # Get vertex count
            mesh_geom = UsdGeom.Mesh(mesh_prim)
            vertex_count = len(mesh_geom.GetPointsAttr().Get())

            # Reshape flat arrays to per-vertex lists
            joint_indices = []
            joint_weights = []

            # Diagnostic: Track weight statistics
            min_weight = float('inf')
            max_weight = 0.0
            total_weights = 0
            non_zero_weights = 0

            for v_idx in range(vertex_count):
                start_idx = v_idx * element_size
                end_idx = start_idx + element_size

                indices = list(joint_indices_flat[start_idx:end_idx])
                weights = list(joint_weights_flat[start_idx:end_idx])

                # Collect statistics for first 100 vertices
                if v_idx < 100:
                    for w in weights:
                        if w > 0:
                            min_weight = min(min_weight, w)
                            max_weight = max(max_weight, w)
                            non_zero_weights += 1
                        total_weights += 1

                joint_indices.append(indices)
                joint_weights.append(weights)

            self.logger.info(f"Read skin weights: {vertex_count} vertices, {element_size} max influences")
            if non_zero_weights > 0:
                self.logger.info(
                    f"📊 Weight range (first 100 verts): min={min_weight:.6f}, "
                    f"max={max_weight:.6f}, non-zero={non_zero_weights}/{total_weights}"
                )

            # CRITICAL: Read vertex positions for position-based matching
            # This solves vertex order mismatch between USD and Maya
            vertex_positions = []
            try:
                points_attr = mesh_geom.GetPointsAttr()
                if points_attr:
                    points = points_attr.Get()
                    if points:
                        for point in points:
                            vertex_positions.append((float(point[0]), float(point[1]), float(point[2])))
                        self.logger.info(f"[OK] Read {len(vertex_positions)} vertex positions for matching")
            except Exception as pos_error:
                self.logger.warning(f"Could not read vertex positions: {pos_error}")
                vertex_positions = None

            # Read geomBindTransform if present
            # NOTE: skel:geomBindTransform is often computed/inherited in USD and may not be directly readable
            # Maya can calculate the correct bind pose from joint transforms (bindPreMatrix) so this is optional
            geom_bind_transform = None
            try:
                primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
                geom_bind_primvar = primvars_api.GetPrimvar("skel:geomBindTransform")

                geom_bind_value = None
                if geom_bind_primvar:
                    geom_bind_value = geom_bind_primvar.ComputeFlattened()
                    if not geom_bind_value:
                        geom_bind_value = geom_bind_primvar.Get()

                # Try direct attribute access as fallback
                if not geom_bind_value:
                    geom_bind_attr = mesh_prim.GetAttribute("primvars:skel:geomBindTransform")
                    if geom_bind_attr and geom_bind_attr.IsValid():
                        geom_bind_value = geom_bind_attr.Get()

                # Convert USD matrix to flat list if found
                if geom_bind_value and hasattr(geom_bind_value, '__iter__'):
                    flat_matrix = []
                    for row in range(4):
                        for col in range(4):
                            flat_matrix.append(float(geom_bind_value[row][col]))
                    geom_bind_transform = flat_matrix
                    self.logger.info(f"[OK] Read skel:geomBindTransform from {mesh_path}")
                else:
                    # This is not an error - Maya will use joint bind matrices instead
                    self.logger.debug(f"No skel:geomBindTransform on {mesh_path} (will use joint bind matrices)")

            except Exception as bind_error:
                self.logger.debug(f"Could not read geomBindTransform: {bind_error}")

            # Create skin weight data
            weight_data = UsdSkinWeightData(
                mesh_path=mesh_path,
                skeleton_path=skeleton_path,
                joint_indices=joint_indices,
                joint_weights=joint_weights,
                vertex_count=vertex_count,
                max_influences=element_size,
                vertex_positions=vertex_positions,  # CRITICAL: For position-based matching
                geom_bind_transform=geom_bind_transform
            )

            # Validate
            is_valid, error_msg = weight_data.validate()
            if not is_valid:
                self.logger.warning(f"Skin weight validation warning: {error_msg}")

            return weight_data

        except Exception as e:
            self.logger.error(f"Failed to read skin weights from {mesh_path}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def find_skeletons(self, stage: Any) -> List[str]:
        """
        Find all skeleton prims in USD stage

        Args:
            stage: USD Stage

        Returns:
            List of skeleton prim paths
        """
        if not USD_AVAILABLE:
            return []

        skeletons = []
        try:
            # Traverse stage looking for UsdSkel.Skeleton prims
            for prim in stage.Traverse():
                if prim.IsA(UsdSkel.Skeleton):
                    skeletons.append(str(prim.GetPath()))

            self.logger.info(f"Found {len(skeletons)} skeletons in stage")

        except Exception as e:
            self.logger.error(f"Failed to find skeletons: {e}")

        return skeletons

    def find_skinned_meshes(self, stage: Any, skeleton_path: str) -> List[str]:
        """
        Find all meshes bound to a skeleton

        Args:
            stage: USD Stage
            skeleton_path: Path to skeleton

        Returns:
            List of mesh prim paths
        """
        if not USD_AVAILABLE:
            return []

        skinned_meshes = []
        try:
            skeleton_sdf_path = Sdf.Path(skeleton_path)

            # Traverse stage looking for meshes with skinning
            for prim in stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue

                # Check for skeleton binding
                binding_api = UsdSkel.BindingAPI(prim)
                if not binding_api:
                    continue

                skel_rel = binding_api.GetSkeletonRel()
                if not skel_rel:
                    continue

                targets = skel_rel.GetTargets()
                if skeleton_sdf_path in targets:
                    skinned_meshes.append(str(prim.GetPath()))

            self.logger.info(f"Found {len(skinned_meshes)} meshes bound to {skeleton_path}")

        except Exception as e:
            self.logger.error(f"Failed to find skinned meshes: {e}")

        return skinned_meshes
