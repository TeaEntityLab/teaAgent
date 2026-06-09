# TEST MATRIX — SURF-010: Unified CLI/TUI Resume Preparation

> Spec: [`../specs/SURF-010-resume-parity.md`](../specs/SURF-010-resume-parity.md).
> P0 here = the permission/trust paths (auto-grant, legacy, tamper, already-approved).
> Existing tests: `tests/test_resume_preparation.py`,
> `tests/acceptance/test_cli_tui_resume_parity_flow.py`.

> **Status: all P0 gaps closed 2026-06-09.** Tests live in `tests/test_resume_preparation.py`
> (unit) and `tests/acceptance/test_cli_tui_resume_parity_flow.py` (parity). The new P0 tests all
> **passed on first run** → the digest binding already held; no permission hole existed. Value =
> explicit regression guard + verified spec-mutation catch (see bottom).

| # | Case | Input | Expected | Type | Priority | Covered by |
|---|---|---|---|---|---|---|
| 1 | valid digest pending → auto-grant | pending w/ digest, `call_id ∉ approve` | scoped approval added, `auto_approved_call_id == call_id` | security | **P0** | `test_cli_tui_resume_parity_flow.py::...auto_grants_pending_approval` ✅ |
| 2 | CLI/TUI parity | same args both surfaces | equal `to_dict()` | integration | **P0** | `test_cli_tui_resume_parity_flow.py::...same_preparation_contract` ✅ |
| 3 | **tampered/different digest** | grant bound to recorded digest; tampered digest queried | **no** matching grant; store has exactly 1 grant for the real digest (T7 +/- post-state) | adversarial | **P0** | `test_resume_preparation.py::test_auto_grant_is_bound_to_exact_digest` ✅ |
| 4 | **legacy record** | pending w/o `argument_digest` | `pending_warning` set; no auto-grant; `auto_approved_call_id is None`; store unchanged | security | **P0** | `test_resume_preparation.py::test_legacy_record_without_digest_warns_and_does_not_auto_grant` ✅ |
| 5 | **already pre-approved** | `call_id ∈ approve_call_ids` | skipped: no warning, no new grant | security | **P0** | `test_resume_preparation.py::test_pre_approved_call_id_is_skipped_not_re_granted` ✅ |
| 6 | idempotent re-grant | digest already scoped-approved | not re-added; `auto_approved_call_id == call_id` | integration | P1 | `test_resume_preparation.py::test_auto_grant_is_idempotent_when_already_scoped` ✅ |
| 7 | fresh restart | `fresh_restart=True` | no obs, no auto-grant, no warning | unit | P1 | `test_resume_preparation.py::test_fresh_restart_skips_pending_auto_grant` ✅ |
| 8 | missing run | bad `run_id` | raises `ResumePreparationError` | unit | P1 | `test_resume_preparation.py::test_prepare_run_resume_missing_run_raises` ✅ |
| 9 | auto-compaction | >40 observations, `auto_compact=True` | keep 20; `resume_compaction.truncated=True` | unit | P2 | `test_resume_preparation.py::test_prepare_run_resume_compacts_large_observation_history` ✅ |
| 10 | checkpoint source | `checkpoint_path` present | obs/context from checkpoint, bypass compaction | integration | P2 | not yet covered (P2, deferred) |
| 11 | `auto_approve_pending=False` | digest-bearing pending, TUI policy | `pending_warning` set; no grant; `auto_approved_call_id is None` | unit | P1 | `test_resume_preparation.py::test_auto_approve_pending_false_warns_without_granting` ✅ |

## Gap analysis (resolved)

Before this pass, coverage = rows 1, 2, 8, 9 (the original matrix incorrectly flagged 8 & 9 as gaps —
they were already covered in `test_resume_preparation.py`). The **dangerous** paths (3, 4, 5) and the
robustness paths (6, 7) were genuinely untested and are now closed. Row 11 (`auto_approve_pending`) was
added when CLI/TUI resume policy diverged in later commits; it had only TUI-level coverage
(`test_tui.py::test_tui_resume_does_not_auto_approve_pending`) and is now guarded at the prepare layer.

| Row | Priority | Verdict | Outcome |
|---|---|---|---|
| 3 tampered/different digest | P0 | **CLOSED** | Test asserts grant binds the exact digest (positive) and a different digest matches nothing (negative T7 post-state). Passed first run. |
| 4 legacy record | P0 | **CLOSED** | Test asserts warning + no grant + store unchanged. Passed first run; verified by spec mutation below. |
| 5 already-approved | P0 | **CLOSED** | Test asserts skip (no warning, no new grant). Passed first run. |
| 6 idempotent | P1 | **CLOSED** | Test asserts no duplicate grant, call_id still reported. |
| 7 fresh restart | P1 | **CLOSED** | Test asserts empty/clean result, no grant. |
| 10 checkpoint source | P2 | open | Deferred — P2, not security-bearing. |

> **Result of the executable plan, Step 3:** no permission hole found — the digest binding already
> held. The three P0 tests now guard it against regression.

## Adversarial checklist (L3)
- [x] permission escalation: tampered digest must not grant (row 3)
- [x] safe-by-default: legacy/undigested must not grant (row 4)
- [x] consent scope: explicit pre-approval must not double-grant (row 5)
- [x] state post-condition: approval store unchanged on rejection (T7, row 3)

## Mutation checks (T4/T5)
- **Spec (T5) — DONE 2026-06-09:** flipped the legacy guard `if not digest:` → `if False:` in
  `resume_preparation.py`; the row-4 test failed exactly as required
  (`auto_approved_call_id == 'write-1'` instead of `None`); mutation reverted, code byte-identical to
  HEAD. The legacy-warn governance rule is enforced by a test, not just prose. Logged in
  [`../LOCAL_FEEDBACK.md`](../LOCAL_FEEDBACK.md).
- **Code (T4) — for nightly (Roadmap A3):** flipping the digest-match condition should fail row 3;
  candidate for automated `mutmut` scope on this module.
