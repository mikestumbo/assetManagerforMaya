# -*- coding: utf-8 -*-
"""
Enhanced Asset Information Widget
Improved asset metadata display with larger font and scroll wheel font sizing

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Optional

# PySide6 imports for Maya 2025.3+ - Required, no fallbacks
try:
    from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QFont, QWheelEvent
except ImportError as e:
    raise ImportError(f"PySide6 import error: {e}. Maya 2025.3+ requires PySide6.")


class EnhancedAssetInfoWidget(QLabel):
    """
    Enhanced Asset Information Widget - Single Responsibility for displaying asset metadata
    Features:
    - Larger default font (14px instead of 11px)
    - Mouse scroll wheel to adjust font size (12px-24px range)
    - Visual feedback when changing font size
    - Better readability for most users
    """
    
    # Signal emitted when font size changes
    font_size_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Font size settings
        self._default_font_size = 14  # Increased from 11px for better readability
        self._current_font_size = self._default_font_size
        self._min_font_size = 12
        self._max_font_size = 24
        
        # Feedback timer for font size changes
        self._feedback_timer = QTimer()
        self._feedback_timer.timeout.connect(self._hide_font_feedback)
        self._feedback_timer.setSingleShot(True)
        
        # Store original text for feedback display
        self._original_text = "No asset selected"
        self._showing_feedback = False
        
        self._setup_widget()
    
    def _setup_widget(self) -> None:
        """Setup the enhanced asset info widget - Single Responsibility"""
        # Enable mouse tracking and focus for scroll wheel events
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        
        # Set initial properties
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setText(self._original_text)
        
        # Apply enhanced styling with larger font
        self._update_stylesheet()
    
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
            }}
            QLabel:hover {{
                border: 1px solid #777777;
            }}
        """
        self.setStyleSheet(stylesheet)
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events for font size adjustment - Single Responsibility"""
        # Check if Ctrl is pressed for font size adjustment
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Get wheel delta (positive = up, negative = down)
            delta = event.angleDelta().y()
            
            # Adjust font size
            if delta > 0:  # Scroll up = increase font
                self._increase_font_size()
            else:  # Scroll down = decrease font
                self._decrease_font_size()
            
            # Accept the event to prevent scrolling
            event.accept()
        else:
            # Show hint about Ctrl+scroll for font adjustment
            self._show_font_hint()
            # Let parent handle regular scrolling
            super().wheelEvent(event)
    
    def _increase_font_size(self) -> None:
        """Increase font size within limits - Single Responsibility"""
        if self._current_font_size < self._max_font_size:
            self._current_font_size += 1
            self._update_font_size()
    
    def _decrease_font_size(self) -> None:
        """Decrease font size within limits - Single Responsibility"""
        if self._current_font_size > self._min_font_size:
            self._current_font_size -= 1
            self._update_font_size()
    
    def _update_font_size(self) -> None:
        """Apply font size change and show feedback - Single Responsibility"""
        # Update stylesheet
        self._update_stylesheet()
        
        # Show font size feedback
        self._show_font_feedback()
        
        # Emit signal for external listeners
        self.font_size_changed.emit(self._current_font_size)
    
    def _show_font_feedback(self) -> None:
        """Show temporary font size feedback - Single Responsibility"""
        if not self._showing_feedback:
            # Store original text
            if not self._original_text or self._original_text == "No asset selected":
                self._original_text = self.text()
        
        # Show font size feedback
        self._showing_feedback = True
        feedback_text = f"Font Size: {self._current_font_size}px\n\n{self._original_text}"
        self.setText(feedback_text)
        
        # Hide feedback after 1.5 seconds
        self._feedback_timer.start(1500)
    
    def _show_font_hint(self) -> None:
        """Show hint about Ctrl+scroll for font adjustment - Single Responsibility"""
        if not self._showing_feedback:
            self._original_text = self.text()
        
        self._showing_feedback = True
        hint_text = "💡 Tip: Ctrl + Scroll Wheel to adjust font size\n\n" + self._original_text
        self.setText(hint_text)
        
        # Hide hint after 2 seconds
        self._feedback_timer.start(2000)
    
    def _hide_font_feedback(self) -> None:
        """Hide font size feedback and restore original text - Single Responsibility"""
        self._showing_feedback = False
        self.setText(self._original_text)
    
    def set_asset_info(self, info_text: str) -> None:
        """Set asset information text - Single Responsibility"""
        print(f"Asset Info: setting info = {info_text[:100]}...")
        self._original_text = info_text
        if not self._showing_feedback:
            self.setText(info_text)
    
    def reset_font_size(self) -> None:
        """Reset font size to default - Single Responsibility"""
        self._current_font_size = self._default_font_size
        self._update_font_size()
    
    def get_current_font_size(self) -> int:
        """Get current font size - Single Responsibility"""
        return self._current_font_size
    
    def set_font_size(self, size: int) -> None:
        """Set specific font size within limits - Single Responsibility"""
        if self._min_font_size <= size <= self._max_font_size:
            self._current_font_size = size
            self._update_stylesheet()
            self.font_size_changed.emit(self._current_font_size)
