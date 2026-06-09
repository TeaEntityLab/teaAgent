<!-- Copy to governance/test-matrices/<ticket>.md and fill. Delete this comment. Template = framework T2. -->
# TEST MATRIX — <ticket / feature name>

> Priority guide: **P0** = security / data / money / permission (absolute coverage required).
> **P1** = core logic. **P2** = important edge cases. **P3** = nice-to-have.
> Test types: unit · integration · schema · security · scenario · adversarial.

| Case | Input | Expected | Type | Priority | Covered by |
|---|---|---|---|---|---|
| <happy path> | … | … | integration | P0 | `tests/...::test_...` |
| <wrong input> | … | <safe error> | security | P0 | _gap?_ |
| <boundary> | "" / max / unicode | <validation> | unit | P1 | … |

## Gap analysis
> Diff the rows above against the actual test files. List every P0 row with a verdict.

| Case | Priority | Verdict (covered / **GAP**) | Action |
|---|---|---|---|
| … | P0 | … | … |

## Adversarial checklist (L3)
- [ ] permission bypass / escalation
- [ ] tampered input → must be rejected, not silently accepted
- [ ] race condition / concurrency (assert post-state, not just return value — T7)
- [ ] empty / oversized / unicode / null inputs
