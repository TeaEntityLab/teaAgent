"""Validator for backend adapter protocol compliance."""

from typing import Any
from teaagent.external_backends.knowledge import KnowledgeSearchBackend
from teaagent.external_backends.code_parse import CodeParseBackend


class BackendAdapterValidator:
    """Validator for backend adapter protocol compliance."""
    
    @staticmethod
    def validate_knowledge_backend(
        backend: Any,
    ) -> tuple[bool, list[str]]:
        """Validate knowledge backend compliance.
        
        Args:
            backend: Backend instance to validate
            
        Returns:
            Tuple of (is_valid: bool, errors: list[str])
        """
        errors = []
        
        # Check required methods
        required_methods = ['search', 'initialize', 'shutdown', 'check_health']
        for method in required_methods:
            if not hasattr(backend, method):
                errors.append(f'Missing required method: {method}')
        
        # Check method signatures
        if hasattr(backend, 'search'):
            import inspect
            sig = inspect.signature(backend.search)
            params = list(sig.parameters.keys())
            if 'query' not in params or 'root' not in params:
                errors.append('search method must have query and root parameters')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_code_parse_backend(
        backend: Any,
    ) -> tuple[bool, list[str]]:
        """Validate code parse backend compliance.
        
        Args:
            backend: Backend instance to validate
            
        Returns:
            Tuple of (is_valid: bool, errors: list[str])
        """
        errors = []
        
        # Check required methods
        required_methods = ['parse', 'initialize', 'shutdown', 'check_health']
        for method in required_methods:
            if not hasattr(backend, method):
                errors.append(f'Missing required method: {method}')
        
        # Check method signatures
        if hasattr(backend, 'parse'):
            import inspect
            sig = inspect.signature(backend.parse)
            params = list(sig.parameters.keys())
            if 'path' not in params or 'root' not in params:
                errors.append('parse method must have path and root parameters')
        
        return len(errors) == 0, errors
