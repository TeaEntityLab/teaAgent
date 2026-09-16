# Documentation Aging Dashboard (Generated)

> **Not current truth.** Use [docs/INDEX.md](../INDEX.md) for the curated front door.

**Stale threshold:** 90 days since `Last reviewed`
**Current-truth docs scanned:** 17
**Needs attention (working tier only):** 2
**Archive-tier docs (exempt from staleness):** 0

Regenerate: `python3 scripts/report_docs_aging.py`

## Stale Or Incomplete By Owner Surface

### cli

| Document | Status | Last reviewed | File mtime | Notes |
| --- | --- | --- | --- | --- |
| `docs/cli.md` | stale_by_mtime | 2026-09-15 | 2026-09-16 | Missing owner banner; File modified after last reviewed date |

### daily-driver

| Document | Status | Last reviewed | File mtime | Notes |
| --- | --- | --- | --- | --- |
| `docs/USAGE.md` | stale_by_mtime | 2026-08-26 | 2026-09-16 | Missing owner banner; File modified after last reviewed date |

## Review Triggers (Current-Truth Docs)

| Document | Owner | Tier | Review trigger |
| --- | --- | --- | --- |
| `README.md` | project | working | README feature claims, golden path, or provider count changes. |
| `docs/INDEX.md` | docs | working | New front-door docs, supersession links, roadmap evidence, or validation command changes. |
| `docs/USAGE.md` | daily-driver | working | CLI/TUI command behavior, permission modes, or surface recipes change. |
| `docs/cli.md` | cli | working | CLI flags, subcommands, or handler behavior changes. |
| `docs/acceptance.md` | verification | working | Acceptance test inventory or count changes. |
| `docs/roadmap-status.md` | roadmap | working | Roadmap horizon, milestone, or track status changes |
| `docs/daily-driver-current-status.md` | daily-driver | working | TUI, chat, agent mode, approval, cost, undo, or resume behavior changes. |
| `docs/release-checklist.md` | release | working | Release gates, survey cadence, or validation workflow changes. |
| `docs/backlog-priority.md` | strategy | working | Backlog priorities or shipped/beta status claims change. |
| `docs/maturity-matrix.md` | governance | working | Subsystem maturity labels change. |
| `docs/terminology.md` | governance | working | Canonical terminology or state vocabulary changes. |
| `docs/architecture.md` | architecture | working | Architecture claims, provider count, or module boundaries change. |
| `docs/tui-daily-driver-guide.md` | daily-driver | working | TUI operator loop or recovery pointers change. |
| `docs/permission-and-approval-playbook.md` | security | working | Approval, permission, or MCP trust behavior changes. |
| `docs/governance/README.md` | governance | working | Governance index or process entry points change. |
| `docs/plans/ticket-plans/index.md` | daily-driver | working | Ticket closure status or execution order changes. |
| `docs/analysis/active-findings-status-ledger-2026-06-06.md` | daily-driver | working | Finding closure status or new CG/AG/DS ids. |

## Corpus Cost (G5 Signal)

**Total docs:** 665 (baseline 582 at diagnosis, delta +83)
**Live corpus (non-archive):** 377
**Working-tier docs unreferenced by INDEX.md:** 328

Dead-weight candidates (working tier, not linked from INDEX.md):

- `DOCUMENTATION_STRATEGY.md`
- `adr/0001-p0-framework.md`
- `adr/0002-p1-primitives.md`
- `adr/0003-p2-code-mode-sandbox.md`
- `adr/0004-oauth-dpop.md`
- `adr/0005-mcp-streamable-http.md`
- `adr/0006-oauth-store-keyring.md`
- `adr/0007-anp-adapter-boundary.md`
- `adr/0008-p4-strategic-posture.md`
- `adr/0009-5-loop-governance-system.md`
- `adr/0010-circular-dependencies.md`
- `adr/0011-approval-manager-refactoring.md`
- `adr/0012-tight-coupling.md`
- `adr/0013-backend-abstraction.md`
- `adr/0014-error-handling.md`
- `adr/0015-configuration-plugin.md`
- `adr/0016-tool-dependency-injection.md`
- `adr/0017-backend-adapter-interfaces.md`
- `adr/0018-async-from-sync-pattern.md`
- `adr/0019-phase-4-federated-swarm-consensus.md`
- ... and 308 more
