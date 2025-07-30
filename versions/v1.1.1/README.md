# Asset Manager for Maya v1.1.1

Enhanced asset management with visual organization and color-coding system.

## Installation

Use the `DRAG&DROP.mel` file for quick installation:

1. Drag the `DRAG&DROP.mel` file into Maya's viewport
2. The plugin installs automatically with a shelf button

## What's New in v1.1.1

### 🎨 Asset Type Color-Coding System

- **11 Predefined Types**: Character, Prop, Environment, Vehicle, Weapon, Texture, Material, Animation, Lighting, Camera, Effect
- **Unique Colors**: Each asset type has a distinctive color for instant visual identification
- **Color Legend**: Reference panel showing all asset types and their colors
- **Quick Assignment**: Right-click context menu for fast asset type assignment
- **Visual Organization**: Assets displayed with color-coded indicators

### 🏷️ Enhanced Context Menus

- **Asset Type Assignment**: Quick selection from predefined types
- **Clear Type Option**: Remove asset type assignments easily
- **Visual Feedback**: See asset types immediately in the interface
- **Streamlined Workflow**: Faster asset organization and management

### 📊 Collection Visibility

- **Collection Indicators**: See which collections each asset belongs to
- **Enhanced Organization**: Visual cues for better asset management
- **Multi-Collection Support**: Assets can belong to multiple collections with clear indication

### 🔄 Update Checking System

- **Automatic Checking**: Built-in update checker in Help menu
- **Version Awareness**: Know when newer versions are available
- **Easy Access**: Check for updates directly from the interface

### 🎯 Color Legend Panel

- **Visual Reference**: Always-visible color guide for asset types
- **Professional Display**: Clean, organized color indicators
- **Quick Identification**: Instantly understand asset organization

## Enhanced UI Features

- **Expanded Left Panel**: Color legend, tags, and collections in organized layout
- **Visual Asset List**: Color-coded items for immediate type recognition
- **Enhanced Menu System**: Help menu with update checking and about information
- **Professional Layout**: Improved spacing and organization

## Previous Version Features

All features from v1.1.0 and v1.0.0 are included:

- Asset tagging system with custom labels
- Asset collections and sets management
- Dependency tracking and visualization
- Batch import/export operations
- Asset versioning with notes and history
- Advanced filtering and search capabilities
- Project management and asset library

## Requirements

- Maya 2025.3+
- Python 3.9+
- PySide6, Shiboken6

## Files in this Version

- `assetManager.py` - Main plugin with v1.1.1 features
- `assetManager.mod` - Plugin descriptor
- `DRAG&DROP.mel` - Primary installer
- `version.json` - Version information
- `setup.py` - Python installation script
- `install.bat` / `install.sh` - Alternative installers  
- `CLEAR_MAYA_CACHE.mel` - Cache clearing utility
- `LICENSE` - MIT License
- `icons/` - Icon assets

## Asset Type Colors

- **Character**: Red (#FF6B6B)
- **Prop**: Teal (#4ECDC4)
- **Environment**: Blue (#45B7D1)
- **Vehicle**: Green (#96CEB4)
- **Weapon**: Yellow (#FFEAA7)
- **Texture**: Plum (#DDA0DD)
- **Material**: Mint (#98D8C8)
- **Animation**: Light Yellow (#F7DC6F)
- **Lighting**: Light Purple (#BB8FCE)
- **Camera**: Light Blue (#85C1E9)
- **Effect**: Orange (#F8C471)

For the latest development version, see the root directory of this repository.
