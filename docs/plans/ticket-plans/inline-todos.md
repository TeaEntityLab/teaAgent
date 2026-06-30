# Inline TODO / FIXME / XXX Catalog
**Generated:** 2026-06-02 | **Last reviewed:** 2026-06-30 | **Scope:** `teaagent/` and `scripts/`

---

## Production source (`teaagent/`)

| File | Line | Comment | Context | Action |
|------|------|---------|---------|--------|
| [`teaagent/domain/issue_intake.py`](../../../teaagent/domain/issue_intake.py) | 194 | GitHub API integration | **Fixed (2026-06-09):** `extract_github_issue()` uses PyGithub with `GITHUB_TOKEN`; raises actionable errors when library/token missing. | None — closed. |
| [`teaagent/tui/cockpit_data_sources.py`](../../../teaagent/tui/cockpit_data_sources.py) | 158 | Cost period attribution | **Fixed (2026-06-30):** `CostDataSource.get_costs()` now derives `CostRow.period` from `RunSummary.updated_at` with an `unknown` fallback. | None — closed. |

---

## Scripts (`scripts/`)

These are utility/monitoring scripts, not production runtime. The TODOs here
are stubs left from scaffolding and are lower priority.

| File | Lines | Comment | Context | Action |
|------|-------|---------|---------|--------|
| [`scripts/opencode_gap_watch.py`](../../../scripts/opencode_gap_watch.py) | 21, 29 | GitHub API integration | **Fixed (2026-06-09):** release and governance-issue checks use `scripts/_github_api.py` (OpenCode repo configurable via `OPENCODE_GITHUB_REPO`). | Community platform checks remain manual (Reddit/Discord need separate credentials). |
| [`scripts/community_presence_monitor.py`](../../../scripts/community_presence_monitor.py) | 21, 37 | GitHub + HN API integration | **Fixed (2026-06-09):** GitHub stars via REST API; HN via Algolia public API. | Reddit/Dev.to still return empty lists until credentials are configured. |

---

## Implicit deferrals requiring owner / ticket

These are not literal `# TODO` comments, so the explicit TODO drift guard does
not count them. They remain review-needed until each is either ticketed,
implemented, or explicitly documented as intentional scaffolding.

| Location | Pattern | Action |
|----------|---------|--------|
| `teaagent/consensus/consensus_validation.py:113-114` | Voter role is inferred from `voter_id` instead of looked up. | Ticket consensus role source of truth or document why `voter_id` encoding is contractual. |
| `teaagent/domain/workflow_engine.py:357-358` | Workflow step execution is simulated. | Ticket real agent invocation boundary before treating workflow engine as production execution. |
| `teaagent/eval_suite.py:410-517` | Eval execution and baseline diffing use placeholder/simulated behavior. | Ticket real executor/diff semantics or label suite as non-gating simulation. |
| `teaagent/cli/_handlers/_consensus.py:154,177` | Consensus history query and configuration persistence are not implemented. | Ticket persistence/history or hide commands from production-facing flows. |
| `teaagent/domain/agent_factory.py:434-435` | Agent removal is logged as not fully implemented. | Ticket registry removal support and persisted cleanup semantics. |
| `teaagent/domain/issue_intake.py:570,776` | Plan exploration and generated command are placeholders. | Ticket PlanMode integration or label issue-intake plan execution as advisory only. |

---

## Architectural dead-letter items

These are historical implicit TODOs. They are kept below with status so the
audit remains traceable without re-opening closed work.

| Location | Pattern | Status / Implicit TODO |
|----------|---------|------------------------|
| `tui/__init__.py::_handle_undo` | `_handle_undo` called `_restore_checkpoint` (git-stash) | Fixed: TICKET-12 now routes through `ChatSessionController.undo_last_run()` before checkpoint fallback |
| `chat_session_controller.py` | `except (AttributeError, TypeError): pass` | Fixed: TICKET-13 removed exception-swallowing mock detection |
| `chat_repl.py` | `suspension_data['audit_trail']` | Fixed: TICKET-15 removed redundant suspension `audit_trail` |
| `chat_repl.py::suspend_to_background` | Broken resume commands printed at suspend | Fixed: TICKET-16 Phase 1 now prints the working `interactive-review` path only |
| `run_store.py:143-149` | `task_for_run` raises on REPL suspensions | Fixed: TICKET-16 Phase 2 writes `run_started` at suspend time |
| `_chat.py:538-586` | `chat_command` ignores `args.task` | Fixed: TASK-DD2-001 forwards positional task to `run_tui` |
| `tui/__init__.py:1107` | `_load_tui_state` unconditionally overwrites `self.root` | Fixed: TASK-DD2-002 guards with `_root_explicit` flag |

---

## Summary counts

| Category | Count |
|----------|-------|
| Explicit `# TODO` in production (`teaagent/`) | 0 |
| Explicit `# TODO` in scripts (unfixed stubs) | 0 |
| Implicit deferrals requiring owner / ticket | 6 review-needed |
| Implicit architectural TODOs (ticketed) | 0 active |
| **Active total** | **6 review-needed** |
| Fixed historical entries retained | 11 |
