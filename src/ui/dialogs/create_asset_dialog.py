# -*- coding: utf-8 -*-
"""
Create Asset Dialog
Dialog for creating new assets from the current Maya scene

Author: Mike Stumbo
"""

from typing import Dict, Any, Optional

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
        QLineEdit, QTextEdit, QComboBox, QCheckBox, QPushButton,
        QLabel, QMessageBox, QGroupBox, QSpacerItem, QSizePolicy
    )
    from PySide6.QtCore import Qt
except ImportError as e:
    print(f"❌ PySide6 import failed: {e}")
    raise


class CreateAssetDialog(QDialog):
    """Dialog for creating new assets from current Maya scene"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Asset")
        self.setModal(True)
        self.resize(400, 500)
        
        self._asset_data: Optional[Dict[str, Any]] = None
        
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Asset Information Group
        info_group = QGroupBox("Asset Information")
        info_layout = QFormLayout(info_group)
        
        # Asset Name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter asset name...")
        info_layout.addRow("Name*:", self._name_edit)
        
        # Asset Type/Category
        self._category_combo = QComboBox()
        self._category_combo.addItems([
            "General",
            "Characters",
            "Props",
            "Environments",
            "Vehicles",
            "Textures",
            "Materials",
            "Rigs",
            "Animations"
        ])
        info_layout.addRow("Category:", self._category_combo)
        
        # Description
        self._description_edit = QTextEdit()
        self._description_edit.setPlaceholderText("Enter asset description...")
        self._description_edit.setMaximumHeight(80)
        info_layout.addRow("Description:", self._description_edit)
        
        # Tags
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("Enter tags separated by commas...")
        info_layout.addRow("Tags:", self._tags_edit)
        
        layout.addWidget(info_group)
        
        # Export Options Group
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout(export_group)
        
        self._export_selected_check = QCheckBox("Export selected objects only")
        self._export_selected_check.setChecked(True)
        export_layout.addWidget(self._export_selected_check)
        
        self._generate_thumbnail_check = QCheckBox("Generate thumbnail")
        self._generate_thumbnail_check.setChecked(True)
        export_layout.addWidget(self._generate_thumbnail_check)
        
        self._include_materials_check = QCheckBox("Include materials")
        self._include_materials_check.setChecked(True)
        export_layout.addWidget(self._include_materials_check)
        
        layout.addWidget(export_group)
        
        # Spacer
        spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(spacer)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._create_button = QPushButton("Create Asset")
        self._create_button.setDefault(True)
        
        self._cancel_button = QPushButton("Cancel")
        
        button_layout.addStretch()
        button_layout.addWidget(self._create_button)
        button_layout.addWidget(self._cancel_button)
        
        layout.addLayout(button_layout)
    
    def _setup_connections(self) -> None:
        """Setup signal connections"""
        self._create_button.clicked.connect(self._on_create_clicked)
        self._cancel_button.clicked.connect(self.reject)
        self._name_edit.textChanged.connect(self._validate_input)
        
        # Initial validation
        self._validate_input()
    
    def _validate_input(self) -> None:
        """Validate user input and enable/disable create button"""
        name = self._name_edit.text().strip()
        self._create_button.setEnabled(bool(name))
    
    def _on_create_clicked(self) -> None:
        """Handle create button click"""
        name = self._name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Asset name is required.")
            return
        
        # Prepare asset data
        tags = []
        tags_text = self._tags_edit.text().strip()
        if tags_text:
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        
        self._asset_data = {
            'name': name,
            'category': self._category_combo.currentText(),
            'description': self._description_edit.toPlainText().strip(),
            'tags': tags,
            'export_selected': self._export_selected_check.isChecked(),
            'generate_thumbnail': self._generate_thumbnail_check.isChecked(),
            'include_materials': self._include_materials_check.isChecked()
        }
        
        self.accept()
    
    def get_asset_data(self) -> Optional[Dict[str, Any]]:
        """Get the asset data from the dialog"""
        return self._asset_data
