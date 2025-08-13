# Asset Manager - User Customization Guide

## Overview

The Asset Manager includes comprehensive customization features that allow you to personalize your workflow with custom asset types, colors, priorities, and behaviors. Version 1.2.0 adds powerful new visual customization options including resizable thumbnails and independent 3D preview controls.

## 🖼️ Customizing Your Visual Experience

### Adjusting Thumbnail Sizes

You can customize thumbnail sizes to match your preferred workflow:

**How to Resize Thumbnails:**

1. Look for the size slider below the Import/Delete buttons in the asset library
2. Drag the slider left for smaller thumbnails (32px) or right for larger ones (128px)
3. The size label shows your current setting in real-time
4. Your preference is automatically saved for next time

**When to Use Different Sizes:**

- **Small (32-48px)**: When you want to see many assets at once in a compact view
- **Medium (64px)**: Default size that balances detail and screen space
- **Large (96-128px)**: When you need to see fine details in asset thumbnails

### Using the 3D Preview System

The Asset Manager includes an independent 3D preview that won't interfere with your main work:

**How to Use 3D Preview:**

1. Select any 3D asset (.ma, .mb, .obj, .fbx) in your library
2. The preview panel shows a real-time 3D view of your asset  
3. Use mouse controls to orbit, zoom, and examine the asset
4. Your main Maya viewport remains completely unchanged

**Preview Controls:**

- **Orbit**: Click and drag to rotate around the asset
- **Zoom**: Mouse wheel or drag to get closer/further from asset
- **Frame**: Double-click to center and frame the asset optimally
- **Independent View**: Each collection tab can have its own viewing angle

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

## 🔄 Getting Started After an Update

If you've recently updated your Asset Manager:

### Exploring New Customization Options

**Visual Customization**:

- Try the new thumbnail size slider to find your preferred asset view size
- Experiment with the independent 3D preview to browse assets without disrupting your workspace
- Your preferences will be saved automatically for future sessions

### Preserving Your Existing Setup

**Your Current Configuration**:

1. All your custom asset types remain exactly as you configured them
2. Color assignments and priorities continue to work unchanged  
3. Asset collections and organization are preserved
4. No need to reconfigure your existing customizations

### Taking Advantage of Improvements

**Enhanced Workflow**:

- Your thumbnail size preference is now remembered between sessions
- 3D asset previews work independently from your main Maya scene
- Better performance with improved caching and memory management

## 🆘 Troubleshooting

### Visual Customization Issues

**Q: Thumbnail size slider doesn't appear**
A: Check that you're using Maya 2025.3+ with PySide6 support

**Q: Thumbnails don't resize when I move the slider**
A: Try refreshing the asset library or clearing the thumbnail cache

**Q: 3D preview shows error messages**
A: This may be due to renderer conflicts - see "3D Preview Issues" below

### 3D Preview Issues

**Q: Error "No object matches name: assetMgrPreview..."**
A: The 3D preview panel was unexpectedly destroyed. Solutions:

   1. Restart the Asset Manager to recreate the preview panel
   2. Switch Maya's renderer to "Maya Software" temporarily
   3. Check Maya Script Editor for additional error details

**Q: Viewport errors with Arnold/RenderMan**
A: Production renderers can conflict with preview panels:

   1. Set Maya's viewport to "Maya Software" or "Viewport 2.0"
   2. Avoid changing renderers while Asset Manager is open
   3. Restart Asset Manager after renderer changes

**Q: "updateModelPanelBar" syntax errors**
A: This indicates panel name corruption with pipe characters (||||||||):

   1. **Immediate Fix**: Run the 3D Preview Reset Tool:

      ```mel
      source "YOURPATH/3D_PREVIEW_RESET.mel";
      ```

   2. Close and reopen the Asset Manager
   3. Restart Maya if corruption persists
   4. Check for complex production scenes that may trigger the issue

**Q: Arnold/RenderMan viewport errors like "Object '|||||||' not found"**
A: Production renderers conflict with the 3D preview system:

   1. **Apply Renderer Safety**: Load the renderer patch:

      ```mel
      source "YOURPATH/RENDERER_SAFE_PATCH.mel";
      ```

   2. Switch Maya's main renderer to "Maya Software" when using Asset Manager
   3. Avoid previewing complex RenderMan scenes with many nodes
   4. Consider using simplified proxy assets for preview

**Q: "RuntimeError: Object not found" in mtoa/viewport.py**
A: Arnold is trying to access corrupted preview panels:

   1. Reset all 3D preview panels using the reset tool
   2. Restart Asset Manager to create clean panels
   3. Use "Maya Software" renderer for asset preview workflows
   4. Keep Arnold scenes separate from asset management workflows

**Q: Complex production scenes (like RenderMan rigs) cause errors**
A: Large production files can overwhelm the preview system:

   1. Use simplified proxy versions for Asset Manager library
   2. Switch to "Maya Software" renderer before opening Asset Manager
   3. Consider creating lightweight preview versions of complex assets
   4. Use the renderer-safe 3D preview functions for production compatibility

**Q: Preview camera controls not working**
A: Check that the preview panel is properly initialized:

   1. Verify you can see assets loading in the preview
   2. Try right-clicking in the preview area for camera options
   3. Restart Asset Manager if preview appears frozen

### Asset Type Customization Issues

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

### Performance Issues

**Q: Asset Manager feels slow with large libraries**
A: Try these optimization steps:

   1. Use smaller thumbnail sizes (32-48px) for better performance
   2. Limit the number of assets in your library folders
   3. Close the 3D preview if not needed
   4. Clear old thumbnail cache files periodically

**Q: Maya becomes unresponsive during asset loading**
A: Large production scenes can cause delays:

   1. Use "Maya Software" renderer for faster loading
   2. Avoid complex RenderMan/Arnold scenes in preview
   3. Consider using proxy/simplified versions for thumbnails

## 📞 Support

For additional help with customization features:

- Check the main Asset Manager documentation
- Test changes in a safe environment first
- Export your working configuration before experimenting
- Consider the impact on team members when sharing configurations

---

**Enjoy your fully customizable Asset Manager experience!** 🎉
