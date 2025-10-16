# -*- coding: utf-8 -*-
"""
Asset Repository Implementation
Concrete implementation of asset CRUD operations

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import os
import json
import hashlib
from typing import List, Optional, Dict, Any, Set
from pathlib import Path
from datetime import datetime

from ..core.interfaces.asset_repository import IAssetRepository
from ..core.interfaces.metadata_extractor import IMetadataExtractor
from ..core.models.asset import Asset
from ..core.models.search_criteria import SearchCriteria, SortBy, SortOrder
from ..config.constants import SEARCH_CONFIG, PERFORMANCE_CONFIG
from ..config.constants import SEARCH_CONFIG, PERFORMANCE_CONFIG


class AssetRepositoryImpl(IAssetRepository):
    """
    Asset Repository Implementation - Single Responsibility for asset data operations
    Implements Repository Pattern for data access abstraction
    """
    
    def __init__(self, metadata_extractor: IMetadataExtractor):
        self._metadata_extractor = metadata_extractor
        self._asset_cache: Dict[str, Asset] = {}
        self._favorites_file = Path.home() / ".assetmanager" / "favorites.json"
        self._recent_file = Path.home() / ".assetmanager" / "recent.json"
        self._removed_file = Path.home() / ".assetmanager" / "removed_assets.json"
        self._supported_extensions = {
            '.ma', '.mb', '.mel',  # Maya files
            '.obj', '.fbx', '.abc', '.usd',  # 3D formats
            '.png', '.jpg', '.jpeg', '.tiff', '.tga', '.exr', '.hdr',  # Images
            '.mov', '.mp4', '.avi',  # Video
            '.mtl', '.mat',  # Material files
            '.zip', '.rar'  # Compressed assets
            # Note: .txt, .md, .json removed to prevent project files from appearing
        }
        
        # Ensure config directory exists
        self._ensure_config_directory()
    
    def _ensure_config_directory(self) -> None:
        """Create configuration directory if it doesn't exist"""
        config_dir = Path.home() / ".assetmanager"
        config_dir.mkdir(exist_ok=True)
    
    def _generate_asset_id(self, file_path: Path) -> str:
        """Generate unique asset ID from file path"""
        path_str = str(file_path.resolve())
        return hashlib.md5(path_str.encode()).hexdigest()
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file extension is supported and not a project management file"""
        # Check if extension is supported
        if file_path.suffix.lower() not in self._supported_extensions:
            return False
        
        # Exclude project management files
        project_files = {
            'project.json',
            'README.md', 
            'readme.md',
            '.gitignore',
            '.assetmanager'
        }
        
        if file_path.name.lower() in project_files:
            return False
            
        # Exclude hidden files and system files
        if file_path.name.startswith('.'):
            return False
            
        # Exclude files in temp directories
        if 'temp' in file_path.parts or 'tmp' in file_path.parts:
            return False
            
        return True
    
    def _create_asset_from_path(self, file_path: Path) -> Optional[Asset]:
        """
        Create Asset object from file path
        Single Responsibility: asset creation logic
        """
        try:
            if not file_path.exists() or not self._is_supported_file(file_path):
                return None
            
            # Generate unique ID
            asset_id = self._generate_asset_id(file_path)
            
            # Extract metadata
            metadata = self._metadata_extractor.extract_metadata(file_path)
            
            # Determine asset type
            asset_type = self._determine_asset_type(file_path)
            
            # Create asset
            asset = Asset(
                id=asset_id,
                name=file_path.stem,
                file_path=file_path,
                file_extension=file_path.suffix.lower(),
                file_size=metadata.file_size,
                created_date=metadata.created_date,
                modified_date=metadata.modified_date,
                asset_type=asset_type,
                metadata=metadata.custom_properties
            )
            
            return asset
            
        except Exception as e:
            # Log error but don't crash
            print(f"Error creating asset from {file_path}: {e}")
            return None
    
    def _determine_asset_type(self, file_path: Path) -> str:
        """Determine asset type from file extension"""
        ext = file_path.suffix.lower()
        
        if ext in {'.ma', '.mb', '.mel'}:
            return 'maya_scene'
        elif ext in {'.obj', '.fbx', '.abc', '.usd'}:
            return '3d_model'
        elif ext in {'.png', '.jpg', '.jpeg', '.tiff', '.tga', '.exr', '.hdr'}:
            return 'image'
        elif ext in {'.mov', '.mp4', '.avi'}:
            return 'video'
        elif ext in {'.mtl', '.mat'}:
            return 'material'
        elif ext in {'.zip', '.rar'}:
            return 'archive'
        else:
            return 'unknown'
    
    def find_all(self, directory: Path) -> List[Asset]:
        """
        Discover all assets in a directory
        Implements recursive file discovery with caching
        """
        assets = []
        
        if not directory.exists():
            return assets
        
        try:
            # Recursive file discovery
            for file_path in directory.rglob('*'):
                if (file_path.is_file() and 
                    self._is_supported_file(file_path) and 
                    not self._is_asset_removed(file_path)):  # Filter out removed assets
                    asset = self._create_asset_from_path(file_path)
                    if asset:
                        assets.append(asset)
                        # Cache for faster subsequent access
                        self._asset_cache[asset.id] = asset
            
            return assets
            
        except Exception as e:
            print(f"Error discovering assets in {directory}: {e}")
            return []
    
    def find_by_criteria(self, criteria: SearchCriteria) -> List[Asset]:
        """
        Find assets matching search criteria
        Implements Specification Pattern for flexible filtering
        """
        assets = []
        
        # Get assets from specified directories or use cache
        if criteria.search_directories:
            for directory in criteria.search_directories:
                assets.extend(self.find_all(directory))
        else:
            assets = list(self._asset_cache.values())
        
        # Apply filters
        filtered_assets = self._apply_filters(assets, criteria)
        
        # Apply sorting
        sorted_assets = self._apply_sorting(filtered_assets, criteria)
        
        # Apply pagination
        paginated_assets = self._apply_pagination(sorted_assets, criteria)
        
        return paginated_assets
    
    def _apply_filters(self, assets: List[Asset], criteria: SearchCriteria) -> List[Asset]:
        """Apply search criteria filters to asset list"""
        filtered = assets
        
        # Text search filter
        if criteria.has_text_search and criteria.search_text:
            if not criteria.case_sensitive:
                search_text = criteria.search_text.lower()
                filtered = [a for a in filtered if search_text in a.name.lower()]
            else:
                filtered = [a for a in filtered if criteria.search_text in a.name]
        
        # File extension filter
        if criteria.file_extensions:
            filtered = [a for a in filtered if a.file_extension.lstrip('.') in criteria.file_extensions]
        
        # Asset type filter
        if criteria.asset_types:
            filtered = [a for a in filtered if a.asset_type in criteria.asset_types]
        
        # Size filters
        if criteria.has_size_filters:
            if criteria.min_file_size is not None:
                filtered = [a for a in filtered if a.file_size >= criteria.min_file_size]
            if criteria.max_file_size is not None:
                filtered = [a for a in filtered if a.file_size <= criteria.max_file_size]
        
        # Tag filters
        if criteria.has_tag_filters:
            if criteria.required_tags:
                filtered = [a for a in filtered if criteria.required_tags.issubset(set(a.tags))]
            if criteria.excluded_tags:
                filtered = [a for a in filtered if not criteria.excluded_tags.intersection(set(a.tags))]
        
        # Special filters
        if criteria.favorites_only:
            favorites = self._load_favorites()
            favorite_ids = {fav['id'] for fav in favorites}
            filtered = [a for a in filtered if a.id in favorite_ids]
        
        if criteria.recently_accessed:
            filtered = [a for a in filtered if a.last_accessed is not None]
        
        return filtered
    
    def _apply_sorting(self, assets: List[Asset], criteria: SearchCriteria) -> List[Asset]:
        """Apply sorting to asset list"""
        reverse = criteria.sort_order == SortOrder.DESCENDING
        
        if criteria.sort_by == SortBy.NAME:
            return sorted(assets, key=lambda a: a.name.lower(), reverse=reverse)
        elif criteria.sort_by == SortBy.DATE_CREATED:
            return sorted(assets, key=lambda a: a.created_date or datetime.min, reverse=reverse)
        elif criteria.sort_by == SortBy.DATE_MODIFIED:
            return sorted(assets, key=lambda a: a.modified_date or datetime.min, reverse=reverse)
        elif criteria.sort_by == SortBy.DATE_ACCESSED:
            return sorted(assets, key=lambda a: a.last_accessed or datetime.min, reverse=reverse)
        elif criteria.sort_by == SortBy.FILE_SIZE:
            return sorted(assets, key=lambda a: a.file_size, reverse=reverse)
        elif criteria.sort_by == SortBy.ACCESS_COUNT:
            return sorted(assets, key=lambda a: a.access_count, reverse=reverse)
        elif criteria.sort_by == SortBy.ASSET_TYPE:
            return sorted(assets, key=lambda a: a.asset_type, reverse=reverse)
        else:
            return assets
    
    def _apply_pagination(self, assets: List[Asset], criteria: SearchCriteria) -> List[Asset]:
        """Apply pagination to asset list"""
        if criteria.limit is None:
            return assets[criteria.offset:]
        else:
            end_index = criteria.offset + criteria.limit
            return assets[criteria.offset:end_index]
    
    def find_by_id(self, asset_id: str) -> Optional[Asset]:
        """Find specific asset by unique identifier"""
        return self._asset_cache.get(asset_id)
    
    def get_recent_assets(self, limit: int = 20) -> List[Asset]:
        """Get recently accessed assets"""
        recent_data = self._load_recent()
        recent_assets = []
        
        for item in recent_data[:limit]:
            asset = self.find_by_id(item['id'])
            if asset:
                recent_assets.append(asset)
        
        return recent_assets
    
    def get_favorites(self) -> List[Asset]:
        """Get user's favorite assets"""
        favorites_data = self._load_favorites()
        favorite_assets = []
        
        for item in favorites_data:
            asset = self.find_by_id(item['id'])
            if asset:
                asset.is_favorite = True
                favorite_assets.append(asset)
        
        return favorite_assets
    
    def add_to_favorites(self, asset: Asset) -> bool:
        """Add asset to favorites"""
        try:
            favorites = self._load_favorites()
            
            # Check if already in favorites
            if any(fav['id'] == asset.id for fav in favorites):
                return True
            
            # Add to favorites
            favorites.append({
                'id': asset.id,
                'name': asset.name,
                'file_path': str(asset.file_path),
                'added_date': datetime.now().isoformat()
            })
            
            # Limit favorites
            if len(favorites) > SEARCH_CONFIG.MAX_FAVORITES:
                favorites = favorites[-SEARCH_CONFIG.MAX_FAVORITES:]
            
            self._save_favorites(favorites)
            asset.is_favorite = True
            return True
            
        except Exception as e:
            print(f"Error adding to favorites: {e}")
            return False
    
    def remove_from_favorites(self, asset: Asset) -> bool:
        """Remove asset from favorites"""
        try:
            favorites = self._load_favorites()
            favorites = [fav for fav in favorites if fav['id'] != asset.id]
            
            self._save_favorites(favorites)
            asset.is_favorite = False
            return True
            
        except Exception as e:
            print(f"Error removing from favorites: {e}")
            return False
    
    def update_access_time(self, asset: Asset) -> None:
        """Update last access time for asset"""
        asset.update_access()
        
        # Update recent assets
        try:
            recent = self._load_recent()
            
            # Remove if already present
            recent = [item for item in recent if item['id'] != asset.id]
            
            # Add to beginning
            recent.insert(0, {
                'id': asset.id,
                'name': asset.name,
                'file_path': str(asset.file_path),
                'access_date': datetime.now().isoformat()
            })
            
            # Limit recent items
            if len(recent) > SEARCH_CONFIG.MAX_RECENT_ASSETS:
                recent = recent[:SEARCH_CONFIG.MAX_RECENT_ASSETS]
            
            self._save_recent(recent)
            
        except Exception as e:
            print(f"Error updating access time: {e}")
    
    def _load_favorites(self) -> List[Dict[str, Any]]:
        """Load favorites from file"""
        try:
            if self._favorites_file.exists():
                with open(self._favorites_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []
    
    def _save_favorites(self, favorites: List[Dict[str, Any]]) -> None:
        """Save favorites to file"""
        try:
            with open(self._favorites_file, 'w') as f:
                json.dump(favorites, f, indent=2)
        except Exception as e:
            print(f"Error saving favorites: {e}")
    
    def _load_recent(self) -> List[Dict[str, Any]]:
        """Load recent assets from file"""
        try:
            if self._recent_file.exists():
                with open(self._recent_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []
    
    def _save_recent(self, recent: List[Dict[str, Any]]) -> None:
        """Save recent assets to file"""
        try:
            with open(self._recent_file, 'w') as f:
                json.dump(recent, f, indent=2)
        except Exception as e:
            print(f"Error saving recent assets: {e}")
    
    def _load_removed_assets(self) -> List[str]:
        """Load list of removed asset paths - Single Responsibility"""
        try:
            if self._removed_file.exists():
                with open(self._removed_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading removed assets: {e}")
            return []
    
    def _save_removed_assets(self, removed_paths: List[str]) -> None:
        """Save list of removed asset paths - Single Responsibility"""
        try:
            with open(self._removed_file, 'w') as f:
                json.dump(removed_paths, f, indent=2)
        except Exception as e:
            print(f"Error saving removed assets: {e}")
    
    def _is_asset_removed(self, asset_path: Path) -> bool:
        """Check if asset is in the removed list - Single Responsibility"""
        removed_paths = self._load_removed_assets()
        return str(asset_path) in removed_paths
    
    def remove_asset(self, asset: Asset) -> bool:
        """
        Remove an asset from the repository and optionally from file system - Single Responsibility
        
        Args:
            asset: The asset to remove
            
        Returns:
            bool: True if removal was successful, False otherwise
        """
        try:
            # Add to removed assets list (blacklist approach - safer than file deletion)
            removed_paths = self._load_removed_assets()
            asset_path_str = str(asset.file_path)
            if asset_path_str not in removed_paths:
                removed_paths.append(asset_path_str)
                self._save_removed_assets(removed_paths)
            
            # Remove from cache
            if asset.id in self._asset_cache:
                del self._asset_cache[asset.id]
            
            # Remove from favorites if present
            favorites = self._load_favorites()
            favorites = [fav for fav in favorites if fav.get('id') != asset.id]
            self._save_favorites(favorites)
            
            # Remove from recent if present
            recent = self._load_recent()
            recent = [rec for rec in recent if rec.get('id') != asset.id]
            self._save_recent(recent)
            
            print(f"Asset {asset.display_name} removed from repository (file preserved)")
            
            return True
            
        except Exception as e:
            print(f"Error removing asset {asset.display_name}: {e}")
            return False
    
    def restore_asset(self, asset_path: Path) -> bool:
        """
        Restore a previously removed asset - Single Responsibility
        
        Args:
            asset_path: Path to the asset file to restore
            
        Returns:
            bool: True if restoration was successful, False otherwise
        """
        try:
            removed_paths = self._load_removed_assets()
            asset_path_str = str(asset_path)
            
            if asset_path_str in removed_paths:
                removed_paths.remove(asset_path_str)
                self._save_removed_assets(removed_paths)
                print(f"Asset {asset_path.name} restored to repository")
                return True
            else:
                print(f"Asset {asset_path.name} was not in removed list")
                return False
                
        except Exception as e:
            print(f"Error restoring asset {asset_path.name}: {e}")
            return False

    def get_asset_by_path(self, file_path: Path) -> Optional[Asset]:
        """
        Get asset by file path - Single Responsibility
        
        Args:
            file_path: Path to the asset file
            
        Returns:
            Asset object if found, None otherwise
        """
        try:
            # Generate ID from path
            asset_id = self._generate_asset_id(file_path)
            
            # Check cache first
            if asset_id in self._asset_cache:
                return self._asset_cache[asset_id]
            
            # Try to create asset from path
            asset = self._create_asset_from_path(file_path)
            if asset:
                self._asset_cache[asset_id] = asset
                return asset
            
            return None
            
        except Exception as e:
            print(f"Error getting asset by path {file_path}: {e}")
            return None
    
    def update_asset(self, asset: Asset) -> bool:
        """
        Update asset in repository - Single Responsibility
        
        Args:
            asset: The asset with updated data
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Update cache
            self._asset_cache[asset.id] = asset
            
            # Note: In a full database implementation, this would save to persistent storage
            # For now, the cache serves as temporary storage until next refresh
            print(f"✅ Asset updated in repository: {asset.display_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating asset {asset.display_name}: {e}")
            return False
