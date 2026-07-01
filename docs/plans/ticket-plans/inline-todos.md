# Inline TODO / FIXME / XXX Catalog
**Generated:** 2026-06-02 | **Last reviewed:** 2026-07-01 | **Scope:** `teaagent/` and `scripts/`

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

## Implicit deferrals — resolved 2026-06-30

These were not literal `# TODO` comments (the explicit drift guard never counted
them). Each has now been either implemented for real or made explicitly honest
about being a non-gating simulation. Verified by
[`tests/test_inline_todo_resolutions.py`](../../../tests/test_inline_todo_resolutions.py).

| Location | Pattern | Resolution |
|----------|---------|------------|
| [`teaagent/consensus/consensus_validation.py`](../../../teaagent/consensus/consensus_validation.py) | Voter role was inferred from `voter_id`. | **Resolved:** `ConsensusRule.check_consensus` / `ConsensusValidator.cast_vote` accept an optional `voter_roles` map and look the role up; absent a mapping, `voter_id` is treated as its own role (documented default contract). |
| [`teaagent/domain/workflow_engine.py`](../../../teaagent/domain/workflow_engine.py) | Workflow step execution was silently simulated. | **Resolved (honest):** steps are flagged `StepExecution.simulated=True` and the log/docstring state that real agent invocation is a governed-execution (AgentRunner) boundary, deliberately deferred. No synthetic output is presented as real. |
| [`teaagent/eval_suite.py`](../../../teaagent/eval_suite.py) | Eval execution and baseline diffing were placeholders. | **Resolved:** prompt/conversational tests run via the real `model_runner`/fixture/replay seam; `_compare_with_baseline` produces a real difflib unified diff + similarity ratio; non-prompt categories carry honest `advisory_only=True` / `execution_mode='simulated'` metadata (non-gating). |
| [`teaagent/cli/_handlers/_consensus.py`](../../../teaagent/cli/_handlers/_consensus.py) | History query / config persistence "not implemented". | **Resolved (stale ref):** `consensus_history_command` and persisted config (`_load_persisted_consensus_config`) are implemented; the prior line refs were stale. |
| [`teaagent/domain/agent_factory.py`](../../../teaagent/domain/agent_factory.py) | Agent removal logged as not fully implemented. | **Resolved:** `PluginRegistry.unregister_agent` added; `remove_agent` removes from memory + disk and returns an honest bool (warns when absent). |
| [`teaagent/domain/issue_intake.py`](../../../teaagent/domain/issue_intake.py) | Plan exploration + generated command placeholders. | **Resolved:** `_build_command` uses `shlex.quote` (shell-safe); `explore` delegates to an injected `context_gatherer`/`plan_mode` collaborator when present, else returns deterministic context. |

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
| `swarm.py::_review_subagent` | returned a hardcoded mock review (`score=0.8`, `findings=['Mock code review finding']`) presented as a real review | Fixed 2026-07-01: deterministic evidence-based review scoring observed result facts (success, output, test results, relative runtime); no fabricated findings; `tests/test_swarm.py`, `tests/test_inline_todo_resolutions.py` |
| `governance/repo_map_benchmark.py::_execute_repo_map_query` | "placeholder" content grep with a false "in production, this would call the actual repo-map" claim; module still labeled `experimental — unwired` after the M5 release-gate wiring | Fixed 2026-07-01: deterministic symbol-aware AST scan (the real query the benchmark measures); module docstring now states its wired status; `tests/test_repo_map_benchmark.py` |

---

## Summary counts

| Category | Count |
|----------|-------|
| Explicit `# TODO` in production (`teaagent/`) | 0 |
| Explicit `# TODO` in scripts (unfixed stubs) | 0 |
| Implicit deferrals requiring owner / ticket | 0 review-needed |
| Implicit deferrals resolved (2026-06-30) | 6 |
| Implicit architectural TODOs (ticketed) | 0 active |
| **Active total** | **0 review-needed** |
| Fixed historical entries retained | 13 |
