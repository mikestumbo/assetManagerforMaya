# Asset Recognition Debugging - v1.3.0

**Date:** October 2, 2025  
**Status:** Debugging in Progress

## Problem Report

User reports that after adding asset to library:

1. ✅ Asset appears in library list
2. ❌ Asset not recognized when selected
3. ❌ Cannot remove from library
4. ❌ Cannot double-click to import into Maya
5. ❌ Cannot drag-and-drop into Maya

## Investigation

### Flow Analysis

**Expected Flow:**

```text
1. User adds asset → Library service copies file
2. Library service creates Asset object with NEW path
3. Library service calls update_access_time(new_asset)
4. Refresh library → Repository.find_all() scans directory
5. Assets populated in QListWidget with Qt.UserRole data
6. User selects → Get Asset from UserRole
7. Validate asset path → Import
```

**Potential Issues:**

- Asset objects might have incorrect file paths
- File validation failing on `file_path.exists()`
- Selection not retrieving Asset objects correctly
- Recent assets vs All Assets tab mismatch

### Code Points to Check

**1. Library Service (`library_service_impl.py`):**

```python
new_asset = Asset(
    id=str(target_path),      # Should be library path
    file_path=target_path,    # Should be library path
    ...
)
```

**2. Repository Find All (`standalone_services.py`):**

```python
asset = Asset(
    id=str(file_path),        # Scanned from filesystem
    file_path=file_path,      # From directory.rglob()
    ...
)
```

**3. Asset Validation (`asset_manager_window.py`):**

```python
if not file_path.exists():
    print(f"❌ Asset validation failed: File does not exist: {file_path}")
    return False
```

## Debugging Added

### 1. Library Service - Enhanced Logging

```python
print(f"📌 Full path: {target_path}")
print(f"📌 Asset ID: {new_asset.id}")
print(f"📌 File exists: {target_path.exists()}")
```

### 2. Asset Population - Path Verification

```python
print(f"🔄 Adding asset [{i+1}]: {asset.display_name}")
print(f"   ID: {asset.id}")
print(f"   Path: {asset.file_path}")
print(f"   Exists: {file_exists}")
```

## Testing Instructions

1. **Fresh Maya Scene**
2. **Open Asset Manager**
3. **Create/Open Project**
4. **Add Asset to Library** - Watch console output:

   ```text
   ✅ Asset added to library: <name>
   📌 Library path: assets/scenes/<name>
   📌 Full path: D:/Maya/projects/MyProject/assets/scenes/<name>
   📌 Asset ID: D:/Maya/projects/MyProject/assets/scenes/<name>
   📌 File exists: True/False  ← CRITICAL CHECK
   ```

5. **Library Refresh** - Watch console output:

   ```text
   🔄 Populating asset list with X assets
   🔄 Adding asset [1]: <name>
      ID: <path>
      Path: <path>
      Exists: True/False  ← CRITICAL CHECK
   ```

6. **Select Asset** - Watch for:

   ```text
   (Selection should emit signal)
   ```

7. **Try to Import** - Watch for:

```text
   (Import should trigger validation)
   ```

   ✅ Asset file path validated: `name`
   OR
   ❌ Asset validation failed: File does not exist: &lt;path&gt;

   ```text

## Expected Findings

### Scenario A: Path Mismatch

- Library service creates asset with: `D:/Maya/projects/MyProject/assets/scenes/Asset.mb`
- But find_all() creates asset with different path
- Validation fails because paths don't match filesystem

### Scenario B: File Not Found

- Asset ID/path is correct
- But file doesn't actually exist at that location
- Indicates copy operation failed

### Scenario C: Selection Issue

- Assets in list have correct paths
- But selection not retrieving Asset objects from UserRole
- Problem in `_on_selection_changed()`

### Scenario D: Tab Confusion

- Asset added to recent assets only
- User looking at "All Assets" tab
- Find_all() not finding the file in directory scan

## Next Steps

1. Run test with enhanced debugging
2. Analyze console output to identify exact failure point
3. Implement targeted fix based on findings
4. Retest to confirm fix

## Hypothesis

**Most Likely**: The library refresh (`find_all()`) is scanning the directory but not finding the newly copied file, possibly due to:

- Timing issue (refresh happens before file is fully written)
- Directory path mismatch
- File permissions issue
- Filesystem cache not updated

**Solution**: May need to:

- Increase delay before refresh
- Force filesystem sync/flush
- Directly add the asset to the list without full rescan
- Clear repository cache before rescan
