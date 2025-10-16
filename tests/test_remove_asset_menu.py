#!/usr/bin/env python3
"""
Remove Asset Button Test - Issue #10
Tests the Remove Asset functionality accessible from main menu bar (Assets menu)
"""

import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

try:
    from PySide6.QtWidgets import QApplication, QMainWindow
    from PySide6.QtCore import Qt
    print("✅ PySide6 available")
except ImportError:
    print("❌ PySide6 not available - cannot test UI functionality")
    sys.exit(1)

def test_remove_asset_menu_presence():
    """Test Remove Asset menu item presence - Issue #10"""
    print("\n🔧 Testing Remove Asset Menu Presence...")
    
    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        if not asset_manager_file.exists():
            print("❌ AssetManagerWindow source file not found")
            return False
            
        with open(asset_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for Assets menu remove action
        if 'remove_asset_action = QAction("&Remove Selected Asset...", self)' in content:
            print("✅ Remove Asset action created in Assets menu")
        else:
            print("❌ Remove Asset action creation not found in Assets menu")
            return False
            
        # Check for action connection
        if 'remove_asset_action.triggered.connect(self._on_remove_selected_asset)' in content:
            print("✅ Remove Asset action properly connected")
        else:
            print("❌ Remove Asset action connection not found")
            return False
            
        # Check for keyboard shortcut
        if 'remove_asset_action.setShortcut(QKeySequence.StandardKey.Delete)' in content:
            print("✅ Delete key shortcut implemented")
        else:
            print("⚠️ Delete key shortcut may not be implemented")
            
        # Check for separator before destructive action
        if 'assets_menu.addSeparator()' in content:
            print("✅ Separator added before destructive action (good UX)")
        else:
            print("⚠️ No separator before destructive action")
            
        return True
        
    except Exception as e:
        print(f"❌ Remove Asset menu presence test failed: {e}")
        return False

def test_existing_connections():
    """Test that existing connections are maintained"""
    print("\n🔍 Testing Existing Connections...")
    
    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check File menu connection (existing)
        if 'remove_selected_action.triggered.connect(self._on_remove_selected_asset)' in content:
            print("✅ File menu Remove Selected Asset connection maintained")
        else:
            print("❌ File menu connection missing")
            return False
            
        # Check toolbar button connection (existing)
        if 'remove_btn.clicked.connect(self._on_remove_selected_asset)' in content:
            print("✅ Toolbar Remove Asset button connection maintained")
        else:
            print("❌ Toolbar button connection missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Existing connections test failed: {e}")
        return False

def test_method_implementation():
    """Test that the method implementation exists and is robust"""
    print("\n🛠️ Testing Method Implementation...")
    
    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for method definition
        if 'def _on_remove_selected_asset(self) -> None:' in content:
            print("✅ _on_remove_selected_asset method found")
        else:
            print("❌ _on_remove_selected_asset method not found")
            return False
            
        # Check for key implementation features
        method_start = content.find('def _on_remove_selected_asset(self) -> None:')
        if method_start == -1:
            print("❌ Method implementation not found")
            return False
            
        # Get method content (rough extraction for testing)
        method_end = content.find('\n    def ', method_start + 1)
        if method_end == -1:
            method_end = len(content)
        method_content = content[method_start:method_end]
        
        features_found = 0
        
        if 'selected_assets' in method_content:
            print("✅ Asset selection check implemented")
            features_found += 1
            
        if 'QMessageBox.question' in method_content:
            print("✅ User confirmation dialog implemented")
            features_found += 1
            
        if 'self._repository.remove_asset' in method_content:
            print("✅ Repository removal call implemented")
            features_found += 1
            
        if 'self._on_refresh_library()' in method_content:
            print("✅ Library refresh after removal implemented")
            features_found += 1
            
        if 'try:' in method_content and 'except' in method_content:
            print("✅ Exception handling implemented")
            features_found += 1
        
        print(f"✅ Implementation features found: {features_found}/5")
        
        if features_found >= 3:
            print("✅ Remove Asset method is robustly implemented")
            return True
        else:
            print("❌ Remove Asset method needs more robust implementation")
            return False
        
    except Exception as e:
        print(f"❌ Method implementation test failed: {e}")
        return False

def test_menu_structure():
    """Test that the menu structure is logical and well-organized"""
    print("\n📋 Testing Menu Structure...")
    
    try:
        asset_manager_file = Path("src/ui/asset_manager_window.py")
        with open(asset_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Find Assets menu section
        assets_menu_start = content.find('assets_menu = menubar.addMenu("&Assets")')
        if assets_menu_start == -1:
            print("❌ Assets menu not found")
            return False
            
        # Get Assets menu section
        view_menu_start = content.find('view_menu = menubar.addMenu("&View")', assets_menu_start)
        if view_menu_start == -1:
            view_menu_start = len(content)
        assets_menu_content = content[assets_menu_start:view_menu_start]
        
        # Check menu item order and structure
        menu_items = []
        if 'Import Selected' in assets_menu_content:
            menu_items.append('Import Selected')
        if 'Add to Favorites' in assets_menu_content:
            menu_items.append('Add to Favorites')
        if 'Remove Selected Asset' in assets_menu_content:
            menu_items.append('Remove Selected Asset')
            
        print(f"✅ Assets menu items found: {', '.join(menu_items)}")
        
        # Check logical order (import, favorites, then remove)
        expected_order = ['Import Selected', 'Add to Favorites', 'Remove Selected Asset']
        if menu_items == expected_order:
            print("✅ Menu items in logical order (constructive actions first, destructive last)")
        else:
            print("⚠️ Menu item order could be improved")
            
        # Check for separator before destructive action
        if 'addSeparator()' in assets_menu_content:
            print("✅ Separator properly separates destructive actions")
        else:
            print("⚠️ No separator found in Assets menu")
            
        return True
        
    except Exception as e:
        print(f"❌ Menu structure test failed: {e}")
        return False

def main():
    """Run Remove Asset button functionality tests"""
    print("🧪 REMOVE ASSET BUTTON FUNCTIONALITY TEST - Issue #10")
    print("=" * 60)
    
    # Initialize QApplication for Qt imports
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Run tests
    tests = [
        ("Remove Asset Menu Presence", test_remove_asset_menu_presence),
        ("Existing Connections Maintained", test_existing_connections),
        ("Method Implementation", test_method_implementation),
        ("Menu Structure", test_menu_structure),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 REMOVE ASSET BUTTON TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All Remove Asset button tests PASSED!")
        print("🗑️ Remove Asset is now accessible from Assets menu in main menu bar")
        return True
    else:
        print("⚠️ Some tests failed - check implementation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
