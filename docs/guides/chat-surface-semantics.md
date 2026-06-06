# Chat Surface Semantics
# 2026-06-06

> **Owns:** How CLI, TUI, and controller commands relate across surfaces.
>
> **Review trigger:** New chat/TUI commands, REPL routing, or controller API changes.

TeaAgent exposes three interactive surfaces that share one permission, approval,
and audit model but use different command vocabularies.

## Surfaces

| Surface | Entry | Primary operator |
| --- | --- | --- |
| CLI agent/chat | `teaagent chat`, `teaagent agent run` | Scripts, CI, IDE integrations |
| TUI | `teaagent tui` | Daily interactive operator |
| Controller | `ChatSessionController` (REPL/TUI backend) | Programmatic session control |

## Translation layer

| Intent | CLI | TUI | Controller |
| --- | --- | --- | --- |
| Start interactive session | `teaagent chat` | `chat on` | `controller.start_session()` |
| Send user turn | stdin / `--task` | `ask …` | `controller.send_user_message()` |
| Toggle destructive tools | `--allow-destructive` / permission mode | `destructive on\|off` | permission mode on session |
| List pending approvals | `approval pending --human` | `approvals` | approval store + run store |
| Approve by selector | `approval approve --selector N` | `approve <call_id>` (legacy) | scoped approval grant |
| Show run progress | `agent status <id> --progress --human` | `status <id>` + progress lines | audit stream sink |
| Human run receipt | `agent status <id> --evidence --human` | receipt via run history | evidence summary builder |
| Undo last mutating run | `agent undo --last` | `/undo` | `controller.undo_last_run()` |
| Resume paused run | `agent resume …` | `resume <id>` | resume handler with checkpoint |
| Daily readiness | `agent daily … --human` | `daily …` | daily brief builder |

## Rules

1. **Permission mode is canonical.** Surface-specific wording must not imply a
   weaker mode than the configured `permission_mode`.
2. **RunStore is authoritative** for run history, pending approvals, and receipts.
   Suspension JSON and scratchpad files are hints only.
3. **Destructive approval is exact.** A scoped grant or selector approval must
   match the pending call digest; surfaces must not auto-broaden path scope.
4. **Progress vs receipt.** Progress (`--progress`) is for live or paused runs;
   receipts (`--evidence --human`) are for post-run sharing and audit review.

## Verification

- Translation table updated when a new user-facing command ships on any surface.
- `tests/acceptance/test_conversation_ux_flow.py` covers approval display,
  progress summary, and receipt generation paths.

See also: [Background And Resume Vocabulary](background-resume-vocabulary.md),
[USAGE.md](../USAGE.md), [cli.md](../cli.md).
