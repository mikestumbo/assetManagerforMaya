# Asset Manager Thumbnail Troubleshooting Guide

## Overview

If assets aren't getting thumbnails in the Asset Manager, this guide will help you identify and resolve the issue.

## 🔍 Diagnostic Steps

### 1. Check Maya Availability

The Asset Manager requires Maya to generate thumbnails.

**Test:**

```python
# Run this in Maya's Script Editor or Python console
try:
    import maya.cmds as cmds
    print("✓ Maya is available")
    print(f"✓ Maya version: {cmds.about(version=True)}")
except ImportError:
    print("✗ Maya not available - thumbnails cannot be generated")
```

### 2. Check Thumbnail Cache Directory

Verify the thumbnail cache directory exists and is writable.

**Location:** `%USERPROFILE%\Documents\maya\assetManager\thumbnails\`

**Manual Check:**

1. Navigate to: `C:\Users\[YourUsername]\Documents\maya\assetManager\thumbnails\`
2. Check if directory exists
3. Check if it's writable (try creating a test file)

### 3. Test Thumbnail Generation

Use the built-in tools to test thumbnail generation:

**Via Asset Manager UI:**

1. Go to `Tools → Generate Thumbnails...`
2. Follow the prompts
3. Check console output for errors

**Via Script:**

```python
# Run this in Maya
from assetManager import AssetManager
asset_manager = AssetManager()

# Test with a specific asset
asset_path = "path/to/your/asset.ma"
result = asset_manager.generate_asset_thumbnail(asset_path)
print(f"Thumbnail result: {result}")
```

## 🐛 Common Issues and Solutions

### Issue 1: Maya Import Errors

**Symptoms:** Console shows import errors, node name clashes, missing plugins

**Example Errors:**

```text
# Warning: The node 'Veteran_Rig.0001_defaultLayer' still clashed with a node in the main scene.
requires -nodeType "ngst2SkinLayerData" "ngSkinTools2" "2.1.6";
// Error: mirror: could not initialize vertex mapping
```

**Solutions:**

1. **Install Missing Plugins:** Ensure required plugins are installed
   - ngSkinTools2
   - RenderMan for Maya
   - Any other plugins mentioned in errors

2. **Use Namespaces:** The updated code now uses namespaces to avoid clashes

3. **Clean Asset Files:** Remove unnecessary nodes/connections from assets

### Issue 2: Viewport Display Problems

**Symptoms:** Thumbnails are black, empty, or incorrect

**Solutions:**

1. **Check Viewport Settings:**

   ```python
   import maya.cmds as cmds
   # Ensure perspective view exists
   cmds.modelEditor('perspView', edit=True, displayAppearance='smoothShaded')
   ```

2. **Verify Geometry Exists:**
   - Assets must contain visible geometry
   - Check that objects aren't hidden or on invisible layers

3. **Camera Framing:**
   - The code uses `viewFit()` to frame objects
   - Ensure objects have reasonable bounding boxes

### Issue 3: File Permission Issues

**Symptoms:** Can't write thumbnail files

**Solutions:**

1. **Check Directory Permissions:**
   - Ensure Maya has write access to the cache directory
   - Run Maya as administrator if needed

2. **Antivirus Interference:**
   - Some antivirus software blocks file creation
   - Add Maya and cache directory to exclusions

### Issue 4: File Path Issues

**Symptoms:** Can't find assets or thumbnails

**Solutions:**

1. **Check File Paths:**
   - Ensure asset paths don't contain special characters
   - Use forward slashes or proper escaping

2. **Network Drives:**
   - Local drives work better than network paths
   - Consider copying assets locally for thumbnail generation

## 🔧 Advanced Debugging

### Enable Verbose Logging

Add print statements to track thumbnail generation:

```python
# In generate_asset_thumbnail method, add debug prints:
print(f"Attempting to generate thumbnail for: {asset_path}")
print(f"Thumbnail cache dir: {self.thumbnail_cache_dir}")
print(f"Expected thumbnail path: {thumbnail_path}")
```

### Test Individual Steps

Break down the process:

1. **Test Asset Import:**

   ```python
   import maya.cmds as cmds
   cmds.file(new=True, force=True)
   cmds.file("path/to/asset.ma", i=True, type="mayaAscii", namespace="test")
   print(f"Imported objects: {cmds.ls(type='mesh')}")
   ```

2. **Test Playblast:**

   ```python
   cmds.playblast(
       format="image",
       filename="C:/temp/test_thumbnail.png",
       widthHeight=(128, 128),
       showOrnaments=False,
       frame=1,
       viewer=False,
       percent=100
   )
   ```

### Check Asset Manager Settings

Verify the Asset Manager is configured correctly:

```python
asset_manager = AssetManager()
print(f"Current project: {asset_manager.current_project}")
print(f"Thumbnail cache: {asset_manager.thumbnail_cache_dir}")
print(f"Maya available: {asset_manager.MAYA_AVAILABLE}")
```

## 🚀 Performance Tips

### 1. Optimize Asset Files

- Remove unnecessary history
- Delete unused nodes
- Minimize plugin dependencies

### 2. Batch Generation

- Use `Tools → Generate Thumbnails...` for bulk processing
- Process during off-hours for large libraries

### 3. Cache Management

- Clear cache if thumbnails appear corrupted
- Regenerate thumbnails after major asset changes

## 📋 Checklist for Thumbnail Issues

- [ ] Maya is available and running
- [ ] Thumbnail cache directory exists and is writable
- [ ] Assets can be imported without errors
- [ ] Required plugins are installed
- [ ] Viewport displays geometry correctly
- [ ] No file permission issues
- [ ] Asset paths are valid
- [ ] Console shows no critical errors

## 🆘 Getting Help

If thumbnails still aren't working:

1. **Check Console Output:** Look for specific error messages
2. **Test with Simple Assets:** Try with basic geometry files
3. **Update Maya:** Ensure you're using Maya 2025.3+
4. **Clean Installation:** Try reinstalling the Asset Manager

## 🔄 Manual Thumbnail Generation

As a workaround, you can manually create thumbnails:

1. Open asset in Maya
2. Frame geometry in perspective view
3. Use `Window → Playblast` to capture image
4. Save as PNG in thumbnail cache directory
5. Name it `[AssetName].png`

The Asset Manager will use manually created thumbnails if they exist in the cache directory.
