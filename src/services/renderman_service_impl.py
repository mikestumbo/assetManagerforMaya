# -*- coding: utf-8 -*-
"""
RenderMan Integration Service
Provides RenderMan-specific features for Asset Manager

Author: Mike Stumbo
RenderMan Integration: Professional renderer support

Official API Documentation:
- RenderMan for Maya: https://renderman.pixar.com/maya
- RenderMan API Reference: https://renderman.pixar.com/resources/rman26/index.html
- Python API: https://renderman.pixar.com/resources/rman26/python_api.html
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class RenderManService:
    """
    RenderMan Integration Service - Single Responsibility
    Handles RenderMan-specific operations for asset management
    """
    
    def __init__(self):
        """Initialize RenderMan service"""
        self.logger = logging.getLogger(__name__)
        self._renderman_available = False
        self._prman_available = False
        
        # Check RenderMan availability
        self._check_renderman_availability()
        
    def _check_renderman_availability(self) -> bool:
        """Check if RenderMan is available in Maya - Single Responsibility"""
        try:
            import maya.cmds as cmds  # type: ignore
            
            # Check if RenderMan plugin is loaded
            if cmds.pluginInfo('RenderMan_for_Maya.py', query=True, loaded=True):
                self._renderman_available = True
                self.logger.info("✅ RenderMan for Maya detected")
            else:
                # Try to load RenderMan plugin
                try:
                    cmds.loadPlugin('RenderMan_for_Maya.py', quiet=True)
                    self._renderman_available = True
                    self.logger.info("✅ RenderMan for Maya loaded successfully")
                except Exception:
                    self._renderman_available = False
                    self.logger.info("ℹ️ RenderMan for Maya not available")
            
            # Check if prman Python module is available
            try:
                import prman  # type: ignore
                self._prman_available = True
                self.logger.info("✅ prman Python API available")
            except ImportError:
                self._prman_available = False
                self.logger.info("ℹ️ prman Python API not available")
                
            return self._renderman_available
            
        except Exception as e:
            self.logger.warning(f"RenderMan availability check failed: {e}")
            return False
    
    def is_renderman_available(self) -> bool:
        """Check if RenderMan is available - Public API"""
        return self._renderman_available
    
    def is_prman_available(self) -> bool:
        """Check if prman Python API is available - Public API"""
        return self._prman_available
    
    def detect_renderman_nodes(self, namespace: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Detect RenderMan nodes in scene - Single Responsibility
        
        Args:
            namespace: Optional namespace to search within
            
        Returns:
            Dictionary categorizing RenderMan nodes by type
        """
        try:
            import maya.cmds as cmds  # type: ignore
            
            if not self._renderman_available:
                return {}
            
            renderman_nodes = {
                'materials': [],
                'lights': [],
                'volume_aggregates': [],
                'displays': [],
                'channels': [],
                'baking': [],
                'shaders': []
            }
            
            # Search pattern based on namespace
            search_pattern = f"{namespace}:*" if namespace else "*"
            
            # Detect RenderMan materials (PxrSurface, PxrDisney, etc.)
            pxr_materials = cmds.ls(search_pattern, type='shadingEngine') or []
            for mat in pxr_materials:
                connections = cmds.listConnections(f"{mat}.surfaceShader", source=True) or []
                for conn in connections:
                    node_type = cmds.nodeType(conn)
                    if node_type.startswith('Pxr'):
                        renderman_nodes['materials'].append(conn)
            
            # Detect RenderMan lights (PxrRectLight, PxrDomeLight, etc.)
            light_types = ['PxrRectLight', 'PxrDomeLight', 'PxrDiskLight', 
                          'PxrSphereLight', 'PxrCylinderLight', 'PxrDistantLight']
            for light_type in light_types:
                lights = cmds.ls(search_pattern, type=light_type) or []
                renderman_nodes['lights'].extend(lights)
            
            # Detect volume aggregates
            volume_aggs = cmds.ls(search_pattern, type='rmanVolumeAggregateSet') or []
            renderman_nodes['volume_aggregates'].extend(volume_aggs)
            
            # Detect RenderMan displays
            displays = cmds.ls(search_pattern, type='rmanDisplay') or []
            renderman_nodes['displays'].extend(displays)
            
            # Detect RenderMan display channels
            channels = cmds.ls(search_pattern, type='rmanDisplayChannel') or []
            renderman_nodes['channels'].extend(channels)
            
            # Detect baking globals
            if cmds.objExists('rmanBakingGlobals'):
                renderman_nodes['baking'].append('rmanBakingGlobals')
            
            # Detect RenderMan shaders (all Pxr nodes)
            all_nodes = cmds.ls(search_pattern) or []
            for node in all_nodes:
                try:
                    node_type = cmds.nodeType(node)
                    if node_type.startswith('Pxr') and node not in renderman_nodes['materials']:
                        renderman_nodes['shaders'].append(node)
                except Exception:
                    continue
            
            return renderman_nodes
            
        except Exception as e:
            self.logger.error(f"RenderMan node detection failed: {e}")
            return {}
    
    def generate_renderman_thumbnail(self, file_path: Path, output_path: Path, 
                                    size: tuple = (256, 256)) -> bool:
        """
        Generate high-quality thumbnail using RenderMan IPR
        
        Args:
            file_path: Asset file to render
            output_path: Output thumbnail path
            size: Thumbnail dimensions (width, height)
            
        Returns:
            True if successful
        """
        try:
            import maya.cmds as cmds  # type: ignore
            import maya.mel as mel  # type: ignore
            
            if not self._renderman_available:
                self.logger.warning("RenderMan not available for thumbnail generation")
                return False
            
            # Set up RenderMan IPR settings for quick preview
            if cmds.objExists('rmanGlobals'):
                # Low-quality fast settings for thumbnails
                cmds.setAttr('rmanGlobals.pixelVariance', 0.15)  # Lower quality for speed
                cmds.setAttr('rmanGlobals.minSamples', 1)
                cmds.setAttr('rmanGlobals.maxSamples', 8)  # Fast sampling
                
            # Set render resolution
            cmds.setAttr('defaultResolution.width', size[0])
            cmds.setAttr('defaultResolution.height', size[1])
            cmds.setAttr('defaultResolution.deviceAspectRatio', size[0] / size[1])
            
            # Frame all objects for good composition
            cmds.viewFit()
            
            # Get active camera
            active_panel = cmds.getPanel(withFocus=True)
            if 'modelPanel' in active_panel:
                camera = cmds.modelPanel(active_panel, query=True, camera=True)
            else:
                # Use persp camera as fallback
                camera = 'persp'
            
            # Render with RenderMan
            mel.eval('RenderViewWindow;')  # Ensure render view is available
            
            # Use RenderMan's render command
            mel.eval(f'rman render -cam {camera}')
            
            # Save the render
            render_view = mel.eval('$tmp = $gRenderViewWindow')
            if render_view:
                cmds.renderWindowEditor(render_view, edit=True, 
                                       writeImage=str(output_path))
            
            if output_path.exists():
                self.logger.info(f"✅ RenderMan thumbnail generated: {output_path.name}")
                return True
            else:
                self.logger.warning(f"⚠️ RenderMan thumbnail generation failed")
                return False
                
        except Exception as e:
            self.logger.error(f"RenderMan thumbnail generation error: {e}")
            return False
    
    def extract_renderman_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract RenderMan-specific metadata from asset
        
        Args:
            file_path: Asset file path
            
        Returns:
            Dictionary of RenderMan metadata
        """
        try:
            import maya.cmds as cmds  # type: ignore
            
            if not self._renderman_available:
                return {}
            
            metadata = {
                'has_renderman': False,
                'renderman_version': None,
                'material_count': 0,
                'light_count': 0,
                'shader_count': 0,
                'uses_volume_rendering': False,
                'render_settings': {}
            }
            
            # Detect RenderMan version
            try:
                version = cmds.pluginInfo('RenderMan_for_Maya.py', query=True, version=True)
                metadata['renderman_version'] = version
            except Exception:
                pass
            
            # Detect nodes
            nodes = self.detect_renderman_nodes()
            
            if any(nodes.values()):
                metadata['has_renderman'] = True
                metadata['material_count'] = len(nodes.get('materials', []))
                metadata['light_count'] = len(nodes.get('lights', []))
                metadata['shader_count'] = len(nodes.get('shaders', []))
                metadata['uses_volume_rendering'] = len(nodes.get('volume_aggregates', [])) > 0
            
            # Extract render settings if available
            if cmds.objExists('rmanGlobals'):
                try:
                    metadata['render_settings'] = {
                        'pixel_variance': cmds.getAttr('rmanGlobals.pixelVariance'),
                        'min_samples': cmds.getAttr('rmanGlobals.minSamples'),
                        'max_samples': cmds.getAttr('rmanGlobals.maxSamples'),
                        'integrator': self._get_active_integrator()
                    }
                except Exception:
                    pass
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"RenderMan metadata extraction error: {e}")
            return {}
    
    def _get_active_integrator(self) -> Optional[str]:
        """Get active RenderMan integrator - Helper method"""
        try:
            import maya.cmds as cmds  # type: ignore
            
            # Check for PxrPathTracer (most common)
            if cmds.objExists('PxrPathTracer'):
                return 'PxrPathTracer'
            
            # Check for other integrators
            integrators = ['PxrUnified', 'PxrVCM', 'PxrDirectLighting']
            for integrator in integrators:
                if cmds.objExists(integrator):
                    return integrator
            
            return None
            
        except Exception:
            return None
    
    def cleanup_renderman_nodes(self, namespace: str) -> int:
        """
        Clean up RenderMan nodes in namespace - Enhanced cleanup
        
        Args:
            namespace: Namespace to clean
            
        Returns:
            Number of nodes cleaned
        """
        try:
            import maya.cmds as cmds  # type: ignore
            
            if not self._renderman_available:
                return 0
            
            cleaned_count = 0
            
            # Detect all RenderMan nodes
            nodes = self.detect_renderman_nodes(namespace)
            
            # Clean volume aggregates first (most problematic)
            for vol_agg in nodes.get('volume_aggregates', []):
                try:
                    # Use existing cleanup logic
                    if cmds.objExists(vol_agg):
                        cmds.lockNode(vol_agg, lock=False)
                        cmds.delete(vol_agg)
                        cleaned_count += 1
                except Exception:
                    continue
            
            # Clean displays and channels
            for display in nodes.get('displays', []):
                try:
                    if cmds.objExists(display):
                        cmds.delete(display)
                        cleaned_count += 1
                except Exception:
                    continue
            
            for channel in nodes.get('channels', []):
                try:
                    if cmds.objExists(channel):
                        cmds.delete(channel)
                        cleaned_count += 1
                except Exception:
                    continue
            
            self.logger.info(f"🧹 Cleaned {cleaned_count} RenderMan nodes from: {namespace}")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"RenderMan cleanup error: {e}")
            return 0
    
    def get_renderman_info(self) -> Dict[str, Any]:
        """
        Get RenderMan installation info - Diagnostic method
        
        Returns:
            Dictionary with RenderMan information
        """
        info = {
            'available': self._renderman_available,
            'prman_api': self._prman_available,
            'version': None,
            'plugin_loaded': False
        }
        
        try:
            import maya.cmds as cmds  # type: ignore
            
            if self._renderman_available:
                info['plugin_loaded'] = True
                try:
                    info['version'] = cmds.pluginInfo('RenderMan_for_Maya.py', 
                                                      query=True, version=True)
                except Exception:
                    pass
            
        except Exception:
            pass
        
        return info


# Singleton instance
_renderman_service = None


def get_renderman_service() -> RenderManService:
    """Get or create RenderMan service singleton - Factory Pattern"""
    global _renderman_service
    if _renderman_service is None:
        _renderman_service = RenderManService()
    return _renderman_service
