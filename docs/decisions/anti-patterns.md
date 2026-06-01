# Anti-Patterns to Avoid

Patterns that were tried (or observed in early versions) and caused problems.  
Each entry explains what the pattern is, what went wrong, and what to do instead.

---

## 1. Two Classes Named the Same Thing in Different Modules

**Pattern:** Having both `teaagent/approval_manager.py::ApprovalManager` and a second `ApprovalManager` in a different module, with slightly different interfaces.  
**What went wrong:** Callers imported the wrong one. The circular import between `approval_manager.py` and `policy.py` arose because both classes imported each other's types. Bugs in one class were fixed without fixing the other, causing inconsistent behaviour depending on which import path was active.  
**What to do instead:** One class, one module. If two classes share concepts, extract shared types into a `_types.py` module that neither depends on the other. (ADR-0010, ADR-0011)

---

## 2. Module-Level Mutable Globals for State

**Pattern:** Using a module-level `_REGISTRY: dict = {}` as the canonical registry, mutated by `register_backend()` calls at import time.  
**What went wrong:** Import-order sensitivity — if module A is imported before module B, B's registrations may arrive after A has already queried the registry. In tests, registry state bleeds across test cases unless explicitly cleared.  
**What to do instead:** Pass registry objects explicitly via constructor injection. Use `pytest` fixtures to create a fresh registry per test. (ADR-0013)

---

## 3. Lambda Closures for Tool Registration

**Pattern:** Registering tools as lambda closures that capture variables from the registration scope:
```python
for tool in tools:
    registry.register(tool.name, lambda args: tool.execute(args))
```
**What went wrong:** The classic Python closure-in-loop bug — all lambdas capture the same `tool` variable, which ends up being the last item in the loop. All registered tools call the last tool's `execute`. This caused wrong tool dispatch in early tool registration code.  
**What to do instead:** Use `functools.partial` or define a proper factory function with explicit binding. (ADR-0016)

---

## 4. Calling `asyncio.set_event_loop()` from Approval/Policy Code

**Pattern:** Approval and policy code that needed to run an async function would call `asyncio.set_event_loop(asyncio.new_event_loop())` and then `loop.run_until_complete(coro)`.  
**What went wrong:** This corrupted the event loop state for any caller that was already inside an async context (e.g., a Jupyter notebook, an async test runner, or a `prompt-toolkit` async prompt session). The next `await` in the caller's context raised `RuntimeError: This event loop is already running`.  
**What to do instead:** Use the run-coroutine-sync bridge pattern: check if there is a running loop; if yes, submit to a `ThreadPoolExecutor`; if no, call `asyncio.run()`. Never call `asyncio.set_event_loop()` from library code. (ADR-0018)

---

## 5. Swallowing Exceptions with Bare `except`

**Pattern:**
```python
try:
    result = tool.execute(args)
except:
    result = None
```
**What went wrong:** Silent failures. A tool that raised `PermissionError` because the workspace was read-only would return `None`, the agent would receive an empty result, and the run would continue as if the tool succeeded. Audit events were never emitted for the failure.  
**What to do instead:** Catch specific exception types. Re-raise or emit an audit event for unexpected exceptions. Use `TeaAgentError` subclasses with structured error context so the agent can reason about the failure. (ADR-0014)

---

## 6. Hardcoded Configuration Keys as String Literals

**Pattern:** Accessing configuration with `config["permission_mode"]` or `os.getenv("TEAAGENT_PERMISSION_MODE")` at arbitrary call sites throughout the codebase.  
**What went wrong:** Typos in key names silently returned `None` instead of failing loudly. When renaming a config key, `grep`-based refactoring missed some occurrences. The config documentation was always stale because the keys were never centrally enumerated.  
**What to do instead:** Enumerate all config keys in `config_loader.py::CONFIG_KEYS` with types and env var names. Access configuration only through `ConfigResolver`, which validates key names. (ADR-0015 proposes a plugin extension of this)

---

## 7. Storing Approval State in the LLM Message History

**Pattern:** Early versions tracked which tools had been approved by injecting `"User approved: bash(rm -rf /tmp/work)"` messages into the LLM conversation history.  
**What went wrong:** The LLM could be prompted to claim a tool had been approved by referencing the approval message format. Approval state was not queryable programmatically — determining whether a session-wide tool approval was active required parsing message strings.  
**What to do instead:** Approval state lives in `JITApprovalState` (structured Python object), not in the LLM context. The LLM never has access to the approval state directly.

---

## 8. One Giant `chat_agent.py` Function

**Pattern:** A single `run_chat_agent()` function that owned execution, result printing, cost tracking, undo, audit emission, and session state.  
**What went wrong:** Impossible to unit-test individual behaviours (cost tracking, undo) without a full mock of the entire chat session. Divergent TUI and REPL implementations emerged because both surfaces forked the function rather than sharing it.  
**What to do instead:** `ChatSessionController` as a class that owns these concerns. Each concern (cost, undo, audit) is a method or injected collaborator. (ADR-0025)

---

## 9. Using `git checkout` for Undo

**Pattern:** The TUI's `/undo` command ran `git checkout .` to revert workspace changes.  
**What went wrong:** `git checkout .` is destructive — it reverts all unstaged changes, including changes the user made manually that were not part of the agent's run. Users lost their own work. (CG-02, tracked in daily-driver-known-issues)  
**What to do instead:** `UndoJournal` tracks exactly which file write operations the agent performed in the current iteration. Undo reverts only those specific writes using stored diffs, leaving other workspace state intact.

---

## 10. Reporting Fake Cost ($0.00) from the TUI

**Pattern:** The TUI called `run_chat_agent()` directly and did not route through the cost accumulation path in `ChatSessionController`. The `/cost` command read from a variable that was never populated.  
**What went wrong:** Users saw `$0.00` for every run, making the cost guard completely ineffective from the TUI. (CG-11, tracked in daily-driver-known-issues)  
**What to do instead:** All execution surfaces (REPL and TUI) must route through `ChatSessionController._run_agent_task()`, which accumulates real token costs. Never read cost from a local variable that bypasses the controller.

---

## 11. Per-Subagent Approval Prompts

**Pattern:** Each subagent in a swarm prompted the operator for approval independently when it needed to invoke a destructive tool.  
**What went wrong:** With 8 parallel subagents, the operator received 8 simultaneous approval prompts, all requiring immediate responses. Approval fatigue caused operators to approve all requests without reading them.  
**What to do instead:** `CentralizedApprovalQueue` aggregates all requests under the parent run ID. The operator handles a single approval UI with `approve-all`/`deny-all` semantics. (ADR-0022)

---

## 12. Skipping the Plan Gate in Workspace-Write Mode

**Pattern:** Early runs in `workspace-write` mode allowed the agent to write files without a prior plan, as long as the individual file write was approved.  
**What went wrong:** The agent made structurally incorrect changes (wrong file, wrong scope) that required multiple rounds of correction. Approval at the file-write level did not provide the operator with enough context to evaluate whether the change was appropriate.  
**What to do instead:** Plan-before-write is the default in `workspace-write` mode. The plan step shows the operator the full set of files that will be modified and the rationale, before any write occurs. `--skip-plan-check` requires an explicit operator override. (ADR-0023)

---

## 13. Importing at the Top of Every Module Unconditionally

**Pattern:** Every module importing heavy optional dependencies (`prompt_toolkit`, `wasmer`, `cryptography`) at the top level, even when the relevant feature was not in use.  
**What went wrong:** Cold-start time increased with every added optional feature. A simple `teaagent run --help` imported the TUI stack, the WASM runtime, and the crypto stack.  
**What to do instead:** Lazy imports inside the functions that need them, guarded by `try/ImportError`:
```python
def get_tui():
    try:
        from prompt_toolkit import PromptSession
        return PromptSession()
    except ImportError:
        raise RuntimeError("Install teaagent[tui] for TUI support")
```
Optional features should be invisible at import time.
