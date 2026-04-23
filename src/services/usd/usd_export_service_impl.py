"""USD Export Service Implementation

Clean Code: Orchestrates Maya → USD export pipeline
Disney/Pixar Critical: Main entry point for USD conversion workflow
"""

from pathlib import Path
from typing import Optional, List, Any, Tuple, TYPE_CHECKING
import logging
import time
import threading
import maya.cmds as cmds  # type: ignore

if TYPE_CHECKING:
    from ..usd_service_impl import UsdService
else:
    UsdService = Any  # Runtime fallback for type hints

# Import interfaces
from ...core.interfaces.usd_export_service import IUSDExportService, USDExportOptions
from ...core.interfaces.maya_scene_parser import IMayaSceneParser, MayaSceneData, JointData
from ...core.interfaces.usd_material_converter import IUSDMaterialConverter
from .usd_material_converter_impl import USDMaterialConverterImpl
from ...core.interfaces.usd_rig_converter import IUSDRigConverter

# Conditional USD import
try:
    from pxr import Usd, UsdGeom, Sdf, UsdShade, Gf, UsdUtils, Vt  # type: ignore

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    Usd: Any = None  # type: ignore
    UsdGeom: Any = None  # type: ignore
    Sdf: Any = None  # type: ignore
    UsdShade: Any = None  # type: ignore
    Gf: Any = None  # type: ignore
    UsdUtils: Any = None  # type: ignore
    Vt: Any = None  # type: ignore


class ExportResult:
    def __init__(
        self,
        success,
        output_file,
        mesh_count,
        joint_count,
        skin_cluster_count,
        curve_count,
        warnings,
        error_message,
    ):
        self.success = success
        self.output_file = output_file
        self.mesh_count = mesh_count
        self.joint_count = joint_count
        self.skin_cluster_count = skin_cluster_count
        self.curve_count = curve_count
        self.warnings = warnings
        self.error_message = error_message


class USDExportServiceImpl(IUSDExportService):
    """USD Export Service - Main orchestrator for Maya → USD pipeline

    Clean Code: Single Responsibility - Orchestrate export workflow
    SOLID: Dependency Inversion - Depends on abstractions (interfaces)
    Disney/Pixar Critical: Production-ready USD export for animation pipelines
    """

    @staticmethod
    def _sanitize_mesh_name(maya_name: str) -> str:
        """Sanitize Maya mesh name for USD path compliance

        Clean Code: DRY - Single source of truth for name sanitization

        Args:
            maya_name: Original Maya DAG path (e.g., |model:Veteran_Geo_Grp|model:Body_Geo)

        Returns:
            USD-compliant name (e.g., model_Veteran_Geo_Grp_model_Body_Geo)
        """
        # Remove leading pipes and replace all invalid characters
        sanitized = maya_name.lstrip("|").replace(":", "_").replace("|", "_")
        return sanitized

    def __init__(
        self,
        scene_parser: IMayaSceneParser,
        material_converter: Optional[IUSDMaterialConverter] = None,
        rig_converter: Optional[IUSDRigConverter] = None,
        usd_service: Optional[UsdService] = None,
    ):
        """Initialize USD export service with dependencies

        Clean Code: Dependency Injection for testability

        Args:
            scene_parser: Maya scene parser implementation
            material_converter: Optional material converter
            rig_converter: Optional rig converter
            usd_service: Optional USD service for plugin availability checks
        """
        self.logger = logging.getLogger(__name__)
        self.scene_parser = scene_parser
        self.material_converter = material_converter or USDMaterialConverterImpl()
        self.rig_converter = rig_converter
        self.usd_service = usd_service

        # Export state
        self._is_exporting = False
        self._cancel_requested = False
        self._current_progress = 0.0
        self._current_stage = ""
        self._last_error = ""
        self._progress_lock = threading.Lock()  # Thread-safe progress updates

        if not USD_AVAILABLE:
            self.logger.warning("USD Python libraries not available - export will fail")

    def export_maya_scene(self, maya_file: Optional[Path], options: USDExportOptions) -> bool:
        """Export complete Maya scene to USD

        Clean Code: Main orchestration method
        Disney/Pixar Critical: Complete pipeline execution

        Args:
            maya_file: Path to Maya source file, or None to use current scene
            options: Export configuration

        Returns:
            True if export succeeded
        """
        if not USD_AVAILABLE:
            self._last_error = "USD Python libraries not available"
            self.logger.error(self._last_error)
            return False

        if self._is_exporting:
            self._last_error = "Export already in progress"
            self.logger.error(self._last_error)
            return False

        # Get output path from options
        if not options.output_path:
            self._last_error = "No output path specified in options"
            self.logger.error(self._last_error)
            return False

        output_path = Path(options.output_path)

        try:
            self._is_exporting = True
            self._cancel_requested = False
            self._last_error = ""
            self._current_progress = 0.0

            # Determine source
            if maya_file:
                source_desc = str(maya_file)
                self.logger.info(f"Starting USD export: {maya_file} → {output_path}")
            else:
                source_desc = "current Maya scene"
                self.logger.info(f"Starting USD export from current scene → {output_path}")

            start_time = time.time()

            # Phase 0: Pre-export cleanup (blendshapes, duplicates) - NEW!
            self._update_progress(0.0, "Cleaning up blendshapes and duplicates...")
            cleanup_count = self._pre_export_cleanup()
            self.logger.info(f"[NEW] Pre-export cleanup: {cleanup_count} objects hidden")

            # Phase 1: Parse Maya scene (20%)
            self._update_progress(0.0, f"Parsing {source_desc}...")
            scene_data = self.scene_parser.parse_maya_file(maya_file, options=None)  # type: ignore
            if self._check_cancel():
                return False

            self.logger.info(
                f"🔍 SCENE PARSED: {len(scene_data.meshes)} meshes, "
                f"{len(scene_data.materials)} materials, "
                f"{len(scene_data.nurbs_curves)} NURBS curves, "
                f"{len(scene_data.joints)} joints"
            )
            self._update_progress(
                0.2,
                f"Parsed {len(scene_data.meshes)} meshes, "
                f"{len(scene_data.materials)} materials, "
                f"{len(scene_data.nurbs_curves)} curves",
            )

            # Phase 2: Create USD stage (10%)
            self._update_progress(0.2, "Creating USD stage...")
            stage = self._create_stage(output_path, options)
            if not stage:
                self._last_error = "Failed to create USD stage"
                return False
            if self._check_cancel():
                return False

            self._update_progress(0.3, "USD stage created")

            # Phase 3: Export geometry (30%)
            self.logger.info(
                f"[DEBUG] Checking geometry export: export_meshes={options.export_meshes}, "
                f"mesh_count={len(scene_data.meshes)}"
            )
            if options.export_meshes:
                self.logger.info(
                    f"[DEBUG] Starting geometry export for {len(scene_data.meshes)} meshes"
                )
                self._update_progress(0.3, "Exporting geometry...")
                if not self._export_geometry(stage, scene_data, options):
                    self._last_error = "Failed to export geometry"
                    return False
                if self._check_cancel():
                    return False
            else:
                self.logger.warning("[DEBUG] GEOMETRY EXPORT SKIPPED - export_meshes is FALSE!")

            self._update_progress(0.6, f"Exported {len(scene_data.meshes)} meshes")

            # Phase 4: Export materials (20%)
            if options.export_materials and self.material_converter:
                self._update_progress(0.6, "Exporting materials...")
                if not self._export_materials(stage, scene_data, options):
                    self._last_error = "Failed to export materials"
                    return False
                if self._check_cancel():
                    return False

            self._update_progress(0.8, f"Exported {len(scene_data.materials)} materials")

            # Phase 5: Export NURBS curves (rig controls) - INDUSTRY FIRST! (5%)
            self.logger.info(
                f"[TARGET] NURBS EXPORT CHECK: options.export_nurbs_curves={options.export_nurbs_curves}, "
                f"scene_data.nurbs_curves count={len(scene_data.nurbs_curves)}"
            )
            if options.export_nurbs_curves and scene_data.nurbs_curves:
                self.logger.info(
                    f"[TARGET] STARTING NURBS EXPORT: {len(scene_data.nurbs_curves)} curves found"
                )
                self._update_progress(0.8, "Exporting NURBS curves (rig controls)...")
                if not self._export_nurbs_curves(stage, scene_data, options):
                    self._last_error = "Failed to export NURBS curves"
                    return False
                if self._check_cancel():
                    return False
                self.logger.info(
                    f"[NEW] Exported {len(scene_data.nurbs_curves)} NURBS curves (rig controls)"
                )
            else:
                self.logger.warning(
                    f"[TARGET] NURBS EXPORT SKIPPED: export_nurbs_curves="
                    f"{options.export_nurbs_curves}, curves found={len(scene_data.nurbs_curves)}"
                )

            self._update_progress(0.85, "NURBS curves exported")

            # Phase 6: Export rig connections (functional controllers) - INDUSTRY FIRST! (5%)
            has_rig_data = (
                scene_data.rig_connections or scene_data.constraints or scene_data.set_driven_keys
            )
            if (
                options.export_nurbs_curves
                and options.export_rig_connections
                and scene_data.nurbs_curves
                and has_rig_data
            ):
                self._update_progress(
                    0.85, "Exporting rig connections (functional controllers)..."
                )
                if not self._export_rig_connections(stage, scene_data, options):
                    self._last_error = "Failed to export rig connections"
                    return False
                if self._check_cancel():
                    return False
                self.logger.info(
                    f"[NEW] Exported rig connections: {len(scene_data.rig_connections)} "
                    f"connections, {len(scene_data.constraints)} constraints, "
                    f"{len(scene_data.set_driven_keys)} SDKs"
                )

            self._update_progress(0.9, "Rig connections exported")

            # Phase 7: Export rigging (5%)
            # Only export skin weights if NOT using viewport_friendly_skeleton
            # viewport_friendly = skeleton only (fast viewport), no skin bindings
            if options.export_skeleton and self.rig_converter:
                if options.viewport_friendly_skeleton:
                    self.logger.info(
                        "[HYBRID] Viewport-friendly mode: Skipping skin weight export "
                        "(skeleton hierarchy only)"
                    )
                else:
                    self._update_progress(0.9, "Exporting rigging with skin weights...")
                    if not self._export_rigging(stage, scene_data, options):
                        self._last_error = "Failed to export rigging"
                        return False
                    if self._check_cancel():
                        return False

            self._update_progress(0.95, "Rigging exported")

            # Phase 7: Save USD file (10%)
            self._update_progress(0.9, f"Saving {options.file_format.upper()} file...")
            stage.GetRootLayer().Save()

            elapsed = time.time() - start_time
            self._update_progress(1.0, f"Export complete in {elapsed:.2f}s")

            self.logger.info(f"USD export successful: {output_path}")
            return True

        except Exception as e:
            self._last_error = f"Export failed: {str(e)}"
            self.logger.error(self._last_error, exc_info=True)
            return False

        finally:
            self._is_exporting = False

    def _pre_export_cleanup(self) -> int:
        """
        Pre-export cleanup: Hide blendshape targets and duplicate meshes.

        This runs before scene parsing to ensure clean USD export.

        Returns:
            Number of objects hidden
        """
        try:
            # Import and run blendshape cleanup
            import sys
            import os

            # Get plugin directory
            plugin_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            scripts_dir = os.path.join(plugin_dir, "scripts")
            script_path = os.path.join(scripts_dir, "HIDE_BLENDSHAPE_TARGETS.py")

            self.logger.info(f"[TOOL] PRE-EXPORT CLEANUP: plugin_dir = {plugin_dir}")
            self.logger.info(f"[TOOL] PRE-EXPORT CLEANUP: scripts_dir = {scripts_dir}")
            self.logger.info(f"[TOOL] PRE-EXPORT CLEANUP: script_path = {script_path}")
            self.logger.info(
                f"[TOOL] PRE-EXPORT CLEANUP: script_path exists = {os.path.exists(script_path)}"
            )
            is_file = os.path.isfile(script_path) if os.path.exists(script_path) else "N/A"
            self.logger.info(f"[TOOL] PRE-EXPORT CLEANUP: script_path is_file = {is_file}")

            # Check if we're in development (workspace) vs installed
            # If the script doesn't exist at the calculated path, try to find workspace
            if not os.path.exists(script_path):
                msg = f"PRE-EXPORT CLEANUP: Script not found at {script_path}, looking for workspace..."
                self.logger.info(f"[TOOL] {msg}")
                # Look for workspace by checking parent directories for the script
                current_dir = plugin_dir
                for i in range(5):  # Check up to 5 levels up
                    current_dir = os.path.dirname(current_dir)
                    workspace_script = os.path.join(
                        current_dir, "scripts", "HIDE_BLENDSHAPE_TARGETS.py"
                    )
                    exists = os.path.exists(workspace_script)
                    self.logger.info(
                        f"[TOOL] PRE-EXPORT CLEANUP: Checking level {i+1}: "
                        f"{workspace_script} (exists: {exists})"
                    )
                    if os.path.exists(workspace_script):
                        scripts_dir = os.path.join(current_dir, "scripts")
                        script_path = workspace_script
                        self.logger.info(
                            f"[TOOL] PRE-EXPORT CLEANUP: Found workspace script at {script_path}"
                        )
                        break
                else:
                    self.logger.warning(
                        f"[TOOL] PRE-EXPORT CLEANUP: Could not find "
                        f"HIDE_BLENDSHAPE_TARGETS.py, tried 5 levels up from {plugin_dir}"
                    )
                    return 0

            # Add scripts directory to path temporarily
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)

            try:
                self.logger.info(f"[TOOL] PRE-EXPORT CLEANUP: Loading script from {scripts_dir}")

                # Execute the cleanup script directly (avoids import issues with paths containing spaces)
                with open(script_path, "r", encoding="utf-8") as f:
                    script_code = f.read()

                # Execute in a controlled namespace (exec is safe here — script_path is
                # a known internal path, not user-provided input)
                cleanup_namespace = {}
                exec(script_code, cleanup_namespace)  # pylint: disable=exec-used  # nosec B102

                self.logger.info(
                    "[TOOL] PRE-EXPORT CLEANUP: Successfully loaded HIDE_BLENDSHAPE_TARGETS"
                )

                # Run cleanup for export
                self.logger.info(
                    "[TOOL] PRE-EXPORT CLEANUP: Calling cleanup_blendshapes_for_export()"
                )
                bs_count, dup_count = cleanup_namespace["cleanup_blendshapes_for_export"]()
                self.logger.info(
                    f"[TOOL] PRE-EXPORT CLEANUP: cleanup_blendshapes_for_export() "
                    f"returned bs_count={bs_count}, dup_count={dup_count}"
                )

                total_hidden = bs_count + dup_count
                self.logger.info(
                    f"[OK] Pre-export cleanup complete: {bs_count} blendshapes, "
                    f"{dup_count} duplicates hidden (total: {total_hidden})"
                )

                return total_hidden

            except Exception as e:
                self.logger.error(f"[ERROR] Could not load blendshape cleanup script: {e}")
                return 0
            finally:
                # Clean up path
                if scripts_dir in sys.path:
                    sys.path.remove(scripts_dir)

        except Exception as e:
            self.logger.error(f"[ERROR] Error during pre-export cleanup: {e}")
            return 0

    def export_selected_objects(
        self, options: USDExportOptions, object_names: Optional[List[str]] = None
    ) -> bool:
        """Export selected Maya objects to USD (requires Maya session)

        Clean Code: Partial export workflow
        Use Case: Export specific assets from active scene

        Args:
            options: Export configuration
            object_names: Specific object names, or None for current selection

        Returns:
            True if export succeeded
        """
        if not USD_AVAILABLE:
            self._last_error = "USD Python libraries not available"
            self.logger.error(self._last_error)
            return False

        # Get output path from options
        if not options.output_path:
            self._last_error = "No output path specified in options"
            self.logger.error(self._last_error)
            return False

        output_path = Path(options.output_path)

        try:
            self._is_exporting = True
            self._cancel_requested = False
            self._last_error = ""

            self.logger.info(f"Exporting selected objects to: {output_path}")

            # Parse selected objects
            self._update_progress(0.0, "Parsing selected objects...")
            scene_data = self.scene_parser.parse_selected_objects()

            if not scene_data or not scene_data.meshes:
                self._last_error = "No valid objects selected"
                return False

            self._update_progress(0.3, f"Parsed {len(scene_data.meshes)} selected meshes")

            # Create stage and export
            stage = self._create_stage(output_path, options)
            if not stage:
                self._last_error = "Failed to create USD stage"
                return False

            # Export geometry
            if not self._export_geometry(stage, scene_data, options):
                self._last_error = "Failed to export geometry"
                return False

            self._update_progress(0.8, "Exporting materials...")

            # Export materials if available
            if options.export_materials and self.material_converter:
                self._export_materials(stage, scene_data, options)

            # Save
            self._update_progress(0.9, "Saving USD file...")
            stage.GetRootLayer().Save()

            self._update_progress(1.0, "Export complete")
            self.logger.info(f"Selected objects exported: {output_path}")
            return True

        except Exception as e:
            self._last_error = f"Export failed: {str(e)}"
            self.logger.error(self._last_error, exc_info=True)
            return False

        finally:
            self._is_exporting = False

    def validate_export_options(self, options: USDExportOptions) -> Tuple[bool, str]:
        """Validate export options before starting

        Clean Code: Fail fast with validation

        Args:
            options: Export configuration to validate

        Returns:
            (is_valid, error_message) - Empty string if valid
        """
        # Check file format
        if options.file_format not in ["usda", "usdc", "usdz"]:
            return (
                False,
                f"Invalid file format: {options.file_format}. Must be usda, usdc, or usdz",
            )

        # Check output directory exists
        if options.output_path:
            output_dir = Path(options.output_path).parent
            if not output_dir.exists():
                return (False, f"Output directory does not exist: {output_dir}")

        # Check material export requirements
        if options.export_materials and not self.material_converter:
            self.logger.warning("Material export requested but no converter available")

        # Check rigging export requirements
        if options.export_skeleton and not self.rig_converter:
            self.logger.warning("Rigging export requested but no converter available")

        # Check animation export requirements
        if options.export_animation and not options.export_skeleton:
            return (False, "Animation export requires skeleton export to be enabled")

        return (True, "")

    def get_supported_formats(self) -> List[str]:
        """Get list of supported USD formats

        Returns:
            List of format extensions
        """
        return ["usda", "usdc", "usdz"]

    def estimate_export_time(self, maya_file: Path, options: USDExportOptions) -> float:
        """Estimate export time in seconds

        Clean Code: Progress estimation for UX

        Args:
            maya_file: Maya source file
            options: Export configuration

        Returns:
            Estimated time in seconds
        """
        try:
            # Quick file size estimate
            file_size_mb = maya_file.stat().st_size / (1024 * 1024)

            # Base estimate: ~1 second per MB
            base_time = file_size_mb * 1.0

            # Adjust for options
            if options.export_materials:
                base_time *= 1.2

            if options.export_skeleton:
                base_time *= 1.3

            if options.export_animation:
                base_time *= 1.5

            return max(1.0, base_time)

        except Exception as e:
            self.logger.warning(f"Failed to estimate export time: {e}")
            return 10.0  # Default estimate

    def cancel_export(self) -> None:
        """Cancel ongoing export operation

        Clean Code: User control over long operations
        """
        if not self._is_exporting:
            return

        self._cancel_requested = True
        self.logger.info("Export cancellation requested")

    def get_export_progress(self) -> Tuple[int, str]:
        """Get current export progress

        Returns:
            (percentage_complete, current_stage_description)

        Clean Code: Real-time feedback for UI
        Thread-Safe: Uses lock to prevent race conditions
        """
        with self._progress_lock:
            percentage = int(self._current_progress * 100)
            return (percentage, self._current_stage)

    def get_last_error(self) -> Optional[str]:
        """Get last error message

        Returns:
            Error message or None if no error
        """
        return self._last_error if self._last_error else None

    # ==================== PRIVATE HELPER METHODS ====================

    def _create_stage(self, output_path: Path, options: USDExportOptions) -> Any:
        """Create USD stage with proper configuration

        Clean Code: Stage initialization
        Disney/Pixar Critical: Proper stage setup for pipeline compatibility

        Args:
            output_path: Output file path
            options: Export options

        Returns:
            USD stage or None on failure
        """
        try:
            # Clean Code: Force fresh USD stage - delete file FIRST
            # Then create stage fresh (USD won't cache deleted files)

            # CRITICAL: For USDZ format, we cannot create a stage directly with .usdz extension
            # The USD API doesn't support creating package layers via CreateNew()
            # Instead, create as .usdc (binary) and let the dialog package it into .usdz later
            actual_output_path = output_path
            if options.file_format == "usdz":
                # Change extension to .usdc for stage creation
                # The dialog will package this into .usdz with .mrig bundled
                actual_output_path = output_path.with_suffix(".usdc")
                self.logger.info(
                    f"USDZ format requested - creating intermediate .usdc: {actual_output_path}"
                )

            # Critical: Delete file before USD touches it
            if actual_output_path.exists():
                try:
                    actual_output_path.unlink()
                    self.logger.debug(f"Deleted existing file: {actual_output_path}")
                except Exception as e:
                    self.logger.warning(f"Could not delete existing file: {e}")

            # Also clean up the original path if different
            if output_path != actual_output_path and output_path.exists():
                try:
                    output_path.unlink()
                    self.logger.debug(f"Deleted existing target file: {output_path}")
                except Exception as e:
                    self.logger.warning(f"Could not delete existing target file: {e}")

            # Clear stage cache for good measure
            try:
                UsdUtils.StageCache.Get().Clear()
            except Exception:
                pass

            # Determine file format and create stage
            if options.file_format == "usda":
                # ASCII format for readability
                stage = Usd.Stage.CreateNew(str(actual_output_path))
            elif options.file_format == "usdc":
                # Binary format for performance
                stage = Usd.Stage.CreateNew(str(actual_output_path))
            elif options.file_format == "usdz":
                # Package format - create as .usdc first, will be packaged later
                stage = Usd.Stage.CreateNew(str(actual_output_path))
            else:
                self.logger.error(f"Unsupported format: {options.file_format}")
                return None

            # Set stage metadata
            stage.SetMetadata("comment", "Exported from Maya Asset Manager")

            # Set up axis (Maya uses Y-up)
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

            # Set meters per unit (Maya default is cm)
            UsdGeom.SetStageMetersPerUnit(stage, 0.01)

            # Set default prim for easier referencing
            default_prim = UsdGeom.Xform.Define(stage, "/root")
            stage.SetDefaultPrim(default_prim.GetPrim())

            self.logger.info(f"Created USD stage: {actual_output_path}")
            return stage

        except Exception as e:
            self.logger.error(f"Failed to create USD stage: {e}")
            return None

    def _export_geometry(
        self, stage: Any, scene_data: MayaSceneData, options: USDExportOptions
    ) -> bool:
        """Export mesh geometry to USD stage

        Clean Code: Geometry conversion
        Disney/Pixar Critical: Accurate mesh data preservation

        Args:
            stage: USD stage
            scene_data: Parsed Maya scene data
            options: Export options

        Returns:
            True if successful
        """
        # CRITICAL DEBUG: Entry point
        self.logger.info(f"[DEBUG] _export_geometry CALLED with {len(scene_data.meshes)} meshes")
        self.logger.info(f"[DEBUG] export_meshes option: {options.export_meshes}")

        try:
            self.logger.info(f"[DEBUG] Starting mesh loop for {len(scene_data.meshes)} meshes")
            mesh_count = 0
            for mesh_data in scene_data.meshes:
                mesh_count += 1
                self.logger.debug(
                    f"[DEBUG] Processing mesh {mesh_count}/{len(scene_data.meshes)}: {mesh_data.name}"
                )
                if self._check_cancel():
                    return False

                # Clean Code: Use centralized sanitization for consistency
                sanitized_name = self._sanitize_mesh_name(mesh_data.name)

                if sanitized_name != mesh_data.name:
                    self.logger.debug(f"Sanitized mesh name: {mesh_data.name} -> {sanitized_name}")

                # Create mesh prim path
                mesh_path = f"/root/meshes/{sanitized_name}"
                self.logger.debug(f"Creating mesh prim at: {mesh_path}")

                # Define mesh
                mesh = UsdGeom.Mesh.Define(stage, mesh_path)

                # Set vertices
                mesh.GetPointsAttr().Set(mesh_data.vertices)

                # Set face topology
                mesh.GetFaceVertexCountsAttr().Set(mesh_data.face_vertex_counts)
                mesh.GetFaceVertexIndicesAttr().Set(mesh_data.face_vertex_indices)

                # Set normals if available
                if mesh_data.normals:
                    mesh.GetNormalsAttr().Set(mesh_data.normals)
                    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

                # Set UVs if available
                if mesh_data.uvs:
                    primvar_api = UsdGeom.PrimvarsAPI(mesh)
                    uv_primvar = primvar_api.CreatePrimvar(
                        "st", Sdf.ValueTypeNames.TexCoord2fArray
                    )
                    uv_primvar.Set(mesh_data.uvs)
                    if mesh_data.uv_indices:
                        uv_primvar.SetIndices(mesh_data.uv_indices)

                # Set vertex colors if available
                if mesh_data.vertex_colors:
                    primvar_api = UsdGeom.PrimvarsAPI(mesh)
                    color_primvar = primvar_api.CreatePrimvar(
                        "displayColor", Sdf.ValueTypeNames.Color3fArray
                    )
                    color_primvar.Set(mesh_data.vertex_colors)

                # Set transform
                if mesh_data.world_matrix:
                    xform = UsdGeom.Xformable(mesh)
                    # Convert 16-element list to 4x4 matrix
                    matrix = mesh_data.world_matrix
                    # USD expects row-major 4x4 matrix
                    mat = Gf.Matrix4d(
                        matrix[0],
                        matrix[1],
                        matrix[2],
                        matrix[3],
                        matrix[4],
                        matrix[5],
                        matrix[6],
                        matrix[7],
                        matrix[8],
                        matrix[9],
                        matrix[10],
                        matrix[11],
                        matrix[12],
                        matrix[13],
                        matrix[14],
                        matrix[15],
                    )

                    # Defensive: avoid adding duplicate xformOp 'xformOp:transform'
                    try:
                        existing_ops = xform.GetOrderedXformOps()
                        transform_set = False
                        for op in existing_ops:
                            try:
                                # XformOp has GetName(); compare to the default transform op name
                                if op.GetName() == "xformOp:transform":
                                    op.Set(mat)
                                    transform_set = True
                                    break
                            except Exception:
                                # If any op interrogation fails, continue to next
                                continue

                        if not transform_set:
                            xform_op = xform.AddTransformOp()
                            xform_op.Set(mat)
                    except Exception as e:
                        # Fallback: try adding transform op (best-effort)
                        self.logger.debug(f"Transform fallback for {mesh_data.name}: {e}")
                        try:
                            xform_op = xform.AddTransformOp()
                            xform_op.Set(mat)
                        except Exception:
                            pass

                # Bind materials if available
                if mesh_data.material_assignments and options.export_materials:
                    self._bind_materials_to_mesh(stage, mesh, mesh_data)

                self.logger.debug(f"Exported mesh: {mesh_data.name}")

            # Diagnostic: List all mesh prims that were actually created
            meshes_prim = stage.GetPrimAtPath("/root/meshes")
            if meshes_prim.IsValid():
                mesh_children = meshes_prim.GetChildren()
                mesh_names = [child.GetName() for child in mesh_children]
                suffix = "..." if len(mesh_names) > 10 else ""
                self.logger.info(
                    f"[DEBUG] Created {len(mesh_names)} mesh prims: {mesh_names[:10]}{suffix}"
                )
            else:
                self.logger.error("[DEBUG] /root/meshes prim is NOT VALID after mesh export!")

            self.logger.info(
                f"[DEBUG] _export_geometry RETURNING TRUE - processed {mesh_count} meshes"
            )
            return True

        except Exception as e:
            self.logger.error(f"[DEBUG] EXCEPTION in _export_geometry: {e}", exc_info=True)
            return False

    def _export_materials(
        self, stage: Any, scene_data: MayaSceneData, options: USDExportOptions
    ) -> bool:
        """Export materials to USD stage

        Clean Code: Material delegation
        Disney/Pixar Critical: RenderMan material preservation

        Args:
            stage: USD stage
            scene_data: Parsed Maya scene data
            options: Export options

        Returns:
            True if successful
        """
        if not options.export_materials:
            self.logger.info("Material export disabled")
            return True

        try:
            # Create /Materials scope
            UsdGeom.Scope.Define(stage, "/Materials")

            for material_data in scene_data.materials:
                if self._check_cancel():
                    return False

                # Use material converter to create USD material
                material_name = self._sanitize_mesh_name(material_data.name)

                if material_data.is_renderman:
                    # RenderMan materials use native USD RenderMan shaders (ri:PxrSurface etc.)
                    # Both RenderMan and USD are Pixar - they work together natively!
                    usd_material = self.material_converter.convert_renderman_material(
                        material_name,
                        material_data.renderman_params or {},
                        stage,
                        None,  # usd_service not needed for native RenderMan-USD
                    )
                    if usd_material:
                        self.logger.info(f"[OK] Exported RenderMan material: {material_name}")
                    else:
                        self.logger.warning(
                            f"[WARNING] Failed to export RenderMan material: {material_name}"
                        )
                else:
                    # Convert standard material to Preview Surface
                    usd_material = self.material_converter.convert_to_preview_surface(
                        material_name,
                        {
                            "diffuse_color": material_data.diffuse_color,
                            "metallic": material_data.metallic,
                            "roughness": material_data.roughness,
                        },
                        stage,
                    )

                if not usd_material:
                    self.logger.warning(f"Failed to convert material: {material_data.name}")

                mat_type = "RenderMan" if material_data.is_renderman else "Standard"
                self.logger.debug(f"Exported material: {material_data.name} ({mat_type})")

            self.logger.info(f"Exported {len(scene_data.materials)} materials")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export materials: {e}")
            return False

    def _bind_materials_to_mesh(self, stage: Any, mesh: Any, mesh_data: Any) -> None:
        """Bind materials to mesh geometry

        Args:
            stage: USD stage
            mesh: UsdGeom.Mesh prim
            mesh_data: MeshData with material assignments
        """
        try:
            # Get mesh prim for binding API
            mesh_prim = mesh.GetPrim()

            # Bind each material
            for material_name in mesh_data.material_assignments.keys():
                # Find material prim
                mat_path = f"/Materials/{self._sanitize_mesh_name(material_name)}"
                material_prim = stage.GetPrimAtPath(mat_path)

                if not material_prim or not material_prim.IsValid():
                    self.logger.debug(f"Material not found for binding: {material_name}")
                    continue

                # Create UsdShade.Material and bind to mesh
                material = UsdShade.Material(material_prim)
                binding_api = UsdShade.MaterialBindingAPI(mesh_prim)
                binding_api.Bind(material)

                self.logger.debug(f"Bound material {material_name} to {mesh_data.name}")

                # Note: Per-face material assignments would require geomSubsets
                # For now, using single material per mesh (first assigned material wins)
                break

        except Exception as e:
            self.logger.debug(f"Failed to bind materials to {mesh_data.name}: {e}")

    def _export_nurbs_curves(
        self, stage: Any, scene_data: MayaSceneData, options: USDExportOptions
    ) -> bool:
        """Export NURBS curves (rig controls) to USD - INDUSTRY FIRST!

        This enables complete character rigs with control curves in USD.
        Most pipelines skip rig controls - this is groundbreaking!

        Args:
            stage: USD stage
            scene_data: Parsed Maya scene data
            options: Export options

        Returns:
            True if successful
        """
        if not scene_data.nurbs_curves:
            self.logger.info("No NURBS curves to export")
            return True

        try:
            self.logger.info(
                f"[NEW] Exporting {len(scene_data.nurbs_curves)} NURBS curves (rig controls)"
            )

            # Create a scope for curves (fallback for non-skeleton curves)
            UsdGeom.Scope.Define(stage, "/root/curves")

            # Build joint path mapping for parenting curves to skeleton
            joint_path_map = {}
            if scene_data.joints:
                for joint in scene_data.joints:
                    # Map full Maya joint path to USD skeleton path
                    # Build USD path by walking up the hierarchy
                    usd_path = self._get_joint_usd_path(joint, scene_data.joints)
                    if usd_path:
                        joint_path_map[joint.name] = f"/Skeleton{usd_path}"

            for curve_data in scene_data.nurbs_curves:
                if self._check_cancel():
                    return False

                # Determine curve path based on parenting
                curve_name = self._sanitize_mesh_name(curve_data.name)

                # Check if curve is parented to a joint in the skeleton
                curve_path = None
                if curve_data.parent_name and curve_data.parent_name in joint_path_map:
                    # Parent curve to the joint in USD skeleton
                    joint_usd_path = joint_path_map[curve_data.parent_name]
                    curve_path = f"{joint_usd_path}/{curve_name}"
                    self.logger.debug(
                        f"Parenting curve {curve_name} to skeleton joint: {joint_usd_path}"
                    )
                else:
                    # Place under curves scope
                    curve_path = f"/root/curves/{curve_name}"

                # Create NurbsCurves prim
                nurbs_curve = UsdGeom.NurbsCurves.Define(stage, curve_path)

                # Set purpose based on renderability option
                # "guide" = non-renderable (for rig controls), "default" = renderable
                purpose = (
                    UsdGeom.Tokens.default
                    if options.nurbs_curves_renderable
                    else UsdGeom.Tokens.guide
                )

                # Set purpose using UsdGeom.Imageable API (not Prim API)
                # UsdGeom.NurbsCurves inherits from UsdGeom.Imageable which has GetPurposeAttr()
                try:
                    purpose_attr = nurbs_curve.GetPurposeAttr()
                    purpose_attr.Set(purpose)
                except Exception as purpose_err:
                    self.logger.debug(f"Could not set purpose for {curve_name}: {purpose_err}")

                # Set curve topology
                # In USD, NURBS curves are defined by:
                # - points (CV positions)
                # - curveVertexCounts (number of CVs per curve)
                # - knots (knot vector)
                # - order (degree + 1)
                # - ranges (parameter ranges)

                # Convert CV positions to Gf.Vec3f array
                points = [Gf.Vec3f(cv[0], cv[1], cv[2]) for cv in curve_data.control_vertices]
                nurbs_curve.GetPointsAttr().Set(points)

                # Set curve vertex counts (single curve = all CVs)
                nurbs_curve.GetCurveVertexCountsAttr().Set([len(curve_data.control_vertices)])

                # Set order (degree + 1)
                order = curve_data.degree + 1
                nurbs_curve.GetOrderAttr().Set([order])

                # Set knots
                nurbs_curve.GetKnotsAttr().Set(curve_data.knots)

                # Set ranges (parameter space)
                # For periodic curves, range is [knots[0], knots[-1]]
                if curve_data.knots:
                    param_range = Vt.Vec2dArray([(curve_data.knots[0], curve_data.knots[-1])])
                    nurbs_curve.GetRangesAttr().Set(param_range)

                # Set transforms using LOCAL space (object space = relative to parent)
                # CRITICAL: USD expects local transforms, not world transforms!
                if curve_data.local_matrix:
                    # Convert 16-element list to 4x4 matrix
                    matrix_values = curve_data.local_matrix
                    gf_matrix = Gf.Matrix4d(
                        matrix_values[0],
                        matrix_values[1],
                        matrix_values[2],
                        matrix_values[3],
                        matrix_values[4],
                        matrix_values[5],
                        matrix_values[6],
                        matrix_values[7],
                        matrix_values[8],
                        matrix_values[9],
                        matrix_values[10],
                        matrix_values[11],
                        matrix_values[12],
                        matrix_values[13],
                        matrix_values[14],
                        matrix_values[15],
                    )

                    # Use MakeMatrixXform to safely set/create transform
                    xformable = UsdGeom.Xformable(nurbs_curve.GetPrim())
                    xformable.MakeMatrixXform().Set(gf_matrix)

                # Set display color if available
                if curve_data.color:
                    # Set color as primvar (more reliable than direct attribute)
                    primvar_api = UsdGeom.PrimvarsAPI(nurbs_curve)
                    color_primvar = primvar_api.CreatePrimvar(
                        "displayColor", Sdf.ValueTypeNames.Color3fArray
                    )
                    color_primvar.Set(
                        [Gf.Vec3f(curve_data.color[0], curve_data.color[1], curve_data.color[2])]
                    )

                # Set line width if available
                if curve_data.line_width:
                    width_attr = nurbs_curve.GetWidthsAttr()
                    if not width_attr:
                        width_attr = nurbs_curve.CreateWidthsAttr()
                    width_attr.Set([curve_data.line_width])

                # Add custom attributes as primvars
                if curve_data.custom_attrs:
                    prim = nurbs_curve.GetPrim()
                    for attr_name, attr_value in curve_data.custom_attrs.items():
                        try:
                            # Create custom attribute
                            safe_name = attr_name.replace(":", "_")  # USD doesn't like colons
                            if isinstance(attr_value, (int, float)):
                                attr = prim.CreateAttribute(
                                    f"userProperties:{safe_name}", Sdf.ValueTypeNames.Double
                                )
                                attr.Set(float(attr_value))
                            elif isinstance(attr_value, str):
                                attr = prim.CreateAttribute(
                                    f"userProperties:{safe_name}", Sdf.ValueTypeNames.String
                                )
                                attr.Set(attr_value)
                        except Exception as e:
                            self.logger.debug(
                                f"Could not export custom attribute {attr_name}: {e}"
                            )

                self.logger.debug(
                    f"Exported NURBS curve: {curve_name} ({len(curve_data.control_vertices)} CVs)"
                )

            self.logger.info(
                f"[OK] Successfully exported {len(scene_data.nurbs_curves)} NURBS curves"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to export NURBS curves: {e}")
            return False

    def _export_rigging(
        self, stage: Any, scene_data: MayaSceneData, options: USDExportOptions
    ) -> bool:
        """Export rigging data to USD stage

        Clean Code: Rigging delegation to rig converter
        Disney/Pixar Critical: UsdSkel for animation pipelines

        Args:
            stage: USD stage
            scene_data: Parsed Maya scene data
            options: Export options

        Returns:
            True if successful
        """
        if not self.rig_converter:
            self.logger.warning("No rig converter available - skipping rigging")
            return True  # Not a failure, just skip

        if not scene_data.joints or not scene_data.skin_clusters:
            self.logger.info("No rigging data to export")
            return True

        try:
            # Step 1: Convert skeleton
            self.logger.info(f"Exporting skeleton with {len(scene_data.joints)} joints")
            skeleton = self.rig_converter.convert_skeleton(
                scene_data.joints, stage, skeleton_path="/Skeleton"
            )

            if not skeleton:
                self.logger.error("Failed to create skeleton")
                return False

            # Step 2: Convert skin weights for each mesh
            for skin_cluster in scene_data.skin_clusters:
                if self._check_cancel():
                    return False

                self.logger.info(f"Exporting skin weights: {skin_cluster.name}")

                # Clean Code: Use same sanitization as mesh export for name matching
                sanitized_mesh_name = self._sanitize_mesh_name(skin_cluster.mesh_name)
                self.logger.debug(
                    f"Looking for mesh: {skin_cluster.mesh_name} -> {sanitized_mesh_name}"
                )

                # Find corresponding mesh prim
                mesh_prim_path = f"/root/meshes/{sanitized_mesh_name}"
                self.logger.debug(f"Attempting to find mesh prim at: {mesh_prim_path}")
                mesh_prim = stage.GetPrimAtPath(mesh_prim_path)

                if not mesh_prim or not mesh_prim.IsValid():
                    self.logger.warning(f"Mesh prim not found: {mesh_prim_path}")
                    continue

                # Convert skin weights
                success = self.rig_converter.convert_skin_weights(
                    skin_cluster, skeleton, mesh_prim
                )

                if not success:
                    self.logger.warning(f"Failed to convert skin weights for {skin_cluster.name}")

            self.logger.info("Rigging export complete")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export rigging: {e}")
            return False

    def _export_rig_connections(
        self, stage: Any, scene_data: MayaSceneData, options: USDExportOptions
    ) -> bool:
        """Export rig connections for functional controllers - INDUSTRY FIRST!

        This enables complete rig functionality round-tripping through USD.
        Controllers will actually work after import!

        Args:
            stage: USD stage
            scene_data: Parsed Maya scene data
            options: Export options

        Returns:
            True if successful
        """
        try:
            # Create a scope for rig connections metadata
            UsdGeom.Scope.Define(stage, "/root/rigConnections")

            # Export direct connections
            for i, connection in enumerate(scene_data.rig_connections):
                if self._check_cancel():
                    return False

                # Create a prim for each connection
                connection_prim = UsdGeom.Xform.Define(
                    stage, f"/root/rigConnections/connection_{i}"
                )

                # Store connection metadata as custom attributes
                prim = connection_prim.GetPrim()
                prim.CreateAttribute("sourceNode", Sdf.ValueTypeNames.String).Set(
                    connection.source_node
                )
                prim.CreateAttribute("targetNode", Sdf.ValueTypeNames.String).Set(
                    connection.target_node
                )
                prim.CreateAttribute("sourceAttr", Sdf.ValueTypeNames.String).Set(
                    connection.source_attr
                )
                prim.CreateAttribute("targetAttr", Sdf.ValueTypeNames.String).Set(
                    connection.target_attr
                )
                prim.CreateAttribute("connectionType", Sdf.ValueTypeNames.String).Set(
                    connection.connection_type
                )
                prim.CreateAttribute("isInput", Sdf.ValueTypeNames.Bool).Set(connection.is_input)

                if connection.constraint_type:
                    prim.CreateAttribute("constraintType", Sdf.ValueTypeNames.String).Set(
                        connection.constraint_type
                    )
                if connection.constraint_node:
                    prim.CreateAttribute("constraintNode", Sdf.ValueTypeNames.String).Set(
                        connection.constraint_node
                    )
                if connection.driver_value is not None:
                    prim.CreateAttribute("driverValue", Sdf.ValueTypeNames.Double).Set(
                        connection.driver_value
                    )
                if connection.driven_value is not None:
                    prim.CreateAttribute("drivenValue", Sdf.ValueTypeNames.Double).Set(
                        connection.driven_value
                    )

            # Export constraints
            for i, constraint in enumerate(scene_data.constraints):
                if self._check_cancel():
                    return False

                # Create a prim for each constraint
                constraint_prim = UsdGeom.Xform.Define(
                    stage, f"/root/rigConnections/constraint_{i}"
                )

                # Store constraint metadata
                prim = constraint_prim.GetPrim()
                prim.CreateAttribute("name", Sdf.ValueTypeNames.String).Set(constraint.name)
                prim.CreateAttribute("constraintType", Sdf.ValueTypeNames.String).Set(
                    constraint.constraint_type
                )
                prim.CreateAttribute("targetNode", Sdf.ValueTypeNames.String).Set(
                    constraint.target_node
                )
                prim.CreateAttribute("targetAttrs", Sdf.ValueTypeNames.StringArray).Set(
                    constraint.target_attrs
                )
                prim.CreateAttribute("driverNodes", Sdf.ValueTypeNames.StringArray).Set(
                    constraint.driver_nodes
                )
                prim.CreateAttribute("maintainOffset", Sdf.ValueTypeNames.Bool).Set(
                    constraint.maintain_offset
                )
                prim.CreateAttribute("interpolate", Sdf.ValueTypeNames.Bool).Set(
                    constraint.interpolate
                )

                # Store driver weights as a dictionary (serialized as string)
                weights_str = str(constraint.driver_weights)
                prim.CreateAttribute("driverWeights", Sdf.ValueTypeNames.String).Set(weights_str)

            # Export set-driven keys
            for i, sdk in enumerate(scene_data.set_driven_keys):
                if self._check_cancel():
                    return False

                # Create a prim for each SDK
                sdk_prim = UsdGeom.Xform.Define(stage, f"/root/rigConnections/setDrivenKey_{i}")

                # Store SDK metadata
                prim = sdk_prim.GetPrim()
                prim.CreateAttribute("driverNode", Sdf.ValueTypeNames.String).Set(sdk.driver_node)
                prim.CreateAttribute("driverAttr", Sdf.ValueTypeNames.String).Set(sdk.driver_attr)
                prim.CreateAttribute("drivenNode", Sdf.ValueTypeNames.String).Set(sdk.driven_node)
                prim.CreateAttribute("drivenAttr", Sdf.ValueTypeNames.String).Set(sdk.driven_attr)
                prim.CreateAttribute("interpolation", Sdf.ValueTypeNames.String).Set(
                    sdk.interpolation
                )

                # Store keyframe data
                prim.CreateAttribute("driverValues", Sdf.ValueTypeNames.DoubleArray).Set(
                    sdk.driver_values
                )
                prim.CreateAttribute("drivenValues", Sdf.ValueTypeNames.DoubleArray).Set(
                    sdk.driven_values
                )

            total_connections = (
                len(scene_data.rig_connections)
                + len(scene_data.constraints)
                + len(scene_data.set_driven_keys)
            )
            self.logger.info(f"[OK] Successfully exported {total_connections} rig connections")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export rig connections: {e}")
            return False

    def _get_joint_usd_path(self, joint: JointData, all_joints: List[JointData]) -> Optional[str]:
        """Get the USD path for a joint in the skeleton hierarchy

        Args:
            joint: JointData for the joint
            all_joints: All joints in the scene

        Returns:
            USD path relative to /Skeleton, or None if not found
        """
        # Build joint name to JointData mapping
        joint_map = {j.name: j for j in all_joints}

        # Walk up the hierarchy to build the path
        path_parts = []
        current_joint = joint

        while current_joint:
            joint_short_name = current_joint.name.split("|")[-1]
            path_parts.insert(0, joint_short_name)

            # Move to parent
            if current_joint.parent_name and current_joint.parent_name in joint_map:
                current_joint = joint_map[current_joint.parent_name]
            else:
                break

        # Build USD path
        if path_parts:
            return "/" + "/".join(path_parts)

        return None

    def _update_progress(self, percentage: float, stage: str) -> None:
        """Update export progress

        Args:
            percentage: Progress percentage (0.0 to 1.0)
            stage: Current stage description

        Thread-Safe: Uses lock to ensure UI sees updates immediately
        """
        with self._progress_lock:
            self._current_progress = percentage
            self._current_stage = stage
        self.logger.debug(f"Progress: {percentage*100:.1f}% - {stage}")

    def _check_cancel(self) -> bool:
        """Check if export should be cancelled

        Returns:
            True if export was cancelled
        """
        if self._cancel_requested:
            self._last_error = "Export cancelled by user"
            self.logger.info("Export cancelled")
            return True
        return False

    def export_maya_scene_builtin(self, maya_file, output_path, export_options):
        """Export using Maya's built-in USD export functionality

        Args:
            maya_file: Path to the Maya file to export
            output_path: Path where the USD file will be saved
            export_options: Dictionary of options for the export command

        Returns:
            ExportResult object with details of the export
        """
        try:
            # If maya_file is provided, open it; otherwise, use current scene
            if maya_file:
                cmds.file(maya_file, open=True, force=True)

            # Perform the USD export using Maya's command
            cmds.mayaUSDExport(file=str(output_path), **export_options)

            # Count elements in the scene (approximate post-export counts)
            mesh_count = len(cmds.ls(type="mesh"))
            joint_count = len(cmds.ls(type="joint"))
            skin_cluster_count = len(cmds.ls(type="skinCluster"))
            curve_count = len(cmds.ls(type="nurbsCurve"))

            # Check if output file exists
            if output_path.exists():
                success = True
                warnings = []  # Could populate with actual warnings if available
                error_message = None
            else:
                success = False
                warnings = []
                error_message = "Export failed: output file not created"

            return ExportResult(
                success,
                output_path if success else None,
                mesh_count,
                joint_count,
                skin_cluster_count,
                curve_count,
                warnings,
                error_message,
            )

        except Exception as e:
            return ExportResult(False, None, 0, 0, 0, 0, [], str(e))
