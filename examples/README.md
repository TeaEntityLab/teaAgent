# TeaAgent Examples

## Inspect-Only Agent Run

```bash
teaagent agent run gpt "Summarize this repository" --permission-mode read-only --route-model
```

## Workspace Metadata

```bash
teaagent workspace tools
```

## MCP HTTP Loopback

```bash
export MCP_TOKEN="local-dev-token"
teaagent mcp serve --http --auth-token "$MCP_TOKEN" --root .
```

## Local Config

Create `.teaagent/config.json`:

```json
{
  "provider": "gpt",
  "model": "gpt-4o-mini",
  "root": ".",
  "permission_mode": "read-only"
}
```

Then run:

```bash
teaagent --config .teaagent/config.json agent run gpt "Inspect tests"
```
