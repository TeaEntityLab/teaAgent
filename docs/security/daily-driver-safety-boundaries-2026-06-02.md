# Daily-Driver Safety Boundaries
# 2026-06-02

Safety boundaries for daily TUI, chat, and agent-mode use.

## Boundaries

| Boundary | Must protect | Current concern |
|----------|--------------|-----------------|
| Workspace root | Which files can be touched. | Saved TUI root can override explicit root. |
| Approval scope | Which tool action is authorized. | Path extraction/matching needs hardening. |
| Pinned files | What local context is read. | Path containment must be enforced. |
| Cost cap | Provider spend. | Zero semantics and display parity need proof. |
| Undo scope | User edits. | TUI and REPL undo differ. |
| Run evidence | Auditability. | Corrupt state can be silent. |
| Git sandbox | Branch and stash state. | Lifecycle object can be split. |

## Safety defaults

- Prefer prompt-mode approvals.
- Prefer exact file approvals.
- Reject missing or escaping paths.
- Verify active root before writes.
- Treat false zero cost as a bug.
- Review before resume when state is unclear.

## Security review triggers

Run security review when changing:

- Approval matching.
- Root resolution.
- Pinned-file reads.
- Sandbox branch/stash behavior.
- Tool execution authority.
- Persistence of credentials, memory, or run evidence.
