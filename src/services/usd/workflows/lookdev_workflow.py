"""
lookdev_workflow.py — Look-Dev / Layout USD Proxy Workflow
===========================================================
Delegates to the existing ``ImportMixin._import_with_mayausd`` pipeline
so the proven USD proxy path (mayaUsdProxyShape + layered stage + RfM
PxrDisneyBsdf shaders) is unchanged.

This thin wrapper exists so:
* The orchestrator in usd_pipeline_import.py dispatches uniformly through
  the workflows package.
* The lookdev path can be extracted into a fully standalone script later
  without touching the orchestrator.

When to use
-----------
* Lighting / rendering layout (static pose, no live deformation needed).
* USD layer authoring (Option B — open Layer Editor).
* VP2 look-development with UsdPreviewSurface.

Render note
-----------
RfM 27.2 with MayaUSD 0.35.0 has no per-mesh shading translator for
``mayaUsdProxyShape``.  The whole proxy renders with the fallback shader
assigned via Phase-C per-prim binding inside ``_create_rfm_maya_shaders``.
For per-mesh PxrDisneyBsdf rendering use the **Hybrid** workflow instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base_workflow import BaseWorkflow


class LookdevWorkflow(BaseWorkflow):
    """USD proxy (Look-Dev / Layout) import workflow.

    Delegates to the existing ``ImportMixin`` implementation on a live
    ``UsdPipeline`` instance.  The caller (ImportMixin.import_usd) passes
    ``self`` as the pipeline so the delegation is zero-overhead.
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
        """Execute the Look-Dev / Layout workflow.

        Args:
            usd_path:    Path to the primary USD file.
            rig_mb_path: Optional companion .rig.mb path.
            options:     ``ImportOptions`` dataclass.
            result:      ``ImportResult`` dataclass mutated in-place.
            pipeline:    The ``UsdPipeline`` instance — provides access to
                         the existing ``_import_with_mayausd`` implementation.

        Returns:
            ``True`` on success.
        """
        if not self._maya_available():
            self.logger.error("[LOOKDEV] Maya cmds not available.")
            return False

        self.logger.info("[LOOKDEV] USD Proxy workflow — delegating to UsdPipeline.")

        # The existing _import_with_mayausd does colour-boost, layered-stage
        # build, proxy creation, RfM shader import and per-prim binding.
        # We simply call it through the pipeline instance.
        try:
            return pipeline._import_with_mayausd(  # type: ignore[attr-defined]
                usd_path, options, result
            )
        except Exception as exc:
            self.logger.error(f"[LOOKDEV] _import_with_mayausd raised: {exc}")
            return False
