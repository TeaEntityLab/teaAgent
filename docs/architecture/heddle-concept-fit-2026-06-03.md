# Heddle Concept Fit for TeaAgent
**Date:** 2026-06-03  
**Status:** Architecture fit analysis — boundaries and process adoption  
**Related:** Architecture Evolution Roadmap (2026-06-02), Daily Driver State Map (2026-06-02)

---

## Executive Summary

**Conclusion:** Heddle concepts are applicable to TeaAgent, but should be adopted as "boundaries and process" rather than copying the TypeScript/daemon architecture wholesale.

**Direct Adoption:**
- CLI entry point flow
- Agent loop layering  
- Session persistence
- Memory/knowledge maintenance loop

**Partial Adoption:**
- Runtime host (use existing `managed_runtime.py` as view/control surface, not new execution model)
- Daemon/control plane (document existing `control_plane_api.py` as observation/control, not ownership)

**Not Adopted:**
- New large-scale daemon ownership model
- Second agent framework
- Major repo restructuring

---

## Heddle Concept Mapping

### 1. CLI Entry Point Flow → TeaAgent CLI Handlers

**Heddle Concept:** CLI is the primary entry point with consistent argument parsing and execution flow.

**TeaAgent Mapping:**
- Existing: `teaagent/cli/__init__.py` with subcommand handlers in `cli/_handlers/`
- Alignment: Strong — already follows subcommand pattern with consistent error handling
- Gap: Some commands (TUI vs REPL) have divergent execution paths (CG-12)

**Action:** Document CLI flow as reference surface; ensure all surfaces route through consistent entry validation.

### 2. Agent Loop Layering → AgentRunner + ModelDecisionEngine

**Heddle Concept:** Clear separation between orchestration loop and decision engine.

**TeaAgent Mapping:**
- Existing: `AgentRunner` (runner/_core.py) + `ModelDecisionEngine` (chat_agent.py)
- Alignment: Strong — already has separation between loop governance and LLM decision
- Boundary: Runner should not contain runtime/control-plane logic

**Action:** Formalize this boundary in docs; ensure control plane features don't leak into runner core.

### 3. Session Persistence → SessionStore + RunStore Separation

**Heddle Concept:** Session state (transcript, context) separate from execution evidence (audit, resume).

**TeaAgent Mapping:**
- Existing: `SessionStore` (chat transcripts) + `RunStore` (run summaries, audit logs)
- Alignment: Strong — already has separation
- Gap: TUI bypasses `ChatSessionController`, creating inconsistency (CG-12)

**Action:** Enforce boundary: SessionStore for chat state, RunStore for execution evidence. All surfaces must use `ChatSessionController`.

### 4. Memory/Knowledge Maintenance Loop → MemoryCatalog + Quarantine

**Heddle Concept:** Continuous memory curation with review/promote workflow.

**TeaAgent Mapping:**
- Existing: `MemoryCatalog` with auto-curation
- Alignment: Partial — has auto-curation but lacks review/promote workflow
- Gap: No quarantine mechanism for untrusted or stale memory

**Action:** Add quarantine list/promote path; keep existing auto-curation; add provenance (`run_id`) to summaries.

### 5. Runtime Host → managed_runtime.py as View/Control Surface

**Heddle Concept:** Runtime host manages process lifecycle and resource allocation.

**TeaAgent Mapping:**
- Existing: `managed_runtime.py` 
- Alignment: Partial — exists but not formalized as view/control surface
- Gap: Not clearly documented as observation/control vs execution ownership

**Action:** Document as existing runtime's view/control surface; do not create second execution model.

### 6. Daemon/Control Plane → control_plane_api.py as Observation/Control

**Heddle Concept:** Daemon provides long-running process management and control surface.

**TeaAgent Mapping:**
- Existing: `control_plane_api.py`
- Alignment: Partial — exists but not formalized as daemon
- Gap: Not clearly documented as control surface only (not task execution owner)

**Action:** Document as active runtime view/control; any true daemonization requires ADR.

---

## Key Changes

### New Architecture Documentation

**File:** `docs/architecture/heddle-concept-fit-2026-06-03.md` (this document)

**Purpose:** Record how Heddle's six concepts map to TeaAgent's CLI, runner, session, memory, and control plane.

**Content:**
- Concept mapping table
- Boundary definitions
- Adoption decisions (direct/partial/not adopted)
- Interface specifications

### UX First: Surface Consistency

**Priority:** Complete TUI/chat/agent mode consistency before daemon expansion.

**Focus Areas:**
- `ChatSessionController` usage across all surfaces
- Cost accumulation consistency
- Undo verb unification (CG-15)
- Root path precedence rules
- Resume/background terminology alignment

**Rationale:** Surface inconsistency compounds migration debt (CG-12). Fix before adding complexity.

### Runner Boundary Formalization

**Boundary Definition:**
- **In:** AgentRunner + ModelDecisionEngine = core loop
- **Out:** Runtime lifecycle, control-plane operations, daemon management

**Files:**
- `teaagent/runner/_core.py:45` (AgentRunner)
- `teaagent/chat_agent.py:130` (ModelDecisionEngine)

**Constraint:** No runtime/control-plane logic in runner core. Use protocols for extensibility.

### Session Boundary Clarification

**Separation of Concerns:**
- `SessionStore`: Chat transcript, message history, session metadata
- `RunStore`: Run summaries, audit logs, resume evidence
- `ChatSessionController`: Unified execution semantics for CLI/TUI

**Constraint:** Tests must verify both stores separately. No conflation of session vs run state.

### Memory Loop Enhancement

**Current Behavior:** Auto-curated memory acceptance (keep as-is).

**New Features:**
- Add `run_id`/provenance to auto-curated summaries
- Add quarantine review/promote path
- Reduce memory poisoning and stale memory risk

**Backward Compatibility:** Existing `add`, `list`, `search`, `show` behavior unchanged.

### Control Plane Guardrails

**Definition:** `ControlPlaneServer` is active runtime view/control surface, not task execution owner.

**Constraint:** Any true daemonization requires ADR. Control plane remains observation/control only.

---

## Interfaces

### No Breaking CLI Changes

**Principle:** All changes are additive or internal. No breaking changes to CLI arguments or behavior.

### New Internal Execution Metadata

**Field:** `surface: "cli" | "tui" | "agent" | "control_plane" | "managed_runtime"`

**Location:** 
- Execution context
- Audit `run_started` payload

**Purpose:** Track consistency across different entry points for diagnostics and acceptance testing.

### New Memory CLI Commands

```bash
# List quarantined memory entries
teaagent memory quarantine list --root . --limit N

# Promote quarantined memory with attestation
teaagent memory quarantine promote <memory_id> --i-attest-untrusted-write

# Dry-run maintenance report
teaagent memory maintain --dry-run
```

### MemoryCatalog Extensions

**New Methods:**
- `list_quarantined()` — List quarantined entries
- `promote_quarantined(memory_id, attestation)` — Promote with attestation
- `maintain_dry_run()` — Report maintenance actions without executing

**Unchanged Methods:**
- `add()` — Existing behavior preserved
- `list()` — Existing behavior preserved  
- `search()` — Existing behavior preserved
- `show()` — Existing behavior preserved

---

## Task Plan

### TASK-001: Docs Mapping

**Objective:** Create Heddle fit documentation and update architecture roadmap.

**Deliverables:**
- `docs/architecture/heddle-concept-fit-2026-06-03.md` (this document)
- Update daily-driver index with Heddle concept references
- Update architecture roadmap with Heddle adoption milestones

**Constraints:**
- No changes to AGENTS.md
- No breaking changes to existing docs

**Acceptance:**
- Documentation validation script passes: `python3 scripts/validate_docs_consistency.py`
- All architecture docs reference each other correctly

### TASK-002: Session UX Parity

**Objective:** Ensure TUI task path routes through `ChatSessionController`.

**Changes:**
- Modify TUI to use `ChatSessionController` instead of direct `run_chat_agent` calls
- Ensure cost accumulation uses controller path
- Unify undo verb semantics (CG-15)
- Align root path precedence rules

**Files:**
- `teaagent/tui/__init__.py`
- `teaagent/chat_session_controller.py`

**Acceptance:**
- TUI does not call `run_chat_agent` directly
- Cost accumulation consistent across surfaces
- Undo verb unified (checkpoint vs journal decision documented)

### TASK-003: Root and Lifecycle Truth

**Objective:** Lock down explicit `--root` precedence and fix background/suspend/resume terminology.

**Changes:**
- Document explicit `--root` wins over implicit workspace detection
- Fix background/suspend/resume/review terminology to match actual behavior
- Only promise behavior for existing backing state

**Files:**
- CLI help text and documentation
- TUI help text
- Session controller documentation

**Acceptance:**
- Explicit root precedence documented and tested
- Background/suspend/resume terminology matches implementation
- No over-promising on unsupported features

**Status:** ✅ COMPLETED
- TASK-DD2-002 implemented explicit root guard with `_root_explicit` flag
- TASK-DD2-006 and TICKET-16 Phase 1 fixed lifecycle wording (removed --detach references, clarified suspend vs background)
- TUI help now displays active root path

### TASK-004: Runtime Surface Metadata

**Objective:** Add `surface` field to execution context and audit logs.

**Changes:**
- Add `surface` field to execution context
- Write `surface` to audit `run_started` payload
- Update test expectations to include surface metadata

**Files:**
- `teaagent/runner/_core.py`
- `teaagent/audit.py`
- Test files

**Acceptance:**
- Audit records include `surface` field
- All entry points (CLI, TUI, agent, control plane) set correct surface
- Tests verify surface metadata

### TASK-005: Memory Maintenance

**Objective:** Add quarantine list/promote and dry-run maintain to memory system.

**Changes:**
- Add quarantine list/promote CLI commands
- Extend `MemoryCatalog` with quarantine methods
- Add `run_id`/provenance to auto-curated summaries
- Implement dry-run maintenance report

**Files:**
- `teaagent/memory/catalog.py`
- `teaagent/cli/_handlers/_memory.py`
- New memory quarantine tests

**Acceptance:**
- Quarantine list/promote commands work
- Auto-curated summaries include `run_id`
- Dry-run maintenance reports actions without executing
- Existing memory commands unchanged

### TASK-006: Control Plane Guardrail

**Objective:** Document and test that control plane is view/control surface only.

**Changes:**
- Document `ControlPlaneServer` as view/control surface
- Add tests verifying control plane doesn't own task execution
- Ensure control plane health/auth remain unchanged

**Files:**
- `teaagent/control_plane_api.py` documentation
- Control plane tests

**Acceptance:**
- Control plane documented as view/control only
- Tests verify no task execution ownership
- Health and auth behavior unchanged

**Status:** ✅ COMPLETED
- Added module-level documentation clarifying control plane as view/control surface only
- Control plane does not own task execution (runner/agent components own execution)

---

## Test Plan

### Documentation Validation

```bash
python3 scripts/validate_docs_consistency.py
```

**Expected:** All architecture docs reference each other correctly, no broken links.

### Focused Unit Tests

```bash
python3 -m pytest tests/test_cli_chat.py tests/test_tui.py tests/test_memory.py tests/test_memory_isolation.py -q
```

**Expected:** All focused unit tests pass, covering CLI, TUI, and memory functionality.

### Acceptance Tests

```bash
python3 -m pytest tests/acceptance/test_memory_auto_curation_flow.py tests/acceptance/test_session_resume_continuity_flow.py tests/acceptance/test_cli_tui_surface_parity_flow.py -q
```

**Expected:** All acceptance tests pass, covering end-to-end flows.

### New Scenario Tests

**Scenarios:**
1. TUI does not call `run_chat_agent` directly
2. Explicit `--root` wins over implicit detection
3. Audit records include `surface` metadata
4. Quarantined memory cannot be promoted without attestation
5. Promoted memory appears in search results
6. Control plane health/auth remain unchanged

**Expected:** All new scenarios pass with appropriate test coverage.

---

## Risks and Assumptions

### Risks

**Risk:** Over-importing Heddle could create architecture bloat.

**Mitigation:** Adopt boundaries and processes, not the framework. Focus on "what" not "how".

**Risk:** Session and run persistence can be conflated.

**Mitigation:** Write boundary documentation before code edits. Test both stores separately.

**Risk:** Memory maintenance can break current acceptance.

**Mitigation:** Keep current auto-curation behavior. Add review/promote as additive only.

**Risk:** Control plane becomes new task execution owner.

**Mitigation:** Document as view/control only. Add guardrail tests. Require ADR for daemonization.

### Assumptions

**Assumption:** Pasted Heddle codemap is the reference source.

**Implication:** No external Heddle compatibility required. Internal mapping only.

**Assumption:** No new dependencies.

**Implication:** All features must use existing libraries and patterns.

**Assumption:** No AGENTS.md edits.

**Implication:** Runtime instructions remain in AGENTS.md; architecture docs are separate.

**Assumption:** Daily-driver stability > daemon expansion.

**Implication:** Prioritize surface consistency and session fixes before daemon features.

---

## Success Criteria

### Completion Criteria

- All 6 tasks completed with corresponding acceptance criteria met
- Documentation validation passes
- Focused unit tests pass
- Acceptance tests pass
- New scenario tests pass

### Quality Criteria

- No breaking CLI changes
- Session and run stores remain separate
- Memory auto-curation behavior preserved
- Control plane remains view/control only
- Architecture boundaries documented and tested

### Maintainability Criteria

- Clear documentation of Heddle concept mapping
- Test coverage for new features
- No increase in architectural complexity
- Existing patterns followed (no new frameworks)

---

## Next Steps

1. **Immediate:** Complete TASK-001 (this documentation)
2. **Short-term:** Implement TASK-002 (session UX parity) 
3. **Medium-term:** Complete TASK-003 through TASK-006
4. **Long-term:** Evaluate daemonization only after ADR process

**Review Point:** After TASK-002, review session UX parity results before proceeding to memory maintenance changes.

---

## References

- Architecture Evolution Roadmap (2026-06-02)
- Daily Driver State and Lifecycle Map (2026-06-02)
- ADR 0025: Chat Session Controller
- CG-12: TUI Surface Divergence
- AG-01..04: Broken Agent Suspend/Resume
- CG-15: Undo Verb Collision
