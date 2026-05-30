# MCP Setup Recipe

**When to use:** You want to connect TeaAgent workspace tools to an MCP client
(desktop app, IDE plugin, or another agent). The client talks JSON-RPC over
stdio or HTTP to TeaAgent's MCP server.

## Step 1: Choose a transport

### stdio (default, simplest)

```bash
teaagent mcp serve --root .
```

Configure your MCP client to run this command. Clients receive `tools/list`
and `tools/call` for workspace tools.

### Streamable HTTP (loopback, IDE-friendly)

```bash
teaagent mcp serve --http --port 7330 --root .
```

Default bind is `127.0.0.1`. Use `--host 0.0.0.0` only with auth:

```bash
teaagent mcp serve --http --port 7330 --root . --auth-token "$MCP_TOKEN"
```

## Step 2: Verify the server

```bash
teaagent doctor mcp --wizard --root .
```

This validates the workspace root, checks tool registration, and prints the
launch command for your MCP client configuration.

## Step 3: Configure your client

For VS Code, point the MCP extension at:

```
command: teaagent mcp serve --root /path/to/repo
```

For Claude Desktop or other MCP hosts, add to `mcp_server` config:

```json
{
  "command": "teaagent",
  "args": ["mcp", "serve", "--root", "/path/to/repo"],
  "env": {}
}
```

For HTTP mode, use the `--http` URL and include `Mcp-Session-Id` headers
from the `initialize` response in every subsequent request.

## Step 4: Test tools

```bash
teaagent workspace tools --root .
```

This lists all registered tools exposed via MCP, including read-only and
destructive annotations.

**Recovery:** If `teaagent doctor mcp` fails, verify the workspace root exists
and is writable. Use `--root .` or an absolute path.
