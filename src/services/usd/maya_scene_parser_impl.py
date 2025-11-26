"""Maya Scene Parser Implementation

Clean Code: Extract geometry, materials, and rigging data from Maya scenes
Disney/Pixar Critical: Accurate data extraction for USD export pipeline
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

# Import interfaces and data models
from src.core.interfaces.maya_scene_parser import (
    IMayaSceneParser,
    MeshData,
    MaterialData,
    JointData,
    SkinClusterData,
    NurbsCurveData,  # NEW: NURBS curve support!
    RigConnectionData,  # NEW: Rig connection support!
    ConstraintData,     # NEW: Constraint support!
    SetDrivenKeyData,   # NEW: Set-driven key support!
    MayaSceneData
)

# Conditional Maya import (pattern from thumbnail_service_impl.py)
try:
    import maya.cmds as cmds  # type: ignore
    import maya.api.OpenMaya as om  # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    # Create stub for type checking
    cmds: Any = None  # type: ignore
    om: Any = None  # type: ignore


class MayaSceneParserImpl(IMayaSceneParser):
    """Maya Scene Parser - Extract all scene data for USD export

    Clean Code: Single Responsibility - Parse Maya scenes
    SOLID: Dependency Inversion - Implements IMayaSceneParser interface
    """

    def __init__(self):
        """Initialize Maya scene parser"""
        self.logger = logging.getLogger(__name__)

        if not MAYA_AVAILABLE:
            self.logger.warning("Maya not available - parser will have limited functionality")

    def parse_maya_file(self, maya_file: Optional[Path], options: Optional[Dict[str, Any]] = None) -> MayaSceneData:
        """Parse complete Maya file and extract all data

        Clean Code: Main entry point for file parsing
        Disney/Pixar Critical: Must extract all data accurately

        Args:
            maya_file: Path to .ma or .mb file, or None to parse current scene
            options: Optional parsing options

        Returns:
            Complete scene data

        Raises:
            RuntimeError: If parsing fails
        """
        if not MAYA_AVAILABLE:
            raise RuntimeError("Maya not available - cannot parse file")

        # If no file specified, parse current scene
        if maya_file is None:
            self.logger.info("Parsing current Maya scene")
            scene_data = self._parse_current_scene(source_file=None)
            if not scene_data:
                raise RuntimeError("Failed to extract scene data from current scene")
            return scene_data

        is_valid, error_msg = self.validate_maya_file(maya_file)
        if not is_valid:
            raise RuntimeError(f"Invalid Maya file: {error_msg}")

        if cmds is None:
            raise RuntimeError("Maya cmds module not available - cannot parse file")

        try:
            # Open Maya file in new scene
            cmds.file(str(maya_file), open=True, force=True)
            self.logger.info(f"Opened Maya file: {maya_file}")

            # Parse all scene data
            scene_data = self._parse_current_scene(source_file=maya_file)

            if not scene_data:
                raise RuntimeError(f"Failed to extract scene data from: {maya_file}")

            return scene_data

        except Exception as e:
            self.logger.error(f"Failed to parse Maya file {maya_file}: {e}")
            raise RuntimeError(f"Failed to parse Maya file: {e}") from e

    def parse_selected_objects(self, object_names: Optional[List[str]] = None) -> MayaSceneData:
        """Parse currently selected objects in Maya session

        Clean Code: Extract data from active selection
        Use Case: Export selected assets only

        Args:
            object_names: Optional list of specific object names to parse; if None, uses current selection

        Returns:
            Scene data for selected or specified objects
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available - cannot parse selection")
            raise RuntimeError("Maya not available - cannot parse selection")

        if cmds is None:
            self.logger.error("Maya cmds module not available - cannot parse selection")
            raise RuntimeError("Maya cmds module not available - cannot parse selection")

        try:
            # Get objects to parse
            if object_names:
                selected = object_names
            else:
                selected = cmds.ls(selection=True, long=True)

            if not selected:
                self.logger.warning("No objects selected or specified")
                # Return empty scene data instead of None
                current_file = cmds.file(query=True, sceneName=True)
                source_file = Path(current_file) if current_file else Path("untitled.ma")
                return MayaSceneData(
                    source_file=source_file,
                    meshes=[],
                    materials=[],
                    joints=[],
                    skin_clusters=[]
                )

            self.logger.info(f"Parsing {len(selected)} selected objects")

            # Get current scene file
            current_file = cmds.file(query=True, sceneName=True)
            source_file = Path(current_file) if current_file else Path("untitled.ma")

            # Parse selected objects
            scene_data = self._parse_current_scene(source_file=source_file, objects_filter=selected)
            if not scene_data:
                raise RuntimeError("Failed to parse scene data")
            return scene_data

        except Exception as e:
            self.logger.error(f"Failed to parse selected objects: {e}")
            raise RuntimeError(f"Failed to parse selected objects: {e}") from e

    def extract_mesh_data(self, mesh_name: str) -> MeshData:
        """Extract geometry data from single mesh

        Clean Code: Single mesh extraction

        Args:
            mesh_name: Name of mesh node

        Returns:
            Mesh data
        """
        if not MAYA_AVAILABLE:
            raise RuntimeError("Maya not available")

        if cmds is None:
            raise RuntimeError("Maya cmds module not available")

        try:
            # Check if mesh exists
            if not cmds.objExists(mesh_name):
                raise ValueError(f"Mesh not found: {mesh_name}")

            # Get mesh shape node
            shapes = cmds.listRelatives(mesh_name, shapes=True, fullPath=True)
            if not shapes:
                raise ValueError(f"No shape node found for: {mesh_name}")

            shape_node = shapes[0]

            # Extract geometry data
            vertices = self._extract_vertices(shape_node)
            face_vertex_counts, face_vertex_indices = self._extract_faces(shape_node)
            normals = self._extract_normals(shape_node)
            uvs, uv_indices = self._extract_uvs(shape_node)
            vertex_colors = self._extract_vertex_colors(shape_node)
            world_matrix = self._extract_transform(mesh_name)

            # Get assigned materials
            material_assignments = self._get_material_assignments(shape_node)

            self.logger.info(
                f"Extracted mesh data: {mesh_name} ({len(vertices)} vertices, "
                f"{len(face_vertex_counts)} faces)")

            return MeshData(
                name=mesh_name,  # CRITICAL FIX: Use full DAG path for skin cluster matching
                transform_name=mesh_name.split('|')[-1],
                vertices=vertices,
                face_vertex_counts=face_vertex_counts,
                face_vertex_indices=face_vertex_indices,
                normals=normals,
                uvs=uvs,
                uv_indices=uv_indices,
                vertex_colors=vertex_colors,
                world_matrix=world_matrix,
                material_assignments=material_assignments
            )

        except Exception as e:
            self.logger.error(f"Failed to extract mesh data for {mesh_name}: {e}")
            raise RuntimeError(f"Failed to extract mesh data for {mesh_name}: {e}") from e

    def extract_material_data(self, material_name: str) -> MaterialData:
        """Extract material/shader properties

        Clean Code: Material data extraction
        Disney/Pixar Critical: RenderMan material support

        Args:
            material_name: Name of material node

        Returns:
            Material data

        Raises:
            RuntimeError: If material extraction fails
        """
        if not MAYA_AVAILABLE:
            raise RuntimeError("Maya not available")

        try:
            if not cmds.objExists(material_name):
                raise RuntimeError(f"Material not found: {material_name}")

            # Get shader type
            node_type = cmds.nodeType(material_name)

            # Extract properties based on shader type
            if node_type == 'lambert' or node_type == 'blinn':
                return self._extract_standard_material(material_name, node_type)
            elif node_type == 'standardSurface':
                return self._extract_standard_surface_material(material_name, node_type)
            elif node_type == 'openPBRSurface':
                # Maya 2026+ OpenPBR shader - has different attribute names
                return self._extract_openpbr_material(material_name, node_type)
            elif node_type.startswith('Pxr') or node_type == 'unknown':
                return self._extract_renderman_material(material_name, node_type)
            elif node_type in ('particleCloud', 'volumeShader'):
                # Volume shaders - not surface materials, skip extraction
                self.logger.debug(f"Skipping volume shader: {node_type}")
                return self._extract_generic_material(material_name, node_type)
            else:
                self.logger.warning(f"Unsupported shader type: {node_type}")
                return self._extract_generic_material(material_name, node_type)

        except Exception as e:
            self.logger.error(f"Failed to extract material data for {material_name}: {e}")
            raise RuntimeError(f"Failed to extract material data for {material_name}: {e}") from e

    def extract_skin_cluster(self, mesh_name: str) -> Optional[SkinClusterData]:
        """Extract skin cluster (rigging) data from mesh

        Clean Code: Rigging data extraction
        Disney/Pixar Critical: Accurate skin weights for animation

        Args:
            mesh_name: Name of mesh with skin cluster

        Returns:
            Skin cluster data or None if not rigged
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available")
            return None

        try:
            # Find skin cluster attached to mesh
            skin_clusters = self._find_skin_clusters(mesh_name)

            if not skin_clusters:
                self.logger.info(f"No skin cluster found on: {mesh_name}")
                return None

            skin_cluster = skin_clusters[0]

            # Get influenced joints - defensive: may raise exception for blendshape targets
            try:
                influence_joints = cmds.skinCluster(skin_cluster, query=True, influence=True)
            except Exception as e:
                self.logger.debug(f"Could not query influence joints for {mesh_name}: {e}")
                return None

            # Defensive check: blendshapes may return None for influence_joints
            if not influence_joints:
                self.logger.debug(f"No influence joints found for skin cluster on: {mesh_name}")
                return None

            # Extract per-vertex weights
            weights = self._extract_skin_weights(skin_cluster, mesh_name)

            # Final defensive check before using influence_joints
            if not influence_joints:
                self.logger.debug(f"Influence joints became None during processing: {mesh_name}")
                return None

            # Get bind matrices
            bind_pre_matrices = self._extract_bind_matrices(skin_cluster, influence_joints)

            self.logger.info(f"Extracted skin cluster: {skin_cluster} ({len(influence_joints)} joints)")

            return SkinClusterData(
                name=skin_cluster,
                mesh_name=mesh_name,
                influence_joints=influence_joints,
                weights=weights,
                bind_pre_matrices=bind_pre_matrices
            )

        except Exception as e:
            self.logger.error(f"Failed to extract skin cluster for {mesh_name}: {e}")
            return None

    def get_joint_hierarchy(self, root_joint: Optional[str] = None) -> List[JointData]:
        """Extract joint hierarchy starting from root

        Clean Code: Skeleton structure extraction
        Disney/Pixar Critical: Accurate hierarchy for UsdSkel

        Args:
            root_joint: Name of root joint, or None to find automatically

        Returns:
            List of joint data in hierarchy order
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available")
            return []

        try:
            # Auto-detect root joint if not provided
            if root_joint is None:
                all_joints = cmds.ls(type='joint', long=True)
                root_joints = [j for j in all_joints if not cmds.listRelatives(j, parent=True, type='joint')]
                if not root_joints:
                    self.logger.warning("No root joints found")
                    return []
                root_joint = root_joints[0]
                self.logger.info(f"Auto-detected root joint: {root_joint}")

            if not cmds.objExists(root_joint):
                self.logger.error(f"Root joint not found: {root_joint}")
                return []

            # Get all joints in hierarchy
            all_joints = cmds.listRelatives(root_joint, allDescendents=True, type='joint', fullPath=True) or []
            all_joints.insert(0, root_joint)  # Include root

            joint_data_list = []

            for joint in all_joints:
                # Get parent (only consider joint-type parents for skeleton hierarchy)
                parent = cmds.listRelatives(joint, parent=True, type='joint', fullPath=True)
                parent_name = parent[0] if parent else None

                # Get bind pose matrix
                bind_pose_matrix = self._get_joint_bind_pose(joint)

                # Get world bind matrix
                world_bind_matrix = self._extract_transform(joint)

                # Get children
                children = cmds.listRelatives(joint, children=True, type='joint', fullPath=True) or []

                joint_data = JointData(
                    name=joint,
                    parent_name=parent_name,
                    bind_pose_matrix=bind_pose_matrix,
                    world_bind_matrix=world_bind_matrix,
                    children=[c.split('|')[-1] for c in children]  # Short names
                )

                joint_data_list.append(joint_data)

            self.logger.info(f"Extracted joint hierarchy: {len(joint_data_list)} joints")
            return joint_data_list

        except Exception as e:
            self.logger.error(f"Failed to extract joint hierarchy from {root_joint}: {e}")
            return []

    def extract_nurbs_curves(
        self,
        curve_names: Optional[List[str]] = None,
        include_hierarchy: bool = True
    ) -> List[NurbsCurveData]:
        """Extract NURBS curves (rig controls) from Maya scene

        INDUSTRY FIRST: Full rig control export to USD!

        Args:
            curve_names: Specific curves to extract, or None for all
            include_hierarchy: Preserve parent/child relationships

        Returns:
            List of NURBS curve data structures
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available for curve extraction")
            return []

        try:
            # Get all NURBS curves or specific ones
            if curve_names is None:
                # Get all NURBS curve shapes, including intermediates (rig controls may be intermediate)
                all_curve_shapes = cmds.ls(type='nurbsCurve', long=True)  # Remove noIntermediate filter
                self.logger.info(f"🔍 Found {len(all_curve_shapes)} total NURBS curve shapes (including intermediates)")

                # Filter out true intermediates (construction history), but keep rig controls
                filtered_shapes = []
                for shape in all_curve_shapes:
                    if cmds.getAttr(f"{shape}.intermediateObject"):
                        # Check if it's a rig control (has transform parent with meaningful name)
                        transform = cmds.listRelatives(shape, parent=True, fullPath=True)
                        if transform and not any(keyword in transform[0].lower() for keyword in ['history', 'cache']):
                            filtered_shapes.append(shape)  # Keep as potential rig control
                    else:
                        filtered_shapes.append(shape)

                all_curve_shapes = filtered_shapes
                self.logger.info(f"🎯 Filtered to {len(all_curve_shapes)} NURBS curves for extraction")
            else:
                # Get shape nodes for specified transforms
                all_curve_shapes = []
                for curve_name in curve_names:
                    shapes = cmds.listRelatives(curve_name, shapes=True, fullPath=True) or []  # Remove noIntermediate
                    all_curve_shapes.extend([s for s in shapes if cmds.nodeType(s) == 'nurbsCurve'])

            self.logger.info(f"Found {len(all_curve_shapes)} NURBS curves to extract")

            if not all_curve_shapes:
                self.logger.warning("⚠️  No NURBS curves found in scene!")
                return []

            curves = []
            for curve_shape in all_curve_shapes:
                # Get transform node (parent of shape)
                transforms = cmds.listRelatives(curve_shape, parent=True, fullPath=True)
                if not transforms:
                    self.logger.warning(f"Curve shape {curve_shape} has no transform parent")
                    continue

                transform_node = transforms[0]

                try:
                    # Extract curve data
                    curve_data = self._extract_single_nurbs_curve(curve_shape, transform_node, include_hierarchy)
                    if curve_data:
                        curves.append(curve_data)
                except Exception as e:
                    self.logger.error(f"Failed to extract curve {curve_shape}: {e}")
                    continue

            self.logger.info(f"Successfully extracted {len(curves)} NURBS curves")
            return curves

        except Exception as e:
            self.logger.error(f"Failed to extract NURBS curves: {e}")
            return []

    def _extract_single_nurbs_curve(
        self,
        curve_shape: str,
        transform_node: str,
        include_hierarchy: bool
    ) -> Optional[NurbsCurveData]:
        """Extract single NURBS curve data

        Args:
            curve_shape: Shape node name
            transform_node: Transform node name
            include_hierarchy: Whether to extract parent/child info

        Returns:
            NurbsCurveData or None if extraction fails
        """
        try:
            # Get curve name (use transform, not shape)
            curve_name = transform_node.split('|')[-1]  # Short name

            # Check if this is an intermediate object (skip those)
            if cmds.getAttr(f"{curve_shape}.intermediateObject"):
                self.logger.debug(f"Skipping intermediate curve shape: {curve_shape}")
                return None

            # Get curve topology attributes
            degree = cmds.getAttr(f"{curve_shape}.degree")
            spans = cmds.getAttr(f"{curve_shape}.spans")
            form = cmds.getAttr(f"{curve_shape}.form")  # 0=open, 1=closed, 2=periodic

            # Form mapping
            form_map = {0: "open", 1: "closed", 2: "periodic"}
            form_str = form_map.get(form, "open")

            # Get CV count (correct formula)
            if form == 0:  # Open
                num_cvs = spans + degree
            elif form == 1:  # Closed
                num_cvs = spans
            else:  # Periodic
                num_cvs = spans

            # Get CV positions in object space (local coordinates)
            cvs = []
            for i in range(num_cvs):
                try:
                    # Extract in object space - USD expects local space points
                    cv_pos = cmds.pointPosition(f"{curve_shape}.cv[{i}]")
                    cvs.append((cv_pos[0], cv_pos[1], cv_pos[2]))
                except Exception as e:
                    self.logger.warning(f"Failed to get CV {i} for {curve_name}: {e}")
                    continue

            if not cvs:
                self.logger.warning(f"No CVs extracted for {curve_name}")
                return None

            # Get knot vector using Maya's curveInfo node
            # Create temporary curveInfo node to query knots
            curve_info = cmds.createNode('curveInfo', name='tempCurveInfo')
            try:
                cmds.connectAttr(f"{curve_shape}.worldSpace[0]", f"{curve_info}.inputCurve")
                knots_attr = cmds.getAttr(f"{curve_info}.knots")[0]  # Returns list of knots
                knots = list(knots_attr) if knots_attr else []
            finally:
                cmds.delete(curve_info)  # Clean up temp node

            # Get world matrix
            world_matrix = cmds.xform(transform_node, query=True, matrix=True, worldSpace=True)

            # Get local matrix
            local_matrix = cmds.xform(transform_node, query=True, matrix=True, objectSpace=True)

            # Get hierarchy if requested
            parent_name = None
            children = []

            if include_hierarchy:
                parents = cmds.listRelatives(transform_node, parent=True, fullPath=True)
                if parents:
                    parent_name = parents[0]

                child_list = cmds.listRelatives(transform_node, children=True, fullPath=True) or []
                # Filter out shape nodes from children
                children = [c for c in child_list if cmds.nodeType(c) != 'nurbsCurve']

            # Get override color if set
            color = None
            if cmds.getAttr(f"{transform_node}.overrideEnabled"):
                override_color = cmds.getAttr(f"{transform_node}.overrideColor")
                # Maya color index to RGB (approximate mapping)
                color = self._maya_color_index_to_rgb(override_color)

            # Get line width (Maya 2015+)
            line_width = None
            if cmds.attributeQuery('lineWidth', node=transform_node, exists=True):
                line_width = cmds.getAttr(f"{transform_node}.lineWidth")

            # Get custom attributes
            custom_attrs = {}
            user_attrs = cmds.listAttr(transform_node, userDefined=True) or []
            for attr in user_attrs:
                try:
                    value = cmds.getAttr(f"{transform_node}.{attr}")
                    custom_attrs[attr] = value
                except Exception:
                    pass  # Skip attributes we can't read

            # Create curve data
            curve_data = NurbsCurveData(
                name=curve_name,
                transform_name=transform_node,
                control_vertices=cvs,
                degree=degree,
                form=form_str,
                knots=knots,
                world_matrix=world_matrix,
                local_matrix=local_matrix,
                parent_name=parent_name,
                children=children,
                color=color,
                line_width=line_width,
                custom_attrs=custom_attrs
            )

            self.logger.debug(f"Extracted curve: {curve_name} ({len(cvs)} CVs, degree {degree}, {form_str})")
            return curve_data

        except Exception as e:
            self.logger.error(f"Failed to extract curve data: {e}")
            return None

    def _maya_color_index_to_rgb(self, color_index: int) -> tuple:
        """Convert Maya color index to approximate RGB

        Args:
            color_index: Maya override color index (0-31)

        Returns:
            (r, g, b) tuple normalized to 0-1
        """
        # Maya standard color palette (approximate)
        color_map = {
            0: (0.5, 0.5, 0.5),    # Gray
            1: (0.0, 0.0, 0.0),    # Black
            2: (0.25, 0.25, 0.25),  # Dark gray
            3: (0.5, 0.5, 0.5),    # Gray
            4: (0.6, 0.0, 0.15),   # Dark red
            5: (0.0, 0.0, 0.4),    # Dark blue
            6: (0.0, 0.0, 1.0),    # Blue
            7: (0.0, 0.3, 0.0),    # Dark green
            8: (0.15, 0.0, 0.3),   # Purple
            9: (0.8, 0.0, 0.8),    # Magenta
            10: (0.5, 0.3, 0.2),   # Brown
            11: (0.2, 0.1, 0.0),   # Dark brown
            12: (0.6, 0.3, 0.0),   # Orange brown
            13: (1.0, 0.0, 0.0),   # Red
            14: (0.0, 1.0, 0.0),   # Green
            15: (0.0, 0.25, 0.6),  # Blue
            16: (1.0, 1.0, 1.0),   # White
            17: (1.0, 1.0, 0.0),   # Yellow
            18: (0.0, 1.0, 1.0),   # Cyan
            19: (0.0, 1.0, 0.5),   # Aqua
            20: (1.0, 0.7, 0.7),   # Pink
            21: (0.9, 0.7, 0.5),   # Peach
            22: (1.0, 1.0, 0.4),   # Light yellow
            23: (0.0, 0.7, 0.0),   # Green
            24: (0.6, 0.4, 0.2),   # Brown
            25: (0.6, 0.6, 0.0),   # Yellow
            26: (0.4, 0.6, 0.2),   # Green
            27: (0.2, 0.6, 0.4),   # Cyan
            28: (0.2, 0.6, 0.6),   # Light blue
            29: (0.2, 0.4, 0.6),   # Blue
            30: (0.4, 0.2, 0.6),   # Purple
            31: (0.6, 0.2, 0.4),   # Magenta
        }

        return color_map.get(color_index, (0.5, 0.5, 0.5))  # Default to gray

    def validate_maya_file(self, maya_file: Path) -> tuple[bool, str]:
        """Validate Maya file before parsing

        Clean Code: Pre-flight validation

        Args:
            maya_file: Path to Maya file

        Returns:
            (is_valid, error_message) - Empty string if valid
        """
        # Check file exists
        if not maya_file.exists():
            error = f"File not found: {maya_file}"
            self.logger.error(error)
            return (False, error)

        # Check extension
        if maya_file.suffix.lower() not in ['.ma', '.mb']:
            error = f"Invalid file extension: {maya_file.suffix}. Expected .ma or .mb"
            self.logger.error(error)
            return (False, error)

        # Check file size
        if maya_file.stat().st_size == 0:
            error = f"Empty file: {maya_file}"
            self.logger.error(error)
            return (False, error)

        return (True, "")

    # ==================== PRIVATE HELPER METHODS ====================

    def _parse_current_scene(
        self,
        source_file: Optional[Path],
        objects_filter: Optional[List[str]] = None
    ) -> Optional[MayaSceneData]:
        """Parse current Maya scene (internal helper)

        Clean Code: DRY - Shared parsing logic

        Args:
            source_file: Source Maya file path, or None if parsing current unsaved scene
            objects_filter: Optional list of specific objects to parse

        Returns:
            Complete scene data
        """
        try:
            # Get all meshes (or filtered objects)
            if objects_filter:
                all_meshes = [obj for obj in objects_filter if cmds.nodeType(obj) == 'transform']
            else:
                all_meshes = cmds.ls(type='mesh', long=True)
                # Filter out intermediate objects (blendshape targets, construction history)
                all_meshes = [m for m in all_meshes if not cmds.getAttr(f"{m}.intermediateObject")]
                all_meshes = [cmds.listRelatives(m, parent=True, fullPath=True)[0] for m in all_meshes]
                # Filter out hidden objects (blendshape targets that were hidden)
                all_meshes = [m for m in all_meshes if cmds.getAttr(f"{m}.visibility")]

            # Extract mesh data
            meshes = []
            for mesh in all_meshes:
                mesh_data = self.extract_mesh_data(mesh)
                if mesh_data:
                    meshes.append(mesh_data)

            # Extract materials (include RenderMan-specific query)
            # NOTE: RenderMan creates TWO materials per surface:
            #   1. PxrSurface (or similar) - The renderable material
            #   2. Lambert shader - Viewport preview for animators
            # Both are intentional and should be exported to USD.
            materials = []
            all_materials = cmds.ls(materials=True)

            # Add RenderMan materials if available (defensive: don't fail if plugin not loaded)
            try:
                renderman_materials = cmds.ls('Pxr*', materials=True) or []
                all_materials.extend(renderman_materials)
            except Exception:
                pass  # Graceful degradation if RenderMan not available

            for mat in set(all_materials):  # Deduplicate
                mat_data = self.extract_material_data(mat)
                if mat_data:
                    materials.append(mat_data)

            # Extract ALL joints (including FK/IK control joints)
            # INDUSTRY FIRST: Complete rig preservation for USD pipeline!
            # We export the ENTIRE joint hierarchy to preserve FK/IK systems
            joints = []
            joints_seen = set()  # Track unique joint paths to avoid duplicates
            all_joints = cmds.ls(type='joint', long=True)
            root_joints = [j for j in all_joints if not cmds.listRelatives(j, parent=True, type='joint')]

            for root in root_joints:
                joint_hierarchy = self.get_joint_hierarchy(root)
                # Add all joints we haven't seen before (deduplication)
                for joint_data in joint_hierarchy:
                    if joint_data.name not in joints_seen:
                        joints.append(joint_data)
                        joints_seen.add(joint_data.name)
            
            self.logger.info(f"Extracted {len(joints)} joints (including FK/IK control systems)")

            # Extract skin clusters
            skin_clusters = []
            for mesh in all_meshes:
                skin_data = self.extract_skin_cluster(mesh)
                if skin_data:
                    skin_clusters.append(skin_data)

            # Extract NURBS curves (rig controls) - INDUSTRY FIRST!
            nurbs_curves = []
            try:
                curve_data_list = self.extract_nurbs_curves(include_hierarchy=True)
                nurbs_curves = curve_data_list
                self.logger.info(f"Extracted {len(nurbs_curves)} NURBS curves (rig controls)")
            except Exception as e:
                self.logger.warning(f"Failed to extract NURBS curves: {e}")

            # Extract rig connections for functional controllers - INDUSTRY FIRST!
            rig_connections = []
            constraints = []
            set_driven_keys = []
            try:
                if nurbs_curves:
                    rig_connections = self.extract_rig_connections(nurbs_curves)
                    constraints = self.extract_constraints(nurbs_curves)
                    set_driven_keys = self.extract_set_driven_keys(nurbs_curves)
                    self.logger.info(
                        f"Extracted {len(rig_connections)} rig connections, "
                        f"{len(constraints)} constraints, {len(set_driven_keys)} set-driven keys"
                    )
            except Exception as e:
                self.logger.warning(f"Failed to extract rig connections: {e}")

            self.logger.info(
                f"Parsed scene: {len(meshes)} meshes, {len(materials)} materials, "
                f"{len(joints)} joints, {len(nurbs_curves)} curves"
            )

            # Ensure source_file is not None for MayaSceneData (default to "untitled.ma" for unsaved scenes)
            if source_file is None:
                source_file = Path("untitled.ma")

            return MayaSceneData(
                source_file=source_file,
                meshes=meshes,
                materials=materials,
                joints=joints,
                skin_clusters=skin_clusters,
                nurbs_curves=nurbs_curves,  # NEW: Include rig controls!
                rig_connections=rig_connections,  # NEW: Include rig connections!
                constraints=constraints,  # NEW: Include constraints!
                set_driven_keys=set_driven_keys  # NEW: Include set-driven keys!
            )

        except Exception as e:
            self.logger.error(f"Failed to parse current scene: {e}")
            return None

    def _extract_vertices(self, shape_node: str) -> List[tuple]:
        """Extract vertex positions in object space (local coordinates)"""
        vertices = []
        vertex_count = cmds.polyEvaluate(shape_node, vertex=True)

        for i in range(vertex_count):
            # Extract in object space (local coordinates) - USD expects local space points
            pos = cmds.xform(f"{shape_node}.vtx[{i}]", query=True, translation=True, objectSpace=True)
            vertices.append(tuple(pos))

        return vertices

    def _extract_faces(self, shape_node: str) -> tuple:
        """Extract face topology

        Returns:
            (face_vertex_counts, face_vertex_indices)
        """
        face_vertex_counts = []
        face_vertex_indices = []
        face_count = cmds.polyEvaluate(shape_node, face=True)

        for i in range(face_count):
            vertex_indices = cmds.polyInfo(f"{shape_node}.f[{i}]", faceToVertex=True)[0]
            # Parse vertex indices from string
            indices = [int(x) for x in vertex_indices.split() if x.isdigit()]
            face_vertex_counts.append(len(indices))
            face_vertex_indices.extend(indices)

        return (face_vertex_counts, face_vertex_indices)

    def _extract_normals(self, shape_node: str) -> List[tuple]:
        """Extract vertex normals"""
        normals = []
        vertex_count = cmds.polyEvaluate(shape_node, vertex=True)

        for i in range(vertex_count):
            normal = cmds.polyNormalPerVertex(f"{shape_node}.vtx[{i}]", query=True, xyz=True)
            # Average normals for this vertex
            if normal:
                avg_normal = (
                    sum(normal[0::3]) / len(normal[0::3]),
                    sum(normal[1::3]) / len(normal[1::3]),
                    sum(normal[2::3]) / len(normal[2::3])
                )
                normals.append(avg_normal)

        return normals

    def _extract_uvs(self, shape_node: str) -> tuple:
        """Extract UV coordinates

        Returns:
            (uvs, uv_indices)
        """
        try:
            u_values = cmds.polyEditUV(f"{shape_node}.map[*]", query=True, u=True) or []
            v_values = cmds.polyEditUV(f"{shape_node}.map[*]", query=True, v=True) or []

            uvs = [(u, v) for u, v in zip(u_values, v_values)]

            # Get UV indices per face-vertex
            # For now, return simple sequential indices
            uv_indices = list(range(len(uvs)))

            return (uvs, uv_indices)
        except Exception:
            return ([], [])

    def _extract_vertex_colors(self, shape_node: str) -> List[tuple]:
        """Extract vertex colors if present"""
        try:
            # Check if vertex colors exist
            color_sets = cmds.polyColorSet(shape_node, query=True, allColorSets=True)
            if not color_sets:
                return []

            # Get colors from first color set
            colors = cmds.polyColorPerVertex(shape_node, query=True, rgb=True) or []
            vertex_colors = [(colors[i], colors[i+1], colors[i+2]) for i in range(0, len(colors), 3)]
            return vertex_colors
        except Exception:
            return []

    def _extract_transform(self, node: str) -> List[float]:
        """Extract world transform matrix (4x4 flattened)"""
        matrix = cmds.xform(node, query=True, matrix=True, worldSpace=True)
        return matrix

    def _get_material_assignments(self, shape_node: str) -> Dict[str, List[int]]:
        """Get materials assigned to faces

        Returns:
            Dict mapping material_name -> [face_indices]
        """
        shading_engines = cmds.listConnections(shape_node, type='shadingEngine')
        if not shading_engines:
            return {}

        material_assignments = {}

        for sg in set(shading_engines):  # Remove duplicates
            # Get material from shading engine
            materials = cmds.listConnections(f"{sg}.surfaceShader")
            if not materials:
                continue

            material_name = materials[0]

            # Get faces assigned to this shading engine
            assigned_faces = cmds.sets(sg, query=True) or []
            face_indices = []

            for face in assigned_faces:
                if '.f[' in face:
                    # Parse face index from "meshShape.f[0]"
                    try:
                        idx = int(face.split('[')[1].split(']')[0])
                        face_indices.append(idx)
                    except Exception:
                        pass

            if face_indices:
                material_assignments[material_name] = face_indices

        return material_assignments

    def _extract_standard_material(self, material_name: str, node_type: str) -> MaterialData:
        """Extract Lambert/Blinn material properties"""
        material_data = MaterialData(
            name=material_name,
            shader_type=node_type,
            diffuse_color=self._get_color_attribute(material_name, 'color'),
            specular_color=self._get_color_attribute(material_name, 'specularColor') if node_type == 'blinn' else None,
            roughness=1.0 - self._get_float_attribute(material_name, 'reflectivity', 0.0),
            metallic=0.0,  # Standard Maya shaders don't have metallic
            opacity=self._get_float_attribute(material_name, 'transparency', 1.0),
            is_renderman=False
        )

        # Check for connected textures
        color_connections = cmds.listConnections(f"{material_name}.color", source=True)
        if color_connections:
            material_data.diffuse_texture = Path(self._get_texture_path(color_connections[0]))

        return material_data

    def _extract_standard_surface_material(self, material_name: str, node_type: str) -> MaterialData:
        """Extract StandardSurface (Arnold/Maya 2020+) material properties

        StandardSurface is Maya's modern physically-based shader (Arnold/USD compatible)
        """
        material_data = MaterialData(
            name=material_name,
            shader_type=node_type,
            # StandardSurface uses baseColor instead of color
            diffuse_color=self._get_color_attribute(material_name, 'baseColor'),
            specular_color=self._get_color_attribute(material_name, 'specularColor'),
            roughness=self._get_float_attribute(material_name, 'specularRoughness', 0.5),
            metallic=self._get_float_attribute(material_name, 'metalness', 0.0),
            opacity=1.0 - self._get_float_attribute(material_name, 'transmission', 0.0),
            is_renderman=False
        )

        # Check for connected textures
        base_color_connections = cmds.listConnections(f"{material_name}.baseColor", source=True)
        if base_color_connections:
            material_data.diffuse_texture = Path(self._get_texture_path(base_color_connections[0]))

        # Check for normal map
        normal_connections = cmds.listConnections(f"{material_name}.normalCamera", source=True)
        if normal_connections:
            material_data.normal_texture = Path(self._get_texture_path(normal_connections[0]))

        # Check for roughness map
        roughness_connections = cmds.listConnections(f"{material_name}.specularRoughness", source=True)
        if roughness_connections:
            material_data.roughness_texture = Path(self._get_texture_path(roughness_connections[0]))

        # Check for metalness map
        metallic_connections = cmds.listConnections(f"{material_name}.metalness", source=True)
        if metallic_connections:
            material_data.metallic_texture = Path(self._get_texture_path(metallic_connections[0]))

        return material_data

    def _extract_openpbr_material(self, material_name: str, node_type: str) -> MaterialData:
        """Extract OpenPBR Surface (Maya 2026+) material properties

        OpenPBR is the new industry-standard physically-based shader
        Attribute names differ from standardSurface
        """
        # OpenPBR uses different attribute names - safely get with fallbacks
        # Base color: base_color (not baseColor)
        base_color = self._get_color_attribute_safe(material_name, 'base_color', [0.8, 0.8, 0.8])
        
        # Specular color
        specular_color = self._get_color_attribute_safe(material_name, 'specular_color', [1.0, 1.0, 1.0])
        
        # Roughness: specular_roughness (not specularRoughness)
        roughness = self._get_float_attribute_safe(material_name, 'specular_roughness', 0.5)
        
        # Metallic: base_metalness (not metalness)
        metallic = self._get_float_attribute_safe(material_name, 'base_metalness', 0.0)
        
        # Transmission for opacity
        transmission = self._get_float_attribute_safe(material_name, 'transmission_weight', 0.0)
        
        material_data = MaterialData(
            name=material_name,
            shader_type=node_type,
            diffuse_color=base_color,
            specular_color=specular_color,
            roughness=roughness,
            metallic=metallic,
            opacity=1.0 - transmission,
            is_renderman=False
        )

        # Check for connected textures (with safe attribute checking)
        try:
            base_color_connections = cmds.listConnections(f"{material_name}.base_color", source=True)
            if base_color_connections:
                material_data.diffuse_texture = Path(self._get_texture_path(base_color_connections[0]))
        except Exception:
            pass

        # Check for normal map
        try:
            normal_connections = cmds.listConnections(f"{material_name}.geometry_normal", source=True)
            if normal_connections:
                material_data.normal_texture = Path(self._get_texture_path(normal_connections[0]))
        except Exception:
            pass

        # Check for roughness map
        try:
            roughness_connections = cmds.listConnections(f"{material_name}.specular_roughness", source=True)
            if roughness_connections:
                material_data.roughness_texture = Path(self._get_texture_path(roughness_connections[0]))
        except Exception:
            pass

        # Check for metalness map
        try:
            metallic_connections = cmds.listConnections(f"{material_name}.base_metalness", source=True)
            if metallic_connections:
                material_data.metallic_texture = Path(self._get_texture_path(metallic_connections[0]))
        except Exception:
            pass

        return material_data

    def _get_color_attribute_safe(self, node: str, attr: str, default: List[float]) -> List[float]:
        """Safely get a color attribute with fallback"""
        try:
            if cmds.objExists(f"{node}.{attr}"):
                return list(cmds.getAttr(f"{node}.{attr}")[0])
        except Exception:
            pass
        return default

    def _get_float_attribute_safe(self, node: str, attr: str, default: float) -> float:
        """Safely get a float attribute with fallback"""
        try:
            if cmds.objExists(f"{node}.{attr}"):
                return cmds.getAttr(f"{node}.{attr}")
        except Exception:
            pass
        return default

    def _extract_renderman_material(self, material_name: str, node_type: str) -> MaterialData:
        """Extract RenderMan material properties

        Disney/Pixar Critical: Preserve RenderMan parameters
        """
        # Get basic material properties with proper attribute names
        diffuse_color = self._get_color_attribute(material_name, 'diffuseColor')
        # PxrDisney uses baseColor, PxrSurface uses diffuseColor
        if diffuse_color == [0.5, 0.5, 0.5]:  # Default means not found
            diffuse_color = self._get_color_attribute(material_name, 'baseColor')
        
        # PxrSurface uses specularFaceColor, not specularColor
        specular_color = self._get_color_attribute(material_name, 'specularFaceColor')
        if specular_color == [0.5, 0.5, 0.5]:  # Default means not found
            specular_color = self._get_color_attribute(material_name, 'specularColor')

        # For metallic, try different possible attribute names (PxrDisney has metallic, PxrSurface doesn't)
        metallic = self._get_float_attribute(material_name, 'metallic', 0.0)
        if metallic == 0.0:  # If not found, estimate from specular
            specular_intensity = sum(specular_color) / 3.0
            metallic = min(specular_intensity * 2.0, 1.0)

        # For roughness, try different possible attribute names
        roughness = self._get_float_attribute(material_name, 'roughness', 0.5)
        if roughness == 0.5:  # If not found, try specularRoughness
            roughness = self._get_float_attribute(material_name, 'specularRoughness', 0.5)

        material_data = MaterialData(
            name=material_name,
            shader_type=node_type,
            diffuse_color=diffuse_color,
            metallic=metallic,
            roughness=roughness,
            is_renderman=True
        )

        # Extract all RenderMan-specific parameters with better filtering
        try:
            pxr_attributes = cmds.listAttr(material_name, userDefined=True) or []
            for attr in pxr_attributes:
                try:
                    # Skip connection-related attributes
                    if 'Connection' in attr or attr.endswith('Connection'):
                        continue

                    value = cmds.getAttr(f"{material_name}.{attr}")

                    # Skip complex data types that USD can't handle
                    if isinstance(value, (list, tuple)) and len(value) > 4:
                        continue
                    elif hasattr(value, '__len__') and not isinstance(value, (str, list, tuple)):
                        continue  # Skip other complex objects

                    material_data.renderman_params[attr] = value
                except Exception as e:
                    self.logger.debug(f"Skipping attribute {attr} on {material_name}: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to extract RenderMan attributes for {material_name}: {e}")

        return material_data

    def _extract_generic_material(self, material_name: str, node_type: str) -> MaterialData:
        """Extract generic material properties"""
        return MaterialData(
            name=material_name,
            shader_type=node_type,
            diffuse_color=(0.5, 0.5, 0.5),
            metallic=0.0,
            roughness=0.5,
            is_renderman=False
        )

    def _get_color_attribute(self, node: str, attr: str) -> tuple:
        """Get RGB color attribute"""
        try:
            color = cmds.getAttr(f"{node}.{attr}")[0]
            return color
        except Exception:
            return (0.5, 0.5, 0.5)

    def _get_float_attribute(self, node: str, attr: str, default: float) -> float:
        """Get float attribute with fallback"""
        try:
            return cmds.getAttr(f"{node}.{attr}")
        except Exception:
            return default

    def _get_texture_path(self, file_node: str) -> str:
        """Get texture file path from file node"""
        try:
            return cmds.getAttr(f"{file_node}.fileTextureName")
        except Exception:
            return ""

    def _find_skin_clusters(self, mesh_name: str) -> List[str]:
        """Find skin clusters attached to mesh"""
        history = cmds.listHistory(mesh_name, pruneDagObjects=True)
        skin_clusters = [h for h in history if cmds.nodeType(h) == 'skinCluster']
        return skin_clusters

    def _extract_skin_weights(self, skin_cluster: str, mesh_name: str) -> Dict[int, List[tuple]]:
        """Extract skin weights per vertex

        Returns:
            Dict mapping vertex_index -> [(joint_index, weight), ...]
        """
        weights = {}
        vertex_count = cmds.polyEvaluate(mesh_name, vertex=True)

        # Defensive: blendshape targets may raise exceptions or return None
        try:
            joints = cmds.skinCluster(skin_cluster, query=True, influence=True)
        except Exception as e:
            self.logger.debug(f"Could not query joints for skin weights on {mesh_name}: {e}")
            return weights

        # Defensive: blendshape targets may have no joints
        if not joints:
            self.logger.debug(f"No influence joints for skin weights extraction on: {mesh_name}")
            return weights

        for v_idx in range(vertex_count):
            # Defensive: blendshape targets may raise exceptions on skinPercent queries
            try:
                vertex_weights = cmds.skinPercent(
                    skin_cluster,
                    f"{mesh_name}.vtx[{v_idx}]",
                    query=True,
                    value=True
                )
            except Exception as e:
                # Blendshape targets or invalid skin clusters may fail here
                self.logger.debug(f"Could not query skin weights for vertex {v_idx} on {mesh_name}: {e}")
                continue

            # Defensive: vertex_weights can be None for invalid skin clusters
            if not vertex_weights:
                continue

            # Build list of (joint_index, weight) pairs
            influences = []
            for j_idx, weight in enumerate(vertex_weights):
                if weight > 0.0001:  # Ignore near-zero weights
                    influences.append((j_idx, weight))

            weights[v_idx] = influences

        return weights

    def _extract_bind_matrices(self, skin_cluster: str, joints: List[str]) -> Dict[str, List[float]]:
        """Extract bind pose matrices for each joint"""
        bind_matrices = {}

        # Defensive: if joints is None or empty, return empty dict
        if not joints:
            self.logger.debug(f"No joints provided for bind matrix extraction on skin cluster: {skin_cluster}")
            return bind_matrices

        for joint in joints:
            try:
                # Get bind pre-matrix (inverse bind matrix)
                matrix_attr = f"{skin_cluster}.bindPreMatrix[{joints.index(joint)}]"
                matrix = cmds.getAttr(matrix_attr)
                bind_matrices[joint] = list(matrix)
            except Exception:
                # Fallback to identity matrix
                bind_matrices[joint] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

        return bind_matrices

    def _get_joint_bind_pose(self, joint: str) -> List[float]:
        """Get joint's bind pose transform in LOCAL space (object space)

        CRITICAL: USD bindTransforms expect LOCAL/OBJECT space matrices,
        not world space! This reads from dagPose nodes for correct bind pose.
        """
        try:
            # Find bind pose dagPose node
            bind_poses = cmds.ls(type='dagPose')
            bind_pose_node = None

            for pose in bind_poses:
                is_bind = cmds.dagPose(pose, query=True, bindPose=True)
                if is_bind:
                    bind_pose_node = pose
                    break

            if bind_pose_node:
                # Read bind pose from dagPose node
                members = cmds.dagPose(bind_pose_node, query=True, members=True) or []

                # Find this joint's index in the dagPose
                joint_short_name = joint.split(':')[-1].split('|')[-1]
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

                        # Convert world matrix to local matrix
                        # Get parent's world matrix
                        parent = cmds.listRelatives(joint, parent=True, type='joint', fullPath=True)
                        if parent:
                            parent_world_matrix = cmds.xform(parent[0], query=True, matrix=True, worldSpace=True)
                            import maya.api.OpenMaya as om2
                            parent_m = om2.MMatrix(parent_world_matrix)
                            world_m = om2.MMatrix(world_matrix)
                            local_m = world_m * parent_m.inverse()
                            return list(local_m)
                        else:
                            # Root joint - world matrix is local matrix
                            return list(world_matrix)

            # Fallback: Get current LOCAL transform (object space)
            # This is what USD skeleton bindTransforms expect!
            self.logger.debug(f"No bind pose found for {joint}, using current transform")
            matrix = cmds.xform(joint, query=True, matrix=True, objectSpace=True)
            return list(matrix)

        except Exception as e:
            # Use debug level - this is expected for FK/IK control joints
            self.logger.debug(f"Could not get bind pose for {joint}: {e}")
            # Fallback to current transform
            try:
                matrix = cmds.xform(joint, query=True, matrix=True, objectSpace=True)
                return list(matrix)
            except Exception:
                # Ultimate fallback to identity matrix
                return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

    def extract_rig_connections(
        self,
        nurbs_curves: List[NurbsCurveData]
    ) -> List[RigConnectionData]:
        """Extract rigging connections for NURBS curve controllers

        INDUSTRY FIRST: Functional rig controller preservation!
        This enables complete rig functionality round-tripping through USD.

        Args:
            nurbs_curves: List of NURBS curves to extract connections for

        Returns:
            List of rig connection data structures
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available for connection extraction")
            return []

        try:
            connections = []
            curve_transforms = [curve.transform_name for curve in nurbs_curves]

            # Get all connections from curve transforms
            for curve_transform in curve_transforms:
                if not cmds.objExists(curve_transform):
                    continue

                # Get all attributes of the curve transform
                attrs = cmds.listAttr(curve_transform, keyable=True) or []
                attrs.extend(cmds.listAttr(curve_transform, userDefined=True) or [])

                for attr in attrs:
                    if not cmds.attributeQuery(attr, node=curve_transform, exists=True):
                        continue

                    # Get connections where this attribute is the source
                    connections_list = cmds.listConnections(
                        f"{curve_transform}.{attr}",
                        source=False,  # We want destinations
                        destination=True,
                        plugs=True,
                        connections=True
                    ) or []

                    # Process connections in pairs (source, destination)
                    for i in range(0, len(connections_list), 2):
                        source_plug = connections_list[i]
                        dest_plug = connections_list[i + 1] if i + 1 < len(connections_list) else None

                        if dest_plug:
                            # Parse source and destination
                            source_parts = source_plug.split('.')
                            dest_parts = dest_plug.split('.')

                            if len(source_parts) >= 2 and len(dest_parts) >= 2:
                                source_node = '.'.join(source_parts[:-1])
                                source_attr = source_parts[-1]
                                target_node = '.'.join(dest_parts[:-1])
                                target_attr = dest_parts[-1]

                                # Create connection data
                                connection = RigConnectionData(
                                    source_node=source_node,
                                    target_node=target_node,
                                    source_attr=source_attr,
                                    target_attr=target_attr,
                                    connection_type="direct",
                                    is_input=True
                                )
                                connections.append(connection)

            self.logger.info(f"Extracted {len(connections)} rig connections")
            return connections

        except Exception as e:
            self.logger.error(f"Failed to extract rig connections: {e}")
            return []

    def extract_constraints(
        self,
        nurbs_curves: List[NurbsCurveData]
    ) -> List[ConstraintData]:
        """Extract Maya constraints involving NURBS curve controllers

        Args:
            nurbs_curves: List of NURBS curves to check for constraints

        Returns:
            List of constraint data structures
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available for constraint extraction")
            return []

        try:
            constraints = []
            curve_transforms = [curve.transform_name for curve in nurbs_curves]

            # Find all constraint nodes in the scene
            constraint_types = [
                'parentConstraint', 'pointConstraint', 'orientConstraint',
                'scaleConstraint', 'aimConstraint', 'poleVectorConstraint'
            ]

            for constraint_type in constraint_types:
                constraint_nodes = cmds.ls(type=constraint_type) or []

                for constraint_node in constraint_nodes:
                    # Get constraint target (what it's constraining)
                    constrained_objs = cmds.listConnections(
                        f"{constraint_node}.constraintParentInverseMatrix",
                        source=True,
                        type='transform'
                    ) or []

                    if not constrained_objs:
                        continue

                    target_node = constrained_objs[0]

                    # Check if target is one of our curves
                    if target_node not in curve_transforms:
                        continue

                    # Get constraint drivers
                    driver_nodes = cmds.listConnections(
                        f"{constraint_node}.target",
                        source=True,
                        type='transform'
                    ) or []

                    # Get driver weights
                    driver_weights = {}
                    for i, driver in enumerate(driver_nodes):
                        try:
                            weight = cmds.getAttr(f"{constraint_node}.target[{i}].targetWeight")
                            driver_weights[driver] = weight
                        except Exception:
                            driver_weights[driver] = 1.0

                    # Get constraint settings
                    maintain_offset = cmds.getAttr(f"{constraint_node}.maintainOffset")
                    interpolate = cmds.getAttr(f"{constraint_node}.interpType") == 1

                    # Determine constrained attributes based on constraint type
                    if constraint_type == 'parentConstraint':
                        target_attrs = ['translate', 'rotate']
                    elif constraint_type == 'pointConstraint':
                        target_attrs = ['translate']
                    elif constraint_type == 'orientConstraint':
                        target_attrs = ['rotate']
                    elif constraint_type == 'scaleConstraint':
                        target_attrs = ['scale']
                    else:
                        target_attrs = ['translate', 'rotate', 'scale']

                    constraint_data = ConstraintData(
                        name=constraint_node,
                        constraint_type=constraint_type,
                        target_node=target_node,
                        target_attrs=target_attrs,
                        driver_nodes=driver_nodes,
                        driver_weights=driver_weights,
                        maintain_offset=maintain_offset,
                        interpolate=interpolate
                    )
                    constraints.append(constraint_data)

            self.logger.info(f"Extracted {len(constraints)} constraints")
            return constraints

        except Exception as e:
            self.logger.error(f"Failed to extract constraints: {e}")
            return []

    def extract_set_driven_keys(
        self,
        nurbs_curves: List[NurbsCurveData]
    ) -> List[SetDrivenKeyData]:
        """Extract set-driven keys involving NURBS curve controllers

        Args:
            nurbs_curves: List of NURBS curves to check for SDKs

        Returns:
            List of set-driven key data structures
        """
        if not MAYA_AVAILABLE:
            self.logger.error("Maya not available for set-driven key extraction")
            return []

        try:
            sdk_data = []
            curve_transforms = [curve.transform_name for curve in nurbs_curves]

            # Get all anim curves in the scene
            anim_curves = cmds.ls(type='animCurve') or []

            for anim_curve in anim_curves:
                # Get what this anim curve is driving
                driven_attrs = cmds.listConnections(
                    anim_curve,
                    destination=True,
                    plugs=True
                ) or []

                for driven_attr in driven_attrs:
                    driven_parts = driven_attr.split('.')
                    if len(driven_parts) >= 2:
                        driven_node = '.'.join(driven_parts[:-1])
                        driven_attr_name = driven_parts[-1]

                        # Check if driven node is one of our curves
                        if driven_node not in curve_transforms:
                            continue

                        # Get driver attribute
                        driver_attrs = cmds.listConnections(
                            f"{anim_curve}.input",
                            source=True,
                            plugs=True
                        ) or []

                        if not driver_attrs:
                            continue

                        driver_attr = driver_attrs[0]
                        driver_parts = driver_attr.split('.')
                        if len(driver_parts) >= 2:
                            driver_node = '.'.join(driver_parts[:-1])
                            driver_attr_name = driver_parts[-1]

                            # Get keyframe data
                            driver_values = cmds.keyframe(
                                anim_curve,
                                query=True,
                                floatChange=True
                            ) or []

                            driven_values = cmds.keyframe(
                                anim_curve,
                                query=True,
                                valueChange=True
                            ) or []

                            # Get interpolation type
                            interp_type = cmds.getAttr(f"{anim_curve}.preInfinity")
                            interp_map = {0: "constant", 1: "linear", 2: "cycle", 3: "cycleRelative"}
                            interpolation = interp_map.get(interp_type, "linear")

                            sdk = SetDrivenKeyData(
                                driver_node=driver_node,
                                driver_attr=driver_attr_name,
                                driven_node=driven_node,
                                driven_attr=driven_attr_name,
                                driver_values=driver_values,
                                driven_values=driven_values,
                                interpolation=interpolation
                            )
                            sdk_data.append(sdk)

            self.logger.info(f"Extracted {len(sdk_data)} set-driven keys")
            return sdk_data

        except Exception as e:
            self.logger.error(f"Failed to extract set-driven keys: {e}")
            return []
