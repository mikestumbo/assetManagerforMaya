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
    mel  = None   # type: ignore[assignment]
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
                    # Materials live inside the USD stage — rendered by VP2, not Maya Hypershade
                    if result.usd_materials > 0:
                        self.logger.info(
                            f"[LOOKDEV] {result.usd_materials} USD materials rendered via VP2 "
                            f"(UsdPreviewSurface — these are USD-native, not Maya Hypershade shaders)"
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
                    # Used .rig.mb fallback - safe to cleanup temp files
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self.logger.info("[CLEANUP] Cleaned up temp USDZ extraction")

        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            result.error_message = str(e)

        return result

    def _extract_usdz(
        self,
        usdz_path: Path
    ) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """
        Extract USDZ package

        Returns:
            (usd_path, rig_mb_path, temp_dir) or (None, None, None) on failure
        """
        try:
            import zipfile
            import tempfile

            # Create temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix='usdz_import_'))

            usd_path = None
            rig_mb_path = None

            with zipfile.ZipFile(str(usdz_path), 'r') as zf:
                for name in zf.namelist():
                    zf.extract(name, str(temp_dir))
                    extracted_path = temp_dir / name

                    if name.endswith(('.usd', '.usdc', '.usda')):
                        usd_path = extracted_path
                        self.logger.info(f"[FILE] Extracted USD: {name}")
                    elif name.endswith('.rig.mb') or name.endswith('.rig.ma'):
                        rig_mb_path = extracted_path
                        self.logger.info(f"[PACKAGE] Extracted rig backup: {name}")

            return usd_path, rig_mb_path, temp_dir

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
                    from pxr import Usd, UsdSkel  # type: ignore
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
                cmds.setAttr(f"{proxy_shape}.filePath", str(usd_path), type='string')

                # Enable proxy drawing
                cmds.setAttr(f"{proxy_shape}.loadPayloads", True)

                # IMPORTANT: For skinned meshes, set draw modes
                try:
                    cmds.setAttr(f"{proxy_shape}.drawProxyPurpose", True)
                    cmds.setAttr(f"{proxy_shape}.drawRenderPurpose", True)
                    cmds.setAttr(f"{proxy_shape}.drawGuidePurpose", False)
                except Exception:
                    pass  # Attribute may not exist in all Maya versions

                # WORKAROUND: Force stage reload to ensure skeleton bindings resolve correctly
                # Toggling the file path forces a clean reload.
                try:
                    # Store the path
                    file_path = cmds.getAttr(f"{proxy_shape}.filePath")
                    # Clear and reset to force reload
                    cmds.setAttr(f"{proxy_shape}.filePath", "", type='string')
                    cmds.refresh()
                    cmds.setAttr(f"{proxy_shape}.filePath", file_path, type='string')
                    cmds.refresh()
                    self.logger.info("[REFRESH] Forced stage reload for skeleton imaging")
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
                            # Switch to VP2.0 if needed
                            renderer = cmds.modelEditor(panel, query=True, rendererName=True)
                            if renderer != 'vp2Renderer':
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

                # Open USD Layer Editor if requested (Option B animation authoring)
                if options.open_layer_editor:
                    self._open_usd_layer_editor(proxy_shape)

                return True
            else:
                self.logger.warning("[ERROR] No USD proxy shapes found after import")
                return False

        except Exception as e:
            self.logger.error(f"USD import failed: {e}")
            import traceback
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
            from pxr import Usd  # pyright: ignore[reportMissingImports]

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
                    from pxr import Sdf  # pyright: ignore[reportMissingImports]
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
            from pxr import Usd, UsdShade, UsdGeom, Gf, Vt  # type: ignore

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
            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Mesh':
                    continue
                try:
                    color = None

                    # ComputeBoundMaterial handles full USD binding resolution
                    # including inherited and collection-based bindings.
                    bound_mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
                    if bound_mat and bound_mat.GetPrim().IsValid():
                        mat_prim_path = bound_mat.GetPrim().GetPath()
                        color = mat_path_to_color.get(mat_prim_path)
                        if color is None:
                            # Bound material exists but was texture-driven (None
                            # sentinel) or not in our map — name-hash the material.
                            color = self._rfm_name_color(bound_mat.GetPrim().GetName())

                    if color is None:
                        # No material bound at all — name-hash the mesh itself
                        # so it still gets a unique non-grey display colour.
                        color = self._rfm_name_color(prim.GetName())

                    UsdGeom.Gprim(prim).CreateDisplayColorAttr(
                        Vt.Vec3fArray([Gf.Vec3f(color[0], color[1], color[2])])
                    )
                    display_colored += 1
                except Exception:
                    continue

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
            from pxr import Usd, Sdf, UsdGeom  # pyright: ignore[reportMissingImports]

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

                sub_stage.Save()
                created_layers.append(layer_path)
                self.logger.info(f"   [LAYER] {layer_path.name}")

            # ── Create root .usda that composes everything ──
            root_path = base_dir / f"{asset_name}.root.usda"
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
            import traceback
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

            # Suppress deprecated-attribute errors printed when Maya loads
            # nested references inside the rig.mb (e.g. ".atlasStyle" from
            # PxrTexture nodes in RfM 27.x era files).  These are harmless
            # forward-compatibility warnings — suppressing them keeps the
            # Script Editor clean without hiding any real failures.
            # Suppress deprecated-attribute errors from the nested file load.
            # scriptEditorInfo is a global command — no 'edit' flag needed.
            try:
                cmds.scriptEditorInfo(
                    suppressErrors=True,
                    suppressWarnings=True,
                    suppressInfo=True,
                )
            except Exception:
                pass

            try:
                cmds.file(
                    str(rig_mb_path),
                    reference=True,
                    namespace=namespace,
                    returnNewNodes=False,
                    loadReferenceDepth="all"
                )
                self.logger.info("[RIG] Referenced .rig.mb for controller extraction")
            except Exception as ref_err:
                self.logger.warning(
                    f"[RIG] Could not reference .rig.mb: {ref_err}"
                )
                return None
            finally:
                # Always restore all output channels immediately.
                try:
                    cmds.scriptEditorInfo(
                        suppressErrors=False,
                        suppressWarnings=False,
                        suppressInfo=False,
                    )
                except Exception:
                    pass

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
                    f"[RIG] Extracted {len(controllers)} controllers, "
                    f"{len(mappings)} controller→joint mappings"
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
            import traceback
            self.logger.error(traceback.format_exc())
            return None

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
            from pxr import (  # pyright: ignore[reportMissingImports]
                Gf, Sdf, UsdGeom, Vt
            )

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
            import traceback
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
            import json
            from pxr import Usd, Sdf, UsdSkel  # pyright: ignore[reportMissingImports]

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
            import traceback
            self.logger.debug(traceback.format_exc())

