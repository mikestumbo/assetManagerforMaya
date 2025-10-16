# -*- coding: utf-8 -*-
"""
File Metadata Domain Model
Value object for file metadata information

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime


@dataclass(frozen=True)
class FileMetadata:
    """
    File Metadata Value Object - Immutable data container
    Single Responsibility for file metadata representation
    """
    
    # Basic file information
    file_path: Path
    file_name: str
    file_extension: str
    file_size: int
    
    # Timestamps
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    accessed_date: Optional[datetime] = None
    
    # File attributes
    is_readonly: bool = False
    is_hidden: bool = False
    is_system: bool = False
    
    # Content information
    mime_type: Optional[str] = None
    encoding: Optional[str] = None
    
    # Extended metadata
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def file_size_kb(self) -> float:
        """Get file size in kilobytes"""
        return self.file_size / 1024
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes"""
        return self.file_size / (1024 * 1024)
    
    @property
    def file_size_human(self) -> str:
        """Get human-readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size_kb:.1f} KB"
        else:
            return f"{self.file_size_mb:.1f} MB"
    
    @property
    def is_maya_file(self) -> bool:
        """Check if file is a Maya file"""
        maya_extensions = {'.ma', '.mb', '.mel'}
        return self.file_extension.lower() in maya_extensions
    
    @property
    def is_image_file(self) -> bool:
        """Check if file is an image"""
        image_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.tga', '.bmp', '.gif', '.exr'}
        return self.file_extension.lower() in image_extensions
    
    @property
    def is_video_file(self) -> bool:
        """Check if file is a video"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
        return self.file_extension.lower() in video_extensions
    
    @property
    def is_audio_file(self) -> bool:
        """Check if file is audio"""
        audio_extensions = {'.mp3', '.wav', '.aiff', '.flac', '.ogg', '.m4a'}
        return self.file_extension.lower() in audio_extensions
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """Get custom property value"""
        return self.custom_properties.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            'file_path': str(self.file_path),
            'file_name': self.file_name,
            'file_extension': self.file_extension,
            'file_size': self.file_size,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'accessed_date': self.accessed_date.isoformat() if self.accessed_date else None,
            'is_readonly': self.is_readonly,
            'is_hidden': self.is_hidden,
            'is_system': self.is_system,
            'mime_type': self.mime_type,
            'encoding': self.encoding,
            'custom_properties': self.custom_properties.copy()
        }
