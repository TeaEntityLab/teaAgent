# Proposal: Add Abstraction Layer for Backend Systems

> **⚠️ OBSOLETED:** This proposal describes work that has already been implemented. See the corresponding module docs under `docs/modules/` for current state. The associated ADR status has been updated to "Implemented".

## Executive Summary
This proposal outlines a plan to create an abstraction layer for backend systems by implementing a `BackendRegistry` class to encapsulate backend management with proper lifecycle support.

## Problem Statement

### Current State
The `external_backends.py` module uses global module-level dictionaries to manage backend registration:
```python
_KNOWLEDGE_BACKENDS: dict[str, KnowledgeSearchBackend] = {}
_CODE_PARSE_BACKENDS: dict[str, CodeParseBackend] = {}
```

This creates:
- **Hidden Global State**: Global dictionaries create implicit dependencies
- **Testing Difficulty**: Hard to test with mock implementations
- **Lifecycle Management**: No support for backend initialization/shutdown
- **Health Monitoring**: No mechanism for monitoring backend health

### Impact
- **Global State**: Hidden global state makes testing difficult
- **No Lifecycle**: No support for backend initialization/shutdown
- **No Health Checks**: No mechanism for monitoring backend health
- **Extensibility**: Difficult to add new backend types

## Proposed Solution

### Phase 1: Create BackendRegistry Class
1. **Create Class**: Create `BackendRegistry` class to encapsulate backend management
2. **Move Global State**: Move global dictionaries to instance variables
3. **Add Methods**: Add methods for registration, retrieval, and lifecycle management
4. **Add Tests**: Add unit tests for the registry

### Phase 2: Implement BackendFactory Interface
1. **Create Interface**: Create `BackendFactory` protocol/interface
2. **Implement Factories**: Implement factory methods for each backend type
3. **Add Tests**: Add unit tests for each factory
4. **Update Registration**: Update registration to use factories

### Phase 3: Add Lifecycle Management
1. **Create Interface**: Create `BackendLifecycle` interface
2. **Implement Hooks**: Implement lifecycle hooks for each backend
3. **Add Tests**: Add unit tests for lifecycle management
4. **Update Registry**: Update registry to manage backend lifecycles

### Phase 4: Create BackendHealthCheck Interface
1. **Create Interface**: Create `BackendHealthCheck` protocol
2. **Implement Checks**: Implement health checks for each backend
3. **Add Tests**: Add unit tests for health checks
4. **Update Registry**: Update registry to support health monitoring

### Phase 5: Use Dependency Injection
1. **Update Components**: Update all components to accept `BackendRegistry` as parameter
2. **Create Singleton**: Create singleton registry instance for backward compatibility
3. **Add Tests**: Add integration tests for the new pattern
4. **Update Callers**: Update all callers to use dependency injection

## Implementation Details

### BackendRegistry
```python
# external_backends/registry.py
from typing import Protocol, Any
from teaagent.external_backends import KnowledgeSearchBackend, CodeParseBackend

class BackendRegistry:
    """Registry for backend systems with lifecycle management."""
    
    def __init__(self):
        """Initialize backend registry."""
        self._knowledge_backends: dict[str, KnowledgeSearchBackend] = {}
        self._code_parse_backends: dict[str, CodeParseBackend] = {}
        self._factories: dict[str, BackendFactory] = {}
    
    def register_knowledge_backend(
        self,
        name: str,
        backend: KnowledgeSearchBackend,
    ) -> None:
        """Register knowledge backend."""
        self._knowledge_backends[name] = backend
    
    def register_code_parse_backend(
        self,
        name: str,
        backend: CodeParseBackend,
    ) -> None:
        """Register code parse backend."""
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
        """Initialize all backends."""
        for backend in self._knowledge_backends.values():
            if hasattr(backend, 'initialize'):
                backend.initialize()
        for backend in self._code_parse_backends.values():
            if hasattr(backend, 'initialize'):
                backend.initialize()
    
    def shutdown_all(self) -> None:
        """Shutdown all backends."""
        for backend in self._knowledge_backends.values():
            if hasattr(backend, 'shutdown'):
                backend.shutdown()
        for backend in self._code_parse_backends.values():
            if hasattr(backend, 'shutdown'):
                backend.shutdown()
```

### BackendFactory Interface
```python
# external_backends/factory.py
from typing import Protocol, Any
from teaagent.external_backends import KnowledgeSearchBackend, CodeParseBackend

class BackendFactory(Protocol):
    """Protocol for backend factories."""
    
    def create(self, config: dict[str, Any]) -> KnowledgeSearchBackend | CodeParseBackend:
        """Create backend instance."""
        ...

class KnowledgeBackendFactory:
    """Factory for knowledge backends."""
    
    def create(self, config: dict[str, Any]) -> KnowledgeSearchBackend:
        """Create knowledge backend instance."""
        backend_type = config.get('type')
        if backend_type == 'local':
            return LocalKnowledgeAdapter(config)
        elif backend_type == 'qmd':
            return QmdMcpAdapter(config)
        else:
            raise ValueError(f'Unknown backend type: {backend_type}')

class CodeParseBackendFactory:
    """Factory for code parse backends."""
    
    def create(self, config: dict[str, Any]) -> CodeParseBackend:
        """Create code parse backend instance."""
        backend_type = config.get('type')
        if backend_type == 'tree-sitter':
            return TreeSitterAdapter(config)
        else:
            raise ValueError(f'Unknown backend type: {backend_type}')
```

### BackendLifecycle Interface
```python
# external_backends/lifecycle.py
from typing import Protocol

class BackendLifecycle(Protocol):
    """Protocol for backend lifecycle management."""
    
    def initialize(self) -> None:
        """Initialize backend."""
        ...
    
    def shutdown(self) -> None:
        """Shutdown backend."""
        ...

class LifecycleAwareBackend:
    """Mixin for lifecycle-aware backends."""
    
    def initialize(self) -> None:
        """Initialize backend (default no-op)."""
        pass
    
    def shutdown(self) -> None:
        """Shutdown backend (default no-op)."""
        pass
```

### BackendHealthCheck Interface
```python
# external_backends/health.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class HealthStatus:
    """Health status of backend."""
    healthy: bool
    message: str
    details: dict[str, Any] | None = None

class BackendHealthCheck(Protocol):
    """Protocol for backend health checks."""
    
    def check_health(self) -> HealthStatus:
        """Check backend health."""
        ...

class HealthCheckBackend:
    """Mixin for health-checkable backends."""
    
    def check_health(self) -> HealthStatus:
        """Check backend health (default healthy)."""
        return HealthStatus(healthy=True, message='OK')
```

### Refactored Backend Registration
```python
# external_backends/__init__.py
from teaagent.external_backends.registry import BackendRegistry

# Singleton registry for backward compatibility
_default_registry = BackendRegistry()

def register_knowledge_backend(
    name: str,
    backend: KnowledgeSearchBackend,
) -> None:
    """Register knowledge backend (backward compatible)."""
    _default_registry.register_knowledge_backend(name, backend)

def register_code_parse_backend(
    name: str,
    backend: CodeParseBackend,
) -> None:
    """Register code parse backend (backward compatible)."""
    _default_registry.register_code_parse_backend(name, backend)

def get_knowledge_backend(
    name: str,
) -> KnowledgeSearchBackend | None:
    """Get knowledge backend (backward compatible)."""
    return _default_registry.get_knowledge_backend(name)

def get_code_parse_backend(
    name: str,
) -> CodeParseBackend | None:
    """Get code parse backend (backward compatible)."""
    return _default_registry.get_code_parse_backend(name)

def get_default_registry() -> BackendRegistry:
    """Get default backend registry."""
    return _default_registry
```

## Migration Plan

### Step 1: Create BackendRegistry
1. Create `BackendRegistry` class
2. Move global dictionaries to instance variables
3. Add unit tests for registry
4. Update module to use registry

### Step 2: Create BackendFactory
1. Create `BackendFactory` interface
2. Implement factories for each backend type
3. Add unit tests for each factory
4. Update registration to use factories

### Step 3: Add Lifecycle Management
1. Create `BackendLifecycle` interface
2. Implement lifecycle hooks for each backend
3. Add unit tests for lifecycle management
4. Update registry to manage lifecycles

### Step 4: Add Health Checks
1. Create `BackendHealthCheck` interface
2. Implement health checks for each backend
3. Add unit tests for health checks
4. Update registry to support health monitoring

### Step 5: Update Callers
1. Update callers to accept `BackendRegistry` parameter
2. Create singleton registry for backward compatibility
3. Add integration tests for new pattern
4. Update documentation

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep global functions working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for lifecycle management
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for backend health

## Timeline

### Phase 1: Create BackendRegistry (1 week)
- Week 1: Create registry, move global state, add tests

### Phase 2: Implement BackendFactory (1 week)
- Week 2: Create factories, add tests, update registration

### Phase 3: Add Lifecycle Management (1 week)
- Week 3: Create lifecycle interface, add tests, update registry

### Phase 4: Add Health Checks (1 week)
- Week 4: Create health check interface, add tests, update registry

### Phase 5: Update Callers (1 week)
- Week 5: Update callers, add tests, verify all tests pass

### Phase 6: Documentation (1 week)
- Week 6: Update documentation, create migration guide

## Success Criteria

- ✅ No global module-level state
- ✅ BackendRegistry encapsulates all backend management
- ✅ Lifecycle management supported
- ✅ Health checks supported
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Global Dictionaries
- **Pros**: No changes required
- **Cons**: Hidden state, hard to test
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Service Locator Pattern
- **Pros**: Minimal code changes
- **Cons**: Hidden dependencies, hard to track
- **Decision**: Rejected - dependency injection is more explicit

### Alternative 3: Use Framework-Level Dependency Injection
- **Pros**: Automatic dependency resolution
- **Cons**: Over-engineering, adds dependency
- **Decision**: Rejected - simpler solution available

## References
- ADR 0013: Add abstraction layer for backend systems
- Current implementation in `external_backends.py`
- Backend system best practices
