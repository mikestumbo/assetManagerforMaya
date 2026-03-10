# -*- coding: utf-8 -*-
"""
Maya Skin Cluster Builder Implementation
Creates Maya skinCluster nodes from USD skin weight data

Author: Mike Stumbo
Version: 1.5.0
Date: November 2025
"""

import logging
from typing import Optional, List, Dict, Tuple, Any

# Conditional Maya import
try:
    import maya.cmds as cmds  # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    cmds: Any = None  # type: ignore

logger = logging.getLogger(__name__)


class MayaSkinClusterBuilderImpl:
    """
    Maya Skin Cluster Builder

    Creates Maya skinCluster nodes from USD skin weight data.
    Handles joint mapping, weight application, and normalization.

    Clean Code: Single Responsibility - Build Maya skinClusters
    """

    def __init__(self):
        """Initialize skin cluster builder"""
        self.logger = logging.getLogger(__name__)

        if not MAYA_AVAILABLE:
            self.logger.error("Maya cmds not available!")

    def create_skin_cluster(
        self,
        mesh_name: str,
        joint_names: List[str],
        skin_weight_data: Any,  # UsdSkinWeightData
        skincluster_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Create Maya skinCluster and apply weights

        Args:
            mesh_name: Maya mesh name (with namespace)
            joint_names: List of Maya joint names (short names from USD)
            skin_weight_data: UsdSkinWeightData with per-vertex weights
            skincluster_name: Optional name for skinCluster

        Returns:
            skinCluster node name or None if failed
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available")
            return None

        try:
            # Validate mesh exists
            if not cmds.objExists(mesh_name):
                self.logger.error(f"Mesh not found: {mesh_name}")
                return None

            # Ensure we have the transform node, not shape
            mesh_transform = self._get_transform_node(mesh_name)
            if not mesh_transform:
                self.logger.error(f"Could not find transform for: {mesh_name}")
                return None

            # CRITICAL FIX: Build vertex position mapping BEFORE applying geomBindTransform
            # USD vertex positions are in pre-transform space, so transform them first if needed
            usd_to_maya_vertex_map = None
            if skin_weight_data.vertex_positions:
                self.logger.info("🔍 Building vertex position mapping...")

                # If geomBindTransform exists, transform USD positions to match Maya space
                positions_to_match = skin_weight_data.vertex_positions
                if skin_weight_data.geom_bind_transform:
                    positions_to_match = self._transform_vertex_positions(
                        skin_weight_data.vertex_positions,
                        skin_weight_data.geom_bind_transform
                    )
                    self.logger.info("   Transformed USD positions by geomBindTransform")

                usd_to_maya_vertex_map = self._build_vertex_position_map(
                    mesh_transform,
                    positions_to_match
                )

                if usd_to_maya_vertex_map:
                    self.logger.info(f"[OK] Mapped {len(usd_to_maya_vertex_map)} vertices by position")
                else:
                    self.logger.warning("[WARNING] Position mapping failed, using index-based (may be incorrect!)")

            # Apply geomBindTransform to mesh for correct bind pose
            if skin_weight_data.geom_bind_transform:
                self._apply_geom_bind_transform(mesh_transform, skin_weight_data.geom_bind_transform)

            # Find joints in scene (handle namespace)
            maya_joints = self._find_maya_joints(joint_names)
            if not maya_joints:
                self.logger.error(f"No joints found for skin cluster on {mesh_name}")
                return None

            self.logger.info(f"Creating skinCluster: {mesh_transform} → {len(maya_joints)} joints")

            # Create skinCluster
            skin_cluster = self._create_maya_skincluster(
                mesh_transform,
                maya_joints,
                skincluster_name
            )

            if not skin_cluster:
                return None

            # Apply weights from USD data
            success = self._apply_weights(
                skin_cluster,
                mesh_transform,
                maya_joints,
                skin_weight_data,
                usd_to_maya_vertex_map
            )

            if not success:
                self.logger.warning(f"Weight application had issues on {mesh_transform}")
                # Don't return None - skinCluster was created, weights might be partial

            self.logger.info(f"[OK] Created skinCluster: {skin_cluster}")
            return skin_cluster

        except Exception as e:
            self.logger.error(f"Failed to create skin cluster on {mesh_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_maya_joints(self, joint_short_names: List[str]) -> List[str]:
        """
        Find Maya joints matching USD joint names

        Handles namespaces - searches for joints by short name.

        Args:
            joint_short_names: List of short joint names from USD (may include namespace like "test:Root")

        Returns:
            List of full Maya joint paths
        """
        if not MAYA_AVAILABLE:
            return []

        maya_joints = []

        try:
            # Get all joints in scene
            all_joints = cmds.ls(type='joint', long=True) or []

            # Build mapping of BOTH short name (no namespace) AND short name (with namespace) → full path
            # This handles both "Root" and "test:Root" lookups
            joint_map = {}
            for joint_path in all_joints:
                dag_short_name = joint_path.split('|')[-1]  # Get last part of DAG path
                short_name_no_ns = dag_short_name.split(':')[-1]  # Remove namespace: "test:Root" -> "Root"

                # Map both versions
                if dag_short_name not in joint_map:
                    joint_map[dag_short_name] = []
                joint_map[dag_short_name].append(joint_path)

                if short_name_no_ns not in joint_map:
                    joint_map[short_name_no_ns] = []
                joint_map[short_name_no_ns].append(joint_path)

            # Find matching joints
            for search_name in joint_short_names:
                # Strip namespace from search name to get base name
                base_name = search_name.split(':')[-1]

                # Try to find:
                # 1. Exact match with namespace (search_name = "test:Root")
                # 2. Match without namespace (base_name = "Root")
                if search_name in joint_map:
                    maya_joints.append(joint_map[search_name][0])
                elif base_name in joint_map:
                    maya_joints.append(joint_map[base_name][0])
                else:
                    self.logger.warning(f"Joint not found in Maya: {search_name}")

            self.logger.debug(f"Mapped {len(maya_joints)}/{len(joint_short_names)} joints")

        except Exception as e:
            self.logger.error(f"Failed to find Maya joints: {e}")

        return maya_joints

    def _get_transform_node(self, node_name: str) -> Optional[str]:
        """
        Get transform node from mesh name (handles shape vs transform)

        Args:
            node_name: Node name (could be shape or transform)

        Returns:
            Transform node name or None
        """
        if not MAYA_AVAILABLE:
            return None

        try:
            # Check if it's already a transform
            if cmds.nodeType(node_name) == 'transform':
                return node_name

            # If it's a shape, get its transform parent
            if cmds.nodeType(node_name) == 'mesh':
                parents = cmds.listRelatives(node_name, parent=True, fullPath=True)
                if parents:
                    return parents[0]

            # Try to find shape node and get transform
            shapes = cmds.listRelatives(node_name, shapes=True, fullPath=True)
            if shapes:
                # node_name is already a transform with shapes
                return node_name

            self.logger.warning(f"Could not determine transform for: {node_name}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to get transform node: {e}")
            return None

    def _apply_geom_bind_transform(self, mesh_transform: str, geom_bind_matrix: List[float]) -> None:
        """
        Apply geomBindTransform to mesh before skinning

        This positions the mesh at its bind-time location, which is critical
        for correct skinCluster bindPreMatrix calculation.

        Args:
            mesh_transform: Maya mesh transform node
            geom_bind_matrix: 4x4 matrix as flat list of 16 floats
        """
        if not MAYA_AVAILABLE:
            return

        try:
            # USD matrices are row-major, Maya expects column-major
            # Convert by transposing: reshape to 4x4, transpose, flatten
            import maya.api.OpenMaya as om2  # type: ignore

            # Create MMatrix from flat list (USD is row-major)
            # Maya MMatrix constructor expects 16 values in row-major order too
            _ = om2.MMatrix(geom_bind_matrix)

            # Apply to Maya transform
            # Convert to Maya's xform command format (row-major, 16 values)
            cmds.xform(mesh_transform, matrix=geom_bind_matrix, worldSpace=True)

            self.logger.info(f"Applied geomBindTransform to {mesh_transform}")

        except Exception as e:
            self.logger.warning(f"Could not apply geomBindTransform to {mesh_transform}: {e}")

    def _create_maya_skincluster(
        self,
        mesh_name: str,
        joint_names: List[str],
        skincluster_name: Optional[str]
    ) -> Optional[str]:
        """
        Create Maya skinCluster node

        Args:
            mesh_name: Mesh to skin
            joint_names: Joints to bind to
            skincluster_name: Optional name

        Returns:
            skinCluster node name or None
        """
        if not MAYA_AVAILABLE:
            return None

        try:
            # Create skinCluster with all joints
            # Maya will capture current joint transforms as bind pose
            # We'll fix the bind matrices afterwards
            skin_cluster_nodes = cmds.skinCluster(
                joint_names,
                mesh_name,
                toSelectedBones=True,
                bindMethod=0,  # Closest distance
                skinMethod=0,  # Classic linear
                normalizeWeights=1,  # Interactive normalize
                maximumInfluences=4,  # Default max influences
                obeyMaxInfluences=False,  # Allow more if needed
                name=skincluster_name
            )

            # skinCluster returns list, get first element
            skin_cluster = skin_cluster_nodes[0] if skin_cluster_nodes else None

            if not skin_cluster:
                self.logger.error("skinCluster creation returned None")
                return None

            # CRITICAL FIX: Use Maya API to force DAG hierarchy evaluation and restore bind pose
            self._force_bind_pose_via_api(skin_cluster, joint_names)

            return skin_cluster

        except Exception as e:
            self.logger.error(f"Failed to create Maya skinCluster: {e}")
            return None

    def _fix_bind_matrices_from_dagpose(self, skin_cluster: str, joint_names: List[str]) -> None:
        """
        Fix skinCluster bind matrices by reading from dagPose node's stored worldMatrix attributes

        This works around the "Hierarchy must be specified or selected" error by directly
        reading the matrix data from the dagPose node attributes instead of calling restore().

        Args:
            skin_cluster: skinCluster node name
            joint_names: List of joint names
        """
        if not MAYA_AVAILABLE:
            return

        try:
            # Find bind pose dagPose node
            bind_poses = cmds.ls(type='dagPose')
            bind_pose_node = None

            for pose in bind_poses:
                is_bind = cmds.dagPose(pose, query=True, bindPose=True)
                if is_bind:
                    bind_pose_node = pose
                    break

            if not bind_pose_node:
                self.logger.warning("No bind pose found - skinning may not work correctly")
                return

            # Get influence list from skinCluster
            influences = cmds.skinCluster(skin_cluster, query=True, influence=True)

            # Import Maya API for matrix math
            import maya.api.OpenMaya as om2  # type: ignore

            matrices_fixed = 0
            for idx, joint_name in enumerate(influences):
                try:
                    # Read worldMatrix directly from dagPose node's attribute
                    # Each joint has a worldMatrix array attribute in the dagPose
                    _ = cmds.listAttr(bind_pose_node, multi=True) or []

                    # Find which index this joint is in the dagPose
                    members = cmds.dagPose(bind_pose_node, query=True, members=True) or []

                    # Match joint to dagPose member index
                    joint_short_name = joint_name.split(':')[-1].split('|')[-1]
                    dag_pose_idx = None

                    for member_idx, member in enumerate(members):
                        member_short = member.split(':')[-1].split('|')[-1]
                        if member_short == joint_short_name:
                            dag_pose_idx = member_idx
                            break

                    if dag_pose_idx is not None:
                        # Read the worldMatrix from dagPose
                        matrix_attr = f"{bind_pose_node}.worldMatrix[{dag_pose_idx}]"
                        if cmds.objExists(matrix_attr):
                            world_matrix = cmds.getAttr(matrix_attr)

                            # Invert to get bindPreMatrix
                            m_matrix = om2.MMatrix(world_matrix)
                            m_inverse = m_matrix.inverse()

                            # Set skinCluster's bindPreMatrix
                            bind_attr = f"{skin_cluster}.bindPreMatrix[{idx}]"
                            cmds.setAttr(bind_attr, list(m_inverse), type="matrix")
                            matrices_fixed += 1

                except Exception:
                    continue

            if matrices_fixed > 0:
                self.logger.info(f"[OK] Fixed {matrices_fixed}/{len(influences)} bind matrices from dagPose")
            else:
                self.logger.warning("[WARNING] Could not fix any bind matrices")

        except Exception as e:
            self.logger.warning(f"Failed to fix bind matrices: {e}")

    def _force_bind_pose_via_api(self, skin_cluster: str, joint_names: List[str]) -> None:
        """
        Set bindPreMatrix directly from current joint transforms

        This COMPLETELY BYPASSES dagPose by capturing joint world transforms
        at the moment of skinCluster creation and setting bindPreMatrix directly.

        Since USD import positions joints in bind pose, we just need to:
        1. Get each joint's current worldMatrix
        2. Invert it to get bindPreMatrix
        3. Set it on the skinCluster

        Args:
            skin_cluster: skinCluster node name
            joint_names: List of joint names
        """
        if not MAYA_AVAILABLE:
            return

        try:
            import maya.api.OpenMaya as om2  # type: ignore

            # Get influence list from skinCluster
            influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
            if not influences:
                self.logger.warning("No influences found in skinCluster")
                return

            matrices_set = 0

            for idx, joint_name in enumerate(influences):
                try:
                    # Get the joint's current world matrix
                    # Since joints are imported in bind pose from USD, this IS the bind pose
                    world_matrix = cmds.xform(joint_name, query=True, worldSpace=True, matrix=True)

                    # Convert to MMatrix and invert
                    m_matrix = om2.MMatrix(world_matrix)
                    m_inverse = m_matrix.inverse()

                    # Set bindPreMatrix on skinCluster
                    bind_attr = f"{skin_cluster}.bindPreMatrix[{idx}]"
                    cmds.setAttr(bind_attr, list(m_inverse), type="matrix")
                    matrices_set += 1

                except Exception as joint_error:
                    self.logger.warning(f"Could not set bindPreMatrix for {joint_name}: {joint_error}")
                    continue

            if matrices_set == len(influences):
                self.logger.info(
                    f"[OK] Successfully set {matrices_set}/{len(influences)} bindPreMatrix values"
                )
            elif matrices_set > 0:
                self.logger.warning(f"[WARNING] Partially set {matrices_set}/{len(influences)} bindPreMatrix values")
            else:
                self.logger.warning("[ERROR] Failed to set any bindPreMatrix values")

        except Exception as e:
            self.logger.warning(f"Failed to set bindPreMatrix: {e}")

    def _restore_bind_pose_for_skincluster(self, joint_names: List[str]) -> None:
        """
        Restore bind pose BEFORE creating skinCluster

        This ensures joints are in the correct pose when Maya captures bind matrices.
        Uses MEL command to properly restore the pose.

        Args:
            joint_names: List of joint names that will be in the skinCluster
        """
        if not MAYA_AVAILABLE:
            return

        try:
            # Find the bind pose dagPose node
            bind_poses = cmds.ls(type='dagPose')
            bind_pose_node = None

            for pose in bind_poses:
                is_bind = cmds.dagPose(pose, query=True, bindPose=True)
                if is_bind:
                    bind_pose_node = pose
                    break

            if not bind_pose_node:
                self.logger.warning("No bind pose found - using current joint poses")
                return

            # Use MEL to restore - it handles hierarchy correctly
            import maya.mel as mel  # type: ignore
            mel_command = f'dagPose -restore -g -bindPose {bind_pose_node};'
            mel.eval(mel_command)

            self.logger.info(f"[OK] Restored bind pose: {bind_pose_node}")

        except Exception as e:
            self.logger.warning(f"Failed to restore bind pose: {e}")

    def _copy_bind_pose_to_skincluster(self, skin_cluster: str, joint_names: List[str]) -> None:
        """
        Copy bind pose matrices from dagPose to skinCluster bindPreMatrix attributes

        This fixes the issue where joints aren't in bind pose when skinCluster is created.
        We manually set the inverse bind matrices from the dagPose node.

        Args:
            skin_cluster: skinCluster node name
            joint_names: List of joint names in the skinCluster
        """
        if not MAYA_AVAILABLE:
            return

        try:
            # Find the bind pose dagPose node
            bind_poses = cmds.ls(type='dagPose')
            bind_pose_node = None

            for pose in bind_poses:
                is_bind = cmds.dagPose(pose, query=True, bindPose=True)
                if is_bind:
                    bind_pose_node = pose
                    break

            if not bind_pose_node:
                self.logger.warning("No bind pose found - skinCluster may not deform correctly")
                return

            self.logger.info(f"Copying bind matrices from {bind_pose_node} to {skin_cluster}")

            # Get the influence list from skinCluster
            influences = cmds.skinCluster(skin_cluster, query=True, influence=True)

            # Import Maya API for matrix operations
            import maya.api.OpenMaya as om2  # type: ignore

            matrices_copied = 0
            for idx, joint_name in enumerate(influences):
                try:
                    # Get the joint's current world matrix (which should be in bind pose)
                    # by querying it directly from the joint
                    joint_world_matrix = cmds.xform(joint_name, query=True, worldSpace=True, matrix=True)

                    # Convert to MMatrix and invert
                    m_matrix = om2.MMatrix(joint_world_matrix)
                    m_inverse = m_matrix.inverse()

                    # Set the bindPreMatrix attribute
                    bind_attr = f"{skin_cluster}.bindPreMatrix[{idx}]"
                    cmds.setAttr(bind_attr, list(m_inverse), type="matrix")
                    matrices_copied += 1

                except Exception as joint_error:
                    self.logger.warning(f"Failed to copy bind matrix for {joint_name}: {joint_error}")
                    continue

            if matrices_copied > 0:
                self.logger.info(f"[OK] Copied {matrices_copied} bind matrices to skinCluster")
            else:
                self.logger.warning("[WARNING] No bind matrices copied - deformation may not work")

        except Exception as e:
            self.logger.warning(f"Failed to copy bind pose matrices: {e}")

    def _transform_vertex_positions(
        self,
        vertex_positions: List[Tuple[float, float, float]],
        transform_matrix: List[float]
    ) -> List[Tuple[float, float, float]]:
        """
        Transform vertex positions by a 4x4 matrix

        Args:
            vertex_positions: List of (x,y,z) positions
            transform_matrix: 4x4 matrix as flat list of 16 floats

        Returns:
            Transformed positions
        """
        if not MAYA_AVAILABLE:
            return vertex_positions

        try:
            import maya.api.OpenMaya as om2  # type: ignore

            # Create MMatrix from flat list
            m_matrix = om2.MMatrix(transform_matrix)

            transformed_positions = []
            for pos in vertex_positions:
                # Create MPoint from position
                point = om2.MPoint(pos[0], pos[1], pos[2])

                # Transform point
                transformed_point = point * m_matrix

                # Convert back to tuple
                transformed_positions.append((
                    float(transformed_point.x),
                    float(transformed_point.y),
                    float(transformed_point.z)
                ))

            return transformed_positions

        except Exception as e:
            self.logger.warning(f"Could not transform vertex positions: {e}")
            return vertex_positions

    def _build_vertex_position_map(
        self,
        mesh_name: str,
        usd_vertex_positions: List[Tuple[float, float, float]]
    ) -> Optional[Dict[int, int]]:
        """
        Build mapping from USD vertex indices to Maya vertex indices by matching positions

        CRITICAL FIX: Maya's USD import may reorder vertices. This function matches
        them by 3D position to ensure weights are applied correctly.

        PERFORMANCE: Uses Maya API batch operations instead of per-vertex cmds calls.

        Args:
            mesh_name: Maya mesh name
            usd_vertex_positions: List of (x,y,z) positions from USD

        Returns:
            Dict mapping USD vertex index → Maya vertex index, or None if failed
        """
        if not MAYA_AVAILABLE:
            return None

        try:
            import maya.api.OpenMaya as om2  # type: ignore

            # Get Maya mesh using API for FAST vertex position access
            sel_list = om2.MSelectionList()
            sel_list.add(mesh_name)
            dag_path = sel_list.getDagPath(0)

            # Get mesh function set
            mesh_fn = om2.MFnMesh(dag_path)
            maya_points = mesh_fn.getPoints(om2.MSpace.kObject)  # Object space

            maya_vertex_count = len(maya_points)

            if maya_vertex_count != len(usd_vertex_positions):
                self.logger.error(f"Vertex count mismatch: Maya={maya_vertex_count}, USD={len(usd_vertex_positions)}")
                return None

            self.logger.info(f"   Matching {maya_vertex_count} vertices by position (API batch)...")

            # Build spatial hash of Maya vertices for faster lookup
            tolerance = 0.0001  # Position matching tolerance
            maya_position_map = {}

            for maya_idx, pt in enumerate(maya_points):
                key = (
                    round(pt.x / tolerance),
                    round(pt.y / tolerance),
                    round(pt.z / tolerance)
                )
                maya_position_map[key] = maya_idx

            # Match USD vertices to Maya vertices
            usd_to_maya_map = {}
            unmatched_count = 0

            for usd_idx, usd_pos in enumerate(usd_vertex_positions):
                key = (
                    round(usd_pos[0] / tolerance),
                    round(usd_pos[1] / tolerance),
                    round(usd_pos[2] / tolerance)
                )

                if key in maya_position_map:
                    maya_idx = maya_position_map[key]
                    usd_to_maya_map[usd_idx] = maya_idx
                else:
                    unmatched_count += 1
                    if unmatched_count < 10:  # Limit warnings
                        self.logger.warning(f"Could not match USD vertex {usd_idx} at {usd_pos}")

            match_percentage = len(usd_to_maya_map) / len(usd_vertex_positions) * 100
            self.logger.info(
                f"   Matched {len(usd_to_maya_map)}/{len(usd_vertex_positions)} "
                f"vertices ({match_percentage:.1f}%)"
            )

            if unmatched_count > 0:
                self.logger.warning(
                    f"[WARNING] {unmatched_count}/{len(usd_vertex_positions)} "
                    "vertices could not be matched"
                )

            if len(usd_to_maya_map) < len(usd_vertex_positions) * 0.9:  # Less than 90% matched
                self.logger.error(f"[ERROR] Only {match_percentage:.1f}% matched - position mapping failed")
                return None

            return usd_to_maya_map

        except Exception as e:
            self.logger.error(f"Failed to build vertex position map: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _apply_weights(
        self,
        skin_cluster: str,
        mesh_name: str,
        maya_joints: List[str],
        weight_data: Any,  # UsdSkinWeightData
        usd_to_maya_vertex_map: Optional[Dict[int, int]] = None
    ) -> bool:
        """
        Apply skin weights from USD data to Maya skinCluster

        PERFORMANCE FIX: Uses Maya API batch operations instead of per-vertex skinPercent.
        For 50K vertices, this reduces time from hours to seconds.

        Args:
            skin_cluster: skinCluster node name
            mesh_name: Mesh name
            maya_joints: List of Maya joint paths
            weight_data: UsdSkinWeightData
            usd_to_maya_vertex_map: Pre-computed mapping from USD to Maya vertex indices

        Returns:
            True if successful
        """
        if not MAYA_AVAILABLE:
            return False

        try:
            self.logger.info(f"Applying weights to {weight_data.vertex_count} vertices (batch API)...")

            # Use pre-computed vertex mapping (built before geomBindTransform)
            if usd_to_maya_vertex_map:
                self.logger.info(f"Using pre-computed vertex mapping ({len(usd_to_maya_vertex_map)} vertices)")
            else:
                self.logger.warning("[WARNING] No vertex mapping available, using index-based matching")
                self.logger.warning("   This may cause incorrect skinning if Maya reordered vertices!")

            # Diagnostic: Check first few vertices
            self.logger.info("📝 Sample USD weight data (first 3 vertices):")
            for v_idx in range(min(3, weight_data.vertex_count)):
                usd_joint_indices = weight_data.joint_indices[v_idx]
                usd_weights = weight_data.joint_weights[v_idx]
                non_zero = [
                    (maya_joints[j], w) for j, w in zip(usd_joint_indices, usd_weights)
                    if w > 0.0001 and j < len(maya_joints)
                ]
                maya_vert_idx = usd_to_maya_vertex_map[v_idx] if usd_to_maya_vertex_map else v_idx
                self.logger.info(f"   USD vtx[{v_idx}] → Maya vtx[{maya_vert_idx}]: {non_zero[:3]}")

            # Try fast Maya API method first, fall back to cmds if needed
            try:
                return self._apply_weights_api(
                    skin_cluster, mesh_name, maya_joints, weight_data, usd_to_maya_vertex_map
                )
            except Exception as api_error:
                self.logger.error(f"[ERROR] API weight method failed: {api_error}")
                import traceback
                traceback.print_exc()
                self.logger.error("[ERROR] Cannot fall back to per-vertex method (too slow for large meshes)")
                self.logger.error("   Please report this error to the developer")
                return False

        except Exception as e:
            self.logger.error(f"Failed to apply weights: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _apply_weights_api(
        self,
        skin_cluster: str,
        mesh_name: str,
        maya_joints: List[str],
        weight_data: Any,
        usd_to_maya_vertex_map: Optional[Dict[int, int]]
    ) -> bool:
        """
        Apply weights using Maya API (MFnSkinCluster) - FASTEST method.
        Applies all weights in a single API call.
        """
        import maya.api.OpenMaya as om2  # type: ignore
        import maya.api.OpenMayaAnim as oma2  # type: ignore  # MFnSkinCluster is here!

        self.logger.info("   Using Maya API batch weight application...")

        # Get skin cluster function set (from OpenMayaAnim, not OpenMaya!)
        sel_list = om2.MSelectionList()
        sel_list.add(skin_cluster)
        skin_obj = sel_list.getDependNode(0)
        skin_fn = oma2.MFnSkinCluster(skin_obj)  # Use oma2 not om2!

        # Get the mesh dag path
        sel_list.clear()
        sel_list.add(mesh_name)
        mesh_dag = sel_list.getDagPath(0)

        # Get influence (joint) indices
        influence_dag_paths = skin_fn.influenceObjects()
        num_influences = len(influence_dag_paths)

        # Build mapping from maya_joints list to influence indices
        joint_to_influence_idx = {}
        for inf_idx, dag_path in enumerate(influence_dag_paths):
            joint_name = dag_path.fullPathName()
            short_name = dag_path.partialPathName()
            joint_to_influence_idx[joint_name] = inf_idx
            joint_to_influence_idx[short_name] = inf_idx
            # Also map by final name component
            final_name = short_name.split('|')[-1].split(':')[-1]
            if final_name not in joint_to_influence_idx:
                joint_to_influence_idx[final_name] = inf_idx

        # Map our maya_joints list indices to skin cluster influence indices
        joint_list_to_influence = []
        for joint in maya_joints:
            short = joint.split('|')[-1].split(':')[-1]
            if joint in joint_to_influence_idx:
                joint_list_to_influence.append(joint_to_influence_idx[joint])
            elif short in joint_to_influence_idx:
                joint_list_to_influence.append(joint_to_influence_idx[short])
            else:
                joint_list_to_influence.append(-1)  # Not found

        # Get vertex count
        mesh_fn = om2.MFnMesh(mesh_dag)
        maya_vertex_count = mesh_fn.numVertices

        # Build weight array: [vert0_inf0, vert0_inf1, ..., vert1_inf0, vert1_inf1, ...]
        # This is a flat array: num_vertices * num_influences
        weights = om2.MDoubleArray(maya_vertex_count * num_influences, 0.0)

        vertices_processed = 0
        vertices_failed = 0

        for usd_v_idx in range(weight_data.vertex_count):
            # Map USD vertex to Maya vertex
            maya_v_idx = usd_to_maya_vertex_map[usd_v_idx] if usd_to_maya_vertex_map else usd_v_idx

            if maya_v_idx >= maya_vertex_count:
                vertices_failed += 1
                continue

            # Get USD weights for this vertex
            usd_joint_indices = weight_data.joint_indices[usd_v_idx]
            usd_weights = weight_data.joint_weights[usd_v_idx]

            # Base index in flat weight array
            base_idx = maya_v_idx * num_influences

            weight_sum = 0.0
            for joint_idx, weight in zip(usd_joint_indices, usd_weights):
                if weight > 0.0001 and joint_idx < len(joint_list_to_influence):
                    inf_idx = joint_list_to_influence[joint_idx]
                    if inf_idx >= 0 and inf_idx < num_influences:
                        weights[base_idx + inf_idx] = weight
                        weight_sum += weight

            if weight_sum > 0:
                vertices_processed += 1
            else:
                vertices_failed += 1

        # Create influence indices array (all influences)
        influence_indices = om2.MIntArray(range(num_influences))

        # Create component for all vertices
        single_idx_component = om2.MFnSingleIndexedComponent()
        vertex_comp = single_idx_component.create(om2.MFn.kMeshVertComponent)
        single_idx_component.addElements(list(range(maya_vertex_count)))

        # Apply all weights in ONE call!
        self.logger.info(f"   Setting weights for {maya_vertex_count} vertices, {num_influences} influences...")
        skin_fn.setWeights(mesh_dag, vertex_comp, influence_indices, weights, normalize=True)

        success_rate = vertices_processed / weight_data.vertex_count if weight_data.vertex_count > 0 else 0
        self.logger.info(
            f"[OK] Weight application: {vertices_processed}/{weight_data.vertex_count} "
            f"vertices ({success_rate*100:.1f}%)"
        )

        if vertices_failed > 0:
            self.logger.warning(f"[WARNING] {vertices_failed} vertices had weight application issues")

        return vertices_failed == 0

    def _apply_weights_batch_cmds(
        self,
        skin_cluster: str,
        mesh_name: str,
        maya_joints: List[str],
        weight_data: Any,
        usd_to_maya_vertex_map: Optional[Dict[int, int]]
    ) -> bool:
        """
        Apply weights using cmds.skinPercent in batches - fallback method.
        Groups vertices by similar weight patterns to reduce cmds calls.
        """
        self.logger.info("   Using batch cmds weight application...")

        vertices_processed = 0
        vertices_failed = 0

        # Process in batches of 1000 vertices for progress feedback
        batch_size = 1000
        total_batches = (weight_data.vertex_count + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, weight_data.vertex_count)

            if batch_idx % 10 == 0:
                self.logger.info(f"   Processing batch {batch_idx+1}/{total_batches}...")

            for usd_v_idx in range(start_idx, end_idx):
                try:
                    maya_v_idx = usd_to_maya_vertex_map[usd_v_idx] if usd_to_maya_vertex_map else usd_v_idx

                    usd_joint_indices = weight_data.joint_indices[usd_v_idx]
                    usd_weights = weight_data.joint_weights[usd_v_idx]

                    transform_values = []
                    for joint_idx, weight in zip(usd_joint_indices, usd_weights):
                        if weight > 0.0001 and joint_idx < len(maya_joints):
                            transform_values.append((maya_joints[joint_idx], weight))

                    if not transform_values:
                        vertices_failed += 1
                        continue

                    vertex_name = f"{mesh_name}.vtx[{maya_v_idx}]"
                    cmds.skinPercent(
                        skin_cluster,
                        vertex_name,
                        transformValue=transform_values,
                        normalize=True
                    )
                    vertices_processed += 1

                except Exception:
                    vertices_failed += 1

        success_rate = vertices_processed / weight_data.vertex_count if weight_data.vertex_count > 0 else 0
        self.logger.info(
            f"Weight application: {vertices_processed}/{weight_data.vertex_count} "
            f"vertices ({success_rate*100:.1f}%)"
        )

        if vertices_failed > 0:
            self.logger.warning(f"[WARNING] {vertices_failed} vertices had weight application issues")

        return vertices_failed == 0

    def validate_joint_mapping(
        self,
        usd_joint_names: List[str],
        maya_joint_names: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate USD joints can be mapped to Maya joints

        Args:
            usd_joint_names: Joint names from USD
            maya_joint_names: Available Maya joints

        Returns:
            (is_valid, missing_joints) - List of joints not found
        """
        maya_short_names = set()
        for joint in maya_joint_names:
            short_name = joint.split('|')[-1].split(':')[-1]
            maya_short_names.add(short_name)

        missing_joints = []
        for usd_joint in usd_joint_names:
            if usd_joint not in maya_short_names:
                missing_joints.append(usd_joint)

        is_valid = len(missing_joints) == 0
        return is_valid, missing_joints
