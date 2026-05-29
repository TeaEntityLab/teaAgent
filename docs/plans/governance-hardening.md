# Governance Hardening Plan (in-repo)

Last updated: 2026-05-28

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
| Hardening+ | adversarial plugin runtime tests, queue cleanup TTL, handler AST gate | Shipped |
| Refactor | `teaagent.sandbox` package, approval store module split | Shipped |
| Phase 4 | Federated consensus + swarm pre-approval gate | Beta |
| Phase 5 | Skill sandbox routing (`isolation=auto`) + docker limits | Beta |

## Verification commands

```bash
pytest tests/test_governance_fuzz.py tests/test_governance_adversarial_runtime.py \
  tests/test_tranche_bc_governance.py tests/test_approval_queue_persistence.py \
  tests/test_subagent_approval_queue_integration.py tests/policy/
pytest tests/acceptance/test_consensus_flow.py tests/acceptance/test_sandbox_enhancement_flow.py
teaagent approval subagents prune --root . --max-age-hours 168
teaagent selftest --root .
teaagent tool lint --root .
```

## Open decisions

1. **Swarm LLM execution** — real adapter path exists via `SwarmManager.with_agent_execution`; deeper tournament benchmarks remain optional.
2. **Phase 4–5** — consensus and sandbox routing are **Beta** with acceptance tests; async voting UX and WASM execution remain optional hardening (see `docs/backlog-priority.md`).
3. **Dependabot #10** — reconcile GitHub Security alert if `pip-audit` stays clean (see `SECURITY.md`).

## Related

- [maturity-matrix.md](../maturity-matrix.md)
- [threat-model.md](../threat-model.md)
- [product-contract.md](../product-contract.md)
