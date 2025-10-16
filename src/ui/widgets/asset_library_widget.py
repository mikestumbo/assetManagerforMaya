# -*- coding: utf-8 -*-
"""
Asset Library Widget
Manages asset list display and selection following Single Responsibility

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, TYPE_CHECKING
try:
    from pathlib import Path
except ImportError:
    # Fallback for older Python versions
    Path = str

# Runtime imports
try:
    from PySide6.QtWidgets import (
        QWidget, QListWidget, QMenu, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTabWidget, QListWidgetItem,
        QDialog, QFormLayout, QLabel, QTextEdit, QMessageBox
    )
    from PySide6.QtCore import Qt, Signal, QTimer, QSize, QSettings, QMimeData
    from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QFont, QDrag
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    QWidget = None  # type: ignore
    QListWidget = None  # type: ignore  # Add this to prevent "possibly unbound" errors
    Signal = None  # Define Signal as None for fallback compatibility
    Qt = None  # Ensure Qt is defined to avoid "possibly unbound" errors
    QSize = None  # Ensure QSize is defined to avoid "possibly unbound" errors

# Type checking imports (for IDE/linters only)
if TYPE_CHECKING:
    from PySide6.QtGui import QColor  # This makes QColor available for type hints

# Import core models and interfaces - suppress import warnings for standalone testing
try:
    from ...core.models.asset import Asset  # type: ignore
    from ...core.models.search_criteria import SearchCriteria  # type: ignore
    from ...core.interfaces.asset_repository import IAssetRepository  # type: ignore
    from ...core.interfaces.thumbnail_service import IThumbnailService  # type: ignore
    from ...core.interfaces.event_publisher import IEventPublisher, EventType  # type: ignore
    from ...core.container import get_container  # type: ignore
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Import warning for asset library: {e}")
    # Create enhanced fallback classes with required methods and attributes
    class Asset:
        def __init__(self):
            self.id = ""
            self.name = ""
            self.file_path = ""
            self.display_name = ""
            self.asset_type = "unknown"
            self.file_size = 0
            self.file_size_mb = 0.0
            self.created_date = None
            self.modified_date = None
            self.access_count = 0
            self.tags = []
            self.metadata = {}
            self.is_favorite = False
    
    class SearchCriteria:
        def __init__(self, search_text="", **kwargs):
            self.search_text = search_text
            self.search_directories = []
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    class IAssetRepository:
        def find_all(self, path): return []
        def find_by_criteria(self, criteria): return []
        def add_to_favorites(self, asset): pass
        def remove_from_favorites(self, asset): pass
    
    class IThumbnailService:
        pass
    
    class IEventPublisher:
        def publish(self, event_type, data): pass
    
    class EventType:
        LIBRARY_REFRESHED = "library_refreshed"
    
    def get_container():
        class MockContainer:
            def resolve(self, interface):
                if interface == IAssetRepository:
                    return IAssetRepository()
                elif interface == IEventPublisher:
                    return IEventPublisher()
                elif interface == IThumbnailService:
                    return IThumbnailService()
                return None
        return MockContainer()
    
    IMPORTS_AVAILABLE = False

if PYSIDE_AVAILABLE and QWidget is not None:
    class DragEnabledAssetList(QListWidget):  # type: ignore
        """
        Custom QListWidget with drag support for Maya viewport
        Implements proper mime data for asset drag operations
        """
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setDragEnabled(True)
            self.setAcceptDrops(False)  # We only drag out, not drop in
        
        def startDrag(self, supportedActions):  # type: ignore
            """Override to provide custom drag behavior with asset file path"""
            item = self.currentItem()
            if not item:
                return
            
            # Get asset data using duck typing
            asset = item.data(Qt.UserRole)  # type: ignore
            if not asset or not hasattr(asset, 'file_path'):
                print("⚠️ No valid asset data for drag operation")
                return
            
            print(f"🎯 Starting drag operation for: {asset.display_name if hasattr(asset, 'display_name') else 'Unknown'}")
            print(f"   File path: {asset.file_path}")
            
            # Create mime data with file path
            mime_data = QMimeData()  # type: ignore
            
            # Set file path as URL for drag and drop
            from PySide6.QtCore import QUrl
            file_url = QUrl.fromLocalFile(str(asset.file_path))  # type: ignore
            mime_data.setUrls([file_url])  # type: ignore
            
            # Also set text representation
            mime_data.setText(str(asset.file_path))  # type: ignore
            
            print(f"✅ Mime data prepared with file URL: {file_url.toString()}")
            
            # Create drag object
            drag = QDrag(self)  # type: ignore
            drag.setMimeData(mime_data)  # type: ignore
            
            # Set drag icon (use the item's icon if available)
            if item.icon():
                drag.setPixmap(item.icon().pixmap(64, 64))  # type: ignore
            
            # Execute drag
            result = drag.exec(Qt.CopyAction)  # type: ignore
            print(f"🎬 Drag operation completed with result: {result}")
    
    class AssetLibraryWidget(QWidget):  # type: ignore
        """
        Asset Library Widget - Single Responsibility for asset list management
        Handles asset display, search, and selection
        """
        
        # Asset Type Color Mapping - Synced with Asset Type Colors keychart
        # This provides a single source of truth for all asset type colors
        ASSET_TYPE_COLORS: Dict[str, Any] = {
            "Maya Scene": (255, 150, 50),     # Orange
            "3D Model": (150, 255, 150),      # Green
            "Image": (100, 150, 255),         # Blue
            "Video": (255, 100, 150),         # Pink
            "Material": (200, 100, 255),      # Purple
            "Archive": (150, 150, 150)        # Gray
        }
        
        # Clean event signals - defined here to avoid None callable error
        if Signal is not None:
            asset_selected = Signal(Asset)  # type: ignore
            asset_double_clicked = Signal(Asset)  # type: ignore
            selection_changed = Signal(list)  # List[Asset]  # type: ignore
            asset_info_requested = Signal(Asset)  # type: ignore - Request to show asset info in panel
            color_scheme_changed = Signal(dict)  # Dict[str, QColor] - Emitted when color scheme is updated
        
        def __init__(self, parent=None):
            super().__init__(parent)
            
            # Initialize service attributes with flexible types for fallback compatibility
            self._repository: Any
            self._thumbnail_service: Any
            self._event_publisher: Any
            
            # Robust dependency injection with fallbacks
            try:
                # Try normal dependency injection first
                if IMPORTS_AVAILABLE:
                    container = get_container()  # type: ignore
                    self._repository = container.resolve(IAssetRepository)  # type: ignore
                    self._thumbnail_service = container.resolve(IThumbnailService)  # type: ignore
                    self._event_publisher = container.resolve(IEventPublisher)  # type: ignore
                    print("✅ Asset library services resolved from container")
                else:
                    raise ImportError("Imports not available, using fallback")
            except Exception as e:
                print(f"⚠️ Container resolution failed: {e}")
                print("🔄 Using robust service factory fallback...")
                
                # Fallback to service factory
                try:
                    # Add src to path for factory import
                    import sys
                    from pathlib import Path
                    src_path = Path(__file__).parent.parent.parent
                    if str(src_path) not in sys.path:
                        sys.path.insert(0, str(src_path))
                    
                    from ...core.service_factory import get_service_factory  # type: ignore
                    factory = get_service_factory()
                    
                    self._repository = factory.create_asset_repository() or self._create_fallback_repository()
                    self._thumbnail_service = factory.create_thumbnail_service() or self._create_fallback_thumbnail_service()
                    self._event_publisher = factory.create_event_publisher() or self._create_fallback_event_publisher()
                    
                    print("✅ Asset library using service factory")
                    
                except Exception as factory_error:
                    print(f"❌ Service factory also failed: {factory_error}")
                    print("🔄 Using minimal fallback services...")
                    
                    # Last resort: create minimal services
                    self._repository = self._create_fallback_repository()
                    self._thumbnail_service = self._create_fallback_thumbnail_service()
                    self._event_publisher = self._create_fallback_event_publisher()
            
            # State management
            self._current_assets = []
            self._selected_assets = []
            # Use string instead of Path to avoid type issues
            self._current_project_path: Optional[str] = None
            
            # UI components
            self._search_input: Optional[QLineEdit] = None  # type: ignore
            self._asset_list: Optional[QListWidget] = None  # type: ignore
            self._tab_widget: Optional[QTabWidget] = None  # type: ignore
            
            # Icon size control (mouse wheel zoom)
            self._icon_size = 64  # Default icon size
            self._min_icon_size = 32
            self._max_icon_size = 256
            self._icon_size_step = 16  # Amount to change per wheel notch
            
            # Color coding storage (temporary until proper metadata system)
            self._asset_colors: Dict[str, str] = {}  # asset_id -> color_name
            
            # Tag tracking - maintain a set of all used tags
            self._all_used_tags: set = set()
            self._predefined_tags = [
                "Environment", "Character", "Prop", "Texture", 
                "Material", "Animation", "Lighting", "VFX",
                "WIP", "Final", "Approved", "Archived"
            ]
            self._all_used_tags.update(self._predefined_tags)  # Start with predefined tags
            
            # Load custom tags from config file
            self._load_custom_tags()
            
            # Setup UI
            self._create_ui()
            self._setup_connections()
            
            # Auto-refresh timer
            self._refresh_timer = QTimer()  # type: ignore
            self._refresh_timer.timeout.connect(self._auto_refresh)  # type: ignore
            self._refresh_timer.start(30000)  # 30 seconds
        
        def _create_fallback_repository(self):
            """Create minimal fallback asset repository"""
            class FallbackAssetRepository:
                def find_all(self, directory):
                    from pathlib import Path
                    assets = []
                    if directory and directory.exists():
                        for file_path in directory.rglob('*'):
                            if file_path.is_file() and self._is_asset_file(file_path):
                                assets.append(self._create_minimal_asset(file_path))
                    return assets
                
                def _is_asset_file(self, file_path):
                    supported_extensions = {'.png', '.jpg', '.jpeg', '.ma', '.mb', '.obj', '.fbx'}
                    return file_path.suffix.lower() in supported_extensions
                
                def _create_minimal_asset(self, file_path):
                    return type('Asset', (), {
                        'id': str(file_path),
                        'name': file_path.name,
                        'file_path': file_path,
                        'display_name': file_path.name,
                        'is_favorite': False,
                        'file_extension': file_path.suffix,
                        'asset_type': 'unknown'
                    })()
                
                def add_to_favorites(self, asset):
                    print(f"📌 Would add {asset.name} to favorites")
                
                def remove_from_favorites(self, asset):
                    print(f"📌 Would remove {asset.name} from favorites")
                
                def find_by_criteria(self, criteria):
                    return []
            
            return FallbackAssetRepository()
        
        def _create_fallback_thumbnail_service(self):
            """Create enhanced fallback thumbnail service with basic file type icons"""
            class FallbackThumbnailService:
                def __init__(self):
                    self._cache_dir = None
                    try:
                        from pathlib import Path
                        import tempfile
                        self._cache_dir = Path(tempfile.gettempdir()) / "asset_manager_icons"
                        self._cache_dir.mkdir(exist_ok=True)
                    except Exception:
                        pass
                
                def generate_thumbnail(self, file_path, size=(64, 64)):
                    """Generate basic file type icon as fallback thumbnail"""
                    try:
                        from pathlib import Path
                        file_name = Path(file_path).name if hasattr(Path(file_path), 'name') else str(file_path)
                        print(f"🔄 Fallback thumbnail service generating icon for: {file_name}")
                        result = self._create_file_type_icon(file_path, size)
                        if result:
                            print(f"✅ Fallback thumbnail created: {result}")
                        return result
                    except Exception as e:
                        print(f"❌ Failed to create file type icon for {file_path}: {e}")
                        return None
                
                def get_cached_thumbnail(self, file_path, size=(64, 64)):
                    """Check if we have a cached file type icon"""
                    try:
                        return self._create_file_type_icon(file_path, size)
                    except Exception:
                        return None
                
                def _create_file_type_icon(self, file_path, size=(64, 64)):
                    """Create a basic file type icon using Qt drawing"""
                    try:
                        from pathlib import Path
                        from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
                        from PySide6.QtCore import Qt
                        
                        file_path = Path(file_path) if isinstance(file_path, str) else file_path
                        
                        # Get file extension for icon type
                        ext = file_path.suffix.lower() if hasattr(file_path, 'suffix') else '.unknown'
                        if not ext:
                            ext = '.file'
                        
                        # Create a simple colored icon based on file type
                        pixmap = QPixmap(size[0], size[1])
                        pixmap.fill(QColor(60, 60, 60, 180))  # Semi-transparent dark background
                        
                        painter = QPainter(pixmap)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        
                        # Choose color based on file type
                        colors = {
                            '.ma': QColor(0, 150, 255),    # Maya - Blue
                            '.mb': QColor(0, 120, 200),    # Maya Binary - Dark Blue  
                            '.fbx': QColor(255, 150, 0),   # FBX - Orange
                            '.obj': QColor(150, 255, 150), # OBJ - Light Green
                            '.usd': QColor(255, 100, 150), # USD - Pink
                            '.usda': QColor(255, 120, 170), # USDA - Light Pink
                            '.abc': QColor(150, 150, 255), # Alembic - Light Blue
                            '.3ds': QColor(255, 255, 100), # 3DS - Yellow
                        }
                        
                        color = colors.get(ext, QColor(180, 180, 180))  # Default gray
                        
                        # Draw file icon shape
                        painter.setBrush(color)
                        painter.setPen(QColor(255, 255, 255, 200))
                        
                        # Draw a simple file icon shape
                        margin = size[0] // 8
                        rect_width = size[0] - (margin * 2)
                        rect_height = size[1] - (margin * 2)
                        
                        # Main rectangle
                        painter.drawRoundedRect(margin, margin, rect_width, rect_height, 4, 4)
                        
                        # Draw file extension text
                        font = QFont("Arial", max(8, size[0] // 8), QFont.Weight.Bold)
                        painter.setFont(font)
                        painter.setPen(QColor(255, 255, 255))
                        
                        # Remove the dot for display
                        ext_text = ext[1:].upper() if ext.startswith('.') else ext.upper()
                        painter.drawText(margin, margin, rect_width, rect_height, 
                                       Qt.AlignmentFlag.AlignCenter, ext_text)
                        
                        painter.end()
                        
                        # Save to cache if possible
                        if self._cache_dir:
                            try:
                                cache_name = f"{file_path.name}_{size[0]}x{size[1]}.png"
                                cache_path = self._cache_dir / cache_name
                                pixmap.save(str(cache_path), "PNG")
                                return str(cache_path)
                            except Exception:
                                pass
                        
                        # Return as temporary file
                        import tempfile
                        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                        pixmap.save(temp_file.name, "PNG")
                        return temp_file.name
                        
                    except Exception as e:
                        print(f"❌ Error creating file type icon: {e}")
                        return None
                
                def is_thumbnail_supported(self, file_path):
                    return True
                
                def clear_cache_for_file(self, file_path):
                    """Clear cache for file - fallback implementation"""
                    pass
            
            return FallbackThumbnailService()
        
        def _create_fallback_event_publisher(self):
            """Create minimal fallback event publisher"""
            class FallbackEventPublisher:
                def publish(self, event_type, data=None):
                    print(f"📢 Event: {event_type}")
            
            return FallbackEventPublisher()
        
        def _create_ui(self) -> None:
            """Create the user interface - Single Responsibility"""
            layout = QVBoxLayout(self)  # type: ignore
            layout.setContentsMargins(4, 4, 4, 4)  # type: ignore
            
            # Search section
            search_layout = self._create_search_section()
            layout.addLayout(search_layout)  # type: ignore
            
            # Tab widget for different views
            self._tab_widget = QTabWidget()  # type: ignore
            layout.addWidget(self._tab_widget)  # type: ignore
            
            # All Assets tab
            self._asset_list = self._create_asset_list()
            self._tab_widget.addTab(self._asset_list, "All Assets")  # type: ignore
            
            # Recent Assets tab
            recent_list = self._create_asset_list()
            self._tab_widget.addTab(recent_list, "Recent")  # type: ignore
            
            # Favorites tab
            favorites_list = self._create_asset_list()
            self._tab_widget.addTab(favorites_list, "Favorites")  # type: ignore
            
            # Collections tab with proper implementation
            from .collections_widget import CollectionsDisplayWidget
            collections_widget = CollectionsDisplayWidget(self)  # type: ignore
            # Connect collection widget signals to library widget signals
            collections_widget.asset_selected.connect(self.asset_selected.emit)  # type: ignore
            collections_widget.asset_double_clicked.connect(self.asset_double_clicked.emit)  # type: ignore
            collections_widget.collection_manager_requested.connect(self._show_collection_manager)  # type: ignore
            self._tab_widget.addTab(collections_widget, "Collections")  # type: ignore
        
        def _create_search_section(self):  # type: ignore
            """Create search input section - Single Responsibility"""
            search_layout = QHBoxLayout()  # type: ignore
            
            # Search input
            self._search_input = QLineEdit()  # type: ignore
            self._search_input.setPlaceholderText("Search assets...")  # type: ignore
            search_layout.addWidget(self._search_input)  # type: ignore
            
            # Search button
            search_btn = QPushButton("Search")  # type: ignore
            search_btn.setToolTip("Search for assets by name or properties")  # type: ignore
            search_btn.clicked.connect(self._perform_search)  # type: ignore
            search_layout.addWidget(search_btn)  # type: ignore
            
            # Advanced search button
            advanced_btn = QPushButton("Advanced...")  # type: ignore
            advanced_btn.setToolTip("Open advanced search options and filters")  # type: ignore
            advanced_btn.clicked.connect(self._show_advanced_search)  # type: ignore
            search_layout.addWidget(advanced_btn)  # type: ignore
            
            return search_layout
        
        def _create_asset_list(self):  # type: ignore
            """Create asset list widget - Single Responsibility"""
            print(f"🎨 Creating asset list widget with drag support and event connections...")
            asset_list = DragEnabledAssetList()  # Use custom drag-enabled list
            asset_list.setViewMode(QListWidget.IconMode)  # type: ignore
            asset_list.setGridSize(QSize(80, 100))  # type: ignore
            asset_list.setIconSize(QSize(64, 64))  # type: ignore
            asset_list.setResizeMode(QListWidget.Adjust)  # type: ignore
            asset_list.setSelectionMode(QListWidget.ExtendedSelection)  # type: ignore
            # Drag mode is set in DragEnabledAssetList constructor
            
            # Enable custom context menu
            asset_list.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
            asset_list.customContextMenuRequested.connect(self._show_context_menu)  # type: ignore
            
            # Connect signals
            asset_list.itemSelectionChanged.connect(self._on_selection_changed)  # type: ignore
            asset_list.itemDoubleClicked.connect(self._on_item_double_clicked)  # type: ignore
            print(f"✅ Asset list signals connected: itemSelectionChanged, itemDoubleClicked, drag enabled")
            
            return asset_list
        
        def _setup_connections(self) -> None:
            """Setup signal connections - Single Responsibility"""
            if self._search_input:
                self._search_input.textChanged.connect(self._on_search_text_changed)  # type: ignore
                self._search_input.returnPressed.connect(self._perform_search)  # type: ignore
        
        def _show_context_menu(self, position) -> None:
            """Handle right-click context menu - Single Responsibility"""
            # Get the list widget that sent the signal
            sender = self.sender()  # type: ignore
            if QListWidget is None or not isinstance(sender, QListWidget):
                return
            
            # Get item at cursor position
            item = sender.itemAt(position)  # type: ignore
            if not item:
                return
            
            # Get asset data - more flexible check instead of strict isinstance
            asset = item.data(Qt.UserRole)  # type: ignore
            if not asset:
                return
            
            # Validate that asset has required attributes (duck typing approach)
            required_attrs = ['display_name', 'file_path', 'id']
            if not all(hasattr(asset, attr) for attr in required_attrs):
                return
            
            # Create context menu
            menu = QMenu(self)  # type: ignore
            
            # Import action
            import_action = menu.addAction("Import Asset...")
            import_action.setToolTip("Import selected asset(s) into Maya")
            import_action.triggered.connect(lambda: self._import_asset(asset))
            
            # Remove asset action
            remove_action = menu.addAction("Remove Asset...")
            remove_action.setToolTip("Remove selected asset(s) from library")
            remove_action.triggered.connect(lambda: self._remove_asset(asset))
            
            # Separator for screenshot section
            menu.addSeparator()
            
            # Screenshot capture action with custom icon
            screenshot_action = menu.addAction("Capture Screenshot")
            screenshot_action.setToolTip("Create custom captured screenshot from Maya's currently selected viewport")
            # Try to use custom screenshot icon
            try:
                screenshot_icon_path = self._get_screenshot_icon_path()
                if screenshot_icon_path:
                    from PySide6.QtGui import QIcon
                    screenshot_action.setIcon(QIcon(screenshot_icon_path))
            except Exception as e:
                print(f"⚠️ Could not set custom screenshot icon in menu: {e}")
            screenshot_action.triggered.connect(lambda: self._capture_screenshot(asset))
            
            # Separator after screenshot section
            menu.addSeparator()
            
            # Favorites actions - show both, enable/disable based on status
            is_favorite = getattr(asset, 'is_favorite', False)
            
            add_fav_action = menu.addAction("Add to Favorites")
            add_fav_action.setEnabled(not is_favorite)
            add_fav_action.triggered.connect(lambda: self._add_to_favorites(asset))
            if is_favorite:
                add_fav_action.setToolTip("Asset is already in favorites")
            
            remove_fav_action = menu.addAction("Remove from Favorites")
            remove_fav_action.setEnabled(is_favorite)
            remove_fav_action.triggered.connect(lambda: self._remove_from_favorites(asset))
            if not is_favorite:
                remove_fav_action.setToolTip("Asset is not in favorites")
            
            # Separator
            menu.addSeparator()
            
            # Color Coding submenu - Synced with Asset Type Colors
            color_menu = menu.addMenu("Color Coding")
            color_menu.setToolTip("Apply asset type colors for visual organization")
            
            # Add asset type color options using the class dictionary
            # Note: Color descriptions removed - colors are now dynamically managed via Color Manager
            for asset_type_name in self.ASSET_TYPE_COLORS.keys():
                action = color_menu.addAction(asset_type_name)
                if action is not None:
                    # Use lambda with default argument to capture current value
                    action.triggered.connect(
                        lambda checked=False, type_name=asset_type_name: 
                        self._set_asset_type_color(asset, type_name)
                    )
            
            color_menu.addSeparator()
            action = color_menu.addAction("Clear Color")
            if action is not None:
                action.triggered.connect(lambda: self._clear_asset_color(asset))
            action = color_menu.addAction("Manage Colors...")
            if action is not None:
                action.triggered.connect(self._open_color_manager)
            
            # Tag Manager submenu
            tag_menu = menu.addMenu("Tags")
            
            # Show current tags if any
            if hasattr(asset, 'tags') and asset.tags:
                tag_menu.addAction(f"Current Tags: {', '.join(asset.tags)}").setEnabled(False)
                tag_menu.addSeparator()
            
            tag_menu.addAction("Add Tag...").triggered.connect(lambda: self._add_tag_to_asset(asset))
            
            # Only show remove option if asset has tags
            if hasattr(asset, 'tags') and asset.tags:
                tag_menu.addAction("Remove Tag...").triggered.connect(lambda: self._remove_tags_from_asset(asset))
            
            tag_menu.addSeparator()
            tag_menu.addAction("Manage Tags...").triggered.connect(self._open_tag_manager)
            
            # Collections submenu
            collections_menu = menu.addMenu("Collections")
            collections_menu.addAction("Add to Collection...").triggered.connect(lambda: self._add_to_collection(asset))
            collections_menu.addAction("New Collection...").triggered.connect(self._create_new_collection)
            collections_menu.addSeparator()
            collections_menu.addAction("Manage Collections...").triggered.connect(self._open_collections_manager)
            
            # Separator
            menu.addSeparator()
            
            # Show in folder action
            show_folder_action = menu.addAction("Show in Folder")
            show_folder_action.triggered.connect(lambda: self._show_in_folder(asset))
            
            # Properties action
            properties_action = menu.addAction("Properties")
            properties_action.triggered.connect(lambda: self._show_properties(asset))
            
            # Show menu at cursor position
            menu.exec(sender.mapToGlobal(position))  # type: ignore
        
        def _import_asset(self, asset: Any) -> None:
            """Import asset - Single Responsibility"""
            self.asset_double_clicked.emit(asset)
        
        def _remove_asset(self, asset: Any) -> None:
            """Remove asset from library - Single Responsibility"""
            try:
                from PySide6.QtWidgets import QMessageBox
                
                # Confirm deletion
                reply = QMessageBox.question(
                    self,
                    "Remove Asset",
                    f"Are you sure you want to remove '{asset.display_name}' from the library?\n\n"
                    f"This will delete the asset file from disk and cannot be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Delete the file from disk
                    import os
                    from pathlib import Path
                    
                    file_path = Path(asset.file_path) if isinstance(asset.file_path, str) else asset.file_path
                    if file_path.exists():
                        os.remove(file_path)
                        print(f"🗑️ Deleted asset file: {file_path}")
                        
                        # Also remove thumbnail if it exists
                        try:
                            self._thumbnail_service.clear_cache_for_file(asset.file_path)
                        except Exception as e:
                            print(f"⚠️ Could not clear thumbnail cache: {e}")
                        
                        # Refresh the library to update the display
                        self.refresh_library()
                        
                        self._set_status(f"Removed asset: {asset.display_name}")
                        
                        QMessageBox.information(
                            self,
                            "Asset Removed",
                            f"'{asset.display_name}' has been removed from the library."
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "File Not Found",
                            f"The asset file could not be found:\n{file_path}"
                        )
                        
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                print(f"❌ Error removing asset: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to remove asset:\n{str(e)}"
                )
        
        def _add_to_favorites(self, asset: Any) -> None:
            """Add asset to favorites - Single Responsibility"""
            self._repository.add_to_favorites(asset)
            
            # Persist favorite status to metadata file
            asset.is_favorite = True
            self._save_asset_metadata(asset)
            
            # Refresh the Favorites tab to show the newly added asset
            self._load_favorite_assets()
            
            # Refresh info panel if this asset is currently selected
            if asset in self._selected_assets:
                self.asset_selected.emit(asset)
            
            self._set_status(f"⭐ Added to favorites: {asset.name}")
            print(f"⭐ Added '{asset.display_name}' to favorites and saved to metadata")
        
        def _remove_from_favorites(self, asset: Any) -> None:
            """Remove asset from favorites - Single Responsibility"""
            self._repository.remove_from_favorites(asset)
            
            # Persist favorite status to metadata file
            asset.is_favorite = False
            self._save_asset_metadata(asset)
            
            # Refresh the Favorites tab to remove the asset
            self._load_favorite_assets()
            
            # Refresh info panel if this asset is currently selected
            if asset in self._selected_assets:
                self.asset_selected.emit(asset)
            
            self._set_status(f"⭐ Removed from favorites: {asset.name}")
            print(f"⭐ Removed '{asset.display_name}' from favorites and saved to metadata")
        
        def _capture_screenshot(self, asset: Any) -> None:
            """Capture screenshot for asset - Single Responsibility"""
            try:
                print(f"📸 Opening screenshot dialog for: {asset.display_name if hasattr(asset, 'display_name') else 'Unknown'}")
                
                # Import screenshot dialog
                from ..dialogs.screenshot_capture_dialog import ScreenshotCaptureDialog
                
                # Create and show screenshot capture dialog
                dialog = ScreenshotCaptureDialog(asset, self)  # type: ignore
                
                # Set refresh callback to update just this asset's thumbnail
                def refresh_callback():
                    """Refresh thumbnail for the specific asset after screenshot capture"""
                    try:
                        # Clear thumbnail cache for this asset to force reload
                        if hasattr(asset, 'file_path') and self._thumbnail_service:
                            try:
                                self._thumbnail_service.clear_cache_for_file(asset.file_path)
                                print(f"🗑️ Cleared thumbnail cache for {asset.display_name}")
                            except Exception as cache_error:
                                print(f"⚠️ Could not clear cache: {cache_error}")
                        
                        # Update thumbnail for just this specific asset across all list views
                        # This is more efficient than refreshing the entire library
                        print(f"🔄 Refreshing thumbnail for: {asset.display_name}")
                        self.refresh_thumbnails_for_assets([asset.file_path])
                        print("✅ Thumbnail refreshed after screenshot capture")
                    except Exception as e:
                        print(f"⚠️ Error refreshing thumbnail after screenshot: {e}")
                
                dialog.set_refresh_callback(refresh_callback)  # type: ignore
                
                # Show dialog
                dialog.exec()  # type: ignore
                
            except Exception as e:
                import traceback
                print(f"❌ Error opening screenshot dialog: {e}")
                print(f"Traceback:\n{traceback.format_exc()}")
                self._set_status(f"Screenshot error: {e}")
        
        def _get_screenshot_icon_path(self) -> Optional[str]:
            """Get the path to the custom screenshot icon - Single Responsibility"""
            try:
                # Method 1: Check current Asset Manager installation directory (when running in Maya)
                from pathlib import Path as PathLib
                current_file = PathLib(__file__)
                
                # If we're running from Maya's assetManager installation
                if "assetManager" in str(current_file):
                    # Navigate up to find the assetManager root directory
                    asset_manager_root = current_file
                    while asset_manager_root.name != "assetManager" and asset_manager_root.parent != asset_manager_root:
                        asset_manager_root = asset_manager_root.parent
                    
                    # Check for icon in the assetManager directory
                    icon_path = asset_manager_root / "screen-shot_icon.png"
                    if icon_path.exists():
                        return str(icon_path)
                
                # Method 2: Check the source icons directory (development/testing)
                root_dir = current_file.parent.parent.parent
                icon_path = root_dir / "icons" / "screen-shot_icon.png"
                
                if icon_path.exists():
                    return str(icon_path)
                
                # Method 3: Try to find Maya scripts directory with our icon
                try:
                    home = PathLib.home()
                    maya_paths = [
                        home / "OneDrive" / "Documents" / "maya" / "scripts" / "assetManager" / "screen-shot_icon.png",
                        home / "Documents" / "maya" / "scripts" / "assetManager" / "screen-shot_icon.png"
                    ]
                    
                    for maya_path in maya_paths:
                        if maya_path.exists():
                            return str(maya_path)
                            
                except Exception:
                    pass
                
                return None
                
            except Exception as e:
                print(f"🔧 Could not resolve screenshot icon path: {e}")
                return None
        
        def _show_in_folder(self, asset: Any) -> None:
            """Show asset in file explorer - Single Responsibility"""
            import subprocess
            import os
            try:
                if os.name == 'nt':  # Windows
                    subprocess.run(['explorer', '/select,', str(asset.file_path)])
                elif os.name == 'posix':  # macOS/Linux
                    subprocess.run(['xdg-open', str(asset.file_path.parent)])
            except Exception as e:
                self._set_status(f"Error opening folder: {e}")
        
        def wheelEvent(self, event) -> None:
            """Handle mouse wheel for icon size adjustment - Enhanced UX"""
            try:
                # Check if Ctrl key is pressed (for icon size adjustment)
                # Without Ctrl, let default scrolling behavior happen
                if Qt and event.modifiers() & Qt.KeyboardModifier.ControlModifier:  # Added check for Qt availability
                    delta = event.angleDelta().y()
                    
                    if delta > 0:
                        # Zoom in (larger icons)
                        self._icon_size = min(self._icon_size + self._icon_size_step, self._max_icon_size)
                    else:
                        # Zoom out (smaller icons)
                        self._icon_size = max(self._icon_size - self._icon_size_step, self._min_icon_size)
                    
                    # Apply new icon size to all asset list widgets
                    self._update_icon_sizes()
                    
                    event.accept()
                    return
            except Exception as e:
                print(f"⚠️ Wheel event error: {e}")
            
            # Default behavior for normal scrolling (without Ctrl)
            super().wheelEvent(event)
        
        def _update_icon_sizes(self) -> None:
            """Update icon and grid sizes for all list widgets - Single Responsibility"""
            try:
                # Guard against None QSize to prevent calling None
                if QSize is None:
                    print("⚠️ QSize not available, skipping icon size update")
                    return
                
                # Calculate grid size based on icon size (add 16px padding for text)
                grid_width = self._icon_size + 16
                grid_height = self._icon_size + 36  # Extra space for text below icon
                
                new_icon_size = QSize(self._icon_size, self._icon_size)
                new_grid_size = QSize(grid_width, grid_height)
                
                # Update all list widgets in tabs
                if self._tab_widget and QListWidget is not None:
                    for i in range(self._tab_widget.count()):
                        widget = self._tab_widget.widget(i)
                        # Use hasattr for duck typing instead of isinstance to avoid type errors
                        if widget and hasattr(widget, 'setIconSize') and hasattr(widget, 'setGridSize'):
                            widget.setIconSize(new_icon_size)  # type: ignore
                            widget.setGridSize(new_grid_size)  # type: ignore
                
                print(f"🔍 Icon size adjusted to {self._icon_size}px")
                
            except Exception as e:
                print(f"⚠️ Error updating icon sizes: {e}")
        
        def _show_properties(self, asset: Any) -> None:
            """Show asset properties dialog - Single Responsibility"""
            try:
                # Create and show properties dialog
                self._show_asset_properties_dialog(asset)
                
                # Also emit signal to request asset info display in main window panel
                self.asset_info_requested.emit(asset)
                
                # Ensure the asset is selected for consistency
                self.asset_selected.emit(asset)
                
            except Exception as e:
                print(f"⚠️ Error showing properties: {e}")
                # Fallback: show basic info in status
                self._set_status(f"Properties for: {getattr(asset, 'display_name', 'Unknown Asset')}")
        
        def _show_asset_properties_dialog(self, asset: Any) -> None:
            """Display asset properties in a dialog - Single Responsibility"""
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFormLayout
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Asset Properties - {getattr(asset, 'display_name', 'Unknown')}")
            dialog.setMinimumSize(400, 500)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QLabel {
                    color: #cccccc;
                    font-weight: bold;
                    padding: 2px;
                }
                QTextEdit {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px;
                }
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            
            # Create form layout for properties
            form_layout = QFormLayout()
            
            # Basic properties
            properties = [
                ("Name", getattr(asset, 'display_name', 'Unknown')),
                ("File Path", str(getattr(asset, 'file_path', 'Unknown'))),
                ("Asset Type", getattr(asset, 'asset_type', 'Unknown')),
                ("ID", getattr(asset, 'id', 'Unknown')),
                ("Is Favorite", "Yes" if getattr(asset, 'is_favorite', False) else "No"),
            ]
            
            # Add file-specific properties if file exists
            try:
                file_path = getattr(asset, 'file_path', None)
                if file_path and hasattr(file_path, 'stat'):
                    import datetime
                    stat_info = file_path.stat()
                    file_size = f"{stat_info.st_size / 1024:.1f} KB"
                    modified_time = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    properties.extend([
                        ("File Size", file_size),
                        ("Modified", modified_time),
                    ])
            except Exception:
                pass  # Skip file properties if not available
            
            # Add properties to form
            for label, value in properties:
                label_widget = QLabel(f"{label}:")
                value_widget = QLabel(str(value))
                value_widget.setStyleSheet("font-weight: normal; color: #ffffff;")
                value_widget.setWordWrap(True)
                form_layout.addRow(label_widget, value_widget)
            
            layout.addLayout(form_layout)
            
            # Add description/notes section if available
            description = getattr(asset, 'description', '') or getattr(asset, 'notes', '')
            if description:
                layout.addWidget(QLabel("Description:"))
                desc_text = QTextEdit()
                desc_text.setPlainText(description)
                desc_text.setMaximumHeight(100)
                desc_text.setReadOnly(True)
                layout.addWidget(desc_text)
            
            # Add tags if available
            tags = getattr(asset, 'tags', [])
            if tags:
                tags_label = QLabel("Tags:")
                layout.addWidget(tags_label)
                tags_text = QLabel(", ".join(tags) if tags else "None")
                tags_text.setStyleSheet("font-weight: normal; color: #ffffff; padding: 4px; background-color: #3c3c3c; border-radius: 4px;")
                tags_text.setWordWrap(True)
                layout.addWidget(tags_text)
            
            # Button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            # OK button
            ok_button = QPushButton("OK")
            ok_button.clicked.connect(dialog.accept)
            button_layout.addWidget(ok_button)
            
            layout.addLayout(button_layout)
            
            # Show dialog
            dialog.exec()
        
        def _set_status(self, message: str) -> None:
            """Set status message - Helper method"""
            # This would need to be connected to the main window's status bar
            print(f"Status: {message}")
        
        def load_project(self, project_path: Any) -> None:
            """Load assets from project directory - Single Responsibility"""
            self._current_project_path = project_path
            self.refresh_library()
        
        def refresh_library(self) -> None:
            """Refresh asset library - Single Responsibility"""
            if not self._current_project_path:
                return
            
            try:
                # Load assets from repository
                assets = self._repository.find_all(self._current_project_path)
                self._current_assets = assets
                
                # Update main asset list
                self._populate_asset_list(self._asset_list, assets)
                
                # Load recent and favorites
                self._load_recent_assets()
                self._load_favorite_assets()
                
                # Publish library refreshed event with asset count
                self._event_publisher.publish(EventType.LIBRARY_REFRESHED, {'asset_count': len(assets)})
                
            except Exception as e:
                print(f"Error refreshing library: {e}")
        
        def _populate_asset_list(self, list_widget, assets: List[Any]) -> None:  # type: ignore
            """Populate list widget with assets - Single Responsibility"""
            if not list_widget:
                print(f"❌ _populate_asset_list: No list widget provided")
                return
            
            list_widget.clear()  # type: ignore
            print(f"🔄 Populating asset list with {len(assets) if assets else 0} assets")
            
            # Use a set to track asset IDs to prevent duplicates
            seen_asset_ids = set()
            
            for i, asset in enumerate(assets):
                # Skip if we've already added this asset
                if asset.id in seen_asset_ids:
                    continue
                    
                seen_asset_ids.add(asset.id)
                
                # Load metadata (tags, favorites, etc.) from sidecar file
                self._load_asset_metadata(asset)
                
                item = QListWidgetItem()  # type: ignore
                
                # Build display name with tag indicator
                display_text = asset.display_name
                tooltip_text = asset.display_name
                
                if hasattr(asset, 'tags') and asset.tags:
                    # Add tag indicator
                    tag_count = len(asset.tags)
                    display_text = f"{display_text} 🏷️×{tag_count}"
                    
                    # Add tag list to tooltip
                    tags_str = ", ".join(asset.tags)
                    tooltip_text = f"{asset.display_name}\n\nTags: {tags_str}"
                
                item.setText(display_text)  # type: ignore
                item.setToolTip(tooltip_text)  # type: ignore
                item.setData(Qt.UserRole, asset)  # type: ignore
                
                print(f"🔄 Adding asset [{i+1}]: {asset.display_name}")
                print(f"   ID: {asset.id}")
                if hasattr(asset, 'file_path') and asset.file_path:
                    from pathlib import Path as PathLib
                    file_exists = PathLib(asset.file_path).exists()
                    print(f"   Path: {asset.file_path}")
                    print(f"   Exists: {file_exists}")
                else:
                    print(f"   Path: N/A")
                
                # Apply color coding if asset has color
                asset_color = self._asset_colors.get(asset.id)
                if asset_color:
                    self._apply_color_coding(item, asset_color)
                
                # Set thumbnail if available - FIX: Include size parameter for proper cache lookup
                icon_size = (64, 64)  # Match the QListWidget icon size
                thumbnail_path = self._thumbnail_service.get_cached_thumbnail(asset.file_path, size=icon_size)  # type: ignore
                if thumbnail_path:
                    try:
                        icon = QIcon(thumbnail_path)  # type: ignore
                        item.setIcon(icon)  # type: ignore
                        print(f"🖼️ Loaded cached thumbnail for: {asset.display_name}")
                    except Exception as e:
                        print(f"❌ Failed to load thumbnail icon for {asset.display_name}: {e}")
                        # Generate thumbnail in background if icon loading fails
                        self._generate_thumbnail_async(asset, item, icon_size)
                else:
                    print(f"🖼️ No cached thumbnail for {asset.display_name}, generating...")
                    # Generate thumbnail in background
                    self._generate_thumbnail_async(asset, item, icon_size)
                
                list_widget.addItem(item)  # type: ignore
            
            print(f"✅ Populated asset list with {len(seen_asset_ids)} unique assets")
        
        def _generate_thumbnail_async(self, asset: Asset, item, size: tuple = (64, 64)) -> None:  # type: ignore
            """Generate thumbnail asynchronously - Non-blocking UI with proper size parameter"""
            def generate():
                try:
                    print(f"🔄 Async thumbnail generation started for: {asset.display_name} ({size})")
                    thumbnail_path = self._thumbnail_service.generate_thumbnail(asset.file_path, size=size)  # type: ignore
                    if thumbnail_path:
                        print(f"✅ Async thumbnail path received: {thumbnail_path}")
                        # Update UI on main thread
                        QTimer.singleShot(0, lambda: self._set_item_thumbnail(item, thumbnail_path))  # type: ignore
                        print(f"🖼️ Generated async thumbnail for: {asset.display_name} (size: {size})")
                    else:
                        print(f"❌ Failed to generate thumbnail for: {asset.display_name}")
                except Exception as e:
                    print(f"❌ Async thumbnail generation error for {asset.display_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            import threading
            threading.Thread(target=generate, daemon=True).start()
        
        def _set_item_thumbnail(self, item, thumbnail_path: str) -> None:  # type: ignore
            """Set thumbnail for list item - UI thread only with enhanced error handling"""
            try:
                from pathlib import Path
                thumb_file = Path(thumbnail_path)
                
                if not thumb_file.exists():
                    print(f"❌ Thumbnail file does not exist: {thumbnail_path}")
                    return
                
                icon = QIcon(thumbnail_path)  # type: ignore
                if icon.isNull():
                    print(f"❌ Failed to create QIcon from: {thumbnail_path}")
                    return
                
                item.setIcon(icon)  # type: ignore
                print(f"✅ Set thumbnail icon for item: {thumbnail_path}")
                
            except Exception as e:
                print(f"❌ Error setting thumbnail icon: {e}")
                import traceback
                traceback.print_exc()
        
        def _load_recent_assets(self) -> None:
            """Load recent assets into tab - Single Responsibility"""
            print(f"🕒 Loading recent assets...")
            recent_assets = self._repository.get_recent_assets(20)  # type: ignore
            recent_list = self._tab_widget.widget(1) if self._tab_widget else None  # Recent tab  # type: ignore
            
            print(f"🕒 Found {len(recent_assets) if recent_assets else 0} recent assets")
            print(f"🕒 Recent tab widget: {type(recent_list).__name__ if recent_list else 'None'}")
            
            if recent_list and hasattr(recent_list, 'clear'):  # Check if it's a list widget  # type: ignore
                self._populate_asset_list(recent_list, recent_assets)
                print(f"🕒 Populated recent assets tab with {len(recent_assets)} items")
            else:
                print(f"❌ Recent tab widget not found or invalid")
        
        def _load_favorite_assets(self) -> None:
            """Load favorite assets into tab - Single Responsibility"""
            print(f"⭐ Loading favorite assets...")
            favorite_assets = self._repository.get_favorites()  # type: ignore
            favorites_list = self._tab_widget.widget(2) if self._tab_widget else None  # Favorites tab  # type: ignore
            
            print(f"⭐ Found {len(favorite_assets) if favorite_assets else 0} favorite assets")
            print(f"⭐ Favorites tab widget: {type(favorites_list).__name__ if favorites_list else 'None'}")
            
            if favorites_list and hasattr(favorites_list, 'clear'):  # Check if it's a list widget  # type: ignore
                self._populate_asset_list(favorites_list, favorite_assets)
                print(f"⭐ Populated favorites tab with {len(favorite_assets)} items")
            else:
                print(f"❌ Favorites tab widget not found or invalid")
        
        def _perform_search(self) -> None:
            """Perform asset search - Single Responsibility"""
            if not self._search_input:
                return
            
            search_text = self._search_input.text().strip()
            if not search_text:
                self.refresh_library()
                return
            
            # Create search criteria
            criteria = SearchCriteria(search_text=search_text)
            self.search_with_criteria(criteria)
        
        def search_with_criteria(self, criteria: Any) -> None:
            """Search with specific criteria - Single Responsibility"""
            try:
                # If no search directories specified, use current project
                if not criteria.search_directories and self._current_project_path:
                    criteria.search_directories = [self._current_project_path]
                
                # Perform search
                results = self._repository.find_by_criteria(criteria)
                
                # Update asset list
                self._populate_asset_list(self._asset_list, results)
                
                # Switch to All Assets tab to show results
                if self._tab_widget:
                    self._tab_widget.setCurrentIndex(0)
                    
            except Exception as e:
                print(f"Search error: {e}")
        
        def get_selected_assets(self) -> List[Any]:
            """Get currently selected assets - Single Responsibility"""
            return self._selected_assets.copy()
        
        def select_all_assets(self) -> None:
            """Select all assets in current view - Single Responsibility"""
            current_list = self._get_current_asset_list()
            if current_list:
                current_list.selectAll() # type: ignore
        
        def set_recent_assets(self, assets: List[Any]) -> None:
            """Set recent assets from external source - Single Responsibility"""
            recent_list = self._tab_widget.widget(1) if self._tab_widget else None  # type: ignore
            if recent_list and hasattr(recent_list, 'clear'):  # Check if it's a list widget  # type: ignore
                self._populate_asset_list(recent_list, assets)
        
        def set_favorite_assets(self, assets: List[Any]) -> None:
            """Set favorite assets from external source - Single Responsibility"""
            favorites_list = self._tab_widget.widget(2) if self._tab_widget else None  # type: ignore
            if favorites_list and hasattr(favorites_list, 'clear'):  # Check if it's a list widget  # type: ignore
                self._populate_asset_list(favorites_list, assets)
        
        def _get_current_asset_list(self):  # type: ignore
            """Get currently active asset list widget - Single Responsibility"""
            if not self._tab_widget:
                return None
            
            current_widget = self._tab_widget.currentWidget()  # type: ignore
            return current_widget if (current_widget and hasattr(current_widget, 'clear')) else None  # type: ignore
        
        def _auto_refresh(self) -> None:
            """Auto-refresh library periodically - Single Responsibility"""
            # Only refresh if we have a project loaded and it's not already refreshing
            if self._current_project_path and not hasattr(self, '_refreshing'):
                self._refreshing = True
                self.refresh_library()
                # Reset the flag after a short delay
                QTimer.singleShot(1000, lambda: setattr(self, '_refreshing', False))  # type: ignore
        
        # Event handlers
        
        def _on_search_text_changed(self, text: str) -> None:
            """Handle search text changes - Real-time search"""
            # Debounce search for performance
            if hasattr(self, '_search_timer'):
                self._search_timer.stop()  # type: ignore
            
            self._search_timer = QTimer()  # type: ignore
            self._search_timer.timeout.connect(self._perform_search)  # type: ignore
            self._search_timer.setSingleShot(True)  # type: ignore
            self._search_timer.start(500)  # 500ms delay
        
        def _on_selection_changed(self) -> None:
            """Handle asset selection changes - Single Responsibility"""
            print(f"🎯 Selection changed event fired!")
            
            current_list = self._get_current_asset_list()
            if not current_list:
                print(f"❌ No current list found")
                return
            
            # Get selected assets
            selected_items = current_list.selectedItems()  # type: ignore
            print(f"🎯 Selected items count: {len(selected_items)}")
            
            self._selected_assets = []
            
            for item in selected_items:
                asset = item.data(Qt.UserRole)  # type: ignore
                print(f"🎯 Item data type: {type(asset)}")
                # Use duck typing instead of isinstance to avoid module path issues
                if asset and hasattr(asset, 'file_path') and hasattr(asset, 'display_name'):
                    self._selected_assets.append(asset)
                    print(f"✅ Asset selected: {asset.display_name}")
            
            # Emit signals
            self.selection_changed.emit(self._selected_assets)  # type: ignore
            
            # Emit single asset selection for preview
            if len(self._selected_assets) == 1:
                self.asset_selected.emit(self._selected_assets[0])  # type: ignore
        
        # Context menu helper methods - Clean Code implementation
        def _set_asset_color(self, asset: Asset, color: str) -> None:
            """Set asset color coding - DEPRECATED - Use _set_asset_type_color instead"""
            # Store color in our color mapping
            self._asset_colors[asset.id] = color
            
            # Update UI immediately
            self._refresh_asset_display(asset)
            self._set_status(f"Applied {color} color to {asset.name}")
        
        def _set_asset_type_color(self, asset: Any, asset_type: str) -> None:
            """Set asset type color coding - Synced with Asset Type Colors system"""
            # Validate asset type exists in our dictionary
            if asset_type not in self.ASSET_TYPE_COLORS:
                print(f"⚠️ Unknown asset type: {asset_type}")
                return
            
            # Store color type name in our color mapping
            self._asset_colors[asset.id] = asset_type
            
            # Get RGB values from dictionary and create QColor
            rgb_values = self.ASSET_TYPE_COLORS[asset_type]
            if QColor is not None:  # type: ignore
                color = QColor(*rgb_values)  # type: ignore
            else:
                # Fallback if QColor not available (shouldn't happen in Maya)
                color = None
            
            # Update UI immediately
            if color is not None:
                self._refresh_asset_display_with_qcolor(asset, color)
            else:
                self._refresh_asset_display(asset)
            
            self._set_status(f"Applied {asset_type} color to {asset.display_name if hasattr(asset, 'display_name') else asset.name}")
        
        def _clear_asset_color(self, asset: Any) -> None:
            """Clear asset color coding - Single Responsibility"""
            if asset.id in self._asset_colors:
                del self._asset_colors[asset.id]
                
            # Update UI immediately
            self._refresh_asset_display(asset)
            self._set_status(f"Cleared color for {asset.display_name if hasattr(asset, 'display_name') else asset.name}")
        
        def _apply_color_coding(self, item, color: str) -> None:  # type: ignore
            """Apply color coding to list widget item - Single Responsibility"""
            if not color:
                return
                
            # Build dynamic color map from ASSET_TYPE_COLORS dictionary
            color_map = {
                # Legacy simple colors
                'red': '#ffcccc',
                'green': '#ccffcc', 
                'blue': '#ccccff',
                'yellow': '#ffffcc',
                'orange': '#ffddcc',
                'purple': '#ddccff',
            }
            
            # Add Asset Type Colors dynamically from ASSET_TYPE_COLORS dictionary
            # Store as RGB tuples for proper QColor construction
            asset_type_colors = {}
            for asset_type, rgb_tuple in self.ASSET_TYPE_COLORS.items():
                asset_type_colors[asset_type] = rgb_tuple
            
            # Check if this is an asset type color (needs RGB construction)
            if color in asset_type_colors:
                r, g, b = asset_type_colors[color]
                bg_color = QColor(r, g, b, 100)  # type: ignore - RGBA with transparency
                item.setBackground(bg_color)  # type: ignore
            else:
                # Legacy color - use hex string
                bg_color_str = color_map.get(color, '#ffffff')
                item.setBackground(QColor(bg_color_str))  # type: ignore
        
        def _refresh_asset_display(self, asset: Any) -> None:
            """Refresh display of specific asset - Single Responsibility"""
            print(f"🔄 _refresh_asset_display called for: {asset.display_name if hasattr(asset, 'display_name') else 'Unknown'}")
            print(f"   Asset has tags: {hasattr(asset, 'tags') and asset.tags}")
            
            # Update asset item in ALL list widgets (Library, Recent, Favorites)
            list_widgets = []
            if self._asset_list:
                list_widgets.append(self._asset_list)
            # Get Recent and Favorites tabs from tab widget
            if self._tab_widget:
                recent_list = self._tab_widget.widget(1)  # Recent tab
                if recent_list and hasattr(recent_list, 'count'):
                    list_widgets.append(recent_list)
                favorites_list = self._tab_widget.widget(2)  # Favorites tab
                if favorites_list and hasattr(favorites_list, 'count'):
                    list_widgets.append(favorites_list)
            
            print(f"   Updating {len(list_widgets)} list widgets")
            items_found = 0
            
            for list_widget in list_widgets:
                for i in range(list_widget.count()):  # type: ignore
                    item = list_widget.item(i)  # type: ignore
                    if item and item.data(Qt.UserRole) == asset:  # type: ignore
                        items_found += 1
                        print(f"   Found item #{items_found} to update")
                        
                        # Update display text with tag indicator
                        display_text = asset.display_name
                        tooltip_text = asset.display_name
                        
                        if hasattr(asset, 'tags') and asset.tags:
                            tag_count = len(asset.tags)
                            display_text = f"{display_text} 🏷️×{tag_count}"
                            tags_str = ", ".join(asset.tags)
                            tooltip_text = f"{asset.display_name}\n\nTags: {tags_str}"
                            print(f"   Setting display text with {tag_count} tags: {display_text}")
                        
                        item.setText(display_text)  # type: ignore
                        item.setToolTip(tooltip_text)  # type: ignore
                        
                        # Update background color (preserves icon)
                        color = self._asset_colors.get(asset.id)
                        if color:
                            print(f"   Applying color: {color}")
                            self._apply_color_coding(item, color)
                        else:
                            print(f"   Clearing background (transparent)")
                            # Clear background if no color (preserves icon)
                            transparent = QColor(0, 0, 0, 0)  # type: ignore
                            transparent.setAlpha(0)  # Explicitly set to fully transparent
                            item.setBackground(transparent)  # type: ignore
            
            print(f"✅ Refresh complete. Updated {items_found} items")
        
        def _refresh_asset_display_with_qcolor(self, asset: Any, qcolor) -> None:  # type: ignore
            """Refresh display of specific asset with QColor - Single Responsibility"""
            # Update asset item in ALL list widgets (Library, Recent, Favorites)
            list_widgets = []
            if self._asset_list:
                list_widgets.append(self._asset_list)
            # Get Recent and Favorites tabs from tab widget
            if self._tab_widget:
                recent_list = self._tab_widget.widget(1)  # Recent tab
                if recent_list and hasattr(recent_list, 'count'):
                    list_widgets.append(recent_list)
                favorites_list = self._tab_widget.widget(2)  # Favorites tab
                if favorites_list and hasattr(favorites_list, 'count'):
                    list_widgets.append(favorites_list)
            
            for list_widget in list_widgets:
                for i in range(list_widget.count()):  # type: ignore
                    item = list_widget.item(i)  # type: ignore
                    if item and item.data(Qt.UserRole) == asset:  # type: ignore
                        # Apply QColor with transparency for better visual (preserves icon)
                        transparent_color = QColor(qcolor)  # type: ignore
                        transparent_color.setAlpha(100)  # Set to semi-transparent
                        item.setBackground(transparent_color)  # type: ignore
        
        def _open_color_manager(self) -> None:
            """Open color coding manager - Single Responsibility"""
            try:
                from ..dialogs.color_coding_manager_dialog import ColorCodingManagerDialog
                dialog = ColorCodingManagerDialog(self)
                
                # Store reference to dialog for color updates
                self._color_manager_dialog = dialog
                
                # Connect signal to refresh colors when changed
                dialog.color_scheme_changed.connect(lambda: self._on_color_scheme_changed(dialog))  # type: ignore
                
                dialog.exec()  # type: ignore
            except ImportError as e:
                print(f"⚠️ Could not import ColorCodingManagerDialog: {e}")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Color Manager",
                    "Color Coding Manager dialog is being loaded...\n\n"
                    "This feature allows you to customize asset type colors."
                )
            except Exception as e:
                print(f"❌ Error opening color manager: {e}")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Failed to open Color Manager:\n{str(e)}")
        
        def _on_color_scheme_changed(self, dialog) -> None:  # type: ignore
            """Handle color scheme changes from color manager - Single Responsibility"""
            # Update ASSET_TYPE_COLORS dictionary from dialog's current scheme
            try:
                current_colors = dialog.get_current_color_scheme()
                
                # Update class-level dictionary with new RGB values
                for asset_type, qcolor in current_colors.items():
                    # Convert QColor to RGB tuple
                    rgb_tuple = (qcolor.red(), qcolor.green(), qcolor.blue())
                    self.ASSET_TYPE_COLORS[asset_type] = rgb_tuple
                
                print(f"✅ Updated ASSET_TYPE_COLORS with new color scheme")
                
                # Emit signal to notify other components (like color keychart) of the change
                self.color_scheme_changed.emit(current_colors)
                
            except Exception as e:
                print(f"⚠️ Error updating asset type colors: {e}")
            
            # Refresh all asset displays to show updated colors
            self.refresh_library()
        
        def get_current_color_scheme(self) -> Dict[str, 'QColor']:
            """Get current color scheme as QColor dictionary - Single Responsibility"""
            from PySide6.QtGui import QColor
            
            color_scheme = {}
            for asset_type, rgb_tuple in self.ASSET_TYPE_COLORS.items():
                r, g, b = rgb_tuple
                color_scheme[asset_type] = QColor(r, g, b)
            
            return color_scheme
        
        def _add_tag_to_asset(self, asset: Any) -> None:
            """Add tag to asset - Single Responsibility"""
            from PySide6.QtWidgets import QInputDialog, QMessageBox
            
            print(f"🏷️  _add_tag_to_asset called for: {asset.display_name if hasattr(asset, 'display_name') else asset.name}")
            
            # Build dynamic tag list: predefined tags + all used tags (sorted)
            available_tags = sorted(list(self._all_used_tags))
            custom_tag_count = len(self._all_used_tags) - len(self._predefined_tags)
            print(f"🏷️  Available tags: {len(available_tags)} total ({len(self._predefined_tags)} predefined, {custom_tag_count} custom)")
            print(f"🏷️  Tag list: {available_tags[:5]}{'...' if len(available_tags) > 5 else ''}")
            
            # Show dialog to select or create tag
            tag, ok = QInputDialog.getItem(
                self,
                "Add Tag",
                f"Select a tag to add to '{asset.display_name if hasattr(asset, 'display_name') else asset.name}':\n\n"
                f"(You can also type a custom tag name)",
                available_tags,
                0,
                True  # Allow custom text - CRITICAL for custom tags!
            )
            
            if ok and tag:
                tag = tag.strip()  # Remove any extra whitespace
                if not tag:
                    print(f"⚠️  Empty tag name, ignoring")
                    return
                
                print(f"🏷️  User selected/entered tag: '{tag}'")
                
                # Add to global tag set (so it shows up in future dropdowns)
                if tag not in self._all_used_tags:
                    self._all_used_tags.add(tag)
                    print(f"🏷️  ✨ NEW TAG ADDED '{tag}' to global tag registry!")
                    print(f"🏷️  Total unique tags: {len(self._all_used_tags)} (predefined: {len(self._predefined_tags)}, custom: {len(self._all_used_tags) - len(self._predefined_tags)})")
                else:
                    print(f"🏷️  Tag '{tag}' already in registry (not adding duplicate)")
                
                # Initialize tags list if it doesn't exist
                if not hasattr(asset, 'tags') or asset.tags is None:
                    asset.tags = []
                    print(f"🏷️  Initialized tags list for asset")
                
                # Add tag if not already present on this asset
                if tag not in asset.tags:
                    asset.tags.append(tag)
                    print(f"🏷️  Added tag '{tag}' to asset. Total tags on asset: {len(asset.tags)}")
                    self._set_status(f"Added tag '{tag}' to {asset.display_name if hasattr(asset, 'display_name') else asset.name}")
                    
                    # Save asset metadata FIRST
                    print(f"💾 Saving metadata...")
                    self._save_asset_metadata(asset)
                    
                    # Refresh display to show tag indicator
                    print(f"🔄 Refreshing display...")
                    self._refresh_asset_display(asset)
                    
                    # Update info panel if this asset is currently selected
                    if asset in self._selected_assets:
                        print(f"🔄 Refreshing info panel for selected asset")
                        self.asset_selected.emit(asset)
                    
                    print(f"✅ Tag addition complete!")
                else:
                    print(f"⚠️  Tag '{tag}' already exists on this asset")
                    QMessageBox.information(
                        self,
                        "Tag Exists",
                        f"Asset already has tag '{tag}'"
                    )
        
        def _remove_tags_from_asset(self, asset: Any) -> None:
            """Remove tags from asset - Single Responsibility"""
            from PySide6.QtWidgets import QInputDialog, QMessageBox
            
            # Check if asset has any tags
            if not hasattr(asset, 'tags') or not asset.tags:
                QMessageBox.information(
                    self,
                    "No Tags",
                    f"Asset '{asset.display_name if hasattr(asset, 'display_name') else asset.name}' has no tags to remove."
                )
                return
            
            # Show dialog to select tag to remove
            tag, ok = QInputDialog.getItem(
                self,
                "Remove Tag",
                f"Select a tag to remove from '{asset.display_name if hasattr(asset, 'display_name') else asset.name}':",
                asset.tags,
                0,
                False  # Don't allow custom text
            )
            
            if ok and tag:
                asset.tags.remove(tag)
                self._set_status(f"Removed tag '{tag}' from {asset.display_name if hasattr(asset, 'display_name') else asset.name}")
                
                # Save asset metadata
                self._save_asset_metadata(asset)
                
                # Refresh display
                self._refresh_asset_display(asset)
                
                # Update info panel if this asset is currently selected
                if asset in self._selected_assets:
                    print(f"🔄 Refreshing info panel after tag removal")
                    self.asset_selected.emit(asset)
        
        def _save_asset_metadata(self, asset: Any) -> None:
            """Save asset metadata including tags - Single Responsibility"""
            try:
                # In production, this would save to a database or metadata file
                # For now, we'll save tags to a sidecar JSON file
                import json
                from pathlib import Path
                
                # Handle both Path objects and strings
                file_path = Path(asset.file_path) if isinstance(asset.file_path, str) else asset.file_path
                metadata_path = file_path.with_suffix(file_path.suffix + '.meta')
                
                metadata = {
                    'tags': asset.tags if hasattr(asset, 'tags') else [],
                    'is_favorite': getattr(asset, 'is_favorite', False),
                    'category': getattr(asset, 'category', 'general'),
                    'modified_date': str(getattr(asset, 'modified_date', ''))
                }
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
                    
                print(f"💾 Saved metadata for {asset.display_name if hasattr(asset, 'display_name') else asset.name}")
                
            except Exception as e:
                print(f"⚠️ Failed to save asset metadata: {e}")
                # Don't show error to user - metadata saving is non-critical
        
        def _load_asset_metadata(self, asset: Any) -> None:
            """Load asset metadata including tags from sidecar file - Single Responsibility"""
            try:
                import json
                from pathlib import Path
                
                # Handle both Path objects and strings
                file_path = Path(asset.file_path) if isinstance(asset.file_path, str) else asset.file_path
                metadata_path = file_path.with_suffix(file_path.suffix + '.meta')
                
                if not metadata_path.exists():
                    return  # No metadata file exists yet
                
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Apply loaded metadata to asset
                if 'tags' in metadata:
                    asset.tags = metadata['tags']
                    # Add these tags to our global tag set
                    if asset.tags:
                        before_count = len(self._all_used_tags)
                        self._all_used_tags.update(asset.tags)
                        after_count = len(self._all_used_tags)
                        new_tags_count = after_count - before_count
                        print(f"📂 Loaded {len(asset.tags)} tags from metadata: {asset.tags}")
                        if new_tags_count > 0:
                            print(f"📂 ✨ Added {new_tags_count} NEW tags to registry. Total: {after_count}")
                        else:
                            print(f"📂 No new tags (all already in registry). Total: {after_count}")
                
                if 'is_favorite' in metadata:
                    asset.is_favorite = metadata['is_favorite']
                
                if 'category' in metadata:
                    asset.category = metadata['category']
                
                print(f"📂 Loaded metadata for {asset.display_name if hasattr(asset, 'display_name') else asset.name}: {len(asset.tags) if hasattr(asset, 'tags') and asset.tags else 0} tags")
                
            except Exception as e:
                print(f"⚠️ Failed to load asset metadata: {e}")
                # Don't show error to user - metadata loading is non-critical
        
        def refresh_thumbnails_for_assets(self, asset_paths: List[Any]) -> None:
            """Force refresh thumbnails for specific assets - Single Responsibility"""
            print(f"🔄 Refreshing thumbnails for {len(asset_paths)} assets...")
            
            # Get icon size for consistency
            icon_size = (64, 64)
            
            # Clear cache for these assets first to force regeneration
            for asset_path in asset_paths:
                try:
                    self._thumbnail_service.clear_cache_for_file(asset_path)  # type: ignore
                    print(f"🗑️ Cleared cache for: {asset_path.name if hasattr(asset_path, 'name') else asset_path}")
                except Exception as e:
                    print(f"❌ Failed to clear cache for {asset_path}: {e}")
            
            # Update thumbnails in ALL list widgets (Library, Recent, Favorites)
            list_widgets = []
            if self._asset_list:
                list_widgets.append(self._asset_list)
            # Get Recent and Favorites tabs from tab widget
            if self._tab_widget:
                recent_list = self._tab_widget.widget(1)  # Recent tab
                if recent_list and hasattr(recent_list, 'count'):
                    list_widgets.append(recent_list)
                favorites_list = self._tab_widget.widget(2)  # Favorites tab
                if favorites_list and hasattr(favorites_list, 'count'):
                    list_widgets.append(favorites_list)
            
            # Find and update items in all lists
            for list_widget in list_widgets:
                for i in range(list_widget.count()):  # type: ignore
                    item = list_widget.item(i)   # type: ignore
                    if item:
                        asset = item.data(Qt.UserRole)   # type: ignore
                        # Use duck typing instead of isinstance to avoid module path issues
                        if asset and hasattr(asset, 'file_path') and asset.file_path in asset_paths:
                            print(f"🔄 Refreshing thumbnail for list item: {asset.display_name if hasattr(asset, 'display_name') else 'Unknown'}")
                            # Generate new thumbnail asynchronously
                            self._generate_thumbnail_async(asset, item, icon_size)
        
        def force_refresh_all_thumbnails(self) -> None:
            """Force refresh all thumbnails in the current view - Single Responsibility"""
            if not self._current_assets:
                return
            
            asset_paths = [asset.file_path for asset in self._current_assets]
            self.refresh_thumbnails_for_assets(asset_paths)
        
        def _open_tag_manager(self) -> None:
            """Open tag manager - Single Responsibility"""
            from ..dialogs.tag_manager_dialog import TagManagerDialog
            
            print(f"🏷️  Opening Tag Manager with {len(self._all_used_tags)} tags")
            
            # Create dialog and pass current tag registry
            dialog = TagManagerDialog(self)
            
            # Convert set to dict format expected by dialog (tag_name -> {color, description})
            current_tags = {}
            for tag_name in self._all_used_tags:
                # Check if it's a predefined tag
                is_predefined = tag_name in self._predefined_tags
                current_tags[tag_name] = {
                    "color": "#2196F3" if is_predefined else "#CCCCCC",  # Blue for predefined, gray for custom
                    "description": f"{'Predefined' if is_predefined else 'Custom'} tag: {tag_name}",
                    "predefined": is_predefined
                }
            dialog.set_tags(current_tags)
            

            # Show dialog
            result = dialog.exec()
            
            # If user clicked OK/Save, update the global tag registry
            if result:
                updated_tags = dialog.get_tags()
                print(f"🏷️  Tag Manager closed. Updating registry with {len(updated_tags)} tags")
                
                # Clear and rebuild the tag registry (preserving predefined tags)
                self._all_used_tags.clear()
                self._all_used_tags.update(self._predefined_tags)  # Always keep predefined
                
                # Add all tags from the dialog
                for tag_name in updated_tags.keys():
                    self._all_used_tags.add(tag_name)
                
                print(f"🏷️  ✅ Global tag registry updated: {len(self._all_used_tags)} total tags")
                print(f"🏷️  Tags: {sorted(list(self._all_used_tags))[:10]}{'...' if len(self._all_used_tags) > 10 else ''}")
                
                # Save custom tags to config file
                self._save_custom_tags()
                
                # Refresh the currently selected asset's info panel if any
                if self._selected_assets and len(self._selected_assets) == 1:
                    selected_asset = self._selected_assets[0]
                    print(f"🏷️  Refreshing info panel for selected asset: {selected_asset.display_name if hasattr(selected_asset, 'display_name') else 'Unknown'}")
                    # Re-emit the asset_selected signal to update the info panel
                    self.asset_selected.emit(selected_asset)
                    
                print(f"🏷️  Tag Manager updates complete!")
        
        def _load_custom_tags(self) -> None:
            """Load custom tags from config file - Single Responsibility"""
            try:
                import json
                from pathlib import Path
                from PySide6.QtCore import QSettings
                
                # Use QSettings to get config directory
                settings = QSettings("MikeStumbo", "AssetManager")
                config_dir = Path(settings.fileName()).parent
                config_file = config_dir / "custom_tags.json"
                
                if not config_file.exists():
                    print(f"🏷️  No custom tags config file found")
                    return
                
                with open(config_file, 'r', encoding='utf-8') as f:
                    custom_tags = json.load(f)
                
                if isinstance(custom_tags, list):
                    self._all_used_tags.update(custom_tags)
                    print(f"🏷️  ✅ Loaded {len(custom_tags)} custom tags from config")
                    print(f"🏷️  Total tags in registry: {len(self._all_used_tags)}")
                    
            except Exception as e:
                print(f"⚠️  Failed to load custom tags: {e}")
        
        def _save_custom_tags(self) -> None:
            """Save custom tags to config file - Single Responsibility"""
            try:
                import json
                from pathlib import Path
                from PySide6.QtCore import QSettings
                
                # Get only custom tags (exclude predefined)
                custom_tags = [tag for tag in self._all_used_tags if tag not in self._predefined_tags]
                
                # Use QSettings to get config directory
                settings = QSettings("MikeStumbo", "AssetManager")
                config_dir = Path(settings.fileName()).parent
                config_dir.mkdir(parents=True, exist_ok=True)
                config_file = config_dir / "custom_tags.json"
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(sorted(custom_tags), f, indent=2)
                
                print(f"🏷️  💾 Saved {len(custom_tags)} custom tags to config")
                print(f"🏷️  Config file: {config_file}")
                
            except Exception as e:
                print(f"❌ Failed to save custom tags: {e}")
        
        def _show_collection_manager(self) -> None:
            """Open collection manager from collections widget - Single Responsibility"""
            try:
                from ..collection_manager_dialog import CollectionManagerDialog
                dialog = CollectionManagerDialog(self)
                dialog.exec()
            except ImportError:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Feature Not Available", "Collection Manager is not yet fully implemented.")
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Failed to open Collection Manager: {e}")
        
        def _add_to_collection(self, asset: Any) -> None:
            """Add asset to collection - Single Responsibility"""
            print(f"Adding asset {asset.name} to collection")
            # TODO: Implement collections system
        
        def _create_new_collection(self) -> None:
            """Create new collection - Single Responsibility"""
            from ..dialogs.collection_dialog import CollectionDialog
            dialog = CollectionDialog(self)
            if dialog.exec():
                collection_name = dialog.get_collection_name()
                print(f"Creating new collection: {collection_name}")
        
        def _open_collections_manager(self) -> None:
            """Open collections manager - Single Responsibility"""
            from ..dialogs.collections_manager_dialog import CollectionsManagerDialog
            dialog = CollectionsManagerDialog(self)
            dialog.exec()
        
        def _on_item_double_clicked(self, item) -> None:  # type: ignore
            """Handle asset double-click - Import action"""
            print(f"🖱️ Double-click event fired!")
            asset = item.data(Qt.UserRole)  # type: ignore
            print(f"🖱️ Asset data type: {type(asset)}")
            print(f"🖱️ Asset data repr: {repr(asset)}")
            
            # Use duck typing instead of isinstance - check for required attributes
            if asset and hasattr(asset, 'file_path') and hasattr(asset, 'display_name'):
                print(f"✅ Valid asset object - emitting double-click signal for: {asset.display_name}")
                self.asset_double_clicked.emit(asset)  # type: ignore
            else:
                print(f"❌ Asset data is not a valid asset object!")
                print(f"   Has file_path: {hasattr(asset, 'file_path') if asset else False}")
                print(f"   Has display_name: {hasattr(asset, 'display_name') if asset else False}")
        
        def _show_advanced_search(self) -> None:
            """Show advanced search dialog - Single Responsibility"""
            try:
                from ...ui.dialogs.advanced_search_dialog import AdvancedSearchDialog
                
                dialog = AdvancedSearchDialog(self)
                if dialog.exec() == dialog.DialogCode.Accepted:  # type: ignore
                    criteria = dialog.get_search_criteria()
                    if criteria:
                        self.search_with_criteria(criteria)
            except ImportError:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Feature Not Available", "Advanced Search dialog is not implemented yet.")
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Failed to open advanced search: {e}")
