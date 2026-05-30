"""Configuration providers for tool dependency injection."""

from typing import Protocol, Any, Callable
from teaagent.workspace_tools._files import WorkspaceToolConfig


class ToolConfigProvider(Protocol):
    """Protocol for tool configuration providers."""
    
    def get_config(self) -> WorkspaceToolConfig:
        """Get tool configuration.
        
        Returns:
            Current workspace tool configuration
        """
        ...


class StaticConfigProvider:
    """Static configuration provider.
    
    Provides a fixed configuration that doesn't change.
    """
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize static configuration provider.
        
        Args:
            config: Fixed workspace tool configuration
        """
        self._config = config
    
    def get_config(self) -> WorkspaceToolConfig:
        """Get static configuration.
        
        Returns:
            The fixed configuration
        """
        return self._config


class DynamicConfigProvider:
    """Dynamic configuration provider.
    
    Provides configuration that can change at runtime by calling a loader function.
    """
    
    def __init__(self, config_loader: Callable[[], WorkspaceToolConfig]):
        """Initialize dynamic configuration provider.
        
        Args:
            config_loader: Function that loads configuration on demand
        """
        self._config_loader = config_loader
    
    def get_config(self) -> WorkspaceToolConfig:
        """Get dynamic configuration.
        
        Returns:
            Configuration loaded from the loader function
        """
        return self._config_loader()
