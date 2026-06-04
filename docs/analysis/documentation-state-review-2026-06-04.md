# Documentation State Review
# 2026-06-04

## Purpose

This review records the current state of TeaAgent's Markdown corpus and turns
that state into concrete consolidation, governance, and UX recommendations. It
is written as a current evidence snapshot, not as a replacement for historical
audits.

The central question is:

> Can a daily user, maintainer, or future agent find the current truth quickly
> without being misled by an older but plausible document?

## Scope And Method

Reviewed:

- Repository Markdown inventory and directory shape.
- `cx overview docs --limit 120`.
- `cx symbols --kind heading --name '*Status*' --limit 120`.
- `cx symbols --kind heading --name '*Risk*' --limit 120`.
- `cx symbols --kind heading --name '*Roadmap*' --limit 120`.
- Current front doors: `docs/daily-driver-current-status.md`,
  `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`,
  `docs/plans/ticket-plans/index.md`, `docs/roadmap-status.md`,
  `docs/modules/INDEX.md`, and `docs/governance/README.md`.
- Current staged review package created on 2026-06-04.

Not reviewed:

- Every line of every Markdown file.
- Full external competitor refresh.
- Full link validation across all Markdown files.
- Runtime truth of every risk row in module docs.

## Inventory Snapshot

| Signal | Current value | Evidence |
| --- | ---: | --- |
| Tracked Markdown files | 456 | `git ls-files '*.md'` |
| Markdown files under `docs/` | 421 | `find docs -type f -name '*.md'` |
| `docs/analysis` files | 62 | `cx overview docs --limit 120` |
| `docs/plans` files | 43 | `cx overview docs --limit 120` |
| `docs/modules` files | 103 | `cx overview docs --limit 120` |
| `docs/governance` files | 15 | `cx overview docs --limit 120` |
| Status-heading hits | 60 | `cx symbols --kind heading --name '*Status*' --limit 120` |
| Risk-heading hits | 120 shown out of 133 | `cx symbols --kind heading --name '*Risk*' --limit 120` |
| Roadmap-heading hits | 23 | `cx symbols --kind heading --name '*Roadmap*' --limit 120` |
| Current collected tests | 3,379 | `/tmp/tea312/bin/python -m pytest --collect-only -q` |
| Current acceptance collection | 441 | `/tmp/tea312/bin/python -m pytest tests/acceptance --collect-only -q` and acceptance collection guard |

The counts differ from older docs because the corpus is growing quickly and
because different commands include different scopes. Future reports must name
the counting method.

## Findings

### DSR-001: The corpus is large but highly structured

State: Active.

The documentation tree is not random. It has recognizable families: user
guides, analysis, governance, plans, module docs, security, reliability, specs,
decisions, and operations. The problem is not lack of structure. The problem is
that structure has outgrown the reader's ability to infer current truth from
date alone.

Recommendation: preserve dated evidence, add stronger front doors, and avoid
mass merging historical reviews.

### DSR-002: Current-truth docs and evidence docs are not visually distinct enough

State: Active.

Files such as `daily-driver-current-status.md` are current truth. Files such as
dated audits and review packages are evidence snapshots. Both appear side by
side in search and indexes, which means a reader can easily treat old evidence
as a current instruction.

Recommendation: use `docs/INDEX.md` and supersession notes to mark current
truth surfaces clearly.

### DSR-003: `docs/acceptance.md` had a high-trust contradiction

State: Fixed in this documentation pass.

The headline correctly said `441 passed`, but the body still stated an older
full-suite failure result from 2026-06-03. This was dangerous because
`docs/acceptance.md` is guarded by tests, and a reader could reasonably assume
all status claims in that file were guarded.

Change made: the stale failure paragraph now separates acceptance collection
from the last recorded supported-interpreter full-suite evidence.

Follow-up: add a prose-claim guard for full-suite status phrases.

### DSR-004: The total-review package needed cleanup before becoming durable evidence

State: Fixed in this documentation pass.

The staged total-review package contained non-English labels and stray closing
tags from generation. It also mixed measured-baseline facts with current-HEAD
phrasing.

Change made: the package now uses English headings, removes stray tags, and
labels its `4695d46` full-suite evidence as a measured baseline while recording
the current documentation-pass inventory separately.

### DSR-005: `docs/modules/INDEX.md` was a useful generated map with stale status edges

State: Partially fixed.

The module index is valuable as a map, but its generated risk summary and old
"known P0/P1 bugs" section can mislead readers if treated as live closure
truth.

Change made: added a supersession note and replaced the stale bug list with
current front-door pointers.

Follow-up: regenerate the module index or split it into "module map" and
"module risk inventory" so generated historical risk rows do not masquerade as
current status.

### DSR-006: Status, risk, and roadmap claims are spread across many valid files

State: Active.

`cx` found 60 status-heading hits, 133 risk-heading hits, and 23 roadmap-heading
hits. This is not automatically bad: ADRs, module risks, FMEA, roadmap, and
ticket plans all need their own local views. It becomes bad when those local
views compete to answer the same current-truth question.

Recommendation: keep local views, but require upward links for P0/P1 risks and
one canonical source of truth for each status question.

### DSR-007: The current validators are necessary but insufficient

State: Active.

`validate_docs_consistency.py` and the acceptance-count guard catch important
drift, but they do not parse most prose status claims. The `acceptance.md`
contradiction proves the gap: a test can pass while a nearby paragraph is stale.

Recommendation: add a small guarded-claim registry for volatile facts such as
test counts, provider counts, dependency audit results, full-suite results, and
release claims.

### DSR-008: Roadmap status needs fresher connection to documentation work

State: Active.

`docs/roadmap-status.md` is canonical, but it was last updated before the June 4
documentation-state review. H0 claim and risk hygiene should explicitly include
documentation-current-truth work.

Recommendation: update H0 rows to link this documentation optimization package
and add a doc-vs-HEAD guard as a named roadmap item.

### DSR-009: More documentation is still useful, but only when it reduces future search

State: Active.

The user requested more plans, risks, surveys, and work items. That is useful
only if each new document either becomes a front door, records dated evidence,
or turns ambiguity into executable work.

Recommendation: every new doc must declare whether it is current truth,
evidence, plan, governance, or work log.

## Current Front-Door Model

| Reader question | Current front door | Needed improvement |
| --- | --- | --- |
| What should I use today? | `docs/daily-driver-current-status.md` | Keep short and current; avoid historical caveats. |
| What happened in the daily-driver review? | `docs/analysis/daily-driver-review-INDEX-2026-06-01.md` | Link newer total-review and documentation-state packages. |
| What is the current roadmap? | `docs/roadmap-status.md` | Add June 4 documentation work and H0 guard rows. |
| What should be implemented next? | `docs/plans/ticket-plans/index.md` | Link non-ticket documentation optimization tasks. |
| Which module owns a risk? | `docs/modules/INDEX.md` and module `risks.md` files | Regenerate or add stale-risk metadata. |
| What rules govern docs? | `docs/governance/README.md` | Add this operating model to the top-level governance list. |

## Recommended Consolidation

Do not merge:

- Dated reviews into a single mega-review.
- Module risks into a single central risk register.
- ADRs into roadmap rows.
- Competitor surveys into product principles.

Do merge or redirect:

- Competing current-status pages that answer the same question.
- Stale "known issue" lists into current-status pointers.
- Repeated ticket-order narratives into the ticket index.
- Long roadmap implementation steps into ticket links and exit evidence.

## Review Verdict

TeaAgent's documentation is a real project asset. It is also now large enough to
become a trust liability if current truth is not guarded. The immediate path is
not deletion. The path is:

1. Curated front doors.
2. Explicit claim classes.
3. Supersession notes.
4. Guarded volatile facts.
5. Work-item ledgers with acceptance criteria.
6. Regular re-anchoring after trust-sensitive code changes.
