# Cost State Taxonomy (WS3-004)

> **Status:** Current truth for run receipt and budget display labels.
> **Implementation:** `teaagent/cost_state.py`

## States

| State | Meaning | When used |
| --- | --- | --- |
| `estimated` | Token/heuristic projection before provider invoice | Default when `cost_cents > 0` and no provider usage event |
| `provider_reported` | Provider or adapter returned usage/cost fields | Audit events include `actual_cost_cents` or equivalent usage payload |
| `pending` | Cost not yet known; run still in flight | Active runs before first usage rollup |
| `unknown` | No cost signal yet under a capped budget | Zero cost with finite budget cap |
| `unlimited` | No budget cap configured | `budget_cap_cents is None` |
| `unavailable` | Legacy/invalid label fallback | Unrecognized external labels |

## Legacy mapping

Older UI strings used `actual` for finalized provider cost. New code maps `actual` → `provider_reported` via `normalize_cost_state()`.

## API

```python
from teaagent.cost_state import derive_cost_state

derive_cost_state(cost_cents=42, budget_cap_cents=500)  # -> estimated
derive_cost_state(cost_cents=42, budget_cap_cents=500, provider_reported=True)  # -> provider_reported
derive_cost_state(pending=True, budget_cap_cents=500)  # -> pending
```

## Verification

```bash
python3 -m pytest tests/test_cost_state_taxonomy.py -q
```
