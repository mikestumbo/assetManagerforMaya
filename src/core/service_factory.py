# -*- coding: utf-8 -*-
"""
Service Factory - Robust Service Creation
Handles service creation with proper error handling and fallbacks

Author: Mike Stumbo
Clean Code: Factory Pattern with error resilience
SOLID: Single Responsibility for service instantiation
"""

import sys
from pathlib import Path
from typing import Optional, Any, Dict, Type

# Add robust import path handling
sys.path.insert(0, str(Path(__file__).parent.parent))

from .import_helper import ImportHelper


class ServiceFactory:
    """
    Service Factory - Single Responsibility for creating services
    Implements Factory Pattern with error handling
    """
    
    def __init__(self):
        self._service_cache: Dict[str, Any] = {}
        
    def create_thumbnail_service(self) -> Optional[Any]:
        """
        Create thumbnail service with fallback handling
        
        Returns:
            ThumbnailService instance or None
        """
        if 'thumbnail_service' in self._service_cache:
            return self._service_cache['thumbnail_service']
        
        try:
            # Direct import of thumbnail service implementation (full-featured service)
            import sys
            from pathlib import Path
            
            # Get direct path to thumbnail service implementation
            services_file = Path(__file__).parent.parent / "services" / "thumbnail_service_impl.py"
            
            # Load module directly using importlib
            import importlib.util
            spec = importlib.util.spec_from_file_location("thumbnail_service_impl", services_file)
            if spec and spec.loader:
                thumbnail_service_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(thumbnail_service_module)
                
                # Create the full-featured service
                service = thumbnail_service_module.ThumbnailServiceImpl()
                self._service_cache['thumbnail_service'] = service
                print("✅ Full-featured thumbnail service created via direct import")
                return service
            else:
                print("❌ Could not load thumbnail service implementation module")
                return None
                
        except Exception as e:
            print(f"❌ Failed to create thumbnail service: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_asset_repository(self) -> Optional[Any]:
        """
        Create asset repository with dependency injection
        
        Returns:
            AssetRepository instance or None
        """
        if 'asset_repository' in self._service_cache:
            return self._service_cache['asset_repository']
        
        try:
            # Direct import of standalone services file
            import importlib.util
            from pathlib import Path
            
            # Get direct path to standalone services
            services_file = Path(__file__).parent.parent / "services" / "standalone_services.py"
            
            # Load module directly
            spec = importlib.util.spec_from_file_location("standalone_services", services_file)
            if spec and spec.loader:
                standalone_services = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(standalone_services)
                
                # Create repository
                repository = standalone_services.StandaloneAssetRepository()
                self._service_cache['asset_repository'] = repository
                print("✅ Standalone asset repository created via direct import")
                return repository
            else:
                print("❌ Could not load standalone services module")
                return None
                
        except Exception as e:
            print(f"❌ Failed to create asset repository: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_metadata_extractor(self) -> Optional[Any]:
        """
        Create metadata extractor service
        
        Returns:
            MetadataExtractor instance or None
        """
        if 'metadata_extractor' in self._service_cache:
            return self._service_cache['metadata_extractor']
        
        try:
            extractor_class = ImportHelper.get_class_from_module(
                'services.metadata_extractor_impl',
                'MetadataExtractorImpl'
            )
            
            if extractor_class:
                extractor = extractor_class()
                self._service_cache['metadata_extractor'] = extractor
                print("✅ Metadata extractor created successfully")
                return extractor
            else:
                print("❌ Could not find MetadataExtractorImpl class")
                return None
                
        except Exception as e:
            print(f"❌ Failed to create metadata extractor: {e}")
            return None
    
    def create_event_publisher(self) -> Optional[Any]:
        """
        Create event publisher service
        
        Returns:
            EventPublisher instance or None
        """
        if 'event_publisher' in self._service_cache:
            return self._service_cache['event_publisher']
        
        try:
            # Strategy 1: Try fast relative import first (most common case)
            try:
                from ..services.event_system_impl import EventSystemImpl
                publisher = EventSystemImpl()
                self._service_cache['event_publisher'] = publisher
                print("✅ Event publisher created via relative import")
                return publisher
            except ImportError:
                pass
            
            # Strategy 2: Use standalone event publisher (reliable fallback)
            try:
                import importlib.util
                from pathlib import Path
                
                # Get direct path to standalone services
                standalone_file = Path(__file__).parent.parent / "services" / "standalone_services.py"
                
                if standalone_file.exists():
                    # Load module directly
                    spec = importlib.util.spec_from_file_location("standalone_services", standalone_file)
                    if spec and spec.loader:
                        standalone_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(standalone_module)
                        
                        # Create standalone event publisher
                        publisher = standalone_module.StandaloneEventPublisher()
                        self._service_cache['event_publisher'] = publisher
                        print("✅ Event publisher created using standalone service")
                        return publisher
                        
            except Exception as standalone_error:
                print(f"⚠️ Standalone event publisher failed: {standalone_error}")
            
            print("❌ Event publisher creation failed")
            return None
                
        except Exception as e:
            print(f"❌ Failed to create event publisher: {e}")
            return None
    
    def get_all_services(self) -> Dict[str, Any]:
        """
        Get all available services
        
        Returns:
            Dictionary of service name to instance
        """
        services = {}
        
        # Try to create each service
        thumbnail_service = self.create_thumbnail_service()
        if thumbnail_service:
            services['thumbnail_service'] = thumbnail_service
        
        asset_repository = self.create_asset_repository()
        if asset_repository:
            services['asset_repository'] = asset_repository
        
        event_publisher = self.create_event_publisher()
        if event_publisher:
            services['event_publisher'] = event_publisher
        
        return services
    
    def validate_services(self) -> bool:
        """
        Validate that core services can be created
        
        Returns:
            True if core services are available
        """
        core_services = ['thumbnail_service', 'asset_repository']
        services = self.get_all_services()
        
        available_services = [name for name in core_services if name in services]
        missing_services = [name for name in core_services if name not in services]
        
        print(f"✅ Available services: {', '.join(available_services)}")
        if missing_services:
            print(f"❌ Missing services: {', '.join(missing_services)}")
        
        return len(missing_services) == 0


# Global service factory instance
_service_factory: Optional[ServiceFactory] = None


def get_service_factory() -> ServiceFactory:
    """
    Get global service factory instance
    
    Returns:
        ServiceFactory instance
    """
    global _service_factory
    if _service_factory is None:
        _service_factory = ServiceFactory()
    return _service_factory
