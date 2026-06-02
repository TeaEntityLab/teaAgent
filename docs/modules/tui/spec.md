# tui — Behavior Specification

## Purpose

The TUI module is the operator cockpit for TeaAgent. It should expose project state,
chat/session commands, approvals, runs, cost, and recovery without changing the meaning
of core agent behavior.

## Responsibilities

- Render current root, provider, model, permission mode, and run state.
- Route user commands to stable backend/controller APIs.
- Display approval prompts and pending approvals.
- Display cost and budget only from authoritative state.
- Persist local UI preferences without overriding explicit command intent.
- Provide headless test seams for command-path verification.

## Non-responsibilities

- Owning chat semantics independently from `ChatSessionController`.
- Owning provider billing logic.
- Hiding approval scope.
- Reinterpreting run lifecycle words.
- Performing recovery without naming its scope.

## Contracts

- Explicit root wins over saved state.
- TUI chat should converge on controller-backed semantics.
- Cost is real or unknown.
- Undo mechanism is visible.
- Every run-producing command should expose a run id.

## Open risks

- Saved state root overwrite.
- Partial controller migration.
- Cost stop-gap not yet full parity.
- TUI undo scope drift.
- Tests can bypass the active TUI path.
