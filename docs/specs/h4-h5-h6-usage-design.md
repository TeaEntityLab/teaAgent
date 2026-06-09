# H4/H5/H6 Usage-First Design

> **Status:** Draft
> **Last Updated:** 2026-06-09
> **Owner:** TBD

## Purpose

Design the user experience for H4 (Durable Team Operations), H5 (Quality and Eval Loop), and H6 (Packaging and Adoption) by starting from actual usage scenarios.

## H4: Durable Team Operations

### Scenario 1: Team Operator Monitors Multi-Tenant Workflows

**User Story:** As a team operator, I need to monitor active workflows across multiple tenants to ensure policies are being followed and costs are within budget.

**CLI Example:**
```bash
# View all active workflows across tenants
teaagent cockpit workflows --all-tenants

# View pending approvals for a specific tenant
teaagent cockpit approvals --tenant acme-corp

# Approve a pending workflow action
teaagent approve --workflow-id wf-123 --action-id act-456

# View cost allocation by tenant
teaagent cost report --by-tenant --period today
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ TeaAgent Control Plane Cockpit                              │
├─────────────────────────────────────────────────────────────┤
│ [Workflows] [Approvals] [Costs] [Memory] [Background]      │
├─────────────────────────────────────────────────────────────┤
│ Active Workflows (3 tenants, 12 active)                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Tenant           │ Workflow      │ Status   │ Cost      ││
│ │ acme-corp        │ deploy-prod   │ running  │ $12.34    ││
│ │ acme-corp        │ test-integration │ pending │ $0.00    ││
│ │ startup-inc      │ feature-x     │ waiting  │ $5.67     ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- Operator views all active workflows
- Filters by tenant to focus on specific customer
- Sees cost attribution in real-time
- Approves pending action with one keystroke

**Error Example:**
```
Error: Approval denied - policy violation
Reason: Workflow 'deploy-prod' requires 2-of-3 consensus for production deployments
Current approvals: 1/3 required
```

**Design Issues Revealed:**
- Need for tenant filtering and search
- Cost attribution needs to be real-time
- Policy violations should be actionable (show who else needs to approve)

### Scenario 2: Background Run Durability

**User Story:** As a developer, I need long-running background tasks to complete even if my laptop restarts or I lose network connectivity.

**CLI Example:**
```bash
# Start a long-running task in background
teaagent agent run --background "Analyze entire codebase for security issues"

# Check background run status
teaagent background status --run-id bg-789

# Attach to a background run after restart
teaagent background attach --run-id bg-789

# View background run logs
teaagent background logs --run-id bg-789 --tail
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Background Runs                                             │
├─────────────────────────────────────────────────────────────┤
│ Run ID        │ Status    │ Progress │ Cost    │ Action    │
│ bg-789        │ running   │ 67%      │ $8.90   │ [Attach]  │
│ bg-790        │ suspended │ 45%      │ $3.21   │ [Resume]  │
│ bg-791        │ completed │ 100%     │ $15.00  │ [View]    │
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- User starts background task
- Closes laptop, goes home
- Reopens laptop next day
- Task completed successfully, results available

**Error Example:**
```
Error: Background run bg-789 failed to resume
Reason: Worker process died during network interruption
Recovery: Automatic retry initiated (attempt 2/3)
```

**Design Issues Revealed:**
- Need for robust recovery mechanisms
- Progress indication for long-running tasks
- Clear error messages with recovery options

### Scenario 3: Collaboration Policy Enforcement

**User Story:** As a team lead, I need to ensure that destructive actions require consensus from multiple team members.

**CLI Example:**
```bash
# Define a collaboration policy
teaagent policy create --name production-deploy \
  --consensus 2-of-3 \
  --roles senior-dev,devops-lead \
  --actions deploy,delete

# View policy status
teaagent policy status --workflow-id wf-123

# Cast approval vote
teaagent approve --workflow-id wf-123 --vote-approve
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Pending Approval: Production Deploy                         │
├─────────────────────────────────────────────────────────────┤
│ Policy: production-deploy (2-of-3 consensus)               │
│ Current Approvals: 1/3                                      │
├─────────────────────────────────────────────────────────────┤
│ Required Roles: senior-dev, devops-lead                     │
│                                                              │
│ [✓] alice@company.com (senior-dev) - approved 2m ago       │
│ [ ] bob@company.com (devops-lead) - pending                │
│ [ ] carol@company.com (senior-dev) - pending               │
├─────────────────────────────────────────────────────────────┤
│ [Approve] [Reject] [View Details]                           │
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- Policy requires 2-of-3 consensus
- Two team members approve
- Action executes automatically

**Error Example:**
```
Error: Insufficient permissions
Reason: Your role 'junior-dev' is not in the required roles for this action
Required roles: senior-dev, devops-lead
```

**Design Issues Revealed:**
- Need for role management interface
- Clear visualization of approval progress
- Handling of role changes mid-approval

## H5: Quality and Eval Loop

### Scenario 1: Release Engineer Runs Eval Gates

**User Story:** As a release engineer, I need to run automated eval gates before releasing to ensure prompt changes don't degrade performance.

**CLI Example:**
```bash
# Run full eval suite
teaagent eval run --full-suite

# Run specific eval category
teaagent eval run --category prompt-regression

# View eval results
teaagent eval results --run-id eval-456

# Compare with baseline
teaagent eval compare --run-id eval-456 --baseline baseline-123
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Eval Suite Results                                           │
├─────────────────────────────────────────────────────────────┤
│ Run ID: eval-456 | Duration: 24m 32s                        │
├─────────────────────────────────────────────────────────────┤
│ Category           │ Passed │ Failed │ Duration │ Status   │
│ Prompt regression  │ 45     │ 2      │ 8m 12s   │ ❌ FAIL  │
│ Repo-map benchmark │ 12     │ 0      │ 5m 45s   │ ✓ PASS   │
│ Long-session       │ 8      │ 0      │ 6m 30s   │ ✓ PASS   │
│ Scope-creep        │ 15     │ 1      │ 4m 05s   │ ❌ FAIL  │
├─────────────────────────────────────────────────────────────┤
│ Overall: 80/88 passed (90.9%) - BLOCKING RELEASE            │
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- Release engineer runs eval suite
- All tests pass
- Release is approved automatically

**Error Example:**
```
Error: Eval suite failed - blocking release
Failed tests:
  - prompt-regression/test-002: Expected response time < 2s, got 3.5s
  - scope-creep/test-007: Scope expanded beyond allowed boundaries

Action: Fix failing tests or request exception with justification
```

**Design Issues Revealed:**
- Need for clear failure explanations
- Exception process for acceptable failures
- Baseline management for regression detection

### Scenario 2: Evidence Bundle Export for Compliance

**User Story:** As a security reviewer, I need to export tamper-proof evidence bundles for compliance audits.

**CLI Example:**
```bash
# Export evidence bundle for a run
teaagent audit export --run-id run-789 --output evidence-bundle.tar.gz

# Verify evidence bundle integrity
teaagent audit verify --bundle evidence-bundle.tar.gz

# View bundle contents
teaagent audit inspect --bundle evidence-bundle.tar.gz
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Evidence Bundle Export                                      │
├─────────────────────────────────────────────────────────────┤
│ Run ID: run-789 | Tenant: acme-corp                         │
│ Bundle Size: 2.3 MB | Signature: ✓ Valid                    │
├─────────────────────────────────────────────────────────────┤
│ Contents:                                                    │
│  - audit-trail.jsonl (signed)                               │
│  - cost-attribution.csv (signed)                            │
│  - policy-violations.json (signed)                          │
│  - tool-calls.jsonl (signed)                                │
│  - sbom.json (signed)                                       │
├─────────────────────────────────────────────────────────────┤
│ [Export] [Verify] [View Contents]                           │
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- User exports evidence bundle
- Bundle is cryptographically signed
- Compliance reviewer verifies signature
- All contents are tamper-proof

**Error Example:**
```
Error: Evidence bundle verification failed
Reason: Signature invalid - bundle may have been tampered with
Expected signature: abc123...
Actual signature: def456...
```

**Design Issues Revealed:**
- Need for clear verification feedback
- Bundle size management for large runs
- Key management for signing

### Scenario 3: Regression Test Management

**User Story:** As a QA engineer, I need to manage regression test baselines and handle false positives.

**CLI Example:**
```bash
# Update baseline for a specific test
teaagent regression baseline update --test test-002 --new-baseline result.json

# Quarantine a flaky test
teaagent regression quarantine --test test-007 --reason "network dependency"

# View regression trends
teaagent regression trends --period 30d
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Regression Test Management                                  │
├─────────────────────────────────────────────────────────────┤
│ Test ID        │ Status    │ Trend    │ Last Run │ Action   │
│ test-001       │ passing   │ stable   │ 2h ago   │ [View]   │
│ test-002       │ failing   │ degraded │ 2h ago   │ [Update] │
│ test-007       │ quarantined│ flaky   │ 1d ago   │ [Unquarantine]│
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- QA engineer identifies failing test
- Determines it's a legitimate improvement
- Updates baseline
- Test passes in next run

**Error Example:**
```
Error: Cannot update baseline
Reason: Test test-002 is in a protected suite
Protected suites require security review for baseline changes
```

**Design Issues Revealed:**
- Need for protected test suites
- Baseline versioning and rollback
- Flaky test detection and quarantine

## H6: Packaging and Adoption

### Scenario 1: End User Installs Packaged TeaAgent

**User Story:** As an end user, I need to install TeaAgent easily on my machine without manual setup.

**CLI Example:**
```bash
# Install via package manager (macOS)
brew install teaagent

# Install via package manager (Linux)
sudo apt install teaagent

# Install via downloaded package
teaagent-installer-macos.pkg

# Verify installation
teaagent --version
```

**Success Example:**
- User runs one command
- Package manager handles dependencies
- TeaAgent installs correctly
- User can start using immediately

**Error Example:**
```
Error: Installation failed
Reason: Signature verification failed
Package: teaagent-1.2.3-macos.pkg
Expected signature: valid
Actual signature: INVALID
Action: Download package from official source only
```

**Design Issues Revealed:**
- Need for clear installation instructions
- Signature verification should be automatic
- Dependency management across platforms

### Scenario 2: User Updates TeaAgent

**User Story:** As a user, I want to update TeaAgent to the latest version safely with rollback capability.

**CLI Example:**
```bash
# Check for updates
teaagent update check

# Apply update
teaagent update apply

# Rollback if needed
teaagent update rollback
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ TeaAgent Update                                             │
├─────────────────────────────────────────────────────────────┤
│ Current Version: 1.2.3                                     │
│ Latest Version: 1.2.4                                       │
│                                                              │
│ Changes in 1.2.4:                                           │
│  - Fixed background run durability issue                    │
│  - Improved TUI performance                                  │
│  - Added eval suite optimizations                           │
├─────────────────────────────────────────────────────────────┤
│ [Update Now] [Skip] [View Changelog]                         │
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- User checks for updates
- Sees new version available
- Updates successfully
- Can rollback if issues occur

**Error Example:**
```
Error: Update failed
Reason: Download interrupted
Recovery: Automatic rollback to version 1.2.3 initiated
```

**Design Issues Revealed:**
- Need for clear changelog communication
- Automatic rollback on failure
- Delta updates for large downloads

### Scenario 3: Session Attach Across Restarts

**User Story:** As a user, I want to resume my TeaAgent session after restarting my computer or switching devices.

**CLI Example:**
```bash
# List available sessions
teaagent session list

# Attach to a session
teaagent session attach --session-id sess-123

# Resume from where I left off
# (continues in TUI/CLI)
```

**TUI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Available Sessions                                          │
├─────────────────────────────────────────────────────────────┤
│ Session ID    │ Last Active │ Status    │ Context           │
│ sess-123      │ 2h ago      │ suspended │ code-review       │
│ sess-124      │ 1d ago      │ completed │ bug-fix           │
│ sess-125      │ 5m ago      │ active    │ deployment        │
├─────────────────────────────────────────────────────────────┤
│ [Attach sess-123] [Resume sess-125] [View Details]         │
└─────────────────────────────────────────────────────────────┘
```

**Success Example:**
- User restarts computer
- Opens TeaAgent
- Sees previous session available
- Attaches and continues work

**Error Example:**
```
Error: Session sess-123 cannot be resumed
Reason: Session state corrupted during shutdown
Recovery: Session terminated, starting new session
```

**Design Issues Revealed:**
- Need for robust session persistence
- Clear session status indicators
- Graceful handling of corrupted sessions

## Design Resolutions for Confusing Parts

### H4 Resolved Confusions
1. **Policy precedence**: Specificity-first resolution. Tenant-specific policies override global system policies. If multiple conflicting tenant policies apply, the most restrictive policy is enforced (fail-closed model).
2. **Tenant isolation context visibility**: The active `tenant_id` will be rendered in the TUI title bar (e.g., `TeaAgent Cockpit - [tenant-alpha]`) and appended to standard CLI output headers to avoid ambiguity.
3. **Cost attribution of shared resources**: Shared resource usage (such as base model keys) will be metered and charged to the invoking tenant execution session in real-time.

### H5 Resolved Confusions
1. **Eval baselines updates**: Baselines are version-controlled in the repository. Updating a baseline requires running `teaagent regression baseline update --test TEST_ID` followed by a git commit to the main branch.
2. **Evidence bundle size management**: Large output streams (like raw command logs) are compressed using gzip. Very large outputs (exceeding 20KB per entry) will be summarized in the metadata, with complete logs accessible via secondary files.
3. **Exception process**: Eval failures can be bypassed for emergency hotfixes by supplying a signed `ApprovalRequest` token signed by a designated team operator.

### H6 Resolved Confusions
1. **Package signatures manual verification**: If automatic validation fails, users can manually run `teaagent verify --package PKG_PATH --signature SIG_PATH` using public signing keys.
2. **Update rollback data safety**: Rolling back an update affects only system binaries and shared libraries; user configurations, databases, and logs stored under `.teaagent/` are preserved.
3. **Session synchronization**: Session status is stored locally. Across different devices, synchronization is handled by configuring an encrypted remote volume endpoint (e.g., S3/GCS) in the tenant settings.

## Design Issues Summary

1. **Cross-horizon integration:** Cost attribution from H4 should be included in H5 evidence bundles
2. **Policy complexity:** H4 collaboration policies need a simple default configuration
3. **Eval maintenance:** H5 regression suite needs ongoing maintenance burden reduction
4. **Platform support:** H6 packaging should prioritize platforms based on user telemetry
5. **Session state:** H6 session attach needs clear state management to avoid confusion
