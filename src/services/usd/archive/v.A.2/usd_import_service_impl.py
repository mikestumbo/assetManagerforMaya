# -*- coding: utf-8 -*-
"""
USD Import Service Implementation
Main orchestrator for importing USD files with automatic skinCluster reconstruction

Author: Mike Stumbo
Version: 1.5.0
Date: November 2025
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

# USD imports
try:
    from pxr import Usd, UsdGeom, UsdSkel  # type: ignore
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    Usd: Any = None  # type: ignore
    UsdGeom: Any = None  # type: ignore
    UsdSkel: Any = None  # type: ignore

# Maya imports
try:
    import maya.cmds as cmds  # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    cmds: Any = None  # type: ignore

# Internal imports
from ...core.interfaces.usd_import_service import (
    IUsdImportService,
    UsdImportOptions,
    ImportResult
)
from .usd_skeleton_reader_impl import (
    UsdSkeletonReaderImpl,
    UsdSkeletonData
)
from .maya_skin_cluster_builder_impl import MayaSkinClusterBuilderImpl
from .pure_python_usd_reader_impl import get_pure_python_usd_reader
from .external_usd_bridge_impl import get_usdview_bridge

logger = logging.getLogger(__name__)


class UsdImportServiceImpl(IUsdImportService):
    """
    USD Import Service Implementation - Multi-Method Architecture

    Orchestrates USD import with intelligent fallback chain:
    1. PRIMARY: mayaUSD plugin (fastest, most compatible)
    2. FALLBACK 1: Pure Python USD Reader (no plugin dependencies)
    3. FALLBACK 2: USD View tools (Pixar's official utilities)

    All methods support automatic skinCluster reconstruction!

    Clean Code: Strategy Pattern with fallback chain
    INDUSTRY FIRST: Complete USD pipeline with zero-plugin fallback!
    """

    def __init__(self):
        """Initialize USD import service"""
        self.logger = logging.getLogger(__name__)

        # Validate dependencies
        if not USD_AVAILABLE:
            self.logger.error("USD Python libraries not available!")
        if not MAYA_AVAILABLE:
            self.logger.error("Maya cmds not available!")

        # Initialize sub-components
        self.skeleton_reader = UsdSkeletonReaderImpl()
        self.skin_builder = MayaSkinClusterBuilderImpl()

        # Initialize alternative import methods
        self.pure_python_reader = get_pure_python_usd_reader()
        self.usdview_bridge = get_usdview_bridge()

        # Log available methods
        methods = ['mayaUSD']
        if self.pure_python_reader:
            methods.append('Pure Python')
        if self.usdview_bridge.is_available():
            methods.append('USD View')

        self.logger.info(f"USD Import Service initialized with {len(methods)} methods: {', '.join(methods)}")

    def import_usd_file(
        self,
        usd_path: Path,
        options: Optional[UsdImportOptions] = None
    ) -> ImportResult:
        """
        Import USD file with automatic skinning reconstruction

        Args:
            usd_path: Path to USD file
            options: Import configuration

        Returns:
            ImportResult with detailed feedback
        """
        if not USD_AVAILABLE or not MAYA_AVAILABLE:
            return ImportResult(
                success=False,
                error_message="USD or Maya not available"
            )

        # Use default options if not provided
        if options is None:
            options = UsdImportOptions()

        # Validate USD file
        is_valid, error_msg = self.validate_usd_file(usd_path)
        if not is_valid:
            return ImportResult(success=False, error_message=error_msg)

        self.logger.info(f"START: Starting USD import: {usd_path.name}")

        # Create result object
        result = ImportResult(success=False)

        try:
            # Step 1: Intelligent import method selection with fallback chain
            namespace = None
            import_method = None

            # Try Method 1: MayaUSD (fastest, most compatible)
            namespace = self._import_with_mayausd(usd_path, options, result)
            if namespace:
                import_method = 'mayaUSD'
                self.logger.info("SUCCESS: MayaUSD import successful")

            # Try Method 2: Pure Python USD Reader (no plugin dependencies)
            if not namespace:
                self.logger.warning("MayaUSD import failed, trying Pure Python method...")
                namespace = self._import_with_pure_python(usd_path, options, result)
                if namespace:
                    import_method = 'Pure Python'
                    self.logger.info("SUCCESS: Pure Python import successful")

            # Try Method 3: USD View conversion (Pixar's official tools)
            if not namespace and self.usdview_bridge.is_available():
                self.logger.warning("Pure Python import failed, trying USD View conversion...")
                namespace = self._import_with_usdview(usd_path, options, result)
                if namespace:
                    import_method = 'USD View'
                    self.logger.info("SUCCESS: USD View conversion successful")

            # All methods failed
            if not namespace:
                result.error_message = "All USD import methods failed (mayaUSD, Pure Python, USD View)"
                self.logger.error(result.error_message)
                return result

            result.import_method = import_method
            self.logger.info(f"RESULT: Successfully imported using: {import_method}")

            # Step 2: Apply skin weights if requested
            print("=" * 80)
            print(f"CHECKING: CHECKING SKINNING: options.apply_skin_weights = {options.apply_skin_weights}")
            print("=" * 80)

            if options.apply_skin_weights:
                print(
                    f"SUCCESS: Going to call _apply_skin_weights_from_usd "
                    f"with namespace={namespace}"
                )
                self.logger.info(
                    f"HOUDINI: apply_skin_weights=True, calling "
                    f"_apply_skin_weights_from_usd with namespace={namespace}"
                )
                self._apply_skin_weights_from_usd(usd_path, namespace, options, result)
                print(
                    f"SUCCESS: Returned from _apply_skin_weights_from_usd, "
                    f"created {result.skin_clusters_created} skinClusters"
                )
                self.logger.info(
                    f"HOUDINI: Finished _apply_skin_weights_from_usd, "
                    f"created {result.skin_clusters_created} skinClusters"
                )
            else:
                print("SKIPPING: Skipping skinning because apply_skin_weights=False")
                self.logger.info("SKIPPING: apply_skin_weights=False, skipping skin weight application")

            # Step 4: Reconstruct rig connections for functional controllers - INDUSTRY FIRST!
            if options.import_nurbs_curves and options.import_rig_connections and result.imported_curves:
                self.logger.info("🎯 Reconstructing rig connections for functional controllers...")
                connections_restored = self._reconstruct_rig_connections(usd_path, namespace, options, result)
                self.logger.info(f"✨ Restored {connections_restored} rig connections - controllers are now functional!")

            # Mark as successful
            result.success = True
            self.logger.info(f"SUCCESS: {result.get_summary()}")

        except Exception as e:
            self.logger.error(f"USD import failed: {e}")
            import traceback
            traceback.print_exc()
            result.success = False
            result.error_message = str(e)

        return result

    def import_with_skinning(
        self,
        usd_path: Path,
        namespace: Optional[str] = None
    ) -> ImportResult:
        """
        Convenience method: Import USD with automatic skinning

        Args:
            usd_path: Path to USD file
            namespace: Optional namespace

        Returns:
            ImportResult
        """
        options = UsdImportOptions(
            apply_skin_weights=True,
            namespace=namespace
        )
        return self.import_usd_file(usd_path, options)

    def validate_usd_file(self, usd_path: Path) -> tuple[bool, str]:
        """
        Validate USD file before import

        Args:
            usd_path: Path to USD file

        Returns:
            (is_valid, error_message)
        """
        if not USD_AVAILABLE:
            return False, "USD not available"

        try:
            # Check file exists
            if not usd_path.exists():
                return False, f"File not found: {usd_path}"

            # Check file extension
            if usd_path.suffix.lower() not in {'.usd', '.usda', '.usdc', '.usdz'}:
                return False, f"Not a USD file: {usd_path.suffix}"

            # Try to open USD stage
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                return False, "Could not open USD stage"

            # Check for content
            if not stage.GetPseudoRoot():
                return False, "Empty USD stage"

            return True, ""

        except Exception as e:
            return False, f"USD validation error: {e}"

    def get_usd_info(self, usd_path: Path) -> Dict[str, Any]:
        """
        Get information about USD file without importing

        Args:
            usd_path: Path to USD file

        Returns:
            Dictionary of USD file information
        """
        info = {
            'file_path': str(usd_path),
            'file_size': 0,
            'mesh_count': 0,
            'skeleton_count': 0,
            'has_animation': False,
            'valid': False
        }

        if not USD_AVAILABLE:
            return info

        try:
            # File size
            info['file_size'] = usd_path.stat().st_size

            # Open stage
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                return info

            info['valid'] = True

            # Count meshes
            mesh_count = 0
            for prim in stage.Traverse():
                if prim.IsA(UsdGeom.Mesh):
                    mesh_count += 1
            info['mesh_count'] = mesh_count

            # Find skeletons
            skeletons = self.skeleton_reader.find_skeletons(stage)
            info['skeleton_count'] = len(skeletons)

            # Check for animation data
            info['has_animation'] = self._check_for_animation(stage, skeletons)

        except Exception as e:
            self.logger.error(f"Failed to get USD info: {e}")

        return info

    def _check_for_animation(self, stage, skeletons: list) -> bool:
        """
        Check if USD stage contains animation data.

        Looks for time samples on transforms, skeleton animation prims,
        and blend shape animation.

        Args:
            stage: The Usd.Stage
            skeletons: List of skeleton prims found in stage

        Returns:
            True if animation data is present
        """
        try:
            from pxr import UsdSkel, UsdGeom  # type: ignore

            # Check skeleton animation
            for skel_prim in skeletons:
                skel = UsdSkel.Skeleton(skel_prim)
                if self.skeleton_reader._check_skeleton_animation(skel):
                    return True

            # Check for time-sampled transforms on any prim
            for prim in stage.Traverse():
                if prim.IsA(UsdGeom.Xformable):
                    xformable = UsdGeom.Xformable(prim)
                    xform_ops = xformable.GetOrderedXformOps()
                    for op in xform_ops:
                        if op.GetNumTimeSamples() > 1:
                            return True

                # Check first 100 prims only (performance)
                if prim.GetPath().pathElementCount > 100:
                    break

            return False

        except Exception as e:
            self.logger.debug(f"Animation check failed: {e}")
            return False

    # ==================== Private Implementation ====================

    def _import_with_mayausd(
        self,
        usd_path: Path,
        options: UsdImportOptions,
        result: ImportResult
    ) -> Optional[str]:
        """
        Import USD file using mayaUSD plugin

        Args:
            usd_path: Path to USD file
            options: Import options
            result: Result object to populate

        Returns:
            Namespace used for import, or None if failed
        """
        self.logger.info(f"START: _import_with_mayausd CALLED with usd_path={usd_path}, namespace={options.namespace}")

        if not MAYA_AVAILABLE:
            self.logger.error("ERROR: MAYA_AVAILABLE is False!")
            return None

        try:
            # Ensure mayaUSD plugin is loaded
            if not cmds.pluginInfo('mayaUsdPlugin', query=True, loaded=True):
                self.logger.info("Loading mayaUSD plugin...")
                cmds.loadPlugin('mayaUsdPlugin')

            # Determine namespace
            namespace = options.namespace
            if not namespace:
                namespace = usd_path.stem  # Use filename as namespace

            result.created_namespaces.append(namespace)

            # Import USD file
            self.logger.info(f"Importing USD with mayaUSD: {usd_path.name}  namespace:{namespace}")

            # Check if RenderMan is the active renderer
            use_renderman = False
            try:
                current_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
                if current_renderer and "renderman" in current_renderer.lower():
                    use_renderman = True
                    self.logger.info("🎨 RenderMan is active renderer")
            except Exception:
                pass

            # Try using mayaUsdImport command directly (more reliable for materials)
            try:
                # mayaUsdImport has better material support
                self.logger.info("Using mayaUsdImport for better material support...")

                # Build import arguments
                # Note: shadingMode format is [["mode", "materialConversion"]]
                # For RenderMan: use 'pxrRis' mode
                # For standard: use 'useRegistry' with 'UsdPreviewSurface'
                import_args = {
                    'file': str(usd_path),
                    'readAnimData': True,
                    'useAsAnimationCache': False,
                    'importInstances': True,
                    'importUSDZTextures': True,  # Import textures from USDZ
                }

                # Set shading mode based on renderer
                if use_renderman:
                    # For RenderMan: try multiple approaches
                    import_args['shadingMode'] = [['pxrRis', 'default']]
                    self.logger.info("🎨 Using pxrRis shading mode for RenderMan materials")
                else:
                    import_args['shadingMode'] = [['useRegistry', 'UsdPreviewSurface']]
                    self.logger.info("Using useRegistry shading mode for standard materials")

                self.logger.info(f"mayaUSDImport args: {import_args}")
                imported_nodes = cmds.mayaUSDImport(**import_args)
                self.logger.info(f"mayaUSDImport returned {len(imported_nodes) if imported_nodes else 0} nodes")

            except Exception as e:
                self.logger.warning(f"mayaUsdImport failed ({e}), using cmds.file fallback")
                # Fallback: Use cmds.file with simpler options (no shadingMode to avoid parse errors)
                import_options = "readAnimData=1;"
                self.logger.info(f"Import options: {import_options}")

                imported_nodes = cmds.file(
                    str(usd_path),
                    i=True,
                    type="USD Import",
                    ignoreVersion=True,
                    mergeNamespacesOnClash=False,
                    namespace=namespace,
                    options=import_options,
                    returnNewNodes=True
                )

            if not imported_nodes:
                self.logger.error("No nodes imported from USD")
                return None

            self.logger.info(f"Imported {len(imported_nodes)} nodes")

            # Categorize imported nodes
            for node in imported_nodes:
                try:
                    if cmds.nodeType(node) == 'mesh':
                        # Get transform parent
                        parents = cmds.listRelatives(node, parent=True, fullPath=True)
                        if parents:
                            result.imported_meshes.append(parents[0])

                    elif cmds.nodeType(node) == 'joint':
                        result.imported_joints.append(node)

                    elif cmds.nodeType(node) == 'nurbsCurve':
                        parents = cmds.listRelatives(node, parent=True, fullPath=True)
                        if parents:
                            result.imported_curves.append(parents[0])
                except Exception:
                    pass  # Skip problematic nodes

            self.logger.info(
                f"Imported: {len(result.imported_meshes)} meshes, "
                f"{len(result.imported_joints)} joints, "
                f"{len(result.imported_curves)} curves"
            )

            # CRITICAL FIX: Detect actual namespace used by Maya
            # Maya may not use the namespace we requested, especially if there are clashes
            actual_namespace = namespace

            # Check what namespace Maya actually used by inspecting imported nodes
            if result.imported_joints:
                # Get first joint's namespace
                first_joint = result.imported_joints[0]
                # Extract namespace from full path (format: |namespace:object or namespace:object)
                if ':' in first_joint:
                    # Remove leading pipe if present
                    node_name = first_joint.lstrip('|')
                    # Split on first colon to get namespace
                    detected_ns = node_name.split(':')[0]
                    # Remove any path components
                    detected_ns = detected_ns.split('|')[-1]

                    if detected_ns != namespace:
                        self.logger.warning(
                            f"Namespace mismatch! Requested '{namespace}' "
                            f"but Maya used '{detected_ns}'"
                        )
                        actual_namespace = detected_ns
                        result.created_namespaces = [detected_ns]  # Update result
            elif result.imported_meshes:
                # Get first mesh's namespace
                first_mesh = result.imported_meshes[0]
                # Extract namespace from full path
                if ':' in first_mesh:
                    # Remove leading pipe if present
                    node_name = first_mesh.lstrip('|')
                    # Split on first colon to get namespace
                    detected_ns = node_name.split(':')[0]
                    # Remove any path components
                    detected_ns = detected_ns.split('|')[-1]

                    if detected_ns != namespace:
                        self.logger.warning(
                            f"Namespace mismatch! Requested '{namespace}' "
                            f"but Maya used '{detected_ns}'"
                        )
                        actual_namespace = detected_ns
                        result.created_namespaces = [detected_ns]  # Update result

            self.logger.info(f"Using namespace for skinning: {actual_namespace}")

            # CRITICAL FIX: Position joints in bind pose after MayaUSD import
            # MayaUSD may import joints in rest pose instead of bind pose
            self._position_joints_in_bind_pose(usd_path, actual_namespace, result)

            # Check for RenderMan materials
            self._verify_renderman_materials(result.imported_meshes)

            return actual_namespace

        except Exception as e:
            self.logger.error(f"mayaUSD import failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _verify_renderman_materials(self, imported_meshes: list) -> None:
        """
        Verify RenderMan materials were imported and log status

        Args:
            imported_meshes: List of imported mesh transform nodes
        """
        try:
            # Check if RenderMan is available
            renderman_available = False
            try:
                __import__('rfm2')
                renderman_available = True
            except ImportError:
                pass

            if not renderman_available:
                self.logger.info("RenderMan for Maya not detected - materials may display as lambert")
                return

            # Check materials assigned to meshes
            renderman_materials = []
            standard_materials = []

            for mesh in imported_meshes[:10]:  # Check first 10 meshes
                try:
                    # Get shading groups
                    shapes = cmds.listRelatives(mesh, shapes=True) or []
                    for shape in shapes:
                        sgs = cmds.listConnections(shape, type='shadingEngine') or []
                        for sg in sgs:
                            # Get material connected to shading group
                            mats = cmds.listConnections(f"{sg}.surfaceShader") or []
                            for mat in mats:
                                mat_type = cmds.nodeType(mat)
                                if mat_type.startswith('Pxr'):
                                    renderman_materials.append(mat)
                                else:
                                    standard_materials.append(mat)
                except Exception:
                    pass

            if renderman_materials:
                self.logger.info(
                    f"✅ RenderMan materials found: {len(set(renderman_materials))} "
                    f"(e.g., {renderman_materials[0]})"
                )
            elif standard_materials:
                self.logger.warning(
                    f"⚠️ Standard materials found instead of RenderMan: {len(set(standard_materials))}"
                )
                self.logger.info("   Tip: Set RenderMan as active renderer before import for full material support")
            else:
                self.logger.info("No materials detected on imported meshes")

        except Exception as e:
            self.logger.debug(f"Material verification error: {e}")

    def _apply_skin_weights_from_usd(
        self,
        usd_path: Path,
        namespace: str,
        options: UsdImportOptions,
        result: ImportResult
    ) -> None:
        """
        Read skin weights from USD and create Maya skinClusters

        Args:
            usd_path: Path to USD file
            namespace: Namespace used for import
            options: Import options
            result: Result object to populate
        """
        # AGGRESSIVE DEBUG: Prove function is called
        print("=" * 80)
        print(" _apply_skin_weights_from_usd() CALLED!")
        print(f" usd_path: {usd_path}")
        print(f" namespace: {namespace}")
        print(f" USD_AVAILABLE: {USD_AVAILABLE}")
        print(f" Usd module: {Usd}")
        print(f" UsdSkel module: {UsdSkel}")
        print("=" * 80)

        if not USD_AVAILABLE:
            print(" USD not available - returning early")
            self.logger.warning("USD not available - skipping skin weights")
            return

        try:
            print("SKELETON: Inside try block - about to log")
            print(f"SKELETON: Logger object: {self.logger}")
            print(f"SKELETON: Logger name: {self.logger.name}")
            print(f"SKELETON: Logger level: {self.logger.level}")
            print(f"SKELETON: Logger handlers: {self.logger.handlers}")
            self.logger.info("SKELETON: Applying skin weights from USD...")
            print("SKELETON: After logger.info call")

            # Open USD stage
            print(f"SKELETON: About to open USD stage: {usd_path}")
            stage = Usd.Stage.Open(str(usd_path))
            print(f"SKELETON: Stage opened: {stage}")
            if not stage:
                print("ERROR: Stage is None/False")
                self.logger.error("Could not open USD stage")
                return

            # Find skeletons
            skeletons = self.skeleton_reader.find_skeletons(stage)
            if not skeletons:
                self.logger.info("No skeletons found in USD - skipping skinning")
                return

            self.logger.info(f"Found {len(skeletons)} skeleton(s)")

            # Process each skeleton
            for skel_path in skeletons:
                self.logger.info(f"SKELETON: Processing skeleton: {skel_path}")
                self._process_skeleton(stage, skel_path, namespace, result)
                self.logger.info(
                    f"SKELETON: Finished skeleton {skel_path}, "
                    f"total skinClusters so far: {result.skin_clusters_created}"
                )

            self.logger.info(f"SUCCESS: Created {result.skin_clusters_created} skin clusters")

        except Exception as e:
            print("=" * 80)
            print(" EXCEPTION CAUGHT IN _apply_skin_weights_from_usd!")
            print(f" Exception type: {type(e).__name__}")
            print(f" Exception message: {e}")
            print("=" * 80)
            self.logger.error(f"Failed to apply skin weights: {e}")
            import traceback
            traceback.print_exc()
            result.add_warning(f"Skin weight application error: {e}")

    def _process_skeleton(
        self,
        stage: Any,
        skeleton_path: str,
        namespace: str,
        result: ImportResult
    ) -> None:
        """
        Process a single skeleton and its bound meshes

        Args:
            stage: USD Stage
            skeleton_path: Path to skeleton in USD
            namespace: Maya namespace
            result: Result object to populate
        """
        try:
            # Read skeleton data
            skeleton_data = self.skeleton_reader.read_skeleton(stage, skeleton_path)
            if not skeleton_data:
                self.logger.error(f"Could not read skeleton: {skeleton_path}")
                return

            joint_short_names = skeleton_data.get_joint_short_names()
            self.logger.info(f"Skeleton has {len(joint_short_names)} joints")

            # Find meshes bound to this skeleton
            skinned_meshes = self.skeleton_reader.find_skinned_meshes(stage, skeleton_path)
            if not skinned_meshes:
                self.logger.info(f"No skinned meshes found for skeleton: {skeleton_path}")
                return

            self.logger.info(f"Found {len(skinned_meshes)} skinned meshes")

            # Process each mesh
            for i, mesh_path in enumerate(skinned_meshes, 1):
                self.logger.info(f"HOUDINI: Processing mesh {i}/{len(skinned_meshes)}: {mesh_path}")
                self._create_skin_cluster_for_mesh(
                    stage,
                    mesh_path,
                    skeleton_data,
                    namespace,
                    result
                )

        except Exception as e:
            self.logger.error(f"Failed to process skeleton {skeleton_path}: {e}")

    def _create_skin_cluster_for_mesh(
        self,
        stage: Any,
        mesh_path: str,
        skeleton_data: UsdSkeletonData,
        namespace: str,
        result: ImportResult
    ) -> None:
        """
        Create skinCluster for a single mesh

        Args:
            stage: USD Stage
            mesh_path: Path to mesh in USD
            skeleton_data: Skeleton data
            namespace: Maya namespace
            result: Result object to populate
        """
        try:
            # Get mesh name from USD
            mesh_short_name = mesh_path.split('/')[-1]

            # Search for mesh transform in scene by short name
            # USD mesh paths point to transforms, not shapes
            all_transforms = cmds.ls(type='transform', long=True) or []
            maya_mesh_name = None

            for transform in all_transforms:
                # Check if short name matches (with or without namespace)
                transform_short = transform.split('|')[-1]  # Get short name from DAG path

                # Remove namespace prefix if present
                if ':' in transform_short:
                    name_without_ns = transform_short.split(':')[-1]
                else:
                    name_without_ns = transform_short

                # Match if the name (without namespace) equals mesh_short_name
                if name_without_ns == mesh_short_name:
                    # Verify it has a mesh shape child
                    shapes = cmds.listRelatives(transform, shapes=True, type='mesh')
                    if shapes:
                        maya_mesh_name = transform
                        self.logger.debug(f"Found mesh transform: {mesh_short_name} -> {maya_mesh_name}")
                        break

            if not maya_mesh_name:
                self.logger.warning(f"Mesh not found in Maya: {mesh_short_name}")
                return

            self.logger.info(f"Processing mesh: {maya_mesh_name}")

            # Read skin weights from USD
            weight_data = self.skeleton_reader.read_skin_weights(
                stage,
                mesh_path,
                skeleton_data
            )

            if not weight_data:
                self.logger.warning(f"No skin weights found for: {mesh_path}")
                return

            # Get joint names with namespace
            maya_joint_names = [f"{namespace}:{name}" for name in skeleton_data.get_joint_short_names()]

            # Create skinCluster
            skin_cluster = self.skin_builder.create_skin_cluster(
                maya_mesh_name,
                maya_joint_names,
                weight_data,
                skincluster_name=f"{namespace}:{mesh_short_name}_skinCluster"
            )

            if skin_cluster:
                result.created_skin_clusters.append(skin_cluster)
                result.skin_clusters_created += 1
                result.total_vertices += weight_data.vertex_count
                self.logger.info(f"SUCCESS: Created skinCluster: {skin_cluster}")
            else:
                self.logger.warning(f"Failed to create skinCluster for: {maya_mesh_name}")

        except Exception as e:
            self.logger.error(f"Failed to create skinCluster for {mesh_path}: {e}")
            import traceback
            traceback.print_exc()

    def _import_with_pure_python(
        self,
        usd_path: Path,
        options: UsdImportOptions,
        result: ImportResult
    ) -> Optional[str]:
        """
        Import USD using Pure Python method (no plugins)

        Args:
            usd_path: Path to USD file
            options: Import options
            result: Result object to populate

        Returns:
            Namespace or None if failed
        """
        self.logger.info("PYTHON: Attempting Pure Python USD import...")

        try:
            namespace = options.namespace or usd_path.stem

            # Use pure Python reader
            import_result = self.pure_python_reader.import_usd(usd_path, namespace)

            if import_result.get('success'):
                # Populate result object
                result.created_namespaces.append(namespace)

                for mesh_info in import_result.get('meshes', []):
                    result.imported_meshes.append(mesh_info['maya_mesh'])

                for joint in import_result.get('joints', []):
                    result.imported_joints.append(joint)

                self.logger.info(
                    f"Pure Python import: {len(result.imported_meshes)} meshes, "
                    f"{len(result.imported_joints)} joints"
                )
                return namespace

            return None

        except Exception as e:
            self.logger.error(f"Pure Python import failed: {e}")
            return None

    def _position_joints_in_bind_pose(
        self,
        usd_path: Path,
        namespace: str,
        result: ImportResult
    ) -> None:
        """
        Position imported joints in their bind pose from USD bindTransforms

        MayaUSD may import joints in rest pose instead of bind pose.
        This reads bindTransforms from USD and applies them to Maya joints.

        Args:
            usd_path: Path to USD file
            namespace: Namespace used for import
            result: Import result with joint list
        """
        if not USD_AVAILABLE or not result.imported_joints:
            return

        try:
            self.logger.info("🔧 Positioning joints in bind pose from USD...")

            # Open USD stage
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("Could not open USD stage for joint positioning")
                return

            # Find skeletons
            skeletons = self.skeleton_reader.find_skeletons(stage)
            if not skeletons:
                self.logger.info("No skeletons found for joint positioning")
                return

            joints_positioned = 0

            for skel_path in skeletons:
                try:
                    # Read skeleton data
                    skeleton_data = self.skeleton_reader.read_skeleton(stage, skel_path)
                    if not skeleton_data:
                        continue

                    # Get skeleton prim
                    skel_prim = stage.GetPrimAtPath(skel_path)
                    skeleton = UsdSkel.Skeleton(skel_prim)

                    # Read bind transforms
                    bind_transforms_attr = skeleton.GetBindTransformsAttr()
                    if not bind_transforms_attr:
                        self.logger.warning(f"No bind transforms for skeleton: {skel_path}")
                        continue

                    bind_transforms = bind_transforms_attr.Get()
                    if not bind_transforms:
                        self.logger.warning(f"Empty bind transforms for skeleton: {skel_path}")
                        continue

                    joint_names = skeleton_data.get_joint_short_names()

                    self.logger.info(f"Positioning {len(joint_names)} joints from {skel_path}")

                    # Position each joint
                    for idx, joint_short_name in enumerate(joint_names):
                        if idx >= len(bind_transforms):
                            continue

                        # Find Maya joint with namespace
                        maya_joint_name = f"{namespace}:{joint_short_name}"
                        if not cmds.objExists(maya_joint_name):
                            # Try without namespace
                            maya_joint_name = joint_short_name
                            if not cmds.objExists(maya_joint_name):
                                continue

                        # Convert USD matrix to Maya format
                        usd_matrix = bind_transforms[idx]
                        maya_matrix = [usd_matrix[i][j] for i in range(4) for j in range(4)]

                        # Apply transform in object space (local to parent)
                        cmds.xform(maya_joint_name, matrix=maya_matrix, objectSpace=True)
                        joints_positioned += 1

                except Exception as skel_error:
                    self.logger.warning(f"Failed to position joints for skeleton {skel_path}: {skel_error}")

            self.logger.info(f"✅ Positioned {joints_positioned} joints in bind pose")

        except Exception as e:
            self.logger.error(f"Failed to position joints in bind pose: {e}")

    def _import_with_usdview(
        self,
        usd_path: Path,
        options: UsdImportOptions,
        result: ImportResult
    ) -> Optional[str]:
        """
        Import USD via USD View tools format conversion

        Args:
            usd_path: Path to USD file
            options: Import options
            result: Result object to populate

        Returns:
            Namespace or None if failed
        """
        self.logger.info("USDVIEW: Attempting USD View conversion...")

        try:
            # First validate the USD file
            validation = self.usdview_bridge.validate_usd_file(usd_path)
            if not validation.get('valid'):
                self.logger.error(f"USD validation failed: {validation.get('errors')}")
                return None

            # Convert to ASCII USD for better compatibility
            usda_path = self.usdview_bridge.convert_format(usd_path, 'usda')
            if not usda_path:
                return None

            # Try importing the converted file with mayaUSD
            result_temp = ImportResult(success=False)
            namespace = self._import_with_mayausd(usda_path, options, result_temp)

            if namespace:
                # Copy results
                result.imported_meshes = result_temp.imported_meshes
                result.imported_joints = result_temp.imported_joints
                result.imported_curves = result_temp.imported_curves
                result.created_namespaces = result_temp.created_namespaces

                self.logger.info(f"USD View import: {len(result.imported_meshes)} meshes")
                return namespace

            return None

        except Exception as e:
            self.logger.error(f"USD View import failed: {e}")
            return None

    def _reconstruct_rig_connections(
        self,
        usd_path: Path,
        namespace: Optional[str],
        options: UsdImportOptions,
        result: ImportResult
    ) -> int:
        """Reconstruct rig connections for functional controllers - INDUSTRY FIRST!

        This makes imported NURBS curves actually work as rig controllers!

        Args:
            usd_path: Path to USD file
            namespace: Import namespace
            options: Import options
            result: Import result to update

        Returns:
            Number of connections restored
        """
        if not USD_AVAILABLE:
            self.logger.warning("USD not available - cannot reconstruct rig connections")
            return 0

        try:
            # Open USD stage to read connection metadata
            stage = Usd.Stage.Open(str(usd_path))
            if not stage:
                self.logger.warning("Could not open USD stage for connection reconstruction")
                return 0

            connections_restored = 0

            # Build namespace prefix
            ns_prefix = f"{namespace}:" if namespace else ""

            # Reconstruct direct connections
            connections_scope = stage.GetPrimAtPath("/root/rigConnections")
            if connections_scope and connections_scope.IsValid():

                # Find all connection prims
                for prim in stage.Traverse():
                    if prim.GetPath().GetParentPath() == "/root/rigConnections":
                        prim_name = prim.GetName()

                        if prim_name.startswith("connection_"):
                            # Reconstruct direct connection
                            if self._reconstruct_direct_connection(prim, ns_prefix):
                                connections_restored += 1

                        elif prim_name.startswith("constraint_"):
                            # Reconstruct constraint
                            if self._reconstruct_constraint(prim, ns_prefix):
                                connections_restored += 1

                        elif prim_name.startswith("setDrivenKey_"):
                            # Reconstruct set-driven key
                            if self._reconstruct_set_driven_key(prim, ns_prefix):
                                connections_restored += 1

            self.logger.info(f"Reconstructed {connections_restored} rig connections")
            return connections_restored

        except Exception as e:
            self.logger.error(f"Failed to reconstruct rig connections: {e}")
            return 0

    def _reconstruct_direct_connection(self, connection_prim: Any, ns_prefix: str) -> bool:
        """Reconstruct a direct attribute connection"""
        try:
            prim = connection_prim

            # Get connection metadata
            source_node = prim.GetAttribute("sourceNode").Get()
            target_node = prim.GetAttribute("targetNode").Get()
            source_attr = prim.GetAttribute("sourceAttr").Get()
            target_attr = prim.GetAttribute("targetAttr").Get()

            if not all([source_node, target_node, source_attr, target_attr]):
                return False

            # Apply namespace prefix
            source_node = f"{ns_prefix}{source_node}"
            target_node = f"{ns_prefix}{target_node}"

            # Check if nodes exist
            if not cmds.objExists(source_node) or not cmds.objExists(target_node):
                self.logger.debug(f"Connection nodes don't exist: {source_node} -> {target_node}")
                return False

            # Create the connection
            source_plug = f"{source_node}.{source_attr}"
            target_plug = f"{target_node}.{target_attr}"

            if cmds.isConnected(source_plug, target_plug):
                self.logger.debug(f"Connection already exists: {source_plug} -> {target_plug}")
                return True

            cmds.connectAttr(source_plug, target_plug, force=True)
            self.logger.debug(f"Reconstructed connection: {source_plug} -> {target_plug}")
            return True

        except Exception as e:
            self.logger.debug(f"Failed to reconstruct direct connection: {e}")
            return False

    def _reconstruct_constraint(self, constraint_prim: Any, ns_prefix: str) -> bool:
        """Reconstruct a Maya constraint"""
        try:
            prim = constraint_prim

            # Get constraint metadata
            constraint_type = prim.GetAttribute("constraintType").Get()
            target_node = prim.GetAttribute("targetNode").Get()
            target_attrs = prim.GetAttribute("targetAttrs").Get()
            driver_nodes = prim.GetAttribute("driverNodes").Get()
            maintain_offset = prim.GetAttribute("maintainOffset").Get()
            _ = prim.GetAttribute("interpolate").Get()

            if not all([constraint_type, target_node, target_attrs, driver_nodes]):
                return False

            # Apply namespace prefix
            target_node = f"{ns_prefix}{target_node}"
            driver_nodes = [f"{ns_prefix}{node}" for node in driver_nodes]

            # Check if nodes exist
            if not cmds.objExists(target_node) or not all(cmds.objExists(node) for node in driver_nodes):
                self.logger.debug(f"Constraint nodes don't exist: {driver_nodes} -> {target_node}")
                return False

            # Create the constraint
            constraint_func = getattr(cmds, constraint_type, None)
            if not constraint_func:
                self.logger.debug(f"Unknown constraint type: {constraint_type}")
                return False

            # Create constraint with appropriate arguments
            if constraint_type == "parentConstraint":
                _ = constraint_func(driver_nodes, target_node, maintainOffset=maintain_offset)[0]
            elif constraint_type == "pointConstraint":
                _ = constraint_func(driver_nodes, target_node, maintainOffset=maintain_offset)[0]
            elif constraint_type == "orientConstraint":
                _ = constraint_func(driver_nodes, target_node, maintainOffset=maintain_offset)[0]
            elif constraint_type == "scaleConstraint":
                _ = constraint_func(driver_nodes, target_node, maintainOffset=maintain_offset)[0]
            else:
                # Generic constraint creation
                _ = constraint_func(driver_nodes, target_node)[0]

            self.logger.debug(f"Reconstructed {constraint_type}: {driver_nodes} -> {target_node}")
            return True

        except Exception as e:
            self.logger.debug(f"Failed to reconstruct constraint: {e}")
            return False

    def _reconstruct_set_driven_key(self, sdk_prim: Any, ns_prefix: str) -> bool:
        """Reconstruct a set-driven key"""
        try:
            prim = sdk_prim

            # Get SDK metadata
            driver_node = prim.GetAttribute("driverNode").Get()
            driver_attr = prim.GetAttribute("driverAttr").Get()
            driven_node = prim.GetAttribute("drivenNode").Get()
            driven_attr = prim.GetAttribute("drivenAttr").Get()
            driver_values = prim.GetAttribute("driverValues").Get()
            driven_values = prim.GetAttribute("drivenValues").Get()

            if not all([driver_node, driver_attr, driven_node, driven_attr, driver_values, driven_values]):
                return False

            # Apply namespace prefix
            driver_node = f"{ns_prefix}{driver_node}"
            driven_node = f"{ns_prefix}{driven_node}"

            # Check if nodes exist
            if not cmds.objExists(driver_node) or not cmds.objExists(driven_node):
                self.logger.debug(f"SDK nodes don't exist: {driver_node}.{driver_attr} -> {driven_node}.{driven_attr}")
                return False

            # Create set-driven key
            cmds.setDrivenKeyframe(
                f"{driven_node}.{driven_attr}",
                currentDriver=f"{driver_node}.{driver_attr}"
            )

            # Set keyframe values
            for driver_val, driven_val in zip(driver_values, driven_values):
                cmds.setDrivenKeyframe(
                    f"{driven_node}.{driven_attr}",
                    currentDriver=f"{driver_node}.{driver_attr}",
                    driverValue=driver_val,
                    value=driven_val
                )

            self.logger.debug(f"Reconstructed SDK: {driver_node}.{driver_attr} -> {driven_node}.{driven_attr}")
            return True

        except Exception as e:
            self.logger.debug(f"Failed to reconstruct set-driven key: {e}")
            return False


# Singleton instance
_usd_import_service: Optional[UsdImportServiceImpl] = None


def get_usd_import_service():
    """Get singleton USD import service instance"""
    global _usd_import_service
    if _usd_import_service is None:
        _usd_import_service = UsdImportServiceImpl()
    return _usd_import_service
