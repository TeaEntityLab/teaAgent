# General-User Conversation Experience — Refresh
# 2026-06-10

> **Claim class:** Dated evidence package.
> **Anchor:** TeaAgent at commit `8fcd781` (HEAD on 2026-06-10).
> **Refreshes:** [User Experience and Conversation Patterns Analysis (2026-06-06)](user-experience-and-conversation-patterns-2026-06-06.md).
> **Perspective:** an ordinary developer (not the maintainer, not a governance
> specialist) using TeaAgent as a daily conversational assistant.

---

## Verdict

The trust-visibility half of the 06-06 UX critique was substantially executed:
run receipts, numbered approval selectors, unified pending-approval queues,
cockpit snapshots, honest token metrics, and resume parity all landed. The
cognitive-load half was not: the system still greets a new user with a large
command vocabulary, governance concepts (tenants, envelopes, receipts, trust
tiers) now appear in *more* surfaces, and the H4 cockpit adds an
operator-grade view without a corresponding "just chat" simplification. The
gap has rotated: in June the risk was *opacity* (users couldn't see what the
agent did); now the risk is *register* — the system speaks compliance-officer
English to someone who asked a coding question.

---

## 06-06 Findings Re-Scored

| 06-06 finding | Status at HEAD | Evidence |
| --- | --- | --- |
| No human-readable run receipt | **Closed.** `run_receipt.py` wired into CLI `run`/`runs` handlers and TUI commands. | Import graph |
| Approval-by-raw-ID UX | **Closed.** Numbered destructive-approval selectors; unified pending queue contract across CLI/TUI (`5ea042f`). | Non-goals doc "Supported today"; commit log |
| Cost figures redacted/wrong in places | **Closed at P0.** Token metrics no longer redacted (`67a5c9b`, `7580121`); TUI cost accumulation fixed earlier (DS-01). | Commit log; findings ledger |
| Resume/suspend semantics broken or unclear | **Improved.** Approve–resume parity (`ac6b318`), suspend/resume roundtrip tests (DS-08). Vocabulary cleanup (WS1-005) only partially verified. | Findings ledger |
| Three divergent chat surfaces | **Structurally improved, not unified.** Shared controller (CG-05, `test_task001_surface_parity.py`) covers CLI/TUI baseline; REPL/TUI/CLI remain distinct entry points with distinct affordances. | Ledger; surface parity tests |
| JSON-heavy default output | **Partially improved.** Receipts and cockpit snapshots give human-readable summaries; many inspection commands still emit JSON-first. | Spot checks |
| Permission-mode vocabulary requires prior knowledge | **Open.** Mode names unchanged; no progressive disclosure observed. | — |

---

## New Observations (2026-06-10)

### UX-R1 — Register mismatch: governance vocabulary in the daily path (High)

A general user's happy path now crosses, at minimum: permission modes, run
receipts, budget envelopes, approval selectors, trust tiers, and (if they open
the TUI) a multi-tenant cockpit with cost-allocation and memory-registry
screens. Each is individually justified; together they make the product feel
like an audit console that also chats. Competitor baseline (see
[consolidation](competitor-analyses-vs-self-consolidation-2026-06-10.md)):
Claude Code, Cursor, and Cline expose approval and cost concepts *lazily* —
only at the moment they matter. TeaAgent exposes them *structurally* — in
navigation, command lists, and receipts by default.

**Concrete test:** the first 10 minutes of a new user's session should require
understanding at most three concepts (ask, approve, undo). Today it does not.

### UX-R2 — The cockpit serves the operator persona, and nobody else yet (Medium)

H4-001 cockpit screens (pending approvals across tenants, cost allocation,
memory registry, background lifecycle) are genuinely good for the *team
operator* persona. But the 06-06 package's core persona — "a normal developer
having a conversation" — gets no equivalent investment in this delta. The
persona priority has silently inverted relative to the daily-driver roadmap
rationale (H1 first, teams later).

### UX-R3 — Conversational quality is untested territory (Medium)

The acceptance suites verify *mechanics* (approval display, cost display,
resume wording, receipt generation — WS1-006). Nothing measures
*conversation*: response latency feel, interruption handling, clarification
behavior, context retention across turns, or graceful degradation when the
model is wrong. As eval infrastructure (H5) exists in component form, the
highest-leverage first wiring of `eval_suite` would be a conversational-quality
suite, not another regression gate.

### UX-R4 — First-run ceremony unchanged (Medium, carried forward)

The 06-06 journey map's setup friction (provider config, mode selection,
workspace trust) is structurally the same. Jules/Codex-class "try it in one
command" onboarding remains the competitor benchmark TeaAgent is furthest
from. The new `update/` package (H6) may eventually help packaged onboarding
but is currently unwired (see
[Engineering Refresh ENG-R1](engineering-critique-refresh-2026-06-10.md)).

### UX-R5 — Vocabulary debt is now self-colliding (Low)

"Tenant" (data partition), "workspace" (filesystem scope), "session",
"run", "goal", and "background run" coexist with overlapping meanings across
CLI flags and docs. Each new subsystem adds nouns faster than the terminology
doc (`docs/terminology.md`) consolidates them. This is the doc⇄reality drift
pattern applied to language.

---

## What "Good" Looks Like for a General User (Target State)

1. **One obvious entry:** `teaagent` opens a conversation; everything else is
   discoverable from inside it. REPL/TUI/CLI remain, but as views of one
   session, which the shared controller now makes feasible.
2. **Three-concept onboarding:** ask, approve, undo. Receipts, budgets,
   tenants, and trust tiers appear only when an action triggers them, each
   with a one-line plain-English explanation.
3. **Progressive disclosure of governance:** the same receipt has a
   two-line human summary on top and the audit-grade detail behind a flag or
   keypress. Governance depth becomes a feeling of safety, not a reading
   assignment.
4. **Conversational eval gate:** a small fixed corpus of multi-turn sessions
   (clarification, interruption, correction, long-context recall) scored in
   CI via the now-existing `eval_suite` machinery, so conversational quality
   cannot silently regress — this is also the cheapest honest wiring target
   for H5.

---

## Recommendations (feed into work directions)

1. Run a "ten-minute stranger test" (someone who has never seen TeaAgent) and
   record every concept they were forced to confront; drive UX-R1 from that
   list, not from maintainer intuition.
2. Add plain-language summaries as the first line of every receipt and
   approval prompt; keep JSON behind `--json`.
3. Freeze the noun set: one pass over `docs/terminology.md` that declares
   canonical terms and marks the rest as aliases, enforced by docs lint.
4. Wire `eval_suite` to a conversational-quality corpus before wiring it to
   release gating; it derisks both H5 and UX simultaneously.
5. Defer further operator-cockpit breadth until the general-user path has had
   one equivalent investment cycle.
