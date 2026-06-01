# Proposal: Resolve Circular Dependencies Between approval_manager.py and policy.py

## Executive Summary
This proposal outlines a plan to resolve circular dependencies between `approval_manager.py` and `policy.py` by consolidating duplicate `ApprovalManager` classes and removing the wrapper pattern in `ApprovalPolicy`.

## Problem Statement

### Current State
- `policy.py` imports from `approval_manager.py` (line 18)
- `approval_manager.py` has TYPE_CHECKING imports from `ergonomics.approval_store` (line 23)
- `policy.py` creates an instance of `ApprovalManager` in its `__post_init__` (line 75-88)
- There are two separate `ApprovalManager` classes in different modules:
  - `teaagent/approval_manager.py` - Main approval manager
  - `teaagent/runner/_approval_manager.py` - Runner-specific approval manager

### Impact
- **Tight Coupling**: Modules are tightly coupled, making changes difficult
- **Testing Difficulty**: Circular dependencies make unit testing challenging
- **Maintenance Burden**: Duplicate code increases maintenance cost
- **Confusion**: Two separate `ApprovalManager` classes create confusion

## Proposed Solution

### Phase 1: Consolidate ApprovalManager Classes
1. **Identify Differences**: Analyze differences between the two `ApprovalManager` implementations
2. **Merge Functionality**: Create a single, unified `ApprovalManager` class
3. **Update Imports**: Update all imports across the codebase to use the consolidated class
4. **Remove Duplicate**: Delete the duplicate `ApprovalManager` from `runner/_approval_manager.py`

### Phase 2: Refactor ApprovalPolicy
1. **Remove Wrapper Pattern**: Remove the wrapper pattern from `ApprovalPolicy`
2. **Simplify Data Container**: Make `ApprovalPolicy` a simple data container
3. **Direct Usage**: Have the runner directly use the consolidated `ApprovalManager`
4. **Update Callers**: Update all callers to use the new pattern

### Phase 3: Break Circular Dependencies
1. **Create Shared Types Module**: Move shared types to `approval_types.py`
2. **Use Dependency Injection**: Replace direct instantiation with dependency injection
3. **Add Interface Protocols**: Create protocols for loose coupling
4. **Update Import Structure**: Reorganize imports to eliminate cycles

## Implementation Details

### New Module Structure
```
teaagent/
  approval/
    __init__.py
    types.py              # Shared types and protocols
    manager.py            # Consolidated ApprovalManager
    policy.py             # Simplified ApprovalPolicy
    store.py              # ApprovalStore (unchanged)
```

### Shared Types Module
```python
# approval/types.py
from typing import Protocol, Any
from dataclasses import dataclass

@dataclass
class ApprovalRequest:
    """Request for approval."""
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    content_digest: str | None = None
    destructive: bool = False

@dataclass
class ApprovalDecision:
    """Decision on approval request."""
    approved: bool
    reason: str | None = None

class ApprovalHandler(Protocol):
    """Protocol for approval handlers."""
    
    def check_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalDecision:
        """Check if request is approved."""
        ...
    
    def add_approval(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        """Add approval decision."""
        ...
```

### Consolidated ApprovalManager
```python
# approval/manager.py
from teaagent.approval.types import ApprovalRequest, ApprovalDecision
from teaagent.approval.store import ApprovalStore
from teaagent.policy import PermissionMode

class ApprovalManager:
    """Consolidated approval manager."""
    
    def __init__(
        self,
        approval_store: ApprovalStore,
        permission_mode: PermissionMode,
        jit_approval_enabled: bool = False,
    ):
        """Initialize approval manager."""
        self._store = approval_store
        self._permission_mode = permission_mode
        self._jit_approval_enabled = jit_approval_enabled
    
    def check_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalDecision:
        """Check if request is approved."""
        # Implementation from both existing ApprovalManagers
        pass
    
    def add_approval(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        """Add approval decision."""
        # Implementation from both existing ApprovalManagers
        pass
```

### Simplified ApprovalPolicy
```python
# approval/policy.py
from dataclasses import dataclass
from teaagent.approval.types import ApprovalHandler
from teaagent.policy import PermissionMode

@dataclass
class ApprovalPolicy:
    """Policy for approval decisions (data container only)."""
    
    permission_mode: PermissionMode
    approval_handler: ApprovalHandler | None = None
    
    def is_destructive_allowed(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Check if destructive operation is allowed."""
        # Simplified implementation
        pass
```

## Migration Plan

### Step 1: Create New Module Structure
1. Create `teaagent/approval/` directory
2. Create `types.py` with shared types
3. Create `manager.py` with consolidated ApprovalManager
4. Update `__init__.py` to export public APIs

### Step 2: Update Imports
1. Update `policy.py` to import from new module
2. Update `runner/_approval_manager.py` to use consolidated class
3. Update all other files that import ApprovalManager
4. Remove duplicate ApprovalManager

### Step 3: Update Tests
1. Update unit tests for ApprovalManager
2. Update integration tests for approval workflow
3. Add tests for new module structure
4. Verify all tests pass

### Step 4: Documentation
1. Update API documentation
2. Update architecture documentation
3. Create migration guide
4. Update examples

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep old imports working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for approval workflow
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for approval success rate

## Timeline

### Phase 1: Consolidation (2 weeks)
- Week 1: Analyze differences, create shared types module
- Week 2: Consolidate ApprovalManager, update imports

### Phase 2: Refactoring (1 week)
- Week 3: Refactor ApprovalPolicy, update callers

### Phase 3: Testing (1 week)
- Week 4: Update tests, verify all tests pass

### Phase 4: Documentation (1 week)
- Week 5: Update documentation, create migration guide

## Success Criteria

- ✅ No circular dependencies in import graph
- ✅ Single ApprovalManager class in codebase
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Circular Dependencies
- **Pros**: No changes required
- **Cons**: Technical debt, hard to maintain
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Lazy Imports
- **Pros**: Minimal code changes
- **Cons**: Hides the problem, doesn't fix root cause
- **Decision**: Rejected - doesn't address the underlying issue

### Alternative 3: Create Mediator Pattern
- **Pros**: Decouples modules
- **Cons**: Adds complexity, over-engineering
- **Decision**: Rejected - simpler solution available

## References
- ADR 0010: Resolve circular dependencies between approval_manager.py and policy.py
- Current implementation in `approval_manager.py` and `policy.py`
- Duplicate implementation in `runner/_approval_manager.py`
