# Quarterly Competitor Refresh Process (WS6-003)

> **Last reviewed:** 2026-06-06
> **Cadence:** Quarterly, or before any public positioning / comparison claim
> **Owner:** Strategy + documentation

Competitor products change quickly. Volatile facts (stars, pricing, model names,
feature flags) must be **source-dated** or **omitted**. This process keeps
TeaAgent's public comparisons honest and maintainable.

## Artifacts to refresh

| Artifact | Path | Action |
| --- | --- | --- |
| Signal survey | [competitor-signal-survey-YYYY-MM-DD.md](../analysis/competitor-signal-survey-2026-06-06.md) | New dated file; supersede prior survey |
| Self-comparison matrix | [competitor-self-comparison-matrix-YYYY-MM-DD.md](../analysis/competitor-self-comparison-matrix-2026-06-06.md) | Update rows from official docs only |
| Landscape / positioning | [competitive-landscape-and-positioning-*.md](../analysis/competitive-landscape-and-positioning-2026-06-06.md) | Revise anti-personas and gaps if needed |
| Release checklist | [release-checklist.md](../release-checklist.md) | Bump `Last reviewed` on quarterly section |
| When not to use | [when-not-to-use-teaagent.md](../guides/when-not-to-use-teaagent.md) | Confirm non-fit scenarios still accurate |

## Refresh checklist

1. **Pick review date** — Use ISO date in new survey filename (`YYYY-MM-DD`).
2. **Official sources only** — Product docs, help centers, release notes. No forum rumors without labeling as anecdotal.
3. **Timestamp volatile metrics** — GitHub stars, pricing tiers, model lists: include "as of DATE" or drop the metric.
4. **Run automation**:
   ```bash
   python3 scripts/refresh_competitive_docs.py
   python3 scripts/validate_docs_consistency.py
   python3 scripts/generate_docs_inventory.py
   ./scripts/verify_docs.sh
   ```
5. **Supersession notes** — Old surveys link forward; do not delete historical reasoning.
6. **Gap workflow** — New competitor capabilities → [signal-to-acceptance-gap.md](signal-to-acceptance-gap.md).
7. **Record evidence** — Update `docs/release-evidence.json` with refresh date and commit.

## Source rules

| Allowed | Avoid |
| --- | --- |
| Vendor documentation URLs checked on review date | Undated "X is better" claims |
| TeaAgent codebase + test references for our claims | Copying competitor marketing superlatives |
| Explicit "not refreshed since DATE" on stale rows | Implied parity without evidence |

## Current baseline (2026-06-06)

- Survey: [competitor-signal-survey-2026-06-06.md](../analysis/competitor-signal-survey-2026-06-06.md)
- Matrix: [competitor-self-comparison-matrix-2026-06-06.md](../analysis/competitor-self-comparison-matrix-2026-06-06.md)
- Process owner checklist in [release-checklist.md § Quarterly Refresh](../release-checklist.md#quarterly-refresh-process-p2-c)
