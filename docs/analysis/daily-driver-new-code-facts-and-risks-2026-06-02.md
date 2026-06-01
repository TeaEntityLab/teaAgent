# Daily-Driver New Code Facts And Risks
# 2026-06-02

This layer records newly observed working-tree facts after the user's code improvements.
It separates "appears patched" from "verified daily-driver behavior."

## New code facts

| ID | Status | Fact | Evidence | Next action |
|----|--------|------|----------|-------------|
| CF-001 | Partially fixed | `chat_command()` now reads `args.task` and passes `initial_task` into `run_tui`. | `teaagent/cli/_handlers/_chat.py` reads `getattr(args, 'task', None)` and forwards `initial_task`. | Convert TASK-DD2-001 into verify/close with parser + TUI tests. |
| CF-002 | Partially fixed | TUI startup attempts to execute `initial_task` before entering the prompt loop. | `teaagent/tui/__init__.py` calls `_run_agent_task(initial_task)` before `while True`. | Verify visible error/result behavior and deterministic loop continuation. |
| CF-003 | Partially fixed | TUI now increments `_session_cost_cents` by `result.cost_cents`. | `teaagent/tui/__init__.py` adds the stop-gap after `run_chat_agent`. | Add active-path test, then finish controller migration. |
| CF-004 | Still active | TUI still calls `run_chat_agent` directly instead of `ChatSessionController`. | TUI `_run_agent_task` constructs `ChatAgentConfig` and invokes `run_chat_agent`. | Keep TICKET-12 full migration active. |
| CF-005 | Still active | Saved TUI state can overwrite explicit root. | `_load_tui_state()` assigns `self.root` from saved JSON unconditionally. | Fix TASK-DD2-002 first in the next code batch. |
| CF-006 | Still active | Stale `_chat.py` suspension wording still advertises attach/resume-style commands. | `_chat.py` prints attach/resume/review instructions after suspension. | Fold into lifecycle wording and stale cleanup tickets. |

## Newly discovered risks

| ID | Priority | Risk | Evidence | Recommended ticket |
|----|----------|------|----------|--------------------|
| RL-NEW-01 | P1 | `daily --dry-run` and read-only preflight can still initialize `.teaagent` state. | Dry-run calls `preflight()` and `build_daily_brief()` without a readonly invariant. | TASK-DD2-008 |
| RL-NEW-02 | P1 | `ContextPack.read_only` can report `true` even when the builder was called with `readonly=False`. | `ContextPack` defaults `read_only=True`; `build_context_pack()` does not pass `readonly`. | TASK-DD2-009 |
| RL-NEW-03 | P0 | Pinned-file storage joins `root / file_path` without containment checks. | `PinnedFileStorage.add()` accepts a string and validates existence after joining. | TASK-DD2-010 |
| RL-NEW-04 | P1 | Corrupt memory/run JSON can silently disappear from daily cockpit state. | Memory catalog skips bad JSONL; run summaries return `None` on JSON errors. | TASK-DD2-011 |
| RL-NEW-05 | P2 | Failure-card matching can be sticky due to raw word overlap. | Matching scores any common split word and can inject prior failure text. | TASK-DD2-012 |

## Interpretation

The project is moving in the right direction: the highest-friction TUI/chat issues are
getting small patches. The new risk is confidence drift: docs and tickets must now
distinguish active defects from patched-but-not-verified behavior.

## Recommended closure rule

Do not mark a daily-driver issue fixed until:

1. The active command path is tested.
2. The user-facing doc no longer contradicts runtime behavior.
3. Manual smoke covers the terminal-visible behavior if the surface is interactive.
4. The review index names the superseding file.
