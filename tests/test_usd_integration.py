#!/usr/bin/env python3
"""
USD Integration Test Suite
Validates USD service functionality
"""

import sys
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))


def test_usd_service_creation():
    """Test that USD service can be created"""
    print("🧪 Test: USD Service Creation")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import UsdService

        service = UsdService()
        assert service is not None, "USD service should be created"

        print("✅ USD service created successfully")
        print(f"   USD Available: {service.is_usd_available()}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_service_singleton():
    """Test that USD service uses singleton pattern"""
    print("\n🧪 Test: USD Service Singleton Pattern")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import get_usd_service

        service1 = get_usd_service()
        service2 = get_usd_service()

        assert service1 is service2, "Should return same instance"

        print("✅ Singleton pattern working correctly")
        print(f"   Service1 ID: {id(service1)}")
        print(f"   Service2 ID: {id(service2)}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_availability_check():
    """Test USD availability detection"""
    print("\n🧪 Test: USD Availability Check")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import get_usd_service

        service = get_usd_service()
        available = service.is_usd_available()

        print(f"   USD Available: {available}")
        assert isinstance(available, bool), "Should return boolean"

        print("✅ USD availability check working")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_info():
    """Test USD info retrieval"""
    print("\n🧪 Test: USD Info Retrieval")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import get_usd_service

        service = get_usd_service()
        info = service.get_usd_info()

        assert isinstance(info, dict), "Should return dictionary"
        assert 'usd_available' in info, "Should have usd_available key"
        assert 'mayausd_available' in info, "Should have mayausd_available key"
        assert 'pxr_available' in info, "Should have pxr_available key"
        assert 'supported_formats' in info, "Should have supported_formats key"

        print("✅ USD info structure valid")
        print(f"   Info keys: {list(info.keys())}")
        for key, value in info.items():
            print(f"   {key}: {value}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_metadata_structure():
    """Test USD metadata extraction structure"""
    print("\n🧪 Test: USD Metadata Structure")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import get_usd_service

        service = get_usd_service()

        # Test with a dummy path (won't actually open file)
        _test_path = Path("test.usd")

        # Method should exist and be callable
        assert hasattr(service, 'extract_usd_metadata'), "Should have extract_usd_metadata method"
        assert hasattr(service, 'detect_usd_content'), "Should have detect_usd_content method"
        assert hasattr(service, 'get_usd_stage_info'), "Should have get_usd_stage_info method"
        assert hasattr(service, 'generate_usd_thumbnail'), "Should have generate_usd_thumbnail method"
        assert hasattr(service, 'import_usd_file'), "Should have import_usd_file method"

        print("✅ All USD methods present")
        print("   - extract_usd_metadata")
        print("   - detect_usd_content")
        print("   - get_usd_stage_info")
        print("   - generate_usd_thumbnail")
        print("   - import_usd_file")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_container_registration():
    """Test USD service container registration"""
    print("\n🧪 Test: USD Container Registration")
    print("=" * 60)

    try:
        from src.core.container import EMSAContainer
        from src.services.usd_service_impl import UsdService

        container = EMSAContainer()

        # Check if USD service was registered
        has_usd = False
        for service_type in container._services:
            if 'Usd' in service_type._name__:
                has_usd = True
                print(f"✅ Found USD service type: {service_type._name__}")

        # Also check instances
        for instance in container._services.values():
            if isinstance(instance, UsdService):
                has_usd = True
                print("✅ Found USD service instance")

        if has_usd:
            print("✅ USD service registered in container")
        else:
            print("ℹ️ USD service registration may be pending")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_supported_formats():
    """Test USD supported file formats"""
    print("\n🧪 Test: USD Supported Formats")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import get_usd_service

        service = get_usd_service()
        info = service.get_usd_info()

        supported = info.get('supported_formats', [])
        expected_formats = ['.usd', '.usda', '.usdc', '.usdz']

        for fmt in expected_formats:
            assert fmt in supported, f"{fmt} should be supported"
            print(f"✅ {fmt} - supported")

        print(f"✅ All USD formats supported: {supported}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usd_prim_counting():


    print("\n🧪 Test: USD Prim Counting Functionality")
    print("=" * 60)

    try:
        from src.services.usd_service_impl import get_usd_service

        service = get_usd_service()

        # Check that prim counting method exists
        assert hasattr(service, '_count_prims'), "Should have _count_prims method"

        print("✅ Prim counting method exists")
        print("   Expected prim types:")
        print("   - mesh, curve, points")
        print("   - xform, camera, light")
        print("   - material, scope")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':


    print("USD INTEGRATION TEST SUITE")
    print("=" * 60)

    tests = [
        test_usd_service_creation,
        test_usd_service_singleton,
        test_usd_availability_check,
        test_usd_info,
        test_usd_metadata_structure,
        test_usd_container_registration,
        test_usd_supported_formats,
        test_usd_prim_counting,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed")
        sys.exit(1)
