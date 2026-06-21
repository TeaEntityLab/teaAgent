# Approval Package — Inspection: Purpose, Dependencies, Exports, Call Graph

## Purpose

The `teaagent.approval` package provides a unified, multi-layered system for deciding whether an agent tool call is permitted to execute. It coordinates:

- **Permission mode enforcement** — enforces global modes (read-only, workspace-write, prompt, allow, danger-full-access)
- **JIT (just-in-time) approval** — interactive TTY prompting for one-time or session-wide approvals
- **Preset grant management** — durable grants stored in `.teaagent/approvals.json`
- **Scoped approval records** — per-run, per-call approvals enabling safe run resumption
- **Multi-signature quorum** — federated peer approval for high-risk operations
- **Approval UI (DiffApprovalHandler)** — interactive HITL handler with unified diff preview

---

## Source Files

| File | Role |
|------|------|
| `teaagent/approval/manager.py` | `ApprovalManager` (unified), `PermissionModeEnforcer`, `JITApprovalManager`, `MultiSigQuorumManager`, `ApprovalStoreManager`, `JITApprovalState`, `PermissionMode` enum |
| `teaagent/approval/ui.py` | `DiffApprovalHandler` — interactive approval UI with unified diff preview |
| `teaagent/ergonomics/_approval_grants.py` | `ApprovalGrant`, `ScopedApprovalRecord`, grant helpers, digest computation |
| `teaagent/ergonomics/_approval_persistence.py` | `ApprovalPersistence` — JSON file I/O, file permission enforcement, security health checks |
| `teaagent/ergonomics/_approval_state.py` | `ApprovalPresetStore` — the main store API (delegates persistence to `ApprovalPersistence`) |
| `teaagent/ergonomics/approval_store.py` | Thin re-export of `ApprovalPresetStore` |

---

## Exported Symbols

### `teaagent/approval/manager.py`

```python
__all__ = [
    'ApprovalManager',
    'ApprovalRequest',
    'ApprovalStoreManager',
    'JITApprovalManager',
    'JITApprovalState',
    'MultiSigQuorumConfig',
    'MultiSigQuorumManager',
    'PeerSignature',
    'PermissionMode',
    'PermissionModeEnforcer',
    '_verify_ssh_signature',
    'format_denial_message',
]
```

### `teaagent/ergonomics/approval_store.py`

```python
__all__ = ['ApprovalPresetStore']
```

### `teaagent/ergonomics/_approval_grants.py`

```python
__all__ = [
    'APPROVAL_TTL_HOURS', 'POLICY_ORDER', 'SESSION_TTL_HOURS',
    'ApprovalDecision', 'ApprovalGrant', 'GrantScope', 'ScopedApprovalRecord',
    '_command_matches', '_compute_argument_digest', '_compute_expires_at',
    '_grant_expired', '_new_grant_id', '_new_record_id', '_parse_grant',
    '_path_matches', '_stable_grant_id',
]
```

---

## External Dependencies

### `approval/manager.py`

| Module | Symbols |
|--------|---------|
| `teaagent.errors` | `DenialReasonCode`, `ToolPermissionError` |
| `teaagent.read_only_gate` | `read_only_runtime_block_reason` |
| `teaagent.ergonomics.approval_store` | `ApprovalPresetStore` (TYPE_CHECKING only) |
| `teaagent.policy` | `ApprovalPolicy` (imported lazily in `MultiSigQuorumManager.is_high_risk`) |
| `teaagent.federated_sync` | `ApprovalRequestMessage`, `FederatedGraphSync` (optional, lazy import) |
| `teaagent.security_env` | `allow_dev_signatures` (lazy import) |
| `teaagent.ssh_signatures` | `is_ssh_signature_blob`, `verify_message_ssh` (lazy import) |
| `teaagent.async_bridge` | `run_coroutine_sync` (lazy import) |

### `approval/ui.py`

| Module | Symbols |
|--------|---------|
| `teaagent.runner` | `ApprovalRequest` |
| `difflib` | `unified_diff` |

### `ergonomics/_approval_persistence.py`

| Module | Symbols |
|--------|---------|
| `teaagent.ergonomics._approval_grants` | `_stable_grant_id` |
| `teaagent.storage` | `file_lock` |

### `ergonomics/_approval_state.py`

| Module | Symbols |
|--------|---------|
| `teaagent.ergonomics._approval_grants` | All helpers |
| `teaagent.ergonomics._approval_persistence` | `ApprovalPersistence` |
| `teaagent.storage` | `file_lock` |

---

## Class Relationships

```
ApprovalManager (approval/manager.py)
├── has-a PermissionModeEnforcer
│         └── permission_mode: PermissionMode
│         └── allow_all_destructive: bool
├── has-a JITApprovalManager
│         └── jit_state: JITApprovalState
│         └── enable_jit_prompt: bool
├── has-a MultiSigQuorumManager
│         └── config: MultiSigQuorumConfig
│         └── _executor: ThreadPoolExecutor
│         └── uses: FederatedGraphSync (optional)
└── has-a ApprovalStoreManager
          └── approval_store: ApprovalPresetStore | None
          └── approval_origin_run_id: str | None

ApprovalPresetStore (ergonomics/_approval_state.py)
└── has-a ApprovalPersistence (_approval_persistence.py)
          └── root: Path
          └── path: Path (.teaagent/approvals.json)
          └── readonly: bool

DiffApprovalHandler (approval/ui.py)
└── implements ApprovalHandler protocol
└── workspace_root: Path
```

---

## Call Graph

### `ApprovalManager.assert_allowed()`

```
assert_allowed(tool_name, call_id, destructive, arguments, ...)
├── PermissionModeEnforcer.check()
│   └── read_only_runtime_block_reason()    [on READ_ONLY mode]
│   └── plan_contract.allows_file_write()   [on WORKSPACE_WRITE mode]
├── JITApprovalManager.is_approved()
│   └── jit_state.is_tool_session_approved()
│   └── jit_state.is_call_approved()
├── ApprovalStoreManager.check_preset()
│   └── approval_store.is_allowed()
│       └── _resolve_decision()
│           └── _active_grants_for()
│           └── _grant_matches()
│               └── _grant_expired()
│               └── _path_matches()
│               └── _command_matches()
├── ApprovalStoreManager.check_scoped()
│   └── approval_store.try_consume_scoped_approval()
│       └── _compute_argument_digest() [v1 + v2]
│       └── file_lock(path)
├── ApprovalStoreManager.handle_preapproved()
│   └── approval_store.check_scoped_approval()
│   └── approval_store.add_scoped_approval()
│   └── approval_store.try_consume_scoped_approval()
├── MultiSigQuorumManager.is_high_risk()
│   └── ApprovalPolicy._normalize_shell_arg()   [lazy import]
├── MultiSigQuorumManager.check_quorum()
│   └── _generate_approval_hash()
│   └── _collect_peer_signatures()
│       └── FederatedGraphSync.broadcast_approval_request()
│       └── _run_async_signature_collection()
│           └── sync.collect_approval_signatures()
│       └── _verify_ssh_signature()
│           └── verify_message_ssh()             [ssh_signatures]
└── JITApprovalManager.prompt_and_resolve()
    └── _prompt()
    └── jit_state.approve_once() or approve_session()
```

### `DiffApprovalHandler.__call__()`

```
__call__(request)
├── _show_preview(request)
│   ├── _show_write_diff()     [workspace_write_file]
│   │   └── difflib.unified_diff()
│   ├── _show_patch()          [workspace_apply_patch]
│   ├── _show_edit_diff()      [workspace_edit_at_hash]
│   │   └── difflib.unified_diff()
│   └── _show_arg_summary()    [other tools]
├── input(prompt)              [up to max_prompts times]
└── _explain(request)          [if 'e' entered]
```

### `ApprovalPresetStore.grant()`

```
grant(tool_name, scope, permission_mode, path_globs, command_prefixes, ttl_hours)
├── _migrate_missing_grant_ids()
│   └── _persist._load()
│   └── _stable_grant_id()     [for grants missing grant_id]
│   └── _persist._save()
├── _compute_expires_at()
├── file_lock(path)
└── _persist._save()
```

### `ApprovalPresetStore.is_allowed()`

```
is_allowed(tool_name, permission_mode, arguments)
├── _resolve_decision()
│   └── _active_grants_for()
│   └── _grant_matches()       [for each active grant]
├── [if decision == 'allow' and scope == 'once']
│   └── file_lock(path)
│   └── _remove_grant(matched.grant_id)
│   └── _persist._save()
└── return True/False
```
