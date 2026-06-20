# Scope Field Taxonomy for `tool_call_approved` Events

> **Status:** Canonical reference
> **Applies to:** Audit events of type `tool_call_approved`
> **Related ADRs:** ADR-0039 (audit-event schema split)

## Purpose

The `scope` field on `tool_call_approved` audit events records **what boundary the
approval was granted within**. This determines blast radius, revocation semantics, and
how downstream consumers (compliance dashboards, replay tools, governance reviews)
interpret the approval.

## Taxonomy

| Scope value | Meaning | Granted by | Blast radius | Revocation |
|-------------|---------|------------|--------------|------------|
| `call_id` | Approval bound to one exact tool call identifier. **Preapproval via `--approve-call-id` was removed (G-P2-2)** — call ids are predictable, so they are weaker authority than a payload digest; use `payload_digest`. The `call_id` scope remains valid only for JIT/session approvals that authorize a single in-flight call. | JIT prompt for a single call (no longer the `--approve-call-id` flag, which is deprecated and ignored). | Single tool invocation only. | Automatic — expires after the call executes or the run ends. |
| `payload_digest` | Approval bound to a canonical SHA-256 digest of the tool name + arguments. | `--approve-scoped TOOL:SHA256` CLI flag. | Any tool call whose computed digest matches. | Manual — remove the digest from the approval set or revoke the grant. |
| `session` | Approval granted for the duration of the current session/run. | TUI approval panel, CLI session-grant, or `--allow-destructive`. | All calls to the approved tool (or tool category) within the session. | Session end, explicit revoke, or process exit. |
| `preset` | Approval pre-configured via a named preset profile (planned). | Workspace or tenant-level preset configuration. | All calls matching the preset's tool + argument constraints. | Preset removal or config update. |

## Usage in audit events

Each `tool_call_approved` event MUST include exactly one `scope` value:

```json
{
  "event": "tool_call_approved",
  "run_id": "<run_id>",
  "call_id": "<call_id>",
  "tool_name": "<tool_name>",
  "authority_type": "preapproved_call_id | preapproved_payload_digest | jit_prompt | session_grant",
  "approved_by": "cli --approve-call-id | cli --approve-scoped | user | session",
  "scope": "call_id | payload_digest | session | preset",
  "auto_approved": true
}
```

## Current implementation status

| Scope | Implemented | Source locations |
|-------|-------------|------------------|
| `call_id` | Preapproval removed (G-P2-2) | `--approve-call-id` is deprecated/ignored; `call_id` scope now only via JIT/session grants. Use `payload_digest`. |
| `payload_digest` | Yes | `teaagent/runner/_core.py` — `--approve-scoped` path |
| `session` | Yes | `teaagent/tui/core.py`, `teaagent/cli/_handlers/_agent/approval.py`, `teaagent/cli/_handlers/agent_helpers.py` |
| `preset` | Planned | Not yet implemented; reserved for future preset-based approval profiles |

## Governance notes

- **Least-privilege default:** Consumers should prefer `call_id` or `payload_digest`
  over `session` whenever the use case allows. `session` grants have wider blast radius
  and should be treated as elevated.
- **Audit review:** Compliance dashboards should group approvals by `scope` to surface
  sessions with excessive `session`-scope grants.
- **Replay fidelity:** Replay tools must respect the original `scope` — a `call_id`
  approval must not be replayed as a `session` approval.
- **`preset` forward-compatibility:** The `preset` value is reserved. Implementations
  must not emit it until the preset profile system is built and its semantics are
  documented in an ADR.
