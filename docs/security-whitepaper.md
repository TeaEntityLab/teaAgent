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

---

## NIST AI Agent Standards Initiative Mapping

This section maps TeaAgent controls to the NIST AI Agent Standards
taxonomy.  Every control is linked to its code path so that an evaluator
can verify the claim directly.

### Identity — Who is the agent acting as?

| TeaAgent control | NIST concept | Code path |
|---|---|---|
| Permission modes (read-only, workspace-write, prompt, allow, danger-full-access) | `Identity / agent persona` — the agent assumes a declared role with bounded capabilities. | `teaagent/policy.py` → `ApprovalPolicy` & `PermissionMode` enum; `teaagent/approval_manager.py` → `PermissionModeEnforcer.check()` |
| Provider key configuration per workspace | `Identity / principal credential` — each workspace binds a provider identity. | `teaagent/cli/_misc_parsers.py` → `_add_workspace_bootstrap_args()`; `.teaagent/config.json` / `.teaagent/env` |

### Authorization — What is the agent allowed to do?

| TeaAgent control | NIST concept | Code path |
|---|---|---|
| `ApprovalPolicy.assert_allowed()` — unified gate before every destructive tool call | `Authorization / policy enforcement point` — single decision point for all tool-gated writes. | `teaagent/approval_manager.py` → `ApprovalManager.assert_allowed()` |
| Multi-sig quorum for high-risk operations | `Authorization / multi-party consent` — requires N-of-M peer signatures for sensitive tools. | `teaagent/approval_manager.py` → `MultiSigQuorumManager.check_quorum()`; `teaagent/policy.py` → `_check_multi_sig_quorum()` |
| Scoped approval (consume-once call-ID tokens) | `Authorization / just-in-time access` — temporary, single-use grant tied to exact tool+arguments. | `teaagent/approval_manager.py` → `ApprovalStoreManager.check_scoped()`; `teaagent/ergonomics/approval_store.py` |
| File policy (path allow/deny rules) | `Authorization / resource-level policy` — fine-grained path-level access control. | `teaagent/file_policy.py` → `FilePolicy.assert_allowed()` |
| Plan-before-write enforcement | `Authorization / intent attestation` — writes require a prior plan artifact. | `teaagent/runner/_plan_validator.py` → `PlanValidator.validate_write_allowed()` |

### Security — How is the agent's activity monitored and contained?

| TeaAgent control | NIST concept | Code path |
|---|---|---|
| Hash-chained JSONL audit log | `Security / tamper-evident logging` — append-only event stream with cryptographic chain integrity. | `teaagent/audit.py` → `AuditLogger.record()` & `verify_chain_integrity()`; `teaagent/audit_chain.py` |
| Tiered audit levels (L0-L3) | `Security / data minimization` — configurable logging depth from metrics-only to full trace. | `teaagent/audit.py` → `_apply_audit_level()`; `AuditLevel` type |
| Sensitive data redaction in audit payloads | `Security / privacy-preserving logging` — secrets, tokens, and credentials are auto-redacted. | `teaagent/audit.py` → `redact_audit_payload()`, `SENSITIVE_STRING_PATTERNS` |
| Git sandbox isolation | `Security / execution isolation` — destructive runs occur in isolated git branches with rollback. | `teaagent/git_sandbox.py`; `teaagent/runner/_core.py` → git sandbox integration |
| Resource budgets (iterations, tool calls, cost) | `Security / resource exhaustion prevention` — hard caps prevent runaway agents. | `teaagent/budget.py` → `RunBudget`; `teaagent/runner/_core.py` → `_assert_cost_budget()` |
| Context compaction | `Security / context integrity` — prevents token-window overflow and context corruption. | `teaagent/context.py` → `ContextCompactor`; `teaagent/runner/_core.py` → compaction in run loop |
| Heartbeat monitoring | `Security / liveness detection` — background audit events detect hung runs. | `teaagent/heartbeat.py`; `teaagent/runner/_core.py` → heartbeat integration |
| Undo journal + git rollback | `Security / reversibility` — every write can be rolled back via undo journal or git sandbox. | `teaagent/cli/_handlers/_agent.py` → `agent_undo_command`; workspace tool undo logic |

### Governance — Who watches the watchers?

| TeaAgent control | NIST concept | Code path |
|---|---|---|
| Audit export (compliance bundle) | `Governance / evidentiary package` — signed, verifiable export of a run's audit trail. | `teaagent/audit_export.py` → `export_compliance_bundle()` |
| Multi-sig quorum auditing | `Governance / consensus verification` — peer signatures are recorded and verifiable. | `teaagent/approval_manager.py` → `MultiSigQuorumManager._collect_peer_signatures()` |
| SSH/GPG attestation of audit chain | `Governance / cryptographic attestation` — audit logs can be externally signed. | `teaagent/cli/_handlers/_audit.py` → `audit_verify_command()` |
| Permission explain mode | `Governance / transparency` — every denial produces a structured explanation with remediation paths. | `teaagent/approval_manager.py` → `ToolPermissionError` with `reason_code`; `teaagent/cli/_handlers/_approval.py` → `approval_explain_command()` |

### Operational Recommendations (NIST-aligned)

- **Least privilege**: Default to `read-only`; escalate to `workspace-write` or
  `prompt` only when writes are required.
- **Audit everything**: Use L2 (redacted) as the minimum audit level for
  production runs; L3 (full trace) for debugging; L0 (metrics-only) for
  high-throughput automation.
- **Verify chain integrity**: Run `teaagent audit verify` periodically;
  sign attestations with `--signature` for compliance evidence.
- **Isolate destructive runs**: Enable git sandbox branches and
  plan-before-write for any workflow that can mutate the workspace.
- **Multi-sig for high-risk**: Enable multi-signature quorum for production
  deployments, database migrations, and credential rotations.

