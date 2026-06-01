# Runbooks

Step-by-step procedures for operational incidents. Each runbook follows: **Symptoms → Diagnosis → Mitigation → Recovery → Post-incident**.

---

## RB-01: Emergency Pause / Resume

**When:** A runaway agent is consuming cost or making unexpected changes; a security concern is detected mid-run; you need to halt all automation before a production change window.

### Pause all automation

```bash
# Stop all running automation workflows
teaagent automation pause --all

# Verify nothing is running
teaagent automation status
```

Expected: all workflows show status `paused`.

### Pause a specific run in progress

Send `SIGTERM` to the agent process:

```bash
# Find the PID
pgrep -f "teaagent"

# Graceful stop
kill -TERM <pid>
```

TeaAgent flushes audit events before exit. The interrupted run is recorded with status `interrupted`.

### Resume when safe

```bash
# Resume all paused automation
teaagent automation resume --all

# Resume a specific suspended session
teaagent resume <session_id>
```

### Post-incident

1. Review what the agent did before pause: `teaagent audit list --run-id <run_id>`
2. Check for uncommitted changes: `git status`
3. Undo the last agent action if needed: `teaagent agent undo --last`
4. Document the incident and root cause.

---

## RB-02: Cost Limit Breach

**When:** `TEAAGENT_DAILY_COST_CAP_CENTS` is exceeded; unexpectedly high API spend is detected; a runaway loop is suspected.

### Symptoms

- Agent exits with `COST_CAP_EXCEEDED` status
- `teaagent cost cost_report --period today` shows spend above cap
- Alert fired from cost monitoring (see [Monitoring and Alerting](monitoring-and-alerting.md))

### Immediate mitigation

```bash
# 1. Stop all active runs
teaagent automation pause --all

# 2. Check today's spend
teaagent cost cost_report --period today

# 3. Identify the expensive run(s)
teaagent agent runs --sort cost --limit 10
```

### Diagnosis

```bash
# Show full cost breakdown for a specific run
teaagent agent show <run_id>

# Check iteration count (runaway loop indicator)
grep '"iteration"' .teaagent/runs/<run_id>.jsonl | wc -l
```

Common causes:
- `max_iterations` set too high with a looping task
- Large context window being sent repeatedly
- Tool returning errors that trigger retry loops

### Recovery

```bash
# Temporarily lower the cap or max_iterations
export TEAAGENT_DAILY_COST_CAP_CENTS=1000
export TEAAGENT_MAX_ITERATIONS=5

# Resume limited operations
teaagent automation resume --filter low-cost-only
```

### Post-incident

1. Adjust `max_iterations` and `max_tool_calls` in `.teaagent/config.json`
2. Set `TEAAGENT_DAILY_COST_CAP_CENTS` to a value with 20% headroom above normal spend
3. Add cost monitoring alert (see [Monitoring and Alerting](monitoring-and-alerting.md))

---

## RB-03: Audit Log Corruption Detected

**When:** `teaagent audit verify` reports a chain HMAC mismatch; audit JSONL is malformed; a file integrity alert fires.

### Symptoms

```
ERROR: HMAC chain broken at event 4521
ERROR: Invalid JSON at line 892 of audit.jsonl
```

### Immediate actions

```bash
# 1. Preserve the corrupted file
cp .teaagent/audit.jsonl .teaagent/audit.jsonl.corrupted-$(date +%Y%m%d-%H%M%S)

# 2. Determine extent of corruption
teaagent audit verify 2>&1 | head -50

# 3. Find the last valid event
grep -c '^{' .teaagent/audit.jsonl
python3 -c "
import json, sys
with open('.teaagent/audit.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except Exception as e:
            print(f'First bad line: {i}: {e}')
            break
"
```

### Recovery options

**Option A: Truncate to last valid line (partial recovery)**

```bash
# Truncate at first bad line (replace N with the bad line number - 1)
head -n <N> .teaagent/audit.jsonl > .teaagent/audit.jsonl.repaired
mv .teaagent/audit.jsonl.repaired .teaagent/audit.jsonl
chmod 600 .teaagent/audit.jsonl
```

**Option B: Restore from backup**

```bash
# Restore latest audit backup (see Backup and Recovery)
cp /backup/teaagent/.teaagent/audit.jsonl .teaagent/audit.jsonl
chmod 600 .teaagent/audit.jsonl
```

**Option C: Start fresh (last resort)**

```bash
mv .teaagent/audit.jsonl .teaagent/audit.jsonl.archive-$(date +%Y%m%d)
teaagent audit list  # This creates a new empty audit.jsonl
```

### Investigation

```bash
# Check filesystem errors
dmesg | grep -i error | tail -20

# Check disk health
df -h .
diskutil verifyVolume / 2>/dev/null || fsck -n /dev/sdX
```

### Post-incident

1. Identify root cause (disk error, process crash mid-write, permissions issue)
2. Enable audit log shipping to an external sink as a second copy
3. Consider the OTLP telemetry sink or webhook sink for real-time redundancy
4. File an incident report noting the time range of potentially unverifiable events

---

## RB-04: Agent Timeout

**When:** An agent run hangs indefinitely; no tool-call progress for an extended period; TUI appears frozen with a spinner.

### Symptoms

- `teaagent agent status` shows a run in `running` state for longer than expected
- No new lines appearing in `.teaagent/runs/<run_id>.jsonl`
- TUI spinner active but no output

### Diagnosis

```bash
# Check if the process is actually running
pgrep -af "teaagent"

# Check last event time in the run log
tail -1 .teaagent/runs/<run_id>.jsonl | python3 -c "import json,sys; e=json.loads(sys.stdin.read()); print(e.get('ts', 'no ts'))"

# Check for network hangs (strace on Linux)
strace -p <pid> -e trace=network 2>&1 | head -20
```

Common causes:
- LLM provider API timeout (no response from upstream)
- Tool waiting for user approval that was never surfaced
- Deadlock in multi-sig quorum wait

### Mitigation

```bash
# 1. Check for pending approvals
teaagent approval pending

# If approvals are pending, approve or deny them
teaagent approval next
teaagent approval approve <id>

# 2. If no pending approvals, forcibly terminate the hung process
kill -TERM <pid>

# 3. If SIGTERM doesn't work after 10 seconds
kill -KILL <pid>
```

### Recovery

```bash
# Resume the interrupted session if it was checkpointed
teaagent resume <session_id>

# Or restart from scratch
teaagent run "continue from where you left off" --root .
```

### Post-incident

1. Check `TEAAGENT_HEARTBEAT` interval — set to `60` to enable watchdog heartbeats
2. Add a timeout wrapper for CI: `timeout 1800 teaagent run "task"`
3. Consider reducing `max_iterations` to limit maximum run duration

---

## RB-05: Approval Backlog

**When:** Many runs are blocked awaiting human approval; `teaagent approval pending` shows a large queue; automation throughput drops to zero.

### Diagnosis

```bash
# Count pending approvals
teaagent approval pending | wc -l

# Show oldest pending approvals
teaagent approval pending --sort created --limit 20

# Explain why each is blocked
teaagent approval why_denied <approval_id>
```

### Bulk approval (use with care)

```bash
# Approve all pending read-only operations
teaagent approval pending --filter read-only | \
  awk '{print $1}' | \
  xargs -I{} teaagent approval approve {}

# Set a preset to auto-approve specific tool patterns
teaagent approval preset --tool "read_file,list_directory" --action allow --scope session
```

### Systemic fix

If the permission mode is too restrictive for your workflow:

```bash
# Upgrade permission mode for a session
teaagent run "task" --permission-mode workspace-write

# Or update the workspace config
cat > .teaagent/config.json <<EOF
{
  "permission_mode": "workspace-write"
}
EOF
```

### Post-incident

1. Review which tools are triggering approval most frequently: `teaagent approval audit --sort count`
2. Add frequently-approved tools to a session preset: `teaagent approval preset`
3. Consider switching from `prompt` to `workspace-write` mode if all approvals are for file writes

---

## RB-06: Disk Full

**When:** `.teaagent/` or its parent filesystem is full; writes to audit log fail; agent aborts with `OSError: [Errno 28] No space left on device`.

### Immediate mitigation

```bash
# 1. Check disk usage
df -h .
du -sh .teaagent/

# 2. Find large files
du -sh .teaagent/*/ | sort -rh | head -10

# 3. Largest audit files
ls -lSh .teaagent/runs/ | head -10
```

### Free space

```bash
# Remove old run logs (> 30 days)
find .teaagent/runs/ -name "*.jsonl" -mtime +30 -delete

# Prune audit log
teaagent audit prune --older-than 30d

# Remove old undo checkpoints
find .teaagent/undo/ -name "*.jsonl" -mtime +7 -delete

# Clear old plan files
find .teaagent/plans/ -name "*.json" -mtime +30 -delete
```

### Permanent fix

1. Set up automated cron pruning (see [Operations Manual](operations-manual.md))
2. Ship audit logs to an external system and prune local copies
3. Move `.teaagent/` to a larger volume via symlink:

```bash
mv /opt/workspace/.teaagent /data/teaagent-state
ln -s /data/teaagent-state /opt/workspace/.teaagent
```

---

## RB-07: Undo / Rollback Agent Changes

**When:** An agent made incorrect edits; a run completed but produced wrong results; you need to revert to pre-run state.

### Undo last agent action

```bash
teaagent agent undo --last
```

### Undo a specific run

```bash
# List undoable runs
teaagent agent runs --undoable

# Undo a specific run
teaagent agent undo --run-id <run_id>
```

### Git-based rollback (if workspace uses git)

```bash
# See what the agent changed
git diff HEAD~1

# Revert agent commits
git revert HEAD --no-edit

# Or hard reset (destructive — confirm first)
git stash   # save any work-in-progress
git reset --hard <commit_before_agent_ran>
```

### Post-incident

1. Verify the undo completed successfully: `git diff HEAD`
2. Review what triggered the incorrect behavior in the audit log
3. Add the problematic tool call pattern to a deny preset if appropriate

---

## RB-08: LLM Provider Outage

**When:** The configured LLM provider returns 5xx errors, timeouts, or is unreachable.

### Diagnosis

```bash
# Run provider smoke test
teaagent model smoke --provider claude

# Check all provider health
teaagent doctor providers
```

### Failover to alternate provider

```bash
# Switch to backup provider for this run
teaagent run "task" --provider gpt --model gpt-4o

# Or update config temporarily
export TEAAGENT_PROVIDER=gpt
export OPENAI_API_KEY=sk-...
```

### Switch via config profile

If you have a backup profile configured in `.teaagent/config.json`:

```bash
teaagent run "task" --profile backup-provider
```

### Post-incident

1. Add a backup provider profile to config
2. Set up provider health monitoring (see [Monitoring and Alerting](monitoring-and-alerting.md))

---

## RB-09: MCP Trust Policy Failure

**When:** MCP server connection fails with trust error; `teaagent mcp trust_list` shows no trusted servers; `TEAAGENT_MCP_TRUST_KEY` is missing or rotated.

### Diagnosis

```bash
# List trust policies
teaagent mcp trust_list

# Inspect a specific policy
teaagent mcp trust_inspect <server_id>
```

### Recovery

```bash
# If trust key was rotated, re-encrypt policies with new key
export TEAAGENT_MCP_TRUST_KEY=<new-key>

# Re-allow a server
teaagent mcp trust_allow <server_id>

# If trust manifest is corrupted
mv .teaagent/mcp-trust.json .teaagent/mcp-trust.json.bak
teaagent mcp trust_allow <server_id>   # recreates the manifest
```
