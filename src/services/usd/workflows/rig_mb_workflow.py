"""
rig_mb_workflow.py — Full Maya Rig (.rig.mb) Import Workflow
==============================================================
Delegates to the existing ``SkeletonMixin._import_rig_mb_fallback``
and ``SkeletonMixin._supplement_from_rig_mb`` implementations so the
proven .rig.mb import path is unchanged.

This thin wrapper exists so:
* The orchestrator dispatches uniformly through the workflows package.
* The rig-only path can be extracted into a fully standalone script
  later without touching the orchestrator.

When to use
-----------
* USD export was problematic or unavailable.
* Traditional Maya-only animation pipeline (no USD dependency).
* Full IK / constraints / blendShapes from the original .rig.mb.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base_workflow import BaseWorkflow

try:
    import maya.cmds as cmds  # type: ignore[import-unresolved]
except ImportError:
    cmds = None  # type: ignore[assignment]


class RigMbWorkflow(BaseWorkflow):
    """Full .rig.mb import workflow (no USD geometry).

    Delegates to the existing ``SkeletonMixin`` implementation on a live
    ``UsdPipeline`` instance.
    """

    def run(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path],
        options: object,
        result: object,
        *,
        pipeline: object,
    ) -> bool:
        """Execute the Full Maya Rig workflow.

        Args:
            usd_path:    Path to the primary USD file (used only if rig_mb
                         is unavailable and a USD fallback is desired).
            rig_mb_path: Path to the .rig.mb file (required).
            options:     ``ImportOptions`` dataclass.
            result:      ``ImportResult`` dataclass mutated in-place.
            pipeline:    The ``UsdPipeline`` instance — provides access to
                         the existing ``_import_rig_mb_fallback`` /
                         ``_supplement_from_rig_mb`` implementation.

        Returns:
            ``True`` if at least one mesh was imported.
        """
        if not self._maya_available():
            self.logger.error("[RIG_MB] Maya cmds not available.")
            return False

        if rig_mb_path is None or not rig_mb_path.exists():
            self.logger.error(
                f"[RIG_MB] .rig.mb file not found: {rig_mb_path}. "
                "Cannot proceed with Full Maya Rig workflow."
            )
            result.error_message = (  # type: ignore[attr-defined]
                f".rig.mb not found: {rig_mb_path}"
            )
            return False

        self.logger.info(f"[RIG_MB] Full Maya Rig workflow — importing: {rig_mb_path.name}")
        self._report_progress("[PACKAGE] Importing full Maya rig…", 20)

        try:
            success: bool = pipeline._import_rig_mb_fallback(  # type: ignore[attr-defined]
                rig_mb_path, result
            )
            if success:
                self._report_progress("[PACKAGE] Rig import complete.", 100)
                self.logger.info(
                    f"[RIG_MB] Import complete — "
                    f"{getattr(result, 'meshes_imported', '?')} mesh(es)."
                )
            return success
        except Exception as exc:
            self.logger.error(f"[RIG_MB] _import_rig_mb_fallback raised: {exc}")
            return False
