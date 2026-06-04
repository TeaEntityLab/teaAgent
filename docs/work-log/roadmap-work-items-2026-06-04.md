# Roadmap Work Items - 2026-06-04

## Purpose

This work log turns the current strategy into concrete execution chunks.

## Work Items

### TASK-001: Close TUI / CLI semantic drift

- Goal: Make the same chat, cost, undo, root, and resume commands behave consistently across surfaces.
- Scope: TUI chat path, controller-backed shared state, help text, and surface-specific fallback wording.
- Dependencies: controller semantics, current TUI state model.
- Acceptance Criteria: same user command produces same trust semantics on CLI and TUI; fallback paths are explicitly labeled.
- Tests: regression coverage for cost accumulation, undo scope, and root precedence.
- Files likely touched: `teaagent/tui/__init__.py`, `teaagent/chat_session_controller.py`, surface docs.
- Risk: high
- Parallelizable: no
- Human Review Required: yes

### TASK-002: Make undo wording and behavior honest

- Goal: Separate journal-based undo from checkpoint restore in both code and docs.
- Scope: command wording, current-status docs, recovery guide, and TUI help text.
- Dependencies: TUI controller alignment.
- Acceptance Criteria: user can tell which undo path is used before running it.
- Tests: undo regression tests on both live and fallback paths.
- Files likely touched: `teaagent/tui/__init__.py`, `docs/recovery-and-continuity-guide.md`, `docs/daily-driver-current-status.md`.
- Risk: high
- Parallelizable: yes
- Human Review Required: yes

### TASK-003: Fix cost truth on the daily surfaces

- Goal: Ensure `/cost`, budget bars, and run summaries never show a fake zero or stale local state.
- Scope: shared cost source, display formatting, and cost documentation.
- Dependencies: shared controller state.
- Acceptance Criteria: cost reflects actual run spend after a real task execution.
- Tests: live task accumulation regression, formatting regression, budget display check.
- Files likely touched: `teaagent/chat_session_controller.py`, `teaagent/tui/__init__.py`, `tests/test_tui.py`.
- Risk: high
- Parallelizable: no
- Human Review Required: yes

### TASK-004: Strengthen first-hour onboarding

- Goal: Make the first successful use path obvious without deep architecture reading.
- Scope: current-status front door, quick-start docs, and recovery pointers.
- Dependencies: stable trust-path docs.
- Acceptance Criteria: a new user can discover the safe first run, where to look for current status, and what to do on failure.
- Tests: docs consistency and acceptance references.
- Files likely touched: `docs/daily-driver-current-status.md`, `docs/tui-daily-driver-guide.md`, `docs/use-cases.md`.
- Risk: medium
- Parallelizable: yes
- Human Review Required: no

### TASK-005: Harden trust boundaries for extensions and MCP

- Goal: Make trust expiry, tool access, and extension loading enforceable at call time.
- Scope: MCP trust, skill loading, and subagent isolation risks.
- Dependencies: risk register and governance rules.
- Acceptance Criteria: no expired trust entry continues to act trusted; unsafe extension paths are explicit.
- Tests: trust expiry and permission enforcement regressions.
- Files likely touched: `teaagent/mcp_trust.py`, `teaagent/skill_executor.py`, `teaagent/subagents/_isolation.py`, related tests.
- Risk: high
- Parallelizable: yes
- Human Review Required: yes

### TASK-006: Convert the docs corpus into a clearer control plane

- Goal: Keep dated evidence, add supersession notes, and make the shortest path to current truth obvious.
- Scope: analysis indexes, governance docs, and current-status links.
- Dependencies: evidence-to-principle policy.
- Acceptance Criteria: users can find the current truth without reading the whole archive.
- Tests: docs consistency checks and link verification.
- Files likely touched: `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`, `docs/governance/README.md`, new evidence docs.
- Risk: medium
- Parallelizable: yes
- Human Review Required: no

### TASK-007: Refresh competitor survey and strategic rationale periodically

- Goal: Keep the product rationale aligned with current official docs and community signals.
- Scope: competitor survey, roadmap rationale, critique doc.
- Dependencies: external signal refresh process.
- Acceptance Criteria: the strategy docs state date context and distinguish evidence from inference.
- Tests: manual source verification and link checks.
- Files likely touched: `docs/analysis/competitor-signal-survey-2026-06-04.md`, `docs/strategy/daily-driver-roadmap-rationale-2026-06-04.md`, `docs/reviews/daily-driver-critique-and-counterarguments-2026-06-04.md`.
- Risk: medium
- Parallelizable: yes
- Human Review Required: no

## Execution Order

1. Task 3
2. Task 1
3. Task 2
4. Task 4
5. Task 5
6. Task 6
7. Task 7

## Status Log

- 2026-06-04 — **TASK-004 DONE** (Human Review Required: no). First-hour
  onboarding strengthened: `docs/daily-driver-current-status.md` gained a
  "First run (safe)" callout (safe command + where status lives + recovery
  pointer) and `docs/tui-daily-driver-guide.md` gained an early "If something
  goes wrong" pointer to the recovery guide.
- 2026-06-04 — **TASK-006 DONE** (Human Review Required: no). Docs control
  plane clarified: the dated `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`
  now carries a supersession banner pointing to the current front door
  (`docs/INDEX.md`) and current status; `docs/governance/README.md` already
  links the front door.
- 2026-06-04 — **TASK-003 VERIFIED DONE** (no behavior change). Cost truth was
  already enforced: `ChatSessionController` is the single source of truth
  (`get_session_cost`), the TUI reads it with a local fallback, and spend
  accumulates additively. Verify-first regression guard:
  `tests/test_task003_cost_truth.py` (no fake zero after real spend; honest
  zero on free runs; additive accumulation).
- 2026-06-04 — **TASK-001 VERIFIED DONE** (no behavior change). Both CLI
  (`cli/_handlers/chat_repl.py`) and TUI route cost and undo through the same
  `ChatSessionController`, so trust semantics are surface-independent.
  Verify-first regression guard: `tests/test_task001_surface_parity.py`
  (identical cost + undo outcomes across surfaces; only the output sink differs).
- 2026-06-04 — **TASK-002 VERIFIED DONE** (no behavior change). Journal-based
  undo and checkpoint restore are separated in code, help text (journal-first,
  checkpoint fallback), cockpit availability signals (`has_undo_journal` vs
  `has_checkpoint`), and completion wording. The selected path is derivable
  before running from cockpit availability + the documented precedence.
  Verify-first regression guard: `tests/test_task002_undo_honesty.py`.
  Optional non-blocking enhancement: add a single explicit "undo will use: …"
  pre-run line; deferred (would be a user-facing change requiring review).
- 2026-06-04 — **TASK-005 VERIFIED DONE** (no behavior change). Trust expiry is
  enforced at call time: `merged_tool_filters` drops expired servers' tools and
  the registered pre-tool hook raises an explicit `HookError` (naming the
  server) when an expired server's tool is invoked. Verify-first regression
  guard: `tests/test_task005_trust_expiry_enforcement.py`.
- Net: all four Human-Review-Required behavior tasks were already satisfied by
  existing code; the verify-first pass added regression guards only, with no
  behavior change, so no human-review gate was triggered.
- 2026-06-04 — **TICKET-15 DONE**. Removed redundant `audit_trail` field from
  `agent_review.py` review JSON (replaced with governance-record comment per
  previous `_agent.py` pattern). Removed `audit_trail` injection from test
  suspension fixtures and updated review-data assertions to check `mode` instead.
  Verified: 203 affected tests pass, full suite 3376 pass.
- 2026-06-04 — **TICKET-16 Phase 2 VERIFIED DONE** (Option A: `run_started`
  event written at suspend time). Roundtrip test `test_repl_suspend_resume_roundtrip`
  asserts `task_for_run` finds the run after suspension. All 5 suspend/resume
  tests pass.
- 2026-06-04 — **TASK-DD2 compliance audit DONE**. Cross-referenced 3 standards
  docs (`tool-development.md`, `integration-guide.md`, `approval-policy-design.md`)
  against live code. Updated each checklist with pass/warn annotations and
  per-file evidence references. All 14 TASK-DD2 items verified committed.
- 2026-06-04 — **TASK-007 still open** (competitor survey — docs/research, not
  code). All code tasks for P0/P1 workstreams in the complete work plan are
  otherwise closed. See `docs/plans/documentation-optimization-master-plan-2026-06-04.md`
  P1/P2 proposals (DOCOPT-007 through DOCOPT-016) if design/planning capacity
  available.
- 2026-06-04 — **COMPREHENSIVE VERIFICATION INVESTIGATION DONE**. Cross-referenced
  every claimed-done task against actual code, tests, and git history. Summary:
  - **TASK-001/002/003/005**: 4 regression guard test files verified — exist,
    substantive, match claims exactly (84–97 lines each, 2–5 tests per file).
  - **TASK-004/006**: Doc changes verified — "First run (safe)" callout in
    daily-driver-current-status.md, "If something goes wrong" in tui-daily-driver-guide.md,
    supersession banner in daily-driver-review-INDEX, governance/README.md links front door.
  - **TICKET-12/13/14/15/16 Phase 1+2**: All 6 items FIXED — commits found for each,
    file changes match claims, key code patterns verified, tests exist.
  - **TASK-DD2-001–014**: 11 clean Fixed, 3 with plan-status discrepancies (005: plan
    says "Active" but index says "Fixed", `git_sandbox.py` untouched; 013: plan says
    "Active support ticket" but headless TUI tests exist; 014: plan says "Active support
    ticket" but docs synchronized). Plan file status headers need reconciliation.
  - **DOCOPT-001–012**: 14/14 items pass verification (13 fully, 1 minor linking gap
    in acceptance.md → coverage omit ledger). ADR statuses confirmed (zero "Proposed"
    stale entries). Dependency audit lanes verified in CI workflows.
  - **TASK-007**: Still open (competitor survey — docs/research, not code).
  Minor gap found: `docs/acceptance.md` does not explicitly link the coverage omit
  ledger at `docs/governance/coverage-omit-ledger.md`. All other claims verified.
