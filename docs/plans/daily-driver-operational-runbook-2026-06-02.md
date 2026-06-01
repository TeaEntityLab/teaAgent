# Daily-Driver Operational Runbook
# 2026-06-02

This runbook is for maintainers and heavy users running TeaAgent daily.

## Before a run

1. Confirm current repository root.
2. Check `git status`.
3. Choose the surface:
   - `teaagent chat` for conversational coding.
   - `teaagent tui` for cockpit/status work.
   - `teaagent agent run` for non-interactive audited work.
4. Choose permission mode.
5. Decide max cost or provider if spend matters.

## During a run

Watch for:

- Run id.
- Approval prompts.
- Changed files.
- Cost display source.
- Lifecycle wording.
- Any command that promises background/resume behavior.

If something looks ambiguous, pause and inspect with `agent show` or `git status`.

## After a run

1. Inspect final answer.
2. Inspect changed files.
3. Inspect run/audit evidence when the task mattered.
4. Run relevant tests.
5. Run manual smoke for TUI/chat/agent changes.
6. Update docs if user-visible semantics changed.

## If cost looks wrong

- Treat TUI `$0.00` as non-authoritative until TICKET-12 lands.
- Check run summary.
- Check provider dashboard when spend matters.
- File or link the run id in the issue.

## If root looks wrong

- Stop before approving writes.
- Record visible root and command used.
- Restart with explicit `--root .`.
- Check whether saved TUI state overrode CLI root.

## If approval looks too broad

- Reject.
- Ask for narrower path scope.
- Avoid broad approval for delete, write, git, or shell-like operations.

## If resume fails

- Run `teaagent agent show <run_id>`.
- Use `teaagent agent interactive-review <run_id>` if changes exist.
- Do not pass a run id as a task to `agent run --background`.
- Capture the error and run id for TICKET-16 follow-up.

## If undo is needed

- Inspect `git status`.
- Identify whether the path uses undo journal or checkpoint restore.
- Prefer journal undo for preserving unrelated edits.
- If unsure, make a manual patch or backup before recovery.

## Release-day daily-driver check

Run or verify:

- Docs consistency checks.
- Focused pytest docs/acceptance tests.
- Manual QA smoke checklist.
- Current-status page updated.
- Known-issues page updated if any trust-sensitive behavior changed.
