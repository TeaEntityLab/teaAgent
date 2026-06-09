# Inline TODO / FIXME / XXX Catalog
**Generated:** 2026-06-02 | **Last reviewed:** 2026-06-09 | **Scope:** `teaagent/` and `scripts/`

---

## Production source (`teaagent/`)

| File | Line | Comment | Context | Action |
|------|------|---------|---------|--------|
| [`teaagent/issue_intake.py`](../../teaagent/issue_intake.py) | 195 | GitHub API integration | **Fixed (2026-06-09):** `extract_github_issue()` uses PyGithub with `GITHUB_TOKEN`; raises actionable errors when library/token missing. | None — closed. |

---

## Scripts (`scripts/`)

These are utility/monitoring scripts, not production runtime. The TODOs here
are stubs left from scaffolding and are lower priority.

| File | Lines | Comment | Context | Action |
|------|-------|---------|---------|--------|
| [`scripts/opencode_gap_watch.py`](../../scripts/opencode_gap_watch.py) | 21, 29 | GitHub API integration | **Fixed (2026-06-09):** release and governance-issue checks use `scripts/_github_api.py` (OpenCode repo configurable via `OPENCODE_GITHUB_REPO`). | Community platform checks remain manual (Reddit/Discord need separate credentials). |
| [`scripts/community_presence_monitor.py`](../../scripts/community_presence_monitor.py) | 21, 37 | GitHub + HN API integration | **Fixed (2026-06-09):** GitHub stars via REST API; HN via Algolia public API. | Reddit/Dev.to still return empty lists until credentials are configured. |

---

## Architectural dead-letter items

These are not inline comments but recurring patterns the audit uncovered that
function as implicit TODOs:

**2026-06-04 update:** Several entries in the original generated catalog are
now fixed. They are kept below with status so the historical audit remains
traceable without re-opening closed work.

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
| Implicit architectural TODOs (ticketed) | 0 active |
| **Active total** | **0** |
| Fixed historical entries retained | 9 |
