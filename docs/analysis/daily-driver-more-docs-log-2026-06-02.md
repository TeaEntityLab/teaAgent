# Daily-Driver More Docs Log
# 2026-06-02

This log records the additional "more docs" pass after the June 2 status, risk, and
ticket layer.

## Docs added in this pass

| Area | New docs |
|------|----------|
| Guides | Command cookbook, TUI chat recipes, agent-mode recipes, approval recipes, recovery recipes, guide index. |
| Debugging | Daily-driver debug playbook, TUI chat checklist, agent resume checklist. |
| Reliability | Reliability scorecard, trust-sensitive invariants, interactive failure taxonomy. |
| Security | Safety boundaries, path/root threat scenarios, approval abuse cases. |
| Governance | Release gates, review checklist, documentation maintenance policy. |
| Design | UX principles, cockpit information architecture, TUI chat parity notes. |
| Modules | TUI, run store, git sandbox, context pack, pinned file specs/risks/inspection docs. |
| Ops | Shift handoff, incident response. |
| API | Daily-driver command contracts. |
| Decisions | Decision backlog. |
| Reviews | Red-team review. |
| Plans | Verification backlog. |

## Advice captured

| ID | Advice |
|----|--------|
| MD-001 | Keep user-facing guides separate from code-grounded audits. |
| MD-002 | Every troubleshooting symptom should point to a safer next command. |
| MD-003 | Every module risk should name the owning module and ticket. |
| MD-004 | Treat "read-only" and "dry-run" as user trust contracts. |
| MD-005 | Add negative tests for every command that can be misused. |
| MD-006 | Use incident-response docs to capture surprising daily behavior before it is overwritten. |
| MD-007 | Use release gates to prevent docs from claiming readiness before path-level tests exist. |
| MD-008 | Make command contracts boring and explicit. |
| MD-009 | A guide index is needed once docs span multiple directories. |
| MD-010 | Module docs should explain non-responsibilities, not just responsibilities. |

## Risks of this docs expansion

| Risk | Mitigation |
|------|------------|
| More docs can bury the current answer. | Keep `daily-driver-current-status.md` and guide index as front doors. |
| Module docs can drift from code. | Link each module doc to ticket and inspection questions. |
| Security docs can overstate safety. | Use "open risks" and "required tests" wording. |
| Governance docs can become process theater. | Tie gates to concrete commands and blockers. |

## Recommended next implementation move

The next non-doc move should be TASK-DD2-002, because explicit root correctness affects
all later TUI work.
