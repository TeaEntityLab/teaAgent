# TASK-DD2-005: Repair Git Sandbox Lifecycle

**Priority:** P1
**Status:** Partially Fixed — core `_agent.py` fix delivered (removed sandbox re-creation in commit 4cc6c51); `git_sandbox.py` not modified. Broader ACs (run evidence persistence, stash restoration, help text alignment) need verification before full close. See verification audit at docs/work-log/roadmap-work-items-2026-06-04.md.
**Primary files:** `teaagent/cli/_handlers/_agent.py`, `teaagent/git_sandbox.py`, `tests/test_git_tools.py`

## Problem

Git sandbox lifecycle state can be split across a pending run id and a final run id.
If a new sandbox object is created after `start()`, branch/original-branch state can be
lost or misreported during merge/discard/keep prompts.

## Scope

- Preserve the started sandbox object through run completion.
- Persist sandbox branch, original branch, stash id, and resolution status in run evidence.
- Avoid creating a second sandbox object unless full state is rehydrated.
- Align help text with actual default sandbox behavior.

## Acceptance criteria

- A sandboxed run can merge, discard, or keep its branch without losing original branch state.
- Dirty-worktree auto-stash is restored only after explicit resolution.
- Run evidence records sandbox lifecycle state.
- Help and docs do not imply opt-in when runtime defaults differ.

## Verification

```bash
python3 -m pytest tests/test_git_tools.py
python3 -m pytest tests/test_cli_execution.py -k sandbox
```

## Risks

- Branch state bugs can strand user work.
- Auto-stash behavior can hide local edits.
- Renaming pending branches after run creation can create confusing history.
