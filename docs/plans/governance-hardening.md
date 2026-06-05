# Governance Hardening Plan (in-repo)

> Supersession note, 2026-06-05: This file is historical evidence from the
> earliest governance pass (2026-05-28). The governance loops were hardened in
> Phase 0 work. For current governance rules, use
> `docs/governance/documentation-operating-model-2026-06-04.md` and
> `docs/governance/README.md`. For closure evidence, use
> `docs/work-log/phase-0-governance-closure-report-2026-06-04.md`.

Last updated: 2026-05-28 (Phase 4–6 verification)

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
| Phase 5 | Skill sandbox routing + execution (`isolation=auto`, `skill_executor`) | Beta |
| Phase 6 | Skill writer, docker monitor, control plane, prompt tournament | Beta |

## Verification commands

```bash
pytest tests/test_governance_fuzz.py tests/test_governance_adversarial_runtime.py \
  tests/test_tranche_bc_governance.py tests/test_approval_queue_persistence.py \
  tests/test_subagent_approval_queue_integration.py tests/policy/
pytest tests/test_skill_executor.py tests/test_phase6_*.py
pytest tests/acceptance/test_consensus_flow.py tests/acceptance/test_sandbox_enhancement_flow.py
teaagent control-plane serve --host 127.0.0.1 --port 8765  # manual smoke; Ctrl+C to stop
teaagent approval subagents prune --root . --max-age-hours 168
teaagent selftest --root .
teaagent tool lint --root .
```

## Open decisions

1. **Swarm LLM execution** — real adapter path exists via `SwarmManager.with_agent_execution`; deeper tournament benchmarks remain optional.
2. **Phase 4–6** — consensus, sandbox execution, and control-plane CLI are **Beta** with acceptance/unit tests (see `docs/backlog-priority.md`).
3. **Dependabot #10** — reconcile GitHub Security alert if `pip-audit` stays clean (see `SECURITY.md`).

## Related

- [maturity-matrix.md](../maturity-matrix.md)
- [threat-model.md](../threat-model.md)
- [product-contract.md](../product-contract.md)
