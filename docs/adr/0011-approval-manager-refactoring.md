# ADR 0011: Refactor ApprovalManager to Follow Single Responsibility Principle

## Status
Implemented

## Context
The `ApprovalManager` class in `approval_manager.py` has too many responsibilities:
1. Permission mode enforcement (READ_ONLY, WORKSPACE_WRITE, PROMPT, ALLOW, DANGER_FULL_ACCESS)
2. JIT approval state management
3. Multi-sig quorum coordination
4. Approval store persistence
5. Plan contract validation
6. Read-only gate enforcement
7. Signature collection and verification

This violates the Single Responsibility Principle, making the class difficult to test, maintain, and extend.

## Decision
We will extract the `ApprovalManager` into multiple specialized classes coordinated through composition.

### Implementation Plan

#### Phase 1: Extract PermissionModeEnforcer
1. Create `PermissionModeEnforcer` class to handle permission mode logic
2. Move permission mode enforcement methods from `ApprovalManager`
3. Add unit tests for the new class
4. Update `ApprovalManager` to use `PermissionModeEnforcer`

#### Phase 2: Extract JITApprovalManager
1. Create `JITApprovalManager` class to handle JIT approval state
2. Move JIT approval logic from `ApprovalManager`
3. Add unit tests for the new class
4. Update `ApprovalManager` to use `JITApprovalManager`

#### Phase 3: Extract MultiSigQuorumManager
1. Create `MultiSigQuorumManager` class to handle multi-sig coordination
2. Move multi-sig logic from `ApprovalManager`
3. Add unit tests for the new class
4. Update `ApprovalManager` to use `MultiSigQuorumManager`

#### Phase 4: Extract ApprovalStoreManager
1. Create `ApprovalStoreManager` class to handle persistence
2. Move approval store operations from `ApprovalManager`
3. Add unit tests for the new class
4. Update `ApprovalManager` to use `ApprovalStoreManager`

#### Phase 5: Refactor ApprovalManager as Coordinator
1. Make `ApprovalManager` a lightweight coordinator
2. Use composition to delegate to specialized managers
3. Add integration tests for the coordinator pattern
4. Update all callers to use the new pattern

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before each extraction
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Better separation of concerns, easier testing, more maintainable code
- **Negative**: Breaking changes to internal APIs, requires significant refactoring
- **Risk**: High - affects core approval workflow

## Alternatives Considered
1. Keep monolithic ApprovalManager (rejected - violates SRP)
2. Use inheritance instead of composition (rejected - creates tight coupling)
3. Create microservices (rejected - over-engineering for this use case)

## References
- Original issue: Medium-severity architecture issue #2
- Related files: `approval_manager.py`, `policy.py`
