# -*- coding: utf-8 -*-
"""
USD Rig Converter Interface  
Defines contract for converting Maya rigging to UsdSkel

Author: Mike Stumbo
Version: 1.4.0
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class UsdSkelData:
    """USD Skeleton data structure"""
    skeleton_path: str  # Path in USD stage
    joint_names: List[str]  # Joint topology
    bind_transforms: List[Any]  # Joint bind transforms (4x4 matrices)
    rest_transforms: List[Any]  # Joint rest transforms
    
    # Skinning
    joint_indices: List[List[int]]  # Per-vertex joint indices
    joint_weights: List[List[float]]  # Per-vertex weights


class IUSDRigConverter(ABC):
    """
    Interface for USD Rig Converter
    
    Responsibilities (Single Responsibility Principle):
    - Convert Maya skin clusters to UsdSkel
    - Preserve joint hierarchies and bind poses
    - Handle skin weight data accurately
    - Support blend shapes (if needed)
    
    Clean Code: Rigging conversion separated from geometry/materials
    Disney/Pixar Critical: UsdSkel is essential for animation pipelines
    """
    
    @abstractmethod
    def convert_skeleton(
        self,
        joint_data: List[Any],  # List[JointData]
        usd_stage: Any,  # pxr.Usd.Stage
        skeleton_path: str = "/Skeleton"
    ) -> Optional[Any]:  # pxr.UsdSkel.Skeleton
        """
        Convert Maya joint hierarchy to UsdSkel.Skeleton
        
        Args:
            joint_data: List of JointData from Maya parser
            usd_stage: USD stage to create skeleton in
            skeleton_path: Path for skeleton prim
            
        Returns:
            Created UsdSkel.Skeleton or None if failed
            
        Clean Code: Skeleton structure conversion
        """
        pass
    
    @abstractmethod
    def convert_skin_weights(
        self,
        skin_cluster_data: Any,  # SkinClusterData
        skeleton: Any,  # pxr.UsdSkel.Skeleton
        mesh_prim: Any  # pxr.Usd.Prim
    ) -> bool:
        """
        Convert Maya skin weights to USD skinning primvars
        
        Args:
            skin_cluster_data: Skin weights from Maya
            skeleton: USD skeleton to bind to
            mesh_prim: Mesh primitive to skin
            
        Returns:
            True if conversion successful
            
        Clean Code: Weight data conversion and binding
        Disney/Pixar Critical: Accurate weight preservation essential
        """
        pass
    
    @abstractmethod
    def create_bind_pose(
        self,
        skeleton: Any,  # pxr.UsdSkel.Skeleton
        joint_data: List[Any]  # List[JointData]
    ) -> bool:
        """
        Set skeleton bind pose from Maya joint transforms
        
        Args:
            skeleton: USD skeleton
            joint_data: Joint transforms from Maya
            
        Returns:
            True if bind pose set successfully
            
        Clean Code: Bind pose is explicit operation
        """
        pass
    
    @abstractmethod
    def validate_joint_topology(
        self,
        joint_data: List[Any]
    ) -> tuple[bool, str]:
        """
        Validate joint hierarchy is valid for USD
        
        Args:
            joint_data: Joint hierarchy from Maya
            
        Returns:
            (is_valid, error_message) - Empty string if valid
            
        Clean Code: Validation before processing
        """
        pass
    
    @abstractmethod
    def normalize_weights(
        self,
        weights: Dict[int, List[tuple]]
    ) -> Dict[int, List[tuple]]:
        """
        Normalize skin weights to sum to 1.0 per vertex
        
        Args:
            weights: Raw weight data {vertex_idx: [(joint_idx, weight), ...]}
            
        Returns:
            Normalized weights
            
        Clean Code: Weight normalization is separate utility
        """
        pass
    
    @abstractmethod
    def get_max_influences_per_vertex(
        self,
        skin_cluster_data: Any
    ) -> int:
        """
        Get maximum number of joint influences per vertex
        
        Args:
            skin_cluster_data: Skin cluster to analyze
            
        Returns:
            Max influences (typically 4 or 8 for games)
            
        Clean Code: Analyze data before processing
        """
        pass
    
    @abstractmethod
    def prune_zero_weights(
        self,
        weights: Dict[int, List[tuple]],
        threshold: float = 0.001
    ) -> Dict[int, List[tuple]]:
        """
        Remove weights below threshold to optimize data
        
        Args:
            weights: Weight data
            threshold: Minimum weight to keep
            
        Returns:
            Pruned weight data
            
        Clean Code: Optimization utility
        """
        pass
