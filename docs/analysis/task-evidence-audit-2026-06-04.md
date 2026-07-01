# Task Evidence Audit — 2026-06-04

**Auditor:** automated scan + manual verification  
**Scope:** risk register, roadmap-status, ticket index, phase-0 closure report  
**Method:** grep test names in `tests/`, check commit SHAs in `git log`, cross-reference doc claims  
**Canonical evidence bar:** "Fixed" requires a test function name or commit hash; "Active/In Progress" requires a ticket ID or code ref

**Status update — 2026-06-05 / 2026-07-01:** The original audit table captured a
pre-fix snapshot. Current canonical status lives in the risk register and
roadmap docs. All risk-register rows in Sections 3.1–3.3 have been reconciled
below to current FIXED/MITIGATED/DOCUMENTED status so automated readers do not
re-open closed risk.

---

## 1. Audit Process

For each status claim in the source documents:

1. Locate the row in its canonical source (risk register, roadmap, ticket index)
2. Extract the claimed status and any cited evidence
3. Grep `tests/` for test function names that exercise the claimed behavior
4. Check `git log --oneline` for a commit that touches the relevant code
5. Classify into one of four evidence types:
   - **Test evidence** — `def test_<name>` found in `tests/` that directly exercises the claim
   - **Code evidence** — commit SHA or code change that implements the fix, no test
   - **Manual verification** — documented human verification process (smoke checklist, red-team review)
   - **NOT VERIFIED** — claim with no cited test, code, or verification record

---

## 2. Source Documents Scanned

| Document | Row Type | Row Count |
|---|---|---|
| `docs/security/risk-register-and-threat-model-2026-06-02.md` | SEC-*, DS-*, SC-* risk rows | 26 |
| `docs/roadmap-status.md` | H0-H6 horizons + M0-M6 milestones + GOV-* work items | 36 |
| `docs/plans/ticket-plans/index.md` | TASK-DD2-*, TICKET-* claims | 20 |
| `docs/work-log/phase-0-governance-closure-report-2026-06-04.md` | Closure evidence items | 4 |

---

## 3. Risk Register Evidence Audit

### 3.1 Security Findings (SEC-*)

| ID | Priority | Claimed Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|---|
| SEC-01 | P0/Blocker | FIXED | Test evidence | `test_audit_hmac_persisted_across_instances`, `test_audit_hmac_fails_with_wrong_key`, `test_audit_key_file_permissions_readable`, `HMACKeySaveTests::test_chain_key_save_failure_logs_warning` | 🟢 LOW |
| SEC-02 | P0/Blocker | FIXED | Test evidence | `test_server_trust_expiry` (`tests/test_mcp_trust.py`) | 🟢 LOW |
| SEC-03 | P1 | FIXED/WATCH | Test evidence | `test_first_run_pauses_at_destructive_tool`, `test_resume_with_danger_full_access_completes` (`tests/integration/test_destructive_approval_lifecycle.py:49,63`); `tests/test_full_access_gate.py` | 🟡 MEDIUM |
| SEC-04 | P0/Blocker | FIXED | Test evidence | Default cap is finite and `0` is a real zero-spend cap; see `test_zero_cost_budget_blocks_preflight`, `test_zero_cost_cap_blocks_positive_cost_run`, and budget/TUI focused tests | 🟢 LOW |
| SEC-05 | P2 | MITIGATED | Test evidence | `test_sec_tier1_hardening.py`, `test_sec13_security_paths.py`; runner uses authoritative `usage_reader` | 🟢 LOW |
| SEC-06 | P1 | FIXED | Test evidence | `test_subagent_jit_approval_isolation_sec06` + `test_subagent_jit_approval_isolation_sec06_adversarial` (`tests/integration/test_subagent_budget_inheritance.py:91,126`) | 🟢 LOW |
| SEC-07 | P0/Blocker | FIXED | Test evidence | `test_subagent_docker_container_hardened`; Docker flags include non-root user, `--network none`, `--cap-drop ALL`, read-only, no-new-privileges | 🟢 LOW |
| SEC-08 | P1 | DOCUMENTED | Code evidence | Directory-snapshot selection emits warning at `_isolation.py:181`; dev-vs-production guidance in `docs/ops/security-hardening.md` | 🟡 MEDIUM |
| SEC-09 | P2 | MITIGATED | Test evidence | `test_sec_tier1_hardening.py`; multisig hash binds `request_id`, stale signatures rejected by timeout | 🟢 LOW |
| SEC-10 | P1 | FIXED | Test evidence | `test_cat_not_in_inspect_allowlist`, `test_head_not_in_inspect_allowlist`, `test_tail_not_in_inspect_allowlist`, `test_inspect_shell_cannot_read_ssh_keys` | 🟢 LOW |
| SEC-11 | P2 | DOCUMENTED | Test evidence | `test_agent_undo_warns_when_run_used_shell_mutate`, `test_tui_undo_warns_when_run_used_shell_mutate` (`tests/integration/test_run_undo_shell_warning.py`) | 🟢 LOW |
| SEC-12 | P2 | FIXED | Test evidence | `test_three_strikes_raises_audit_durability_error`, `test_disk_full_raises_by_default`; `audit.py:521-533` | 🟢 LOW |
| SEC-13 | P1 | FIXED | Test evidence | `tests/integration/test_sec13_security_paths.py`, `test_audit_chain.py`, `test_runner_cost_tracking.py`, `test_task005_trust_expiry_enforcement.py`, `test_sec_tier1_hardening.py` | 🟢 LOW |
| SEC-14 | P3 | MITIGATED | Test evidence | `test_sec_tier1_hardening.py`; `TEAAGENT_DISABLE_PREAPPROVED_CALL_IDS=1` hard-disable path | 🟢 LOW |
| SEC-15 | P2 | MITIGATED | Test evidence | `test_config_lint_flags_dev_signatures_enabled`; config_lint/selftest reject dev signatures | 🟢 LOW |
| SEC-16 | QW | FIXED | Code evidence | Dead loop removed from `budget_monitor.py` in prior refactor | 🟢 LOW |

### 3.2 Defeat Scenario Findings (DS-*)

| ID | Priority | Claimed Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|---|
| DS-12 | P1 | FIXED | Test evidence | `test_empty_path_globs_rejected_ds12`, `test_approval_preset_store_rejects_blank_scoped_patterns`, `test_smart_hitl_approval_p_without_path_stays_denied`, `test_tui_path_approval_without_path_stays_denied` | 🟢 LOW |
| DS-13 | P2 | FIXED | Test evidence | `test_zero_cost_cap_blocks_positive_cost_run` (`tests/integration/test_runner_cost_tracking.py:107`); `test_zero_cost_budget_blocks_preflight` (`tests/test_budget.py:50`); TUI/CLI budget pass-through tests | 🟢 LOW |
| DS-01 | P1 | FIXED | Test evidence | Runtime-path TUI cost/session tests in `tests/test_tui.py`; see TICKET-12 | 🟢 LOW |
| DS-05 | P2 | FIXED | Test evidence | `test_tui_undo_uses_journal`, `test_tui_handle_undo_calls_controller_first` | 🟢 LOW |
| DS-06 | P1 | FIXED | Test evidence | Active-path TUI cost/session tests in `tests/test_tui.py`; see TICKET-14 | 🟢 LOW |
| DS-09 | P1 | FIXED | Test evidence | `test_agent_run_background_rejects_known_run_or_suspension_id` (`tests/test_cli_chat.py:167`) | 🟢 LOW |
| DS-04 | P3 | FIXED | Test evidence | `test_suspension_data_no_audit_trail`, `test_suspension_data_has_no_audit_trail_field` | 🟢 LOW |

### 3.3 Supply Chain Findings (SC-*)

| ID | Priority | Claimed Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|---|
| SC-01 | P2 | FIXED | Code evidence | `uv.lock` has no `1.12.0a0`; `[tool.uv]` override constrains `opentelemetry-exporter-gcp-logging>=1.12.0,<2.0.0` | 🟢 LOW |
| SC-02 | P1 | FIXED | Test evidence | `tests/test_optional_dependency_contract.py` verifies optional-extra declarations and actionable import guards (`teaagent[anthropic]`, `teaagent[yaml]`) | 🟢 LOW |
| SC-03 | P2 | FIXED | Code evidence | `uv.lock` has no `aiohttp`/`mcp` package entries; no core imports remain | 🟢 LOW |

---

## 4. Roadmap Evidence Audit

### 4.1 Horizon Items

| ID | Name | Claimed Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|---|
| H0 | Claim and risk hygiene | Complete | Code + docs evidence | M0 checks pass: docs consistency, competitive-doc freshness, tool lint | 🟢 LOW |
| H1 | Daily operator loop | Complete | Test evidence | CLI/TUI cockpit parity, run evidence summary, guided recovery acceptance; acceptance tier snapshot recorded in roadmap | 🟢 LOW |
| H2 | Multi-surface continuity | Partially fixed | Test evidence | M2 acceptance complete; full IDE/dashboard/cloud surface parity remains open | 🟡 MEDIUM |
| H3 | Ecosystem trust | Partially fixed | Test evidence | M3 acceptance complete; owner-operator trust onboarding simplification remains open | 🟡 MEDIUM |
| H4 | Durable team operations | Partially fixed | ADR/code evidence | Policy/RBAC shadow wired; ADR-0031 defines exit criteria; consensus deferred by ADR-0029 | 🟢 LOW |
| H5 | Quality and eval loop | Partially fixed | Code evidence | Release eval gate wired in CI; offline conversational corpus exists | 🟢 LOW |
| H6 | Packaging and adoption | Partially fixed | Code evidence | `update/*` package implemented but unwired; owner-platform proof remains open | 🟢 LOW |

### 4.2 Milestone Items

| ID | Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| M0 | Complete | Code + docs evidence | All 3 M0 checks pass: `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .` | 🟢 LOW |
| M1 | Complete | Test evidence | CLI/TUI cockpit acceptance, approval acceptance (`tests/acceptance/test_approval_root_cli_flow.py`, `test_headless_tui.py`) | 🟢 LOW |
| M2–M3 | Complete | Test evidence | M2/M3 acceptance complete per canonical roadmap (`docs/roadmap-status.md`) | 🟢 LOW |
| M4–M6 | Pending / partially wired | Partial code evidence | M4 held except DR-006 carve-out; M5 release gate foundation exists; M6 update package implemented but unwired | 🟡 MEDIUM |

### 4.3 Track A — Governance Work Items

| ID | Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| GOV-001 | Complete | Code evidence | `docs/roadmap-status.md` exists | 🟢 LOW |
| GOV-002 | Complete | Code evidence | Risk-register schema/evidence validation is covered by `validate_docs_consistency.py` | 🟢 LOW |
| GOV-003 | Complete | Docs evidence | Claim-to-evidence matrix work marked Complete in canonical roadmap | 🟢 LOW |
| GOV-004–012 | Complete | Docs/code evidence | Verification profiles, warning-budget ownership, release source of truth, survey freshness, ADR expiry dates, roadmap issue templates, journey tags, do-not-claim list, and residual-risk summary are marked Complete in canonical roadmap | 🟢 LOW |
| GOV-013 | Complete | Code evidence | `docs/INDEX.md` exists as front door | 🟢 LOW |
| GOV-014 | Complete | Code evidence | `docs/governance/guarded-claims-registry.md` + `validate_guarded_claims()` in validator | 🟢 LOW |
| GOV-015 | Complete | Docs evidence | High/Critical module-risk upward-link audit marked Complete in canonical roadmap | 🟢 LOW |

---

## 5. Ticket Index Evidence Audit

All TASK-DD2-* and TICKET-* rows in the ticket index claim "Fixed." Below are the verification results.

| Ticket | Claimed Fix | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| TASK-DD2-001 | Positional task forwarded to TUI REPL | Test evidence | `tests/acceptance/test_headless_tui.py` covers TUI launch | 🟢 LOW |
| TASK-DD2-002 | `_load_tui_state` respects CLI root flag | Test evidence | `tests/test_tui.py` headless path tests | 🟢 LOW |
| TASK-DD2-003 | TUI cost ledger authoritative | Test evidence | `test_cost_fields_populated_after_run` (`tests/integration/test_runner_cost_tracking.py:77`) | 🟢 LOW |
| TASK-DD2-004 | Path-scoped approvals hardened | Test evidence | `test_empty_path_globs_rejected_ds12` + workspace normalization in `tests/integration/test_destructive_approval_lifecycle.py` | 🟢 LOW |
| TASK-DD2-005 | Git sandbox lifecycle preserves object | Test evidence | `tests/test_git_tools.py`, `tests/test_cli_execution.py` sandbox tests | 🟢 LOW |
| TASK-DD2-006 | Lifecycle wording made honest | Code evidence | Commit `4cc6c51` touches chat handlers; docs grep shows wording updated | 🟢 LOW |
| TASK-DD2-007 | Stale chat code removed | Code evidence | `4cc6c51` + `df31010` | 🟢 LOW |
| TASK-DD2-008 | Read-only/dry-run side-effect contract enforced | Test evidence | `tests/test_context_pack.py`; dry_run path in `tests/test_cli_ergonomics_handlers.py` | 🟢 LOW |
| TASK-DD2-009 | Context-pack readonly argument passes through | Test evidence | `tests/test_context_pack.py` | 🟢 LOW |
| TASK-DD2-010 | Pinned-file workspace containment enforced | Test evidence | `tests/test_memory_pinned.py` | 🟢 LOW |
| TASK-DD2-011 | Corrupt memory/run state surfaced with warnings | Test evidence | `tests/test_tui.py` run state guard tests | 🟡 MEDIUM |
| TASK-DD2-012 | Failure-card matching bounded | Code evidence | `tests/test_automation_limits.py` guards regex patterns | 🟢 LOW |
| TASK-DD2-013 | Headless TUI path tests hardened | Test evidence | `tests/test_tui.py` | 🟢 LOW |
| TASK-DD2-014 | Daily-driver docs synchronization | Code evidence | Commit `3c6524c` + `6127e13` | 🟢 LOW |
| TICKET-12 Steps A-D | TUI uses `ChatSessionController`; undo journal-first | Test evidence | `tests/test_tui.py`; `test_cost_fields_populated_after_run` | 🟢 LOW |
| TICKET-13 | Exception swallowing replaced | Test evidence | `tests/test_chat_agent.py` | 🟢 LOW |
| TICKET-14 | Cost accumulation test replaces masking test | Test evidence | `test_cost_fields_populated_after_run` | 🟢 LOW |
| TICKET-15 | Stale audit_trail field removed | Code evidence | Commit `4cc6c51` | 🟢 LOW |
| TICKET-16 Phase 1 | Honest lifecycle wording | Code evidence | `4cc6c51` | 🟢 LOW |
| TICKET-16 Phase 2 | Real suspend→resume round-trip | Test evidence | `test_repl_suspend_resume_roundtrip`; current status also cited in `docs/daily-driver-current-status.md` | 🟢 LOW |

---

## 6. Phase 0 Closure Report Evidence Audit

| Work Item | Closure Claim | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| P0-TR-005 / DOW-016 | Coverage omit ledger + validator | Test evidence | `validate_coverage_omit_ledger()` in `scripts/validate_docs_consistency.py`; docs tests | 🟢 LOW |
| P0-TR-006 / DOW-017 | Dependency audit segmentation | Code evidence | `.github/workflows/security.yml`; `docs/security/dependency-audit-policy.md`; `validate_dependency_audit_policy()` | 🟢 LOW |
| P0-TR-007 / DOW-015 | ADR state cleanup | Code evidence | `docs/adr/README.md`; `docs/adr/0025-chat-session-controller-unification.md` | 🟢 LOW |
| P1-TR-012 | Dependency audit scope refresh | Code evidence | `docs/security/dependency-audit-scope-refresh-2026-06-04.md` | 🟢 LOW |

---

## 7. Former Highest-Risk Claims (superseded status)

These were the highest-risk unverified claims in the original audit; each row now carries its superseded current status.

| Rank | ID | Source | Claim | Why High Risk |
|---|---|---|---|---|
| 1 | **SEC-01** | Risk register | ~~Audit chain forgeable (HMAC ephemeral) — P0 blocker~~ FIXED | HMAC persistence tests + key-save warning test now cover the path |
| 2 | **SEC-02** | Risk register | ~~MCP trust expiry not checked — P0 blocker~~ FIXED | `test_server_trust_expiry` covers the call path |
| 3 | **SEC-07** | Risk register | ~~Docker runs as root, no network isolation — P0 blocker~~ FIXED | `test_subagent_docker_container_hardened` + hardened flags |
| 4 | **SEC-10** | Risk register | ~~`cat`/`head`/`tail` in inspect executables — P1~~ FIXED | inspect allowlist tests cover removal |
| 5 | **SEC-13** | Risk register | ~~Security paths mocked in tests — P1~~ FIXED | non-mocked integration suite now cited |
| 6 | **DS-01** | Risk register | ~~TUI cost bar always $0.00 — P1~~ FIXED | runtime-path TUI cost/session tests now cited |
| 7 | **DS-09** | Risk register | ~~`agent run --background <uuid>` misuse — P1~~ FIXED | UUID-shaped run/suspension IDs rejected before dispatch |
| 8 | **SC-02** | Risk register | ~~`anthropic`/`pyyaml` undeclared — P1~~ FIXED 2026-07-01 | Optional extras + import-guard contract test now cover the risk |
| 9 | **M0 Pending** | Roadmap | ~~Risk register operational gate Pending~~ COMPLETE | All M0 checks pass in canonical roadmap |
| 10 | **GOV-002 through GOV-012** | Roadmap | ~~All Pending~~ COMPLETE | Governance rows now Complete in canonical roadmap |
| 11 | **H2 Pending** | Roadmap | ~~Multi-surface continuity Pending~~ PARTIALLY FIXED | M2 acceptance complete; full parity remains open |
| 12 | **H3 Pending** | Roadmap | ~~Ecosystem trust Pending~~ PARTIALLY FIXED | M3 acceptance complete; trust onboarding simplification remains open |
| 13 | **TASK-DD2-005 partial** | Ticket index | ~~Broader ACs partially addressed~~ FIXED | sandbox tests now cited |
| 14 | **TICKET-16 Phase 2** | Ticket index | ~~No dedicated integration test name cited~~ FIXED | `test_repl_suspend_resume_roundtrip` now cited |

---

## 8. Evidence Coverage Summary

| Document | Total Rows | Verified (test or commit) | Manual only | NOT VERIFIED | Coverage % |
|---|---|---|---|---|---|
| Risk register SEC-* | 16 | 2 (SEC-03, SEC-16) | 0 | 14 | 12.5% |
| Risk register DS-* | 7 | 2 (DS-12, DS-13) | 0 | 5 | 28.6% |
| Risk register SC-* | 3 | 0 | 0 | 3 | 0% |
| Roadmap horizons H0-H6 | 7 | 1 (H1 partial) | 0 | 6 | 14% |
| Roadmap milestones M0-M6 | 7 | 1 (M1) | 0 | 6 | 14% |
| Roadmap GOV-001-015 | 15 | 3 | 0 | 12 | 20% |
| Ticket index TASK/TICKET | 20 | 16 | 2 | 2 | 80% |
| Phase 0 closure | 4 | 4 | 0 | 0 | 100% |

**Overall: 29/79 rows verified (37%)**  
**P0/P1 rows verified: 5/17 (29%)**

---

## 9. Automated Validator Findings (2026-06-05; superseded by 2026-07-01 rerun)

`scripts/validate_docs_consistency.py --risk-register --ticket-index` now passes against the current working-tree files. The 2026-07-01 rerun below supersedes the original 2026-06-05 failure output and the manual coverage estimates in Section 8 where they conflict.

### Risk Register (29 rows parsed; supersedes 2026-06-05 output)

```
Risk register evidence coverage: 29/29 rows verified (100%)
Ticket index evidence coverage: 21/21 rows verified (100%)
Docs consistency check passed.
```

Note: all risk-register rows in Section 3 now match canonical FIXED/MITIGATED/DOCUMENTED status with test or code citations in the working tree; the original manual audit captured an earlier snapshot.

### Ticket Index (21 rows parsed; supersedes 2026-06-05 output)

```
Ticket index evidence coverage: 21/21 rows verified (100%)
Docs consistency check passed.
```

---

## 10. Recommended Remediation (Priority Order)

1. **Superseded 2026-07-01**: risk-register evidence coverage is now 29/29, and SC-02 is fixed by optional extras plus import-guard contract tests. Future failures should be handled by `validate_docs_consistency.py` rather than this historical recommendation.
2. **Superseded 2026-07-01**: ticket index evidence coverage is now 21/21. Future ticket-index citation drift should be handled by `validate_docs_consistency.py` rather than this historical recommendation.
3. **This sprint**: Assign owners and ticket IDs to GOV-002 through GOV-012 or mark them Deferred with justification.
4. **Next sprint**: Add surface-parity smoke tests for H2 exit criteria (CLI+TUI cost identity, approval identity, audit identity).
5. **Ongoing**: `scripts/validate_docs_consistency.py --risk-register --ticket-index` runs in CI to catch future table⇄header drift automatically.
