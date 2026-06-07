# Governance Compliance

> Maps [AGENTS.md](../../AGENTS.md) rules to automated verification.

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

## Manual review

- Skill supply-chain review (`SKILL.md` + `REFERENCE.md` pattern)
- ADR updates for governance boundary changes
