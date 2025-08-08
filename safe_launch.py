#!/usr/bin/env python
"""
Safe Asset Manager Launcher for Maya v1.1.4
This script safely launches the Asset Manager with recursion error protection
and UI improvements including window memory and better sizing defaults.

Version: 1.1.4
Author: Mike Stumbo  
Maya Version: 2025.3+
"""

import sys
import os
import traceback

def safe_launch_asset_manager():
    """Safely launch Asset Manager with error handling"""
    try:
        import maya.cmds as cmds # pyright: ignore[reportMissingImports]
        
        # Add plugin directory to Python path
        user_app_dir = cmds.internalVar(userAppDir=True)
        plugin_dir = os.path.join(user_app_dir, 'plug-ins')
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)
        
        # Also add the current directory (where our updated assetManager.py is)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        try:
            # Try to import and show Asset Manager
            import assetManager
            
            print("Launching Asset Manager v1.1.4 with UI improvements...")
            window = assetManager.show_asset_manager()
            
            if window is not None:
                print("✓ Asset Manager v1.1.4 launched successfully!")
                return window
            else:
                print("✗ Asset Manager failed to launch (but no exception thrown)")
                return None
                
        except ImportError as e:
            print(f"ImportError: {e}")
            # Try to load plugin and retry
            try:
                cmds.loadPlugin('assetManager', quiet=True)
                # Re-add to path and import again
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                import assetManager
                
                print("Launching Asset Manager v1.1.4 after loading plugin...")
                window = assetManager.show_asset_manager()
                
                if window is not None:
                    print("✓ Asset Manager v1.1.4 launched successfully after loading plugin!")
                    return window
                else:
                    print("✗ Asset Manager failed to launch after loading plugin")
                    return None
                    
            except Exception as e:
                print(f'Asset Manager Error: Could not load plugin or module - {str(e)}')
                traceback.print_exc()
                return None
                
        except RecursionError as e:
            print(f"RecursionError caught and handled: {e}")
            print("The recursion error fix should prevent this. If you see this message,")
            print("there may be another recursion issue that needs investigation.")
            traceback.print_exc()
            return None
            
        except Exception as e:
            print(f'Asset Manager Error: {str(e)}')
            traceback.print_exc()
            return None
            
    except Exception as e:
        print(f"Error in safe launcher: {e}")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # This will only work when run from within Maya
    print("Safe Asset Manager Launcher v1.1.4")
    print("Run this script from within Maya's script editor")
    
    result = safe_launch_asset_manager()
    if result:
        print("Launch successful! Enjoy the improved UI with window memory and better sizing!")
    else:
        print("Launch failed - check error messages above")
