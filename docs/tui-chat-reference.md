# TUI Chat Reference
# As of 2026-06-21

This is a focused reference for chat-like workflows inside the TUI. It is written from
the user's point of view and records the shared `ChatSessionController` contract used
by the TUI and `teaagent chat`.

## Chat mode

| Command | Intent | Current confidence |
|---------|--------|--------------------|
| `chat on` | Enable chat-oriented interaction in the TUI. | Medium |
| `chat off` | Return to command-oriented cockpit behavior. | Medium |
| `ask <prompt>` | Submit a prompt through the active TUI path. | Medium |
| `ask --clarify <prompt>` | Ask for clarification-first behavior where supported. | Medium |
| `compact` | Compact session context. | High for visible action; parity still needs guarding. |

## Session commands

| Command | Intent |
|---------|--------|
| `session new` | Start a new chat session. |
| `session list` | List available sessions. |
| `session switch <id>` | Switch to a known session. |
| `session clear` | Clear current session content. |
| `session show` | Show current session details. |

## Ask semantics

The target contract is simple:

1. A submitted task must either execute or be rejected with a clear message.
2. A successful task must print or display the answer.
3. Failure labels must describe real failure, not missing display plumbing.
4. Cost and undo should have the same meaning in TUI and REPL chat.

Current contract: task execution delegates to `ChatSessionController`; positional chat
tasks are forwarded into `run_tui(initial_task=...)` and run before the prompt loop.
Parser, handler, result display, cost, and active command-path behavior have regression
coverage.

## Cost and budget display

Target behavior:

- Session cost increases after real model work.
- Budget bars and `/budget` reflect the same session ledger.
- Provider billing, run summary cost, and user-facing display do not contradict each other.

Current behavior:

- `ChatSessionController` owns session cost for both TUI and REPL chat.
- `/cost`, `/budget`, and cockpit budget display read the controller-backed session
  ledger, with a compatibility fallback for older callers.
- A displayed session value is only as complete as the provider usage data; it is not a
  substitute for the provider billing statement.

## Undo and recovery

Target behavior:

- TUI chat undo and REPL undo share the same `UndoJournal` semantics.
- Unrelated manual edits are preserved.
- Empty undo reports "Nothing to undo" and performs no destructive fallback.

Current behavior:

- TUI and REPL undo use `ChatSessionController.undo_last_run()` and the run undo journal.
- TUI undo does not fall back to a global checkpoint or stash restore.
- When no journal is available, the command reports `nothing to undo` without changing
  the workspace.

## Output formats

Keep output boring and inspectable:

- Plain answers for normal tasks.
- Explicit run ids for agent work.
- Explicit approval ids for blocked actions.
- Clear "known issue" wording when a display is not authoritative.

## Maintainer note

Preserve the shared controller contract when either surface changes. A user should be
able to switch between TUI chat and REPL chat without relearning cost, undo, result, or
failure semantics; active-path parity tests are the release guard.
