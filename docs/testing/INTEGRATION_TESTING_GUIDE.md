# Asset Manager v1.3.0 - Final Integration Testing Guide

## 🧪 Maya Integration Testing Protocol

### Pre-Testing Validation Checklist

#### 1. File Structure Validation

- [x] Main plugin files in correct locations
- [x] Source directory (`src/`) properly organized
- [x] MEL installation script ready
- [x] Icon files accessible
- [x] Security compliance validated

#### 2. Installation Testing Steps

##### Step 1: Clean Maya Environment

```mel
// Clear any existing Asset Manager installations
// Remove old shelf buttons and plugins
unloadPlugin "assetManager";
deleteUI -window "assetManagerUI";
```

##### Step 2: Install via MEL Script

```mel
// Method 1: Drag & Drop Installation
// Drag DRAG&DROP.mel into Maya viewport
// Should see installation messages in Script Editor

// Method 2: Manual MEL Execution
source "DRAG&DROP.mel";
installAssetManager();
```

##### Step 3: Plugin Loading Test

```mel
// Load plugin through Plugin Manager
loadPlugin "assetManager";

// Verify plugin is loaded
pluginInfo -query -loaded "assetManager";
```

##### Step 4: UI Functionality Test

```python
# Test Python integration
import maya_plugin
maya_plugin.show_asset_manager()
```

#### 3. Security Validation Tests

##### Test A: No Security Warnings

- Plugin loads without Maya security warnings
- No unauthorized path modifications
- Clean plugin registration

##### Test B: Safe Path Management

- sys.path restored after operations
- No permanent path pollution
- Temporary modifications only

##### Test C: Error Handling

- Graceful failure modes
- Proper error messages
- No Maya crashes

#### 4. Functionality Validation

##### Core Features to Test

- [ ] Plugin initialization successful
- [ ] UI window opens without errors
- [ ] Asset library loads correctly
- [ ] Collections system functional
- [ ] Import/Export operations work
- [ ] Screenshot capture functional
- [ ] Settings persistence works

##### EMSA Architecture Test

- [ ] Service container initializes
- [ ] Dependency injection works
- [ ] Event publishing functional
- [ ] Legacy fallback available

#### 5. Performance & Stability

##### Memory Management

- [ ] No memory leaks during operation
- [ ] Proper resource cleanup on close
- [ ] Stable during extended use

##### Maya Integration

- [ ] Shelf button works correctly
- [ ] Menu integration functional
- [ ] No conflicts with other plugins
- [ ] Scene operations don't interfere

## 🔍 Expected Test Results

### Success Indicators

✅ Plugin loads without security warnings
✅ All UI components render correctly  
✅ Asset operations complete successfully
✅ No Python errors in Script Editor
✅ Clean plugin unload/reload cycles
✅ Stable performance during use

### Failure Indicators

❌ Security validation errors
❌ Import/path related errors
❌ UI rendering failures
❌ Maya crashes or freezes
❌ Memory leaks or resource issues

## 🚨 Troubleshooting Guide

### Common Issues & Solutions

#### Issue: Plugin Load Failure

- Check Maya Plugin Manager for error details
- Verify all dependencies are available
- Confirm Maya version compatibility

#### Issue: Import Errors

- Validate src/ directory structure
- Check Python path configuration
- Ensure all required modules present

#### Issue: UI Problems

- Check PySide6 availability (Maya 2025+ requirement)
- Verify Maya parent window integration
- Test fallback UI modes

#### Issue: Path Related Errors

- Confirm plugin directory structure
- Check file permissions
- Validate installation paths

## 📋 Test Report Template

```text
Asset Manager v1.3.0 Integration Test Report
Date: [Test Date]
Maya Version: [Version]
Platform: [Windows/Mac/Linux]

INSTALLATION:
[ ] MEL script execution: PASS/FAIL
[ ] Plugin registration: PASS/FAIL
[ ] File deployment: PASS/FAIL

SECURITY:
[ ] No security warnings: PASS/FAIL
[ ] Safe path management: PASS/FAIL
[ ] Clean initialization: PASS/FAIL

FUNCTIONALITY:
[ ] UI launch: PASS/FAIL
[ ] Asset operations: PASS/FAIL
[ ] Settings persistence: PASS/FAIL

STABILITY:
[ ] Extended use: PASS/FAIL
[ ] Clean shutdown: PASS/FAIL
[ ] Memory management: PASS/FAIL

OVERALL STATUS: PASS/FAIL
NOTES: [Additional observations]
```

---
*Testing Protocol - September 16, 2025*
*Maya 2025+ Compatibility Validated*
