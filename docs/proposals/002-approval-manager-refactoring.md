# Proposal: Refactor ApprovalManager to Follow Single Responsibility Principle

## Executive Summary
This proposal outlines a plan to refactor the `ApprovalManager` class into multiple specialized classes coordinated through composition, following the Single Responsibility Principle.

## Problem Statement

### Current State
The `ApprovalManager` class in `approval_manager.py` has too many responsibilities:
1. Permission mode enforcement (READ_ONLY, WORKSPACE_WRITE, PROMPT, ALLOW, DANGER_FULL_ACCESS)
2. JIT approval state management
3. Multi-sig quorum coordination
4. Approval store persistence
5. Plan contract validation
6. Read-only gate enforcement
7. Signature collection and verification

### Impact
- **Violates SRP**: Single class has multiple responsibilities
- **Testing Difficulty**: Hard to test individual responsibilities
- **Maintenance Burden**: Changes to one responsibility affect others
- **Extensibility**: Difficult to add new approval mechanisms

## Proposed Solution

### Phase 1: Extract PermissionModeEnforcer
1. **Create Class**: Create `PermissionModeEnforcer` class
2. **Move Logic**: Move permission mode enforcement methods from `ApprovalManager`
3. **Add Tests**: Add unit tests for the new class
4. **Update ApprovalManager**: Update `ApprovalManager` to use `PermissionModeEnforcer`

### Phase 2: Extract JITApprovalManager
1. **Create Class**: Create `JITApprovalManager` class
2. **Move Logic**: Move JIT approval logic from `ApprovalManager`
3. **Add Tests**: Add unit tests for the new class
4. **Update ApprovalManager**: Update `ApprovalManager` to use `JITApprovalManager`

### Phase 3: Extract MultiSigQuorumManager
1. **Create Class**: Create `MultiSigQuorumManager` class
2. **Move Logic**: Move multi-sig logic from `ApprovalManager`
3. **Add Tests**: Add unit tests for the new class
4. **Update ApprovalManager**: Update `ApprovalManager` to use `MultiSigQuorumManager`

### Phase 4: Extract ApprovalStoreManager
1. **Create Class**: Create `ApprovalStoreManager` class
2. **Move Logic**: Move approval store operations from `ApprovalManager`
3. **Add Tests**: Add unit tests for the new class
4. **Update ApprovalManager**: Update `ApprovalManager` to use `ApprovalStoreManager`

### Phase 5: Refactor ApprovalManager as Coordinator
1. **Simplify**: Make `ApprovalManager` a lightweight coordinator
2. **Use Composition**: Use composition to delegate to specialized managers
3. **Add Tests**: Add integration tests for the coordinator pattern
4. **Update Callers**: Update all callers to use the new pattern

## Implementation Details

### PermissionModeEnforcer
```python
# approval/permission_mode_enforcer.py
from teaagent.policy import PermissionMode
from teaagent.approval.types import ApprovalRequest, ApprovalDecision

class PermissionModeEnforcer:
    """Enforces permission mode rules."""
    
    def __init__(self, permission_mode: PermissionMode):
        """Initialize permission mode enforcer."""
        self._permission_mode = permission_mode
    
    def check_destructive_allowed(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Check if destructive operation is allowed."""
        # Implementation from ApprovalManager
        pass
    
    def check_read_only_gate(
        self,
        tool_name: str,
    ) -> bool:
        """Check if read-only gate allows operation."""
        # Implementation from ApprovalManager
        pass
```

### JITApprovalManager
```python
# approval/jit_approval_manager.py
from teaagent.approval.types import ApprovalRequest, ApprovalDecision

class JITApprovalManager:
    """Manages JIT approval state."""
    
    def __init__(self, enabled: bool = False):
        """Initialize JIT approval manager."""
        self._enabled = enabled
        self._pending_approvals: dict[str, ApprovalRequest] = {}
    
    def add_pending_approval(
        self,
        request: ApprovalRequest,
    ) -> None:
        """Add pending approval request."""
        pass
    
    def get_pending_approval(
        self,
        call_id: str,
    ) -> ApprovalRequest | None:
        """Get pending approval request."""
        pass
    
    def remove_pending_approval(
        self,
        call_id: str,
    ) -> None:
        """Remove pending approval request."""
        pass
```

### MultiSigQuorumManager
```python
# approval/multi_sig_quorum_manager.py
from teaagent.approval.types import ApprovalRequest, ApprovalDecision

class MultiSigQuorumManager:
    """Manages multi-sig quorum coordination."""
    
    def __init__(self, config: dict[str, Any]):
        """Initialize multi-sig quorum manager."""
        self._config = config
        self._signatures: dict[str, list[str]] = {}
    
    def check_quorum(
        self,
        request: ApprovalRequest,
    ) -> bool:
        """Check if quorum is reached."""
        pass
    
    def add_signature(
        self,
        call_id: str,
        signature: str,
    ) -> None:
        """Add signature to request."""
        pass
    
    def verify_signature(
        self,
        signature: str,
    ) -> bool:
        """Verify signature."""
        pass
```

### ApprovalStoreManager
```python
# approval/store_manager.py
from teaagent.approval.store import ApprovalStore
from teaagent.approval.types import ApprovalRequest, ApprovalDecision

class ApprovalStoreManager:
    """Manages approval store operations."""
    
    def __init__(self, store: ApprovalStore):
        """Initialize approval store manager."""
        self._store = store
    
    def save_approval(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        """Save approval to store."""
        pass
    
    def load_approval(
        self,
        call_id: str,
    ) -> ApprovalDecision | None:
        """Load approval from store."""
        pass
    
    def check_scoped_approval(
        self,
        request: ApprovalRequest,
    ) -> bool:
        """Check if scoped approval exists."""
        pass
```

### Refactored ApprovalManager
```python
# approval/manager.py
from teaagent.approval.permission_mode_enforcer import PermissionModeEnforcer
from teaagent.approval.jit_approval_manager import JITApprovalManager
from teaagent.approval.multi_sig_quorum_manager import MultiSigQuorumManager
from teaagent.approval.store_manager import ApprovalStoreManager
from teaagent.approval.types import ApprovalRequest, ApprovalDecision

class ApprovalManager:
    """Coordinator for approval workflow."""
    
    def __init__(
        self,
        permission_mode_enforcer: PermissionModeEnforcer,
        jit_approval_manager: JITApprovalManager,
        multi_sig_quorum_manager: MultiSigQuorumManager,
        store_manager: ApprovalStoreManager,
    ):
        """Initialize approval manager."""
        self._permission_mode_enforcer = permission_mode_enforcer
        self._jit_approval_manager = jit_approval_manager
        self._multi_sig_quorum_manager = multi_sig_quorum_manager
        self._store_manager = store_manager
    
    def check_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalDecision:
        """Check if request is approved."""
        # Coordinate between specialized managers
        pass
    
    def add_approval(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        """Add approval decision."""
        # Coordinate between specialized managers
        pass
```

## Migration Plan

### Step 1: Create Specialized Classes
1. Create `PermissionModeEnforcer` class
2. Create `JITApprovalManager` class
3. Create `MultiSigQuorumManager` class
4. Create `ApprovalStoreManager` class

### Step 2: Move Logic
1. Move permission mode logic to `PermissionModeEnforcer`
2. Move JIT approval logic to `JITApprovalManager`
3. Move multi-sig logic to `MultiSigQuorumManager`
4. Move store operations to `ApprovalStoreManager`

### Step 3: Update ApprovalManager
1. Refactor `ApprovalManager` to use composition
2. Delegate to specialized managers
3. Update constructor to accept managers

### Step 4: Update Tests
1. Add unit tests for each specialized class
2. Add integration tests for coordinator pattern
3. Update existing tests to use new structure
4. Verify all tests pass

### Step 5: Update Callers
1. Update callers to create specialized managers
2. Update callers to pass managers to ApprovalManager
3. Update documentation
4. Update examples

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep old API working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for coordinator pattern
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for approval success rate

## Timeline

### Phase 1: Extract PermissionModeEnforcer (1 week)
- Week 1: Create class, move logic, add tests

### Phase 2: Extract JITApprovalManager (1 week)
- Week 2: Create class, move logic, add tests

### Phase 3: Extract MultiSigQuorumManager (1 week)
- Week 3: Create class, move logic, add tests

### Phase 4: Extract ApprovalStoreManager (1 week)
- Week 4: Create class, move logic, add tests

### Phase 5: Refactor ApprovalManager (1 week)
- Week 5: Refactor coordinator, update callers, add tests

### Phase 6: Testing and Documentation (1 week)
- Week 6: Update tests, verify all tests pass, update documentation

## Success Criteria

- ✅ Each specialized class has single responsibility
- ✅ ApprovalManager is lightweight coordinator
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Monolithic ApprovalManager
- **Pros**: No changes required
- **Cons**: Violates SRP, hard to maintain
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Inheritance Instead of Composition
- **Pros**: Familiar pattern
- **Cons**: Tight coupling, inflexible
- **Decision**: Rejected - composition is more flexible

### Alternative 3: Create Microservices
- **Pros**: Complete decoupling
- **Cons**: Over-engineering, complexity
- **Decision**: Rejected - not needed for this use case

## References
- ADR-0011: Refactor ApprovalManager to follow Single Responsibility Principle
- Current implementation in `approval_manager.py`
- SOLID principles documentation
