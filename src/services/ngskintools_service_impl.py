# -*- coding: utf-8 -*-
"""
ngSkinTools2 Service Implementation

Provides ngSkinTools2 integration with availability checking.

Author: Asset Manager Development Team
Version: 1.3.0

Official API Documentation:
- ngSkinTools2 API: https://www.ngskintools.com/documentation/v2/api/
- Layers API: https://www.ngskintools.com/documentation/v2/api/layers/
- Target Info: https://www.ngskintools.com/documentation/v2/api/target_info/
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import logging

# Type checking imports - these are optional runtime dependencies
if TYPE_CHECKING:
    try:
        import ngSkinTools2.api # type: ignore
        from ngSkinTools2.api import Layers, init_layers, target_info # type: ignore
    except ImportError:
        pass


class NgSkinToolsService:
    """Service for ngSkinTools2 integration"""
    
    def __init__(self):
        """Initialize ngSkinTools2 service"""
        self.logger = logging.getLogger(__name__)
        self._plugin_available = False
        self._api_available = False
        self._plugin_version = None
        
        # Check availability on initialization
        self._check_ngskintools_availability()
    
    def _check_ngskintools_availability(self) -> None:
        """
        Check if ngSkinTools2 plugin and API are available in Maya.
        Updates internal flags for plugin and API availability.
        """
        try:
            import maya.cmds as cmds # type: ignore
            
            # Check if ngSkinTools2 plugin is loaded
            try:
                plugin_loaded = cmds.pluginInfo('ngSkinTools2', query=True, loaded=True)
                if plugin_loaded:
                    self._plugin_available = True
                    # Get plugin version if available
                    try:
                        self._plugin_version = cmds.pluginInfo('ngSkinTools2', query=True, version=True)
                    except Exception:
                        self._plugin_version = "Unknown"
                    
                    self.logger.info(f"# {__name__} : ✅ ngSkinTools2 plugin detected (v{self._plugin_version})")
                else:
                    self.logger.info(f"# {__name__} : ⚠️ ngSkinTools2 plugin not loaded")
                    return
            except Exception:
                self.logger.info(f"# {__name__} : ⚠️ ngSkinTools2 plugin not available")
                return
            
            # Check if ngSkinTools2 API is available
            try:
                import ngSkinTools2.api  # type: ignore[import-not-found]
                from ngSkinTools2.api import Layers, init_layers, target_info  # type: ignore[import-not-found]
                self._api_available = True
                self.logger.info(f"# {__name__} : ✅ ngSkinTools2 Python API available")
            except ImportError:
                self.logger.info(f"# {__name__} : ⚠️ ngSkinTools2 Python API not available")
                return
                
        except Exception as e:
            self.logger.warning(f"# {__name__} : Error checking ngSkinTools2 availability: {e}")
    
    def is_available(self) -> bool:
        """
        Check if ngSkinTools2 is fully available (plugin + API).
        
        Returns:
            bool: True if both plugin and API are available
        """
        return self._plugin_available and self._api_available
    
    def get_plugin_version(self) -> Optional[str]:
        """
        Get ngSkinTools2 plugin version.
        
        Returns:
            str: Plugin version string, or None if not available
        """
        return self._plugin_version if self._plugin_available else None
    
    def detect_ngskintools_nodes(self, namespace: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Detect and categorize ngSkinTools2 nodes in the scene.
        
        Args:
            namespace: Optional namespace to filter nodes
            
        Returns:
            dict: Categorized ngSkinTools2 nodes:
                - 'data_nodes': ngSkinLayerData nodes
                - 'skin_clusters': Skin clusters with ngSkinTools2 layers enabled
                - 'layer_count': Total number of layers across all meshes
                - 'total_nodes': Total number of ngSkinTools2-related nodes
        """
        result = {
            'data_nodes': [],
            'skin_clusters': [],
            'layer_count': 0,
            'total_nodes': 0
        }
        
        if not self._plugin_available:
            return result
        
        try:
            import maya.cmds as cmds # type: ignore
            
            # Build namespace filter
            ns_filter = f"{namespace}:*" if namespace else "*"
            
            # Find ngSkinTools2 data nodes (ngst2SkinLayerData)
            data_nodes = cmds.ls(ns_filter, type='ngst2SkinLayerData') or []
            result['data_nodes'] = data_nodes
            result['total_nodes'] += len(data_nodes)
            
            # Find skin clusters with ngSkinTools2 enabled
            if self._api_available:
                try:
                    from ngSkinTools2.api import target_info  # type: ignore[import-not-found]
                    
                    # Get all skin clusters in the scene
                    all_skin_clusters = cmds.ls(ns_filter, type='skinCluster') or []
                    
                    for skin_cluster in all_skin_clusters:
                        # Check if this skin cluster has ngSkinTools2 data attached
                        data_node = target_info.get_related_data_node(skin_cluster)
                        if data_node:
                            result['skin_clusters'].append(skin_cluster)
                            
                            # Count layers for this skin cluster
                            try:
                                from ngSkinTools2.api import Layers # type: ignore
                                layers = Layers(skin_cluster)
                                layer_list = layers.list()
                                result['layer_count'] += len(layer_list)
                            except Exception:
                                pass
                                
                except ImportError:
                    pass
            
            self.logger.debug(f"Detected {result['total_nodes']} ngSkinTools2 nodes in namespace '{namespace or 'root'}'")
            
        except Exception as e:
            self.logger.warning(f"Error detecting ngSkinTools2 nodes: {e}")
        
        return result
    
    def extract_ngskintools_metadata(self, target: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from ngSkinTools2-enabled mesh or skin cluster.
        
        Args:
            target: Mesh or skin cluster name
            
        Returns:
            dict: Metadata containing:
                - 'has_ngskintools': Whether ngSkinTools2 is enabled
                - 'plugin_version': ngSkinTools2 plugin version
                - 'data_node': Name of the ngSkinTools2 data node
                - 'skin_cluster': Related skin cluster name
                - 'layer_count': Number of layers
                - 'layer_names': List of layer names
                - 'influence_count': Number of influences in skin cluster
                - 'influence_names': List of influence names
                - 'is_slow_mode': Whether slow API mode is active
                - 'layers_enabled': Whether layers are enabled on this target
        """
        metadata = {
            'has_ngskintools': False,
            'plugin_version': self._plugin_version,
            'data_node': None,
            'skin_cluster': None,
            'layer_count': 0,
            'layer_names': [],
            'influence_count': 0,
            'influence_names': [],
            'is_slow_mode': False,
            'layers_enabled': False
        }
        
        if not self.is_available():
            return metadata
        
        try:
            import maya.cmds as cmds # type: ignore
            from ngSkinTools2.api import target_info, Layers  # type: ignore[import-not-found]
            
            # Check if target exists
            if not cmds.objExists(target):
                return metadata
            
            # Get related skin cluster
            skin_cluster = target_info.get_related_skin_cluster(target)
            if not skin_cluster:
                return metadata
            
            metadata['skin_cluster'] = skin_cluster
            
            # Get related data node
            data_node = target_info.get_related_data_node(target)
            if data_node:
                metadata['has_ngskintools'] = True
                metadata['data_node'] = data_node
            else:
                return metadata
            
            # Check if layers are enabled
            try:
                layers = Layers(target)
                metadata['layers_enabled'] = layers.is_enabled()
                
                if metadata['layers_enabled']:
                    # Get layer information
                    layer_list = layers.list()
                    metadata['layer_count'] = len(layer_list)
                    metadata['layer_names'] = [layer.name for layer in layer_list]
                    
                    # Get influence information
                    influences = layers.list_influences()
                    metadata['influence_count'] = len(influences)
                    metadata['influence_names'] = [inf.path for inf in influences]
                    
            except Exception as layer_error:
                self.logger.debug(f"Error extracting layer data: {layer_error}")
            
            # Check if slow mode is active
            try:
                metadata['is_slow_mode'] = target_info.is_slow_mode_skin_cluster(skin_cluster)
            except Exception:
                pass
            
            self.logger.debug(f"Extracted ngSkinTools2 metadata for '{target}': {metadata['layer_count']} layers")
            
        except Exception as e:
            self.logger.warning(f"Error extracting ngSkinTools2 metadata from '{target}': {e}")
        
        return metadata
    
    def get_scene_summary(self) -> Dict[str, Any]:
        """
        Get summary of all ngSkinTools2 content in the current scene.
        
        Returns:
            dict: Scene summary containing:
                - 'available': Whether ngSkinTools2 is available
                - 'plugin_version': Plugin version
                - 'total_data_nodes': Total number of data nodes
                - 'total_skin_clusters': Total skin clusters with ngSkinTools2
                - 'total_layers': Total number of layers across all meshes
                - 'skinned_meshes': List of meshes with ngSkinTools2 enabled
        """
        summary = {
            'available': self.is_available(),
            'plugin_version': self._plugin_version,
            'total_data_nodes': 0,
            'total_skin_clusters': 0,
            'total_layers': 0,
            'skinned_meshes': []
        }
        
        if not self.is_available():
            return summary
        
        try:
            import maya.cmds as cmds # type: ignore
            from ngSkinTools2.api import target_info, Layers  # type: ignore[import-not-found]
            
            # Get all ngSkinTools2 data nodes
            data_nodes = cmds.ls(type='ngst2SkinLayerData') or []
            summary['total_data_nodes'] = len(data_nodes)
            
            # Get all skin clusters and check for ngSkinTools2
            all_skin_clusters = cmds.ls(type='skinCluster') or []
            
            for skin_cluster in all_skin_clusters:
                data_node = target_info.get_related_data_node(skin_cluster)
                if data_node:
                    summary['total_skin_clusters'] += 1
                    
                    # Get mesh connected to this skin cluster
                    try:
                        shapes = cmds.skinCluster(skin_cluster, query=True, geometry=True) or []
                        if shapes:
                            mesh = shapes[0]
                            summary['skinned_meshes'].append(mesh)
                            
                            # Count layers
                            try:
                                layers = Layers(skin_cluster)
                                layer_list = layers.list()
                                summary['total_layers'] += len(layer_list)
                            except Exception:
                                pass
                    except Exception:
                        pass
            
            self.logger.info(f"ngSkinTools2 scene summary: {summary['total_skin_clusters']} skinned meshes, {summary['total_layers']} layers")
            
        except Exception as e:
            self.logger.warning(f"Error generating ngSkinTools2 scene summary: {e}")
        
        return summary
    
    def cleanup_ngskintools_nodes(self, namespace: str) -> bool:
        """
        Clean up ngSkinTools2 nodes from a specific namespace.
        This is called during asset removal to ensure clean deletion.
        
        Args:
            namespace: Namespace to clean up
            
        Returns:
            bool: True if cleanup was successful
        """
        if not self._plugin_available:
            return True
        
        try:
            import maya.cmds as cmds # type: ignore
            
            # Find all ngSkinTools2 data nodes in this namespace
            ns_filter = f"{namespace}:*"
            data_nodes = cmds.ls(ns_filter, type='ngst2SkinLayerData') or []
            
            if not data_nodes:
                return True
            
            self.logger.debug(f"Cleaning up {len(data_nodes)} ngSkinTools2 data nodes from namespace '{namespace}'")
            
            # Delete data nodes (this should clean up the layers automatically)
            deleted_count = 0
            for node in data_nodes:
                try:
                    if cmds.objExists(node):
                        # Try to unlock the node first
                        try:
                            cmds.lockNode(node, lock=False, lockName=False)
                        except Exception:
                            pass
                        
                        cmds.delete(node)
                        deleted_count += 1
                except Exception as delete_error:
                    self.logger.debug(f"Could not delete ngSkinTools2 node '{node}': {delete_error}")
            
            self.logger.debug(f"Deleted {deleted_count}/{len(data_nodes)} ngSkinTools2 data nodes")
            return deleted_count == len(data_nodes)
            
        except Exception as e:
            self.logger.warning(f"Error cleaning up ngSkinTools2 nodes from namespace '{namespace}': {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about ngSkinTools2 service status.
        
        Returns:
            dict: Service information including availability and capabilities
        """
        return {
            'name': 'ngSkinTools2',
            'available': self.is_available(),
            'plugin_available': self._plugin_available,
            'api_available': self._api_available,
            'version': self._plugin_version,
            'description': 'Advanced layer-based skinning for Maya',
            'capabilities': [
                'Layer-based weight painting',
                'Influence management',
                'Mirror effects',
                'Weight import/export',
                'Dual quaternion skinning'
            ] if self.is_available() else []
        }


# Singleton instance factory
_ngskintools_service_instance = None


def get_ngskintools_service() -> NgSkinToolsService:
    """
    Get singleton instance of NgSkinToolsService.
    
    Returns:
        NgSkinToolsService: Singleton service instance
    """
    global _ngskintools_service_instance
    if _ngskintools_service_instance is None:
        _ngskintools_service_instance = NgSkinToolsService()
    return _ngskintools_service_instance
