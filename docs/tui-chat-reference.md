# TUI Chat Reference
# As of 2026-06-02

This is a focused reference for chat-like workflows inside the TUI. It is written from
the user's point of view and records current divergence from `teaagent chat`.

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

Current warning: the TUI path is not fully migrated to `ChatSessionController`, so it
should not yet be treated as the canonical chat semantics.

2026-06-02 code fact: the working tree now forwards `args.task` from
`chat_command()` into `run_tui(initial_task=...)`, and the TUI attempts to run that task
before entering the prompt loop. Keep this as a verify/close item until tests cover the
parser, handler, failure display, and prompt-loop behavior.

## Cost and budget display

Target behavior:

- Session cost increases after real model work.
- Budget bars and `/budget` reflect the same session ledger.
- Provider billing, run summary cost, and user-facing display do not contradict each other.

Current behavior:

- The working tree includes a stop-gap that adds `result.cost_cents` to
  `_session_cost_cents`.
- Full parity is still incomplete because the TUI still calls `run_chat_agent` directly
  instead of using `ChatSessionController` as the single ledger owner.
- The budget cap can still enforce while visible session display parity is being proven.

## Undo and recovery

Target behavior:

- TUI chat undo and REPL undo share the same `UndoJournal` semantics.
- Unrelated manual edits are preserved.
- Empty undo reports "Nothing to undo" and performs no destructive fallback.

Current behavior:

- `teaagent chat` already has the safer journal-backed behavior.
- TUI undo can still follow checkpoint/stash semantics.

## Output formats

Keep output boring and inspectable:

- Plain answers for normal tasks.
- Explicit run ids for agent work.
- Explicit approval ids for blocked actions.
- Clear "known issue" wording when a display is not authoritative.

## Maintainer note

After TICKET-12 lands, this reference should be changed from a caveat page into a
parity page. The acceptance condition is that a user can switch between TUI chat and
REPL chat without relearning cost, undo, result, or failure semantics.
