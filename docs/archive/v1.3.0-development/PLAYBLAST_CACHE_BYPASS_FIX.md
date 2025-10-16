# Critical Fix - Playblast Cache Bypass

## Date: October 6, 2025

## Status: ✅ FIXED - Playblast Now Actually Generates

---

## The Problem

When adding assets to the library with automatic playblast generation enabled, the system was **using old cached file-type icons** instead of generating new playblasts:

```text
📁 Using cached thumbnail: Veteran_Rig.mb  ← Old file-type icon cache
🖼️ Generated large playblast thumbnail    ← LIE! Just returned cache
```

### Root Cause

The `generate_thumbnail()` method was checking the cache BEFORE checking if `force_playblast=True`:

```python
# OLD CODE (BROKEN):
def generate_thumbnail(..., force_playblast=False):
    # Check custom screenshot
    if custom_screenshot:
        return custom_screenshot
    
    # Check cache ← PROBLEM! Returns old file-type icon cache
    if cache_path.exists():
        return str(cache_path)
    
    # Generate playblast ← NEVER REACHED!
    if force_playblast:
        ...
```

**Flow**:

1. Custom screenshot doesn't exist yet ❌
2. Old cache exists (file-type icon) ✅ → **Returns immediately!**
3. Playblast code never executes ❌
4. User sees generic icon ❌

---

## The Fix

Skip cache check when `force_playblast=True` to ensure new playblast is always generated:

```python
# NEW CODE (FIXED):
def generate_thumbnail(..., force_playblast=False):
    # Check custom screenshot
    if custom_screenshot:
        return custom_screenshot
    
    # CRITICAL FIX: Skip cache if force_playblast=True
    if not force_playblast:
        # Only check cache for file-type icons
        if cache_path.exists():
            return str(cache_path)
    
    # Generate playblast ← NOW GETS CALLED!
    if force_playblast:
        print(f"📸 Generating Maya playblast...")
        base_capture = self._ensure_playblast_capture(...)
        # ... generate and save playblast
```

**Flow**:

1. Custom screenshot doesn't exist yet ❌
2. Cache check **skipped** when `force_playblast=True` ✅
3. Playblast code **executes** ✅
4. New playblast generated ✅
5. Saved as custom screenshot ✅
6. User sees actual asset preview! ✅

---

## Expected Console Output

### Before Fix (Broken)

```text
🎬 Generating playblast preview for library: Veteran_Rig.mb
📁 Using cached thumbnail: Veteran_Rig.mb           ← Wrong!
🖼️ Generated large playblast thumbnail             ← Lie!
🗑️ Cleared cache for: Veteran_Rig.mb
📄 Using file-type icon for library browsing        ← Back to generic icon
```

### After Fix (Working)

```text
🎬 Generating playblast preview for library: Veteran_Rig.mb
📸 Generating Maya playblast thumbnail for Veteran_Rig.mb  ← Actually runs!
📸 Starting SAFE Maya playblast for: Veteran_Rig.mb
✅ Imported 350 nodes for playblast
✅ Viewport configured for textured playblast
✅ Maya playblast successful: .../_master.png
📸 Saved playblast as custom screenshot: .../Veteran_Rig_screenshot.png
✅ Generated playblast thumbnail: Veteran_Rig.mb (256x256)
✅ Generated playblast thumbnail: Veteran_Rig.mb (64x64)
🔄 Scheduled thumbnail refresh
✅ Using custom screenshot: Veteran_Rig.mb         ← Success!
```

---

## What Changed

### File: `src/services/thumbnail_service_impl.py`

**Method**: `generate_thumbnail()`

**Change**: Conditional cache check

```python
# OLD: Always check cache
cache_key = self._generate_cache_key(file_path, size)
cache_path = self._get_cache_path(cache_key)
if cache_path.exists():
    return str(cache_path)

# NEW: Only check cache if NOT force_playblast
if not force_playblast:
    cache_key = self._generate_cache_key(file_path, size)
    cache_path = self._get_cache_path(cache_key)
    if cache_path.exists():
        return str(cache_path)
```

**Lines Modified**: ~140-148
**Impact**: HIGH - Core feature now works correctly

---

## Testing Checklist

### Test 1: New Asset Addition

- [ ] Remove `Veteran_Rig` from library (if exists)
- [ ] Clear cache: `C:\Users\[user]\AppData\Local\Temp\assetmanager_thumbnails\`
- [ ] Add `Veteran_Rig.mb` to library
- [ ] Check console for: `📸 Generating Maya playblast thumbnail`
- [ ] Check console for: `📸 Saved playblast as custom screenshot`
- [ ] Verify textured thumbnail appears (not generic .mb icon)

### Test 2: Cached Asset

- [ ] Add asset to library (generates playblast)
- [ ] Close Asset Manager
- [ ] Reopen Asset Manager
- [ ] Asset should show custom screenshot immediately
- [ ] Console should show: `✅ Using custom screenshot`
- [ ] NO playblast regeneration needed

### Test 3: Multiple Assets

- [ ] Add 3-4 different Maya files
- [ ] Each should generate playblast
- [ ] Each should show textured thumbnail
- [ ] Scene should remain clean (check Outliner)

---

## Why This Happened

### The Cache System

The thumbnail service has two types of cached thumbnails:

1. **File-type icons** - Generic `.mb` icon, cached in temp directory
2. **Custom screenshots** - Actual playblast, saved in `.thumbnails/` directory

### The Confusion

When `generate_thumbnail()` was called with `force_playblast=True`, it would:

1. Check for custom screenshot (doesn't exist yet - first time adding asset)
2. Check cache (finds old file-type icon from previous session)
3. Return the cached file-type icon
4. Never execute playblast code!

### The Solution

By skipping the cache check when `force_playblast=True`, we ensure:

1. Check for custom screenshot (doesn't exist yet)
2. **Skip cache check** (intentional)
3. Execute playblast code
4. Generate and save new custom screenshot
5. Return actual textured thumbnail!

---

## Priority & Risk

**Priority**: CRITICAL - Core feature was completely broken
**Risk**: Low - Fix is simple conditional logic
**Testing**: Required - Must verify playblast actually runs now

---

## Files Modified

1. `src/services/thumbnail_service_impl.py` - Added conditional cache check

**Total Changes**: 1 file, ~10 lines modified

---

**Status**: ✅ FIXED - Ready for Testing

**Expected Result**: Assets added to library will now generate actual playblast thumbnails instead of returning cached file-type icons!
