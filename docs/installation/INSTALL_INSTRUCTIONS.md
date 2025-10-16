# Asset Manager v1.3.0 - Standard Installation

## ✅ Standard Installation Method

Asset Manager **always** uses DRAG&DROP.mel for installation.

---

## 🚀 Install in Maya (Copy & Paste)

### **MEL Script Editor**

```mel
source "C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/DRAG&DROP.mel";
```

**That's it!** This single command:

- ✅ Installs Asset Manager to Maya scripts directory
- ✅ Sets up proper file structure
- ✅ Creates shelf button for easy access
- ✅ Handles all dependencies automatically
- ✅ Works persistently across Maya sessions

---

## 📋 After Installation

Once installed, Asset Manager can be launched:

1. **Shelf Button**: Click the Asset Manager button on your Maya shelf
2. **Python Command**: `import assetManager; assetManager.show_asset_manager()`
3. **MEL Command**: Asset Manager command (if available in shelf)

---

## 🔍 What to Verify

After running DRAG&DROP.mel, check Maya Script Editor for:

```text
✅ Asset Manager v1.3.0 installed successfully
✅ Installation complete - Shelf button added
✅ EMSA Container initialized
✅ Service registry ready

API Service Registration:
✅ RenderMan service registered and available
   OR
ℹ️ RenderMan not detected (normal if not installed)

✅ USD service registered and available
   OR
ℹ️ USD API not available (normal if mayaUSD not installed)

✅ ngSkinTools2 service registered and available
   OR
ℹ️ ngSkinTools2 not detected (normal if not installed)
```

**No Python errors = Successful installation!** ✅

---

## 🎯 Test the Installation

### 1. Launch Asset Manager

Click the shelf button or run:

```python
import assetManager
assetManager.show_asset_manager()
```

### 2. Check About Dialog

- Click **Help → About**
- Verify trademark acknowledgments display correctly
- Check for HTML formatting with ® and ™ symbols

### 3. Test with Veteran_Rig.mb (if ngSkinTools2 installed)

- Import your rigged character
- Check Script Editor for ngSkinTools2 detection
- Verify layer information is recognized

---

## 🔄 Reinstall/Update

To reinstall or update Asset Manager, simply run DRAG&DROP.mel again:

```mel
source "C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/DRAG&DROP.mel";
```

The installer will handle the update automatically.

---

## 📚 Additional Documentation

- **Testing Checklist**: `docs/MAYA_TESTING_CHECKLIST.md`
- **Quick Commands**: `docs/MAYA_QUICK_COMMANDS.md`
- **Installation Guide**: `docs/MAYA_INSTALLATION_TROUBLESHOOTING.md`
- **Integration Guide**: `docs/MAYA_INTEGRATION_GUIDE_v1.3.0.md`

---

## ✅ Ready for Production

Asset Manager v1.3.0 is ready for:

- ✅ **Production Use** - All 79 tests passing
- ✅ **Maya 2025.3+** - PySide6 compatible
- ✅ **Three API Integrations** - RenderMan, USD, ngSkinTools2
- ✅ **GitHub Publication** - Complete documentation and compliance

---

**Standard Installation Command:**

```mel
source "C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/DRAG&DROP.mel";
```

**Copy this into Maya Script Editor (MEL tab) and press Execute!** 🚀
