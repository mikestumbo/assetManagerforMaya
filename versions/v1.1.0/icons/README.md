# Asset Manager Icons

This directory contains icons used by the Asset Manager plugin for Maya 2025.3+.

## Icon Categories

### UI Icons

- `asset-manager-logo.png` - Main plugin logo (32x32, 64x64)
- `assetManager_icon.png` - Custom shelf button icon (default state)
- `assetManager_icon2.png` - Custom shelf button icon (hover state)
- `folder-open.png` - Open folder icon for shelf button
- `refresh.png` - Refresh/reload icon
- `search.png` - Search icon
- `settings.png` - Settings/preferences icon

### Asset Type Icons

- `model-icon.png` - 3D model assets
- `texture-icon.png` - Texture/material assets
- `scene-icon.png` - Maya scene files
- `rig-icon.png` - Character rigs
- `animation-icon.png` - Animation files
- `reference-icon.png` - Reference assets

### Action Icons

- `import.png` - Import asset action
- `export.png` - Export asset action
- `delete.png` - Delete asset action
- `duplicate.png` - Duplicate asset action
- `rename.png` - Rename asset action

### Project Icons

- `project-new.png` - New project icon
- `project-open.png` - Open project icon
- `project-save.png` - Save project icon
- `project-close.png` - Close project icon

## Icon Guidelines

- **Size**: Icons should be provided in multiple sizes (16x16, 24x24, 32x32, 48x48)
- **Format**: PNG format with transparency support
- **Style**: Consistent flat design with Maya's UI theme
- **Colors**: Use Maya's standard UI colors for consistency

## Usage in Plugin

Icons are loaded using Qt's QIcon class and can be referenced by their filename:

```python
from PySide6.QtGui import QIcon
import os

# Get icon path
icon_dir = os.path.join(os.path.dirname(__file__), 'icons')
icon_path = os.path.join(icon_dir, 'asset-manager-logo.png')

# Create icon
icon = QIcon(icon_path)
```

## Maya Integration

For shelf buttons, icons can reference Maya's built-in icons or custom icons:

```mel
shelfButton -image "folder-open.png"  // Maya built-in
shelfButton -image "asset-manager-logo.png"  // Custom icon
```
