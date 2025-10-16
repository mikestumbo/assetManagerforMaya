"""
Collection Manager Dialog for Asset Manager v1.3.0

This module provides the Collection Manager Dialog interface for organizing and managing
asset collections within the Asset Manager system. It follows Clean Code principles
and implements SOLID design patterns for maintainable and extensible collection management.

Author: Asset Manager Development Team
Version: 1.3.0
License: MIT
"""

from typing import List, Dict, Optional, Any
import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QTextEdit, QGroupBox, QSplitter,
    QMessageBox, QInputDialog, QFrame, QScrollArea, QWidget,
    QTreeWidget, QTreeWidgetItem, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont, QPalette, QColor

# Import the unified theme
from .theme import UITheme


class CollectionManagerDialog(QDialog):
    """
    Professional Collection Manager Dialog following Clean Code principles.
    Implements Single Responsibility Principle for collection management operations.
    
    Features:
    - Create/Edit/Delete collections
    - Add/Remove assets from collections
    - Collection categories and organization
    - Collection descriptions and metadata
    - Search and filter collections
    - Import/Export collection definitions
    """
    
    # Signals for communication with main window - Single Responsibility
    collection_created = Signal(str, dict)  # collection_name, collection_data
    collection_updated = Signal(str, dict)  # collection_name, collection_data
    collection_deleted = Signal(str)  # collection_name
    collections_imported = Signal(list)  # list of collections
    
    def __init__(self, parent=None, existing_collections: Optional[Dict[str, Any]] = None):
        """
        Initialize Collection Manager Dialog with professional styling.
        
        Args:
            parent: Parent widget
            existing_collections: Dictionary of existing collections
        """
        super().__init__(parent)
        self.existing_collections = existing_collections or {}
        self.current_collection = None
        self.modified = False
        
        self._setup_ui()
        self._connect_signals()
        self._load_built_in_collections()
        self._populate_collections_list()
        
    def _setup_ui(self) -> None:
        """Setup the user interface - Single Responsibility"""
        self.setWindowTitle("Collection Manager - Asset Manager v1.3.0")
        self.setModal(True)
        self.resize(1000, 700)
        
        # Apply unified theme styling
        self.setStyleSheet(UITheme.get_dialog_stylesheet())
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header section
        self._create_header_section(main_layout)
        
        # Main content splitter
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.content_splitter)
        
        # Left panel - Collections list
        self._create_collections_panel()
        
        # Right panel - Collection details
        self._create_details_panel()
        
        # Button panel
        self._create_button_panel(main_layout)
        
    def _create_header_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the header section with title and search - Single Responsibility"""
        header_frame = QFrame()
        header_frame.setProperty("panel", True)  # Use theme panel styling
        header_layout = QVBoxLayout(header_frame)
        
        # Title
        title_label = QLabel("Collection Manager")
        title_label.setProperty("title", True)  # Use theme styling
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("Organize and manage your asset collections for better project workflow")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #666666; font-style: italic;")
        header_layout.addWidget(desc_label)
        
        # Search and filter controls
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search collections...")
        self.search_input.textChanged.connect(self._filter_collections)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)
        
        self.category_filter = QComboBox()
        self.category_filter.setMinimumHeight(36)  # Increased height for legible font
        self.category_filter.setMinimumWidth(180)  # Ensure adequate width for text
        self.category_filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.category_filter.addItems(["All Categories", "Characters", "Environments", 
                                     "Props", "Textures", "Animation", "Custom"])
        self.category_filter.currentTextChanged.connect(self._filter_collections)
        search_layout.addWidget(QLabel("Category:"))
        search_layout.addWidget(self.category_filter)
        
        header_layout.addLayout(search_layout)
        parent_layout.addWidget(header_frame)
        
    def _create_collections_panel(self) -> None:
        """Create the left panel with collections list - Single Responsibility"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Collections list header
        collections_header = QHBoxLayout()
        collections_label = QLabel("Collections")
        collections_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        collections_header.addWidget(collections_label)
        
        # Quick action buttons - Increased width for full text visibility
        self.new_collection_btn = QPushButton("New")
        self.new_collection_btn.setMinimumWidth(80)  # Increased from 60 for better text fit
        self.duplicate_collection_btn = QPushButton("Copy")
        self.duplicate_collection_btn.setMinimumWidth(80)  # Increased from 60 for better text fit
        self.delete_collection_btn = QPushButton("Delete")
        self.delete_collection_btn.setMinimumWidth(80)  # Increased from 60 for better text fit
        
        collections_header.addStretch()
        collections_header.addWidget(self.new_collection_btn)
        collections_header.addWidget(self.duplicate_collection_btn)
        collections_header.addWidget(self.delete_collection_btn)
        
        left_layout.addLayout(collections_header)
        
        # Collections list
        self.collections_list = QListWidget()
        self.collections_list.setAlternatingRowColors(True)
        self.collections_list.currentItemChanged.connect(self._on_collection_selected)
        left_layout.addWidget(self.collections_list)
        
        # Collection statistics
        self.stats_label = QLabel("0 collections loaded")
        self.stats_label.setStyleSheet("color: #666666; font-size: 11px;")
        left_layout.addWidget(self.stats_label)
        
        self.content_splitter.addWidget(left_widget)
        self.content_splitter.setSizes([300, 700])
        
    def _create_details_panel(self) -> None:
        """Create the right panel with collection details - Single Responsibility"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Collection details form
        self.details_group = QGroupBox("Collection Details")
        details_layout = QVBoxLayout(self.details_group)
        
        # Basic information
        basic_layout = QVBoxLayout()
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self._mark_modified)
        name_layout.addWidget(self.name_input)
        basic_layout.addLayout(name_layout)
        
        # Category - Enhanced height for proper text display
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.setMinimumHeight(36)  # Increased height for legible font
        self.category_input.setMinimumWidth(200)  # Ensure adequate width for text
        self.category_input.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.category_input.addItems(["Characters", "Environments", "Props", 
                                    "Textures", "Animation", "Custom"])
        self.category_input.currentTextChanged.connect(self._mark_modified)
        category_layout.addWidget(self.category_input)
        basic_layout.addLayout(category_layout)
        
        # Description
        basic_layout.addWidget(QLabel("Description:"))
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.description_input.textChanged.connect(self._mark_modified)
        basic_layout.addWidget(self.description_input)
        
        details_layout.addLayout(basic_layout)
        
        # Assets in collection
        assets_group = QGroupBox("Assets in Collection")
        assets_layout = QVBoxLayout(assets_group)
        
        # Asset management controls
        asset_controls = QHBoxLayout()
        self.add_asset_btn = QPushButton("Add Assets")
        self.remove_asset_btn = QPushButton("Remove Selected")
        self.clear_assets_btn = QPushButton("Clear All")
        
        asset_controls.addWidget(self.add_asset_btn)
        asset_controls.addWidget(self.remove_asset_btn)
        asset_controls.addWidget(self.clear_assets_btn)
        asset_controls.addStretch()
        assets_layout.addLayout(asset_controls)
        
        # Assets list
        self.assets_list = QListWidget()
        self.assets_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        assets_layout.addWidget(self.assets_list)
        
        # Asset count
        self.asset_count_label = QLabel("0 assets")
        self.asset_count_label.setStyleSheet("color: #666666; font-size: 11px;")
        assets_layout.addWidget(self.asset_count_label)
        
        details_layout.addWidget(assets_group)
        
        # Collection metadata
        metadata_group = QGroupBox("Metadata")
        metadata_layout = QVBoxLayout(metadata_group)
        
        # Auto-include options
        self.auto_include_by_tag = QCheckBox("Auto-include assets with matching tags")
        self.auto_include_by_type = QCheckBox("Auto-include assets of same type")
        self.auto_include_by_folder = QCheckBox("Auto-include assets from same folder")
        
        metadata_layout.addWidget(self.auto_include_by_tag)
        metadata_layout.addWidget(self.auto_include_by_type)
        metadata_layout.addWidget(self.auto_include_by_folder)
        
        details_layout.addWidget(metadata_group)
        
        right_layout.addWidget(self.details_group)
        
        # Initially disable details panel
        self.details_group.setEnabled(False)
        
        self.content_splitter.addWidget(right_widget)
        
    def _create_button_panel(self, parent_layout: QVBoxLayout) -> None:
        """Create the bottom button panel - Single Responsibility"""
        button_layout = QHBoxLayout()
        
        # Left side buttons
        self.import_btn = QPushButton("Import Collections")
        self.export_btn = QPushButton("Export Collections")
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        
        button_layout.addStretch()
        
        # Save status
        self.save_status_label = QLabel("")
        button_layout.addWidget(self.save_status_label)
        
        # Right side buttons
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setEnabled(False)
        self.close_btn = QPushButton("Close")
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.close_btn)
        
        parent_layout.addLayout(button_layout)
        
    def _apply_professional_styling(self) -> None:
        """Apply professional styling consistent with other dialogs - Single Responsibility"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #34495e;
                background-color: white;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
            
            QListWidget {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                selection-background-color: #3498db;
                selection-color: white;
                outline: none;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
                border-radius: 4px;
                margin: 1px;
            }
            
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QListWidget::item:hover {
                background-color: #ebf3fd;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #21618c;
            }
            
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            
            QLineEdit, QTextEdit, QComboBox {
                background-color: white;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #3498db;
                outline: none;
            }
            
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 10px;
            }
            
            QCheckBox {
                spacing: 8px;
                color: #2c3e50;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
            }
            
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
                image: url(:/icons/check.png);
            }
            
            QSplitter::handle {
                background-color: #bdc3c7;
                width: 2px;
            }
        """)
        
    def _connect_signals(self) -> None:
        """Connect all signal handlers - Single Responsibility"""
        # Collection management buttons
        self.new_collection_btn.clicked.connect(self._create_new_collection)
        self.duplicate_collection_btn.clicked.connect(self._duplicate_collection)
        self.delete_collection_btn.clicked.connect(self._delete_collection)
        
        # Asset management buttons
        self.add_asset_btn.clicked.connect(self._add_assets_to_collection)
        self.remove_asset_btn.clicked.connect(self._remove_assets_from_collection)
        self.clear_assets_btn.clicked.connect(self._clear_collection_assets)
        
        # Import/Export buttons
        self.import_btn.clicked.connect(self._import_collections)
        self.export_btn.clicked.connect(self._export_collections)
        
        # Bottom buttons
        self.save_btn.clicked.connect(self._save_changes)
        self.close_btn.clicked.connect(self._close_dialog)
        
        # Auto-include checkboxes
        self.auto_include_by_tag.toggled.connect(self._mark_modified)
        self.auto_include_by_type.toggled.connect(self._mark_modified)
        self.auto_include_by_folder.toggled.connect(self._mark_modified)
        
    def _load_built_in_collections(self) -> None:
        """Load built-in collection templates - Single Responsibility"""
        self.built_in_collections = {
            "Character Collection": {
                "category": "Characters",
                "description": "Collection for character models, rigs, and animations",
                "assets": [],
                "auto_include_by_tag": True,
                "matching_tags": ["character", "rig", "animation"],
                "built_in": True
            },
            "Environment Collection": {
                "category": "Environments",
                "description": "Collection for environment assets, props, and textures",
                "assets": [],
                "auto_include_by_tag": True,
                "matching_tags": ["environment", "prop", "texture"],
                "built_in": True
            },
            "Animation Collection": {
                "category": "Animation",
                "description": "Collection for animation files, mocap data, and clips",
                "assets": [],
                "auto_include_by_tag": True,
                "matching_tags": ["animation", "mocap", "clip"],
                "built_in": True
            },
            "Texture Library": {
                "category": "Textures",
                "description": "Collection for texture maps, materials, and shaders",
                "assets": [],
                "auto_include_by_tag": True,
                "matching_tags": ["texture", "material", "shader"],
                "built_in": True
            },
            "Work in Progress": {
                "category": "Custom",
                "description": "Collection for assets currently being developed",
                "assets": [],
                "auto_include_by_tag": True,
                "matching_tags": ["wip", "development"],
                "built_in": True
            },
            "Final Assets": {
                "category": "Custom",
                "description": "Collection for completed and approved assets",
                "assets": [],
                "auto_include_by_tag": True,
                "matching_tags": ["final", "approved"],
                "built_in": True
            }
        }
        
        # Merge with existing collections
        for name, data in self.built_in_collections.items():
            if name not in self.existing_collections:
                self.existing_collections[name] = data
                
    def _populate_collections_list(self) -> None:
        """Populate the collections list widget - Single Responsibility"""
        self.collections_list.clear()
        
        for collection_name, collection_data in self.existing_collections.items():
            item = QListWidgetItem(collection_name)
            
            # Add visual indicators
            category = collection_data.get("category", "Custom")
            asset_count = len(collection_data.get("assets", []))
            
            item.setText(f"{collection_name} ({category}) - {asset_count} assets")
            
            # Mark built-in collections differently
            if collection_data.get("built_in", False):
                item.setToolTip(f"Built-in collection: {collection_data.get('description', '')}")
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            
            self.collections_list.addItem(item)
            
        self._update_stats_label()
        
    def _filter_collections(self) -> None:
        """Filter collections based on search and category - Single Responsibility"""
        search_text = self.search_input.text().lower()
        category_filter = self.category_filter.currentText()
        
        for i in range(self.collections_list.count()):
            item = self.collections_list.item(i)
            collection_name = item.text().split(" (")[0]  # Extract name before category
            collection_data = self.existing_collections.get(collection_name, {})
            
            # Check search filter
            search_match = (search_text == "" or 
                          search_text in collection_name.lower() or
                          search_text in collection_data.get("description", "").lower())
            
            # Check category filter
            category_match = (category_filter == "All Categories" or
                            collection_data.get("category", "Custom") == category_filter)
            
            item.setHidden(not (search_match and category_match))
            
    def _on_collection_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle collection selection - Single Responsibility"""
        if current is None:
            self.details_group.setEnabled(False)
            self.current_collection = None
            return
            
        # Save current changes before switching
        if self.modified and previous is not None:
            self._save_current_collection()
            
        collection_name = current.text().split(" (")[0]  # Extract name before category
        self.current_collection = collection_name
        collection_data = self.existing_collections.get(collection_name, {})
        
        # Populate details form
        self.name_input.setText(collection_name)
        self.category_input.setCurrentText(collection_data.get("category", "Custom"))
        self.description_input.setText(collection_data.get("description", ""))
        
        # Populate assets list
        self.assets_list.clear()
        assets = collection_data.get("assets", [])
        for asset in assets:
            self.assets_list.addItem(asset)
            
        # Set auto-include options
        self.auto_include_by_tag.setChecked(collection_data.get("auto_include_by_tag", False))
        self.auto_include_by_type.setChecked(collection_data.get("auto_include_by_type", False))
        self.auto_include_by_folder.setChecked(collection_data.get("auto_include_by_folder", False))
        
        # Update asset count
        self._update_asset_count()
        
        # Enable details panel
        self.details_group.setEnabled(True)
        self.modified = False
        self._update_save_status()
        
    def _create_new_collection(self) -> None:
        """Create a new collection - Single Responsibility"""
        name, ok = QInputDialog.getText(self, "New Collection", "Collection name:")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        if name in self.existing_collections:
            QMessageBox.warning(self, "Duplicate Name", 
                              f"A collection named '{name}' already exists.")
            return
            
        # Create new collection with default data
        new_collection = {
            "category": "Custom",
            "description": "",
            "assets": [],
            "auto_include_by_tag": False,
            "auto_include_by_type": False,
            "auto_include_by_folder": False,
            "built_in": False
        }
        
        self.existing_collections[name] = new_collection
        self._populate_collections_list()
        
        # Select the new collection
        for i in range(self.collections_list.count()):
            item = self.collections_list.item(i)
            if item.text().startswith(name):
                self.collections_list.setCurrentItem(item)
                break
                
        self.collection_created.emit(name, new_collection)
        
    def _duplicate_collection(self) -> None:
        """Duplicate the selected collection - Single Responsibility"""
        if not self.current_collection:
            QMessageBox.information(self, "No Selection", "Please select a collection to duplicate.")
            return
            
        name, ok = QInputDialog.getText(self, "Duplicate Collection", 
                                      "New collection name:", 
                                      text=f"{self.current_collection}_copy")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        if name in self.existing_collections:
            QMessageBox.warning(self, "Duplicate Name", 
                              f"A collection named '{name}' already exists.")
            return
            
        # Copy collection data
        original_data = self.existing_collections[self.current_collection].copy()
        original_data["built_in"] = False  # Copies are never built-in
        
        self.existing_collections[name] = original_data
        self._populate_collections_list()
        
        self.collection_created.emit(name, original_data)
        
    def _delete_collection(self) -> None:
        """Delete the selected collection - Single Responsibility"""
        if not self.current_collection:
            QMessageBox.information(self, "No Selection", "Please select a collection to delete.")
            return
            
        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                   f"Are you sure you want to delete the collection '{self.current_collection}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.existing_collections[self.current_collection]
            self.collection_deleted.emit(self.current_collection)
            
            self.current_collection = None
            self.details_group.setEnabled(False)
            self._populate_collections_list()
            
    def _add_assets_to_collection(self) -> None:
        """Add assets to the current collection - Single Responsibility"""
        if not self.current_collection:
            return
            
        # Simulate asset selection dialog
        text, ok = QInputDialog.getText(self, "Add Assets", 
                                      "Enter asset names (comma-separated):")
        if not ok or not text.strip():
            return
            
        assets = [asset.strip() for asset in text.split(",") if asset.strip()]
        
        for asset in assets:
            if asset not in [self.assets_list.item(i).text() 
                           for i in range(self.assets_list.count())]:
                self.assets_list.addItem(asset)
                
        self._update_asset_count()
        self._mark_modified()
        
    def _remove_assets_from_collection(self) -> None:
        """Remove selected assets from collection - Single Responsibility"""
        selected_items = self.assets_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select assets to remove.")
            return
            
        for item in selected_items:
            row = self.assets_list.row(item)
            self.assets_list.takeItem(row)
            
        self._update_asset_count()
        self._mark_modified()
        
    def _clear_collection_assets(self) -> None:
        """Clear all assets from collection - Single Responsibility"""
        if self.assets_list.count() == 0:
            return
            
        reply = QMessageBox.question(self, "Clear Assets", 
                                   "Are you sure you want to remove all assets from this collection?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.assets_list.clear()
            self._update_asset_count()
            self._mark_modified()
            
    def _import_collections(self) -> None:
        """Import collections from file - Single Responsibility"""
        QMessageBox.information(self, "Import Collections", 
                               "Import functionality will be implemented in a future version.\n"
                               "This will allow importing collection definitions from JSON files.")
                               
    def _export_collections(self) -> None:
        """Export collections to file - Single Responsibility"""
        QMessageBox.information(self, "Export Collections", 
                               "Export functionality will be implemented in a future version.\n"
                               "This will allow exporting collection definitions to JSON files.")
                               
    def _mark_modified(self) -> None:
        """Mark the dialog as having unsaved changes - Single Responsibility"""
        self.modified = True
        self.save_btn.setEnabled(True)
        self._update_save_status()
        
    def _update_save_status(self) -> None:
        """Update the save status label - Single Responsibility"""
        if self.modified:
            self.save_status_label.setText("❋ Unsaved changes")
            self.save_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            self.save_status_label.setText("✓ All changes saved")
            self.save_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            
    def _update_asset_count(self) -> None:
        """Update the asset count label - Single Responsibility"""
        count = self.assets_list.count()
        self.asset_count_label.setText(f"{count} asset{'s' if count != 1 else ''}")
        
    def _update_stats_label(self) -> None:
        """Update the collections statistics label - Single Responsibility"""
        total = len(self.existing_collections)
        visible = sum(1 for i in range(self.collections_list.count()) 
                     if not self.collections_list.item(i).isHidden())
        
        if visible == total:
            self.stats_label.setText(f"{total} collection{'s' if total != 1 else ''} loaded")
        else:
            self.stats_label.setText(f"{visible} of {total} collection{'s' if total != 1 else ''} shown")
            
    def _save_current_collection(self) -> None:
        """Save the current collection data - Single Responsibility"""
        if not self.current_collection or not self.modified:
            return
            
        # Get current form data
        collection_data = {
            "category": self.category_input.currentText(),
            "description": self.description_input.toPlainText(),
            "assets": [self.assets_list.item(i).text() 
                      for i in range(self.assets_list.count())],
            "auto_include_by_tag": self.auto_include_by_tag.isChecked(),
            "auto_include_by_type": self.auto_include_by_type.isChecked(),
            "auto_include_by_folder": self.auto_include_by_folder.isChecked(),
            "built_in": self.existing_collections[self.current_collection].get("built_in", False)
        }
        
        # Check if name changed
        new_name = self.name_input.text().strip()
        if new_name != self.current_collection:
            if new_name in self.existing_collections:
                QMessageBox.warning(self, "Duplicate Name", 
                                  f"A collection named '{new_name}' already exists.")
                return
                
            # Rename collection
            del self.existing_collections[self.current_collection]
            self.existing_collections[new_name] = collection_data
            self.current_collection = new_name
        else:
            self.existing_collections[self.current_collection] = collection_data
            
        self.collection_updated.emit(self.current_collection, collection_data)
        
    def _save_changes(self) -> None:
        """Save all changes - Single Responsibility"""
        self._save_current_collection()
        self.modified = False
        self.save_btn.setEnabled(False)
        self._update_save_status()
        self._populate_collections_list()
        
    def _close_dialog(self) -> None:
        """Close the dialog with confirmation if needed - Single Responsibility"""
        if self.modified:
            reply = QMessageBox.question(self, "Unsaved Changes", 
                                       "You have unsaved changes. Do you want to save them before closing?",
                                       QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                       QMessageBox.StandardButton.Save)
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_changes()
                self.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                self.reject()
            # Cancel - do nothing
        else:
            self.accept()
            
    def closeEvent(self, event) -> None:
        """Handle dialog close event - Single Responsibility"""
        if self.modified:
            reply = QMessageBox.question(self, "Unsaved Changes", 
                                       "You have unsaved changes. Do you want to save them before closing?",
                                       QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                       QMessageBox.StandardButton.Save)
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_changes()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
