# -*- coding: utf-8 -*-
"""
Metadata Extractor Implementation
Concrete implementation of file metadata extraction

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import os
import stat
import platform
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from ..core.interfaces.metadata_extractor import IMetadataExtractor
from ..core.models.metadata import FileMetadata


class MetadataExtractorImpl(IMetadataExtractor):
    """
    Metadata Extractor Implementation - Single Responsibility for file metadata
    Uses Strategy Pattern for different file type handling
    """
    
    def __init__(self):
        self._supported_formats = {
            '.ma', '.mb', '.mel',  # Maya files
            '.obj', '.fbx', '.abc', '.usd',  # 3D formats
            '.png', '.jpg', '.jpeg', '.tiff', '.tga', '.exr',  # Images
            '.mov', '.mp4', '.avi',  # Video
            '.txt', '.md', '.json'  # Documents
        }
    
    def extract_metadata(self, file_path: Path) -> FileMetadata:
        """
        Extract comprehensive metadata from file
        Single Responsibility: coordinate metadata extraction
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        # Get basic file stats
        stats = file_path.stat()
        
        # Extract basic metadata
        metadata = FileMetadata(
            file_path=file_path,
            file_name=file_path.name,
            file_extension=file_path.suffix.lower(),
            file_size=stats.st_size,
            created_date=self._get_creation_date_from_stats(stats),
            modified_date=self._get_modification_date_from_stats(stats),
            accessed_date=self._get_access_date_from_stats(stats),
            is_readonly=self._is_readonly(file_path),
            is_hidden=self._is_hidden(file_path),
            is_system=self._is_system_file(file_path),
            mime_type=self._get_mime_type(file_path),
            custom_properties=self._extract_custom_properties(file_path)
        )
        
        return metadata
    
    def get_file_size(self, file_path: Path) -> int:
        """Get file size in bytes"""
        try:
            return file_path.stat().st_size
        except (OSError, IOError):
            return 0
    
    def get_creation_date(self, file_path: Path) -> Optional[str]:
        """Get file creation date"""
        try:
            stats = file_path.stat()
            creation_time = self._get_creation_date_from_stats(stats)
            return creation_time.isoformat() if creation_time else None
        except (OSError, IOError):
            return None
    
    def get_modification_date(self, file_path: Path) -> Optional[str]:
        """Get file modification date"""
        try:
            stats = file_path.stat()
            mod_time = self._get_modification_date_from_stats(stats)
            return mod_time.isoformat() if mod_time else None
        except (OSError, IOError):
            return None
    
    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported for metadata extraction"""
        return file_path.suffix.lower() in self._supported_formats
    
    def _get_creation_date_from_stats(self, stats: os.stat_result) -> Optional[datetime]:
        """Extract creation date from file stats (platform-specific)"""
        try:
            if platform.system() == 'Windows':
                # Windows has creation time
                return datetime.fromtimestamp(stats.st_ctime)
            else:
                # Unix systems: use change time as approximation
                return datetime.fromtimestamp(stats.st_ctime)
        except (OSError, ValueError):
            return None
    
    def _get_modification_date_from_stats(self, stats: os.stat_result) -> Optional[datetime]:
        """Extract modification date from file stats"""
        try:
            return datetime.fromtimestamp(stats.st_mtime)
        except (OSError, ValueError):
            return None
    
    def _get_access_date_from_stats(self, stats: os.stat_result) -> Optional[datetime]:
        """Extract access date from file stats"""
        try:
            return datetime.fromtimestamp(stats.st_atime)
        except (OSError, ValueError):
            return None
    
    def _is_readonly(self, file_path: Path) -> bool:
        """Check if file is read-only"""
        try:
            return not os.access(file_path, os.W_OK)
        except (OSError, IOError):
            return False
    
    def _is_hidden(self, file_path: Path) -> bool:
        """Check if file is hidden (platform-specific)"""
        try:
            if platform.system() == 'Windows':
                # Windows hidden file check
                import ctypes
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(file_path))
                return attrs != -1 and bool(attrs & 2)  # FILE_ATTRIBUTE_HIDDEN
            else:
                # Unix systems: files starting with . are hidden
                return file_path.name.startswith('.')
        except Exception:
            return False
    
    def _is_system_file(self, file_path: Path) -> bool:
        """Check if file is a system file"""
        try:
            if platform.system() == 'Windows':
                # Windows system file check
                import ctypes
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(file_path))
                return attrs != -1 and bool(attrs & 4)  # FILE_ATTRIBUTE_SYSTEM
            else:
                # Unix systems: check if in system directories
                system_dirs = {'/bin', '/sbin', '/usr/bin', '/usr/sbin', '/sys', '/proc'}
                return any(str(file_path).startswith(sys_dir) for sys_dir in system_dirs)
        except Exception:
            return False
    
    def _get_mime_type(self, file_path: Path) -> Optional[str]:
        """Get MIME type for file"""
        try:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            return mime_type
        except Exception:
            return None
    
    def _extract_custom_properties(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract file-type specific custom properties
        Uses Strategy Pattern for different file types
        """
        properties = {}
        
        try:
            extension = file_path.suffix.lower()
            
            if extension in {'.ma', '.mb'}:
                properties.update(self._extract_maya_properties(file_path))
            elif extension in {'.png', '.jpg', '.jpeg', '.tiff', '.tga'}:
                properties.update(self._extract_image_properties(file_path))
            elif extension in {'.mov', '.mp4', '.avi'}:
                properties.update(self._extract_video_properties(file_path))
            elif extension == '.json':
                properties.update(self._extract_json_properties(file_path))
            
        except Exception as e:
            properties['extraction_error'] = str(e)
        
        return properties
    
    def _extract_maya_properties(self, file_path: Path) -> Dict[str, Any]:
        """Extract Maya-specific file properties"""
        properties = {}
        
        try:
            # Basic Maya file detection
            properties['file_type'] = 'maya_scene'
            
            if file_path.suffix.lower() == '.ma':
                properties['format'] = 'maya_ascii'
                # Could parse ASCII file for more details
            elif file_path.suffix.lower() == '.mb':
                properties['format'] = 'maya_binary'
            elif file_path.suffix.lower() == '.mel':
                properties['format'] = 'maya_script'
            
            # Add version detection if possible
            properties['maya_compatible'] = True
            
        except Exception:
            properties['maya_error'] = 'Could not extract Maya properties'
        
        return properties
    
    def _extract_image_properties(self, file_path: Path) -> Dict[str, Any]:
        """Extract image-specific properties"""
        properties = {}
        
        try:
            # Try to get image dimensions using PIL if available
            try:
                from PIL import Image  # type: ignore
                with Image.open(file_path) as img:
                    properties['width'] = img.width
                    properties['height'] = img.height
                    properties['format'] = img.format
                    properties['mode'] = img.mode
                    properties['has_transparency'] = 'transparency' in img.info
            except (ImportError, ModuleNotFoundError):
                # PIL not available, basic detection
                properties['format'] = file_path.suffix.upper()
            
            properties['file_type'] = 'image'
            
        except Exception:
            properties['image_error'] = 'Could not extract image properties'
        
        return properties
    
    def _extract_video_properties(self, file_path: Path) -> Dict[str, Any]:
        """Extract video-specific properties"""
        properties = {}
        
        try:
            properties['file_type'] = 'video'
            properties['format'] = file_path.suffix.upper()
            
            # Could add ffprobe integration for detailed video info
            
        except Exception:
            properties['video_error'] = 'Could not extract video properties'
        
        return properties
    
    def _extract_json_properties(self, file_path: Path) -> Dict[str, Any]:
        """Extract JSON file properties"""
        import json
        properties = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            properties['file_type'] = 'json'
            properties['json_keys'] = list(data.keys()) if isinstance(data, dict) else []
            properties['json_size'] = len(data) if isinstance(data, (list, dict)) else 1
            properties['valid_json'] = True
            
        except json.JSONDecodeError:
            properties['valid_json'] = False
            properties['json_error'] = 'Invalid JSON format'
        except Exception:
            properties['json_error'] = 'Could not parse JSON'
        
        return properties
