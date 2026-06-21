# A-P0-2 Observability Error-Handling Risk Review

**Date:** 2026-06-21  
**Action:** A-P0-2  
**Scope:** Local audit, preflight audit health, cockpit data, hybrid-store health,
and child-cost observability paths.

## Goal

Replace silent exception handling with classified, non-sensitive diagnostics while
preserving each path's documented best-effort behavior.

## Assets at Risk

- Audit-chain continuity and HMAC verification evidence.
- Operator cockpit and preflight health accuracy.
- Approval-queue rollback validation.
- Child-run cost attribution.

## Threat Model

Corrupt local state, unreadable files, malformed command output, or an unexpected
backend exception can currently erase failure evidence. Conversely, logging raw
exceptions can expose paths or payload fragments, and raising from best-effort paths
can make the operator surface unavailable.

## Boundaries

- No production, network, credential, or existing run-data mutation.
- No change to approval authority or audit event schemas.
- Expected degradation remains non-fatal unless the existing contract already fails
  closed.
- Logs contain operation names and structured classification, not exception messages or
  payloads.

## Failure Modes and Controls

| Failure mode | Control |
| --- | --- |
| Silent loss of audit or health evidence | Emit a warning/error with structured category, severity, and recovery hint. |
| Sensitive data copied into logs | Do not interpolate exceptions, paths, events, or tool arguments. |
| Best-effort UI/preflight path starts raising | Preserve fallback values and add regression tests. |
| Rollback cleanup failure is reported as healthy | Track cleanup separately and include it in the overall validation result. |
| New silent handlers recur | Static regression assertion covers the bounded observability modules. |

## Dry Run and Rollback

The dry run is a focused test suite that forces every failure path before implementation.
Rollback is file-local: revert the affected handler and its test. There is no migration
or persistent-state rewrite.

## Human Review Gate

The owner explicitly authorized starting A-P0-2 on 2026-06-21. Human review remains
required before merge because the change touches audit and security-sensitive paths.

## Acceptance Criteria

1. No silent `except ...: pass` remains in the bounded observability modules.
2. Every degraded operation emits structured classification without sensitive content.
3. Existing best-effort return behavior remains intact.
4. Rollback cleanup failure makes rollback validation incomplete.
5. Focused tests, static checks, documentation checks, and pre-commit hooks pass.

## Decision

**Go for bounded local execution.** Do not broaden this change into a repository-wide
exception-handling refactor.
