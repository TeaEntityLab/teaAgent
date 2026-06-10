# Eval Gate Competitor Absence Note — 2026-06-10

**Work item:** WDD-003  
**Claim class:** Competitive positioning evidence (not a product survey).

## Finding

As of 2026-06-10, TeaAgent ships a **release eval gate** (`scripts/run_release_eval_gate.py`,
wired in `.github/workflows/release.yml`) with a conversational regression corpus.

Surveyed IDE-first agents (Cursor, Copilot, Windsurf) and hosted delegators (Codex
cloud, Devin-style products) do **not** publish an equivalent **blocking release
eval gate** tied to operator receipts and audit evidence. They optimize for latency,
IDE integration, or hosted delegation — not governed release blocking.

## Inference (bounded)

The eval gate is a plausible public differentiator **once** S1–S3 truth work is
complete and the gate stays green on release tags. This note does not claim
superior model quality — only differentiated **governance-at-release**.

## Re-verify trigger

Next competitor landscape refresh (WS6-003 quarterly) or any competitor shipping a
documented release-blocking eval gate.
