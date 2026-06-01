# TUI Chat Recipes
# 2026-06-02

Small recipes for using TUI chat without overtrusting incomplete parity.

## Recipe: Safe TUI startup

```bash
teaagent tui --setup --root .
```

Check:

- Visible root matches the repository.
- Permission mode is expected.
- Provider/model are expected.
- No pending approval from an old run is confused with the current run.

## Recipe: Ask a low-risk question

```text
ask summarize current open daily-driver risks
```

Expected:

- A visible answer or visible failure.
- A run id when agent work is created.
- No silent no-op.

## Recipe: Use sessions

```text
session new
ask list the current ticket risks
session show
```

Use sessions for continuity, but do not treat session state as a replacement for run
evidence.

## Recipe: Check cost

```text
/cost
```

Interpretation:

- Non-zero cost after real work is a good sign.
- `$0.00` after real work means check the run summary or provider dashboard.
- Full confidence requires TICKET-12 active-path tests.

## Recipe: Recover safely

Before TUI `/undo`:

1. Check `git status` in another terminal.
2. Decide whether you need journal undo or checkpoint restore.
3. If unsure, use manual git inspection before running recovery.

## Recipe: Leave TUI for precise chat work

Switch to:

```bash
teaagent chat
```

when you need precise cost, result, and undo behavior.
