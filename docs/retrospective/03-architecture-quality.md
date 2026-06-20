# 03 - Architecture and Code Quality Audit

> Dimension priority: **Third** | Method: cx overview / cx references + Read/Grep + direct execution of `mypy`, `check_root_module_count`, and `check_complexity`

## Module Map (Selected Highlights)

| Module | Responsibility | H/D | Coupling Notes |
| --- | --- | --- | --- |
| `runner/_core.py` (1095) | Agent loop: decision dispatch, budget, audit, and tool execution | Harness | Imports audit/budget/policy/tools/context - central hub |
| `runner/_events.py` | EventSpine + RunEventType (ADR-0032) | Harness | `register_audit_consumer` |
| `tools.py` | ToolRegistry, ToolDefinition, ToolAnnotations | Harness | Home of the AGENTS.md tool-governance contract |
| `audit.py` (922) | AuditEvent, AuditLogger, redaction | Harness | Audit backbone |
| `errors.py` (219) | AgentHarnessError + 10 subclasses, ErrorCategory, DenialReasonCode | Harness | Shared by runner/CLI/approval |
| `policy.py` | ApprovalPolicy, PermissionMode, multisig | Harness | ADR-0010/0011 |
| `approval_manager.py` (1378) | ApprovalManager, JIT, MultiSigQuorumManager | Harness (large) | Root-level god module; ADR-0011 |
| `sandbox/_git_branch.py` (1065) | GitBranchSandbox, worktree isolation | Harness | ADR-0020/0028 |
| `cli/` (80 files, 518 symbols) | CLI entry point, subparsers, handlers | Harness (thin) | `add_agent_run_arguments` reused 3x |
| `tui/core.py` (1509) | TUI event loop, prompt-toolkit | Harness (UI) | Coverage omitted; ADR-0025 |
| `skills/` (built-ins only) | SKILL.md skill assets | Protocol asset | Loader in `skill_loader.py` (1050) |
| `subagents/_manager.py` (587) | SubagentManager: recursive child runner | **Domain/second framework** | Custom registry/config/approval handler; ADR-0022 |
| `subagents/_approval_queue_hybrid_store.py` (**4884**) | HybridApprovalQueueStore | **Domain god module** | 60+ features; see Gaps |
| `swarm.py` (1010) | SwarmManager, Subagent, tournament | **Domain/second framework** | ADR-0019/0028; parallel to runner |
| `consensus/` (6 files, 161 symbols) | ConsensusEngine, VotingMechanism, PeerRegistry | **Domain/second framework** | ADR-0019/0029 |
| `governance/` (16 files, 350 symbols) | policy_engine, rbac, release_gate, review_gate, scope_creep | Harness governance | ADR-0009 five-loop model |
| `ergonomics/` (21 files, 220 symbols) | approval_state, background_run, daily_cost, run_history | Harness UX | `cli/_handlers/_ergonomics.py` (1407) god module |
| `oauth21/` (11 files, 214 symbols) | DPoP, PKCE, replay, stores | Harness auth | ADR-0004/0006 |
| `code_analysis/` (9 files) | tree-sitter, graph-RAG, LSP client | Domain tooling | Optional extra |
| `workspace_tools/` (10 files) | File/shell/git tools | Harness tools | builder/_git/_config coverage omitted |

## Evidence

### God Modules (Largest Files)
- **`teaagent/subagents/_approval_queue_hybrid_store.py:113-4884`** - A single `HybridApprovalQueueStore` class spanning 4,771 lines. Its `__init__` spans lines `131-300` and defines roughly 30 instance attributes (`_delegations`, `_escalations`, `_comments`, `_approval_history`, `_approval_quotas`, `_workflow_chains`, `_reviewer_assignments`, `_approval_templates`, `_request_tags`, `_votes`, `_reminders`, `_sla_deadlines`, `_versions`, `_conflicts`, `_dependencies`, `_signatures`, `_tags`, `_analytics`, `_notifications`). `cx overview` lists 60+ methods: `cast_vote`, `add_comment`, `delegate_approval`, `assign_reviewer`, `create_workflow_chain`, `create_approval_template`, `apply_approval_template`, `add_dependency`, `check_sla_compliance`, `check_approval_quota`, `add_compliance_rule`, `add_validation_rule`, `detect_conflict`, `archive_old_requests`, `clear_notifications`, `bulk_approve_requests`, `bulk_deny_requests`, `create_version` - an entire approval product embedded in the harness.
- 4,884 lines equals 45% of the `subagents/` package (11,011 total lines).
- Other large files: `tui/core.py:1-1509`, `cli/_handlers/_ergonomics.py:1-1407`, `approval_manager.py:1-1378`, `cli/_agent_parsers.py:1-1248`, `run_evidence.py:1-1104`, `runner/_core.py:1-1095`, `sandbox/_git_branch.py:1-1065`, `tui/_commands.py:1-1060`, `skill_loader.py:1-1050`, `cli/_handlers/_doctor.py:1-1022`, `swarm.py:1-1010`.

### Second Framework (AGENTS.md Rule)
- `teaagent/subagents/_manager.py:205-538` `SubagentManager` recursively constructs child runners with a custom registry/config/approval handler.
- `teaagent/swarm.py:370-1010` `SwarmManager` is a parallel orchestrator (`execute_swarm`, `_select_tournament_winner`, `_execute_subagent_batch`, heartbeat loop).
- ADRs are present: `docs/adr/0019-phase-4-federated-swarm-consensus.md`, `0028-tournament-swarm-architecture.md`, `0022-centralized-approval-queue-subagents.md`, `0029-consensus-validation-deferred.md`. The AGENTS.md rule, "Do not add a second framework without an ADR," is satisfied.

### Domain Logic Leaking into the Harness
- `subagents/_approval_queue_hybrid_store.py` (voting, comments, SLA, templates, compliance, delegation, escalation, reminders, analytics) contains approval-product domain logic rather than harness orchestration. This violates `AGENTS.md:5`.
- `coordinator.py` (`_classify_task_with_llm`, `_generate_workflow_plan`), `agent_factory.py` (`_generate_evolution_prompt`, `_llm_evolve_prompt`), `workflow_engine.py:1-748` (`_generate_self_correction_prompt`, `_generate_unified_diff`), `issue_intake.py:1-922` (AmbiguityDetector, ChecklistGenerator, CommandSuggester), and `intent.py` (`clarify_task`) place domain task-planning reasoning in harness modules.

### Duplication (Revalidation of Earlier Notes)
- "Agent run argument parsing variations" - **Resolved**: `teaagent/cli/_agent_parsers.py:63` contains the single definition of `add_agent_run_arguments`, reused at `:392` (ask), `:425` (run), and `:679` (chat with `include_task_positional=True`).
- "Chat command handler logic duplication" - **Refactored**: split into `chat_commands.py:1-305`, `chat_repl.py:1-894`, `_chat.py:1-66`, and `chat_completion.py:1-113`; `chat_repl.py:25-33` imports slash handlers from `chat_commands` without duplicating logic.
- "CLI handlers undefined names" (bugfix 1567) - `git log --oneline --all | rg undefined` has no matches; the current `mypy teaagent/` run reports "Success: no issues found in 464 source files," so the undefined-name debt is cleared.

### Type Safety
- `pyproject.toml:166-219` enables strict mypy: `disallow_untyped_defs=true`, `disallow_incomplete_defs=true`, `check_untyped_defs=true`, `warn_unused_ignores=true`, `warn_redundant_casts=true`, `no_implicit_optional=true`, `python_version="3.10"`.
- The test override (`177-199`) disables 15 error codes (arg-type, union-attr, var-annotated, index, return-value, func-returns-value, str-bytes-safe, list-item, dict-item, operator, method-assign, override, call-overload, misc, assignment).
- The subagent approval-queue-store override (`201-219`) disables 11 error codes, including `attr-defined`, `misc`, and `unused-ignore` - a clear signal that the god module is not type-clean.
- **Current `mypy teaagent/` execution: Success: no issues found in 464 source files** (clean).
- `# type: ignore` appears **22 times** in `teaagent/` (low), concentrated in `memory/file_watcher.py:12` (12 occurrences), `subagents/_approval_queue_hybrid_store.py:4`, and `prompt.py:2`.
- `Any` appears on **2,199 lines** (2,379 raw occurrences; high). Top files by matching-line count: `subagents/_approval_queue_hybrid_store.py:71`, `external_backends.py:44`, `context_pack.py:30`, `run_evidence.py:28`, `hooks.py:28`, `acp_adapter.py:26`.
- mypy runs in pre-commit (`.pre-commit-config.yaml:32-36`) and CI (`.github/workflows/ci.yml:198-199`).

### Error Handling
- `teaagent/errors.py:39-219` is well designed: an `AgentHarnessError.hint` field, `ErrorCategory` enum, `DenialReasonCode` enum, and 10 subclasses, each with an actionable default hint.
- Roughly 20 exceptions are silently swallowed with `except Exception: pass/continue/return None`:
  - `teaagent/audit.py:59-60` `except Exception: pass` (the audit logger itself swallows errors, creating an observability concern)
  - `teaagent/cockpit.py:381-382,453-454,462-463` three `pass` blocks
  - `teaagent/extension_explain.py:161-162,198-199,234-235` three blocks
  - `teaagent/context_pressure.py:131-132,138-139` two blocks
  - `teaagent/ergonomics/background_run.py:39-40`
  - `teaagent/asset_provenance.py:135-136`
  - `teaagent/subagents/_review.py:167-168`
  - `teaagent/subagents/_approval_queue_hybrid_store.py:1318-1319`
  - `teaagent/approval_manager.py:1035-1036` `continue`
  - `teaagent/governance/repo_map_benchmark.py:275-276,301-302,327-328` three `continue` blocks
  - `teaagent/memory/file_watcher.py:98-99,129-130` `return`
  - `teaagent/code_analysis/_manager.py:43-44` `return None`
- There are roughly 40+ broad `except Exception:` blocks; most log, but the cases above are silent.

### Tests
- 542 Python test files and **6,103 test definitions** matching `^\s*(async\s+)?def test_`; the raw `def test_` occurrence count is 6,152.
- `tests/` structure: `acceptance/` (127), `integration/` (34), `regression/` (4), `e2e/` (1), `lifecycle/` (2), `policy/` (1), `skills/` (0 - empty), and about 370 top-level `test_*.py` files.
- `pyproject.toml:153-164` pytest markers: `integration/smoke/acceptance/nightly/slow/test_type`.
- `scripts/run_test_tier.py:30-52` defines the smoke tier as 20 explicit governance-core + regression tests; `:55-63` dispatches smoke/acceptance/nightly tiers.
- Coverage gate: `.github/workflows/ci.yml:141` uses `--cov=teaagent --cov-report=term-missing --cov-fail-under=75` (75% gate, Ubuntu/Python 3.12 cell).
- Harness core is covered by `tests/test_p0_harness.py`, `test_chat_agent.py`, `test_run_store.py`, `test_run_evidence.py`, `test_subagent_isolation.py`, and `test_prompt.py`.
- Hypothesis use is minimal: `.hypothesis/` exists, but only one test file imports `hypothesis` (the cache may be stale).
- `test_support.py:1-50` provides `skip_if_socket_bind_is_blocked` / `skip_if_thread_start_is_blocked` for sandboxed CI.

### Coverage Omit Assessment
- `pyproject.toml:250-269` omits 16 patterns: `tui/*`, `tournament/*`, `validation/*`, `workflow_engine.py`, `vote_relay.py`, `tls_server.py`, `webhook_sink.py`, `wasm_runtime.py`, `wasm_skill.py`, `tsb_format.py`, `workspace_tools/builder.py`, `workspace_tools/_git.py`, `workspace_tools/_config.py`, `browser_tools.py`, `cli/_handlers/_cost.py`, and `cli/_handlers/_control_plane.py`.
- `docs/governance/coverage-omit-ledger.md:1-80` records Owner/Reason/Risk/Expected Return Milestone/Smoke-Test Candidate for every omission; `scripts/validate_docs_consistency.py` enforces ledger-to-pyproject consistency in CI. **This is mature governance, not neglect**, but it still means 16 surfaces face no line-coverage pressure. **High-risk omission: `tls_server.py` (Risk: High per ledger:42)**.

### Lint, Format, and Quality Tooling
- `ruff.toml:1-56`: selects E/F/W/I/B/SIM/T201; a per-file T201 allowlist covers CLI/server code; single quotes and space indentation.
- `.pre-commit-config.yaml:1-67`: 10 hooks - lore-trailers, check-circular-imports, check-event-spine-wiring (ADR-0032), ruff-format, ruff (`--fix --exit-non-zero-on-fix`), mypy, check-public-docstrings, check-test-assertion-regression (A1 gate), pytest (smoke or `TEAAGENT_PRECOMMIT_FULL=1`), and check-docs-inventory.
- `.github/workflows/ci.yml:162-223` lint job: public-docstrings, config-access (`--max 65`), complexity (`--max 99`), ruff check, ruff format `--check`, mypy, bandit (advisory), test-quality (`--fail-on severe`), test-assertion-regression, and agent-contribution-contract.
- `scripts/check_complexity.py` defaults to a maximum of 50; the current direct run reports **99 C901 violations** and fails that default target. CI explicitly invokes the script with `--max 99`, so CI permits the current 99 violations. The script default and CI gate must remain distinct.
- `scripts/check_root_module_count.py:14` has `ROOT_BASELINE = 184`; current result: **177** (under the gate).
- `.github/workflows/` contains seven workflows: ci, nightly-mutation, nightly-smoke (claude/gpt/gemini/openrouter/opencodezen-go), publish-tsb, release, security, and wasm-skill-build.

### Dependencies
- `pyproject.toml:25-31` defines five core dependencies: `bandit`, `cryptography`, `msgpack`, `python-multipart`, and `starlette`. All are used across six files.
- `pyproject.toml:39-138` defines **19 optional-extra groups**: config/file-watching/tui/code-analysis/graphqlite/playwright/crypto/oauth/audit-encryption/managed-google-adk/managed-vertex/telemetry/anthropic/yaml/wasm/release/security/sigstore/github/redis/blake3/dev.
- **Fragmentation concern**: `crypto` (`60-62`), `oauth` (`63-65` -> `teaagent[crypto]`), and `audit-encryption` (`66-68` -> `teaagent[crypto]`) are three aliases for the same crypto extra, creating unnecessary fragmentation.
- `pyproject.toml:143-151` uv overrides pin `tuf>=7.0.0,<8` and `opentelemetry-exporter-gcp-logging` for supply-chain control.

### ADRs
- `docs/adr/README.md:1-138` lists 32 ADRs (0001-0032) with an index, status legend, template, and categories. The convention is established and followed.
- Second-framework ADRs are present: 0019/0022/0028/0029. This complies with `AGENTS.md:7`.
- Refactoring ADRs: 0010 (circular dependencies - Superseded), 0011 (ApprovalManager SRP - Implemented), 0012 (chat_agent coupling - Superseded), 0013 (backend abstraction - Implemented), 0014 (error handling - Archived), 0015 (config plugin - Rejected), 0016 (tool DI - Implemented), 0017 (backend interfaces - Archived), 0018 (async-from-sync - Implemented).
- ADR-0030 (root-module-freeze) is enforced by `scripts/check_root_module_count.py` in pre-commit and CI.
- ADR-0032 (run-event-taxonomy) is enforced by `scripts/validate_event_spine_wiring.py` in pre-commit.

### Documentation
- `docs/INDEX.md:1-201` defines a three-tier reading model (Current truth / Active work / Historical evidence).
- `docs/DOCUMENTATION_STRATEGY.md:1-174` defines Tier 1 canonical / Tier 2 historical documentation; `scripts/validate_docs_consistency.py` is a CI gate (`ci.yml:38-39`).
- `docs/governance/coverage-omit-ledger.md` gives every omission a complete attribute set.
- `ABSTRACTION_LAYER_SUMMARY.md:1-95` describes the `cli/execution.py` abstraction layer (ADR-0026), consistently with the implementation.

### Build and Packaging
- `pyproject.toml:1-3` uses setuptools >=82.0.1; `:7` sets version `0.1.0`; `:14` sets `Development Status :: 3 - Alpha`.
- `setup.py:1-6` is a stub for legacy editable-install compatibility (PEP 517/660), with an explicit comment, so it is not redundant.
- `MANIFEST.in:1-17` includes LICENSE/README/CHANGELOG/SECURITY/pyproject/requirements, docs, examples, and `py.typed`; it excludes cache/build artifacts.
- `teaagent.egg-info/` exists as an editable-install artifact.
- `.github/workflows/ci.yml:289-322` package job runs `python -m build`, `twine check dist/*`, and a wheel smoke install that verifies `teaagent.__version__` and `py.typed`. Clean.

## Strengths

1. **Type safety is real**: strict mypy + a clean run (464 files, 0 issues) + CI and pre-commit gates; only 22 `# type: ignore` occurrences in the entire package.
2. **Quality gates are comprehensive and enforced**: ruff, ruff format, mypy, bandit, complexity (<=99), root-module-count (<=184), circular-imports, event-spine-wiring, public-docstrings, test-assertion-regression (A1), test-quality, agent-contribution-contract, docs-inventory, and docs-consistency. Seven CI workflows include nightly provider smoke tests and weekly security checks.
3. **Strong ADR discipline**: 32 ADRs with an index, status legend, template, and categories. Every major architecture decision (swarm, consensus, approval queue, root freeze, event spine, plan-before-write) has an ADR. The AGENTS.md second-framework rule is satisfied.
4. **Actionable error model**: the `errors.py` base class has a `hint` field, populated by every subclass; `ErrorCategory` and `DenialReasonCode` enums enable programmatic classification.
5. **Large, tiered test suite**: 6,103 test definitions across 542 Python files (6,152 raw `def test_` occurrences); smoke/acceptance/nightly tiers; 75% coverage gate; a separate governance-gate job runs fuzz/permission-matrix/plan-enforcement tests.
6. **Governed coverage omission ledger**: every omission records owner/reason/risk/return-milestone/smoke-candidate, and CI validates ledger-to-pyproject consistency.
7. **Mature documentation governance**: Tier 1/Tier 2 model, curated INDEX, generated inventory, and consistency validation in CI.
8. **Previously noted duplication has been resolved**: `add_agent_run_arguments` has one source and three reuse points; chat handlers are cleanly split; the `cli/execution.py` abstraction layer decouples CLI and core.
9. **Root-module freeze (ADR-0030) is constraining growth**: 177 <= 184 baseline, with CI preventing regression.

## Gaps

| ID | Severity | Summary | Evidence |
| --- | --- | --- | --- |
| G-CRIT-1 | **Critical** | `subagents/_approval_queue_hybrid_store.py:113-4884` is a 4,771-line single-class god module containing an entire approval product (voting/comments/SLA/templates/compliance/validation/conflict/archive/reviewer assignment/workflow chains/notifications/reminders/analytics/encryption/compression/circuit breaker/Prometheus). `pyproject.toml:201-219` disables 11 mypy error codes for this module, effectively exempting it from type governance. It accounts for 45% of the `subagents/` package. | `teaagent/subagents/_approval_queue_hybrid_store.py:113-4884`; `pyproject.toml:201-219` |
| G-HIGH-1 | High | Domain logic leaks into the harness: `coordinator.py`, `agent_factory.py`, `workflow_engine.py:1-748`, `issue_intake.py:1-922`, and `intent.py` contain domain task-planning/reasoning, violating `AGENTS.md:5`. | Modules above |
| G-HIGH-2 | High | A second agent framework runs parallel to `runner/`: `subagents/_manager.py:205-538`, `swarm.py:370-1010`. ADRs exist (literal compliance), but the thin-harness principle is violated because two execution frameworks double the correctness surface for budget/audit/approval. | `teaagent/subagents/_manager.py:205-538`; `teaagent/swarm.py:370-1010` |
| G-HIGH-3 | High | **2,199 lines contain `Any`** (2,379 raw occurrences) - heavy use of `Any` as an escape hatch weakens strict mypy. Top files by matching-line count: `_approval_queue_hybrid_store.py:71`, `external_backends.py:44`, `context_pack.py:30`, `run_evidence.py:28`, `hooks.py:28`. | `rg -n "\bAny\b" teaagent -g '*.py'` |
| G-HIGH-4 | High | Roughly 20 exceptions are silently swallowed in observability/governance-adjacent paths: `audit.py:59` (the audit logger itself), `cockpit.py:381/453/462` (health surface), `context_pressure.py:131/138`, `extension_explain.py:161/198/234`, `ergonomics/background_run.py:39`, `subagents/_review.py:167`, `subagents/_approval_queue_hybrid_store.py:1318`, `governance/repo_map_benchmark.py:275/301/327`. | As listed |
| G-MED-1 | Medium | Several large root modules remain: `approval_manager.py:1-1378`, `run_evidence.py:1-1104`, `chat_agent.py:1-911`, `federated_sync.py:1-763`, `workflow_engine.py:1-748`, `plan_storage.py:1-748`, `release_evidence.py:1-745`. The freeze prevents growth but does not reduce the existing 177 modules. | As listed |
| G-MED-2 | Medium | CLI handler god modules: `cli/_handlers/_ergonomics.py:1-1407`, `_doctor.py:1-1022`, `_agent/run.py:1-999`, `chat_repl.py:1-894`. | As listed |
| G-MED-3 | Medium | `approval/` (7 files) coexists with root-level `approval_manager.py`, `approval_backend.py`, `approval_selectors.py`, and `approval_ui.py`, indicating a partial migration. ADR-0011 targets consolidation but root-level modules remain (including deprecated aliases in `_compat_modules.py` per ADR-0030). | `teaagent/approval/`; `teaagent/approval_*.py` |
| G-MED-4 | Medium | The 16 coverage omissions include high-risk `tls_server.py` (Risk: High at ledger:42) and medium-risk `vote_relay.py`, `wasm_runtime.py`, `wasm_skill.py`, `tsb_format.py`, `workflow_engine.py`, `tournament/*`, `browser_tools.py`, and `cli/_handlers/_control_plane.py`. Return milestones are Phase 0/1/2 with no date commitment. | `pyproject.toml:250-269`; `docs/governance/coverage-omit-ledger.md` |
| G-MED-5 | Medium | Optional extras are over-fragmented: `crypto`/`oauth`/`audit-encryption` are three aliases for the same `teaagent[crypto]` extra. Nineteen extra groups are excessive for alpha 0.1.0. | `pyproject.toml:60-68` |
| G-MED-6 | Medium | Hypothesis use is minimal (one test file versus a `.hypothesis/` cache directory); property-based testing is underused on governance, permission, and safety-critical surfaces. | `tests/` |
| G-LOW-1 | Low | `tests/skills/` is empty (0 files). | `tests/skills/` |
| G-LOW-2 | Low | `tests/e2e/` contains only one file; e2e coverage is thin relative to 127 acceptance tests. | `tests/e2e/` |
| G-LOW-3 | Low | `setup.py` is only a legacy editable-install compatibility stub. | `setup.py:4-5` |

## AGENTS.md Rule Compliance

| Rule | Compliance | Evidence |
| --- | --- | --- |
| "Keep the harness thin" (`AGENTS.md:5`) | **Partial violation** | `_approval_queue_hybrid_store.py` god module; domain reasoning from `coordinator`/`agent_factory`/`workflow_engine`/`issue_intake`/`intent` in the harness |
| "domain reasoning belongs in the model or skills" (`AGENTS.md:5`) | **Violation** | `_classify_task_with_llm`, `_generate_evolution_prompt`, `_generate_self_correction_prompt`, and `clarify_task` are domain reasoning in harness modules |
| "Prefer protocol assets over vendor-specific" (`AGENTS.md:6`) | Compliant | `mcp_*`, `acp_adapter`, `anp_adapter`, `agentcard` (A2A), `stateless_mcp`; vendor code is isolated behind optional extras in `llm/_adapters.py` and `managed_runtime.py` |
| "No second agent framework without an ADR" (`AGENTS.md:7`) | Compliant (literally) | ADRs 0019/0022/0028/0029 cover swarm/subagents/consensus/tournament |
| "Tools registered through ToolRegistry" (`AGENTS.md:11`) | Compliant | `teaagent/tools.py` `ToolRegistry`/`ToolDefinition`/`ToolAnnotations` |
| "Each tool: name, desc, input, output, annotations" (`AGENTS.md:12`) | Compliant | `tools.py` dataclasses per `cx overview` |
| "Destructive tools need approval token for exact call" (`AGENTS.md:13`) | Compliant | `errors.py:104-124` `ToolPermissionError` + `DenialReasonCode`; approval hash in `policy.py`; `approval_token_exactness` test |
| "Tool errors actionable and classified" (`AGENTS.md:14`) | Compliant | `errors.py:28-36` `ErrorCategory`; `:9-25` `DenialReasonCode`; `:52-54` `hint` |
| "Every run: iteration limit + tool-call limit" (`AGENTS.md:18`) | Compliant | `budget.py` `RunBudget`; `auto_mode.py` `AutoModeGuard` |
| "Every tool call and final result recorded in audit" (`AGENTS.md:19`) | Compliant | `runner/_events.py` EventSpine + `register_audit_consumer`; ADR-0032; `audit.py` AuditLogger |
| "Long-lived state externalized" (`AGENTS.md:20`) | Compliant | `run_store.py`, `checkpoint.py`, `abstract_store.py`, `context_bus.py` (SQLite), `automations.py` `AutomationStore` |
| "SKILL.md short, details in REFERENCE.md" (`AGENTS.md:24`) | Compliant | Tracked `.opencode/skill/*` contains 7 SKILL.md files, all <=73 lines; tracked `teaagent/skills/builtin/rss-summary/SKILL.md` is 62 lines and routes details to REFERENCE/examples. `.agents/skills` is an ignored local symlink to `/Users/teee/.agents/skills`, not a checked-in TeaAgent asset. |
| "Skills as reviewed supply-chain assets" (`AGENTS.md:25`) | Partially verified | `skill_review.py` `DangerousPatternVisitor` + `BLOCKLIST_PATTERNS`; `skill_lifecycle.py` `SkillLifecycleTracker`; provenance in `skill_candidate_artifacts.py` |

## Recommendations

### P0 (Critical)
1. **Decompose `subagents/_approval_queue_hybrid_store.py` (4,884 lines)** into focused modules: storage backend (file/Redis sync, compression, encryption), voting, comments, SLA/quota, templates, compliance/validation rules, conflict detection, analytics, notifications/reminders, and archival. Remove the mypy override in `pyproject.toml:201-219` once the modules are type-clean. **This is the project's single largest quality debt.**
2. **Remove silently swallowed exceptions from observability paths**: at minimum, `audit.py:59` (the audit logger must not fail silently; at least log to stderr), `cockpit.py:381/453/462` (health surface), `subagents/_approval_queue_hybrid_store.py:1318`, and `subagents/_review.py:167`. Replace `except Exception: pass` with logged and classified handling, per ADR-0014.

### P1 (High)
3. **Move domain reasoning out of the harness**: relocate `coordinator.py` (`_classify_task_with_llm`, `_generate_workflow_plan`), `agent_factory.py` (`_generate_evolution_prompt`, `_llm_evolve_prompt`), `workflow_engine.py` (`_generate_self_correction_prompt`), `issue_intake.py`, and `intent.py` to skills or a `teaagent.domain/` subpackage. Keep only the orchestration/governance shell in the harness, per `AGENTS.md:5`.
4. **Reduce `Any` in the worst offenders**: target `_approval_queue_hybrid_store.py` (71), `external_backends.py` (44), `context_pack.py` (30), `run_evidence.py` (28), `hooks.py` (28), and `acp_adapter.py` (26). Introduce typed `Protocol` classes for backend/hook/adapter boundaries.
5. **Unify the second framework with the primary runner**: either (a) fold `SubagentManager.run_subagent` into `runner/` to create one execution path, or (b) write an ADR that explicitly justifies the dual-framework architecture and the shared invariants across both (budget/audit/approval correctness). ADR-0022 covers the approval queue but no ADR reconciles the two execution loops.
6. **Complete the `approval/` migration**: ADR-0011 is "Implemented," but `approval_manager.py:1-1378`, `approval_backend.py`, `approval_selectors.py`, and `approval_ui.py` remain at the root. Move them into `teaagent/approval/` and update aliases in `_compat_modules.py`.
7. **Add line coverage to high-risk omitted surfaces**: move `tls_server.py` (High risk per ledger), `vote_relay.py`, and `cli/_handlers/_control_plane.py` (Medium risk, long-lived server) out of the omit list. Convert the ledger's smoke-test candidates into covered tests.

### P2 (Medium/Low)
8. **Consolidate optional-extra aliases**: fold `crypto`/`oauth`/`audit-encryption` into one `crypto` extra, or keep `oauth`/`audit-encryption` as documented aliases backed by a consolidated dependency set. Nineteen extras are excessive for alpha 0.1.0; remove unused ones after an import-graph audit.
9. **Split CLI handler god modules**: decompose `cli/_handlers/_ergonomics.py:1-1407`, `_doctor.py:1-1022`, `_agent/run.py:1-999`, and `chat_repl.py:1-894` into output formatting, business logic, and argument plumbing; route business logic through `cli/execution.py` (ADR-0026).
10. **Expand property-based testing**: only one file uses `hypothesis`. Add Hypothesis strategies for permission-mode transitions, budget enforcement, approval-hash exactness, and audit-chain invariants; these are high-value safety-critical surfaces.
11. **Populate `tests/skills/` or remove the empty directory** so it does not imply skill tests exist there.
12. **Reconcile `tests/e2e/` (one file) with 127 acceptance tests**: either move e2e tests into acceptance or define a clearer e2e contract.
