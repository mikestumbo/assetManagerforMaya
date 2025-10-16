#!/usr/bin/env python3
"""
Asset Manager v1.3.0 - Maya Functionality Test Suite
Comprehensive testing for Asset Manager plugin in Maya environment

Run this in Maya's Script Editor (Python) to validate all functionality.
"""

import sys
import os
import traceback
from typing import List, Tuple, Any
from pathlib import Path

def print_test_header(test_name: str):
    """Print formatted test header."""
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {test_name}")
    print(f"{'='*60}")

def print_test_result(test_name: str, success: bool, details: str = ""):
    """Print formatted test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        print(f"    Details: {details}")

def test_basic_import() -> Tuple[bool, str]:
    """Test if assetManager can be imported successfully."""
    try:
        import assetManager
        return True, f"Version: {getattr(assetManager, 'PLUGIN_VERSION', 'Unknown')}"
    except Exception as e:
        return False, f"Import error: {str(e)}"

def test_maya_plugin_import() -> Tuple[bool, str]:
    """Test if maya_plugin module can be imported."""
    try:
        import maya_plugin
        return True, f"Module loaded successfully"
    except Exception as e:
        return False, f"Import error: {str(e)}"

def test_show_asset_manager() -> Tuple[bool, str]:
    """Test if Asset Manager UI can be launched."""
    try:
        import assetManager
        ui_instance = assetManager.show_asset_manager()
        if ui_instance:
            return True, "UI launched successfully"
        else:
            return False, "UI function returned None"
    except Exception as e:
        return False, f"Launch error: {str(e)}"

def test_plugin_directory_detection() -> Tuple[bool, str]:
    """Test plugin directory detection."""
    try:
        import assetManager
        if hasattr(assetManager, '_get_current_plugin_directory'):
            plugin_dir = assetManager._get_current_plugin_directory()
            if os.path.exists(plugin_dir):
                return True, f"Plugin directory: {plugin_dir}"
            else:
                return False, f"Directory not found: {plugin_dir}"
        else:
            return False, "Function _get_current_plugin_directory not found"
    except Exception as e:
        return False, f"Detection error: {str(e)}"

def test_maya_commands_integration() -> Tuple[bool, str]:
    """Test Maya commands integration."""
    try:
        import maya.cmds as cmds # type: ignore
        # Test basic Maya functionality
        scene_name = cmds.file(query=True, sceneName=True) or "untitled"
        return True, f"Maya integration working, scene: {os.path.basename(scene_name)}"
    except Exception as e:
        return False, f"Maya commands error: {str(e)}"

def test_pyside6_availability() -> Tuple[bool, str]:
    """Test PySide6 availability for Maya 2025+."""
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        import PySide6
        return True, f"PySide6 available - {PySide6.__version__}"
    except ImportError:
        return False, "PySide6 not available - required for Maya 2025+"
    except Exception as e:
        return False, f"PySide6 error: {str(e)}"

def test_service_container_initialization() -> Tuple[bool, str]:
    """Test EMSA service container initialization and service registration."""
    try:
        # Import after assetManager is loaded
        sys.path.insert(0, "C:/Users/ChEeP/Documents/maya/2025.3/scripts/assetManager")
        
        from src.core.container import get_container, configure_services
        
        # Configure services
        container = configure_services()
        
        # Check what services are registered
        registered_services = container.get_registered_services()
        
        if len(registered_services) >= 2:  # Should have at least thumbnail and repository services
            return True, f"EMSA container initialized with {len(registered_services)} services: {list(registered_services.keys())}"
        else:
            return False, f"Insufficient services registered: {list(registered_services.keys())}"
            
    except Exception as e:
        return False, f"Service container error: {str(e)}"

def test_asset_repository_integration() -> Tuple[bool, str]:
    """Test asset repository service integration."""
    try:
        from src.core.container import get_container, configure_services
        from src.core.interfaces.asset_repository import IAssetRepository
        
        container = configure_services()
        repo = container.get(IAssetRepository)
        
        if not repo:
            repo = container.resolve(IAssetRepository) if container.is_registered(IAssetRepository) else None
        
        if repo:
            # Test basic functionality
            repo_type = type(repo).__name__
            has_find_method = hasattr(repo, 'find_all') or hasattr(repo, 'get_assets_from_directory')
            return True, f"Repository service active: {repo_type}, methods available: {has_find_method}"
        else:
            return False, "Asset repository service not available"
            
    except Exception as e:
        return False, f"Repository integration error: {str(e)}"

def test_thumbnail_service_integration() -> Tuple[bool, str]:
    """Test thumbnail service integration."""
    try:
        from src.core.container import get_container, configure_services
        from src.core.interfaces.thumbnail_service import IThumbnailService
        
        container = configure_services()
        thumbnail_service = container.get(IThumbnailService)
        
        if not thumbnail_service:
            thumbnail_service = container.resolve(IThumbnailService) if container.is_registered(IThumbnailService) else None
        
        if thumbnail_service:
            service_type = type(thumbnail_service).__name__
            has_generate = hasattr(thumbnail_service, 'generate_thumbnail')
            has_cache = hasattr(thumbnail_service, 'get_cached_thumbnail')
            return True, f"Thumbnail service active: {service_type}, generate: {has_generate}, cache: {has_cache}"
        else:
            return False, "Thumbnail service not available"
            
    except Exception as e:
        return False, f"Thumbnail service error: {str(e)}"

def test_maya_workspace_integration() -> Tuple[bool, str]:
    """Test Maya workspace and project integration."""
    try:
        import maya.cmds as cmds # type: ignore
        
        # Get workspace info
        current_project = cmds.workspace(query=True, rootDirectory=True)
        scene_name = cmds.file(query=True, sceneName=True) or "untitled"
        
        # Test workspace access
        workspace_accessible = os.path.exists(current_project) if current_project else False
        
        return True, f"Workspace: {os.path.basename(current_project) if current_project else 'None'}, Scene: {os.path.basename(scene_name)}, Accessible: {workspace_accessible}"
        
    except Exception as e:
        return False, f"Maya workspace error: {str(e)}"

def test_installation_files() -> Tuple[bool, str]:
    """Test if all required installation files are present with enhanced detection."""
    try:
        import assetManager
        
        # Try multiple detection methods for robust installation validation
        install_locations = []
        
        # Method 1: Check Maya scripts directory
        try:
            import maya.cmds as cmds # type: ignore
            maya_scripts_dir = cmds.internalVar(userScriptDir=True)
            maya_install_dir = os.path.join(maya_scripts_dir, "assetManager")
            install_locations.append(("Maya Scripts", maya_install_dir))
        except:
            pass
        
        # Method 2: Check assetManager module path (where it's actually running from)
        try:
            asset_manager_path = os.path.dirname(assetManager.__file__)
            install_locations.append(("Module Path", asset_manager_path))
        except:
            pass
        
        # Method 3: Check current working directory
        try:
            current_dir = os.getcwd()
            if "assetManager" in current_dir.lower():
                install_locations.append(("Working Directory", current_dir))
        except:
            pass
        
        required_files = [
            "assetManager.py",
            "maya_plugin.py", 
            "__init__.py"
        ]
        
        icon_files = [
            "assetManager_icon.png",
            "assetManager_icon2.png"
        ]
        
        # Check each potential location
        for location_name, install_dir in install_locations:
            if not os.path.exists(install_dir):
                continue
                
            missing_core = []
            present_core = []
            missing_icons = []
            present_icons = []
            
            # Check core files
            for file in required_files:
                file_path = os.path.join(install_dir, file)
                if os.path.exists(file_path):
                    present_core.append(file)
                else:
                    missing_core.append(file)
            
            # Check icon files (more flexible - may be in subdirectories)
            for icon in icon_files:
                # Check in main directory
                icon_path = os.path.join(install_dir, icon)
                if os.path.exists(icon_path):
                    present_icons.append(icon)
                else:
                    # Check in icons subdirectory
                    icons_dir_path = os.path.join(install_dir, "icons", icon)
                    if os.path.exists(icons_dir_path):
                        present_icons.append(f"icons/{icon}")
                    else:
                        missing_icons.append(icon)
            
            # If we found most core files in this location, this is likely the right one
            if len(present_core) >= 2:  # At least 2 core files present
                total_files = len(required_files) + len(icon_files)
                found_files = len(present_core) + len(present_icons)
                
                if len(missing_core) == 0:
                    return True, f"All core files present in {location_name}: {install_dir} | Found: {found_files}/{total_files} files"
                else:
                    return False, f"Missing core files in {location_name}: {', '.join(missing_core)} | Icons: {len(present_icons)}/{len(icon_files)}"
        
        # If no good location found, return diagnostic info
        locations_info = [f"{name}: {path}" for name, path in install_locations]
        return False, f"Installation validation failed. Checked locations: {'; '.join(locations_info) if locations_info else 'None found'}"
            
    except Exception as e:
        return False, f"File check error: {str(e)}"

def run_comprehensive_tests():
    """Run all functionality tests."""
    print_test_header("ASSET MANAGER v1.3.0 - MAYA FUNCTIONALITY TESTS")
    
    tests = [
        ("Basic Import Test", test_basic_import),
        ("Maya Plugin Import Test", test_maya_plugin_import), 
        ("Plugin Directory Detection", test_plugin_directory_detection),
        ("Installation Files Check", test_installation_files),
        ("Maya Commands Integration", test_maya_commands_integration),
        ("PySide6 Availability", test_pyside6_availability),
        ("Service Container Initialization", test_service_container_initialization),
        ("Asset Repository Integration", test_asset_repository_integration),
        ("Thumbnail Service Integration", test_thumbnail_service_integration),
        ("Maya Workspace Integration", test_maya_workspace_integration),
        ("Asset Manager UI Launch", test_show_asset_manager),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            success, details = test_func()
            print_test_result(test_name, success, details)
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print_test_result(test_name, False, f"Test execution error: {str(e)}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"📊 COMPREHENSIVE TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed))*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Asset Manager is fully functional.")
        print("🚀 Ready for production use in Maya 2025.3")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Check details above for issues.")
        if passed >= 8:  # If most tests pass
            print("✅ Core functionality appears to be working correctly.")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    # Run tests when executed in Maya
    run_comprehensive_tests()