# Acceptance Coverage

TeaAgent acceptance tests live under `tests/acceptance/` and verify user-facing workflows rather than isolated primitives.

## Covered

- Daily CLI read-only workflow: `agent preflight`, `agent run`, `agent show`, audit persistence, and run-level audit summary.
- CLI prompt approval workflow: destructive call pauses, `agent resume` auto-approves the pending call id, writes the file, and reports audit summary.
- Daily TUI workflow: chat mode, memory injection, progress streaming, agent answer persistence in session history.
- TUI prompt approval workflow: approval prompt, destructive write, final run payload, and audit summary.
- MCP client compatibility flow: bearer auth, session lifecycle, `tools/list`, `tools/call`, and session close.
- A2A federation flow: remote discovery, partial endpoint failure, capability routing, delegation, context forwarding, and agent trace metadata.
- Managed runtime flow: tool metadata context construction, workspace/request context forwarding, persisted managed task audit events, and result trace metadata.
- Long-running worker flow: background worker start, list, show, log tail, and stop lifecycle.

## Next User Stories

- Live provider conformance gated by environment variables.
- Workspace edit flow covering hash reads, patch application, git status, test execution, and final diff summary.
