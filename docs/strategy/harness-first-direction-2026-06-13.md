# Harness-First Direction and Restructuring Plan

> **Claim class:** Direction decision record + restructuring spec (owner-ratified).
> **Date:** 2026-06-13. **Anchor:** `d736a1b`.
> **Supersedes (in direction questions only):** the implicit "product seeking
> external users" posture in `docs/product-contract.md` personas and the
> WDH-002 simulated-pilot evidence line. Engineering findings in the dated
> review packages remain valid.
> **Derived from:** the 2026-06-12 strict direction review (closed-loop
> evidence finding) and the owner's explicit answer to its strategic fork.
> **Human review required before:** changing public positioning text,
> deleting docs/tests, or starting Phase 2 of the architecture migration.

---

## 1. The Identity Decision (owner-ratified, 2026-06-13)

**TeaAgent is harness-first.** It is the owner's personal, local-first,
provider-agnostic governance harness for agentic coding work — option (b)
from the 2026-06-12 direction review.

**The usability track exists because the owner-operator himself finds the
harness hard to use — not to chase external adoption.** This single sentence
re-grounds every UX decision:

- The persona is the **owner-operator**: one person who is simultaneously
  the maintainer, the daily user, and the governance auditor of his own runs.
- "Simulated pilots" are retired as evidence sources. The UX backlog has
  **two intake channels** (§5.1): the **operator friction log** (the owner's
  own recorded WTF-moments — ground truth by definition) and
  **competitor-survey-derived UX hypotheses** (the existing survey mechanism,
  retargeted from positioning to ergonomics). A hypothesis becomes evidence
  only after the owner validates it in real use.
- External adoption claims (daily driver for ordinary developers,
  enterprise-ready, team operations) are **descoped from current truth**.
  They may return later as goals, but no doc may state them as present-tense
  capability. `docs/product-contract.md` personas and README framing should
  be edited to match (TASK-001).
- Multi-agent co-maintenance (Claude Code sessions, parallel agents, Devin)
  is part of the identity: the harness's first external users are **other
  agents working on the harness itself**, governed by the agent contribution
  contract. This is dogfooding, and it has already paid (V1, V8 caught).

**What this dissolves:** the closed-evidence-loop finding stops being a
defect. A personal harness validated by its owner's daily use and its own
gates is *exactly* a closed loop, on purpose. The remaining honesty
requirement is only that docs never claim more than that.

## 2. North-Star Spec

### Problem

The harness works (646/646 acceptance, receipts, undo, audit chain) but is
hard to operate, even for its author: too many concepts on the happy path,
governance vocabulary saturating daily interactions, a runner that has
become a gravity well, three half-finished eventing systems, and a docs
corpus (582 files, 110 analysis docs) that costs more to keep truthful than
it returns.

### Goals (measurable, owner-centric)

| # | Goal | Acceptance signal |
| --- | --- | --- |
| G1 | The owner can run a daily task without consulting docs | Friction log shows zero doc-lookups for the ask/approve/undo path over a week of real use |
| G2 | Any run can be explained from one artifact | `teaagent show <run>` answers "why was this allowed, what changed, how do I undo" in one screen |
| G3 | One event spine | Every governance decision and audit fact is derived from a single typed run-lifecycle event stream (§6) |
| G4 | Extensible by hooks, not forks | The owner can add a lifecycle behavior (lint-on-write, custom budget rule) as a registered hook without touching `AgentRunner` |
| G5 | Docs corpus carries its weight | Constitution tier ≤ 12 claim-tested docs; everything dated is archive-tiered with an aging policy |
| G6 | Tests prove behavior, not construction | Every test is typed (contract / behavior / adversarial / lifecycle); count stops being a vanity metric |

### Non-Goals (binding until revisited by a new decision record)

- External user acquisition, marketing positioning, or competitor *parity*
  work. Scoped exception (owner-ratified 2026-06-13): **competitor UX/
  ergonomics surveys are allowed** as friction-hypothesis intake for §5.1 —
  dated, source-linked, and labeled hypothesis until owner-validated.
  Positioning surveys and self-surveys remain frozen (WDH-001).
- Remote/federated multi-agent execution beyond the existing non-goals doc.
- A general-purpose workflow/event engine. The event spine covers the **run
  lifecycle only**; it is not a plugin message bus, not a distributed queue.
- Big-bang runner rewrite. Every architecture step is behavior-preserving
  and lands with the acceptance tier green.

### Actors

- **Owner-operator** — runs tasks, approves, reads receipts, undoes.
- **Co-maintainer agents** — edit the repo under the contribution contract.
- **The harness itself** — emits events, enforces gates, produces receipts.

### Failure modes this plan must not create

- Event spine becomes a fourth parallel system instead of replacing three.
- Hook API ships before veto/ordering/error semantics are pinned, breaking
  determinism of the acceptance suite.
- Docs restructure deletes evidence that the claim-audit rules require.

## 3. Docs Restructure (from 582 files toward a tiered corpus)

### 3.1 Three tiers

| Tier | Contents | Rules |
| --- | --- | --- |
| **Constitution** (≤ 12 files) | product-contract, architecture, terminology, governance contract, agent-contribution-contract, roadmap-status, acceptance, this file | Claim-tested (traceability matrix), gated by `validate_docs_consistency.py`, every line is current truth |
| **Working** | guides, runbooks, ADRs, design notes | Reviewed on a trigger (the existing "Review trigger" headers); may go stale but must say so |
| **Archive** | every dated analysis/review/critique/delta file | Immutable once superseded; excluded from currency checks; aging dashboard tracks them but no one is obliged to refresh them |

### 3.2 Concrete moves

- Mark all `docs/analysis/*-2026-*` files as archive tier in the inventory
  generator; the aging dashboard stops nagging about them (they are records,
  not promises).
- `docs/product-contract.md` + README: rewrite personas to owner-operator;
  move "ordinary developer / team operator" personas to a `future-goals`
  section explicitly labeled aspiration.
- Codify the **introspection freeze**: new dated review artifacts require a
  triggering event (incident, release, quarterly) — enforced as a docs-lint
  warning when a new `*-review-*.md`/`*-critique-*.md` lands without a
  trigger note.
- Inventory regeneration moves into the pre-commit hook chain (it went stale
  four times in one day on 2026-06-12; humans should never run it manually).

### 3.3 Do not

- Do not delete dated evidence (claim-audit rules forbid it); archive it.
- Do not write a new strategy doc per session; **amend this one**.

## 4. Test Restructure

### 4.1 Type every test

Four types, declared by marker or directory, enforced by the existing
`audit_test_quality.py`:

| Type | Proves | Current home | Rule |
| --- | --- | --- | --- |
| Contract | An interface holds (provider metadata, receipt fields, plan contract) | `tests/test_governance_contract.py`, `test_run_receipt.py` | Deterministic, fake adapters welcome |
| Behavior | A user-visible flow works end-to-end | `tests/acceptance/` | Drives real CLI/runner paths; FakeAdapter only as the model |
| Adversarial | A boundary refuses correctly | `test_adversarial_*` | Each maps to a denial reason code |
| **Lifecycle** (new with §6) | The event spine emits the right events in the right order with the right payloads | new `tests/lifecycle/` | Asserts event sequences, not implementation internals |

### 4.2 Direction shifts

- **Stop counting; start typing.** The acceptance count guard stays (it
  catches drift) but no doc may use raw counts as a quality claim.
- As gates migrate onto the event spine, their tests migrate from "call the
  internal method" to "assert the event sequence" — lifecycle tests become
  the primary regression net, which decouples tests from runner internals
  and makes the gravity-well refactor safe.
- Deprecated paths out of flagship tests: the first-hour e2e still exercises
  `preapproved_call_ids` (deprecation warning in every run); flagship proofs
  must use the current approval mechanism (TASK-004).
- Deletion policy: a test may be deleted when its assertions are fully
  covered by a typed successor *and* the traceability matrix is updated in
  the same commit.

## 5. Operator UX Track (the real "(a)")

### 5.1 Operator friction log

A single append-only file `docs/work-log/operator-friction-log.md`. Every
time the owner hits friction in real use, one dated line: what was
attempted, what was expected, what happened. Rules:

- Owner-written entries are evidence; nobody simulates them.
- Agents may append **competitor-derived hypothesis entries**, tagged
  `[hypothesis: <source, date>]` — drawn from dated competitor UX surveys
  (the survey mechanism, retargeted at ergonomics). A hypothesis converts to
  evidence only when the owner confirms the friction (or its absence) in
  real use.
- The UX backlog derives from this log's evidence and hypothesis entries —
  no speculative UX work outside it.
- A friction entry is closed by a commit that links it.

### 5.2 Known friction to seed the log (from the 06-10/06-11 UX findings)

- Register mismatch: governance nouns (tenant, envelope, trust tier,
  cockpit) appear on the daily path; target remains ask/approve/undo with
  progressive disclosure (WDC-002 shipped the mechanism; verify it in
  *daily real use*, not in tests).
- Receipts: plain-language first line everywhere; JSON behind `--json`.
- The V8 lesson as UX: precedence must be *visible* — `teaagent doctor
  config` should print where each effective setting came from (CLI / env /
  cwd config / root config / default). One command kills the entire class
  of "why is it read-only" confusion (TASK-005).

## 6. Core Architecture: One Event Spine, Gates as Interceptors

### 6.1 Current state (verified at `d736a1b`)

Three parallel half-systems already exist:

1. **Audit strings** — `audit.record('run_started', …)` etc., scattered
   call sites, implicit taxonomy, consumed by receipts/evidence.
2. **HookRegistry** (`teaagent/hooks.py`, Claude-Code-compatible events:
   SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact,
   Stop, SubagentStop, SessionEnd; `HookError` = veto) — wired only at the
   tool boundary via `chat_agent` → `tool_registry`.
3. **ContextBus** (`teaagent/context_bus.py`, DeltaCards) — separate.

Meanwhile every governance gate (approval, budget, plan, tool policy) is
inline in `AgentRunner` (`runner/_core.py`), which the ownership map
(`docs/architecture/control-loop-ownership-map-2026-06-11.md`) already
declares a gravity well. `PlanValidator.evaluate_write_gate()` (W6) is the
one extracted seam and the template for the rest.

### 6.2 Target shape

```
                    ┌──────────────────────────────────────────┐
                    │            AgentRunner (thin)            │
                    │  loop control · iteration · cancellation │
                    └───────────────┬──────────────────────────┘
                                    │ emits typed RunEvents
                          ┌─────────▼─────────┐
                          │    Event spine    │  ordered, sync-first,
                          │  (run lifecycle)  │  veto-capable phases
                          └─┬─────┬─────┬─────┘
              interceptors  │     │     │   consumers (never veto)
        ┌───────────────────┘     │     └──────────────────────┐
        ▼                         ▼                            ▼
  Plan gate · Approval gate   User hooks                AuditLogger →
  Budget gate · Tool policy   (HookRegistry,            receipts / evidence
  RBAC/policy (shadow→enforce  public API)              ContextBus deltas
  per ADR 0031)
```

Principles:

- **One taxonomy.** A typed `RunEvent` (enum + dataclass payloads) whose
  members are seeded from the union of today's audit event names and
  `HookEvent`. Audit strings become serialized RunEvents; the implicit
  taxonomy becomes explicit and claim-testable.
- **Two subscriber classes.** *Interceptors* (governance gates) run in a
  declared order and may veto (the existing `HookError` semantics,
  generalized; veto carries a `DenialReasonCode`). *Consumers* (audit,
  receipts, evidence, ContextBus, webhook sink) run after interceptors and
  can never affect the run.
- **Receipts derive from events.** `run_receipt`/`run_evidence` stop being
  hand-assembled and become folds over the event stream — which makes
  "receipt completeness" structurally guaranteed instead of test-enforced,
  and kills the synthetic-vs-real receipt gap found on 06-11.
- **Hooks are the public subset.** User-facing hooks subscribe to the same
  spine with a stability contract (names, payload schema, ordering, error
  isolation: a crashing consumer hook logs and continues; a crashing
  interceptor fails closed). Claude Code-compatible names are preserved as
  aliases.
- **Sync-first.** The spine is synchronous in-process (ADR 0018's
  async-from-sync pattern applies where needed). No threads, no queues —
  determinism for tests outranks throughput.
- **Shadow→enforce as configuration.** Policy/RBAC interceptors carry a
  `mode: shadow|enforce` flag; ADR 0031's promotion becomes a one-line
  config flip with an acceptance test, not a code change.

### 6.3 Lifecycle phases (taxonomy seed)

`run_started → plan_resolved → iteration_started → decision_received →
[tool_call_requested → gates… → tool_call_{approved|blocked|completed|failed}]*
→ context_compacted? → budget_checkpoint* → iteration_completed →
final_validation → run_{completed|failed|pending_approval|cancelled} →
receipt_emitted`

plus session-scope events (session_start/end, skill_load, model_route,
git_sandbox_started/resolved, undo_performed). The full schema is an ADR
(TASK-006); this list is the seed, not the contract.

### 6.4 Migration: strangler, dual-write, one gate at a time

| Step | Change | Invariant proven before next step |
| --- | --- | --- |
| M0 | Define `RunEvent` types + spine; **dual-write**: runner emits RunEvents alongside existing `audit.record` calls | Lifecycle tests assert event sequence for the five-minute-proof scenario; acceptance tier green |
| M1 | AuditLogger becomes a consumer (serializes RunEvents); old call sites delegate | Byte-equivalent audit JSONL on the proof scenario (golden file) |
| M2 | Receipts/evidence fold over events | Receipt completeness test passes from events alone; synthetic-receipt fixtures retired |
| M3 | Plan gate moves to interceptor (reuse `PlanValidator`) | Same denials, same reason codes; adversarial tests unchanged |
| M4 | Approval gate, then budget gate | `pending_approval` semantics identical; W8/V-series regressions stay green |
| M5 | HookRegistry re-homed onto the spine; public hook API documented | Existing hook lifecycle acceptance tests pass via aliases |
| M6 | ContextBus + webhook sink consume the spine; inline emission paths deleted | Wiring validator shows no orphaned eventing module |

Stop-rule: if any step needs >1 behavioral change to land green, stop and
re-slice — the 06-11 rule ("if the wrapper becomes noisy, stop") applies
spine-wide.

## 7. Task Plan (first slice)

### TASK-001: Reposition constitution docs to harness-first
- Goal: product-contract/README personas match §1; aspirational claims labeled.
- Acceptance: docs validator green; claim-audit finds no present-tense adoption claims.
- Risk: low. Parallelizable: yes. Human review: yes (positioning text).

### TASK-002: Docs tiering in inventory generator
- Goal: archive tier excluded from currency nagging; inventory regen in pre-commit.
- Acceptance: aging dashboard shows tier column; pre-commit regenerates inventory; validator green.
- Risk: low. Parallelizable: yes. Human review: no.

### TASK-003: Test typing pass
- Goal: every test file declares contract/behavior/adversarial/lifecycle type (marker); quality audit reports per-type counts.
- Acceptance: `audit_test_quality.py` extended; zero untyped files.
- Risk: low, mechanical. Parallelizable: yes. Human review: no.

### TASK-004: Flagship tests off deprecated approval path
- Goal: first-hour e2e + five-minute proof use scoped approvals, not `preapproved_call_ids`.
- Acceptance: no deprecation warnings in flagship runs; tests green.
- Risk: medium (touches approval flow). Human review: no.

### TASK-005: `teaagent doctor config` provenance view — DONE (2026-06-14)
- Goal: print effective config with per-key source (CLI/env/cwd/root/default) using the V8 sentinel knowledge.
- Acceptance: command exists; integration test; friction-log entry closeable.
- Risk: low. Human review: no.
- **Status: DONE.** `teaagent doctor config [--root]` prints each effective config
  key with its provenance source (`default` -> `config:config.toml` ->
  `config:config.json` -> `env:VAR`; CLI overrides noted, not resolved, since
  doctor is not the agent run). Backed by a single source of truth:
  `resolve_config_provenance()` in `teaagent/ergonomics/workspace_defaults.py`,
  from which `load_workspace_defaults` is now derived (cannot drift). Secrets are
  redacted while their source is preserved. Tests in
  `tests/test_workspace_defaults_toml.py` (resolver layering/precedence,
  load-derivation consistency, doctor-command integration incl. secret
  redaction). This command is the citeable closure mechanism for any
  owner-logged config-source-confusion friction (the log's evidence entries
  remain owner-seeded per TASK-007).
- **Review fix (F-A):** provenance distinguishes the shell environment
  (`env:VAR`) from the workspace env file (`env-file:.teaagent/env`); a var set
  in both is attributed to the shell, which wins. (Initially both were
  mislabeled `env:` — defeating the point for env-file values.) Residuals,
  documented not fixed: `automation_webhook_url` is not redacted (could embed a
  token; consistent with existing redaction policy); a malformed numeric env var
  raises in both `resolve_config_provenance` and `load_workspace_defaults`
  (pre-existing, unchanged behavior).

### TASK-006: RunEvent taxonomy ADR + M0 dual-write spike
- Goal: ADR for event schema; spine emitting alongside audit on the proof scenario.
- Acceptance: lifecycle test asserts the §6.3 sequence; acceptance tier green; ADR merged.
- Risk: medium. Human review: **yes** (schema is the long-term contract).
- Dependency: none, but M1+ depend on it.

### TASK-007: Operator friction log bootstrap
- Goal: create the log; owner seeds it with the current top-5 real frictions;
  agents may seed competitor-derived `[hypothesis]` entries from dated surveys.
- Acceptance: file exists with ≥5 dated owner-written evidence entries
  (hypothesis entries do not count toward the 5).
- Risk: none. Human review: **yes — evidence entries are owner-only;
  hypothesis entries are agent-permitted.**

Sequencing: 001/002/003/007 are a parallel batch (days); 004/005 next;
006 starts the architecture arc and gates everything in §6.4.

## 8. Open Questions (tracked, not hidden)

1. Should ContextBus DeltaCards become RunEvent payloads or remain a derived
   view? (Decide at M6, not before.)
2. Does the TUI need its own session-scope events beyond the Claude-Code
   aliases? (Collect from friction log.)
3. When policy/RBAC flip to enforce (ADR 0031 expiry 2026-09-12), does the
   interceptor order need owner-configurable priority? (Default: fixed
   order, revisit on evidence.)
4. Archive-tier retention: keep forever vs. compress quarterly? (Owner call;
   no action before 2026-Q3.)

## 9. Standing Rules Carried Forward

- WDH-001 narrowed: positioning/self-surveys stay frozen; competitor **UX**
  surveys are a standing permitted intake for the friction log (§5.1).
- Truth gates stay: count guard, wiring validator, contract gate, docs
  consistency — they are the constitution's immune system.
- Every claim in this doc is dated and anchored; supersede with a note,
  never delete.
