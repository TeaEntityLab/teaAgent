# Review Institution Specification

> Phase B design document | Purpose: turn the 45 actions identified in Phase A from a one-time checklist into a continuously governed work queue.
> Design principle: **Doing the right thing > doing things right** - establish the smallest viable institution, scale it by team size, and avoid overengineering.

## 1. Why a Review Institution Is Needed

The systemic gaps exposed in Phase A are not isolated bugs; they are governance fallbacks:

- Silent escalation by `AutoModeManager` ([01](01-security-risk.md) G1) - the governance claim and implementation have diverged, with no periodic validation.
- A 4,884-line god module ([03](03-architecture-quality.md) G-CRIT-1) - a freeze gate prevents further growth but does not reduce existing debt, and there is no regression detection.
- An incomplete audit-event schema ([02](02-tool-governance.md) G-1) - no owner periodically validates the external contract.
- A placeholder URL on the initial welcome screen ([04](04-ux-usability.md) G-C1) - no one owns this trust surface.

**The institution's purpose** is to assign an owner, cadence, gate, and artifact to each type of gap, turning "no one noticed" into "someone is accountable, and automation will catch it."

## 2. Design Principles

1. **Minimum viable institution**: make it work for a solo maintainer first; do not introduce roles that the team cannot staff merely for institutional completeness.
2. **Automation first**: do not spend human time on checks that CI, pre-commit, or hooks can perform.
3. **Risk-proportional gates**: apply strong gates to high-risk changes and a fast path to low-risk changes.
4. **Artifacts over memory**: persist review conclusions in documents or audit records rather than relying on human memory.
5. **Scale down and up**: solo mode can degrade to self-review; growing teams can upgrade to RBAC.
6. **Do not duplicate existing harness governance**: TeaAgent already has `ToolRegistry`, `ApprovalManager`, `AuditLogger`, and `SkillLifecycle`. The institution governs the governors; it does not rebuild them.

## 3. Role Mapping by Team Size

### Size A - Solo Maintainer

| Role | Filled by | Responsibilities |
| --- | --- | --- |
| Author | Maintainer | Write changes, self-assess, and open PRs |
| Reviewer | Maintainer (self-review with checklist) | Self-assess against the review checklist and complete a self-review report |
| Approver | Maintainer (assisted by the `reflective-risk` skill for high-risk changes) | Self-approve; run `reflective-risk` and produce a dry-run/rollback plan before any high-risk change |
| Auditor | Automation + weekly maintainer review | CI generates audit-chain health checks; the maintainer manually samples `teaagent audit tail` each week |

**Key constraint**: in solo mode, the **self-review checklist is a mandatory artifact**, not optional. It is the only source of credibility when the author also acts as reviewer. The checklist follows the machine-verifiable completeness-checklist pattern in `run_receipt.py:76-96`.

### Size B - Small Team (2-5 People)

| Role | Filled by | Responsibilities |
| --- | --- | --- |
| Author | Any member | Write changes, self-assess, and open PRs |
| Reviewer | Another member (not the Author) | Perform code review and validate the checklist |
| Approver | Reviewer for low-risk changes / lead maintainer for high-risk changes | Use two-person approval; high-risk changes require a second reviewer |
| Auditor | Weekly rotation | Run `audit_health`, sample `audit_tail`, and investigate CI anomalies |

**Key constraint**: Reviewer != Author (four-eyes principle). High-risk changes involving destructive tools, permission modes, the audit chain, or the sandbox require a **second reviewer**. Small teams may reuse TeaAgent's multi-signature quorum (`approval/manager.py`) as an SSH-signature ceremony for external reviewer sign-off.

### Size C - Formal RBAC

| Role | Permissions | Responsibilities |
| --- | --- | --- |
| Author | Write workspace, propose | Write changes, self-assess, and open PRs |
| Reviewer | Read + comment | Perform code review and complete the review report |
| Approver | Approve merge | Approve changes; high-risk changes require two Approvers |
| Security Officer | Read + edit security policy | Mandatory reviewer for permission-mode, destructive-tool, sandbox, and audit-chain changes |
| Auditor | Read audit + run audit tools | Perform independent audits, periodic chain health checks, and compliance-bundle exports |
| Release Officer | Tag + publish | Enforce the release gate and sign release evidence |

**Key constraint**: the Security Officer is **independent of the Approver**. Any PR that touches `approval_*`, `approval/`, `audit*`, `sandbox/`, `tool_permissions.py`, `policy.py`, `mcp_trust.py`, or the budget/approval sections of `runner/_core.py` requires Security Officer sign-off as a mandatory second review. The Auditor may not simultaneously be the Author or Approver, preserving separation of duties.

> TeaAgent already provides a multi-signature quorum through `governance/rbac.py`, `governance/policy_engine.py`, and `approval/manager.py`. Size C can reuse it directly without building another RBAC system.

## 4. Review Criteria

Criteria are grouped by change category, with a mandatory checklist for each category.

### 4.1 General Criteria (All PRs)

- [ ] `ruff check` + `ruff format --check` pass
- [ ] `mypy teaagent/` reports 0 issues
- [ ] `pytest -m smoke` passes
- [ ] Coverage is at least 75% (`--cov-fail-under=75`)
- [ ] `check_root_module_count.py` reports no more than 184
- [ ] `check_complexity.py` reports no more than 99
- [ ] `check-circular-imports` passes
- [ ] `validate_event_spine_wiring.py` passes (ADR-0032)
- [ ] `validate_docs_consistency.py` passes
- [ ] The PR description contains Why / What / How / Done sections
- [ ] The change references one ID from [06-action-register.md](06-action-register.md), or registers a new ID

### 4.2 High-Risk Change Criteria (Mandatory `reflective-risk` + Security Officer)

Trigger conditions (any one is sufficient):
- Modify `teaagent/approval_*.py`, `teaagent/approval/`, or `teaagent/policy.py`
- Modify `teaagent/audit*.py` or `teaagent/audit_chain.py`
- Modify `teaagent/sandbox/`, `teaagent/docker_sandbox.py`, or `teaagent/git_sandbox.py`
- Modify `teaagent/tool_permissions.py` or `teaagent/workspace_tools/_shell.py`
- Modify `teaagent/mcp_trust.py`, `teaagent/provenance_gate.py`, or `teaagent/prompt_gate.py`
- Modify the budget/approval/JIT sections of `teaagent/runner/_core.py`
- Modify `teaagent/budget.py`, `teaagent/budget_monitor.py`, or `teaagent/scope_budget.py`
- Add a destructive tool or change `ToolAnnotations.security_tier`
- Add a permission mode or change the `PermissionMode` enum
- Change the audit schema (`docs/audit-event.schema.json`)
- Change ADR status or add a second framework

Additional criteria:
- [ ] Run the `reflective-risk` skill and attach a dry-run + rollback plan
- [ ] Obtain Security Officer sign-off (Size C), or a second reviewer plus the `full_access_acknowledged` ceremony (Size B)
- [ ] Add or update the corresponding tests: permission-matrix, audit-chain invariants, and approval-token exactness
- [ ] For wire-format changes such as the `edit_at_hash` hash or audit-chain fields, add a migration test + backward-compatibility flag
- [ ] Update `SECURITY.md` and `docs/threat-model.md` where applicable

### 4.3 Skill Review Criteria (SKILL.md / REFERENCE.md / Skill Code)

- [ ] `SKILL.md` is no more than 80 lines (warning); `REFERENCE.md` is not required when it is no more than 40 lines
- [ ] `REFERENCE.md` exists when `SKILL.md` exceeds 40 lines
- [ ] `review_skill` passes: frontmatter contains `name`/`description`, no blocklisted pattern is present, and the AST contains no dangerous import
- [ ] The `skill_lifecycle_transition` audit event was recorded
- [ ] For candidate installs, `provenance.json` is complete and includes the `attested_personal` flag

### 4.4 Documentation Review Criteria

- [ ] The docs-consistency CI check passes
- [ ] There is no contradiction with the current truth; if a change affects behavior described in `daily-driver-current-status.md`, update that file too
- [ ] Commands in onboarding documentation are executable, checked manually or with `teaagent doctor docs-commands` if implemented
- [ ] The error reference is consistent with the `errors.py` enum
- [ ] No outdated dated document contradicts the current truth

## 5. Review Cadence

| Activity | Frequency | Trigger | Artifact |
| --- | --- | --- | --- |
| PR review | Every PR | Push | Self-review report / review comment |
| Smoke gate | Every push | CI | CI result |
| High-risk gate | Every high-risk PR | Trigger conditions in 4.2 | `reflective-risk` report + size-appropriate G4 approval evidence |
| Audit-chain health | Daily via CI cron + weekly manual sampling | Cron + weekly meeting | `audit_health` report |
| Coverage-omit ledger alignment | Every PR via CI + monthly review | `validate_docs_consistency.py` + monthly review | Ledger update |
| Action-register progress | Weekly | Weekly meeting | Status-column update in [06-action-register.md](06-action-register.md) |
| Large retrospective (such as this document set) | Quarterly | Calendar | `docs/retrospective/<YYYY-MM>/` |
| ADR review | Quarterly | Calendar | ADR status assessment, including unresolved Superseded entries |
| Coverage-omit recovery review | Quarterly | Calendar | Entries whose return milestone is due |
| Dependency security review | Weekly via Dependabot + monthly manual review | Dependabot PR + monthly review | Dependabot merge record + `pip-audit` report |
| Skill supply-chain review | Monthly | Calendar | Skill lifecycle report + candidate retirement |

## 6. Review Gates

A gate prevents a change from merging until its condition is satisfied.

| Gate | Condition | Size A | Size B | Size C |
| --- | --- | --- | --- | --- |
| G1 - CI green | Smoke + lint + mypy + coverage | Mandatory | Mandatory | Mandatory |
| G2 - Self-review checklist | Machine-verifiable completeness | Mandatory | Mandatory | Mandatory |
| G3 - Four-eyes review | Reviewer != Author | Self-review exemption | Mandatory | Mandatory |
| G4 - High-risk Security Officer | Trigger conditions in 4.2 | `reflective-risk` report | Second reviewer + SSH signature | Security Officer sign-off |
| G5 - Audit-chain integrity | If audit code changes, new chain-verification tests pass | Mandatory | Mandatory | Mandatory |
| G6 - Schema conformance | If audit events change, the schema is synchronized | Mandatory | Mandatory | Mandatory |
| G7 - Migration plan | Wire-format change | Mandatory | Mandatory | Mandatory |
| G8 - Signed ADR | Second framework / major architecture | Mandatory | Mandatory | Mandatory |
| G9 - Action register linked | PR references an action ID | Mandatory | Mandatory | Mandatory |
| G10 - Release Officer | Release PR | N/A | Lead maintainer | Release Officer |

## 7. Audit and Evidence

The review institution itself must be auditable; otherwise, "governing the governors" is an empty claim.

- **Record review events in the audit chain**: every PR merge emits a `review_completed` event with `reviewer`, `approver`, `action_id`, `risk_class`, and `checklist_hash`.
- **Persist the self-review report**: store it in `.teaagent/reviews/<pr-id>.json` with checklist completeness + the change digest.
- **Persist high-risk `reflective-risk` reports**: store them in `docs/reviews/<pr-id>-risk.md` with dry-run results + a rollback plan.
- **Aggregate quarterly retrospectives**: `docs/retrospective/<YYYY-MM>/` contains the quarter's action-register progress, newly discovered gaps, and ADR status changes.
- **Publish monthly Auditor reports**: `docs/audits/<YYYY-MM>.md` contains audit-chain health, coverage-omit recovery progress, dependency security incidents, and skill supply-chain status.

## 8. Integration with Existing TeaAgent Governance

This institution **composes** existing governance assets rather than rebuilding them:

| Institutional need | Reused TeaAgent asset |
| --- | --- |
| Reviewer != Author | Multi-signature quorum in `approval_manager.py` (SSH signatures) |
| Approval for destructive changes | Reuse the `JITApprovalState.approved_call_ids` pattern as a PR approval token |
| Audit chain | `audit.py` `AuditLogger` + verification in `audit_chain.py`; add the `review_completed` event type |
| RBAC | `governance/rbac.py` + `governance/policy_engine.py` |
| Skill review | `skill_review.py` + `skill_lifecycle.py` |
| Schema conformance | `teaagent/schema.py` (must be extended first; see [02](02-tool-governance.md) G-3) |
| Coverage-omit governance | `docs/governance/coverage-omit-ledger.md` + `validate_docs_consistency.py` |
| Health checks | `teaagent selftest` + `audit_health.py` |
| Doctor command | `teaagent doctor` subcommand, extendable with `doctor review-institution` |

## 9. Downgrade and Upgrade Paths

- **Downgrade Size C -> B**: combine the Security Officer and Approver roles while preserving four-eyes review; rotate the Auditor role.
- **Downgrade Size B -> A**: set Reviewer = Author; elevate the self-review checklist to the only source of credibility; require `reflective-risk` for high-risk changes.
- **Upgrade A -> B**: when a second contributor joins, immediately make four-eyes review a PR gate; retain self-review as a supplement.
- **Upgrade B -> C**: when the team reaches at least six people or faces external compliance requirements, separate Security Officer from Auditor and enable the RBAC `policy_engine`.

## 10. Explicit Boundaries

- Do not introduce a second PR system; use the existing GitHub PR / local patch workflow.
- Do not require four-eyes review in solo mode, which would encourage bypassing the institution.
- Do not turn the criteria into a check-every-box ritual. High-risk criteria require a `reflective-risk` report; low-risk changes use the fast path.
- Do not merge automatically. The Approver is always a human, or an auto-mode explicitly authorized by a human with a recorded payload digest.
- Do not duplicate existing TeaAgent governance assets; compose them.

## 11. Minimum First Iteration

1. Commit this document and [06-action-register.md](06-action-register.md) to the repository.
2. Add a Review Institution section to `CONTRIBUTING.md` that links to this document.
3. Extend `.github/pull_request_template.md` with an action-ID field, risk-class self-assessment field, and self-review checklist link.
4. Add a pre-commit hook, `check-action-register-link.py`, that verifies the PR description contains an action ID or a newly registered action.
5. Add a `review-institution-gate` CI job that runs the self-review checklist conformance check.
6. Add a `doctor review-institution` subcommand to `teaagent doctor` that reports the current mode (A/B/C), pending actions, and audit-chain health.
7. Evaluate whether to upgrade the team size at the first quarterly review.

> See [automation-plan.md](automation-plan.md) for automation details and [tool-capability-review.md](tool-capability-review.md) for the tool-capability self-review.
