# Operator Cockpit Information Architecture
# 2026-06-02

Information architecture for the TUI/operator cockpit.

## Top-level information

Always make these easy to find:

- Active root.
- Provider/model.
- Permission mode.
- Current run id.
- Pending approvals.
- Cost state or unknown state.
- Last verification/result.

## Secondary information

Available on demand:

- Recent runs.
- Session list.
- Audit event summary.
- Changed files.
- Memory/context hints.
- Known caveats.

## Dangerous actions

Dangerous or trust-sensitive actions need clear scope:

- Approve.
- Undo.
- Resume.
- Merge sandbox branch.
- Discard sandbox branch.
- Pin file.

## Layout rule

Do not bury trust-sensitive facts in decorative panels. If a value can change user
behavior, it must be accurate or marked unknown.
