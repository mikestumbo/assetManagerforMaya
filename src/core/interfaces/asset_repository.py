# -*- coding: utf-8 -*-
"""
Asset Repository Interface
Defines asset CRUD operations following Interface Segregation Principle

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path

from ..models.asset import Asset
from ..models.search_criteria import SearchCriteria


class IAssetRepository(ABC):
    """
    Asset Repository Interface - Single Responsibility for asset data operations
    Follows Interface Segregation: only asset-related operations
    """
    
    @abstractmethod
    def find_all(self, directory: Path) -> List[Asset]:
        """
        Discover all assets in a directory
        
        Args:
            directory: Root directory to search
            
        Returns:
            List of discovered assets
        """
        pass
    
    @abstractmethod
    def find_by_criteria(self, criteria: SearchCriteria) -> List[Asset]:
        """
        Find assets matching search criteria
        
        Args:
            criteria: Search specifications
            
        Returns:
            Filtered list of assets
        """
        pass
    
    @abstractmethod
    def find_by_id(self, asset_id: str) -> Optional[Asset]:
        """
        Find specific asset by unique identifier
        
        Args:
            asset_id: Unique asset identifier
            
        Returns:
            Asset if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_recent_assets(self, limit: int = 20) -> List[Asset]:
        """
        Get recently accessed assets
        
        Args:
            limit: Maximum number of recent assets
            
        Returns:
            List of recently used assets
        """
        pass
    
    @abstractmethod
    def get_favorites(self) -> List[Asset]:
        """
        Get user's favorite assets
        
        Returns:
            List of favorited assets
        """
        pass
    
    @abstractmethod
    def add_to_favorites(self, asset: Asset) -> bool:
        """
        Add asset to favorites
        
        Args:
            asset: Asset to favorite
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def remove_from_favorites(self, asset: Asset) -> bool:
        """
        Remove asset from favorites
        
        Args:
            asset: Asset to unfavorite
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def update_access_time(self, asset: Asset) -> None:
        """
        Update last access time for asset
        
        Args:
            asset: Asset that was accessed
        """
        pass
    
    @abstractmethod
    def remove_asset(self, asset: Asset) -> bool:
        """
        Remove an asset from the repository and optionally from file system.
        
        Args:
            asset: The asset to remove
            
        Returns:
            bool: True if removal was successful, False otherwise
            
        Raises:
            AssetNotFoundError: If the asset doesn't exist in the repository
            PermissionError: If insufficient permissions to delete files
        """
        pass
    
    @abstractmethod
    def get_assets_from_directory(self, directory: str) -> List[Asset]:
        """
        Get a list of assets from the specified directory.
        
        Args:
            directory: The directory path as a string
            
        Returns:
            List of assets found in the directory
        """
        pass
