# -*- coding: utf-8 -*-
"""
Search Criteria Domain Model
Specification pattern for asset search operations

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from dataclasses import dataclass, field
from typing import Optional, List, Set, Dict, Any
from pathlib import Path
from enum import Enum


class SortOrder(Enum):
    """Sort order enumeration"""
    ASCENDING = "asc"
    DESCENDING = "desc"


class SortBy(Enum):
    """Sort criteria enumeration"""
    NAME = "name"
    DATE_CREATED = "created_date"
    DATE_MODIFIED = "modified_date"
    DATE_ACCESSED = "last_accessed"
    FILE_SIZE = "file_size"
    ACCESS_COUNT = "access_count"
    ASSET_TYPE = "asset_type"


@dataclass
class SearchCriteria:
    """
    Search Criteria Specification - Single Responsibility for search logic
    Implements Specification Pattern for flexible search combinations
    """
    
    # Text search
    search_text: Optional[str] = None
    case_sensitive: bool = False
    
    # File filters
    file_extensions: Set[str] = field(default_factory=set)
    asset_types: Set[str] = field(default_factory=set)
    categories: Set[str] = field(default_factory=set)
    
    # Size filters
    min_file_size: Optional[int] = None  # in bytes
    max_file_size: Optional[int] = None  # in bytes
    
    # Date filters
    created_after: Optional[str] = None  # ISO date string
    created_before: Optional[str] = None  # ISO date string
    modified_after: Optional[str] = None  # ISO date string
    modified_before: Optional[str] = None  # ISO date string
    
    # Tag filters
    required_tags: Set[str] = field(default_factory=set)
    excluded_tags: Set[str] = field(default_factory=set)
    
    # Special filters
    favorites_only: bool = False
    recently_accessed: bool = False
    
    # Directory scope
    search_directories: List[Path] = field(default_factory=list)
    recursive: bool = True
    
    # Sorting
    sort_by: SortBy = SortBy.NAME
    sort_order: SortOrder = SortOrder.ASCENDING
    
    # Pagination
    limit: Optional[int] = None
    offset: int = 0
    
    def __post_init__(self):
        """Validate search criteria after initialization"""
        # Normalize file extensions
        self.file_extensions = {ext.lower().lstrip('.') for ext in self.file_extensions}
        
        # Validate size filters
        if self.min_file_size and self.max_file_size:
            if self.min_file_size > self.max_file_size:
                raise ValueError("min_file_size cannot be greater than max_file_size")
    
    @property
    def has_text_search(self) -> bool:
        """Check if text search is specified"""
        return bool(self.search_text and self.search_text.strip())
    
    @property
    def has_file_filters(self) -> bool:
        """Check if file type filters are specified"""
        return bool(self.file_extensions or self.asset_types or self.categories)
    
    @property
    def has_size_filters(self) -> bool:
        """Check if size filters are specified"""
        return self.min_file_size is not None or self.max_file_size is not None
    
    @property
    def has_date_filters(self) -> bool:
        """Check if date filters are specified"""
        return any([
            self.created_after, self.created_before,
            self.modified_after, self.modified_before
        ])
    
    @property
    def has_tag_filters(self) -> bool:
        """Check if tag filters are specified"""
        return bool(self.required_tags or self.excluded_tags)
    
    @property
    def is_empty(self) -> bool:
        """Check if criteria is empty (no filters specified)"""
        return not any([
            self.has_text_search,
            self.has_file_filters,
            self.has_size_filters,
            self.has_date_filters,
            self.has_tag_filters,
            self.favorites_only,
            self.recently_accessed
        ])
    
    def add_file_extension(self, extension: str) -> None:
        """Add file extension to filter"""
        self.file_extensions.add(extension.lower().lstrip('.'))
    
    def remove_file_extension(self, extension: str) -> None:
        """Remove file extension from filter"""
        self.file_extensions.discard(extension.lower().lstrip('.'))
    
    def add_required_tag(self, tag: str) -> None:
        """Add required tag to filter"""
        if tag:
            self.required_tags.add(tag)
    
    def add_excluded_tag(self, tag: str) -> None:
        """Add excluded tag to filter"""
        if tag:
            self.excluded_tags.add(tag)
    
    def clear_filters(self) -> None:
        """Clear all search filters"""
        self.search_text = None
        self.file_extensions.clear()
        self.asset_types.clear()
        self.categories.clear()
        self.min_file_size = None
        self.max_file_size = None
        self.created_after = None
        self.created_before = None
        self.modified_after = None
        self.modified_before = None
        self.required_tags.clear()
        self.excluded_tags.clear()
        self.favorites_only = False
        self.recently_accessed = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert criteria to dictionary"""
        return {
            'search_text': self.search_text,
            'case_sensitive': self.case_sensitive,
            'file_extensions': list(self.file_extensions),
            'asset_types': list(self.asset_types),
            'categories': list(self.categories),
            'min_file_size': self.min_file_size,
            'max_file_size': self.max_file_size,
            'created_after': self.created_after,
            'created_before': self.created_before,
            'modified_after': self.modified_after,
            'modified_before': self.modified_before,
            'required_tags': list(self.required_tags),
            'excluded_tags': list(self.excluded_tags),
            'favorites_only': self.favorites_only,
            'recently_accessed': self.recently_accessed,
            'search_directories': [str(d) for d in self.search_directories],
            'recursive': self.recursive,
            'sort_by': self.sort_by.value,
            'sort_order': self.sort_order.value,
            'limit': self.limit,
            'offset': self.offset
        }
