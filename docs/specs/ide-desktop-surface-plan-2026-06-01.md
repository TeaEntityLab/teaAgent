# IDE / Desktop Surface Plan
# 2026-06-01

**Fills:** Gap **F-ECO-004** — *"either package a minimal desktop/client-server workflow
or state that TeaAgent intentionally remains CLI-first with documented attach recipes."*
The May-31 review marks desktop/client-server packaging as *partial*; mainstream agents
increasingly meet users in IDEs and app shells (Codex, OpenCode, Cursor).

**Grounding (current state, verified).**
- **VS Code extension** `vscode/src/extension.ts` (**188 lines**) registers **7
  commands**: `teaagent.agentPreflight`, `teaagent.agentRun`, `teaagent.doctor`,
  `teaagent.graphqliteSmoke`, `teaagent.modelProviders`, `teaagent.openTUI`,
  `teaagent.startMcpServer`. It is a **command launcher**, not an inline agent UX.
- **HTTP surface** `teaagent/mcp_http/` (432 lines) + `_oauth.py` (210) +
  `teaagent/surface_auth.py` (`SurfaceAuthPolicy`, bearer tokens, tenant scoping,
  `is_loopback_host`) — a real client-server foundation exists.
- **`teaagent/managed_runtime.py`** (537 lines) — managed/hosted runtime foundation.
- **No desktop app shell** exists.

---

## Recommendation: CLI-first, with an *honest, tested* IDE/attach contract

teaagent should **not** chase a full IDE rewrite (it would dilute the governance focus —
see NG-2/NG-3). Instead: declare CLI/TUI as the primary surface, and make the IDE a
**thin, governed bridge** with explicit parity guarantees. The HTTP + surface-auth
foundation already supports this.

### Tier 1 — VS Code extension reaches command parity (near-term)

The extension launches the CLI; it should expose the *daily* verbs with parity:

| CLI verb | Extension command | Status | Action |
|----------|-------------------|--------|--------|
| `agent run` | `teaagent.agentRun` | ✓ | keep |
| `preflight` | `teaagent.agentPreflight` | ✓ | keep |
| `doctor` | `teaagent.doctor` | ✓ | keep |
| `daily` | — | ✗ | **add** — show cockpit (see cockpit spec) |
| approvals | — | ✗ | **add** — surface pending approvals in a panel |
| `undo` | — | ✗ | **add** — single governed undo (P2-1) |
| run evidence | — | ✗ | **add** — render `run_evidence.json` (EVB spec) |

**Principle:** the extension must **never bypass** approval/audit. It drives the same
`agent run` path; permission mode is shown and honored (PMR spec), not silently widened.

### Tier 2 — Client-server attach recipe (document what exists)

Write an operator guide for: start `teaagent` HTTP surface (loopback-only by default per
`is_loopback_host`), authenticate with a bearer token (`SurfaceAuthPolicy`), attach from
the IDE/desktop client, inspect runs, approve out-of-band. This is **documentation of
existing capability**, not new code.

### Tier 3 — Desktop app shell (explicit decision, see DQ)

Either (a) ship a minimal Electron/Tauri shell wrapping the TUI + cockpit, or (b)
declare desktop a **documented non-goal** with the Tier-2 attach recipe as the
replacement path. **Recommendation: (b)** until enterprise demand is proven — honesty
beats a half-built app.

---

## Security constraints (must hold on every IDE/desktop path)

- Default loopback-only (`surface_auth.is_loopback_host`); non-loopback requires a token
  and should warn (ties to MCP-trust + PMR specs).
- Tenant scoping (`SurfaceAuthPolicy.can_access_tenant`) enforced when multi-tenant.
- The IDE surface is subject to the **same permission-mode risk table** (PMR) — a task
  started from VS Code in `prompt` mode still prompts; it does not auto-escalate.

## Acceptance

- `test_vscode_command_parity` (manifest-level): every Tier-1 daily verb has a
  registered command; doc-lint asserts the parity table matches `package.json`.
- `test_http_surface_loopback_default`: surface refuses non-loopback without a token.
- `test_ide_run_honors_permission_mode`: a run launched via the HTTP surface in `prompt`
  mode emits an approval request (no silent widening).
- Operator-guide doc exists for the Tier-2 attach recipe.

## Open decisions

- **DQ-IDE-1** (= DQ-1 family): Tier-3 desktop shell — build (a) or document non-goal
  (b)? Recommendation (b).
- **DQ-IDE-2:** Should the extension embed a webview cockpit, or only launch the TUI in a
  terminal panel (`teaagent.openTUI`)? Recommendation: launch TUI first; webview later.

## Non-goals

- Not a Cursor-style inline-completion product. teaagent's value is governed agency, not
  autocomplete.
- Not an IDE fork. The extension stays a thin, parity-tested bridge.

## Cross-references

- Cockpit parity: `operator-cockpit-contract-2026-06-01.md`
- Permission modes per surface: `permission-mode-risk-decision-table-2026-06-01.md`
- Evidence rendering: `run-evidence-bundle-spec-2026-06-01.md`
</content>
