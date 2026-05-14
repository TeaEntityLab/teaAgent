# TeaAgent CLI

## Install

For local development, install the package in editable mode:

```bash
python3 -m pip install -e .
```

Then run:

```bash
teaagent --help
```

Use a JSON config file for common optional defaults:

```bash
teaagent --config .teaagent/config.json model smoke gpt
```

If `--config` is omitted and `.teaagent/config.json` exists, it is loaded automatically.

Supported keys include `root`, `model`, `provider`, and `permission_mode`. Positional arguments such as `agent run <provider>` remain explicit.

Profiles can override top-level defaults:

```json
{
  "model": "gpt-4o-mini",
  "profiles": {
    "ci": {"model": "gpt-4o-mini", "permission_mode": "read-only"}
  }
}
```

```bash
teaagent --profile ci model smoke gpt
```

Print shell completion snippets:

```bash
teaagent completion bash
teaagent completion zsh
teaagent completion fish
```

Inspect and prune audit logs:

```bash
teaagent audit list --limit 20
teaagent audit show <run_id>
teaagent audit prune --days 30 --keep 20
teaagent audit prune --all
```

`audit prune` requires an explicit deletion selector: `--days`, `--keep`, or `--all`.

You can also run without installing the console script:

```bash
python3 -m teaagent.cli --help
```

## GraphQLite

Run all environment checks:

```bash
teaagent doctor all --provider gpt
```

Check the GraphQLite runtime:

```bash
teaagent doctor graphqlite
```

Run a smoke query:

```bash
teaagent graphqlite smoke
```

Run a Cypher query:

```bash
teaagent graphqlite query "MATCH (n:SmokeTest) RETURN n.name"
```

Use a persistent SQLite file:

```bash
teaagent graphqlite smoke --database ./graph.db
teaagent graphqlite query "MATCH (n) RETURN n" --database ./graph.db
```

## Interactive TUI

Start the interactive terminal UI:

```bash
teaagent tui
```

Or without installing the console script:

```bash
python3 -m teaagent.cli tui
```

Inside the TUI:

```text
help
doctor
clarify Improve the CLI
provider gpt
model gpt-4o-mini
route-model on
route review this patch
root /path/to/repo
destructive off
progress on
permission prompt
approve write-file-1
approvals
ask Inspect this repo and summarize the test suite
ask --clarify Update docs/cli.md to document clarify and verify tests pass
memory add Prefer read-only mode for audit tasks
memory search audit tasks
smoke
query MATCH (n:SmokeTest) RETURN n.name
use ./graph.db
exit
```

Start with a persistent database:

```bash
teaagent tui --database ./graph.db
```

Start with model and workspace defaults:

```bash
teaagent tui --provider claude --model claude-3-5-sonnet-latest --root /path/to/repo
```

Allow destructive tools inside `ask` commands:

```bash
teaagent tui --allow-destructive
```

Use a permission mode for `ask` commands:

```bash
teaagent tui --permission-mode read-only
teaagent tui --permission-mode workspace-write
teaagent tui --permission-mode prompt
teaagent tui --permission-mode allow
teaagent tui --permission-mode danger-full-access
```

## Model Adapters

List supported providers:

```bash
teaagent model providers
```

Check provider configuration:

```bash
teaagent doctor model claude
teaagent doctor model gpt
teaagent doctor model gemini
teaagent doctor model openrouter
teaagent doctor model ollama
teaagent doctor model vllm
teaagent doctor model opencodezen-go
```

Run a smoke prompt:

```bash
teaagent model smoke gpt --prompt "Reply with exactly: ok"
teaagent model smoke claude --prompt "Reply with exactly: ok"
teaagent model smoke gemini --prompt "Reply with exactly: ok"
```

Preview deterministic task routing for a provider:

```bash
teaagent model route "review this patch for regressions" --provider gpt
teaagent model route "update docs/cli.md" --provider claude
```

Routing classifies tasks into `review`, `test`, `code`, `docs`, `search`, or `general`, then chooses a provider-specific model. Explicit `--model` still wins.

Environment variables:

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
export OLLAMA_API_KEY=...    # optional for local deployments
export VLLM_API_KEY=...      # optional for local deployments
export OPENCODEZEN_API_KEY=...
```

Optional base URL overrides:

```bash
export ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
export OPENAI_BASE_URL=https://api.openai.com/v1
export GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
export OLLAMA_BASE_URL=http://localhost:11434/v1
export VLLM_BASE_URL=http://localhost:8000/v1
export OPENCODEZEN_BASE_URL=https://opencode.ai/zen/go/v1
```

Optional proxy/TLS settings:

```bash
export HTTPS_PROXY=http://proxy.internal:8080
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem
export SSL_CERT_FILE=/path/to/ca-bundle.pem
export TEAAGENT_TLS_CLIENT_CERT=/path/to/client.crt
export TEAAGENT_TLS_CLIENT_KEY=/path/to/client.key
```

## Workspace Tools

List the repo-operation tool metadata that will be exposed to the agent runner:

```bash
teaagent workspace tools
```

Use another workspace root:

```bash
teaagent workspace tools --root /path/to/repo
```

Registered tools:

- `workspace_read_file`: read UTF-8 files under the root.
- `workspace_read_file_hashed`: read UTF-8 files with `LINE#HASH|content` anchors.
- `workspace_write_file`: write UTF-8 files under the root; destructive.
- `workspace_apply_patch`: replace one exact text span; destructive.
- `workspace_edit_at_hash`: edit one line only if its hash anchor still matches; destructive.
- `workspace_list_files`: list files by glob.
- `workspace_search_text`: regex search text files.
- `workspace_git_status`: run `git status --short`.
- `workspace_run_shell_inspect`: run inspect-safe shell commands without destructive permission.
- `workspace_run_shell_mutate`: run arbitrary shell commands; destructive.
- `workspace_run_shell`: compatibility alias for `workspace_run_shell_mutate`; destructive.

All path-based tools reject paths that escape the configured workspace root.

## Clarification

Score a task for ambiguity before invoking a model:

```bash
teaagent clarify "Improve this project"
```

The result includes an ambiguity score, missing fields, and at most one next question.

Use the same gate before an autonomous run:

```bash
teaagent agent run gpt "Improve this project" --clarify
```

If key details are missing, TeaAgent returns `status: needs_clarification` and does not call the model. If the task is concrete enough, TeaAgent injects a structured task specification into the agent prompt.

Inside TUI:

```text
clarify Improve this project
ask --clarify Update docs/cli.md to document clarify and verify tests pass
```

## Memory Catalog

Store reusable workspace observations under `.teaagent/memory.jsonl`:

```bash
teaagent memory add "Prefer read-only mode for audit tasks" --tag policy
teaagent memory list
teaagent memory search "audit tasks"
teaagent memory show <memory_id>
```

Use another workspace root:

```bash
teaagent memory add "GraphQLite requires pysqlite3 on macOS" --tag graphqlite --root /path/to/repo
```

Agent runs search the catalog with the task text and inject matching memories into the model prompt.

Inside TUI:

```text
memory add Prefer read-only mode for audit tasks
memory list
memory search audit tasks
memory show <memory_id>
```

## Ultrawork (background workers)

Run an agent task as a detached background worker that survives the parent shell:

```bash
teaagent ultrawork start gpt "Long-running task" --root /path/to/repo --heartbeat 5 --label nightly
```

The store under `.teaagent/ultrawork/` keeps a JSON record per worker plus a per-worker log file. Inspect or stop workers:

```bash
teaagent ultrawork list --root /path/to/repo
teaagent ultrawork show <worker_id> --root /path/to/repo
teaagent ultrawork stop <worker_id> --root /path/to/repo
```

`list` reports `alive` based on a PID liveness check; `stop` sends SIGTERM (then SIGKILL if it does not exit within the timeout).

## Heartbeat

Emit a periodic `heartbeat` audit event while a run is in progress so observers can confirm liveness:

```bash
teaagent agent run gpt "Long-running task" --heartbeat 5
```

Inspect liveness for a persisted run id:

```bash
teaagent agent status <run_id> --root /path/to/repo
```

The status payload reports `status` (`running` / `completed` / `failed:*`) and the most recent heartbeat tick and timestamp.

Inside TUI:

```text
heartbeat 5
ask Long-running task
status <run_id>
```

## MCP Server

Serve the workspace tool pack to other MCP clients over stdio JSON-RPC:

```bash
teaagent mcp serve --root /path/to/repo
```

Or over Streamable HTTP transport on loopback:

```bash
teaagent mcp serve --http --root /path/to/repo --port 7330
```

Streamable HTTP details:

- POST `/mcp`: send one JSON-RPC request or a batch. Server responds with `application/json`.
- GET `/mcp`: open a `text/event-stream` keep-alive (no server-initiated notifications yet).
- DELETE `/mcp`: terminate the session.
- `initialize` returns a fresh `Mcp-Session-Id` response header. Every later request must echo it.
- Default bind is `127.0.0.1` only. Use `--host 0.0.0.0` deliberately and pair it with auth.
- `--auth-token TOKEN` requires `Authorization: Bearer TOKEN` on every request.
- `--allowed-origin URL` may be repeated to whitelist browser Origin headers. Default: allow all.

Supported methods: `initialize`, `tools/list`, `tools/call`. Each tool is exposed with its `inputSchema` and read-only / destructive / idempotent annotations. Tool errors are returned as `result.isError = true` rather than JSON-RPC errors so the client can recover.

## Subagent Delegation

Expose a `subagent` tool so the model can delegate one focused sub-task to a fresh agent run that shares the same workspace tools, ApprovalPolicy, RunBudget, and permission mode:

```bash
teaagent agent run gpt "Plan and execute the cleanup" --subagent --max-subagent-depth 1
```

Each sub-run is persisted under `.teaagent/runs/*.jsonl` with its own `run_id` so it can be inspected or resumed.

Inside TUI:

```text
subagent on
ask Plan and execute the cleanup
```

## Preflight

Summarize clarification, routing, matching memories, permission state, and tool count without calling a model:

```bash
teaagent agent preflight gpt "review this patch for regressions in the test suite" --route-model
```

Exit code is `0` when the task is concrete enough and `2` when it still needs clarification. Pair with `--permission-mode workspace-write` or `--memory-limit 10` as needed.

Inside TUI:

```text
route-model on
preflight review this patch for regressions in the test suite
```

## Agent Run

Run one model-driven task with the workspace tool pack:

```bash
teaagent agent run gpt "Inspect this repo and summarize the test suite"
```

Use another provider:

```bash
teaagent agent run claude "List the Python files"
teaagent agent run gemini "Search for GraphQLite usage"
teaagent agent run openrouter "Explain pyproject.toml"
teaagent agent run opencodezen-go "Inspect workspace tools"
```

Use a specific workspace root:

```bash
teaagent agent run gpt "Read AGENTS.md" --root /path/to/repo
```

Enable task-based model routing for one run:

```bash
teaagent agent run gpt "review this patch for regressions" --route-model
```

Inside TUI, use `route-model on` to apply routing to later `ask` commands. Use `route <task>` to preview the selected category and model.

By default, destructive tools are blocked. To allow file writes, patching, or shell commands:

```bash
teaagent agent run gpt "Create a TODO.md summary" --allow-destructive
```

Approve one exact destructive tool call id while staying in `prompt` mode:

```bash
teaagent agent run gpt "Create a TODO.md summary" --approve-call-id write-todo-1
```

The model decision must use the approved `call_id` for that exact destructive tool call. Other destructive calls remain blocked.

For interactive HITL approval during a CLI run, use:

```bash
teaagent agent run gpt "Create a TODO.md summary" --hitl-approval
```

Without `--hitl-approval`, an unapproved destructive tool in `prompt` mode returns `pending_approval` with the required `call_id`. Re-run with `--approve-call-id <call_id>` or use `agent resume` with the same approval token.

Prefer explicit permission modes for regular use:

```bash
teaagent agent run gpt "Inspect this repo" --permission-mode read-only
teaagent agent run gpt "Update one markdown file" --permission-mode workspace-write
teaagent agent run gpt "Run tests and patch failures" --permission-mode prompt
teaagent agent run gpt "Run approved automation" --permission-mode allow
```

Permission modes:

- `read-only`: blocks every destructive tool.
- `workspace-write`: allows file write/patch/hash-edit tools, blocks shell mutation.
- `prompt`: destructive tools pause for HITL approval or require an approval token.
- `allow`: allows destructive tools for the session.
- `danger-full-access`: allows destructive tools; reserve for trusted automation.

The model must return JSON decisions internally:

```json
{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"AGENTS.md"},"call_id":"read-agents"}
{"type":"final","content":"Done"}
```

Agent runs are persisted under `.teaagent/runs/*.jsonl` in the selected workspace root.

List recent runs:

```bash
teaagent agent runs --root /path/to/repo
```

Show one run record:

```bash
teaagent agent show <run_id> --root /path/to/repo
```

Resume the original task from a persisted run id with optional new approval tokens or settings:

```bash
teaagent agent resume gpt <run_id> --root /path/to/repo --approve-call-id write-1
```

By default, resume replays already-completed `tool_call_completed` observations into the new run's context so the model does not have to redo prior tool calls. If the original run paused with `pending_approval`, the pending `call_id` is auto-added to the approval list and reported back as `auto_approved_call_id` in the response payload.

Pass `--fresh-restart` to skip replay and re-run the original task from scratch.

Inside TUI:

```text
ask write TODO.md       # prompts y/N when a destructive call is proposed
approve write-todo-1
approvals
unapprove write-todo-1
runs
show <run_id>
resume <run_id>
```
