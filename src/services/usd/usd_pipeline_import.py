"""
Import-side mixin: import_usd(), layered stage builder, rig controller extraction.

Auto-generated mixin — do not edit directly; edit usd_pipeline.py then re-split.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

# ── Optional Maya imports (same guards as original) ──────────────────────────
try:
    import maya.api.OpenMaya as om  # type: ignore[import-unresolved]
    import maya.cmds as cmds  # type: ignore[import-unresolved]
    import maya.mel as mel  # type: ignore[import-unresolved]

    MAYA_AVAILABLE = True
except ImportError:
    cmds = None  # type: ignore[assignment]
    mel = None  # type: ignore[assignment]
    om = None  # type: ignore[assignment]
    MAYA_AVAILABLE = False

# ── Optional USD imports ──────────────────────────────────────────────────────
try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt  # type: ignore

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

from .usd_pipeline_models import MAYA_AVAILABLE as _MAYA_AVAILABLE_MODEL
from .usd_pipeline_models import USD_AVAILABLE as _USD_AVAILABLE_MODEL
from .usd_pipeline_models import (
    ConversionResult,
    ConversionStatus,
    ExportOptions,
    ExportResult,
    ImportOptions,
    ImportResult,
)


class ImportMixin:
    # ── Attribute stubs (provided by UsdPipeline.__init__) ────────────
    logger: logging.Logger
    _maya_available: bool
    _usd_available: bool
    _mayausd_available: bool
    _progress_callback: Optional[Callable[[str, int], None]]

    def import_usd(self, usd_path: Path, options: Optional[ImportOptions] = None) -> ImportResult:
        """
        Import USD file with smart fallback to .rig.mb
        Args:
            usd_path: Path to .usd/.usdc/.usda/.usdz file
            options: Import options

        Returns:
            ImportResult with details
        """
        result = ImportResult()
        options = options or ImportOptions()

        if not self._maya_available:
            result.error_message = "Maya not available"
            return result

        try:
            self._report_progress("Starting import", 0)

            # Handle USDZ packages
            actual_usd_path = usd_path
            rig_mb_path: Optional[Path] = None
            temp_dir: Optional[Path] = None

            if usd_path.suffix.lower() == ".usdz":
                self._report_progress("Extracting USDZ package", 5)
                actual_usd_path, rig_mb_path, temp_dir = self._extract_usdz(usd_path)

                if not actual_usd_path:
                    result.error_message = "Failed to extract USDZ package"
                    return result

                # Sibling .rig.mb lookup — the .rig.mb is kept separate from
                # the .usdz for online viewer compatibility.  Check for a file
                # named <stem>.rig.mb (or .rig.ma) alongside the source .usdz.
                if rig_mb_path is None:
                    for _ext in (".rig.mb", ".rig.ma"):
                        _sibling = usd_path.parent / (usd_path.stem + _ext)
                        if _sibling.exists():
                            rig_mb_path = _sibling
                            self.logger.info(f"[RIG] Found sibling rig file: {_sibling.name}")
                            break
                    if rig_mb_path is None:
                        self.logger.info(
                            f"[RIG] No .rig.mb found inside USDZ or alongside it.  "
                            f"Place '{usd_path.stem}.rig.mb' next to the .usdz to "
                            f"enable controller and skeleton layer population."
                        )

            # ========== USD PROXY MODE (EXPERIMENTAL) ==========
            # Keep USD as proxy for pipeline integration
            if options.usd_proxy_mode:
                self.logger.info("[USD] USD PROXY MODE ACTIVATED (Experimental)")

                # IMPORT-TIME COLOUR BOOST: the USDC was written by a previous
                # export run and may contain desaturated grey-brown diffuseColors
                # (0.29-0.43 typical for military gear).  Boost them now so VP2
                # shows clearly distinct hues without needing to re-export.
                # This is safe to run on every import — it is idempotent and only
                # touches static (non-texture-connected) diffuseColor inputs.
                self._boost_usd_material_colors(actual_usd_path)

                # Build layered stage: decompose monolithic .usdc into
                # root.usda → animation / controllers / materials / skeleton / geometry / base
                self._report_progress("[LAYER] Building layered USD stage", 10)
                layered_root = self._build_layered_stage(actual_usd_path, rig_mb_path)
                if layered_root:
                    self.logger.info(f"[OK] Proxy will load layered stage: {layered_root.name}")
                    actual_usd_path = layered_root
                else:
                    self.logger.warning(
                        "[WARNING] Layered stage creation failed — "
                        "falling back to monolithic USD"
                    )

                self._report_progress("[USD] Creating USD Proxy Shape", 20)
                usd_success = self._import_with_mayausd(actual_usd_path, options, result)

                if usd_success and result.usd_meshes > 0:
                    result.success = True
                    result.meshes_imported = result.usd_meshes
                    result.joints_imported = result.usd_joints
                    self.logger.info(
                        f"[OK] USD Proxy created: {result.usd_meshes} meshes, "
                        f"{result.usd_joints} joints in USD"
                    )
                    # VP2 uses USD-native UsdPreviewSurface; RenderMan uses Maya PxrSurface
                    # shaders created by _create_rfm_maya_shaders inside _import_with_mayausd.
                    if result.usd_materials > 0:
                        self.logger.info(
                            f"[LOOKDEV] {result.usd_materials} USD materials: "
                            f"VP2 via UsdPreviewSurface · "
                            f"RenderMan via Maya Pxr shaders (PxrDisneyBsdf from .rig.mb cache "
                            f"+ synthetic PxrSurface fallback for any unmatched)"
                        )
                    if options.open_layer_editor:
                        self.logger.info(
                            "[TIP] USD Layer Editor opened — author animation as a non-destructive layer (Option B)"
                        )
                    else:
                        self.logger.info(
                            "[TIP] Animate via USD > Edit As Maya Data (Option A) "
                            "or reopen with 'USD Layer Editor' selected (Option B)"
                        )
                else:
                    result.error_message = "USD proxy creation failed or no content"

                self._report_progress("USD Proxy import complete", 100)
                return result

            # ========== HYBRID WORKFLOW (RECOMMENDED) ==========
            # Routes to the self-contained HybridWorkflow class which uses
            # the correct load order (USD first, .rig.mb with namespace second)
            # to avoid skinCluster-lock failures on SG assignment.
            rig_exists = rig_mb_path.exists() if rig_mb_path else False
            self.logger.info(
                f"[IMPORT] Hybrid check: hybrid_mode={options.hybrid_mode}, "
                f"rig_mb_path={rig_mb_path}, exists={rig_exists}"
            )
            if options.hybrid_mode:
                self.logger.info("[OK] HYBRID MODE ACTIVATED — routing to HybridWorkflow")
                from .workflows.hybrid_workflow import (
                    HybridWorkflow,  # local import avoids circular
                )

                wf = HybridWorkflow()
                wf.set_progress_callback(self._report_progress)
                result.success = wf.run(actual_usd_path, rig_mb_path, options, result)
                return result

            # ========== STANDARD WORKFLOWS ==========
            # Build layered stage for standard proxy import too
            layered_root = self._build_layered_stage(actual_usd_path, rig_mb_path)
            if layered_root:
                actual_usd_path = layered_root

            # Import USD using mayaUSD - creates a proxy shape with USD prims
            self._report_progress("Importing USD via mayaUSD", 20)
            usd_success = self._import_with_mayausd(actual_usd_path, options, result)

            # Check if USD import succeeded (proxy shape with content)
            has_usd_content = usd_success and result.usd_meshes > 0

            if has_usd_content:
                # SUCCESS! USD prims loaded in proxy shape - this is the Disney workflow
                self.logger.info(
                    f"[OK] USD import successful: {result.usd_meshes} mesh prims, "
                    f"{result.usd_joints} skeleton prims in USD proxy shape"
                )
                self.logger.info("[TIP] USD prims are viewable in Maya viewport via proxy shape")
                self.logger.info(
                    "[TIP] To convert to native Maya: Right-click proxy > Duplicate As > Maya Data"
                )

                result.success = True
                self._report_progress("USD import complete", 100)

            elif not usd_success:
                # USD import completely failed - use .rig.mb fallback
                if rig_mb_path and rig_mb_path.exists() and options.use_rig_mb_fallback:
                    self._report_progress("USD import failed - Using .rig.mb fallback", 60)
                    self._import_rig_mb_fallback(rig_mb_path, result)
                    result.success = result.meshes_imported > 0
                else:
                    result.error_message = "USD import failed and no fallback available"
                    return result

            else:
                # USD import returned True but no meshes - try .rig.mb fallback
                if rig_mb_path and rig_mb_path.exists() and options.use_rig_mb_fallback:
                    self._report_progress("No USD meshes found - Using .rig.mb fallback", 60)
                    self._supplement_from_rig_mb(rig_mb_path, options, result)
                    result.success = result.meshes_imported > 0
                else:
                    result.error_message = "USD proxy created but contains no meshes"
                    return result

            self._report_progress("Import complete", 100)

            # IMPORTANT: Do NOT cleanup temp directory if we created a proxy shape!
            # The proxy shape REFERENCES the USD file - deleting it breaks the scene.
            if temp_dir and temp_dir.exists():
                if has_usd_content:
                    # Keep the temp dir - proxy shape needs the USD file
                    self.logger.info(f"[SAVE] USD files preserved in: {temp_dir}")
                    self.logger.info(
                        "[TIP] To make permanent: File > Archive Scene or re-export USDZ"
                    )
                    result.temp_usd_path = actual_usd_path  # Store for reference
                else:
                    # Persistent extract_dir — do not delete; proxy shape may
                    # still reference sublayers inside it.  Log location instead.
                    self.logger.info(f"[SAVE] USD files preserved in: {temp_dir}")

        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            self.logger.error(traceback.format_exc())
            result.error_message = str(e)

        return result

    def _extract_usdz(
        self, usdz_path: Path
    ) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """
        Extract USDZ package to a persistent directory alongside the source file.

        Using a persistent directory (not a system temp dir) means the
        mayaUsdProxyShape filePath remains valid across Maya sessions and
        machine reboots.  The directory is named <stem>_usd/ and sits next
        to the .usdz file so it travels with the project.

        Returns:
            (usd_path, rig_mb_path, extract_dir) or (None, None, None) on failure
        """
        try:
            # Persistent sibling directory — survives Maya restarts
            extract_dir = usdz_path.parent / (usdz_path.stem + "_usd")
            extract_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"[EXTRACT] Extracting USDZ to persistent dir: {extract_dir}")

            # Remove any previously-extracted USD/rig files so we always
            # start from a clean extraction.  Existing .usda sublayers written
            # by _build_layered_stage are kept — they may contain user edits.
            _usd_exts = {".usd", ".usdc", ".mb", ".ma"}
            for old_file in extract_dir.iterdir():
                if old_file.is_file() and old_file.suffix in _usd_exts:
                    try:
                        old_file.unlink()
                    except Exception:
                        pass

            usd_path = None
            rig_mb_path = None

            with zipfile.ZipFile(str(usdz_path), "r") as zf:
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue  # skip directory entries

                    flat_name = Path(name).name

                    if flat_name.endswith((".usd", ".usdc", ".usda")):
                        # USD stage files go to root of extract_dir so that
                        # relative paths inside the USDC (e.g. @textures/foo.png@)
                        # resolve correctly against extract_dir as the base.
                        dest = extract_dir / flat_name
                        with zf.open(name) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        usd_path = dest
                        self.logger.info(f"[FILE] Extracted USD: {flat_name}")
                    elif flat_name.endswith((".rig.mb", ".rig.ma")):
                        dest = extract_dir / flat_name
                        with zf.open(name) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        rig_mb_path = dest
                        self.logger.info(f"[PACKAGE] Extracted rig backup: {flat_name}")
                    else:
                        # ALL other files (textures, etc.) — preserve the
                        # relative ZIP path so that USDC-internal references
                        # like @./textures/Chain_Base_color.png@ resolve correctly.
                        dest = extract_dir / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, open(dest, "wb") as dst:
                            dst.write(src.read())

            # Count extracted textures for diagnostics
            tex_count = sum(
                1
                for f in extract_dir.rglob("*")
                if f.is_file()
                and f.suffix.lower()
                in {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".tx", ".tex"}
            )
            if tex_count:
                self.logger.info(f"[EXTRACT] {tex_count} texture file(s) extracted")

            return usd_path, rig_mb_path, extract_dir

        except Exception as e:
            self.logger.error(f"USDZ extraction failed: {e}")
            return None, None, None

    def _import_with_mayausd(
        self, usd_path: Path, options: ImportOptions, result: ImportResult
    ) -> bool:
        """
        Import USD by creating a mayaUsdProxyShape that loads the USD natively.

        This is the Disney/Pixar workflow - USD prims are displayed through
        the proxy shape, NOT converted to native Maya meshes.
        """
        if not self._mayausd_available:
            self.logger.error("mayaUSD plugin not available")
            return False

        try:
            # First, let's inspect the USD to see what's in it
            mesh_count = 0
            skel_count = 0
            curve_count = 0
            material_count = 0
            has_skeleton_bindings = False

            joint_count = 0

            if USD_AVAILABLE:
                try:
                    stage = Usd.Stage.Open(str(usd_path))
                    if stage:
                        # Find the default prim or root
                        default_prim = stage.GetDefaultPrim()
                        default_path = default_prim.GetPath() if default_prim else None
                        self.logger.info(f"[FILE] USD default prim: {default_path}")

                        # Count prims
                        for prim in stage.Traverse():
                            prim_type = prim.GetTypeName()
                            if prim_type == "Mesh":
                                mesh_count += 1
                                # Check if mesh has skeleton binding
                                if prim.HasAPI(UsdSkel.BindingAPI):
                                    has_skeleton_bindings = True
                            elif prim_type == "Skeleton":
                                skel_count += 1
                                # Sum actual joints defined in this Skeleton
                                joints_attr = UsdSkel.Skeleton(prim).GetJointsAttr().Get()
                                if joints_attr:
                                    joint_count += len(joints_attr)
                            elif prim_type in ("NurbsCurves", "BasisCurves"):
                                curve_count += 1
                            elif prim_type == "Material":
                                material_count += 1

                        self.logger.info(
                            f"[INFO] USD contains: {mesh_count} meshes, {skel_count} skeleton rig(s) "
                            f"({joint_count} joints), {curve_count} curves, {material_count} materials"
                        )
                        if has_skeleton_bindings:
                            self.logger.info("[INFO] USD has skeleton-bound meshes (skinned)")
                except Exception as e:
                    self.logger.warning(f"Could not inspect USD: {e}")

            if cmds is None:
                self.logger.error("Maya cmds not available")
                return False

            # Create a USD proxy shape that loads the USD file natively
            # This is the proper Disney/Pixar workflow - USD prims displayed through proxy
            self.logger.info("[ANIMATION] Creating USD Stage (mayaUsdProxyShape)...")

            try:
                # Tell VP2 to resolve UsdPreviewSurface materials via the shader registry
                # BEFORE the stage loads.  The proxy shape consults this optionVar at load
                # time (when filePath is set), so it must be in place first.
                # Maya confirms success with: "# Using V3 Lighting API for UsdPreviewSurface shading."
                try:
                    cmds.optionVar(stringValue=("mayaUsd_ShadingModeImport", "useRegistry"))
                    self.logger.info(
                        "[SHADING] mayaUsd_ShadingModeImport=useRegistry — VP2 will use V3 Lighting API"
                    )
                except Exception:
                    pass

                # Sanitize the stem: Maya node names must not contain dots.
                # e.g. "Veteran_Rig.root" → "Veteran_Rig_root"
                node_base = usd_path.stem.replace(".", "_")

                # Create the proxy shape
                proxy_transform = cmds.createNode("transform", name=node_base + "_USD")
                proxy_shape = cmds.createNode(
                    "mayaUsdProxyShape", parent=proxy_transform, name=node_base + "_USDShape"
                )

                # Loading the file path triggers USD stage composition.
                # Maya will print "# Using V3 Lighting API for UsdPreviewSurface shading."
                # confirming the optionVar above was respected.
                # NOTE: Always use forward slashes — pathlib.Path on Windows gives
                # backslashes, but PxrUSD procedural and Sdf expect POSIX separators.
                usd_path_fwd = str(usd_path).replace("\\", "/")
                cmds.setAttr(f"{proxy_shape}.filePath", usd_path_fwd, type="string")

                # ── CRITICAL for RfM 27.2 rendering ───────────────────────────
                # primPath tells rfm2's translator which USD prim to use as the
                # root object for the PxrUSD procedural.
                # When primPath is empty (the default), rfm2 outputs:
                #   Procedural2 "DynamicLoad" "PxrUSD" "string object" [""]
                # PxrUSD interprets an empty object as the pseudo-root — which
                # has no geometry — so nothing renders in IPR or IT.
                # Setting it to '/' causes rfm2 to output:
                #   Procedural2 "DynamicLoad" "PxrUSD" "string object" ["/"]
                # PxrUSD then traverses the full USD hierarchy, finds /SkelRoot
                # and all its children (meshes, skeleton, materials) and renders
                # them correctly.
                cmds.setAttr(f"{proxy_shape}.primPath", "/", type="string")

                # Enable proxy drawing
                cmds.setAttr(f"{proxy_shape}.loadPayloads", True)

                # IMPORTANT: For skinned meshes, set draw modes.
                # drawDefaultPurpose = True is critical: character mesh prims are
                # authored with "default" USD purpose (no explicit purpose opinion),
                # so they must be included in both VP2 and the RenderMan USD procedural.
                try:
                    cmds.setAttr(f"{proxy_shape}.drawProxyPurpose", True)
                    cmds.setAttr(f"{proxy_shape}.drawRenderPurpose", True)
                    cmds.setAttr(f"{proxy_shape}.drawGuidePurpose", False)
                except Exception:
                    pass  # Attribute may not exist in all Maya versions
                try:
                    cmds.setAttr(f"{proxy_shape}.drawDefaultPurpose", True)
                except Exception:
                    pass

                # Explicitly set render visibility on the SHAPE — these attrs
                # live on shape nodes, not transforms.  Without them the PxrUSD
                # procedural may skip the proxy in the RIB export.
                try:
                    cmds.setAttr(f"{proxy_shape}.primaryVisibility", True)
                    cmds.setAttr(f"{proxy_shape}.castsShadows", True)
                    cmds.setAttr(f"{proxy_shape}.receiveShadows", True)
                except Exception:
                    pass

                # NOTE: The blank-filePath force-reload was REMOVED.
                # Setting filePath to "" triggered rfm2's MDGMessage::kAttributeSet
                # callback with an empty path, which caused rfm2 to unregister
                # the shape from its internal render scene.  Restoring the path
                # afterward was insufficient — rfm2 had already removed the shape.
                # The USD stage composes correctly on the first setAttr filePath
                # call; no reload is needed.  The primPath='/' set above ensures
                # rfm2 renders the full hierarchy.  A dgdirty below handles any
                # deferred DG evaluation that needs to pick up these attributes.
                cmds.refresh()
                self.logger.info(
                    "[USD] Stage loaded via mayaUsdProxyShape (primPath='/'; full hierarchy rendered)"
                )

                # ── RfM 27.2: Optional rmanAddAttr registration ──────────────────
                # rmanAddAttr was a legacy rfm1 MEL command (pre-RfM 24). In
                # rfm2 (RfM 24+ / 27.2) it no longer exists — rfm2 auto-discovers
                # all Maya shape nodes (including mayaUsdProxyShape) via its
                # registered translator plugins. Calling it in RfM 27.2 causes a
                # "Cannot find procedure" MEL error even though that error is
                # harmless. Guard with whatIs so the error never prints.
                try:
                    if mel is not None:
                        _proc_exists = mel.eval('whatIs "rmanAddAttr"') not in ("Unknown", "")
                        if _proc_exists:
                            # rfm1-style session (very old RfM) — call legacy proc
                            prev_sel = cmds.ls(selection=True) or []
                            cmds.select(proxy_shape, replace=True)
                            mel.eval("rmanAddAttr")
                            if prev_sel:
                                cmds.select(prev_sel, replace=True)
                            else:
                                cmds.select(clear=True)
                            self.logger.info(
                                "[RFM] rmanAddAttr — proxy shape registered with RenderMan translator"
                            )
                        else:
                            # rfm2 27.2: translator auto-discovers mayaUsdProxyShape —
                            # visibility/shading set above is all that's required.
                            self.logger.info(
                                "[RFM] rfm2 27.2 — proxy shape auto-discovered by translator "
                                "(rmanAddAttr is rfm1-only; not needed in RfM 24+)"
                            )
                except Exception:
                    pass

                # Dirty the DG so rfm2's scene graph callbacks re-fire with the
                # correct filePath.  This recovers registration that was lost
                # during the blank-path force-reload step above.
                try:
                    cmds.dgdirty(proxy_shape, allPlugs=True)
                except Exception:
                    pass

                self.logger.info(f"[OK] Created USD proxy shape: {proxy_shape}")
                self.logger.info(f"[FILE] Loading USD file: {usd_path}")

                # Select and frame the proxy transform for visibility
                try:
                    cmds.select(proxy_transform, replace=True)
                    cmds.viewFit(allObjects=False)  # Frame selection in viewport
                    self.logger.info("[CAMERA] Selected and framed USD proxy in viewport")
                except Exception as frame_err:
                    self.logger.warning(f"[WARNING] Could not frame proxy: {frame_err}")

                # Ensure VP2.0 is active for USD display with materials.
                # getPanel(withFocus=True) returns the dialog when the asset manager
                # UI has focus — fall back to all model panels so material display
                # is always configured regardless of which window is focused.
                try:
                    focused = cmds.getPanel(withFocus=True)
                    if focused and "modelPanel" in focused:
                        panels_to_configure = [focused]
                    else:
                        panels_to_configure = cmds.getPanel(type="modelPanel") or []

                    configured = 0
                    for panel in panels_to_configure:
                        try:
                            # Switch to VP2.0 if the panel is using an unknown
                            # renderer.  PRESERVE RenderMan's viewport renderer
                            # ('renderManForMaya') if the user has it active —
                            # overriding it with VP2 would break RenderMan viewport
                            # rendering.  Both VP2 and RenderMan VP2 can display
                            # the USD proxy shape with materials.
                            renderer = cmds.modelEditor(panel, query=True, rendererName=True)
                            _rman_vp = {"renderManForMaya", "myRenderView", "renderManXPU"}
                            if renderer not in _rman_vp and renderer != "vp2Renderer":
                                cmds.modelEditor(panel, edit=True, rendererName="vp2Renderer")

                            # Enable shaded+material display.
                            # useDefaultMaterial=False is the critical flag —
                            # without it VP2 shows solid white ("default material") on
                            # USD proxy shapes even when UsdPreviewSurface shaders exist.
                            cmds.modelEditor(
                                panel,
                                edit=True,
                                displayTextures=True,
                                displayAppearance="smoothShaded",
                                displayLights="default",
                                useDefaultMaterial=False,
                            )
                            configured += 1
                        except Exception:
                            pass  # Skip any panel that doesn't support these flags

                    if configured:
                        self.logger.info(
                            f"[LOOKDEV] Enabled material display in {configured} viewport(s) "
                            f"(VP2, smoothShaded, useDefaultMaterial=False)"
                        )
                    else:
                        self.logger.warning(
                            "[WARNING] Could not configure any model panel for material display"
                        )

                    cmds.refresh(force=True)
                except Exception as vp_err:
                    self.logger.warning(f"[WARNING] Could not configure viewport: {vp_err}")

                # Convert USD Skeleton to Maya Joints if requested
                if options.convert_skeleton_to_maya:
                    self._convert_usd_skeleton_to_maya(proxy_shape, usd_path)
                else:
                    self.logger.info(
                        "[SKEL] Skeleton managed by UsdSkelImaging inside proxy shape "
                        "(set convert_skeleton_to_maya=True to extract as Maya joints)"
                    )

                # ── RfM 27.2 render integration ──────────────────────────────
                # Force rfm2 to re-scan the scene and include the USD proxy in
                # the next IPR / batch render via the PxrUSD procedural.
                #
                # rfm2 (RfM 24+) architecture notes:
                #   - rfmUpdateUI was removed; rfm2 uses DG callbacks instead
                #   - rfm2.api.RfM().refresh() only refreshes UI state, not renders
                #   - The correct approach: dirty the specific plugs rfm2 watches,
                #     then use rfm2.scene_updater to trigger a full scene rebuild.
                try:
                    import maya.mel as mel_m

                    if mel_m.eval('whatIs "rfmUpdateUI"') not in ("Unknown", ""):
                        # rfm1-style session (very old RfM) — use legacy command
                        mel_m.eval("rfmUpdateUI")
                    else:
                        # rfm2 (RfM 24+ / 27.2) — DG dirty is the correct trigger.
                        # Mark the transform and shape dirty so rfm2's registered
                        # MDGMessage::kAttributeChanged callbacks re-process them.
                        cmds.dgdirty(proxy_transform, allPlugs=True)
                        cmds.dgdirty(proxy_shape, allPlugs=True)
                        # Also attempt the rfm2.scene_updater path if importable.
                        # scene_updater is the module that fired update_lama_nodes,
                        # update_disney_nodes etc. — its update_rman_globals resets
                        # the global render state which causes a full scene re-scan.
                        try:
                            import rfm2.scene_updater as rfm2_su

                            rfm2_su.update_rman_globals({})
                        except Exception:
                            pass  # rfm2 not installed or wrong signature — DG dirty above is sufficient
                    self.logger.info(
                        "[RFM] Scene graph refreshed \u2014 USD proxy registered "
                        "for RenderMan IPR and XPU rendering"
                    )
                except Exception:
                    pass  # RfM not loaded \u2014 harmless

            except Exception as proxy_err:
                self.logger.error(f"mayaUsdProxyShape creation failed: {proxy_err}")
                return False

            # Check for proxy shapes
            proxy_shapes = cmds.ls(type="mayaUsdProxyShape") or []
            if proxy_shapes:
                self.logger.info(f"[PACKAGE] USD proxy shape(s) created: {len(proxy_shapes)}")

                # Count USD prims inside the proxy shape(s)
                self._count_usd_prims_in_proxy(proxy_shapes, result)

                # Mark as successful USD import
                result.usd_meshes = mesh_count if mesh_count > 0 else result.usd_meshes
                # Use real joint count; skel_count is kept for threshold checks below
                result.usd_joints = joint_count if joint_count > 0 else skel_count
                result.usd_curves = curve_count if curve_count > 0 else result.usd_curves
                result.usd_materials = (
                    material_count if material_count > 0 else result.usd_materials
                )

                # For display, these ARE our imported counts (USD prims = content)
                result.meshes_imported = result.usd_meshes
                result.joints_imported = result.usd_joints
                result.curves_imported = result.usd_curves
                result.materials_imported = result.usd_materials

                self.logger.info(
                    f"[OK] USD Stage loaded - {result.usd_meshes} meshes, "
                    f"{skel_count} skeleton rig(s) / {result.usd_joints} joints, "
                    f"{result.usd_curves} curves, {result.usd_materials} materials"
                )

                # Info about USD workflow
                if has_skeleton_bindings and skel_count > 10:
                    self.logger.info(
                        "[INFO] Complex skeleton detected - USD proxy will display skinned meshes via UsdSkelImaging"
                    )

                # ── Create Maya PxrSurface shaders (Hypershade + rfm2 RIS) ────────────
                # Creates real Maya DG PxrSurface + PxrTexture nodes visible in
                # Hypershade and rendered by rfm2's standard RIS translation path.
                # This runs AFTER the stage is loaded so the proxy shape already
                # exists and mesh→material bindings are resolvable from the stage.
                if USD_AVAILABLE and result.usd_materials > 0:
                    self._create_rfm_maya_shaders(usd_path, proxy_transform, proxy_shape)

                    # ── RENDER-READY NATIVE IMPORT (FROZEN — opt-in only) ────
                    # Architecture seam: MayaUSD 0.35.0 / RfM 27.2 has no
                    # working per-mesh path for `mayaUsdProxyShape`.  The
                    # native-import workaround collides with already-loaded
                    # .rig.mb shape names (mayaUSDImport renames to
                    # `*_usdExport`) and the rig's skinned shapes reject SG
                    # reassignment ("Source node will not allow the
                    # connection").  Disabled by default — the Animation
                    # Importer stays in USD-proxy mode for layout/anim;
                    # rendering is owned by the Hybrid Importer Workflow.
                    if getattr(options, "render_ready_native_import", False):
                        mb = getattr(self, "_last_mesh_bindings", None) or {}
                        m2sg = getattr(self, "_last_mat_path_to_sg", None) or {}
                        rr_count = self._render_ready_native_import(
                            usd_path, proxy_transform, mb, m2sg
                        )
                        if rr_count > 0 and getattr(
                            options, "hide_proxy_after_render_ready", False
                        ):
                            try:
                                cmds.setAttr(f"{proxy_transform}.visibility", False)
                                self.logger.info(
                                    f"[RR] Hid USD proxy '{proxy_transform}' — "
                                    f"renderer will use {rr_count} native mesh(es) "
                                    f"with original RfM SGs.  Re-show the proxy "
                                    f"any time for live USD animation/layout."
                                )
                            except Exception as hide_err:
                                self.logger.debug(f"[RR] Could not hide proxy: {hide_err}")

                # Open USD Layer Editor if requested (Option B animation authoring)
                if options.open_layer_editor:
                    self._open_usd_layer_editor(proxy_shape)

                return True
            else:
                self.logger.warning("[ERROR] No USD proxy shapes found after import")
                return False

        except Exception as e:
            self.logger.error(f"USD import failed: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def _open_usd_layer_editor(self, proxy_shape: str) -> None:
        """
        Open the mayaUSD Layer Editor and create an editable animation sublayer.

        This is Option B — author animation non-destructively as a USD layer
        on top of the stage rather than converting prims to Maya joints.
        """
        try:
            # Select the proxy transform so the Layer Editor shows its stage
            if cmds is not None:
                parents = cmds.listRelatives(proxy_shape, parent=True) or []
                if parents:
                    cmds.select(parents[0], replace=True)

            # Create an anonymous edit sublayer BEFORE opening the editor
            # so the user sees a writable layer immediately
            self._create_animation_edit_layer(proxy_shape)

            # Open the mayaUSD Layer Editor
            try:
                mel.eval("mayaUsdLayerEditorWindow")
                self.logger.info(
                    "[LAYER] Opened mayaUSD Layer Editor — author animation as USD layers (Option B)"
                )
                return
            except Exception:
                pass

            # Fall back to Maya's built-in Animation Layer Editor
            try:
                mel.eval("LayerEditorWindow")
                self.logger.info("[LAYER] Opened Animation Layer Editor (fallback)")
            except Exception as fallback_err:
                self.logger.warning(f"[WARNING] Could not open Layer Editor: {fallback_err}")

        except Exception as e:
            self.logger.warning(f"[WARNING] _open_usd_layer_editor failed: {e}")

    def _create_animation_edit_layer(self, proxy_shape: str) -> None:
        """
        Set the animation sublayer as the edit target on the proxy's live stage.

        The layered stage already contains editorial sublayers (animation, materials,
        skeleton, geometry) built by _build_layered_stage.  This method finds the
        animation layer and makes it the active edit target so keyframes land there.
        """
        if cmds is None:
            return

        try:
            # ── Get the live stage from the proxy shape ──
            stage = None

            try:
                import mayaUsd.ufe as mayaUsdUfe  # type: ignore[import-unresolved]

                try:
                    stage = mayaUsdUfe.getStage(proxy_shape)
                except RuntimeError:
                    proxy_long = (cmds.ls(proxy_shape, long=True) or [proxy_shape])[0]
                    stage = mayaUsdUfe.getStage(proxy_long)
            except (ImportError, RuntimeError) as e:
                self.logger.debug(f"[LAYER] mayaUsd.ufe.getStage unavailable: {e}")

            if stage is None:
                file_path = cmds.getAttr(f"{proxy_shape}.filePath")
                if file_path:
                    stage = Usd.Stage.Open(file_path)

            if stage is None:
                self.logger.warning(
                    "[LAYER] Could not access proxy stage — "
                    "select the animation sublayer manually in the Layer Editor"
                )
                return

            # ── Find the animation sublayer and set it as edit target ──
            root_layer = stage.GetRootLayer()
            for sublayer_path in root_layer.subLayerPaths:
                if "animation" in sublayer_path.lower():
                    anim_layer = Sdf.Layer.FindOrOpen(
                        root_layer.ComputeAbsolutePath(sublayer_path)
                    )
                    if anim_layer:
                        stage.SetEditTarget(Usd.EditTarget(anim_layer))
                        self.logger.info(
                            "[LAYER] Edit target set to 'animation' sublayer — "
                            "keyframes will be authored here"
                        )
                        self.logger.info(
                            "[TIP] Select USD prims in viewport → "
                            "press S to set keyframes on the animation layer"
                        )
                        return

            self.logger.warning(
                "[LAYER] animation sublayer not found — "
                "select an edit layer manually in the Layer Editor"
            )

        except Exception as e:
            self.logger.warning(f"[LAYER] Could not set animation edit target: {e}")
            self.logger.warning(
                "[TIP] In the Layer Editor, click the animation sublayer to make it the edit target"
            )

    # ─── Layered USD Stage Builder ───────────────────────────────────────

    def _boost_usd_material_colors(self, usd_path: Path) -> None:
        """Boost desaturated diffuseColors in a USD file for VP2 material identification.

        Pass 1 — UsdPreviewSurface diffuseColor:
            For every static (non-texture-connected) diffuseColor:
            - If the colour has a detectable hue, boosts S/V so per-material
              differences are clearly visible in VP2.
            - If achromatic, replaces with a deterministic name-hash hue so
              each material still gets a unique distinct colour.
            Bug fixed: mat_name now uses the Material prim's OWN name
            (prim.GetParent().GetName()), not its grandparent scope name.
            Previously GetParent().GetParent().GetName() returned "Looks"
            for every material, making all 20 achromatic materials hash to
            the same single colour.

        Pass 2 — primvars:displayColor on every Mesh prim:
            Follows each mesh's material:binding and writes
            primvars:displayColor to the same boosted colour.
            VP2 reads displayColor directly from geometry even when
            UsdSkelImaging is active and bypasses the full
            material:binding → UsdPreviewSurface resolution chain,
            which is the case for all skinned meshes.  Without this pass
            VP2 renders skinned meshes as flat grey regardless of what
            the UsdPreviewSurface diffuseColor is set to.
        """
        if not USD_AVAILABLE:
            return
        try:
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.debug("[BOOST] Could not open USD for colour boost")
                return

            boosted = 0
            hashed = 0
            skipped = 0
            # Maps Material Sdf.Path → final display colour (None = texture-driven)
            mat_path_to_color: dict = {}

            # ── Pass 1: boost UsdPreviewSurface diffuseColor ─────────────────
            for prim in stage.Traverse():
                if prim.GetTypeName() != "Shader":
                    continue
                shader = UsdShade.Shader(prim)
                if not shader or shader.GetShaderId() != "UsdPreviewSurface":
                    continue

                dc_input = shader.GetInput("diffuseColor")
                if not dc_input:
                    continue

                # The Material prim is the direct parent of the PreviewSurface shader.
                # Its name (e.g. "Veteran_Body_mat") is what we hash for name-colours.
                mat_prim = prim.GetParent()
                mat_path = mat_prim.GetPath() if mat_prim else None
                mat_name = mat_prim.GetName() if mat_prim else "Unknown"

                # Skip texture-driven inputs — never overwrite upstream connections.
                if dc_input.HasConnectedSource():
                    skipped += 1
                    if mat_path:
                        mat_path_to_color[mat_path] = None  # texture-driven
                    continue

                current = dc_input.Get()
                if current is None:
                    continue

                raw = Gf.Vec3f(float(current[0]), float(current[1]), float(current[2]))
                boosted_color = self._boost_color_for_display(raw)

                if boosted_color is not None:
                    dc_input.Set(boosted_color)
                    boosted += 1
                    final_color = boosted_color
                    self.logger.debug(
                        f"   [BOOST] {mat_name}: "
                        f"({raw[0]:.3f}, {raw[1]:.3f}, {raw[2]:.3f}) → {boosted_color}"
                    )
                else:
                    # Achromatic — each material gets a unique deterministic hue
                    hash_color = self._rfm_name_color(mat_name)
                    dc_input.Set(hash_color)
                    hashed += 1
                    final_color = hash_color
                    self.logger.debug(
                        f"   [BOOST] {mat_name}: achromatic → name-hash {hash_color}"
                    )

                if mat_path:
                    mat_path_to_color[mat_path] = final_color

            # ── Pass 2: primvars:displayColor on every Mesh prim ─────────────
            # VP2's UsdSkelImaging adapter renders skinned meshes but does NOT
            # always follow material:binding → UsdPreviewSurface.  Setting
            # primvars:displayColor directly on the geometry guarantees VP2
            # shows distinct colours regardless of the material system path.
            #
            # Use ComputeBoundMaterial() — the proper USD composition-aware
            # API that resolves inherited bindings, collection bindings, and
            # purpose-specific bindings.  GetDirectBinding() only returns
            # bindings authored directly on the prim itself, and returns an
            # always-truthy object even when no binding exists, making the
            # previous ancestor-walk logic unreliable.
            #
            # Fallback guarantee: every mesh gets a displayColor — either the
            # boosted material colour or a name-hash of the mesh's own name.
            # This ensures no mesh is invisible-grey even if binding fails.
            display_colored = 0
            _first_disp_err: Optional[str] = None
            for prim in stage.Traverse():
                if prim.GetTypeName() != "Mesh":
                    continue
                try:
                    color = None

                    # ── Primary: direct material:binding relationship ──────────
                    # More reliable than ComputeBoundMaterial across USD versions
                    # because it avoids USD 22.x/23.x/24.x API signature changes.
                    binding_rel = prim.GetRelationship("material:binding")
                    if binding_rel and binding_rel.HasAuthoredTargets():
                        targets = binding_rel.GetForwardedTargets()
                        if targets:
                            mat_prim = stage.GetPrimAtPath(targets[0])
                            if mat_prim and mat_prim.IsValid():
                                color = mat_path_to_color.get(mat_prim.GetPath())
                                if color is None:
                                    # Texture-driven sentinel or unknown — name-hash
                                    color = self._rfm_name_color(mat_prim.GetName())

                    # ── Secondary: ComputeBoundMaterial (inherited/collection) ─
                    if color is None:
                        try:
                            _cm_result = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
                            # Handle both tuple return (USD 22+) and bare object
                            bound_mat = (
                                _cm_result[0]
                                if isinstance(_cm_result, (tuple, list))
                                else _cm_result
                            )
                            if bound_mat and bound_mat.GetPrim().IsValid():
                                color = mat_path_to_color.get(bound_mat.GetPrim().GetPath())
                                if color is None:
                                    color = self._rfm_name_color(bound_mat.GetPrim().GetName())
                        except Exception:
                            pass

                    # ── Final fallback: name-hash the mesh itself ─────────────
                    if color is None:
                        color = self._rfm_name_color(prim.GetName())

                    r = float(color[0])
                    g = float(color[1])
                    b = float(color[2])
                    UsdGeom.Gprim(prim).CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(r, g, b)]))
                    display_colored += 1
                except Exception as _disp_err:
                    if _first_disp_err is None:
                        _first_disp_err = f"{prim.GetPath()}: {_disp_err}"
                    continue

            if _first_disp_err:
                self.logger.warning(f"[BOOST] displayColor: first mesh error — {_first_disp_err}")

            if boosted + hashed > 0:
                stage.GetRootLayer().Save()
                self.logger.info(
                    f"[BOOST] Colour boost applied: "
                    f"{boosted} hue-boosted, {hashed} name-hashed, "
                    f"{skipped} texture-skipped | "
                    f"{display_colored} mesh primvars:displayColor set"
                )
            else:
                self.logger.debug("[BOOST] No static diffuseColors found to boost")

        except Exception as e:
            self.logger.warning(f"[BOOST] Colour boost failed: {e}")

    def _build_layered_stage(
        self, base_usd_path: Path, rig_mb_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Build a layered USD stage from a monolithic .usdc file.

        If a .rig.mb path is provided, its NURBS controllers and
        controller→joint mappings are extracted and written into
        a controllers sublayer, giving users visual animation guides
        inside the USD stage.

        Creates a root .usda whose sublayer stack looks like:

            root.usda  (this file — loaded by the proxy shape)
              ├── animation.usda      ← empty, editable: keyframes
              ├── controllers.usda    ← NURBS curves from .rig.mb (guide)
              ├── materials.usda      ← empty, editable: shader overrides
              ├── skeleton.usda       ← joint→controller metadata
              ├── geometry.usda       ← empty, editable: geo overrides
              └── <base>.usdc         ← original monolithic data (read-only)

        Returns:
            Path to root .usda on success, None on failure.
        """
        try:
            base_dir = base_usd_path.parent
            asset_name = base_usd_path.stem  # e.g. "Veteran_Rig"

            self.logger.info("[LAYER] Building layered USD stage from base asset...")

            # ── Extract rig data from .rig.mb if available ──
            rig_data = None
            if rig_mb_path and rig_mb_path.exists():
                self.logger.info(f"[LAYER] Extracting controller data from: {rig_mb_path.name}")
                rig_data = self._extract_rig_controllers(rig_mb_path)

            # ── Create editorial sublayers ──
            # Controllers layer is only created when we have rig data
            layer_names = ["animation", "controllers", "materials", "skeleton", "geometry"]
            created_layers: list[Path] = []

            for name in layer_names:
                layer_path = base_dir / f"{asset_name}.{name}.usda"
                # Re-import safe: Sdf.Layer.CreateNew fails if file exists.
                # Two cases:
                #   a) Layer is in the Sdf registry cache from a previous import
                #      in this Maya session — call Clear() to wipe stale specs so
                #      we don't accumulate conflicting PxrPreviewSurface definitions
                #      from old runs.  The layer object (and its cache entry) is
                #      preserved so any USD stages already holding a reference to it
                #      continue to work.
                #   b) Layer file exists on disk but is not in the cache — delete
                #      the file and call CreateNew to start fresh.
                layer = Sdf.Layer.Find(str(layer_path))
                if layer is not None:
                    layer.Clear()  # wipe stale content; keep cache entry intact
                else:
                    if layer_path.exists():
                        try:
                            layer_path.unlink()
                        except Exception:
                            pass
                    layer = Sdf.Layer.CreateNew(str(layer_path))
                if layer is None:
                    self.logger.warning(f"[LAYER] Could not create {name} sublayer")
                    continue

                sub_stage = Usd.Stage.Open(layer)
                UsdGeom.SetStageUpAxis(sub_stage, UsdGeom.Tokens.y)
                layer.documentation = (
                    f"USD {name.title()} Override Layer — {asset_name}\n"
                    f"Author {name} edits here. Opinions in this layer "
                    f"override the base asset."
                )

                # Populate controllers sublayer from .rig.mb data
                if name == "controllers" and rig_data:
                    self._populate_controllers_sublayer(sub_stage, rig_data)

                # Populate skeleton sublayer with controller→joint metadata
                if name == "skeleton" and rig_data:
                    self._populate_skeleton_metadata(sub_stage, base_usd_path, rig_data)

                # Populate materials sublayer with RenderMan ri:surface networks
                # so the USD proxy is renderable in RenderMan for Maya 27.2+ IPR
                # and batch renders in addition to VP2 UsdPreviewSurface display.
                if name == "materials":
                    self._populate_rfm_materials_sublayer(sub_stage, base_usd_path)

                # Populate geometry sublayer with primvar index fixes.
                # The source .usdc sometimes contains mesh primvars whose index
                # arrays reference slots beyond the values array length.  MayaUSD
                # emits "Invalid primvar indices" warnings for each such mesh.
                # Writing clamped-index opinions here (stronger sublayer) silences
                # those warnings completely without touching the source asset.
                if name == "geometry":
                    self._populate_geometry_primvar_fixes(sub_stage, base_usd_path)

                sub_stage.Save()
                created_layers.append(layer_path)
                self.logger.info(f"   [LAYER] {layer_path.name}")

            # ── Create root .usda that composes everything ──
            root_path = base_dir / f"{asset_name}.root.usda"
            root_layer = Sdf.Layer.Find(str(root_path))
            if root_layer is None:
                if root_path.exists():
                    try:
                        root_path.unlink()
                    except Exception:
                        pass
                root_layer = Sdf.Layer.CreateNew(str(root_path))
            if root_layer is None:
                self.logger.error("[LAYER] Could not create root layer")
                return None

            root_stage = Usd.Stage.Open(root_layer)
            UsdGeom.SetStageUpAxis(root_stage, UsdGeom.Tokens.y)

            # Read the default prim from the base stage so the root inherits it.
            # IMPORTANT: use OverridePrim (or just set defaultPrim metadata) — never
            # DefinePrim with a type here.  A "def Xform" opinion in root.usda would
            # override the base USDC's "SkelRoot" type in stronger-wins composition,
            # breaking UsdSkelImaging and hiding all material colours in VP2.
            base_stage = Usd.Stage.Open(str(base_usd_path))
            default_prim = base_stage.GetDefaultPrim() if base_stage else None
            default_prim_name = default_prim.GetName() if default_prim else asset_name

            # Set the defaultPrim metadata on the layer only — no prim spec,
            # no type opinion.  The actual prim definition (SkelRoot / Xform /
            # whatever the rig uses) stays exclusively in the base USDC sublayer.
            root_layer.defaultPrim = default_prim_name

            # ── Build sublayer stack (strongest on top) ──
            for layer_path in created_layers:
                root_layer.subLayerPaths.append(f"./{layer_path.name}")

            # Base monolithic file is the weakest (bottom) sublayer
            root_layer.subLayerPaths.append(f"./{base_usd_path.name}")

            has_controllers = rig_data is not None
            ctrl_line = (
                "  controllers.usda  — NURBS controllers from .rig.mb\n"
                if has_controllers
                else "  controllers.usda  — empty (no .rig.mb available)\n"
            )
            root_layer.documentation = (
                f"USD Layered Rig: {asset_name}\n"
                f"Generated by Asset Manager USD Pipeline\n\n"
                f"Sublayer stack (strongest → weakest):\n"
                f"  animation.usda    — keyframes & motion\n"
                f"{ctrl_line}"
                f"  materials.usda    — shader overrides\n"
                f"  skeleton.usda     — skeleton edits & controller mappings\n"
                f"  geometry.usda     — geo overrides\n"
                f"  {base_usd_path.name}  — base asset (read-only)\n\n"
                f"Edit the sublayer you need; the base asset is never modified."
            )

            root_stage.Save()

            total_sublayers = len(created_layers) + 1  # editorial + base
            ctrl_msg = ""
            if rig_data:
                ctrl_count = len(rig_data.get("controllers", []))
                mapping_count = len(rig_data.get("mappings", {}))
                ctrl_msg = (
                    f" ({ctrl_count} controllers, " f"{mapping_count} joint mappings from .rig.mb)"
                )
            self.logger.info(
                f"[OK] Layered stage: {root_path.name} → " f"{total_sublayers} sublayers{ctrl_msg}"
            )

            return root_path

        except Exception as e:
            self.logger.error(f"[LAYER] Failed to build layered stage: {e}")
            self.logger.error(traceback.format_exc())
            return None

    # ─── .rig.mb Controller Extraction ────────────────────────────────────

    def _extract_rig_controllers(self, rig_mb_path: Path) -> Optional[dict]:
        """
        Temporarily reference .rig.mb and extract NURBS controller data.

        Returns a dict:
            {
                "controllers": [
                    {
                        "name": "L_Arm_CTRL",
                        "cvs": [(x,y,z), ...],
                        "degree": 3,
                        "form": 0,           # 0=open, 1=closed, 2=periodic
                        "knots": [0.0, ...],
                        "translate": (tx, ty, tz),
                        "rotate": (rx, ry, rz),
                        "color": (r, g, b) or None,
                    },
                    ...
                ],
                "mappings": {
                    "L_Arm_CTRL": ["L_Arm_JNT"],  # controller → driven joints
                    ...
                },
                "joint_names": ["Root", "Spine1", ...],  # all joint names
            }
        """
        if cmds is None:
            return None

        try:
            # ── Reference the .rig.mb temporarily ──
            namespace = "_rigExtract_"

            # ── RfM 27.1→27.2 compatibility note ─────────────────────────────
            # The .rig.mb was saved with RenderMan for Maya 27.1 which stored an
            # 'atlasStyle' attribute on PxrTexture/PxrNormalMap nodes.  RfM 27.2
            # removed this attribute.  Maya's C++ file parser emits one
            # "setAttr: No object matches name: .atlasStyle" error per node
            # during the reference load.  These are emitted at the C++ I/O layer
            # and cannot be suppressed by scriptEditorInfo — they are completely
            # harmless and do not affect controller extraction.  The [RIG-OK]
            # message below confirms extraction succeeded despite the noise.
            self.logger.info(
                "[RIG] Loading .rig.mb — expect RfM 27.1→27.2 .atlasStyle "
                "compatibility messages below.  These are harmless."
            )

            # Snapshot scene SGs before loading the reference.  Veteran_Model_Final.ma
            # is a nested reference inside .rig.mb that may use mergeWithRoot, placing
            # all PxrDisney/PxrSurface SGs at the ROOT namespace rather than under
            # _rigExtract_:*.  Comparing post-load SGs to this snapshot lets us find
            # them regardless of where Maya actually puts them.
            pre_load_sgs: set = set(cmds.ls(type="shadingEngine") or [])

            # NOTE: Veteran_Model_Final.ma (nested ref inside .rig.mb) was saved
            # with Arnold and bakes `import arnold`/`import mtoa` callbacks.
            # The "import arnold / import mtoa" text visible in Maya's console is
            # MEL echo of the file-parse — it does NOT mean the import ran.
            # However, `registerArnoldRenderer()` may call cmds.loadPlugin("mtoa")
            # internally.  We snapshot loaded plugins before/after so we can
            # detect and unload any Arnold plugin that snuck in as a side-effect.
            _plugins_before_ref: set = set(cmds.pluginInfo(query=True, listPlugins=True) or [])
            try:
                cmds.file(
                    str(rig_mb_path),
                    reference=True,
                    namespace=namespace,
                    returnNewNodes=False,
                    loadReferenceDepth="all",
                )
                self.logger.info("[RIG] .rig.mb reference loaded successfully")
            except Exception as ref_err:
                self.logger.warning(f"[RIG] Could not reference .rig.mb: {ref_err}")
                return None

            # ── Detect + unload Arnold if loaded as a side-effect ────────────
            _plugins_after_ref: set = set(cmds.pluginInfo(query=True, listPlugins=True) or [])
            _arnold_side_effects: set = {
                p
                for p in (_plugins_after_ref - _plugins_before_ref)
                if p.lower() in ("mtoa", "arnold", "htoa", "mtoacmd")
            }
            if _arnold_side_effects:
                self.logger.warning(
                    f"[RIG] Arnold plugin(s) loaded as a side-effect of .rig.mb "
                    f"scriptNodes: {_arnold_side_effects}. "
                    f"The .rig.mb was saved with Arnold callbacks. "
                    f"Re-save .rig.mb without Arnold to stop this permanently. "
                    f"Attempting to unload..."
                )
                for _ap in _arnold_side_effects:
                    try:
                        cmds.unloadPlugin(_ap, force=True)
                        self.logger.info(f"[RIG] Unloaded Arnold plugin: {_ap}")
                    except Exception as _uerr:
                        self.logger.debug(
                            f"[RIG] Could not unload {_ap} (may have node types in scene): {_uerr}"
                        )
            else:
                self.logger.debug(
                    "[RIG] No Arnold/mtoa plugins were loaded by this reference "
                    "(the 'import arnold/mtoa' console lines are MEL echo only, not execution)"
                )

            controllers = []
            mappings: dict[str, list[str]] = {}
            joint_names: list[str] = []

            try:
                # ── Find all joints ──
                all_joints = cmds.ls(f"{namespace}:*", type="joint", long=False) or []
                # Strip namespace for clean names
                joint_names = [j.replace(f"{namespace}:", "") for j in all_joints]

                # ── Find NURBS curves (controllers) ──
                all_curves = cmds.ls(f"{namespace}:*", type="nurbsCurve", long=True) or []
                self.logger.info(
                    f"[RIG] Found {len(all_curves)} NURBS curves, " f"{len(all_joints)} joints"
                )

                for curve_shape in all_curves:
                    # Get transform parent
                    parents = cmds.listRelatives(curve_shape, parent=True, fullPath=True)
                    if not parents:
                        continue
                    transform = parents[0]
                    short_name = transform.split("|")[-1].split(":")[-1]

                    # Skip non-controller curves (construction history, etc.)
                    # Controllers typically have "ctrl" or "CTRL" or known
                    # prefixes, but we'll be inclusive and grab everything
                    try:
                        # Get curve CVs
                        num_cvs = cmds.getAttr(f"{curve_shape}.controlPoints", size=True)
                        cvs = []
                        for i in range(num_cvs):
                            pt = cmds.getAttr(f"{curve_shape}.controlPoints[{i}]")
                            if pt:
                                cvs.append(pt[0])  # [(x,y,z)]

                        if not cvs:
                            continue

                        # Curve properties
                        degree = cmds.getAttr(f"{curve_shape}.degree")
                        form = cmds.getAttr(f"{curve_shape}.form")
                        spans = cmds.getAttr(f"{curve_shape}.spans")

                        # Knot vector
                        num_knots = spans + 2 * degree - 1
                        knots = []
                        try:
                            knots_raw = cmds.getAttr(f"{curve_shape}.knots[0:{num_knots - 1}]")
                            if knots_raw:
                                knots = list(knots_raw)
                        except Exception:
                            pass

                        # Transform
                        tx = cmds.getAttr(f"{transform}.translateX")
                        ty = cmds.getAttr(f"{transform}.translateY")
                        tz = cmds.getAttr(f"{transform}.translateZ")
                        rx = cmds.getAttr(f"{transform}.rotateX")
                        ry = cmds.getAttr(f"{transform}.rotateY")
                        rz = cmds.getAttr(f"{transform}.rotateZ")

                        # Override color (if set)
                        color = None
                        try:
                            if cmds.getAttr(f"{transform}.overrideEnabled"):
                                if cmds.getAttr(f"{transform}.overrideRGBColors"):
                                    cr = cmds.getAttr(f"{transform}.overrideColorR")
                                    cg = cmds.getAttr(f"{transform}.overrideColorG")
                                    cb = cmds.getAttr(f"{transform}.overrideColorB")
                                    color = (cr, cg, cb)
                        except Exception:
                            pass

                        controllers.append(
                            {
                                "name": short_name,
                                "cvs": cvs,
                                "degree": degree,
                                "form": form,
                                "knots": knots,
                                "translate": (tx, ty, tz),
                                "rotate": (rx, ry, rz),
                                "color": color,
                            }
                        )

                    except Exception as cv_err:
                        self.logger.debug(f"[RIG] Skipped {short_name}: {cv_err}")
                        continue

                # ── Find controller → joint mappings via constraints ──
                constraint_types = [
                    "parentConstraint",
                    "orientConstraint",
                    "pointConstraint",
                    "aimConstraint",
                    "scaleConstraint",
                ]
                for joint in all_joints:
                    joint_short = joint.replace(f"{namespace}:", "")
                    for ctype in constraint_types:
                        try:
                            constraints = (
                                cmds.listConnections(
                                    joint, type=ctype, source=True, destination=False
                                )
                                or []
                            )
                            for con in constraints:
                                # Find what drives this constraint
                                drivers = (
                                    cmds.listConnections(
                                        f"{con}.target", source=True, destination=False
                                    )
                                    or []
                                )
                                for driver in drivers:
                                    drv_short = driver.split(":")[-1].split("|")[-1]
                                    if drv_short not in mappings:
                                        mappings[drv_short] = []
                                    if joint_short not in mappings[drv_short]:
                                        mappings[drv_short].append(joint_short)
                        except Exception:
                            continue

                # Also check direct connections (no constraints)
                for joint in all_joints:
                    joint_short = joint.replace(f"{namespace}:", "")
                    for attr in ["rotate", "translate"]:
                        try:
                            conns = (
                                cmds.listConnections(
                                    f"{joint}.{attr}",
                                    source=True,
                                    destination=False,
                                    skipConversionNodes=True,
                                )
                                or []
                            )
                            for conn in conns:
                                conn_short = conn.split(":")[-1].split("|")[-1]
                                # Only map if it looks like a controller
                                node_type = cmds.nodeType(conn)
                                if node_type == "transform":
                                    shapes = cmds.listRelatives(
                                        conn, shapes=True, type="nurbsCurve"
                                    )
                                    if shapes:
                                        if conn_short not in mappings:
                                            mappings[conn_short] = []
                                        if joint_short not in mappings[conn_short]:
                                            mappings[conn_short].append(joint_short)
                        except Exception:
                            continue

                self.logger.info(
                    f"[RIG-OK] Extracted {len(controllers)} controllers, "
                    f"{len(mappings)} controller\u2192joint mappings \u2014 "
                    f"any .atlasStyle errors above are harmless RfM 27.1\u219227.2 noise"
                )

                # ── Cache RfM shader networks for use in _create_rfm_maya_shaders ──
                # While the reference is still live, BFS-export all PxrSurface / PxrDisney
                # SG networks to a temp .mb file.  _create_rfm_maya_shaders() imports this
                # cache to give the USD proxy the REAL original shaders (correct textures,
                # roughness, normal maps, subsurface, etc.) instead of synthetic
                # USD-approximation PxrSurface nodes.
                self._rfm_shader_cache_path: Optional[Path] = (
                    self._export_rfm_shaders_from_reference(namespace, pre_load_sgs)
                )
                if self._rfm_shader_cache_path:
                    self.logger.info(
                        "[RFM] RfM shader cache written \u2014 "
                        "original PxrSurface/PxrDisney nodes will be used on import"
                    )

            finally:
                # ── Remove the reference ──
                try:
                    # Get the reference node created by file -reference
                    ref_nodes = cmds.ls(f"{namespace}*", type="reference") or []
                    for rn in ref_nodes:
                        try:
                            cmds.file(removeReference=True, referenceNode=rn)
                        except Exception:
                            pass
                    self.logger.info("[RIG] Removed .rig.mb reference")
                except Exception as rm_err:
                    self.logger.warning(f"[RIG] Could not remove reference: {rm_err}")

            if not controllers:
                self.logger.warning("[RIG] No controllers extracted")
                return None

            return {
                "controllers": controllers,
                "mappings": mappings,
                "joint_names": joint_names,
            }

        except Exception as e:
            self.logger.error(f"[RIG] Controller extraction failed: {e}")
            self.logger.error(traceback.format_exc())
            return None

    def _export_rfm_shaders_from_reference(
        self, namespace: str, pre_load_sgs: Optional[set] = None
    ) -> Optional[Path]:
        """BFS-export all RenderMan shader networks from a loaded reference to a temp .mb.

        Called while the Maya reference ``namespace:*`` is still live (before
        ``removeReference``).  Uses a snapshot-diff strategy to find new SGs
        introduced by the reference load — this is robust to ``mergeWithRoot``
        nested references (like ``Veteran_Model_Final.ma``) which place their
        Pxr* SGs at the ROOT namespace rather than under ``namespace:*``.

        Args:
            namespace: The Maya reference namespace (without trailing colon).
            pre_load_sgs: Set of shadingEngine node names that existed in the
                scene BEFORE the reference was loaded.  New SGs (post minus pre)
                are the reference-sourced ones.  If ``None``, falls back to
                scanning ``namespace:*`` and ``namespace:*:*``.

        Returns:
            Path to the temp ``.mb`` file on success, ``None`` on failure.
        """
        if cmds is None:
            return None
        import tempfile as _tempfile

        try:
            # ── Strategy: snapshot-diff to locate SGs from the reference ─────
            # Veteran_Model_Final.ma is a nested ref inside .rig.mb.  Depending
            # on how .rig.mb saved the nested reference (bare namespace vs.
            # mergeWithRoot), the Pxr* SGs may land at ROOT namespace, under
            # _rigExtract_:*, or under _rigExtract_:sub_ns:*.
            # Using post−pre diff catches all three cases.
            post_load_all_sgs: list = cmds.ls(type="shadingEngine") or []
            if pre_load_sgs is not None:
                # New SGs introduced by the reference load (any namespace)
                new_sgs: list = [sg for sg in post_load_all_sgs if sg not in pre_load_sgs]
            else:
                # Fallback: namespace-prefix scan (3 levels deep)
                new_sgs = (
                    (cmds.ls(f"{namespace}:*", type="shadingEngine") or [])
                    + (cmds.ls(f"{namespace}:*:*", type="shadingEngine") or [])
                    + (cmds.ls(f"{namespace}:*:*:*", type="shadingEngine") or [])
                )
            self.logger.info(
                f"[RFM] Shader cache scan: {len(post_load_all_sgs)} total scene SGs, "
                f"{len(new_sgs)} new SG(s) from reference load"
            )
            if new_sgs:
                # Log first 10 names so we can see what Maya actually named them
                sample = new_sgs[:10]
                self.logger.info(f"[RFM] New SG names (first 10): {sample}")

            rfm_sgs: list = []
            for sg in new_sgs:
                # Wrap every per-SG probe in its own guard so a single bad node
                # (e.g. asBlackSG missing .surfaceShader/.rman__shader) can
                # never abort the whole scan.
                try:
                    found_pxr: bool = False

                    # ① Name-pattern fast-path: rfm2 consistently names its
                    #   shadingEngines after the shader — 'PxrDisneyBsdf1SG',
                    #   'PxrSurface3SG', etc.  The SG name itself is the most
                    #   reliable indicator when attribute connections vary across
                    #   rfm2 versions / rig setups.
                    sg_base = sg.split(":")[-1]  # strip any namespace prefix
                    if sg_base.startswith("Pxr"):
                        rfm_sgs.append(sg)
                        self.logger.debug(
                            f"[RFM] SG '{sg}' → accepted via name-pattern (Pxr* prefix)"
                        )
                        found_pxr = True

                    if not found_pxr:
                        # ② Broad attribute scan: query ALL source nodes connected
                        #   to this SG and check if any are Pxr* type.  This covers
                        #   .surfaceShader, .rman__shader, .rman__surface,
                        #   .rman_materials_out[N], and any future rfm2 attributes
                        #   without needing to enumerate them explicitly.
                        try:
                            all_sources = (
                                cmds.listConnections(
                                    sg,
                                    source=True,
                                    destination=False,
                                    plugs=False,
                                )
                                or []
                            )
                            for src_node in all_sources:
                                try:
                                    if cmds.nodeType(src_node).startswith("Pxr"):
                                        rfm_sgs.append(sg)
                                        self.logger.debug(
                                            f"[RFM] SG '{sg}' → accepted via "
                                            f"broad-scan (node '{src_node}' is "
                                            f"type '{cmds.nodeType(src_node)}')"
                                        )
                                        found_pxr = True
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    if not found_pxr:
                        self.logger.debug(
                            f"[RFM] SG '{sg}' (base='{sg_base}') → "
                            f"no Pxr* shader found via name-pattern or broad-scan"
                        )
                except Exception:
                    pass  # malformed SG — skip silently

            if not rfm_sgs:
                self.logger.info(
                    f"[RFM] Shader cache: scanned {len(new_sgs)} new SG(s) via "
                    f"name-pattern + broad-scan — none qualified as Pxr* SGs; "
                    f"Strategy 2 (USD-derived shaders) will be used"
                )
                return None
            self.logger.info(
                f"[RFM] Shader cache: {len(rfm_sgs)} Pxr* SG(s) accepted "
                f"(sample: {rfm_sgs[:5]})"
            )

            # ── Force rfm2 relay connections before BFS ───────────────────────
            # rfm2 27.2's update_disney_nodes fires via evalDeferred, which runs
            # AFTER cmds.file returns.  Without this call the relay connections
            # (SG.rman__surface → relay → PxrDisneyBsdf) don't exist yet and the
            # BFS falls back to the polluted defaultShaderList1 path which exports
            # the ENTIRE scene's shader library instead of only the relevant
            # network.  Calling the updater synchronously here ensures relay wiring
            # is present before traversal.
            for _rfm2_mod_path in (
                "rfm2.api.scene_updater",
                "rfm2.utils.scene_updater",
                "rfm2.scene_updater",
            ):
                try:
                    import importlib as _il

                    _su = _il.import_module(_rfm2_mod_path)
                    if hasattr(_su, "update_disney_nodes"):
                        _su.update_disney_nodes()
                        break
                except Exception:
                    pass

            # ── Build SG→shader sidecar map while relay connections are live ──
            # The update_disney_nodes() call above ensures every SG's
            # rman__surface → relay → PxrDisneyBsdf connection exists NOW.
            # Capture this ground-truth mapping so _rewrite_materials_usda
            # never has to guess via topology traversal (Strategy A/B/D/C).
            # Stored as {sg_leaf_name: pxr_shader_leaf_name}.
            # ── Surface-shader type allow-list ───────────────────────────────
            # rfm2 relay nodes have BOTH a surface shader (PxrDisneyBsdf /
            # PxrSurface) AND possibly a displacement shader (PxrDisplace)
            # connected as sources.  Taking the FIRST Pxr* node found from
            # the relay sometimes gives PxrDisplace instead of the surface
            # shader.  This set is used to prefer surface shader types over
            # displacement/utility types in all relay traversals.
            _SURFACE_SHADER_TYPES: frozenset = frozenset(
                {
                    "PxrDisneyBsdf",
                    "PxrSurface",
                    "PxrLayer",
                    "PxrLayerSurface",
                    "PxrLayerMixer",
                    "PxrVolume",
                    "PxrMarschnerHair",
                    "PxrConstant",
                    "PxrBlack",
                    "PxrSkin",
                }
            )

            _sg_shader_map: dict = {}
            for _map_sg in rfm_sgs:
                _map_sg_leaf = _map_sg.split(":")[-1]
                _map_shader: Optional[str] = None
                # Primary: relay topology SG.rman__surface → relay → Pxr*
                # Prefer surface shader types; only fall back to other Pxr*
                # nodes if no surface shader is found in the relay sources.
                try:
                    _relay_list = (
                        cmds.listConnections(
                            f"{_map_sg}.rman__surface",
                            source=False,
                            destination=True,
                            plugs=False,
                        )
                        or []
                    )
                    _relay_best: Optional[str] = None  # surface shader
                    _relay_fallback: Optional[str] = None  # any Pxr*
                    for _relay in set(_relay_list):
                        try:
                            for _rsrc in (
                                cmds.listConnections(
                                    _relay,
                                    source=True,
                                    destination=False,
                                    plugs=False,
                                )
                                or []
                            ):
                                if _rsrc == _map_sg:
                                    continue
                                try:
                                    if cmds.ls(_rsrc, dagObjects=True):
                                        continue
                                    _rtype = cmds.nodeType(_rsrc)
                                    if _rtype in _SURFACE_SHADER_TYPES:
                                        _relay_best = _rsrc.split(":")[-1]
                                        break  # surface shader found — stop
                                    elif _rtype.startswith("Pxr") and _relay_fallback is None:
                                        _relay_fallback = _rsrc.split(":")[-1]
                                except Exception:
                                    pass
                            if _relay_best:
                                break
                        except Exception:
                            pass
                    _map_shader = _relay_best or _relay_fallback
                except Exception:
                    pass
                # Fallback: broad incoming-source scan (surfaceShader / direct)
                # Prefer surface shader types over displacement/utility.
                if not _map_shader:
                    try:
                        _broad_best: Optional[str] = None
                        _broad_fallback: Optional[str] = None
                        for _bsrc in (
                            cmds.listConnections(
                                _map_sg,
                                source=True,
                                destination=False,
                                plugs=False,
                            )
                            or []
                        ):
                            try:
                                if not cmds.ls(_bsrc, dagObjects=True) and _bsrc != _map_sg:
                                    _btype = cmds.nodeType(_bsrc)
                                    if _btype in _SURFACE_SHADER_TYPES:
                                        _broad_best = _bsrc.split(":")[-1]
                                        break
                                    elif _btype.startswith("Pxr") and _broad_fallback is None:
                                        _broad_fallback = _bsrc.split(":")[-1]
                            except Exception:
                                pass
                        _map_shader = _broad_best or _broad_fallback
                    except Exception:
                        pass
                if _map_shader:
                    # Keep both full SG name and leaf key to avoid collisions
                    # when multiple namespaces contain similarly-named SGs.
                    _sg_shader_map[_map_sg] = _map_shader
                    _sg_shader_map.setdefault(_map_sg_leaf, _map_shader.split(":")[-1])

            # ── BFS: collect the full shader network (bidirectional) ──────────
            # Uses bidirectional listConnections (no source/destination filter)
            # so the rfm2 27.2 relay topology is traversed correctly:
            #
            #   PxrTexture → PxrDisneyBsdf → relay ← SG.rman__surface
            #
            # The connection between SG and relay is DESTINATION-direction from
            # the SG (SG.rman__surface is the SOURCE, relay.message is the
            # DESTINATION).  A source-only BFS from the SG finds nothing because
            # the relay is an outgoing destination — it is not a source flowing
            # into the SG.  Bidirectional traversal catches SG→relay, then
            # relay→PxrDisneyBsdf (source direction into relay), and continues
            # upstream to PxrTexture/PxrNormalMap nodes.
            #
            # DAG nodes (geometry, transforms, joints, curves) are pruned to
            # keep the BFS inside the shader DG graph only.
            #
            # Scene-wide utility nodes (defaultShaderList1, defaultTextureList1,
            # etc.) connect to EVERY shader in the scene.  Traversing through
            # them bloats the visited set with unrelated shaders and makes the
            # exported .mb unnecessarily large.  These are excluded explicitly.
            _SYSTEM_NODES_EXCLUDE: frozenset = frozenset(
                {
                    "defaultShaderList1",
                    "defaultTextureList1",
                    "defaultRenderUtilityList1",
                    "defaultRenderingList1",
                    "initialShadingGroup",
                    "initialParticleSE",
                    "lambert1",
                    "defaultLambertShader",
                    "particleCloud1",
                }
            )
            visited: set = set()
            stack = list(rfm_sgs)
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                try:
                    if cmds.ls(node, dagObjects=True):
                        # DAG node — geometry, transform, joint, etc.  Skip it
                        # so the BFS stays within the shader DG graph only.
                        continue
                except Exception:
                    pass
                visited.add(node)
                # Bidirectional — no source/destination filter so we traverse
                # both incoming AND outgoing connections from every node.
                # System-wide list nodes are excluded to keep traversal lean.
                connected = [
                    n
                    for n in (cmds.listConnections(node, plugs=False) or [])
                    if n.split(":")[-1] not in _SYSTEM_NODES_EXCLUDE
                ]
                stack.extend(connected)

            # ── Export to temp file ───────────────────────────────────────────
            tmp_path = Path(_tempfile.mktemp(suffix="_rfm_shaders.mb"))
            cmds.select(list(visited), replace=True)
            cmds.file(
                str(tmp_path),
                exportSelected=True,
                type="mayaBinary",
                force=True,
                preserveReferences=False,
            )
            cmds.select(clear=True)
            self.logger.debug(
                f"[RFM] Shader cache: exported {len(rfm_sgs)} SGs "
                f"({len(visited)} nodes) \u2192 {tmp_path.name}"
            )

            # ── Write SG→shader sidecar JSON alongside the .mb ───────────────
            # The importer reads this as Strategy 0 in
            # _rewrite_materials_usda_with_disney_networks — no topology
            # guessing required at import time.
            import json as _json

            _sidecar_path = tmp_path.with_suffix(".sg_map.json")
            try:
                _sidecar_path.write_text(
                    _json.dumps(_sg_shader_map, indent=2),
                    encoding="utf-8",
                )
                self._rfm_shader_cache_sg_map_path: Optional[Path] = _sidecar_path
                self.logger.info(
                    f"[RFM] SG\u2192shader sidecar written: "
                    f"{len(_sg_shader_map)} entr{'y' if len(_sg_shader_map) == 1 else 'ies'} "
                    f"\u2192 {_sidecar_path.name}"
                )
            except Exception as _sidecar_err:
                self.logger.warning(f"[RFM] Sidecar write failed: {_sidecar_err}")
                self._rfm_shader_cache_sg_map_path = None

            return tmp_path

        except Exception as err:
            self.logger.warning(f"[RFM] Shader cache export failed: {err}")
            try:
                cmds.select(clear=True)
            except Exception:
                pass
            return None

    def _import_rfm_shaders_from_cache(self, mat_prim_paths: set) -> dict:
        """Import the RfM shader cache created by ``_export_rfm_shaders_from_reference``.

        Imports the temp ``.mb`` under a fresh namespace, deletes all DAG
        transforms (geometry / joints / curves) from that namespace so only
        DG shader nodes remain, then name-matches each imported
        ``shadingEngine`` to a USD material prim path.

        Args:
            mat_prim_paths: Set of USD material prim path strings
                (e.g. ``{'/Materials/PxrDisneyBsdf1', ...}``).

        Returns:
            ``{mat_path_str: sg_node_name}`` mapping on success; empty dict
            if the cache does not exist or the import fails.
        """
        if cmds is None:
            return {}

        cache_path: Optional[Path] = getattr(self, "_rfm_shader_cache_path", None)
        if not cache_path or not cache_path.exists():
            return {}

        IMPORT_NS = "rfmMat"
        _file_import_err: Optional[Exception] = None

        # ── Pre-import snapshot ───────────────────────────────────────────────
        # Use snapshot-diff (same strategy as the export side) so we catch ALL
        # newly imported SGs regardless of namespace depth.  When the temp .mb
        # was exported from a mergeWithRoot reference, some nodes may land at
        # rfmMat:subNS:SgName rather than rfmMat:SgName, making a
        # 'rfmMat:*' wildcard scan miss them entirely.
        pre_sgs: set = set(cmds.ls(type="shadingEngine") or [])
        pre_transforms: set = set(cmds.ls(type="transform", long=True) or [])
        _tex_node_types: list = [
            "PxrTexture",
            "PxrNormalMap",
            "PxrPtexture",
            "PxrManifoldFile",
            "PxrTextureObject",
        ]

        try:
            cmds.file(
                str(cache_path),
                i=True,
                type="mayaBinary",
                namespace=IMPORT_NS,
                ignoreVersion=True,
            )
        except Exception as import_err:
            # Maya sometimes raises RuntimeError("Error reading file.") even when
            # shader DG nodes WERE successfully imported — non-fatal rig-model
            # reference errors (e.g. .atlasStyle, missing blendShapes) get
            # re-raised by cmds.file even though the Pxr* network loaded fine.
            # Store the error and continue — we'll attempt to recover any rfmMat:
            # SGs that made it into the scene; only bail out if truly nothing imported.
            _file_import_err = import_err
            self.logger.debug(
                f"[RFM] Shader cache import raised — will attempt node recovery: {import_err}"
            )
        finally:
            # Always delete the temp file and clear the cache pointer.
            try:
                cache_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._rfm_shader_cache_path = None

        # ── Load SG→shader sidecar (Strategy-0 ground-truth map) ─────────────
        # Written during export with live relay connections (before evalDeferred
        # fires).  Using it here avoids relying on live graph traversal which
        # fails for deferred-wired rfm2 relay nodes at import time.
        import json as _json_import

        _sidecar_map: dict = {}
        _sgmap_path: Optional[Path] = getattr(self, "_rfm_shader_cache_sg_map_path", None)
        if _sgmap_path and _sgmap_path.exists():
            try:
                _sidecar_map = _json_import.loads(_sgmap_path.read_text(encoding="utf-8"))
                self.logger.debug(
                    f"[RFM] Import: sidecar loaded — {len(_sidecar_map)} entries "
                    f"will be used as Strategy-0 SG detection"
                )
            except Exception as _sc_load_err:
                self.logger.debug(
                    f"[RFM] Import: sidecar load failed — {_sc_load_err}; "
                    f"falling back to live graph traversal only"
                )
        # NOTE: do NOT delete _sgmap_path here — _rewrite_materials_usda_with_disney_networks
        # needs it for its own Strategy-0 USD spec generation.

        NS_PREFIX = f"{IMPORT_NS}:"

        try:
            # ── Post-import snapshot diff ─────────────────────────────────────
            # Finds every SG and transform that was introduced by the import,
            # regardless of how deep the namespace nesting is.
            post_sgs: set = set(cmds.ls(type="shadingEngine") or [])
            post_transforms: set = set(cmds.ls(type="transform", long=True) or [])
            all_sgs: list = [sg for sg in post_sgs if sg not in pre_sgs]
            new_transforms: list = [t for t in post_transforms if t not in pre_transforms]

            # ── Collect SGs with Pxr* surface shaders ────────────────────────
            rfm_sgs: dict = {}  # leaf_name (no namespace) → sg_full_name

            def _find_live_pxr_shader_for_sg(_sg_name: str) -> Optional[str]:
                """Return a connected/derivable Pxr* shader for the SG.

                If a derivable shader exists but the SG has no direct surfaceShader
                connection yet (common while rfm2 relay wiring is still deferred),
                this method also repairs a direct SG.surfaceShader connection so the
                shader is visible/useful in Hypershade immediately.
                """

                def _try_repair_surface_shader(_sg: str, _shader: str) -> None:
                    """Connect shader.outColor -> SG.surfaceShader if currently unbound."""
                    try:
                        _incoming = (
                            cmds.listConnections(
                                f"{_sg}.surfaceShader",
                                source=True,
                                destination=False,
                                plugs=False,
                            )
                            or []
                        )
                        if _incoming:
                            return
                        if not cmds.attributeQuery("outColor", node=_shader, exists=True):
                            return
                        cmds.connectAttr(
                            f"{_shader}.outColor",
                            f"{_sg}.surfaceShader",
                            force=True,
                        )
                    except Exception:
                        pass

                # A) rfm2 relay path: SG.rman__surface -> relay <- Pxr*
                try:
                    _relay_nodes = (
                        cmds.listConnections(
                            f"{_sg_name}.rman__surface",
                            source=False,
                            destination=True,
                            plugs=False,
                        )
                        or []
                    )
                    for _relay_node in set(_relay_nodes):
                        for _src_node in (
                            cmds.listConnections(
                                _relay_node,
                                source=True,
                                destination=False,
                                plugs=False,
                            )
                            or []
                        ):
                            if _src_node == _sg_name:
                                continue
                            try:
                                if cmds.ls(_src_node, dagObjects=True):
                                    continue
                                if cmds.nodeType(_src_node).startswith("Pxr"):
                                    _try_repair_surface_shader(_sg_name, _src_node)
                                    return _src_node
                            except Exception:
                                pass
                except Exception:
                    pass

                # B) direct incoming shader plugs
                for _attr_name in ("surfaceShader", "rman__surface"):
                    try:
                        for _src_node in (
                            cmds.listConnections(
                                f"{_sg_name}.{_attr_name}",
                                source=True,
                                destination=False,
                                plugs=False,
                            )
                            or []
                        ):
                            try:
                                if cmds.nodeType(_src_node).startswith("Pxr"):
                                    _try_repair_surface_shader(_sg_name, _src_node)
                                    return _src_node
                            except Exception:
                                pass
                    except Exception:
                        pass

                # C) name-derived fallback (handles deferred relay wiring)
                # NOTE: We intentionally avoid broad graph BFS here.  BFS can
                # cross partition/default list utility nodes and falsely treat
                # lambert/default SGs as Pxr-backed, which breaks Hypershade
                # material visibility and SG->shader mapping correctness.
                try:
                    _sg_leaf = _sg_name.split(":")[-1]
                    _sg_ns = ":".join(_sg_name.split(":")[:-1])
                    _bases: List[str] = [_sg_leaf]
                    for _sfx in ("_SG", "SG"):
                        if _sg_leaf.endswith(_sfx):
                            _bases.insert(0, _sg_leaf[: -len(_sfx)])
                            break

                    _candidates: List[str] = []
                    for _base in _bases:
                        for _stype in ("PxrDisneyBsdf", "PxrSurface", "PxrLayer"):
                            for _node in cmds.ls(type=_stype) or []:
                                if _node.split(":")[-1] == _base:
                                    _candidates.append(_node)
                        _candidates.extend(cmds.ls(f"*:{_base}") or [])
                        if _sg_ns:
                            _candidates.append(f"{_sg_ns}:{_base}")

                    for _cand in dict.fromkeys(_candidates):
                        try:
                            if cmds.objExists(_cand) and cmds.nodeType(_cand).startswith("Pxr"):
                                _try_repair_surface_shader(_sg_name, _cand)
                                return _cand
                        except Exception:
                            pass
                except Exception:
                    pass

                return None

            for sg in all_sgs:
                try:
                    sg_base = sg.split(":")[-1]

                    # ── Strategy 0: sidecar fast-path ─────────────────────────
                    # The sidecar was captured during export when rfm2 relay
                    # connections were definitively live.  Trust it without
                    # live graph traversal (which fails before update_disney_nodes
                    # evalDeferred fires and the SG.surfaceShader/rman__surface
                    # links are established).
                    if sg_base in _sidecar_map:
                        _sidecar_shader_raw = _sidecar_map[sg_base]
                        if isinstance(_sidecar_shader_raw, str):
                            _sidecar_shader_leaf = _sidecar_shader_raw.split(":")[-1]
                            # Verify shader node exists (handles any namespace depth).
                            _sc_shader_found: bool = False
                            for _stype in ("PxrDisneyBsdf", "PxrSurface", "PxrLayer"):
                                for _n in cmds.ls(type=_stype) or []:
                                    if _n.split(":")[-1] == _sidecar_shader_leaf:
                                        _sc_shader_found = True
                                        break
                                if _sc_shader_found:
                                    break
                            # Accept SG regardless of live-shader detection:
                            # sidecar confirms Pxr-backed, and
                            # _rewrite_materials_usda uses its own Strategy-0
                            # to locate the shader node for USD spec authoring.
                            rfm_sgs[sg_base] = sg
                            continue

                    # ── Strategy 1: live graph traversal fallback ──────────────
                    _live_shader = _find_live_pxr_shader_for_sg(sg)
                    if _live_shader:
                        rfm_sgs[sg_base] = sg
                except Exception:
                    pass

            # ── Delete all DAG transforms imported alongside the shaders ──────
            # Shader/texture DG nodes have no DAG parents and survive this step.
            if new_transforms:
                try:
                    cmds.delete(new_transforms)
                except Exception:
                    pass

            # ── Diagnostic: total vs filtered ────────────────────────────────
            self.logger.info(
                f"[RFM] Import: snapshot-diff found {len(all_sgs)} total new SGs; "
                f"Pxr* filter accepted {len(rfm_sgs)}; "
                f"supplemental lookup will fill the remainder"
            )

            # ── Supplemental lookup: fill any SGs missed by snapshot-diff ────
            # When the .rig.mb reference is removed, some nested-reference SGs
            # from Veteran_Model_Final.ma may survive at ROOT namespace (Maya
            # doesn't always clean up mergeWithRoot nested-ref nodes).  Those
            # SGs are in pre_sgs so the diff misses them.  Check by name:
            #   a) root namespace  (survived ref cleanup) — e.g. PxrDisneyBsdf1SG
            #   b) rfmMat: namespace (imported but missed by diff for any reason)
            supplemental_added: int = 0
            for mat_path_s in (str(p) for p in mat_prim_paths):
                mat_leaf = Sdf.Path(mat_path_s).name  # e.g. 'PxrDisneyBsdf1SG'
                if mat_leaf in {"initialShadingGroup", "initialParticleSE"}:
                    continue
                if mat_leaf.startswith("default"):
                    continue
                if mat_leaf in rfm_sgs:
                    continue  # already found via snapshot-diff

                # (a) root namespace — SG survived .rig.mb ref cleanup
                if cmds.ls(mat_leaf, type="shadingEngine"):
                    # Strategy 0: sidecar confirms Pxr-backed — no traversal needed
                    if mat_leaf in _sidecar_map:
                        rfm_sgs[mat_leaf] = mat_leaf
                        supplemental_added += 1
                    elif _find_live_pxr_shader_for_sg(mat_leaf):
                        rfm_sgs[mat_leaf] = mat_leaf
                        supplemental_added += 1
                    continue

                # (b) rfmMat: namespace — may have been missed by snapshot-diff
                ns_candidate = f"{NS_PREFIX}{mat_leaf}"
                if cmds.ls(ns_candidate, type="shadingEngine"):
                    if mat_leaf in _sidecar_map:
                        rfm_sgs[mat_leaf] = ns_candidate
                        supplemental_added += 1
                    elif _find_live_pxr_shader_for_sg(ns_candidate):
                        rfm_sgs[mat_leaf] = ns_candidate
                        supplemental_added += 1

            if supplemental_added:
                self.logger.info(
                    f"[RFM] Import: supplemental lookup added {supplemental_added} "
                    f"SGs that were in pre_sgs (survived .rig.mb ref cleanup)"
                )

            # ── Build USD material path → Maya SG mapping ────────────────────
            # USD material names: /Looks/PxrDisneyBsdf1SG  → name = 'PxrDisneyBsdf1SG'
            # Maya SG base names: 'PxrDisneyBsdf1SG'  (exact match via base_name key)
            # Also try stripping trailing 'SG' in case USD name omits it.
            sg_lookup: dict = {}  # lower(name) → sg_full_name
            for base_name, sg_node in rfm_sgs.items():
                # Try both {name}SG and just {name} (some rigs don't append SG)
                stripped = base_name[:-2] if base_name.lower().endswith("sg") else base_name
                sg_lookup[stripped.lower()] = sg_node
                sg_lookup[base_name.lower()] = sg_node

            self.logger.info(
                f"[RFM] Import: {len(rfm_sgs)} SGs collected; "
                f"sg_lookup has {len(sg_lookup)} keys; "
                f"sample keys: {list(sg_lookup)[:6]}"
            )

            # Normalise all mat_prim_paths to str so Sdf.Path vs str
            # key types never cause silent dict-lookup misses.
            mat_path_strs: list = [str(p) for p in mat_prim_paths]
            self.logger.info(
                f"[RFM] Import: {len(mat_path_strs)} mat_prim_paths; "
                f"sample: {mat_path_strs[:4]}"
            )

            mat_path_to_sg: dict = {}  # str(USD mat path) → maya SG name
            for mat_path_str in mat_path_strs:
                mat_name = Sdf.Path(mat_path_str).name
                candidate = sg_lookup.get(mat_name.lower()) or sg_lookup.get(
                    (mat_name + "SG").lower()
                )
                if candidate:
                    _cand_leaf = candidate.split(":")[-1]
                    if _cand_leaf in {"initialShadingGroup", "initialParticleSE"}:
                        continue
                    if _cand_leaf.startswith("default"):
                        continue
                    mat_path_to_sg[mat_path_str] = candidate

            self.logger.info(
                f"[RFM] Import: name-matched {len(mat_path_to_sg)}/{len(mat_path_strs)} "
                f"USD material paths to imported SGs"
            )

            # ── Log unmatched paths so the user knows which 8 get Strategy 2 ─
            _unmatched = [p for p in mat_path_strs if p not in mat_path_to_sg]
            if _unmatched:
                _unmatched_names = [Sdf.Path(p).name for p in _unmatched]
                _pxr_unmatched = [n for n in _unmatched_names if n.startswith("Pxr")]
                self.logger.info(
                    f"[RFM] Import: {len(_unmatched)} unmatched USD paths → Strategy-2 "
                    f"PxrSurface fallback: {_unmatched_names}"
                )
                if _pxr_unmatched:
                    self.logger.warning(
                        f"[RFM] Import: {len(_pxr_unmatched)} UNMATCHED Pxr* material(s) "
                        f"will get synthetic PxrSurface instead of original PxrDisneyBsdf: "
                        f"{_pxr_unmatched} — check if .rig.mb shader cache is current"
                    )

            # ── Rename nodes to drop the entire namespace prefix ─────────────
            # This gives clean Hypershade node names (PxrDisneyBsdf1SG, etc.).
            # We rename ALL non-DAG nodes introduced by the import using the
            # snapshot-diff set.  Using the leaf name (split(':')[-1]) correctly
            # handles nodes at any namespace depth (rfmMat:sub:Name → Name).
            #
            # IMPORTANT: deduplicate before iterating.  `cmds.ls(type='shadingEngine')`
            # and `cmds.ls()` both return SG nodes, so the same rfmMat:XXX node can
            # appear TWICE.  Without dedup, the first loop renames it successfully
            # and stores `renamed[old] = new`.  The second loop tries to rename the
            # now-gone old name, raises an exception, and overwrites `renamed[old]`
            # with the stale `old` value — making mat_path_to_sg keep the rfmMat:
            # prefix and causing _sg_has_texture to be called on a dead node name.
            all_new_nodes: list = list(
                dict.fromkeys(
                    n
                    for n in (cmds.ls(type="shadingEngine") or []) + (cmds.ls() or [])
                    if n not in pre_sgs and n not in pre_transforms and n.startswith(NS_PREFIX)
                )
            )
            renamed: dict = {}  # old_name → new_name
            for node in all_new_nodes:
                leaf = node.split(":")[-1]
                try:
                    new_name = cmds.rename(node, leaf)
                    renamed[node] = new_name
                except Exception:
                    renamed[node] = node  # keep qualified name on collision

            # Update mat_path_to_sg with renamed SG names
            for mat_path, sg in list(mat_path_to_sg.items()):
                if sg in renamed:
                    mat_path_to_sg[mat_path] = renamed[sg]

            def _register_shader_in_default_list(_shader: str) -> bool:
                """Ensure shader.message is connected to defaultShaderList1."""
                try:
                    if not cmds.objExists(_shader) or not cmds.objExists("defaultShaderList1"):
                        return False
                    _msg_out = (
                        cmds.listConnections(
                            f"{_shader}.message",
                            source=False,
                            destination=True,
                            plugs=True,
                        )
                        or []
                    )
                    if any(_dst.startswith("defaultShaderList1.") for _dst in _msg_out):
                        return True

                    # Direct connectAttr only — defaultNavigation is an interactive
                    # MEL command that calls connectWindowWith and opens the Connection
                    # Editor when connection classification is ambiguous.
                    for _dst_attr in ("defaultShaderList1.shaders", "defaultShaderList1.s"):
                        try:
                            cmds.connectAttr(
                                f"{_shader}.message",
                                _dst_attr,
                                nextAvailable=True,
                                force=True,
                            )
                        except Exception:
                            pass

                    _msg_out = (
                        cmds.listConnections(
                            f"{_shader}.message",
                            source=False,
                            destination=True,
                            plugs=True,
                        )
                        or []
                    )
                    return any(_dst.startswith("defaultShaderList1.") for _dst in _msg_out)
                except Exception:
                    return False

            def _resolve_sidecar_shader_for_sg(_sg_name: str) -> Optional[str]:
                """Resolve sidecar SG->shader mapping to a live Pxr SURFACE node.

                Only accepts surface shader types — displacement (PxrDisplace,
                PxrDispTransform) and utility nodes are explicitly excluded.
                """
                # Valid surface shader types in rfm2 27.2.
                _surf_types: frozenset = frozenset(
                    {
                        "PxrDisneyBsdf",
                        "PxrSurface",
                        "PxrLayer",
                        "PxrLayerSurface",
                        "PxrLayerMixer",
                        "PxrVolume",
                        "PxrMarschnerHair",
                        "PxrConstant",
                        "PxrBlack",
                        "PxrSkin",
                    }
                )
                _sg_leaf = _sg_name.split(":")[-1]
                _shader_raw = _sidecar_map.get(_sg_name) or _sidecar_map.get(_sg_leaf)
                if not isinstance(_shader_raw, str):
                    return None

                _shader_leaf = _shader_raw.split(":")[-1]
                _sg_ns = ":".join(_sg_name.split(":")[:-1])
                _candidates: List[str] = []
                if _sg_ns:
                    _candidates.append(f"{_sg_ns}:{_shader_leaf}")
                _candidates.append(_shader_leaf)
                _candidates.extend(cmds.ls(f"*:{_shader_leaf}") or [])

                for _cand in dict.fromkeys(_candidates):
                    try:
                        if cmds.objExists(_cand) and cmds.nodeType(_cand) in _surf_types:
                            return _cand
                    except Exception:
                        pass
                return None

            # ── Sidecar-first SG->shader rebinding for Hypershade visibility ─
            # Force a direct SG.surfaceShader plug from the sidecar mapping so
            # BSDF nodes show in Hypershade even before rfm2 relay deferred
            # callbacks run.
            _sidecar_rebound = 0
            _sidecar_unresolved = 0
            _sidecar_listed = 0
            for _sg_name in dict.fromkeys(mat_path_to_sg.values()):
                try:
                    if not cmds.objExists(_sg_name):
                        _sidecar_unresolved += 1
                        continue
                    _shader_node = _resolve_sidecar_shader_for_sg(_sg_name)
                    if not _shader_node:
                        _sidecar_unresolved += 1
                        continue
                    if not cmds.attributeQuery("outColor", node=_shader_node, exists=True):
                        _sidecar_unresolved += 1
                        continue
                    cmds.connectAttr(
                        f"{_shader_node}.outColor",
                        f"{_sg_name}.surfaceShader",
                        force=True,
                    )
                    if _register_shader_in_default_list(_shader_node):
                        _sidecar_listed += 1
                    _sidecar_rebound += 1
                except Exception:
                    _sidecar_unresolved += 1

            if _sidecar_rebound or _sidecar_unresolved:
                self.logger.info(
                    f"[RFM] Import: sidecar rebinding applied to {_sidecar_rebound} SGs; "
                    f"{_sidecar_unresolved} SGs unresolved; "
                    f"{_sidecar_listed} shaders listed in defaultShaderList1"
                )

            self.logger.info(
                f"[RFM] Import: final mat_path_to_sg has {len(mat_path_to_sg)} entries; "
                f"sample: {dict(list(mat_path_to_sg.items())[:3])}"
            )

            # ── Identify textured SGs via relay-aware shader history ─────────
            # rfm2 27.2's scene updater (update_disney_nodes) rebuilds the
            # PxrDisneyBsdf→relay→SG connection AFTER cmds.file returns, so
            # listHistory(future=True) from a PxrTexture always stops at
            # PxrDisneyBsdf and never reaches the SG.
            #
            # rfm2 relay topology:
            #   SG.rman__surface → relay.message   (SG is SOURCE → relay is DEST)
            #   PxrDisneyBsdf → relay.someAttr     (PxrDisney is SOURCE)
            # The SG has NO incoming surfaceShader connection — must traverse:
            #   SG.rman__surface (dest=True) → relay → sources → Pxr* shader
            # Then run listHistory(shader) upstream to find PxrTexture nodes.
            # Fallback: try stripping 'SG' suffix if relay traversal finds nothing.
            _tex_type_set: frozenset = frozenset(_tex_node_types)
            sgs_with_texture: set = set()
            for sg_node in mat_path_to_sg.values():
                _found_shader: Optional[str] = None

                # Path A: rfm2 relay traversal
                try:
                    _relay_list = (
                        cmds.listConnections(
                            f"{sg_node}.rman__surface",
                            source=False,
                            destination=True,
                            plugs=False,
                        )
                        or []
                    )
                    for _relay in set(_relay_list):
                        try:
                            for _src in (
                                cmds.listConnections(
                                    _relay,
                                    source=True,
                                    destination=False,
                                    plugs=False,
                                )
                                or []
                            ):
                                if _src == sg_node:
                                    continue
                                try:
                                    if cmds.ls(_src, dagObjects=True):
                                        continue
                                    if cmds.nodeType(_src).startswith("Pxr"):
                                        _found_shader = _src
                                        break
                                except Exception:
                                    pass
                            if _found_shader:
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

                # Path B: strip-SG-suffix convention (e.g. PxrDisneyBsdf13SG → PxrDisneyBsdf13)
                if not _found_shader:
                    _derived = sg_node
                    for _sfx in ("_SG", "SG"):
                        if sg_node.endswith(_sfx):
                            _derived = sg_node[: -len(_sfx)]
                            break
                    if _derived != sg_node and cmds.ls(_derived):
                        _found_shader = _derived

                if not _found_shader:
                    continue

                # Walk upstream history of the discovered shader node
                try:
                    for h_node in cmds.listHistory(_found_shader, pruneDagObjects=True) or []:
                        try:
                            if cmds.nodeType(h_node) in _tex_type_set:
                                sgs_with_texture.add(sg_node)
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

            # Store on instance as preliminary value; the caller
            # (_create_rfm_maya_shaders) immediately overwrites this with the
            # USD-sourced mat_textures dict which is more reliable than live
            # DG traversal before rfm2's update_disney_nodes evalDeferred fires.
            self._rfm_sgs_with_texture: set = sgs_with_texture
            self.logger.debug(
                f"[RFM] Import: preliminary relay check — {len(sgs_with_texture)} "
                f"textured SGs detected pre-evalDeferred (USD-sourced mat_textures "
                f"provides ground truth; this value will be overridden by caller)"
            )

        except Exception as err:
            self.logger.warning(f"[RFM] Shader cache processing failed: {err}")
            return {}

        # ── Recovery check ────────────────────────────────────────────────────
        # If cmds.file raised but we still found SGs (partial import succeeded),
        # proceed with what we have.  Only bail if NOTHING was recovered.
        if _file_import_err and not mat_path_to_sg:
            self.logger.warning(
                f"[RFM] Shader cache import failed — no rfmMat: shader nodes "
                f"recovered: {_file_import_err}"
            )
            return {}

        return mat_path_to_sg

    def _sg_has_texture(self, sg_name: str) -> bool:
        """Return True when *sg_name* has any recognised RfM texture node in its shader network.

        rfm2 27.2 topology (confirmed):

            PxrTexture → PxrDisneyBsdf → relay.someAttr   (source → dest)
                                     SG.rman__surface → relay.message  (source → dest)

        The SG has NO INCOMING source connections from PxrDisneyBsdf.  The
        shader connects into the **relay** node, not directly into the SG.
        The SG's ``rman__surface`` attribute is itself the SOURCE of a
        connection going OUT to the relay — not a destination receiving from
        a shader.

        Strategy:
          A. Follow ``SG.rman__surface`` as a *source* attribute to its
             destination(s) = relay node(s).  (destination=True)
          B. From each relay, collect all *source* connections = connected
             shaders (PxrDisneyBsdf, PxrSurface, etc.) plus other SGs.
          C. Run ``listHistory(shader, pruneDagObjects=True)`` on each shader
             to walk upstream toward PxrTexture/PxrNormalMap nodes.
          D. Fallback: standard incoming ``.surfaceShader`` probe in case the
             rig uses a direct SG→shader connection instead of the relay.
          E. Final safety net: bidirectional BFS (cap 100) which covers any
             other topology variant.
        """
        if cmds is None:
            return False

        # ── Fast path: use the snapshot diff computed at import time ──────────
        # _rfm_sgs_with_texture is populated by _import_rfm_shaders_from_cache
        # immediately after the shader cache .mb is imported, using a pre/post
        # PxrTexture node snapshot diff + listHistory(future=True) traversal.
        # This skips all relay topology issues entirely.
        _snap = getattr(self, "_rfm_sgs_with_texture", None)
        if _snap is not None:
            _leaf = sg_name.split(":")[-1]
            if sg_name in _snap or _leaf in _snap:
                return True
            # _snap is populated — trust it and skip the slow fallback unless
            # the SG genuinely wasn't in the cached result.
            # We still fall through to the relay/BFS logic for SGs that come
            # from Strategy 2 (synthetic, no cache used).

        _TEXTURE_TYPES: frozenset = frozenset(
            {
                "PxrTexture",
                "PxrNormalMap",
                "PxrPtexture",
                "PxrManifoldFile",
                "PxrTextureObject",
            }
        )
        try:
            if not cmds.ls(sg_name):
                return False  # node no longer exists

            # ── A: SG.rman__surface → relay (destination direction) ───────────
            try:
                relay_list = (
                    cmds.listConnections(
                        f"{sg_name}.rman__surface",
                        source=False,
                        destination=True,
                        plugs=False,
                    )
                    or []
                )
                for relay in set(relay_list):
                    try:
                        for src in (
                            cmds.listConnections(
                                relay,
                                source=True,
                                destination=False,
                                plugs=False,
                            )
                            or []
                        ):
                            if src == sg_name:
                                continue
                            try:
                                if cmds.ls(src, dagObjects=True):
                                    continue
                                for h_node in cmds.listHistory(src, pruneDagObjects=True) or []:
                                    try:
                                        if cmds.nodeType(h_node) in _TEXTURE_TYPES:
                                            return True
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            # ── B/D: standard incoming surface-shader attrs ───────────────────
            for attr in ("surfaceShader", "rman__surface", "volumeShader", "displacementShader"):
                try:
                    for shader in (
                        cmds.listConnections(
                            f"{sg_name}.{attr}",
                            source=True,
                            destination=False,
                            plugs=False,
                        )
                        or []
                    ):
                        try:
                            for h_node in cmds.listHistory(shader, pruneDagObjects=True) or []:
                                try:
                                    if cmds.nodeType(h_node) in _TEXTURE_TYPES:
                                        return True
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

            # ── E: bidirectional BFS safety net ──────────────────────────────
            # Covers future rfm2 topology variants.  Now that the export BFS
            # is also bidirectional, the imported .mb contains the relay and
            # shader nodes, so this BFS reaches PxrTexture quickly (3-4 hops).
            _MAX_NODES = 100
            visited: set = {sg_name}
            queue: list = list(cmds.listConnections(sg_name, plugs=False) or [])
            visited.update(queue)
            while queue and len(visited) < _MAX_NODES:
                node = queue.pop(0)
                try:
                    if cmds.nodeType(node) in _TEXTURE_TYPES:
                        return True
                    if cmds.ls(node, dagObjects=True):
                        continue
                    for nbr in cmds.listConnections(node, plugs=False) or []:
                        if nbr not in visited:
                            visited.add(nbr)
                            queue.append(nbr)
                except Exception:
                    pass

        except Exception:
            pass
        return False

    def _populate_controllers_sublayer(self, stage, rig_data: dict) -> None:
        """
        Write NURBS controllers from .rig.mb as NurbsCurves prims
        in the controllers sublayer.

        Each controller becomes a USD NurbsCurves prim with:
        - Curve points (CVs)
        - Display color (from Maya override color)
        - Purpose = "guide" (visible in viewport, not rendered)
        - Custom attribute: assetManager:drivenJoints
        """
        try:
            controllers = rig_data.get("controllers", [])
            mappings = rig_data.get("mappings", {})

            # Create a /Controllers scope to organize them
            ctrl_scope = stage.DefinePrim("/Controllers", "Scope")
            UsdGeom.Imageable(ctrl_scope).CreatePurposeAttr(UsdGeom.Tokens.guide)

            written = 0
            skipped = 0
            seen_names: dict[str, int] = {}  # track name collisions

            for ctrl in controllers:
                name = ctrl["name"]
                cvs = ctrl["cvs"]
                if not cvs:
                    continue

                # Sanitize name for USD prim path
                safe_name = name.replace("|", "_").replace(":", "_")

                # Deduplicate: append suffix for collisions
                if safe_name in seen_names:
                    seen_names[safe_name] += 1
                    safe_name = f"{safe_name}_{seen_names[safe_name]}"
                else:
                    seen_names[safe_name] = 0

                prim_path = f"/Controllers/{safe_name}"

                try:
                    # Create NurbsCurves prim
                    prim = stage.DefinePrim(prim_path, "NurbsCurves")
                    curves = UsdGeom.NurbsCurves(prim)

                    # Set curve data
                    points = Vt.Vec3fArray([Gf.Vec3f(p[0], p[1], p[2]) for p in cvs])
                    curves.CreatePointsAttr(points)
                    curves.CreateCurveVertexCountsAttr(Vt.IntArray([len(cvs)]))

                    # Degree and order
                    degree = ctrl.get("degree", 3)
                    curves.CreateOrderAttr(Vt.IntArray([degree + 1]))

                    # Knots
                    knots = ctrl.get("knots", [])
                    if knots:
                        curves.CreateKnotsAttr(Vt.DoubleArray(knots))

                    # Set purpose to "guide" so it's visible but not rendered
                    UsdGeom.Imageable(prim).CreatePurposeAttr(UsdGeom.Tokens.guide)

                    # Display color from Maya override
                    color = ctrl.get("color")
                    if color:
                        curves.CreateDisplayColorAttr(
                            Vt.Vec3fArray([Gf.Vec3f(color[0], color[1], color[2])])
                        )

                    # Transform — only add ops if non-zero
                    tx, ty, tz = ctrl.get("translate", (0, 0, 0))
                    rx, ry, rz = ctrl.get("rotate", (0, 0, 0))
                    has_translate = any(v != 0 for v in (tx, ty, tz))
                    has_rotate = any(v != 0 for v in (rx, ry, rz))

                    if has_translate or has_rotate:
                        xform = UsdGeom.Xformable(prim)
                        if has_translate:
                            xform.AddTranslateOp().Set(Gf.Vec3d(tx, ty, tz))
                        if has_rotate:
                            xform.AddRotateXYZOp().Set(Gf.Vec3f(rx, ry, rz))

                    # Custom attribute: which joints this controller drives
                    driven = mappings.get(name, [])
                    if driven:
                        driven_attr = prim.CreateAttribute(
                            "assetManager:drivenJoints", Sdf.ValueTypeNames.StringArray
                        )
                        driven_attr.Set(driven)

                    written += 1

                except Exception as ctrl_err:
                    skipped += 1
                    self.logger.debug(f"[LAYER] Skipped controller {safe_name}: {ctrl_err}")

            skip_msg = f", {skipped} skipped" if skipped else ""
            self.logger.info(
                f"[LAYER] Wrote {written} NURBS controllers " f"to controllers sublayer{skip_msg}"
            )

        except Exception as e:
            self.logger.warning(f"[LAYER] Could not populate controllers sublayer: {e}")
            self.logger.debug(traceback.format_exc())

    def _populate_skeleton_metadata(self, stage, base_usd_path: Path, rig_data: dict) -> None:
        """
        Write controller→joint mapping metadata into the skeleton sublayer.

        For each Skeleton prim in the base USD, adds custom attributes:
        - assetManager:controllerMap — JSON mapping of joint→controller names

        This lets tools and scripts know which controller drives which joint
        without needing the .rig.mb at runtime.
        """
        try:
            mappings = rig_data.get("mappings", {})
            if not mappings:
                return

            # Invert: controller→joints  →  joint→controllers
            joint_to_ctrl: dict[str, list[str]] = {}
            for ctrl_name, joints in mappings.items():
                for joint_name in joints:
                    if joint_name not in joint_to_ctrl:
                        joint_to_ctrl[joint_name] = []
                    joint_to_ctrl[joint_name].append(ctrl_name)

            # Open the base stage read-only to find skeleton paths
            base_stage = Usd.Stage.Open(str(base_usd_path))
            if not base_stage:
                return

            # Find all Skeleton prims and write metadata
            skeletons_found = 0
            for prim in base_stage.Traverse():
                if not prim.IsA(UsdSkel.Skeleton):
                    continue

                skel = UsdSkel.Skeleton(prim)
                joints_attr = skel.GetJointsAttr().Get()
                if not joints_attr:
                    continue

                # Build the mapping for joints in this skeleton
                skel_map = {}
                for joint_path in joints_attr:
                    # Joint path like "Root/Spine1/L_Arm"
                    joint_leaf = str(joint_path).split("/")[-1]
                    if joint_leaf in joint_to_ctrl:
                        skel_map[str(joint_path)] = joint_to_ctrl[joint_leaf]

                if skel_map:
                    # Write onto the same prim path in the skeleton sublayer
                    over_prim = stage.OverridePrim(prim.GetPath())
                    map_attr = over_prim.CreateAttribute(
                        "assetManager:controllerMap", Sdf.ValueTypeNames.String
                    )
                    map_attr.Set(json.dumps(skel_map, indent=2))
                    skeletons_found += 1

            if skeletons_found:
                self.logger.info(
                    f"[LAYER] Wrote controller→joint mappings "
                    f"for {skeletons_found} skeleton(s) — "
                    f"{len(joint_to_ctrl)} joints mapped"
                )

        except Exception as e:
            self.logger.warning(f"[LAYER] Could not populate skeleton metadata: {e}")
            self.logger.debug(traceback.format_exc())

    def _populate_geometry_primvar_fixes(
        self,
        geo_stage: Any,
        base_usd_path: Path,
    ) -> None:
        """Fix invalid primvar index arrays in the geometry override sublayer.

        The base .usdc may contain mesh prims whose indexed primvar arrays
        (typically UV sets) have out-of-range indices — i.e. an index value
        that is >= the length of the values array.  MayaUSD logs one
        ``Warning: Invalid primvar indices`` message per affected mesh when the
        proxy shape loads.

        This method opens the base USDC as a read-only stage, scans every
        ``UsdGeom.Mesh`` prim, and for each indexed primvar with at least one
        bad index it authors a corrected ``primvars:<name>:indices`` opinion
        into *geo_stage* (the writable ``geometry.usda`` sublayer).  Because
        ``geometry.usda`` sits above the base USDC in the root sublayer stack,
        its opinions win at composition time — eliminating the warnings without
        modifying the source file.

        Args:
            geo_stage: The ``Usd.Stage`` backed by ``geometry.usda`` (writable).
            base_usd_path: Path to the monolithic ``.usdc`` (read-only source).
        """
        if not USD_AVAILABLE:
            return
        try:
            base_stage = Usd.Stage.Open(str(base_usd_path))
            if not base_stage:
                return

            fix_count = 0
            for prim in base_stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                pvars_api = UsdGeom.PrimvarsAPI(prim)
                for pv in pvars_api.GetPrimvars():
                    if not pv.IsIndexed():
                        continue
                    indices = pv.GetIndices()  # Vt.IntArray
                    values = pv.Get()  # Vt values array
                    if not indices or not values:
                        continue
                    max_valid = len(values) - 1
                    if not any(i < 0 or i > max_valid for i in indices):
                        continue

                    # Author clamped indices into the geometry override layer.
                    override_prim = geo_stage.OverridePrim(str(prim.GetPath()))
                    idx_attr_name = f"primvars:{pv.GetPrimvarName()}:indices"
                    idx_attr = override_prim.GetAttribute(idx_attr_name)
                    if not idx_attr.IsValid():
                        idx_attr = override_prim.CreateAttribute(
                            idx_attr_name,
                            Sdf.ValueTypeNames.IntArray,
                            False,  # not a custom attribute
                        )
                    fixed = Vt.IntArray([max(0, min(int(i), max_valid)) for i in indices])
                    idx_attr.Set(fixed)
                    fix_count += 1
                    self.logger.debug(
                        f"[GEOM] Clamped primvar '{pv.GetPrimvarName()}' "
                        f"indices on {prim.GetPath()}"
                    )

            if fix_count:
                self.logger.info(
                    f"[GEOM] Sanitized {fix_count} invalid primvar index "
                    f"array(s) → geometry.usda — "
                    f"'Invalid primvar indices' warnings suppressed"
                )
        except Exception as e:
            self.logger.warning(f"[GEOM] Primvar index sanitization skipped: {e}")

    def _create_rfm_maya_shaders(
        self,
        usd_path: Path,
        proxy_transform: str,
        proxy_shape: str,
    ) -> int:
        """Create Maya PxrSurface + PxrTexture shaders from USD materials.

        For every Material prim that has a ``UsdPreviewSurface`` in the USD
        stage, this method creates matching Maya ``PxrSurface`` nodes (with
        optional ``PxrTexture`` for the diffuse channel) directly in the Maya
        DG.  The resulting shading groups are immediately visible in Hypershade
        and are rendered by rfm2's standard RIS translation path — solving both
        "no shaders in Hypershade" and "nothing renders in RenderMan IPR/IT".

        Each Maya shading group is also assigned to the matching USD mesh prims
        through the proxy shape using MayaUSD's ``|transform|shape,/PrimPath``
        selection syntax, mirroring the USD material bindings into Maya.

        Args:
            usd_path: Path to the composed root ``.usda`` (or base ``.usdc``).
            proxy_transform: Name of the Maya transform above the proxy shape.
            proxy_shape: Name of the ``mayaUsdProxyShape`` node.

        Returns:
            Number of Maya shading groups successfully created.
        """
        if cmds is None or not USD_AVAILABLE:
            return 0

        # Verify rfm2 is loaded — PxrSurface only exists when rfm2 is active.
        try:
            _probe = cmds.shadingNode("PxrSurface", asShader=True, name="__rfm_probe__")
            cmds.delete(_probe)
        except Exception:
            self.logger.info(
                "[RFM] PxrSurface unavailable — rfm2 may not be loaded; "
                "skipping Maya Hypershade shader creation"
            )
            return 0

        try:
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                return 0

            usd_dir = usd_path.parent

            # ── Collect materials, their UsdPreviewSurface shaders, and ─────────
            # mesh→material bindings from the composed stage.
            mat_preview: Dict[str, Any] = {}  # mat_path_str → UsdShade.Shader
            mat_textures: Dict[str, List] = {}  # mat_path_str → [UsdShade.Shader, …]
            mesh_bindings: Dict[str, str] = {}  # mesh_path_str → mat_path_str

            for prim in stage.Traverse():
                ptype = prim.GetTypeName()

                if ptype == "Mesh":
                    binding_api = UsdShade.MaterialBindingAPI(prim)
                    binding = binding_api.GetDirectBinding()
                    bound_mat = binding.GetMaterial()
                    if bound_mat and bound_mat.GetPrim().IsValid():
                        mesh_bindings[str(prim.GetPath())] = str(bound_mat.GetPrim().GetPath())
                    continue

                if ptype != "Shader":
                    continue

                shader = UsdShade.Shader(prim)
                try:
                    sid = shader.GetShaderId() or ""
                except Exception:
                    try:
                        sid = shader.GetIdAttr().Get() or ""
                    except Exception:
                        sid = ""

                if sid not in ("UsdPreviewSurface", "UsdUVTexture"):
                    continue

                # Walk up the hierarchy to find the enclosing Material prim.
                ancestor = prim.GetParent()
                mat_prim: Any = None
                while ancestor and ancestor.IsValid():
                    if ancestor.GetTypeName() == "Material":
                        mat_prim = ancestor
                        break
                    ancestor = ancestor.GetParent()
                if mat_prim is None:
                    continue

                mat_key = str(mat_prim.GetPath())
                if sid == "UsdPreviewSurface":
                    if mat_key not in mat_preview:
                        mat_preview[mat_key] = shader
                elif sid == "UsdUVTexture":
                    mat_textures.setdefault(mat_key, []).append(shader)

            if not mat_preview:
                self.logger.info(
                    "[RFM] No UsdPreviewSurface materials — nothing to import as Maya shaders"
                )
                return 0

            created_count = 0
            tex_count = 0
            mat_path_to_sg: Dict[str, str] = {}  # USD mat path → Maya SG name

            # ── Strategy 1: Import REAL RfM shaders from .rig.mb cache ────────
            # During _extract_rig_controllers the reference was used to export
            # the complete original PxrSurface / PxrDisney shader networks to a
            # temp .mb cache file (self._rfm_shader_cache_path).  Importing
            # that cache gives the scene the REAL materials from the original
            # Maya scene — correct textures, roughness, normal maps, subsurface,
            # etc. — instead of the lossy USD→PxrSurface reconstruction below.
            mat_prim_paths = set(mat_preview.keys()) | set(mesh_bindings.values())
            mat_path_to_sg = self._import_rfm_shaders_from_cache(mat_prim_paths)
            # Expose for Render-Ready Native Import (post-call SG assignment).
            self._last_mesh_bindings = dict(mesh_bindings)
            self._last_mat_path_to_sg = dict(mat_path_to_sg)

            if mat_path_to_sg:
                created_count = len(mat_path_to_sg)
                # Use the USD-sourced mat_textures dict to determine which SGs
                # are textured.  mat_textures was populated by scanning the
                # exported materials.usda for UsdUVTexture shaders — it is the
                # ground-truth record of what the exporter wrote and is 100%
                # reliable regardless of rfm2's evalDeferred relay rebuilding or
                # listHistory's inability to traverse plugin-node connections.
                tex_count = sum(1 for mp in mat_path_to_sg.keys() if mat_textures.get(mp))
                # Expose as instance set so _sg_has_texture + proxy label agree.
                self._rfm_sgs_with_texture = {
                    sg for mp, sg in mat_path_to_sg.items() if mat_textures.get(mp)
                }
                self.logger.info(
                    f"[RFM] Imported {created_count} original RfM shaders from "
                    f".rig.mb ({tex_count} textured) \u2014 exact settings from "
                    f"original Maya scene (PxrDisney/PxrSurface with full texture maps)"
                )
                # ── Rewrite materials.usda with real RIS networks from Maya DG ─
                # Now that PxrDisneyBsdf/PxrSurface nodes are live in the Maya
                # scene, replace the PxrPreviewSurface placeholders written by
                # _populate_rfm_materials_sublayer with the actual param values
                # and PxrTexture/PxrNormalMap connections read from the DG.
                # This makes outputs:ri:surface in the USD stage resolve to the
                # real Disney shader at render time (RfM IPR + batch/XPU).
                self._rewrite_materials_usda_with_disney_networks(
                    usd_path, mat_path_to_sg, mesh_bindings=mesh_bindings
                )
            _cache_used: bool = bool(mat_path_to_sg)  # True when Strategy 1 succeeded
            # ── Strategy 2: Synthetic PxrSurface from USD data (fallback) ──────
            # Runs for any material that was NOT found in the .rig.mb shader cache.
            # If Strategy 1 filled mat_path_to_sg completely, this loop is a no-op.
            for _sdf_mat_key, preview_shader in mat_preview.items():
                mat_key: str = str(_sdf_mat_key)  # normalise to str
                if mat_key in mat_path_to_sg:
                    # Real shader already imported from .rig.mb cache — skip.
                    continue

                mat_name = Sdf.Path(mat_key).name
                safe = mat_name.replace(" ", "_").replace(":", "_").replace(".", "_")

                # ── Resolve diffuse texture path ───────────────────────────────
                diffuse_tex: Optional[str] = None
                try:
                    dc_inp = preview_shader.GetInput("diffuseColor")
                    if dc_inp and dc_inp.HasConnectedSource():
                        for conn in dc_inp.GetAttr().GetConnections():
                            src_prim = stage.GetPrimAtPath(conn.GetPrimPath())
                            if not (src_prim and src_prim.IsValid()):
                                continue
                            src_sh = UsdShade.Shader(src_prim)
                            try:
                                src_id = src_sh.GetShaderId() or ""
                            except Exception:
                                src_id = ""
                            if src_id != "UsdUVTexture":
                                continue
                            f_inp = src_sh.GetInput("file")
                            if not f_inp:
                                continue
                            asset = f_inp.Get()
                            if asset:
                                diffuse_tex = str(asset.path)
                            break
                except Exception:
                    pass

                # Fallback: first non-normal texture in the material's UVTexture list.
                if not diffuse_tex:
                    for uv_sh in mat_textures.get(_sdf_mat_key, []):
                        cname = uv_sh.GetPrim().GetName().lower()
                        if any(t in cname for t in ("normal", "nrm", "nml", "bump", "spec")):
                            continue
                        f_inp = uv_sh.GetInput("file")
                        if not f_inp:
                            continue
                        asset = f_inp.Get()
                        if asset:
                            diffuse_tex = str(asset.path)
                            break

                # Resolve relative → absolute path.
                if diffuse_tex and not Path(diffuse_tex).is_absolute():
                    resolved = (usd_dir / diffuse_tex).resolve()
                    diffuse_tex = str(resolved).replace("\\", "/") if resolved.exists() else None
                elif diffuse_tex:
                    diffuse_tex = diffuse_tex.replace("\\", "/")
                    if not Path(diffuse_tex).exists():
                        diffuse_tex = None

                # ── Read scalar PBR properties from UsdPreviewSurface ──────────
                roughness = 0.5
                metallic = 0.0
                try:
                    r_inp = preview_shader.GetInput("roughness")
                    if r_inp and not r_inp.HasConnectedSource():
                        v = r_inp.Get()
                        if v is not None:
                            roughness = max(0.0, min(float(v), 1.0))
                except Exception:
                    pass
                try:
                    m_inp = preview_shader.GetInput("metallic")
                    if m_inp and not m_inp.HasConnectedSource():
                        v = m_inp.Get()
                        if v is not None:
                            metallic = max(0.0, min(float(v), 1.0))
                except Exception:
                    pass

                # ── Create Maya PxrSurface node + shading group ────────────────
                try:
                    pxr_surf = cmds.shadingNode("PxrSurface", asShader=True, name=f"rfm_{safe}")
                    # Strip any trailing 'SG'/'sg' from safe before appending 'SG'
                    # so USD mat names like 'PxrDisneyBsdf1SG' don't become
                    # 'rfm_PxrDisneyBsdf1SGSG' — the SG suffix is added here.
                    safe_no_sg = safe[:-2] if safe.lower().endswith("sg") else safe
                    sg = cmds.sets(
                        renderable=True,
                        noSurfaceShader=True,
                        empty=True,
                        name=f"rfm_{safe_no_sg}SG",
                    )
                    cmds.connectAttr(f"{pxr_surf}.outColor", f"{sg}.surfaceShader", force=True)

                    # Specular roughness (UsdPreviewSurface roughness → PxrSurface)
                    try:
                        cmds.setAttr(f"{pxr_surf}.specularRoughness", roughness)
                    except Exception:
                        pass

                    # Metallic approximation: reduce diffuse gain for metallic surfaces.
                    if metallic > 0.1:
                        try:
                            cmds.setAttr(f"{pxr_surf}.diffuseGain", max(0.05, 1.0 - metallic))
                        except Exception:
                            pass

                    # ── Diffuse: PxrTexture node or static color ───────────────
                    if diffuse_tex:
                        pxr_tex = cmds.shadingNode(
                            "PxrTexture", asTexture=True, name=f"rfm_tex_{safe}"
                        )
                        # Set texture file path
                        try:
                            cmds.setAttr(f"{pxr_tex}.filename", diffuse_tex, type="string")
                        except Exception:
                            pass
                        # Convert sRGB → linear for physically correct shading
                        try:
                            cmds.setAttr(f"{pxr_tex}.linearize", 1)
                        except Exception:
                            pass
                        # Connect PxrTexture.resultRGB → PxrSurface.diffuseColor
                        try:
                            cmds.connectAttr(
                                f"{pxr_tex}.resultRGB", f"{pxr_surf}.diffuseColor", force=True
                            )
                            tex_count += 1
                        except Exception:
                            pass
                    else:
                        # No texture: copy static diffuseColor from UsdPreviewSurface
                        try:
                            dc_inp = preview_shader.GetInput("diffuseColor")
                            if dc_inp and not dc_inp.HasConnectedSource():
                                dc_val = dc_inp.Get()
                                if dc_val is not None:
                                    cmds.setAttr(
                                        f"{pxr_surf}.diffuseColor",
                                        float(dc_val[0]),
                                        float(dc_val[1]),
                                        float(dc_val[2]),
                                        type="double3",
                                    )
                        except Exception:
                            pass

                    mat_path_to_sg[str(mat_key)] = sg
                    created_count += 1

                except Exception as node_err:
                    self.logger.debug(
                        f"[RFM] Maya shader creation skipped for {mat_name}: {node_err}"
                    )
                    continue

            # Ensure SG.surfaceShader is bound for Hypershade visibility.
            # rfm2 relay wiring can be deferred, leaving SGs renderable but not
            # consistently visible in Hypershade until update_disney_nodes runs.
            if mat_path_to_sg:
                self._ensure_hypershade_shader_bindings(mat_path_to_sg)

            # ── Deferred post-rfm2 Hypershade registration (definitive fix) ──
            #
            # CONFIRMED PROBLEM (log analysis): executeDeferred fired BEFORE
            # rfm2's update_disney_nodes, AND the sidecar incorrectly mapped 9
            # SGs to PxrDisplace (displacement) instead of PxrDisneyBsdf.
            #
            # Fix 1 — timing: evalDeferred(lowestPriority=True) pushes our
            #   callback to the END of the deferred queue, which means it runs
            #   AFTER rfm2's update_disney_nodes (already in queue from file load).
            # Fix 2 — shader type: direct scan of ALL PxrDisneyBsdf/PxrSurface
            #   nodes, no sidecar dependency.  Surface-shader type allow-list
            #   prevents displacement/utility nodes from being wired incorrectly.
            if mat_path_to_sg:
                try:
                    _sg_snapshot: Dict[str, str] = dict(mat_path_to_sg)
                    _sgmap_snap: Optional[Path] = getattr(
                        self, "_rfm_shader_cache_sg_map_path", None
                    )
                    _log = self.logger

                    def _deferred_rfm2_hypershade_registration() -> None:
                        """Post-rfm2 Hypershade registration — runs after update_disney_nodes.

                        1. Direct scan: ALL PxrDisneyBsdf/PxrSurface in scene.
                        2. Register every one in defaultShaderList1 (Hypershade).
                        3. Repair SG.surfaceShader using live relay — surface types only.
                        """
                        try:
                            import json as _json_d

                            import maya.cmds as _cmds_d
                            import maya.mel as _mel_d

                            _surf_d: frozenset = frozenset(
                                {
                                    "PxrDisneyBsdf",
                                    "PxrSurface",
                                    "PxrLayer",
                                    "PxrLayerSurface",
                                    "PxrLayerMixer",
                                    "PxrVolume",
                                    "PxrMarschnerHair",
                                    "PxrConstant",
                                    "PxrBlack",
                                    "PxrSkin",
                                }
                            )

                            _sidecar_d: Dict[str, str] = {}
                            if _sgmap_snap and _sgmap_snap.exists():
                                try:
                                    _sidecar_d = _json_d.loads(
                                        _sgmap_snap.read_text(encoding="utf-8")
                                    )
                                except Exception:
                                    pass

                            # 1) DIRECT SCAN — no sidecar, no snapshot dependency.
                            _all_surface: list = list(
                                dict.fromkeys(
                                    (_cmds_d.ls(type="PxrDisneyBsdf") or [])
                                    + (_cmds_d.ls(type="PxrSurface") or [])
                                )
                            )
                            _reg = 0
                            _skip = 0
                            for _sh in _all_surface:
                                try:
                                    if not _cmds_d.objExists(_sh):
                                        continue
                                    _out = (
                                        _cmds_d.listConnections(
                                            f"{_sh}.message",
                                            source=False,
                                            destination=True,
                                            plugs=True,
                                        )
                                        or []
                                    )
                                    if any(_d.startswith("defaultShaderList1.") for _d in _out):
                                        _skip += 1
                                        continue
                                    _listed = False
                                    try:
                                        # Direct connectAttr — never defaultNavigation
                                        # (interactive MEL that opens Connection Editor)
                                        _cmds_d.connectAttr(
                                            f"{_sh}.message",
                                            "defaultShaderList1.shaders",
                                            nextAvailable=True,
                                        )
                                        _listed = True
                                    except Exception:
                                        pass
                                    if _listed:
                                        _reg += 1
                                except Exception:
                                    pass

                            # 2) SG.surfaceShader repair — surface types only.
                            _repaired = 0
                            _already_ok = 0
                            for _sg in dict.fromkeys(_sg_snapshot.values()):
                                try:
                                    if not _cmds_d.objExists(_sg):
                                        continue
                                    _cur = (
                                        _cmds_d.listConnections(
                                            f"{_sg}.surfaceShader",
                                            source=True,
                                            destination=False,
                                        )
                                        or []
                                    )
                                    if any(
                                        _cmds_d.objExists(_c) and _cmds_d.nodeType(_c) in _surf_d
                                        for _c in _cur
                                    ):
                                        _already_ok += 1
                                        continue

                                    _shader_found: Optional[str] = None
                                    _relay_fb: Optional[str] = None
                                    for _relay in (
                                        _cmds_d.listConnections(
                                            f"{_sg}.rman__surface",
                                            source=False,
                                            destination=True,
                                        )
                                        or []
                                    ):
                                        for _src in (
                                            _cmds_d.listConnections(
                                                _relay,
                                                source=True,
                                                destination=False,
                                            )
                                            or []
                                        ):
                                            if _src == _sg:
                                                continue
                                            try:
                                                _st = _cmds_d.nodeType(_src)
                                                if _st in _surf_d:
                                                    _shader_found = _src
                                                    break
                                                elif _st.startswith("Pxr") and _relay_fb is None:
                                                    _relay_fb = _src
                                            except Exception:
                                                pass
                                        if _shader_found:
                                            break
                                    _shader_found = _shader_found or _relay_fb

                                    if not _shader_found and _sidecar_d:
                                        _sg_lf = _sg.split(":")[-1]
                                        _raw = _sidecar_d.get(_sg) or _sidecar_d.get(_sg_lf)
                                        if _raw:
                                            _sl = str(_raw).split(":")[-1]
                                            for _cand in [_sl] + (_cmds_d.ls(f"*:{_sl}") or []):
                                                try:
                                                    if (
                                                        _cmds_d.objExists(_cand)
                                                        and _cmds_d.nodeType(_cand) in _surf_d
                                                    ):
                                                        _shader_found = _cand
                                                        break
                                                except Exception:
                                                    pass

                                    if (
                                        _shader_found
                                        and _cmds_d.objExists(_shader_found)
                                        and _cmds_d.attributeQuery(
                                            "outColor", node=_shader_found, exists=True
                                        )
                                    ):
                                        try:
                                            _cmds_d.connectAttr(
                                                f"{_shader_found}.outColor",
                                                f"{_sg}.surfaceShader",
                                                force=True,
                                            )
                                            _repaired += 1
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            _log.info(
                                f"[RFM] Deferred post-rfm2 (lowestPriority): "
                                f"{_reg} shaders added to defaultShaderList1, "
                                f"{_skip} already listed; "
                                f"SG.surfaceShader: {_already_ok} OK, {_repaired} repaired"
                            )
                        except Exception:
                            pass

                    # lowestPriority=True → END of deferred queue, AFTER
                    # rfm2's update_disney_nodes which was queued during file load.
                    cmds.evalDeferred(
                        _deferred_rfm2_hypershade_registration,
                        lowestPriority=True,
                    )
                except Exception as _defer_err:
                    self.logger.debug(
                        f"[RFM] Could not schedule deferred registration: {_defer_err}"
                    )

            if created_count == 0:
                return 0

            if not _cache_used:
                # Strategy 2 (synthetic) ran — log what was created
                tex_label = f"{tex_count} with PxrTexture" if tex_count else "static colors"
                self.logger.info(
                    f"[RFM] Created {created_count} Maya PxrSurface shaders from USD "
                    f"data ({tex_label}) \u2014 visible in Hypershade + renderable via rfm2 RIS"
                )

            # ── Bind materials to USD mesh prims + register proxy with rfm2 ──
            #
            # Three-phase approach:
            #   Phase A: Session-layer material:binding (for Hydra VP2 display)
            #   Phase B: Assign proxy shape to a PxrSurface SG (rfm2 include in RIB)
            #   Phase C: Per-prim rfm2 SG assignment via |transform|shape,/PrimPath
            #
            # Phase C is the CRITICAL render fix.  rfm2 27.2 renders a
            # mayaUsdProxyShape by walking the USD hierarchy and checking SG
            # membership on each prim.  Per-prim SG assignments are authored with
            # Maya's |transform|shape,/Prim/Path selection syntax, which maps
            # each USD mesh prim to the correct PxrDisneyBsdf SG directly in the
            # Maya DG.  rfm2 reads these assignments and emits per-mesh shading in
            # the RIB — producing correct per-mesh RIS shading in IPR and XPU.
            # Without Phase C rfm2 renders the whole proxy with one shader (Phase B).

            # ── Phase A: Session-layer material:binding for VP2 Hydra ──────────
            # Normalise mesh_bindings mat-path values to str to match the
            # str keys now stored in mat_path_to_sg (Strategy 1 or 2).
            mesh_bindings_str: dict = {str(mesh): str(mat) for mesh, mat in mesh_bindings.items()}
            bound = 0
            total_bindings = sum(1 for mk in mesh_bindings_str.values() if mk in mat_path_to_sg)
            try:
                import mayaUsd.lib as mayaUsdLib  # type: ignore[import-unresolved]

                proxy_long = cmds.ls(proxy_shape, long=True)[0]
                root_prim = mayaUsdLib.GetPrim(proxy_long)

                if root_prim and root_prim.IsValid():
                    live_stage = root_prim.GetStage()
                    session = live_stage.GetSessionLayer()
                    prev_target = live_stage.GetEditTarget()
                    live_stage.SetEditTarget(Usd.EditTarget(session))
                    try:
                        for mesh_path_str, mat_key in mesh_bindings_str.items():
                            sg = mat_path_to_sg.get(mat_key)
                            if not sg:
                                continue
                            mesh_prim = live_stage.GetPrimAtPath(mesh_path_str)
                            mat_prim = live_stage.GetPrimAtPath(mat_key)
                            if (
                                mesh_prim
                                and mesh_prim.IsValid()
                                and mat_prim
                                and mat_prim.IsValid()
                            ):
                                usd_mat = UsdShade.Material(mat_prim)
                                api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
                                # Generic binding — VP2 Hydra (UsdPreviewSurface)
                                api.Bind(usd_mat)
                                # RenderMan-specific binding — HdPrman (rfm2 V2 IPR
                                # and XPU) resolves material:binding:ri first, then
                                # reads outputs:ri:surface from the Material prim.
                                # Without this, HdPrman may fall back to the Maya
                                # SG material (Phase B = one shader for all meshes).
                                try:
                                    api.Bind(
                                        usd_mat,
                                        UsdShade.Tokens.fallbackStrength,
                                        "ri",
                                    )
                                except Exception:
                                    pass  # older USD build without render-context API
                                bound += 1
                    finally:
                        live_stage.SetEditTarget(prev_target)
            except ImportError:
                pass  # mayaUsd.lib unavailable — session bindings skipped
            except Exception as phase_a_err:
                self.logger.debug(f"[RFM] Session-layer binding: {phase_a_err}")

            if bound > 0:
                self.logger.info(
                    f"[RFM] Bound {bound}/{total_bindings} materials "
                    f"to USD mesh prims (session layer — VP2 Hydra + rfm2 HdPrman)"
                )

            # ── Phase C: Per-prim rfm2 SG assignment ─────────────────────────
            # rfm2 renders USD mesh prims by checking their Maya SG membership.
            # Maya's |transform|shape,/Prim/Path syntax selects a specific USD
            # prim inside a proxy shape — cmds.sets(forceElement) then creates
            # a proper Maya SG membership for that prim so rfm2 emits per-prim
            # RIS shading in the RIB (not just one shader for the whole proxy).
            #
            # ORDER: Phase C MUST run before Phase B (proxy still in
            # initialShadingGroup so partition doesn't block shape-level removal).
            #
            # PARTITION BYPASS: rfm2 SGs are connected to renderPartition the
            # moment they're imported from the .rig.mb cache.  renderPartition
            # marks them as "exclusive" — component-level forceElement is blocked
            # regardless of which SG the proxy shape itself is in.  Fix: for each
            # target SG, temporarily disconnect it from renderPartition, perform
            # the sub-prim forceElement, then reconnect.  Maya enforces partition
            # exclusivity only at write-time, not retroactively, so the component
            # membership survives the reconnection.

            def _assign_prim_bypass_partition(sg: str, selector: str) -> bool:
                """Assign selector to sg, bypassing renderPartition exclusivity.

                Temporarily disconnects sg from renderPartition so the set
                loses partition exclusivity, calls forceElement, then
                reconnects.  Returns True if the forceElement succeeded.

                Bug notes on earlier naive implementation:
                  1. `sg.partition` is a multi-attr (sg.partition[0], [1]…).
                     `disconnectAttr('sg.partition', dst)` fails silently
                     because the source needs the indexed form — e.g.
                     'sg.partition[0]'.  Fix: use `connections=True` in
                     listConnections which returns the actual indexed plug.
                  2. The reconnect used `renderPartition.members` which
                     does not exist on a partition node.  The correct attr
                     is `renderPartition.sets`.
                  3. `cmds.sets(sg, query=True)` does NOT enumerate USD proxy
                     prim components, so membership-count comparison always
                     returned 0.  Fix: treat absence of exception as success
                     (verified select selected something first).
                """
                # connections=True yields alternating [srcPlug, dstPlug, ...]
                # giving us the EXACT indexed plug (e.g. sg.partition[0])
                # needed for a successful disconnectAttr call.
                try:
                    _raw = (
                        cmds.listConnections(
                            f"{sg}.partition",
                            connections=True,
                            plugs=True,
                            source=False,
                            destination=True,
                        )
                        or []
                    )
                except Exception:
                    _raw = []

                _pairs: list = [(_raw[_i], _raw[_i + 1]) for _i in range(0, len(_raw) - 1, 2)]

                # Disconnect — lifts the partition's exclusivity restriction
                _disconnected: list = []
                for _src_p, _dst_p in _pairs:
                    try:
                        cmds.disconnectAttr(_src_p, _dst_p)
                        _disconnected.append((_src_p, _dst_p))
                    except Exception:
                        pass

                success = False
                try:
                    # Pass the selector string directly to cmds.sets — no
                    # intermediate cmds.select required.  With renderPartition
                    # disconnected the "Cannot add" exclusivity error should be
                    # gone; if any other error occurs, log it so the next test
                    # run exposes the exact root cause.
                    #
                    # NOTE: Maya's shadingEngine nodes cannot accept USD proxy
                    # sub-prim component selectors as set members — Maya emits
                    # a "Cannot add… set has restrictions on membership" WARNING
                    # (not an exception) and silently rejects the member.
                    # success=True here means "no exception was raised," NOT
                    # that the membership was actually created.  Phase A's
                    # USD-native material:binding + materials.usda outputs:surface
                    # is the reliable per-mesh shading path for rfm2 rendering.
                    cmds.sets(selector, edit=True, forceElement=sg)
                    success = True
                except Exception as _fe_err:
                    self.logger.warning(
                        f"[RFM][Phase-C] forceElement failed — "
                        f"sg={sg!r}  selector={selector!r}  "
                        f"→ {type(_fe_err).__name__}: {_fe_err}"
                    )
                finally:
                    # Reconnect — try to restore the original slot first
                    # (keeps the partition index stable for other tools);
                    # fall back to nextAvailable if that slot was re-taken.
                    for _src_p, _dst_p in _disconnected:
                        try:
                            cmds.connectAttr(_src_p, _dst_p, force=True)
                        except Exception:
                            try:
                                _pnode = _dst_p.split(".")[0]
                                cmds.connectAttr(
                                    _src_p,
                                    f"{_pnode}.sets",
                                    nextAvailable=True,
                                    force=True,
                                )
                            except Exception:
                                pass

                return success

            _prim_assigned = 0
            _prim_failed = 0
            _prim_rejected = 0
            _proxy_long_name: Optional[str] = None
            try:
                proxy_long = cmds.ls(proxy_shape, long=True)
                _proxy_long_name = proxy_long[0] if proxy_long else proxy_shape
                _first_prim_logged = False
                for mesh_path_str, mat_path_str in mesh_bindings_str.items():
                    _sg_for_mesh = mat_path_to_sg.get(mat_path_str)
                    if not _sg_for_mesh:
                        continue
                    if not cmds.objExists(_sg_for_mesh):
                        continue
                    # Selector: "|transform|shape,/Prim/Path"
                    _prim_selector = f"{_proxy_long_name},{mesh_path_str}"
                    if not _first_prim_logged:
                        self.logger.info(
                            f"[RFM][Phase-C] first selector: {_prim_selector!r}  "
                            f"sg={_sg_for_mesh!r}"
                        )
                        _first_prim_logged = True
                    try:
                        if _assign_prim_bypass_partition(_sg_for_mesh, _prim_selector):
                            _prim_assigned += 1
                        else:
                            _prim_rejected += 1
                    except Exception:
                        _prim_failed += 1

                if _prim_rejected > 0 or _prim_failed > 0:
                    self.logger.warning(
                        f"[RFM] Per-prim SG assignment (Phase C): "
                        f"{_prim_assigned} assigned, {_prim_rejected} rejected, "
                        f"{_prim_failed} errored — "
                        f"USD stage outputs:ri:surface provides per-mesh fallback."
                    )
                else:
                    self.logger.info(
                        f"[RFM] Per-prim SG assignment (Phase C): "
                        f"{_prim_assigned}/{len(mesh_bindings_str)} mesh prims "
                        f"assigned — rfm2 renders each USD mesh with correct shader"
                    )
            except Exception as _phase_c_err:
                self.logger.warning(f"[RFM] Phase C per-prim SG assignment failed: {_phase_c_err}")

            # ── Phase B: Assign proxy shape to PxrSurface SG for rfm2 ─────────
            # MANDATORY — rfm2's Maya translator checks SG membership on the
            # shape node.  If the shape is in `initialShadingGroup` (Lambert),
            # rfm2 never emits a RenderMan surface and the proxy renders grey.
            #
            # Phase B runs AFTER Phase C.  This is intentional:
            #   • When Phase C ran first, the proxy was in initialShadingGroup
            #     (not a render SG), so renderPartition placed no restrictions on
            #     the component-level sub-prim assignments.
            #   • Phase B now assigns the SHAPE (not components) to a render SG.
            #     Maya's SG system keeps shape-level and component-level
            #     memberships independent — the Phase C component assignments
            #     are preserved as per-prim overrides above the Phase B fallback.
            #   • rfm2 renders each mesh prim with the Phase C SG shader;
            #     prims without a Phase C assignment fall back to Phase B SG.
            proxy_assigned_sg = False
            if mat_path_to_sg:
                # Prefer a Strategy-1 (real rfm2) SG — these are the original
                # PxrDisney/PxrSurface nodes from the .rig.mb cache and are
                # always better than synthetic Strategy-2 rfm_ nodes.
                best_sg: Optional[str] = None

                # Priority 0: any Strategy-1 SG (no rfm_ prefix) — real rfm2
                # nodes imported from the .rig.mb shader cache.  This is picked
                # WITHOUT requiring _sg_has_texture to succeed, because rfm2
                # 27.2's non-standard DG wiring (SG→relay destination-direction
                # connections) makes texture detection unreliable.  A real
                # PxrDisneyBsdf SG is ALWAYS better than a synthetic rfm_ node.
                for _candidate_key, sg_candidate in mat_path_to_sg.items():
                    base_leaf = sg_candidate.split(":")[-1]
                    if not base_leaf.startswith("rfm_"):
                        best_sg = sg_candidate
                        break

                # Priority 1: textured Strategy-1 SG (upgrade Priority 0 choice
                # if _sg_has_texture now works with bidirectional BFS)
                if best_sg and not self._sg_has_texture(best_sg):
                    for _candidate_key, sg_candidate in mat_path_to_sg.items():
                        base_leaf = sg_candidate.split(":")[-1]
                        if not base_leaf.startswith("rfm_") and self._sg_has_texture(sg_candidate):
                            best_sg = sg_candidate
                            break

                # Priority 2: fallback to any textured SG (Strategy-2 synthetic)
                if not best_sg:
                    for _candidate_key, sg_candidate in mat_path_to_sg.items():
                        if self._sg_has_texture(sg_candidate):
                            best_sg = sg_candidate
                            break

                first_sg = best_sg or next(iter(mat_path_to_sg.values()))

                try:
                    # Remove from initialShadingGroup so rfm2 doesn't see Lambert
                    try:
                        cmds.sets(proxy_shape, remove="initialShadingGroup")
                    except Exception:
                        pass  # may not be a member

                    cmds.sets(proxy_shape, edit=True, forceElement=first_sg)
                    proxy_assigned_sg = True
                    _is_rfm2_sg = best_sg and not best_sg.split(":")[-1].startswith("rfm_")
                    _has_tex = best_sg and self._sg_has_texture(best_sg)
                    tex_flag = (
                        " [textured]" if _has_tex else " [rfm2-unverified]" if _is_rfm2_sg else ""
                    )
                    _phase_c_summary = (
                        f"; {_prim_assigned}/{len(mesh_bindings_str)} prims override "
                        f"via Phase C per-prim SGs"
                        if _prim_assigned > 0
                        else " (Phase C failed — all prims will use this fallback shader)"
                    )
                    self.logger.info(
                        f"[RFM] Proxy shape → {first_sg}{tex_flag} "
                        f"(fallback shader for rfm2 include-in-RIB{_phase_c_summary})"
                    )
                except Exception as sg_err:
                    self.logger.warning(f"[RFM] Could not assign proxy shape to SG: {sg_err}")

            # Restore viewport selection
            prev_sel = cmds.ls(selection=True, long=True) or []
            try:
                if prev_sel:
                    cmds.select(prev_sel, replace=True)
                else:
                    cmds.select(clear=True)
            except Exception:
                pass

            if not proxy_assigned_sg:
                self.logger.info(
                    "[RFM] PxrSurface shaders in Hypershade. "
                    "Per-mesh materials use USD outputs:ri:surface "
                    "(materials.usda). To connect to viewport rendering: "
                    "select proxy shape → RMB → Assign Existing Material."
                )

            # ── FIX 8: Auto-switch viewport renderer to mayaHydra HdPrman ─────
            # NOTE: As of the Render-Ready Native Import pivot, this code path
            # is only useful on installs that ship a newer mayaHydra (MayaUSD
            # ≥ 0.37) which actually exposes HdPrman as a Maya viewport
            # renderer.  On the bundled MayaUSD 0.35 + mayaHydra 0.7.3 it will
            # always log "No HdPrman renderer plugin registered" because that
            # mayaHydra build only registers `mayaHydraRenderOverride` (Storm).
            # Render-Ready Native Import (called from `_import_with_mayausd`
            # right after this method returns) is the actual fix for grey
            # IPR — this Fix 8 call is left in as a forward-compatible no-op.
            self._enable_hydra_render_for_usd_proxy(proxy_shape)

            return created_count

        except Exception as e:
            self.logger.warning(f"[RFM] Maya shader creation failed: {e}")
            self.logger.debug(traceback.format_exc())
            return 0

    def _enable_hydra_render_for_usd_proxy(self, proxy_shape: str) -> None:
        """Switch active model panels to mayaHydra HdPrman renderer.

        RfM 27.2's RIB-based `it` IPR has no translator for
        `mayaUsdProxyShape` (verified via `mayaTranslation.json` registry
        scan), so it renders proxy meshes as flat grey.  The Hydra Render
        Delegate path (mayaHydra + HdPrman) walks the USD stage natively and
        honors `material:binding` per-prim, which is what we author in
        Phase A and Fix 7.

        This method tries to switch each model panel's viewport renderer to
        an HdPrman delegate.  It is fully reversible — the user can revert
        any time via the panel's Renderer menu.  Failures are logged but
        never raised, since this is a render-quality enhancement and must
        not break the import pipeline.

        Args:
            proxy_shape: Long DAG path to the `mayaUsdProxyShape` (only used
                for diagnostic logging).
        """
        if cmds is None:
            return

        try:
            # ── FIX 9: Auto-load the mayaHydra Maya plugin first ──────────
            # Without it, Maya only registers `vp2Renderer` + basic OpenGL
            # renderers and there is no HdPrman delegate to switch to —
            # exactly what the previous test caught:
            #   Available renderers: ['vp2Renderer', 'base_OpenGL_Renderer',
            #     'hwRender_OpenGL_Renderer', 'stub_Renderer']
            # The plugin ships with MayaUSD (`mayaHydra.mll` under MAYAHYDRA
            # 0.7.3 module).  Loading is idempotent and reversible.
            try:
                if not cmds.pluginInfo("mayaHydra", q=True, loaded=True):
                    cmds.loadPlugin("mayaHydra", quiet=True)
                    self.logger.info(
                        "[RFM][FIX8] Loaded mayaHydra plugin so HdPrman "
                        "viewport renderer registers."
                    )
            except Exception as plugin_err:
                self.logger.warning(
                    f"[RFM][FIX8] Could not load mayaHydra plugin: {plugin_err}. "
                    "Per-mesh USD bindings will not appear in RfM IPR. "
                    "Install MayaUSD's MAYAHYDRA module or load 'mayaHydra' "
                    "via Window → Settings/Preferences → Plug-in Manager."
                )
                # Continue — modelEditor query below will report what IS
                # available so the diagnostic message is still useful.

            # Discover renderer plugins that mayaHydra registered.  In
            # Maya 2026 + mayaHydra 0.7.3 the typical names are:
            #   - "HdStormRendererPlugin"        (Hydra Storm — VP2 fallback)
            #   - "HdPrmanLoaderRendererPlugin"  (HdPrman CPU/GPU loader)
            #   - "HdPrmanXpuLoaderRendererPlugin"
            #   - "HdPrmanXpuCpuLoaderRendererPlugin"
            #   - "HdPrmanXpuGpuLoaderRendererPlugin"
            panels = cmds.getPanel(type="modelPanel") or []
            if not panels:
                self.logger.info(
                    "[RFM][FIX8] No modelPanel found; skipping Hydra renderer switch."
                )
                return

            # Use the first model panel to enumerate available renderers.
            # All panels share the same renderer plugin registry.
            sample_panel = panels[0]
            available: List[str] = list(
                cmds.modelEditor(sample_panel, q=True, rendererList=True) or []
            )
            self.logger.debug(f"[RFM][FIX8] Available viewport renderers: {available}")

            # Prefer XPU GPU > XPU CPU > XPU loader > RIS loader.  Storm is
            # the explicit fallback the user already gets in VP2 — switching
            # to Storm would be a no-op for RfM IPR purposes.
            preferred_order = [
                "HdPrmanXpuGpuLoaderRendererPlugin",
                "HdPrmanXpuLoaderRendererPlugin",
                "HdPrmanXpuCpuLoaderRendererPlugin",
                "HdPrmanLoaderRendererPlugin",
            ]
            chosen: Optional[str] = next(
                (name for name in preferred_order if name in available), None
            )

            if chosen is None:
                self.logger.warning(
                    "[RFM][FIX8] No HdPrman renderer plugin registered. "
                    "mayaHydra may not be loaded, or RfM 27.2's HdPrman "
                    "loader plug-ins are not on PXR_PLUGINPATH_NAME. "
                    f"Available renderers: {available}. "
                    "Per-mesh USD bindings will not appear in RfM IPR until "
                    "mayaHydra+HdPrman is enabled."
                )
                return

            switched = 0
            for panel in panels:
                try:
                    current = cmds.modelEditor(panel, q=True, rendererName=True)
                    if current == chosen:
                        switched += 1
                        continue
                    cmds.modelEditor(panel, edit=True, rendererName=chosen)
                    switched += 1
                except Exception as panel_err:
                    self.logger.debug(
                        f"[RFM][FIX8] Panel {panel} renderer switch failed: {panel_err}"
                    )

            self.logger.info(
                f"[RFM][FIX8] Switched {switched}/{len(panels)} model panel(s) to "
                f"'{chosen}' so the Hydra Render Delegate honors USD "
                f"material:binding on the proxy shape ({proxy_shape}). "
                f"Use Renderer menu in any viewport to revert."
            )
        except Exception as fix8_err:
            self.logger.warning(f"[RFM][FIX8] Hydra renderer auto-switch failed: {fix8_err}")
            self.logger.debug(traceback.format_exc())

    # ─────────────────────────────────────────────────────────────────────────
    # Render-Ready Native Import (architectural pivot)
    # ─────────────────────────────────────────────────────────────────────────
    def _render_ready_native_import(
        self,
        usd_path: Path,
        proxy_transform: str,
        mesh_bindings: Dict[str, str],
        mat_path_to_sg: Dict[str, str],
    ) -> int:
        """Import USD geometry as native Maya meshes and assign existing SGs.

        WHY THIS EXISTS:
            RfM 27.2 has no translator entry for ``mayaUsdProxyShape`` (verified
            via ``config/mayaTranslation.json`` — 51 entries, none matching the
            proxy type), and the bundled mayaHydra 0.7.3 only exposes the
            Hydra Storm rasterizer in the viewport — not HdPrman.  Neither
            path can deliver per-mesh PxrDisneyBsdf shading in IPR or batch.

            This method bypasses both limitations by importing the USD content
            as **native Maya polygon meshes** via ``mayaUSDImport`` (with
            ``shadingMode=none`` so we keep the original PxrDisneyBsdf SGs
            already imported from the .rig.mb cache) and then assigning each
            native mesh shape to its correct SG using the
            ``mesh_bindings → mat_path_to_sg`` map produced by
            ``_create_rfm_maya_shaders``.  The proxy is hidden by default so
            the renderer sees only native geometry; toggle it back on for live
            USD animation/layout.

        Args:
            usd_path: Path to the composed root .usda the proxy was loaded from.
            proxy_transform: Maya transform above the ``mayaUsdProxyShape``,
                used to derive a unique namespace and to hide the proxy.
            mesh_bindings: ``{usd_mesh_prim_path: usd_material_prim_path}``
                from the USD stage traversal.
            mat_path_to_sg: ``{usd_material_prim_path: maya_SG_name}`` from
                the .rig.mb shader cache import.

        Returns:
            Number of native Maya meshes successfully assigned to a SG.
        """
        if cmds is None:
            return 0
        if not mesh_bindings or not mat_path_to_sg:
            self.logger.info(
                "[RR] Skipping Render-Ready Native Import — no mesh→SG map available."
            )
            return 0

        # ── Snapshot scene state so we can identify newly-imported nodes ─────
        meshes_before: set = set(cmds.ls(type="mesh", long=True) or [])

        # Use a unique namespace to keep render-ready nodes isolated from the
        # original .rig.mb-loaded controllers and the proxy.
        ns_base = proxy_transform.replace("|", "").replace(":", "_") + "_RR"
        ns = ns_base
        suffix = 1
        try:
            while cmds.namespace(exists=ns):
                suffix += 1
                ns = f"{ns_base}{suffix}"
        except Exception:
            ns = ns_base

        usd_path_fwd = str(usd_path).replace("\\", "/")

        # ── Pre-scan stage: build excludePrimPath for non-mesh content ───────
        # The composed USD stage contains NurbsCurves prims authored by
        # `_write_nurbs_controllers_to_usd` (i.e., the .rig.mb rig controllers
        # round-tripped into USD), plus Skeletons, Cameras and Lights.  Without
        # filtering, mayaUSDImport pulls ALL of them into the Maya scene as
        # native nurbsCurve / joint / camera / light nodes — duplicating the
        # controllers that the .rig.mb cache already provides and polluting
        # the outliner.  We restrict the import to mesh subtrees only.
        exclude_paths: List[str] = []
        if USD_AVAILABLE:
            try:
                _stage = Usd.Stage.Open(str(usd_path))
                if _stage:
                    _exclude_types = {
                        "NurbsCurves",
                        "BasisCurves",
                        "Skeleton",
                        "SkelAnimation",
                        "Camera",
                        "DistantLight",
                        "RectLight",
                        "SphereLight",
                        "DiskLight",
                        "DomeLight",
                        "CylinderLight",
                        "GeometryLight",
                    }
                    for _prim in _stage.Traverse():
                        if _prim.GetTypeName() in _exclude_types:
                            exclude_paths.append(str(_prim.GetPath()))
            except Exception as scan_err:
                self.logger.debug(f"[RR] excludePrimPath scan failed: {scan_err}")

        if exclude_paths:
            self.logger.info(
                f"[RR] Excluding {len(exclude_paths)} non-mesh prim(s) from "
                f"native import (NurbsCurves/Skeleton/Camera/Light)."
            )

        # ── Native USD geometry import (no shading networks created) ─────────
        # shadingMode=("none","default") tells mayaUSDImport NOT to build any
        # Maya shading network — the existing PxrDisneyBsdf SGs (already in
        # Hypershade from the .rig.mb cache) are what we will assign next.
        try:
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)
        except Exception:
            pass

        # ── Snapshot scene state for ALL geometry types so post-import sweep
        # can identify and delete any non-mesh nodes that slipped past
        # excludePrimPath (defense in depth).
        curves_before: set = set(cmds.ls(type="nurbsCurve", long=True) or [])
        joints_before: set = set(cmds.ls(type="joint", long=True) or [])
        cams_before: set = set(cmds.ls(type="camera", long=True) or [])
        lights_before: set = set(cmds.ls(type="light", long=True) or [])

        try:
            import_kwargs: Dict[str, Any] = dict(
                file=usd_path_fwd,
                primPath="/",
                shadingMode=[("none", "default")],
                readAnimData=False,
                useAsAnimationCache=False,
                importInstances=False,
            )
            if exclude_paths:
                import_kwargs["excludePrimPath"] = ",".join(exclude_paths)
            try:
                imported_roots = cmds.mayaUSDImport(**import_kwargs)
            except (TypeError, RuntimeError) as flag_err:
                # MayaUSD 0.35.0 (Maya 2026) does NOT expose excludePrimPath
                # on the mayaUSDImport command (verified on user's install:
                # "Invalid flag 'excludePrimPath'").  Retry without that flag
                # and rely on the post-import sweep below to delete
                # NurbsCurves / joints / cameras / lights.
                if "excludePrimPath" in str(flag_err) and exclude_paths:
                    self.logger.info(
                        "[RR] mayaUSDImport does not support excludePrimPath in "
                        "this MayaUSD build; importing full stage and relying "
                        "on post-import non-mesh sweep instead."
                    )
                    import_kwargs.pop("excludePrimPath", None)
                    imported_roots = cmds.mayaUSDImport(**import_kwargs)
                else:
                    raise
        except Exception as imp_err:
            self.logger.warning(
                f"[RR] mayaUSDImport failed: {imp_err}. "
                f"Per-mesh native render path is unavailable."
            )
            return 0

        # ── Sweep: delete any non-mesh DAG nodes that slipped through ────────
        def _delete_new(node_type: str, before: set) -> int:
            after = set(cmds.ls(type=node_type, long=True) or [])
            new_nodes = sorted(after - before)
            removed = 0
            for n in new_nodes:
                try:
                    parents = cmds.listRelatives(n, parent=True, fullPath=True) or []
                    target = parents[0] if parents else n
                    if cmds.objExists(target):
                        cmds.delete(target)
                        removed += 1
                except Exception:
                    pass
            return removed

        swept_curves = _delete_new("nurbsCurve", curves_before)
        swept_joints = _delete_new("joint", joints_before)
        swept_cams = _delete_new("camera", cams_before)
        swept_lights = _delete_new("light", lights_before)
        if swept_curves or swept_joints or swept_cams or swept_lights:
            self.logger.info(
                f"[RR] Post-import sweep removed: "
                f"{swept_curves} curve(s), {swept_joints} joint(s), "
                f"{swept_cams} camera(s), {swept_lights} light(s)."
            )

        # ── Find new mesh shapes and build a USD-prim-path → Maya-shape map ──
        meshes_after: set = set(cmds.ls(type="mesh", long=True) or [])
        new_mesh_shapes = sorted(meshes_after - meshes_before)
        if not new_mesh_shapes:
            self.logger.warning(
                "[RR] mayaUSDImport returned no new meshes. " f"Imported roots: {imported_roots}"
            )
            return 0

        self.logger.info(
            f"[RR] mayaUSDImport created {len(new_mesh_shapes)} native Maya mesh "
            f"shape(s) from USD geometry (no shading networks generated)."
        )

        # Build a quick "tail of DAG path → shape" lookup so we can match USD
        # prim paths (e.g., "/Veteran/Geom/body_geo") to Maya shapes regardless
        # of namespace prefix.  We compare on the joined non-namespaced suffix.
        def _strip_ns(name: str) -> str:
            # "ns:body_geo" → "body_geo"
            return name.rsplit(":", 1)[-1]

        def _maya_path_tail(long_path: str) -> str:
            # "|RR_ns:Veteran|RR_ns:Geom|RR_ns:body_geo|RR_ns:body_geoShape"
            #   → "Veteran/Geom/body_geo"
            parts = [p for p in long_path.split("|") if p]
            if not parts:
                return ""
            # drop the final "Shape" segment so we compare transform-level paths
            transform_parts = parts[:-1] if len(parts) > 1 else parts
            return "/".join(_strip_ns(p) for p in transform_parts)

        tail_to_shape: Dict[str, str] = {}
        for shape in new_mesh_shapes:
            tail = _maya_path_tail(shape)
            if tail:
                # Last writer wins; in practice tails are unique within an import
                tail_to_shape[tail] = shape

        # ── Assign existing Maya SGs to native meshes per USD bindings ───────
        # Strategy: try `cmds.sets(forceElement)` first; that is the canonical
        # API but silently emits "None of the items can be added to the set"
        # warnings without raising when the shape is intermediate or already
        # in another shading-engine set with restrictions.  We therefore READ
        # BACK the connection on `<shape>.instObjGroups[0]` to confirm; on
        # failure we retry with `cmds.hyperShade(assign=)` against the parent
        # transform (which Maya routes through the non-intermediate shape) and
        # verify again.  Only shapes whose surface SG is verifiably the target
        # SG count toward the `assigned` total.
        assigned = 0
        unmatched_usd: List[str] = []
        unmatched_mat: List[str] = []
        verify_failures: List[str] = []

        def _shape_sg(shape_path: str) -> Optional[str]:
            try:
                conns = (
                    cmds.listConnections(
                        f"{shape_path}.instObjGroups[0]",
                        source=False,
                        destination=True,
                        type="shadingEngine",
                    )
                    or []
                )
                return conns[0] if conns else None
            except Exception:
                return None

        for usd_mesh_path, usd_mat_path in mesh_bindings.items():
            sg_name = mat_path_to_sg.get(usd_mat_path)
            if not sg_name or not cmds.objExists(sg_name):
                unmatched_mat.append(f"{usd_mesh_path} → {usd_mat_path}")
                continue

            usd_tail = usd_mesh_path.lstrip("/")
            shape = tail_to_shape.get(usd_tail)
            if shape is None:
                leaf = usd_tail.rsplit("/", 1)[-1]
                candidates = [
                    s for t, s in tail_to_shape.items() if t.endswith("/" + leaf) or t == leaf
                ]
                if len(candidates) == 1:
                    shape = candidates[0]
            if shape is None:
                unmatched_usd.append(usd_mesh_path)
                continue

            # Skip intermediate object shapes — Maya never renders or assigns
            # shaders to them; we want the deformed/visible shape sibling.
            try:
                if cmds.getAttr(f"{shape}.intermediateObject"):
                    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
                    if parents:
                        sibs = (
                            cmds.listRelatives(
                                parents[0], shapes=True, fullPath=True, noIntermediate=True
                            )
                            or []
                        )
                        sibs = [s for s in sibs if cmds.objectType(s) == "mesh"]
                        if sibs:
                            shape = sibs[0]
            except Exception:
                pass

            transform_parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            transform = transform_parents[0] if transform_parents else None

            # Attempt 1: cmds.sets forceElement
            try:
                cmds.sets(shape, edit=True, forceElement=sg_name)
            except Exception:
                pass

            if _shape_sg(shape) == sg_name:
                assigned += 1
                continue

            # Attempt 2: hyperShade(assign=) on the transform
            if transform:
                try:
                    prev_sel = cmds.ls(selection=True, long=True) or []
                    cmds.select(transform, replace=True)
                    cmds.hyperShade(assign=sg_name)
                    if prev_sel:
                        cmds.select(prev_sel, replace=True)
                    else:
                        cmds.select(clear=True)
                except Exception:
                    pass

            if _shape_sg(shape) == sg_name:
                assigned += 1
                continue

            verify_failures.append(f"{shape} → {sg_name}")

        self.logger.info(
            f"[RR] Verified SG bindings: {assigned}/{len(mesh_bindings)} native "
            f"meshes confirmed connected to their original RfM PxrDisneyBsdf SG "
            f"(via instObjGroups[0]→shadingEngine read-back)."
        )
        if verify_failures:
            self.logger.warning(
                f"[RR] {len(verify_failures)} native mesh(es) did not bind to their "
                f"target SG even after hyperShade fallback. First 5: "
                f"{verify_failures[:5]}"
            )
        if unmatched_usd:
            self.logger.warning(
                f"[RR] {len(unmatched_usd)} USD mesh prim(s) had no matching native "
                f"Maya shape after import. First 5: {unmatched_usd[:5]}"
            )
        if unmatched_mat:
            self.logger.warning(
                f"[RR] {len(unmatched_mat)} USD mesh binding(s) had no SG in the "
                f"shader cache. First 5: {unmatched_mat[:5]}"
            )

        return assigned

    def _ensure_hypershade_shader_bindings(self, mat_path_to_sg: Dict[str, str]) -> None:
        """Ensure each mapped SG has a direct Pxr source on surfaceShader.

        This keeps imported RenderMan materials visible in Hypershade even when
        relay links are still being rebuilt by deferred rfm2 scene-updater work.
        """
        if cmds is None:
            return

        import json as _json_hs

        # Strategy-0 sidecar map captured during export while rfm2 relay
        # connections were guaranteed live.
        _sidecar_map: Dict[str, str] = {}
        _sgmap_path: Optional[Path] = getattr(self, "_rfm_shader_cache_sg_map_path", None)
        if _sgmap_path and _sgmap_path.exists():
            try:
                _raw = _json_hs.loads(_sgmap_path.read_text(encoding="utf-8"))
                if isinstance(_raw, dict):
                    _sidecar_map = {
                        str(_k): str(_v)
                        for _k, _v in _raw.items()
                        if isinstance(_k, str) and isinstance(_v, str)
                    }
            except Exception:
                _sidecar_map = {}

        def _resolve_shader_node(_shader_leaf: str, _sg_name: str) -> Optional[str]:
            """Resolve a Pxr SURFACE shader by leaf name, favoring SG namespace locality.

            Only accepts surface shader types — displacement/utility nodes excluded.
            """
            _surf_types: frozenset = frozenset(
                {
                    "PxrDisneyBsdf",
                    "PxrSurface",
                    "PxrLayer",
                    "PxrLayerSurface",
                    "PxrLayerMixer",
                    "PxrVolume",
                    "PxrMarschnerHair",
                    "PxrConstant",
                    "PxrBlack",
                    "PxrSkin",
                }
            )
            if not _shader_leaf:
                return None
            _candidates: List[str] = []
            _sg_ns = ":".join(_sg_name.split(":")[:-1])
            if _sg_ns:
                _candidates.append(f"{_sg_ns}:{_shader_leaf}")
            _candidates.append(_shader_leaf)
            _candidates.extend(cmds.ls(f"*:{_shader_leaf}") or [])

            for _cand in dict.fromkeys(_candidates):
                try:
                    if cmds.objExists(_cand) and cmds.nodeType(_cand) in _surf_types:
                        return _cand
                except Exception:
                    pass
            return None

        def _register_shader_in_default_list(_shader: str) -> bool:
            """Ensure shader.message is connected to defaultShaderList1."""
            try:
                if not cmds.objExists(_shader):
                    return False
                if not cmds.objExists("defaultShaderList1"):
                    return False

                _msg_out = (
                    cmds.listConnections(
                        f"{_shader}.message",
                        source=False,
                        destination=True,
                        plugs=True,
                    )
                    or []
                )
                if any(_dst.startswith("defaultShaderList1.") for _dst in _msg_out):
                    return True

                # Direct connectAttr only — defaultNavigation is an interactive
                # MEL command that calls connectWindowWith and opens the Connection
                # Editor when connection classification is ambiguous.
                for _dst_attr in ("defaultShaderList1.shaders", "defaultShaderList1.s"):
                    try:
                        cmds.connectAttr(
                            f"{_shader}.message",
                            _dst_attr,
                            nextAvailable=True,
                            force=True,
                        )
                    except Exception:
                        pass

                _msg_out = (
                    cmds.listConnections(
                        f"{_shader}.message",
                        source=False,
                        destination=True,
                        plugs=True,
                    )
                    or []
                )
                return any(_dst.startswith("defaultShaderList1.") for _dst in _msg_out)
            except Exception:
                return False

        def _find_pxr_shader_for_sg(_sg_name: str) -> Optional[str]:
            # Surface shader types — displacement/utility are explicitly excluded.
            _surf_types: frozenset = frozenset(
                {
                    "PxrDisneyBsdf",
                    "PxrSurface",
                    "PxrLayer",
                    "PxrLayerSurface",
                    "PxrLayerMixer",
                    "PxrVolume",
                    "PxrMarschnerHair",
                    "PxrConstant",
                    "PxrBlack",
                    "PxrSkin",
                }
            )

            # Strategy 0: sidecar SG->shader mapping (most reliable).
            # _resolve_shader_node already filters to surface shader types only.
            _sg_leaf = _sg_name.split(":")[-1]
            for _key in (_sg_name, _sg_leaf):
                _shader_name = _sidecar_map.get(_key)
                if not _shader_name:
                    continue
                _shader_leaf = _shader_name.split(":")[-1]
                _resolved = _resolve_shader_node(_shader_leaf, _sg_name)
                if _resolved:
                    return _resolved

            # Direct Maya surfaceShader connection — filter to surface types.
            try:
                for _n in (
                    cmds.listConnections(
                        f"{_sg_name}.surfaceShader",
                        source=True,
                        destination=False,
                        plugs=False,
                    )
                    or []
                ):
                    try:
                        if cmds.nodeType(_n) in _surf_types:
                            return _n
                    except Exception:
                        pass
            except Exception:
                pass

            # rfm2 relay path: SG.rman__surface -> relay <- Pxr* SURFACE
            # Prefer surface shader types — relay nodes have both surface AND
            # displacement shaders as sources; we must take the surface one.
            try:
                _relay_best: Optional[str] = None
                _relay_fallback: Optional[str] = None
                for _relay in set(
                    cmds.listConnections(
                        f"{_sg_name}.rman__surface",
                        source=False,
                        destination=True,
                        plugs=False,
                    )
                    or []
                ):
                    for _src in (
                        cmds.listConnections(
                            _relay,
                            source=True,
                            destination=False,
                            plugs=False,
                        )
                        or []
                    ):
                        if _src == _sg_name:
                            continue
                        try:
                            if cmds.ls(_src, dagObjects=True):
                                continue
                            _st = cmds.nodeType(_src)
                            if _st in _surf_types:
                                _relay_best = _src
                                break
                            elif _st.startswith("Pxr") and _relay_fallback is None:
                                _relay_fallback = _src
                        except Exception:
                            pass
                    if _relay_best:
                        break
                if _relay_best or _relay_fallback:
                    return _relay_best or _relay_fallback
            except Exception:
                pass

            # Name-derived fallback: SG name without SG suffix.
            try:
                _leaf = _sg_name.split(":")[-1]
                _base = _leaf
                for _sfx in ("_SG", "SG"):
                    if _leaf.endswith(_sfx):
                        _base = _leaf[: -len(_sfx)]
                        break
                for _stype in ("PxrDisneyBsdf", "PxrSurface", "PxrLayer"):
                    for _cand in cmds.ls(type=_stype) or []:
                        if _cand.split(":")[-1] == _base:
                            return _cand
            except Exception:
                pass

            return None

        already_bound = 0
        repaired = 0
        unresolved = 0
        already_listed = 0
        newly_listed = 0

        for _sg_name in dict.fromkeys(mat_path_to_sg.values()):
            try:
                if not cmds.objExists(_sg_name):
                    unresolved += 1
                    continue

                _incoming = (
                    cmds.listConnections(
                        f"{_sg_name}.surfaceShader",
                        source=True,
                        destination=False,
                        plugs=False,
                    )
                    or []
                )
                _has_pxr_incoming = False
                for _n in _incoming:
                    try:
                        if cmds.objExists(_n) and cmds.nodeType(_n).startswith("Pxr"):
                            _has_pxr_incoming = True
                            break
                    except Exception:
                        pass

                if _has_pxr_incoming:
                    for _n in _incoming:
                        try:
                            if cmds.objExists(_n) and cmds.nodeType(_n).startswith("Pxr"):
                                if _register_shader_in_default_list(_n):
                                    _post = (
                                        cmds.listConnections(
                                            f"{_n}.message",
                                            source=False,
                                            destination=True,
                                            plugs=True,
                                        )
                                        or []
                                    )
                                    if any(_d.startswith("defaultShaderList1.") for _d in _post):
                                        already_listed += 1
                                break
                        except Exception:
                            pass
                    already_bound += 1
                    continue

                _shader = _find_pxr_shader_for_sg(_sg_name)
                if not _shader:
                    unresolved += 1
                    continue
                if not cmds.attributeQuery("outColor", node=_shader, exists=True):
                    unresolved += 1
                    continue

                cmds.connectAttr(
                    f"{_shader}.outColor",
                    f"{_sg_name}.surfaceShader",
                    force=True,
                )
                if _register_shader_in_default_list(_shader):
                    newly_listed += 1
                repaired += 1
            except Exception:
                unresolved += 1

        self.logger.info(
            f"[RFM] Hypershade SG bindings: {already_bound} already bound, "
            f"{repaired} repaired, {unresolved} unresolved"
        )
        self.logger.info(
            f"[RFM] Hypershade shader-list registration: "
            f"{already_listed} already listed, {newly_listed} registered"
        )

    def _rewrite_materials_usda_with_disney_networks(
        self,
        usd_path: Path,
        mat_path_to_sg: dict,
        mesh_bindings: Optional[dict] = None,
    ) -> None:
        """Overwrite the PxrPreviewSurface placeholders in materials.usda with
        real RIS shader networks read directly from the Maya DG.

        ``_populate_rfm_materials_sublayer`` runs during stage construction
        (before the .rig.mb is loaded) and writes ``PxrPreviewSurface`` USD
        specs into materials.usda — the only shader data available from the
        base USDC at that point.

        This method is called *after* ``_import_rfm_shaders_from_cache`` has
        loaded the real ``PxrDisneyBsdf`` / ``PxrSurface`` SGs into the Maya
        scene.  It reads each shader's parameter values and upstream
        ``PxrTexture`` / ``PxrNormalMap`` connections from the live Maya DG and
        writes them as proper USD RIS shader specs, replacing the per-material
        ``PxrPreviewSurface`` child prims.

        After saving, it calls ``Sdf.Layer.Reload()`` so the live MayaUSD stage
        picks up the new specs without requiring a scene reload.

        Materials NOT present in *mat_path_to_sg* (Strategy-2 synthetics) are
        left unchanged — their ``PxrPreviewSurface`` fallback is still valid.

        Args:
            usd_path: Path to the composed root ``.usda`` (or base ``.usdc``).
            mat_path_to_sg: ``{USD mat path str → Maya SG name}`` mapping
                produced by ``_import_rfm_shaders_from_cache``.
        """
        if not USD_AVAILABLE or cmds is None:
            return

        # Resolve the .materials.usda sibling path
        asset_stem = usd_path.stem  # e.g. 'Veteran_Rig.root' or 'Veteran_Rig'
        if asset_stem.endswith(".root"):
            asset_stem = asset_stem[:-5]
        mat_usda_path = usd_path.parent / f"{asset_stem}.materials.usda"
        if not mat_usda_path.exists():
            self.logger.warning(
                f"[RFM] materials.usda not found at {mat_usda_path} — "
                f"PxrDisneyBsdf rewrite skipped"
            )
            return

        try:
            # Open the in-memory Sdf layer (avoids a second file-open)
            mat_layer = Sdf.Layer.Find(str(mat_usda_path))
            if mat_layer is None:
                mat_layer = Sdf.Layer.FindOrOpen(str(mat_usda_path))
            if mat_layer is None:
                self.logger.warning(
                    "[RFM] Could not open materials.usda Sdf layer for Disney rewrite"
                )
                return

            # Open a transient stage rooted at the materials layer so we can
            # use Usd.Stage.RemovePrim / DefinePrim against it directly.
            mat_stage = Usd.Stage.Open(mat_layer)

            # Texture node types whose outputs we'll re-wire into USD
            _TEX_TYPES: frozenset = frozenset(
                ("PxrTexture", "PxrNormalMap", "PxrManifold2D", "PxrManifoldFile")
            )

            disney_written = 0
            fallback_kept = 0

            # ── Load SG→shader sidecar written at export time ─────────────────
            # _export_rfm_shaders_from_reference captures the ground-truth
            # SG→PxrDisneyBsdf mapping while relay connections are definitively
            # live.  Loading it once here lets Strategy 0 (below) skip all
            # topology traversal for every matched SG.
            import json as _json_r

            _sg_shader_sidecar: dict = {}
            _sidecar_r = getattr(self, "_rfm_shader_cache_sg_map_path", None)
            if _sidecar_r:
                try:
                    _sidecar_r_path = Path(_sidecar_r)
                    if _sidecar_r_path.exists():
                        _sg_shader_sidecar = _json_r.loads(
                            _sidecar_r_path.read_text(encoding="utf-8")
                        )
                        self.logger.info(
                            f"[RFM] Loaded SG\u2192shader sidecar: "
                            f"{len(_sg_shader_sidecar)} entries"
                        )
                except Exception as _sc_err:
                    self.logger.warning(f"[RFM] Sidecar load failed: {_sc_err}")

            for mat_path_str, sg_name in mat_path_to_sg.items():
                mat_prim_path = Sdf.Path(mat_path_str)

                # ── Get the surface shader connected to this SG ──────────────
                # rfm2 27.2 relay topology:
                #   SG.rman__surface → relay.message   (SG is SOURCE → relay is DEST)
                #   PxrDisneyBsdf.out → relay.someAttr (PxrDisney is SOURCE → relay DEST)
                # The standard Maya surfaceShader attribute is NEVER wired by rfm2 27.x.
                # Must traverse via: SG.rman__surface → relay → filter sources → Pxr*
                maya_shader: Optional[str] = None

                # Strategy 0: ground-truth sidecar lookup (fastest, most reliable)
                # Written by _export_rfm_shaders_from_reference while the relay
                # was live — no topology guessing required.
                _sg_leaf_0 = sg_name.split(":")[-1]
                _sidecar_keys = [sg_name, _sg_leaf_0]
                _shader_candidates: List[str] = []
                _sg_ns = ":".join(sg_name.split(":")[:-1])
                for _sk in _sidecar_keys:
                    if _sk not in _sg_shader_sidecar:
                        continue
                    _raw_shader = _sg_shader_sidecar[_sk]
                    if not isinstance(_raw_shader, str):
                        continue
                    _shader_candidates.append(_raw_shader)
                    _raw_leaf = _raw_shader.split(":")[-1]
                    if _sg_ns:
                        _shader_candidates.append(f"{_sg_ns}:{_raw_leaf}")
                    _shader_candidates.extend(cmds.ls(f"*:{_raw_leaf}") or [])

                for _cand_0 in dict.fromkeys(_shader_candidates):
                    try:
                        if cmds.objExists(_cand_0) and cmds.nodeType(_cand_0).startswith("Pxr"):
                            maya_shader = _cand_0
                            break
                    except Exception:
                        pass

                # Strategy A: rfm2 relay topology
                if not maya_shader:
                    try:
                        relay_list = (
                            cmds.listConnections(
                                f"{sg_name}.rman__surface",
                                source=False,
                                destination=True,
                                plugs=False,
                            )
                            or []
                        )
                        for relay in set(relay_list):
                            try:
                                for src in (
                                    cmds.listConnections(
                                        relay,
                                        source=True,
                                        destination=False,
                                        plugs=False,
                                    )
                                    or []
                                ):
                                    if src == sg_name:
                                        continue
                                    try:
                                        if cmds.ls(src, dagObjects=True):
                                            continue
                                        src_type = cmds.nodeType(src)
                                        if src_type.startswith("Pxr"):
                                            maya_shader = src
                                            break
                                    except Exception:
                                        pass
                                if maya_shader:
                                    break
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Strategy B: standard Maya surfaceShader attribute (non-rfm2 rigs /
                # rfm1 legacy connections that wired directly to SG.surfaceShader)
                if not maya_shader:
                    for _attr in ("surfaceShader", "rman__surface"):
                        try:
                            for s in (
                                cmds.listConnections(
                                    f"{sg_name}.{_attr}",
                                    source=True,
                                    destination=False,
                                    plugs=False,
                                )
                                or []
                            ):
                                try:
                                    if cmds.nodeType(s).startswith("Pxr"):
                                        maya_shader = s
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        if maya_shader:
                            break

                # Strategy D: type-enumeration with leaf-name matching.
                # Called before BFS because it is O(N_shaders) and doesn't
                # rely on relay connections being established.  Matches the
                # rfm2 naming convention where the ShadingEngine is named
                # after its shader node: 'PxrDisneyBsdf18SG' → 'PxrDisneyBsdf18'.
                if not maya_shader:
                    _sg_leaf_d = sg_name.split(":")[-1]
                    for _sfx_d in ("_SG", "SG"):
                        if _sg_leaf_d.endswith(_sfx_d):
                            _shader_base_d = _sg_leaf_d[: -len(_sfx_d)]
                            for _stype_d in ("PxrDisneyBsdf", "PxrSurface", "PxrLayer"):
                                for _cand_d in cmds.ls(type=_stype_d) or []:
                                    if _cand_d.split(":")[-1] == _shader_base_d:
                                        maya_shader = _cand_d
                                        break
                                if maya_shader:
                                    break
                            break

                # Strategy C: bidirectional BFS safety net (covers unusual topologies
                # and artist-named SGs where the name convention doesn't apply).
                # NOTE: _bfs_vis is NOT pre-filled from the initial neighbour list —
                # pre-filling consumes the entire 400-node cap budget if the SG has
                # 60+ geometry dagSetMembers connections, preventing deeper traversal.
                if not maya_shader:
                    try:
                        _bfs_vis: set = {sg_name}
                        _bfs_q: list = list(cmds.listConnections(sg_name, plugs=False) or [])
                        while _bfs_q and len(_bfs_vis) < 400:
                            _cur = _bfs_q.pop(0)
                            if _cur in _bfs_vis:
                                continue
                            _bfs_vis.add(_cur)
                            try:
                                if cmds.ls(_cur, dagObjects=True):
                                    continue
                                _cur_type = cmds.nodeType(_cur)
                                if _cur_type.startswith("Pxr") and _cur != sg_name:
                                    # Must be a shading node (ShadingEngine subclass
                                    # would also start 'Pxr' — skip those)
                                    if _cur_type not in ("PxrShadingEngine",):
                                        maya_shader = _cur
                                        break
                                for _nbr in cmds.listConnections(_cur, plugs=False) or []:
                                    if _nbr not in _bfs_vis:
                                        _bfs_q.append(_nbr)
                            except Exception:
                                pass
                    except Exception:
                        pass

                if not maya_shader:
                    fallback_kept += 1
                    continue

                try:
                    shader_type = cmds.nodeType(maya_shader)
                except Exception:
                    fallback_kept += 1
                    continue

                if not shader_type.startswith("Pxr"):
                    fallback_kept += 1
                    continue

                # ── Collect upstream texture / normal-map connections ─────────
                # cmds.listConnections(conn=True, plugs=True) returns pairs:
                #   [dest_plug, src_plug, dest_plug, src_plug, …]
                upstream_tex: dict = {}  # dest_attr_name → (src_node, src_node_type)
                try:
                    conns = (
                        cmds.listConnections(
                            maya_shader,
                            connections=True,
                            plugs=True,
                            source=True,
                            destination=False,
                        )
                        or []
                    )
                    for i in range(0, len(conns) - 1, 2):
                        dest_plug = conns[i]
                        src_plug = conns[i + 1]
                        dest_attr = dest_plug.split(".")[-1]
                        src_node = src_plug.split(".")[0]
                        try:
                            src_type = cmds.nodeType(src_node)
                        except Exception:
                            continue
                        if src_type in _TEX_TYPES:
                            upstream_tex[dest_attr] = (src_node, src_type)
                except Exception:
                    pass

                # ── Remove stale legacy shader children from older sessions ─────
                # Do NOT remove "UsdPreviewSurface" or "UsdUVTexture_diffuse" —
                # those were authored by the export phase with valid texture paths
                # relative to the USD stage.  We override them in-place below,
                # which keeps the working UsdUVTexture connections intact and avoids
                # the rfm2 "Failed verification: ' image '" errors that occur when
                # new UsdUVTexture nodes are created from cmds.getAttr(PxrTexture.filename)
                # (absolute Maya project paths that rfm2 cannot resolve from the USD stage).
                for _child in ("PxrPreviewSurface", "PxrTexture_diffuse"):
                    _stale = mat_stage.GetPrimAtPath(mat_prim_path.AppendChild(_child))
                    if _stale and _stale.IsValid():
                        mat_stage.RemovePrim(mat_prim_path.AppendChild(_child))

                # ── Override the Material prim ────────────────────────────────
                mat_override = mat_stage.OverridePrim(mat_prim_path)
                mat_override.SetTypeName("Material")

                # ── Override the export-phase UsdPreviewSurface shader in-place ─
                # Author over the SAME child path the export phase wrote so the
                # composed stage has exactly 30 unique UsdPreviewSurface prims
                # (not 60: base USDC 30 + import-phase new-name 30).
                # rfm2 27.2 HdPrman: UsdPreviewSurfaceParameters.oso is the only
                # valid surface bxdf .oso; PxrSurface / PxrDisneyBsdf / PxrPreviewSurface
                # are .dll RIS shaders with no .oso → "Invalid info:id X node" → grey.
                shader_usd_path = mat_prim_path.AppendChild("UsdPreviewSurface")
                _sx = mat_stage.GetPrimAtPath(shader_usd_path)
                shader_prim = (
                    _sx
                    if (_sx and _sx.IsValid())
                    else mat_stage.DefinePrim(shader_usd_path, "Shader")
                )
                usd_shader = UsdShade.Shader(shader_prim)
                usd_shader.CreateIdAttr("UsdPreviewSurface")

                # Per-source-type read-attr → UsdPreviewSurface write-attr tables.
                # Keys are MAYA shader attribute names; values are the matching
                # UsdPreviewSurface input names.
                _FLOAT_MAP: dict = {
                    "PxrDisneyBsdf": {
                        "roughness": "roughness",
                        "metallic": "metallic",
                        "ior": "ior",
                        "clearcoat": "clearcoat",
                        "presence": "opacity",
                    },
                    "PxrSurface": {
                        "specularRoughness": "roughness",
                        "presence": "opacity",
                    },
                    "PxrBlack": {},
                }.get(shader_type, {})

                _COLOR_MAP: dict = {
                    "PxrDisneyBsdf": {
                        "baseColor": "diffuseColor",
                        "emitColor": "emissiveColor",
                    },
                    "PxrSurface": {
                        "diffuseColor": "diffuseColor",
                        "glowColor": "emissiveColor",
                    },
                    "PxrBlack": {},
                }.get(shader_type, {})

                # ── Copy scalar float inputs ──────────────────────────────────
                for src_attr, dst_attr in _FLOAT_MAP.items():
                    if src_attr in upstream_tex:
                        continue  # texture already wired by export-phase UsdUVTexture node
                    try:
                        val = cmds.getAttr(f"{maya_shader}.{src_attr}")
                        if val is not None:
                            usd_shader.CreateInput(dst_attr, Sdf.ValueTypeNames.Float).Set(
                                float(val)
                            )
                    except Exception:
                        pass

                # ── Copy Color3f inputs ───────────────────────────────────────
                for src_attr, dst_attr in _COLOR_MAP.items():
                    if src_attr in upstream_tex:
                        continue
                    try:
                        raw = cmds.getAttr(f"{maya_shader}.{src_attr}")
                        # Maya returns list-of-tuple for compound attrs: [(r,g,b)]
                        if raw is not None:
                            v = (
                                raw[0]
                                if (
                                    isinstance(raw, (list, tuple))
                                    and len(raw) > 0
                                    and isinstance(raw[0], (list, tuple))
                                )
                                else raw
                            )
                            usd_shader.CreateInput(dst_attr, Sdf.ValueTypeNames.Color3f).Set(
                                Gf.Vec3f(float(v[0]), float(v[1]), float(v[2]))
                            )
                    except Exception:
                        pass

                # PxrBlack: explicit flat-black PxrPreviewSurface values
                if shader_type == "PxrBlack":
                    usd_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                        Gf.Vec3f(0.0, 0.0, 0.0)
                    )
                    usd_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
                    usd_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

                # ── Texture connections: preserved from export phase ──────────
                # The export phase already authored UsdUVTexture_diffuse nodes with
                # paths resolved relative to the USD stage.  Creating new UsdUVTexture
                # nodes here from cmds.getAttr(PxrTexture.filename) produces absolute
                # Maya project paths that rfm2 27.2 cannot verify, causing
                # "Failed verification: ' image '" errors and breaking the render.
                # The UsdUVTexture_diffuse child prim is intentionally preserved.

                # ── Wire surface outputs ──────────────────────────────────────
                # "surface" is the ONLY registered output in the UsdPreviewSurface
                # OSO schema.  Using "out" (a non-standard name) causes rfm2 27.2
                # HdPrman to silently reject the shader connection → grey render.
                surf_out = usd_shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
                mat_usd = UsdShade.Material(mat_override)
                # Wire both render contexts: rfm2 HdPrman queries "ri" first then
                # falls back to generic.  Both must connect to the same prim.
                mat_usd.CreateSurfaceOutput("ri").ConnectToSource(surf_out)
                mat_usd.CreateSurfaceOutput().ConnectToSource(surf_out)

                disney_written += 1

            # ── FIX 7: Write material:binding to materials.usda (file layer) ──
            # Phase A writes material:binding only to the in-memory session layer.
            # rfm2 27.2 HdPrman opens a fresh Usd.Stage from the root.usda FILE
            # PATH (no session layer), so Phase A's session-layer bindings are
            # invisible to the renderer.  Writing bindings into materials.usda
            # (a persistent sublayer of root.usda) guarantees rfm2 finds
            # material:binding even when constructing a sessionless stage.
            _bindings_written = 0
            if mesh_bindings:
                for _mesh_path_str, _mat_path_str in mesh_bindings.items():
                    if _mat_path_str not in mat_path_to_sg:
                        continue  # skip unmatched materials (no USD network)
                    try:
                        _mesh_prim_b = mat_stage.GetPrimAtPath(Sdf.Path(_mesh_path_str))
                        if not (_mesh_prim_b and _mesh_prim_b.IsValid()):
                            _mesh_prim_b = mat_stage.OverridePrim(Sdf.Path(_mesh_path_str))
                        _mat_prim_b = mat_stage.GetPrimAtPath(Sdf.Path(_mat_path_str))
                        if not (_mat_prim_b and _mat_prim_b.IsValid()):
                            _mat_prim_b = mat_stage.OverridePrim(Sdf.Path(_mat_path_str))
                        _usd_mat_b = UsdShade.Material(_mat_prim_b)
                        _ba = UsdShade.MaterialBindingAPI.Apply(_mesh_prim_b)
                        _ba.Bind(_usd_mat_b)
                        _bindings_written += 1
                    except Exception as _be:
                        self.logger.debug(f"[RFM] FIX7 mesh binding write: {_be}")

            mat_stage.Save()

            self.logger.info(
                f"[RFM] materials.usda rewritten: {disney_written} UsdPreviewSurface "
                f"networks authored "
                f"(PxrDisneyBsdf/PxrSurface/PxrBlack → UsdPreviewSurface + UsdUVTexture; "
                f"UsdPreviewSurfaceParameters.oso is the ONLY valid bxdf .oso in rfm2 27.2 "
                f"HdPrman usd3 shader path; outputs:surface + outputs:ri:surface wired). "
                f"{fallback_kept} materials retained export-phase UsdPreviewSurface. "
                f"FIX7: {_bindings_written} mesh material:binding overrides written to "
                f"materials.usda file layer (rfm2 HdPrman reads file layer, not session layer)."
            )

            # Reload so the live MayaUSD stage picks up the new layer content
            # without the user needing to close and reopen the scene.
            try:
                mat_layer.Reload()
                self.logger.debug("[RFM] materials.usda layer reloaded in live stage")
            except Exception as _rel_err:
                self.logger.debug(f"[RFM] materials.usda layer reload: {_rel_err}")

            # ── Post-reload diagnostic: confirm composed material state ─────────
            # Logs what rfm2 HdPrman will see for the first matched material
            # prim in materials.usda after save + reload.
            try:
                _diag_keys = list(mat_path_to_sg.keys())[:1]
                if _diag_keys:
                    _diag_stage = Usd.Stage.Open(mat_layer)
                    _dsp = Sdf.Path(_diag_keys[0])
                    _diag_mat_prim = _diag_stage.GetPrimAtPath(_dsp)
                    if _diag_mat_prim and _diag_mat_prim.IsValid():
                        _ri_attr = _diag_mat_prim.GetAttribute("outputs:ri:surface")
                        _ri_conns = _ri_attr.GetConnections() if _ri_attr else []
                        _surf_attr = _diag_mat_prim.GetAttribute("outputs:surface")
                        _surf_conns = _surf_attr.GetConnections() if _surf_attr else []
                        self.logger.info(
                            f"[RFM][DIAG] materials.usda sample {_diag_keys[0]!r}: "
                            f"outputs:ri:surface={_ri_conns}, "
                            f"outputs:surface={_surf_conns}"
                        )
                    _diag_stage = None
            except Exception as _diag_err:
                self.logger.debug(f"[RFM][DIAG] post-reload: {_diag_err}")

        except Exception as e:
            self.logger.warning(f"[RFM] Disney materials.usda rewrite failed: {e}")
            self.logger.debug(traceback.format_exc())

    def _populate_rfm_materials_sublayer(
        self,
        sub_stage: Any,
        base_usd_path: "Path",
    ) -> None:
        """Populate the materials sublayer with RenderMan ri:surface shader networks.

        For every Material prim in the base USDC that has a UsdPreviewSurface,
        this method authors a PxrPreviewSurface shader override into the materials
        sublayer and wires it to ``outputs:ri:surface`` on the material.

        RenderMan for Maya 27.2 resolves ``outputs:ri:surface`` in preference to
        ``outputs:surface`` when rendering, so the USD proxy shape will render
        correctly in RfM IPR (``.it``) and batch/XPU renders without any scene
        conversion or Hybrid Mode.

        VP2 continues to use the original ``UsdPreviewSurface`` (via
        ``outputs:surface``) because USD's render-context resolution means VP2
        never sees the ``ri:`` namespace outputs.

        Texture files referenced by UsdUVTexture nodes are re-connected to new
        sibling PxrTexture nodes in this sublayer using the same relative paths,
        so no texture duplication occurs on disk.

        Args:
            sub_stage: The materials sublayer Usd.Stage (already open for edit).
            base_usd_path: Absolute Path to the monolithic base .usdc file.
        """
        if not USD_AVAILABLE:
            return
        try:
            base_stage = Usd.Stage.Open(str(base_usd_path))
            if not base_stage:
                self.logger.warning("[RFM] Could not open base USDC for RfM materials")
                return

            rfm_count = 0
            tex_count = 0

            # ── Step 1: Collect all shaders via flat Traverse (same pattern as ──
            # _boost_usd_material_colors).  This finds shaders at ANY nesting    ──
            # depth inside a material — direct children, NodeGraph subscopes,   ──
            # or deeply nested hierarchies.  The previous GetAllChildren() approach ──
            # only found 8/30 materials because 22 had shaders nested in NodeGraphs.──
            mat_preview: dict = {}  # Sdf.Path → UsdShade.Shader (UsdPreviewSurface)
            mat_uv_textures: dict = {}  # Sdf.Path → list[UsdShade.Shader] (UsdUVTexture)

            for prim in base_stage.Traverse():
                if prim.GetTypeName() != "Shader":
                    continue
                shader = UsdShade.Shader(prim)
                try:
                    sid = shader.GetShaderId() or ""
                except Exception:
                    try:
                        sid = shader.GetIdAttr().Get() or ""
                    except Exception:
                        sid = ""

                if sid not in ("UsdPreviewSurface", "UsdUVTexture"):
                    continue

                # Walk up the hierarchy to find the enclosing Material prim.
                # Shaders may be direct children (depth 1) or inside a NodeGraph
                # subscope (depth 2+) — the ancestor walk handles either case.
                ancestor = prim.GetParent()
                mat_prim = None
                while ancestor and ancestor.IsValid():
                    if ancestor.GetTypeName() == "Material":
                        mat_prim = ancestor
                        break
                    ancestor = ancestor.GetParent()

                if mat_prim is None:
                    continue

                mat_path = mat_prim.GetPath()
                if sid == "UsdPreviewSurface":
                    if mat_path not in mat_preview:  # keep first found
                        mat_preview[mat_path] = shader
                elif sid == "UsdUVTexture":
                    mat_uv_textures.setdefault(mat_path, []).append(shader)

            # ── Step 2: Author PxrPreviewSurface overrides for every material ──
            for mat_path, preview_shader in mat_preview.items():

                # ── Find diffuse texture via connection chain ─────────────────
                # Follow diffuseColor's connection to its upstream UsdUVTexture.
                # This is reliable regardless of whether the texture node is a
                # sibling, inside a NodeGraph, or deeply nested.
                diffuse_tex_file: Optional[str] = None
                try:
                    dc_inp = preview_shader.GetInput("diffuseColor")
                    if dc_inp and dc_inp.HasConnectedSource():
                        for conn_path in dc_inp.GetAttr().GetConnections():
                            src_prim = base_stage.GetPrimAtPath(conn_path.GetPrimPath())
                            if src_prim and src_prim.IsValid():
                                src_shader = UsdShade.Shader(src_prim)
                                try:
                                    src_id = src_shader.GetShaderId() or ""
                                except Exception:
                                    src_id = ""
                                if src_id == "UsdUVTexture":
                                    file_inp = src_shader.GetInput("file")
                                    if file_inp:
                                        asset = file_inp.Get()
                                        if asset:
                                            diffuse_tex_file = str(asset.path)
                                    break
                except Exception:
                    pass

                # Fallback: scan the collected UdimTexture list for this material
                if not diffuse_tex_file:
                    for uv_shader in mat_uv_textures.get(mat_path, []):
                        try:
                            cname = uv_shader.GetPrim().GetName().lower()
                            if "normal" in cname or "nrm" in cname or "nml" in cname:
                                continue
                            file_inp = uv_shader.GetInput("file")
                            if file_inp:
                                asset = file_inp.Get()
                                if asset:
                                    diffuse_tex_file = str(asset.path)
                                    break
                        except Exception:
                            pass

                # ── Author override in materials sublayer ─────────────────────
                mat_override = sub_stage.OverridePrim(mat_path)
                # Give the over prim the 'Material' typed schema so that
                # UsdShade.Material(mat_override).CreateSurfaceOutput('ri')
                # operates on a valid Material object.
                # UsdShade.Material is a *typed* schema (not an API schema) —
                # it has no .Apply() class method.  SetTypeName is the correct
                # way to assign the type opinion to an existing prim.
                mat_override.SetTypeName("Material")

                # UsdPreviewSurface — rfm2 27.2 HdPrman Hydra path ships
                # UsdPreviewSurfaceParameters.oso in usd3/resources/shaders/.
                # The registered shader ID is "UsdPreviewSurface" (strip the
                # "Parameters.oso" suffix).  "PxrPreviewSurface" has no .oso
                # counterpart and is rejected with "Invalid info:id" warnings.
                pxr_surf_path = mat_path.AppendChild("UsdPreviewSurface")
                pxr_surf_prim = sub_stage.DefinePrim(pxr_surf_path, "Shader")
                pxr_surf = UsdShade.Shader(pxr_surf_prim)
                pxr_surf.CreateIdAttr("UsdPreviewSurface")

                # ── Copy scalar inputs ────────────────────────────────────────
                for attr_name in ("roughness", "metallic", "opacity"):
                    try:
                        inp = preview_shader.GetInput(attr_name)
                        if inp and not inp.HasConnectedSource():
                            val = inp.Get()
                            if val is not None:
                                pxr_surf.CreateInput(attr_name, Sdf.ValueTypeNames.Float).Set(
                                    float(val)
                                )
                    except Exception:
                        pass

                # ── diffuseColor: connect PxrTexture or copy static value ─────
                if diffuse_tex_file:
                    pxr_tex_path = mat_path.AppendChild("UsdUVTexture_diffuse")
                    pxr_tex_prim = sub_stage.DefinePrim(pxr_tex_path, "Shader")
                    pxr_tex = UsdShade.Shader(pxr_tex_prim)
                    # UsdUVTexture matches UsdUVTexture.oso in rfm2 27.2 usd3 shader path.
                    # Use inputs:file (not inputs:filename) and inputs:sourceColorSpace
                    # (not inputs:linearize) — these are the standard USD attribute names.
                    pxr_tex.CreateIdAttr("UsdUVTexture")
                    pxr_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                        Sdf.AssetPath(diffuse_tex_file)
                    )
                    # Diffuse textures are sRGB (PNG/JPEG gamma-encoded)
                    pxr_tex.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
                    # UsdUVTexture output is "rgb" (not "resultRGB")
                    tex_out = pxr_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Color3f)
                    pxr_surf.CreateInput(
                        "diffuseColor", Sdf.ValueTypeNames.Color3f
                    ).ConnectToSource(tex_out)
                    tex_count += 1
                else:
                    try:
                        dc_inp = preview_shader.GetInput("diffuseColor")
                        if dc_inp and not dc_inp.HasConnectedSource():
                            dc_val = dc_inp.Get()
                            if dc_val is not None:
                                pxr_surf.CreateInput(
                                    "diffuseColor", Sdf.ValueTypeNames.Color3f
                                ).Set(
                                    Gf.Vec3f(float(dc_val[0]), float(dc_val[1]), float(dc_val[2]))
                                )
                    except Exception:
                        pass

                # ── Wire outputs:surface + outputs:ri:surface ─────────────────
                # UsdPreviewSurface's registered schema output is "surface" — NOT
                # "out".  rfm2 27.2 HdPrman validates the output port name against
                # the compiled OSO schema; "out" is silently rejected → grey render.
                # Wire BOTH render contexts so rfm2 finds the shader regardless of
                # whether it queries "ri" context or falls back to generic.
                pxr_surf_out = pxr_surf.CreateOutput("surface", Sdf.ValueTypeNames.Token)
                mat_usd_export = UsdShade.Material(mat_override)
                mat_usd_export.CreateSurfaceOutput("ri").ConnectToSource(pxr_surf_out)
                mat_usd_export.CreateSurfaceOutput().ConnectToSource(pxr_surf_out)

                rfm_count += 1

            if rfm_count > 0:
                self.logger.info(
                    f"[RFM] Wrote UsdPreviewSurface ri:surface for {rfm_count} "
                    f"materials ({tex_count} with UsdUVTexture diffuse) in "
                    f"materials.usda \u2014 renderable in RenderMan for Maya 27.2+ "
                    f"via IPR (.it) and XPU batch render"
                )
            else:
                self.logger.warning(
                    "[RFM] No UsdPreviewSurface materials found in base USDC \u2014 "
                    "ri:surface networks could not be authored"
                )

        except Exception as e:
            self.logger.warning(f"[RFM] RfM materials sublayer population failed: {e}")
            self.logger.debug(traceback.format_exc())
            self.logger.warning(f"[RFM] RfM materials sublayer population failed: {e}")
            self.logger.debug(traceback.format_exc())
            self.logger.warning(f"[RFM] RfM materials sublayer population failed: {e}")
            self.logger.debug(traceback.format_exc())
