# -*- coding: utf-8 -*-
"""
Tag Manager Dialog
Manages asset tags with CRUD operations

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
        QInputDialog, QMessageBox, QLabel, QLineEdit, QTextEdit,
        QGroupBox, QSplitter, QListWidgetItem, QColorDialog
    )
    from PySide6.QtCore import Signal, Qt
    from PySide6.QtGui import QIcon, QColor
except ImportError as e:
    print(f"❌ PySide6 import failed: {e}")
    raise

from pathlib import Path
from typing import List, Dict, Optional


class TagManagerDialog(QDialog):
    """
    Tag Manager Dialog - Single Responsibility for tag management
    Provides CRUD operations for asset tags
    """
    
    # Signal emitted when tags are modified
    tags_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Tags data - will be loaded from parent widget
        # Format: {"tag_name": {"color": "#RRGGBB", "description": "...", "predefined": bool}}
        self._tags = {}
        
        self._setup_ui()
        # Don't populate yet - wait for set_tags() to be called by parent
    
    def _setup_ui(self) -> None:
        """Setup dialog UI - Single Responsibility"""
        self.setWindowTitle("Tag Manager")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel("Asset Tag Management")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #cccccc; padding: 5px;")
        layout.addWidget(title_label)
        
        # Create splitter for tags list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Tags list
        left_panel = self._create_tags_list_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Tag details
        right_panel = self._create_tag_details_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([300, 400])
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_tags_list_panel(self) -> QGroupBox:
        """Create left panel with tags list and controls - Single Responsibility"""
        group = QGroupBox("Tags")
        layout = QVBoxLayout(group)
        
        # Tags list
        self._tags_list = QListWidget()
        self._tags_list.itemSelectionChanged.connect(self._on_tag_selection_changed)
        layout.addWidget(self._tags_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Tag")
        add_btn.clicked.connect(self._on_add_tag)
        button_layout.addWidget(add_btn)
        
        self._edit_btn = QPushButton("Edit Tag")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit_tag)
        button_layout.addWidget(self._edit_btn)
        
        self._delete_btn = QPushButton("Delete Tag")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_tag)
        button_layout.addWidget(self._delete_btn)
        
        layout.addLayout(button_layout)
        
        return group
    
    def _create_tag_details_panel(self) -> QGroupBox:
        """Create right panel with tag details - Single Responsibility"""
        group = QGroupBox("Tag Details")
        layout = QVBoxLayout(group)
        
        # Tag name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Tag name...")
        self._name_edit.textChanged.connect(self._on_tag_details_changed)
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self._name_edit)
        
        # Description
        self._description_edit = QTextEdit()
        self._description_edit.setPlaceholderText("Tag description...")
        self._description_edit.setMaximumHeight(100)
        self._description_edit.textChanged.connect(self._on_tag_details_changed)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self._description_edit)
        
        # Color section with label and buttons
        layout.addWidget(QLabel("Color:"))
        
        # Color display and edit controls
        color_layout = QHBoxLayout()
        
        self._color_edit = QLineEdit()
        self._color_edit.setPlaceholderText("#FF0000")
        self._color_edit.textChanged.connect(self._on_tag_details_changed)
        self._color_edit.setMaximumWidth(120)
        color_layout.addWidget(self._color_edit)
        
        # Edit Color button
        self._edit_color_btn = QPushButton("Edit Color")
        self._edit_color_btn.setEnabled(False)
        self._edit_color_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self._edit_color_btn.clicked.connect(self._on_edit_color)
        color_layout.addWidget(self._edit_color_btn)
        
        # Reset to Default button
        self._reset_color_btn = QPushButton("Reset to Default")
        self._reset_color_btn.setEnabled(False)
        self._reset_color_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self._reset_color_btn.clicked.connect(self._on_reset_color)
        color_layout.addWidget(self._reset_color_btn)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # Save button
        self._save_btn = QPushButton("Save Changes")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_tag_details)
        layout.addWidget(self._save_btn)
        
        layout.addStretch()
        
        return group
    
    def _populate_tags(self) -> None:
        """Populate tags list - Single Responsibility"""
        self._tags_list.clear()
        for tag_name in sorted(self._tags.keys()):
            item = QListWidgetItem(tag_name)
            self._tags_list.addItem(item)
    
    def _on_tag_selection_changed(self) -> None:
        """Handle tag selection change - Single Responsibility"""
        current_item = self._tags_list.currentItem()
        has_selection = current_item is not None
        
        # Enable/disable buttons
        self._edit_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        self._edit_color_btn.setEnabled(has_selection)
        self._reset_color_btn.setEnabled(has_selection)
        
        if has_selection:
            tag_name = current_item.text()
            tag_data = self._tags.get(tag_name, {})
            
            # Update details panel
            self._name_edit.setText(tag_name)
            self._description_edit.setPlainText(tag_data.get("description", ""))
            self._color_edit.setText(tag_data.get("color", "#FFFFFF"))
            
            self._save_btn.setEnabled(False)  # No changes yet
        else:
            # Clear details panel
            self._name_edit.clear()
            self._description_edit.clear()
            self._color_edit.clear()
            self._save_btn.setEnabled(False)
    
    def _on_tag_details_changed(self) -> None:
        """Handle tag details change - Single Responsibility"""
        # Enable save button when details are modified
        self._save_btn.setEnabled(True)
    
    def _on_add_tag(self) -> None:
        """Add new tag - Single Responsibility"""
        text, ok = QInputDialog.getText(self, 'Add Tag', 'Tag name:')
        if ok and text.strip():
            tag_name = text.strip()
            if tag_name in self._tags:
                QMessageBox.warning(self, "Duplicate Tag", f"Tag '{tag_name}' already exists.")
                return
            
            print(f"🏷️  Tag Manager: Creating new custom tag '{tag_name}'")
            
            # Add new tag with default values
            self._tags[tag_name] = {
                "color": "#CCCCCC",
                "description": f"Custom tag: {tag_name}",
                "predefined": False  # Mark as custom tag
            }
            
            # Refresh list and select new tag
            self._populate_tags()
            items = self._tags_list.findItems(tag_name, Qt.MatchFlag.MatchExactly)
            if items:
                self._tags_list.setCurrentItem(items[0])
            
            print(f"🏷️  ✨ Custom tag '{tag_name}' added to Tag Manager")
            self.tags_changed.emit()
    
    def _on_edit_tag(self) -> None:
        """Edit selected tag - Single Responsibility"""
        current_item = self._tags_list.currentItem()
        if not current_item:
            return
        
        old_name = current_item.text()
        new_name, ok = QInputDialog.getText(self, 'Edit Tag', 'Tag name:', text=old_name)
        
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            
            if new_name in self._tags:
                QMessageBox.warning(self, "Duplicate Tag", f"Tag '{new_name}' already exists.")
                return
            
            # Rename tag
            tag_data = self._tags.pop(old_name)
            self._tags[new_name] = tag_data
            
            # Refresh list and select renamed tag
            self._populate_tags()
            items = self._tags_list.findItems(new_name, Qt.MatchFlag.MatchExactly)
            if items:
                self._tags_list.setCurrentItem(items[0])
            
            self.tags_changed.emit()
    
    def _on_delete_tag(self) -> None:
        """Delete selected tag - Single Responsibility"""
        current_item = self._tags_list.currentItem()
        if not current_item:
            return
        
        tag_name = current_item.text()
        tag_data = self._tags.get(tag_name, {})
        
        # Prevent deletion of predefined tags
        if tag_data.get("predefined", False):
            QMessageBox.warning(
                self, "Cannot Delete",
                f"Cannot delete predefined tag '{tag_name}'.\n\n"
                "Predefined tags are part of the core system."
            )
            return
        
        reply = QMessageBox.question(
            self, "Delete Tag", 
            f"Are you sure you want to delete tag '{tag_name}'?\n\n"
            "This will remove the tag from the global registry.\n"
            "Assets using this tag will keep it until you manually remove it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove tag
            if tag_name in self._tags:
                del self._tags[tag_name]
                print(f"🏷️  Tag Manager: Deleted custom tag '{tag_name}'")
            
            # Refresh list
            self._populate_tags()
            self.tags_changed.emit()
    
    def _on_save_tag_details(self) -> None:
        """Save tag details changes - Single Responsibility"""
        current_item = self._tags_list.currentItem()
        if not current_item:
            return
        
        tag_name = current_item.text()
        if tag_name not in self._tags:
            return
        
        # Update tag data
        self._tags[tag_name]["description"] = self._description_edit.toPlainText()
        self._tags[tag_name]["color"] = self._color_edit.text() or "#FFFFFF"
        
        # Disable save button
        self._save_btn.setEnabled(False)
        
        self.tags_changed.emit()
        QMessageBox.information(self, "Saved", f"Tag '{tag_name}' details saved successfully.")
    
    def _on_edit_color(self) -> None:
        """Open color picker to edit tag color - Single Responsibility"""
        current_item = self._tags_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a tag to edit its color.")
            return
        
        tag_name = current_item.text()
        current_color_hex = self._color_edit.text() or "#FFFFFF"
        
        # Parse current color
        try:
            current_color = QColor(current_color_hex)
        except:
            current_color = QColor("#FFFFFF")
        
        # Open color dialog
        color = QColorDialog.getColor(current_color, self, f"Choose Color for Tag '{tag_name}'")
        
        if color.isValid():
            # Update color field
            hex_color = color.name().upper()
            self._color_edit.setText(hex_color)
            
            # Mark as changed
            self._on_tag_details_changed()
            
            print(f"🎨 Tag '{tag_name}' color changed to {hex_color}")
    
    def _on_reset_color(self) -> None:
        """Reset tag color to default - Single Responsibility"""
        current_item = self._tags_list.currentItem()
        if not current_item:
            return
        
        tag_name = current_item.text()
        
        reply = QMessageBox.question(
            self, 
            "Reset Color",
            f"Reset color for tag '{tag_name}' to default (#CCCCCC)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._color_edit.setText("#CCCCCC")
            self._on_tag_details_changed()
            print(f"🎨 Tag '{tag_name}' color reset to default")
    
    def get_tags(self) -> Dict[str, Dict]:
        """Get current tags data - Single Responsibility"""
        return self._tags.copy()
    
    def set_tags(self, tags: Dict[str, Dict]) -> None:
        """Set tags data and populate the list - Single Responsibility"""
        self._tags = tags.copy()
        print(f"🏷️  Tag Manager: Loaded {len(self._tags)} tags from parent")
        predefined_count = sum(1 for t in self._tags.values() if t.get("predefined", False))
        custom_count = len(self._tags) - predefined_count
        print(f"🏷️  ({predefined_count} predefined, {custom_count} custom)")
        self._populate_tags()