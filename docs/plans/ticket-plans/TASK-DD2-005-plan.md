# TASK-DD2-005: Repair Git Sandbox Lifecycle

**Priority:** P1
**Status:** Fixed (2026-06-09) — run_id pre-generated before sandbox start; squash/discard/keep resolution paths implemented; stash pop uses labeled stash ref; `git_sandbox_started` / `git_sandbox_resolved` audit events persisted; `RunEvidenceBundle.git_sandbox` extracts lifecycle state.
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
