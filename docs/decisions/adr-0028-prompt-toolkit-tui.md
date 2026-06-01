# ADR-0028: prompt-toolkit as TUI Framework (Optional Dependency)

**Status:** Accepted  
**Date:** 2026-06-02  
**Deciders:** Core team  
**Related ADRs:** ADR-0001 (P0 zero-dep posture), ADR-0025 (ChatSessionController unification)

---

## Context

TeaAgent needs an interactive terminal UI (`teaagent chat`) that supports:
- Multi-line input with readline-style editing
- Slash-command autocompletion (`/cost`, `/undo`, `/plan`, `/approve`, …)
- Syntax highlighting for code output
- Non-blocking streaming output from the agent (tokens arrive during user's next prompt composition)
- A split-pane view for cockpit status (token count, cost, permission mode) alongside the conversation

This cannot be satisfied by `input()` or raw `sys.stdin` readline — completion and async output require a proper terminal abstraction.

## Decision

Use `prompt-toolkit >= 3.0.0` as an optional dependency (`pip install teaagent[tui]`). The TUI lives in `teaagent/tui/` and is imported lazily (never at CLI startup unless the `chat` command is invoked). Core harness has zero awareness of `prompt-toolkit`.

The TUI is structured as:
- `tui/__init__.py` — `TeaAgentTUI` class, REPL loop
- `tui/_commands.py` — `/cmd` handler dispatch
- `tui/_completion.py` — `WordCompleter` for slash commands and model names
- `tui/_approval_subagents.py` — inline approval UI for subagent queues
- `tui/_setup.py` — first-run wizard

## Consequences

**Positive:**
- `prompt-toolkit` provides cross-platform (Linux/macOS/Windows) terminal handling, readline emulation, and async-compatible `PromptSession`
- Completion and key-bindings are declarative — no `curses` attr arithmetic
- `patch_stdout()` allows the agent's streaming output to interleave correctly with the prompt line without tearing
- No C extensions — pure Python, installable in constrained environments
- Active maintenance (used by IPython, pgcli, etc.)

**Negative:**
- Adds ~1.5 MB to installed size and ~0.2s to `import prompt_toolkit` cold start
- Split-pane cockpit requires layering `prompt-toolkit` layout primitives (HSplit/VSplit) which are not trivial to test headlessly
- TUI tests require either a real PTY or `prompt_toolkit.input.create_pipe_input()` — more complex than unit tests
- `prompt-toolkit`'s async model (uses `asyncio`) interacts with TeaAgent's sync-from-async bridge (ADR-0018) — must use `PromptSession.prompt()` in a thread, not `prompt_async()`

## Alternatives Considered

### `curses` (stdlib)
- **Rejected:** No Windows support. Screen management arithmetic (move, clrtobot, addstr) is error-prone. No built-in readline emulation — must implement key dispatch manually. Zero-dependency but unacceptable ergonomics burden.

### `textual` (Textualize)
- **Rejected:** Pulls in `rich` + `textual` (~4 MB). Widget-based reactive model is powerful for dashboards but heavyweight for a REPL. Textual's CSS layout system is not worth the complexity for TeaAgent's primarily linear chat flow.

### `rich` alone (no input handling)
- **Rejected:** `rich` handles output rendering beautifully but provides no input facilities. Would still need `readline` or `prompt-toolkit` for input. Using both adds two deps without eliminating either.

### Raw `readline` (stdlib)
- **Rejected:** No async interleave — streaming output corrupts the input line. No custom completer API on Windows. Completion integration with our command set would require reimplementing what `prompt-toolkit` provides.

## Rationale

`prompt-toolkit` is the minimal viable framework that provides all required TUI primitives (completion, async-safe output, key bindings) without pulling in a full widget toolkit. Its optional-dep placement preserves the zero-dependency core for CI and headless usage. IPython's long-term use of `prompt-toolkit` confirms it is stable enough to depend on.

## Conditions to Reconsider

- If a richer split-pane cockpit (charts, tables, live sparklines) is required → evaluate `textual`
- If Windows terminal compatibility issues emerge with `prompt-toolkit` → add `pyreadline3` shim or fall back to `input()` on Windows with a warning
- If TUI cold-start time becomes a UX complaint → lazy-import `prompt-toolkit` sub-modules rather than top-level package
