# -*- coding: utf-8 -*-
"""
USD Rig Converter Implementation
Converts Maya rigging data to UsdSkel format

Author: Mike Stumbo
Version: 1.5.0
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

# USD imports (conditional)
try:
    from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf, Vt  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    # Type suppressions
    Usd: Any = None  # type: ignore
    UsdGeom: Any = None  # type: ignore
    UsdSkel: Any = None  # type: ignore
    Sdf: Any = None  # type: ignore
    Gf: Any = None  # type: ignore
    Vt: Any = None  # type: ignore

from ...core.interfaces.usd_rig_converter import IUSDRigConverter
from ...core.interfaces.maya_scene_parser import JointData, SkinClusterData

logger = logging.getLogger(__name__)


class USDRigConverterImpl(IUSDRigConverter):
    """
    USD Rig Converter Implementation

    Converts Maya rigging data to UsdSkel format.

    Clean Code Principles:
    - Single Responsibility: Only handles rigging conversion
    - Dependency Inversion: Depends on interface, not implementation
    - Small functions with clear names

    Disney/Pixar Critical: UsdSkel accuracy essential for animation pipelines
    """

    def __init__(self):
        """Initialize rig converter"""
        if not USD_AVAILABLE:
            logger.warning("USD Python libraries not available - rig converter will fail")

        logger.info("USD Rig Converter initialized")

    def convert_skeleton(
        self,
        joint_data: List[JointData],
        usd_stage: Any,  # pxr.Usd.Stage
        skeleton_path: str = "/Skeleton"
    ) -> Optional[Any]:  # pxr.UsdSkel.Skeleton
        """
        Convert Maya joint hierarchy to UsdSkel.Skeleton

        Clean Code: Clear workflow - validate, build topology, create skeleton
        """
        if not USD_AVAILABLE:
            logger.error("USD libraries not available")
            return None

        if not joint_data:
            logger.warning("No joint data provided")
            return None

        try:
            logger.info(f"Converting skeleton with {len(joint_data)} joints to {skeleton_path}")

            # Validate joint topology
            is_valid, error_msg = self.validate_joint_topology(joint_data)
            if not is_valid:
                logger.error(f"Invalid joint topology: {error_msg}")
                return None

            # Create skeleton prim
            skeleton = UsdSkel.Skeleton.Define(usd_stage, skeleton_path)

            # Build joint topology (ordered list of joint paths)
            joint_paths = self._build_joint_paths(joint_data)
            skeleton.GetJointsAttr().Set(joint_paths)

            logger.info(f"Created skeleton with {len(joint_paths)} joints")

            # Set bind transforms
            if not self.create_bind_pose(skeleton, joint_data):
                logger.error("Failed to set bind pose")
                return None

            return skeleton

        except Exception as e:
            logger.error(f"Failed to convert skeleton: {e}")
            return None

    def convert_skin_weights(
        self,
        skin_cluster_data: SkinClusterData,
        skeleton: Any,  # pxr.UsdSkel.Skeleton
        mesh_prim: Any  # pxr.Usd.Prim
    ) -> bool:
        """
        Convert Maya skin weights to USD skinning primvars

        Clean Code: Normalize, prune, then apply weights
        Disney/Pixar Critical: Accurate weight preservation
        """
        if not USD_AVAILABLE:
            logger.error("USD libraries not available")
            return False

        try:
            logger.info(f"Converting skin weights for mesh: {skin_cluster_data.mesh_name}")

            # Normalize and prune weights
            weights = self.normalize_weights(skin_cluster_data.weights)
            weights = self.prune_zero_weights(weights, threshold=0.001)

            # Get max influences
            max_influences = self.get_max_influences_per_vertex(skin_cluster_data)
            logger.debug(f"Max influences per vertex: {max_influences}")

            # Convert weights to USD format
            joint_indices, joint_weights = self._convert_weights_to_usd_format(
                weights,
                max_influences
            )

            # Create skinning primvars on mesh
            skel_binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)

            # Set skeleton binding
            skeleton_path = skeleton.GetPath()
            skel_binding_api.CreateSkeletonRel().SetTargets([skeleton_path])

            # Set joint indices
            joint_indices_primvar = skel_binding_api.CreateJointIndicesPrimvar(
                False,  # constant = False (per-vertex)
                max_influences
            )
            joint_indices_primvar.Set(joint_indices)

            # Set joint weights
            joint_weights_primvar = skel_binding_api.CreateJointWeightsPrimvar(
                False,  # constant = False (per-vertex)
                max_influences
            )
            joint_weights_primvar.Set(joint_weights)

            logger.info(f"Successfully converted skin weights for {len(weights)} vertices")
            return True

        except Exception as e:
            logger.error(f"Failed to convert skin weights: {e}")
            return False

    def create_bind_pose(
        self,
        skeleton: Any,  # pxr.UsdSkel.Skeleton
        joint_data: List[JointData]
    ) -> bool:
        """
        Set skeleton bind pose from Maya joint transforms

        Clean Code: Explicit bind pose operation
        """
        if not USD_AVAILABLE:
            logger.error("USD libraries not available")
            return False

        try:
            logger.debug(f"Setting bind pose for {len(joint_data)} joints")

            # Build bind transforms in joint order
            bind_transforms = []
            rest_transforms = []

            # Create joint SHORT NAME to data mapping for quick lookup
            # USD skeleton uses short names, Maya joint_data uses full DAG paths
            joint_map = {}
            for j in joint_data:
                short_name = j.name.split('|')[-1]  # Extract short name from DAG path
                joint_map[short_name] = j

            # Get joint order from skeleton
            joint_paths = skeleton.GetJointsAttr().Get()

            for joint_path in joint_paths:
                # Extract joint name from USD path (e.g., "root/spine/head" -> "head")
                joint_short_name = joint_path.split('/')[-1]

                if joint_short_name not in joint_map:
                    logger.error(f"Joint {joint_short_name} not found in joint data")
                    return False

                joint = joint_map[joint_short_name]

                # FIXED: Use bind_pose_matrix which is now in LOCAL space (object space)
                # Maya scene parser now queries objectSpace=True directly from Maya
                # No need to compute local from world - Maya gives us the correct local transform!
                local_matrix = self._maya_matrix_to_gf_matrix(joint.bind_pose_matrix)

                bind_transforms.append(local_matrix)
                rest_transforms.append(local_matrix)  # Use same for rest (identity bind)

            # Set bind transforms
            skeleton.GetBindTransformsAttr().Set(Vt.Matrix4dArray(bind_transforms))
            skeleton.GetRestTransformsAttr().Set(Vt.Matrix4dArray(rest_transforms))

            logger.info(f"Successfully set bind pose for {len(bind_transforms)} joints")
            return True

        except Exception as e:
            logger.error(f"Failed to create bind pose: {e}")
            return False

    def validate_joint_topology(
        self,
        joint_data: List[JointData]
    ) -> Tuple[bool, str]:
        """
        Validate joint hierarchy is valid for USD

        Clean Code: Validation before processing
        """
        if not joint_data:
            return False, "No joint data provided"

        # Check for duplicate joint FULL PATHS (joint.name is the DAG path from Maya)
        joint_paths = [j.name for j in joint_data]
        if len(joint_paths) != len(set(joint_paths)):
            duplicates = [path for path in joint_paths if joint_paths.count(path) > 1]
            # Show only first 3 duplicates to avoid overwhelming log
            duplicates_preview = duplicates[:3]
            return False, f"Duplicate joint paths found (showing first 3): {duplicates_preview}"

        # Check for root joints (joints with no parent)
        root_joints = [j for j in joint_data if j.parent_name is None]
        if not root_joints:
            return False, "No root joint found (all joints have parents)"

        # Multiple root joints are valid in USD (separate hierarchies, FK/IK, facial rigs, etc.)
        if len(root_joints) > 1:
            root_names = [j.name.split('|')[-1] for j in root_joints]
            preview = root_names[:5]
            suffix = '...' if len(root_names) > 5 else ''
            logger.info(f"Skeleton has {len(root_joints)} root joints: {preview}{suffix}")

        # Check for valid parent references
        joint_path_set = set(joint_paths)
        for joint in joint_data:
            if joint.parent_name and joint.parent_name not in joint_path_set:
                joint_short = joint.name.split('|')[-1]
                parent_short = joint.parent_name.split('|')[-1] if joint.parent_name else "None"
                return False, f"Joint {joint_short} references non-existent parent: {parent_short}"

        # Check for cycles (a joint cannot be its own ancestor)
        if self._has_cycle(joint_data):
            return False, "Cycle detected in joint hierarchy"

        # Build validation summary
        if len(root_joints) == 1:
            root_short_name = root_joints[0].name.split('|')[-1]
            logger.debug(f"Joint topology validated: {len(joint_data)} joints, single root: {root_short_name}")
        else:
            logger.debug(f"Joint topology validated: {len(joint_data)} joints, {len(root_joints)} root hierarchies")

        return True, ""

    def normalize_weights(
        self,
        weights: Dict[int, List[tuple]]
    ) -> Dict[int, List[tuple]]:
        """
        Normalize skin weights to sum to 1.0 per vertex

        Clean Code: Weight normalization is separate utility
        """
        normalized = {}

        for vertex_idx, vertex_weights in weights.items():
            if not vertex_weights:
                continue

            # Calculate sum
            total = sum(weight for _, weight in vertex_weights)

            if total == 0.0:
                logger.warning(f"Vertex {vertex_idx} has zero total weight")
                # Equal distribution as fallback
                normalized[vertex_idx] = [
                    (joint_idx, 1.0 / len(vertex_weights))
                    for joint_idx, _ in vertex_weights
                ]
            elif abs(total - 1.0) > 0.001:
                # Normalize
                normalized[vertex_idx] = [
                    (joint_idx, weight / total)
                    for joint_idx, weight in vertex_weights
                ]
            else:
                # Already normalized
                normalized[vertex_idx] = vertex_weights

        return normalized

    def get_max_influences_per_vertex(
        self,
        skin_cluster_data: SkinClusterData
    ) -> int:
        """
        Get maximum number of joint influences per vertex

        Clean Code: Analyze data before processing
        """
        if not skin_cluster_data.weights:
            return 0

        max_influences = max(
            len(vertex_weights)
            for vertex_weights in skin_cluster_data.weights.values()
        )

        return max_influences

    def prune_zero_weights(
        self,
        weights: Dict[int, List[tuple]],
        threshold: float = 0.001
    ) -> Dict[int, List[tuple]]:
        """
        Remove weights below threshold to optimize data

        Clean Code: Optimization utility
        """
        pruned = {}

        for vertex_idx, vertex_weights in weights.items():
            # Filter weights above threshold
            filtered = [
                (joint_idx, weight)
                for joint_idx, weight in vertex_weights
                if weight >= threshold
            ]

            if filtered:
                pruned[vertex_idx] = filtered
            else:
                # Keep at least one weight (the largest)
                if vertex_weights:
                    max_weight = max(vertex_weights, key=lambda x: x[1])
                    pruned[vertex_idx] = [max_weight]

        return pruned

    # ==================== Private Helper Methods ====================

    def _build_joint_paths(self, joint_data: List[JointData]) -> List[str]:
        """
        Build ordered list of joint paths for USD skeleton

        Clean Code: Hierarchical path building
        """
        # Build parent-child mapping using full DAG paths
        joint_map_full = {j.name: j for j in joint_data}

        # Also build short name mapping for child lookup
        # (Children are stored as short names in JointData.children)
        joint_map_short = {}
        for j in joint_data:
            short_name = j.name.split('|')[-1]
            # Handle potential short name collisions by storing list
            if short_name not in joint_map_short:
                joint_map_short[short_name] = []
            joint_map_short[short_name].append(j)

        # Find all root joints (USD supports multiple root hierarchies)
        roots = [j for j in joint_data if j.parent_name is None]
        if not roots:
            raise ValueError("No root joint found")

        # Build paths recursively for each root hierarchy
        paths = []
        for root in roots:
            self._build_joint_paths_recursive(root, "", paths, joint_map_full, joint_map_short)

        return paths

    def _build_joint_paths_recursive(
        self,
        joint: JointData,
        parent_path: str,
        paths: List[str],
        joint_map_full: Dict[str, JointData],
        joint_map_short: Dict[str, List[JointData]]
    ):
        """Recursive helper for building joint paths"""
        # Extract short name from full DAG path for USD token
        # Maya full path: |Group|MotionSystem|FKAnkle_L -> short: FKAnkle_L
        joint_short_name = joint.name.split('|')[-1]

        # Build current path
        if parent_path:
            current_path = f"{parent_path}/{joint_short_name}"
        else:
            current_path = joint_short_name

        paths.append(current_path)

        # Process children (stored as short names)
        for child_short_name in joint.children:
            # Find child by short name, then match to parent
            if child_short_name in joint_map_short:
                # Get candidates with this short name
                candidates = joint_map_short[child_short_name]

                # Find the one whose parent matches current joint
                for candidate in candidates:
                    if candidate.parent_name == joint.name:  # Full path match
                        self._build_joint_paths_recursive(
                            candidate, current_path, paths, joint_map_full, joint_map_short
                        )
                        break

    def _maya_matrix_to_gf_matrix(self, maya_matrix: List[float]) -> Any:
        """
        Convert Maya 4x4 matrix (row-major) to USD Gf.Matrix4d

        Clean Code: Explicit conversion function
        """
        if len(maya_matrix) != 16:
            raise ValueError(f"Expected 16 floats for matrix, got {len(maya_matrix)}")

        # Maya is row-major, USD Gf.Matrix4d is row-major too
        # So we can directly construct
        return Gf.Matrix4d(
            maya_matrix[0], maya_matrix[1], maya_matrix[2], maya_matrix[3],
            maya_matrix[4], maya_matrix[5], maya_matrix[6], maya_matrix[7],
            maya_matrix[8], maya_matrix[9], maya_matrix[10], maya_matrix[11],
            maya_matrix[12], maya_matrix[13], maya_matrix[14], maya_matrix[15]
        )

    def _convert_weights_to_usd_format(
        self,
        weights: Dict[int, List[tuple]],
        max_influences: int
    ) -> Tuple[List[int], List[float]]:
        """
        Convert weight dictionary to USD flat arrays

        Args:
            weights: {vertex_idx: [(joint_idx, weight), ...]}
            max_influences: Pad to this many influences per vertex

        Returns:
            (joint_indices, joint_weights) - Flat arrays

        Clean Code: Format conversion for USD
        """
        # Get vertex count (assumes vertices are 0 to N-1)
        if not weights:
            return [], []

        vertex_count = max(weights.keys()) + 1

        # Build flat arrays
        joint_indices = []
        joint_weights = []

        for vertex_idx in range(vertex_count):
            vertex_weights = weights.get(vertex_idx, [])

            # Pad to max_influences
            for i in range(max_influences):
                if i < len(vertex_weights):
                    joint_idx, weight = vertex_weights[i]
                    joint_indices.append(joint_idx)
                    joint_weights.append(weight)
                else:
                    # Padding with zero influence
                    joint_indices.append(0)
                    joint_weights.append(0.0)

        return joint_indices, joint_weights

    def _has_cycle(self, joint_data: List[JointData]) -> bool:
        """
        Check for cycles in joint hierarchy

        Clean Code: Cycle detection utility
        """
        # Build parent mapping
        parent_map = {j.name: j.parent_name for j in joint_data}

        # Check each joint for cycles
        for joint in joint_data:
            visited = set()
            current = joint.name

            while current is not None:
                if current in visited:
                    return True  # Cycle detected

                visited.add(current)
                current = parent_map.get(current)

        return False
