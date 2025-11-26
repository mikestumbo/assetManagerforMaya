# OpenUSD API Reference for Asset Manager v1.5

## Overview

This document consolidates the official OpenUSD source code references used for developing the Asset Manager's USD export functionality. The full OpenUSD source is located at:

```
docs/development/OpenUSD-reference/OpenUSD-dev/
```

## Key Reference Files

### 1. UsdPreviewSurface Specification
**Location:** `docs/spec_usdpreviewsurface.rst`

The official specification for UsdPreviewSurface, the universal material format for USD interchange.

#### Core UsdPreviewSurface Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `diffuseColor` | color3f | (0.18, 0.18, 0.18) | Base diffuse/albedo color |
| `emissiveColor` | color3f | (0.0, 0.0, 0.0) | Self-illumination color |
| `useSpecularWorkflow` | int | 0 | 0=Metallic, 1=Specular workflow |
| `specularColor` | color3f | (0.0, 0.0, 0.0) | Specular color (workflow=1) |
| `metallic` | float | 0.0 | Metalness (workflow=0) |
| `roughness` | float | 0.5 | Surface roughness |
| `clearcoat` | float | 0.0 | Clearcoat intensity |
| `clearcoatRoughness` | float | 0.01 | Clearcoat roughness |
| `opacity` | float | 1.0 | Surface opacity |
| `opacityThreshold` | float | 0.0 | Alpha cutoff threshold |
| `ior` | float | 1.5 | Index of refraction |
| `normal` | normal3f | (0, 0, 1) | Normal map input |
| `displacement` | float | 0.0 | Displacement amount |
| `occlusion` | float | 1.0 | Ambient occlusion |

---

### 2. UsdPreviewSurface to PxrSurface Conversion
**Location:** `third_party/renderman/plugin/hdPrman/matfiltConvertPreviewMaterial.cpp`

Official Pixar code for converting UsdPreviewSurface to RenderMan's PxrSurface.

#### Key Mapping Logic (from source)

```cpp
// PxrSurface parameter names used in conversion
(diffuseGain)
(diffuseColor)
(specularFaceColor)      // NOT specularColor!
(specularEdgeColor)
(specularRoughness)
(specularIor)
(clearcoatFaceColor)
(clearcoatEdgeColor)
(clearcoatRoughness)
(glowGain)
(glowColor)
(refractionGain)
(glassIor)
(glassRoughness)
(presence)
(bumpNormal)
```

---

### 3. UsdPreviewSurface Parameters OSL Shader
**Location:** `third_party/renderman/shaders/UsdPreviewSurfaceParameters.osl`

This OSL shader performs the actual conversion in RenderMan, showing exact parameter mappings.

#### Critical Conversion Formula: Metallic to Specular

```osl
// From UsdPreviewSurfaceParameters.osl
float r = (1.0 - ior) / (1.0 + ior);
if (useSpecularWorkflow) {
    specularFaceColorOut = specularColor;
    specularEdgeColorOut = color(1.0,1.0,1.0);
} else {
    float metal = clamp(metallic, 0.0, 1.0); 
    color spec = mix(color(1.0,1.0,1.0), diffuseColor, metal);
    specularFaceColorOut = mix(r * r * spec, spec, metal);
    specularEdgeColorOut = spec;
    diffuseGainOut *= 1.0 - metal;  // Reduce diffuse for metals
}
```

---

### 4. UsdGeomNurbsPatch Schema
**Location:** `pxr/usd/usdGeom/nurbsPatch.h`

The official USD schema for NURBS patches.

#### Required Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `points` | point3f[] | Control vertices (row-major, U=rows, V=cols) |
| `uVertexCount` | int | Vertices in U direction (≥ uOrder) |
| `vVertexCount` | int | Vertices in V direction (≥ vOrder) |
| `uOrder` | int | Polynomial degree + 1 in U |
| `vOrder` | int | Polynomial degree + 1 in V |
| `uKnots` | double[] | Knot vector in U (size = uVertexCount + uOrder) |
| `vKnots` | double[] | Knot vector in V (size = vVertexCount + vOrder) |
| `uForm` | token | "open", "closed", or "periodic" |
| `vForm` | token | "open", "closed", or "periodic" |
| `uRange` | double2 | Param range in U |
| `vRange` | double2 | Param range in V |
| `pointWeights` | double[] | NURBS weights (optional, for rational) |

#### Form Types
- **open**: No continuity constraints
- **closed**: First and last control points coincide
- **periodic**: First and last (order-1) control points coincide

---

### 5. UsdSkel (Skeletal Animation)
**Location:** `pxr/usd/usdSkel/`

Key files:
- `skeleton.h` - Skeleton definition
- `animation.h` - Animation data
- `bindingAPI.h` - Mesh-to-skeleton binding
- `blendShape.h` - Blend shape support
- `bakeSkinning.cpp` - Reference for skinning calculations

---

### 6. RenderMan Args Parser
**Location:** `third_party/renderman/plugin/rmanArgsParser/rmanArgsParser.cpp`

Pixar's official parser for .args files (shader parameter definitions).

---

### 7. hdPrman Material Conversion
**Location:** `third_party/renderman/plugin/hdPrman/material.cpp`

Core material handling for RenderMan in Hydra, including shader network conversion.

---

## Usage in Asset Manager

### Material Extraction (maya_scene_parser_impl.py)

When extracting RenderMan materials, we now correctly use:

```python
# PxrSurface uses specularFaceColor (not specularColor)
spec_color = cmds.getAttr(f'{node}.specularFaceColor') or \
             cmds.getAttr(f'{node}.specularColor')  # fallback

# PxrDisney uses baseColor (not diffuseColor for base)
base_color = cmds.getAttr(f'{node}.baseColor') or \
             cmds.getAttr(f'{node}.diffuseColor')  # fallback
```

### NURBS Export (usd_geometry_converter_impl.py)

Following the UsdGeomNurbsPatch schema, we export:
- Control points in row-major order
- Proper knot vectors with correct padding
- Form tokens matching Maya's surface forms

---

## Additional Resources

### Maya Plugin Integration
**Location:** `third_party/maya/README.md`

Notes on Maya-specific USD integration (MayaUSD plugin).

### RenderMan Plugin
**Location:** `third_party/renderman/README.md`

RenderMan-specific USD integration notes.

---

## Version Information

- **OpenUSD Source Version:** Latest development branch
- **Compatible with:** RenderMan Pro Server 27.0, Maya 2024/2025
- **Asset Manager Version:** 1.5.0

---

## Cross-Reference with RenderMan Args

See also: `RENDERMAN_API_VERIFICATION.md` for the verified .args file parameters from RenderMan Pro Server 27.0's installation.

The Args folder location:
```
C:\Program Files\Pixar\RenderManProServer-27.0\lib\plugins\Args\
```

Key shader files:
- `PxrSurface.args` - Main physically-based shader
- `PxrDisney.args` - Disney BRDF shader
