# TeaAgent Security Whitepaper (Draft)
_Last updated: 2026-05-31_

This document describes TeaAgent’s security posture for enterprise evaluation.
It is intentionally concrete: every control should map to a code path, an
acceptance test, or an explicit limitation.

## Executive summary

TeaAgent is a governance-first agent harness designed to make AI-assisted
changes:
- **inspectable** (what happened),
- **auditable** (why it was allowed/denied),
- **bounded** (budgets, iterations, tool-call limits),
- **undoable** (git sandbox rollback or undo journal).

TeaAgent’s core value proposition is reducing “invisible agent action” risk by
making tool execution explicit and policy-gated.

## Control catalog

### Permission modes

TeaAgent enforces permission modes before tool execution:
- `read-only`: blocks all destructive tools.
- `workspace-write`: allows file writes, blocks shell mutation.
- `prompt`: requires explicit approval for destructive actions.
- `allow`: allows destructive tools for the session.
- `danger-full-access`: full access for trusted automation only.

### Audit trail

Every run writes an append-only JSONL event log under:
- `.teaagent/runs/<run_id>.jsonl`

Events include run lifecycle, tool call start/completion, denials, and failures.
The audit log is **hash-chained** to make tampering detectable.

### Undo / rollback

TeaAgent supports two rollback mechanisms:
1. **Git sandbox rollback** when running in a sandbox branch.
2. **Undo journal** snapshots for path-based workspace write tools:
   - `teaagent agent undo --last`
   - `teaagent agent undo <run_id>`

### Plan-before-write (verification safety)

Workspace writes can be gated behind an explicit plan artifact, preventing
“free-form” destructive edits without operator intent.

### Cost controls

Runs are bounded by:
- maximum iterations,
- maximum tool calls,
- maximum estimated cost (budget cap).

The runner emits budget threshold warnings and can prompt at 90% of the cap in
interactive sessions.

## Data handling

### What leaves the machine

TeaAgent sends:
- the user task text,
- selected context (workspace reads, optional memory snippets),
- tool observations (as configured / required by the run loop),
to the configured model provider.

TeaAgent does **not** automatically upload the repository; it calls explicit
workspace tools for reads and includes only the read results in context.

### Local storage

TeaAgent stores:
- run audit logs under `.teaagent/runs/`,
- undo journals under `.teaagent/undo/` (when writes occurred),
- optional memory artifacts under `.teaagent/` (feature-dependent).

## Trust boundaries

### Tools and plugins

All tool execution flows through a single registry and policy layer.
Plugins and skills are treated as supply-chain inputs; strict profiles are
recommended for CI/release.

### Remote MCP servers

Remote tools are higher-risk than local file tools. TeaAgent includes policy
hooks for MCP trust, but operators should treat remote MCP as untrusted until
explicitly reviewed and scoped.

## Known limitations / honest gaps

- Audit payload encryption at rest is not a default guarantee; treat local audit
  logs as sensitive files.
- Provider-side data retention and logging is determined by the configured model
  provider and its account settings.
- Multi-tenant / hosted deployments require an explicit threat-model review
  beyond local CLI usage.

## Operational recommendations

- Prefer `read-only` for planning and exploration.
- Prefer git sandbox branches for any write-capable sessions.
- Enforce plan-before-write in CI and release profiles.
- Treat `.teaagent/` as sensitive operational metadata; protect with OS-level
  permissions and repository policy.

