# TeaAgent CLI

**Last reviewed:** 2026-06-05

Choose your surface: [USAGE.md — Choose Your Surface](USAGE.md#choose-your-surface) (CLI, TUI, VS Code, MCP, ACP, A2A, ANP, managed runtime).

## Install

For local development, install the package in editable mode:

```bash
python3 -m pip install -e .
```

Install optional enhanced TUI support:

```bash
python3 -m pip install -e ".[tui]"
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

Workspace defaults also load from `.teaagent/config.toml` when `config.json` is absent
(`provider`, `context_profile`, `heartbeat`, `daily_cost_cap_cents`, and related keys).

After setup, provider comes from config — two-word daily use:

```bash
teaagent daily "what to do today"
teaagent run "fix the failing test" --dry-run
```

Top-level shortcuts (same as `agent` subcommands; provider comes from config when omitted):

```bash
teaagent daily gpt
teaagent run gpt "summarize repo"
teaagent resume gpt <run_id>
```

Daily ergonomics:

```bash
teaagent status                    # one-line token/approval/run status
teaagent yesterday                 # runs from the previous calendar day
teaagent recall --limit 5
teaagent session list
teaagent session switch <session_id>   # switch active session (with fuzzy matching on partial IDs)
teaagent recipes list
teaagent recipes run review-staged --print-only
teaagent background list
teaagent agent attach <run_id> --follow
teaagent agent attach <run_id> --resume
teaagent model capabilities --per-model --provider gpt
teaagent ci review --provider gpt
teaagent approval grant workspace_write_file --scope session --root .
teaagent approval list --root .
teaagent approval check workspace_write_file --path src/foo.py --root .
teaagent approval revoke <grant_id> --root .
teaagent guidance
teaagent agent run gpt "read @README.md" --dry-run
teaagent agent daily gpt --write-journal
teaagent watch --interval 30
```

### Live streaming

| Flag | Effect |
|------|--------|
| `--progress` | Emit iteration/tool progress lines to stderr (default on when stderr is a TTY). |
| `--no-progress` | Disable progress lines. |
| `--stream` | Stream user-visible final-answer text (filters structured decision JSON). |
| `--stream-raw` | With `--stream`, emit raw model tokens. |
| `--json-stream` | Emit normalized NDJSON events on stdout (`text_delta`, `tool_call_started`, …). |

TUI equivalents: `progress on/off` (default **on**), `stream on/off`.

Top-level aliases expose the same flags: `teaagent run gpt "task" --stream` (equivalent to `teaagent agent run ...`).

`teaagent agent attach <run_id> --follow` tails the audit JSONL with native directory watch on Linux (inotify) and fast stat-based follow elsewhere.

```bash
teaagent agent run gpt "fix the failing test" --progress --stream
teaagent agent run gpt "long task" --json-stream 2>/dev/null | jq -c '.type'
teaagent agent attach <run_id> --follow --json-stream
```

### Background runs and attach

Detached runs use `agent run --background` (writes under `.teaagent/background/`). Use `teaagent background list` and `teaagent background show <background_id>` for PID liveness, log path, and run ID parsed from worker stdout. Attach always targets the **audit run id** (not the background id):

```bash
teaagent agent run "long task" --background --root .
teaagent background list --root .
teaagent agent attach <run_id> --follow --root .
teaagent agent attach <run_id> --resume --root .
```

Git hook recipe: [examples/ergonomics/git-pre-commit-recipe.sh](../examples/ergonomics/git-pre-commit-recipe.sh).

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

With `.[tui]` installed, TeaAgent uses `prompt-toolkit` for history and autosuggest. If not installed, it falls back to builtin `input()` automatically.

Or without installing the console script:

```bash
python3 -m teaagent.cli tui
```

Run the guided setup wizard before the REPL (same flow as `teaagent setup`):

```bash
teaagent tui --setup --root . --write-env
```

Inside the TUI, type `setup` (optional `write-env`, optional provider name):

```text
setup
setup write-env
setup gpt
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
teaagent doctor model opencodezen
teaagent doctor model opencodezen-go
teaagent doctor model mistral
teaagent doctor model deepseek
teaagent doctor model grok
teaagent doctor model workers-ai
teaagent doctor model aigateway
teaagent doctor model gpt --wizard
```

Guided Cloudflare AI Gateway readiness check:

```bash
teaagent doctor aigateway
teaagent doctor aigateway --mode workers-ai
teaagent doctor aigateway --mode compat
```

This command validates `CLOUDFLARE_API_TOKEN`, a mode-specific base URL
(`WORKERS_AI_BASE_URL` for `workers-ai` mode or `AIGATEWAY_BASE_URL` for `compat`
mode), and optional `WORKERS_AI_EXTRA_HEADERS` (for authenticated gateway mode),
then returns a step-by-step `next_steps` checklist.

Boundary:
- Workers AI = inference provider endpoint.
- AI Gateway = optional routing/policy layer in front of Workers AI.
- `WORKERS_AI_BASE_URL` may use either direct Workers AI (`.../ai/v1`) or AI Gateway workers-ai provider route (`https://gateway.ai.cloudflare.com/.../workers-ai/v1`).

Interactive setup wizard:

```bash
teaagent doctor aigateway --wizard
teaagent doctor aigateway --mode compat --wizard
teaagent doctor aigateway --wizard --write-env --root .
teaagent doctor aigateway --mode compat --write-env --root .
```

`--mode workers-ai` expects the provider route:
`https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/workers-ai/v1`

`--mode compat` expects the unified OpenAI-compatible route:
`https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/compat`
Use model names like `dynamic/default` or `<provider>/<model>`.

Provider setup wizard:

```bash
teaagent doctor providers
teaagent doctor providers --wizard
teaagent doctor providers --wizard --provider gpt --provider claude --write-env --root .
```

`teaagent doctor providers` now includes token-source signals per provider:
`env_loaded` and `keychain_present`.

Project onboarding wizard:

```bash
teaagent doctor project
teaagent doctor project --wizard --root .
```

MCP setup wizard:

```bash
teaagent doctor mcp
teaagent doctor mcp --wizard --root .
```

When bearer auth is enabled in wizard mode, output redacts the token from
`launch_command` to avoid leaking secrets in logs.

Environment layering check:

```bash
teaagent doctor env-order --root .
```

If you use macOS Keychain integration, load and configure keys with:

```bash
cp scripts/provider_keys_keychain.zsh ~/.teaagent/provider_keys_keychain.zsh
source ~/.teaagent/provider_keys_keychain.zsh
teaagent_configure_provider_keys
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
export CLOUDFLARE_API_TOKEN=...
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
export WORKERS_AI_BASE_URL=https://api.cloudflare.com/client/v4/accounts/<account_id>/ai/v1
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
- `workspace_hybrid_index`: local fallback hybrid index builder (FTS5 + basic vector + RRF).
- `workspace_hybrid_search`: local fallback hybrid retrieval over indexed collections.
- `workspace_knowledge_index`: pluggable knowledge indexing (`backend` or `backend=auto`).
- `workspace_knowledge_search`: pluggable knowledge retrieval (`backend` or `backend=auto`).
- `workspace_code_parse`: pluggable code-navigation action router (`health`, `overview`, `symbols`, `definition`, `references`).
- `workspace_run_shell_inspect`: run inspect-safe shell commands without destructive permission.
- `workspace_run_shell_mutate`: run arbitrary shell commands; destructive.
- `workspace_run_shell`: compatibility alias for `workspace_run_shell_mutate`; destructive.

All path-based tools reject paths that escape the configured workspace root.

Backend notes:

- `workspace_knowledge_*` uses `KnowledgeSearchBackend` registrations and supports fallback routing with `backend=auto` plus optional `primary_backend`/`fallback_backend`.
- `workspace_code_parse` uses `CodeParseBackend` registrations for tools such as `cx` and `codegraph` adapters without hard-coding one provider.

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

`agent daily` uses the same persisted runs, pending approvals, heartbeat status,
and optional checkpoint/run replay signals to provide a lightweight background
session cockpit before starting or resuming work.

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

### Lineage and isolation (default: shared workspace)

Child runs record parent lineage on every `subagent` / `subagent_*` / `subagent_batch` result:

| Field | Meaning |
|-------|---------|
| `parent_run_id` | Persisted parent run that invoked the tool |
| `def_name` | Named subagent definition (`generic` when using `subagent`) |
| `depth` | Child depth (`parent depth + 1`) |
| `batch_index` | Position in `subagent_batch` (null for single delegation) |
| `isolation` | `shared` (default), `worktree` (detached git worktree), or `container` (gitignore-respecting snapshot under `.teaagent/subagent-containers/`) |
| `worktree_path` | Relative worktree path when `isolation=worktree` (audit metadata) |
| `container_path` | Relative snapshot path when `isolation=container` (audit metadata) |

Pass `isolation` on `subagent` or per task in `subagent_batch`. Worktree mode requires a git repository. Container mode copies the workspace (excluding parent `.teaagent` state) and removes the snapshot when the child completes.

`subagent_batch` returns a top-level `lineage` array ordered by `batch_index`, parallel to `results`.

Audit: child runs emit a `subagent_lineage` event in their JSONL; parent tool results embed the same `lineage` object.

Inside TUI:

```text
subagent on
ask Plan and execute the cleanup
```

## Consensus (Phase 4 Beta)

Peer registry, voting, and swarm pre-approval for high-risk tasks:

```bash
teaagent consensus peers list --root .
teaagent consensus request "Deploy billing service" --risk-level high --wait --auto-approve
teaagent consensus wait <proposal-id> --timeout 120
teaagent consensus votes-import votes.json
teaagent consensus relay serve --port 8790 --api-token-file relay-tokens.json
teaagent consensus relay serve --tls-cert srv.pem --tls-key srv.key --tls-client-ca ca.pem
teaagent consensus relay submit --relay-url https://127.0.0.1:8790 PROP peer-a approve \
  --private-key ~/.ssh/id_ed25519 --task-description "Deploy billing" --api-token "$RELAY_TOKEN"
teaagent control-plane serve --api-token-file tokens.json --default-tenant team-a
# Clients: Authorization: Bearer <token> and X-TeaAgent-Tenant: team-a
# See docs/http-surface-auth.md and templates/reverse-proxy/
```

Swarm runs can enable consensus with pre-approval patterns or async vote polling
(`ConsensusConfig.async_vote_collection`). See `tests/acceptance/test_consensus_flow.py`.

## Sandbox (Phase 5 Beta)

Route skills to directory-snapshot, Docker, or WASM sandboxes; execute skill `tool.py`:

```bash
teaagent sandbox route ./my-skill --risk-level medium --root .
teaagent sandbox execute ./my-skill --payload '{"n": 1}' --risk-level low --root .
teaagent sandbox check wasm
teaagent sandbox check compatibility ./my-skill --root .
teaagent sandbox monitor <container_id> --duration 30
```

Skill execution uses `teaagent/skill_executor.py` (subprocess, Docker, or WASM module when present).

## Control plane (Phase 6 Beta)

Local dashboard for workflow state, focus stack, and JIT approvals:

```bash
teaagent control-plane serve --host 127.0.0.1 --port 8765
```

Opens `teaagent/html_dashboard/` with SSE streams (`/api/workflow/stream`, `/api/focus/stream`, `/api/jit/diff`) and JIT approve/reject endpoints. The serve command wires `ToolPermissionManager(approval_callback=...)` so dashboard approvals grant tool access for the session.

## Preflight and Daily Brief

**Daily start ritual (recommended):** run `agent daily` read-only before every session to see
readiness, token pressure, recent runs, pending approvals, and the next safe command. Use
`agent preflight` when you only need clarification/routing without the full cockpit rollup.

Summarize clarification, routing, matching memories, permission state, and tool count without calling a model:

```bash
teaagent agent daily gpt "what I want to do today" --permission-mode read-only --root .
teaagent agent preflight gpt "review this patch for regressions in the test suite" --route-model
teaagent agent daily gpt "review this patch for regressions in the test suite" --context-profile balanced
teaagent agent daily gpt "quick status check" --context-profile lean
teaagent agent daily gpt "map auth and session flow" --context-profile deep
```

Exit code is `0` when the task is concrete enough and `2` when it still needs clarification. Pair with `--permission-mode workspace-write` or `--memory-limit 10` as needed.

Preflight JSON includes a read-only `context_pack` (candidate files from task/`AGENTS.md` mentions, matching memories, LSP symbol hydration when code analysis is enabled, and read-only graph hits from hybrid search, the `.teaagent/knowledge` collection marker, and `.teaagent/graphqlite.db` when present) so planning runs can show *why this context* without workspace writes. `context_pack.graph_rag.sources` lists per-backend hits; `hits` is the deduped union.

Both preflight and daily include `token_budget`: estimated input tokens, output reserve, green/yellow/red context pressure, estimated cost, and contributor breakdown for task text, memories, context pack, tool metadata, and recent-run replay. `agent daily` adds `harness_health`, `recent_runs`, and `recommendations` so daily work can start from a single read-only cockpit.

Use `--context-profile lean|balanced|deep` to tune read-only context collection:
`lean` minimizes context pressure, `balanced` is the default, and `deep` includes more memories plus a larger output reserve.

Inside TUI:

```text
route-model on
daily what I want to do today
preflight review this patch for regressions in the test suite
ask summarize the test suite
runs
resume <run_id>
```

### Everyday task recipes

| Task | Example |
|------|---------|
| Summarize repo | `teaagent agent daily gpt "summarize repo" --context-profile lean` then read-only `agent run` |
| Review diff | `teaagent agent daily gpt "review diff" --context-profile balanced` |
| Fix failing test | `teaagent agent preflight gpt "fix test_foo"` → `agent run ... --permission-mode workspace-write` |
| Write docs | `teaagent agent run gpt "update USAGE daily section" --permission-mode workspace-write` |
| Inspect architecture | `teaagent agent daily gpt "auth flow" --context-profile deep` |
| Resume previous run | `teaagent agent status <run_id>` → `teaagent agent resume gpt <run_id>` |
| Safe cleanup | read-only `agent run` first; use `prompt` only if destructive deletes are required |

See [USAGE.md#daily-use](USAGE.md#daily-use) for Inspect/Edit/Autonomous modes and TUI workflow.

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

Approve one exact destructive tool call id (Legacy Escape Hatch / Deprecated):

```bash
teaagent agent run gpt "Create a TODO.md summary" --approve-call-id write-todo-1
```

> [!WARNING]
> `--approve-call-id` is a deprecated legacy escape hatch. Using bare call IDs bypasses exact argument cryptographic validation and is highly discouraged. For standard workflows, use interactive HITL or exact-match `agent resume`.

For interactive HITL approval during a CLI run, use:

```bash
teaagent agent run gpt "Create a TODO.md summary" --hitl-approval
```

Without `--hitl-approval`, an unapproved destructive tool in `prompt` mode returns `pending_approval` with the required `call_id`. Use `agent resume` to auto-approve that precise tool call using its raw cryptographic digest, or use `--hitl-approval` to approve it interactively.

### Approval presets

Persistent scoped presets live in `.teaagent/approvals.json` under `--root`. Evaluation order is **deny → allow (once/session/always) → prompt** when no preset matches.

```bash
teaagent approval grant workspace_write_file --path-glob 'src/**' --scope session --root .
teaagent approval grant workspace_run_shell_mutate --command-prefix 'pytest ' --scope session --root .
teaagent approval deny workspace_write_file --path-glob 'secrets/**' --root .
teaagent approval list --root .                         # { policy_order, grants }
teaagent approval list --grants-only --root .           # legacy grants array for jq
teaagent approval check workspace_write_file --path src/foo.py --permission-mode prompt --root .
teaagent approval revoke <grant_id> --root .
teaagent approval audit --limit 20 --root .
```

`approval check` is dry-run: it does not consume `once` grants (those are removed when the tool actually runs). `approval list` defaults to a policy envelope; pass `--grants-only` if scripts expect a top-level JSON array.

#### Enhanced approval check with arbitrary arguments

Test arbitrary tool arguments beyond just `--path` and `--command`:

```bash
# Using --arg key=value (repeatable)
teaagent approval check workspace_write_file --arg path=src/foo.py --arg content=bar --root .

# Using --arguments-json for complex nested arguments
teaagent approval check workspace_write_file --arguments-json '{"path": "src/foo.py", "content": "bar"}' --root .
```

#### Approval why-denied (audit-backed)

After a run completes, inspect denials and blocks recorded in the audit log:

```bash
teaagent approval why-denied <run_id> --root .
teaagent approval why-denied <run_id> --call-id <call_id> --verbose --root .
```

Each denial prints a `reason_code` (for example `read_only_mode`, `jit_no_approval`,
`multisig_no_quorum`) and a short human-readable explanation. Use `--verbose` to dump
the full redacted payload.

#### Approval explain with mismatch diagnostics

Understand why a tool call matches or fails to match approval rules:

```bash
teaagent approval explain workspace_write_file --arg path=src/foo.py --root .
```

Output includes a human-readable `summary` field explaining the decision and `reason` fields in `evaluated_grants` showing why each grant matched or failed (e.g., `path_glob_mismatch`, `permission_mode_mismatch`, `expired`).

#### Approval pending and approve workflow

Manage runs stuck on pending approval:

```bash
# List all runs with pending approvals
teaagent approval pending --root .

# Approve a specific call (without resuming)
teaagent approval approve <call_id> --root .

# Approve and immediately resume the run
teaagent approval approve <call_id> --root . --resume
```

#### Approval presets for common patterns

Apply predefined policy templates:

```bash
# dev-safe: allow workspace writes, pytest, git diff/status; deny secrets/** and deploy commands
teaagent approval preset dev-safe --root .

# ci-safe: read-only mode for CI environments
teaagent approval preset ci-safe --root .

# strict: deny all destructive tools, require explicit approval
teaagent approval preset strict --root .
```

#### Approval doctor for policy health

Diagnose approval policy health and get suggestions:

```bash
teaagent approval doctor --root .
```

Reports expired grants, conflicting rules (deny + allow for same tool), missing common patterns, and overly broad rules.

Prefer explicit permission modes for regular use:

```bash
teaagent agent run gpt "Inspect this repo" --permission-mode read-only
teaagent agent run gpt "Update one markdown file" --permission-mode workspace-write
teaagent agent run gpt "Run tests and patch failures" --permission-mode prompt
teaagent agent run gpt "Run approved automation" --permission-mode allow
```

Mode and safety comparison matrix: see [USAGE.md — Mode and Safety Comparison Matrix](USAGE.md#mode-and-safety-comparison-matrix).

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

Export a compliance audit bundle with hash-chain verification for a completed run:

```bash
teaagent audit export --audit-log <run_id> --output compliance.json
```

The compliance bundle includes a signed digest of all audit events, chain verification
status, and a summary of tool calls. Use `verify_bundle_integrity()` from
`teaagent.audit_export` to validate the bundle's authenticity.

Resume the original task from a persisted run id with optional new settings:

```bash
teaagent agent resume <run_id> --root /path/to/repo
```

By default, resume replays already-completed `tool_call_completed` observations into the new run's context so the model does not have to redo prior tool calls. If the original run paused with `pending_approval`, the pending tool call is auto-approved by creating a precise, run-scoped exact-match approval (binding the run_id, call_id, tool_name, and raw canonical argument digest) in the persistent preset database (`ApprovalPresetStore`), rather than adding a bare wildcard call ID. This ensures that only the exact prior proposed tool execution (validating sensitive unredacted parameters like `command`, `content`, `old`, and `new` keys) is permitted upon resumption. Legacy pending approvals without raw canonical digests cannot be auto-approved safely and will trigger explicit/interactive HITL approval.

Pass `--fresh-restart` to skip replay and re-run the original task from scratch.

Inside TUI:

```text
ask write TODO.md       # prompts y/N when a destructive call is proposed
approve write-todo-1
approvals               # list approved call IDs
approvals check workspace_write_file path=src/foo.py
approvals revoke <grant_id>
approvals pending
approvals diff <call_id> # show git diff for a pending approval
unapprove write-todo-1
runs
show <run_id>
resume <run_id>
```

### Undo

Undo write operations by rolling back the git sandbox state used by agent runs:

```bash
teaagent undo --last
```

Undo all writes produced by a specific run id:

```bash
teaagent undo --run-id <run_id>
```

`undo` uses git sandbox rollback. Use `--last` to revert the most recent write operation, or `--run-id` to revert all writes associated with that run.

## Agent Automation

Create persistent scheduled automations (stored under `.teaagent/automations/*.json`):

```bash
teaagent agent automation add daily-brief "Summarize open TODOs" --schedule "daily 09:00" --root .
teaagent agent automation add lint-sweep "Check docs consistency" --schedule "every 2h" --root . --auto-propose-skill
```

List and inspect:

```bash
teaagent agent automation list --root .
teaagent agent automation show <automation_id> --root .
```

Control lifecycle:

```bash
teaagent agent automation pause <automation_id> --root .
teaagent agent automation resume <automation_id> --root .
teaagent agent automation delete <automation_id> --root .
```

Execute runs:

```bash
teaagent agent automation run <automation_id> --root .
teaagent agent automation tick --root .
teaagent agent automation tick --dry-run --root .
teaagent agent automation serve --interval-seconds 30 --max-ticks 10 --root .
```

`tick` enforces a lock (`.teaagent/automations/.tick.lock`) to avoid duplicate scheduling in concurrent invocations.
`serve` emits one JSON health snapshot per tick with `uptime_seconds` and
`health` (`automation_count`, `enabled_count`, `due_count`, `running_count`).

Automation tickets are designed for fresh sessions. Add `--acceptance-criteria`
before production scheduling; each tick wraps the task with the criteria,
permission/tool limits, selected skills, cost/runtime caps, and a reminder not
to rely on prior chat history. Use `--skill NAME` for explicit skill loading
and `--requires-subagent` when a tick intentionally needs delegation.

Script-first collectors use `--collector-command` and are checked twice: at
add/dry-run time and immediately before every tick. Shell/network wrappers and
inline interpreters are blocked, local script/module content is sealed with a
`collector_command_digest`, and changed scripts fail with `integrity_failed`
instead of waking an agent. `--context-from` handoffs and log tails are injected
as untrusted data and truncated/redacted before prompt use.

## Skill Candidates

Use candidate quarantine for agent-authored skills before installing into active skill paths:

```bash
teaagent skill candidate propose --from-run <run_id> --name test-first --description "Generate test-first plans" --root .
teaagent skill candidate list --root .
teaagent skill candidate show <candidate_id> --root .
teaagent skill candidate review <candidate_id> --root .
teaagent skill candidate install <candidate_id> --scope project --root .
teaagent skill candidate install <candidate_id> --scope personal --i-attest-personal-install --root .
```

Candidates are stored under `.teaagent/skill-candidates/<candidate_id>/`.
Install requires passing offline eval and review first. Candidate bundles carry
`SKILL.md`, `REFERENCE.md`, `tool_call_contract.json`, `cost_profile.json`,
`interaction_policy.json`, and `provenance.json`; active skills with these
sidecars are skipped at load time if their provenance digest no longer matches.
Personal installs require explicit attestation and record install scope/time in
`provenance.json`.
