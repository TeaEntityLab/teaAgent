# Risk Report — PR 102: background lifecycle events on a per-workspace audit chain

> **Claim class:** Risk note for one PR. Not current truth.
> **Last reviewed:** 2026-10-27

**Date:** 2026-10-27
**Scope:** U-P1-22 (`docs/retrospective/06-action-register.md`); ADR-0032 Amendment A1 (`docs/adr/0032-run-event-taxonomy.md`)
**High-risk area:** the audit trail. No path in `scripts/high_risk_paths.yaml` is edited (`teaagent/audit*.py`, `teaagent/approval/`, `teaagent/runner/_core.py` and `docs/audit-event.schema.json` are unchanged), but the PR adds a new audit chain and two event types, so it is declared high-risk. The design-level report is `docs/reviews/adr-0032-background-events-risk.md`; this note covers the implementation diff.

## What changes

1. **Two event types.** `RunEventType.BACKGROUND_SUBMITTED` and `BACKGROUND_STOPPED` (`teaagent/runner/_events.py`), with taxonomy mapping entries. `event_type` in the audit schema is a free string, so the schema does not change.
2. **Emission (`teaagent/ergonomics/background_run.py`).** `start()` emits `background_submitted` after the record file is persisted; `stop()` emits `background_stopped` on its first transition, after persisting. A repeated stop emits nothing.
3. **Destination.** The unmodified `AuditLogger.record()` writes to `<store dir>/lifecycle-<sha256(resolved workspace root)[:12]>.jsonl` (`lifecycle_log_path`). AuditLogger keys its HMAC by file stem, so each workspace has its own chain key (owner decision). The envelope `run_id` is `background:<background_id>`.
4. **Payloads.** These are the exact A1.2 keys; the child run id is `child_run_id` (owner decision; it avoids the `record(event_type, run_id, ...)` keyword collision without overriding a private method). The command is recorded only as `command_digest` (sha256 of argv), and there is no readable command text.

## Risk assessment

- **Blast radius.** Only `BackgroundRunStore.start()` and `stop()` gain a write. Run logs, the run store and existing audit chains are untouched. Readers that ignore unknown event types are unaffected.
- **Failure modes.**
  - A failed emit after the record is persisted leaves the record correct and the event missing. Outside compliance mode this is logged at ERROR with category `system` and the `background_id`, and is not retried, so there are no duplicates (owner decision Q4). In compliance mode the failure raises, so the caller sees it.
  - A read-only store emits nothing.
  - The lifecycle file grows by two lines per background run. There is no rotation; it is the same order as the record files.
- **Secrets.** Task text never reaches the chain: the argv appears only as a one-way digest, and a test asserts that no task text appears in the payload.
- **Keys.** A new per-workspace key file appears under the tenant `run-keys` directory, the same mechanism every run log already uses.
- **Thin harness.** No new framework or dependency. `background_run.py` is 715 lines, under the 800-line rule; god-module exemptions stay at 18.

## Dry run and rollback

- **Dry run.** The tests were written first: 17 of the 20 new or activated tests failed before implementation. The new lifecycle tests, the lifecycle spec suite, `check_audit_schema_conformance` and `validate_event_spine_wiring` all pass, as do all local CI gates. The full suite runs on the PR head.
- **Rollback.** Revert `3c1b376a` and `17cc4504`. Existing `lifecycle-*.jsonl` files are left in place and nothing reads them. No migration and no stored-state format change.

## Tests

- `tests/test_background_lifecycle_events.py`: the A1.6 list (emit-after-persist, exact payload keys, `child_run_id` null at submit, digest excludes task text, no readable command, stop on first transition only, stop on a dead process, `exit_code_derived` semantics, read-only store, persist failure, compliance-mode raise, hash-chain verification), plus `test_lifecycle_file_is_per_workspace` and `test_no_private_auditlogger_override`.
- `tests/lifecycle/test_background_lifecycle_spec.py::test_background_event_taxonomy_activates`: its `skipif` is removed.

## Decision

Proceed to review. The design and its open questions were decided by the owner on 2026-10-27 (ADR-0032 A1.7). **Human review gate: open.** The implementer does not self-approve. A human reviewer signs off on this diff before merge.
