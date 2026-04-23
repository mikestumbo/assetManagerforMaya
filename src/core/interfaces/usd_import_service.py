# -*- coding: utf-8 -*-
"""
USD Import Service Interface
Defines contract for importing USD files with full rigging support

Author: Mike Stumbo
Version: 1.5.0 (USD Import Pipeline)
Date: November 2025
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class UsdImportOptions:
    """Configuration options for USD import"""

    # What to import
    import_geometry: bool = True
    import_skeleton: bool = True
    import_materials: bool = True
    apply_skin_weights: bool = True  # NEW: Auto-create Maya skinClusters!
    import_nurbs_curves: bool = True
    import_rig_connections: bool = True  # NEW: Reconstruct functional rig connections!
    import_animation: bool = False

    # Namespace handling
    namespace: Optional[str] = None  # If None, use filename as namespace
    merge_with_existing: bool = False

    # Advanced options
    frame_range: Optional[tuple] = None  # (start, end) for animation
    create_display_layers: bool = False
    preserve_references: bool = False

    # Performance
    verbose: bool = True


@dataclass
class ImportResult:
    """Result of USD import operation"""

    success: bool
    error_message: Optional[str] = None

    # Import method used
    import_method: Optional[str] = None  # 'mayaUSD', 'Pure Python', 'USD View'

    # Imported objects
    imported_meshes: List[str] = field(default_factory=list)
    imported_joints: List[str] = field(default_factory=list)
    imported_curves: List[str] = field(default_factory=list)
    imported_materials: List[str] = field(default_factory=list)

    # Created Maya nodes
    created_skin_clusters: List[str] = field(default_factory=list)
    created_namespaces: List[str] = field(default_factory=list)

    # Statistics
    total_vertices: int = 0
    total_joints: int = 0
    skin_clusters_created: int = 0

    # Warnings/info
    warnings: List[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)

    def get_summary(self) -> str:
        """Get human-readable import summary"""
        if not self.success:
            return f"Import failed: {self.error_message}"

        summary = [
            "SUCCESS: Import successful!",
        ]

        if self.import_method:
            summary.append(f"METHOD: Method: {self.import_method}")

        summary.extend(
            [
                f"MESHES: Imported {len(self.imported_meshes)} meshes",
                f"JOINTS: Imported {len(self.imported_joints)} joints",
                f"CURVES: Imported {len(self.imported_curves)} NURBS curves",
                f"SKIN_CLUSTERS: Created {self.skin_clusters_created} skin clusters",
            ]
        )

        if self.warnings:
            summary.append(f"WARNINGS: {len(self.warnings)} warnings")

        return "\n".join(summary)


class IUsdImportService(ABC):
    """
    Interface for USD Import Service

    Responsibilities:
    - Import USD files into Maya scene
    - Reconstruct Maya skinClusters from UsdSkel data
    - Handle namespaces and scene organization
    - Provide detailed import feedback

    Clean Code: Single Responsibility - USD to Maya conversion
    INDUSTRY FIRST: Automatic skin weight reconstruction from USD!
    """

    @abstractmethod
    def import_usd_file(
        self, usd_path: Path, options: Optional[UsdImportOptions] = None
    ) -> ImportResult:
        """
        Import USD file into Maya scene

        This is the main entry point for USD import. Uses mayaUSD plugin
        for initial geometry/skeleton import, then adds custom skinCluster
        reconstruction from UsdSkel data.

        Args:
            usd_path: Path to USD file (.usd, .usda, .usdc, .usdz)
            options: Import configuration options

        Returns:
            ImportResult with detailed feedback

        Example:
            >>> service = get_usd_import_service()
            >>> result = service.import_usd_file(Path("character.usda"))
            >>> if result.success:
            ...     print(f"Created {result.skin_clusters_created} skin clusters!")
        """

    @abstractmethod
    def import_with_skinning(
        self, usd_path: Path, namespace: Optional[str] = None
    ) -> ImportResult:
        """
        Convenience method: Import USD with automatic skinning

        Shortcut for import_usd_file with skinning enabled.

        Args:
            usd_path: Path to USD file
            namespace: Optional namespace for imported objects

        Returns:
            ImportResult
        """

    @abstractmethod
    def validate_usd_file(self, usd_path: Path) -> tuple[bool, str]:
        """
        Validate USD file before import

        Checks:
        - File exists and is readable
        - USD stage can be opened
        - Contains valid geometry
        - Has skeleton data (if skinning requested)

        Args:
            usd_path: Path to USD file

        Returns:
            (is_valid, error_message) - Empty string if valid
        """

    @abstractmethod
    def get_usd_info(self, usd_path: Path) -> Dict[str, Any]:
        """
        Get information about USD file without importing

        Returns metadata about:
        - Number of meshes
        - Skeleton hierarchy
        - Frame range (if animated)
        - File format details

        Args:
            usd_path: Path to USD file

        Returns:
            Dictionary of USD file information
        """
