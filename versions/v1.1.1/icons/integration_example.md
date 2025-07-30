# Icon Integration Example

This file shows how to integrate the icon system into the Asset Manager plugin.

## Example: Updating the AssetManagerUI class

```python
# At the top of assetManager.py, add the icon import
try:
    from . import icon_utils
except ImportError:
    import icon_utils

class AssetManagerUI(QMainWindow):
    def __init__(self, parent=None):
        super(AssetManagerUI, self).__init__(parent)
        self.asset_manager = AssetManager()
        self.setWindowTitle(f"Asset Manager v{self.asset_manager.version}")
        
        # Set window icon
        window_icon = icon_utils.get_ui_icon('logo')
        if window_icon:
            self.setWindowIcon(window_icon)
        
        # Rest of initialization...
        self.setup_ui()
        
    def create_toolbar(self):
        """Create the toolbar with icons"""
        toolbar = self.addToolBar('Main')
        
        # New project button with icon
        new_project_btn = QAction('New Project', self)
        new_icon = icon_utils.get_ui_icon('new_project')
        if new_icon:
            new_project_btn.setIcon(new_icon)
        new_project_btn.triggered.connect(self.new_project_dialog)
        toolbar.addAction(new_project_btn)
        
        # Import asset button with icon
        import_btn = QAction('Import Asset', self)
        import_icon = icon_utils.get_ui_icon('import')
        if import_icon:
            import_btn.setIcon(import_icon)
        import_btn.triggered.connect(self.import_asset_dialog)
        toolbar.addAction(import_btn)
        
        # Export selected button with icon
        export_btn = QAction('Export Selected', self)
        export_icon = icon_utils.get_ui_icon('export')
        if export_icon:
            export_btn.setIcon(export_icon)
        export_btn.triggered.connect(self.export_selected_dialog)
        toolbar.addAction(export_btn)
        
        toolbar.addSeparator()
        
        # Refresh button with icon
        refresh_btn = QAction('Refresh', self)
        refresh_icon = icon_utils.get_ui_icon('refresh')
        if refresh_icon:
            refresh_btn.setIcon(refresh_icon)
        refresh_btn.triggered.connect(self.refresh_assets)
        toolbar.addAction(refresh_btn)

    def refresh_assets(self):
        """Refresh the asset library with proper icons"""
        self.asset_list.clear()
        
        if not self.asset_manager.current_project:
            return
            
        project_path = self.asset_manager.current_project
        if not os.path.exists(project_path):
            return
            
        supported_extensions = ['.ma', '.mb', '.obj', '.fbx']
        
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    item = QListWidgetItem(os.path.splitext(file)[0])
                    item.setData(Qt.ItemDataRole.UserRole, file_path)
                    
                    # Set icon based on file type using icon system
                    file_ext = os.path.splitext(file)[1]
                    asset_icon = icon_utils.get_asset_icon(file_ext)
                    if asset_icon:
                        item.setIcon(asset_icon)
                    
                    self.asset_list.addItem(item)
```

## Example: Custom Shelf Button Icon

```mel
// In DRAG&DROP.mel, updated shelf button creation with custom icons
shelfButton -parent $currentShelf
            -label "Asset Manager"
            -annotation "Open Asset Manager - Comprehensive asset management for Maya"
            -image "assetManager_icon.png"        // Custom default icon
            -imageOverlayLabel ""                 // No text overlay needed
            -command $buttonCmd
            -sourceType "python"
            -style "iconOnly";                    // Clean icon-only appearance

// Note: Maya automatically handles hover states if assetManager_icon2.png exists
// in the same directory and follows Maya's naming convention
```

## Example: Adding Search Icon

```python
def create_left_panel(self):
    # ... existing code ...
    
    # Search group with icon
    search_group = QGroupBox("Search")
    search_layout = QHBoxLayout(search_group)
    
    # Add search icon
    search_icon = icon_utils.get_ui_icon('search')
    if search_icon:
        search_icon_label = QLabel()
        search_icon_label.setPixmap(search_icon.pixmap(16, 16))
        search_layout.addWidget(search_icon_label)
    
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("Search assets...")
    self.search_input.textChanged.connect(self.filter_assets)
    search_layout.addWidget(self.search_input)
```
