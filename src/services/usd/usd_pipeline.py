"""
USD Pipeline — thin shell.

The implementation is split across mixin modules for Pylance performance:
  usd_pipeline_models.py    — data classes and constants
  usd_pipeline_export.py    — ExportMixin
  usd_pipeline_stages.py    — StagesMixin
  usd_pipeline_materials.py — MaterialsMixin
  usd_pipeline_import.py    — ImportMixin
  usd_pipeline_skeleton.py  — SkeletonMixin
"""

from __future__ import annotations

from pathlib import Path

from .usd_pipeline_models import (
    ExportOptions,
    ExportResult,
    ImportOptions,
    ImportResult,
)
from .usd_pipeline_export import ExportMixin
from .usd_pipeline_stages import StagesMixin
from .usd_pipeline_materials import MaterialsMixin
from .usd_pipeline_import import ImportMixin
from .usd_pipeline_skeleton import SkeletonMixin


class UsdPipeline(
    ExportMixin,
    StagesMixin,
    MaterialsMixin,
    ImportMixin,
    SkeletonMixin,
):
    """USD export/import pipeline for Maya character rigs.

    Implementation is split into mixin modules; this class composes them.
    The public API (export, import_usd) is unchanged.
    """


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================
def export_rig_to_usd(source_path: str, output_path: str, **kwargs) -> ExportResult:
    """
    Convenience function to export a Maya rig to USD

    Args:
        source_path: Path to source .mb/.ma file
        output_path: Path for output
        **kwargs: Additional ExportOptions fields

    Returns:
        ExportResult
    """
    pipeline = UsdPipeline()
    options = ExportOptions(**kwargs)
    return pipeline.export(Path(source_path), Path(output_path), options)


def import_usd_rig(usd_path: str, **kwargs) -> ImportResult:
    """
    Convenience function to import a USD rig

    Args:
        usd_path: Path to .usd/.usdc/.usda/.usdz file
        **kwargs: Additional ImportOptions fields

    Returns:
        ImportResult
    """
    pipeline = UsdPipeline()
    options = ImportOptions(**kwargs)
    return pipeline.import_usd(Path(usd_path), options)
