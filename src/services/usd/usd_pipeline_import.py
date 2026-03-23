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
    import maya.cmds as cmds          # type: ignore[import-unresolved]
    import maya.mel as mel            # type: ignore[import-unresolved]
    MAYA_AVAILABLE = True
except ImportError:
    cmds = None   # type: ignore[assignment]
    mel = None   # type: ignore[assignment]
    MAYA_AVAILABLE = False

# ── Optional USD imports ──────────────────────────────────────────────────────
try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

from .usd_pipeline_models import (
    ConversionResult,
    ConversionStatus,
    ExportOptions,
    ExportResult,
    ImportOptions,
    ImportResult,
    MAYA_AVAILABLE as _MAYA_AVAILABLE_MODEL,
    USD_AVAILABLE as _USD_AVAILABLE_MODEL,
)


class ImportMixin:
    # ── Attribute stubs (provided by UsdPipeline.__init__) ────────────
    logger: logging.Logger
    _maya_available: bool
    _usd_available: bool
    _mayausd_available: bool
    _progress_callback: Optional[Callable[[str, int], None]]

    def import_usd(
        self,
        usd_path: Path,
        options: Optional[ImportOptions] = None
    ) -> ImportResult:
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

            if usd_path.suffix.lower() == '.usdz':
                self._report_progress("Extracting USDZ package", 5)
                actual_usd_path, rig_mb_path, temp_dir = self._extract_usdz(usd_path)

                if not actual_usd_path:
                    result.error_message = "Failed to extract USDZ package"
                    return result

                # Sibling .rig.mb lookup — the .rig.mb is kept separate from
                # the .usdz for online viewer compatibility.  Check for a file
                # named <stem>.rig.mb (or .rig.ma) alongside the source .usdz.
                if rig_mb_path is None:
                    for _ext in ('.rig.mb', '.rig.ma'):
                        _sibling = usd_path.parent / (usd_path.stem + _ext)
                        if _sibling.exists():
                            rig_mb_path = _sibling
                            self.logger.info(
                                f"[RIG] Found sibling rig file: {_sibling.name}"
                            )
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
                    self.logger.info(
                        f"[OK] Proxy will load layered stage: {layered_root.name}"
                    )
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
                            f"[LOOKDEV] {result.usd_materials} USD materials: VP2 via "
                            f"UsdPreviewSurface + RenderMan via Maya PxrSurface (Hypershade)"
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
            rig_exists = rig_mb_path.exists() if rig_mb_path else False
            self.logger.info(
                f"[IMPORT] Hybrid check: hybrid_mode={options.hybrid_mode}, "
                f"rig_mb_path={rig_mb_path}, exists={rig_exists}"
            )
            if options.hybrid_mode and rig_mb_path and rig_mb_path.exists():
                self.logger.info("[OK] HYBRID MODE ACTIVATED")
                self._report_progress("[HYBRID] Hybrid Mode: Converting USD to Maya + controllers", 20)
                success = self._import_hybrid(actual_usd_path, rig_mb_path, options, result)
                result.success = success
                self._report_progress("Hybrid import complete", 100)
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
                self.logger.info("[TIP] To convert to native Maya: Right-click proxy > Duplicate As > Maya Data")

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
                    self.logger.info(
                        f"[SAVE] USD files preserved in: {temp_dir}"
                    )

        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            self.logger.error(traceback.format_exc())
            result.error_message = str(e)

        return result

    def _extract_usdz(
        self,
        usdz_path: Path
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
            _usd_exts = {'.usd', '.usdc', '.mb', '.ma'}
            for old_file in extract_dir.iterdir():
                if old_file.is_file() and old_file.suffix in _usd_exts:
                    try:
                        old_file.unlink()
                    except Exception:
                        pass

            usd_path = None
            rig_mb_path = None

            with zipfile.ZipFile(str(usdz_path), 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('/'):
                        continue  # skip directory entries

                    flat_name = Path(name).name

                    if flat_name.endswith(('.usd', '.usdc', '.usda')):
                        # USD stage files go to root of extract_dir so that
                        # relative paths inside the USDC (e.g. @textures/foo.png@)
                        # resolve correctly against extract_dir as the base.
                        dest = extract_dir / flat_name
                        with zf.open(name) as src, open(dest, 'wb') as dst:
                            dst.write(src.read())
                        usd_path = dest
                        self.logger.info(f"[FILE] Extracted USD: {flat_name}")
                    elif flat_name.endswith(('.rig.mb', '.rig.ma')):
                        dest = extract_dir / flat_name
                        with zf.open(name) as src, open(dest, 'wb') as dst:
                            dst.write(src.read())
                        rig_mb_path = dest
                        self.logger.info(f"[PACKAGE] Extracted rig backup: {flat_name}")
                    else:
                        # ALL other files (textures, etc.) — preserve the
                        # relative ZIP path so that USDC-internal references
                        # like @./textures/Chain_Base_color.png@ resolve correctly.
                        dest = extract_dir / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, open(dest, 'wb') as dst:
                            dst.write(src.read())

            # Count extracted textures for diagnostics
            tex_count = sum(
                1 for f in extract_dir.rglob('*')
                if f.is_file() and f.suffix.lower() in
                {'.png', '.jpg', '.jpeg', '.exr', '.tif', '.tiff', '.tx', '.tex'}
            )
            if tex_count:
                self.logger.info(f"[EXTRACT] {tex_count} texture file(s) extracted")

            return usd_path, rig_mb_path, extract_dir

        except Exception as e:
            self.logger.error(f"USDZ extraction failed: {e}")
            return None, None, None

    def _import_with_mayausd(
        self,
        usd_path: Path,
        options: ImportOptions,
        result: ImportResult
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
                            if prim_type == 'Mesh':
                                mesh_count += 1
                                # Check if mesh has skeleton binding
                                if prim.HasAPI(UsdSkel.BindingAPI):
                                    has_skeleton_bindings = True
                            elif prim_type == 'Skeleton':
                                skel_count += 1
                                # Sum actual joints defined in this Skeleton
                                joints_attr = UsdSkel.Skeleton(prim).GetJointsAttr().Get()
                                if joints_attr:
                                    joint_count += len(joints_attr)
                            elif prim_type in ('NurbsCurves', 'BasisCurves'):
                                curve_count += 1
                            elif prim_type == 'Material':
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
                    cmds.optionVar(stringValue=('mayaUsd_ShadingModeImport', 'useRegistry'))
                    self.logger.info("[SHADING] mayaUsd_ShadingModeImport=useRegistry — VP2 will use V3 Lighting API")
                except Exception:
                    pass

                # Sanitize the stem: Maya node names must not contain dots.
                # e.g. "Veteran_Rig.root" → "Veteran_Rig_root"
                node_base = usd_path.stem.replace('.', '_')

                # Create the proxy shape
                proxy_transform = cmds.createNode('transform', name=node_base + '_USD')
                proxy_shape = cmds.createNode(
                    'mayaUsdProxyShape',
                    parent=proxy_transform,
                    name=node_base + '_USDShape'
                )

                # Loading the file path triggers USD stage composition.
                # Maya will print "# Using V3 Lighting API for UsdPreviewSurface shading."
                # confirming the optionVar above was respected.
                # NOTE: Always use forward slashes — pathlib.Path on Windows gives
                # backslashes, but PxrUSD procedural and Sdf expect POSIX separators.
                usd_path_fwd = str(usd_path).replace('\\', '/')
                cmds.setAttr(f"{proxy_shape}.filePath", usd_path_fwd, type='string')

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
                cmds.setAttr(f"{proxy_shape}.primPath", '/', type='string')

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
                self.logger.info("[USD] Stage loaded via mayaUsdProxyShape (primPath='/'; full hierarchy rendered)")

                # ── RfM 27.2: Optional rmanAddAttr registration ──────────────────
                # rmanAddAttr was a legacy rfm1 MEL command (pre-RfM 24). In
                # rfm2 (RfM 24+ / 27.2) it no longer exists — rfm2 auto-discovers
                # all Maya shape nodes (including mayaUsdProxyShape) via its
                # registered translator plugins. Calling it in RfM 27.2 causes a
                # "Cannot find procedure" MEL error even though that error is
                # harmless. Guard with whatIs so the error never prints.
                try:
                    if mel is not None:
                        _proc_exists = mel.eval('whatIs "rmanAddAttr"') not in ('Unknown', '')
                        if _proc_exists:
                            # rfm1-style session (very old RfM) — call legacy proc
                            prev_sel = cmds.ls(selection=True) or []
                            cmds.select(proxy_shape, replace=True)
                            mel.eval('rmanAddAttr')
                            if prev_sel:
                                cmds.select(prev_sel, replace=True)
                            else:
                                cmds.select(clear=True)
                            self.logger.info("[RFM] rmanAddAttr — proxy shape registered with RenderMan translator")
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
                    if focused and 'modelPanel' in focused:
                        panels_to_configure = [focused]
                    else:
                        panels_to_configure = cmds.getPanel(type='modelPanel') or []

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
                            _rman_vp = {'renderManForMaya', 'myRenderView', 'renderManXPU'}
                            if renderer not in _rman_vp and renderer != 'vp2Renderer':
                                cmds.modelEditor(panel, edit=True, rendererName='vp2Renderer')

                            # Enable shaded+material display.
                            # useDefaultMaterial=False is the critical flag —
                            # without it VP2 shows solid white ("default material") on
                            # USD proxy shapes even when UsdPreviewSurface shaders exist.
                            cmds.modelEditor(
                                panel,
                                edit=True,
                                displayTextures=True,
                                displayAppearance='smoothShaded',
                                displayLights='default',
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
                        self.logger.warning("[WARNING] Could not configure any model panel for material display")

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
                    if mel_m.eval('whatIs "rfmUpdateUI"') not in ('Unknown', ''):
                        # rfm1-style session (very old RfM) — use legacy command
                        mel_m.eval('rfmUpdateUI')
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
            proxy_shapes = cmds.ls(type='mayaUsdProxyShape') or []
            if proxy_shapes:
                self.logger.info(f"[PACKAGE] USD proxy shape(s) created: {len(proxy_shapes)}")

                # Count USD prims inside the proxy shape(s)
                self._count_usd_prims_in_proxy(proxy_shapes, result)

                # Mark as successful USD import
                result.usd_meshes = mesh_count if mesh_count > 0 else result.usd_meshes
                # Use real joint count; skel_count is kept for threshold checks below
                result.usd_joints = joint_count if joint_count > 0 else skel_count
                result.usd_curves = curve_count if curve_count > 0 else result.usd_curves
                result.usd_materials = material_count if material_count > 0 else result.usd_materials

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
                mel.eval('mayaUsdLayerEditorWindow')
                self.logger.info(
                    "[LAYER] Opened mayaUSD Layer Editor — author animation as USD layers (Option B)"
                )
                return
            except Exception:
                pass

            # Fall back to Maya's built-in Animation Layer Editor
            try:
                mel.eval('LayerEditorWindow')
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
                if prim.GetTypeName() != 'Shader':
                    continue
                shader = UsdShade.Shader(prim)
                if not shader or shader.GetShaderId() != 'UsdPreviewSurface':
                    continue

                dc_input = shader.GetInput('diffuseColor')
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
                if prim.GetTypeName() != 'Mesh':
                    continue
                try:
                    color = None

                    # ── Primary: direct material:binding relationship ──────────
                    # More reliable than ComputeBoundMaterial across USD versions
                    # because it avoids USD 22.x/23.x/24.x API signature changes.
                    binding_rel = prim.GetRelationship('material:binding')
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
                            _cm_result = UsdShade.MaterialBindingAPI(
                                prim
                            ).ComputeBoundMaterial()
                            # Handle both tuple return (USD 22+) and bare object
                            bound_mat = (
                                _cm_result[0]
                                if isinstance(_cm_result, (tuple, list))
                                else _cm_result
                            )
                            if bound_mat and bound_mat.GetPrim().IsValid():
                                color = mat_path_to_color.get(
                                    bound_mat.GetPrim().GetPath()
                                )
                                if color is None:
                                    color = self._rfm_name_color(
                                        bound_mat.GetPrim().GetName()
                                    )
                        except Exception:
                            pass

                    # ── Final fallback: name-hash the mesh itself ─────────────
                    if color is None:
                        color = self._rfm_name_color(prim.GetName())

                    r = float(color[0])
                    g = float(color[1])
                    b = float(color[2])
                    UsdGeom.Gprim(prim).CreateDisplayColorAttr(
                        Vt.Vec3fArray([Gf.Vec3f(r, g, b)])
                    )
                    display_colored += 1
                except Exception as _disp_err:
                    if _first_disp_err is None:
                        _first_disp_err = f"{prim.GetPath()}: {_disp_err}"
                    continue

            if _first_disp_err:
                self.logger.warning(
                    f"[BOOST] displayColor: first mesh error — {_first_disp_err}"
                )

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
        self,
        base_usd_path: Path,
        rig_mb_path: Optional[Path] = None
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
                self.logger.info(
                    f"[LAYER] Extracting controller data from: {rig_mb_path.name}"
                )
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
                    layer.Clear()   # wipe stale content; keep cache entry intact
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
                    self._populate_skeleton_metadata(
                        sub_stage, base_usd_path, rig_data
                    )

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
            default_prim_name = (
                default_prim.GetName() if default_prim else asset_name
            )

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
                    f" ({ctrl_count} controllers, "
                    f"{mapping_count} joint mappings from .rig.mb)"
                )
            self.logger.info(
                f"[OK] Layered stage: {root_path.name} → "
                f"{total_sublayers} sublayers{ctrl_msg}"
            )

            return root_path

        except Exception as e:
            self.logger.error(f"[LAYER] Failed to build layered stage: {e}")
            self.logger.error(traceback.format_exc())
            return None

    # ─── .rig.mb Controller Extraction ────────────────────────────────────

    def _extract_rig_controllers(
        self, rig_mb_path: Path
    ) -> Optional[dict]:
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

            try:
                cmds.file(
                    str(rig_mb_path),
                    reference=True,
                    namespace=namespace,
                    returnNewNodes=False,
                    loadReferenceDepth="all"
                )
                self.logger.info("[RIG] .rig.mb reference loaded successfully")
            except Exception as ref_err:
                self.logger.warning(
                    f"[RIG] Could not reference .rig.mb: {ref_err}"
                )
                return None

            controllers = []
            mappings: dict[str, list[str]] = {}
            joint_names: list[str] = []

            try:
                # ── Find all joints ──
                all_joints = cmds.ls(
                    f"{namespace}:*", type="joint", long=False
                ) or []
                # Strip namespace for clean names
                joint_names = [
                    j.replace(f"{namespace}:", "") for j in all_joints
                ]

                # ── Find NURBS curves (controllers) ──
                all_curves = cmds.ls(
                    f"{namespace}:*", type="nurbsCurve", long=True
                ) or []
                self.logger.info(
                    f"[RIG] Found {len(all_curves)} NURBS curves, "
                    f"{len(all_joints)} joints"
                )

                for curve_shape in all_curves:
                    # Get transform parent
                    parents = cmds.listRelatives(
                        curve_shape, parent=True, fullPath=True
                    )
                    if not parents:
                        continue
                    transform = parents[0]
                    short_name = transform.split("|")[-1].split(":")[-1]

                    # Skip non-controller curves (construction history, etc.)
                    # Controllers typically have "ctrl" or "CTRL" or known
                    # prefixes, but we'll be inclusive and grab everything
                    try:
                        # Get curve CVs
                        num_cvs = cmds.getAttr(
                            f"{curve_shape}.controlPoints", size=True
                        )
                        cvs = []
                        for i in range(num_cvs):
                            pt = cmds.getAttr(
                                f"{curve_shape}.controlPoints[{i}]"
                            )
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
                            knots_raw = cmds.getAttr(
                                f"{curve_shape}.knots[0:{num_knots - 1}]"
                            )
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
                            if cmds.getAttr(
                                f"{transform}.overrideEnabled"
                            ):
                                if cmds.getAttr(
                                    f"{transform}.overrideRGBColors"
                                ):
                                    cr = cmds.getAttr(
                                        f"{transform}.overrideColorR"
                                    )
                                    cg = cmds.getAttr(
                                        f"{transform}.overrideColorG"
                                    )
                                    cb = cmds.getAttr(
                                        f"{transform}.overrideColorB"
                                    )
                                    color = (cr, cg, cb)
                        except Exception:
                            pass

                        controllers.append({
                            "name": short_name,
                            "cvs": cvs,
                            "degree": degree,
                            "form": form,
                            "knots": knots,
                            "translate": (tx, ty, tz),
                            "rotate": (rx, ry, rz),
                            "color": color,
                        })

                    except Exception as cv_err:
                        self.logger.debug(
                            f"[RIG] Skipped {short_name}: {cv_err}"
                        )
                        continue

                # ── Find controller → joint mappings via constraints ──
                constraint_types = [
                    "parentConstraint", "orientConstraint",
                    "pointConstraint", "aimConstraint",
                    "scaleConstraint"
                ]
                for joint in all_joints:
                    joint_short = joint.replace(f"{namespace}:", "")
                    for ctype in constraint_types:
                        try:
                            constraints = cmds.listConnections(
                                joint,
                                type=ctype,
                                source=True,
                                destination=False
                            ) or []
                            for con in constraints:
                                # Find what drives this constraint
                                drivers = cmds.listConnections(
                                    f"{con}.target",
                                    source=True,
                                    destination=False
                                ) or []
                                for driver in drivers:
                                    drv_short = driver.split(
                                        ":"
                                    )[-1].split("|")[-1]
                                    if drv_short not in mappings:
                                        mappings[drv_short] = []
                                    if joint_short not in mappings[drv_short]:
                                        mappings[drv_short].append(
                                            joint_short
                                        )
                        except Exception:
                            continue

                # Also check direct connections (no constraints)
                for joint in all_joints:
                    joint_short = joint.replace(f"{namespace}:", "")
                    for attr in ["rotate", "translate"]:
                        try:
                            conns = cmds.listConnections(
                                f"{joint}.{attr}",
                                source=True,
                                destination=False,
                                skipConversionNodes=True
                            ) or []
                            for conn in conns:
                                conn_short = conn.split(
                                    ":"
                                )[-1].split("|")[-1]
                                # Only map if it looks like a controller
                                node_type = cmds.nodeType(conn)
                                if node_type == "transform":
                                    shapes = cmds.listRelatives(
                                        conn, shapes=True, type="nurbsCurve"
                                    )
                                    if shapes:
                                        if conn_short not in mappings:
                                            mappings[conn_short] = []
                                        if (
                                            joint_short
                                            not in mappings[conn_short]
                                        ):
                                            mappings[conn_short].append(
                                                joint_short
                                            )
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
                    self._export_rfm_shaders_from_reference(namespace)
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
                    ref_nodes = cmds.ls(
                        f"{namespace}*", type="reference"
                    ) or []
                    for rn in ref_nodes:
                        try:
                            cmds.file(
                                removeReference=True, referenceNode=rn
                            )
                        except Exception:
                            pass
                    self.logger.info("[RIG] Removed .rig.mb reference")
                except Exception as rm_err:
                    self.logger.warning(
                        f"[RIG] Could not remove reference: {rm_err}"
                    )

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

    def _export_rfm_shaders_from_reference(self, namespace: str) -> Optional[Path]:
        """BFS-export all RenderMan shader networks from a loaded reference to a temp .mb.

        Called while the Maya reference ``namespace:*`` is still live (before
        ``removeReference``).  Walks upstream from every ``shadingEngine`` whose
        ``surfaceShader`` is a RenderMan Pxr* shader and exports the full
        connected network (PxrTexture, PxrNormalMap, PxrManifold2D, etc.) to a
        temporary ``.mb`` file.  The file is consumed — and then deleted — by
        :meth:`_import_rfm_shaders_from_cache` during shader setup.

        Args:
            namespace: The Maya reference namespace (without trailing colon).

        Returns:
            Path to the temp ``.mb`` file on success, ``None`` on failure.
        """
        if cmds is None:
            return None
        import tempfile as _tempfile
        try:
            # ── Collect all SGs with a RenderMan Pxr* surface shader ─────────
            all_sgs = cmds.ls(f'{namespace}:*', type='shadingEngine') or []
            rfm_sgs: list = []
            for sg in all_sgs:
                surf = (
                    cmds.listConnections(
                        f'{sg}.surfaceShader', source=True, destination=False
                    ) or
                    cmds.listConnections(
                        f'{sg}.rman__shader', source=True, destination=False
                    ) or []
                )
                if surf and cmds.nodeType(surf[0]).startswith('Pxr'):
                    rfm_sgs.append(sg)

            if not rfm_sgs:
                return None

            # ── BFS: collect the full upstream shader network ─────────────────
            visited: set = set()
            stack = list(rfm_sgs)
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                upstream = (
                    cmds.listConnections(
                        node, source=True, destination=False,
                        skipConversionNodes=False,
                    ) or []
                )
                stack.extend(upstream)

            # ── Export to temp file ───────────────────────────────────────────
            tmp_path = Path(
                _tempfile.mktemp(suffix='_rfm_shaders.mb')
            )
            cmds.select(list(visited), replace=True)
            cmds.file(
                str(tmp_path),
                exportSelected=True,
                type='mayaBinary',
                force=True,
                preserveReferences=False,
            )
            cmds.select(clear=True)
            self.logger.debug(
                f"[RFM] Shader cache: exported {len(rfm_sgs)} SGs "
                f"({len(visited)} nodes) \u2192 {tmp_path.name}"
            )
            return tmp_path

        except Exception as err:
            self.logger.warning(f"[RFM] Shader cache export failed: {err}")
            try:
                cmds.select(clear=True)
            except Exception:
                pass
            return None

    def _import_rfm_shaders_from_cache(
        self, mat_prim_paths: set
    ) -> dict:
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

        cache_path: Optional[Path] = getattr(self, '_rfm_shader_cache_path', None)
        if not cache_path or not cache_path.exists():
            return {}

        IMPORT_NS = 'rfmMat'
        try:
            cmds.file(
                str(cache_path),
                i=True,
                type='mayaBinary',
                namespace=IMPORT_NS,
                ignoreVersion=True,
                importTimeRange='none',
            )
        except Exception as import_err:
            self.logger.warning(
                f"[RFM] Shader cache import failed: {import_err}"
            )
            return {}
        finally:
            # Always delete the temp file and clear the cache pointer.
            try:
                cache_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._rfm_shader_cache_path = None

        NS_PREFIX = f'{IMPORT_NS}:'

        try:
            # ── Collect SGs with Pxr* surface shaders ────────────────────────
            all_sgs = cmds.ls(f'{NS_PREFIX}*', type='shadingEngine') or []
            rfm_sgs: dict = {}  # base_name (no namespace) → sg_full_name
            for sg in all_sgs:
                surf = (
                    cmds.listConnections(
                        f'{sg}.surfaceShader', source=True, destination=False
                    ) or
                    cmds.listConnections(
                        f'{sg}.rman__shader', source=True, destination=False
                    ) or []
                )
                if surf and cmds.nodeType(surf[0]).startswith('Pxr'):
                    base = sg[len(NS_PREFIX):]  # strip namespace
                    rfm_sgs[base] = sg

            # ── Delete all DAG transforms (geometry, joints, curves) ──────────
            # Shader/texture DG nodes have no DAG parents and survive this step.
            dag_transforms = (
                cmds.ls(f'{NS_PREFIX}*', type='transform', long=True) or []
            )
            if dag_transforms:
                try:
                    cmds.delete(dag_transforms)
                except Exception:
                    pass

            # ── Build USD material path → Maya SG mapping ────────────────────
            # USD material names: /Materials/PxrDisneyBsdf1  → 'PxrDisneyBsdf1'
            # Maya SG base names: 'PxrDisneyBsdf1SG'         → strip 'SG' → 'PxrDisneyBsdf1'
            sg_lookup: dict = {}  # lower(stripped_name) → sg_full_name
            for base_name, sg_node in rfm_sgs.items():
                # Try both {name}SG and just {name} (some rigs don't append SG)
                stripped = base_name[:-2] if base_name.lower().endswith('sg') else base_name
                sg_lookup[stripped.lower()] = sg_node
                sg_lookup[base_name.lower()] = sg_node

            mat_path_to_sg: dict = {}
            for mat_path_str in mat_prim_paths:
                mat_name = Sdf.Path(mat_path_str).name
                candidate = (
                    sg_lookup.get(mat_name.lower()) or
                    sg_lookup.get((mat_name + 'SG').lower())
                )
                if candidate:
                    mat_path_to_sg[mat_path_str] = candidate

            # ── Rename nodes to drop the rfmMat: namespace prefix ────────────
            # This gives clean Hypershade node names (PxrDisneyBsdf1SG, etc.).
            remaining_ns = cmds.ls(f'{NS_PREFIX}*') or []
            renamed: dict = {}  # old_name → new_name
            for node in remaining_ns:
                base = node[len(NS_PREFIX):]
                try:
                    new_name = cmds.rename(node, base)
                    renamed[node] = new_name
                except Exception:
                    renamed[node] = node  # keep prefixed name on collision

            # Update mat_path_to_sg with renamed SG names
            for mat_path, sg in list(mat_path_to_sg.items()):
                if sg in renamed:
                    mat_path_to_sg[mat_path] = renamed[sg]

            return mat_path_to_sg

        except Exception as err:
            self.logger.warning(
                f"[RFM] Shader cache processing failed: {err}"
            )
            return {}

    def _sg_has_texture(self, sg_name: str) -> bool:
        """Return True if the SG's surface shader has a PxrTexture on diffuseColor."""
        if cmds is None:
            return False
        try:
            surf_nodes = (
                cmds.listConnections(
                    f'{sg_name}.surfaceShader', source=True, destination=False
                ) or []
            )
            for surf in surf_nodes:
                tex_inputs = (
                    cmds.listConnections(
                        f'{surf}.diffuseColor', source=True, destination=False
                    ) or []
                )
                if any(
                    cmds.nodeType(t) in ('PxrTexture', 'PxrManifoldFile')
                    for t in tex_inputs
                ):
                    return True
        except Exception:
            pass
        return False

    def _populate_controllers_sublayer(
        self, stage, rig_data: dict
    ) -> None:
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
            UsdGeom.Imageable(ctrl_scope).CreatePurposeAttr(
                UsdGeom.Tokens.guide
            )

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
                    points = Vt.Vec3fArray(
                        [Gf.Vec3f(p[0], p[1], p[2]) for p in cvs]
                    )
                    curves.CreatePointsAttr(points)
                    curves.CreateCurveVertexCountsAttr(
                        Vt.IntArray([len(cvs)])
                    )

                    # Degree and order
                    degree = ctrl.get("degree", 3)
                    curves.CreateOrderAttr(Vt.IntArray([degree + 1]))

                    # Knots
                    knots = ctrl.get("knots", [])
                    if knots:
                        curves.CreateKnotsAttr(
                            Vt.DoubleArray(knots)
                        )

                    # Set purpose to "guide" so it's visible but not rendered
                    UsdGeom.Imageable(prim).CreatePurposeAttr(
                        UsdGeom.Tokens.guide
                    )

                    # Display color from Maya override
                    color = ctrl.get("color")
                    if color:
                        curves.CreateDisplayColorAttr(
                            Vt.Vec3fArray(
                                [Gf.Vec3f(color[0], color[1], color[2])]
                            )
                        )

                    # Transform — only add ops if non-zero
                    tx, ty, tz = ctrl.get("translate", (0, 0, 0))
                    rx, ry, rz = ctrl.get("rotate", (0, 0, 0))
                    has_translate = any(v != 0 for v in (tx, ty, tz))
                    has_rotate = any(v != 0 for v in (rx, ry, rz))

                    if has_translate or has_rotate:
                        xform = UsdGeom.Xformable(prim)
                        if has_translate:
                            xform.AddTranslateOp().Set(
                                Gf.Vec3d(tx, ty, tz)
                            )
                        if has_rotate:
                            xform.AddRotateXYZOp().Set(
                                Gf.Vec3f(rx, ry, rz)
                            )

                    # Custom attribute: which joints this controller drives
                    driven = mappings.get(name, [])
                    if driven:
                        driven_attr = prim.CreateAttribute(
                            "assetManager:drivenJoints",
                            Sdf.ValueTypeNames.StringArray
                        )
                        driven_attr.Set(driven)

                    written += 1

                except Exception as ctrl_err:
                    skipped += 1
                    self.logger.debug(
                        f"[LAYER] Skipped controller {safe_name}: {ctrl_err}"
                    )

            skip_msg = f", {skipped} skipped" if skipped else ""
            self.logger.info(
                f"[LAYER] Wrote {written} NURBS controllers "
                f"to controllers sublayer{skip_msg}"
            )

        except Exception as e:
            self.logger.warning(
                f"[LAYER] Could not populate controllers sublayer: {e}"
            )
            self.logger.debug(traceback.format_exc())

    def _populate_skeleton_metadata(
        self, stage, base_usd_path: Path, rig_data: dict
    ) -> None:
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
                        "assetManager:controllerMap",
                        Sdf.ValueTypeNames.String
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
            self.logger.warning(
                f"[LAYER] Could not populate skeleton metadata: {e}"
            )
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
                    indices = pv.GetIndices()   # Vt.IntArray
                    values = pv.Get()           # Vt values array
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
                    fixed = Vt.IntArray(
                        [max(0, min(int(i), max_valid)) for i in indices]
                    )
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
            _probe = cmds.shadingNode('PxrSurface', asShader=True, name='__rfm_probe__')
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
            mat_preview: Dict[str, Any] = {}       # mat_path_str → UsdShade.Shader
            mat_textures: Dict[str, List] = {}     # mat_path_str → [UsdShade.Shader, …]
            mesh_bindings: Dict[str, str] = {}     # mesh_path_str → mat_path_str

            for prim in stage.Traverse():
                ptype = prim.GetTypeName()

                if ptype == 'Mesh':
                    binding_api = UsdShade.MaterialBindingAPI(prim)
                    binding = binding_api.GetDirectBinding()
                    bound_mat = binding.GetMaterial()
                    if bound_mat and bound_mat.GetPrim().IsValid():
                        mesh_bindings[str(prim.GetPath())] = (
                            str(bound_mat.GetPrim().GetPath())
                        )
                    continue

                if ptype != 'Shader':
                    continue

                shader = UsdShade.Shader(prim)
                try:
                    sid = shader.GetShaderId() or ''
                except Exception:
                    try:
                        sid = shader.GetIdAttr().Get() or ''
                    except Exception:
                        sid = ''

                if sid not in ('UsdPreviewSurface', 'UsdUVTexture'):
                    continue

                # Walk up the hierarchy to find the enclosing Material prim.
                ancestor = prim.GetParent()
                mat_prim: Any = None
                while ancestor and ancestor.IsValid():
                    if ancestor.GetTypeName() == 'Material':
                        mat_prim = ancestor
                        break
                    ancestor = ancestor.GetParent()
                if mat_prim is None:
                    continue

                mat_key = str(mat_prim.GetPath())
                if sid == 'UsdPreviewSurface':
                    if mat_key not in mat_preview:
                        mat_preview[mat_key] = shader
                elif sid == 'UsdUVTexture':
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

            if mat_path_to_sg:
                created_count = len(mat_path_to_sg)
                tex_count = sum(
                    1 for sg in mat_path_to_sg.values()
                    if self._sg_has_texture(sg)
                )
                self.logger.info(
                    f"[RFM] Imported {created_count} original RfM shaders from "
                    f".rig.mb ({tex_count} textured) \u2014 exact settings from "
                    f"original Maya scene (PxrDisney/PxrSurface with full texture maps)"
                )
            _cache_used: bool = bool(mat_path_to_sg)  # True when Strategy 1 succeeded
            # ── Strategy 2: Synthetic PxrSurface from USD data (fallback) ──────
            # Runs for any material that was NOT found in the .rig.mb shader cache.
            # If Strategy 1 filled mat_path_to_sg completely, this loop is a no-op.
            for mat_key, preview_shader in mat_preview.items():
                if mat_key in mat_path_to_sg:
                    # Real shader already imported from .rig.mb cache — skip.
                    continue

                mat_name = Sdf.Path(mat_key).name
                safe = (
                    mat_name.replace(' ', '_').replace(':', '_').replace('.', '_')
                )

                # ── Resolve diffuse texture path ───────────────────────────────
                diffuse_tex: Optional[str] = None
                try:
                    dc_inp = preview_shader.GetInput('diffuseColor')
                    if dc_inp and dc_inp.HasConnectedSource():
                        for conn in dc_inp.GetAttr().GetConnections():
                            src_prim = stage.GetPrimAtPath(conn.GetPrimPath())
                            if not (src_prim and src_prim.IsValid()):
                                continue
                            src_sh = UsdShade.Shader(src_prim)
                            try:
                                src_id = src_sh.GetShaderId() or ''
                            except Exception:
                                src_id = ''
                            if src_id != 'UsdUVTexture':
                                continue
                            f_inp = src_sh.GetInput('file')
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
                    for uv_sh in mat_textures.get(mat_key, []):
                        cname = uv_sh.GetPrim().GetName().lower()
                        if any(t in cname for t in ('normal', 'nrm', 'nml', 'bump', 'spec')):
                            continue
                        f_inp = uv_sh.GetInput('file')
                        if not f_inp:
                            continue
                        asset = f_inp.Get()
                        if asset:
                            diffuse_tex = str(asset.path)
                            break

                # Resolve relative → absolute path.
                if diffuse_tex and not Path(diffuse_tex).is_absolute():
                    resolved = (usd_dir / diffuse_tex).resolve()
                    diffuse_tex = (
                        str(resolved).replace('\\', '/') if resolved.exists() else None
                    )
                elif diffuse_tex:
                    diffuse_tex = diffuse_tex.replace('\\', '/')
                    if not Path(diffuse_tex).exists():
                        diffuse_tex = None

                # ── Read scalar PBR properties from UsdPreviewSurface ──────────
                roughness = 0.5
                metallic = 0.0
                try:
                    r_inp = preview_shader.GetInput('roughness')
                    if r_inp and not r_inp.HasConnectedSource():
                        v = r_inp.Get()
                        if v is not None:
                            roughness = max(0.0, min(float(v), 1.0))
                except Exception:
                    pass
                try:
                    m_inp = preview_shader.GetInput('metallic')
                    if m_inp and not m_inp.HasConnectedSource():
                        v = m_inp.Get()
                        if v is not None:
                            metallic = max(0.0, min(float(v), 1.0))
                except Exception:
                    pass

                # ── Create Maya PxrSurface node + shading group ────────────────
                try:
                    pxr_surf = cmds.shadingNode(
                        'PxrSurface', asShader=True, name=f'rfm_{safe}'
                    )
                    sg = cmds.sets(
                        renderable=True,
                        noSurfaceShader=True,
                        empty=True,
                        name=f'rfm_{safe}SG'
                    )
                    cmds.connectAttr(
                        f'{pxr_surf}.outColor', f'{sg}.surfaceShader', force=True
                    )

                    # Specular roughness (UsdPreviewSurface roughness → PxrSurface)
                    try:
                        cmds.setAttr(f'{pxr_surf}.specularRoughness', roughness)
                    except Exception:
                        pass

                    # Metallic approximation: reduce diffuse gain for metallic surfaces.
                    if metallic > 0.1:
                        try:
                            cmds.setAttr(f'{pxr_surf}.diffuseGain', max(0.05, 1.0 - metallic))
                        except Exception:
                            pass

                    # ── Diffuse: PxrTexture node or static color ───────────────
                    if diffuse_tex:
                        pxr_tex = cmds.shadingNode(
                            'PxrTexture', asTexture=True, name=f'rfm_tex_{safe}'
                        )
                        # Set texture file path
                        try:
                            cmds.setAttr(f'{pxr_tex}.filename', diffuse_tex, type='string')
                        except Exception:
                            pass
                        # Convert sRGB → linear for physically correct shading
                        try:
                            cmds.setAttr(f'{pxr_tex}.linearize', 1)
                        except Exception:
                            pass
                        # Connect PxrTexture.resultRGB → PxrSurface.diffuseColor
                        try:
                            cmds.connectAttr(
                                f'{pxr_tex}.resultRGB', f'{pxr_surf}.diffuseColor',
                                force=True
                            )
                            tex_count += 1
                        except Exception:
                            pass
                    else:
                        # No texture: copy static diffuseColor from UsdPreviewSurface
                        try:
                            dc_inp = preview_shader.GetInput('diffuseColor')
                            if dc_inp and not dc_inp.HasConnectedSource():
                                dc_val = dc_inp.Get()
                                if dc_val is not None:
                                    cmds.setAttr(
                                        f'{pxr_surf}.diffuseColor',
                                        float(dc_val[0]),
                                        float(dc_val[1]),
                                        float(dc_val[2]),
                                        type='double3'
                                    )
                        except Exception:
                            pass

                    mat_path_to_sg[mat_key] = sg
                    created_count += 1

                except Exception as node_err:
                    self.logger.debug(
                        f"[RFM] Maya shader creation skipped for {mat_name}: {node_err}"
                    )
                    continue

            if created_count == 0:
                return 0

            if not _cache_used:
                # Strategy 2 (synthetic) ran — log what was created
                tex_label = (
                    f'{tex_count} with PxrTexture' if tex_count else 'static colors'
                )
                self.logger.info(
                    f"[RFM] Created {created_count} Maya PxrSurface shaders from USD "
                    f"data ({tex_label}) \u2014 visible in Hypershade + renderable via rfm2 RIS"
                )

            # ── Bind materials to USD mesh prims + register proxy with rfm2 ──
            #
            # rfm2 translates a mayaUsdProxyShape as a single PxrUSD procedural.
            # The PxrUSD procedural opens the USD stage at render time and uses
            # material:binding + outputs:ri:surface (authored in materials.usda)
            # to resolve per-mesh RenderMan shaders.  Maya SG membership does
            # NOT drive per-mesh materials — but the proxy shape itself MUST be
            # a member of a RenderMan SG (not initialShadingGroup) for rfm2 to
            # include it in the RIB and mark it as "uses RenderMan materials".
            #
            # Two-phase approach:
            #   Phase A: Session-layer material:binding (for Hydra VP2 display)
            #   Phase B: Always assign proxy shape to a PxrSurface SG (for rfm2)

            # ── Phase A: Session-layer material:binding for VP2 Hydra ──────────
            bound = 0
            total_bindings = sum(
                1 for mk in mesh_bindings.values() if mk in mat_path_to_sg
            )
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
                        for mesh_path_str, mat_key in mesh_bindings.items():
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
                                api = UsdShade.MaterialBindingAPI.Apply(
                                    mesh_prim
                                )
                                api.Bind(UsdShade.Material(mat_prim))
                                bound += 1
                    finally:
                        live_stage.SetEditTarget(prev_target)
            except ImportError:
                pass  # mayaUsd.lib unavailable — session bindings skipped
            except Exception as phase_a_err:
                self.logger.debug(
                    f"[RFM] Session-layer binding: {phase_a_err}"
                )

            if bound > 0:
                self.logger.info(
                    f"[RFM] Bound {bound}/{total_bindings} materials "
                    f"to USD mesh prims (session layer — VP2 Hydra display)"
                )

            # ── Phase B: Assign proxy shape to PxrSurface SG for rfm2 ─────────
            # MANDATORY — rfm2's Maya translator checks SG membership on the
            # shape node.  If the shape is in `initialShadingGroup` (Lambert),
            # rfm2 never emits a RenderMan surface, and the PxrUSD procedural
            # renders with no material (solid grey / invisible).
            #
            # By moving the proxy to a PxrSurface SG, rfm2 marks the shape as
            # "has RenderMan shading" in the RIB.  The PxrUSD procedural then
            # uses the USD-authored outputs:ri:surface (in materials.usda) for
            # per-mesh material resolution — the Maya SG is only used to flag
            # the shape, not to drive per-mesh assignments.
            proxy_assigned_sg = False
            if mat_path_to_sg:
                # Prefer a SG whose PxrSurface has a PxrTexture on diffuseColor
                # (i.e. a textured "skin" or clothing material rather than the
                # grey fallback `initialShadingGroup` equivalent).  This makes
                # the proxy shape's representative Hypershade material meaningful
                # and ensures any unbound-mesh fallback is a textured surface.
                best_sg: Optional[str] = None
                for _candidate_key, sg_candidate in mat_path_to_sg.items():
                    try:
                        surf_nodes = cmds.listConnections(
                            f'{sg_candidate}.surfaceShader',
                            source=True,
                            destination=False,
                        ) or []
                        for surf in surf_nodes:
                            if cmds.nodeType(surf) != 'PxrSurface':
                                continue
                            tex_inputs = cmds.listConnections(
                                f'{surf}.diffuseColor',
                                source=True,
                                destination=False,
                            ) or []
                            if any(
                                cmds.nodeType(t) == 'PxrTexture'
                                for t in tex_inputs
                            ):
                                best_sg = sg_candidate
                                break
                    except Exception:
                        pass
                    if best_sg:
                        break
                first_sg = best_sg or next(iter(mat_path_to_sg.values()))

                try:
                    # Remove from initialShadingGroup so rfm2 doesn't see Lambert
                    try:
                        cmds.sets(
                            proxy_shape, remove='initialShadingGroup'
                        )
                    except Exception:
                        pass  # may not be a member

                    cmds.sets(
                        proxy_shape, edit=True, forceElement=first_sg
                    )
                    proxy_assigned_sg = True
                    tex_flag = " [textured]" if best_sg else ""
                    self.logger.info(
                        f"[RFM] Proxy shape → {first_sg}{tex_flag} "
                        f"(rfm2 RenderMan shading enabled; per-mesh materials "
                        f"driven by USD outputs:ri:surface in materials.usda)"
                    )
                except Exception as sg_err:
                    self.logger.warning(
                        f"[RFM] Could not assign proxy shape to SG: {sg_err}"
                    )

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

            return created_count

        except Exception as e:
            self.logger.warning(f"[RFM] Maya shader creation failed: {e}")
            self.logger.debug(traceback.format_exc())
            return 0

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
            mat_preview: dict = {}        # Sdf.Path → UsdShade.Shader (UsdPreviewSurface)
            mat_uv_textures: dict = {}    # Sdf.Path → list[UsdShade.Shader] (UsdUVTexture)

            for prim in base_stage.Traverse():
                if prim.GetTypeName() != 'Shader':
                    continue
                shader = UsdShade.Shader(prim)
                try:
                    sid = shader.GetShaderId() or ''
                except Exception:
                    try:
                        sid = shader.GetIdAttr().Get() or ''
                    except Exception:
                        sid = ''

                if sid not in ('UsdPreviewSurface', 'UsdUVTexture'):
                    continue

                # Walk up the hierarchy to find the enclosing Material prim.
                # Shaders may be direct children (depth 1) or inside a NodeGraph
                # subscope (depth 2+) — the ancestor walk handles either case.
                ancestor = prim.GetParent()
                mat_prim = None
                while ancestor and ancestor.IsValid():
                    if ancestor.GetTypeName() == 'Material':
                        mat_prim = ancestor
                        break
                    ancestor = ancestor.GetParent()

                if mat_prim is None:
                    continue

                mat_path = mat_prim.GetPath()
                if sid == 'UsdPreviewSurface':
                    if mat_path not in mat_preview:          # keep first found
                        mat_preview[mat_path] = shader
                elif sid == 'UsdUVTexture':
                    mat_uv_textures.setdefault(mat_path, []).append(shader)

            # ── Step 2: Author PxrPreviewSurface overrides for every material ──
            for mat_path, preview_shader in mat_preview.items():

                # ── Find diffuse texture via connection chain ─────────────────
                # Follow diffuseColor's connection to its upstream UsdUVTexture.
                # This is reliable regardless of whether the texture node is a
                # sibling, inside a NodeGraph, or deeply nested.
                diffuse_tex_file: Optional[str] = None
                try:
                    dc_inp = preview_shader.GetInput('diffuseColor')
                    if dc_inp and dc_inp.HasConnectedSource():
                        for conn_path in dc_inp.GetAttr().GetConnections():
                            src_prim = base_stage.GetPrimAtPath(
                                conn_path.GetPrimPath()
                            )
                            if src_prim and src_prim.IsValid():
                                src_shader = UsdShade.Shader(src_prim)
                                try:
                                    src_id = src_shader.GetShaderId() or ''
                                except Exception:
                                    src_id = ''
                                if src_id == 'UsdUVTexture':
                                    file_inp = src_shader.GetInput('file')
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
                            if 'normal' in cname or 'nrm' in cname or 'nml' in cname:
                                continue
                            file_inp = uv_shader.GetInput('file')
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

                # PxrPreviewSurface — RenderMan 27.x ships this shader in
                # $RMANTREE/lib/shaders/ as a first-class RIS surface shader
                # that implements the same Disney PBR model as UsdPreviewSurface.
                pxr_surf_path = mat_path.AppendChild('PxrPreviewSurface')
                pxr_surf_prim = sub_stage.DefinePrim(pxr_surf_path, 'Shader')
                pxr_surf = UsdShade.Shader(pxr_surf_prim)
                pxr_surf.CreateIdAttr('PxrPreviewSurface')

                # ── Copy scalar inputs ────────────────────────────────────────
                for attr_name in ('roughness', 'metallic', 'opacity'):
                    try:
                        inp = preview_shader.GetInput(attr_name)
                        if inp and not inp.HasConnectedSource():
                            val = inp.Get()
                            if val is not None:
                                pxr_surf.CreateInput(
                                    attr_name, Sdf.ValueTypeNames.Float
                                ).Set(float(val))
                    except Exception:
                        pass

                # ── diffuseColor: connect PxrTexture or copy static value ─────
                if diffuse_tex_file:
                    pxr_tex_path = mat_path.AppendChild('PxrTexture_diffuse')
                    pxr_tex_prim = sub_stage.DefinePrim(pxr_tex_path, 'Shader')
                    pxr_tex = UsdShade.Shader(pxr_tex_prim)
                    pxr_tex.CreateIdAttr('PxrTexture')
                    pxr_tex.CreateInput(
                        'filename', Sdf.ValueTypeNames.Asset
                    ).Set(Sdf.AssetPath(diffuse_tex_file))
                    # linearize=1: convert sRGB PNG/JPEG to linear before shading
                    pxr_tex.CreateInput(
                        'linearize', Sdf.ValueTypeNames.Int
                    ).Set(1)
                    tex_out = pxr_tex.CreateOutput(
                        'resultRGB', Sdf.ValueTypeNames.Color3f
                    )
                    pxr_surf.CreateInput(
                        'diffuseColor', Sdf.ValueTypeNames.Color3f
                    ).ConnectToSource(tex_out)
                    tex_count += 1
                else:
                    try:
                        dc_inp = preview_shader.GetInput('diffuseColor')
                        if dc_inp and not dc_inp.HasConnectedSource():
                            dc_val = dc_inp.Get()
                            if dc_val is not None:
                                pxr_surf.CreateInput(
                                    'diffuseColor', Sdf.ValueTypeNames.Color3f
                                ).Set(Gf.Vec3f(
                                    float(dc_val[0]),
                                    float(dc_val[1]),
                                    float(dc_val[2])
                                ))
                    except Exception:
                        pass

                # ── Wire outputs:ri:surface via the proper render-context API ─
                # UsdShadeMaterial.CreateSurfaceOutput('ri') creates the
                # outputs:ri:surface attribute with correct USD schema metadata.
                pxr_surf_out = pxr_surf.CreateOutput('out', Sdf.ValueTypeNames.Token)
                ri_surface_out = UsdShade.Material(mat_override).CreateSurfaceOutput('ri')
                ri_surface_out.ConnectToSource(pxr_surf_out)

                rfm_count += 1

            if rfm_count > 0:
                self.logger.info(
                    f"[RFM] Wrote PxrPreviewSurface ri:surface for {rfm_count} "
                    f"materials ({tex_count} with PxrTexture diffuse) in "
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
