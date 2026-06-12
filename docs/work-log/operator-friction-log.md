# Operator Friction Log

> **Status:** Active intake log.
> **Evidence boundary:** Owner-written entries are evidence. Agent-written
> competitor or community entries are hypotheses until the owner validates or
> rejects them in real TeaAgent use.
> **Derived from:** [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md).

## Purpose

This log is the intake surface for owner-operator friction. It keeps TeaAgent's
UX work tied to real harness use instead of competitor feature parity.

Use this log when:

- the owner hits friction while asking, approving, undoing, resuming, reading a
  receipt, checking cost, or understanding why a run was allowed or blocked
- a competitor UX pattern suggests a possible ergonomics problem, but TeaAgent
  has not validated it locally
- a prior friction entry is closed by a commit, test, or documentation change

## Entry Rules

- Owner-written entries are evidence.
- Agents may add only competitor-derived or community-derived hypothesis entries.
- Hypothesis entries must be tagged `[hypothesis: source, date]`.
- Hypothesis entries must not become roadmap truth until the owner confirms the
  friction in real use or repository evidence shows a governance gap.
- A closed entry must cite the commit, test, or document that resolved it.
- Do not use this log for public positioning, competitor ranking, or feature
  parity requests.

## Entry Format

```markdown
### YYYY-MM-DD - Short title

- **Type:** evidence | hypothesis
- **Source:** owner real use | [hypothesis: source, date]
- **Attempted:** What the owner or source tried to do.
- **Expected:** What should have happened.
- **Actual:** What happened instead.
- **Harness impact:** approval | audit | rollback | cost | receipt | state | validation | ergonomics
- **Status:** open | closed | rejected
- **Closure evidence:** commit/test/doc link, or `n/a`
```

## Owner Evidence Entries

No owner-written evidence entries are recorded in this scaffold. Agents must not
invent owner friction; owner evidence starts when the owner provides or writes a
real-use entry.

## Competitor-Derived Hypotheses

No hypothesis entries are recorded yet. Add them only after a dated source is
captured through the [Signal-to-Acceptance-Gap Process](../processes/signal-to-acceptance-gap.md).

## Related Rules

- [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md)
- [Signal-to-Acceptance-Gap Process](../processes/signal-to-acceptance-gap.md)
- [Evidence to Principle Policy](../governance/evidence-to-principle-policy.md)
