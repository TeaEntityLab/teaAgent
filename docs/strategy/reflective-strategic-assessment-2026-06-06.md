# Reflective Strategic Assessment — TeaAgent
# 2026-06-06

> **Supersession note, 2026-06-07:** This file contains volatile facts
> (star counts, pricing, model availability, adoption claims, or status claims)
> that may be stale. For current competitive positioning and claim hygiene, see
> [competitive-claim-audit-2026-06-06.md](../analysis/competitive-claim-audit-2026-06-06.md).
> For current roadmap status, see [roadmap-status.md](../roadmap-status.md).

> **Document class:** Dated strategic synthesis.
>
> **Scope:** TeaAgent at commit `ad5e2d7`, incorporating the full June 6, 2026
> multi-angle critical review package, competitor source checks dated 2026-06-06,
> and 626 commits of repository evidence.
>
> **Audience:** Founders, engineering leads, and external advisors evaluating
> TeaAgent's market position, product maturity, and investment worthiness.
>
> **Honest header:** This document is a strategy consultant's synthesis of
> a codebase, not a market study with primary data. Where claims are inferences
> or bounded extrapolations from code evidence, they are marked as such.
> Where they are direct code evidence, file:line citations are provided.
> Treat all competitor claims as valid only on 2026-06-06 and refresh before
> using in external-facing materials.

---

## Table of Contents

1. [Executive Summary](#part-1-executive-summary)
2. [Critical Reflection Framework](#part-2-critical-reflection-framework)
3. [The Five Critical Truths](#part-3-the-five-critical-truths)
4. [Competitive Positioning Map](#part-4-competitive-positioning-map)
5. [Work Direction with Effort/Impact](#part-5-work-direction-with-effortimpact)
6. [Decision Log](#part-6-decision-log)
7. [Three-Year Vision](#part-7-three-year-vision)

---

# Part 1: Executive Summary

## 1.1 What Is TeaAgent?

TeaAgent is a **governance-first, local-first, multi-provider AI agent harness**
for developer teams that cannot afford to deploy an ungoverned autonomous agent
into sensitive workflows. It is not primarily a coding assistant, a chat UI, or a
cloud agent platform. Its core value proposition is a five-loop governance system
that wraps any LLM provider — Claude, GPT, Gemini, Ollama, and 10 others — with
enforceable constraints that competitors either lack entirely or treat as optional
UI elements.

**Mission (stated):** Make autonomous agent work safe for teams that care about
auditability, cost discipline, and correctness.

**Mission (observed from code):** Build a harness where tool execution is always
logged, always bounded by budget, always subject to human approval at configurable
granularity, and always reversible via a per-run undo journal.

### Capability Summary (HEAD `ad5e2d7`, `pyproject.toml v0.1.0`)

| Layer | Status | Code anchor |
|-------|--------|-------------|
| Core agent run loop (Strategy + Decide/Execute) | Stable | `runner/_core.py:801` |
| ToolRegistry with schema validation and security-tier annotations | Stable | `tools.py:50` |
| Permission modes (5 levels: read-only → danger-full-access) | Stable | `policy.py`, `permission_matrix.py` |
| Append-only JSONL audit log with SHA-256 hash-chain | Stable | `audit.py:111`, `audit_chain.py:57` |
| Hard cost cap (`--max-estimated-cost-cents`) | Stable | `runner/_core.py`, budget enforcement |
| Per-run HMAC integrity on audit records | Stable | `audit_chain.py:72-78` |
| Run undo journal | Stable | `test_run_undo_acceptance_flow.py` |
| Plan-before-write enforcement (`PlanContract`) | Stable | `tests/test_tranche_b_governance.py` |
| Local subagent spawning (single + batch) | Beta | `subagents/_manager.py:82` |
| SwarmManager (tournament-style multi-agent) | Beta | `swarm.py:532` |
| TUI (interactive terminal UI) | Beta | `tui/__init__.py` |
| MCP server + client (JSON-RPC 2.0) | Beta | `mcp_server.py`, `mcp_http/` |
| WASM skill sandboxing | Beta | `wasm-skill-ci.md`, `sandbox wasm-contract` |
| VS Code MCP extension | Beta | `docs/architecture/` |
| Managed runtime / cloud control plane | Alpha / Stub | `managed_runtime.py:64` |
| SOC 2 certification | Not present | — |
| External community adoption | Zero | — |

### Maturity Level (Honest Assessment)

`pyproject.toml` declares `Development Status :: 3 - Alpha`. This is accurate. The
core governance loops are test-validated and daily-driver-hardened. The surrounding
surface — TUI, multi-agent, MCP, WASM skills, cloud runtime — ranges from Beta
(tests present, UX rough) to Alpha (code present, not production-hardened).

The project is not "enterprise-ready" in the sense that an enterprise buyer would
use the phrase. It is enterprise-architecturally-shaped — the right primitives are
in place — but it lacks external adoption, SOC 2 certification, an operational
cloud deployment, and the documentation discipline that enterprise procurement
requires.

---

## 1.2 Current State: Strengths, Weaknesses, Risks

### Strengths

**S1 — Governance depth is unique.** No open-source AI agent harness ships a
complete five-loop governance system: tool governance, coding safety,
audit replay, memory hygiene, and swarm hardening. Claude Code has approval UX.
OpenCode has parallel sessions. Neither has a hash-chained audit trail, hard cost
caps, or a compliance export bundle. This is a real technical moat.
Evidence: `docs/analysis/competitive-landscape-and-positioning-2026-06-06.md §3`.

**S2 — Hard cost caps prevent the industry's #1 trust failure.** The
`--max-estimated-cost-cents` budget enforcement (`runner/_core.py`) is a hard
block, not a UI warning. The "Claude Is Dead" thread (841 upvotes, August 2025)
represents exactly the trust failure this prevents. No other open-source agent
ships this. Evidence: `competitive-landscape-and-positioning §3`.

**S3 — Multi-provider flexibility preserves governance under model pluralism.**
14 LLM provider adapters (Claude, GPT, Gemini, Ollama, vllm, OpenRouter, and 8
more) mean governance survives provider changes. Claude Code locks to Claude.
GitHub Copilot locks to GPT. TeaAgent is the only governed harness that doesn't
impose a model monopoly. Evidence: `integration-and-extensibility-critique §1`.

**S4 — Synchronous run loop is highly debuggable.** The single-threaded
`AgentRunner.run()` loop (`runner/_core.py:801`) using a clean Strategy pattern
is fully traceable. The run loop doesn't know how tools work; tools don't know
they're in a run. This separation is architecturally sound and makes the system
understandable. Evidence: `engineering-architecture-critique §1`.

**S5 — Test suite is GREEN at HEAD.** 3355 passed, 0 failed, 22 skipped (verified
at `4695d46`). Coverage gate at 75% (`ci.yml:112`). 88 test files. The suite is
functional and the baseline is solid. Evidence: `teaagent-total-review` memory.

### Weaknesses

**W1 — Community adoption is zero.** OpenCode has 164K GitHub stars. Aider has
~28K. TeaAgent is internal-only. Technical differentiation with zero market
awareness equals zero go-to-market. This is the most urgent gap.

**W2 — UX creates cognitive overload.** JSON is the default output mode. The
canonical REPL (`chat_repl.py:217`) is marked `@deprecated` but is what
`teaagent chat` actually calls. Approval IDs require users to copy/paste UUIDs.
Multiple "chat" entry points (`teaagent chat`, `teaagent tui`, `teaagent daily`)
have divergent semantics. Evidence: `user-experience-and-conversation-patterns §1.2`.

**W3 — Multi-agent is local-process only, not production-safe.** Parent cost
caps are not propagated to children (`subagents/_manager.py` — missing
`max_estimated_cost_cents` propagation). `_approval_queues` is a module-level
in-process singleton (`_approval_queue.py:673`). Swarm and SubagentManager are
independent layers with no shared state. Evidence: `multi-agent-coordination-critique §1.2`.

**W4 — Audit integrity has exploitable weaknesses.** HMAC key save silently fails
(`audit.py:191-214`, `except OSError: pass`). Legacy-format lines silently reset
the hash chain anchor (`audit_chain.py:130-133`). Disk write failures are silent;
the run continues without durable audit records (`audit.py:439-442`).
Evidence: `risk-and-trust-model-critique §3`.

**W5 — Operations is documentation-heavy but execution-sparse.** 65+ configuration
knobs, zero published Docker image, no `pip install teaagent[all]` meta-extra,
no telemetry out-of-the-box. The ops docs are thorough; the deployment automation
is thin. Evidence: `deployment-and-operations-readiness §1-2`.

**W6 — Documentation⇄reality drift is a systemic trust risk.** `acceptance.md`
prose says "3255 passed, 26 failed" while HEAD has 0 failures. Some "Beta" labels
cover shipped features; others cover stubs. External evaluators will find
inconsistencies. Evidence: `teaagent-total-review-2026-06-04` memory, §Meta-finding.

### Risks

**R1 — OpenCode copies the permission matrix.** OpenCode has 164K stars and an
active, capable community. A well-scoped PR adding a permission matrix could ship
in weeks. The moat requires staying 6–12 months ahead, not 1 month.

**R2 — Async refactor gets harder the longer it waits.** The synchronous
`ThreadPoolExecutor` design (`policy.py:70`, `swarm.py:692`) creates unmanaged
thread pools that accumulate in long-lived processes. The async refactor touches
core runner, approval policy, swarm, and TUI. Every new feature added now is
one more file to change in the async refactor.

**R3 — "Beta" labels mask product-readiness claims.** The maturity matrix applies
"Beta" to features ranging from "almost stable" (`runs trace/export/replay`) to
"barely wired" (consensus vote relay, WASM org-signing). An external security
reviewer who reads the Beta claims and then discovers the HMAC key silently fails
will not forgive the discrepancy.

**R4 — No Kubernetes/cloud deployment unblocks zero enterprise conversations.**
The `managed_runtime.py` stub exists. Without a reference deployment, every
enterprise evaluation ends at "we can't run this in our environment." The security
whitepaper is necessary but not sufficient; the deployment artifact must exist.

---

## 1.3 Strategic Question: What Is TeaAgent Trying to Be?

This is the central unresolved question. The repository simultaneously signals:

1. **A thin governed harness** — `teaagent-product-principles-2026-06-04.md` says
   "governance before chat surface or feature platform."
2. **A full-featured agent platform** — 130 modules, WASM skills, OAuth 2.1/DPoP,
   GraphQLite code index, SSH vote relay, federated registry, multi-tenant control
   plane.
3. **An open-source competitor to Claude Code** — feature matrix comparisons,
   TUI, MCP server, subagents, IDE extension.

These are not mutually exclusive, but they require different go-to-market,
different prioritization, and different customer conversations. A team buying a
"governed harness" is a DevSecOps lead at a fintech company. A team buying a
"full-featured agent platform" is a power developer who wants every capability.
These are different buyers with different evaluation criteria.

**This assessment recommends option 1: governed harness.** Not because the
platform vision is wrong, but because the competitive market for option 3
(general-purpose coding agent) is already owned by Claude Code, OpenCode, and
Cursor. The governance lane is uncontested. The moat is real. The TAM is smaller
but fundable.

---

## 1.4 Recommendation: 3-Year Vision + 1-Year Plan

### 3-Year Vision

TeaAgent is the **obvious choice for any organization that needs to answer the
question: "How do we safely run autonomous AI agents?"** It is not trying to win
a feature race with OpenCode or Claude Code. It is defining and owning the
**governed AI agent infrastructure** category — the same way HashiCorp defined
infrastructure-as-code, or the way Grafana defined observability tooling.

**Success flag:** A CISO at a Fortune 500 financial services company can point to
TeaAgent and say: "This is our answer to the AI agent governance problem."

### 1-Year Plan (2026–2027)

| Quarter | Theme | Critical deliverables |
|---------|-------|----------------------|
| Q3 2026 | Trust tier repair | Fix P0 audit integrity bugs; compliance mode; CI doc-truth guard |
| Q3 2026 | Visibility | External README, governance whitepaper, one public blog post |
| Q4 2026 | Operations unblocked | Kubernetes reference deployment; `pip install teaagent[all]`; published Docker image |
| Q4 2026 | UX repair | Run receipt MVP; human-readable approval UX; default `--human` output |
| Q1 2027 | Extensibility | `AgentService` contract; stable event stream; plugin governance |
| Q1 2027 | Market | First external user; first case study; persona-specific onboarding guides |
| Q2 2027 | Multi-agent safety | Budget propagation to children; durable approval queue; swarm/subagent unification |

---

# Part 2: Critical Reflection Framework

> **Purpose:** Honest accounting of what we know, what we assume, and what
> would make each angle wrong. Strategy that doesn't model its own failure modes
> is not strategy — it is optimism with footnotes.

---

## 2.1 Engineering: What Could Break Our Confidence

**What we're confident about:**
The core run loop (`runner/_core.py:801`), ToolRegistry (`tools.py`), and audit
chain (`audit.py`, `audit_chain.py`) are the right architecture. The Strategy
pattern for decision injection is clean. The value-object model (frozen
dataclasses for `AuditEvent`, `RunResult`, `ToolDefinition`) prevents accidental
mutation. The test suite is GREEN with 3355 tests.

**Assumptions made:**
- The synchronous threading model is "good enough" for current TAM.
- `ApprovalPolicy` as a frozen dataclass with an embedded `ThreadPoolExecutor`
  works correctly despite the immutability violation (`policy.py:65-90`).
- Coverage at 75% is sufficient; 16 `omit` entries don't hide critical paths.
- `context` dict side-channels (`_cost_cents`, `_input_tokens` written by
  `ModelDecisionEngine`, read by runner at `runner/_core.py:389`) are safe because
  no one modifies them outside the intended path.

**What would make this assessment wrong:**
- A production daemon runs hundreds of tasks. `ApprovalPolicy` thread pools
  accumulate. Process runs out of OS threads. This has not been tested.
- Python 3.13+ nogil mode breaks the audit chain's implicit GIL assumption
  (`audit.py:381` reads `_prev_hash` without explicit lock).
- A refactor changes who writes to `context['_cost_cents']`. Budget enforcement
  silently breaks. The untyped dict has no compiler enforcement.
- Coverage omit entries hide a real behavior gap in a production path.

**Confidence level:** 7/10. The architecture is sound; the implementation has
known accumulation bugs (TD-01 through TD-12 in engineering-architecture-critique)
that become relevant at scale or in daemon use.

---

## 2.2 Multi-Agent: What We're Confident About vs. Speculation

**What we're confident about:**
Local single-process subagent spawning works and is tested. Permission-mode
capping to `workspace-write` for children is implemented (`_manager.py:230-256`).
JIT approval isolation per child is implemented (`_manager.py:207`, `jit_state=None`).
Lineage tracing to audit log is implemented (`_types.py:28`).

**What is speculation:**
- The "multi-agent" positioning implies distributed, parallel, resilient
  coordination. The current implementation is none of those things. It is local,
  synchronous, and in-process.
- `SwarmManager` and `SubagentManager` are parallel independent layers. There is
  no unified multi-agent substrate.
- "Consensus / multi-sig approvals" appear in the maturity matrix as Beta. The
  underlying SSH vote relay and WAN deployment docs exist. Whether they work under
  real adversarial conditions is unknown.

**Risks of being wrong:**
If we position multi-agent as a production feature to an enterprise buyer who
deploys it and discovers the approval queue dies with the process, we lose the
evaluation. Trust is harder to rebuild than to establish.

**Confidence level:** 5/10. Local delegation is real; distributed multi-agent is
aspirational. This gap must be acknowledged in all positioning.

---

## 2.3 UX: User Research Depth vs. Assumption-Based

**What we know:**
`daily-driver-code-grounded-ux-findings-2026-06-01.md` is a thorough internal
audit grounded in code. `community-agent-pain-points-survey-2026-06-05.md`
synthesizes external signals. The governance model has been designed by
engineering.

**What is assumption-based:**
All UX work is inference from code reading and community signal synthesis, not
from actual TeaAgent user testing. We do not have a single documented TeaAgent
user session from an external user. The assumption that "a security-conscious
engineering lead will see governance value and accept the CLI complexity" is
reasonable but unvalidated.

**What we're missing:**
- No external user study or usability test session for TeaAgent.
- No data on whether the "governance-first" framing resonates with buyers or
  repels them.
- No validated answer to: "Does the median developer read `teaagent --help` output
  and understand what permission modes mean?"

**What would make this assessment wrong:**
The security-conscious persona is real, but they may not be willing to absorb
the current UX complexity. A competitor ships governance with a clean UI and
captures the persona before TeaAgent reaches external beta. The CLI-heavy,
JSON-default output makes TeaAgent a tool for power users, not for
"security-conscious teams" who may not be power users.

**Confidence level:** 4/10. The target persona is sound; whether the product
will reach them before they choose a simpler alternative is genuinely unknown.

---

## 2.4 Competitive: Market Knowledge Gaps and Uncertain Predictions

**What we know:**
Official documentation for all listed competitors was checked on 2026-06-06.
Feature matrices are source-backed. Governance gap relative to TeaAgent is
confirmed by direct feature comparison.

**What we don't know:**
- OpenCode's internal roadmap. Their 164K-star community has the capacity to close
  governance gaps in months.
- Claude Code's unannounced governance roadmap. Anthropic has the brand trust to
  add audit-trail features and immediately make them the default for the Claude
  ecosystem.
- Kiro's enterprise sales traction. If AWS is bundling Kiro into enterprise
  contracts, the procurement channel advantage overwhelms any feature comparison.
- Whether the "governance-first" category is a real purchasing category or a
  narrative we're projecting onto the market.

**Uncertain predictions:**
- "OpenCode will not ship a permission matrix in the next 6 months" — this is a
  guess, not a fact. The community is capable of doing it faster.
- "Fintech and healthcare teams are the right first vertical" — this is a
  hypothesis based on regulatory logic, not based on actual conversations with
  fintech CTOs.

**Confidence level:** 6/10 on feature comparison; 4/10 on market dynamics
predictions.

---

## 2.5 Integration: Extensibility vs. Real-World Complexity

**What we know:**
14 LLM provider adapters exist. MCP server + client are implemented. Plugin
discovery via `importlib.metadata` entry-points is wired. Hook lifecycle has 8
events. These are real, tested extension points.

**What is uncertain:**
- Approval policy is not pluggable (enum, no custom logic path).
- Run storage is not pluggable (no interface to swap).
- Memory catalog is not pluggable.
- Hook lifecycle has no config-based entry points (code-only registration).
- DPoP OAuth refresh is wired but nonfunctional (`FilteredMCPClient.refresh_oauth_token()`
  does nothing with the returned token).

**What would make this assessment wrong:**
A third-party developer tries to build a plugin, discovers that approval policy
is hardcoded, run storage is not injectable, and the hook system requires forking
core code. The "extensible platform" positioning collapses on first external use.

**Confidence level:** 6/10 on current extension points; 3/10 on whether an
external developer can meaningfully extend the system without forking.

---

## 2.6 Risk/Trust: Threat Model Limitations

**What we know:**
The approval model is structurally sound for a single trusted operator using
well-behaved first-party tools. All tool dispatch goes through
`approval_policy.assert_allowed` (`runner/_core.py:585-669`). No unguarded
execution path exists for the primary tool dispatch.

**What we're assuming:**
- Tools are well-behaved and declare their `destructive` annotation accurately.
- The operator is trusted.
- The deployment is single-user.
- The audit log filesystem is not adversarially controlled.

**Known gaps in the threat model:**
- BP-01: Path containment only checks 4 argument keys; custom keys bypass it.
- BP-02: `destructive=False` annotation skips all containment checks.
- AUD-03: A legacy-format line injected into the audit log silently resets the
  chain anchor.
- Multi-tenant is explicitly not supported; if two users share a running agent,
  approvals are not identity-bound.

**What would make this assessment wrong:**
A third-party skill registers a tool with `destructive=False` that writes to
arbitrary paths. The containment check doesn't fire. The audit trail shows a
"read" operation that was actually a write. The security whitepaper says
"path-contained writes" — the claim is technically true for the known 4 keys but
false for custom argument names.

**Confidence level:** 7/10 for single-user trusted-operator deployment; 3/10
for adversarial tool or multi-tenant deployment.

---

## 2.7 Performance: Baseline Measurements and Extrapolation Risks

**What we know:**
Audit `fsync` overhead is 300–400 ms per run (`storage.py:35-36`, confirmed by
roadmap). Swarm heartbeat tick is 30s (`swarm.py:37`). LLM retry max wall time
is ~30s (`llm/_retry.py:17`). No runtime benchmarks exist in the codebase
(`benchmark.py` measures model quality, not latency).

**What we're extrapolating:**
All performance claims are static-analysis inferences. No profiling has been run.
The "300–400 ms fsync overhead" comes from the roadmap, not a measured trace.
LLM latency baselines (1–30s per iteration) are reasonable estimates but
are not measured from actual TeaAgent runs.

**What would make this assessment wrong:**
- The fsync overhead is actually negligible on modern NVMe storage.
- The true bottleneck is token estimation via `len(text)/3.5` character counting,
  which causes premature compaction and additional LLM calls (±30% error,
  `context.py:38-45`).
- The `AuditLogger.events` list memory accumulation
  (`audit.py:123`) causes observable GC pauses in a long-running daemon after
  1000+ events, making the system feel slow in ways that are hard to diagnose.

**Confidence level:** 4/10. No runtime profiling; all claims are estimates.
The system likely performs acceptably for short developer tasks; daemon/automation
use cases are unknown.

---

## 2.8 Operations: Ops Experience Depth, Deployment Readiness

**What we know:**
`docs/ops/deployment-guide.md` is thorough and technically accurate.
`teaagent doctor all` provides a binary go/no-go health check. The configuration
reference documents 65+ settings. The ops documentation is unusually good for
an 0.1.0-alpha.

**What is aspirational:**
- No published Docker image; users must build from an inline `Dockerfile` snippet.
- No Kubernetes manifests.
- No `pip install teaagent[all]` meta-extra.
- No log aggregation integration (ELK, Splunk, Datadog) out of the box.
- No dashboards.
- Audit log growth is unbounded; rotation is manual or via external cron.
- Configuration surface of 65+ knobs with no opinionated preset bundles
  ("secure-default", "ci-mode", "enterprise-hardened").

**What would make this assessment wrong:**
An ops team follows the deployment guide, installs TeaAgent in a Docker container,
and discovers the TOML config extra is missing on Python < 3.11 (silent failure,
not a clear error message). They spend a day debugging before finding the docs
footnote. TeaAgent's reputation with that team is poisoned before they experience
any of the governance value.

**Confidence level:** 5/10. The documentation is real; the deployment automation
is not.

---

# Part 3: The Five Critical Truths

> These are hard-won, non-negotiable findings from the June 6 multi-angle review.
> They are not opinions. Each is supported by code evidence. Roadmap decisions
> that contradict these truths should be considered high-risk by default.

---

## Truth 1: Governance-First Is a Vertical Story, Not Horizontal

The 164K stars on OpenCode represent developers who want velocity, not auditability.
The 841-upvote "Claude Is Dead" thread represents developers who want cost
transparency. TeaAgent's governance story — hash-chained audit, compliance export,
multi-sig approvals, WASM skill signing — is not what the median developer is
looking for. It is exactly what a security-conscious DevOps lead at a Series B
fintech company needs to answer to their CISO.

**The non-negotiable truth:** TeaAgent cannot win a feature race against OpenCode
or Claude Code for general developer adoption. It can win a governance race for
regulated-industry adoption. These are different markets with different buyers,
different sales motions, and different success metrics.

**Practical implication:** Every go-to-market decision should be filtered through
the question: "Does this help us win the CISO conversation?" Horizontal features
(IDE integration, richer TUI, more LLM providers) are not the priority until the
vertical story is fully developed and a reference customer exists.

**What would falsify this:** A survey of 50 non-regulated developer teams shows
that 40% of them would pay for governance primitives. Currently, there is no such
data for TeaAgent. This is a hypothesis, not a measurement.

---

## Truth 2: Architecture Strength ≠ Product Readiness

TeaAgent has 130 modules, 3355 passing tests, 14 LLM providers, a five-loop
governance system, WASM sandboxing, OAuth 2.1/DPoP, SSH vote relay, and a
multi-tenant control plane architecture. This is impressive. It is not product
readiness.

Product readiness requires:
- External users who have successfully run `pip install teaagent` and completed a
  task (zero external users documented).
- Documentation that matches reality (doc⇄reality drift is a known recurring
  issue per `teaagent-total-review` memory).
- An installation path that works for non-expert operators (no `pip install teaagent[all]`,
  no published Docker image, PEP 668 trap on macOS).
- A UX that a developer can use without reading the source code (JSON default
  output, `@deprecated` chat REPL, UUID-based approval IDs).

**The non-negotiable truth:** The architecture is the right foundation. The
product needs 6–12 months of hardening, simplification, and external exposure
before the architecture becomes a credible asset rather than a credibility risk.

**Practical implication:** Before making any external claims about governance
capabilities, close the trust gap: fix AUD-01/AUD-02/AUD-03 audit integrity bugs,
ship the run receipt, make `--human` the default output mode, and publish the
security whitepaper with accurate claims.

---

## Truth 3: The Moat Exists But Isn't Obvious

The hash-chained audit trail (`audit.py:111-139`, `audit_chain.py:57-78`), hard
cost caps (`runner/_core.py`), and compliance export bundle are genuine features
that no direct competitor ships. This is a real moat.

The moat has three problems:

**Problem A:** It's not visible. TeaAgent has no external users, no case studies,
and no public blog posts explaining the moat. A moat that no one can see is not
a competitive advantage.

**Problem B:** The moat has internal cracks. The HMAC key save silently fails
(`audit.py:209-214`). Legacy lines reset the chain anchor silently
(`audit_chain.py:130-133`). Disk write failures let the run continue with no
durable audit (`audit.py:439-442`). The moat makes claims it cannot fully
deliver yet.

**Problem C:** The moat requires a specific buyer. Most developers don't care
about compliance-grade audit trails. The subset who do is real and has budget,
but they are not going to discover TeaAgent on their own.

**The non-negotiable truth:** The moat is real, but it must be (a) made visible
externally, (b) made technically sound (fix the audit integrity bugs), and
(c) made discoverable to the specific buyers who care about it.

---

## Truth 4: Multi-Agent Is Over-Promised

TeaAgent's maturity matrix marks multi-agent / tournament as "Beta." The feature
matrix claims "✅ Beta (SwarmManager, tournament)." The reality:

- Parent cost caps are **not** propagated to child agents
  (`subagents/_manager.py` — the `max_estimated_cost_cents` field is never passed
  to children).
- The approval queue is an **in-process module-level singleton**
  (`_approval_queue.py:673`). It dies with the process.
- `SwarmManager` and `SubagentManager` are **independent, parallel layers** with
  no shared state, no shared approval queue, and no shared cost rollup.
- The threading model (`swarm.py:692`, `ThreadPoolExecutor`) hits OS thread limits
  at ~32 concurrent subagents before it hits LLM API limits.
- Remote/distributed multi-agent is a **non-goal** for current phase
  (`strategy/remote-multi-agent-non-goals-2026-06-06.md`).

**The non-negotiable truth:** Multi-agent works for short, local, single-process
delegation. It is not a distributed multi-agent substrate. Positioning it as one
to enterprise buyers is a trust liability that will surface during proof-of-concept.

**Practical implication:** The multi-agent section of any external positioning
material must explicitly scope to "local, single-process delegation." The
enterprise story for multi-agent requires: durable approval queue, budget
envelope propagation, swarm/subagent layer unification, and at minimum a
reference architecture for distributed deployment.

---

## Truth 5: Operations Is the Hidden Blocker

The technical and governance story can be compelling in a presentation. It will
fail in production deployment for the following reasons:

**5a — Approval queue invisibility.** There is no CLI command showing pending
approvals with age, risk level, and expiry. An operator running a long swarm
has no visibility into whether child approvals are stuck or timed out.
Evidence: `WS4-002` in `system-improvement-work-directions`.

**5b — Audit log growth is unbounded.** `AuditLogger.events` grows forever
(`audit.py:123`). `runs-index.jsonl` is never paginated or rotated
(`run_store.py:47`). At 10k+ runs, listing runs requires reading the entire index.
Evidence: `engineering-architecture-critique §2 — JSONL Ceiling`.

**5c — Configuration complexity is hostile.** 65+ configurable settings with no
opinionated preset bundles. A new operator faces 14 LLM providers, 5 permission
modes, 8 audit settings, 9 multi-sig quorum keys, and ~18 environment variables.
The complexity is not documented as progressive disclosure; it is documented as a
configuration reference. Evidence: `deployment-and-operations-readiness §2`.

**5d — No live operational visibility.** No wall-clock timing on LLM calls. No
approval queue depth metrics. No cost burn rate display. An operator running
TeaAgent in CI cannot answer "is this run in trouble?" without reading raw JSONL.
Evidence: `performance-and-observability-critique §2.2`.

**The non-negotiable truth:** Governance is only valuable if the operators can
see it working. An audit log that silently fails disk writes is not an audit log.
An approval queue with no visibility is not a governance control. Operational
observability is a prerequisite to the governance story, not an optional add-on.

---

# Part 4: Competitive Positioning Map

## 4.1 Dimension Matrix

| Dimension | TeaAgent | Claude Code | OpenCode | Aider | Kiro | Cursor |
|-----------|----------|-------------|----------|-------|------|--------|
| **Governance** | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ | ★☆☆☆☆ | ★★★☆☆ | ★☆☆☆☆ |
| **Audit Trail** | Hash-chain JSONL | Chat logs only | None | Git log only | CloudWatch logs | None |
| **Hard Budgets** | ✅ Enforced ceiling | ❌ Session total only | ❌ None | ❌ None | ✅ Token limits | ❌ None |
| **Multi-provider** | ✅ 14 adapters | ❌ Claude only | ✅ Multi | ✅ Multi | ❌ Bedrock/Anthropic | ✅ Multi |
| **UX Surface** | ⚠️ CLI/TUI | ✅ CLI + IDE | ✅ TUI + IDE | ✅ CLI | ✅ IDE | ✅ IDE (primary) |
| **Multi-agent** | ⚠️ Local only | ✅ Subagents | ✅ Parallel sessions | ❌ Sequential | ✅ Autonomous mode | ✅ Background agents |
| **Extensibility** | ⚠️ Entry-points; policy not pluggable | ✅ Hooks + skills | ✅ Agents config | ✅ Custom commands | ✅ Hooks + steering | ✅ Rules + MCP |
| **Open source** | ✅ Yes | ❌ Closed | ✅ Yes | ✅ Yes | ❌ Closed | ❌ Closed |
| **External adoption** | ❌ Zero | ✅ Very high | ✅ 164K stars | ✅ ~28K stars | ⚠️ Growing | ✅ Very high |
| **Cloud hosted** | ❌ Stub only | ✅ Yes | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **SOC 2** | ❌ Doc only | ✅ (via Anthropic) | ❌ | ❌ | ✅ (via AWS) | ⚠️ Partial |
| **IDE integration** | ⚠️ VS Code MCP Beta | ✅ Deep (Zed, VS Code, JetBrains) | ✅ IDE + desktop | ⚠️ Partial | ✅ IDE-native | ✅ IDE-native |
| **Cost** | Free (OSS) | API + subscription | Free (OSS) | Free (OSS) | $$$ subscription | $$$ subscription |

> **Rating methodology:** ★★★★★ = unique, production-grade, tested claim.
> ★★★☆☆ = present, solid, but not differentiated. ★★☆☆☆ = present but partial.
> ★☆☆☆☆ = absent or minimal.

---

## 4.2 Head-to-Head Analysis

### 4.2.1 TeaAgent vs. Claude Code

**Where Claude Code wins:**
- IDE integration is deep and mature (Zed, VS Code, JetBrains — all first-class).
- Brand trust via Anthropic; SOC 2 via Anthropic's enterprise agreements.
- Subagent system is production-tested at massive scale.
- Claude model quality is best-in-class; vendor lock is a feature, not a bug,
  for teams already committed to Anthropic.
- Distribution: every developer who uses Claude knows Claude Code exists.

**Where TeaAgent wins:**
- Multi-provider: Claude Code is Claude-only. Any team uncomfortable with
  Anthropic monopoly, or needing local/on-premises model deployment, has no
  governance option from Claude Code.
- Hard cost caps: Claude Code has a session cost counter; TeaAgent's hard ceiling
  prevents runaway spend. This is a concrete, testable differentiator.
- Hash-chained audit: Claude Code has no audit replay, no compliance export.
  For a regulated-industry buyer who needs to demonstrate what the agent did,
  Claude Code provides nothing; TeaAgent provides a signed, verifiable record.
- Open source: Claude Code is closed-source. For security-paranoid teams (common
  in defense, government, and financial services), the ability to audit the agent
  harness code is a purchasing requirement.

**Where the competition underestimates TeaAgent:**
Claude Code's most likely path is to add governance features over time. But the
governance story requires not just features but an audit culture — the right
defaults, the right documentation, the right testing. TeaAgent's five-loop
governance system was designed as the primary product, not bolted on. That
architecture advantage may not matter if Claude Code ships a "good enough"
governance layer before TeaAgent has external users.

**Strategic recommendation:**
Position TeaAgent as the governance bridge over Claude Code, not a replacement.
"Run Claude-quality tasks with TeaAgent governance" avoids head-to-head
model quality comparison and reaches Claude Code's existing user base.

---

### 4.2.2 TeaAgent vs. OpenCode

**Where OpenCode wins:**
- 164K GitHub stars — community momentum, third-party integrations, plugins.
- Rust-native TUI (`opencode.ai`) — dramatically faster than Python-based
  terminal UIs.
- Multi-surface: terminal TUI + IDE + desktop app. TeaAgent is CLI/TUI only.
- Community-driven development velocity is very high.

**Where TeaAgent wins:**
- Governance layer: OpenCode has "per-agent permissions" (described as `⚠️ partial`
  in the feature matrix). It has no audit trail, no hash-chain, no compliance
  export, no hard cost cap.
- Plan-before-write is an enforced invariant in TeaAgent, not a workflow mode.
  OpenCode's "Plan mode" is a user choice; `--require-plan` in TeaAgent is a
  safety gate with validation and rollback.
- Multi-sig consensus: OpenCode has no equivalent. This is the feature that is
  hardest to copy in a weekend PR.

**Where the competition underestimates TeaAgent:**
OpenCode's community moves fast and will close feature gaps. They may not
prioritize the enterprise governance story because their community is
developer-first, not enterprise-security-first. A governance PR from an
anonymous contributor without compliance testing and security review would likely
not satisfy enterprise buyers anyway. TeaAgent's governance is differentiated
not just by the feature existing, but by the depth of testing and the explicit
threat model.

**Strategic recommendation:**
Publish a blog post: "What OpenCode's permission model is missing." Target it
precisely at the community that reads OpenCode's changelog. Cost: one week of
writing time. Potential reach: thousands of security-aware developers who are
already evaluating OpenCode.

---

### 4.2.3 TeaAgent vs. Aider

**Where Aider wins:**
- Simplicity: `aider --model gpt-4o` and you're running. Zero governance overhead
  for users who want maximum velocity.
- Git-native undo: every change is a git commit. The undo model is familiar and
  universally understood.
- ~28K stars: established community, known in the ML/AI tools ecosystem.

**Where TeaAgent wins:**
- Hard cost caps: Aider has no cost controls. A runaway Aider session on a complex
  refactor can accumulate significant API spend before the user notices.
- Permission modes: Aider has no concept of read-only mode or workspace-write mode.
  It executes whatever the model requests.
- Audit trail: Aider's "audit" is a git log. For compliance purposes, git log does
  not record tool arguments, cost, approval decisions, or timing.

**Where the competition underestimates TeaAgent:**
Aider's simplicity is its market position; adding governance would require a
significant redesign. TeaAgent can point to specific, documented incidents
(the "$300 in one session" Reddit posts) where Aider's lack of cost controls
burned users. This is a concrete, emotionally resonant competitive message.

**Strategic recommendation:**
Target cost-conscious teams — indie developers, small startups — with the
budget cap story. "The agent that never surprises your finance team." This
is a different buyer segment from the governance/CISO story, but it's
achievable without enterprise sales motion.

---

### 4.2.4 TeaAgent vs. Kiro

**Where Kiro wins:**
- AWS backing: enterprise procurement, compliance, and trust via AWS relationship.
- SOC 2 through AWS.
- Spec-driven development with steering docs is a strong UX innovation.
- Cloud-native: agents run in AWS infrastructure; no local deployment required.
- Autonomous mode with web access.

**Where TeaAgent wins:**
- No AWS lock-in: Kiro is Bedrock/Anthropic only. TeaAgent runs any model,
  including local Ollama models for organizations with data sovereignty requirements.
- Open source: security teams can audit TeaAgent's approval model. Kiro is closed.
- Hash-chained audit: Kiro has CloudWatch logs; TeaAgent has a verifiable,
  hash-chained, signed audit trail. These are not equivalent for compliance purposes.
- On-premises deployment: a regulated org with data-never-leaves-AWS requirements
  may still need on-premises AI agent execution. Kiro cannot satisfy that requirement.

**Where the competition underestimates TeaAgent:**
Kiro's AWS backing is also its constraint. Healthcare organizations with BAA
requirements, government contractors with FedRAMP needs, and European enterprises
with GDPR data-residency requirements may not be able to use Kiro in their
environments. TeaAgent's local-first, multi-provider design is purpose-built for
exactly these constraints.

**Strategic recommendation:**
Target organizations that are already in regulated industries but cannot commit
to cloud-only AI agent infrastructure. "All your agent decisions, all your tool
calls, all your cost — on-premises, auditable, hash-chained." This message
differentiates from Kiro on the axis where Kiro cannot compete.

---

## 4.3 Competitive Strategy Summary

| Competition | Core message | Channel |
|-------------|-------------|---------|
| vs. Claude Code | "Governance bridge: Claude quality + TeaAgent audit" | Claude Code user community, enterprise evaluations |
| vs. OpenCode | "The governance layer OpenCode doesn't have" | OpenCode community, HN, technical blog |
| vs. Aider | "Hard cost caps and compliance audit" | Cost-conscious developers, indie hackers, r/LocalLLaMA |
| vs. Kiro | "On-premises, multi-provider, no AWS lock-in" | Regulated industries, government contractors, EU enterprises |

---

# Part 5: Work Direction with Effort/Impact

> **Framework:** Each work item is evaluated on:
> - **Effort:** XS (< 0.5 person-weeks), S (0.5–1 pw), M (1–3 pw), L (3–6 pw),
>   XL (6+ pw).
> - **Impact:** Risk reduction (R), Revenue unlock (Rev), Adoption unlock (A).
> - **Decision:** 3-month / 6-month / 12-month plan inclusion.

---

## Phase 1: Trust Tier (Critical Path, Must Ship First)

### P1-A: Fix Audit Integrity Bugs (WS3-001, WS3-002)

**What:** Fix AUD-01 (HMAC key save silent failure at `audit.py:209-214`), AUD-02
(disk write failure silent at `audit.py:439-442`), and AUD-03 (legacy line resets
chain anchor silently at `audit_chain.py:130-133`). Add compliance mode that raises
on audit durability failure.

**Why:** The hash-chained audit trail is TeaAgent's primary competitive moat.
An audit trail that silently fails is a liability, not an asset. Before any
external claim about audit integrity, these bugs must be closed. Without this fix,
the security whitepaper cannot be written accurately.

**Effort:** S (0.5–1 person-week) — targeted bug fixes in existing audit code.

**Impact:**
- R: Eliminates critical trust liability; makes audit moat defensible.
- Rev: Prerequisite to every enterprise conversation.
- A: Prerequisite to security whitepaper publication.

**Dependencies:** None.

**Decision:** 3-month plan. P0 prerequisite.

---

### P1-B: Compliance Mode for Audit Failures (WS3-001)

**What:** In compliance mode, any audit write failure that would silently continue
(`audit.py:439-442`) instead halts the run with a clear error. Operator-facing
error message explains that audit durability failed and the run was stopped to
preserve the integrity guarantee.

**Why:** The current behavior — silently continuing in-memory after a disk failure —
undermines the integrity claim. An enterprise buyer evaluating TeaAgent's audit
trail needs to know it is fail-safe, not fail-silent.

**Effort:** XS (< 0.5 person-weeks) — add a flag and a conditional raise.

**Impact:**
- R: Closes AUD-02 completely.
- Rev: Directly enables the "compliance-grade audit" sales message.

**Dependencies:** P1-A (fix AUD-01/AUD-02/AUD-03 first; then add compliance mode
as an explicit opt-in for audited deployments).

**Decision:** 3-month plan.

---

### P1-C: CI Documentation Truth Guard (WS0-003, FO-1)

**What:** Add a CI step that fails when a documented claim contradicts a fresh
pytest run. At minimum: `acceptance.md`'s test count prose must match the actual
pytest output. Extend to any doc that makes verifiable quantitative claims.

**Why:** `acceptance.md` says "3255 passed, 26 failed" while HEAD has 0 failures.
External evaluators will find this. The doc⇄reality drift is a recurring systemic
risk (meta-finding from `teaagent-total-review-2026-06-04`).

**Effort:** S (0.5–1 person-week) — new CI job, grep-based claim extractor.

**Impact:**
- R: Prevents the doc⇄reality drift from compounding.
- A: Makes external publication safe.

**Dependencies:** None.

**Decision:** 3-month plan.

---

### P1-D: Run Receipt MVP (WS1-001)

**What:** After every run, emit a human-readable receipt that includes: goal,
provider/model, budget used, tools invoked, approvals granted, files touched,
tests run (if any), total cost, and audit path. This should be the default
output mode for non-interactive runs.

**Why:** The current default is raw JSON. A developer running TeaAgent for the
first time who sees a wall of JSON will not return. The run receipt is the first
step in converting the internal governance richness into user-visible trust.

**Effort:** M (1–3 person-weeks) — new `RunReceipt` type, output formatting,
integration into `AgentRunner.run()` exit path.

**Impact:**
- A: Dramatically lowers first-use friction.
- R: Creates an observable artifact for every run; makes governance visible.

**Dependencies:** None.

**Decision:** 3-month plan.

---

### P1-E: Human-Readable Output as Default (WS1-001, WS1-002)

**What:** Make `--human` the default output mode for all CLI commands. JSON output
becomes opt-in via `--json` or `--output json`. Replace UUID-based approval IDs
with numbered pending actions with tool name, risk class, and path summary.

**Why:** JSON-default is the single highest-friction point in the first-use
experience (`user-experience-and-conversation-patterns §1.1`). A developer who
runs `teaagent daily "summarize this repo"` and gets a wall of JSON will not use
the tool again.

**Effort:** M (1–3 person-weeks) — output layer changes across CLI handlers,
approval UX refactor.

**Impact:**
- A: Directly reduces first-use abandonment.
- R: Approval UX improvement closes a usability gap that undermines the governance
  story.

**Dependencies:** P1-D (run receipt) is complementary but not blocking.

**Decision:** 3-month plan.

---

## Phase 2: Extensibility and Market Preparation

### P2-A: AgentService Run Contract (WS5-001)

**What:** Define an `AgentService` interface that CLI, TUI, plugins, and tests
invoke via a shared run setup path rather than duplicating orchestration logic.
This eliminates the three separate entry points (`cli/_handlers/_agent.py:3026 lines`,
`tui/__init__.py:1632 lines`, `chat_session_controller.py`) that each orchestrate
agent runs with slightly different semantics.

**Why:** The three parallel entry points create three places where governance
invariants must be maintained. Every new governance feature (run receipt, compliance
mode, approval UX) must be wired into all three separately. A shared `AgentService`
contract reduces this to one.

**Effort:** L (3–6 person-weeks) — interface design, migration of CLI/TUI/chat to
use it, tests.

**Impact:**
- R: Reduces governance invariant duplication.
- Rev: Enables external plugin authors to invoke the harness without forking.

**Dependencies:** None.

**Decision:** 6-month plan.

---

### P2-B: Stable Event Stream Contract (WS5-002)

**What:** Define and document a stable event stream that consumers can subscribe
to without depending on internal audit object layout. This enables: external
dashboards, IDE extensions, CI integrations, and third-party observability tools.

**Why:** The current audit log is the best observability artifact but is tied to
internal object layout (`AuditEvent` structure). Any external consumer that reads
audit JSONL is coupled to internal types. A stable event stream enables the
ecosystem without coupling it.

**Effort:** M (1–3 person-weeks) — schema definition, serialization layer, tests.

**Impact:**
- Rev: Enables third-party integrations that multiply TeaAgent's reach.
- A: IDE extension and dashboard can be built without forking core.

**Dependencies:** P2-A (event stream consumers use `AgentService`).

**Decision:** 6-month plan.

---

### P2-C: Kubernetes Reference Deployment (WS4)

**What:** A hardened, documented, Kubernetes Helm chart for single-instance
TeaAgent deployment. Includes: config management via Secrets, audit log to
persistent volume, `teaagent doctor all` as a readiness probe, and a basic
operational runbook.

**Why:** Without a reference deployment, every enterprise evaluation ends at
"we can't run this in our environment." The security whitepaper is necessary but
not sufficient; the deployment artifact must exist before the CISO conversation
is winnable.

**Effort:** L (3–6 person-weeks) — Helm chart, operational runbook, CI testing.

**Impact:**
- Rev: Directly unblocks enterprise procurement conversations.
- A: Makes TeaAgent deployable by an ops team without Python expertise.

**Dependencies:** P1-A (audit integrity fixed before deploying in enterprise).

**Decision:** 6-month plan.

---

### P2-D: Security Whitepaper (WS6-002)

**What:** A 10-page document that maps TeaAgent's controls to NIST AI Agent
Standards and OWASP LLM Top 10. Must include: exact guarantees, non-goals,
failure behavior descriptions, and verification commands. Must NOT include claims
about features that are Beta or have known integrity gaps.

**Why:** Enterprise evaluators cannot approve a tool without a formal security
document. The whitepaper is a purchasing prerequisite, not a marketing artifact.
It is also a forcing function for the honest claim discipline required by P1-A
and P1-C.

**Effort:** M (1–3 person-weeks) — writing, claim audit, legal review.

**Impact:**
- Rev: Directly enables enterprise evaluation conversations.

**Dependencies:** P1-A (audit bugs fixed), P1-C (doc-truth CI guard passing).

**Decision:** 6-month plan.

---

### P2-E: Persona-Specific Onboarding Guides (WS6-004)

**What:** At minimum four guides: (1) solo CLI developer, (2) team operator,
(3) tool/plugin author, (4) security reviewer. Each guide has a defined goal,
a 15-minute golden path, and a "what this persona cares about" framing.

**Why:** The current docs are reference documentation. No one reads reference
documentation first. A developer encountering TeaAgent for the first time needs
a 15-minute path to "I understand what this does and why I would use it."

**Effort:** M (1–3 person-weeks) — writing + golden path validation.

**Impact:**
- A: Directly reduces time-to-first-value for new users.

**Dependencies:** P1-E (human-readable output).

**Decision:** 6-month plan.

---

## Phase 3: Multi-Agent Safety and Distributed Foundation

### P3-A: Budget Envelope Propagation to Children (WS2-003)

**What:** When a parent agent spawns a child, propagate `max_estimated_cost_cents`,
`max_iterations`, `max_tool_calls`, and `elapsed_time_budget` as explicit child
constraints. Children must not be able to exceed the parent's remaining budget.

**Why:** Currently, children get fixed defaults (`max_iterations=5, max_tool_calls=5`)
regardless of the parent's remaining budget (`_manager.py` — missing propagation).
A parent with 90% of its budget spent can still spawn children with full default
budgets. This is a cost governance gap for multi-agent use.

**Effort:** M (1–3 person-weeks) — budget propagation in `_manager.py`, tests.

**Impact:**
- R: Closes the multi-agent cost governance gap.
- Rev: Required for enterprise claims about multi-agent cost control.

**Dependencies:** Typed `RunContext` dataclass (TD-05 in engineering tech debt).

**Decision:** 6-month plan.

---

### P3-B: Durable Approval Queue (WS2-005)

**What:** Replace the in-process module-level `_approval_queues` dict
(`_approval_queue.py:673`) with a durable coordination abstraction. Local default
can be file-backed (a JSONL queue file in `.teaagent/`); the interface must
support recovery after process restart and, eventually, remote orchestration.

**Why:** The current in-process queue dies with the process. Any multi-agent
deployment that spans a process restart loses all pending approval state. This
is not acceptable for production governance use.

**Effort:** L (3–6 person-weeks) — interface design, file-backed implementation,
migration, tests.

**Impact:**
- R: Makes approval queue a real governance control, not a process-scoped ephemeral.
- Rev: Required for any "production multi-agent governance" claim.

**Dependencies:** P2-A (`AgentService` contract simplifies integration).

**Decision:** 12-month plan.

---

### P3-C: Swarm/SubagentManager Unification Design (WS2-006)

**What:** Produce a design document (not implementation) for a unified orchestration
layer that replaces the parallel `SwarmManager` and `SubagentManager` systems.
The design must address: unified approval queue, unified cost rollup, unified
lineage tracing, and a migration path.

**Why:** Two separate orchestration layers with no shared state is a architectural
debt that accumulates with every multi-agent feature added. The design must be done
before the implementation to avoid locking in a broken architecture.

**Effort:** M (1–3 person-weeks) — design only, no implementation.

**Impact:**
- R: Prevents multi-agent architecture from forking further.
- Rev: Design document enables external contributors to understand and improve
  the multi-agent system.

**Dependencies:** P3-A (budget propagation), P3-B (durable queue design).

**Decision:** 12-month plan.

---

### P3-D: Async Refactor Foundation (Engineering Architecture)

**What:** Introduce an async-first execution model for the core run loop and
approval policy. This is not a full async rewrite; it is the foundation that
unblocks async without requiring simultaneous migration of all call sites.
The immediate deliverable: `ApprovalPolicy` as a proper async-capable class,
not a frozen dataclass with a hidden `ThreadPoolExecutor`.

**Why:** The `ThreadPoolExecutor` per `ApprovalPolicy` instance (`policy.py:70`)
is a known thread pool leak in long-lived processes (TD-01, TD-02). The sync→async
bridge (`policy.py:434`, `asyncio.get_running_loop()` + executor) can deadlock.
Every new feature that touches approval policy touches the leak.

**Effort:** XL (6+ person-weeks) — high-risk refactor; must be done incrementally.

**Impact:**
- R: Eliminates the thread pool leak in production daemons.
- Rev: Enables async provider adapters (streaming LLM responses, lower latency).

**Dependencies:** P2-A (`AgentService` contract must be stable before refactoring
the underlying run loop).

**Decision:** 12-month plan.

---

## 12-Week Tradeoff: If We Have Only 12 Weeks

Given 12 weeks and a single-team budget, the recommended allocation is:

| Weeks | Item | Rationale |
|-------|------|-----------|
| 1–2 | P1-A: Fix audit integrity bugs | Non-negotiable; the moat has cracks |
| 2–3 | P1-C: CI doc truth guard | Prevents drift from compounding during active dev |
| 3–5 | P1-D + P1-E: Run receipt + human-readable output | Highest adoption impact per week |
| 5–8 | P1-B: Compliance mode; P2-D: Security whitepaper | Unlocks enterprise conversations |
| 8–10 | P2-E: Persona-specific onboarding guides | Multiplies external adoption |
| 10–12 | P2-C: Kubernetes reference deployment | Unblocks procurement |

What we are explicitly deferring in a 12-week window:
- P2-A (AgentService contract): Impactful but disruptive; wrong for a fast sprint.
- P3-x (multi-agent safety): Necessary but not on the critical path for the first
  external customer.
- P3-D (async refactor): High risk; do not touch during a sprint with external
  commitments.

---

# Part 6: Decision Log

> This log documents the hard calls made in this assessment. Each decision
> includes the alternative considered, the rationale, the risk if wrong, and a
> confidence level. Decisions that contradict this log should be documented with
> new rationale, not silently overridden.

---

## Decision 1: Fix P0 Audit Integrity Bugs Before Shipping Features

**Decision:** The three audit integrity bugs (AUD-01 HMAC silent failure,
AUD-02 disk write silent continuance, AUD-03 legacy line chain reset) must be
fixed before any external positioning of TeaAgent's audit capabilities.

**Alternative considered:** Parallel work — ship the Kubernetes deployment and
security whitepaper while fixing audit bugs in a separate track.

**Rationale:** The audit trail is the primary moat. An audit trail that makes
claims it cannot deliver destroys trust faster than no audit trail. The security
whitepaper cannot accurately describe the audit chain without acknowledging these
gaps. External evaluators will find them; better to fix them first.

**Risk if wrong:** Serializing on audit bugs delays market entry by 2–4 weeks.
If OpenCode ships a permission matrix during those weeks, the window narrows.
This risk is real but manageable; audit bugs would be discovered during any
serious enterprise evaluation, and the cost of discovery after positioning is
much higher than the cost of a 2–4 week delay.

**Confidence:** 85%.

---

## Decision 2: Governance-First Positioning, Not Horizontal

**Decision:** TeaAgent's go-to-market should target regulated/compliance-sensitive
organizations (fintech, healthcare, government contractors) as the primary vertical,
not general developer adoption.

**Alternative considered:** "Governance + general purpose" positioning — compete
for general adoption while also targeting compliance-sensitive verticals.

**Rationale:** The market for general-purpose coding agents is already owned by
Claude Code, OpenCode, and Cursor. These competitors have distribution advantages
(brand, IDE integration, community) that cannot be overcome with features alone.
The governance lane is uncontested, has a real TAM with budget, and aligns with
TeaAgent's actual architectural strengths.

**Risk if wrong:** The TAM for governance-first tools may be too small to sustain
a project. If the "CISO conversation" TAM turns out to be 50 companies rather than
5000, the vertical strategy fails to generate enough adoption to sustain development.
Market validation — at least one paying reference customer — is needed within
12 months to validate this decision.

**Confidence:** 70%. This confidence is explicitly low because it has not been
validated with real buyer conversations. The decision is structurally sound but
requires empirical validation.

---

## Decision 3: Async Refactor Is P2, Not P0

**Decision:** The async refactor (making the run loop, approval policy, and swarm
async-native) is planned for the 12-month horizon, not the immediate sprint.

**Alternative considered:** Start the async refactor now, before more synchronous
code is written and the refactor scope grows further.

**Rationale:** The threading model, while inefficient, works for current use cases
(single-user, local, developer CLI). The async refactor is high-risk (touches
runner, policy, swarm, TUI) and would dominate a 12-week sprint. The immediate
priority is external adoption and trust — features users can see. The async
refactor is an internal quality improvement that users cannot see.

**Risk if wrong:** Every new feature added to the synchronous model is one more
file to change in the async refactor. If a production daemon use case becomes
important in the next 6 months, the thread pool leak at scale becomes a customer-
facing bug. The async refactor later is riskier than doing it now.

**Confidence:** 60%. This is explicitly low. The decision may be pennywise-
pound-foolish if the use case evolves toward long-lived daemons or CI/CD
integration faster than expected.

---

## Decision 4: Kubernetes Reference Deployment Before Full Cloud-Native

**Decision:** Ship a Kubernetes reference deployment (Helm chart, single-instance,
persistent audit volume) before designing a full cloud-native microservices
architecture.

**Alternative considered:** Design a true cloud-native multi-tenant SaaS platform
before shipping any deployment artifact.

**Rationale:** A reference deployment unblocks enterprise procurement conversations
in 6 months. A full cloud-native design takes 12–18 months and requires a product
that already has external traction to justify the investment. Industry standard
practice: ship the reference deployment, learn from production usage, design the
platform from observed real requirements rather than predicted ones.

**Risk if wrong:** The Kubernetes reference approach creates a monolithic deployment
that becomes technical debt when the cloud-native platform is eventually designed.
Users who deploy the reference may have expectations that the production platform
must maintain compatibility with.

**Confidence:** 80%. Standard practice in the infrastructure software market;
deviation would require a specific counter-argument.

---

## Decision 5: Defer Team Collaboration Features

**Decision:** Shared approval queues, PR-linked workflows, and team audit
dashboards are not on the 12-month plan. They are acknowledged as market gaps
but are not in the near-term roadmap.

**Alternative considered:** Build team collaboration features as a differentiated
enterprise offering from day one.

**Rationale:** Team collaboration requires a stable, tested single-user product
first. Building team features on a foundation with known audit integrity bugs,
approval queue lifecycle issues, and doc⇄reality drift is building on sand.
GitHub Copilot, Kiro, and Devin own the team collaboration market today. TeaAgent's
path is to win single-operator governance buyers first, then extend to team
workflows once the foundation is solid.

**Risk if wrong:** Enterprise procurement is often driven by team-level buying
decisions, not individual developer choices. If the sales cycle requires team
features to close, deferring them costs revenue. This is a real risk that should
be revisited at the 6-month mark.

**Confidence:** 75%.

---

# Part 7: Three-Year Vision

> This vision is a prediction about a market that does not yet have a TeaAgent
> customer. It is directional intent, not a forecast. The strategy should be
> updated at each 6-month review based on empirical evidence from actual user
> interactions, not on the prediction being right.

---

## Year 1 (0–12 months): Foundation and First Trust

**Theme:** Fix the trust tier, become externally discoverable, close the first
enterprise conversation.

### Engineering goals
- Fix all P0 audit integrity bugs (AUD-01, AUD-02, AUD-03).
- Ship compliance mode for audit durability.
- CI doc-truth guard prevents doc⇄reality drift from compounding.
- Run receipt MVP: every run produces a human-readable artifact.
- Human-readable output as default: `--human` is the default, `--json` is opt-in.
- Kubernetes reference deployment (Helm chart, production-quality runbook).
- `pip install teaagent[all]` meta-extra.
- Published Docker image on Docker Hub.

### Market goals
- Security whitepaper: 10 pages, NIST AI/OWASP LLM Top 10 mapping, honest about
  non-goals and failure behavior.
- External README: governance-first positioning, anti-personas, "when not to use
  TeaAgent" page.
- Persona-specific onboarding guides: solo developer, team operator, security
  reviewer.
- One public blog post targeting the cost-surprise/governance-aware developer
  community.
- Target verticals: fintech startups, healthcare tech companies, government
  contractors evaluating AI agent safety.
- **Success metric:** One external user who has successfully deployed TeaAgent and
  is using it for real work. One documented case study.

---

## Year 2 (12–24 months): Architecture and Market Expansion

**Theme:** Scale the architecture, deepen the enterprise story, expand the team.

### Engineering goals
- `AgentService` run contract: unified entry point for CLI, TUI, plugins, tests.
- Stable event stream: external dashboards and IDE extensions can be built without
  forking core.
- Budget envelope propagation to child agents: multi-agent cost governance is real.
- Durable approval queue: file-backed recovery; survives process restart.
- Swarm/SubagentManager unification: one orchestration layer.
- Async refactor: async-native run loop, approval policy, and swarm coordination.
- VS Code extension promoted from Beta to Stable: first-class IDE surface.

### Market goals
- 5+ public case studies from actual users.
- SOC 2 Type I certification (establishes the certification, not just the docs).
- Enterprise SLA offering: managed hosting for organizations that cannot run
  self-hosted.
- Fortune 500 procurement conversations: one signed enterprise customer.
- Developer relations: 500+ GitHub stars, one conference talk.
- **Success metric:** 10 organizations using TeaAgent in production. One paid
  enterprise customer.

---

## Year 3 (24–36 months): Platform and Category Ownership

**Theme:** Define and own the "governed AI agent infrastructure" category.

### Engineering goals
- TeaAgent Cloud: multi-tenant SaaS platform with control plane, approval queue UI,
  team audit dashboards, and tenant isolation.
- Multi-tenant governance model: identity-bound approvals, team-level policies,
  shared audit views.
- Partner ecosystem: consulting integrations, OEM partnerships, certification program
  for "TeaAgent-compatible" tools.
- Industry-specific policy bundles: Fintech (SOX, PCI-DSS agent controls), Healthcare
  (HIPAA agent audit requirements), Legal (privilege-protected AI agent actions).

### Market goals
- $10M+ ARR, 50+ enterprise customers.
- SOC 2 Type II certification.
- NIST AI Agent Framework alignment documentation: TeaAgent as a reference
  implementation for AI agent governance.
- External contributors: 10+ open-source contributors to core governance layer.
- **Success metric:** A CISO at a Fortune 500 company points to TeaAgent when asked
  "How do we safely run autonomous AI agents?" This is the flag we are racing to plant.

---

## Summary: The Flag We Are Racing to Plant

TeaAgent's long-term success criterion is singular and falsifiable:

> **A CISO at a regulated-industry organization can use TeaAgent to answer the
> question: "How do we safely run autonomous AI agents?" and can demonstrate it
> to an auditor with a verifiable audit trail, a compliance export, and a
> reference deployment.**

Every work item that is not on the direct path to this outcome should be
evaluated against the question: "Does this get us to the CISO conversation, or
does it distract us from it?"

The three-year plan is ambitious but grounded: Year 1 builds the trust foundation,
Year 2 builds the architecture to support teams, Year 3 builds the platform to
support enterprises at scale. The risk at each stage is the same: that the market
moves faster than we do, that a better-resourced competitor claims the governance
category, or that the governance-first TAM turns out to be smaller than the
current analysis suggests.

The hedge against all of these risks is the same: ship something external users
can touch, learn from real usage, and update the plan based on evidence, not
prediction.

---

## Cross-Reference: Key Evidence Sources

All claims in this document are traceable to the following June 6, 2026 evidence package:

| Source | Primary question | This document's use |
|--------|-----------------|---------------------|
| `docs/analysis/engineering-architecture-critique-2026-06-06.md` | Architecture depth and technical debt | Part 2.1, Part 3, Part 5 tech debt items |
| `docs/analysis/multi-agent-coordination-critique-2026-06-06.md` | Multi-agent production readiness | Part 2.2, Truth 4, P3 work items |
| `docs/analysis/user-experience-and-conversation-patterns-2026-06-06.md` | UX friction and first-use experience | Part 1.2, Part 2.3, P1-D/P1-E |
| `docs/analysis/risk-and-trust-model-critique-2026-06-06.md` | Security trust claims and bypass paths | Part 2.6, Truth 3, P1-A/P1-B |
| `docs/analysis/performance-and-observability-critique-2026-06-06.md` | Operational observability gaps | Part 2.7, Truth 5, P2 observability items |
| `docs/analysis/integration-and-extensibility-critique-2026-06-06.md` | Plugin/extension boundary quality | Part 2.5, P2-A/P2-B |
| `docs/analysis/deployment-and-operations-readiness-2026-06-06.md` | Installation and ops readiness | Part 2.8, Truth 5, P2-C |
| `docs/analysis/competitive-landscape-and-positioning-2026-06-06.md` | Market positioning and competitor analysis | Part 4, Decision Log |
| `docs/analysis/competitor-self-comparison-matrix-2026-06-06.md` | Source-backed competitor features | Part 4.1 dimension matrix |
| `docs/analysis/system-critical-review-2026-06-06-INDEX.md` | Overall verdict and angle summaries | Part 1, Part 3 |
| `docs/plans/system-improvement-work-directions-2026-06-06.md` | Work items and acceptance criteria | Part 5 work items |
| `docs/maturity-matrix.md` | Feature readiness level by subsystem | Part 1.1 capability table |
| `docs/strategy/teaagent-product-principles-2026-06-04.md` | Core product principles | Part 1.3, Part 3 |

---

*Document generated: 2026-06-06. This is a dated strategic synthesis. All competitor
claims must be refreshed from official sources before use in external-facing materials.
Treat code:line citations as valid at HEAD `ad5e2d7`; verify before asserting in
any future context.*
