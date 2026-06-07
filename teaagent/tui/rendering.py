from __future__ import annotations

from pathlib import Path
from typing import Optional

from teaagent.policy import PermissionMode

from .core import TeaAgentTUI
from .state import InputFn

HELP_TEXT = """Commands:
  help                      Show this help.
  setup [write-env]         Guided first-session workspace setup (same as teaagent setup).
  doctor                    Check GraphQLite runtime.
  provider <name>           Set model provider: claude, gpt, gemini, openrouter, ollama, vllm, opencodezen-go, workers-ai, aigateway.
  model <name|default>      Set or clear model override.
  route-model <on|off>      Enable or disable task-based model routing.
  route <task>              Preview model route for a task.
  complexity <task>         Analyze task complexity (high/medium/low).
  estimate <task>           Estimate token budget for a task.
  root <path>               Set workspace root for agent tasks.
  destructive <on|off>      Allow or block destructive workspace tools.
  progress <on|off|run_id>   Toggle audit-event progress lines or show run progress details.
  stream <on|off>           Stream model output token-by-token during ask runs.
  subagent <on|off>         Expose the 'subagent' tool so the model can delegate sub-tasks.
  chat <on|off>             Enable or disable multi-turn chat mode with session history.
  session new               Create a new chat session.
  session list              List saved chat sessions.
  session switch <id>       Switch to another chat session.
  session clear             Clear messages in the current chat session.
  session show              Show the current chat session details.
  heartbeat <seconds>       Set heartbeat interval for ask runs. 0 disables.
  status <run_id>           Show heartbeat liveness for a persisted run.
  permission <mode>         Set permission mode: read-only, workspace-write, prompt, allow, danger-full-access.
  approve <call_id|--selector N>  Approve one destructive tool call by id or pending selector.
  unapprove <call_id>       Remove one approved call id.
  receipt <run_id>          Show human-readable run receipt including goal, cost, and audit path.
  approvals                 List approved call ids for this session.
  approvals subagents       Batch view of parallel subagent destructive-tool queue.
  approvals subagents approve|deny|approve-all|deny-all
  clarify <task>            Score task ambiguity without calling a model.
  preflight <task>          Show clarify, routing, memory, and tool plan without calling a model.
  plan <task>               Write a read-only plan artifact under .teaagent/plans.
  daily [task]              Show readiness, recent runs, harness health, and token budget.
  run <task>                Run a model-driven agent task (alias for ask).
  ask <task>                Run a model-driven agent task with workspace tools.
  ask --clarify <task>      Clarify first; stop if key details are missing.
  undo [run_id]             Restore workspace files from the last undo journal (or a run id).
  permissions               List destructive-tool approval presets for this workspace.
  mcp                       Hint for MCP doctor / serve commands (run from a shell).
  memory add <text>         Add a workspace memory entry.
  memory list               List recent workspace memories.
  memory search <query>     Search workspace memories.
  memory show <id>          Show one workspace memory.
  runs                      List recent persisted agent runs.
  show <run_id>             Show one persisted run record.
  resume <run_id>           Re-run the original task from a persisted run id.
  context list [prefix]     List workspace files for @-mentions in tasks.
  use <database>            Switch database path. Use :memory: for in-memory.
  smoke                     Create a SmokeTest node and query it.
  query <cypher>            Execute a Cypher query.
  parallel <optA> <optB>... Start parallel experiment branches for comparison.
  select <option>           Merge selected parallel experiment branch.
  cancel                    Cancel and cleanup all parallel experiment branches.
  conflict                  Enter conflict resolution mode for merge conflicts.
  o                         Accept Our version (current branch) in conflict mode.
  t                         Accept Their version (incoming branch) in conflict mode.
  n                         Next conflicted file in conflict mode.
  p                         Previous conflicted file in conflict mode.
  a                         Abort merge in conflict mode.
  pin <path>                Pin a file for live context sync (watches for changes).
  unpin <path>              Unpin a file from live context sync.
  pinned                    List all pinned files.
  compact                   Compact session context to save tokens.
  cost                      Show session cost.
  effort <low|normal|high|unlimited>  Set effort throttling level.
  budget                    Show budget and effort status.
  checkpoint                Create manual git checkpoint.
  undo [run_id]              Undo last agent edit (journal-first, checkpoint fallback).
  background                Create a suspension checkpoint (not background execution); use interactive-review/resume on the run id.
  handoff                   Alias for suspension checkpoint (same as background command).
  skill-diagnostics         Show comprehensive skill diagnostics: loaded, shadowed,
                            candidates, artifacts, output verification (JSON).
  skill-health              Show skill ecosystem health dashboard (JSON).
  exit | quit               Leave the TUI.

Slash aliases (/daily, /plan, /run, …) are accepted for the same commands.

TUI Command Reference — Controller-Backed Commands (P0-A)
  All task-execution commands delegate to ChatSessionController for unified
  result handling, cost tracking, and undo behavior.

  ask <task>                 Execute a task through ChatSessionController.
                             Cost accumulates in controller session state.
  run <task>                 Alias for ask; same controller path.
  cost  (/cost)              Display session cost from controller-owned state.
                             Reads ChatSessionController.get_session_cost().
  undo  (/undo)              Undo via controller undo journal (file-level restore).
                             Falls back to git-stash checkpoint when no journal exists.
                             Output explicitly labels which method was used:
                               - "journal undo completed" (file-level restore)
                               - "checkpoint restore completed" (git-level restore)
                               - "nothing to undo" (no journal or checkpoint)
  root <path>                Set workspace root. Controller picks up new root
                             when created; existing controller instances retain
                             their construction-time root.
  resume <run_id>            Re-run original task from a persisted run through
                             ChatSessionController.execute_task().
"""


def run_tui(
    *,
    database: str = ':memory:',
    provider: Optional[str] = None,
    model: Optional[str] = None,
    root: str | Path = '.',
    allow_destructive: bool = False,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    chat: bool = False,
    input_fn: Optional[InputFn] = None,
    run_setup: bool = False,
    setup_write_env: bool = False,
    stream: bool = False,
    subagent: bool = False,
    heartbeat_seconds: float = 0.0,
    max_iterations: int = 10,
    max_tool_calls: int = 10,
    max_subagent_depth: int = 1,
    enable_git_tools: bool = False,
    skill_search_dirs: Optional[list[str]] = None,
    memory_limit: int = 5,
    max_estimated_cost_cents: int | None = 500,
    # TASK-DD2-001: initial task from `teaagent chat "task"` positional arg
    initial_task: Optional[str] = None,
) -> int:
    tui = TeaAgentTUI(
        database=database,
        provider=provider,
        model=model,
        root=root,
        allow_destructive=allow_destructive,
        permission_mode=permission_mode,
        input_fn=input_fn,
        stream=stream,
        subagent=subagent,
        heartbeat_seconds=heartbeat_seconds,
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
        max_subagent_depth=max_subagent_depth,
        enable_git_tools=enable_git_tools,
        skill_search_dirs=skill_search_dirs,
        memory_limit=memory_limit,
        max_estimated_cost_cents=max_estimated_cost_cents,
    )
    if chat:
        tui.chat = True
        tui._chat_explicit = True
    if str(root) != '.':
        tui._root_explicit = True
    return tui.run(
        run_setup=run_setup,
        setup_write_env=setup_write_env,
        initial_task=initial_task,
    )
