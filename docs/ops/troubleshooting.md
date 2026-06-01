# Troubleshooting Guide

Diagnosis and resolution for common teaagent problems.

---

## Diagnostic Commands

Run these first before digging into specific issues:

```bash
# Full health check
teaagent doctor all

# Model reachability
teaagent model smoke

# Provider status
teaagent doctor providers

# Approval policy sanity
teaagent approval doctor

# Environment variable resolution order
teaagent doctor env_order

# Git sandbox check
teaagent doctor git_sandbox
```

---

## Cost Tracking Wrong

### Symptom

`teaagent cost cost_report` shows $0 or an unrealistically low number despite running many tasks. The TUI cost counter doesn't update.

### Diagnosis

```bash
# Check the raw audit log for cost events
grep '"type":"cost"' .teaagent/audit.jsonl | tail -10

# Check if cost events are being written to run logs
grep '"cost_usd"' .teaagent/runs/*.jsonl | tail -10

# Verify the budget monitor is active
grep -r "budget_monitor\|cost_cap" .teaagent/config.json
```

### Known causes and fixes

**Cause: Provider adapter not returning usage data**

Some providers return `usage: null` in their API responses. Check:

```bash
teaagent model capabilities --provider <provider>
```

If `token_counting` shows `false`, cost tracking is not available for this provider.

**Cause: Cost accumulation regression (CG-03)**

A known issue where mock cost data from test paths leaks into production sessions. This was addressed in TICKET-14.

Verify you're on a fixed version:

```bash
teaagent --version
# Should be >= the version containing the CG-03 fix
```

Workaround: restart the TUI session — cost resets to 0 on each new session start and accumulates correctly within a session.

**Cause: `TEAAGENT_NO_SUMMARY=1` hiding cost output**

The cost is tracked internally but the summary is suppressed. Unset the variable or check the audit log directly:

```bash
grep '"session_cost"' .teaagent/audit.jsonl | tail -5
```

---

## Undo Not Working

### Symptom

`teaagent agent undo --last` returns an error or reports nothing to undo. File changes made by the agent persist after undo.

### Diagnosis

```bash
# Check if undo data exists
ls -la .teaagent/undo/

# Check what runs are undoable
teaagent agent runs --undoable

# Look at the undo log for the specific run
teaagent agent show <run_id> | grep undo
```

### Known causes and fixes

**Cause: Undo data not written (CG-02 destructive undo regression)**

If `.teaagent/undo/` is empty even after running tasks, the checkpoint write may have failed silently. Check disk space and file permissions:

```bash
df -h .teaagent/
ls -la .teaagent/
```

The directory must be writable by the teaagent process:

```bash
chmod 700 .teaagent/
chmod 700 .teaagent/undo/
```

**Cause: Run used `danger-full-access` mode**

In `danger-full-access` mode, undo checkpoints may be skipped. Check:

```bash
grep '"permission_mode"' .teaagent/runs/<run_id>.jsonl | head -1
```

**Cause: Changes were committed to git**

Undo only reverts in-process changes. If the agent committed to git, use git to revert:

```bash
git log --oneline -5
git revert HEAD --no-edit
```

---

## TUI Frozen

### Symptom

The terminal UI is unresponsive: spinner spinning indefinitely, no response to keyboard input, `Ctrl+C` doesn't work.

### Diagnosis

```bash
# From another terminal, check if the process is alive
pgrep -af "teaagent"

# Check for pending approvals that need input
teaagent approval pending

# Check the last event written to the run log
tail -1 .teaagent/runs/*.jsonl
```

### Fixes

**Fix 1: A pending approval is waiting**

If the TUI is waiting for approval but not rendering the prompt correctly, approve from another terminal:

```bash
teaagent approval pending
teaagent approval approve <id>
```

**Fix 2: LLM API call stalled**

The agent is waiting for a response that never comes. Kill and resume:

```bash
# Kill the stuck process
kill -TERM $(pgrep -f "teaagent")

# Resume from checkpoint
teaagent resume <session_id>
```

**Fix 3: Terminal state corrupted**

If the terminal is garbled after killing:

```bash
reset   # or: stty sane
```

**Fix 4: prompt-toolkit version incompatibility**

```bash
pip install --upgrade prompt-toolkit
```

### Prevention

Set a heartbeat timeout so hung sessions self-terminate:

```bash
export TEAAGENT_HEARTBEAT=60   # kill if no heartbeat for 60s
```

---

## Agent Crashes

### Symptom

`teaagent run` exits with a non-zero code and a Python traceback. The run is marked `failed` in the run store.

### Diagnosis

```bash
# Show the last failed run
teaagent agent runs --status failed --limit 5
teaagent agent show <run_id>

# Check the run log for the exception
grep '"error"\|"exception"\|"traceback"' .teaagent/runs/<run_id>.jsonl
```

### Common crash causes

**ImportError: optional dependency not installed**

```
ImportError: No module named 'tree_sitter'
```

Fix:

```bash
pip install "teaagent[code-analysis]"
```

**AuthenticationError / 401 from provider**

API key is invalid or expired:

```bash
teaagent doctor providers
# Re-export the correct key
export ANTHROPIC_API_KEY="sk-ant-..."
```

**RateLimitError / 429 from provider**

Reduce throughput:

```bash
export TEAAGENT_MAX_TOOL_CALLS=5
export TEAAGENT_MAX_ITERATIONS=5
```

**OSError: No space left on device**

See [RB-06: Disk Full](runbooks.md#rb-06-disk-full).

**PermissionError writing to .teaagent/**

```bash
ls -la .teaagent/
chmod 700 .teaagent/
```

**JSON decode error in config**

```bash
python3 -m json.tool .teaagent/config.json
```

Fix any JSON syntax errors reported.

---

## Provider Not Reachable

### Symptom

`teaagent doctor providers` reports `[FAIL]` for your provider. API calls time out or return connection errors.

### Diagnosis

```bash
# Smoke test specific provider
teaagent model smoke --provider claude

# Check network connectivity
curl -s https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" | head -c 200

# For OpenAI
curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 200
```

### Fixes

**No API key set:**

```bash
echo $ANTHROPIC_API_KEY   # should be non-empty
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Behind a corporate proxy:**

```bash
export HTTPS_PROXY="http://proxy.corp.example.com:8080"
export REQUESTS_CA_BUNDLE="/etc/ssl/certs/corporate-ca.pem"
```

**Custom base URL needed (private endpoint, AI Gateway):**

```bash
export ANTHROPIC_BASE_URL="https://api-gateway.corp.example.com/anthropic"
```

**TLS certificate issue:**

```bash
export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
```

---

## Memory Catalog / Skill Not Found

### Symptom

`teaagent skill search <term>` returns nothing. A skill that was previously working is no longer found.

### Diagnosis

```bash
# Check skill search directories
teaagent tool list
echo $TEAAGENT_SKILL_SEARCH_DIRS

# Check skill source profile
echo $TEAAGENT_SKILL_SOURCE_PROFILE
```

### Fix

```bash
# Add skill directory to config
cat > .teaagent/config.json <<EOF
{
  "skill_search_dirs": ["/path/to/your/skills"],
  "skill_source_profile": "default"
}
EOF
```

---

## Multi-Sig Quorum Stuck

### Symptom

A run is waiting for peer approval that never arrives. `teaagent consensus status` shows quorum pending.

### Diagnosis

```bash
teaagent consensus status
teaagent consensus history --limit 10
```

### Fixes

```bash
# Check if peers are reachable
teaagent consensus peers_status

# Import votes manually from a peer
teaagent consensus votes_import --peer <peer_id> --file votes.json

# If quorum is unresolvable, bypass for this run (requires admin)
teaagent consensus config_update --required-approvals 1
```

---

## Config Precedence Confusion

### Symptom

An environment variable or config file value appears to be ignored.

### Diagnosis

```bash
# Show the resolved config values and their sources
teaagent doctor env_order
```

This prints each config key with its final value and the source (env var, workspace config, user config, or default).

### Common mistakes

- Environment variable name misspelled (must be `TEAAGENT_MAX_ITERATIONS`, not `TEAAGENT_MAXITERATIONS`)
- Config file is TOML format but `teaagent[config]` is not installed — file is silently ignored
- Wrong workspace root: check `--root` or `$PWD`

---

## Graphqlite / Code Analysis Not Working

### Symptom

`teaagent doctor graphqlite` reports `[FAIL]`. Code search returns no results.

### Diagnosis

```bash
teaagent doctor graphqlite
ls .teaagent/*.db 2>/dev/null
```

### Fix

```bash
pip install "teaagent[graphqlite,code-analysis]"

# Rebuild the code index
teaagent agent card --rebuild-index
```

---

## Log Reference

| Log location | What it contains |
|-------------|-----------------|
| `.teaagent/audit.jsonl` | All audit events, chain-signed |
| `.teaagent/runs/<id>.jsonl` | Full replay data for a specific run |
| `.teaagent/scratchpad.json` | Persisted run context |
| `~/.teaagent/tui_state.json` | TUI layout and history |
| stderr | Python tracebacks (unhandled exceptions) |

To capture stderr for debugging:

```bash
teaagent run "task" 2> debug.log
cat debug.log
```
