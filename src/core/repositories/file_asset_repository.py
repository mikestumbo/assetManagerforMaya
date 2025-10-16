# -*- coding: utf-8 -*-
"""
File Asset Repository
Concrete implementation of IAssetRepository for file-based assets

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import os
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..interfaces.asset_repository import IAssetRepository
from ..models.asset import Asset
from ..exceptions import AssetNotFoundError

class FileAssetRepository(IAssetRepository):
    """
    File Asset Repository - Concrete implementation for managing assets in files
    Follows Clean Architecture with dependency injection
    """
    
    def __init__(self, asset_directories: Optional[List[Path]] = None):
        # Internal asset list - in-memory tracking of assets
        self._assets: List[Asset] = []
        
        # Cache for asset lookups by file path
        self._asset_cache: Dict[str, Asset] = {}
        
        # Asset directories to scan for assets
        self._asset_directories: List[Path] = asset_directories or []
        
        # Initialize repository (e.g., load existing assets from file system)
        self._load_assets()
    
    def set_asset_directories(self, directories: List[Path]) -> None:
        """Set the asset directories and reload assets"""
        self._asset_directories = directories
        self._load_assets()
    
    def add_asset_directory(self, directory: Path) -> None:
        """Add a new asset directory and scan for assets"""
        if directory not in self._asset_directories:
            self._asset_directories.append(directory)
            # Only scan the new directory
            if directory.exists():
                for file_path in directory.rglob("*"):
                    if file_path.is_file():
                        self._add_asset_file(file_path)

    def _load_assets(self) -> None:
        """Load assets from configured directories - Single Responsibility"""
        try:
            # Clear existing assets
            self._assets.clear()
            self._asset_cache.clear()
            
            # Load from each configured asset directory
            for asset_dir in self._asset_directories:
                if not asset_dir.exists():
                    continue  # Skip missing directories
                
                # Recursively find all asset files
                for file_path in asset_dir.rglob("*"):
                    if file_path.is_file():
                        self._add_asset_file(file_path)
        
        except Exception as e:
            print(f"Error loading assets: {e}")
    
    def _add_asset_file(self, file_path: Path) -> None:
        """Add a single asset file to the repository - Single Responsibility"""
        try:
            # Skip if already added
            if str(file_path) in self._asset_cache:
                return
            
            # Extract asset information from file path
            file_stats = file_path.stat()
            file_size = file_stats.st_size
            file_extension = file_path.suffix.lower()
            name = file_path.stem
            
            # Generate unique ID based on file path and modification time
            asset_id = hashlib.md5(f"{file_path}_{file_stats.st_mtime}".encode()).hexdigest()
            
            # Create asset from file with all required parameters
            asset = Asset(
                id=asset_id,
                name=name,
                file_path=file_path,
                file_extension=file_extension,
                file_size=file_size
            )
            
            # Add to internal list and cache
            self._assets.append(asset)
            self._asset_cache[str(file_path)] = asset
        
        except Exception as e:
            print(f"Error adding asset file {file_path}: {e}")
    
    def get_all_assets(self) -> List[Asset]:
        """Get all assets in the repository"""
        return list(self._assets)
    
    def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        """Get a single asset by its unique ID"""
        for asset in self._assets:
            if asset.id == asset_id:
                return asset
        return None
    
    def add_asset(self, asset: Asset) -> bool:
        """
        Add a new asset to the repository.
        
        Args:
            asset: The asset to add
            
        Returns:
            bool: True if addition was successful, False otherwise
        """
        try:
            # Avoid duplicates
            if asset in self._assets:
                return False
            
            # Add to internal list
            self._assets.append(asset)
            
            # Update cache
            self._asset_cache[str(asset.file_path)] = asset
            
            return True
        
        except Exception as e:
            print(f"Error adding asset {asset.display_name}: {e}")
            return False
    
    def remove_asset(self, asset: Asset) -> bool:
        """
        Remove an asset from the repository and optionally from file system.
        
        Args:
            asset: The asset to remove
            
        Returns:
            bool: True if removal was successful, False otherwise
        """
        try:
            # Remove from internal tracking
            if hasattr(self, '_assets') and asset in self._assets:
                self._assets.remove(asset)
            
            # Remove from any cached collections
            if hasattr(self, '_asset_cache'):
                self._asset_cache.pop(str(asset.file_path), None)
            
            # Optionally remove the actual file (be careful!)
            if asset.file_path.exists():
                try:
                    # Only remove if it's actually an asset file we manage
                    if self._is_managed_asset_file(asset.file_path):
                        asset.file_path.unlink()  # Delete the file
                        
                        # Also remove any associated metadata files
                        metadata_file = asset.file_path.with_suffix('.meta')
                        if metadata_file.exists():
                            metadata_file.unlink()
                            
                except PermissionError as e:
                    print(f"Permission denied removing file {asset.file_path}: {e}")
                    return False
                except Exception as e:
                    print(f"Error removing file {asset.file_path}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error removing asset {asset.display_name}: {e}")
            return False
    
    def _is_managed_asset_file(self, file_path: Path) -> bool:
        """
        Check if a file path is within our managed asset directories.
        This prevents accidentally deleting files outside our control.
        """
        try:
            # Check if the file is within our configured asset directories
            for asset_dir in self._asset_directories:
                if file_path.is_relative_to(asset_dir):
                    return True
            
            # Fallback: check common asset file extensions
            asset_extensions = {'.ma', '.mb', '.fbx', '.obj', '.abc', '.usd', '.usda', '.usdc'}
            return file_path.suffix.lower() in asset_extensions
            
        except Exception:
            return False
    
    def clear_all_assets(self) -> None:
        """Clear all assets from the repository - for testing or reset"""
        self._assets.clear()
        self._asset_cache.clear()
    
    # Additional methods as needed...