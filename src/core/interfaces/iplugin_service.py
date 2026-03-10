"""
Plugin Service Interface
Defines the contract for plugin services in EMSA architecture.
"""

from abc import ABC, abstractmethod


class IPluginService(ABC):
    """
    Interface for plugin services.
    Follows Interface Segregation Principle.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin service.

        Returns:
            bool: True if initialization successful, False otherwise
        """

    @abstractmethod
    def shutdown(self) -> bool:
        """
        Shutdown the plugin service.

        Returns:
            bool: True if shutdown successful, False otherwise
        """

    @abstractmethod
    def get_version(self) -> str:
        """
        Get the plugin version.

        Returns:
            str: Version string
        """
