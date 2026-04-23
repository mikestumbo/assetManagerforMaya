# pylint: disable=invalid-name  # Script filename uses UPPER_CASE per Maya pipeline convention
"""
Blendshape Target Cleanup Utility
Automatically hides blendshape targets and duplicate meshes for clean USD export/import.

Integrates with:
- USD Pipeline Creator (pre-export cleanup)
- Asset Manager USD Import (post-import cleanup)

Author: Mike Stumbo
Version: 1.5.0 - Enhanced detection with blendShape node analysis
"""

from typing import Set, Tuple
import maya.cmds as cmds  # type: ignore
import logging

logger = logging.getLogger(__name__)


class BlendshapeTargetCleaner:
    """
    Clean Code: Single Responsibility - Hide blendshape targets and duplicates
    SOLID: Open/Closed - Extensible detection strategies
    """

    def __init__(self, verbose: bool = True):
        """
        Initialize cleaner

        Args:
            verbose: Whether to print detailed output
        """
        self.verbose = verbose
        self.hidden_count = 0
        self.blendshape_targets: Set[str] = set()
        self.duplicate_meshes: Set[str] = set()

    def find_all_blendshape_targets(self) -> Set[str]:
        """
        Find ALL blendshape target meshes using multiple detection strategies.
        OCP: Extensible - add new strategies without modifying this method.

        Returns:
            Set of mesh shape names that are blendshape targets
        """
        targets = set()

        # Strategy 1: Connection-based (existing, for properly connected targets)
        targets.update(self._find_by_connections())

        # Strategy 2: Name-based (new, for scenes where connections fail)
        targets.update(self._find_by_names())

        # Strategy 3: History-based (existing, as fallback)
        targets.update(self._find_by_history())

        return targets

    def _find_by_connections(self) -> Set[str]:
        """Find targets by analyzing blendShape node connections."""
        targets = set()

        blendshape_nodes = cmds.ls(type="blendShape")
        if self.verbose:
            logger.info(f"Found {len(blendshape_nodes)} blendShape nodes")

        for bs_node in blendshape_nodes:
            try:
                weight_count = cmds.blendShape(bs_node, query=True, weightCount=True)
                if weight_count:
                    for i in range(weight_count):
                        target_names = cmds.blendShape(bs_node, query=True, target=True)
                        if target_names and i < len(target_names):
                            target_name = target_names[i]
                            potential_targets = cmds.ls(f"*{target_name}*", type="transform")

                            for transform in potential_targets:
                                shapes = cmds.listRelatives(transform, shapes=True, fullPath=True)
                                if shapes:
                                    for shape in shapes:
                                        connections = cmds.listConnections(
                                            shape, source=True, destination=False
                                        )
                                        if connections and bs_node in connections:
                                            targets.add(shape)
                                            if self.verbose:
                                                logger.debug(
                                                    f"Found blendShape target by connection: {shape}"
                                                )
            except Exception as e:
                logger.warning(f"Error analyzing blendShape node {bs_node}: {e}")

        return targets

    def _find_by_names(self) -> Set[str]:
        """Find targets by name patterns (fallback for connection failures)."""
        import re

        targets = set()
        all_meshes = cmds.ls(type="mesh", long=True)

        # Common blendshape suffixes/patterns
        patterns = [
            r"Shape$",
            r"_Shape$",
            r"ShapeDeformed$",
            r"_deformed$",
            r"_target$",
            r"_blend$",
            r"_morph$",
            r"Blend\d+$",
            r"_.*_$",
        ]

        for mesh in all_meshes:
            short_name = mesh.split("|")[-1].split(":")[-1]
            if any(re.search(pattern, short_name, re.IGNORECASE) for pattern in patterns):
                # Verify it's not a main mesh (has corresponding base mesh)
                base_name = re.sub(r"Shape.*$", "", short_name)
                if cmds.ls(f"*{base_name}*", type="transform"):
                    targets.add(mesh)
                    if self.verbose:
                        logger.debug(f"Found blendshape target by name: {short_name}")

        return targets

    def _find_by_history(self) -> Set[str]:
        """Find targets by checking mesh history for blendShape connections."""
        targets = set()
        all_meshes = cmds.ls(type="mesh", long=True)

        for mesh in all_meshes:
            try:
                history = cmds.listHistory(mesh, pruneDagObjects=True)
                if history:
                    for node in history:
                        if cmds.nodeType(node) == "blendShape":
                            connections = cmds.listConnections(
                                mesh, plugs=True, source=False, destination=True
                            )
                            if connections:
                                for conn in connections:
                                    if (
                                        "inputTarget" in conn
                                        and cmds.nodeType(conn.split(".")[0]) == "blendShape"
                                    ):
                                        targets.add(mesh)
                                        if self.verbose:
                                            logger.debug(
                                                f"Found blendShape target via history: {mesh}"
                                            )
                                        break
            except Exception as e:
                logger.warning(f"Error checking history for {mesh}: {e}")

        return targets

    def find_duplicate_meshes(self) -> Set[str]:
        """
        Find duplicate meshes based on name patterns.
        More robust detection than simple name matching.

        Returns:
            Set of duplicate mesh shape names to hide
        """
        import re

        duplicates = set()
        all_meshes = cmds.ls(type="mesh", long=True)

        # Track meshes by base name
        base_name_map = {}

        for mesh_shape in all_meshes:
            # Skip if already intermediate
            if cmds.getAttr(f"{mesh_shape}.intermediateObject"):
                continue

            # Get transform
            transforms = cmds.listRelatives(mesh_shape, parent=True, fullPath=True)
            if not transforms:
                continue

            transform = transforms[0]
            short_name = transform.split("|")[-1].split(":")[-1]

            # Extract base name with multiple strategies
            base_name = short_name

            # Remove common suffixes
            for suffix in ["Shape", "_Geo", "_geo", "_GEO", "_mesh", "_Mesh", "Orig"]:
                base_name = base_name.replace(suffix, "")

            # Remove trailing numbers (Body1, Body2, etc.)
            base_name = re.sub(r"\d+$", "", base_name)

            # Remove common pattern indicators
            base_name = re.sub(r"_copy\d*$", "", base_name, flags=re.IGNORECASE)
            base_name = re.sub(r"_duplicate\d*$", "", base_name, flags=re.IGNORECASE)

            # Check for FK/IK variants
            is_fk_ik = "_FK" in short_name or "_IK" in short_name

            # Track by base name
            if base_name in base_name_map:
                # This is a duplicate!
                duplicates.add(mesh_shape)
                if self.verbose:
                    logger.debug(f"Found duplicate: {short_name} (base: {base_name})")
            elif is_fk_ik:
                # FK/IK meshes are always considered duplicates
                duplicates.add(mesh_shape)
                if self.verbose:
                    logger.debug(f"Found FK/IK mesh: {short_name}")
            else:
                # First time seeing this base name
                base_name_map[base_name] = mesh_shape

        return duplicates

    def hide_targets(self, target_shapes: Set[str]) -> int:
        """
        Hide mesh shapes by setting them as intermediate objects.

        Args:
            target_shapes: Set of mesh shape names to hide

        Returns:
            Number of shapes successfully hidden
        """
        hidden = 0

        for shape in target_shapes:
            try:
                # Check if already intermediate
                if cmds.getAttr(f"{shape}.intermediateObject"):
                    continue

                # Set as intermediate object
                cmds.setAttr(f"{shape}.intermediateObject", True)
                hidden += 1

                if self.verbose:
                    short_name = shape.split("|")[-1]
                    logger.info(f"Hidden: {short_name}")

            except Exception as e:
                logger.warning(f"Failed to hide {shape}: {e}")

        return hidden

    def cleanup(self) -> Tuple[int, int]:
        """
        Run complete cleanup: find and hide all blendshape targets and duplicates.

        Returns:
            Tuple of (blendshape_count, duplicate_count)
        """
        if self.verbose:
            print("\n" + "=" * 70)
            print("[TOOL] BLENDSHAPE TARGET & DUPLICATE MESH CLEANUP")
            print("=" * 70)

        # Find all blendshape targets
        self.blendshape_targets = self.find_all_blendshape_targets()
        if self.verbose:
            print(f"\n📊 Found {len(self.blendshape_targets)} blendShape target meshes")

        # Find duplicate meshes
        self.duplicate_meshes = self.find_duplicate_meshes()
        if self.verbose:
            print(f"📊 Found {len(self.duplicate_meshes)} duplicate/FK/IK meshes")

        # Hide blendshape targets
        bs_hidden = self.hide_targets(self.blendshape_targets)

        # Hide duplicates
        dup_hidden = self.hide_targets(self.duplicate_meshes)

        if self.verbose:
            print(f"\n[OK] Hidden {bs_hidden} blendShape targets")
            print(f"[OK] Hidden {dup_hidden} duplicate/FK/IK meshes")
            print("\n" + "=" * 70)
            print(f"[OK] TOTAL HIDDEN: {bs_hidden + dup_hidden} meshes")
            print("=" * 70 + "\n")

        return bs_hidden, dup_hidden


def cleanup_blendshapes_for_export() -> Tuple[int, int]:
    """
    Public API: Cleanup blendshapes before USD export.
    Called by USD Pipeline Creator.

    Returns:
        Tuple of (blendshape_count, duplicate_count)
    """
    print("[TOOL] BLENDSHAPE CLEANUP: Starting cleanup_blendshapes_for_export()")
    cleaner = BlendshapeTargetCleaner(verbose=True)
    result = cleaner.cleanup()
    print(
        f"[TOOL] BLENDSHAPE CLEANUP: cleanup_blendshapes_for_export() completed with result: {result}"
    )
    return result


def cleanup_blendshapes_for_import() -> Tuple[int, int]:
    """
    Public API: Cleanup blendshapes after USD import.
    Called by Asset Manager import system.

    Returns:
        Tuple of (blendshape_count, duplicate_count)
    """
    cleaner = BlendshapeTargetCleaner(verbose=True)
    return cleaner.cleanup()


def hide_blendshape_targets():
    """Legacy function name for backward compatibility"""
    return cleanup_blendshapes_for_export()


# Run cleanup if executed directly
if __name__ == "__main__":
    pass
