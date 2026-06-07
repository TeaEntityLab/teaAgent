# Troubleshooting Guide

> Last updated: 2026-06-07

Symptom-first troubleshooting for TeaAgent. Each entry follows the pattern:
**symptom** → **cause** → **fix** → **prevention**.

For TUI and chat-specific issues, see [daily-driver-troubleshooting.md](daily-driver-troubleshooting.md).
For error hierarchy and denial reason codes, see [error-reference.md](error-reference.md).

## Provider connection failures

### "Provider X not configured"

**Symptom:** `teaagent run` or `teaagent daily` fails with "Provider X not configured" or "ProviderNotFound."

**Cause:** The selected provider's API key is missing from the environment, or the provider was never initialized in this workspace.

**Fix:**

1. Run `teaagent doctor providers` to list configured and unconfigured providers.
2. Set the environment variable for your provider:

   ```bash
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=...
   export GEMINI_API_KEY=...
   ```

3. For persistent setup, add the export to your shell profile or use the bundled template:

   ```bash
   cp scripts/providers_env.zsh ~/.teaagent/providers_env.zsh
   echo 'source ~/.teaagent/providers_env.zsh' >> ~/.zshrc
   ```

4. Run `teaagent doctor model <provider_name>` to verify the provider is reachable.

**Prevention:**

- Keep `~/.teaagent/providers_env.zsh` up to date with active API keys.
- Set key expiry reminders if using time-limited keys.
- Use `teaagent wizard` on first run.

### "LLM request failed" / HTTP errors from provider

**Symptom:** The run starts but the model call fails with an HTTP error (401, 403, 429, 5xx).

**Cause:** Expired API key, rate limit exceeded, or provider outage.

**Fix:**

1. Check the API key validity on the provider dashboard.
2. For rate limits, reduce parallelism (`--parallel 1`) or wait for the rate window to reset.
3. For 5xx errors, try again later or switch providers:

   ```bash
   teaagent run "your task" --provider gpt
   ```

**Prevention:**

- Configure a fallback provider in `.teaagent/config.json` under `fallback_provider`.
- Monitor the [OpenAI Status](https://status.openai.com), [Anthropic Status](https://status.anthropic.com), or similar status pages.

## Permission mode confusion

### "Why can't I write?" / "Tool permission denied"

**Symptom:** The agent says "Tool permission denied" when you expected it to edit files or run shell commands.

**Cause:** The current permission mode blocks the requested operation.

**Fix:**

1. Check your current permission mode:

   ```bash
   teaagent run "status" --dry-run --root . --human
   # Output includes the active permission mode
   ```

2. The five permission modes and what they block:

   | Mode | File reads | File writes | Shell inspect | Shell mutate |
   |------|-----------|-------------|---------------|--------------|
   | `read-only` | ✓ | ✗ | ✗ | ✗ |
   | `workspace-write` | ✓ | ✓ | ✓ | ✗ |
   | `prompt` | ✓ | ✓ | ✓ | requires approval |
   | `allow` | ✓ | ✓ | ✓ | ✓ |
   | `danger-full-access` | ✓ | ✓ | ✓ | ✓ |

3. Re-run with a more permissive mode:

   ```bash
   teaagent run "your task" --permission-mode workspace-write
   ```

**Prevention:**

- Start explorations with `read-only`, then bump to `workspace-write` or `prompt` when you're ready to commit changes.
- Use `--human` on `daily` to preview the planned permission mode before tasks run.
- For CI/automation, pin the required mode explicitly in scripts.

### "Plan-before-write enforcement blocked my task"

**Symptom:** `workspace-write` mode rejects tool calls with a plan-contract error.

**Cause:** Plan-before-write enforcement requires a plan to exist before destructive operations. This is a safety feature, not a bug.

**Fix:**

1. Create a plan first in read-only mode:

   ```bash
   teaagent run "Analyze the codebase and plan changes" --permission-mode read-only
   ```

2. Then execute with workspace-write.

3. If you know the task is safe and low-risk, bypass with:

   ```bash
   teaagent run "your task" --permission-mode workspace-write --skip-plan-check
   ```

**Prevention:**

- Always plan in `read-only` before switching to write modes.
- Reserve `--skip-plan-check` for trivial, well-scoped edits only.

## Test failures after rebase

### "Tests pass on main but not on my branch"

**Symptom:** You rebased onto main and now tests fail on your branch, even though the same tests pass on `main`.

**Cause:** One of:
- Merge conflicts were resolved incorrectly, dropping or duplicating code.
- Your branch changes interact unexpectedly with new code on main.
- A dependency was updated on main (check `pyproject.toml` diff).

**Fix:**

1. Reinstall dependencies to match the rebased state:

   ```bash
   pip install -e ".[dev]"
   ```

2. Re-run the failing test in isolation:

   ```bash
   pytest tests/path/to/failing_test.py -x -v
   ```

3. Bisect the failing commit on your branch:

   ```bash
   git bisect start HEAD main
   git bisect run pytest tests/path/to/failing_test.py
   ```

4. If the failure is in a file you didn't change, check whether a rebase introduced a breaking change from main that your branch must accommodate.

**Prevention:**

- After every rebase, run the full test suite before pushing:

  ```bash
  pytest && ruff check . && mypy teaagent/ tests/ --explicit-package-bases
  ```

- Squash merge-conflict-only commits to keep history clean.

## Pre-commit hook failures

### "pre-commit hooks are failing"

**Symptom:** `git commit` is blocked by failing pre-commit hooks (ruff, mypy, etc.).

**Cause:** Staged changes violate linting, formatting, or type-checking rules enforced by the pre-commit configuration.

**Fix:**

1. See which hook failed and the specific error:

   ```bash
   pre-commit run --all-files
   ```

2. Common failures and their fixes:

   | Hook failure | Fix |
   |-------------|-----|
   | `ruff check` | `ruff check --fix .` then re-stage |
   | `ruff format` | `ruff format .` then re-stage |
   | `mypy` | Fix type errors in changed files; check `mypy teaagent/ tests/ --explicit-package-bases` |
   | `bandit` | Review security finding; decide whether to fix or suppress with `# nosec` |
   | `check for merge conflicts` | Resolve leftover `<<<<<<<` markers |

3. After fixing, re-stage and commit:

   ```bash
   git add <fixed files>
   git commit -m "your message"
   ```

4. If a hook is incorrectly blocking (e.g. a false positive), bypass with caution:

   ```bash
   SKIP=hook-id git commit -m "your message"
   ```

**Prevention:**

- Run lint checks before staging (`ruff check . && ruff format --check .`).
- Install pre-commit hooks globally: `pre-commit install`.
- Keep `pyproject.toml` tool configs consistent with CI.

## Audit chain verification

### "audit verify fails"

**Symptom:** `teaagent audit verify` reports a broken hash chain, missing entries, or integrity violations.

**Cause:** The audit log (`.teaagent/runs/<run_id>/audit.jsonl`) has been tampered with, truncated, or corrupted. This can also happen if a run was interrupted during a write.

**Fix:**

1. Identify the specific failure:

   ```bash
   teaagent audit verify --run-id <run_id> --verbose
   ```

   The output shows which entry failed validation and why.

2. **If the run was interrupted** (e.g., process killed, OOM):
   - The audit chain may be salvageable up to the last valid entry.
   - Run `teaagent audit list` to see which runs have valid chains.

3. **If entries were lost or corrupted:**
   - Check whether a backup exists (some deployments mirror audit logs).
   - For compliance-grade runs, use `teaagent audit export <run_id>` to produce a portable audit bundle before corruption spreads.

4. **If tampering is suspected:**
   - Compare the audit chain hash with a known-good hash from an earlier export.
   - The security whitepaper details the hash-chain scheme: see [security-whitepaper.md](security-whitepaper.md).

**Prevention:**

- Export audit chains after important runs:

  ```bash
  teaagent audit export <run_id> --output audit-bundle.tar.gz
  ```

- Set `audit_compliance_mode: true` in `.teaagent/config.json` for stricter disk-sync guarantees (at a performance cost).
- Rotate audit logs to cold storage before the run directory grows too large.

## Common error messages quick reference

| Error message | Likely cause | First action |
|--------------|-------------|-------------|
| `Budget exceeded` | Task exceeded `--max-estimated-cost-cents` | Increase budget or reduce task scope |
| `Tool validation error` | Model produced an invalid tool call | Retry; check the model's tool-call output format |
| `Run not found` | Wrong run ID or workspace | List runs with `teaagent runs` |
| `Approval timeout` | JIT approval prompt not answered in time | Re-run and respond to prompts within 3 min |
| `Circular import detected` | Module dependency cycle | Run `python3 scripts/check_circular_imports.py` |
| `MCP server connection refused` | MCP server not running or wrong port | Verify `--port` matches the server; check firewall |
| `Permission denied: full-access` | `danger-full-access` not acknowledged | Re-run with explicit acknowledgment |
| `File policy denied` | Path outside allowed globs in file policy | Adjust `~/.config/teaagent/file_policy.toml` |

For the full error hierarchy and programmatic error handling, see [error-reference.md](error-reference.md).
