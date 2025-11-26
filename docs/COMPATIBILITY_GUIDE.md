# Asset Manager v1.5.0 - Compatibility Quick Reference

**Release**: November 18, 2025  
**Version**: 1.5.0

## ✅ Supported Software Versions

| Software | Version | Status |
|----------|---------|--------|
| **Maya** | 2026.3 | ✅ Fully Compatible |
| **MayaUSD** | 0.34.5 | ✅ Latest Plugin |
| **RenderMan** | 27 | ✅ Complete Support |
| **Python** | 3.11+ | ✅ Maya 2026+ |
| **PySide6** | Latest | ✅ UI Framework |

## 🎨 RenderMan 27 Shader Support

### Surface Shaders (11)

- `PxrSurface` - Primary physically-based shader
- `PxrMarschnerHair` - Hair and fur
- `PxrVolume` - Volume rendering
- `PxrLMDiffuse`, `PxrLMGlass`, `PxrLMMetal`, `PxrLMPlastic`
- `PxrLMSkin`, `PxrLMSubsurface`
- `PxrDisplace`

### Patterns & Textures (13)

- `PxrTexture`, `PxrPtexture`, `PxrMultiTexture`
- `PxrBump`, `PxrNormalMap`
- `PxrRoundCube`, `PxrFractal`, `PxrWorley`, `PxrVoronoise`
- `PxrChecker`, `PxrRamp`, `PxrHairColor`
- `PxrDirt`, `PxrFlakes`

### Utility Nodes (12)

- `PxrBlend`, `PxrLayerSurface`, `PxrLayerMixer`
- `PxrMatteID`, `PxrVariable`
- `PxrToFloat`, `PxrToFloat3`
- `PxrHSL`, `PxrColorCorrect`, `PxrExposure`, `PxrGamma`
- `PxrInvert`, `PxrClamp`, `PxrMix`, `PxrRemap`, `PxrThreshold`

### Light Filters (7)

- `PxrIntMultLightFilter`, `PxrBlockerLightFilter`
- `PxrRodLightFilter`, `PxrCookieLightFilter`
- `PxrGoboLightFilter`, `PxrRampLightFilter`
- `PxrBarnLightFilter`

### Lights (8)

- `PxrDomeLight`, `PxrRectLight`, `PxrDiskLight`
- `PxrSphereLight`, `PxrCylinderLight`
- `PxrDistantLight`, `PxrPortalLight`, `PxrMeshLight`

## 📦 Installation

Same methods as previous versions:

### Method 1: Drag & Drop (Recommended)

1. Open Maya 2026.3
2. Drag `DRAG&DROP.mel` into viewport
3. Follow on-screen instructions

### Method 2: Command Line (Windows)

```batch
install.bat
```

### Method 3: Command Line (Unix/Linux/macOS)

```bash
./install.sh
```

## 🔧 API Version Information

```python
# Plugin metadata (from assetManager.py)
PLUGIN_VERSION = "1.5.0"
PLUGIN_REQUIRED_API_VERSION = "20260000"  # Maya 2026

# Supported versions
SUPPORTED_MAYA_VERSION = "2026.3"
SUPPORTED_MAYAUSD_VERSION = "0.34.5"
SUPPORTED_RENDERMAN_VERSION = "27"
```

## 🎯 Key Features for Maya 2026.3

1. **Full API Compatibility**
   - Updated for Maya 2026 Python API
   - PySide6 UI integration
   - Modern Qt framework support

2. **MayaUSD 0.34.5 Integration**
   - Latest USD plugin features
   - Improved material handling
   - RenderMan preservation on import

3. **RenderMan 27 Support**
   - 75+ shaders supported
   - Proper USD material export
   - Parameter preservation

## 📝 Quick Start

### Verify Installation

```python
# In Maya Script Editor
import maya.cmds as cmds

# Check plugin version
if cmds.pluginInfo('assetManager', query=True, loaded=True):
    version = cmds.pluginInfo('assetManager', query=True, version=True)
    print(f"Asset Manager version: {version}")
else:
    print("Asset Manager not loaded")
```

### Launch Asset Manager

- **Menu**: `File → Asset Manager`
- **Hotkey**: `Ctrl+Shift+A` (Windows) / `Cmd+Shift+A` (macOS)

### USD Pipeline

- **Export to USD**: `Tools → USD Pipeline Creator` (Ctrl+U)
- **Supports**: .usda, .usdc, .usdz formats
- **Includes**: Geometry, Materials (RenderMan), Rigging, NURBS curves

## ⚠️ Important Notes

### RenderMan Users

- All RenderMan 27 shaders are recognized
- Materials export with proper `ri:` shader IDs
- Import preserves RenderMan shaders (no forced conversion)

### MayaUSD Users

- Plugin loads automatically when needed
- `shadingMode=useRegistry` preserves material types
- Skeleton/animation import enabled by default

### Upgrade from Previous Versions

- **Fully backward compatible**
- No configuration changes needed
- Existing projects work unchanged

## 🐛 Troubleshooting

### Issue: Plugin doesn't load

**Solution**: Ensure Maya 2026.3 is installed

### Issue: MayaUSD not found

**Solution**: Install MayaUSD 0.34.5 from Autodesk

### Issue: RenderMan materials not exporting

**Solution**: Verify RenderMan 27 is installed and licensed

## 📚 Documentation

- **README.md**: Complete feature documentation
- **releases/v1.5.0-release-notes.md**: Detailed release notes
- **docs/**: User guides and examples
- **CHANGELOG.md**: Full version history

## 🔗 Links

- **GitHub**: [Your Repository URL]
- **Issues**: Report bugs or request features
- **Wiki**: Detailed guides and tutorials

## 📞 Support

For issues or questions:

1. Check documentation in `docs/` folder
2. Review release notes
3. Check GitHub Issues
4. Contact developer

---

**Updated for Maya 2026.3, MayaUSD 0.34.5, and RenderMan 27!** 🚀
