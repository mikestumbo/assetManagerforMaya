"""
USD BlendShape Reader - DRAFT Implementation
Reads UsdSkel BlendShape data and creates Maya blendShape nodes

This handles FK/IK blendshape visibility issues where multiple meshes appear.
"""

import logging
from typing import Optional, List, Any
from dataclasses import dataclass
from pathlib import Path

try:
    from pxr import Usd, UsdGeom, UsdSkel  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    Usd = None
    UsdGeom = None
    UsdSkel = None

try:
    import maya.cmds as cmds  # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    cmds = None

logger = logging.getLogger(__name__)


@dataclass
class UsdBlendShapeData:
    """Container for USD BlendShape data"""
    mesh_path: str
    target_paths: List[str]  # Paths to blendshape target geometries
    target_names: List[str]  # Names for each target
    weights: List[float]  # Default weight values


class UsdBlendShapeReader:
    """
    Reads USD BlendShape data

    USD stores blendshapes as:
    - SkelAnimation with blendShapes attribute
    - Or separate Mesh prims marked as blendshape targets
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def read_blendshapes_for_mesh(
        self,
        stage: Any,  # Usd.Stage
        mesh_prim: Any,  # Usd.Prim
        skel_root: Any  # Usd.Prim
    ) -> Optional[UsdBlendShapeData]:
        """
        Read blendshape data for a skinned mesh

        Args:
            stage: USD stage
            mesh_prim: Mesh prim to check for blendshapes
            skel_root: SkelRoot prim

        Returns:
            UsdBlendShapeData or None if no blendshapes
        """
        if not USD_AVAILABLE:
            return None

        try:
            mesh_path = str(mesh_prim.GetPath())

            # Method 1: Check for skel:blendShapes attribute on mesh
            blend_attr = mesh_prim.GetAttribute("skel:blendShapes")
            if blend_attr and blend_attr.IsValid():
                self.logger.info(f"Found skel:blendShapes on {mesh_path}")
                # This contains relationship to blendshape targets

            # Method 2: Check SkelAnimation for blendShapes
            # Look for SkelAnimation prims under SkelRoot
            for child_prim in skel_root.GetAllChildren():
                if child_prim.IsA(UsdSkel.Animation):
                    anim = UsdSkel.Animation(child_prim)

                    # Check if it has blendShapes
                    blend_shapes_attr = anim.GetBlendShapesAttr()
                    if blend_shapes_attr:
                        blend_shape_names = blend_shapes_attr.Get()
                        if blend_shape_names:
                            self.logger.info(f"Found {len(blend_shape_names)} blendshapes in SkelAnimation")

                            # Get blendshape weights
                            weights_attr = anim.GetBlendShapeWeightsAttr()
                            weights = weights_attr.Get() if weights_attr else []

                            # TODO: Find target geometry prims
                            # These are usually sibling meshes with naming convention

                            return UsdBlendShapeData(
                                mesh_path=mesh_path,
                                target_paths=[],  # TODO: Find targets
                                target_names=list(blend_shape_names) if blend_shape_names else [],
                                weights=list(weights) if weights else []
                            )

            # Method 3: Look for sibling meshes that might be blendshape targets
            # Common pattern: mesh, mesh_FK, mesh_IK, etc.
            parent_prim = mesh_prim.GetParent()
            if parent_prim:
                mesh_name = mesh_prim.GetName()
                possible_targets = []

                for sibling in parent_prim.GetAllChildren():
                    if sibling == mesh_prim:
                        continue

                    if sibling.IsA(UsdGeom.Mesh):
                        sibling_name = sibling.GetName()
                        # Check if this looks like a blendshape target
                        # Common patterns: baseName_targetName, baseName_FK, baseName_IK
                        if sibling_name.startswith(mesh_name):
                            possible_targets.append(str(sibling.GetPath()))
                            self.logger.info(f"Found possible blendshape target: {sibling_name}")

                if possible_targets:
                    target_names = [Path(p).name for p in possible_targets]
                    return UsdBlendShapeData(
                        mesh_path=mesh_path,
                        target_paths=possible_targets,
                        target_names=target_names,
                        weights=[0.0] * len(possible_targets)
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error reading blendshapes for {mesh_prim.GetPath()}: {e}")
            import traceback
            traceback.print_exc()
            return None


class MayaBlendShapeBuilder:
    """Creates Maya blendShape nodes from USD data"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_blendshape(
        self,
        base_mesh: str,
        target_meshes: List[str],
        target_names: List[str],
        weights: List[float],
        namespace: str = ""
    ) -> Optional[str]:
        """
        Create Maya blendShape node

        Args:
            base_mesh: Base mesh name
            target_meshes: List of target mesh names
            target_names: Names for each target
            weights: Default weight values
            namespace: Namespace prefix

        Returns:
            blendShape node name or None
        """
        if not MAYA_AVAILABLE:
            return None

        try:
            if not target_meshes:
                return None

            # Verify meshes exist
            if not cmds.objExists(base_mesh):
                self.logger.error(f"Base mesh not found: {base_mesh}")
                return None

            valid_targets = []
            for target in target_meshes:
                if cmds.objExists(target):
                    valid_targets.append(target)
                else:
                    self.logger.warning(f"Target mesh not found: {target}")

            if not valid_targets:
                return None

            # Create blendShape node
            blend_shape_name = f"{namespace}:{base_mesh}_blendShape" if namespace else f"{base_mesh}_blendShape"

            # Create blendShape with all targets
            blend_node = cmds.blendShape(
                *valid_targets,
                base_mesh,
                name=blend_shape_name,
                origin="world"
            )[0]

            # Set target names and weights
            for idx, (target_name, weight) in enumerate(zip(target_names, weights)):
                # Set alias
                cmds.aliasAttr(target_name, f"{blend_node}.weight[{idx}]")
                # Set default weight
                cmds.setAttr(f"{blend_node}.{target_name}", weight)

            # Hide target meshes (mark as intermediate objects)
            for target in valid_targets:
                target_shape = target
                if cmds.objectType(target) == "transform":
                    shapes = cmds.listRelatives(target, shapes=True, fullPath=True)
                    if shapes:
                        target_shape = shapes[0]

                cmds.setAttr(f"{target_shape}.intermediateObject", True)

            self.logger.info(f"[OK] Created blendShape: {blend_node} with {len(valid_targets)} targets")
            return blend_node

        except Exception as e:
            self.logger.error(f"Failed to create blendShape: {e}")
            import traceback
            traceback.print_exc()
            return None
