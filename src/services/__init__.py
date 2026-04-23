# -*- coding: utf-8 -*-
"""
Services Package - Service Implementations
Concrete implementations following Dependency Inversion Principle

Author: Mike Stumbo
"""

# Lazy imports to avoid circular dependency issues in Maya context
# Import modules only when explicitly accessed

__all__ = [
    "AssetRepositoryImpl",
    "MetadataExtractorImpl",
    "ThumbnailServiceImpl",
    "MayaIntegrationImpl",
    "EventSystemImpl",
    "UsdService",
]


def __getattr__(name):
    """Lazy import services to avoid circular dependencies"""
    if name == "AssetRepositoryImpl":
        from .asset_repository_impl import AssetRepositoryImpl

        return AssetRepositoryImpl
    elif name == "MetadataExtractorImpl":
        from .metadata_extractor_impl import MetadataExtractorImpl

        return MetadataExtractorImpl
    elif name == "ThumbnailServiceImpl":
        from .thumbnail_service_impl import ThumbnailServiceImpl

        return ThumbnailServiceImpl
    elif name == "MayaIntegrationImpl":
        from .maya_integration_impl import MayaIntegrationImpl

        return MayaIntegrationImpl
    elif name == "EventSystemImpl":
        from .event_system_impl import EventSystemImpl

        return EventSystemImpl
    elif name == "UsdService":
        from .usd_service_impl import UsdService

        return UsdService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
