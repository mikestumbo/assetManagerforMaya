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
    from typing import Any as MayaCmds
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
    
    
    def parse_maya_file(self, maya_file: Path, options: Optional[Dict[str, Any]] = None) -> MayaSceneData:
        """Parse complete Maya file and extract all data
        
        Clean Code: Main entry point for file parsing
        Disney/Pixar Critical: Must extract all data accurately
        
        Args:
            maya_file: Path to .ma or .mb file
            options: Optional parsing options
            
        Returns:
            Complete scene data
            
        Raises:
            RuntimeError: If parsing fails
        """
        if not MAYA_AVAILABLE:
            raise RuntimeError("Maya not available - cannot parse file")
        
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
            
            self.logger.info(f"Extracted mesh data: {mesh_name} ({len(vertices)} vertices, {len(face_vertex_counts)} faces)")
            
            return MeshData(
                name=shape_node.split('|')[-1],  # Short name
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
            elif node_type.startswith('Pxr'):
                return self._extract_renderman_material(material_name, node_type)
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
            
            # Get influenced joints
            influence_joints = cmds.skinCluster(skin_cluster, query=True, influence=True)
            
            # Extract per-vertex weights
            weights = self._extract_skin_weights(skin_cluster, mesh_name)
            
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
                # Get parent
                parent = cmds.listRelatives(joint, parent=True, fullPath=True)
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
    
    def _parse_current_scene(self, source_file: Path, objects_filter: Optional[List[str]] = None) -> Optional[MayaSceneData]:
        """Parse current Maya scene (internal helper)
        
        Clean Code: DRY - Shared parsing logic
        
        Args:
            source_file: Source Maya file path
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
                all_meshes = [cmds.listRelatives(m, parent=True, fullPath=True)[0] for m in all_meshes]
            
            # Extract mesh data
            meshes = []
            for mesh in all_meshes:
                mesh_data = self.extract_mesh_data(mesh)
                if mesh_data:
                    meshes.append(mesh_data)
            
            # Extract materials
            materials = []
            all_materials = cmds.ls(materials=True)
            for mat in all_materials:
                mat_data = self.extract_material_data(mat)
                if mat_data:
                    materials.append(mat_data)
            
            # Extract joints (find root joints)
            joints = []
            all_joints = cmds.ls(type='joint', long=True)
            root_joints = [j for j in all_joints if not cmds.listRelatives(j, parent=True, type='joint')]
            
            for root in root_joints:
                joint_hierarchy = self.get_joint_hierarchy(root)
                joints.extend(joint_hierarchy)
            
            # Extract skin clusters
            skin_clusters = []
            for mesh in all_meshes:
                skin_data = self.extract_skin_cluster(mesh)
                if skin_data:
                    skin_clusters.append(skin_data)
            
            self.logger.info(f"Parsed scene: {len(meshes)} meshes, {len(materials)} materials, {len(joints)} joints")
            
            return MayaSceneData(
                source_file=source_file,
                meshes=meshes,
                materials=materials,
                joints=joints,
                skin_clusters=skin_clusters
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse current scene: {e}")
            return None
    
    
    def _extract_vertices(self, shape_node: str) -> List[tuple]:
        """Extract vertex positions"""
        vertices = []
        vertex_count = cmds.polyEvaluate(shape_node, vertex=True)
        
        for i in range(vertex_count):
            pos = cmds.xform(f"{shape_node}.vtx[{i}]", query=True, translation=True, worldSpace=True)
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
        except:
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
        except:
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
                    except:
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
    
    
    def _extract_renderman_material(self, material_name: str, node_type: str) -> MaterialData:
        """Extract RenderMan material properties
        
        Disney/Pixar Critical: Preserve RenderMan parameters
        """
        material_data = MaterialData(
            name=material_name,
            shader_type=node_type,
            diffuse_color=(1.0, 1.0, 1.0),
            metallic=self._get_float_attribute(material_name, 'specularFaceColor', 0.0),
            roughness=self._get_float_attribute(material_name, 'specularRoughness', 0.5),
            is_renderman=True
        )
        
        # Extract all RenderMan-specific parameters
        pxr_attributes = cmds.listAttr(material_name, userDefined=True) or []
        for attr in pxr_attributes:
            try:
                value = cmds.getAttr(f"{material_name}.{attr}")
                material_data.renderman_params[attr] = value
            except:
                pass
        
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
        except:
            return (0.5, 0.5, 0.5)
    
    
    def _get_float_attribute(self, node: str, attr: str, default: float) -> float:
        """Get float attribute with fallback"""
        try:
            return cmds.getAttr(f"{node}.{attr}")
        except:
            return default
    
    
    def _get_texture_path(self, file_node: str) -> str:
        """Get texture file path from file node"""
        try:
            return cmds.getAttr(f"{file_node}.fileTextureName")
        except:
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
        joints = cmds.skinCluster(skin_cluster, query=True, influence=True)
        
        for v_idx in range(vertex_count):
            vertex_weights = cmds.skinPercent(
                skin_cluster, 
                f"{mesh_name}.vtx[{v_idx}]", 
                query=True, 
                value=True
            )
            
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
        
        for joint in joints:
            try:
                # Get bind pre-matrix (inverse bind matrix)
                matrix_attr = f"{skin_cluster}.bindPreMatrix[{joints.index(joint)}]"
                matrix = cmds.getAttr(matrix_attr)
                bind_matrices[joint] = list(matrix)
            except:
                # Fallback to identity matrix
                bind_matrices[joint] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        
        return bind_matrices
    
    
    def _get_joint_bind_pose(self, joint: str) -> List[float]:
        """Get joint's bind pose transform"""
        try:
            # Try to get from bind pose node
            dag_pose_nodes = cmds.ls(type='dagPose')
            for pose_node in dag_pose_nodes:
                if cmds.dagPose(joint, query=True, bindPose=True, name=pose_node):
                    matrix = cmds.dagPose(joint, query=True, worldMatrix=True, name=pose_node)
                    return matrix
        except:
            pass
        
        # Fallback to current world transform
        return self._extract_transform(joint)
