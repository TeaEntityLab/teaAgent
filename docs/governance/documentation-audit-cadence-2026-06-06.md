# Documentation Audit Cadence
# 2026-06-06

> **Owns:** When documentation governance checks must run and what evidence to keep.
>
> **Review trigger:** Release gates, roadmap changes, or trust-sensitive code changes.

## Triggers

Run the full docs gate whenever any of the following happen:

| Trigger | Minimum commands | Evidence artifact |
| --- | --- | --- |
| Minor release or tag | `scripts/verify_docs.sh` | `docs/generated/release-docs-evidence.md` |
| Roadmap horizon/milestone status change | `python3 scripts/validate_docs_consistency.py` | Updated `docs/roadmap-status.md` review date |
| Trust-sensitive code change (approval, audit, sandbox, subagents) | `scripts/verify_docs.sh` + targeted pytest | PR notes + run receipt if applicable |
| Competitor survey refresh | `scripts/refresh_competitive_docs.py` | Survey `Last reviewed` date |
| New current-truth doc or front-door link | `scripts/verify_docs.sh` | `docs/INDEX.md` review date |
| OKF catalog source change | `scripts/verify_docs.sh` | Regenerated `knowledge/teaagent-*` bundles |

## Monthly baseline

Follow the [Monthly Docs Drift Review](../release-checklist.md#monthly-docs-drift-review-p2-b)
in the release checklist. The monthly pass must include:

1. `python3 scripts/report_docs_aging.py --check`
2. `python3 scripts/generate_docs_inventory.py --check`
3. `python3 scripts/generate_command_snippet_inventory.py --check`
4. `python3 scripts/build_release_docs_evidence_bundle.py --check`

## Quarterly baseline

Follow the [Quarterly Refresh Process](../release-checklist.md#quarterly-refresh-process-p2-c)
in the release checklist. A quarterly pass is not complete until the monthly
baseline above has run in the same month.

## One-command local gate

```bash
./scripts/verify_docs.sh
```

This runs inventory, aging, release-docs evidence, OKF catalog stale checks,
and consistency validators.

## Escalation

If any generated artifact is stale, regenerate rather than hand-editing:

```bash
python3 scripts/generate_docs_inventory.py
python3 scripts/report_docs_aging.py
python3 scripts/generate_command_snippet_inventory.py
python3 scripts/build_release_docs_evidence_bundle.py --skip-gates
python3 scripts/generate_okf_docs_bundle.py
python3 scripts/generate_okf_docs_bundle.py --manifest docs/okf-catalog-reference.yaml --output knowledge/teaagent-reference
python3 scripts/generate_okf_docs_bundle.py --manifest docs/okf-catalog-history.yaml --output knowledge/teaagent-history
python3 scripts/validate_docs_consistency.py
```

Human review is required before marking roadmap claim-hygiene or release-readiness
docs as Fixed when validators newly start failing.
