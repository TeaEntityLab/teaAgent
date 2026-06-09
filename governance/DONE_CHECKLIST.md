# DONE_CHECKLIST.md — Definition of Done Gate

> "I fixed it" means nothing without a re-runnable green-light evidence (CV-2). Run this gate before
> calling any change complete. Scale by risk level.

## Always (L1 / L2 / L3)
- [ ] The change does what the task asked — stated plainly, no hedging.
- [ ] Tests run and pass on Python 3.12 (the project baseline). Paste/point to the command + result.
- [ ] `ruff` clean, `mypy` clean, `bandit` clean (no new findings).
- [ ] No forbidden behavior from [`AGENT_RULES.md`](AGENT_RULES.md) was used.
- [ ] If any step was skipped or any test failed, that is stated explicitly — not omitted.

## L2 and up
- [ ] A spec exists under `specs/` (from `templates/SPEC.template.md`) and passed the Spec Quality Gate.
- [ ] A test matrix exists under `test-matrices/` with **P0 fully covered**.
- [ ] Every acceptance criterion maps to ≥1 test (no orphan AC).

## L3 only (auth / payment / permission / migration / delete / deploy)
- [ ] Permission Binding declared: Allowed / Forbidden / Requires Human Review.
- [ ] **Human review obtained** for the trust-boundary diff.
- [ ] State-machine pre/post-conditions asserted (T7), incl. the negative no-op path.
- [ ] Rollback condition is written and verified to work.
- [ ] Trace / audit evidence exists for the privileged action.
- [ ] (Nightly, if configured) mutation check passes on the touched permission module.

## On any failure
- [ ] Logged in [`LOCAL_FEEDBACK.md`](LOCAL_FEEDBACK.md) with Evidence **and** an Anti-regression Rule.
      A fix without an Anti-regression Rule is a temporary patch, not a fix.
