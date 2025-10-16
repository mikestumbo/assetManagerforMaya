# Bug Fixes - October 6, 2025 (Second Round)

## Issues Reported from Maya Testing

### ❌ Issue #1: Redundant Screenshot Button in Toolbar

**Problem**: Screenshot button in toolbar was redundant because the preview panel already has one with custom icon.

**Fix**:

- Removed "📸 Screenshot" button from main toolbar
- Kept only the custom icon screenshot button in preview panel (RIGHT_A)
- Removed unused handler methods: `_on_capture_screenshot_for_selected()` and `_refresh_library_after_screenshot()`

**Files Modified**:

- `src/ui/asset_manager_window.py` - Removed button from `_create_main_toolbar()` and cleaned up handlers

---

### ⚠️ Issue #2: Screenshot Context Menu Using Emoji Instead of Custom Icon

**Problem**: Right-click "Capture Screenshot" menu item used emoji 📸 instead of custom icon.

**Fix**:

- Added `_get_screenshot_icon_path()` method to `AssetLibraryWidget`
- Updated context menu to use custom `screen-shot_icon.png` icon
- Falls back gracefully if icon not found
- Changed menu text from "📸 Capture Screenshot" to "Capture Screenshot" with icon

**Code Added**:

```python
# Screenshot capture action with custom icon
screenshot_action = menu.addAction("Capture Screenshot")
# Try to use custom screenshot icon
try:
    screenshot_icon_path = self._get_screenshot_icon_path()
    if screenshot_icon_path:
        from PySide6.QtGui import QIcon
        screenshot_action.setIcon(QIcon(screenshot_icon_path))
except Exception as e:
    print(f"⚠️ Could not set custom screenshot icon in menu: {e}")
screenshot_action.triggered.connect(lambda: self._capture_screenshot(asset))
```

**Files Modified**:

- `src/ui/widgets/asset_library_widget.py` - Added icon path method and updated context menu

---

### ❌ Issue #3: Thumbnail Not Syncing After Screenshot Capture

**Problem**: After capturing screenshot, the library icon view didn't update to show new thumbnail.

**Root Cause**:

- Only called `refresh_thumbnails_for_assets()` which is partial refresh
- Didn't clear thumbnail cache, so old cached thumbnail was reused
- Didn't trigger full library reload

**Fix**:

- Clear thumbnail cache for the asset using `clear_cache_for_file()`
- Call `refresh_library()` for full library reload instead of partial refresh
- This ensures all views (Library, Recent, Favorites) update properly

**Code Updated**:

```python
def refresh_callback():
    """Refresh thumbnails and library display after screenshot capture"""
    try:
        # Clear thumbnail cache for this asset to force reload
        if hasattr(asset, 'file_path') and self._thumbnail_service:
            try:
                self._thumbnail_service.clear_cache_for_file(asset.file_path)
                print(f"🗑️ Cleared thumbnail cache for {asset.display_name}")
            except Exception as cache_error:
                print(f"⚠️ Could not clear cache: {cache_error}")
        
        # Force full library refresh to update all views
        self.refresh_library()
        print("✅ Library refreshed after screenshot capture")
    except Exception as e:
        print(f"⚠️ Error refreshing after screenshot: {e}")
```

**Files Modified**:

- `src/ui/widgets/asset_library_widget.py` - Updated `_capture_screenshot()` refresh callback

---

### ❌ Issue #4: No Metadata in Asset Information Tab

**Problem**: Asset Information panel (RIGHT_B) stayed empty when selecting assets.

**Root Cause**:

- `asset_selected` signal from `AssetLibraryWidget` was not connected to metadata display update
- Only `asset_info_requested` signal updated metadata (triggered by properties dialog)

**Fix**:

- Connected `asset_selected` signal directly to `_update_asset_info_display()` method
- Now metadata updates immediately when any asset is selected in library
- Works for single-click selection, not just double-click or properties

**Code Added**:

```python
# Connect selection to metadata display update
self._library_widget.asset_selected.connect(self._update_asset_info_display)
```

**Files Modified**:

- `src/ui/asset_manager_window.py` - Added signal connection in `_create_center_library_panel()`

---

## Testing Results Expected

### Screenshot Context Menu

- ✅ Right-click asset → See "Capture Screenshot" with custom camera icon
- ✅ Click menu item → Screenshot dialog opens
- ✅ Capture screenshot → Library icon updates immediately
- ✅ Works in all tabs (Library, Recent, Favorites)

### Thumbnail Sync

- ✅ Capture screenshot from context menu → Icon updates automatically
- ✅ Capture screenshot from preview button → Icon updates automatically
- ✅ No need to manually refresh library
- ✅ Works across all views (list, icon, tabs)

### Asset Information Panel

- ✅ Click any asset in library → Metadata appears in right panel
- ✅ Shows: Name, Type, File, Size, Tags, Metadata
- ✅ Updates immediately on selection change
- ✅ Works in all tabs

### UI Cleanup

- ✅ No redundant screenshot button in toolbar
- ✅ Clean toolbar with only essential buttons
- ✅ Screenshot accessible via: Preview panel + Context menu

---

## Code Quality

All fixes maintain:

- **Clean Code**: Single Responsibility Principle
- **Duck Typing**: Compatible across module boundaries
- **Error Handling**: Try-catch with graceful fallbacks
- **User Feedback**: Console logging for debugging

---

## Files Modified Summary

1. **src/ui/asset_manager_window.py**
   - Removed redundant toolbar button
   - Removed unused handler methods
   - Connected `asset_selected` to metadata display

2. **src/ui/widgets/asset_library_widget.py**
   - Added `_get_screenshot_icon_path()` method
   - Updated context menu to use custom icon
   - Fixed screenshot refresh callback to clear cache and reload library

---

**Status**: All issues resolved - Ready for retesting in Maya ✅
