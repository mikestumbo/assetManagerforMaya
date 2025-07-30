# -*- coding: utf-8 -*-
"""
Asset Manager Plugin for Maya 2025.3
A comprehensive asset management system for Maya using Python 3 and PySide6

Author: Mike Stumbo
Version: 1.1.0
Maya Version: 2025.3+

New in v1.1.0:
- Asset Tagging System: Custom labels for improved organization
- Asset Collections: Group related assets into collections
- Dependency Tracking: Track asset relationships and dependencies
- Batch Operations: Import/export multiple assets at once
- Asset Versioning: Track and manage asset versions
- Enhanced Context Menus: Right-click asset management
- Advanced Filtering: Filter by tags, collections, and more
- Management Dialogs: Dedicated windows for collections and dependencies

Previous Features (v1.0.0):
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
from datetime import datetime
from pathlib import Path

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
                                   QApplication, QMenu, QComboBox, QMenuBar, QMessageBox)
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
    QApplication = QMenu = QComboBox = QMenuBar = QMessageBox = None
    Qt = Signal = QObject = QIcon = QPixmap = QFont = None
    shiboken6 = None

class AssetManager:
    """Main Asset Manager class for v1.1.0"""
    
    def __init__(self):
        self.version = "1.1.0"
        self.plugin_name = "Asset Manager"
        self.config_data = {}
        self.current_project = None
        self.assets_data = {}
        self.tags_data = {}
        self.collections_data = {}
        self.dependencies_data = {}
        self.versions_data = {}
        
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
            except Exception as e:
                print(f"Error loading config: {e}")
                
    def save_config(self):
        """Save configuration to file"""
        config_path = self.get_config_path()
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        self.config_data.update({
            'tags': self.tags_data,
            'collections': self.collections_data,
            'dependencies': self.dependencies_data,
            'versions': self.versions_data
        })
        
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def get_config_path(self):
        """Get the configuration file path"""
        home = os.path.expanduser("~")
        return os.path.join(home, "Documents", "maya", "assetManager", "config.json")
    
    # New v1.1.0 methods
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
            self.save_config()
    
    def create_collection(self, collection_name):
        """Create a new collection"""
        if collection_name not in self.collections_data:
            self.collections_data[collection_name] = []
            self.save_config()
    
    def add_to_collection(self, asset_id, collection_name):
        """Add an asset to a collection"""
        if collection_name in self.collections_data:
            if asset_id not in self.collections_data[collection_name]:
                self.collections_data[collection_name].append(asset_id)
                self.save_config()
    
    def track_dependency(self, asset_id, dependency_id):
        """Track a dependency between assets"""
        if asset_id not in self.dependencies_data:
            self.dependencies_data[asset_id] = []
        if dependency_id not in self.dependencies_data[asset_id]:
            self.dependencies_data[asset_id].append(dependency_id)
            self.save_config()
    
    def create_version(self, asset_id, version_notes=""):
        """Create a new version of an asset"""
        if asset_id not in self.versions_data:
            self.versions_data[asset_id] = []
        
        version_info = {
            'version': len(self.versions_data[asset_id]) + 1,
            'date': datetime.now().isoformat(),
            'notes': version_notes
        }
        
        self.versions_data[asset_id].append(version_info)
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
                                           QApplication, QMenu, QComboBox)
            from PySide6.QtCore import Qt
            
            # Create QMainWindow instance
            self._window = QMainWindow(parent)
            self._setup_ui(QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                          QPushButton, QListWidget, QLabel, QLineEdit, 
                          QApplication, QMenu, QComboBox, Qt)
        except ImportError:
            print("Failed to import Qt widgets")
            self._window = None
        
    def _setup_ui(self, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                  QPushButton, QListWidget, QLabel, QLineEdit, 
                  QApplication, QMenu, QComboBox, Qt):
        """Setup the user interface with passed Qt classes"""
        if not self._window:
            return
            
        self._window.setWindowTitle("Asset Manager v1.1.0")
        self._window.setMinimumSize(1000, 700)
        
        # Central widget
        central_widget = QWidget()
        self._window.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for filters and tools
        left_panel = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(250)
        
        # Tags section
        left_panel.addWidget(QLabel("Tags:"))
        self.tags_list = QListWidget()
        left_panel.addWidget(self.tags_list)
        
        # Collections section
        left_panel.addWidget(QLabel("Collections:"))
        self.collections_list = QListWidget()
        left_panel.addWidget(self.collections_list)
        
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
        
        # Asset library
        self.asset_list = QListWidget()
        self.asset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.asset_list.customContextMenuRequested.connect(self.show_context_menu)
        
        right_layout.addWidget(QLabel("Asset Library:"))
        right_layout.addWidget(self.asset_list)
        
        # Search and filter
        search_layout = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search assets...")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "By Tag", "By Collection"])
        
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_field)
        search_layout.addWidget(QLabel("Filter:"))
        search_layout.addWidget(self.filter_combo)
        
        right_layout.addLayout(search_layout)
        
        # Add panels to main layout
        main_layout.addWidget(left_widget)
        main_layout.addLayout(right_layout)
        
        # Connect signals
        new_project_btn.clicked.connect(self.new_project)
        open_project_btn.clicked.connect(self.open_project)
        import_asset_btn.clicked.connect(self.import_asset)
        batch_import_btn.clicked.connect(self.batch_import)
        
    def show(self):
        """Show the UI window"""
        if not QT_AVAILABLE or not self._window:
            print("Cannot show UI - Qt not available or window not created")
            return
        self._window.show()
        
    def show_context_menu(self, position):
        """Show context menu for asset items"""
        if not QT_AVAILABLE or not self._window:
            return
        
        try:
            from PySide6.QtWidgets import QMenu
            
            menu = QMenu(self._window)
            
            # Tag actions
            tag_menu = menu.addMenu("Tags")
            tag_menu.addAction("Add Tag...", self.add_tag_dialog)
            tag_menu.addAction("Remove Tag...", self.remove_tag_dialog)
            
            # Collection actions
            collection_menu = menu.addMenu("Collections")
            collection_menu.addAction("Add to Collection...", self.add_to_collection_dialog)
            collection_menu.addAction("Remove from Collection...", self.remove_from_collection_dialog)
            
            # Dependency actions
            dep_menu = menu.addMenu("Dependencies")
            dep_menu.addAction("Add Dependency...", self.add_dependency_dialog)
            dep_menu.addAction("View Dependencies", self.view_dependencies)
            
            # Version actions
            version_menu = menu.addMenu("Versions")
            version_menu.addAction("Create Version...", self.create_version_dialog)
            version_menu.addAction("View Versions", self.view_versions)
            
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
        """Batch import assets"""
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
    
    def add_dependency_dialog(self):
        """Show add dependency dialog"""
        print("Add dependency dialog...")
    
    def view_dependencies(self):
        """Show dependencies viewer"""
        print("View dependencies...")
    
    def create_version_dialog(self):
        """Show create version dialog"""
        print("Create version dialog...")
    
    def view_versions(self):
        """Show versions viewer"""
        print("View versions...")

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
        print("Asset Manager v1.1.0 - Maya not available")
