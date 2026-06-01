# TeaAgent — Known Issues (Daily Use)
# As of 2026-06-01

This is an honest, user-facing list of current rough edges in the interactive surfaces
(`teaagent chat` and `teaagent tui`), so you can use TeaAgent confidently and not be
misled by displays that are not yet wired correctly. Maintainer-facing detail and fixes
are tracked in `docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md` and
the backlog (TICKET-12…15).

## Recently fixed (no action needed)

If you used an older build, these are now corrected in `teaagent chat`:
- The REPL no longer reports completed tasks as "failed", and prints the answer (CG-01).
- `/undo` no longer wipes all uncommitted changes — it restores only files the run
  touched, via the undo journal (CG-02).
- `/cost` and `/budget` in the REPL now reflect real spend (CG-03).
- `/background` no longer silently switches your git branch, and the suspension is
  recorded in the audit chain (CG-09, CG-10).

## Open issues and workarounds

### 1. TUI `/cost` and the budget bar show $0.00 (cosmetic, not a spend cap)
In `teaagent tui`, the session cost counter is not yet wired to real run cost, so
`/cost` and the budget display read `$0.00` regardless of actual usage.
- **2026-06-02 code note:** the working tree now includes a stop-gap that adds
  `result.cost_cents` to the TUI session counter. Keep this issue open until the
  active TUI path and full controller parity are tested.
- **Impact:** display only — your provider still bills normally; the budget *cap*
  (`--max-estimated-cost-cents`) still enforces.
- **Workaround:** use `teaagent chat` if you need an accurate live session-cost readout,
  or check the per-run summary / provider dashboard.
- **Tracking:** CG-11 / TICKET-12.

### 2. `/undo` behaves differently in the TUI vs the CLI
- `teaagent chat` `/undo` → surgical, restores only the last run's files (undo journal).
- `teaagent tui` `/undo` → git-stash checkpoint restore (different mechanism/scope).
- **Recommendation:** prefer `teaagent chat` for fine-grained undo today. In the TUI,
  create a `/checkpoint` before risky tasks.
- **Tracking:** CG-15 / TICKET-12.

### 3. Shell escape (`!command`) is intentionally disabled in the REPL
This is by design — shell escape would bypass approval/audit governance.
- **Workaround:** run shell commands in a normal terminal; let TeaAgent operate through
  its governed tools.

## What is solid today

- Governance: approvals, audit chain, plan-before-write, and run summaries work and are
  the project's strongest area.
- `teaagent chat`: result handling, real cost, surgical undo, and honest/audited
  suspension are all correct.
- The TUI does not destroy your scrollback (the old screen-clearing behavior is gone),
  and `compact` actually compacts the session.

## Reporting

If you hit something not listed here, capture the run id (shown in the run summary) and
the exact command, and file it — the audit chain makes runs reproducible for diagnosis.

---
*This page is updated as fixes land; cross-check the date in the title against your
build.*
