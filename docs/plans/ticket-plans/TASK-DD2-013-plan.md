# TASK-DD2-013: Harden Headless TUI Path Tests

**Priority:** P1
**Status:** Fixed — 17 headless TUI test methods exist in `tests/acceptance/test_headless_tui.py` (419 lines) covering cost, root, initial task, undo, approval prompt, and more. Core scope delivered (commit df31010). Verified by comprehensive audit (see docs/work-log/roadmap-work-items-2026-06-04.md).
**Primary files:** `tests/test_tui.py`, `teaagent/tui/__init__.py`

## Problem

Several TUI risks were hard to detect because tests verified helper state or formatting
instead of driving the active command path. Headless TUI tests should behave more like a
user typing commands.

## Scope

- Create reusable headless TUI fixtures that drive command input.
- Assert user-visible output and backing state.
- Cover initial task, root load, cost, budget, compact, undo, and approval prompts.
- Mark known issues explicitly instead of hiding them behind helper tests.

## Acceptance criteria

- TUI cost test fails if `_run_agent_task()` does not add real result cost.
- Root test fails if `_load_tui_state()` overwrites explicit root.
- Initial-task test fails if parser/handler/TUI handoff drops the task.
- Tests do not set the final state they claim to prove.

## Verification

```bash
python3 -m pytest tests/test_tui.py
```

## Risks

- Headless tests can become brittle if they assert decorative text.
- Keep assertions focused on trust-sensitive output and state.
