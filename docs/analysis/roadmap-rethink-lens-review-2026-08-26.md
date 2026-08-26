# Roadmap Rethink — Parallel Lens Review 2026-08-26

> **Claim class:** Dated evidence snapshot. Not current truth.
> **Protocol:** Parallel Lens Review Packet (seven independent read-only lenses over
> `review-packet-roadmap-rethink-2026-08-26.md`; packet deleted after synthesis).
> **Scope:** Re-verdict roadmap state after EFX-001–003 implementation session
> (`87d1c61`→`39fd5a8`, unpushed ahead of origin at review time).

## Panel Consensus

- **Decision:** AGREE WITH CHANGES — five lenses AGREE, two AGREE WITH CHANGES,
  zero DISAGREE.
- **Use-case recommendation:** `adopt` the wording tightening below; `study` the
  deferred items; no `deploy`/`reproduce` actions authorized (live credentials
  remain gated).

## Required Wording Changes (all adopted same-day)

Adopted verbatim from OperatorUsability and StrategicSynthesis:

1. `docs/daily-driver-current-status.md` "Do not rely on yet": gate changed from
   "until acceptance-tier evidence exists" (vacuous once providerless acceptance
   landed) to "until live-credential dry-run proof exists".
2. `docs/roadmap-status.md`: Last-updated and Scheduling-Rule dates to
   2026-08-26; H4 Next Gate "EFX local closure" → "EFX live-proof closure" +
   ADR-0031 named; H4 Exit Evidence now states runtime guards landed on existing
   seams **with live-provider proof pending**.
3. `docs/backlog-priority.md`: gate dates to 2026-08-26; RBAC enforce flip row
   now names the fixed 2026-09-12 ADR-0031 calendar review (decision packet:
   promote/extend/revert) instead of open-ended owner-demand hold.
4. `docs/specs/held-roadmap-forward-spec-index-2026-07-11.md`: H4 policy/RBAC
   expiry cell annotated "(decision packet review)".

No horizon status changed. H0/H1 Complete; H2/H3/H6 On Hold; H4 On Hold;
H5 Blocked; EFX-FUTURE Held. Authority chain unchanged
(Harness-First > DR-006 > ADR-0032 > ADR-0042).

## Candidate Adoption Ledger

| ID | Candidate | Status | Evidence | Next action or trigger |
|---|---|---|---|---|
| L1 | Replace stale "acceptance-tier evidence" operator gate with "live-credential dry-run proof" gate | adopted | Providerless acceptance landed in `tests/acceptance/test_efx_durable_effect_flow.py` (669 guard); stale gate invited operators to re-enable live creds | Guarded by `test_durable_effect_review_candidate_adoption_state`; revisit if live dry-run lands |
| L2 | Qualify H4 Next Gate as "EFX live-proof closure" + name ADR-0031 review; clarify RBAC row as decision-packet review due 2026-09-12 | adopted | Runtime guards + providerless acceptance are local-only; "local closure" without qualification conflated guards with settlement | Guarded same test; next trigger is the 2026-09-12 ADR-0031 packet itself |
| L3 | Require `TEAAGENT_RISK_ACK` to cite an existing `docs/reviews/*-risk.md` (ProvenanceSecurity Q4) | adopted | Env-only acks leave no in-tree artifact — audit-provenance erosion ("normalization of deviance" objection); `39fd5a8` ack is unrecoverable from history | Enforced by `scripts/check_high_risk_paths.py` (`ref <report>: <reason>`); guarded by `tests/test_check_high_risk_paths.py` |

## Shared Findings

- All seven lenses verified `39fd5a8` reorder is behavior-neutral:
  `compute_scoped_payload_digest` is pure (`teaagent/policy.py:464-477`);
  session-approved path discarded the digest pre-reorder
  (`teaagent/approval/manager.py:151-153`).
- EvidenceAuditor reproduced the 669 count arithmetically (652 defs + 17
  parametrized) and confirmed count-guard parity mechanics.
- ReproducibilityEngineer root-caused the coordinator's `PYTHONPATH=scripts`
  quirk: `validate_docs_consistency.py` inserts `_REPO_ROOT/scripts` only inside
  `validate_test_quality()`; `--test-quality-mode off` paths skip that insert.
- ReproducibilityEngineer flagged legacy `test_github_integration_flow.py`
  ambient-token skips vs hermetic `patch.dict` in the new EFX flow (debt, not
  blocker); ssh-keygen-less hosts yield 666 passed + 3 skipped.
- ArchitectureLens: god-module exemptions are load-bearing (EFX correctness
  lives inside them); split deferred behind post-push verification gate;
  suggested eventual extractions (`_effect_sandwich.py`, `_grant_store.py`).
- ProvenanceSecurity: `TEAAGENT_RISK_ACK` compliant for the 2-line reorder
  within the active risk-review envelope; warned ack-without-artifact erodes
  audit provenance if used for substantive changes (Socratic Q4 proposes
  parent-report reference requirement).

## Disagreements / Residual Risks

- No lens disagreed on verdicts. Tension noted by ArchitectureLens (strongest
  objection): continued growth of exempt modules risks "thin harness" becoming
  cover for unbounded bloat — counter: extraction now would destabilize an
  unpushed HEAD with unverified full suite.
- Residual: fail-closed breadth for future/third-party tools depends on
  registration discipline or `_infer_annotations` routing [INFERENCE];
  full-suite sample failures untriaged; ambient-credential preflight warning
  absent (OperatorUsability finding 4).

## Evidence Actually Checked

- Lenses executed: file reads across `docs/current-truth` surfaces,
  `teaagent/{runner,approval,policy}`, both test files, `git show 39fd5a8`,
  `scripts/check_god_modules.py`, `scripts/check_high_risk_paths.py`,
  `.pre-commit-config.yaml`, pyproject pytest config.
- Coordinator executed: all commits' pre-commit gates green; 669-collection
  parity; docs gates; seven-lens fan-out and synthesis.
- Not executed: live providers, full suite triage, push/deploy.
