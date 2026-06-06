# Background And Resume Vocabulary
# 2026-06-06

> **Owns:** Precise terms for suspension, resume, checkpoint, and background execution.
>
> **Review trigger:** Resume, background run, checkpoint, or suspension behavior changes.

Use these terms consistently in CLI help, TUI prompts, and current-truth docs.

## Terms

| Term | Meaning | Operator signal |
| --- | --- | --- |
| **Checkpointed suspension** | Run paused with context saved to checkpoint store after `pending_approval` or operator interrupt. | `status=pending_approval`, resume requires explicit approval. |
| **Resumable session** | Same run id continues from checkpoint; audit trail in RunStore is authoritative. | `teaagent agent resume <run_id> …` |
| **Live background execution** | Process continues outside the foreground TTY (background id / PID). | `teaagent agent run --background …`, `background list` |
| **Scratchpad hint** | Best-effort `.teaagent/scratchpad.json` note; not a substitute for RunStore. | Shown on next `chat`/`tui` start |
| **Suspension JSON (legacy hint)** | Optional sidecar file; may contain stale audit_trail — prefer RunStore. | Do not treat as forensic source |

## Do not conflate

- **Background** ≠ **resume**. Background keeps a live process; resume continues a
  persisted paused run from checkpoint.
- **Approve** ≠ **resume**. Approving records scoped consent; resume replays the
  runner unless `--resume` is passed on `approval approve`.
- **Undo** ≠ **git sandbox rollback**. Undo journal restores tracked file tools;
  sandbox rollback resets branch state.

## Recommended operator flows

### Paused for approval

```bash
teaagent approval pending --human
teaagent approval approve --selector 1 --resume
```

### Background run monitoring

```bash
teaagent background list --root .
teaagent agent status <run_id> --progress --human --root .
```

### Post-run review

```bash
teaagent agent status <run_id> --evidence --human --root .
```

## Verification

Docs and UI strings must use the table terms above. See
[chat-surface-semantics.md](chat-surface-semantics.md) for cross-surface mapping.
