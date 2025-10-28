# -*- coding: utf-8 -*-
"""
USD Material Converter Interface
Defines contract for converting Maya materials to USD

Author: Mike Stumbo
Version: 1.4.0
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path


class IUSDMaterialConverter(ABC):
    """
    Interface for USD Material Converter
    
    Responsibilities (Single Responsibility Principle):
    - Convert Maya materials to USD Preview Surface
    - Convert RenderMan materials to USD
    - Handle texture file references and paths
    - Preserve material properties during conversion
    
    Clean Code: Material conversion is separate concern from geometry
    """
    
    @abstractmethod
    def convert_to_preview_surface(
        self,
        material_name: str,
        material_data: Dict[str, Any],
        usd_stage: Any  # pxr.Usd.Stage
    ) -> Optional[Any]:  # pxr.UsdShade.Material
        """
        Convert Maya material to UsdPreviewSurface
        
        Args:
            material_name: Name for USD material
            material_data: Material properties from Maya
            usd_stage: USD stage to create material in
            
        Returns:
            Created UsdShade.Material or None if failed
            
        Clean Code: Standard USD Preview Surface workflow
        """
        pass
    
    @abstractmethod
    def convert_renderman_material(
        self,
        material_name: str,
        renderman_params: Dict[str, Any],
        usd_stage: Any
    ) -> Optional[Any]:
        """
        Convert RenderMan material to USD
        
        Args:
            material_name: Name for USD material
            renderman_params: RenderMan shader parameters
            usd_stage: USD stage to create material in
            
        Returns:
            Created UsdShade.Material with RenderMan shader
            
        Clean Code: RenderMan-specific conversion logic
        Disney/Pixar Compatibility: Preserves RenderMan workflows
        """
        pass
    
    @abstractmethod
    def map_texture_inputs(
        self,
        maya_texture_path: Path,
        usd_output_path: Path,
        copy_textures: bool = False
    ) -> str:
        """
        Map Maya texture file path to USD texture reference
        
        Args:
            maya_texture_path: Original Maya texture path
            usd_output_path: USD file output location
            copy_textures: Whether to copy textures to USD location
            
        Returns:
            USD texture path (relative or absolute)
            
        Clean Code: Texture path resolution separated from conversion
        """
        pass
    
    @abstractmethod
    def bind_material_to_geometry(
        self,
        geometry_prim: Any,  # pxr.Usd.Prim
        material: Any  # pxr.UsdShade.Material
    ) -> bool:
        """
        Bind USD material to geometry primitive
        
        Args:
            geometry_prim: USD geometry prim
            material: USD material to bind
            
        Returns:
            True if binding successful
            
        Clean Code: Material binding is explicit operation
        """
        pass
    
    @abstractmethod
    def get_supported_maya_shaders(self) -> list[str]:
        """
        Get list of supported Maya shader types
        
        Returns:
            List of shader type names (e.g., ['lambert', 'blinn', 'PxrSurface'])
            
        Clean Code: Explicit about capabilities
        """
        pass
    
    @abstractmethod
    def validate_texture_paths(
        self,
        texture_paths: list[Path]
    ) -> tuple[list[Path], list[Path]]:
        """
        Validate texture file paths exist
        
        Args:
            texture_paths: List of texture paths to validate
            
        Returns:
            (valid_paths, invalid_paths)
            
        Clean Code: Validation before processing
        """
        pass
