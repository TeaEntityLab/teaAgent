# Memory State Integrity Contract
# 2026-06-02

## Contract

Corrupt local memory or run state must be visible as degraded health, not silently
omitted from daily views.

## Rules

- Malformed memory JSONL lines are counted and surfaced.
- Malformed run JSONL files are counted and surfaced.
- Healthy entries still load best-effort.
- Warnings include path context but avoid dumping sensitive contents.

## Acceptance

- Injected corrupt memory produces a warning.
- Injected corrupt run file produces a warning.
- Daily/preflight output distinguishes "no runs" from "some runs unreadable."

## User risk

Silent state loss makes the cockpit look trustworthy precisely when local evidence is
degraded.
