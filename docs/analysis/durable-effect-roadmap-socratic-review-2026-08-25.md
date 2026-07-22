# Durable-Effect Roadmap Socratic Review — 2026-08-25

> **Claim class:** Dated Archive evidence snapshot and roadmap proposal. It is not
> current-truth authority; `docs/roadmap-status.md` and `docs/backlog-priority.md`
> own current status and scheduling.
>
> **Trigger:** Owner-requested roadmap rethink using a temporary 2026-08-25
> survey of Pi, Maka, Amplio, Ankole, and distributed-systems patterns.
>
> **Target:** TeaAgent `0df77f7`, package version `0.1.0`, branch `main` at
> packet creation.
>
> **Method:** One shared packet; five read-only scout lenses, one code-review
> lens, one security-review lens; Socratic pressure; coordinator source checks;
> three providerless deterministic probes. No reviewer edited the repository.
>
> **Authority:** Subordinate to Harness-First, DR-006, the canonical roadmap,
> backlog provenance, ADR-0032, and ADR-0042.

## Why → What → How → Done

- **Why:** “Durable execution” can hide three different questions: whether a run
  resumes, whether an operator authorized the exact effect, and whether reality
  changed once and reached a known outcome. TeaAgent's H4 wording did not expose
  those boundaries.
- **What:** Reclassify the roadmap by user-visible promises and proved local
  failures. Keep speculative distributed machinery held; promote only the
  local governance gaps demonstrated on TeaAgent's active seams.
- **How:** Separate repository observations, survey-author claims, and
  `[INFERENCE]`; verify authority before roadmap changes; reproduce load-bearing
  local claims without network effects; require exact adoption status and
  deterministic drift guards.
- **Done:** H4 distinguishes run continuity from effect correctness; EFX-001–003
  become scoped DR-006 governance-gap intake; broad outbox/fencing/actor work
  remains held; daily planning and recovery guidance point to current truth;
  the adoption ledger is guarded by a focused test.

## Panel Consensus

- **Decision:** **AGREE WITH CHANGES.** All seven lenses accepted the core
  distinction between run continuity, decision/approval correctness, and effect
  correctness. All rejected the survey as authority for a generic effect
  engine, distributed outbox, fencing service, actor supervisor, or second
  workflow/event framework.
- **Use-case recommendation:**
  - `study`: **yes** — Pi's intent/effect/settlement boundary, projection versus
    durable truth, provider-specific idempotency/reconciliation, and sink-backed
    fencing are useful design references;
  - `reproduce`: **yes, completed locally for three boundaries** — dispatch
    ambiguity, approval-ID/grant reuse, and prompt-mode effect misclassification;
  - `adopt`: **narrowly** — claim separation, exact-intent approval, effect-class
    inventory, `UNKNOWN`/no-blind-retry semantics, and effect-specific fault
    evidence;
  - `deploy`: **no generic subsystem** — only scoped fixes inside the existing
    governed runner/tool/approval seams qualify under DR-006.

### Routing and recovery honesty

The host launched `scout`, `reviewer`, and `security-reviewer` agent types. No
provider or named model persona is claimed. Scout yields were schema-coerced;
the full required deliverables were recovered over hub messages before
synthesis. Reviewer judgments remain advisory; coordinator-executed probes are
listed separately below.

## Required Wording Changes

1. **H4:** say `durable run-state continuity`, not an unqualified `durable
   execution`; explicitly deny any implication of exactly-once tool execution,
   external-effect settlement, business acceptance, or reversal.
2. **Scheduling rule:** replace the stale “no known authorized code item” claim
   with EFX-001–003 as the only new promoted P0 governance-gap intake. Their
   authorization comes from deterministic local evidence, not the survey.
3. **Backlog and held queue:** promote the three local defects for in-place
   remediation while keeping generic external-effect architecture held behind
   an owner promise, provider contract, and effect-specific evidence.
4. **Daily planning:** demote the 2026-06-04 daily-driver plan to historical
   evidence; route scheduling through the canonical roadmap, backlog, DR-006,
   friction log, and dated decision queue.
5. **Recovery guidance:** warn that an unmatched mutating tool start is
   unconfirmed and that blind rerun can duplicate a non-idempotent mutation.
6. **Survey provenance:** do not cite the removed Pi `harness-v2.md` path; the
   current `harness.md` supports the intent/effect/settlement claims. Avoid
   `CrashBench`/`EffectBench` as TeaAgent benchmark names because unrelated
   projects already use those names.

## Shared Findings

### 1. The survey's useful core is authority separation, not an architecture mandate

**Observed upstream:** Pi's current harness specification describes immutable
entries, mutable total-state registers, a durable program counter, an
intent/effect/settlement “effect sandwich,” replay-safe versus replay-never
behavior, and exactly-once external effects as a non-goal.

**Author-claimed:** The supplied survey synthesizes Pi, Maka, Amplio, Ankole,
Temporal, DBOS, Restate, outbox, fencing, and actor patterns into a broad
reference architecture.

**[INFERENCE]:** The examples support distinctions and test questions. They do
not prove a settled industry consensus, TeaAgent user demand, or the need for
all mechanisms in one local harness. The old Pi `harness-v2.md` survey URL
returned HTTP 404; the current `harness.md` was read successfully.

### 2. Run continuity does not prove effect settlement

TeaAgent records `tool_call_started` before synchronous handler execution
(`teaagent/runner/_core.py:579-600`) and records completion/checkpoint only after
return (`teaagent/runner/_core.py:670-681`). `ToolAnnotations.idempotent` is
exported, displayed, linted, and audited, but the dispatch path does not enforce
it as a retry contract. `RunStore.observations_for_run()` retains completed
observations and does not turn unmatched starts into recovery state.

The first coordinator probe made that gap observable: a child exited after a
non-idempotent temp mutation but before handler return. Audit persisted the
start, the checkpoint row was absent, and an explicit blind same-run/same-call
retry applied the logical mutation twice. This proves a local ambiguity window;
it does not prove a live provider failure or that every normal resume
necessarily repeats the same logical effect.

### 3. Effect authority is under-classified on the governed path

`PromptBackend` auto-approves tools whose annotation says
`destructive=False`. `github_create_pr` and `github_review_pr` mutate GitHub but
are registered non-destructive; create-PR is also labeled idempotent.
`browser_click`, `browser_fill`, and `browser_evaluate` are labeled read-only.

A providerless component probe confirmed those metadata decisions pass
`PromptBackend`. A stronger governed-path probe ran `AgentRunner` in `PROMPT`
mode with registered `github_create_pr` and a mocked `_gh_api`: the handler ran,
the run completed, and no `tool_call_pending_approval` event appeared. No
network call or live GitHub mutation occurred. The result proves the active
approval path trusts a classification that is false for an external effect.

### 4. “Approve once” is not exact-intent authority

Missing model call IDs become predictable `model-{tool_name}` values
(`teaagent/prompt.py:321-343`). `JITApprovalState.approve_once()` stores only the
ID in a reusable set; `is_call_approved()` does not consume it or bind a payload
(`teaagent/approval/manager.py:103-124`).

The second coordinator probe parsed two `github_review_pr` calls with different
arguments and no IDs. Both became `model-github_review_pr`; one `approve_once`
left both repeated approval checks true. No handler ran. This is component-level
proof plus source-backed active-path evidence, not a live unauthorized effect.

### 5. Existing controls remain valuable but partial

- Hash/mtime checks and exact-span edits reduce stale workspace writes.
- Git sandbox and undo journal bound in-worktree recovery.
- Audit JSONL can fsync `tool_call_started` when a durable path is configured.
- Payload-digest approval paths exist elsewhere and show the intended exact
  binding direction.
- `audit_completeness.py` can identify unmatched starts after the fact.

None of those facts currently turns an unmatched start into `UNKNOWN`, makes a
one-time JIT grant single-use, or corrects external-effect metadata. Audit may
also continue memory-only after non-compliance disk errors. Therefore “log a
stable ID” is not an effect-safety guarantee.

### 6. The narrow roadmap change is two-tiered

1. **Promote local correctness:** EFX-001–003 are P0 governance gaps on existing
   TeaAgent seams. DR-006 authorizes scoped remediation without reopening a
   product horizon.
2. **Hold broad effect infrastructure:** generic ledger/outbox/reconciliation,
   fencing, actor supervision, distributed leases, and compensation remain
   absent. Each would need an earned owner-visible promise and a canonical sink
   capable of enforcing the claimed semantics.

No new H7, no horizon renumbering, and no second framework.

### 7. The planning front door had drifted

`docs/daily-driver-current-status.md` called the dated 2026-06-04 plan the
master active plan. `docs/INDEX.md` classifies it as historical, while the
canonical roadmap and DR-006 own current scheduling. The old pointer could
restart closed work by repetition and is corrected in this review.

## Disagreements / Residual Risks

1. **Immediate fix versus held evaluation:** Some lenses initially kept the
   dispatch gap held because the survey alone had no authority. The three probes
   changed the evidence tier. Consensus after the probes: local EFX fixes are
   promoted under DR-006; the generic effect architecture remains held.
2. **Audit as recovery ledger:** An unmatched audit start is useful evidence,
   but audit durability is configuration-dependent and can fail open outside
   compliance mode. The roadmap does not prescribe audit lookup as the sole
   implementation.
3. **Call ID versus effect identity:** A call ID correlates attempts; it is not
   sufficient semantic identity. Normal resume may generate a fresh ID for the
   same intended effect. Acceptance is stated behaviorally rather than freezing
   a call-ID dedup design.
4. **Annotation seam:** Existing registry/governed paths must be reused, but the
   current booleans are insufficient and MCP hints may be untrusted. C4 is only
   partially adopted; the exact additive contract remains an implementation
   decision.
5. **Benchmark names:** The provenance lens treated `CrashBench`/`EffectBench`
   as benchmark conflation. The survey text presents them as proposed labels,
   not established evidence. The concrete issue is name collision, so TeaAgent
   does not adopt those names.
6. **Current exposure:** No live GitHub/browser/provider effect was executed in
   this review. Severity follows the governed path plus mutating handler source,
   not a production incident report.
7. **External-effect scope:** ADR-0042's reversal boundary remains binding.
   Preventing unauthorized or duplicate attempts is not the same as promising
   generic post-hoc reversal.

## Evidence Actually Checked

### Coordinator-executed

| Probe | What ran | Observed result | Boundary |
|---|---|---|---|
| P1 dispatch crash | Isolated child, non-idempotent temp marker, durable audit + SQLite checkpoint, exit 73 inside handler | start persisted; no completion/checkpoint; explicit same-run/same-call retry changed marker `1 → 2` | No external provider; explicit blind retry, not proof of every resume path |
| P2 approval binding | Real parser, PromptBackend metadata decisions, JIT state; no handlers | different payloads shared `model-github_review_pr`; one-time approval remained reusable; GitHub/browser effect metadata auto-approved | Component proof; no network/effect |
| P3 governed prompt path | Real `AgentRunner` + registered `github_create_pr` in `PROMPT`; `_gh_api` mocked | handler called; run completed; no pending-approval event | Active governed path; remote effect mocked |

### Read and inspected

- Harness-first, DR-006, canonical roadmap, backlog provenance, daily-driver
  current truth, held forward-spec index, ADR-0032, and ADR-0042.
- `ToolAnnotations`, `ToolRegistry.execute`, runner dispatch/result/checkpoint,
  resume preparation/run-store observations, audit persistence, JIT approval,
  PromptBackend, GitHub registrations, and browser registrations.
- Existing checkpoint/resume integration test and adoption-guard precedent.
- Pi's current `harness.md`; the survey's old `harness-v2.md` path returned 404.
- The existing projects named CrashBench and OpenAdapt Flow, solely to identify
  naming/provenance risk.

### Not executed

- No live external provider, GitHub mutation, browser mutation, remote MCP
  mutation, paid model call, multi-host lease, network partition, outbox relay,
  or exactly-once claim.
- No panel reviewer edited files or ran project-wide tests.

## Socratic Questions

1. What exact owner-visible promise requires more than local authorization,
   containment, and honest `UNKNOWN` disclosure?
2. Which enabled tools can change remote reality while labeled read-only or
   non-destructive, and what local policy—not remote hint—authorizes each one?
3. Why may a “one-time” approval survive or authorize changed arguments?
4. After a persisted start without settlement, what evidence authorizes another
   attempt?
5. Which provider or canonical resource actually enforces idempotency or rejects
   a stale fence? If none, is the field only telemetry?
6. Can H4 describe checkpoint/resume truth without implying effect settlement,
   business acceptance, or reversal?
7. What real requirement would earn an outbox, reconciliation adapter, lease, or
   actor supervisor?

## Strongest Objection

The probes expose active failures of TeaAgent's core promise of governed
execution. Calling broad architecture “overbuilt” could become an excuse to
leave a high-severity approval bypass and duplicate-effect window open.

**Decision:** accept the objection's urgency, reject its architectural leap.
Promote EFX-001–003 as P0 in-place fixes with permanent behavioral tests. Do not
turn them into an effect platform. If the boring fixes cannot satisfy the
acceptance contracts below, re-litigate mechanism scope from the failing
falsifier—not from survey momentum.

## Roadmap Decision And Acceptance Contracts

| ID | Scope | Status after review | Required observable contract | Explicit non-goal |
|---|---|---|---|---|
| EFX-001 | Interrupted mutating-tool dispatch | **Promote — P0 governance gap** | An unmatched started effect is surfaced as unconfirmed/`UNKNOWN`; non-idempotent work is not blindly redispatched; a permanent process-death fault test proves the boundary | Exactly-once external effects; generic recovery engine |
| EFX-002 | Effect classification and approval escalation | **Promote — P0 governance gap** | Every built-in effectful tool is inventoried; prompt/read-only/workspace-write modes fail closed for external mutation; untrusted remote hints cannot silently relax local policy | Universal effect gateway; provider-independent compensation |
| EFX-003 | One-time approval identity and consumption | **Promote — P0 governance gap** | One-time authority binds the run, tool, canonical payload/effect intent, expires or is consumed before dispatch, and cannot authorize changed arguments | Distributed capability broker; lease service |
| EFX-FUTURE | Provider-specific settlement/reconciliation | **Held** | Only reconsider after local gaps close, an owner-visible promise exists, and the provider offers enforceable idempotency/status/reconciliation semantics with fault evidence | Generic outbox, fencing, actor/OTP, multi-agent expansion |

### Promotion order

1. EFX-002 and EFX-003 first: they are direct authorization failures on the
   governed path.
2. EFX-001 next: preserve unmatched-start evidence and refuse blind mutation
   until the operator or a trusted provider-specific contract resolves it.
3. EFX-FUTURE stays held. Fencing is considered only for actual leased
   multi-executor work and only when the canonical sink rejects stale tokens.

## Candidate Adoption Ledger

| ID | Candidate | Status | Evidence | Next action or trigger |
|---|---|---|---|---|
| C1 | Retain H0–H3 and H0–H6 taxonomy; do not reopen completed survey tracks | adopted | Harness-first, DR-006, prior 2026-07-22 review; panel consensus | Keep status stable; local governance fixes remain roadmap-neutral |
| C2 | Split H4 run continuity from effect correctness | adopted | H4 ambiguity plus P1; seven-lens agreement | Guard exact H4 wording on current-truth surface |
| C3 | Add an effect-safety forward contract gated by evidence | partial | P1–P3 promote local gaps; broad external settlement remains unproved | Promote EFX-001–003; keep EFX-FUTURE held |
| C4 | Reuse ToolRegistry/runner/approval seams and add no second framework | partial | Active gaps sit on those seams, but current booleans/hints are insufficient | Design the smallest additive local contract; do not freeze `ToolAnnotations` as sufficient or exclusive |
| C5 | Adopt execution/decision/effect correctness and authority separation vocabulary | adopted | Survey core, source inspection, probes | Use as claim/test taxonomy, not a new service boundary |
| C6 | Require crash/fault injection for effect-safety promotion | adopted | P1 exposed a gap happy-path tests missed | Land permanent effect-specific fault tests with each fix |
| C7 | Defer outbox, fencing, actor supervision, distributed leases, and generic compensation | deferred | No earned topology/provider contract; ADR-0042 and no-second-framework rule | Reconsider only from explicit owner promise plus failing scoped evidence |
| C8 | Correct the daily planning front door | adopted | Direct conflict between daily status, INDEX, roadmap, and DR-006 | Keep historical plan labeled historical |
| C9 | Preserve ADR-0042's external-effect reversal boundary | adopted | Owner-ratified ADR; panel consensus | Any widening requires a new dated owner decision |

### Adoption guard

`tests/test_docs_consistency.py::test_durable_effect_review_candidate_adoption_state`
asserts C1–C9, the H4 claim split, EFX-001–003 promotion, EFX-FUTURE hold,
the daily planning correction, and the interrupted-effect operator warning.

## Critical Thinking Check

### Assumption audit

- **Assumption:** Prompt mode is expected to gate external mutation. This is
  supported by the operator trust model and approval semantics, but the exact
  annotation design remains open.
- **Assumption:** The temp-marker crash represents non-idempotent tools. It proves
  ordering and duplicate possibility, not frequency or provider behavior.
- **Assumption:** Scoped local fixes can close the proved gaps. Fresh-call-ID
  same-intent retries may falsify a naive call-ID-only design.
- **Assumption:** The owner does not intend to supersede ADR-0042 through this
  request. The request authorizes roadmap reconsideration; it contains no dated
  rationale for generic external-effect closure.

### Falsifiability

This review is wrong or incomplete if any of the following occurs:

1. changed arguments execute under a prior one-time approval;
2. a mutating external tool traverses prompt mode without an exact authority
   decision after EFX-002 closes;
3. an unmatched started effect can create a second logical effect without new
   authority after EFX-001 closes;
4. the current docs imply exactly-once, settlement, acceptance, or reversal from
   checkpoint/resume alone;
5. a proposed outbox/fence/ledger has no canonical sink enforcing its semantics;
6. a candidate is partially adopted but disappears from this ledger or its named
   current-truth surfaces.

## Explicit Non-Goals

- No new agent framework, scheduler, queue, event spine, effect service, actor
  supervisor, outbox daemon, generic reconciliation agent, or compensation
  engine.
- No exactly-once external-effect claim.
- No live provider or remote mutation as evidence.
- No H7, horizon renumbering, cloud/SaaS/multi-tenant expansion, or reopening of
  SCL/CPP legacy survey tracks.
- No durable dependency on the temporary survey or review packet.
