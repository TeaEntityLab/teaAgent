# Implementation Roadmap With Effort/Impact Analysis — TeaAgent
# 2026-06-06

> **Supersession note, 2026-06-07:** This file contains volatile facts
> (star counts, pricing, model availability, adoption claims, or status claims)
> that may be stale. For current competitive positioning and claim hygiene, see
> [competitive-claim-audit-2026-06-06.md](../analysis/competitive-claim-audit-2026-06-06.md).
> For current roadmap status, see [roadmap-status.md](../roadmap-status.md).

> **Claim class:** Plan and workstream decomposition.
>
> **Status:** Proposed. All effort estimates are engineering judgment from
> code-grounded review at HEAD `ad5e2d7`. No team has been assigned.
> Revisit estimates after first sprint retrospective.
>
> **Sources:**
> - [System Improvement Work Directions](../plans/system-improvement-work-directions-2026-06-06.md)
> - [System Review Workstream Traceability](../plans/system-review-workstream-traceability-2026-06-06.md)
> - [Engineering Architecture Critique](../analysis/engineering-architecture-critique-2026-06-06.md)
> - [Risk and Trust Model Critique](../analysis/risk-and-trust-model-critique-2026-06-06.md)
> - [Performance and Observability Critique](../analysis/performance-and-observability-critique-2026-06-06.md)
> - [Integration and Extensibility Critique](../analysis/integration-and-extensibility-critique-2026-06-06.md)
> - [User Experience and Conversation Patterns Analysis](../analysis/user-experience-and-conversation-patterns-2026-06-06.md)
> - [Active Findings Status Ledger](../analysis/active-findings-status-ledger-2026-06-06.md)
>
> **Effort scale:**
> - XS = < half a day
> - S = 1–3 days
> - M = 3–7 days
> - L = 1–2 weeks
> - XL = 2–4 weeks
>
> **Impact scale:**
> - L = Low (cosmetic, minor DX)
> - M = Medium (meaningful improvement, unlocks next item)
> - H = High (prevents failure mode, unlocks enterprise conversation, or enables market claim)
> - C = Critical (data loss, security, trust claim, or blocking revenue)

---

## Table of Contents

1. [Part 1 — Work Item Catalog with Effort/Impact Matrix](#part-1)
2. [Part 2 — Phase 1–4 Detailed Breakdown](#part-2)
3. [Part 3 — Resource Planning and Tradeoff Matrix](#part-3)
4. [Part 4 — Decision Rules for Item Selection](#part-4)
5. [Part 5 — Resource and Capability Assessment](#part-5)

---

<a name="part-1"></a>
## Part 1: Work Item Catalog with Effort/Impact Matrix

### Reading the matrix

Each row maps to a finding in the June 6 critical review package. The
**3M / 6M / 12M** columns show the recommended delivery horizon:

- `✅` = target delivery window
- `—` = intentionally deferred
- `⚡` = pull forward if resources allow

The **Dependencies** column lists item IDs whose acceptance criteria must pass
before this item begins. "None" means it can start immediately.

---

### Cluster 0 — Claim Hygiene and Maturity Boundaries (WS0)

These items eliminate stale or overreaching claims from the codebase before any
market work or external audit. They cost almost nothing but protect every
downstream claim from being undermined.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **WS0-001** | Define claim classes for docs | Add frontmatter `claim-class` to all analysis, strategy, and plan docs; define five classes (current-truth, dated-evidence, proposal, aspiration, non-goal) in a governance doc | XS | H | None | ✅ | — | — |
| **WS0-002** | Supersede stale competitor facts | Add a `supersession-note` block to every doc that contains volatile data (star counts, pricing, model names, hosted availability). Link to a same-day refresh source | XS | M | WS0-001 | ✅ | — | — |
| **WS0-003** | Subsystem maturity map | Create `docs/maturity-matrix.md` with `stable / beta / alpha / experimental` labels for: runner, tools, approval, audit, providers, chat, TUI, subagents, memory, plugins, remote orchestration | S | H | WS0-001 | ✅ | — | — |
| **WS0-004** | Release checklist claim guard | Add prohibited-claim examples and required-proof links to `docs/release-checklist.md`; block "enterprise-ready", "remote-ready", "sandbox-complete" without linked evidence | XS | M | WS0-003 | ✅ | — | — |

**Cluster 0 total:** ~3 FTE-days

---

### Cluster 1 — Architecture and Engineering Health (WS5, ENG)

These items address code-level structural debts identified in the engineering
architecture critique. Most are self-contained refactors that reduce coupling,
improve testability, and unblock downstream extensibility work.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **ENG-01** | Fix ApprovalPolicy thread leak | Add `__del__` / explicit `shutdown()` to `ApprovalPolicy` in `policy.py:70`; test in long-lived process and 3000+ test suite run | S | H | None | ✅ | — | — |
| **ENG-02** | Introduce RunContext dataclass | Replace mutable `context: dict` run bag with a typed `RunContext` dataclass; migrate callers in `chat_agent.py`, `runner/_core.py` | M | H | None | ✅ | — | — |
| **ENG-03** | Bound AuditLogger in-memory events | Add a max-event cap and streaming flush path to `AuditLogger.events` list; prevent unbounded growth in daemon mode | S | M | None | ✅ | — | — |
| **ENG-04** | Paginate runs-index.jsonl | Add pagination and optional pruning to `run_store.py`; cap listing at configurable N most-recent runs | S | M | None | ✅ | — | — |
| **ENG-05** | Cap approval-queue global dict | Add TTL and max-size eviction to `_approval_queues` module-level dict in `subagents/_approval_queue.py` | S | M | None | ✅ | — | — |
| **ENG-06** | Define AgentService run boundary | Extract `run_chat_agent()` orchestration into an `AgentService` class; CLI, TUI, tests, and plugins call one entry point | L | H | ENG-02 | — | ✅ | — |
| **ENG-07** | Stable event stream contract | Define an `EventStream` interface that consumers (TUI, plugins, receipts) can subscribe to without coupling to internal audit objects | M | H | ENG-06 | — | ✅ | — |
| **ENG-08** | 1000-agent scale test suite | Add pytest fixtures and scripts for 1000-iteration, multi-subagent workloads; measure thread counts, memory growth, and audit log size | L | M | ENG-01, ENG-03 | — | ✅ | — |
| **ENG-09** | Async/await refactor planning | Produce a design document for transitioning the synchronous run loop to async-first; identify risk areas and migration sequence | M | H | ENG-06 | — | — | ✅ |
| **ENG-10** | Async/await implementation | Implement async-first run loop per the design document | XL | H | ENG-09 | — | — | ✅ |

**Cluster 1 total:** ~45 FTE-days across three phases

---

### Cluster 2 — Security, Trust, and Audit Integrity (WS3, RISK)

These items address the risk and trust model critique. Several are data-loss or
audit-integrity risks that belong in Phase 1 before any enterprise or compliance
claim is made.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **RISK-01** | HMAC key save error handling | Replace `except OSError: pass` in key-save path with explicit logging and run-abort in compliance mode | XS | C | None | ✅ | — | — |
| **RISK-02** | Cost rates for offline providers | Set non-zero default cost rates for fake/ollama/vllm providers; guards budget enforcement when real rates unknown | XS | M | None | ✅ | — | — |
| **RISK-03** | Expand path containment checks | Add approval path containment checks for all path-like arguments; cover symlinks, `..` traversal, workspace escape, and destructive tools | M | H | None | ✅ | — | — |
| **RISK-04** | Approval timeout default | Set a non-zero default expiry on approval requests; prevent stale approvals from being reused in the next run | S | H | None | ✅ | — | — |
| **RISK-05** | Compliance-mode fatal audit | In compliance mode, make audit disk write failure halt the run instead of silently continuing in memory | M | C | RISK-01 | ✅ | — | — |
| **RISK-06** | Strict audit chain verification | Add a strict mode that rejects legacy reset lines in the chain; require explicit compatibility flag for old logs | M | H | RISK-05 | ✅ | — | — |
| **RISK-07** | Approval token exactness tests | Add tests proving a destructive call cannot reuse a stale or mismatched approval token across runs | S | H | RISK-04 | ✅ | — | — |
| **RISK-08** | Cost state taxonomy | Define and document `estimated / provider-reported / pending / unknown` cost states; expose in receipts and TUI | M | M | ENG-02 | — | ✅ | — |
| **RISK-09** | Prompt injection boundary docs + tests | Document and test tool output, skill, memory, and repo-doc trust boundaries; add prompt injection boundary assertions | M | H | None | — | ✅ | — |
| **RISK-10** | VFS sandbox integration | Integrate or enforce VFS-based file system sandbox for workspace-write tool calls; validate escape prevention | L | H | RISK-03 | — | ✅ | — |

**Cluster 2 total:** ~32 FTE-days across two phases

---

### Cluster 3 — Multi-Agent Safety and Coordination (WS2)

These items address the multi-agent coordination critique. None of these should
be deferred if TeaAgent intends to ship any multi-agent or remote-agent claims.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **MA-01** | Make shared subagent isolation explicit | Change default subagent isolation from `shared` to `isolated`; add explicit `isolation=shared` flag; document the difference | S | H | None | ✅ | — | — |
| **MA-02** | Batch-level timeout and cancellation | Add `deadline` parameter to subagent batch execution; report partial results on timeout without hanging the parent | M | H | None | ✅ | — | — |
| **MA-03** | Propagate budget envelopes to children | Ensure child agents inherit `max_iterations`, `max_tool_calls`, `cost_budget`, and `elapsed_time_budget` from parent unless explicitly narrowed | M | H | ENG-02 | ✅ | — | — |
| **MA-04** | Enforce depth and concurrency controls | Add global depth and concurrency caps that cannot be bypassed by named or anonymous subagent definitions | M | H | MA-01 | ✅ | — | — |
| **MA-05** | Durable approval queue abstraction | Replace in-process approval queue with an interface that supports file-backed recovery; keep local-process as default | M | H | RISK-05 | — | ✅ | — |
| **MA-06** | Orchestration unification design | Produce one design document naming the canonical orchestration manager, migration path from `SwarmManager`/`SubagentManager`, and compatibility tests | M | M | MA-01 to MA-04 | — | ✅ | — |
| **MA-07** | Subagent failure semantics | Define and test child failure propagation: hard stop, partial result, retry, or escalation to human gate | M | H | MA-02 | — | ✅ | — |

**Cluster 3 total:** ~22 FTE-days across two phases

---

### Cluster 4 — Observability and Operations (WS4, OPS)

These items make TeaAgent diagnosable from product commands without reading raw
JSONL or source code. They are a prerequisite for operator trust claims.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **OPS-01** | Run receipt MVP | Emit a human-readable run receipt after every run: goal, provider/model, mode, budget, tools used, approvals, files touched, cost state, audit path, resume state | M | H | ENG-02 | ✅ | — | — |
| **OPS-02** | LLM and tool latency metrics | Record per-run latency buckets for LLM call, tool execute, approval round-trip, audit write, and storage write | M | H | OPS-01 | ✅ | — | — |
| **OPS-03** | Approval queue age and depth display | Add `teaagent approvals` command showing pending items with age, risk class, and expiry; surface in TUI sidebar | M | M | RISK-04 | ✅ | — | — |
| **OPS-04** | Audit tail command | Add `teaagent audit tail` with redaction and event classification; show last N events in human-readable form | S | M | RISK-05 | ✅ | — | — |
| **OPS-05** | Audit durability health display | Show disk write failure count, cooldown status, and chain verification status in receipt and `selftest` output | S | H | RISK-05, RISK-06 | ✅ | — | — |
| **OPS-06** | Config lint for unsafe combinations | Add `teaagent lint --config` that warns about permissive tools, missing audit path, shared isolation, unclear cost policy | M | M | OPS-01 | — | ✅ | — |
| **OPS-07** | Structured JSON logging | Emit structured JSON logs for all agent events; replace remaining bare-string log calls in `chat_agent.py` and `runner/_core.py` | M | H | None | ✅ | — | — |
| **OPS-08** | Rotating log files | Add log rotation policy with configurable max size and retention count; prevent unbounded log growth | S | M | OPS-07 | ✅ | — | — |
| **OPS-09** | Kubernetes reference deployment | Publish a validated Kubernetes manifest and Helm chart for multi-tenant TeaAgent deployment; test with simulated load | L | M | OPS-06, MA-05 | — | — | ✅ |

**Cluster 4 total:** ~29 FTE-days across three phases

---

### Cluster 5 — Conversation UX and Trust (WS1, UX)

These items convert TeaAgent's internal governance depth into user-visible
confidence. A daily user should understand what happened without reading JSONL,
source code, or internal call IDs.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **UX-01** | Consolidate chat surfaces | Ensure CLI, TUI, and controller share command definitions or an explicit translation layer; end the triple-path divergence | M | H | ENG-06 | ✅ | — | — |
| **UX-02** | Readable approval selectors | Replace call-ID-first approval UX with numbered pending actions; show tool name, reason, path summary, risk class, expiry | M | H | OPS-03 | ✅ | — | — |
| **UX-03** | Progress summaries for long runs | TUI/CLI shows current phase, last tool called, next intended action, elapsed time, and budget remaining; not opt-in | M | H | ENG-07 | ✅ | — | — |
| **UX-04** | Background/resume vocabulary repair | Distinguish checkpointed suspension, resumable session, and live background execution in docs and UI | S | M | None | ✅ | — | — |
| **UX-05** | Conversation UX acceptance tests | Tests cover approval display, cost display, compact/resume wording, receipt generation, and progress summary | M | M | UX-01 to UX-04 | ✅ | — | — |
| **UX-06** | TUI JSON-default repair | Change TUI default output from raw JSON to human-readable text for TTY sessions; preserve JSON as `--json` flag | M | H | ENG-07 | — | ✅ | — |
| **UX-07** | Approval UX polish | Add keyboard shortcut approval, batch approval for related items, and reason display on approval request | M | M | UX-02 | — | ✅ | — |

**Cluster 5 total:** ~22 FTE-days across two phases

---

### Cluster 6 — Integration and Extension Boundaries (WS5, EXT)

These items stabilize the extension surface so that plugin authors, IDE adapters,
and future remote servers can build on TeaAgent without duplicating runner policy.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **EXT-01** | ApprovalBackend abstract base | Define `ApprovalBackend` ABC; inject into runner; local default is current in-process implementation | M | H | ENG-06 | — | ✅ | — |
| **EXT-02** | Unify plugin discovery with tool registry | Plugin-provided tools must pass schema validation, annotation, approval, and audit requirements at registration | M | H | ENG-07 | — | ✅ | — |
| **EXT-03** | AbstractStore for runs/approvals/memory | Define storage interfaces for runs, approvals, memory, and audit; local defaults remain simple files | L | H | ENG-06 | — | ✅ | — |
| **EXT-04** | Enforce CommandExecutor interface | All shell-execution paths use a single `CommandExecutor` interface; prevents policy bypass via direct subprocess | M | H | None | — | ✅ | — |
| **EXT-05** | Extensible LLM provider factory | Expose a clean `LLMProviderFactory` with first-class registration; remove ad-hoc provider string matching | S | M | None | — | ✅ | — |
| **EXT-06** | Policy and tool authoring examples | Add worked examples for custom approval policies, tool authors, and plugin manifests to `docs/` | M | M | EXT-01 to EXT-05 | — | — | ✅ |
| **EXT-07** | IDE integration design | Design document for VS Code / JetBrains extension entry points; defer implementation until WS5 is stable | M | M | EXT-01 to EXT-04 | — | — | ✅ |

**Cluster 6 total:** ~26 FTE-days across two phases

---

### Cluster 7 — Performance Optimization (PERF)

These items address identified scalability ceilings. They are not urgent unless
TeaAgent hits the ceilings in production. Defer unless a bottleneck is reported.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **PERF-01** | Chain hash optimization | Cache SHA-256 incremental state instead of re-hashing full chain on every append; benchmark on 50k-event logs | M | M | ENG-03 | — | — | ✅ |
| **PERF-02** | Batch JSONL writes | Buffer audit events and flush as a batch; reduces fsync overhead on high-throughput runs | M | M | ENG-03 | — | — | ✅ |
| **PERF-03** | TraceRecorder O(n) fix | Replace O(n) linear trace scan with an indexed structure; profile before and after | M | M | None | — | — | ✅ |

**Cluster 7 total:** ~12 FTE-days in Phase 3

---

### Cluster 8 — Documentation Governance (WS0, DOC)

These items keep the documentation system honest and maintainable.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **DOC-01** | Validate docs consistency CI gate | Ensure `scripts/validate_docs_consistency.py` runs in CI and fails the build on stale front-door links | S | M | None | ✅ | — | — |
| **DOC-02** | Docs front-door index refresh | Update `docs/INDEX.md` to point to the June 6 package as current analysis; retire June 1 docs from primary navigation | S | M | WS0-001 | ✅ | — | — |
| **DOC-03** | Persona-specific onboarding guides | Write getting-started guides for: solo CLI user, team operator, tool/plugin author, security reviewer | L | H | WS0-003, UX-01 | — | ✅ | — |
| **DOC-04** | "When not to use TeaAgent" page | Publish honest non-fit scenarios: IDE-first teams, hosted delegation needs, zero-config beginners | S | M | DOC-03 | — | ✅ | — |

**Cluster 8 total:** ~12 FTE-days across two phases

---

### Cluster 9 — Market and Competitive Positioning (WS6, MKT)

These items should not be started until the trust gates in Clusters 1–4 are
passed. Marketing claims backed by verified product behavior are durable.
Marketing claims that precede the behavior damage credibility.

| Item ID | Title | What | Effort | Impact | Dependencies | 3M | 6M | 12M |
|---------|-------|------|--------|--------|--------------|----|----|-----|
| **MKT-01** | Governance-first README | Add a "why TeaAgent" section that explains local-first governed harness positioning; cite receipts and audit demos | M | H | OPS-01, RISK-06 | — | ✅ | — |
| **MKT-02** | Trust and audit whitepaper | Document exact guarantees, non-goals, failure behavior, and verification commands for security-minded buyers | L | H | RISK-05, RISK-06, OPS-05 | — | — | ✅ |
| **MKT-03** | Quarterly competitor refresh process | Define and schedule a process to refresh the competitor matrix from official upstream sources; timestamp volatile claims | S | M | WS0-002 | — | ✅ | — |
| **MKT-04** | Case study: governed agent workflow | Document one real governance-first use case end-to-end with receipt screenshots and audit walk-through | M | H | OPS-01, UX-01 | — | — | ✅ |
| **MKT-05** | Ecosystem integrations | Add MCP server examples, Slack notification plugin, and GitHub PR hook to demonstrate extensibility | L | M | EXT-01 to EXT-05 | — | — | ✅ |

**Cluster 9 total:** ~25 FTE-days in Phases 2–3

---

### Full Catalog Summary

| Cluster | Items | Total Effort (days) | Horizon |
|---------|-------|---------------------|---------|
| 0 — Claim Hygiene | 4 | 3 | Phase 1 |
| 1 — Engineering Health | 10 | 45 | Phases 1–3 |
| 2 — Security & Trust | 10 | 32 | Phases 1–2 |
| 3 — Multi-Agent Safety | 7 | 22 | Phases 1–2 |
| 4 — Observability | 9 | 29 | Phases 1–3 |
| 5 — Conversation UX | 7 | 22 | Phases 1–2 |
| 6 — Integration/Extension | 7 | 26 | Phases 2–3 |
| 7 — Performance | 3 | 12 | Phase 3 |
| 8 — Documentation | 4 | 12 | Phases 1–2 |
| 9 — Market/Competitive | 5 | 25 | Phases 2–3 |
| **Total** | **66** | **~228** | — |

At 1 FTE: ~45 weeks. At 2 FTE running parallel tracks: ~24 weeks. At 3 FTE: ~17 weeks.

---

<a name="part-2"></a>
## Part 2: Phase 1–4 Detailed Breakdown

---

### Phase 1 — Trust Tier (Weeks 1–12, ~36 FTE-days)

**Goal:** Make every existing trust claim boringly true. Nothing shipped in this
phase should be reversible or require follow-on apology. Exit only when all trust
gates pass.

**Exit gate for Phase 2:** Claim hygiene, compliance audit mode, multi-agent
safety minimums, run receipt, and conversation UX foundations are all verified
and tested.

---

#### Week 1–2: Foundation (Cluster 0 + High-Priority ENG + RISK)

| Item | Effort | Owner Track |
|------|--------|-------------|
| WS0-001 Define claim classes | XS | Documentation |
| WS0-002 Supersede stale competitor facts | XS | Documentation |
| WS0-003 Subsystem maturity map | S | Documentation |
| WS0-004 Release checklist claim guard | XS | Documentation |
| DOC-01 Validate docs consistency CI gate | S | Engineering |
| DOC-02 Docs front-door index refresh | S | Documentation |
| ENG-01 Fix ApprovalPolicy thread leak | S | Engineering |
| RISK-01 HMAC key save error handling | XS | Engineering |
| RISK-02 Cost rates for offline providers | XS | Engineering |

**FTE-days:** ~8 days  
**Blockers:** None  
**Exit criteria:**  
- Claim classes defined in governance doc; frontmatter added to all analysis docs
- CI blocks on stale front-door links
- `ApprovalPolicy.__del__` added and tested in 3000-test suite run
- HMAC save path logs error; does not silently swallow it
- Fake/ollama/vllm providers have non-zero default cost rates

---

#### Week 3–4: Security Core (RISK-03 to RISK-07 + ENG-02)

| Item | Effort | Owner Track |
|------|--------|-------------|
| RISK-03 Expand path containment checks | M | Security |
| RISK-04 Approval timeout default | S | Security |
| RISK-05 Compliance-mode fatal audit | M | Security |
| RISK-06 Strict audit chain verification | M | Security |
| RISK-07 Approval token exactness tests | S | Security |
| ENG-02 Introduce RunContext dataclass | M | Engineering |

**FTE-days:** ~12 days  
**Blockers:** RISK-01 (HMAC trust foundation must be in place)  
**Exit criteria:**  
- `tests/test_security_fixes.py` covers all six RISK items
- RunContext is a typed dataclass; mutable context dict is deprecated but not yet
  fully migrated (migration continues in weeks 5–8)
- Compliance mode halts on disk write failure; tested in CI
- Strict audit chain rejects legacy reset lines; compatibility flag required

---

#### Week 5–6: Observability Foundation (OPS-01 to OPS-08 + ENG-03 to ENG-05)

| Item | Effort | Owner Track |
|------|--------|-------------|
| OPS-07 Structured JSON logging | M | Engineering |
| OPS-08 Rotating log files | S | Engineering |
| OPS-01 Run receipt MVP | M | Engineering |
| OPS-02 LLM and tool latency metrics | M | Engineering |
| OPS-03 Approval queue age and depth | M | Engineering |
| OPS-04 Audit tail command | S | Engineering |
| OPS-05 Audit durability health display | S | Engineering |
| ENG-03 Bound AuditLogger events | S | Engineering |
| ENG-04 Paginate runs-index.jsonl | S | Engineering |
| ENG-05 Cap approval-queue global dict | S | Engineering |

**FTE-days:** ~14 days  
**Blockers:** RISK-05 and RISK-06 (audit durability must be real before we expose it)  
**Exit criteria:**  
- `teaagent run` emits a receipt after every run; receipt includes all required fields
- `teaagent audit tail` shows recent events in human-readable form
- `teaagent approvals` shows pending items with age and expiry
- Memory growth test: 100-run daemon loop shows stable memory (no unbounded growth)
- All logs structured JSON; no bare `print()` or unformatted `logging.info()` in hot paths

---

#### Week 7–8: Multi-Agent Safety Minimums (MA-01 to MA-04 + UX-01 to UX-04)

| Item | Effort | Owner Track |
|------|--------|-------------|
| MA-01 Make shared isolation explicit | S | Engineering |
| MA-02 Batch-level timeout + cancellation | M | Engineering |
| MA-03 Propagate budget envelopes | M | Engineering |
| MA-04 Enforce depth + concurrency | M | Engineering |
| UX-01 Consolidate chat surfaces | M | UX |
| UX-02 Readable approval selectors | M | UX |
| UX-03 Progress summaries | M | UX |
| UX-04 Background/resume vocabulary | S | UX |

**FTE-days:** ~16 days  
**Blockers:** ENG-02 (RunContext required for budget propagation); OPS-03 (approval display required for UX-02)  
**Exit criteria:**  
- Default subagent isolation is `isolated`; `isolation=shared` requires explicit flag
- Batch deadline tested: timeout returns partial results, does not hang
- Budget envelopes propagated in test with three-level agent tree
- `tests/test_subagent_batch.py` and `tests/test_subagent_isolation.py` pass
- TUI and CLI use same command definitions or documented translation layer
- Approval display shows numbered actions, not raw call IDs

---

#### Week 9–10: UX Completion + Conversation Trust (UX-05 + ENG-05 continuation)

| Item | Effort | Owner Track |
|------|--------|-------------|
| UX-05 Conversation UX acceptance tests | M | QA |
| MA completion and regression guard | S | Engineering |
| Receipt integration tests | M | QA |

**FTE-days:** ~7 days  
**Blockers:** All UX-01 to UX-04 items  
**Exit criteria:**  
- `tests/acceptance/` covers approval display, cost display, compact/resume,
  receipt generation, and progress summary
- Zero UX regressions on existing chat and TUI flows

---

#### Week 11–12: Phase 1 Hardening and Docs

| Item | Effort | Owner Track |
|------|--------|-------------|
| Phase 1 regression guard pass | M | Engineering |
| `docs/daily-driver-current-status.md` refresh | S | Documentation |
| Threat model update | M | Security |
| Phase 2 entry criteria validation | S | All |

**FTE-days:** ~7 days  
**Blockers:** All above items  
**Exit criteria (Phase 1 complete):**  
- All P0 and P1 findings from June 6 critical review package are closed
- Zero security findings in threat model without linked mitigations
- 100% test coverage on all security and trust items (RISK-01 to RISK-07)
- All June 6 workstream items for WS0, WS1, WS3, WS4 have passing acceptance gates
- `validate_docs_consistency.py` passes with no errors
- Subsystem maturity map is accurate and publicly linked from `docs/INDEX.md`
- Run receipt emitted after every run; visible without reading JSONL

**Phase 1 total:** ~64 FTE-days ≈ 13 FTE-weeks  
For a 2-person team working parallel tracks: **7 calendar weeks**  
For a 3-person team: **5 calendar weeks**

---

### Phase 2 — Extensibility Tier (Weeks 13–24, ~60 FTE-days)

**Goal:** Stabilize the extension surface. Plugin authors, test authors, and future
IDE adapters can build on a single run contract. Remote multi-agent safety is
gated and documented.

---

#### Week 13–16: Run Service and Storage Contracts (ENG-06, ENG-07, EXT-01 to EXT-05)

| Item | Effort | Owner Track |
|------|--------|-------------|
| ENG-06 Define AgentService run boundary | L | Architecture |
| ENG-07 Stable event stream contract | M | Architecture |
| EXT-01 ApprovalBackend abstract base | M | Architecture |
| EXT-02 Unify plugin discovery with tool registry | M | Architecture |
| EXT-03 AbstractStore for runs/approvals/memory | L | Architecture |
| EXT-04 Enforce CommandExecutor interface | M | Security |
| EXT-05 Extensible LLM provider factory | S | Engineering |

**FTE-days:** ~22 days  
**Blockers:** ENG-02 (RunContext), OPS-01 (receipt as an anchoring artifact)  
**Exit criteria:**  
- `AgentService` class passes mypy; CLI, TUI, and tests use it exclusively
- Event stream interface has at least one test subscriber (receipt generator)
- Plugin tool registration enforces schema, annotations, and audit requirements
- CommandExecutor interface covers all shell-execution paths; no direct `subprocess.run()` in hot paths
- Storage interfaces defined; local default unchanged

---

#### Week 17–20: Multi-Agent Durability + UX Polish (MA-05 to MA-07, UX-06, UX-07)

| Item | Effort | Owner Track |
|------|--------|-------------|
| MA-05 Durable approval queue abstraction | M | Engineering |
| MA-06 Orchestration unification design | M | Architecture |
| MA-07 Subagent failure semantics | M | Engineering |
| UX-06 TUI JSON-default repair | M | UX |
| UX-07 Approval UX polish | M | UX |
| RISK-08 Cost state taxonomy | M | Product |
| RISK-09 Prompt injection boundary docs + tests | M | Security |
| RISK-10 VFS sandbox integration | L | Security |

**FTE-days:** ~22 days  
**Blockers:** MA-05 requires RISK-05 (compliance mode); UX-06 requires ENG-07 (event stream)  
**Exit criteria:**  
- File-backed approval queue survives process restart; tested
- One canonical orchestration manager; `SwarmManager` compatibility path documented
- Child failure propagation tested: hard stop, partial result, human escalation
- TUI shows human-readable text by default on TTY; `--json` flag preserved
- Prompt injection boundary documented and tested for tool outputs, skills, memory, repo docs

---

#### Week 21–24: Observability Maturity + Doc + Market Entry (OPS-06, ENG-08, DOC-03, DOC-04, MKT-01, MKT-03)

| Item | Effort | Owner Track |
|------|--------|-------------|
| OPS-06 Config lint | M | Engineering |
| ENG-08 1000-agent scale test suite | L | QA |
| DOC-03 Persona-specific onboarding guides | L | Documentation |
| DOC-04 "When not to use TeaAgent" page | S | Documentation |
| MKT-01 Governance-first README | M | Product |
| MKT-03 Quarterly competitor refresh process | S | Product |

**FTE-days:** ~16 days  
**Blockers:** WS0 items, OPS-01 (receipt), RISK-05/06 (trust gates), UX-01 (surface consolidation)  
**Exit criteria:**  
- `teaagent lint --config` warns on unsafe combinations
- 1000-agent test suite runs without memory leak or thread leak
- Three persona guides published and linked from `docs/INDEX.md`
- README governance-first section cites verifiable product behavior, not aspirational claims
- Competitor matrix refreshed from official docs with timestamps

**Phase 2 total:** ~60 FTE-days ≈ 12 FTE-weeks  
For a 2-person team: **6 calendar weeks**  
For a 3-person team: **4 calendar weeks**

---

### Phase 3 — Performance and Scale (Weeks 25–36, ~40 FTE-days)

**Goal:** Address scalability ceilings before they manifest as production
incidents. Defer until a bottleneck is actually reported, but do not defer past
12M horizon.

| Item | Effort | Track |
|------|--------|-------|
| ENG-09 Async/await refactor design | M | Architecture |
| PERF-01 Chain hash optimization | M | Engineering |
| PERF-02 Batch JSONL writes | M | Engineering |
| PERF-03 TraceRecorder O(n) fix | M | Engineering |
| ENG-10 Async/await implementation | XL | Engineering |
| OPS-09 Kubernetes reference deployment | L | Operations |
| EXT-06 Policy and tool authoring examples | M | Documentation |
| EXT-07 IDE integration design | M | Architecture |

**FTE-days:** ~40 days  
**Blockers:** ENG-09 must precede ENG-10; EXT-01 to EXT-05 must precede EXT-07  
**Exit criteria:**  
- Async run loop operational; zero behavioral regressions
- Audit log verified stable at 100k events
- Kubernetes manifest tested with 10-concurrent-user simulated load
- IDE integration design reviewed and approved before implementation begins

**Phase 3 total:** ~40 FTE-days ≈ 8 FTE-weeks  
For a 2-person team: **4 calendar weeks**  
Runs in parallel with Phase 4 marketing work.

---

### Phase 4 — Market and Developer Relations (Parallel with Phase 3, Weeks 25–36)

**Goal:** Convert Phase 1 and 2 product proof into market positioning. Nothing in
this phase should be started until Phase 1 trust gates are closed.

| Item | Effort | Track |
|------|--------|-------|
| MKT-02 Trust and audit whitepaper | L | Product |
| MKT-04 Case study: governed agent workflow | M | Product |
| MKT-05 Ecosystem integrations | L | Engineering |

**FTE-days:** ~22 days  
**Blockers:** RISK-05/06 (audit trust gates for whitepaper); OPS-01 (receipt for case study)  
**Exit criteria:**  
- Whitepaper reviewed by one external security reviewer
- Case study published with receipt screenshots and audit walk-through video
- At minimum one MCP server example and one plugin example in `examples/`

**Phase 4 total:** ~22 FTE-days — can run in parallel with Phase 3

---

<a name="part-3"></a>
## Part 3: Resource Planning and Tradeoff Matrix

### Effort summary by phase

| Phase | Name | FTE-days | At 2 FTE | At 3 FTE |
|-------|------|----------|----------|----------|
| 1 | Trust Tier | 64 | 7 weeks | 5 weeks |
| 2 | Extensibility Tier | 60 | 6 weeks | 4 weeks |
| 3 | Performance and Scale | 40 | 4 weeks | 3 weeks |
| 4 | Market and Dev Relations | 22 | parallel with 3 | parallel with 3 |
| **Total (sequential)** | — | **186** | **17 weeks** | **12 weeks** |

These are engineering days, not calendar days. They assume no context-switching
overhead, no onboarding time for new contributors, and no unplanned incidents.
Add 25–35% buffer for realistic planning.

---

### Scenario 1: 12-Week Sprint — Trust Tier Only (1–2 FTE)

**Do:** All of Phase 1 (Clusters 0, 1 partial, 2, 3 minimums, 4 foundation, 5, 8 partial)

**Skip:** Phase 2 extensibility; Phase 3 performance; Phase 4 market

**Outcome:**
- All six RISK trust items verified and tested
- Run receipt emitted after every run
- Approval selectors are human-readable
- Multi-agent safety minimums in place (isolation, timeout, budget propagation)
- Structured logs with rotation
- Subsystem maturity map published
- CI blocks on stale docs

**Market impact:** Can truthfully say "every trust claim is tested and verifiable."
Cannot yet say "extensible by third parties" or "enterprise deployment" or "remote agents."

**Risk of this scenario:**
- Competitive gap with Claude Code, OpenCode, and Kiro grows during 12-week focus
- No new visible features shipped; team morale risk if the work is invisible
- Phase 2 extensibility deferred; plugin authors waiting

**Recommended for:** A solo or 2-person team that needs to make trust claims
credible before approaching enterprise buyers or external contributors.

---

### Scenario 2: 24-Week Sprint — Trust Tier + Extensibility (2–3 FTE)

**Do:** Phase 1 (weeks 1–12) + Phase 2 (weeks 13–24)

**Skip:** Phase 3 performance (defer to 12M); Phase 4 market runs in parallel
starting week 17

**Outcome:**
- All Phase 1 outcomes, plus:
- `AgentService` / `EventStream` / `ApprovalBackend` / `AbstractStore` contracts stable
- Plugin authors can build without duplicating runner policy
- TUI shows human-readable output by default
- Durable approval queue (file-backed, survives restart)
- Governance-first README published
- Competitor matrix refreshed and timestamped
- Persona-specific onboarding guides for four audiences

**Market impact:** Can market as "extensible governed harness." Third-party plugin
authors can build. Security-minded buyers can read a maturity map and test commands.

**Risk of this scenario:**
- 24 weeks is a long runway without a customer milestone
- Async/performance gap widens relative to OpenCode during deferral
- IDE integration design deferred; no VS Code entry point

**Recommended for:** A 2–3 person squad with 6 months of runway. This is the
**primary recommended scenario**. It locks in the governance moat before expanding
the feature surface, and does market work in parallel in the back half.

---

### Scenario 3: 36-Week Sprint — All Three Tiers (3 FTE)

**Do:** Phase 1 + Phase 2 + Phase 3 (sequential) + Phase 4 (parallel with Phase 3)

**Skip:** Nothing from the 30+ item catalog

**Outcome:**
- All Phase 1 and 2 outcomes, plus:
- Async-first run loop
- Kubernetes reference deployment
- Trust and audit whitepaper (reviewed externally)
- Case study with receipt walk-through
- Ecosystem integrations (MCP server, plugin examples)
- IDE integration design (not yet implemented)
- 1000-agent scale tested

**Market impact:** Production-ready, scalable, extensible. Can make enterprise
deployment and scale claims backed by verified evidence.

**Risk of this scenario:**
- Requires sustained 3 FTE for 9 months — high organizational commitment
- Async refactor is the highest-risk item (XL, 2–4 weeks, potential for regressions)
- If async refactor slips, Phase 3 slides and blocks Phase 4 market claims

**Recommended for:** A funded team with a clear enterprise buyer pipeline that
needs to ship all tiers within a product year.

---

### Recommended Scenario: Scenario 2 (24 weeks, 2–3 FTE)

**Why:**
1. The governance moat is the real competitive differentiator. Lock it in before
   expanding breadth.
2. Extensibility (Phase 2) is required before external contributors can build
   without duplicating policy — this is a network effect. Get it early.
3. Performance (Phase 3) is a solve-when-bottlenecked problem. Not needed until
   a user reports hitting the ceiling.
4. Market work (Phase 4) can and should run in parallel with Phase 3 from week 17.
   Do not wait for all engineering to ship before publishing positioning.

**Modified Scenario 2 timeline:**

| Weeks | Work |
|-------|------|
| 1–12 | Phase 1: Trust Tier (2 parallel tracks: engineering + security/docs) |
| 13–16 | Phase 2 start: AgentService, EventStream, storage contracts |
| 17–20 | Phase 2 mid: Multi-agent durability, UX polish |
| 17–24 | Phase 4 begins in parallel: README, competitor refresh, personas |
| 21–24 | Phase 2 close: Observability maturity, scale tests, docs |
| 25–36 | Phase 3: Performance + Kubernetes + whitepaper (Phase 4 continues) |

---

### FTE Allocation Guide

**Track A — Engineering/Architecture:**
Primary owner of Clusters 1, 3, 4, 6, 7. This track owns the run loop, storage,
multi-agent safety, and integration contracts. Requires senior-level Python and
systems knowledge.

**Track B — Security/QA:**
Primary owner of Clusters 2 (RISK items) and all acceptance test expansion.
Works in parallel with Track A from day 1 on security items; hands over to QA
role in weeks 9–24. Requires security engineering background.

**Track C — Product/Docs (part-time, ~0.5 FTE):**
Primary owner of Clusters 0, 8, 9. Can start from week 1 on claim hygiene;
accelerates in weeks 17–24 as trust gates pass and market work begins. Requires
strong technical writing and competitive research skills.

---

### What Gets Cut If Resources Are Constrained

If resources are below 2 FTE, use this priority ordering:

1. **Never cut:** RISK-01 to RISK-07, ENG-01, MA-01 to MA-04, OPS-01. These are
   the trust floor. Cutting them means claims are unverifiable.

2. **Cut first:** PERF-01 to PERF-03 (unless hitting bottleneck), EXT-07 IDE
   design, MKT-05 ecosystem integrations, OPS-09 Kubernetes.

3. **Cut if needed:** ENG-08 1000-agent tests (keep manual benchmark), DOC-04
   "when not to use" page, MKT-04 case study (produce a shorter blog post instead).

4. **Never cut without replacement:** DOC-01 (CI gate on docs consistency) — if
   this is cut, assign a human reviewer to catch stale claims before publication.

---

<a name="part-4"></a>
## Part 4: Decision Rules for Item Selection

### Rule 1: Must-haves — No Negotiation

These items have no optional path. Skipping them means a trust claim is false or
a bug manifests in production. They are not features; they are integrity maintenance.

| Must-have | Why non-negotiable |
|-----------|-------------------|
| RISK-01 HMAC error handling | Silent `except OSError: pass` means audit key loss is invisible. HMAC integrity is the foundation of the audit chain. |
| RISK-02 Cost rates for offline providers | Zero default rates mean the budget guard does not work for teams using fake/ollama/vllm. |
| RISK-03 Path containment | An approval system that does not check path-like arguments cannot claim to protect the workspace. |
| RISK-04 Approval timeout | Stale approvals that never expire create a replay window. |
| RISK-05 Compliance-mode fatal audit | Silent audit disk failures in a system claiming "audit trail integrity" are a contradiction. |
| RISK-06 Strict chain verification | Legacy reset lines in the audit chain weaken tamper evidence. |
| ENG-01 Thread leak | Hundreds of leaked executor threads eventually exhaust OS resources and silently degrade performance. |
| MA-01 Isolation explicit | Shared write isolation by default means multi-agent runs can corrupt each other silently. |
| MA-02 Batch timeout | A batch that cannot be cancelled is a denial-of-service vector. |
| MA-03 Budget propagation | Children that do not inherit parent budget caps can spend without limit. |
| OPS-01 Run receipt | "Verifiable governance" requires the verification artifact to exist by default. |

---

### Rule 2: If Doing X, Must Also Do Y

These coupling rules prevent half-implementations that create the illusion of
safety without the substance.

| If you ship... | You must also ship... | Why |
|----------------|----------------------|-----|
| Async/await refactor (ENG-10) | 1000-agent test suite (ENG-08) | Async introduces new race conditions; the scale test is the regression guard |
| Extensibility contracts (EXT-01 to EXT-05) | Kubernetes reference deployment (OPS-09) | Extension points are only credible if a real multi-tenant deployment has validated them |
| Market work (MKT-01/02) | Docs examples (DOC-03/04) | Governance claims without worked examples are marketing, not proof |
| Compliance-mode audit (RISK-05) | Audit durability health display (OPS-05) | Operators need to see compliance mode status, not just know it exists |
| Durable approval queue (MA-05) | Subagent failure semantics (MA-07) | Durability without defined failure behavior leaves operators without a recovery path |
| Plugin discovery unification (EXT-02) | CommandExecutor interface (EXT-04) | Plugin tools that can bypass CommandExecutor inherit no shell policy governance |
| Prompt injection boundary tests (RISK-09) | VFS sandbox integration (RISK-10) | Documentation without sandbox enforcement is a partial defense |

---

### Rule 3: Defer If Not Blocking Revenue

These items are valuable but do not block the next trust claim, the next external
contributor, or the next enterprise conversation.

| Item | Defer until |
|------|-------------|
| PERF-01 Chain hash optimization | Benchmark shows > 500ms for chain verification at scale |
| PERF-02 Batch JSONL writes | Throughput profiling shows fsync as bottleneck |
| PERF-03 TraceRecorder O(n) fix | Profiling shows > 5% of run latency in tracer |
| ENG-09/10 Async refactor | Concurrent-user testing shows synchronous loop as throughput ceiling |
| EXT-07 IDE integration design | Phase 2 extension contracts are stable and used by at least one external plugin |
| OPS-09 Kubernetes | First paying multi-tenant customer or team deployment request |
| MKT-04 Case study | OPS-01 receipt and RISK-06 chain verification are both live and tested |
| MKT-05 Ecosystem integrations | EXT-01 to EXT-05 stable and documented with at least one working plugin |

---

### Rule 4: Quality Gates Before Shipping

These gates must pass before any phase is declared complete. They are not
optional; they are the acceptance definition.

**Phase 1 quality gate:**
- Zero open security findings in the threat model without linked mitigations
- 100% test coverage on all RISK-01 to RISK-07 code paths
- External audit chain integrity confirmed by running `teaagent audit verify` on a
  test log with > 1000 events
- All June 6 critical review WS0, WS1, WS3, WS4 workstream items have verified
  acceptance gates
- Zero regressions in existing acceptance tests (3355+ passing at HEAD)
- `validate_docs_consistency.py` passes with no errors
- Run receipt emitted after every run; no raw JSONL required to understand what happened

**Phase 2 quality gate:**
- `AgentService` passes mypy strict; CLI, TUI, and tests all route through it
- At least one external plugin registered via entry-point and passing the full tool
  governance requirements
- 1000-agent test suite passes without memory or thread growth
- Competitor matrix refreshed from official upstream sources with timestamps
- Persona-specific onboarding guides reviewed by one person from each target audience

**Phase 3 quality gate:**
- Async run loop passes the full 3355+ test suite; zero behavioral regressions
- Audit log stable at 100k events without memory spike or chain verification pause
- Kubernetes manifest tested with 10 concurrent simulated users; zero data corruption

**Phase 4 quality gate:**
- Trust and audit whitepaper reviewed by one external security practitioner
- Case study includes `teaagent audit verify` walk-through with real log output
- All competitive claims in README and whitepaper trace to source-verified evidence
  dated within 30 days of publication

---

### Rule 5: Competitive Claim Hygiene

These rules apply to every external-facing claim regardless of phase.

| Claim type | Rule |
|------------|------|
| Star counts, community size | Do not quote; they change daily. Link to live source only. |
| Competitor feature descriptions | Source from official docs; timestamp the access date |
| "Enterprise-grade audit" | Blocked until Phase 1 trust gate passes |
| "Remote multi-agent" | Blocked until WS2 safety gate passes (MA-01 to MA-07 + MA-05 durability) |
| "Production-safe autonomy" | Blocked until Phase 1 + 2 quality gates pass |
| "Extensible by third parties" | Blocked until EXT-01 to EXT-05 stable and one real external plugin exists |
| "Sandbox isolation" | Blocked until RISK-10 VFS integration is verified |

---

### Rule 6: The Brutally Honest Assessment

- The 30+ FTE-days of Phase 1 alone is a serious quarterly commitment for a 1–2
  person team. It is not a 2-week sprint.
- The async refactor (ENG-09/10) is the highest-risk single item on the roadmap.
  It has XL effort, high regression surface, and no revenue justification until
  concurrent load testing reveals the synchronous ceiling. Do not start it without
  a clear bottleneck signal.
- Documentation work is not optional decoration. Claim hygiene (WS0) is a
  prerequisite for every market claim. Skipping it creates technical debt that
  surfaces as embarrassment in enterprise sales cycles.
- The competitive environment will not pause. OpenCode is growing at ~1K GitHub
  stars/month. Claude Code shipped remote agents and plan/act mode while this
  review was being written. Every week of delay costs a small amount of mindshare
  that is hard to recapture.
- The right response to competitive pressure is not to copy features. It is to
  ship Phase 1 as fast as possible, make the governance claims unambiguously true,
  and then use that truth as the moat. "Our audit trail is testable with one command"
  beats "we also have subagents" every time with a security-minded buyer.

---

<a name="part-5"></a>
## Part 5: Resource and Capability Assessment

### Current State

| Resource | Status |
|----------|--------|
| Engineering FTE | 1 FTE (lead) + part-time support |
| Test suite health | GREEN at HEAD (`4695d46`); 3355 passed, 0 failed on Python 3.12 |
| Documentation health | Active; 435+ markdown files; some stale competitor facts flagged |
| Security posture | Alpha; RISK-01 to RISK-07 open; no external audit completed |
| Performance | Untested at scale; identified ceilings but no production incident yet |
| Extension surface | Promising; no external plugin authors yet |
| Market position | Pre-launch; no public community adoption data available |

---

### Required Capability Map

#### For Phase 1 (Trust Tier)

| Role | Required Skills | Fraction |
|------|----------------|----------|
| Senior Python engineer | Concurrency (`ThreadPoolExecutor`, `ContextVar`), security engineering, audit systems, testing | 1.0 FTE |
| Security reviewer / QA | Python, threat modeling, penetration testing mindset, test authorship | 0.5–1.0 FTE |
| Technical writer / PM | Markdown governance, competitive research, structured writing | 0.25–0.5 FTE |

**Phase 1 minimum viable team:** 1.5 FTE (senior engineer + part-time security/QA)  
**Phase 1 recommended team:** 2.5 FTE (senior engineer + security/QA + technical PM)

#### For Phase 2 (Extensibility Tier)

| Role | Required Skills | Fraction |
|------|----------------|----------|
| Architect / senior engineer | Interface design, ABC patterns, dependency injection, plugin systems | 1.0 FTE |
| Engineer | Feature implementation, integration testing, mypy strict | 1.0 FTE |
| Product / PM | Developer relations, competitive positioning, partner outreach | 0.5 FTE |

**Phase 2 minimum viable team:** 2.0 FTE  
**Phase 2 recommended team:** 2.5 FTE

#### For Phase 3 (Performance and Scale)

| Role | Required Skills | Fraction |
|------|----------------|----------|
| Async Python engineer | `asyncio`, `aiofiles`, concurrency migration, profiling | 1.0 FTE |
| DevOps / SRE | Kubernetes, Helm, load testing, monitoring | 0.5 FTE |
| Engineer | Performance benchmarking, O(n) analysis, JSONL optimization | 0.5 FTE |

**Phase 3 minimum viable team:** 1.5 FTE  
**Phase 3 recommended team:** 2.0 FTE (parallel with Phase 4)

#### For Phase 4 (Market and Developer Relations)

| Role | Required Skills | Fraction |
|------|----------------|----------|
| Technical writer | Security whitepapers, developer guides, technical case studies | 0.5 FTE |
| Developer advocate | Plugin development, ecosystem outreach, demo creation | 0.5 FTE |

**Phase 4 minimum viable team:** 0.5 FTE  
**Phase 4 recommended team:** 1.0 FTE (can run parallel with Phase 3)

---

### Make / Build / Buy Decision Matrix

| Need | Make | Buy | Hire |
|------|------|-----|------|
| Phase 1 engineering | Preferred — domain expertise in governance harness is internal | Risk: onboarding cost + quality variance for security-critical work | Consider if solo timeline > 16 weeks |
| Phase 1 security review | Make first-party tests; Buy external audit | External pentest: $15k–$50k; high ROI for compliance claims | Not needed |
| Phase 2 architecture | Make — interface design must align with existing runner patterns | Risk: external architects won't know the audit chain semantics | Consider if no architect on team |
| Phase 3 async migration | Make — requires deep knowledge of concurrent Python | Risk: contractor without audit-chain knowledge will miss subtle bugs | Consider hiring a concurrent Python specialist |
| Phase 4 market / writing | Buy or part-time — does not require deep code knowledge | Technical writing agencies: $5k–$30k for whitepaper | Consider part-time developer advocate |

---

### Recommended Team Structure

**Scenario 2 (recommended — 24 weeks, 2.5 FTE):**

```
Technical Lead (1.0 FTE, 24 weeks)
  — Owns architecture, security engineering, Phase 1 and 2 critical path
  — Reviews all security and trust items personally

Engineer (1.0 FTE, 24 weeks)
  — Owns observability, UX, extensibility contracts, testing
  — Runs parallel track from week 1

Product / Technical PM (0.5 FTE, 24 weeks)
  — Owns claim hygiene, docs governance, competitive research, onboarding guides
  — Transitions to developer relations in weeks 17–24
```

**Total cost estimate (rough):**
- At $200k/year blended FTE cost (loaded): 2.5 FTE × $200k × 0.5 year = **$250k**
- External security audit: **$25k–$50k** (recommended before any enterprise sales)
- Total 24-week budget: **$275k–$300k**

This is a significant but bounded investment for a software product that
differentiates on governance. The moat is real; the question is whether the team
can be assembled and sustained.

---

### Four Watch Metrics for Phase 1

Track these weekly. If any metric goes in the wrong direction, hold the sprint review
and identify the root cause before proceeding.

| Metric | Baseline (2026-06-06) | Phase 1 Target | Warning Threshold |
|--------|----------------------|---------------|-------------------|
| Open P0 trust findings (RISK-01 to RISK-07) | 7 open | 0 open | > 3 open at week 6 |
| Test suite: pass count | 3355 passing | ≥ 3355 + 150 new | Any regression |
| Docs consistency check | Needs verification | Green in CI | Red for > 2 days |
| Subsystem maturity map items labeled | 0 | 11 labeled | < 6 labeled at week 4 |

---

### Risk Register for This Roadmap

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Async refactor introduces behavioral regressions | High | High | Gate behind ENG-09 design review; do not start ENG-10 without 95%+ test coverage baseline |
| Phase 1 slips past 12 weeks | Medium | Medium | Cut DOC-03/04 and MKT items from Phase 1; never cut RISK or MA items |
| External security audit finds critical issues | Medium | High | Budget 2 weeks after audit to address findings before any public trust claims |
| Competitor ships governance feature first | Low | Medium | Differentiate on verifiability, not feature count; "our audit trail is testable" remains true even if others add audit logs |
| Key contributor leaves mid-Phase 2 | Low | High | Document architecture decisions in ADRs; keep `AgentService` boundary clean so onboarding new contributors is bounded |
| Test suite performance degrades with 150+ new tests | Low | Low | Parallelize with pytest-xdist; split acceptance tests from unit tests in CI matrix |

---

## Appendix: Item ID Quick-Reference

| ID | Title | Phase | Cluster |
|----|-------|-------|---------|
| WS0-001 | Define claim classes | 1 | 0 |
| WS0-002 | Supersede stale competitor facts | 1 | 0 |
| WS0-003 | Subsystem maturity map | 1 | 0 |
| WS0-004 | Release checklist claim guard | 1 | 0 |
| ENG-01 | Fix ApprovalPolicy thread leak | 1 | 1 |
| ENG-02 | Introduce RunContext dataclass | 1 | 1 |
| ENG-03 | Bound AuditLogger in-memory events | 1 | 1 |
| ENG-04 | Paginate runs-index.jsonl | 1 | 1 |
| ENG-05 | Cap approval-queue global dict | 1 | 1 |
| ENG-06 | Define AgentService run boundary | 2 | 1 |
| ENG-07 | Stable event stream contract | 2 | 1 |
| ENG-08 | 1000-agent scale test suite | 2 | 1 |
| ENG-09 | Async/await refactor planning | 3 | 1 |
| ENG-10 | Async/await implementation | 3 | 1 |
| RISK-01 | HMAC key save error handling | 1 | 2 |
| RISK-02 | Cost rates for offline providers | 1 | 2 |
| RISK-03 | Expand path containment checks | 1 | 2 |
| RISK-04 | Approval timeout default | 1 | 2 |
| RISK-05 | Compliance-mode fatal audit | 1 | 2 |
| RISK-06 | Strict audit chain verification | 1 | 2 |
| RISK-07 | Approval token exactness tests | 1 | 2 |
| RISK-08 | Cost state taxonomy | 2 | 2 |
| RISK-09 | Prompt injection boundary docs + tests | 2 | 2 |
| RISK-10 | VFS sandbox integration | 2 | 2 |
| MA-01 | Make shared isolation explicit | 1 | 3 |
| MA-02 | Batch-level timeout + cancellation | 1 | 3 |
| MA-03 | Propagate budget envelopes | 1 | 3 |
| MA-04 | Enforce depth + concurrency | 1 | 3 |
| MA-05 | Durable approval queue abstraction | 2 | 3 |
| MA-06 | Orchestration unification design | 2 | 3 |
| MA-07 | Subagent failure semantics | 2 | 3 |
| OPS-01 | Run receipt MVP | 1 | 4 |
| OPS-02 | LLM and tool latency metrics | 1 | 4 |
| OPS-03 | Approval queue age and depth | 1 | 4 |
| OPS-04 | Audit tail command | 1 | 4 |
| OPS-05 | Audit durability health display | 1 | 4 |
| OPS-06 | Config lint | 2 | 4 |
| OPS-07 | Structured JSON logging | 1 | 4 |
| OPS-08 | Rotating log files | 1 | 4 |
| OPS-09 | Kubernetes reference deployment | 3 | 4 |
| UX-01 | Consolidate chat surfaces | 1 | 5 |
| UX-02 | Readable approval selectors | 1 | 5 |
| UX-03 | Progress summaries | 1 | 5 |
| UX-04 | Background/resume vocabulary | 1 | 5 |
| UX-05 | Conversation UX acceptance tests | 1 | 5 |
| UX-06 | TUI JSON-default repair | 2 | 5 |
| UX-07 | Approval UX polish | 2 | 5 |
| EXT-01 | ApprovalBackend abstract base | 2 | 6 |
| EXT-02 | Unify plugin discovery | 2 | 6 |
| EXT-03 | AbstractStore | 2 | 6 |
| EXT-04 | Enforce CommandExecutor | 2 | 6 |
| EXT-05 | Extensible LLM provider factory | 2 | 6 |
| EXT-06 | Policy and tool authoring examples | 3 | 6 |
| EXT-07 | IDE integration design | 3 | 6 |
| PERF-01 | Chain hash optimization | 3 | 7 |
| PERF-02 | Batch JSONL writes | 3 | 7 |
| PERF-03 | TraceRecorder O(n) fix | 3 | 7 |
| DOC-01 | Validate docs consistency CI gate | 1 | 8 |
| DOC-02 | Docs front-door index refresh | 1 | 8 |
| DOC-03 | Persona-specific onboarding guides | 2 | 8 |
| DOC-04 | "When not to use TeaAgent" page | 2 | 8 |
| MKT-01 | Governance-first README | 2 | 9 |
| MKT-02 | Trust and audit whitepaper | 3 | 9 |
| MKT-03 | Quarterly competitor refresh process | 2 | 9 |
| MKT-04 | Case study: governed agent workflow | 3 | 9 |
| MKT-05 | Ecosystem integrations | 3 | 9 |

**Total items: 66**  
**Total estimated FTE-days: ~228**  
**Recommended delivery: Scenario 2 — 24 weeks at 2.5 FTE**

---

*Document class: Plan and workstream decomposition. Dated 2026-06-06. Refresh
effort estimates after first sprint retrospective. Refresh competitive claims from
official sources before any public use.*
