# Run Evidence Bundle Specification
# 2026-06-01

**Fills:** Gap **F-ECO-011** — *"create a run completion evidence summary that includes
changed files, commands run, tests passed/failed, approvals, known gaps, and rollback
path."* The May-31 survey's #1 wishlist item is a *visible, actionable audit trail*,
and its headline thesis is that **verification capacity** — not code generation — is
the 2026 bottleneck. The evidence bundle is the artifact that closes a run with proof.

**Grounding.** This spec **extends** the existing `summarize_run` output
(`teaagent/ergonomics/run_summary.py`), which already produces:
`tool_calls_total/read/write`, `files_changed[]`, `cost_usd`, `budget_cap_usd`,
`budget_remaining_usd`, `audit_log` path, `undo_command`, `input_tokens`,
`output_tokens`. The bundle adds the fields F-ECO-011 names that `summarize_run` does
*not* yet carry: commands run, tests pass/fail, approvals granted, known gaps.

---

## Bundle schema (`run_evidence`)

```
RunEvidence
├── run_id, task, status, started_at, ended_at
├── identity        provider, model, permission_mode      (was the run governed?)
├── work
│   ├── files_changed[]          ← summarize_run (undo journal)   [HAVE]
│   ├── commands_run[]           {cmd, exit_code, read_only}      [ADD]
│   └── tool_calls {total, read, write}  ← summarize_run          [HAVE]
├── verification
│   ├── tests {passed, failed, skipped, command}                  [ADD]
│   └── validation_profile (if run)                               [ADD]
├── governance
│   ├── approvals[]              {tool, call_id, decision, scope} [ADD]
│   └── audit_log + audit_chain_verified: bool                    [HAVE+ADD]
├── economics
│   └── cost_usd, budget_remaining_usd, tokens_in/out  ← summarize_run [HAVE]
├── known_gaps[]                 free-text + auto-derived          [ADD]
└── recovery
    └── undo_command  ← summarize_run                             [HAVE]
```

`[HAVE]` = already produced today. `[ADD]` = new, sourced from audit events that
already exist in `.teaagent/runs/{run_id}.jsonl` (commands and approvals are audit
events; this is extraction, not new instrumentation).

---

## Derivation rules (so the bundle cannot lie — UX-F4)

1. **files_changed** comes only from the `UndoJournal` (`.teaagent/undo/{run_id}.jsonl`)
   — i.e. files the agent *actually wrote*, not files it *claimed* to write. This is the
   anti-hallucination guarantee.
2. **commands_run** comes from `tool_call_started` audit events with their recorded
   exit codes — never from the model's narration.
3. **tests** are populated only if a test command actually ran in the audit trail;
   otherwise `tests: null` (never inferred "passing").
4. **audit_chain_verified** runs the existing hash-chain verification and records the
   boolean; a broken chain makes the whole bundle `tamper_suspected: true`.
5. **known_gaps** combines explicit agent-declared gaps with auto-derived ones (e.g.
   `status != 'completed'`, failed tests, denied approvals that blocked work).

---

## Rendering

- **Human (`format_run_summary` extended):** the current text block plus a
  `Verification:` line and a `Known gaps:` block. Backward-compatible — existing fields
  unchanged.
- **Machine (`run_evidence.json`):** written to `.teaagent/runs/{run_id}.evidence.json`
  for PR comments, compliance export, and consumption by the next agent (addresses the
  survey's "team memory / onboarding agents" gap, UX wishlist #9).
- **Sendable:** `teaagent agent evidence <run_id> [--markdown]` emits a paste-ready
  summary for a PR or a manager.

---

## Acceptance

- `test_evidence_files_changed_from_journal`: a run that writes A and *claims* to write
  B (but doesn't) lists only A.
- `test_evidence_commands_from_audit`: commands + exit codes match audit events exactly.
- `test_evidence_no_phantom_tests`: a run with no test command yields `tests: null`,
  not "passed".
- `test_evidence_tamper_flag`: a corrupted audit chain sets `tamper_suspected: true`.
- `test_evidence_known_gaps`: a non-completed run auto-lists a gap.
- Backward-compat: existing `test_run_summary.py` assertions still pass.

## Relationship to other docs

- Consumed by the **operator cockpit** (`last_run` field) — see cockpit contract.
- The **risk register** PR-3 (fake cost) must be fixed for `economics` to be truthful.
- Directly serves persona **P-SEC** and **P-OPS** report steps (journey-maps doc).

## Non-goals

- Not a replacement for the full audit log or trace/replay — it is the *closing
  summary*, a legible top layer over the existing audit chain, not a new store.
</content>
