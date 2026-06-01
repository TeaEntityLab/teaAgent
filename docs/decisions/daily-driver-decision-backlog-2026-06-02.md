# Daily-Driver Decision Backlog
# 2026-06-02

Decision backlog for maintainers.

## Needs decision soon

| ID | Decision | Default recommendation |
|----|----------|------------------------|
| DB-001 | Should dry-run initialize `.teaagent` on first run? | No hidden writes; announce if initialization is intentional. |
| DB-002 | What does cost cap `0` mean? | Pick one meaning and test it. |
| DB-003 | Should absolute pinned files ever be allowed? | No by default. |
| DB-004 | Should TUI checkpoint restore remain as `/undo`? | Rename or label mechanism. |
| DB-005 | Should background commands exist before true background execution? | No; use suspend/review wording. |

## Can wait

| ID | Decision | Default recommendation |
|----|----------|------------------------|
| DB-006 | Should `TUIConfig` replace long `run_tui` parameters? | Yes when next TUI feature touches parameter flow. |
| DB-007 | Should old chat REPL code be deleted or deprecated first? | Deprecate only if imports still need migration. |
| DB-008 | Should docs move into dated subdirectories? | Not until current-status/index links are stable. |

## Decision rule

Prefer the decision that makes user authority, cost, root, and recovery easier to
predict.
