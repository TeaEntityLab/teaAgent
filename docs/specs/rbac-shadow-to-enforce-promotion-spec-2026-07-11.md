# H4 Policy/RBAC Shadow-to-Enforce Promotion Spec

> **Claim class:** Forward-looking specification (planned/held work — NOT current truth).
>
> **Status:** Preparation artifact for held item.
>
> **Date:** 2026-07-11
>
> **Trigger:** Owner request 2026-07-11 — forward-spec held/external roadmap items
> so future execution has pinned contracts and executable holds.
>
> **Scheduling gate (DR-006):** `governance-gap` — RBAC enforce flip is **Hold
> until owner demand signal** per `docs/backlog-priority.md` (Open items —
> provenance) and ADR-0031 expiry review 2026-09-12
> (`docs/adr/0031-shadow-mode-exit-criteria.md`).
>
> **Owns:** The future contract + acceptance criteria for promoting H4
> policy/RBAC governance from shadow to enforce.
>
> **Does not own:** Current-truth status (`docs/roadmap-status.md`), the hold
> decision itself, ADR statuses.
>
> **Review trigger:** Owner demand signal for enforcement, or the ADR-0031
> expiry review on 2026-09-12 (whichever first).

## 1. Current verified state (2026-07-11, HEAD)

Two H4 governance surfaces exist, wired through
`teaagent/governance/h4_integration.py`. **They are asymmetric, and the
asymmetry is the load-bearing fact of this spec:**

| Surface | Entry point | Wired at | Shadow behavior | Enforce behavior today |
| --- | --- | --- | --- | --- |
| Approval policy | `evaluate_approval_policy_shadow()` (`h4_integration.py:72-120`) | `teaagent/runner/_approval_manager.py:83-88` | Records receipt, returns `True` | **Identical to shadow.** Docstring says "Never blocks" (`:82`); returns `True` unconditionally (`:120`); `enforced=False` hardcoded (`:117`). `TEAAGENT_H4_POLICY_MODE=enforce` changes only the `mode` label in the audit event. |
| Subagent-launch RBAC | `check_subagent_launch_rbac()` (`h4_integration.py:123-166`) | `teaagent/subagents/_manager.py:278-285` | Records receipt, returns `(True, reason)` | **Implemented.** `mode == ENFORCE and not allowed` → returns `(False, reason)` (`h4_integration.py:164-166`); audit `enforced` flag set accordingly (`:161`). |

Mode resolution (`h4_integration.py:28-40`):

- `policy_governance_mode()` reads `TEAAGENT_H4_POLICY_MODE`; default `SHADOW`.
- `rbac_governance_mode()` reads `TEAAGENT_H4_RBAC_MODE`; default `SHADOW`.
- Values are `strip().lower()`-normalized; anything outside
  `{shadow, enforce}` silently falls back to the default (`:28-32`).

Shadow receipt contract (`record_h4_shadow_event`, `h4_integration.py:47-69`):
audit event type `h4_governance_shadow` with payload keys
`{surface, mode, allowed, enforced, reason, context, details}`. This event is
the **only** data source for the ADR-0031 exit-criterion analysis (§3.1), so
its schema is frozen by test (§4).

Existing coverage: `tests/test_h4_shadow_wiring.py` proves shadow receipts are
recorded and that RBAC enforce mode denies an under-privileged assignee.

## 2. The hold and its gate

- ADR-0031 (Proposed, 2026-06-12): five exit criteria, expiry review
  **2026-09-12**. On expiry: promote, extend with evidence, or revert wiring.
- DR-006 / `docs/backlog-priority.md`: `governance-gap` classification, **Hold
  until owner demand signal**. No agent may flip the default.
- `docs/work-log/roadmap-verification-2026-07-01.md` §Held/external repeats the
  hold.

Nothing in this spec changes the hold. Everything here is preparation so the
promotion, when demanded, is a config flip plus a checklist — not a design
session.

## 3. Future contract

### 3.1 Exit-criterion evidence procedures (ADR-0031 §Exit Criteria, made concrete)

1. **30-day zero-false-positive window.** Input: audit JSONL events with
   `event_type == 'h4_governance_shadow'`. Analysis contract:
   - Group by `surface`.
   - A **false positive** is an event with `allowed == false` whose `reason`
     the owner marks as wrong (the action should have been allowed). Owner
     adjudication is recorded as a dated table in a work-log file; agents may
     prepare the candidate list, never the verdicts.
   - Candidate extraction (deterministic, offline): implemented as
     `teaagent/governance/h4_evidence.py` (`build_h4_evidence_report` /
     `extract_denial_candidates`) with the CLI
     `scripts/prepare_h4_evidence.py`. It filters audit records for
     `event_type == 'h4_governance_shadow' and payload['allowed'] is False`,
     emitting `{ts, surface, mode, reason, context.action,
     context.tool_name | context.subagent, assignee, run_id, event_id}` plus
     per-surface weekly coverage and empty-week gaps. Every candidate carries
     `owner_verdict=None` — the tool prepares the list, the owner records the
     verdicts in the work-log table.
     The extractor accepts persisted nested audit records and in-memory flat
     captures only when the full frozen analysis key-set is present; malformed
     H4 receipts or unknown surfaces are counted in `skipped_malformed`, not
     silently turned into coverage. Date-only `--until` bounds include the full
     civil day, and inverted windows are rejected as operator error.
   - Pass condition per surface: zero owner-confirmed false positives across a
     window containing ≥ 1 real run per week.
2. **Coverage completeness.** Every enabled policy in
   `.teaagent/policies/*.json` and every role in the RBAC store has at least
   one test exercising its allow AND deny sides. Evidence: extend
   `docs/architecture/claim-to-test-traceability-matrix.md` with a policy/RBAC
   section; the matrix row count must equal the enabled-policy count.
3. **Performance.** Benchmark `PolicyEngine.evaluate_with_explanation` on a
   store with 25 policies: median < 50 ms (ADR-0031 SLO). Harness:
   `pytest-benchmark` (already a dev dependency, `pyproject.toml:118`).
4. **Human sign-off.** PR titled "Approve shadow→enforce promotion" that flips
   the default and cites this spec; owner review required (positioning-level
   decision).
5. **Rollback plan.** §3.4 below is the runbook; validated by running its steps
   in a scratch workspace before the promotion PR merges.

### 3.2 Promotion mechanics (config flip, per harness-first §6.2)

Target state: mode is configuration, not code.

- **Config surface (new):** `h4_policy_mode` / `h4_rbac_mode` keys resolved by
  the standard workspace-defaults provenance chain
  (`resolve_config_provenance()` in
  `teaagent/ergonomics/workspace_defaults.py`), with env vars
  `TEAAGENT_H4_POLICY_MODE` / `TEAAGENT_H4_RBAC_MODE` keeping today's
  precedence (env over config file). `teaagent doctor config` must show the
  effective mode and its source — this is the V8-lesson requirement: the flip
  must be *visible*.
- **Default flip:** change the `default=` argument in
  `policy_governance_mode()` / `rbac_governance_mode()`
  (`h4_integration.py:35-40`) from `SHADOW` to config-resolved value; the
  promotion PR flips the shipped default to `ENFORCE` per surface.
- **Policy-surface enforcement (the real gap):** `evaluate_approval_policy_shadow`
  gains an enforce branch mirroring the RBAC pattern: on
  `mode == ENFORCE and not allowed`, return `False` (or raise the runner's
  denial with a `DenialReasonCode`), set `enforced=True` in the receipt, and
  rename the function (`evaluate_approval_policy` — the `_shadow` suffix
  becomes a lie the moment it can block). Caller
  `runner/_approval_manager.py:83-88` must translate `False` into the standard
  approval-denied path so denial UX is identical to existing approval denials.
- **Mode-change audit:** any run where the effective mode differs from the
  previous run's mode emits an audit event `h4_mode_changed`
  `{surface, old_mode, new_mode, source}` so the 30-day window analysis can
  segment by mode era.

### 3.3 Promotion order

Promote **RBAC first, policy second** (RBAC enforce code already exists and
has test history; policy enforcement is new code). Each surface promotes
independently: a false positive on one surface must not roll back the other.

### 3.4 Rollback runbook (criterion 5)

1. Set `TEAAGENT_H4_POLICY_MODE=shadow` (env wins over config — verified
   precedence) or edit workspace config; run `teaagent doctor config` and
   confirm effective mode + source.
2. Re-run the denied action; confirm it proceeds and the receipt shows
   `mode=shadow, enforced=false`.
3. File the false-positive record (§3.1.1 table) — rollback without a recorded
   cause is prohibited.
4. No data migration is needed in either direction (mode only changes gating,
   never storage) — this property is part of the contract and must stay true.

## 4. Executable specification

Tests live in `tests/test_h4_promotion_spec.py` (this spec's companion).

| Contract clause | Test | Kind |
| --- | --- | --- |
| Default mode is SHADOW on both surfaces | `test_policy_and_rbac_modes_default_to_shadow` | guards hold today |
| Invalid mode value falls back to SHADOW (fail-safe parse) | `test_invalid_mode_value_falls_back_to_shadow` | guards hold today |
| Mode parse normalizes case/whitespace | `test_mode_parsing_normalizes_case_and_whitespace` | guards hold today |
| Policy enforce is advisory-only **today** (asymmetry pin) | `test_policy_enforce_mode_is_currently_advisory_only` | guards hold today — **failure means the policy surface began enforcing; execute §5 and update roadmap-status H4** |
| Shadow receipt schema = evidence-analysis input | `test_shadow_receipt_payload_schema` | guards hold today |
| Shadow never blocks even on deny | `test_shadow_mode_never_blocks_denied_action` | guards hold today |
| Enforce return value ↔ receipt consistency (RBAC) | `test_rbac_enforce_result_consistent_with_receipt` | guards hold today, survives promotion |
| Denial-candidate extraction is deterministic and owner-verdict-null | `tests/test_h4_evidence.py` | prepares ADR-0031 exit-criterion-1 evidence; does not change the hold |

Existing (not duplicated here): shadow receipts recorded and RBAC
enforce-denies — `tests/test_h4_shadow_wiring.py`.

## 5. Promotion-day checklist

1. Owner demand signal recorded (friction-log entry or dated owner-override) —
   DR-006 T1 gate satisfied.
2. §3.1 evidence package assembled; five criteria green.
3. Implement policy-surface enforce branch + rename (§3.2); RBAC needs no code.
4. Add enforce-mode acceptance test (denial UX parity with approval denials).
5. Flip default(s); update `teaagent doctor config` output test.
6. Update `docs/roadmap-status.md` H4 row (shadow → enforce), ADR-0031 status
   (Proposed → Accepted, expiry achieved), and retire the asymmetry pin test
   `test_policy_enforce_mode_is_currently_advisory_only` **in the same commit**
   (deletion policy: covered by the new enforce acceptance test + traceability
   update, per harness-first §4.2).
7. Run `python3 scripts/validate_docs_consistency.py` and the acceptance tier.

## 6. Risks and open questions

- **False-positive definition is owner-subjective.** Mitigated by the dated
  adjudication table; an agent must never auto-classify.
- **Split promotion (RBAC before policy)** creates a window where receipts mix
  `enforced=true` and `enforced=false` across surfaces. The §3.1.1 analysis
  groups by surface, so the window is analyzable; the cockpit should surface
  per-surface mode.
- **Interceptor ordering** (harness-first §8 Q3): fixed order today; revisit
  only on evidence. Not a promotion blocker.
- **`_shadow` naming debt:** the rename in §3.2 is mandatory at promotion;
  keeping the name while it can block would be a receipt-comprehension bug.
- Open: should enforce-mode policy denial produce `run_pending_approval`
  (recoverable) instead of hard denial for non-destructive tools? Decide at
  promotion with owner; default to hard denial (boring, matches RBAC).
