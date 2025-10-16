# -*- coding: utf-8 -*-
"""
Import Utilities - Robust Import System
Handles different execution contexts (Maya plugin, standalone, testing)

Author: Mike Stumbo
Clean Code: Single Responsibility for import resolution
"""

import sys
import os
from pathlib import Path
from typing import Any, Optional


class ImportHelper:
    """
    Import Helper - Single Responsibility for handling import resolution
    Follows Open/Closed Principle: extensible for new execution contexts
    """
    
    @staticmethod
    def setup_src_path() -> Path:
        """
        Setup src path for imports - works in different contexts
        Note: Caller responsible for path restoration
        
        Returns:
            Path to src directory
        """
        # Try to find src directory from current file location
        current_file = Path(__file__).resolve()
        
        # Look for src directory in parent directories
        for parent in current_file.parents:
            src_path = parent / "src"
            if src_path.exists():
                # Temporarily add to path (caller should restore)
                if str(src_path) not in sys.path:
                    sys.path.insert(0, str(src_path))
                return src_path
        
        # Fallback: assume we're in the project root
        project_root = Path.cwd()
        src_path = project_root / "src"
        if src_path.exists():
            # Temporarily add to path (caller should restore)
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
            return src_path
        
        raise ImportError("Could not locate src directory for imports")
    
    @staticmethod
    def safe_import(module_name: str, fallback_value: Any = None) -> Optional[Any]:
        """
        Safely import module with fallback - Maya security compliant
        
        Args:
            module_name: Module to import (must be trusted/allowlisted)
            fallback_value: Value to return if import fails
            
        Returns:
            Imported module or fallback value
        """
        # Security: Validate module name to prevent code injection
        if not module_name or not isinstance(module_name, str):
            print(f"❌ Invalid module name: {module_name}")
            return fallback_value
            
        # Security: Allow only specific module patterns for our plugin
        allowed_prefixes = ['core.', 'ui.', 'services.', 'integrations.', 'config.']
        if not any(module_name.startswith(prefix) for prefix in allowed_prefixes):
            if module_name not in ['core', 'ui', 'services', 'integrations', 'config']:
                print(f"❌ Module not in allowlist: {module_name}")
                return fallback_value
        
        original_path = sys.path[:]
        try:
            ImportHelper.setup_src_path()
            
            # Use importlib instead of __import__ for security
            import importlib
            try:
                module = importlib.import_module(module_name)
                return module
            except ImportError:
                # Fallback to relative import if absolute fails
                if '.' in module_name:
                    parent_module = module_name.rsplit('.', 1)[0]
                    child_name = module_name.rsplit('.', 1)[1]
                    parent = importlib.import_module(parent_module)
                    return getattr(parent, child_name, fallback_value)
                return fallback_value
            
        except ImportError as e:
            print(f"⚠️ Import failed for {module_name}: {e}")
            return fallback_value
        finally:
            # Restore original path for security
            sys.path[:] = original_path
    
    @staticmethod
    def get_class_from_module(module_path: str, class_name: str) -> Optional[type]:
        """
        Get class from module path safely
        
        Args:
            module_path: Path to module (e.g., 'services.thumbnail_service_impl')
            class_name: Name of class to retrieve
            
        Returns:
            Class type or None if not found
        """
        try:
            module = ImportHelper.safe_import(module_path)
            if module and hasattr(module, class_name):
                return getattr(module, class_name)
            return None
        except Exception as e:
            print(f"❌ Failed to get class {class_name} from {module_path}: {e}")
            return None


# Note: No global path modification for security
# Path setup is done per-operation with restoration
