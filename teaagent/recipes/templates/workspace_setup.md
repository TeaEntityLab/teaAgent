# Workspace Setup Recipe

**When to use:** Setting up TeaAgent in a new or existing repository for the
first time. You need a `.teaagent/config.json`, a provider key, and a
safe permission mode.

## Step 1: Install TeaAgent

```bash
pip install -e .
```

Use a virtual environment on macOS/Homebrew Python (PEP 668):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[tui]"
```

## Step 2: Configure the workspace

```bash
teaagent setup --root . --provider gpt --permission-mode read-only --write-env
```

This creates:
- `.teaagent/config.json` with provider, permission mode, and budget defaults
- `.teaagent/config.toml` (TOML equivalent)
- `.teaagent/env` with your API key export (if `--write-env` is passed)
- `AGENTS.md` with basic project instructions (if not present)

## Step 3: Verify readiness

```bash
teaagent daily "summarize this repo" --dry-run --human --root .
```

Check the output for **Blocking** vs **Warning** vs **Info** items.

## Step 4: Run a read-only task

```bash
teaagent run "summarize the test suite" --permission-mode read-only --root .
```

## Step 5: Set up daily ergonomics (optional)

Enable the TUI for multi-turn interaction:

```bash
teaagent tui --setup --root .
```

Inside the TUI: `daily`, `ask`, `runs`, `resume`.

**Recovery:** If `teaagent setup` fails with "unknown provider", verify the
provider name via `teaagent model providers`. If the API key is rejected,
run `teaagent doctor model gpt` to diagnose.
