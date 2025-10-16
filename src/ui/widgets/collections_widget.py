"""
Collections Widget for Asset Manager v1.3.0

This module provides a dedicated widget for displaying and managing asset collections
within the Asset Library. It follows Clean Code principles and implements SOLID
design patterns for maintainable and extensible collection display.

Author: Asset Manager Development Team  
Version: 1.3.0
License: MIT
"""

from typing import List, Dict, Optional, Any
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QComboBox, QSplitter, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QInputDialog, QFrame, QScrollArea, QTabWidget
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor

# Import theme for consistent styling
from ..theme import UITheme


class CollectionsDisplayWidget(QWidget):
    """
    Professional Collections Display Widget following Clean Code principles.
    Implements Single Responsibility Principle for collection asset display.
    
    Features:
    - Display collections in organized tabs
    - Show assets within each collection  
    - Collection switching and navigation
    - Asset thumbnail display with metadata
    - Integration with Collection Manager
    """
    
    # Signals for communication - Single Responsibility
    collection_selected = Signal(str)  # collection_name
    asset_selected = Signal(str)  # asset_path
    asset_double_clicked = Signal(str)  # asset_path 
    collection_manager_requested = Signal()
    collection_created = Signal(str)  # collection_name - emitted when new collection is created
    
    def __init__(self, parent=None):
        """
        Initialize Collections Display Widget with professional styling.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.collections_data: Dict[str, Any] = {}
        self.current_collection: Optional[str] = None
        
        self._setup_ui()
        self._load_sample_collections()  # Temporary sample data
        
    def _setup_ui(self) -> None:
        """Setup the user interface - Single Responsibility"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Header section
        self._create_header_section(layout)
        
        # Main content area
        self._create_content_area(layout)
        
        # Footer controls
        self._create_footer_section(layout)
        
    def _create_header_section(self, parent_layout: QVBoxLayout) -> None:
        """Create header with collection selector - Single Responsibility"""
        header_frame = QFrame()
        header_frame.setProperty("panel", True)
        header_layout = QVBoxLayout(header_frame)
        
        # Title
        title_label = QLabel("Asset Collections")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #cccccc; padding: 4px;")
        header_layout.addWidget(title_label)
        
        # Collection selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Collection:"))
        
        self.collection_selector = QComboBox()
        self.collection_selector.setMinimumHeight(32)
        self.collection_selector.setToolTip("Select a collection to view its assets")
        self.collection_selector.currentTextChanged.connect(self._on_collection_changed)
        selector_layout.addWidget(self.collection_selector)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(80)
        refresh_btn.setToolTip("Refresh Collection Tabs and Update Asset Lists")
        refresh_btn.clicked.connect(self._refresh_collections)
        selector_layout.addWidget(refresh_btn)
        
        header_layout.addLayout(selector_layout)
        parent_layout.addWidget(header_frame)
        
    def _create_content_area(self, parent_layout: QVBoxLayout) -> None:
        """Create main content area with asset display - Single Responsibility"""
        # Splitter for collection info and asset list
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Collection info panel
        self.info_panel = self._create_info_panel()
        splitter.addWidget(self.info_panel)
        
        # Asset list panel
        self.asset_list = self._create_asset_list()
        splitter.addWidget(self.asset_list)
        
        # Set splitter proportions (30% info, 70% assets)
        splitter.setSizes([200, 500])
        
        parent_layout.addWidget(splitter, 1)  # Take most space
        
    def _create_info_panel(self) -> QWidget:
        """Create collection information panel - Single Responsibility"""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(8, 8, 8, 8)
        
        # Collection name and description
        self.collection_name_label = QLabel("No Collection Selected")
        self.collection_name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.collection_name_label.setStyleSheet("color: #ffffff; padding: 4px;")
        info_layout.addWidget(self.collection_name_label)
        
        self.collection_desc_label = QLabel("Select a collection to view its assets and details.")
        self.collection_desc_label.setWordWrap(True)
        self.collection_desc_label.setStyleSheet("color: #999999; font-style: italic; padding: 4px;")
        info_layout.addWidget(self.collection_desc_label)
        
        # Statistics
        self.stats_label = QLabel("Assets: 0 | Created: --")
        self.stats_label.setStyleSheet("color: #666666; font-size: 11px; padding: 4px;")
        info_layout.addWidget(self.stats_label)
        
        info_layout.addStretch()
        return info_widget
        
    def _create_asset_list(self) -> QListWidget:
        """Create asset list with thumbnails - Single Responsibility"""
        asset_list = QListWidget()
        
        # Configure for thumbnail display
        asset_list.setViewMode(QListWidget.ViewMode.IconMode)
        asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        asset_list.setUniformItemSizes(True)
        asset_list.setMovement(QListWidget.Movement.Static)
        
        # Thumbnail sizing
        thumbnail_size = 128
        grid_size = thumbnail_size + 50
        asset_list.setIconSize(QSize(thumbnail_size, thumbnail_size))
        asset_list.setGridSize(QSize(grid_size, grid_size))
        
        # Styling
        asset_list.setStyleSheet("""
            QListWidget::item {
                border: 2px solid transparent;
                padding: 4px;
                margin: 2px;
                border-radius: 6px;
                background-color: rgba(60, 60, 60, 100);
            }
            QListWidget::item:hover {
                border: 2px solid rgba(255, 255, 255, 120);
                background-color: rgba(80, 80, 80, 120);
            }
            QListWidget::item:selected {
                border: 2px solid #0078d4;
                background-color: rgba(0, 120, 212, 80);
            }
        """)
        
        # Connect signals
        asset_list.currentItemChanged.connect(self._on_asset_selected)
        asset_list.itemDoubleClicked.connect(self._on_asset_double_clicked)
        
        return asset_list
        
    def _create_footer_section(self, parent_layout: QVBoxLayout) -> None:
        """Create footer with action buttons - Single Responsibility"""
        footer_layout = QHBoxLayout()
        
        # Collection management buttons
        manage_btn = QPushButton("Manage Collections...")
        manage_btn.setToolTip("Open Collection Manager to create, edit, and organize collections")
        manage_btn.clicked.connect(self.collection_manager_requested.emit)
        footer_layout.addWidget(manage_btn)
        
        footer_layout.addStretch()
        
        # Asset count display
        self.asset_count_label = QLabel("0 assets")
        self.asset_count_label.setStyleSheet("color: #666666; font-size: 11px;")
        footer_layout.addWidget(self.asset_count_label)
        
        parent_layout.addLayout(footer_layout)
        
    def _load_sample_collections(self) -> None:
        """Load sample collections for demonstration - Single Responsibility"""
        sample_collections = {
            "Characters": {
                "description": "Character models and rigs for animation projects",
                "assets": ["Hero_Character.ma", "Villain_Character.ma", "NPC_Guard.ma"],
                "created": "2024-01-15",
                "category": "Characters",
                "asset_count": 3
            },
            "Environments": {
                "description": "Environment scenes and props for level design", 
                "assets": ["Forest_Scene.ma", "Castle_Interior.ma", "Desert_Landscape.ma", "Ocean_Vista.ma"],
                "created": "2024-01-20",
                "category": "Environments", 
                "asset_count": 4
            },
            "Props": {
                "description": "Miscellaneous props and objects for scene decoration",
                "assets": ["Sword_Medieval.ma", "Shield_Knight.ma", "Treasure_Chest.ma", "Magic_Staff.ma", "Ancient_Book.ma"],
                "created": "2024-01-25", 
                "category": "Props",
                "asset_count": 5
            },
            "Vehicles": {
                "description": "Transportation and mechanical assets",
                "assets": ["Spaceship_Fighter.ma", "Motorcycle_Racing.ma"],
                "created": "2024-02-01",
                "category": "Vehicles",
                "asset_count": 2
            }
        }
        
        self.collections_data = sample_collections
        self._populate_collection_selector()
        
    def _populate_collection_selector(self) -> None:
        """Populate collection selector dropdown - Single Responsibility"""
        self.collection_selector.clear()
        
        if not self.collections_data:
            self.collection_selector.addItem("No collections available")
            # Always add New Collection option even when no collections exist
            self.collection_selector.addItem("New Collection...", "CREATE_NEW")
            return
            
        self.collection_selector.addItem("Select a collection...")
        
        # Add New Collection option at the top for easy access
        self.collection_selector.addItem("New Collection...", "CREATE_NEW")
        
        # Add separator line for visual clarity
        self.collection_selector.insertSeparator(2)
        
        for collection_name in sorted(self.collections_data.keys()):
            asset_count = len(self.collections_data[collection_name].get("assets", []))
            display_text = f"{collection_name} ({asset_count} assets)"
            self.collection_selector.addItem(display_text, collection_name)
            
    def _on_collection_changed(self, text: str) -> None:
        """Handle collection selection change - Single Responsibility"""
        if text == "Select a collection..." or text == "No collections available":
            self._clear_display()
            return
            
        # Handle New Collection creation
        collection_data = self.collection_selector.currentData()
        if collection_data == "CREATE_NEW":
            self._create_new_collection()
            return
            
        # Extract collection name from display text
        collection_name = self.collection_selector.currentData()
        if collection_name and collection_name in self.collections_data:
            self.current_collection = collection_name
            self._display_collection(collection_name)
            self.collection_selected.emit(collection_name)
            
    def _create_new_collection(self) -> None:
        """Create a new collection - Single Responsibility"""
        # Prompt user for collection name
        collection_name, ok = QInputDialog.getText(
            self, 
            "New Collection", 
            "Enter collection name:",
            text="My Collection"
        )
        
        if not ok or not collection_name.strip():
            # User cancelled or entered empty name - reset dropdown to previous selection
            self._reset_dropdown_selection()
            return
            
        collection_name = collection_name.strip()
        
        # Validate collection name
        if collection_name in self.collections_data:
            QMessageBox.warning(
                self,
                "Collection Exists", 
                f"A collection named '{collection_name}' already exists.\nPlease choose a different name."
            )
            self._reset_dropdown_selection()
            return
            
        # Prompt for description (optional)
        description, ok = QInputDialog.getText(
            self,
            "Collection Description",
            f"Enter description for '{collection_name}' (optional):",
            text="A new asset collection"
        )
        
        if not ok:
            description = "A new asset collection"
        
        # Create new collection data structure
        new_collection = {
            "description": description.strip() or "A new asset collection",
            "created": "2025-09-06",  # Current date
            "assets": [],  # Empty initially
            "tags": ["user-created"],
            "category": "user"
        }
        
        # Add to collections data
        self.collections_data[collection_name] = new_collection
        
        # Refresh dropdown to include new collection
        self._populate_collection_selector()
        
        # Select the newly created collection
        self._select_collection_in_dropdown(collection_name)
        
        # Emit signal to notify other components
        self.collection_created.emit(collection_name)
        
        # Show success message
        QMessageBox.information(
            self,
            "Collection Created",
            f"Collection '{collection_name}' has been created successfully.\n\nYou can now add assets to this collection."
        )
        
    def _reset_dropdown_selection(self) -> None:
        """Reset dropdown to previous valid selection - Single Responsibility"""
        if self.current_collection and self.current_collection in self.collections_data:
            self._select_collection_in_dropdown(self.current_collection)
        else:
            self.collection_selector.setCurrentIndex(0)  # "Select a collection..."
            
    def _select_collection_in_dropdown(self, collection_name: str) -> None:
        """Select a specific collection in the dropdown - Single Responsibility"""
        for i in range(self.collection_selector.count()):
            if self.collection_selector.itemData(i) == collection_name:
                self.collection_selector.setCurrentIndex(i)
                break
            
    def _display_collection(self, collection_name: str) -> None:
        """Display the selected collection - Single Responsibility"""
        if collection_name not in self.collections_data:
            return
            
        collection_data = self.collections_data[collection_name]
        
        # Update info panel
        self.collection_name_label.setText(collection_name)
        description = collection_data.get("description", "No description available")
        self.collection_desc_label.setText(description)
        
        created_date = collection_data.get("created", "Unknown")
        asset_count = len(collection_data.get("assets", []))
        self.stats_label.setText(f"Assets: {asset_count} | Created: {created_date}")
        
        # Populate asset list
        self._populate_asset_list(collection_data.get("assets", []))
        
        # Update footer count
        self.asset_count_label.setText(f"{asset_count} assets")
        
    def _populate_asset_list(self, asset_names: List[str]) -> None:
        """Populate asset list with thumbnails - Single Responsibility"""
        self.asset_list.clear()
        
        if not asset_names:
            # Add placeholder item
            placeholder_item = QListWidgetItem("📦 No assets in this collection")
            placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            self.asset_list.addItem(placeholder_item)
            return
            
        for asset_name in asset_names:
            item = QListWidgetItem(asset_name)
            
            # Create placeholder icon
            icon = self._create_placeholder_icon(asset_name)
            item.setIcon(QIcon(icon))
            
            # Store full asset path as data
            asset_path = f"/project/assets/{asset_name}"  # Placeholder path
            item.setData(Qt.ItemDataRole.UserRole, asset_path)
            
            self.asset_list.addItem(item)
            
    def _create_placeholder_icon(self, asset_name: str) -> QPixmap:
        """Create placeholder thumbnail icon - Single Responsibility"""
        size = 128
        pixmap = QPixmap(size, size)
        
        # Determine color based on asset type
        if asset_name.endswith(".ma"):
            color = QColor(100, 150, 200)  # Blue for Maya files
        else:
            color = QColor(150, 150, 150)  # Gray for others
            
        pixmap.fill(color)
        
        # Draw text overlay
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # Asset type indicator
        if asset_name.endswith(".ma"):
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Maya\nScene")
        else:
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Asset")
            
        painter.end()
        return pixmap
        
    def _clear_display(self) -> None:
        """Clear the display when no collection is selected - Single Responsibility"""
        self.current_collection = None
        self.collection_name_label.setText("No Collection Selected")
        self.collection_desc_label.setText("Select a collection to view its assets and details.")
        self.stats_label.setText("Assets: 0 | Created: --")
        self.asset_count_label.setText("0 assets")
        
        self.asset_list.clear()
        placeholder_item = QListWidgetItem("📋 Select a collection from the dropdown above")
        placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.asset_list.addItem(placeholder_item)
        
    def _on_asset_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle asset selection change - Single Responsibility"""
        if current and current.data(Qt.ItemDataRole.UserRole):
            asset_path = current.data(Qt.ItemDataRole.UserRole)
            self.asset_selected.emit(asset_path)
            
    def _on_asset_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle asset double-click for import - Single Responsibility"""
        if item and item.data(Qt.ItemDataRole.UserRole):
            asset_path = item.data(Qt.ItemDataRole.UserRole)
            self.asset_double_clicked.emit(asset_path)
            
    def _refresh_collections(self) -> None:
        """Refresh collections display - Single Responsibility"""
        # In a real implementation, this would reload from the collection manager
        self._populate_collection_selector()
        QMessageBox.information(self, "Collections Refreshed", 
                              f"Refreshed {len(self.collections_data)} collections")
        
    def update_collections(self, collections_data: Dict[str, Any]) -> None:
        """Update collections data from external source - Single Responsibility"""
        self.collections_data = collections_data
        self._populate_collection_selector()
        
        # If current collection no longer exists, clear display
        if self.current_collection and self.current_collection not in collections_data:
            self._clear_display()
            
    def get_current_collection(self) -> Optional[str]:
        """Get currently selected collection name - Single Responsibility"""
        return self.current_collection
        
    def select_collection(self, collection_name: str) -> bool:
        """Programmatically select a collection - Single Responsibility"""
        if collection_name not in self.collections_data:
            return False
            
        # Find and select the item in combobox
        for i in range(self.collection_selector.count()):
            if self.collection_selector.itemData(i) == collection_name:
                self.collection_selector.setCurrentIndex(i)
                return True
        return False
