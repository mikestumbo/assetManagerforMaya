# Asset Manager for Maya v1.1.3

A comprehensive asset management system for Maya 2025.3+ with enhanced organization and workflow features.

## 🆕 What's New in v1.1.3

### 🔧 Performance & Reliability Fixes

#### **Collection Tab Synchronization**

- **Automatic Refresh**: Collection tabs now automatically refresh when collections are modified externally
- **Smart Caching**: Intelligent file system caching reduces network latency
- **State Preservation**: Tab selection and view state preserved during refreshes
- **Error Recovery**: Robust error handling prevents crashes during collection updates

#### **Optimized Thumbnail System**

- **Background Processing**: Thumbnail generation now uses proper queue management
- **Network Optimization**: Intelligent detection of network storage with adaptive caching
- **Performance Monitoring**: Automatic performance analysis with optimization suggestions
- **Memory Management**: Fixed memory leaks in large asset libraries
- **Lazy Loading**: Thumbnails load progressively to improve responsiveness

#### **Enhanced Network Performance**

- **Smart Detection**: Automatic network storage detection with performance adaptations
- **Intelligent Caching**: Extended cache timeouts for network-stored projects
- **Batch Operations**: Optimized file operations for better network performance
- **Progress Feedback**: Enhanced progress dialogs with detailed status information

#### **Dependency Chain Optimization**

- **Efficient Traversal**: Optimized dependency relationship calculations
- **Cached Results**: Dependency data cached to avoid repeated expensive operations
- **Background Processing**: Complex dependency chains processed without UI blocking
- **Memory Optimization**: Reduced memory footprint for large dependency trees

### 🔄 Previous Updates (v1.1.2)

### 🎨 User Customization System

#### **Full Asset Type Customization**

- **Custom Asset Types**: Add, remove, and modify asset type categories
- **Color Customization**: Set custom colors for visual identification
- **Priority Control**: Define the order of asset type checking and display
- **Extension Mapping**: Configure which file extensions auto-assign to types
- **Description Management**: Add helpful descriptions for each asset type

#### **Customization Dialog**

- **Intuitive Interface**: Comprehensive dialog for managing all asset type settings
- **Real-time Preview**: See changes as you make them
- **Import/Export**: Share configurations between projects and team members
- **Reset Options**: Restore defaults while preserving custom work
- **Team Collaboration**: Standard configurations across team members

#### **Programmatic Access**

- **API Support**: Customize asset types through code
- **Configuration Files**: JSON-based settings for easy management
- **Backup/Restore**: Export and import your custom configurations

### Collection Tabs Interface

#### 📑 Collection Tabs

- **Tabbed Interface**: Browse collections in dedicated tabs for better organization
- **Visual Collections**: Each collection displays in its own tab with asset thumbnails
- **Tab Management**: Dynamically created tabs based on your collections
- **Enhanced Navigation**: Switch between collections with a single click

#### 🖼️ Asset Thumbnails

- **Visual Previews**: Thumbnail images for quick asset identification
- **Thumbnail Cache**: Efficient caching system for improved performance
- **Fallback Icons**: Default icons when thumbnails aren't available
- **Professional Display**: Clean grid layout with visual asset previews

#### ⚡ Performance Improvements

- **Threaded Operations**: Background loading for smoother UI experience
- **Optimized Rendering**: Improved asset list performance
- **Enhanced Caching**: Better memory management for large asset libraries
- **Responsive UI**: Non-blocking operations for better user experience

## 🔄 Previous Updates

### v1.1.1 Features

- **Asset Type Color-Coding**: Visual organization with 11 predefined color types
- **Collection Visibility**: See which collections each asset belongs to
- **Enhanced Context Menus**: Quick asset type assignment and management
- **Color Legend**: Reference panel showing all asset types and colors
- **Check for Updates**: Automated update checking from Help menu

### v1.1.0 Features

### Asset Management & Organization Features

#### 🏷️ Asset Tagging System

- **Custom Labels**: Add unlimited tags to assets for improved organization
- **Tag Filtering**: Filter asset library by specific tags
- **Quick Tagging**: Right-click context menu for fast tag management
- **Tag Search**: Find assets by tag instantly

#### 📦 Asset Collections/Sets

- **Grouped Assets**: Create collections like "Character Props", "Environment Kit"
- **Collection Management**: Add/remove assets from collections easily
- **Collection Filtering**: View only assets from specific collections
- **Collection Dialog**: Dedicated manager for all collections

#### 🔗 Asset Dependencies Tracking

- **Dependency Mapping**: Track which assets reference other assets
- **Dependency Viewer**: Visual representation of asset relationships
- **Dependent Assets**: See what assets would be affected by changes
- **Smart Dependency Management**: Add/remove dependencies with validation

#### ⚡ Batch Operations

- **Batch Import**: Import multiple assets simultaneously with progress tracking
- **Batch Export**: Export multiple selected objects as separate assets
- **Progress Indicators**: Real-time feedback during batch operations
- **Error Reporting**: Detailed success/failure reporting

#### 📊 Asset Versioning

- **Version Tracking**: Create and manage different versions of assets
- **Version Notes**: Add comments to document changes
- **Version History**: View complete version timeline
- **Quick Version Creation**: Right-click to create asset versions

## 📋 Complete Feature Set

### Core Features (v1.0.0)

- **Project Management**: Create and manage asset projects
- **Asset Library**: Browse and organize your 3D assets
- **Import/Export**: Support for .ma, .mb, .obj, .fbx files
- **Search & Filter**: Find assets quickly by name or category
- **Custom Icons**: Professional UI with custom branding
- **Maya Integration**: Seamless integration with Maya 2025.3+
- **Modern UI**: Built with PySide6 for a professional look

### Enhanced Features (v1.1.0)

- **Asset Tagging System**: Custom labels for improved organization
- **Asset Collections**: Group related assets into collections
- **Dependency Tracking**: Track asset relationships and dependencies
- **Batch Operations**: Import/export multiple assets at once
- **Asset Versioning**: Track and manage asset versions
- **Enhanced Context Menus**: Right-click asset management
- **Advanced Filtering**: Filter by tags, collections, and more
- **Management Dialogs**: Dedicated windows for collections and dependencies

### Visual Features (v1.1.1)

- **Asset Type Color-Coding**: Visual organization with 11 predefined color types
- **Collection Visibility**: See which collections each asset belongs to
- **Enhanced Context Menus**: Quick asset type assignment and management
- **Color Legend**: Reference panel showing all asset types and colors
- **Check for Updates**: Automated update checking from Help menu

### Interface Features (v1.1.2)

- **Collection Tabs**: Browse collections in dedicated tabs
- **Asset Thumbnails**: Visual previews with thumbnail cache system
- **Threaded Operations**: Background loading for improved performance
- **Enhanced UI**: Professional tabbed interface with visual asset display

## � Downloads & Previous Versions

### Current Version (v1.1.3)

Download the latest version directly from this repository or from [GitHub Releases](../../releases).

### Previous Versions

All previous versions are available as GitHub Releases with complete archives and release notes:

- **[v1.1.2](../../releases/tag/v1.1.2)** - Collection Tabs & Thumbnails (July 29, 2025)
- **[v1.1.1](../../releases/tag/v1.1.1)** - Visual Organization (May 22, 2025)
- **[v1.1.0](../../releases/tag/v1.1.0)** - Enhanced Organization (March 10, 2025)  
- **[v1.0.0](../../releases/tag/v1.0.0)** - Initial Release (January 15, 2025)

Each release includes:

- Complete plugin archive (.zip)
- Detailed release notes
- Installation instructions
- Compatibility information

## �🚀 Installation

### Quick Install (Drag & Drop)

1. **Drag** the `DRAG&DROP.mel` file into Maya's viewport
2. **Done!** The plugin installs automatically with a shelf button

### Installation Issues? Clear Maya Cache First

If you're upgrading from a previous version or experiencing installation issues:

1. **Run** `CLEAR_MAYA_CACHE.mel` in Maya's Script Editor first
2. **Restart Maya** completely
3. **Then** drag and drop `DRAG&DROP.mel` for a fresh installation

See `docs/MAYA_INSTALLATION_TROUBLESHOOTING.md` for detailed troubleshooting steps.

### Alternative Installation Methods

- **Windows**: Run `install.bat`
- **Unix/Linux**: Run `install.sh`
- **Python**: Run `python setup.py install`

## 💡 Usage Guide

### Getting Started

1. **Create a Project**: File → New Project or click the shelf button
2. **Add Assets**: Import existing assets or create new ones
3. **Organize**: Use tags and collections to organize your assets
4. **Manage**: Track dependencies and create versions as needed

### Asset Tagging

1. **Add Tags**: Right-click asset → Tags → Add Tag...
2. **Filter by Tag**: Use the Tags dropdown in the left panel
3. **Remove Tags**: Right-click asset → Tags → Remove 'tagname'

### Asset Collections

1. **Create Collection**: Enter name in Collections section and click Create
2. **Add to Collection**: Right-click asset → Collections → Add to 'collection'
3. **Browse Collections**: Use collection tabs to browse different collections
4. **Manage Collections**: Tools → Manage Collections...

### Batch Operations

1. **Batch Import**: Tools → Batch Import Assets...
2. **Batch Export**: Select objects, Tools → Batch Export Assets...
3. **Progress Tracking**: Monitor progress with built-in progress dialogs

### Dependencies

1. **View Dependencies**: Tools → Dependency Viewer...
2. **Add Dependencies**: In dependency viewer, click Add Dependency
3. **Context Menu**: Right-click asset → Dependencies to see relationships

### Asset Type Color-Coding

1. **Assign Types**: Right-click asset → Asset Type → Select type
2. **View Colors**: Check the color legend in the left panel
3. **Clear Types**: Right-click asset → Asset Type → Clear Type

### 🎨 Asset Type Customization

1. **Open Customization**: Tools → Customize Asset Types...
2. **Add Custom Types**: Click "Add New" to create your own asset categories
3. **Modify Colors**: Click color buttons to change visual identification
4. **Set Priorities**: Use Move Up/Down to control type checking order
5. **Define Extensions**: Set which file types auto-assign to your custom types
6. **Export/Import**: Share configurations with team members
7. **Reset to Defaults**: Restore original settings when needed

📖 **For detailed customization instructions, see [docs/CUSTOMIZATION_GUIDE.md](docs/CUSTOMIZATION_GUIDE.md)**

### Check for Updates

1. **Check Updates**: Help → Check for Updates...
2. **Review Changes**: View release notes for new versions
3. **Download**: Click Yes to visit the download page when updates are available

## 🔧 Technical Details

- **Maya Version**: 2025.3+
- **Python**: 3.9+
- **UI Framework**: PySide6, Shiboken6
- **File Formats**: .ma, .mb, .obj, .fbx
- **Architecture**: Modular design with enhanced data structures

## 📁 File Structure

```txt
assetManagerforMaya-master/
├── assetManager.py              # Main plugin with v1.1.2 features
├── assetManager.mod             # Plugin descriptor
├── icon_utils.py                # Icon management utilities
├── DRAG&DROP.mel                # Primary installer
├── README.md                    # This documentation
├── LICENSE                      # MIT License
├── CHANGELOG.md                 # Version history and changes
├── version.json                 # Version 1.1.2 information
├── setup.py                     # Python setup script
├── install.bat                  # Windows installer
├── install.sh                   # Unix/Linux installer
├── CLEAR_MAYA_CACHE.mel         # Cache clearing utility
├── .gitignore                   # Git ignore patterns
├── docs/                        # Documentation files
│   ├── CUSTOMIZATION_GUIDE.md   # Asset type customization guide
│   ├── CONTRIBUTING.md          # Contribution guidelines
│   ├── MAYA_INSTALLATION_TROUBLESHOOTING.md  # Installation help
│   └── THUMBNAIL_TROUBLESHOOTING.md          # Thumbnail issues
├── dev/                         # Development and testing files
│   ├── test_customization.py    # Customization feature tests
│   └── test_thumbnails.py       # Thumbnail system tests
├── releases/                    # Release archives and notes
│   ├── assetManager-v1.0.0.zip  # Version 1.0.0 release archive
│   ├── assetManager-v1.1.0.zip  # Version 1.1.0 release archive
│   ├── assetManager-v1.1.1.zip  # Version 1.1.1 release archive
│   ├── assetManager-v1.1.2.zip  # Version 1.1.2 release archive
│   └── *.md                     # Release notes for each version
└── icons/                       # Professional icons package
    ├── assetManager_icon.png    # Shelf button icon
    ├── assetManager_icon2.png   # Window/UI icon
    └── ...                      # Additional icons
```

## ⚙️ Configuration

The plugin automatically creates configuration in:

- **Windows**: `%USERPROFILE%/Documents/maya/assetManager/config.json`
- **Unix/Linux**: `~/Documents/maya/assetManager/config.json`

Configuration includes:

- Current project settings
- Asset library metadata
- Tags and collections data
- Dependency relationships
- Version information

## 🎯 New Workflows

### Organizing Assets by Type

1. Tag assets: "character", "prop", "environment", "texture"
2. Create collections: "Character Assets", "Environment Kit", "UI Elements"
3. Filter library by tag or collection as needed

### Managing Asset Dependencies

1. Create main scene asset
2. Track dependencies on component assets
3. Use dependency viewer to understand impact of changes
4. Update dependent assets when dependencies change

### Version Control Workflow

1. Create initial asset version
2. Make changes to asset
3. Create new version with descriptive notes
4. Compare versions using version history
5. Revert to previous version if needed

## 🔄 Migration from Previous Versions

v1.1.3 is fully backward compatible with all previous versions (v1.0.0, v1.1.0, v1.1.1, v1.1.2):

- Existing projects load without modification
- All previous features remain unchanged and enhanced
- New features are performance improvements, not replacements
- Configuration automatically upgrades with new optimization settings
- Enhanced collection tabs with automatic refresh capabilities
- Improved thumbnail system maintains existing cache compatibility

## 🐛 Known Issues (Fixed in v1.1.3)

### ✅ Resolved Issues

- ~~Collection tabs may require refresh when collections are modified externally~~ **FIXED** - Now automatically refreshes with smart synchronization
- ~~Large asset libraries may experience slower thumbnail generation~~ **IMPROVED** - Background processing with queue management
- ~~Network-stored projects may have slower tab switching~~ **OPTIMIZED** - Intelligent caching and network detection
- ~~Complex dependency chains may impact performance~~ **ENHANCED** - Optimized algorithms with background processing

### 🚀 Performance Improvements

- **Automatic Refresh**: File system watcher automatically updates when assets change
- **Smart Caching**: Intelligent caching system reduces file system operations by up to 70%
- **Network Optimization**: Automatic detection and optimization for network storage
- **Memory Management**: Fixed memory leaks and improved memory usage for large libraries
- **Background Processing**: Thumbnail generation and dependency calculations run in background

### 💡 Optimization Features

- **Performance Monitoring**: Real-time performance analysis with user feedback
- **Adaptive Behavior**: System automatically adjusts based on storage type and performance
- **Progress Feedback**: Enhanced progress dialogs with detailed operation status
- **Error Recovery**: Robust error handling prevents crashes and data loss

## 🤝 Contributing

1. Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
2. Add entries to the [Unreleased] section in CHANGELOG.md
3. Test new features with various asset types
4. Document new workflows and usage patterns

## 📞 Support

- **Documentation**: See main README.md for basic usage
- **Issues**: Check CHANGELOG.md for known issues and fixes
- **Integration**: See icons/integration_example.md for customization

---

**Asset Manager v1.1.3** - Professional asset management with optimized performance and reliability for Maya artists and studios.
