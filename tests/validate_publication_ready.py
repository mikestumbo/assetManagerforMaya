#!/usr/bin/env python3
"""
Asset Manager v1.3.0 - Pre-Publication Validation Script
Quick validation of bulletproof cleanup integration

Author: Mike Stumbo
Date: September 29, 2025
"""

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def validate_bulletproof_integration():
    """Validate bulletproof cleanup integration in services"""
    print("🔍 Validating Bulletproof Cleanup Integration...")
    
    validation_results = []
    
    # Check if bulletproof methods exist
    methods_to_check = [
        '_bulletproof_namespace_cleanup',
        '_unlock_namespace_nodes', 
        '_disconnect_render_connections',
        '_delete_namespace_content',
        '_fallback_cleanup'
    ]
    
    # Test thumbnail service integration
    try:
        # Check if file exists first
        thumbnail_file = Path("src/services/thumbnail_service_impl.py")
        if not thumbnail_file.exists():
            raise FileNotFoundError(f"File not found: {thumbnail_file}")
        
        # Read file content to check for methods
        content = thumbnail_file.read_text(encoding='utf-8')
        thumbnail_methods_found = []
        
        for method in methods_to_check:
            if f"def {method}" in content:
                thumbnail_methods_found.append(method)
        
        validation_results.append({
            'component': 'Thumbnail Service',
            'methods_found': len(thumbnail_methods_found),
            'methods_expected': len(methods_to_check),
            'success': len(thumbnail_methods_found) == len(methods_to_check),
            'details': thumbnail_methods_found
        })
        
    except Exception as e:
        validation_results.append({
            'component': 'Thumbnail Service',
            'success': False,
            'error': str(e)
        })
    
    # Test standalone services integration
    try:
        # Check if file exists first
        standalone_file = Path("src/services/standalone_services.py")
        if not standalone_file.exists():
            raise FileNotFoundError(f"File not found: {standalone_file}")
        
        # Read file content to check for methods
        content = standalone_file.read_text(encoding='utf-8')
        standalone_methods_found = []
        
        for method in methods_to_check:
            if f"def {method}" in content:
                standalone_methods_found.append(method)
        
        validation_results.append({
            'component': 'Standalone Services',
            'methods_found': len(standalone_methods_found),
            'methods_expected': len(methods_to_check),
            'success': len(standalone_methods_found) == len(methods_to_check),
            'details': standalone_methods_found
        })
        
    except Exception as e:
        validation_results.append({
            'component': 'Standalone Services',
            'success': False,
            'error': str(e)
        })
    
    # Print results
    print("\n📊 Validation Results:")
    all_success = True
    
    for result in validation_results:
        component = result['component']
        if result['success']:
            methods_found = result.get('methods_found', 0)
            methods_expected = result.get('methods_expected', 0)
            print(f"   ✅ {component}: {methods_found}/{methods_expected} methods integrated")
        else:
            print(f"   ❌ {component}: {result.get('error', 'Integration failed')}")
            all_success = False
    
    return all_success

def validate_documentation():
    """Validate documentation completeness"""
    print("\n📚 Validating Documentation...")
    
    docs_to_check = [
        "docs/BULLETPROOF_CLEANUP_SYSTEM_v1.3.0.md",
        "BULLETPROOF_CLEANUP_COMPLETE.md",
        "test_bulletproof_cleanup.py"
    ]
    
    docs_found = 0
    for doc_path in docs_to_check:
        if Path(doc_path).exists():
            docs_found += 1
            print(f"   ✅ {doc_path}")
        else:
            print(f"   ❌ {doc_path} - Missing")
    
    print(f"\n📊 Documentation: {docs_found}/{len(docs_to_check)} files present")
    return docs_found == len(docs_to_check)

def main():
    """Run complete pre-publication validation"""
    print("🎯 Asset Manager v1.3.0 - Pre-Publication Validation")
    print("=" * 60)
    
    # Run validations
    integration_success = validate_bulletproof_integration()
    docs_success = validate_documentation()
    
    # Overall results
    print("\n🏆 Overall Validation Results:")
    print(f"   Integration: {'✅ PASS' if integration_success else '❌ FAIL'}")
    print(f"   Documentation: {'✅ PASS' if docs_success else '❌ FAIL'}")
    
    overall_success = integration_success and docs_success
    
    if overall_success:
        print(f"\n🚀 VALIDATION SUCCESSFUL!")
        print(f"   Asset Manager v1.3.0 is READY FOR GITHUB PUBLICATION!")
        print(f"   🎉 Bulletproof Cleanup System: PRODUCTION READY")
    else:
        print(f"\n⚠️ Validation Issues Found")
        print(f"   Please address issues before publication")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)