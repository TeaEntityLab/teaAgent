---
type: guide
audience: operator, developer
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# Approval Policy Design

How to design approval policies that match your trust model.

An approval policy answers one question for every tool call:
**"Is this operation authorised, by whom, and under what constraints?"**

**Related docs:**
- [Permission and approval playbook](../permission-and-approval-playbook.md) — operator reference
- [Tool development](tool-development.md) — marking tools as destructive
- [Integration guide § Custom Approval](integration-guide.md#3-creating-a-custom-approval-policy)

---

## Permission Modes

`PermissionMode` is the coarsest control. Set it once per session:

| Mode | What is allowed without additional grants | Typical use |
|------|------------------------------------------|-------------|
| `READ_ONLY` | Only `read_only=True` tools | Exploration, planning, audits |
| `WORKSPACE_WRITE` | All workspace tools; `destructive=True` tools require grant or prompt | Day-to-day coding sessions |
| `PROMPT` | Every destructive call prompts the operator interactively | Default; highest transparency |
| `ALLOW` | All tools allowed without prompting | CI/CD with pre-reviewed toolsets |
| `DANGER_FULL_ACCESS` | No restrictions at all | Emergency recovery only |

```python
from teaagent.approval import PermissionMode
from teaagent.policy import ApprovalPolicy

# Safe default for any new repository
policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
```

---

## Trust Model Layers

Approval is checked in this order. The first match wins:

```
1. READ_ONLY gate          — block all destructive tools immediately
2. Session-approved tools  — tool approved for the full session (approve-session)
3. Call-ID approved        — this exact call was pre-approved by digest
4. Approval store grants   — path-scoped or command-prefix grants from approval grant
5. Multi-sig quorum        — peer signatures from other agents
6. JIT prompt              — interactive TTY prompt (PROMPT mode only)
7. Deny                    — raise ToolPermissionError
```

---

## JIT (Just-In-Time) Approvals

In `PROMPT` mode the operator approves each destructive call at runtime.
`JITApprovalState` tracks what has been approved so far in the session:

```python
from teaagent.approval import JITApprovalState

state = JITApprovalState()

# Approve a single call (one-time)
state.approve_once("call-id-abc123")

# Approve a tool for the rest of the session
state.approve_session("workspace_write_file")

# Check
state.is_call_approved("call-id-abc123")    # True
state.is_tool_session_approved("workspace_write_file")  # True
```

`enable_jit_prompt=True` (default) enables the interactive TTY dialog when
no prior grant covers the call. Set `enable_jit_prompt=False` for headless
runs where you want hard failures instead of interactive prompts.

---

## Scoped Grants (Approval Store)

Grants express "tool X is pre-approved when the path matches glob Y":

```bash
# CLI
teaagent approval grant workspace_write_file --path-glob 'src/**' --root .
teaagent approval grant workspace_run_shell_mutate --command-prefix 'pytest ' --root .
teaagent approval list --root .
teaagent approval revoke <grant_id> --root .
```

```python
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from pathlib import Path

store = ApprovalPresetStore(root=Path("."))
store.grant("workspace_write_file", path_glob="src/**")
store.grant("workspace_run_shell_mutate", command_prefix="pytest ")

# Pass to policy
from teaagent.policy import ApprovalPolicy, PermissionMode

policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    approval_store=store,
)
```

Grants expire after 8 hours by default. Pass `ttl_seconds` to override.

**Good grant patterns:**

| Situation | Grant |
|-----------|-------|
| Editing only generated output | `path_glob='.teaagent/generated/**'` |
| Running tests | `command_prefix='pytest '` |
| Docs-only work | `path_glob='docs/**'` |
| Single file fix | `path_glob='src/auth/tokens.py'` |

**Risky grant patterns (avoid):**

| Pattern | Risk |
|---------|------|
| `path_glob='**'` (root wildcard) | Effectively allows all writes |
| `path_glob=''` (empty) | Rejected by the store |
| `path_glob='~/**'` | Home directory scope |
| Granting `git_push` globally | Permanent remote mutations |

---

## Multi-Sig Quorum

High-stakes operations can require signatures from multiple peer agents before proceeding.
Configure in `.teaagent/config.json`:

```json
{
  "multi_sig": {
    "enabled": true,
    "required_approvals": 2,
    "peer_agent_ids": ["agent-alice", "agent-bob"],
    "peer_public_keys": {
      "agent-alice": "ssh-ed25519 AAAA...",
      "agent-bob":   "ssh-ed25519 AAAA..."
    },
    "peer_relay_urls": {
      "agent-alice": "https://alice.internal/relay",
      "agent-bob":   "https://bob.internal/relay"
    },
    "high_risk_patterns": ["git push", "rm -rf", "DROP TABLE"],
    "timeout_seconds": 300
  }
}
```

Load at runtime:

```python
from teaagent.approval import MultiSigQuorumConfig
from teaagent.policy import ApprovalPolicy, PermissionMode
from pathlib import Path

quorum = MultiSigQuorumConfig.from_workspace_config(Path("."))
policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    multi_sig_config=quorum,
    agent_id="agent-main",
)
```

---

## Hook-Level Permission Guards

For fine-grained per-path or per-argument control that doesn't fit into coarse mode + grants,
add a `PreToolUse` hook:

```python
from teaagent.hooks import (
    HookRegistry, HookPermissionMode, permission_check_hook,
    mcp_tool_filter_hook,
)

hook_reg = HookRegistry()

# Block writes outside src/ and tests/
hook_reg.register_pre_hook(
    permission_check_hook(
        mode=HookPermissionMode.ASK,
        allow_patterns=frozenset({"src/**", "tests/**", "docs/**"}),
        deny_patterns=frozenset({"secrets/**", ".env", "*.pem"}),
    )
)

# Block all MCP tools not on the allowlist
hook_reg.register_pre_hook(
    mcp_tool_filter_hook(
        allowed_tools=frozenset({"mcp_github_list_prs", "mcp_github_get_issue"}),
    )
)
```

`PreToolUse` hooks run before the approval store check. Raise `HookError` to veto;
return `None` to continue with normal approval logic.

---

## Design Patterns

### Pattern 1: Narrow + prompt (safest interactive)

Use for any new repository or unfamiliar codebase:

```python
policy = ApprovalPolicy(
    permission_mode=PermissionMode.PROMPT,
    enable_jit_prompt=True,
)
```

Every destructive call prompts. After a session you can promote frequently-approved calls to grants.

### Pattern 2: Path-scoped write + no prompt (CI automation)

Pre-approve only the paths the agent is allowed to touch:

```python
store = ApprovalPresetStore(root=root)
store.grant("workspace_write_file", path_glob="generated/**")
store.grant("workspace_run_shell_mutate", command_prefix="make build")

policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    approval_store=store,
    enable_jit_prompt=False,   # headless; fail hard on unapproved calls
)
```

### Pattern 3: Read-only exploration

```python
policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
```

All destructive tools blocked at the gate. Use for planning, auditing, or code review runs.

### Pattern 4: High-stakes with multi-sig

For production deployments or release automation:

```python
quorum = MultiSigQuorumConfig(
    enabled=True,
    required_approvals=2,
    peer_agent_ids=["approver-a", "approver-b"],
    high_risk_patterns=["git push origin main", "helm upgrade"],
)
policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    multi_sig_config=quorum,
    enable_jit_prompt=False,
)
```

---

## Checklist

Before shipping a policy configuration:

> **Last codebase audit: 2026-06-04** — Each item cross-referenced against enforcement code.
> Items marked ✅ are enforced in code. Unchecked boxes remain **operator review gates**.

- [x] `permission_mode` matches the minimum required for the task
      ✅ `PermissionModeEnforcer` in `approval/manager.py` enforces all 5 modes.
      Default is `PROMPT` (policy.py:51). Workspace config uses `"prompt"`.
- [x] `path_glob` grants are as narrow as possible (file or directory, not root)
      ✅ `_path_matches()` enforces glob matching. TUI grants use single-file scopes.
      ⚠️ No hard validation rejecting `path_glob='**'` — `approval doctor` warns but does not block.
      Empty `path_globs` returns True (all paths allowed, `_approval_grants.py:209`).
- [x] `enable_jit_prompt=False` in headless CI; `True` for interactive operator sessions
      ✅ Mechanism: `JITApprovalManager.prompt_and_resolve()` checks both the flag and `sys.stdin.isatty()`.
      ⚠️ No automatic CI detection (no `CI`/`GITHUB_ACTIONS` env var check). Pure convention.
- [x] Approval grants are revoked or expire after the task completes
      ✅ TTL: session grants 8h, scoped approvals 24h (`_approval_grants.py:15-16`).
      `_grant_expired()` checked on every access. `revoke()` removes persistently.
- [x] Multi-sig is enabled for any operation that mutates shared infrastructure
      ✅ `MultiSigQuorumManager`, WAN HTTP relay (`signature_relay.py`), P2P broadcast (`federated_sync.py`).
      Opt-in by design (`enabled=False` default). Production-grade WAN transport; file-based experimental.
- [x] Approval records are written to the audit log (`--audit-level L1` minimum)
      ✅ Every approval decision produces audit events: `tool_call_pending_approval`,
      `tool_call_approved`, `tool_call_denied`, `tool_call_blocked`. All audit events always recorded
      (no level filtering on recording — contra the doc reference to `--audit-level L1`).
- [x] `DANGER_FULL_ACCESS` is never committed to config files or CI scripts
      ✅ Not present in `.teaagent/config.json`, `.github/workflows/`, or `scripts/`.
      Present only in source code enum definition, test assertions, documentation,
      and `vscode/package.json` schema enum (listing valid VS Code settings options, not enabling it).

---

## See Also

- [Examples — approval patterns](examples/approval_patterns.py)
- [Permission and approval playbook](../permission-and-approval-playbook.md) — operator-facing detail
- [Run evidence and audit guide](../run-evidence-and-audit-guide.md) — what the audit log captures
