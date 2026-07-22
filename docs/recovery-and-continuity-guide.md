# Recovery And Continuity Guide
# As of 2026-08-25

This guide answers one question: "I need to stop, recover, continue, or revert. What is
the least surprising path?"

## Resume vs attach vs interactive review

| Situation | Prefer | Why |
|-----------|--------|-----|
| You have a run id and want to inspect changes | `teaagent agent interactive-review <run_id>` | Review is the most reliable current path. |
| You have a suspended run and the resume path is known-good | `teaagent agent resume <run_id>` | Intended continuity path when task context is stored. |
| You only want to see metadata | `teaagent agent show <run_id>` | Read-only and low risk. |
| You want a live TUI cockpit | `teaagent tui --root .` | Useful for status, approvals, and run listing. |

## Undo mechanisms

TeaAgent provides two undo paths that are explicitly labeled in output:

### Journal undo (mechanism: "journal undo")

The preferred path. An undo journal records pre-write state of every workspace file
touched by ``workspace_write_file``, ``workspace_apply_patch``, or
``workspace_edit_at_hash``. Calling undo replays the journal in reverse:

- Files that **did not exist** before the run are **deleted**.
- Files that **did exist** are **restored** to their original content.

Triggered by:
- ``teaagent undo --last`` (CLI, no git repo or git sandbox unavailable)
- ``/undo`` in Chat REPL (ChatSessionController)
- ``/undo`` in TUI (when undo journal is available)

Output includes ``"mechanism": "journal undo"`` in the payload and
``"method": "journal"``.

### Checkpoint restore (mechanism: "checkpoint restore")

The fallback path used when a git sandbox or stash checkpoint exists. This is a
git-level operation that restores the workspace to the pre-run state via git
branch rollback or stash pop.

Triggered by:
- ``teaagent undo --last`` (CLI, when git repo exists and journal is absent or
  rollback succeeds first)
- ``/undo`` in TUI (when no undo journal is found and a checkpoint was created)

Output includes ``"mechanism": "checkpoint restore"`` in the payload and
``"method": "checkpoint"`` (previously ``"git"``).

### Which path is used?

The system prefers journal undo when a journal exists. In the CLI, git sandbox
rollback is attempted first if the workspace is a git repository; if that fails,
the journal is tried next. In TUI/REPL, the controller tries the journal first.

| Operation | Scope | Safer when |
|-----------|-------|------------|
| Journal undo | Last run's touched files via undo journal. | You need to preserve unrelated manual edits. |
| Checkpoint restore | Git-level workspace state restore. | You intentionally created a checkpoint and understand the scope. |
| Git manual revert | Whatever you select. | You need precise human-controlled recovery. |

## Background vs suspend

Current recommended wording:

- "Suspended" means the run stopped and left a record.
- "Background" should mean work continues somewhere else.
- If a path does not continue work, do not describe it as background execution.
- In TeaAgent's current REPL and TUI flows, `/background` is a suspension checkpoint
  with recovery guidance, not a true detached background handoff.

Operator rule: if a command prints a run id, inspect it with `agent show` before assuming
work is still running.

## Pending approval

When blocked on approval:

1. Read the tool name.
2. Read the exact input and path scope.
3. Approve only the exact call you understand.
4. Prefer rejecting and rerunning with narrower scope when the request is broad.

### Approval blocked — how to approve

If a run is stuck with `status: "pending_approval"`:

**Option 1 — Resume with approval token (recommended):**

```bash
# The paused run shows the tool + arguments in the approval payload; pre-approve
# by payload digest. (--approve-call-id was removed in G-P2-2 and is now inert.)
teaagent agent resume opencodezen-go <run_id> --approve-scoped <tool>:<sha256>
```

**Option 2 — Re-run with broader permission:**

```bash
teaagent agent run gpt "your task" --permission-mode allow
# or allow file writes but not shell mutation:
teaagent agent run gpt "your task" --permission-mode workspace-write
```

**Option 3 — Approve in TUI:**
Inside `teaagent tui`, the TUI prompts `y/N` before destructive operations in `prompt` mode.

## Provider missing

### Symptom

`teaagent agent run gpt "task"` fails with "API key not found" or provider errors.

### Recovery

**Check if the key is set:**

```bash
teaagent doctor model gpt
teaagent doctor model opencodezen-go
```

**Set up provider keys (recommended persistent path):**

```bash
cp scripts/providers_env.zsh ~/.teaagent/providers_env.zsh
# Edit the file and fill in your keys
${EDITOR:-vi} ~/.teaagent/providers_env.zsh
echo 'source ~/.teaagent/providers_env.zsh' >> ~/.zshrc
source ~/.zshrc
```

**Quick alternative (this session only):**

```bash
export OPENAI_API_KEY="sk-..."
export OPENCODEZEN_API_KEY="..."
```

**Test the connection:**

```bash
teaagent model smoke gpt --prompt "Reply with exactly: ok"
```

**Setup wizard:**

```bash
teaagent setup --root . --provider gpt --write-env
teaagent doctor providers --wizard --root .
```

## Read-only write block

### Symptom

The agent says it cannot write files because the permission mode is `read-only`.

```
"tool execution blocked: permission mode read-only does not allow workspace_write_file"
```

### Recovery

This is intentional safety behavior. To allow file writes:

**Switch to workspace-write (file edits only, no shell mutation):**

```bash
teaagent agent run gpt "update README" --permission-mode workspace-write --root .
```

**Switch to prompt mode (approval required for destructive tools):**

```bash
teaagent agent run gpt "fix failing tests" --permission-mode prompt --root .
```

**In TUI:**

```
permission workspace-write
# or
permission prompt
```

The first run in the golden path intentionally uses `read-only` — switch modes only when you need mutations.

## Budget exceeded

### Symptom

The run stops with `status: "failed:budget"` or the agent reports it cannot continue because the iteration/tool-call limit was reached.

### Recovery

**Increase iteration limit:**

```bash
teaagent agent run gpt "your task" --max-iterations 50
```

**Increase tool-call limit:**

```bash
teaagent agent run gpt "your task" --max-tool-calls 100
```

**Set a cost cap (cents):**

```bash
teaagent agent run gpt "your task" --max-estimated-cost-cents 500
```

**Use a leaner context profile to reduce token pressure:**

```bash
teaagent agent run gpt "your task" --context-profile lean
```

**Preflight first to estimate token budget:**

```bash
teaagent agent preflight gpt "your task" --root .
# Check token_budget in the output for green/yellow/red pressure
```

## Undo unavailable

### Symptom

`teaagent undo --last` fails or `/undo` in TUI shows "nothing to undo" when you expected a rollback.

### Common causes

| Cause | What to do |
|-------|-----------|
| **No undo journal was recorded.** The run did not write any workspace files. | Nothing to undo — inspect the run with `teaagent agent show <run_id>` to confirm no file changes occurred. |
| **The undo journal file was deleted or cleaned up.** | Check if `.teaagent/undo.jsonl` exists. If missing, use git to review changes: `git diff` or `git stash`. |
| **You are in a non-git workspace and no journal exists.** | TeaAgent's checkpoint restore requires a git repo. For non-git workspaces, undo relies on the journal. If neither is available, revert manually. |
| **Checkpoint restore was used instead of journal undo.** | Checkpoint restore is a full workspace revert (git-level). If you had unrelated manual edits, they may have been reverted too. In the future, keep unrelated edits committed before running undo. |

### Recovery

**Inspect what the last run did:**

```bash
teaagent agent show <run_id> --root .
cat .teaagent/runs/<run_id>.jsonl
```

**Manual recovery options:**

```bash
# Git-based recovery
git status
git diff HEAD
git checkout -- <file>   # restore a specific file
git stash                # stash changes for later inspection

# Journal-based recovery (if journal exists)
# Journal records are in .teaagent/undo.jsonl
# Files are restored to pre-write state when journal undo succeeds
```

**Verify undo mechanism used:**

TUI `/undo` and CLI `teaagent undo --last` explicitly label whether journal undo or checkpoint restore was used. Check the output for `"mechanism": "journal undo"` or `"mechanism": "checkpoint restore"`.


## Interrupted mutating tool execution

If a process stops after `tool_call_started` but before a completion/failure and
checkpoint save, the effect is **unconfirmed**. Current TeaAgent does not
reconcile that unmatched start. Blindly rerunning the same logical mutation can
apply a non-idempotent effect again.

Before resume or rerun:

1. Inspect the stored run: `teaagent agent show <run_id> --root .`.
2. Inspect local state with `git status` and `git diff HEAD`.
3. Check the external provider or target system when the tool could have changed
   remote state.
4. Use the documented journal/checkpoint undo only after confirming its scope.
5. Resume or issue a new mutation only after the first attempt is reconciled or
   deliberately abandoned.

The 2026-08-25 roadmap tracks the missing runtime guard as EFX-001. This advice
does not claim exactly-once behavior or generic external-effect reversal.

## Persistence error handling (P1-C fix)

As of 2026-06-05, `ChatSessionController` handles persistence failures with classified
warnings instead of broad exception swallowing or uncontrolled crashes:

- **Store save failures** (OSError, RuntimeError): logged as `WARNING` with run_id; the
  task result is still returned to the caller.
- **Undo journal save failures** (OSError, RuntimeError): logged as `WARNING` with
  run_id; the task result is still returned.
- **Undo restore failures** (OSError, RuntimeError, ValueError, JSONDecodeError): logged
  as `WARNING` and surfaced to the user as `[TeaAgent] journal undo error:`.
- **Unexpected exceptions** (e.g. AttributeError, TypeError): still propagate so they
  are visible in test suites and operator tooling.

The controller exposes a `_store_factory` test seam so that persistence failure
scenarios can be verified without mocking the filesystem. See
`tests/test_controller_persistence.py`.

## Known broken or risky paths

| Path | Status | Safer alternative |
|------|--------|-------------------|
| `teaagent agent run --background <run_id>` | Can treat run id as a task. | `teaagent agent interactive-review <run_id>` |
| TUI `/cost` as spend truth | Known display gap. | Run summary or provider dashboard. |
| TUI `/undo` when no journal exists | Falls back to checkpoint restore (explicitly labeled). | Check git status, then use `teaagent chat` `/undo` or manual git review. |
| `teaagent chat <task>` | Needs execute/reject fix. | Use `teaagent agent run "<task>"` or REPL prompt after launch. |
| Mutating tool started with no completion/failure after process interruption | Effect is unconfirmed; blind rerun can duplicate it. | Inspect the run, workspace, and external system; do not retry until reconciled (EFX-001). |

## Continuity acceptance criteria

A continuity feature is daily-driver ready only when:

- The user sees one canonical command for the current state.
- The run id maps to a stored task and observations.
- Pending approvals survive the transition.
- The command either continues safely or refuses clearly.
- The audit log records the transition.
- An unmatched mutating-tool start is surfaced as unconfirmed and cannot be
  blindly redispatched without new authority.
