# Risk Register & Threat Model — teaagent
**Date:** 2026-06-02  
**Last updated:** 2026-06-09 (SEC-01 verified/closed; SEC-05/09/13/14/15 mitigated — see Fix Status §9)
**Branch:** fix/task-dd2-001-initial-task-passthrough  
**Scope:** Full system — CLI, TUI, REPL, MCP, subagents, Docker, audit, OAuth, approval, budget  
**Sources:** security-risk-assessment-2026-06-02.md · defeat-scenarios-and-cascade-effects-2026-06-02.md · dependency-audit-and-security-2026-06-02.md · agent-enterprise-security-risks-2026-05-31.md · docs/threat-model.md · static source analysis

---

## Executive Summary

teaagent is a governance-first AI agent harness with strong policy enforcement, a 5-loop governance architecture, and a comprehensive approval system. The security posture is solid at the policy layer; most high-severity gaps have been closed. **No P0 findings remain open.** **Fixed 2026-06-04/05:** SEC-02 (MCP trust expiry), SEC-04 (budget default), SEC-06 (JIT isolation), SEC-07 (Docker hardening), SEC-10 (shell allowlist), DS-02 (TUI controller routing), DS-05 (TUI undo via journal), DS-09 (background UUID rejection), DS-12 (empty-path approval), DS-13 (budget semantics). **Verified 2026-06-09:** SEC-01 (HMAC key persist + verify), SEC-13 (non-mocked integration tests). See §9 Fix Status for test evidence on each.

| Severity | Count | Immediately Blocking |
|---|---|---|
| Critical | 0 | No (SEC-01 verified/closed) |
| High | 5 | Partial (SEC-02) |
| Medium | 10 | No |
| Low | 5 | No |
| **Total** | **20 open** | |

---

## Risk Register Schema

**Effective:** 2026-06-06  
**Governed by:** this schema (GOV-002) — any structural change to risk register rows must update this section.

This section defines the canonical column schema for every risk register row (SEC-\*, DS-\*, SC-\*) in Part 2. Non-conforming rows fail automated validation via `scripts/validate_docs_consistency.py` (`_parse_risk_register_rows`, `_RISK_ROW_ID`).

### Column Definitions

| Column | Field Name | Type | Constraints | Description |
|---|---|---|---|---|
| 1 | **ID** | `string` | Pattern `[A-Z]{2,4}-\d{2}` (e.g. `SEC-01`, `DS-12`, `SC-03`) | Unique risk identifier. Prefix indicates source: `SEC`=Security Finding, `DS`=Defeat Scenario, `SC`=Supply Chain. |
| 2 | **Category** | `string` | Free-text, 1–3 words | Risk taxonomy bucket (e.g. Audit Integrity, Access Control, Permission, Budget, Isolation, Dependencies). |
| 3 | **Description** | `string` | Free-text, actionable | One-sentence summary of the risk, the gap, and why it matters. |
| 4 | **Likelihood (L)** | `enum` | `H` (High/certain), `M` (Medium/conditional), `L` (Low/rare) | Probability of exploitation or occurrence in normal use. Defined in Appendix A. |
| 5 | **Impact (I)** | `enum` | `H` (High), `M` (Medium), `L` (Low) | Severity if exploited. Defined in Appendix A. |
| 6 | **Score** | `integer` | `1`–`9` (see mapping below) | Risk Score = Likelihood × Impact quantisation. Computed, not asserted. |
| 7 | **Status** | `enum` | Canonical state from `docs/governance/document-state-model.md`: `Proposed`, `Active` (`OPEN` maps to `Active`), `Partially fixed`, `Verify/close`, `Fixed`, `Superseded`, `Archived`. Legacy labels (`OPEN`, `FIXED`, `WATCH`) are accepted with canonical mapping in doc-state-model.md. | Current mitigation state with evidence or fix date where applicable. |
| 8 | **Priority** | `enum` | `P0` (no-go for production), `P1` (fix this sprint), `P2` (fix within cycle), `P3` (backlog), `QW` (quick win), `—` (already fixed) | Remediation urgency. Follows Part 5 §5.2 priority tiers. |

### Risk Score Calculation

Risk Score is the quantised product of Likelihood × Impact:

| Likelihood | Impact | Score | Severity Label |
|---|---|---|---|
| H | H | 9 | Critical |
| H | M | 6 | High |
| M | H | 6 | High |
| M | M | 4 | Medium |
| H | L | 4 | Medium |
| L | H | 3 | Medium |
| M | L | 2 | Low |
| L | M | 2 | Low |
| L | L | 1 | Informational |

Scores are used for the heat matrix (Part 1) and for priority triage.

### Status Value Reference

All Status cells must use a canonical state defined in `docs/governance/document-state-model.md`. Common values:

| Status | Meaning | Example Row |
|---|---|---|
| `Active` / `OPEN` | Verified defect or gap affecting current product. | SEC-05, SEC-14 |
| `Verify/close` | Implementation exists; closure evidence pending. | SEC-01 |
| `Fixed` | Active-path verification and docs agree issue is resolved. Must include fix date and test evidence. | SEC-02 (Fixed 2026-06-05) |
| `**FIXED** YYYY-MM-DD — …` | Same as Fixed; bolded to surface recent mitigation. Evidence inline. | SEC-04, SEC-07, SEC-10 |
| `**DOCUMENTED** YYYY-MM-DD — …` | Risk accepted but documented with warnings. | SEC-08 |
| `Superseded` | Replaced by a newer finding or decision. | — |

### Validation Rules

1. **ID uniqueness**: Each `SEC-\*`, `DS-\*`, `SC-\*` ID must appear exactly once across all register tables.
2. **ID pattern**: Must match `^[A-Z]{2,4}-\d{2,}$` (two-to-four uppercase letters, hyphen, two or more digits).
3. **Score consistency**: The Score column must match the quantised product of the Likelihood and Impact columns per the table above.
4. **Status vocabulary**: Status text must map to a canonical state in `document-state-model.md`. Legacy labels (`OPEN`, `FIXED`, `WATCH`) are acceptable if the canonical mapping is supplied.
5. **Fixed rows require evidence**: Any row marked `Fixed` / `FIXED` must include either a test name (e.g. `test_*`) or a commit reference inline in the Status cell.
6. **Priority consistency**: Priority must match the tier defined in Part 5 §5.2 for open risks. Fixed risks use `—`.

### Schema Compliance in CI

The `_parse_risk_register_rows()` function in `scripts/validate_docs_consistency.py` parses every risk register row against this schema. CI runs `validate_docs_consistency.py --check-all` as part of the `use-case-matrix` job. Rows that fail ID pattern matching are silently skipped by the parser; missing or malformed rows should be caught by manual review during the risk register update process.

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

Each row: **ID · Category · Description · Likelihood (H/M/L) · Impact (H/M/L) · Risk Score (Likelihood×Impact: HH=9, HM=6, MM=4, etc.) · Owner · Due · Mitigation Status · Priority**

### 2.1 Security Findings (SEC-*)

| ID | Category | Description | L | I | Score | Owner | Due | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|
| SEC-01 | Audit Integrity | HMAC key is ephemeral — audit chain unverifiable across restarts; SHA-256 recomputable by attacker with write access | H | H | 9 | security | | **FIXED 2026-06-06** — key persisted to `~/.teaagent/run-keys/<run_id>.key` (chmod 600) since audit.py:165; **RISK-01 hardening 2026-06-06**: OSError on key save now emits `logger.warning` instead of silent pass — audit chain non-reproducibility is surfaced at runtime; tests: `test_audit_hmac_persisted_across_instances`, `test_audit_hmac_fails_with_wrong_key`, `test_audit_key_file_permissions_readable`, `HMACKeySaveTests::test_chain_key_save_failure_logs_warning` | — |
| SEC-02 | Access Control | MCP server trust `expires_at` never checked at call time; `is_server_trust_expired()` is dead call — expired servers remain trusted indefinitely | H | H | 9 | security | | **Fixed** (2026-06-05) — `is_server_trust_expired()` enforced in hot path at `mcp_trust.py:148,168`; `test_server_trust_expiry()` in `tests/test_mcp_trust.py` | — |
| SEC-03 | Permission | Historical: `allow_all_destructive=True` short-circuited the approval gate outside explicit full-access mode. Current branch blocks it in `prompt` mode and requires explicit broad-mode promotion for bypass callers. | L | H | 3 | security | | **FIXED / WATCH** | P1 |
| SEC-04 | Budget | ~~`ChatAgentConfig.max_estimated_cost_cents` defaults to `0`, interpreted as "no cap"~~ Default changed to `500`; `0`=no-spend, `None`=unlimited. Tests: `test_budget_zero_cents_rejects_any_spend`, `test_budget_none_allows_unlimited`, `test_budget_default_500_cents` | H | H | 9 | security | | **FIXED 2026-06-05** | — |
| SEC-05 | Budget | Cost accounting reads `context['_cost_cents']` written by the LLM adapter — injectable by malicious adapter or prompt-injected response | L | H | 3 | security | 2026-07-15 | **Mitigated 2026-06-09** — runner uses authoritative `usage_reader` from `ModelDecisionEngine`; residual: malicious adapter can still report `estimated_cost_cents=0`; tests: `test_sec_tier1_hardening.py`, `test_sec13_security_paths.py` | P2 |
| SEC-06 | Permission | Bidirectional JIT session approval sync leaks parent-approved tools to subagents via shared `jit_state`; subagent inherits `workspace_run_shell_mutate` without fresh approval | M | H | 6 | security | | **FIXED 2026-06-05** | — |
| SEC-07 | Isolation | Docker subagent runs as root, no `--network none`, no `--cap-drop ALL`, no seccomp — allows exfiltration and container escape | H | H | 9 | security | | **FIXED 2026-06-05** — all flags present in `_isolation.py:223-242`: `--user 65534:65534 --network none --cap-drop ALL --read-only --security-opt no-new-privileges`; test: `test_subagent_docker_container_hardened`; documented in `docs/ops/security-hardening.md` | — |
| SEC-08 | Isolation | `directory-snapshot` mode provides only filesystem isolation, not process isolation — agent reads `/etc/`, `/proc/`, `~/.ssh/`, spawns host processes | H | M | 6 | security | | **DOCUMENTED 2026-06-05** — `logger.warning()` emitted at every `directory-snapshot` selection (`_isolation.py:181`); isolation modes table and dev-vs-production guidance added to `docs/ops/security-hardening.md` | P1 |
| SEC-09 | Multi-sig | Multi-sig approval hash uses 1-hour time bucket (`int(time.time()/3600)`); captured signature replayable for up to 59:59 within same window; hash logic duplicated in two files | M | M | 4 | security | 2026-07-15 | **Mitigated 2026-06-09** — hash binds `request_id`; stale peer signatures rejected by timeout; test: `test_sec_tier1_hardening.py` | P2 |
| SEC-10 | Shell | `cat`, `head`, `tail` in `_INSPECT_EXECUTABLES` — classified as read-only inspect but can read `~/.ssh/id_rsa`, `.env`, `/etc/shadow` | H | H | 9 | security | | **FIXED 2026-06-05** — `_INSPECT_EXECUTABLES` contains only `{pwd, ls, rg, grep, wc}`; `cat/head/tail` absent; tests: `test_cat_not_in_inspect_allowlist`, `test_head_not_in_inspect_allowlist`, `test_tail_not_in_inspect_allowlist`, `test_inspect_shell_cannot_read_ssh_keys` | — |
| SEC-11 | Undo | `UndoJournal._PATH_WRITE_TOOLS` covers file tools only; `workspace_run_shell_mutate` not tracked — UI shows "undo available" but shell side-effects are unrecoverable | H | M | 6 | security | 2026-07-15 | **OPEN** | P2 |
| SEC-12 | Audit | `os.fsync()` failure caught and silenced; audit degrades to in-memory only with no operator notification; disk-full attack eliminates all log persistence | L | M | 2 | security | 2026-07-15 | **OPEN** | P2 |
| SEC-13 | Testing | Critical security paths (cost tracking, audit HMAC, approval denial) mocked out in tests — bugs live undetected (confirmed: CG-03 lived months this way) | H | M | 6 | security | 2026-06-20 | **Fixed 2026-06-09** — integration suite: `tests/integration/test_sec13_security_paths.py`, `test_audit_chain.py` (SEC-01), `test_runner_cost_tracking.py`, `test_task005_trust_expiry_enforcement.py`, `test_sec_tier1_hardening.py` | — |
| SEC-14 | Permission | `preapproved_call_ids` deprecated but still functional — old integrations or adversarial callers can pre-approve arbitrary call IDs without HMAC digest verification | L | L | 1 | security | | **Mitigated 2026-06-09** — opt-in hard-disable via `TEAAGENT_DISABLE_PREAPPROVED_CALL_IDS=1`; test: `test_sec_tier1_hardening.py` | P3 |
| SEC-15 | Multi-sig | `TEAAGENT_ALLOW_DEV_SIGNATURES=1` accepts SHA-256 of `(message+pubkey)` as valid signature; no runtime guard prevents this in production WAN deployment | L | M | 2 | security | 2026-07-15 | **Mitigated 2026-06-09** — `config_lint` errors when set; `selftest` fails; test: `test_config_lint_flags_dev_signatures_enabled` | P2 |
| SEC-16 | Code Quality | Dead code at `budget_monitor.py:104-119` after early return — maintenance hazard that could accidentally activate on refactor | H | L | 3 | security | | **Fixed** — dead loop removed in prior refactor | QW |
| SEC-17 | Engineering | `ApprovalPolicy` creates a `ThreadPoolExecutor` in `__post_init__` with no shutdown — every policy instance leaks threads (`policy.py:70`) | M | M | 4 | engineering | | **FIXED 2026-06-06 (ENG-01)** — `__del__` added to call `shutdown(wait=False, cancel_futures=True)`; tests: `ApprovalPolicyThreadLeakTests::test_del_shuts_down_signature_executor`, `test_del_is_safe_to_call_twice` | — |
| SEC-18 | Budget | `fake`, `ollama`, and `vllm` providers had `0.0` cost rates — budget guard never triggered for local/test providers, masking runaway inference | M | M | 4 | budget | | **FIXED 2026-06-06 (RISK-02)** — `fake=0.001`, `ollama=0.0001`, `vllm=0.0001` (nominal compute-cost sentinels); budget guard now exercisable with all providers; tests: `ProviderCostRateTests::test_fake_cost_rates_nonzero`, `test_ollama_cost_rates_nonzero`, `test_vllm_cost_rates_nonzero` | — |
| SEC-19 | Permission | JIT approval `input()` prompt has no timeout — agent blocks indefinitely waiting for human response on unattended TTY | M | M | 4 | permission | | **FIXED 2026-06-06 (OPS-01)** — 60-second default timeout via daemon thread; auto-denies with log message; configurable via `approval_timeout_seconds`; tests: `JITApprovalTimeoutTests::test_prompt_auto_denies_on_timeout`, `test_prompt_respects_valid_choice_before_timeout` | — |

### 2.2 Defeat Scenario Findings (DS-*)

| ID | Category | Description | L | I | Score | Owner | Due | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|
| DS-12 | Permission | Empty-path approval creates implicit global workspace grant; user believes they granted path-scoped access; audit log records it as "path-scoped" masking the expansion | M | H | 6 | infrastructure | | **FIXED 2026-06-05** | — |
| DS-13 | Budget | ~~`0` cost cap had three incompatible semantics~~ `None`=unlimited, `0`=zero-spend, positive=cap. Default 500 cents. Tests: `test_budget_zero_cents_rejects_any_spend`, `test_budget_default_500_cents` | M | M | 4 | infrastructure | | **FIXED 2026-06-05** | — |
| DS-01 | Budget | Historical: TUI `_session_cost_cents` never incremented — `/cost` and budget bar always showed `$0.00`; per-run cap still fired but cumulative cap never triggered | H | M | 6 | infrastructure | | **FIXED 2026-06-05** — runtime-path TUI tests in `tests/test_tui.py`; see TICKET-12 | — |
| DS-05 | Undo | TUI `/undo` calls `git stash pop` (broadcast restore); REPL `/undo` calls `UndoJournal.restore()` (surgical) — same command word, different blast radius; TUI can destroy manual edits irreversibly | M | H | 6 | infrastructure | | **Fixed** (2026-06-05) — TUI undo routes journal-first via `ChatSessionController.undo_last_run()` at `tui/__init__.py:860`; checkpoint fallback retained; `test_tui_undo_uses_journal()`, `test_tui_handle_undo_calls_controller_first()` in `tests/test_tui.py` | — |
| DS-09 | UX/Security | `agent run --background <uuid>` silently runs the UUID as a literal task string, spawning a real LLM call that spends money on nonsense | H | M | 6 | infrastructure | | **Fixed** (2026-06-05) — known run/suspension IDs rejected before dispatch; `test_agent_run_background_rejects_known_run_or_suspension_id()` in `tests/test_cli_chat.py:167` | — |
| DS-04 | Audit | Stale `audit_trail` dict in suspension JSON predates CG-10 fix; forensic tooling may prefer the stale copy over the real RunStore events | M | L | 2 | infrastructure | | **OPEN** | P3 |
| DS-06 | Testing | Historical: TUI cost test injected `_session_cost_cents` directly and tested formatter only, masking CG-11 from CI | H | M | 6 | infrastructure | | **FIXED 2026-06-05** — active-path TUI cost/session tests in `tests/test_tui.py`; see TICKET-14 | — |

### 2.3 Supply Chain Findings (SC-*)

| ID | Category | Description | L | I | Score | Owner | Due | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|
| SC-01 | Dependencies | Two alpha packages in production lock (`opentelemetry-exporter-gcp-logging==1.12.0a0`, `opentelemetry-resourcedetector-gcp==1.12.0a0`) can break between lock refreshes | M | L | 2 | architecture | 2026-07-15 | **OPEN** | P2 |
| SC-02 | Dependencies | `anthropic` SDK and `pyyaml` imported at runtime but undeclared in `pyproject.toml` — silent `ImportError` on installs without `google-cloud-aiplatform` or `pre-commit` | H | M | 6 | architecture | 2026-06-20 | **OPEN** — TASK-DD2-015 dependency declaration/import-check follow-up; fix target: `pyproject.toml` | P1 |
| SC-03 | Dependencies | `aiohttp` and `mcp` SDK in lock as orphans — not declared, not imported in core; add 22 transitive packages to attack surface unnecessarily | H | L | 3 | architecture | 2026-07-15 | **OPEN** | P2 |

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
| D-1: Runaway LLM loop exhausts API budget | `runner/_core.py:142` | `RunBudget` caps per-run; default 500 cents | ~~Default `max_estimated_cost_cents=0` = unlimited~~ — SEC-04 fixed | MEDIUM |
| D-2: Disk-full attack silences audit writes | `audit.py:298-307` | In-memory fallback | No operator notification; all events lost at process exit (SEC-12) | MEDIUM |
| D-3: UUID-as-task bogus run spends real API budget | `_agent.py:145-146` | None | `agent run --background <uuid>` runs UUID as literal task (DS-09) | MEDIUM |
| D-4: Zero budget cap interpreted as unlimited | `runner/_core.py:142` | `0`=no-spend, `None`=unlimited (DS-13 fixed) | Resolved — any positive cost raises `BudgetExceededError` when cap=0 | LOW |
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
| **SEC-04** | ~~Change default from `0` to `500`~~ **Done 2026-06-05**: `0`=no-spend, `None`=unlimited, default=500 cents. Tests added. | `teaagent/chat_agent.py:70`, `teaagent/budget.py`, `runner/_core.py:142` | Done |
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
| **DS-13** | ~~Use `None` as no-cap sentinel~~ **Done 2026-06-05**: `None`=unlimited, `0`=no-spend. Tests: `test_budget_zero_cents_rejects_any_spend`, `test_budget_none_allows_unlimited` | `teaagent/runner/_core.py:142` | Done |
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

1. **SEC-01** — ~~Persist HMAC key~~ **FIXED 2026-06-09**: key persisted at `audit.py:209-244`; verify autoload at `audit_chain.py:422`; tests: `test_audit_hmac_persisted_across_instances`, `test_audit_key_file_permissions_readable`, `test_verify_audit_chain_autoloads_persisted_hmac_key`.
2. **SEC-02** — ~~Call `is_server_trust_expired()`~~ **FIXED 2026-06-05**: enforced at `mcp_trust.py:148,168`; `test_server_trust_expiry()` passes.
3. **SEC-04** — ~~Change default~~ **FIXED 2026-06-05**: default 500 cents, `0`=no-spend, `None`=unlimited.
4. **SEC-07** — ~~Add Docker flags~~ **FIXED 2026-06-05**: `--user 65534:65534 --network none --cap-drop ALL --read-only --security-opt no-new-privileges` at `_isolation.py:234-241`.
5. **SEC-10** — ~~Remove `cat/head/tail`~~ **FIXED 2026-06-05**: `_INSPECT_EXECUTABLES` = `{pwd, ls, rg, grep, wc}` at `_shell.py:175`.
6. **SEC-16** — Delete dead loop at `budget_monitor.py:104-119` (QW — 10 min)
7. **DS-09** — ~~Stale hint removed~~ **FIXED 2026-06-05 (full fix)**: UUID-shaped task args rejected before LLM dispatch; `test_agent_run_background_rejects_known_run_or_suspension_id()` passes.
8. **SC-02** — Declare `anthropic` and `pyyaml` in `pyproject.toml` (XS — 30 min)

### Sprint 2 — High priority

9. **DS-12** — Validate non-empty path on path-scoped approval; reject empty or confirm-expand
10. **SEC-06** — `clone_for_subagent()` one-way JIT state sync
11. **SEC-13** — ~~Integration tests~~ **FIXED 2026-06-09**: `tests/integration/test_sec13_security_paths.py` + existing `test_runner_cost_tracking.py`, `test_audit_chain.py`, `test_task005_trust_expiry_enforcement.py`.
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
22. **DS-13** — ~~Use `None` as no-cap sentinel; fix zero-cap semantics~~ **FIXED 2026-06-04**: `None` is now the only unlimited sentinel; `0` means zero spend allowed. Test: `test_zero_cost_cap_blocks_positive_cost_run`
23. **DS-05** — ~~Unified TUI undo via controller~~ **FIXED 2026-06-05**: `_handle_undo()` routes journal-first via `controller.undo_last_run()` at `tui/__init__.py:860`; `test_tui_undo_uses_journal()` passes.

### Fix Status (2026-06-04)

**Fixed:**
- **DS-13**: Budget semantics fixed. `None` is now the only unlimited sentinel; `0` means zero spend allowed. Default budget changed from 100 to 500 cents. Test: `test_zero_cost_cap_blocks_positive_cost_run`.

**Fixed (2026-06-05):**
- **DS-12**: Empty-path approval rejection implemented. Empty path globs now raise `ValueError` to prevent implicit global grants. Session-scope allows `None` (no restriction); other scopes require explicit non-empty patterns. Relative paths in tool arguments are normalized via `_normalize_and_validate_path` before matching. Parent-traversal (`../`) and paths outside workspace are rejected. Tests: `test_empty_path_globs_rejected_ds12`, `test_approval_policy_rejects_empty_path`, `test_approval_policy_normalizes_relative_paths`.
- **SEC-06**: Subagent JIT approval isolation enforced. `SubagentManager.run_subagent` omits `jit_state` when building `sub_config`, so subagents always start with a fresh empty `JITApprovalState`. Approval lineage is one-way read-only: parent grants are never copied to child; child grants never propagate back to parent. Tests: `test_subagent_jit_approval_isolation_sec06`, `test_subagent_jit_approval_isolation_sec06_adversarial`, `test_subagent_does_not_inherit_parent_approvals`, `test_subagent_approval_doesnt_elevate_parent`.
- **SEC-04**: Default changed to 500 cents; `0`=no-spend, `None`=unlimited. Tests: `test_budget_zero_cents_rejects_any_spend`, `test_budget_none_allows_unlimited`, `test_budget_default_500_cents`.
- **SEC-02**: `is_server_trust_expired()` is now called in the hot path at `mcp_trust.py:148` (inside `merged_tool_filters`) and at `mcp_trust.py:168` (in the hook check). Expired servers now raise `HookError` and are excluded from allowed tools. Test: `test_server_trust_expiry()` in `tests/test_mcp_trust.py`. All 20 MCP trust tests pass.
- **SEC-07**: Docker hardening flags added to `subagents/_isolation.py:234-241`: `--user 65534:65534`, `--network none`, `--cap-drop ALL`, `--read-only`, `--security-opt no-new-privileges`. Tests: `test_docker_isolation_with_resource_limits()`, `test_docker_isolation_without_resource_limits()` in `tests/test_subagent_isolation.py`.
- **SEC-10**: `cat`, `head`, `tail` removed from `_INSPECT_EXECUTABLES`. Allowlist is now `{'pwd', 'ls', 'rg', 'grep', 'wc'}` at `workspace_tools/_shell.py:175`. Tests: `test_all_inspect_commands_classified_as_inspect()`, `test_safe_inspect_commands_still_allowed()`, `test_shell_inspect_rejects_mutating_command()` in `tests/test_workspace_tools.py`.
- **DS-02**: TUI now routes all task execution through `ChatSessionController.execute_task()` at `tui/__init__.py:996`. The controller is lazily initialized via `_get_chat_controller()` (:889) and shared across cost, undo, and task calls. Tests: `test_tui_uses_chat_session_controller_for_cost_tracking()`, `test_tui_handle_undo_calls_controller_first()` in `tests/test_tui.py`.
- **DS-05**: TUI undo now routes journal-first: `_handle_undo()` at `tui/__init__.py:860` calls `controller.undo_last_run()` first; falls back to `_restore_checkpoint()` only if journal is empty. Tests: `test_tui_undo_uses_journal()`, `test_tui_handle_undo_calls_controller_first()` in `tests/test_tui.py::TUITests`.
- **DS-09**: `agent run --background <id>` now rejects task args that match known run IDs or suspension IDs, preventing silent launch of a bogus LLM task. Test: `test_agent_run_background_rejects_known_run_or_suspension_id()` in `tests/test_cli_chat.py:167`.

**Still Open — Active (2026-06-09 review):**

Daily-driver items DS-01..DS-11 and TICKET-12..16 were **closed** in the June 4–9 ticket pass.
See [`active-findings-status-ledger-2026-06-06.md`](../analysis/active-findings-status-ledger-2026-06-06.md).

| ID | Status | Notes |
|---|---|---|
| SEC-01 | Fixed (2026-06-09) | HMAC key persisted + verify autoload; 4 tests pass including permissions |
| SEC-05 | Mitigated (2026-06-09) | Runner reads authoritative usage via `usage_reader`; engine tracks `DecisionUsage` |
| SEC-09 | Mitigated (2026-06-09) | Multisig hash binds `request_id`; stale signatures rejected by timeout |
| SEC-13 | Fixed (2026-06-09) | Non-mocked integration suite — `test_sec13_security_paths.py` |
| SEC-14 | Mitigated (2026-06-09) | Set `TEAAGENT_DISABLE_PREAPPROVED_CALL_IDS=1` in production; deprecation warning retained |
| SEC-15 | Mitigated (2026-06-09) | `config_lint` + `selftest` reject dev signatures |
| SEC-16 | Fixed | Dead code removed from `budget_monitor.py` (prior refactor) |
| WS3-001 | Implemented | Compliance mode fatal audit — `test_ws3_compliance_audit.py` |
| WS3-006 | Implemented | Approval-token exactness — `tests/test_approval_token_exactness.py` |
| MA-01..04 | Implemented | Isolation default, batch timeout, budget/depth caps — `test_subagent_isolation_policy.py`, `test_subagent_batch.py` |

### Backlog — Design decisions required

24. **SEC-05** — Cost side-channel: move `_cost_cents` out of adapter context dict
25. **SEC-NEW1** — Per-session Ed25519 agent identity
26. **SEC-NEW2** — Prompt injection detection layer
27. **SEC-NEW3** — Behavioral contract per deployment
28. **SEC-14** — Remove `preapproved_call_ids` in next major version
29. **DS-04** — Remove stale `audit_trail` field from suspension JSON

---

## Appendix C — Unverified Ecosystem Claims (Do Not Mark Complete)

The following capabilities are described in teaagent documentation or roadmap materials but have **no passing test evidence** and should not be claimed as shipped. Each item is aspirational and must be verified before any release claim.

| Claim | Location | Why Not Complete | What Would Prove It |
|---|---|---|---|
| Cloud/background command parity | `docs/cloud-deployment.md`, `docs/roadmap-status.md` H2 | No acceptance test proves CLI/cloud run state contract is identical across surfaces | Passing acceptance test comparing run-state, permissions, audit, cost, and recovery parity between CLI and background/cloud |
| IDE command parity | `docs/analysis/agent-ecosystem-daily-use-gap-review-2026-05-31.md` | No IDE integration code exists; parity gap not measured | Acceptance test proving equivalent task, approve, undo, and cost flows inside VS Code/JetBrains extension |
| Extension activation explanation | `docs/roadmap-status.md` H3 / TICKET-M3 | No "explain activation" UX code path; EXT-001 still Pending | `test_extension_activation_explain_acceptance` passes for MCP, plugin, and skill onboarding flows |
| Provider fallback day-two flow | `docs/provider-authoring.md`, model capability matrix | No test covers provider downgrade or fallback routing during a live session | Integration test: primary provider returns 5xx → fallback provider used → run completes with audit annotation |
| Risk-mode decision table | `docs/analysis/permission-mode-risk-decision-table-2026-06-01.md` | Document exists but no acceptance test enforces the table's correctness | Mode matrix acceptance test: each mode × each tool class × each user scenario asserts expected approval behavior |
| Workflow framework boundary | `docs/specs/` | "Workflow self-healing" described but boundary between workflow and agent loop is undocumented | Architectural decision record + acceptance test: workflow re-entry does not re-enter runner loop; bounded attempt count enforced |
| Release evidence acceptance | `docs/release-evidence.json`, `docs/release-checklist.md` | JSON has no machine-readable schema; checklist is not CI-gated | `validate_docs_consistency.py --check-release-evidence` passes in CI; evidence bundle export passes automated format validation |

**Policy:** Any PR that claims one of the above is "complete" must include the evidence column above and CI proof. Absence of test evidence = aspirational, not shipped.

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
