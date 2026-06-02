# Risk Issue Roadmap Workflow
# 2026-06-02

This workflow turns scattered review findings into durable work without losing
history or inventing a new tracking style for each audit pass.

## Pipeline

Use this pipeline for new risks, issues, defeat scenarios, UX gaps, roadmap
ideas, and stability findings:

```text
Finding/Risk -> Issue row -> Ticket plan -> Roadmap item -> Verification evidence
             -> Status ledger update -> Archive or supersession note
```

Not every item needs every artifact. Small doc-only corrections may go straight
from finding to verification. P0/P1 risks should almost always reach a ticket or
roadmap row.

## Step 1: Capture the finding

Capture first in the narrowest useful place:

| Finding type | First capture location |
|--------------|------------------------|
| User-facing daily-driver defect | `docs/analysis/` dated review or active findings ledger |
| Security boundary risk | `docs/security/` risk register or threat model |
| Reliability failure mode | `docs/reliability/` FMEA or scorecard |
| Module-local risk | `docs/modules/<module>/risks.md` |
| Roadmap or product gap | `docs/plans/` or `docs/roadmap-status.md` |
| Decision or rejected alternative | `docs/adr/` or `docs/decisions/` |

Minimum capture fields:

- Stable ID.
- One-sentence statement.
- Evidence source.
- Impact.
- Current state from `document-state-model.md`.
- Recommended owner surface.
- Verification gap.

## Step 2: Create or update an issue row

An issue row is the bridge between research and execution. It should answer:

- Is this real today?
- Who would notice?
- Which surface owns it?
- What proof would close it?
- What happens if it is ignored?

Issue rows may live in a dated review, a risk register, a module `risks.md`, or
the active daily-driver ledger. P0/P1 issue rows must link to one of:

- A ticket plan.
- A roadmap row.
- A Human Review decision.
- A documented defer or reject rationale.

## Step 3: Promote to a ticket plan

Promote when the item is actionable within the repo.

Ticket plans should use the existing shape:

- Problem.
- Scope.
- Affected files or surfaces.
- Acceptance criteria.
- Verification.
- Risks.
- Dependencies.
- Human review gate.

Ticket plans belong in `docs/plans/ticket-plans/` unless a more specific plan
directory already owns the execution lane.

## Step 4: Attach to roadmap

Attach to `docs/roadmap-status.md` when the work affects a roadmap horizon,
release claim, adoption story, or cross-surface architecture.

Use this mapping:

| Work shape | Roadmap horizon |
|------------|-----------------|
| Claim hygiene, docs truth, status drift | H0 |
| Daily TUI/chat/agent usefulness | H1 |
| CLI/TUI/IDE/background continuity | H2 |
| MCP, plugins, skills, hooks, subagents | H3 |
| Team, cloud, background, control plane | H4 |
| Eval, prompt, model, provider regression gates | H5 |
| Packaging, release, adoption, support | H6 |

The roadmap row should not repeat the whole ticket. It should link to the ticket
and name the exit evidence.

## Step 5: Verify

Verification is the evidence that allows a state transition.

| Claim | Evidence |
|-------|----------|
| Docs are coherent | `python3 scripts/validate_docs_consistency.py` |
| Docs acceptance stays accurate | `python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q` |
| User-facing behavior changed | Manual smoke or active-path acceptance test |
| Security boundary changed | Targeted security test plus Human Review note |
| Roadmap status changed | Linked exit evidence and updated status row |
| Old docs became stale | Supersession note or active index update |

Tests that inject the state they claim to verify are not closure evidence. They
may prove formatting, but they do not prove active behavior.

## Step 6: Update the status ledger

After verification, update the active ledger or index. Do not leave users to
reconcile dated files manually.

For daily-driver work, update at least one of:

- `docs/daily-driver-current-status.md` for user-facing truth.
- `docs/analysis/daily-driver-findings-status-ledger-2026-06-01.md` or successor.
- `docs/plans/ticket-plans/index.md`.
- `docs/plans/daily-driver/README.md`.

For roadmap work, update:

- `docs/roadmap-status.md`.
- Any linked plan index.

For module-local work, update:

- `docs/modules/<module>/risks.md`.
- `docs/modules/INDEX.md` if the risk is P0/P1 or cross-module.

## Step 7: Archive or supersede

Keep historical evidence. Avoid bulk deletion unless the file is clearly
duplicative and no longer linked by any index.

Use:

- `Superseded` when a newer source replaces the claim.
- `Archived` when the file is retained only for context.
- `Fixed` when the active behavior has proof.

## Classic references

Use these reference models without turning them into heavyweight process:

| Reference model | Use here |
|-----------------|----------|
| ADR | Irreversible technical decision or rejected alternative. |
| RFC/RFD | New capability proposal before implementation. |
| Risk Register | Ranked operational, product, and security risk list. |
| FMEA | Failure mode ranking for stability and UX trust. |
| STRIDE | Security threat classification. |
| Diataxis | Separate guides, how-to docs, reference, and explanation. |
| DRI/RACI | Make roadmap ownership explicit even when owner is `TBD`. |

## Anti-patterns

Avoid:

- Adding a new dated doc that repeats an existing active finding without linking it.
- Marking a ticket done without updating the user-facing status page.
- Treating a module risk file as a central risk register.
- Hiding stale claims by rewriting old history.
- Creating parallel status labels for the same state.
- Using a roadmap as a bug tracker.
- Using a risk register as an implementation plan.

## Lightweight checklist

Before adding or updating a risk, issue, or roadmap document:

- Is there a stable ID?
- Is the current state one of the canonical states?
- Is the active source of truth clear?
- Is there a ticket, roadmap row, or defer decision?
- Is verification named?
- Is the user-facing truth updated if behavior changed?
- Is a supersession note needed?
