#!/usr/bin/env python
"""
Asset Manager Config Diagnostic Tool
Helps diagnose and fix recursion errors in asset manager configuration
"""

import os
import json
import sys
import traceback

def diagnose_config():
    """Diagnose the asset manager configuration file"""
    print("=== Asset Manager Configuration Diagnostic ===")
    
    # Find the config file
    if sys.platform == "win32":
        config_dir = os.path.join(os.path.expanduser("~"), "Documents", "maya", "assetManager")
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".maya", "assetManager")
    
    config_path = os.path.join(config_dir, "config.json")
    
    print(f"Config directory: {config_dir}")
    print(f"Config file path: {config_path}")
    
    if not os.path.exists(config_path):
        print("✓ No config file found - this is normal for first run")
        return True
    
    print(f"✓ Config file exists")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print("✓ Config file is valid JSON")
    except Exception as e:
        print(f"✗ Error reading config file: {e}")
        return False
    
    # Check current_project
    current_project = config.get('current_project')
    print(f"Current project in config: {repr(current_project)}")
    
    if current_project is None:
        print("✓ No current project set")
        return True
    
    if not isinstance(current_project, str):
        print(f"✗ Current project is not a string: {type(current_project)}")
        return False
    
    if not current_project.strip():
        print("✗ Current project is empty or whitespace")
        return False
    
    # Test os.path.basename - this is where the recursion error occurs
    try:
        print(f"Testing os.path.basename on: {repr(current_project)}")
        basename_result = os.path.basename(current_project.rstrip(os.sep))
        print(f"✓ os.path.basename works: {repr(basename_result)}")
        
        if not basename_result:
            print("✗ Warning: basename is empty")
            return False
            
    except RecursionError as e:
        print(f"✗ RecursionError in os.path.basename: {e}")
        print("This is the source of your problem!")
        return False
    except Exception as e:
        print(f"✗ Other error in os.path.basename: {e}")
        return False
    
    print("✓ Configuration appears to be valid")
    return True

def fix_config():
    """Attempt to fix the configuration by resetting current_project"""
    print("\n=== Attempting to Fix Configuration ===")
    
    # Find the config file
    if sys.platform == "win32":
        config_dir = os.path.join(os.path.expanduser("~"), "Documents", "maya", "assetManager")
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".maya", "assetManager")
    
    config_path = os.path.join(config_dir, "config.json")
    
    if not os.path.exists(config_path):
        print("No config file to fix")
        return True
    
    try:
        # Create backup
        backup_path = config_path + ".backup"
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"✓ Created backup: {backup_path}")
        
        # Load and fix config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Reset current_project to None
        old_project = config.get('current_project')
        config['current_project'] = None
        
        # Save fixed config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✓ Reset current_project from {repr(old_project)} to None")
        print("✓ Configuration has been fixed")
        print("You can now try opening Asset Manager again")
        
        return True
        
    except Exception as e:
        print(f"✗ Error fixing config: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = diagnose_config()
    
    if not success:
        print("\nConfiguration has issues. Attempting to fix...")
        fix_config()
    
    print("\n=== Diagnostic Complete ===")
