# Release Checklist

**Last reviewed:** 2026-06-07

> **Review trigger:** Release gates, survey cadence, or validation workflow changes.

Use before tagging a minor release or merging a federation/protocol ADR.

Periodic documentation audit cadence:
[Documentation Audit Cadence](governance/documentation-audit-cadence-2026-06-06.md)
(via `./scripts/verify_docs.sh`).

## Competitive landscape hygiene

1. Re-run [scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md) against DeepWiki/upstream signals (Codex, Claude Code, OpenCode, OpenHands, Aider, LangGraph, CrewAI).
2. Update `Last reviewed: **YYYY-MM-DD**` in the survey artifact.
3. Sync [docs/backlog-priority.md](backlog-priority.md) and [docs/use-cases.md](use-cases.md) differentiator tables.
4. Check generated coverage artifacts without mutating tracked files:
   - `python3 scripts/refresh_competitive_docs.py --check`
5. Regenerate coverage artifacts only when the check reports drift:
   - `python3 scripts/refresh_competitive_docs.py`
   - Or step-by-step: `build_acceptance_status.py`, `build_use_case_matrix.py`, `render_use_case_dashboard.py`
6. `refresh_competitive_docs.py` runs `validate_docs_consistency.py` at the end (must pass).

## Provider and docs drift

- Confirm README/USAGE/architecture provider counts match `PROVIDER_CONFIGS`.
- Run `python3 -m pytest tests/acceptance/test_provider_matrix_consistency_flow.py -q`.

## Acceptance smoke

- `python3 -m pytest tests/acceptance --collect-only -q` matches `docs/acceptance.md` status count.
- Spot-check new acceptance flows referenced in the survey backlog table.

## Monthly Docs Drift Review (P2-B)

Run monthly (or after any major doc batch) to keep the documentation corpus
navigable and truthful. Evidence docs should either point to current truth or
remain clearly marked as archival.

### Freshness check

1. **Current-truth docs**: Verify `docs/daily-driver-current-status.md`,
   `docs/roadmap-status.md`, `docs/acceptance.md`, and `docs/INDEX.md` have
   been updated within their freshness windows (see
   [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md)).
2. **Last reviewed dates**: Run `python3 scripts/detect_stale_plans.py --check-review-dates`
   and fix any docs with stale review markers.
3. **Provider count coherence**: Re-run provider consistency check:
   ```bash
   python3 scripts/validate_docs_consistency.py
   ```

### Supersession hygiene

4. **Stale plan detection**: Run `python3 scripts/detect_stale_plans.py` and
   check for plans older than 90 days without updates. For each:
   - If the plan work is complete → add a supersession note pointing to current
     status or closure evidence.
   - If the plan work is superseded by a newer plan → add a supersession note
     pointing to the newer plan.
   - If the plan remains active but unchanged → update its `Last updated` date
     or add a note explaining why it's still current.
5. **Supersession note audit**: Spot-check 3–5 superseded docs (look for
   `> Supersession note` prefix) and verify:
   - The note date is within the last 90 days.
   - The linked `<new-source>` is accessible and still current.
   - The stated `<State>` is still accurate.
6. **Contradiction scan**: For each current-truth doc, grep for claims that
   might contradict older evidence docs:
   ```bash
   grep -rl "0 failed\|0 failures\|all passing\|full suite" docs/ | head -20
   ```
   If a current-truth doc claims zero failures, verify the evidence is dated
   and reproducible.

### Index and linkage health

7. **INDEX.md completeness**: Verify any new major plan, review, or strategy
   doc added since the last review has an entry in `docs/INDEX.md` or is
   explicitly marked as archival evidence.
8. **Orphaned docs**: Check for new `.md` files in `docs/plans/`,
   `docs/analysis/`, `docs/reviews/`, or `docs/strategy/` that are not linked
   from any index or front door:
   ```bash
   find docs/plans docs/analysis docs/reviews docs/strategy -name '*.md' -newer docs/INDEX.md
   ```
9. **Link rot**: Spot-check 5 cross-document links for validity (no 404
   within the repo).

### Guarded claims

10. **Guarded claims registry**: Run the guarded-claims check:
    ```bash
    python3 scripts/validate_docs_consistency.py
    ```
    Fix any guarded-claim drift errors (stale failure prose in current-truth docs).
11. **Daily-driver status accuracy**: Read `docs/daily-driver-current-status.md`
    "Solid today" and "Known issues" sections. Verify each claim against the
    most recent 5 commits. Remove or update any claim that no longer holds.

### Completion evidence

After each monthly review, update the `Last reviewed` date at the top of this
file and regenerate the release documentation evidence bundle:

```bash
python3 scripts/build_release_docs_evidence_bundle.py
```

See [docs/generated/release-docs-evidence.md](generated/release-docs-evidence.md)
for the dated bundle (commands, commit, docs freshness, roadmap excerpt, and
open residual risks). JSON mirror:
[docs/generated/release-docs-evidence.json](generated/release-docs-evidence.json).

## Guarded Claims

Release notes and public-facing docs must not claim capabilities without
explicit test or artifact evidence.

| Prohibited claim type | Required evidence | Example |
|---|---|---|
| "Enterprise-ready" or "Enterprise grade" | Compliance gate acceptance, audit-level tiers test, documented RBAC test | Not "TeaAgent is enterprise-ready" without linked acceptance test |
| "Remote-ready" or "Works remotely" | Remote agent isolation tests, gateway task intake acceptance, cloud lifecycle tests | Not "Use TeaAgent remotely" without `test_background_full_lifecycle_flow.py` |
| "Sandbox-complete" or "Fully sandboxed" | Docker/container isolation tests, path-escape tests, shell allowlist property tests | Not "Fully sandboxed execution" without `test_docker_isolation_*` |
| "Production-hardened" or "Battle-tested" | Long-session eval, scope-creep benchmark, 7-day stress test results | Not "Battle-tested for production" without linked benchmark report |

Before any release note or public-facing doc update, check each claim against
the evidence column. If the evidence does not exist at the claimed level, the
claim must be removed or downgraded (e.g., "Beta" or "Experimental").

## Quarterly Refresh Process (P2-C)

Competitor landscape evolves continuously. A quarterly refresh ensures the
documentation corpus does not silently stale between release cycles.

### Refresh cadence

| Artifact | Refresh interval | Owner |
|---|---|---|
| [docs/release-checklist.md](release-checklist.md) | Quarterly (or per minor release) | Release owner |
| [docs/release-evidence.json](release-evidence.json) | Per release | Release owner |
| [docs/maturity-matrix.md](maturity-matrix.md) | Quarterly | Strategy owner |
| [docs/backlog-priority.md](backlog-priority.md) | Quarterly (sync with survey) | Strategy owner |
| [docs/use-case-matrix.md](use-case-matrix.md) | Quarterly (sync with survey) | Strategy owner |
| [docs/use-cases.md](use-cases.md) | Quarterly | Strategy owner |
| [docs/model-capability-matrix.md](model-capability-matrix.md) | Per provider update | Provider owner |
| [docs/roadmap-status.md](roadmap-status.md) | Monthly + per release | Product owner |
| Release notes (`CHANGELOG.md` / GitHub Releases) | Per release | Release owner |
| [docs/INDEX.md](INDEX.md) | After any new doc front-door addition | Documentation owner |
| [Monthly docs drift review](#monthly-docs-drift-review-p2-b) | Monthly | Documentation owner |

### Quarterly refresh checklist

0. **Monthly drift review** — Ensure the [monthly docs drift review](#monthly-docs-drift-review-p2-b)
   has been completed for the current month. The quarterly refresh builds on the
   monthly baseline.
1. **Review dates** — Every artifact above must have its `Last reviewed` /
   `Last updated` field bumped to the current quarter. Run:
   ```bash
   python3 scripts/detect_stale_plans.py --check-review-dates
   ```
2. **Competitor signal survey** — Follow [Quarterly Competitor Refresh Process](processes/quarterly-competitor-refresh.md)
   and run `python3 scripts/refresh_competitive_docs.py`; update `Last reviewed` date.
3. **Maturity matrix** — Re-assess every row in `docs/maturity-matrix.md`:
   - Experimental → Beta transitions that happened
   - Beta → Stable transitions that qualified
   - Remove rows whose features were removed or superseded
4. **Release notes** — Convert any unreleased `CHANGELOG.md` entries to dated
   release section; create GitHub Release with full changelog body.
5. **Docs consistency** — Run `python3 scripts/validate_docs_consistency.py`
   and fix all errors before the quarterly refresh is considered complete.
6. **Stale plan review** — Run `python3 scripts/detect_stale_plans.py` and
   either archive or add supersession notes to plans older than 90 days
   without updates.

### Competitor signal → acceptance gap workflow

When the quarterly survey reveals a competitor capability gap, follow the
[signal-to-acceptance-gap process](processes/signal-to-acceptance-gap.md):

1. Record the signal with date, source, and confidence.
2. Map signal to an existing or new use-case row in `docs/use-cases.md`.
3. If the gap is P0/P1, file a ticket with acceptance criteria.
4. Add a row to `docs/use-case-matrix.md` with `Covered = no` and a
   linked backlog action.

### Refresh evidence

After each quarterly refresh, record in `docs/release-evidence.json`:
- Date of refresh
- Commit at refresh time
- Which artifacts were updated
- Any gaps deferred with rationale
