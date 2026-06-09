# SPEC — SURF-010: Unified CLI/TUI Resume Preparation

`SPEC_VERSION = 2026-06-09-surf010-resume-parity-v1`
**Risk level:** **L3** (permission / trust boundary)   ·   **Status:** implemented (retroactive spec) @ `c37e181`
**Code:** [`teaagent/integration/resume_preparation.py`](../../teaagent/integration/resume_preparation.py) ·
consumers: `cli/_handlers/_agent/resume.py`, `tui/_commands.py`, `chat_session_controller.py`.

## Goal / Non-goals
- **Goal:** CLI and TUI resume of a persisted run must produce **identical trust inputs** via a single
  surface-independent function, so neither surface can diverge on what gets re-approved or re-loaded.
- **Non-goals:** does not change how runs are *executed* after preparation; does not alter the approval
  digest scheme itself; does not add new permission modes.

## Inputs / Outputs (schema)
**Input — `prepare_run_resume(root, run_id, *, approve_call_ids, fresh_restart, auto_compact, checkpoint_path, auto_approve_pending)`**
- `root: str|Path` — run store root.
- `run_id: str` — run to resume.
- `approve_call_ids: frozenset[str]` — call_ids the human has explicitly pre-approved (default empty).
- `fresh_restart: bool` — if True, skip observations + pending-approval handling entirely.
- `auto_compact: bool` — if True, truncate to last 20 when >40 observations.
- `checkpoint_path: str|Path|None` — optional SQLite checkpoint source.
- `auto_approve_pending: bool` — default `True` (CLI). When `False` (TUI, `tui/_commands.py:284`),
  a digest-bearing pending call is **not** auto-granted; the caller is warned so the user approves
  explicitly first. This is a surface *policy* knob, not a relaxation of the digest rule below.

**Output — `PreparedRunResume` (frozen dataclass):**
`run_id`, `original_task`, `initial_observations: list[dict]`, `initial_context_extra: dict|None`,
`auto_approved_call_id: str|None`, `pending_warning: str|None`; plus `to_dict()` for parity comparison.

## Acceptance Criteria (each testable)
- [x] **AC-1** Missing/invalid run → raises `ResumePreparationError` (wraps `FileNotFoundError`/`ValueError`).
- [x] **AC-2** Same `(root, run_id, kwargs)` from CLI and TUI yields equal `to_dict()` (surface parity).
- [x] **AC-3** Pending approval **with** valid `argument_digest`, `call_id ∉ approve_call_ids`, not
  already scoped → a scoped approval is added **and** `auto_approved_call_id == call_id`.
- [x] **AC-4** Pending approval **without** digest (legacy/redacted) → `pending_warning` set, **no**
  scoped approval added, `auto_approved_call_id is None`.
- [x] **AC-5** Pending `call_id ∈ approve_call_ids` → skipped: no auto-grant, no warning.
- [x] **AC-6** Already-scoped approval (digest matches) → not re-added, but `auto_approved_call_id` still
  reports the call_id (idempotent).
- [x] **AC-7** `fresh_restart=True` → no observations, no auto-grant, no warning.
- [x] **AC-8** `auto_compact=True` with >40 observations → kept 20, `initial_context_extra` records
  `resume_compaction.truncated = True`.
- [x] **AC-9** `auto_approve_pending=False` with a digest-bearing pending call → `pending_warning` set,
  **no** scoped approval added, `auto_approved_call_id is None` (TUI explicit-approval policy).

## Edge Cases / Failure Conditions
- Tampered recorded arguments → recomputed digest ≠ stored digest → scoped-approval check fails → **no
  auto-grant** (this is the core security property; see Forbidden).
- Checkpoint present → observations + context_extra come from checkpoint, bypassing compaction.
- Empty pending / no pending → clean `PreparedRunResume`, no warning.

## Security / Privacy Constraints
- Auto-grant is permissible **only** through the digest-verified path. The digest is the capability
  attestation: it binds the grant to the exact recorded arguments.
- Legacy records (no digest) must **never** be auto-approved — they require explicit
  `--approve-call-id`. This is the safe-by-default fallback.

## Allowed / Forbidden / Requires Human Review (CV-8)
- **Allowed:** auto-grant a scoped approval when digest is present, valid, and the human has resumed the
  run; load/compact observations; surface a warning for legacy records.
- **Forbidden:** auto-grant when `argument_digest` is absent; auto-grant when the recomputed digest does
  not match the stored digest; broaden a scoped grant beyond `(run_id, call_id, tool_name, digest)`;
  silently drop the `pending_warning`.
- **Requires Human Review:** any change to the auto-grant condition, the digest computation, or the
  legacy-record handling.

## Real-world Assumptions (CV-4)
- A pending tool call (e.g. `workspace_write_file`) **may be re-executed** after resume — so the grant
  decision is security-relevant, not cosmetic.
- Runs may have been recorded by an older version → legacy records without digests exist in the wild.
- Resume is human-initiated (the human chose to resume this `run_id`), which is the consent basis for a
  digest-verified auto-grant — but consent does **not** extend to tampered or undigested calls.

## Test Plan
See [`../test-matrices/SURF-010.md`](../test-matrices/SURF-010.md). P0 = AC-3/4/5/6 (permission paths).

---

## Spec Quality Gate
- [x] Goal single & verifiable; Non-goals explicit
- [x] Inputs/Outputs have schema; every AC is testable
- [x] P0 risk classified (permission); forbidden behavior listed
- [x] Rollback: revert `c37e181`; each surface retains its prior independent resume path in history
- [x] Human-review trigger present (auto-grant condition / digest / legacy handling)
- [x] No mutually contradictory conditions
- [x] Real-world assumptions stated
