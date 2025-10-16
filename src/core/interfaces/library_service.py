"""
Asset Library Service Interface
Handles library-specific operations like adding/removing assets to/from library
Separates library management from generic asset repository operations
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple
from ..models.asset import Asset


class ILibraryService(ABC):
    """
    Library Service Interface - SOLID: Interface Segregation Principle
    
    Handles library-specific operations:
    - Adding assets to library (file copying + repository update)
    - Removing assets from library (file deletion + repository update)
    - Managing library state coordination
    """
    
    @abstractmethod
    def add_asset_to_library(
        self, 
        source_path: Path, 
        project_path: Path
    ) -> Optional[Tuple[bool, Optional[Path]]]:
        """
        Add asset to library - copies file and updates repository with new path
        
        Args:
            source_path: Original asset file path
            project_path: Target project directory
            
        Returns:
            Tuple of (success: bool, new_path: Optional[Path])
        """
        pass
    
    @abstractmethod
    def remove_asset_from_library(self, asset: Asset) -> bool:
        """
        Remove asset from library - deletes file and updates repository
        
        Args:
            asset: Asset to remove
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_library_path_for_asset(
        self, 
        source_path: Path, 
        project_path: Path
    ) -> Path:
        """
        Calculate target library path for an asset
        
        Args:
            source_path: Original asset file path
            project_path: Project directory
            
        Returns:
            Calculated target path in library
        """
        pass
