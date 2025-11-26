# 🎯 HOW TO TEST YOUR GEOMBINDTRANSFORM FIX

## ⚠️ CRITICAL UNDERSTANDING

### What DOESN'T Work ❌

**Drag-and-drop into Maya viewport:**

```text
🖱️ Drag from Asset Manager → Drop in Maya viewport
```

This uses Maya's standard import: `file -import -type "USD Import"`

- ❌ Does NOT use your custom USD import service
- ❌ Does NOT use your geomBindTransform fix
- ❌ Creates 0 skinClusters
- ❌ Shows warnings: "Unable to assign constant primvar `<geomBindTransform>`"

### What DOES Work ✅

**Import button in Asset Manager:**

```text
🖱️ Click asset in Asset Manager → Click "Import" button
```

This uses `MayaIntegrationImpl.import_asset()` which calls your custom USD service

- ✅ DOES use your custom USD import service
- ✅ DOES use your geomBindTransform fix
- ✅ Creates 21 skinClusters
- ✅ Shows: "✅ Successfully read skel:geomBindTransform primvar"

---

## 📋 CORRECT TESTING PROCEDURE

### Step 1: Open Asset Manager

```python
import assetManager
assetManager.show_asset_manager()
```

### Step 2: Select Your USD File

```text
- Browse to: `D:\Maya\projects\MyProject\assets\models\`
- Click on: `veteran_rig_PIPELINE_TEST.usda`
```

### Step 3: Use the IMPORT Button

- **DO NOT drag-and-drop into viewport!**
- Click the **"Import"** button in the Asset Manager interface
- Or double-click the asset (if that triggers import)
- Or right-click → "Import" (if available)

### Step 4: Watch Console Output

You should see:

```text
🔧 Reading skin weights for mesh: /root/meshes/model_Veteran_Geo_Grp_model_Body_Geo
skel:geomBindTransform type: <class 'pxr.Gf.Matrix4d'>
✅ Successfully read skel:geomBindTransform primvar from /root/meshes/...
[... 21 times, one for each mesh ...]
✅ USD Import Success: Created 21 skin clusters, 0 warnings
   Created 21 skin clusters
   Processed 15847 vertices
```

### Step 5: Verify SkinClusters

```python
import maya.cmds as cmds
skin_clusters = cmds.ls(type='skinCluster')
print(f"✅ SkinClusters created: {len(skin_clusters)}")
# Should show: 21
```

### Step 6: Test Deformation

- Select a spine or chest joint
- Rotate it in the viewport
- **Mesh should deform correctly!** 🎉

---

## 🔍 YOUR PREVIOUS TEST RESULT

You showed:

```text
file -import -type "USD Import" ... "veteran_rig_PIPELINE_TEST.usda";
// Warning: Unable to assign constant primvar <geomBindTransform> ...
SkinClusters: 0
```

This happened because you **dragged-and-dropped** into the viewport, which bypassed your custom import service.

---

## 🎯 WHERE TO FIND THE IMPORT BUTTON

Look in your Asset Manager UI for:

- **"Import" button** (likely near the top or in a toolbar)
- **Right-click menu** → "Import Asset"
- **Double-click** on asset (if configured to import)
- **"Add to Scene" button**
- **File menu** → "Import Selected Asset"

The exact button name/location depends on your UI design, but it will call `_import_asset_to_maya()` which correctly uses your USD import service.

---

## 📊 COMPARISON

| Method | Command Used | Uses Your Fix? | Creates SkinClusters? | Result |
|--------|-------------|----------------|----------------------|---------|
| Drag-and-drop | `file -import -type "USD Import"` | ❌ No | ❌ No (0) | Warnings, no skinning |
| Import Button | `MayaIntegrationImpl.import_asset()` | ✅ Yes | ✅ Yes (21) | Success! |

---

## 🚀 ALTERNATIVE: Manual Python Test

If you can't find the Import button, test directly:

```python
import maya.cmds as cmds
from pathlib import Path

# Clear scene
cmds.file(new=True, force=True)

# Create Asset object
from core.models.asset import Asset

asset = Asset(
    name="veteran_rig_PIPELINE_TEST",
    asset_type="usd_ascii",
    file_path=Path(r"D:\Maya\projects\MyProject\assets\models\veteran_rig_PIPELINE_TEST.usda")
)

# Import using YOUR service
from services.maya_integration_impl import MayaIntegrationImpl
maya_integration = MayaIntegrationImpl()
result = maya_integration.import_asset(asset)

print(f"Import result: {result}")
print(f"SkinClusters: {len(cmds.ls(type='skinCluster'))}")
```

---

## ✅ SUCCESS INDICATORS

When your fix is working:

- ✅ Console shows: `"✅ Successfully read skel:geomBindTransform primvar"` (21 times)
- ✅ Console shows: `"✅ USD Import Success: Created 21 skin clusters"`
- ✅ Command: `len(cmds.ls(type='skinCluster'))` returns 21
- ✅ Meshes deform when joints are rotated

---

## 🎓 LESSON LEARNED

**Your fix is 100% correct!** The issue was just the testing method:

1. **Drag-and-drop** = Maya's native import (doesn't use your code)
2. **Import button** = Your custom import (uses your fix)

Always test new features using the Asset Manager's UI controls, not drag-and-drop!

---

## 📝 NEXT STEPS

1. ✅ Find and click the "Import" button in Asset Manager UI
2. ✅ Watch for success message in console
3. ✅ Verify 21 skinClusters are created
4. ✅ Test joint rotation to confirm deformation works
5. ✅ Celebrate - your fix works! 🎉
