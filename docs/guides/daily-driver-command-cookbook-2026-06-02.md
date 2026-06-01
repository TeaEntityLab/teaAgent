# Daily-Driver Command Cookbook
# 2026-06-02

This cookbook gives users concrete command choices for common daily work.

## Choose the surface

| Goal | Start here | Avoid |
|------|------------|-------|
| Ask and iterate conversationally | `teaagent chat` | TUI cost-sensitive work until parity is verified. |
| Operate a cockpit with runs and approvals | `teaagent tui --setup --root .` | Assuming displayed cost is authoritative before TICKET-12 proof. |
| Run one audited task | `teaagent agent run "<task>"` | Passing run ids as task arguments. |
| Inspect a run | `teaagent agent show <run_id>` | Resuming before reading the run state. |
| Review changes | `teaagent agent interactive-review <run_id>` | Blindly accepting output claims. |

## First command in a repo

```bash
teaagent agent preflight
```

Use this to discover provider, permission, and repo readiness. If the command is
documented as read-only, verify whether first-run `.teaagent` initialization is expected
for your build.

## Conversational task

```bash
teaagent chat
```

Then enter the task in the prompt. If using `teaagent chat "<task>"`, treat it as a
verify/close feature in the current working tree until your build has tests for initial
task execution.

## Audited one-shot task

```bash
teaagent agent run "summarize risk in the TUI cost path"
```

Record the run id from the result. The run id is the handle for audit, review, and
continuity.

## Approval-heavy task

Start conservative:

```bash
teaagent agent run "update docs for daily-driver risks" --permission-mode prompt
```

Approve only exact paths that match the task.

## Recovery command

```bash
teaagent agent interactive-review <run_id>
```

Use review before resume when run state or lifecycle wording is unclear.

## Cost-sensitive command

Prefer the REPL until TUI parity is proven:

```bash
teaagent chat
```

Check run summary or provider dashboard if the TUI shows a suspicious zero.
