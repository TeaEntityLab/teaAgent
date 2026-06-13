# ADR32-M2-T002: Evidence Bundle Fold (Parity Path)

> **Status**: Draft | **Risk**: High | **Dependencies**: ADR32-M2-T001 (T001 already exists — `read_run_events_from_audit()` at `_events.py:217`) | **Human Review Required**: Yes (parity assertion)

## 1. Goal

Add an alternative `build_run_evidence_bundle_from_events()` that derives `RunEvidenceBundle` from the EventSpine's typed `RunEvent` stream, preserving byte-equivalent output with the legacy `build_run_evidence_bundle()` for all four run outcomes (success, failure, cancelled, pending-approval).

## 2. Why This Is Risky

The evidence bundle is consumed by the receipt builder (`format_run_receipt`) and the 5-minute proof flow. A silent mismatch between legacy and event-derived bundles would produce incorrect receipts or fail completeness checks without raising an error. Per §13.4, the parity assertion must go green **before** the default switches.

## 3. Scope

### In scope
- New function `build_run_evidence_bundle_from_events()` in `teaagent/run_evidence.py`
- Reads typed `RunEvent` sequence (from EventSpine stream or stored event log)
- Falls back to raw audit event dicts for evidence categories not yet representable as RunEvents
- Parity test comparing legacy vs event-derived output for 4 fixtures
- Explicit gap reporting: which evidence categories still use audit fallback
- Feature gate: new path is opt-in via `use_event_stream=True` parameter

### Out of scope
- Adding new RunEventType members (that's M2-T001 scope or deferred to later phases)
- Changing the receipt builder (that's M2-T003)
- Retiring synthetic fixtures (that's M2-T003)
- Switching the default production path

## 4. Data Flow

```
EventSpine (typed RunEvent stream)
  │
  ▼
build_run_evidence_bundle_from_events(events, raw_audit_events)
  │  ├─ For M0 RunEvent types: extract from typed RunEvents
  │  └─ For all other evidence categories: fall back to raw_audit_events
  ▼
RunEvidenceBundle  ──►  parity test vs  ──►  build_run_evidence_bundle()
                         (legacy path)
```

## 5. Functional Requirements

### FR-01: New function signature

```python
def build_run_evidence_bundle_from_events(
    root: str | Path,
    run_id: str,
    events: list[RunEvent],
    raw_audit_events: list[dict[str, Any]],
    *,
    goal_id: str = '',
) -> RunEvidenceBundle:
```

- `events`: typed RunEvent sequence (from EventSpine)
- `raw_audit_events`: original audit dicts for fallback (from RunStore.show_run())
- Parity path: `use_event_stream=True` flag (optional, default `False` on `build_run_evidence_bundle`)

### FR-02: Evidence extraction matrix

Which evidence categories can be served from typed RunEvents (M0 set) vs require audit fallback:

| Evidence field | M0 RunEvent source | Audit fallback needed? | Notes |
|---|---|---|---|
| `commands_run` | `TOOL_CALL_STARTED.metadata`, `TOOL_CALL_COMPLETED.result` | Partial — `tool_use` events not represented | Only completed calls w/ result; start-of-run calls from audit |
| `tests` | ❌ no RunEvent | **Yes** — `test_run` audit events | Deferred to later M phase |
| `approvals` | ❌ no RunEvent | **Yes** — `approval_*` audit events | Deferred to M3 (approval gate interceptor) |
| `routes` | ❌ no RunEvent | **Yes** — `model_route` audit events | Deferred to later phase |
| `known_gaps` | `RUN_FAILED` ✓ | Partial — `tool_error` audit needed | RUN_FAILED gap available; tool_error falls back |
| `git_sandbox` | ❌ no RunEvent | **Yes** — `git_sandbox_*` audit events | Not yet in RunEventType |
| `provenance` | ❌ no RunEvent | **Yes** — `provenance_collected` audit events | Deferred |
| `skill_activations` | ❌ no RunEvent | **Yes** — `skill_lifecycle_transition` audit events | Deferred |
| `undo_evidence` | ❌ no RunEvent | **Yes** — `undo_applied` audit events | Deferred |
| `proof_of_use` | mixed | **Yes** — reads multiple audit event types | Full PoU requires audit |
| `cost_cents / cost_state / budget_cap_cents` | `RUN_COMPLETED.metadata` | Partial — fallback to audit for budget details | RUN_COMPLETED carries final cost if set |
| `context_health` | n/a | n/a | Computed externally, not from events |

### FR-03: Gap reporting

The function MUST return a `gap_categories: list[str]` alongside the bundle, listing which evidence categories fell back to audit:

```python
@dataclass
class EventDerivedEvidenceResult:
    bundle: RunEvidenceBundle
    gap_categories: list[str]  # e.g. ['tests', 'approvals', 'routes', ...]
```

Accessible as `build_run_evidence_bundle(..., use_event_stream=True) -> RunEvidenceBundle` without changing the public return type — gap categories logged via audit.

### FR-04: Feature gate

`build_run_evidence_bundle()` gets a new optional parameter:

```python
def build_run_evidence_bundle(
    root: str | Path,
    run_id: str,
    *,
    goal_id: str = '',
    use_event_stream: bool = False,  # NEW
) -> RunEvidenceBundle:
```

- `False` (default): existing legacy path, unchanged
- `True`: calls `build_run_evidence_bundle_from_events()`, uses RunEvents where possible, falls back to audit

## 6. Acceptance Criteria

| # | Criterion | Verification |
|---|---|---|
| AC-01 | `build_run_evidence_bundle(use_event_stream=True)` returns same output as `build_run_evidence_bundle()` for **success** fixture | Parity test: `to_dict()` byte equality after normalization |
| AC-02 | Same for **failure** fixture | Same |
| AC-03 | Same for **cancelled** fixture | Same |
| AC-04 | Same for **pending-approval** fixture | Same |
| AC-05 | `check_evidence_completeness()` passes on event-derived bundle for all 4 outcomes | Completeness check returns empty list |
| AC-06 | Gap categories are non-empty for evidence types not yet in RunEventType | Gap list includes `['tests', 'approvals', 'routes', ...]` |
| AC-07 | `use_event_stream=False` (default) produces identical output to current code | No behavioral regression |

## 7. Tests

| Test file | New/Existing | Description |
|---|---|---|
| `tests/parity/test_evidence_fold_parity.py` | **NEW** | Golden parity: run legacy vs event-derived for 4 outcomes, compare `to_dict()` output |
| `tests/test_run_evidence.py` | Extend | Add test for `build_run_evidence_bundle_from_events()` with known event fixtures |
| `tests/lifecycle/test_run_event_spine.py` | Extend | Add fixture for each outcome type (success/failure/cancelled/pending) that produces both audit JSONL and RunEvent stream |

## 8. Fixture Strategy

For each of the 4 outcomes, create a fixture function that generates BOTH:
1. Raw audit event list (for legacy `build_run_evidence_bundle()`)
2. Typed RunEvent list (for new `build_run_evidence_bundle_from_events()`)

The fixture must produce equivalent outputs from both paths.

**Fixture location**: `tests/parity/fixtures.py` (or inline in parity test file).

A helper `_run_events_from_audit(audit_events: list[dict]) -> list[RunEvent]` converts the existing M1 golden fixture events to RunEvent sequence where mapping exists.

## 9. Implementation Steps

### Step 1: Fixture scaffold
Create `tests/parity/` directory with:
- `test_evidence_fold_parity.py` — the parity test harness
- `conftest.py` — 4 outcome fixture generators

### Step 2: `EventDerivedEvidenceResult` dataclass
Add to `teaagent/run_evidence.py`:
- `gap_categories` field
- Internal `_GapTracker` helper class accumulates which extractors fell back

### Step 3: `build_run_evidence_bundle_from_events()`
New function in `teaagent/run_evidence.py`. Structure:

```python
def build_run_evidence_bundle_from_events(
    root, run_id, events, raw_audit_events, *, goal_id=''
) -> RunEvidenceBundle:
    gap_tracker = _GapTracker()
    
    # Extract from typed RunEvents where possible
    commands = _extract_commands_from_events(events, gap_tracker)
    known_gaps = _extract_gaps_from_events(events, gap_tracker)
    cost_cents, cost_state, budget_cap_cents = _extract_cost_from_events(events, gap_tracker)
    
    # Fall back to audit for everything else
    tests = extract_tests(raw_audit_events)          # gap: 'tests'
    approvals = extract_approvals(raw_audit_events)   # gap: 'approvals'
    routes = extract_routes(raw_audit_events)         # gap: 'routes'
    git_sandbox = extract_git_sandbox(raw_audit_events)  # gap: 'git_sandbox'
    provenance = extract_provenance(raw_audit_events) # gap: 'provenance'
    skill_activations = extract_skill_activations(raw_audit_events)  # gap: 'skills'
    undo_mechanism, undo_outcome = _extract_undo_evidence(raw_audit_events)  # gap: 'undo'
    proof_of_use = build_proof_of_use(raw_audit_events, '')
    
    # ... assemble bundle ...
```

### Step 4: Feature gate on `build_run_evidence_bundle()`
Add `use_event_stream: bool = False` parameter. When `True`, calls the new function.

### Step 5: Parity tests
Each fixture:
1. Generates both raw audit events and typed RunEvents
2. Calls legacy path → gets `RunEvidenceBundle` A
3. Calls event-derived path → gets `RunEvidenceBundle` B
4. Asserts `A.to_dict() == B.to_dict()` (after normalizing timestamps/metadata)
5. Calls `check_evidence_completeness(B, events, outcome_status)` → asserts passes

### Step 6: Known gap test
Assert that `gap_categories` output includes the expected set of categories that still rely on audit fallback.

## 10. Edge Cases & Failure Modes

| Edge case | Expected behavior |
|---|---|
| No typed RunEvents available (empty list) | Full fallback to audit, no data loss |
| Partial RunEvent stream (missing events) | Extract what's available, gap-track missing |
| RunEvent metadata fields missing | Default to None/empty, same as legacy extractors |
| Raw audit events also missing | Empty bundle with `run_id` only |
| Mismatched ordering between RunEvent and audit streams | Sort both by timestamp before extraction |

## 11. M0 RunEvent Type Gap: RUN_CANCELLED and RUN_PAUSED

The `evidence_completeness_checklist()` expects these audit event types for two outcomes:

| Outcome | Required event | In M0 RunEventType? |
|---|---|---|
| cancelled | `event:run_cancelled` | ❌ Not in M0 set |
| pending_approval | `event:run_paused` | ❌ Not in M0 set |

This means **the `check_evidence_completeness()` call on the event-derived path will fail** for cancelled/pending-approval outcomes unless we:

**Option A** (Recommended): Add `RUN_CANCELLED` and `RUN_PAUSED` to `RunEventType` as part of T002. These are minimal additions with no interceptor/consumer changes — just enum members and audit mapping entries. The `read_run_events_from_audit()` will convert them automatically once mapped.

```python
# In RunEventType (add to M0 section, they're essential for evidence completeness):
RUN_CANCELLED = 'run_cancelled'
RUN_PAUSED = 'run_paused'

# In _RUN_EVENT_TO_AUDIT_EVENT_TYPE:
RunEventType.RUN_CANCELLED: 'run_cancelled',
RunEventType.RUN_PAUSED: 'run_paused',
```

**Option B**: Modify `check_evidence_completeness()` to accept an event-derived flag that skips these two event-type checks. **Not recommended** — this creates divergent behavior between legacy and event-derived paths.

**Decision required before implementation.**

## 12. M2-T001 Dependency (Already Done)

T001 (`read_run_events_from_audit()`) is already implemented at `teaagent/runner/_events.py:217`. It reads audit JSONL entries and converts mapped event types to typed `RunEvent` objects, skipping unmapped legacy events. The new function should call:

```python
from teaagent.runner._events import read_run_events_from_audit

audit_entries = RunStore(root).show_run(run_id)  # list[dict]
typed_events = read_run_events_from_audit(audit_entries)
```

Event-derived extraction then operates on `typed_events` for supported types and falls back to `audit_entries` for the rest.

## 13. User Review Checklist (Parity Review)

When reviewing the T002 implementation, verify:

- [ ] **FR-01**: `build_run_evidence_bundle_from_events()` accepts both typed events and raw audit events
- [ ] **FR-02**: The evidence extraction matrix is followed — commands_run partial, known_gaps partial, cost partial from RunEvents; everything else from audit fallback
- [ ] **FR-03**: Gap categories are reported explicitly (log or audit event)
- [ ] **FR-04**: `use_event_stream=False` is still the default (no behavior change yet)
- [ ] **AC-01–04**: Parity tests pass for all 4 outcomes — `to_dict()` byte equality after timestamp/metadata normalization
- [ ] **AC-05**: `check_evidence_completeness()` passes on event-derived bundle
- [ ] **AC-06**: Gap categories are non-empty and correct
- [ ] **AC-07**: Legacy path unchanged
- [ ] **M0 gap**: RUN_CANCELLED and RUN_PAUSED decision resolved (Option A or B)
- [ ] All existing evidence tests still pass
- [ ] Pre-commit hooks pass (ruff, mypy)

## 14. Files Touched

- `teaagent/run_evidence.py` — new function, feature gate, gap dataclass
- `tests/parity/test_evidence_fold_parity.py` — parity tests
- `tests/parity/conftest.py` — fixture generators (or inline in parity test)
- `tests/test_run_evidence.py` — extend with event-derived path tests
- `tests/lifecycle/test_run_event_spine.py` — extend with 4-outcome fixtures

## 12. Definition of Done

- [ ] `build_run_evidence_bundle_from_events()` implemented
- [ ] Feature gate `use_event_stream` parameter added
- [ ] Parity tests pass for all 4 outcomes (legacy == event-derived)
- [ ] `check_evidence_completeness()` passes for event-derived bundles
- [ ] Gap categories reported correctly
- [ ] All existing evidence tests still pass
- [ ] Pre-commit hooks pass (ruff, mypy)
