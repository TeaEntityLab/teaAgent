# Governance Hardening Plan (in-repo)

Last updated: 2026-05-29

## Goal

Close the five governance loops with verifiable runtime behavior—not greenfield modules.

## Status

| Tranche | Scope | Status |
|---------|--------|--------|
| B | tool lint, plan gate, audit completeness, runs trace, selftest | Shipped |
| C | failure cards, MCP trust, read-only `--parallel` | Shipped |
| Hardening | centralized approval queue ↔ `SubagentManager`, CI selftest gate | Shipped (this tranche) |
| Next | parent TUI batch approve, full swarm LLM path, adversarial plugin runtime tests | Open |

## Verification commands

```bash
pytest tests/test_governance_fuzz.py tests/test_tranche_bc_governance.py \
  tests/test_subagent_approval_queue_integration.py tests/policy/
teaagent selftest --root .
teaagent tool lint --root .
```

## Open decisions

1. **Parent TUI** for `CentralizedApprovalQueue` batch approve/deny (queue is wired; UX pending).
2. **Swarm LLM execution** still uses sandbox placeholder; lineage records queue mode when `parent_run_id` is set.
3. **Phase 4–5** (federated consensus E2E, WASM sandbox routing)—see `docs/backlog-priority.md`.

## Related

- [maturity-matrix.md](../maturity-matrix.md)
- [threat-model.md](../threat-model.md)
- [product-contract.md](../product-contract.md)
