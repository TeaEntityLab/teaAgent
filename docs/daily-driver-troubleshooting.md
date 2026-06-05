# Daily-Driver Troubleshooting
# As of 2026-06-02

Symptom-first guide for the daily TeaAgent surfaces.

| Symptom | Likely cause | Safest next command | Reference |
|---------|--------------|---------------------|-----------|
| `teaagent chat <task>` opens but the task did not run. | Positional task forwarding was recently added but may lack full tests in your build. | Submit the prompt inside REPL or use `teaagent agent run "<task>"`. | TASK-DD2-001 |
| TUI `/cost` shows `$0.00` after work. | TUI session cost stop-gap may be absent, failing, or not on your installed version. | Check run summary or provider dashboard. | CG-11 / TICKET-12 |
| TUI budget looks calm but provider spend exists. | Same display gap as TUI cost. | Treat TUI budget display as non-authoritative. | CG-11 |
| A resume command errors. | Run task/observations may not be stored for that path. | `teaagent agent show <run_id>` then `teaagent agent interactive-review <run_id>`. | AG-01 |
| `agent run --background <id>` starts odd work. | The id can be parsed as a new task. | Stop and use review/resume command. | AG-02 |
| TUI opens in the wrong repo. | Saved state may have overwritten explicit root. | Restart with `teaagent tui --root .` and verify visible root. | TASK-DD2-002 |
| `/undo` affects more than expected. | Checkpoint restore (git-level) is different from journal undo (file-level). Check which mechanism was used in the output payload (`method`/`mechanism` fields). | Inspect git status and recover manually if needed. If journal undo was expected, verify the undo journal exists for the run. | CG-15 |
| A test says cost works but live TUI does not. | Test may inject the state it claims to verify. | Add a path-level test through the user command. | CG-16 |
| Approval prompt has no path. | Path scope fallback is too broad or ambiguous. | Reject and rerun with narrower scope. | PATH-GATE |
| CLI says background but no work continues. | Lifecycle wording drift. | Treat as suspended and inspect the run id. | TICKET-16 |

## Fast triage flow

1. Capture the exact command and run id.
2. Run `teaagent agent show <run_id>` if a run id exists.
3. Check git status before undo or resume.
4. Check pending approvals before retrying.
5. Prefer review over continuation when state is unclear.

## Reporting a new issue

Include:

- Command entered.
- Current working directory.
- Run id.
- Provider/model.
- Permission mode.
- Whether TUI, REPL chat, or agent mode was used.
- Expected result.
- Actual result.
