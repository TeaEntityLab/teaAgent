# ADR32-M2-T003: Receipt Fold and Synthetic Fixture Retirement

> **Status**: Agent-safe parity implementation complete — 2026-07-22 | **Risk**: Medium | **Dependencies**: ADR32-M2-T002 | **Human Review Required**: Yes (fixture retirement)

## 1. Goal

Switch `build_run_receipt()` to consume event-derived evidence (via `build_run_evidence_bundle(use_event_stream=True)`) by default, then retire or clearly mark legacy synthetic receipt fixtures.

## 2. Why This Matters

Synthetic fixtures that construct receipt test data from hardcoded audit event dicts mask real-path gaps. Once the event stream can produce byte-equivalent evidence, those fixtures become liabilities — they test a path that no longer matches production. M2-T003 eliminates this gap.

**2026-07-22 execution note:** the safe local implementation added
`build_run_receipt(..., use_event_stream=True|False)`, receipt parity coverage,
and a best-effort `receipt_event_derived_mismatch` audit warning when the
event-derived receipt diverges from the legacy receipt. The synthetic-fixture
retirement remains Human Review work; no fixture was deleted by the agent.

## 3. Scope

### In scope
- Flip `build_run_receipt()` to use `use_event_stream=True` as default
- Retire or rename legacy synthetic fixtures in `tests/test_run_receipt.py`
- Ensure `build_run_receipt()` output is unchanged for existing real-run fixtures
- Update `build_run_receipt()` callers to pass raw_audit_events if they have them
- 5-minute proof completeness acceptance test remains green

### Out of scope
- Adding new evidence extractors (T002 scope)
- Changing receipt format or content
- Retiring fixtures in `test_run_evidence.py` (those test extractors directly, not synthetic receipts)

## 4. Data Flow (After T003)

```
EventSpine (typed RunEvent stream) + RunStore (raw audit events fallback)
  │
  ▼
build_run_evidence_bundle(use_event_stream=True)    ◄── DEFAULT
  │
  ▼
RunEvidenceBundle  ──►  format_run_receipt()  ──►  receipt string
```

```
Legacy path: build_run_evidence_bundle(use_event_stream=False)
Remains available for parity; not used in production after T003.
```

## 5. Functional Requirements

### FR-01: Default switch

`build_run_receipt()` switches default:

```python
def build_run_receipt(
    store: RunStore,
    run_id: str,
    root: str | Path,
    *,
    budget_cap_cents: int | None = None,
    use_event_stream: bool = True,  # was: no such param (now defaults True)
) -> str:
```

When `use_event_stream=True`:
1. Read typed RunEvents from EventSpine (or convert from audit JSONL via M2-T001 reader)
2. Read raw audit events from RunStore for fallback
3. Call `build_run_evidence_bundle(root, run_id, use_event_stream=True, raw_audit_events=events_audit)`
4. Format receipt using event-derived bundle

When `use_event_stream=False`:
- Existing legacy path, unchanged

### FR-02: Shallow parity gate (pre-flight)

Before flipping the default, a **one-time shallow parity assertion** runs in `build_run_receipt()` for 2 weeks (or N calls): when `use_event_stream=True`, also compute the legacy receipt and compare them. If they differ, emit an audit warning. This catches silent regressions from the parity test gap.

Implementation:

```python
if use_event_stream:
    # Compute legacy receipt for shadow comparison
    legacy_bundle = build_run_evidence_bundle(root, run_id, use_event_stream=False)
    legacy_receipt = format_run_receipt(legacy_summary, context, bundle=legacy_bundle, events=raw_events)
    if legacy_receipt != receipt:
        # Emit audit warning — mismatch detected
        audit.record('receipt_event_derived_mismatch', run_id, ...)
```

**Note**: Remove this shallow gate after one release cycle once confidence is established.

### FR-03: Synthetic fixture retirement

In `tests/test_run_receipt.py`:

| Fixture/Action | What to do |
|---|---|
| `_write_run()` | Keep — it's a test helper, not synthetic fixture data |
| All `test_*` functions that build inline `events = [...]` dict lists | Keep the tests; they test the **legacy** extraction path. Add a `pytest.mark.legacy_event_path` marker to flag them. Inline event data is valid for testing legacy extractors. |

The **real synthetic fixtures to retire** are any that:
- Construct an entire receipt from hand-crafted event data that doesn't go through `build_run_evidence_bundle()`
- Bypass the evidence builder entirely and feed fake data directly to `format_run_receipt()`

Search and handle:
1. `grep -r "format_run_receipt" tests/` — any test that calls `format_run_receipt()` with a mock bundle (not from `build_run_evidence_bundle()`) is a candidate for retirement or marking.
2. For tests that pass a `bundle` directly to `format_run_receipt()`: either refactor to use event-derived bundle, or mark `@pytest.mark.legacy_event_path`.

### FR-04: 5-minute proof completeness

`tests/acceptance/test_five_minute_proof_flow.py` must remain green. It tests the end-to-end: run → evidence → receipt. After T003, the receipt comes from event-derived evidence, so this test implicitly validates the full chain.

## 6. Acceptance Criteria

| # | Criterion | Verification |
|---|---|---|
| AC-01 | `build_run_receipt(use_event_stream=True)` output equals `build_run_receipt(use_event_stream=False)` for all existing real-run fixtures | Compare receipt strings |
| AC-02 | 5-minute proof acceptance test passes | `pytest tests/acceptance/test_five_minute_proof_flow.py` |
| AC-03 | All receipt completeness checks pass (`check_receipt_completeness()`) | Existing tests |
| AC-04 | Synthetic-only receipt fixtures are removed or marked `legacy_event_path` | Review `tests/test_run_receipt.py` |
| AC-05 | Shallow parity gate emits audit warning on mismatch | Test: inject mismatched data, observe audit warning |
| AC-06 | `use_event_stream=False` still works (emergency fallback) | Explicit test |

## 7. Tests

| Test file | New/Existing | Description |
|---|---|---|
| `tests/test_run_receipt.py` | Modify | Add `use_event_stream=True` test variant; mark synthetic fixtures with `@pytest.mark.legacy_event_path` |
| `tests/acceptance/test_five_minute_proof_flow.py` | Verify | Confirm green with event-derived default |
| `tests/parity/test_evidence_fold_parity.py` | No change | Re-run to confirm T002 parity still holds |
| `tests/parity/test_receipt_fold_parity.py` | **NEW** | Shadow parity: run receipt both ways, compare output strings |

## 8. Implementation Steps

### Step 1: Pre-flight audit
Before any code changes:
1. Run `build_run_receipt()` on all existing real-run fixtures (golden runs from acceptance tests)
2. Capture receipt outputs as reference strings
3. Store as `tests/parity/fixtures/receipt_reference_{success,failure,cancelled,pending}.txt`

### Step 2: Add `use_event_stream` parameter to `build_run_receipt()`
```python
def build_run_receipt(
    store, run_id, root, *, budget_cap_cents=None, use_event_stream=True
):
    events = store.show_run(run_id)
    # ... existing context extraction ...
    bundle = build_run_evidence_bundle(
        root, run_id, use_event_stream=use_event_stream
    )
    return format_run_receipt(summary, context, bundle=bundle, events=events)
```

### Step 3: Shallow parity gate
Add the shadow comparison described in FR-02. Emit audit warning on mismatch.

### Step 4: Verify with 5-minute proof
Run `test_five_minute_proof_flow.py` — it exercises the full chain. If it passes with `use_event_stream=True`, the default switch is safe.

### Step 5: Mark synthetic receipt fixtures
In `tests/test_run_receipt.py`:
- Identify tests that directly construct `RunEvidenceBundle` or pass synthetic data to `format_run_receipt()`
- Add `@pytest.mark.legacy_event_path` marker
- Add a configurable `--skip-legacy-event-path` option to skip these in CI

### Step 6: Default switch PR
Final commit: flip `use_event_stream` default from `False` to `True`. Include:
- `build_run_receipt()` parameter change
- Audit warning gate
- Test updates
- Changelog entry

## 9. Edge Cases & Failure Modes

| Edge case | Expected behavior |
|---|---|
| Event-derived bundle missing data (gap) | Receipt shows less detail for gap categories; completeness check shows which gaps |
| Audit fallback events also missing | Receipt falls back to summary-only (same as legacy with missing data) |
| Shallow gate detects mismatch | Audit warning emitted, receipt uses event-derived path anyway (no silent data loss) |
| Caller passes `use_event_stream=False` explicitly | Legacy path, unchanged, no warnings |
| 5-minute proof test fails | **Do not merge.** Investigate evidence/receipt extraction gap before flipping default |

## 10. User Review Checklist (Receipt Flip)

When reviewing the T003 implementation:

- [ ] **AC-01**: `build_run_receipt(use_event_stream=True)` output matches `use_event_stream=False` for all fixtures
- [ ] **AC-02**: 5-minute proof acceptance test passes
- [ ] **AC-03**: `check_receipt_completeness()` passes
- [ ] **AC-04**: Synthetic-only receipt fixtures marked or removed
- [ ] **AC-05**: Shallow parity gate emits audit warning on mismatch
- [ ] **AC-06**: `use_event_stream=False` still works as fallback
- [ ] Pre-flight receipt reference strings captured before changes
- [ ] Shallow parity gate wired to audit (not silent)
- [ ] `pytest.mark.legacy_event_path` marker works with `--skip-legacy-event-path`
- [ ] All existing receipt tests pass
- [ ] Pre-commit hooks pass (ruff, mypy)

## 11. Files Touched

- `teaagent/run_receipt.py` — `use_event_stream` parameter, shallow parity gate
- `tests/test_run_receipt.py` — mark synthetic fixtures, add event-stream variant tests
- `tests/parity/test_receipt_fold_parity.py` — receipt parity test
- `tests/parity/fixtures/receipt_reference_*.txt` — reference receipt strings

## 11. Definition of Done

- [ ] `build_run_receipt()` accepts `use_event_stream` parameter (default: True)
- [ ] Shallow parity gate implemented with audit warning
- [ ] 5-minute proof acceptance test passes
- [ ] Synthetic receipt fixtures marked `@pytest.mark.legacy_event_path`
- [ ] Receipt parity test compares `use_event_stream=True` vs `False` output
- [ ] All existing receipt tests pass
- [ ] Pre-commit hooks pass (ruff, mypy)
- [ ] Default switch PR ready for review
