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

You can also run without installing the console script:

```bash
python3 -m teaagent.cli --help
```

## GraphQLite

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
provider gpt
model gpt-4o-mini
root /path/to/repo
destructive off
ask Inspect this repo and summarize the test suite
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
teaagent doctor model opencodezen-go
```

Run a smoke prompt:

```bash
teaagent model smoke gpt --prompt "Reply with exactly: ok"
teaagent model smoke claude --prompt "Reply with exactly: ok"
teaagent model smoke gemini --prompt "Reply with exactly: ok"
```

Environment variables:

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
export OPENCODEZEN_API_KEY=...
```

Optional base URL overrides:

```bash
export ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
export OPENAI_BASE_URL=https://api.openai.com/v1
export GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
export OPENCODEZEN_BASE_URL=https://api.opencodezen.com/v1
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
- `workspace_write_file`: write UTF-8 files under the root; destructive.
- `workspace_apply_patch`: replace one exact text span; destructive.
- `workspace_list_files`: list files by glob.
- `workspace_search_text`: regex search text files.
- `workspace_git_status`: run `git status --short`.
- `workspace_run_shell`: run a shell command in the workspace; destructive.

All path-based tools reject paths that escape the configured workspace root.

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

By default, destructive tools are blocked. To allow file writes, patching, or shell commands:

```bash
teaagent agent run gpt "Create a TODO.md summary" --allow-destructive
```

The model must return JSON decisions internally:

```json
{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"AGENTS.md"},"call_id":"read-agents"}
{"type":"final","content":"Done"}
```
