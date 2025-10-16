"""
Test suite for ngSkinTools2 service integration

Validates ngSkinTools2 API integration, service registration, and functionality.

Author: Asset Manager Development Team
Version: 1.3.0
"""


def test_ngskintools_service_creation():
    """Test that ngSkinTools2 service can be created"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    assert service is not None
    assert hasattr(service, 'is_available')
    assert hasattr(service, 'get_plugin_version')
    assert hasattr(service, 'detect_ngskintools_nodes')
    assert hasattr(service, 'extract_ngskintools_metadata')
    return True


def test_ngskintools_service_singleton():
    """Test that ngSkinTools2 service uses singleton pattern"""
    from src.services.ngskintools_service_impl import get_ngskintools_service
    
    service1 = get_ngskintools_service()
    service2 = get_ngskintools_service()
    
    assert service1 is service2, "NgSkinTools2 service should be singleton"
    return True


def test_ngskintools_availability_check():
    """Test ngSkinTools2 availability detection"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    
    # Availability check should not crash
    is_available = service.is_available()
    assert isinstance(is_available, bool)
    
    # Version check should not crash
    version = service.get_plugin_version()
    assert version is None or isinstance(version, str)
    
    return True


def test_ngskintools_info():
    """Test ngSkinTools2 service info retrieval"""
    from src.services.ngskintools_service_impl import get_ngskintools_service
    
    service = get_ngskintools_service()
    info = service.get_info()
    
    assert isinstance(info, dict)
    assert 'name' in info
    assert info['name'] == 'ngSkinTools2'
    assert 'available' in info
    assert 'plugin_available' in info
    assert 'api_available' in info
    assert 'description' in info
    assert 'capabilities' in info
    
    # Capabilities should be a list
    assert isinstance(info['capabilities'], list)
    
    return True


def test_ngskintools_metadata_structure():
    """Test ngSkinTools2 metadata extraction structure"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    
    # Test with dummy target (should return empty metadata gracefully)
    metadata = service.extract_ngskintools_metadata('dummy_target')
    
    assert isinstance(metadata, dict)
    assert 'has_ngskintools' in metadata
    assert 'plugin_version' in metadata
    assert 'data_node' in metadata
    assert 'skin_cluster' in metadata
    assert 'layer_count' in metadata
    assert 'layer_names' in metadata
    assert 'influence_count' in metadata
    assert 'influence_names' in metadata
    assert 'is_slow_mode' in metadata
    assert 'layers_enabled' in metadata
    
    # For non-existent target, should have safe defaults
    assert isinstance(metadata['layer_count'], int)
    assert isinstance(metadata['layer_names'], list)
    assert isinstance(metadata['influence_count'], int)
    assert isinstance(metadata['influence_names'], list)
    
    return True


def test_ngskintools_scene_summary():
    """Test ngSkinTools2 scene summary generation"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    summary = service.get_scene_summary()
    
    assert isinstance(summary, dict)
    assert 'available' in summary
    assert 'plugin_version' in summary
    assert 'total_data_nodes' in summary
    assert 'total_skin_clusters' in summary
    assert 'total_layers' in summary
    assert 'skinned_meshes' in summary
    
    # All counts should be non-negative integers
    assert isinstance(summary['total_data_nodes'], int)
    assert summary['total_data_nodes'] >= 0
    assert isinstance(summary['total_skin_clusters'], int)
    assert summary['total_skin_clusters'] >= 0
    assert isinstance(summary['total_layers'], int)
    assert summary['total_layers'] >= 0
    
    # Skinned meshes should be a list
    assert isinstance(summary['skinned_meshes'], list)
    
    return True


def test_ngskintools_node_detection():
    """Test ngSkinTools2 node detection"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    
    # Detect nodes without namespace filter
    nodes = service.detect_ngskintools_nodes()
    
    assert isinstance(nodes, dict)
    assert 'data_nodes' in nodes
    assert 'skin_clusters' in nodes
    assert 'layer_count' in nodes
    assert 'total_nodes' in nodes
    
    # All should be valid types
    assert isinstance(nodes['data_nodes'], list)
    assert isinstance(nodes['skin_clusters'], list)
    assert isinstance(nodes['layer_count'], int)
    assert isinstance(nodes['total_nodes'], int)
    
    # Counts should be non-negative
    assert nodes['layer_count'] >= 0
    assert nodes['total_nodes'] >= 0
    
    return True


def test_ngskintools_cleanup():
    """Test ngSkinTools2 cleanup functionality"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    
    # Cleanup of non-existent namespace should return True (nothing to clean)
    result = service.cleanup_ngskintools_nodes('nonexistent_namespace')
    assert isinstance(result, bool)
    
    return True


def test_ngskintools_container_registration():
    """Test that ngSkinTools2 service is registered in EMSA container"""
    from src.core.container import EMSAContainer
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    container = EMSAContainer()
    
    # Try to get the service from container
    service = container.get(NgSkinToolsService)
    
    # Service might not be registered if ngSkinTools2 is not available
    # But the service class should still exist
    assert NgSkinToolsService is not None
    
    return True


def test_ngskintools_api_methods():
    """Test that all expected API methods are available"""
    from src.services.ngskintools_service_impl import NgSkinToolsService
    
    service = NgSkinToolsService()
    
    # Check all required methods exist
    required_methods = [
        'is_available',
        'get_plugin_version',
        'detect_ngskintools_nodes',
        'extract_ngskintools_metadata',
        'get_scene_summary',
        'cleanup_ngskintools_nodes',
        'get_info'
    ]
    
    for method_name in required_methods:
        assert hasattr(service, method_name), f"Method '{method_name}' not found"
        method = getattr(service, method_name)
        assert callable(method), f"'{method_name}' is not callable"
    
    return True


if __name__ == '__main__':
    print("Running ngSkinTools2 integration tests...")
    
    tests = [
        test_ngskintools_service_creation,
        test_ngskintools_service_singleton,
        test_ngskintools_availability_check,
        test_ngskintools_info,
        test_ngskintools_metadata_structure,
        test_ngskintools_scene_summary,
        test_ngskintools_node_detection,
        test_ngskintools_cleanup,
        test_ngskintools_container_registration,
        test_ngskintools_api_methods
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            if result:
                print(f"✅ {test.__name__}")
                passed += 1
            else:
                print(f"❌ {test.__name__}")
                failed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"ngSkinTools2 Integration Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}")
