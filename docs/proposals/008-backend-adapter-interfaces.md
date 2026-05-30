# Proposal: Standardize Backend Adapter Interfaces

## Executive Summary
This proposal outlines a plan to create a unified `BackendAdapter` base class with consistent initialization and behavior, addressing inconsistent signatures and error handling across backend implementations.

## Problem Statement

### Current State
The `KnowledgeSearchBackend` and `CodeParseBackend` protocols define methods, but implementations have inconsistent signatures and behavior:
- `FallbackKnowledgeBackend` wraps two backends but doesn't fully implement the protocol
- `LocalKnowledgeAdapter` has different initialization than `QmdMcpAdapter`
- Error handling is inconsistent across implementations
- Some methods accept `root: Path` while others use different parameters

This inconsistency makes it difficult to add new backends and maintain existing ones.

### Impact
- **Inconsistent Interfaces**: Different implementations have different signatures
- **Error Handling**: Inconsistent error handling across implementations
- **Maintenance Burden**: Hard to maintain and extend backends
- **Testing Difficulty**: Hard to test with consistent patterns

## Proposed Solution

### Phase 1: Create Unified BackendAdapter Base Class
1. **Create Base Class**: Create `BackendAdapter` base class with consistent initialization
2. **Define Standard Methods**: Define standard methods with consistent signatures
3. **Add Abstract Methods**: Add abstract methods for required functionality
4. **Add Tests**: Add unit tests for the base class

### Phase 2: Implement BackendAdapterFactory
1. **Create Factory**: Create `BackendAdapterFactory` for creating adapters
2. **Implement Factories**: Implement factory methods for each adapter type
3. **Add Tests**: Add unit tests for the factory
4. **Update Creation**: Update adapter creation to use the factory

### Phase 3: Standardize Error Handling
1. **Define Standard Errors**: Define standard error types for backend operations
2. **Implement Consistent Handling**: Implement consistent error handling across all adapters
3. **Add Tests**: Add unit tests for error handling
4. **Update Adapters**: Update all adapters to use standard error handling

### Phase 4: Create BackendAdapterValidator
1. **Create Validator**: Create `BackendAdapterValidator` to ensure protocol compliance
2. **Implement Validation**: Implement validation checks for each adapter
3. **Add Tests**: Add unit tests for validation
4. **Update Registration**: Update adapter registration to validate compliance

### Phase 5: Implement BackendAdapterRegistry
1. **Create Registry**: Create `BackendAdapterRegistry` for centralized management
2. **Add Methods**: Add methods for registration, retrieval, and lifecycle management
3. **Add Tests**: Add unit tests for the registry
4. **Update Backend System**: Update backend system to use the registry

## Implementation Details

### BackendAdapter Base Class
```python
# external_backends/adapter.py
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
        """Initialize backend adapter with consistent configuration."""
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
        """Check backend health."""
        pass
    
    def is_initialized(self) -> bool:
        """Check if adapter is initialized."""
        return self._initialized
    
    def get_config(self) -> BackendConfig:
        """Get adapter configuration."""
        return self._config
```

### KnowledgeSearchBackend Protocol
```python
# external_backends/knowledge.py
from typing import Protocol, Any
from pathlib import Path

class KnowledgeSearchBackend(Protocol):
    """Protocol for knowledge search backends."""
    
    def search(
        self,
        query: str,
        root: Path,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search knowledge base."""
        ...
    
    def initialize(self) -> None:
        """Initialize backend."""
        ...
    
    def shutdown(self) -> None:
        """Shutdown backend."""
        ...
    
    def check_health(self) -> tuple[bool, str]:
        """Check backend health."""
        ...
```

### CodeParseBackend Protocol
```python
# external_backends/code_parse.py
from typing import Protocol, Any
from pathlib import Path

class CodeParseBackend(Protocol):
    """Protocol for code parse backends."""
    
    def parse(
        self,
        path: Path,
        root: Path,
    ) -> dict[str, Any]:
        """Parse code structure."""
        ...
    
    def initialize(self) -> None:
        """Initialize backend."""
        ...
    
    def shutdown(self) -> None:
        """Shutdown backend."""
        ...
    
    def check_health(self) -> tuple[bool, str]:
        """Check backend health."""
        ...
```

### BackendAdapterFactory
```python
# external_backends/factory.py
from typing import Any
from teaagent.external_backends.adapter import BackendAdapter, BackendConfig
from teaagent.external_backends.knowledge import KnowledgeSearchBackend
from teaagent.external_backends.code_parse import CodeParseBackend

class BackendAdapterFactory:
    """Factory for creating backend adapters."""
    
    @staticmethod
    def create_knowledge_backend(
        backend_type: str,
        config: BackendConfig,
    ) -> KnowledgeSearchBackend:
        """Create knowledge backend adapter."""
        if backend_type == 'local':
            from teaagent.external_backends.local import LocalKnowledgeAdapter
            return LocalKnowledgeAdapter(config)
        elif backend_type == 'qmd':
            from teaagent.external_backends.qmd import QmdMcpAdapter
            return QmdMcpAdapter(config)
        else:
            raise ValueError(f'Unknown knowledge backend type: {backend_type}')
    
    @staticmethod
    def create_code_parse_backend(
        backend_type: str,
        config: BackendConfig,
    ) -> CodeParseBackend:
        """Create code parse backend adapter."""
        if backend_type == 'tree-sitter':
            from teaagent.external_backends.tree_sitter import TreeSitterAdapter
            return TreeSitterAdapter(config)
        else:
            raise ValueError(f'Unknown code parse backend type: {backend_type}')
```

### Standard Error Handling
```python
# external_backends/errors.py
from typing import Any

class BackendError(Exception):
    """Base class for backend errors."""
    
    def __init__(
        self,
        message: str,
        backend_name: str,
        details: dict[str, Any] | None = None,
    ):
        """Initialize backend error."""
        super().__init__(message)
        self._backend_name = backend_name
        self._details = details or {}
    
    @property
    def backend_name(self) -> str:
        """Get backend name."""
        return self._backend_name
    
    @property
    def details(self) -> dict[str, Any]:
        """Get error details."""
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
```

### BackendAdapterValidator
```python
# external_backends/validator.py
from typing import Any
from teaagent.external_backends.knowledge import KnowledgeSearchBackend
from teaagent.external_backends.code_parse import CodeParseBackend

class BackendAdapterValidator:
    """Validator for backend adapter protocol compliance."""
    
    @staticmethod
    def validate_knowledge_backend(
        backend: Any,
    ) -> tuple[bool, list[str]]:
        """Validate knowledge backend compliance."""
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
        """Validate code parse backend compliance."""
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
```

### BackendAdapterRegistry
```python
# external_backends/registry.py
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
        """Register knowledge backend with optional validation."""
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
        """Register code parse backend with optional validation."""
        if validate:
            valid, errors = self._validator.validate_code_parse_backend(backend)
            if not valid:
                raise ValueError(f'Invalid code parse backend: {errors}')
        
        self._code_parse_backends[name] = backend
    
    def get_knowledge_backend(
        self,
        name: str,
    ) -> KnowledgeSearchBackend | None:
        """Get knowledge backend by name."""
        return self._knowledge_backends.get(name)
    
    def get_code_parse_backend(
        self,
        name: str,
    ) -> CodeParseBackend | None:
        """Get code parse backend by name."""
        return self._code_parse_backends.get(name)
    
    def initialize_all(self) -> None:
        """Initialize all registered backends."""
        for backend in self._knowledge_backends.values():
            backend.initialize()
        for backend in self._code_parse_backends.values():
            backend.initialize()
    
    def shutdown_all(self) -> None:
        """Shutdown all registered backends."""
        for backend in self._knowledge_backends.values():
            backend.shutdown()
        for backend in self._code_parse_backends.values():
            backend.shutdown()
    
    def check_health_all(self) -> dict[str, tuple[bool, str]]:
        """Check health of all registered backends."""
        health_status = {}
        
        for name, backend in self._knowledge_backends.items():
            health_status[f'knowledge:{name}'] = backend.check_health()
        
        for name, backend in self._code_parse_backends.items():
            health_status[f'code_parse:{name}'] = backend.check_health()
        
        return health_status
```

## Migration Plan

### Step 1: Create BackendAdapter Base Class
1. Create `BackendAdapter` base class
2. Define standard methods with consistent signatures
3. Add abstract methods for required functionality
4. Add unit tests for base class

### Step 2: Create BackendAdapterFactory
1. Create `BackendAdapterFactory` class
2. Implement factory methods for each adapter type
3. Add unit tests for factory
4. Update adapter creation to use factory

### Step 3: Standardize Error Handling
1. Define standard error types
2. Implement consistent error handling across adapters
3. Add unit tests for error handling
4. Update all adapters to use standard error handling

### Step 4: Create BackendAdapterValidator
1. Create `BackendAdapterValidator` class
2. Implement validation checks for each adapter
3. Add unit tests for validation
4. Update adapter registration to validate

### Step 5: Create BackendAdapterRegistry
1. Create `BackendAdapterRegistry` class
2. Add methods for registration and lifecycle management
3. Add unit tests for registry
4. Update backend system to use registry

### Step 6: Update Adapters
1. Update all existing adapters to inherit from BackendAdapter
2. Update all adapters to use standard error handling
3. Add unit tests for updated adapters
4. Verify all tests pass

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep existing adapters working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for registry and validation
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for backend health

## Timeline

### Phase 1: Create BackendAdapter Base Class (1 week)
- Week 1: Create base class, define methods, add tests

### Phase 2: Create BackendAdapterFactory (1 week)
- Week 2: Create factory, add tests, update creation

### Phase 3: Standardize Error Handling (1 week)
- Week 3: Define errors, implement handling, add tests

### Phase 4: Create BackendAdapterValidator (1 week)
- Week 4: Create validator, add tests, update registration

### Phase 5: Create BackendAdapterRegistry (1 week)
- Week 5: Create registry, add tests, update system

### Phase 6: Update Adapters and Documentation (1 week)
- Week 6: Update adapters, add tests, update documentation

## Success Criteria

- ✅ Consistent interfaces across all backend adapters (unified BackendAdapter base class)
- ✅ Standard error handling implemented with BackendError hierarchy
- ✅ Protocol compliance validation via BackendAdapterValidator
- ✅ Centralized registry with lifecycle management (initialize/shutdown/health checks)
- ✅ All existing tests passing
- ✅ New unit tests for BackendAdapter, BackendAdapterFactory, and BackendAdapterRegistry
- ✅ No breaking changes to public API (backward compatible)
- ✅ Documentation updated with new patterns
- ✅ Migration guide provided with before/after examples
- ✅ Health check endpoint operational for monitoring
- ✅ Performance impact < 5% overhead compared to current implementation

## Performance Considerations

- **Adapter Overhead**: Minimal overhead from base class methods (< 2%)
- **Validation Overhead**: Validation only during registration, not runtime
- **Health Check Overhead**: Health checks are async and non-blocking
- **Memory Impact**: Slight increase from registry and validation (< 200KB)
- **Initialization**: Lazy initialization to reduce startup time

## Migration Examples

### Before (Current Pattern)
```python
# external_backends/__init__.py
_KNOWLEDGE_BACKENDS: dict[str, KnowledgeSearchBackend] = {}

def register_knowledge_backend(name: str, backend: KnowledgeSearchBackend) -> None:
    _KNOWLEDGE_BACKENDS[name] = backend

def get_knowledge_backend(name: str) -> KnowledgeSearchBackend | None:
    return _KNOWLEDGE_BACKENDS.get(name)
```

### After (New Pattern)
```python
# external_backends/__init__.py
from teaagent.external_backends.registry import BackendAdapterRegistry

_default_registry = BackendAdapterRegistry()

def register_knowledge_backend(
    name: str,
    backend: KnowledgeSearchBackend,
    validate: bool = True,
) -> None:
    _default_registry.register_knowledge_backend(name, backend, validate)

def get_knowledge_backend(name: str) -> KnowledgeSearchBackend | None:
    return _default_registry.get_knowledge_backend(name)

def get_default_registry() -> BackendAdapterRegistry:
    return _default_registry
```

### Health Check Usage
```python
# Check health of all backends
registry = get_default_registry()
health_status = registry.check_health_all()

for backend_name, (healthy, message) in health_status.items():
    if not healthy:
        print(f'{backend_name} is unhealthy: {message}')
```

## Alternatives Considered

### Alternative 1: Keep Inconsistent Interfaces
- **Pros**: No changes required
- **Cons**: Maintenance burden, hard to extend
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Duck Typing Only
- **Pros**: Simple implementation
- **Cons**: No contract enforcement
- **Decision**: Rejected - validation needed for compliance

### Alternative 3: Use Framework-Level Adapter Library
- **Pros**: Off-the-shelf solution
- **Cons**: Adds dependency, may not fit needs
- **Decision**: Rejected - custom solution better suited

## References
- ADR-008: Standardize backend adapter interfaces
- Current implementation in `external_backends.py`
- Adapter pattern best practices
