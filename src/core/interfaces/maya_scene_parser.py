# -*- coding: utf-8 -*-
"""
Maya Scene Parser Interface
Defines contract for extracting data from Maya scenes

Author: Mike Stumbo
Version: 1.4.0
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class MeshData:
    """Mesh geometry data extracted from Maya"""
    name: str
    transform_name: str
    
    # Geometry
    vertices: List[tuple]  # [(x, y, z), ...]
    face_vertex_counts: List[int]  # [4, 4, 3, ...] vertices per face
    face_vertex_indices: List[int]  # [0, 1, 2, 3, 4, 5, 6, 7, ...]
    
    # Attributes
    normals: Optional[List[tuple]] = None  # [(nx, ny, nz), ...]
    uvs: Optional[List[tuple]] = None  # [(u, v), ...]
    uv_indices: Optional[List[int]] = None
    vertex_colors: Optional[List[tuple]] = None  # [(r, g, b, a), ...]
    
    # Transform
    world_matrix: Optional[List[float]] = None  # 4x4 matrix as 16 floats
    
    # Material
    material_assignments: Dict[str, List[int]] = field(default_factory=dict)  # {material_name: [face_indices]}


@dataclass
class MaterialData:
    """Material data extracted from Maya"""
    name: str
    shader_type: str  # "lambert", "blinn", "PxrSurface", etc.
    
    # Common attributes
    diffuse_color: Optional[tuple] = None  # (r, g, b)
    specular_color: Optional[tuple] = None
    roughness: Optional[float] = None
    metallic: Optional[float] = None
    opacity: Optional[float] = 1.0
    
    # Texture maps
    diffuse_texture: Optional[Path] = None
    normal_texture: Optional[Path] = None
    roughness_texture: Optional[Path] = None
    metallic_texture: Optional[Path] = None
    
    # RenderMan specific
    is_renderman: bool = False
    renderman_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JointData:
    """Joint/bone data for rigging"""
    name: str
    parent_name: Optional[str]
    
    # Transform
    bind_pose_matrix: List[float]  # 4x4 matrix
    world_bind_matrix: List[float]
    
    # Hierarchy
    children: List[str] = field(default_factory=list)


@dataclass
class SkinClusterData:
    """Skin cluster (skin weights) data"""
    name: str
    mesh_name: str
    
    # Influences (joints affecting this mesh)
    influence_joints: List[str]
    
    # Weights per vertex
    # weights[vertex_index] = [(joint_index, weight), ...]
    weights: Dict[int, List[tuple]] = field(default_factory=dict)
    
    # Bind pre-matrix (for each influence)
    bind_pre_matrices: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class MayaSceneData:
    """Complete Maya scene data structure"""
    source_file: Path
    
    # Scene contents
    meshes: List[MeshData] = field(default_factory=list)
    materials: List[MaterialData] = field(default_factory=list)
    joints: List[JointData] = field(default_factory=list)
    skin_clusters: List[SkinClusterData] = field(default_factory=list)
    
    # Scene metadata
    units: str = "cm"  # Scene linear units
    up_axis: str = "y"  # Up axis (y or z)
    frame_rate: float = 24.0
    
    # Statistics
    total_vertices: int = 0
    total_faces: int = 0
    has_rigging: bool = False


class IMayaSceneParser(ABC):
    """
    Interface for Maya Scene Parser
    
    Responsibilities (Single Responsibility Principle):
    - Extract geometry data from Maya scenes
    - Parse material assignments and properties
    - Extract rigging data (joints, skin weights)
    - Provide clean data structures for USD conversion
    
    Clean Code: Parser responsibility - only reads and structures data
    """
    
    @abstractmethod
    def parse_maya_file(
        self,
        maya_file: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> MayaSceneData:
        """
        Parse Maya file and extract all relevant data
        
        Args:
            maya_file: Path to .ma or .mb file
            options: Optional parsing configuration
            
        Returns:
            Complete scene data structure
            
        Raises:
            FileNotFoundError: If Maya file doesn't exist
            ValueError: If file is invalid or corrupted
            
        Clean Code: Single entry point for file parsing
        """
        pass
    
    @abstractmethod
    def parse_selected_objects(
        self,
        object_names: Optional[List[str]] = None
    ) -> MayaSceneData:
        """
        Parse currently selected objects in active Maya session
        
        Args:
            object_names: Specific objects to parse, or None for selection
            
        Returns:
            Scene data for selected objects only
            
        Requires: Active Maya session (cmds available)
        
        Clean Code: Supports partial parsing for workflows
        """
        pass
    
    @abstractmethod
    def extract_mesh_data(self, mesh_name: str) -> MeshData:
        """
        Extract geometry data from specific mesh
        
        Args:
            mesh_name: Name of mesh node in Maya
            
        Returns:
            Complete mesh geometry data
            
        Clean Code: Single mesh extraction for modularity
        """
        pass
    
    @abstractmethod
    def extract_material_data(self, material_name: str) -> MaterialData:
        """
        Extract material properties and textures
        
        Args:
            material_name: Name of material/shader node
            
        Returns:
            Material data structure
            
        Clean Code: Material extraction separated from geometry
        """
        pass
    
    @abstractmethod
    def extract_skin_cluster(self, mesh_name: str) -> Optional[SkinClusterData]:
        """
        Extract skin weights for rigged mesh
        
        Args:
            mesh_name: Name of mesh with skin cluster
            
        Returns:
            Skin cluster data, or None if not rigged
            
        Clean Code: Optional rigging data (not all meshes are rigged)
        """
        pass
    
    @abstractmethod
    def get_joint_hierarchy(self, root_joint: Optional[str] = None) -> List[JointData]:
        """
        Extract joint hierarchy starting from root
        
        Args:
            root_joint: Root joint name, or None to find automatically
            
        Returns:
            List of joints in hierarchy order
            
        Clean Code: Preserves skeletal structure
        """
        pass
    
    @abstractmethod
    def validate_maya_file(self, maya_file: Path) -> tuple[bool, str]:
        """
        Validate Maya file before parsing
        
        Args:
            maya_file: Path to Maya file
            
        Returns:
            (is_valid, error_message) - Empty string if valid
            
        Clean Code: Fail fast with validation
        """
        pass
