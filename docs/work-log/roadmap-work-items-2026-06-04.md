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

## Notes

- The highest-value work is still trust repair, not broad expansion.
- Documentation should accompany code and verification, not replace them.
