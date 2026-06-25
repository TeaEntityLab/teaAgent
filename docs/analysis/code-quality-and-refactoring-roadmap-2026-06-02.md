# Code Quality & Refactoring Roadmap — 2026-06-02

**Scope:** `teaagent/` package + `tests/`  
**Tools used:** flake8 7.3.0 · bandit 1.9.4 · radon 6.0.1 · vulture 2.16 · pylint 4.0.5 · manual audit  
**Total source functions analysed:** 2,928  

---

## Severity Legend

| Level | Meaning |
|---|---|
| **P0** | Runtime error risk or correctness bug — fix before next release |
| **P1** | High complexity or major architectural defect — fix within sprint |
| **P2** | Medium debt, quality/maintainability impact — address within cycle |
| **QW** | Quick win — under 10-minute fix, low risk |

---

## 1. Static Analysis Findings

### 1a. Undefined symbols in `__all__` (P0)

Three names exported in `teaagent/__init__.__all__` are never imported into the module — any consumer doing `from teaagent import X` for these will get an `ImportError` at runtime.

| Line | Symbol | Remedy |
|---|---|---|
| `teaagent/__init__.py:278` | `AIBOMComponent` | Import from `teaagent.aibom` or remove from `__all__` |
| `teaagent/__init__.py:282` | `AuditEvent` | Import from `teaagent.audit` or remove from `__all__` |
| `teaagent/__init__.py:439` | `ToolRegistryBuilder` | Import from `teaagent.workspace_tools.builder` or remove |

### 1b. Unused `nonlocal` declarations (P1)

`nonlocal` is declared but the variable is never re-assigned in scope — the declaration is misleading and can mask future bugs when a developer assumes the outer variable is being written.

| File | Lines | Variables |
|---|---|---|
| `teaagent/cli/_handlers/_chat.py` | 690 | `session_context`, `targeted_files` |
| `teaagent/cli/_handlers/_chat.py` | 765 | `file_watcher` |
| `teaagent/cli/_handlers/_chat.py` | 815 | `checkpoint_created`, `checkpoint_ref` |
| `teaagent/cli/_handlers/chat_repl.py` | 282 | `session_context`, `targeted_files` |
| `teaagent/cli/_handlers/chat_repl.py` | 346 | `file_watcher` |
| `teaagent/cli/_handlers/chat_repl.py` | 395 | `checkpoint_ref` |

Remedy: remove each unused `nonlocal` statement.

### 1c. Wildcard import (P1)

`teaagent/git_sandbox.py:10` — `from teaagent.sandbox import *` pollutes the namespace unpredictably and breaks static analysis. Replace with explicit imports.

### 1d. Dead import in oauth21 (QW)

`teaagent/oauth21/_types.py:10` — `encode_dss_signature` is imported from `cryptography` but never used. Remove.

### 1e. Re-export `__init__.py` false-positive F401s (QW)

`teaagent/llm/__init__.py` (20 symbols) and `teaagent/workspace_tools/__init__.py` (9 symbols) are re-export shims — flake8 flags them as unused. Add `# noqa: F401` to each re-export line **or** add an explicit `__all__` list to suppress correctly.

### 1f. Reimports inside functions — `swarm.py` (P2)

`teaagent/swarm.py:213–214` and `:535` reimport `threading` and `time` inside the body of methods already imported at module level. This wastes import machinery on every call and confuses readers.

```
swarm.py:213  import threading  # already at line 13
swarm.py:214  import time       # already at line 14
swarm.py:535  import time       # again
```

Move to module-level. Also: `swarm.py:226` declares `HEARTBEAT_TICK_INTERVAL` as a local variable inside a method — it should be a module-level constant.

### 1g. Logging f-string interpolation (QW)

Multiple files use `logger.info(f"…")` which evaluates the format string even when the log level is suppressed. Replace with `logger.info("…%s", var)` or `logger.info("…", extra={"key": val})`.

Worst offenders: `swarm.py` (4 instances), `coordinator.py` (2), `acp_adapter.py` (1), `plugins.py` (3).

### 1h. Assigned but unused variables (QW)

| File | Line | Variable | Action |
|---|---|---|---|
| `teaagent/cli/_handlers/_agent.py` | 470 | `_sp_sigint_restore` | Prefix `_` is misleading — variable holds signal handler. Use `_` or actually use the value. |
| `tests/test_cli.py` | 273 | `_tmp` | Remove or assign to `_` |

---

## 2. Security Findings (bandit)

### 2a. `exec()` of user code (P1 — intentional but must be documented)

`teaagent/code_mode/_child_process.py:77`:
```python
exec(compile(code, '<teaagent-code-mode>', 'exec'), namespace, namespace)
```
This is `SAFE_BUILTINS`-sandboxed intentionally. However:
- The sandbox is not documented in a comment explaining why this `exec` is safe.
- `SAFE_BUILTINS` is never audited in tests for bypass.
- Bandit B102 (CWE-78) — add `# noqa: B102` with an inline explanation of the sandboxing invariant.

### 2b. SQL table-name injection (P1)

`teaagent/schema_migration.py:92`:
```python
f'SELECT version FROM {self.TABLE} ORDER BY version'
```
`self.TABLE` is a class attribute (`str`), currently hardcoded. However, if a subclass or caller can influence `TABLE`, this is a SQL injection vector. SQLite does not support parameterised table names. Remedy: assert `TABLE` is an identifier-safe string (alphanumeric + `_`) at class instantiation, and add `# noqa: B608` with a comment.

`teaagent/context_bus.py:460` — `f'DELETE FROM delta_cards WHERE delta_id IN ({placeholders})'` — `placeholders` is built from `'?' * len(delta_ids)` which is safe. Add `# noqa: B608` with inline comment explaining placeholder construction.

### 2c. `urllib.request.urlopen` used project-wide (P2)

14 call-sites use `urllib.request.urlopen` directly (bandit B310, CWE-22). This library does not validate schemes or enforce redirects safely. Centralise HTTP calls behind a thin wrapper that:
- Validates the scheme is `https://` or an explicitly allowlisted `http://`
- Enforces a timeout
- Handles redirect limits

Key locations: `agentcard.py:372,393,443`, `automation_delivery.py:99`, `github_integration.py:45`, `llm/_adapters.py:233,417`, `notify.py:114,169,203`, `marketplace/_client.py:47,74`, `llm/_transport.py:55`, `signature_relay.py:178`.

### 2d. Hardcoded temp directory string (QW)

`teaagent/tsb_format.py:86` — `'/tmp/'` literal in a redaction rule (bandit B108). Replace with `tempfile.gettempdir()` for portability.

### 2e. Bind-all-interfaces flag (QW)

`teaagent/mcp_http/__init__.py:37` — the check `host in {'', '0.0.0.0', '::'}` is correct logic. Add `# noqa: B104` with a comment confirming this is intentional host validation, not accidental binding.

---

## 3. Cyclomatic Complexity

Radon grades: A (1–5), B (6–10), C (11–15), D (16–20), E (21–25), F (26+).

### 3a. F-grade functions — split immediately (P0 / P1)

| File | Line | Function | CC | Priority |
|---|---|---|---|---|
| `teaagent/tui/_commands.py` | 38 | `_handle_tui_command` | **225** | **P0** |
| `teaagent/chat_agent.py` | 419 | `_run_chat_agent_impl` | **38** | **P1** |
| `teaagent/automation_ticket.py` | 240 | `validate_automation_spec` | **34** | **P1** |
| `teaagent/subagents/_manager.py` | 76 | `SubagentManager.run_subagent` | **32** | **P1** |
| `teaagent/runner/_core.py` | 278 | `AgentRunner.run` | **32** | **P1** |
| `teaagent/llm/_extract.py` | 8 | `_extract_openai_content` | **27** | **P2** |
| `teaagent/memory/failure_card.py` | 361 | `FailureCardStorage.apply_auto_invalidation` | **27** | **P2** |
| `teaagent/llm_conformance/_runner.py` | 160 | `_run_tiered_provider` | **26** | **P2** |

**`_handle_tui_command` (CC=225)** is a 937-line single function acting as a command router. Every new TUI command adds another branch. Immediate remedy: replace with a dispatch dict `{"/command": handler_fn}` mapping and extract each branch into its own handler. This function also has a maintainability grade of C at the file level.

**`_run_chat_agent_impl` (CC=38)** is the core chat loop. It is also the location of the P0 CG-01 result-handling bug. Its complexity makes the bug hard to locate and fix. Split into: `_build_context`, `_execute_turn`, `_handle_tool_calls`, `_finalize_response`.

**`AgentRunner.run` (CC=32)** controls the main agent execution loop. Split into phases: `_pre_run_checks`, `_execute_loop`, `_finalize_run`.

### 3b. D-grade functions — schedule for refactor (P2)

| File | Line | Function | CC |
|---|---|---|---|
| `teaagent/swarm.py` | 533 | `SwarmManager.execute_swarm` | 25 |
| `teaagent/tui/__init__.py` | 202 | `TeaAgentTUI._print_state_panel` | 26 |
| `teaagent/subagents/_isolation.py` | 112 | `prepare_subagent_isolation` | 21 |
| `teaagent/chat_agent.py` | 66,102 | `ChatAgentConfig` / `from_root` | 22/21 |
| `teaagent/subagents/_loader.py` | 16 | `load_subagent_defs` | 22 |
| `teaagent/acp_adapter.py` | 145 | `ACPServer.session_prompt` | 23 |
| `teaagent/tsb_format.py` | 422 | `TSBVerifier.verify` | 23 |

### 3c. Files with low Maintainability Index (P2)

Radon MI grade C means "hard to maintain":

| File | MI Grade |
|---|---|
| `teaagent/automations.py` | C |
| `teaagent/tui/__init__.py` | C |
| `teaagent/tui/_commands.py` | C |
| `teaagent/cli/_handlers/_doctor.py` | C |
| `teaagent/cli/_handlers/_ergonomics.py` | C |
| `teaagent/cli/_handlers/_agent.py` | C |
| `teaagent/ergonomics/_approval_state.py` | C |

---

## 4. Dead Code & Unreachable Code

### 4a. Unreachable code (P1 / QW)

| File | Line | Description |
|---|---|---|
| `teaagent/budget_monitor.py` | 104 | Code after `return` — dead branch |
| `teaagent/cli/_handlers/_ergonomics.py` | 1336 | Code after `while True:` with no `break` path |
| `tests/test_p0_harness.py` | 171 | Code after `return` in test — test assertions unreachable |

### 4b. Unused variables (QW)

| File | Line | Variable | Risk |
|---|---|---|---|
| `teaagent/session.py` | 134 | `compaction_manager` | Object created but never used — probable logic gap |
| `teaagent/consensus.py` | 1124 | `cancelled_by` | Assigned but not propagated to result |
| `teaagent/subagents/_approval_queue.py` | 379 | `denied_by` | Same pattern — decision context lost |
| `teaagent/heartbeat.py` | 34 | `exc_tb`, `exc_val` | Context manager params — use `_` if intentional |
| `teaagent/tui/_completion.py` | 141 | `complete_event` | prompt_toolkit callback parameter, use `_` |

`session.py:134` (`compaction_manager` created but discarded) and `consensus.py:1124` (`cancelled_by` not propagated) are the most suspicious — these may be logic gaps rather than style issues.

---

## 5. Error Handling Audit

### 5a. Swallowed exceptions — `except Exception: pass` (P1)

These silently discard errors, making failures invisible in production logs:

| File | Line | Context |
|---|---|---|
| `teaagent/cli/_handlers/_chat.py` | 370 | Chat message dispatch — errors become silent no-ops |
| `teaagent/cli/_handlers/_chat.py` | 771 | File watcher teardown |
| `teaagent/cli/_handlers/chat_repl.py` | 352 | REPL loop — exceptions in user commands silently swallowed |
| `teaagent/cli/_handlers/_agent.py` | 460 | Agent start path |
| `teaagent/cli/_handlers/chat_completion.py` | 67 | Completion handler |
| `teaagent/code_analysis/_client.py` | 44 | LSP client response |

Remedy: at minimum log the exception at `WARNING` level before `pass`. Prefer raising a specific error or returning an error sentinel.

### 5b. Broad `except Exception` with log-and-continue (~50 locations, P2)

These are preferable to bare `pass` but still too broad. Top candidates for narrowing:

| File | Line | Should catch |
|---|---|---|
| `teaagent/agent_factory.py` | 48 | Import errors — catch `ImportError` only |
| `teaagent/backend_registry.py` | 31, 37, 46, 52 | Backend initialisation — catch specific init errors |
| `teaagent/external_backends.py` | 238, 248, 279, 300 | HTTP/subprocess errors |
| `teaagent/consensus.py` | 1225 | `except BaseException` — never catch `BaseException` outside shutdown |
| `teaagent/swarm.py` | 277, 703, 718, 812 | Task execution — loses error type |

`teaagent/consensus.py:1225` is the only `except BaseException` in the codebase. This catches `SystemExit` and `KeyboardInterrupt`. Remove or narrow to `Exception`.

### 5c. Import errors swallowed at startup (P2)

`teaagent/plugins.py:151` — `except Exception as exc: logger.warning(…)` during plugin load. This means a broken plugin silently degrades functionality. Consider a mode where plugin load errors fail loudly unless `--permissive-plugins` is set.

---

## 6. Type Hints Coverage

**Summary:** 742 of 2,928 functions/methods (~25%) are missing return type annotations.

### 6a. Critical public API — missing return types (P2)

| File | Line | Function | Should return |
|---|---|---|---|
| `teaagent/runner/_core.py` | 278 | `AgentRunner.run()` | `FinalAnswer` |
| `teaagent/tools.py` | 186 | `ToolRegistry.execute()` | `dict[str, Any]` |
| `teaagent/tools.py` | 124 | `ToolRegistry.register()` | `None` |
| `teaagent/chat_agent.py` | 419 | `_run_chat_agent_impl()` | `FinalAnswer` |
| `teaagent/approval_manager.py` | 651 | `ApprovalManager.assert_allowed()` | `None` |
| `teaagent/policy.py` | 531 | `parse_permission_mode()` | `PermissionMode` |
| `teaagent/subagents/_manager.py` | 76 | `SubagentManager.run_subagent()` | `SubagentSession` |

### 6b. Missing parameter type hints — key hotspots (P2)

`teaagent/acp_adapter.py:145` — `ACPServer.session_prompt()` has 25 local variables with no type annotations, making static analysis blind to type errors in the most complex method of the adapter.

`teaagent/chat_agent.py:102` — `ChatAgentConfig.from_root()` has complex config-building logic with no annotated parameter types.

### 6c. Recommended approach

Add types incrementally starting from the public API surface (`runner`, `tools`, `approval_manager`, `policy`). Use `mypy --strict teaagent/runner teaagent/tools` as a gate. Do not annotate private/internal helpers first.

---

## 7. Architectural Debt

### 7a. CG-16: Test suite validates mock behaviour, not real integration (P1)

**82 test files** use `MagicMock`, `@patch`, or `monkeypatch`. This means the test suite primarily validates that mocked collaborators are called correctly — not that the real integration works.

Worst offenders by mock density:
| File | Mock count |
|---|---|
| `tests/test_cli_chat.py` | 37 |
| `tests/test_low_coverage_modules.py` | 17 |
| `tests/test_tui.py` | 12 |
| `tests/test_external_backends.py` | 6 |
| `tests/integration/test_plugins.py` | 6 |

**Root cause:** The chat agent, TUI, and runner tightly couple I/O, LLM calls, and business logic — making real integration tests hard to write without mocks.

**Remedy (phased):**
1. Introduce a `FakeLLMAdapter` that returns scripted responses from fixtures (no `MagicMock`).
2. Replace mock-heavy tests in `test_cli_chat.py` with `FakeLLMAdapter`-driven tests.
3. Reserve `@patch` only for OS-level side effects (file I/O, signals, network).

### 7b. CG-17: Acceptance tests use `@patch` (P1)

24 acceptance test files under `tests/acceptance/` use `@patch`, defeating their purpose. Acceptance tests should exercise the full system path. Files:

`test_agent_undo_cli_flow.py`, `test_approval_root_cli_flow.py`, `test_automation_budget_caps_flow.py`, `test_consensus_flow.py`, `test_first_hour_e2e_flow.py`, `test_subagent_*` (7 files), etc.

Remedy: stand up real in-process stubs (fake LLM, temp git repos, local SQLite) instead of patching collaborators.

### 7c. `swarm.py` private-member access across class boundaries (P2)

`swarm.py` directly accesses `._task`, `._batch_index`, `._parent_run_id`, `._original_branch` on peer objects across 15+ call-sites. This tight coupling means any rename of those attributes in their owning class silently breaks swarm logic. Expose these as read-only properties or named tuples.

### 7d. Scattered in-function imports (P2)

Multiple modules defer standard-library imports inside function bodies, presumably to avoid circular imports at module load time. This pattern is fragile and should be resolved by restructuring the import graph. Primary offenders:

| File | Reimported symbols inside functions |
|---|---|
| `teaagent/swarm.py` | `threading`, `time`, `teaagent.subagents._manager`, `teaagent.tournament.benchmark`, `teaagent.control_plane_bridge`, `teaagent.subagent_run_context` |
| `teaagent/acp_adapter.py` | `ChatAgentConfig`, `RunStore`, `create_llm_adapter`, `parse_permission_mode`, `DecisionContentStreamer`, 8 others |
| `teaagent/hooks.py` | `shlex`, `fnmatch`, `teaagent.prompt.load_project_instructions` |
| `teaagent/coordinator.py` | `json` (twice) |
| `teaagent/plugins.py` | `teaagent.security_env.plugins_strict_audit` (three times) |

Remedy: audit and resolve circular import cycles using `__init__.py` restructuring or a `TYPE_CHECKING` guard.

### 7e. `teaagent/__init__.py` wrong-import-position (P2)

Pylint C0413 fires on every import in the root `__init__.py` (50+ lines). The file mixes a `try/except ImportError` block at the top with unconditional imports after it. This is legitimate for optional-dependency guarding but pollutes static analysis. Structure as: all unconditional imports first, then guarded optional imports.

### 7f. `plugins.py:61` — AttributeError risk (P2)

```python
ep_map = importlib.metadata.entry_points()
group = ep_map.get('teaagent.plugins', [])  # EntryPoints has no .get()
```
`importlib.metadata.entry_points()` returns an `EntryPoints` object (Python 3.12+) that does **not** have a `.get()` method. Use `entry_points(group='teaagent.plugins')` directly. This will raise `AttributeError` at runtime on Python 3.12+.

---

## 8. Naming & Clarity

### 8a. Clear naming violations (P2)

| File | Line | Name | Problem | Better |
|---|---|---|---|---|
| `teaagent/swarm.py` | 226 | `HEARTBEAT_TICK_INTERVAL` (local) | Screaming-snake in local scope — looks like a module constant but dies on function exit | Move to module level as actual constant |
| `teaagent/graphqlite_store.py` | 53 | `sys` (local reimport) | Shadows module-level `sys` — confusing in a debugger | Remove reimport |
| `teaagent/hooks.py` | 225, 263, 302, 334, 467 | `arguments`, `result` (unused params) | Dead parameters in hook signatures — document or remove | Prefix with `_` |
| `teaagent/coordinator.py` | 108 | `elif` after `return` | Unnecessary `elif` increases indent nesting without logical need | Remove `el` from `elif` |

### 8b. Long parameter lists (P2)

Functions with >5 positional parameters make call-sites hard to read and test:

| File | Line | Function | Params |
|---|---|---|---|
| `teaagent/swarm.py` | 368 | `SwarmManager.__init__` | 11 |
| `teaagent/swarm.py` | 186 | `SwarmWorker.__init__` | 6 |
| `teaagent/sigstore_signer.py` | 122 | `sign_artifact` | 7 |
| `teaagent/memory_legacy.py` | 73, 396 | `MemoryEntry.__init__`, `update_memory` | 6 each |

Remedy: group related parameters into dataclasses or `TypedDict` config objects.

---

## 9. Documentation Gaps

### 9a. Core execution path — no docstrings (P2)

| File | Function | Why it matters |
|---|---|---|
| `teaagent/runner/_core.py:278` | `AgentRunner.run()` | Entry point for all agent execution — no contract documented |
| `teaagent/runner/_core.py:56` | `AgentRunner.__init__()` | Constructor dependencies are non-obvious |
| `teaagent/chat_agent.py:419` | `_run_chat_agent_impl()` | Core chat loop, location of P0 bugs CG-01/CG-02 |
| `teaagent/tools.py:186` | `ToolRegistry.execute()` | Tool dispatch contract undocumented |
| `teaagent/approval_manager.py:651` | `ApprovalManager.assert_allowed()` | Security boundary — no description of raise conditions |
| `teaagent/subagents/_manager.py:76` | `SubagentManager.run_subagent()` | Subagent lifecycle undocumented |

### 9b. Module-level docstrings missing (P2)

Modules without any module docstring (first non-import line is code):
`teaagent/runner/_core.py`, `teaagent/tools.py`, `teaagent/approval_manager.py`, `teaagent/policy.py`, `teaagent/subagents/_manager.py`, `teaagent/chat_agent.py`, `teaagent/tui/__init__.py`, `teaagent/tui/_commands.py`.

---

## 10. Prioritised Refactoring Roadmap

### Tier 0 — Quick Wins (< 1 hour each)

| ID | Task | File:Line | Effort |
|---|---|---|---|
| QW-01 | Remove 9 unused `nonlocal` declarations | `_chat.py:690,765,815`, `chat_repl.py:282,346,395` | 15 min |
| QW-02 | Fix 3 undefined `__all__` symbols | `__init__.py:278,282,439` | 10 min |
| QW-03 | Remove dead `encode_dss_signature` import | `oauth21/_types.py:10` | 5 min |
| QW-04 | Add `noqa: F401` + inline comment to llm & workspace_tools `__init__.py` | `llm/__init__.py`, `workspace_tools/__init__.py` | 15 min |
| QW-05 | Remove unreachable code blocks | `budget_monitor.py:104`, `_ergonomics.py:1336`, `test_p0_harness.py:171` | 20 min |
| QW-06 | Fix `HEARTBEAT_TICK_INTERVAL` to module-level constant | `swarm.py:226` | 5 min |
| QW-07 | Fix reimports of `threading`/`time` inside swarm functions | `swarm.py:213,214,535` | 10 min |
| QW-08 | Replace logging f-strings with lazy `%s` format | `swarm.py`, `coordinator.py`, `plugins.py`, `acp_adapter.py` | 20 min |
| QW-09 | Fix `plugins.py:61` `EntryPoints.get()` → `entry_points(group=…)` | `plugins.py:61` | 10 min |
| QW-10 | Add `# noqa: B608` comments to safe SQL f-strings with explanation | `context_bus.py:460`, `schema_migration.py:92` | 10 min |
| QW-11 | Replace `/tmp/` literal with `tempfile.gettempdir()` | `tsb_format.py:86` | 5 min |
| QW-12 | Prefix unused context-manager params with `_` | `heartbeat.py:34`, `tui/_completion.py:141`, `hooks.py:225,263,302,334,467` | 15 min |
| QW-13 | Eliminate `elif` after `return` | `coordinator.py:108` | 5 min |

### Tier 1 — Sprint (1–3 days each)

| ID | Task | Rationale | File | Effort |
|---|---|---|---|---|
| S-01 | **Decompose `_handle_tui_command` (CC=225)** | Single function with 225 branches; every new command adds risk | `tui/_commands.py:38` | 2 days |
| S-02 | **Decompose `_run_chat_agent_impl` (CC=38)** | Location of P0 CG-01 bug; untestable as monolith | `chat_agent.py:419` | 2 days |
| S-03 | **Decompose `AgentRunner.run` (CC=32)** | Core agent loop with no ability to unit-test phases | `runner/_core.py:278` | 1 day |
| S-04 | **Fix swallowed exceptions in CLI handlers** | Silent failures in chat/completion paths mask user-visible bugs | `_chat.py:370,771`, `chat_repl.py:352`, `_agent.py:460`, `chat_completion.py:67` | 0.5 day |
| S-05 | **Centralise `urllib.request.urlopen` → HTTP wrapper** | 14 call-sites with no scheme validation or redirect control | 14 files | 1 day |
| S-06 | **Add `# noqa: B102` + sandbox invariant comment to `exec()`** | `exec()` use is intentional but undocumented — risk in code review | `code_mode/_child_process.py:77` | 0.5 day |
| S-07 | **Fix `session.py:134` unused `compaction_manager`** | Probable logic gap — object created but its side-effects may not fire | `session.py:134` | 0.5 day |
| S-08 | **Fix `consensus.py:1124` `cancelled_by` not propagated** | Decision context is lost — audit trail incomplete | `consensus.py:1124` | 0.5 day |
| S-09 | **Replace `except BaseException` at `consensus.py:1225`** | Catches `SystemExit`/`KeyboardInterrupt` — masks forced termination | `consensus.py:1225` | 0.5 day |
| S-10 | **Add return type hints to 7 core public functions** | Enables mypy, self-documents contracts | See §6a | 1 day |

### Tier 2 — Cycle (1–2 weeks, major restructures)

| ID | Task | Rationale | Effort |
|---|---|---|---|
| M-01 | **Introduce `FakeLLMAdapter` and remove MagicMock from `test_cli_chat.py`** (CG-16) | 37 mocks validate mock wiring, not system behaviour | 3 days |
| M-02 | **Rework 24 acceptance tests to use real stubs** (CG-17) | Acceptance tests that patch collaborators cannot catch integration regressions | 5 days |
| M-03 | **Resolve circular import graph** (eliminate in-function imports) | `swarm.py` and `acp_adapter.py` have 10+ deferred imports each | 3 days |
| M-04 | **Group long parameter lists into config dataclasses** | `SwarmManager.__init__` (11 args), `sigstore_signer.sign_artifact` (7 args) | 2 days |
| M-05 | **Add docstrings to core execution path** | `run()`, `execute()`, `assert_allowed()`, `run_subagent()` | 1 day |
| M-06 | **Narrow broad `except Exception` to specific types in 10 highest-risk locations** | Improves debuggability and prevents silent degradation | 2 days |
| M-07 | **Expose `swarm.py` private fields as properties** | 15+ cross-class private accesses make refactoring brittle | 1 day |
| M-08 | **Restructure `teaagent/__init__.py` import ordering** | 50+ C0413 warnings; unconditional imports after guarded block confuses static analysis | 1 day |


---

## Implementation status (2026-06-27)

Tracked against `docs/retrospective/06-action-register.md` (**A-P2-6**, **S-P2-5**) and harness goals in `AGENTS.md` (thin harness, centralized HTTP, governed tests).

| ID | Status | Evidence |
|---|---|---|
| S-01 | ✅ Done | `teaagent/tui/_commands.py` dispatch table (`_COMMAND_DISPATCH`) |
| S-02 | ✅ Done | `chat_agent.py` helpers (`_resolve_audit_logger`, `_execute_chat_run`, …) |
| S-03 | ✅ Done | `runner/_core.py` → `_execute_run_loop()` |
| S-05 | ✅ Done | `teaagent/http_utils.py` (`safe_urlopen` / `safe_urlopen_request`); callers migrated |
| S-P2-5 | ✅ Done | `config_lint` dev-signature warning + `notify.py` `shell=False` docs |
| QW-02 | ✅ Done | Lazy exports via `teaagent/_lazy_exports.py` (no broken `__all__` symbols) |
| QW-06, QW-07 | ✅ Done | `HEARTBEAT_TICK_INTERVAL` module constant; no in-function `threading`/`time` reimports in `swarm.py` |
| QW-10 | ✅ Done | `# nosec B608` on safe SQL f-strings (`schema_migration`, `context_bus`) |
| QW-11 | ✅ Done | `tempfile.gettempdir()` in `tsb_format.py` |
| 1c | ✅ Done | Explicit imports in `git_sandbox.py` shim (no wildcard import) |
| M-01 | 🟡 Partial | `FakeLLMAdapter` shipped (`teaagent/llm/_fake_adapter.py`); `tests/test_cli_chat.py` no longer mock-heavy |
| M-02 | ✅ Done | Acceptance tests use `FakeLLMAdapter`, `RunResult`/`FinalAnswer`, and direct manager stubs; narrow `patch` only for `run_chat_agent` / `Path.home` boundaries |
| S-06 | ✅ Done | `# noqa: B102` on both code_mode exec sites |
| S-04 | ✅ Done | CLI handlers log swallowed paths: `_chat.py`, `chat_commands.py`, `chat_completion.py`, `agent_misc.py`, `_agent/preflight.py` |
| S-07 | ✅ Done | `ChatSession.compress_returned_topic` uses `CompactionManager.compactor.compact_chat_history` |
| S-08 | ✅ Done | `cancelled_by` on `ConsensusState`; `consensus cancel` CLI; `denied_by` propagated on subagent denials |
| S-09 | ✅ Done | No production `except BaseException` in consensus path (removed/narrowed) |
| S-10 | ✅ Done | Return types on core APIs: `AgentRunner.run` → `RunResult`, `ToolRegistry.execute` → `dict`, `parse_permission_mode` → `PermissionMode`, `run_subagent` → `dict[str, Any]`, `assert_allowed` → `None` |
| M-05 | 🟡 Partial | Docstrings added to `run()`, `execute()`, `run_subagent()` |
| M-03–M-08 | ⬜ Open | See Tier 2 table above for remaining cycle work |


---

## Appendix: Tool Invocations

```
.venv/bin/flake8 teaagent/ tests/ --max-line-length=120 --extend-ignore=E501,W503
.venv/bin/bandit -r teaagent/ -f txt --severity-level medium
.venv/bin/radon cc teaagent/ --min C --show-complexity --average
.venv/bin/radon mi teaagent/ --min B
.venv/bin/vulture teaagent/ tests/ --min-confidence 80
.venv/bin/pylint teaagent/ --disable=C0114,C0115,C0116,R0903,R0801,W0107 --max-line-length=120
```
