# Maya Installation Troubleshooting Guide for Asset Manager v1.1.2

## 🔧 **Quick Fix: Maya Cache Clearing (UPDATED - SYNTAX FIXED)**

The `CLEAR_MAYA_CACHE.mel` script has been **fixed** to resolve MEL syntax errors. If Asset Manager v1.1.2 isn't installing properly in Maya, follow these steps:

### **Step 1: Clear Maya Cache (Required - Now Fixed)**

**The cache cleaner script is now working properly without syntax errors!**

1. **Open Maya Script Editor** (Windows → General Editors → Script Editor)
2. **Load the fixed script:**
   - Method A: File → Load Script... → Select `CLEAR_MAYA_CACHE.mel`
   - Method B: Copy the entire contents of the fixed `CLEAR_MAYA_CACHE.mel` file
3. **Make sure you're in the MEL tab** (not Python tab)
4. **Execute the script** by pressing Ctrl+Enter or clicking Execute
5. **Watch the detailed output** - the script will show progress for each step:
   - Unloading existing plugins
   - Removing old plugin files  
   - Clearing Python cache
   - Refreshing Maya systems
   - Cleaning preferences
6. **Wait for "Cache cleaning completed!" message**
7. **Restart Maya completely** (Very Important!)

### **What Was Fixed in the Cache Cleaner:**

- ✅ **Removed invalid try-catch syntax** (MEL doesn't support try-catch like other languages)
- ✅ **Fixed variable scoping issues** with `$pluginsDir`
- ✅ **Added proper plugin state checking** using `pluginInfo -query -loaded`
- ✅ **Added UI existence checks** before querying shelf buttons
- ✅ **Improved Python module cleanup** with proper list handling

### **Step 2: Fresh Installation**

After restarting Maya:

1. **Drag and drop** the `DRAG&DROP.mel` file into Maya's viewport
2. **Wait for installation** - the script will automatically find v1.1.2 files
3. **Confirm success** - you should see a confirmation dialog

---

## 🚨 **Common Installation Issues & Solutions**

### **Issue 1: Plugin Not Loading**

**Symptoms:** No shelf button appears, plugin not found in Plugin Manager

**Solutions:**

```mel
# Check if plugin exists in the plugins directory
string $pluginsDir = `internalVar -userAppDir` + "plug-ins/";
print($pluginsDir + "assetManager.py");
if (`filetest -f ($pluginsDir + "assetManager.py")`) {
    print("Plugin file exists");
} else {
    print("Plugin file missing - reinstall required");
}

# Try manual loading
loadPlugin "assetManager";
```

### **Issue 2: Old Version Conflicts**

**Symptoms:** Wrong version number, missing features, errors in console

**Solutions:**

1. Run `CLEAR_MAYA_CACHE.mel` script
2. Manually check for old files:
   - Delete `%USERPROFILE%\Documents\maya\2025\plug-ins\assetManager*`
   - Delete any `__pycache__` folders in plugins directory
3. Restart Maya and reinstall

### **Issue 3: Python Import Errors**

**Symptoms:** "Module not found", "Import error" messages

**Solutions:**

```python
# Clear Python module cache
import sys
modules_to_remove = [m for m in sys.modules.keys() if 'assetManager' in m.lower()]
for module in modules_to_remove:
    del sys.modules[module]
    print(f'Removed cached module: {module}')

# Check Python path
import maya.cmds as cmds
user_app_dir = cmds.internalVar(userAppDir=True)
plugin_dir = user_app_dir + 'plug-ins'
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)
    print(f'Added to Python path: {plugin_dir}')
```

### **Issue 4: Shelf Button Missing**

**Symptoms:** Plugin loads but no shelf button appears

**Solutions:**

```mel
# Create shelf button manually
global string $gShelfTopLevel;
string $currentShelf = `tabLayout -query -selectTab $gShelfTopLevel`;

string $buttonCmd = "import sys, os, maya.cmds as cmds; user_app_dir = cmds.internalVar(userAppDir=True); plugin_dir = os.path.join(user_app_dir, 'plug-ins'); sys.path.insert(0, plugin_dir) if plugin_dir not in sys.path else None; import assetManager; assetManager.show_asset_manager()";

shelfButton -parent $currentShelf
    -label "Asset Manager"
    -annotation "Asset Manager v1.1.2 - Collection tabs, thumbnails, enhanced organization"
    -image "menuIconFile.png"
    -command $buttonCmd
    -sourceType "python";
```

---

## 🔍 **Diagnostic Commands**

Run these commands in Maya's Script Editor to diagnose issues:

### **Check Plugin Status**

```mel
// List all loaded plugins
string $plugins[] = `pluginInfo -query -listPlugins`;
for ($plugin in $plugins) {
    if (`gmatch $plugin "*asset*"`) {
        print("Found: " + $plugin + "\n");
    }
}

// Check if assetManager is loaded
if (`pluginInfo -query -loaded "assetManager"`) {
    print("Asset Manager is loaded\n");
    string $version = `pluginInfo -query -version "assetManager"`;
    print("Version: " + $version + "\n");
} else {
    print("Asset Manager is NOT loaded\n");
}
```

### **Check File Locations**

```mel
// Check plugin directory
string $pluginsDir = `internalVar -userAppDir` + "plug-ins/";
print("Plugins directory: " + $pluginsDir + "\n");

// Check for Asset Manager files
string $files[] = {"assetManager.py", "assetManager.mod", "icon_utils.py"};
for ($file in $files) {
    string $fullPath = $pluginsDir + $file;
    if (`filetest -f $fullPath`) {
        print("Found: " + $fullPath + "\n");
    } else {
        print("Missing: " + $fullPath + "\n");
    }
}
```

### **Check Python Environment**

```python
# Check Python paths and modules
import sys
print("Python paths:")
for path in sys.path:
    if 'maya' in path.lower() or 'plug' in path.lower():
        print(f"  {path}")

print("\nAsset Manager modules in cache:")
for module in sys.modules.keys():
    if 'asset' in module.lower():
        print(f"  {module}")
```

---

## 🚀 **Manual Installation (Last Resort)**

If automated installation fails, try manual installation:

### **Step 1: Manual File Copy**

```powershell
# Windows PowerShell commands
$mayaVersion = "2025"  # Adjust for your Maya version
$userDocs = [Environment]::GetFolderPath("MyDocuments")
$pluginsDir = "$userDocs\maya\$mayaVersion\plug-ins"

# Create plugins directory if it doesn't exist
New-Item -ItemType Directory -Force -Path $pluginsDir

# Copy files (adjust source path as needed)
$sourcePath = "C:\path\to\assetManagerforMaya-master"  # Update this path
Copy-Item "$sourcePath\assetManager.py" -Destination $pluginsDir -Force
Copy-Item "$sourcePath\assetManager.mod" -Destination $pluginsDir -Force
Copy-Item "$sourcePath\icon_utils.py" -Destination $pluginsDir -Force
Copy-Item "$sourcePath\icons" -Destination $pluginsDir -Recurse -Force
```

### **Step 2: Manual Plugin Loading**

```mel
// In Maya Script Editor
loadPlugin "assetManager";
pluginInfo -edit -autoload true "assetManager";
```

### **Step 3: Test Installation**

```python
# Test if Asset Manager can be imported and shown
try:
    import assetManager
    assetManager.show_asset_manager()
    print("Asset Manager v1.1.2 loaded successfully!")
except Exception as e:
    print(f"Error: {e}")
```

---

## 📋 **Installation Verification Checklist**

After installation, verify these items:

- [ ] Plugin appears in Window → Settings/Preferences → Plug-in Manager
- [ ] "assetManager" is checked and auto-load is enabled
- [ ] Shelf button exists and shows proper tooltip
- [ ] Clicking shelf button opens Asset Manager window
- [ ] Window title shows "Asset Manager v1.1.2"
- [ ] Help → About shows correct version
- [ ] Help → Check for Updates menu item exists
- [ ] Collection tabs are visible and functional
- [ ] Asset thumbnails display properly
- [ ] Color-coded assets appear in asset library
- [ ] Right-click context menu includes "Asset Type" submenu

---

## 🆘 **Still Having Issues?**

If problems persist after following this guide:

1. **Capture detailed error messages** from Maya's Script Editor
2. **Check Maya version compatibility** (requires Maya 2025.3+)
3. **Verify Python version** (requires Python 3.9+)
4. **Test with a fresh Maya scene** and user preferences
5. **Contact support** with detailed error logs and system information

---

**Note:** This troubleshooting guide covers Maya 2025.3+ installations. For other Maya versions, paths and procedures may vary.
