# ADR-001: Resolve Circular Dependencies Between approval_manager.py and policy.py

## Status
Proposed

## Context
The codebase has circular dependencies between `approval_manager.py` and `policy.py`:
- `policy.py` imports from `approval_manager.py` (line 18)
- `approval_manager.py` has TYPE_CHECKING imports from `ergonomics.approval_store` (line 23)
- `policy.py` creates an instance of `ApprovalManager` in its `__post_init__` (line 75-88)
- There are two separate `ApprovalManager` classes in different modules

This creates tight coupling and makes the code difficult to test and maintain.

## Decision
We will consolidate the two `ApprovalManager` classes into a single, unified implementation and remove the wrapper pattern in `ApprovalPolicy`.

### Implementation Plan

#### Phase 1: Consolidate ApprovalManager Classes
1. Identify differences between the two `ApprovalManager` implementations
2. Merge functionality into a single `ApprovalManager` class in `approval_manager.py`
3. Update all imports across the codebase to use the consolidated class
4. Remove the duplicate `ApprovalManager` from `runner/_approval_manager.py`

#### Phase 2: Refactor ApprovalPolicy
1. Remove the wrapper pattern from `ApprovalPolicy`
2. Make `ApprovalPolicy` a simple data container
3. Have the runner directly use the consolidated `ApprovalManager`
4. Update all callers to use the new pattern

#### Phase 3: Break Circular Dependencies
1. Move shared types to a separate module (e.g., `approval_types.py`)
2. Use dependency injection instead of direct instantiation
3. Add interface protocols for loose coupling

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before refactoring
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Reduced coupling, better testability, clearer architecture
- **Negative**: Breaking changes to public APIs, requires migration effort
- **Risk**: High - affects core approval workflow

## Alternatives Considered
1. Keep circular dependencies but document them (rejected - technical debt)
2. Use lazy imports to break the cycle (rejected - hides the problem)
3. Create a mediator pattern (rejected - adds complexity)

## References
- Original issue: Medium-severity architecture issue #1
- Related files: `approval_manager.py`, `policy.py`, `runner/_approval_manager.py`
