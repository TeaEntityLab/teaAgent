# Support

## Documentation

- [Architecture overview](docs/architecture.md) — component layers, data flow, extension points.
- [CLI reference](docs/cli.md) — full command-line reference.
- [Security model](SECURITY.md) — threat model, hardening details, vulnerability scope.
- [Tool authoring](docs/tool-authoring.md) — how to register and annotate tools.
- [Provider authoring](docs/provider-authoring.md) — how to add LLM providers.

## Examples

- [Full agent lifecycle](examples/full_agent_run.py) — self-contained walkthrough.
- [MCP client](examples/mcp_client.py) — minimal HTTP MCP client.

## Questions

For usage questions, open a [GitHub Discussion](https://github.com/anomalyco/teaagent/discussions).

## Bugs and Feature Requests

Open an issue via the issue templates. Include:

- TeaAgent version (`python3 -m teaagent.cli --version` or `teaagent.__version__`)
- Python version (`python3 --version`)
- Operating system
- Steps to reproduce

## Security

Do **not** open public issues for security-sensitive findings. Follow the
[security policy](SECURITY.md).
