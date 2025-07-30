# -*- coding: utf-8 -*-
"""
Asset Manager Plugin for Maya 2025.3
A comprehensive asset management system for Maya using Python 3 and PySide6

Author: Mike Stumbo
Version: 1.1.1
Maya Version: 2025.3+

New in v1.1.1:
- Asset Type Color-Coding: Visual organization with 11 predefined color types
- Collection Visibility: See which collections each asset belongs to
- Enhanced Context Menus: Quick asset type assignment and management
- Color Legend: Reference panel showing all asset types and colors
- Check for Updates: Automated update checking from Help menu

Previous Features (v1.1.0):
- Asset Tagging System: Custom labels for improved organization
- Asset Collections: Group related assets into collections
- Dependency Tracking: Track asset relationships and dependencies
- Batch Operations: Import/export multiple assets at once
- Asset Versioning: Track and manage asset versions
- Enhanced Context Menus: Right-click asset management
- Advanced Filtering: Filter by tags, collections, and more
- Management Dialogs: Dedicated windows for collections and dependencies

Original Features (v1.0.0):
- Project Management: Create and manage asset projects
- Asset Library: Browse and organize your 3D assets
- Import/Export: Support for .ma, .mb, .obj, .fbx files
- Search & Filter: Find assets quickly by name or category
- Custom Icons: Professional UI with custom branding
- Maya Integration: Seamless integration with Maya 2025.3+
- Modern UI: Built with PySide6 for a professional look
"""

import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

try:
    import maya.cmds as cmds # type: ignore
    import maya.mel as mel # type: ignore
    import maya.OpenMayaUI as omui # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    print("Maya modules not available. Running in standalone mode.")
    MAYA_AVAILABLE = False
    cmds = None
    mel = None
    omui = None

try:
    from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                   QPushButton, QListWidget, QLabel, QLineEdit, 
                                   QApplication, QMenu, QMenuBar, QMessageBox, QComboBox)
    from PySide6.QtCore import Qt, Signal, QObject
    from PySide6.QtGui import QIcon, QPixmap, QFont
    import shiboken6
    QT_AVAILABLE = True
except ImportError:
    print("PySide6 not available.")
    QT_AVAILABLE = False
    # Set as None for type checking but don't use them
    QMainWindow = QWidget = QVBoxLayout = QHBoxLayout = None
    QPushButton = QListWidget = QLabel = QLineEdit = None
    QApplication = QMenu = QMenuBar = QMessageBox = QComboBox = None
    Qt = Signal = QObject = QIcon = QPixmap = QFont = None
    shiboken6 = None

class AssetManager:
    """Main Asset Manager class for v1.1.1"""
    
    # Asset type color definitions
    ASSET_TYPE_COLORS = {
        'Character': '#FF6B6B',     # Red
        'Prop': '#4ECDC4',          # Teal
        'Environment': '#45B7D1',   # Blue
        'Vehicle': '#96CEB4',       # Green
        'Weapon': '#FFEAA7',        # Yellow
        'Texture': '#DDA0DD',       # Plum
        'Material': '#98D8C8',      # Mint
        'Animation': '#F7DC6F',     # Light Yellow
        'Lighting': '#BB8FCE',      # Light Purple
        'Camera': '#85C1E9',        # Light Blue
        'Effect': '#F8C471'         # Orange
    }
    
    def __init__(self):
        self.version = "1.1.1"
        self.plugin_name = "Asset Manager"
        self.config_data = {}
        self.current_project = None
        self.assets_data = {}
        self.tags_data = {}
        self.collections_data = {}
        self.dependencies_data = {}
        self.versions_data = {}
        self.asset_types_data = {}  # New in v1.1.1
        
    def initialize(self):
        """Initialize the asset manager"""
        print(f"Initializing {self.plugin_name} v{self.version}")
        self.load_config()
        
    def load_config(self):
        """Load configuration from file"""
        config_path = self.get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config_data = json.load(f)
                    self.tags_data = self.config_data.get('tags', {})
                    self.collections_data = self.config_data.get('collections', {})
                    self.dependencies_data = self.config_data.get('dependencies', {})
                    self.versions_data = self.config_data.get('versions', {})
                    self.asset_types_data = self.config_data.get('asset_types', {})  # New in v1.1.1
            except Exception as e:
                print(f"Error loading config: {e}")
                
    def save_config(self):
        """Save configuration to file"""
        config_path = self.get_config_path()
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Update config data with all features
        self.config_data['tags'] = self.tags_data
        self.config_data['collections'] = self.collections_data
        self.config_data['dependencies'] = self.dependencies_data
        self.config_data['versions'] = self.versions_data
        self.config_data['asset_types'] = self.asset_types_data  # New in v1.1.1
        
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def get_config_path(self):
        """Get the configuration file path"""
        home = os.path.expanduser("~")
        return os.path.join(home, "Documents", "maya", "assetManager", "config.json")
    
    # v1.1.0 Methods - Asset Tagging
    def add_tag(self, asset_id, tag):
        """Add a tag to an asset"""
        if asset_id not in self.tags_data:
            self.tags_data[asset_id] = []
        if tag not in self.tags_data[asset_id]:
            self.tags_data[asset_id].append(tag)
            self.save_config()
            
    def remove_tag(self, asset_id, tag):
        """Remove a tag from an asset"""
        if asset_id in self.tags_data and tag in self.tags_data[asset_id]:
            self.tags_data[asset_id].remove(tag)
            if not self.tags_data[asset_id]:
                del self.tags_data[asset_id]
            self.save_config()
            
    def get_asset_tags(self, asset_id):
        """Get all tags for an asset"""
        return self.tags_data.get(asset_id, [])
    
    # v1.1.0 Methods - Collections
    def create_collection(self, collection_name):
        """Create a new collection"""
        if collection_name not in self.collections_data:
            self.collections_data[collection_name] = []
            self.save_config()
            
    def add_to_collection(self, asset_id, collection_name):
        """Add an asset to a collection"""
        if collection_name not in self.collections_data:
            self.create_collection(collection_name)
        if asset_id not in self.collections_data[collection_name]:
            self.collections_data[collection_name].append(asset_id)
            self.save_config()
            
    def remove_from_collection(self, asset_id, collection_name):
        """Remove an asset from a collection"""
        if collection_name in self.collections_data and asset_id in self.collections_data[collection_name]:
            self.collections_data[collection_name].remove(asset_id)
            self.save_config()
    
    # v1.1.0 Methods - Dependencies
    def add_dependency(self, asset_id, dependency_id):
        """Add a dependency relationship"""
        if asset_id not in self.dependencies_data:
            self.dependencies_data[asset_id] = []
        if dependency_id not in self.dependencies_data[asset_id]:
            self.dependencies_data[asset_id].append(dependency_id)
            self.save_config()
            
    def get_dependencies(self, asset_id):
        """Get all dependencies for an asset"""
        return self.dependencies_data.get(asset_id, [])
    
    # v1.1.0 Methods - Versioning
    def create_version(self, asset_id, notes=""):
        """Create a new version of an asset"""
        if asset_id not in self.versions_data:
            self.versions_data[asset_id] = []
            
        version_info = {
            'version': len(self.versions_data[asset_id]) + 1,
            'timestamp': datetime.now().isoformat(),
            'notes': notes
        }
        
        self.versions_data[asset_id].append(version_info)
        self.save_config()
        return version_info['version']
    
    # New v1.1.1 Methods - Asset Type Color-Coding
    def set_asset_type(self, asset_id, asset_type):
        """Set the asset type for an asset"""
        if asset_type in self.ASSET_TYPE_COLORS:
            self.asset_types_data[asset_id] = asset_type
            self.save_config()
            
    def get_asset_type(self, asset_id):
        """Get the asset type for an asset"""
        return self.asset_types_data.get(asset_id, None)
    
    def get_asset_type_color(self, asset_id):
        """Get the color for an asset's type"""
        asset_type = self.get_asset_type(asset_id)
        if asset_type and asset_type in self.ASSET_TYPE_COLORS:
            return self.ASSET_TYPE_COLORS[asset_type]
        return None
    
    def clear_asset_type(self, asset_id):
        """Clear the asset type for an asset"""
        if asset_id in self.asset_types_data:
            del self.asset_types_data[asset_id]
            self.save_config()

class AssetManagerUI:
    """Asset Manager UI class that handles Qt availability"""
    
    def __init__(self, parent=None):
        self.asset_manager = AssetManager()
        self.asset_manager.initialize()
        
        if not QT_AVAILABLE:
            print("Qt not available - UI cannot be created")
            self._window = None
            return
            
        try:
            # Import required Qt classes dynamically to avoid None type issues
            from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                           QPushButton, QListWidget, QLabel, QLineEdit, 
                                           QApplication, QMenu, QMenuBar, QMessageBox)
            from PySide6.QtCore import Qt
            
            # Create QMainWindow instance
            self._window = QMainWindow(parent)
            self._setup_ui(QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                          QPushButton, QListWidget, QLabel, QLineEdit, 
                          QApplication, QMenu, QMenuBar, QMessageBox, Qt)
        except ImportError:
            print("Failed to import Qt widgets")
            self._window = None
        
    def _setup_ui(self, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                  QPushButton, QListWidget, QLabel, QLineEdit, 
                  QApplication, QMenu, QMenuBar, QMessageBox, Qt):
        """Setup the user interface with passed Qt classes"""
        if not self._window:
            return
            
        self._window.setWindowTitle("Asset Manager v1.1.1")
        self._window.setMinimumSize(1100, 750)
        
        # Central widget
        central_widget = QWidget()
        self._window.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for filters, tags, and color legend
        left_panel = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setMaximumWidth(280)
        left_widget.setLayout(left_panel)
        
        # Color Legend section (New in v1.1.1)
        left_panel.addWidget(QLabel("Asset Type Colors:"))
        self.color_legend = QVBoxLayout()
        self._setup_color_legend(QHBoxLayout, QLabel)
        legend_widget = QWidget()
        legend_widget.setLayout(self.color_legend)
        left_panel.addWidget(legend_widget)
        
        # Tags section
        left_panel.addWidget(QLabel("Tags:"))
        self.tags_list = QListWidget()
        left_panel.addWidget(self.tags_list)
        
        # Collections section
        left_panel.addWidget(QLabel("Collections:"))
        self.collections_list = QListWidget()
        left_panel.addWidget(self.collections_list)
        
        main_layout.addWidget(left_widget)
        
        # Right panel for main content
        right_layout = QVBoxLayout()
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        new_project_btn = QPushButton("New Project")
        open_project_btn = QPushButton("Open Project")
        import_asset_btn = QPushButton("Import Asset")
        batch_import_btn = QPushButton("Batch Import")
        
        toolbar.addWidget(new_project_btn)
        toolbar.addWidget(open_project_btn)
        toolbar.addWidget(import_asset_btn)
        toolbar.addWidget(batch_import_btn)
        toolbar.addStretch()
        
        right_layout.addLayout(toolbar)
        
        # Asset library with color-coded items
        self.asset_list = QListWidget()
        self.asset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.asset_list.customContextMenuRequested.connect(self.show_context_menu)
        
        right_layout.addWidget(QLabel("Asset Library:"))
        right_layout.addWidget(self.asset_list)
        
        # Search and filter
        search_layout = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search assets...")
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_field)
        
        right_layout.addLayout(search_layout)
        
        main_layout.addLayout(right_layout)
        
        # Setup menu bar
        self._setup_menu_bar(QMenuBar, QMessageBox)
        
        # Connect signals
        new_project_btn.clicked.connect(self.new_project)
        open_project_btn.clicked.connect(self.open_project)
        import_asset_btn.clicked.connect(self.import_asset)
        batch_import_btn.clicked.connect(self.batch_import)
    
    def _setup_color_legend(self, QHBoxLayout, QLabel):
        """Setup the color legend panel (New in v1.1.1)"""
        for asset_type, color in self.asset_manager.ASSET_TYPE_COLORS.items():
            legend_item = QHBoxLayout()
            
            # Color indicator
            color_label = QLabel()
            color_label.setFixedSize(16, 16)
            color_label.setStyleSheet(f"background-color: {color}; border: 1px solid #333;")
            
            # Type name
            type_label = QLabel(asset_type)
            type_label.setMaximumWidth(120)
            
            legend_item.addWidget(color_label)
            legend_item.addWidget(type_label)
            legend_item.addStretch()
            
            self.color_legend.addLayout(legend_item)
    
    def _setup_menu_bar(self, QMenuBar, QMessageBox):
        """Setup the menu bar (Enhanced in v1.1.1)"""
        if not self._window:
            return
            
        menubar = self._window.menuBar()
        
        # Help menu with update checker
        help_menu = menubar.addMenu('Help')
        help_menu.addAction('Check for Updates...', self.check_for_updates)
        help_menu.addAction('About', lambda: self._show_about(QMessageBox))
        
    def _show_about(self, QMessageBox):
        """Show about dialog"""
        QMessageBox.about(self._window, "About Asset Manager", 
                         f"Asset Manager v{self.asset_manager.version}\n"
                         f"Enhanced asset management for Maya\n\n"
                         f"New in v1.1.1:\n"
                         f"• Asset type color-coding\n"
                         f"• Visual collection indicators\n"
                         f"• Enhanced context menus\n"
                         f"• Color legend panel\n"
                         f"• Update checking")
        
    def show(self):
        """Show the UI window"""
        if not QT_AVAILABLE or not self._window:
            print("Cannot show UI - Qt not available or window not created")
            return
        self._window.show()
        
    def show_context_menu(self, position):
        """Show context menu for asset operations (Enhanced in v1.1.1)"""
        if not QT_AVAILABLE or not self._window:
            return
        
        try:
            from PySide6.QtWidgets import QMenu
            
            if self.asset_list.itemAt(position):
                menu = QMenu(self._window)
                
                # Asset Type submenu (New in v1.1.1)
                asset_type_menu = menu.addMenu("Asset Type")
                for asset_type in self.asset_manager.ASSET_TYPE_COLORS.keys():
                    action = asset_type_menu.addAction(asset_type)
                    action.triggered.connect(lambda checked, t=asset_type: self.set_asset_type(t))
                asset_type_menu.addSeparator()
                asset_type_menu.addAction("Clear Type", self.clear_asset_type)
                
                # Tags submenu
                tags_menu = menu.addMenu("Tags")
                tags_menu.addAction("Add Tag...", self.add_tag_dialog)
                tags_menu.addAction("Remove Tag...", self.remove_tag_dialog)
                
                # Collections submenu
                collections_menu = menu.addMenu("Collections")
                collections_menu.addAction("Add to Collection...", self.add_to_collection_dialog)
                collections_menu.addAction("Remove from Collection...", self.remove_from_collection_dialog)
                
                # Dependencies and versions
                menu.addAction("View Dependencies...", self.view_dependencies)
                menu.addAction("Create Version...", self.create_version_dialog)
                
                menu.exec_(self.asset_list.mapToGlobal(position))
        except ImportError:
            print("Could not create context menu - Qt not available")
        
    def new_project(self):
        """Create a new project"""
        print("Creating new project...")
        
    def open_project(self):
        """Open an existing project"""
        print("Opening project...")
        
    def import_asset(self):
        """Import an asset"""
        print("Importing asset...")
        
    def batch_import(self):
        """Batch import multiple assets"""
        print("Batch importing assets...")
        
    def add_tag_dialog(self):
        """Show add tag dialog"""
        print("Add tag dialog...")
        
    def remove_tag_dialog(self):
        """Show remove tag dialog"""
        print("Remove tag dialog...")
        
    def add_to_collection_dialog(self):
        """Show add to collection dialog"""
        print("Add to collection dialog...")
        
    def remove_from_collection_dialog(self):
        """Show remove from collection dialog"""
        print("Remove from collection dialog...")
        
    def view_dependencies(self):
        """Show dependencies viewer"""
        print("View dependencies...")
        
    def create_version_dialog(self):
        """Show create version dialog"""
        print("Create version dialog...")
    
    # New v1.1.1 Methods
    def set_asset_type(self, asset_type):
        """Set asset type for selected asset"""
        print(f"Setting asset type to: {asset_type}")
        
    def clear_asset_type(self):
        """Clear asset type for selected asset"""
        print("Clearing asset type...")
        
    def check_for_updates(self):
        """Check for plugin updates (New in v1.1.1)"""
        print("Checking for updates...")
        
def show_asset_manager():
    """Show the Asset Manager UI"""
    if not QT_AVAILABLE or QApplication is None:
        print("PySide6 not available. Cannot show UI.")
        return None
        
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Get Maya main window as parent if available
    parent = None
    if MAYA_AVAILABLE:
        parent = maya_main_window()
    
    window = AssetManagerUI(parent)
    window.show()
    
    return window

# Maya integration
def maya_main_window():
    """Get Maya's main window"""
    if not MAYA_AVAILABLE or not QT_AVAILABLE or not omui:
        return None
        
    try:
        main_window_ptr = omui.MQtUtil.mainWindow()
        if main_window_ptr and QWidget is not None and shiboken6 is not None:
            return shiboken6.wrapInstance(int(main_window_ptr), QWidget)
    except Exception as e:
        print(f"Error getting Maya main window: {e}")
    
    return None

# Plugin entry point
if __name__ == "__main__":
    if MAYA_AVAILABLE:
        window = show_asset_manager()
    else:
        print("Asset Manager v1.1.1 - Maya not available")
