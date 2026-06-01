# ADR 0023: Strict Plan-Before-Write Enforcement

## Status

Accepted and Implemented - 2026-05-29

## Context

The TeaAgent system required strict enforcement of plan-before-write semantics to ensure that all file modifications are explicitly approved before execution. The initial plan mode (ADR 0001 Post-Implementation) provided basic plan creation and binding, but lacked:

1. **Default enforcement** - Plan-before-write was optional, not enforced by default
2. **Workspace-write mode integration** - No automatic plan requirement in workspace-write mode
3. **File target validation** - No validation that actual file modifications match approved plan
4. **Explicit override mechanism** - No controlled way to skip plan checks when necessary
5. **JIT rollback integration** - No automatic rollback when plan violations are detected

These gaps created security risks where agents could modify files without explicit approval, plans could be bypassed, and there was no mechanism to ensure execution matches approved plans.

## Decision

Implement strict plan-before-write enforcement with default enforcement in workspace-write mode, file target validation, and JIT rollback integration:

### Core Components

#### 1. Plan Gate Enforcement

**Implementation:**
- Modified `teaagent/governance/plan_gate.py` to enforce plan-by-default in workspace-write mode
- Added `--skip-plan-check` CLI flag for explicit override
- Updated `ChatAgentConfig` and `AgentRunner` to support `skip_plan_check` parameter
- Added test for strict enforcement behavior

**Files:**
- `teaagent/governance/plan_gate.py` (29 lines modified)
- `teaagent/chat_agent.py` (2 lines added)
- `teaagent/runner/_core.py` (3 lines added)
- `teaagent/cli/_agent_parsers.py` (8 lines added)
- `teaagent/cli/_handlers/_agent.py` (1 line added)

**Features:**
- Default plan requirement in workspace-write mode
- Explicit `--skip-plan-check` flag for controlled override
- Plan validation before any write operation
- File target validation against approved plan

**Configuration:**
```python
@dataclass
class PlanGateConfig:
    enforce_plan_by_default: bool = True
    skip_plan_check: bool = False
    enable_jit_rollback: bool = True
    validation_profile: ValidationProfile = ValidationProfile.STANDARD
```

#### 2. PlanContract File Target Validation

**Implementation:**
- Extended `PlanContract` with approved file target lists
- Added `allows_file_write()` method to validate file modifications
- Integration with `WorkflowEngine` for validation profile enforcement
- Automatic rollback on strict validation failure

**Files:**
- `teaagent/plan.py` (45 lines added)
- `teaagent/workflow_engine.py` (79 lines modified)
- `teaagent/validation/profiles.py` (1 line added)

**Features:**
- Approved file target lists in plans
- `allows_file_write()` validation method
- Validation profile integration (Fast, Standard, Strict)
- Automatic rollback on strict validation failure

**PlanContract Structure:**
```python
@dataclass
class PlanContract:
    plan_id: str
    file_targets: List[str]  # Approved file targets
    validation_profile: ValidationProfile
    created_at: datetime
    
    def allows_file_write(self, file_path: str) -> bool:
        """Check if file write is allowed by plan."""
        return any(file_path.startswith(target) for target in self.file_targets)
```

#### 3. Validation Profile Integration

**Implementation:**
- Integration with `WorkflowEngine` for validation profile enforcement
- Fast, Standard, and Strict validation profiles
- Automatic rollback on strict validation failure
- JIT rollback integration via `UndoJournal`

**Files:**
- `teaagent/workflow_engine.py` (79 lines modified)
- `teaagent/validation/profiles.py` (1 line added)

**Validation Profiles:**
- **Fast**: Basic syntax checks, no rollback
- **Standard**: Syntax + semantic checks, rollback on failure
- **Strict**: Full validation with automatic rollback, JIT enforcement

**Features:**
- Configurable validation profiles
- Automatic rollback on strict validation failure
- JIT rollback integration via `UndoJournal`
- Validation error reporting with actionable messages

#### 4. CLI Integration

**Implementation:**
- Added `--skip-plan-check` CLI flag for explicit override
- Updated `ChatAgentConfig` to support skip_plan_check
- Updated `AgentRunner` to respect skip_plan_check flag
- Added documentation for plan enforcement behavior

**Files:**
- `teaagent/cli/_agent_parsers.py` (8 lines added)
- `teaagent/cli/_handlers/_agent.py` (1 line added)

**CLI Flags:**
- `--skip-plan-check` - Explicitly skip plan validation (requires user intent)
- `--validation-profile {fast|standard|strict}` - Select validation profile
- `--enable-jit-rollback` - Enable JIT rollback on validation failure

#### 5. Governance Fuzz Tests

**Implementation:**
- Comprehensive adversarial fuzz tests in `tests/test_governance_fuzz.py`
- Tests for plan-before-write enforcement
- Validates conservative defaults and path filtering
- Tests for bypass attempts and security edge cases

**Files:**
- `tests/test_governance_fuzz.py` (381 lines)

**Test Coverage:**
- Plan enforcement in workspace-write mode
- File target validation
- Validation profile enforcement
- JIT rollback on validation failure
- Bypass attempt detection
- Path filtering edge cases

### Configuration

**Plan Gate Config:**
```python
@dataclass
class PlanGateConfig:
    enforce_plan_by_default: bool = True
    skip_plan_check: bool = False
    enable_jit_rollback: bool = True
    validation_profile: ValidationProfile = ValidationProfile.STANDARD
```

**Validation Profiles:**
```python
class ValidationProfile(Enum):
    FAST = "fast"  # Basic syntax checks, no rollback
    STANDARD = "standard"  # Syntax + semantic checks, rollback on failure
    STRICT = "strict"  # Full validation with automatic rollback
```

**PlanContract:**
```python
@dataclass
class PlanContract:
    plan_id: str
    file_targets: List[str]
    validation_profile: ValidationProfile
    created_at: datetime
    
    def allows_file_write(self, file_path: str) -> bool:
        return any(file_path.startswith(target) for target in self.file_targets)
```

## Implementation Timeline

**2026-05-29 09:10:36 +0800** - Implement governance hardening decisions
- Commit: `47e969bf1448db445ef8636d85b4f4117cecb666`
- Files: plan_gate.py, chat_agent.py, runner/_core.py, CLI parsers/handlers, plan.py, workflow_engine.py
- Tests: Governance fuzz tests for plan enforcement

**2026-05-29 09:39:35 +0800** - Wire centralized approval queue into subagents and CI governance gate
- Commit: `7f24de2a1c30e774373efe401728a6584ff8f097`
- Files: Enhanced plan.py, workflow_engine.py integration
- Tests: Integration tests for plan enforcement

## Git History

**Key Commits:**
- `47e969bf1448db445ef8636d85b4f4117cecb666` (2026-05-29 09:10:36) - "Implement governance hardening decisions: centralized approval queue, strict plan-before-write, and automated memory invalidation"
- `7f24de2a1c30e774373efe401728a6584ff8f097` (2026-05-29 09:39:35) - "Wire centralized approval queue into subagents and CI governance gate"

**Implementation Files:**
- `teaagent/governance/plan_gate.py` - Plan gate enforcement (29 lines modified)
- `teaagent/plan.py` - PlanContract with file target validation (45 lines added)
- `teaagent/workflow_engine.py` - Validation profile integration (79 lines modified)
- `teaagent/validation/profiles.py` - Validation profile definitions (1 line added)
- `teaagent/chat_agent.py` - ChatAgentConfig integration (2 lines added)
- `teaagent/runner/_core.py` - AgentRunner integration (3 lines added)
- `teaagent/cli/_agent_parsers.py` - CLI parsers (8 lines added)
- `teaagent/cli/_handlers/_agent.py` - CLI handlers (1 line added)

**Test Files:**
- `tests/test_governance_fuzz.py` - Governance fuzz tests (381 lines)
- `tests/test_tranche_bc_governance.py` - Tranche B/C governance tests (22 lines)

## Consequences

**Positive:**
- Default plan enforcement ensures all file modifications are approved
- File target validation prevents un-declared modifications
- Validation profiles provide configurable strictness
- JIT rollback integration ensures safety on validation failure
- Explicit override mechanism for legitimate bypass scenarios
- Comprehensive test coverage (403 lines of tests)

**Negative:**
- Increased complexity in plan validation
- Additional operational overhead for plan management
- Strict validation may slow development velocity
- Requires user workflow changes (plan creation before write)
- JIT rollback adds execution overhead

**Risk:**
- Medium - strict plan enforcement affects write operations
- Mitigated by comprehensive unit and fuzz tests
- Explicit `--skip-plan-check` flag for controlled override
- Gradual rollout with feature flags for breaking changes
- Conservative defaults with path filtering

## Alternatives Considered

1. **Keep plan-before-write optional** - Rejected due to security risks
2. **Implement only file validation without rollback** - Rejected as incomplete coverage
3. **Use external plan validation framework** - Rejected as over-engineering
4. **Defer strict enforcement to later phases** - Rejected as security risk for file modifications

## References

- [ADR 0001: P0 Agent Harness Framework](0001-p0-framework.md) (Post-Implementation section)
- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)
- [ADR 0022: Centralized Approval Queue for Subagents](0022-centralized-approval-queue-subagents.md)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Architecture - Loop 2: Coding Safety Loop](../architecture.md#loop-2-coding-safety-loop-plan-binding--validation)

## Verification Commands

```bash
# Plan enforcement tests
pytest tests/test_governance_fuzz.py -v
pytest tests/test_tranche_bc_governance.py -v

# Plan mode tests
pytest tests/test_plan_contract.py -v
pytest tests/test_plan_storage.py -v
pytest tests/test_phase4_workflow_engine.py -v
pytest tests/test_phase5_workflow_engine.py -v

# CLI commands
teaagent run --skip-plan-check  # Explicit override
teaagent run --validation-profile strict  # Strict validation
teaagent run --enable-jit-rollback  # Enable JIT rollback

# Selftest
teaagent selftest --root .
```

## Post-Implementation Notes (2026-05-29)

Strict plan-before-write enforcement is now fully implemented with default enforcement in workspace-write mode, file target validation, validation profile integration, and JIT rollback. The system ensures that all file modifications are explicitly approved before execution, with configurable validation profiles and automatic rollback on strict validation failure. Explicit `--skip-plan-check` flag provides controlled override for legitimate bypass scenarios. Remaining work includes monitoring plan enforcement performance and optimizing JIT rollback overhead.
