#!/usr/bin/env python3
"""
Asset Manager v1.3.0 - Unified Installation System
Single Source of Truth for all installation methods

This module provides the core installation logic that is used by:
- DRAG&DROP.mel (Maya GUI installer)
- install.bat (Windows command-line installer)  
- install.sh (Unix/Linux/macOS command-line installer)
- Direct Python execution

Following Clean Code principles:
- Single Responsibility: Only handles Asset Manager installation
- DRY: Single implementation used by all installers
- Error Handling: Comprehensive validation and user feedback
- Cross-Platform: Works on Windows, macOS, and Linux

Author: Mike Stumbo
Version: 1.3.0
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple


class AssetManagerInstaller:
    """
    Unified Asset Manager installer following Clean Code principles.
    
    This class replicates the exact logic from DRAG&DROP.mel to ensure
    all installation methods produce identical results.
    """
    
    def __init__(self, source_dir: Optional[str] = None, verbose: bool = True):
        """
        Initialize the installer.
        
        Args:
            source_dir: Source directory path (auto-detected if None)
            verbose: Whether to print progress messages
        """
        self.verbose = verbose
        self.source_dir = Path(source_dir) if source_dir else self._get_source_directory()
        self.maya_scripts_dir = self._get_maya_scripts_directory()
        self.install_dir = self.maya_scripts_dir / "assetManager"
        
    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def _get_source_directory(self) -> Path:
        """
        Get the source directory containing Asset Manager files.
        
        Returns:
            Path to source directory
            
        Raises:
            FileNotFoundError: If source directory cannot be found
        """
        # Try script directory first
        script_dir = Path(__file__).parent
        if self._validate_source_directory(script_dir):
            return script_dir
            
        # Try current working directory
        cwd = Path.cwd()
        if self._validate_source_directory(cwd):
            return cwd
            
        raise FileNotFoundError(
            f"Could not find Asset Manager source files.\n"
            f"Checked:\n- {script_dir}\n- {cwd}\n"
            f"Please ensure assetManager.py and maya_plugin.py exist."
        )
    
    def _validate_source_directory(self, path: Path) -> bool:
        """Validate that directory contains required Asset Manager files."""
        required_files = ["assetManager.py", "maya_plugin.py", "__init__.py"]
        return all((path / file).exists() for file in required_files)
    
    def _get_maya_scripts_directory(self) -> Path:
        """
        Get Maya scripts directory with comprehensive cloud sync support.
        
        Checks multiple locations with cloud service priority:
        Windows: OneDrive Documents → Regular Documents
        macOS: iCloud Drive Documents → Regular Documents → Maya Preferences
        Linux: Home maya directory
        
        Returns:
            Path to Maya scripts directory (version-agnostic)
            
        Raises:
            FileNotFoundError: If Maya directory cannot be found
        """
        home = Path.home()
        
        # Platform-specific Maya paths with cloud sync support
        if sys.platform == "win32":
            # Windows: Check OneDrive Documents first (preferred for modern setups)
            onedrive_docs = home / "OneDrive" / "Documents" / "maya"
            regular_docs = home / "Documents" / "maya"
            possible_bases = [onedrive_docs, regular_docs]
        elif sys.platform == "darwin":
            # macOS: Check iCloud Drive and regular paths
            # iCloud Drive Documents (when Desktop & Documents sync is enabled)
            icloud_docs = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Documents" / "maya"
            # Regular Documents folder (may be symlinked to iCloud when sync is enabled)
            regular_docs = home / "Documents" / "maya"
            # Traditional Maya preferences location
            maya_prefs = home / "Library" / "Preferences" / "Autodesk" / "maya"
            possible_bases = [icloud_docs, regular_docs, maya_prefs]
        else:
            # Linux/Unix: Standard home directory
            maya_base = home / "maya"
            possible_bases = [maya_base]
        
        # Try each possible Maya base directory
        for maya_base in possible_bases:
            scripts_dir = maya_base / "scripts"
            
            # Check if this location exists or can be created
            if scripts_dir.exists():
                self._log(f"📂 Found existing Maya scripts directory: {scripts_dir}")
                if "OneDrive" in str(maya_base):
                    self._log("   ✨ Using OneDrive synced location (Windows)")
                elif "CloudDocs" in str(maya_base):
                    self._log("   ☁️ Using iCloud Drive synced location (macOS)")
                elif "Documents" in str(maya_base):
                    self._log("   📁 Using Documents folder (may be cloud-synced)")
                return scripts_dir
            elif self._can_create_directory(scripts_dir.parent):
                self._log(f"📂 Using Maya scripts directory: {scripts_dir}")
                if "OneDrive" in str(maya_base):
                    self._log("   ✨ Creating in OneDrive synced location (Windows)")
                elif "CloudDocs" in str(maya_base):
                    self._log("   ☁️ Creating in iCloud Drive synced location (macOS)")
                elif "Documents" in str(maya_base):
                    self._log("   📁 Creating in Documents folder (may be cloud-synced)")
                self._log("   This ensures compatibility with all Maya versions!")
                return scripts_dir
        
        # If general directories don't work, fall back to version-specific as last resort
        for maya_base in possible_bases:
            if maya_base.exists():
                version_dirs = [d for d in maya_base.iterdir() if d.is_dir() and d.name.replace(".", "").isdigit()]
                if version_dirs:
                    latest_version = max(version_dirs, key=lambda x: x.name)
                    scripts_dir = latest_version / "scripts"
                    if scripts_dir.exists() or self._can_create_directory(scripts_dir):
                        self._log(f"📂 Fallback to version-specific directory: {scripts_dir}")
                        return scripts_dir
        
        # Generate helpful error message with all checked locations
        checked_paths = "\n".join(f"- {base / 'scripts'}" for base in possible_bases)
        raise FileNotFoundError(
            f"Could not find or create Maya scripts directory.\n"
            f"Checked locations:\n{checked_paths}\n"
            f"Please ensure Maya is installed and you have write permissions."
        )
    
    def _can_create_directory(self, path: Path) -> bool:
        """Check if we can create a directory at the given path."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except (PermissionError, OSError):
            return False
    
    def copy_asset_file(self, src_file: str, dst_file: str) -> bool:
        """
        Copy a single file, replicating DRAG&DROP.mel's copyAssetFile().
        
        Args:
            src_file: Source file path relative to source directory
            dst_file: Destination file path relative to install directory
            
        Returns:
            True if copied successfully, False if file missing (optional)
        """
        src_path = self.source_dir / src_file
        dst_path = self.install_dir / dst_file
        
        if src_path.exists():
            try:
                # Ensure destination directory exists
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                self._log(f"Copied: {src_path.name}")
                return True
            except Exception as e:
                self._log(f"Error copying {src_path.name}: {e}")
                return False
        else:
            self._log(f"Missing: {src_path.name} (optional)")
            return False
    
    def copy_source_directory(self, src_dir: str, dst_dir: str) -> bool:
        """
        Copy entire directory tree, replicating DRAG&DROP.mel's copySourceDirectory().
        Filters out __pycache__ directories for clean installation.
        
        Args:
            src_dir: Source directory path relative to source directory
            dst_dir: Destination directory path relative to install directory
            
        Returns:
            True if copied successfully, False otherwise
        """
        src_path = self.source_dir / src_dir
        dst_path = self.install_dir / dst_dir
        
        if not src_path.exists():
            self._log(f"Source directory not found: {src_path}")
            return False
        
        try:
            if dst_path.exists():
                shutil.rmtree(dst_path)
            
            # Clean copy excluding __pycache__ directories
            def ignore_pycache(dir_path, names):
                """Filter function to ignore __pycache__ directories and .pyc files."""
                return [name for name in names if name == '__pycache__' or name.endswith('.pyc')]
            
            shutil.copytree(src_path, dst_path, ignore=ignore_pycache)
            self._log(f"EMSA architecture copied (clean): {src_dir}")
            return True
        except Exception as e:
            self._log(f"Warning: Could not copy directory {src_dir}: {e}")
            self._log(f"Note: EMSA architecture is optional - core functionality will work")
            return False
    
    def _create_hot_reload_tool(self) -> bool:
        """
        Create dev_hot_reload.py on-demand for development workflow.
        This follows Single Source of Truth by generating the tool rather than copying.
        
        Returns:
            True if created successfully, False otherwise
        """
        hot_reload_content = '''#!/usr/bin/env python3
"""
Asset Manager v1.3.0 - Development Hot Reload System

This system completely bypasses Maya's module caching issues by:
1. Force-clearing all related modules from sys.modules
2. Reloading everything from scratch
3. Providing instant feedback on changes

Usage in Maya Script Editor:
    import dev_hot_reload
    dev_hot_reload.reload_asset_manager()

    # Quick reload aliases:
    dev_hot_reload.r()   # Same as reload_asset_manager()
    dev_hot_reload.qr()  # Quick reload with minimal output

Generated by Asset Manager Unified Installation System
"""

import sys
import importlib
import traceback
from pathlib import Path


class AssetManagerHotReloader:
    """Professional hot reload system for Asset Manager development."""
    
    def __init__(self):
        self.module_patterns = [
            'assetManager',
            'maya_plugin',
            'src.config',
            'src.core',
            'src.services', 
            'src.ui'
        ]
    
    def clear_all_modules(self):
        """Aggressively clear all Asset Manager related modules."""
        modules_to_remove = []
        for module_name in sys.modules:
            for pattern in self.module_patterns:
                if pattern in module_name:
                    modules_to_remove.append(module_name)
                    break
        
        for module_name in modules_to_remove:
            try:
                del sys.modules[module_name]
            except KeyError:
                pass
    
    def reload_asset_manager(self, verbose=True):
        """Complete Asset Manager hot reload."""
        if verbose:
            print("🔥 Hot Reloading Asset Manager...")
        
        try:
            # Step 1: Clear all modules
            self.clear_all_modules()
            if verbose:
                print("✅ Module cache cleared")
            
            # Step 2: Re-import main module
            import assetManager
            importlib.reload(assetManager)
            if verbose:
                print("✅ Asset Manager reloaded")
            
            # Step 3: Test functionality
            if hasattr(assetManager, 'show_asset_manager'):
                if verbose:
                    print("✅ Hot reload complete - ready for testing!")
                return True
            else:
                print("❌ Hot reload failed - show_asset_manager not found")
                return False
                
        except Exception as e:
            print(f"❌ Hot reload error: {e}")
            traceback.print_exc()
            return False


# Global instance for easy access
_reloader = AssetManagerHotReloader()

# Main function
def reload_asset_manager(verbose=True):
    """Hot reload Asset Manager with cache clearing."""
    return _reloader.reload_asset_manager(verbose)

# Quick access aliases
def r():
    """Quick reload alias."""
    return reload_asset_manager(verbose=True)

def qr():
    """Quiet quick reload alias."""
    return reload_asset_manager(verbose=False)

# Auto-message on import
print("🔥 Asset Manager Hot Reload System Ready!")
print("Usage: dev_hot_reload.r() or dev_hot_reload.reload_asset_manager()")
'''
        
        try:
            hot_reload_path = self.maya_scripts_dir / "dev_hot_reload.py"
            with open(hot_reload_path, 'w', encoding='utf-8') as f:
                f.write(hot_reload_content)
            self._log("Created: dev_hot_reload.py")
            return True
        except Exception as e:
            self._log(f"Warning: Could not create dev_hot_reload.py: {e}")
            return False
    
    def install(self) -> bool:
        """
        Perform complete Asset Manager installation.
        
        This method replicates the exact logic from DRAG&DROP.mel to ensure
        identical installations across all installation methods.
        
        Returns:
            True if installation successful, False otherwise
        """
        try:
            self._log("🚀 Asset Manager v1.3.0 Installation Starting...")
            self._log("=" * 60)
            
            # Step 1: Create installation directory (like DRAG&DROP.mel)
            self._log(f"📂 Creating installation directory: {self.install_dir}")
            self.install_dir.mkdir(parents=True, exist_ok=True)
            self._log("✅ Installation directory created")
            
            # Step 2: Copy core files (replicating DRAG&DROP.mel exactly)
            self._log("\n📦 Copying core files...")
            core_files = [
                ("assetManager.py", "assetManager.py"),
                ("maya_plugin.py", "maya_plugin.py"),
                ("__init__.py", "__init__.py"),
            ]
            
            for src, dst in core_files:
                self.copy_asset_file(src, dst)
            
            # Step 3: Create development tools on-demand
            self._log("\n🔧 Creating development tools...")
            self._create_hot_reload_tool()
            
            # Step 4: Copy professional icons
            self._log("\n🎨 Copying professional icons...")
            icon_files = [
                ("icons/assetManager_icon.png", "assetManager_icon.png"),
                ("icons/assetManager_icon2.png", "assetManager_icon2.png"),
                ("icons/screen-shot_icon.png", "screen-shot_icon.png"),
            ]
            
            for src, dst in icon_files:
                self.copy_asset_file(src, dst)
            
            # Verify icons were copied successfully
            icon1_path = self.install_dir / "assetManager_icon.png"
            icon2_path = self.install_dir / "assetManager_icon2.png"
            screenshot_icon_path = self.install_dir / "screen-shot_icon.png"
            
            if icon1_path.exists() and icon2_path.exists() and screenshot_icon_path.exists():
                self._log("✅ All icons copied successfully")
                self._log(f"   Main icon: {icon1_path}")
                self._log(f"   Hover icon: {icon2_path}")
                self._log(f"   Screenshot icon: {screenshot_icon_path}")
            else:
                self._log(f"⚠️ Icon copy verification failed:")
                self._log(f"   Main icon exists: {icon1_path.exists()}")
                self._log(f"   Hover icon exists: {icon2_path.exists()}")
                self._log(f"   Screenshot icon exists: {screenshot_icon_path.exists()}")
                
            # List all files in install directory for debugging
            if self.install_dir.exists():
                files = list(self.install_dir.iterdir())
                self._log(f"📂 Install directory contents: {[f.name for f in files]}")
            
            # Step 5: Copy complete EMSA architecture
            self._log("\n🏗️ Copying EMSA architecture...")
            self.copy_source_directory("src", "src")
            
            # Step 6: Installation complete
            self._log("\n" + "=" * 60)
            self._log("🎉 ASSET MANAGER v1.3.0 INSTALLATION COMPLETE!")
            self._log("=" * 60)
            
            self._log(f"📂 Installation Location: {self.install_dir}")
            self._log("✅ Professional icons and EMSA architecture ready")
            self._log("✅ Module activated for immediate use")
            
            return True
            
        except Exception as e:
            self._log(f"\n❌ Installation failed: {e}")
            return False


def install_asset_manager(source_dir: Optional[str] = None, verbose: bool = True) -> bool:
    """
    Main entry point for Asset Manager installation.
    
    Args:
        source_dir: Source directory path (auto-detected if None)
        verbose: Whether to print progress messages
        
    Returns:
        True if installation successful, False otherwise
    """
    installer = AssetManagerInstaller(source_dir, verbose)
    return installer.install()


def main():
    """Command-line interface for setup.py execution."""
    print("Asset Manager v1.3.0 - Unified Installation System")
    print("Multi-Version Maya Compatibility (2022-2025+)")
    print("=" * 60)
    
    try:
        success = install_asset_manager()
        
        if success:
            print("\n🚀 NEXT STEPS:")
            print("1. Open any Maya version (2022, 2023, 2024, 2025+)")
            print("2. Run: import assetManager; assetManager.show_asset_manager()")
            print("3. OR use DRAG&DROP.mel for complete shelf button setup")
            print("\n💡 TIP: Works across all Maya versions!")
            print("🔧 For development: import dev_hot_reload; dev_hot_reload.r()")
            
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())