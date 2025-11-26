# -*- coding: utf-8 -*-
"""
USD View Export Bridge
Bridge to external USD tools for maximum compatibility

This module provides integration with industry-standard
USD tools like Pixar's USD View for robust conversion.

Author: Mike Stumbo
Version: 1.0.0
Date: November 2025
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class UsdViewBridge:
    """
    Bridge to USD View for USD file inspection and export

    Uses Pixar's USD View command-line tools for validation
    and format conversion.

    Clean Code: Single Responsibility - USD View integration
    """

    def __init__(self):
        """Initialize USD View bridge"""
        self.logger = logging.getLogger(__name__)
        self.usdview_path = None
        self.usdcat_path = None
        self._detect_usdview()

    def _detect_usdview(self) -> bool:
        """
        Detect USD View/tools installation

        Returns:
            True if USD tools found
        """
        # USD tools are usually in Python environment or system path
        try:
            result = subprocess.run(
                ["usdcat", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.usdcat_path = "usdcat"
                self.logger.info("✅ USD command-line tools detected")
                return True
        except Exception:
            pass

        self.logger.warning("⚠️ USD command-line tools not detected")
        return False

    def is_available(self) -> bool:
        """Check if USD tools are available"""
        return self.usdcat_path is not None

    def validate_usd_file(self, usd_path: Path) -> Dict[str, Any]:
        """
        Validate USD file using usdcat

        Args:
            usd_path: Path to USD file

        Returns:
            Validation results
        """
        if not self.is_available():
            return {'valid': False, 'error': 'USD tools not available'}

        try:
            result = subprocess.run(
                ["usdcat", "--validate", str(usd_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            return {
                'valid': result.returncode == 0,
                'output': result.stdout,
                'errors': result.stderr if result.returncode != 0 else None
            }

        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def convert_format(
        self,
        usd_path: Path,
        output_format: str = 'usda'
    ) -> Optional[Path]:
        """
        Convert USD to different format (usda, usdc, usdz)

        Args:
            usd_path: Input USD file
            output_format: Target format ('usda', 'usdc', 'usdz')

        Returns:
            Path to converted file or None
        """
        if not self.is_available():
            return None

        try:
            output_path = usd_path.parent / f"{usd_path.stem}.{output_format}"

            result = subprocess.run(
                ["usdcat", "-o", str(output_path), str(usd_path)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and output_path.exists():
                self.logger.info(f"✅ Format conversion successful: {output_path}")
                return output_path
            else:
                self.logger.error(f"Format conversion failed: {result.stderr}")
                return None

        except Exception as e:
            self.logger.error(f"Format conversion error: {e}")
            return None

# Singleton instances
_usdview_bridge = None


def get_usdview_bridge() -> UsdViewBridge:
    """Get singleton USD View bridge instance"""
    global _usdview_bridge
    if _usdview_bridge is None:
        _usdview_bridge = UsdViewBridge()
    return _usdview_bridge
