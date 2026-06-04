# Project State Cross-Review Fact Check
# 2026-06-04

## Purpose

This document compares the pasted comprehensive project review with the current
repository state. It records what is confirmed, what needs correction, and what
should be treated as inference rather than fact.

The review is useful because it names the right strategic tension: TeaAgent is
late-P0 / early-P1, strong in governance infrastructure, and exposed to trust
repair debt. The review is also imperfect: several counts are stale, some risk
severities are inconsistent with local registers, and a few claims compress
different kinds of evidence into one line.

## Status Correction

This fact check was measured before the ADR status cleanup on 2026-06-04. The
current ADR index has no live `Proposed` ADR rows; ADR 0025 is now recorded as
implemented for both REPL and TUI chat surfaces. Treat the earlier "6 proposed
ADRs" finding as a valid stale-snapshot finding, not as the current source of
truth. Current truth lives in `docs/adr/README.md` and
`docs/work-log/phase-0-governance-closure-report-2026-06-04.md`.

## Baseline

These facts were measured at the start of this review against `main` at commit
`4695d46`.

| Metric | Measured value | Evidence command |
| --- | ---: | --- |
| First commit date | 2026-05-08 | `git log --reverse --format=%cs` |
| Commit count | 626 | `git rev-list --count HEAD` |
| Tracked total lines | 352,271 | `git ls-files \| xargs wc -l` |
| Tracked Python lines | 155,841 | `git ls-files '*.py' \| xargs wc -l` |
| Tracked Markdown lines | 64,420 | `git ls-files '*.md' \| xargs wc -l` |
| Markdown files | 435 | `rg --files \| rg '\.md$' \| wc -l` |
| Pytest collected tests | 3,377 | `python3 -m pytest --collect-only -q` |
| Acceptance tests collected | 441 | `python3 -m pytest tests/acceptance --collect-only -q` |
| GitHub workflows | 6 | `rg --files --hidden .github/workflows` |
| ADR files | 30 | `find docs/adr docs/decisions ...` |
| Module folders | 28 | `find docs/modules -mindepth 1 -maxdepth 1 -type d` |
| Standard module docs | 101 | `find docs/modules ... spec/api/risks/inspection` |
| Coverage omit entries | 16 | `[tool.coverage.run].omit` in `pyproject.toml` |

## Confirmed Claims

| Review claim | Status | Notes |
| --- | --- | --- |
| Project started on May 8, 2026 | Confirmed | First commit date is 2026-05-08. |
| Project is roughly late-P0 / early-P1 | Supported inference | Acceptance coverage is broad, but Phase 0 trust debt remains active. |
| 6 workflows exist | Confirmed | `ci`, `security`, `nightly-smoke`, `release`, `wasm-skill-build`, `publish-tsb`. |
| 30 ADRs exist | Confirmed with directory nuance | 25 live under `docs/adr`; 5 live under `docs/decisions`. |
| Acceptance test count is 441 | Confirmed | `docs/acceptance.md` and pytest collection agree. |
| Zero forced runtime dependency posture | Confirmed | `project.dependencies = []` in `pyproject.toml`. Optional extras carry the heavy trees. |
| Duplicate `ApprovalManager` risk exists | Confirmed | `teaagent/approval_manager.py::ApprovalManager` and `teaagent/runner/_approval_manager.py::ApprovalManager` both exist. |
| Memory catalog divergence exists | Confirmed | `teaagent/memory_legacy.py` is canonical through `teaagent/memory/__init__.py`, while `teaagent/memory/catalog.py` remains a divergent near-copy. |
| Proposed ADR debt exists | Superseded stale snapshot | At the measured baseline this review believed ADRs 0010, 0012, 0014, 0015, 0017, and 0018 were proposed; the 2026-06-04 cleanup rechecked the ADR source of truth and found no live `Proposed` ADR rows. |

## Corrected Claims

| Review claim | Correction | Why it matters |
| --- | --- | --- |
| `625 commits` | Current baseline was 626 before this documentation pass. | Small difference, but this proves the review is already stale at commit-level granularity. |
| `151K LOC` | Python LOC is about 155,841; all tracked LOC is about 352,271. | "LOC" must say whether it means Python code, all tracked text, or product code. |
| `3,359 tests` | Current collection is 3,377 tests. | Test count is moving quickly; reports should name collection date and commit. |
| `250+ markdown files` | Current count is 435 Markdown files. | Discoverability risk is larger than the review implies. |
| `93 module docs` | Current standard module-doc count is 101 across 28 module folders. | Module docs have grown; taxonomy/index work is more important, not less. |
| `18 modules zero coverage` | Current coverage omit list has 16 patterns. | Some are packages, some are single modules; call them "coverage omit patterns" unless measured by coverage XML. |
| `Circular import policy.py <-> approval_manager.py will explode by import order` | Current state is subtler: `policy.py` imports `approval_manager.py` at top level; `approval_manager.py` has a lazy import back to `policy.py`. | The risk is still real, but the failure mode is design fragility and security-boundary coupling, not necessarily immediate import failure. |

## High-Value Confirmations

### Approval bypass risk is real, not merely theoretical

`PermissionModeEnforcer.check()` allows destructive calls when
`allow_all_destructive` is true, regardless of `permission_mode`, after the
`ALLOW` and `DANGER_FULL_ACCESS` mode checks. `tests/test_policy.py` explicitly
tests `ApprovalPolicy(allow_all_destructive=True)` in default prompt mode and
expects a destructive write to pass.

That means the review's `DANGER_FULL_ACCESS bypass` framing is incomplete. The
more precise P0 issue is:

> Broad destructive bypass semantics exist through both permission mode and
> `allow_all_destructive`; at least one bypass path is not gated to
> `DANGER_FULL_ACCESS`.

### ADR status is not the same as implementation truth

ADR-0011 is listed as "Accepted and Implemented", yet duplicate approval-manager
classes still exist. That may be acceptable if the runner-local class is now only
a workflow helper, but the name collision keeps confusing future reviewers. The
real state is not simply "implemented"; it is "implemented enough to pass tests,
but still confusing enough to be a Phase 0 cleanup item."

### Optional dependency security posture needs two lanes

The base package has no mandatory runtime dependencies. The dev/managed ADK
extras can pull a much larger dependency tree, including `google-adk`, `fastapi`,
and `starlette`. The security workflow was recently tightened so the editable
`pip-audit` job scans the base install rather than accidentally auditing all
dev-only optional runtimes. This is the right base-surface policy, but it does
not remove the need for a separate optional-extra audit lane.

## Claims That Need Better Evidence

| Claim | Current issue | Better evidence needed |
| --- | --- | --- |
| "Security maturity is 2.5 / 5" | The number is plausible but subjective. | Scorecard with criteria, weights, and pass/fail evidence. |
| "UX is 2.5 / 5" | This compresses CLI breadth, TUI parity, docs, and first-hour onboarding into one score. | Separate scores for first-run, daily chat, TUI cockpit, recovery, and error explanation. |
| "Average 23 commits/day is sustainable for sprint but not quarter" | True-sounding but not directly proven. | Commit histogram plus defect rate, revert rate, and review latency. |
| "18 zero-coverage modules" | Current omit list has 16 patterns; not all are modules. | Coverage XML or `coverage json` grouped by package. |
| "Core harness is solid" | Broadly supported, but security bypass and duplicate boundaries remain active. | P0 trust repair exit checklist before using "solid" unqualified. |

## Overall Truth

TeaAgent is unusually mature for a 27-day-old project in documentation,
acceptance testing, and governance vocabulary. It is also carrying the exact
kind of debt that fast security-oriented agent projects accumulate: duplicate
authority paths, confusing bypass semantics, optional dependency surface area,
and documentation status drift.

The best reading is neither "this project is production-ready" nor "this project
is overbuilt." The current truth is:

> TeaAgent is a credible governance-first agent harness in late Phase 0. It has
> enough architecture and tests to be worth hardening, but it should not enter a
> feature-expansion phase until approval authority, memory authority, dependency
> audit scope, and coverage omit policy are tightened.

## What This Changes

1. Treat Phase 0 exit as a security and trust milestone, not a generic cleanup.
2. Replace broad metrics with commit-stamped evidence.
3. Do not merge ADR status into implementation status without checking code.
4. Track `allow_all_destructive` as a P0 bypass issue alongside
   `DANGER_FULL_ACCESS`.
5. Add a separate policy for optional-extra dependency auditing.
