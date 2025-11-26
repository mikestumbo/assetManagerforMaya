# USD Pipeline Creator Test Plan

## Version 1.5.0 - Maya 2026.3 + MayaUSD 0.34.5 + RenderMan 27

## Overview

Test the three reported issues from final testing:

1. **NURBS curves not being exported**
2. **Blendshapes not being hidden during export**
3. **RenderMan materials not importing from asset manager**

## Pre-Test Setup

### 1. Run Diagnostic Script

```python
# In Maya Script Editor (Python tab):
exec(open(r"C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master\test_scripts\DIAGNOSE_USD_PIPELINE_CREATOR.py").read())
```

This will check:

- ✅ NURBS curves in scene
- ✅ BlendShape nodes and visible targets
- ✅ RenderMan materials present
- ✅ USD Pipeline services available
- ✅ Cleanup scripts functional

### 2. Create Test Scene

For complete testing, your scene should have:

**NURBS Curves (Rig Controls):**

```python
# Create some colored NURBS curves
import maya.cmds as cmds

# Circle controller
circle = cmds.circle(name="ctrl_circle", radius=2)[0]
cmds.setAttr(f"{circle}.overrideEnabled", 1)
cmds.setAttr(f"{circle}.overrideColor", 13)  # Red

# Square controller
square = cmds.nurbsSquare(name="ctrl_square", sideLength=3)[0]
cmds.setAttr(f"{square}.overrideEnabled", 1)
cmds.setAttr(f"{square}.overrideColor", 6)  # Blue

print("✅ Created 2 NURBS rig controls")
```

**BlendShapes:**

```python
# Create blendshape test
sphere1 = cmds.polySphere(name="character_head")[0]
sphere2 = cmds.polySphere(name="smile_target")[0]
cmds.move(0, 0, 2, sphere2)
cmds.scale(1.2, 1, 1, sphere2)

# Create blendshape
bs = cmds.blendShape(sphere2, sphere1, name="facial_bs")[0]

# Target should be visible before export
print(f"✅ Created blendShape: {bs}")
print(f"   Target visible: {cmds.getAttr(f'{sphere2}.visibility')}")
```

**RenderMan Materials:**

```python
# Create RenderMan PxrSurface material
mat = cmds.shadingNode('PxrSurface', asShader=True, name='char_skin')
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f'{mat}SG')
cmds.connectAttr(f'{mat}.outColor', f'{sg}.surfaceShader')

# Assign to geometry
cmds.select(sphere1)
cmds.sets(edit=True, forceElement=sg)

print(f"✅ Created RenderMan material: {mat}")
```

---

## Test 1: NURBS Curves Export

### Expected Debug Output for NURBS Curves Export

When you export, you should see in Script Editor:

```text
🔧 PRE-EXPORT CLEANUP: Running blendshape cleanup...
🔍 SCENE PARSED: Found X meshes, Y materials, Z joints, **W curves**
🎯 NURBS EXPORT CHECK: options.export_nurbs_curves=True, scene_data.nurbs_curves count=W
🎯 STARTING NURBS EXPORT: W curves found
✨ Exported W NURBS curves (rig controls)
```

### Export Steps

1. Open **Tools → USD Pipeline Creator**
2. Check **☑ Include Rig Controls (NURBS) - INDUSTRY FIRST! ✨**
3. Set export path: `C:\temp\test_export.usda`
4. Click **Export USD**
5. **WATCH SCRIPT EDITOR** for debug output

### Test 1 Success Criteria

- ✅ Debug log shows: `Found X NURBS curves to extract`
- ✅ Debug log shows: `🎯 STARTING NURBS EXPORT`
- ✅ Debug log shows: `✨ Exported X NURBS curves`
- ✅ USD file contains `def NurbsCurves` prims
- ✅ Curves have color attributes preserved

### Test 1 Failure Cases

**Look for these messages:**

- `⚠️  No NURBS curves found in scene!` → Scene has no curves
- `🎯 NURBS EXPORT SKIPPED: export_nurbs_curves=False` → UI checkbox unchecked
- `🎯 NURBS EXPORT SKIPPED: curves found=0` → Parser found nothing

**Copy the full Script Editor output** and we'll diagnose together.

---

## Test 2: BlendShape Cleanup

### Expected Debug Output for BlendShape Cleanup

```text
🔧 PRE-EXPORT CLEANUP: Running blendshape cleanup...
Found X blendShape node(s) in scene
Analyzing blendShape node: facial_bs
  Found Y target mesh(es)
  Hidden Y target mesh(es)
Cleanup complete: Hidden N mesh(es), deleted M duplicate(s)
```

### Steps

1. **Before export:** Check outliner - blendshape targets should be **VISIBLE**
2. Run diagnostic script to confirm targets are visible
3. Export USD file
4. **After export:** Check outliner - targets should be **HIDDEN** (eye icon closed)

### Test 2 Success Criteria

- ✅ Debug log shows: `Found X blendShape node(s)`
- ✅ Debug log shows: `Hidden Y target mesh(es)`
- ✅ Outliner shows targets are hidden after export
- ✅ USD file does NOT contain target meshes (only base mesh)

### Test 2 Failure Cases

**Check these:**

- Are targets still visible after export? → Cleanup script didn't run
- Does USD file contain target meshes? → Targets not hidden before scene parsing
- No cleanup messages in Script Editor? → Script not being called

**Copy Script Editor output showing cleanup phase.**

---

## Test 3: RenderMan Material Import

### Expected Behavior

When importing USD file through Asset Manager:

- RenderMan materials should be preserved as `PxrSurface` nodes
- Material assignments should be maintained
- Shader networks should be intact

### Import Steps

1. Export scene with RenderMan materials using Pipeline Creator
2. Create **new Maya scene**
3. Open **Asset Manager**
4. Import the exported USD file
5. **Check Hypershade** for material types

### Test 3 Success Criteria

- ✅ Materials import as `PxrSurface` (not `lambert` or `standardSurface`)
- ✅ Material assignments preserved on meshes
- ✅ Shader attributes maintained

### Test 3 Failure Cases

**Check:**

- Do materials import as `lambert`/`standardSurface`? → Material conversion issue
- Are materials missing entirely? → USD material encoding problem
- Different shader type than exported? → Import conversion forcing wrong type

**Note:** This should already be fixed by removing `preferredMaterial=standardSurface` from import options (v1.4.3), but we'll verify it works with RenderMan 27.

---

## Diagnostic Commands

### Check What's in USD File

```python
from pxr import Usd, UsdGeom, UsdShade # type: ignore

stage = Usd.Stage.Open(r"C:\temp\test_export.usda")

# Check for NURBS curves
for prim in stage.Traverse():
    if prim.GetTypeName() == "NurbsCurves":
        print(f"✅ Found NURBS: {prim.GetPath()}")

# Check for materials
for prim in stage.Traverse():
    if prim.IsA(UsdShade.Material):
        print(f"✅ Found Material: {prim.GetPath()}")
        material = UsdShade.Material(prim)
        for output in material.GetOutputs():
            print(f"   Output: {output.GetBaseName()}")

# List all mesh prims (check for unwanted targets)
for prim in stage.Traverse():
    if prim.IsA(UsdGeom.Mesh):
                print(f"📦 Mesh: {prim.GetPath()}")
```

### Force Cleanup Manually

```python
# Test blendshape cleanup in isolation
import sys
sys.path.insert(0, r"C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master")

from HIDE_BLENDSHAPE_TARGETS import cleanup_blendshapes_for_export

# Run cleanup
hidden_count, deleted_count = cleanup_blendshapes_for_export()
print(f"Cleanup result: {hidden_count} hidden, {deleted_count} deleted")
```

---

## Expected Full Export Log

Here's what a **successful export** should look like in Script Editor:

```text
[assetManager.usd_export_service] Starting Maya → USD export...
🔧 PRE-EXPORT CLEANUP: Running blendshape cleanup...
Found 1 blendShape node(s) in scene
Analyzing blendShape node: facial_bs
  Found 1 target mesh(es)
  Hidden 1 target mesh(es)
Cleanup complete: Hidden N mesh(es), deleted M duplicate(s)
```

🔍 STARTING SCENE PARSE...
Found 2 NURBS curves to extract
Successfully extracted 2 NURBS curves
Extracted 2 NURBS curves (rig controls)
Parsed scene: 1 meshes, 1 materials, 0 joints, 2 curves

📝 Creating USD stage at: C:\temp\test_export.usda
Creating USD geometry for: character_head
Exporting 1 materials...
Exported 1 materials

🎯 NURBS EXPORT CHECK: options.export_nurbs_curves=True, scene_data.nurbs_curves count=2
🎯 STARTING NURBS EXPORT: 2 curves found
Exporting NURBS curve: ctrl_circle
Exporting NURBS curve: ctrl_square
✨ Exported W NURBS curves (rig controls)

Export complete in 1.23s
USD export successful: C:\temp\test_export.usda

```text

---

## Reporting Issues

If any test fails, please provide:

1. **Full Script Editor output** (copy entire log)
2. **Scene description:**
   - How many NURBS curves?
   - How many blendShape nodes?
   - What RenderMan materials?
3. **Diagnostic script results**
4. **USD Pipeline Creator options** (screenshot or list checked boxes)
5. **USD file inspection results** (what prims are in the file?)

The debug logging will tell us exactly where things go wrong! 🔍

---

## Clean Code Notes

This test plan follows **Clean Code principles**:

- **Single Responsibility:** Each test focuses on one feature
- **Clear Intent:** Every step has explicit success criteria
- **Fail-Fast:** Diagnostic checks before main tests
- **Observable:** Extensive debug output for troubleshooting
- **Repeatable:** Copy-paste commands for consistent testing

The code already has comprehensive logging (🔧 🔍 🎯 ✨ emojis), so failures will be immediately obvious in Script Editor output.
