# TeaAgent Comprehensive Retrospective

> Produced: 2026-06-20 | Scope: project code and tool capabilities | Basis: `AGENTS.md` rules, cx semantic navigation, and four parallel audit dimensions
> Priority order (as requested): **Security and risk > tools and governance > architecture and quality > UX and usability**

## Why This Retrospective Exists

- **Project scale**: 177 root modules, 542 Python files containing 6,103 test-function definitions, 32 ADRs, and 601 Markdown files under `docs/` exceed what a person can reliably hold in working memory. The project needs an evidence-based retrospective that can be cited and audited.
- **Tool capability**: TeaAgent positions itself as a governance-first agent harness. Its governance claims, including `ToolRegistry`, destructive-tool approvals, budget limits, the audit chain, and the skill supply chain, require independent verification; otherwise, "governance" becomes a marketing term.
- **Review system and automation**: A retrospective is a point-in-time snapshot. A review system plus automation can turn quality from an event-driven concern into continuous governance. Phase B provides that design.

## Contents

### Phase A - Retrospective Evidence (Complete)

| File | Dimension | Key Judgment |
| --- | --- | --- |
| [01-security-risk.md](01-security-risk.md) | Security and risk (highest priority) | The layered fail-closed approval pipeline is strong, but `AutoModeManager` silently escalating to `DANGER_FULL_ACCESS` is a P0 risk. |
| [02-tool-governance.md](02-tool-governance.md) | Tool capability and governance | `ToolRegistry`, the tracked skill supply chain, and the audit chain are mature; the published audit-event schema is incomplete. |
| [03-architecture-quality.md](03-architecture-quality.md) | Architecture and code quality | Type and quality gates are strong; the 4,884-line `_approval_queue_hybrid_store.py` god module is the largest single source of debt. |
| [04-ux-usability.md](04-ux-usability.md) | UX and usability | The actionable error model is strong; the placeholder welcome-page URL and advertised but unimplemented TUI commands create a trust problem. |
| [05-compliance-matrix.md](05-compliance-matrix.md) | `AGENTS.md` compliance matrix | 9 of 12 rules are compliant, 2 are partial, and the exact-call approval rule is violated by auto-mode escalation. |
| [06-action-register.md](06-action-register.md) | Prioritized action register | Eight P0, seventeen P1, and twenty P2 actions are traceable to concrete `file:line` evidence. |

### Phase B - Review System and Automation Design (Complete)

| File | Contents |
| --- | --- |
| [review-system.md](review-system.md) | Review-system specification: criteria, cadence, gates, and roles for three team sizes. |
| [automation-plan.md](automation-plan.md) | Six automation layers (editing, pre-commit, CI, high risk, nightly, and quarterly review), extensions to seven existing workflows, and eleven new scripts. |
| [tool-capability-review.md](tool-capability-review.md) | Four-layer tool-capability self-review (static, dynamic, contract, and supply chain) plus `teaagent selftest --check-agents-md`. |

## Executive Summary

### Overall Judgment

TeaAgent demonstrates **unusually strong governance intent for an agent harness**. Its layered approval pipeline, HMAC audit chain, skill supply-chain review, triple budget checks, and subagent permission clamping are uncommon among comparable CLI agents. However, four systemic gaps remain between the governance claims and their implementation:

1. **Silent escalation paths bypass approval governance** (P0): `AutoModeManager` changes the permission mode for allowlisted tools directly to `DANGER_FULL_ACCESS`, bypassing exact-call and JIT approval. The runner still records tool execution, but it does not record a distinct approval-authority event for the auto-mode escalation. Approval-queue HMAC is disabled by default. Governance only works when authority changes are explicit and auditable.
2. **A god module overwhelms the governance boundary** (P0): the single 4,771-line class at `subagents/_approval_queue_hybrid_store.py:113-4884` contains voting, comments, SLA logic, templates, compliance rules, notifications, and analytics. This embeds an approval product inside the harness and violates the `AGENTS.md` requirement to keep the harness thin. Mypy disables eleven error codes for the module, effectively exempting it from type governance.
3. **Public contracts diverge from the implementation** (P1): `docs/audit-event.schema.json` omits `prev_hash`, `hash`, and `chain_hmac`, so external compliance consumers that validate against the schema will reject every chained event. The exit-code table in `docs/error-reference.md` is incorrect, and onboarding documentation references commands that do not exist.
4. **Trust breaks at first contact** (P0): the initial welcome page prints the placeholder URL `https://github.com/yourusername/teaagent`. The TUI advertises `parallel`, `select`, and `cancel` as branch operations, but their handlers only store, select, or clear option strings. `conflict` and `o/t/n/p/a` explicitly return "not yet implemented." Users encounter these semantic failures during their first interaction.

### Quantitative Evidence

| Metric | Value | Source |
| --- | --- | --- |
| Root modules | 177 (limit: 184 under the ADR-0030 freeze) | `scripts/check_root_module_count.py` |
| Test-function definitions | 6,103 across 542 Python files | `rg -n '^\s*(async\s+)?def test_' tests -g '*.py'` |
| Mypy result | 0 issues across 464 files | Executed `mypy teaagent/` |
| `# type: ignore` uses | 22 (low) | `rg "# type: ignore" teaagent/` |
| Lines containing `Any` | 2,199 (high) | `rg -n "\bAny\b" teaagent -g '*.py'` |
| Cyclomatic-complexity violations | 99; CI limit 99 (the script default target is 50) | `scripts/check_complexity.py --max 99` |
| Coverage gate | 75% fail-under | `.github/workflows/ci.yml:141` |
| ADR count | 32 | `docs/adr/README.md` |
| Coverage-omitted modules | 16, including one high-risk module (`tls_server.py`) | `pyproject.toml:250-269` and the ledger |
| Largest file | `subagents/_approval_queue_hybrid_store.py`, 4,884 lines | `wc -l` |

### P0 Actions (8; see [06-action-register.md](06-action-register.md))

1. **Prevent `AutoModeManager` from unconditionally escalating to `DANGER_FULL_ACCESS`** - use payload-digest preapproval plus an audit event ([01](01-security-risk.md), G1).
2. **Require approval-queue HMAC by default** - generate a 32-byte key or refuse to load ([01](01-security-risk.md), G3).
3. **Use a path-backed `AuditLogger` for the `chat_agent.py:755` library caller** - prevent unaudited execution ([01](01-security-risk.md), G4).
4. **Decompose the 4,884-line god module** - separate storage backends, voting, SLA logic, templates, compliance, notifications, and analytics ([03](03-architecture-quality.md), G-CRIT-1).
5. **Remove silent `except: pass` handling from audit and observability paths** - at minimum, fix `audit.py:59` and `cockpit.py:381/453/462` ([03](03-architecture-quality.md), G-HIGH-4).
6. **Fix the placeholder welcome-page URL and standardize all four GitHub URLs** ([04](04-ux-usability.md), G-C1).
7. **Implement advertised TUI commands or remove them from Help and the status panel** ([04](04-ux-usability.md), G-C2).
8. **Make the published audit-event schema match persisted chained events** - add `prev_hash`, `hash`, and `chain_hmac`, or separate logical-event and persisted-entry schemas ([02](02-tool-governance.md), G-1).

### Methodology

- **Navigation**: cx semantic navigation (`overview`, `symbols`, `definition`, and `references`) supplemented by file reads and searches. Four explore subagents collected evidence in parallel, and key judgments cite concrete file and line evidence.
- **Compliance review**: all 12 rules across the four `AGENTS.md` sections were assessed as compliant, partial, or violated, with supporting evidence.
- **Risk ratings**: Critical/High/Medium/Low by likelihood and impact, with concrete attack or failure scenarios.
- **Evidence discipline**: verification that was not executed is not described as verified; missing evidence is marked "not found" rather than guessed.

### Human Review Gate

Phase A is an evidence-based retrospective and does not modify program code. **Phase B defines a review system and automation based on the Phase A findings, but it still requires human review before implementation.** Review these decisions:

- Should the P0 actions enter the next sprint immediately?
- Do the Phase B roles (Reviewer, Approver, and Auditor) match the people available?
- Should the proposed CI gates be added on top of the seven existing workflows?
