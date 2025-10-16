# Trademarks and Acknowledgments

Asset Manager v1.3.0 is independent software that provides optional integration with several third-party technologies. This document provides proper attribution and acknowledgment for all trademarks, copyrights, and third-party software referenced or integrated with Asset Manager.

---

## Software Integrations

Asset Manager v1.3.0 includes optional API integrations with the following third-party software:

### 1. Pixar RenderMan®

**Status**: Optional Integration  
**Version Supported**: RenderMan 26.3 and later

- **Trademark**: RenderMan® is a registered trademark of Pixar Animation Studios.
- **Copyright**: © 1989-2025 Pixar. All rights reserved.
- **Official Website**: <https://renderman.pixar.com/>
- **API Documentation**: <https://renderman.pixar.com/resources/rman26/index.html>

**Integration Scope**:

- Detection of RenderMan nodes in Maya scenes
- Metadata extraction from RenderMan lights and materials
- Scene analysis for RenderMan content
- Optional cleanup support for RenderMan nodes

**License**: RenderMan for Maya must be separately licensed from Pixar. Asset Manager does not include or distribute any RenderMan software or components.

---

### 2. Universal Scene Description (USD)

**Status**: Optional Integration  
**Version Supported**: USD 23.11 and later

- **Name**: Universal Scene Description (USD)
- **Developer**: Pixar Animation Studios (open-source)
- **Copyright**: © 2016-2025 Pixar. All rights reserved.
- **License**: Apache License 2.0
- **Official Website**: <https://openusd.org/>
- **API Documentation**: <https://openusd.org/release/api/index.html>
- **GitHub Repository**: <https://github.com/PixarAnimationStudios/USD>

**Integration Scope**:

- USD stage inspection and analysis
- Metadata extraction from USD files
- Prim counting and hierarchy analysis
- USD import support in Maya

**License**: USD is open-source software licensed under Apache License 2.0. Asset Manager uses the publicly available USD Python API (pxr module) when available on the user's system.

---

### 3. ngSkinTools2™

**Status**: Optional Integration  
**Version Supported**: ngSkinTools2 2.4.0 and later

- **Trademark**: ngSkinTools2™ is a trademark of Viktoras Makauskas.
- **Copyright**: © 2009-2025 Viktoras Makauskas. All rights reserved.
- **Developer**: Viktoras Makauskas
- **Official Website**: <https://www.ngskintools.com/>
- **API Documentation**: <https://www.ngskintools.com/documentation/v2/api/>

**Integration Scope**:

- Detection of ngSkinTools2 layer data in Maya scenes
- Metadata extraction from skinned meshes
- Layer and influence information analysis
- Optional cleanup support for ngSkinTools2 nodes

**License**: ngSkinTools2 must be separately licensed from <www.ngskintools.com>. Asset Manager does not include or distribute any ngSkinTools2 software or components.

---

## Platform and Framework Acknowledgments

### 4. Autodesk Maya®

**Status**: Required Platform

- **Trademark**: Maya® is a registered trademark of Autodesk, Inc.
- **Copyright**: © 2025 Autodesk, Inc. All rights reserved.
- **Supported Versions**: Maya 2025.3 and later
- **Official Website**: <https://www.autodesk.com/products/maya/>

**Relationship**: Asset Manager is a third-party plugin developed independently for Autodesk Maya. It is not affiliated with, endorsed by, or sponsored by Autodesk, Inc.

---

### 5. Qt Framework and PySide6

**Status**: Required Framework

- **Name**: PySide6 (Python bindings for Qt)
- **Developer**: The Qt Company Ltd.
- **License**: GNU Lesser General Public License (LGPL) version 3
- **Official Website**: <https://www.qt.io/qt-for-python>
- **Documentation**: <https://doc.qt.io/qtforpython-6/>

**Usage**: Asset Manager uses PySide6 for its graphical user interface components. PySide6 is dynamically linked at runtime and is not modified or distributed with Asset Manager.

---

## Additional Acknowledgments

### Python Software Foundation

- **Python®** is a registered trademark of the Python Software Foundation.
- Asset Manager is developed in Python and requires Python 3.10 or later.

### Open Source Libraries

Asset Manager may utilize various open-source Python libraries available through standard package managers. All such libraries retain their original licenses and copyrights.

---

## Disclaimer

### No Affiliation

Asset Manager is **independent software** and is **not affiliated with, endorsed by, or sponsored by**:

- Pixar Animation Studios
- Autodesk, Inc.
- The Qt Company Ltd.
- ngSkinTools / Viktoras Makauskas
- Any other trademark holder mentioned in this document

### Trademark Ownership

All trademarks, service marks, trade names, trade dress, product names, and logos appearing in Asset Manager or its documentation are the property of their respective owners. Any rights not expressly granted herein are reserved.

### No Warranty or Endorsement

The mention of third-party products, services, or websites in Asset Manager or its documentation does not constitute an endorsement. Asset Manager is provided "as is" without warranty of any kind.

### Third-Party Software Requirements

The API integration features provided by Asset Manager are **optional** and require the respective third-party software to be:

1. Separately installed by the user
2. Properly licensed according to the vendor's terms
3. Compatible with the user's Maya version

Asset Manager does not include, distribute, or provide licenses for any third-party software.

---

## Integration Architecture

Asset Manager's integration approach:

1. **Detection-Based**: Checks for the presence of third-party software at runtime
2. **Graceful Degradation**: Works fully without optional integrations installed
3. **No Distribution**: Does not include any third-party code or binaries
4. **API-Level Only**: Uses publicly documented APIs when available
5. **User-Controlled**: All integrations are optional and user-configurable

---

## Contact and Questions

For questions about:

- **Asset Manager licensing**: See LICENSE file in this repository
- **RenderMan licensing**: Contact Pixar Animation Studios
- **USD licensing**: See Apache License 2.0 at <https://www.apache.org/licenses/LICENSE-2.0>
- **ngSkinTools2 licensing**: Contact <www.ngskintools.com>
- **Maya licensing**: Contact Autodesk, Inc.
- **Qt/PySide6 licensing**: See LGPL v3 at <https://www.gnu.org/licenses/lgpl-3.0.html>

---

## Updates to This Document

This document was last updated: **September 30, 2025**

Trademarks, copyrights, and third-party acknowledgments are subject to change. Users should verify current trademark and copyright information directly with the respective trademark and copyright holders.

---

**Asset Manager v1.3.0**  
Copyright (c) 2025 Mike Stumbo  
Licensed under MIT License

*This document is provided for informational purposes and proper attribution.*
