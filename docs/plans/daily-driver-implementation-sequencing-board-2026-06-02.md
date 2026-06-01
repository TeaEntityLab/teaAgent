# Daily-Driver Implementation Sequencing Board
# 2026-06-02

This board turns the latest docs and ticket plans into an implementation order. It is
optimized for stability, UX trust, and small reviewable changes.

## Now

| Order | Work | Why first | Proof |
|-------|------|-----------|-------|
| 1 | TASK-DD2-002: explicit root guard | Prevents work in wrong repo before later tasks run. | State-load test proves CLI root wins. |
| 2 | TASK-DD2-001: verify/close `teaagent chat <task>` | Working tree appears patched; closure needs tests. | CLI/TUI test proves task is run or refused. |
| 3 | TICKET-14: unmask TUI cost test | Makes next cost fix measurable. | Test fails without active-path accumulation. |
| 4 | TICKET-12 Step A: verify/close TUI cost stop-gap | Working tree has `+= result.cost_cents`; prove it through UI path. | TUI task increments session cost. |
| 5 | TICKET-16 Phase 1: honest suspend/background wording | Removes broken instructions. | Help/output no longer advertises broken command. |

## Next

| Work | Dependency | Proof |
|------|------------|-------|
| TICKET-12 full TUI controller migration | Stop-gap and test unmasking | REPL/TUI parity tests for result, cost, budget, undo. |
| TICKET-13 controller error handling | Controller tests | Real AttributeError/TypeError surfaces or is classified. |
| TASK-DD2-003 TUI cost ledger | TICKET-12 or stop-gap | Cost/budget state comes from one source. |
| TASK-DD2-004 path approval scope | Approval UX review | Empty path rejected or clearly classified. |
| TASK-DD2-005 git sandbox lifecycle | Human decision on default semantics | Help text, docs, and runtime agree. |
| TASK-DD2-008 read-only/dry-run side effects | Policy decision on first-run initialization | Fresh workspace snapshot proves invariant. |
| TASK-DD2-010 pinned file containment | Security review | Absolute and parent paths are rejected. |

## Later

| Work | Why later |
|------|-----------|
| TICKET-15 cleanup | Lower risk after parity paths settle. |
| TASK-DD2-006 lifecycle wording | Depends on resume/background behavior decision. |
| TASK-DD2-007 stale chat cleanup | Safer after parity and tests prove replacement. |
| TASK-DD2-009 context pack read-only truth label | Needs naming decision. |
| TASK-DD2-011 corrupt state visibility | Can grow with daily/preflight health checks. |
| TASK-DD2-012 failure-card matching guard | Memory relevance tuning after safety fixes. |

## Parallel lanes

| Lane | Can run in parallel with | Avoid overlap with |
|------|--------------------------|--------------------|
| Docs/status updates | Most code fixes | Index edits in same files. |
| Root precedence tests | Chat initial task work | Shared `run_tui` signature edits. |
| TUI cost test unmasking | Lifecycle wording | Full TUI controller migration. |
| Agent mode wording | TUI cost work | TICKET-16 Phase 2 resume storage. |
| Approval path-scope tests | Docs updates | Approval manager refactor. |

## Stop conditions

Stop the batch and re-plan if:

- A fix requires broad rewrite of controller/TUI boundaries.
- A test can only pass by injecting the state being asserted.
- A command becomes more permissive with approvals.
- Root, cost, or undo behavior changes without updated user-facing docs.
