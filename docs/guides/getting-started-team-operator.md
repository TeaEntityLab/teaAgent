# Getting Started — Team Operator

> **Last reviewed:** 2026-06-06
> **Persona:** Platform / DevOps engineer rolling out TeaAgent to a team or CI

You need **repeatable, auditable agent runs** across workspaces — shared
approval policy, budget defaults, and evidence for incident review.

## Workspace bootstrap

```bash
teaagent setup --root /path/to/repo \
  --provider gpt \
  --permission-mode prompt \
  --write-env

teaagent approval preset dev-safe --root /path/to/repo
teaagent doctor config-lint --root /path/to/repo
```

Review `doctor config-lint` findings before enabling destructive modes in CI.

## Team policy patterns

| Pattern | Setting |
| --- | --- |
| CI read-only analysis | `--permission-mode read-only` in pipelines |
| Human-gated writes | `--permission-mode prompt` + approval presets |
| Shared subagent approvals | `teaagent approval subagents list --root .` |
| Compliance fail-closed | `TEAAGENT_COMPLIANCE_MODE=1` on regulated runners |
| Cost ceiling | `TEAAGENT_MAX_ESTIMATED_COST_CENTS` or CLI flag |

## Observability for operators

```bash
teaagent approval pending --human --root .
teaagent audit verify --root .
teaagent audit export <run_id> --output evidence.json --root .
teaagent doctor config-lint --root .
```

Run receipts include latency metrics and audit durability health (WS4).

## CI integration

- Headless runs: omit TUI; use JSON output (`teaagent run ...` without `--human`)
- Gate merges on read-only agent tasks where possible
- Store `.teaagent/runs/` artifacts as CI job outputs for failed runs

## References

- [Approval Policy Design](approval-policy-design.md)
- [Performance Tuning § Server](performance-tuning.md)
- [Trust and Audit Whitepaper](../governance/trust-and-audit-whitepaper.md)
