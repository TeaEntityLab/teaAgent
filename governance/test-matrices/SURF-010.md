# TEST MATRIX — SURF-010: Unified CLI/TUI Resume Preparation

> Spec: [`../specs/SURF-010-resume-parity.md`](../specs/SURF-010-resume-parity.md).
> P0 here = the permission/trust paths (auto-grant, legacy, tamper, already-approved).
> Existing tests: `tests/test_resume_preparation.py`,
> `tests/acceptance/test_cli_tui_resume_parity_flow.py`.

| # | Case | Input | Expected | Type | Priority | Covered by |
|---|---|---|---|---|---|---|
| 1 | valid digest pending → auto-grant | pending w/ digest, `call_id ∉ approve` | scoped approval added, `auto_approved_call_id == call_id` | security | **P0** | `test_cli_tui_resume_parity_flow.py::...auto_grants_pending_approval` ✅ |
| 2 | CLI/TUI parity | same args both surfaces | equal `to_dict()` | integration | **P0** | `test_cli_tui_resume_parity_flow.py::...same_preparation_contract` ✅ |
| 3 | **tampered args** | pending recorded, args mutated so digest ≠ stored | **no** auto-grant; store unchanged | adversarial | **P0** | **GAP** |
| 4 | **legacy record** | pending w/o `argument_digest` | `pending_warning` set; no auto-grant; `auto_approved_call_id is None` | security | **P0** | **GAP** |
| 5 | **already pre-approved** | `call_id ∈ approve_call_ids` | skipped: no warning, no new grant | security | **P0** | **GAP** |
| 6 | idempotent re-grant | digest already scoped-approved | not re-added; `auto_approved_call_id == call_id` | integration | P1 | partial / **GAP** |
| 7 | fresh restart | `fresh_restart=True` | no obs, no auto-grant, no warning | unit | P1 | **GAP** |
| 8 | missing run | bad `run_id` | raises `ResumePreparationError` | unit | P1 | **GAP** |
| 9 | auto-compaction | >40 observations, `auto_compact=True` | keep 20; `resume_compaction.truncated=True` | unit | P2 | **GAP** |
| 10 | checkpoint source | `checkpoint_path` present | obs/context from checkpoint, bypass compaction | integration | P2 | **GAP** |

## Gap analysis (the high-value finding)

Existing coverage = rows 1 & 2 only (happy-path auto-grant + parity). The **dangerous** paths are
untested:

| Row | Priority | Verdict | Action |
|---|---|---|---|
| 3 tampered args | P0 | **GAP** | Add test: mutate stored args, assert no auto-grant **and** approval store unchanged (T7 negative post-state). If this fails → real permission hole → fix `resume_preparation.py`. |
| 4 legacy record | P0 | **GAP** | Add test: seed pending w/o digest, assert `pending_warning` + `auto_approved_call_id is None` + no grant added. |
| 5 already-approved | P0 | **GAP** | Add test: pass `approve_call_ids={call_id}`, assert skip (no warning, no new grant). |
| 6 idempotent | P1 | GAP | Add test: pre-seed scoped grant, assert no duplicate, call_id still reported. |
| 7 fresh restart | P1 | GAP | Add test: `fresh_restart=True` → empty/clean result. |

> **These three P0 gaps (3, 4, 5) are the concrete deliverable of the executable plan, Step 3.** Until
> they exist, the security property "auto-grant only on a valid digest" is asserted by the spec but not
> guarded by a test.

## Adversarial checklist (L3)
- [ ] permission escalation: tampered digest must not grant (row 3)
- [ ] safe-by-default: legacy/undigested must not grant (row 4)
- [ ] consent scope: explicit pre-approval must not double-grant (row 5)
- [ ] state post-condition: approval store unchanged on rejection (T7, row 3)

## Mutation checks to run (T4/T5, nightly per Roadmap A3)
- **Code (T4):** flip the digest-match condition in `resume_preparation.py` → row-3 test must fail.
- **Spec (T5):** flip spec "legacy → warn" to "legacy → auto-grant" → row-4 test must fail. Record in
  [`../LOCAL_FEEDBACK.md`](../LOCAL_FEEDBACK.md).
