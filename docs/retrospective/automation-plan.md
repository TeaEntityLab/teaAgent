# Automation Plan

> Phase B design document | Purpose: convert the criteria and gates in [review-system.md](review-system.md) into an executable automation pipeline.
> Design principle: **reuse the existing 7 CI workflows and 10 pre-commit hooks; fill gaps instead of rebuilding**.

## 1. Current Automation Inventory

### 1.1 Pre-commit Hooks (`.pre-commit-config.yaml`, 10 hooks)

| Hook | Purpose | Related review criteria |
| --- | --- | --- |
| lore-trailers | Commit trailer format | - |
| check-circular-imports | Circular dependencies | 4.1 General |
| check-event-spine-wiring | ADR-0032 event spine | 4.1 General |
| ruff-format | Formatting | 4.1 General |
| ruff (`--fix --exit-non-zero-on-fix`) | Lint + automatic fixes | 4.1 General |
| mypy | Types | 4.1 General |
| check-public-docstrings | Public API docstrings | 4.1 General |
| check-test-assertion-regression | A1 gate (test quality) | 4.1 General |
| pytest (smoke or `TEAAGENT_PRECOMMIT_FULL=1`) | Tests | 4.1 General |
| check-docs-inventory | Documentation inventory | 4.4 Documentation |

### 1.2 CI Workflows (`.github/workflows/`, 7 workflows)

| Workflow | Purpose | Related criteria |
| --- | --- | --- |
| `ci.yml` | Lint + tests + coverage + governance gates | 4.1, 4.4 |
| `security.yml` | pip-audit + Bandit + CodeQL | 4.2 High risk |
| `nightly-mutation` | Mutation testing | 4.1 In-depth |
| `nightly-smoke` | Provider smoke tests (claude/gpt/gemini/openrouter/opencodezen-go) | 4.1 In-depth |
| `publish-tsb` | TSB publication | - |
| `release` | Release pipeline | 4.2 Release |
| `wasm-skill-build` | WASM skill compilation | 4.3 Skills |

### 1.3 Scripts (`scripts/`)

`check_circular_imports.py`, `check_complexity.py` (baseline 99), `check_root_module_count.py` (baseline 184), `run_test_tier.py`, `validate_docs_consistency.py`, `validate_event_spine_wiring.py`, `check_test_assertion_regression.py`, `check_public_docstrings.py`, `check_test_quality.py`, `check_config_access.py` (max 65), and `agent_contribution_contract.py`.

### 1.4 Existing Gaps Exposed by Phase A

- The Bandit step in `ci.yml` is non-blocking ([01](01-security-risk.md) G11) and must be fixed.
- There is no CI check for audit-event schema conformance ([02](02-tool-governance.md) G-1); one must be added.
- There is no validation that the `--no-tui` flag exists, allowing documentation/code drift ([04](04-ux-usability.md) G-H2); one must be added.
- There is no executability check for onboarding documentation commands ([04](04-ux-usability.md) G-H1); one must be added.
- There is no TUI command-path coverage ([04](04-ux-usability.md) G-M1); one must be added.
- There is no automatic trigger detection for high-risk PRs ([review-system.md](review-system.md) 4.2); one must be added.
- There is no self-review checklist conformance validation ([review-system.md](review-system.md) G2); one must be added.
- There is no action-register link validation ([review-system.md](review-system.md) G9); one must be added.

## 2. Automation Layers

```
Layer 0 - During editing (IDE/LSP)
Layer 1 - At commit time (pre-commit)
Layer 2 - At push time (CI smoke)
Layer 3 - High-risk trigger (CI high-risk gate)
Layer 4 - Nightly/periodic (nightly + cron)
Layer 5 - Quarterly review/retrospective (manual + automated reports)
```

## 3. Automation Design by Layer

### Layer 0 - During Editing

- **cx LSP**: `teaagent code-definition` / `code-references`, already present in `code_analysis/_tools.py:21-280`, provides semantic IDE navigation.
- **TypeScript/Python LSP**: the mypy daemon (`dmypy`) provides continuous type checking.
- **ruff LSP**: provides real-time linting.
- **Out of scope**: do not build a custom IDE plugin; reuse cx and existing LSPs.

### Layer 1 - At Commit Time (Pre-commit Extensions)

**Retain the existing 10 hooks.** Add:

| New hook | Purpose | Related gap |
| --- | --- | --- |
| `check-action-register-link.py` | Require the commit message or staged files to contain an action ID (`<dimension>-P<priority>-<sequence>`) or a new entry in `docs/retrospective/06-action-register.md` | review-system G9 |
| `check-high-risk-paths.py` | When staged files touch a path listed in [review-system.md](review-system.md) 4.2, require `docs/reviews/<pr-id>-risk.md` with a `reflective-risk` report | review-system G4 |
| `check-skill-md-length.py` | Require Git-tracked SKILL.md files under `.opencode/skill/` and `teaagent/skills/` to be at most 80 lines (error for installed skills, warning for development skills) | AGENTS.md Skills |
| `check-docs-drift.py` (extension of `validate_docs_consistency.py`) | Require flags and commands mentioned in documentation to exist in code, including `--no-tui`, `teaagent skill install`, and `--parallel "string"` | 04 G-H1, G-H2 |
| `check-error-reference-sync.py` | Keep exit codes in `docs/error-reference.md` consistent with the `errors.py` enum | 04 G-H5 |

**Example `check-high-risk-paths.py` logic**:

```python
HIGH_RISK_PATTERNS = [
    "teaagent/approval_*.py", "teaagent/approval/", "teaagent/policy.py",
    "teaagent/audit*.py", "teaagent/audit_chain.py",
    "teaagent/sandbox/", "teaagent/docker_sandbox.py", "teaagent/git_sandbox.py",
    "teaagent/tool_permissions.py", "teaagent/workspace_tools/_shell.py",
    "teaagent/mcp_trust.py", "teaagent/provenance_gate.py", "teaagent/prompt_gate.py",
    "teaagent/runner/_core.py",  # budget/approval/JIT sections
    "teaagent/budget.py", "teaagent/budget_monitor.py", "teaagent/scope_budget.py",
    "docs/audit-event.schema.json",
]
# If any staged file matches, verify that docs/reviews/<pr>-risk.md exists.
# Otherwise, fail and instruct the user to run the reflective-risk skill.
```

### Layer 2 - At Push Time (CI Smoke Extensions)

**Retain the existing `ci.yml`.** Add these jobs:

| New job | Purpose | Related gap |
| --- | --- | --- |
| `audit-schema-conformance` | Use `jsonschema` to verify that `docs/audit-event.schema.json` validates every chained event written by `AuditLogger`, sampling the latest N entries in `.teaagent/audit/*.jsonl` | 02 G-1 |
| `review-institution-gate` | Verify that the PR description includes an action ID, a self-review checklist link, and a risk-class self-assessment; for high-risk classes, verify that `docs/reviews/<pr>-risk.md` exists | review-system G2, G4, G9 |
| `tui-command-coverage` | Run smoke tests for TUI dispatch and published commands; even if `tui/*` is omitted from coverage, dispatch and command existence must be tested | 04 G-M1 |
| `docs-command-executability` | Parse `teaagent ...` commands in documentation and run them with `--help` to verify existence without executing side-effecting commands | 04 G-H1 |
| `error-reference-sync` | Verify that the exit-code table in `docs/error-reference.md` matches constants in `teaagent/cli/__init__.py` | 04 G-H5 |
| `agent-md-compliance` | Run `teaagent selftest` plus a new `selftest --check-agents-md` option that validates 12 rules: schema completeness, tool registry, audit chain, budget, and SKILL.md length | 05 compliance matrix |

**Example `audit-schema-conformance` logic**:

```yaml
- name: Audit schema conformance
  run: |
    python - <<'PY'
    import json, jsonschema, pathlib
    schema = json.load(open("docs/audit-event.schema.json"))
    # Sample the latest 100 audit events.
    for audit_file in pathlib.Path(".teaagent/audit").glob("*.jsonl"):
        for line in audit_file.read_text().splitlines()[-100:]:
            event = json.loads(line)
            jsonschema.validate(event, schema)  # Must pass.
    PY
```

> **Prerequisite**: fix [02 G-1](02-tool-governance.md) first by adding `prev_hash`, `hash`, and `chain_hmac` to the schema. Otherwise, this job will fail for every chained event.

### Layer 3 - High-Risk Trigger (CI High-Risk Gate)

When a PR touches a path listed in [review-system.md](review-system.md) 4.2, CI automatically:

1. **Applies the `risk-class: high` label**.
2. **Requires `docs/reviews/<pr-id>-risk.md`** containing:
   - Output from the `reflective-risk` skill (dry-run + rollback plan)
   - A Security Officer sign-off section for Size C, or a second reviewer's SSH signature for Size B
3. **Runs additional tests**:
   - `tests/policy/test_permission_matrix.py` (existing)
   - `tests/test_audit_chain.py` (existing)
   - `tests/test_approval_token_exactness.py` (existing)
   - A new `tests/test_high_risk_path_coverage.py`: changes to high-risk paths must include a corresponding test diff
4. **Makes Bandit blocking**: the Bandit step is blocking for high-risk PRs, fixing [01 G11](01-security-risk.md).

**Trigger detection**: use the `dorny/paths-filter@v3` action or `tj-actions/changed-files`.

### Layer 4 - Nightly/Periodic (Nightly + Cron Extensions)

**Retain the existing `nightly-mutation`, `nightly-smoke`, and weekly `security.yml`.** Add:

| New workflow | Frequency | Purpose | Related cadence |
| --- | --- | --- | --- |
| `audit-health-cron.yml` | Daily | Run `teaagent audit_health` against recent runs; produce `docs/audits/<YYYY-MM-DD>.md`; open an issue for chain anomalies | review-system 5 - audit-chain health |
| `coverage-omit-review.yml` | Monthly | Open reminder issues for due return milestones in `docs/governance/coverage-omit-ledger.md` | review-system 5 - coverage-omit recovery |
| `dependency-security-monthly.yml` | Monthly | Run `pip-audit` across the full extras matrix + `uv tree --outdated`; produce `docs/audits/<YYYY-MM>-deps.md` | review-system 5 - dependency security |
| `skill-supply-chain-monthly.yml` | Monthly | Run `teaagent skill lifecycle report` + `review_skill` for candidate skills; retire expired candidates | review-system 5 - skill supply chain |
| `adr-status-quarterly.yml` | Quarterly | Assess statuses under `docs/adr/`, including cleanup of Superseded/Archived entries; produce `docs/audits/<YYYY-Qn>-adr.md` | review-system 5 - ADR review |

### Layer 5 - Quarterly Review/Retrospective

- **Automated report generator**: `scripts/generate_quarterly_retrospective.py` aggregates the quarter's:
  - Action-register progress (completed/pending/cancelled)
  - Newly discovered gaps from `audit-health-cron`, `dependency-security-monthly`, and `skill-supply-chain-monthly`
  - ADR status changes
  - Coverage-omit recovery progress
  - It produces `docs/retrospective/<YYYY-MM>/README.md` following the structure of this document set
- **Manual review**: the Auditor chairs the quarterly review meeting and produces the next quarter's action-register update.

## 4. Tool and Command Mapping

| Automation need | Tool/command | Existing? |
| --- | --- | --- |
| Lint | `ruff check` | Yes |
| Formatting | `ruff format --check` | Yes |
| Types | `mypy teaagent/` | Yes |
| Coverage | `pytest --cov=teaagent --cov-fail-under=75` | Yes |
| Complexity | `scripts/check_complexity.py --max 99` | Yes |
| Root module count | `scripts/check_root_module_count.py` | Yes |
| Circular dependencies | `scripts/check_circular_imports.py` | Yes |
| Event-spine wiring | `scripts/validate_event_spine_wiring.py` | Yes |
| Documentation consistency | `scripts/validate_docs_consistency.py` | Yes |
| Public docstrings | `scripts/check_public_docstrings.py` | Yes |
| Test assertion regression | `scripts/check_test_assertion_regression.py` | Yes |
| Test quality | `scripts/check_test_quality.py` | Yes |
| Config access | `scripts/check_config_access.py --max 65` | Yes |
| Agent contribution contract | `scripts/agent_contribution_contract.py` | Yes |
| Bandit | `bandit -r teaagent/ -c pyproject.toml` | Yes, but non-blocking in `ci.yml` |
| pip-audit | `pip-audit` | Yes, in `security.yml` |
| CodeQL | GitHub CodeQL | Yes |
| Dependabot | GitHub Dependabot | Yes |
| Audit health | `teaagent audit_health` / `audit_chain.verify` | Yes, in `audit_health.py` |
| Skill review | `teaagent skill review` / `review_skill` | Yes, in `skill_review.py` |
| Self-test | `teaagent selftest` | Yes, in `selftest.py` |
| Doctor | `teaagent doctor` | Yes |
| **Audit schema conformance** | `jsonschema` + schema | **Must be added** |
| **High-risk path detection** | `dorny/paths-filter` | **Must be added** |
| **Action-register link check** | `scripts/check_action_register_link.py` | **Must be added** |
| **Documentation command executability** | `scripts/check_docs_command_executability.py` | **Must be added** |
| **Error-reference synchronization** | `scripts/check_error_reference_sync.py` | **Must be added** |
| **TUI command coverage** | `tests/tui/test_command_dispatch.py` | **Must be added** |
| **AGENTS.md compliance** | `teaagent selftest --check-agents-md` | **Must be added** |
| **Quarterly retrospective generator** | `scripts/generate_quarterly_retrospective.py` | **Must be added** |

## 5. Integration with the Existing 7 CI Workflows

**Extend existing workflows for push and release paths. Add dedicated cron workflows only when their cadence or permissions differ from existing schedules**:

- `ci.yml`: after the lint job, add six steps: `audit-schema-conformance`, `review-institution-gate`, `tui-command-coverage`, `docs-command-executability`, `error-reference-sync`, and `agent-md-compliance`.
- `ci.yml`: remove `|| echo "::warning::..."` from the Bandit step, fixing [01 G11](01-security-risk.md).
- `security.yml`: retain it; Layer 3 separately handles the additional blocking Bandit check for high-risk PRs.
- `nightly-smoke`: retain it; extend it to run `audit_health` and produce a report.
- Add five dedicated cron workflows because they use distinct daily, monthly, or quarterly cadences: `audit-health-cron.yml`, `coverage-omit-review.yml`, `dependency-security-monthly.yml`, `skill-supply-chain-monthly.yml`, and `adr-status-quarterly.yml`.

## 6. Failure Handling

| Failure type | Behavior | Related rule |
| --- | --- | --- |
| Lint/format/mypy failure | Blocking | 4.1 |
| Coverage < 75% | Blocking | 4.1 |
| Smoke-test failure | Blocking | 4.1 |
| Audit-schema conformance failure | Blocking | 4.2 G6 |
| High-risk path without a `reflective-risk` report | Blocking | 4.2 G4 |
| Action register without an ID link | Blocking, with an optional `new-action` label exemption | 4.1 G9 |
| Documentation command does not exist | Warning, then blocking after a grace period | 4.4 |
| Error reference is out of sync | Blocking | 4.4 |
| Installed SKILL.md > 80 lines | Blocking | 4.3 |
| Development SKILL.md > 80 lines | Warning | 4.3 |
| Bandit medium+ | Blocking for high-risk PRs / warning otherwise | 4.2 |
| Audit-chain health anomaly | Open an issue + notify the Auditor | 5 |

## 7. Phased Rollout

### Phase 0 - Fix P0 Issues (1 Week)
- Fix [01 G11](01-security-risk.md): make Bandit blocking in `ci.yml`.
- Fix [02 G-1](02-tool-governance.md): add chain fields to `docs/audit-event.schema.json`.
- Fix [04 G-C1, G-H5](04-ux-usability.md): unify URLs and correct the error reference.

### Phase 1 - Foundation Gates (2 Weeks)
- Add pre-commit hooks: `check-action-register-link.py`, `check-docs-drift.py`, `check-error-reference-sync.py`, and `check-skill-md-length.py`.
- Add CI jobs: `audit-schema-conformance`, `error-reference-sync`, and `docs-command-executability`.
- Extend `teaagent selftest` with `--check-agents-md`.

### Phase 2 - High-Risk Gates (2 Weeks)
- Add the `check-high-risk-paths.py` pre-commit hook.
- Add the CI jobs `review-institution-gate`, `tui-command-coverage`, and `agent-md-compliance`.
- Extend the PR template with an action-ID field, risk-class self-assessment field, and self-review checklist link.

### Phase 3 - Periodic Reviews (1 Month)
- Add five cron workflows: `audit-health-cron`, `coverage-omit-review`, `dependency-security-monthly`, `skill-supply-chain-monthly`, and `adr-status-quarterly`.
- Extend `teaagent doctor` with the `doctor review-institution` subcommand.

### Phase 4 - Quarterly Review Automation (1 Month)
- Add `scripts/generate_quarterly_retrospective.py`.
- Run the complete process at the first quarterly review and produce `docs/retrospective/<YYYY-MM>/`.

## 8. Out of Scope

- Do not build a custom CI system; use GitHub Actions.
- Do not rebuild linting, typing, or coverage tools; use ruff, mypy, and pytest-cov.
- Do not enable every blocking gate in solo mode, because that would encourage bypasses. Size A can set the `TEAAGENT_REVIEW_INSTITUTION=solo` environment variable to downgrade selected blocking checks to warnings.
- Do not fully automate the quarterly review. Manual review remains the Auditor's responsibility; automation only produces reports.
- Do not hard-code high-risk trigger conditions in multiple places. Centralize them in `scripts/high_risk_paths.yaml` as the single source shared by pre-commit and CI.

## 9. Mapping to Existing Governance Assets

| Automation item | Reused existing asset |
| --- | --- |
| Audit-schema conformance | `docs/audit-event.schema.json` + `AuditLogger` in `audit.py` + `audit_chain.py` |
| High-risk path detection | Sensitive-path collection in `approval_manager.py`, reusing the `_PROTECTED_SKILL_PATTERNS` pattern |
| Action-register link | `docs/retrospective/06-action-register.md` as the single source |
| Self-test extension | `teaagent selftest` + `selftest.py` |
| Doctor extension | `teaagent doctor` + `cli/_handlers/_doctor.py` |
| Skill review | `skill_review.py` + `skill_lifecycle.py` |
| Audit health | `audit_health.py` + `audit_chain.py:verify_audit_chain` |
| Coverage-omit governance | `docs/governance/coverage-omit-ledger.md` + `validate_docs_consistency.py` |
| Documentation consistency | `validate_docs_consistency.py` |
| Event-spine wiring | `validate_event_spine_wiring.py` |
| RBAC | `governance/rbac.py` + `governance/policy_engine.py` for Size C |

## 10. Success Metrics

| Metric | Target | Measurement |
| --- | --- | --- |
| P0 action completion rate | 100% by the end of Phase 0 | Status column in `06-action-register.md` |
| Audit-schema conformance pass rate | 100% | CI job |
| High-risk PR `reflective-risk` report coverage | 100% | CI job + PR label |
| Actual blocks by blocking Bandit | > 0 per quarter | CI records |
| Documentation command executability pass rate | 100% | CI job |
| Error-reference synchronization pass rate | 100% | CI job |
| SKILL.md violations | 0 installed / < 5 development | Pre-commit + CI |
| Action-register link rate | 100% of PRs | CI job |
| Quarterly review report production rate | 1 per quarter | `docs/retrospective/<YYYY-MM>/` |
| Audit-chain health anomaly detection time | < 24 hours | `audit-health-cron` |
| Coverage-omit recovery rate | 100% of due entries | `coverage-omit-review` |

> See [review-system.md](review-system.md) for review roles and criteria, and [tool-capability-review.md](tool-capability-review.md) for the tool-capability self-review.
