"""
USD Import Workflow Package
============================
Each workflow is an isolated, independently testable script.
The UsdPipeline orchestrator in usd_pipeline_import.py routes to the
appropriate workflow based on ImportOptions flags.

Workflows
---------
HybridWorkflow   — USD → native Maya polys + .rig.mb RfM SGs + NURBS controllers
LookdevWorkflow  — USD proxy (mayaUsdProxyShape) + layered stage + RfM shaders
RigMbWorkflow    — Full .rig.mb import, USD used only for texture/material data
"""

from .hybrid_workflow import HybridWorkflow
from .lookdev_workflow import LookdevWorkflow
from .rig_mb_workflow import RigMbWorkflow

__all__ = ["HybridWorkflow", "LookdevWorkflow", "RigMbWorkflow"]
