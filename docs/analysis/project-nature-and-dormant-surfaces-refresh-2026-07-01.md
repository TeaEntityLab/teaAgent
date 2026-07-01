# TeaAgent — Origins Deep-Dive, Wiring Refresh & Activation Playbook

> **Claim class:** Dated analysis (archive tier). **Refresh/delta companion** to
> [`project-nature-and-dormant-surfaces-2026-07-01.md`](./project-nature-and-dormant-surfaces-2026-07-01.md)
> (`9efe3b9`). Not a capability claim; not current-truth for roadmap/status
> (see [`docs/roadmap-status.md`](../roadmap-status.md)). Descoped/dormant items
> below are **not** shipped capability.
> **Date:** 2026-07-01 · **Anchor:** HEAD `55464d6` · branch `main` · version `0.1.0`
> **Trigger:** Owner request — "project goals from origins; per git logs + parallel
> discussion, what kind of project is this; leaked functions/features or better ways
> to use, and scenarios; log thoughts into docs." Also a verification pass reconciling
> the 2026-07-01 study after stub→real wiring (`c5f4130`, `9f5e461`) and the
> post-study security fixes (`6e4a1f1`, `37a5ed4`, `5316c50`, `55464d6`). Complements —
> does not supersede — the 2026-07-01 archive record.
> **Method:** Parallel-lens review packet + **five** adversarial read-only lenses
> (origins historian, wiring-refresh auditor, activation-playbook reviewer, evidence
> skeptic, strategic synthesis). Every load-bearing claim is `OBSERVED` (a command ran
> / a file was read) or `INFERENCE`. Panel corrections are folded in.

---

## Panel Consensus

- **Decision:** **AGREE WITH CHANGES** (5 lenses). The prior study's structure holds;
  this companion publishes the methodized corrections, deepens origins, and adds an
  activation playbook. Corrections below are mandatory and already folded in.
- **Use-case recommendation:** `study` ✅ · `reproduce` ✅ (governance/audit/wiring
  claims are command-verifiable) · `adopt` ✅ **owner-operator only** (single-user,
  local-first) · `deploy` ❌ multi-user/hosted/team (descoped per harness-first §1).
- **One recorded dissent** (EvidenceSkeptic): prefer *fixing the current-truth guides*
  over publishing a second analysis doc. Addressed two ways: (1) this doc is a
  **drift-correcting reconciliation record** (it supersedes the prior study's stale
  counts rather than forking a new narrative), and (2) the guide fixes are the **#1/#2
  ranked follow-ups** (§7) with exact `file:line`.

---

## 0. Corrections to the 2026-07-01 study (methodized — these supersede)

Published numbers reconciled by method at HEAD `55464d6` (EvidenceSkeptic + OriginsHistorian):

| Metric | Prior study | Corrected @ HEAD | Method / evidence |
|---|---:|---:|---|
| CLI top-level verbs | 56 | **60** | `teaagent --help` root choices (also 60 at `9efe3b9`; prior 56 was already stale). Reject "134" (raw `add_parser` incl. nested). Structured alts: 171 unique subparser names, 232 total argparse leaves. `[OBSERVED]` |
| `TEAAGENT_*` flags | 65 | **65** | Distinct tokens in `teaagent/**/*.py` (`rg`); 25 in `CONFIG_REGISTRY`. Prior 65 stands; a raw dir grep ("72") over-counts non-code/dup matches. `[OBSERVED]` |
| Optional extras | 21 | **20** | `pyproject.toml [project.optional-dependencies]`. `[OBSERVED]` |
| Providers | 14 | **14** | Confirmed (README correct; "15" was a reconstruction site). `[OBSERVED]` |
| First README commit | `b13ebbe` | **`f29cfb7`** (2026-05-09) | `b13ebbe` expanded the architecture doc; `f29cfb7` introduced the governance-first README. `[OBSERVED]` |
| Day-1 commits (2026-05-08) | ~implied | **59** | `git log --since/--until`. `[OBSERVED]` |
| P0 deferrals (MCP/OAuth/multi-agent) realized | "48–72h" | **same-day (hours)** | `docs/p0-scope.md` defers; same-day commits add them. `[OBSERVED]` |
| `validate_wiring` (reachable / unwired) | 312 / 9 (@ `1306ca7`) | **313 / 8** | Delta = `repo_map_benchmark` left the island (wired at `c1e7b50`). `[OBSERVED]` |
| Acceptance count (D7) | "650/650" (harness-first) | **663** | `docs/acceptance.md:45` = 663; `harness-first-direction-2026-06-13.md:53` still says 650/650 — **stale** (fix = §7). `[OBSERVED]` |

---

## 1. What kind of project — and goals from origins (git-substantiated)

**TeaAgent is a governance-first, local-first, provider-agnostic harness for autonomous
coding, scoped (since 2026-06-13) to a single owner-operator** who is simultaneously its
maintainer, daily user, and audit reviewer. (Full "what kind" treatment: prior study §1.)

**Founding goals, present from commit 1** `[OBSERVED` git log --reverse; OriginsHistorian]:
1. **Governance-first** — root commit `3244321` (2026-05-08): *"Establish governance-first
   P0 agent harness."* Not a later bolt-on.
2. **Model-agnostic / stdlib-first** — reject premature vendor-SDK lock-in; adapters isolated.
3. **Bounded runs** — iteration / tool-call / cost caps from P0.
4. **The harness is the platform** — orchestration + tool governance + audit, not a model wrapper.
5. **Agent co-maintenance as design** — `docs/agent-contribution-contract.md` (Active V4-a);
   the harness's first "external users" are other agents editing it (dogfooding).

**Is it "agent-built"?** Measurably *agent-assisted, increasingly so over time — not
whole-repo generated* `[OBSERVED` OriginsHistorian]: ~17% of 946 commits carry explicit
`Co-Authored-By` trailers (**≈160 Devin + ≈51 Claude**); **zero on day-1**; the
harness-first pivot commit itself (`ddd32f1`) carries `Co-Authored-By: Claude`. The
day-1 velocity (59 commits) and later structured `Constraint:`/`Tested:` trailers point
to an agent-assisted workflow, consistent with the project's own dogfooding thesis.
(Memory: a prior session found **no explicit external survey** inspired the project.)

## 2. Origins arc — 946 commits, 2026-05-08 → 2026-07-01 (corrected)

**Not two clean phases.** One governance-first harness with two *overlapping tracks*
from day one — (a) governance/security hardening and (b) surface-area expansion —
running in parallel throughout May–June `[OBSERVED` OriginsHistorian].

```
2026-05-08      Founding blitz — governance-first P0 + same-day surface expansion (59 commits)
2026-05-09..15  Day-2 polish; first README (f29cfb7); modularization; OAuth/DPoP/MCP HTTP
2026-05-16..22  Protocol + parity — LSP, subagents, hooks, plugins, Tree-sitter, GraphRAG,
                hybrid search, ANP/ACP/A2A adapters, AI Gateway; then competitive/daily-use docs
2026-05-24..27  Surface-area sprint (peak 56 commits on 05-27) — automation/scheduling, and a
                burst of numbered TASK-*/Phase-* features (numbering non-contiguous, some reused):
                git-checkpointing, VFS sandbox, time-travel replay, multi-sig quorum, Sigstore/
                ProvenanceGate, P2P broadcast, swarm orchestration, GraphRAG, context compaction
2026-05-28..29  Phase 4/5/6 push (consensus, swarm, hardened sandbox, control plane) interleaved
                with heavy audit-remediation waves (103 commits over two days)
2026-06-01..12  Consolidation; daily-driver/competitive-docs posture (reversed next week)
2026-06-13      PIVOT — owner-ratified harness-first identity (ddd32f1); external adoption/
                enterprise/team/hosted DESCOPED from current truth (docs/persona, not a code rip-out)
2026-06-14..30  "Align current truth" (8e0361b); ADR-0032 event-spine migration M1–M7; OKF docs;
                risk-register reconciliation; ADR-0040/0041 execution unification; CG-16 de-mock
2026-06-30..07-01  Stubs made real (c5f4130, 9f5e461); SEC-09/15/08/11 fixes; ADR-0041 Ph.2; ADR-0042
```

**The dormant surfaces are the residue of the 2026-05-24…29 surface-area sprint** — but
the causal story matters `[OBSERVED` OriginsHistorian, correcting the packet]: the
2026-06-13 pivot **descoped** external/enterprise/multi-agent surfaces from *docs
current-truth*; it did **not** rip A2A / OAuth / registry / federation out of the code.
Their dormancy is a **positioning decision**, separate from the handful of modules that
were simply never fully wired (§3).

## 3. Wiring refresh — dormancy delta at HEAD `55464d6`

`scripts/validate_wiring.py`: **reachable=313, unwired_watch=8, unlabeled=0** `[OBSERVED]`.
The 8 unwired (all labeled `experimental — unwired`): `consensus.consensus_validation`,
`governance.policy_routing`, `governance.scope_creep`, `update` (+ `.changelog`,
`.delta`, `.installer`, `.update`). **This companion does not restate the prior study's
L1–L17 table** — only the rows that changed or need nuance (WiringRefreshAuditor):

| Row / surface | Prior status (@ `1306ca7`) | Status @ HEAD `55464d6` | Evidence |
|---|---|---|---|
| **L10 Swarm review** | "partial — `run_code_reviews`/`select_best_result` dormant-path (tests only)" | **still dormant-path (tests only)** — `9f5e461` only replaced the mock `_review_subagent` body with an evidence-based heuristic; **did not** add production callers. `execute_swarm` sets `code_reviews=[]` and picks via `_select_tournament_winner`. | `swarm.py:717-718,748-752,1006-1068`; `rg` → tests only `[OBSERVED]` |
| **L1 Consensus** | "partial — only `consensus_validation.py` unwired" | **partial (unchanged classification); CLI/engine hardened** — `c5f4130` added `list_all_consensus()`, real `consensus history` + persisted `config set`. `consensus_validation` **still unwired** (ADR-0029, expiry 2026-12-10). | `consensus/engine.py`; `_handlers/_consensus.py:183-221`; `consensus_validation.py:3` `[OBSERVED]` |
| **`repo_map_benchmark`** | unwired island | **wired** into the release-eval path (first reachable at **`c1e7b50`**, *not* `9f5e461`); `9f5e461` = stub→real query + dropped the stale `experimental — unwired` label. | `governance/repo_map_benchmark.py:1-8`; bisect `[OBSERVED]` |
| **eval executor / env-lock / consensus CLI** | wired w/ placeholders | **stub bodies made real** inside already-reachable code (`c5f4130`) — `EvalRunner.model_runner` + `execution_mode`; real `generate_lockfile`; consensus history/config. | `eval_suite.py`, `env_config.py` `[OBSERVED]` |
| L2 policy / L3 routing / L4 scope-creep / L5 self-update / L6 A2A·ANP·ACP / L9 gateway | shadow / unwired / unwired / unwired / partial / descoped+wired | **all unchanged** | `h4_integration.py:82-120`; `unwired_watch` list `[OBSERVED]` |

**Load-bearing distinction (fold into any future reading):** *"stub made real" ≠
"surface activated."* The recent commits improved **stub bodies inside already-wired
code** (consensus CLI, eval executor, `repo_map_benchmark` query, `swarm._review_subagent`,
env-lock) — only `repo_map_benchmark` was a genuine *previously-unreachable → wired*
event (and at `c1e7b50`). **Swarm code-review remains a test-only API.**

*Caveat* `[INFERENCE]`: `validate_wiring` under-reports `teaagent.env_config` /
`cli._handlers._env` reachability (static resolver mis-maps `from ._env`); env-lock is
real at runtime — verify by `teaagent env lock`, not the import graph alone.

## 4. Activation playbook — better ways to use (spot-checked recipes)

For advanced/dormant-but-usable surfaces. Commands spot-checked via `--help` /
parser unless marked otherwise (ActivationPlaybookReviewer). **Do not** treat these as
default-path features; each is opt-in.

| # | Surface | Enable | Safety | Scenario | Watch-outs |
|---|---|---|---|---|---|
| A1 | Consensus / multi-sig | `consensus peers add`; `config set`; `request --wait`; opt. `relay serve/submit` | caution (high on WAN relay) | Co-sign destructive ops before a run | SSH keys; `--allow-dev-signatures` dev-only; token off-loopback |
| A2 | Federated sync export/import | `sync export\|import\|status` | safe | Move graph state between machines | back up `graphqlite.db`; JSON uncrypted |
| A3 | Sync signature relay | `sync signature-relay serve\|submit` | caution | Remote multi-sig w/o SSH hop | §6 WAN; TLS+mTLS; token leak |
| A4 | Cloud submit | `cloud capabilities`; `cloud submit` | caution (egress) | Offload to managed runtime | §6 egress; `managed-*` extras; data leaves host |
| A5 | MCP HTTP + OAuth | `mcp serve --http --auth-token` / `--oauth-*` | safe (loopback+auth) | IDE/agent bridge over HTTP | §6; origin allowlist; tool-plane exposure |
| A6 | Gateway (chat intake) | `gateway start --platform telegram` | caution | Phone intake for approvals | §6 outbound; untrusted chat input |
| A7 | Parallel tournament | `agent run --parallel N --permission-mode read-only`; `experiment compare/select` | safe read-only; caution on select | Compare N approaches before merge | git branches; N model calls |
| A8 | Git-sandbox checkpointing | `agent run --git-sandbox [--git-sandbox-auto-stash]`; `doctor git-sandbox --prune` | safe | Transactional rollback on destructive runs (see ADR-0042) | orphan branches; manual merge |
| A9 | Code ontology | `pip install .[graphqlite]`; `code-ontology build\|query` | safe (query) | Symbol/dependency map before refactor | `graphqlite` extra; rebuild needed |
| A10 | Hybrid search | `workspace_hybrid_index/search` tools via agent | caution (index writes DB) | Semantic+keyword repo search | no standalone CLI; index size |
| A11 | Replay / time-travel | `replay list\|steps\|fork\|resume` | safe inspect; caution resume | Debug from step N | `resume` can mutate workspace |
| A12 | Browser / Playwright | `pip install .[playwright]`; `playwright install` | caution | Web-UI verification | SSRF; browser binaries; egress |
| A13 | Hooks | `HookRegistry` via `ChatAgentConfig` (programmatic) | caution (veto power) | Path guards / post-tool lint | not CLI-wired; full tool power |
| A14 | Plugins | `.teaagent/plugins/`; `plugin list\|verify` | caution | Custom tools without a fork | supply-chain (RSK-10) |
| A15 | Distributed approval queue | `TEAAGENT_APPROVAL_COORDINATION_BACKEND=hybrid` + Redis env; `approval subagents` | safe (file default); caution (hybrid) | One queue for parallel-subagent approvals | Redis creds; HMAC key |
| A16 | Control-plane JIT | `control-plane serve --api-token` | safe (loopback+token) | Browser dashboard for JIT approvals | non-loopback needs token |

**DO NOT enable** (unwired / shadow / deprecated / refused) `[OBSERVED]`:
`governance.policy_routing`, `governance.scope_creep`, `consensus_validation`
integration (ADR-0029), `update/*` self-update (all unwired); `ultrawork` (deprecated);
`TEAAGENT_H4_POLICY_MODE=enforce` (policy is **shadow-only** — `evaluate_approval_policy_shadow`
always returns `True`; only `TEAAGENT_H4_RBAC_MODE=enforce` is real); `mcp serve --http
--host 0.0.0.0` without auth (handler refuses); `consensus relay --allow-dev-signatures`
in prod (dev hashes, not SSH — see SEC-15); `agent run --parallel N` without a read-only
mode (handler rejects).

### WAN-exposure map (§6 of prior study, with default ports) `[OBSERVED]`

| Op | Direction | Default bind | Auth | Verdict |
|---|---|---|---|---|
| `gateway start` | outbound | — | bot tokens | caution |
| `cloud submit` | outbound | — | provider creds | caution |
| `sync signature-relay serve` | inbound | `127.0.0.1:8791` | `--api-token` off-loopback | safe if loopback |
| `consensus relay serve` | inbound | `127.0.0.1:8790` | `--api-token` off-loopback | safe if loopback |
| `mcp serve --http` | inbound | `127.0.0.1:7330` | refused w/o token/OAuth | safe if loopback |
| `control-plane serve` | inbound | `127.0.0.1:8765` | `--api-token` | safe if loopback |

**No dormant surface auto-starts network I/O**; defaults are loopback and non-loopback
binds are refused without auth. The real exposure is **cognitive**: 60 commands / 65
flags let an operator open an egress/attack surface without realizing it.

## 5. Scenarios (owner-operator; extends prior study S1–S5)

- **Baseline daily loop** (current truth): `setup → daily --dry-run → preflight/plan →
  run → agent status <run> --evidence --human → undo/journal`.
- **Destructive-run safety net:** A8 git-sandbox checkpoint + A16 control-plane JIT for
  reviewed approvals; ADR-0042 sets the shell-mutation reversibility boundary.
- **Pre-refactor understanding:** A9 code-ontology + A10 hybrid search before touching code.
- **Compare approaches:** A7 read-only parallel tournament, then promote the winner.
- **Cross-machine continuity:** A2 sync export/import (sneakernet), not a hosted service.
- **External bridge (edge of scope):** A5 MCP-HTTP for an IDE; A6 gateway for phone
  approvals — both WAN-adjacent; keep loopback + auth.

## 6. Disagreements / Residual risks

- **Dissent (EvidenceSkeptic):** a second analysis doc risks count-drift and duplicates
  the archive record; the repo's pattern is *archive study + fix current-truth guides*.
  → Mitigated here by publishing methodized corrections (§0) and headlining the guide
  fixes (§7). If the owner prefers, treat §0/§7 as the payload and this narrative as
  disposable scaffolding.
- **"Made real" ≠ "activated"** — the single biggest misread risk (swarm review, L10).
- **`consensus_validation`** stays unwired under ADR-0029 (**expiry review 2026-12-10**):
  decide wire-behind-approval-queue vs delete.
- **`validate_wiring` static-resolver gap** on relative imports (env-lock under-reported).
- **Panel access caveat:** the `local://` packet did not resolve inside subagents; each
  lens independently reproduced the numbers from its assignment + its own commands
  (which is why the counts were corrected). `[INFERENCE` on cause]

## 7. Recommendations (ranked; highest value first)

1. **Reconcile D1–D6 documented-but-uncalled** (prior study §3b, re-confirmed zero
   prod callers at HEAD): wire, or relabel README as planned/experimental —
   `get_failure_warnings` (`chat_commands.py:213`), pin indicator (`tui/core.py:~1515`),
   CLI auto-refresh (`FileWatcher` TUI-only, `tui/core.py:603`), LSP `--validate`
   (`ValidationRunner` uncalled), pre-commit validation (post-run only), `archive_to_rag`
   (`context_bus.py:350`).
2. **Fix §3c invalid documented surfaces:** `agent runs show --receipt` → `agent status
   <run> --evidence --human`; stale `--audit-log` at `docs/cli.md:927` (+ security/
   onboarding guides); `@hook_registry.register(...)` → `HookRegistry.register_pre_hook/
   register_post_hook` at `docs/api/integration-guide.md:291-295`.
3. **Fix D7 stale acceptance count** (`harness-first-direction-2026-06-13.md:53` 650/650
   → 663) — **constitution-tier, requires Human Review**.
4. **WAN-exposure callout** in a working-tier operator runbook (the §4 map).
5. *(demoted)* a `teaagent surfaces` status command that annotates each command
   (wired/shadow/descoped/deprecated) — nice-to-have, no implementation exists today.

---

## Evidence actually checked

- **Executed:** `git log --reverse/--since/--until --date=short`, `git show --stat`
  (`c5f4130`, `9f5e461`), `git rev-list --count/--max-parents=0`, `validate_wiring.py`
  (HEAD and bisected to `1306ca7`), `teaagent --help` + subcommand `--help`
  (consensus/sync/cloud/mcp/gateway/replay/code-ontology/experiment/plugin/approval/
  control-plane/agent run), env-flag/provider/`add_parser` scans, `rg` call-site checks.
- **Read:** prior study `9efe3b9`, `harness-first-direction-2026-06-13.md`,
  `p0-scope.md`, `agent-contribution-contract.md`, `swarm.py`, `consensus/engine.py`,
  `governance/repo_map_benchmark.py`, `h4_integration.py`, `eval_suite.py`,
  `env_config.py`, README/CLI/integration guides.
- **Inferred (flagged):** origins interpretation; "agent-assisted" characterization
  (bounded by the 17% trailer count); risk severity; env-lock resolver-gap cause.
- **Not executed:** no project-wide test run; no live gateway/cloud/relay/Playwright/
  Redis; no code edited by this analysis. Reviewer `file:line` claims were spot-checked,
  not exhaustively re-run.
