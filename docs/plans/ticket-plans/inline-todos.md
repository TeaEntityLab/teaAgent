# Inline TODO / FIXME / XXX Catalog
**Generated:** 2026-06-02 | **Scope:** `teaagent/` and `scripts/`

---

## Production source (`teaagent/`)

| File | Line | Comment | Context | Action |
|------|------|---------|---------|--------|
| [`teaagent/issue_intake.py`](../../teaagent/issue_intake.py) | 195 | `# TODO: Implement GitHub API integration` | Inside `_parse_github_issue(self, issue_url)` — method returns a mock `ParsedIssue` with title "GitHub Issue (API not implemented)" and logs a warning. The entire `IssueIntake.from_github_url` flow hits this stub. | Implement GitHub API call (needs a PAT or app credential). Until then the stub should raise `NotImplementedError` rather than returning fake data that could mislead callers. |

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

| Location | Pattern | Implicit TODO |
|----------|---------|---------------|
| `tui/__init__.py:812-814` | `_handle_undo` calls `_restore_checkpoint` (git-stash) | TICKET-12: migrate to `UndoJournal` via `ChatSessionController` |
| `chat_session_controller.py:143-159` | `except (AttributeError, TypeError): pass` | TICKET-13: replace with proper DI; let real errors surface |
| `chat_repl.py:89-93` | `suspension_data['audit_trail']` | TICKET-15: remove stale field |
| `chat_repl.py:142,145` | Broken resume commands printed at suspend | TICKET-16 Phase 1: print only the working command |
| `run_store.py:143-149` | `task_for_run` raises on REPL suspensions | TICKET-16 Phase 2: write `run_started` at suspend time |
| `_chat.py:538-586` | `chat_command` ignores `args.task` | TASK-DD2-001: forward positional task to `run_tui` |
| `tui/__init__.py:1107` | `_load_tui_state` unconditionally overwrites `self.root` | TASK-DD2-002: guard with `_root_explicit` flag |

---

## Summary counts

| Category | Count |
|----------|-------|
| Explicit `# TODO` in production (`teaagent/`) | 1 |
| Explicit `# TODO` in scripts | 9 |
| Implicit architectural TODOs (ticketed) | 7 |
| **Total** | **17** |
