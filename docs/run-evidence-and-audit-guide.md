# Run Evidence And Audit Guide
# As of 2026-06-02

This guide helps a user answer: "What did the agent actually do?"

## Find a run

Use:

```bash
teaagent agent runs
```

Record the run id before resuming, undoing, approving, or reporting a bug.

## Read the summary

Use:

```bash
teaagent agent show <run_id>
```

Look for:

- Final status.
- Task text.
- Changed files.
- Approval state.
- Tests or verification claims.
- Cost and provider metadata when available.

## Inspect audit events

An audit event should answer:

- What happened?
- Which run did it belong to?
- Which tool or command was involved?
- What authority was used?
- What result was recorded?

If a final answer claims success but no audit/result/verification event supports it,
treat the claim as unverified.

## Changed files

Before accepting a run:

1. Inspect `git status`.
2. Inspect diffs for files the task should touch.
3. Look for unrelated files.
4. Verify generated files are intentional.
5. Run relevant tests or the manual smoke checklist.

## Approvals

Approval evidence should show:

- Approval id.
- Tool call id.
- Tool name.
- Path or resource scope.
- Decision and timestamp.

Missing approval evidence is a governance bug for destructive or write-capable tools.

## Tests and validation

Separate three layers:

| Layer | Meaning |
|-------|---------|
| Claimed | The agent says it ran or checked something. |
| Observed | Logs, diffs, or audit events show something happened. |
| Verified | A test, smoke check, or human review confirms the behavior. |

## Known gaps

- Some existing docs are historical and may describe fixed or shifted findings.
- Some tests verify helper state instead of active user paths.
- TUI cost display can contradict actual provider spend.
- Suspend/resume evidence is incomplete for some paths.

## Daily acceptance rule

A run is daily-driver acceptable when the final answer, audit events, changed files, and
verification evidence tell the same story.
