# -*- coding: utf-8 -*-
"""
Color Coding Manager Dialog
Professional asset color management interface

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Dict, List, Optional
from pathlib import Path

# PySide6 for Maya 2022+
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QColorDialog, QGroupBox,
    QLineEdit, QTextEdit, QMessageBox, QSplitter, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush
PYSIDE_VERSION = "PySide6"

# Import the unified theme
from ..theme import UITheme


class ColorCodingManagerDialog(QDialog):
    """
    Color Coding Manager Dialog - Single Responsibility for color management
    Follows Clean Architecture with professional UI design
    """
    
    color_scheme_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Color schemes data
        self._color_schemes: Dict[str, Dict[str, QColor]] = {
            "Default": {
                "Maya Scene": QColor(255, 150, 50),     # Orange
                "3D Model": QColor(150, 255, 150),      # Green  
                "Image": QColor(100, 150, 255),         # Blue
                "Video": QColor(255, 100, 150),         # Pink
                "Material": QColor(200, 100, 255),      # Purple
                "Archive": QColor(150, 150, 150)        # Gray
            },
            "Professional": {
                "Maya Scene": QColor(230, 126, 34),     # Professional Orange
                "3D Model": QColor(46, 204, 113),       # Professional Green
                "Image": QColor(52, 152, 219),          # Professional Blue
                "Video": QColor(231, 76, 60),           # Professional Red
                "Material": QColor(155, 89, 182),       # Professional Purple
                "Archive": QColor(149, 165, 166)        # Professional Gray
            },
            "Pastel": {
                "Maya Scene": QColor(255, 205, 178),    # Pastel Orange
                "3D Model": QColor(200, 247, 197),      # Pastel Green
                "Image": QColor(174, 214, 241),         # Pastel Blue
                "Video": QColor(248, 196, 196),         # Pastel Pink
                "Material": QColor(212, 172, 213),      # Pastel Purple
                "Archive": QColor(215, 219, 221)        # Pastel Gray
            }
        }
        
        self._current_scheme = "Default"
        
        self._setup_ui()
        self._load_color_scheme()
    
    def _setup_ui(self) -> None:
        """Setup dialog UI - Single Responsibility"""
        self.setWindowTitle("Color Coding Manager")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)
        
        # Apply unified theme styling
        self.setStyleSheet(UITheme.get_dialog_stylesheet())
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Title
        title_label = QLabel("Asset Color Coding Manager")
        title_label.setProperty("title", True)  # Use theme styling
        main_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("Assign colors to different asset types for better visual organization in the asset library.")
        desc_label.setWordWrap(True)
        desc_label.setProperty("description", True)  # Use theme styling
        main_layout.addWidget(desc_label)
        
        # Splitter for side-by-side layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Color schemes
        left_panel = self._create_schemes_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Asset type colors
        right_panel = self._create_colors_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter sizes
        splitter.setSizes([250, 450])
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        apply_btn = QPushButton("Apply Colors")
        apply_btn.setProperty("accent", True)  # Use theme accent styling
        apply_btn.clicked.connect(self._apply_colors)
        button_layout.addWidget(apply_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def _create_schemes_panel(self) -> QGroupBox:
        """Create color schemes selection panel - Single Responsibility"""
        group = QGroupBox("Color Schemes")
        
        layout = QVBoxLayout(group)
        
        # Scheme list
        self._scheme_list = QListWidget()
        
        for scheme_name in self._color_schemes.keys():
            self._scheme_list.addItem(scheme_name)
        
        self._scheme_list.setCurrentRow(0)
        self._scheme_list.currentItemChanged.connect(self._on_scheme_changed)
        layout.addWidget(self._scheme_list)
        
        # Custom scheme button
        custom_btn = QPushButton("Create Custom Scheme")
        custom_btn.setProperty("danger", True)  # Use theme danger styling
        custom_btn.clicked.connect(self._create_custom_scheme)
        layout.addWidget(custom_btn)
        
        return group
    
    def _create_colors_panel(self) -> QGroupBox:
        """Create asset type colors panel - Single Responsibility"""
        group = QGroupBox("Asset Type Colors")
        
        layout = QVBoxLayout(group)
        
        # Asset type colors list
        self._colors_list = QListWidget()
        # Removed white background styling - use unified theme
        layout.addWidget(self._colors_list)
        
        # Color edit buttons
        btn_layout = QHBoxLayout()
        
        edit_color_btn = QPushButton("Edit Color")
        edit_color_btn.setStyleSheet("""
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
        """)
        edit_color_btn.clicked.connect(self._edit_selected_color)
        btn_layout.addWidget(edit_color_btn)
        
        reset_btn = QPushButton("Reset to Default")
        reset_btn.setStyleSheet("""
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
        """)
        reset_btn.clicked.connect(self._reset_colors)
        btn_layout.addWidget(reset_btn)
        
        layout.addLayout(btn_layout)
        
        return group
    
    def _load_color_scheme(self) -> None:
        """Load and display current color scheme - Single Responsibility"""
        scheme = self._color_schemes[self._current_scheme]
        
        self._colors_list.clear()
        
        for asset_type, color in scheme.items():
            item = QListWidgetItem()
            
            # Create color preview icon
            pixmap = QPixmap(24, 24)
            painter = QPainter(pixmap)
            painter.fillRect(pixmap.rect(), QBrush(color))
            painter.end()
            
            item.setIcon(pixmap)
            item.setText(f"{asset_type}")
            item.setData(Qt.ItemDataRole.UserRole, asset_type)
            
            self._colors_list.addItem(item)
    
    def _on_scheme_changed(self, current_item: Optional[QListWidgetItem], previous_item: Optional[QListWidgetItem]) -> None:
        """Handle color scheme selection change - Single Responsibility"""
        if current_item:
            self._current_scheme = current_item.text()
            self._load_color_scheme()
    
    def _edit_selected_color(self) -> None:
        """Edit color for selected asset type - Single Responsibility"""
        current_item = self._colors_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select an asset type to edit its color.")
            return
        
        asset_type = current_item.data(Qt.ItemDataRole.UserRole)
        current_color = self._color_schemes[self._current_scheme][asset_type]
        
        color = QColorDialog.getColor(current_color, self, f"Choose Color for {asset_type}")
        
        if color.isValid():
            # Update color scheme
            self._color_schemes[self._current_scheme][asset_type] = color
            
            # Refresh display
            self._load_color_scheme()
            
            # Emit signal for real-time updates
            self.color_scheme_changed.emit()
            
            # Select the edited item
            for i in range(self._colors_list.count()):
                item = self._colors_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == asset_type:
                    self._colors_list.setCurrentItem(item)
                    break
    
    def _reset_colors(self) -> None:
        """Reset colors to default scheme - Single Responsibility"""
        reply = QMessageBox.question(
            self, 
            "Reset Colors",
            "Are you sure you want to reset all colors to the default scheme?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._current_scheme = "Default"
            self._scheme_list.setCurrentRow(0)
            self._load_color_scheme()
    
    def _create_custom_scheme(self) -> None:
        """Create custom color scheme - Single Responsibility"""
        QMessageBox.information(
            self,
            "Custom Schemes",
            "Custom color scheme creation will be available in a future version.\n\n"
            "For now, you can modify the existing schemes by editing individual asset type colors."
        )
    
    def _apply_colors(self) -> None:
        """Apply selected color scheme - Single Responsibility"""
        try:
            # Emit signal to notify about color changes
            self.color_scheme_changed.emit()
            
            QMessageBox.information(
                self,
                "Colors Applied", 
                f"Color scheme '{self._current_scheme}' has been applied!\n\n"
                "Asset thumbnails and icons will now use the selected colors."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to apply color scheme:\n{str(e)}"
            )
    
    def get_current_color_scheme(self) -> Dict[str, QColor]:
        """Get the currently selected color scheme - Single Responsibility"""
        return self._color_schemes[self._current_scheme].copy()
    
    def get_color_for_asset_type(self, asset_type: str) -> QColor:
        """Get color for specific asset type - Single Responsibility"""
        scheme = self._color_schemes[self._current_scheme]
        return scheme.get(asset_type, QColor(150, 150, 150))  # Default gray
