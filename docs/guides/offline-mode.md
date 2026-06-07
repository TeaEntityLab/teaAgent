# Offline Mode

TeaAgent core governance works without network access:

- Permission modes and approval enforcement
- Audit logging and hash-chain verification
- Tool registry and workspace tools (read/inspect)
- Run store, checkpoints, and resume
- TUI and CLI (except LLM calls)

## Requires network

- LLM provider API calls (unless using a local model)
- MCP servers hosted remotely
- Webhook sinks and cloud submit
- Marketplace skill install

## Local LLM providers

Configure Ollama, vLLM, or other local endpoints via provider env vars and `teaagent doctor providers`.

## Offline workflow example

```bash
# Verify harness without API keys
teaagent health --root .
teaagent audit verify --root .
teaagent tool lint --root .

# Dry-run planning (no model call when keys missing)
teaagent daily "summarize repo" --dry-run --root .
```

See [troubleshooting.md](../troubleshooting.md) for provider setup when back online.
