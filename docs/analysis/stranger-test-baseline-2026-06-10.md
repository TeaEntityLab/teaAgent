# Stranger Test Baseline — 2026-06-10

**Work item:** WDC-001  
**Method:** Ten-minute first-session concept inventory (maintainer simulation).

## Baseline concept count

| Scope | Count | Concepts |
| --- | ---: | --- |
| Happy path (target) | **3** | ask, approve, undo |
| Full first session (measured) | **9** | ask, approve, undo, receipt, budget, tenant, trust tier, envelope, cockpit |

## Reduction target

Ship WDC-002 progressive disclosure so strangers encounter **≤ 3** concepts on
the default happy path. Advanced nouns remain available behind explicit opt-in.

## Evidence

- `teaagent/governance/conversation_ux.py` — `CORE_ONBOARDING_CONCEPTS`
- `tests/acceptance/test_three_concept_onboarding_flow.py`
