# WDA-001: Label Unwired H4/H5/H6 Modules

**Priority:** P0  
**Status:** Fixed  
**Sprint:** 2026-06-10 → 2026-06-17  
**Primary files:** `teaagent/governance/rbac.py`, `teaagent/governance/policy_engine.py`, `teaagent/governance/policy_routing.py`, `teaagent/consensus_validation.py` (retired 2026-07-22, ADR-0029 Option D), `teaagent/eval_suite.py`, `teaagent/governance/release_gate.py`, `teaagent/governance/scope_creep.py`, `teaagent/prompt_regression.py`, `teaagent/governance/repo_map_benchmark.py`, `teaagent/update/*`, `docs/roadmap-status.md`

> Note 2026-10-26: the "no production import path" premise is no longer true. `teaagent/subagents/_manager.py:10` imports `teaagent.governance.rbac`, and `:277` calls `teaagent.governance.h4_integration.check_subagent_launch_rbac` at subagent launch (shadow by default; enforced when `rbac_governance_mode` is set). `teaagent/runner/_approval_manager.py:52` calls `evaluate_approval_policy_shadow`. Policy/RBAC are wired in shadow mode; see `docs/roadmap-status.md` H4.

## Problem

ENG-R1: ~12k lines of H4/H5/H6 components exist with 291 passing tests but
**no production import path** references them. Roadmap and commit messages
nevertheless imply implementation completeness.

## Scope

1. Add module-level docstring banner: `experimental — unwired` on every module
   in the import-graph island list (confirm list via WDB-001 dry-run before merge).
2. Update `docs/roadmap-status.md` H4, H5, H6 rows to `Partially implemented —
   unwired` (or equivalent honest status) with evidence citation to engineering
   refresh ENG-R1.
3. Do **not** wire any production path in this ticket.

## Acceptance criteria

- Every island module docstring contains `experimental — unwired`.
- Roadmap horizon rows for H4/H5/H6 reflect unwired state with Next Gate =
  WDA-002 or WDB-001.
- WDB-001 validator passes at HEAD (green after labels registered).
- No behavioral change: acceptance + regression tiers unchanged.

## Verification

```bash
python scripts/validate_wiring.py  # after WDB-001 lands; dry-run script acceptable for WDA-001-only PR
python scripts/validate_docs_consistency.py --test-quality-mode off
python -m pytest tests/acceptance tests/test_rbac.py tests/test_policy_engine.py -q --tb=no
```

## Risks

- Labeling without WDB-001 risks missing a newly wired module — land WDB-001
  in same sprint, ideally same PR stack.
- Roadmap status vocabulary must stay within `ROADMAP_VALID_STATUS_VALUES` in
  `validate_docs_consistency.py`.

## Do not

- Claim H4/H5/H6 Complete.
- Add features to unwired modules.
