# Custom Shelf Icons for Asset Manager

## Overview

The Asset Manager plugin uses two custom shelf icons for enhanced visual feedback:

- **`assetManager_icon.png`** - Default shelf button icon (normal state)
- **`assetManager_icon2.png`** - Hover shelf button icon (mouse-over state)

## Icon Specifications

### Technical Requirements

- **Format**: PNG with transparency
- **Size**: 32x32 pixels (recommended for Maya shelf buttons)
- **Color Depth**: 32-bit RGBA
- **Background**: Transparent
- **DPI**: 96 DPI (standard for UI elements)

### Design Guidelines

- **Style**: Flat design consistent with Maya 2025+ UI
- **Colors**: Maya's standard color palette (grays, blues, subtle accents)
- **Visibility**: High contrast for visibility on various shelf backgrounds
- **Simplicity**: Clean, recognizable design that works at small sizes
- **Theme Compatibility**: Works well in both light and dark Maya themes

## Icon States

### Default State (`assetManager_icon.png`)

- Normal appearance when shelf button is idle
- Should be the primary visual representation of the Asset Manager
- Recommended: Neutral colors, clear iconography

### Hover State (`assetManager_icon2.png`)

- Appears when user hovers mouse over the shelf button
- Should provide visual feedback that the button is interactive
- Recommended: Slightly brighter/highlighted version of default icon
- Common approaches:
  - Brighten colors by 10-20%
  - Add subtle glow effect
  - Increase contrast slightly
  - Use accent color (Maya blue)

## Maya Shelf Integration

The shelf button is created with hover support in the MEL installer:

```mel
// Enhanced shelf button with hover icon (Clean Code: Single Responsibility)
shelfButton -parent $currentShelf
            -label "Asset Manager"
            -annotation "Asset Manager v1.3.0 - Enterprise Modular Service Architecture"
            -image "assetManager_icon.png"        // Default state
            -image1 "assetManager_icon2.png"      // Hover state ✨ NEW!
            -imageOverlayLabel ""                 // No text overlay
            -command $buttonCmd
            -sourceType "python"
            -style "iconOnly"                     // Icon-only display
            -enableCommandRepeat true             // Better UX
            -enable true;
```

### Hover State Implementation

Maya shelf buttons support multiple image states using `-image1`, `-image2`, `-image3` parameters:

- **`-image`**: Default state (always visible)
- **`-image1`**: Hover state (mouse over) ⭐ **Now Implemented!**
- **`-image2`**: Pressed state (optional)
- **`-image3`**: Disabled state (optional)

## Icon Usage in Code

In Python, you can access these icons through the icon utilities:

```python
# Get default shelf icon
default_icon = icon_utils.get_ui_icon('shelf_icon')

# Get hover shelf icon  
hover_icon = icon_utils.get_ui_icon('shelf_icon_hover')

# Load icons directly
shelf_icon = icon_utils.load_icon('assetManager_icon.png')
shelf_hover = icon_utils.load_icon('assetManager_icon2.png')
```

## Installation

These icons are automatically installed with the plugin:

1. **Source Location**: `icons/assetManager_icon.png`, `icons/assetManager_icon2.png`
2. **Install Location**: Maya's `plug-ins/icons/` directory
3. **Installer**: The MEL drag-and-drop installer copies these files automatically

## Design Tips

### Effective Shelf Icon Design

- **Symbolic**: Use recognizable symbols (folder, database, asset symbols)
- **Unique**: Distinguishable from other plugin icons
- **Scalable**: Readable at 16x16, 24x24, and 32x32 sizes
- **Professional**: Matches Maya's overall aesthetic

### Color Recommendations

- **Primary**: Maya UI grays (#393939, #4A4A4A, #5A5A5A)
- **Accent**: Maya blue (#5285A6, #4F94CD)
- **Highlight**: Light gray (#7A7A7A, #8A8A8A)
- **Warning**: Orange (#E89611) - use sparingly

### Common Icon Elements

- Folder/directory symbols
- Database/storage symbols  
- Asset/package symbols
- Grid/library symbols
- Document/file symbols
