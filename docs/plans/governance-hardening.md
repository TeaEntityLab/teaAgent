# Governance Hardening Plan (in-repo)

Last updated: 2026-05-29

## Goal

Close the five governance loops with verifiable runtime behavior—not greenfield modules.

## Status

| Tranche | Scope | Status |
|---------|--------|--------|
| B | tool lint, plan gate, audit completeness, runs trace, selftest | Shipped |
| C | failure cards, MCP trust, read-only `--parallel` | Shipped |
| Hardening | centralized approval queue ↔ `SubagentManager`, CI selftest gate | Shipped |
| CLI | `teaagent approval subagents list|approve|deny|approve-all|deny-all` | Shipped |
| TUI | `approvals subagents` batch table + approve/deny/all | Shipped |
| Tournament | `ParallelExecutor` + `parallel_executor_with_manager` | Shipped |
| Persistence | `.teaagent/approval_queues/<parent_run_id>.json` | Shipped |
| Swarm LLM | `SwarmManager.with_agent_execution` + `SubagentManager` | Shipped |
| Hardening+ | adversarial plugin runtime tests, queue cleanup TTL | Shipped |

## Verification commands

```bash
pytest tests/test_governance_fuzz.py tests/test_governance_adversarial_runtime.py \
  tests/test_tranche_bc_governance.py tests/test_approval_queue_persistence.py \
  tests/test_subagent_approval_queue_integration.py tests/policy/
teaagent approval subagents prune --root . --max-age-hours 168
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
