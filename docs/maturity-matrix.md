# TeaAgent Maturity Matrix

Last updated: 2026-05-29 (comprehensive audit P0)

**Audit artifacts:** `docs/analysis/comprehensive-audit-2026-05-29.md`, `docs/plans/remediation-roadmap.md`

## Status Key

| Label | Meaning |
|-------|---------|
| **Stable** | Shipped; acceptance/integration tests; safe for daily use with documented modes |
| **Beta** | Shipped; tests exist; edge cases or UX still hardening |
| **Foundation** | Core code present; incomplete integration or missing production gates |
| **Experimental** | Opt-in; behavior may change |
| **Spec only** | Documented intent; not implemented |

Scale reference (internal engineering, not market validation):

```text
0 Spec only → 1 Unit → 2 Integration → 3 Acceptance → 4 Dogfood → 5 External beta → 6 Production-hardened
```

## Core Governance Loops (Tranche B)

| Feature | Status | Evidence | Next step |
|---------|--------|----------|-----------|
| ToolRegistry + schemas | Stable | `test_workspace_tools.py`, `test_contract_policy.py` | Expand capability manifest |
| `teaagent tool lint` | Stable | `tests/test_tranche_b_governance.py`, CI `governance-gate` job | Expand capability manifest |
| Permission matrix | Stable | `tests/policy/test_permission_matrix.py`, `tests/test_governance_adversarial_runtime.py` | — |
| Plan-before-write (`--require-plan`) | Stable | `tests/test_tranche_b_governance.py`, strict workspace-write default | — |
| Plan-before-write (`--skip-plan-check`) | Beta | `tests/test_governance_fuzz.py` | UX refinement |
| Validation profiles | Beta | `tests/test_tranche_b_governance.py`, `--validation-profile` | Self-healing loop integration |
| Audit completeness gate | Beta | `tests/test_tranche_b_governance.py` | Wire into release checklist |
| `runs trace/export/replay` | Beta | `tests/test_tranche_b_governance.py` | TUI surface |
| `doctor selftest` / `teaagent selftest` | Stable | `tests/test_tranche_bc_governance.py`, CI `governance-gate` job | — |
| Audit chain + redaction | Stable | `test_audit_chain_integrity_flow.py` | Audit level tiers |
| Run undo | Stable | `test_run_undo_acceptance_flow.py` | — |
| Failure cards (TTL/invalidate) | Stable | `tests/test_governance_fuzz.py`, automated invalidation rules | — |
| Failure cards (auto-invalidation CLI) | Beta | `teaagent memory failures auto-invalidate` | Per-project customization |
| Centralized approval queue | Beta | Disk persistence + cross-process approve, CLI/TUI, `approval subagents prune` | — |
| Multi-agent / tournament | Beta | `SwarmManager`, `select_winner_from_subagent_results`, prompt gene pool | Hosted tournament dashboards |
| MCP trust policy CLI | Beta | `tests/test_tranche_bc_governance.py`, `mcp trust` | Per-server defaults |
| Read-only numeric `--parallel` | Beta | CLI guard in `agent run` | Swarm read-only analysis |
| Governance fuzz tests | Stable | `tests/test_governance_fuzz.py`, `tests/test_governance_hardening.py` | — |
| CI governance gate | Stable | `.github/workflows/ci.yml` governance-gate job | — |
| Phase 4 consensus | Beta | `vote_relay` rate limits, SSH verify unified | WAN deployment runbooks |
| Phase 5 sandbox routing + execution | Beta | `wasm-skill-build.yml`, `sandbox wasm-contract` | Org-wide WASM signing in CI |
| Phase 6 skill writer / control plane | Beta | `gateway_oauth`, path tenant routes, OAuth templates | External IdP automation |

## Surfaces (summary)

| Surface | Status | Primary test |
|---------|--------|--------------|
| CLI / TUI | Stable | `test_daily_cli.py`, `test_cli_tui_surface_parity_flow.py` |
| First-hour onboarding | Stable | `test_first_hour_e2e_flow.py` |
| VS Code extension | Stable | `test_vscode_extension_mcp_boot_flow.py` |
| Plugin install gate | Beta | `test_plugin_install_security_flow.py` |
| Code Mode container | Beta | `docker_sandbox.py`, `tests/test_phase6_docker.py` | Docker dogfood benchmarks |
| Managed cloud runtime | Foundation | `test_managed_runtime_flow.py` |

## Honest External Posture

- Public repo activity ≠ production validation.
- **Internal acceptance coverage is strong** (80+ flows under `tests/acceptance/`).
- External adoption signals (stars, forks, production references) remain early — do not infer enterprise readiness from architecture alone.

## Related Docs

- [product-contract.md](product-contract.md) — what TeaAgent is / is not
- [threat-model.md](threat-model.md) — security threats and tests
- [use-cases.md](use-cases.md) — parity traceability vs mainstream coding agents
- [backlog-priority.md](backlog-priority.md) — shipped vs open engineering items
