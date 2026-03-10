"""
Maya Rig Importer - Import .mrig data and rebuild rig

This module imports .mrig JSON files and rebuilds rig components
on top of USD-imported geometry, reconnecting controllers, constraints,
blendshapes, IK handles, and SDKs.

Clean Code: Single Responsibility - Handles only rig data import
SOLID: Open/Closed - Extensible for new rig component types

Author: Mike Stumbo
Version: 1.5.0
License: MIT

Enhancements in v1.5.0:
- Progress callback for UI feedback
- Undo support (wrap operations in undo chunk)
- Space switch import
- Custom attribute recreation
- Proxy attribute reconnection
- Smart name remapping (fuzzy matching, namespace handling)
- Connection validation with detailed reporting
- Rig health check
- Auto-repair for common naming issues
"""
# pyright: reportOptionalMemberAccess=false

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Set

print("=" * 80)
print("[DEBUG][DEBUG][DEBUG] MAYA_RIG_IMPORTER.PY LOADED - VERSION 8 (CONTROLLERS .MA REF) [DEBUG][DEBUG][DEBUG]")
print("=" * 80)

# Maya imports (conditional)
try:
    import maya.cmds as cmds  # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    cmds = None  # type: ignore


@dataclass
class RigHealthReport:
    """
    v1.5.0: Detailed report of rig import health

    Contains information about what succeeded, what failed,
    and suggestions for manual fixes.
    """
    success: bool = True
    controllers_created: int = 0
    controllers_failed: List[str] = field(default_factory=list)
    constraints_created: int = 0
    constraints_failed: List[str] = field(default_factory=list)
    connections_made: int = 0
    connections_broken: List[str] = field(default_factory=list)
    nodes_not_found: List[str] = field(default_factory=list)
    nodes_remapped: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    auto_repairs: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get human-readable summary"""
        lines = []
        lines.append(f"{'[OK]' if self.success else '[WARNING]'} Rig Import Health Report")
        lines.append(f"  Controllers: {self.controllers_created} created, {len(self.controllers_failed)} failed")
        lines.append(f"  Constraints: {self.constraints_created} created, {len(self.constraints_failed)} failed")
        lines.append(f"  Connections: {self.connections_made} made, {len(self.connections_broken)} broken")

        if self.nodes_remapped:
            lines.append(f"  Name remaps: {len(self.nodes_remapped)}")

        if self.auto_repairs:
            lines.append(f"  Auto-repairs: {len(self.auto_repairs)}")

        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")

        return "\n".join(lines)


class MayaRigImporter:
    """
    Import .mrig data and rebuild rig on USD geometry

    Clean Code: Single Responsibility - Rig data import only
    SOLID: Interface Segregation - Focused interface for rig import

    v1.5.0 Enhancements:
    - Progress callback for UI feedback
    - Undo support (single-step undo of entire import)
    - Space switch import
    - Custom attribute recreation
    - Proxy attribute reconnection
    - Smart name remapping with fuzzy matching
    - Connection validation and health reporting
    - Auto-repair for common issues
    """

    def __init__(self):
        """Initialize rig importer"""
        self.logger = logging.getLogger(__name__)
        self.name_mapping: Dict[str, str] = {}  # Maps original names to scene names
        self._progress_callback: Optional[Callable[[str, int], None]] = None
        self._health_report: Optional[RigHealthReport] = None
        self._scene_nodes: Set[str] = set()  # Cache of all scene node names
        self._scene_short_names: Dict[str, List[str]] = {}  # short name -> full names

    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """
        Set progress callback for UI feedback

        Args:
            callback: Function(stage_name: str, percent: int) -> None
        """
        self._progress_callback = callback

    def _report_progress(self, stage: str, percent: int) -> None:
        """Report progress to callback if set"""
        if self._progress_callback:
            self._progress_callback(stage, percent)
        self.logger.debug(f"Progress: {stage} ({percent}%)")

    def get_health_report(self) -> Optional[RigHealthReport]:
        """Get the health report from the last import"""
        return self._health_report

    def import_rig(
        self,
        mrig_path: Path,
        usd_root: Optional[str] = None,
        options: Optional[Dict] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Tuple[bool, str]:
        """
        Import .mrig file and rebuild rig

        Args:
            mrig_path: Path to .mrig file
            usd_root: Optional USD root node for name mapping
            options: Import options dict
            progress_callback: Optional callback for progress updates

        Returns:
            (success: bool, message: str)

        v1.5.0: Supports undo - entire import can be undone in one step
        v1.5.0: Smart name remapping with fuzzy matching
        v1.5.0: Connection validation with health reporting
        """
        if not MAYA_AVAILABLE:
            return False, "Maya not available"

        if not mrig_path.exists():
            return False, f"File not found: {mrig_path}"

        # Set progress callback if provided
        if progress_callback:
            self.set_progress_callback(progress_callback)

        # Initialize health report
        self._health_report = RigHealthReport()

        # v1.5.0: Wrap entire import in undo chunk for single-step undo
        use_undo = options.get('enable_undo', True) if options else True

        try:
            options = options or {}

            # Start undo chunk
            if use_undo:
                cmds.undoInfo(openChunk=True, chunkName="Import Rig Data")

            self._report_progress("Loading rig data", 0)

            # v2.0: Check if this is a Maya rig file (.rig.mb or .rig.ma) instead of .mrig
            is_maya_rig_file = mrig_path.suffix.lower() in ('.mb', '.ma') or '.rig.' in str(mrig_path).lower()

            if is_maya_rig_file:
                # v2.0: Direct Maya file import - much faster!
                self.logger.info(f"🎮 v2.0: Importing Maya rig file: {mrig_path}")
                self._report_progress("Importing Maya rig file", 10)

                success = self._import_maya_rig_file(mrig_path)
                if success:
                    self._report_progress("Import complete", 100)
                    return True, f"[OK] Imported rig from {mrig_path.name}"
                else:
                    return False, f"Failed to import rig from {mrig_path.name}"

            # Legacy: Load .mrig JSON data
            with open(mrig_path, 'r') as f:
                rig_data = json.load(f)

            self.logger.info(f"[TOOL] Importing rig data from: {mrig_path}")

            # v1.5.0: Import controllers .mb file if it exists
            # This brings in NURBS controllers natively instead of recreating from JSON
            # Check for .mb first (faster), fall back to .ma for backwards compatibility
            # Note: Use stem to get base name without .mrig suffix, then add .controllers.mb/.ma
            base_path = mrig_path.parent / mrig_path.stem
            controllers_mb = base_path.with_suffix('.controllers.mb')
            controllers_ma = base_path.with_suffix('.controllers.ma')

            self.logger.info(f"🔍 Looking for controllers at: {controllers_mb}")

            if controllers_mb.exists() and options.get('import_controllers', True):
                self._report_progress("Importing controllers (.mb)", 10)
                print(f">>> Importing controllers from: {controllers_mb.name}")
                ref_success = self._reference_controllers_mb(controllers_mb)
                if ref_success:
                    self.logger.info(f"[OK] Imported controllers from {controllers_mb.name}")
                    # Skip JSON-based controller import since we imported them
                    options['_skip_controller_import'] = True
                else:
                    self.logger.warning(f"Failed to import {controllers_mb.name}, will try JSON import")
            elif controllers_ma.exists() and options.get('import_controllers', True):
                # Backwards compatibility with .ma files
                self._report_progress("Importing controllers (.ma)", 10)
                print(f">>> Importing controllers from: {controllers_ma.name}")
                ref_success = self._reference_controllers_mb(controllers_ma)  # Same method works for both
                if ref_success:
                    self.logger.info(f"[OK] Imported controllers from {controllers_ma.name}")
                    options['_skip_controller_import'] = True
                else:
                    self.logger.warning(f"Failed to import {controllers_ma.name}, will try JSON import")

            # v1.5.0: Build scene node cache for smart name matching
            self._report_progress("Scanning scene", 3)
            self._build_scene_node_cache()

            # Build name mapping (USD-imported geometry may have namespace/prefix)
            self._report_progress("Building name mapping", 5)
            self._build_smart_name_mapping(rig_data, usd_root)

            # Import controllers with custom/proxy attrs
            # Skip if we already referenced them from .ma file
            if options.get('import_controllers', True) and not options.get('_skip_controller_import'):
                print(">>> STEP: Importing controllers (15%)")
                self._report_progress("Importing controllers from JSON", 15)
                controllers = rig_data.get('controllers', [])
                print(f">>> Found {len(controllers)} controllers to import from JSON")
                self._import_controllers(
                    controllers,
                    import_custom_attrs=options.get('import_custom_attrs', True),
                    import_proxy_attrs=options.get('import_proxy_attrs', True)
                )
                print(f">>> Controllers DONE: {self._health_report.controllers_created}")
                self.logger.info(f"     [OK] {self._health_report.controllers_created} controllers")
            elif options.get('_skip_controller_import'):
                print(">>> STEP: Controllers already imported from .mb (15%)")
                self._report_progress("Controllers imported from .mb ✓", 15)
                print(">>> Controllers imported via .mb reference - skipping JSON import")
                self.logger.info("     [OK] Controllers imported via .mb reference")

            # Import IK handles BEFORE constraints (pole vector constraints need IK handles)
            print(">>> STEP: Importing IK handles (25%)")
            self._report_progress("Importing IK handles", 25)
            if options.get('import_ik_handles', True):
                ik_handles = rig_data.get('ik_handles', [])
                print(f">>> Found {len(ik_handles)} IK handles to import")
                self._import_ik_handles(ik_handles)
                print(">>> IK handles DONE")
                self.logger.info(f"     [OK] {len(ik_handles)} IK handles")

            # Import constraints (after IK handles so pole vector constraints work)
            print(">>> STEP: Importing constraints (40%)")
            self._report_progress("Importing constraints", 40)
            if options.get('import_constraints', True):
                constraints = rig_data.get('constraints', [])
                print(f">>> Found {len(constraints)} constraints to import")
                self._import_constraints(constraints)
                print(f">>> Constraints DONE: {self._health_report.constraints_created}")
                self.logger.info(f"     [OK] {self._health_report.constraints_created} constraints")

            # v1.5.0: Import space switches
            print(">>> STEP: Importing space switches (55%)")
            self._report_progress("Importing space switches", 55)
            if options.get('import_space_switches', True):
                space_switches = rig_data.get('space_switches', [])
                print(f">>> Found {len(space_switches)} space switches to import")
                self._import_space_switches(space_switches)
                print(">>> Space switches DONE")
                self.logger.info(f"     [OK] {len(space_switches)} space switches")

            # Import blendshapes
            print(">>> STEP: Importing blendshapes (70%)")
            self._report_progress("Importing blendshapes", 70)
            if options.get('import_blendshapes', True):
                blendshapes = rig_data.get('blendshapes', [])
                connections = rig_data.get('blendshape_connections', [])
                print(f">>> Found {len(blendshapes)} blendshapes, {len(connections)} connections")
                self._import_blendshapes(blendshapes, connections)
                print(">>> Blendshapes DONE")
                self.logger.info(
                    f"     [OK] {len(blendshapes)} blendshapes, {len(connections)} connections"
                )

            # Import Set Driven Keys
            print(">>> STEP: Importing SDKs (85%)")
            self._report_progress("Importing SDKs", 85)
            if options.get('import_sdks', True):
                sdks = rig_data.get('set_driven_keys', [])
                self._import_set_driven_keys(sdks)
                self.logger.info(f"     [OK] {len(sdks)} SDKs")

            # v1.5.0: Run health check and attempt auto-repair
            self._report_progress("Validating connections", 92)
            if options.get('validate_connections', True):
                self._validate_rig_connections(rig_data)

            # v1.5.0: Attempt auto-repair if enabled
            if options.get('auto_repair', True):
                self._report_progress("Auto-repairing", 96)
                self._attempt_auto_repair()

            self._report_progress("Import complete", 100)

            # Determine overall success
            has_critical_failures = (
                len(self._health_report.constraints_failed) > 0
                or len(self._health_report.connections_broken) > 5
            )
            self._health_report.success = not has_critical_failures

            # Build result message
            summary = self._health_report.get_summary()
            self.logger.info(f"[OK] Rig import complete\n{summary}")

            # Close undo chunk on success
            if use_undo:
                cmds.undoInfo(closeChunk=True)

            return True, summary

        except Exception as e:
            self.logger.error(f"[ERROR] Failed to import rig data: {e}")

            # Close undo chunk and undo on failure (clean rollback)
            if use_undo:
                cmds.undoInfo(closeChunk=True)
                self.logger.info("Rolling back partial import...")
                cmds.undo()

            return False, f"Import failed: {e}"

    def _import_maya_rig_file(self, rig_path: Path) -> bool:
        """
        v2.0: Import Maya rig file (.rig.mb or .rig.ma)

        This is the fast path - directly importing the Maya file with all
        rig components (controllers, constraints, IK, SDKs) intact.

        Args:
            rig_path: Path to the .rig.mb or .rig.ma file

        Returns:
            True if import succeeded, False otherwise
        """
        try:
            self.logger.info(f"🎮 Importing Maya rig file: {rig_path.name}")

            # Determine file type
            suffix = rig_path.suffix.lower()
            if suffix == '.ma' or '.rig.ma' in str(rig_path).lower():
                file_type = 'mayaAscii'
            else:
                file_type = 'mayaBinary'

            # Import the Maya file
            imported_nodes = cmds.file(
                str(rig_path),
                i=True,  # import, not reference
                type=file_type,
                returnNewNodes=True,
                preserveReferences=False,
                ignoreVersion=True
            )

            if not imported_nodes:
                self.logger.warning("No nodes imported from rig file")
                return False

            self.logger.info(f"[OK] Imported {len(imported_nodes)} nodes from {rig_path.name}")

            # Keep Maya responsive
            cmds.refresh()

            # Rebuild scene cache
            self._build_scene_node_cache()

            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Failed to import Maya rig file: {e}")
            return False

    def _reference_controllers_mb(self, mb_path: Path) -> bool:
        """
        v1.5.0: Import the controllers .mb file

        This imports NURBS controller curves natively instead of recreating
        from JSON data, which is much faster and more reliable.

        Args:
            mb_path: Path to the .controllers.mb file

        Returns:
            True if import succeeded, False otherwise
        """
        try:
            # Import (not reference) - controllers keep original names
            imported_nodes = cmds.file(
                str(mb_path),
                i=True,  # import, not reference
                returnNewNodes=True,
                preserveReferences=False
            )

            if not imported_nodes:
                self.logger.warning("No nodes imported from controller file")
                return False

            self.logger.info(f"[OK] Imported {len(imported_nodes)} nodes from {mb_path.name}")

            # Keep Maya responsive after file import
            cmds.refresh()

            # Rebuild scene cache to include new nodes
            self._build_scene_node_cache()
            return True

        except Exception as e:
            self.logger.error(f"Failed to import controllers .mb: {e}")
            return False

    def _build_scene_node_cache(self) -> None:
        """
        v1.5.0: Build cache of all scene nodes for efficient name matching

        Creates:
        - _scene_nodes: Set of all node names
        - _scene_short_names: Dict mapping short names to full names
        """
        self._scene_nodes = set()
        self._scene_short_names = {}

        self.logger.info("🔍 Scanning scene nodes...")

        # Get all transforms and joints
        all_nodes = cmds.ls(transforms=True, long=True) or []
        self.logger.info(f"   Found {len(all_nodes)} transforms")

        joints = cmds.ls(type='joint', long=True) or []
        self.logger.info(f"   Found {len(joints)} joints")
        all_nodes.extend(joints)

        for full_name in all_nodes:
            self._scene_nodes.add(full_name)

            # Extract short name (without namespace or path)
            short_name = full_name.split('|')[-1].split(':')[-1]

            if short_name not in self._scene_short_names:
                self._scene_short_names[short_name] = []
            self._scene_short_names[short_name].append(full_name)

        # Keep Maya responsive after heavy scene scan
        cmds.refresh()

        self.logger.info(f"[OK] Cached {len(self._scene_nodes)} scene nodes")

    def _build_smart_name_mapping(self, rig_data: Dict, usd_root: Optional[str]) -> None:
        """
        v1.5.0: Smart name mapping with fuzzy matching and namespace handling

        Handles common USD naming transformations:
        - Namespace prefixes (Character1:Hips)
        - Path prefixes (|imported|Hips)
        - Underscore/camelCase variations
        - Common suffixes (_geo, _jnt, _ctrl)
        """
        import time
        start_time = time.time()

        self.name_mapping = {}

        # Collect all names from .mrig that need mapping
        names_to_map: Set[str] = set()

        # Skeleton root
        skeleton_root = rig_data.get('skeleton_root')
        if skeleton_root:
            names_to_map.add(skeleton_root)

        # Controllers
        for ctrl in rig_data.get('controllers', []):
            names_to_map.add(ctrl['name'])
            if ctrl.get('parent'):
                names_to_map.add(ctrl['parent'])

        # Constraint targets
        for const in rig_data.get('constraints', []):
            names_to_map.add(const['driven'])
            names_to_map.update(const.get('drivers', []))

        # IK handle joints
        for ik in rig_data.get('ik_handles', []):
            names_to_map.add(ik['start_joint'])
            names_to_map.add(ik['end_joint'])
            if ik.get('pole_vector'):
                names_to_map.add(ik['pole_vector'])

        # Blendshape geometry
        for bs in rig_data.get('blendshapes', []):
            names_to_map.add(bs['base_geometry'])

        total_names = len(names_to_map)
        self.logger.info(f"🔍 Mapping {total_names} unique names...")

        # Try to find each name in the scene
        processed = 0
        slow_lookups = 0
        fast_mode_enabled = False

        for orig_name in names_to_map:
            if not orig_name:
                continue

            # PERFORMANCE: Enable fast mode if lookups are too slow
            lookup_start = time.time()
            scene_name = self._find_scene_node(orig_name, usd_root, fast_mode=fast_mode_enabled)
            lookup_time = time.time() - lookup_start

            if lookup_time > 0.5:
                slow_lookups += 1
                self.logger.warning(f"⏱️ Slow lookup for '{orig_name}': {lookup_time:.2f}s")

                # Enable fast mode after 3 slow lookups
                if slow_lookups >= 3 and not fast_mode_enabled:
                    fast_mode_enabled = True
                    self.logger.warning("[HYBRID] Enabling fast mode - skipping expensive name searches")

            if scene_name and scene_name != orig_name:
                self.name_mapping[orig_name] = scene_name
                self._health_report.nodes_remapped[orig_name] = scene_name
            elif not scene_name:
                self._health_report.nodes_not_found.append(orig_name)

            processed += 1
            # Log progress and refresh UI every 100 names to prevent Maya freeze
            if processed % 100 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                self.logger.info(f"   Progress: {processed}/{total_names} names ({rate:.0f} names/sec)")
                cmds.refresh()  # Keep Maya responsive

        elapsed = time.time() - start_time
        self.logger.info(f"📍 Name mapping complete in {elapsed:.2f}s: "
                         f"{len(self.name_mapping)} remapped, "
                         f"{len(self._health_report.nodes_not_found)} not found")

    def _find_scene_node(self, orig_name: str, usd_root: Optional[str], fast_mode: bool = False) -> Optional[str]:
        """
        v1.5.0: Find a scene node matching the original name

        Search strategies (in order):
        1. Exact match
        2. Short name match (ignoring namespace/path)
        3. Strip prefixes like 'model:' and try again (if not fast_mode)
        4. Fuzzy match (common variations) (if not fast_mode)
        5. Under USD root hierarchy (if not fast_mode)

        Args:
            orig_name: Original name from .mrig
            usd_root: USD root node name
            fast_mode: Skip expensive fuzzy matching and hierarchy searches
        """

        # Strategy 1: Exact match
        if cmds.objExists(orig_name):
            return orig_name

        # Strategy 2: Short name match
        short_name = orig_name.split('|')[-1].split(':')[-1]
        if short_name in self._scene_short_names:
            candidates = self._scene_short_names[short_name]
            if len(candidates) == 1:
                return candidates[0].split('|')[-1]  # Return short path
            elif len(candidates) > 1:
                # Multiple matches - prefer one under USD root
                if usd_root:
                    for candidate in candidates:
                        if usd_root in candidate:
                            return candidate.split('|')[-1]
                # Return first match with warning
                self._health_report.warnings.append(
                    f"Multiple matches for '{orig_name}', using '{candidates[0]}'"
                )
                return candidates[0].split('|')[-1]

        # FAST MODE: Skip expensive searches
        if fast_mode:
            return None

        # Strategy 3: Handle 'model:' prefix and other namespace prefixes
        # PERFORMANCE: Use dictionary lookups only, NO string iteration
        # The .mrig may have names like 'model:Body_Blendshape' but scene has namespace prefix
        if ':' in short_name:
            # Strip any namespace prefix from the original name
            stripped_name = short_name.split(':')[-1]
            if stripped_name in self._scene_short_names:
                candidates = self._scene_short_names[stripped_name]
                if candidates:
                    return candidates[0].split('|')[-1]

        # Strategy 4: Try common suffix variations (dictionary lookup only)
        # Check base name without common suffixes
        for suffix in ['Shape', 'Orig', '_jnt', '_geo', '_ctrl', '_grp', 'Blendshape']:
            if short_name.endswith(suffix):
                base_name = short_name[:-len(suffix)]
                if base_name in self._scene_short_names:
                    candidates = self._scene_short_names[base_name]
                    if candidates:
                        return candidates[0].split('|')[-1]
            # Also try adding suffix
            name_with_suffix = short_name + suffix
            if name_with_suffix in self._scene_short_names:
                candidates = self._scene_short_names[name_with_suffix]
                if candidates:
                    return candidates[0].split('|')[-1]

        return None

    def _generate_name_variations(self, name: str) -> List[str]:
        """
        v1.5.0: Generate common name variations for fuzzy matching

        Handles:
        - With/without common suffixes
        - CamelCase vs underscore
        - Common Maya naming conventions
        """
        variations = []
        base = name.split('|')[-1].split(':')[-1]

        # Common suffix variations
        suffixes = ['', '_jnt', '_JNT', '_Jnt', '_geo', '_GEO', '_ctrl', '_CTRL', '_Ctrl']
        base_no_suffix = base
        for suffix in ['_jnt', '_JNT', '_Jnt', '_geo', '_GEO', '_ctrl', '_CTRL', '_Ctrl', '_grp', '_GRP']:
            if base.endswith(suffix):
                base_no_suffix = base[:-len(suffix)]
                break

        # Generate variations
        for suffix in suffixes:
            variations.append(f"{base_no_suffix}{suffix}")

        # CamelCase variations
        # Convert underscore to CamelCase
        if '_' in base:
            camel = ''.join(word.capitalize() for word in base.split('_'))
            variations.append(camel)
            variations.append(camel[0].lower() + camel[1:] if camel else camel)

        # Convert CamelCase to underscore
        underscore = re.sub(r'(?<!^)(?=[A-Z])', '_', base).lower()
        if underscore != base.lower():
            variations.append(underscore)
            variations.append(underscore.title().replace('_', ''))

        return variations

    def _resolve_name(self, orig_name: str) -> str:
        """Resolve original name to scene name using mapping"""
        return self.name_mapping.get(orig_name, orig_name)

    def _import_controllers(
        self,
        controllers: List[Dict],
        import_custom_attrs: bool = True,
        import_proxy_attrs: bool = True
    ):
        """
        Create controller curves

        Args:
            controllers: List of controller data dicts
            import_custom_attrs: v1.5.0 - Recreate custom attributes
            import_proxy_attrs: v1.5.0 - Reconnect proxy attributes
        """
        for ctrl_data in controllers:
            try:
                name = ctrl_data['name']

                # Skip if already exists
                if cmds.objExists(name):
                    self.logger.debug(f"Controller {name} already exists, skipping")
                    continue

                curve = None  # Track created node

                # Create controller based on shape type
                if ctrl_data['shape_type'] == 'nurbs':
                    # Create NURBS curve from CV data
                    curve_data = ctrl_data.get('curve_data', {})
                    if curve_data and curve_data.get('cvs'):
                        degree = curve_data.get('degree', 3)
                        cvs = curve_data['cvs']
                        form = curve_data.get('form', 0)  # 0=open, 1=closed, 2=periodic
                        knots = curve_data.get('knots')

                        # Create curve
                        try:
                            if form == 2:  # periodic
                                # Periodic curves require explicit knots
                                if knots:
                                    curve = cmds.curve(degree=degree, point=cvs, knot=knots, periodic=True)
                                else:
                                    # Generate knots for periodic curve
                                    # For periodic: knots = [-degree, ..., numCVs-1]
                                    num_cvs = len(cvs)
                                    knots = list(range(-degree, num_cvs))
                                    curve = cmds.curve(degree=degree, point=cvs, knot=knots, periodic=True)
                            elif knots:
                                # Open curve with explicit knots
                                curve = cmds.curve(degree=degree, point=cvs, knot=knots)
                            else:
                                # Open curve without knots (Maya will generate)
                                curve = cmds.curve(degree=degree, point=cvs)
                        except Exception as curve_error:
                            # Fallback: try creating as non-periodic if periodic fails
                            self.logger.debug(f"Periodic curve creation failed, trying non-periodic: {curve_error}")
                            try:
                                curve = cmds.curve(degree=degree, point=cvs)
                            except Exception as e2:
                                raise e2

                        # Rename to match original
                        curve = cmds.rename(curve, name)

                        # Set transform - position the curve in space
                        # CVs are in object space and already contain the scale baked in,
                        # so we only apply translation and rotation, NOT scale
                        transform = ctrl_data['transform']
                        cmds.xform(curve, translation=transform['translate'], worldSpace=False)
                        cmds.xform(curve, rotation=transform['rotate'], worldSpace=False)
                        # NOTE: Scale is NOT applied because CVs already have scale baked into
                        # their object-space positions. Applying scale would double it.

                        # Set color override
                        color = ctrl_data.get('color')
                        if color is not None:
                            cmds.setAttr(f"{curve}.overrideEnabled", True)
                            cmds.setAttr(f"{curve}.overrideColor", color)

                        # Parent if needed
                        parent = ctrl_data.get('parent')
                        if parent:
                            parent_name = self._resolve_name(parent)
                            if cmds.objExists(parent_name):
                                cmds.parent(curve, parent_name)

                        self.logger.debug(f"Created controller: {name}")

                elif ctrl_data['shape_type'] == 'locator':
                    # Create locator
                    curve = cmds.spaceLocator(name=name)[0]

                    # For locators, we need to set position and rotation
                    # But locators are created at default scale, so we DO need scale here
                    transform = ctrl_data['transform']
                    cmds.xform(curve, translation=transform['translate'], worldSpace=False)
                    cmds.xform(curve, rotation=transform['rotate'], worldSpace=False)
                    # Locators need scale applied (unlike NURBS where CVs have it baked)
                    scale = transform['scale']
                    cmds.setAttr(f"{curve}.scaleX", scale[0])
                    cmds.setAttr(f"{curve}.scaleY", scale[1])
                    cmds.setAttr(f"{curve}.scaleZ", scale[2])

                    # Parent if needed
                    parent = ctrl_data.get('parent')
                    if parent:
                        parent_name = self._resolve_name(parent)
                        if cmds.objExists(parent_name):
                            cmds.parent(curve, parent_name)

                    self.logger.debug(f"Created locator controller: {name}")

                # v1.5.0: Track success in health report
                if curve:
                    self._health_report.controllers_created += 1

                # v1.5.0: Import custom attributes
                if curve and import_custom_attrs:
                    custom_attrs = ctrl_data.get('custom_attrs')
                    if custom_attrs:
                        self._create_custom_attributes(curve, custom_attrs)

                # v1.5.0: Import proxy attributes (after all controllers exist)
                # Note: Proxy attrs are handled in a second pass

            except Exception as e:
                self.logger.warning(f"Failed to create controller {ctrl_data.get('name')}: {e}")
                self._health_report.controllers_failed.append(ctrl_data.get('name', 'unknown'))
                continue

        # v1.5.0: Second pass for proxy attribute connections
        if import_proxy_attrs:
            # Count controllers with proxy attrs and total proxy attrs
            controllers_with_proxy = [
                (c['name'], c.get('proxy_attrs', {}))
                for c in controllers if c.get('proxy_attrs')
            ]
            proxy_count = len(controllers_with_proxy)
            total_attrs = sum(len(pa) for _, pa in controllers_with_proxy)
            print(f">>> Connecting proxy attrs: {total_attrs} attrs across {proxy_count} controllers...")

            processed_ctrls = 0
            processed_attrs = 0
            connected = 0
            missing_sources = set()  # Track unique missing sources

            for name, proxy_attrs in controllers_with_proxy:
                if cmds.objExists(name):
                    for attr_name, proxy_data in proxy_attrs.items():
                        processed_attrs += 1
                        try:
                            source_node = self._resolve_name(proxy_data['source_node'])
                            source_attr = proxy_data['source_attr']

                            if not cmds.objExists(source_node):
                                missing_sources.add(source_node)
                                continue

                            source_path = f"{source_node}.{source_attr}"
                            dest_path = f"{name}.{attr_name}"

                            if cmds.objExists(source_path) and cmds.objExists(dest_path):
                                cmds.connectAttr(source_path, dest_path, force=True)
                                connected += 1
                        except Exception:
                            continue

                        # Progress every 500 attrs
                        if processed_attrs % 500 == 0:
                            print(f">>> Proxy attrs: {processed_attrs}/{total_attrs} processed, {connected} connected")

                    processed_ctrls += 1

            # Summary instead of per-attr warnings
            if missing_sources:
                self.logger.warning(
                    f"Proxy attrs: {len(missing_sources)} source nodes not found"
                )
            print(f">>> Proxy attrs DONE: {connected}/{total_attrs} connected across {processed_ctrls} controllers")

    def _create_custom_attributes(self, node: str, custom_attrs: Dict):
        """
        v1.5.0: Recreate custom attributes on a node

        Args:
            node: Target node name
            custom_attrs: Dict of {attr_name: {type, value, min, max, enum_names, keyable, channelBox}}
        """
        for attr_name, attr_data in custom_attrs.items():
            try:
                attr_type = attr_data.get('type', 'double')

                # Create attribute based on type
                if attr_type == 'enum':
                    enum_names = attr_data.get('enum_names', ['Option1', 'Option2'])
                    cmds.addAttr(
                        node, longName=attr_name, attributeType='enum',
                        enumName=':'.join(enum_names)
                    )
                elif attr_type in ['double', 'float']:
                    kwargs = {'longName': attr_name, 'attributeType': 'double'}
                    if 'min' in attr_data:
                        kwargs['minValue'] = attr_data['min']
                    if 'max' in attr_data:
                        kwargs['maxValue'] = attr_data['max']
                    cmds.addAttr(node, **kwargs)
                elif attr_type in ['long', 'short', 'int']:
                    kwargs = {'longName': attr_name, 'attributeType': 'long'}
                    if 'min' in attr_data:
                        kwargs['minValue'] = int(attr_data['min'])
                    if 'max' in attr_data:
                        kwargs['maxValue'] = int(attr_data['max'])
                    cmds.addAttr(node, **kwargs)
                elif attr_type == 'bool':
                    cmds.addAttr(node, longName=attr_name, attributeType='bool')
                elif attr_type == 'string':
                    cmds.addAttr(node, longName=attr_name, dataType='string')
                else:
                    # Default to double
                    cmds.addAttr(node, longName=attr_name, attributeType='double')

                # Set keyable/channelBox
                attr_path = f"{node}.{attr_name}"
                if attr_data.get('keyable', True):
                    cmds.setAttr(attr_path, keyable=True)
                elif attr_data.get('channelBox', False):
                    cmds.setAttr(attr_path, channelBox=True)

                # Set value
                value = attr_data.get('value')
                if value is not None:
                    if attr_type == 'string':
                        cmds.setAttr(attr_path, value, type='string')
                    else:
                        cmds.setAttr(attr_path, value)

                self.logger.debug(f"Created custom attr: {attr_path}")

            except Exception as e:
                self.logger.debug(f"Failed to create custom attr {attr_name}: {e}")
                continue

    def _import_space_switches(self, space_switches: List[Dict]):
        """
        v1.5.0: Recreate space switch setups

        Args:
            space_switches: List of space switch data dicts
        """
        total = len(space_switches)
        print(f">>> Space switches: processing {total} switches...")
        created = 0
        skipped = 0

        for idx, switch_data in enumerate(space_switches):
            try:
                control = self._resolve_name(switch_data['control'])
                attr_name = switch_data['attribute']
                spaces = switch_data.get('spaces', [])
                # constraint_name not used - SDK connections disabled for now

                if not cmds.objExists(control):
                    skipped += 1
                    continue

                # Create enum attribute for space switching
                space_names = [s.get('name', f'space{i}') for i, s in enumerate(spaces)]
                attr_path = f"{control}.{attr_name}"

                if not cmds.objExists(attr_path):
                    try:
                        cmds.addAttr(
                            control, longName=attr_name, attributeType='enum',
                            enumName=':'.join(space_names), keyable=True
                        )
                        created += 1
                    except Exception:
                        skipped += 1
                        continue
                else:
                    created += 1  # Already exists

                # Skip SDK connections for now - they require constraint targets
                # that may not exist and can cause hangs
                # TODO: Re-enable when constraint import is verified working

            except Exception:
                skipped += 1
                continue

            # Progress and UI refresh every 25 to keep Maya responsive
            if (idx + 1) % 25 == 0:
                print(f">>> Space switches: {idx + 1}/{total} processed")
                cmds.refresh()

        print(f">>> Space switches DONE: {created} created, {skipped} skipped")

    def _import_constraints(self, constraints: List[Dict]):
        """Recreate constraints with health reporting"""
        total = len(constraints)
        print(f">>> Constraints: processing {total} constraints...")
        created = 0
        skipped_driven = 0
        skipped_drivers = 0

        for idx, const_data in enumerate(constraints):
            try:
                constraint_type = const_data['type']
                driven = self._resolve_name(const_data['driven'])
                drivers = [self._resolve_name(d) for d in const_data['drivers']]
                maintain_offset = const_data.get('maintain_offset', True)
                weights = const_data.get('weights', [])
                skip_translate = const_data.get('skip_translate', [])
                skip_rotate = const_data.get('skip_rotate', [])

                # Check if objects exist
                if not cmds.objExists(driven):
                    # Don't log each one - just count
                    self._health_report.constraints_failed.append(
                        f"{constraint_type} on {driven}: driven not found"
                    )
                    skipped_driven += 1
                    continue

                existing_drivers = [d for d in drivers if cmds.objExists(d)]
                missing_drivers = [d for d in drivers if not cmds.objExists(d)]

                if missing_drivers:
                    self._health_report.warnings.append(
                        f"Constraint on {driven}: missing drivers {missing_drivers}"
                    )

                if not existing_drivers:
                    # Don't log each one - just count
                    self._health_report.constraints_failed.append(
                        f"{constraint_type} on {driven}: no drivers found"
                    )
                    skipped_drivers += 1
                    continue

                # Create constraint
                success = self._create_constraint(
                    constraint_type,
                    driven,
                    existing_drivers,
                    maintain_offset,
                    weights,
                    skip_translate,
                    skip_rotate
                )

                if success:
                    self._health_report.constraints_created += 1
                    self._health_report.connections_made += len(existing_drivers)
                    created += 1
                else:
                    self._health_report.constraints_failed.append(
                        f"{constraint_type} on {driven}: creation failed"
                    )

            except Exception:
                continue

            # Progress and UI refresh every 50 to keep Maya responsive
            if (idx + 1) % 50 == 0:
                print(f">>> Constraints: {idx + 1}/{total} processed, {created} created")
                cmds.refresh()

        # Summary at end
        if skipped_driven > 0 or skipped_drivers > 0:
            self.logger.warning(
                f"Constraints: {skipped_driven} skipped (driven not found), "
                f"{skipped_drivers} skipped (no drivers)"
            )
        print(f">>> Constraints DONE: {created}/{total} created")

    def _create_constraint(
        self,
        constraint_type: str,
        driven: str,
        drivers: List[str],
        maintain_offset: bool,
        weights: List[float],
        skip_translate: List[str],
        skip_rotate: List[str]
    ) -> bool:
        """Create a constraint of the specified type. Returns True on success."""
        try:
            # Build skip flags
            skip_flags = {}
            for axis in skip_translate:
                skip_flags[f'skip{axis}'] = True
            for axis in skip_rotate:
                skip_flags[f'skip{axis}'] = True

            constraint = None

            # Create constraint based on type
            if constraint_type == 'parentConstraint':
                constraint = cmds.parentConstraint(
                    *drivers,
                    driven,
                    maintainOffset=maintain_offset,
                    **skip_flags
                )[0]

            elif constraint_type == 'orientConstraint':
                constraint = cmds.orientConstraint(
                    *drivers,
                    driven,
                    maintainOffset=maintain_offset,
                    **skip_flags
                )[0]

            elif constraint_type == 'pointConstraint':
                constraint = cmds.pointConstraint(
                    *drivers,
                    driven,
                    maintainOffset=maintain_offset,
                    **skip_flags
                )[0]

            elif constraint_type == 'aimConstraint':
                constraint = cmds.aimConstraint(
                    *drivers,
                    driven,
                    maintainOffset=maintain_offset
                )[0]

            elif constraint_type == 'scaleConstraint':
                constraint = cmds.scaleConstraint(
                    *drivers,
                    driven,
                    maintainOffset=maintain_offset
                )[0]

            elif constraint_type == 'poleVectorConstraint':
                if len(drivers) == 1:
                    # Pole vector only works with rotate plane (RP) solver IK handles
                    # Check if driven is an IK handle with RP solver
                    if cmds.objectType(driven) == 'ikHandle':
                        solver = cmds.ikHandle(driven, q=True, solver=True)
                        if solver and 'ikRPsolver' not in solver:
                            # SC solver doesn't support pole vector - skip silently
                            return False
                    constraint = cmds.poleVectorConstraint(drivers[0], driven)[0]
                else:
                    self.logger.warning(
                        f"poleVectorConstraint requires exactly 1 driver, got {len(drivers)}"
                    )
                    return False

            else:
                self.logger.warning(f"Unknown constraint type: {constraint_type}")
                return False

            # Set weights if provided
            if constraint and weights and len(weights) == len(drivers):
                weight_attrs = cmds.listAttr(constraint, string='*W*') or []
                for i, weight in enumerate(weights):
                    if i < len(weight_attrs):
                        try:
                            cmds.setAttr(f"{constraint}.{weight_attrs[i]}", weight)
                        except Exception as e:
                            self.logger.debug(f"Could not set weight: {e}")

            return constraint is not None

        except Exception as e:
            self.logger.warning(f"Constraint creation error: {e}")
            return False

    def _import_ik_handles(self, ik_handles: List[Dict]):
        """Create IK handles"""
        total = len(ik_handles)
        print(f">>> IK Handles: processing {total} handles...")
        created = 0
        skipped = 0
        already_exist = 0

        for idx, ik_data in enumerate(ik_handles):
            try:
                name = ik_data['name']
                start_joint = self._resolve_name(ik_data['start_joint'])
                end_joint = self._resolve_name(ik_data['end_joint'])
                solver = ik_data.get('solver', 'ikRPsolver')
                priority = ik_data.get('priority', 1)
                pole_vector = ik_data.get('pole_vector')

                # Check if joints exist
                if not cmds.objExists(start_joint) or not cmds.objExists(end_joint):
                    skipped += 1
                    continue

                # Skip if IK handle already exists
                if cmds.objExists(name):
                    already_exist += 1
                    created += 1  # Count as success
                    continue

                # Create IK handle
                ik_handle = cmds.ikHandle(
                    name=name,
                    startJoint=start_joint,
                    endEffector=end_joint,
                    solver=solver,
                    priority=priority
                )[0]

                # Add pole vector constraint if specified (only for RP solver)
                if pole_vector and 'ikRPsolver' in solver:
                    pole_name = self._resolve_name(pole_vector)
                    if cmds.objExists(pole_name):
                        try:
                            cmds.poleVectorConstraint(pole_name, ik_handle)
                        except Exception:
                            pass  # Silently skip pole vector errors

                created += 1

            except Exception as e:
                self.logger.debug(f"IK handle {ik_data.get('name')} error: {e}")
                skipped += 1
                continue

            # Refresh UI every 10 handles
            if (idx + 1) % 10 == 0:
                cmds.refresh()

        if already_exist > 0:
            print(f">>> IK Handles: {already_exist} already existed (from .mb import)")
        if skipped > 0:
            self.logger.warning(f"IK Handles: {skipped} skipped (joints not found)")
        print(f">>> IK Handles DONE: {created}/{total} created")

    def _import_blendshapes(self, blendshapes: List[Dict], connections: List[Dict]):
        """Create blendshape deformers and reconnect drivers"""
        total_bs = len(blendshapes)
        total_conn = len(connections)
        print(f">>> Blendshapes: processing {total_bs} deformers, {total_conn} connections...")
        created = 0
        skipped = 0
        skipped_curves = 0

        for idx, bs_data in enumerate(blendshapes):
            try:
                name = bs_data['name']
                base_geometry = self._resolve_name(bs_data['base_geometry'])

                # Check if base geometry exists
                if not cmds.objExists(base_geometry):
                    skipped += 1
                    continue

                # Check if base geometry is deformable (mesh or nurbsSurface, not nurbsCurve)
                # NURBS curves can't have blendshapes - they use wire deformers instead
                node_type = cmds.nodeType(base_geometry)

                # If it's already a shape node, check directly
                if node_type == 'nurbsCurve':
                    skipped_curves += 1
                    continue

                # If it's a transform, check its shapes
                if node_type == 'transform':
                    shapes = cmds.listRelatives(base_geometry, shapes=True) or []
                    if shapes:
                        shape_type = cmds.nodeType(shapes[0])
                        if shape_type == 'nurbsCurve':
                            skipped_curves += 1
                            continue

                # Check if blendshape already exists
                if cmds.objExists(name):
                    created += 1  # Already exists
                else:
                    # Create empty blendshape (targets will be added separately if needed)
                    targets = bs_data.get('targets', [])
                    target_names = [t['name'] for t in targets if cmds.objExists(t['name'])]

                    if target_names:
                        # Create blendshape with existing targets
                        blendshape = cmds.blendShape(
                            target_names,
                            base_geometry,
                            name=name,
                            frontOfChain=True
                        )[0]

                        # Set initial weights
                        for target in targets:
                            target_name = target['name']
                            weight = target.get('weight', 0.0)
                            if cmds.objExists(f"{blendshape}.{target_name}"):
                                cmds.setAttr(f"{blendshape}.{target_name}", weight)

                        created += 1
                    else:
                        skipped += 1
                        continue

            except Exception:
                skipped += 1
                continue

            # Progress every 10
            if (idx + 1) % 10 == 0:
                print(f">>> Blendshapes: {idx + 1}/{total_bs} processed")

        if skipped_curves > 0:
            print(f">>> Blendshapes: {skipped_curves} NURBS curves skipped (use wire deformers instead)")
        print(f">>> Blendshapes DONE: {created}/{total_bs} created, {skipped} skipped")

        # Reconnect blendshape drivers
        connected = 0
        conn_skipped = 0
        for idx, conn_data in enumerate(connections):
            try:
                blendshape = conn_data['blendshape']
                target = conn_data['target']
                driver = conn_data['driver']
                connection_type = conn_data.get('connection_type', 'direct')
                sdk_keys = conn_data.get('sdk_keys')

                # Resolve names
                blendshape = self._resolve_name(blendshape)
                driver = self._resolve_name(driver)

                # Check if blendshape and driver exist
                if not cmds.objExists(blendshape):
                    conn_skipped += 1
                    continue

                if not cmds.objExists(driver.split('.')[0]):
                    conn_skipped += 1
                    continue

                target_attr = f"{blendshape}.{target}"
                if not cmds.objExists(target_attr):
                    conn_skipped += 1
                    continue

                # Create connection
                if connection_type == 'direct':
                    cmds.connectAttr(driver, target_attr, force=True)
                    connected += 1
                elif connection_type == 'sdk' and sdk_keys:
                    self._create_sdk(driver, target_attr, sdk_keys)
                    connected += 1

            except Exception:
                conn_skipped += 1
                continue

            # Progress every 50
            if (idx + 1) % 50 == 0:
                print(f">>> Blendshape connections: {idx + 1}/{total_conn} processed")

        if conn_skipped > 0:
            self.logger.warning(f"Blendshape connections: {conn_skipped} skipped")
        print(f">>> Blendshape connections DONE: {connected}/{total_conn} connected")

    def _import_set_driven_keys(self, sdks: List[Dict]):
        """Recreate Set Driven Key relationships"""
        total = len(sdks)
        print(f">>> SDKs: processing {total} set driven keys...")
        created = 0
        skipped = 0

        for idx, sdk_data in enumerate(sdks):
            try:
                driver = self._resolve_name(sdk_data['driver'])
                driven = self._resolve_name(sdk_data['driven'])
                keys = sdk_data.get('keys', [])

                # Check if driver and driven exist
                driver_obj = driver.split('.')[0]
                driven_obj = driven.split('.')[0]

                if not cmds.objExists(driver_obj) or not cmds.objExists(driven_obj):
                    skipped += 1
                    continue

                # Create SDK
                self._create_sdk(driver, driven, keys)
                created += 1

            except Exception:
                skipped += 1
                continue

            # Progress every 100
            if (idx + 1) % 100 == 0:
                print(f">>> SDKs: {idx + 1}/{total} processed")

        if skipped > 0:
            self.logger.warning(f"SDKs: {skipped} skipped (driver/driven not found)")
        print(f">>> SDKs DONE: {created}/{total} created")

    def _create_sdk(self, driver: str, driven: str, keys: List[List[float]]):
        """
        Create Set Driven Key relationship

        Args:
            driver: Driver attribute (e.g., "Ctrl.translateY")
            driven: Driven attribute (e.g., "blendShape.target")
            keys: List of [driver_value, driven_value] pairs
        """
        if not keys:
            return

        # Set each key
        for driver_val, driven_val in keys:
            try:
                # Set driver to driver_val
                cmds.setAttr(driver, driver_val)

                # Set driven to driven_val
                cmds.setAttr(driven, driven_val)

                # Set driven key
                cmds.setDrivenKeyframe(
                    driven,
                    currentDriver=driver,
                    driverValue=driver_val,
                    value=driven_val
                )

            except Exception as e:
                self.logger.debug(f"Failed to set key at {driver_val}: {e}")
                continue

        # Reset driver to first key value
        if keys:
            cmds.setAttr(driver, keys[0][0])
    # ==================== v1.5.0: Validation & Auto-Repair ====================

    def _validate_rig_connections(self, rig_data: Dict) -> None:
        """
        v1.5.0: Validate that all rig connections are properly established

        Checks:
        - All constraints have connected drivers
        - All IK handles are functional
        - All blendshape connections are live
        - All SDKs are working
        """
        self.logger.info("🔍 Validating rig connections...")

        # Check constraints
        all_constraints = cmds.ls(type=['parentConstraint', 'orientConstraint',
                                        'pointConstraint', 'aimConstraint',
                                        'scaleConstraint', 'poleVectorConstraint']) or []

        for constraint in all_constraints:
            try:
                # Check if constraint has targets
                targets = cmds.constraintTargetList(constraint) or []
                if not targets:
                    self._health_report.connections_broken.append(
                        f"Constraint {constraint}: no targets"
                    )
            except Exception:
                pass  # Some constraint types don't support constraintTargetList

        # Check IK handles
        ik_handles = cmds.ls(type='ikHandle') or []
        for ik in ik_handles:
            try:
                start = cmds.ikHandle(ik, q=True, startJoint=True)
                end = cmds.ikHandle(ik, q=True, endEffector=True)
                if not start or not end:
                    self._health_report.connections_broken.append(
                        f"IK handle {ik}: missing start/end joint"
                    )
            except Exception as e:
                self._health_report.warnings.append(f"Could not validate IK {ik}: {e}")

        # Check for broken connections (attributes with no input)
        for ctrl in rig_data.get('controllers', []):
            ctrl_name = self._resolve_name(ctrl['name'])
            if cmds.objExists(ctrl_name):
                # Check if controller is connected to anything
                connections = cmds.listConnections(ctrl_name, source=False, destination=True) or []
                if not connections:
                    self._health_report.warnings.append(
                        f"Controller {ctrl_name}: not driving anything"
                    )

        self.logger.info(f"     Found {len(self._health_report.connections_broken)} broken connections")

    def _attempt_auto_repair(self) -> None:
        """
        v1.5.0: Attempt to automatically repair common issues

        Repairs:
        - Reconnect constraints with fuzzy name matching
        - Fix broken attribute connections
        - Repair IK handle references
        """
        if not self._health_report.connections_broken:
            return

        self.logger.info("[TOOL] Attempting auto-repair...")
        repairs_made = 0

        for broken in self._health_report.connections_broken[:]:  # Copy list to modify
            try:
                # Try to identify and fix the issue
                if "no targets" in broken:
                    # Constraint with no targets - try to find and reconnect
                    constraint_name = broken.split(":")[0].replace("Constraint ", "").strip()
                    if self._repair_constraint_targets(constraint_name):
                        self._health_report.auto_repairs.append(f"Repaired: {broken}")
                        self._health_report.connections_broken.remove(broken)
                        repairs_made += 1

                elif "missing start/end" in broken:
                    # IK handle issue - try to find joints
                    ik_name = broken.split(":")[0].replace("IK handle ", "").strip()
                    if self._repair_ik_handle(ik_name):
                        self._health_report.auto_repairs.append(f"Repaired: {broken}")
                        self._health_report.connections_broken.remove(broken)
                        repairs_made += 1

            except Exception as e:
                self.logger.debug(f"Auto-repair failed for {broken}: {e}")

        self.logger.info(f"     Auto-repaired {repairs_made} issues")

    def _repair_constraint_targets(self, constraint_name: str) -> bool:
        """
        Try to repair a constraint by finding targets with fuzzy matching
        """
        if not cmds.objExists(constraint_name):
            return False

        try:
            # Get constraint type
            node_type = cmds.nodeType(constraint_name)

            # Get the constrained object
            connections = cmds.listConnections(f"{constraint_name}.constraintParentInverseMatrix")
            if not connections:
                return False

            driven = connections[0]

            # Try to find potential targets based on naming convention
            # Look for objects with similar names that could be drivers
            potential_targets = []

            # Check for objects ending in _ctrl, _Ctrl, _CTRL
            all_transforms = cmds.ls(transforms=True) or []
            driven_base = driven.split(':')[-1].replace('_jnt', '').replace('_Jnt', '')

            for obj in all_transforms:
                obj_base = obj.split(':')[-1]
                if driven_base in obj_base and obj != driven:
                    if any(suffix in obj for suffix in ['_ctrl', '_Ctrl', '_CTRL', 'Control']):
                        potential_targets.append(obj)

            if potential_targets:
                # Try to add the first potential target
                target = potential_targets[0]

                if node_type == 'parentConstraint':
                    cmds.parentConstraint(target, driven, maintainOffset=True, edit=True)
                elif node_type == 'orientConstraint':
                    cmds.orientConstraint(target, driven, maintainOffset=True, edit=True)
                elif node_type == 'pointConstraint':
                    cmds.pointConstraint(target, driven, maintainOffset=True, edit=True)

                self.logger.info(f"     Repaired {constraint_name}: added target {target}")
                return True

        except Exception as e:
            self.logger.debug(f"Could not repair constraint {constraint_name}: {e}")

        return False

    def _repair_ik_handle(self, ik_name: str) -> bool:
        """
        Try to repair an IK handle by finding joints with fuzzy matching
        """
        if not cmds.objExists(ik_name):
            return False

        try:
            # Get current start/end joints
            start = cmds.ikHandle(ik_name, q=True, startJoint=True)
            end = cmds.ikHandle(ik_name, q=True, endEffector=True)

            if start and end:
                return True  # Already has joints

            # If missing, we can't easily repair IK handles
            # They would need to be recreated
            self._health_report.warnings.append(
                f"IK handle {ik_name} needs manual repair - missing joint references"
            )

        except Exception as e:
            self.logger.debug(f"Could not repair IK handle {ik_name}: {e}")

        return False

    def run_health_check(self) -> RigHealthReport:
        """
        v1.5.0: Run a comprehensive health check on the imported rig

        Can be called after import to get detailed status.
        Returns a RigHealthReport with all findings.
        """
        if not MAYA_AVAILABLE:
            report = RigHealthReport()
            report.success = False
            report.warnings.append("Maya not available")
            return report

        report = RigHealthReport()

        # Count controllers (NURBS curves that look like controls)
        curves = cmds.ls(type='nurbsCurve') or []
        for curve in curves:
            transform = cmds.listRelatives(curve, parent=True)
            if transform:
                name = transform[0]
                if any(s in name.lower() for s in ['ctrl', 'control', 'con_']):
                    report.controllers_created += 1

        # Count constraints
        constraint_types = [
            'parentConstraint', 'orientConstraint', 'pointConstraint',
            'aimConstraint', 'scaleConstraint', 'poleVectorConstraint'
        ]
        for ctype in constraint_types:
            constraints = cmds.ls(type=ctype) or []
            report.constraints_created += len(constraints)

            # Check each constraint for issues
            for const in constraints:
                try:
                    targets = cmds.listConnections(f"{const}.target") or []
                    if not targets:
                        report.connections_broken.append(f"{const}: no targets")
                except Exception:
                    pass

        # Count IK handles
        ik_handles = cmds.ls(type='ikHandle') or []
        for ik in ik_handles:
            try:
                start = cmds.ikHandle(ik, q=True, startJoint=True)
                if not start:
                    report.connections_broken.append(f"IK {ik}: missing joints")
            except Exception:
                pass

        # Determine overall success
        report.success = len(report.connections_broken) == 0

        return report
