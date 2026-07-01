# Project Nature, Origins, and Dormant Surfaces — Parallel-Lens Analysis

> **Claim class:** Dated analysis (archive tier). Descriptive study of what TeaAgent
> *is*, its origins, and its dormant/experimental/descoped surfaces. Not a capability
> claim; not current-truth for roadmap/status (see `docs/roadmap-status.md`).
> **Date:** 2026-07-01 · **Anchor:** `1306ca7` · branch `main` · version `0.1.0`
> **Trigger:** Explicit owner request — "what kind of project is this, goals from
> origins, leaked/dormant features, better ways to use, scenarios."
> **Method:** Parallel-lens review packet + four adversarial read-only reviewers
> (historian, capability-wiring, usage-scenario, evidence-skeptic). Every
> load-bearing claim is tagged OBSERVED (a command was run / file read) or
> INFERENCE. Corrections from the panel are folded in.
> **Do not** treat descoped/dormant items below as shipped capability.

---

## Panel Consensus

- **Decision:** AGREE WITH CHANGES (4/4 reviewers). The analysis is substantially
  correct; five corrections below are mandatory.
- **Use-case recommendation:** `study` ✅ · `reproduce` ✅ (governance/audit claims
  are verifiable) · `adopt` ✅ *only* as a single-user, local, owner-operator harness ·
  `deploy` ❌ as multi-user/hosted/team (explicitly descoped; WAN surfaces exist but
  need deliberate hardening).
- **Framing correction (unanimous):** do **not** call these "leaked" features. No
  unintentional security exposure was found. Correct vocabulary: **dormant/unwired**,
  **experimental/Beta**, **shadow-mode**, **descoped**, or **documented-but-uncalled**.

### Required wording changes (folded into this doc)
1. "Leaked features" → "dormant / experimental / shadow / descoped surfaces" (EvidenceSkeptic).
2. "Two phases: platform → harness" → "one governance-first harness with two
   *overlapping* tracks (governance + surface area) from commit 1; 2026-06-13 tightened
   persona and allowed claims — not a technical break" (HistorianAuditor).
3. Provider count = **14** canonical; README is correct. The "15" was a dynamic
   `ProviderConfig()` reconstruction site, not a 15th provider (EvidenceSkeptic).
4. Feature-status table corrections L1/L2/L6/L7/L8/L9/L10 (CapabilityWiringReviewer).
5. Add "documented-but-uncalled functions" (D1–D6) and "invalid documented CLI/API
   surfaces" as first-class findings (EvidenceSkeptic, UsageScenarioReviewer).

---

## 1. What kind of project is this?

**TeaAgent is a governance-first, local-first, provider-agnostic harness for
autonomous coding — scoped (as of 2026-06-13) to a single owner-operator who is
simultaneously its maintainer, daily user, and audit reviewer.** `[OBSERVED` README.md:7,
`docs/strategy/harness-first-direction-2026-06-13.md`]

It is explicitly **not** a generic IDE-agent clone, an enterprise multi-user platform,
or a hosted cloud delegate `[OBSERVED` README.md:9]. The distinguishing pillars are a
5-level permission matrix, hash-chained append-only JSONL audit logs, bounded runs
(iteration/tool/cost caps), human approval gates for destructive tools, and
verify-don't-trust commands (`audit verify`, `doctor config-lint`, run receipts)
`[OBSERVED` README.md:13-21].

A defining property: **its first "external users" are other agents editing the harness
itself**, under `docs/agent-contribution-contract.md` (Status: Active V4-a) — deliberate
dogfooding, not adoption chasing `[OBSERVED` harness-first §1; contract verified by UsageScenarioReviewer].

## 2. Goals from origins (git-substantiated)

- **Commit 1** `3244321` (2026-05-08): *"Establish governance-first P0 agent harness."*
  Governance was the founding goal, not a later addition `[OBSERVED` git log --reverse].
- The first README (`b13ebbe`, 2026-05-09) already says "governance-first agent harness
  for autonomous coding tasks" `[OBSERVED` HistorianAuditor].
- Origin scope (`docs/p0-scope.md`): minimal runner, tool registry, approval gate, audit
  log — with MCP/A2A/multi-agent explicitly deferred, then landed within 48–72h `[OBSERVED` HistorianAuditor].
- Strategy docs consistently frame it as *"the harness is the platform, not the product"*
  (`malleable-governed-agent-harness-2026-06-03`, `teaagent-product-principles-2026-06-04`) `[OBSERVED` HistorianAuditor].

**Corrected arc (not two clean phases):** one harness with two *overlapping* tracks from
day one — (a) governance/security hardening and (b) surface-area expansion — running in
parallel throughout May–June `[OBSERVED` ~62 commits on 2026-05-08 alone mixing both;
HistorianAuditor U1=confirmed]. What changed on **2026-06-13** (`ddd32f1`,
`harness-first-direction-2026-06-13.md`) was the **positioning/persona and the
docs-truth rule**: external adoption / enterprise / team / hosted were "descoped from
current truth … may return later as goals, but no doc may state them as present-tense
capability." That decision reframed the docs and persona; it did **not** rip out A2A,
OAuth, the registry, or federation `[OBSERVED` HistorianAuditor].

Timeline (refined):
```
2026-05-08..15  Governance-first harness + rapid surface expansion (same sprint)
2026-05-16..06-12  Continued hardening + external-facing daily-driver/competitive docs
2026-06-13      Owner-ratified harness-first identity; external adoption descoped
2026-06-14+     Execute plan: event-spine migration (ADR 0032 M1–M7), docs tiering, UX friction log
```

## 3. Dormant / experimental / shadow / descoped surfaces

Package scale (drives the discoverability risk in §6): **56 top-level CLI commands**,
**65 `TEAAGENT_*` env flags**, **21 optional extras**, **14 providers** `[OBSERVED`].
Status legend: *unwired* = reachable from no entry point (carries `experimental —
unwired`); *shadow* = runs but never enforces; *descoped* = wired + real but product-
descoped; *dormant-path* = code exists, no production caller; *documented-uncalled* =
README claims a behavior whose function is never invoked.

| # | Surface | CLI / flag | Status (panel-corrected) | Evidence |
|---|---------|-----------|--------------------------|----------|
| L1 | Consensus / multi-sig | `consensus` | **partial** — CLI + `consensus/engine.py` wired; only `consensus_validation.py` unwired (ADR-0029 defers *validation integration*, not the CLI) | validate_wiring; CapabilityWiring |
| L2 | Policy engine + RBAC (H4) | `TEAAGENT_H4_POLICY_MODE`/`_RBAC_MODE` | **shadow (split)** — policy shadow-only, *never blocks* (`evaluate_approval_policy_shadow` always True); RBAC enforce only via `TEAAGENT_H4_RBAC_MODE=enforce` | CapabilityWiring |
| L3 | Policy routing | — | **unwired** (`experimental — unwired`) | validate_wiring |
| L4 | Scope-creep detector | — | **unwired** | validate_wiring |
| L5 | Self-update mechanism | — | **unwired** (`update/*`) | validate_wiring |
| L6 | Graph federation | `sync` | **partial** — `sync export/import/status` (FederatedGraphSync, file-based) wired; A2A/ANP/ACP *protocol adapters* have no CLI/runner entry → dormant | CapabilityWiring |
| L7 | Managed cloud runtimes | `cloud submit`; extras `managed-google-adk/vertex` | **advanced (opt-in egress)** — wired; hits provider SDKs only with runtime + extra installed | CapabilityWiring |
| L8 | OAuth 2.1/DPoP + MCP HTTP | `mcp serve --http` | **advanced (opt-in)** — OAuth only with explicit `--oauth-issuer`/`--oauth-signing-key`; default bind 127.0.0.1; non-loopback refused without auth | CapabilityWiring |
| L9 | Gateway / control-plane / JIT | `gateway`, `control-plane` | **descoped + wired** — these are `ENTRY_ROOTS`; handlers run real servers. Product-descoped, not dormant | CapabilityWiring |
| L10 | Tournament / swarm | `agent run --parallel N`; `experiment` | **partial** — `--parallel` uses `ParallelExperimentStack` (real); `SwarmManager.run_code_reviews`/`select_best_result` is **dormant-path** (tests only) | CapabilityWiring; U4 |
| L11 | Code Mode sandbox | `sandbox`; `code_mode` | advanced — AST-validated restricted exec; subprocess/container/gVisor backends | packet E7 |
| L12 | GraphRAG / code ontology / hybrid | `code-ontology`, `sync`; `TEAAGENT_HYBRID_*` | advanced (extra `graphqlite`) | packet E5 |
| L13 | Distributed approval queue | `TEAAGENT_APPROVAL_COORDINATION_*`, `TEAAGENT_REDIS_*` | advanced (Redis/file/http; file-backed default) | CapabilityWiring |
| L14 | Browser automation | extra `playwright` | dormant unless extra installed | packet E5 |
| L15 | Feature-flag system | `TEAAGENT_FEATURE_*` | hidden runtime flags | packet E4 |
| L16 | `ultrawork` workers | `ultrawork` | **deprecated** | teaagent --help |
| L17 | Replay / time-travel | `replay` | advanced | teaagent --help |

### 3b. Documented-but-uncalled functions (the honest "leaked features")
These are README/doc behaviors whose backing function has **zero production call sites** —
half-wired features that read as shipped but are not `[OBSERVED` EvidenceSkeptic]:
- **D1** README §7 "future tasks automatically receive warnings" → `get_failure_warnings()` never called (README:133; chat_commands.py:213-256).
- **D2** README §7 `teaagent📌2>` pin indicator → prompt has no pin count (README:141; tui/core.py:1515-1519).
- **D3** README §7 CLI auto-refresh on pinned-file save → `FileWatcher` is TUI-session only (README:139; tui/core.py:603).
- **D4** README §8 "LSP/static analysis integrated with `--validate`" → `--validate` runs ruff/mypy/pytest; `ValidationRunner` (LSP) unwired (README:145; validation/*).
- **D5** README §8 "validates code *before committing*" → post-run validation only (README:149; _agent/config.py:184-209).
- **D6** README §10 "automatic RAG archive after workflow completion" → `archive_to_rag()` has zero call sites (README:180; context_bus.py:350).

### 3c. Invalid documented CLI/API surfaces (doc drift)
Repo guides cite surfaces that don't exist; correct forms `[OBSERVED` UsageScenarioReviewer]:
- `agent runs show --receipt` → `teaagent agent status <run_id> --evidence --human`.
- `audit export --audit-log <run_id>` → `teaagent audit export <run_id> [--output PATH]`.
- `@hook_registry.register('before_tool_call')` → `HookRegistry.register_pre_hook(...)` / `register_post_hook(...)` (integration-guide.md:291,295).
- Stale metric: harness-first doc says "650/650 acceptance"; current is 663 (D7).

## 4. Better ways to use (all verified PASS)

- **BU1** Prefer `teaagent setup` (guided; `--verify --write-env --context-profile`) over legacy `init`.
- **BU2** `teaagent daily … --dry-run --human`, `preflight`, `plan` — read-only, zero-model cockpit before spending.
- **BU3** `teaagent doctor config` prints per-key **source + precedence** (`[cli, env, env-file, config.json, config.toml, default]`) — kills "why is it read-only" confusion. (`config-lint`, `env-order` also exist.)
- **BU4** Extend via **hooks/plugins**, not forks: `HookRegistry.register_pre_hook/register_post_hook`; plugin tools via entry-point group `teaagent.tools` + `validate_plugin_tools`.
- **BU5** Verify-first: `teaagent audit verify`, `tool lint`, `doctor review-institution`.
- **BU6** Opt-in power: `agent run --validate --validation-profile {fast,standard,strict}` (post-run) and `--parallel N` (read-only tournament analysis).

## 5. Scenarios (all verified PASS)

- **S1 Owner-operator daily coding** (current truth): `setup → daily → preflight/plan → run → agent status <run> --evidence --human → undo/journal/cockpit/watch`.
- **S2 Co-maintainer agents** editing the harness under `agent-contribution-contract.md` (Active) — gated by docs validator + acceptance collect + ruff + mypy.
- **S3 Security reviewer** auditing runs — `audit verify/export`, `doctor config-lint/review-institution`, receipts. *(Note: some security guides use invalid flags — see §3c.)*
- **S4 Tool/plugin/provider author** — `tool lint`, `plugin {list,show,verify}`, authoring guides.
- **S5 MCP server for external IDE/agents** — `mcp serve` (stdio default; `--http` + OAuth). Present but adjacent to descoped external-integration territory.

## 6. Chief risk: discoverability-vs-safety (not insecure-by-default)

Panel U5 verdict: **no dormant surface auto-starts network I/O**; defaults are loopback,
non-loopback binds are *refused* without auth, and the default approval backend is
file-backed `[OBSERVED` CapabilityWiring]. The real exposure is **cognitive**: with 56
commands and 65 flags, an operator can enable WAN-exposing surfaces
(`gateway start`, `cloud submit`, `sync` signature relay, `mcp serve --http --host
0.0.0.0`) without realizing they opened an egress/attack surface. Supply-chain risk is
low at base install and rises with optional extras (`managed-*`, `playwright`, `redis`,
gateway SDKs). Recommendation: mark those four as explicit "WAN-exposure operations" in
operator docs; keep the harness-first default posture.

## 7. Recommendations (highest value first)
1. Reconcile §3b documented-but-uncalled features: either wire them or move them to a
   clearly-labeled "planned/experimental" section (honesty debt the harness-first
   docs-truth rule targets).
2. Fix §3c invalid documented surfaces in security/integration guides.
3. Add a one-screen "surface safety map" flagging WAN-exposing commands (§6).
4. Consider a `teaagent surfaces` extension that annotates each command's status
   (wired/shadow/descoped/deprecated) — turns the discoverability risk into a feature.

---

## Evidence actually checked
- **Executed:** `git log --reverse`; `teaagent --help` and subcommand `--help`
  (setup/daily/preflight/plan/doctor/agent run/mcp serve/consensus/cloud/gateway/sync);
  `scripts/validate_wiring.py --report`; env-flag + provider AST scans; module glob.
- **Read:** README.md, `harness-first-direction-2026-06-13.md`, product-principles/
  malleable-harness strategy docs, `agent-contribution-contract.md`, hooks.py,
  plugin_system.py, policy_engine.py/rbac.py, context_bus.py, validation/*, llm/_config.py.
- **Inferred (flagged):** the origin arc interpretation; "better usage" prioritization;
  risk severity. Corrected by four adversarial reviewers (verdicts: 4× AGREE WITH CHANGES).
- **Not executed:** no project-wide test run for this analysis; no code edited; reviewer
  claims about specific `file:line` call-sites were spot-checked, not exhaustively re-run.
