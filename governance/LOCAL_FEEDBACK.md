# LOCAL_FEEDBACK.md — Failure-Learning Log (T8)

> Every failure gets recorded, or the system just repeats it. Two non-negotiables:
> **a correction without Evidence is not a correction; a correction without an Anti-regression Rule is
> only a temporary patch.** Newest entries on top.

## Entry template
```markdown
### YYYY-MM-DD — <short title>
- **Step:** what was being attempted
- **Evidence:** the re-runnable proof of the failure (command + output, failing test, trace)
- **Error Type:** logic / spec / test-gap / permission / config / race / env
- **Root Cause:** the actual cause, not the symptom
- **Correction:** what changed
- **Verification:** the re-runnable proof it is now fixed
- **Anti-regression Rule:** the durable rule / test / check that stops recurrence
```

---

### 2026-06-09 — Governance framework adopted; T0 files were entirely missing
- **Step:** adopting Governed Agentic Engineering into teaagent; planning to apply it to SURF-010.
- **Evidence:** `for f in SPEC.md TEST_MATRIX.md AGENT_RULES.md LOCAL_FEEDBACK.md DONE_CHECKLIST.md; do ...`
  → all reported `missing` at HEAD `c37e181`. CI present (`ci.yml`, `security.yml`) but no mutation testing.
- **Error Type:** process gap (no spec/permission/feedback layer despite shipping L3 changes).
- **Root Cause:** governance scaffolding never created; L3 trust-boundary changes (e.g. resume auto-grant)
  shipped without an explicit spec or P0 security matrix.
- **Correction:** added `governance/` with framework doc, adoption roadmap, T0 five files, templates,
  and the first live spec + test matrix (SURF-010).
- **Verification:** files present and cross-linked from `governance/README.md`; this commit.
- **Anti-regression Rule:** any change classified L3 by the §4 cost model MUST carry a `specs/<ticket>.md`
  + `test-matrices/<ticket>.md` with P0 covered before merge. (To be CI-enforced per Roadmap A1.)

### 2026-06-09 — SURF-010 P0 permission gaps closed; spec-mutation verified
- **Step:** executable plan Steps 3–5 — add the 3 untested P0 permission paths for `prepare_run_resume`
  and prove the legacy-warn rule is test-enforced (T5).
- **Evidence:**
  - `python -m pytest tests/test_resume_preparation.py -v` → 7 passed (5 new). The new P0 tests
    **passed on first run**, so the digest binding already held — **no permission hole existed**.
  - T5 mutation: changed `if not digest:` → `if False:` in `resume_preparation.py`; the legacy test
    failed with `AssertionError: assert 'write-1' is None` (legacy record auto-granted). Reverted;
    `git diff teaagent/integration/resume_preparation.py` is empty (byte-identical to HEAD `c37e181`).
- **Error Type:** test-gap (not a code defect) — the safe behavior was correct but unguarded.
- **Root Cause:** SURF-010 shipped with only happy-path + parity tests; the dangerous branches
  (legacy / tampered-digest / pre-approved) had no regression guard.
- **Correction:** added `test_legacy_record_without_digest_warns_and_does_not_auto_grant`,
  `test_pre_approved_call_id_is_skipped_not_re_granted`, `test_auto_grant_is_bound_to_exact_digest`
  (T7 +/- post-state), `test_auto_grant_is_idempotent_when_already_scoped`,
  `test_fresh_restart_skips_pending_auto_grant`. No production code changed.
- **Verification:** `pytest tests/test_resume_preparation.py tests/acceptance/test_cli_tui_resume_parity_flow.py`
  → 9 passed; resume code unchanged from HEAD.
- **Anti-regression Rule:** the legacy-record branch in `prepare_run_resume` must keep
  `pending_warning` + no auto-grant; the T5 mutation (`if not digest:` → `if False:`) MUST fail the
  legacy test. Any future change to the auto-grant condition is **Requires Human Review** per
  [`AGENT_RULES.md`](AGENT_RULES.md) and must keep these five P0/P1 tests green.
