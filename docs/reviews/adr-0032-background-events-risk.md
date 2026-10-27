# Risk Report: ADR-0032 Amendment A1 (Background Lifecycle Events)

> **Claim class:** Risk note for one proposed high-risk change. Not current truth.
> **Last reviewed:** 2026-10-27
> **Gate status:** Human Review gate **PENDING**. No implementation has started.

**Date:** 2026-10-27
**Action:** U-P1-22
**Scope:** Proposed `RunEventType` members `BACKGROUND_SUBMITTED` and
`BACKGROUND_STOPPED`, and the append-only lifecycle audit file they would write.
**High-risk trigger (review-system §4.2):** Change to the audit schema or audit
event taxonomy. `docs/audit-event.schema.json` is listed in
`scripts/high_risk_paths.yaml`. The implementation will also touch
`teaagent/runner/_events.py` and `teaagent/ergonomics/background_run.py`, and
the audit writer path is involved through `AuditLogger`.
**Artifact under review:** `docs/adr/0032-run-event-taxonomy.md`, Amendment A1
(design accepted by the owner 2026-10-27; implementation pending).

## Goal

Make background submit and stop transitions auditable and append-only (BG-001
§3.5), without changing the background record protocol, run-level evidence, or
the audit schema file.

## What changes (proposed, not yet implemented)

- Two enum members in `RunEventType`, with serialized values
  `background_submitted` and `background_stopped`, plus matching entries in
  `_RUN_EVENT_TO_AUDIT_EVENT_TYPE`.
- Emit on the parent side only: `BackgroundRunStore.start()` (submit, after the
  record is persisted) and the first transition in `BackgroundRunStore.stop()`
  (stop, after the record is persisted).
- Writes go to `<BackgroundRunStore.dir>/lifecycle-<sha256(workspace root)[:12]>.jsonl`,
  a new hash-chained file per workspace through `AuditLogger`, with the synthetic
  envelope `run_id` `background:<background_id>`. The payload key that carries the
  child run id is `child_run_id` (owner decision 2026-10-27, A1.7).
- `docs/audit-event.schema.json` is **not** changed. Its `event_type` is an
  unconstrained string, so there is no enum to extend.

## Assets at risk

- Audit-chain integrity: a new file that other writers append to must not fork
  or break the existing chain verification.
- Run evidence and receipts: a background event must never be folded into, or
  change, a run's evidence.
- Background record protocol (BG-001 pinned fields): the record file format must
  not change.
- Secrets in commands: the full argv can embed task text, paths, or tokens.

## Threat model and failure modes

| Failure mode | Control in the proposal | Residual risk |
| --- | --- | --- |
| Concurrent submit and stop from two processes fork the new chain | Relies on the `AuditLogger.record` tip-resync fix (2026-10-23) under the file lock | Depends on that fix staying in place. Covered by a two-logger strict-verify test (A1.6 #14). |
| Command text leaks into the audit chain | Payload stores only `command_digest` (sha256 of argv); no readable command field (owner decision Q3) | Tests assert the digest excludes task text and that no readable command is written (A1.6 #5, #6). |
| Emit failure makes `stop()` look like it failed, or silently loses the stop event | Record persisted first. Compliance mode raises. Otherwise logged at ERROR. | Outside compliance mode, a lost STOPPED event is not re-emitted on retry (Q4). Accepted gap until the owner decides. |
| Repeated stop emits duplicate STOPPED events | Emit only on the first transition, after the early-return convergence branch | Low. Covered by A1.6 #8. |
| Run evidence or receipts pick up background events | The lifecycle file is separate, and run-level readers never open it | Low. Golden test (A1.6 #20). |
| Exit code overstated as authoritative | `exit_code_derived` flag; derived values never persisted (U-P1-17) | Low. Covered by A1.6 #10, #11. |
| Synthetic `run_id` collides with a minted run id | Namespace prefix `background:`; collision test | Low. Requires confirming minted run ids never contain `:` (A1.6 #13). |
| Old readers break on new event types | Schema accepts any string; additive change | None known. |
| Taxonomy closure guard fails (member with no mapping) | Add both mapping entries in the same change | Low. Guarded by `validate_event_spine_wiring.py`. |

## Dry run (planned, not executed)

The dry run is a focused test pass that must happen before any merge, and it uses
only a scratch workspace:

1. Create two scratch workspaces under the scratchpad directory.
2. Submit a `sleep` background child and check the chain: one
   `background_submitted` event, one envelope `background:<id>`, and
   `verify_audit_chain(strict=True)` passes.
3. Stop it twice and check that exactly one `background_stopped` event exists, with
   the first stop's `stopped_at`.
4. Kill a second child with `SIGKILL` out of band, then stop it and confirm the stop
   event is still written and the record is consistent.
5. Run the 20 new tests in A1.6 and the gates in A1.6 #21 to #24.

No production `.teaagent/` directory and no real run data is touched by the dry run.

## Rollback plan

- Code: revert the emit calls and the two enum members with their mapping
  entries. Each step is one file-local revert and an independent commit.
- Data: the workspace lifecycle file (`lifecycle-<h>.jsonl`) stays on disk after rollback. It is a valid chain and
  nothing reads it. Deleting it is optional and does not affect any run.
- Migration: none. The record format and all existing audit files are unchanged,
  so no stored-state migration is needed and none can be broken.
- Validation after rollback: `scripts/validate_event_spine_wiring.py`,
  `scripts/check_audit_schema_conformance.py`, and `tests/lifecycle/` pass.

## Acceptance criteria (for the implementation PR)

1. All 24 items in A1.6 pass.
2. `docs/audit-event.schema.json` is byte-identical to its state before the change.
3. Run evidence for a proof scenario is byte-identical with and without background
   events present.
4. No command text, task text, or paths appear in any lifecycle payload.

## Human Review Gate

- **Status: PENDING.** The owner has approved drafting only (2026-10-27). Nothing
  in this report authorizes implementation or merge.
- Review path per review-system §4.2 and §6: G4 requires a `reflective-risk`
  report (this document) plus Security Officer sign-off for Size C, or a second
  reviewer plus signature for Size B. The implementer must not self-approve.
- G6 (schema conformance): the implementation must show the schema is unchanged
  and `check_audit_schema_conformance.py` passes.
- Design questions answered by the owner on 2026-10-27 (ADR-0032 A1.7): Q1
  dedicated `lifecycle.jsonl`, Q3 digest only, Q4 persist-then-emit with a logged
  gap and no retry, Q5 amend ADR 0032. Q2 and Q6 follow from Q1; Q7 is out of scope.
  Owner decision 2026-10-27 (A1.7), recorded after the design was accepted: the
  payload key is `child_run_id` (not `run_id`), and the file is per workspace,
  `lifecycle-<sha256(workspace root)[:12]>.jsonl`, so each workspace has its own
  HMAC chain key. The private `AuditLogger` override is dropped.

## Decision

**Design accepted by the owner (2026-10-27).** The implementation may proceed in
its own PR. The Human Review gate for that PR stays open: the implementer must
not self-approve, and a human reviewer signs off on the implementation diff.
