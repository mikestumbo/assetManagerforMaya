# -*- coding: utf-8 -*-
"""
Color Coding Keychart Widget
Visual legend showing asset type colors for easy reference

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Dict, Optional
from pathlib import Path

# PySide6 for Maya 2022+
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
PYSIDE_VERSION = "PySide6"# Import the unified theme
from ..theme import UITheme


class ColorCodingKeychartWidget(QWidget):  # type: ignore
    """
    Color Coding Keychart Widget - Single Responsibility for visual color legend
    Shows colored squares with asset type names for quick reference
    """
    
    color_coding_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Default color scheme - matches ColorCodingManagerDialog
        self._color_scheme: Dict[str, QColor] = {
            "Maya Scene": QColor(255, 150, 50),     # Orange
            "3D Model": QColor(150, 255, 150),      # Green  
            "Image": QColor(100, 150, 255),         # Blue
            "Video": QColor(255, 100, 150),         # Pink
            "Material": QColor(200, 100, 255),      # Purple
            "Archive": QColor(150, 150, 150)        # Gray
        }
        
        # Keep references to color swatch widgets for efficient updates
        self._color_swatches: Dict[str, QLabel] = {}
        self._name_labels: Dict[str, QLabel] = {}
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup keychart UI - Single Responsibility"""
        # Apply unified theme styling
        self.setStyleSheet(UITheme.get_dialog_stylesheet())
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Create group box
        self._keychart_group = QGroupBox("Asset Type Colors")
        
        # Create keychart content
        self._create_keychart_content()
        
        layout.addWidget(self._keychart_group)
        
        # Manage colors button
        manage_btn = QPushButton("Manage Colors...")
        manage_btn.setToolTip("Customize asset type colors and create custom types")
        manage_btn.setProperty("accent", True)  # Use theme accent styling
        manage_btn.clicked.connect(self.color_coding_requested.emit)
        layout.addWidget(manage_btn)
        
        # Set fixed height to prevent overlapping and make stationary
        self.setFixedHeight(260)  # Increased height to prevent color square overlap
        self.setMaximumWidth(340)  # Expanded width to fit "Maya Scene" and "3D Model" text
    
    def _create_keychart_content(self) -> None:
        """Create the color keychart content - Single Responsibility"""
        keychart_layout = QVBoxLayout(self._keychart_group)
        keychart_layout.setContentsMargins(6, 12, 6, 8)  # Increased bottom margin
        keychart_layout.setSpacing(8)  # Increased spacing between elements
        
        # Create grid for color swatches
        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add color swatches in a 2-column layout
        row = 0
        col = 0
        for asset_type, color in self._color_scheme.items():
            # Create color swatch
            color_swatch = QLabel()
            color_swatch.setFixedSize(14, 14)
            color_swatch.setStyleSheet(UITheme.get_color_preview_style(color.name()))
            
            # Create type name label
            name_label = QLabel(asset_type)
            name_label.setFont(QFont("Arial", 9))
            
            # Store references for efficient updates
            self._color_swatches[asset_type] = color_swatch
            self._name_labels[asset_type] = name_label
            
            # Add to grid
            grid_layout.addWidget(color_swatch, row, col * 2, Qt.AlignmentFlag.AlignLeft)
            grid_layout.addWidget(name_label, row, col * 2 + 1, Qt.AlignmentFlag.AlignLeft)
            
            col += 1
            if col >= 2:  # 2 columns
                col = 0
                row += 1
        
        keychart_layout.addLayout(grid_layout)
        
        # Add some spacing before separator
        keychart_layout.addSpacing(8)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #bdc3c7;")
        keychart_layout.addWidget(separator)
        
        # Add spacing after separator
        keychart_layout.addSpacing(4)
        
        # Add info label
        info_label = QLabel("Colors help identify asset types")
        info_label.setFont(QFont("Arial", 8))
        info_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        keychart_layout.addWidget(info_label)
    
    def update_color_scheme(self, color_scheme: Dict[str, QColor]) -> None:
        """Update the color scheme and refresh display - Single Responsibility"""
        # Validate the color scheme first
        if not self.validate_color_scheme(color_scheme):
            print("Invalid color scheme provided, keeping current scheme")
            return
            
        self._color_scheme = color_scheme.copy()
        self._update_existing_colors()
    
    def _update_existing_colors(self) -> None:
        """Update existing color swatches without recreating widgets - Safer approach"""
        try:
            print(f"🎨 Updating keychart colors for {len(self._color_scheme)} asset types")
            
            # Update existing color swatches with new colors
            for asset_type, color in self._color_scheme.items():
                if asset_type in self._color_swatches:
                    # Update existing swatch color
                    swatch = self._color_swatches[asset_type]
                    swatch.setStyleSheet(UITheme.get_color_preview_style(color.name()))
                    print(f"  ✅ Updated {asset_type}: {color.name()}")
                else:
                    # If new asset type, need full recreation
                    print(f"  🔄 New asset type '{asset_type}' detected, recreating keychart")
                    self._recreate_keychart()
                    return
            
            # Check if any asset types were removed
            existing_types = set(self._color_swatches.keys())
            new_types = set(self._color_scheme.keys())
            if existing_types != new_types:
                # Asset types changed, need full recreation
                removed_types = existing_types - new_types
                print(f"  🔄 Asset types removed {removed_types}, recreating keychart")
                self._recreate_keychart()
            else:
                print("  ✅ Keychart colors updated successfully")
                
        except Exception as e:
            print(f"❌ Error updating colors: {e}")
            # Fallback to full recreation on any error
            self._recreate_keychart()
    
    def _recreate_keychart(self) -> None:
        """Safely recreate the keychart when structure changes - Fallback method"""
        try:
            print("🔄 Recreating keychart layout...")
            
            # Clear widget references
            self._color_swatches.clear()
            self._name_labels.clear()
            
            # Clear layout more safely
            layout = self._keychart_group.layout()
            if layout:
                # Remove widgets from layout first
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        widget = child.widget()
                        widget.setParent(None)  # Immediate removal instead of deleteLater
                    elif child.layout():
                        # Handle nested layouts
                        child_layout = child.layout()
                        while child_layout.count():
                            grandchild = child_layout.takeAt(0)
                            if grandchild.widget():
                                grandchild.widget().setParent(None)
                
                # Delete the layout itself
                layout.setParent(None)
            
            # Recreate the content
            self._create_keychart_content()
            print("✅ Keychart recreated successfully")
            
        except Exception as e:
            print(f"❌ Error recreating keychart: {e}")
    
    def _refresh_keychart(self) -> None:
        """Legacy method - redirects to safer update mechanism"""
        self._update_existing_colors()
    
    def get_color_for_asset_type(self, asset_type: str) -> QColor:
        """Get color for specific asset type - Single Responsibility"""
        return self._color_scheme.get(asset_type, QColor(150, 150, 150))  # Default gray
    
    def get_all_colors(self) -> Dict[str, QColor]:
        """Get all asset type colors - Single Responsibility"""
        return self._color_scheme.copy()
    
    def validate_color_scheme(self, color_scheme: Dict[str, QColor]) -> bool:
        """Validate that a color scheme is properly formatted - Single Responsibility"""
        if not color_scheme:
            return False
        
        # Check that all values are QColor objects
        for asset_type, color in color_scheme.items():
            if not isinstance(asset_type, str) or not isinstance(color, QColor):
                return False
            if not color.isValid():
                return False
        
        return True
