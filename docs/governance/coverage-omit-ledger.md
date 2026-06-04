# Coverage Omit Ledger

This document maintains the governance ledger for all files and directories omitted from test coverage reporting in `pyproject.toml` under `[tool.coverage.run].omit`.

## Ledger

| Omit Pattern | Owner | Reason | Risk | Expected Return Milestone |
|---|---|---|---|---|
| `teaagent/tui/*` | Platform UX Team | Stateful terminal user interface containing rendering and curses-based event loops. Hard to run in standard headless coverage runs. | Medium (UI/UX regressions in interactive cockpit) | Phase 1 (Automated Headless TUI smoke assertions) |
| `teaagent/tournament/*` | Swarm Consensus Team | Swarm tournament mechanics. Part of federated multi-agent consensus system which is currently in Beta. | Low (Non-critical optional multi-agent paths) | Phase 2 (Swarm production release) |
| `teaagent/validation/*` | Governance Team | Schema and constraint validation rules. Consists of static definition files and rule schemas. | Low (Static rule errors, easily caught by build-time linters) | Phase 1 (Add rule parsing validation tests) |
| `teaagent/workflow_engine.py` | Subagents Team | Background workflow graph executor. Manages multi-step asynchronous subagent graphs. | Medium (State machine or locking bugs in complex workflows) | Phase 1 (Integrate headless workflow tests) |
| `teaagent/vote_relay.py` | Swarm Consensus Team | Peer-to-peer voting and attestation relays. Requires active multi-node transport setup. | Low (Non-critical swarm consensus feature) | Phase 2 (Consensus transport mocks) |
| `teaagent/tls_server.py` | Security Team | Dynamic TLS listener for local subagent and runner control loops. | High (Flaws in connection security or cert handshake) | Phase 1 (Encrypted local subagent e2e test tunnel) |
| `teaagent/webhook_sink.py` | Platform Team | External telemetry and event webhook integration. | Low (Simple HTTP client post calls) | Phase 2 (Telemetry mock validation) |
| `teaagent/wasm_runtime.py` | Sandbox Team | Optional WASM engine using the optional `wasmer` dependency. Checked conditionally at runtime. | Medium (Errors in WASM code execution or memory isolation) | Phase 1 (Conditional WASM engine integration tests) |
| `teaagent/wasm_skill.py` | Sandbox Team | Skill loader and compiler logic for executing WASM-packaged tools. | Medium (Errors in package signature verification) | Phase 1 (WASM compilation mock suite) |
| `teaagent/tsb_format.py` | Governance Team | Tool signing bundle structure and serialization logic. | Low (Format parsing differences) | Phase 1 (Add serialization unit coverage) |
| `teaagent/workspace_tools/builder.py` | Workspace Team | Utility wrapping shell compilations and local setup helpers. | Low (Local setup wrapper errors) | Phase 1 (Local tool setup smoke tests) |
| `teaagent/workspace_tools/_git.py` | Workspace Team | Integration wrapper calling host `git` executable. Substituted with git mocks in standard runner tests. | Low (Git command argument mismatch) | Phase 1 (Mocked Git harness tests) |
| `teaagent/workspace_tools/_config.py` | Workspace Team | Workspace defaults config parsing helpers. | Low (Parser errors for custom workspace TOML) | Phase 1 (TOML parser coverage) |
| `teaagent/browser_tools.py` | Workspace Team | Dynamic browser automation tools using the optional `playwright` package. | Medium (Bypasses or browser driver mismatch) | Phase 1 (Playwright headless tests integration) |
| `teaagent/cli/_handlers/_cost.py` | Core CLI Team | Legacy CLI command handler for standalone cost commands. Superseded by `ChatSessionController` cost reporting. | Low (Stale command interface) | Phase 0 (Deprecate or delete in favor of chat/tui unified cost commands) |
| `teaagent/cli/_handlers/_control_plane.py` | Platform Team | Swarm control plane commands. Interacts with remote nodes. | Medium (Arguments mapping errors) | Phase 2 (Control plane command mock verification) |
