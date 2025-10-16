# -*- coding: utf-8 -*-
"""
Maya Integration Interface  
Defines Maya-specific operations following Single Responsibility

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..models.asset import Asset


class IMayaIntegration(ABC):
    """
    Maya Integration Interface - Single Responsibility for Maya operations
    Follows Interface Segregation: only Maya-specific functionality
    """
    
    @abstractmethod
    def is_maya_available(self) -> bool:
        """
        Check if Maya is available for operations
        
        Returns:
            True if Maya is accessible
        """
        pass
    
    @abstractmethod
    def import_asset(self, asset: Asset, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Import asset into Maya scene
        
        Args:
            asset: Asset to import
            options: Import options and settings
            
        Returns:
            True if import was successful
        """
        pass
    
    @abstractmethod
    def reference_asset(self, asset: Asset, namespace: Optional[str] = None) -> bool:
        """
        Reference asset in Maya scene
        
        Args:
            asset: Asset to reference
            namespace: Optional namespace for reference
            
        Returns:
            True if reference was successful
        """
        pass
    
    @abstractmethod
    def export_selection(self, export_path: Path, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Export Maya selection to file
        
        Args:
            export_path: Destination file path
            options: Export options and settings
            
        Returns:
            True if export was successful
        """
        pass
    
    @abstractmethod
    def get_scene_assets(self) -> List[str]:
        """
        Get list of assets currently in Maya scene
        
        Returns:
            List of asset paths in current scene
        """
        pass
    
    @abstractmethod
    def validate_asset_compatibility(self, asset: Asset) -> bool:
        """
        Check if asset is compatible with current Maya version
        
        Args:
            asset: Asset to validate
            
        Returns:
            True if asset is compatible
        """
        pass
    
    @abstractmethod
    def get_maya_version(self) -> Optional[str]:
        """
        Get current Maya version
        
        Returns:
            Maya version string, None if Maya not available
        """
        pass
