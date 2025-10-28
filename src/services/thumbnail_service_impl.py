# -*- coding: utf-8 -*-
"""
Thumbnail Service Implementation - Maya Playblast System RESTORED
WORKING Maya viewport screenshot generation - Like v1.2.2 that actually worked!

Author: Mike Stumbo  
Version: EMSA with restored playblast functionality
"""

import os
import hashlib
import tempfile
import shutil
import time
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path

# PySide6 for Maya 2022+
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, QPen, QBrush, QLinearGradient
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QApplication

# Import dependencies using robust path resolution for Maya plugin loading
import sys
import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional, Tuple

# Add src directory to path for imports
current_file = Path(__file__).resolve()
src_dir = current_file.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Now import with fallback handling
try:
    from core.interfaces.thumbnail_service import IThumbnailService # type: ignore
    from config.constants import THUMBNAIL_CONFIG
except ImportError:
    # Create minimal interface locally if imports fail
    class IThumbnailService(ABC):
        @abstractmethod
        def generate_thumbnail(self, file_path: Path, size: Tuple[int, int] = (64, 64)) -> Optional[str]:
            pass
        
        @abstractmethod
        def get_cached_thumbnail(self, file_path: Path, size: Tuple[int, int] = (64, 64)) -> Optional[str]:
            pass
        
        @abstractmethod
        def is_thumbnail_supported(self, file_path: Path) -> bool:
            pass
    
    # Create minimal config locally if imports fail
    class ThumbnailConfig:
        def __init__(self):
            self.DEFAULT_SIZE = (64, 64)
            self.CACHE_DIR = "thumbnails"
            self.MAX_SIZE = (256, 256)
            self.CACHE_SIZE_LIMIT = 100  # MB
            self.QUALITY = 85
            self.FORMAT = "PNG"
    
    THUMBNAIL_CONFIG = ThumbnailConfig()


class ThumbnailServiceImpl(IThumbnailService):
    """
    RESTORED: Working Maya Playblast Thumbnail System
    Generates REAL Maya viewport screenshots - Like v1.2.2 that actually worked!
    """
    
    def __init__(self):
        try:
            temp_dir = Path(tempfile.gettempdir())
            self._cache_dir = temp_dir / "assetmanager_thumbnails"
            self._cache_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"❌ Error setting up cache directory: {e}")
            # Fallback to a simple temp directory
            self._cache_dir = Path(tempfile.gettempdir()) / "thumbnails"
            self._cache_dir.mkdir(exist_ok=True)
            
        self._supported_extensions = {
            '.png', '.jpg', '.jpeg', '.tiff', '.tga', '.bmp', '.gif',  # Images
            '.ma', '.mb',  # Maya files
            '.obj', '.fbx',  # 3D models
            '.usd', '.usda', '.usdc', '.usdz',  # USD files
            '.py', '.mel', '.txt', '.md'  # Script/text files
        }
        self._cache_stats: Dict[str, int] = {}  # Track cache usage
        self._master_capture_cache: Dict[str, Dict[str, Any]] = {}  # Store high-res playblast captures
        print("📸 ThumbnailServiceImpl initialized - RESTORED Maya playblast system")
    
    def _generate_cache_key(self, file_path: Path, size: Tuple[int, int]) -> str:
        """Generate unique cache key for file and size combination"""
        try:
            path_str = str(file_path.resolve())
            size_str = f"{size[0]}x{size[1]}"
            
            # Get file modification time safely
            try:
                mtime = file_path.stat().st_mtime
            except Exception as e:
                print(f"⚠️ Could not get file stat for {file_path}: {e}, using 0")
                mtime = 0
                
            key_data = f"{path_str}_{size_str}_{mtime}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            return cache_key
            
        except Exception as e:
            print(f"❌ Error generating cache key for {file_path}: {e}")
            # Fallback to simple hash
            fallback_data = f"{file_path.name}_{size[0]}x{size[1]}"
            return hashlib.md5(fallback_data.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for cache key"""
        return self._cache_dir / f"{cache_key}.png"
    
    def generate_thumbnail(self, file_path: Path, size: Tuple[int, int] = (64, 64), force_playblast: bool = False) -> Optional[str]:
        """Generate or retrieve thumbnail for asset.
        
        Args:
            file_path: Path to asset file
            size: Thumbnail dimensions (width, height)
            force_playblast: If True, generate Maya playblast (imports asset to Maya)
                           If False, use simple file-type icon (no Maya import)
        
        Returns:
            Path to thumbnail image, or None if generation failed
        """
        try:
            # ALWAYS check for existing custom screenshot first (highest priority!)
            # Custom screenshots should always be used if they exist
            custom_screenshot = self._check_custom_screenshot(file_path)
            if custom_screenshot:
                print(f"✅ Using custom screenshot: {file_path.name}")
                return custom_screenshot

            # CRITICAL FIX: Skip cache check if force_playblast=True
            # We need to generate a NEW playblast, not return old file-type icon cache!
            if not force_playblast:
                # Check cache (only for file-type icons, not playblasts)
                cache_key = self._generate_cache_key(file_path, size)
                cache_path = self._get_cache_path(cache_key)

                if cache_path.exists():
                    print(f"📁 Using cached thumbnail: {file_path.name}")
                    return str(cache_path)

            extension = file_path.suffix.lower()
            
            # CRITICAL: Two-tier thumbnail system
            # Tier 1: Simple file-type icons (NO Maya import - safe for library browsing)
            # Tier 2: Maya playblast (imports to Maya - generates actual preview)
            
            if extension in {'.ma', '.mb'}:
                if force_playblast:
                    # Generate high-quality playblast (isolated namespace - no scene pollution!)
                    print(f"📸 Generating Maya playblast thumbnail for {file_path.name}")
                    requested_dimension = max(size[0], size[1])
                    base_capture = self._ensure_playblast_capture(file_path, requested_dimension)
                    if base_capture and Path(base_capture).exists():
                        pixmap = QPixmap(base_capture)
                        if not pixmap.isNull():
                            # Save to cache for this size
                            cache_key = self._generate_cache_key(file_path, size)
                            cache_path = self._get_cache_path(cache_key)
                            cache_path.parent.mkdir(parents=True, exist_ok=True)
                            scaled_pixmap = pixmap.scaled(
                                size[0],
                                size[1],
                                Qt.KeepAspectRatio, # type: ignore
                                Qt.SmoothTransformation # type: ignore
                            )
                            if scaled_pixmap.save(str(cache_path)):
                                print(f"✅ Generated playblast thumbnail: {file_path.name} ({size[0]}x{size[1]})")
                                return str(cache_path)
                            else:
                                print(f"⚠️ Failed to save scaled thumbnail for {file_path.name}")
                        else:
                            print(f"⚠️ Base playblast capture invalid for {file_path.name}")
                    else:
                        print(f"⚠️ Unable to capture playblast for {file_path.name}")
                    # Fallback to file-type icon if playblast fails
                    print(f"📄 Falling back to file-type icon for {file_path.name}")
                else:
                    # Library browsing - use simple icon (no Maya import!)
                    print(f"📄 Using file-type icon for library browsing: {file_path.name}")

            # Generate simple file-type icon (no Maya import needed)
            cache_key = self._generate_cache_key(file_path, size)
            cache_path = self._get_cache_path(cache_key)
            thumbnail_path = self._create_file_type_icon(file_path, size)
            if thumbnail_path and Path(thumbnail_path).exists():
                print(f"✅ Generated file-type icon: {file_path.name}")
                return thumbnail_path

            print(f"⚠️ Thumbnail generation failed: {file_path.name}")
            return None

        except Exception as e:
            print(f"❌ Thumbnail generation error: {e}")
            return None
    
    def get_cached_thumbnail(self, file_path: Path, size: Tuple[int, int] = (64, 64)) -> Optional[str]:
        """Get cached thumbnail if available and valid - checks custom screenshots first"""
        try:
            # ISSUE #2 FIX: Check for custom screenshot FIRST (highest priority)
            custom_screenshot = self._check_custom_screenshot(file_path)
            if custom_screenshot:
                return custom_screenshot
            
            # Then check cache
            cache_key = self._generate_cache_key(file_path, size)
            cache_path = self._get_cache_path(cache_key)
            
            if cache_path.exists():
                # Check if source file is newer than cache
                source_mtime = file_path.stat().st_mtime
                cache_mtime = cache_path.stat().st_mtime
                
                if cache_mtime >= source_mtime:
                    return str(cache_path)
                else:
                    # Cache is outdated, remove it
                    cache_path.unlink(missing_ok=True)
                    
        except Exception as e:
            print(f"Error checking cache for {file_path}: {e}")
        
        return None
    
    def is_thumbnail_supported(self, file_path: Path) -> bool:
        """Check if thumbnail generation is supported for this file type"""
        return file_path.suffix.lower() in self._supported_extensions
    
    def _check_custom_screenshot(self, file_path: Path) -> Optional[str]:
        """Check for custom user screenshot (v1.2.2 feature)"""
        try:
            asset_dir = file_path.parent
            asset_name = file_path.stem
            thumbnail_dir = asset_dir / ".thumbnails"
            
            # Debug logging
            print(f"🔍 Checking custom screenshot for: {asset_name}")
            print(f"   Looking in: {thumbnail_dir}")
            
            # Check for various screenshot formats
            screenshot_files = [
                thumbnail_dir / f"{asset_name}_screenshot.png",
                thumbnail_dir / f"{asset_name}_screenshot.jpg", 
                thumbnail_dir / f"{asset_name}_screenshot.tiff",
                thumbnail_dir / f"{asset_name}.png",
                thumbnail_dir / f"{asset_name}.jpg"
            ]
            
            for screenshot_file in screenshot_files:
                print(f"   Checking: {screenshot_file.name} - Exists: {screenshot_file.exists()}")
                if screenshot_file.exists():
                    print(f"✅ Using custom screenshot: {screenshot_file}")
                    return str(screenshot_file)
            
            print(f"   ℹ️ No custom screenshot found for: {asset_name}")
                    
        except Exception as e:
            print(f"⚠️ Error checking custom screenshot: {e}")
        
        return None
    
    def _ensure_playblast_capture(self, file_path: Path, requested_dimension: int) -> Optional[str]:
        """Capture a high-resolution playblast once per asset revision and reuse it."""
        try:
            mtime = file_path.stat().st_mtime
        except Exception:
            mtime = 0

        cache_entry = self._master_capture_cache.get(str(file_path))
        if cache_entry:
            cached_path = Path(cache_entry.get('path', ''))
            cached_mtime = cache_entry.get('mtime')
            if cached_path.exists() and cached_mtime == mtime:
                # Cached playblast is still valid, but ensure custom screenshot exists
                try:
                    asset_dir = file_path.parent
                    asset_name = file_path.stem
                    thumbnail_dir = asset_dir / ".thumbnails"
                    thumbnail_dir.mkdir(parents=True, exist_ok=True)
                    custom_screenshot_path = thumbnail_dir / f"{asset_name}_screenshot.png"
                    
                    # Copy cached playblast to custom screenshot location if it doesn't exist
                    if not custom_screenshot_path.exists():
                        import shutil
                        shutil.copy2(cached_path, str(custom_screenshot_path))
                        print(f"📸 Saved cached playblast as custom screenshot: {custom_screenshot_path.name}")
                except Exception as save_error:
                    print(f"⚠️ Could not save custom screenshot from cache: {save_error}")
                
                return str(cached_path)

        capture_dimension = max(requested_dimension, 512)
        capture_size = (capture_dimension, capture_dimension)
        capture_path = self._capture_maya_playblast(file_path, capture_size)

        if capture_path and Path(capture_path).exists():
            self._master_capture_cache[str(file_path)] = {
                'mtime': mtime,
                'path': capture_path
            }
            return capture_path

        # Remove stale cache entry if capture failed
        self._master_capture_cache.pop(str(file_path), None)
        return None

    def _capture_maya_playblast(self, file_path: Path, capture_size: Tuple[int, int]) -> Optional[str]:
        """Import asset into temporary namespace, capture playblast, and clean up."""
        try:
            import maya.cmds as cmds  # type: ignore
        except ImportError:
            print("⚠️ Maya cmds not available")
            return None

        namespace = None
        original_selection = []
        original_viewport_settings = {}
        temp_dir = None
        try:
            print(f"📸 Starting SAFE Maya playblast for: {file_path.name}")

            original_selection = cmds.ls(selection=True) or []
            cmds.select(clear=True)

            namespace, imported_nodes = self._import_maya_scene_safely_no_new_scene(file_path, cmds)
            if not namespace:
                print(f"⚠️ Playblast import failed for {file_path.name}")
                return None

            if imported_nodes:
                print(f"✅ Imported {len(imported_nodes)} nodes for playblast")

            meshes = self._get_scene_geometry_safely(cmds, namespace)
            if not meshes:
                print(f"⚠️ No geometry found in {file_path.name}")
                return None

            # Frame imported geometry for consistent thumbnails
            try:
                cmds.select(meshes[:5])
                cmds.viewFit()
            except Exception as frame_error:
                print(f"⚠️ View fit warning: {frame_error}")
            finally:
                cmds.select(clear=True)

            # CRITICAL: Enable textures and materials for playblast
            original_viewport_settings = self._setup_viewport_for_playblast(cmds)

            cache_key = self._generate_cache_key(file_path, capture_size)
            capture_path = self._cache_dir / f"{cache_key}_master.png"
            capture_path.parent.mkdir(parents=True, exist_ok=True)

            temp_dir = tempfile.mkdtemp(prefix="maya_playblast_")
            temp_filename = f"screenshot_{int(time.time())}"
            temp_file = os.path.join(temp_dir, temp_filename)

            width, height = capture_size
            cmds.playblast(
                filename=temp_file,
                format='image',
                compression='png',
                quality=100,
                percent=100,
                width=width,
                height=height,
                viewer=False,
                showOrnaments=False,
                offScreen=True,
                frame=1,
                completeFilename=f"{temp_file}.0001.png"
            )

            generated_files = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if f.startswith("screenshot_") and f.endswith(".png")
            ]

            if not generated_files:
                print("❌ Playblast file not generated")
                return None

            latest_capture = max(generated_files, key=os.path.getmtime)
            shutil.copy2(latest_capture, str(capture_path))
            
            # CRITICAL FIX: Also save as custom screenshot so it appears in library!
            # This makes playblast thumbnails persist like user-captured screenshots
            try:
                asset_dir = file_path.parent
                asset_name = file_path.stem
                thumbnail_dir = asset_dir / ".thumbnails"
                thumbnail_dir.mkdir(parents=True, exist_ok=True)
                custom_screenshot_path = thumbnail_dir / f"{asset_name}_screenshot.png"
                shutil.copy2(latest_capture, str(custom_screenshot_path))
                print(f"📸 Saved playblast as custom screenshot: {custom_screenshot_path}")
            except Exception as save_error:
                print(f"⚠️ Could not save as custom screenshot: {save_error}")
            
            print(f"✅ Maya playblast successful: {capture_path}")
            return str(capture_path)

        except Exception as capture_error:
            print(f"❌ Maya playblast error: {capture_error}")
            return None

        finally:
            # Restore original viewport settings
            try:
                if original_viewport_settings:
                    self._restore_viewport_settings(cmds, original_viewport_settings)
            except Exception as viewport_error:
                print(f"⚠️ Viewport restoration warning: {viewport_error}")
            
            try:
                if namespace:
                    self._bulletproof_namespace_cleanup(namespace, cmds)
            except Exception as cleanup_error:
                print(f"⚠️ Playblast cleanup warning: {cleanup_error}")

            try:
                if original_selection:
                    cmds.select(original_selection, replace=True)
                else:
                    cmds.select(clear=True)
            except Exception:
                try:
                    cmds.select(clear=True)
                except:
                    pass

            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _setup_viewport_for_playblast(self, cmds) -> dict:
        """Configure viewport to display textures and materials for playblast thumbnail.
        
        Returns:
            dict: Original viewport settings for restoration
        """
        original_settings = {}
        try:
            # Get the active model panel (viewport)
            panels = cmds.getPanel(type='modelPanel')
            if not panels:
                print("⚠️ No model panels found")
                return original_settings
            
            active_panel = cmds.getPanel(withFocus=True)
            if active_panel not in panels:
                active_panel = panels[0]  # Use first panel if focused panel isn't a model panel
            
            # Store original settings
            original_settings['panel'] = active_panel
            original_settings['displayTextures'] = cmds.modelEditor(active_panel, query=True, displayTextures=True)
            original_settings['displayAppearance'] = cmds.modelEditor(active_panel, query=True, displayAppearance=True)
            original_settings['displayLights'] = cmds.modelEditor(active_panel, query=True, displayLights=True)
            original_settings['shadows'] = cmds.modelEditor(active_panel, query=True, shadows=True)
            original_settings['useDefaultMaterial'] = cmds.modelEditor(active_panel, query=True, useDefaultMaterial=True)
            
            # Enable textures and materials
            cmds.modelEditor(active_panel, edit=True, displayTextures=True)  # Show textures
            cmds.modelEditor(active_panel, edit=True, displayAppearance='smoothShaded')  # Smooth shaded mode
            cmds.modelEditor(active_panel, edit=True, displayLights='default')  # Use default lighting
            cmds.modelEditor(active_panel, edit=True, shadows=False)  # Disable shadows for performance
            cmds.modelEditor(active_panel, edit=True, useDefaultMaterial=False)  # Use actual materials
            
            print("✅ Viewport configured for textured playblast")
            return original_settings
            
        except Exception as e:
            print(f"⚠️ Could not configure viewport settings: {e}")
            return original_settings
    
    def _restore_viewport_settings(self, cmds, original_settings: dict) -> None:
        """Restore original viewport settings after playblast.
        
        Args:
            cmds: Maya cmds module
            original_settings: Dictionary of original viewport settings
        """
        try:
            if not original_settings or 'panel' not in original_settings:
                return
            
            panel = original_settings['panel']
            
            # Restore original settings
            if 'displayTextures' in original_settings:
                cmds.modelEditor(panel, edit=True, displayTextures=original_settings['displayTextures'])
            if 'displayAppearance' in original_settings:
                cmds.modelEditor(panel, edit=True, displayAppearance=original_settings['displayAppearance'])
            if 'displayLights' in original_settings:
                cmds.modelEditor(panel, edit=True, displayLights=original_settings['displayLights'])
            if 'shadows' in original_settings:
                cmds.modelEditor(panel, edit=True, shadows=original_settings['shadows'])
            if 'useDefaultMaterial' in original_settings:
                cmds.modelEditor(panel, edit=True, useDefaultMaterial=original_settings['useDefaultMaterial'])
            
            print("✅ Viewport settings restored")
            
        except Exception as e:
            print(f"⚠️ Could not restore viewport settings: {e}")
    
    def _bulletproof_namespace_cleanup(self, namespace: str, cmds) -> bool:
        """Bulletproof namespace cleanup handling complex production assets
        
        Based on September 25th test analysis, this handles:
        - Locked objects (globalVolumeAggregate, ngSkinTools data)
        - Persistent render connections (RenderMan, Arnold)
        - Complex asset structures with multiple renderers
        - Scene-level metadata and references
        
        Returns:
            bool: True if cleanup completely successful, False if partial
        """
        if not namespace or not cmds.namespace(exists=namespace):
            return True
            
        try:
            print(f"🧹 Starting enhanced bulletproof cleanup for: {namespace}")
            
            # PHASE 0: PRE-SCAN - Clear scene metadata and undo queue
            self._clear_scene_metadata(namespace, cmds)
            
            # PHASE 1: PRE-CLEANUP - Unlock locked nodes
            self._unlock_namespace_nodes(namespace, cmds)
            
            # PHASE 2: DISCONNECT - Break persistent connections
            self._disconnect_render_connections(namespace, cmds)
            
            # PHASE 3: DELETE - Remove objects safely
            # CRITICAL FIX: Don't let Phase 3 failure prevent Phase 6 from running!
            success = False
            try:
                success = self._delete_namespace_content(namespace, cmds)
            except Exception as phase3_error:
                print(f"⚠️ Phase 3 error (continuing to aggressive cleanup): {phase3_error}")
            
            # PHASE 4: NAMESPACE - Remove namespace (only if Phase 3 succeeded)
            if success:
                try:
                    cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)
                except:
                    pass  # Phase 6 will handle this
                
            # PHASE 5: VALIDATION - Verify cleanup
            cleanup_complete = not cmds.namespace(exists=namespace)
            
            if cleanup_complete:
                print(f"✅ Complete cleanup successful: {namespace}")
                return True
            else:
                print(f"⚠️ Partial cleanup - namespace still exists, attempting aggressive final cleanup: {namespace}")
                
            # PHASE 6: AGGRESSIVE FINAL CLEANUP - Force remove everything from Outliner
            # THIS MUST ALWAYS RUN if namespace still exists!
            try:
                print(f"🔥 Phase 6: Aggressive final cleanup for: {namespace}")
                
                # Get all remaining nodes in namespace
                remaining_nodes = []
                try:
                    remaining_nodes = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True, dagPath=True) or []
                    print(f"   Found {len(remaining_nodes)} remaining nodes to force-delete")
                except:
                    pass
                
                # Aggressive deletion loop - try multiple strategies
                for node in remaining_nodes:
                    if not cmds.objExists(node):
                        continue
                        
                    # Strategy 0: Special handling for RenderMan volume aggregates
                    if 'globalVolumeAggregate' in node or 'VolumeAggregate' in node:
                        try:
                            # Remove from all volume sets first
                            try:
                                volume_sets = cmds.listConnections(node, type='set') or []
                                for vset in volume_sets:
                                    try:
                                        cmds.sets(node, remove=vset)
                                    except:
                                        pass
                            except:
                                pass
                            
                            # Disconnect all RenderMan-specific connections
                            try:
                                all_conns = cmds.listConnections(node, plugs=True, connections=True) or []
                                for i in range(0, len(all_conns), 2):
                                    try:
                                        cmds.disconnectAttr(all_conns[i], all_conns[i+1])
                                    except:
                                        try:
                                            cmds.disconnectAttr(all_conns[i+1], all_conns[i])
                                        except:
                                            pass
                            except:
                                pass
                            
                            # Force unlock with all attributes
                            try:
                                cmds.lockNode(node, lock=False, lockName=False, lockUnpublished=False, ignoreComponents=True)
                            except:
                                pass
                                
                            print(f"   🎯 Special handling for RenderMan volume: {node.split(':')[-1]}")
                        except Exception as vol_err:
                            print(f"   ⚠️ RenderMan volume handling: {vol_err}")
                    
                    # Strategy 1: Unlock everything
                    try:
                        cmds.lockNode(node, lock=False, lockName=False, lockUnpublished=False)
                    except:
                        pass
                    
                    # Strategy 2: Break all connections
                    try:
                        connections = cmds.listConnections(node, plugs=True, connections=True) or []
                        for i in range(0, len(connections), 2):
                            try:
                                cmds.disconnectAttr(connections[i], connections[i+1])
                            except:
                                pass
                    except:
                        pass
                    
                    # Strategy 3: Remove from all sets
                    try:
                        all_sets = cmds.listSets(object=node) or []
                        for set_node in all_sets:
                            try:
                                cmds.sets(node, remove=set_node)
                            except:
                                pass
                    except:
                        pass
                    
                    # Strategy 4: Force delete with all options
                    try:
                        cmds.delete(node)
                        if not cmds.objExists(node):
                            print(f"   ✅ Force-deleted: {node.split(':')[-1]}")
                            continue
                    except:
                        pass
                    
                    # Strategy 5: Try parent deletion for nested nodes
                    try:
                        if '|' in node:
                            parent = node.rsplit('|', 1)[0]
                            if cmds.objExists(parent) and namespace in parent:
                                cmds.delete(parent)
                                if not cmds.objExists(node):
                                    print(f"   ✅ Deleted via parent: {node.split(':')[-1]}")
                                    continue
                    except:
                        pass
                    
                    # Strategy 6: Rename and isolate
                    try:
                        temp_name = f"__toDelete_{int(time.time())}_{node.split(':')[-1]}"
                        renamed = cmds.rename(node, temp_name)
                        cmds.delete(renamed)
                        if not cmds.objExists(renamed):
                            print(f"   ✅ Deleted after rename: {node.split(':')[-1]}")
                    except:
                        print(f"   ⚠️ Could not delete locked node: {node.split(':')[-1]} (acceptable for nested references)")
                
                # Delete namespace with all content (don't move to root!)
                try:
                    if cmds.namespace(exists=namespace):
                        cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True, force=True)
                        print(f"   ✅ Removed namespace with deleteNamespaceContent flag")
                except Exception as ns_error:
                    print(f"   ⚠️ Namespace removal attempt: {ns_error}")
                
                # ISSUE #1 FIX: Nuclear option - DELETE all nodes in namespace (don't move!)
                
                # ISSUE #1 FIX: Nuclear option - DELETE all nodes in namespace (don't move!)
                try:
                    if cmds.namespace(exists=namespace):
                        print(f"   🔥 Nuclear option: Deleting all content in namespace {namespace}")
                        
                        # Get ALL nodes in the namespace (DAG and DG nodes)
                        dag_nodes = cmds.namespaceInfo(namespace, listNamespace=True, recurse=True, dagPath=True) or []
                        dg_nodes = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True) or []
                        all_nodes = list(set(dag_nodes + dg_nodes))  # Combine and deduplicate
                        
                        nodes_deleted = 0
                        if all_nodes:
                            print(f"   📋 Found {len(all_nodes)} nodes to delete")
                            
                            # Debug: Show some node names to verify we're getting the right nodes
                            print(f"   🔍 Sample nodes: {[n.split(':')[-1] for n in all_nodes[:5]]}")
                            
                            # Special handling for RenderMan globalVolumeAggregate nodes (often locked)
                            volume_nodes = [n for n in all_nodes if 'globalvolumeaggregate' in n.lower()]
                            print(f"   🔍 Searching for volume nodes in {len(all_nodes)} total nodes...")
                            if volume_nodes:
                                print(f"   🔓 Found {len(volume_nodes)} RenderMan volume aggregate nodes to unlock...")
                                for vol_node in volume_nodes:
                                    try:
                                        if cmds.objExists(vol_node):
                                            # Always try to unlock, don't query first (query can fail on nested namespaces)
                                            cmds.lockNode(vol_node, lock=False)
                                            print(f"   ✅ Unlocked: {vol_node.split(':')[-1]}")
                                    except Exception as unlock_err:
                                        print(f"   ⚠️ Could not unlock {vol_node.split(':')[-1]}: {unlock_err}")
                            else:
                                print(f"   ℹ️ No volume aggregate nodes found in initial scan")
                            
                            # Delete DAG nodes first (transforms, shapes, etc.)
                            for node in dag_nodes:
                                try:
                                    if cmds.objExists(node):
                                        cmds.delete(node)
                                        nodes_deleted += 1
                                except Exception as e:
                                    print(f"   ⚠️ Could not delete DAG node {node.split(':')[-1]}: {e}")
                            
                            # Then delete DG nodes (shaders, textures, etc.)
                            for node in dg_nodes:
                                try:
                                    if cmds.objExists(node) and ':' in node and namespace in node:
                                        cmds.delete(node)
                                        nodes_deleted += 1
                                except Exception as e:
                                    pass  # Expected for default nodes
                            
                            print(f"   ✅ Deleted {nodes_deleted} nodes from namespace")
                        
                        # Special cleanup: Force-unlock and delete any remaining locked nodes
                        if cmds.namespace(exists=namespace):
                            print(f"   🔍 Checking for remaining locked nodes in namespace...")
                            try:
                                # Get ALL remaining nodes using ls command with namespace prefix
                                remaining_nodes = cmds.ls(f"{namespace}:*", long=True) or []
                                if remaining_nodes:
                                    print(f"   📋 Found {len(remaining_nodes)} remaining nodes")
                                    # Focus on globalVolumeAggregate nodes specifically
                                    locked_volumes = [n for n in remaining_nodes if 'globalVolumeAggregate' in n]
                                    if locked_volumes:
                                        print(f"   🔓 Attempting to unlock {len(locked_volumes)} volume aggregate nodes...")
                                        for vol_node in locked_volumes:
                                            try:
                                                cmds.lockNode(vol_node, lock=False)
                                                cmds.delete(vol_node)
                                                print(f"   ✅ Unlocked and deleted: {vol_node.split(':')[-1]}")
                                            except Exception as e:
                                                print(f"   ⚠️ Failed to cleanup: {vol_node.split(':')[-1]} - {e}")
                            except Exception as remaining_err:
                                print(f"   ⚠️ Could not scan remaining nodes: {remaining_err}")
                        
                        # Now remove the empty namespace
                        if cmds.namespace(exists=namespace):
                            cmds.namespace(set=':')  # Switch to root namespace first
                            cmds.namespace(removeNamespace=namespace, force=True)
                            print(f"   ✅ Namespace {namespace} removed")
                except Exception as nuclear_error:
                    print(f"   ⚠️ Nuclear cleanup error: {nuclear_error}")
                
                # Verify final cleanup
                final_cleanup = not cmds.namespace(exists=namespace)
                if final_cleanup:
                    print(f"🎉 Aggressive cleanup successful: {namespace} completely removed from Outliner")
                else:
                    print(f"⚠️ Warning: Namespace {namespace} still exists - manual cleanup may be needed")
                    # List remaining nodes for debugging
                    try:
                        remaining = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True) or []
                        print(f"   Remaining nodes ({len(remaining)}): {remaining[:5]}...")  # Show first 5
                    except:
                        pass
                    
                return final_cleanup  # Return actual cleanup status
                
            except Exception as aggressive_error:
                print(f"⚠️ Aggressive cleanup warning: {aggressive_error}")
                return False  # Indicate cleanup failed
            
        except Exception as e:
            print(f"⚠️ Bulletproof cleanup error: {e}")
            return self._fallback_cleanup(namespace, cmds)
    
    def _clear_scene_metadata(self, namespace: str, cmds):
        """Clear scene-level metadata and references (Phase 0)"""
        try:
            # Clear undo queue to remove references
            cmds.flushUndo()
            
            # Clear any scene-level references to namespace objects
            if hasattr(cmds, 'dgdirty'):
                cmds.dgdirty(allPlugs=True)
                
            # Force garbage collection of unused nodes
            if hasattr(cmds, 'dgeval'):
                try:
                    cmds.dgeval("time")
                except:
                    pass
            
            # Additional aggressive cleanup for leftover objects
            try:
                # Force dependency graph evaluation to clear stale references
                cmds.dgeval("defaultRenderGlobals.currentTime")
                
                # Clear any remaining references in the scene
                if hasattr(cmds, 'scriptEditorInfo'):
                    cmds.scriptEditorInfo(clearHistory=True)
                
                # Force Maya to update its internal node tracking
                if hasattr(cmds, 'refresh'):
                    cmds.refresh(force=True)
                
                # Clear any lingering selection handles that can pin namespaces
                if hasattr(cmds, 'select'):
                    cmds.select(clear=True)
                    
            except Exception as cleanup_error:
                print(f"⚠️ Advanced cleanup warning: {cleanup_error}")
                    
            print(f"✅ Enhanced scene metadata cleared for: {namespace}")
            
        except Exception as e:
            print(f"⚠️ Scene metadata clearing warning: {e}")
    
    def _unlock_namespace_nodes(self, namespace: str, cmds):
        """Unlock all locked nodes in namespace (Phase 1)"""
        try:
            # Get all nodes in namespace
            namespace_nodes = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True)
            if not namespace_nodes:
                return
                
            # Find locked nodes
            locked_nodes = []
            for node in namespace_nodes:
                try:
                    if cmds.lockNode(node, query=True)[0]:
                        locked_nodes.append(node)
                except:
                    continue
                    
            # Unlock locked nodes with enhanced volume aggregate handling
            if locked_nodes:
                print(f"🔓 Unlocking {len(locked_nodes)} locked nodes...")
                cmds.lockNode(locked_nodes, lock=False)

                # Force unlock RenderMan volume aggregates that ignore standard unlock
                volume_aggregates = [node for node in locked_nodes if 'globalVolumeAggregate' in node]
                if volume_aggregates:
                    print(f"🔥 Force unlocking {len(volume_aggregates)} volume aggregates")
                    for vol_node in volume_aggregates:
                        if cmds.objExists(vol_node):
                            try:
                                if cmds.attributeQuery('locked', node=vol_node, exists=True):
                                    cmds.setAttr(f"{vol_node}.locked", False)
                            except Exception as attr_error:
                                print(f"⚠️ Volume aggregate attribute unlock warning: {attr_error}")
                            try:
                                cmds.lockNode(vol_node, lock=False, lockName=False)
                            except Exception as lock_error:
                                print(f"⚠️ Volume aggregate lock warning: {lock_error}")

                print(f"✅ Unlocked nodes: {', '.join(locked_nodes[:3])}{'...' if len(locked_nodes) > 3 else ''}")
                
        except Exception as e:
            print(f"⚠️ Lock management error: {e}")
    
    def _disconnect_render_connections(self, namespace: str, cmds):
        """Break persistent render setup connections (Phase 2)"""
        try:
            # Target problematic connection types from September 25th logs
            connection_patterns = [
                'rmanDefaultDisplay.displayType',
                'rmanDefaultDisplay.displayChannels[0]',
                'rmanDefaultDisplay.displayChannels[1]', 
                'rmanBakingGlobals.displays[0]',
                'defaultArnoldRenderOptions.drivers'
            ]
            
            connections_broken = 0
            for pattern in connection_patterns:
                try:
                    connections = cmds.listConnections(pattern, source=True, plugs=True)
                    if connections:
                        for conn in connections:
                            if namespace in conn:
                                cmds.disconnectAttr(conn, pattern)
                                connections_broken += 1
                                print(f"🔌 Disconnected: {conn} -> {pattern}")
                except:
                    continue
                    
            if connections_broken > 0:
                print(f"✅ Broke {connections_broken} render connections")
                
        except Exception as e:
            print(f"⚠️ Connection breaking error: {e}")
    
    def _delete_namespace_content(self, namespace: str, cmds) -> bool:
        """Safely delete namespace content (Phase 3)"""
        try:
            # Get all objects in namespace
            namespace_objects = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True)
            if not namespace_objects:
                return True
                
            # Try to delete objects individually for better error handling
            deleted_count = 0
            failed_objects = []
            
            for obj in namespace_objects:
                try:
                    if cmds.objExists(obj):
                        cmds.delete(obj)
                        deleted_count += 1
                        continue
                except Exception as delete_error:
                    # Attempt targeted recovery for locked volume aggregates
                    if 'globalVolumeAggregate' in obj and self._force_delete_volume_aggregate(obj, cmds):
                        deleted_count += 1
                        continue

                    # Generic locked-node retry
                    error_text = str(delete_error)
                    if 'locked' in error_text.lower() and cmds.objExists(obj):
                        try:
                            cmds.lockNode(obj, lock=False, lockName=False)
                            if cmds.attributeQuery('locked', node=obj, exists=True):
                                cmds.setAttr(f"{obj}.locked", False)
                            cmds.delete(obj)
                            deleted_count += 1
                            continue
                        except Exception:
                            pass

                    failed_objects.append((obj, error_text))
                    continue
            
            print(f"✅ Deleted {deleted_count}/{len(namespace_objects)} objects")
            
            if failed_objects:
                print(f"⚠️ {len(failed_objects)} objects could not be deleted:")
                for obj, error in failed_objects[:3]:  # Show first 3 failures
                    print(f"   • {obj}: {error}")
                if len(failed_objects) > 3:
                    print(f"   • ... and {len(failed_objects) - 3} more")
            
            return len(failed_objects) == 0  # Success if no failures
            
        except Exception as e:
            print(f"⚠️ Content deletion error: {e}")
            return False

    def _force_delete_volume_aggregate(self, node_name: str, cmds) -> bool:
        """Aggressively unlock, disconnect, and delete RenderMan volume aggregates"""
        try:
            if not cmds.objExists(node_name):
                return True
            
            # Early detection: Skip deeply nested reference nodes (3+ namespace levels)
            # These will be automatically cleaned when parent namespace is removed
            namespace_depth = node_name.count(':')
            if namespace_depth >= 3:
                # Silently accept - parent namespace deletion will clean this up
                return True

            def _unlock_node(target: str) -> None:
                try:
                    cmds.lockNode(target, lock=False, lockName=False)
                except Exception:
                    pass
                try:
                    import maya.mel as mel  # type: ignore
                    mel.eval(f'lockNode -lock 0 -lockName 0 "{target}";')
                except Exception:
                    pass

            _unlock_node(node_name)

            # If this aggregate belongs to a reference, remove the reference entirely
            try:
                if cmds.referenceQuery(node_name, isNodeReferenced=True):
                    ref_node = cmds.referenceQuery(node_name, referenceNode=True)
                    if ref_node:
                        try:
                            cmds.lockNode(ref_node, lock=False, lockName=False)
                        except Exception:
                            pass
                        try:
                            import maya.mel as mel  # type: ignore
                            mel.eval(f'lockNode -lock 0 -lockName 0 "{ref_node}";')
                        except Exception:
                            pass
                        try:
                            cmds.file(referenceNode=ref_node, removeReference=True, force=True)
                            if not cmds.objExists(node_name):
                                print(f"🗑️ Removed reference {ref_node} for {node_name}")
                                return True
                        except Exception:
                            pass
            except Exception:
                pass

            # Unlock any locked attributes on the aggregate
            try:
                locked_attrs = cmds.listAttr(node_name, locked=True) or []
                for attr in locked_attrs:
                    try:
                        cmds.setAttr(f"{node_name}.{attr}", lock=False)
                    except Exception:
                        continue
            except Exception:
                pass

            if cmds.attributeQuery('locked', node=node_name, exists=True):
                try:
                    cmds.setAttr(f"{node_name}.locked", False)
                except Exception:
                    pass

            # Disconnect all connections involving this aggregate
            try:
                connections = cmds.listConnections(node_name, plugs=True, connections=True, skipConversionNodes=True) or []
                for idx in range(0, len(connections), 2):
                    src = connections[idx]
                    dest = connections[idx + 1] if idx + 1 < len(connections) else None
                    try:
                        if src and dest:
                            cmds.disconnectAttr(src, dest)
                    except Exception:
                        try:
                            if src and dest:
                                cmds.disconnectAttr(dest, src)
                        except Exception:
                            continue
            except Exception:
                pass

            # Remove known RenderMan display connections referencing this aggregate
            volume_patterns = [
                'rmanDefaultDisplay.displayType',
                'rmanDefaultDisplay.displayChannels[0]',
                'rmanDefaultDisplay.displayChannels[1]',
                'rmanBakingGlobals.displays[0]',
                'rmanDefaultDisplay.message',
                'rmanDefaultBakeDisplay.message'
            ]
            for pattern in volume_patterns:
                try:
                    connections = cmds.listConnections(pattern, source=True, plugs=True) or []
                    for conn in connections:
                        if node_name in conn:
                            try:
                                cmds.disconnectAttr(conn, pattern)
                            except Exception:
                                try:
                                    cmds.disconnectAttr(pattern, conn)
                                except Exception:
                                    continue
                except Exception:
                    continue

            # Ensure the aggregate is no longer a member of renderPartition or other utility sets
            try:
                for target_set in ('renderPartition', 'initialParticleSE', 'initialShadingGroup'):
                    if cmds.objExists(target_set):
                        try:
                            cmds.sets(node_name, remove=target_set)
                        except Exception:
                            continue
            except Exception:
                pass

            # Remove all members from the aggregate set before deletion
            try:
                members = cmds.sets(node_name, query=True) or []
                for member in members:
                    try:
                        cmds.sets(member, remove=node_name)
                    except Exception:
                        continue
            except Exception:
                pass

            # Find and remove from all volume aggregate sets
            try:
                # Aggressively unlock the node one more time before set operations
                _unlock_node(node_name)
                try:
                    import maya.mel as mel  # type: ignore
                    # Try MEL unlock as well
                    mel.eval(f'lockNode -lock 0 -lockName 0 "{node_name}";')
                    # Also try to unlock using setAttr
                    if cmds.attributeQuery('locked', node=node_name, exists=True):
                        cmds.setAttr(f"{node_name}.locked", False, lock=False)
                except Exception:
                    pass
                
                all_sets = cmds.ls(type='rmanVolumeAggregateSet') or []
                for agg_set in all_sets:
                    try:
                        # Remove the node from this aggregate set
                        cmds.sets(node_name, remove=agg_set)
                    except Exception:
                        continue
            except Exception:
                pass

            # Attempt RenderMan-specific removal if available
            try:
                import maya.mel as mel  # type: ignore
                mel.eval(f'rmanRemoveVolumeAggregateSet("{node_name}")')
                if not cmds.objExists(node_name):
                    return True
            except Exception:
                pass

            # Final delete attempts with optional rename fallback
            try:
                cmds.delete(node_name)
                if not cmds.objExists(node_name):
                    return True
            except Exception:
                pass

            try:
                short_name = node_name.split(':')[-1]
                temp_name = f"{short_name}_cleanup"
                renamed = cmds.rename(node_name, temp_name)
                _unlock_node(renamed)
                cmds.delete(renamed)
                return not cmds.objExists(renamed)
            except Exception:
                pass
            
            # Final strategy: If the node is in a nested reference, it may be impossible to delete
            # Check if this is a deeply nested reference node (3+ namespace levels)
            namespace_depth = node_name.count(':')
            if namespace_depth >= 3:
                # This is likely a nested reference node that can't be deleted directly
                # This is acceptable - the parent namespace cleanup will handle it
                # print(f"ℹ️ Skipping deeply nested reference node: {node_name}")
                return True  # Consider this a success - it's in a reference we'll delete
            
            # Only report as failure if it's not a nested reference
            # print(f"⚠️ Could not delete volume aggregate: {node_name}")
            return False

        except Exception as e:
            # print(f"⚠️ Volume aggregate cleanup error: {e}")
            return False
    
    def _fallback_cleanup(self, namespace: str, cmds) -> bool:
        """Fallback cleanup when standard cleanup fails (Recovery Level 2-4)"""
        try:
            print(f"🔄 Attempting fallback cleanup for: {namespace}")
            
            # Recovery Level 2: Individual node deletion + namespace removal
            try:
                namespace_nodes = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True)
                if namespace_nodes:
                    for node in namespace_nodes:
                        try:
                            if cmds.objExists(node):
                                cmds.delete(node)
                        except:
                            continue
                            
                # Try namespace deletion again
                if cmds.namespace(exists=namespace):
                    cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)
                    
                if not cmds.namespace(exists=namespace):
                    print(f"✅ Fallback Level 2 successful: {namespace}")
                    return True
                    
            except:
                pass
            
            # Recovery Level 3: Force namespace deletion
            try:
                if cmds.namespace(exists=namespace):
                    cmds.namespace(removeNamespace=namespace, force=True)
                    
                if not cmds.namespace(exists=namespace):
                    print(f"✅ Fallback Level 3 successful: {namespace}")
                    return True
                    
            except:
                pass
            
            # Recovery Level 4: Log warning and continue
            print(f"⚠️ All cleanup levels failed for: {namespace} - continuing operation")
            return False
            
        except Exception as e:
            print(f"❌ Fallback cleanup failed: {e}")
            return False
    
    def _create_clean_scene_safely(self, cmds):
        """
        Safely create new Maya scene - prevents UI callback crashes
        Clean Code: Single Responsibility for safe scene operations
        """
        try:
            # Disable UI callbacks during scene creation to prevent crashes
            cmds.scriptJob(killAll=True)  # Clear any existing callbacks
            
            # Create new scene with minimal UI interaction
            cmds.file(new=True, force=True)
            
            print(f"✅ Created clean Maya scene safely")
            
        except Exception as e:
            print(f"❌ Safe scene creation failed: {e}")
            # Fallback: try without callback clearing
            try:
                cmds.file(new=True, force=True)
                print(f"⚠️ Scene created with fallback method")
            except Exception as fallback_error:
                print(f"❌ Complete scene creation failure: {fallback_error}")
                raise fallback_error
    
    def _import_maya_scene_safely_no_new_scene(self, file_path: Path, cmds) -> Tuple[Optional[str], List[str]]:
        """
        Import Maya scene into current scene - NO NEW SCENE CREATION
        Clean Code: Single Responsibility for safe import without scene crashes
        """
        namespace = None
        imported_nodes: List[str] = []
        try:
            # Import with namespace to avoid conflicts and enable easy cleanup
            namespace = f"thumb_{int(time.time() * 1000)}"  # Unique namespace
            
            # Import with settings that worked in v1.2.2 - but into current scene
            if file_path.suffix.lower() == '.ma':
                imported_nodes = cmds.file(
                    str(file_path),
                    i=True,
                    type="mayaAscii",
                    ignoreVersion=True,
                    mergeNamespacesOnClash=False,
                    namespace=namespace,
                    returnNewNodes=True
                )
            else:  # .mb
                imported_nodes = cmds.file(
                    str(file_path),
                    i=True,
                    type="mayaBinary",
                    ignoreVersion=True,
                    mergeNamespacesOnClash=False,
                    namespace=namespace,
                    returnNewNodes=True
                )
            
            if imported_nodes:
                # Select the imported objects for thumbnail generation
                cmds.select(imported_nodes)
                print(f"✅ Imported {len(imported_nodes)} objects for thumbnail: {file_path.name}")
            else:
                print(f"⚠️ No objects imported from: {file_path.name}")
            return namespace, imported_nodes
            
        except Exception as e:
            print(f"❌ Import error: {e}")
            # Try bulletproof cleanup of namespace if it was created
            try:
                if namespace:
                    self._bulletproof_namespace_cleanup(namespace, cmds)
            except:
                pass
            return namespace, imported_nodes
    
    def _import_maya_scene_safely(self, file_path: Path, cmds):
        """Safely import Maya scene for thumbnail generation"""
        try:
            # Import with settings that worked in v1.2.2
            if file_path.suffix.lower() == '.ma':
                cmds.file(str(file_path), i=True, type="mayaAscii", 
                         ignoreVersion=True, mergeNamespacesOnClash=True)
            else:  # .mb
                cmds.file(str(file_path), i=True, type="mayaBinary",
                         ignoreVersion=True, mergeNamespacesOnClash=True) 
            
            print(f"✅ Imported Maya scene: {file_path.name}")
            
        except Exception as e:
            print(f"⚠️ Import warning (continuing): {e}")
            # Continue anyway - scene might have loaded partially
    
    def _get_scene_geometry_safely(self, cmds, namespace: Optional[str] = None, limit: int = 10):
        """Get visible geometry for framing, optionally scoped to a namespace."""
        try:
            meshes = cmds.ls(type='mesh', long=True) or []
            if namespace:
                prefix = f"{namespace}:"
                meshes = [mesh for mesh in meshes if mesh.startswith(prefix)]

            transforms: List[str] = []
            for mesh in meshes[:limit]:
                try:
                    parents = cmds.listRelatives(mesh, parent=True, fullPath=True) or []
                    transforms.extend(parent for parent in parents if not namespace or parent.startswith(f"{namespace}:"))
                except Exception:
                    continue

            if transforms:
                seen = set()
                ordered_transforms = []
                for transform in transforms:
                    if transform not in seen:
                        seen.add(transform)
                        ordered_transforms.append(transform)
                print(f"Found {len(ordered_transforms)} namespace transforms")
                return ordered_transforms[:limit]

            if meshes:
                print(f"Found {len(meshes)} namespace meshes")
                return meshes[:limit]

            if namespace:
                ns_objects = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True) or []
                ns_transforms = [obj for obj in ns_objects if cmds.nodeType(obj) == 'transform']
                if ns_transforms:
                    print(f"Found {len(ns_transforms)} transforms via namespace info")
                    return ns_transforms[:limit]

            generic_geometry = cmds.ls(geometry=True, long=True) or []
            if namespace:
                generic_geometry = [geo for geo in generic_geometry if geo.startswith(f"{namespace}:")]

            print(f"Found {len(generic_geometry)} fallback geometry nodes")
            return generic_geometry[:limit]

        except Exception as e:
            print(f"Error querying geometry: {e}")
            return []
    
    def _create_file_type_icon(self, file_path: Path, size: Tuple[int, int]) -> Optional[str]:
        """Create file type icon for non-Maya files"""
        try:
            cache_key = self._generate_cache_key(file_path, size) 
            cache_path = self._get_cache_path(cache_key)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file type icon with custom graphics (v1.4.0)
            extension = file_path.suffix.lower()
            
            # Map file extensions to custom icon files
            icon_map = {
                '.ma': 'maya_ascii_am_icon.png',
                '.mb': 'maya_binary_am_icon.png',
                '.usd': 'usd_am_icon.png',
                '.fbx': 'fbx_am_icon.png',
                '.obj': 'obj_am_icon.png',
                '.abc': 'abc_am_icon.png',
                '.tex': 'tex_am_icon.png',
            }
            
            # Get custom icon path
            custom_icon_name = icon_map.get(extension, 'unknown_am_icon.png')
            icons_dir = Path(__file__).parent.parent.parent / 'icons'
            custom_icon_path = icons_dir / custom_icon_name
            
            # Try to load custom icon
            if custom_icon_path.exists():
                # Load and scale custom icon
                pixmap = QPixmap(str(custom_icon_path))
                if not pixmap.isNull():
                    # Scale to requested size
                    pixmap = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    # Only add text overlay for unknown file types
                    # Known file types have complete custom icons with built-in labels
                    is_unknown_type = extension not in icon_map
                    
                    if is_unknown_type:
                        # Overlay extension text for unknown file types only
                        painter = QPainter(pixmap)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                        
                        # Draw extension text
                        painter.setPen(QPen(Qt.GlobalColor.white))
                        font = QFont("Arial", max(8, size[0] // 8), QFont.Weight.Bold)
                        painter.setFont(font)
                        
                        text = extension.upper().replace('.', '') if extension else "FILE"
                        rect = QRect(0, 0, pixmap.width(), pixmap.height())
                        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
                        
                        painter.end()
                    
                    # Save to cache
                    if pixmap.save(str(cache_path), "PNG"):
                        if is_unknown_type:
                            print(f"✅ Created custom icon with text overlay: {extension}")
                        else:
                            print(f"✅ Using custom icon (no text): {extension}")
                        return str(cache_path)
            
            # Fallback to programmatic colored icon if custom icon fails
            print(f"⚠️ Custom icon not found: {custom_icon_path}, using fallback")
            
            # Color mapping for fallback (v1.4.0 style)
            color_map = {
                '.ma': QColor(100, 150, 255),   # Maya ASCII - Blue
                '.mb': QColor(80, 120, 200),    # Maya Binary - Dark Blue  
                '.obj': QColor(255, 150, 100),  # OBJ - Orange
                '.fbx': QColor(150, 255, 100),  # FBX - Green
                '.usd': QColor(100, 195, 238),  # USD - Cyan (#64c3ee)
                '.abc': QColor(255, 255, 100),  # Alembic - Yellow
                '.tex': QColor(255, 100, 150),  # RenderMan Texture - Pink
            }
            
            color = color_map.get(extension, QColor(150, 150, 150))
            
            # Create pixmap and draw fallback icon
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw background
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            
            margin = 4
            rect = QRect(margin, margin, size[0] - margin*2, size[1] - margin*2)
            painter.drawRoundedRect(rect, 4, 4)
            
            # Draw text
            painter.setPen(QPen(Qt.GlobalColor.white))
            font = QFont("Arial", max(8, size[0] // 8), QFont.Weight.Bold)
            painter.setFont(font)
            
            text = extension.upper().replace('.', '') if extension else "FILE"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            
            painter.end()
            
            # Save icon
            if pixmap.save(str(cache_path), "PNG"):
                print(f"✅ Created fallback file type icon: {extension}")
                return str(cache_path)
            
        except Exception as e:
            print(f"❌ Error creating file icon: {e}")
        
        return None
    
    def get_cache_size(self) -> int:
        """Get total cache size in bytes"""
        try:
            total_size = 0
            for cache_file in self._cache_dir.glob("*.png"):
                total_size += cache_file.stat().st_size
            return total_size
        except Exception:
            return 0
    
    def clear_cache(self) -> None:
        """Clear all cached thumbnails"""
        try:
            for cache_file in self._cache_dir.glob("*.png"):
                cache_file.unlink(missing_ok=True)
            self._cache_stats.clear()
            print("🗑️ Thumbnail cache cleared")
        except Exception as e:
            print(f"Error clearing cache: {e}")
    
    def clear_cache_for_file(self, file_path: Path) -> None:
        """Clear cached thumbnails for specific file"""
        try:
            # Generate all possible cache keys for this file (different sizes)
            common_sizes = [(64, 64), (128, 128), (256, 256), (512, 512)]
            
            for size in common_sizes:
                try:
                    cache_key = self._generate_cache_key(file_path, size)
                    cache_path = self._get_cache_path(cache_key)
                    
                    if cache_path.exists():
                        cache_path.unlink(missing_ok=True)
                        self._cache_stats.pop(cache_key, None)
                        print(f"🗑️ Cleared cache for {file_path.name} ({size[0]}x{size[1]})")
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"❌ Error clearing cache for {file_path}: {e}")
