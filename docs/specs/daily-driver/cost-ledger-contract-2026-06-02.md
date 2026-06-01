# Cost Ledger Contract
# 2026-06-02

## Contract

Cost displayed to a user must come from a real ledger or be marked unknown.

## Rules

- Do not display `$0.00` merely because a ledger is missing.
- `/cost`, `/budget`, cockpit display, and run summary must agree on the source.
- TUI and REPL chat should share controller-backed cost semantics.
- Budget cap enforcement and budget display must not contradict each other.

## Acceptance

- Two tasks with known stubbed costs produce the expected total.
- Unknown cost renders as unknown, not zero.
- Tests drive the active command path.

## User risk

Cost is a spend and trust signal. False zero is a product bug even if the provider bill
is technically outside TeaAgent.
