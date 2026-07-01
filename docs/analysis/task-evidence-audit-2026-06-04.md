# Task Evidence Audit — 2026-06-04

**Auditor:** automated scan + manual verification  
**Scope:** risk register, roadmap-status, ticket index, phase-0 closure report  
**Method:** grep test names in `tests/`, check commit SHAs in `git log`, cross-reference doc claims  
**Canonical evidence bar:** "Fixed" requires a test function name or commit hash; "Active/In Progress" requires a ticket ID or code ref

**Status update — 2026-06-05 / 2026-07-01:** The original audit table captured a
pre-fix snapshot. Current canonical status lives in the risk register and
roadmap docs. Rows for SEC-04, SEC-06, DS-12, DS-13 (2026-06-05) and SEC-11,
DS-04, SC-01, SC-02, SC-03 (2026-07-01) have been reconciled below so
automated readers do not re-open closed risk.

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
| SEC-01 | P0/Blocker | OPEN | NOT VERIFIED | No test guards audit HMAC persistence across restarts | 🔴 HIGH |
| SEC-02 | P0/Blocker | OPEN | NOT VERIFIED | No test exercises `is_server_trust_expired()` at call time | 🔴 HIGH |
| SEC-03 | P1 | FIXED/WATCH | Test evidence | `test_first_run_pauses_at_destructive_tool`, `test_resume_with_danger_full_access_completes` (`tests/integration/test_destructive_approval_lifecycle.py:49,63`); `tests/test_full_access_gate.py` | 🟡 MEDIUM |
| SEC-04 | P0/Blocker | FIXED | Test evidence | Default cap is finite and `0` is a real zero-spend cap; see `test_zero_cost_budget_blocks_preflight`, `test_zero_cost_cap_blocks_positive_cost_run`, and budget/TUI focused tests | 🟢 LOW |
| SEC-05 | P2 | OPEN | NOT VERIFIED | No test guards cost side-channel via adapter context dict | 🟡 MEDIUM |
| SEC-06 | P1 | FIXED | Test evidence | `test_subagent_jit_approval_isolation_sec06` + `test_subagent_jit_approval_isolation_sec06_adversarial` (`tests/integration/test_subagent_budget_inheritance.py:91,126`) | 🟢 LOW |
| SEC-07 | P0/Blocker | OPEN | NOT VERIFIED | No test asserts Docker flags `--network none`, `--cap-drop ALL`, seccomp | 🔴 HIGH |
| SEC-08 | P1 | OPEN | NOT VERIFIED | No test verifies directory-snapshot isolation vs `/etc/`, `/proc/` access | 🟡 MEDIUM |
| SEC-09 | P2 | OPEN | NOT VERIFIED | Multi-sig 1-hour replay window; no test exercises replay attack | 🟢 LOW |
| SEC-10 | P1 | OPEN | NOT VERIFIED | `_INSPECT_EXECUTABLES` still includes `cat`, `head`, `tail`; no test enforces safe-reads-only list | 🔴 HIGH |
| SEC-11 | P2 | DOCUMENTED | Test evidence | `test_agent_undo_warns_when_run_used_shell_mutate`, `test_tui_undo_warns_when_run_used_shell_mutate` (`tests/integration/test_run_undo_shell_warning.py`) | 🟢 LOW |
| SEC-12 | P2 | OPEN | NOT VERIFIED | `os.fsync()` silence path not covered by test | 🟢 LOW |
| SEC-13 | P1 | OPEN | NOT VERIFIED | Critical paths still mock security internals; CG-03 class bug confirmed latent; no remediation timeline | 🔴 HIGH |
| SEC-14 | P3 | OPEN | NOT VERIFIED | `preapproved_call_ids` deprecated but still callable; no test asserts old integrations are blocked | 🟢 LOW |
| SEC-15 | P2 | OPEN | NOT VERIFIED | Dev-signature bypass has no production guard; no test asserts rejection on non-loopback | 🟡 MEDIUM |
| SEC-16 | QW | OPEN | Code evidence | Dead code at `budget_monitor.py:104-119` visible in static analysis; no test required | 🟢 LOW |

### 3.2 Defeat Scenario Findings (DS-*)

| ID | Priority | Claimed Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|---|
| DS-12 | P1 | FIXED | Test evidence | `test_empty_path_globs_rejected_ds12`, `test_approval_preset_store_rejects_blank_scoped_patterns`, `test_smart_hitl_approval_p_without_path_stays_denied`, `test_tui_path_approval_without_path_stays_denied` | 🟢 LOW |
| DS-13 | P2 | FIXED | Test evidence | `test_zero_cost_cap_blocks_positive_cost_run` (`tests/integration/test_runner_cost_tracking.py:107`); `test_zero_cost_budget_blocks_preflight` (`tests/test_budget.py:50`); TUI/CLI budget pass-through tests | 🟢 LOW |
| DS-01 | P1 | OPEN | NOT VERIFIED | TUI `_session_cost_cents` accumulation bug; DS-13 fixed budget semantics but DS-01 is a separate TUI accumulation path | 🔴 HIGH |
| DS-05 | P2 | OPEN | NOT VERIFIED | TUI/REPL undo divergence; no test shows same command has consistent blast radius | 🟡 MEDIUM |
| DS-06 | P1 | OPEN | NOT VERIFIED | TUI cost test still injects state directly; accumulation path not covered by CI | 🟡 MEDIUM |
| DS-09 | P1 | OPEN | NOT VERIFIED | `agent run --background <uuid>` misuse not blocked; no test guards literal-UUID task misparse | 🔴 HIGH |
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
| H0 | Claim and risk hygiene | In Progress | Partial code evidence | `validate_docs_consistency.py` exists; `docs/governance/guarded-claims-registry.md` exists; but DOCOPT-012 still open | 🟡 MEDIUM |
| H1 | Daily operator loop | In Progress | Manual verification | M1 marked Complete with High confidence; acceptance tests exist for approval/TUI flows | 🟡 MEDIUM |
| H2 | Multi-surface continuity | Pending | NOT VERIFIED | No surface-parity tests for identity/cost/recovery across CLI+TUI+IDE | 🔴 HIGH |
| H3 | Ecosystem trust | Pending | NOT VERIFIED | No activation-explain or MCP trust-onboarding acceptance tests | 🔴 HIGH |
| H4 | Durable team operations | Pending | NOT VERIFIED | Background/cloud/team lifecycle tests do not exist | 🟡 MEDIUM |
| H5 | Quality and eval loop | Pending | NOT VERIFIED | Eval-gate infrastructure not built | 🟡 MEDIUM |
| H6 | Packaging and adoption | Pending | NOT VERIFIED | SBOM/signing/update docs not started | 🟡 MEDIUM |

### 4.2 Milestone Items

| ID | Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| M0 | Pending | NOT VERIFIED | `validate_docs_consistency.py` exists (a gate) but M0 itself still Pending; GOV-002 through GOV-012 all Pending | 🔴 HIGH |
| M1 | Complete | Test evidence | CLI/TUI cockpit acceptance, approval acceptance (`tests/acceptance/test_approval_root_cli_flow.py`, `test_headless_tui.py`) | 🟡 MEDIUM |
| M2–M6 | Pending | NOT VERIFIED | No acceptance suites for long-session, federation, eval, or packaging | 🟡 MEDIUM |

### 4.3 Track A — Governance Work Items

| ID | Status | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| GOV-001 | Complete | Code evidence | `docs/roadmap-status.md` exists | 🟢 LOW |
| GOV-002 | Pending | NOT VERIFIED | No risk-register schema validator; row format is unstructured prose | 🔴 HIGH |
| GOV-003 | Pending | NOT VERIFIED | No claim-to-evidence matrix tool | 🔴 HIGH |
| GOV-004–012 | Pending | NOT VERIFIED | No owner, no ticket IDs, no exit criteria evidence | 🔴 HIGH |
| GOV-013 | Complete | Code evidence | `docs/INDEX.md` exists as front door | 🟢 LOW |
| GOV-014 | In Progress | Partial code evidence | `docs/governance/guarded-claims-registry.md` + `validate_guarded_claims()` in validator; DOCOPT-012 still open | 🟡 MEDIUM |
| GOV-015 | Pending | NOT VERIFIED | Module risk files lack central owner/ticket links for High/Critical rows | 🟡 MEDIUM |

---

## 5. Ticket Index Evidence Audit

All TASK-DD2-* and TICKET-* rows in the ticket index claim "Fixed." Below are the verification results.

| Ticket | Claimed Fix | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| TASK-DD2-001 | Positional task forwarded to TUI REPL | Test evidence | `tests/acceptance/test_headless_tui.py` covers TUI launch | 🟢 LOW |
| TASK-DD2-002 | `_load_tui_state` respects CLI root flag | Test evidence | `tests/test_tui.py` headless path tests | 🟢 LOW |
| TASK-DD2-003 | TUI cost ledger authoritative | Test evidence | `test_cost_fields_populated_after_run` (`tests/integration/test_runner_cost_tracking.py:77`) | 🟢 LOW |
| TASK-DD2-004 | Path-scoped approvals hardened | Test evidence | `test_empty_path_globs_rejected_ds12` + workspace normalization in `tests/integration/test_destructive_approval_lifecycle.py` | 🟢 LOW |
| TASK-DD2-005 | Git sandbox lifecycle preserves object — "core fix" only; broader ACs partially addressed | Manual verification | "Broader ACs partially addressed — see plan file" is the only note; no test names listed for the partial ACs | 🟡 MEDIUM |
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
| TICKET-16 Phase 2 | Real suspend→resume round-trip | Manual verification | Claimed Fixed but no dedicated test name cited for the suspend→resume round-trip path | 🟡 MEDIUM |

---

## 6. Phase 0 Closure Report Evidence Audit

| Work Item | Closure Claim | Evidence Type | Evidence Link | Risk Level |
|---|---|---|---|---|
| P0-TR-005 / DOW-016 | Coverage omit ledger + validator | Test evidence | `validate_coverage_omit_ledger()` in `scripts/validate_docs_consistency.py`; docs tests | 🟢 LOW |
| P0-TR-006 / DOW-017 | Dependency audit segmentation | Code evidence | `.github/workflows/security.yml`; `docs/security/dependency-audit-policy.md`; `validate_dependency_audit_policy()` | 🟢 LOW |
| P0-TR-007 / DOW-015 | ADR state cleanup | Code evidence | `docs/adr/README.md`; `docs/adr/0025-chat-session-controller-unification.md` | 🟢 LOW |
| P1-TR-012 | Dependency audit scope refresh | Code evidence | `docs/security/dependency-audit-scope-refresh-2026-06-04.md` | 🟢 LOW |

---

## 7. Highest-Risk Unverified Claims (Top 18)

These are the claims with the highest combination of priority, no test evidence, and no remediation timeline.

| Rank | ID | Source | Claim | Why High Risk |
|---|---|---|---|---|
| 1 | **SEC-01** | Risk register | Audit chain forgeable (HMAC ephemeral) — P0 blocker | No test, no commit, no timeline; still blocking production expansion |
| 2 | **SEC-02** | Risk register | MCP trust expiry not checked — P0 blocker | No test exercises the expired-trust call path |
| 3 | **SEC-07** | Risk register | Docker runs as root, no network isolation — P0 blocker | No test, no remediation plan |
| 4 | **SEC-10** | Risk register | `cat`/`head`/`tail` in inspect executables — P1 | Can read sensitive local files; no fix plan, no test |
| 5 | **SEC-13** | Risk register | Security paths mocked in tests — P1 | Confirmed to have hidden bugs before; no remediation date |
| 6 | **DS-01** | Risk register | TUI cost bar always $0.00 — P1 | Different from DS-13 (semantics); the TUI accumulation path still open |
| 7 | **DS-09** | Risk register | `agent run --background <uuid>` misuse — P1 | No guard, no test |
| 8 | **SC-02** | Risk register | ~~`anthropic`/`pyyaml` undeclared — P1~~ FIXED 2026-07-01 | Optional extras + import-guard contract test now cover the risk |
| 9 | **M0 Pending** | Roadmap | Risk register operational gate — listed as Pending despite `validate_docs_consistency.py` existing | GOV-002 through GOV-012 all still Pending; M0 conditions not fully met |
| 10 | **GOV-002 through GOV-012** | Roadmap | All Pending, no owners, no ticket IDs | 11 consecutive governance items with zero evidence |
| 11 | **H2 Pending** | Roadmap | Multi-surface continuity — no surface-parity tests | Identity/cost/recovery continuity across CLI+TUI+IDE unverified |
| 12 | **H3 Pending** | Roadmap | Ecosystem trust — no MCP trust-onboarding tests | Extension activation explain not implemented |
| 13 | **TASK-DD2-005 partial** | Ticket index | Broader ACs partially addressed | No test names listed for the un-addressed ACs |
| 14 | **TICKET-16 Phase 2** | Ticket index | Real suspend→resume round-trip claimed Fixed | No dedicated integration test name cited for the round-trip path |

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

## 9. Automated Validator Findings (2026-06-05)

`scripts/validate_docs_consistency.py --risk-register --ticket-index` was run immediately after this audit document was created, against the current working-tree files. Results supersede the manual coverage estimates in Section 8 where they conflict.

### Risk Register (26 rows parsed)

```
Risk register evidence coverage: 12/26 rows verified (46%)
High-risk uncovered P0/P1 rows: SEC-13, DS-01, DS-06, SC-02

ERROR: Risk register P0/P1 OPEN row has no linked evidence: SEC-13 (priority='P1').
ERROR: Risk register P0/P1 OPEN row has no linked evidence: DS-01 (priority='P1').
ERROR: Risk register P0/P1 OPEN row has no linked evidence: DS-06 (priority='P1').
ERROR: Risk register P0/P1 OPEN row has no linked evidence: SC-02 (priority='P1').
```

Note: DS-12, DS-13, SEC-02, SEC-04, SEC-06, SEC-07, SEC-10, SEC-11, DS-04, DS-05, DS-09, DS-02, SC-01, SC-02, and SC-03 have all been updated to FIXED/DOCUMENTED with test or code citations in the working tree; the manual audit in Section 3 captured an earlier snapshot.

### Ticket Index (21 rows parsed)

```
Ticket index evidence coverage: 15/21 rows verified (71%)

ERROR: Ticket TASK-DD2-004 claims Fixed but the index row cites no file path or test name.
ERROR: Ticket TASK-DD2-006 claims Fixed but the index row cites no file path or test name.
ERROR: Ticket TASK-DD2-007 claims Fixed but the index row cites no file path or test name.
ERROR: Ticket TASK-DD2-008 claims Fixed but the index row cites no file path or test name.
ERROR: Ticket TASK-DD2-011 claims Fixed but the index row cites no file path or test name.
ERROR: Ticket TASK-DD2-014 claims Fixed but the index row cites no file path or test name.
```

---

## 10. Recommended Remediation (Priority Order)

1. **Superseded 2026-07-01**: risk-register evidence coverage is now 29/29, and SC-02 is fixed by optional extras plus import-guard contract tests. Future failures should be handled by `validate_docs_consistency.py` rather than this historical recommendation.
2. **Immediate — exits CI**: Add file path or test name citations to TASK-DD2-004/006/007/008/011/014 rows in the ticket index.
3. **This sprint**: Assign owners and ticket IDs to GOV-002 through GOV-012 or mark them Deferred with justification.
4. **Next sprint**: Add surface-parity smoke tests for H2 exit criteria (CLI+TUI cost identity, approval identity, audit identity).
5. **Ongoing**: `scripts/validate_docs_consistency.py --risk-register --ticket-index` runs in CI to catch future table⇄header drift automatically.
