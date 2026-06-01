# subagents — Behavior Contract, Invariants, State Machines

## Purpose

The `subagents` module implements hierarchical agent delegation: a parent agent may spawn child ("subagent") runs with their own workspace isolation, tool whitelists, permission policies, and depth limits. It also handles centralized destructive-tool approval queuing for parallel/tournament scenarios.

---

## Behavior Contract

### Subagent execution (`SubagentManager.run_subagent`)

1. **Depth guard** — A subagent will not be started if `depth >= sub_def.max_depth`. Returns an error dict with `status="error"`.
2. **Isolation preparation** — A valid `IsolationContext` must be created before any child agent is run. If isolation setup fails (git missing, docker unavailable, etc.) the call returns an error dict immediately without launching the child.
3. **Cleanup guarantee** — `iso_ctx.cleanup()` is called in a `finally` block, so worktree/snapshot resources are always freed even if the child run raises.
4. **Tool whitelist inheritance** — The child's `ToolRegistry` is derived from the parent's. Subagent and `subagent_*` tools are stripped; only whitelisted tools (or all tools when no whitelist) are copied.
5. **Cost propagation** — The child's `cost_cents` is recorded to the parent audit log via `sub_audit.record("subagent_lineage", ...)`.
6. **Review artifact** — After a worktree/container run, `capture_subagent_review` produces a `.patch` and `.status` file in `.teaagent/subagent-reviews/`. If the parent root and child root are the same (shared isolation), no review is produced.
7. **Session record** — After a successful child run, a `SubagentSession` is stored in `SubagentManager._sessions` keyed by `sub_result.run_id`.

### Approval queue (`CentralizedApprovalQueue`)

1. **Centralized approval applies only when** `batch_index is not None` OR `parallel_mode=True` AND `parent_run_id` is non-empty (see `should_use_centralized_approval`).
2. **Timeout default** — Requests time out after `timeout_seconds=180` if not actioned.
3. **Persistence** — When a `workspace_root` is provided, queue state is written to `.teaagent/approval_queues/<parent_run_id>.json` on every `submit_request_sync` and `approve/deny` call.
4. **Cross-process reload** — `reload_from_store` merges disk state into in-memory `_requests`, resolving pending futures/events when a status change is detected.
5. **HMAC integrity** — When `TEAAGENT_APPROVAL_HMAC_KEY` is set, all queue files are signed on write and verified on load; a mismatch returns an empty snapshot (does not crash).

---

## Invariants

| Invariant | Location |
|-----------|----------|
| `SubagentDef` and `SubagentSession` are frozen dataclasses — immutable after construction | `_types.py:12,59` |
| `IsolationContext` is frozen — cleanup state cannot be mutated | `_isolation.py:24` |
| `iso_ctx.cleanup()` always runs regardless of child run outcome | `_manager.py:310` |
| A tool named `subagent` or `subagent_*` is never copied to child registry | `_manager.py:325-327` |
| `SubagentApprovalRequest.request_id` is a UUID hex — globally unique | `_approval_queue.py:272-273` |
| `session_key` for isolation paths contains only alphanumeric, dash, underscore characters | `_isolation.py:281-292` |
| The disk queue file is written atomically via `os.replace` (temp → final) | `_approval_queue_store.py:166-170` |
| `prune_stale` never removes a queue file that has pending requests | `_approval_queue_store.py:265-268` |

---

## State Machines

### SubagentApprovalRequest lifecycle

```
         submit_request / submit_request_sync
                    |
                    v
               [PENDING]
              /    |    \
        approve  deny   timeout(180s)
           |      |          |
      [APPROVED] [DENIED] [TIMEOUT]
           |
       cancel (if agent terminated)
           |
       [CANCELLED]
```

Transitions:
- `PENDING → APPROVED` via `approve_request`, `approve_request_sync`, `approve_batch`, `approve_all_pending_sync`, `approve_request_cross_process`
- `PENDING → DENIED` via `deny_request`, `deny_request_sync`, `deny_batch`, `deny_all_pending_sync`, `deny_request_cross_process`
- `PENDING → TIMEOUT` automatically after `timeout_seconds` in `submit_request` / `submit_request_sync`
- `PENDING → CANCELLED` via `cancel_request`

Once a terminal state (`APPROVED`, `DENIED`, `TIMEOUT`, `CANCELLED`) is reached, no further transitions occur. `cleanup()` removes terminal requests from memory.

### IsolationContext cleanup states

```
[created]  →  child agent runs  →  [finished or error]  →  cleanup()
                                                               |
                          ┌────────────────────────────────────┘
                          |
              isolation=worktree: git worktree remove --force + prune
              isolation=directory-snapshot: shutil.rmtree(container_path)
              isolation=docker: docker rm -f <container_id>
              isolation=shared: no-op
```

---

## Key Constants

| Name | Value | Defined in |
|------|-------|-----------|
| `DEFAULT_SUBAGENT_ISOLATION` | `'shared'` | `_types.py:8` |
| `SUPPORTED_SUBAGENT_ISOLATIONS` | `{'shared','worktree','directory-snapshot','docker','auto'}` | `_isolation.py:18-20` |
| `DEPRECATED_ISOLATION_ALIASES` | `{'container': 'directory-snapshot'}` | `_isolation.py:21` |
| `SUBAGENTS_DIR` | `'.teaagent/subagents'` | `_loader.py:11` |
| Default `timeout_seconds` | `180` | `_approval_queue.py:69` |
