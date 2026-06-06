# Ticket Execution Plans — Master Index
**Date:** 2026-06-02 | **Derived from:** daily-driver review passes 1-4 (2026-06-01)

> **Claim class:** Current truth for daily-driver ticket closure and execution order.
>
> **Owns:** Which TICKET/TASK-DD2 items are fixed and their verification evidence.
>
> **Does not own:** Roadmap horizons (`roadmap-status.md`) or historical finding
> narratives in dated analysis files. For finding status roll-up see
> [Active Findings Status Ledger](../../analysis/active-findings-status-ledger-2026-06-06.md).
>
> **Review trigger:** Ticket closure status or execution order changes.
> **Last reviewed:** 2026-06-06

---

## Recommended Execution Order

The critical path as of the June 2 re-review is:

```
TASK-DD2-002 (explicit TUI root)
  └─► TASK-DD2-001 (chat positional task verify/close)
        └─► TICKET-14 (un-mask test)
              └─► TASK-DD2-003 / TICKET-12 Step A (cost stop-gap verify/close)
                    └─► TICKET-12 Steps B-D (full TUI controller migration)
                          └─► TICKET-13 (stop swallowing errors)
                                └─► TASK-DD2-007 / TICKET-15 (cleanup)

TASK-DD2-004 (path approval scope) <- safety-sensitive, can run in parallel
TASK-DD2-005 (git sandbox lifecycle) <- safety-sensitive, needs human review
TASK-DD2-006 / TICKET-16 Phase 1 (honest lifecycle wording) <- independent
TICKET-16 Phase 2 (real resume) <- after lifecycle wording and run-store decision

TASK-DD2-008..012 (new June 2 stability risks) <- parallel support lane
TASK-DD2-013..014 (test/doc hardening) <- support lane
```

## Related Documentation-Control Work

The June 4 documentation optimization package is tracked outside this
daily-driver ticket directory because it governs the whole Markdown corpus, not
only the daily-driver fixes:

- [Documentation State Review](../../analysis/documentation-state-review-2026-06-04.md)
- [Documentation Operating Model](../../governance/documentation-operating-model-2026-06-04.md)
- [Documentation Optimization Master Plan](../documentation-optimization-master-plan-2026-06-04.md)
- [Documentation Optimization Work Items](../../work-log/documentation-optimization-work-items-2026-06-04.md)

---

## Tickets

| Ticket | Priority | Size | File | Summary |
|--------|----------|------|------|---------|
| [TICKET-14](TICKET-14-plan.md) | P1 | XS | `tests/test_tui.py` | Fixed: masking test replaced with active-path cost accumulation coverage |
| [TICKET-12 Step A](TICKET-12-plan.md) | P1 | XS (1 line) | `tui/__init__.py` | Fixed: TUI cost uses controller-backed session state |
| [TICKET-12 Steps B-D](TICKET-12-plan.md) | P1 | M | `tui/__init__.py`, `chat_session_controller.py` | Fixed: TUI uses `ChatSessionController`; undo is journal-first with checkpoint fallback |
| [TICKET-13](TICKET-13-plan.md) | P2 | S | `chat_session_controller.py` | Fixed: exception swallowing replaced with proper isinstance checks and dependency injection |
| [TICKET-15](TICKET-15-plan.md) | P3 | XS | `chat_repl.py`, `_agent.py` | Fixed: redundant `audit_trail` field removed; stale `/undo` help text updated |
| [TICKET-16 Phase 1](TICKET-16-plan.md) | P1 | XS | `chat_repl.py` | Fixed: print only working suspend review command; remove broken hints |
| [TICKET-16 Phase 2](TICKET-16-plan.md) | P1 | M | `chat_repl.py`, `_agent.py`, `run_store.py` | Fixed: real suspend→resume round-trip with `run_started` event at suspend time |
| [TASK-DD2-001](TASK-DD2-001-plan.md) | P1 | S | `_chat.py`, `tui/__init__.py` | Fixed: positional task forwarded to TUI REPL |
| [TASK-DD2-002](TASK-DD2-002-plan.md) | P1 | S | `tui/__init__.py` | Fixed: `_load_tui_state` respects explicit CLI root flag |
| [TASK-DD2-003](TASK-DD2-003-plan.md) | P1 | M | `tui/__init__.py`, `chat_session_controller.py` | Fixed: make TUI cost ledger authoritative |
| [TASK-DD2-004](TASK-DD2-004-plan.md) | P0 | M | `teaagent/ergonomics/_approval_grants.py`, `teaagent/cli/_handlers/agent_helpers.py` | Fixed: path-scoped approvals hardened; tests: `test_empty_path_globs_rejected_ds12`, `test_smart_hitl_approval_p_without_path_stays_denied` |
| [TASK-DD2-005](TASK-DD2-005-plan.md) | P1 | M | `_agent.py`, `git_sandbox.py` | Fixed: git sandbox lifecycle preserves sandbox object through run completion (core fix). Broader ACs partially addressed — see plan file. |
| [TASK-DD2-006](TASK-DD2-006-plan.md) | P1 | S | `teaagent/cli/_handlers/chat_repl.py`, `docs/cli.md` | Fixed: lifecycle wording made honest; covered by chat command/help tests |
| [TASK-DD2-007](TASK-DD2-007-plan.md) | P2 | M | `teaagent/cli/_handlers/_chat.py`, `tests/test_cli_chat.py` | Fixed: stale chat code removed/retired |
| [TASK-DD2-008](TASK-DD2-008-plan.md) | P1 | S | `teaagent/ergonomics/dry_run.py`, `tests/test_context_pack.py` | Fixed: read-only and dry-run side-effect contract enforced |
| [TASK-DD2-009](TASK-DD2-009-plan.md) | P1 | XS | `context_pack.py` | Fixed: context-pack read-only truth label passes through caller's readonly argument |
| [TASK-DD2-010](TASK-DD2-010-plan.md) | P0 | S | `pinned_file.py` | Fixed: enforce pinned-file workspace containment |
| [TASK-DD2-011](TASK-DD2-011-plan.md) | P1 | S | `teaagent/memory/catalog.py`, `tests/test_tui.py` | Fixed: corrupt memory/run state surfaced with warnings |
| [TASK-DD2-012](TASK-DD2-012-plan.md) | P2 | S | `failure_card.py` | Fixed: failure-card matching bounded |
| [TASK-DD2-013](TASK-DD2-013-plan.md) | P1 | M | `tests/test_tui.py` | Fixed: headless TUI path tests hardened |
| [TASK-DD2-014](TASK-DD2-014-plan.md) | P2 | S | `docs/daily-driver-current-status.md`, `scripts/validate_docs_consistency.py` | Fixed: daily-driver docs synchronization |

---

## Key Files Referenced

| File | Relevant Tickets |
|------|-----------------|
| [`teaagent/tui/__init__.py`](../../teaagent/tui/__init__.py) | TICKET-12, TICKET-14, TASK-DD2-001, TASK-DD2-002 |
| [`teaagent/chat_session_controller.py`](../../teaagent/chat_session_controller.py) | TICKET-12, TICKET-13 |
| [`teaagent/cli/_handlers/chat_repl.py`](../../teaagent/cli/_handlers/chat_repl.py) | TICKET-15, TICKET-16 |
| [`teaagent/cli/_handlers/_agent.py`](../../teaagent/cli/_handlers/_agent.py) | TICKET-15, TICKET-16 |
| [`teaagent/run_store.py`](../../teaagent/run_store.py) | TICKET-16 |
| [`teaagent/cli/_handlers/_chat.py`](../../teaagent/cli/_handlers/_chat.py) | TASK-DD2-001 |
| [`teaagent/cli/_agent_parsers.py`](../../teaagent/cli/_agent_parsers.py) | TASK-DD2-001 |
| [`tests/test_tui.py`](../../tests/test_tui.py) | TICKET-14, TICKET-12 |
| [`teaagent/cli/_handlers/agent_helpers.py`](../../teaagent/cli/_handlers/agent_helpers.py) | TASK-DD2-004 |
| [`teaagent/ergonomics/_approval_grants.py`](../../teaagent/ergonomics/_approval_grants.py) | TASK-DD2-004 |
| [`teaagent/git_sandbox.py`](../../teaagent/git_sandbox.py) | TASK-DD2-005 |
| [`teaagent/ergonomics/dry_run.py`](../../teaagent/ergonomics/dry_run.py) | TASK-DD2-008 |
| [`teaagent/context_pack.py`](../../teaagent/context_pack.py) | TASK-DD2-009 |
| [`teaagent/memory/pinned_file.py`](../../teaagent/memory/pinned_file.py) | TASK-DD2-010 |
| [`teaagent/memory/catalog.py`](../../teaagent/memory/catalog.py) | TASK-DD2-011 |
| [`teaagent/memory/failure_card.py`](../../teaagent/memory/failure_card.py) | TASK-DD2-012 |

---

## Inline TODOs

See [inline-todos.md](inline-todos.md) for the full catalog of `# TODO`,
`# FIXME`, and implicit architectural TODOs across the codebase.

**TL;DR:** 1 production `TODO` (`issue_intake.py:195` — GitHub API stub), 9 in
monitoring scripts, 7 implicit architectural items (all ticketed above).

---

## Architectural Recommendations

### 1. Single source of truth for chat execution
`ChatSessionController` was designed to be that source. TICKET-12 completes
the original intent. Once done, any new chat behavior (streaming, tool-call
visibility, cost alerts) is written once and works on both surfaces.

### 2. Dependency injection over exception-based mock detection
TICKET-13 is a specific instance of a general pattern: production code should
never infer "I am being tested" from exception types. Use explicit `None`
checks or pass stub objects that satisfy a protocol. This is the standard
Python pattern for testable code.

### 3. Suspend→resume should be a first-class feature, not a printout
TICKET-16 Phase 2 closes the gap. The governance side (scoped approvals,
plan-gate, auto-compact) is already solid in `agent_resume_command`. The only
missing piece is writing the task and observations to `RunStore` at suspend
time so the existing resume machinery can find them.

### 4. Test hygiene: never inject the state you claim to verify
TICKET-14 is a concrete lesson. Tests that set `_session_cost_cents = 123` and
assert the display shows `$1.23` verify the formatter, not the accumulation.
Going forward: prefer end-to-end tests that drive the full call path.

### 5. Future-proofing: `run_tui` parameter surface is growing
`run_tui` now has 16 keyword arguments. As features are added, consider
building a `TUIConfig` dataclass and passing it as a single argument. This
also makes it easier to serialize/deserialize TUI state (TASK-DD2-002) without
keeping `_save_tui_state` and `_load_tui_state` in sync by hand.

### 6. Treat partial fixes as verify/close work
The June 2 re-review found that chat positional task forwarding and TUI cost
accumulation have partial working-tree fixes. Keep the ticket open until active-path
tests, manual smoke, and user-facing docs agree.

### 7. Read-only must mean no hidden writes, or be renamed
Dry-run/preflight/context-pack evidence should not imply no filesystem side effects
unless the command path enforces that invariant. If first-run initialization is
intentional, say so directly in the output and docs.
