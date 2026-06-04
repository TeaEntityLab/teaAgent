# Risk Register & Threat Model — teaagent
**Date:** 2026-06-02  
**Branch:** fix/task-dd2-001-initial-task-passthrough  
**Scope:** Full system — CLI, TUI, REPL, MCP, subagents, Docker, audit, OAuth, approval, budget  
**Sources:** security-risk-assessment-2026-06-02.md · defeat-scenarios-and-cascade-effects-2026-06-02.md · dependency-audit-and-security-2026-06-02.md · agent-enterprise-security-risks-2026-05-31.md · docs/threat-model.md · static source analysis

---

## Executive Summary

teaagent is a governance-first AI agent harness with strong policy enforcement, a 5-loop governance architecture, and a comprehensive approval system. The security posture is solid at the policy layer but has specific high-severity gaps at the audit, isolation, and budget layers. **Four findings are no-go for production expansion** (SEC-01, SEC-02, SEC-04, SEC-07). Three additional findings involve active security boundary violations in currently-deployed code (DS-12, SEC-06, SEC-10).

| Severity | Count | Immediately Blocking |
|---|---|---|
| Critical | 1 | Yes (SEC-01) |
| High | 8 | Partial (SEC-02, SEC-04, SEC-07, DS-12) |
| Medium | 10 | No |
| Low | 5 | No |
| **Total** | **24** | |

---

## Part 1 — Risk Heat Matrix

```
         IMPACT
              Low │ Medium │  High │ Critical
         ─────────┼────────┼───────┼─────────
 High    │        │ SEC-12 │SEC-07 │  SEC-01
 L       │        │ SEC-13 │SEC-06 │
 I       │ SEC-16 │ DS-04  │DS-12  │
 K       │        │        │SEC-02 │
 E       │ SEC-14 │ SEC-09 │SEC-04 │
 L       │        │        │SEC-05 │
 I       │        │        │SEC-03 │
 H       │        │ SEC-08 │SEC-10 │
 O       │        │ DS-13  │DS-05  │
 O       │        │ DS-06  │DS-08  │
 D       │ SEC-15 │ DS-09  │DS-11  │
 ─────────┴────────┴───────┴─────────
           Low    │ Medium │  High
```

### Quadrant summary
- **Critical/High (top-right):** SEC-01 audit chain forgeable; fix immediately
- **High/High:** SEC-07 Docker root+network, SEC-06 JIT escalation, DS-12 empty-path global grant
- **Certain/High:** SEC-04 unlimited cost default; SEC-02 expired MCP trust not enforced
- **Medium/Medium:** SEC-09 replay window, SEC-08 directory-snapshot no OS isolation, DS-13 zero-cap

---

## Part 2 — Risk Register

Each row: **ID · Category · Description · Likelihood (H/M/L) · Impact (H/M/L) · Risk Score (Likelihood×Impact: HH=9, HM=6, MM=4, etc.) · Mitigation Status · Priority**

### 2.1 Security Findings (SEC-*)

| ID | Category | Description | L | I | Score | Status | Priority |
|---|---|---|---|---|---|---|---|
| SEC-01 | Audit Integrity | HMAC key is ephemeral — audit chain unverifiable across restarts; SHA-256 recomputable by attacker with write access | H | H | 9 | **OPEN** | P0/Blocker |
| SEC-02 | Access Control | MCP server trust `expires_at` never checked at call time; `is_server_trust_expired()` is dead call — expired servers remain trusted indefinitely | H | H | 9 | **OPEN** | P0/Blocker |
| SEC-03 | Permission | Historical: `allow_all_destructive=True` short-circuited the approval gate outside explicit full-access mode. Current branch blocks it in `prompt` mode and requires explicit broad-mode promotion for bypass callers. | L | H | 3 | **FIXED / WATCH** | P1 |
| SEC-04 | Budget | `ChatAgentConfig.max_estimated_cost_cents` defaults to `0`, interpreted as "no cap" (`runner/_core.py:142`); runaway loop or prompt injection has no cost ceiling | H | H | 9 | **OPEN** | P0/Blocker |
| SEC-05 | Budget | Cost accounting reads `context['_cost_cents']` written by the LLM adapter — injectable by malicious adapter or prompt-injected response | L | H | 3 | **OPEN** | P2 |
| SEC-06 | Permission | Bidirectional JIT session approval sync leaks parent-approved tools to subagents via shared `jit_state`; subagent inherits `workspace_run_shell_mutate` without fresh approval | M | H | 6 | **OPEN** | P1 |
| SEC-07 | Isolation | Docker subagent runs as root, no `--network none`, no `--cap-drop ALL`, no seccomp — allows exfiltration and container escape | H | H | 9 | **OPEN** | P0/Blocker |
| SEC-08 | Isolation | `directory-snapshot` mode provides only filesystem isolation, not process isolation — agent reads `/etc/`, `/proc/`, `~/.ssh/`, spawns host processes | H | M | 6 | **OPEN** | P1 |
| SEC-09 | Multi-sig | Multi-sig approval hash uses 1-hour time bucket (`int(time.time()/3600)`); captured signature replayable for up to 59:59 within same window; hash logic duplicated in two files | M | M | 4 | **OPEN** | P2 |
| SEC-10 | Shell | `cat`, `head`, `tail` in `_INSPECT_EXECUTABLES` — classified as read-only inspect but can read `~/.ssh/id_rsa`, `.env`, `/etc/shadow` | H | H | 9 | **OPEN** | P1 |
| SEC-11 | Undo | `UndoJournal._PATH_WRITE_TOOLS` covers file tools only; `workspace_run_shell_mutate` not tracked — UI shows "undo available" but shell side-effects are unrecoverable | H | M | 6 | **OPEN** | P2 |
| SEC-12 | Audit | `os.fsync()` failure caught and silenced; audit degrades to in-memory only with no operator notification; disk-full attack eliminates all log persistence | L | M | 2 | **OPEN** | P2 |
| SEC-13 | Testing | Critical security paths (cost tracking, audit HMAC, approval denial) mocked out in tests — bugs live undetected (confirmed: CG-03 lived months this way) | H | M | 6 | **OPEN** | P1 |
| SEC-14 | Permission | `preapproved_call_ids` deprecated but still functional — old integrations or adversarial callers can pre-approve arbitrary call IDs without HMAC digest verification | L | L | 1 | **OPEN** | P3 |
| SEC-15 | Multi-sig | `TEAAGENT_ALLOW_DEV_SIGNATURES=1` accepts SHA-256 of `(message+pubkey)` as valid signature; no runtime guard prevents this in production WAN deployment | L | M | 2 | **OPEN** | P2 |
| SEC-16 | Code Quality | Dead code at `budget_monitor.py:104-119` after early return — maintenance hazard that could accidentally activate on refactor | H | L | 3 | **OPEN** | QW |

### 2.2 Defeat Scenario Findings (DS-*)

| ID | Category | Description | L | I | Score | Status | Priority |
|---|---|---|---|---|---|---|---|
| DS-12 | Permission | Empty-path approval creates implicit global workspace grant; user believes they granted path-scoped access; audit log records it as "path-scoped" masking the expansion | M | H | 6 | **OPEN** | P1 (Security) |
| DS-13 | Budget | `0` cost cap has three incompatible semantics: parser sentinel, runtime "unlimited", REPL default-fill `1000`; `--max-estimated-cost-cents 0` silently removes cap | M | M | 4 | **OPEN** | P2 |
| DS-01 | Budget | TUI `_session_cost_cents` never incremented — `/cost` and budget bar always show `$0.00`; per-run cap still fires but cumulative cap never triggers | H | M | 6 | **OPEN** | P1 |
| DS-05 | Undo | TUI `/undo` calls `git stash pop` (broadcast restore); REPL `/undo` calls `UndoJournal.restore()` (surgical) — same command word, different blast radius; TUI can destroy manual edits irreversibly | M | H | 6 | **OPEN** | P2 |
| DS-09 | UX/Security | `agent run --background <uuid>` silently runs the UUID as a literal task string, spawning a real LLM call that spends money on nonsense | H | M | 6 | **OPEN** | P1 |
| DS-04 | Audit | Stale `audit_trail` dict in suspension JSON predates CG-10 fix; forensic tooling may prefer the stale copy over the real RunStore events | M | L | 2 | **OPEN** | P3 |
| DS-06 | Testing | TUI cost test injects `_session_cost_cents` directly, tests formatter only — accumulation bug CG-11 permanently masked from CI | H | M | 6 | **OPEN** | P1 |

### 2.3 Supply Chain Findings (SC-*)

| ID | Category | Description | L | I | Score | Status | Priority |
|---|---|---|---|---|---|---|---|
| SC-01 | Dependencies | Two alpha packages in production lock (`opentelemetry-exporter-gcp-logging==1.12.0a0`, `opentelemetry-resourcedetector-gcp==1.12.0a0`) can break between lock refreshes | M | L | 2 | **OPEN** | P2 |
| SC-02 | Dependencies | `anthropic` SDK and `pyyaml` imported at runtime but undeclared in `pyproject.toml` — silent `ImportError` on installs without `google-cloud-aiplatform` or `pre-commit` | H | M | 6 | **OPEN** | P1 |
| SC-03 | Dependencies | `aiohttp` and `mcp` SDK in lock as orphans — not declared, not imported in core; add 22 transitive packages to attack surface unnecessarily | H | L | 3 | **OPEN** | P2 |

---

## Part 3 — STRIDE Threat Model

### 3.1 Core Flows Analyzed

1. **CLI → Runner loop** — user invokes `teaagent chat/agent`, task dispatched to LLM, tool calls evaluated against ApprovalPolicy, results written to audit
2. **Subagent spawn** — parent runner creates child runner with isolation mode, shares or copies JIT state, approvals delegated via queue
3. **MCP tool dispatch** — external MCP server registered, tools filtered by trust policy, calls forwarded
4. **Approval gate** — tool call hits policy check, user prompted (prompt mode), multi-sig quorum assembled (WAN mode)
5. **Audit write** — JSONL event written with SHA-256 hash chain and per-run HMAC

---

### 3.2 STRIDE Table

#### S — Spoofing

| Threat | Affected Component | Current Mitigation | Gap | Severity |
|---|---|---|---|---|
| S-1: Agent impersonation in multi-agent federation | `MultiSigQuorumConfig`, `peer_agent_ids` | `agent_id` string field | No cryptographic agent identity credential; string `agent_id` trivially forged (SEC-NEW1) | HIGH |
| S-2: Rogue MCP server spoofs trusted server identity | `mcp_trust.py` | Per-server `trusted=True` + filter hooks | Trust anchored to URL/name, not certificate; MCP loopback has no auth by default | HIGH |
| S-3: Prompt injection masquerades as user instruction | Model output → tool dispatcher | Approval gates block execution of suspicious tool sequences | No formal prompt injection detection layer before tool dispatch (SEC-NEW2) | HIGH |
| S-4: `allow_dev_signatures` accepts fake SSH signatures | `security_env.py:12-14` | Dev-only flag with warning | No production guard when relay URL is non-loopback (SEC-15) | MEDIUM |

#### T — Tampering

| Threat | Affected Component | Current Mitigation | Gap | Severity |
|---|---|---|---|---|
| T-1: Audit log event modification | `.teaagent/runs/*.jsonl` | SHA-256 hash chain + HMAC | HMAC key ephemeral — attacker can recompute chain after modifying events (SEC-01) | CRITICAL |
| T-2: Cost field injection via adapter context | `runner/_core.py:322-325` | None | `context['_cost_cents']` writable by adapter — prompt injection can zero it (SEC-05) | HIGH |
| T-3: Suspension JSON audit_trail field vs RunStore divergence | `chat_repl.py` | RunStore is authoritative; stale direct resume hint removed in current branch | Full resume rehydration still needs explicit continuity support (DS-04/DS-09) | LOW |
| T-4: Config file sets `allow_all_destructive=true` | `approval_manager.py` | Prompt-mode bypass is blocked; bypass callers must use explicit broad permission mode | Config schema should still reject or warn on broad-mode persistence (SEC-03) | MEDIUM |
| T-5: Stash conflict corrupts workspace in parallel sandboxes | `git_sandbox.py` | `stash_save` returns specific reflog selector | Already fixed in prior audit (stash@{0} hardcode) | LOW (Fixed) |

#### R — Repudiation

| Threat | Affected Component | Current Mitigation | Gap | Severity |
|---|---|---|---|---|
| R-1: Agent denies performing a tool call | `AuditLogger` | JSONL + hash chain records all tool dispatches | Chain is forgeable when HMAC key is ephemeral (SEC-01) | CRITICAL |
| R-2: Subagent denies inheriting parent approvals | Per-agent JIT approval scope | `_agent_approved_tools` is per-agent | Bidirectional sync leaks approvals without explicit grant record (SEC-06) | MEDIUM |
| R-3: Suspension JSON recorded but resume never executed | `chat_repl.py:77-94` | N/A | Suspension write is confirmed; resume path always errors (DS-08/AG-01) | MEDIUM |
| R-4: Empty-path grant recorded as "path-scoped" | Approval store | None | Audit log misleads post-incident review (DS-12) | HIGH |

#### I — Information Disclosure

| Threat | Affected Component | Current Mitigation | Gap | Severity |
|---|---|---|---|---|
| I-1: SSH key / `.env` file read via inspect-classified shell | `workspace_tools/_shell.py:175-176` | Read-only classification | `cat`, `head`, `tail` in `_INSPECT_EXECUTABLES` — can read secrets (SEC-10) | HIGH |
| I-2: Audit L3 plaintext secrets on disk | `audit.py` | L0/L1/L2 redaction | L3 writes unredacted tool arguments; doc says "encrypted" but doesn't encrypt (AS-6) | HIGH |
| I-3: Subagent exfiltrates data via Docker network | `subagents/_isolation.py:222-243` | Workspace volume read-only mount | No `--network none` — full internet access from container (SEC-07) | HIGH |
| I-4: Cost data visible in model adapter context dict | `runner/_core.py:322` | None | Any code reading `context` can observe billing data | LOW |
| I-5: Orphaned suspension files accumulate | `chat_repl.py:77` | None | Files with session observations never cleaned up, remain accessible | LOW |

#### D — Denial of Service

| Threat | Affected Component | Current Mitigation | Gap | Severity |
|---|---|---|---|---|
| D-1: Runaway LLM loop exhausts API budget | `runner/_core.py:142` | `RunBudget` caps per-run | Default `max_estimated_cost_cents=0` = unlimited (SEC-04) | HIGH |
| D-2: Disk-full attack silences audit writes | `audit.py:298-307` | In-memory fallback | No operator notification; all events lost at process exit (SEC-12) | MEDIUM |
| D-3: UUID-as-task bogus run spends real API budget | `_agent.py:145-146` | None | `agent run --background <uuid>` runs UUID as literal task (DS-09) | MEDIUM |
| D-4: Zero budget cap interpreted as unlimited | `runner/_core.py:142`, `chat_repl.py:255` | None | `--max-estimated-cost-cents 0` removes cap (DS-13) | MEDIUM |
| D-5: Alpha OTel GCP packages break on lock refresh | `uv.lock` | None | Two alpha packages can introduce breaking changes between `uv lock --upgrade` (SC-01) | LOW |

#### E — Elevation of Privilege

| Threat | Affected Component | Current Mitigation | Gap | Severity |
|---|---|---|---|---|
| E-1: Subagent inherits parent session approvals | `policy.py:110-135` | Per-agent JIT scope | Bidirectional `jit_state` sync — child gets parent's approved tools (SEC-06) | HIGH |
| E-2: Empty-path approval expands to global workspace access | `ApprovalManager` | None | Missing path defaults to "match all paths" (DS-12) | HIGH |
| E-3: Docker subagent escalates as root in container | `subagents/_isolation.py:223` | None | `--user` flag absent; container runs UID 0 (SEC-07) | HIGH |
| E-4: `directory-snapshot` subagent reads host sensitive paths | `subagents/_isolation.py:181-200` | Deprecation warning | No process isolation; can read `~/.ssh/`, env vars (SEC-08) | MEDIUM |
| E-5: Expired MCP server retains tool access | `mcp_trust.py:141-149` | `is_server_trust_expired()` defined | Function never called in hot path (SEC-02) | HIGH |
| E-6: `allow_all_destructive=True` bypasses entire permission model | `approval_manager.py` | Fixed in current branch: prompt mode blocks the flag even with acknowledgement metadata | Broad modes still need entry ceremony, audit, and persistence warnings (SEC-03 follow-up) | MEDIUM |

---

## Part 4 — Attack Surface

### 4.1 Entry Points

| Entry Point | Description | Auth Required | Trust Level | Notes |
|---|---|---|---|---|
| **CLI** (`teaagent chat/agent/run`) | Primary human interface; parses args, dispatches to runner | None (local process) | Implicit operator trust | Initial task silently dropped (DS-11 — partially fixed) |
| **TUI** (`teaagent tui`) | Interactive terminal UI; bypasses `ChatSessionController` | None (local) | Operator trust | Entire controller layer bypassed (DS-02/CG-12) |
| **REPL** (`teaagent chat`) | Read-eval-print loop with slash commands | None (local) | Operator trust | Suspension resume chain broken (DS-08, DS-09) |
| **MCP stdio** | Local MCP server via stdio; tools registered to agent | None by default | Configurable via `mcp_trust.py` | Loopback has no auth default (AS-4) |
| **MCP HTTP** | Remote MCP over HTTP/SSE; bearer auth optional | Bearer token when `TEAAGENT_STRICT_LOCAL=1` | Configurable | Auth not enforced by default |
| **JIT Approval HTTP server** | SSE server for remote approval collection | None specified | Peer agents | Race condition on approve/reject (prior fix) |
| **Docker subagent** | Spawned container running subagent code | Parent process | Supposed isolation | Root + full network (SEC-07) |
| **Plugin entry points** | Python entry points registered by installed plugins | Plugin verify gate | Reviewed | Fail-open without `TEAAGENT_PLUGINS_STRICT=1` |
| **Git sandbox** | Worktree/branch isolation for parallel agents | None (local git) | Isolated workspace | Fixed stash selector (prior); NFS unsupported |
| **OAuth 2.1/DPoP gateway** | `gateway_oauth.py` / `oauth21/` — token exchange for multi-tenant | DPoP-bound tokens | Authenticated | Full OAuth 2.1 implementation with replay protection |
| **Context Bus (SQLite)** | Cross-sandbox delta sharing via SQLite | File permissions | Same host only | WAL + per-thread connections; NFS not supported |
| **Audit log JSONL** | `.teaagent/runs/*.jsonl` | File permissions | Local FS | Forgeable without persistent HMAC key (SEC-01) |
| **Suspension JSON** | `suspension-{id}.json` in workspace | File permissions | Local FS | Stale, never read by resume path (DS-10) |

### 4.2 Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│  TRUSTED: teaagent harness (Runner, Policy, Audit, built-in tools)│
│  Owner: teaagent process                                        │
├────────────────────────────┬────────────────────────────────────┤
│  REVIEWED: project plugins │  REVIEWED: MCP servers             │
│  manifest + human enable   │  trust policy + filter hooks       │
│  Fail-open without strict  │  Expiry not enforced (SEC-02)      │
├────────────────────────────┴────────────────────────────────────┤
│  UNTRUSTED: Model output / LLM response                         │
│  External MCP payloads                                          │
│  Arbitrary plugin handlers                                      │
│  Content read from workspace files (prompt injection vector)    │
├─────────────────────────────────────────────────────────────────┤
│  EXTERNAL: Anthropic API / model provider                       │
│  (Trusted for computation; cost data should NOT be from here)  │
└─────────────────────────────────────────────────────────────────┘

Boundary violations:
  - JIT state bidirectional sync crosses TRUSTED → UNTRUSTED (SEC-06)
  - cat/head/tail in INSPECT crosses filesystem trust boundary (SEC-10)
  - Docker container has network access crossing isolation boundary (SEC-07)
  - Empty-path grant crosses path-scoped → global boundary (DS-12)
```

### 4.3 Attacker Personas

| Persona | Entry Vector | Capability | Primary Targets |
|---|---|---|---|
| **Prompt-injected content** | File read, web fetch, MCP response | Craft model input causing tool calls | Escalate permissions, exfiltrate credentials, exceed budget |
| **Rogue subagent** | Spawned with weaker isolation or shared JIT | Inherit parent approvals, escape sandbox | Unauthorized writes, lateral movement to host filesystem |
| **Compromised MCP server** | Gained `trusted=True`; trust expires but check never runs | Execute all `allowed_tools` after TTL lapses | Persistent access, data exfiltration |
| **Local attacker** (same machine) | Write access to `.teaagent/runs/` | Modify JSONL, recompute SHA-256 chain | Forge audit log, delete evidence of malicious runs |
| **Peer signature attacker** | Captured valid approval signature | Replay within 1-hour time bucket | Authorize high-risk operations without fresh consent |
| **Config/template attacker** | Write `.teaagent/config.json` with `allow_all_destructive: true` | Activate total permission bypass | Unlimited destructive tool access without any approval gate |
| **Supply chain attacker** | Publish malicious package update to PyPI | Code execution at import time | Full agent compromise on `uv lock --upgrade` |

---

## Part 5 — Mitigation Roadmap

### 5.1 Already Mitigated (in current code)

| Risk | File:Line | Mitigation in Place |
|---|---|---|
| Shell command obfuscation bypass | `teaagent/workspace_tools/_shell.py` (multi-pass normalize) | Multi-pass `_normalize_shell_arg`: quotes, backticks, `$()`, brace expansion, process substitution |
| Path traversal / symlink escape | `teaagent/workspace_tools/` | Workspace path resolution + protected paths enforcement |
| Prompt injection → destructive execution | `teaagent/approval_manager.py` | 5 permission modes; ApprovalPolicy blocks execution; policy-as-code deny rules |
| Git stash cross-agent contamination | `teaagent/git_sandbox.py` | `stash_save` returns specific reflog selector (`stash@{N}` not hardcoded) |
| JIT approval server event-loop blocking | `teaagent/jit_approval_server.py` | `async def _wait_for_approval` with `asyncio.wait_for` (not `time.sleep`) |
| Workflow self-healing infinite recursion | `teaagent/runner/` | `current_attempt` parameter preserved; max attempt guard before recursion |
| Parallel branch contamination | `teaagent/git_sandbox.py`, worktree isolation | Main-branch writes blocked in tournament mode |
| Protected directory alternate-path bypass | `teaagent/workspace_tools/` | `workspace_write_*` pattern + `.git*` argument pattern covers subdirectories |
| Swarm thread deadlock | `teaagent/swarm.py` | Thread-ref liveness check replaces PID-based check; heartbeat monitor via thread |
| OAuth DPoP replay | `teaagent/oauth21/_replay.py` | DPoP nonce replay store with configurable window |
| Bearer token at rest | `teaagent/surface_auth.py` | Tokens hashed at load; chmod 600 guidance in docs |
| Plugin supply chain (with strict flag) | `teaagent/plugins.py` | Verify/install gates; `TEAAGENT_PLUGINS_STRICT=1` fails closed |
| Context Bus SQLite lock contention | `teaagent/context_bus.py` | Per-thread connections, WAL, exponential backoff, generation-based reconnect |
| Workflow rollback not executed | `teaagent/runner/` | `requires_rollback` flag now consumed; triggers `UndoJournal.restore()` |
| MCP loopback auth (with env flag) | `teaagent/mcp_http/_oauth.py` | Bearer auth enforced when `TEAAGENT_STRICT_LOCAL=1` |

### 5.2 Open Risks by Priority

#### Priority 0 — No-go for production expansion (fix this sprint)

| Risk ID | Fix Description | File:Line | Effort |
|---|---|---|---|
| **SEC-01** | Persist HMAC key to `~/.teaagent/run-keys/<run_id>.key` (chmod 600); pass key to `verify_audit_chain()` in `audit_export.py:56` | `teaagent/audit.py:127`, `teaagent/audit_export.py:56` | S (1–2 days) |
| **SEC-02** | Add `is_server_trust_expired(server)` check in `merged_tool_filters()` at `mcp_trust.py:141`; add periodic policy reload every 60 s | `teaagent/mcp_trust.py:141-149` | S (1 day) |
| **SEC-04** | Change `ChatAgentConfig.max_estimated_cost_cents` default from `0` to `500` (or prompt on first run) | `teaagent/chat_agent.py:70` | XS (30 min) |
| **SEC-07** | Add to Docker command: `--user 65534:65534 --network none --cap-drop ALL --read-only --security-opt no-new-privileges` | `teaagent/subagents/_isolation.py:223-243` | S (2–4 hours) |

#### Priority 1 — Fix within sprint

| Risk ID | Fix Description | File:Line | Effort |
|---|---|---|---|
| **SEC-06** | Replace bidirectional `jit_state` sync with `clone_for_subagent()` (one-way: parent→child at spawn); never sync child→parent | `teaagent/policy.py:110-135` | M (3–5 days) |
| **SEC-10** | Remove `cat`, `head`, `tail` from `_INSPECT_EXECUTABLES`; use `workspace_read_file` tool instead | `teaagent/workspace_tools/_shell.py:175-176` | XS (15 min) |
| **SEC-13** | Add integration tests: full runner loop with stub adapter (real cost values); `verify_audit_chain` with correct/wrong HMAC key; test `is_server_trust_expired` is called in enforcement path | `tests/test_chat_agent.py` + new tests | M (3–5 days) |
| **DS-12** | Validate path-scoped approval has non-empty path; reject or default-fill to CWD with explicit confirmation; log scope expansion warnings | `teaagent/approval_manager.py` (path rule creation) | S (1–2 days) |
| **DS-09** | Fixed in current branch: remove the stale direct resume hint from REPL suspend output; print only the supported interactive-review path | `teaagent/cli/_handlers/chat_repl.py` (suspend output) | Done |
| **DS-06** | Fixed in current branch: TUI cost/session tests exercise runtime paths instead of only direct attribute injection | `tests/test_tui.py` | Done |
| **SEC-08** | Add runtime warning when `directory-snapshot` mode is selected: "No process isolation — not for untrusted content" | `teaagent/subagents/_isolation.py:181-200` | XS (30 min) |
| **SC-02** | Declare `anthropic>=0.40` in `[project.optional-dependencies]`; declare `pyyaml>=6.0` in `dependencies` | `pyproject.toml` | XS (30 min) |

#### Priority 2 — Fix within cycle

| Risk ID | Fix Description | File:Line | Effort |
|---|---|---|---|
| **SEC-03** | Fixed in current branch: prompt mode rejects `allow_all_destructive=True`; follow-up is prominent warning/audit ceremony for broad-mode entry | `teaagent/approval_manager.py` | Follow-up XS/S |
| **SEC-09** | Reduce time bucket from 3600 to 300 seconds; deduplicate hash function to single canonical location | `teaagent/approval_manager.py:393`, `teaagent/policy.py:379-398` | S (1–2 days) |
| **SEC-11** | When `workspace_run_shell_mutate` is in tool history, display explicit warning: "undo is partial — shell effects not reversed" | `teaagent/run_undo.py:48-55` | XS (2 hours) |
| **SEC-12** | On consecutive `fsync()` failures, emit stderr warning; after 3 failures, raise `BudgetExceededError` or halt | `teaagent/audit.py:298-307` | S (1 day) |
| **SEC-15** | Reject `TEAAGENT_ALLOW_DEV_SIGNATURES=1` when `multi_sig_config.enabled` and relay URL is non-loopback | `teaagent/security_env.py:12-14` | XS (1 hour) |
| **DS-13** | Use `None` as "no cap" sentinel instead of `0`; add explicit test for `--max-estimated-cost-cents 0` | `teaagent/runner/_core.py:142`, `teaagent/cli/_handlers/chat_repl.py:255` | S (1 day) |
| **DS-01** | Fixed in current branch: TUI cost accumulation is covered by runtime-path tests | `teaagent/tui/__init__.py` / `tests/test_tui.py` | Done |
| **DS-05** | After DS-02 (TUI controller migration): unified undo via controller | `teaagent/tui/__init__.py:641` | M (pending DS-02) |
| **SC-01** | Add `==` overrides to freeze two alpha GCP OTel packages in `[tool.uv]` | `pyproject.toml` | XS (15 min) |
| **SC-03** | Run `uv remove aiohttp mcp`; or declare `mcp` in `[project.optional-dependencies]` if intended | `uv.lock`, `pyproject.toml` | XS (30 min) |

#### Priority 3 — Backlog

| Risk ID | Fix Description | File:Line | Effort |
|---|---|---|---|
| **SEC-05** | Architecture: move cost tracking out of adapter context dict to side-channel (API response headers or tamper-resistant accounting layer) | `teaagent/runner/_core.py:322-325` | L (design decision required) |
| **SEC-14** | Remove `preapproved_call_ids` functionality in next major version; raise `ValueError` instead of `DeprecationWarning` | `teaagent/policy.py:101-107` | S (next major) |
| **SEC-16** | Delete dead code at `budget_monitor.py:104-119` | `teaagent/budget_monitor.py:104-119` | XS (10 min) |
| **DS-04** | Remove stale `audit_trail` dict from suspension JSON | `teaagent/cli/_handlers/chat_repl.py:89-93` | XS (10 min) |
| **SEC-NEW1** | Per-session Ed25519 key pair for agent identity; sign all outbound approval requests | New module required | L (2–3 weeks) |
| **SEC-NEW2** | Prompt injection detection layer: pattern-based + anomaly detection on tool call sequences | New module required | L (2–4 weeks) |
| **SEC-NEW3** | Behavioral contract document per deployment (YAML, human + machine readable, signed and stored with audit log) | New module required | L (3–4 weeks) |

---

## Part 6 — Residual Risk Assessment

After all Priority 0–1 mitigations are applied:

| Risk Area | Residual Risk | Acceptable? |
|---|---|---|
| **Audit chain integrity** | Per-run key persisted, chain verifiable; still no Sigstore-backed external verification | Acceptable for single-operator local use; NOT acceptable for multi-tenant or compliance deployments |
| **MCP trust expiry** | Expiry enforced at call time; 60 s reload cycle means max 60 s window of stale trust | Acceptable |
| **Cost unbounded** | Default 500 cents cap; operator can raise; unlimited via explicit `0`→`None` fix | Acceptable (informed operator choice) |
| **Docker isolation** | Root→UID 65534, no network, no caps, no new privs | Acceptable for code execution workloads; requires minimal image (python:3.11-slim still has a large surface) |
| **JIT approval inheritance** | One-way parent→child sync; no child→parent escalation | Acceptable |
| **Shell credential read** | `cat`/`head`/`tail` removed from inspect; `workspace_read_file` restricted to workspace root | Acceptable |
| **Subagent process isolation** | `directory-snapshot` deprecated/warned; Docker hardened | Acceptable with warnings |
| **Multi-sig replay** | 5-minute window; deduplicated hash | Acceptable for most deployments |
| **Audit disk failure** | Operator notified on fsync failure; halt after 3 | Acceptable |
| **Prompt injection** | No formal detection layer (SEC-NEW2 backlog) | **Not acceptable for high-security deployments** — mitigated by approval gates but not detected |
| **Agent identity** | String `agent_id` (SEC-NEW1 backlog) | **Not acceptable for federated/WAN deployments** |
| **Behavioral contracts** | No formal pre-run contract (SEC-NEW3 backlog) | **Not acceptable for compliance/enterprise** |

**Go / No-go summary after P0+P1 fixes:**
- ✅ Local single-operator development use: GO
- ✅ Small team with `permission_mode=prompt` and `audit_level=L2`: GO with documented caveats
- ⛔ Production multi-tenant or WAN federated: NO-GO until SEC-NEW1 (agent identity) resolved
- ⛔ Compliance-required enterprise deployment: NO-GO until SEC-NEW3 (behavioral contracts) and Sigstore audit signing resolved

---

## Part 7 — Monitoring and Controls

### 7.1 Detective Controls (current)

| Control | Mechanism | Gaps |
|---|---|---|
| Audit chain verification | `teaagent audit verify` / `audit_export.py:56` | HMAC not verified (SEC-01 fix required before this is meaningful) |
| Per-run spend reporting | `RunResult.cost_cents`, `runner/_core.py:142` | TUI always shows $0.00 (DS-01); cost injectable (SEC-05) |
| Approval grant store inspection | `ergonomics/approval_store.py` | Empty-path grants look identical to scoped grants (DS-12) |
| MCP trust policy view | `teaagent mcp trust list` | Trust expiry shown but not enforced at call time (SEC-02) |
| Git audit trail | `git log`, worktree isolation | Supplements but does not replace internal audit log |
| Budget warnings | `BudgetMonitor`; 80%/90% thresholds | Thresholds never fire when TUI cost is $0.00 (DS-01) |

### 7.2 Detective Controls to Add

| Control | What it detects | How |
|---|---|---|
| `pip-audit` in CI | New CVEs in dependency tree | Wire `security` optional group into CI pipeline |
| HMAC key rotation log | Key lifecycle events | Log `audit_key_created` event at run start after SEC-01 fix |
| fsync failure alert | Audit persistence degradation | Implement SEC-12 fix — stderr warning + halt |
| Empty-path grant alert | Accidental global scope widening | Log warning on grant creation after DS-12 fix |
| Cost anomaly detector | Runaway loops or prompt injection budget abuse | Compare per-run cost to session rolling average; alert >3σ |
| Docker flag audit | Container created without hardening flags | Assert expected flags in pre-flight check; fail if absent |
| MCP trust expiry monitor | Expired-but-trusted servers | Periodic scan of trust policy; log expired entries |

### 7.3 How to Detect Mitigation Failures

| Mitigation | Failure Mode | Detection Command |
|---|---|---|
| SEC-01 (HMAC persist) | Key not found at verify time | `teaagent audit verify <run_id>` → `invalid HMAC` error |
| SEC-02 (MCP expiry) | Expired server accepts calls | `teaagent mcp trust list` → `expires_at` in past but server active |
| SEC-04 (cost default) | Sessions run with no cap | `grep max_estimated_cost_cents ~/.teaagent/config.toml` → missing/0 |
| SEC-07 (Docker flags) | Container spawned without flags | `docker inspect teaagent-subagent-* --format='{{.HostConfig.SecurityOpt}}'` |
| DS-12 (empty-path grant) | Global grant in approval store | `grep '"path": ""' ~/.teaagent/approvals/*.json` |
| DS-01 (TUI cost) | Cost remains $0 after tasks | Compare TUI `/cost` to provider API dashboard |

---

## Part 8 — Compliance Mapping

### 8.1 NIST AI Agent Standards Initiative (Feb 2026)

| NIST Priority Area | teaagent Control | Status | Gap |
|---|---|---|---|
| Agent identity | `agent_id` string | ⚠️ Partial | No cryptographic credential (SEC-NEW1) |
| Per-action authorization | `ApprovalPolicy`, 5 permission modes | ✅ Implemented | Empty-path bug (DS-12) |
| Per-agent authorization scope | Per-agent JIT approval | ✅ Implemented | Bidirectional sync leak (SEC-06) |
| Audit trail | `AuditLogger`, hash chain | ⚠️ Partial | HMAC ephemeral (SEC-01) |
| Runtime visibility | TUI approval UI, CLI audit view | ⚠️ CLI only | No dashboard; cost display broken (DS-01) |
| Kill switch / halt | `RunCancelledError`, budget cap | ✅ Implemented | Default cap=0 (SEC-04) |
| Incident response | `teaagent undo`, `git_sandbox` | ⚠️ Partial | Shell mutations not tracked (SEC-11) |

### 8.2 SOC 2 Type II

| Control | Trust Services Criterion | Status | Gap |
|---|---|---|---|
| Logical access controls | CC6.1 | ✅ Permission modes implemented | `allow_all_destructive` bypass (SEC-03) |
| Network transmission security | CC6.6 | ✅ MCP HTTP auth, DPoP, TLS | Loopback MCP no-auth default (AS-4) |
| Encryption at rest | CC6.7 | ⚠️ L0/L1/L2 redaction | L3 claims encryption, writes plaintext (AS-6) |
| System monitoring | CC7.2 | ⚠️ Audit chain exists | Chain forgeable (SEC-01) |
| Vendor / third-party risk | CC9.2 | ⚠️ 0 CVEs, clean licenses | Alpha packages (SC-01); no model provider docs |

### 8.3 OWASP Top 10 (LLM Applications — 2025)

| OWASP LLM Risk | teaagent Exposure | Control |
|---|---|---|
| LLM01 — Prompt Injection | HIGH — file reads, MCP payloads, web content | Approval gates (but no detection layer — SEC-NEW2) |
| LLM02 — Insecure Output Handling | MEDIUM — shell mutations, file writes | Destructive approval required; plan-before-write mode |
| LLM03 — Training Data Poisoning | LOW — not a training context | N/A |
| LLM04 — Model DoS | MEDIUM — runaway loops | Budget cap; default cap=0 gap (SEC-04) |
| LLM05 — Supply Chain Vulnerabilities | MEDIUM — plugin system, 197 deps | Plugin gates; 0 CVEs; alpha packages (SC-01) |
| LLM06 — Sensitive Info Disclosure | HIGH — workspace file access, inspect tools | `cat`/`head`/`tail` gap (SEC-10); audit L3 plaintext (AS-6) |
| LLM07 — Insecure Plugin Design | MEDIUM — plugin tool manifest | Capability manifest "in progress" |
| LLM08 — Excessive Agency | HIGH — shell mutation, Docker, network | Permission modes; Docker no network isolation (SEC-07) |
| LLM09 — Overreliance | LOW — governance UX context | N/A |
| LLM10 — Model Theft | LOW — local API key usage | API key not transmitted to subagents by default |

### 8.4 Minimum Compliant Configuration

```toml
# .teaagent/config.toml — minimum viable secure deployment
[security]
permission_mode = "prompt"
audit_level = "L2"
require_plan = true
mcp_strict_local = true
plugins_strict = true

[budget]
max_cost_cents = 500     # $5 hard cap (after SEC-04 fix; never use 0)
warn_at_pct = 50

# Required environment variables
# TEAAGENT_ALLOW_DEV_SIGNATURES=0
# TEAAGENT_STRICT_LOCAL=1
# TEAAGENT_PLUGINS_STRICT=1
```

---

## Part 9 — Prioritized Action List

### Sprint 1 (this week) — Blockers

1. **SEC-01** — Persist HMAC key to `~/.teaagent/run-keys/<run_id>.key`; pass to `verify_audit_chain()` — `teaagent/audit.py:127`, `teaagent/audit_export.py:56`
2. **SEC-02** — Call `is_server_trust_expired()` in `merged_tool_filters()` at `mcp_trust.py:141`
3. **SEC-04** — Change default `max_estimated_cost_cents` from `0` to `500` — `teaagent/chat_agent.py:70`
4. **SEC-07** — Add `--user 65534:65534 --network none --cap-drop ALL --read-only --security-opt no-new-privileges` to Docker command — `teaagent/subagents/_isolation.py:223-243`
5. **SEC-10** — Remove `cat`, `head`, `tail` from `_INSPECT_EXECUTABLES` — `teaagent/workspace_tools/_shell.py:175-176`
6. **SEC-16** — Delete dead loop at `budget_monitor.py:104-119` (QW — 10 min)
7. **DS-09** — Fixed in current branch: stale `--background <id>` hint removed from REPL suspend output
8. **SC-02** — Declare `anthropic` and `pyyaml` in `pyproject.toml` (XS — 30 min)

### Sprint 2 — High priority

9. **DS-12** — Validate non-empty path on path-scoped approval; reject empty or confirm-expand
10. **SEC-06** — `clone_for_subagent()` one-way JIT state sync
11. **SEC-13** — Integration tests: real cost path, HMAC verify, trust expiry enforcement
12. **DS-06** — Fixed in current branch: TUI cost test exercises runtime path
13. **DS-01** — Fixed in current branch: TUI cost accumulation stop-gap is covered
14. **SEC-08** — Add runtime warning for `directory-snapshot` mode
15. **SC-01** — Freeze alpha GCP OTel packages with `==` overrides in `[tool.uv]`
16. **SC-03** — `uv remove aiohttp mcp` (or declare intentional)

### Sprint 3 — Medium priority

17. **SEC-03** — Fixed in current branch: prompt mode blocks `allow_all_destructive`; follow-up is broad-mode entry ceremony/audit
18. **SEC-09** — Reduce multi-sig time bucket to 300 s; deduplicate hash function
19. **SEC-11** — UI warning when undo is partial (shell mutations in run)
20. **SEC-12** — fsync failure: stderr warning + halt after 3 failures
21. **SEC-15** — Reject `TEAAGENT_ALLOW_DEV_SIGNATURES=1` on non-loopback relay
22. **DS-13** — Use `None` as no-cap sentinel; fix zero-cap semantics
23. **DS-05** — Unified TUI undo via controller (dependency: DS-02 / TICKET-12)

### Backlog — Design decisions required

24. **SEC-05** — Cost side-channel: move `_cost_cents` out of adapter context dict
25. **SEC-NEW1** — Per-session Ed25519 agent identity
26. **SEC-NEW2** — Prompt injection detection layer
27. **SEC-NEW3** — Behavioral contract per deployment
28. **SEC-14** — Remove `preapproved_call_ids` in next major version
29. **DS-04** — Remove stale `audit_trail` field from suspension JSON

---

## Appendix A — Risk Score Methodology

**Likelihood:** H = certain or near-certain in normal use; M = requires specific conditions; L = rare/requires adversary  
**Impact:** H = data loss, security boundary violation, financial harm, or audit integrity loss; M = degraded functionality or misleading state; L = cosmetic or forensic only  
**Risk Score:** HH=9 (Critical), HM/MH=6 (High), MM/HL/LH=4 (Medium), ML/LM=2 (Low), LL=1 (Informational)

## Appendix B — Source Documents

| Document | Location |
|---|---|
| Security Risk Assessment | `docs/reviews/security-risk-assessment-2026-06-02.md` |
| Defeat Scenarios & Cascade Effects | `docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md` |
| Dependency Audit & Security | `docs/analysis/dependency-audit-and-security-2026-06-02.md` |
| Enterprise Security Risks | `docs/analysis/agent-enterprise-security-risks-2026-05-31.md` |
| Prior Threat Model | `docs/threat-model.md` |
| Architecture | `docs/architecture.md` |
| Code Quality Roadmap | `docs/analysis/code-quality-and-refactoring-roadmap-2026-06-02.md` |
| Daily-Driver Findings Ledger | `docs/analysis/daily-driver-findings-status-ledger-2026-06-01.md` |

---

*Generated by Claude Code (claude-sonnet-4-6) on 2026-06-02.*  
*All file:line references anchored to branch `fix/task-dd2-001-initial-task-passthrough` at HEAD as of 2026-06-02.*
