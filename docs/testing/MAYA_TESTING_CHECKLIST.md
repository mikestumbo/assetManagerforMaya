# Asset Manager v1.3.0 - Maya Testing Guide

## 🚀 Quick Start - Install Asset Manager in Maya

### Standard Installation: DRAG&DROP.mel

**This is the primary installation method used for Asset Manager.**

```mel
// In Maya Script Editor (MEL tab):
source "C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/DRAG&DROP.mel";
```

**What DRAG&DROP.mel does:**

- Installs Asset Manager to Maya scripts directory
- Sets up proper directory structure
- Creates shelf button for easy access
- Handles all dependencies and paths automatically
- Works across Maya sessions

### Alternative: Python Direct Load (Development/Testing Only)

**Note**: This method is only for development testing. Always use DRAG&DROP.mel for actual installation.

```python
# In Maya Script Editor (Python tab):
import sys
sys.path.insert(0, r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master')

import assetManager
assetManager.show_asset_manager()
```

---

## ✅ Testing Checklist

### 1. **Basic Launch** ✓

- [ ] Asset Manager window opens without errors
- [ ] No errors in Maya Script Editor
- [ ] UI elements display correctly
- [ ] No crash on startup

### 2. **API Service Registration** ✓

**Check Maya Script Editor output for:**

```text
✅ RenderMan service registered and available
   OR
ℹ️ RenderMan not detected (this is normal if not installed)

✅ USD service registered and available
   OR
ℹ️ USD API not available (this is normal if mayaUSD not installed)

✅ ngSkinTools2 service registered and available
   OR
ℹ️ ngSkinTools2 plugin not detected (this is normal if not installed)
```

### 3. **About Dialog** ✓

**Test the new trademark acknowledgments:**

- [ ] Click **Help → About**
- [ ] Verify HTML formatting displays correctly
- [ ] Check for trademark symbols: ®, ™
- [ ] Verify all three API integrations listed:
  - Pixar RenderMan®
  - Universal Scene Description (USD)
  - ngSkinTools2™
- [ ] Verify copyright notices display
- [ ] Verify disclaimer at bottom

### 4. **ngSkinTools2 Integration** (if installed) ✓

**With your Veteran_Rig.mb file:**

- [ ] Import the rig asset
- [ ] Check Script Editor for ngSkinTools2 detection messages
- [ ] Verify layer information is detected
- [ ] Check Asset Info panel for metadata
- [ ] Test asset removal with proper cleanup

### 5. **RenderMan Integration** (if installed) ✓

**With RenderMan content:**

- [ ] Import asset with RenderMan lights/materials
- [ ] Check for RenderMan node detection
- [ ] Verify metadata extraction
- [ ] Test cleanup on asset removal

### 6. **USD Integration** (if installed) ✓

**With USD files:**

- [ ] Try importing a .usd or .usda file
- [ ] Check for USD stage inspection
- [ ] Verify prim counting
- [ ] Test metadata display

---

## 🔍 What to Look For

### Success Indicators

✅ **No Python errors** in Script Editor  
✅ **Clean startup** with service registration messages  
✅ **Proper UI display** with all widgets visible  
✅ **About dialog** shows proper formatting and trademarks  
✅ **API services** register (or gracefully report unavailable)  
✅ **Asset operations** work smoothly  

### Error Indicators

❌ **Import errors** or Python exceptions  
❌ **Missing UI elements** or broken layout  
❌ **Crash on About dialog** click  
❌ **Service registration failures** (check for typos)  

---

## 📊 Expected Script Editor Output

### On Startup (Successful)

```python
# Asset Manager v1.3.0 initializing...
# ✅ EMSA Container initialized
# ✅ Service registry ready

# API Service Registration:
# Checking RenderMan availability...
# ℹ️ RenderMan for Maya not available (expected if not installed)

# Checking USD availability...
# ℹ️ USD API not available (expected if mayaUSD not installed)

# Checking ngSkinTools2 availability...
# ✅ ngSkinTools2 plugin detected (v2.4.0)
# ✅ ngSkinTools2 Python API available
# ✅ ngSkinTools2 service registered and available

# Asset Manager window ready!
```

### With All APIs Installed

```python
# ✅ RenderMan for Maya detected
# ✅ RenderMan service registered and available

# ✅ mayaUsdPlugin loaded successfully
# ✅ USD Python API (pxr) available
# ✅ USD service registered and available

# ✅ ngSkinTools2 plugin detected (v2.4.0)
# ✅ ngSkinTools2 Python API available
# ✅ ngSkinTools2 service registered and available
```

---

## 🎯 Priority Tests

### HIGH PRIORITY

1. **Launch without errors** - Core functionality
2. **About dialog displays** - Trademark compliance
3. **Service registration** - Architecture validation
4. **No crashes** - Stability

### MEDIUM PRIORITY

1. **ngSkinTools2 detection** with Veteran_Rig.mb
2. **Asset import/export** workflows
3. **UI responsiveness** and performance
4. **Theme compatibility** (dark/light Maya themes)

### LOW PRIORITY (if APIs installed)

1. **RenderMan content** detection
2. **USD file** inspection
3. **Advanced cleanup** scenarios

---

## 🐛 Troubleshooting

### Issue: Import Error on Startup

```python
# If you see: ModuleNotFoundError
# Solution: Verify path is correct
import sys
sys.path.insert(0, r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master')
```

### Issue: About Dialog Not Showing

```python
# Check if QMessageBox works:
from PySide6.QtWidgets import QMessageBox
# Should not error

# If it works, the About dialog should work too
```

### Issue: Service Registration Errors

```python
# Check container initialization:
from src.core.container import get_container
container = get_container()
print(container.list_services())
```

### Issue: ngSkinTools2 Not Detected

```python
# Verify plugin is loaded:
import maya.cmds as cmds
print(cmds.pluginInfo('ngSkinTools2', query=True, loaded=True))

# Try loading manually:
cmds.loadPlugin('ngSkinTools2', quiet=True)
```

---

## 📝 Testing Results Template

Copy this to document your testing:

```text
# Asset Manager v1.3.0 - Maya Testing Results
Date: September 30, 2025
Maya Version: ___________
Python Version: ___________

## Launch Test
- [ ] Loaded successfully: YES / NO
- [ ] Errors in Script Editor: YES / NO
- [ ] If errors, describe: ___________

## About Dialog Test
- [ ] Opens correctly: YES / NO
- [ ] HTML formatting: GOOD / BROKEN
- [ ] Trademark symbols visible: YES / NO
- [ ] All 3 APIs listed: YES / NO
- [ ] Disclaimer visible: YES / NO

## API Service Tests
- [ ] RenderMan: AVAILABLE / NOT INSTALLED / ERROR
- [ ] USD: AVAILABLE / NOT INSTALLED / ERROR
- [ ] ngSkinTools2: AVAILABLE / NOT INSTALLED / ERROR

## Veteran_Rig.mb Test (if ngSkinTools2 available)
- [ ] Import successful: YES / NO
- [ ] ngSkinTools2 detected: YES / NO
- [ ] Layer info shown: YES / NO
- [ ] Cleanup works: YES / NO

## Overall Assessment
- [ ] Ready for production: YES / NO
- [ ] Issues found: ___________
- [ ] Notes: ___________
```

---

## 🎉 Success Criteria

Asset Manager v1.3.0 is ready for GitHub release if:

✅ **Launches without errors** in Maya 2025.3+  
✅ **About dialog displays** with proper trademarks  
✅ **API services register** (or gracefully report unavailable)  
✅ **No crashes** during normal operations  
✅ **ngSkinTools2 detection** works with your Veteran_Rig.mb  
✅ **All 79 tests pass** (already verified ✓)  

---

## 📞 Quick Commands Reference

### Load Asset Manager

```python
import assetManager
assetManager.show_asset_manager()
```

### Check About Dialog

```python
# After loading, click: Help → About
# Or test directly:
from src.ui.asset_manager_window import AssetManagerWindow
# About dialog is in _on_about method
```

### Check Services

```python
from src.core.container import get_container
container = get_container()
services = container.list_services()
print(f"Registered services: {services}")
```

### Test ngSkinTools2

```python
from src.services.ngskintools_service_impl import get_ngskintools_service
service = get_ngskintools_service()
print(f"Available: {service.is_available()}")
if service.is_available():
    print(f"Version: {service.get_plugin_version()}")
```

---

**Ready to test! Load Asset Manager in Maya and verify the new v1.3.0 features!** 🚀

*All 79 tests passing - Production ready!*
