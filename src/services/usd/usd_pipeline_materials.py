"""
Material/texture mixin: RenderMan→UsdPreview, colour sampling, packaging.

Auto-generated mixin — do not edit directly; edit usd_pipeline.py then re-split.
"""
from __future__ import annotations

import logging
import os
import traceback
import zipfile
from pathlib import Path
from typing import Callable, Optional

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
    ExportOptions,
)


class MaterialsMixin:
    # ── Attribute stubs (provided by UsdPipeline.__init__) ────────────
    logger: logging.Logger
    _maya_available: bool
    _usd_available: bool
    _mayausd_available: bool
    _progress_callback: Optional[Callable[[str, int], None]]

    def _sample_pxr_texture_color(
        self, rfm_node: str, color_attr: str
    ):
        """
        Follow a PxrTexture connection on *rfm_node.color_attr* and return
        an average Gf.Vec3f sampled from that texture file, or None on failure.

        Connection traversal (most reliable first):
          1. connectionInfo(sourceFromDestination) — direct single-source lookup
          2. listConnections on compound attr  e.g. .baseColor
          3. listConnections on first child    e.g. .baseColorR
          4. One level deeper for each candidate found above

        File sampling (first available library wins):
          1. PIL / Pillow
          2. OpenImageIO (ships with RenderMan for Maya 24+)
        """
        try:
            from pxr import Gf  # type: ignore
            import re
            import os

            if cmds is None:
                return None

            # ── Step 1: Collect upstream candidate nodes ─────────────────────
            candidates: list = []

            # 1a. Direct source plug via connectionInfo (most reliable)
            try:
                src = cmds.connectionInfo(
                    f"{rfm_node}.{color_attr}", sourceFromDestination=True
                )
                if src:
                    # "PxrTexture1.resultRGB" → "PxrTexture1"
                    src_node = src.split(".")[0]
                    if src_node:
                        candidates.append(src_node)
            except Exception:
                pass

            # 1b. listConnections on compound attr (colour compound), no skip
            try:
                lc = (
                    cmds.listConnections(
                        f"{rfm_node}.{color_attr}",
                        source=True,
                        destination=False,
                    )
                    or []
                )
                candidates.extend(lc)
            except Exception:
                pass

            # 1c. listConnections on the first scalar child (".baseColorR")
            #     Maya sometimes connects at component level
            try:
                lc_r = (
                    cmds.listConnections(
                        f"{rfm_node}.{color_attr}R",
                        source=True,
                        destination=False,
                    )
                    or []
                )
                candidates.extend(lc_r)
            except Exception:
                pass

            # 1d. Walk one level deeper for each candidate so far
            first_pass = list(candidates)
            for node in first_pass:
                try:
                    deeper = (
                        cmds.listConnections(
                            node,
                            source=True,
                            destination=False,
                        )
                        or []
                    )
                    candidates.extend(deeper)
                except Exception:
                    pass

            # De-duplicate while preserving insertion order
            seen: set = set()
            unique_candidates: list = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    unique_candidates.append(c)

            if not unique_candidates:
                self.logger.debug(
                    f"   [TEX-DIAG] {rfm_node}.{color_attr}: no upstream nodes found "
                    f"via connectionInfo or listConnections"
                )
                return None

            self.logger.info(
                f"   [TEX-DIAG] {rfm_node}.{color_attr}: candidates = "
                f"{unique_candidates[:6]}"  # cap at 6 to keep log tidy
            )

            # ── Step 2: Find texture file path ──────────────────────────────
            FILENAME_ATTRS = (
                "filename",         # PxrTexture (RenderMan for Maya)
                "textureName",      # some RfM variants
                "fileTextureName",  # Maya file node
                "imageName",        # misc
            )

            tex_path = None
            for node in unique_candidates:
                for attr in FILENAME_ATTRS:
                    try:
                        val = cmds.getAttr(f"{node}.{attr}")
                        if val and isinstance(val, str) and len(val) > 4:
                            tex_path = val
                            self.logger.info(
                                f"   [TEX-DIAG] Found path on {node}.{attr}: {val}"
                            )
                            break
                    except Exception:
                        continue
                if tex_path:
                    break

            if not tex_path:
                # Log all attrs on the first candidate to help future diagnosis
                if unique_candidates:
                    try:
                        attrs = cmds.listAttr(unique_candidates[0], scalar=True) or []
                        str_attrs = [a for a in attrs if 'file' in a.lower()
                                     or 'tex' in a.lower() or 'image' in a.lower()
                                     or 'name' in a.lower()]
                        self.logger.info(
                            f"   [TEX-DIAG] No filename attr on {unique_candidates[0]}. "
                            f"Likely attrs: {str_attrs[:10]}"
                        )
                    except Exception:
                        pass
                return None

            # ── Step 3: Resolve UDIM / tile tokens ──────────────────────────
            tex_path = re.sub(r'<[Uu][Dd][Ii][Mm]>', '1001', tex_path)
            tex_path = re.sub(r'#{4}', '1001', tex_path)
            tex_path = re.sub(r'%04d', '1001', tex_path)

            # ── Step 4: Verify file exists, try alt extensions ───────────────
            if not os.path.exists(tex_path):
                base, _ext = os.path.splitext(tex_path)
                for alt_ext in ('.tx', '.exr', '.tif', '.tiff', '.png', '.jpg', '.jpeg'):
                    candidate = base + alt_ext
                    if os.path.exists(candidate):
                        tex_path = candidate
                        break
                else:
                    self.logger.info(
                        f"   [TEX-DIAG] Texture file not found on disk: {tex_path}"
                    )
                    return None

            self.logger.info(
                f"   [TEX-DIAG] Sampling texture: {os.path.basename(tex_path)}"
            )

            # ── Resolve RenderMan .tex → source image ────────────────────────
            # RenderMan compiles source textures (PNG/EXR/TIFF) to a binary .tex
            # format that PIL and most image libs cannot read.  The convention is
            # "source.png.tex" — stripping the trailing ".tex" gets us back to the
            # original source file.  Try that first; if it doesn't exist on disk,
            # fall through and let PIL/OIIO try the .tex directly.
            if tex_path.lower().endswith('.tex'):
                source_candidate = tex_path[:-4]   # "body.png.tex" → "body.png"
                if os.path.exists(source_candidate):
                    self.logger.info(
                        f"   [TEX-DIAG] RenderMan .tex → source: "
                        f"{os.path.basename(source_candidate)}"
                    )
                    tex_path = source_candidate
                else:
                    self.logger.info(
                        f"   [TEX-DIAG] .tex source not on disk "
                        f"({os.path.basename(source_candidate)}), trying .tex directly"
                    )
                    # ── One-time dir listing so we can see actual filenames ──
                    _sc_dir = os.path.dirname(source_candidate)
                    try:
                        _dir_files = sorted(os.listdir(_sc_dir))[:12]
                        self.logger.info(
                            f"   [TEX-DIAG] Contents of {os.path.basename(_sc_dir)}/: "
                            f"{_dir_files}"
                        )
                    except Exception:
                        pass

            # ── Store resolved path before PIL sampling ────────────────────────
            # Capture the path now so _convert_renderman_materials_to_usd_preview
            # can wire a UsdUVTexture even when PIL/OIIO sampling fails below.
            # Only cache non-.tex paths — bare RenderMan .tex files are not
            # displayable by standard USD image loaders.
            if not tex_path.lower().endswith('.tex') and os.path.isfile(tex_path):
                self._last_resolved_tex_path = tex_path

            # ── Attempt 0: user-supplied texture folder ───────────────────────
            # The user points us at a folder of source PNGs — either the flat
            # project renderman folder (Substance Painter exports) or the
            # RenderMan Asset Library root whose subfolders end in .rma.
            # Both use the same source filename; only the directory layout differs:
            #
            #   Flat   : <path>/<texname>.png
            #            e.g. renderman/Veteran/Veteran_V008_Base_color_..._1001.png
            #
            #   .rma   : <path>/<Mat>.rma/<texname>.png
            #            e.g. RenderManAssetLibrary/.../Body.rma/Veteran_V008_...png
            #
            # Maya's PxrTexture.filename already tells us which .rma subfolder the
            # texture belongs to, so we use that to target the exact folder instead
            # of walking every .rma directory.
            _rma_lib = ""
            try:
                _rma_lib = getattr(
                    getattr(self, "_current_export_options", None),
                    "renderman_library_path",
                    ""
                ) or ""
            except Exception:
                _rma_lib = ""

            if _rma_lib and not os.path.isdir(_rma_lib):
                self.logger.info(f"   [TEX-DIAG] src-lib: path not found on disk: {_rma_lib}")
            if _rma_lib and os.path.isdir(_rma_lib):
                # ── One-shot listing diagnostic (first call only) ─────────────
                if not getattr(self, "_rma_lib_listed", False):
                    self._rma_lib_listed = True
                    try:
                        top_entries = sorted(os.listdir(_rma_lib))
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib listing ({len(top_entries)} entries): "
                            + ", ".join(top_entries[:30])
                            + ("..." if len(top_entries) > 30 else "")
                        )
                        # For each subdirectory, list its first 10 files
                        for entry in top_entries[:10]:
                            entry_path = os.path.join(_rma_lib, entry)
                            if os.path.isdir(entry_path):
                                sub_files = sorted(os.listdir(entry_path))
                                self.logger.info(
                                    f"   [TEX-DIAG] src-lib subdir '{entry}' "
                                    f"({len(sub_files)} files): "
                                    + ", ".join(sub_files[:10])
                                    + ("..." if len(sub_files) > 10 else "")
                                )
                    except Exception as _list_err:
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib listing error: {_list_err}"
                        )

                tex_basename = os.path.basename(tex_path)
                # Strip .tex to recover the original source filename:
                # "Veteran_V008_Base_color_..._1001.png.tex"
                # → "Veteran_V008_Base_color_..._1001.png"
                tex_basename_raw = (
                    tex_basename[:-4]
                    if tex_basename.lower().endswith('.tex')
                    else tex_basename
                )
                self.logger.info(
                    f"   [TEX-DIAG] src-lib seeking: '{tex_basename_raw}'"
                )

                def _sample_png(path: str) -> "Optional[Gf.Vec3f]":
                    """Read *path* with PIL, return Gf.Vec3f color or None.

                    Source-library PNGs are real PBR albedo textures. Their raw
                    averages are physically accurate but often dark (< 0.2) for
                    realistic materials. We apply a proportional brightness lift
                    — scaling all three channels equally so the brightest channel
                    reaches TARGET_V — which preserves the exact hue ratios from
                    the source while making the colour clearly visible in the viewer.
                    No saturation forcing is applied, so the hue stays true.
                    """
                    try:
                        from PIL import Image  # type: ignore
                        import numpy as np     # type: ignore
                        with Image.open(path).convert('RGB') as img:
                            thumb = img.resize((32, 32), Image.LANCZOS)
                            arr = np.array(thumb, dtype=float) / 255.0
                            r = float(arr[:, :, 0].mean())
                            g = float(arr[:, :, 1].mean())
                            b = float(arr[:, :, 2].mean())
                            if r + g + b > 0.02:
                                # Proportional lift — preserve hue, boost to visibility
                                TARGET_V = 0.45
                                max_ch = max(r, g, b)
                                if 0.02 < max_ch < TARGET_V:
                                    scale = TARGET_V / max_ch
                                    r = min(r * scale, 1.0)
                                    g = min(g * scale, 1.0)
                                    b = min(b * scale, 1.0)
                                color_out = Gf.Vec3f(
                                    max(0.0, min(1.0, r)),
                                    max(0.0, min(1.0, g)),
                                    max(0.0, min(1.0, b)),
                                )
                                self.logger.info(
                                    f"   [TEX] {os.path.basename(path)} "
                                    f"(src-lib): ({r:.3f}, {g:.3f}, {b:.3f})"
                                )
                                self._last_resolved_tex_path = path
                                return color_out
                    except ImportError:
                        self.logger.info(
                            "   [TEX-DIAG] PIL not available for src-lib scan"
                        )
                    except Exception:
                        pass
                    return None

                # Extract .rma folder info early — needed by multiple priorities.
                orig_rma_dir = os.path.dirname(tex_path)
                orig_rma_folder = os.path.basename(orig_rma_dir)  # e.g. "Body.rma"
                rma_stem = (
                    orig_rma_folder[:-4]
                    if orig_rma_folder.lower().endswith('.rma')
                    else orig_rma_folder
                )

                # ── Priority 1: flat folder — exact filename match ─────────────
                flat_candidate = os.path.join(_rma_lib, tex_basename_raw)
                if os.path.exists(flat_candidate):
                    result_color = _sample_png(flat_candidate)
                    if result_color is not None:
                        return result_color

                # ── Priority 1b: flat folder — fuzzy Base_color match ──────────
                # Handles backups where files are named "{MatName}_Base_color.png"
                # but the .rma stem differs slightly (e.g. LfButn01 → LfButton_01,
                # LfZipr → LfZipper, LwrTeeth → LwrTeeth_3).
                # Only applies to base-color textures (the ones that drive diffuse).
                if 'base_color' in tex_basename_raw.lower():
                    try:
                        import difflib
                        _bc_files = [
                            f for f in os.listdir(_rma_lib)
                            if f.lower().endswith('.png')
                            and 'base_color' in f.lower()
                        ]
                        _matched_bc = None
                        _stem_lo = rma_stem.lower()
                        # Step A: exact prefix "{rma_stem}_"
                        for f in _bc_files:
                            if f.lower().startswith(_stem_lo + '_'):
                                _matched_bc = f
                                break
                        # Step B: backup stem starts with rma_stem
                        # (handles LwrTeeth → LwrTeeth_3_Base_color.png)
                        if _matched_bc is None:
                            for f in _bc_files:
                                if f.lower().startswith(_stem_lo):
                                    _matched_bc = f
                                    break
                        # Step C: difflib fuzzy on the portion before "_Base_color"
                        # (handles LfButn01 → LfButton_01, LfZipr → LfZipper)
                        if _matched_bc is None and _bc_files:
                            _bc_stems = []
                            for f in _bc_files:
                                idx = f.lower().find('_base_color')
                                _bc_stems.append(f[:idx] if idx != -1 else f)
                            best = difflib.get_close_matches(
                                rma_stem, _bc_stems, n=1, cutoff=0.5
                            )
                            if best:
                                _matched_bc = _bc_files[_bc_stems.index(best[0])]
                        if _matched_bc:
                            self.logger.info(
                                f"   [TEX-DIAG] src-lib fuzzy match: "
                                f"'{rma_stem}' → '{_matched_bc}'"
                            )
                            result_color = _sample_png(
                                os.path.join(_rma_lib, _matched_bc)
                            )
                            if result_color is not None:
                                return result_color
                    except Exception as _fuzz_err:
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib fuzzy match error: {_fuzz_err}"
                        )

                # ── Priority 2: targeted .rma subfolder ──────────────────────
                # Maya's tex_path tells us which .rma subfolder owns this
                # texture (e.g. Body.rma).  Use that name under the user's
                # supplied root so we land in exactly the right place without
                # having to walk every .rma directory.
                if orig_rma_folder.lower().endswith('.rma'):
                    targeted = os.path.join(
                        _rma_lib, orig_rma_folder, tex_basename_raw
                    )
                    if os.path.exists(targeted):
                        result_color = _sample_png(targeted)
                        if result_color is not None:
                            return result_color
                    else:
                        self.logger.info(
                            f"   [TEX-DIAG] src-lib targeted miss: "
                            f"{orig_rma_folder}/{tex_basename_raw}"
                        )

                # ── Priority 3: walk all .rma subfolders as last resort ───────
                try:
                    for rma_folder in os.listdir(_rma_lib):
                        if not rma_folder.lower().endswith('.rma'):
                            continue
                        if rma_folder == orig_rma_folder:
                            continue  # already tried above
                        rma_full = os.path.join(_rma_lib, rma_folder)
                        if not os.path.isdir(rma_full):
                            continue
                        rma_candidate = os.path.join(rma_full, tex_basename_raw)
                        if os.path.exists(rma_candidate):
                            result_color = _sample_png(rma_candidate)
                            if result_color is not None:
                                return result_color
                except Exception as lib_err:
                    self.logger.info(
                        f"   [TEX-DIAG] src-lib .rma scan error: {lib_err}"
                    )

            # ── Attempt 1: Maya MImage — reads .tex via RenderMan plugin ────
            # RenderMan registers a .tex format reader with Maya when the plugin
            # is loaded. MImage.readFromFile() goes through Maya's plugin chain,
            # so it can decode .tex files that OIIO/PIL cannot.
            try:
                from maya import OpenMaya as _om  # type: ignore
                import numpy as _np_mimg
                _mimg = _om.MImage()
                _mimg.readFromFile(tex_path)
                _w, _h = _om.MScriptUtil(), _om.MScriptUtil()
                _wp = _w.asUintPtr()
                _hp = _h.asUintPtr()
                _mimg.getSize(_wp, _hp)
                _width = _om.MScriptUtil.getUint(_wp)
                _height = _om.MScriptUtil.getUint(_hp)
                if _width > 0 and _height > 0:
                    _mimg.verticalFlip()  # MImage is bottom-up
                    _char_arr = _mimg.pixels()
                    _byte_arr = _np_mimg.frombuffer(
                        bytes(_char_arr[:_width * _height * 4]),
                        dtype=_np_mimg.uint8
                    ).reshape(_height, _width, 4)
                    arr_f = _byte_arr[:, :, :3].astype(float) / 255.0
                    r = float(arr_f[:, :, 0].mean())
                    g = float(arr_f[:, :, 1].mean())
                    b = float(arr_f[:, :, 2].mean())
                    if r + g + b > 0.02:
                        TARGET_V = 0.45
                        max_ch = max(r, g, b)
                        if 0.02 < max_ch < TARGET_V:
                            scale = TARGET_V / max_ch
                            r = min(r * scale, 1.0)
                            g = min(g * scale, 1.0)
                            b = min(b * scale, 1.0)
                        color_out = Gf.Vec3f(
                            max(0.0, min(1.0, r)),
                            max(0.0, min(1.0, g)),
                            max(0.0, min(1.0, b)),
                        )
                        self.logger.info(
                            f"   [TEX] {os.path.basename(tex_path)} "
                            f"(MImage): ({r:.3f}, {g:.3f}, {b:.3f})"
                        )
                        self._last_resolved_tex_path = tex_path
                        return color_out
            except Exception as _mimg_err:
                self.logger.info(
                    f"   [TEX-DIAG] MImage failed for "
                    f"{os.path.basename(tex_path)}: {_mimg_err}"
                )

            try:
                from PIL import Image  # type: ignore
                import numpy as np     # type: ignore

                with Image.open(tex_path).convert('RGB') as img:
                    thumb = img.resize((32, 32), Image.LANCZOS)
                    arr = np.array(thumb, dtype=float) / 255.0
                    r = float(arr[:, :, 0].mean())
                    g = float(arr[:, :, 1].mean())
                    b = float(arr[:, :, 2].mean())
                    if r + g + b > 0.02:
                        raw_color = Gf.Vec3f(
                            max(0.0, min(1.0, r)),
                            max(0.0, min(1.0, g)),
                            max(0.0, min(1.0, b)),
                        )
                        boosted = self._boost_color_for_display(raw_color)
                        if boosted is not None:
                            self.logger.info(
                                f"   [TEX] {os.path.basename(tex_path)}: "
                                f"({r:.3f}, {g:.3f}, {b:.3f}) via PIL → boosted {boosted}"
                            )
                            self._last_resolved_tex_path = tex_path
                            return boosted
                        self.logger.info(
                            f"   [TEX] {os.path.basename(tex_path)}: "
                            f"({r:.3f}, {g:.3f}, {b:.3f}) via PIL — achromatic, trying rma-scan"
                        )
            except ImportError:
                self.logger.info("   [TEX-DIAG] PIL not available")
            except Exception as pil_err:
                self.logger.info(f"   [TEX-DIAG] PIL failed: {pil_err}")

            # ── Attempt 2: OpenImageIO (ships with RfM 24+) ──────────────────
            try:
                import sys as _sys
                import glob as _glob
                _oiio_base = (
                    r"C:\Program Files\Pixar\RenderManProServer-*"
                    r"\lib\python3.11\Lib\site-packages\thirdparty"
                )
                for _p in _glob.glob(_oiio_base):
                    if _p not in _sys.path:
                        _sys.path.insert(0, _p)
                import OpenImageIO as oiio  # type: ignore

                def _oiio_sample(path: str):
                    """Try ImageInput then ImageBuf; return (r,g,b) tuple or None."""
                    import numpy as np  # type: ignore

                    # ── Strategy A: ImageInput.open ──────────────────────────
                    inp = oiio.ImageInput.open(path)
                    if inp is not None:
                        pixels = inp.read_image('float')
                        inp.close()
                        if pixels is not None:
                            arr = np.array(pixels)
                            if arr.ndim == 3 and arr.shape[2] >= 3:
                                return (
                                    float(arr[:, :, 0].mean()),
                                    float(arr[:, :, 1].mean()),
                                    float(arr[:, :, 2].mean()),
                                )
                        return None

                    # If ImageInput fails (returns None), log the reason.
                    _oiio_err = oiio.geterror()
                    self.logger.info(
                        f"   [TEX-DIAG] OIIO ImageInput.open returned None "
                        f"for {os.path.basename(path)}"
                        + (f": {_oiio_err}" if _oiio_err else "")
                    )

                    # ── Strategy B: ImageBuf (handles more format variants) ──
                    buf = oiio.ImageBuf(path)
                    if buf.has_error:
                        self.logger.info(
                            f"   [TEX-DIAG] OIIO ImageBuf also failed: {buf.geterror()}"
                        )
                        return None
                    spec = buf.spec()
                    if spec.nchannels < 3:
                        return None
                    pixels_b = buf.get_pixels(oiio.FLOAT)
                    if pixels_b is None:
                        return None
                    arr = np.array(pixels_b)
                    if arr.ndim == 3 and arr.shape[2] >= 3:
                        return (
                            float(arr[:, :, 0].mean()),
                            float(arr[:, :, 1].mean()),
                            float(arr[:, :, 2].mean()),
                        )
                    return None

                rgb = _oiio_sample(tex_path)
                if rgb is not None:
                    r, g, b = rgb
                    if r + g + b > 0.02:
                        raw_color = Gf.Vec3f(
                            max(0.0, min(1.0, r)),
                            max(0.0, min(1.0, g)),
                            max(0.0, min(1.0, b)),
                        )
                        boosted = self._boost_color_for_display(raw_color)
                        if boosted is not None:
                            self.logger.info(
                                f"   [TEX] {os.path.basename(tex_path)}: "
                                f"({r:.3f}, {g:.3f}, {b:.3f}) via OIIO → boosted {boosted}"
                            )
                            self._last_resolved_tex_path = tex_path
                            return boosted
                        self.logger.info(
                            f"   [TEX] {os.path.basename(tex_path)}: "
                            f"({r:.3f}, {g:.3f}, {b:.3f}) via OIIO — achromatic, trying rma-scan"
                        )
            except ImportError:
                self.logger.info("   [TEX-DIAG] OpenImageIO not available")
            except Exception as oiio_err:
                self.logger.info(f"   [TEX-DIAG] OIIO failed: {oiio_err}")

            # ── Last resort: scan the .rma package dir for any preview / source image ──
            # RenderMan Material Archives ship a rendered preview PNG (asset_100.png)
            # alongside the .tex files.  A naive mean over the whole preview is
            # unreliable because the image includes the grey background, a full-white
            # specular highlight at the top and a full-black shadow at the bottom.
            # Fix: crop to the centre 50 % of the image (where the diffuse midtone
            # lives), then exclude the remaining near-white / near-black pixels and
            # take the per-channel MEDIAN.  This gives a much cleaner approximation
            # of the actual diffuse colour than the old whole-image mean.
            try:
                rma_dir = os.path.dirname(tex_path)
                if os.path.isdir(rma_dir):
                    for fname in sorted(os.listdir(rma_dir)):
                        if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                            candidate = os.path.join(rma_dir, fname)
                            try:
                                from PIL import Image  # type: ignore
                                import numpy as np     # type: ignore
                                with Image.open(candidate).convert('RGB') as img:
                                    w, h = img.size
                                    # Centre-crop: keep the middle 50 % of each axis
                                    cx, cy = w // 2, h // 2
                                    mx = max(w // 4, 1)
                                    my = max(h // 4, 1)
                                    center = img.crop(
                                        (cx - mx, cy - my, cx + mx, cy + my)
                                    )
                                    thumb = center.resize((16, 16), Image.LANCZOS)
                                    arr = np.array(thumb, dtype=float) / 255.0
                                    pixels = arr.reshape(-1, 3)
                                    # Exclude near-black (shadow) and near-white (highlight)
                                    brightness = pixels.mean(axis=1)
                                    mask = (brightness > 0.12) & (brightness < 0.88)
                                    if mask.sum() >= 4:
                                        pixels = pixels[mask]
                                    r = float(np.median(pixels[:, 0]))
                                    g = float(np.median(pixels[:, 1]))
                                    b = float(np.median(pixels[:, 2]))
                                    if r + g + b > 0.02:
                                        raw_color = Gf.Vec3f(
                                            max(0.0, min(1.0, r)),
                                            max(0.0, min(1.0, g)),
                                            max(0.0, min(1.0, b)),
                                        )
                                        boosted = self._boost_color_for_display(raw_color)
                                        if boosted is not None:
                                            self.logger.info(
                                                f"   [TEX] {fname} (rma-scan): "
                                                f"({r:.3f}, {g:.3f}, {b:.3f}) → boosted {boosted}"
                                            )
                                            self._last_resolved_tex_path = candidate
                                            return boosted
                                        self.logger.info(
                                            f"   [TEX] {fname} (rma-scan): "
                                            f"({r:.3f}, {g:.3f}, {b:.3f}) achromatic — using name-hash"
                                        )
                            except Exception:
                                continue  # try next file
            except Exception as scan_err:
                self.logger.info(f"   [TEX-DIAG] rma-dir scan error: {scan_err}")

            self.logger.info(
                f"   [TEX-DIAG] Sampling failed for {os.path.basename(tex_path)} — "
                f"no supported image library could read it"
            )
            return None

        except Exception as outer_err:
            self.logger.info(f"   [TEX-DIAG] Unexpected error: {outer_err}")
            return None

    def _rfm_name_color(self, name: str) -> "Gf.Vec3f":
        """Generate a unique, visually distinct color from a material name.

        Uses MD5 hash → hue so that every material gets a consistent, spread-out
        hue regardless of alphabetical ordering.  Saturation and value are fixed
        at mid-range so colors are clearly visible in VP2 without being garish.
        This is used as a last-resort fallback when RenderMan .tex textures cannot
        be read by the available image libraries.
        """
        import hashlib
        import colorsys
        from pxr import Gf  # type: ignore
        h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)  # 0–4 294 967 295
        hue = h / 4294967296.0   # uniformly spread 0.0–1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.72)
        return Gf.Vec3f(float(r), float(g), float(b))

    def _boost_color_for_display(self, color: "Gf.Vec3f"):
        """Boost a sampled texture colour to be clearly visible in VP2.

        Physically-accurate texture averages are typically dark and desaturated
        for realistic character materials (skin, metal, cloth).  This method
        preserves the dominant hue while pushing saturation and value into a
        range that makes per-material differences immediately visible.

        Returns None when the colour is a truly dark/black achromatic (HSV
        saturation < 0.08 AND value < 0.80), which tells the caller to use
        _rfm_name_color instead.

        Near-white achromatic colours (e.g. eye sclera, teeth at ~(1,1,1)) are
        returned unchanged — they must NOT be name-hashed, as that would turn
        white eye whites into a random vivid hue like magenta or pink.
        """
        import colorsys
        from pxr import Gf  # type: ignore
        r, g, b = float(color[0]), float(color[1]), float(color[2])
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s < 0.08:
            # Near-white (sclera, teeth, light-grey surfaces) — preserve as-is.
            # Only truly dark/black achromatic colours get name-hashed.
            if v > 0.80:
                return Gf.Vec3f(r, g, b)
            return None  # dark achromatic — name-hash will be more distinctive
        s_out = max(s, 0.62)
        v_out = max(min(max(v, 0.58), 0.82), 0.58)
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s_out, v_out)
        return Gf.Vec3f(float(r2), float(g2), float(b2))

    def _convert_renderman_materials_to_usd_preview(self, usd_path: Path) -> None:
        """
        Convert RenderMan PxrShader materials to UsdPreviewSurface.

        Maya's RenderMan typically uses Lambert nodes with PxrSurface/PxrShader connections.
        This method reads the Lambert diffuse colors and converts to UsdPreviewSurface materials.
        """
        if not USD_AVAILABLE:
            self.logger.warning("[WARNING] USD Python API not available for material conversion")
            return

        try:
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("[WARNING] Could not open USD stage for material conversion")
                return

            self.logger.info("[LOOKDEV] Converting RenderMan materials to UsdPreviewSurface...")

            materials_converted = 0

            # ----------------------------------------------------------------
            # Step 1: Build sg_to_color from Maya — keyed by shading group name.
            # This is more reliable than mesh→material because skinned mesh
            # bindings in USD may not be authored on the mesh prim itself.
            # mayaUSD names USD Material prims after the Maya shading group.
            # ----------------------------------------------------------------
            sg_to_color = {}
            # Parallel dict: sg_name → resolved source PNG path.
            # Populated by Phase B Lambert scan (and Pxr sampler fallback).
            # Used in the USD injection step to create UsdUVTexture networks
            # instead of flat diffuseColor values.  Works for any RenderMan
            # rig — the Lambert proxy / file-node chain is standard RfM.
            sg_to_texpath: dict = {}
            # Parallel dict: sg_name → {'metallic': float, 'roughness': float}
            # Populated by Phase B-PBR scan from PxrDisney / PxrSurface attrs.
            # Transferred to UsdPreviewSurface so metal objects (chain, dog tags,
            # zippers, buttons) render with correct PBR properties instead of
            # looking like flat plastic.
            sg_to_pbr: dict = {}
            # Parallel dict: sg_name → [pxr_node_full_names]
            # Populated by Phase B Pxr node scan.  Used in the metal keyword
            # override pass: RfM auto-names SGs as PxrDisneyBsdf[N]SG which has no
            # semantic content, but the underlying Pxr node (e.g. Veteran_Chain_Bsdf)
            # does.  Must be initialised here so the injection loop can reference it
            # even when cmds is None.
            _sg_to_pxr_map: dict = {}
            if cmds is not None:
                try:
                    # ----------------------------------------------------------
                    # Phase A: Lambert → SG (non-proxy Lamberts only).
                    # Skip lambert1 (Maya default) and any Lambert whose name
                    # contains "pxr" (RFM occasionally names proxies that way).
                    # ----------------------------------------------------------
                    lambert_colors = {}
                    for lambert in (cmds.ls(type="lambert") or []):
                        try:
                            if lambert == "lambert1" or "pxr" in lambert.lower():
                                continue
                            c = cmds.getAttr(f"{lambert}.color")[0]
                            r, g, b = float(c[0]), float(c[1]), float(c[2])
                            # Skip near-black lamberts — RfM creates placeholder
                            # lambert nodes with color (0,0,0) for every Pxr shader.
                            # Storing them in Phase A would poison the SG lookup with
                            # black before Phase B can mark it None (texture-driven).
                            if r + g + b <= 0.01:
                                continue
                            lambert_colors[lambert] = Gf.Vec3f(r, g, b)
                        except Exception:
                            pass

                    for lambert, color in lambert_colors.items():
                        try:
                            for sg in (cmds.listConnections(lambert, type="shadingEngine") or []):
                                sg_to_color[sg] = color
                        except Exception:
                            pass

                    # ----------------------------------------------------------
                    # Phase B: RenderMan PxrSurface / PxrDisney / PxrUnified.
                    # RfM connects shaders to shadingEngine.rmanSurface (not
                    # .surfaceShader), so Phase C misses them entirely.
                    # PxrSurface final color = diffuseGain * diffuseColor.
                    # PxrDisney / PxrUnified use baseColor directly.
                    # ----------------------------------------------------------
                    # ── PHASE B CODE VERSION: v5 ─────────────────────────
                    self.logger.info("   [PHASE-B] v5 — scanning RfM SGs for texture colors")
                    _phase_b_rma_lib = getattr(
                        getattr(self, "_current_export_options", None),
                        "renderman_library_path", ""
                    ) or ""
                    if _phase_b_rma_lib:
                        self.logger.info(
                            f"   [PHASE-B] src-lib path: {_phase_b_rma_lib}"
                        )
                    else:
                        self.logger.info(
                            "   [PHASE-B] src-lib path: (none) — texture colors from asset_100.png"
                        )
                    RFM_SHADER_TYPES = {
                        # node_type: (color_attr, gain_attr_or_None)
                        "PxrSurface":      ("diffuseColor", "diffuseGain"),
                        # RfM 26+: "PxrDisney" was later registered as "PxrDisneyBsdf"
                        "PxrDisney":       ("baseColor",    None),
                        "PxrDisneyBsdf":   ("baseColor",    None),
                        # Some RfM 27 builds register it without the 'Bsdf' suffix
                        "PxrDisneyBSDF":   ("baseColor",    None),
                        "PxrUnified":      ("diffuseColor", "diffuseGain"),
                        "PxrLayer":        ("diffuseColor", None),
                        "PxrLMDiffuse":    ("transmissionColor", None),
                    }
                    # Pre-collect ALL Pxr* shader nodes in the scene, keyed by
                    # their SHORT name (namespace stripped).  This lets the
                    # name-derivation fallback below find nodes even when they
                    # live inside a Maya reference namespace.
                    # e.g. "SomeRef:PxrDisneyBsdf1" is stored under key "PxrDisneyBsdf1".
                    _pxr_short_to_full: dict = {}
                    try:
                        # Per-type sweep — finds shader nodes by TYPE regardless of name
                        # (actual Bsdf nodes are named 'Veteran_Body_Bsdf', not 'Pxr*').
                        # Guard each type with a registration check to skip unregistered
                        # variants (PxrDisneyBSDF, PxrLMDiffuse) that would emit
                        # "Unknown object type" warnings in this Maya/RfM version.
                        _registered_node_types = set(cmds.allNodeTypes() or [])
                        for _pxr_type in RFM_SHADER_TYPES:
                            if _pxr_type not in _registered_node_types:
                                continue  # type not registered → skip silently
                            for _n in (cmds.ls(type=_pxr_type) or []):
                                _short = _n.split(":")[-1]
                                _pxr_short_to_full.setdefault(_short, _n)
                        # Broad name sweep: catches nodes with Pxr* prefix (e.g. SGs,
                        # any variant not covered by the registered-type check above).
                        for _n in (cmds.ls("Pxr*") or []) + (cmds.ls("*:Pxr*") or []):
                            _short = _n.split(":")[-1]
                            _pxr_short_to_full.setdefault(_short, _n)
                    except Exception:
                        pass
                    self.logger.info(
                        f"   [PHASE-B] pre-collected {len(_pxr_short_to_full)} "
                        f"Pxr* nodes: {list(_pxr_short_to_full.keys())[:6]}..."
                    )

                    # Build reverse map: Pxr surface shader → its connected SG(s).
                    # In RfM 27 the PxrDisneyBsdf shader may not appear in the SG's
                    # incoming connections at all; instead the SG appears in the shader's
                    # *outgoing* connections.  Querying "what SGs does Veteran_Body_Bsdf
                    # output to?" gives us the link even when the SG refuses to list it.
                    _sg_to_pxr_map: dict = {}
                    for _full in _pxr_short_to_full.values():
                        try:
                            if cmds.nodeType(_full) not in RFM_SHADER_TYPES:
                                continue
                        except Exception:
                            continue
                        try:
                            for _sg_name in (
                                cmds.listConnections(
                                    _full,
                                    source=False,
                                    destination=True,
                                    type="shadingEngine",
                                ) or []
                            ):
                                _sg_to_pxr_map.setdefault(_sg_name, [])
                                if _full not in _sg_to_pxr_map[_sg_name]:
                                    _sg_to_pxr_map[_sg_name].append(_full)
                        except Exception:
                            pass
                    if _sg_to_pxr_map:
                        self.logger.info(
                            f"   [PHASE-B] reverse Pxr→SG map: "
                            f"{len(_sg_to_pxr_map)} SGs have Pxr shader linkage. "
                            f"Sample: {dict(list(_sg_to_pxr_map.items())[:3])}"
                        )
                    else:
                        self.logger.info(
                            "   [PHASE-B] reverse map: no outgoing Pxr→SG connections found"
                        )

                    # Also check .rmanSurface on every SG.
                    # Each SG is isolated in its own try/except so a missing
                    # .rmanSurface attribute on one SG never aborts the loop.
                    for sg in (cmds.ls(type="shadingEngine") or []):
                        if sg in sg_to_color:
                            continue
                        # Skip numbered Maya duplicate SGs (e.g. PxrDisneyBsdf18SG1,
                        # PxrDisneyBsdf18SG2) when their un-numbered base was already
                        # processed.  These duplicates have no corresponding USD
                        # Material prim so their color values are never used.
                        import re as _re_phb  # noqa: PLC0415 (local import, intentional)
                        _dup_match = _re_phb.match(r'^(.+SG)\d+$', sg)
                        if _dup_match and _dup_match.group(1) in sg_to_color:
                            continue
                        try:
                            # RfM primary connection point (.rmanSurface may not
                            # exist on non-RfM SGs — catch the Maya error per-SG)
                            try:
                                rfm_nodes = (
                                    cmds.listConnections(
                                        f"{sg}.rmanSurface", source=True, destination=False
                                    ) or []
                                )
                            except Exception:
                                rfm_nodes = []
                            # Fallback: .surfaceShader may hold a PxrSurface in some RfM setups
                            try:
                                rfm_nodes += (
                                    cmds.listConnections(
                                        f"{sg}.surfaceShader", source=True, destination=False
                                    ) or []
                                )
                            except Exception:
                                pass
                            # RfM 27 name-derived fallback: the SG is named after
                            # its shader node (e.g. PxrDisneyBsdf1SG → PxrDisneyBsdf1).
                            # In RfM 27 the Pxr shader is NOT wired to .rmanSurface or
                            # .surfaceShader — only a lambert placeholder is.  Stripping
                            # the trailing "SG" gives us the shader's short name; we then
                            # look it up in _pxr_short_to_full (handles reference namespaces).
                            if sg.endswith("SG"):
                                derived_short = sg.split(":")[-1][:-2]  # "NS:PxrDisneyBsdf1SG" → "PxrDisneyBsdf1"
                                full_name = _pxr_short_to_full.get(derived_short)
                                if full_name and full_name not in rfm_nodes:
                                    rfm_nodes.append(full_name)
                                    self.logger.info(
                                        f"   [PHASE-B] {sg}: name-derived fallback found {full_name!r}"
                                    )
                            # Broad incoming-connection scan: check ALL source connections
                            # on this SG for any Pxr* node (catches undocumented RfM attrs).
                            try:
                                for _c in (
                                    cmds.listConnections(
                                        sg, source=True, destination=False
                                    ) or []
                                ):
                                    try:
                                        if (
                                            cmds.nodeType(_c).startswith("Pxr")
                                            and _c not in rfm_nodes
                                        ):
                                            rfm_nodes.append(_c)
                                            self.logger.info(
                                                f"   [PHASE-B] {sg}: broad-scan found {_c!r}"
                                            )
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            # Reverse map: Pxr shader declared THIS SG as its output.
                            for _p in _sg_to_pxr_map.get(sg, []):
                                if _p not in rfm_nodes:
                                    rfm_nodes.append(_p)
                                    self.logger.info(
                                        f"   [PHASE-B] {sg}: reverse-map found {_p!r}"
                                    )
                            # --------------------------------------------------
                            # Lambert VP2 file texture pre-scan.
                            # RfM wires a Lambert to sg.surfaceShader for VP2.
                            # That Lambert.color → file.fileTextureName is the
                            # actual source PNG — readable by PIL, no .tex needed.
                            # This runs BEFORE the Pxr rfm_nodes loop so the
                            # rma-scan fallback can never shadow it.
                            # --------------------------------------------------
                            try:
                                for _lam in (
                                    cmds.listConnections(
                                        f"{sg}.surfaceShader",
                                        source=True,
                                        destination=False,
                                    ) or []
                                ):
                                    if cmds.nodeType(_lam) != "lambert":
                                        continue
                                    for _lf in (
                                        cmds.listConnections(
                                            f"{_lam}.color",
                                            source=True,
                                            destination=False,
                                        ) or []
                                    ):
                                        if cmds.nodeType(_lf) != "file":
                                            continue
                                        _lfile_path = cmds.getAttr(
                                            f"{_lf}.fileTextureName"
                                        )
                                        if not (_lfile_path and os.path.isfile(_lfile_path)):
                                            continue
                                        try:
                                            from PIL import Image  # type: ignore
                                            import numpy as _np
                                            with Image.open(_lfile_path).convert("RGB") as _limg:
                                                # Resize to a small sample for speed —
                                                # preserves the full color distribution
                                                # across the UV layout.
                                                _lthumb = _limg.resize(
                                                    (32, 32), Image.LANCZOS
                                                )
                                                _larr = _np.array(
                                                    _lthumb, dtype=float
                                                ) / 255.0
                                                _lpix = _larr.reshape(-1, 3)
                                                # Filter out near-black pixels
                                                # (unmapped UV space / shadows) so
                                                # they don't drag the median to zero.
                                                _lbright = _lpix.mean(axis=1)
                                                _lmask = _lbright > 0.05
                                                if _lmask.sum() >= 4:
                                                    _lpix = _lpix[_lmask]
                                                lr = float(_np.median(_lpix[:, 0]))
                                                lg = float(_np.median(_lpix[:, 1]))
                                                lb = float(_np.median(_lpix[:, 2]))
                                            if max(lr, lg, lb) > 0.02:
                                                sg_to_color[sg] = Gf.Vec3f(
                                                    max(0.0, min(1.0, lr)),
                                                    max(0.0, min(1.0, lg)),
                                                    max(0.0, min(1.0, lb)),
                                                )
                                                _tex_for_usd = _lfile_path
                                                if _tex_for_usd.lower().endswith(".tex"):
                                                    _src = _tex_for_usd[:-4]
                                                    if os.path.isfile(_src):
                                                        _tex_for_usd = _src
                                                sg_to_texpath[sg] = _tex_for_usd
                                                self.logger.info(
                                                    f"   [PHASE-B] {sg}: Lambert file texture "
                                                    f"({lr:.3f}, {lg:.3f}, {lb:.3f}) ← "
                                                    f"{os.path.basename(_lfile_path)}"
                                                )
                                            else:
                                                self.logger.info(
                                                    f"   [PHASE-B] {sg}: Lambert file near-zero "
                                                    f"({lr:.3f}, {lg:.3f}, {lb:.3f}) ← "
                                                    f"{os.path.basename(_lfile_path)}"
                                                    f" — skipping, will use Pxr texture sampler"
                                                )
                                        except Exception as _lpil_exc:
                                            self.logger.info(
                                                f"   [PHASE-B] {sg}: Lambert file PIL "
                                                f"failed ({_lpil_exc})"
                                            )
                                        break  # one file node per lambert is enough
                                    if sg in sg_to_color:
                                        break  # found the texture, stop checking lamberts
                            except Exception:
                                pass

                            # Lambert pre-scan already resolved this SG — skip
                            # the Pxr loop entirely to avoid noisy [B-DIAG] output.
                            if sg in sg_to_color:
                                continue

                            has_pxr_node = False
                            for rfm_node in rfm_nodes:
                                try:
                                    node_type = cmds.nodeType(rfm_node)
                                except Exception:
                                    continue
                                # Any Pxr* node is a RenderMan shader — mark
                                # the SG as RfM-owned even if we can't read
                                # a meaningful color from it.
                                if node_type.startswith("Pxr"):
                                    has_pxr_node = True
                                # PxrBlack is a valid shader that renders as solid black.
                                # Give it a near-black preview color so the mesh is visible.
                                if node_type == "PxrBlack":
                                    if sg not in sg_to_color:
                                        sg_to_color[sg] = Gf.Vec3f(0.01, 0.01, 0.01)
                                    break
                                if node_type not in RFM_SHADER_TYPES:
                                    if node_type != "lambert":  # Lambert handled in pre-scan above
                                        self.logger.info(
                                            f"   [PHASE-B] {sg}: found {rfm_node} "
                                            f"type={node_type!r} — not in RFM_SHADER_TYPES, skipping"
                                        )
                                    continue
                                color_attr, gain_attr = RFM_SHADER_TYPES[node_type]
                                try:
                                    raw = cmds.getAttr(f"{rfm_node}.{color_attr}")
                                    # A compound color attribute that has an
                                    # upstream connection returns None from
                                    # getAttr (Maya can't evaluate it outside
                                    # the DG).  Treat that as (0,0,0) so we
                                    # fall through to the texture sampler below.
                                    if raw is None:
                                        r, g, b = 0.0, 0.0, 0.0
                                    else:
                                        c = raw[0] if isinstance(raw, list) else raw
                                        r, g, b = float(c[0]), float(c[1]), float(c[2])
                                    # Only log the raw diagnostic when the sg
                                    # is still unresolved — avoids noise for
                                    # texture-driven shaders with 0,0,0 base color.
                                    if sg not in sg_to_color:
                                        self.logger.debug(
                                            f"   [B-DIAG] {rfm_node}.{color_attr}: "
                                            f"raw={raw!r}  r+g+b={r+g+b:.4f}"
                                        )
                                    if gain_attr:
                                        try:
                                            gain = float(cmds.getAttr(f"{rfm_node}.{gain_attr}"))
                                            r, g, b = r * gain, g * gain, b * gain
                                        except Exception:
                                            pass
                                    # Only use if meaningfully non-zero
                                    if r + g + b > 0.01:
                                        if sg not in sg_to_color:  # don't overwrite Lambert file result
                                            sg_to_color[sg] = Gf.Vec3f(
                                                max(0.0, min(1.0, r)),
                                                max(0.0, min(1.0, g)),
                                                max(0.0, min(1.0, b)),
                                            )
                                        break
                                    else:
                                        # baseColor is near-zero — this shader is
                                        # texture-driven. If Lambert already found a
                                        # color for this SG, skip the expensive texture
                                        # sampler entirely (MImage/PIL/OIIO would run
                                        # for nothing and the result would be discarded).
                                        if sg in sg_to_color:
                                            break
                                        self.logger.debug(
                                            f"   [B-DIAG] {rfm_node}: near-zero, "
                                            f"calling texture sampler..."
                                        )
                                        tex_color = self._sample_pxr_texture_color(
                                            rfm_node, color_attr
                                        )
                                        if tex_color is not None:
                                            sg_to_color[sg] = tex_color
                                            _ltp = getattr(
                                                self, '_last_resolved_tex_path', None
                                            )
                                            if _ltp:
                                                sg_to_texpath[sg] = _ltp
                                                self._last_resolved_tex_path = None
                                            self.logger.info(
                                                f"   [TEX] {sg} — sampled texture color: {tex_color}"
                                            )
                                            break
                                except Exception as _b_exc:
                                    self.logger.info(
                                        f"   [B-DIAG] EXCEPTION for {rfm_node}.{color_attr}: "
                                        f"{type(_b_exc).__name__}: {_b_exc}"
                                    )
                                    continue
                            # If ANY Pxr* node was found on this SG but no
                            # usable color was extracted, assign a sensible
                            # fallback so Phase C can't corrupt it with 0,0,0.
                            # Transparent/glass materials get a pale glass color;
                            # everything else is marked None (RfM name-hash
                            # fallback runs later in the USD injection step).
                            if has_pxr_node and sg not in sg_to_color:
                                _sg_lo = sg.lower()
                                _is_glass = any(
                                    kw in _sg_lo
                                    for kw in ("cornea", "glass", "crystal", "clear", "transp")
                                )
                                sg_to_color[sg] = (
                                    Gf.Vec3f(0.85, 0.88, 0.92)  # pale ice-blue for transparent
                                    if _is_glass
                                    else None
                                )
                        except Exception:
                            continue

                    # ----------------------------------------------------------
                    # Phase B-PBR: Transfer metallic / roughness from PxrDisney
                    # shaders into sg_to_pbr.  Metal accessories (chain, dog tags,
                    # zippers, buttons) rely on this to not look like flat plastic
                    # in USD Preview Surface viewers.
                    # ----------------------------------------------------------
                    for _sg_pbr, _pxr_list_pbr in _sg_to_pxr_map.items():
                        for _pxr_pbr in _pxr_list_pbr:
                            try:
                                _nt_pbr = cmds.nodeType(_pxr_pbr)
                                if _nt_pbr not in (
                                    'PxrDisney', 'PxrDisneyBsdf', 'PxrDisneyBSDF',
                                    'PxrSurface', 'PxrUnified',
                                ):
                                    continue
                                _m_pbr, _r_pbr = 0.0, 0.5
                                try:
                                    _m_pbr = float(
                                        cmds.getAttr(f"{_pxr_pbr}.metallic") or 0.0
                                    )
                                except Exception:
                                    pass
                                try:
                                    _rough_attr = (
                                        "roughness"
                                        if _nt_pbr.startswith("PxrDisney")
                                        else "diffuseRoughness"
                                    )
                                    _r_pbr = float(
                                        cmds.getAttr(f"{_pxr_pbr}.{_rough_attr}") or 0.5
                                    )
                                except Exception:
                                    pass
                                if _sg_pbr not in sg_to_pbr:
                                    sg_to_pbr[_sg_pbr] = {
                                        'metallic': min(1.0, max(0.0, _m_pbr)),
                                        'roughness': min(1.0, max(0.0, _r_pbr)),
                                    }
                                break
                            except Exception:
                                pass
                    self.logger.info(
                        f"   [PHASE-B-PBR] Populated {len(sg_to_pbr)} SGs with PBR values "
                        f"(metallic/roughness from PxrDisney). "
                        f"Samples: {list(sg_to_pbr.items())[:4]}"
                    )

                    # ----------------------------------------------------------
                    # Phase C: Generic surface shader fallback for non-Lambert,
                    # non-RFM SGs (e.g. aiStandardSurface, blinn, phong, etc.).
                    # Tries common color attribute names on whatever node is
                    # connected to .surfaceShader.
                    # ----------------------------------------------------------
                    # outColor covers Maya's built-in surfaceShader node type
                    # (used by utility shaders like asRedSG, asGreenSG, etc.).
                    # NOTE: outColor MUST be last.  On lambert nodes it is
                    # a computed output that returns (0,0,0) without a DG
                    # evaluation context.  Reading 'color' first yields the
                    # authored diffuse color (correct for lamberts).
                    GENERIC_COLOR_ATTRS = ("color", "baseColor", "diffuseColor", "Kd", "outColor")
                    for sg in (cmds.ls(type="shadingEngine") or []):
                        if sg in sg_to_color:
                            continue  # already resolved
                        try:
                            nodes = cmds.listConnections(f"{sg}.surfaceShader") or []
                        except Exception:
                            nodes = []
                        for node in nodes:
                            # Any Pxr* node is a RenderMan shader. Reading
                            # outColor/baseColor from an unevaluated Pxr node
                            # returns (0,0,0) and would corrupt the USD.
                            # Use startswith("Pxr") to catch every variant
                            # (PxrDisney, PxrDisneyBsdf, PxrSurface, etc.).
                            try:
                                if cmds.nodeType(node).startswith("Pxr"):
                                    sg_to_color[sg] = None
                                    break
                            except Exception:
                                pass
                            for ca in GENERIC_COLOR_ATTRS:
                                try:
                                    # Skip texture-driven attributes: if the color
                                    # input is connected to a PxrTexture or similar
                                    # upstream node, getAttr only returns the scalar
                                    # fallback (usually 0,0,0) which is misleading.
                                    # Using the black fallback would overwrite any
                                    # correct texture wiring already in USD.
                                    if cmds.listConnections(
                                        f"{node}.{ca}",
                                        source=True,
                                        destination=False,
                                    ):
                                        continue
                                    c = cmds.getAttr(f"{node}.{ca}")[0]
                                    sg_to_color[sg] = Gf.Vec3f(c[0], c[1], c[2])
                                    break
                                except Exception:
                                    pass
                            if sg in sg_to_color:
                                break

                    self.logger.info(f"[LOOKDEV] Found {len(lambert_colors)} Lambert materials in Maya")
                    color_count = sum(1 for v in sg_to_color.values() if v is not None)
                    skip_count = sum(1 for v in sg_to_color.values() if v is None)
                    skipped_sgs = [k for k, v in sg_to_color.items() if v is None]
                    self.logger.info(
                        f"[LOOKDEV] Mapped {color_count} shading groups to colors "
                        f"(A=Lambert, B=RfM Pxr*, C=generic)"
                        + (f", {skip_count} RfM texture-driven skipped" if skip_count else "")
                    )
                    if skipped_sgs:
                        self.logger.info(f"[LOOKDEV] Skipped RfM SGs: {skipped_sgs[:10]}")
                    self.logger.info(f"[LOOKDEV] Sample SG keys: {list(sg_to_color.keys())[:8]}")
                except Exception as e:
                    self.logger.warning(f"[WARNING] Could not query Maya materials: {e}")

            # ----------------------------------------------------------------
            # Step 2: Walk all USD Material prims and inject UsdPreviewSurface.
            # Match USD material prim name → Maya SG name using variations.
            # This avoids relying on mesh binding relationships entirely.
            # ----------------------------------------------------------------
            self.logger.info("[LOOKDEV] Scanning USD material prims for name→SG matches...")
            usd_mat_count = 0
            usd_mat_name_samples = []
            for prim in stage.Traverse():
                if prim.GetTypeName() != "Material":
                    continue
                usd_mat_count += 1
                usd_mat_name = prim.GetName()
                if len(usd_mat_name_samples) < 5:
                    usd_mat_name_samples.append(usd_mat_name)
                material = UsdShade.Material(prim)

                # Build name variations to match against Maya SG names
                # mayaUSD may strip trailing 'SG' or append it, clean namespaces, etc.
                name_vars = [
                    usd_mat_name,
                    usd_mat_name + "SG",
                    usd_mat_name + "1SG",
                    usd_mat_name.rstrip("SG"),
                    usd_mat_name.replace("_mat", "SG"),
                    usd_mat_name.replace("_mat", "1SG"),
                ]

                lambert_color = None
                matched_sg = None
                for var in name_vars:
                    if var in sg_to_color:
                        lambert_color = sg_to_color[var]
                        matched_sg = var
                        break

                if lambert_color is None:
                    # Last resort: infer color from the USD material prim name.
                    # Rig control shaders like asRedSG, asGreenSG, asBlueSG may
                    # not exist in the current Maya session (e.g. if the model
                    # file had a partial load error) but their names encode the
                    # intended color unambiguously.
                    name_lower = usd_mat_name.lower()
                    NAME_COLOR_MAP = [
                        ("red",     Gf.Vec3f(0.8, 0.1, 0.1)),
                        ("green",   Gf.Vec3f(0.1, 0.7, 0.1)),
                        ("blue",    Gf.Vec3f(0.1, 0.3, 0.9)),
                        ("yellow",  Gf.Vec3f(0.9, 0.85, 0.1)),
                        ("orange",  Gf.Vec3f(0.9, 0.5, 0.1)),
                        ("purple",  Gf.Vec3f(0.5, 0.1, 0.8)),
                        ("cyan",    Gf.Vec3f(0.1, 0.8, 0.8)),
                        ("pink",    Gf.Vec3f(0.9, 0.4, 0.6)),
                        ("brown",   Gf.Vec3f(0.45, 0.25, 0.1)),
                        ("white",   Gf.Vec3f(0.95, 0.95, 0.95)),
                        ("black",   Gf.Vec3f(0.02, 0.02, 0.02)),
                        ("gray",    Gf.Vec3f(0.5, 0.5, 0.5)),
                        ("grey",    Gf.Vec3f(0.5, 0.5, 0.5)),
                        ("gold",    Gf.Vec3f(0.85, 0.7, 0.1)),
                        ("silver",  Gf.Vec3f(0.75, 0.75, 0.78)),
                    ]
                    for keyword, inferred in NAME_COLOR_MAP:
                        if keyword in name_lower:
                            lambert_color = inferred
                            matched_sg = f"[name:{keyword}]"
                            break

                is_rfm_name = usd_mat_name.startswith(
                    ("PxrDisney", "PxrSurface", "PxrUnified", "PxrLayer", "PxrLM")
                )
                # Also treat near-black Gf.Vec3f as missing for RfM materials —
                # Phase B stores None for texture-driven Pxr nodes, but due to
                # exception-swallowing or phantom lambert connections the dict may
                # hold Gf.Vec3f(0,0,0) instead of Python None.  Either way the
                # mesh would render invisible without this guard.
                is_near_black = (
                    lambert_color is not None
                    and isinstance(lambert_color, Gf.Vec3f)
                    and (lambert_color[0] + lambert_color[1] + lambert_color[2]) <= 0.01
                )

                if lambert_color is None or (is_rfm_name and is_near_black):
                    # Apply name-hash fallback to:
                    #   a) Any material Phase B identified as RfM-owned (matched_sg
                    #      is set, even when the stored value was None meaning
                    #      "texture-driven but sampling failed") — covers body/skin/
                    #      clothing SGs whose USD prim names never start with "Pxr*".
                    #   b) Materials whose USD prim name explicitly starts with a
                    #      Pxr* shader type (legacy path).
                    # Materials with no SG match at all (matched_sg is None AND not
                    # is_rfm_name) are left untouched — mayaUSD may have converted
                    # them correctly already.
                    if matched_sg is not None or is_rfm_name:
                        # Texture sampling failed — generate a unique, deterministic
                        # color from the material name so each part of the rig is
                        # visually distinct in USD viewers rather than showing white.
                        lambert_color = self._rfm_name_color(usd_mat_name)
                        matched_sg = "[fallback:name-hash]"
                        self.logger.info(
                            f"   [FALLBACK] {usd_mat_name} — texture unreadable, "
                            f"using name-hash color: {lambert_color}"
                        )
                    else:
                        continue  # Unknown material with no SG match — skip

                # RfM auto-names SGs after the shader node (e.g. PxrDisneyBsdf1SG).
                if is_rfm_name:
                    self.logger.info(
                        f"   [RFM] {usd_mat_name} — writing Phase B color: {lambert_color}"
                    )

                # Check if we already injected a PreviewSurface (re-export).
                # Use path-prefix traversal — GetAllDescendants() not available
                # in Maya's embedded USD Python build.
                preview_shader = None
                mat_path_prefix = str(prim.GetPath()) + "/"
                for desc_prim in stage.Traverse():
                    if not str(desc_prim.GetPath()).startswith(mat_path_prefix):
                        continue
                    if desc_prim.GetTypeName() == "Shader":
                        s = UsdShade.Shader(desc_prim)
                        if s and s.GetShaderId() == "UsdPreviewSurface":
                            preview_shader = s
                            break

                _active_shader = None  # set below; used for shared PBR / eye overrides
                if preview_shader:
                    # Never overwrite a diffuseColor that already has a texture
                    # connection wired by mayaUSD (e.g. PxrDisney with PxrTexture).
                    # Reading the static color from the Lambert placeholder would
                    # replace the real texture with solid black.
                    dc_input = preview_shader.GetInput("diffuseColor")
                    if dc_input and dc_input.HasConnectedSource():
                        materials_converted += 1
                        self.logger.debug(
                            f"   [SKIP] {usd_mat_name} — diffuseColor already has texture connection"
                        )
                    else:
                        _tex_src = sg_to_texpath.get(matched_sg) if matched_sg else None
                        if (
                            _tex_src and os.path.isfile(_tex_src)
                            and self._wire_diffuse_texture(
                                stage, prim, preview_shader, _tex_src, usd_path.parent,
                                lambert_color,
                            )
                        ):
                            self.logger.info(
                                f"   [UPDATE] {usd_mat_name} ← {matched_sg}: "
                                f"UsdUVTexture({os.path.basename(_tex_src)})"
                            )
                        else:
                            preview_shader.CreateInput(
                                "diffuseColor", Sdf.ValueTypeNames.Color3f
                            ).Set(lambert_color)
                            self.logger.info(
                                f"   [UPDATE] {usd_mat_name} ← {matched_sg} = {lambert_color}"
                            )
                        materials_converted += 1
                        _active_shader = preview_shader

                    # Ensure material's universal 'surface' output is connected.
                    # The RenderMan exporter only creates ri:surface — VP2 needs
                    # the renderContext-free 'surface' output to find the shader.
                    # Wire through the NodeGraph when the shader is inside one,
                    # otherwise some USD viewers reject the cross-boundary link.
                    surface_out = material.GetSurfaceOutput()
                    if not surface_out or not surface_out.HasConnectedSource():
                        _sp = preview_shader.GetPrim()
                        _pp = _sp.GetParent()
                        if (
                            _pp.IsValid()
                            and _pp.GetTypeName() == 'NodeGraph'
                            and _pp.GetPath() != prim.GetPath()
                        ):
                            _ng = UsdShade.NodeGraph(_pp)
                            _ng_out = _ng.CreateOutput(
                                'surface', Sdf.ValueTypeNames.Token
                            )
                            _ng_out.ConnectToSource(
                                preview_shader.ConnectableAPI(), 'surface'
                            )
                            # Wire Material.outputs:surface directly to the inner
                            # shader — same bypass approach as _fix_exported_usdc.
                            material.CreateSurfaceOutput().ConnectToSource(
                                preview_shader.ConnectableAPI(), 'surface'
                            )
                        else:
                            material.CreateSurfaceOutput().ConnectToSource(
                                preview_shader.ConnectableAPI(), "surface"
                            )
                        self.logger.debug(
                            f"   [FIX] {usd_mat_name} — wired surface output for VP2"
                        )
                else:
                    # Inject PreviewSurface into the existing RenderMan material.
                    # universal 'surface' output leaves ri:surface connection untouched.
                    shader_path = f"{str(prim.GetPath())}/PreviewSurface"
                    shader = UsdShade.Shader.Define(stage, shader_path)
                    shader.CreateIdAttr("UsdPreviewSurface")
                    _tex_src = sg_to_texpath.get(matched_sg) if matched_sg else None
                    if (
                        _tex_src and os.path.isfile(_tex_src)
                        and self._wire_diffuse_texture(
                            stage, prim, shader, _tex_src, usd_path.parent,
                            lambert_color,
                        )
                    ):
                        self.logger.info(
                            f"   [INJECT] {usd_mat_name} ← {matched_sg}: "
                            f"UsdUVTexture({os.path.basename(_tex_src)})"
                        )
                    else:
                        shader.CreateInput(
                            "diffuseColor", Sdf.ValueTypeNames.Color3f
                        ).Set(lambert_color)
                        self.logger.info(
                            f"   [INJECT] {usd_mat_name} ← {matched_sg} = {lambert_color}"
                        )
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                    shader.CreateOutput('surface', Sdf.ValueTypeNames.Token)
                    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
                    materials_converted += 1
                    _active_shader = shader

                # ── Shared PBR + eye override post-processing ──────────────────
                # Runs after both UPDATE (non-skip) and INJECT branches.
                # Applies Phase B-PBR values (metallic / roughness from PxrDisney)
                # and eye-specific material overrides (cornea opacity, sclera white,
                # iris / pupil metallic reset).
                if _active_shader is not None:
                    _name_lo = usd_mat_name.lower()
                    # Augment keyword checks with semantic Pxr shader node names.
                    # RfM auto-names SGs as PxrDisneyBsdf[N]SG (no semantic content);
                    # the Pxr node itself (e.g. Veteran_Chain_Bsdf) carries the meaning.
                    _pxr_nodes = _sg_to_pxr_map.get(matched_sg, []) if matched_sg else []
                    _name_check = (
                        _name_lo + ' '
                        + ' '.join(n.split(':')[-1].lower() for n in _pxr_nodes)
                    )
                    # Transfer PBR values from PxrDisney scan
                    _pbr = sg_to_pbr.get(matched_sg) if matched_sg else None
                    if _pbr:
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(_pbr['metallic'])
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(_pbr['roughness'])
                        self.logger.info(
                            f"   [PBR] {usd_mat_name} -- metallic={_pbr['metallic']:.3f}, "
                            f"roughness={_pbr['roughness']:.3f}"
                        )
                    # Eye material name-based overrides
                    if 'cornea' in _name_lo:
                        # Cornea = transparent glass.
                        # opacity=0.0 → fully transparent in QuickLook / full USD renderers.
                        # diffuseColor set to a near-clear water tint so that viewers
                        # which do NOT support opacity (render everything as opaque) still
                        # show a plausible glossy white eye-surface rather than a muddy grey.
                        # roughness=0.02 → near-mirror wet-glass specular highlight.
                        _active_shader.CreateInput(
                            "diffuseColor", Sdf.ValueTypeNames.Color3f
                        ).Set(Gf.Vec3f(0.95, 0.97, 1.0))   # near-clear water tint
                        _active_shader.CreateInput(
                            "opacity", Sdf.ValueTypeNames.Float
                        ).Set(0.0)
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.0)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.02)                          # near-mirror gloss → reads as glass
                        self.logger.info(
                            f"   [EYE] {usd_mat_name} — opacity=0 glass cornea, "
                            f"diffuse=clear-water, roughness=0.02"
                        )
                    elif 'sclera' in _name_lo:
                        # Force white regardless of Lambert proxy color
                        _active_shader.CreateInput(
                            "diffuseColor", Sdf.ValueTypeNames.Color3f
                        ).Set(Gf.Vec3f(0.95, 0.95, 0.95))
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.0)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.35)
                        self.logger.info(
                            f"   [EYE] {usd_mat_name} — white sclera, metallic=0"
                        )
                    elif 'iris' in _name_lo:
                        # The Lambert proxy colour for iris is near-black (~0.06)
                        # which is unusable.  Force a warm hazel-brown so the iris
                        # ring is clearly visible against both the white sclera and
                        # the black pupil in all USD viewers.
                        _active_shader.CreateInput(
                            "diffuseColor", Sdf.ValueTypeNames.Color3f
                        ).Set(Gf.Vec3f(0.35, 0.20, 0.05))
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.0)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.2)
                        self.logger.info(
                            f"   [EYE] {usd_mat_name} -- iris hazel-brown, roughness=0.2"
                        )
                    elif 'pupil' in _name_lo:
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.0)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.5)
                        self.logger.info(
                            f"   [EYE] {usd_mat_name} -- pupils non-metallic, roughness=0.5"
                        )
                    # Metal accessory overrides — PxrDisney metallic=0 in Maya
                    # means chain/tags/zippers look like flat plastic in USD.
                    # _name_check combines the USD mat name with the underlying Pxr
                    # shader node name (e.g. 'veteran_chain_bsdf') so keywords fire
                    # even when the SG is generically named PxrDisneyBsdf[N]SG.
                    #
                    # metallic values are capped at ~0.45 so accessories remain
                    # visible in viewers without an IBL environment.  Full metallic
                    # (0.9+) suppresses all diffuse contribution leaving pure black
                    # in flat-lit web viewers.  0.45 still reads as metallic while
                    # keeping enough diffuse/texture contribution to show colour.
                    elif 'chain' in _name_check:
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.45)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.3)
                        self.logger.info(
                            f"   [METAL] {usd_mat_name} -- chain override metallic=0.45, roughness=0.3"
                        )
                    elif 'tag' in _name_check:
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.4)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.25)
                        self.logger.info(
                            f"   [METAL] {usd_mat_name} -- dog tag override metallic=0.4, roughness=0.25"
                        )
                    elif 'zipr' in _name_check or 'zipper' in _name_check:
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.4)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.35)
                        self.logger.info(
                            f"   [METAL] {usd_mat_name} -- zipper override metallic=0.4, roughness=0.35"
                        )
                    elif 'butn' in _name_check or 'button' in _name_check:
                        _active_shader.CreateInput(
                            "metallic", Sdf.ValueTypeNames.Float
                        ).Set(0.35)
                        _active_shader.CreateInput(
                            "roughness", Sdf.ValueTypeNames.Float
                        ).Set(0.4)
                        self.logger.info(
                            f"   [METAL] {usd_mat_name} -- button override metallic=0.35, roughness=0.4"
                        )

            self.logger.info(f"[LOOKDEV] Sample USD mat names: {usd_mat_name_samples}")
            self.logger.info(f"[LOOKDEV] Scanned {usd_mat_count} USD materials, injected/updated {materials_converted}")
            unmatched = usd_mat_count - materials_converted
            if unmatched > 0:
                self.logger.info(f"[LOOKDEV] {unmatched} USD materials had no SG color match — check SG keys above")
            if materials_converted > 0:
                stage.Save()
                self.logger.info(f"[OK] Created/updated {materials_converted} UsdPreviewSurface materials with colors")
            else:
                self.logger.info(
                    f"[OK] No SG name matches found in {usd_mat_count} USD materials"
                    " — check SG name samples above"
                )

        except Exception as e:
            self.logger.warning(f"[WARNING] Material conversion error: {e}")
            self.logger.warning(traceback.format_exc())

    def _fix_exported_usdc(self, usd_path: Path) -> None:
        """
        Comprehensive post-export structural fix-up for the USDC written by mayaUSD.

        mayaUSD leaves several structural issues that break display in all non-Maya
        USD viewers (needle.tools, usdview, Unreal, Houdini, etc.) and in Maya's own
        VP2 when the file is imported back as a proxy:

        1. outputs:surface wiring  — mayaUSD with RenderMan shading mode creates
           UsdPreviewSurface shaders inside render-context NodeGraphs but forgets to
           connect the material's universal ``outputs:surface`` output.  Any viewer that
           uses the universal surface output (everything except RenderMan) sees grey.
           CRITICAL: Material.outputs:surface must connect DIRECTLY to the Shader prim
           (even when nested inside a NodeGraph) — web viewers (needle.tools, trellis3d,
           three.js / Babylon.js USDZ loaders) do NOT traverse NodeGraph outputs to find
           shaders; they only resolve direct Material→Shader connections.

        2. material:binding  — mayaUSD's ``useRegistry`` shading mode skips writing
           material:binding relationships on skinned meshes when the source shaders are
           RenderMan PxrSurface/PxrDisney nodes.  We rebuild the mesh→SG→Material path
           mapping from Maya cmds and write the missing relationships.

        3. GeomSubset binding  — face-level material assignments exported as GeomSubset
           prims are named after their shading group; we match the name directly to the
           USD Material prim and write material:binding.

        4. Skeleton→Xform re-typing  — mayaUSD types EVERY joint chain as a Skeleton
           prim.  A rig with 121 FK control joints produces 121 Skeleton prims, causing
           UsdSkelImaging to create a separate mesh instance per skeleton and flooding
           the stage with orphaned SkelAnimation prims.  Only the bind skeleton
           (FitSkeleton) stays as Skeleton; all others become lightweight Xform prims.

        5. SkelAnimation deactivation  — SkelAnimation prims paired with the now-Xform'd
           rig-control joints are deactivated so they don't waste evaluation time.

        6. Root-level Mesh deactivation  — any Mesh prim that lives outside the default
           prim's subtree is a blendshape target mesh exported by mayaUSD as a standalone
           prim.  These appear as floating duplicate geometry in viewers.  We deactivate
           them (the UsdSkel.BlendShape prims written by _export_blendshapes_to_usd
           already contain the correct offset data).
        """
        if not USD_AVAILABLE:
            return
        try:
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning(f"[FIX] Could not open stage: {usd_path}")
                return

            # ── Pass 1: Single traversal \u2014 build all lookup maps ─────────────────────
            # mat_name_to_path: Material prim name → SdfPath
            # mat_path_to_shader: Material SdfPath → UsdShade.Shader (UsdPreviewSurface)
            mat_name_to_path = {}
            mat_path_to_shader = {}
            for prim in stage.Traverse():
                ptype = prim.GetTypeName()
                if ptype == 'Material':
                    mat_name_to_path[prim.GetName()] = prim.GetPath()
                elif ptype == 'Shader':
                    s = UsdShade.Shader(prim)
                    sid_attr = s.GetIdAttr()
                    if sid_attr and sid_attr.Get() == 'UsdPreviewSurface':
                        # Walk up to find the owning Material
                        ancestor = prim.GetParent()
                        while ancestor and ancestor.IsValid():
                            if ancestor.GetTypeName() == 'Material':
                                # Keep the first (deepest) match per material
                                if ancestor.GetPath() not in mat_path_to_shader:
                                    mat_path_to_shader[ancestor.GetPath()] = s
                                break
                            ancestor = ancestor.GetParent()

            self.logger.info(
                f"[FIX] Found {len(mat_name_to_path)} USD materials, "
                f"{len(mat_path_to_shader)} with UsdPreviewSurface shaders"
            )

            # ── Fix 1: Wire outputs:surface to the UsdPreviewSurface shader ────────
            # mayaUSD places UsdPreviewSurface shaders inside render-context
            # NodeGraphs (e.g. /Mat/preview/ShaderName).  A direct Material →
            # Shader connection that crosses a NodeGraph boundary is rejected
            # by many USD viewers (needle.tools, three.js, Babylon, etc.).
            #
            # Spec-compliant wiring when a NodeGraph is present:
            #   Material.outputs:surface  →  NodeGraph.outputs:surface
            #   NodeGraph.outputs:surface →  Shader.outputs:surface
            #
            # When the shader lives directly under the Material (INJECT path)
            # we wire directly — no NodeGraph boundary to cross.
            surface_wired = 0
            ng_wired = 0
            direct_wired = 0
            for mat_path, preview_shader in mat_path_to_shader.items():
                mat_prim = stage.GetPrimAtPath(mat_path)
                if not mat_prim.IsValid():
                    continue
                material = UsdShade.Material(mat_prim)
                shader_prim = preview_shader.GetPrim()
                parent_prim = shader_prim.GetParent()

                # Ensure the shader's outputs:surface is explicitly authored.
                # Some USDZ viewers only resolve connections to attributes that
                # exist on the target prim — a dangling path reference is ignored.
                preview_shader.CreateOutput('surface', Sdf.ValueTypeNames.Token)

                if (
                    parent_prim.IsValid()
                    and parent_prim.GetTypeName() == 'NodeGraph'
                    and parent_prim.GetPath() != mat_prim.GetPath()
                ):
                    # Shader is inside a NodeGraph.
                    # Wire NodeGraph.outputs:surface → shader (for NG-aware renderers).
                    node_graph = UsdShade.NodeGraph(parent_prim)
                    ng_output = node_graph.CreateOutput(
                        'surface', Sdf.ValueTypeNames.Token
                    )
                    ng_output.ConnectToSource(
                        preview_shader.ConnectableAPI(), 'surface'
                    )
                    # CRITICAL: wire Material.outputs:surface DIRECTLY to the shader
                    # inside the NodeGraph, bypassing the NodeGraph boundary.
                    # Web viewers (needle.tools, trellis3d, three.js / Babylon.js
                    # USDZ loaders) only follow Material→Shader DIRECT connections;
                    # they do not traverse NodeGraph outputs to find nested shaders.
                    # Without this direct wire, ALL NodeGraph-wrapped materials are
                    # invisible in every web viewer.
                    material.CreateSurfaceOutput().ConnectToSource(
                        preview_shader.ConnectableAPI(), 'surface'
                    )
                    ng_wired += 1
                    self.logger.info(
                        f"   [WIRE-NG-DIRECT] {mat_prim.GetName()} → "
                        f"{shader_prim.GetPath()} (bypassing NodeGraph)"
                    )
                else:
                    # Shader is directly under the Material — wire directly.
                    material.CreateSurfaceOutput().ConnectToSource(
                        preview_shader.ConnectableAPI(), 'surface'
                    )
                    direct_wired += 1
                    self.logger.info(
                        f"   [WIRE-DIRECT] {mat_prim.GetName()} → "
                        f"{shader_prim.GetPath()}"
                    )
                surface_wired += 1
            self.logger.info(
                f"[FIX] Wired outputs:surface on {surface_wired} materials "
                f"({ng_wired} via NodeGraph, {direct_wired} direct)"
            )

            # ── Fix 2: Build Maya mesh→SG map (cmds available at export time) ───────
            mesh_to_sg = {}   # USD Mesh prim transform name → Maya shading group name
            if cmds is not None:
                try:
                    for maya_mesh_shape in (cmds.ls(type='mesh') or []):
                        try:
                            sgs = cmds.listConnections(
                                maya_mesh_shape, type='shadingEngine'
                            ) or []
                            if not sgs:
                                continue
                            parents = (
                                cmds.listRelatives(maya_mesh_shape, parent=True, fullPath=False)
                                or []
                            )
                            transform_name = parents[0] if parents else maya_mesh_shape
                            # mayaUSD can represent namespaces two ways:
                            # 1. stripNamespaces=True  → prim name = short name only
                            # 2. stripNamespaces=False → colon sanitized to underscore
                            short_name = transform_name.split(':')[-1]
                            sanitized = transform_name.replace(':', '_')
                            mesh_to_sg.setdefault(short_name, sgs[0])
                            if sanitized != short_name:
                                mesh_to_sg.setdefault(sanitized, sgs[0])
                        except Exception:
                            pass
                    self.logger.info(f"[FIX] Maya mesh→SG map: {len(mesh_to_sg)} entries")
                except Exception as me:
                    self.logger.warning(f"[FIX] Could not build mesh→SG map: {me}")

            # ── Fix 3: Write material:binding + identify root-level Mesh prims ──────
            default_prim = stage.GetDefaultPrim()
            default_path_prefix = (
                str(default_prim.GetPath()) + '/' if default_prim else ''
            )
            bindings_written = 0
            subset_bindings = 0
            root_mesh_paths = []

            for prim in stage.Traverse():
                ptype = prim.GetTypeName()
                if ptype == 'Mesh':
                    prim_path_str = str(prim.GetPath())
                    if default_path_prefix and not prim_path_str.startswith(default_path_prefix):
                        root_mesh_paths.append(prim.GetPath())
                        continue  # Will deactivate below
                    bind_api = UsdShade.MaterialBindingAPI(prim)
                    existing, _ = bind_api.ComputeBoundMaterial()
                    if existing and existing.GetPrim().IsValid():
                        # Binding exists — but the MaterialBindingAPI schema
                        # may not be applied.  USDZ viewers (needle.tools,
                        # Apple Quick Look, etc.) silently ignore bindings
                        # without the schema applied on the prim.
                        UsdShade.MaterialBindingAPI.Apply(prim)
                        continue
                    # Only skip mesh-level binding when the mesh has GeomSubset children
                    # that are actual per-face material assignments (i.e. named after a
                    # Material prim in the stage).  Topology/blendshape subsets such as
                    # 'blendShape1', 'bottom', 'front', 'left', 'right', 'top' must NOT
                    # block a valid whole-mesh material binding from being written —
                    # those subsets exist for skinning or UV partitioning, not shading.
                    if any(
                        c.GetTypeName() == 'GeomSubset' and c.GetName() in mat_name_to_path
                        for c in prim.GetChildren()
                    ):
                        continue
                    prim_name = prim.GetName()
                    sg_name = mesh_to_sg.get(prim_name)
                    if not sg_name:
                        # Baked meshes: _usdExport[N] suffix was added by the
                        # pipeline during multi-skincluster fixup; strip it to
                        # find the original transform in the map.
                        import re as _re
                        base_name = _re.sub(r'_usdExport\d*$', '', prim_name)
                        if base_name != prim_name:
                            sg_name = mesh_to_sg.get(base_name)
                    if sg_name and sg_name in mat_name_to_path:
                        mat_prim = stage.GetPrimAtPath(mat_name_to_path[sg_name])
                        if mat_prim.IsValid():
                            UsdShade.MaterialBindingAPI.Apply(prim)
                            bind_api.Bind(UsdShade.Material(mat_prim))
                            bindings_written += 1
                elif ptype == 'GeomSubset':
                    # Only process GeomSubsets that represent per-face material
                    # assignments.  mayaUSD names these subsets after the shading
                    # group (e.g. 'Pupils_MatSG', 'PxrDisneyBsdf1SG').  Topology
                    # subsets ('blendShape1', 'bottom', 'front', …) are NOT material
                    # subsets and must be skipped — setting familyName='materialBind'
                    # on them would confuse USD-compliant viewers.
                    subset_name = prim.GetName()
                    if subset_name not in mat_name_to_path:
                        continue
                    # Ensure the subset is declared as a face-element materialBind
                    # family so USD-compliant viewers treat it as a per-face binding.
                    _gs = UsdGeom.Subset(prim)
                    _gs.CreateElementTypeAttr().Set(UsdGeom.Tokens.face)
                    _fam_attr = prim.CreateAttribute(
                        "familyName", Sdf.ValueTypeNames.Token, False
                    )
                    _fam_attr.Set("materialBind")
                    bind_api = UsdShade.MaterialBindingAPI(prim)
                    existing, _ = bind_api.ComputeBoundMaterial()
                    if existing and existing.GetPrim().IsValid():
                        UsdShade.MaterialBindingAPI.Apply(prim)
                        continue
                    mat_prim = stage.GetPrimAtPath(mat_name_to_path[subset_name])
                    if mat_prim.IsValid():
                        UsdShade.MaterialBindingAPI.Apply(prim)
                        bind_api.Bind(UsdShade.Material(mat_prim))
                        subset_bindings += 1

            self.logger.info(
                f"[FIX] Material binding: {bindings_written} Mesh + "
                f"{subset_bindings} GeomSubset relationships written"
            )

            # ── Fix 4: Deactivate root-level blendshape target Mesh prims + rig-fit helpers
            # Root-level prims: blendshape targets exported by mayaUSD outside SkelRoot.
            # FaceGroup fit-geometry (FitEyeSphere, EyeLidInnerArea, LipInner, ForeHead):
            #   Advanced Skeleton face-fitting rig meshes live under FaceGroup/FaceFitSkeleton.
            #   They are scene-construction helpers, not render geometry — deactivate them.
            # Duplicate _usdExport1 meshes: mayaUSD sometimes writes a numbered duplicate
            #   when the same shape is skinned by more than one skin cluster (e.g. body mesh
            #   with a secondary corrective cluster); deactivate the redundant copy.
            fit_geo_keywords = ('FaceGroup', 'FaceFit', 'FitEye', 'FitLip', 'FitFore')
            deactivated_extra = 0

            # Two-pass _usdExport duplicate resolution.
            # When a mesh has both a deformed shape node (e.g. Body_GeoShapeDeformed)
            # and the actual model shape (e.g. model:Body_GeoShape), mayaUSD bakes
            # both.  The deformed-origin prim claims the base name first:
            #   Body_GeoShapeDeformed  → model_Body_Geo_usdExport   (NO material binding)
            #   model:Body_GeoShape    → model_Body_Geo_usdExport1  (HAS SG / material)
            # The previous logic deactivated all numbered variants — this killed the
            # material-bound mesh and left the white un-bound one visible.
            # Correct rule: when un-numbered AND numbered counterpart both exist,
            # deactivate the UN-NUMBERED (deformed-origin, no material) and keep the
            # NUMBERED one (model-origin, has material binding).
            import re as _re_dedup
            _usd_export_by_base = {}  # stripped_base → [(name, prim), ...]

            for prim in stage.Traverse():
                if prim.GetTypeName() != 'Mesh':
                    continue
                p_str = str(prim.GetPath())
                # FaceGroup fit-geometry — always deactivate immediately
                if any(kw in p_str for kw in fit_geo_keywords):
                    prim.SetActive(False)
                    deactivated_extra += 1
                    continue
                name = prim.GetName()
                if '_usdExport' in name:
                    # Strip trailing digits to get the base export name
                    # "model_Body_Geo_usdExport1" → "model_Body_Geo_usdExport"
                    base = _re_dedup.sub(r'\d+$', '', name)
                    _usd_export_by_base.setdefault(base, []).append((name, prim))

            # Deactivate un-numbered (deformed-origin) when numbered counterpart exists.
            # If only one variant exists (numbered or not), keep it unchanged.
            for base, variants in _usd_export_by_base.items():
                if len(variants) > 1:
                    for vname, vprim in variants:
                        if vname == base:  # exact un-numbered = deformed-origin
                            vprim.SetActive(False)
                            deactivated_extra += 1
                            self.logger.info(
                                f"[FIX-DEDUP] Deactivated deformed-origin duplicate: {vname}"
                            )

            for path in root_mesh_paths:
                stage.GetPrimAtPath(path).SetActive(False)
            self.logger.info(
                f"[FIX] Deactivated {len(root_mesh_paths)} root-level blendshape Mesh prims, "
                f"{deactivated_extra} FaceGroup/duplicate Mesh prims"
            )

            # ── Fix 4b: Set NurbsPatch purpose → guide (belt-and-suspenders for
            #           cases where filterTypes didn't strip them) ──────────────────
            nurbs_patched = []
            for prim in stage.Traverse():
                if prim.GetTypeName() == 'NurbsPatch':
                    nurbs_patched.append(prim.GetPath())
            for path in nurbs_patched:
                UsdGeom.Imageable(stage.GetPrimAtPath(path)).CreatePurposeAttr().Set(
                    UsdGeom.Tokens.guide
                )
            if nurbs_patched:
                self.logger.info(
                    f"[FIX] Set purpose=guide on {len(nurbs_patched)} NurbsPatch prims"
                )

            # ── Fix 5: Collect Skeleton paths BOUND to mesh prims ───────────────────────────
            # mayaUSDExport attaches UsdSkelBindingAPI to each skinned Mesh/SkelRoot prim
            # with a 'skel:skeleton' rel pointing to the actual Skeleton.  We keep ONLY
            # those Skeletons — they genuinely drive mesh deformation.  All other Skeleton
            # prims (FK/IK controls, unbound fit-rig hierarchy) are re-typed to Xform.
            bound_skeleton_paths: set = set()
            for prim in stage.Traverse():
                try:
                    skel_binding = UsdSkel.BindingAPI(prim)
                    skel_rel = skel_binding.GetSkeletonRel()
                    if skel_rel and skel_rel.HasAuthoredTargets():
                        for target_path in skel_rel.GetTargets():
                            bound_skeleton_paths.add(target_path)
                except Exception:
                    pass

            # Pick the 'primary' bind skeleton (most joints) for info logging.
            bind_skeleton_path = None
            max_joints = 0
            for skel_path in bound_skeleton_paths:
                skel_prim = stage.GetPrimAtPath(skel_path)
                if not (skel_prim and skel_prim.IsValid()):
                    continue
                sk = UsdSkel.Skeleton(skel_prim)
                joints_attr = sk.GetJointsAttr()
                joints = joints_attr.Get() if joints_attr else None
                count = len(joints) if joints else 0
                if count > max_joints:
                    max_joints = count
                    bind_skeleton_path = skel_path

            self.logger.info(
                f"[FIX] {len(bound_skeleton_paths)} Skeleton(s) bound to meshes via "
                f"BindingAPI; largest: {bind_skeleton_path} ({max_joints} joints)"
            )

            # ── Fix 6: Re-type unbound Skeleton prims → Xform ───────────────────────────────
            # Keep: (1) all Skeletons referenced via BindingAPI (drive mesh deformation),
            #        (2) any FitSkeleton prim (Advanced Skeleton face rig).
            # Re-type: FK/IK control Skeletons that no mesh is bound to.
            # Deactivate: SkelAnimations NOT under any kept Skeleton.
            skeletons_to_retype = []
            skel_anims_to_deactivate = []
            for prim in stage.Traverse():
                ptype = prim.GetTypeName()
                if ptype == 'Skeleton':
                    ppath = prim.GetPath()
                    ppath_str = str(ppath)
                    if ppath in bound_skeleton_paths:
                        continue  # Mesh-bound — keep
                    if 'FitSkeleton' in ppath_str:
                        continue  # Advanced Skeleton face rig — keep
                    skeletons_to_retype.append(ppath)
                elif ptype == 'SkelAnimation':
                    ppath_str = str(prim.GetPath())
                    # Keep SkelAnimations that live under ANY bound Skeleton or FitSkeleton
                    is_under_bound = any(
                        ppath_str.startswith(str(bp) + '/') for bp in bound_skeleton_paths
                    )
                    if not is_under_bound and 'FitSkeleton' not in ppath_str:
                        skel_anims_to_deactivate.append(prim.GetPath())

            for path in skeletons_to_retype:
                stage.GetPrimAtPath(path).SetTypeName('Xform')
            for path in skel_anims_to_deactivate:
                stage.GetPrimAtPath(path).SetActive(False)

            self.logger.info(
                f"[FIX] Re-typed {len(skeletons_to_retype)} Skeleton→Xform, "
                f"deactivated {len(skel_anims_to_deactivate)} orphan SkelAnimation prims"
            )

            # ── Fix 7: Sanitize absolute asset-path references ────────────────────
            # mayaUSD writes RenderMan shader nodes (inside the 'rendermanForMaya'
            # render context) with host-absolute file paths, e.g.
            #   D:\Maya\projects\...\Body_Base_color.png
            # Apple's USDZ spec requires ALL asset references inside the package to
            # be package-relative.  An absolute external path causes Apple Quick Look
            # and usdzviewer.com to reject the entire USDZ (0 polygons / 0 textures).
            # Fix: replace any absolute path with './textures/<filename>' which is
            # the correct package-relative path for our texture layout.
            import os.path as _osp_fix
            n_abs_fixed = 0
            for _fprim in stage.Traverse():
                if _fprim.GetTypeName() != 'Shader':
                    continue
                _fs = UsdShade.Shader(_fprim)
                _fid = _fs.GetIdAttr()
                if not (_fid and _fid.Get() == 'UsdUVTexture'):
                    continue
                _finp = _fs.GetInput('file')
                if not _finp:
                    continue
                _fval = _finp.Get()
                if _fval is None:
                    continue
                _fraw = _fval.path  # Sdf.AssetPath.path — no surrounding '@' signs
                # Detect Windows absolute path (D:\...) or Unix absolute path (/...)
                if not ((len(_fraw) >= 2 and _fraw[1] == ':') or _fraw.startswith('/')):
                    continue  # Already relative — leave untouched
                _fname = _osp_fix.basename(_fraw.replace('\\', '/'))
                if not _fname:
                    continue
                _finp.Set(Sdf.AssetPath(f'./textures/{_fname}'))
                n_abs_fixed += 1
            if n_abs_fixed:
                self.logger.info(
                    f"[FIX] Sanitized {n_abs_fixed} absolute shader asset paths "
                    f"→ package-relative (./textures/)"
                )

            # ── Fix 8: Deactivate ALL NodeGraphs with non-standard USD shader IDs ───
            # Standard USD Preview Material shader IDs — any other shader ID is
            # assumed viewer-incompatible (Pxr*, Arnold, MaterialX, etc.) and will
            # cause strict USDZ validators (Apple Quick Look, usdzviewer.com) to
            # reject the ENTIRE archive.  We scan every active NodeGraph regardless
            # of name ('rendermanForMaya', 'preview', 'renderContext', etc.) so that
            # any shader graph variant introduced by different Maya/RenderMan configs
            # is caught.  Deactivating the NodeGraph removes the unknown prims from
            # the scene graph without touching the UsdPreviewSurface wiring from Fix 1.
            _STANDARD_USD_SHADER_IDS = {
                'UsdPreviewSurface', 'UsdUVTexture', 'UsdTransform2d',
                'UsdPrimvarReader_float2', 'UsdPrimvarReader_float',
                'UsdPrimvarReader_float3', 'UsdPrimvarReader_float4',
                'UsdPrimvarReader_int', 'UsdPrimvarReader_string',
                'UsdPrimvarReader_normal', 'UsdPrimvarReader_point',
                'UsdPrimvarReader_vector', 'UsdPrimvarReader_matrix',
            }
            _rman_ng_deactivated = 0
            _ng_bad: list = []
            for _ngprim in stage.Traverse():
                if _ngprim.GetTypeName() != 'NodeGraph' or not _ngprim.IsActive():
                    continue
                _first_bad_id: str = ''
                for _child in _ngprim.GetAllChildren():
                    if _child.GetTypeName() != 'Shader':
                        continue
                    _cshader = UsdShade.Shader(_child)
                    _cid_attr = _cshader.GetIdAttr()
                    if not _cid_attr:
                        continue
                    _cid = _cid_attr.Get() or ''
                    # Strip any namespace / path prefix
                    # (e.g. 'rendermanForMaya:PxrMayaFile', 'Pxr/PxrSurface')
                    _bare_id = _cid.split(':')[-1].split('/')[-1]
                    if _bare_id not in _STANDARD_USD_SHADER_IDS:
                        _first_bad_id = _cid
                        break
                if _first_bad_id:
                    _ng_bad.append((_ngprim, _first_bad_id))
            for _ngprim, _first_bad_id in _ng_bad:
                _ngprim.SetActive(False)
                _rman_ng_deactivated += 1
                self.logger.info(
                    f"[FIX-NG] Deactivated NodeGraph '{_ngprim.GetName()}' under "
                    f"{_ngprim.GetParent().GetName()} "
                    f"(non-standard shader: {_first_bad_id})"
                )
            if _rman_ng_deactivated:
                self.logger.info(
                    f"[FIX] Deactivated {_rman_ng_deactivated} NodeGraph(s) with "
                    f"non-standard shader IDs → USDZ validator compatible"
                )

            stage.Save()
            self.logger.info(f"[FIX] Structural fix-up complete → {usd_path.name}")

            # ── Post-save validation: dump connection chain for first few materials ──
            # Re-open the saved stage and verify outputs:surface connections
            # so the log proves whether NodeGraph wire-through is actually persisted.
            try:
                vstage = Usd.Stage.Open(str(usd_path))
                # Use three separate counters so each category gets log coverage.
                # DIRECT       = shader directly under Material (8 plain mats)
                # BYPASS-NG    = shader inside a NodeGraph, bypassed directly (22 RfM mats)
                # UNEXPECTED   = target is NOT a Shader — flags a regression
                plain_direct_samples = 0
                bypass_ng_samples = 0
                unexpected_samples = 0
                for vprim in vstage.Traverse():
                    if vprim.GetTypeName() != 'Material':
                        continue
                    vmat = UsdShade.Material(vprim)
                    vsurf = vmat.GetSurfaceOutput()
                    if not vsurf:
                        self.logger.info(
                            f"[VALIDATE] {vprim.GetName()} — no outputs:surface"
                        )
                        continue
                    conns = vsurf.GetAttr().GetConnections()
                    is_direct_shader = False
                    bypasses_ng = False
                    target_prim = None
                    if conns:
                        target_path = conns[0].GetPrimPath()
                        target_prim = vstage.GetPrimAtPath(target_path)
                        is_direct_shader = (
                            target_prim.IsValid()
                            and target_prim.GetTypeName() == 'Shader'
                        )
                        bypasses_ng = (
                            is_direct_shader
                            and target_prim.GetParent().GetTypeName() == 'NodeGraph'
                        )
                    if bypasses_ng and bypass_ng_samples < 3:
                        self.logger.info(
                            f"[VALIDATE-DIRECT-BYPASS-NG] "
                            f"{vprim.GetName()}.outputs:surface → {conns}"
                        )
                        bypass_ng_samples += 1
                    elif is_direct_shader and not bypasses_ng and plain_direct_samples < 3:
                        self.logger.info(
                            f"[VALIDATE-DIRECT] "
                            f"{vprim.GetName()}.outputs:surface → {conns}"
                        )
                        plain_direct_samples += 1
                    elif not is_direct_shader and unexpected_samples < 3:
                        ttype = (
                            target_prim.GetTypeName()
                            if target_prim and target_prim.IsValid()
                            else "invalid"
                        )
                        self.logger.info(
                            f"[VALIDATE-UNEXPECTED] "
                            f"{vprim.GetName()}.outputs:surface → {conns} "
                            f"(target type: {ttype})"
                        )
                        unexpected_samples += 1
                    if plain_direct_samples >= 3 and bypass_ng_samples >= 3:
                        break
                del vstage
            except Exception as ve:
                self.logger.debug(f"[VALIDATE] Connection validation skipped: {ve}")

        except Exception as e:
            self.logger.warning(f"[FIX] Post-export fix-up failed: {e}")
            self.logger.warning(traceback.format_exc())

    def _create_usd_preview_material(
        self,
        stage,
        materials_scope,
        mesh_name: str,
        diffuse_color: 'Gf.Vec3f',
        mesh_prim
    ) -> None:
        """Create a UsdPreviewSurface material and bind it to a mesh"""
        try:
            # Create material prim
            material_path = f"{materials_scope.GetPath()}/{mesh_name}_mat"
            material = UsdShade.Material.Define(stage, material_path)

            # Create UsdPreviewSurface shader
            shader_path = f"{material_path}/PreviewSurface"
            shader = UsdShade.Shader.Define(stage, shader_path)
            shader.CreateIdAttr("UsdPreviewSurface")

            # Set diffuse color from Lambert
            if diffuse_color:
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(diffuse_color)
            else:
                # Default to white if no color found
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.8, 0.8, 0.8))

            # Set reasonable default PBR values
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

            # Connect shader to material surface
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

            # Bind material to mesh
            UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)

            self.logger.debug(f"   [OK] Created UsdPreviewSurface for {mesh_name}")

        except Exception as e:
            self.logger.warning(f"[WARNING] Failed to create material for {mesh_name}: {e}")

    def _wire_diffuse_texture(
        self,
        stage,
        mat_prim,
        surface_shader,
        png_src_path: str,
        usd_dir,
        fallback_color=None,
    ) -> bool:
        """
        Create a UsdUVTexture + UsdPrimvarReader_float2 shader network and
        connect it to ``surface_shader.inputs:diffuseColor``.

        Also copies the source PNG into ``usd_dir/textures/`` so that
        ``_create_usdz_package`` can bundle it automatically.

        The relative asset path ``textures/<basename>`` written into the
        USD is resolved by any USDZ viewer from the archive root — no
        hardcoded paths, no rig-specific logic.  Works for any character
        whose RenderMan Lambert proxy nodes point to real PNG files.

        Returns True on success so callers can fall back to a flat color on
        failure without needing a try/except at the call site.
        """
        try:
            import shutil
            from pxr import Sdf, UsdShade  # type: ignore

            tex_basename = os.path.basename(png_src_path)
            textures_dir = usd_dir / "textures"
            textures_dir.mkdir(exist_ok=True)
            dst_png = textures_dir / tex_basename
            if not dst_png.exists():
                shutil.copy2(png_src_path, str(dst_png))

            # Place helper shaders in the SAME scope as the UsdPreviewSurface.
            # When mayaUSD wraps shaders in a render-context NodeGraph (e.g.
            # /Mat/preview/Shader), creating the texture shaders at the Material
            # root (e.g. /Mat/DiffuseTexture) would produce a cross-NodeGraph
            # connection that many USD viewers refuse to follow.  Using the
            # shader's own parent scope keeps every connection within one scope.
            shader_scope = str(surface_shader.GetPrim().GetParent().GetPath())

            # UV reader — provides the mesh's 'st' primvar to the texture
            st_reader = UsdShade.Shader.Define(
                stage, f"{shader_scope}/TexCoordReader"
            )
            st_reader.CreateIdAttr("UsdPrimvarReader_float2")
            st_reader.CreateInput(
                "varname", Sdf.ValueTypeNames.Token
            ).Set("st")
            # When the mesh has no 'st' primvar exported (e.g. procedural chain/
            # button accessories without UV sets), the reader returns the fallback
            # value instead of (0,0).  Sampling at the texture CENTER (0.5, 0.5)
            # is far more likely to return the correct metal colour than the
            # bottom-left corner pixel (0,0) which is often black or near-black.
            st_reader.CreateInput(
                "fallback", Sdf.ValueTypeNames.Float2
            ).Set(Gf.Vec2f(0.5, 0.5))

            # Diffuse texture — reads the source PNG via relative USDZ path
            tex_shader = UsdShade.Shader.Define(
                stage, f"{shader_scope}/DiffuseTexture"
            )
            tex_shader.CreateIdAttr("UsdUVTexture")
            tex_shader.CreateInput(
                "file", Sdf.ValueTypeNames.Asset
            ).Set(Sdf.AssetPath(f"textures/{tex_basename}"))
            tex_shader.CreateInput(
                "wrapS", Sdf.ValueTypeNames.Token
            ).Set("repeat")
            tex_shader.CreateInput(
                "wrapT", Sdf.ValueTypeNames.Token
            ).Set("repeat")
            tex_shader.CreateInput(
                "sourceColorSpace", Sdf.ValueTypeNames.Token
            ).Set("sRGB")
            # Texture-file-not-found fallback — use the Phase B sampled colour so
            # the material shows a reasonable flat colour rather than black if the
            # PNG is missing from the USDZ (e.g. packaging edge-case).
            if fallback_color is not None:
                tex_shader.CreateInput(
                    "fallback", Sdf.ValueTypeNames.Float4
                ).Set(Gf.Vec4f(
                    float(fallback_color[0]),
                    float(fallback_color[1]),
                    float(fallback_color[2]),
                    1.0,
                ))
            tex_shader.CreateInput(
                "st", Sdf.ValueTypeNames.Float2
            ).ConnectToSource(st_reader.ConnectableAPI(), "result")

            # Explicitly author the output attributes so strict USD validators
            # and online USDZ viewers (which require outputs to be authored,
            # not just schema-defined) can resolve these connections.
            st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
            tex_shader.CreateOutput("rgb", Sdf.ValueTypeNames.Color3f)

            # Wire texture RGB output → PreviewSurface diffuseColor
            surface_shader.CreateInput(
                "diffuseColor", Sdf.ValueTypeNames.Color3f
            ).ConnectToSource(tex_shader.ConnectableAPI(), "rgb")

            return True

        except Exception as _exc:
            self.logger.warning(
                f"   [TEX-WIRE] Failed to wire UsdUVTexture for "
                f"{os.path.basename(png_src_path)}: {_exc}"
            )
            return False

    def _create_usdz_package(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path],
        usdz_path: Path
    ) -> bool:
        """
        Create USDZ package with 64-byte aligned data payloads.

        The Apple/Pixar USDZ spec requires every file's DATA (not header) to
        start at a 64-byte boundary within the ZIP archive.  This allows
        implementations to memory-map entries directly without copying —
        required by Apple's USD WebAssembly engine (usdzviewer.com, AR Quick
        Look) and by any viewer built on the C++ USD runtime.  needle.tools
        (pure JS/WASM parser) also benefits from the structured layout.

        Alignment is achieved by padding the ``extra`` field in each local
        file header with NUL bytes until the data payload starts on a 64-byte
        boundary.  This is the identical approach used by Apple's own usdzip
        command-line tool and Pixar's USD toolkit.

        The rig backup (.rig.mb) is kept ALONGSIDE the USDZ — non-USD file
        types cause strict validators to reject the archive.
        """
        # ── Inner helper: write a single file with 64-byte aligned data ──────────
        _USDZ_ALIGN = 64

        def _write_aligned(zf: zipfile.ZipFile, src: Path, arcname: str) -> None:
            """Add src to zf with its data payload starting on a 64-byte boundary."""
            data = src.read_bytes()
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_STORED
            # Local file header layout (ZIP spec §4.3.7):
            #   30 bytes fixed signature + filename_utf8 + extra
            #   data payload follows immediately.
            # We need: (fp.tell() + 30 + len(filename) + len(extra)) % 64 == 0
            assert zf.fp is not None, "ZipFile.fp is None — file not open for writing"
            current_pos = zf.fp.tell()
            fname_len = len(arcname.encode('utf-8'))
            base_hdr = 30 + fname_len
            pad = (_USDZ_ALIGN - (current_pos + base_hdr) % _USDZ_ALIGN) % _USDZ_ALIGN
            info.extra = b'\x00' * pad
            zf.writestr(info, data)

        try:
            with zipfile.ZipFile(str(usdz_path), 'w', zipfile.ZIP_STORED) as zf:
                # USDZ spec: root USD layer must be the FIRST archive entry.
                _write_aligned(zf, usd_path, usd_path.name)

                # Bundle texture PNGs staged by _wire_diffuse_texture.
                textures_dir = usd_path.parent / "textures"
                if textures_dir.is_dir():
                    tex_files = sorted(
                        f for f in textures_dir.iterdir() if f.is_file()
                    )
                    for tex_file in tex_files:
                        _write_aligned(zf, tex_file, f"textures/{tex_file.name}")
                    if tex_files:
                        self.logger.info(
                            f"[PACKAGE] Bundled {len(tex_files)} texture(s) "
                            f"into USDZ: {', '.join(f.name for f in tex_files[:5])}"
                            + ("..." if len(tex_files) > 5 else "")
                        )

            file_size = usdz_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"[BUNDLE] USDZ package: {usdz_path.name} ({file_size:.1f} MB)")

            # Post-packaging validation: verify contents and 64-byte alignment
            try:
                all_aligned = True
                with zipfile.ZipFile(str(usdz_path), 'r') as zcheck:
                    entries = zcheck.namelist()
                    self.logger.info(
                        f"[USDZ-CHECK] Archive entries ({len(entries)}): "
                        f"{entries[0]} (first)"
                    )
                    for info in zcheck.infolist():
                        comp = "STORED" if info.compress_type == 0 else "DEFLATED"
                        # Data starts after: local header (30) + filename + extra
                        fname_bytes = info.filename.encode('utf-8')
                        extra_bytes = info.extra if info.extra else b''
                        data_offset = (
                            info.header_offset + 30
                            + len(fname_bytes) + len(extra_bytes)
                        )
                        aligned = "YES" if data_offset % _USDZ_ALIGN == 0 else (
                            f"NO (data_offset={data_offset}, "
                            f"mod64={data_offset % _USDZ_ALIGN})"
                        )
                        if "NO" in aligned:
                            all_aligned = False
                        self.logger.info(
                            f"[USDZ-CHECK]   {info.filename}  "
                            f"size={info.file_size}  {comp}  "
                            f"header_offset={info.header_offset}  aligned={aligned}"
                        )
                if all_aligned:
                    self.logger.info(
                        "[USDZ-CHECK] All entries 64-byte aligned — "
                        "compatible with Apple USDZ spec"
                    )
                else:
                    self.logger.warning(
                        "[USDZ-CHECK] Alignment failures detected — "
                        "usdzviewer.com / AR Quick Look may not load this file"
                    )
            except Exception as zce:
                self.logger.warning(f"[USDZ-CHECK] Validation failed: {zce}")

            return True

        except Exception as e:
            self.logger.error(f"USDZ packaging failed: {e}")
            return False

    def _cleanup_intermediate_files(
        self,
        usd_path: Path,
        rig_mb_path: Optional[Path]
    ) -> None:
        """
        Delete intermediate files after USDZ packaging.

        The rig backup (.rig.mb) is kept alongside the USDZ — it is NOT
        bundled inside the archive because non-USD file types cause strict
        online validators to reject the entire package.
        """
        try:
            # Delete .usdc file (already packaged inside the USDZ)
            if usd_path.exists():
                usd_path.unlink()
                self.logger.info(f"[CLEANUP] Cleaned up intermediate: {usd_path.name}")

            # Log where the rig backup lives (alongside USDZ, not inside)
            if rig_mb_path and rig_mb_path.exists():
                self.logger.info(
                    f"[CLEANUP] Rig backup kept alongside USDZ: {rig_mb_path.name}"
                )

            self.logger.info("[OK] Intermediate files cleaned up (bundled in USDZ)")

        except Exception as e:
            self.logger.warning(f"[WARNING] Cleanup warning: {e}")

    def _create_zip_archive(
        self,
        subfolder: Optional[Path],
        usdz_path: Optional[Path],
        usd_path: Path,
        rig_mb_path: Optional[Path],
        zip_path: Path,
        options: ExportOptions
    ) -> bool:
        """
        Create ZIP archive containing all export files.

        This provides better compression and protection for asset distribution.
        """
        try:
            with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                # If organized in subfolder, zip the entire folder
                if subfolder and subfolder.exists():
                    for file in subfolder.iterdir():
                        if file.is_file():
                            # Store with folder structure: AssetName_USD/filename
                            arcname = f"{subfolder.name}/{file.name}"
                            zf.write(str(file), arcname)
                            self.logger.info(f"[PACKAGE] Added to ZIP: {arcname}")
                else:
                    # Add individual files
                    if usdz_path and usdz_path.exists():
                        zf.write(str(usdz_path), usdz_path.name)
                        self.logger.info(f"[PACKAGE] Added to ZIP: {usdz_path.name}")

                    if not options.cleanup_intermediate_files:
                        if usd_path.exists():
                            zf.write(str(usd_path), usd_path.name)
                            self.logger.info(f"[PACKAGE] Added to ZIP: {usd_path.name}")

                        if rig_mb_path and rig_mb_path.exists():
                            zf.write(str(rig_mb_path), rig_mb_path.name)
                            self.logger.info(f"[PACKAGE] Added to ZIP: {rig_mb_path.name}")

            file_size = zip_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"🗜️ ZIP archive: {zip_path.name} ({file_size:.1f} MB)")
            return True

        except Exception as e:
            self.logger.error(f"ZIP archive creation failed: {e}")
            return False

    # =========================================================================
    # IMPORT
    # =========================================================================
