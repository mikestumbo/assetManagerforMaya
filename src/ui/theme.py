# -*- coding: utf-8 -*-
"""
UI Theme Constants for Asset Manager
Centralized styling for consistent UI appearance across all components

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Dict


class UITheme:
    """
    Centralized UI Theme Constants - Single Responsibility for consistent styling
    All dialogs and widgets should use these constants for cohesive appearance
    """
    
    # === MAIN COLOR PALETTE ===
    PRIMARY_BG = "#4a4a4a"      # Main background color
    SECONDARY_BG = "#5a5a5a"    # Hover/selected background
    TERTIARY_BG = "#6a6a6a"     # Pressed/active background
    DARK_BG = "#3a3a3a"         # Darker background for panels
    
    # === TEXT COLORS ===
    TEXT_PRIMARY = "#ffffff"    # Main text color
    TEXT_SECONDARY = "#cccccc"  # Secondary text color  
    TEXT_DISABLED = "#808080"   # Disabled text color
    TEXT_ACCENT = "#0078d4"     # Accent/link color
    
    # === BORDER COLORS ===
    BORDER_PRIMARY = "#666666"  # Main border color
    BORDER_DARK = "#555555"     # Darker border
    BORDER_LIGHT = "#777777"    # Lighter border
    
    # === BUTTON COLORS ===
    BUTTON_BG = PRIMARY_BG
    BUTTON_HOVER = SECONDARY_BG
    BUTTON_PRESSED = TERTIARY_BG
    BUTTON_ACCENT = "#0078d4"   # Blue accent for primary buttons
    BUTTON_SUCCESS = "#28a745"  # Green for success actions
    BUTTON_DANGER = "#dc3545"   # Red for danger actions
    
    # === INPUT COLORS ===
    INPUT_BG = "#3a3a3a"
    INPUT_BORDER = "#555555"
    INPUT_FOCUS = "#0078d4"
    
    @classmethod
    def get_dialog_stylesheet(cls) -> str:
        """Get the standard dialog stylesheet for consistent appearance"""
        return f"""
            QDialog {{
                background-color: {cls.PRIMARY_BG};
                color: {cls.TEXT_PRIMARY};
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }}
            
            /* === LABELS === */
            QLabel {{
                color: {cls.TEXT_PRIMARY};
                background-color: transparent;
                font-weight: normal;
                padding: 4px;
            }}
            
            QLabel[title="true"] {{
                font-size: 16px;
                font-weight: bold;
                color: {cls.TEXT_PRIMARY};
                margin-bottom: 8px;
            }}
            
            QLabel[description="true"] {{
                color: {cls.TEXT_SECONDARY};
                font-size: 12px;
                margin-bottom: 12px;
            }}
            
            /* === BUTTONS === */
            QPushButton {{
                background-color: {cls.BUTTON_BG};
                border: 1px solid {cls.BORDER_PRIMARY};
                border-radius: 4px;
                color: {cls.TEXT_PRIMARY};
                padding: 8px 16px;
                font-size: 13px;
                font-weight: normal;
                min-height: 20px;
            }}
            
            QPushButton:hover {{
                background-color: {cls.BUTTON_HOVER};
                border-color: {cls.BORDER_LIGHT};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.BUTTON_PRESSED};
                border-color: {cls.BORDER_DARK};
            }}
            
            QPushButton:disabled {{
                background-color: {cls.DARK_BG};
                color: {cls.TEXT_DISABLED};
                border-color: {cls.BORDER_DARK};
            }}
            
            QPushButton[accent="true"] {{
                background-color: {cls.BUTTON_ACCENT};
                color: {cls.TEXT_PRIMARY};
                font-weight: bold;
            }}
            
            QPushButton[accent="true"]:hover {{
                background-color: #106ebe;
            }}
            
            QPushButton[success="true"] {{
                background-color: {cls.BUTTON_SUCCESS};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QPushButton[danger="true"] {{
                background-color: {cls.BUTTON_DANGER};
                color: {cls.TEXT_PRIMARY};
            }}
            
            /* === INPUT FIELDS === */
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {cls.INPUT_BG};
                border: 1px solid {cls.INPUT_BORDER};
                border-radius: 4px;
                color: {cls.TEXT_PRIMARY};
                padding: 8px;
                font-size: 13px;
            }}
            
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 2px solid {cls.INPUT_FOCUS};
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left: 1px solid {cls.INPUT_BORDER};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                background-color: {cls.BUTTON_BG};
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-style: solid;
                border-width: 5px 4px 0px 4px;
                border-color: {cls.TEXT_PRIMARY} transparent transparent transparent;
                width: 0px;
                height: 0px;
                margin-right: 6px;
            }}
            
            QComboBox::down-arrow:hover {{
                border-color: {cls.TEXT_ACCENT} transparent transparent transparent;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {cls.PRIMARY_BG};
                border: 1px solid {cls.BORDER_PRIMARY};
                color: {cls.TEXT_PRIMARY};
                selection-background-color: {cls.SECONDARY_BG};
            }}
            
            /* === LIST WIDGETS === */
            QListWidget {{
                background-color: {cls.DARK_BG};
                border: 1px solid {cls.BORDER_PRIMARY};
                border-radius: 4px;
                color: {cls.TEXT_PRIMARY};
                alternate-background-color: {cls.PRIMARY_BG};
                outline: none;
            }}
            
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {cls.BORDER_DARK};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QListWidget::item:selected {{
                background-color: {cls.BUTTON_ACCENT};
                color: {cls.TEXT_PRIMARY};
                border: none;
            }}
            
            QListWidget::item:hover {{
                background-color: {cls.SECONDARY_BG};
            }}
            
            /* === GROUP BOXES === */
            QGroupBox {{
                font-weight: bold;
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_PRIMARY};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {cls.TEXT_PRIMARY};
                background-color: {cls.PRIMARY_BG};
            }}
            
            /* === FRAMES === */
            QFrame[panel="true"] {{
                background-color: {cls.DARK_BG};
                border: 1px solid {cls.BORDER_PRIMARY};
                border-radius: 4px;
                padding: 8px;
            }}
            
            /* === SPLITTERS === */
            QSplitter::handle {{
                background-color: {cls.BORDER_PRIMARY};
                width: 3px;
                height: 3px;
            }}
            
            QSplitter::handle:hover {{
                background-color: {cls.BORDER_LIGHT};
            }}
            
            /* === SCROLL AREAS === */
            QScrollArea {{
                background-color: {cls.DARK_BG};
                border: 1px solid {cls.BORDER_PRIMARY};
                border-radius: 4px;
            }}
            
            QScrollBar:vertical {{
                background-color: {cls.DARK_BG};
                width: 12px;
                border: none;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {cls.BORDER_PRIMARY};
                border-radius: 6px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.BORDER_LIGHT};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
        """
    
    @classmethod  
    def get_color_preview_style(cls, color: str) -> str:
        """Get stylesheet for color preview widgets"""
        return f"""
            QLabel {{
                background-color: {color};
                border: 2px solid {cls.BORDER_PRIMARY};
                border-radius: 4px;
                min-width: 24px;
                min-height: 24px;
                max-width: 24px; 
                max-height: 24px;
            }}
        """
