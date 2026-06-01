# subagents — Purpose, Dependencies, Exported API, Call Graph

## Purpose

The `subagents` module provides:

1. **Definition loading** — Reads subagent persona files from `.teaagent/subagents/` (YAML/JSON/Markdown with frontmatter) and builds typed `SubagentDef` objects.
2. **Lifecycle management** — `SubagentManager` prepares workspace isolation, builds a scoped child `ToolRegistry`, launches child `run_chat_agent` runs, captures review artifacts, and stores session records.
3. **Tool registration** — `register_subagent_tools` registers `subagent`, `subagent_<name>`, `subagent_batch`, and `team` tools into the parent's `ToolRegistry`.
4. **Approval queue** — `CentralizedApprovalQueue` serializes destructive-tool requests from parallel subagents to a centralized in-memory + on-disk queue so the parent TUI can review them as a batch.
5. **Team orchestration** — `TeamOrchestrator` distributes a single task to N specialist subagents sequentially (up to `max_concurrent`), then merges outputs.

---

## File Map

| File | Responsibility |
|------|---------------|
| `__init__.py` | Public re-exports |
| `_types.py` | `SubagentDef`, `SubagentLineage`, `SubagentSession` dataclasses |
| `_loader.py` | Parse YAML/JSON/Markdown definition files |
| `_isolation.py` | Create/clean `IsolationContext` (shared, worktree, directory-snapshot, docker, auto) |
| `_manager.py` | `SubagentManager` — orchestrates a single subagent execution |
| `_tools.py` | `register_subagent_tools` — `subagent`, `subagent_<name>`, `subagent_batch`, `team` |
| `_team_orchestrator.py` | `TeamOrchestrator`, `TeamDef`, `load_team_defs` |
| `_review.py` | `capture_subagent_review`, `list_subagent_reviews`, `apply_subagent_review` |
| `_approval_queue.py` | `CentralizedApprovalQueue` + module-level helpers/global registry |
| `_approval_queue_store.py` | `ApprovalQueueStore` — disk persistence, HMAC, file locking, pruning |

---

## Imports / Dependencies

### Internal

| Module | Imported by |
|--------|------------|
| `teaagent.chat_agent.run_chat_agent` | `_manager.py` |
| `teaagent.llm.LLMAdapter` | `_manager.py`, `_tools.py` |
| `teaagent.tools.ToolRegistry`, `ToolAnnotations` | `_manager.py`, `_tools.py` |
| `teaagent.run_store.RunStore` | `_manager.py` |
| `teaagent.subagent_run_context` | `_manager.py`, `_tools.py` |
| `teaagent.runner._types.ApprovalHandler`, `ApprovalRequest` | `_approval_queue.py` |
| `teaagent.storage.atomic_write_text` | `_review.py` |
| `teaagent.policy.parse_permission_mode`, `PermissionMode` | `_loader.py`, `_types.py` |
| `teaagent.consensus.RiskLevel` | `_manager.py` (conditional — `isolation=auto`) |
| `teaagent.skill_router.plan_skill_isolation` | `_manager.py` (conditional — `isolation=auto`) |
| `teaagent.workspace_tools._config._load_gitignore_matcher` | `_isolation.py` |

### External / stdlib

| Package | Usage |
|---------|-------|
| `asyncio` | Async futures in `CentralizedApprovalQueue` |
| `threading` | Sync waiters, `_queue_lock`, `_sync_lock` |
| `concurrent.futures.ThreadPoolExecutor` | `subagent_batch` parallel execution |
| `subprocess` | Git worktree ops, Docker ops, review patches |
| `shutil` | Directory snapshot copy/cleanup |
| `yaml` (optional) | YAML def file parsing (falls back to `_load_simple_yaml`) |
| `fcntl` (optional, Unix only) | File locking in `ApprovalQueueStore` |
| `hmac`, `hashlib` | HMAC-SHA256 for queue file integrity |

---

## Exported Symbols (`__init__.py`)

```python
DEFAULT_SUBAGENT_ISOLATION  # str constant
SubagentDef                  # frozen dataclass
SubagentLineage              # frozen dataclass
SubagentSession              # frozen dataclass
SubagentManager              # class
load_subagent_defs           # function(root: Path) -> dict[str, SubagentDef]
register_subagent_tools      # function(registry, *, adapter, config, depth, manager)
```

---

## Entry Points

| Entry Point | Called from |
|-------------|------------|
| `load_subagent_defs(root)` | `SubagentManager.__init__` |
| `SubagentManager.run_subagent(...)` | `_tools.py` handlers (`execute`, `execute_named`, `_run_one`) |
| `register_subagent_tools(registry, ...)` | Runner / chat agent setup |
| `make_centralized_subagent_approval_handler(...)` | `_manager.py` when `use_centralized=True` |
| `get_approval_queue(parent_run_id, ...)` | TUI / CLI approval review flow |
| `approve_request_cross_process(...)` / `deny_request_cross_process(...)` | CLI commands |

---

## Call Graph

```
register_subagent_tools(registry, adapter, config, depth, manager)
  └── manager.bind_registry(registry)
  └── _register(registry, 'subagent', handler=execute)
         └── execute(args)
               └── manager.run_subagent(task, parent_run_id, depth, ...)
  └── for sub_def in manager.list_defs():
         _register(registry, 'subagent_<name>', handler=execute_named)
               └── execute_named → manager.run_subagent(def_name=...)
  └── _register_batch(registry, manager, depth, config)
         └── execute_batch(args)
               └── ThreadPoolExecutor → _run_one(task_obj, batch_index)
                     └── manager.run_subagent(batch_index=i)
  └── _register_team_tool(registry, manager)
         └── TeamOrchestrator(root, manager)
         └── execute_team(args)
               └── orchestrator.run_team(task, team_name, parent_run_id)
                     └── for spec in team.specialists:
                           manager.run_subagent(task, ...)

SubagentManager.run_subagent(...)
  ├── get_def(def_name) → SubagentDef
  ├── depth check → return _error(...)
  ├── normalize_subagent_isolation(isolation)
  ├── plan_skill_isolation(skill_path, risk)      [isolation=auto only]
  ├── prepare_subagent_isolation(root, isolation, session_key)
  │     ├── shared → IsolationContext(child_root=root)
  │     ├── worktree → subprocess git worktree add
  │     ├── directory-snapshot → _copy_workspace_snapshot()
  │     └── docker → subprocess docker run
  ├── should_use_centralized_approval(...)
  ├── make_centralized_subagent_approval_handler(...)  [if centralized]
  ├── _build_registry_for(sub_def)
  │     └── copy parent tools except subagent/*
  ├── run_chat_agent(task, adapter, config, audit, registry, depth, ...)
  ├── capture_subagent_review(parent_root, child_root, ...)
  │     ├── _git(child, ['add', '-N', ...])
  │     ├── _git(child, ['diff', '--binary', 'HEAD', ...])
  │     └── atomic_write_text(patch_file, diff)
  └── iso_ctx.cleanup()   [always, in finally]

CentralizedApprovalQueue.submit_request_sync(...)
  ├── _persist()  →  ApprovalQueueStore.save(...)
  └── poll loop (0.25s) → reload_from_store() → check status
        └── approve_request_sync / deny_request_sync resolves via threading.Event
```
