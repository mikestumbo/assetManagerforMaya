# -*- coding: utf-8 -*-
"""
Asset Information Panel Widget
Enhanced text display with scroll wheel font scaling and better readability

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Optional

# PySide6 for Maya 2022+
from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QWheelEvent


class AssetInfoLabel(QLabel):
    """
    Enhanced Asset Information Label - Single Responsibility for text display with font scaling
    Provides scroll wheel font size adjustment and improved readability
    """
    
    font_size_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Font size configuration
        self._default_font_size = 14  # Increased from 11px for better readability
        self._min_font_size = 10
        self._max_font_size = 24
        self._current_font_size = self._default_font_size
        
        # Initialize with better default styling
        self._setup_initial_appearance()
    
    def _setup_initial_appearance(self) -> None:
        """Setup initial appearance with improved readability - Single Responsibility"""
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Apply enhanced styling with better font size
        self._update_stylesheet()
        
        # Set initial text
        self.setText("No asset selected\n\nTip: Hold Ctrl and scroll mouse wheel to adjust font size")
    
    def _update_stylesheet(self) -> None:
        """Update stylesheet with current font size - Single Responsibility"""
        stylesheet = f"""
            QLabel {{
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px;
                color: #cccccc;
                font-family: monospace;
                font-size: {self._current_font_size}px;
                line-height: 1.4;
            }}
        """
        self.setStyleSheet(stylesheet)
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events for font size adjustment - Single Responsibility"""
        # Only adjust font size when Ctrl is held down
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Get scroll direction
            delta = event.angleDelta().y()
            
            if delta > 0:
                # Scroll up - increase font size
                self._increase_font_size()
            elif delta < 0:
                # Scroll down - decrease font size
                self._decrease_font_size()
            
            # Accept the event to prevent further propagation
            event.accept()
        else:
            # Pass event to parent if Ctrl not held
            super().wheelEvent(event)
    
    def _increase_font_size(self) -> None:
        """Increase font size within bounds - Single Responsibility"""
        new_size = min(self._current_font_size + 1, self._max_font_size)
        self._set_font_size(new_size)
    
    def _decrease_font_size(self) -> None:
        """Decrease font size within bounds - Single Responsibility"""
        new_size = max(self._current_font_size - 1, self._min_font_size)
        self._set_font_size(new_size)
    
    def _set_font_size(self, size: int) -> None:
        """Set font size and update display - Single Responsibility"""
        if self._min_font_size <= size <= self._max_font_size and size != self._current_font_size:
            self._current_font_size = size
            self._update_stylesheet()
            self.font_size_changed.emit(size)
            
            # Update tooltip with current size
            self.setToolTip(f"Asset Information (Font: {size}px)\nCtrl + Scroll to adjust font size")
    
    def get_font_size(self) -> int:
        """Get current font size - Single Responsibility"""
        return self._current_font_size
    
    def set_font_size(self, size: int) -> None:
        """Set font size from external source - Single Responsibility"""
        self._set_font_size(size)
    
    def reset_font_size(self) -> None:
        """Reset font size to default - Single Responsibility"""
        self._set_font_size(self._default_font_size)
    
    def get_font_size_range(self) -> tuple[int, int]:
        """Get font size range (min, max) - Single Responsibility"""
        return self._min_font_size, self._max_font_size
    
    def is_font_size_at_minimum(self) -> bool:
        """Check if font size is at minimum - Single Responsibility"""
        return self._current_font_size <= self._min_font_size
    
    def is_font_size_at_maximum(self) -> bool:
        """Check if font size is at maximum - Single Responsibility"""
        return self._current_font_size >= self._max_font_size
    
    def get_font_size_info(self) -> dict:
        """Get comprehensive font size information - Single Responsibility"""
        return {
            'current': self._current_font_size,
            'default': self._default_font_size,
            'min': self._min_font_size,
            'max': self._max_font_size,
            'at_min': self.is_font_size_at_minimum(),
            'at_max': self.is_font_size_at_maximum()
        }


class AssetInfoPanel(QLabel):
    """
    Legacy alias for backward compatibility
    Use AssetInfoLabel for new implementations
    """
    
    def __init__(self, parent=None):
        # Delegate to the new implementation
        super().__init__(parent)
        print("⚠️  AssetInfoPanel is deprecated, use AssetInfoLabel instead")
        
        # Create the enhanced label as a child
        self._enhanced_label = AssetInfoLabel(self)
        
    def setText(self, text: str) -> None:
        """Override to use enhanced label"""
        if hasattr(self, '_enhanced_label'):
            self._enhanced_label.setText(text)
        else:
            super().setText(text)
