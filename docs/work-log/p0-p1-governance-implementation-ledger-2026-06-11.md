# P0/P1 Governance Implementation Ledger - 2026-06-11

Source: `docs/analysis/intent-reassessment-and-worklist-2026-06-11.md`  
Workflow: reflective-dispatch -> reflective-implement  
Scope: W1-W9 only (P0/P1). W10-W12 remain P2 and out of scope for this pass.

## Acceptance Ledger

| Item | Status | Evidence |
|---|---|---|
| W1 Fix docs evidence drift | done | `docs/acceptance.md` now reports `627 passed`; stale `446` wording removed; roadmap snapshot wording clarified. |
| W2 Restore full test collection | done | `.venv` collection succeeds: `tests/acceptance --collect-only` reports 627 tests; `tests --collect-only` reports 6001 tests. Guard now checks `hypothesis` remains in dev deps. |
| W3 Add governed first-hour e2e | done | `tests/acceptance/test_first_hour_e2e_flow.py` now runs from a generated plan with `--require-plan`, records command evidence via inspect-safe shell, and verifies pytest outside the agent run. |
| W4 Add receipt completeness contract | done | `teaagent/run_receipt.py`, `teaagent/run_evidence.py`, and receipt tests now require provider/model, permission mode, plan hash, final result, files, redacted command exit evidence, approvals, and rollback. |
| W5 Create control-loop ownership map | done | Added `docs/architecture/control-loop-ownership-map-2026-06-11.md`. |
| W6 Extract one narrow runner boundary | done | `PlanValidator.evaluate_write_gate()` now owns plan-before-write, scope, and read-only-lint gate evaluation; runner calls the wrapper. |
| W7 Add adversarial over-scope tests | done | Added `tests/acceptance/test_adversarial_over_scope_behavior_flow.py` for unauthorized write, unauthorized shell mutation, missing verification, and plan-scope expansion. |
| W8 Improve test quality queue | done | Repaired no-assertion cases in GitHub integration, hook lifecycle, and headless TUI tests; quality audit reports no high-risk no-assertion files. |
| W9 Refresh competitive claims | done | Competitive strategy and claim-audit docs now separate evidence, inference, and positioning; over-strong uniqueness/security/enterprise claims softened. |

## Subagent Lanes

| Lane | Scope | Status |
|---|---|---|
| A | W1/W2 docs count and `hypothesis` collection | complete |
| B | W3/W4 receipt completeness and governed first-hour e2e | integrated locally; agent closed after timeout |
| C | W5/W6 control-loop map and narrow boundary | complete |
| D | W7/W8 adversarial and test-quality repairs | complete |
| E | W9 competitive claim hygiene | complete |

## Verification Log

| Check | Status | Evidence |
|---|---|---|
| Initial git status | done | Only prior analysis artifact was staged/new before implementation pass. |
| `python3 -c "import hypothesis"` | failed | Active interpreter `/opt/homebrew/opt/python@3.14/bin/python3.14` cannot import `hypothesis`. |
| `.venv` acceptance collection | passed | `./.venv/bin/python -m pytest tests/acceptance --collect-only -q` -> 627 tests collected. |
| `.venv` full collection | passed | `./.venv/bin/python -m pytest tests --collect-only -q` -> 6001 tests collected. |
| Receipt / evidence / first-hour slice | passed | `./.venv/bin/python -m pytest tests/test_run_receipt.py tests/acceptance/test_run_evidence_summary_flow.py tests/acceptance/test_first_hour_e2e_flow.py -q` -> 25 passed. |
| Docs / plan / P0 harness slice | passed | `./.venv/bin/python -m pytest tests/acceptance/test_docs_acceptance_count_accuracy.py tests/test_plan_contract.py tests/test_p0_harness.py -q` -> 47 passed. |
| Adversarial / test-quality repair slice | passed | `./.venv/bin/python -m pytest tests/acceptance/test_github_integration_flow.py tests/acceptance/test_hook_lifecycle_flow.py tests/acceptance/test_headless_tui.py tests/acceptance/test_adversarial_over_scope_behavior_flow.py -q` -> 51 passed. |
| Evidence / receipt unit slice | passed | `./.venv/bin/python -m pytest tests/test_run_evidence.py tests/test_evidence_completeness.py tests/test_ws4_observability.py tests/test_run_receipt.py -q` -> 51 passed. |
| Sandbox / receipt-adjacent unit slice | passed | `./.venv/bin/python -m pytest tests/test_sandbox_resolution.py tests/test_run_evidence_summary.py tests/test_model_route_receipt.py tests/test_conversation_ux.py -q` -> 35 passed. |
| Acceptance test quality audit | passed | `./.venv/bin/python scripts/audit_test_quality.py --tests-dir tests/acceptance --format markdown --fail-on none` -> no high-risk no-assertion files. |
| Docs consistency | passed | Regenerated `docs/generated/docs-inventory.md` and `docs/generated/docs-aging-dashboard.md`; `./.venv/bin/python scripts/validate_docs_consistency.py` passed. |
| Diff whitespace | passed | `git diff --check` passed. |

## Open Constraints

- System `python3` still lacks `hypothesis`; project verification should use `.venv/bin/python` or another dev environment with `pyproject.toml` dev dependencies installed.
- `preapproved_call_ids` remains deprecated; this pass only made existing CLI preapproval auditable via `tool_call_approved`.
- Audit level L2 redacts shell command strings by design, so receipt command evidence asserts `[redacted] [exit 0]` rather than the raw command.
- Treat competitor facts as current to 2026-06-11 only.
