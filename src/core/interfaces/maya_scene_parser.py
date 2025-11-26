# -*- coding: utf-8 -*-
"""
Maya Scene Parser Interface
Defines contract for extracting data from Maya scenes

Author: Mike Stumbo
Version: 1.5.0 - NURBS Curves & Alembic Support!
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
    bind_pose_matrix: List[float]  # 4x4 matrix in LOCAL space (objectSpace=True)
    world_bind_matrix: List[float]  # 4x4 matrix in WORLD space (worldSpace=True)

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
class NurbsCurveData:
    """NURBS curve data for rig controls - INDUSTRY FIRST!

    This enables full character rig export to USD with control curves.
    Most pipelines skip rig controls - this is groundbreaking!
    """
    name: str
    transform_name: str

    # Curve geometry
    control_vertices: List[tuple]  # [(x, y, z), ...] CV positions
    degree: int  # Curve degree (1=linear, 3=cubic)
    form: str  # "open" or "closed" (periodic)
    knots: List[float]  # Knot vector

    # Transform
    world_matrix: Optional[List[float]] = None  # 4x4 matrix as 16 floats
    local_matrix: Optional[List[float]] = None  # Local transform

    # Hierarchy
    parent_name: Optional[str] = None
    children: List[str] = field(default_factory=list)

    # Metadata
    color: Optional[tuple] = None  # (r, g, b) override color
    line_width: Optional[float] = None

    # Custom attributes (for rig controls)
    custom_attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RigConnectionData:
    """Rigging connection data for preserving controller functionality

    INDUSTRY FIRST: Complete rig controller preservation in USD!
    This enables functional rig round-tripping with constraints and connections.
    """
    source_node: str  # Node providing the value (e.g., "L_arm_ctrl.translateX")
    target_node: str  # Node receiving the value (e.g., "L_arm_joint.rotateX")
    source_attr: str  # Attribute name on source (e.g., "translateX")
    target_attr: str  # Attribute name on target (e.g., "rotateX")

    # Connection type
    connection_type: str  # "direct", "constraint", "setDrivenKey"

    # For constraints
    constraint_type: Optional[str] = None  # "parent", "point", "orient", "scale"
    constraint_node: Optional[str] = None  # Name of constraint node

    # For set-driven keys
    driver_value: Optional[float] = None
    driven_value: Optional[float] = None

    # Connection metadata
    is_input: bool = True  # True if source drives target, False if target drives source


@dataclass
class ConstraintData:
    """Maya constraint data for rig controllers"""
    name: str
    constraint_type: str  # "parentConstraint", "pointConstraint", "orientConstraint", etc.

    # Constraint targets (what the constraint is constraining)
    target_node: str
    target_attrs: List[str]  # ["translate", "rotate", "scale"] or specific attrs

    # Constraint drivers (what's driving the constraint)
    driver_nodes: List[str]  # List of nodes driving this constraint
    driver_weights: Dict[str, float] = field(default_factory=dict)  # {driver_node: weight}

    # Constraint settings
    maintain_offset: bool = False
    interpolate: bool = True


@dataclass
class SetDrivenKeyData:
    """Maya set-driven key data for rig controllers"""
    driver_node: str
    driver_attr: str
    driven_node: str
    driven_attr: str

    # Keyframe data
    driver_values: List[float]
    driven_values: List[float]

    # Interpolation
    interpolation: str = "linear"  # "linear", "spline", "step"


@dataclass
class MayaSceneData:
    """Complete Maya scene data structure"""
    source_file: Optional[Path]  # None when parsing current unsaved scene

    # Scene contents
    meshes: List[MeshData] = field(default_factory=list)
    materials: List[MaterialData] = field(default_factory=list)
    joints: List[JointData] = field(default_factory=list)
    skin_clusters: List[SkinClusterData] = field(default_factory=list)
    nurbs_curves: List[NurbsCurveData] = field(default_factory=list)  # NEW: Rig controls!

    # NEW: Rig connections for functional controllers!
    rig_connections: List[RigConnectionData] = field(default_factory=list)
    constraints: List[ConstraintData] = field(default_factory=list)
    set_driven_keys: List[SetDrivenKeyData] = field(default_factory=list)

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
    def extract_nurbs_curves(
        self,
        curve_names: Optional[List[str]] = None,
        include_hierarchy: bool = True
    ) -> List[NurbsCurveData]:
        """
        Extract NURBS curves (rig controls) from Maya scene

        INDUSTRY FIRST: Full rig control export to USD!
        This enables complete character rigs with controls in USD pipelines.

        Args:
            curve_names: Specific curves to extract, or None for all
            include_hierarchy: Preserve parent/child relationships

        Returns:
            List of NURBS curve data structures

        Clean Code: Separates curve extraction from other geometry
        Production Critical: Enables full rig round-tripping
        """
        pass

    @abstractmethod
    def extract_rig_connections(
        self,
        nurbs_curves: List[NurbsCurveData]
    ) -> List[RigConnectionData]:
        """
        Extract rigging connections for NURBS curve controllers

        INDUSTRY FIRST: Functional rig controller preservation!
        This enables complete rig functionality round-tripping through USD.

        Args:
            nurbs_curves: List of NURBS curves to extract connections for

        Returns:
            List of rig connection data structures

        Clean Code: Separates connection extraction from geometry
        Production Critical: Makes controllers actually functional after import
        """
        pass

    @abstractmethod
    def extract_constraints(
        self,
        nurbs_curves: List[NurbsCurveData]
    ) -> List[ConstraintData]:
        """
        Extract Maya constraints involving NURBS curve controllers

        Args:
            nurbs_curves: List of NURBS curves to check for constraints

        Returns:
            List of constraint data structures
        """
        pass

    @abstractmethod
    def extract_set_driven_keys(
        self,
        nurbs_curves: List[NurbsCurveData]
    ) -> List[SetDrivenKeyData]:
        """
        Extract set-driven keys involving NURBS curve controllers

        Args:
            nurbs_curves: List of NURBS curves to check for SDKs

        Returns:
            List of set-driven key data structures
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
