# Maya Testing Guide - Asset Manager v1.3.0

## 🧪 **Comprehensive Testing Plan for Maya Integration**

This guide provides step-by-step testing procedures for Asset Manager v1.3.0's unified installation architecture in Maya 2025+.

---

## 🚀 **Pre-Testing Setup**

### 1. **Clear Maya Cache (REQUIRED)**

Before any testing, clear Maya's cache to ensure clean state:

```mel
// In Maya Script Editor (MEL), run:
source "C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/CLEAR_MAYA_CACHE.mel";
clearMayaCacheForAssetManager();
```

### 2. **Maya Requirements**

- Maya 2025.3+ (required for PySide6 compatibility)
- Admin/write permissions to Maya scripts directory
- Internet connection (for potential updates)

---

## 🎯 **Installation Testing Methods**

### **Method 1: DRAG&DROP.mel (Recommended)**

**Test the unified installation architecture:**

1. **Open Maya 2025+**
2. **Drag & Drop Installation:**

   ```text
   Drag: DRAG&DROP.mel → Maya viewport
   ```

3. **Expected Output:**

   ```text
   Asset Manager Professional Installer v1.3.0
   🚀 Using unified installation system...
   [Python installation progress...]
   🎨 Creating professional shelf button...
   PROFESSIONAL INSTALLATION COMPLETE!
   Asset Manager v1.3.0 installed successfully
   ```

4. **Validation:**
   - ✅ Shelf button appears with `assetManager_icon.png`
   - ✅ Hover shows `assetManager_icon2.png`
   - ✅ Success dialog appears
   - ✅ No error messages in Script Editor

### **Method 2: Direct Python Installation**

**Test the unified setup.py core:**

1. **In Maya Script Editor (Python):**

   ```python
   import sys
   sys.path.insert(0, r'C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master')
   import setup
   success = setup.install_asset_manager(verbose=True)
   print(f"Installation success: {success}")
   ```

2. **Expected Output:**

   ```text
   Asset Manager v1.3.0 - Unified Installation System
   🚀 Asset Manager v1.3.0 Installation Starting...
   📂 Creating installation directory...
   📁 Copying core files...
   🔧 Creating hot reload tool...
   🎉 ASSET MANAGER v1.3.0 INSTALLATION COMPLETE!
   ```

---

## 🔥 **Hot Reload System Testing**

### **Development Workflow Test**

1. **Install Asset Manager** (using either method above)

2. **Verify Hot Reload Generation:**

   ```python
   # In Maya Script Editor (Python):
   import os
   scripts_dir = r'C:/Users/ChEeP/Documents/maya/scripts'
   hot_reload_path = os.path.join(scripts_dir, 'assetManager', 'dev_hot_reload.py')
   print(f"Hot reload exists: {os.path.exists(hot_reload_path)}")
   ```

3. **Test Hot Reload Functionality:**

   ```python
   # Load the hot reload system
   exec(open(r'C:/Users/ChEeP/Documents/maya/scripts/assetManager/dev_hot_reload.py').read())
   
   # Test quick reload aliases
   r()    # Should reload everything
   qr()   # Should do quick reload
   ```

4. **Expected Behavior:**
   - ✅ Hot reload file auto-generated during installation
   - ✅ `r()` and `qr()` aliases work
   - ✅ Module cache cleared on reload
   - ✅ No import errors

---

## 🎨 **UI Testing Scenarios**

### **Basic UI Launch Test**

1. **Launch Asset Manager:**

   ```python
   # In Maya Script Editor (Python):
   import sys
   sys.path.append(r'C:/Users/ChEeP/Documents/maya/scripts/assetManager')
   import assetManager
   assetManager.show_ui()
   ```

2. **Expected Results:**

   ```text
   🚀 Asset Manager v1.3.0 ready for production use!
   🎨 Launching Asset Manager v1.3.0...
   [UI launches successfully]
   ```

### **Shelf Button Test**

1. **Click shelf button** (if installed via DRAG&DROP.mel)
2. **Expected:**
   - ✅ UI launches immediately
   - ✅ No error dialogs
   - ✅ Professional interface appears

### **Maya Integration Test**

1. **Test Maya-specific features:**

   ```python
   # Test Maya command registration
   import maya.cmds as cmds
   if cmds.commandPort:
       print("✅ Maya commands available")
   
   # Test UI parent integration
   import maya.OpenMayaUI as omui
   if omui.MQtUtil.mainWindow:
       print("✅ Maya main window integration available")
   ```

---

## 🧪 **Validation Tests**

### **Automated Test Suite**

Run the comprehensive test suite:

```python
# In Maya Script Editor (Python):
import sys
sys.path.insert(0, r'C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master')

# Run shelf hover icon test
exec(open(r'C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/tests/test_shelf_hover_icon.py').read())
```

### **Manual Validation Checklist**

**Installation:**

- [ ] DRAG&DROP.mel installs without errors
- [ ] Unified setup.py works in Maya Python
- [ ] Hot reload system auto-generates
- [ ] Shelf button appears with icons

**Functionality:**

- [ ] UI launches from shelf button
- [ ] UI launches from Python command
- [ ] Hot reload `r()` and `qr()` work
- [ ] No Python import errors
- [ ] No Maya crashes or freezes

**Professional Features:**

- [ ] Shelf button shows hover effect
- [ ] Professional success dialog appears
- [ ] All v1.3.0 version strings correct
- [ ] Maya cache clearing works

---

## 🚨 **Troubleshooting Guide**

### **Common Issues & Solutions**

#### Issue: "No module named 'setup'"

```python
# Solution: Check Python path
import sys
print(sys.path)
# Ensure source directory is in path
```

#### Issue: Shelf button not appearing

```mel
// Solution: Manually refresh shelf
source "DRAG&DROP.mel";
DRAG_DROP_assetManager_installer();
```

##### Issue: UI not launching

```python
# Solution: Check Maya environment
try:
    import maya.cmds
    print("✅ Maya environment detected")
except ImportError:
    print("❌ Not in Maya environment")
```

#### Issue: Hot reload not working

```python
# Solution: Regenerate hot reload
import setup
setup.AssetManagerInstaller().create_hot_reload_tool(install_dir)
```

---

## 📊 **Testing Results Template**

```text
=== Asset Manager v1.3.0 Maya Testing Results ===

Maya Version: 2025.x
Test Date: 2025-09-19
Tester: [Your Name]

INSTALLATION TESTS:
[ ] DRAG&DROP.mel installation: PASS/FAIL
[ ] Python setup.py installation: PASS/FAIL
[ ] Hot reload generation: PASS/FAIL
[ ] Shelf button creation: PASS/FAIL

FUNCTIONALITY TESTS:
[ ] UI launch from shelf: PASS/FAIL
[ ] UI launch from Python: PASS/FAIL
[ ] Hot reload system: PASS/FAIL
[ ] Maya integration: PASS/FAIL

PERFORMANCE TESTS:
[ ] Installation speed: Fast/Medium/Slow
[ ] UI launch speed: Fast/Medium/Slow
[ ] Hot reload speed: Fast/Medium/Slow
[ ] Memory usage: Low/Medium/High

NOTES:
[Any observations, issues, or recommendations]

OVERALL RESULT: PASS/FAIL
```

---

## 🎉 **Success Criteria**

✅ **Installation completes without errors**
✅ **All v1.3.0 version strings display correctly**  
✅ **Unified installation architecture works**
✅ **Hot reload system functions properly**
✅ **UI launches and integrates with Maya**
✅ **Professional shelf button with hover effects**
✅ **No Python import or Maya compatibility issues**

---

**Ready for Maya testing! Start with Method 1 (DRAG&DROP.mel) for the complete unified installation experience.**
