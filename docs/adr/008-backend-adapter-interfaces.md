# ADR-008: Standardize Backend Adapter Interfaces

## Status
Proposed

## Context
The `KnowledgeSearchBackend` and `CodeParseBackend` protocols define methods, but implementations have inconsistent signatures and behavior:
- `FallbackKnowledgeBackend` wraps two backends but doesn't fully implement the protocol
- `LocalKnowledgeAdapter` has different initialization than `QmdMcpAdapter`
- Error handling is inconsistent across implementations
- Some methods accept `root: Path` while others use different parameters

This inconsistency makes it difficult to add new backends and maintain existing ones.

## Decision
We will create a unified `BackendAdapter` base class with consistent initialization and behavior.

### Implementation Plan

#### Phase 1: Create Unified BackendAdapter Base Class
1. Create `BackendAdapter` base class with consistent initialization
2. Define standard methods with consistent signatures
3. Add abstract methods for required functionality
4. Add unit tests for the base class

#### Phase 2: Implement BackendAdapterFactory
1. Create `BackendAdapterFactory` for creating adapters
2. Implement factory methods for each adapter type
3. Add unit tests for the factory
4. Update adapter creation to use the factory

#### Phase 3: Standardize Error Handling
1. Define standard error types for backend operations
2. Implement consistent error handling across all adapters
3. Add unit tests for error handling
4. Update all adapters to use standard error handling

#### Phase 4: Create BackendAdapterValidator
1. Create `BackendAdapterValidator` to ensure protocol compliance
2. Implement validation checks for each adapter
3. Add unit tests for validation
4. Update adapter registration to validate compliance

#### Phase 5: Implement BackendAdapterRegistry
1. Create `BackendAdapterRegistry` for centralized management
2. Add methods for registration, retrieval, and lifecycle management
3. Add unit tests for the registry
4. Update backend system to use the registry

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before refactoring
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Consistent interfaces, easier to add new backends, better error handling
- **Negative**: Breaking changes to backend adapter APIs
- **Risk**: Medium - affects backend system

## Alternatives Considered
1. Keep inconsistent interfaces (rejected - maintenance burden)
2. Use duck typing only (rejected - no contract enforcement)
3. Use framework-level adapter library (rejected - adds dependency)

## References
- Original issue: Medium-severity architecture issue #8
- Related files: `external_backends.py`
