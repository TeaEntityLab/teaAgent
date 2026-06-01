# MCP Trust Onboarding Journey
# 2026-06-01

**Fills:** Gap **F-ECO-008** — *"define an MCP trust onboarding journey and add
remote-MCP acceptance tests for unknown tools, expired tokens, revoked trust, and
authorization-required resources."* MCP is an ecosystem trust boundary; the May-31
review rates this **High**.

**Grounding (current state, verified).**
- **`teaagent/mcp_trust.py`** (203 lines): `MCPServerTrust{allowed_tools[],
  denied_tools[], trusted: bool}` and `MCPTrustPolicy{version, allowed_tools[],
  denied_tools[], servers{name→MCPServerTrust}}`. Policy is **Fernet-encrypted** on disk
  (`_get_trust_policy_fernet`, `trust_policy_path`). `apply_mcp_trust_hooks(registry,
  root)` wires the policy into the `ToolRegistry`; `update_server_tools` /
  `update_global_tools` mutate filters; `merged_tool_filters` combines global + server.
- **`teaagent/mcp_client.py`** (219), **`teaagent/stateless_mcp.py`** (58),
  **`teaagent/oauth21/`**, **`mcp_http/_oauth.py`** — client + OAuth pieces exist.
- ADR `docs/adr/0005-mcp-streamable-http.md`, `0004-oauth-dpop.md` document the design.

**What exists:** per-server + global allow/deny tool filters, a `trusted` flag,
encrypted persistence, registry integration.
**What's missing (the journey):** there is no *operator flow* for first-contact trust
review, token-expiry handling in the trust layer, an explicit **revoke** action, or an
"unknown tool ⇒ prompt for review" gate. Trust is a **data model without a journey**.

---

## The journey (setup → review → scope → use → audit → revoke → recover)

| Step | Operator action | Backed by | Gap to close |
|------|-----------------|-----------|--------------|
| **discover** | `teaagent mcp add <url>` | `mcp_client` | list advertised tools without trusting them |
| **review** | show each tool + server `trusted=false` by default | `MCPServerTrust` | **unknown tools must default-deny and prompt** |
| **authorize** | OAuth/bearer setup for restricted resources | `oauth21`, `mcp_http/_oauth` | wire token lifecycle into trust state |
| **scope** | `allowed_tools` / `denied_tools` per server | `update_server_tools` | scoped-grant UX (per-tool, not all-or-nothing) |
| **use** | tool calls filtered via `merged_tool_filters` | `apply_mcp_trust_hooks` | (works) |
| **audit** | every trust change + remote tool call audited | audit chain | **surface trust-change events in audit viewer** |
| **expire** | token expiry ⇒ tool auto-disabled | — | **not implemented — add expiry → re-auth prompt** |
| **revoke** | `teaagent mcp revoke <server>` | `update_server_tools` (set untrusted) | **add explicit revoke verb + audit** |
| **recover** | revoked/expired server fails closed, not open | trust default | **assert fail-closed on trust loss** |

---

## Behavioral requirements (trust must fail safe)

1. **Default-deny for unknown servers/tools.** A newly added server is `trusted=false`
   and its tools are not callable until explicitly scoped. (Today the data model
   supports this; the journey must enforce the default.)
2. **Token expiry disables, never silently downgrades.** On expiry, the server's tools
   fail closed with a re-auth prompt — never fall back to an unauthenticated call.
3. **Revoke is one verb and is audited.** `revoke` sets `trusted=false` + clears
   `allowed_tools`, writes an audit event, and takes effect on the next tool resolution.
4. **Authorization-required resources** (MCP spec) are gated by the OAuth layer before
   the tool is offered, not after it errors.
5. **Remote ≠ local trust.** A remote MCP tool, even if allowed, is subject to the same
   permission mode (PMR) as any destructive tool — trust governs *availability*,
   permission mode governs *execution gating*.

---

## Acceptance (the four cases F-ECO-008 names + two more)

- `test_mcp_unknown_tool_default_deny`: a tool from an untrusted server is not callable.
- `test_mcp_expired_token_fails_closed`: expired token ⇒ tool disabled + re-auth prompt,
  no unauthenticated call.
- `test_mcp_revoke_takes_effect`: after `revoke`, the server's tools are unavailable and
  an audit event is written.
- `test_mcp_authorization_required_resource`: a resource needing auth is not offered
  until the OAuth flow completes.
- `test_mcp_trust_change_audited`: `update_server_tools`/`revoke` emit audit events.
- `test_mcp_remote_tool_honors_permission_mode`: an allowed remote destructive tool still
  prompts in `prompt` mode.

## Open decisions

- **DQ-MCP-1:** Should first-contact with an unknown server be interactive (prompt the
  operator to review tools now) or deferred (added untrusted, reviewed later)?
  Recommendation: interactive in TUI/CLI, deferred-untrusted for automation/background.
- **DQ-MCP-2:** Where does token expiry state live — in `MCPTrustPolicy` or the OAuth
  store? Recommendation: OAuth store owns tokens; trust layer reads expiry.

## Non-goals

- Not a general OAuth provider; teaagent is a *client/consumer* of MCP authorization.
- Not auto-trust by reputation/registry — trust is explicit and operator-driven.

## Cross-references

- Permission gating: `permission-mode-risk-decision-table-2026-06-01.md` (MCP row ⚠).
- Surface auth: `ide-desktop-surface-plan-2026-06-01.md` (Tier-2 attach).
- ADRs: `docs/adr/0004-oauth-dpop.md`, `docs/adr/0005-mcp-streamable-http.md`.
</content>
