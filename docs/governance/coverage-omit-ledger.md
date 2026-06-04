# Coverage Omit Ledger

This document maintains the governance ledger for all files and directories
omitted from test coverage reporting in `pyproject.toml` under
`[tool.coverage.run].omit`.

The ledger is not a permission slip for untested code. An omit pattern is
acceptable only when it has an owner surface, a reason, a risk rating, a return
milestone, and at least one smoke-test candidate or current adjacent evidence.
`scripts/validate_docs_consistency.py` checks that the omit patterns listed here
match `pyproject.toml`.

## Ledger

| Omit Pattern | Owner | Reason | Risk | Expected Return Milestone | Smoke-Test Candidate |
|---|---|---|---|---|---|
| `teaagent/tui/*` | Platform UX Team | Stateful terminal interface with rendering, command loops, and prompt-toolkit behavior that is noisy in line coverage. | Medium: UI/UX regressions in the daily cockpit can mislead users even when core logic works. | Phase 1: move command-path tests from smoke to coverage where practical. | `tests/acceptance/test_headless_tui.py`, `tests/test_tui.py`, `tests/test_tui_interactive.py` |
| `teaagent/tournament/*` | Swarm Consensus Team | Optional tournament mechanics for federated evaluation paths. | Medium: coordination scoring or ranking drift can silently reduce swarm quality. | Phase 2: add deterministic tournament scenario coverage before production swarm positioning. | `tests/test_tournament.py`, `tests/test_tournament_parallel_executor.py`, `tests/acceptance/test_consensus_flow.py` |
| `teaagent/validation/*` | Governance Team | Static validation rule definitions and schema-like helpers are easier to assert through rule outcomes than raw line coverage. | Low: static rule drift is usually caught by validators, but missing rule coverage can weaken governance claims. | Phase 1: add rule parsing and invalid-rule fixture coverage. | `tests/test_validation.py`, `tests/test_tranche_b_governance.py` |
| `teaagent/workflow_engine.py` | Subagents Team | Background workflow graph executor with async/state-machine behavior. | Medium: lock, state transition, or retry bugs can break long-running agent workflows. | Phase 1: add headless workflow transition tests with persistence fixtures. | `tests/test_phase5_workflow_engine.py`, `tests/test_phase4_workflow_engine.py` |
| `teaagent/vote_relay.py` | Swarm Consensus Team | Peer voting and attestation relay behavior depends on transport and multi-node setup. | Medium: transport or auth drift can weaken consensus evidence. | Phase 2: add relay transport mocks and signature edge-case coverage. | `tests/acceptance/test_security_vote_relay_flow.py`, `tests/test_surface_auth_hardening.py` |
| `teaagent/tls_server.py` | Security Team | TLS/mTLS listener helpers depend on generated certs and socket wrapping. | High: handshake or certificate mistakes can expose remote control surfaces. | Phase 1: add encrypted local tunnel e2e and negative-cert fixtures. | `tests/acceptance/test_security_tls_server_flow.py` |
| `teaagent/webhook_sink.py` | Platform Team | External webhook posting is integration-shaped and better checked with a local HTTP target. | Low: delivery regressions affect observability more than core safety. | Phase 2: add telemetry mock validation and retry/backoff checks. | `tests/acceptance/test_webhook_audit_flow.py`, `tests/integration/test_webhook_sink.py` |
| `teaagent/wasm_runtime.py` | Sandbox Team | Optional WASM engine depends on optional `wasmer` availability and platform support. | Medium: sandbox execution or memory isolation bugs can affect optional untrusted-code paths. | Phase 1: add conditional WASM engine integration tests that skip only when runtime is unavailable. | `tests/test_wasm_runtime.py` |
| `teaagent/wasm_skill.py` | Sandbox Team | WASM-packaged skill manifest and invocation contract logic is tied to optional skill build flows. | Medium: package validation drift can allow invalid or unsafe skill artifacts. | Phase 1: add manifest validation and compilation-mock coverage. | `tests/test_phase6_remaining_features.py`, `tests/test_skill_executor.py` |
| `teaagent/tsb_format.py` | Governance Team | Tool signing bundle serialization spans filesystem, audit evidence, and manifest verification. | Medium: bundle parsing differences can weaken supply-chain evidence. | Phase 1: keep unit coverage plus lifecycle integration before release packaging. | `tests/test_tsb_format.py`, `tests/integration/test_tsb_lifecycle.py` |
| `teaagent/workspace_tools/builder.py` | Workspace Team | Builder wraps local workspace tool registration and setup paths. | Low: local setup wrapper errors are likely visible quickly, but can confuse first-run UX. | Phase 1: add local tool setup smoke tests to coverage suite. | `tests/test_workspace_tools.py::WorkspaceToolConfigTests::test_builder_with_workspace_tools` |
| `teaagent/workspace_tools/_git.py` | Workspace Team | Host `git` integration is safer to test with temp repos and mocks than global coverage pressure. | Medium: argument mistakes can affect commit, stash, and recovery workflows. | Phase 1: expand mocked git harness and temp-repo lifecycle tests. | `tests/test_git_tools.py`, `tests/test_lore_commit_formatter.py` |
| `teaagent/workspace_tools/_config.py` | Workspace Team | Workspace defaults and ignore matching are configuration helpers used through higher-level tools. | Low: config parsing errors are bounded to workspace-tool setup. | Phase 1: add TOML parser coverage and invalid config fixtures. | `tests/test_workspace_defaults_toml.py`, `tests/test_tool_dependency_injection.py` |
| `teaagent/browser_tools.py` | Workspace Team | Optional browser automation tools rely on Playwright-like drivers and read-only tool registration. | Medium: browser driver mismatch or mutating action exposure can violate operator expectations. | Phase 1: add Playwright headless tests when optional extra is available. | `tests/test_browser_tools.py`, `tests/acceptance/test_browser_tools_integration_flow.py` |
| `teaagent/cli/_handlers/_cost.py` | Core CLI Team | Legacy standalone cost command is superseded by chat/TUI controller-backed cost reporting. | Low: main risk is stale UX or duplicate cost truth. | Phase 0: deprecate, delete, or add direct handler smoke before release. | `tests/acceptance/test_cost_tracking_flow.py`, `tests/test_cli_ergonomics_handlers.py` |
| `teaagent/cli/_handlers/_control_plane.py` | Platform Team | Control-plane CLI starts long-lived HTTP/SSE surfaces and tenant registries. | Medium: argument mapping or bind/auth mistakes can expose local control surfaces. | Phase 2: add direct command handler smoke with mocked server lifecycle. | `tests/test_phase6_control_plane.py`, `tests/test_phase6_remaining_features.py` |

## Re-Entry Rules

- New omit patterns require a same-commit ledger row and a linked smoke-test
  candidate.
- Security-sensitive omit patterns (`tls_server`, `wasm_runtime`,
  `wasm_skill`, browser tools, approval/control-plane surfaces) require a
  central risk or roadmap link when their risk is High or Critical.
- Removing an omit pattern is allowed only when the relevant tests run under
  the normal coverage command, not only in a hand-run optional environment.
- Legacy surfaces should be deleted or deprecated before adding more indirect
  tests around them.
