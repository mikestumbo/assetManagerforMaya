# Asset Manager for Maya v1.2.1

A comprehensive asset management system for Maya 2025.3+ with **guaranteed visible background colors**, professional multi-select functionality, and **critical bug fixes**.

## 🔧 **Critical Fixes in v1.2.1**

### 🚀 **FIXED: Drag & Drop Duplication Issue**

**Problem Solved**: Drag & drop operations no longer create duplicate imports when dragging assets to Maya viewport.

- **🎯 Root Cause Fixed**: Eliminated double-import mechanism where both primary and fallback import methods executed sequentially
- **🛡️ Intelligent Tracking**: Time-based duplicate prevention system with smart cooldown timers
- **⚡ Enhanced Performance**: Conditional fallback logic instead of sequential execution for more reliable operations
- **🔄 Better Recovery**: Improved error handling and user feedback during drag & drop operations

### 🔗 **FIXED: GitHub Updates Feature**

**Real Integration**: "Check for Updates" feature now properly connects to the actual GitHub repository.

- **🌐 Live API Connection**: Real GitHub API integration with proper error handling and timeout management
- **📍 Correct Repository**: Updated endpoint to point to the actual project repository
- **🛡️ Robust Error Handling**: Enhanced network error recovery and user feedback
- **⏱️ Reliable Timeouts**: Improved connection handling for various network conditions

### 🎨 **ENHANCED: Background Transparency**

**Visual Improvement**: Icon backgrounds are now more transparent for better aesthetic appeal.

- **✨ Subtle Backgrounds**: Reduced alpha from 180 to 120 for more transparent appearance
- **👁️ Maintained Visibility**: Preserved breakthrough color technology while improving visual balance
- **🎪 Professional Polish**: Better integration with Maya's overall visual design
- **🔧 Configurable**: Transparency enhancement maintains all existing color customization features

## 🎉 **Revolutionary v1.2.0 Features**

A comprehensive asset management system for Maya 2025.3+ with **guaranteed visible background colors** and professional multi-select functionality.

### 🎨 **BREAKTHROUGH: Guaranteed Visible Background Colors**

**The #1 requested feature is finally here!** Asset type background colors are now **guaranteed visible** in all Maya UI themes.

- **🔥 Problem Solved**: Background colors visible in all Maya themes (light, dark, custom)
- **💪 Bulletproof Technology**: Custom `AssetTypeItemDelegate` that physically paints backgrounds
- **🌈 Enhanced Visibility**: HSV color manipulation ensures vibrant, distinct colors for each asset type
- **⚡ Real-time Updates**: Colors update instantly when asset types change
- **🎪 Professional Polish**: Selection states enhanced with proper highlighting and borders

> **Technical Innovation**: Uses Qt's custom delegate system to bypass CSS conflicts that caused invisible colors in previous versions. This approach **cannot be overridden** by any Maya UI theme.

### 🎯 **Professional Multi-Select Functionality**

Transform your workflow with powerful batch operations:

- **Ctrl+Click**: Add/remove individual assets from selection
- **Shift+Click**: Select ranges of assets for batch operations  
- **Ctrl+A**: Select all assets in current view
- **Visual Feedback**: Professional blue borders and backgrounds for selected items
- **Cross-Collection**: Multi-select works in both main library and collection tabs

### 🚀 **Bulk Operations for Power Users**

Boost productivity with batch asset management:

- **Import Selected (Ctrl+I)**: Import multiple assets simultaneously
- **Add to Collection (Ctrl+Shift+C)**: Batch add assets to collections
- **Drag & Drop Multiple**: Drag selected assets directly to Maya viewport
- **Professional UI**: Clear visual indicators for selected items

### 🎪 **Enhanced Drag & Drop Support**

Streamlined Maya integration:

- **Drag from Library**: Drag assets directly from Asset Manager to Maya viewport
- **Instant Import**: Assets import automatically on drop
- **Multi-Asset Drag**: Drag multiple selected assets at once
- **Visual Feedback**: Enhanced drag indicators and responsiveness

### 🔧 Performance & Reliability Fixes

#### **Collection Tab Synchronization**

## 🎨 **Core Features**

### **Visual Asset Organization**

- **Color-Coded Asset Types**: Guaranteed visible background colors for Models, Textures, Rigs, Environments, etc.
- **Professional Icons**: High-quality icons with visual asset type indicators
- **Grid & List Views**: Flexible viewing options with consistent color coding
- **Smart Filtering**: Quick filtering by asset type with visual color coding

### **Collection Management**

- **Tabbed Collections**: Organize assets into themed collections with separate tabs
- **Drag & Drop Organization**: Easy collection management with visual feedback
- **Persistent Collections**: Collections saved automatically between sessions
- **Cross-Collection Multi-Select**: Advanced selection across all collection tabs

### **Maya Integration**

- **Seamless Import**: Direct asset import with multiple file format support
- **Viewport Drag & Drop**: Drag assets directly into Maya viewport for instant import
- **Scene Integration**: Smart asset placement and scene organization
- **Format Support**: Maya (.ma/.mb), OBJ, FBX, Alembic, USD, and more

### **Professional UI**

- **Modern Interface**: Clean, professional design optimized for production use
- **Keyboard Shortcuts**: Industry-standard shortcuts for power users
- **Responsive Layout**: Adaptive UI that works on different screen sizes
- **Persistent Preferences**: UI settings and window geometry saved between sessions

## 🔧 **Technical Excellence**

### **Stability & Performance**

- **Memory-Safe Operations**: Enhanced memory management for large asset libraries
- **Network Optimization**: Intelligent caching and lazy loading for network storage
- **Error Recovery**: Robust handling of edge cases and network issues
- **Thread Safety**: Improved threading for background operations

### **Background Color Technology**

- **AssetTypeItemDelegate**: Custom Qt delegate for direct background painting
- **HSV Color Manipulation**: Ensures vibrant, visible colors in all themes
- **CSS Bypass**: Completely avoids Qt CSS system conflicts
- **Cross-Platform**: Reliable color display on Windows, macOS, and Linux

---

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

## 📅 Previously Updated Versions

### v1.1.3 Features (2023-08-30)

- **Automatic Refresh**: Collection tabs now automatically refresh when collections are modified externally
- **Smart Caching**: Intelligent file system caching reduces network latency
- **State Preservation**: Tab selection and view state preserved during refreshes
- **Error Recovery**: Robust error handling prevents crashes during collection updates
- **Optimized Thumbnails**: Background processing with queue management for better performance
- **Network Optimization**: Intelligent detection of network storage with adaptive caching
- **Memory Management**: Fixed memory leaks in large asset libraries
- **Dependency Chain Optimization**: Efficient traversal and cached results for better performance

### v1.1.2 Features (2023-07-15)

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

## 📦 Downloads & Previous Versions

### Current Version (v1.2.1)

Download the latest version directly from this repository or from [GitHub Releases](../../releases).

### Previous Versions

All previous versions are available as GitHub Releases with complete archives and release notes:

- **[v1.2.0](../../releases/tag/v1.2.0)** - Revolutionary Background Colors & Multi-Select (August 18, 2025)
- **[v1.1.4](../../releases/tag/v1.1.4)** - UI Improvements & Window Memory (August 7, 2025)
- **[v1.1.3](../../releases/tag/v1.1.3)** - Performance & Reliability (August 7, 2025)
- **[v1.1.2](../../releases/tag/v1.1.2)** - Collection Tabs & Thumbnails (July 29, 2025)
- **[v1.1.1](../../releases/tag/v1.1.1)** - Visual Organization (May 22, 2025)
- **[v1.1.0](../../releases/tag/v1.1.0)** - Enhanced Organization (March 10, 2025)  
- **[v1.0.0](../../releases/tag/v1.0.0)** - Initial Release (January 15, 2025)

Each release includes:

- Complete plugin archive (.zip)
- Detailed release notes
- Installation instructions
- Compatibility information

## 🚀 **Installation**

### **Quick Install (Drag & Drop)**

1. **Download** `assetManager-v1.2.1.zip` from the releases
2. **Extract** the files to your preferred location
3. **Drag** the `DRAG&DROP.mel` file into Maya's viewport
4. **Done!** The plugin installs automatically with a shelf button

### **Upgrading from Previous Versions**

**Important for v1.2.1**: Clear Maya cache to ensure all fixes work properly:

1. **Run** `CLEAR_MAYA_CACHE.mel` in Maya's Script Editor first
2. **Restart Maya** completely  
3. **Install** v1.2.1 using the drag & drop method above

### **Alternative Installation Methods**

- **Windows**: Run `install.bat`
- **Unix/Linux**: Run `install.sh`  
- **Python**: Run `python setup.py install`

### **Troubleshooting**

If you experience any issues after installation:

- Ensure you cleared Maya cache before upgrading to v1.2.1
- Restart Maya completely after installation
- Verify Maya 2025.3+ compatibility
- For drag & drop issues, ensure you're using the latest v1.2.1 with duplicate prevention fixes

See `docs/MAYA_INSTALLATION_TROUBLESHOOTING.md` for detailed troubleshooting steps.

## 💡 **Usage Guide**

### **Getting Started with v1.2.1**

1. **Open Asset Manager**: Click the shelf button or run from Scripts menu
2. **Add Assets**: Use "Add Asset" button to include `.mb`, `.ma`, `.obj`, `.fbx` files  
3. **Visual Organization**: Assets display with guaranteed visible background colors
4. **Reliable Drag & Drop**: Drag assets to Maya viewport without duplicate imports (v1.2.1 fix)
5. **Multi-Select**: Hold `Ctrl` to select multiple assets for batch operations
6. **Collection Management**: Group related assets using the collection system
7. **Check Updates**: Use Help → Check for Updates for real GitHub integration (v1.2.1 fix)

### **New v1.2.1 Features**

### 🔧 **Critical Bug Fixes**

- Drag & drop operations now work reliably without creating duplicate file imports
- GitHub updates feature connects to real repository for accurate version checking
- Enhanced background transparency for better visual integration with Maya themes

### 🎨 **Advanced Background Color Technology**

- Every asset now has guaranteed visible background colors
- No more invisible assets on matching background themes
- Intelligent color selection prevents visual conflicts

### 📦 Enhanced Multi-Select Operations

- Select multiple assets with `Ctrl+Click`
- Batch export, copy, and organize operations
- Professional workflow efficiency improvements

### **Asset Collections**

1. **Create Collection**: Enter name in Collections section and click Create
2. **Add to Collection**: Right-click asset → Collections → Add to 'collection'
3. **Browse Collections**: Use collection tabs to browse different collections
4. **Manage Collections**: Tools → Manage Collections...

### **Professional Workflow**

1. **Browse**: Navigate your asset library with visual previews
2. **Preview**: View assets with clear, contrasting backgrounds  
3. **Select**: Use single-click or multi-select for operations
4. **Import**: Double-click or drag assets directly into Maya scenes
5. **Organize**: Create collections and manage your asset library

### **Asset Type Management**

#### 🔍 Visual Asset Types

- **Assign Types**: Right-click asset → Asset Type → Select type
- **Color Coding**: Each type has guaranteed visible background colors
- **Clear Types**: Right-click asset → Asset Type → Clear Type

#### ⚙️Custom Asset Types

1. **Open Customization**: Tools → Customize Asset Types...
2. **Add Types**: Create custom asset categories with unique colors
3. **Color Selection**: Automatic contrast ensures visibility on all themes
4. **Priority Control**: Set type checking and display order
5. **File Extensions**: Auto-assign file types to custom categories

### **Advanced Features**

#### 📊 Dependency Management

- **View Dependencies**: Tools → Dependency Viewer for asset relationships
- **Track References**: Monitor file dependencies and connections
- **Context Access**: Right-click any asset to see its dependency tree

#### 🎯 Professional Tools

- **Batch Operations**: Multi-select for efficient asset management
- **Collection System**: Organize assets into themed groups
- **Maya Integration**: Seamless workflow with Maya's native tools
- **Performance**: Optimized for large asset libraries

1. **Reset to Defaults**: Restore original settings when needed

📖 **For detailed customization instructions, see [docs/CUSTOMIZATION_GUIDE.md](docs/CUSTOMIZATION_GUIDE.md)**

### Check for Updates

1. **Check Updates**: Help → Check for Updates...
2. **Review Changes**: View release notes for new versions
3. **Download**: Click Yes to visit the download page when updates are available

## 🔧 **Technical Details**

- **Maya Version**: 2025.3+
- **Python**: 3.9+
- **UI Framework**: PySide6, Shiboken6 with custom AssetTypeItemDelegate
- **File Formats**: .ma, .mb, .obj, .fbx
- **Architecture**: Revolutionary background color technology with guaranteed visibility

### **v1.2.0 Technical Breakthrough**

#### 🎨 AssetTypeItemDelegate Technology

- Custom QStyledItemDelegate implementation for guaranteed visible backgrounds
- Intelligent HSV color manipulation prevents theme conflicts
- Automatic contrast calculation ensures visibility on all Maya themes
- Professional UI standards with consistent visual hierarchy

#### 📊 Enhanced Performance

- Optimized rendering pipeline for better asset display
- Multi-select operations with efficient batch processing
- Smart caching system for improved responsiveness
- Background color computation with minimal performance impact

## 📁 File Structure

```txt
assetManagerforMaya-master/
├── assetManager.py              # Main plugin with v1.2.1 fixes & v1.2.0 features
├── assetManager.mod             # Plugin descriptor
├── icon_utils.py                # Icon management utilities
├── DRAG&DROP.mel                # Primary installer (v1.2.1)
├── README.md                    # This documentation
├── LICENSE                      # MIT License
├── CHANGELOG.md                 # Version history and changes
├── version.json                 # Version 1.2.1 information
├── setup.py                     # Python setup script
├── install.bat                  # Windows installer (v1.2.1)
├── install.sh                   # Unix/Linux installer (v1.2.1)
├── CLEAR_MAYA_CACHE.mel         # Cache clearing utility (v1.2.1)
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

## 🔄 **Migration from Previous Versions**

### **Upgrading to v1.2.1**

**⚠️ Important**: Clear Maya cache before upgrading to ensure all fixes work properly:

1. **Run** `CLEAR_MAYA_CACHE.mel` in Maya's Script Editor
2. **Restart Maya** completely
3. **Install** v1.2.1 using the drag & drop method

### **Full Backward Compatibility**

v1.2.1 is fully backward compatible with all previous versions (v1.0.0 → v1.2.0):

- **Existing Projects**: Load without modification with enhanced reliability
- **All Features**: Previous functionality remains unchanged and improved
- **New Benefits**: Automatic drag & drop fixes and real GitHub updates
- **Configuration**: Seamlessly upgrades with improved reliability systems
- **Zero Data Loss**: All assets, collections, and settings preserved

### **What's New in Your Existing Projects**

- **Reliable Operations**: Drag & drop now works without creating duplicate imports
- **Real Updates**: GitHub updates feature connects to actual repository  
- **Enhanced Visuals**: More transparent backgrounds for better integration
- **Preserved Workflows**: All existing workflows work exactly as before, just more reliably

## 🎯 **Revolutionary v1.2.1 Improvements**

### **🏆 Critical Issues Resolved in v1.2.1**

**The Problems**: Drag & drop duplications, non-functional GitHub updates, and overly opaque backgrounds.

**The Solutions**: Intelligent duplicate prevention, real GitHub API integration, and enhanced transparency.

**The Results**: 100% reliable drag & drop operations, functional update checking, and improved visual aesthetics.

### 🔧 Critical Fixes Achievements

### **✅ All Major Issues Resolved in v1.2.1**

- ~~Drag & drop creating duplicate file imports~~ **COMPLETELY FIXED** - Intelligent time-based duplicate prevention system
- ~~GitHub updates feature not working with real repository~~ **FULLY RESOLVED** - Live API integration with robust error handling
- ~~Background transparency could be improved~~ **ENHANCED** - Optimized alpha values for better visual integration
- ~~Import tracking needed improvement~~ **SIGNIFICANTLY IMPROVED** - Smart cooldown timers and conditional fallback logic
- ~~Network error handling in updates feature~~ **PROFESSIONALLY HANDLED** - Comprehensive timeout and error recovery systems

### **🚀 Reliability & Performance Achievements**

- **Perfect Drag & Drop**: Every drag operation guaranteed to import once without duplicates
- **Real GitHub Integration**: Live update checking with actual repository connectivity
- **Professional Visuals**: Enhanced transparency while maintaining guaranteed color visibility
- **Smart Error Recovery**: Robust handling of network issues and edge cases
- **Future-Proof**: Scalable architecture ready for continued development

### **🎨 Visual Excellence Maintained**

- **Guaranteed Visibility**: Every asset still guaranteed visible on all Maya themes (v1.2.0 breakthrough preserved)
- **Enhanced Transparency**: Improved visual integration with Maya's interface design
- **Professional Standards**: Consistent visual hierarchy with optimized transparency levels
- **User Experience**: All v1.2.0 revolutionary features enhanced with v1.2.1 reliability improvements

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

**Asset Manager v1.2.1** - Professional asset management with guaranteed visible background colors, reliable drag & drop operations, real GitHub updates, and enhanced transparency for Maya artists and studios.
