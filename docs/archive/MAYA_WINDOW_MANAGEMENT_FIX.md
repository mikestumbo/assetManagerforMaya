# Maya Window Management Fix - Singleton Pattern & Z-Order

## Issue Resolution Summary

**Date:** September 8, 2025  
**Issue:** Asset Manager disappears behind Maya windows and shelf button creates duplicates  
**Status:** ✅ **RESOLVED**

## Root Cause Analysis

### Problems Identified

1. **Z-Order Issue**: Asset Manager window didn't stay above Maya's interface
2. **No Parent Relationship**: Window not properly connected to Maya's main window
3. **No Singleton Pattern**: Each shelf button click created new window instance
4. **Hidden Window Confusion**: Users thought plugin was crashing when window went behind Maya

### Technical Root Causes

- **Missing Maya Parent**: Window created with `parent=None` instead of Maya's main window
- **No Window Management**: No singleton pattern to prevent duplicates
- **No Window Flags**: Default Qt flags didn't maintain proper Z-order with Maya
- **No Front-Bringing Logic**: No mechanism to raise existing window to front

## Clean Code Solution Applied

### 1. Singleton Pattern Implementation

**Principle Applied**: **Single Instance** - One Asset Manager window at a time

#### Before (Problem)

```python
def show_asset_manager():
    # Always creates new window - DUPLICATES!
    window = create_asset_manager()
    window.show()
    return window
```

#### After (Fixed)

```python
# Global singleton reference
_asset_manager_window = None

def show_asset_manager():
    global _asset_manager_window
    
    # Check if window already exists
    if _asset_manager_window is not None:
        try:
            # Bring existing window to front
            if _asset_manager_window.isVisible():
                _asset_manager_window.raise_()
                _asset_manager_window.activateWindow()
                _asset_manager_window.showNormal()
                return _asset_manager_window
        except RuntimeError:
            # Window was deleted - clear reference
            _asset_manager_window = None
    
    # Create new window only if needed
    _asset_manager_window = create_asset_manager()
    # ...
```

### 2. Maya Parent Window Integration

**Principle Applied**: **Proper Parent-Child Relationship** - Connect to Maya's window hierarchy

#### Maya Main Window Detection

```python
def get_maya_main_window():
    """Get Maya's main window as QWidget parent"""
    try:
        import maya.OpenMayaUI as omui
        
        if PYSIDE_VERSION == "PySide6":
            import shiboken6
            maya_main_window_ptr = omui.MQtUtil.mainWindow()
            return shiboken6.wrapInstance(int(maya_main_window_ptr), QWidget)
        # PySide2 fallback...
    except Exception as e:
        print(f"⚠️ Could not get Maya main window: {e}")
    return None
```

#### Window Creation with Maya Parent

```python
def create_asset_manager():
    # Get Maya's main window as parent
    maya_parent = get_maya_main_window()
    
    # Create window with proper parent relationship
    window = AssetManagerWindow(parent=maya_parent)
    
    if maya_parent:
        print("✅ Asset Manager window parented to Maya main window")
    return window
```

### 3. Enhanced Window Configuration

**Principle Applied**: **Proper Window Flags** - Configure Qt window behavior for Maya

#### Window Setup Enhancement

```python
def _setup_window(self) -> None:
    """Setup main window properties with Maya integration"""
    self.setWindowTitle("Asset Manager")
    self.setMinimumSize(1000, 600)
    self.resize(1200, 800)
    
    # Configure window flags for Maya integration
    if self.parent() is not None:
        # Has Maya parent - set flags to stay above Maya
        self.setWindowFlags(
            Qt.WindowType.Window |  # Independent window
            Qt.WindowType.WindowCloseButtonHint |  # Close button
            Qt.WindowType.WindowMinimizeButtonHint |  # Minimize button  
            Qt.WindowType.WindowMaximizeButtonHint  # Maximize button
        )
        print("✅ Asset Manager window configured for Maya integration")
```

### 4. Window Activation Utilities

**Principle Applied**: **User Experience** - Easy window management

#### Bring-to-Front Method

```python
def bring_to_front(self) -> None:
    """Bring Asset Manager window to front - Maya integration utility"""
    try:
        if not self.isVisible():
            self.show()
        
        # Bring window to front and activate
        self.raise_()  # Bring to front of window stack
        self.activateWindow()  # Give keyboard focus
        self.showNormal()  # Restore if minimized
        
        print("✅ Asset Manager brought to front")
    except Exception as e:
        print(f"⚠️ Error bringing window to front: {e}")
```

## Implementation Details

### Maya Integration Architecture

```text
Maya Main Window (Parent)
    └── Asset Manager Window (Child)
        ├── Proper Z-order relationship
        ├── Singleton instance management
        ├── Window state persistence
        └── Focus management
```

### Singleton Lifecycle Management

1. **First Launch**: Creates new window with Maya parent
2. **Subsequent Clicks**: Brings existing window to front
3. **Window Closed**: Clears singleton reference for next launch
4. **Maya Restart**: Fresh singleton state

### Window Flag Configuration

- **Qt.WindowType.Window**: Independent window (not dialog)
- **WindowCloseButtonHint**: Standard close button
- **WindowMinimizeButtonHint**: Can be minimized
- **WindowMaximizeButtonHint**: Can be maximized
- **No AlwaysOnTop**: Respects Maya's window stacking

## User Experience Transformation

### Before Fix

- ❌ Asset Manager disappears behind Maya windows
- ❌ Shelf button creates multiple duplicate windows
- ❌ Users think plugin crashed when window hidden
- ❌ No way to bring window back without shelf button
- ❌ Window not properly integrated with Maya

### After Fix

- ✅ Asset Manager maintains proper Z-order with Maya
- ✅ Shelf button brings existing window to front (no duplicates)
- ✅ Window stays accessible and visible
- ✅ Proper parent-child relationship with Maya
- ✅ Professional window management behavior

## Technical Benefits

### 1. Memory Management

- **Before**: Multiple window instances consuming memory
- **After**: Single window instance with proper lifecycle

### 2. Resource Efficiency

- **Before**: Multiple UI threads and event handlers
- **After**: Single UI instance with shared resources

### 3. State Consistency

- **Before**: Multiple windows with potentially different states
- **After**: Single window with consistent application state

### 4. Maya Integration

- **Before**: Independent window fighting with Maya's window manager
- **After**: Proper child window respecting Maya's window hierarchy

## Debug Information

### Console Output Examples

```text
✅ Asset Manager window parented to Maya main window
✅ Asset Manager window configured for Maya integration
🚀 Asset Manager EMSA started successfully
✅ Asset Manager brought to front                    # Subsequent clicks
✅ Asset Manager singleton reference cleared         # When closed
```

### Error Handling

```text
⚠️ Could not get Maya main window: [error details]
ℹ️ Asset Manager running without Maya parent (standalone mode)
ℹ️ Previous Asset Manager window was closed, creating new one
```

## Integration with Existing Features

### MEL Shelf Button

- **No Changes Required**: Existing button code works with new singleton
- **Command**: `assetManager.maya_main()` → `show_asset_manager()` → Singleton logic
- **Behavior**: First click creates, subsequent clicks bring to front

### Window State Persistence

- **Compatible**: Singleton works with existing window state saving
- **Enhanced**: Window size/position maintained across singleton lifecycle
- **Seamless**: No conflicts with existing persistence system

## Testing Validation

### Test Scenarios

1. **First Launch**: Click shelf button → Window appears with Maya parent ✓
2. **Bring to Front**: Click button again → Existing window comes forward ✓
3. **Hidden Window**: Asset Manager behind Maya → Button brings it forward ✓
4. **Minimized Window**: Minimized Asset Manager → Button restores and activates ✓
5. **Closed Window**: Close Asset Manager → Next button click creates new instance ✓
6. **Maya Restart**: Restart Maya → Clean singleton state ✓

### Expected Behavior

- **One Instance**: Only one Asset Manager window ever exists
- **Always Accessible**: Window can always be brought to front via shelf button
- **Proper Z-Order**: Window maintains appropriate stacking with Maya
- **Clean Lifecycle**: Window creation/destruction properly managed

## Clean Code Principles Applied

### 1. Single Responsibility

- **Window Management**: Dedicated methods for window lifecycle
- **Maya Integration**: Separate functions for Maya-specific setup
- **Singleton Logic**: Clear separation of instance management

### 2. Dependency Injection

- **Maya Parent**: Injected during window creation
- **Clean Interface**: Window doesn't need to know about Maya details
- **Testable**: Can work with or without Maya parent

### 3. Error Handling

- **Graceful Degradation**: Works without Maya parent (standalone mode)
- **Resource Cleanup**: Proper singleton reference management
- **User Feedback**: Clear console messages for debugging

### 4. User Experience Priority

- **No Surprises**: Intuitive window behavior matching Maya standards
- **Always Available**: Window never "disappears" permanently
- **Professional**: Behavior matches commercial Maya plugins

This fix transforms the Asset Manager from a "sometimes disappearing tool" to a professionally integrated Maya plugin with proper window management that users can rely on. The singleton pattern ensures no duplicate windows while the Maya parent relationship maintains proper Z-order behavior.
