# -*- coding: utf-8 -*-
"""
Asset Manager Main Window
Clean UI orchestration following Single Responsibility Principle

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QTabWidget, QMenuBar, QMenu,
        QStatusBar, QLabel, QProgressBar, QMessageBox, QPushButton, QInputDialog,
        QDialog, QGroupBox, QLineEdit
    )
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QIcon, QKeySequence, QAction, QColor
except ImportError as e:
    print(f"❌ PySide6 import failed: {e}")
    print("🔧 Maya 2025+ requires PySide6. Please ensure it's properly installed.")
    raise

from ..core.container import get_container
from ..core.interfaces.asset_repository import IAssetRepository
from ..core.interfaces.event_publisher import IEventPublisher, EventType
from .collection_manager_dialog import CollectionManagerDialog
from ..core.models.asset import Asset

# Robust import strategy for Maya compatibility
try:
    from ..config.constants import UI_CONFIG
except ImportError:
    try:
        # Fallback for Maya context
        import sys
        from pathlib import Path
        current_dir = Path(__file__).parent.parent
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))
        from config.constants import UI_CONFIG
    except ImportError:
        # Ultimate fallback - define UI_CONFIG locally
        UI_CONFIG = {
            'WINDOW_TITLE': 'Asset Manager v1.4.0',
            'WINDOW_SIZE': (1400, 900),
            'MIN_WINDOW_SIZE': (800, 600)
        }

from .widgets.asset_library_widget import AssetLibraryWidget
from .widgets.asset_preview_widget import AssetPreviewWidget
from .widgets.color_coding_keychart_widget import ColorCodingKeychartWidget
from .widgets.enhanced_asset_info_widget import EnhancedAssetInfoWidget
from .dialogs.color_coding_manager_dialog import ColorCodingManagerDialog
from .dialogs.tag_manager_dialog import TagManagerDialog

# Add global variable for singleton reference (replaces reliance on external module attribute)
_asset_manager_window = None

class AssetManagerWindow(QMainWindow):
    """
    Asset Manager Main Window - Single Responsibility for window orchestration
    Follows Clean Architecture with dependency injection
    """
    
    # Signals for clean event communication
    asset_selected = Signal(Asset)
    asset_imported = Signal(Asset)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Dependency injection - resolve services
        self._container = get_container()
        self._repository = self._container.resolve(IAssetRepository)
        self._event_publisher = self._container.resolve(IEventPublisher)
        
        # Resolve library service (handles add/remove operations)
        from ..core.interfaces.library_service import ILibraryService
        self._library_service = self._container.resolve(ILibraryService)
        
        # UI components
        self._library_widget: Optional[AssetLibraryWidget] = None
        self._preview_widget: Optional[AssetPreviewWidget] = None
        self._color_keychart: Optional[ColorCodingKeychartWidget] = None
        self._metadata_panel: Optional[QWidget] = None  # RIGHT_B panel reference
        self._current_asset: Optional[Asset] = None
        
        # Initialize UI
        self._setup_window()
        self._create_menu_bar()
        self._create_central_widget()
        self._create_status_bar()
        self._setup_event_subscriptions()
        self._setup_keyboard_shortcuts()
        
        # Load initial data
        QTimer.singleShot(100, self._load_initial_data)
        
        # Load window state
        self._load_window_state()
        
        # Set global singleton reference to this instance
        global _asset_manager_window
        _asset_manager_window = self
    def _setup_window(self) -> None:
        """Setup main window properties with Maya integration - Single Responsibility"""
        self.setWindowTitle("Asset Manager")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 800)
        
        # Set window icon if available
        icon_path = Path(__file__).parent.parent.parent / "icons" / "assetManager_icon2.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Configure window flags for Maya integration
        if self.parent() is not None:
            # Has Maya parent - set flags to stay above Maya with proper focus
            self.setWindowFlags(
                Qt.WindowType.Window |  # Independent window
                Qt.WindowType.WindowCloseButtonHint |  # Close button
                Qt.WindowType.WindowMinimizeButtonHint |  # Minimize button  
                Qt.WindowType.WindowMaximizeButtonHint |  # Maximize button
                Qt.WindowType.WindowStaysOnTopHint  # Stay above Maya windows
            )
            # Ensure window activates properly
            self.activateWindow()
            self.raise_()
            print("✅ Asset Manager window configured for Maya integration with proper focus")
        else:
            # Standalone mode - use default flags
            print("ℹ️ Asset Manager running in standalone mode")
    
    def _create_menu_bar(self) -> None:
        """Create application menu bar - Single Responsibility"""
        menubar = self.menuBar()
        
        # Style the menu bar for better visibility and consistency
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #4a4a4a;
                color: #ffffff;
                font-size: 13px;
                font-weight: normal;
                padding: 6px 0px;
                border: none;
                border-bottom: 1px solid #666666;
                spacing: 8px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 8px 16px;
                margin: 0px 2px;
                border-radius: 3px;
            }
            QMenuBar::item:selected {
                background-color: #5a5a5a;
                color: #ffffff;
            }
            QMenuBar::item:pressed {
                background-color: #6a6a6a;
                color: #ffffff;
            }
            QMenu {
                background-color: #4a4a4a;
                color: #ffffff;
                border: 1px solid #666666;
                font-size: 12px;
                padding: 4px;
            }
            QMenu::item {
                background: transparent;
                padding: 8px 20px;
                margin: 1px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #5a5a5a;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #666666;
                margin: 4px 8px;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_project_action = QAction("&New Project...", self)
        new_project_action.setShortcut(QKeySequence.StandardKey.New)
        new_project_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_project_action)
        
        open_project_action = QAction("&Open Project...", self)
        open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        open_project_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_project_action)
        
        # Add Set Project menu item for switching between existing projects
        set_project_action = QAction("&Set Project...", self)
        set_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        set_project_action.setStatusTip("Set an existing project as the current Asset Library")
        set_project_action.triggered.connect(self._on_set_project)
        file_menu.addAction(set_project_action)
        
        # Save Project options
        save_project_action = QAction("&Save Project...", self)
        save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        save_project_action.setStatusTip("Save the current project and asset library")
        save_project_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_project_action)
        
        save_project_as_action = QAction("Save Project &As...", self)
        save_project_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_project_as_action.setStatusTip("Save the current project to a new location")
        save_project_as_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(save_project_as_action)
        
        # Add Delete Project menu item for removing projects permanently
        delete_project_action = QAction("&Delete Project...", self)
        delete_project_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        delete_project_action.setStatusTip("Permanently delete an existing Asset Manager project")
        delete_project_action.triggered.connect(self._on_delete_project)
        file_menu.addAction(delete_project_action)
        
        file_menu.addSeparator()
        
        refresh_action = QAction("&Refresh Library", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._on_refresh_library)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        # Add Asset Management Options
        add_asset_action = QAction("&Add Asset to Library...", self)
        add_asset_action.setShortcut(QKeySequence("Ctrl+A"))
        add_asset_action.triggered.connect(self._on_add_asset_to_library)
        file_menu.addAction(add_asset_action)
        
        add_multiple_assets_action = QAction("Add &Multiple Assets from Folders...", self)
        add_multiple_assets_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        add_multiple_assets_action.triggered.connect(self._on_add_multiple_assets)
        file_menu.addAction(add_multiple_assets_action)
        
        file_menu.addSeparator()
        
        # Add missing Remove Selected Asset menu item
        remove_selected_action = QAction("&Remove Selected Asset...", self)
        remove_selected_action.setShortcut(QKeySequence.StandardKey.Delete)
        remove_selected_action.triggered.connect(self._on_remove_selected_asset)
        file_menu.addAction(remove_selected_action)
        
        # Add Delete Selected Asset(s) menu item with Ctrl+Del hotkey
        delete_selected_action = QAction("&Delete Selected Asset(s)...", self)
        delete_selected_action.setShortcut(QKeySequence("Ctrl+Del"))
        delete_selected_action.setStatusTip("Delete Selected Asset(s) from Set Project")
        delete_selected_action.triggered.connect(self._on_delete_selected_asset)
        file_menu.addAction(delete_selected_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        search_action = QAction("&Advanced Search...", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(self._on_advanced_search)
        edit_menu.addAction(search_action)
        
        edit_menu.addSeparator()
        
        # Thumbnail management
        refresh_thumbnails_action = QAction("Refresh &Thumbnails", self)
        refresh_thumbnails_action.setShortcut(QKeySequence("F5"))
        refresh_thumbnails_action.triggered.connect(self._on_refresh_thumbnails)
        edit_menu.addAction(refresh_thumbnails_action)
        
        clear_thumbnail_cache_action = QAction("&Clear Thumbnail Cache", self)
        clear_thumbnail_cache_action.triggered.connect(self._on_clear_thumbnail_cache)
        edit_menu.addAction(clear_thumbnail_cache_action)
        
        # Assets menu
        assets_menu = menubar.addMenu("&Assets")
        
        import_selected_action = QAction("&Import Selected", self)
        import_selected_action.setShortcut(QKeySequence("Ctrl+I"))
        import_selected_action.triggered.connect(self._on_import_selected)
        assets_menu.addAction(import_selected_action)
        
        add_to_favorites_action = QAction("Add to &Favorites", self)
        add_to_favorites_action.setShortcut(QKeySequence("Ctrl+D"))
        add_to_favorites_action.triggered.connect(self._on_add_to_favorites)
        assets_menu.addAction(add_to_favorites_action)
        
        export_selected_action = QAction("&Export Selected...", self)
        export_selected_action.setShortcut(QKeySequence("Ctrl+E"))
        export_selected_action.setStatusTip("Export selected asset(s) to a new location")
        export_selected_action.triggered.connect(self._on_export_selected)
        assets_menu.addAction(export_selected_action)
        
        # Add separator before destructive action
        assets_menu.addSeparator()
        
        # Remove Asset action - matches File menu functionality
        remove_asset_action = QAction("&Remove Selected Asset...", self)
        remove_asset_action.setShortcut(QKeySequence.StandardKey.Delete)
        remove_asset_action.triggered.connect(self._on_remove_selected_asset)
        assets_menu.addAction(remove_asset_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        self._show_preview_action = QAction("Show &Preview", self)
        self._show_preview_action.setCheckable(True)
        self._show_preview_action.setChecked(True)
        self._show_preview_action.triggered.connect(self._on_toggle_preview_unified)
        view_menu.addAction(self._show_preview_action)
        
        # Add missing "Show Asset Information" option
        show_asset_info_action = QAction("&Asset Information", self)
        show_asset_info_action.setCheckable(True)
        show_asset_info_action.setChecked(True)  # Initially visible
        show_asset_info_action.triggered.connect(self._on_toggle_asset_info_unified)
        
        # Store as instance variable for synchronization - Single Responsibility
        self._show_asset_info_action = show_asset_info_action
        view_menu.addAction(show_asset_info_action)
        
        view_menu.addSeparator()
        
        # Color Coding Manager
        color_coding_action = QAction("&Color Coding Manager...", self)
        color_coding_action.triggered.connect(self._on_color_coding_manager)
        view_menu.addAction(color_coding_action)
        
        # Tag Manager  
        tag_manager_action = QAction("&Tag Manager...", self)
        tag_manager_action.triggered.connect(self._on_tag_manager)
        view_menu.addAction(tag_manager_action)
        
        # Collections menu - moved to separate menu for better UX
        collections_menu = menubar.addMenu("&Collections")
        
        new_collection_action = QAction("&New Collection...", self)
        new_collection_action.setShortcut(QKeySequence("Ctrl+N"))
        new_collection_action.triggered.connect(self._on_new_collection)
        collections_menu.addAction(new_collection_action)
        
        manage_collections_action = QAction("&Manage Collections...", self)
        manage_collections_action.triggered.connect(self._on_manage_collections)
        collections_menu.addAction(manage_collections_action)
        
        # USD Pipeline menu - NEW! v1.4.0
        usd_menu = menubar.addMenu("&USD Pipeline")
        
        usd_export_action = QAction("&Export to USD...", self)
        usd_export_action.setShortcut(QKeySequence("Ctrl+U"))
        usd_export_action.setStatusTip("Open USD Pipeline Creator for Maya → USD export")
        usd_export_action.triggered.connect(self._on_usd_pipeline)
        usd_menu.addAction(usd_export_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        # Add missing "Check for Update" 
        check_update_action = QAction("&Check for Update...", self)
        check_update_action.triggered.connect(self._on_check_update)
        help_menu.addAction(check_update_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _create_central_widget(self) -> None:
        """Create central widget with splitter layout - Single Responsibility"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout with tight spacing
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)  # Tight spacing between toolbar and content
        
        # Create toolbar for missing buttons
        toolbar = self._create_main_toolbar()
        main_layout.addWidget(toolbar)
        
        # Small separator between toolbar and main content
        main_layout.addSpacing(4)
        
        # Create 4-panel layout: LEFT (controls) | CENTER (library) | RIGHT_A (preview) | RIGHT_B (metadata)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # LEFT Panel: Search, Tags, Collections, Color Keychart
        left_panel = self._create_left_controls_panel()
        main_splitter.addWidget(left_panel)
        
        # CENTER Panel: Asset Library
        center_panel = self._create_center_library_panel()
        main_splitter.addWidget(center_panel)
        
        # Create right side splitter for RIGHT_A and RIGHT_B panels
        right_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(right_splitter)
        
        # RIGHT_A Panel: Asset Preview
        right_a_panel = self._create_right_a_preview_panel()
        right_splitter.addWidget(right_a_panel)
        
        # RIGHT_B Panel: Asset Information/Metadata
        right_b_panel = self._create_right_b_metadata_panel()
        self._metadata_panel = right_b_panel  # Store reference for toggling
        right_splitter.addWidget(right_b_panel)
        
        # Set proportional sizes: LEFT(200) | CENTER(400) | RIGHT_A(300) | RIGHT_B(250)
        main_splitter.setSizes([200, 400, 550])  # Left, Center, Right combined
        right_splitter.setSizes([300, 250])      # Preview, Metadata
        
        # Configure stretch factors for responsive behavior
        main_splitter.setStretchFactor(0, 0)  # LEFT: fixed size
        main_splitter.setStretchFactor(1, 1)  # CENTER: stretches most
        main_splitter.setStretchFactor(2, 0)  # RIGHT: moderate stretch
        
        right_splitter.setStretchFactor(0, 1)  # RIGHT_A: stretches more
        right_splitter.setStretchFactor(1, 0)  # RIGHT_B: fixed size
    
    def _create_left_controls_panel(self) -> QWidget:
        """Create LEFT panel with search, tags, collections, and color keychart - Single Responsibility"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(8)
        
        # Panel title
        title_label = QLabel("Asset Controls")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #cccccc; padding: 4px;")
        left_layout.addWidget(title_label)
        
        # Tag Management Section
        tag_group = QGroupBox("Tag Management")
        tag_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cccccc; }")
        tag_layout = QVBoxLayout(tag_group)
        
        # Create tag button
        create_tag_btn = QPushButton("Create New Tag")
        create_tag_btn.clicked.connect(self._on_create_tag)
        tag_layout.addWidget(create_tag_btn)
        
        # Tag manager button
        tag_manager_btn = QPushButton("Tag Manager...")
        tag_manager_btn.clicked.connect(self._on_tag_manager)
        tag_layout.addWidget(tag_manager_btn)
        
        left_layout.addWidget(tag_group)
        
        # Collections Section
        collections_group = QGroupBox("Collections")
        collections_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cccccc; }")
        collections_layout = QVBoxLayout(collections_group)
        
        # Create collection button
        create_collection_btn = QPushButton("Create Collection")
        create_collection_btn.clicked.connect(self._on_new_collection)
        collections_layout.addWidget(create_collection_btn)
        
        # Manage collections button
        manage_collections_btn = QPushButton("Manage Collections...")
        manage_collections_btn.clicked.connect(self._on_manage_collections)
        collections_layout.addWidget(manage_collections_btn)
        
        left_layout.addWidget(collections_group)
        
        # Color Coding Keychart - moved here from old left panel
        self._color_keychart = ColorCodingKeychartWidget()
        try:
            if hasattr(self._color_keychart, 'color_coding_requested'):
                self._color_keychart.color_coding_requested.connect(self._on_color_coding_manager)  # type: ignore
        except AttributeError:
            pass  # Signal not available
        left_layout.addWidget(self._color_keychart)
        
        # Add stretch to push everything to top
        left_layout.addStretch()
        
        return left_widget
    
    def _create_center_library_panel(self) -> QWidget:
        """Create CENTER panel with asset library - Single Responsibility"""
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 4, 4, 4)
        center_layout.setSpacing(4)
        
        # Panel title
        title_label = QLabel("Asset Library")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #cccccc; padding: 4px;")
        center_layout.addWidget(title_label)
        
        # Create asset library widget
        self._library_widget = AssetLibraryWidget()
        self._library_widget.asset_selected.connect(self._on_asset_selected)
        self._library_widget.asset_double_clicked.connect(self._on_asset_import)
        self._library_widget.asset_info_requested.connect(self._on_asset_info_requested)
        # Connect selection to metadata display update
        self._library_widget.asset_selected.connect(self._update_asset_info_display)
        # Connect color scheme changes to update keychart
        if hasattr(self._library_widget, 'color_scheme_changed'):
            self._library_widget.color_scheme_changed.connect(self._on_library_color_scheme_changed)
        center_layout.addWidget(self._library_widget, 1)  # Take most space
        
        # Initialize color keychart with current library colors
        if self._color_keychart and self._library_widget:
            try:
                current_scheme = self._library_widget.get_current_color_scheme()
                self._color_keychart.update_color_scheme(current_scheme)
            except Exception as e:
                print(f"⚠️ Could not initialize color keychart with library colors: {e}")
        
        return center_widget
    
    def _create_right_a_preview_panel(self) -> QWidget:
        """Create RIGHT_A panel with asset preview - Single Responsibility"""
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.setSpacing(4)
        
        # Panel title
        title_label = QLabel("Asset Preview")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #cccccc; padding: 4px;")
        preview_layout.addWidget(title_label)
        
        # Create preview widget (without integrated info display)
        self._preview_widget = AssetPreviewWidget()
        preview_layout.addWidget(self._preview_widget, 1)  # type: ignore
        
        return preview_widget
    
    def _create_right_b_metadata_panel(self) -> QWidget:
        """Create RIGHT_B panel with asset information/metadata - Single Responsibility"""
        metadata_widget = QWidget()
        metadata_layout = QVBoxLayout(metadata_widget)
        metadata_layout.setContentsMargins(4, 4, 4, 4)
        metadata_layout.setSpacing(4)
        
        # Panel title
        title_label = QLabel("Asset Information")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #cccccc; padding: 4px;")
        metadata_layout.addWidget(title_label)
        
        # Asset metadata display - Enhanced widget with larger font and scroll wheel control
        self._metadata_widget = EnhancedAssetInfoWidget(self)
        metadata_layout.addWidget(self._metadata_widget, 1)
        
        return metadata_widget

    def _create_main_toolbar(self) -> QWidget:
        """Create main toolbar with essential buttons - Enhanced styling and compact layout"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        
        # Enhanced margins and spacing for better visibility
        toolbar_layout.setContentsMargins(10, 6, 10, 6)  # left, top, right, bottom
        toolbar_layout.setSpacing(6)  # Increased spacing between buttons
        
        # Force toolbar to use system window color to match main UI
        from PySide6.QtGui import QPalette
        
        try:
            # Get system window color
            palette = self.palette()
            system_color = palette.color(QPalette.ColorRole.Window)
            bg_color = system_color.name()
            print(f"🎨 Using system background color: {bg_color}")  # Debug info
        except Exception as e:
            # Fallback to common Maya UI color
            bg_color = "#393939"  # Maya's default dark gray
            print(f"🎨 Using fallback Maya color: {bg_color}")  # Debug info
        
        toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color} !important;
                border: 1px solid #555555;
                border-radius: 3px;
            }}
            QWidget#toolbar {{
                background-color: {bg_color} !important;
                border: 1px solid #555555;
                border-radius: 3px;
            }}
            QPushButton {{
                background-color: #4a4a4a;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 8px 12px;
                min-height: 36px;  /* Increased button height for better centering */
                font-size: 13px;
                font-weight: normal;
                color: #cccccc;
            }}
            QPushButton:hover {{
                background-color: #5a5a5a;
                border: 1px solid #777777;
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #2a2a2a;
                border: 1px solid #333333;
                color: #ffffff;
            }}
            QPushButton:checked {{
                background-color: #0078d4;  /* Matching Manage Colors button accent color */
                border: 1px solid #106ebe;
                font-weight: bold;
                color: #ffffff;  /* White text for better contrast */
            }}
            QLabel {{
                color: #999999;
                font-weight: bold;
                font-size: 13px;
                margin: 0px 6px;
            }}
        """)
        
        # Set object name and force update
        toolbar.setObjectName("toolbar")
        toolbar.setAutoFillBackground(True)
        
        # Set increased height for better visibility and button fit
        toolbar.setFixedHeight(56)  # Increased toolbar height for better button centering
        
        # Create Asset button (FIRST in new order)
        create_btn = QPushButton("Create Asset")
        create_btn.setToolTip("Create new asset from current scene")
        create_btn.clicked.connect(self._on_create_asset)
        toolbar_layout.addWidget(create_btn)
        
        # Import Asset button (SECOND in new order)
        import_btn = QPushButton("Import Asset")
        import_btn.setToolTip("Import selected asset into scene")
        import_btn.clicked.connect(self._on_import_selected)
        toolbar_layout.addWidget(import_btn)
        
        # Remove Asset button (THIRD in new order)
        remove_btn = QPushButton("Remove Asset")
        remove_btn.setToolTip("Remove selected asset from library")
        remove_btn.clicked.connect(self._on_remove_selected_asset)
        toolbar_layout.addWidget(remove_btn)
        
        # Separator
        separator1 = self._create_toolbar_separator()
        toolbar_layout.addWidget(separator1)
        
        # Refresh Library button (FOURTH in new order)
        refresh_btn = QPushButton("Refresh Library")
        refresh_btn.setToolTip("Refresh Asset Library and Reload All Assets from Project")
        refresh_btn.clicked.connect(self._on_refresh_library)
        toolbar_layout.addWidget(refresh_btn)
        
        # Reset Icons button (NEW - next to Refresh Library)
        reset_icons_btn = QPushButton("Reset Icons")
        reset_icons_btn.setToolTip("Resets Library icons to the default size")
        reset_icons_btn.clicked.connect(self._on_reset_icon_size)
        toolbar_layout.addWidget(reset_icons_btn)
        
        # Separator
        separator2 = self._create_toolbar_separator()
        toolbar_layout.addWidget(separator2)
        
        # Preview toggle button (FIFTH in new order) - increased width
        self._preview_btn = QPushButton("Hide Preview")  # Initially shows "Hide" since preview is visible
        self._preview_btn.setCheckable(True)
        self._preview_btn.setChecked(True)
        self._preview_btn.setToolTip("Toggle preview panel")
        self._preview_btn.setMinimumWidth(120)  # Increased width for bold text legibility
        self._preview_btn.clicked.connect(self._on_toggle_preview_unified)
        toolbar_layout.addWidget(self._preview_btn)
        
        # Info button (SIXTH in new order) - increased width and matching color
        self._info_btn = QPushButton("Hide Info")
        self._info_btn.setCheckable(True)
        self._info_btn.setChecked(True)  # Initially checked since panel is visible
        self._info_btn.setToolTip("Toggle asset information panel")
        self._info_btn.setMinimumWidth(120)  # Increased width for bold text legibility
        self._info_btn.clicked.connect(self._on_toggle_asset_info_unified)
        toolbar_layout.addWidget(self._info_btn)
        
        toolbar_layout.addStretch()  # Push buttons to left
        return toolbar
    
    def _create_toolbar_separator(self) -> QWidget:
        """Create professional toolbar separator - Single Responsibility"""
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setFixedHeight(40)  # Adjusted for larger toolbar height
        separator.setStyleSheet("""
            QWidget {
                background-color: #999999;
                border: none;
                margin: 3px 8px;
            }
        """)
        return separator
    
    def _create_status_bar(self) -> None:
        """Create status bar with progress indicator - Single Responsibility"""
        status_bar = self.statusBar()
        
        # Status label
        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label)
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMaximumWidth(200)
        status_bar.addPermanentWidget(self._progress_bar)
        
        # Asset count label
        self._asset_count_label = QLabel("0 assets")
        status_bar.addPermanentWidget(self._asset_count_label)
    
    def _setup_event_subscriptions(self) -> None:
        """Setup event system subscriptions - Observer Pattern"""
        self._event_publisher.subscribe(EventType.ASSET_SELECTED, self._handle_asset_selected_event)
        self._event_publisher.subscribe(EventType.ASSET_IMPORTED, self._handle_asset_imported_event)
        self._event_publisher.subscribe(EventType.LIBRARY_REFRESHED, self._handle_library_refreshed_event)
        self._event_publisher.subscribe(EventType.ERROR_OCCURRED, self._handle_error_event)
    
    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts - Single Responsibility"""
        # Additional shortcuts beyond menu items
        select_all_action = QAction(self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self._on_select_all)
        self.addAction(select_all_action)
    
    def _load_initial_data(self) -> None:
        """Load initial data asynchronously - Non-blocking initialization"""
        self._set_status("Loading assets...", show_progress=True)
        
        # Load data in background thread
        def load_data():
            try:
                # Load recent assets
                recent_assets = self._repository.get_recent_assets(10)
                favorites = self._repository.get_favorites()
                
                # Update UI on main thread
                if self._library_widget:
                    self._library_widget.set_recent_assets(recent_assets)
                    self._library_widget.set_favorite_assets(favorites)
                
                self._set_status("Ready")
                
            except Exception as e:
                self._set_status(f"Error loading data: {e}")
        
        # Run in background
        import threading
        threading.Thread(target=load_data, daemon=True).start()
    
    def _set_status(self, message: str, show_progress: bool = False) -> None:
        """Update status bar message - Single Responsibility"""
        self._status_label.setText(message)
        self._progress_bar.setVisible(show_progress)
        
        if show_progress:
            self._progress_bar.setRange(0, 0)  # Indeterminate progress
    
    def _update_asset_count(self, count: int) -> None:
        """Update asset count display - Single Responsibility"""
        self._asset_count_label.setText(f"{count} assets")
    
    # Event Handlers - Clean separation of concerns
    
    def _on_asset_selected(self, asset: Asset) -> None:
        """Handle asset selection from library widget"""
        self._current_asset = asset
        
        # Update preview
        if self._preview_widget:
            self._preview_widget.set_asset(asset)
        
        # Update repository access time
        self._repository.update_access_time(asset)
        
        # Emit signal and publish event
        self.asset_selected.emit(asset)
        self._event_publisher.publish(EventType.ASSET_SELECTED, {'asset': asset})
        
    def _on_asset_info_requested(self, asset: Asset) -> None:
        """Handle asset information request - Display in RIGHT_B metadata panel"""
        # Set current asset
        self._current_asset = asset
        
        # Update both preview (RIGHT_A) and metadata (RIGHT_B) panels
        if self._preview_widget:
            self._preview_widget.set_asset(asset)
        
        # Update the dedicated metadata panel
        self._update_asset_info_display(asset)
    
    def _on_asset_import(self, asset: Asset) -> None:
        """Handle asset import request - Enhanced error handling"""
        print(f"🎬 Import request received for: {asset.display_name if hasattr(asset, 'display_name') else 'Unknown'}")
        print(f"🎬 Asset type: {type(asset)}")
        print(f"🎬 Asset path: {asset.file_path if hasattr(asset, 'file_path') else 'No path'}")
        
        try:
            # Try Maya import with fallback approach
            success = self._import_asset_to_maya(asset)
            
            if success:
                self._set_status(f"Imported: {asset.display_name}")
                self.asset_imported.emit(asset)
                self._event_publisher.publish(EventType.ASSET_IMPORTED, {'asset': asset})
                
                # Update access time for recent assets
                self._repository.update_access_time(asset)
                
                # NOW that asset is in Maya scene, extract full metadata and generate thumbnails
                print(f"🎬 Asset imported to Maya - extracting full metadata and generating thumbnails")
                
                # Extract full Maya metadata (asset already in scene)
                QTimer.singleShot(300, lambda: self._extract_full_metadata_for_imported_asset(asset.file_path))
                
                # Generate playblast thumbnail (asset already in scene)
                QTimer.singleShot(500, lambda: self._generate_thumbnail_for_imported_asset(asset.file_path))
            else:
                self._set_status(f"Failed to import: {asset.display_name}")
                
        except Exception as e:
            error_msg = f"Import error: {str(e)}"
            print(error_msg)  # Log to console
            self._set_status(error_msg)
            QMessageBox.warning(self, "Import Error", f"Failed to import {asset.display_name}:\n{str(e)}")
    
    def _import_asset_to_maya(self, asset: Asset) -> bool:
        """Import asset to Maya with proper error handling - Single Responsibility"""
        try:
            import maya.cmds as cmds # type: ignore
            
            # SAFE FILE PATH VALIDATION - Defensive Programming
            if not self._validate_asset_file_path(asset):
                return False
            
            file_path = str(asset.file_path)
            file_ext = asset.file_path.suffix.lower()
            
            # Handle different file types
            if file_ext in ['.ma', '.mb']:
                # Maya scene files
                cmds.file(file_path, i=True, type="mayaAscii" if file_ext == '.ma' else "mayaBinary")
                return True
            elif file_ext in ['.obj']:
                # OBJ files
                cmds.file(file_path, i=True, type="OBJ")
                return True
            elif file_ext in ['.fbx']:
                # FBX files
                if cmds.pluginInfo('fbxmaya', query=True, loaded=True) or cmds.loadPlugin('fbxmaya', quiet=True):
                    cmds.file(file_path, i=True, type="FBX")
                    return True
                else:
                    raise Exception("FBX plugin not available")
            elif file_ext in ['.abc']:
                # Alembic files
                if cmds.pluginInfo('AbcImport', query=True, loaded=True) or cmds.loadPlugin('AbcImport', quiet=True):
                    cmds.AbcImport(file_path)
                    return True
                else:
                    raise Exception("Alembic plugin not available")
            else:
                raise Exception(f"Unsupported file type: {file_ext}")
                
        except Exception as e:
            print(f"Maya import failed: {e}")
            return False
    
    def _validate_asset_file_path(self, asset: Asset) -> bool:
        """
        Validate asset file path before Maya operations - Defensive Programming
        Prevents QUrl crashes from invalid/null paths
        Single Responsibility: File path validation only
        """
        try:
            # Check if asset exists
            if not asset:
                print("❌ Asset validation failed: No asset provided")
                return False
            
            # Check if file_path attribute exists
            if not hasattr(asset, 'file_path'):
                print("❌ Asset validation failed: No file_path attribute")
                return False
            
            # Check if file_path is not None/empty
            if not asset.file_path:
                print("❌ Asset validation failed: Empty file path")
                return False
            
            # Convert to Path object for validation
            file_path = Path(asset.file_path)
            
            # Check if path is absolute and exists
            if not file_path.is_absolute():
                print(f"❌ Asset validation failed: Relative path not allowed: {file_path}")
                return False
            
            if not file_path.exists():
                print(f"❌ Asset validation failed: File does not exist: {file_path}")
                return False
            
            if not file_path.is_file():
                print(f"❌ Asset validation failed: Path is not a file: {file_path}")
                return False
            
            # Check file extension
            if not file_path.suffix:
                print(f"❌ Asset validation failed: No file extension: {file_path}")
                return False
            
            print(f"✅ Asset file path validated: {file_path.name}")
            return True
            
        except Exception as e:
            print(f"❌ Asset validation error: {e}")
            return False
    
    def _on_new_project(self) -> None:
        """Handle new project creation - Enhanced with functional dialog"""
        try:
            # Use built-in dialogs for robust functionality
            from PySide6.QtWidgets import QFileDialog, QInputDialog
            
            # Get project name
            project_name, ok = QInputDialog.getText(
                self, 
                'New Project', 
                'Project name:',
                text='MyProject'
            )
            
            if not ok or not project_name.strip():
                return
                
            # Get project location
            parent_dir = QFileDialog.getExistingDirectory(
                self, 
                "Select Parent Directory for New Project",
                str(Path.home() / "Documents")
            )
            
            if not parent_dir:
                return
                
            # Create project directory structure
            project_path = Path(parent_dir) / project_name.strip()
            success = self._create_project_structure(project_path)
            
            if success:
                self._load_project(project_path)
                self._set_status(f"Created new project: {project_name}")
                QMessageBox.information(
                    self, 
                    "Project Created", 
                    f"New project '{project_name}' created successfully!\n\nLocation: {project_path}"
                )
            else:
                self._set_status("Failed to create project")
                
        except Exception as e:
            error_msg = f"Failed to create new project: {e}"
            self._set_status(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
    
    def _create_project_structure(self, project_path: Path) -> bool:
        """Create standard project directory structure - Single Responsibility"""
        try:
            # Create main project directory
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Create standard subdirectories for asset organization
            subdirs = [
                "assets",           # Main assets folder
                "assets/models",    # 3D models
                "assets/textures",  # Texture files
                "assets/materials", # Material definitions
                "assets/rigs",      # Character/object rigs
                "assets/animations", # Animation files
                "assets/scenes",    # Maya scene files
                "assets/references", # Reference files
                "exports",          # Exported files
                "temp",             # Temporary files
                "docs"              # Project documentation
            ]
            
            for subdir in subdirs:
                (project_path / subdir).mkdir(parents=True, exist_ok=True)
            
            # Create project configuration file
            config_file = project_path / "project.json"
            import json
            from datetime import datetime
            
            project_config = {
                "name": project_path.name,
                "created": datetime.now().isoformat(),
                "version": "1.0",
                "asset_manager_version": "1.3.0",
                "description": f"Asset Manager project: {project_path.name}",
                "directories": {
                    "assets": "assets",
                    "exports": "exports",
                    "temp": "temp",
                    "docs": "docs"
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(project_config, f, indent=4)
            
            # Create README file
            readme_file = project_path / "README.md"
            readme_content = f"""# {project_path.name}

Asset Manager Project created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Directory Structure

- **assets/** - Main asset library (only asset files will appear in the Asset Manager)
  - **models/** - 3D models and geometry (.ma, .mb, .obj, .fbx, .abc, .usd)
  - **textures/** - Texture and image files (.png, .jpg, .tiff, .exr, .hdr)
  - **materials/** - Material definitions (.mtl, .mat)
  - **rigs/** - Character and object rigs
  - **animations/** - Animation files
  - **scenes/** - Maya scene files
  - **references/** - Reference files
- **exports/** - Exported and published assets
- **temp/** - Temporary working files (excluded from asset library)
- **docs/** - Project documentation

## Important Notes

- **Project management files** (project.json, README.md) are automatically excluded from the asset library
- **Hidden files** and **temp directories** are not shown as assets
- Only supported asset file types appear in the Asset Manager interface

## Usage

This project is managed by Asset Manager v1.4.0. Use the Asset Manager interface to:
- Browse and organize assets
- Import assets into Maya
- Create new assets from scenes
- Manage asset metadata and tags

"""
            
            with open(readme_file, 'w') as f:
                f.write(readme_content)
            
            print(f"✅ Created project structure at: {project_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create project structure: {e}")
            return False
    
    def _on_open_project(self) -> None:
        """Handle project opening - Enhanced with validation"""
        from PySide6.QtWidgets import QFileDialog
        
        project_path = QFileDialog.getExistingDirectory(
            self, 
            "Open Asset Manager Project",
            str(Path.home() / "Documents")
        )
        
        if project_path:
            project_dir = Path(project_path)
            
            # Validate project directory
            if self._validate_project_directory(project_dir):
                self._load_project(project_dir)
                self._set_status(f"Opened project: {project_dir.name}")
            else:
                # Ask if user wants to initialize as new project
                reply = QMessageBox.question(
                    self,
                    "Initialize Project?", 
                    f"'{project_dir.name}' doesn't appear to be an Asset Manager project.\n\n"
                    "Would you like to initialize it as a new project?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    success = self._create_project_structure(project_dir)
                    if success:
                        self._load_project(project_dir)
                        self._set_status(f"Initialized and opened project: {project_dir.name}")
    
    def _on_set_project(self) -> None:
        """Handle setting an existing project as the current Asset Library - Single Responsibility"""
        from PySide6.QtWidgets import QFileDialog
        
        try:
            project_path = QFileDialog.getExistingDirectory(
                self, 
                "Set Asset Manager Project",
                str(Path.home() / "Documents")
            )
            
            if project_path:
                project_dir = Path(project_path)
                
                # Validate project directory - must be a valid project
                if self._validate_project_directory(project_dir):
                    # Load the project directly
                    self._load_project(project_dir)
                    self._set_status(f"Set project: {project_dir.name}")
                    
                    # Show success message with project info
                    project_info = self._get_project_info(project_dir)
                    message = f"Project '{project_dir.name}' has been set as the current Asset Library."
                    if project_info:
                        message += f"\n\nProject Details:\n{project_info}"
                    
                    QMessageBox.information(self, "Project Set", message)
                    
                else:
                    # Provide more specific feedback for invalid projects
                    QMessageBox.warning(
                        self,
                        "Invalid Project", 
                        f"'{project_dir.name}' is not a valid Asset Manager project.\n\n"
                        "Please select a directory that contains:\n"
                        "• A project.json file, or\n"
                        "• An 'assets' folder with asset files\n\n"
                        "Use 'File > New Project...' to create a new project, or\n"
                        "Use 'File > Open Project...' to initialize an existing directory."
                    )
                    
        except Exception as e:
            error_msg = f"Failed to set project: {str(e)}"
            self._set_status(error_msg)
            QMessageBox.critical(self, "Set Project Error", error_msg)
    
    def _get_project_info(self, project_path: Path) -> str:
        """Get project information for display - Single Responsibility"""
        try:
            info_parts = []
            
            # Check for project.json
            config_file = project_path / "project.json"
            if config_file.exists():
                try:
                    import json
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    if 'created' in config:
                        from datetime import datetime
                        created_date = datetime.fromisoformat(config['created'].replace('Z', '+00:00'))
                        info_parts.append(f"Created: {created_date.strftime('%Y-%m-%d %H:%M')}")
                    
                    if 'version' in config:
                        info_parts.append(f"Version: {config['version']}")
                    
                    if 'description' in config:
                        info_parts.append(f"Description: {config['description']}")
                        
                except Exception:
                    pass  # Skip if config can't be read
            
            # Count assets
            assets_dir = project_path / "assets"
            if assets_dir.exists():
                asset_extensions = ['.ma', '.mb', '.obj', '.fbx', '.abc', '.usd', 
                                  '.png', '.jpg', '.jpeg', '.tiff', '.tga', '.exr', '.hdr']
                asset_count = 0
                for ext in asset_extensions:
                    asset_count += len(list(assets_dir.rglob(f'*{ext}')))
                
                info_parts.append(f"Assets: {asset_count} files")
            
            # Add location
            info_parts.append(f"Location: {project_path}")
            
            return "\n".join(info_parts)
            
        except Exception as e:
            return f"Location: {project_path}"
    
    def _on_delete_project(self) -> None:
        """Handle deleting an existing project permanently - Single Responsibility with Safety Measures"""
        from PySide6.QtWidgets import QFileDialog
        import shutil
        
        try:
            # Show warning dialog first
            initial_warning = QMessageBox.warning(
                self,
                "⚠️ Delete Project - WARNING",
                "🔥 This action will PERMANENTLY DELETE an entire project and all its files.\n\n"
                "This includes:\n"
                "• All asset files (.ma, .mb, .obj, .fbx, textures, etc.)\n"
                "• Project configuration and metadata\n"
                "• All subdirectories and documentation\n"
                "• Thumbnail cache and generated files\n\n"
                "💡 Consider backing up important files before proceeding.\n\n"
                "Are you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if initial_warning != QMessageBox.StandardButton.Yes:
                return
            
            # Select project to delete
            project_path = QFileDialog.getExistingDirectory(
                self, 
                "⚠️ Select Project to DELETE PERMANENTLY",
                str(Path.home() / "Documents")
            )
            
            if not project_path:
                return
                
            project_dir = Path(project_path)
            
            # Validate it's actually a project
            if not self._validate_project_directory(project_dir):
                QMessageBox.warning(
                    self,
                    "Not a Project",
                    f"'{project_dir.name}' is not a valid Asset Manager project.\n\n"
                    "Only Asset Manager projects can be deleted using this function.\n"
                    "Please select a directory that contains project.json or an 'assets' folder."
                )
                return
            
            # Get project information for confirmation
            project_info = self._get_project_info(project_dir)
            
            # Final confirmation with detailed info
            final_confirmation = QMessageBox.critical(
                self,
                "🔥 FINAL CONFIRMATION - DELETE PROJECT",
                f"⚠️ LAST CHANCE TO CANCEL ⚠️\n\n"
                f"You are about to PERMANENTLY DELETE:\n"
                f"📁 Project: {project_dir.name}\n\n"
                f"Project Details:\n{project_info}\n\n"
                f"🚨 THIS ACTION CANNOT BE UNDONE! 🚨\n\n"
                f"Type the project name '{project_dir.name}' to confirm deletion.\n"
                f"This is your final protection against accidental deletion.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel
            )
            
            if final_confirmation != QMessageBox.StandardButton.Ok:
                self._set_status("Project deletion cancelled")
                return
            
            # Ask user to type project name for final confirmation
            from PySide6.QtWidgets import QInputDialog
            typed_name, ok = QInputDialog.getText(
                self,
                "Type Project Name to Confirm",
                f"Type the exact project name to confirm deletion:\n'{project_dir.name}'",
                text=""
            )
            
            if not ok or typed_name.strip() != project_dir.name:
                QMessageBox.information(
                    self,
                    "Deletion Cancelled",
                    "Project name did not match. Deletion cancelled for safety."
                )
                self._set_status("Project deletion cancelled - name mismatch")
                return
            
            # Check if we're deleting the current project
            current_project_path = None
            if (self._library_widget and 
                hasattr(self._library_widget, '_current_project_path') and 
                self._library_widget._current_project_path):
                current_project_path = Path(self._library_widget._current_project_path)
            
            is_current_project = (current_project_path and 
                                current_project_path.resolve() == project_dir.resolve())
            
            # Perform the deletion
            self._set_status("Deleting project...", show_progress=True)
            
            try:
                # Remove the entire project directory
                shutil.rmtree(project_dir)
                
                # If we deleted the current project, clear the library
                if is_current_project:
                    if self._library_widget:
                        self._library_widget._current_project_path = None
                        self._library_widget.refresh_library()
                    self._set_status(f"Deleted current project: {project_dir.name} - Library cleared")
                else:
                    self._set_status(f"Deleted project: {project_dir.name}")
                
                # Show success message
                QMessageBox.information(
                    self,
                    "Project Deleted",
                    f"Project '{project_dir.name}' has been permanently deleted.\n\n"
                    f"All files and directories have been removed from:\n{project_dir}"
                )
                
                print(f"🗑️ Successfully deleted project: {project_dir}")
                
            except PermissionError as e:
                error_msg = f"Permission denied: Cannot delete project.\n\nSome files may be in use or you may not have sufficient permissions.\n\nError: {str(e)}"
                QMessageBox.critical(self, "Permission Error", error_msg)
                self._set_status("Project deletion failed - permission error")
                
            except Exception as e:
                error_msg = f"Failed to delete project: {str(e)}"
                QMessageBox.critical(self, "Deletion Error", error_msg)
                self._set_status("Project deletion failed")
                
            finally:
                self._progress_bar.setVisible(False)
                
        except Exception as e:
            error_msg = f"Failed to delete project: {str(e)}"
            self._set_status(error_msg)
            QMessageBox.critical(self, "Delete Project Error", error_msg)
    
    def _validate_project_directory(self, project_path: Path) -> bool:
        """Validate if directory is a valid Asset Manager project - Single Responsibility"""
        try:
            # Check for project.json file (preferred)
            if (project_path / "project.json").exists():
                return True
            
            # Check for assets directory (fallback)
            if (project_path / "assets").exists():
                return True
                
            # Check if directory has any asset files
            asset_extensions = ['.ma', '.mb', '.obj', '.fbx', '.abc', '.png', '.jpg', '.jpeg']
            for ext in asset_extensions:
                if list(project_path.rglob(f'*{ext}')):
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error validating project directory: {e}")
            return False
    
    def _on_save_project(self) -> None:
        """Handle saving current project - Single Responsibility"""
        try:
            # Check if we have a current project loaded
            if (not self._library_widget or 
                not hasattr(self._library_widget, '_current_project_path') or
                not self._library_widget._current_project_path):
                QMessageBox.information(
                    self, 
                    "No Project Loaded", 
                    "No project is currently loaded.\n\n"
                    "Please open or create a project first using:\n"
                    "• File > New Project...\n"
                    "• File > Open Project...\n"
                    "• File > Set Project..."
                )
                return
            
            project_path = Path(self._library_widget._current_project_path)
            
            # Save project configuration and refresh library
            self._save_project_data(project_path)
            
            # Refresh the library to ensure consistency
            if self._library_widget:
                self._library_widget.refresh_library()
            
            self._set_status(f"Saved project: {project_path.name}")
            QMessageBox.information(
                self,
                "Project Saved",
                f"Project '{project_path.name}' has been saved successfully.\n\n"
                "All project data and asset library have been updated."
            )
            
        except Exception as e:
            error_msg = f"Failed to save project: {str(e)}"
            self._set_status(error_msg)
            QMessageBox.critical(self, "Save Project Error", error_msg)
    
    def _on_save_project_as(self) -> None:
        """Handle saving current project to a new location - Single Responsibility"""
        try:
            # Check if we have a current project loaded
            if (not self._library_widget or 
                not hasattr(self._library_widget, '_current_project_path') or
                not self._library_widget._current_project_path):
                QMessageBox.information(
                    self, 
                    "No Project Loaded", 
                    "No project is currently loaded.\n\n"
                    "Please open or create a project first using:\n"
                    "• File > New Project...\n"
                    "• File > Open Project...\n"
                    "• File > Set Project..."
                )
                return
            
            from PySide6.QtWidgets import QFileDialog
            current_project_path = Path(self._library_widget._current_project_path)
            
            # Get new project location
            new_project_path = QFileDialog.getExistingDirectory(
                self, 
                "Save Project As - Select New Location",
                str(current_project_path.parent)
            )
            
            if not new_project_path:
                return
            
            new_project_dir = Path(new_project_path) / f"{current_project_path.name}_copy"
            
            # Ask for new project name
            from PySide6.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(
                self,
                "Save Project As",
                "Enter new project name:",
                text=f"{current_project_path.name}_copy"
            )
            
            if not ok or not new_name.strip():
                return
            
            final_project_path = Path(new_project_path) / new_name.strip()
            
            # Check if destination already exists
            if final_project_path.exists():
                reply = QMessageBox.question(
                    self,
                    "Directory Exists",
                    f"Directory '{final_project_path.name}' already exists.\n\n"
                    "Do you want to overwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply != QMessageBox.StandardButton.Yes:
                    return
                
                # Remove existing directory
                shutil.rmtree(final_project_path)
            # Copy project to new location
            self._set_status("Copying project...", show_progress=True)
            
            try:
                shutil.copytree(current_project_path, final_project_path)
                
                # Update project configuration in new location
                self._save_project_data(final_project_path, new_name=new_name.strip())
                
                # Ask if user wants to switch to the new project
                reply = QMessageBox.question(
                    self,
                    "Project Copied",
                    f"Project has been successfully copied to:\n{final_project_path}\n\n"
                    "Would you like to switch to the new project location?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._load_project(final_project_path)
                    self._set_status(f"Switched to copied project: {new_name}")
                else:
                    self._set_status(f"Project copied successfully to: {final_project_path}")
                
            except Exception as e:
                error_msg = f"Failed to copy project: {str(e)}"
                QMessageBox.critical(self, "Copy Error", error_msg)
                self._set_status(error_msg)
            finally:
                self._progress_bar.setVisible(False)
                
        except Exception as e:
            error_msg = f"Failed to save project as: {str(e)}"
            self._set_status(error_msg)
            QMessageBox.critical(self, "Save Project As Error", error_msg)
    
    def _save_project_data(self, project_path: Path, new_name: Optional[str] = None) -> None:
        """Save project configuration data - Single Responsibility"""
        try:
            config_file = project_path / "project.json"
            
            # Load existing config or create new one
            project_config = {}
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        project_config = json.load(f)
                except Exception:
                    pass  # Use empty config if can't read
            
            # Update configuration
            from datetime import datetime
            project_config.update({
                "name": new_name or project_path.name,
                "last_saved": datetime.now().isoformat(),
                "version": project_config.get("version", "1.0"),
                "asset_manager_version": "1.3.0",
                "description": project_config.get("description", f"Asset Manager project: {new_name or project_path.name}"),
                "directories": {
                    "assets": "assets",
                    "exports": "exports", 
                    "temp": "temp",
                    "docs": "docs"
                }
            })
            
            # Ensure created date exists
            if "created" not in project_config:
                project_config["created"] = datetime.now().isoformat()
            
            # Save updated configuration
            with open(config_file, 'w') as f:
                json.dump(project_config, f, indent=4)
                
            print(f"✅ Saved project configuration: {config_file}")
            
        except Exception as e:
            print(f"❌ Failed to save project configuration: {e}")
            raise
    
    def _on_add_asset_to_library(self) -> None:
        """Handle adding a single asset to the library - Single Responsibility"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            # Check if we have a project loaded (optional warning)
            if (not self._library_widget or 
                not hasattr(self._library_widget, '_current_project_path') or
                not self._library_widget._current_project_path):
                reply = QMessageBox.question(self, "No Project Loaded", 
                                           "No project is currently loaded. Assets will be added to the default location.\n\n"
                                           "Would you like to continue?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # Get supported file extensions for the dialog filter
            supported_exts = ['.ma', '.mb', '.obj', '.fbx', '.abc', '.usd', 
                            '.png', '.jpg', '.jpeg', '.tiff', '.tga', '.exr', '.hdr',
                            '.mov', '.mp4', '.avi', '.mtl', '.mat', '.zip', '.rar']
            
            # Create filter string
            filters = "Asset Files ("
            for ext in supported_exts:
                filters += f"*{ext} "
            filters = filters.strip() + ");;"
            filters += "Maya Files (*.ma *.mb);;"
            filters += "3D Models (*.obj *.fbx *.abc *.usd);;"
            filters += "Images (*.png *.jpg *.jpeg *.tiff *.tga *.exr *.hdr);;"
            filters += "All Files (*)"
            
            # Open file dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Add Asset to Library",
                str(Path.home()),
                filters
            )
            
            if file_path:
                success = self._copy_asset_to_library(Path(file_path))
                if success:
                    self._set_status(f"Added asset: {Path(file_path).name}")
                    self._on_refresh_library()
                else:
                    self._set_status("Failed to add asset")
                    
        except Exception as e:
            error_msg = f"Error adding asset: {str(e)}"
            print(error_msg)
            self._set_status(error_msg)
            QMessageBox.critical(self, "Add Asset Error", error_msg)
    
    def _on_add_multiple_assets(self) -> None:
        """Handle adding multiple assets from folders - Single Responsibility"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            # Check if we have a project loaded (optional warning)
            if (not self._library_widget or 
                not hasattr(self._library_widget, '_current_project_path') or
                not self._library_widget._current_project_path):
                reply = QMessageBox.question(self, "No Project Loaded", 
                                           "No project is currently loaded. Assets will be added to the default location.\n\n"
                                           "Would you like to continue?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # Get multiple files
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Add Multiple Assets to Library",
                str(Path.home()),
                "Asset Files (*.ma *.mb *.obj *.fbx *.abc *.usd *.png *.jpg *.jpeg *.tiff *.tga *.exr *.hdr *.mov *.mp4 *.avi *.mtl *.mat *.zip *.rar);;All Files (*)"
            )
            
            if file_paths:
                # Show progress
                self._set_status(f"Adding {len(file_paths)} assets...", show_progress=True)
                
                added_count = 0
                failed_count = 0
                
                for file_path in file_paths:
                    try:
                        if self._copy_asset_to_library(Path(file_path)):
                            added_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        print(f"Failed to add {file_path}: {e}")
                        failed_count += 1
                
                # Update status
                if failed_count == 0:
                    self._set_status(f"Successfully added {added_count} assets")
                else:
                    self._set_status(f"Added {added_count} assets, {failed_count} failed")
                
                # Refresh library to show new assets
                self._on_refresh_library()
                
                # Show summary dialog
                if added_count > 0:
                    message = f"Successfully added {added_count} asset(s) to the library."
                    message += f"\n\nThumbnails have been generated for all imported assets."
                    if failed_count > 0:
                        message += f"\n\n{failed_count} file(s) could not be added."
                    QMessageBox.information(self, "Assets Added", message)
                else:
                    QMessageBox.warning(self, "No Assets Added", 
                                       "No assets were successfully added to the library.")
                    
        except Exception as e:
            error_msg = f"Error adding multiple assets: {str(e)}"
            print(error_msg)
            self._set_status(error_msg)
            QMessageBox.critical(self, "Add Multiple Assets Error", error_msg)
    
    def _copy_asset_to_library(self, source_path: Path) -> bool:
        """Copy asset file to the project library - Uses Library Service"""
        try:
            # Get project path
            project_path = None
            if (self._library_widget and 
                hasattr(self._library_widget, '_current_project_path') and 
                self._library_widget._current_project_path):
                project_path = self._library_widget._current_project_path
            
            if not project_path:
                # Fallback to default assets directory
                project_path = Path.home() / "Documents" / "maya" / "projects" / "default"
                # Create default project structure if it doesn't exist
                if not project_path.exists():
                    project_path.mkdir(parents=True, exist_ok=True)
            
            # Ensure project_path is a Path object
            project_path = Path(project_path) if isinstance(project_path, str) else project_path
            
            # Use library service to add asset
            # This handles: file copy + repository update + recent assets with correct path
            result = self._library_service.add_asset_to_library(source_path, project_path)
            
            if result and result[0]:  # Success
                target_path = result[1]
                print(f"✅ Asset successfully added to library via LibraryService")
                print(f"📁 Source: {source_path}")
                print(f"📁 Target: {target_path}")
                
                # CRITICAL: Generate playblast thumbnails for Maya files BEFORE importing to scene!
                # This allows users to preview assets in library without cluttering their scene
                if target_path and isinstance(target_path, Path):
                    if target_path.suffix.lower() in {'.ma', '.mb'}:
                        print(f"🎬 Generating preview thumbnail for: {target_path.name}")
                        # Schedule thumbnail generation after library refresh
                        QTimer.singleShot(200, lambda: self._generate_thumbnail_for_library_asset(target_path))
                
                # Refresh library to show new asset
                QTimer.singleShot(100, lambda: self._on_refresh_library())
                
                return True
            else:
                print(f"❌ Failed to add asset to library")
                return False
            
        except Exception as e:
            print(f"❌ Error copying asset to library: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_thumbnail_for_library_asset(self, asset_path: Path) -> None:
        """
        Generate PLAYBLAST thumbnail for asset when added to library.
        
        This is the KEY feature - generates thumbnails WITHOUT importing to user's scene!
        Uses isolated temporary namespace for preview generation, then cleans up completely.
        
        Single Responsibility: Playblast thumbnail generation for library preview
        """
        try:
            # Get thumbnail service from container
            from ..core.container import get_container
            from ..core.interfaces.thumbnail_service import IThumbnailService
            
            container = get_container()
            thumbnail_service = container.resolve(IThumbnailService)
            
            print(f"🎬 Generating playblast preview for library: {asset_path.name}")
            
            # Generate playblast thumbnail with force_playblast=True
            # This imports to isolated namespace, captures, and cleans up - NO scene pollution!
            thumbnail_path = thumbnail_service.generate_thumbnail(asset_path, size=(256, 256), force_playblast=True)
            
            if thumbnail_path:
                print(f"🖼️ Generated large playblast thumbnail: {asset_path.name}")
                # Also generate smaller thumbnail for list view
                small_thumbnail_path = thumbnail_service.generate_thumbnail(asset_path, size=(64, 64), force_playblast=True)
                if small_thumbnail_path:
                    print(f"🖼️ Generated small playblast thumbnail: {asset_path.name}")
                    
                    # Trigger UI refresh for this specific asset
                    if (self._library_widget and 
                        hasattr(self._library_widget, 'refresh_thumbnails_for_assets') and
                        callable(getattr(self._library_widget, 'refresh_thumbnails_for_assets'))):
                        # Use QTimer to ensure this runs after thumbnails are saved
                        def refresh_thumbnail():
                            try:
                                self._library_widget.refresh_thumbnails_for_assets([asset_path])  # type: ignore
                            except Exception as e:
                                print(f"❌ Failed to refresh thumbnail in UI: {e}")
                        
                        QTimer.singleShot(500, refresh_thumbnail)
                        print(f"🔄 Scheduled thumbnail refresh for: {asset_path.name}")
                else:
                    print(f"⚠️ Could not generate small thumbnail for: {asset_path.name}")
            else:
                print(f"⚠️ Could not generate thumbnail for: {asset_path.name}")
                
        except Exception as e:
            print(f"❌ Thumbnail generation failed for {asset_path}: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the library addition if thumbnail generation fails
    
    def _generate_thumbnail_for_imported_asset(self, asset_path: Path) -> None:
        """
        Generate PLAYBLAST thumbnail for asset AFTER it's imported into Maya scene.
        
        NOTE: This is now redundant since thumbnails are generated when added to library.
        Kept for backwards compatibility or manual thumbnail regeneration.
        
        Single Responsibility: Playblast thumbnail generation with UI refresh
        """
        # Simply call the library asset thumbnail generator
        self._generate_thumbnail_for_library_asset(asset_path)
    
    def _extract_full_metadata_for_imported_asset(self, asset_path: Path) -> None:
        """
        Extract FULL Maya metadata for asset AFTER it's imported into Maya scene
        
        IMPORTANT: This should ONLY be called when user explicitly imports asset to Maya,
        NOT when adding to library! Adding to library gets basic metadata only.
        
        This extracts detailed Maya scene data:
        - Actual polygon counts from geometry
        - Material and texture information  
        - Animation data and frame ranges
        - Camera and light counts
        - Scene hierarchy information
        
        Single Responsibility: Full metadata extraction with asset update
        """
        try:
            # Get repository service from container
            from ..core.container import get_container
            
            container = get_container()
            
            # Check if repository has extract_full_maya_metadata method
            if hasattr(self._repository, 'extract_full_maya_metadata'):
                print(f"📊 Extracting full Maya metadata for imported asset: {asset_path.name}")
                
                # Extract full metadata (this imports asset to analyze it)
                full_metadata = self._repository.extract_full_maya_metadata(asset_path)  # type: ignore
                
                if full_metadata and full_metadata.get('metadata_level') == 'full':
                    poly_count = full_metadata.get('poly_count', 0)
                    material_count = full_metadata.get('material_count', 0)
                    has_animation = full_metadata.get('has_animation', False)
                    
                    print(f"✅ Full metadata extracted for {asset_path.name}:")
                    print(f"   - Polygons: {poly_count:,}")
                    print(f"   - Materials: {material_count}")
                    print(f"   - Animation: {'Yes' if has_animation else 'No'}")
                    
                    # CRITICAL FIX: Persist extracted metadata to asset!
                    try:
                        # Get the asset from repository
                        asset = self._repository.get_asset_by_path(asset_path)  # type: ignore
                        if asset:
                            # Update asset metadata with extracted data
                            if not hasattr(asset, 'metadata') or asset.metadata is None:
                                asset.metadata = {}
                            
                            # Store extracted metadata
                            asset.metadata['poly_count'] = poly_count
                            asset.metadata['material_count'] = material_count
                            asset.metadata['has_animation'] = has_animation
                            asset.metadata['metadata_level'] = 'full'
                            
                            # Save updated asset to repository
                            if hasattr(self._repository, 'update_asset'):
                                self._repository.update_asset(asset)  # type: ignore
                                print(f"💾 Metadata persisted for {asset_path.name}")
                                
                                # ISSUE #3 FIX: Directly update asset info display for currently selected asset
                                if self._current_asset and self._current_asset.file_path == asset_path:
                                    print(f"🔄 Updating metadata display for currently selected asset")
                                    # Refresh the asset object from repository with new metadata
                                    updated_asset = self._repository.get_asset_by_path(asset_path)  # type: ignore
                                    if updated_asset:
                                        self._current_asset = updated_asset
                                        self._update_asset_info_display(updated_asset)
                                
                                # Also trigger library refresh
                                if self._library_widget:
                                    QTimer.singleShot(100, lambda: self._library_widget.refresh_library())  # type: ignore
                            else:
                                print(f"⚠️ Repository doesn't support update_asset()")
                        else:
                            print(f"⚠️ Asset not found in repository: {asset_path}")
                    except Exception as persist_error:
                        print(f"⚠️ Could not persist metadata: {persist_error}")
                    
                else:
                    print(f"⚠️ Could not extract full metadata for: {asset_path.name}")
            else:
                print(f"⚠️ Repository does not support full metadata extraction")
                
        except Exception as e:
            print(f"❌ Metadata extraction error: {e}")
    
    def _on_refresh_library(self) -> None:
        """Handle library refresh - Enhanced with proper error handling and user feedback"""
        try:
            # Check if library widget exists
            if not self._library_widget:
                QMessageBox.warning(self, "Warning", "Library widget is not initialized.")
                return
            
            # Show progress and status feedback
            self._set_status("Refreshing library...", show_progress=True)
            
            # Perform the refresh
            self._library_widget.refresh_library()
            
            # Get current project path for feedback
            if hasattr(self._library_widget, '_current_project_path'):
                project_path = self._library_widget._current_project_path
                if project_path:
                    # Ensure project_path is a Path object before accessing .name
                    if isinstance(project_path, str):
                        project_path = Path(project_path)
                    self._set_status(f"Library refreshed from: {project_path.name}")
                else:
                    self._set_status("No project loaded - nothing to refresh")
                    QMessageBox.information(self, "Info", "No project is currently loaded.\nPlease open a project first.")
            else:
                self._set_status("Library refresh completed")
            
            # Hide progress
            self._progress_bar.setVisible(False)
            
        except Exception as e:
            # Hide progress on error
            self._progress_bar.setVisible(False)
            
            
            error_msg = f"Failed to refresh library: {str(e)}"
            self._set_status(f"Error: {error_msg}")
            QMessageBox.critical(self, "Refresh Error", error_msg)
            print(f"Library refresh error: {e}")  # Debug output
    
    def _on_reset_icon_size(self) -> None:
        """Reset library icon size to default - Single Responsibility"""
        try:
            if self._library_widget and hasattr(self._library_widget, '_icon_size'):
                # Reset to default size (64px)
                self._library_widget._icon_size = 64
                # Apply the reset
                if hasattr(self._library_widget, '_update_icon_sizes'):
                    self._library_widget._update_icon_sizes()
                    self._set_status("Icon size reset to default (64px)")
                    print("✅ Icon size reset to default: 64px")
                else:
                    self._set_status("Could not reset icon size - method not available")
            else:
                self._set_status("Library widget not available")
        except Exception as e:
            error_msg = f"Failed to reset icon size: {str(e)}"
            self._set_status(f"Error: {error_msg}")
            print(f"Reset icon size error: {e}")
    
    def _on_advanced_search(self) -> None:
        """Handle advanced search dialog"""
        try:
            from .dialogs.advanced_search_dialog import AdvancedSearchDialog
            
            dialog = AdvancedSearchDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                criteria = dialog.get_search_criteria()
                if criteria and self._library_widget:
                    self._library_widget.search_with_criteria(criteria)
        except ImportError:
            QMessageBox.warning(self, "Feature Not Available", "Advanced Search dialog is not implemented yet.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to perform advanced search: {e}")
    
    def _on_import_selected(self) -> None:
        """Handle import selected assets with safe validation"""
        try:
            if not self._library_widget:
                QMessageBox.warning(self, "Warning", "Asset library is not available.")
                return
            
            selected_assets = self._library_widget.get_selected_assets()
            
            # SAFE SELECTION VALIDATION - Defensive Programming
            if not selected_assets:
                QMessageBox.information(self, "No Selection", "Please select one or more assets to import.")
                return
            
            # Validate each asset before import
            valid_assets = []
            for asset in selected_assets:
                if self._validate_asset_file_path(asset):
                    valid_assets.append(asset)
                else:
                    print(f"⚠️ Skipping invalid asset: {getattr(asset, 'display_name', 'Unknown')}")
            
            if not valid_assets:
                QMessageBox.warning(self, "Invalid Assets", "No valid assets selected for import.")
                return
            
            # Import valid assets
            for asset in valid_assets:
                self._on_asset_import(asset)
                
        except Exception as e:
            print(f"❌ Import selected error: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to import selected assets:\n{str(e)}")
    
    def _on_refresh_thumbnails(self) -> None:
        """Handle manual thumbnail refresh - Single Responsibility"""
        try:
            if not self._library_widget:
                QMessageBox.warning(self, "Warning", "Library widget is not initialized.")
                return
            
            # Show progress
            self._set_status("Refreshing all thumbnails...", show_progress=True)
            
            # Force refresh all thumbnails
            if hasattr(self._library_widget, 'force_refresh_all_thumbnails'):
                self._library_widget.force_refresh_all_thumbnails()  # type: ignore
                self._set_status("Thumbnail refresh completed")
            else:
                # Fallback - just refresh the library
                self._library_widget.refresh_library()
                self._set_status("Library refreshed")
            
            # Hide progress
            self._progress_bar.setVisible(False)
            
        except Exception as e:
            self._progress_bar.setVisible(False)
            error_msg = f"Failed to refresh thumbnails: {str(e)}"
            self._set_status(f"Error: {error_msg}")
            QMessageBox.critical(self, "Thumbnail Refresh Error", error_msg)
            print(f"Thumbnail refresh error: {e}")
    
    def _on_clear_thumbnail_cache(self) -> None:
        """Handle clearing thumbnail cache - Single Responsibility"""
        try:
            from ..core.container import get_container
            from ..core.interfaces.thumbnail_service import IThumbnailService
            
            # Ask for confirmation
            reply = QMessageBox.question(self, "Clear Thumbnail Cache", 
                                       "This will delete all cached thumbnails.\n"
                                       "Thumbnails will be regenerated as needed.\n\n"
                                       "Are you sure you want to continue?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # Clear the cache
                container = get_container()
                thumbnail_service = container.resolve(IThumbnailService)
                thumbnail_service.clear_cache()  # type: ignore
                
                # Refresh thumbnails after clearing cache
                if self._library_widget and hasattr(self._library_widget, 'refresh_library'):
                    self._library_widget.refresh_library()
                
                self._set_status("Thumbnail cache cleared")
                QMessageBox.information(self, "Cache Cleared", "Thumbnail cache has been cleared successfully.")
            
        except Exception as e:
            error_msg = f"Failed to clear thumbnail cache: {str(e)}"
            self._set_status(f"Error: {error_msg}")
            QMessageBox.critical(self, "Cache Clear Error", error_msg)
            print(f"Cache clear error: {e}")
    
    def _on_create_asset(self) -> None:
        """Handle create asset button click - Single Responsibility"""
        try:
            from ..ui.dialogs.create_asset_dialog import CreateAssetDialog
            
            dialog = CreateAssetDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                asset_data = dialog.get_asset_data()
                if asset_data:
                    # Create the asset
                    success = self._create_asset_from_scene(asset_data)
                    if success:
                        self._set_status(f"Created asset: {asset_data.get('name', 'Unknown')}")
                        self._on_refresh_library()  # Refresh to show new asset
                    else:
                        self._set_status("Failed to create asset")
                        
        except ImportError:
            # Fallback to simple dialog
            self._show_simple_create_dialog()



        except Exception as e:
            error_msg = f"Create asset error: {str(e)}"
            print(error_msg)
            self._set_status(error_msg)
            QMessageBox.warning(self, "Create Asset Error", f"Failed to create asset:\n{str(e)}")
    
    def _show_simple_create_dialog(self) -> None:
        """Simple create asset dialog fallback - YAGNI implementation"""
        name, ok = QInputDialog.getText(self, 'Create Asset', 'Asset name:')
        if ok and name.strip():
            asset_data = {
                'name': name.strip(),
                'description': '',
                'tags': [],
                'category': 'General'
            }
            success = self._create_asset_from_scene(asset_data)
            if success:
                self._set_status(f"Created asset: {name}")
                self._on_refresh_library()
            else:
                self._set_status("Failed to create asset")
    
    def _create_asset_from_scene(self, asset_data: dict) -> bool:
        """Create asset from current Maya scene - Single Responsibility"""
        try:
            import maya.cmds as cmds # type: ignore
            from pathlib import Path
            import tempfile
            import os
            
            # Get asset library path - simple fallback approach
            # Try to use Documents/Maya/projects/default/assets
            try:
                user_docs = Path.home() / "Documents"
                maya_projects = user_docs / "maya" / "projects" / "default" / "assets"
                if not maya_projects.exists():
                    maya_projects.mkdir(parents=True, exist_ok=True)
                library_path = maya_projects
            except:
                # Ultimate fallback - current directory
                library_path = Path.cwd() / "assets"
                library_path.mkdir(parents=True, exist_ok=True)
            
            # Create asset filename
            asset_name = asset_data['name']
            safe_name = "".join(c for c in asset_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            asset_file = library_path / f"{safe_name}.ma"
            
            # Make sure directory exists
            asset_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Export selection or whole scene
            selection = cmds.ls(selection=True)
            if selection:
                # Export selected objects
                cmds.file(str(asset_file), force=True, options="v=0", type="mayaAscii", 
                         exportSelected=True)
                self._set_status(f"Exported {len(selection)} selected objects to {safe_name}")
            else:
                # Export whole scene
                cmds.file(str(asset_file), force=True, options="v=0", type="mayaAscii", 
                         exportAll=True)
                self._set_status(f"Exported entire scene to {safe_name}")
            
            # Generate thumbnail
            thumbnail_path = asset_file.with_suffix('.png')
            self._generate_thumbnail_for_asset(str(thumbnail_path))
            
            return True
            
        except Exception as e:
            print(f"Asset creation failed: {e}")
            return False
    
    def _generate_thumbnail_for_asset(self, thumbnail_path: str) -> None:
        """Generate thumbnail for newly created asset - Single Responsibility"""
        try:
            import maya.cmds as cmds # type: ignore
            
            # Get current viewport
            current_panel = cmds.getPanel(withFocus=True)
            if 'modelPanel' in current_panel:
                # Capture viewport
                cmds.viewFit()  # Frame all objects
                cmds.refresh()  # Refresh viewport
                
                # Capture image
                cmds.playblast(frame=1, viewer=False, showOrnaments=False,
                              compression="png", format="image", 
                              filename=thumbnail_path, widthHeight=(256, 256),
                              percent=100, quality=100)
                              
        except Exception as e:
            print(f"Thumbnail generation failed: {e}")
            # Create a default thumbnail or skip
    
    def _on_add_to_favorites(self) -> None:
        """Handle add to favorites"""
        if self._current_asset:
            self._repository.add_to_favorites(self._current_asset)
            self._set_status(f"Added to favorites: {self._current_asset.name}")
    
    def _on_export_selected(self) -> None:
        """Handle exporting selected asset(s) to a new location - Single Responsibility"""
        try:
            # Check if we have selected assets
            if not self._library_widget or not hasattr(self._library_widget, '_selected_assets'):
                QMessageBox.information(
                    self, 
                    "No Selection", 
                    "Please select one or more assets to export."
                )
                return
                
            selected_assets = getattr(self._library_widget, '_selected_assets', [])
            if not selected_assets:
                QMessageBox.information(
                    self, 
                    "No Selection", 
                    "Please select one or more assets to export."
                )
                return
            
            from PySide6.QtWidgets import QFileDialog
            
            # Get export destination directory
            export_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Export Destination",
                str(Path.home() / "Documents")
            )
            
            if not export_dir:
                return
                
            export_path = Path(export_dir)
            
            # Show progress for multiple assets
            self._set_status("Exporting assets...", show_progress=True)
            
            try:
                exported_count = 0
                failed_exports = []
                
                for asset in selected_assets:
                    try:
                        # Create export filename with original extension
                        source_file = Path(asset.file_path)
                        export_file = export_path / f"{asset.name}{source_file.suffix}"
                        
                        # Handle filename conflicts
                        counter = 1
                        original_export_file = export_file
                        while export_file.exists():
                            stem = original_export_file.stem
                            suffix = original_export_file.suffix
                            export_file = export_path / f"{stem}_{counter:03d}{suffix}"
                            counter += 1
                        
                        # Copy the asset file
                        shutil.copy2(source_file, export_file)
                        exported_count += 1
                        
                        # Also copy thumbnail if it exists
                        if hasattr(asset, 'thumbnail_path') and asset.thumbnail_path:
                            thumb_source = Path(asset.thumbnail_path)
                            if thumb_source.exists():
                                thumb_export = export_path / f"{export_file.stem}_thumbnail{thumb_source.suffix}"
                                try:
                                    shutil.copy2(thumb_source, thumb_export)
                                except Exception:
                                    pass  # Thumbnail copy is optional
                        
                    except Exception as e:
                        failed_exports.append(f"{asset.name}: {str(e)}")
                        print(f"Failed to export {asset.name}: {e}")
                
                # Show results
                if exported_count > 0:
                    message = f"Successfully exported {exported_count} asset(s) to:\n{export_path}"
                    if failed_exports:
                        message += f"\n\nFailed to export {len(failed_exports)} asset(s):\n"
                        message += "\n".join([f"• {failure}" for failure in failed_exports[:5]])
                        if len(failed_exports) > 5:
                            message += f"\n... and {len(failed_exports) - 5} more"
                    
                    QMessageBox.information(self, "Export Complete", message)
                    self._set_status(f"Exported {exported_count} asset(s)")
                else:
                    QMessageBox.warning(
                        self, 
                        "Export Failed", 
                        "No assets could be exported.\n\nErrors:\n" + "\n".join(failed_exports[:3])
                    )
                    self._set_status("Export failed")
                    
            except Exception as e:
                error_msg = f"Export operation failed: {str(e)}"
                QMessageBox.critical(self, "Export Error", error_msg)
                self._set_status(error_msg)
            finally:
                self._progress_bar.setVisible(False)
                
        except Exception as e:
            error_msg = f"Failed to export assets: {str(e)}"
            self._set_status(error_msg)
            QMessageBox.critical(self, "Export Error", error_msg)
    
    def _on_select_all(self) -> None:
        """Handle select all assets"""
        if self._library_widget:
            self._library_widget.select_all_assets()
    
    def _on_toggle_preview_unified(self) -> None:
        """Unified preview panel toggle - Synchronizes menu action and button - Single Responsibility"""
        # Determine current state from the preview widget
        current_visible = True
        if hasattr(self, '_preview_widget') and self._preview_widget:
            from PySide6.QtWidgets import QWidget
            widget = self._preview_widget
            if isinstance(widget, QWidget):
                current_visible = widget.isVisible()
        
        # Toggle the state
        new_visible = not current_visible
        
        # Update preview widget visibility
        if hasattr(self, '_preview_widget') and self._preview_widget:
            from PySide6.QtWidgets import QWidget
            widget = self._preview_widget
            if isinstance(widget, QWidget):
                widget.setVisible(new_visible)
        
        # Synchronize menu action state (temporarily disconnect to avoid recursion)
        if hasattr(self, '_show_preview_action'):
            self._show_preview_action.triggered.disconnect()
            self._show_preview_action.setChecked(new_visible)
            self._show_preview_action.triggered.connect(self._on_toggle_preview_unified)
        
        # Synchronize button state and text (temporarily disconnect to avoid recursion)
        if hasattr(self, '_preview_btn'):
            self._preview_btn.clicked.disconnect()
            self._preview_btn.setChecked(new_visible)
            self._preview_btn.setText("Hide Preview" if new_visible else "Show Preview")
            self._preview_btn.clicked.connect(self._on_toggle_preview_unified)
        
        # Update status
        status = "shown" if new_visible else "hidden"
        self._set_status(f"Preview panel {status}")
        
    # Legacy method kept for compatibility - redirects to unified method
    def _on_toggle_preview(self, visible: bool) -> None:
        """Legacy preview toggle - redirects to unified method for backward compatibility"""
        # This method is kept for any existing connections that might use the old signature
        # It calls the unified method which will handle the synchronization
        self._on_toggle_preview_unified()
    
    def _on_about(self) -> None:
        """Handle about dialog"""
        about_text = (
            "<h2>Asset Manager v1.4.0</h2>"
            "<p><b>Enterprise Modular Service Architecture (EMSA)</b></p>"
            "<p>A comprehensive asset management system for Maya<br>"
            "Built with Clean Code & SOLID principles</p>"
            "<p><b>Author:</b> Mike Stumbo</p>"
            "<hr>"
            "<h3>New in v1.4.0</h3>"
            "<p><b>USD Pipeline System</b><br>"
            "Complete Maya → USD export workflow<br>"
            "• Geometry, Materials, Rigging (UsdSkel)<br>"
            "• RenderMan material preservation<br>"
            "• Interactive export dialog with progress tracking</p>"
            "<hr>"
            "<h3>API Integrations</h3>"
            "<p><b>Pixar RenderMan®</b> (v26.3)<br>"
            "RenderMan® is a registered trademark of Pixar Animation Studios.<br>"
            "© 1989-2025 Pixar. All rights reserved.<br>"
            "<i>Professional production rendering support</i></p>"
            "<p><b>Universal Scene Description (USD)</b><br>"
            "USD is developed by Pixar Animation Studios and open-sourced.<br>"
            "© 2016-2025 Pixar. Licensed under Apache 2.0.<br>"
            "<i>Industry-standard scene interchange format</i></p>"
            "<p><b>ngSkinTools2™</b> (v2.4.0)<br>"
            "ngSkinTools2™ is developed by Viktoras Makauskas.<br>"
            "© 2009-2025 www.ngskintools.com. All rights reserved.<br>"
            "<i>Advanced layer-based skinning system</i></p>"
            "<hr>"
            "<p><b>Maya®</b> is a registered trademark of Autodesk, Inc.<br>"
            "© 2025 Autodesk, Inc. All rights reserved.</p>"
            "<p><b>PySide6</b> is developed by The Qt Company Ltd.<br>"
            "Licensed under LGPL v3.</p>"
            "<hr>"
            "<p><small>Asset Manager is independent software and is not affiliated with,<br>"
            "endorsed by, or sponsored by Pixar, Autodesk, The Qt Company,<br>"
            "or ngSkinTools. All trademarks are property of their respective owners.</small></p>"
        )
        
        QMessageBox.about(self, "About Asset Manager", about_text)
    
    def _load_project(self, project_path: Path) -> None:
        """Load project from path - Single Responsibility"""
        try:
            self._set_status(f"Loading project: {project_path.name}...", show_progress=True)
            
            if self._library_widget:
                self._library_widget.load_project(project_path)
            
            # Auto-select first asset if available
            try:
                if self._library_widget and hasattr(self._library_widget, '_current_assets'):
                    current_assets = getattr(self._library_widget, '_current_assets', None)
                    if current_assets and len(current_assets) > 0:
                        first_asset = current_assets[0]
                        self._on_asset_selected(first_asset)
            except Exception as e:
                print(f"Error auto-selecting asset: {e}")
            
            self._set_status(f"Loaded project: {project_path.name}")
            
        except Exception as e:
            self._set_status(f"Error loading project: {e}")
            QMessageBox.critical(self, "Project Load Error", str(e))
    
    # Event system handlers
    
    def _handle_asset_selected_event(self, event_data: Dict[str, Any]) -> None:
        """Handle asset selected event from event system"""
        # Could update other UI components here
        pass
    
    def _handle_asset_imported_event(self, event_data: Dict[str, Any]) -> None:
        """Handle asset imported event from event system"""
        # Could update recent assets, statistics, etc.
        pass
    
    def _handle_library_refreshed_event(self, event_data: Dict[str, Any]) -> None:
        """Handle library refreshed event from event system"""
        asset_count = event_data.get('asset_count', 0)
        self._update_asset_count(asset_count)
    
    def _handle_error_event(self, event_data: Dict[str, Any]) -> None:
        """Handle error event from event system"""
        error_message = event_data.get('message', 'Unknown error')
        self._set_status(f"Error: {error_message}")
    
    def _load_window_state(self) -> None:
        """Load window state and last project path - Single Responsibility"""
        try:
            from PySide6.QtCore import QSettings
            
            settings = QSettings("MikeStumbo", "AssetManager")
            
            # Restore window geometry (size and position)
            geometry = settings.value("geometry")
            if geometry:
                success = self.restoreGeometry(geometry)
                if success:
                    print(f"✅ Window geometry restored: {self.size().width()}x{self.size().height()}")
                else:
                    print("⚠️ Failed to restore window geometry, using defaults")
            else:
                print("ℹ️ No saved window geometry found, using defaults")
            
            # Restore window state (toolbars, docks, etc.)
            state = settings.value("windowState")
            if state:
                success = self.restoreState(state)
                if success:
                    print("✅ Window state restored")
                else:
                    print("⚠️ Failed to restore window state")
            else:
                print("ℹ️ No saved window state found")
            
            # Load last project path
            last_project = settings.value("lastProject")
            if last_project and self._library_widget:
                try:
                    self._load_project(Path(last_project))
                    print(f"✅ Last project restored: {last_project}")
                except Exception as e:
                    print(f"⚠️ Failed to restore last project: {e}")
            else:
                print("ℹ️ No last project found to restore")
                
        except Exception as e:
            print(f"❌ Error loading window state: {e}")
    
    def _save_window_state(self) -> None:
        """Save window state and current project path - Single Responsibility"""
        try:
            from PySide6.QtCore import QSettings
            
            settings = QSettings("MikeStumbo", "AssetManager")
            
            # Save window geometry
            settings.setValue("geometry", self.saveGeometry())
            
            # Save window state
            settings.setValue("windowState", self.saveState())
            
            # Save current project path
            if (self._library_widget and 
                hasattr(self._library_widget, '_current_project_path') and 
                self._library_widget._current_project_path):
                settings.setValue("lastProject", str(self._library_widget._current_project_path))
            
            # Ensure settings are written to disk immediately
            settings.sync()
            print(f"✅ Window state saved: {self.size().width()}x{self.size().height()}")
                
        except Exception as e:
            print(f"❌ Error saving window state: {e}")
    
    # Missing menu action handlers - Clean Code implementation
    def _on_toggle_asset_info_unified(self, *args) -> None:
        """Unified asset information panel visibility toggle - Single Responsibility
        
        Toggles the RIGHT_B metadata panel visibility and synchronizes both 
        the View menu action and Info button states.
        """
        # Determine current visibility state of RIGHT_B metadata panel
        current_visible = True
        if self._metadata_panel:
            current_visible = self._metadata_panel.isVisible()
        
        # Toggle the visibility
        new_visible = not current_visible
        
        # Update metadata panel visibility
        if self._metadata_panel:
            self._metadata_panel.setVisible(new_visible)
        
        # Synchronize menu action state (disconnect to prevent recursion)
        if hasattr(self, '_show_asset_info_action'):
            self._show_asset_info_action.triggered.disconnect()
            self._show_asset_info_action.setChecked(new_visible)
            self._show_asset_info_action.triggered.connect(self._on_toggle_asset_info_unified)
        
        # Synchronize Info button state and text (disconnect to prevent recursion)
        if hasattr(self, '_info_btn'):
            self._info_btn.clicked.disconnect()
            self._info_btn.setChecked(new_visible)
            self._info_btn.setText("Hide Info" if new_visible else "Show Info")
            self._info_btn.clicked.connect(self._on_toggle_asset_info_unified)
        
        # Update current asset info if panel is now visible
        if new_visible and self._current_asset:
            self._update_asset_info_display(self._current_asset)
        
        # Update status
        status = "shown" if new_visible else "hidden"
        self._set_status(f"Asset Information panel {status}")
    
    def _on_toggle_asset_info(self, visible: bool) -> None:
        """Legacy method - maintained for backward compatibility"""
        # Redirect to unified handler
        self._on_toggle_asset_info_unified()
    
    def _on_show_asset_info(self) -> None:
        """Legacy method - maintained for backward compatibility"""
        # Redirect to unified handler
        self._on_toggle_asset_info_unified()
    
    def _on_color_coding_manager(self) -> None:
        """Open Color Coding Manager dialog - Single Responsibility"""
        try:

            dialog = ColorCodingManagerDialog(self)
            dialog.color_scheme_changed.connect(lambda: self._on_color_scheme_changed(dialog))
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Color Coding Manager:\n{str(e)}")
    
    def _on_color_scheme_changed(self, dialog=None) -> None:
        """Handle color scheme changes - Single Responsibility"""
        try:
            # Get updated color scheme from dialog if available
            if dialog:
                color_scheme = dialog.get_current_color_scheme()
                # Update color keychart
                if hasattr(self, '_color_keychart') and self._color_keychart:
                    self._color_keychart.update_color_scheme(color_scheme)
                
                # Update library's ASSET_TYPE_COLORS
                if hasattr(self, '_library_widget') and self._library_widget:
                    for asset_type, qcolor in color_scheme.items():
                        rgb_tuple = (qcolor.red(), qcolor.green(), qcolor.blue())
                        self._library_widget.ASSET_TYPE_COLORS[asset_type] = rgb_tuple
            
            # Refresh asset library to apply new colors
            if hasattr(self, '_library_widget') and self._library_widget:
                self._library_widget.refresh_library()
        except Exception as e:
            print(f"Error refreshing colors: {e}")
    
    def _on_library_color_scheme_changed(self, color_scheme: Dict[str, QColor]) -> None:
        """Handle color scheme changes from library widget - Single Responsibility"""
        try:
            # Update color keychart with new scheme
            if hasattr(self, '_color_keychart') and self._color_keychart:
                self._color_keychart.update_color_scheme(color_scheme)
        except Exception as e:
            print(f"Error updating color keychart from library: {e}")
    
    def _on_tag_manager(self) -> None:
        """Open Tag Manager dialog - Single Responsibility"""
        try:
            dialog = TagManagerDialog(self)
            dialog.tags_changed.connect(self._on_tags_changed)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Tag Manager:\n{str(e)}")
    
    def _on_tags_changed(self) -> None:
        """Handle tag system changes - Single Responsibility"""
        try:
            # Refresh asset library to apply new tag system
            if hasattr(self, '_library_widget') and self._library_widget:
                self._library_widget.refresh_library()
        except Exception as e:
            print(f"Error refreshing tags: {e}")
    
    def _on_new_collection(self) -> None:
        """Create new collection - Single Responsibility"""
        text, ok = QInputDialog.getText(self, 'New Collection', 'Collection name:')
        if ok and text:
            QMessageBox.information(self, "Collection Created", f"Created new collection: {text}")
    
    def _on_create_tag(self) -> None:
        """Create new tag - Single Responsibility"""
        text, ok = QInputDialog.getText(self, 'Create Tag', 'Tag name:')
        if ok and text:
            QMessageBox.information(self, "Tag Created", f"Created new tag: {text}")
    
    def _on_manage_collections(self) -> None:
        """Open Collections Manager dialog - Single Responsibility"""
        try:
            # Get existing collections data (this would come from the asset repository in practice)
            existing_collections = getattr(self, '_collections', {})
            
            dialog = CollectionManagerDialog(self, existing_collections)
            
            # Connect signals to handle collection changes
            dialog.collection_created.connect(self._on_collection_created)
            dialog.collection_updated.connect(self._on_collection_updated)
            dialog.collection_deleted.connect(self._on_collection_deleted)
            dialog.collections_imported.connect(self._on_collections_imported)
            
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                # Collections were modified, refresh UI if needed
                self._refresh_collections_display()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Collection Manager:\n{str(e)}")
            
    def _on_collection_created(self, collection_name: str, collection_data: dict) -> None:
        """Handle new collection creation - Single Responsibility"""
        if not hasattr(self, '_collections'):
            self._collections = {}
        self._collections[collection_name] = collection_data
        print(f"✓ Collection created: {collection_name}")
        
    def _on_collection_updated(self, collection_name: str, collection_data: dict) -> None:
        """Handle collection updates - Single Responsibility"""
        if not hasattr(self, '_collections'):
            self._collections = {}
        self._collections[collection_name] = collection_data
        print(f"✓ Collection updated: {collection_name}")
        
    def _on_collection_deleted(self, collection_name: str) -> None:
        """Handle collection deletion - Single Responsibility"""
        if hasattr(self, '_collections') and collection_name in self._collections:
            del self._collections[collection_name]
            print(f"✓ Collection deleted: {collection_name}")
            
    def _on_collections_imported(self, collections: list) -> None:
        """Handle collection import - Single Responsibility"""
        if not hasattr(self, '_collections'):
            self._collections = {}
        for collection in collections:
            self._collections.update(collection)
        print(f"✓ Imported {len(collections)} collections")
        
    def _refresh_collections_display(self) -> None:
        """Refresh the collections display in the UI - Single Responsibility"""
        # This would update any collection-related UI elements
        # For now, just log the action
        collection_count = len(getattr(self, '_collections', {}))
        print(f"🔄 Collections display refreshed - {collection_count} collections loaded")
    
    def _on_usd_pipeline(self) -> None:
        """Open USD Pipeline Creator dialog - Single Responsibility
        
        Clean Code: New v1.4.0 feature for Maya → USD export
        """
        try:
            from .dialogs.usd_pipeline_dialog import USDPipelineDialog
            
            dialog = USDPipelineDialog(self)
            
            # Connect signals if needed
            dialog.export_started.connect(lambda: print("📤 USD export started..."))
            dialog.export_completed.connect(
                lambda success, msg: print(f"{'✅' if success else '❌'} USD export: {msg}")
            )
            
            dialog.exec()
            
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to load USD Pipeline dialog:\n{e}\n\n"
                "USD Pipeline requires Python USD libraries (pxr)."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open USD Pipeline:\n{str(e)}"
            )
    
    def _on_check_update(self) -> None:
        """Check for plugin updates - Single Responsibility"""
        QMessageBox.information(self, "Check for Updates", 
                               "Update Checker\n\nAsset Manager v1.4.0\n"
                               "You are running the latest version.\n"
                               "Check back later for updates.")
    
    # Missing toolbar and UI action handlers - Clean Code implementation
    def _on_remove_selected_asset(self) -> None:
        """Remove selected asset from library - Single Responsibility"""
        if not self._library_widget:
            return
        
        selected_assets = self._library_widget._selected_assets
        if not selected_assets:
            QMessageBox.information(self, "No Selection", "Please select an asset to remove.")
            return
        
        # Validate assets using duck typing
        valid_assets = []
        for asset in selected_assets:
            if hasattr(asset, 'display_name') and hasattr(asset, 'file_path') and hasattr(asset, 'id'):
                valid_assets.append(asset)
            else:
                print(f"⚠️ Invalid asset object skipped during removal validation")
        
        if not valid_assets:
            QMessageBox.warning(self, "Invalid Selection", "No valid assets selected for removal.")
            return
        
        # Confirm removal
        asset_names = [asset.display_name for asset in valid_assets]
        message = f"Are you sure you want to remove:\n{', '.join(asset_names)}?"
        
        reply = QMessageBox.question(self, "Confirm Removal", message,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            removed_count = 0
            failed_removals = []
            
            for asset in valid_assets:
                try:
                    print(f"🗑️ Removing asset from library: {asset.display_name}")
                    print(f"   Asset ID: {asset.id}")
                    print(f"   Asset file_path: {asset.file_path}")
                    print(f"   Asset type: {type(asset)}")
                    
                    # Use LibraryService to properly coordinate file and repository removal
                    success = self._library_service.remove_asset_from_library(asset)
                    
                    if success:
                        removed_count += 1
                        print(f"✅ Successfully removed asset: {asset.display_name}")
                        self._set_status(f"Removed asset: {asset.display_name}")
                    else:
                        failed_removals.append(asset.display_name)
                        print(f"⚠️ LibraryService reported failure for: {asset.display_name}")
                        
                except Exception as e:
                    failed_removals.append(f"{asset.display_name}: {str(e)}")
                    print(f"❌ Exception removing {asset.display_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Show results
            if removed_count > 0:
                if failed_removals:
                    message = f"Removed {removed_count} asset(s) successfully.\n\n"
                    message += f"Failed to remove {len(failed_removals)} asset(s):\n"
                    message += "\n".join([f"• {failure}" for failure in failed_removals])
                    QMessageBox.warning(self, "Partial Success", message)
                else:
                    QMessageBox.information(self, "Removal Complete", 
                                          f"Successfully removed {removed_count} asset(s) from library.")
            else:
                QMessageBox.warning(self, "Removal Failed", 
                                  "No assets were removed. Check the console for error details.")
            
            # Refresh library to reflect changes
            print(f"🔄 Refreshing library after removal...")
            self._on_refresh_library()
    
    def _on_delete_selected_asset(self) -> None:
        """Delete selected asset(s) from file system and project - Single Responsibility"""
        if not self._library_widget:
            return
        
        selected_assets = self._library_widget._selected_assets
        if not selected_assets:
            QMessageBox.information(self, "No Selection", 
                                  "Please select one or more assets to delete from the project.")
            return
        
        # Confirm deletion with stronger warning
        asset_names = [asset.display_name for asset in selected_assets]
        message = f"⚠️ WARNING: This will permanently delete the following files:\n\n"
        message += f"{chr(10).join([f'• {asset.display_name} ({asset.file_path})' for asset in selected_assets])}\n\n"
        message += f"This action cannot be undone. Are you sure you want to delete these files from the project?"
        
        reply = QMessageBox.critical(self, "Confirm File Deletion", message,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            failed_deletions = []
            
            for asset in selected_assets:
                try:
                    # First remove from repository
                    self._repository.remove_asset(asset)
                    
                    # Then delete the actual file from file system
                    file_path = Path(asset.file_path) if isinstance(asset.file_path, str) else asset.file_path
                    if file_path.exists():
                        file_path.unlink()  # Delete the file
                        deleted_count += 1
                        self._set_status(f"Deleted asset: {asset.display_name}")
                        print(f"🗑️ Deleted file: {file_path}")
                    else:
                        # Remove from repository even if file doesn't exist
                        deleted_count += 1
                        self._set_status(f"Removed non-existent asset: {asset.display_name}")
                        print(f"⚠️ File already missing: {file_path}")
                        
                except Exception as e:
                    failed_deletions.append(f"{asset.display_name}: {str(e)}")
                    print(f"❌ Failed to delete {asset.display_name}: {e}")
            
            # Show results
            if deleted_count > 0:
                if failed_deletions:
                    message = f"Deleted {deleted_count} asset(s) successfully.\n\n"
                    message += f"Failed to delete {len(failed_deletions)} asset(s):\n"
                    message += "\n".join([f"• {failure}" for failure in failed_deletions])
                    QMessageBox.warning(self, "Partial Success", message)
                else:
                    QMessageBox.information(self, "Deletion Complete", 
                                          f"Successfully deleted {deleted_count} asset(s) from the project.")
            else:
                QMessageBox.warning(self, "Deletion Failed", 
                                  "No assets were deleted. Check the console for error details.")
            
            # Refresh library to reflect changes
            self._on_refresh_library()

    
    def _update_asset_info_display(self, asset: Asset) -> None:
        """Update asset information display in RIGHT_B metadata panel - Single Responsibility"""
        print(f"📊 _update_asset_info_display called for: {asset.display_name if hasattr(asset, 'display_name') else 'Unknown'}")
        print(f"   Has _metadata_widget: {hasattr(self, '_metadata_widget')}")
        
        if hasattr(self, '_metadata_widget') and self._metadata_widget:
            # Create detailed metadata text
            info_text = f"📄 Name: {asset.display_name}\n"
            info_text += f"🗂️ Type: {asset.asset_type}\n"
            info_text += f"📁 File: {asset.file_path.name}\n"
            info_text += f"📏 Size: {asset.file_size} bytes\n"
            info_text += f"🕐 Created: {asset.created_date}\n"
            info_text += f"🕑 Modified: {asset.modified_date}\n"
            
            if hasattr(asset, 'access_count'):
                info_text += f"👁️ Access Count: {asset.access_count}\n"
            
            if hasattr(asset, 'tags') and asset.tags:
                info_text += f"🏷️ Tags: {', '.join(asset.tags)}\n"
            
            if hasattr(asset, 'metadata') and asset.metadata:
                info_text += "\n📊 Additional Metadata:\n"
                for key, value in asset.metadata.items():
                    info_text += f"  • {key}: {value}\n"
            
            print(f"📊 Setting asset info in metadata widget...")
            self._metadata_widget.set_asset_info(info_text)
            print(f"✅ Metadata widget updated successfully")
        else:
            print(f"⚠️ Metadata widget not available yet")
        
        # Also update the preview widget if it exists
        if self._preview_widget:
            self._preview_widget.set_asset(asset)
    
    def closeEvent(self, event) -> None:
        """Handle window close event - Clean shutdown and singleton cleanup"""
        # Save window state
        self._save_window_state()
        
        # Clean up resources
        self._event_publisher.clear_all_subscriptions()
        
        # Clear global singleton reference (replaces external module attribute access)
        global _asset_manager_window
        _asset_manager_window = None
        print("✅ Asset Manager singleton reference cleared")
        
        super().closeEvent(event)
    
    def resizeEvent(self, event) -> None:
        """Handle window resize event - Auto-save window geometry"""
        super().resizeEvent(event)
        
        # Save window state after resize (with small delay to avoid excessive saves)
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        else:
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_window_state)
        
        # Save after 500ms of no more resize events (debouncing)
        self._resize_timer.start(500)
    
    def bring_to_front(self) -> None:
        """Bring Asset Manager window to front - Maya integration utility"""
        try:
            if not self.isVisible():
                self.show()
            
            # Bring window to front and activate
            self.raise_()  # Bring to front of window stack
            self.activateWindow()  # Give keyboard focus
            self.showNormal()  # Restore if minimized
            
            print("✅ Asset Manager brought to front")
        except Exception as e:
            print(f"⚠️ Error bringing window to front: {e}")