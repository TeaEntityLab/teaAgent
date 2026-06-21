## Summary

<!-- Why this change is needed; what it does (one paragraph) -->

## Action ID

<!-- Reference one ID from docs/retrospective/06-action-register.md (e.g. S-P2-4, G-P2-4).
     If none applies, describe the gap being addressed. -->

- Action ID:

## Risk Class

<!-- Choose one: low / medium / high.
     High-risk triggers require a reflective-risk report per review-system.md §4.2. -->

- Risk class:

## Self-Review Checklist

<!-- Complete the applicable items. All PRs must satisfy the general criteria. -->

### General (all PRs)

- [ ] `ruff check` + `ruff format --check` pass
- [ ] `mypy teaagent/` reports 0 issues
- [ ] `pytest -m smoke` passes
- [ ] Coverage at least 75%
- [ ] `check_root_module_count.py` ≤ 184
- [ ] `check_complexity.py` ≤ 99
- [ ] No circular imports
- [ ] Event-spine wiring passes
- [ ] Docs consistency passes
- [ ] PR has Why / What / How / Done sections

### High-Risk (if risk class = high)

- [ ] `reflective-risk` report attached (docs/reviews/<pr-id>-risk.md)
- [ ] Security Officer sign-off obtained
- [ ] Permission-matrix / audit-chain / approval-token tests updated

### Documentation

- [ ] No contradiction with current-truth docs
- [ ] Commands in docs are executable
- [ ] Stale dated docs updated or marked as superseded
