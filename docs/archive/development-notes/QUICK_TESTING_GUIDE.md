# Quick Testing Guide - Asset Manager v1.3.0

## Pre-Test Setup

1. Launch Maya 2025 or later
2. Load Asset Manager plugin
3. Set or create an Asset Manager project
4. Have test assets ready (scenes, models, textures)

---

## Test #1: Remove from Library ✅

### Steps for Remove from Library

1. Select one or more assets in library
2. Click **"Remove Asset"** toolbar button OR right-click and choose "Remove from Library"
3. Confirm removal in dialog

### Expected Results for Remove from Library

- ✅ Confirmation dialog appears
- ✅ Asset(s) removed from library view
- ✅ Files deleted from disk
- ✅ Success message shown
- ✅ Library refreshes automatically

### What to Check for Remove from Library

- Multiple asset removal works
- Error messages for failures
- File actually deleted from project folder
- Asset no longer appears after refresh

---

## Test #2: Drag and Drop ✅

### Steps for Drag and Drop

1. Select an asset in library (Recent, Favorites, or Library tab)
2. Click and drag asset to Maya viewport
3. Release mouse to drop

### Expected Results for Drag and Drop

- ✅ Drag cursor shows asset icon
- ✅ Asset imports into Maya scene
- ✅ File appears in outliner/hierarchy
- ✅ Asset displays correctly in viewport

### What to Check for Drag and Drop

- Works from all tabs (Recent, Favorites, Library)
- Works with different asset types (.ma, .mb, .obj, .fbx)
- Visual feedback during drag
- Maya recognizes the file import

---

## Test #3: Screenshot Toolbar Button ✅

### Steps for Screenshot Toolbar Button

1. Select an asset in library (any tab)
2. Click **"📸 Screenshot"** button in toolbar
3. Position Maya viewport as desired
4. Capture screenshot in dialog

### Expected Results for Screenshot Toolbar Button

- ✅ Screenshot dialog opens
- ✅ Can capture Maya viewport
- ✅ Thumbnail updates in library
- ✅ Library refreshes after capture

### What to Check for Screenshot Toolbar Button

- Works without previewing asset first
- Works with assets that have no thumbnail
- Works with assets that have file-type icons
- Thumbnail immediately updates after capture

---

## Test #4: Screenshot Context Menu ✅

### Steps for Screenshot Context Menu

1. Right-click on any asset in library
2. Choose **"📸 Capture Screenshot"** from menu
3. Position Maya viewport as desired
4. Capture screenshot in dialog

### Expected Results for Screenshot Context Menu

- ✅ Screenshot dialog opens
- ✅ Can capture Maya viewport
- ✅ Thumbnail updates immediately
- ✅ No need to refresh manually

### What to Check for Screenshot Context Menu

- Available in context menu for all assets
- Works independently of preview panel
- Thumbnail refreshes automatically
- Same functionality as toolbar button

---

## Test #5: Screenshot Preview Window (Existing) ✅

### Steps for Screenshot Preview Window

1. Select an asset
2. Ensure preview panel is visible
3. Click **"📸"** button in preview window
4. Capture screenshot

### Expected Results for Screenshot Preview Window

- ✅ Dialog opens (same as other methods)
- ✅ Preview updates after capture
- ✅ Works consistently with other screenshot methods

---

## Quick Troubleshooting

### Remove Asset Not Working

- Check console for error messages
- Verify asset file exists on disk
- Check file permissions
- Ensure project is set correctly

### Drag and Drop Not Working

- Verify asset has valid file path
- Check Maya's script editor for errors
- Try importing asset manually first (double-click)
- Ensure file type is supported by Maya

### Screenshot Not Capturing

- Verify Maya viewport is visible
- Check Maya's playblast settings
- Ensure sufficient disk space
- Verify write permissions to project folder

---

## Console Output to Look For

### Successful Remove

```text
🗑️ Removing asset from library: [Asset Name]
✅ Successfully removed asset: [Asset Name]
🔄 Refreshing library after removal...
```

### Successful Drag

```text
🎯 Starting drag operation for: [Asset Name]
✅ Mime data prepared with file URL: [URL]
🎬 Drag operation completed
```

### Successful Screenshot

```text
📸 Opening screenshot dialog for: [Asset Name]
✅ Thumbnails refreshed after screenshot capture
🔄 Refreshing library after screenshot capture...
```

---

## Known Limitations

1. **Drag and Drop**: Requires Maya to accept file drops (Maya 2025+ should support this)
2. **Screenshot**: Requires visible Maya viewport for capture
3. **Remove**: Cannot undo file deletion (warns user)

---

## Success Criteria

All tests pass = **READY FOR RELEASE** ✅

If any test fails, check:

1. Console output for specific errors
2. Maya Script Editor for Python errors
3. File permissions and disk space
4. Project configuration

---

## Next Steps After Testing

1. ✅ All tests pass → Proceed to UI design updates
2. ⚠️ Some tests fail → Report specific failures for debugging
3. 🔧 Need fixes → Provide console output and error messages

---

**Happy Testing!** 🚀
