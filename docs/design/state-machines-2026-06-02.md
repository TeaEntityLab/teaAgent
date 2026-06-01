# TeaAgent State Machines — 2026-06-02

Finite-state models for the major stateful components. States are derived from the
actual source code; transitions are labeled with the triggering events and guards.

---

## 1. Agent Run FSM

States and transitions for a single `AgentRunner.run()` invocation
(`teaagent/runner/_core.py`).

```
                     ┌─────────────────────────────────────────────────────┐
                     │                  AGENT RUN FSM                       │
                     └─────────────────────────────────────────────────────┘

        run() called
             │
             ▼
      ┌─────────────┐   audit: run_started
      │  STARTING   │──────────────────────────────────────────────────────►
      └─────────────┘
             │
             ▼
      ┌─────────────┐
      │   DECIDING  │◄──────────────────────────────────────────────────────┐
      └─────────────┘                                                        │
             │                                                               │
    ┌────────┴──────────────────────────────────────────────────────┐        │
    │                           decide(context)                      │        │
    │                                                                │        │
    ▼                                              ▼                 ▼        │
FinalAnswer                               ToolRequest         AgentHarnessError
    │                                          │                    │        │
    ▼                                          ▼                    ▼        │
┌──────────┐                        ┌─────────────────┐     ┌────────────┐  │
│COMPLETING│                        │ POLICY_CHECKING │     │  FAILING   │  │
└──────────┘                        └─────────────────┘     └────────────┘  │
    │                                         │                    │         │
    │ audit: run_completed                    │                    │         │
    │                             ┌───────────┴────────────┐       │         │
    ▼                             │                        │       │         │
┌──────────┐               allowed│               denied   │       │         │
│ COMPLETED│                      ▼                        ▼       │         │
└──────────┘              ┌──────────────┐     ┌──────────────────┐│         │
 status='completed'       │  DISPATCHING │     │ APPROVAL_PENDING  ││         │
                          └──────────────┘     └──────────────────┘│         │
                                 │              status='pending_approval'     │
                                 │              or re-raise ToolPermissionError│
                      ┌──────────┴──────────┐                      │         │
                      │                     │                       │         │
                  success               ToolExecutionError          │         │
                      │                     │                       │         │
                      ▼                     ▼                       │         │
              ┌──────────────┐    ┌──────────────────┐             │         │
              │  OBSERVING   │    │  ERR_OBSERVING   │             │         │
              └──────────────┘    └──────────────────┘             │         │
                      │           audit: tool_call_failed           │         │
                      │                 │                           │         │
                      │   (both paths)  │                           │         │
                      └────────────────►┼───────────────────────────┘         │
                                        │                                      │
                   iterations < max ────┘─────────────────────────────────────┘
                   iterations == max → FAILING (iteration_budget_exceeded)
```

### Run Status Strings (RunResult.status)

| Status | Meaning |
|---|---|
| `completed` | FinalAnswer returned |
| `pending_approval` | paused waiting for human approval |
| `failed:model_logic` | iteration/cost budget exceeded |
| `failed:permission` | ToolPermissionError not recoverable |
| `failed:transient` | transient error (network, etc.) |
| `failed:system` | unexpected exception |

---

## 2. Approval FSM

```
                     ┌─────────────────────────────────────────────────────┐
                     │               APPROVAL FSM                           │
                     └─────────────────────────────────────────────────────┘

  ToolPermissionError raised
           │
           ▼
  ┌────────────────────┐
  │  CHECKING_POLICY   │
  └────────────────────┘
           │
  ┌────────┴─────────────────────────────────────┐
  │ can_request_approval?                         │
  │                                               │
  ▼ True (destructive + PROMPT mode)             ▼ False
  ┌─────────────────┐                   ┌──────────────────┐
  │  AWAITING_HUMAN │                   │    BLOCKED       │
  └─────────────────┘                   └──────────────────┘
           │                             audit: tool_call_blocked
  ┌────────┴────────────────────────────────────────────────────┐
  │ handler(approval_request)?                                   │
  │                                                              │
  ▼ handler is None              ▼ True                ▼ False
  ┌──────────────┐        ┌──────────────┐     ┌──────────────────┐
  │   PAUSED     │        │   APPROVED   │     │     DENIED       │
  └──────────────┘        └──────────────┘     └──────────────────┘
  status='pending_approval'  audit: tool_call_approved  audit: tool_call_denied
  checkpoint saved           continue run execution     re-raise → FAILING
```

### Approval Preset Resolution (TeaAgentTUI._approval_handler)

```
handler called
  │
  ▼
ApprovalPresetStore.is_allowed(tool_name, permission_mode, arguments)?
  ├─ Yes → auto-approve (no prompt)
  └─ No  → print approval_required JSON
           input prompt: [y]es / [n]o / always [p]ath / always [t]ool / [s]top
            ├─ y   → approved (scoped)
            ├─ n   → denied
            ├─ p   → grant session preset (path-scoped, 8h TTL) → approved
            ├─ t   → grant session preset (tool-scoped, 8h TTL) → approved
            └─ s   → SystemExit (operator abort)
```

---

## 3. TUI REPL FSM

```
                     ┌─────────────────────────────────────────────────────┐
                     │                   TUI REPL FSM                       │
                     └─────────────────────────────────────────────────────┘

  run_tui() called
        │
        ▼
  ┌───────────┐  _load_workspace_defaults()
  │   INIT    │  _load_tui_state()
  └───────────┘  _print_header()
        │        initial_task? → RUNNING_TASK
        │
        ▼
  ┌───────────┐◄─────────────────────────────────────────────────────────────┐
  │  WAITING  │  input_fn(prompt) / prompt_toolkit.prompt()                  │
  └───────────┘                                                               │
        │                                                                      │
  ┌─────┴───────────────────────────────────────────────────────────────────┐ │
  │ raw_command                                                              │ │
  │                                                                          │ │
  ▼                               ▼                              ▼           │ │
exit/quit                   /run or /ask                    /command         │ │
  │                               │                              │           │ │
  ▼                               ▼                    ┌─────────┴──────────┐│ │
┌────────┐               ┌──────────────────┐          │  dispatch handler  ││ │
│  EXIT  │               │  RUNNING_TASK    │          │  (setup, session,  ││ │
└────────┘               └──────────────────┘          │   approve, undo,…) ││ │
  _stop_file_watcher()           │                     └─────────┬──────────┘│ │
  _save_tui_state()              │                               │            │ │
  return 0                       │ RunResult                     │            │ │
                                 └───────────────────────────────┘            │ │
                                                                               │ │
                                 (continue == True) ──────────────────────────┘ │
                                 (continue == False) ──────────────────────────►│EXIT
                                 EOFError/KeyboardInterrupt ───────────────────►│EXIT
```

### TUI Mode Flags

| Flag | Default | Effect |
|---|---|---|
| `chat` | False | multi-turn session history |
| `stream` | False | token-by-token LLM output |
| `subagent` | False | expose sub-delegation tool |
| `progress` | True | stream audit event progress lines |
| `allow_destructive` | False | bypass destructive gate |
| `route_model_enabled` | False | task-based model routing |
| `_conflict_mode` | False | git merge conflict resolution |

---

## 4. Session State FSM

```
  no session_id
       │ chat on / session new
       ▼
  ┌─────────┐
  │ CREATED │  uuid generated, SessionStore.save()
  └─────────┘
       │ ask run
       ▼
  ┌──────────┐
  │  ACTIVE  │◄─────────────────────────────────────────────────────┐
  └──────────┘                                                        │
       │                                                               │
  ┌────┴──────────────────────────────────────────────────────────┐    │
  │                                                               │    │
  ▼ run completes                          ▼ /compact            │    │
  append (user, assistant) messages        compact_chat_history   │    │
  SessionStore.save()                      SessionStore.save()    │    │
  │                                               │               │    │
  └───────────────────────────────────────────────┘               │    │
                       │ next ask                                  │    │
                       └──────────────────────────────────────────┘    │
                                                                         │
  /session switch <id> ──────────────────────────────────────────────►  │
  /session clear ─── messages.clear() ──────────────────────────────►  │
  /session new ────── new uuid ──────────────────────────────────────►  │
```

---

## 5. Tool Execution State

```
  runner decides ToolRequest
       │
       ▼
  ┌────────────────┐
  │ POLICY_CHECK   │  file_policy, plan_validator, auto_mode, approval_policy
  └────────────────┘
       │ allowed
       ▼
  ┌──────────────────┐
  │ PRE_EXEC         │  audit: tool_call_started
  │                  │  bind_parent_run_id / bind_tool_call_context
  └──────────────────┘
       │
       ▼
  ┌──────────────────┐
  │  EXECUTING       │  registry.execute(tool_name, arguments)
  └──────────────────┘
       │
  ┌────┴──────────────────────────────┐
  │                                   │
  ▼ success                          ▼ ToolExecutionError
  ┌────────────────┐        ┌────────────────────────┐
  │  COMPLETED     │        │  EXEC_FAILED           │
  └────────────────┘        └────────────────────────┘
  audit: tool_call_completed  audit: tool_call_failed
  UndoJournal: commit         UndoJournal: discard pending
  context.append(result)      context.append(error obs)
  checkpoint_store.save()     checkpoint_store.save()
                              continue loop (no raise)
```

---

## 6. Parallel Experiment FSM

```
  /parallel optA optB optC
       │
       ▼
  ┌──────────────┐
  │  BRANCHING   │  ParallelExperimentStack.start_all(auto_stash=True)
  └──────────────┘  git checkout -b experiment/optA, optB, optC
       │
       ▼
  ┌──────────────────┐
  │  EXPERIMENTING   │◄─── /run <task> (user runs tasks on each branch manually)
  └──────────────────┘
       │
  ┌────┴──────────────────────────────┐
  │                                   │
  ▼ /select optA                     ▼ /cancel
  ┌──────────────────┐    ┌──────────────────────────┐
  │   MERGING        │    │   CANCELLING             │
  └──────────────────┘    └──────────────────────────┘
  git checkout original    cleanup_all()
  git merge experiment/optA
  cleanup_all(keep_best=optA)
       │                              │
       ▼                              ▼
  ┌──────────────┐           ┌─────────────────┐
  │   MERGED     │           │   CANCELLED     │
  └──────────────┘           └─────────────────┘
  _parallel_stack = None      _parallel_stack = None
```
