# Asset Manager - User Customization Guide

## Overview

The Asset Manager now includes a comprehensive user customization system that allows you to fully customize asset types, colors, priorities, and behaviors. This guide explains how to use these powerful new features.

## 🎨 Asset Type Customization Features

### What You Can Customize

- **Asset Types**: Add, remove, and modify asset type categories
- **Colors**: Set custom colors for each asset type for visual identification
- **Priorities**: Control the order in which asset types are checked and displayed
- **File Extensions**: Define which file extensions automatically get assigned to each type
- **Descriptions**: Add helpful descriptions for each asset type

### Accessing Customization

1. **Via Menu**: Go to `Tools → Customize Asset Types...`
2. **The dialog provides a comprehensive interface for managing all aspects of asset types**

## 🛠️ Using the Customization Dialog

### Main Interface

The customization dialog is split into two main panels:

#### Left Panel - Asset Type List

- **Asset Type List**: Shows all current asset types sorted by priority
- **Add New**: Create completely new asset types
- **Duplicate**: Copy an existing type as a starting point
- **Delete**: Remove custom asset types (default types cannot be deleted)
- **Priority Controls**: Move types up/down in priority order

#### Right Panel - Type Editor

- **Type ID**: Unique identifier for the asset type
- **Display Name**: Human-readable name shown in the UI
- **Color**: Visual color for the asset type (click to change)
- **Priority**: Numeric priority (lower = higher priority)
- **Description**: Helpful description text
- **File Extensions**: Comma-separated list of file extensions

### Step-by-Step Customization

#### Adding a New Asset Type

1. Click **"Add New"** in the left panel
2. Enter a unique type ID (e.g., "environments")
3. Fill in the details in the right panel:
   - **Display Name**: "Environments"
   - **Color**: Click the color button to choose
   - **Priority**: Set order (0 = highest priority)
   - **Description**: "Environment and scene assets"
   - **Extensions**: ".ma, .mb, .obj"
4. Click **"Apply"** or **"OK"** to save

#### Modifying Existing Types

1. Select an asset type from the left panel
2. Modify any properties in the right panel
3. See real-time preview of changes
4. Click **"Apply"** to save changes

#### Organizing Priorities

- Use **"↑ Move Up"** and **"↓ Move Down"** to reorder types
- Lower priority numbers appear first in lists
- Priority affects auto-detection order when categorizing assets

#### Color Customization

- Click the color button to open the color picker
- Choose any RGB color for visual identification
- Colors appear in asset lists, legends, and context menus
- Preview shows how the color will look

## 💾 Configuration Management

### Importing/Exporting Configurations

#### Export Your Configuration

1. Click **"Export Config..."**
2. Choose a filename (e.g., "my_asset_types.json")
3. Save your custom configuration

#### Import a Configuration

1. Click **"Import Config..."**
2. Select a previously exported JSON file
3. Your asset types will be updated

#### Reset to Defaults

- Click **"Reset to Defaults"** to restore original asset types
- This removes all custom types and resets colors/priorities
- Use with caution - consider exporting first

### Sharing Configurations

You can share asset type configurations between:

- Different Maya installations
- Team members
- Projects

Simply export your configuration and share the JSON file.

## 🎯 Practical Examples

### Example 1: Animation Studio Setup

```text
Priority | Type        | Color      | Extensions
---------|-------------|------------|------------------
0        | Characters  | Red        | .ma, .mb
1        | Environments| Green      | .ma, .mb, .obj
2        | Props       | Blue       | .obj, .fbx, .ma
3        | Rigs        | Purple     | .ma, .mb
4        | Animations  | Orange     | .ma, .mb
5        | Textures    | Yellow     | .jpg, .png, .exr
```

### Example 2: Game Development Setup

```text
Priority | Type        | Color      | Extensions
---------|-------------|------------|------------------
0        | Models      | Blue       | .obj, .fbx
1        | Textures    | Orange     | .png, .jpg, .tga
2        | Materials   | Pink       | .mat, .json
3        | Audio       | Cyan       | .wav, .mp3
4        | Scripts     | Gray       | .py, .cs, .js
5        | Prefabs     | Green      | .prefab, .ma
```

### Example 3: Architectural Visualization

```text
Priority | Type        | Color      | Extensions
---------|-------------|------------|------------------
0        | Buildings   | Brown      | .ma, .mb, .obj
1        | Interiors   | Beige      | .ma, .mb
2        | Furniture   | Wood       | .obj, .fbx
3        | Landscapes  | Green      | .ma, .mb
4        | Lighting    | Yellow     | .ma, .mb
5        | Materials   | Purple     | .ma, .mb
```

## 🔧 Advanced Features

### Programmatic Access

You can also customize asset types programmatically:

```python
from assetManager import AssetManager

# Create asset manager instance
asset_manager = AssetManager()

# Add custom asset type
asset_manager.add_custom_asset_type(
    type_id='environments',
    name='Environments',
    color=[100, 200, 100],
    priority=8,
    extensions=['.ma', '.mb', '.obj'],
    description='Environment and scene assets'
)

# Update existing type
asset_manager.update_asset_type(
    type_id='models',
    color=[255, 100, 50],
    description='Updated description'
)

# Save changes
asset_manager.save_config()
```

### File Extension Auto-Detection

When you define file extensions for asset types:

- Assets are automatically categorized when imported
- Priority order determines which type wins for overlapping extensions
- You can always manually override using the context menu

### Integration with Existing Features

Your custom asset types automatically work with:

- **Asset Lists**: Visual color coding
- **Context Menus**: Assignment options
- **Search/Filtering**: Type-based filtering
- **Collections**: Organization by type
- **Color Legend**: Visual reference guide

## 📝 Best Practices

### Naming Conventions

- Use descriptive, lowercase type IDs (e.g., "environments", "characters")
- Choose clear display names (e.g., "Environment Assets", "Character Models")
- Keep descriptions concise but informative

### Color Choices

- Use distinct colors that are easy to differentiate
- Consider colorblind accessibility
- Use consistent color schemes across projects
- Avoid very light colors on light backgrounds

### Priority Organization

- Put most commonly used types at higher priority (lower numbers)
- Group related types together in priority
- Consider your workflow when setting priorities

### File Extensions

- Be specific with extensions to avoid conflicts
- Consider all file types you work with
- Remember that multiple types can share extensions (priority matters)

## 🚀 Tips and Tricks

1. **Start with Defaults**: Modify existing types before adding new ones
2. **Export Often**: Save your configurations before major changes
3. **Team Standardization**: Share configurations across your team
4. **Project-Specific**: Create different configurations for different project types
5. **Color Coding**: Use colors that match your studio/project branding
6. **Test Changes**: Use the preview to see how changes will look
7. **Backup First**: Export your current config before importing new ones

## 🔄 Updating from Previous Versions

If you're upgrading from a previous version:

1. Your existing asset assignments will be preserved
2. Default colors and types will be updated to the new system
3. Any custom modifications will need to be redone using the new interface
4. Consider exporting your configuration after setting up your preferences

## 🆘 Troubleshooting

### Common Issues

**Q: My custom types don't appear in the context menu**
A: Make sure you clicked "Apply" or "OK" to save changes

**Q: File extensions aren't working for auto-detection**
A: Check that extensions start with a dot (e.g., ".ma" not "ma")

**Q: Colors aren't updating in the asset list**
A: Try refreshing the asset library or restarting the Asset Manager

**Q: I can't delete a default asset type**
A: Default types are protected - you can modify them but not delete them

**Q: Import failed with an error**
A: Check that the JSON file is valid and from a compatible version

## 📞 Support

For additional help with customization features:

- Check the main Asset Manager documentation
- Test changes in a safe environment first
- Export your working configuration before experimenting
- Consider the impact on team members when sharing configurations

---

**Enjoy your fully customizable Asset Manager experience!** 🎉
