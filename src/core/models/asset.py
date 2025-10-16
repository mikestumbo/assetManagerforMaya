# -*- coding: utf-8 -*-
"""
Asset Domain Model
Core entity representing an asset in the system

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime


@dataclass
class Asset:
    """
    Asset Entity - Single Responsibility for asset data representation
    Immutable value object following Domain-Driven Design principles
    """
    
    # Core identity
    id: str
    name: str
    file_path: Path
    
    # File information  
    file_extension: str
    file_size: int
    
    # Timestamps
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    
    # Asset properties
    asset_type: str = "unknown"
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # User interactions
    is_favorite: bool = False
    access_count: int = 0
    
    # Thumbnail information
    thumbnail_path: Optional[Path] = None
    
    def __post_init__(self):
        """Validate asset data after initialization"""
        if not self.file_path.exists():
            raise ValueError(f"Asset file does not exist: {self.file_path}")
        
        if not self.name:
            self.name = self.file_path.stem
            
        if not self.file_extension:
            self.file_extension = self.file_path.suffix.lower()
    
    @property
    def display_name(self) -> str:
        """Get human-readable display name"""
        return self.name or self.file_path.stem
    
    @property
    def is_maya_file(self) -> bool:
        """Check if asset is a Maya file"""
        maya_extensions = {'.ma', '.mb', '.mel'}
        return self.file_extension in maya_extensions
    
    @property
    def is_image_file(self) -> bool:
        """Check if asset is an image file"""
        image_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.tga', '.bmp', '.gif'}
        return self.file_extension in image_extensions
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes"""
        return self.file_size / (1024 * 1024)
    
    def add_tag(self, tag: str) -> None:
        """Add tag to asset if not already present"""
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove tag from asset"""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def update_access(self) -> None:
        """Update access timestamp and increment count"""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert asset to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'file_path': str(self.file_path),
            'file_extension': self.file_extension,
            'file_size': self.file_size,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'asset_type': self.asset_type,
            'category': self.category,
            'tags': self.tags.copy(),
            'metadata': self.metadata.copy(),
            'is_favorite': self.is_favorite,
            'access_count': self.access_count,
            'thumbnail_path': str(self.thumbnail_path) if self.thumbnail_path else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Asset':
        """Create asset from dictionary"""
        # Convert string paths back to Path objects
        data['file_path'] = Path(data['file_path'])
        if data.get('thumbnail_path'):
            data['thumbnail_path'] = Path(data['thumbnail_path'])
        
        # Convert ISO date strings back to datetime objects
        for date_field in ['created_date', 'modified_date', 'last_accessed']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        return cls(**data)
