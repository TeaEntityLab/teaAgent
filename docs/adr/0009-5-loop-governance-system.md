# ADR 0009: 5-Loop Governance System

## Status

Accepted and Implemented (2026-05-27 to 2026-05-29)

## Context

The TeaAgent harness required a comprehensive governance framework to ensure operational closure, security boundaries, and verifiable runtime behavior. The initial P0 framework (ADR 0001) established basic tool registry, approval gates, and audit logging, but lacked:

1. **Tool governance at CI level** - No static validation of tool security tiers and capabilities
2. **Plan-before-write enforcement** - No binding between approved plans and actual file modifications
3. **Tiered audit logging** - No configurable audit levels with integrity verification
4. **Memory failure management** - No automated curation or invalidation of poisoned memory
5. **Swarm hardening** - No approval lineage tracing or tournament sandbox isolation

These gaps created operational risks where tools could bypass safety checks, plans could be modified without approval, audit trails could be tampered with, memory could accumulate failures, and multi-agent execution lacked security boundaries.

## Decision

Implement a comprehensive 5-loop governance system that provides complete operational closure and security boundaries:

### Loop 1: Tool Governance (CI Gate & Manifests)

**Components:**
- `ToolRegistry` with security tier mapping (Low, Medium, High, Critical)
- Enhanced tool linting with static validation
- AST-based fuzz checking in `selftest.py`
- Capability manifest enforcement

**Implementation:**
- Tools include `security_tier` annotations with automatic tier calculation
- Static validation checks for write-like keywords in `read_only` tool descriptions
- Capability manifest validation with tier mismatch warnings
- `selftest.py` includes static analysis to detect tools marked as `read_only=True` that contain write operations
- Tools must declare capabilities (filesystem_write, network) with preflight warnings for undeclared capabilities

**Verification:**
- `teaagent tool lint --root .`
- `tests/test_governance_fuzz.py`
- `tests/test_governance_adversarial_runtime.py`

### Loop 2: Coding Safety Loop (Plan Binding & Validation)

**Components:**
- Strict plan-before-write enforcement
- `PlanContract` file target validation
- Validation profile integration (Fast, Standard, Strict)
- JIT rollback integration

**Implementation:**
- `workspace-write` mode requires plan binding by default (user-approved strict immediate block)
- Plans include approved file target lists with `allows_file_write()` method to prevent un-declared file modifications
- Fast, Standard, and Strict validation profiles wired to `WorkflowEngine` with automatic rollback on strict validation failure
- Strict validation failures trigger automatic rollback via `UndoJournal`

**Verification:**
- `tests/test_plan_mode.py`
- `tests/test_workflow_engine.py`

### Loop 3: Audit / Replay Loop (Tiered Logging & Integrity)

**Components:**
- Tiered audit levels (L0-L3)
- Audit chain integrity verification
- Per-project encryption support
- TUI run trace surface

**Implementation:**
- L0 (Metrics-only), L1 (Metadata), L2 (Redacted Payload), L3 (Full Local Trace) with configurable filtering
- SHA-256 hash chain validation for trace import to prevent tampering
- L3 audits support per-project encryption keys for metadata leakage prevention
- Interactive run store management for trace, export, and replay operations in TUI

**Verification:**
- `tests/test_audit.py`
- `tests/test_run_store.py`

### Loop 4: Memory / Failure Loop (Curation & Warning Injection)

**Components:**
- Confidence-based blocking
- Enhanced CLI curation suite
- Custom invalidation rules
- Memory hygiene enforcement

**Implementation:**
- Low-confidence failure cards never block execution automatically (enforced warning thresholds)
- `teaagent memory failures review/prune/invalidate` commands with confidence filtering
- Per-project automated invalidation rules (e.g., auto-pruning when target files change)
- TTL expiration rules and manual correction capabilities for memory poisoning

**Verification:**
- `tests/test_memory.py`
- `tests/test_failure_card.py`

### Loop 5: Swarm & Tournament Sandbox Hardening

**Components:**
- Approval lineage tracing
- Fail-fast approval logic
- Git worktree sandbox enforcement
- Security-aware tournament scoring

**Implementation:**
- Subagents carry parent-run IDs and inherit permission mode constraints with structured tracking
- Tournament/parallel mode halts immediately if any subagent requires human permission (user-approved)
- Tournament runs require git worktree isolation as hard pre-condition for zero-contamination guarantees
- Weighted comparator schema (tests 40%, performance 15%, lint 10%, diff size 10%, architectural fit 15%, security 10%)

**Verification:**
- `tests/test_swarm.py`
- `tests/test_tournament.py`
- `tests/acceptance/test_consensus_flow.py`

## Implementation Timeline

**Tranche B (2026-05-27):**
- Tool lint, plan gate, audit completeness, runs trace, selftest

**Tranche C (2026-05-28):**
- Failure cards, MCP trust, read-only `--parallel`

**Hardening (2026-05-28):**
- Centralized approval queue ↔ `SubagentManager`, CI selftest gate

**CLI/TUI (2026-05-28):**
- `teaagent approval subagents list|approve|deny|approve-all|deny-all`
- `approvals subagents` batch table + approve/deny/all

**Tournament (2026-05-28):**
- `ParallelExecutor` + `parallel_executor_with_manager`

**Persistence (2026-05-28):**
- `.teaagent/approval_queues/<parent_run_id>.json`

**Swarm LLM (2026-05-28):**
- `SwarmManager.with_agent_execution` + `SubagentManager`

**Hardening+ (2026-05-29):**
- Adversarial plugin runtime tests, queue cleanup TTL, handler AST gate

**Refactor (2026-05-29):**
- `teaagent.sandbox` package, approval store module split

## Git History

**Key Commits:**
- `2026-05-29 09:10:36 +0800` - "Implement governance hardening decisions: centralized approval queue, strict plan-before-write, and automated memory invalidation"
- `2026-05-29 08:39:28 +0800` - "Extend governance loops with selftest, failure cards, and MCP trust"
- `2026-05-29 08:31:10 +0800` - "Add governance loop MVP: tool lint, plan gate, runs trace, and docs"
- `2026-05-28 16:26:14 +0800` - "security: Enhance tool governance, credential redaction, and command normalization"
- `2026-05-27 16:12:57 +0800` - "Add ecosystem strategy: reference skills, CI/CD templates, onboarding docs, governance"

**Implementation Files:**
- `teaagent/governance/tool_lint.py`
- `teaagent/plan_mode.py`
- `teaagent/workflow_engine.py`
- `teaagent/audit.py`
- `teaagent/memory/failure_card.py`
- `teaagent/swarm.py`
- `teaagent/tournament/`
- `teaagent/selftest.py`

## Consequences

**Positive:**
- Complete operational closure with verifiable runtime behavior
- Security boundaries enforced at multiple layers (CI, runtime, audit)
- Automated memory hygiene prevents failure accumulation
- Multi-agent execution with structured approval lineage
- Configurable audit levels for different security requirements

**Negative:**
- Increased complexity in governance layer
- Additional CI gates may slow development velocity
- Plan-before-write enforcement requires user workflow changes
- Git worktree requirement for tournaments adds operational overhead

**Risk:**
- Medium - governance hardening affects core execution paths
- Mitigated by comprehensive unit and acceptance tests
- Gradual rollout with feature flags for breaking changes

## Alternatives Considered

1. **Keep basic P0 governance without loops** - Rejected due to operational risks
2. **Implement only 2-3 loops** - Rejected as incomplete coverage
3. **Use external governance framework** - Rejected as premature lock-in
4. **Defer governance to later phases** - Rejected as security risk

## References

- [ADR 0001: P0 Agent Harness Framework](0001-p0-framework.md)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Architecture - 5-Loop Governance System](../architecture.md#5-loop-governance-system-completed-hardening)
- [Threat Model](../threat-model.md)
- [Maturity Matrix](../maturity-matrix.md)

## Verification Commands

```bash
# Tool governance
teaagent tool lint --root .
pytest tests/test_governance_fuzz.py tests/test_governance_adversarial_runtime.py

# Plan binding
pytest tests/test_plan_mode.py tests/test_workflow_engine.py

# Audit logging
pytest tests/test_audit.py tests/test_run_store.py

# Memory curation
teaagent memory failures review --root .
pytest tests/test_memory.py tests/test_failure_card.py

# Swarm hardening
pytest tests/test_swarm.py tests/test_tournament.py
pytest tests/acceptance/test_consensus_flow.py

# Full governance suite
pytest tests/test_governance_fuzz.py tests/test_governance_adversarial_runtime.py \
  tests/test_tranche_bc_governance.py tests/test_approval_queue_persistence.py \
  tests/test_subagent_approval_queue_integration.py tests/policy/
teaagent selftest --root .
```

## Post-Implementation Notes (2026-05-29)

All 5 loops are now shipped with CLI, unit tests, and E2E acceptance. The governance system provides complete operational closure and security boundaries for the TeaAgent harness. The system is documented in `docs/architecture.md` and verified through comprehensive test coverage.
