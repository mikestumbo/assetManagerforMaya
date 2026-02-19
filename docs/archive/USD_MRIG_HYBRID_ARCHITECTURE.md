# USD + .mrig Hybrid Architecture

## Overview

Version 2.0.0 introduces a **hybrid architecture** that uses USD for what it does well, and a new `.mrig` format for Maya rig data that USD cannot handle.

### Why Hybrid?

USD (Universal Scene Description) was designed by Pixar for **geometry interchange**, not rigging. While UsdSkel handles skinned meshes, it doesn't preserve:

- Rig controllers (NURBS curves with colors)
- Constraints (parent, orient, point, aim, pole vector)
- IK handles and solvers
- Set Driven Keys
- Blendshapes with corrective shapes and connections
- Rig hierarchy (MotionSystem, FKSystem, IKSystem)

Attempting to force this data through USD resulted in:

- 166 root joints instead of proper hierarchy
- Controllers not parented to rig structure
- Materials rendering black
- Hands not following arms, feet not following legs

### The Solution

**Use each format for what it does best:**

| Format | Handles                                         | Compatible With                |
|:-------|:------------------------------------------------|:-------------------------------|
| USD    | Geometry, Skeleton, Skin Weights, Materials     | Houdini, Blender, Unreal, Maya |
| .mrig  | Controllers, Constraints, Blendshapes, SDKs, IK | Maya only (rig reconstruction) |

## .mrig Format Specification

The `.mrig` file is a JSON format containing:

```json
{
  "version": "2.0.0",
  "source_file": "character.ma",
  "skeleton_root": "|Group|Main|DeformationSystem|Root",
  
  "controllers": [
    {
      "name": "|Group|Main|FKSystem|Spine_ctrl",
      "short_name": "Spine_ctrl",
      "parent": "|Group|Main|FKSystem",
      "cvs": [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
      "knots": [0, 1, 2, 3, 4],
      "degree": 3,
      "form": 0,
      "color": [1.0, 1.0, 0.0],
      "world_matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
      "visibility": true
    }
  ],
  
  "constraints": [
    {
      "name": "FKSpine1_parentConstraint1",
      "constraint_type": "parentConstraint",
      "driven": "FKSpine1",
      "drivers": ["Spine_ctrl"],
      "weights": [1.0],
      "maintain_offset": true
    }
  ],
  
  "ik_handles": [
    {
      "name": "ikHandle_leg_L",
      "start_joint": "Hip_L",
      "end_joint": "Ankle_L",
      "solver": "ikRPsolver",
      "pole_vector": "PV_leg_L",
      "twist": 0
    }
  ],
  
  "blendshapes": [
    {
      "name": "FacialBlendshapes",
      "base_mesh": "Head_Geo",
      "targets": [
        {
          "name": "Smile",
          "index": 0,
          "weight": 0.0,
          "vertex_indices": [0, 1, 2, 3],
          "position_deltas": [[0.1, 0.05, 0], [0.15, 0.08, 0]],
          "in_betweens": []
        }
      ]
    }
  ],
  
  "blendshape_connections": [
    {
      "blendshape": "FacialBlendshapes",
      "target": "Smile",
      "driver": "Smile_ctrl.translateY",
      "connection_type": "sdk",
      "sdk_keys": [[0, 0], [1, 1]]
    }
  ],
  
  "set_driven_keys": [
    {
      "driver": "Arm_L_ctrl.fkIk",
      "driven": "FKArm_L.visibility",
      "keys": [[0, 1], [1, 0]]
    }
  ],
  
  "hierarchy": {
    "|Group": ["Main", "Geometry"],
    "|Group|Main": ["MotionSystem", "FKSystem", "IKSystem", "DeformationSystem"]
  }
}
```

## Usage

### Export

1. Open Maya scene with rigged character
2. Launch **USD Pipeline Creator** from Asset Manager
3. **Export Tab**:
   - Check "Export Rig Data (.mrig)"
   - Configure which components to include
4. Click "Convert to USD"
5. Two files created:
   - `character.usda` - Geometry, skeleton, weights, materials
   - `character.mrig` - Controllers, constraints, blendshapes, SDKs

### Import

1. Launch **USD Pipeline Creator**
2. **Import Tab**:
   - Browse for `.usda` file
   - `.mrig` file auto-detected if in same folder
   - Or manually browse for `.mrig` file
3. Configure import options
4. Click "Import from USD"
5. Result: Full functional rig!

## Technical Details

### Export Flow

```text
Maya Scene
    │
    ├── MayaSceneParser
    │       │
    │       ├── Meshes, Joints, SkinClusters, Materials
    │       │       → USDExportServiceImpl → .usda/.usdc
    │       │
    │       └── Controllers, Constraints, Blendshapes, SDKs
    │               → MayaRigExporter → .mrig
```

### Import Flow

```text
.usda/.usdc
    │
    └── UsdImportServiceImpl
            │
            ├── mayaUSD import (geometry, skeleton, materials)
            ├── Skin weight reconstruction
            │
            └── MayaRigImporter (.mrig)
                    │
                    ├── Create controllers
                    ├── Apply constraints
                    ├── Rebuild blendshapes
                    └── Restore SDKs/IK handles
```

## Benefits

1. **Clean USD files** - No broken rig data cluttering the USD
2. **Cross-platform geometry** - USD works in Houdini, Blender, Unreal
3. **Perfect Maya round-trip** - .mrig preserves everything Maya-specific
4. **Smaller file sizes** - Rig data in efficient JSON vs verbose USD
5. **Easier debugging** - Human-readable .mrig files
6. **Future-proof** - Easy to extend .mrig format

## Compatibility

- Maya 2024.3+
- MayaUSD 0.34.0+
- RenderMan 27.0+ (for material support)
- Python 3.10+

## Version History

- **2.0.0** - Initial hybrid architecture release
  - Added MayaRigExporter
  - Added MayaRigImporter
  - Updated UI with .mrig options
  - Simplified USD export (geometry focus)
