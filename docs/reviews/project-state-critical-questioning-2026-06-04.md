# Project State Critical Questioning
# 2026-06-04

## Review Mode

Primary mode: AI output / project-state review.

Secondary checks: security posture, test integrity, roadmap sequencing, and
documentation governance.

The goal is to challenge the pasted comprehensive review and our own optimism.
This document should make uncomfortable questions reusable.

## Findings

### 1. The approval boundary is still the most important Phase 0 question

The review names `DANGER_FULL_ACCESS` as critical. That is directionally right,
but the sharper question is broader:

> How many independent ways can a caller bypass approval, and are all of them
> visible as explicit user intent?

Current evidence shows:

- `danger-full-access` is a first-class permission mode.
- `allow_all_destructive=True` allows destructive calls in prompt mode.
- The security risk register already tracks SEC-03: gate
  `allow_all_destructive` on `DANGER_FULL_ACCESS`.
- Tests currently encode the bypass as accepted behavior.

This is a "truth path" issue: if a user sees prompt mode but the system is
actually allowing all destructive operations, the project has violated its own
trust contract.

### 2. The project has a strong governance vocabulary, but status truth is split

The docs corpus is not weak. It may be too strong in the wrong shape. There are
435 Markdown files, 30 ADRs, many module docs, multiple risk registers, and
several daily-driver review layers.

The critical question:

> Can a maintainer find the current truth in less than five minutes?

If not, the project has converted governance into archaeology. The right fix is
not deleting dated evidence. The right fix is stronger front doors, supersession
notes, and one source of truth per decision type.

### 3. Test count is high, but test count is not trust

3,377 collected tests and 441 acceptance tests are impressive. The recent work
to remove fake skips and reconnect tests to real paths is more important than
the count.

The critical question:

> Which tests would fail if the approval model silently changed?

If many tests only confirm the current bypass behavior, they preserve behavior
but not necessarily safety. For security-sensitive flows, "existing behavior"
must be challenged against the product contract, not merely protected.

### 4. Optional dependency policy is not fully mature yet

The zero-dependency core is real and strategically valuable. The optional extras
story is less clean. `google-adk` brings a large transitive surface. The security
workflow now scans the base editable install, which is correct for core package
health. But optional extras still need their own documented audit cadence.

The critical question:

> Does "zero forced runtime dependency" accidentally become "optional dependencies
> are less governed"?

It must not. Optional dependencies are not harmless just because they are
optional; they become real attack surface in any deployment that enables them.

### 5. ADR implementation status can become a comfort blanket

ADR-0011 is described as accepted and implemented, but a second
`ApprovalManager` class remains under `runner/_approval_manager.py`. This does
not automatically mean the ADR failed; the runner-local class may be a workflow
helper rather than the same authority object. Still, the duplicate name is a
review hazard.

The critical question:

> Can two classes with the same security-adjacent name exist without future
> agents patching the wrong one?

For Phase 0, that answer should be no unless the helper is renamed or explicitly
documented as non-authoritative.

### 6. Velocity is now a risk multiplier

The review's velocity warning is valid. At this project age, high velocity has
already produced both impressive assets and duplicated authority paths.

The critical question:

> Are we measuring progress by shipped trust guarantees, or by artifact growth?

The next month should reduce the number of places future maintainers must look,
not increase it.

## Traceability

| Acceptance Criteria | Artifact Evidence | Test Evidence | Status |
| --- | --- | --- | --- |
| Project-state claims are fact-checked | `project-state-cross-review-fact-check-2026-06-04.md` | Repo commands listed in the fact-check doc | Done |
| Approval bypass is challenged | `approval_manager.py` bypass behavior documented here | `tests/test_policy.py::test_prompt_mode_with_allow_all_destructive_passes` | Active risk |
| Duplicate authority paths are called out | `approval_manager.py`, `runner/_approval_manager.py` | Indirect coverage only | Active risk |
| Docs sprawl is treated as a product risk | This document and existing governance docs | Docs consistency validation | Active risk |
| Optional dependency audit scope is explicit | Security workflow behavior discussed here | `pip-audit` workflow still needs CI confirmation | Partial |

## Required Fixes

1. Gate `allow_all_destructive` behind `PermissionMode.DANGER_FULL_ACCESS`, or
   rename it into an explicit emergency flag with typed confirmation and audit.
2. Rename or remove `runner/_approval_manager.py::ApprovalManager`, or document
   why it is not the canonical approval authority.
3. Turn the six proposed ADRs into owned roadmap rows with one of:
   `Accept`, `Reject`, `Supersede`, or `Archive`.
4. Create a docs front-door that distinguishes:
   current truth, historical evidence, risk register, roadmap, and execution
   tickets.
5. Add an optional-extra audit lane for heavy managed runtimes.

## Decision

Request changes for Phase 0 exit.

The project is on track, but the pasted review is slightly too generous in
calling the core harness solid without qualifying active approval-boundary and
status-truth risks.

## Residual Risks

- Some risk scores remain subjective until a scored security/UX rubric exists.
- Full coverage data was not regenerated in this review; coverage omit analysis
  is based on `pyproject.toml`, not coverage XML.
- Competitor positioning was not refreshed from external sources in this pass.
- This document records critique; it does not itself fix the underlying code.
