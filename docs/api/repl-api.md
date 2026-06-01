# REPL API Specification

The REPL (Read-Eval-Print Loop) is the interactive shell available inside `teaagent chat` / `teaagent tui`. Commands are entered at the `> ` prompt. A leading `/` is optional — `/help` and `help` are equivalent.

**Source:** `teaagent/tui/_commands.py`, `teaagent/tui/__init__.py`

---

## Command Index

### Help & Diagnostics

#### `help`

Display the full command reference.

```
help
```

**Output:** Formatted table of all available commands.

---

#### `setup [write-env] [provider]`

Run the guided interactive setup wizard.

```
setup
setup write-env claude
```

| Argument | Description |
|----------|-------------|
| `write-env` | Write resolved API keys to `.env` |
| `provider` | Provider to configure (claude, gpt, gemini, …) |

---

#### `doctor`

Check GraphQLite database runtime health.

```
doctor
```

**Output:** Pass/fail for database connectivity, schema version, and migration status.

---

### Provider & Model Configuration

#### `provider <name>`

Set the active LLM provider for this session.

```
provider claude
provider gpt
provider gemini
provider openrouter
provider ollama
provider vllm
provider workers-ai
provider aigateway
```

**Error cases:**
- Unknown provider name → `Unknown provider: <name>. Run 'model providers' to list available.`
- Missing API key → `API key not set. Set <ENV_VAR> or run 'setup'.`

---

#### `model <name|default>`

Override the model for the current session.

```
model claude-opus-4-8
model default
```

`default` clears any override, reverting to the provider default.

---

#### `route-model <on|off>`

Enable or disable task-based model routing.

```
route-model on
route-model off
```

When on, the router selects a model based on task complexity before each run.

---

#### `route <task>`

Preview which model the router would select for a task without running it.

```
route "refactor the auth module"
```

**Output:** `→ claude-opus-4-8 (complexity: high, reason: multi-file refactor)`

---

#### `complexity <task>`

Score task complexity as `high`, `medium`, or `low`.

```
complexity "add a docstring to utils.py"
```

**Output:**
```
Complexity: low
Rationale: Single-file, read-only, no branching logic.
```

---

#### `estimate <task>`

Estimate token budget for a task before running.

```
estimate "migrate the database schema"
```

**Output:**
```
Estimated input tokens:  ~4,200
Estimated output tokens: ~1,800
Estimated cost:          ~$0.04
```

---

### Workspace & Execution Settings

#### `root <path>`

Set the workspace root for subsequent runs.

```
root /Users/me/project
root .
```

---

#### `destructive <on|off>`

Allow or block destructive tools (file writes, shell commands, patches).

```
destructive on
destructive off
```

---

#### `progress <on|off>`

Enable or disable streaming progress events to the output pane.

```
progress on
progress off
```

---

#### `stream <on|off>`

Enable or disable streaming model output token-by-token.

```
stream on
stream off
```

---

#### `subagent <on|off>`

Expose or hide the `subagent` delegation tool in the active tool set.

```
subagent on
subagent off
```

---

#### `heartbeat <seconds>`

Set heartbeat emission interval. `0` disables heartbeats.

```
heartbeat 30
heartbeat 0
```

---

#### `effort <level>`

Set effort throttling for the model.

```
effort low
effort normal
effort high
effort unlimited
```

| Level | Description |
|-------|-------------|
| `low` | Fewer iterations, faster, cheaper |
| `normal` | Default balanced setting |
| `high` | More iterations, deeper reasoning |
| `unlimited` | No iteration cap |

---

### Chat & Sessions

#### `chat <on|off>`

Enable or disable multi-turn chat mode. When on, message history is preserved across runs.

```
chat on
chat off
```

---

#### `session new`

Start a new chat session, discarding current history.

```
session new
```

---

#### `session list`

List all saved sessions.

```
session list
```

**Output:**
```
ID                      Created              Messages  Label
──────────────────────  ───────────────────  ────────  ─────────────────
abc123                  2026-06-01 09:14     12        auth refactor
def456                  2026-06-02 11:30     3         (untitled)
```

---

#### `session switch <id>`

Switch to a saved session, loading its message history.

```
session switch abc123
```

---

#### `session clear`

Clear all messages in the current session (does not delete the session record).

```
session clear
```

---

#### `session show`

Show details of the current session including message count, focus stack depth, and label.

```
session show
```

---

### Permissions & Approval

#### `permission <mode>`

Set the permission mode for this session.

```
permission read-only
permission workspace-write
permission prompt
permission allow
permission danger-full-access
```

See [Permission Modes](cli-api.md#permission-modes) in the CLI spec for mode descriptions.

---

#### `approve <call_id>`

Pre-approve a specific tool call by its call ID.

```
approve call_abc123
```

---

#### `unapprove <call_id>`

Remove a pre-approval for a tool call.

```
unapprove call_abc123
```

---

#### `approvals`

List all pre-approved call IDs for this session.

```
approvals
```

---

#### `approvals subagents`

Show the subagent approval queue.

```
approvals subagents
approvals subagents approve <id>
approvals subagents deny <id>
approvals subagents approve-all
approvals subagents deny-all
```

---

#### `permissions`

List configured approval presets.

```
permissions
```

---

### Task Planning & Execution

#### `clarify <task>`

Score task ambiguity and surface clarifying questions without running the model.

```
clarify "improve the API"
```

**Output:**
```
Ambiguity score: 8/10 (HIGH)
Clarifying questions:
  1. Which API — internal Python API or REST endpoints?
  2. What does "improve" mean — performance, readability, error handling?
  3. Which files are in scope?
```

---

#### `preflight <task>`

Show routing, memory context, and tool plan for a task without calling the model.

```
preflight "add pagination to /users endpoint"
```

---

#### `plan <task>`

Write a plan artifact to `.teaagent/plans/` without executing anything.

```
plan "migrate SQLite to PostgreSQL"
```

**Output:** Path to the written plan file.

---

#### `daily [task]`

Show agent readiness, recent runs, harness health, and token budget. Optionally scoped to a task.

```
daily
daily "auth module work"
```

---

#### `run <task>` / `ask <task>`

Run an agent task from within the REPL. Both are identical.

```
run "add type hints to models.py"
ask "explain the approval flow"
ask --clarify "refactor the router"
```

| Flag | Description |
|------|-------------|
| `--clarify` | Score ambiguity first; abort if score ≥ threshold |

**Output (streaming):** Progress events, then final answer.

---

#### `status <run_id>`

Show heartbeat liveness status for a running or completed run.

```
status run_abc123
```

---

#### `resume <run_id>`

Re-run a task from a persisted run ID, replaying state up to the checkpoint.

```
resume run_abc123
```

---

#### `undo [run_id]`

Restore workspace files from the undo journal. Defaults to the most recent run.

```
undo
undo run_abc123
```

**Behavior:** Interactive diff shown before restoring. Requires confirmation unless `--force` was set on original run.

---

### Memory & Context

#### `memory add <text>`

Add a memory entry.

```
memory add "Use pytest-asyncio for all async tests"
```

---

#### `memory list`

List recent memory entries.

```
memory list
```

---

#### `memory search <query>`

Full-text search over memory entries.

```
memory search "async testing"
```

---

#### `memory show <id>`

Show details of a specific memory entry.

```
memory show mem_abc123
```

---

#### `context list [prefix]`

List workspace files available for `@`-mention auto-complete.

```
context list
context list src/
```

---

#### `pin <path>`

Pin a file for live sync — its contents are injected into the context on every run.

```
pin src/auth.py
```

---

#### `unpin <path>`

Remove a pinned file.

```
unpin src/auth.py
```

---

#### `pinned`

List all currently pinned files.

```
pinned
```

---

#### `compact`

Compact the current session's message history, summarising old exchanges to reduce token usage.

```
compact
```

---

#### `cost`

Show accumulated token and cost summary for the current session.

```
cost
```

**Output:**
```
Session cost summary
  Input tokens:   12,450
  Output tokens:   3,210
  Estimated cost: $0.18
  Runs this session: 4
```

---

#### `budget`

Show remaining token and cost budget for the current session.

```
budget
```

---

### Run Management

#### `runs`

List persisted runs for the current workspace.

```
runs
```

---

#### `show <run_id>`

Show details of a specific persisted run.

```
show run_abc123
```

---

#### `background`

Suspend the current session to a background task and return to the shell.

```
background
```

Resume later with `teaagent resume <run_id>` or `teaagent attach <run_id>`.

---

### Database & Experimentation

#### `use <database>`

Switch the active GraphQLite database. Use `:memory:` for an in-memory ephemeral store.

```
use :memory:
use .teaagent/graph.db
```

---

#### `smoke`

Create a SmokeTest node in the current database to verify connectivity.

```
smoke
```

---

#### `query <cypher>`

Execute a raw Cypher query against the current GraphQLite database.

```
query "MATCH (n:Run) RETURN n LIMIT 5"
```

---

#### `parallel <optA> <optB> ...`

Start parallel experiment branches with different approaches.

```
parallel "use SQLAlchemy" "use raw psycopg2" "use Tortoise ORM"
```

Each branch runs the same task with a different approach hint. Results are shown side-by-side.

---

#### `select <option>`

After `parallel`, merge the selected branch into the workspace.

```
select 2
```

---

#### `cancel`

Cancel active parallel experiments.

```
cancel
```

---

#### `conflict`

Enter conflict resolution mode for a merge conflict.

```
conflict
```

**Sub-commands while in conflict mode:**

| Key | Action |
|-----|--------|
| `o` | Accept current branch (ours) |
| `t` | Accept incoming branch (theirs) |
| `n` | Move to next conflicted file |
| `p` | Move to previous conflicted file |
| `a` | Abort the merge |

---

#### `checkpoint`

Create a git checkpoint (commit) of the current workspace state.

```
checkpoint
```

---

### System

#### `mcp`

Print MCP server integration hint.

```
mcp
```

---

#### `exit` / `quit`

Exit the REPL and TUI.

```
exit
quit
```

---

## Error Handling

All commands follow the same error format:

```
Error: <short description>
  → <actionable hint>
```

Example:
```
Error: No persisted run found with ID 'run_xyz'.
  → Run 'runs' to list available run IDs.
```

Commands that fail do not exit the REPL — control returns to the prompt.

---

## `@`-Mention Syntax

Within a `run` or `ask` task string, files can be injected by mentioning them with `@`:

```
ask "add error handling to @src/auth.py and @src/utils.py"
```

The file contents are appended to the context before the model call. Tab-completion is available for `@` mentions if `context list` is populated.
