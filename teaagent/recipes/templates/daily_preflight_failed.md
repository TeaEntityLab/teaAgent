# Daily Preflight Failed Recipe

**When to use:** `teaagent daily "readiness" --dry-run --human --root .`
reports blocking items or warnings that prevent a safe agent run.

## Step 1: Read the severity

The `--human` output groups issues by severity:

- **Blocking** (red) — must fix before any agent run
- **Warning** (yellow) — should fix, but limited tasks may proceed
- **Info** (blue) — optional, not blocking

## Step 2: Fix blocking items by type

### Provider not configured

```bash
teaagent doctor model gpt
teaagent setup --root . --provider gpt --write-env
```

### Permission denied on .git

Git metadata not writable (common in sandboxes). Retry in a writable directory:

```bash
teaagent setup --root /tmp/teaagent-try --provider gpt --api-key "$OPENAI_API_KEY"
teaagent daily "readiness" --dry-run --human --root /tmp/teaagent-try
```

### Workspace not initialized

```bash
teaagent setup --root . --permission-mode read-only
```

### API key missing

```bash
export OPENAI_API_KEY="sk-..."
teaagent doctor model gpt
```

## Step 3: Re-check readiness

```bash
teaagent daily "readiness" --dry-run --human --root .
```

## Step 4: Proceed once clear

```bash
teaagent run "summarize the test suite" --permission-mode read-only --root .
```

**Still blocked?** Check provider connectivity:
- `teaagent model smoke gpt --prompt "Reply with exactly: ok"`
- `teaagent doctor model gpt --wizard`
- Verify `OPENAI_API_KEY` is set and valid
