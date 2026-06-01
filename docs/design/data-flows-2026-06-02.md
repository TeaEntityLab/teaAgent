# TeaAgent Data Flows — 2026-06-02

Traces the movement of data through the major runtime paths. All paths are grounded in
the current source tree; file references are relative to the repo root.

---

## 1. Chat Run Flow (`ask` / `run` task)

```
CLI args / TUI input
     │
     ▼
teaagent/cli/_handlers/_chat.py  ──chat_command──►  teaagent/tui/__init__.py
  parse_args                                           run_tui(initial_task=...)
  build ChatAgentConfig
     │
     ▼
TeaAgentTUI._run_agent_task(task)          teaagent/tui/__init__.py:859
  expand_at_references                     # file @-mentions resolved to content
  clarify_task (optional)
  route_model (optional)
  build adapter
  create RunStore → audit_logger()
  create UndoJournal (audit sink)
  attach progress_sink (optional)
     │
     ▼
run_chat_agent(task, adapter, config, audit)   teaagent/chat_agent.py
  build workspace tool registry
  load memory entries → inject into prompt
  load skill index
  build system prompt (assemble_agent_prompt)
  build initial LLM request
     │
     ▼
AgentRunner.run(task, decide=…)           teaagent/runner/_core.py:278
  audit.record('run_started')
  LOOP:
    decide(context) → Decision
       ├─ FinalAnswer  → audit.record('run_completed') → RunResult
       └─ ToolRequest  →
            file_policy.assert_allowed()
            plan_validator.validate_write_allowed()
            auto_mode_manager.validate_tool_allowed()
            approval_policy.assert_allowed()  [may raise ToolPermissionError]
            audit.record('tool_call_started')
            registry.execute(tool_name, arguments)
            audit.record('tool_call_completed')
            context['observations'].append(result)
            checkpoint_store.save() (if set)
            compact context (if observation count > threshold)
     │
     ▼
RunResult  ←─────────────────────────────────────────────────────────────
  _session_cost_cents += result.cost_cents
  store.logger_for_result(result, audit)     # persist JSONL run record
  undo_journal.save_to(store.undo_path())    # persist undo journal
  last_run_id = result.run_id
  chat session updated (if chat mode)
  output JSON payload / final answer
```

### Key data structures passing through this flow

| Object | Type | Owner | Purpose |
|---|---|---|---|
| `context` | `dict` | AgentRunner | Rolling observation window: `{task, observations, _cost_cents, …}` |
| `AuditEvent` | frozen dataclass | AuditLogger | Immutable, hash-chained event record |
| `RunResult` | frozen dataclass | AgentRunner | Final summary returned to caller |
| `_JournalEntry` | frozen dataclass | UndoJournal | Pre-write file snapshot |
| `ChatSession` | dataclass | SessionStore | Multi-turn message history |

---

## 2. Approval Flow

```
approval_policy.assert_allowed() raises ToolPermissionError
     │
     ▼
ApprovalManager.can_request_approval(destructive)
  ├─ False (read-only or non-destructive)  →  record_blocked() → re-raise
  └─ True  →
       create_approval_request(call_id, tool_name, arguments, …)
       handle_approval_request(approval_request, audit, …)
            ├─ no handler  →  audit.record('run_paused')
            │               checkpoint_store.save()
            │               return RunResult(status='pending_approval')
            └─ handler present  →  handler(approval_request)
                 ├─ True   →  audit.record('tool_call_approved') → continue run
                 └─ False  →  audit.record('tool_call_denied')  → raise
```

Approval handlers live in `TeaAgentTUI._approval_handler` (interactive prompt)
or `ApprovalPresetStore.is_allowed()` (preset/digest-based auto-approval).

---

## 3. Undo Flow

```
AgentRunner dispatches tool_call_started
     │
     ▼
UndoJournal.__call__(event)          teaagent/run_undo.py:122
  event_type == 'tool_call_started'
  tool_name ∈ {workspace_write_file, workspace_apply_patch, workspace_edit_at_hash}
  _snapshot(rel_path) → _JournalEntry (base64 pre-write content)
  self._pending[call_id] = entry

tool_call_completed
  _on_tool_completed(call_id)
  _entries.append(entry)             # committed

tool_call_failed | tool_call_blocked | tool_call_denied
  _pending.pop(call_id)              # discarded — no state change

─────────────
User runs /undo or `teaagent agent undo`
     │
     ▼
UndoJournal.restore()
  for entry in _entries (oldest first):
    if existed_before: write original bytes
    else:              delete file
  return UndoResult(restored, deleted, errors)
  undo journal file unlinked (on success)
  audit.record('undo_applied', run_id, …)
```

---

## 4. Cost Tracking Flow

```
LLM response → LLMAdapter extracts (input_tokens, output_tokens, cost_cents)
     │
     ▼
context['_cost_cents']      updated by decide() callback in AgentRunner
context['_input_tokens']
context['_output_tokens']

AgentRunner._assert_cost_budget(cost_cents)   called before AND after decide()
  BudgetExceededError if cost_cents > max_estimated_cost_cents

AgentRunner._check_budget_warnings(cost_cents)
  50% / 80% / 90% / 100% thresholds
  audit.record('budget_warning', …)
  BudgetMonitor.check_at_threshold()
    PROMPT_CONFIRM → audit.record('budget_prompt') → RunCancelledError
    SUGGEST_READ_ONLY → audit.record('budget_read_only_suggested')

FinalAnswer path → audit.record('run_completed', cost_cents=…)
─────────────
TeaAgentTUI._run_agent_task returns
  self._session_cost_cents += result.cost_cents   # in-memory session accumulation

─────────────
/cost command → self._session_cost_cents / 100 (display)

─────────────
CostTracker (teaagent/cost_tracker.py)   off-line aggregation
  scans .teaagent/runs/*.jsonl
  extracts run_completed / run_failed events
  aggregates by label / day / model
```

---

## 5. Suspend / Resume Flow

```
Run blocked at approval → RunResult(status='pending_approval')
OR
User sends Ctrl-C / cancel_token.set()
     │
     ▼
checkpoint_store.save(run_id, context)   # context = {task, observations}
run_store.record_pending_approval()

─────────────
Resume:
  teaagent agent resume <run_id>
    or TUI: resume <run_id>
     │
     ▼
store.task_for_run(run_id)      # recover original task
store.observations_for_run()   # recover checkpoint context
store.pending_approval_for_run()

if pending:
  ApprovalPresetStore.add_scoped_approval(run_id, call_id, …)

_run_agent_task(task, initial_observations=observations, resumed_from=run_id)
  AgentRunner.run(initial_observations=…)
  context rebuilt with replayed observations → continue from checkpoint
```

---

## 6. Audit Logging Flow

```
AuditLogger.record(event_type, run_id, **payload)    teaagent/audit.py:241
     │
     ├─ _apply_audit_level(payload)   L0/L1/L2/L3 tier filtering
     ├─ redact_audit_payload()        scrub secrets, truncate long strings
     ├─ AuditEvent created (frozen, event_id=uuid, created_at=UTC ISO)
     │
     ├─ self._lock: events.append(event)   in-memory list
     │
     └─ file_lock(path):
          last_chain_hash(path)            read prev_hash from last JSONL line
          canonical JSON → SHA-256 hash    hash-chain integrity
          compute_chain_hmac(hash, key)    per-run HMAC secret
          path.open('a').write(line)
          os.fsync()                       durability flush
          secure_audit_file(path)          chmod 600

     └─ for sink in sinks:
          sink(event)                      fire-and-forget (UndoJournal, progress)
```

Each run gets a separate JSONL file at `.teaagent/runs/<run_id>.jsonl`.
Chain integrity can be verified with `AuditLogger.verify_chain_integrity()`.

---

## 7. Session / Chat History Flow

```
TUI chat mode on → _ensure_session() → ChatSession (uuid id, messages=[])
                   SessionStore.save(session)

Each ask run:
  chat_messages = [LLMMessage(role, content) for m in session.messages]
  passed into run_chat_agent(chat_messages=…)
  → injected as LLM message history before system prompt

Post-run:
  session.messages.append(ChatMessage(role='user', content=task))
  session.messages.append(ChatMessage(role='assistant', content=answer))
  SessionStore.save(session)

/compact:
  ContextCompactor.compact_chat_history(messages_dicts, max_tokens)
  session.messages = compacted + [system summary note]
  SessionStore.save(session)
```

---

## 8. Sequence Diagram — Simple Chat Run

```
User            TUI                  AgentRunner         LLM          Audit
 │                │                       │               │              │
 │ ask "task"     │                       │               │              │
 ├───────────────►│                       │               │              │
 │                │ run_chat_agent        │               │              │
 │                ├──────────────────────►│               │              │
 │                │                       │ run_started   │              │
 │                │                       ├───────────────────────────►  │
 │                │                       │               │              │
 │                │                       │ decide(ctx)   │              │
 │                │                       ├──────────────►│              │
 │                │                       │  ToolRequest  │              │
 │                │                       │◄──────────────┤              │
 │                │                       │               │  tool_call_started
 │                │                       ├───────────────────────────►  │
 │                │                       │ execute tool  │              │
 │                │                       ├──────────────►│ (if LLM tool)│
 │                │                       │  result       │              │
 │                │                       │◄──────────────┤              │
 │                │                       │               │  tool_call_completed
 │                │                       ├───────────────────────────►  │
 │                │                       │ decide(ctx)   │              │
 │                │                       ├──────────────►│              │
 │                │                       │  FinalAnswer  │              │
 │                │                       │◄──────────────┤              │
 │                │                       │               │  run_completed
 │                │                       ├───────────────────────────►  │
 │                │ RunResult             │               │              │
 │                │◄──────────────────────┤               │              │
 │ JSON output    │                       │               │              │
 │◄───────────────┤                       │               │              │
```
