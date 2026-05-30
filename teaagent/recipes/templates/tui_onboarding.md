# TUI Onboarding Recipe

**When to use:** You prefer an interactive terminal session over one-shot CLI
commands. The TUI provides multi-turn chat, memory, approvals, and session
management in a single window.

## Step 1: Start the TUI

```bash
teaagent tui --setup --root . --write-env
```

The `--setup` flag runs the guided setup wizard before entering the REPL.
Use `--write-env` to persist your API key to `.teaagent/env`.

## Step 2: Run the daily cockpit

At the `teaagent>` prompt, type:

```
daily what I want to do today
```

This shows readiness, token budget, recent runs, and pending approvals
without calling a model.

## Step 3: Explore with ask

```
ask summarize the test suite
```

For ambiguity checking first:

```
ask --clarify summarize the test suite
```

## Step 4: Handle approvals

When a destructive tool is proposed in prompt mode:

```
approve write-todo-1
approvals
```

## Step 5: Manage memory

```
memory add Prefer read-only mode for audit tasks
memory search audit tasks
memory list
```

## Step 6: Review runs and resume

```
runs
show <run_id>
resume <run_id>
```

## TUI cheat sheet

| Command | What it does |
|---------|-------------|
| `provider gpt` | Set LLM provider |
| `model gpt-4o` | Override model name |
| `permission read-only` | Set permission mode |
| `chat on` | Enable multi-turn context |
| `route-model on` | Enable automatic model routing |
| `doctor` | Diagnose setup issues |
| `exit` | Quit the TUI |

**Recovery:** If the TUI fails to start, verify `pip install -e ".[tui]"` for
enhanced editing support. Without it, TUI falls back to standard `input()`.
