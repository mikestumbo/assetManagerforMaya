# -*- coding: utf-8 -*-
"""
Metadata Extractor Interface
Defines file metadata extraction operations following Single Responsibility

Author: Mike Stumbo  
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

from ..models.metadata import FileMetadata


class IMetadataExtractor(ABC):
    """
    Metadata Extractor Interface - Single Responsibility for file metadata
    Follows Interface Segregation: only metadata extraction operations
    """
    
    @abstractmethod
    def extract_metadata(self, file_path: Path) -> FileMetadata:
        """
        Extract comprehensive metadata from file
        
        Args:
            file_path: Path to file for metadata extraction
            
        Returns:
            FileMetadata object with all extracted information
        """
        pass
    
    @abstractmethod
    def get_file_size(self, file_path: Path) -> int:
        """
        Get file size in bytes
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes
        """
        pass
    
    @abstractmethod
    def get_creation_date(self, file_path: Path) -> Optional[str]:
        """
        Get file creation date
        
        Args:
            file_path: Path to file
            
        Returns:
            Creation date as string, None if unavailable
        """
        pass
    
    @abstractmethod
    def get_modification_date(self, file_path: Path) -> Optional[str]:
        """
        Get file modification date
        
        Args:
            file_path: Path to file
            
        Returns:
            Modification date as string, None if unavailable
        """
        pass
    
    @abstractmethod
    def is_supported_format(self, file_path: Path) -> bool:
        """
        Check if file format is supported for metadata extraction
        
        Args:
            file_path: Path to file
            
        Returns:
            True if format is supported
        """
        pass
