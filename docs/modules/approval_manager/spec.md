# Approval Package — Behavior Specification

## Overview

The `teaagent.approval` package provides all approval-related concerns: permission mode enforcement, JIT (just-in-time) interactive prompting, multi-signature quorum for high-risk operations, preset grant management, scoped (run-resumable) approval records, and the interactive diff-showing HITL UI. It spans two layers: the runtime `ApprovalManager` in `approval/manager.py` and the persistent `ApprovalPresetStore` backed by `approvals.json`.

---

## Behavior Contract

### Guarantees

1. **`assert_allowed()` either returns silently or raises `ToolPermissionError`.**  
   There is no partial approval state — a call either passes all checks or is rejected.

2. **Permission mode is checked first, JIT state is checked second, store presets third.**  
   The evaluation order is: `PermissionModeEnforcer` → JIT session/call approval → store preset → store scoped approval → preapproved call IDs → multi-sig quorum → JIT TTY prompt → raise.

3. **`once`-scoped grants are atomically consumed on first use.**  
   `is_allowed()` removes the grant from the store under a file lock before returning `True`.

4. **`deny` grants take precedence over `allow` grants.**  
   `_resolve_decision()` checks deny grants before allow/session/once grants.

5. **Scoped approvals expire after 24 hours by default (`APPROVAL_TTL_HOURS = 24.0`).**

6. **Session-scoped grants expire after 8 hours (`SESSION_TTL_HOURS = 8.0`).**

7. **All writes to `approvals.json` are done under `file_lock`.** Concurrent processes cannot corrupt the store.

8. **`approvals.json` is fail-closed on read.** A corrupt or malformed file raises `IOError` rather than silently returning an empty state.

9. **File permissions are enforced on the `.teaagent/` directory (mode `0o700`) and all files within it (mode `0o600`).** These are applied on every write.

10. **Multi-sig signatures are cryptographically verified before quorum is counted.**  
    Invalid or unverified signatures are rejected; `allow_dev_signatures` must be explicitly set to accept dev-hash fallback.

### What the module does NOT guarantee

- Preventing replay attacks on v1 (non-HMAC) argument digests — they use a 16-character SHA256 prefix which is not collision-resistant under adversarial conditions.
- That TTY JIT prompts fire in headless/non-TTY environments — `sys.stdin.isatty()` is checked and prompts are silently skipped if not a TTY.
- Thread safety of `JITApprovalState` — `approved_call_ids` and `session_approved_tools` are plain Python sets with no locks.

---

## Invariants

| Invariant | Where enforced |
|-----------|----------------|
| `deny` grants always override `allow` grants | `_resolve_decision()` lines 579-585 |
| `once` grants are removed on consumption | `is_allowed()` line 652-663, under `file_lock` |
| `approvals.json` always has `grants`, `audit`, `approved_call_ids`, `scoped_approvals` keys | `_load()` calls `setdefault()` for all four |
| Expired grants are never matched | `_grant_expired()` called in `_grant_matches()` |
| Expired scoped approvals are never returned | `list_scoped_approvals_for_run()` filters by `expires_at` |
| Workspace secret is exactly 64 hex chars (32 bytes) | `_get_workspace_secret()` validates length and hex encoding |
| HMAC secret is per-workspace, never exposed in digests | Key ID is stored as first 16 hex chars only |

---

## Permission Mode Decision Tree

```
assert_allowed(tool_name, call_id, destructive, arguments, ...)
│
├─ PermissionModeEnforcer.check()
│   ├─ READ_ONLY      → read_only_runtime_block_reason()
│   │   ├─ if blocked: raise ToolPermissionError(READ_ONLY_MODE)
│   │   └─ else: return (allowed)
│   ├─ WORKSPACE_WRITE + destructive
│   │   ├─ write tool in {workspace_write_file, workspace_apply_patch, workspace_edit_at_hash}
│   │   │   └─ plan_contract check → raise ToolPermissionError(PLAN_CONTRACT_DENIED) or allow
│   │   └─ other destructive tool → raise ToolPermissionError(WORKSPACE_WRITE_MODE)
│   ├─ non-destructive → return (allowed)
│   ├─ ALLOW/DANGER_FULL_ACCESS + destructive → return (allowed)
│   └─ PROMPT + destructive → return '__continue__' (fall through to JIT)
│
├─ [if mode_result == '__continue__']
│   ├─ JITApprovalManager.is_approved() → if True: return
│   ├─ ApprovalStoreManager.check_preset() → if True: return
│   ├─ ApprovalStoreManager.check_scoped() → if True: return
│   ├─ ApprovalStoreManager.handle_preapproved() → if True: return
│   ├─ MultiSigQuorumManager (if enabled + high_risk)
│   │   └─ check_quorum() → if True: return
│   ├─ JITApprovalManager.prompt_and_resolve()
│   │   ├─ 'o' → approve_once(call_id) → return
│   │   ├─ 's' → approve_session(tool_name) → return
│   │   ├─ 'd' → raise ToolPermissionError(JIT_USER_DENIED)
│   │   ├─ 'e' → raise ToolPermissionError(JIT_USER_DENIED)
│   │   └─ None (no TTY) → fall through
│   └─ raise ToolPermissionError(MULTISIG_NO_QUORUM or JIT_NO_APPROVAL)
```

---

## JIT Approval State Machine

```
JITApprovalState
  approved_call_ids: set[str]        (one-time approvals by call_id)
  session_approved_tools: set[str]   (session-wide approvals by tool_name)

  Initial state: both sets empty.

  Transitions:
  ─────────────
  approve_once(call_id)       → approved_call_ids.add(call_id)
  approve_session(tool_name)  → session_approved_tools.add(tool_name)

  Query:
  ──────
  is_call_approved(call_id)         → call_id in approved_call_ids
  is_tool_session_approved(tool)    → tool in session_approved_tools

  No expiry, no removal. State is in-memory only. Cleared on process exit.
```

---

## Grant Evaluation State Machine

```
Grant match for a tool call:
  1. Load all grants for tool_name
  2. Filter expired grants (grant.expires_at < now)
  3. Filter permission_mode mismatch
  4. For remaining active grants:
     - Check _path_matches(grant.path_globs, arguments)
     - Check _command_matches(grant.command_prefixes, arguments)
     - Both must match (or both absent = wildcard)

  Decision (priority order):
  - Any matching deny grant  → decision='deny'
  - Any matching once grant  → decision='allow', consume grant
  - Any matching always grant → decision='allow'
  - Any matching session grant → decision='allow'
  - No match                  → decision='prompt'
```

---

## Scoped Approval Lifecycle

```
Created:   add_scoped_approval(run_id, call_id, tool_name, arguments)
           └─ argDigest = HMAC-SHA256(arguments, workspace_secret)
           └─ expires_at = now + 24h
           └─ key_id = first 16 hex of secret

Active:    unconsumed, not expired, key_id matches current secret

Consumed:  try_consume_scoped_approval() → sets consumed_at

Expired:   expires_at < now → skipped in list queries, prunable

Orphaned:  key_id != current secret (workspace secret was rotated)
           → will be blocked on resume, must re-approve
```
