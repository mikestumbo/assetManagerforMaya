# -*- coding: utf-8 -*-
"""
New Project Dialog
Project creation interface following Single Responsibility

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Optional
from pathlib import Path

# Import with fallback
# PySide6 for Maya 2022+
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog
PYSIDE_AVAILABLE = True


class NewProjectDialog(QDialog):
    """New Project Dialog - Single Responsibility for project creation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        
        self._project_path = None
        
        # Create placeholder UI
        layout = QVBoxLayout(self)
        
        label = QLabel("Project creation functionality will be implemented here.")
        layout.addWidget(label)
        
        # Path input
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Project path...")
        layout.addWidget(self._path_input)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_for_path)
        layout.addWidget(browse_btn)
        
        # OK/Cancel buttons
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
    
    def _browse_for_path(self):
        """Browse for project path"""
        if not PYSIDE_AVAILABLE:
            return
            
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if path:
            self._path_input.setText(path)
            self._project_path = Path(path)
    
    def get_project_path(self) -> Optional[Path]:
        """Get selected project path"""
        return self._project_path



