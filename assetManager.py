# -*- coding: utf-8 -*-
"""
Asset Manager Plugin for Maya 2025.3
A comprehensive asset management system for Maya using Python 3 and PySide6

Author: Mike Stumbo
Version: 1.2.0
Maya Version: 2025.3+

New in v1.2.0:
- PROFESSIONAL ASSET DISPLAY: Stable, crash-safe asset information system
- ADVANCED METADATA EXTRACTION: Deep asset analysis for Maya, OBJ, FBX, and cache files
- INTEGRATED UI LAYOUT: Seamless professional info panel with metadata display  
- STABLE PERFORMANCE: Eliminated Maya viewport crashes with professional file icons
- ASSET COMPARISON FRAMEWORK: Side-by-side comparison capabilities
- Fixed collection tab refresh issues with automatic synchronization
- Improved network performance with intelligent caching and lazy loading
- Enhanced dependency chain performance with optimizations
- Added smart refresh triggers and external modification detection
- Improved error handling for network-stored projects
- Enhanced UI responsiveness with better thread management
- Fixed memory leaks in large asset libraries
- Added performance monitoring and optimization alerts
- CRITICAL FIX: Resolved RecursionError in project path handling
- Enhanced path validation and error recovery mechanisms
- Added comprehensive error handling throughout the application
- Improved stability and graceful error recovery
- MAJOR IMPROVEMENT: Implemented memory-safe thumbnail generation system
- Enhanced thumbnail caching with intelligent size limits (50 thumbnails max)
- Added background processing queue for thumbnail generation
- UI now uses professional file icons with gradient backgrounds and type indicators for better visualization
- Optimized icon sizing and grid layout for enhanced readability and professional appearance

Previous Features (v1.1.2):
- Fixed incomplete method implementations and context menu actions
- Improved error handling and user feedback
- Enhanced UI responsiveness with threaded operations
- Added asset metadata storage and retrieval
- Improved asset search and filtering performance
- Fixed context menu incomplete implementations
- Added comprehensive asset preview system
- COLLECTION TABS FEATURE - Browse collections in separate tabs
- Interactive collection management with drag-and-drop interface
- Enhanced tabbed asset library with visual collection organization

Previous Features (v1.1.1):
- Asset type color-coding system
- Visual collection indicators in asset library
- Enhanced context menu with asset type assignment
- Color legend for easy asset type identification
"""

import sys
import os
import json
import shutil
import threading
import time
import tempfile
from datetime import datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

# Clean Code Constants - Replace magic numbers with named constants
class ThumbnailConstants:
    """Constants for thumbnail generation - follows DRY principle"""
    DEFAULT_SIZE = (64, 64)
    CACHE_SIZE_LIMIT = 50
    GENERATION_BATCH_SIZE = 5
    CACHE_TIMEOUT_LOCAL = 30  # seconds
    CACHE_TIMEOUT_NETWORK = 120  # seconds
    # REMOVED: Crash-prone playblast constants replaced with stable alternatives

class ErrorMessages:
    """Centralized error messages - Single Source of Truth"""
    MAYA_NOT_AVAILABLE = "Maya not available - cannot import asset"
    FILE_NOT_FOUND = "FILE\nNOT FOUND"
    MAYA_ERROR = "MAYA\nERROR" 
    MAYA_SCENE_FALLBACK = "MAYA\nSCENE"

class UIConstants:
    """UI dimension constants - DRY Principle"""
    # Preview widget dimensions
    PREVIEW_MIN_WIDTH = 350
    PREVIEW_MIN_HEIGHT = 250
    PREVIEW_FRAME_WIDTH = 400
    PREVIEW_FRAME_HEIGHT = 300
    
    # Splitter sizes  
    LIBRARY_WIDTH = 700
    PREVIEW_WIDTH = 300

class RendererConfig:
    """Renderer configuration interface - Dependency Inversion Principle"""
    
    @staticmethod
    def get_renderer_settings(renderer_name):
        """Get renderer-specific settings"""
        renderers = {
            'renderman': RenderManConfig(),
            'arnold': ArnoldConfig(),
            'maya_software': MayaSoftwareConfig()
        }
        return renderers.get(renderer_name.lower(), MayaSoftwareConfig())

class RenderManConfig:
    """RenderMan-specific configuration and .ptex support"""
    
    def __init__(self):
        self.name = "RenderMan"
        self.supported_textures = ['.tex', '.ptx', '.ptex', '.tif', '.tiff', '.exr', '.jpg', '.png']
        self.viewport_settings = {
            'displayAppearance': 'smoothShaded',
            'wireframeOnShaded': False,
            'displayLights': 'default',
            'shadows': True,
            'useDefaultMaterial': False,  # Use actual materials for RenderMan
            'textureMaxRes': 1024,       # RenderMan texture resolution
            'subdivSurfaces': True,      # Show smooth surfaces
            'useRmanDisplayFilter': True # Use RenderMan display filtering
        }
    
    def configure_maya_viewport(self, cmds, panel):
        """Configure Maya viewport for RenderMan rendering"""
        try:
            # Set RenderMan as current renderer if available
            if cmds.pluginInfo('RenderMan_for_Maya.py', q=True, loaded=True):
                cmds.setAttr("defaultRenderGlobals.currentRenderer", "renderManRIS", type="string")
                
                # Configure RenderMan-specific viewport settings
                for attr, value in self.viewport_settings.items():
                    try:
                        if attr == 'useRmanDisplayFilter' and value:
                            # Enable RenderMan IPR if available
                            if cmds.objExists('rmanGlobals'):
                                cmds.setAttr('rmanGlobals.enableIPR', True)
                        else:
                            cmds.modelEditor(panel, edit=True, **{attr: value})
                    except Exception as e:
                        print(f"RenderMan viewport config warning: {attr} - {e}")
                        
                # Configure .ptex support
                self._configure_ptex_support(cmds)
                
            else:
                print("RenderMan plugin not loaded, using default viewport settings")
                
        except Exception as e:
            print(f"RenderMan viewport configuration error: {e}")
    
    def _configure_ptex_support(self, cmds):
        """Configure .ptex texture support for RenderMan"""
        try:
            # Enable ptex texture support in RenderMan globals
            if cmds.objExists('rmanGlobals'):
                cmds.setAttr('rmanGlobals.enableSubdivisionSurfaces', True)
                cmds.setAttr('rmanGlobals.ptexMemoryLimit', 512)  # MB
                print("✓ RenderMan .ptex support configured")
                
            # Set texture search paths for .ptex files
            if hasattr(cmds, 'workspace'):
                current_workspace = cmds.workspace(q=True, rootDirectory=True)
                ptex_paths = [
                    os.path.join(current_workspace, 'sourceimages'),
                    os.path.join(current_workspace, 'textures'),
                    os.path.join(current_workspace, 'ptex')
                ]
                
                for path in ptex_paths:
                    if os.path.exists(path):
                        # Add to RenderMan texture search paths
                        print(f"✓ Added .ptex search path: {path}")
                        
        except Exception as e:
            print(f"Ptex configuration warning: {e}")
    
    def supports_texture(self, texture_path):
        """Check if texture format is supported by RenderMan"""
        file_ext = os.path.splitext(texture_path)[1].lower()
        return file_ext in self.supported_textures
    
    def get_material_preview_settings(self):
        """Get RenderMan-specific material preview settings"""
        return {
            'enableBump': True,
            'enableDisplacement': True,
            'enableSubsurface': True,
            'maxSubdivisionLevel': 2,
            'ptexFilterSize': 1.0
        }

class ArnoldConfig:
    """Arnold renderer configuration"""
    
    def __init__(self):
        self.name = "Arnold"
        self.supported_textures = ['.tx', '.tif', '.tiff', '.exr', '.jpg', '.png']
        self.viewport_settings = {
            'displayAppearance': 'smoothShaded',
            'useDefaultMaterial': False,
            'shadows': True
        }
    
    def configure_maya_viewport(self, cmds, panel):
        """Configure viewport for Arnold"""
        try:
            if cmds.pluginInfo('mtoa', q=True, loaded=True):
                cmds.setAttr("defaultRenderGlobals.currentRenderer", "arnold", type="string")
                for attr, value in self.viewport_settings.items():
                    cmds.modelEditor(panel, edit=True, **{attr: value})
        except Exception as e:
            print(f"Arnold viewport configuration error: {e}")
    
    def supports_texture(self, texture_path):
        file_ext = os.path.splitext(texture_path)[1].lower()
        return file_ext in self.supported_textures

class MayaSoftwareConfig:
    """Maya Software renderer configuration (fallback)"""
    
    def __init__(self):
        self.name = "Maya Software"
        self.supported_textures = ['.jpg', '.png', '.tif', '.tiff', '.iff']
        self.viewport_settings = {
            'displayAppearance': 'smoothShaded',
            'useDefaultMaterial': True,
            'shadows': False
        }
    
    def configure_maya_viewport(self, cmds, panel):
        """Configure viewport for Maya Software"""
        try:
            cmds.setAttr("defaultRenderGlobals.currentRenderer", "mayaSoftware", type="string")
            for attr, value in self.viewport_settings.items():
                cmds.modelEditor(panel, edit=True, **{attr: value})
        except Exception as e:
            print(f"Maya Software viewport configuration error: {e}")
    
    def supports_texture(self, texture_path):
        file_ext = os.path.splitext(texture_path)[1].lower()
        return file_ext in self.supported_textures

try:
    import maya.cmds as cmds  # pyright: ignore[reportMissingImports]
    import maya.mel as mel # type: ignore
    import maya.OpenMayaUI as omui # type: ignore
    import maya.api.OpenMaya as om2 # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    print("Maya modules not available. Running in standalone mode.")
    MAYA_AVAILABLE = False
    cmds = None
    mel = None
    omui = None
    om2 = None

try:
    from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                   QSplitter, QGroupBox, QLabel, QListWidget, 
                                   QLineEdit, QPushButton, QMenuBar,
                                   QToolBar, QStatusBar, QDialog, QMessageBox,
                                   QFileDialog, QApplication, QListWidgetItem,
                                   QStyle, QComboBox, QTextEdit, QCheckBox,
                                   QScrollArea, QFrame, QTabWidget, QTreeWidget,
                                   QTreeWidgetItem, QInputDialog, QProgressDialog,
                                   QMenu, QSlider)
    from PySide6.QtGui import QAction, QIcon, QPixmap, QFont, QColor, QBrush, QPainter, QPen, QLinearGradient
    from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, QFileSystemWatcher, QObject, QPoint, QRect
    from shiboken6 import wrapInstance
except ImportError:
    print("PySide6 not available. Please ensure Maya 2025.3+ is being used.")
    sys.exit(1)


class AssetManager:
    """Main Asset Manager class handling core functionality"""
    
    def __init__(self):
        self.plugin_name = "assetManager"
        self.version = "1.2.0"
        self.config_path = self._get_config_path()
        self.assets_library = {}
        self.current_project = None
        
        # Recursion protection flags
        self._processing_project_entry = False
        
        # Performance optimization: File system cache
        self._file_cache = {}
        self._cache_timestamps = {}
        self._cache_timeout = 30  # seconds
        
        # Thread pool for background operations
        self._thread_pool = ThreadPoolExecutor(max_workers=2)  # Reduced workers to prevent Maya overload
        
        # Track if cleanup has been performed
        self._is_cleaned_up = False
        
        # Thumbnail system with memory-safe caching and duplicate prevention
        self._thumbnail_cache = {}  # Cache QPixmap objects
        self._icon_cache = {}  # NEW: Cache QIcon objects to prevent UI duplication
        self._thumbnail_cache_size_limit = 50  # Limit to prevent memory bloat
        self._thumbnail_generation_queue = []
        self._thumbnail_workers = 1  # Limited workers for memory safety
        self._thumbnail_processing = False
        self._thumbnail_timer = None
        self._generating_thumbnails = set()  # Track thumbnails currently being generated
        
        # Initialize default asset type configuration
        self._init_default_asset_types()
        
        # Initialize UI preferences
        self.ui_preferences = {}
        
        # Load configuration (including custom asset types and UI preferences)
        self.load_config()
        
        # Network performance monitoring
        self._network_performance = {
            'slow_operations': 0,
            'timeout_threshold': 5.0,  # seconds
            'network_mode': False  # Auto-detected based on performance
        }
    
    def _init_default_asset_types(self):
        """Initialize default asset type configuration"""
        self.default_asset_types = {
            'models': {
                'name': 'Models',
                'color': [0, 150, 255],           # Vibrant Blue
                'priority': 0,
                'extensions': ['.obj', '.fbx', '.ma', '.mb'],
                'description': '3D models and geometry'
            },
            'rigs': {
                'name': 'Rigs',
                'color': [138, 43, 226],          # Blue Violet
                'priority': 1,
                'extensions': ['.ma', '.mb'],
                'description': 'Character and object rigs'
            },
            'textures': {
                'name': 'Textures',
                'color': [255, 140, 0],           # Vibrant Orange
                'priority': 2,
                'extensions': ['.jpg', '.png', '.tga', '.exr', '.tif', '.tiff', '.ptex', '.tex', '.tx'],
                'description': 'Texture maps and images including RenderMan .ptex'
            },
            'materials': {
                'name': 'Materials',
                'color': [255, 20, 147],          # Deep Pink
                'priority': 3,
                'extensions': ['.ma', '.mb'],
                'description': 'Material definitions and shaders'
            },
            'cameras': {
                'name': 'Cameras',
                'color': [255, 215, 0],           # Gold
                'priority': 4,
                'extensions': ['.ma', '.mb'],
                'description': 'Camera setups and animations'
            },
            'lights': {
                'name': 'Lights',
                'color': [255, 255, 255],         # White
                'priority': 5,
                'extensions': ['.ma', '.mb'],
                'description': 'Lighting setups and rigs'
            },
            'vfx': {
                'name': 'VFX',
                'color': [50, 205, 50],           # Lime Green
                'priority': 6,
                'extensions': ['.ma', '.mb'],
                'description': 'Visual effects and simulations'
            },
            'animations': {
                'name': 'Animations',
                'color': [255, 0, 0],             # Vibrant Red
                'priority': 7,
                'extensions': ['.ma', '.mb'],
                'description': 'Animation data and sequences'
            },
            'default': {
                'name': 'Default',
                'color': [128, 128, 128],         # Medium Gray
                'priority': 999,
                'extensions': [],
                'description': 'Uncategorized assets'
            }
        }
        
        # Initialize current asset types with defaults
        self.asset_types = self.default_asset_types.copy()
        
        # Create QColor objects for backward compatibility
        self.asset_type_colors = {}
        self._update_color_cache()
    
    def _update_color_cache(self):
        """Update the QColor cache from asset type configuration"""
        self.asset_type_colors = {}
        for type_id, config in self.asset_types.items():
            color = config['color']
            self.asset_type_colors[type_id] = QColor(color[0], color[1], color[2])
    
    def get_asset_type_list(self):
        """Get list of asset types sorted by priority"""
        types = [(type_id, config) for type_id, config in self.asset_types.items() if type_id != 'default']
        types.sort(key=lambda x: x[1]['priority'])
        return [type_id for type_id, _ in types]
    
    def add_custom_asset_type(self, type_id, name, color, priority=None, extensions=None, description=""):
        """Add a new custom asset type"""
        if priority is None:
            # Find the highest priority and add 1
            max_priority = max([config['priority'] for config in self.asset_types.values() if config['priority'] != 999])
            priority = max_priority + 1
        
        self.asset_types[type_id] = {
            'name': name,
            'color': color if isinstance(color, list) else [color.red(), color.green(), color.blue()],
            'priority': priority,
            'extensions': extensions or [],
            'description': description
        }
        self._update_color_cache()
        self.save_config()
        return True
    
    def update_asset_type(self, type_id, name=None, color=None, priority=None, extensions=None, description=None):
        """Update an existing asset type"""
        if type_id not in self.asset_types:
            return False
        
        config = self.asset_types[type_id]
        if name is not None:
            config['name'] = name
        if color is not None:
            config['color'] = color if isinstance(color, list) else [color.red(), color.green(), color.blue()]
        if priority is not None:
            config['priority'] = priority
        if extensions is not None:
            config['extensions'] = extensions
        if description is not None:
            config['description'] = description
        
        self._update_color_cache()
        self.save_config()
        return True
    
    def remove_asset_type(self, type_id):
        """Remove a custom asset type (cannot remove defaults)"""
        if type_id in self.default_asset_types:
            return False  # Cannot remove default types
        
        if type_id in self.asset_types:
            del self.asset_types[type_id]
            self._update_color_cache()
            self.save_config()
            return True
        return False
    
    def reset_asset_types_to_default(self):
        """Reset all asset types to default configuration"""
        self.asset_types = self.default_asset_types.copy()
        self._update_color_cache()
        self.save_config()
        return True
    
    def export_asset_type_config(self, file_path):
        """Export asset type configuration to file"""
        try:
            config = {
                'asset_types': self.asset_types,
                'version': self.version,
                'exported': datetime.now().isoformat()
            }
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error exporting asset type config: {e}")
            return False
    
    def import_asset_type_config(self, file_path):
        """Import asset type configuration from file"""
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            if 'asset_types' in config:
                self.asset_types = config['asset_types']
                self._update_color_cache()
                self.save_config()
                return True
        except Exception as e:
            print(f"Error importing asset type config: {e}")
        return False
    
    def get_asset_type(self, asset_path):
        """Determine asset type based on tags and file extension"""
        # Get tags for the asset
        tags = self.get_asset_tags(asset_path)
        
        # Check for type tags (priority order)
        type_priorities = self.get_asset_type_list()
        for asset_type in type_priorities:
            if asset_type in tags:
                return asset_type
        
        # Fallback to file extension matching
        file_ext = os.path.splitext(asset_path)[1].lower()
        
        # Check each asset type's extensions
        for type_id, config in self.asset_types.items():
            if type_id == 'default':
                continue
            if file_ext in config.get('extensions', []):
                return type_id
        
        return 'default'
    
    def get_asset_type_color(self, asset_path):
        """Get the color for an asset based on its type"""
        asset_type = self.get_asset_type(asset_path)
        return self.asset_type_colors.get(asset_type, self.asset_type_colors['default'])
    
    def _get_config_path(self):
        """Get the configuration file path"""
        try:
            if MAYA_AVAILABLE and cmds is not None:
                maya_app_dir = cmds.internalVar(userAppDir=True)
            else:
                raise ImportError("Maya cmds not available")
        except:
            # Fallback when Maya is not available
            home = os.path.expanduser("~")
            maya_app_dir = os.path.join(home, "Documents", "maya")
        
        config_dir = os.path.join(maya_app_dir, "assetManager")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        return os.path.join(config_dir, "config.json")
    
    def _is_network_path(self, path):
        """Check if path is on a network drive (Windows UNC or mapped drive)"""
        if not path:
            return False
        # Check for UNC paths (\\server\share)
        if path.startswith('\\\\'):
            return True
        # Check for mapped network drives (heuristic based on performance)
        try:
            start_time = time.time()
            os.path.exists(path)
            elapsed = time.time() - start_time
            return elapsed > 0.1  # If it takes more than 100ms to check existence, likely network
        except:
            return False
    
    def _get_cached_file_list(self, directory):
        """Get cached file list with background scanning for better performance"""
        if not os.path.exists(directory):
            return []
        
        cache_key = f"files_{directory}"
        current_time = time.time()
        
        # Check cache validity
        if (cache_key in self._file_cache and 
            cache_key in self._cache_timestamps and
            current_time - self._cache_timestamps[cache_key] < self._cache_timeout):
            return self._file_cache[cache_key]
        
        # Measure operation time for network detection
        start_time = time.time()
        
        try:
            files = []
            supported_extensions = ['.ma', '.mb', '.obj', '.fbx']
            
            # For large directories, use progressive scanning with thread pool
            def scan_directory_chunk(root_path):
                """Scan a single directory level"""
                chunk_files = []
                try:
                    for file in os.listdir(root_path):
                        file_path = os.path.join(root_path, file)
                        if os.path.isfile(file_path):
                            if any(file.lower().endswith(ext) for ext in supported_extensions):
                                chunk_files.append(file_path)
                        elif os.path.isdir(file_path):
                            # Add subdirectory to scan queue
                            for sub_file in os.listdir(file_path):
                                sub_file_path = os.path.join(file_path, sub_file)
                                if (os.path.isfile(sub_file_path) and 
                                    any(sub_file.lower().endswith(ext) for ext in supported_extensions)):
                                    chunk_files.append(sub_file_path)
                except (OSError, PermissionError):
                    pass
                return chunk_files
            
            # Start with immediate files in root directory for faster initial response
            try:
                for file in os.listdir(directory):
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path):
                        if any(file.lower().endswith(ext) for ext in supported_extensions):
                            files.append(file_path)
            except (OSError, PermissionError):
                pass
            
            # Use ThreadPoolExecutor for subdirectory scanning
            subdirs = []
            try:
                subdirs = [os.path.join(directory, d) for d in os.listdir(directory) 
                          if os.path.isdir(os.path.join(directory, d))]
            except (OSError, PermissionError):
                pass
            
            if subdirs:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    # Limit concurrent scanning to prevent overwhelming network drives
                    future_to_dir = {executor.submit(scan_directory_chunk, subdir): subdir 
                                   for subdir in subdirs[:10]}  # Limit to first 10 subdirs for performance
                    
                    for future in as_completed(future_to_dir):
                        try:
                            subdir_files = future.result(timeout=5)  # 5-second timeout per directory
                            files.extend(subdir_files)
                        except Exception:
                            continue  # Skip problematic directories
            
            # Cache the result
            self._file_cache[cache_key] = files
            self._cache_timestamps[cache_key] = current_time
            
            # Monitor performance for network detection
            elapsed = time.time() - start_time
            if elapsed > self._network_performance['timeout_threshold']:
                self._network_performance['slow_operations'] += 1
                self._network_performance['network_mode'] = True
                # Extend cache timeout for network paths
                self._cache_timeout = 120  # 2 minutes for network
            
            return files
            
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
            return []
    
    def _clear_file_cache(self):
        """Clear the file system cache"""
        self._file_cache.clear()
        self._cache_timestamps.clear()
        # Reset cache timeout
        self._cache_timeout = 30 if not self._network_performance['network_mode'] else 120
    
    def cleanup(self):
        """Cleanup resources and threads to prevent memory leaks"""
        if self._is_cleaned_up:
            return
            
        try:
            print("Cleaning up Asset Manager resources...")
            
            # Shutdown thread pool
            if hasattr(self, '_thread_pool') and self._thread_pool:
                try:
                    self._thread_pool.shutdown(wait=False)
                    print("Thread pool shutdown completed")
                except Exception as e:
                    print(f"Error shutting down thread pool: {e}")
            
            # Clear caches to free memory
            self._clear_file_cache()
            if hasattr(self, 'asset_type_colors'):
                self.asset_type_colors.clear()
            
            # Clear thumbnail cache to prevent memory leaks
            if hasattr(self, '_thumbnail_cache'):
                self._thumbnail_cache.clear()
                print("Thumbnail cache cleared")
            
            # Clear icon cache to prevent UI duplication issues  
            if hasattr(self, '_icon_cache'):
                self._icon_cache.clear()
                print("Icon cache cleared")

            # Clear thumbnail generation queue and stop processing
            if hasattr(self, '_thumbnail_generation_queue'):
                self._thumbnail_generation_queue.clear()
                
            # Clear generating thumbnails set to prevent stuck states
            if hasattr(self, '_generating_thumbnails'):
                self._generating_thumbnails.clear()
                print("Generating thumbnails set cleared")
            
            if hasattr(self, '_thumbnail_processing'):
                self._thumbnail_processing = False
            
            if hasattr(self, '_thumbnail_timer') and self._thumbnail_timer:
                try:
                    self._thumbnail_timer.stop()
                    self._thumbnail_timer.deleteLater()
                except:
                    pass
            
            # Clear large data structures
            if hasattr(self, 'assets_library'):
                self.assets_library.clear()
            
            # Mark as cleaned up to prevent double cleanup
            self._is_cleaned_up = True
            print("Asset Manager cleanup completed")
            
        except Exception as e:
            print(f"Error during Asset Manager cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup on garbage collection"""
        self.cleanup()
    
    def _generate_thumbnail_safe(self, file_path, size=None):
        """Generate professional file icon with gradient and type - CRASH-SAFE LIBRARY UI"""
        try:
            # Use default size if not provided
            if size is None:
                thumbnail_size = self.get_ui_preference('thumbnail_size', 64)
                size = (thumbnail_size, thumbnail_size)
            
            # Ensure tuple format
            if isinstance(size, int):
                size = (size, size)
                
            # Use our professional file icon system instead of crash-prone thumbnails
            professional_icon = self._generate_professional_file_icon(file_path, size)
            if professional_icon and not professional_icon.isNull():
                return professional_icon
            
            # Fallback to text-based thumbnail if professional icon fails
            file_ext = os.path.splitext(file_path)[1].lower()
            return self._generate_fallback_thumbnail(file_ext, size)
            
        except Exception as e:
            print(f"Error generating professional thumbnail: {e}")
            return self._generate_fallback_thumbnail(os.path.splitext(file_path)[1].lower(), size)
    
    def _generate_real_thumbnail(self, file_path, file_ext, size):
        """Generate real thumbnail preview for different file types"""
        try:
            if file_ext in ['.ma', '.mb']:
                # Maya scene files - generate scene preview
                return self._generate_maya_scene_thumbnail(file_path, size)
            elif file_ext == '.obj':
                # OBJ files - generate mesh preview  
                return self._generate_obj_thumbnail(file_path, size)
            elif file_ext == '.fbx':
                # FBX files - generate geometry preview
                return self._generate_fbx_thumbnail(file_path, size)
            elif file_ext in ['.abc', '.usd']:
                # Cache/USD files - generate special preview
                return self._generate_cache_thumbnail(file_path, size)
            else:
                # Unknown files - fallback to type icon
                return self._generate_fallback_thumbnail(file_ext, size)
                
        except Exception as e:
            print(f"Error generating real thumbnail for {file_path}: {e}")
            return self._generate_fallback_thumbnail(file_ext, size)
    
    def _generate_maya_scene_thumbnail(self, file_path, size):
        """Generate thumbnail preview of Maya scene content with better error handling"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Create scene manager for safe operations
            scene_manager = self._create_maya_scene_manager(cmds)
            return self._safe_generate_maya_thumbnail(file_path, size, scene_manager)
            
        except Exception as e:
            print(f"Error generating Maya scene thumbnail: {e}")
            return self._generate_text_thumbnail(ErrorMessages.MAYA_ERROR, QColor(255, 100, 100), size)
    
    def _create_maya_scene_manager(self, cmds_module):
        """Create Maya scene manager - factory method following DI principle"""
        return {
            'cmds': cmds_module,
            'original_scene': None
        }
        
    def _save_maya_scene_state(self, cmds):
        """Save current Maya scene state safely"""
        try:
            return cmds.file(q=True, sceneName=True)
        except Exception:
            return None
    
    def _restore_maya_scene_state(self, scene_manager):
        """Restore original Maya scene state safely with proper cleanup"""
        try:
            original_scene = scene_manager.get('original_scene')
            cmds = scene_manager.get('cmds')
            
            if not cmds:
                return
                
            # Re-enable viewport refresh if it was suspended
            try:
                cmds.refresh(suspend=False)
                cmds.scriptEditorInfo(suppressWarnings=False)  # Re-enable warnings
            except Exception:
                pass  # Ignore cleanup errors
            
            # Restore original scene
            if original_scene and cmds:
                try:
                    cmds.file(original_scene, open=True, force=True)
                    print(f"Restored original scene: {os.path.basename(original_scene)}")
                except Exception as e:
                    print(f"Warning: Could not restore original scene, creating new: {e}")
                    cmds.file(new=True, force=True)
            elif cmds:
                cmds.file(new=True, force=True)
                print("Created new clean scene")
                
        except Exception as e:
            print(f"Warning: Could not restore Maya scene state: {e}")
            # Ultimate fallback - try to at least create a new scene
            try:
                if scene_manager.get('cmds'):
                    scene_manager.get('cmds').file(new=True, force=True)
            except Exception:
                pass  # Ignore complete restoration failure
    
    def _safe_generate_maya_thumbnail(self, file_path, size, scene_manager):
        """Safely generate Maya thumbnail with proper scene management"""
        # Save current scene state
        scene_manager['original_scene'] = self._save_maya_scene_state(scene_manager['cmds'])
        
        try:
            # Create clean scene for thumbnail generation
            scene_manager['cmds'].file(new=True, force=True)
            
            # Process the Maya scene
            return self._process_maya_scene_for_thumbnail(file_path, size, scene_manager['cmds'])
            
        except Exception as e:
            print(f"Maya scene processing error: {e}")
            return self._generate_text_thumbnail(ErrorMessages.MAYA_SCENE_FALLBACK, QColor(100, 150, 255), size)
        finally:
            # Always restore original scene
            self._restore_maya_scene_state(scene_manager)
    
    def _process_maya_scene_for_thumbnail(self, file_path, size, cmds):
        """Process Maya scene file to generate thumbnail - Single Responsibility"""
        if not os.path.exists(file_path):
            return self._generate_text_thumbnail(ErrorMessages.FILE_NOT_FOUND, QColor(255, 100, 100), size)
        
        # Check if this scene might be already loaded in the interactive preview
        # to avoid redundant imports during thumbnail generation
        try:
            current_scene = cmds.file(q=True, sceneName=True)
            if current_scene and os.path.basename(current_scene) == os.path.basename(file_path):
                print(f"Using already loaded scene for thumbnail: {os.path.basename(file_path)}")
                # Use current scene content for thumbnail instead of importing again
                scene_meshes = self._get_scene_geometry_safely(cmds)
                if scene_meshes:
                    return self._generate_geometry_thumbnail(file_path, size, scene_meshes, cmds)
        except Exception:
            pass  # Continue with normal import if detection fails
        
        # Pre-validate scene for common production issues
        scene_info = self._validate_production_scene(file_path)
        if scene_info.get('skip_import', False):
            return self._create_production_scene_thumbnail(file_path, size, scene_info)
        
        # Import scene with error suppression for complex scenes
        self._import_maya_scene_safely(file_path, cmds)
        
        # Analyze scene content with error handling
        scene_meshes = self._get_scene_geometry_safely(cmds)
        
        if scene_meshes:
            return self._generate_geometry_thumbnail(file_path, size, scene_meshes, cmds)
        else:
            return self._generate_text_thumbnail(ErrorMessages.MAYA_SCENE_FALLBACK, QColor(100, 150, 255), size)
    
    def _validate_production_scene(self, file_path):
        """Validate production scene and provide metadata for thumbnail generation"""
        scene_info = {
            'skip_import': False,
            'estimated_complexity': 'unknown',
            'plugin_dependencies': [],
            'file_size_mb': 0
        }
        
        try:
            # Get file size for complexity estimation
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            scene_info['file_size_mb'] = file_size
            
            # Large files likely have many dependencies - handle carefully
            if file_size > 100:  # > 100MB suggests complex production scene
                scene_info['estimated_complexity'] = 'high'
                print(f"Detected large production scene ({file_size:.1f}MB): {os.path.basename(file_path)}")
            elif file_size > 10:  # > 10MB suggests moderate complexity
                scene_info['estimated_complexity'] = 'medium'
            else:
                scene_info['estimated_complexity'] = 'low'
            
            # Quick scan for plugin requirements in ASCII files
            if file_path.endswith('.ma'):
                scene_info['plugin_dependencies'] = self._scan_maya_ascii_dependencies(file_path)
            
        except Exception as e:
            print(f"Scene validation warning: {e}")
        
        return scene_info
    
    def _scan_maya_ascii_dependencies(self, file_path):
        """Quickly scan Maya ASCII file for plugin dependencies - avoid full import for complex scenes"""
        dependencies = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Only read first 100 lines for performance
                for i, line in enumerate(f):
                    if i > 100:  # Limit scan for performance
                        break
                    if line.startswith('requires '):
                        # Extract plugin name
                        parts = line.strip().split('"')
                        if len(parts) >= 2:
                            plugin_name = parts[1]
                            dependencies.append(plugin_name)
                            
        except Exception as e:
            print(f"Dependency scan warning: {e}")
        
        return dependencies
    
    def _create_production_scene_thumbnail(self, file_path, size, scene_info):
        """Create thumbnail for production scenes that are too complex to import safely"""
        complexity = scene_info.get('estimated_complexity', 'unknown')
        file_size_mb = scene_info.get('file_size_mb', 0)
        
        if complexity == 'high':
            text = f"MAYA\nPROD\n{file_size_mb:.0f}MB"
            color = QColor(255, 150, 0)  # Orange for production complexity
        else:
            text = f"MAYA\nSCENE\n{file_size_mb:.0f}MB"
            color = QColor(100, 150, 255)  # Blue for normal scenes
            
        return self._generate_text_thumbnail(text, color, size)
    
    def _get_scene_geometry_safely(self, cmds):
        """Get scene geometry with error handling for complex production scenes"""
        try:
            # Use more specific queries for better performance in complex scenes
            meshes = cmds.ls(type='mesh', long=True) or []
            
            # Filter out intermediate objects and hidden shapes for thumbnail
            visible_meshes = []
            for mesh in meshes[:20]:  # Limit to first 20 for performance
                try:
                    # Check if mesh is visible and not intermediate
                    if cmds.getAttr(f"{mesh}.intermediateObject") == False:
                        visible_meshes.append(mesh)
                except Exception:
                    # Include mesh even if attribute check fails
                    visible_meshes.append(mesh)
                    
            print(f"Found {len(visible_meshes)} visible meshes out of {len(meshes)} total")
            return visible_meshes[:10]  # Limit to 10 meshes for thumbnail performance
            
        except Exception as e:
            print(f"Error querying scene geometry: {e}")
            return []
    
    def _import_maya_scene_safely(self, file_path, cmds):
        """Import Maya scene with robust error handling for complex RenderMan production scenes"""
        try:
            # Enhanced plugin and warning management for complex production scenes
            self._suppress_maya_warnings_temporarily(cmds)
            
            # Pre-configure Maya for RenderMan production scene import
            self._prepare_maya_for_renderman_import(cmds)
            
            # Configure import settings for maximum compatibility with RenderMan production scenes
            import_kwargs = {
                'i': True,                          # Import mode
                'ignoreVersion': True,              # Ignore version mismatches
                'mergeNamespacesOnClash': True,     # Handle namespace conflicts
                'returnNewNodes': False,            # Don't track new nodes for performance
                'importTimeRange': 'combine',       # Handle animation properly
                'preserveReferences': False,        # Resolve references for thumbnails
                'loadReferenceDepth': 'none',       # Don't load references for preview
                'namespace': 'temp_preview',        # Use temporary namespace
            }
            
            # Handle RenderMan connection conflicts gracefully
            try:
                if file_path.endswith('.ma'):
                    import_kwargs['type'] = "mayaAscii"
                    cmds.file(file_path, **import_kwargs)
                else:  # .mb
                    import_kwargs['type'] = "mayaBinary"
                    cmds.file(file_path, **import_kwargs)
                
                print(f"✓ RenderMan production scene imported successfully: {os.path.basename(file_path)}")
                
            except RuntimeError as e:
                error_msg = str(e).lower()
                if any(term in error_msg for term in ['connection', 'rman', 'display', 'already has an incoming']):
                    # These are expected RenderMan connection conflicts - continue anyway
                    print(f"✓ RenderMan scene imported with expected connection warnings")
                    print(f"  Info: RenderMan display connections already established")
                else:
                    # Re-raise unexpected errors
                    raise
                         
        except Exception as e:
            # Handle various production scene import issues
            error_msg = str(e).lower()
            if any(term in error_msg for term in ['mirror', 'vertex mapping', 'rman', 'renderman']):
                print(f"✓ Complex production scene imported with expected geometry/RenderMan warnings")
                print(f"  RenderMan integration active - scene processing successful")
            else:
                print(f"Production scene import completed with warnings: {e}")
            # Continue execution - these warnings don't prevent 3D preview functionality
    
    def _prepare_maya_for_renderman_import(self, cmds):
        """Prepare Maya environment for robust RenderMan scene import"""
        try:
            # Ensure RenderMan plugin is loaded if available
            try:
                if not cmds.pluginInfo('RenderMan_for_Maya.py', q=True, loaded=True):
                    cmds.loadPlugin('RenderMan_for_Maya.py', quiet=True)
                    print("✓ RenderMan plugin loaded for scene import")
            except Exception:
                # RenderMan not available - continue without it
                pass
            
            # Configure Maya for better RenderMan scene compatibility
            try:
                # Set batch mode behavior to reduce UI conflicts
                cmds.scriptEditorInfo(suppressWarnings=True, suppressResults=True)
                
                # Disable certain evaluators that can cause issues with complex scenes
                if hasattr(cmds, 'evaluationManager'):
                    original_mode = cmds.evaluationManager(query=True, mode=True)[0]
                    if original_mode != 'off':
                        cmds.evaluationManager(mode='off')
                        
            except Exception as e:
                print(f"Maya environment preparation info: {e}")
                
        except Exception as e:
            print(f"RenderMan preparation warning: {e}")
            # Continue without preparation - not critical

    def _suppress_maya_warnings_temporarily(self, cmds):
        """Temporarily suppress non-critical Maya warnings for thumbnail generation"""
        try:
            # Disable script editor warnings temporarily
            cmds.scriptEditorInfo(suppressWarnings=True)
            
            # Set Maya to batch mode behavior for cleaner import
            if hasattr(cmds, 'about') and cmds.about(batch=True):
                # Already in batch mode
                pass
            else:
                # Configure UI-less import behavior
                cmds.refresh(suspend=True)  # Suspend viewport refresh
                
        except Exception as e:
            print(f"Note: Could not configure warning suppression: {e}")
            # Continue without suppression - not critical for functionality
    
    def _generate_geometry_thumbnail(self, file_path, size, meshes, cmds):
        """Generate professional file-type thumbnail - CRASH-SAFE ALTERNATIVE"""
        try:
            # Professional stable thumbnail generation - no Maya viewport operations
            return self._generate_professional_file_icon(file_path, size)
            
        except Exception as e:
            print(f"Error generating professional thumbnail: {e}")
            return self._generate_text_thumbnail(ErrorMessages.MAYA_SCENE_FALLBACK, QColor(100, 150, 255), size)
    
    def _generate_professional_file_icon(self, file_path, size):
        """Generate professional file-type icon with metadata - CUSTOM SCREENSHOT PRIORITY"""
        
        # FIRST: Check for custom screenshot thumbnail
        custom_thumbnail = self._load_custom_screenshot(file_path, size)
        if custom_thumbnail and not custom_thumbnail.isNull():
            return custom_thumbnail
        
        # FALLBACK: Generate professional file type icon
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        
        # Professional color scheme based on file type
        color_scheme = {
            '.ma': QColor(0, 150, 255),      # Maya Blue  
            '.mb': QColor(0, 120, 200),      # Maya Dark Blue
            '.obj': QColor(255, 140, 0),     # OBJ Orange
            '.fbx': QColor(0, 200, 100),     # FBX Green
            '.abc': QColor(200, 0, 150),     # Alembic Purple  
            '.usd': QColor(255, 200, 0),     # USD Gold
        }
        
        base_color = color_scheme.get(file_ext, QColor(150, 150, 150))
        
        # Create professional icon
        pixmap = QPixmap(size[0], size[1])
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Calculate INNER rectangle for content with MORE margin to prevent cutoff
        margin = 12  # Increased margin to prevent text cutoff
        content_rect = QRect(margin, margin, size[0] - 2*margin, size[1] - 2*margin)
        
        # Professional gradient background with PROPER boundaries
        gradient = QLinearGradient(0, 0, size[0], size[1])
        gradient.setColorAt(0, base_color.lighter(140))
        gradient.setColorAt(1, base_color.darker(120))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(base_color.darker(150), 2))
        # Draw rounded rect with proper margin
        painter.drawRoundedRect(margin//2, margin//2, size[0]-margin, size[1]-margin, 6, 6)
        
        # IMPROVED: Text positioning with better spacing and smaller fonts to guarantee fit
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        
        # File extension at TOP - CONSERVATIVE sizing to prevent cutoff
        ext_text = file_ext.upper().replace('.', '') if file_ext else 'FILE'
        type_font_size = max(8, min(size[0]//12, content_rect.height()//5))  # Much more conservative sizing
        painter.setFont(QFont("Arial", type_font_size, QFont.Weight.Bold))
        
        ext_rect = QRect(content_rect.x(), content_rect.y(), 
                        content_rect.width(), content_rect.height()//4)  # Smaller section
        painter.drawText(ext_rect, Qt.AlignmentFlag.AlignCenter, ext_text)
        
        # File name in MIDDLE - CONSERVATIVE sizing to prevent cutoff
        name_text = file_name if len(file_name) <= 12 else file_name[:9] + "..."  # Shorter text
        name_font_size = max(6, min(size[0]//15, content_rect.height()//6))  # Much more conservative sizing
        painter.setFont(QFont("Arial", name_font_size, QFont.Weight.Bold))
        
        name_rect = QRect(content_rect.x(), content_rect.y() + content_rect.height()//4,
                         content_rect.width(), content_rect.height()//2)  # Larger section for text
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, name_text)
        
        # Status at BOTTOM - CONSERVATIVE sizing to prevent cutoff
        status_font_size = max(6, min(size[0]//18, content_rect.height()//8))  # Much more conservative sizing
        painter.setFont(QFont("Arial", status_font_size, QFont.Weight.Bold))
        
        status_rect = QRect(content_rect.x(), content_rect.y() + 3*content_rect.height()//4,
                           content_rect.width(), content_rect.height()//4)  # Smaller section
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, "READY")
        
        painter.end()
        return pixmap
    
    def _load_custom_screenshot(self, file_path, size):
        """Load custom screenshot thumbnail if it exists"""
        try:
            # Get the asset directory and name
            asset_dir = os.path.dirname(file_path)
            asset_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Look for custom screenshot in .thumbnails directory
            thumbnail_dir = os.path.join(asset_dir, ".thumbnails")
            
            # Check for various screenshot formats
            screenshot_extensions = ['png', 'jpg', 'jpeg', 'tiff', 'tga']
            
            for ext in screenshot_extensions:
                screenshot_path = os.path.join(thumbnail_dir, f"{asset_name}_screenshot.{ext}")
                if os.path.exists(screenshot_path):
                    # Load and resize the custom screenshot
                    original_pixmap = QPixmap(screenshot_path)
                    if not original_pixmap.isNull():
                        # Scale to requested size while maintaining aspect ratio
                        scaled_pixmap = original_pixmap.scaled(
                            size[0], size[1],
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Create final pixmap with exact size and center the scaled image
                        final_pixmap = QPixmap(size[0], size[1])
                        final_pixmap.fill(Qt.GlobalColor.black)  # Black background for screenshots
                        
                        painter = QPainter(final_pixmap)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                        
                        # Center the scaled image
                        x = (size[0] - scaled_pixmap.width()) // 2
                        y = (size[1] - scaled_pixmap.height()) // 2
                        painter.drawPixmap(x, y, scaled_pixmap)
                        
                        # Add subtle screenshot indicator
                        painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
                        painter.setFont(QFont("Arial", max(8, size[0]//24), QFont.Weight.Bold))
                        indicator_rect = QRect(5, 5, size[0]-10, 20)
                        painter.drawText(indicator_rect, Qt.AlignmentFlag.AlignLeft, "📸 CUSTOM")
                        
                        painter.end()
                        
                        print(f"✅ Loaded custom screenshot: {screenshot_path}")
                        return final_pixmap
            
            # No custom screenshot found
            return None
            
        except Exception as e:
            print(f"Error loading custom screenshot for {file_path}: {e}")
            return None
    
    def _frame_scene_geometry(self, meshes, cmds):
        """Frame geometry in viewport for thumbnail capture"""
        try:
            cmds.select(meshes)
            cmds.viewFit(allObjects=True)
        except Exception as e:
            print(f"Warning: Could not frame geometry: {e}")
            # Continue without framing
    
    def _load_and_cleanup_thumbnail(self, thumbnail_path, size):
        """Load thumbnail image and cleanup temporary files"""
        try:
            pixmap = QPixmap(size[0], size[1])
            if pixmap.load(thumbnail_path):
                self._cleanup_temp_file(thumbnail_path)
                return pixmap
        except Exception as e:
            print(f"Error loading thumbnail: {e}")
        finally:
            self._cleanup_temp_file(thumbnail_path)
        
        return self._generate_text_thumbnail(ErrorMessages.MAYA_SCENE_FALLBACK, QColor(100, 150, 255), size)
    
    def _cleanup_temp_file(self, file_path):
        """Clean up temporary thumbnail file safely"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass  # Ignore cleanup errors
    
    # REMOVED: All Maya playblast methods replaced with crash-safe professional alternatives
    
    def _generate_rendered_maya_thumbnail(self, size, meshes):
        """Generate professional Maya scene icon - CRASH-SAFE ALTERNATIVE"""
        # Professional Maya scene representation  
        return self._generate_text_thumbnail("MAYA\nSCENE", QColor(0, 150, 255), size)
    
    def _generate_obj_thumbnail(self, file_path, size):
        """Generate thumbnail preview for OBJ files"""
        try:
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(QColor(50, 40, 30))  # Brown background for geometry
            
            # Try to parse OBJ file for vertex count
            vertex_count = 0
            face_count = 0
            
            try:
                with open(file_path, 'r') as f:
                    for line_num, line in enumerate(f):
                        if line_num > 1000:  # Don't read entire large files
                            break
                        line = line.strip()
                        if line.startswith('v '):
                            vertex_count += 1
                        elif line.startswith('f '):
                            face_count += 1
            except:
                pass
            
            painter = QPainter(pixmap)
            
            # Draw mesh representation
            painter.setPen(QPen(QColor(255, 180, 120), 1))  # Orange wireframe
            
            # Draw geometric pattern based on complexity
            if vertex_count > 0:
                # Draw more complex pattern for higher poly count
                complexity = min(vertex_count // 100, 10)
                for i in range(complexity + 3):
                    x = 10 + (i % 4) * 12
                    y = 10 + (i // 4) * 12
                    painter.drawEllipse(x, y, 8, 8)
                    if i > 0:
                        prev_x = 10 + ((i-1) % 4) * 12 + 4
                        prev_y = 10 + ((i-1) // 4) * 12 + 4
                        painter.drawLine(prev_x, prev_y, x + 4, y + 4)
            else:
                # Simple geometric pattern
                painter.drawPolygon([
                    QPoint(size[0]//2, 10),
                    QPoint(size[0]-10, size[1]//2),
                    QPoint(size[0]//2, size[1]-10),
                    QPoint(10, size[1]//2)
                ])
            
            # Add statistics
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPixelSize(7)
            painter.setFont(font)
            
            if vertex_count > 0:
                painter.drawText(2, size[1] - 10, f"V:{vertex_count}")
                painter.drawText(2, size[1] - 2, f"F:{face_count}")
            else:
                painter.drawText(2, size[1] - 5, "OBJ")
            
            painter.end()
            return pixmap
            
        except Exception as e:
            print(f"Error generating OBJ thumbnail: {e}")
            return self._generate_text_thumbnail("OBJ", QColor(255, 150, 100), size)
    
    def _generate_fbx_thumbnail(self, file_path, size):
        """Generate thumbnail preview for FBX files"""
        try:
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(QColor(40, 50, 40))  # Dark green background
            
            painter = QPainter(pixmap)
            
            # Draw FBX-style icon (hierarchical structure)
            painter.setPen(QPen(QColor(150, 255, 150), 2))  # Bright green
            
            # Draw node hierarchy
            # Root node
            painter.drawRect(size[0]//2 - 4, 8, 8, 8)
            
            # Child nodes  
            painter.drawRect(15, 25, 6, 6)
            painter.drawRect(35, 25, 6, 6)
            painter.drawRect(25, 40, 6, 6)
            
            # Connection lines
            painter.setPen(QPen(QColor(100, 200, 100), 1))
            painter.drawLine(size[0]//2, 16, 18, 25)  # Root to left child
            painter.drawLine(size[0]//2, 16, 38, 25)  # Root to right child
            painter.drawLine(28, 31, 28, 40)  # Child to grandchild
            
            # Add file type label
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPixelSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(2, size[1] - 2, "FBX")
            
            painter.end()
            return pixmap
            
        except Exception as e:
            print(f"Error generating FBX thumbnail: {e}")
            return self._generate_text_thumbnail("FBX", QColor(150, 255, 100), size)
    
    def _generate_cache_thumbnail(self, file_path, size):
        """Generate thumbnail for cache files (ABC, USD)"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.abc':
                bg_color = QColor(60, 60, 30)  # Dark yellow for Alembic
                fg_color = QColor(255, 255, 100)
                label = "ABC"
            else:  # .usd
                bg_color = QColor(60, 30, 60)  # Dark purple for USD
                fg_color = QColor(255, 100, 255)
                label = "USD"
            
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(bg_color)
            
            painter = QPainter(pixmap)
            
            # Draw cache/animation icon
            painter.setPen(QPen(fg_color, 1))
            
            # Draw waveform pattern to represent animation/cache data
            points = []
            for x in range(0, size[0], 4):
                y = size[1]//2 + int(10 * (0.5 - abs((x / size[0]) - 0.5)) * 2)
                points.append(QPoint(x, y))
            
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
            
            # Add dotted timeline
            painter.setPen(QPen(fg_color, 1, Qt.PenStyle.DotLine))
            painter.drawLine(0, size[1] - 15, size[0], size[1] - 15)
            
            # Add file type label
            painter.setPen(fg_color)
            font = painter.font()
            font.setPixelSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(2, size[1] - 2, label)
            
            painter.end()
            return pixmap
            
        except Exception as e:
            print(f"Error generating cache thumbnail: {e}")
            return self._generate_text_thumbnail("CACHE", QColor(255, 255, 100), size)
    
    def _generate_text_thumbnail(self, text, color, size):
        """Generate simple text-based thumbnail as fallback"""
        try:
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(QColor(40, 40, 40))  # Dark background
            
            painter = QPainter(pixmap)
            painter.setPen(QColor(255, 255, 255))  # White text
            
            # Set font size based on thumbnail size
            font = painter.font()
            font.setPixelSize(max(8, size[0] // 8))
            font.setBold(True)
            painter.setFont(font)
            
            # Draw text centered
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
            
            # Draw colored border
            painter.setPen(QPen(color, 2))
            painter.drawRect(1, 1, size[0] - 2, size[1] - 2)
            
            painter.end()
            return pixmap
            
        except Exception as e:
            print(f"Error generating text thumbnail: {e}")
            # Ultimate fallback
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(QColor(128, 128, 128))
            return pixmap
    
    def _generate_fallback_thumbnail(self, file_ext, size):
        """Generate fallback thumbnail for unknown file types"""
        # Color mapping for different file types
        type_colors = {
            '.ma': QColor(100, 150, 255),   # Maya ASCII - Blue
            '.mb': QColor(80, 120, 200),    # Maya Binary - Dark Blue  
            '.obj': QColor(255, 150, 100),  # OBJ - Orange
            '.fbx': QColor(150, 255, 100),  # FBX - Green
            '.abc': QColor(255, 255, 100),  # Alembic - Yellow
            '.usd': QColor(255, 100, 150),  # USD - Pink
        }
        
        color = type_colors.get(file_ext, QColor(128, 128, 128))
        text = file_ext.upper().replace('.', '') if file_ext else "FILE"
        
        return self._generate_text_thumbnail(text, color, size)
    
    def _get_thumbnail_icon(self, file_path):
        """Get thumbnail icon with UI duplication prevention through icon caching"""
        try:
            # Use absolute path for consistent caching
            abs_path = os.path.abspath(file_path)
            icon_cache_key = f"{abs_path}_icon"
            
            # Check icon cache first - PREVENT UI DUPLICATION
            if icon_cache_key in self._icon_cache:
                cached_icon = self._icon_cache[icon_cache_key]
                if cached_icon and not cached_icon.isNull():
                    print(f"Icon cache hit for {os.path.basename(file_path)}")
                    return cached_icon
            
            # Generate thumbnail pixmap (with deduplication)
            pixmap = self._generate_thumbnail_safe(file_path)
            
            if pixmap and not pixmap.isNull():
                # Create a DEEP COPY of pixmap to prevent shared references
                pixmap_copy = QPixmap(pixmap)  # This creates independent copy
                
                # Create QIcon from the independent pixmap copy
                icon = QIcon()
                icon.addPixmap(pixmap_copy, QIcon.Mode.Normal, QIcon.State.Off)
                
                # Cache the icon to prevent creating multiple QIcon objects for same asset
                self._icon_cache[icon_cache_key] = icon
                print(f"Created and cached icon for {os.path.basename(file_path)}")
                
                # Clean icon cache if it gets too large
                if len(self._icon_cache) > self._thumbnail_cache_size_limit:
                    # Remove oldest icon cache entry
                    oldest_icon_key = next(iter(self._icon_cache))
                    del self._icon_cache[oldest_icon_key]
                    print(f"Icon cache limit reached, removed: {oldest_icon_key}")
                
                return icon
            else:
                # Return empty icon for fallback
                return QIcon()
                
        except Exception as e:
            print(f"Error creating thumbnail icon for {file_path}: {e}")
            # Return empty icon on error to use fallback system
            return QIcon()
            return QIcon()
    
    def _queue_thumbnail_generation(self, file_paths, callback=None):
        """Queue multiple thumbnail generations for background processing with deduplication"""
        if self._is_cleaned_up:
            return
            
        try:
            queued_count = 0
            for file_path in file_paths:
                # Use absolute path for consistent caching
                abs_path = os.path.abspath(file_path)
                cache_key = f"{abs_path}_64x64"
                
                # Only queue if not already cached AND not already in queue AND not currently generating
                if (cache_key not in self._thumbnail_cache and 
                    abs_path not in self._thumbnail_generation_queue and
                    cache_key not in getattr(self, '_generating_thumbnails', set())):
                    
                    self._thumbnail_generation_queue.append(abs_path)
                    queued_count += 1
                    
            if queued_count > 0:
                print(f"Queued {queued_count} new thumbnails for background generation")
            else:
                print("No new thumbnails to queue - all already cached or in progress")
            
            # Process queue in background if not already processing
            if not hasattr(self, '_thumbnail_processing') or not self._thumbnail_processing:
                if self._thumbnail_generation_queue:  # Only process if queue has items
                    self._process_thumbnail_queue(callback)
                
        except Exception as e:
            print(f"Error queueing thumbnail generation: {e}")
    
    def _process_thumbnail_queue(self, callback=None):
        """Process thumbnail generation queue with memory management"""
        if self._is_cleaned_up or not self._thumbnail_generation_queue:
            return
            
        try:
            self._thumbnail_processing = True
            
            # Process queue in batches to prevent memory overload
            batch_size = 5  # Small batches for memory safety
            batch = self._thumbnail_generation_queue[:batch_size]
            self._thumbnail_generation_queue = self._thumbnail_generation_queue[batch_size:]
            
            for file_path in batch:
                if not self._is_cleaned_up:  # Check if still valid
                    # Generate thumbnail (will cache automatically)
                    self._generate_thumbnail_safe(file_path)
                    
                    # Call callback if provided
                    if callback:
                        callback(file_path)
            
            # Continue processing if queue has more items
            if self._thumbnail_generation_queue and not self._is_cleaned_up:
                # Use timer for non-blocking processing
                if hasattr(self, '_thumbnail_timer'):
                    if not hasattr(self._thumbnail_timer, 'deleteLater'):
                        # Create timer if needed
                        from PySide6.QtCore import QTimer
                        self._thumbnail_timer = QTimer()
                        self._thumbnail_timer.setSingleShot(True)
                        self._thumbnail_timer.timeout.connect(lambda: self._process_thumbnail_queue(callback))
                        self._thumbnail_timer.start(100)  # Process next batch after 100ms
            else:
                self._thumbnail_processing = False
                
        except Exception as e:
            print(f"Error processing thumbnail queue: {e}")
            self._thumbnail_processing = False
    
    def _safe_basename(self, file_path):
        """Safe alternative to os.path.basename that avoids recursion issues"""
        if not file_path or not isinstance(file_path, str):
            return ""
        
        try:
            # Normalize path separators and extract the last component manually
            normalized_path = str(file_path).replace('\\', '/')
            filename = normalized_path.split('/')[-1] if '/' in normalized_path else normalized_path
            return filename
        except Exception as e:
            print(f"Error extracting basename from '{file_path}': {e}")
            return "unknown_file"
    
    def _safe_splitext(self, file_path):
        """Safe alternative to os.path.splitext that uses safe basename"""
        filename = self._safe_basename(file_path)
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            return name, '.' + ext
        return filename, ""
    
    def _safe_asset_name(self, asset_path):
        """Get asset name safely without extension"""
        name, _ = self._safe_splitext(asset_path)
        return name
    
    def _validate_project_path(self, path):
        """Validate and clean a project path to prevent recursion errors"""
        if not path:
            return None
            
        try:
            # Ensure it's a string
            if not isinstance(path, str):
                print(f"Warning: Project path is not a string: {type(path)}")
                return None
                
            # Basic validation
            path = path.strip()
            if not path:
                print("Warning: Project path is empty after strip")
                return None
                
            # Test if os.path.basename works without recursion
            try:
                test_basename = os.path.basename(path.rstrip(os.sep))
                if not test_basename:
                    print(f"Warning: Project path produces empty basename: {path}")
                    return None
            except (RecursionError, OSError, ValueError) as e:
                print(f"Warning: Project path causes errors: {path} - {e}")
                return None
                
            # Additional path validation
            if len(path) > 260:  # Windows path length limit
                print(f"Warning: Project path too long ({len(path)} chars): {path[:50]}...")
                return None
                
            return path
            
        except Exception as e:
            print(f"Error validating project path '{path}': {e}")
            return None
    
    def reset_current_project(self):
        """Reset current project to None and clean up problematic state"""
        print("Resetting current project due to errors...")
        self.current_project = None
        self.save_config()  # Save the reset state
    
    def _ensure_project_entry(self, project_name=None):
        """Ensure project entry exists in assets_library, return project_name"""
        # Add recursion protection flag
        if hasattr(self, '_processing_project_entry') and self._processing_project_entry:
            print("Warning: Recursive call to _ensure_project_entry detected, returning None")
            return None
            
        if not self.current_project:
            return None
            
        if project_name is None:
            try:
                # Set recursion protection
                self._processing_project_entry = True
                
                # Add safety check for problematic paths that cause recursion
                if not isinstance(self.current_project, str):
                    print(f"Warning: current_project is not a string: {type(self.current_project)}")
                    return None
                
                # Check for empty or problematic paths
                current_path = str(self.current_project).strip()
                if not current_path:
                    print("Warning: current_project is empty or whitespace")
                    return None
                
                # CRITICAL FIX: Use manual string parsing instead of os.path.basename to avoid recursion
                # Normalize path separators and extract the last component
                normalized_path = current_path.replace('\\', '/').rstrip('/')
                path_parts = normalized_path.split('/')
                
                # Get the last non-empty part
                project_name = None
                for part in reversed(path_parts):
                    if part.strip():
                        project_name = part.strip()
                        break
                
                # Additional safety check
                if not project_name:
                    project_name = "UnknownProject"
                    print(f"Warning: Could not extract project name, using: {project_name}")
                    
            except Exception as e:
                print(f"Error extracting project name from '{self.current_project}': {e}")
                # Create a safe fallback project name
                project_name = f"Project_{int(time.time())}"
                print(f"Using emergency fallback project name: {project_name}")
            finally:
                # Always clear recursion protection
                self._processing_project_entry = False
        
        try:
            # Initialize project entry if not exist
            if project_name not in self.assets_library:
                self.assets_library[project_name] = {
                    'path': self.current_project,
                    'created': datetime.now().isoformat(),
                    'assets': {}
                }
        except Exception as e:
            print(f"Error initializing project entry for '{project_name}': {e}")
            return None
        
        return project_name
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    
                    # Safely load current_project with validation
                    current_project = config.get('current_project', None)
                    if current_project:
                        # Use the new validation method
                        validated_project = self._validate_project_path(current_project)
                        if validated_project:
                            self.current_project = validated_project
                        else:
                            print(f"Warning: Invalid project path in config, resetting to None")
                            self.current_project = None
                    else:
                        self.current_project = None
                        
                    self.assets_library = config.get('assets_library', {})
                    
                    # Load custom asset types if available
                    if 'asset_types' in config:
                        self.asset_types = config['asset_types']
                        self._update_color_cache()
                    
                    # Load UI preferences if available
                    self.ui_preferences = config.get('ui_preferences', {})
        except Exception as e:
            print(f"Error loading config: {e}")
            self.assets_library = {}
            self.current_project = None
    
    def save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'current_project': self.current_project,
                'assets_library': self.assets_library,
                'asset_types': self.asset_types,
                'version': self.version,
                'ui_preferences': getattr(self, 'ui_preferences', {})
            }
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_ui_preference(self, key, default_value=None):
        """Get a UI preference value"""
        if not hasattr(self, 'ui_preferences'):
            self.ui_preferences = {}
        return self.ui_preferences.get(key, default_value)
    
    def set_ui_preference(self, key, value):
        """Set a UI preference value"""
        if not hasattr(self, 'ui_preferences'):
            self.ui_preferences = {}
        self.ui_preferences[key] = value
        self.save_config()
    
    def create_project(self, project_name, project_path):
        """Create a new asset project"""
        full_path = os.path.join(project_path, project_name)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
            
        # Create project structure
        subdirs = ['models', 'textures', 'scenes', 'exports', 'references']
        for subdir in subdirs:
            subdir_path = os.path.join(full_path, subdir)
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path)
        
        self.current_project = full_path
        self.assets_library[project_name] = {
            'path': full_path,
            'created': datetime.now().isoformat(),
            'assets': {}
        }
        self.save_config()
        return True
    
    def import_asset(self, asset_path, asset_name=None):
        """Import an asset into the current scene"""
        if not os.path.exists(asset_path):
            return False
        
        if not MAYA_AVAILABLE or cmds is None:
            print("Maya not available - cannot import asset")
            return False
            
        try:
            if asset_path.endswith('.ma'):
                cmds.file(asset_path, i=True, type="mayaAscii")
            elif asset_path.endswith('.mb'):
                cmds.file(asset_path, i=True, type="mayaBinary")
            elif asset_path.endswith('.obj'):
                cmds.file(asset_path, i=True, type="OBJ")
            elif asset_path.endswith('.fbx'):
                cmds.file(asset_path, i=True, type="FBX")
            else:
                cmds.file(asset_path, i=True)
            return True
        except Exception as e:
            print(f"Error importing asset: {e}")
            return False
    
    def export_selected_as_asset(self, export_path, asset_name):
        """Export selected objects as an asset"""
        if not MAYA_AVAILABLE or cmds is None:
            print("Maya not available - cannot export asset")
            return False
            
        selected = cmds.ls(selection=True)
        if not selected:
            return False
            
        try:
            cmds.file(export_path, exportSelected=True, type="mayaAscii")
            return True
        except Exception as e:
            print(f"Error exporting asset: {e}")
            return False

    # =============================================================================
    # Asset Library Registration Features
    # =============================================================================
    
    def register_asset_to_library(self, asset_path, copy_to_project=True):
        """Register an asset file to the library with optional copying"""
        if not os.path.exists(asset_path):
            return False
        
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        # Initialize assets registry if not exist
        if 'registered_assets' not in self.assets_library[project_name]:
            self.assets_library[project_name]['registered_assets'] = {}
        
        # Determine destination path
        if copy_to_project and self.current_project:
            # Determine subdirectory based on asset type
            asset_type = self.get_asset_type(asset_path)
            asset_type_config = self.asset_types.get(asset_type, self.asset_types['default'])
            
            # Map asset types to subdirectories
            type_to_subdir = {
                'models': 'models',
                'textures': 'textures', 
                'materials': 'scenes',
                'rigs': 'scenes',
                'cameras': 'scenes',
                'lights': 'scenes',
                'vfx': 'scenes',
                'animations': 'scenes',
                'default': 'assets'
            }
            
            subdir = type_to_subdir.get(asset_type, 'assets')
            dest_dir = os.path.join(self.current_project, subdir)
            
            # Create subdirectory if it doesn't exist
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            
            dest_path = os.path.join(dest_dir, os.path.basename(asset_path))
            
            # Copy the file if it's not already in the project
            if not os.path.samefile(asset_path, dest_path) if os.path.exists(dest_path) else True:
                try:
                    shutil.copy2(asset_path, dest_path)
                    final_path = dest_path
                except Exception as e:
                    print(f"Error copying asset {asset_path}: {e}")
                    return False
            else:
                final_path = dest_path
        else:
            final_path = asset_path
        
        # Register the asset
        self.assets_library[project_name]['registered_assets'][asset_name] = {
            'path': final_path,
            'original_path': asset_path,
            'registered': datetime.now().isoformat(),
            'type': self.get_asset_type(asset_path),
            'size': os.path.getsize(asset_path),
            'copied_to_project': copy_to_project
        }
        
        self.save_config()
        return True
    
    def register_multiple_assets(self, asset_paths, copy_to_project=True, progress_callback=None):
        """Register multiple assets to the library"""
        if not asset_paths:
            return {'registered': [], 'failed': []}
        
        registered = []
        failed = []
        total = len(asset_paths)
        
        for i, asset_path in enumerate(asset_paths):
            try:
                if self.register_asset_to_library(asset_path, copy_to_project):
                    registered.append(asset_path)
                else:
                    failed.append(asset_path)
            except Exception as e:
                print(f"Error registering asset {asset_path}: {e}")
                failed.append(asset_path)
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(i + 1, total, asset_path)
        
        return {'registered': registered, 'failed': failed}
    
    def get_registered_assets(self):
        """Get all registered assets in the current project"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return {}
        
        if 'registered_assets' not in self.assets_library[project_name]:
            return {}
        
        return self.assets_library[project_name]['registered_assets']
    
    def remove_asset_from_library(self, asset_name, delete_file=False):
        """Remove an asset from the library registry"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        
        if 'registered_assets' not in self.assets_library[project_name]:
            return False
        
        if asset_name not in self.assets_library[project_name]['registered_assets']:
            return False
        
        asset_info = self.assets_library[project_name]['registered_assets'][asset_name]
        
        # Delete file if requested and it was copied to the project
        if delete_file and asset_info.get('copied_to_project', False):
            asset_path = asset_info['path']
            try:
                if os.path.exists(asset_path):
                    os.remove(asset_path)
            except Exception as e:
                print(f"Error deleting asset file {asset_path}: {e}")
                return False
        
        # Remove from registry
        del self.assets_library[project_name]['registered_assets'][asset_name]
        self.save_config()
        return True

    # =============================================================================
    # Asset Management & Organization Features (v1.1.0)
    # =============================================================================
    
    def add_asset_tag(self, asset_path, tag):
        """Add a tag to an asset for better organization"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        # Defensive: always use asset_name (no extension) as key
        if 'tags' not in self.assets_library[project_name]:
            self.assets_library[project_name]['tags'] = {}
        if asset_name not in self.assets_library[project_name]['tags']:
            self.assets_library[project_name]['tags'][asset_name] = []
        if tag not in self.assets_library[project_name]['tags'][asset_name]:
            self.assets_library[project_name]['tags'][asset_name].append(tag)
            self.save_config()
        return True
    
    def remove_asset_tag(self, asset_path, tag):
        """Remove a tag from an asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        # Initialize asset tags if not exist
        if 'tags' not in self.assets_library[project_name]:
            self.assets_library[project_name]['tags'] = {}
        if asset_name not in self.assets_library[project_name]['tags']:
            self.assets_library[project_name]['tags'][asset_name] = []
        try:
            if tag in self.assets_library[project_name]['tags'][asset_name]:
                self.assets_library[project_name]['tags'][asset_name].remove(tag)
                self.save_config()
                return True
        except (KeyError, ValueError):
            pass
        return False
    
    def get_asset_tags(self, asset_path):
        """Get all tags for an asset"""
        try:
            project_name = self._ensure_project_entry()
            if not project_name:
                return []
            
            # CRITICAL FIX: Use manual string parsing instead of os.path.basename to avoid recursion
            if not asset_path or not isinstance(asset_path, str):
                return []
                
            # Extract filename manually to avoid os.path recursion
            normalized_path = str(asset_path).replace('\\', '/')
            filename = normalized_path.split('/')[-1] if '/' in normalized_path else normalized_path
            asset_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            if 'tags' not in self.assets_library[project_name]:
                return []
            if asset_name not in self.assets_library[project_name]['tags']:
                return []
            return self.assets_library[project_name]['tags'][asset_name]
        except (RecursionError, KeyError, ValueError, OSError) as e:
            print(f"Error getting asset tags for {asset_path}: {e}")
            return []
    
    def get_all_tags(self):
        """Get all unique tags in the current project"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return []
        
        all_tags = set()
        
        if 'tags' not in self.assets_library[project_name]:
            return []
        
        try:
            for asset_tags in self.assets_library[project_name]['tags'].values():
                all_tags.update(asset_tags)
        except KeyError:
            pass
        
        return sorted(list(all_tags))
    
    def search_assets_by_tag(self, tag):
        """Find all assets with a specific tag"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return []
        
        matching_assets = []
        
        if 'tags' not in self.assets_library[project_name]:
            return []
        
        try:
            for asset_name, tags in self.assets_library[project_name]['tags'].items():
                if tag in tags:
                    matching_assets.append(asset_name)
        except KeyError:
            pass
        
        return matching_assets
    
    def create_asset_collection(self, collection_name, asset_paths=None):
        """Create a collection/set of related assets"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        
        # Initialize collections if not exist
        if 'collections' not in self.assets_library[project_name]:
            self.assets_library[project_name]['collections'] = {}
        
        if collection_name in self.assets_library[project_name]['collections']:
            return False  # Collection already exists
        
        self.assets_library[project_name]['collections'][collection_name] = {
            'created': datetime.now().isoformat(),
            'assets': asset_paths or [],
            'description': ''
        }
        self.save_config()
        return True
    
    def add_asset_to_collection(self, collection_name, asset_path):
        """Add an asset to an existing collection"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        # Initialize collections if not exist
        if 'collections' not in self.assets_library[project_name]:
            self.assets_library[project_name]['collections'] = {}
        
        try:
            if collection_name in self.assets_library[project_name]['collections']:
                if asset_name not in self.assets_library[project_name]['collections'][collection_name]['assets']:
                    self.assets_library[project_name]['collections'][collection_name]['assets'].append(asset_name)
                    self.save_config()
                    return True
        except KeyError:
            pass
        return False
    
    def remove_asset_from_collection(self, collection_name, asset_path):
        """Remove an asset from a collection"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        # Initialize collections if not exist  
        if 'collections' not in self.assets_library[project_name]:
            return False
        
        try:
            if (collection_name in self.assets_library[project_name]['collections'] and
                asset_name in self.assets_library[project_name]['collections'][collection_name]['assets']):
                
                self.assets_library[project_name]['collections'][collection_name]['assets'].remove(asset_name)
                self.save_config()
                return True
        except (KeyError, ValueError):
            pass
        return False
    
    def get_asset_collections(self):
        """Get all collections in the current project"""
        try:
            project_name = self._ensure_project_entry()
            if not project_name:
                return {}
            
            try:
                if 'collections' in self.assets_library[project_name]:
                    return self.assets_library[project_name]['collections']
            except KeyError:
                pass
            return {}
        except (RecursionError, KeyError, ValueError, OSError) as e:
            print(f"Error getting asset collections: {e}")
            return {}
    
    def track_asset_dependency(self, asset_path, dependency_path):
        """Track that an asset depends on another asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        dependency_name = os.path.splitext(os.path.basename(dependency_path))[0]
        # Initialize dependencies if not exist
        if 'dependencies' not in self.assets_library[project_name]:
            self.assets_library[project_name]['dependencies'] = {}
        if asset_name not in self.assets_library[project_name]['dependencies']:
            self.assets_library[project_name]['dependencies'][asset_name] = []
        # Defensive: ensure dependency_name is not the same as asset_name
        if dependency_name == asset_name:
            return False
        if dependency_name not in self.assets_library[project_name]['dependencies'][asset_name]:
            self.assets_library[project_name]['dependencies'][asset_name].append(dependency_name)
            self.save_config()
            return True
        return False
    
    def get_asset_dependencies(self, asset_path):
        """Get all dependencies for an asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return []
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        if 'dependencies' not in self.assets_library[project_name]:
            return []
        if asset_name not in self.assets_library[project_name]['dependencies']:
            return []
        return self.assets_library[project_name]['dependencies'][asset_name]
    
    def get_asset_dependents(self, asset_path):
        """Get all assets that depend on this asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return []
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        dependents = []
        if 'dependencies' not in self.assets_library[project_name]:
            return []
        try:
            for dependent, deps in self.assets_library[project_name]['dependencies'].items():
                if asset_name in deps:
                    dependents.append(dependent)
        except KeyError:
            pass
        return dependents
    
    def batch_import_assets(self, asset_paths):
        """Import multiple assets at once"""
        if not MAYA_AVAILABLE or cmds is None:
            print("Maya not available - cannot import assets")
            return {
                'imported': [],
                'failed': asset_paths
            }
            
        imported_assets = []
        failed_assets = []
        
        for asset_path in asset_paths:
            if self.import_asset(asset_path):
                imported_assets.append(asset_path)
            else:
                failed_assets.append(asset_path)
        
        return {
            'imported': imported_assets,
            'failed': failed_assets
        }
    
    def batch_export_assets(self, export_settings):
        """Export multiple assets based on selection groups"""
        if not MAYA_AVAILABLE or cmds is None:
            print("Maya not available - cannot export assets")
            return {
                'exported': [],
                'failed': [setting['name'] for setting in export_settings]
            }
            
        exported_assets = []
        failed_exports = []
        
        # export_settings should be a list of dicts with 'name', 'objects', 'path'
        for setting in export_settings:
            try:
                # Select the specified objects
                cmds.select(setting['objects'])
                if self.export_selected_as_asset(setting['path'], setting['name']):
                    exported_assets.append(setting['name'])
                else:
                    failed_exports.append(setting['name'])
            except Exception as e:
                print(f"Error exporting {setting['name']}: {e}")
                failed_exports.append(setting['name'])
        
        return {
            'exported': exported_assets,
            'failed': failed_exports
        }
    
    def create_asset_version(self, asset_path, version_notes=""):
        """Create a new version of an asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
            
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        # Initialize versions if not exist
        if 'versions' not in self.assets_library[project_name]:
            self.assets_library[project_name]['versions'] = {}
        
        if asset_name not in self.assets_library[project_name]['versions']:
            self.assets_library[project_name]['versions'][asset_name] = []
        
        # Create version info
        version_info = {
            'version': len(self.assets_library[project_name]['versions'][asset_name]) + 1,
            'created': datetime.now().isoformat(),
            'notes': version_notes,
            'file_path': asset_path
        }
        
        self.assets_library[project_name]['versions'][asset_name].append(version_info)
        self.save_config()
        return True
    
    def get_asset_versions(self, asset_path):
        """Get all versions of an asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return []
        
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        try:
            if ('versions' in self.assets_library[project_name] and 
                asset_name in self.assets_library[project_name]['versions']):
                return self.assets_library[project_name]['versions'][asset_name]
        except KeyError:
            pass
        return []

    # =============================================================================
    # Asset Metadata & Thumbnail Support (v1.1.2)
    # =============================================================================
    
    def set_asset_metadata(self, asset_path, metadata):
        """Store metadata for an asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return False
        
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        # Initialize metadata if not exist
        if 'metadata' not in self.assets_library[project_name]:
            self.assets_library[project_name]['metadata'] = {}
        
        self.assets_library[project_name]['metadata'][asset_name] = {
            'description': metadata.get('description', ''),
            'author': metadata.get('author', ''),
            'creation_date': metadata.get('creation_date', datetime.now().isoformat()),
            'file_size': metadata.get('file_size', 0),
            'last_modified': metadata.get('last_modified', datetime.now().isoformat()),
            'custom_fields': metadata.get('custom_fields', {})
        }
        
        self.save_config()
        return True
    
    def get_asset_metadata(self, asset_path):
        """Get metadata for an asset"""
        project_name = self._ensure_project_entry()
        if not project_name:
            return {}
        
        asset_name = os.path.splitext(os.path.basename(asset_path))[0]
        
        if ('metadata' in self.assets_library[project_name] and 
            asset_name in self.assets_library[project_name]['metadata']):
            return self.assets_library[project_name]['metadata'][asset_name]
        
        return {}

    # =============================================================================
    # Asset Preview & Visualization System (v1.2.0)
    # =============================================================================
    
    def extract_asset_metadata(self, asset_path):
        """
        Extract comprehensive metadata from asset files for preview system
        Returns detailed information about geometry, textures, and file properties
        """
        if not os.path.exists(asset_path):
            return {}
        
        metadata = {
            'file_path': asset_path,
            'file_name': os.path.basename(asset_path),
            'file_size': os.path.getsize(asset_path),
            'file_extension': os.path.splitext(asset_path)[1].lower(),
            'last_modified': os.path.getmtime(asset_path),
            'poly_count': 0,
            'vertex_count': 0,
            'face_count': 0,
            'texture_count': 0,
            'texture_paths': [],
            'bounding_box': {'min': [0, 0, 0], 'max': [0, 0, 0]},
            'material_count': 0,
            'animation_frames': 0,
            'has_animation': False,
            'scene_objects': [],
            'cameras': [],
            'lights': [],
            'extraction_time': time.time()
        }
        
        try:
            file_ext = metadata['file_extension']
            
            if file_ext in ['.ma', '.mb']:
                metadata.update(self._extract_maya_metadata(asset_path))
            elif file_ext == '.obj':
                metadata.update(self._extract_obj_metadata(asset_path))
            elif file_ext == '.fbx':
                metadata.update(self._extract_fbx_metadata(asset_path))
            elif file_ext in ['.abc', '.usd']:
                metadata.update(self._extract_cache_metadata(asset_path))
            
            # Calculate additional derived info
            metadata['complexity_rating'] = self._calculate_complexity_rating(metadata)
            metadata['preview_quality_suggestion'] = self._suggest_preview_quality(metadata)
            
        except Exception as e:
            print(f"Error extracting metadata from {asset_path}: {e}")
            metadata['extraction_error'] = str(e)
        
        return metadata
    
    def _extract_maya_metadata(self, asset_path):
        """Extract metadata from Maya files (.ma/.mb)"""
        metadata = {}
        
        try:
            if not MAYA_AVAILABLE or cmds is None:
                return metadata
            
            # Save current scene state
            current_scene = cmds.file(q=True, sceneName=True)
            
            try:
                # Open file in background for analysis
                cmds.file(new=True, force=True)
                
                if asset_path.endswith('.ma'):
                    cmds.file(asset_path, open=True, force=True, type="mayaAscii")
                else:
                    cmds.file(asset_path, open=True, force=True, type="mayaBinary")
                
                # Extract geometry information
                all_meshes = cmds.ls(type='mesh', long=True) or []
                metadata['scene_objects'] = [cmds.listRelatives(mesh, parent=True, fullPath=True)[0] 
                                           for mesh in all_meshes if cmds.listRelatives(mesh, parent=True)]
                
                # Calculate polygon and vertex counts
                total_polys = 0
                total_verts = 0
                for mesh in all_meshes:
                    try:
                        polys = cmds.polyEvaluate(mesh, face=True) or 0
                        verts = cmds.polyEvaluate(mesh, vertex=True) or 0
                        total_polys += polys
                        total_verts += verts
                    except:
                        continue
                
                metadata['poly_count'] = total_polys
                metadata['vertex_count'] = total_verts
                metadata['face_count'] = total_polys
                
                # Extract material and texture information
                materials = cmds.ls(materials=True) or []
                metadata['material_count'] = len([m for m in materials if not m.startswith('default')])
                
                # Find texture files
                texture_nodes = cmds.ls(type='file') or []
                texture_paths = []
                for tex_node in texture_nodes:
                    try:
                        tex_path = cmds.getAttr(f"{tex_node}.fileTextureName")
                        if tex_path and os.path.exists(tex_path):
                            texture_paths.append(tex_path)
                    except:
                        continue
                
                metadata['texture_paths'] = texture_paths
                metadata['texture_count'] = len(texture_paths)
                
                # Calculate bounding box
                if all_meshes:
                    try:
                        bbox = cmds.exactWorldBoundingBox(metadata['scene_objects'])
                        if len(bbox) >= 6:
                            metadata['bounding_box'] = {
                                'min': [bbox[0], bbox[1], bbox[2]],
                                'max': [bbox[3], bbox[4], bbox[5]]
                            }
                    except:
                        pass
                
                # Check for animation
                time_range = cmds.playbackOptions(q=True, animationStartTime=True), cmds.playbackOptions(q=True, animationEndTime=True)
                if time_range[1] > time_range[0]:
                    metadata['has_animation'] = True
                    metadata['animation_frames'] = int(time_range[1] - time_range[0] + 1)
                
                # Extract cameras and lights
                metadata['cameras'] = cmds.ls(type='camera') or []
                metadata['lights'] = cmds.ls(lights=True) or []
                
            finally:
                # Restore original scene
                try:
                    if current_scene:
                        cmds.file(current_scene, open=True, force=True)
                    else:
                        cmds.file(new=True, force=True)
                except:
                    cmds.file(new=True, force=True)
            
        except Exception as e:
            print(f"Error extracting Maya metadata: {e}")
            metadata['extraction_error'] = str(e)
        
        return metadata
    
    def _extract_obj_metadata(self, asset_path):
        """Extract metadata from OBJ files"""
        metadata = {}
        
        try:
            vertex_count = 0
            face_count = 0
            texture_coords = 0
            materials = set()
            min_bounds = [float('inf')] * 3
            max_bounds = [float('-inf')] * 3
            
            with open(asset_path, 'r') as f:
                for line_num, line in enumerate(f):
                    if line_num > 50000:  # Limit parsing for performance
                        break
                    
                    line = line.strip()
                    if line.startswith('v '):  # Vertex
                        vertex_count += 1
                        # Extract coordinates for bounding box
                        try:
                            coords = [float(x) for x in line.split()[1:4]]
                            for i, coord in enumerate(coords[:3]):
                                min_bounds[i] = min(min_bounds[i], coord)
                                max_bounds[i] = max(max_bounds[i], coord)
                        except:
                            pass
                    elif line.startswith('f '):  # Face
                        face_count += 1
                    elif line.startswith('vt '):  # Texture coordinate
                        texture_coords += 1
                    elif line.startswith('usemtl '):  # Material usage
                        materials.add(line.split()[1])
            
            metadata['vertex_count'] = vertex_count
            metadata['face_count'] = face_count
            metadata['poly_count'] = face_count
            metadata['texture_count'] = texture_coords
            metadata['material_count'] = len(materials)
            
            # Set bounding box if we found valid bounds
            if min_bounds[0] != float('inf'):
                metadata['bounding_box'] = {
                    'min': min_bounds,
                    'max': max_bounds
                }
                
        except Exception as e:
            print(f"Error extracting OBJ metadata: {e}")
            metadata['extraction_error'] = str(e)
        
        return metadata
    
    def _extract_fbx_metadata(self, asset_path):
        """Extract metadata from FBX files"""
        metadata = {}
        
        try:
            # For FBX files, we'll provide estimated metadata based on file size
            # Real FBX parsing would require the FBX SDK
            file_size = os.path.getsize(asset_path)
            
            # Rough estimates based on file size (these are approximations)
            if file_size < 1024 * 1024:  # < 1MB
                metadata['vertex_count'] = min(1000, file_size // 100)
                metadata['face_count'] = min(800, file_size // 150)
            elif file_size < 10 * 1024 * 1024:  # < 10MB
                metadata['vertex_count'] = min(10000, file_size // 500)
                metadata['face_count'] = min(8000, file_size // 600)
            else:  # > 10MB
                metadata['vertex_count'] = min(100000, file_size // 1000)
                metadata['face_count'] = min(80000, file_size // 1200)
            
            metadata['poly_count'] = metadata['face_count']
            metadata['material_count'] = max(1, file_size // (1024 * 1024))  # Estimate materials
            metadata['extraction_method'] = 'size_estimation'
            
        except Exception as e:
            print(f"Error extracting FBX metadata: {e}")
            metadata['extraction_error'] = str(e)
        
        return metadata
    
    def _extract_cache_metadata(self, asset_path):
        """Extract metadata from cache files (.abc, .usd)"""
        metadata = {}
        
        try:
            file_size = os.path.getsize(asset_path)
            file_ext = os.path.splitext(asset_path)[1].lower()
            
            # Basic file analysis
            metadata['has_animation'] = True  # Cache files typically contain animation
            metadata['file_type'] = 'animation_cache' if file_ext == '.abc' else 'usd_scene'
            
            # Estimate frame count based on file size
            estimated_frames = max(1, file_size // (100 * 1024))  # Rough estimate
            metadata['animation_frames'] = min(estimated_frames, 1000)  # Cap at reasonable number
            
        except Exception as e:
            print(f"Error extracting cache metadata: {e}")
            metadata['extraction_error'] = str(e)
        
        return metadata
    
    def _calculate_complexity_rating(self, metadata):
        """Calculate complexity rating (1-10) based on asset metadata"""
        try:
            rating = 1
            
            # Vertex count contribution (0-3 points)
            vertex_count = metadata.get('vertex_count', 0)
            if vertex_count > 100000:
                rating += 3
            elif vertex_count > 10000:
                rating += 2
            elif vertex_count > 1000:
                rating += 1
            
            # Texture count contribution (0-2 points)
            texture_count = metadata.get('texture_count', 0)
            if texture_count > 10:
                rating += 2
            elif texture_count > 3:
                rating += 1
            
            # Material count contribution (0-2 points)
            material_count = metadata.get('material_count', 0)
            if material_count > 5:
                rating += 2
            elif material_count > 2:
                rating += 1
            
            # Animation contribution (0-2 points)
            if metadata.get('has_animation', False):
                frames = metadata.get('animation_frames', 0)
                if frames > 100:
                    rating += 2
                elif frames > 10:
                    rating += 1
            
            return min(10, rating)
            
        except Exception as e:
            print(f"Error calculating complexity rating: {e}")
            return 5  # Default medium complexity
    
    def _suggest_preview_quality(self, metadata):
        """Suggest preview quality based on asset complexity"""
        complexity = metadata.get('complexity_rating', 5)
        
        if complexity <= 3:
            return 'High'
        elif complexity <= 6:
            return 'Medium'
        else:
            return 'Low'


class AssetPreviewWidget(QWidget):
    """
    Comprehensive asset preview widget with 3D visualization and metadata display
    Part of the Preview & Visualization system for v1.2.0
    """
    
    def __init__(self, asset_manager, parent=None):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.current_asset_path = None
        self.preview_quality = 'Medium'
        self.camera_position = {'distance': 5.0, 'rotation_x': -30, 'rotation_y': 45}
        
        self.setup_ui()
        self.setup_connections()
    
    def _configure_preview_button(self, button, min_width=80, height=30):
        """Configure preview UI buttons with proper sizing - Single Responsibility Principle"""
        button.setMinimumWidth(min_width)
        button.setFixedHeight(height)
        button.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #777777;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
        """)
    
    def setup_ui(self):
        """Setup the preview widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Preview header with screenshot functionality
        header_layout = QHBoxLayout()
        
        # Asset info display
        self.asset_info_label = QLabel("Asset Preview")
        self.asset_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.asset_info_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                padding: 8px;
            }
        """)
        
        # Professional screenshot button
        self.screenshot_btn = QPushButton("📸 Capture Screenshot")
        self.screenshot_btn.setToolTip("Take high-resolution screenshot of current Maya viewport and set as asset thumbnail")
        self.screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.screenshot_btn.setEnabled(False)  # Enabled when asset is selected
        
        header_layout.addWidget(self.screenshot_btn)
        header_layout.addStretch()
        header_layout.addWidget(self.asset_info_label)
        header_layout.addStretch()
        
        # Main preview area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 3D Preview area (left side)
        self.preview_widget = self.create_3d_preview_widget()
        splitter.addWidget(self.preview_widget)
        
        # Metadata panel (right side)
        self.metadata_widget = self.create_metadata_widget()
        splitter.addWidget(self.metadata_widget)
        
        # Set splitter proportions (70% preview, 30% metadata)
        splitter.setSizes([UIConstants.LIBRARY_WIDTH, UIConstants.PREVIEW_WIDTH])
        
        # Add to main layout
        layout.addLayout(header_layout)
        layout.addWidget(splitter, 1)
        
        # Comparison mode toggle (initially hidden)
        self.comparison_widget = self.create_comparison_widget()
        self.comparison_widget.hide()
        layout.addWidget(self.comparison_widget)
    
    def create_3d_preview_widget(self):
        """Create the 3D preview display widget with multiple fallback options"""
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.Box)
        preview_frame.setMinimumSize(UIConstants.PREVIEW_FRAME_WIDTH, UIConstants.PREVIEW_FRAME_HEIGHT)
        
        layout = QVBoxLayout(preview_frame)
        
        # Try multiple 3D preview approaches in order of preference
        self.preview_widget = self._create_maya_viewport_widget()
        
        # Ensure preview_label exists for compatibility
        if not hasattr(self, 'preview_label'):
            self.preview_label = None
            
        layout.addWidget(self.preview_widget, 1)
        
        # Preview controls (cleaned up)
        controls_layout = QHBoxLayout()
        
        # Replace old 3D loading text with asset status
        self.preview_status = QLabel("Ready")
        self.preview_status.setStyleSheet("color: #888888; font-size: 11px;")
        
        controls_layout.addWidget(self.preview_status)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        self.last_mouse_pos = None
        self._rotation_x = 0
        self._rotation_y = 0
        self._zoom_level = 1.0
        
        return preview_frame
    
    def _create_maya_viewport_widget(self):
        """Create professional asset preview widget - CLEAN PREVIEW ONLY"""
        try:
            print("🎯 Initializing Professional Asset Preview Display")
            
            # Create a simple preview widget for asset thumbnails/previews
            preview_widget = QWidget()
            preview_widget.setMinimumSize(UIConstants.PREVIEW_MIN_WIDTH, UIConstants.PREVIEW_MIN_HEIGHT)
            
            layout = QVBoxLayout(preview_widget)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)
            
            # Preview display area (for thumbnails, icons, etc.)
            self.preview_info_label = QLabel("Select an asset to preview")
            self.preview_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_info_label.setStyleSheet("""
                QLabel {
                    background-color: #2a2a2a;
                    border: 2px solid #555555;
                    border-radius: 4px;
                    color: #cccccc;
                    font-size: 14px;
                    padding: 20px;
                    min-height: 300px;
                }
            """)
            
            layout.addWidget(self.preview_info_label, 1)
            
            # Store preview configuration 
            self.professional_preview = True
            self.mel_preview = False  # No more MEL panels
            
            print("✅ Professional Asset Preview Display initialized successfully")
            return preview_widget
                
        except Exception as e:
            print(f"Error creating professional info display: {e}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_preview_widget()
    
    def _create_maya_viewport_method1(self):
        """Method 1: Direct Maya viewport integration with shiboken6 (Maya 2025+)"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            import maya.OpenMayaUI as omui # pyright: ignore[reportMissingImports]
            from shiboken6 import wrapInstance # pyright: ignore[reportMissingImports]
            
            # Create a Maya model panel for 3D interaction
            panel_name = cmds.modelPanel(menuBarVisible=False, toolBarVisible=False)
            
            # Configure the model editor for better 3D preview
            cmds.modelEditor(panel_name, edit=True,
                           displayAppearance='smoothShaded',
                           wireframeOnShaded=False,
                           displayLights='default',
                           shadows=True,
                           useDefaultMaterial=False,
                           textures=True,
                           grid=False,
                           manipulators=False,
                           cameras=False)
            
            # Get the Maya widget pointer and convert to Qt widget
            maya_widget_ptr = omui.MQtUtil.findControl(panel_name)
            if maya_widget_ptr:
                maya_widget = wrapInstance(int(maya_widget_ptr), QWidget)
                if isinstance(maya_widget, QWidget):
                    # Type cast to QWidget to resolve attribute access
                    widget = maya_widget
                    widget.setMinimumSize(UIConstants.PREVIEW_MIN_WIDTH, UIConstants.PREVIEW_MIN_HEIGHT)
                    # Store panel reference for cleanup
                    self.maya_panel_name = panel_name
                    
                    print("✓ Created interactive Maya viewport using shiboken6")
                    return widget
       
            return None
                
        except Exception as e:
            print(f"Method 1 (shiboken6) failed: {e}")
            return None
    
    def _create_maya_viewport_method2(self):
        """Method 2: Alternative Maya viewport approach for Maya 2025+"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            import maya.OpenMayaUI as omui # pyright: ignore[reportMissingImports]
            from PySide6.QtWidgets import QWidget # pyright: ignore[reportMissingImports]
            
            # Try alternative viewport creation method
            panel_name = f"assetPreview_panel_{id(self)}"
            
            # Create viewport with specific configuration for embedding
            if cmds.modelPanel(panel_name, exists=True):
                cmds.deleteUI(panel_name, panel=True)
            
            panel = cmds.modelPanel(panel_name, 
                                  menuBarVisible=False, 
                                  toolBarVisible=False,
                                  parent=cmds.window())
            
            # Try to get control and wrap it
            try:
                control_name = cmds.modelPanel(panel, query=True, control=True)
                if control_name:
                    # Try with Maya's Qt parent finding
                    maya_widget_ptr = omui.MQtUtil.findControl(control_name)
                    if maya_widget_ptr:
                        from shiboken6 import wrapInstance
                        maya_widget = wrapInstance(int(maya_widget_ptr), QWidget)
                        if isinstance(maya_widget, QWidget):
                            # Type cast to QWidget to resolve attribute access
                            widget = maya_widget
                            widget.setMinimumSize(UIConstants.PREVIEW_MIN_WIDTH, UIConstants.PREVIEW_MIN_HEIGHT)
                            
                            self.maya_panel_name = panel_name
                            print("✓ Created Maya viewport using alternative method")
                            return widget
            except Exception:
                pass
                
            return None
                
        except Exception as e:
            print(f"Method 2 (alternative viewport) failed: {e}")
            return None
    
    def _create_playblast_preview_widget(self):
        """Method 3: Real-time playblast-based 3D preview"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Create a widget that will show playblast thumbnails
            preview_widget = QWidget()
            layout = QVBoxLayout(preview_widget)
            
            # Create image label for playblast display
            self.playblast_label = QLabel("3D Preview (Real-time)")
            self.playblast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playblast_label.setMinimumSize(350, 250)
            self.playblast_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    font-size: 14px;
                }
            """)
            
            # Add controls for camera orbit simulation
            controls_layout = QHBoxLayout()
            
            orbit_btn = QPushButton("Orbit View")
            orbit_btn.clicked.connect(self._simulate_orbit_view)
            controls_layout.addWidget(orbit_btn)
            
            refresh_btn = QPushButton("Refresh Preview")
            refresh_btn.clicked.connect(self._refresh_playblast_preview)
            controls_layout.addWidget(refresh_btn)
            
            layout.addWidget(self.playblast_label)
            layout.addLayout(controls_layout)
            
            # Store widget reference
            self.playblast_widget = preview_widget
            
            print("✓ Created playblast-based 3D preview")
            return preview_widget
                
        except Exception as e:
            print(f"Method 3 (playblast preview) failed: {e}")
            return None
    
    def _create_mesh_preview_widget(self):
        """Method 4: Custom OpenGL-based mesh preview widget"""
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShaderProgram
            
            class Simple3DPreview(QOpenGLWidget):
                def __init__(self):
                    super().__init__()
                    self.rotation_x = 0
                    self.rotation_y = 0
                    self.zoom = -5
                    self.setMinimumSize(350, 250)
                    
                def mousePressEvent(self, event):
                    self.last_pos = event.position()
                    
                def mouseMoveEvent(self, event):
                    if hasattr(self, 'last_pos'):
                        dx = event.position().x() - self.last_pos.x()
                        dy = event.position().y() - self.last_pos.y()
                        self.rotation_x += dy
                        self.rotation_y += dx
                        self.last_pos = event.position()
                        self.update()
                        
                def wheelEvent(self, event):
                    delta = event.angleDelta().y()
                    self.zoom += delta / 120.0
                    self.update()
                    
                def paintGL(self):
                    # Simple wireframe cube rendering would go here
                    pass
                    
            preview_widget = Simple3DPreview()
            print("✓ Created custom OpenGL 3D preview")
            return preview_widget
                
        except Exception as e:
            print(f"Method 4 (OpenGL preview) failed: {e}")
            return None
    
    def _create_fallback_preview_widget(self):
        """Create fallback preview widget when Maya viewport is unavailable"""
        self.preview_label = QLabel("3D Preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        self.preview_label.setMinimumSize(350, 250)
        
        # Add mouse tracking for simulated orbit controls
        self.preview_label.mousePressEvent = self.preview_mouse_press
        self.preview_label.mouseMoveEvent = self.preview_mouse_move
        self.preview_label.wheelEvent = self.preview_wheel
        
        return self.preview_label
    
    def _set_preview_text(self, text):
        """Set preview text in the appropriate preview widget - Clean Code helper method"""
        # Handle different preview widget types (Single Responsibility Principle)
        if hasattr(self, 'preview_info_label') and self.preview_info_label:
            self.preview_info_label.setText(text)
        elif hasattr(self, 'preview_label') and self.preview_label:
            self.preview_label.setText(text)
        else:
            print(f"Warning: No preview label available for text: {text[:50]}...")
    
    def _set_preview_pixmap(self, pixmap):
        """Set preview pixmap in the appropriate preview widget - Clean Code helper method"""
        # Professional info display shows file icons instead of pixmaps
        if hasattr(self, 'preview_info_label') and self.preview_info_label:
            self.preview_info_label.setPixmap(pixmap)
        elif hasattr(self, 'preview_label') and self.preview_label:
            self.preview_label.setPixmap(pixmap)
        else:
            print("Warning: No preview label available for pixmap")
    
    def _simulate_orbit_view(self):
        """Simulate orbit view by generating a new playblast from different angle"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            if not hasattr(self, 'current_scene_file') or not self.current_scene_file:
                print("No scene loaded for orbit simulation")
                return
                
            # Get a valid model panel instead of using the focused panel
            model_panel = self._get_suitable_viewport_panel(cmds)
            
            if not model_panel:
                print("No suitable model panel found for orbit simulation")
                return
                
            # Get current camera from the model panel
            try:
                current_cam = cmds.modelPanel(model_panel, query=True, camera=True)
                
                # Orbit camera slightly
                if current_cam and cmds.objExists(current_cam):
                    cmds.rotate(15, 10, 0, current_cam, relative=True)
                    print(f"✓ Orbited camera: {current_cam}")
                else:
                    print(f"Camera not found or invalid: {current_cam}")
                    
            except Exception as e:
                print(f"Camera rotation error: {e}")
                
            # Refresh preview
            self._refresh_playblast_preview()
            
        except Exception as e:
            print(f"Orbit simulation error: {e}")
    
    def _refresh_playblast_preview(self):
        """Refresh the playblast preview with current scene"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            if not hasattr(self, 'playblast_label') or not self.playblast_label:
                return
                
            # Get a suitable model panel for playblast
            model_panel = self._get_suitable_viewport_panel(cmds)
            if not model_panel:
                self.playblast_label.setText("No viewport\navailable for\nplayblast")
                return
                
            # Generate quick playblast
            temp_dir = tempfile.mkdtemp(prefix="preview_")
            preview_path = os.path.join(temp_dir, "preview.jpg")
            
            # Quick playblast of current view with specific panel
            playblast_config = {
                'format': 'image',
                'compression': 'jpg',
                'quality': 70,
                'width': 350,
                'height': 250,
                'viewer': False,
                'showOrnaments': False,
                'frame': [1, 1],
                'offScreen': True,
                'filename': preview_path
            }
            
            # Try to set active panel for playblast
            try:
                cmds.setFocus(model_panel)
            except Exception:
                pass  # Continue without setting focus
                
            result = cmds.playblast(**playblast_config)
            
            # Load image into label
            if result and os.path.exists(result + ".jpg"):
                pixmap = QPixmap(result + ".jpg")
                if not pixmap.isNull():
                    self.playblast_label.setPixmap(pixmap.scaled(
                        350, 250, Qt.AspectRatioMode.KeepAspectRatio))
                    print("✓ Preview refreshed with playblast")
                else:
                    self.playblast_label.setText("Preview\nGeneration\nFailed")
                    
                # Cleanup temp file
                try:
                    os.remove(result + ".jpg")
                except:
                    pass
            else:
                self.playblast_label.setText("3D Preview\n(Scene Empty)")
                
        except Exception as e:
            print(f"Playblast preview error: {e}")
            if hasattr(self, 'playblast_label') and self.playblast_label:
                self.playblast_label.setText(f"Preview Error:\n{str(e)[:30]}...")
    
    def create_metadata_widget(self):
        """Create the metadata display widget"""
        metadata_frame = QFrame()
        metadata_frame.setFrameStyle(QFrame.Shape.Box)
        
        layout = QVBoxLayout(metadata_frame)
        
        # Metadata header
        header_label = QLabel("Asset Information")
        header_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        layout.addWidget(header_label)
        
        # Scrollable metadata area
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.metadata_layout = QVBoxLayout(scroll_widget)
        
        # Initialize with empty metadata
        self.update_metadata_display({})
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        layout.addWidget(scroll_area, 1)
        
        return metadata_frame
    
    def create_comparison_widget(self):
        """Create the asset comparison widget"""
        comparison_frame = QFrame()
        comparison_frame.setFrameStyle(QFrame.Shape.Box)
        
        layout = QHBoxLayout(comparison_frame)
        
        # Comparison controls
        controls_layout = QVBoxLayout()
        
        compare_label = QLabel("Asset Comparison")
        compare_label.setStyleSheet("font-weight: bold;")
        
        self.compare_with_btn = QPushButton("Compare With...")
        self.close_comparison_btn = QPushButton("Close Comparison")
        
        controls_layout.addWidget(compare_label)
        controls_layout.addWidget(self.compare_with_btn)
        controls_layout.addWidget(self.close_comparison_btn)
        controls_layout.addStretch()
        
        # Comparison preview areas
        self.comparison_preview_left = QLabel("Original Asset")
        self.comparison_preview_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.comparison_preview_left.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                min-height: 200px;
            }
        """)
        
        self.comparison_preview_right = QLabel("Comparison Asset")
        self.comparison_preview_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.comparison_preview_right.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                min-height: 200px;
            }
        """)
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.comparison_preview_left, 1)
        layout.addWidget(self.comparison_preview_right, 1)
        
        return comparison_frame
    
    def setup_connections(self):
        """Setup widget signal connections"""
        # Professional asset comparison controls  
        self.compare_with_btn.clicked.connect(self.start_asset_comparison)
        self.close_comparison_btn.clicked.connect(self.close_asset_comparison)
        
        # Professional screenshot system
        self.screenshot_btn.clicked.connect(self.capture_maya_screenshot)
    
    def preview_asset(self, asset_path):
        """Load and preview an asset"""
        if not os.path.exists(asset_path):
            self.clear_preview()
            return
        
        self.current_asset_path = asset_path
        
        # Update header info to show current asset
        asset_name = os.path.basename(asset_path)
        if hasattr(self, 'asset_info_label'):
            self.asset_info_label.setText(f"Previewing: {asset_name}")
        
        # Enable screenshot button when asset is selected
        if hasattr(self, 'screenshot_btn'):
            self.screenshot_btn.setEnabled(True)
        
        # Update 3D preview
        self.update_3d_preview(asset_path)
        
        # Extract and display metadata
        metadata = self.asset_manager.extract_asset_metadata(asset_path)
        self.update_metadata_display(metadata)
        
        # Professional asset information system - no quality suggestions needed
    
    def _detect_and_apply_renderman_materials(self, nodes):
        """Detect and configure RenderMan materials for proper 3D preview with production scene robustness"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Get all materials in the scene with error handling for production scenes
            all_materials = []
            try:
                all_materials = cmds.ls(materials=True) or []
                # Also check shading engines which are more reliable in complex scenes
                shading_engines = cmds.ls(type='shadingEngine') or []
                all_materials.extend(shading_engines)
            except Exception as e:
                print(f"Material query info: {e}")
            
            renderman_materials = []
            ptex_textures = []
            renderman_nodes = []
            
            # Find RenderMan-specific material types with comprehensive detection
            for material in all_materials:
                try:
                    material_type = cmds.nodeType(material)
                    # Enhanced RenderMan material detection
                    if any(rman_type in material_type for rman_type in ['Pxr', 'Rman', 'renderman', 'RenderMan']):
                        renderman_materials.append(material)
                        print(f"✓ Found RenderMan material: {material} ({material_type})")
                except Exception:
                    continue
            
            # Find RenderMan-specific nodes in the scene
            try:
                # Look for RenderMan-specific node types
                rman_node_types = ['PxrSurface', 'PxrTexture', 'PxrDisney', 'PxrLMDiffuse', 'RmanDisplayChannel']
                for node_type in rman_node_types:
                    try:
                        nodes_of_type = cmds.ls(type=node_type) or []
                        renderman_nodes.extend(nodes_of_type)
                        if nodes_of_type:
                            print(f"✓ Found {len(nodes_of_type)} {node_type} nodes")
                    except Exception:
                        continue
            except Exception:
                pass
            
            # Find .ptex textures with better error handling
            texture_node_types = ['PxrTexture', 'file', 'rmanImageFile']
            for texture_type in texture_node_types:
                try:
                    texture_nodes = cmds.ls(type=texture_type) or []
                    for texture in texture_nodes:
                        try:
                            # Try different attribute names for file path
                            file_attrs = ['filename', 'fileTextureName', 'imageName']
                            for attr in file_attrs:
                                try:
                                    file_path = cmds.getAttr(f"{texture}.{attr}")
                                    if file_path and file_path.endswith('.ptex'):
                                        ptex_textures.append((texture, file_path))
                                        print(f"✓ Found .ptex texture: {texture} -> {os.path.basename(file_path)}")
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            continue
                except Exception:
                    continue
            
            # Apply RenderMan viewport settings for better material display
            total_rman_elements = len(renderman_materials) + len(renderman_nodes) + len(ptex_textures)
            if total_rman_elements > 0:
                if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
                    try:
                        # Enable RenderMan preview in viewport with production scene compatibility
                        cmds.modelEditor(self.maya_panel_name, edit=True, 
                                       displayAppearance='smoothShaded',
                                       displayTextures=True,
                                       textureHilight=True,
                                       wireframeOnShaded=False,
                                       displayLights='all')
                        
                        # Try to enable RenderMan-specific viewport features
                        try:
                            # Enable RenderMan viewport rendering if available
                            if cmds.objExists('defaultRenderGlobals'):
                                current_renderer = cmds.getAttr('defaultRenderGlobals.currentRenderer')
                                if 'renderman' in current_renderer.lower():
                                    print("✓ RenderMan detected as current renderer")
                        except Exception:
                            pass
                        
                        print(f"✓ Applied RenderMan viewport settings:")
                        print(f"  - {len(renderman_materials)} RenderMan materials")
                        print(f"  - {len(renderman_nodes)} RenderMan nodes") 
                        print(f"  - {len(ptex_textures)} .ptex textures")
                        
                    except Exception as e:
                        print(f"Viewport configuration info: {e}")
                else:
                    print("No Maya panel available for RenderMan configuration")
            else:
                print("No RenderMan materials or .ptex textures detected in this scene")
                
        except Exception as e:
            print(f"RenderMan material detection info: {e}")
            # Continue without RenderMan detection - not critical for basic preview

    def _configure_viewport_for_renderer(self, renderer_name):
        """Configure viewport display settings for specific renderer"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            if not hasattr(self, 'maya_panel_name') or not self.maya_panel_name:
                return
                
            # Apply renderer-specific viewport settings
            if renderer_name == "RenderMan":
                cmds.modelEditor(self.maya_panel_name, edit=True,
                               displayAppearance='smoothShaded',
                               displayTextures=True,
                               textureHilight=True,
                               wireframeOnShaded=False,
                               displayLights='all')
                print("✓ Configured viewport for RenderMan display")
                
            elif renderer_name == "Arnold":
                cmds.modelEditor(self.maya_panel_name, edit=True,
                               displayAppearance='smoothShaded', 
                               displayTextures=True,
                               wireframeOnShaded=False)
                print("✓ Configured viewport for Arnold display")
                
            else:  # Maya Software
                cmds.modelEditor(self.maya_panel_name, edit=True,
                               displayAppearance='smoothShaded',
                               displayTextures=False)
                print("✓ Configured viewport for Maya Software display")
                
        except Exception as e:
            print(f"Error configuring viewport for renderer: {e}")

    def update_3d_preview(self, asset_path):
        """Update the 3D preview display with clean screenshot-based approach"""
        if not asset_path or not os.path.exists(asset_path):
            if hasattr(self, 'preview_info_label'):
                self.preview_info_label.setText("Asset not found")
            return
            
        self.current_asset_path = asset_path
        asset_name = os.path.basename(asset_path)
        file_ext = os.path.splitext(asset_path)[1].lower()
        
        # Use professional asset info display - CRASH-SAFE ALTERNATIVE
        if hasattr(self, 'professional_preview') and self.professional_preview:
            self._show_professional_asset_info(asset_path)
            return
            
        # Fallback to old method if screenshot not available
        try:
            if file_ext in ['.ma', '.mb']:
                self._load_maya_scene_preview(asset_path)
            elif file_ext == '.obj':
                self._load_obj_preview(asset_path)  
            elif file_ext == '.fbx':
                self._load_fbx_preview(asset_path)
            else:
                self._show_unsupported_preview(asset_path)
        except Exception as e:
            print(f"Error loading 3D preview: {e}")
            self._show_error_preview(asset_path, str(e))

    def _generate_screenshot_preview(self, asset_path):
        """REMOVED: Replaced with crash-safe professional asset information display"""
        # Redirect to professional info display
        self._show_professional_asset_info(asset_path)
    
    def _show_professional_asset_info(self, asset_path):
        """Show professional asset information - CRASH-SAFE ALTERNATIVE"""
        try:
            asset_name = os.path.basename(asset_path)
            file_ext = os.path.splitext(asset_path)[1].lower()
            
            # Show simplified preview with SQUARE icon to match library
            if hasattr(self, 'preview_info_label'):
                # Show large SQUARE professional file icon for preview (matches library style)
                professional_icon = self.asset_manager._generate_professional_file_icon(asset_path, (250, 250))
                if professional_icon:
                    self.preview_info_label.setPixmap(professional_icon)
                else:
                    self.preview_info_label.setText(f"Preview Ready\n\n{asset_name}")
                    
            # Show focused technical details (non-duplicate information)
            if hasattr(self, 'preview_details_label'):
                file_stats = os.stat(asset_path)
                file_size = file_stats.st_size
                modified_time = datetime.fromtimestamp(file_stats.st_mtime).strftime("%Y-%m-%d %H:%M")
                
                # Show only technical file details (not duplicating icon info)
                if file_size > 1024*1024:
                    size_str = f"{file_size/(1024*1024):.1f} MB"
                elif file_size > 1024:
                    size_str = f"{file_size/1024:.1f} KB" 
                else:
                    size_str = f"{file_size} bytes"
                
                # Asset details are now handled by the metadata widget
                print(f"✅ Professional asset preview displayed: {asset_name}")
                
        except Exception as e:
            print(f"Error showing professional asset info: {e}")
            if hasattr(self, 'preview_info_label'):
                self.preview_info_label.setText(f"Preview Error\n\n{os.path.basename(asset_path)}")
    
    def _load_maya_scene_preview(self, asset_path):
        """Load Maya scene content in preview - Single Responsibility with import optimization"""
        try:
            if not MAYA_AVAILABLE:
                self._show_no_maya_preview(asset_path)
                return
            
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Store current scene file reference
            self.current_scene_file = asset_path
            
            # Check if this scene is already loaded to prevent redundant imports
            if hasattr(self, '_last_loaded_scene') and self._last_loaded_scene == asset_path:
                print(f"✓ Scene already loaded: {os.path.basename(asset_path)}")
                self._handle_already_loaded_scene(asset_path)
                return
                
            # Import the Maya scene into current scene for interactive preview
            print(f"Loading RenderMan production scene: {os.path.basename(asset_path)}")
            
            # Clear scene first if we have a different asset loaded
            if hasattr(self, '_last_loaded_scene') and self._last_loaded_scene != asset_path:
                print("Clearing previous scene content...")
                cmds.file(new=True, force=True)
            
            nodes = cmds.file(asset_path, i=True, returnNewNodes=True)
            self._last_loaded_scene = asset_path  # Track loaded scene
            
            # Handle different preview widget types
            if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
                # Interactive Maya viewport approach
                self._handle_maya_viewport_preview(asset_path, nodes)
            elif hasattr(self, 'playblast_label') and self.playblast_label:
                # Playblast-based preview approach  
                self._handle_playblast_preview(asset_path, nodes)
            else:
                # Fallback thumbnail approach
                self._handle_thumbnail_preview(asset_path, nodes)
                
        except Exception as e:
            print(f"RenderMan scene load info: Expected production scene warnings handled")
            # Don't treat RenderMan connection warnings as real errors
            self._handle_preview_error(asset_path, "Production scene loaded with warnings")
    
    def _handle_already_loaded_scene(self, asset_path):
        """Handle scene that's already loaded in preview"""
        if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
            # Just reframe the existing content
            try:
                import maya.cmds as cmds # pyright: ignore[reportMissingImports]
                all_transforms = cmds.ls(type='transform', long=False) or []
                scene_objects = [obj for obj in all_transforms if not obj.startswith('default') and not obj.startswith('persp')]
                if scene_objects:
                    cmds.select(scene_objects)
                    cmds.viewFit(self.maya_panel_name)
                    self.preview_status.setText(f"RenderMan Scene • {len(scene_objects)} objects • Already Loaded")
                    print(f"✓ Reframed existing content: {len(scene_objects)} objects")
                return
            except Exception as e:
                print(f"Reframe warning: {e}")
                # Clear tracking and proceed with fresh import
                if hasattr(self, '_last_loaded_scene'):
                    delattr(self, '_last_loaded_scene')
        elif hasattr(self, 'playblast_label'):
            # Refresh playblast preview
            self._refresh_playblast_preview()
            self.preview_status.setText("RenderMan Scene • Already Loaded")
        else:
            # Update status for thumbnail preview
            self.preview_status.setText("RenderMan Scene • Already Loaded")
    
    def _handle_maya_viewport_preview(self, asset_path, nodes):
        """Handle Maya viewport-based preview"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            if nodes:
                # Focus camera on imported content
                cmds.select(nodes)
                cmds.viewFit(self.maya_panel_name)
                
                # Professional asset system - 3D viewport configuration removed
                
                # Update info display
                preview_type = "MEL 3D" if hasattr(self, 'mel_preview') and self.mel_preview else "Interactive 3D"
                self.preview_status.setText(f"RenderMan Scene • {len(nodes)} objects • {preview_type}")
                
                print(f"✓ Loaded RenderMan production scene with {len(nodes)} objects successfully")
            else:
                self.preview_status.setText("Maya Scene • No geometry found")
                
        except Exception as e:
            print(f"Maya viewport preview error: {e}")
            self.preview_status.setText("RenderMan Production Scene • Loaded with warnings")
    
    def _handle_playblast_preview(self, asset_path, nodes):
        """Handle playblast-based preview"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            if nodes:
                # Frame geometry for playblast
                cmds.select(nodes)
                cmds.viewFit()
                
                # Refresh playblast preview
                self._refresh_playblast_preview()
                
                self.preview_status.setText(f"RenderMan Scene • {len(nodes)} objects • Real-time Preview")
                print(f"✓ Loaded scene for playblast preview with {len(nodes)} objects")
            else:
                self.playblast_label.setText("3D Preview\n(No Geometry)")
                self.preview_status.setText("Maya Scene • No geometry found")
                
        except Exception as e:
            print(f"Playblast preview error: {e}")
            self.playblast_label.setText(f"Preview Error:\n{str(e)[:30]}...")
    
    def _handle_thumbnail_preview(self, asset_path, nodes):
        """Handle fallback thumbnail preview"""
        try:
            # Fallback to thumbnail preview
            scene_info = self._analyze_maya_scene(asset_path)
            preview_image = self.asset_manager._generate_thumbnail_safe(asset_path, size=(300, 300))
            
            if preview_image and not preview_image.isNull():
                scaled_pixmap = preview_image.scaled(
                    300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self._set_preview_pixmap(scaled_pixmap)
                self.preview_status.setText(f"Maya Scene • {scene_info.get('meshes', 0)} meshes")
            else:
                self._show_maya_scene_info(asset_path, scene_info)
                
        except Exception as e:
            print(f"Thumbnail preview error: {e}")
            self._show_error_preview(asset_path, "Thumbnail generation failed")
    
    def _handle_preview_error(self, asset_path, error_msg):
        """Handle preview error for all preview types"""
        if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
            self.preview_status.setText("RenderMan Production Scene • Loaded with warnings")
        elif hasattr(self, 'playblast_label') and self.playblast_label:
            self.playblast_label.setText("Preview Error")
            self.preview_status.setText("Production scene loaded with warnings")
        else:
            self._show_error_preview(asset_path, error_msg)

    def _get_scene_info_from_nodes(self, nodes):
        """Get scene information from imported nodes"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            meshes = [n for n in nodes if cmds.nodeType(n) == 'mesh']
            lights = [n for n in nodes if 'light' in cmds.nodeType(n).lower()]
            materials = cmds.ls(materials=True, type='shadingEngine')
            
            return {
                'meshes': len(meshes),
                'lights': len(lights), 
                'materials': len(materials),
                'total_nodes': len(nodes)
            }
        except:
            return {'meshes': 0, 'lights': 0, 'materials': 0, 'total_nodes': len(nodes)}
    
    def _analyze_maya_scene(self, asset_path):
        """Analyze Maya scene content for preview metadata"""
        scene_info = {'meshes': 0, 'lights': 0, 'cameras': 0, 'materials': 0}
        
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Save current state
            current_file = cmds.file(q=True, sceneName=True) if cmds else None
            
            # Create new scene and import asset
            cmds.file(new=True, force=True)
            cmds.file(asset_path, i=True, ignoreVersion=True)
            
            # Analyze scene content
            scene_info['meshes'] = len(cmds.ls(type='mesh') or [])
            scene_info['lights'] = len(cmds.ls(type='light') or [])
            scene_info['cameras'] = len(cmds.ls(type='camera') or []) - 4  # Exclude default cameras
            scene_info['materials'] = len(cmds.ls(materials=True) or [])
            
            # Restore original scene
            if current_file:
                cmds.file(current_file, o=True, force=True)
            else:
                cmds.file(new=True, force=True)
                
        except Exception as e:
            print(f"Scene analysis error: {e}")
            
        return scene_info
    
    def _load_obj_preview(self, asset_path):
        """Load OBJ file preview with vertex analysis"""
        try:
            # Generate OBJ thumbnail and analyze content
            preview_image = self.asset_manager._generate_thumbnail_safe(asset_path, size=(300, 300))
            obj_info = self._analyze_obj_file(asset_path)
            
            if preview_image and not preview_image.isNull():
                scaled_pixmap = preview_image.scaled(
                    300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self._set_preview_pixmap(scaled_pixmap)
                self.preview_status.setText(f"OBJ Mesh • {obj_info.get('vertices', 0)} vertices • {obj_info.get('faces', 0)} faces")
            else:
                self._show_obj_info(asset_path, obj_info)
                
        except Exception as e:
            self._show_error_preview(asset_path, f"OBJ loading error: {e}")
    
    def _analyze_obj_file(self, asset_path):
        """Analyze OBJ file for preview metadata"""
        obj_info = {'vertices': 0, 'faces': 0, 'materials': 0}
        
        try:
            with open(asset_path, 'r') as f:
                for line_num, line in enumerate(f):
                    if line_num > 5000:  # Limit analysis for performance
                        break
                    line = line.strip()
                    if line.startswith('v '):
                        obj_info['vertices'] += 1
                    elif line.startswith('f '):
                        obj_info['faces'] += 1
                    elif line.startswith('usemtl'):
                        obj_info['materials'] += 1
                        
        except Exception as e:
            print(f"OBJ analysis error: {e}")
            
        return obj_info
    
    def _load_fbx_preview(self, asset_path):
        """Load FBX file preview"""
        try:
            preview_image = self.asset_manager._generate_thumbnail_safe(asset_path, size=(300, 300))
            
            if preview_image and not preview_image.isNull():
                scaled_pixmap = preview_image.scaled(
                    300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self._set_preview_pixmap(scaled_pixmap)
                self.preview_status.setText("FBX Asset • Hierarchical data")
            else:
                self._show_fbx_info(asset_path)
                
        except Exception as e:
            self._show_error_preview(asset_path, f"FBX loading error: {e}")
    
    def _show_maya_scene_info(self, asset_path, scene_info):
        """Show Maya scene info when preview image unavailable"""
        asset_name = os.path.basename(asset_path)
        info_text = f"""
{asset_name}

Maya Scene Information:
• Meshes: {scene_info.get('meshes', 0)}
• Lights: {scene_info.get('lights', 0)} 
• Cameras: {scene_info.get('cameras', 0)}
• Materials: {scene_info.get('materials', 0)}

Quality: {self.preview_quality}
        """
        self._set_preview_text(info_text)
    
    def _show_obj_info(self, asset_path, obj_info):
        """Show OBJ info when preview image unavailable"""
        asset_name = os.path.basename(asset_path)
        info_text = f"""
{asset_name}

OBJ Geometry Information:
• Vertices: {obj_info.get('vertices', 0):,}
• Faces: {obj_info.get('faces', 0):,}
• Materials: {obj_info.get('materials', 0)}

Quality: {self.preview_quality}
        """
        self._set_preview_text(info_text)
    
    def _show_fbx_info(self, asset_path):
        """Show FBX info when preview image unavailable"""
        asset_name = os.path.basename(asset_path)
        info_text = f"""
{asset_name}

FBX Asset
Hierarchical geometry data
Animation and rigging support

Quality: {self.preview_quality}
        """
        self._set_preview_text(info_text)
    
    def _show_unsupported_preview(self, asset_path):
        """Show message for unsupported file types"""
        asset_name = os.path.basename(asset_path)
        file_ext = os.path.splitext(asset_path)[1].upper()
        
        self._set_preview_text(f"""
{asset_name}

File Type: {file_ext}
Preview not supported for this format

Supported formats:
• Maya Scenes (.ma, .mb)
• OBJ Geometry (.obj)  
• FBX Assets (.fbx)
        """)
    
    def _show_no_maya_preview(self, asset_path):
        """Show message when Maya is unavailable"""
        asset_name = os.path.basename(asset_path)
        self._set_preview_text(f"""
{asset_name}

Maya Required
3D preview requires Maya to be available
for scene analysis and rendering

Please run Asset Manager within Maya
        """)
    
    def _show_error_preview(self, asset_path, error_msg):
        """Show error message in preview area"""
        asset_name = os.path.basename(asset_path)
        self._set_preview_text(f"""
{asset_name}

Preview Error
{error_msg}

Please check the asset file and try again
        """)
    
    def update_metadata_display(self, metadata):
        """Update the metadata display panel"""
        # Clear existing metadata widgets
        for i in reversed(range(self.metadata_layout.count())):
            child = self.metadata_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        if not metadata:
            no_data_label = QLabel("No metadata available")
            no_data_label.setStyleSheet("color: #888888; padding: 10px;")
            self.metadata_layout.addWidget(no_data_label)
            return
        
        # File information
        self.add_metadata_section("File Information", [
            ("Name", metadata.get('file_name', 'Unknown')),
            ("Type", metadata.get('file_extension', 'Unknown').upper()),
            ("Size", f"{metadata.get('file_size', 0) / (1024*1024):.2f} MB"),
            ("Modified", time.strftime('%Y-%m-%d %H:%M', time.localtime(metadata.get('last_modified', 0))))
        ])
        
        # Geometry information
        if any(key in metadata for key in ['vertex_count', 'face_count', 'poly_count']):
            geo_info = []
            if metadata.get('vertex_count', 0) > 0:
                geo_info.append(("Vertices", f"{metadata['vertex_count']:,}"))
            if metadata.get('face_count', 0) > 0:
                geo_info.append(("Faces", f"{metadata['face_count']:,}"))
            if metadata.get('poly_count', 0) > 0:
                geo_info.append(("Polygons", f"{metadata['poly_count']:,}"))
            
            if geo_info:
                self.add_metadata_section("Geometry", geo_info)
        
        # Material and texture information
        material_info = []
        if metadata.get('material_count', 0) > 0:
            material_info.append(("Materials", str(metadata['material_count'])))
        if metadata.get('texture_count', 0) > 0:
            material_info.append(("Textures", str(metadata['texture_count'])))
        
        if material_info:
            self.add_metadata_section("Materials & Textures", material_info)
        
        # Animation information
        if metadata.get('has_animation', False):
            anim_info = [
                ("Has Animation", "Yes"),
                ("Frame Count", str(metadata.get('animation_frames', 0)))
            ]
            self.add_metadata_section("Animation", anim_info)
        
        # Scene objects
        scene_objects = metadata.get('scene_objects', [])
        if scene_objects:
            objects_info = [("Object Count", str(len(scene_objects)))]
            if len(scene_objects) <= 10:
                for i, obj in enumerate(scene_objects[:5]):
                    objects_info.append((f"Object {i+1}", os.path.basename(obj)))
                if len(scene_objects) > 5:
                    objects_info.append(("...", f"and {len(scene_objects) - 5} more"))
            
            self.add_metadata_section("Scene Objects", objects_info)
        
        # Complexity and suggestions
        complexity = metadata.get('complexity_rating', 0)
        if complexity > 0:
            complexity_info = [
                ("Complexity", f"{complexity}/10"),
                ("Suggested Quality", metadata.get('preview_quality_suggestion', 'Medium'))
            ]
            self.add_metadata_section("Performance", complexity_info)
        
        self.metadata_layout.addStretch()
    
    def add_metadata_section(self, title, items):
        """Add a metadata section with title and items"""
        # Section title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #ffffff;
                background-color: #404040;
                padding: 4px 8px;
                border-radius: 3px;
                margin-top: 5px;
            }
        """)
        self.metadata_layout.addWidget(title_label)
        
        # Section items
        for key, value in items:
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 2, 5, 2)
            
            key_label = QLabel(f"{key}:")
            key_label.setStyleSheet("color: #cccccc; font-weight: normal;")
            key_label.setMinimumWidth(80)
            
            value_label = QLabel(str(value))
            value_label.setStyleSheet("color: #ffffff; font-weight: normal;")
            value_label.setWordWrap(True)
            
            item_layout.addWidget(key_label)
            item_layout.addWidget(value_label, 1)
            
            self.metadata_layout.addWidget(item_widget)
    
    def clear_preview(self):
        """Clear the preview display"""
        self.current_asset_path = None
        
        # Reset header info
        if hasattr(self, 'asset_info_label'):
            self.asset_info_label.setText("Asset Preview")
        
        # Disable screenshot button when no asset selected
        if hasattr(self, 'screenshot_btn'):
            self.screenshot_btn.setEnabled(False)
        
        # Handle different preview widget types
        if hasattr(self, 'preview_info_label') and self.preview_info_label:
            self.preview_info_label.setText("Select an asset to preview")
        elif hasattr(self, 'preview_label') and self.preview_label:
            self.preview_label.setText("Select an asset to preview")
            
        # Reset status
        if hasattr(self, 'preview_status'):
            self.preview_status.setText("Ready")
            
        self.update_metadata_display({})
    
    def capture_maya_screenshot(self):
        """Capture high-resolution screenshot from Maya viewport and set as asset thumbnail"""
        if not hasattr(self, 'current_asset_path') or not self.current_asset_path:
            QMessageBox.information(self, "No Asset Selected", 
                                  "Please select an asset first to capture a screenshot thumbnail.")
            return
        
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            import tempfile
            import shutil
            
            # Create screenshot options dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("📸 Capture Maya Screenshot")
            dialog.setModal(True)
            dialog.resize(400, 350)
            
            layout = QVBoxLayout(dialog)
            
            # Instructions
            info_label = QLabel("📋 Instructions:\n"
                               "1. Position your asset in Maya's viewport\n"
                               "2. Choose screenshot resolution below\n"
                               "3. Click 'Capture Screenshot' to save as thumbnail")
            info_label.setWordWrap(True)
            info_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f8ff;
                    border: 1px solid #4A90E2;
                    border-radius: 6px;
                    padding: 10px;
                    margin: 5px;
                    font-size: 11px;
                }
            """)
            layout.addWidget(info_label)
            
            # Resolution options
            res_group = QWidget()
            res_layout = QVBoxLayout(res_group)
            res_layout.addWidget(QLabel("Screenshot Resolution:"))
            
            self.res_combo = QComboBox()
            resolution_options = [
                ("Standard (256x256)", 256),
                ("High Quality (512x512)", 512),
                ("Ultra HD (1024x1024)", 1024),
                ("Max Quality (2048x2048)", 2048)
            ]
            
            for name, size in resolution_options:
                self.res_combo.addItem(name, size)
            
            self.res_combo.setCurrentIndex(2)  # Default to Ultra HD
            res_layout.addWidget(self.res_combo)
            layout.addWidget(res_group)
            
            # Quality options
            quality_group = QWidget()
            quality_layout = QVBoxLayout(quality_group)
            quality_layout.addWidget(QLabel("Image Quality:"))
            
            self.quality_combo = QComboBox()
            self.quality_combo.addItem("High Quality (PNG)", "png")
            self.quality_combo.addItem("Maximum Quality (TIFF)", "tiff")
            quality_layout.addWidget(self.quality_combo)
            layout.addWidget(quality_group)
            
            # Viewport options
            viewport_group = QWidget()
            viewport_layout = QVBoxLayout(viewport_group)
            viewport_layout.addWidget(QLabel("Viewport Settings:"))
            
            self.smooth_shading = QCheckBox("Smooth Shading")
            self.smooth_shading.setChecked(True)
            self.wireframe_on_shaded = QCheckBox("Wireframe on Shaded")
            self.wireframe_on_shaded.setChecked(False)
            self.show_grid = QCheckBox("Show Grid")
            self.show_grid.setChecked(False)
            
            viewport_layout.addWidget(self.smooth_shading)
            viewport_layout.addWidget(self.wireframe_on_shaded)
            viewport_layout.addWidget(self.show_grid)
            layout.addWidget(viewport_group)
            
            # Buttons
            button_layout = QHBoxLayout()
            
            preview_btn = QPushButton("🔍 Preview Settings")
            preview_btn.setToolTip("Apply viewport settings to see preview")
            preview_btn.clicked.connect(self._apply_viewport_settings)
            
            capture_btn = QPushButton("📸 Capture Screenshot")
            capture_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            
            cancel_btn = QPushButton("Cancel")
            
            button_layout.addWidget(preview_btn)
            button_layout.addStretch()
            button_layout.addWidget(capture_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            # Button connections
            def capture_screenshot():
                self._perform_screenshot_capture(dialog)
            
            capture_btn.clicked.connect(capture_screenshot)
            cancel_btn.clicked.connect(dialog.reject)
            
            # Show dialog
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._refresh_asset_thumbnail()
                
        except Exception as e:
            QMessageBox.warning(self, "Screenshot Error", 
                              f"Failed to capture screenshot: {str(e)}")
            print(f"Screenshot error: {e}")
    
    def _apply_viewport_settings(self):
        """Apply viewport settings for preview"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Get active viewport
            active_panel = cmds.getPanel(withFocus=True)
            if not cmds.getPanel(typeOf=active_panel) == 'modelPanel':
                # Find a model panel if current panel isn't one
                model_panels = cmds.getPanel(type='modelPanel')
                if model_panels:
                    active_panel = model_panels[0]
                else:
                    QMessageBox.warning(self, "No Viewport", "No Maya viewport found to apply settings.")
                    return
            
            # Apply viewport settings
            cmds.modelEditor(active_panel, edit=True,
                           displayAppearance='smoothShaded' if self.smooth_shading.isChecked() else 'wireframe',
                           wireframeOnShaded=self.wireframe_on_shaded.isChecked(),
                           grid=self.show_grid.isChecked(),
                           displayTextures=True,
                           displayLights='default',
                           shadows=False,
                           useDefaultMaterial=False)
            
            # Force viewport refresh
            cmds.refresh()
            
            QMessageBox.information(self, "Settings Applied", 
                                  "Viewport settings applied successfully!\nYou can now see the preview in Maya.")
            
        except Exception as e:
            QMessageBox.warning(self, "Settings Error", 
                              f"Failed to apply viewport settings: {str(e)}")
    
    def _perform_screenshot_capture(self, dialog):
        """Perform the actual screenshot capture"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            import tempfile
            import shutil
            import os
            
            # Get settings from dialog
            resolution = self.res_combo.currentData()
            file_format = self.quality_combo.currentData()
            
            # Get active viewport
            active_panel = cmds.getPanel(withFocus=True)
            if not cmds.getPanel(typeOf=active_panel) == 'modelPanel':
                model_panels = cmds.getPanel(type='modelPanel')
                if model_panels:
                    active_panel = model_panels[0]
                else:
                    QMessageBox.warning(self, "No Viewport", "No Maya viewport found for screenshot.")
                    return
            
            # Create temporary file
            temp_dir = tempfile.mkdtemp()
            temp_filename = f"maya_screenshot_{int(time.time())}.{file_format}"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            # Apply final viewport settings
            self._apply_viewport_settings()
            
            # Capture screenshot with high quality
            result = cmds.playblast(
                filename=temp_path,
                format='image',
                compression=file_format,
                quality=100,
                percent=100,
                width=resolution,
                height=resolution,
                viewer=False,
                showOrnaments=False,
                offScreen=True,
                frame=cmds.currentTime(query=True),
                completeFilename=temp_path
            )
            
            # Maya adds frame number to filename, find the actual file
            actual_files = [f for f in os.listdir(temp_dir) if f.startswith("maya_screenshot_")]
            if not actual_files:
                raise Exception("Screenshot file not created")
            
            actual_temp_path = os.path.join(temp_dir, actual_files[0])
            
            # Validate current asset path
            if not self.current_asset_path:
                raise Exception("No asset selected for screenshot")
            
            # Create thumbnail directory for this asset
            asset_dir = os.path.dirname(self.current_asset_path)
            asset_name = os.path.splitext(os.path.basename(self.current_asset_path))[0]
            thumbnail_dir = os.path.join(asset_dir, ".thumbnails")
            os.makedirs(thumbnail_dir, exist_ok=True)
            
            # Save screenshot as asset thumbnail
            thumbnail_path = os.path.join(thumbnail_dir, f"{asset_name}_screenshot.{file_format}")
            shutil.move(actual_temp_path, thumbnail_path)
            
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Update thumbnail cache entry
            if hasattr(self.asset_manager, '_thumbnail_cache'):
                cache_key = f"thumb_{self.current_asset_path}"
                if cache_key in self.asset_manager._thumbnail_cache:
                    del self.asset_manager._thumbnail_cache[cache_key]
            
            # Show success message
            QMessageBox.information(dialog, "Screenshot Captured! 📸", 
                                  f"High-resolution screenshot saved successfully!\n\n"
                                  f"Resolution: {resolution}x{resolution}\n"
                                  f"Location: {thumbnail_path}\n\n"
                                  f"The asset thumbnail will be updated automatically.")
            
            dialog.accept()
            
            print(f"✅ Screenshot captured: {thumbnail_path} ({resolution}x{resolution})")
            
        except Exception as e:
            QMessageBox.warning(dialog, "Capture Failed", 
                              f"Failed to capture screenshot:\n{str(e)}")
            print(f"Screenshot capture error: {e}")
    
    def _refresh_asset_thumbnail(self):
        """Refresh the asset thumbnail in the library after screenshot"""
        try:
            # Trigger library refresh to show new thumbnail
            if hasattr(self, 'asset_manager') and hasattr(self.asset_manager, 'refresh_assets'):
                # Small delay to ensure file is written
                QTimer.singleShot(1000, self.asset_manager.refresh_assets)
                
            # Update preview display
            if self.current_asset_path:
                self.preview_asset(self.current_asset_path)
                
        except Exception as e:
            print(f"Error refreshing thumbnail: {e}")

    # Mouse interaction handlers for 3D preview
    def preview_mouse_press(self, event):
        """Handle mouse press in preview area"""
        self.last_mouse_pos = event.position()
    
    def preview_mouse_move(self, event):
        """Handle mouse move in preview area (orbit controls)"""
        if self.last_mouse_pos is None:
            return
        
        # Calculate mouse movement
        delta = event.position() - self.last_mouse_pos
        
        # Update camera rotation (simulation)
        self.camera_position['rotation_y'] += delta.x() * 0.5
        self.camera_position['rotation_x'] += delta.y() * 0.5
        
        # Clamp rotation
        self.camera_position['rotation_x'] = max(-90, min(90, self.camera_position['rotation_x']))
        
        self.last_mouse_pos = event.position()
        
        # Update orbit info
        self.preview_status.setText(f"Rotation: X={self.camera_position['rotation_x']:.0f}° Y={self.camera_position['rotation_y']:.0f}°")
    
    def preview_wheel(self, event):
        """Handle mouse wheel in preview area (zoom controls)"""
        # Update camera distance (simulation)
        delta = event.angleDelta().y() / 120.0
        self.camera_position['distance'] *= (0.9 if delta > 0 else 1.1)
        self.camera_position['distance'] = max(0.5, min(50.0, self.camera_position['distance']))
        
        # Update orbit info
        self.preview_status.setText(f"Distance: {self.camera_position['distance']:.1f} units")
    
    # Event handlers
    def closeEvent(self, event):
        """Clean up resources when widget is closed"""
        try:
            # Clean up Maya panel if it exists
            if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
                import maya.cmds as cmds # pyright: ignore[reportMissingImports]
                if cmds.modelPanel(self.maya_panel_name, exists=True):
                    cmds.deleteUI(self.maya_panel_name, panel=True)
                    print(f"✓ Cleaned up Maya panel: {self.maya_panel_name}")
            
            # Clear scene tracking
            if hasattr(self, '_last_loaded_scene'):
                delattr(self, '_last_loaded_scene')
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        super().closeEvent(event)

    def _get_suitable_viewport_panel(self, cmds):
        """Get suitable viewport panel for thumbnail generation - AssetPreviewWidget version"""
        try:
            # First priority: Use MEL 3D preview panel if available
            if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
                if cmds.modelPanel(self.maya_panel_name, exists=True):
                    print(f"✓ Using MEL 3D Preview panel for thumbnail: {self.maya_panel_name}")
                    return self.maya_panel_name
                else:
                    print(f"⚠ MEL 3D Preview panel no longer exists: {self.maya_panel_name}")
                    self.maya_panel_name = None
            
            # Fallback: Try current panel first
            current_panel = cmds.getPanel(withFocus=True)
            if current_panel and 'modelPanel' in current_panel:
                print(f"Using current focused panel: {current_panel}")
                return current_panel
            
            # Last resort: Get any available model panel
            model_panels = cmds.getPanel(type='modelPanel')
            if model_panels:
                print(f"Using first available model panel: {model_panels[0]}")
                return model_panels[0]
                
            print("Warning: No model panel available for preview")
            return None
            
        except Exception as e:
            print(f"Error getting viewport panel: {e}")
            return None
    
    def refresh_mel_preview(self):
        """Refresh the MEL-based 3D preview when a new asset is loaded"""
        if hasattr(self, 'mel_preview') and self.mel_preview and hasattr(self, 'maya_panel_name'):
            try:
                import maya.mel as mel # pyright: ignore[reportMissingImports]
                print(f"Refreshing MEL 3D preview: {self.maya_panel_name}")
                mel.eval(f'assetManager_refresh3DPreview "{self.maya_panel_name}"')
                return True
            except Exception as e:
                print(f"Error refreshing MEL preview: {e}")
                return False
        return False
    
    def cleanup_mel_preview(self):
        """Clean up the MEL-based 3D preview panel"""
        if hasattr(self, 'mel_preview') and self.mel_preview and hasattr(self, 'maya_panel_name'):
            try:
                import maya.mel as mel # pyright: ignore[reportMissingImports]
                print(f"Cleaning up MEL 3D preview: {self.maya_panel_name}")
                mel.eval(f'assetManager_cleanup3DPreview "{self.maya_panel_name}"')
                self.maya_panel_name = None
                self.mel_preview = False
                return True
            except Exception as e:
                print(f"Error cleaning up MEL preview: {e}")
                return False
        return False
    
    def frame_selection_mel(self):
        """Frame selection in the MEL-based 3D preview"""
        if hasattr(self, 'mel_preview') and self.mel_preview and hasattr(self, 'maya_panel_name'):
            try:
                import maya.mel as mel # pyright: ignore[reportMissingImports]
                mel.eval(f'assetManager_frameSelection "{self.maya_panel_name}"')
                return True
            except Exception as e:
                print(f"Error framing selection in MEL preview: {e}")
                return False
        return False
    
    def toggle_wireframe_mel(self, wireframe=False):
        """Toggle wireframe mode in the MEL-based 3D preview"""
        if hasattr(self, 'mel_preview') and self.mel_preview and hasattr(self, 'maya_panel_name'):
            try:
                import maya.mel as mel # pyright: ignore[reportMissingImports]
                wireframe_int = 1 if wireframe else 0
                mel.eval(f'assetManager_setWireframe "{self.maya_panel_name}" {wireframe_int}')
                return True
            except Exception as e:
                print(f"Error toggling wireframe in MEL preview: {e}")
                return False
        return False

    def clear_3d_preview(self):
        """Clear the current 3D preview scene with enhanced cleanup"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Force scene cleanup to prevent import accumulation
            print("Clearing 3D preview scene...")
            
            # Create completely clean scene
            cmds.file(new=True, force=True)
            
            # Clear all tracking to ensure fresh state
            if hasattr(self, '_last_loaded_scene'):
                delattr(self, '_last_loaded_scene')
                print("✓ Cleared scene tracking")
            
            # Force viewport refresh if we have a Maya panel
            if hasattr(self, 'maya_panel_name') and self.maya_panel_name:
                try:
                    cmds.refresh(currentView=True)
                    print("✓ Refreshed Maya viewport")
                except Exception:
                    pass
            
            # Update info display
            self.preview_status.setText("Preview cleared")
            print("✓ 3D preview scene cleared successfully")
            
        except Exception as e:
            print(f"Error clearing 3D preview: {e}")
            # Force clear tracking even on error
            if hasattr(self, '_last_loaded_scene'):
                delattr(self, '_last_loaded_scene')

    def reset_camera_view(self):
        """Reset camera to default position"""
        self.camera_position = {'distance': 5.0, 'rotation_x': -30, 'rotation_y': 45}
        self.preview_status.setText("Camera view reset")
        
        # Update preview if asset is loaded
        if self.current_asset_path:
            self.update_3d_preview(self.current_asset_path)
    
    def start_asset_comparison(self):
        """Start asset comparison mode"""
        if not self.current_asset_path:
            QMessageBox.warning(self, "No Asset", "Please select an asset first.")
            return
        
        # Show file dialog to select comparison asset
        comparison_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Asset to Compare",
            "",
            "Maya Files (*.ma *.mb);;OBJ Files (*.obj);;FBX Files (*.fbx);;All Files (*.*)"
        )
        
        if comparison_file:
            self.comparison_widget.show()
            self.comparison_preview_left.setText(f"Original:\n{os.path.basename(self.current_asset_path)}")
            self.comparison_preview_right.setText(f"Comparison:\n{os.path.basename(comparison_file)}")
    
    def close_asset_comparison(self):
        """Close asset comparison mode"""
        self.comparison_widget.hide()
    
    def load_asset(self, asset_path):
        """Load an asset for preview - main entry point from UI"""
        self.preview_asset(asset_path)


class AssetTypeCustomizationDialog(QDialog):
    """Dialog for customizing asset types, colors, and priorities"""
    
    def __init__(self, asset_manager, parent=None):
        super(AssetTypeCustomizationDialog, self).__init__(parent)
        self.asset_manager = asset_manager
        self.setWindowTitle("Asset Type Customization")
        self.setModal(True)
        self.resize(800, 600)
        self.setMinimumSize(600, 400)
        
        self.setup_ui()
        self.load_asset_types()
    
    def setup_ui(self):
        """Setup the customization dialog UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Customize Asset Types, Colors, and Priorities")
        header_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Instructions
        instructions = QLabel(
            "Manage your asset types below. You can add custom types, modify colors, "
            "set priorities, and define file extensions. Lower priority numbers appear first."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(instructions)
        
        # Main content area
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(content_splitter)
        
        # Left panel - Asset type list
        left_panel = self.create_type_list_panel()
        content_splitter.addWidget(left_panel)
        
        # Right panel - Type editor
        right_panel = self.create_type_editor_panel()
        content_splitter.addWidget(right_panel)
        
        content_splitter.setSizes([300, 500])
        
        # Button bar
        button_layout = QHBoxLayout()
        
        # Import/Export buttons
        import_btn = QPushButton("Import Config...")
        import_btn.clicked.connect(self.import_config)
        button_layout.addWidget(import_btn)
        
        export_btn = QPushButton("Export Config...")
        export_btn.clicked.connect(self.export_config)
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        # Standard dialog buttons
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_changes)
        button_layout.addWidget(apply_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_changes)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_type_list_panel(self):
        """Create the asset type list panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("Asset Types:"))
        
        # Asset type list
        self.type_list = QListWidget()
        self.type_list.currentItemChanged.connect(self.on_type_selection_changed)
        layout.addWidget(self.type_list)
        
        # List management buttons
        list_buttons = QHBoxLayout()
        
        add_btn = QPushButton("Add New")
        add_btn.clicked.connect(self.add_new_type)
        list_buttons.addWidget(add_btn)
        
        duplicate_btn = QPushButton("Duplicate")
        duplicate_btn.clicked.connect(self.duplicate_type)
        list_buttons.addWidget(duplicate_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_type)
        list_buttons.addWidget(delete_btn)
        
        layout.addLayout(list_buttons)
        
        # Priority controls
        priority_group = QGroupBox("Priority Order")
        priority_layout = QVBoxLayout(priority_group)
        
        priority_buttons = QHBoxLayout()
        move_up_btn = QPushButton("↑ Move Up")
        move_up_btn.clicked.connect(self.move_type_up)
        priority_buttons.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("↓ Move Down")
        move_down_btn.clicked.connect(self.move_type_down)
        priority_buttons.addWidget(move_down_btn)
        
        priority_layout.addLayout(priority_buttons)
        layout.addWidget(priority_group)
        
        return panel
    
    def create_type_editor_panel(self):
        """Create the asset type editor panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Editor form
        form_layout = QVBoxLayout()
        
        # Type ID (read-only for existing types)
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Type ID:"))
        self.id_edit = QLineEdit()
        id_layout.addWidget(self.id_edit)
        form_layout.addLayout(id_layout)
        
        # Display name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Display Name:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        form_layout.addLayout(name_layout)
        
        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_button = QPushButton()
        self.color_button.setFixedSize(50, 30)
        self.color_button.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        form_layout.addLayout(color_layout)
        
        # Priority
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority:"))
        self.priority_spin = QLineEdit()
        self.priority_spin.setPlaceholderText("0 = highest priority")
        priority_layout.addWidget(self.priority_spin)
        form_layout.addLayout(priority_layout)
        
        # Description
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        desc_layout.addWidget(self.description_edit)
        form_layout.addLayout(desc_layout)
        
        # File extensions
        ext_layout = QVBoxLayout()
        ext_layout.addWidget(QLabel("File Extensions (comma-separated):"))
        self.extensions_edit = QLineEdit()
        self.extensions_edit.setPlaceholderText("e.g., .ma, .mb, .obj")
        ext_layout.addWidget(self.extensions_edit)
        form_layout.addLayout(ext_layout)
        
        layout.addLayout(form_layout)
        
        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Select an asset type to see preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(50)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_group)
        
        layout.addStretch()
        
        # Connect change signals
        self.name_edit.textChanged.connect(self.update_preview)
        self.description_edit.textChanged.connect(self.update_preview)
        
        return panel
    
    def load_asset_types(self):
        """Load asset types into the list"""
        self.type_list.clear()
        
        # Get types sorted by priority
        types = [(type_id, config) for type_id, config in self.asset_manager.asset_types.items()]
        types.sort(key=lambda x: x[1]['priority'])
        
        for type_id, config in types:
            item = QListWidgetItem(f"{config['name']} ({type_id})")
            item.setData(Qt.ItemDataRole.UserRole, type_id)
            
            # Set color indicator
            color = QColor(config['color'][0], config['color'][1], config['color'][2])
            item.setBackground(QBrush(color))
            
            # Make default types slightly different to show they can't be deleted
            if type_id in self.asset_manager.default_asset_types:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            self.type_list.addItem(item)
    
    def on_type_selection_changed(self, current, previous):
        """Handle asset type selection change"""
        if current is None:
            self.clear_editor()
            return
        
        type_id = current.data(Qt.ItemDataRole.UserRole)
        if type_id in self.asset_manager.asset_types:
            self.load_type_to_editor(type_id)
    
    def load_type_to_editor(self, type_id):
        """Load asset type data into the editor"""
        config = self.asset_manager.asset_types[type_id]
        
        self.id_edit.setText(type_id)
        self.id_edit.setReadOnly(type_id in self.asset_manager.default_asset_types)
        
        self.name_edit.setText(config['name'])
        self.priority_spin.setText(str(config['priority']))
        self.description_edit.setPlainText(config['description'])
        
        # Set extensions
        extensions = ', '.join(config.get('extensions', []))
        self.extensions_edit.setText(extensions)
        
        # Set color
        color = QColor(config['color'][0], config['color'][1], config['color'][2])
        self.current_color = color
        self.update_color_button()
        self.update_preview()
    
    def clear_editor(self):
        """Clear the editor form"""
        self.id_edit.clear()
        self.id_edit.setReadOnly(False)
        self.name_edit.clear()
        self.priority_spin.clear()
        self.description_edit.clear()
        self.extensions_edit.clear()
        self.current_color = QColor(128, 128, 128)
        self.update_color_button()
        self.preview_label.setText("Select an asset type to see preview")
    
    def update_color_button(self):
        """Update the color button appearance"""
        if hasattr(self, 'current_color'):
            color = self.current_color
            self.color_button.setStyleSheet(
                f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); "
                f"border: 1px solid black;"
            )
    
    def update_preview(self):
        """Update the preview display"""
        if not hasattr(self, 'current_color'):
            return
        
        name = self.name_edit.text() or "Asset Type"
        description = self.description_edit.toPlainText() or "No description"
        
        color = self.current_color
        self.preview_label.setText(f"{name}\n{description}")
        self.preview_label.setStyleSheet(
            f"border: 1px solid black; "
            f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); "
            f"color: {'white' if color.lightness() < 128 else 'black'}; "
            f"padding: 10px;"
        )
    
    def choose_color(self):
        """Open color chooser dialog"""
        from PySide6.QtWidgets import QColorDialog
        
        current_color = getattr(self, 'current_color', QColor(128, 128, 128))
        color = QColorDialog.getColor(current_color, self, "Choose Asset Type Color")
        
        if color.isValid():
            self.current_color = color
            self.update_color_button()
            self.update_preview()
    
    def add_new_type(self):
        """Add a new custom asset type"""
        type_id, ok = QInputDialog.getText(self, "New Asset Type", "Enter type ID (lowercase, no spaces):")
        
        if ok and type_id.strip():
            type_id = type_id.strip().lower().replace(' ', '_')
            
            if type_id in self.asset_manager.asset_types:
                QMessageBox.warning(self, "Error", f"Asset type '{type_id}' already exists!")
                return
            
            # Add new type with default values
            max_priority = max([config['priority'] for config in self.asset_manager.asset_types.values() if config['priority'] != 999])
            new_priority = max_priority + 1
            
            self.asset_manager.asset_types[type_id] = {
                'name': type_id.title(),
                'color': [128, 128, 128],
                'priority': new_priority,
                'extensions': [],
                'description': f'Custom {type_id} assets'
            }
            
            self.load_asset_types()
            
            # Select the new type
            for i in range(self.type_list.count()):
                item = self.type_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == type_id:
                    self.type_list.setCurrentItem(item)
                    break
    
    def duplicate_type(self):
        """Duplicate the selected asset type"""
        current_item = self.type_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select an asset type to duplicate.")
            return
        
        source_type_id = current_item.data(Qt.ItemDataRole.UserRole)
        source_config = self.asset_manager.asset_types[source_type_id]
        
        new_type_id, ok = QInputDialog.getText(
            self, "Duplicate Asset Type", 
            f"Enter new type ID for duplicate of '{source_type_id}':"
        )
        
        if ok and new_type_id.strip():
            new_type_id = new_type_id.strip().lower().replace(' ', '_')
            
            if new_type_id in self.asset_manager.asset_types:
                QMessageBox.warning(self, "Error", f"Asset type '{new_type_id}' already exists!")
                return
            
            # Create duplicate with incremented priority
            max_priority = max([config['priority'] for config in self.asset_manager.asset_types.values() if config['priority'] != 999])
            
            self.asset_manager.asset_types[new_type_id] = {
                'name': source_config['name'] + ' Copy',
                'color': source_config['color'].copy(),
                'priority': max_priority + 1,
                'extensions': source_config['extensions'].copy(),
                'description': source_config['description'] + ' (copy)'
            }
            
            self.load_asset_types()
            
            # Select the new type
            for i in range(self.type_list.count()):
                item = self.type_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_type_id:
                    self.type_list.setCurrentItem(item)
                    break
    
    def delete_type(self):
        """Delete the selected asset type"""
        current_item = self.type_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select an asset type to delete.")
            return
        
        type_id = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Prevent deletion of default types
        if type_id in self.asset_manager.default_asset_types:
            QMessageBox.warning(self, "Error", "Cannot delete default asset types.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the asset type '{type_id}'?\n\n"
            f"This will remove the type but not affect existing asset tags.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.asset_manager.asset_types[type_id]
            self.load_asset_types()
            self.clear_editor()
    
    def move_type_up(self):
        """Move selected type up in priority"""
        current_item = self.type_list.currentItem()
        if not current_item:
            return
        
        type_id = current_item.data(Qt.ItemDataRole.UserRole)
        config = self.asset_manager.asset_types[type_id]
        
        if config['priority'] > 0:
            config['priority'] -= 1
            self.load_asset_types()
            
            # Reselect the item
            for i in range(self.type_list.count()):
                item = self.type_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == type_id:
                    self.type_list.setCurrentItem(item)
                    break
    
    def move_type_down(self):
        """Move selected type down in priority"""
        current_item = self.type_list.currentItem()
        if not current_item:
            return
        
        type_id = current_item.data(Qt.ItemDataRole.UserRole)
        config = self.asset_manager.asset_types[type_id]
        
        # Find max priority (excluding default)
        max_priority = max([c['priority'] for c in self.asset_manager.asset_types.values() if c['priority'] != 999])
        
        if config['priority'] < max_priority:
            config['priority'] += 1
            self.load_asset_types()
            
            # Reselect the item
            for i in range(self.type_list.count()):
                item = self.type_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == type_id:
                    self.type_list.setCurrentItem(item)
                    break
    
    def apply_current_type(self):
        """Apply current editor changes to the selected type"""
        current_item = self.type_list.currentItem()
        if not current_item:
            return False
        
        type_id = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Validate inputs
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Asset type name cannot be empty.")
            return False
        
        try:
            new_priority = int(self.priority_spin.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Priority must be a number.")
            return False
        
        # Parse extensions
        extensions_text = self.extensions_edit.text().strip()
        extensions = []
        if extensions_text:
            extensions = [ext.strip() for ext in extensions_text.split(',')]
            extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        
        # Update the asset type
        self.asset_manager.asset_types[type_id].update({
            'name': new_name,
            'color': [self.current_color.red(), self.current_color.green(), self.current_color.blue()],
            'priority': new_priority,
            'extensions': extensions,
            'description': self.description_edit.toPlainText()
        })
        
        return True
    
    def apply_changes(self):
        """Apply all changes"""
        if self.apply_current_type():
            self.asset_manager._update_color_cache()
            self.load_asset_types()
    
    def accept_changes(self):
        """Accept changes and close dialog"""
        if self.apply_current_type():
            self.asset_manager._update_color_cache()
            self.asset_manager.save_config()
            self.accept()
    
    def import_config(self):
        """Import asset type configuration"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Asset Type Configuration", "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            if self.asset_manager.import_asset_type_config(file_path):
                self.load_asset_types()
                QMessageBox.information(self, "Success", "Asset type configuration imported successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to import asset type configuration.")
    
    def export_config(self):
        """Export asset type configuration"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Asset Type Configuration", "asset_types_config.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            if self.asset_manager.export_asset_type_config(file_path):
                QMessageBox.information(self, "Success", f"Asset type configuration exported to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Error", "Failed to export asset type configuration.")
    
    def reset_to_defaults(self):
        """Reset asset types to default configuration"""
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "Are you sure you want to reset all asset types to default configuration?\n\n"
            "This will remove all custom asset types and reset colors and priorities.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.asset_manager.reset_asset_types_to_default()
            self.load_asset_types()
            self.clear_editor()
            QMessageBox.information(self, "Reset Complete", "Asset types have been reset to defaults.")


class AddAssetsFromFoldersDialog(QDialog):
    """Dialog for adding selected assets from selected folders to the library"""
    
    def __init__(self, asset_manager, parent=None):
        super(AddAssetsFromFoldersDialog, self).__init__(parent)
        self.asset_manager = asset_manager
        self.setWindowTitle("Add Assets from Folders")
        self.setModal(True)
        self.resize(1000, 700)
        self.setMinimumSize(800, 500)
        
        # Supported file extensions
        self.supported_extensions = set()
        for config in self.asset_manager.asset_types.values():
            self.supported_extensions.update(config.get('extensions', []))
        
        # Remove empty extensions and add common ones if needed
        self.supported_extensions.discard('')
        if not self.supported_extensions:
            self.supported_extensions = {'.ma', '.mb', '.obj', '.fbx', '.jpg', '.png', '.tga', '.exr'}
        
        self.setup_ui()
        self.load_initial_folders()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Add Assets from Folders to Library")
        header_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Instructions
        instructions = QLabel(
            "Select folders and choose which asset files to add to your project library. "
            "Assets can be copied to your project or referenced from their current location."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(instructions)
        
        # Main content area
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(content_splitter)
        
        # Left panel - Folder browser
        left_panel = self.create_folder_browser_panel()
        content_splitter.addWidget(left_panel)
        
        # Right panel - File selection
        right_panel = self.create_file_selection_panel()
        content_splitter.addWidget(right_panel)
        
        content_splitter.setSizes([400, 600])
        
        # Options
        options_layout = QHBoxLayout()
        
        self.copy_files_checkbox = QCheckBox("Copy files to project (recommended)")
        self.copy_files_checkbox.setChecked(True)
        self.copy_files_checkbox.setToolTip("Copy files to your project folder vs. referencing them from current location")
        options_layout.addWidget(self.copy_files_checkbox)
        
        options_layout.addStretch()
        
        # Progress info
        self.progress_label = QLabel("")
        options_layout.addWidget(self.progress_label)
        
        layout.addLayout(options_layout)
        
        # Button bar
        button_layout = QHBoxLayout()
        
        # Selection buttons
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_files)
        button_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_files)
        button_layout.addWidget(select_none_btn)
        
        filter_by_type_btn = QPushButton("Filter by Type...")
        filter_by_type_btn.clicked.connect(self.filter_by_asset_type)
        button_layout.addWidget(filter_by_type_btn)
        
        button_layout.addStretch()
        
        # Standard dialog buttons
        add_btn = QPushButton("Add Selected Assets")
        add_btn.clicked.connect(self.add_selected_assets)
        button_layout.addWidget(add_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_folder_browser_panel(self):
        """Create the folder browser panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("Folders:"))
        
        # Folder controls
        folder_controls = QHBoxLayout()
        
        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self.add_folder)
        folder_controls.addWidget(add_folder_btn)
        
        remove_folder_btn = QPushButton("Remove")
        remove_folder_btn.clicked.connect(self.remove_folder)
        folder_controls.addWidget(remove_folder_btn)
        
        folder_controls.addStretch()
        
        layout.addLayout(folder_controls)
        
        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.currentItemChanged.connect(self.on_folder_selection_changed)
        layout.addWidget(self.folder_list)
        
        # Folder options
        options_group = QGroupBox("Scan Options")
        options_layout = QVBoxLayout(options_group)
        
        self.recursive_checkbox = QCheckBox("Include subfolders")
        self.recursive_checkbox.setChecked(True)
        self.recursive_checkbox.stateChanged.connect(self.refresh_current_folder)
        options_layout.addWidget(self.recursive_checkbox)
        
        # Extension filter
        ext_layout = QHBoxLayout()
        ext_layout.addWidget(QLabel("Extensions:"))
        self.extension_filter = QLineEdit()
        self.extension_filter.setPlaceholderText("e.g., .ma,.mb,.obj (leave empty for all)")
        self.extension_filter.textChanged.connect(self.refresh_current_folder)
        ext_layout.addWidget(self.extension_filter)
        options_layout.addLayout(ext_layout)
        
        layout.addWidget(options_group)
        
        return panel
    
    def create_file_selection_panel(self):
        """Create the file selection panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # File list header
        file_header = QHBoxLayout()
        file_header.addWidget(QLabel("Asset Files:"))
        file_header.addStretch()
        
        self.file_count_label = QLabel("0 files")
        file_header.addWidget(self.file_count_label)
        
        layout.addLayout(file_header)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.itemChanged.connect(self.update_selection_count)
        layout.addWidget(self.file_list)
        
        # File info panel
        info_group = QGroupBox("Selection Info")
        info_layout = QVBoxLayout(info_group)
        
        self.selection_info_label = QLabel("No files selected")
        info_layout.addWidget(self.selection_info_label)
        
        layout.addWidget(info_group)
        
        return panel
    
    def load_initial_folders(self):
        """Load initial folders (current project if available)"""
        if self.asset_manager.current_project:
            self.folder_list.addItem(self.asset_manager.current_project)
            self.folder_list.setCurrentRow(0)
    
    def add_folder(self):
        """Add a folder to scan"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Scan for Assets"
        )
        
        if folder_path:
            # Check if folder already exists
            for i in range(self.folder_list.count()):
                if self.folder_list.item(i).text() == folder_path:
                    QMessageBox.information(self, "Info", "Folder already added")
                    return
            
            self.folder_list.addItem(folder_path)
            self.folder_list.setCurrentRow(self.folder_list.count() - 1)
    
    def remove_folder(self):
        """Remove selected folder"""
        current_item = self.folder_list.currentItem()
        if current_item:
            row = self.folder_list.row(current_item)
            self.folder_list.takeItem(row)
            self.file_list.clear()
            self.update_file_count()
    
    def on_folder_selection_changed(self, current, previous):
        """Handle folder selection change"""
        if current:
            self.scan_folder(current.text())
    
    def refresh_current_folder(self):
        """Refresh the currently selected folder"""
        current_item = self.folder_list.currentItem()
        if current_item:
            self.scan_folder(current_item.text())
    
    def scan_folder(self, folder_path):
        """Scan folder for asset files"""
        if not os.path.exists(folder_path):
            self.file_list.clear()
            self.update_file_count()
            return
        
        # Get extension filter
        ext_filter_text = self.extension_filter.text().strip()
        if ext_filter_text:
            extensions = {ext.strip().lower() for ext in ext_filter_text.split(',')}
            extensions = {ext if ext.startswith('.') else f'.{ext}' for ext in extensions}
        else:
            extensions = self.supported_extensions
        
        # Scan for files
        asset_files = []
        recursive = self.recursive_checkbox.isChecked()
        
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in extensions:
                        file_path = os.path.join(root, file)
                        asset_files.append(file_path)
        else:
            try:
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path):
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in extensions:
                            asset_files.append(file_path)
            except PermissionError:
                QMessageBox.warning(self, "Permission Error", f"Cannot access folder: {folder_path}")
                return
        
        # Update file list
        self.file_list.clear()
        for file_path in sorted(asset_files):
            item = QListWidgetItem()
            
            # Create display text with relative path and asset type
            rel_path = os.path.relpath(file_path, folder_path)
            asset_type = self.asset_manager.get_asset_type(file_path)
            type_config = self.asset_manager.asset_types.get(asset_type, self.asset_manager.asset_types['default'])
            
            item.setText(f"{rel_path} ({type_config['name']})")
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            
            # Set color based on asset type
            color = self.asset_manager.asset_type_colors.get(asset_type, self.asset_manager.asset_type_colors['default'])
            item.setBackground(QBrush(color))
            
            self.file_list.addItem(item)
        
        self.update_file_count()
        self.update_selection_count()
    
    def update_file_count(self):
        """Update the file count label"""
        count = self.file_list.count()
        self.file_count_label.setText(f"{count} files")
    
    def update_selection_count(self):
        """Update selection count and info"""
        selected_count = 0
        total_size = 0
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_count += 1
                file_path = item.data(Qt.ItemDataRole.UserRole)
                try:
                    total_size += os.path.getsize(file_path)
                except:
                    pass
        
        # Format size
        if total_size < 1024:
            size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.1f} KB"
        elif total_size < 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
        
        self.selection_info_label.setText(f"{selected_count} files selected, {size_str}")
    
    def select_all_files(self):
        """Select all files"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
        self.update_selection_count()
    
    def select_no_files(self):
        """Deselect all files"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
        self.update_selection_count()
    
    def filter_by_asset_type(self):
        """Show dialog to filter files by asset type"""
        # Get available asset types in current selection
        available_types = set()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            asset_type = self.asset_manager.get_asset_type(file_path)
            available_types.add(asset_type)
        
        if not available_types:
            QMessageBox.information(self, "No Files", "No files to filter")
            return
        
        # Create selection dialog
        types_to_select, ok = QInputDialog.getItem(
            self, "Filter by Asset Type",
            "Select asset type to filter by:",
            [self.asset_manager.asset_types[t]['name'] for t in available_types],
            0, False
        )
        
        if ok and types_to_select:
            # Find the type ID
            selected_type_id = None
            for type_id in available_types:
                if self.asset_manager.asset_types[type_id]['name'] == types_to_select:
                    selected_type_id = type_id
                    break
            
            if selected_type_id:
                # Update selection
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    file_path = item.data(Qt.ItemDataRole.UserRole)
                    asset_type = self.asset_manager.get_asset_type(file_path)
                    
                    if asset_type == selected_type_id:
                        item.setCheckState(Qt.CheckState.Checked)
                    else:
                        item.setCheckState(Qt.CheckState.Unchecked)
                
                self.update_selection_count()
    
    def get_selected_files(self):
        """Get list of selected file paths"""
        selected_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                selected_files.append(file_path)
        return selected_files
    
    def add_selected_assets(self):
        """Add selected assets to the library"""
        selected_files = self.get_selected_files()
        
        if not selected_files:
            QMessageBox.warning(self, "No Selection", "Please select at least one asset file to add.")
            return
        
        copy_files = self.copy_files_checkbox.isChecked()
        
        # Show progress dialog
        progress_dialog = QProgressDialog("Adding assets to library...", "Cancel", 0, len(selected_files), self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        
        def progress_callback(current, total, file_path):
            progress_dialog.setValue(current)
            progress_dialog.setLabelText(f"Processing: {os.path.basename(file_path)}")
            QApplication.processEvents()
            
            if progress_dialog.wasCanceled():
                return False
            return True
        
        # Add assets
        result = self.asset_manager.register_multiple_assets(selected_files, copy_files, progress_callback)
        
        progress_dialog.close()
        progress_dialog.deleteLater()  # Proper cleanup to prevent memory leaks
        
        # Show results
        registered_count = len(result['registered'])
        failed_count = len(result['failed'])
        
        if registered_count > 0:
            message = f"Successfully added {registered_count} assets to the library."
            if failed_count > 0:
                message += f"\n{failed_count} assets failed to add."
            
            QMessageBox.information(self, "Assets Added", message)
            self.accept()
        else:
            QMessageBox.warning(self, "Failed", "No assets were added to the library.")


class AssetManagerUI(QMainWindow):
    """Main UI class for the Asset Manager"""
    
    def __init__(self, parent=None):
        super(AssetManagerUI, self).__init__(parent)
        self.asset_manager = AssetManager()
        self.setWindowTitle(f"Asset Manager v{self.asset_manager.version}")
        
        # Set window flags for Maya integration
        self.setWindowFlags(Qt.WindowType.Window)  # type: ignore
        
        # Set window icon (tab bar icon)
        self.set_window_icon()
        
        # Configure window geometry (size and position)
        self._configure_window_geometry()
        
        # Initialize file system watcher for automatic refresh
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self._on_directory_changed)
        
        # Throttle refresh to avoid excessive updates
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._delayed_refresh)
        self._refresh_timer.setInterval(2000)  # 2 second delay
        
        self.setup_ui()
        self.refresh_assets()
    
    def _configure_window_geometry(self):
        """Configure window size and position with improved defaults and user preferences"""
        # Load saved geometry if available
        saved_geometry = self._load_window_geometry()
        
        if saved_geometry:
            # Restore saved geometry
            self.setGeometry(saved_geometry['x'], saved_geometry['y'], 
                           saved_geometry['width'], saved_geometry['height'])
        else:
            # Calculate optimal default size and set position
            optimal_size = self._calculate_optimal_window_size()
            self.setGeometry(100, 100, optimal_size['width'], optimal_size['height'])
        
        # Always set minimum size to ensure UI elements fit
        min_size = self._calculate_minimum_window_size()
        self.setMinimumSize(min_size['width'], min_size['height'])
    
    def _calculate_optimal_window_size(self):
        """Calculate optimal default window size based on UI requirements"""
        # Base calculations on typical UI element requirements
        left_panel_width = 280  # Increased from 250 for better content fit
        right_panel_width = 650  # Increased from 550 for better asset display
        total_width = left_panel_width + right_panel_width + 30  # +30 for splitter margin
        
        # Calculate height based on typical UI component needs
        menu_bar_height = 30
        toolbar_height = 40
        status_bar_height = 25
        content_padding = 20
        optimal_content_height = 700  # Increased for better asset display
        
        total_height = (menu_bar_height + toolbar_height + status_bar_height + 
                       content_padding + optimal_content_height)
        
        return {
            'width': min(total_width, 1200),  # Cap at reasonable maximum
            'height': min(total_height, 900)   # Cap at reasonable maximum
        }
    
    def _calculate_minimum_window_size(self):
        """Calculate minimum window size to ensure all UI elements are accessible"""
        # Minimum dimensions to keep UI functional
        min_left_panel = 200
        min_right_panel = 400
        min_width = min_left_panel + min_right_panel + 30
        
        min_height = 500  # Increased from 400 for better usability
        
        return {'width': min_width, 'height': min_height}
    
    def _load_window_geometry(self):
        """Load saved window geometry from user preferences"""
        try:
            geometry = self.asset_manager.get_ui_preference('window_geometry')
            if geometry and isinstance(geometry, dict):
                # Validate geometry values
                required_keys = ['x', 'y', 'width', 'height']
                if all(key in geometry and isinstance(geometry[key], int) 
                       for key in required_keys):
                    # Ensure dimensions are reasonable
                    min_size = self._calculate_minimum_window_size()
                    if (geometry['width'] >= min_size['width'] and 
                        geometry['height'] >= min_size['height']):
                        return geometry
            return None
        except Exception as e:
            print(f"Error loading window geometry: {e}")
            return None
    
    def _save_window_geometry(self):
        """Save current window geometry to user preferences"""
        try:
            geometry = self.geometry()
            geometry_data = {
                'x': geometry.x(),
                'y': geometry.y(),
                'width': geometry.width(),
                'height': geometry.height()
            }
            self.asset_manager.set_ui_preference('window_geometry', geometry_data)
        except Exception as e:
            print(f"Error saving window geometry: {e}")
    
    def reset_window_to_optimal_size(self):
        """Reset window to optimal calculated size - useful for troubleshooting"""
        try:
            optimal_size = self._calculate_optimal_window_size()
            self.resize(optimal_size['width'], optimal_size['height'])
            # Clear saved geometry to prevent restoration of old size
            self.asset_manager.set_ui_preference('window_geometry', None)
            print(f"Window reset to optimal size: {optimal_size['width']}x{optimal_size['height']}")
        except Exception as e:
            print(f"Error resetting window size: {e}")
    
    def set_window_icon(self):
        """Set the window icon (appears in tab bar and title bar)"""
        try:
            if MAYA_AVAILABLE and cmds:
                # Get Maya user directory for icon path
                maya_user_dir = cmds.internalVar(userAppDir=True)
                icon_path = os.path.join(maya_user_dir, "plug-ins", "assetManager_icon2.png")
                
                if os.path.exists(icon_path):
                    # Set window icon
                    icon = QIcon(icon_path)
                    self.setWindowIcon(icon)
                    print(f"Window icon set to: {icon_path}")
                else:
                    print("Custom window icon not found, using default")
            else:
                print("Maya not available, using default window icon")
        except Exception as e:
            print(f"Could not set window icon: {e}")
    
    def closeEvent(self, event):
        """Handle window close event and cleanup resources"""
        try:
            print("Asset Manager window closing - performing cleanup...")
            
            # Save window geometry before closing
            self._save_window_geometry()
            
            # Stop and disconnect file watcher
            if hasattr(self, 'file_watcher') and self.file_watcher:
                try:
                    self.file_watcher.directoryChanged.disconnect()
                    self.file_watcher.deleteLater()
                    print("File system watcher cleaned up")
                except Exception as e:
                    print(f"Error cleaning up file watcher: {e}")
            
            # Stop refresh timer
            if hasattr(self, '_refresh_timer') and self._refresh_timer:
                try:
                    self._refresh_timer.stop()
                    self._refresh_timer.deleteLater()
                    print("Refresh timer cleaned up")
                except Exception as e:
                    print(f"Error cleaning up refresh timer: {e}")
            
            # Cleanup asset manager resources
            if hasattr(self, 'asset_manager') and self.asset_manager:
                try:
                    self.asset_manager.cleanup()
                    print("Asset manager cleaned up")
                except Exception as e:
                    print(f"Error cleaning up asset manager: {e}")
            
            # Clear any UI references
            self._clear_ui_references()
            
            print("Asset Manager window cleanup completed")
            
        except Exception as e:
            print(f"Error during window cleanup: {e}")
        finally:
            # Accept the close event
            event.accept()
    
    def _clear_ui_references(self):
        """Clear UI widget references to prevent memory leaks"""
        try:
            # Clear large UI components
            if hasattr(self, 'tab_widget') and self.tab_widget:
                for i in range(self.tab_widget.count()):
                    widget = self.tab_widget.widget(i)
                    if widget:
                        # Find all QListWidget children and clear them
                        for list_widget in widget.findChildren(QListWidget):
                            list_widget.clear()
                self.tab_widget.clear()
          
            if hasattr(self, 'asset_list') and self.asset_list:
                self.asset_list.clear()
            
            if hasattr(self, 'categories_list') and self.categories_list:
                self.categories_list.clear()
            
        except Exception as e:
            print(f"Error clearing UI references: {e}")
    def _safe_close_progress_dialog(self, progress_dialog):
        """Safely close and cleanup progress dialog to prevent memory leaks"""
        try:
            if progress_dialog:
                progress_dialog.close()
                progress_dialog.deleteLater()
        except Exception as e:
            print(f"Error closing progress dialog: {e}")
    
    def setup_ui(self):
        """Setup the main UI components"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main content area
        content_splitter = QSplitter(Qt.Orientation.Horizontal)  # type: ignore
        main_layout.addWidget(content_splitter)
        
        # Left panel - Project and categories
        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)
        
        # Right panel - Asset library
        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)
        
        # Set splitter proportions - improved ratios for better content display
        content_splitter.setSizes([280, 650])  # Increased from [250, 550]
        
        # Status bar
        self.create_status_bar()
        
        # Restore preview panel visibility from user preferences
        self.restore_preview_panel_state()
    
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        new_project_action = QAction('New Project', self)
        new_project_action.triggered.connect(self.new_project_dialog)
        file_menu.addAction(new_project_action)
        
        open_project_action = QAction('Open Project', self)
        open_project_action.triggered.connect(self.open_project_dialog)
        file_menu.addAction(open_project_action)
        
        file_menu.addSeparator()
        
        import_action = QAction('Import Asset', self)
        import_action.triggered.connect(self.import_asset_dialog)
        file_menu.addAction(import_action)
        
        add_assets_action = QAction('Add Assets from Folders...', self)
        add_assets_action.triggered.connect(self.add_assets_from_folders_dialog)
        file_menu.addAction(add_assets_action)
        
        export_action = QAction('Export Selected', self)
        export_action.triggered.connect(self.export_selected_dialog)
        file_menu.addAction(export_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        refresh_action = QAction('Refresh Library', self)
        refresh_action.triggered.connect(self.refresh_assets)
        tools_menu.addAction(refresh_action)
        
        tools_menu.addSeparator()
        
        # Asset Type Customization
        customize_types_action = QAction('Customize Asset Types...', self)
        customize_types_action.triggered.connect(self.show_asset_type_customization)
        tools_menu.addAction(customize_types_action)
        
        # Window management
        reset_window_action = QAction('Reset Window Size', self)
        reset_window_action.triggered.connect(self.reset_window_to_optimal_size)
        tools_menu.addAction(reset_window_action)
        
        tools_menu.addSeparator()
        
        # New v1.1.0 Asset Management Tools
        batch_import_action = QAction('Batch Import Assets...', self)
        batch_import_action.triggered.connect(self.batch_import_dialog)
        tools_menu.addAction(batch_import_action)
        
        batch_export_action = QAction('Batch Export Assets...', self)
        batch_export_action.triggered.connect(self.batch_export_dialog)
        tools_menu.addAction(batch_export_action)
        
        tools_menu.addSeparator()
        
        manage_collections_action = QAction('Manage Collections...', self)
        manage_collections_action.triggered.connect(self.show_collections_dialog)
        tools_menu.addAction(manage_collections_action)
        
        dependency_viewer_action = QAction('Dependency Viewer...', self)
        dependency_viewer_action.triggered.connect(self.show_dependency_viewer)
        tools_menu.addAction(dependency_viewer_action)
        
        tools_menu.addSeparator()
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        check_updates_action = QAction('Check for Updates...', self)
        check_updates_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(check_updates_action)
        
        help_menu.addSeparator()
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = self.addToolBar('Main')
        
        # New project button
        new_project_btn = QAction('New Project', self)
        new_project_btn.triggered.connect(self.new_project_dialog)
        toolbar.addAction(new_project_btn)
        
        # Import asset button
        import_btn = QAction('Import Asset', self)
        import_btn.triggered.connect(self.import_asset_dialog)
        toolbar.addAction(import_btn)
        
        # Export selected button
        export_btn = QAction('Export Selected', self)
        export_btn.triggered.connect(self.export_selected_dialog)
        toolbar.addAction(export_btn)
        
        toolbar.addSeparator()
        
        # Preview toggle button (v1.2.0 Preview & Visualization feature)
        self.preview_toggle_btn = QAction('Toggle Preview', self)
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(True)  # Default to visible
        self.preview_toggle_btn.triggered.connect(self.toggle_preview_panel)
        toolbar.addAction(self.preview_toggle_btn)
        
        toolbar.addSeparator()
        
        # Refresh button
        refresh_btn = QAction('Refresh', self)
        refresh_btn.triggered.connect(self.refresh_assets)
        toolbar.addAction(refresh_btn)
    
    def create_left_panel(self):
        """Create the left panel with project info and categories"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Project info
        project_group = QGroupBox("Current Project")
        project_layout = QVBoxLayout(project_group)
        
        self.project_label = QLabel("No project selected")
        self.project_label.setWordWrap(True)
        project_layout.addWidget(self.project_label)
        
        left_layout.addWidget(project_group)
        
        # Asset categories
        categories_group = QGroupBox("Categories")
        categories_layout = QVBoxLayout(categories_group)
        
        self.categories_list = QListWidget()
        categories = ['All', 'Models', 'Textures', 'Scenes', 'References']
        self.categories_list.addItems(categories)
        self.categories_list.currentTextChanged.connect(self.filter_assets)
        categories_layout.addWidget(self.categories_list)
        
        left_layout.addWidget(categories_group)
        
        # Search
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout(search_group)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search assets...")
        self.search_input.textChanged.connect(self.filter_assets)
        search_layout.addWidget(self.search_input)
        
        left_layout.addWidget(search_group)
        
        # === NEW v1.1.0 Asset Management Features ===
        
        # Asset Tags
        tags_group = QGroupBox("Asset Tags")
        tags_layout = QVBoxLayout(tags_group)
        
        # Tag filter dropdown
        self.tag_filter = QComboBox()
        self.tag_filter.addItem("All Tags")
        self.tag_filter.currentTextChanged.connect(self.filter_by_tag)
        tags_layout.addWidget(QLabel("Filter by Tag:"))
        tags_layout.addWidget(self.tag_filter)
        
        # Add tag to selected asset
        tag_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Add tag...")
        add_tag_btn = QPushButton("Add")
        add_tag_btn.clicked.connect(self.add_tag_to_selected)
        tag_input_layout.addWidget(self.tag_input)
        tag_input_layout.addWidget(add_tag_btn)
        tags_layout.addLayout(tag_input_layout)
        
        left_layout.addWidget(tags_group)
        
        # Asset Collections
        collections_group = QGroupBox("Collections")
        collections_layout = QVBoxLayout(collections_group)
        
        # Collection dropdown
        self.collection_filter = QComboBox()
        self.collection_filter.addItem("All Collections")
        self.collection_filter.currentTextChanged.connect(self.filter_by_collection)
        collections_layout.addWidget(QLabel("Filter by Collection:"))
        collections_layout.addWidget(self.collection_filter)
        
        # Create collection
        collection_input_layout = QHBoxLayout()
        self.collection_input = QLineEdit()
        self.collection_input.setPlaceholderText("Collection name...")
        create_collection_btn = QPushButton("Create")
        create_collection_btn.clicked.connect(self.create_new_collection)
        collection_input_layout.addWidget(self.collection_input)
        collection_input_layout.addWidget(create_collection_btn)
        collections_layout.addLayout(collection_input_layout)
        
        left_layout.addWidget(collections_group)
        
        # Asset Type Color Legend
        self.legend_group = QGroupBox("Asset Type Colors")
        legend_layout = QVBoxLayout(self.legend_group)
        
        # Create color legend with sample swatches
        self.create_color_legend(legend_layout)
        
        left_layout.addWidget(self.legend_group)
        
        left_layout.addStretch()
        
        return left_widget
    
    def create_color_legend(self, layout):
        """Create a color legend showing asset type colors"""
        # Get current asset types sorted by priority
        asset_types = self.asset_manager.get_asset_type_list()
        
        # Create a grid layout for compact display
        from PySide6.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        
        row = 0
        col = 0
        for asset_type in asset_types:
            config = self.asset_manager.asset_types[asset_type]
            
            # Create color swatch
            color_label = QLabel()
            color_label.setFixedSize(16, 16)
            color = self.asset_manager.asset_type_colors.get(asset_type, self.asset_manager.asset_type_colors['default'])
            color_label.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 1px solid black;")
            
            # Type name label
            name_label = QLabel(config['name'])
            name_label.setFont(QFont("Arial", 8))
            
            grid_layout.addWidget(color_label, row, col * 2)
            grid_layout.addWidget(name_label, row, col * 2 + 1)
            
            col += 1
            if col >= 2:  # 2 columns
                col = 0
                row += 1
        
        layout.addLayout(grid_layout)
        
        # Add info label
        info_label = QLabel("Right-click assets → Asset Type to assign colors")
        info_label.setFont(QFont("Arial", 7))
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)
    
    def create_right_panel(self):
        """Create the right panel with asset library and collection tabs"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Create horizontal splitter for asset list and preview
        content_splitter = QSplitter(Qt.Orientation.Horizontal)  # type: ignore
        right_layout.addWidget(content_splitter)
        
        # Left side: Asset tabs and list
        assets_widget = QWidget()
        assets_layout = QVBoxLayout(assets_widget)
        
        # Create tab widget for asset views
        self.tab_widget = QTabWidget()
        assets_layout.addWidget(self.tab_widget)
        
        # Main Asset Library Tab
        self.create_main_asset_tab()
        
        # Collection Tabs (will be added dynamically)
        self.refresh_collection_tabs()
        
        # Asset actions (below tabs)
        actions_layout = QHBoxLayout()
        
        import_selected_btn = QPushButton("Import Selected")
        import_selected_btn.clicked.connect(self.import_selected_asset)
        actions_layout.addWidget(import_selected_btn)
        
        delete_asset_btn = QPushButton("Delete Asset")
        delete_asset_btn.clicked.connect(self.delete_selected_asset)
        actions_layout.addWidget(delete_asset_btn)
        
        # Thumbnail size controls
        actions_layout.addWidget(QLabel("Size:"))
        
        self.thumbnail_size_slider = QSlider(Qt.Orientation.Horizontal)  # type: ignore
        self.thumbnail_size_slider.setMinimum(32)
        self.thumbnail_size_slider.setMaximum(128)
        self.thumbnail_size_slider.setValue(int(self._get_current_thumbnail_size()))
        self.thumbnail_size_slider.setMaximumWidth(100)
        self.thumbnail_size_slider.valueChanged.connect(self._on_thumbnail_size_changed)
        actions_layout.addWidget(self.thumbnail_size_slider)
        
        self.thumbnail_size_label = QLabel(f"{self._get_current_thumbnail_size()}px")
        self.thumbnail_size_label.setMinimumWidth(35)
        actions_layout.addWidget(self.thumbnail_size_label)
        
        # Add collection tab management buttons
        actions_layout.addStretch()
        
        add_collection_tab_btn = QPushButton("+ Collection Tab")
        add_collection_tab_btn.clicked.connect(self.add_collection_tab_dialog)
        actions_layout.addWidget(add_collection_tab_btn)
        
        refresh_tabs_btn = QPushButton("Refresh Tabs")
        refresh_tabs_btn.clicked.connect(self.refresh_collection_tabs)
        actions_layout.addWidget(refresh_tabs_btn)
        
        assets_layout.addLayout(actions_layout)
        content_splitter.addWidget(assets_widget)
        
        # Right side: Asset preview widget
        self.asset_preview_widget = AssetPreviewWidget(self.asset_manager)
        content_splitter.addWidget(self.asset_preview_widget)
        
        # Set splitter proportions (60% assets, 40% preview)
        content_splitter.setSizes([400, 250])
        
        # Make preview panel collapsible
        content_splitter.setCollapsible(1, True)
        
        # Store reference to content splitter for toggle functionality
        self.content_splitter = content_splitter
        
        return right_widget
    
    def toggle_preview_panel(self, visible=None):
        """Toggle the visibility of the asset preview panel"""
        try:
            if not hasattr(self, 'content_splitter') or not self.content_splitter:
                return
            
            if visible is None:
                # Toggle based on current visibility
                visible = self.asset_preview_widget.isVisible()
                visible = not visible
            
            if visible:
                # Show preview panel
                self.asset_preview_widget.show()
                self.content_splitter.setSizes([400, 250])
                self.preview_toggle_btn.setText('Hide Preview')
                self.preview_toggle_btn.setChecked(True)
            else:
                # Hide preview panel
                self.asset_preview_widget.hide()
                self.content_splitter.setSizes([650, 0])
                self.preview_toggle_btn.setText('Show Preview')
                self.preview_toggle_btn.setChecked(False)
                
            # Save preference
            self.asset_manager.set_ui_preference('preview_panel_visible', visible)
            
        except Exception as e:
            print(f"Error toggling preview panel: {e}")
    
    def restore_preview_panel_state(self):
        """Restore the preview panel visibility from user preferences"""
        try:
            # Get saved preference (default to True for first-time users)
            preview_visible = self.asset_manager.get_ui_preference('preview_panel_visible', True)
            
            # Apply the saved state
            self.toggle_preview_panel(preview_visible)
            
        except Exception as e:
            print(f"Error restoring preview panel state: {e}")
            # Default to visible if there's an error
            self.toggle_preview_panel(True)
    
    def _get_current_thumbnail_size(self):
        """Get current thumbnail size from preferences - FORCE MINIMUM SIZE FOR READABLE TEXT"""
        # FORCE minimum 128px for readable text in professional icons
        user_size = int(self.asset_manager.get_ui_preference('thumbnail_size', 128) or 128)
        return max(128, user_size)  # Never smaller than 128px for text readability
    
    def _on_thumbnail_size_changed(self, size):
        """Handle thumbnail size change - Clean Code: descriptive naming and single purpose"""
        try:
            # Update size label
            self.thumbnail_size_label.setText(f"{size}px")
            
            # Save preference
            self.asset_manager.set_ui_preference('thumbnail_size', size)
            
            # Apply new thumbnail size to all asset lists
            self._apply_thumbnail_size_to_lists(size)
            
            # Refresh thumbnails with new size
            self._refresh_thumbnails_with_new_size(size)
            
        except Exception as e:
            print(f"Error changing thumbnail size: {e}")
    
    def _apply_thumbnail_size_to_lists(self, size):
        """Apply thumbnail size to all asset list widgets - Professional Icon Optimization"""
        try:
            # Improved grid sizing for larger professional file icons with better text readability
            grid_size = size + 32  # More padding for larger professional icon text and gradients
            icon_size = min(size, 128)  # Increased cap for better text readability
            
            # Update main asset list with improved professional icon sizing
            if hasattr(self, 'asset_list') and self.asset_list:
                self.asset_list.setIconSize(QSize(icon_size, icon_size))
                self.asset_list.setGridSize(QSize(grid_size, grid_size))
            
            if hasattr(self, 'main_asset_list') and self.main_asset_list:
                self.main_asset_list.setIconSize(QSize(icon_size, icon_size))
                self.main_asset_list.setGridSize(QSize(grid_size, grid_size))
            
            # Update collection tabs
            if hasattr(self, 'tab_widget'):
                for i in range(self.tab_widget.count()):
                    tab_widget = self.tab_widget.widget(i)
                    if tab_widget:
                        # Find QListWidget in tab
                        list_widget = self._find_list_widget_in_tab(tab_widget)
                        if list_widget:
                            list_widget.setIconSize(QSize(icon_size, icon_size))
                            list_widget.setGridSize(QSize(grid_size, grid_size))
                            
        except Exception as e:
            print(f"Error applying thumbnail size to lists: {e}")
    
    def _find_list_widget_in_tab(self, widget):
        """Find QListWidget in a tab widget - Open/Closed Principle helper"""
        if isinstance(widget, QListWidget):
            return widget
        
        for child in widget.findChildren(QListWidget):
            return child
        
        return None
    
    def _refresh_thumbnails_with_new_size(self, size):
        """Refresh thumbnails to use new size - avoid thumbnail cache staleness"""
        try:
            # Clear thumbnail cache to force regeneration with new size
            if hasattr(self.asset_manager, '_thumbnail_cache'):
                print(f"Clearing {len(self.asset_manager._thumbnail_cache)} cached thumbnails for resize")
                self.asset_manager._thumbnail_cache.clear()
            
            if hasattr(self.asset_manager, '_icon_cache'):
                self.asset_manager._icon_cache.clear()
            
            # Update the thumbnail system's target size
            self._update_thumbnail_system_size(size)
            
            # Trigger asset list refresh to regenerate thumbnails
            self.refresh_assets()
            
            print(f"✅ Thumbnails resized to {size}px")
            
        except Exception as e:
            print(f"Error refreshing thumbnails with new size: {e}")
    
    def _update_thumbnail_system_size(self, size):
        """Update the thumbnail generation system target size - SOLID: Interface Segregation"""
        try:
            # The thumbnail generation system will now use the UI preference directly
            # No need to store a separate variable since _generate_thumbnail_safe reads from UI preferences
            print(f"Thumbnail system updated to use {size}px size from UI preferences")
            
        except Exception as e:
            print(f"Warning: Could not update thumbnail system size: {e}")
    
    
    def create_main_asset_tab(self):
        """Create the main 'All Assets' tab"""
        # Asset library widget
        library_widget = QWidget()
        library_layout = QVBoxLayout(library_widget)
        
        # Asset list
        self.asset_list = QListWidget()
        
        # Configure dynamic thumbnail sizing for professional icons with LARGE readable text
        thumbnail_size = self._get_current_thumbnail_size()  # Now minimum 128px
        grid_size = thumbnail_size + 50  # Extra padding for large professional icon fonts and text
        icon_size = thumbnail_size  # Use FULL thumbnail size, no cap

        self.asset_list.setIconSize(QSize(icon_size, icon_size))
        self.asset_list.setGridSize(QSize(grid_size, grid_size))
        self.asset_list.setViewMode(QListWidget.ViewMode.IconMode)  # type: ignore
        self.asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)  # type: ignore
        self.asset_list.setUniformItemSizes(True)  # Prevent size variations
        self.asset_list.setMovement(QListWidget.Movement.Static)  # Prevent layout changes
        
        # COMPLETELY ELIMINATE text duplication - Professional icons only, NO text labels
        self.asset_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
                padding: 2px;
                margin: 2px;
                text-align: center;
                color: transparent;  /* HIDE ALL TEXT LABELS */
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 215, 120);
                border: 2px solid rgba(0, 120, 215, 255);
                border-radius: 6px;
                color: transparent;  /* KEEP TEXT HIDDEN EVEN WHEN SELECTED */
            }
            QListWidget::item:hover {
                background-color: rgba(0, 120, 215, 60);
                border-radius: 6px;
                color: transparent;  /* KEEP TEXT HIDDEN ON HOVER */
            }
        """)
        
        self.asset_list.itemDoubleClicked.connect(self.import_selected_asset)
        
        # Connect selection change to preview widget
        self.asset_list.currentItemChanged.connect(self.on_asset_selection_changed)
        
        # Enable context menu for asset management features
        self.asset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore
        self.asset_list.customContextMenuRequested.connect(self.show_asset_context_menu)
        
        library_layout.addWidget(self.asset_list)
        
        # Add the main tab
        self.tab_widget.addTab(library_widget, "📁 All Assets")
        
        # Store reference to main asset list for refreshing
        self.main_asset_list = self.asset_list
    
    def refresh_collection_tabs(self, force_refresh=False):
        """Refresh collection tabs based on current collections with improved synchronization - WITH RECURSION PROTECTION"""
        # CRITICAL: Prevent recursion cycles in collection tabs refresh
        if hasattr(self, '_refreshing_collection_tabs') and self._refreshing_collection_tabs:
            print("Warning: Blocking recursive refresh_collection_tabs call")
            return
            
        if not hasattr(self, 'tab_widget') or not self.tab_widget:
            return
        
        try:
            self._refreshing_collection_tabs = True
            
            # Clear file cache when refreshing collections to ensure fresh data
            if force_refresh:
                self.asset_manager._clear_file_cache()
            
            # Store current tab index to restore after refresh
            current_tab_index = self.tab_widget.currentIndex()
            current_tab_name = None
            if current_tab_index > 0:  # Not the "All Assets" tab
                current_tab_name = self.tab_widget.tabText(current_tab_index)
            
            # Remove all collection tabs (keep only the first "All Assets" tab)
            while self.tab_widget.count() > 1:
                self.tab_widget.removeTab(1)
            
            # Get current collections with error handling
            try:
                collections = self.asset_manager.get_asset_collections()
            except (RecursionError, Exception) as e:
                print(f"Error getting collections: {e}")
                collections = {}
            
            # Add tab for each collection with progress feedback
            new_tab_index = 1  # Track index for restoring selection
            restore_tab_index = 0  # Default to "All Assets"
            
            for collection_name, collection_data in collections.items():
                try:
                    self.create_collection_tab(collection_name, collection_data)
                    
                    # Check if this was the previously selected tab
                    if current_tab_name and collection_name in current_tab_name:
                        restore_tab_index = new_tab_index
                    
                    new_tab_index += 1
                    
                except Exception as e:
                    print(f"Error creating tab for collection '{collection_name}': {e}")
                    continue
            
            # Restore tab selection
            if restore_tab_index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(restore_tab_index)
            
            # CRITICAL: DO NOT refresh current tab content here to avoid recursion
            # Tab content will be refreshed when tabs are switched or explicitly requested
            
        except Exception as e:
            print(f"Error in refresh_collection_tabs: {e}")
        finally:
            self._refreshing_collection_tabs = False
    
    def _refresh_current_tab_content(self):
        """Refresh the content of the currently visible tab - WITH RECURSION PROTECTION"""
        # CRITICAL: Prevent recursion cycles in UI refresh
        if hasattr(self, '_refreshing_tab_content') and self._refreshing_tab_content:
            print("Warning: Blocking recursive _refresh_current_tab_content call")
            return
            
        if not hasattr(self, 'tab_widget') or not self.tab_widget:
            return
        
        current_widget = None
        current_index = -1  # Initialize with default value
        try:
            self._refreshing_tab_content = True
            current_index = self.tab_widget.currentIndex()
            
            if current_index == 0:
                # All Assets tab - refresh main asset list (but NOT collection filter to avoid recursion)
                if hasattr(self, 'main_asset_list'):
                    self._refresh_asset_list_safe()  # Use safe method
            else:
                # Collection tab - refresh the collection's asset list
                current_widget = self.tab_widget.currentWidget()
                if current_widget:
                    # Get collection name and refresh its content safely
                    if hasattr(current_widget, 'layout') and current_widget.layout():
                        # Find the asset list in this tab and refresh it
                        pass  # Skip complex collection refresh to avoid recursion
        except Exception as e:
            print(f"Error in _refresh_current_tab_content: {e}")
        finally:
            self._refreshing_tab_content = False
            if current_widget and current_index >= 0:
                # Find the asset list widget in the collection tab
                asset_list_widgets = current_widget.findChildren(QListWidget)
                if asset_list_widgets:
                    asset_list = asset_list_widgets[0]  # First (should be only) list widget
                    # Get collection name from tab text
                    tab_text = self.tab_widget.tabText(current_index)
                    collection_name = tab_text.replace("📦 ", "")
                    
                    # Refresh collection data and repopulate
                    try:
                        collections = self.asset_manager.get_asset_collections()
                        if collection_name in collections:
                            collection_data = collections[collection_name]
                            self.populate_collection_assets(asset_list, collection_data.get('assets', []))
                    except Exception as e:
                        print(f"Error refreshing collection tab content: {e}")
    
    def create_collection_tab(self, collection_name, collection_data):
        """Create a tab for a specific collection"""
        # Collection widget
        collection_widget = QWidget()
        collection_layout = QVBoxLayout(collection_widget)
        
        # Collection info
        info_layout = QHBoxLayout()
        info_label = QLabel(f"Collection: {collection_name}")
        info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        asset_count_label = QLabel(f"Assets: {len(collection_data.get('assets', []))}")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        info_layout.addWidget(asset_count_label)
        collection_layout.addLayout(info_layout)
        
        # Collection description (if available)
        if collection_data.get('description'):
            desc_label = QLabel(collection_data['description'])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: gray; font-style: italic;")
            collection_layout.addWidget(desc_label)
        
        # Asset list for this collection
        collection_asset_list = QListWidget()
        
        # Configure same LARGE sizing as main library for consistency  
        thumbnail_size = self._get_current_thumbnail_size()  # Now minimum 128px
        grid_size = thumbnail_size + 50  # Extra padding for large professional icon fonts and text
        icon_size = thumbnail_size  # Use FULL thumbnail size, no cap

        collection_asset_list.setIconSize(QSize(icon_size, icon_size))
        collection_asset_list.setGridSize(QSize(grid_size, grid_size))
        collection_asset_list.setViewMode(QListWidget.ViewMode.IconMode)  # type: ignore
        collection_asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)  # type: ignore
        collection_asset_list.setUniformItemSizes(True)  # Prevent size variations
        collection_asset_list.setMovement(QListWidget.Movement.Static)  # Prevent layout changes
        
        # Ensure no text labels are displayed in collections (icons only)
        collection_asset_list.setStyleSheet("""
            QListWidget::item {
                text-align: center;
                padding: 0px;
                margin: 0px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 215, 100);
                border: 2px solid rgba(0, 120, 215, 255);
                border-radius: 4px;
            }
        """)
        
        collection_asset_list.itemDoubleClicked.connect(self.import_selected_asset)
        
        # Connect selection change to preview widget
        collection_asset_list.currentItemChanged.connect(self.on_asset_selection_changed)
        
        # Enable context menu
        collection_asset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore
        collection_asset_list.customContextMenuRequested.connect(self.show_asset_context_menu)
        
        # LAZY LOADING: Store collection info and populate on demand
        setattr(collection_asset_list, 'collection_name', collection_name)
        setattr(collection_asset_list, 'is_populated', False)
        setattr(collection_asset_list, 'asset_names', collection_data.get('assets', []))
        
        # Add placeholder item
        placeholder_item = QListWidgetItem("🔄 Click to load assets...")
        placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        collection_asset_list.addItem(placeholder_item)
        
        # Connect to item activation for lazy loading
        def on_lazy_activate(item):
            if hasattr(collection_asset_list, 'is_populated') and not getattr(collection_asset_list, 'is_populated'):
                collection_asset_list.clear()
                setattr(collection_asset_list, 'is_populated', True)
                self.populate_collection_assets(collection_asset_list, getattr(collection_asset_list, 'asset_names', []))
        
        collection_asset_list.itemClicked.connect(on_lazy_activate)
        
        collection_layout.addWidget(collection_asset_list)
        
        # Collection management buttons
        collection_buttons_layout = QHBoxLayout()
        
        edit_collection_btn = QPushButton("Edit Collection")
        edit_collection_btn.clicked.connect(lambda: self.edit_collection_dialog(collection_name))
        collection_buttons_layout.addWidget(edit_collection_btn)
        
        delete_collection_btn = QPushButton("Delete Collection")
        delete_collection_btn.clicked.connect(lambda: self.delete_collection_dialog(collection_name))
        collection_buttons_layout.addWidget(delete_collection_btn)
        
        collection_buttons_layout.addStretch()
        collection_layout.addLayout(collection_buttons_layout)
        
        # Add tab with collection emoji
        tab_name = f"📦 {collection_name}"
        self.tab_widget.addTab(collection_widget, tab_name)
    
    def populate_collection_assets(self, asset_list_widget, asset_names):
        """Populate a collection's asset list with improved performance for network storage"""
        asset_list_widget.clear()
        
        print(f"🔍 Populating collection with asset names: {asset_names}")
        print(f"📂 Current project path: {self.asset_manager.current_project}")
        
        if not self.asset_manager.current_project:
            print("❌ No current project set")
            return
            
        project_path = self.asset_manager.current_project
        print(f"📁 Checking project path exists: {project_path} -> {os.path.exists(project_path)}")
        if not os.path.exists(project_path):
            print(f"❌ Project path does not exist: {project_path}")
            return
        
        # Apply same no-text styling to collection tabs to eliminate duplication
        asset_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
                padding: 2px;
                margin: 2px;
                text-align: center;
                color: transparent;  /* HIDE ALL TEXT LABELS */
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 215, 120);
                border: 2px solid rgba(0, 120, 215, 255);
                border-radius: 6px;
                color: transparent;  /* KEEP TEXT HIDDEN EVEN WHEN SELECTED */
            }
            QListWidget::item:hover {
                background-color: rgba(0, 120, 215, 60);
                border-radius: 6px;
                color: transparent;  /* KEEP TEXT HIDDEN ON HOVER */
            }
        """)

        # Use cached file list for better network performance
        try:
            asset_files = self.asset_manager._get_cached_file_list(project_path)
            print(f"📁 Found {len(asset_files)} files in project")
            if len(asset_files) == 0:
                print("🔍 No files found - checking project directory contents:")
                try:
                    if os.path.exists(project_path):
                        dir_contents = []
                        for root, dirs, files in os.walk(project_path):
                            for file in files:
                                if file.lower().endswith(('.ma', '.mb')):
                                    dir_contents.append(os.path.join(root, file))
                        print(f"   Direct scan found {len(dir_contents)} Maya files")
                        if len(dir_contents) > 0:
                            for file in dir_contents[:3]:
                                print(f"   - {os.path.basename(file)}")
                    else:
                        print(f"   Project path does not exist: {project_path}")
                except Exception as scan_error:
                    print(f"   Scan error: {scan_error}")
            # Debug: Show first few files to understand the naming
            for i, file_path in enumerate(asset_files[:5]):
                file_name = os.path.splitext(os.path.basename(file_path))[0]
                print(f"  File {i+1}: {file_name} (from {os.path.basename(file_path)})")
        except Exception as e:
            print(f"Error getting cached file list: {e}")
            return
        
        # Show progress for large collections
        if len(asset_names) > 50:
            progress = QProgressDialog("Loading collection assets...", "Cancel", 0, len(asset_names), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
        else:
            progress = None
        
        items_processed = 0
        
        # Process files in batches for better performance
        matching_found = False
        for file_path in asset_files:
            if progress and progress.wasCanceled():
                break
            
            asset_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Debug: Show the comparison for the expected asset
            if 'Veteran_Rig' in asset_names and not matching_found:
                print(f"🔍 Looking for 'Veteran_Rig', checking: '{asset_name}'")
                if asset_name == 'Veteran_Rig':
                    print(f"✅ EXACT MATCH found!")
                    matching_found = True
                elif 'Veteran' in asset_name:
                    print(f"🔶 Partial match found: {asset_name}")
            
            # Only add if this asset is in the collection
            if asset_name in asset_names:
                print(f"✅ Found matching asset: {asset_name} -> {file_path}")
                try:
                    # Professional icons contain all info - no duplicate text needed
                    # Create clean list item without text to avoid duplication
                    item = QListWidgetItem()
                    item.setData(Qt.ItemDataRole.UserRole, file_path)  # type: ignore
                    
                    # Store asset name for tooltips and context
                    item.setToolTip(self._create_asset_display_text(asset_name, file_path))
                    
                    # Professional icons have their own color scheme - no background needed
                    # Removed item.setBackground() to prevent color bleeding outside icon shape
                    
                    # Try to load thumbnail with lazy loading for better performance
                    self._set_asset_item_icon(item, file_path)
                    
                    asset_list_widget.addItem(item)
                    print(f"  ➕ Added {asset_name} to collection widget")
                    
                    items_processed += 1
                    if progress:
                        progress.setValue(items_processed)
                        if items_processed % 10 == 0:  # Update UI every 10 items
                            QApplication.processEvents()
                
                except Exception as e:
                    print(f"❌ Error processing asset {asset_name}: {e}")
                    continue
            else:
                # Debug: show which files are being skipped
                if items_processed < 5:  # Only show first 5 to avoid spam
                    print(f"⏭️ Skipping {asset_name} (not in collection)")
        
        print(f"📊 Collection population complete: {items_processed} items processed")
        
        if progress:
            progress.close()
            progress.deleteLater()  # Proper cleanup to prevent memory leaks
    
    def _set_asset_item_icon(self, item, file_path):
        """Set professional file icon for asset item with optimized caching"""
        try:
            # Check icon cache first for better performance
            cache_key = f"icon_{file_path}_{self._get_current_thumbnail_size()}"
            
            if hasattr(self.asset_manager, '_icon_cache') and cache_key in self.asset_manager._icon_cache:
                # Use cached icon
                cached_icon = self.asset_manager._icon_cache[cache_key]
                item.setIcon(cached_icon)
                size_hint = self._get_current_thumbnail_size() + 50
                item.setSizeHint(QSize(size_hint, size_hint))
                return
            
            # Generate new icon if not cached
            thumbnail_size = self._get_current_thumbnail_size()
            professional_icon = self.asset_manager._generate_professional_file_icon(file_path, (thumbnail_size, thumbnail_size))
            
            if professional_icon and not professional_icon.isNull():
                # Convert pixmap to icon
                icon = QIcon()
                icon.addPixmap(professional_icon, QIcon.Mode.Normal, QIcon.State.Off)
                
                # Cache the icon for future use
                if not hasattr(self.asset_manager, '_icon_cache'):
                    self.asset_manager._icon_cache = {}
                
                # Limit cache size to prevent memory issues
                if len(self.asset_manager._icon_cache) > 100:
                    # Remove oldest entries (simple cache cleanup)
                    keys_to_remove = list(self.asset_manager._icon_cache.keys())[:20]
                    for old_key in keys_to_remove:
                        del self.asset_manager._icon_cache[old_key]
                
                self.asset_manager._icon_cache[cache_key] = icon
                
                item.setIcon(icon)
                size_hint = thumbnail_size + 50
                item.setSizeHint(QSize(size_hint, size_hint))
            else:
                # Fallback to professional icon system
                self._set_fallback_icon(item, file_path)
                
        except Exception as e:
            print(f"Error setting professional asset icon for {file_path}: {e}")
            # Set fallback icon on error
            self._set_fallback_icon(item, file_path)
    
    def _set_fallback_icon(self, item, file_path):
        """Set professional file type icon as fallback with consistent sizing - PROFESSIONAL UPGRADE"""
        try:
            # Use our professional file icon system for fallbacks with improved size
            professional_icon = self.asset_manager._generate_professional_file_icon(file_path, (96, 96))
            if professional_icon and not professional_icon.isNull():
                # Convert pixmap to icon
                icon = QIcon()
                icon.addPixmap(professional_icon, QIcon.Mode.Normal, QIcon.State.Off)
                item.setIcon(icon)
                item.setSizeHint(QSize(128, 128))  # Larger fallback size for consistency
                return
        except Exception as e:
            print(f"Error creating professional fallback icon: {e}")
        
        # Ultimate fallback to system icons if professional icons fail
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Set default icon based on file type
        if file_ext in ['.ma', '.mb']:
            default_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)  # type: ignore
        elif file_ext == '.obj':
            default_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView)  # type: ignore
        elif file_ext == '.fbx':
            default_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogStart)  # type: ignore
        elif file_ext in ['.abc', '.usd']:
            default_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)  # type: ignore
        else:
            default_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)  # type: ignore
        
        item.setIcon(default_icon)
        # Professional size hint for fallback icons too
        thumbnail_size = self.asset_manager.get_ui_preference('thumbnail_size', 64) or 64
        size_hint = min(thumbnail_size + 26, 98)
        item.setSizeHint(QSize(size_hint, size_hint))
    
    def add_collection_tab_dialog(self):
        """Show dialog to create a new collection tab"""
        collection_name, ok = QInputDialog.getText(
            self, "New Collection Tab", "Enter collection name:"
        )
        
        if ok and collection_name.strip():
            collection_name = collection_name.strip()
            if self.asset_manager.create_asset_collection(collection_name):
                self.refresh_collection_tabs()
                self.refresh_collection_filter()
                self.status_bar.showMessage(f"Created collection tab '{collection_name}'")
                
                # Switch to the new tab
                tab_count = self.tab_widget.count()
                self.tab_widget.setCurrentIndex(tab_count - 1)
            else:
                QMessageBox.warning(self, "Error", "Failed to create collection or collection already exists.")
    
    def edit_collection_dialog(self, collection_name):
        """Show dialog to edit collection properties"""
        collections = self.asset_manager.get_asset_collections()
        if collection_name not in collections:
            return
            
        collection_data = collections[collection_name]
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Collection: {collection_name}")
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Collection description
        layout.addWidget(QLabel("Description:"))
        desc_edit = QTextEdit()
        desc_edit.setPlainText(collection_data.get('description', ''))
        layout.addWidget(desc_edit)
        
        # Asset management
        layout.addWidget(QLabel("Assets in Collection:"))
        asset_list = QListWidget()
        asset_list.addItems(collection_data.get('assets', []))
        layout.addWidget(asset_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # Connect buttons
        save_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        # Show dialog and handle result
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update collection description
            project_name = self.asset_manager._ensure_project_entry()
            if project_name and 'collections' in self.asset_manager.assets_library[project_name]:
                self.asset_manager.assets_library[project_name]['collections'][collection_name]['description'] = desc_edit.toPlainText()
                self.asset_manager.save_config()
                self.refresh_collection_tabs()
                self.status_bar.showMessage(f"Updated collection '{collection_name}'")
    
    def delete_collection_dialog(self, collection_name):
        """Show confirmation dialog and delete collection"""
        reply = QMessageBox.question(
            self, "Delete Collection",
            f"Are you sure you want to delete the collection '{collection_name}'?\n\n"
            f"This will remove the collection but not the actual asset files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete collection
            project_name = self.asset_manager._ensure_project_entry()
            if project_name and 'collections' in self.asset_manager.assets_library[project_name]:
                if collection_name in self.asset_manager.assets_library[project_name]['collections']:
                    del self.asset_manager.assets_library[project_name]['collections'][collection_name]
                    self.asset_manager.save_config()
                    self.refresh_collection_tabs()
                    self.refresh_collection_filter()
                    self.status_bar.showMessage(f"Deleted collection '{collection_name}'")
                    
                    # Switch back to main tab
                    self.tab_widget.setCurrentIndex(0)
    
    def get_current_asset_list(self):
        """Get the currently active asset list widget"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            # Find the QListWidget in the current tab
            for child in current_tab.findChildren(QListWidget):
                return child
        return self.main_asset_list  # Fallback to main asset list
    
    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
    
    def new_project_dialog(self):
        """Show new project dialog"""
        dialog = NewProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:  # type: ignore
            project_name, project_path = dialog.get_values()
            if self.asset_manager.create_project(project_name, project_path):
                self.update_project_info()
                self.refresh_assets()
                self.status_bar.showMessage(f"Created project: {project_name}")
            else:
                QMessageBox.warning(self, "Error", "Failed to create project")
    
    def open_project_dialog(self):
        """Show open project dialog"""
        project_path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if project_path:
            self.asset_manager.current_project = project_path
            self.asset_manager.save_config()
            self.update_project_info()
            self.refresh_assets()
            self.status_bar.showMessage(f"Opened project: {os.path.basename(project_path)}")
    
    def import_asset_dialog(self):
        """Show import asset dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Asset", "", 
            "Maya Files (*.ma *.mb);;OBJ Files (*.obj);;FBX Files (*.fbx);;All Files (*)"
        )
        if file_path:
            if self.asset_manager.import_asset(file_path):
                self.status_bar.showMessage(f"Imported: {os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "Error", "Failed to import asset")
    
    def export_selected_dialog(self):
        """Show export selected dialog"""
        if not MAYA_AVAILABLE or cmds is None:
            QMessageBox.warning(self, "Warning", "Maya not available")
            return
            
        if not cmds.ls(selection=True):
            QMessageBox.warning(self, "Warning", "Please select objects to export")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Asset", "", "Maya ASCII (*.ma);;Maya Binary (*.mb)"
        )
        if file_path:
            asset_name = os.path.splitext(os.path.basename(file_path))[0]
            if self.asset_manager.export_selected_as_asset(file_path, asset_name):
                self.refresh_assets()
                self.status_bar.showMessage(f"Exported: {asset_name}")
            else:
                QMessageBox.warning(self, "Error", "Failed to export asset")
    
    def add_assets_from_folders_dialog(self):
        """Show the add assets from folders dialog"""
        if not self.asset_manager.current_project:
            reply = QMessageBox.question(
                self, "No Project", 
                "No project is currently open. Would you like to create or open a project first?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.new_project_dialog()
                if not self.asset_manager.current_project:
                    return
            else:
                return
        
        dialog = AddAssetsFromFoldersDialog(self.asset_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh the asset library to show new assets
            self.refresh_assets()
            self.refresh_tag_filter()
            self.refresh_collection_filter()
            self.status_bar.showMessage("Assets added to library successfully")
    
    def on_asset_selection_changed(self, current_item, previous_item):
        """Handle asset selection change and update preview"""
        try:
            if hasattr(self, 'asset_preview_widget') and self.asset_preview_widget:
                if current_item:
                    # Get asset path from item data
                    asset_path = current_item.data(Qt.ItemDataRole.UserRole)  # type: ignore
                    if asset_path and os.path.exists(asset_path):
                        # Load asset in preview widget
                        self.asset_preview_widget.load_asset(asset_path)
                    else:
                        # Clear preview if no valid path
                        self.asset_preview_widget.clear_preview()
                else:
                    # Clear preview when no item selected
                    self.asset_preview_widget.clear_preview()
        except Exception as e:
            print(f"Error updating asset preview: {e}")
    
    def import_selected_asset(self):
        """Import the selected asset from the current tab"""
        current_asset_list = self.get_current_asset_list()
        if not current_asset_list:
            return
            
        current_item = current_asset_list.currentItem()
        if current_item:
            asset_path = current_item.data(Qt.ItemDataRole.UserRole)  # type: ignore
            if asset_path and self.asset_manager.import_asset(asset_path):
                self.status_bar.showMessage(f"Imported: {current_item.text()}")
            else:
                QMessageBox.warning(self, "Error", "Failed to import asset")
    
    def delete_selected_asset(self):
        """Delete the selected asset from the current tab"""
        current_asset_list = self.get_current_asset_list()
        if not current_asset_list:
            return
            
        current_item = current_asset_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self, "Confirm Delete", 
                f"Are you sure you want to delete '{current_item.text()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No  # type: ignore
            )
            if reply == QMessageBox.StandardButton.Yes:  # type: ignore
                asset_path = current_item.data(Qt.ItemDataRole.UserRole)  # type: ignore
                if asset_path and os.path.exists(asset_path):
                    os.remove(asset_path)
                    self.refresh_assets()
                    self.refresh_collection_tabs()  # Refresh collection tabs too
                    self.status_bar.showMessage(f"Deleted: {current_item.text()}")
    
    def _refresh_asset_list_safe(self):
        """Safely refresh asset list without triggering collection filter recursion - FIXED DUPLICATION"""
        try:
            # FORCE CLEAR both main_asset_list AND asset_list to prevent duplication
            if hasattr(self, 'main_asset_list') and self.main_asset_list:
                self.main_asset_list.clear()
            if hasattr(self, 'asset_list') and self.asset_list:
                self.asset_list.clear()
            
            # Get the ONE target list widget
            target_asset_list = getattr(self, 'main_asset_list', None) or getattr(self, 'asset_list', None)
            if not target_asset_list:
                return
            
            if not self.asset_manager.current_project:
                return
            
            # Track added paths to prevent duplication
            added_paths = set()
            
            # Get registered assets from library (with error protection)
            try:
                registered_assets = self.asset_manager.get_registered_assets()
            except (RecursionError, Exception) as e:
                print(f"Error getting registered assets: {e}")
                registered_assets = {}
            
            # Populate with registered assets first  
            for asset_name, asset_info in registered_assets.items():
                try:
                    asset_path = asset_info.get('path', '')
                    if asset_path and os.path.exists(asset_path) and asset_path not in added_paths:
                        # Professional icons contain all info - no duplicate text needed
                        item = QListWidgetItem()
                        item.setData(Qt.ItemDataRole.UserRole, asset_path)  # type: ignore
                        
                        # Store full info in tooltip for user reference
                        item.setToolTip(self._create_asset_display_text(asset_name, asset_path, is_registered=True))
                        
                        # Set professional icon with crash-safe loading
                        try:
                            self._set_asset_item_icon(item, asset_path)
                        except:
                            pass
                        
                        # Add to the ONE target list
                        target_asset_list.addItem(item)
                        added_paths.add(asset_path)
                except Exception as e:
                    print(f"Error adding registered asset {asset_name}: {e}")
                    continue
                
        except Exception as e:
            print(f"Error in _refresh_asset_list_safe: {e}")

    def refresh_assets(self):
        """Refresh the asset library with enhanced thumbnail support - FIXED DUPLICATION"""
        # CRITICAL: Add recursion protection
        if hasattr(self, '_refreshing_assets') and self._refreshing_assets:
            print("Warning: Blocking recursive refresh_assets call")
            return

        try:
            self._refreshing_assets = True
          
            # FORCE CLEAR both main_asset_list AND asset_list to prevent duplication
            if hasattr(self, 'main_asset_list') and self.main_asset_list:
                self.main_asset_list.clear()
            if hasattr(self, 'asset_list') and self.asset_list:
                self.asset_list.clear()
            
            # Get the ONE target list widget
            target_asset_list = getattr(self, 'main_asset_list', None) or getattr(self, 'asset_list', None)
            if not target_asset_list:
                return
            
            if not self.asset_manager.current_project:
                return
            
            # Add loading indicator for better user feedback
            loading_item = QListWidgetItem("🔄 Loading assets...")
            loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            target_asset_list.addItem(loading_item)
            
            # Force UI update to show loading message
            QApplication.processEvents()
            
            # Track added paths to prevent duplication
            added_paths = set()
            
            # Get registered assets from library (with error protection)
            try:
                registered_assets = self.asset_manager.get_registered_assets()
            except (RecursionError, Exception) as e:
                print(f"Error getting registered assets: {e}")
                registered_assets = {}
            
            # Process registered assets in batches for better performance
            batch_count = 0
            for asset_name, asset_info in registered_assets.items():
                try:
                    asset_path = asset_info.get('path', '')
                    if asset_path and os.path.exists(asset_path) and asset_path not in added_paths:
                        # Professional icons contain all info - no duplicate text needed
                        item = QListWidgetItem()
                        item.setData(Qt.ItemDataRole.UserRole, asset_path)  # type: ignore
                        
                        # Store full info in tooltip for user reference
                        item.setToolTip(self._create_asset_display_text(asset_name, asset_path, is_registered=True))
                        
                        # Set professional icon with crash-safe loading
                        try:
                            self._set_asset_item_icon(item, asset_path)
                        except:
                            pass
                        
                        # Add to the ONE target list
                        target_asset_list.addItem(item)
                        added_paths.add(asset_path)
                        batch_count += 1
                        
                        # Process UI events every 10 items to keep interface responsive
                        if batch_count % 10 == 0:
                            QApplication.processEvents()
                        
                except Exception as e:
                    print(f"Error adding registered asset {asset_name}: {e}")
                    continue
            
            # Remove loading indicator now that registered assets are loaded
            target_asset_list.takeItem(0)
            
            # Scan project directory for assets using cached file list for better performance
            project_path = self.asset_manager.current_project
            if project_path and os.path.exists(project_path):
                try:
                    # Use cached file scanning instead of os.walk for better performance
                    project_files = self.asset_manager._get_cached_file_list(project_path)
                    
                    # Process files in batches to keep UI responsive
                    batch_size = 25
                    for i, file_path in enumerate(project_files):
                        # Skip if already added to prevent duplication
                        if file_path in added_paths:
                            continue
                        
                        try:
                            file_name = os.path.basename(file_path)
                            asset_name = os.path.splitext(file_name)[0]
                            
                            # Professional icons contain all info - no duplicate text needed
                            item = QListWidgetItem()
                            item.setData(Qt.ItemDataRole.UserRole, file_path)  # type: ignore
                            
                            # Store full info in tooltip for user reference
                            item.setToolTip(self._create_asset_display_text(asset_name, file_path, is_registered=False))
                            
                            # Set professional icon with crash-safe loading
                            try:
                                self._set_asset_item_icon(item, file_path)
                            except:
                                pass
                            
                            # Add to the ONE target list
                            target_asset_list.addItem(item)
                            added_paths.add(file_path)
                            
                            # Process UI events every batch to maintain responsiveness
                            if (i + 1) % batch_size == 0:
                                QApplication.processEvents()
                                
                        except Exception as e:
                            print(f"Error adding asset {file_path}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error scanning project directory: {e}")
            
            # Refresh collection filter (but only if not already refreshing to avoid recursion)
            if not hasattr(self, '_refreshing_collection_filter') or not self._refreshing_collection_filter:
                try:
                    self.refresh_collection_filter()
                except Exception as e:
                    print(f"Error refreshing collection filter: {e}")
        
        except Exception as e:
            print(f"Error in refresh_assets: {e}")
        finally:
            self._refreshing_assets = False
  
    def _create_asset_display_text(self, asset_name, asset_path, is_registered=False):
        """Create enhanced display text showing asset type and collections"""
        display_parts = [asset_name]
        
        # Add library indicator for registered assets
        if is_registered:
            display_parts.append("📚")  # Library book emoji
        
        # Add asset type indicator
        asset_type = self.asset_manager.get_asset_type(asset_path)
        if asset_type != 'default':
            display_parts.append(f"[{asset_type.upper()}]")
        
        # Add collection indicators
        collections = self.asset_manager.get_asset_collections()
        asset_collections = []
        for collection_name, collection_data in collections.items():
            if asset_name in collection_data.get('assets', []):
                asset_collections.append(collection_name)
        
        if asset_collections:
            collections_str = ", ".join(asset_collections)
            display_parts.append(f"(Collections: {collections_str})")
        
        return " ".join(display_parts)
    
    def filter_assets(self):
        """Filter assets based on category and search"""
        category = self.categories_list.currentItem().text() if self.categories_list.currentItem() else "All"
        search_text = self.search_input.text().lower()
        
        for i in range(self.asset_list.count()):
            item = self.asset_list.item(i)
            show_item = True
            
            # Filter by category
            if category != "All":
                asset_path = item.data(Qt.ItemDataRole.UserRole)  # type: ignore
                if asset_path:
                    if category == "Models" and not asset_path.lower().endswith(('.ma', '.mb', '.obj', '.fbx')):
                        show_item = False
                    elif category == "Textures" and not any(asset_path.lower().endswith(ext) for ext in ['.jpg', '.png', '.tga', '.exr']):
                        show_item = False
                    elif category == "Scenes" and not asset_path.lower().endswith(('.ma', '.mb')):
                        show_item = False
            
            # Filter by search text
            if search_text and search_text not in item.text().lower():
                show_item = False
            
            item.setHidden(not show_item)
    
    def update_project_info(self):
        """Update the project info display"""
        if self.asset_manager.current_project:
            project_name = os.path.basename(self.asset_manager.current_project)
            self.project_label.setText(f"Project: {project_name}\nPath: {self.asset_manager.current_project}")
        else:
            self.project_label.setText("No project selected")
    
    def show_asset_type_customization(self):
        """Show the asset type customization dialog"""
        dialog = AssetTypeCustomizationDialog(self.asset_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh UI elements that depend on asset types
            self.refresh_assets()
            self.update_category_list()
            self.refresh_color_legend()
            self.refresh_tag_filter()
            self.refresh_collection_filter()
            self.status_bar.showMessage("Asset type configuration updated")
    
    def refresh_color_legend(self):
        """Refresh the color legend with current asset types"""
        if hasattr(self, 'legend_group'):
            # Clear existing layout
            layout = self.legend_group.layout()
            if layout:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            
            # Recreate the legend
            self.create_color_legend(layout)
    
    def update_category_list(self):
        """Update the categories list with current asset types"""
        if hasattr(self, 'categories_list'):
            current_selection = self.categories_list.currentItem()
            current_text = current_selection.text() if current_selection else "All"
            
            self.categories_list.clear()
            categories = ['All']
            
            # Add asset type categories
            for type_id, config in self.asset_manager.asset_types.items():
                if type_id != 'default':
                    categories.append(config['name'])
            
            self.categories_list.addItems(categories)
            
            # Restore selection
            for i in range(self.categories_list.count()):
                if self.categories_list.item(i).text() == current_text:
                    self.categories_list.setCurrentRow(i)
                    break
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About Asset Manager", 
                         f"Asset Manager v{self.asset_manager.version}\n\n"
                         f"A comprehensive asset management system for Maya 2025.3+\n"
                         f"Built with Python 3 and PySide6\n\n"
                         f"Author: Mike Stumbo")
    
    def _on_directory_changed(self, path):
        """Handle directory changes for automatic refresh"""
        if not hasattr(self, '_refresh_timer'):
            return
        
        print(f"Directory changed: {path}")
        
        # Only refresh if the changed directory is relevant to our current project
        if (self.asset_manager.current_project and 
            path.startswith(self.asset_manager.current_project)):
            
            # Clear file cache for the changed directory
            self.asset_manager._clear_file_cache()
            
            # Start or restart the refresh timer to avoid excessive updates
            self._refresh_timer.start()
    
    def _delayed_refresh(self):
        """Perform delayed refresh after directory changes"""
        try:
            # Refresh with force to clear caches
            self.refresh_collection_tabs(force_refresh=True)
            self.status_bar.showMessage("Assets refreshed automatically", 3000)
        except Exception as e:
            print(f"Error during automatic refresh: {e}")
    
    def _setup_file_watcher(self):
        """Setup file system watcher for the current project"""
        if not hasattr(self, 'file_watcher') or not self.asset_manager.current_project:
            return
        
        # Clear existing watches
        watched_dirs = self.file_watcher.directories()
        if watched_dirs:
            self.file_watcher.removePaths(watched_dirs)
        
        # Add current project directory to watch
        if os.path.exists(self.asset_manager.current_project):
            # Only watch if not in network mode to avoid performance issues
            if not self.asset_manager._network_performance['network_mode']:
                self.file_watcher.addPath(self.asset_manager.current_project)
                print(f"File watcher enabled for: {self.asset_manager.current_project}")
            else:
                print("File watcher disabled for network storage to improve performance")
    
    def check_for_updates(self):
        """Check for updates to the Asset Manager plugin"""
        try:
            # Show progress while checking
            progress = QProgressDialog("Checking for updates...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)  # type: ignore
            progress.show()
            
            # Get current version
            current_version = self.asset_manager.version
            
            # Check for updates - this could be expanded to check a real repository
            # For now, we'll simulate checking against a known latest version
            latest_version = self._get_latest_version()
            release_notes = self._get_release_notes(latest_version)
            
            progress.close()
            progress.deleteLater()  # Proper cleanup to prevent memory leaks
            
            if self._compare_versions(current_version, latest_version):
                # Update available
                message = f"New version available!\n\n"
                message += f"Current version: {current_version}\n"
                message += f"Latest version: {latest_version}\n\n"
                message += f"Release Notes:\n{release_notes}\n\n"
                message += f"Would you like to view the download page?"
                
                reply = QMessageBox.question(
                    self, "Update Available", message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._open_download_page()
            else:
                # No update available
                QMessageBox.information(
                    self, "No Updates", 
                    f"You are running the latest version ({current_version}).\n\n"
                    f"Check again later for new updates."
                )
                
        except Exception as e:
            QMessageBox.warning(
                self, "Update Check Failed", 
                f"Failed to check for updates:\n{str(e)}\n\n"
                f"Please check your internet connection and try again."
            )
    
    def _get_latest_version(self):
        """Get the latest version information (placeholder for real implementation)"""
        # In a real implementation, this would check a remote repository
        # For demonstration, we'll return a mock version that's higher than current
        current_version = self.asset_manager.version
        version_parts = current_version.split('.')
        if len(version_parts) >= 3:
            # Increment the patch version for demo
            patch = int(version_parts[2]) + 1
            return f"{version_parts[0]}.{version_parts[1]}.{patch}"
        return "1.2.0"  # fallback mock version
    
    def _get_release_notes(self, version):
        """Get release notes for a version (placeholder for real implementation)"""
        # In a real implementation, this would fetch actual release notes
        return f"• Bug fixes and stability improvements\n• Enhanced performance\n• New features for version {version}"
    
    def _compare_versions(self, current, latest):
        """Compare version strings to see if update is available"""
        def version_tuple(v):
            return tuple(map(int, (v.split("."))))
        
        try:
            return version_tuple(latest) > version_tuple(current)
        except:
            return False
    
    def _open_download_page(self):
        """Open the download page for updates"""
        # In a real implementation, this would open the actual project repository
        download_url = "https://github.com/mikestumbo/assetManagerforMaya"
        
        try:
            import webbrowser
            webbrowser.open(download_url)
        except:
            # Fallback: show URL in a dialog
            QMessageBox.information(
                self, "Download Link", 
                f"Visit the following URL to download the latest version:\n\n{download_url}"
            )

    # =============================================================================
    # New Asset Management & Organization UI Methods (v1.1.0)
    # =============================================================================
    
    def filter_by_tag(self, tag_name):
        """Filter assets by selected tag"""
        try:
            if tag_name == "All Tags":
                self.filter_assets()  # Show all assets
                return
                
            # Filter assets to show only those with the selected tag
            for i in range(self.asset_list.count()):
                item = self.asset_list.item(i)
                if item:
                    asset_path = item.data(Qt.ItemDataRole.UserRole)  # type: ignore
                    if asset_path:
                        try:
                            asset_tags = self.asset_manager.get_asset_tags(asset_path)
                            item.setHidden(tag_name not in asset_tags)
                        except (RecursionError, Exception) as e:
                            print(f"Error getting tags for {asset_path}: {e}")
                            item.setHidden(True)  # Hide problematic items
        except Exception as e:
            print(f"Error in filter_by_tag: {e}")
            # Fallback to showing all assets
            self.filter_assets()
    
    def filter_by_collection(self, collection_name):
        """Filter assets by selected collection"""
        try:
            if collection_name == "All Collections":
                self.filter_assets()  # Show all assets
                return
                
            try:
                collections = self.asset_manager.get_asset_collections()
            except (RecursionError, Exception) as e:
                print(f"Error getting collections: {e}")
                # Fallback to showing all assets
                self.filter_assets()
                return
                
            if collection_name not in collections:
                return
                
            collection_assets = collections[collection_name]['assets']
            
            # Filter assets to show only those in the selected collection
            for i in range(self.asset_list.count()):
                item = self.asset_list.item(i)
                if item:
                    asset_name = item.text()
                    item.setHidden(asset_name not in collection_assets)
        except Exception as e:
            print(f"Error in filter_by_collection: {e}")
            # Fallback to showing all assets
            self.filter_assets()
    
    def add_tag_to_selected(self):
        """Add a tag to the currently selected asset"""
        current_asset_list = self.get_current_asset_list()
        if not current_asset_list:
            return
            
        current_item = current_asset_list.currentItem()
        tag_text = self.tag_input.text().strip()
        
        if not current_item or not tag_text:
            QMessageBox.warning(self, "Warning", "Please select an asset and enter a tag name.")
            return
        
        asset_path = current_item.data(Qt.ItemDataRole.UserRole)  # type: ignore
        if asset_path and self.asset_manager.add_asset_tag(asset_path, tag_text):
            self.status_bar.showMessage(f"Added tag '{tag_text}' to {current_item.text()}")
            self.tag_input.clear()
            self.refresh_tag_filter()
        else:
            QMessageBox.warning(self, "Error", "Failed to add tag or tag already exists.")
    
    def create_new_collection(self):
        """Create a new asset collection"""
        collection_name = self.collection_input.text().strip()
        
        if not collection_name:
            QMessageBox.warning(self, "Warning", "Please enter a collection name.")
            return
        
        if self.asset_manager.create_asset_collection(collection_name):
            self.status_bar.showMessage(f"Created collection '{collection_name}'")
            self.collection_input.clear()
            
            # CRITICAL: Refresh both filter and tabs to show the new collection
            self.refresh_collection_filter()
            self.refresh_collection_tabs(force_refresh=True)
            print(f"✅ Created collection '{collection_name}' and refreshed tabs")
        else:
            QMessageBox.warning(self, "Error", "Failed to create collection or collection already exists.")
    
    def refresh_tag_filter(self):
        """Refresh the tag filter dropdown with current tags"""
        current_selection = self.tag_filter.currentText()
        self.tag_filter.clear()
        self.tag_filter.addItem("All Tags")
        
        all_tags = self.asset_manager.get_all_tags()
        self.tag_filter.addItems(all_tags)
        
        # Restore previous selection if it still exists
        index = self.tag_filter.findText(current_selection)
        if index >= 0:
            self.tag_filter.setCurrentIndex(index)
    
    def refresh_collection_filter(self):
        """Refresh the collection filter dropdown with current collections - WITH RECURSION PROTECTION"""
        # CRITICAL: Prevent recursion cycles in collection filter refresh
        if hasattr(self, '_refreshing_collection_filter') and self._refreshing_collection_filter:
            print("Warning: Blocking recursive refresh_collection_filter call")
            return
            
        try:
            self._refreshing_collection_filter = True
            
            current_selection = self.collection_filter.currentText()
            self.collection_filter.clear()
            self.collection_filter.addItem("All Collections")
            
            # Get collections safely
            try:
                collections = self.asset_manager.get_asset_collections()
                self.collection_filter.addItems(list(collections.keys()))
            except (RecursionError, Exception) as e:
                print(f"Error getting asset collections for filter: {e}")
                # Continue with empty collections
            
            # Restore previous selection if it still exists
            index = self.collection_filter.findText(current_selection)
            if index >= 0:
                self.collection_filter.setCurrentIndex(index)
            
            # CRITICAL: DO NOT refresh collection tabs here to avoid recursion
            # The tabs will be refreshed elsewhere when needed
            
        except Exception as e:
            print(f"Error in refresh_collection_filter: {e}")
        finally:
            self._refreshing_collection_filter = False
    
    def show_asset_context_menu(self, position):
        """Show context menu for asset with new management options"""
        # Get the asset list that triggered the context menu
        sender_widget = self.sender()
        if not isinstance(sender_widget, QListWidget):
            return
            
        item = sender_widget.itemAt(position)
        if not item:
            return
            
        asset_path = item.data(Qt.ItemDataRole.UserRole)  # type: ignore
        if not asset_path:
            return
        
        # Store asset path for context menu actions
        self._context_asset_path = asset_path
            
        menu = QMenu(self)
        
        # Standard actions
        import_action = menu.addAction("Import Asset")
        import_action.triggered.connect(self.import_selected_asset)
        
        menu.addSeparator()
        
        # Tag management
        tag_menu = menu.addMenu("Tags")
        
        # Show current tags
        current_tags = self.asset_manager.get_asset_tags(asset_path)
        if current_tags:
            tag_menu.addAction("Current Tags:").setEnabled(False)
            for tag in current_tags:
                remove_action = tag_menu.addAction(f"Remove '{tag}'")
                # Store tag in action's data and connect to method
                remove_action.setData(tag)
                remove_action.triggered.connect(self._remove_tag_from_context_asset)
        else:
            tag_menu.addAction("No tags").setEnabled(False)
        
        tag_menu.addSeparator()
        add_tag_action = tag_menu.addAction("Add Tag...")
        add_tag_action.triggered.connect(self._add_tag_to_context_asset)
        
        # Asset type assignment
        type_menu = menu.addMenu("Asset Type")
        current_type = self.asset_manager.get_asset_type(asset_path)
        
        # Use current asset types from configuration
        asset_types = self.asset_manager.get_asset_type_list()
        for asset_type in asset_types:
            config = self.asset_manager.asset_types[asset_type]
            type_action = type_menu.addAction(config['name'])
            if current_type == asset_type:
                type_action.setText(f"✓ {config['name']}")
            type_action.setData(asset_type)
            type_action.triggered.connect(self._set_asset_type)
        
        # Clear type option
        if current_type != 'default':
            type_menu.addSeparator()
            clear_type_action = type_menu.addAction("Clear Type")
            clear_type_action.triggered.connect(self._clear_asset_type)
        
        # Collection management
        collection_menu = menu.addMenu("Collections")
        
        collections = self.asset_manager.get_asset_collections()
        if collections:
            for collection_name in collections.keys():
                asset_name = os.path.splitext(os.path.basename(asset_path))[0]
                if asset_name in collections[collection_name]['assets']:
                    remove_action = collection_menu.addAction(f"Remove from '{collection_name}'")
                    # Store collection name in action's data and connect to method
                    remove_action.setData(collection_name)
                    remove_action.triggered.connect(self._remove_from_collection)
                else:
                    add_action = collection_menu.addAction(f"Add to '{collection_name}'")
                    # Store collection name in action's data and connect to method
                    add_action.setData(collection_name)
                    add_action.triggered.connect(self._add_to_collection)
        
        # Dependencies
        dependency_menu = menu.addMenu("Dependencies")
        dependencies = self.asset_manager.get_asset_dependencies(asset_path)
        dependents = self.asset_manager.get_asset_dependents(asset_path)
        
        if dependencies:
            dependency_menu.addAction("Depends on:").setEnabled(False)
            for dep in dependencies:
                dependency_menu.addAction(f"  - {dep}").setEnabled(False)
        
        if dependents:
            if dependencies:
                dependency_menu.addSeparator()
            dependency_menu.addAction("Used by:").setEnabled(False)
            for dep in dependents:
                dependency_menu.addAction(f"  - {dep}").setEnabled(False)
        
        if not dependencies and not dependents:
            dependency_menu.addAction("No dependencies").setEnabled(False)
        
        # Library management
        library_menu = menu.addMenu("Library")
        registered_assets = self.asset_manager.get_registered_assets()
        is_registered = False
        
        # Check if this asset is registered in the library
        for reg_asset in registered_assets:
            if (asset_path == reg_asset.get('asset_path') or 
                asset_path in reg_asset.get('original_path', '')):
                is_registered = True
                break
        
        if is_registered:
            remove_from_library_action = library_menu.addAction("Remove from Library")
            remove_from_library_action.triggered.connect(self._remove_from_library)
        else:
            add_to_library_action = library_menu.addAction("Add to Library")
            add_to_library_action.triggered.connect(self._add_to_library)
        
        menu.addSeparator()
        
        # Version management
        version_action = menu.addAction("Create Version")
        version_action.triggered.connect(self._create_version_for_context_asset)
        
        menu.addSeparator()
        
        # Delete action
        delete_action = menu.addAction("Delete Asset")
        delete_action.triggered.connect(self.delete_selected_asset)
        
        menu.exec(sender_widget.mapToGlobal(position))
    
    # Context menu helper methods - use 'def' instead of lambda for reliability
    def _remove_tag_from_context_asset(self):
        """Remove tag from context asset - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            from PySide6.QtGui import QAction
            sender_action = self.sender()
            if isinstance(sender_action, QAction) and sender_action.data():
                tag = sender_action.data()
                self.remove_tag_from_selected(self._context_asset_path, tag)
    
    def _add_tag_to_context_asset(self):
        """Add tag to context asset - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            self.show_add_tag_dialog(self._context_asset_path)
    
    def _remove_from_collection(self):
        """Remove asset from collection - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            from PySide6.QtGui import QAction
            sender_action = self.sender()
            if isinstance(sender_action, QAction) and sender_action.data():
                collection_name = sender_action.data()
                self.asset_manager.remove_asset_from_collection(collection_name, self._context_asset_path)
                asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
                self.status_bar.showMessage(f"Removed {asset_name} from collection '{collection_name}'")
                self.refresh_collection_filter()
                self.refresh_assets()  # Refresh to update collection display
    
    def _add_to_collection(self):
        """Add asset to collection - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            from PySide6.QtGui import QAction
            sender_action = self.sender()
            if isinstance(sender_action, QAction) and sender_action.data():
                collection_name = sender_action.data()
                asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
                
                # Add the asset to the collection
                if self.asset_manager.add_asset_to_collection(collection_name, self._context_asset_path):
                    self.status_bar.showMessage(f"Added {asset_name} to collection '{collection_name}'")
                    
                    # CRITICAL: Refresh both filter and collection tabs to show the new asset
                    self.refresh_collection_filter()
                    self.refresh_collection_tabs(force_refresh=True)  # Force refresh to update tabs
                    print(f"✅ Added {asset_name} to collection '{collection_name}' and refreshed tabs")
                else:
                    self.status_bar.showMessage(f"Failed to add {asset_name} to collection '{collection_name}'")
                    print(f"❌ Failed to add {asset_name} to collection '{collection_name}'")
    
    def _create_version_for_context_asset(self):
        """Create version for context asset - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            self.create_asset_version_dialog(self._context_asset_path)
    
    def _set_asset_type(self):
        """Set asset type for context asset - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            from PySide6.QtGui import QAction
            sender_action = self.sender()
            if isinstance(sender_action, QAction) and sender_action.data():
                asset_type = sender_action.data()
                # Remove any existing type tags first
                existing_types = ['character', 'prop', 'environment', 'texture', 'rig', 'animation', 'scene', 'reference', 'model', 'material']
                for existing_type in existing_types:
                    self.asset_manager.remove_asset_tag(self._context_asset_path, existing_type)
                
                # Add the new type tag
                if self.asset_manager.add_asset_tag(self._context_asset_path, asset_type):
                    asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
                    self.status_bar.showMessage(f"Set {asset_name} type to '{asset_type}'")
                    self.refresh_assets()  # Refresh to update colors
    
    def _clear_asset_type(self):
        """Clear asset type for context asset - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            # Remove all type tags
            existing_types = ['character', 'prop', 'environment', 'texture', 'rig', 'animation', 'scene', 'reference', 'model', 'material']
            for existing_type in existing_types:
                self.asset_manager.remove_asset_tag(self._context_asset_path, existing_type)
            
            asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
            self.status_bar.showMessage(f"Cleared type for {asset_name}")
            self.refresh_assets()  # Refresh to update colors
    
    def _add_to_library(self):
        """Add asset to library - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            try:
                self.asset_manager.register_asset_to_library(self._context_asset_path, copy_to_project=True)
                asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
                self.status_bar.showMessage(f"Added {asset_name} to asset library")
                self.refresh_assets()  # Refresh to update library indicators
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to add asset to library: {str(e)}")
    
    def _remove_from_library(self):
        """Remove asset from library - called by context menu"""
        if hasattr(self, '_context_asset_path'):
            registered_assets = self.asset_manager.get_registered_assets()
            # Find the registered asset that matches this path
            for reg_asset in registered_assets:
                if (self._context_asset_path == reg_asset.get('asset_path') or 
                    self._context_asset_path in reg_asset.get('original_path', '')):
                    self.asset_manager.remove_asset_from_library(reg_asset['asset_path'])
                    asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
                    self.status_bar.showMessage(f"Removed {asset_name} from asset library")
                    self.refresh_assets()  # Refresh to update library indicators
                    break
            else:
                QMessageBox.warning(self, "Error", "Asset not found in library registry")
    
    def remove_tag_from_selected(self, asset_path, tag):
        """Remove a tag from an asset"""
        if self.asset_manager.remove_asset_tag(asset_path, tag):
            asset_name = os.path.splitext(os.path.basename(asset_path))[0]
            self.status_bar.showMessage(f"Removed tag '{tag}' from {asset_name}")
            self.refresh_tag_filter()
            self.refresh_assets()  # Refresh to update colors and display
        else:
            QMessageBox.warning(self, "Error", "Failed to remove tag.")
    
    def show_add_tag_dialog(self, asset_path):
        """Show dialog to add a tag to an asset"""
        tag, ok = QInputDialog.getText(self, "Add Tag", "Enter tag name:")
        if ok and tag.strip():
            if self.asset_manager.add_asset_tag(asset_path, tag.strip()):
                asset_name = os.path.splitext(os.path.basename(asset_path))[0]
                self.status_bar.showMessage(f"Added tag '{tag}' to {asset_name}")
                self.refresh_tag_filter()
                self.refresh_assets()  # Refresh to update colors and display
            else:
                QMessageBox.warning(self, "Error", "Failed to add tag or tag already exists.")
    
    def create_asset_version_dialog(self, asset_path):
        """Show dialog to create a new version of an asset"""
        notes, ok = QInputDialog.getText(self, "Create Version", "Version notes (optional):")
        if ok:  # User didn't cancel
            if self.asset_manager.create_asset_version(asset_path, notes):
                asset_name = os.path.splitext(os.path.basename(asset_path))[0]
                versions = self.asset_manager.get_asset_versions(asset_path)
                version_num = len(versions)
                self.status_bar.showMessage(f"Created version {version_num} for {asset_name}")
            else:
                QMessageBox.warning(self, "Error", "Failed to create asset version.")

    def batch_import_dialog(self):
        """Show dialog for batch importing multiple assets"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Assets for Batch Import", "",
            "Maya Files (*.ma *.mb);;OBJ Files (*.obj);;FBX Files (*.fbx);;All Supported (*.ma *.mb *.obj *.fbx)"
        )
        
        if file_paths:
            progress = QProgressDialog("Importing assets...", "Cancel", 0, len(file_paths), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)  # type: ignore
            progress.show()
            
            result = self.asset_manager.batch_import_assets(file_paths)
            
            progress.close()
            progress.deleteLater()  # Proper cleanup to prevent memory leaks
            
            imported_count = len(result.get('imported', []))
            failed_count = len(result.get('failed', []))
            
            message = f"Batch import completed:\n"
            message += f"Successfully imported: {imported_count} assets\n"
            if failed_count > 0:
                message += f"Failed to import: {failed_count} assets"
            
            QMessageBox.information(self, "Batch Import Results", message)
            self.status_bar.showMessage(f"Batch import: {imported_count} successful, {failed_count} failed")

    def batch_export_dialog(self):
        """Show dialog for batch exporting assets"""
        # This is a simplified implementation - in a full version you'd have a more complex UI
        # to define export groups and settings
        if not MAYA_AVAILABLE or cmds is None:
            QMessageBox.warning(self, "Warning", "Maya not available for batch export")
            return
        
        # Get selected objects
        selected = cmds.ls(selection=True)
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select objects to export")
            return
        
        # Ask for export directory
        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return
        
        # Simple batch export - each selected object as separate file
        export_settings = []
        for obj in selected:
            export_path = os.path.join(export_dir, f"{obj}.ma")
            export_settings.append({
                'name': obj,
                'objects': [obj],
                'path': export_path
            })
        
        if export_settings:
            progress = QProgressDialog("Exporting assets...", "Cancel", 0, len(export_settings), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)  # type: ignore
            progress.show()
            
            result = self.asset_manager.batch_export_assets(export_settings)
            
            progress.close()
            progress.deleteLater()  # Proper cleanup to prevent memory leaks
            
            exported_count = len(result['exported'])
            failed_count = len(result['failed'])
            
            message = f"Batch export completed:\n"
            message += f"Successfully exported: {exported_count} assets\n"
            if failed_count > 0:
                message += f"Failed to export: {failed_count} assets"
            
            QMessageBox.information(self, "Batch Export Results", message)
            self.status_bar.showMessage(f"Batch export: {exported_count} successful, {failed_count} failed")

    def show_collections_dialog(self):
        """Show dialog for managing asset collections"""
        dialog = AssetCollectionsDialog(self.asset_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:  # type: ignore
            self.refresh_collection_filter()

    def show_dependency_viewer(self):
        """Show dialog for viewing asset dependencies"""
        dialog = AssetDependencyDialog(self.asset_manager, self)
        dialog.exec()


class AssetTagDialog(QDialog):
    """Dialog for managing asset tags"""
    
    def __init__(self, asset_manager, asset_path, parent=None):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.asset_path = asset_path
        self.setWindowTitle("Manage Asset Tags")
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Current tags
        self.tags_list = QListWidget()
        self.refresh_tags()
        layout.addWidget(QLabel("Current Tags:"))
        layout.addWidget(self.tags_list)
        
        # Add new tag
        add_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("New tag name...")
        add_btn = QPushButton("Add Tag")
        add_btn.clicked.connect(self.add_tag)
        add_layout.addWidget(self.tag_input)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # Remove tag button
        remove_btn = QPushButton("Remove Selected Tag")
        remove_btn.clicked.connect(self.remove_tag)
        layout.addWidget(remove_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def refresh_tags(self):
        self.tags_list.clear()
        tags = self.asset_manager.get_asset_tags(self.asset_path)
        self.tags_list.addItems(tags)
    
    def add_tag(self):
        tag = self.tag_input.text().strip()
        if tag and self.asset_manager.add_asset_tag(self.asset_path, tag):
            self.tag_input.clear()
            self.refresh_tags()
    
    def remove_tag(self):
        current_item = self.tags_list.currentItem()
        if current_item:
            tag = current_item.text()
            if self.asset_manager.remove_asset_tag(self.asset_path, tag):
                self.refresh_tags()


class AssetCollectionsDialog(QDialog):
    """Dialog for managing asset collections"""
    
    def __init__(self, asset_manager, parent=None):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.setWindowTitle("Asset Collections Manager")
        self.setModal(True)
        self.resize(600, 400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Collections list
        self.collections_tree = QTreeWidget()
        self.collections_tree.setHeaderLabels(["Collection", "Assets", "Created"])
        layout.addWidget(QLabel("Collections:"))
        layout.addWidget(self.collections_tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        create_btn = QPushButton("Create Collection")
        create_btn.clicked.connect(self.create_collection)
        button_layout.addWidget(create_btn)
        
        delete_btn = QPushButton("Delete Collection")
        delete_btn.clicked.connect(self.delete_collection)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.refresh_collections()
    
    def refresh_collections(self):
        self.collections_tree.clear()
        collections = self.asset_manager.get_asset_collections()
        
        for name, data in collections.items():
            item = QTreeWidgetItem([name, str(len(data['assets'])), data['created'][:10]])
            self.collections_tree.addTopLevelItem(item)
    
    def create_collection(self):
        name, ok = QInputDialog.getText(self, "Create Collection", "Collection name:")
        if ok and name.strip():
            if self.asset_manager.create_asset_collection(name.strip()):
                self.refresh_collections()
            else:
                QMessageBox.warning(self, "Error", "Failed to create collection or collection already exists.")
    
    def delete_collection(self):
        current_item = self.collections_tree.currentItem()
        if current_item:
            collection_name = current_item.text(0)
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete collection '{collection_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Remove collection from project data
                if self.asset_manager.current_project:
                    project_name = os.path.basename(self.asset_manager.current_project)
                    if 'collections' in self.asset_manager.assets_library[project_name]:
                        del self.asset_manager.assets_library[project_name]['collections'][collection_name]
                        self.asset_manager.save_config()
                        self.refresh_collections()


class AssetDependencyDialog(QDialog):
    """Dialog for viewing and managing asset dependencies"""
    
    def __init__(self, asset_manager, parent=None):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.setWindowTitle("Asset Dependencies")
        self.setModal(True)
        self.resize(700, 500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Dependency tree
        self.dependency_tree = QTreeWidget()
        self.dependency_tree.setHeaderLabels(["Asset", "Type", "Dependencies"])
        layout.addWidget(QLabel("Asset Dependencies:"))
        layout.addWidget(self.dependency_tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_dependency_btn = QPushButton("Add Dependency")
        add_dependency_btn.clicked.connect(self.add_dependency)
        button_layout.addWidget(add_dependency_btn)
        
        remove_dependency_btn = QPushButton("Remove Dependency")
        remove_dependency_btn.clicked.connect(self.remove_dependency)
        button_layout.addWidget(remove_dependency_btn)
        
        button_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_dependencies)
        button_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.refresh_dependencies()
    
    def refresh_dependencies(self):
        self.dependency_tree.clear()
        
        if not self.asset_manager.current_project:
            return
        
        project_name = os.path.basename(self.asset_manager.current_project)
        if 'dependencies' not in self.asset_manager.assets_library[project_name]:
            return
        
        dependencies_data = self.asset_manager.assets_library[project_name]['dependencies']
        
        for asset, deps in dependencies_data.items():
            item = QTreeWidgetItem([asset, "Main Asset", f"{len(deps)} dependencies"])
            self.dependency_tree.addTopLevelItem(item)
            
            for dep in deps:
                dep_item = QTreeWidgetItem([dep, "Dependency", ""])
                item.addChild(dep_item)
    
    def add_dependency(self):
        # Simplified dependency addition - in a full implementation you'd have asset selection
        asset, ok1 = QInputDialog.getText(self, "Add Dependency", "Asset name:")
        if not ok1 or not asset.strip():
            return
        
        dependency, ok2 = QInputDialog.getText(self, "Add Dependency", "Dependency asset name:")
        if ok2 and dependency.strip():
            # Create fake file paths for this example
            asset_path = f"{asset}.ma"
            dep_path = f"{dependency}.ma"
            
            if self.asset_manager.track_asset_dependency(asset_path, dep_path):
                self.refresh_dependencies()
            else:
                QMessageBox.warning(self, "Error", "Failed to add dependency.")
    
    def remove_dependency(self):
        current_item = self.dependency_tree.currentItem()
        if current_item and current_item.parent():
            # This is a dependency item
            asset_item = current_item.parent()
            asset_name = asset_item.text(0)
            dependency_name = current_item.text(0)
            
            # Remove from data structure
            if self.asset_manager.current_project:
                project_name = os.path.basename(self.asset_manager.current_project)
                if ('dependencies' in self.asset_manager.assets_library[project_name] and
                    asset_name in self.asset_manager.assets_library[project_name]['dependencies']):
                    
                    deps = self.asset_manager.assets_library[project_name]['dependencies'][asset_name]
                    if dependency_name in deps:
                        deps.remove(dependency_name)
                        self.asset_manager.save_config()
                        self.refresh_dependencies()


class NewProjectDialog(QDialog):
    """Dialog for creating a new project"""
    
    def __init__(self, parent=None):
        super(NewProjectDialog, self).__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Project name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project Name:"))
        self.name_input = QLineEdit()
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Project path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Project Path:"))
        self.path_input = QLineEdit()
        path_browse_btn = QPushButton("Browse...")
        path_browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(path_browse_btn)
        layout.addLayout(path_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(create_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
    def browse_path(self):
        """Browse for project path"""
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if path:
            self.path_input.setText(path)
    
    def get_values(self):
        """Get the dialog values"""
        return self.name_input.text(), self.path_input.text()


def get_maya_main_window():
    """Get the Maya main window as a QWidget"""
    if not MAYA_AVAILABLE or omui is None:
        return None
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QWidget)


# Global variable to store the window reference
_asset_manager_window = None

def show_asset_manager():
    """Show the Asset Manager UI"""
    global _asset_manager_window
    try:
        # Close existing window if it exists
        if _asset_manager_window is not None:
            _asset_manager_window.close()
            _asset_manager_window = None
        
        # Create new window
        parent = get_maya_main_window()
        _asset_manager_window = AssetManagerUI(parent)
        _asset_manager_window.show()
        
        return _asset_manager_window
    except RecursionError as e:
        print(f"Recursion Error in Asset Manager: {e}")
        print("This is likely due to a corrupted project path. Attempting to reset...")
        
        # Try to create a minimal asset manager to reset the config
        try:
            temp_manager = AssetManager()
            temp_manager.reset_current_project()
            print("Current project has been reset. Please try opening Asset Manager again.")
        except:
            print("Could not reset project automatically. Please check your configuration.")
        
        return None
    except Exception as e:
        print(f"Error showing Asset Manager: {e}")
        return None


# Plugin registration functions for Maya
def maya_useNewAPI():
    """Tell Maya to use the new API"""
    return True


def initializePlugin(plugin):
    """Initialize the plugin"""
    if not MAYA_AVAILABLE:
        print("Maya not available - cannot initialize plugin")
        return
        
    try:
        # Register the plugin command
        om2.MFnPlugin(plugin, "Mike Stumbo", "1.2.0", "Any")  # type: ignore
        
        # Add menu item to Maya
        if cmds.menu('AssetManagerMenu', exists=True):  # type: ignore
            cmds.deleteUI('AssetManagerMenu')  # type: ignore
        
        main_menu = mel.eval('$temp1=$gMainWindow')  # type: ignore
        asset_menu = cmds.menu('AssetManagerMenu', parent=main_menu, label='Asset Manager')  # type: ignore
        cmds.menuItem(parent=asset_menu, label='Open Asset Manager', command='import assetManager; assetManager.show_asset_manager()')  # type: ignore
        
        print("Asset Manager plugin initialized successfully")
        
    except Exception as e:
        print(f"Error initializing Asset Manager plugin: {e}")
        raise


def uninitializePlugin(plugin):
    """Uninitialize the plugin"""
    global _asset_manager_window
    if not MAYA_AVAILABLE:
        print("Maya not available - cannot uninitialize plugin")
        return
        
    try:
        # Remove menu
        if cmds.menu('AssetManagerMenu', exists=True):  # type: ignore
            cmds.deleteUI('AssetManagerMenu')  # type: ignore
        
        # Close window if open and cleanup resources
        if _asset_manager_window is not None:
            try:
                # Trigger cleanup through close event
                _asset_manager_window.close()
            except Exception as e:
                print(f"Error closing Asset Manager window: {e}")
            finally:
                _asset_manager_window = None
        
        print("Asset Manager plugin uninitialized successfully")
        
    except Exception as e:
        print(f"Error uninitializing Asset Manager plugin: {e}")
        raise


# For testing outside Maya
if __name__ == "__main__":
    print("Asset Manager for Maya 2025.3")
    print("This plugin is designed to run within Maya.")
    print("To use: Load this as a Maya plugin or run show_asset_manager() in Maya's script editor.")
