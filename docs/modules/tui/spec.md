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
- TUI and REPL chat share controller-backed task, result, cost, and undo semantics.
- Cost is real or unknown.
- Undo mechanism is visible.
- Every run-producing command should expose a run id.

## Residual risks

- Provider adapters can omit usage data, leaving session cost incomplete.
- Explicit-root precedence, controller routing, journal-only undo, and approval scope can
  regress if new commands bypass their shared helpers.
- Helper-only tests can miss active command-path failures; headless TUI path tests remain
  required for release evidence.
