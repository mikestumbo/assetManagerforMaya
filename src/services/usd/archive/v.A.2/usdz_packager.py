"""USDZ Packager - Bundle USD + MRIG into single package

Author: Mike Stumbo
Version: 1.5.0 - Single-file distribution for USD+mrig workflows

Clean Code: Single Responsibility - Package multiple files into USDZ
Disney/Pixar Critical: USDZ is the standard format for AR/mobile USD delivery

The USDZ format is essentially a ZIP archive with:
- The main USD file (uncompressed, for streaming)
- Supporting files (textures, .mrig, etc.)
- Strict file ordering requirements per USD spec
"""

import logging
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class UsdzPackager:
    """Package USD + supporting files (including .mrig) into USDZ format

    USDZ Spec Notes:
    - Files must be stored uncompressed (no compression)
    - The root USD file must be first in the archive
    - All asset references should be relative paths

    Usage:
        packager = UsdzPackager()
        success = packager.create_package(
            output_path=Path("character.usdz"),
            usd_file=Path("character.usda"),
            mrig_file=Path("character.mrig"),
            additional_files=[texture_path1, texture_path2]
        )
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_package(
        self,
        output_path: Path,
        usd_file: Path,
        mrig_file: Optional[Path] = None,
        rig_file: Optional[Path] = None,  # v2.0: Maya rig file (.mb/.ma)
        additional_files: Optional[List[Path]] = None,
        include_textures: bool = True
    ) -> Tuple[bool, str]:
        """Create USDZ package with USD and supporting files

        Args:
            output_path: Output .usdz file path
            usd_file: Main USD file (.usda or .usdc)
            mrig_file: Optional legacy rig data file (.mrig)
            rig_file: v2.0: Maya rig file (.rig.mb or .rig.ma) - preferred
            additional_files: Optional list of additional files (textures, etc.)
            include_textures: Whether to include referenced textures

        Returns:
            (success, message) tuple
        """
        try:
            # Validate inputs
            if not usd_file.exists():
                return False, f"USD file not found: {usd_file}"

            if mrig_file and not mrig_file.exists():
                return False, f"MRIG file not found: {mrig_file}"

            if rig_file and not rig_file.exists():
                return False, f"Rig file not found: {rig_file}"

            # Ensure output has .usdz extension
            if output_path.suffix.lower() != '.usdz':
                output_path = output_path.with_suffix('.usdz')

            # Build file list (order matters - root USD first!)
            files_to_package: List[Tuple[Path, str]] = []

            # 1. Root USD file (must be first in archive)
            usd_name = usd_file.name
            files_to_package.append((usd_file, usd_name))

            # 2. v2.0: Rig file (.rig.mb or .rig.ma) - preferred format
            if rig_file and rig_file.exists():
                rig_name = rig_file.name
                files_to_package.append((rig_file, rig_name))
                self.logger.info(f"[PACKAGE] Including rig file: {rig_name}")

            # 3. Legacy MRIG file (companion rig data) - optional
            if mrig_file and mrig_file.exists():
                mrig_name = mrig_file.name
                files_to_package.append((mrig_file, mrig_name))
                self.logger.info(f"[PACKAGE] Including .mrig file: {mrig_name}")

                # 3b. Controllers file - check .mb first (faster), then .ma for backwards compat
                # Use parent/stem to get base path without .mrig suffix
                base_path = mrig_file.parent / mrig_file.stem
                controllers_mb = base_path.with_suffix('.controllers.mb')
                controllers_ma = base_path.with_suffix('.controllers.ma')
                if controllers_mb.exists():
                    files_to_package.append((controllers_mb, controllers_mb.name))
                    self.logger.info(f"[PACKAGE] Including controllers .mb file: {controllers_mb.name}")
                elif controllers_ma.exists():
                    files_to_package.append((controllers_ma, controllers_ma.name))
                    self.logger.info(f"[PACKAGE] Including controllers .ma file: {controllers_ma.name}")

            # 3. Additional files (textures, etc.)
            if additional_files:
                for file_path in additional_files:
                    if file_path.exists():
                        files_to_package.append((file_path, file_path.name))

            # 4. Auto-discover textures from USD if requested
            if include_textures:
                texture_paths = self._find_referenced_textures(usd_file)
                for tex_path in texture_paths:
                    if tex_path.exists():
                        # Store textures in a 'textures/' subfolder in the archive
                        archive_name = f"textures/{tex_path.name}"
                        files_to_package.append((tex_path, archive_name))

            # Create USDZ package (ZIP with no compression per spec)
            with zipfile.ZipFile(
                output_path,
                'w',
                compression=zipfile.ZIP_STORED  # USDZ requires uncompressed!
            ) as usdz:
                for source_path, archive_name in files_to_package:
                    usdz.write(source_path, archive_name)
                    self.logger.debug(f"  Added: {archive_name}")

            # Report success
            file_count = len(files_to_package)
            size_kb = output_path.stat().st_size / 1024

            self.logger.info(
                f"[OK] USDZ package created: {output_path.name} "
                f"({file_count} files, {size_kb:.1f} KB)"
            )

            return True, f"Package created with {file_count} files ({size_kb:.1f} KB)"

        except Exception as e:
            error_msg = f"USDZ packaging failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    def extract_package(
        self,
        usdz_path: Path,
        output_dir: Optional[Path] = None
    ) -> Tuple[bool, dict]:
        """Extract USDZ package to directory

        Args:
            usdz_path: Path to .usdz file
            output_dir: Optional output directory (defaults to temp dir)

        Returns:
            (success, info_dict) where info_dict contains:
                - 'usd_file': Path to extracted USD file
                - 'mrig_file': Path to extracted .mrig file (if present)
                - 'controllers_file': Path to extracted .controllers.mb or .ma file (if present)
                - 'textures': List of extracted texture paths
                - 'extract_dir': Directory where files were extracted
        """
        try:
            if not usdz_path.exists():
                return False, {'error': f"USDZ file not found: {usdz_path}"}

            # Create output directory
            if output_dir is None:
                output_dir = Path(tempfile.mkdtemp(prefix="usdz_extract_"))
            else:
                output_dir.mkdir(parents=True, exist_ok=True)

            # Extract all files
            usd_file = None
            mrig_file = None
            controllers_file = None  # Can be .mb or .ma (legacy)
            rig_file = None  # v2.0: .rig.mb or .rig.ma
            textures = []

            with zipfile.ZipFile(usdz_path, 'r') as usdz:
                file_list = usdz.namelist()

                for file_name in file_list:
                    # Extract file
                    extracted_path = output_dir / file_name
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)

                    with usdz.open(file_name) as src:
                        with open(extracted_path, 'wb') as dst:
                            dst.write(src.read())

                    # Categorize extracted file
                    suffix = extracted_path.suffix.lower()
                    if suffix in {'.usd', '.usda', '.usdc'}:
                        usd_file = extracted_path
                    elif suffix == '.mrig':
                        mrig_file = extracted_path
                    elif '.rig.mb' in file_name.lower() or '.rig.ma' in file_name.lower():
                        # v2.0: New rig file format
                        rig_file = extracted_path
                    elif suffix in {'.mb', '.ma'} or '.controllers.' in file_name:
                        # Legacy controllers file
                        controllers_file = extracted_path
                    elif suffix in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr', '.tex'}:
                        textures.append(extracted_path)

            info = {
                'usd_file': usd_file,
                'mrig_file': mrig_file,
                'controllers_file': controllers_file,  # Legacy .controllers.mb or .ma
                'rig_file': rig_file,  # v2.0: .rig.mb or .rig.ma
                'textures': textures,
                'extract_dir': output_dir,
                'file_count': len(file_list)
            }

            self.logger.info(
                f"[OK] USDZ extracted: {len(file_list)} files to {output_dir}"
            )
            if mrig_file:
                self.logger.info(f"   [SELECT] Found .mrig file: {mrig_file.name}")
            if rig_file:
                self.logger.info(f"   🎮 Found rig file (v2.0): {rig_file.name}")
            elif controllers_file:
                self.logger.info(f"   🎮 Found controllers file (legacy): {controllers_file.name}")

            return True, info

        except Exception as e:
            error_msg = f"USDZ extraction failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, {'error': error_msg}

    def get_package_info(self, usdz_path: Path) -> dict:
        """Get info about USDZ package without extracting

        Args:
            usdz_path: Path to .usdz file

        Returns:
            Dictionary with package info:
                - 'files': List of file names in package
                - 'has_mrig': Whether .mrig file is included
                - 'has_controllers': Whether .controllers.mb or .ma file is included
                - 'has_textures': Whether textures are included
                - 'usd_file': Name of the root USD file
                - 'size_bytes': Total package size
        """
        try:
            if not usdz_path.exists():
                return {'error': f"File not found: {usdz_path}"}

            with zipfile.ZipFile(usdz_path, 'r') as usdz:
                file_list = usdz.namelist()

                info = {
                    'files': file_list,
                    'has_mrig': any(f.endswith('.mrig') for f in file_list),
                    'has_controllers': any(
                        '.controllers.' in f or f.endswith(('.mb', '.ma'))
                        for f in file_list
                    ),
                    'has_textures': any(
                        f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.exr'))
                        for f in file_list
                    ),
                    'usd_file': next(
                        (f for f in file_list if f.endswith(('.usd', '.usda', '.usdc'))),
                        None
                    ),
                    'size_bytes': usdz_path.stat().st_size
                }

                return info

        except Exception as e:
            return {'error': str(e)}

    def _find_referenced_textures(self, usd_file: Path) -> List[Path]:
        """Find texture files referenced in USD

        Args:
            usd_file: Path to USD file

        Returns:
            List of paths to referenced texture files
        """
        textures = []

        try:
            # Try to use pxr USD library if available
            try:
                from pxr import Usd

                stage = Usd.Stage.Open(str(usd_file))
                if stage:
                    # Look for asset-valued attributes
                    for prim in stage.Traverse():
                        for attr in prim.GetAttributes():
                            if attr.GetTypeName() == 'asset':
                                try:
                                    asset_path = attr.Get()
                                    if asset_path:
                                        resolved = asset_path.resolvedPath
                                        if resolved and Path(resolved).exists():
                                            textures.append(Path(resolved))
                                except Exception:
                                    pass

            except ImportError:
                # Fall back to simple text parsing for ASCII USD files
                if usd_file.suffix == '.usda':
                    content = usd_file.read_text(errors='ignore')

                    # Look for @path@ asset references
                    import re
                    asset_pattern = r'@([^@]+)@'
                    matches = re.findall(asset_pattern, content)

                    for match in matches:
                        # Check if it's a texture file
                        if any(match.lower().endswith(ext)
                               for ext in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr')):
                            # Resolve relative to USD file
                            tex_path = usd_file.parent / match
                            if tex_path.exists():
                                textures.append(tex_path)

        except Exception as e:
            self.logger.warning(f"Could not scan for textures: {e}")

        return textures


def create_usdz_with_mrig(
    usd_file: Path,
    mrig_file: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> Tuple[bool, str, Optional[Path]]:
    """Convenience function to create USDZ package with .mrig bundled

    Args:
        usd_file: Path to USD file (.usda or .usdc)
        mrig_file: Path to .mrig file (auto-detected if None)
        output_path: Output .usdz path (auto-generated if None)

    Returns:
        (success, message, output_path) tuple
    """
    # Auto-detect mrig file if not provided
    if mrig_file is None:
        mrig_file = usd_file.with_suffix('.mrig')
        if not mrig_file.exists():
            mrig_file = None

    # Auto-generate output path if not provided
    if output_path is None:
        output_path = usd_file.with_suffix('.usdz')

    packager = UsdzPackager()
    success, message = packager.create_package(
        output_path=output_path,
        usd_file=usd_file,
        mrig_file=mrig_file
    )

    return success, message, output_path if success else None


def extract_usdz_with_mrig(
    usdz_path: Path,
    output_dir: Optional[Path] = None
) -> Tuple[bool, Optional[Path], Optional[Path]]:
    """Convenience function to extract USDZ and get USD + mrig paths

    Args:
        usdz_path: Path to .usdz file
        output_dir: Optional extraction directory

    Returns:
        (success, usd_path, mrig_path) tuple
    """
    packager = UsdzPackager()
    success, info = packager.extract_package(usdz_path, output_dir)

    if success:
        return True, info.get('usd_file'), info.get('mrig_file')
    else:
        return False, None, None
