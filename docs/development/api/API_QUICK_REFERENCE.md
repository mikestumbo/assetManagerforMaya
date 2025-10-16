# Asset Manager v1.3.0 - Quick API Reference

## 🔗 Official API Documentation Links

### Pixar RenderMan (v26.3)

```text
Main Documentation: https://renderman.pixar.com/resources/rman26/index.html
RenderMan for Maya:  https://renderman.pixar.com/maya
Python API:          https://renderman.pixar.com/resources/rman26/python_api.html
```

### Disney USD (Universal Scene Description)

```text
Main Documentation: https://openusd.org/release/api/index.html
Python API:         https://openusd.org/release/api/usd_page_front.html
Core Classes:       https://openusd.org/release/api/usd_page_object_model.html
```

### ngSkinTools2 (v2.4.0)

```text
Main Documentation: https://www.ngskintools.com/documentation/v2/api/
Layers API:         https://www.ngskintools.com/documentation/v2/api/layers/
Target Info:        https://www.ngskintools.com/documentation/v2/api/target_info/
```

---

## 🚀 Quick Usage Examples

### RenderMan Service

```python
from src.services.renderman_service_impl import get_renderman_service

service = get_renderman_service()

# Check availability
if service.is_available():
    version = service.get_plugin_version()
    print(f"RenderMan {version} detected")
    
    # Detect content
    nodes = service.detect_renderman_nodes()
    print(f"Found {nodes['total_nodes']} RenderMan nodes")
```

### USD Service

```python
from src.services.usd_service_impl import get_usd_service

service = get_usd_service()

# Check availability
if service.is_available():
    version = service.get_usd_version()
    print(f"USD {version} available")
    
    # Inspect USD file
    info = service.inspect_usd_file('/path/to/asset.usd')
    print(f"Prims: {info['prim_count']}")
```

### ngSkinTools2 Service

```python
from src.services.ngskintools_service_impl import get_ngskintools_service

service = get_ngskintools_service()

# Check availability
if service.is_available():
    version = service.get_plugin_version()
    print(f"ngSkinTools2 {version} detected")
    
    # Extract metadata
    metadata = service.extract_ngskintools_metadata('mesh')
    print(f"Layers: {metadata['layer_count']}")
```

---

## 📋 Service Methods Comparison

| Method | RenderMan | USD | ngSkinTools2 |
|--------|-----------|-----|--------------|
| `is_available()` | ✅ | ✅ | ✅ |
| `get_plugin_version()` | ✅ | `get_usd_version()` | ✅ |
| `detect_*_nodes()` | ✅ | N/A | ✅ |
| `get_scene_summary()` | ✅ | N/A | ✅ |
| `extract_metadata()` | ✅ | N/A | ✅ |
| `cleanup_*_nodes()` | ✅ | N/A | ✅ |
| `inspect_*_file()` | N/A | ✅ | N/A |
| `import_*()` | N/A | ✅ | N/A |
| `get_info()` | ✅ | ✅ | ✅ |

---

## 📊 Test Status

```text
✅ All 79 Tests Passing

Core Tests:          55 ✅
RenderMan Tests:      6 ✅
USD Tests:            8 ✅
ngSkinTools2 Tests:  10 ✅

Total Pass Rate: 100%
```

---

## 🏗️ Service Files

```text
src/services/
├── renderman_service_impl.py    (395 lines)
├── usd_service_impl.py           (527 lines)
└── ngskintools_service_impl.py   (406 lines)

tests/
├── test_renderman_integration.py    (6 tests)
├── test_usd_integration.py          (8 tests)
└── test_ngskintools_integration.py (10 tests)
```

---

## 🎯 Integration Points

### EMSA Container Registration

```python
# src/core/container.py

from ..services.renderman_service_impl import get_renderman_service
from ..services.usd_service_impl import get_usd_service
from ..services.ngskintools_service_impl import get_ngskintools_service

# All three services registered as singletons
container.register('renderman', get_renderman_service())
container.register('usd', get_usd_service())
container.register('ngskintools', get_ngskintools_service())
```

### Access from Asset Manager

```python
# Get services from container
renderman = container.get_service('renderman')
usd = container.get_service('usd')
ngskintools = container.get_service('ngskintools')

# Use services
if renderman.is_available():
    summary = renderman.get_scene_summary()
```

---

## 📚 Complete Documentation

- **API Integration Summary**: `docs/API_INTEGRATION_SUMMARY.md`
- **ngSkinTools2 Details**: `docs/NGSKINTOOLS2_INTEGRATION_COMPLETE.md`
- **Installation Guide**: `docs/MAYA_INSTALLATION_TROUBLESHOOTING.md`
- **Testing Guide**: `docs/MAYA_TESTING_GUIDE.md`

---

*Quick Reference - Asset Manager v1.3.0*  
*Production Ready - September 30, 2025*
