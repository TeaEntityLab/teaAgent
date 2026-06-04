# Inline TODO / FIXME / XXX Catalog
**Generated:** 2026-06-02 | **Scope:** `teaagent/` and `scripts/`

---

## Production source (`teaagent/`)

| File | Line | Comment | Context | Action |
|------|------|---------|---------|--------|
| [`teaagent/issue_intake.py`](../../teaagent/issue_intake.py) | 195 | `# TODO: Implement GitHub API integration` | Fixed: stub now raises `NotImplementedError` with a helpful message instead of returning fake data that could mislead callers. | Implement GitHub API call (needs a PAT or app credential) to replace the `NotImplementedError`. |

---

## Scripts (`scripts/`)

These are utility/monitoring scripts, not production runtime. The TODOs here
are stubs left from scaffolding and are lower priority.

| File | Lines | Comment | Context | Action |
|------|-------|---------|---------|--------|
| [`scripts/opencode_gap_watch.py`](../../scripts/opencode_gap_watch.py) | 21, 29 | `# TODO: Implement actual GitHub API check` | Two stubs in `check_opencode_releases` and `check_competing_tools` — both return hardcoded dummy data. | Implement or delete if the script is unused. |
| [`scripts/opencode_gap_watch.py`](../../scripts/opencode_gap_watch.py) | 37 | `# TODO: Implement actual community platform checks` | `check_community_signals` returns dummy data. | Same. |
| [`scripts/opencode_gap_watch.py`](../../scripts/opencode_gap_watch.py) | 82 | `# TODO: Implement actual document update` | `update_gap_analysis_document` is a no-op. | Implement or delete. |
| [`scripts/community_presence_monitor.py`](../../scripts/community_presence_monitor.py) | 21, 29, 37, 45, 53, 71 | Multiple `# TODO: Implement actual * API check` stubs | Functions return hardcoded dummy data for GitHub, Reddit, HN, Dev.to, community scanning, and document update. | Implement or quarantine behind a `--dry-run` flag if the script is meant to be operational. |

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
| `run_store.py:143-149` | `task_for_run` raises on REPL suspensions | TICKET-16 Phase 2: write `run_started` at suspend time |
| `_chat.py:538-586` | `chat_command` ignores `args.task` | TASK-DD2-001: forward positional task to `run_tui` |
| `tui/__init__.py:1107` | `_load_tui_state` unconditionally overwrites `self.root` | TASK-DD2-002: guard with `_root_explicit` flag |

---

## Summary counts

| Category | Count |
|----------|-------|
| Explicit `# TODO` in production (`teaagent/`) | 1 |
| Explicit `# TODO` in scripts | 9 |
| Implicit architectural TODOs (ticketed) | 3 active, 4 fixed |
| **Active total** | **13** |
| `issue_intake.py:195` stub | 1 | Fixed: now raises `NotImplementedError` instead of returning fake data |
| **Fixed historical entries retained** | **5** |
