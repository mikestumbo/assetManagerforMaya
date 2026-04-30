"""
hybrid_workflow.py — Hybrid USD Import Workflow
=================================================
Production render path for Maya 2026.3 + RfM 27.2.

Algorithm (order matters)
--------------------------
Phase 1  USD → native Maya polygons
         mayaUSDImport with shadingMode=[("none","default")] so
         shapes land in the scene with their natural names and NO
         skinCluster history (instObjGroups[0] is free for assignment).

Phase 2  Load .rig.mb with a dedicated namespace
         The companion .rig.mb is imported into namespace ``<asset>_Rig``.
         All .rig.mb shapes, joints, SGs and NURBS controllers land in
         that namespace — zero name-collision with the Phase-1 shapes.

Phase 3  Build mesh-name → SG map from .rig.mb geometry
         For every namespaced mesh shape from the .rig.mb we read its
         connected shading engine.  We store the map keyed on the *short*
         (non-namespaced) shape name so it can be matched against the
         Phase-1 imports.

Phase 4  Assign .rig.mb SGs to the USD-imported mesh shapes
         The USD-imported shapes have no skinCluster lock, so
         cmds.sets(sg, forceElement=shape) succeeds.  A hyperShade
         fallback is attempted for any that fail.

Phase 5  Hide .rig.mb geometry
         The namespaced .rig.mb meshes are hidden (visibility=False).
         Their SGs and NURBS controllers remain active.

Phase 6  Collect NURBS controllers
         The .rig.mb NURBS controller transforms are already in the scene
         (Phase 2 loaded them).  We simply collect and report them — no
         second file load needed.

Phase 7  Post-import sweep
         Any NurbsCurves / joints / cameras imported from the USD stage
         in Phase 1 are deleted.  We only want polygonal geometry from
         the USD; the rig controls come exclusively from the .rig.mb.

Why this works where earlier attempts failed
--------------------------------------------
The "Render-Ready Native Import" approach in the USD-proxy workflow
failed because the .rig.mb was loaded *first* (as part of shader
creation), and mayaUSDImport then collided on mesh names.  The rig's
skinned shapes are locked through their skinCluster history and reject
SG reassignment ("Source node will not allow the connection").

Here we invert the load order: USD geometry comes in first (clean
scene, no skinCluster locks), .rig.mb comes in second with a namespace
(no collision), and assignment to the unlocked USD shapes succeeds.

Maya version requirements
-------------------------
* Maya 2026.3, MayaUSD 0.35.0+
* RenderMan for Maya 27.2+  (for PxrDisneyBsdf SGs)
* PySide6 / shiboken6       (Qt 6 — not used directly here)
"""

from __future__ import annotations

import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .base_workflow import BaseWorkflow

try:
    import maya.cmds as cmds  # type: ignore[import-unresolved]
    import maya.mel as mel  # type: ignore[import-unresolved]
except ImportError:
    cmds: Any = None
    mel: Any = None


# ── USD prims that should NOT become native Maya nodes (Phase-1 sweep) ────
_SWEEP_TYPES: Tuple[str, ...] = (
    "nurbsCurve",
    "joint",
    "camera",
    # RfM light shapes
    "PxrDomeLight",
    "PxrSphereLight",
    "PxrRectLight",
    "PxrDiskLight",
    "PxrCylinderLight",
)


class HybridWorkflow(BaseWorkflow):
    """Hybrid import: USD geometry + RfM PxrDisneyBsdf SGs + NURBS controllers.

    This is the canonical production render path for RfM 27.2 on Maya 2026.3.
    See module docstring for full algorithm description.
    """

    def run(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path],
        options: object,
        result: object,
        *,
        pipeline: object = None,
    ) -> bool:
        """Execute the Hybrid workflow.

        Args:
            usd_path:    Path to the primary USD file (.usdc / .usda).
            rig_mb_path: Path to the companion .rig.mb file.
            options:     ``ImportOptions`` dataclass (duck-typed).
            result:      ``ImportResult`` dataclass mutated in-place.

        Returns:
            ``True`` on success, ``False`` if a fatal phase failed.
        """
        if not self._maya_available():
            self.logger.error("[HYBRID] Maya cmds not available.")
            return False

        if not usd_path.exists():
            self.logger.error(f"[HYBRID] USD file not found: {usd_path}")
            return False

        if rig_mb_path is None or not rig_mb_path.exists():
            self.logger.warning(
                "[HYBRID] No companion .rig.mb found — falling back to "
                "USD-only import (no RfM shaders, no NURBS controllers)."
            )
            return self._usd_only_fallback(usd_path, result)

        self.logger.info("[HYBRID] ══════════════════════════════════════════════")
        self.logger.info("[HYBRID] HYBRID WORKFLOW  —  Maya 2026.3 + RfM 27.2")
        self.logger.info(f"[HYBRID]   USD  : {usd_path.name}")
        self.logger.info(f"[HYBRID]   RIG  : {rig_mb_path.name}")
        self.logger.info("[HYBRID] ══════════════════════════════════════════════")

        try:
            # ── Phase 1 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 1: Importing USD geometry…", 10)
            usd_roots, usd_shapes = self._phase1_import_usd_geo(usd_path)
            if not usd_shapes:
                self.logger.error("[HYBRID] Phase 1 failed — no mesh shapes imported.")
                return False
            self.logger.info(
                f"[HYBRID] Phase 1 complete: {len(usd_shapes)} mesh shape(s) from USD."
            )

            # ── Phase 2 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 2: Loading .rig.mb…", 30)
            rig_namespace = self._build_namespace_from_path(rig_mb_path)

            # Snapshot meshes + curves BEFORE import so we can identify
            # every rig node by diff regardless of namespace depth.
            # (The .rig.mb often references a second .ma whose nodes land at
            #  Namespace:InnerNS:shape — unreachable by a single-level wildcard.)
            pre_p2_meshes: Set[str] = set(cmds.ls(type="mesh", long=True) or [])
            pre_p2_curves: Set[str] = set(cmds.ls(type="nurbsCurve", long=True) or [])

            rig_nodes = self._phase2_load_rig_mb(rig_mb_path, rig_namespace)
            if not rig_nodes:
                self.logger.error("[HYBRID] Phase 2 failed — .rig.mb import returned no nodes.")
                return False

            post_p2_meshes: Set[str] = set(cmds.ls(type="mesh", long=True) or [])
            post_p2_curves: Set[str] = set(cmds.ls(type="nurbsCurve", long=True) or [])

            # Filter intermediate mesh objects (history nodes).
            rig_mesh_shapes: List[str] = [
                s
                for s in sorted(post_p2_meshes - pre_p2_meshes)
                if cmds.objExists(s) and not cmds.getAttr(f"{s}.intermediateObject")
            ]
            rig_curve_shapes: List[str] = sorted(post_p2_curves - pre_p2_curves)

            self.logger.info(
                f"[HYBRID] Phase 2 complete: {len(rig_nodes)} node(s) from .rig.mb "
                f"(namespace: '{rig_namespace}', "
                f"{len(rig_mesh_shapes)} mesh shape(s), "
                f"{len(rig_curve_shapes)} curve shape(s))."
            )

            # ── Phase 3 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 3: Building SG map…", 40)
            sg_map, rig_shape_map = self._phase3_build_sg_map(rig_mesh_shapes)
            self.logger.info(f"[HYBRID] Phase 3 complete: {len(sg_map)} mesh → SG mappings found.")
            if not sg_map:
                self.logger.warning(
                    "[HYBRID] No SG mappings found in .rig.mb — "
                    "USD geometry will have no RfM shaders."
                )

            # ── Phase 4 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 4: Assigning RfM SGs…", 55)
            assigned, failed, sg_pairings = self._phase4_assign_sgs(
                usd_shapes, sg_map, rig_shape_map
            )
            self.logger.info(
                f"[HYBRID] Phase 4 complete: {assigned}/{assigned + failed} "
                f"mesh(es) bound to RfM PxrDisneyBsdf SG."
            )
            if failed:
                self.logger.warning(
                    f"[HYBRID] {failed} mesh(es) could not be bound to their target SG."
                )

            # ── Phase 4.5: zero + lock USD mesh parent transforms ──────────
            # The hybrid workflow's Phase 8 wiring is:
            #
            #   rig_shape.worldMesh[0] ──► transformGeometry.inputGeometry
            #   usd_parent.worldInverseMatrix[0] ──► transformGeometry.transform
            #   transformGeometry.outputGeometry ──► usd_shape.inMesh
            #
            # The math relies on `usd_parent.worldMatrix` being IDENTICAL to
            # the inverse of what transformGeometry consumed at evaluation
            # time, otherwise VP2's draw stage applies a worldMatrix that
            # does NOT cancel the transformGeometry inverse, producing a
            # visibly inflated / displaced mesh.  Two prior failure modes
            # have been observed:
            #
            #   1) inheritsTransform got re-enabled by cmds.sets(forceElement)
            #      — fixed by locking the attribute below.
            #
            #   2) mayaUSDImport bakes the USD prim's xformOp values into
            #      the parent's local translate/rotate/scale.  Even tiny
            #      asymmetries between worldInverseMatrix (read by
            #      transformGeometry once per eval) and worldMatrix (read
            #      by VP2's draw pass) compound through the
            #      out-of-order parallel evaluation manager into visible
            #      mesh inflation.
            #
            # The deterministic fix: force every USD mesh parent to a
            # **completely identity local transform** AND
            # inheritsTransform=0.  Then worldMatrix == worldInverseMatrix
            # == identity for all time → transformGeometry becomes a true
            # passthrough → worldMesh from the rig flows straight through
            # to the visible USD shape with no matrix reconstruction error.
            # All transform attributes are locked afterwards so nothing
            # downstream (RfM scene_updater, animation playback, controller
            # constraints) can perturb them.
            _it_restored = 0
            _it_locked = 0
            _xform_zeroed = 0
            _ZEROES = {
                "translateX": 0.0,
                "translateY": 0.0,
                "translateZ": 0.0,
                "rotateX": 0.0,
                "rotateY": 0.0,
                "rotateZ": 0.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0,
                "shearXY": 0.0,
                "shearXZ": 0.0,
                "shearYZ": 0.0,
                "rotatePivotX": 0.0,
                "rotatePivotY": 0.0,
                "rotatePivotZ": 0.0,
                "scalePivotX": 0.0,
                "scalePivotY": 0.0,
                "scalePivotZ": 0.0,
                "rotatePivotTranslateX": 0.0,
                "rotatePivotTranslateY": 0.0,
                "rotatePivotTranslateZ": 0.0,
                "scalePivotTranslateX": 0.0,
                "scalePivotTranslateY": 0.0,
                "scalePivotTranslateZ": 0.0,
            }
            _seen_parents: Set[str] = set()
            for _usd_shape in usd_shapes:
                if not cmds.objExists(_usd_shape):
                    continue
                _parents = cmds.listRelatives(_usd_shape, parent=True, fullPath=True) or []
                for _t in _parents:
                    if _t in _seen_parents:
                        continue
                    _seen_parents.add(_t)
                    # ── (a) Drop any incoming connections on transform attrs ──
                    # mayaUSDImport may wire xformOp source plugs into the
                    # parent's TRS attrs.  We must disconnect those before
                    # the setAttr() calls below or they'll be silently
                    # overridden on the next DG pass.
                    for _attr_name in _ZEROES.keys():
                        _plug = f"{_t}.{_attr_name}"
                        try:
                            if not cmds.attributeQuery(_attr_name, node=_t, exists=True):
                                continue
                            # Unlock first in case a prior pass locked it.
                            try:
                                cmds.setAttr(_plug, lock=False)
                            except Exception:
                                pass
                            _src = (
                                cmds.listConnections(
                                    _plug, source=True, destination=False, plugs=True
                                )
                                or []
                            )
                            for _s in _src:
                                try:
                                    cmds.disconnectAttr(_s, _plug)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    # ── (b) Zero/identity-fy the local transform ──
                    for _attr_name, _val in _ZEROES.items():
                        try:
                            if cmds.attributeQuery(_attr_name, node=_t, exists=True):
                                cmds.setAttr(f"{_t}.{_attr_name}", _val)
                                _xform_zeroed += 1
                        except Exception:
                            pass
                    # ── (c) Force inheritsTransform=0 ──
                    try:
                        if cmds.attributeQuery("inheritsTransform", node=_t, exists=True):
                            try:
                                cmds.setAttr(f"{_t}.inheritsTransform", lock=False)
                            except Exception:
                                pass
                            if cmds.getAttr(f"{_t}.inheritsTransform") != 0:
                                cmds.setAttr(f"{_t}.inheritsTransform", 0)
                                _it_restored += 1
                    except Exception:
                        pass
                    # ── (d) Lock everything so nothing downstream can perturb ──
                    for _attr_name in list(_ZEROES.keys()) + ["inheritsTransform"]:
                        try:
                            if cmds.attributeQuery(_attr_name, node=_t, exists=True):
                                cmds.setAttr(f"{_t}.{_attr_name}", lock=True)
                        except Exception:
                            pass
                    _it_locked += 1
            if _xform_zeroed:
                self.logger.info(
                    "[HYBRID] Phase 4.5: zeroed local TRS on %d USD mesh parent transform(s) "
                    "(%d attrs total) — forces worldMatrix == identity for deterministic "
                    "transformGeometry passthrough.",
                    len(_seen_parents),
                    _xform_zeroed,
                )
            if _it_restored:
                self.logger.info(
                    "[HYBRID] Phase 4.5: restored inheritsTransform=0 on %d USD mesh parent(s).",
                    _it_restored,
                )
            if _it_locked:
                self.logger.info(
                    "[HYBRID] Phase 4.5: locked all transform attrs on %d USD mesh parent(s) "
                    "(prevents anything downstream from re-enabling inheritsTransform or "
                    "perturbing the local TRS).",
                    _it_locked,
                )

            # ── Phase 5 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 5: Hiding .rig.mb geometry…", 65)
            hidden, hidden_mesh_xforms = self._phase5_hide_rig_geo(rig_mesh_shapes)
            self.logger.info(
                f"[HYBRID] Phase 5 complete: {hidden} .rig.mb mesh transform(s) hidden."
            )

            # ── Phase 5.5: satisfy RfM on ngSkinTools annotation SGs ──────
            # ngSkinTools2 creates per-paint-layer annotation shadingEngines
            # (asWhiteSG, asRedSG, asGreenSG, asBlackSG, asBlueSG, asGreen2SG,
            # asBlue2SG) inside the rig.mb's referenced inner .ma file.  These
            # SGs have NO surfaceShader connection.  RfM 27.2's scene_updater
            # walks every shadingEngine in the scene at render time and
            # logs:  ``WARNING: <ns>:asWhiteSG is missing a RenderMan material``
            # When an SG has members but no RenderMan material, RfM may also
            # refuse to evaluate / render those members correctly — corrupting
            # the frame.  We cannot remove the referenced rig shapes from
            # these SGs (Maya forbids set-membership edits on referenced
            # nodes), so the only safe fix is to attach a shared dummy
            # PxrSurface so RfM finds a valid RenderMan material on every
            # annotation SG.  The dummy shader has default values — the SGs
            # only carry hidden/intermediate rig geometry, so it never
            # contributes to the final image.
            try:
                _annotation_sg_prefixes = (
                    "asWhite",
                    "asRed",
                    "asGreen",
                    "asBlack",
                    "asBlue",
                    "asGreen2",
                    "asBlue2",
                )
                _all_sgs = cmds.ls(type="shadingEngine") or []
                _annotation_sgs = [
                    sg
                    for sg in _all_sgs
                    if any(sg.split(":")[-1].startswith(p) for p in _annotation_sg_prefixes)
                ]
                _patched = 0
                _shared_dummy: Optional[str] = None
                for _asg in _annotation_sgs:
                    try:
                        _existing = (
                            cmds.listConnections(
                                f"{_asg}.surfaceShader",
                                source=True,
                                destination=False,
                                plugs=False,
                            )
                            or []
                        )
                        if _existing:
                            continue  # already has a shader
                        if _shared_dummy is None or not cmds.objExists(_shared_dummy):
                            _shared_dummy = cmds.shadingNode(
                                "PxrSurface",
                                asShader=True,
                                name="hybrid_annotationSG_dummy_PxrSurface",
                            )
                            # Make the dummy fully non-contributing so it
                            # cannot leak into the rendered image under any
                            # circumstance.  RfM 27.2 treats presence=0 as
                            # fully transparent — the renderer skips the
                            # shape entirely instead of evaluating BSDFs.
                            # Also zero diffuse/specular gains as belt-and-
                            # suspenders for the rare case where presence
                            # is overridden downstream.
                            try:
                                cmds.setAttr(f"{_shared_dummy}.presence", 0.0)
                            except Exception:
                                pass
                            try:
                                cmds.setAttr(f"{_shared_dummy}.diffuseGain", 0.0)
                            except Exception:
                                pass
                            try:
                                cmds.setAttr(f"{_shared_dummy}.specularFaceColorR", 0.0)
                                cmds.setAttr(f"{_shared_dummy}.specularFaceColorG", 0.0)
                                cmds.setAttr(f"{_shared_dummy}.specularFaceColorB", 0.0)
                            except Exception:
                                pass
                        cmds.connectAttr(
                            f"{_shared_dummy}.outColor",
                            f"{_asg}.surfaceShader",
                            force=True,
                        )
                        _patched += 1
                    except Exception as _patch_err:
                        self.logger.debug(
                            "[HYBRID] Phase 5.5: could not patch SG '%s': %s",
                            _asg,
                            _patch_err,
                        )
                if _patched:
                    self.logger.info(
                        "[HYBRID] Phase 5.5: attached dummy PxrSurface to %d "
                        "ngSkinTools annotation SG(s) (silences RfM 'missing "
                        "RenderMan material' warnings).",
                        _patched,
                    )
            except Exception as _phase55_err:
                self.logger.debug(
                    "[HYBRID] Phase 5.5: annotation SG patch skipped: %s", _phase55_err
                )

            # ── Phase 6 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 6: Collecting NURBS controllers…", 75)
            controllers = self._phase6_collect_controllers(rig_curve_shapes, hidden_mesh_xforms)
            self.logger.info(
                f"[HYBRID] Phase 6 complete: {len(controllers)} NURBS controller(s) available."
            )

            # ── Phase 7 ────────────────────────────────────────────────────
            self._report_progress("[HYBRID] Phase 7: Post-import sweep…", 85)
            sweep_counts = self._phase7_post_import_sweep(usd_roots)
            parts = [f"{v} {k}(s)" for k, v in sweep_counts.items() if v > 0]
            if parts:
                self.logger.info(f"[HYBRID] Phase 7 sweep removed: {', '.join(parts)}.")
            else:
                self.logger.info("[HYBRID] Phase 7: nothing to sweep.")

            # ── Phase 8 ────────────────────────────────────────────────────
            # Transfer skinCluster weights from the (now hidden) rig meshes
            # onto the visible USD meshes so the controllers actually deform
            # what the user sees.  Without this, the controllers animate the
            # invisible rig mesh and the USD geometry stays bind-pose.
            self._report_progress(
                "[HYBRID] Phase 8: Wiring USD meshes to rig deformation output…", 92
            )
            skin_bound, skin_skipped, skin_failed = self._phase8_transfer_skin_weights(
                sg_pairings, rig_mesh_shapes
            )
            self.logger.info(
                "[HYBRID] Phase 8 complete: %d connected (shared rig output), %d skipped (static geo), %d failed.",
                skin_bound,
                skin_skipped,
                skin_failed,
            )

            # ── Populate result ────────────────────────────────────────────
            result.success = True  # type: ignore[attr-defined]
            result.meshes_imported = len(usd_shapes)  # type: ignore[attr-defined]
            result.joints_imported = 0  # type: ignore[attr-defined]
            # Store for downstream use (animation binding, etc.)
            result._hybrid_usd_shapes = usd_shapes  # type: ignore[attr-defined]
            result._hybrid_controllers = controllers  # type: ignore[attr-defined]
            result._hybrid_rig_namespace = rig_namespace  # type: ignore[attr-defined]
            result._hybrid_sg_map = sg_map  # type: ignore[attr-defined]
            result._hybrid_sg_assigned = assigned  # type: ignore[attr-defined]

            # Force a scene refresh so VP2 and RfM IPR pick up all SG
            # assignments and visibility changes made during the workflow.
            try:
                cmds.refresh(force=True)
            except Exception:
                pass

            self._report_progress("[HYBRID] Import complete.", 100)
            self.logger.info("[HYBRID] ══════════════════════════════════════════════")
            self.logger.info(
                f"[HYBRID] COMPLETE  —  {len(usd_shapes)} mesh(es), "
                f"{assigned} SG(s) bound, {len(controllers)} controller(s)."
            )
            self.logger.info("[HYBRID] ══════════════════════════════════════════════")
            return True

        except Exception as exc:
            self.logger.error(f"[HYBRID] Unhandled exception: {exc}")
            self.logger.error(traceback.format_exc())
            return False

    # ================================================================== #
    # Phase implementations
    # ================================================================== #

    def _phase1_import_usd_geo(self, usd_path: Path) -> Tuple[List[str], List[str]]:
        """Import USD file as native Maya polygons with no shading.

        Uses ``shadingMode=[("none","default")]`` so no USD shaders are
        created — we supply the .rig.mb RfM SGs in Phase 4.
        Animation data and USD instances are intentionally skipped; this
        is a geometry-only snapshot for rendering.

        Args:
            usd_path: Path to the USD file.

        Returns:
            Tuple of (imported_root_nodes, all_mesh_shape_long_names).
        """
        before_meshes: Set[str] = set(cmds.ls(type="mesh", long=True) or [])

        import_kwargs: Dict[str, object] = {
            "file": str(usd_path).replace("\\", "/"),
            "primPath": "/",
            "shadingMode": [("none", "default")],
            "readAnimData": False,
            "useAsAnimationCache": False,
            "importInstances": False,
        }

        try:
            imported_roots: List[str] = list(cmds.mayaUSDImport(**import_kwargs) or [])
        except (TypeError, RuntimeError) as first_err:
            # MayaUSD 0.35.0 may not recognise certain kwargs.  Log and
            # try a minimal call with only the mandatory arguments.
            self.logger.warning(
                f"[HYBRID] Phase 1 — first mayaUSDImport attempt failed "
                f"({first_err}); retrying with minimal flags."
            )
            minimal_kwargs: Dict[str, object] = {
                "file": import_kwargs["file"],
                "primPath": "/",
                "shadingMode": [("none", "default")],
            }
            try:
                imported_roots = list(cmds.mayaUSDImport(**minimal_kwargs) or [])
            except Exception as retry_err:
                self.logger.error(f"[HYBRID] Phase 1 — mayaUSDImport failed on retry: {retry_err}")
                return [], []

        if not imported_roots:
            self.logger.warning("[HYBRID] Phase 1 — mayaUSDImport returned no root nodes.")
            return [], []

        after_meshes: Set[str] = set(cmds.ls(type="mesh", long=True) or [])
        new_shapes: List[str] = sorted(after_meshes - before_meshes)

        # Filter out intermediate shapes (history nodes created by Maya).
        visible_shapes = [
            s
            for s in new_shapes
            if cmds.objExists(s) and not cmds.getAttr(f"{s}.intermediateObject")
        ]

        self.logger.info(
            f"[HYBRID] Phase 1: mayaUSDImport created {len(visible_shapes)} "
            f"mesh shape(s) (excluded {len(new_shapes) - len(visible_shapes)} "
            f"intermediate)."
        )
        return imported_roots, visible_shapes

    def _phase2_load_rig_mb(self, rig_mb_path: Path, namespace: str) -> List[str]:
        """Import the .rig.mb into a dedicated namespace.

        Loading with a namespace ensures zero name-collision with the
        Phase-1 USD-imported shapes.

        Args:
            rig_mb_path: Path to the .rig.mb file.
            namespace:   Target Maya namespace (e.g. ``"Veteran_Rig"``).

        Returns:
            List of newly imported node names (may include SG nodes,
            transforms, shapes, etc.).
        """
        # Ensure namespace exists.
        if not cmds.namespace(exists=f":{namespace}"):
            cmds.namespace(add=namespace)

        # Snapshot loaded renderer plugins BEFORE import so we can evict any
        # that are loaded as a side effect of 'requires' declarations inside
        # the .rig.mb (e.g. 'requires "mtoa"' triggers Arnold installation
        # and pollutes render globals / triggers evalDeferred UI callbacks).
        try:
            _plugins_before: Set[str] = set(cmds.pluginInfo(query=True, listPlugins=True) or [])
        except Exception:
            _plugins_before = set()

        try:
            nodes: List[str] = list(
                cmds.file(
                    str(rig_mb_path),
                    i=True,
                    type="mayaBinary",
                    returnNewNodes=True,
                    preserveReferences=False,  # inline all references → no lock on inner nodes
                    ignoreVersion=True,
                    namespace=namespace,
                    mergeNamespacesOnClash=False,
                )
                or []
            )
        except Exception as load_err:
            self.logger.error(f"[HYBRID] Phase 2 — cmds.file import failed: {load_err}")
            return []

        # Evict renderer plugins loaded as side effects (Arnold / mtoa).
        # These pollute render globals and fire expensive shader-ball UI callbacks
        # that slow down the import and confuse RfM 27.2 render settings.
        #
        # IMPORTANT: Arnold's own unregisterArnoldRenderer() resets
        # defaultRenderGlobals.currentRenderer to a default value (usually
        # "mayaSoftware") and calls ActivateViewport20(), wiping the RfM
        # viewport mode.  Snapshot the current renderer BEFORE eviction so
        # we can restore it afterwards.
        _renderer_before: str = "renderman"
        try:
            _renderer_before = cmds.getAttr("defaultRenderGlobals.currentRenderer") or "renderman"
        except Exception:
            pass

        try:
            _plugins_after: Set[str] = set(cmds.pluginInfo(query=True, listPlugins=True) or [])
            for _plug in _plugins_after - _plugins_before:
                if any(kw in _plug.lower() for kw in ("arnold", "mtoa")):
                    try:
                        cmds.unloadPlugin(_plug, force=True)
                        self.logger.info(
                            "[HYBRID] Phase 2: evicted side-effect renderer plugin '%s'.",
                            _plug,
                        )
                    except Exception as _upe:
                        self.logger.debug(
                            "[HYBRID] Phase 2: could not unload '%s': %s", _plug, _upe
                        )
        except Exception:
            pass

        # Restore the renderer that was active before the .rig.mb import.
        # Arnold's unload resets currentRenderer → we put RenderMan back.
        try:
            cmds.setAttr(
                "defaultRenderGlobals.currentRenderer",
                _renderer_before,
                type="string",
            )
            self.logger.info(
                "[HYBRID] Phase 2: restored currentRenderer to '%s'.", _renderer_before
            )
        except Exception as _re:
            self.logger.debug("[HYBRID] Phase 2: could not restore renderer: %s", _re)

        if not nodes:
            self.logger.warning(
                f"[HYBRID] Phase 2 — cmds.file returned no nodes for: {rig_mb_path.name}"
            )
        return nodes

    def _phase3_build_sg_map(self, rig_shapes: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Build short-name keyed maps of rig SGs and rig shapes.

        Accepts a pre-computed list of mesh shapes (from the Phase 2
        pre/post snapshot diff) so the lookup is namespace-depth-agnostic.
        The .rig.mb typically contains a reference to a second .ma file
        whose nodes land at ``Namespace:InnerNS:shape`` — one level too
        deep for a simple ``Namespace:*`` wildcard query.

        Args:
            rig_shapes: Non-intermediate mesh shape long-names added by Phase 2.

        Returns:
            Tuple of (sg_map, rig_shape_map):
              * ``sg_map``        — short_shape_name → full SG name.
              * ``rig_shape_map`` — short_shape_name → full rig shape long-name.
            Phase 8 (skin transfer) needs the rig shape to read its
            skinCluster and copy weights onto the matched USD shape.
        """
        sg_map: Dict[str, str] = {}
        rig_shape_map: Dict[str, str] = {}

        # ── SG selection constants (hoisted out of loop for performance) ───────
        # In a typical Maya rig deformer stack the VISIBLE output shape
        # (``Body_GeoShapeDeformed``, intermediateObject=False) often carries
        # ONLY ngSkinTools annotation SGs (``asWhiteSG``, ``asRedSG`` …).
        # The REAL RfM SG (``Body_GeoSG``) is attached to the ORIGINAL input
        # shape (``Body_GeoShape``, intermediateObject=True) which we must NOT
        # skip when collecting SG candidates — only skip when iterating the
        # *primary* shape list that feeds Phase 8.
        # Strategy: collect SGs from the processed shape AND all sibling shapes
        # under the same transform (including intermediate ones).
        _rfm_surface_types = frozenset(
            {
                "PxrDisneyBsdf",
                "PxrSurface",
                "PxrLayerSurface",
                "PxrMarschnerHair",
                "PxrVolume",
            }
        )
        # ngSkinTools annotation SG short-name prefixes to skip in Pass 2.
        _annotation_prefixes = (
            "asWhite",
            "asRed",
            "asGreen",
            "asBlack",
            "asBlue",
            "asGreen2",
            "asBlue2",
            "as",
        )

        for shape in rig_shapes:
            if not cmds.objExists(shape):
                continue

            # Skip intermediate objects (history nodes).
            try:
                if cmds.getAttr(f"{shape}.intermediateObject"):
                    continue
            except ValueError:
                continue

            # ── Gather SGs from this shape AND all sibling shapes (incl. intermediate) ──
            # The deformed output shape may only have annotation SGs; the original
            # input shape (intermediate=True, same transform) has the real RfM SG.
            sgs_set: Set[str] = set(cmds.listSets(type=1, object=shape) or [])
            parents: List[str] = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parents:
                siblings: List[str] = (
                    cmds.listRelatives(
                        parents[0], shapes=True, fullPath=True, noIntermediate=False
                    )
                    or []
                )
                for sib in siblings:
                    if sib == shape:
                        continue
                    for ssg in cmds.listSets(type=1, object=sib) or []:
                        sgs_set.add(ssg)
            sgs: List[str] = list(sgs_set)

            if not sgs:
                continue

            chosen_sg: Optional[str] = None

            # Pass 1 — find first SG whose surfaceShader is a known RfM type.
            for sg in sgs:
                ss_nodes = (
                    cmds.listConnections(
                        f"{sg}.surfaceShader",
                        source=True,
                        destination=False,
                    )
                    or []
                )
                for ss in ss_nodes:
                    try:
                        if cmds.nodeType(ss) in _rfm_surface_types:
                            chosen_sg = sg
                            break
                    except Exception:
                        pass
                if chosen_sg:
                    break

            # Pass 2 — no RfM SG found; take first SG that isn't an annotation SG.
            if chosen_sg is None:
                for sg in sgs:
                    sg_short = sg.split(":")[-1]
                    if not any(sg_short.startswith(p) for p in _annotation_prefixes):
                        chosen_sg = sg
                        break

            # Pass 3 — last resort: first in list.
            if chosen_sg is None:
                chosen_sg = sgs[0]

            # Key: short shape name without namespace prefix or DAG separator.
            short = shape.split(":")[-1].split("|")[-1]
            sg_map[short] = chosen_sg
            rig_shape_map[short] = shape
            self.logger.info(
                "[HYBRID] Phase 3: '%s' → SG '%s' (from %d candidate(s): %s)",
                short,
                chosen_sg,
                len(sgs),
                ", ".join(sgs),
            )

        self.logger.info(
            f"[HYBRID] Phase 3: found {len(sg_map)} mesh→SG pair(s) "
            f"from {len(rig_shapes)} rig shape(s)."
        )
        return sg_map, rig_shape_map

    @staticmethod
    def _mesh_base_name(name: str) -> str:
        """Strip namespace, DAG path, and geometry suffixes for fuzzy matching.

        Used by Phase 4 to match USD-imported shape names against .rig.mb
        SG-map keys regardless of naming convention differences between the
        USD export and the rig file.

        Handles two common divergence patterns:

        * **USD export prefix/suffix** — ``model_`` prefix added by the USD
          exporter, and ``_Geo_usdExport[N]Shape`` compound suffix (or plain
          ``_usdExport[N]`` anywhere in the name).
        * **Maya deformer suffix** — ``.rig.mb`` shapes come through the
          deformer stack and land as ``X_GeoShapeDeformed`` / ``X_Deformed``.

        Examples::

            "model_Body_Geo_usdExportShape"  → "body"
            "model_Body_Geo_usdExport1Shape" → "body"
            "Body_GeoShapeDeformed"          → "body"
            "model_L_Button_01_Geo_usdExportShape" → "l_button_01"
            "L_Button_01_GeoShapeDeformed"         → "l_button_01"
            "FitEyeSphereShape"              → "fiteyesphere"
        """
        n = name.split(":")[-1].split("|")[-1]
        # 1. Strip leading model_ prefix (USD export convention).
        n = re.sub(r"^model_", "", n, flags=re.I)
        # 2. Strip compound _Geo_usdExport[N]Shape suffix as a unit — this
        #    pattern appears when the USD exporter writes intermediate geo
        #    nodes (e.g. "Body_Geo_usdExportShape", "Body_Geo_usdExport1Shape").
        n = re.sub(r"_Geo_usdExport\d*Shape$", "", n, flags=re.I)
        # 3. Strip any remaining _usdExport[N] fragment (handles plain
        #    "_usdExport" or "_usdExportShape" not caught above).
        n = re.sub(r"_usdExport\d*", "", n, flags=re.I)
        # 4. Strip Maya deformer stack suffix: GeoShapeDeformed / ShapeDeformed
        #    / Deformed (with optional leading underscore and trailing digits).
        n = re.sub(r"[_]?(GeoShapeDeformed|ShapeDeformed|Deformed)\d*$", "", n, flags=re.I)
        # 5. Strip remaining shape/geo suffixes: GeoShape / Shape / _Geo / Mesh
        #    (with optional leading underscore and trailing digits).
        n = re.sub(r"[_]?(GeoShape|Shape|Geo|Mesh)\d*$", "", n, flags=re.I)
        # 6. Strip trailing underscores only (preserve _01/_02 numbering).
        n = re.sub(r"_+$", "", n)
        return n.lower()

    def _match_sg_key(self, usd_short: str, sg_map: Dict[str, str]) -> Optional[str]:
        """Return the rig-side short_name key matching a USD shape short name.

        Runs the four matching strategies in priority order and returns the
        winning key (or None).  Centralising this logic ensures Phase 4 (SG
        assignment) and Phase 8 (skin transfer) use IDENTICAL pairings.
        """
        # 1. exact
        if usd_short in sg_map:
            return usd_short
        # 2. case-insensitive exact
        short_lower = usd_short.lower()
        for k in sg_map:
            if k.lower() == short_lower:
                return k
        # 3. normalised base-name exact
        usd_base = self._mesh_base_name(usd_short)
        if usd_base:
            for k in sg_map:
                if self._mesh_base_name(k) == usd_base:
                    return k
            # 4. normalised substring containment, prefer longest
            best_key: Optional[str] = None
            best_score = 0
            for k in sg_map:
                rig_base = self._mesh_base_name(k)
                if rig_base and (usd_base in rig_base or rig_base in usd_base):
                    score = len(rig_base) + len(usd_base)
                    if score > best_score:
                        best_score = score
                        best_key = k
            if best_key is not None:
                return best_key
        return None

    def _phase4_assign_sgs(
        self,
        usd_shapes: List[str],
        sg_map: Dict[str, str],
        rig_shape_map: Dict[str, str],
    ) -> Tuple[int, int, List[Tuple[str, str]]]:
        """Assign the .rig.mb SGs to the USD-imported mesh shapes.

        The USD shapes have no skinCluster lock so ``cmds.sets`` succeeds.
        A ``cmds.hyperShade(assign=)`` at transform level is used as a
        fallback for any shape that rejects the direct set-membership call.

        Args:
            usd_shapes:    Long-name mesh shapes from Phase 1.
            sg_map:        Short-name → SG mapping from Phase 3.
            rig_shape_map: Short-name → rig shape long-name from Phase 3.

        Returns:
            Tuple of (assigned_count, failed_count, pairings) where
            ``pairings`` is a list of (usd_shape, rig_shape) for every
            successfully-matched mesh.  Phase 8 consumes this to copy
            skinCluster weights from the hidden rig mesh onto the visible
            USD mesh so the controllers actually deform what's on screen.
        """
        assigned = 0
        failed = 0
        _annotation_skipped = 0
        pairings: List[Tuple[str, str]] = []

        for shape in usd_shapes:
            if not cmds.objExists(shape):
                continue

            short = shape.split("|")[-1]
            usd_base = self._mesh_base_name(short)

            # ── Step 0: strip USD viewport-color overrides ───────────────────
            # ``mayaUSDImport`` attaches ``primvars:displayColor`` as a Maya
            # colorSet AND flips ``mesh.displayColors=1``.  When that flag
            # is on, VP2's mesh translator BYPASSES the assigned shading
            # engine and renders the per-vertex colorSet instead — which
            # for a default USD export is white.  This is why the original
            # .rig.mb mesh shows materials in VP2 but the USD-imported
            # mesh (with the same SG bound) appears flat white.  We must:
            #   (a) turn off ``displayColors``
            #   (b) delete every colorSet so VP2 falls back to the SG.
            # Also clear DAG draw-overrides which mayaUSDImport occasionally
            # sets on USD prims that had ``visibility = invisible``.
            try:
                if cmds.attributeQuery("displayColors", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.displayColors", 0)
            except Exception as dc_err:
                self.logger.debug(
                    "[HYBRID] Phase 4: could not clear displayColors on '%s': %s",
                    short,
                    dc_err,
                )
            try:
                color_sets = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
                for cs in color_sets:
                    try:
                        cmds.polyColorSet(shape, delete=True, colorSet=cs)
                    except Exception:
                        pass
            except Exception as cs_err:
                self.logger.debug(
                    "[HYBRID] Phase 4: could not clear colorSets on '%s': %s",
                    short,
                    cs_err,
                )
            # Each ``polyColorSet(delete=True)`` call above appends a
            # ``deleteColorSet`` deformer node into the shape's construction
            # history and connects its ``.output`` to ``shape.inMesh``.
            # By the time Phase 8 runs, those shapes would test as "already
            # driven" and be skipped — so 18 / 28 meshes never received the
            # rig's worldMesh connection.  Baking the construction history
            # here removes the ``deleteColorSet`` chain and frees ``inMesh``
            # for Phase 8.  This is safe: USD-imported shapes have no
            # meaningful deformer history of their own (the rig's skinCluster
            # lives on the .rig.mb side only).
            try:
                cmds.delete(shape, constructionHistory=True)
            except Exception as ch_err:
                self.logger.debug(
                    "[HYBRID] Phase 4: could not bake history on '%s': %s",
                    short,
                    ch_err,
                )
            try:
                if cmds.attributeQuery("overrideEnabled", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.overrideEnabled", 0)
            except Exception:
                pass

            matched_key = self._match_sg_key(short, sg_map)
            sg = sg_map.get(matched_key) if matched_key else None

            if sg is None or not cmds.objExists(sg):
                self.logger.warning(
                    "[HYBRID] Phase 4: no SG for '%s' (base='%s') — skipped.",
                    short,
                    usd_base,
                )
                failed += 1
                continue

            # ── Guard: skip annotation SGs (ngSkinTools corrective helpers) ──
            # ngSkinTools2 creates per-mesh annotation SGs (asWhiteSG, asRedSG,
            # asGreenSG, asBlackSG, asBlueSG, asGreen2SG, asBlue2SG) that carry
            # no RenderMan surface shader.  Corrective helper shapes whose rig
            # counterparts live only in annotation SGs get matched here.
            # Do NOT assign an annotation SG to the USD shape — the shape will
            # be hidden in Phase 8 anyway, and assigning it causes RfM's
            # scene_updater to warn "asWhiteSG is missing a RenderMan material"
            # for every single render.  The shape IS added to pairings so
            # Phase 8 detects it as a corrective helper (no skinCluster) and
            # hides its USD transform.
            _annotation_sg_prefixes = (
                "asWhite",
                "asRed",
                "asGreen",
                "asBlack",
                "asBlue",
                "asGreen2",
                "asBlue2",
                "as",
            )
            _sg_short_p4 = sg.split(":")[-1]
            if any(_sg_short_p4.startswith(_p) for _p in _annotation_sg_prefixes):
                self.logger.debug(
                    "[HYBRID] Phase 4: '%s' → annotation SG '%s' — skipped "
                    "(corrective helper; Phase 8 will hide its USD transform).",
                    short,
                    sg,
                )
                _annotation_skipped += 1
                _rig_shape_for_pair = rig_shape_map.get(matched_key) if matched_key else None
                if _rig_shape_for_pair and cmds.objExists(_rig_shape_for_pair):
                    pairings.append((shape, _rig_shape_for_pair))
                continue

            # ── Step A: detach from ALL existing SGs ─────────────────────────
            # The USD import wires every shape into ``initialShadingGroup``.
            # Must fully remove before adding to the target SG, otherwise VP2
            # and RfM keep showing lambert1 (white/grey).
            # IMPORTANT: do NOT use ``cmds.hyperShade(assign=sg)`` here — it
            # has a destructive side-effect of re-enabling ``inheritTransform``
            # on any transform that ``mayaUSDImport`` deliberately set to 0 to
            # decouple the mesh from the USD hierarchy world matrix.
            # Re-enabling ``inheritTransform`` corrupts the
            # ``worldInverseMatrix[0]`` that Phase 8 feeds into
            # ``transformGeometry``, causing all meshes to render at wrong
            # world positions ("blown up" render).
            try:
                existing_sgs = cmds.listSets(object=shape, type=1) or []
                for old_sg in existing_sgs:
                    if old_sg == sg:
                        continue
                    try:
                        # Correct remove syntax: edit=True, remove=<setName>
                        cmds.sets(shape, edit=True, remove=old_sg)
                    except Exception:
                        pass
            except Exception as detach_err:
                self.logger.debug(
                    "[HYBRID] Phase 4: detach failed for '%s': %s", short, detach_err
                )

            # ── Step B: assign via forceElement directly on the shape ────────
            # ``cmds.sets(shape, edit=True, forceElement=sg)`` creates a
            # whole-shape ``instObjGroups[0]`` binding — exactly what the
            # Attribute Editor reads and what RfM / VP2 render from.
            # No selection manipulation → no ``inheritTransform`` side effect.
            assignment_ok = False
            try:
                cmds.sets(shape, edit=True, forceElement=sg)
                connected = self._read_connected_sg(shape)
                if connected and (sg in connected or sg.split(":")[-1] in connected):
                    assignment_ok = True
                    self.logger.info("[HYBRID] Phase 4: '%s' → '%s' ✓", short, sg)
            except Exception as fe_err:
                self.logger.debug(
                    "[HYBRID] Phase 4: forceElement failed for '%s': %s", short, fe_err
                )

            # ── Step C: connectAttr fallback ─────────────────────────────────
            # If forceElement rejected the assignment (e.g. SG has member
            # restrictions), wire ``instObjGroups[0]`` directly to the next
            # available ``dagSetMembers`` slot on the target SG.
            if not assignment_ok:
                try:
                    existing_idx = cmds.getAttr(f"{sg}.dagSetMembers", multiIndices=True) or []
                    next_idx = (max(existing_idx) + 1) if existing_idx else 0
                    cmds.connectAttr(
                        f"{shape}.instObjGroups[0]",
                        f"{sg}.dagSetMembers[{next_idx}]",
                        force=True,
                    )
                    connected = self._read_connected_sg(shape)
                    if connected and (sg in connected or sg.split(":")[-1] in connected):
                        assignment_ok = True
                        self.logger.info(
                            "[HYBRID] Phase 4 (connectAttr): '%s' → '%s' ✓", short, sg
                        )
                except Exception as ca_err:
                    self.logger.debug(
                        "[HYBRID] Phase 4: connectAttr fallback failed for '%s': %s",
                        short,
                        ca_err,
                    )

            if assignment_ok:
                assigned += 1
                # Record pairing for Phase 8 skin transfer.  Even if the
                # rig shape has no skinCluster, Phase 8 will harmlessly
                # skip it; only matched pairs are eligible.
                rig_shape = rig_shape_map.get(matched_key) if matched_key else None
                if rig_shape and cmds.objExists(rig_shape):
                    pairings.append((shape, rig_shape))
                continue

            self.logger.warning("[HYBRID] Phase 4: could not bind '%s' → '%s'.", short, sg)
            failed += 1

        if _annotation_skipped:
            self.logger.info(
                "[HYBRID] Phase 4: %d corrective helper(s) mapped to annotation SGs — "
                "skipped assignment (Phase 8 will hide their USD transforms).",
                _annotation_skipped,
            )
        cmds.select(clear=True)
        return assigned, failed, pairings

    def _phase5_hide_rig_geo(self, rig_shapes: List[str]) -> Tuple[int, Set[str]]:
        """Hide the .rig.mb mesh transforms so only USD geometry is visible.

        Accepts the pre-computed rig mesh shape list (from Phase 2 snapshot
        diff) so the lookup is namespace-depth-agnostic.

        Args:
            rig_shapes: Non-intermediate mesh shape long-names added by Phase 2.

        Returns:
            Tuple of (hidden_count, hidden_transform_long_names).  The set is
            forwarded to Phase 6 so ancestor-walk skips rig mesh nodes.
        """
        transforms_done: Set[str] = set()

        # ngSkinTools annotation SG short-name prefixes — same list as Phase 3.
        _annotation_prefixes = (
            "asWhite",
            "asRed",
            "asGreen",
            "asBlack",
            "asBlue",
            "asGreen2",
            "asBlue2",
            "as",
        )

        # Render stats to zero on each rig shape so RfM does not warn about
        # annotation SGs (asWhiteSG / asRedSG …) that have no RenderMan surface
        # shader.  Setting primaryVisibility=0 tells RfM to skip those shapes
        # entirely.  We also explicitly remove each rig shape from every
        # annotation SG so RfM's scene_updater never encounters them even if
        # it scans SG membership lists post-import.
        _render_stats = (
            "primaryVisibility",
            "castsShadows",
            "receiveShadows",
            "motionBlur",
            "visibleInReflections",
            "visibleInRefractions",
        )

        for shape in rig_shapes:
            if not cmds.objExists(shape):
                continue
            try:
                if cmds.getAttr(f"{shape}.intermediateObject"):
                    continue
            except ValueError:
                pass

            # Zero render stats on the shape so RfM ignores it completely.
            for stat in _render_stats:
                try:
                    if cmds.attributeQuery(stat, node=shape, exists=True):
                        cmds.setAttr(f"{shape}.{stat}", 0)
                except Exception:
                    pass

            # Remove this shape from every annotation SG so RfM's scene_updater
            # never warns "asWhiteSG is missing a RenderMan material".
            # We use ALL shapes (including intermediate siblings) here because
            # ngSkinTools attaches annotation SGs to both.
            all_siblings: List[str] = [shape]
            _parents_tmp = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if _parents_tmp:
                all_siblings = cmds.listRelatives(
                    _parents_tmp[0], shapes=True, fullPath=True, noIntermediate=False
                ) or [shape]
            for sib in all_siblings:
                if not cmds.objExists(sib):
                    continue
                for ssg in list(cmds.listSets(type=1, object=sib) or []):
                    sg_short = ssg.split(":")[-1]
                    if any(sg_short.startswith(p) for p in _annotation_prefixes):
                        try:
                            cmds.sets(sib, edit=True, remove=ssg)
                        except Exception:
                            pass

            parents: List[str] = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            for transform in parents:
                if transform in transforms_done:
                    continue
                try:
                    cmds.setAttr(f"{transform}.visibility", False)
                    transforms_done.add(transform)
                except Exception as hide_err:
                    self.logger.debug(
                        "[HYBRID] Phase 5: could not hide '%s': %s",
                        transform,
                        hide_err,
                    )

        return len(transforms_done), transforms_done

    def _phase6_collect_controllers(
        self,
        rig_curve_shapes: List[str],
        hidden_mesh_transforms: Set[str],
    ) -> List[str]:
        """Collect NURBS controller transforms from the loaded .rig.mb namespace.

        Accepts the pre-computed nurbsCurve shape list (from Phase 2 snapshot
        diff) so the lookup is namespace-depth-agnostic.

        NURBS controllers must be visible all the way to the scene root — rigs
        are typically saved with group nodes set to ``visibility=False``.  This
        method walks the **full ancestor chain** of every controller transform
        and enables visibility on every node, skipping only the rig mesh
        transforms that Phase 5 deliberately hid.

        Args:
            rig_curve_shapes:      nurbsCurve shape long-names added by Phase 2.
            hidden_mesh_transforms: Set of rig mesh transform long-names hidden
                                    by Phase 5 — these are never made visible.

        Returns:
            List of NURBS controller transform long-names.
        """
        controller_transforms: List[str] = []
        seen: Set[str] = set()
        # Track every ancestor we already processed to avoid redundant work.
        ancestors_done: Set[str] = set()

        for shape in rig_curve_shapes:
            if not cmds.objExists(shape):
                continue
            parents: List[str] = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            for t in parents:
                if t not in seen:
                    seen.add(t)
                    controller_transforms.append(t)

                # Walk the full ancestor chain up to the world root, enabling
                # visibility on every transform except rig mesh nodes.
                node: Optional[str] = t
                while node:
                    if node in ancestors_done:
                        break  # already processed this branch
                    ancestors_done.add(node)
                    if node not in hidden_mesh_transforms:
                        try:
                            cmds.setAttr(f"{node}.visibility", True)
                        except Exception:
                            pass
                    up: List[str] = cmds.listRelatives(node, parent=True, fullPath=True) or []
                    node = up[0] if up else None

        self.logger.info(
            f"[HYBRID] Phase 6: {len(controller_transforms)} NURBS controller "
            f"transform(s) collected from {len(rig_curve_shapes)} curve shape(s)."
        )
        return controller_transforms

    def _phase7_post_import_sweep(self, usd_roots: List[str]) -> Dict[str, int]:
        """Delete non-polygon nodes imported from the USD stage.

        We only want polygon meshes from the USD.  NurbsCurves, joints,
        cameras, and lights imported from the USD stage are removed; the
        rig controls come exclusively from the .rig.mb (Phase 2).

        Args:
            usd_roots: Root node names returned by ``mayaUSDImport`` in Phase 1.

        Returns:
            Dict of {node_type_label: deleted_count}.
        """
        counts: Dict[str, int] = {
            "nurbsCurve_transform": 0,
            "joint": 0,
            "camera": 0,
            "light": 0,
        }

        # Gather all descendants of the USD import roots.
        all_usd_nodes: List[str] = []
        for root in usd_roots:
            if cmds.objExists(root):
                all_usd_nodes.append(root)
                descendants = cmds.listRelatives(root, allDescendents=True, fullPath=True) or []
                all_usd_nodes.extend(descendants)

        # Collect transforms to delete whose shapes are unwanted.
        to_delete: List[str] = []
        for node in all_usd_nodes:
            if not cmds.objExists(node):
                continue
            node_type = cmds.nodeType(node)
            if node_type == "joint":
                to_delete.append(node)
                counts["joint"] += 1
            elif node_type == "camera":
                to_delete.append(node)
                counts["camera"] += 1
            elif node_type in ("nurbsCurve",):
                # Delete the transform parent of the curve shape.
                parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
                for p in parents:
                    if p not in to_delete and cmds.objExists(p):
                        to_delete.append(p)
                        counts["nurbsCurve_transform"] += 1
            elif "Light" in node_type:
                parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
                for p in parents:
                    if p not in to_delete and cmds.objExists(p):
                        to_delete.append(p)
                        counts["light"] += 1

        # Delete (top-level transforms first to avoid double-delete errors).
        to_delete = list(dict.fromkeys(to_delete))
        for node in to_delete:
            if cmds.objExists(node):
                try:
                    cmds.delete(node)
                except Exception as del_err:
                    self.logger.debug(f"[HYBRID] Phase 7: could not delete '{node}': {del_err}")

        return counts

    # ================================================================== #
    # Phase 8: deformation transfer (rig mesh → USD mesh via worldMesh)
    # ================================================================== #

    def _phase8_transfer_skin_weights(
        self,
        pairings: List[Tuple[str, str]],
        all_rig_shapes: List[str],
    ) -> Tuple[int, int, int]:
        """Wire each USD mesh to follow its paired rig mesh via worldMesh sharing.

        **Why worldMesh instead of skinCluster.outputGeometry (the definitive fix)**

        ngSkinTools2 2.4.0 registers a **custom graph evaluator** inside
        Maya's evaluation manager.  This evaluator writes deformation
        directly to the mesh geometry output *without* using the standard
        DG ``inMesh`` connection.  From a ``listConnections`` perspective
        ``shape.inMesh`` has no source — the DG connection does not exist
        for ngSkinTools2-managed meshes.  Previous approaches that hunted
        for ``skinCluster.outputGeometry[N]`` therefore found nothing for
        25 of 28 shapes and fell through to "static geo → skipped".

        ``rig_shape.worldMesh[0]`` is the **final post-evaluation world-
        space geometry** of the rig mesh.  It is computed by whatever path
        Maya's evaluation manager chose — standard DG, Cached Playback,
        ngSkinTools2 custom evaluator, blendShapes, correctives — all of
        it is already baked into that attribute.

        A single ``transformGeometry`` node with the USD mesh parent's
        ``worldInverseMatrix[0]`` as the ``transform`` input converts the
        world-space result back to the USD mesh's local (object) space.
        When the USD parent is at the world origin the inverse matrix is
        identity and the node is a zero-cost passthrough.

        **Pull-based evaluation with hidden rig meshes**

        Even though Phase 5 hid the rig meshes (``visibility=False``),
        the downstream USD mesh (visible) creates a DG pull request that
        propagates backwards through the ``transformGeometry`` node to
        ``rig_shape.worldMesh[0]``, forcing the rig mesh to fully evaluate
        on every frame regardless of its visibility state.

        **Rigid accessories**

        Meshes with no skinCluster (belt buckles, buttons, boot clasps)
        also benefit: their ``worldMesh[0]`` changes as their parent joint
        moves, so the USD copy correctly follows the rig joint every frame
        without any weight data needed.

        **Architecture per pair**

        ``rig_shape.worldMesh[0]``
            → ``{name}_p8_tg.inputGeometry``

        ``usd_parent.worldInverseMatrix[0]``
            → ``{name}_p8_tg.transform``

        ``{name}_p8_tg.outputGeometry``
            → ``usd_shape.inMesh``

        Args:
            pairings:       (usd_shape, rig_shape) long-names from Phase 4.
            all_rig_shapes: All non-intermediate rig mesh shapes from Phase 2
                            (used only for topology-mismatch fallback search).

        Returns:
            Tuple of (connected, skipped, failed).
        """
        self.logger.info(
            "[HYBRID] Phase 8 v5: worldMesh deformation sharing — %d pair(s) to process.",
            len(pairings),
        )

        connected = 0
        skipped = 0
        failed = 0
        # Tracks which active_rig_shape nodes have already been wired to a USD
        # shape.  Used in gate 1.5 (duplicate USD prim detection) below.
        wired_rig_shapes: Set[str] = set()

        # ── Sort so canonical USD shapes always beat Maya auto-numbered duplicates ──
        # mayaUSDImport resolves naming collisions by appending a digit to the
        # transform (e.g. model_Body_Geo_usdExport → model_Body_Geo_usdExport1).
        # The duplicate's parent transform has a different worldInverseMatrix
        # than the canonical one, so connecting it through transformGeometry
        # yields wrong vertex positions ("blown up" body in render).
        # Guarantee that the shape WITHOUT a trailing digit processes first so it
        # always wins the wired_rig_shapes gate below.
        _dup_suffix_re = re.compile(r"\d+Shape$")
        pairings = sorted(
            pairings,
            key=lambda p: (1 if _dup_suffix_re.search(p[0].split("|")[-1]) else 0, p[0]),
        )

        for usd_shape, rig_shape in pairings:
            usd_short = usd_shape.split("|")[-1]
            rig_short = rig_shape.split("|")[-1]

            if not (cmds.objExists(usd_shape) and cmds.objExists(rig_shape)):
                self.logger.warning(
                    "[HYBRID] Phase 8: ('%s', '%s') — one or both nodes missing, skipped.",
                    usd_short,
                    rig_short,
                )
                failed += 1
                continue

            # ── 0. Render-visibility gate: skinned surface geo only ───────
            # A standard Maya character rig contains two categories of
            # non-intermediate mesh shape:
            #
            #   • Skinned surface geometry — Maya's skinCluster deformer
            #     ALWAYS appends "Deformed" to the output shape name:
            #     Body_GeoShapeDeformed, Jacket_GeoShapeDeformed, etc.
            #     These are the hero meshes that must render.
            #
            #   • Corrective / helper meshes — blend-shape target "area
            #     meshes", fit spheres, proxy shapes used internally to
            #     drive facial correctives (FitEyeSphere, EyeLidInnerArea,
            #     ForeHeadArea, LipInnerArea …).  These carry NO skinCluster
            #     so they have NO "Deformed" suffix.  They must NOT render.
            #
            # Previous attempt: read rig_shape.primaryVisibility → FAILED.
            # Riggers hide corrective helpers via transform visibility=False,
            # NOT via the render-stats attribute.  primaryVisibility was True
            # on every helper so the gate never fired and all 7 helpers
            # rendered as floating polygon planes / spheres → "blown up".
            #
            # Correct discriminator: the "Deformed" suffix.  It is written
            # by Maya's internal skinCluster node and cannot be set manually.
            # Any rig shape WITHOUT this suffix is unskinned → helper → skip.
            _rig_bare = rig_shape.split("|")[-1].split(":")[-1]
            _is_skinned = bool(re.search(r"Deformed\d*$", _rig_bare))
            if not _is_skinned:
                # This is a corrective/helper mesh — not surface geometry.
                # Setting primaryVisibility=False alone is insufficient:
                # VP2 ignores that flag and shows the mesh anyway, AND
                # RenderMan can still pick it up via indirect/shadow rays.
                #
                # Full suppression requires hiding the TRANSFORM (same
                # approach Phase 5 uses for rig mesh transforms).  This
                # removes the helper from VP2, all render passes, and all
                # shadow/GI calculations simultaneously.
                _usd_parent = (
                    cmds.listRelatives(usd_shape, parent=True, fullPath=True) or [None]
                )[0]
                try:
                    # Hide the transform — invisible in VP2 AND all renders.
                    if _usd_parent and cmds.objExists(_usd_parent):
                        cmds.setAttr(f"{_usd_parent}.visibility", False)
                except Exception:
                    pass
                try:
                    # Belt-and-suspenders: also zero out all render stats
                    # in case something re-enables the transform later.
                    cmds.setAttr(f"{usd_shape}.primaryVisibility", False)
                    cmds.setAttr(f"{usd_shape}.castsShadows", False)
                    cmds.setAttr(f"{usd_shape}.receiveShadows", False)
                    cmds.setAttr(f"{usd_shape}.visibleInReflections", False)
                    cmds.setAttr(f"{usd_shape}.visibleInRefractions", False)
                except Exception:
                    pass
                self.logger.info(
                    "[HYBRID] Phase 8: '%s' → rig '%s' has no skinCluster "
                    "(corrective helper) — USD transform hidden, skipped.",
                    usd_short,
                    _rig_bare,
                )
                skipped += 1
                continue

            # ── 1. Vertex count check — topology must match ────────────────
            try:
                usd_vtx = cmds.polyEvaluate(usd_shape, vertex=True)
                rig_vtx = cmds.polyEvaluate(rig_shape, vertex=True)
            except Exception:
                usd_vtx = rig_vtx = None

            active_rig_shape = rig_shape

            if usd_vtx is not None and rig_vtx is not None and usd_vtx != rig_vtx:
                # Primary rig shape vertex count doesn't match — search
                # all_rig_shapes for an alternate with the same base name
                # and the correct vertex count (e.g. a *Deformed sibling).
                usd_base = self._mesh_base_name(usd_short)
                alt: Optional[str] = None
                for cand in all_rig_shapes:
                    if cand == rig_shape:
                        continue
                    if self._mesh_base_name(cand.split("|")[-1]) != usd_base:
                        continue
                    try:
                        if cmds.polyEvaluate(cand, vertex=True) == usd_vtx:
                            alt = cand
                            break
                    except Exception:
                        continue
                if alt:
                    active_rig_shape = alt
                    self.logger.info(
                        "[HYBRID] Phase 8: '%s' vtx mismatch (rig %d vs usd %d) — "
                        "resolved alternate rig shape '%s' (%d vtx).",
                        usd_short,
                        rig_vtx,
                        usd_vtx,
                        alt.split("|")[-1],
                        usd_vtx,
                    )
                else:
                    self.logger.warning(
                        "[HYBRID] Phase 8: '%s' vtx mismatch (rig %d vs usd %d) — "
                        "no alternate found → skipped.",
                        usd_short,
                        rig_vtx,
                        usd_vtx,
                    )
                    skipped += 1
                    continue

            active_rig_short = active_rig_shape.split("|")[-1]

            # ── 1.5. Duplicate USD prim gate ──────────────────────────────
            # mayaUSDImport can create multiple Maya shapes from the same
            # logical mesh when a prim path appears more than once in the
            # USD hierarchy, or when a naming collision causes Maya to
            # auto-increment the transform name (e.g. Body_Geo_usdExport
            # → Body_Geo_usdExport1).  Both shapes resolve to the SAME
            # rig counterpart and both pass the _is_skinned test.  Each
            # gets its own transformGeometry node driven by
            # active_rig_shape.worldMesh[0], but the duplicate's parent
            # transform has a DIFFERENT worldInverseMatrix — the mesh
            # decomposes into the wrong local space and renders at the
            # wrong position → looks like a ghost/blown-up second body.
            #
            # Fix: first occurrence wins.  Any subsequent USD shape that
            # resolves to the same active_rig_shape is a duplicate; hide
            # its parent transform so it contributes nothing to VP2 or
            # any render pass.
            if active_rig_shape in wired_rig_shapes:
                _dup_parent = (
                    cmds.listRelatives(usd_shape, parent=True, fullPath=True) or [None]
                )[0]
                try:
                    if _dup_parent and cmds.objExists(_dup_parent):
                        cmds.setAttr(f"{_dup_parent}.visibility", False)
                except Exception:
                    pass
                try:
                    cmds.setAttr(f"{usd_shape}.primaryVisibility", False)
                    cmds.setAttr(f"{usd_shape}.castsShadows", False)
                    cmds.setAttr(f"{usd_shape}.receiveShadows", False)
                    cmds.setAttr(f"{usd_shape}.visibleInReflections", False)
                    cmds.setAttr(f"{usd_shape}.visibleInRefractions", False)
                except Exception:
                    pass
                self.logger.info(
                    "[HYBRID] Phase 8: '%s' is a duplicate USD shape for rig '%s' "
                    "— already wired, duplicate transform hidden.",
                    usd_short,
                    active_rig_short,
                )
                skipped += 1
                continue

            # ── 2. Skip if USD shape already driven ───────────────────────
            existing = (
                cmds.listConnections(
                    f"{usd_shape}.inMesh",
                    source=True,
                    destination=False,
                    plugs=True,
                )
                or []
            )
            if existing:
                self.logger.info(
                    "[HYBRID] Phase 8: '%s' already driven by '%s' → skipped.",
                    usd_short,
                    existing[0],
                )
                skipped += 1
                continue

            # ── 3. Wire worldMesh → inMesh (direct, no transformGeometry) ──
            #
            # Phase 4.5 guarantees that every USD mesh parent transform has:
            #   • All TRS attrs zeroed to identity (translate=0, rotate=0,
            #     scale=1, all pivots=0, shear=0)
            #   • inheritsTransform = 0  (node ignores parent hierarchy)
            #   • All those attrs locked so nothing downstream can perturb them
            #
            # Consequence: usd_parent.worldMatrix == identity for all time.
            # Object space == world space for the USD mesh.
            #
            # Therefore ``rig_shape.worldMesh[0]`` (world-space deformed
            # geometry) can be connected DIRECTLY to ``usd_shape.inMesh``
            # without any matrix conversion step.  The transformGeometry
            # node that was used previously read usd_parent.worldInverseMatrix
            # to cancel the parent transform; because worldInverseMatrix is a
            # live-evaluated attribute any stale cache or evaluation-order
            # asymmetry between parallel threads could produce a non-identity
            # matrix at render time, scaling every vertex by an unexpected
            # factor and inflating the entire mesh.  Eliminating that
            # dependency removes the inflation error path entirely.
            try:
                # Source: world-space post-evaluation rig mesh geometry.
                # worldMesh[0] reflects ALL deformers including ngSkinTools2
                # custom evaluator — no skinCluster hunting needed.
                cmds.connectAttr(
                    f"{active_rig_shape}.worldMesh[0]",
                    f"{usd_shape}.inMesh",
                    force=True,
                )
                connected += 1
                wired_rig_shapes.add(active_rig_shape)
                self.logger.info(
                    "[HYBRID] Phase 8: '%s' ← '%s'.worldMesh (vtx=%s) ✓",
                    usd_short,
                    active_rig_short,
                    usd_vtx,
                )

            except Exception as wire_err:
                self.logger.warning(
                    "[HYBRID] Phase 8: wiring failed for '%s' ← '%s': %s",
                    usd_short,
                    active_rig_short,
                    wire_err,
                )
                failed += 1

        return connected, skipped, failed

    # ================================================================== #
    # USD-only fallback (no .rig.mb available)
    # ================================================================== #

    def _usd_only_fallback(self, usd_path: Path, result: object) -> bool:
        """Import USD as native Maya polys with UsdPreviewSurface materials.

        Called when no companion .rig.mb is available.  The result will
        have geometry but no RfM shaders and no NURBS controllers.

        Args:
            usd_path: Path to the USD file.
            result:   ``ImportResult`` mutated in-place.

        Returns:
            ``True`` if at least one mesh was imported.
        """
        self.logger.info("[HYBRID] USD-only fallback: importing with UsdPreviewSurface materials.")
        try:
            cmds.mayaUSDImport(
                file=str(usd_path).replace("\\", "/"),
                primPath="/",
                shadingMode=[("useRegistry", "UsdPreviewSurface")],
                readAnimData=False,
            )
        except Exception as err:
            self.logger.error(f"[HYBRID] USD-only fallback failed: {err}")
            return False

        mesh_shapes: List[str] = cmds.ls(type="mesh", long=True) or []
        visible = [
            s
            for s in mesh_shapes
            if cmds.objExists(s) and not cmds.getAttr(f"{s}.intermediateObject")
        ]
        result.meshes_imported = len(visible)  # type: ignore[attr-defined]
        return len(visible) > 0

    # ================================================================== #
    # Private helpers
    # ================================================================== #

    @staticmethod
    def _read_connected_sg(shape: str) -> Optional[str]:
        """Return the name of the SG connected to any shape.instObjGroups slot.

        Checks ``instObjGroups[0]`` first (the whole-shape slot), then walks
        all populated ``instObjGroups`` indices so face-component or
        alternate-instance connections are also detected.

        Args:
            shape: Long-name Maya mesh shape node.

        Returns:
            SG node name, or ``None`` if not connected.
        """
        try:
            # Fast path: check slot 0.
            plugs: List[str] = (
                cmds.listConnections(
                    f"{shape}.instObjGroups[0]",
                    destination=True,
                    source=False,
                    plugs=False,
                    type="shadingEngine",
                )
                or []
            )
            if plugs:
                return plugs[0]
            # Slow path: walk all instObjGroups slots.
            indices = cmds.getAttr(f"{shape}.instObjGroups", multiIndices=True) or []
            for idx in indices:
                plugs = (
                    cmds.listConnections(
                        f"{shape}.instObjGroups[{idx}]",
                        destination=True,
                        source=False,
                        plugs=False,
                        type="shadingEngine",
                    )
                    or []
                )
                if plugs:
                    return plugs[0]
            return None
        except Exception:
            return None
