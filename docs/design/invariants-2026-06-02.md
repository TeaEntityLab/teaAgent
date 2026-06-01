# TeaAgent Invariants — 2026-06-02

Properties that must hold at all times. Each invariant lists the enforcement point(s)
and what breaks if the invariant is violated.

---

## I-1  Audit Log is Append-Only

**Invariant:** Events are only ever appended to the in-memory list and to the JSONL
file. No event is ever deleted or mutated after creation.

**Enforcement:**
- `AuditEvent` is a `frozen=True` dataclass — immutable after construction.
- `AuditLogger` holds a `threading.Lock`; events appended under lock.
- File writes use `open(path, 'a')` (append mode) only.
- `AuditLogger` exposes no delete or overwrite methods.

**Violation consequence:** Tampered or missing audit events break the hash-chain;
`verify_chain_integrity()` will report errors, and any compliance proof is invalidated.

---

## I-2  Audit Hash Chain Integrity

**Invariant:** Each audit event records the SHA-256 hash of the previous event
(`prev_hash`), forming an unbroken chain from genesis. Any insertion, deletion, or
mutation of a middle event produces a detectable chain break.

**Enforcement:**
- `audit_chain.last_chain_hash(path)` reads the last line's `hash` field under
  `file_lock`.
- The canonical JSON includes `prev_hash` so tampering with either the payload or
  the chain link invalidates the current event's hash.
- HMAC (`compute_chain_hmac`) provides an additional per-run secret layer.

**Verification:** `AuditLogger.verify_chain_integrity()` walks the file and checks
every `prev_hash → hash` link.

---

## I-3  Session Cost is Monotonically Non-Decreasing

**Invariant:** `TeaAgentTUI._session_cost_cents` only ever increases.

**Enforcement:**
- Only `+= result.cost_cents` operations in `_run_agent_task` (line 943).
- `result.cost_cents` is a non-negative `float` in `RunResult` (no negative cost
  reporting path in `AgentRunner.run()`).

**Violation consequence (CG-03 stop-gap context):** Before the fix landed in commit
`31df3ba`, `_session_cost_cents` was never updated, so `/cost` always reported $0.
Any future path that resets the counter to 0 mid-session (e.g., loading from
persistent state) would break this invariant.

---

## I-4  Run-Budget Limits Are Hard

**Invariant:** A run terminates before exceeding `max_iterations`, `max_tool_calls`,
or `max_estimated_cost_cents`.

**Enforcement:**
- `RunBudget.validate()` rejects negative values at construction time.
- `_assert_cost_budget()` is called **before** and **after** `decide()` inside the
  main loop — two checks per iteration to catch cost that lands exactly at the limit.
- The `while iterations < self.budget.max_iterations:` guard is unconditional.
- `tool_calls >= self.budget.max_tool_calls` checked before dispatching any tool.

**Violation consequence:** An unbounded run can exhaust money or context window,
stall indefinitely, or produce unreviewed side effects.

---

## I-5  Undo Journal Only Captures Committed Writes

**Invariant:** `UndoJournal._entries` contains only writes that **completed
successfully**. Failed, blocked, or denied writes leave no journal entry.

**Enforcement:**
- Pre-write snapshot stored in `_pending[call_id]` at `tool_call_started`.
- Moved to `_entries` only at `tool_call_completed`.
- Discarded (via `_pending.pop`) at `tool_call_failed`, `tool_call_blocked`,
  `tool_call_denied`.

**Violation consequence:** An entry for a write that never happened would cause
`restore()` to delete or overwrite a file that was never touched, producing
silent data loss.

---

## I-6  Undo Restore Uses Only the First Snapshot per Path

**Invariant:** When a file is written multiple times in one run, `restore()` uses the
oldest snapshot (the file's state before the first write) and ignores later
snapshots for the same path.

**Enforcement:**
- `restore()` tracks `seen: set[str]` and skips duplicate paths (`if entry.path in seen: continue`).
- Entries are stored in insertion order (list), so `_entries[0]` for a path is always
  the first-write snapshot.

**Violation consequence:** Restoring a later snapshot would leave the file in an
intermediate modified state rather than the original pre-run state.

---

## I-7  Permission Mode Can Only Increase Scope Within a Session

**Invariant:** During an interactive approval prompt the operator can grant *more*
access (y / p / t options), but cannot silently receive less access than the current
`PermissionMode`.

**Enforcement:**
- `ApprovalPresetStore.grant()` adds new grants; revoke is a separate explicit command.
- `_approval_handler` only widens scope (never narrows it mid-run).

**Note:** This invariant is a policy intent, not a hard code enforcement. An operator
explicitly calling `/permission read-only` changes the mode for the *next* run.

---

## I-8  Audit File Permissions Are Restricted

**Invariant:** Audit directories are `0o700` and audit files are `0o600`.

**Enforcement:**
- `secure_audit_dir(path.parent)` called on first write and on every create.
- `secure_audit_file(path)` called after every `os.fsync()` flush.
- `UndoJournal.save_to()` also calls these helpers.

---

## I-9  Checkpoint Context Does Not Leak Cross-Run

**Invariant:** `initial_context_extra` keys `task` cannot be overridden by the
`initial_context_extra` dict passed to `AgentRunner.run()`.

**Enforcement:**
```python
# runner/_core.py:294-296
context.update(
    {k: v for k, v in initial_context_extra.items() if k != 'task'}
)
```
The `task` key is always the caller-provided task string.

---

## I-10  Tool Call Context Is Thread-Local

**Invariant:** `ToolCallContext` (audit ref + run_id + call_id) is bound to the
current thread only for the duration of `registry.execute()` and reset immediately
after, even if the tool raises.

**Enforcement:**
- `bind_tool_call_context` / `reset_tool_call_context` wrap the execute call in a
  `try/finally` block (runner `_core.py:470-484`).
- `bind_parent_run_id` / `reset_parent_run_id` follow the same pattern.

---

## I-11  UndoJournal Paths Cannot Escape Workspace Root

**Invariant:** Only paths that resolve inside `workspace_root` are snapshotted.
Paths with `..` traversal are silently ignored.

**Enforcement:**
```python
# run_undo.py:167-170
abs_path = (self._root / rel_path).resolve()
abs_path.relative_to(self._root)  # raises ValueError if outside root
```
`_snapshot` returns `None` on `ValueError`, and `restore()` logs an error entry
without modifying any file.

---

## I-12  Approval Digest Binds Arguments to Call-ID

**Invariant:** An approval cannot be transferred from one call to a different set
of arguments. The `argument_digest` cryptographically binds the approval to the
exact arguments at the time of approval.

**Enforcement:**
- `_compute_argument_digest(arguments, workspace_secret)` in `_approval_grants.py`
  produces a SHA-256 over a canonical JSON of arguments + optional workspace secret.
- `check_scoped_approval_digest(run_id, call_id, tool_name, argument_digest)` verifies
  exact match before consuming the approval.
