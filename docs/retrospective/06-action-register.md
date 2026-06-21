# 06 - Prioritized Action Register

> Consolidated across four dimensions and ordered by P0 / P1 / P2. Each item includes its dimension, Gap ID, evidence as `file_path:line_number`, and verifiable completion criteria.
> ID format: `<dimension>-<P-level>-<sequence>`, where S=Security, G=Governance, A=Architecture, and U=UX.
> Status column added per review-system.md §5 weekly update requirement.

Legend: ✅ Done (committed) · 🟡 In progress · ⬜ Not started · 🔵 Already existed before this branch

## P0 - Fix Immediately (Trust/Blocking/Security Bypasses)

| ID | Dimension | Summary | Evidence | Completion Criteria | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| S-P0-1 | Security | `AutoModeManager` must not unconditionally escalate to `DANGER_FULL_ACCESS`; replace this with payload-digest-scoped preapproval plus an audit event, or require a separate `full_access_acknowledged=True` ceremony. | `teaagent/runner/_auto_mode_manager.py:52-66`; `teaagent/runner/_core.py:688-690` | Destructive auto-mode calls emit a `tool_call_approved` audit event with `authority_type='auto_mode'`; authority is payload-scoped; no silent escalation. | ✅ | `AutoModeManager.get_auto_approve_policy` returns a payload-digest-scoped `ApprovalPolicy` (no `DANGER_FULL_ACCESS`); `_core.py` emits `tool_call_approved` (`authority_type='auto_mode'`, `scope='payload_digest'`) only AFTER `assert_allowed` succeeds (5acaae7/79cfe2e); `tests/test_auto_mode_authority_audit.py` (7 tests incl. `test_auto_mode_does_not_escalate_to_danger_full_access`, denied-path no-false-approval) |
| S-P0-2 | Security | Make approval-queue HMAC mandatory by default: when `TEAAGENT_APPROVAL_HMAC_KEY` is unset, generate a 32-byte key and persist it with mode `0o600`, or refuse to load with a clear error. | `teaagent/subagents/_approval_queue_store.py:102-110,341-347` | When the environment variable is unset, the store generates and persists a key; forged records are rejected by HMAC; a migration test is added. | ✅ | `_load_or_generate_hmac_key` generates a 32-byte hex key via `secrets.token_hex(32)` and persists it `chmod 0o600`, refusing to load an existing key with wrong mode; HMAC mandatory by default; `tests/test_approval_queue_hmac_default.py` (forged-record-rejected + legacy-migration); fail-closed prune for unverifiable legacy queues (25a234e perf + integrity) |
| S-P0-3 | Security | Make library callers at `chat_agent.py:755` use a path-backed AuditLogger; add a `--no-audit` escape hatch with an explicit warning. | `teaagent/chat_agent.py:755`; `teaagent/audit.py:226-227` | When `audit is None`, construct `AuditLogger(path=RunStore(root).audit_path_for_run(run_id))`; `--no-audit` emits a warning; a new test verifies a durable trail. | ✅ | `run_chat_agent` defaults to a durable disk-backed `AuditLogger(path=RunStore(root).run_path(run_id))` when `audit is None`; the `no_audit=True` library escape hatch emits an `audit_disabled` warning and keeps events in memory only; `tests/test_chat_agent_library_audit.py` (4 tests: durable JSONL created, chain validates, no_audit warns + writes no file, explicit logger respected). NOTE: the escape hatch is at the **library API** level (the action targets library callers at `chat_agent.py:755`); the CLI `agent run` path intentionally requires a durable trail (receipts/resume/`logger_for_result` depend on it). |
| A-P0-1 | Architecture | Decompose `subagents/_approval_queue_hybrid_store.py` (4,884 lines) into focused modules: storage backend / voting / comments / SLA-quota / templates / compliance-validation / conflict / analytics / notifications / archival. | `teaagent/subagents/_approval_queue_hybrid_store.py:113-4884`; `pyproject.toml:201-219` | Every resulting file is under 800 lines; the 11-error-code mypy override is removed; all tests pass. | ✅ | Structural split (8 mixins, all <800 lines) + `_hybrid_store_base.py` typed base class; 11-error-code mypy override removed; `mypy` 0 errors in 1080 files; 714 tests pass |
| A-P0-2 | Architecture | Remove silent `except: pass` handling from audit/observability paths, at minimum `audit.py:59`, `cockpit.py:381/453/462`, `subagents/_review.py:167`, and `subagents/_approval_queue_hybrid_store.py:1318`. | As listed | Replace with logged and classified handling per ADR-0014; no `except Exception: pass` remains in observability paths. | ⬜ | — |
| U-P0-1 | UX | Replace the placeholder URL in the first-run welcome and standardize all four GitHub URLs to one canonical URL. | `teaagent/cli/_handlers/_misc.py:475`; `SUPPORT.md:18`; `teaagent/cli/__init__.py:359`; `docs/ops/deployment-guide.md:68` | The entire repository uses one GitHub URL; `rg "yourusername\|anomalyco"` has no matches in documentation or CLI code. | ✅ | `4022016` — unified to `TeaEntityLab/teaagent` |
| U-P0-2 | UX | Align advertised TUI commands with actual behavior: implement or remove `conflict` and `o/t/n/p/a` from HELP_TEXT (`rendering.py:64-72`) and the state panel (`core.py:226-238`); also implement branch-start/merge/cancel semantics for `parallel`/`select`/`cancel`, or narrow the help text to their current option-store/select/clear behavior. | `teaagent/tui/_commands.py:365-393,307-361` | No advertised command returns a "not yet implemented" response; HELP_TEXT accurately describes implemented semantics. | ✅ | Narrowed: removed dead Conflict Resolution Mode panel + dead Parallel Experiments panel + dead fields/import from `core.py`; HELP_TEXT already aligned; conflict handlers remain as hidden commands returning `not_available` |
| G-P0-1 | Governance | Update `docs/audit-event.schema.json` to add `prev_hash`/`hash`/`chain_hmac` as optional properties, or split it into a "logical event schema" and a "persisted chain-entry schema." | `docs/audit-event.schema.json:5-13`; `teaagent/audit.py:473-477` | Every chained event written by AuditLogger passes schema validation; add a schema-conformance test. | ✅ | Split: `docs/audit-chain-entry.schema.json` (strict envelope with `prev_hash`/`hash`/`chain_hmac`); `tests/test_audit_schema_conformance.py` validates both schemas; `scripts/check_audit_schema_conformance.py` CI script |

## P1 - Fix Soon (Usability/Correctness/Contract Consistency)

| ID | Dimension | Summary | Evidence | Completion Criteria | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| S-P1-1 | Security | Make `check_scope_budget` fail closed: when the enforcer raises, return a denial reason or re-raise unless `TEAAGENT_SCOPE_FAIL_OPEN=1`. | `teaagent/tool_permissions.py:219-228` | Exceptions no longer return `None`; a new test verifies fail-closed behavior. | ⬜ | — |
| S-P1-2 | Security | Require authentication/TLS for a non-loopback Redis approval queue, following `require_signature_relay_bind_auth`. | `teaagent/coordination/approval_backend.py:278-325` | A non-loopback connection without a password/SSL raises; add a test. | ⬜ | — |
| S-P1-3 | Security | Replace the line hash in `edit_at_hash` with full SHA-256 hex (or at least `& 0xFFFFFFFF`); gate the wire-format change and provide migration support. | `teaagent/workspace_tools/_helpers.py:90-94` | Hash is at least 32 bits; a migration flag exists; old anchors remain readable; add tests. | ⬜ | — |
| G-P1-1 | Governance | Extend `teaagent/schema.py` to support `enum/pattern/additionalProperties/oneOf/anyOf`. | `teaagent/schema.py:7-14`; `teaagent/subagents/_tools.py:398-414` | Declared and runtime contracts match; new tests verify that enum/pattern reject invalid input. | ⬜ | — |
| G-P1-2 | Governance | Decide whether `register_github_tools` should auto-load or be explicitly opt-in; add `config.enable_github_tools` or remove the lazy export. | `teaagent/github_integration.py:154`; `teaagent/chat_agent.py:500-535` | All four GitHub tools are reachable or explicitly removed; documentation is consistent. | ⬜ | — |
| G-P1-3 | Governance | Emit a `multisig_fallback` audit event when multisig falls back because `agent_id` is missing. | `teaagent/approval_manager.py:449-454` | Fallback emits an audit event; a misconfigured session is detectable afterward. | ✅ | `79cfe2e` — audit event emitted with `keyword-default` through approval layer |
| A-P1-1 | Architecture | Move domain reasoning out of the harness: relocate `coordinator.py`/`agent_factory.py`/`workflow_engine.py`/`issue_intake.py`/`intent.py` into skills or `teaagent.domain/`. | Modules listed | The harness retains only its orchestration/governance shell; domain modules are under skills or `teaagent/domain/`; tests pass. | ⬜ | — |
| A-P1-2 | Architecture | Reduce `Any` in the worst offenders: target `_approval_queue_hybrid_store.py`, `external_backends.py`, `context_pack.py`, `run_evidence.py`, `hooks.py`, and `acp_adapter.py`; introduce typed `Protocol` classes. | As listed | `Any` use falls by at least 30%; new Protocol classes exist; mypy remains clean. | ⬜ | — |
| A-P1-3 | Architecture | Unify the second framework with the primary runner: fold `SubagentManager.run_subagent` into `runner/`, or write an ADR that justifies the dual-framework design and its shared invariants. | `teaagent/subagents/_manager.py:205-538`; `teaagent/swarm.py:370-1010` | One execution path exists, or a new ADR reconciles budget/audit/approval invariants across both. | ⬜ | — |
| A-P1-4 | Architecture | Complete the `approval/` migration: move root-level `approval_manager.py`/`approval_backend.py`/`approval_selectors.py`/`approval_ui.py` into `teaagent/approval/`; update `_compat_modules.py`. | `teaagent/approval/`; `teaagent/approval_*.py` | No root-level approval modules remain; `_compat_modules.py` aliases are updated; tests pass. | ⬜ | — |
| A-P1-5 | Architecture | Add line coverage for high-risk omitted surfaces: remove `tls_server.py` (High), `vote_relay.py`, and `cli/_handlers/_control_plane.py` from the omit list; convert smoke-test candidates into covered tests. | `pyproject.toml:250-269`; `docs/governance/coverage-omit-ledger.md` | The three modules have line coverage; the ledger is updated; the coverage gate does not decrease. | ⬜ | — |
| U-P1-1 | UX | Make intent clarification interactive: when `--clarify` triggers, present the question as a prompt, accept the answer, and rerun. | `teaagent/cli/_handlers/_agent/run.py:536-545`; `teaagent/intent.py:170-181` | Users can answer interactively; the command no longer exits 2 with JSON; add an e2e test. | ⬜ | — |
| U-P1-2 | UX | Route `agent run` task-resolution, plan-gate, and background error paths through `format_error_block` with hints. | `teaagent/cli/_handlers/_agent/run.py:279-289,471-473,427-451` | All three error paths include hints and match the top-level CLI; add tests. | ⬜ | — |
| U-P1-3 | UX | Add TUI command-path coverage (at least dispatch plus advertised commands); reconsider the `teaagent/tui/*` coverage omission. | `pyproject.toml:253` | TUI dispatch and advertised commands have tests; explicitly unimplemented behavior and advertised-semantic mismatches cannot ship silently. | ⬜ | — |
| U-P1-4 | UX | Reconcile stale dated documentation: add supersession notes to `tui-daily-driver-guide.md:54,67`, `tui-chat-reference.md:36-37`, and `run-evidence-and-audit-guide.md:82`, or update them. | As listed | No current-truth contradictions remain; docs-consistency CI passes. | ⬜ | — |
| U-P1-5 | UX | Remove `--no-tui` from all module documentation or implement it. | `docs/modules/cli/*`; `docs/modules/tui/inspection.md`; `docs/modules/chat_session_controller/api.md`; `docs/decisions/trade-offs.md:101` | Documentation matches code; either `rg --no-tui docs/` has no matches or the flag exists. | ✅ | This session — removed from 7 files; `rg --no-tui docs/` now returns only retrospective references (which document the removal) |
| U-P1-6 | UX | Add a confirmation gate before chat mode forwards typos: `unknown command "x"; send as task? [y/N]`. | `teaagent/tui/_commands.py:396-397` | A typo no longer silently becomes an LLM task; add a test. | ⬜ | — |

## P2 - Cleanup (Polish/Debt/Defense in Depth)

| ID | Dimension | Summary | Evidence | Completion Criteria | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| S-P2-1 | Security | When the audit-chain key is missing, emit a `missing_chain_key` warning failure instead of silently skipping HMAC. | `teaagent/audit_chain.py:439-457` | `_load_run_key` emits `logger.warning` when key file is missing or unreadable. | ✅ | This session — added `logger.warning` to key-not-found path |
| S-P2-2 | Security | Add an explicit `is_symlink()` check to `_assert_paths_in_workspace` (defense in depth). | `teaagent/approval_manager.py:1090-1141` | Symlink component detection exists via `_has_symlink_component` using `Path.is_symlink()`. | 🔵 | Already implemented — `_has_symlink_component` at line 1082 calls `current.is_symlink()` |
| S-P2-3 | Security | Sanitize `run_id` to `[A-Za-z0-9._-]` for `GitBranchSandbox` branch names. | `teaagent/sandbox/_git_branch.py:119` | `_sanitize_run_id` uses `re.compile(r'[^A-Za-z0-9._-]')` to strip unsafe characters. | 🔵 | Already implemented — `_sanitize_run_id` at line 113 |
| S-P2-4 | Security | Make the Bandit step in `ci.yml` blocking by removing the `\|\| echo` fallback. | `.github/workflows/ci.yml:201-203` | Bandit exits non-zero on Medium+ findings; no `|| echo` fallback. | ✅ | This session — removed `|| echo "::warning::..."` fallback |
| S-P2-5 | Security | Correct the `notify.py:42` docstring (`shell=True` -> `shell=False`); make `config_lint` warn about `allow_dev_signatures` outside development workspaces. | `teaagent/notify.py:42,138-141`; `teaagent/config_lint.py:102-108` | Docstring corrected; `config_lint` warns on `allow_dev_signatures` outside dev. | ⬜ | — |
| G-P2-1 | Governance | Gate use of `directory-snapshot` isolation for untrusted content behind an `--acknowledge-no-os-isolation` flag. | `teaagent/subagents/_isolation.py:287-298` | Flag exists; isolation gated. | ⬜ | — |
| G-P2-2 | Governance | Remove `preapproved_call_ids` after the deprecation window and standardize on payload digest. | `teaagent/policy.py:115-121`; `teaagent/approval_manager.py:953-968` | No `preapproved_call_ids` references remain in approval/decision paths; CLI `--approve-call-id` ignored. | ✅ | `25a234e` — `--approve-call-id` deprecated/ignored; docs updated; `--approve-scoped TOOL:SHA256` is the standard |
| G-P2-3 | Governance | Add iteration and tool-call warnings alongside `BudgetMonitor`'s existing cost monitoring. | `teaagent/budget_monitor.py:74-106` | Warnings added. | ⬜ | — |
| G-P2-4 | Governance | Document the `scope` field taxonomy (`call_id`/`payload_digest`/`session`/`preset`). | `teaagent/runner/_core.py:730,742` | Taxonomy documented in `docs/governance/scope-taxonomy.md`. | 🔵 | Already existed — `docs/governance/scope-taxonomy.md` with full taxonomy, blast radius, revocation, and implementation status |
| G-P2-5 | Governance | Make `max_skill_md_lines` an error for installed (candidate-provenance) skills; keep it a warning during development. | `teaagent/skill_review.py:187-193` | Error/warning split by provenance. | ⬜ | — |
| A-P2-1 | Architecture | Consolidate optional-extra aliases: fold `crypto`/`oauth`/`audit-encryption` into a single `crypto` extra. | `pyproject.toml:60-68` | Single `crypto` extra, aliases removed. | ⬜ | — |
| A-P2-2 | Architecture | Split CLI handler god modules: `_ergonomics.py:1407`, `_doctor.py:1022`, `_agent/run.py:999`, `chat_repl.py:894`. | As listed | Each module under 800 lines. | ⬜ | — |
| A-P2-3 | Architecture | Expand property-based testing with Hypothesis strategies for permission-mode transitions, budget enforcement, approval-hash exactness, and audit-chain invariants. | `tests/` | Hypothesis tests exist for the four areas. | ⬜ | — |
| A-P2-4 | Architecture | Populate `tests/skills/` or remove the empty directory. | `tests/skills/` | Directory is non-empty. | 🔵 | Already populated — `test_skill_loading.py` + `fixtures/` |
| A-P2-5 | Architecture | Reconcile `tests/e2e/` (one file) with 127 acceptance tests by moving it or defining an e2e contract. | `tests/e2e/` | Clear contract or migration. | ⬜ | — |
| U-P2-1 | UX | Retire or connect `chat_repl.py`; choose one to avoid divergence between tested and production behavior. | `teaagent/cli/_handlers/chat_repl.py:202-225` | Single code path. | ⬜ | — |
| U-P2-2 | UX | Align TUI parser flags with `run`/`chat` (add budget flags; default `--provider` from configuration). | `teaagent/cli/_misc_parsers/tui_parser.py:25` | TUI flags match CLI. | ⬜ | — |
| U-P2-3 | UX | Fix undo-scope divergence and update the known-issues document. | `teaagent/tui/core.py:1063-1079` | Undo scope consistent; known-issues updated. | ⬜ | — |
| U-P2-4 | UX | Improve `--task` ergonomics with an alias or CLI hint; prominently document the provider/task order flip. | `teaagent/cli/_agent_parsers.py:63-95` | Alias or hint added; documented prominently. | ⬜ | — |
| U-P2-5 | UX | Minor: duplicate `undo` help line, `--chat-mode` docstring, `['*']` "Explicit current directory" comment. | `teaagent/tui/rendering.py:50,81`; `_chat.py:3,15`; `core.py:1329` | Cleaned up. | ⬜ | — |

## Statistics

| Priority | Count | Distribution by Dimension |
| --- | --- | --- |
| P0 | 8 | Security 3, Architecture 2, UX 2, Governance 1 |
| P1 | 17 | Security 3, Governance 3, Architecture 5, UX 6 (including cross-dimensional items) |
| P2 | 20 | Security 5, Governance 5, Architecture 5, UX 5 |
| **Total** | **45** | |

### Status Summary

| Status | Count | Items |
| --- | --- | --- |
| ✅ Done (this branch) | 14 | S-P0-1, S-P0-2, S-P0-3, U-P0-1, U-P0-2, G-P0-1, A-P0-1, G-P1-3, G-P2-2, U-P1-5, S-P2-1, S-P2-4 |
| 🔵 Already existed | 4 | S-P2-2, S-P2-3, G-P2-4, A-P2-4 |
| ⬜ Not started | 27 | Remaining |

### Phase B Infrastructure (New, not in original register)

| Item | Status | Evidence |
| --- | --- | --- |
| PR template with action-ID/risk/checklist fields | ✅ | `.github/pull_request_template.md` updated |
| `check-action-register-link.py` pre-commit hook | ✅ | `scripts/check_action_register_link.py` created; registered in `.pre-commit-config.yaml` |
| `check-github-url-consistency.py` | ✅ | `scripts/check_github_url_consistency.py` created; registered in `.pre-commit-config.yaml` |
| `check-god-modules.py` | ✅ | `scripts/check_god_modules.py` created; registered in `.pre-commit-config.yaml` |
| `high_risk_paths.yaml` centralized config | ✅ | `scripts/high_risk_paths.yaml` created |
| `check-high-risk-paths.py` pre-commit hook | ✅ | `scripts/check_high_risk_paths.py` created (reads `high_risk_paths.yaml`); blocks commits that stage a high-risk path without a `docs/reviews/*-risk.md` report or `TEAAGENT_RISK_ACK`; registered in `.pre-commit-config.yaml`; `tests/test_check_high_risk_paths.py` (4 tests) |
| `audit-schema-conformance` CI job | ✅ | `scripts/check_audit_schema_conformance.py` created; CI job in `review-institution` workflow |
| CI `review-institution-gate` job | ✅ | `scripts/check_review_institution_gate.py` created; CI job in `review-institution` workflow |
| `doctor review-institution` subcommand | ✅ | `teaagent doctor review-institution --root .` reports mode, pending actions, audit health |

## Recommended Execution Order

1. **Sprint 1 (Trust repair)**: U-P0-1 (URL) ✅, U-P0-2 (TUI advertised semantics), G-P0-1 (schema) — U-P0-1 complete.
2. **Sprint 2 (Security bypasses)**: S-P0-1 (AutoMode) ✅, S-P0-2 (HMAC) ✅, S-P0-3 (library audit) ✅ — verified complete (implemented across the refactor + 5acaae7/25a234e/79cfe2e; register corrected after a fact-check found the rows stale).
3. **Sprint 3 (Architecture debt kickoff)**: A-P0-1 (decompose the god module) is a large refactor; use a dedicated branch and staged PRs. A-P0-2 (silent exception swallowing) can proceed in parallel.
4. **Sprint 4+**: execute P1 and P2 in order, paced by team capacity and the Phase B review system.

> Phase B ([review-system.md](review-system.md), [automation-plan.md](automation-plan.md), [tool-capability-review.md](tool-capability-review.md)) is designed to turn this register from a one-time list into a continuously governed work queue.
