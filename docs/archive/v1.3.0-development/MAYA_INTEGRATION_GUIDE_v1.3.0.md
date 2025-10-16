# Asset Manager v1.3.0 - Maya Integration Guide

## 🎯 Maya Plugin Installation & Usage

### Method 1: Maya Module File (Recommended)

#### Installation - Module File Method

1. Copy the entire `assetManagerforMaya-master` folder to your Maya scripts directory
2. Ensure `assetManager.mod` is in your Maya modules path

#### Usage - Module File Method

```python
# Script Editor:
import assetManager
assetManager.maya_main()
```

#### Module File Configuration (`assetManager.mod`)

```ini
+ MAYAVERSION:2025 assetManager 1.3.0 .
MAYA_PLUG_IN_PATH+:=plug-ins
PYTHONPATH+:=src
PYTHONPATH+:=.
```

**Format Explanation:**

- `+ MAYAVERSION:2025`: Specifies minimum Maya version (2025+)
- `assetManager 1.3.0`: Module name and version
- `.`: Current directory as the module path
- `MAYA_PLUG_IN_PATH+:=plug-ins`: Adds `plug-ins` folder to Maya's plugin search path
- `PYTHONPATH+:=src`: Adds `src` folder to Python path for EMSA architecture
- `PYTHONPATH+:=.`: Adds current directory to Python path

### Method 2: Direct Plugin Integration

#### Installation - Direct Plugin Method

1. Copy `assetManager_maya_plugin_v1.3.0.py` to Maya scripts directory
2. Use the alternative module file: `assetManager_plugin_v1.3.0.mod`

#### Usage - Direct Plugin Method

```python
# Script Editor:
import assetManager_maya_plugin_v1.3.0 as am_plugin
am_plugin.show_asset_manager()
```

### Method 3: Manual Script Loading

#### Usage - Manual Script Method

```python
# Script Editor - Full path method:
import sys
sys.path.append(r"C:\path\to\assetManagerforMaya-master")
import assetManager
assetManager.maya_main()
```

### Method 4: Maya Plugin Registration

#### Install as Maya Plugin

```python
# In Maya Script Editor:
import maya.cmds as cmds
import assetManager_maya_plugin_v1.3.0 as plugin

# Load plugin
try:
    plugin.initializePlugin(None)
    print("✅ Asset Manager v1.3.0 Plugin loaded successfully!")
except Exception as e:
    print(f"❌ Plugin load failed: {e}")

# Show UI
plugin.show_asset_manager()
```

## 🏗️ Architecture Features

### Enterprise Modular Service Architecture (EMSA)

- **Dependency Injection Container** - Professional service management
- **SOLID Principles** - Clean, maintainable code architecture  
- **Service Interfaces** - 5 clean service contracts
- **Design Patterns** - Repository, Strategy, Observer patterns

### Maya Integration Features

- **Maya Main Window Integration** - UI appears as child of Maya
- **Viewport Integration** - Direct Maya viewport interaction
- **Scene Management** - Safe scene operations with state preservation
- **Error Handling** - Graceful Maya environment detection

### UI & Performance

- **Modular UI Components** - Clean separation of concerns
- **Event-Driven Communication** - Loose coupling between components
- **Async Operations** - Non-blocking thumbnail generation
- **Smart Caching** - Optimized resource management

## 🔧 Troubleshooting

### Common Issues

#### PySide6 Not Available

```text
Error: PySide6 not available
Solution: Ensure Maya 2025.3+ or install PySide6
```

#### Module Path Issues

```python
# Check Maya module paths:
import maya.cmds as cmds
print(cmds.moduleInfo(listModules=True))

# Add custom path:
import sys
sys.path.append(r"C:\your\path\to\assetManager")
```

#### Service Resolution Errors

```python
# Test EMSA architecture:
import assetManager_ui_v1.3.0
assetManager_ui_v1.3.0.test_emsa_architecture()
```

### Validation Commands

#### Test Core Architecture

```python
import test_v1.3.0
# Runs comprehensive architecture validation
```

#### Test Maya Integration

```python
import assetManager_maya_plugin_v1.3.0 as plugin
plugin.test_emsa()
```

#### Test Complete System

```python
import test_integration_v1.3.0
# Runs full integration test suite
```

## 📋 Maya Environment Requirements

### Maya Version

- **Maya 2025.3+** (Required for PySide6 support)
- **Python 3.9+** (Included with Maya 2025.3)

### Dependencies

- **PySide6** (Included with Maya 2025.3)
- **shiboken6** (Included with Maya 2025.3)

### Optional Enhancements

- **Windows API** (Enhanced file metadata on Windows)
- **PIL/Pillow** (Enhanced thumbnail generation)

## 🚀 Quick Start

### 1. Verify Installation

```python
# In Maya Script Editor:
import assetManager
print(f"✅ Asset Manager v1.3.0 loaded successfully!")
```

### 2. Launch UI

```python
# Launch main interface:
assetManager.maya_main()
```

### 3. Test Architecture

```python
# Validate EMSA architecture:
import test_v1.3.0
print("🧪 Running architecture tests...")
```

## 📝 Version History

### v1.3.0 - Enterprise Modular Service Architecture

- ✅ Complete EMSA refactoring with SOLID principles
- ✅ Dependency injection container
- ✅ Modular UI architecture  
- ✅ Professional error handling
- ✅ Enhanced Maya integration

### v1.2.2 - Legacy (Preserved)

- Original monolithic architecture
- Advanced search & discovery features
- Preserved in `development/legacy_backup/`

## 🎉 Success

Your Asset Manager v1.3.0 is now ready for professional Maya integration with enterprise-grade architecture!

## Maya Integration Complete ✅
