# UX Stability Contract
# As of 2026-06-02

This contract turns the daily-driver audits into product rules. It is maintainer-facing,
but the priority is operator trust.

## No silent success

A submitted task must do one of three things:

1. Execute and show the result.
2. Reject with a clear reason.
3. Stop on approval or planning gate with a clear next action.

It must never accept input and quietly do nothing.

## No decorative state

State displayed to users must be real or clearly marked unknown.

Decorative state examples:

- `$0.00` cost when no ledger is connected.
- "background" when work is not continuing.
- "resume" instructions when task context was not persisted.
- A green status generated from a helper path, not the runtime path.

## No misleading lifecycle copy

Reserved words:

| Word | Must mean |
|------|-----------|
| Running | Work is actively executing. |
| Suspended | Work stopped and can be inspected by run id. |
| Background | Work continues outside the foreground UI. |
| Resume | Task context and observations are restored. |
| Review | Human can inspect current evidence before accepting or continuing. |
| Undo | A documented recovery scope will be applied. |

## Surface parity

Trust-sensitive facts must not depend on the surface:

- Task submitted.
- Answer displayed.
- Cost accumulated.
- Budget enforced.
- Undo scope.
- Approval scope.
- Run lifecycle.
- Root path.

## Required manual smoke

Run [processes/daily-driver-manual-qa-smoke.md](processes/daily-driver-manual-qa-smoke.md)
before releasing changes that touch:

- `teaagent chat`
- `teaagent tui`
- `teaagent agent run`
- approval prompts
- undo/recovery
- run store or audit logs

## Release blockers

Block release when:

- A path accepts a task but drops it.
- A cost display shows false zero after real work.
- A destructive or write-capable approval lacks exact scope.
- A resume command cannot find the task it claims to resume.
- TUI and CLI disagree on an already-documented trust-sensitive behavior.
- Tests pass only because they injected the state they claim to prove.

## Product rule

When forced to choose between a less impressive but accurate interface and a polished
interface that overclaims, choose accuracy.
