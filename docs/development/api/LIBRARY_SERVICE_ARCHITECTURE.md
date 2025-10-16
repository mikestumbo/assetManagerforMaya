# Library Service Architecture - v1.3.0

**Date:** October 2, 2025  
**Status:** Implemented

## Problem Identified

During v1.3.0 testing, three critical bugs were discovered:

1. **Asset Recognition Bug**: Assets added to library weren't being recognized - couldn't remove them
2. **Thumbnail Cache Bug**: Playblast thumbnails generated but not displayed correctly
3. **Custom Screenshot Bug**: Button not working (dependent on bug #1)

**Root Cause**: When assets were copied to library, the recent assets list still referenced the OLD source paths instead of the NEW library paths. This caused file stat errors and broke asset recognition.

## Solution: Separation of Concerns

### Architecture Refactor

Created dedicated `library_service_impl.py` separate from `standalone_services.py`:

```text
Before:
- standalone_services.py: Mixed repository operations + recent assets tracking
- asset_manager_window.py: File copying logic (violating SRP)
- Problem: Old paths in recent assets after copy

After:
- library_service_impl.py: Library-specific operations (add/remove assets)
- standalone_services.py: Generic repository operations (find/search)
- asset_manager_window.py: Uses library service via DI
- Solution: Atomic operations ensure correct paths
```

### Key Components

#### 1. `src/core/interfaces/library_service.py`

**Purpose**: Interface defining library operations contract

**Methods**:

- `add_asset_to_library(source_path, project_path)` - Copy + update repository
- `remove_asset_from_library(asset)` - Delete + update repository  
- `get_library_path_for_asset(source_path, project_path)` - Calculate target path

#### 2. `src/services/library_service_impl.py`

**Purpose**: Implementation of library operations with proper coordination

**Key Features**:

- **Atomic Operation**: Copy file + create new Asset object with library path in single operation
- **Path Resolution**: Handles file type routing and conflict resolution
- **Repository Update**: Updates recent assets with NEW library path (not old source path)
- **Error Handling**: Comprehensive logging and error recovery

**Critical Flow**:

```python
def add_asset_to_library(source_path, project_path):
    1. Calculate target path based on file type
    2. Resolve any filename conflicts
    3. Copy file to library
    4. Create NEW Asset object with LIBRARY path
    5. Update repository.update_access_time(new_asset)  # Uses NEW path!
    6. Return (success, new_path)
```

#### 3. `src/core/container.py`

**Updated**: Registers library service in DI container

**Registration**:

```python
from ..services.library_service_impl import LibraryServiceImpl
library_service = LibraryServiceImpl(asset_repository)
container.register_instance(ILibraryService, library_service)
```

#### 4. `src/ui/asset_manager_window.py`

**Updated**: Uses library service instead of manual file operations

**Changes**:

```python
# Injected in __init__
self._library_service = self._container.resolve(ILibraryService)

# Simplified _copy_asset_to_library
def _copy_asset_to_library(source_path: Path) -> bool:
    result = self._library_service.add_asset_to_library(source_path, project_path)
    if result[0]:  # Success
        QTimer.singleShot(100, lambda: self._on_refresh_library())
        return True
    return False
```

## Benefits

### 1. **Fixes Asset Recognition Bug** ✅

- Recent assets list now has correct library paths
- File stat operations work correctly
- Asset removal operations function properly

### 2. **SOLID Principles** ✅

- **Single Responsibility**: Library operations isolated
- **Open/Closed**: Easy to extend library features
- **Liskov Substitution**: Interface-based design
- **Interface Segregation**: Specific library interface
- **Dependency Inversion**: DI via container

### 3. **Clean Architecture** ✅

- UI layer uses services through interfaces
- Business logic separated from UI
- Easy to test in isolation
- Clear separation of concerns

### 4. **Maintainability** ✅

- Library operations centralized in one service
- Easy to add features (e.g., undo, batch operations)
- Clear responsibility boundaries
- Comprehensive logging

## Files Modified

1. **Created**:
   - `src/core/interfaces/library_service.py` - Interface definition
   - `src/services/library_service_impl.py` - Implementation
   - `docs/LIBRARY_SERVICE_ARCHITECTURE.md` - This document

2. **Updated**:
   - `src/core/container.py` - Register library service
   - `src/core/interfaces/__init__.py` - Export library service interface
   - `src/ui/asset_manager_window.py` - Use library service

## Testing Plan

1. **Add Asset to Library**:
   - Should copy file to correct subdirectory
   - Should update recent assets with library path
   - Should handle filename conflicts

2. **Asset Recognition**:
   - Added asset should appear in library
   - Should be selectable
   - Should be removable
   - File stat should work

3. **Remove Asset**:
   - Should delete file from library
   - Should update repository
   - Should remove from recent assets

4. **Thumbnail Generation**:
   - Library browsing should show file icons
   - Import should trigger playblast generation
   - Playblast should display correctly after import

## Next Steps

1. Test in Maya 2025 with Veteran_Rig.mb
2. Verify asset recognition works
3. Verify thumbnail cache displays playblast
4. Verify custom screenshot button works
5. If all tests pass → Release v1.3.0

## Timeline

- **Implementation**: October 2, 2025
- **Testing**: October 2, 2025 (today)
- **Release Deadline**: October 3, 2025 evening (tomorrow)
