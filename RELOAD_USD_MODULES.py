# RELOAD_USD_MODULES.py - Force reload Asset Manager USD modules
# Run this in Maya Script Editor (Python) before testing USD export
# Clears cached versions that may have outdated code

import sys
import gc

print("\n" + "="*60)
print("Asset Manager USD Module Reloader v1.5.0")
print("="*60 + "\n")

# Step 1: Find and remove all Asset Manager modules from sys.modules
# This is critical because Maya caches imported Python modules
# Changes to files on disk won't be used until modules are unloaded

modules_to_remove = []
keywords = ['asset', 'emsa', 'src.services', 'src.core', 'src.ui', 'src.config', 'usd_export', 'maya_scene_parser']

for module_name in list(sys.modules.keys()):
    lower_name = module_name.lower()
    for keyword in keywords:
        if keyword.lower() in lower_name:
            modules_to_remove.append(module_name)
            break

print(f"[FOUND] {len(modules_to_remove)} cached Asset Manager modules:")
for mod in sorted(modules_to_remove):
    print(f"  - {mod}")

print("\n[ACTION] Removing cached modules...")
for mod in modules_to_remove:
    try:
        del sys.modules[mod]
        print(f"  [OK] Removed: {mod}")
    except Exception as e:
        print(f"  [WARN] Could not remove {mod}: {e}")

# Step 2: Force garbage collection to free memory
gc.collect()
print(f"\n[OK] Garbage collection complete")

# Step 3: Clear any __pycache__ directories
import os
import shutil

base_paths = [
    r'C:\Users\ChEeP\OneDrive\Documents\maya\scripts\assetManager',
    r'C:\Users\ChEeP\OneDrive\Documents\Mike Stumbo plugins\assetManagerforMaya-master'
]

print("\n[ACTION] Clearing __pycache__ directories...")
for base_path in base_paths:
    if os.path.exists(base_path):
        for root, dirs, files in os.walk(base_path):
            for dir_name in dirs:
                if dir_name == '__pycache__':
                    cache_path = os.path.join(root, dir_name)
                    try:
                        shutil.rmtree(cache_path)
                        print(f"  [OK] Cleared: {cache_path}")
                    except Exception as e:
                        print(f"  [WARN] Could not clear {cache_path}: {e}")

print("\n" + "="*60)
print("[READY] Modules cleared! Now re-launch Asset Manager.")
print("="*60)
print("\nNext steps:")
print("1. Close Asset Manager window if open")
print("2. Re-run the launch script or shelf button")
print("3. Try the USD export again")
print("")
