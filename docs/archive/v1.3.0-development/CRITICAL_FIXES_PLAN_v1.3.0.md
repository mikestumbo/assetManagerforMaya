# Asset Manager v1.3.0 - Critical Fixes Implementation Plan

## Issues Identified

### Issue #1: Custom Screenshots Not Displaying

**Symptom**: Screenshot saved but library still shows file-type icon
**Root Cause**: After screenshot capture, `_capture_screenshot()` callback clears cache and calls `refresh_thumbnails_for_assets()`, but logs show a FULL library refresh is happening afterwards (see "Selection changed event fired!" → "Populating asset list"). This full refresh recreates all list items BEFORE the async thumbnail generation completes.

**Fix**: Prevent full library refresh after screenshot capture. The targeted `refresh_thumbnails_for_assets()` should be sufficient.

### Issue #2: Metadata Not Persisting  

**Symptom**: Metadata extracted (207,001 polys, 15 materials) but not shown in Asset Information panel
**Root Cause**: `_extract_full_metadata_for_imported_asset()` extracts metadata but has `# TODO: Update asset metadata in database/cache` - metadata is just printed and discarded.

**Fix**: Implement metadata persistence:

1. Update Asset object with extracted metadata
2. Save to repository/database  
3. Update UI to display persisted metadata

### Issue #3: No Automatic Thumbnails

**Symptom**: Library shows generic `.mb` file-type icons instead of actual asset previews
**Root Cause**: Two-tier system only generates file-type icons for library browsing. Playblast thumbnails only generated when `force_playblast=True` (explicit import).

**Fix**: Auto-generate playblast thumbnails when assets are imported to Maya scene (which already happens during import flow). The system DOES call `_generate_thumbnail_for_imported_asset()` but thumbnails aren't persisting in library view.

## Solution Architecture

### Fix #1: Screenshot Display

**Location**: `src/ui/widgets/asset_library_widget.py`
**Change**: Ensure `refresh_thumbnails_for_assets()` doesn't trigger selection changes that cause full refresh

### Fix #2: Metadata Persistence  

**Location**: `src/ui/asset_manager_window.py`  
**Change**: In `_extract_full_metadata_for_imported_asset()`:

1. Get asset from repository  
2. Update asset's metadata dict
3. Call `repository.update_asset_metadata(asset_id, metadata)`
4. Trigger UI refresh to show new metadata

### Fix #3: Automatic Thumbnails

**Location**: Multiple files
**Analysis**: System ALREADY generates playblast thumbnails on import (`_generate_thumbnail_for_imported_asset()` is called). The issue is the thumbnails aren't showing because:

- Thumbnails are cached in temp directory
- Custom screenshots take precedence  
- Need to ensure playblast thumbnails are treated as "custom screenshots"

**Change**: When playblast thumbnail is generated, save it as a custom screenshot in `.thumbnails/` directory so it persists and takes precedence.

## Implementation Priority

1. **Fix #3 First** - Make playblast thumbnails save as custom screenshots
2. **Fix #1 Second** - Ensure screenshot refresh works properly
3. **Fix #2 Third** - Persist metadata after extraction

## Files to Modify

1. `src/ui/asset_manager_window.py` - Metadata persistence + playblast saves
2. `src/services/thumbnail_service_impl.py` - Playblast saves as custom screenshot
3. `src/services/asset_repository_standalone.py` - Add `update_asset_metadata()` method
4. `src/ui/widgets/asset_info_panel.py` - Display extended metadata
