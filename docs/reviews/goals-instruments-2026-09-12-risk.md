# Risk Report — Goals-review instrument slice (G-P2-11)

**Date:** 2026-09-12 · **Scope:** B-01–B-04, B-08 from the goals Socratic panel
**High-risk path touched:** `teaagent/runner/_core.py` (one additive payload field)

## What changes in the runner

`_initialize_run_state` adds `origin` to the `run_started` event payload when
the caller did not supply one via `run_started_extra`. Source:
`TEAAGENT_RUN_ORIGIN` env var, default `'unknown'`.

## Risk assessment

- **Blast radius:** additive payload key on one event type. No gate, approval,
  budget, or policy path reads `origin`. Consumers added: `RunSummary.origin`
  (index round-trip) and `scripts/prepare_g1_evidence.py` (read-only report).
- **Failure mode:** a caller could set `TEAAGENT_RUN_ORIGIN=owner` on synthetic
  runs, inflating the organic denominator. Mitigation: the field is
  self-declared provenance, not a verified attestation — the G1 report's note
  discloses this, and the falsifier (frictionless unreachable at zero organic)
  still holds because `unknown` never counts as organic.
- **Backward compatibility:** old index rows and run files lack `origin`;
  `summarize()`/`_read_index` default to `'unknown'`. Verified by
  `test_run_origin_round_trips_through_index`.
- **Rollback:** revert the hunk; `origin` becomes absent again and everything
  defaults to `'unknown'`. No persisted state depends on it.

## Decision

Proceed. The change is the smallest honest provenance signal available without
a new channel (callers already had `run_started_extra`); the env-var fallback
makes it usable by an owner shell alias without touching CLI plumbing.
