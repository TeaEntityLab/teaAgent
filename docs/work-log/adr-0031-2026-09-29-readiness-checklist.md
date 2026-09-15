# ADR-0031 2026-09-29 Close — Owner Readiness Checklist

> **Claim class:** Working document for the ADR-0031 expiry close. Not a
> scheduling authority. Does not flip H4 mode.
> **Trigger:** ADR-0031 shadow-to-enforce expiry review, 2026-09-29
> (extended 2026-09-15 conditioned on G1–G5 landing and re-dogfood).
> **Authority:** `docs/adr/0031-shadow-mode-exit-criteria.md`,
> `docs/plans/current-roadmap-execution-plan-2026-08-26.md` §6,
> `docs/specs/rbac-shadow-to-enforce-promotion-spec-2026-07-11.md`,
> `docs/work-log/dogfood-findings-2026-09-15.md`.
> **Owner surface:** The owner must complete and sign this checklist before
> the 2026-09-29 close; agents may prepare and update it but may not check
> the sign-off boxes. Delete or supersede this file at the close.

## Close this checklist no later than 2026-09-29

- [ ] 1. Final evidence window is selected. Window must end on or before
  2026-09-29 and contain at least one real run per week, or a documented gap.
- [ ] 2. Criterion 1 — 30-day shadow receipts:
  `prepare_h4_evidence.py --since <start> --until 2026-09-29` was run; all
  `h4_governance_shadow` denial candidates have owner verdicts (true/false
  positive). D1 verdict recorded.
- [ ] 3. Criterion 2 — coverage: `check_h4_coverage.py --matrix <matrix> --output <report.json>` reports `gaps: []`
  for enabled policies and roles.
- [ ] 4. Criterion 3 — performance: `benchmark_h4_policy.py --threshold-ms 50.0` reports median
  < 50 ms.
- [ ] 5. Criterion 4 — human sign-off: owner signed the ADR-0031 decision
  log (promote/extend/revert) and the D1 classification.
- [ ] 6. Criterion 5 — rollback: `verify_h4_rollback.py` dry-run succeeded;
  runbook reviewed.
- [ ] 7. G1–G5 safety-critical fixes are landed and re-dogfooded (per
  2026-09-15 extension condition).
- [ ] 8. Exactly one disposition is selected and recorded in
  `docs/adr/0031-shadow-mode-exit-criteria.md` plus a dated work-log:
  - **Promote:** all five criteria pass; open promotion PR per H4 promotion
    spec §5.
  - **Extend:** name every missing criterion, new expiry date, and evidence
    to collect; schedule dogfood session if C1 is the gap.
  - **Revert:** remove shadow wiring per a newly authored bounded plan (do
    not pre-build before the 2026-09-29 trigger).

## Verification

After the owner checks all boxes, run:

```bash
python3 scripts/build_h4_decision_packet.py \
  --audit-log "$AUDIT_LOG" \
  --since <start> \
  --until 2026-09-29 \
  --threshold-ms 50.0 \
  --output .teaagent/reviews/adr-0031/decision-packet-2026-09-29.json
python3 scripts/validate_docs_consistency.py
./scripts/verify_docs.sh
```
