# TASK-DD2-006: Make Lifecycle Wording Honest

**Priority:** P1
**Status:** Active
**Primary files:** `teaagent/cli/_handlers/chat_repl.py`, `teaagent/cli/_handlers/_chat.py`, `docs/*`

## Problem

User-facing wording still mixes background, suspend, attach, resume, and review in ways
that can imply work is continuing or resumable before the runtime state supports it.

## Scope

- Reserve `background` for work that continues outside the foreground UI.
- Reserve `suspend` for a stopped run with a durable record.
- Reserve `resume` for rehydrating task, observations, approvals, and context.
- Print only commands that currently work.
- Update docs and help snapshots.

## Acceptance criteria

- No output references nonexistent `--detach`.
- No path says "background execution" unless work continues.
- Suspended runs point to reliable inspection/review commands.
- Resume commands are printed only when the run is actually resumable.

## Verification

```bash
python3 -m pytest tests/test_cli_chat.py -k "suspend or background"
rg -n -- "--detach|background execution|teaagent attach" teaagent docs
```

## Risks

- Removing aspirational wording can feel like a feature regression.
- Keeping inaccurate wording is worse because users make recovery decisions from it.
