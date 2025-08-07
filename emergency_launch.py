#!/usr/bin/env python
"""
Emergency Asset Manager Launcher
This script provides a safe way to launch the Asset Manager after recursion errors.
It includes additional safety checks and error recovery mechanisms.
"""

import sys
import os
import traceback

def safe_launch_asset_manager():
    """Launch Asset Manager with comprehensive error handling"""
    try:
        print("=== Emergency Asset Manager Launcher ===")
        print("Starting safe launch sequence...")
        
        # Add current directory to Python path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Import the asset manager with error handling
        try:
            print("Importing Asset Manager...")
            import assetManager
            print("Asset Manager module imported successfully")
        except Exception as e:
            print(f"ERROR: Failed to import Asset Manager: {e}")
            print("Full traceback:")
            traceback.print_exc()
            return False
        
        # Try to show the Asset Manager UI
        try:
            print("Launching Asset Manager UI...")
            assetManager.show_asset_manager()
            print("Asset Manager launched successfully!")
            return True
        except RecursionError as e:
            print(f"RECURSION ERROR: {e}")
            print("The Asset Manager encountered a recursion error during launch.")
            print("This may indicate a configuration issue that needs to be reset.")
            return False
        except Exception as e:
            print(f"ERROR: Failed to launch Asset Manager UI: {e}")
            print("Full traceback:")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"CRITICAL ERROR in safe launcher: {e}")
        traceback.print_exc()
        return False

def reset_asset_manager_config():
    """Reset Asset Manager configuration to defaults"""
    try:
        print("=== Resetting Asset Manager Configuration ===")
        
        # Try to import and reset
        import assetManager
        if hasattr(assetManager, 'AssetManager'):
            # Create temporary instance to get config path
            temp_manager = assetManager.AssetManager()
            config_path = temp_manager.config_path
            
            if os.path.exists(config_path):
                # Backup current config
                backup_path = config_path + ".backup"
                import shutil
                shutil.copy2(config_path, backup_path)
                print(f"Backed up config to: {backup_path}")
                
                # Remove problematic config
                os.remove(config_path)
                print(f"Removed config file: {config_path}")
                print("Asset Manager will create a new default configuration on next launch.")
                return True
            else:
                print("No config file found to reset.")
                return True
                
    except Exception as e:
        print(f"Error resetting config: {e}")
        return False

def main():
    """Main function"""
    print("Asset Manager Emergency Tools")
    print("1. Safe Launch")
    print("2. Reset Configuration")
    print("3. Exit")
    
    try:
        choice = input("Choose an option (1-3): ").strip()
        
        if choice == "1":
            success = safe_launch_asset_manager()
            if not success:
                print("Safe launch failed. Consider resetting configuration (option 2).")
        elif choice == "2":
            success = reset_asset_manager_config()
            if success:
                print("Configuration reset. Try launching Asset Manager now.")
        elif choice == "3":
            print("Exiting...")
        else:
            print("Invalid choice.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
