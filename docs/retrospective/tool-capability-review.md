# Tool-Capability Self-Review System

> Phase B design document | Purpose: subject TeaAgent's capabilities as a tool to continuous review. This reviews not only programs written with TeaAgent, but also TeaAgent itself.
> Design principle: **the harness is both governor and governed**; there are no self-exemptions.

## 1. Why Tool-Capability Self-Review Is Needed

Several gaps exposed in Phase A show that the tool's capabilities are not governed by the tool itself:

- `AutoModeManager` silently escalates to `DANGER_FULL_ACCESS` ([01](01-security-risk.md) G1) - the harness's approval pipeline is bypassed by its own auto-mode, and no self-test detects it.
- The audit-event schema is incomplete ([02](02-tool-governance.md) G-1) - the harness's own schema validator does not validate its published external contract.
- The library-caller path at `chat_agent.py:755` has no durable audit ([01](01-security-risk.md) G4) - the rule that every tool call enters the audit trail does not apply to the harness's own library entry point.
- A 4,884-line god module exists ([03](03-architecture-quality.md) G-CRIT-1) - the harness's thin-harness rule does not apply to its own subagents package.
- Bandit is non-blocking in `ci.yml` ([01](01-security-risk.md) G11) - the harness's fail-closed principle is not enforced in its own CI.

**Core problem**: TeaAgent claims external governance while retaining dark corners of internal self-exemption. This design makes the harness subject to its own governance.

## 2. Design Principles

1. **No self-exemption**: rules that the harness applies to user code must also apply to the harness code itself.
2. **Prove, do not merely claim**: every governance claim must have an executable self-test, not just a statement in documentation.
3. **Record self-review in the audit chain**: write self-test results to the audit chain so skipping self-review is itself auditable.
4. **Do not rebuild self-test**: extend the existing `teaagent selftest` in `selftest.py` rather than creating a new system.
5. **Layered review**: static code-structure checks, dynamic runtime invariants, external-contract checks, and skill/dependency supply-chain checks.
6. **Downgrade path**: solo mode may downgrade failures to warnings; team mode upgrades them to blocking failures.

## 3. Four Layers of Self-Review

### Layer 1 - Static (Code-Structure Invariants)

Review whether the harness's own code structure complies with `AGENTS.md`.

| Review item | Related AGENTS.md rule | Implementation | Existing? |
| --- | --- | --- | --- |
| Root module count <= 184 | ADR-0030 thin harness | `scripts/check_root_module_count.py` | Yes |
| Complexity <= 99 CI baseline/gate | Quality | `scripts/check_complexity.py --max 99` | Yes |
| No circular dependencies | Quality | `scripts/check_circular_imports.py` | Yes |
| No god modules (single file > X lines) | Thin harness | **Add `check_god_modules.py`** with an 800-line threshold; the current 4,884-line `_approval_queue_hybrid_store.py` triggers it | No |
| Consistent event-spine wiring | ADR-0032 | `scripts/validate_event_spine_wiring.py` | Yes |
| Complete public docstrings | Quality | `scripts/check_public_docstrings.py` | Yes |
| Config access <= 65 | Quality | `scripts/check_config_access.py` | Yes |
| Agent contribution contract | Quality | `scripts/agent_contribution_contract.py` | Yes |
| Monitor `Any` usage | Type quality | **Add `check_any_usage.py`** with a baseline of 2,199 and incremental blocking | No |
| Monitor `# type: ignore` | Type quality | **Add `check_type_ignore.py`** with a baseline of 22 and incremental blocking | No |
| Monitor silent `except: pass` | Observability | **Add `check_silent_exception.py`** to prohibit it in audit/observability paths | No |

**Example `check_god_modules.py`**:

```python
GOD_MODULE_THRESHOLD = 800  # lines
EXEMPT = {"runner/_core.py", "tui/core.py"}  # Explicit exemptions require an ADR.
for py in pathlib.Path("teaagent").rglob("*.py"):
    relative = py.relative_to("teaagent").as_posix()
    lines = sum(1 for _ in py.open())
    if lines > GOD_MODULE_THRESHOLD and relative not in EXEMPT:
        fail(f"{py}: {lines} > {GOD_MODULE_THRESHOLD}; split or add ADR exemption")
```

### Layer 2 - Dynamic (Runtime Invariants)

Review whether the harness's runtime governance claims actually hold.

| Review item | Related claim | Implementation | Existing? |
| --- | --- | --- | --- |
| AutoMode does not escalate silently | Destructive tools require exact-call tokens | **Add `test_automode_no_silent_escalation.py`**: construct `AutoModeManager` + an auto-allowed destructive tool; verify that each call emits `tool_call_approved` with `authority_type='auto_mode'` and never silently grants `DANGER_FULL_ACCESS` | No; add after fixing S-P0-1 |
| Approval-queue HMAC is mandatory by default | Approval integrity | **Add `test_approval_queue_hmac_required.py`**: construct a store without `TEAAGENT_APPROVAL_HMAC_KEY`; verify that it generates and persists a key and rejects forged records | No; add after fixing S-P0-2 |
| Library callers use durable audit | Every tool call enters the audit trail | **Add `test_chat_agent_library_audit.py`**: call `run_chat_agent(...)` without passing `audit`; verify that `.teaagent/audit/` receives JSONL containing `tool_call_started/completed` | No; add after fixing S-P0-3 |
| Audit-chain integrity | Audit chain is tamper-evident | `tests/test_audit_chain.py` | Yes |
| Approval-token exactness | Destructive tools require exact-call tokens | `tests/test_approval_token_exactness.py` | Yes |
| Budget enforcement | Iteration + tool-call limits | `tests/test_p0_harness.py` | Yes |
| Subagent permission clamping | Children do not inherit allow/danger permissions | `tests/test_subagent_isolation.py` | Yes |
| MCP trust at call time | MCP trust is dynamic | `tests/test_mcp_trust.py`, if present | Partial |
| Skill-review gate | Skill supply-chain review | `tests/test_skill_review.py`, if present | Partial |
| Schema validator covers declared constraints | Complete tool schemas | **Add `test_schema_validator_completeness.py`**: verify validation of `enum`, `pattern`, `additionalProperties`, and `oneOf` after fixing G-P1-1 | No |
| Audit-schema conformance | External contract | **Add `test_audit_schema_conformance.py`**: validate every event written by `AuditLogger` against `docs/audit-event.schema.json` after fixing G-P0-1 | No |

### Layer 3 - Contract (External-Contract Consistency)

Review whether the harness's published contracts, including schemas, documentation, error references, and CLI interfaces, match the implementation.

| Review item | Related gap | Implementation | Existing? |
| --- | --- | --- | --- |
| Complete audit-event schema | 02 G-1 | `audit-schema-conformance` CI job; see Layer 2 in [automation-plan.md](automation-plan.md) | No |
| Error reference matches `errors.py` | 04 G-H5 | `check-error-reference-sync.py` | No |
| Documentation commands are executable | 04 G-H1 | `check-docs-command-executability.py` | No |
| Documentation flags exist | 04 G-H2 | `check-docs-drift.py`, extending `validate_docs_consistency.py` | No |
| CLI exit-code documentation is consistent | 04 G-H5 | `check-error-reference-sync.py` | No |
| GitHub URLs are consistent | 04 G-C1 | **Add `check_github_url_consistency.py`** to require one canonical GitHub URL throughout the repository | No |
| TUI `HELP_TEXT` matches the implementation | 04 G-C2 | **Add `check_tui_help_consistency.py`** to compare parsed `HELP_TEXT` from `rendering.py` with handlers in `_commands.py` | No |
| Permission playbook matches permission modes | Documentation | Extend `validate_docs_consistency.py` | Partial |
| AGENTS.md rules are satisfied | 05 | `teaagent selftest --check-agents-md`; see Layer 4 | No |

### Layer 4 - Supply Chain (Skills and Dependencies)

Review the harness's own skill assets and dependencies.

| Review item | Related gap | Implementation | Existing? |
| --- | --- | --- | --- |
| Git-tracked `.opencode/skill/` SKILL.md <= 80 lines | AGENTS.md Skills | `check-skill-md-length.py` (installed=error, development=warning) | No |
| Git-tracked `teaagent/skills/` SKILL.md <= 80 lines and routes detail to references/examples | AGENTS.md Skills | Same as above | No |
| Skill-lifecycle audit events | AGENTS.md 25 | `skill-supply-chain-monthly.yml` cron; see Layer 4 in [automation-plan.md](automation-plan.md) | No |
| Dependency security | 01 | `pip-audit` + Dependabot | Yes |
| Dependency pinning | 01 | `selftest.py:17-45` for CVE pinning | Yes |
| Rational dependency extras matrix | 03 G-MED-5 | **Add `check_extras_usage.py`** to verify that dependencies in each extra are actually imported and warn on unused extras | No |
| Plugin governance | AGENTS.md 11 | `integration/plugin_governance.py` already governs plugins | Yes |

## 4. Design for `teaagent selftest --check-agents-md`

Extend `teaagent/selftest.py` with a `--check-agents-md` mode that validates all 12 `AGENTS.md` rules.

```
$ teaagent selftest --check-agents-md
AGENTS.md Compliance Self-Test
================================
[Architecture]
  WARN  harness thin: root count passes, but a 4,884-line god module remains (A-P0-1)
  PASS  protocol assets: MCP/Skills/Run records present
  PASS  no second framework without ADR: ADRs 0019/0022/0028/0029 found
[Tool Governance]
  PASS  tools registered through ToolRegistry: all registrations via ToolRegistry
  PASS  each tool has 5 fields: 50+ tools verified
  FAIL  destructive tools need exact-call token: AutoModeManager bypasses (S-P0-1)
  PASS  tool errors actionable and classified: ErrorCategory + DenialReasonCode + hint
[Runtime Safety]
  PASS  iteration + tool-call limit: RunBudget enforced
  WARN  every tool call recorded in audit: chat_agent.py:755 library path (S-P0-3)
  PASS  long-lived state externalized: RunStore/Checkpoint/Audit JSONL
[Skills]
  PASS  tracked SKILL.md files are short and route detail to references/examples
  PASS  skills as reviewed supply-chain assets: skill_review + skill_lifecycle
================================
Summary: 9 PASS / 2 WARN / 1 FAIL
Action: fix S-P0-1, S-P0-3, and A-P0-1 to reach 12 PASS
```

**Implementation**: add `run_agents_md_compliance()` to `selftest.py`. It returns a `SelftestResult` containing `pass`/`warn`/`fail` for each rule plus the corresponding action ID. The result can enter the audit chain as a `selftest_completed` event.

## 5. Record Self-Review in the Audit Chain

Self-review itself must be auditable; otherwise, there is no way to detect that it was skipped.

- **Event type**: `selftest_completed`, addable to the `RunEventType` mapping in `runner/_events.py`
- **Payload**: `{check_name, result, action_ids, timestamp, selftest_version}`
- **Critical behavior**: in compliance mode, a FAIL in `selftest_completed` must propagate as `AuditDurabilityError`, following `audit.py:504-508`
- **Health check**: extend `audit_health.py` with `selftest_health` to check whether a `selftest_completed` event occurred in the past 24 hours and whether any FAIL was addressed

## 6. Integration with Existing Governance Assets

| Self-review need | Reused existing asset |
| --- | --- |
| Static structure review | `scripts/check_*` suite + `teaagent selftest` |
| Dynamic invariants | `tests/` + pytest markers + `hypothesis`, pending extension |
| Contract consistency | `validate_docs_consistency.py` + `check-public-docstrings.py` |
| Supply chain | `skill_review.py` + `skill_lifecycle.py` + `pip-audit` + `selftest.py:17-45` |
| Audit | `AuditLogger` in `audit.py` + `audit_chain.py` + `audit_health.py` |
| RBAC for Size C | `governance/rbac.py` + `governance/policy_engine.py` |
| Self-test entry point | `teaagent selftest` CLI + `selftest.py` |
| Doctor health check | `teaagent doctor` + `cli/_handlers/_doctor.py` |

## 7. Trigger Cadence

| Review layer | Trigger | Frequency |
| --- | --- | --- |
| Layer 1 Static | Pre-commit + CI | Every commit / every push |
| Layer 2 Dynamic | CI smoke + nightly | Every push / nightly |
| Layer 3 Contract | CI + pre-commit | Every push / every commit |
| Layer 4 Supply Chain | CI + monthly cron | Every push / monthly |
| `--check-agents-md` | CI `agent-md-compliance` job + quarterly review | Every push / quarterly |
| Record `selftest_completed` in audit | Self-test execution | Every execution |
| `audit_health` includes self-test health | Daily cron | Daily |

## 8. Failure Handling

| Failure type | Size A | Size B | Size C |
| --- | --- | --- | --- |
| Layer 1 Static failure | Warning | Blocking | Blocking |
| Layer 2 Dynamic failure | Warning | Blocking | Blocking |
| Layer 3 Contract failure | Warning | Blocking | Blocking |
| Layer 4 Supply Chain failure (installed) | Blocking | Blocking | Blocking |
| Layer 4 Supply Chain failure (development) | Warning | Warning | Warning |
| `--check-agents-md` WARN | Warning + action ID | Warning + action ID | Warning + action ID |
| `--check-agents-md` FAIL | Warning, downgrade allowed for solo mode | Blocking | Blocking + Security Officer notification |
| No `selftest_completed` in 24 hours | Warning | Warning + Auditor notification | Blocking + Auditor investigation |

## 9. Phased Rollout

### Phase 0 (1 Week)
- Extend `teaagent selftest` with `--check-agents-md` mode for the 12 rules.
- Add the `selftest_completed` event type to `runner/_events.py`.

### Phase 1 (2 Weeks)
- Add static-review scripts: `check_god_modules.py`, `check_any_usage.py`, `check_type_ignore.py`, and `check_silent_exception.py`.
- Add contract-review scripts: `check_github_url_consistency.py` and `check_tui_help_consistency.py`.

### Phase 2 (2 Weeks, After Fixing S-P0-1/2/3)
- Add dynamic tests: `test_automode_no_silent_escalation.py`, `test_approval_queue_hmac_required.py`, `test_chat_agent_library_audit.py`, `test_schema_validator_completeness.py`, and `test_audit_schema_conformance.py`.

### Phase 3 (1 Month)
- Extend `audit_health.py` with `selftest_health`.
- Extend `teaagent doctor` with the `doctor selftest-history` subcommand.
- Add the supply-chain script `check_extras_usage.py`.

### Phase 4 (Quarterly Review)
- Aggregate self-review results in the quarterly review report; `generate_quarterly_retrospective.py` includes the self-test summary.

## 10. Out of Scope

- Do not change self-test results to always PASS, which would be self-deception. A FAIL must include a traceable action ID.
- Do not turn self-test into a check-box ritual. Every rule requires executable validation, not merely a documentation claim.
- Do not make self-review fully self-healing. Remediation requires a human decision, or a human-authorized auto-mode with a recorded payload digest.
- Do not make `--check-agents-md` the only defense. It is an aggregate view; each review layer must still run independently.
- Do not rebuild `skill_review.py`, `audit_health.py`, or `selftest.py`; extend them.

## 11. Mapping to the Phase A Action Register

| Self-review item | Related action ID |
| --- | --- |
| AutoMode does not escalate silently | S-P0-1 |
| Approval-queue HMAC is mandatory | S-P0-2 |
| Durable audit for library callers | S-P0-3 |
| Audit-schema conformance | G-P0-1 |
| Complete schema validator | G-P1-1 |
| Split god module | A-P0-1 |
| Remove silent exceptions | A-P0-2 |
| Consistent GitHub URL | U-P0-1 |
| Consistent TUI help | U-P0-2 |
| Consistent error reference | U-P0-1, including H5 |
| Executable documentation commands | U-P1-2 |

> This document, [review-system.md](review-system.md), and [automation-plan.md](automation-plan.md) form the Phase B document set. See [01](01-security-risk.md)-[06](06-action-register.md) for Phase A evidence.
