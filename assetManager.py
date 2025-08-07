# -*- coding: utf-8 -*-
"""
Asset Manager Plugin for Maya 2025.3
A comprehensive asset management system for Maya using Python 3 and PySide6

Author: Mike Stumbo
Version: 1.1.3
Maya Version: 2025.3+

New in v1.1.3:
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
- UI now uses colorful file-type thumbnails with text labels for better visualization

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
from datetime import datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import maya.cmds as cmds # type: ignore
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
    from PySide6.QtGui import QAction, QIcon, QPixmap, QFont, QColor, QBrush, QPainter, QPen
    from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, QFileSystemWatcher, QObject, QPoint
    from shiboken6 import wrapInstance
except ImportError:
    print("PySide6 not available. Please ensure Maya 2025.3+ is being used.")
    sys.exit(1)


class AssetManager:
    """Main Asset Manager class handling core functionality"""
    
    def __init__(self):
        self.plugin_name = "assetManager"
        self.version = "1.1.3"
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
        
        # Load configuration (including custom asset types)
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
                'extensions': ['.jpg', '.png', '.tga', '.exr', '.tif', '.tiff'],
                'description': 'Texture maps and images'
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
        """Get cached file list with timeout to improve network performance"""
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
            
            # Use os.scandir for better performance than os.listdir
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_file() and any(entry.name.lower().endswith(ext) for ext in supported_extensions):
                        files.append(entry.path)
            
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
        """Generate thumbnail with real Maya scene preview and memory-safe approach"""
        try:
            # Force consistent thumbnail size across the application
            if size is None:
                size = (64, 64)  # Standard thumbnail size
            
            # Ensure we always use exactly 64x64 to prevent sizing issues
            size = (64, 64)
            
            # Use absolute path for consistent caching across different calling contexts
            abs_path = os.path.abspath(file_path)
            
            # Check cache first - PREVENT DUPLICATE GENERATION
            cache_key = f"{abs_path}_64x64"  # Fixed cache key for consistency
            if cache_key in self._thumbnail_cache:
                # Cache hit - return existing thumbnail without generating new one
                return self._thumbnail_cache[cache_key]
            
            # Check if we're already generating this thumbnail to prevent race conditions
            if not hasattr(self, '_generating_thumbnails'):
                self._generating_thumbnails = set()
                
            if cache_key in self._generating_thumbnails:
                # Already being generated - return empty pixmap to prevent duplicate generation
                print(f"Thumbnail already being generated for {os.path.basename(file_path)}")
                return QPixmap(64, 64)  # Return blank thumbnail temporarily
                
            # Mark as being generated
            self._generating_thumbnails.add(cache_key)
            
            try:
                # Check cache size limit to prevent memory bloat
                if len(self._thumbnail_cache) >= self._thumbnail_cache_size_limit:
                    # Remove oldest entries (simple FIFO strategy)
                    oldest_key = next(iter(self._thumbnail_cache))
                    del self._thumbnail_cache[oldest_key]
                    print(f"Cache size limit reached, removed: {oldest_key}")
                
                # Generate real preview thumbnail based on file type
                file_ext = os.path.splitext(file_path)[1].lower()
                pixmap = self._generate_real_thumbnail(file_path, file_ext, size)
                
                # Cache the result with consistent key - SINGLE SOURCE OF TRUTH
                self._thumbnail_cache[cache_key] = pixmap
                print(f"Generated and cached thumbnail for {os.path.basename(file_path)}")
                
                return pixmap
                
            finally:
                # Always remove from generating set when done
                self._generating_thumbnails.discard(cache_key)
            
        except Exception as e:
            print(f"Error generating thumbnail for {file_path}: {e}")
            # Clean up generating set on error
            cache_key = f"{os.path.abspath(file_path)}_64x64"
            if hasattr(self, '_generating_thumbnails') and cache_key in self._generating_thumbnails:
                self._generating_thumbnails.discard(cache_key)
            # Return fallback thumbnail on error
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
        """Generate thumbnail preview of Maya scene content"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            
            # Create QPixmap for thumbnail
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(QColor(45, 45, 45))  # Dark gray background
            
            # Save current scene state
            current_scene = cmds.file(q=True, sceneName=True)
            
            try:
                # Import/reference the file temporarily to generate preview
                if os.path.exists(file_path):
                    # Create new scene for thumbnail generation
                    cmds.file(new=True, force=True)
                    
                    # Import the file
                    if file_path.endswith('.ma'):
                        cmds.file(file_path, i=True, type="mayaAscii", ignoreVersion=True)
                    else:  # .mb
                        cmds.file(file_path, i=True, type="mayaBinary", ignoreVersion=True)
                    
                    # Get all geometry in scene
                    all_meshes = cmds.ls(type='mesh', long=True) or []
                    
                    if all_meshes:
                        # Frame all geometry for thumbnail
                        cmds.select(all_meshes)
                        cmds.viewFit(allObjects=True)
                        
                        # Generate preview using playblast
                        thumbnail_path = self._generate_maya_playblast_thumbnail(file_path, size)
                        if thumbnail_path and os.path.exists(thumbnail_path):
                            pixmap.load(thumbnail_path)
                            # Clean up temp thumbnail file
                            try:
                                os.remove(thumbnail_path)
                            except:
                                pass
                        else:
                            # Fallback to rendered thumbnail
                            pixmap = self._generate_rendered_maya_thumbnail(size, all_meshes)
                    else:
                        # No geometry - create text thumbnail
                        pixmap = self._generate_text_thumbnail("MAYA\nSCENE", QColor(100, 150, 255), size)
                        
            finally:
                # Restore original scene
                try:
                    if current_scene:
                        cmds.file(current_scene, open=True, force=True)
                    else:
                        cmds.file(new=True, force=True)
                except:
                    # If restore fails, at least create new scene
                    cmds.file(new=True, force=True)
            
            return pixmap
            
        except Exception as e:
            print(f"Error generating Maya scene thumbnail: {e}")
            return self._generate_text_thumbnail("MAYA\nERROR", QColor(255, 100, 100), size)
    
    def _generate_maya_playblast_thumbnail(self, file_path, size):
        """Generate thumbnail using Maya's playblast for real scene preview"""
        try:
            import maya.cmds as cmds # pyright: ignore[reportMissingImports]
            import tempfile
            
            # Create temporary directory for thumbnail
            temp_dir = tempfile.mkdtemp(prefix="maya_thumb_")
            thumb_name = f"thumb_{os.path.basename(file_path)}"
            thumb_path = os.path.join(temp_dir, thumb_name)
            
            # Set up viewport for thumbnail
            current_panel = cmds.getPanel(withFocus=True)
            if 'modelPanel' not in current_panel:
                model_panels = cmds.getPanel(type='modelPanel')
                if model_panels:
                    current_panel = model_panels[0]
            
            if 'modelPanel' in current_panel:
                # Configure viewport for clean thumbnail
                cmds.modelEditor(current_panel, edit=True, 
                               displayAppearance='smoothShaded',
                               wireframeOnShaded=False,
                               displayLights='default',
                               shadows=False,
                               useDefaultMaterial=False,
                               grid=False,
                               handles=False,
                               manipulators=False)
                
                # Generate playblast thumbnail
                cmds.playblast(
                    frame=1,
                    format='image',
                    compression='png',
                    quality=70,
                    percent=100,
                    width=size[0] * 2,  # Generate at 2x for better quality
                    height=size[1] * 2,
                    viewer=False,
                    showOrnaments=False,
                    filename=thumb_path
                )
                
                # Return the generated thumbnail path
                generated_files = [f for f in os.listdir(temp_dir) if f.startswith(thumb_name)]
                if generated_files:
                    return os.path.join(temp_dir, generated_files[0])
            
            return None
            
        except Exception as e:
            print(f"Error generating playblast thumbnail: {e}")
            return None
    
    def _generate_rendered_maya_thumbnail(self, size, meshes):
        """Generate rendered thumbnail when playblast fails"""
        try:
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(QColor(60, 60, 80))  # Dark blue-gray background
            
            painter = QPainter(pixmap)
            
            # Draw wireframe representation
            painter.setPen(QPen(QColor(150, 200, 255), 1))  # Light blue lines
            
            # Draw simple wireframe pattern
            mesh_count = len(meshes)
            for i in range(min(mesh_count, 8)):  # Max 8 objects for clarity
                x_offset = (i % 3) * 15 + 10
                y_offset = (i // 3) * 15 + 10
                
                # Draw simple cube wireframe
                painter.drawRect(x_offset, y_offset, 12, 12)
                painter.drawLine(x_offset, y_offset, x_offset + 3, y_offset - 3)
                painter.drawLine(x_offset + 12, y_offset, x_offset + 15, y_offset - 3)
                painter.drawLine(x_offset + 12, y_offset + 12, x_offset + 15, y_offset + 9)
                painter.drawRect(x_offset + 3, y_offset - 3, 12, 12)
            
            # Add file type label
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPixelSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(5, size[1] - 5, f"{mesh_count} objects")
            
            painter.end()
            return pixmap
            
        except Exception as e:
            print(f"Error generating rendered Maya thumbnail: {e}")
            return self._generate_text_thumbnail("MAYA", QColor(100, 150, 255), size)
    
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
                'version': self.version
            }
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
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
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(600, 400)
        
        # Set window flags for Maya integration
        self.setWindowFlags(Qt.WindowType.Window)  # type: ignore
        
        # Set window icon (tab bar icon)
        self.set_window_icon()
        
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
        
        # Set splitter proportions
        content_splitter.setSizes([250, 550])
        
        # Status bar
        self.create_status_bar()
    
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
        
        # Create tab widget for asset views
        self.tab_widget = QTabWidget()
        right_layout.addWidget(self.tab_widget)
        
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
        
        # Add collection tab management buttons
        actions_layout.addStretch()
        
        add_collection_tab_btn = QPushButton("+ Collection Tab")
        add_collection_tab_btn.clicked.connect(self.add_collection_tab_dialog)
        actions_layout.addWidget(add_collection_tab_btn)
        
        refresh_tabs_btn = QPushButton("Refresh Tabs")
        refresh_tabs_btn.clicked.connect(self.refresh_collection_tabs)
        actions_layout.addWidget(refresh_tabs_btn)
        
        right_layout.addLayout(actions_layout)
        
        return right_widget
    
    def create_main_asset_tab(self):
        """Create the main 'All Assets' tab"""
        # Asset library widget
        library_widget = QWidget()
        library_layout = QVBoxLayout(library_widget)
        
        # Asset list
        self.asset_list = QListWidget()
        
        # Configure consistent thumbnail sizing to prevent double-sized thumbnails
        self.asset_list.setIconSize(QSize(64, 64))
        self.asset_list.setGridSize(QSize(80, 80))  # Grid slightly larger than icon
        self.asset_list.setViewMode(QListWidget.ViewMode.IconMode)  # type: ignore
        self.asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)  # type: ignore
        self.asset_list.setUniformItemSizes(True)  # Prevent size variations
        self.asset_list.setMovement(QListWidget.Movement.Static)  # Prevent layout changes
        self.asset_list.itemDoubleClicked.connect(self.import_selected_asset)
        
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
        
        # Configure consistent thumbnail sizing to prevent double-sized thumbnails
        collection_asset_list.setIconSize(QSize(64, 64))
        collection_asset_list.setGridSize(QSize(80, 80))  # Grid slightly larger than icon
        collection_asset_list.setViewMode(QListWidget.ViewMode.IconMode)  # type: ignore
        collection_asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)  # type: ignore
        collection_asset_list.setUniformItemSizes(True)  # Prevent size variations
        collection_asset_list.setMovement(QListWidget.Movement.Static)  # Prevent layout changes
        collection_asset_list.itemDoubleClicked.connect(self.import_selected_asset)
        
        # Enable context menu
        collection_asset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore
        collection_asset_list.customContextMenuRequested.connect(self.show_asset_context_menu)
        
        # Populate collection assets
        self.populate_collection_assets(collection_asset_list, collection_data.get('assets', []))
        
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
        
        if not self.asset_manager.current_project:
            return
            
        project_path = self.asset_manager.current_project
        if not os.path.exists(project_path):
            return
        
        # Use cached file list for better network performance
        try:
            asset_files = self.asset_manager._get_cached_file_list(project_path)
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
        for file_path in asset_files:
            if progress and progress.wasCanceled():
                break
            
            asset_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Only add if this asset is in the collection
            if asset_name in asset_names:
                try:
                    # Create enhanced display text
                    display_text = self._create_asset_display_text(asset_name, file_path)
                    
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, file_path)  # type: ignore
                    
                    # Set background color based on asset type
                    asset_color = self.asset_manager.get_asset_type_color(file_path)
                    item.setBackground(QBrush(asset_color))
                    
                    # Try to load thumbnail with lazy loading for better performance
                    self._set_asset_item_icon(item, file_path)
                    
                    asset_list_widget.addItem(item)
                    
                    items_processed += 1
                    if progress:
                        progress.setValue(items_processed)
                        if items_processed % 10 == 0:  # Update UI every 10 items
                            QApplication.processEvents()
                
                except Exception as e:
                    print(f"Error processing asset {asset_name}: {e}")
                    continue
        
        if progress:
            progress.close()
            progress.deleteLater()  # Proper cleanup to prevent memory leaks
    
    def _set_asset_item_icon(self, item, file_path):
        """Set icon for asset item with consistent thumbnail sizing"""
        try:
            # Use the asset manager's thumbnail system
            thumbnail_icon = self.asset_manager._get_thumbnail_icon(file_path)
            if thumbnail_icon and not thumbnail_icon.isNull():
                # Ensure consistent icon size when setting on item
                item.setIcon(thumbnail_icon)
                # Force the item to use exactly the icon size we want
                item.setSizeHint(QSize(80, 80))  # Match grid size for consistency
            else:
                # Fallback to file type icons
                self._set_fallback_icon(item, file_path)
                
        except Exception as e:
            print(f"Error setting asset icon for {file_path}: {e}")
            # Set fallback icon on error
            self._set_fallback_icon(item, file_path)
    
    def _set_fallback_icon(self, item, file_path):
        """Set fallback file type icon with consistent sizing"""
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
        # Ensure consistent size hint for fallback icons too
        item.setSizeHint(QSize(80, 80))
    
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
        """Safely refresh asset list without triggering collection filter recursion"""
        try:
            # Clear main asset list
            if hasattr(self, 'main_asset_list'):
                self.main_asset_list.clear()
            elif hasattr(self, 'asset_list'):
                self.asset_list.clear()
            else:
                return
            
            if not self.asset_manager.current_project:
                return
            
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
                    if os.path.exists(asset_path):
                        display_text = self._create_asset_display_text(asset_name, asset_path, is_registered=True)
                        item = QListWidgetItem(display_text)
                        item.setData(Qt.ItemDataRole.UserRole, asset_path)  # type: ignore
                        
                        # Set background color and icon safely
                        try:
                            asset_color = self.asset_manager.get_asset_type_color(asset_path)
                            item.setBackground(QBrush(asset_color))
                        except:
                            pass
                        
                        # Add to main list
                        if hasattr(self, 'main_asset_list'):
                            self.main_asset_list.addItem(item)
                        elif hasattr(self, 'asset_list'):
                            self.asset_list.addItem(item)
                except Exception as e:
                    print(f"Error adding registered asset {asset_name}: {e}")
                    continue
                
        except Exception as e:
            print(f"Error in _refresh_asset_list_safe: {e}")

    def refresh_assets(self):
        """Refresh the asset library with enhanced thumbnail support"""
          # CRITICAL: Add recursion protection
        if hasattr(self, '_refreshing_assets') and self._refreshing_assets:
            print("Warning: Blocking recursive refresh_assets call")
            return

        try:
            self._refreshing_assets = True
          
            # Clear main asset list
            if hasattr(self, 'main_asset_list'):
                self.main_asset_list.clear()
            elif hasattr(self, 'asset_list'):
                self.asset_list.clear()
            else:
                registered_assets = {}
                return
            
            if not self.asset_manager.current_project:
                registered_assets = {}
                return
            
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
                    if asset_path and os.path.exists(asset_path):
                        display_text = self._create_asset_display_text(asset_name, asset_path, is_registered=True)
                        item = QListWidgetItem(display_text)
                        item.setData(Qt.ItemDataRole.UserRole, asset_path)  # type: ignore
                        
                        # Set background color and icon safely
                        try:
                            asset_color = self.asset_manager.get_asset_type_color(asset_path)
                            item.setBackground(QBrush(asset_color))
                        except:
                            pass
                        
                        # Add to main list
                        current_asset_list = getattr(self, 'main_asset_list', None) or getattr(self, 'asset_list', None)
                        if current_asset_list:
                            current_asset_list.addItem(item)
                except Exception as e:
                    print(f"Error adding registered asset {asset_name}: {e}")
                    continue
            
            # Scan project directory for assets (avoiding recursion)
            project_path = self.asset_manager.current_project
            if project_path and os.path.exists(project_path):
                try:
                    registered_paths = {info.get('path', '') for info in registered_assets.values()}
                    
                    for root, dirs, files in os.walk(project_path):
                        for file in files:
                            if file.lower().endswith(('.ma', '.mb', '.obj', '.fbx')):
                                file_path = os.path.join(root, file)
                                
                                # Skip if already registered
                                if file_path in registered_paths:
                                    continue
                                
                                try:
                                    asset_name = os.path.splitext(file)[0]
                                    display_text = self._create_asset_display_text(asset_name, file_path, is_registered=False)
                                    
                                    item = QListWidgetItem(display_text)
                                    item.setData(Qt.ItemDataRole.UserRole, file_path)  # type: ignore
                                    
                                    # Set background color safely
                                    try:
                                        asset_color = self.asset_manager.get_asset_type_color(file_path)
                                        item.setBackground(QBrush(asset_color))
                                    except:
                                        pass
                                    
                                    # Add to main list
                                    current_asset_list = getattr(self, 'main_asset_list', None) or getattr(self, 'asset_list', None)
                                    if current_asset_list:
                                        current_asset_list.addItem(item)
                                except Exception as e:
                                    print(f"Error adding asset {file}: {e}")
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
            registered_assets = {}
        finally:
            self._refreshing_assets = False
            if 'registered_assets' not in locals():
                registered_assets = {}
        
        # Add registered assets first (with priority display)
        for asset_name, asset_info in registered_assets.items():
            file_path = asset_info['path']
            
            # Check if file still exists
            if not os.path.exists(file_path):
                continue
            
            # Create enhanced display text with library indicator
            display_text = self._create_asset_display_text(asset_name, file_path, is_registered=True)
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, file_path)  # type: ignore
            
            # Set background color based on asset type
            asset_color = self.asset_manager.get_asset_type_color(file_path)
            item.setBackground(QBrush(asset_color))
            
            # Make registered assets slightly bolder
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            
            # Set icon using new thumbnail system
            self._set_asset_item_icon(item, file_path)
            
            # Add to main asset list
            if hasattr(self, 'main_asset_list'):
                self.main_asset_list.addItem(item)
            elif hasattr(self, 'asset_list'):
                self.asset_list.addItem(item)
            
          # Scan for assets in the current project (that aren't already registered)
        project_path = self.asset_manager.current_project
        if project_path and os.path.exists(project_path):
            supported_extensions = ['.ma', '.mb', '.obj', '.fbx']
            registered_paths = {info['path'] for info in registered_assets.values()}
          
            for root, dirs, files in os.walk(project_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in supported_extensions):
                        file_path = os.path.join(root, file)
                        
                        # Skip if already registered
                        if file_path in registered_paths:
                            continue
                            
                        asset_name = os.path.splitext(file)[0]
                        
                        # Create enhanced display text
                        display_text = self._create_asset_display_text(asset_name, file_path, is_registered=False)
                        
                        item = QListWidgetItem(display_text)
                        item.setData(Qt.ItemDataRole.UserRole, file_path)  # type: ignore
                        
                        # Set background color based on asset type
                        asset_color = self.asset_manager.get_asset_type_color(file_path)
                        item.setBackground(QBrush(asset_color))
                        
                        # Set icon using new thumbnail system
                        self._set_asset_item_icon(item, file_path)
                        
                        # Add to main asset list
                        if hasattr(self, 'main_asset_list'):
                            self.main_asset_list.addItem(item)
                        elif hasattr(self, 'asset_list'):
                            self.asset_list.addItem(item)
        
        # Update tag and collection filters
        self.refresh_tag_filter()
        self.refresh_collection_filter()
        
        # Refresh collection tabs if they exist
        if hasattr(self, 'tab_widget'):
            self.refresh_collection_tabs()
        
        # Update file watcher for new project
        self._setup_file_watcher()
  
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
            self.refresh_collection_filter()
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
                self.asset_manager.add_asset_to_collection(collection_name, self._context_asset_path)
                asset_name = os.path.splitext(os.path.basename(self._context_asset_path))[0]
                self.status_bar.showMessage(f"Added {asset_name} to collection '{collection_name}'")
                self.refresh_collection_filter()
                self.refresh_assets()  # Refresh to update collection display
    
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
        om2.MFnPlugin(plugin, "Mike Stumbo", "1.1.3", "Any")  # type: ignore
        
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
