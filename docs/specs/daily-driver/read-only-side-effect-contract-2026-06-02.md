# Read-Only Side-Effect Contract
# 2026-06-02

## Contract

A command described as read-only or dry-run must either avoid filesystem side effects or
clearly announce intentional initialization.

## Rules

- No hidden `.teaagent` creation for read-only checks unless documented.
- First-run initialization must be visible in output.
- Evidence fields must not claim read-only if the path can write state.
- Tests use fresh workspace snapshots.

## Acceptance

- Fresh workspace before/after snapshots match for no-write mode.
- If initialization is allowed, output names the created state path.
- `ContextPack` truth labels match actual semantics.

## User risk

Read-only is a trust promise. Hidden writes are small operationally but large
psychologically, especially in audited or production repositories.
