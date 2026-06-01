---
type: index
audience: user, developer, operator
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# TeaAgent Guides

Practical documentation for using and extending TeaAgent.

## Guides

| Guide | Audience | Summary |
|-------|----------|---------|
| [Use Cases](use-cases.md) | User | Walkthroughs for 8 common deployment scenarios |
| [Integration Guide](integration-guide.md) | Developer | Add providers, tools, approval policies, and custom UIs |
| [Tool Development](tool-development.md) | Developer | Build safe, auditable tools with full lifecycle coverage |
| [Approval Policy Design](approval-policy-design.md) | Operator | Design policies that match your trust model |
| [Performance Tuning](performance-tuning.md) | Operator | Laptop, server, cloud, and edge deployment patterns |
| [Migration Guide](migration.md) | User | Moving from Claude Code, Codex, OpenCode, or Aider |

## Working Examples

In [examples/](examples/):

| File | What it shows |
|------|---------------|
| [custom_tool.py](examples/custom_tool.py) | Register a read-only SQL tool; run with a deterministic decide function |
| [approval_patterns.py](examples/approval_patterns.py) | READ_ONLY, PROMPT + custom handler, hook-level path guard |
| [hooks_demo.py](examples/hooks_demo.py) | All 8 hook events; built-in lint and format-check hooks |
| [llm_provider.py](examples/llm_provider.py) | Implement and smoke-test a custom LLM adapter |
| [metrics_telemetry.py](examples/metrics_telemetry.py) | InMemoryMetricsSink, custom audit events, CostTracker, OTel |
| [plugin_skeleton/](examples/plugin_skeleton/) | Complete plugin package (entry-points, tests, pyproject.toml) |

All examples in this directory run without API keys using deterministic or stub adapters.

## Quick Navigation

**I want to…**

- **Ask a question** → [Use Cases § Simple Chat](use-cases.md#1-simple-chat-session)
- **Run autonomously with a cost cap** → [Use Cases § Cost-Limited Run](use-cases.md#3-cost-limited-autonomous-run)
- **Pause and resume a long run** → [Use Cases § Suspended Session](use-cases.md#4-suspendedresumed-session)
- **Add a new tool** → [Tool Development](tool-development.md)
- **Package tools as a plugin** → [Integration Guide § Plugin Development](integration-guide.md#4-plugin-development)
- **Connect a new LLM provider** → [Integration Guide § LLM Provider](integration-guide.md#1-adding-a-new-llm-provider)
- **Build a web or Electron UI** → [Integration Guide § Custom UI](integration-guide.md#5-building-a-custom-ui)
- **Add hooks (lint, tests, logging)** → [Integration Guide § Hooks](integration-guide.md#6-middleware-and-hooks)
- **Lock down what the agent can touch** → [Approval Policy Design](approval-policy-design.md)
- **Deploy to CI/CD** → [Performance Tuning § Server](performance-tuning.md#server-headless-ci--automation)
- **Migrate from Claude Code** → [Migration Guide § Claude Code](migration.md#1-from-claude-code)

## Architecture and Reference

- [Architecture](../architecture.md) — system design overview
- [CLI reference](../cli.md) — full flag reference
- [USAGE.md](../USAGE.md) — golden path quick-start
- [Specs](../specs/) — formal interface contracts
- [Audit events](../audit-events.md) — event schema reference
- [Provider authoring](../provider-authoring.md) — provider conformance levels
- [Tool authoring](../tool-authoring.md) — contract quick-reference
- [Permission and approval playbook](../permission-and-approval-playbook.md) — operator reference
