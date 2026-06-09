<!-- Copy to governance/specs/<ticket>.md and fill. Delete this comment. Template = framework T1. -->
# SPEC — <ticket / feature name>

`SPEC_VERSION = YYYY-MM-DD-<slug>-vN`
**Risk level:** L1 / L2 / **L3**   ·   **Status:** draft / gated / implemented

## Goal / Non-goals
- **Goal:** _single, verifiable sentence._
- **Non-goals:** _what this explicitly does not do._

## Inputs / Outputs (with schema)
- **Inputs:** _types / schema._
- **Outputs:** _types / schema._

## Acceptance Criteria (each testable)
- [ ] AC-1: …
- [ ] AC-2: …

## Edge Cases / Failure Conditions
- …

## Security / Privacy Constraints
- …

## Allowed / Forbidden / Requires Human Review  <!-- CV-8; required for L3 -->
- **Allowed:** …
- **Forbidden:** …
- **Requires Human Review:** …

## Real-world Assumptions  <!-- CV-4: traffic / latency / data volume / regulation / security edges -->
- …

## Test Plan
- _link to `test-matrices/<ticket>.md`._

---

## Spec Quality Gate (must pass before implementation)
- [ ] Goal single & verifiable; Non-goals explicit
- [ ] Inputs/Outputs have schema; every AC is testable
- [ ] P0 risk classified; forbidden behavior listed
- [ ] Rollback condition present; human-review trigger present
- [ ] No mutually contradictory conditions
- [ ] Real-world assumptions stated (traffic/latency/data volume/regulation/security edges)
