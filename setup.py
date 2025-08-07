"""
Asset Manager Setup Script v1.1.3
Installs the Asset Manager plugin for Maya 2025.3+ with Performance Optimizations
"""

import os
import sys
import shutil
from pathlib import Path

def get_maya_user_path():
    """Get the Maya user directory path"""
    home = Path.home()
    maya_version = "2025"
    
    # Windows path
    if sys.platform == "win32":
        maya_path = home / "Documents" / "maya" / maya_version
    # macOS path
    elif sys.platform == "darwin":
        maya_path = home / "Library" / "Preferences" / "Autodesk" / "maya" / maya_version
    # Linux path
    else:
        maya_path = home / "maya" / maya_version
    
    return maya_path

def install_plugin():
    """Install the Asset Manager plugin"""
    try:
        # Get source and destination paths
        source_dir = Path(__file__).parent
        maya_user_path = get_maya_user_path()
        
        # Create plugins directory if it doesn't exist
        plugins_dir = maya_user_path / "plug-ins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy plugin files
        plugin_files = ["assetManager.py", "assetManager.mod", "icon_utils.py"]
        
        for file_name in plugin_files:
            source_file = source_dir / file_name
            dest_file = plugins_dir / file_name
            
            if source_file.exists():
                shutil.copy2(source_file, dest_file)
                print(f"Installed: {file_name}")
            else:
                print(f"Warning: {file_name} not found")
        
        # Copy icons directory if it exists
        icons_source = source_dir / "icons"
        if icons_source.exists():
            icons_dest = plugins_dir / "icons"
            if icons_dest.exists():
                shutil.rmtree(icons_dest)
            shutil.copytree(icons_source, icons_dest)
            print("Installed: icons directory")
        
        print(f"\nAsset Manager v1.1.3 plugin installed successfully!")
        print(f"Location: {plugins_dir}")
        print("\nNew in v1.1.3:")
        print("• Performance Optimizations - Smart caching and network storage optimization")
        print("• Automatic Refresh - Real-time synchronization with file system changes") 
        print("• Enhanced Reliability - Fixed collection tab refresh and memory leaks")
        print("• Background Processing - Improved thumbnail generation and dependency calculations")
        print("\nTo activate the plugin in Maya:")
        print("1. Open Maya 2025.3+")
        print("2. Go to Windows > Settings/Preferences > Plug-in Manager")
        print("3. Find 'assetManager.py' and check both 'Loaded' and 'Auto load'")
        print("4. The Asset Manager shelf button should appear automatically")
        
    except Exception as e:
        print(f"Error installing plugin: {e}")
        return False
    
    return True

def uninstall_plugin():
    """Uninstall the Asset Manager plugin"""
    try:
        maya_user_path = get_maya_user_path()
        plugins_dir = maya_user_path / "plug-ins"
        
        plugin_files = ["assetManager.py", "assetManager.mod", "icon_utils.py"]
        
        for file_name in plugin_files:
            plugin_file = plugins_dir / file_name
            if plugin_file.exists():
                plugin_file.unlink()
                print(f"Removed: {file_name}")
        
        # Remove icons directory if it exists
        icons_dir = plugins_dir / "icons"
        if icons_dir.exists():
            shutil.rmtree(icons_dir)
            print("Removed: icons directory")
        
        print("Asset Manager v1.1.3 plugin uninstalled successfully!")
        
    except Exception as e:
        print(f"Error uninstalling plugin: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Asset Manager v1.1.3 Setup")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall_plugin()
    else:
        install_plugin()
