# -*- coding: utf-8 -*-
"""
Event System Implementation
Concrete implementation of event publishing using Observer Pattern

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

import uuid
import threading
from typing import Any, Callable, Dict, List
from collections import defaultdict

from ..core.interfaces.event_publisher import IEventPublisher, EventType


class EventSystemImpl(IEventPublisher):
    """
    Event System Implementation - Single Responsibility for event management
    Implements Observer Pattern for loose coupling between components
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, Dict[str, Callable[[Dict[str, Any]], None]]] = defaultdict(dict)
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: EventType, callback: Callable[[Dict[str, Any]], None]) -> str:
        """
        Subscribe to specific event type
        Thread-safe subscription management
        """
        subscription_id = str(uuid.uuid4())
        
        with self._lock:
            self._subscribers[event_type][subscription_id] = callback
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from event notifications
        Thread-safe unsubscription
        """
        with self._lock:
            for event_type in self._subscribers:
                if subscription_id in self._subscribers[event_type]:
                    del self._subscribers[event_type][subscription_id]
                    return True
        
        return False
    
    def publish(self, event_type: EventType, event_data: Dict[str, Any]) -> None:
        """
        Publish event to all subscribers
        Thread-safe event publishing with error isolation
        """
        # Get snapshot of subscribers to avoid lock during callback execution
        with self._lock:
            subscribers = dict(self._subscribers[event_type])
        
        # Call subscribers outside of lock to prevent deadlocks
        for subscription_id, callback in subscribers.items():
            try:
                callback(event_data)
            except Exception as e:
                # Isolate subscriber errors - don't let one break others
                print(f"Error in event subscriber {subscription_id}: {e}")
                # Could add logging here
    
    def get_subscribers_count(self, event_type: EventType) -> int:
        """Get number of subscribers for event type"""
        with self._lock:
            return len(self._subscribers[event_type])
    
    def clear_all_subscriptions(self) -> None:
        """Clear all event subscriptions"""
        with self._lock:
            self._subscribers.clear()
