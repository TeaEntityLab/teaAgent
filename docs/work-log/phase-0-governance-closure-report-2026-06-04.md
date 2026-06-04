# Phase 0 Governance Closure Report
# 2026-06-04

## Purpose

This report records the continuation work after the Phase 0 trust-boundary
implementation pass. It focuses on documentation-backed governance items that
were still open after approval, memory, TUI, and chat fixes landed.

## What Changed

| Area | Previous state | Current state |
| --- | --- | --- |
| Coverage omit governance | Ledger existed but lacked smoke-test candidates and validator enforcement. | Ledger now lists all 16 omit patterns with owner, reason, risk, return milestone, and smoke-test candidate. Validator checks ledger vs `pyproject.toml`. |
| Dependency audit scope | Security workflow used unscoped environment audit and lockfile audit, which could mix base, dev, and optional findings. | Workflow separates base, dev/lockfile, and optional-extra audit lanes. Base PR gate uses an exported base requirements surface. |
| ADR proposed-state cleanup | Some review docs still said six ADRs were Proposed. | ADR index shows those ADRs as closed or accepted; ADR 0025 now reflects implemented REPL/TUI controller unification. |
| Security policy entry points | Governance docs still described a narrower two-scan audit model. | `SECURITY.md`, governance standards, compliance checklist, release process, and README now point to segmented audit policy. |

## Why This Matters

The core risk was not missing prose. The risk was state drift:

- A CI failure could be interpreted as "the base package is vulnerable" when it
  actually came from an optional extra.
- A coverage omit could be treated as harmless without any owner or return
  path.
- A dated ADR-status claim could keep future agents planning work that had
  already been closed.

These are daily-driver risks because users and agents make operational choices
from docs. If docs cannot distinguish base risk, optional risk, historical
evidence, and current truth, the project feels less stable than its code.

## Completed Work Items

| Work item | Closure evidence |
| --- | --- |
| P0-TR-005 / DOW-016 | `docs/governance/coverage-omit-ledger.md`; `validate_coverage_omit_ledger()`; docs tests. |
| P0-TR-006 / DOW-017 | `.github/workflows/security.yml`; `docs/security/dependency-audit-policy.md`; `validate_dependency_audit_policy()`. |
| P0-TR-007 / DOW-015 | `docs/adr/README.md`; `docs/adr/0025-chat-session-controller-unification.md`. |
| P1-TR-012 | `docs/security/dependency-audit-scope-refresh-2026-06-04.md`. |

## Remaining Priority Work

| Priority | Work | Why it remains |
| --- | --- | --- |
| P0 | Full-access entry ceremony and audit event | `danger-full-access` is necessary but still needs stronger operator evidence. |
| P0 | Auto-mode approval policy restoration evidence | Broad mode should not leak past the intended run lifetime. |
| P1 | Convert omit smoke candidates into direct tests | The ledger reduces blindness; tests reduce risk. |
| P1 | Optional-extra remediation decisions by extra | Segmentation clarifies risk but does not patch upstream CVEs. |
| P1 | Guarded-claim registry | Current validators guard specific claims; a general volatile-claim registry remains open. |
| P1 | Module risk upward-link audit | Module risk files still need central owner/ticket links for High/Critical rows. |

## Cost-Effectiveness Reflection

Highest ROI completed:

- Removing unscoped `pip-audit --skip-editable` from CI. It directly addresses
  the observed failure mode and prevents base/optional confusion.
- Adding coverage omit validation. It turns an easy-to-forget ledger into a
  maintenance contract.
- Correcting ADR 0025 and ADR index state. It prevents redundant planning around
  already-landed TUI controller work.

Highest ROI next:

- Add a broad-mode ceremony audit event before expanding agent-mode autonomy.
- Add direct smoke coverage for `tls_server`, `wasm_runtime`, control-plane CLI,
  and TUI journeys.
- Decide the `managed-google-adk` optional-extra vulnerability story before
  release packaging.

## Final Question For Future Reviewers

Can a maintainer explain, in one minute, which risk belongs to the base package,
which belongs to an optional extra, which is historical evidence, and which is
current release-blocking truth?

If not, the next change should improve the front doors before adding new
surface area.
