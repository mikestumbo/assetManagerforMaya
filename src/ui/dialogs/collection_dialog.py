# -*- coding: utf-8 -*-
"""
Collection Dialog - Placeholder implementation
"""

class CollectionDialog:
    def __init__(self, parent=None):
        self.parent = parent
        self._collection_name = "New Collection"
        print("Collection Dialog initialized")
    
    def exec(self) -> bool:
        print("Collection Dialog executed")
        return True
    
    def get_collection_name(self) -> str:
        return self._collection_name
