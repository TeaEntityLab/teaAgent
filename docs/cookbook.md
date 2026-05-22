# TeaAgent Cookbook

Short, copy-paste recipes for everyday work. For the full daily workflow (modes,
token profiles, TUI loop), see [USAGE.md — Daily Use](USAGE.md#daily-use).

## Start ritual

```bash
teaagent agent daily gpt "what I want to do" --permission-mode read-only --root .
```

## Recipes

| Goal | Commands |
|------|----------|
| Summarize repo | `teaagent agent daily gpt "summarize repo" --context-profile lean` → `teaagent agent run gpt "..." --permission-mode read-only` |
| Review diff | `teaagent agent daily gpt "review diff" --context-profile balanced` → read-only `agent run` |
| Fix failing test | `teaagent agent preflight gpt "fix test_foo"` → `teaagent agent run gpt "..." --permission-mode workspace-write` |
| Write docs | `teaagent agent run gpt "update docs for X" --permission-mode workspace-write` |
| Inspect architecture | `teaagent agent daily gpt "map auth flow" --context-profile deep` |
| Resume work | `teaagent agent daily gpt "continue task"` → `teaagent agent status <run_id>` → `teaagent agent resume gpt <run_id>` |
| Long-running task | `teaagent agent run gpt "task" --permission-mode prompt --heartbeat 5` |
| Safe cleanup | read-only `agent run` first; use `prompt` only if destructive deletes are needed |

## Context profiles

```bash
teaagent agent daily gpt "quick check" --context-profile lean
teaagent agent daily gpt "normal task" --context-profile balanced
teaagent agent daily gpt "deep architecture review" --context-profile deep
```

## TUI session

```bash
teaagent tui --root . --permission-mode prompt
```

```text
daily what I want to do
preflight review this patch
ask fix the failing test
runs
resume <run_id>
```

## References

- [CLI reference](cli.md)
- [Plugin/skill catalog](plugin-skill-catalog.md)
- [Release checklist](release-checklist.md)
