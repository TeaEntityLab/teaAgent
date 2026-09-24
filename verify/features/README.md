# Feature map index

Each feature file starts with YAML front matter read by `verify/checks/*.sh`:

| Key | Meaning |
|---|---|
| `feature` | file stem |
| `source_commit` | product commit the file was last verified against |
| `last_verified_at` | UTC date of that verification |
| `verification_status` | `passed` · `failed` (requires `known_findings`) · `unverified` |
| `known_findings` | open finding ids below that this feature exposes |
| `covers` | product paths whose change makes the file stale |
| `drive` | list of `{id, expect, run}`; `run` is bash executed in a fresh scratch workspace after `source verify/checks/lib.sh; enter_scratch` |

| Feature | Status | Drive items |
|---|---|---|
| [governed-tool-execution](governed-tool-execution.md) | passed | tests, tool-contracts, read-only-blocks-write, prompt-pauses-unapproved-write, scoped-digest-exactness, approve-and-resume, presets-deny-beats-allow, plan-gate |
| [run-lifecycle](run-lifecycle.md) | passed | tests, offline-run-completes, iteration-cap, tool-call-cap, runs-list-and-replay, undo-restores |
| [audit-evidence](audit-evidence.md) | passed | tests, lifecycle-events-recorded, chain-verify-and-tamper, denial-explained |
| [mcp-surface](mcp-surface.md) | failed (F-1) | tests, stdio-protocol, http-auth-and-session |
| [operator-cli](operator-cli.md) | passed | tests, init-non-tty-requires-provider, init-fake, doctor-selftest, read-only-surfaces |

## Known findings (open at `a91f1dc2`)

| Id | Severity | Finding | Oracle | Evidence |
|---|---|---|---|---|
| F-1 | high | `mcp serve` `tools/call` runs destructive tools with no `ApprovalPolicy`, no permission mode, and no audit event (stdio and HTTP). Contradicts `AGENTS.md` Tool Governance + Runtime Safety and `docs/api/mcp-api.md` § Trust Model (which also documents a nonexistent `mcp serve --permission-mode`). Never governed (`git log -S`), so owner decides: gate the server or rewrite the trust-model doc. | A5 (XFAIL) | `teaagent/mcp_server.py` `_call_tool` → `registry.execute(name, arguments)` |
| F-2 | medium | `h4_governance_shadow` audit events store raw tool arguments (`content`, `command`) under `payload.context.arguments`; `redact_audit_payload` only redacts a top-level `arguments` key, so default L2 logs leak what `tool_call_*` events redact. | A6 (XFAIL) | `teaagent/governance/h4_integration.py` `evaluate_approval_policy_shadow`; `teaagent/audit.py` `redact_audit_payload` |
| F-3 | low | `approval approve <call_id> --resume` prints the `--approve-call-id` deprecation notice although the operator never passed that flag. | — | `teaagent/cli/_handlers/_ergonomics/approval.py` passes `approve_call_id=[call_id]` into the resume namespace |
| F-4 | low | `CONTRIBUTING.md` installs `.[dev,oauth,telemetry]`; no `oauth` extra exists in `pyproject.toml`. | — | doc drift |

## Not mapped (no drive coverage here)

TUI (`teaagent tui`), chat REPL, gateway (Telegram/Slack/Discord), cloud/background
runners, consensus/swarm/subagents, OAuth 2.1/DPoP for MCP HTTP, control-plane
server, memory/skills lifecycle, release evidence tooling, VS Code extension,
real LLM providers. Their tests exist under `tests/`; a green sweep says nothing
about them.
