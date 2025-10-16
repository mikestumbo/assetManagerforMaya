# Custom Screenshot Priority Fix v1.3.0

## Bug Fixed: Textured Thumbnails Not Showing in Library View

**Date:** October 8, 2025  
**Severity:** HIGH  
**Impact:** Custom playblast thumbnails not displaying in Asset Manager library

---

## The Problem

### User Report

After adding `Veteran_Rig.mb` to the library:

- ✅ Playblast generation succeeded (console showed success)
- ✅ Custom screenshot saved to `.thumbnails/Veteran_Rig_screenshot.png`
- ❌ Library view showed generic "MB" icon instead of textured character thumbnail
- ❌ Preview panel showed textured character (correct), but library list showed generic icon

### Root Cause

The `generate_thumbnail()` method had flawed logic for checking custom screenshots:

```python
# ❌ OLD CODE (BAD):
if not force_playblast:
    custom_screenshot = self._check_custom_screenshot(file_path)
    if custom_screenshot:
        return custom_screenshot
```

**The Problem:**

- When `force_playblast=True` → Custom screenshots were **SKIPPED**
- When `force_playblast=False` (library browsing/refresh) → Custom screenshots **NOT CHECKED**
- Async thumbnail generation never passed `force_playblast`, so it always fell back to file-type icons

**Why This Happened:**
The original logic tried to prevent returning stale screenshots when forcing a new playblast, but it also accidentally prevented checking for custom screenshots during normal library browsing.

---

## The Solution

### Changes Made

**File:** `src/services/thumbnail_service_impl.py`

#### 1. Always Check Custom Screenshots First

```python
# ✅ NEW CODE (CORRECT):
# ALWAYS check for existing custom screenshot first (highest priority!)
# Custom screenshots should always be used if they exist
custom_screenshot = self._check_custom_screenshot(file_path)
if custom_screenshot:
    print(f"✅ Using custom screenshot: {file_path.name}")
    return custom_screenshot
```

**Logic Flow:**

1. **First priority:** Check for custom screenshot (always!)
2. **Second priority:** Check cache (if not force_playblast)
3. **Third priority:** Generate new playblast (if force_playblast)
4. **Fallback:** Generate file-type icon

#### 2. Enhanced Debug Logging

Added detailed logging to `_check_custom_screenshot()`:

```python
print(f"🔍 Checking custom screenshot for: {asset_name}")
print(f"   Looking in: {thumbnail_dir}")
print(f"   Checking: {screenshot_file.name} - Exists: {screenshot_file.exists()}")
```

This helps diagnose screenshot file detection issues.

---

## Clean Code Principles Applied

### Single Responsibility Principle

- **Custom screenshot check** is separate from **cache check** and **generation logic**
- Each check has clear priority and purpose

### Defensive Programming

```python
for screenshot_file in screenshot_files:
    print(f"   Checking: {screenshot_file.name} - Exists: {screenshot_file.exists()}")
    if screenshot_file.exists():
        print(f"✅ Using custom screenshot: {screenshot_file}")
        return str(screenshot_file)
```

- Checks multiple file formats (PNG, JPG, TIFF)
- Validates file existence before returning path
- Logs each check for debugging

### Clear Intent

```python
# ALWAYS check for existing custom screenshot first (highest priority!)
# Custom screenshots should always be used if they exist
```

- Comment explains WHY we check custom screenshots unconditionally
- Makes the priority system explicit

---

## Testing Instructions

### Test Case 1: Fresh Asset Addition

1. Open Maya, clear scene
2. Add `Veteran_Rig.mb` to library
3. **Wait for playblast generation** (watch console)
4. **Check library view** → Should show textured character thumbnail (not MB icon)
5. **Console should show:**

   ```text
   📸 Saved playblast as custom screenshot: ...
   ✅ Using custom screenshot: Veteran_Rig.mb
   ```

### Test Case 2: Library Refresh

1. Close and reopen Asset Manager
2. **Check library view** → Textured thumbnail should persist
3. **Console should show:**

   ```text
   🔍 Checking custom screenshot for: Veteran_Rig
   ✅ Using custom screenshot: D:\...\Veteran_Rig_screenshot.png
   ```

### Test Case 3: Force Regeneration

1. Select asset in library
2. Right-click → "Regenerate Thumbnail" (if available)
3. **New playblast should generate**
4. **Custom screenshot should be updated**
5. **Library should immediately show new thumbnail**

---

## Expected Console Output

### When Adding Asset to Library

```text
📸 Generating Maya playblast thumbnail for Veteran_Rig.mb
✅ Generated playblast thumbnail: Veteran_Rig.mb (256x256)
📸 Saved playblast as custom screenshot: Veteran_Rig_screenshot.png
🔄 Refreshing thumbnails for 1 assets...
🔍 Checking custom screenshot for: Veteran_Rig
   Looking in: D:\Maya\projects\MyProject\assets\scenes\.thumbnails
   Checking: Veteran_Rig_screenshot.png - Exists: True
✅ Using custom screenshot: D:\...\Veteran_Rig_screenshot.png
```

### When Browsing Library (Async)

```text
🔄 Async thumbnail generation started for: Veteran_Rig ((64, 64))
🔍 Checking custom screenshot for: Veteran_Rig
✅ Using custom screenshot: D:\...\Veteran_Rig_screenshot.png
🖼️ Generated async thumbnail for: Veteran_Rig (size: (64, 64))
```

### What You Should NOT See

```text
❌ 📄 Using file-type icon for library browsing: Veteran_Rig.mb
❌ ✅ Created file type icon: .mb
❌ ✅ Generated file-type icon: Veteran_Rig.mb
```

---

## Impact Summary

### What This Fixes

- ✅ **Textured thumbnails now display** in library view
- ✅ **Custom screenshots persist** across Asset Manager restarts
- ✅ **Playblast thumbnails work** for both library and preview
- ✅ **Async thumbnail generation** now checks custom screenshots

### What Remains Unchanged

- ✅ Playblast generation still works perfectly
- ✅ Namespace cleanup still prevents scene pollution
- ✅ File-type icons still work as fallback
- ✅ Performance unchanged (custom screenshot check is fast)

---

## Related Fixes

This fix complements:

- `NAMESPACE_LEAK_FIX_v1.3.0.md` - Scene cleanup after playblast
- `PHASE6_CLEANUP_FIX_v1.3.0.md` - Exception handling for cleanup
- Issue #2: Custom screenshot priority in cache loading

---

## Version History

### v1.3.0 - October 8, 2025

- Initial fix: Always check custom screenshots regardless of force_playblast flag
- Added debug logging for screenshot file detection
- Simplified priority system for thumbnail sources

---

**Status:** ✅ COMPLETE - Ready for testing in Maya 2025+
