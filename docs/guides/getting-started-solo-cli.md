# Getting Started — Solo CLI User

> **Last reviewed:** 2026-06-06
> **Persona:** Individual developer running TeaAgent locally from the terminal

You want a **governed terminal agent** — not an IDE plugin — with clear
permissions, cost caps, and an audit trail you can inspect after each run.

## Prerequisites

- Python 3.11+ (see [README](../../README.md) for venv setup)
- A model provider API key (OpenAI, Anthropic, etc.)

## 15-minute path

```bash
pip install -e .
teaagent setup --root . --provider gpt --permission-mode read-only --write-env
source ~/.teaagent/providers_env.zsh   # or your shell snippet

teaagent daily "what should I work on?" --human --root .
teaagent run "summarize the test suite" --permission-mode read-only --root .
```

## Daily habits

| Habit | Command |
| --- | --- |
| Read-only exploration | `--permission-mode read-only` |
| Writes with approval | `--permission-mode prompt` |
| Cost cap | `--max-estimated-cost-cents 500` |
| See what happened | `teaagent agent runs show <run_id> --receipt --root .` |
| Undo last write | `teaagent agent undo --last --root .` |

## When to escalate modes

1. **Plan / explore** → `read-only`
2. **Implement with guardrails** → `workspace-write` (plan required by default)
3. **Interactive destructive** → `prompt`
4. **Trusted automation only** → `allow` or `danger-full-access`

## Next steps

- Full walkthrough: [USAGE.md](../USAGE.md)
- TUI loop: `teaagent tui --setup --root .`
- When TeaAgent is a bad fit: [When Not to Use TeaAgent](when-not-to-use-teaagent.md)
