# -*- coding: utf-8 -*-
"""
Core Exceptions Module
Custom exceptions for the Asset Manager

Author: Mike Stumbo
Enterprise Refactoring: Clean Code & SOLID Principles
"""

from typing import Optional


class AssetManagerError(Exception):
    """Base exception class for Asset Manager"""
    pass


class AssetNotFoundError(AssetManagerError):
    """Exception raised when an asset cannot be found"""
    def __init__(self, asset_id: Optional[str] = None, message: Optional[str] = None):
        if message is None:
            if asset_id:
                message = f"Asset with ID '{asset_id}' not found"
            else:
                message = "Asset not found"
        super().__init__(message)
        self.asset_id = asset_id


class AssetValidationError(AssetManagerError):
    """Exception raised when asset validation fails"""
    pass


class RepositoryError(AssetManagerError):
    """Exception raised for repository-related errors"""
    pass
