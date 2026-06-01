# TeaAgent Module Documentation Index

Generated: 2026-06-02 | 24 modules | 92 documents

---

## Module Dependency Graph

```
                        ┌─────────────────────────────────────┐
                        │              cli                     │
                        │  (entry point for all user commands) │
                        └──────────┬──────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         ┌─────────┐        ┌──────────┐         ┌──────────┐
         │  runner │        │   tui    │         │ chat_    │
         │ (agent  │        │(terminal │         │ session_ │
         │  loop)  │        │   UI)    │         │controller│
         └────┬────┘        └────┬─────┘         └────┬─────┘
              │                  │                     │
              └──────────────────┼─────────────────────┘
                                 │ uses
          ┌──────────────────────┼────────────────────────┐
          ▼                      ▼                        ▼
    ┌──────────┐          ┌──────────┐            ┌──────────┐
    │  tools   │          │   llm    │            │  audit   │
    │(registry)│          │(adapters)│            │(logging) │
    └────┬─────┘          └────┬─────┘            └────┬─────┘
         │                     │                       │
         ▼                     ▼                       ▼
  ┌──────────────┐     ┌──────────────┐       ┌──────────────┐
  │workspace_    │     │  streaming   │       │  governance  │
  │   tools      │     │  (events)    │       │(plan gate,   │
  └──────────────┘     └──────────────┘       │ policy)      │
                                              └──────────────┘
          │                     │
          ▼                     ▼
   ┌──────────┐         ┌──────────┐
   │  hooks   │         │ approval │
   │(lifecycle│         │ manager  │
   │  gates)  │         │          │
   └──────────┘         └──────────┘
          │                     │
          ▼                     ▼
   ┌──────────┐         ┌──────────┐
   │  context │         │  budget  │
   │(compaction│        │ monitor  │
   │ /session) │        │          │
   └──────────┘         └──────────┘
          │
          ├──────────────┬──────────────┐
          ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ subagents│  │  skills  │  │   mcp    │
   │(parallel │  │(executor │  │(client & │
   │  runs)   │  │ /router) │  │ server)  │
   └──────────┘  └──────────┘  └──────────┘
          │              │
          ▼              ▼
   ┌──────────┐  ┌──────────┐
   │ sandbox  │  │  memory  │
   │ (git/OS/ │  │(catalog/ │
   │  VFS)    │  │ catalog) │
   └──────────┘  └──────────┘
```

---

## Module Index

| Module | Layer | Purpose | Files |
|--------|-------|---------|-------|
| [runner](runner/) | Core | Agent execution loop, approval, plan validation | [spec](runner/spec.md) · [inspection](runner/inspection.md) · [risks](runner/risks.md) · [api](runner/api.md) |
| [llm](llm/) | Core | Provider-agnostic LLM adapters (Claude, OpenAI, Gemini) | [spec](llm/spec.md) · [inspection](llm/inspection.md) · [risks](llm/risks.md) · [api](llm/api.md) |
| [tools](tools/) | Core | Tool registry, schema validation, hook dispatch | [spec](tools/spec.md) · [inspection](tools/inspection.md) · [risks](tools/risks.md) · [api](tools/api.md) |
| [hooks](hooks/) | Core | 8-event hook lifecycle, veto mechanism | [spec](hooks/spec.md) · [inspection](hooks/inspection.md) · [risks](hooks/risks.md) · [api](hooks/api.md) |
| [audit](audit/) | Core | Tamper-evident JSONL audit log with SHA-256 hash chain | [spec](audit/spec.md) · [inspection](audit/inspection.md) · [risks](audit/risks.md) · [api](audit/api.md) |
| [governance](governance/) | Core | Plan gate, policy enforcement, tool linting | [spec](governance/spec.md) · [inspection](governance/inspection.md) · [risks](governance/risks.md) · [api](governance/api.md) |
| [approval_manager](approval_manager/) | Core | JIT approvals, presets, multi-sig quorum | [spec](approval_manager/spec.md) · [inspection](approval_manager/inspection.md) · [risks](approval_manager/risks.md) · [api](approval_manager/api.md) |
| [context](context/) | Core | Context compaction, session state, pub/sub bus | [spec](context/spec.md) · [inspection](context/inspection.md) · [risks](context/risks.md) · [api](context/api.md) |
| [streaming](streaming/) | Core | Audit-to-stream event mapping, progress display | [spec](streaming/spec.md) · [inspection](streaming/inspection.md) · [risks](streaming/risks.md) · [api](streaming/api.md) |
| [budget](budget/) | Core | Cost tracking, budget enforcement | [spec](budget/spec.md) · [inspection](budget/inspection.md) · [risks](budget/risks.md) · [api](budget/api.md) |
| [cli](cli/) | Interface | CLI entry point, argparse dispatch, all commands | [spec](cli/spec.md) · [inspection](cli/inspection.md) · [risks](cli/risks.md) · [api](cli/api.md) |
| [tui](tui/) | Interface | Textual TUI for interactive chat | [spec](tui/spec.md) · [inspection](tui/inspection.md) · [risks](tui/risks.md) · [api](tui/api.md) |
| [chat_agent](chat_agent/) | Interface | Chat agent state machine and LLM dispatch | [spec](chat_agent/spec.md) · [inspection](chat_agent/inspection.md) · [risks](chat_agent/risks.md) · [api](chat_agent/api.md) |
| [chat_session_controller](chat_session_controller/) | Interface | Stateful chat session: history, cost, tools | [spec](chat_session_controller/spec.md) · [inspection](chat_session_controller/inspection.md) · [risks](chat_session_controller/risks.md) · [api](chat_session_controller/api.md) |
| [workspace_tools](workspace_tools/) | Tools | File, git, shell tools for workspace | [spec](workspace_tools/spec.md) · [inspection](workspace_tools/inspection.md) · [risks](workspace_tools/risks.md) · [api](workspace_tools/api.md) |
| [subagents](subagents/) | Execution | Sub-agent lifecycle, isolation, approval queue | [spec](subagents/spec.md) · [inspection](subagents/inspection.md) · [risks](subagents/risks.md) · [api](subagents/api.md) |
| [sandbox](sandbox/) | Execution | Git branch, OS, VFS, Docker isolation | [spec](sandbox/spec.md) · [inspection](sandbox/inspection.md) · [risks](sandbox/risks.md) · [api](sandbox/api.md) |
| [skills](skills/) | Extension | Skill discovery, routing, sandboxed execution | [spec](skills/spec.md) · [inspection](skills/inspection.md) · [risks](skills/risks.md) · [api](skills/api.md) |
| [mcp](mcp/) | Extension | MCP client/server, trust management | [spec](mcp/spec.md) · [inspection](mcp/inspection.md) · [risks](mcp/risks.md) · [api](mcp/api.md) |
| [memory](memory/) | Storage | Memory catalog, pinned files, failure cards | [spec](memory/spec.md) · [inspection](memory/inspection.md) · [risks](memory/risks.md) · [api](memory/api.md) |
| [context_pack](context_pack/) | Core | Context packing and semantic compression | [spec](context_pack/spec.md) · [risks](context_pack/risks.md) |
| [pinned_file](pinned_file/) | Storage | Pinned file watching, path validation | [spec](pinned_file/spec.md) · [risks](pinned_file/risks.md) |
| [git_sandbox](git_sandbox/) | Execution | Git branch sandboxing, stash, rollback | [spec](git_sandbox/spec.md) · [risks](git_sandbox/risks.md) |
| [run_store](run_store/) | Core | Persistent run storage, replay, audit | [spec](run_store/spec.md) · [inspection](run_store/inspection.md) · [risks](run_store/risks.md) |
---

## Layer Definitions

| Layer | Description |
|-------|-------------|
| **Core** | Foundational — all other modules depend on these |
| **Interface** | User-facing — CLI, TUI, chat sessions |
| **Tools** | Workspace interaction — filesystem, git, shell |
| **Execution** | Run isolation — subagents, sandboxing |
| **Extension** | Plugin points — skills, MCP |
| **Storage** | Persistence — memory, audit, session |

---

## Critical Risk Summary

| Risk ID | Module | Severity | Description |
|---------|--------|----------|-------------|
| R1 | audit | High | L3 stores plaintext credentials |
| R2 | audit | Medium | Regex redaction incomplete |
| R4 | audit | Medium | `hmac.new()` deprecated in Python 3.14 |
| R1 | hooks | High | Hook registration not thread-safe |
| R3 | hooks | Medium | `run_tests_hook` raises `HookError` as post-hook |
| R1 | mcp | Critical | MCP tool injection from untrusted server |
| R3 | approval_manager | High | `DANGER_FULL_ACCESS` bypasses all approval |
| R1 | sandbox | High | Git sandbox unavailable in detached HEAD |
| R3 | workspace_tools | High | Shell command injection if `shell=True` |
| R1 | governance | High | `DANGER_FULL_ACCESS` bypasses plan gate |
| R1 | skills | High | Native skill runs in same process (no isolation) |
| R8 | llm | Medium | No timeout on streaming connections |
| R1 | runner | High | Policy override in auto mode — approval policy mutated in-place and never restored after auto mode exits |
| R2 | runner | Medium | Bare exception swallowing in run loop — programming errors silently become `failed:SYSTEM` |
| RSK-01 | subagents | High | Path traversal in isolation session keys — no length cap on `def_name` segment |
| RSK-02 | subagents | High | Directory-snapshot workspace copy exposes `.env`/secrets if not gitignored |
| RSK-06 | subagents | High | Deadlock risk from nested `asyncio._lock` inside `threading._sync_lock` |
| R1 | memory | High | Duplicate `MemoryCatalog` implementation — divergent `memory_matches()` from `memory_legacy.py` |
| R2 | memory | High | Windows data corruption — no cross-process locking, concurrent writes can corrupt `memory.jsonl` |
| R3 | memory | High | Non-atomic rewrites in `catalog.py` — `delete_by_branch`/`delete_by_run_id` truncate file on crash |
| R2 | budget | Medium | Over-budget execution — `on_prompt` returning `False` does not halt run if caller ignores return value |

---

## Known P0/P1 Bugs (from memory)

See `docs/daily-driver-known-issues-2026-06-01.md` for confirmed unfixed bugs:
- **CG-01**: Chat result handling incorrect
- **CG-02**: Destructive undo
- **CG-03**: Fake cost display (TUI shows 0)
- **TASK-DD2-001**: Initial task passthrough CLI→TUI (fixed in commit `47710d9`)

---

## Document Standards

Each module directory contains:
- `spec.md` — Behavior contract, invariants, state machines
- `inspection.md` — Purpose, dependencies, call graph, entry points
- `risks.md` — Risk vectors, failure modes, file:line references
- `api.md` — Public API with pre/post conditions, data models

---

*Generated by multi-agent documentation sweep, 2026-06-02. Verify against source before acting on specific line references.*
