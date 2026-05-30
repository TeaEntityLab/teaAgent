"""Standard error types for backend operations."""

from typing import Any


class BackendError(Exception):
    """Base class for backend errors."""
    
    def __init__(
        self,
        message: str,
        backend_name: str,
        details: dict[str, Any] | None = None,
    ):
        """Initialize backend error.
        
        Args:
            message: Error message
            backend_name: Name of the backend
            details: Additional error details
        """
        super().__init__(message)
        self._backend_name = backend_name
        self._details = details or {}
    
    @property
    def backend_name(self) -> str:
        """Get backend name.
        
        Returns:
            Backend name
        """
        return self._backend_name
    
    @property
    def details(self) -> dict[str, Any]:
        """Get error details.
        
        Returns:
            Error details dictionary
        """
        return self._details


class BackendInitializationError(BackendError):
    """Error during backend initialization."""
    pass


class BackendExecutionError(BackendError):
    """Error during backend execution."""
    pass


class BackendHealthCheckError(BackendError):
    """Error during backend health check."""
    pass
