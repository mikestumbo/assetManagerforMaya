# -*- coding: utf-8 -*-
"""
Maya Integration Implementation
Concrete implementation of Maya-specific operations

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Optional, List, Dict, Any
from pathlib import Path

from ..core.interfaces.maya_integration import IMayaIntegration
from ..core.models.asset import Asset


class MayaIntegrationImpl(IMayaIntegration):
    """
    Maya Integration Implementation - Single Responsibility for Maya operations
    Uses Adapter Pattern to integrate with Maya's API
    """
    
    def __init__(self):
        self._maya_available = None
        self._maya_cmds = None
        self._maya_version = None
        self._initialize_maya()
    
    def _initialize_maya(self) -> None:
        """Initialize Maya API connection"""
        try:
            import maya.cmds as cmds  # type: ignore
            self._maya_cmds = cmds
            self._maya_available = True
            self._maya_version = cmds.about(version=True)
        except ImportError:
            self._maya_available = False
            self._maya_cmds = None
            self._maya_version = None
    
    def is_maya_available(self) -> bool:
        """Check if Maya is available for operations"""
        return self._maya_available is True
    
    def import_asset(self, asset: Asset, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Import asset into Maya scene
        Single Responsibility: handle Maya import operations
        """
        if not self.is_maya_available():
            return False
        
        try:
            if not asset.file_path.exists():
                return False
            
            # Default import options
            import_options = {
                'type': 'mayaAscii' if asset.file_extension == '.ma' else 'mayaBinary',
                'ignoreVersion': True,
                'mergeNamespacesOnClash': False,
                'rpr': asset.name  # Root prefix
            }
            
            # Update with user options
            if options:
                import_options.update(options)
            
            # Perform import based on file type
            if asset.is_maya_file:
                return self._import_maya_file(asset.file_path, import_options)
            elif asset.file_extension in {'.obj', '.fbx'}:
                return self._import_3d_file(asset.file_path, import_options)
            else:
                return False
                
        except Exception as e:
            print(f"Error importing asset {asset.name}: {e}")
            return False
    
    def reference_asset(self, asset: Asset, namespace: Optional[str] = None) -> bool:
        """
        Reference asset in Maya scene
        Single Responsibility: handle Maya reference operations
        """
        if not self.is_maya_available() or not self._maya_cmds:
            return False
        
        try:
            if not asset.file_path.exists() or not asset.is_maya_file:
                return False
            
            # Generate namespace if not provided
            if namespace is None:
                namespace = self._generate_namespace(asset.name)
            
            # Create reference
            reference_node = self._maya_cmds.file(
                str(asset.file_path),
                reference=True,
                namespace=namespace,
                mergeNamespacesOnClash=False,
                ignoreVersion=True
            )
            
            return reference_node is not None
            
        except Exception as e:
            print(f"Error referencing asset {asset.name}: {e}")
            return False
    
    def export_selection(self, export_path: Path, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Export Maya selection to file
        Single Responsibility: handle Maya export operations
        """
        if not self.is_maya_available():
            return False
        
        try:
            # Check if anything is selected
            if not self._maya_cmds:
                return False
            selection = self._maya_cmds.ls(selection=True)
            if not selection:
                return False
            
            # Default export options
            export_options = {
                'exportSelected': True,
                'type': 'mayaAscii' if export_path.suffix == '.ma' else 'mayaBinary',
                'force': True
            }
            
            # Update with user options
            if options:
                export_options.update(options)
            
            # Perform export
            if not self._maya_cmds:
                return False
            self._maya_cmds.file(
                str(export_path),
                **export_options
            )
            
            return export_path.exists()
            
        except Exception as e:
            print(f"Error exporting selection to {export_path}: {e}")
            return False
    
    def get_scene_assets(self) -> List[str]:
        """
        Get list of assets currently in Maya scene
        Single Responsibility: query Maya scene state
        """
        if not self.is_maya_available():
            return []
        
        try:
            scene_assets = []
            
            # Get referenced files
            if not self._maya_cmds:
                return []
            references = self._maya_cmds.file(query=True, reference=True) or []
            scene_assets.extend(references)
            
            # Get imported files (this is more complex, simplified here)
            # Could traverse scene graph and check file nodes
            
            return scene_assets
            
        except Exception as e:
            print(f"Error getting scene assets: {e}")
            return []
    
    def validate_asset_compatibility(self, asset: Asset) -> bool:
        """
        Check if asset is compatible with current Maya version
        Single Responsibility: asset compatibility validation
        """
        if not self.is_maya_available():
            return False
        
        try:
            if not asset.is_maya_file:
                # Non-Maya files are generally compatible
                return asset.file_extension in {'.obj', '.fbx'}
            
            # For Maya files, could check version compatibility
            # This is a simplified check
            return asset.file_path.exists()
            
        except Exception:
            return False
    
    def get_maya_version(self) -> Optional[str]:
        """Get current Maya version"""
        return self._maya_version
    
    def _import_maya_file(self, file_path: Path, options: Dict[str, Any]) -> bool:
        """Import Maya-specific file formats"""
        try:
            if not self._maya_cmds:
                return False
            self._maya_cmds.file(
                str(file_path),
                i=True,  # Import
                **{k: v for k, v in options.items() if k != 'type'}
            )
            return True
        except Exception as e:
            print(f"Error importing Maya file {file_path}: {e}")
            return False
    
    def _import_3d_file(self, file_path: Path, options: Dict[str, Any]) -> bool:
        """Import 3D file formats (OBJ, FBX, etc.)"""
        try:
            if not self._maya_cmds:
                return False
                
            extension = file_path.suffix.lower()
            
            if extension == '.obj':
                # Import OBJ file
                self._maya_cmds.file(
                    str(file_path),
                    i=True,
                    type='OBJ',
                    **{k: v for k, v in options.items() if k not in ['type']}
                )
            elif extension == '.fbx':
                # Import FBX file (requires FBX plugin)
                try:
                    self._maya_cmds.loadPlugin('fbxmaya', quiet=True)
                    self._maya_cmds.file(
                        str(file_path),
                        i=True,
                        type='FBX',
                        **{k: v for k, v in options.items() if k not in ['type']}
                    )
                except Exception:
                    return False
            else:
                return False
            
            return True
            
        except Exception as e:
            print(f"Error importing 3D file {file_path}: {e}")
            return False
    
    def _generate_namespace(self, asset_name: str) -> str:
        """Generate unique namespace for asset"""
        if not self.is_maya_available() or not self._maya_cmds:
            return asset_name
        
        base_namespace = asset_name.replace(' ', '_').replace('-', '_')
        
        # Check if namespace already exists
        existing_namespaces = self._maya_cmds.namespaceInfo(listOnlyNamespaces=True) or []
        
        if base_namespace not in existing_namespaces:
            return base_namespace
        
        # Generate unique namespace
        counter = 1
        while f"{base_namespace}_{counter}" in existing_namespaces:
            counter += 1
        
        return f"{base_namespace}_{counter}"
