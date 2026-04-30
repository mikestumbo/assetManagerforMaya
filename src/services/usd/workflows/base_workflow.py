"""
base_workflow.py — Abstract base class for all USD import workflows.

Every workflow shares: a logger, a progress callback, and a .rig.mb
sibling-file discovery helper.  Concrete workflows inherit from this class
and implement ``run()``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Tuple

# Maya cmds — available only inside a running Maya session.
try:
    import maya.cmds as cmds  # type: ignore[import-unresolved]
except ImportError:
    cmds = None  # type: ignore[assignment]


class BaseWorkflow(ABC):
    """Abstract base for all USD import workflows.

    Provides shared utilities (logger, progress reporting, .rig.mb discovery)
    so concrete workflows contain zero boilerplate.
    """

    _RIG_EXTENSIONS: Tuple[str, ...] = (".rig.mb", ".rig.ma")

    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._progress_cb: Optional[Callable[[str, int], None]] = None

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #

    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """Attach a progress reporting callback (stage: str, percent: int)."""
        self._progress_cb = callback

    def discover_rig_mb(self, near_path: Path) -> Optional[Path]:
        """Return the companion .rig.mb/.rig.ma path for *near_path*.

        Searches:
        1. A sibling file: ``<near_path.stem>.rig.mb`` next to *near_path*.
        2. If *near_path* is inside an extracted USDZ dir, check the
           parent directory as well.

        Args:
            near_path: Path to a .usd/.usdc/.usda file.

        Returns:
            Path to the companion .rig.mb file, or ``None`` if not found.
        """
        candidates = [near_path.parent]
        # If we're inside an extracted USDZ temp folder the stem of the
        # original .usdz lives one level up.
        if near_path.parent.parent.exists():
            candidates.append(near_path.parent.parent)

        stem = near_path.stem.replace(".root", "").replace(".usdc", "")
        for directory in candidates:
            for ext in self._RIG_EXTENSIONS:
                candidate = directory / (stem + ext)
                if candidate.exists():
                    self.logger.info(f"[RIG] Found companion rig file: {candidate.name}")
                    return candidate
        self.logger.info(
            f"[RIG] No companion .rig.mb found near: {near_path.name}. "
            "Place '<asset>.rig.mb' next to the USD file to enable "
            "RfM shaders and NURBS controllers."
        )
        return None

    # ------------------------------------------------------------------ #
    # Abstract interface
    # ------------------------------------------------------------------ #

    @abstractmethod
    def run(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path],
        options: object,
        result: object,
        *,
        pipeline: object = None,
    ) -> bool:
        """Execute the workflow.

        Args:
            usd_path:    Path to the primary USD file (.usdc/.usda).
            rig_mb_path: Optional path to the companion .rig.mb file.
            options:     ``ImportOptions`` dataclass instance.
            result:      ``ImportResult`` instance — mutated in-place.
            pipeline:    Optional ``UsdPipeline`` instance for delegation
                         workflows (LookdevWorkflow, RigMbWorkflow).
                         Standalone workflows (HybridWorkflow) ignore this.

        Returns:
            ``True`` if the workflow succeeded, ``False`` otherwise.
        """

    # ------------------------------------------------------------------ #
    # Protected utilities
    # ------------------------------------------------------------------ #

    def _report_progress(self, stage: str, percent: int) -> None:
        """Fire the progress callback if one has been set."""
        if self._progress_cb is not None:
            try:
                self._progress_cb(stage, percent)
            except Exception:
                pass  # progress callbacks must never crash the workflow

    def _maya_available(self) -> bool:
        """Return True if Maya cmds is importable (running inside Maya)."""
        return cmds is not None

    def _build_namespace_from_path(self, path: Path) -> str:
        """Derive a safe Maya namespace string from *path*.

        Examples:
            ``Veteran_Rig.rig.mb``  → ``"Veteran_Rig"``
            ``hero_char.rig.mb``    → ``"hero_char"``
        """
        stem = path.name
        # Strip compound extensions like .rig.mb
        while "." in stem:
            stem = Path(stem).stem
        # Replace any remaining non-alphanumeric characters with underscores.
        import re

        stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
        return stem or "rig"
