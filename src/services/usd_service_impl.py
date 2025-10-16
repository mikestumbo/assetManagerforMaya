#!/usr/bin/env python3
"""
USD Service Implementation - Comprehensive USD API Integration
Provides USD stage inspection, metadata extraction, and thumbnail generation

Official API Documentation:
- USD API Reference: https://openusd.org/release/api/index.html
- USD Python API: https://openusd.org/release/api/usd_page_front.html
- Core Classes: https://openusd.org/release/api/usd_page_object_model.html
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class UsdService:
    """Service for USD (Universal Scene Description) integration in Maya"""
    
    def __init__(self):
        """Initialize USD service"""
        self._usd_available = False
        self._mayausd_available = False
        self._pxr_available = False
        
        # Check USD availability
        self._check_usd_availability()
        
        if self._usd_available:
            print("✅ USD Service initialized - Disney's Universal Scene Description support active")
        else:
            print("ℹ️ USD Service initialized - USD API not available (optional)")
    
    def _check_usd_availability(self) -> bool:
        """Check if USD is available in Maya"""
        try:
            # Check for mayaUSD plugin
            import maya.cmds as cmds  # type: ignore
            
            # Try to load mayaUSD plugin if not loaded
            if not cmds.pluginInfo('mayaUsdPlugin', query=True, loaded=True):
                try:
                    cmds.loadPlugin('mayaUsdPlugin', quiet=True)
                    print("✅ mayaUsdPlugin loaded successfully")
                except Exception as e:
                    print(f"ℹ️ mayaUsdPlugin not available: {e}")
            
            self._mayausd_available = cmds.pluginInfo('mayaUsdPlugin', query=True, loaded=True)
            
            # Check for pxr USD Python API
            try:
                from pxr import Usd, UsdGeom, UsdShade, Sdf  # type: ignore
                self._pxr_available = True
                print("✅ Pixar USD Python API available")
            except ImportError:
                print("ℹ️ Pixar USD Python API not available")
                self._pxr_available = False
            
            self._usd_available = self._mayausd_available or self._pxr_available
            return self._usd_available
            
        except ImportError:
            print("ℹ️ Maya not available - USD service in limited mode")
            return False
        except Exception as e:
            print(f"⚠️ Error checking USD availability: {e}")
            return False
    
    def is_usd_available(self) -> bool:
        """Check if USD is available"""
        return self._usd_available
    
    def get_usd_info(self) -> Dict[str, Any]:
        """Get USD system information"""
        return {
            'usd_available': self._usd_available,
            'mayausd_available': self._mayausd_available,
            'pxr_available': self._pxr_available,
            'supported_formats': ['.usd', '.usda', '.usdc', '.usdz']
        }
    
    def detect_usd_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Detect USD content in a file
        
        Args:
            file_path: Path to USD file
            
        Returns:
            Dictionary with USD content information
        """
        if not self._pxr_available:
            return {
                'is_usd': file_path.suffix.lower() in ['.usd', '.usda', '.usdc', '.usdz'],
                'format': file_path.suffix.lower(),
                'detailed_info_available': False
            }
        
        try:
            from pxr import Usd, UsdGeom, UsdShade, Sdf  # type: ignore
            
            # Open USD stage
            stage = Usd.Stage.Open(str(file_path))
            if not stage:
                return {'is_usd': False, 'error': 'Failed to open USD stage'}
            
            # Get root layer
            root_layer = stage.GetRootLayer()
            
            # Count different types of prims
            prim_counts = self._count_prims(stage)
            
            # Get layer information
            layer_info = self._get_layer_info(stage)
            
            # Get variant information
            variant_info = self._get_variant_info(stage)
            
            # Get metadata
            metadata = self._extract_stage_metadata(stage)
            
            return {
                'is_usd': True,
                'format': file_path.suffix.lower(),
                'detailed_info_available': True,
                'stage_info': {
                    'root_path': str(root_layer.identifier),
                    'default_prim': stage.GetDefaultPrim().GetName() if stage.GetDefaultPrim() else None,
                    'frame_range': (stage.GetStartTimeCode(), stage.GetEndTimeCode()),
                    'fps': stage.GetFramesPerSecond() if hasattr(stage, 'GetFramesPerSecond') else None,
                },
                'prim_counts': prim_counts,
                'layers': layer_info,
                'variants': variant_info,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error detecting USD content in {file_path}: {e}")
            return {
                'is_usd': True,
                'format': file_path.suffix.lower(),
                'error': str(e)
            }
    
    def _count_prims(self, stage) -> Dict[str, Any]:
        """Count different types of prims in a USD stage"""
        try:
            from pxr import UsdGeom, UsdShade, UsdLux  # type: ignore
            
            counts = {
                'total': 0,
                'mesh': 0,
                'curve': 0,
                'points': 0,
                'xform': 0,
                'camera': 0,
                'light': 0,
                'material': 0,
                'scope': 0,
                'other': 0
            }
            
            for prim in stage.Traverse():
                counts['total'] += 1
                
                if prim.IsA(UsdGeom.Mesh):
                    counts['mesh'] += 1
                elif prim.IsA(UsdGeom.BasisCurves) or prim.IsA(UsdGeom.NurbsCurves):
                    counts['curve'] += 1
                elif prim.IsA(UsdGeom.Points):
                    counts['points'] += 1
                elif prim.IsA(UsdGeom.Xform):
                    counts['xform'] += 1
                elif prim.IsA(UsdGeom.Camera):
                    counts['camera'] += 1
                elif hasattr(UsdLux, 'Light') and prim.IsA(UsdLux.Light):
                    counts['light'] += 1
                elif prim.IsA(UsdShade.Material):
                    counts['material'] += 1
                elif prim.IsA(UsdGeom.Scope):
                    counts['scope'] += 1
                else:
                    counts['other'] += 1
            
            return counts
            
        except Exception as e:
            logger.error(f"Error counting prims: {e}")
            return {'total': 0, 'error': str(e)}
    
    def _get_layer_info(self, stage) -> List[Dict[str, Any]]:
        """Get information about USD layers"""
        try:
            layers = []
            layer_stack = stage.GetLayerStack()
            
            for layer in layer_stack:
                layer_info = {
                    'identifier': layer.identifier,
                    'display_name': layer.GetDisplayName(),
                    'anonymous': layer.anonymous,
                    'has_authored_metadata': bool(layer.GetAllAuthoredMetadata())
                }
                layers.append(layer_info)
            
            return layers
            
        except Exception as e:
            logger.error(f"Error getting layer info: {e}")
            return []
    
    def _get_variant_info(self, stage) -> List[Dict[str, Any]]:
        """Get information about variant sets"""
        try:
            variants = []
            
            for prim in stage.Traverse():
                if prim.HasVariantSets():
                    variant_sets = prim.GetVariantSets()
                    set_names = variant_sets.GetNames()
                    
                    for set_name in set_names:
                        variant_set = variant_sets.GetVariantSet(set_name)
                        variants.append({
                            'prim_path': str(prim.GetPath()),
                            'set_name': set_name,
                            'variants': variant_set.GetVariantNames(),
                            'selection': variant_set.GetVariantSelection()
                        })
            
            return variants
            
        except Exception as e:
            logger.error(f"Error getting variant info: {e}")
            return []
    
    def _extract_stage_metadata(self, stage) -> Dict[str, Any]:
        """Extract metadata from USD stage"""
        try:
            root_layer = stage.GetRootLayer()
            metadata = {}
            
            # Get common metadata
            if root_layer.HasInfo('comment'):
                metadata['comment'] = root_layer.GetInfo('comment')
            
            if root_layer.HasInfo('documentation'):
                metadata['documentation'] = root_layer.GetInfo('documentation')
            
            # Get custom layer data
            custom_data = root_layer.customLayerData
            if custom_data:
                metadata['custom_data'] = dict(custom_data)
            
            # Get up axis
            from pxr import UsdGeom  # type: ignore
            up_axis = UsdGeom.GetStageUpAxis(stage)
            metadata['up_axis'] = up_axis
            
            # Get metrics
            if hasattr(UsdGeom, 'GetStageMetersPerUnit'):
                metadata['meters_per_unit'] = UsdGeom.GetStageMetersPerUnit(stage)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}
    
    def extract_usd_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from USD file
        
        Args:
            file_path: Path to USD file
            
        Returns:
            Dictionary with metadata
        """
        content = self.detect_usd_content(file_path)
        
        if not content.get('is_usd'):
            return {'error': 'Not a valid USD file'}
        
        metadata = {
            'format': content.get('format'),
            'file_size': file_path.stat().st_size if file_path.exists() else 0,
        }
        
        if content.get('detailed_info_available'):
            metadata.update({
                'stage_info': content.get('stage_info', {}),
                'prim_counts': content.get('prim_counts', {}),
                'layer_count': len(content.get('layers', [])),
                'variant_count': len(content.get('variants', [])),
                'has_variants': len(content.get('variants', [])) > 0,
                'metadata': content.get('metadata', {})
            })
        
        return metadata
    
    def generate_usd_thumbnail(self, file_path: Path, output_path: Path, 
                               size: Tuple[int, int] = (256, 256)) -> bool:
        """
        Generate thumbnail for USD file using Maya viewport
        
        Args:
            file_path: Path to USD file
            output_path: Path for output thumbnail
            size: Thumbnail size (width, height)
            
        Returns:
            True if successful
        """
        if not self._mayausd_available:
            print(f"ℹ️ mayaUSD not available, falling back to standard import")
            return False
        
        try:
            import maya.cmds as cmds  # type: ignore
            import maya.mel as mel  # type: ignore
            
            # Store original state
            original_selection = cmds.ls(selection=True) or []
            
            # Create temporary namespace
            namespace = f"usd_preview_{int(file_path.stat().st_mtime)}"
            
            try:
                # Import USD file
                print(f"📸 Importing USD file: {file_path.name}")
                
                # Use mayaUSD import
                imported_nodes = cmds.file(
                    str(file_path),
                    i=True,
                    namespace=namespace,
                    returnNewNodes=True,
                    options="primPath=/",
                    type="USD Import"
                )
                
                if not imported_nodes:
                    print(f"⚠️ No nodes imported from USD file")
                    return False
                
                print(f"✅ Imported {len(imported_nodes)} nodes from USD")
                
                # Find geometry
                meshes = cmds.ls(f"{namespace}:*", type='mesh', long=True) or []
                if not meshes:
                    # Try without namespace prefix
                    meshes = cmds.ls(imported_nodes, type='mesh', long=True) or []
                
                if not meshes:
                    print(f"⚠️ No geometry found in USD file")
                    return False
                
                # Frame geometry
                transforms = []
                for mesh in meshes[:10]:  # Limit to first 10 meshes
                    try:
                        parent = cmds.listRelatives(mesh, parent=True, fullPath=True)
                        if parent:
                            transforms.extend(parent)
                    except:
                        pass
                
                if transforms:
                    cmds.select(transforms)
                    mel.eval('fitPanel -selected;')
                    cmds.select(clear=True)
                
                # Create output directory
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Capture playblast
                width, height = size
                import tempfile
                import os
                import shutil
                
                temp_dir = tempfile.mkdtemp(prefix="usd_thumbnail_")
                temp_file = os.path.join(temp_dir, "thumbnail")
                
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
                
                # Find generated file
                generated_files = [
                    os.path.join(temp_dir, f)
                    for f in os.listdir(temp_dir)
                    if f.endswith('.png')
                ]
                
                if generated_files:
                    shutil.copy2(generated_files[0], str(output_path))
                    print(f"✅ USD thumbnail generated: {output_path}")
                    
                    # Cleanup temp directory
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        pass
                    
                    return True
                else:
                    print(f"❌ No thumbnail file generated")
                    return False
                
            finally:
                # Cleanup namespace
                try:
                    if cmds.namespace(exists=namespace):
                        cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)
                except Exception as e:
                    print(f"⚠️ Cleanup warning: {e}")
                
                # Restore selection
                if original_selection:
                    try:
                        cmds.select(original_selection)
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Error generating USD thumbnail: {e}")
            print(f"❌ USD thumbnail generation failed: {e}")
            return False
    
    def import_usd_file(self, file_path: Path, namespace: Optional[str] = None,
                        prim_path: str = "/") -> List[str]:
        """
        Import USD file into Maya scene
        
        Args:
            file_path: Path to USD file
            namespace: Optional namespace for import
            prim_path: USD prim path to import (default: root)
            
        Returns:
            List of imported node names
        """
        if not self._mayausd_available:
            print(f"ℹ️ mayaUSD not available, using standard import")
            return []
        
        try:
            import maya.cmds as cmds  # type: ignore
            
            # Generate namespace if not provided
            if not namespace:
                namespace = f"USD_{file_path.stem}"
            
            # Import USD file
            imported_nodes = cmds.file(
                str(file_path),
                i=True,
                namespace=namespace,
                returnNewNodes=True,
                options=f"primPath={prim_path}",
                type="USD Import"
            )
            
            print(f"✅ Imported USD file: {file_path.name} ({len(imported_nodes)} nodes)")
            return imported_nodes or []
            
        except Exception as e:
            logger.error(f"Error importing USD file: {e}")
            print(f"❌ USD import failed: {e}")
            return []
    
    def get_usd_stage_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get detailed USD stage information
        
        Args:
            file_path: Path to USD file
            
        Returns:
            Dictionary with stage information
        """
        content = self.detect_usd_content(file_path)
        
        if not content.get('is_usd'):
            return {'error': 'Not a valid USD file'}
        
        info = {
            'format': content.get('format'),
            'valid': True,
        }
        
        if content.get('detailed_info_available'):
            info.update({
                'stage_info': content.get('stage_info', {}),
                'prim_counts': content.get('prim_counts', {}),
                'has_layers': len(content.get('layers', [])) > 1,
                'layer_count': len(content.get('layers', [])),
                'has_variants': len(content.get('variants', [])) > 0,
                'variant_sets': len(content.get('variants', [])),
                'metadata': content.get('metadata', {})
            })
        
        return info


# Singleton instance
_usd_service_instance: Optional[UsdService] = None


def get_usd_service() -> UsdService:
    """Get or create USD service singleton instance"""
    global _usd_service_instance
    if _usd_service_instance is None:
        _usd_service_instance = UsdService()
    return _usd_service_instance
