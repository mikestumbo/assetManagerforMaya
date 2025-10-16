# -*- coding: utf-8 -*-
"""
Thumbnail Service Interface
Defines thumbnail generation and caching operations

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from pathlib import Path


class IThumbnailService(ABC):
    """
    Thumbnail Service Interface - Single Responsibility for thumbnail operations
    Follows Interface Segregation: only thumbnail-related functionality
    """
    
    @abstractmethod
    def generate_thumbnail(self, file_path: Path, size: Tuple[int, int] = (64, 64), force_playblast: bool = False) -> Optional[str]:
        """
        Generate thumbnail for asset file
        
        Args:
            file_path: Path to asset file
            size: Thumbnail dimensions (width, height)
            force_playblast: If True, generate Maya playblast (imports asset to Maya)
                           If False, use simple file-type icon (no Maya import)
            
        Returns:
            Path to generated thumbnail, None if generation failed
        """
        pass
    
    @abstractmethod
    def get_cached_thumbnail(self, file_path: Path, size: Tuple[int, int] = (64, 64)) -> Optional[str]:
        """
        Get cached thumbnail if available
        
        Args:
            file_path: Path to asset file
            size: Thumbnail dimensions
            
        Returns:
            Path to cached thumbnail, None if not cached
        """
        pass
    
    @abstractmethod
    def clear_cache(self) -> None:
        """
        Clear all cached thumbnails
        """
        pass
    
    @abstractmethod
    def clear_cache_for_file(self, file_path: Path) -> None:
        """
        Clear cached thumbnails for specific file
        
        Args:
            file_path: Path to asset file
        """
        pass
    
    @abstractmethod
    def is_thumbnail_supported(self, file_path: Path) -> bool:
        """
        Check if file format supports thumbnail generation
        
        Args:
            file_path: Path to asset file
            
        Returns:
            True if thumbnail generation is supported
        """
        pass
    
    @abstractmethod
    def get_cache_size(self) -> int:
        """
        Get current cache size in bytes
        
        Returns:
            Cache size in bytes
        """
        pass
