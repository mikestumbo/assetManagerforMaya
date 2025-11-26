# RenderMan API Verification Summary

## Official Parameter Definitions

**Source**: `C:\Program Files\Pixar\RenderManProServer-27.0\lib\plugins\Args\`

### PxrSurface.args - Official Parameters (Verified)

#### Diffuse Lobe
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `diffuseGain` | float | 1.0 | Diffuse intensity multiplier |
| `diffuseColor` | color | 0.18 0.18 0.18 | Base diffuse color |
| `diffuseRoughness` | float | 0.0 | OrenNayar roughness |
| `diffuseExponent` | float | 1.0 | Lambertian falloff |

#### Primary Specular Lobe
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `specularFaceColor` | color | 0 0 0 | Fresnel F0 color (artistic mode) |
| `specularEdgeColor` | color | 0 0 0 | Fresnel edge color |
| `specularRoughness` | float | 0.2 | Surface roughness (0-1) |
| `specularFresnelMode` | int | 0 | 0=Artistic, 1=Physical |
| `specularIor` | color | 1.5 1.5 1.5 | Index of refraction (physical mode) |
| `specularAnisotropy` | float | 0.0 | Anisotropic stretch |

#### Other Notable Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `clearcoatFaceColor` | color | Clearcoat layer color |
| `clearcoatRoughness` | float | Clearcoat roughness |
| `subsurfaceGain` | float | SSS intensity |
| `subsurfaceColor` | color | SSS tint |
| `glassIor` | float | Glass refraction index |
| `presence` | float | Opacity/cutout |

### PxrDisney.args - Official Parameters (Verified)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `baseColor` | color | - | Base diffuse color |
| `metallic` | float | - | Metallic response (0-1) |
| `roughness` | float | - | Surface roughness |
| `specular` | float | - | Specular intensity |
| `specularTint` | float | - | Specular color tinting |
| `subsurface` | float | - | Subsurface scattering |
| `sheen` | float | - | Sheen intensity |
| `clearcoat` | float | - | Clearcoat layer |
| `anisotropic` | float | - | Anisotropy amount |

## Key Differences: PxrSurface vs PxrDisney

| Feature | PxrSurface | PxrDisney |
|---------|------------|-----------|
| **Metallic** | ❌ No `metallic` param | ✅ Has `metallic` param |
| **Base Color** | `diffuseColor` | `baseColor` |
| **Specular Color** | `specularFaceColor` | N/A (uses `specular` float) |
| **Roughness** | `specularRoughness` | `roughness` |

## Code Verification Status

### Current Implementation in `maya_scene_parser_impl.py`:

```python
# These are CORRECT for PxrSurface:
diffuseColor      ✓ (exists in PxrSurface.args)
specularRoughness ✓ (exists in PxrSurface.args)
specularColor     ⚠ (should be specularFaceColor)

# This is for PxrDisney only:
metallic          ✓ (exists in PxrDisney.args, NOT in PxrSurface)
```

### Recommendation

1. **For PxrSurface**: Use `specularFaceColor` instead of `specularColor`
2. **For PxrDisney**: Current `metallic` and `roughness` are correct
3. **Detection**: The code already correctly detects node type (`Pxr*`)

---
*Verified: November 26, 2025*
*Source: RenderMan 27.0 Args files - Official Pixar definitions*
*Path: `C:\Program Files\Pixar\RenderManProServer-27.0\lib\plugins\Args\`*
