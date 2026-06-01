# ADR 0013: Add Abstraction Layer for Backend Systems

## Status
Implemented

## Context
The `external_backends.py` module uses global module-level dictionaries to manage backend registration:
```python
_KNOWLEDGE_BACKENDS: dict[str, KnowledgeSearchBackend] = {}
_CODE_PARSE_BACKENDS: dict[str, CodeParseBackend] = {}
```

This creates hidden global state that makes testing difficult and creates implicit dependencies. There's no abstraction layer for backend discovery or lifecycle management.

## Decision
We will create a `BackendRegistry` class to encapsulate backend management with proper lifecycle support.

### Implementation Plan

#### Phase 1: Create BackendRegistry Class
1. Create `BackendRegistry` class to encapsulate backend management
2. Move global dictionaries to instance variables
3. Add methods for registration, retrieval, and lifecycle management
4. Add unit tests for the registry

#### Phase 2: Implement BackendFactory Interface
1. Create `BackendFactory` protocol/interface for creating backend instances
2. Implement factory methods for each backend type
3. Add unit tests for each factory
4. Update registration to use factories

#### Phase 3: Add Lifecycle Management
1. Create `BackendLifecycle` interface for initialization/shutdown
2. Implement lifecycle hooks for each backend
3. Add integration tests for lifecycle management
4. Update registry to manage backend lifecycles

#### Phase 4: Create BackendHealthCheck Interface
1. Create `BackendHealthCheck` protocol for monitoring backend status
2. Implement health checks for each backend
3. Add unit tests for health checks
4. Update registry to support health monitoring

#### Phase 5: Use Dependency Injection
1. Update all components to accept `BackendRegistry` as a parameter
2. Create a singleton registry instance for backward compatibility
3. Add integration tests for the new pattern
4. Update all callers to use dependency injection

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before refactoring
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Better testability, explicit dependencies, lifecycle management
- **Negative**: Breaking changes to backend registration API
- **Risk**: Medium - affects backend system initialization

## Alternatives Considered
1. Keep global dictionaries (rejected - hidden state, hard to test)
2. Use service locator pattern (rejected - hidden dependencies)
3. Use framework-level dependency injection (rejected - over-engineering)

## References
- Original issue: Medium-severity architecture issue #4
- Related files: `external_backends.py`
