# -*- coding: utf-8 -*-
"""
USD Export Service Interface
Defines contract for Maya → USD export orchestration

Author: Mike Stumbo
Version: 1.4.0
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class USDExportOptions:
    """Configuration for USD export operations"""
    
    # Output settings
    output_path: Path
    file_format: str = "usda"  # usda (ASCII) or usdc (binary) or usdz (package)
    
    # Geometry options
    export_meshes: bool = True
    export_normals: bool = True
    export_uvs: bool = True
    export_vertex_colors: bool = True
    triangulate: bool = False
    
    # Material options
    export_materials: bool = True
    convert_renderman: bool = True  # Convert RenderMan to UsdPreviewSurface
    export_textures: bool = True
    copy_textures: bool = False  # Copy texture files to USD location
    
    # Rigging options
    export_skeleton: bool = True
    export_skin_weights: bool = True
    export_blend_shapes: bool = True
    preserve_bind_pose: bool = True
    
    # Animation options
    export_animation: bool = False
    frame_range: Optional[tuple] = None  # (start, end) or None for current frame
    
    # Scene structure
    merge_transforms: bool = False  # Merge transform with shape
    use_display_color: bool = True  # Add displayColor primvar
    default_prim: Optional[str] = None  # Set default prim name
    
    # Performance
    verbose: bool = True


class IUSDExportService(ABC):
    """
    Interface for USD Export Service
    
    Responsibilities (Single Responsibility Principle):
    - Orchestrate Maya → USD export pipeline
    - Coordinate between parser, converters, and USD writer
    - Handle export options and validation
    - Provide progress reporting
    """
    
    @abstractmethod
    def export_maya_scene(
        self,
        maya_file: Path,
        options: USDExportOptions
    ) -> bool:
        """
        Export complete Maya scene to USD
        
        Args:
            maya_file: Path to Maya scene file (.ma or .mb)
            options: Export configuration
            
        Returns:
            True if export successful, False otherwise
            
        Clean Code: Single responsibility - orchestrate full export
        """
        pass
    
    @abstractmethod
    def export_selected_objects(
        self,
        options: USDExportOptions,
        object_names: Optional[List[str]] = None
    ) -> bool:
        """
        Export selected Maya objects to USD (requires Maya session)
        
        Args:
            options: Export configuration
            object_names: Specific object names, or None for current selection
            
        Returns:
            True if export successful, False otherwise
            
        Clean Code: Supports partial exports for flexibility
        """
        pass
    
    @abstractmethod
    def validate_export_options(self, options: USDExportOptions) -> tuple[bool, str]:
        """
        Validate export options before processing
        
        Args:
            options: Export configuration to validate
            
        Returns:
            (is_valid, error_message) - Empty string if valid
            
        Clean Code: Fail fast with clear error messages
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported USD file formats
        
        Returns:
            List of format extensions (e.g., ['usda', 'usdc', 'usdz'])
            
        Clean Code: Explicit about capabilities
        """
        pass
    
    @abstractmethod
    def estimate_export_time(
        self,
        maya_file: Path,
        options: USDExportOptions
    ) -> float:
        """
        Estimate export time in seconds (for progress UI)
        
        Args:
            maya_file: Path to Maya scene file
            options: Export configuration
            
        Returns:
            Estimated time in seconds, or -1 if cannot estimate
            
        Clean Code: User feedback for long operations
        """
        pass
    
    @abstractmethod
    def cancel_export(self) -> None:
        """
        Cancel ongoing export operation
        
        Clean Code: User control over long operations
        """
        pass
    
    @abstractmethod
    def get_export_progress(self) -> tuple[int, str]:
        """
        Get current export progress
        
        Returns:
            (percentage_complete, current_stage_description)
            
        Clean Code: Real-time feedback for UI
        """
        pass
    
    @abstractmethod
    def get_last_error(self) -> Optional[str]:
        """
        Get detailed error message from last failed export
        
        Returns:
            Error message or None if no error
            
        Clean Code: Detailed error reporting for debugging
        """
        pass
