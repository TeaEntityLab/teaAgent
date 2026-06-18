# Governance Compliance

> Maps [AGENTS.md](../AGENTS.md) rules to automated verification.

| Rule | Verification |
|------|----------------|
| Tools registered through ToolRegistry | `tests/test_governance_compliance.py` |
| Each tool has name, description, schemas, annotations | `tests/test_governance_compliance.py` |
| Destructive tools require approval token | `tests/test_governance_compliance.py`, `tests/test_governance_fuzz.py` |
| Every run has iteration and tool-call limits | `tests/test_governance_compliance.py` |
| Tool calls recorded in audit log | `tests/integration/test_audit_chain.py` |
| Tool errors actionable and classified | `docs/error-reference.md`, `teaagent/errors.py` |

## CI gates

- `governance-gate` job in `.github/workflows/ci.yml`
- `pytest tests/test_governance_compliance.py` (15 tests)
- `pytest tests/test_governance_fuzz.py`
- `use-case-matrix` job in `.github/workflows/ci.yml` includes docs consistency gate (line 38-39): `python3 scripts/validate_docs_consistency.py`

## Branch protection requirements

To prevent drift gate failures from landing on main (V1-b enforcement gap):
- The `use-case-matrix` CI job must be configured as a **required check** in GitHub branch protection rules for the `main` branch
- This ensures that commits with failing docs consistency validation cannot be merged
- Configuration path: GitHub repo → Settings → Branches → Branch protection rule for `main` → Require status checks to pass before merging → add `use-case-matrix`

## Manual review

- Skill supply-chain review (`SKILL.md` + `REFERENCE.md` pattern)
- ADR updates for governance boundary changes
