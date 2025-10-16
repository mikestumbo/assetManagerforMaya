# -*- coding: utf-8 -*-
"""
Event Publisher Interface
Defines event system operations following Observer Pattern

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles  
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List
from enum import Enum


class EventType(Enum):
    """Event types for the asset manager system"""
    ASSET_SELECTED = "asset_selected"
    ASSET_IMPORTED = "asset_imported" 
    ASSET_FAVORITED = "asset_favorited"
    ASSET_UNFAVORITED = "asset_unfavorited"
    SEARCH_PERFORMED = "search_performed"
    THUMBNAIL_GENERATED = "thumbnail_generated"
    LIBRARY_REFRESHED = "library_refreshed"
    ERROR_OCCURRED = "error_occurred"


class IEventPublisher(ABC):
    """
    Event Publisher Interface - Single Responsibility for event management
    Implements Observer Pattern for loose coupling between components
    """
    
    @abstractmethod
    def subscribe(self, event_type: EventType, callback: Callable[[Dict[str, Any]], None]) -> str:
        """
        Subscribe to specific event type
        
        Args:
            event_type: Type of event to listen for
            callback: Function to call when event occurs
            
        Returns:
            Subscription ID for later unsubscription
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from event notifications
        
        Args:
            subscription_id: ID returned from subscribe()
            
        Returns:
            True if unsubscription was successful
        """
        pass
    
    @abstractmethod
    def publish(self, event_type: EventType, event_data: Dict[str, Any]) -> None:
        """
        Publish event to all subscribers
        
        Args:
            event_type: Type of event being published
            event_data: Data associated with the event
        """
        pass
    
    @abstractmethod
    def get_subscribers_count(self, event_type: EventType) -> int:
        """
        Get number of subscribers for event type
        
        Args:
            event_type: Event type to check
            
        Returns:
            Number of active subscribers
        """
        pass
    
    @abstractmethod
    def clear_all_subscriptions(self) -> None:
        """
        Clear all event subscriptions
        """
        pass
