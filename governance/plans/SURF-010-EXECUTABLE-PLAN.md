# Layer B — Executable Plan: Apply the Framework to SURF-010 (resume parity)

> **Target:** commit `c37e181 feat: unify CLI and TUI resume preparation for surface parity`.
> **Risk level:** **L3** — the change auto-grants a previously-pending tool-call approval on resume
> (`teaagent/integration/resume_preparation.py:85-109`). That is a permission/trust boundary.
> **Companion artifacts:** [spec](../specs/SURF-010-resume-parity.md) · [test matrix + gap analysis](../test-matrices/SURF-010.md).

## Why this change is L3

On resume, `prepare_run_resume` reads any `pending_approval` for the run. If the pending call's
`call_id` is **not** in `approve_call_ids`, and it has an `argument_digest`, the function **auto-adds a
scoped approval** and returns `auto_approved_call_id`. Legacy records (no digest) instead get a
`pending_warning` and are **not** auto-approved.

The risk: a previously-pending privileged action (e.g. `workspace_write_file`) could be re-executed
after resume **without fresh human consent**. The safety mechanism is the **argument digest** — if the
recorded arguments were tampered with, the digest changes and the scoped-approval check must fail. This
maps directly to:
- **CV-8 (Permission Boundary):** resume defines what the agent is *allowed* to re-do.
- **T7 (State Machine Constraints):** pre/post-conditions on the approval store.
- **Zero-Trust analog:** `run_id` = ticket-bound access; digest = capability attestation.
- **P0 (security) in the test matrix:** digest mismatch and legacy records are the dangerous paths.

## Steps (ordered; each with acceptance criteria)

### Step 1 — Retroactive SPEC → `specs/SURF-010-resume-parity.md`  ✅ written
Capture the resume-prep contract: `PreparedRunResume` schema as Inputs/Outputs; CV-4 real-world
assumption ("a pending tool call may be re-executed after resume"); CV-8 Allowed/Forbidden
("auto-grant ONLY when argument digest matches; NEVER auto-grant legacy/redacted records").
**Accept:** every field of `PreparedRunResume` and every branch in `resume_preparation.py:63-109`
maps to ≥1 acceptance criterion. — _Done; see the spec._

### Step 2 — TEST_MATRIX + gap analysis → `test-matrices/SURF-010.md`  ✅ written
Enumerate P0 security rows, then diff against existing tests
(`tests/test_resume_preparation.py`, `tests/acceptance/test_cli_tui_resume_parity_flow.py`).
**Predicted gaps (high-value finding):**
| Gap | P0 case | Current coverage |
|---|---|---|
| Tampered args | digest **mismatch** must NOT auto-grant | **appears untested** |
| Legacy record | no-digest must `pending_warning` + NOT auto-grant | **appears untested** |
| Already approved | `call_id ∈ approve_call_ids` must skip, not re-grant | **appears untested** |
| fresh_restart | `fresh_restart=True` must skip all auto-grant | check |
**Accept:** matrix lists every P0 row with a coverage verdict (covered / gap). — _Done; see the matrix._

### Step 3 — Add the missing P0 tests → `tests/test_resume_preparation.py`  ✅ done
Wrote tests for the three gaps (rows 3/4/5) plus idempotency (6) and fresh-restart (7).
**Outcome:** all five **passed on first run** → the digest binding already held; **no permission hole**.
`resume_preparation.py` was **not** changed (verified byte-identical to HEAD). Value = explicit
regression guard.

### Step 4 — T7 state-machine assertion (strengthen, don't just add)  ✅ done
`test_auto_grant_is_bound_to_exact_digest` asserts both the **positive** post-state (a scoped grant
exists for the exact recorded digest) and the **negative** post-state (a different/tampered digest
matches nothing; exactly one grant exists — no over-granting). The legacy and pre-approved tests assert
the store is left **unchanged**.

### Step 5 — One spec-mutation check (manual, T5)  ✅ done
Flipped the legacy guard `if not digest:` → `if False:`; the legacy test failed exactly as required;
mutation reverted. Logged in [`../LOCAL_FEEDBACK.md`](../LOCAL_FEEDBACK.md) with Evidence and an
Anti-regression Rule.

## Scope guard (honored)
Layer B stayed **additive** — only specs + tests were added. `resume_preparation.py` is unchanged from
HEAD `c37e181` because no P0 test failed. The committed feature was not refactored.

## Status tracker
| Step | State | Artifact |
|---|---|---|
| 1 · SPEC | ✅ done | `specs/SURF-010-resume-parity.md` |
| 2 · Matrix + gaps | ✅ done | `test-matrices/SURF-010.md` |
| 3 · P0 tests | ✅ done (all pass; no hole) | `tests/test_resume_preparation.py` |
| 4 · State-machine assertion | ✅ done | `tests/test_resume_preparation.py` |
| 5 · Spec mutation + feedback | ✅ done (mutation caught) | `LOCAL_FEEDBACK.md` |
