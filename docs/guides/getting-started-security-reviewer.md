# Getting Started — Security Reviewer

> **Last reviewed:** 2026-06-06
> **Persona:** Security, compliance, or audit reviewer evaluating TeaAgent

Start with the **trust model**, not the feature list. TeaAgent's value is
making agent actions **provable** — not claiming zero risk.

## Primary artifact

[Trust and Audit Whitepaper](../governance/trust-and-audit-whitepaper.md) —
guarantees, non-goals, failure modes, verification commands.

Enterprise NIST mapping detail: [Security Whitepaper](../security-whitepaper.md).

## Evidence to request from operators

1. Sample run audit log: `.teaagent/runs/<run_id>.jsonl`
2. Chain verification output: `teaagent audit verify --root .`
3. Compliance export: `teaagent audit export <run_id> --output bundle.json`
4. Config lint: `teaagent doctor config-lint --root .`
5. Permission policy: `teaagent approval list --root .`

## Key controls to test

| Control | Test |
| --- | --- |
| Read-only blocks writes | Run with `--permission-mode read-only`; confirm `ToolPermissionError` |
| Approval exactness | Scoped grant must match tool + arguments (see `tests/test_approval_token_exactness.py`) |
| Path containment | Symlink / traversal blocked (`tests/test_ws3_schema_path_containment.py`) |
| Compliance mode | `TEAAGENT_COMPLIANCE_MODE=1` aborts on audit disk failure |
| Prompt injection boundaries | [prompt-injection-trust-boundaries.md](../governance/prompt-injection-trust-boundaries.md) |

## Known gaps (honest)

- No SOC 2 certification bundled with the OSS harness
- Provider-side retention is out of scope
- Remote MCP servers are high-trust-boundary — require explicit review
- Plugin code is not cryptographically signed by default

## Automated regression suite

```bash
python3 -m pytest tests/test_ws3_compliance_audit.py \
  tests/test_ws3_strict_audit_chain.py \
  tests/test_prompt_injection_boundaries.py \
  tests/test_approval_token_exactness.py -q
```

## When to reject TeaAgent

See [When Not to Use TeaAgent](when-not-to-use-teaagent.md) for deployment shapes
where another product is a better fit.
