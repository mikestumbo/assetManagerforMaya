# Quick Maya Commands - Asset Manager v1.3.0 Testing

## 🚀 Install Asset Manager

### ✅ Standard Installation: DRAG&DROP.mel

**This is the standard installation method - always use this!**

```mel
// Copy and paste into Maya Script Editor (MEL tab):
source "C:/Users/ChEeP/OneDrive/Documents/Mike Stumbo plugins/assetManagerforMaya-master/DRAG&DROP.mel";
```

**What this does:**

- Installs to Maya scripts directory
- Creates persistent installation
- Adds shelf button
- Works every time you open Maya

### 🔧 Development Testing Only: Python Direct Load

**Note**: Only use this for development testing when making code changes. For normal use, always use DRAG&DROP.mel above.

```python
# Copy and paste into Maya Script Editor (Python tab):
import sys
sys.path.insert(0, r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master')

import assetManager
assetManager.show_asset_manager()
```

---

## ✅ Verify Services Registered

```python
# Check which services are available:
from src.core.container import get_container

container = get_container()
print("\n=== Asset Manager v1.3.0 Services ===")
print(f"Available services: {container.list_services()}")
```

---

## 🎨 Test ngSkinTools2 Integration

```python
# Check ngSkinTools2 availability:
from src.services.ngskintools_service_impl import get_ngskintools_service

service = get_ngskintools_service()
print("\n=== ngSkinTools2 Service ===")
print(f"Available: {service.is_available()}")
print(f"Plugin Available: {service._plugin_available}")
print(f"API Available: {service._api_available}")

if service.is_available():
    version = service.get_plugin_version()
    print(f"Version: {version}")
    
    # Get service info
    info = service.get_info()
    print(f"\nService Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
```

---

## 🎬 Test RenderMan Integration

```python
# Check RenderMan availability:
from src.services.renderman_service_impl import get_renderman_service

service = get_renderman_service()
print("\n=== RenderMan Service ===")
print(f"Available: {service.is_available()}")

if service.is_available():
    version = service.get_plugin_version()
    print(f"Version: {version}")
    
    # Get service info
    info = service.get_info()
    print(f"\nService Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
```

---

## 📦 Test USD Integration

```python
# Check USD availability:
from src.services.usd_service_impl import get_usd_service

service = get_usd_service()
print("\n=== USD Service ===")
print(f"Available: {service.is_available()}")

if service.is_available():
    version = service.get_usd_version()
    print(f"Version: {version}")
    
    # Get service info
    info = service.get_info()
    print(f"\nService Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
```

---

## 📊 Complete Service Report

```python
# Get comprehensive service report:
from src.services.renderman_service_impl import get_renderman_service
from src.services.usd_service_impl import get_usd_service
from src.services.ngskintools_service_impl import get_ngskintools_service

print("\n" + "="*60)
print("ASSET MANAGER v1.3.0 - API INTEGRATION REPORT")
print("="*60)

# RenderMan
renderman = get_renderman_service()
print(f"\n🎬 RenderMan: {'✅ AVAILABLE' if renderman.is_available() else '❌ NOT AVAILABLE'}")
if renderman.is_available():
    print(f"   Version: {renderman.get_plugin_version()}")

# USD
usd = get_usd_service()
print(f"\n📦 USD: {'✅ AVAILABLE' if usd.is_available() else '❌ NOT AVAILABLE'}")
if usd.is_available():
    print(f"   Version: {usd.get_usd_version()}")

# ngSkinTools2
ngskin = get_ngskintools_service()
print(f"\n🎨 ngSkinTools2: {'✅ AVAILABLE' if ngskin.is_available() else '❌ NOT AVAILABLE'}")
if ngskin.is_available():
    print(f"   Version: {ngskin.get_plugin_version()}")

print("\n" + "="*60)
```

---

## 🔍 Test ngSkinTools2 with Veteran_Rig

```python
# After importing your Veteran_Rig.mb:
from src.services.ngskintools_service_impl import get_ngskintools_service

service = get_ngskintools_service()

if service.is_available():
    # Detect nodes in scene
    nodes = service.detect_ngskintools_nodes()
    print("\n=== ngSkinTools2 Scene Analysis ===")
    print(f"Total nodes: {nodes['total_nodes']}")
    print(f"Data nodes: {len(nodes['data_nodes'])}")
    print(f"Skin clusters: {len(nodes['skin_clusters'])}")
    print(f"Total layers: {nodes['layer_count']}")
    
    # Get scene summary
    summary = service.get_scene_summary()
    print(f"\nScene Summary:")
    print(f"Skinned meshes: {len(summary['skinned_meshes'])}")
    print(f"Plugin version: {summary['plugin_version']}")
    print(f"API available: {summary['api_available']}")
    
    # Extract metadata from specific mesh
    # Replace 'YourMeshName' with actual mesh name from your rig
    # metadata = service.extract_ngskintools_metadata('YourMeshName')
    # print(f"\nMesh Metadata:")
    # print(f"Layer count: {metadata['layer_count']}")
    # print(f"Layer names: {metadata['layer_names']}")
    # print(f"Influence count: {metadata['influence_count']}")
```

---

## 🎯 Test About Dialog

```python
# Open About dialog programmatically (or use Help → About in UI):
from PySide6.QtWidgets import QMessageBox, QApplication

# Note: Normally you'd click Help → About in the Asset Manager UI
# This is just to verify the HTML rendering works:

about_text = """
<h2>Asset Manager v1.3.0</h2>
<p><b>Enterprise Modular Service Architecture (EMSA)</b></p>
<p>Test dialog - click Help → About in Asset Manager for full version</p>
"""

# Only run if you want to test the dialog separately
# QMessageBox.about(None, "Test", about_text)

print("✅ To test About dialog: Click Help → About in Asset Manager window")
```

---

## 🧪 Verify All Tests Still Pass

```python
# From Windows Terminal (PowerShell) in the plugin directory:
# python -m pytest tests/ -v --tb=line

# Expected result: 79 passed
```

---

## 📝 Check Plugin Installation

```python
# Verify ngSkinTools2 plugin:
import maya.cmds as cmds

plugins_to_check = ['ngSkinTools2', 'RenderMan_for_Maya.py', 'mayaUsdPlugin']

print("\n=== Maya Plugin Status ===")
for plugin in plugins_to_check:
    try:
        loaded = cmds.pluginInfo(plugin, query=True, loaded=True)
        print(f"✅ {plugin}: {'LOADED' if loaded else 'NOT LOADED'}")
    except:
        print(f"❌ {plugin}: NOT FOUND")
```

---

## 🔄 Reload Asset Manager (if making changes)

```python
# If you need to reload after code changes:
import sys

# Remove from sys.modules
modules_to_remove = [m for m in sys.modules if m.startswith('assetManager') or m.startswith('src')]
for module in modules_to_remove:
    del sys.modules[module]

# Clear path
if r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master' in sys.path:
    sys.path.remove(r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master')

# Reload
sys.path.insert(0, r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master')
import assetManager
assetManager.show_asset_manager()
```

---

## 🎉 Success Indicators

After running Asset Manager, you should see in Script Editor:

```text
# Asset Manager initializing...
# ✅ EMSA Container initialized
# Checking API services...
# [Service registration messages for RenderMan, USD, ngSkinTools2]
# ✅ Asset Manager ready!
```

**No Python errors or tracebacks = SUCCESS!** ✅

---

## 📞 Quick Reference

| Test | Command | Expected Result |
|------|---------|----------------|
| **Load** | `import assetManager; assetManager.show_asset_manager()` | Window opens, no errors |
| **About** | Click Help → About | Dialog shows with trademarks |
| **Services** | Check Script Editor output | Services register or report unavailable |
| **ngSkin** | Import Veteran_Rig.mb | Detects layer data |

---

**Copy any section above directly into Maya Script Editor to test!** 🚀

*Asset Manager v1.3.0 - Ready for Maya testing!*
