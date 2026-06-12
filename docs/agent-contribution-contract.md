# Agent Contribution Contract

> **Purpose:** Define the required gates and validation steps that any AI agent (Claude Code, Devin, subagent, or other harness) must pass before contributing to the TeaAgent repository.
>
> **Scope:** All automated commits to the TeaAgent repository, regardless of which agent harness authored them.
>
> **Status:** Active (V4-a, 2026-06-12)

## Problem Statement

The TeaAgent repository is now edited by multiple agent harnesses (Claude Code sessions, subagent lanes, Devin, plus the human owner). TeaAgent's product is agent governance, but its own contribution path had no agent-facing contract. This led to V1 (drift gate failure on main) where a false "verified" claim landed via a second AI agent.

## Required Pre-Commit Gates

Before any agent-authored commit can be made, the following validations must pass:

### 1. Docs Consistency Gate

**Command:** `python3 scripts/validate_docs_consistency.py --test-quality-mode off`

**Purpose:** Ensures documentation claims match runtime state and prevents drift.

**What it checks:**
- Acceptance test count in `docs/acceptance.md` matches pytest collection
- Provider counts are consistent across README, architecture.md, and runtime
- Docs inventory is up to date
- Suite summary freshness (WDB-004) if test counts are cited
- Roadmap required fields are present
- Risk register and ticket index evidence coverage

**Failure mode:** Gate exits non-zero; commit must not proceed.

### 2. Test Collection Gate

**Command:** `python3 -m pytest tests/acceptance --collect-only -q`

**Purpose:** Ensures the test suite is collectible (no import errors, missing dependencies).

**Failure mode:** Collection fails with import errors (e.g., missing `hypothesis` in system Python).

**Note:** The repo venv (`.venv/bin/python`) is preferred for consistency with docs gate.

### 3. Lint and Format Gate

**Commands:**
```bash
ruff check .
ruff format --check .
```

**Purpose:** Ensures code style consistency and catches common errors.

**Failure mode:** Non-zero exit from either command.

### 4. Type Check Gate

**Command:** `mypy teaagent/ tests/ --explicit-package-bases`

**Purpose:** Ensures type annotations are correct and complete.

**Failure mode:** Non-zero exit from mypy.

## Claim-Bearing Files Requiring Passing Gates

The following files contain governance-relevant claims and require a passing gate in the same commit that modifies them:

| File | Claim Type | Required Gate |
|------|------------|---------------|
| `docs/acceptance.md` | Acceptance test count | `test_docs_acceptance_count_accuracy.py` must pass |
| `README.md` | Provider count, feature claims | Provider consistency validation must pass |
| `docs/architecture.md` | Architecture claims, provider counts | Provider consistency validation must pass |
| `docs/roadmap-status.md` | Roadmap claims, status values | Roadmap validation must pass |
| `docs/governance-compliance.md` | Governance gate mappings | Docs consistency validation must pass |
| `docs/generated/suite-summary.json` | Test suite results | Must be regenerated with current commit |

## Commit Trailer Requirements

Agent-authored commits should include the following trailers for traceability:

```
Agent: <agent-name> (e.g., "Claude Code", "Devin", "subagent")
Agent-Session: <session-id-or-context>
Reviewed-by: <human-optional>
```

Example:
```
fix: update acceptance test count to 646

Agent: Devin
Agent-Session: cli-2026-06-12-001
```

## CI Enforcement

The `use-case-matrix` job in `.github/workflows/ci.yml` runs the docs consistency gate as a required check. Branch protection rules must require this check to pass before merging to main.

## Emergency Override

**NO SELF-SERVICE BYPASS ALLOWED** (V4-c fix): Agents cannot bypass their own governance gate via trailers or environment variables. This prevents the exact failure mode the contract is designed to prevent.

In rare cases where a gate must be bypassed (e.g., fixing the gate itself):
1. Human must temporarily disable the CI check via GitHub UI
2. Commit with trailer: `Manual-bypass: <reason> <ticket-id>`
3. Open a PR referencing the bypass
4. Human review required before merge
5. Re-enable CI check after merge

## Implementation Status

- ✅ Docs consistency gate exists and runs in CI
- ✅ Test collection gate exists as acceptance count accuracy test
- ✅ Lint/format/type check gates exist in CI
- ✅ Agent contribution contract gate exists in CI (V4-a)
- ✅ Anti-bypass enforcement implemented (V4-c) - no self-service bypass allowed
- ✅ Fixture tests for contract gate (V4-d) - `tests/test_governance_compliance.py::TestAgentContributionContract`
- ✅ Python interpreter preference (venv over system) for consistency (third-pass fix)
- ✅ Auto-regenerate docs inventory to avoid staleness from multi-agent concurrent edits (third-pass fix)
- ⚠️ Branch protection enforcement requires manual GitHub configuration (see V1-b)

## References

- V1 finding: Drift gate failed open on commit `e2e8317`
- V4 finding: Multi-agent contribution surface ungoverned
- `docs/governance-compliance.md` for full gate mapping
- `scripts/validate_docs_consistency.py` for gate implementation