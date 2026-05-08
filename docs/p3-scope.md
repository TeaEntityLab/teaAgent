# P3 Implementation Scope

## Included

- Audit event reference and JSON schema for downstream sinks: `docs/audit-events.md` and `docs/audit-event.schema.json`.
- Tool authoring and provider authoring guides: `docs/tool-authoring.md`, `docs/provider-authoring.md`.
- Examples directory with a minimal MCP HTTP client and tool metadata template under `examples/`.
- Shell completion command (`teaagent completion <bash|zsh|fish>`) producing copy-paste snippets for each shell.
- Aggregated environment check (`teaagent doctor all`) covering provider configuration, GraphQLite runtime, and MCP HTTP smoke checks.
- Global CLI configuration: `--config <file>` plus `.teaagent/config.json` auto-discovery and named profiles via `--profile`.

## Still Deferred

- Programmatic generation of OpenAPI/MCP schemas from `ToolRegistry` metadata.
- A web-based audit viewer or live trace dashboard beyond the OTel exporter.
- IDE/editor integrations (VS Code extension, JetBrains plugin) wrapping the CLI.
- Hosted documentation site with API reference; only Markdown lives in-repo.

## P3 Extension Rules

- Treat `docs/audit-event.schema.json` as the contract for any external consumer; bump versions in lockstep with `AuditEvent` payload changes.
- Keep `examples/` runnable against the in-tree CLI without extra setup; new examples must include a README snippet.
- Doctor subcommands must be read-only checks. Anything that mutates state belongs in `agent run`, `audit prune`, or other explicit commands.
- Configuration profiles are advisory defaults only — positional arguments and explicit flags must always win.
