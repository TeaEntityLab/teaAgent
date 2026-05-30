"""Registry for backend adapters with validation and lifecycle management."""

from typing import Any
from teaagent.external_backends.knowledge import KnowledgeSearchBackend
from teaagent.external_backends.code_parse import CodeParseBackend
from teaagent.external_backends.validator import BackendAdapterValidator


class BackendAdapterRegistry:
    """Registry for backend adapters with validation and lifecycle management."""
    
    def __init__(self):
        """Initialize backend adapter registry."""
        self._knowledge_backends: dict[str, KnowledgeSearchBackend] = {}
        self._code_parse_backends: dict[str, CodeParseBackend] = {}
        self._validator = BackendAdapterValidator()
    
    def register_knowledge_backend(
        self,
        name: str,
        backend: KnowledgeSearchBackend,
        validate: bool = True,
    ) -> None:
        """Register knowledge backend with optional validation.
        
        Args:
            name: Backend name
            backend: Backend instance
            validate: Whether to validate protocol compliance
            
        Raises:
            ValueError: If validation fails
        """
        if validate:
            valid, errors = self._validator.validate_knowledge_backend(backend)
            if not valid:
                raise ValueError(f'Invalid knowledge backend: {errors}')
        
        self._knowledge_backends[name] = backend
    
    def register_code_parse_backend(
        self,
        name: str,
        backend: CodeParseBackend,
        validate: bool = True,
    ) -> None:
        """Register code parse backend with optional validation.
        
        Args:
            name: Backend name
            backend: Backend instance
            validate: Whether to validate protocol compliance
            
        Raises:
            ValueError: If validation fails
        """
        if validate:
            valid, errors = self._validator.validate_code_parse_backend(backend)
            if not valid:
                raise ValueError(f'Invalid code parse backend: {errors}')
        
        self._code_parse_backends[name] = backend
    
    def get_knowledge_backend(
        self,
        name: str,
    ) -> KnowledgeSearchBackend | None:
        """Get knowledge backend by name.
        
        Args:
            name: Backend name
            
        Returns:
            Backend instance or None if not found
        """
        return self._knowledge_backends.get(name)
    
    def get_code_parse_backend(
        self,
        name: str,
    ) -> CodeParseBackend | None:
        """Get code parse backend by name.
        
        Args:
            name: Backend name
            
        Returns:
            Backend instance or None if not found
        """
        return self._code_parse_backends.get(name)
    
    def initialize_all(self) -> None:
        """Initialize all registered backends."""
        for backend in self._knowledge_backends.values():
            if hasattr(backend, 'initialize'):
                backend.initialize()
        for backend in self._code_parse_backends.values():
            if hasattr(backend, 'initialize'):
                backend.initialize()
    
    def shutdown_all(self) -> None:
        """Shutdown all registered backends."""
        for backend in self._knowledge_backends.values():
            if hasattr(backend, 'shutdown'):
                backend.shutdown()
        for backend in self._code_parse_backends.values():
            if hasattr(backend, 'shutdown'):
                backend.shutdown()
    
    def check_health_all(self) -> dict[str, tuple[bool, str]]:
        """Check health of all registered backends.
        
        Returns:
            Dictionary mapping backend names to (healthy, message) tuples
        """
        health_status = {}
        
        for name, backend in self._knowledge_backends.items():
            if hasattr(backend, 'check_health'):
                health_status[f'knowledge:{name}'] = backend.check_health()
            else:
                health_status[f'knowledge:{name}'] = (True, 'No health check method')
        
        for name, backend in self._code_parse_backends.items():
            if hasattr(backend, 'check_health'):
                health_status[f'code_parse:{name}'] = backend.check_health()
            else:
                health_status[f'code_parse:{name}'] = (True, 'No health check method')
        
        return health_status
