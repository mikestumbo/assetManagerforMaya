# -*- coding: utf-8 -*-
"""
Asset Manager Constants Module
Centralized constants following DRY principle and Single Source of Truth pattern

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class SearchConstants:
    """Search and discovery functionality constants - DRY principle"""
    MAX_RECENT_ASSETS: int = 20
    MAX_SEARCH_HISTORY: int = 15
    MAX_FAVORITES: int = 100
    SEARCH_SIMILARITY_THRESHOLD: float = 0.6
    AUTO_COMPLETE_MIN_CHARS: int = 2
    METADATA_CACHE_TIMEOUT: int = 300  # 5 minutes


@dataclass(frozen=True)
class ThumbnailConstants:
    """Thumbnail generation constants - follows DRY principle"""
    DEFAULT_WIDTH: int = 64
    DEFAULT_HEIGHT: int = 64
    CACHE_SIZE_LIMIT: int = 50
    GENERATION_BATCH_SIZE: int = 5
    CACHE_TIMEOUT_LOCAL: int = 30  # seconds
    CACHE_TIMEOUT_NETWORK: int = 120  # seconds
    
    @property
    def DEFAULT_SIZE(self) -> tuple[int, int]:
        return (self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)


@dataclass(frozen=True)
class UIConstants:
    """UI dimension constants - DRY Principle"""
    # Preview widget dimensions
    PREVIEW_MIN_WIDTH: int = 350
    PREVIEW_MIN_HEIGHT: int = 250
    PREVIEW_FRAME_WIDTH: int = 400
    PREVIEW_FRAME_HEIGHT: int = 300
    
    # Splitter sizes  
    LIBRARY_WIDTH: int = 700
    PREVIEW_WIDTH: int = 300


@dataclass(frozen=True)
class ErrorMessages:
    """Centralized error messages - Single Source of Truth"""
    MAYA_NOT_AVAILABLE: str = "Maya not available - cannot import asset"
    FILE_NOT_FOUND: str = "FILE\nNOT FOUND"
    MAYA_ERROR: str = "MAYA\nERROR" 
    MAYA_SCENE_FALLBACK: str = "MAYA\nSCENE"


@dataclass(frozen=True)
class PerformanceConstants:
    """Performance-related constants"""
    THREAD_POOL_MAX_WORKERS: int = 2
    CACHE_TIMEOUT_SECONDS: int = 30
    IMPORT_COOLDOWN_SECONDS: float = 1.5
    NETWORK_TIMEOUT_THRESHOLD: float = 5.0
    REFRESH_DELAY_MS: int = 2000


# Singleton instances - immutable configuration
SEARCH_CONFIG = SearchConstants()
THUMBNAIL_CONFIG = ThumbnailConstants()
UI_CONFIG = UIConstants()
ERROR_MESSAGES = ErrorMessages()
PERFORMANCE_CONFIG = PerformanceConstants()
