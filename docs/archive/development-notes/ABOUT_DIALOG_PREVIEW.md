# Asset Manager v1.3.0 - About Dialog Preview

## What Users Will See

When users click **Help → About** in Maya, they will see this professionally formatted dialog:

---

## Asset Manager v1.3.0

### Enterprise Modular Service Architecture (EMSA)

A comprehensive asset management system for Maya  
Built with Clean Code & SOLID principles

**Author:** Mike Stumbo

---

### API Integrations

**Pixar RenderMan®** (v26.3)  
RenderMan® is a registered trademark of Pixar Animation Studios.  
© 1989-2025 Pixar. All rights reserved.  
*Professional production rendering support*

**Universal Scene Description (USD)**  
USD is developed by Pixar Animation Studios and open-sourced.  
© 2016-2025 Pixar. Licensed under Apache 2.0.  
*Industry-standard scene interchange format*

**ngSkinTools2™** (v2.4.0)  
ngSkinTools2™ is developed by Viktoras Makauskas.  
© 2009-2025 <www.ngskintools.com>. All rights reserved.  
*Advanced layer-based skinning system*

---

**Maya®** is a registered trademark of Autodesk, Inc.  
© 2025 Autodesk, Inc. All rights reserved.

**PySide6** is developed by The Qt Company Ltd.  
Licensed under LGPL v3.

---

*Asset Manager is independent software and is not affiliated with,  
endorsed by, or sponsored by Pixar, Autodesk, The Qt Company,  
or ngSkinTools. All trademarks are property of their respective owners.*

---

## Implementation Details

### Code Location

**File**: `src/ui/asset_manager_window.py`  
**Method**: `_on_about(self) -> None`  
**Lines**: ~2186-2218

### Format

- **HTML-formatted** for professional appearance
- **QMessageBox.about()** for native Maya dialog styling
- **Proper trademark symbols**: ® (registered) and ™ (trademark)
- **Copyright notices** with accurate date ranges
- **License references** for each component
- **Italicized descriptions** for each API integration
- **Clear disclaimer** at bottom

### Styling Features

- `<h2>` for main title
- `<h3>` for section headers
- `<b>` for emphasis on names and labels
- `<i>` for descriptive text
- `<hr>` for visual separation
- `<small>` for disclaimer text
- `<br>` for line breaks

### Accessibility

- ✅ Clear hierarchical structure
- ✅ Easy to read font sizes
- ✅ Professional formatting
- ✅ Proper symbol display
- ✅ Scrollable if needed
- ✅ Standard OK button

## How to Test

### In Maya

```python
# Run Asset Manager
import assetManager
assetManager.show_asset_manager()

# Then click: Help → About
```

### Expected Behavior

1. Dialog opens with professional formatting
2. All trademark symbols display correctly (®, ™)
3. HTML formatting renders properly
4. Text is clear and readable
5. All sections are properly separated
6. Disclaimer is visible at bottom
7. OK button closes dialog

## Compliance Verification

### Trademarks Used Correctly: ✅

- RenderMan® - Registered trademark symbol
- ngSkinTools2™ - Trademark symbol
- Maya® - Registered trademark symbol
- USD - No symbol (open-source)
- PySide6 - No symbol (LGPL)

### Copyright Notices: ✅

- Pixar: © 1989-2025 (RenderMan)
- Pixar: © 2016-2025 (USD)
- ngSkinTools: © 2009-2025
- Autodesk: © 2025

### Disclaimers: ✅

- "All rights reserved" where appropriate
- License type references
- Independence statement
- Non-affiliation statement
- Trademark ownership statement

### Professional Standards: ✅

- Clean layout
- Proper attribution
- Official company names
- Correct version numbers
- Developer credits

## Additional Documentation

For complete trademark and copyright information, see:

- **TRADEMARKS.md** - Comprehensive standalone document (200+ lines)
- **LICENSE** - MIT License with third-party acknowledgments section
- **README.md** - "Trademarks and Acknowledgments" section
- **docs/TRADEMARK_COMPLIANCE_SUMMARY.md** - Implementation summary

---

**Asset Manager v1.3.0**  
*Professional trademark compliance in user-facing interface*

✅ **Ready for Production Use**  
✅ **GitHub Publication Compliant**  
✅ **Legal Standards Met**

---

Last Updated: September 30, 2025

September 30, 2025
