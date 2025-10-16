"""
Asset Library Service Implementation
Handles library-specific operations with proper file and repository coordination
"""

import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from ..core.interfaces.library_service import ILibraryService
from ..core.interfaces.asset_repository import IAssetRepository
from ..core.models.asset import Asset


class LibraryServiceImpl(ILibraryService):
    """
    Library Service Implementation - Clean Code: Single Responsibility
    
    Coordinates file operations with repository updates to ensure
    recent assets and library state remain consistent
    """
    
    def __init__(self, repository: IAssetRepository):
        """
        Initialize library service
        
        Args:
            repository: Asset repository for tracking assets
        """
        self.logger = logging.getLogger(__name__)
        self._repository = repository
    
    def add_asset_to_library(
        self, 
        source_path: Path, 
        project_path: Path
    ) -> Optional[Tuple[bool, Optional[Path]]]:
        """
        Add asset to library - ATOMIC operation
        
        This method:
        1. Copies asset file to appropriate library subdirectory
        2. Creates new Asset object with library path
        3. Updates repository recent assets with NEW path (not old path)
        
        Args:
            source_path: Original asset file path
            project_path: Target project directory
            
        Returns:
            Tuple of (success: bool, new_path: Optional[Path])
        """
        try:
            # Calculate target path
            target_path = self._calculate_target_path(source_path, project_path)
            
            # Create target directory if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle file name conflicts
            target_path = self._resolve_path_conflict(target_path)
            
            # Copy the file
            shutil.copy2(source_path, target_path)
            self.logger.info(f"Copied asset: {source_path.name} → {target_path}")
            
            # Create Asset object with NEW library path
            stat_info = target_path.stat()
            new_asset = Asset(
                id=str(target_path),  # CRITICAL: Use NEW path as ID
                name=target_path.stem,
                file_path=target_path,  # CRITICAL: Use NEW path
                file_extension=target_path.suffix,
                file_size=stat_info.st_size,
                asset_type=self._get_asset_type(target_path),
                created_date=datetime.fromtimestamp(stat_info.st_ctime),
                modified_date=datetime.fromtimestamp(stat_info.st_mtime),
                metadata={}
            )
            
            # Update repository with NEW asset (using library path)
            # This ensures recent assets list has correct path
            self._repository.update_access_time(new_asset)
            
            print(f"✅ Asset added to library: {target_path.name}")
            print(f"📌 Library path: {target_path.relative_to(project_path)}")
            print(f"� Full path: {target_path}")
            print(f"📌 Asset ID: {new_asset.id}")
            print(f"📌 File exists: {target_path.exists()}")
            print(f"�🔄 Recent assets updated with library path")
            
            return (True, target_path)
            
        except Exception as e:
            self.logger.error(f"Failed to add asset to library: {e}")
            print(f"❌ Failed to add asset to library: {e}")
            return (False, None)
    
    def remove_asset_from_library(self, asset: Asset) -> bool:
        """
        Remove asset from library - Clean Code: Error Handling
        
        Args:
            asset: Asset to remove
            
        Returns:
            True if successful
        """
        try:
            # Remove from repository first
            if not self._repository.remove_asset(asset):
                self.logger.warning(f"Failed to remove asset from repository: {asset.name}")
                return False
            
            # Remove custom screenshot if exists (Issue #4 fix)
            try:
                asset_dir = asset.file_path.parent
                asset_name = asset.file_path.stem
                thumbnail_dir = asset_dir / ".thumbnails"
                custom_screenshot = thumbnail_dir / f"{asset_name}_screenshot.png"
                
                if custom_screenshot.exists():
                    custom_screenshot.unlink()
                    print(f"🗑️ Deleted custom screenshot: {custom_screenshot.name}")
            except Exception as screenshot_error:
                self.logger.warning(f"Could not delete custom screenshot: {screenshot_error}")
            
            # Then remove asset file
            if asset.file_path.exists():
                asset.file_path.unlink()
                print(f"✅ Removed asset from library: {asset.name}")
                return True
            else:
                self.logger.warning(f"Asset file not found: {asset.file_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to remove asset from library: {e}")
            print(f"❌ Failed to remove asset: {e}")
            return False
    
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
        return self._calculate_target_path(source_path, project_path)
    
    def _calculate_target_path(self, source_path: Path, project_path: Path) -> Path:
        """
        Calculate target path based on file type - SOLID: Single Responsibility
        
        Args:
            source_path: Source file path
            project_path: Project root path
            
        Returns:
            Target path in appropriate subdirectory
        """
        # Ensure project_path is a Path object
        project_path = Path(project_path) if isinstance(project_path, str) else project_path
        assets_dir = project_path / "assets"
        
        # Determine subdirectory based on file type
        file_ext = source_path.suffix.lower()
        if file_ext in ['.ma', '.mb']:
            target_dir = assets_dir / "scenes"
        elif file_ext in ['.obj', '.fbx', '.abc', '.usd', '.usda', '.usdc']:
            target_dir = assets_dir / "models"
        elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.tga', '.exr', '.hdr']:
            target_dir = assets_dir / "textures"
        elif file_ext in ['.mtl', '.mat']:
            target_dir = assets_dir / "materials"
        elif file_ext in ['.mov', '.mp4', '.avi']:
            target_dir = assets_dir / "animations"
        elif file_ext in ['.zip', '.rar']:
            target_dir = assets_dir / "archives"
        else:
            target_dir = assets_dir  # Default to main assets folder
        
        return target_dir / source_path.name
    
    def _resolve_path_conflict(self, target_path: Path) -> Path:
        """
        Handle file name conflicts - Clean Code: Intention Revealing
        
        Args:
            target_path: Proposed target path
            
        Returns:
            Resolved path (may have counter suffix)
        """
        counter = 1
        original_path = target_path
        
        while target_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            target_path = original_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        return target_path
    
    def _get_asset_type(self, file_path: Path) -> str:
        """
        Determine asset type from extension - SOLID: Single Responsibility
        
        Args:
            file_path: Asset file path
            
        Returns:
            Asset type string
        """
        ext = file_path.suffix.lower()
        
        type_mapping = {
            '.ma': 'Maya ASCII',
            '.mb': 'Maya Binary',
            '.obj': 'OBJ Model',
            '.fbx': 'FBX Model',
            '.abc': 'Alembic Cache',
            '.usd': 'USD Scene',
            '.usda': 'USD ASCII',
            '.usdc': 'USD Crate',
            '.png': 'PNG Image',
            '.jpg': 'JPEG Image',
            '.jpeg': 'JPEG Image',
            '.tiff': 'TIFF Image',
            '.tga': 'TGA Image',
            '.exr': 'EXR Image',
            '.hdr': 'HDR Image',
            '.mov': 'QuickTime Movie',
            '.mp4': 'MP4 Video',
            '.avi': 'AVI Video',
        }
        
        return type_mapping.get(ext, 'Unknown')
