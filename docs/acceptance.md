# Acceptance Coverage

TeaAgent acceptance tests live under `tests/acceptance/` and verify user-facing workflows rather than isolated primitives.

## Covered

- Daily CLI read-only workflow: `agent preflight`, `agent run`, `agent show`, audit persistence, and run-level audit summary.
- CLI prompt approval workflow: destructive call pauses, `agent resume` auto-approves the pending call id, writes the file, and reports audit summary.
- Daily TUI workflow: chat mode, memory injection, progress streaming, agent answer persistence in session history.
- TUI prompt approval workflow: approval prompt, destructive write, final run payload, and audit summary.

## Next User Stories

- Live provider conformance gated by environment variables.
- MCP client compatibility flow with auth, session lifecycle, `tools/list`, and `tools/call`.
- A2A federation flow with remote discovery, capability routing, delegation, failure fallback, and audit correlation.
- Managed runtime flow that forwards task context/tools and records managed runtime audit events.
- Long-running worker flow covering `ultrawork start`, heartbeat/status, logs, and stop.
- Workspace edit flow covering hash reads, patch application, git status, test execution, and final diff summary.
