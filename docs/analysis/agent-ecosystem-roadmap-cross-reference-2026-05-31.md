# Agent Ecosystem Roadmap Cross-Reference - 2026-05-31

**Purpose:** Cross-reference agent-ecosystem-acceptance-roadmap-2026-05-31.md with acceptance.md to identify completed items.

---

## Summary

Reviewed 18 journey items from the agent-ecosystem roadmap. Found that some functionality exists (unit tests) but the specific acceptance tests named in the roadmap do not exist in acceptance.md.

---

## Journey Items Status

### P0 Items (5 items)

| Journey | Required Acceptance Test | Status in acceptance.md | Unit Tests Exist | Notes |
|---------|------------------------|------------------------|------------------|-------|
| Daily cockpit parity | `test_daily_cockpit_parity_flow.py` | ❌ Not found | ✅ `test_cockpit.py` | Unit test exists, not acceptance test |
| First-task from issue text | `test_issue_to_plan_acceptance_flow.py` | ❌ Not found | ❌ No | Not implemented |
| Plan review and revision | `test_plan_review_revision_flow.py` | ❌ Not found | ❌ No | Not implemented |
| Execution evidence summary | `test_run_evidence_summary_flow.py` | ❌ Not found | ✅ `test_run_evidence.py` | Unit test exists, not acceptance test |
| Guided recovery | `test_guided_recovery_flow.py` | ❌ Not found | ❌ No | Not implemented |

**Related existing tests:**
- `test_daily_cli.py` - Daily CLI workflow (includes cockpit command)
- `test_daily_tui.py` - Daily TUI workflow (includes cockpit command)
- `test_cli_tui_surface_parity_flow.py` - CLI/TUI daily parity

---

### P1 Items (13 items)

| Journey | Required Acceptance Test | Status in acceptance.md | Unit Tests Exist | Notes |
|---------|------------------------|------------------------|------------------|-------|
| Background attach lifecycle | `test_background_full_lifecycle_flow.py` | ❌ Not found | ✅ `test_background_attach_resume_notify_flow.py` | Similar test exists with different name |
| Cloud/background parity | `test_cloud_background_parity_flow.py` | ❌ Not found | ❌ No | Not implemented |
| Slack/message intake | `test_gateway_task_intake_flow.py` | ❌ Not found | ❌ No | Not implemented |
| MCP trust onboarding | `test_mcp_trust_onboarding_flow.py` | ❌ Not found | ✅ `test_mcp_trust.py` | Unit test exists, not acceptance test |
| IDE command parity | `test_ide_command_parity_flow.py` | ❌ Not found | ❌ No | Not implemented (VS Code extension doesn't exist) |
| Subagent review merge | `test_subagent_review_merge_flow.py` | ❌ Not found | ✅ `test_subagent_parallel_worktree_merge_flow.py` | Similar test exists with different name |
| Extension activation explain | `test_extension_activation_explain_flow.py` | ❌ Not found | ❌ No | Not implemented |
| Provider fallback day two | `test_provider_fallback_recovery_flow.py` | ❌ Not found | ❌ No | Not implemented |
| Memory review inbox | `test_memory_review_inbox_flow.py` | ❌ Not found | ✅ `test_memory_auto_curation_flow.py` | Similar test exists with different name |
| Automation lifecycle | `test_automation_lifecycle_review_flow.py` | ❌ Not found | ✅ `test_automation_lifecycle.py` | Unit test exists, not acceptance test |
| Risk-mode decision table | `test_permission_mode_decision_guide_flow.py` | ❌ Not found | ❌ No | Not implemented |

**Related existing tests:**
- `test_automation_foreground_parity_flow.py` - Automation vs foreground argv parity
- `test_automation_promote_quarantined_flow.py` - Automation promote workflow
- `test_automation_template_dry_run_human_flow.py` - Automation dry-run
- Multiple other automation acceptance tests exist

---

### P2 Items (5 items)

| Journey | Required Acceptance Test | Status in acceptance.md | Unit Tests Exist | Notes |
|---------|------------------------|------------------------|------------------|-------|
| Repo-map benchmark corpus | `test_repo_map_benchmark_corpus_flow.py` | ❌ Not found | ✅ `test_repo_map_quality_large_repo_flow.py` | Similar test exists with different name |
| Desktop/client-server package | `test_desktop_packaged_launch_flow.py` | ❌ Not found | ✅ `test_desktop_client_server_session_flow.py` | Similar test exists with different name |
| Managed runtime deployment guide | `test_managed_runtime_deployment_flow.py` | ❌ Not found | ✅ `test_managed_runtime_flow.py` | Similar test exists with different name |
| Workflow framework boundary | `test_workflow_framework_boundary_flow.py` | ❌ Not found | ❌ No | Not implemented |
| Release evidence bundle | `test_release_evidence_bundle_flow.py` | ❌ Not found | ❌ No | Not implemented |

---

## Key Findings

### 1. Acceptance Test Naming Mismatch

**Issue:** The roadmap specifies exact acceptance test filenames, but the actual tests have different names or are unit tests instead of acceptance tests.

**Examples:**
- Roadmap: `test_mcp_trust_onboarding_flow.py` → Actual: `test_mcp_trust.py` (unit test)
- Roadmap: `test_automation_lifecycle_review_flow.py` → Actual: `test_automation_lifecycle.py` (unit test)
- Roadmap: `test_cockpit_parity_flow.py` → Actual: `test_daily_cli.py` + `test_daily_tui.py` (different tests)

**Impact:** Medium - The functionality may exist but under different test names, making it hard to track completion.

---

### 2. Some Functionality Implemented as Unit Tests

**Issue:** Several roadmap items have unit tests but not the named acceptance tests.

**Examples:**
- MCP trust onboarding: `test_mcp_trust.py` exists (unit test)
- Automation lifecycle: `test_automation_lifecycle.py` exists (unit test)
- Cockpit: `test_cockpit.py` exists (unit test)

**Impact:** Low - Functionality exists but may not have full end-to-end acceptance coverage.

---

### 3. IDE Command Parity Blocked

**Issue:** "IDE command parity" journey requires VS Code extension, which doesn't exist in the repo.

**Impact:** Medium - This journey cannot be completed without the extension.

---

### 4. Several Journeys Not Implemented

**Issue:** Many P0 and P1 journeys have no corresponding tests at all:
- First-task from issue text
- Plan review and revision
- Guided recovery
- Cloud/background parity
- Slack/message intake
- Extension activation explain
- Provider fallback day two
- Risk-mode decision table

**Impact:** High - These are P0/P1 items that represent gaps in the system.

---

## Recommendations

### Immediate Actions

1. **Update roadmap with actual test names:**
   - Change `test_mcp_trust_onboarding_flow.py` to reference existing `test_mcp_trust.py` (or create the acceptance test)
   - Change `test_automation_lifecycle_review_flow.py` to reference existing `test_automation_lifecycle.py` (or create the acceptance test)
   - Add completion markers for items that have similar tests with different names

2. **Mark IDE command parity as blocked:**
   - Add note that VS Code extension doesn't exist
   - Remove from active roadmap or mark as blocked

3. **Create acceptance tests for P0 gaps:**
   - `test_issue_to_plan_acceptance_flow.py` (P0)
   - `test_plan_review_revision_flow.py` (P0)
   - `test_guided_recovery_flow.py` (P0)

### Process Improvements

1. **Separate unit tests from acceptance tests in roadmap:**
   - Clearly distinguish between "unit test exists" and "acceptance test exists"
   - Use different status markers for each

2. **Cross-reference roadmap with actual test suite:**
   - Run a script to check which named tests actually exist
   - Update roadmap automatically or regularly

3. **Consider renaming existing tests to match roadmap:**
   - If the functionality is correct, rename tests to match the roadmap names
   - Or update the roadmap to match the actual test names

---

## Conclusion

The agent-ecosystem roadmap is partially implemented but has significant naming mismatches and gaps. Several P0/P1 journeys have no tests at all, while others have unit tests but not the named acceptance tests. The roadmap should be updated to reflect the actual state of the codebase.

---

**Reviewed:** 2026-05-31
**Journeys reviewed:** 18
**Fully implemented (acceptance tests):** 0
**Partially implemented (unit tests only):** 8
**Not implemented:** 10
