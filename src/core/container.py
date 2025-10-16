# -*- coding: utf-8 -*-
"""
Enterprise Modular Service Architecture (EMSA) Container
Implements Dependency Injection pattern for clean architecture.
"""

from typing import Dict, Any, Type, TypeVar, Optional
import threading

T = TypeVar('T')


class EMSAContainer:
    """
    Service container implementing dependency injection pattern.
    Manages service registration and resolution.
    """
    
    def __init__(self):
        """Initialize the service container."""
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Any] = {}
        self._lock = threading.Lock()
        self._register_default_services()
    
    def _register_default_services(self) -> None:
        """Register default services."""
        try:
            # Register the plugin service first
            from .services.plugin_service import PluginService
            from .interfaces.iplugin_service import IPluginService
            self.register_singleton(IPluginService, PluginService)
            
            # Now register all other essential services using the robust factory
            self._configure_essential_services()
            
        except ImportError as e:
            print(f"⚠️ Could not register some EMSA services: {e}")
            # Register minimal services for fallback
            try:
                from .services.plugin_service import PluginService
                from .interfaces.iplugin_service import IPluginService
                self.register_singleton(IPluginService, PluginService)
            except ImportError:
                print("⚠️ Could not register plugin service")
    
    def _configure_essential_services(self) -> None:
        """Configure essential services using the robust factory."""
        try:
            from .interfaces.asset_repository import IAssetRepository
            from .interfaces.event_publisher import IEventPublisher
            from .interfaces.thumbnail_service import IThumbnailService
            from .interfaces.library_service import ILibraryService
            from ..services.renderman_service_impl import get_renderman_service
            from ..services.usd_service_impl import get_usd_service
            from ..services.ngskintools_service_impl import get_ngskintools_service
            
            # Use the existing service factory if available
            try:
                from .service_factory import get_service_factory
                factory = get_service_factory()
                services = factory.get_all_services()
                
                # Register services from factory
                if 'asset_repository' in services:
                    self.register_instance(IAssetRepository, services['asset_repository'])
                else:
                    # Fallback to direct registration
                    from .repositories.file_asset_repository import FileAssetRepository
                    self.register_singleton(IAssetRepository, FileAssetRepository)
                
                if 'thumbnail_service' in services:
                    self.register_instance(IThumbnailService, services['thumbnail_service'])
                
                if 'event_publisher' in services:
                    self.register_instance(IEventPublisher, services['event_publisher'])
                
                # Register RenderMan service (always available, checks internally)
                try:
                    renderman_service = get_renderman_service()
                    self.register_instance(type(renderman_service), renderman_service)
                    if renderman_service.is_renderman_available():
                        print("✅ RenderMan service registered and available")
                    else:
                        print("ℹ️ RenderMan service registered (RenderMan not detected)")
                except Exception as rm_error:
                    print(f"⚠️ RenderMan service registration failed: {rm_error}")
                
                # Register USD service (always available, checks internally)
                try:
                    usd_service = get_usd_service()
                    self.register_instance(type(usd_service), usd_service)
                    if usd_service.is_usd_available():
                        print("✅ USD service registered and available")
                    else:
                        print("ℹ️ USD service registered (USD not detected)")
                except Exception as usd_error:
                    print(f"⚠️ USD service registration failed: {usd_error}")
                
                # Register ngSkinTools2 service (always available, checks internally)
                try:
                    ngskintools_service = get_ngskintools_service()
                    self.register_instance(type(ngskintools_service), ngskintools_service)
                    if ngskintools_service.is_available():
                        print("✅ ngSkinTools2 service registered and available")
                    else:
                        print("ℹ️ ngSkinTools2 service registered (ngSkinTools2 not detected)")
                except Exception as ngst_error:
                    print(f"⚠️ ngSkinTools2 service registration failed: {ngst_error}")
                    
                print("✅ Essential EMSA services registered")
                
            except ImportError:
                # Direct registration as fallback
                from .repositories.file_asset_repository import FileAssetRepository
                self.register_singleton(IAssetRepository, FileAssetRepository)
                print("✅ Core services registered (direct)")
            
            # Register Library Service AFTER repository is registered (always runs)
            # This is outside the try-except to ensure it always executes
            try:
                from ..services.library_service_impl import LibraryServiceImpl
                # Get repository (either from factory or fallback)
                repo = self.resolve(IAssetRepository)
                library_service = LibraryServiceImpl(repo)
                self.register_instance(ILibraryService, library_service)
                print("✅ Library service registered")
            except Exception as lib_error:
                print(f"⚠️ Library service registration failed: {lib_error}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"⚠️ Could not configure essential services: {e}")
    
    def register(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register a service implementation for an interface.
        
        Args:
            interface: The interface type
            implementation: The implementation type
        """
        with self._lock:
            self._services[interface] = implementation
    
    def register_singleton(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register a singleton service implementation.
        
        Args:
            interface: The interface type
            implementation: The implementation type
        """
        with self._lock:
            self._services[interface] = implementation
            self._singletons[interface] = None
    
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """
        Register an existing instance as a service.
        
        Args:
            interface: The interface type
            instance: The existing instance to register
        """
        with self._lock:
            self._singletons[interface] = instance
    
    def get(self, interface: Type[T]) -> Optional[T]:
        """
        Resolve a service by its interface.
        
        Args:
            interface: The interface type to resolve
            
        Returns:
            The service instance or None if not found
        """
        with self._lock:
            if interface not in self._services:
                return None
            
            # Check if it's a singleton
            if interface in self._singletons:
                if self._singletons[interface] is None:
                    # Create singleton instance
                    implementation = self._services[interface]
                    self._singletons[interface] = implementation()
                return self._singletons[interface]
            
            # Create new instance
            implementation = self._services[interface]
            return implementation()
    
    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve service instance by interface
        
        Args:
            interface: Service interface to resolve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service not registered
        """
        # Check for pre-registered instance
        if interface in self._singletons:
            return self._singletons[interface]
        
        # Check for singleton service
        if interface in self._services:
            with self._lock:
                if interface not in self._singletons:
                    implementation_class = self._services[interface]
                    self._singletons[interface] = implementation_class()
                return self._singletons[interface]
        
        # Check for transient service
        if interface in self._factories:
            return self._factories[interface]()
        
        raise ValueError(f"Service {interface.__name__} not registered")
    
    def is_registered(self, interface: Type[T]) -> bool:
        """
        Check if service is registered
        
        Args:
            interface: Service interface to check
            
        Returns:
            True if service is registered
        """
        return (interface in self._services or 
                interface in self._factories or 
                interface in self._singletons)
    
    def clear(self) -> None:
        """Clear all registered services"""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._singletons.clear()
    
    def get_registered_services(self) -> Dict[str, str]:
        """
        Get list of all registered services
        
        Returns:
            Dictionary of interface names to registration types
        """
        services = {}
        
        for interface in self._singletons.keys():
            services[interface.__name__] = "instance"
        
        for interface in self._services.keys():
            services[interface.__name__] = "singleton"
        
        for interface in self._factories.keys():
            services[interface.__name__] = "transient"
        
        return services


# Type alias for backward compatibility and cleaner type annotations
ServiceContainer = EMSAContainer

# Global service container instance
_container: Optional[ServiceContainer] = None
_container_lock = threading.Lock()


def get_container() -> ServiceContainer:
    """
    Get global service container instance (Singleton pattern)
    
    Returns:
        Global ServiceContainer instance
    """
    global _container
    
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = ServiceContainer()
    
    return _container


def configure_services() -> ServiceContainer:
    """
    Configure all services in the container with robust error handling
    This function will be called during application startup
    
    Returns:
        Configured service container
    """
    container = get_container()
    
    # Clear any existing registrations
    container.clear()
    
    try:
        # Import the actual interface classes that the UI expects
        from .interfaces.asset_repository import IAssetRepository
        from .interfaces.event_publisher import IEventPublisher
        from .interfaces.thumbnail_service import IThumbnailService
        from .interfaces.library_service import ILibraryService
        
        # Use the robust service factory
        from .service_factory import get_service_factory
        factory = get_service_factory()
        
        print("🔧 Configuring services...")
        
        # Get all available services (skip validation to improve startup time)
        services = factory.get_all_services()
        
        # Register available services as instances using actual interface classes
        if 'thumbnail_service' in services:
            container.register_instance(IThumbnailService, services['thumbnail_service'])
            print("✅ Registered thumbnail service")
        else:
            print("⚠️ Creating fallback thumbnail service")
            fallback_service = _create_fallback_thumbnail_service()
            container.register_instance(IThumbnailService, fallback_service)
        
        if 'asset_repository' in services:
            container.register_instance(IAssetRepository, services['asset_repository'])
            print("✅ Registered asset repository")
        
        if 'event_publisher' in services:
            container.register_instance(IEventPublisher, services['event_publisher'])
            print("✅ Registered event publisher")
        else:
            # Ensure event publisher is always available - create fallback
            print("⚠️ Event publisher not available from factory - creating fallback")
            fallback_event_publisher = _create_fallback_event_publisher()
            container.register_instance(IEventPublisher, fallback_event_publisher)
            print("✅ Registered fallback event publisher")
        
        # Register Library Service (depends on asset repository)
        try:
            from ..services.library_service_impl import LibraryServiceImpl
            # Get the repository that was just registered
            repo = container.resolve(IAssetRepository)
            library_service = LibraryServiceImpl(repo)
            container.register_instance(ILibraryService, library_service)
            print("✅ Registered library service")
        except Exception as lib_error:
            print(f"⚠️ Failed to register library service: {lib_error}")
            import traceback
            traceback.print_exc()
        
        print(f"🎯 Successfully configured {len(services)} services")
        return container
        
    except Exception as e:
        print(f"❌ Error configuring services: {e}")
        print("🔄 Creating minimal fallback container...")
        
        # Create minimal working container
        return _configure_fallback_services(container)


def _configure_fallback_services(container: ServiceContainer) -> ServiceContainer:
    """
    Configure minimal fallback services when main configuration fails
    Single Responsibility: fallback service configuration
    """
    try:
        # Import the actual interface classes
        from .interfaces.asset_repository import IAssetRepository
        from .interfaces.event_publisher import IEventPublisher
        from .interfaces.thumbnail_service import IThumbnailService
        from .interfaces.library_service import ILibraryService
        
        # Create fallback implementations
        thumbnail_service = _create_fallback_thumbnail_service()
        asset_repository = _create_fallback_asset_repository()
        event_publisher = _create_fallback_event_publisher()
        
        # Register fallback services
        container.register_instance(IThumbnailService, thumbnail_service)
        container.register_instance(IAssetRepository, asset_repository)
        container.register_instance(IEventPublisher, event_publisher)
        
        # Register Library Service with fallback repository
        try:
            from ..services.library_service_impl import LibraryServiceImpl
            library_service = LibraryServiceImpl(asset_repository)
            container.register_instance(ILibraryService, library_service)
            print("✅ Fallback library service configured")
        except Exception as lib_error:
            print(f"⚠️ Failed to configure fallback library service: {lib_error}")
        
        print("✅ Fallback services configured")
        return container
        
    except Exception as e:
        print(f"❌ Failed to configure fallback services: {e}")
        return container


def _create_fallback_thumbnail_service():
    """Create minimal fallback thumbnail service"""
    class FallbackThumbnailService:
        def generate_thumbnail(self, file_path, size=(64, 64)):
            print(f"📁 Fallback: No thumbnail for {file_path}")
            return None
        
        def get_cached_thumbnail(self, file_path, size=(64, 64)):
            return None
        
        def is_thumbnail_supported(self, file_path):
            return True
    
    return FallbackThumbnailService()


def _create_fallback_asset_repository():
    """Create minimal fallback asset repository"""
    from .interfaces.asset_repository import IAssetRepository
    
    class FallbackAssetRepository(IAssetRepository):
        def find_all(self, directory):
            from pathlib import Path
            assets = []
            if directory.exists():
                for file_path in directory.rglob('*'):
                    if file_path.is_file():
                        # Create minimal asset-like object
                        assets.append(type('Asset', (), {
                            'id': str(file_path),
                            'name': file_path.name,
                            'file_path': file_path,
                            'display_name': file_path.name,
                            'is_favorite': False
                        })())
            return assets
        
        # Add missing abstract method implementations as stubs
        def find_by_id(self, asset_id):
            return None
        
        def find_by_criteria(self, criteria):
            return []
        
        def save(self, asset):
            pass
        
        def update(self, asset_id, updates):
            pass
        
        def delete(self, asset_id):
            pass
        
        def exists(self, asset_id):
            return False
        
        def get_all(self):
            return []
        
        def count(self):
            return 0
        
        def clear(self):
            pass
        
        # Added missing abstract methods as stubs
        def get_recent_assets(self, limit=10):
            return []
        
        def get_favorites(self):
            return []
        
        def add_favorite(self, asset_id):
            pass
        
        def remove_favorite(self, asset_id):
            pass
        
        def is_favorite(self, asset_id):
            return False
        
        def get_categories(self):
            return []
        
        def get_assets_by_category(self, category):
            return []
        
        # Renamed and implemented to match interface
        def add_to_favorites(self, asset):
            return True
        
        def remove_from_favorites(self, asset):
            return True
        
        # Added stub implementations for the missing abstract methods
        def update_access_time(self, asset):
            pass
        
        def remove_asset(self, asset):
            return True
        
        def add_asset(self, asset):
            pass
        
        # Add the missing abstract method implementation
        def get_assets_from_directory(self, directory):
            """Get assets from the specified directory."""
            from pathlib import Path
            return self.find_all(Path(directory))
    
    return FallbackAssetRepository()


def _create_fallback_event_publisher():
    """Create enhanced fallback event publisher - SOLID: Interface Segregation"""
    class FallbackEventPublisher:
        """Enhanced event publisher implementation for fallback scenarios"""
        
        def __init__(self):
            self._subscribers = {}
        
        def publish(self, event_type, event_data=None):
            """Publish event - enhanced implementation matching IEventPublisher"""
            if event_data is None:
                event_data = {}
            print(f"📢 Fallback Event: {event_type} with data: {event_data}")
            
            # Try to call any registered subscribers
            if hasattr(event_type, 'value'):
                event_key = event_type.value
            else:
                event_key = str(event_type)
            
            if event_key in self._subscribers:
                for callback in self._subscribers[event_key]:
                    try:
                        callback(event_data)
                    except Exception as e:
                        print(f"⚠️ Fallback event subscriber error: {e}")
            
        def subscribe(self, event_type, callback):
            """Subscribe to event - enhanced implementation"""
            if hasattr(event_type, 'value'):
                event_key = event_type.value
            else:
                event_key = str(event_type)
            
            if event_key not in self._subscribers:
                self._subscribers[event_key] = []
            self._subscribers[event_key].append(callback)
            
            return f"fallback_sub_{len(self._subscribers[event_key])}"
            
        def unsubscribe(self, subscription_id):
            """Unsubscribe from event - enhanced implementation"""
            # Simple implementation for fallback
            return True
            
        def get_subscribers_count(self, event_type):
            """Get subscriber count - IEventPublisher interface compatibility"""
            if hasattr(event_type, 'value'):
                event_key = event_type.value
            else:
                event_key = str(event_type)
            return len(self._subscribers.get(event_key, []))
            
        def clear_all_subscriptions(self):
            """Clear all subscriptions - IEventPublisher interface compatibility"""
            self._subscribers.clear()
    
    return FallbackEventPublisher()
