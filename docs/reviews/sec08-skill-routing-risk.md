# Reflective-Risk Report: SEC-08 Skill Routing Hardening

Date: 2026-07-01. Action ID: S-P2-10.
Security surface: skill/subagent isolation routing and `directory-snapshot` compatibility mode.

## Goal

Reduce SEC-08 automatic exposure by removing silent auto-selection of
`directory-snapshot` for skill isolation. `directory-snapshot` is a workspace file
copy only; it does not provide OS/process isolation. It remains available only as
an explicit compatibility mode, and actual subagent preparation still requires
`acknowledge_no_os_isolation=True`.

## Stakeholders

Owner-operator, skill authors, subagent users, and maintainers of the skill
execution/routing contract.

## Assets at Risk

Host process namespace, host filesystem outside the workspace (`~/.ssh`, `/etc`,
`/proc`), environment variables, and operator trust in the term "sandbox".

## Threat Model

A skill or subagent path is auto-routed to `directory-snapshot`; the operator sees
an isolation-like label but the code runs as a host process and can read host
paths. Prior warning/ack gates protected direct subagent preparation, but
`SkillRouter` still used `directory-snapshot` as the low-risk/default/WASM-fallback
auto choice.

## Assumption Audit

- ASSUMPTION: `prepare_subagent_isolation` already blocks direct
  `directory-snapshot` use without an explicit ack. VERIFIED at
  `_isolation.py:288-298` and by `test_directory_snapshot_without_acknowledgment_is_rejected`.
- ASSUMPTION: auto skill routing was the remaining silent directory-snapshot path.
  VERIFIED by `skill_router.py` and tests that previously asserted low-risk skills
  used directory-snapshot.
- ASSUMPTION: using Docker for auto routing preserves local LOW-risk usability on
  machines without Docker. VERIFIED by `execute_skill`: LOW-risk Docker
  unavailability keeps the existing `docker_fallback_subprocess` backend, but the
  routing no longer labels the run as directory-snapshot isolation. Non-low-risk
  remains fail-closed on Docker unavailability.

## Evidence Check

- `SkillRouter._auto_select_sandbox` now returns `SandboxType.DOCKER` for LOW risk
  and default fallback.
- WASM unavailable/incompatible fallback returns Docker, not directory-snapshot.
- `isolation_for_sandbox_type(SandboxType.WASM)` maps to Docker for subagent
  isolation wrappers because `prepare_subagent_isolation` has no WASM process
  boundary.
- Explicit `SandboxType.DIRECTORY_SNAPSHOT` still maps to `directory-snapshot` for
  compatibility and is governed by the existing ack gate.
- Tests: `tests/test_skill_router.py`,
  `tests/acceptance/test_sandbox_enhancement_flow.py`,
  `tests/test_isolation_acknowledgment_flag.py`,
  `tests/test_subagent_isolation.py`,
  `tests/acceptance/test_subagent_directory_snapshot_isolation_flow.py`.

## Authority / Tool Boundary

In scope: routing defaults in `teaagent/skill_router.py`, acceptance/unit tests,
risk register, action register, and docs inventory. Out of scope: removing
`directory-snapshot` entirely, changing Docker runtime internals, or changing the
LOW-risk Docker fallback subprocess policy.

## Failure Modes

- Docker unavailable for LOW-risk skill: unchanged fallback subprocess path, now
  labelled as `SandboxType.DOCKER` with backend `docker_fallback_subprocess`.
- User explicitly requests directory-snapshot: compatibility path remains, but
  direct subagent preparation still requires `acknowledge_no_os_isolation=True`.
- Non-low-risk skill without Docker/WASM: existing fail-closed behavior remains.

## Worst-case Scenario

A low-risk skill still executes locally because Docker is unavailable. This is not
represented as directory-snapshot isolation anymore; non-low-risk remains
fail-closed. Full elimination of subprocess fallback is a separate breaking UX
change and should have its own ADR.

## Safe Dry-run Plan

Run focused skill routing/isolation tests and docs validator. No network, no
credentials, no destructive operations.

## Rollback Plan

`git revert` the commit. The change is routing/test/docs only; no persisted-state
or migration concern.

## Bounded Execution

Single commit. No production deployment. No external I/O.

## Audit Log Plan

No runtime audit event added or removed. Risk/action register rows record the
change for governance audit.

## Human Review Required

Yes for security posture semantics, though the changed code path is not listed in
`high_risk_paths.yaml`.

## Human Approval Gate

Owner instructed: "Fix all known high risks one by one" and then "continue".
This is the next bounded SEC-08 hardening slice after SEC-09/SEC-15.

## Acceptance Criteria

- Auto LOW/default/WASM-fallback skill routing chooses Docker, not directory-snapshot.
- Explicit directory-snapshot still maps for compatibility and remains ack-gated.
- Focused tests pass.
- SEC-08 risk register row reflects reduced likelihood (M/M=4) with evidence.

## Go / No-go Decision

**GO** — small, reversible hardening that removes the silent directory-snapshot
auto route while preserving explicit compatibility and existing LOW-risk fallback
semantics.
