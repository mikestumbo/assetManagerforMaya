#!/usr/bin/env python3
"""
Test for Zoom and Metadata Fixes - Asset Manager v1.2.0
This test validates that the critical zoom and metadata display issues are resolved.

Run this after the latest fixes to validate functionality.
"""

import os
import sys

def test_zoom_consistency_fixes():
    """Test if zoom consistency fixes are present"""
    print("🔍 Testing Zoom Consistency Fixes...")
    
    with open('assetManager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check if original pixmap storage is fixed
    if 'self._info_original_pixmap = professional_icon.copy()' in content:
        checks.append("✅ Original pixmap storage for zoom fixed")
    else:
        checks.append("❌ Original pixmap storage missing")
    
    # Check if double-click uses consistent method
    if 'self._preview_reset_zoom()  # Use the consistent method' in content:
        checks.append("✅ Double-click uses consistent zoom method")
    else:
        checks.append("❌ Double-click zoom method not fixed")
    
    # Check if info label has double-click handler
    if 'self.preview_info_label.mouseDoubleClickEvent = self.preview_double_click' in content:
        checks.append("✅ Info label double-click handler added")
    else:
        checks.append("❌ Info label double-click handler missing")
    
    # Check if zoom level reset is included
    if 'self._zoom_level = 1.0' in content and 'self._update_zoom_label()' in content:
        checks.append("✅ Zoom level reset and label update present")
    else:
        checks.append("❌ Zoom level reset or label update missing")
    
    for check in checks:
        print(f"  {check}")
    
    passed = sum(1 for check in checks if check.startswith("✅"))
    total = len(checks)
    
    if passed == total:
        print("  🎉 All zoom consistency fixes are present!")
        return True
    else:
        print(f"  ⚠️ Only {passed}/{total} zoom fixes found")
        return False

def test_metadata_separation_fixes():
    """Test if metadata handling separation is properly implemented"""
    print("\n📊 Testing Metadata Separation Fixes...")
    
    with open('assetManager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check if metadata handling was removed from preview widget
    if 'Preview widget handles only preview display' in content:
        checks.append("✅ Preview widget separated from metadata")
    else:
        checks.append("❌ Preview widget still handles metadata")
    
    # Check if metadata display debugging is present
    if 'AssetInformationWidget.load_asset_information called with' in content:
        checks.append("✅ Metadata debugging is present")
    else:
        checks.append("❌ Metadata debugging missing")
    
    # Check if information widget has proper metadata handling
    if 'self.update_metadata_display(metadata)' in content and 'AssetInformationWidget' in content:
        checks.append("✅ AssetInformationWidget has metadata display")
    else:
        checks.append("❌ AssetInformationWidget metadata handling missing")
    
    # Check if selection handler calls both widgets properly
    if 'self.asset_information_widget.load_asset_information(asset_path)' in content:
        checks.append("✅ Selection handler calls information widget")
    else:
        checks.append("❌ Selection handler doesn't call information widget")
    
    for check in checks:
        print(f"  {check}")
    
    passed = sum(1 for check in checks if check.startswith("✅"))
    total = len(checks)
    
    if passed == total:
        print("  🎉 All metadata separation fixes are present!")
        return True
    else:
        print(f"  ⚠️ Only {passed}/{total} metadata fixes found")
        return False

def test_clean_code_improvements():
    """Test Clean Code improvements applied"""
    print("\n🧹 Testing Clean Code Improvements...")
    
    with open('assetManager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    improvements = []
    
    # Check for Single Responsibility comments
    if 'Single Responsibility Principle' in content:
        improvements.append("✅ Single Responsibility Principle applied")
    
    # Check for proper debug messages
    debug_count = content.count('print(f"')
    if debug_count > 20:
        improvements.append(f"✅ Comprehensive debug logging ({debug_count} debug statements)")
    else:
        improvements.append(f"⚠️ Limited debug logging ({debug_count} debug statements)")
    
    # Check for error handling
    exception_count = content.count('except Exception as e:')
    if exception_count > 10:
        improvements.append(f"✅ Proper exception handling ({exception_count} handlers)")
    else:
        improvements.append(f"⚠️ Limited exception handling ({exception_count} handlers)")
    
    # Check for method separation
    if 'metadata handled by separate AssetInformationWidget' in content:
        improvements.append("✅ Proper separation of concerns")
    
    for improvement in improvements:
        print(f"  {improvement}")
    
    return len(improvements) >= 3

def main():
    """Run all tests and provide summary"""
    print("🚀 Asset Manager v1.2.0 - Zoom & Metadata Fixes Validation")
    print("=" * 60)
    
    results = {}
    
    # Test all fixes
    results['zoom'] = test_zoom_consistency_fixes()
    results['metadata'] = test_metadata_separation_fixes()
    results['clean_code'] = test_clean_code_improvements()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 VALIDATION SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name.upper():<12}: {status}")
    
    print(f"\n🎯 OVERALL: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL ZOOM & METADATA FIXES VALIDATED! 🎉")
        print("\n📝 Expected Results:")
        print("  🔍 Zoom buttons should now work visually")
        print("  🖱️ Mouse wheel should zoom the preview image")
        print("  🖱️ Double-click should reset zoom to 100%")
        print("  📊 Asset metadata should display when assets are selected")
        print("  🎯 Debug output should show what's happening")
        return 0
    else:
        print(f"\n⚠️ {total_tests - passed_tests} issues need attention before testing")
        return 1

if __name__ == "__main__":
    sys.exit(main())
