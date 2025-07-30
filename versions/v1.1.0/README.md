# Asset Manager for Maya v1.1.0

Enhanced asset management with tagging, collections, and dependency tracking.

## Installation

Use the `DRAG&DROP.mel` file for quick installation:

1. Drag the `DRAG&DROP.mel` file into Maya's viewport
2. The plugin installs automatically with a shelf button

## What's New in v1.1.0

### 🏷️ Asset Tagging System

- **Custom Labels**: Add unlimited tags to assets for improved organization
- **Tag Filtering**: Filter asset library by specific tags
- **Quick Tagging**: Right-click context menu for fast tag management
- **Tag Search**: Find assets by tag instantly

### 📦 Asset Collections/Sets

- **Grouped Assets**: Create collections like "Character Props", "Environment Kit"
- **Collection Management**: Add/remove assets from collections easily
- **Collection Filtering**: View only assets from specific collections
- **Collection Dialog**: Dedicated manager for all collections

### 🔗 Asset Dependencies Tracking

- **Dependency Mapping**: Track which assets reference other assets
- **Dependency Viewer**: Visual representation of asset relationships
- **Dependent Assets**: See what assets would be affected by changes
- **Smart Dependency Management**: Add/remove dependencies with validation

### ⚡ Batch Operations

- **Batch Import**: Import multiple assets simultaneously with progress tracking
- **Batch Export**: Export multiple selected objects as separate assets
- **Progress Indicators**: Real-time feedback during batch operations
- **Error Reporting**: Detailed success/failure reporting

### 📊 Asset Versioning

- **Version Tracking**: Create and manage different versions of assets
- **Version Notes**: Add comments to document changes
- **Version History**: View complete version timeline
- **Quick Version Creation**: Right-click to create asset versions

## Enhanced UI Features

- **Left Panel Organization**: Tags and collections browser
- **Enhanced Context Menus**: Right-click asset management
- **Advanced Filtering**: Filter by multiple criteria
- **Management Dialogs**: Dedicated windows for complex operations

## Requirements

- Maya 2025.3+
- Python 3.9+
- PySide6, Shiboken6

## Files in this Version

- `assetManager.py` - Main plugin with v1.1.0 features
- `assetManager.mod` - Plugin descriptor
- `DRAG&DROP.mel` - Primary installer
- `version.json` - Version information
- `setup.py` - Python installation script
- `install.bat` / `install.sh` - Alternative installers
- `CLEAR_MAYA_CACHE.mel` - Cache clearing utility
- `LICENSE` - MIT License
- `icons/` - Icon assets

For the latest development version, see the root directory of this repository.
