"""
Standalone fix-up script for the already-exported Veteran_Rig.usdz.

Applies the same repairs that _fix_exported_usdc() applies at export time,
so you can verify fixes on the existing file without re-exporting from Maya.

USDZ files are read-only ZIP packages — this script extracts the embedded
.usdc, applies all fixes, re-saves the .usdc, then repacks the USDZ.

Run:  python fix_veteran_usdz.py
"""

import sys
import os
import shutil
import zipfile
import tempfile
import collections

try:
    from pxr import Usd, UsdShade, UsdSkel, UsdGeom
except ImportError:
    print("ERROR: pxr (USD Python) not found.")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────────
USDZ_PATH = r"D:\Maya\projects\Athens_Sequence\assets\Character Models\Veteran\Veteran_Rig.usdz"
BACKUP_PATH = USDZ_PATH + ".bak"

# ── Safety backup ────────────────────────────────────────────────────────────────
if not os.path.exists(BACKUP_PATH):
    shutil.copy2(USDZ_PATH, BACKUP_PATH)
    print(f"Backup: {BACKUP_PATH}")

# ── Extract USDZ → temp dir ──────────────────────────────────────────────────────
tmp_dir = tempfile.mkdtemp(prefix="fix_usdz_")
print(f"Extracting to: {tmp_dir}")
with zipfile.ZipFile(USDZ_PATH, 'r') as zf:
    names = zf.namelist()
    print(f"  USDZ contents: {names}")
    zf.extractall(tmp_dir)

usdc_candidates = [n for n in names if n.endswith(('.usdc', '.usda'))]
if not usdc_candidates:
    print("ERROR: No .usdc/.usda found inside USDZ")
    shutil.rmtree(tmp_dir)
    sys.exit(1)

primary_usdc_name = usdc_candidates[0]
primary_usdc_path = os.path.join(tmp_dir, primary_usdc_name)
print(f"  Primary USD: {primary_usdc_name}\n")

# ── Open ─────────────────────────────────────────────────────────────────────────
stage = Usd.Stage.Open(primary_usdc_path)
if not stage:
    print("ERROR: Could not open stage.")
    shutil.rmtree(tmp_dir)
    sys.exit(1)
print(f"Default prim: {stage.GetDefaultPrim().GetPath() if stage.GetDefaultPrim() else '(none)'}\n")

# ── Pass 1: Build lookup maps (single traversal) ─────────────────────────────────
mat_name_to_path = {}       # Material prim name → SdfPath
mat_path_to_shader = {}     # Material SdfPath → UsdPreviewSurface shader

for prim in stage.Traverse():
    ptype = prim.GetTypeName()
    if ptype == 'Material':
        mat_name_to_path[prim.GetName()] = prim.GetPath()
    elif ptype == 'Shader':
        s = UsdShade.Shader(prim)
        sid_attr = s.GetIdAttr()
        if sid_attr and sid_attr.Get() == 'UsdPreviewSurface':
            ancestor = prim.GetParent()
            while ancestor and ancestor.IsValid():
                if ancestor.GetTypeName() == 'Material':
                    if ancestor.GetPath() not in mat_path_to_shader:
                        mat_path_to_shader[ancestor.GetPath()] = s
                    break
                ancestor = ancestor.GetParent()

print(f"[INFO] {len(mat_name_to_path)} USD Materials  /  {len(mat_path_to_shader)} with UsdPreviewSurface\n")

# ── Fix 1: Wire outputs:surface ──────────────────────────────────────────────────
surface_wired = 0
surface_ok = 0
for mat_path, preview_shader in mat_path_to_shader.items():
    mat_prim = stage.GetPrimAtPath(mat_path)
    if not mat_prim.IsValid():
        continue
    surf_attr = mat_prim.GetAttribute('outputs:surface')
    if surf_attr.IsValid() and surf_attr.HasAuthoredConnections():
        surface_ok += 1
        continue
    UsdShade.Material(mat_prim).CreateSurfaceOutput().ConnectToSource(
        preview_shader.ConnectableAPI(), 'surface'
    )
    surface_wired += 1
print(f"[FIX 1] outputs:surface: {surface_wired} newly wired, {surface_ok} already connected")

# ── Fix 2 & 3: GeomSubset bindings + collect root-level Mesh prims ───────────────
default_prim = stage.GetDefaultPrim()
default_path_prefix = str(default_prim.GetPath()) + '/' if default_prim else ''
root_mesh_paths = []
subset_bindings = 0

for prim in stage.Traverse():
    ptype = prim.GetTypeName()
    if ptype == 'Mesh':
        if default_path_prefix and not str(prim.GetPath()).startswith(default_path_prefix):
            root_mesh_paths.append(prim.GetPath())
    elif ptype == 'GeomSubset':
        bind_api = UsdShade.MaterialBindingAPI(prim)
        existing, _ = bind_api.ComputeBoundMaterial()
        if existing and existing.GetPrim().IsValid():
            continue
        subset_name = prim.GetName()
        if subset_name in mat_name_to_path:
            mat_prim = stage.GetPrimAtPath(mat_name_to_path[subset_name])
            if mat_prim.IsValid():
                bind_api.Bind(UsdShade.Material(mat_prim))
                subset_bindings += 1

print(f"[FIX 2] GeomSubset material:binding: {subset_bindings} written")
print(f"        (Mesh-level binding needs Maya cmds — auto-applied on next export)")

# ── Fix 3: Deactivate root-level blendshape Mesh prims ───────────────────────────
for path in root_mesh_paths:
    stage.GetPrimAtPath(path).SetActive(False)
print(f"[FIX 3] Deactivated {len(root_mesh_paths)} root-level blendshape Mesh prims")

# ── Fix 3b: Set NurbsPatch purpose → guide (hide rig controller surfaces) ─────────
nurbs_fixed = []
for prim in stage.Traverse():
    if prim.GetTypeName() == 'NurbsPatch':
        nurbs_fixed.append(prim.GetPath())
for path in nurbs_fixed:
    p = stage.GetPrimAtPath(path)
    UsdGeom.Imageable(p).CreatePurposeAttr().Set(UsdGeom.Tokens.guide)
print(f"[FIX 3b] Set purpose=guide on {len(nurbs_fixed)} NurbsPatch prims")

# ── Fix 4–5: Re-type FK Skeleton→Xform, deactivate orphan SkelAnimations ─────────
bind_skeleton_path = None
max_joints = 0
for prim in stage.Traverse():
    if prim.GetTypeName() != 'Skeleton':
        continue
    if 'FitSkeleton' in str(prim.GetPath()):
        bind_skeleton_path = prim.GetPath()
        break
    sk = UsdSkel.Skeleton(prim)
    joints_attr = sk.GetJointsAttr()
    joints = joints_attr.Get() if joints_attr else None
    count = len(joints) if joints else 0
    if count > max_joints:
        max_joints = count
        bind_skeleton_path = prim.GetPath()

bind_skel_str = str(bind_skeleton_path) if bind_skeleton_path else ''
print(f"[INFO] Bind skeleton: {bind_skeleton_path}")

skeletons_to_retype = []
skel_anims_to_deactivate = []
for prim in stage.Traverse():
    ptype = prim.GetTypeName()
    if ptype == 'Skeleton':
        if bind_skeleton_path and prim.GetPath() == bind_skeleton_path:
            continue
        skeletons_to_retype.append(prim.GetPath())
    elif ptype == 'SkelAnimation':
        if bind_skel_str and not str(prim.GetPath()).startswith(bind_skel_str + '/'):
            skel_anims_to_deactivate.append(prim.GetPath())

for path in skeletons_to_retype:
    stage.GetPrimAtPath(path).SetTypeName('Xform')
for path in skel_anims_to_deactivate:
    stage.GetPrimAtPath(path).SetActive(False)

print(f"[FIX 4] Re-typed {len(skeletons_to_retype)} Skeleton\u2192Xform")
print(f"[FIX 5] Deactivated {len(skel_anims_to_deactivate)} orphan SkelAnimation prims")

# ── Save, repack ─────────────────────────────────────────────────────────────────
stage.Save()
print(f"\n[OK] Saved .usdc: {primary_usdc_name}")

print(f"Repacking USDZ: {USDZ_PATH}")
with zipfile.ZipFile(USDZ_PATH, 'w', zipfile.ZIP_STORED) as zf:
    zf.write(primary_usdc_path, primary_usdc_name)   # primary must be first
    for name in names:
        if name == primary_usdc_name:
            continue
        file_path = os.path.join(tmp_dir, name)
        if os.path.exists(file_path):
            zf.write(file_path, name)

shutil.rmtree(tmp_dir)
print("[OK] USDZ repacked\n")

# ── Verify ───────────────────────────────────────────────────────────────────────
print("=== POST-FIX VERIFICATION ===")
stage2 = Usd.Stage.Open(USDZ_PATH)
type_counts = collections.Counter()
surface_connected = 0
surface_disconnected = 0
mesh_bound = 0
mesh_unbound = 0

for prim in stage2.Traverse():
    ptype = prim.GetTypeName()
    type_counts[ptype] += 1
    if ptype == 'Material':
        surf_attr = prim.GetAttribute('outputs:surface')
        if surf_attr.IsValid() and surf_attr.HasAuthoredConnections():
            surface_connected += 1
        else:
            surface_disconnected += 1
    elif ptype == 'Mesh':
        if default_path_prefix and str(prim.GetPath()).startswith(default_path_prefix):
            bind_api = UsdShade.MaterialBindingAPI(prim)
            bound, _ = bind_api.ComputeBoundMaterial()
            if bound and bound.GetPrim().IsValid():
                mesh_bound += 1
            else:
                mesh_unbound += 1

print("\nActive type counts:")
for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {v:4d}  {k}")

print(f"\nMaterial outputs:surface : {surface_connected} connected, {surface_disconnected} disconnected")
print(f"Mesh material:binding    : {mesh_bound} bound, {mesh_unbound} unbound (inside SkelRoot)")
print("\nDone. Open the USDZ in https://usd-viewer.needle.tools to verify.")
