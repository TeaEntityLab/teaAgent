"""Base class and configuration for backend adapters."""

from typing import Protocol, Any, Optional
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass


@dataclass
class BackendConfig:
    """Configuration for backend adapters."""
    
    root: Path
    timeout: int = 30
    max_retries: int = 3
    additional_config: dict[str, Any] | None = None


class BackendAdapter(ABC):
    """Base class for backend adapters with consistent interface."""
    
    def __init__(self, config: BackendConfig):
        """Initialize backend adapter with consistent configuration.
        
        Args:
            config: Backend configuration
        """
        self._config = config
        self._initialized = False
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize backend adapter."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown backend adapter."""
        pass
    
    @abstractmethod
    def check_health(self) -> tuple[bool, str]:
        """Check backend health.
        
        Returns:
            Tuple of (healthy: bool, message: str)
        """
        pass
    
    def is_initialized(self) -> bool:
        """Check if adapter is initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized
    
    def get_config(self) -> BackendConfig:
        """Get adapter configuration.
        
        Returns:
            Backend configuration
        """
        return self._config
