#!/usr/bin/env python3
"""
Emergency Recovery Script for Asset Manager Recursion Issues
This script can be used to safely launch Asset Manager if recursion issues occur.
"""

import sys
import os
import json
from datetime import datetime

def safe_launch_asset_manager():
    """Safely launch Asset Manager with recursion protection"""
    
    print("=== Asset Manager Emergency Recovery ===")
    print("This script will attempt to safely launch Asset Manager")
    print("and reset any problematic configuration if needed.\n")
    
    try:
        # Add current directory to path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Try to import and create AssetManager
        print("1. Loading AssetManager...")
        from assetManager import AssetManager
        print("   ✅ AssetManager loaded successfully")
        
        print("2. Creating AssetManager instance...")
        am = AssetManager()
        print("   ✅ AssetManager instance created successfully")
        
        # Test basic functionality
        print("3. Testing basic functionality...")
        
        # Test safe path methods
        test_path = "D:/test/path/example_file.mb"
        basename = am._safe_basename(test_path)
        asset_name = am._safe_asset_name(test_path)
        
        print(f"   ✅ Safe basename test: {basename}")
        print(f"   ✅ Safe asset name test: {asset_name}")
        
        # Check current project state
        print("4. Checking current project state...")
        if am.current_project:
            print(f"   Current project: {am.current_project}")
            
            # Test project entry creation
            project_name = am._ensure_project_entry()
            if project_name:
                print(f"   ✅ Project name extracted: {project_name}")
            else:
                print("   ⚠️ No project name could be extracted")
        else:
            print("   No current project set")
        
        print("\n🎉 Asset Manager is working correctly!")
        print("The recursion issues have been resolved.")
        
        # Import UI if available
        try:
            print("\n5. Testing UI components...")
            from assetManager import AssetManagerUI
            print("   ✅ AssetManagerUI class available")
            
            # Don't actually create UI in emergency mode
            print("   Note: UI creation skipped in emergency mode")
            
        except ImportError as e:
            print(f"   ⚠️ UI components not available: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error during safe launch: {e}")
        print("\nAttempting emergency configuration reset...")
        
        if reset_asset_manager_config():
            print("Configuration reset successful. Please try again.")
            return False
        else:
            print("Configuration reset failed. Manual intervention may be required.")
            return False

def reset_asset_manager_config():
    """Reset Asset Manager configuration to safe defaults"""
    
    try:
        print("\n=== Emergency Configuration Reset ===")
        
        # Get Maya app directory
        home = os.path.expanduser("~")
        maya_app_dir = os.path.join(home, "Documents", "maya")
        config_dir = os.path.join(maya_app_dir, "assetManager")
        config_path = os.path.join(config_dir, "config.json")
        
        print(f"Config directory: {config_dir}")
        print(f"Config file: {config_path}")
        
        # Create backup of existing config
        if os.path.exists(config_path):
            backup_path = config_path + f".backup_{int(datetime.now().timestamp())}"
            print(f"Backing up existing config to: {backup_path}")
            
            import shutil
            shutil.copy2(config_path, backup_path)
            print("   ✅ Backup created")
        
        # Create safe default configuration
        safe_config = {
            'current_project': None,  # Reset to None to avoid recursion
            'assets_library': {},
            'asset_types': {
                'models': {
                    'name': 'Models',
                    'color': [0, 150, 255],
                    'priority': 0,
                    'extensions': ['.obj', '.fbx', '.ma', '.mb'],
                    'description': '3D models and geometry'
                },
                'default': {
                    'name': 'Default',
                    'color': [128, 128, 128],
                    'priority': 999,
                    'extensions': [],
                    'description': 'Uncategorized assets'
                }
            },
            'version': '1.1.3',
            'emergency_reset': datetime.now().isoformat(),
            'reset_reason': 'Recursion error recovery'
        }
        
        # Ensure config directory exists
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            print(f"   ✅ Created config directory: {config_dir}")
        
        # Write safe configuration
        with open(config_path, 'w') as f:
            json.dump(safe_config, f, indent=4)
        
        print("   ✅ Safe configuration written")
        print("\nConfiguration has been reset to safe defaults.")
        print("All project paths have been cleared to prevent recursion.")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error during config reset: {e}")
        return False

def show_usage():
    """Show usage information"""
    print("Asset Manager Emergency Recovery Script")
    print("=====================================")
    print()
    print("Usage:")
    print("  python emergency_recovery.py              - Safe launch with tests")
    print("  python emergency_recovery.py --reset      - Reset configuration only")
    print("  python emergency_recovery.py --help       - Show this help")
    print()
    print("This script helps recover from Asset Manager recursion issues.")

def main():
    """Main function"""
    
    if len(sys.argv) > 1:
        if "--help" in sys.argv or "-h" in sys.argv:
            show_usage()
            return
        elif "--reset" in sys.argv:
            success = reset_asset_manager_config()
            sys.exit(0 if success else 1)
    
    # Default: safe launch with tests
    success = safe_launch_asset_manager()
    
    if success:
        print("\n✅ Emergency recovery completed successfully!")
        print("Asset Manager should now be safe to use.")
    else:
        print("\n❌ Emergency recovery encountered issues.")
        print("You may need to manually check the configuration.")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
