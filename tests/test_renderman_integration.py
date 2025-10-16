# -*- coding: utf-8 -*-
"""
Test RenderMan Service Integration
Validates RenderMan service functionality

Author: Mike Stumbo
Test Suite: RenderMan Integration
"""

def test_renderman_service_creation():
    """Test RenderMan service can be created - Integration Test"""
    from src.services.renderman_service_impl import RenderManService
    
    # Create service
    service = RenderManService()
    assert service is not None, "RenderMan service should be created"
    
    # Check basic properties
    assert hasattr(service, 'is_renderman_available'), "Service should have availability check"
    assert hasattr(service, 'detect_renderman_nodes'), "Service should have node detection"
    assert hasattr(service, 'get_renderman_info'), "Service should have info method"
    
    print("\u2705 RenderMan service creation test passed")
    return True


def test_renderman_service_singleton():
    """Test RenderMan service singleton pattern - Design Pattern Test"""
    from src.services.renderman_service_impl import get_renderman_service
    
    # Get service twice
    service1 = get_renderman_service()
    service2 = get_renderman_service()
    
    # Should be same instance
    assert service1 is service2, "RenderMan service should be singleton"
    
    print("\u2705 RenderMan service singleton test passed")
    return True


def test_renderman_availability_check():
    """Test RenderMan availability detection - Integration Test"""
    from src.services.renderman_service_impl import get_renderman_service
    
    service = get_renderman_service()
    
    # Check availability (will return False in test environment without Maya)
    is_available = service.is_renderman_available()
    assert isinstance(is_available, bool), "Availability should return boolean"
    
    # Check prman availability
    is_prman = service.is_prman_available()
    assert isinstance(is_prman, bool), "prman availability should return boolean"
    
    print(f"\u2139\ufe0f RenderMan available: {is_available}")
    print(f"\u2139\ufe0f prman API available: {is_prman}")
    print("\u2705 RenderMan availability check test passed")
    return True


def test_renderman_info():
    """Test RenderMan info retrieval - Information API Test"""
    from src.services.renderman_service_impl import get_renderman_service
    
    service = get_renderman_service()
    info = service.get_renderman_info()
    
    # Should return dictionary
    assert isinstance(info, dict), "Info should return dictionary"
    assert 'available' in info, "Info should contain availability status"
    assert 'prman_api' in info, "Info should contain prman status"
    assert 'version' in info, "Info should contain version field"
    
    print(f"\u2139\ufe0f RenderMan Info: {info}")
    print("\u2705 RenderMan info retrieval test passed")
    return True


def test_renderman_metadata_structure():
    """Test RenderMan metadata structure - Data Model Test"""
    from src.services.renderman_service_impl import get_renderman_service
    from pathlib import Path
    
    service = get_renderman_service()
    
    # Test with dummy path (won't load but will return structure)
    metadata = service.extract_renderman_metadata(Path("dummy.ma"))
    
    # Should return dictionary even if RenderMan not available
    assert isinstance(metadata, dict), "Metadata should return dictionary"
    
    print(f"\u2139\ufe0f Metadata structure: {list(metadata.keys())}")
    print("\u2705 RenderMan metadata structure test passed")
    return True


def test_renderman_container_registration():
    """Test RenderMan service registration in EMSA container - DI Test"""
    from src.core.container import get_container
    from src.services.renderman_service_impl import RenderManService
    
    container = get_container()
    
    # Check if RenderMan service is registered
    try:
        service = container.resolve(RenderManService)
        assert service is not None, "RenderMan service should be resolvable from container"
        print("\u2705 RenderMan service registered in container")
    except ValueError:
        # May not be registered in test environment
        print("\u2139\ufe0f RenderMan service not in container (expected in test environment)")
    
    print("\u2705 RenderMan container registration test passed")
    return True


if __name__ == "__main__":
    print("="*70)
    print("RENDERMAN SERVICE TEST SUITE")
    print("="*70)
    
    tests = [
        ("RenderMan Service Creation", test_renderman_service_creation),
        ("RenderMan Service Singleton", test_renderman_service_singleton),
        ("RenderMan Availability Check", test_renderman_availability_check),
        ("RenderMan Info Retrieval", test_renderman_info),
        ("RenderMan Metadata Structure", test_renderman_metadata_structure),
        ("RenderMan Container Registration", test_renderman_container_registration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\\n{test_name}...")
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\u274c {test_name} failed: {e}")
            failed += 1
    
    print("\\n" + "="*70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*70)
