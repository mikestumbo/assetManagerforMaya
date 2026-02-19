# USD Animation Layers - Option 3 Implementation Plan

## Goal

Enable skeleton animation with mesh deformations in USD Animation workflow WITHOUT the UsdSkelImaging viewport bug.

## Current State

- Export: Baked meshes (T-pose) + skeleton hierarchy, NO skin weights
- Import: USD proxy loads meshes and skeleton, but no binding
- Result: Skeleton moves but meshes don't deform

## Option 3: USD SkelBindingAPI Post-Process

Create UsdSkel bindings programmatically after import using USD Python API.

### Implementation Steps

#### 1. Export Side (Keep Current)

- ✅ Export baked meshes (static geometry)
- ✅ Export skeleton hierarchy (`exportSkels='auto'`)
- ✅ Keep `exportSkin='none'` (avoids viewport bug)
- ✅ Export materials

#### 2. Import Side (New Logic)

After loading USD proxy in `_import_hybrid()` method:

##### A. Get USD Stage

```python
from pxr import Usd, UsdSkel, UsdGeom, Sdf, Vt

proxy_shape = cmds.ls(type='mayaUsdProxyShape')[0]
stage = mayaUsd.ufe.getStage(proxy_shape)
```

##### B. Find Skeleton and Meshes

```python
# Find SkelRoot prim
skel_roots = [p for p in stage.Traverse() if p.IsA(UsdSkel.Root)]

# Find Skeleton prim
skeletons = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]

# Find Mesh prims
meshes = [p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]
```

##### C. Create Animation Layer

```python
# Create anonymous layer for animation/binding
anim_layer = Sdf.Layer.CreateAnonymous('animation')
stage.GetRootLayer().subLayerPaths.append(anim_layer.identifier)

# Set as edit target
stage.SetEditTarget(anim_layer)
```

##### D. Create SkelBinding

```python
for mesh in meshes:
    # Create UsdSkel binding API
    binding_api = UsdSkel.BindingAPI.Apply(mesh)
    
    # Link to skeleton
    binding_api.CreateSkeletonRel().SetTargets([skeleton.GetPath()])
    
    # Set joint influences (simplified - all joints)
    binding_api.CreateJointIndicesPrimvar(False)
    binding_api.CreateJointWeightsPrimvar(False)
    
    # Get original skin data from .rig.mb (challenge here)
    # OR use proximity-based weights (simple fallback)
```

##### E. Configure Binding

```python
# Set skeleton animation binding
skel_binding = UsdSkel.BindingAPI(mesh)
skel_binding.CreateGeomBindTransformAttr().Set(Gf.Matrix4d(1.0))

# Make skeleton animatable
skeleton.CreateJointsAttr()
skeleton.CreateBindTransformsAttr()
skeleton.CreateRestTransformsAttr()
```

### Challenges & Solutions

#### Challenge 1: Getting Original Skin Weights

**Problem:** Baked meshes lost skin weight data  
**Solutions:**

1. **Extract from .rig.mb:** Query Maya skinCluster data before export
2. **Store in USD metadata:** Save weights as custom primvar during export
3. **Proximity-based:** Calculate weights based on joint distance (simple but inaccurate)
4. **Hybrid export:** Export TWO versions - baked meshes + skinned reference

#### Challenge 2: Joint Mapping

**Problem:** Map USD skeleton joints to mesh influences  
**Solution:** Use joint paths and names for matching

#### Challenge 3: Performance

**Problem:** Creating bindings for 93 meshes × 548 joints  
**Solution:** Batch operations, only bind relevant joints per mesh

### Recommended Approach

**Phase 1 (Tomorrow):** Test basic binding creation

- Load USD proxy
- Create animation layer
- Apply UsdSkel.BindingAPI to ONE test mesh
- Verify skeleton movement affects mesh

**Phase 2:** Weight transfer

- Modify export to ALSO save skinCluster data to temp file
- Read skin weights during import
- Apply to USD bindings

**Phase 3:** Optimize

- Batch processing
- Progress reporting
- Error handling

### Code Location

- Modify: `src/services/usd/usd_pipeline_v21.py`
- Method: `_import_hybrid()` (line ~1738)
- Add helper: `_create_usd_skin_bindings()`

### Testing Plan

1. Export character with current settings (baked meshes)
2. Import with USD Animation workflow
3. Verify meshes + skeleton load
4. Run binding creation
5. Test skeleton animation → mesh deformation
6. Compare with full Maya rig workflow

### References

- USD SkelBindingAPI: <https://graphics.pixar.com/usd/docs/api/class_usd_skel_binding_a_p_i.html>
- UsdSkel Overview: <https://graphics.pixar.com/usd/docs/USD-Glossary.html#USDGlossary-Skeleton>
- mayaUSD Python: <https://github.com/Autodesk/maya-usd>

### Notes

- This is the cleanest pure-USD solution
- No Maya rig needed for animation
- Lightweight viewport (no 121 skeleton bug)
- Animation data stays in USD layers
- Compatible with Disney/Pixar pipelines
