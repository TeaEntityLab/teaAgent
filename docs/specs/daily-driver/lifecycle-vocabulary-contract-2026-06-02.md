# Lifecycle Vocabulary Contract
# 2026-06-02

## Contract

Lifecycle words must describe real runtime state.

## Vocabulary

| Word | Required meaning |
|------|------------------|
| Running | Work is actively executing. |
| Suspended | Work stopped and has a durable run id for inspection. |
| Background | Work continues outside the foreground UI. |
| Resume | Task and observations are rehydrated and execution continues. |
| Review | Human inspects run evidence and changes. |
| Undo | A documented recovery scope is applied. |

## Acceptance

- Output prints only commands that currently work.
- No command says background unless work continues.
- Resume is advertised only when run context is persisted.
- Docs and help text use the same vocabulary.

## User risk

Users make stop, continue, and recovery decisions from these words. Aspirational wording
can turn into lost work or repeated failed recovery attempts.
