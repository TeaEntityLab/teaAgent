# H4/H5/H6 Implementation Task Plan

> **Status:** Draft
> **Last Updated:** 2026-06-09
> **Owner:** TBD

## Overview

This task plan breaks down H4, H5, and H6 implementation into independently testable tickets. Each ticket is designed to be 30-120 minutes of work with clear acceptance criteria.

## Dependencies

- **H4 depends on:** H3 complete (ecosystem trust foundations)
- **H5 depends on:** H4 complete (cost attribution needed for evidence bundles)
- **H6 depends on:** H5 complete (eval-gated releases needed for stable packages)

## H4: Durable Team Operations

### H4-001: Control Plane Operator Cockpit (TUI)

#### TASK-H4-001-01: TUI Cockpit Screen Layout
- **Goal:** Create base TUI screen layout for control plane cockpit
- **Scope:** Tab navigation, screen framework, basic layout
- **Inputs:** Existing TUI foundation, design mockups
- **Outputs:** TUI cockpit screen with navigation tabs
- **Dependencies:** None
- **Acceptance Criteria:**
  - TUI launches with cockpit screen
  - Navigation tabs (Workflows, Approvals, Costs, Memory, Background) are visible
  - Screen layout matches design mockups
- **Tests:** TUI smoke test, navigation test
- **Files likely touched:** `teaagent/tui/__init__.py`, `teaagent/tui/cockpit.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-001-02: Workflows Screen Implementation
- **Goal:** Implement workflows screen showing active multi-tenant workflows
- **Scope:** Workflow listing, tenant filtering, status display
- **Inputs:** Run store, tenant metadata
- **Outputs:** Workflows screen with real-time workflow data
- **Dependencies:** TASK-H4-001-01
- **Acceptance Criteria:**
  - Active workflows displayed in table format
  - Tenant filtering works correctly
  - Status updates in real-time (< 500ms)
- **Tests:** Workflow screen integration test
- **Files likely touched:** `teaagent/tui/cockpit.py`, `teaagent/run_store.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-001-03: Approvals Screen Implementation
- **Goal:** Implement approvals screen for pending workflow actions
- **Scope:** Pending approvals queue, approve/reject actions, tenant context
- **Inputs:** Approval queue, policy engine
- **Outputs:** Approvals screen with action management
- **Dependencies:** TASK-H4-001-01, TASK-H4-002-01
- **Acceptance Criteria:**
  - Pending approvals displayed with tenant context
  - Approve/reject actions work correctly
  - Policy violations are clearly shown
- **Tests:** Approvals screen integration test
- **Files likely touched:** `teaagent/tui/cockpit.py`, `teaagent/approval_manager.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-001-04: Cost Dashboard Implementation
- **Goal:** Implement cost dashboard showing per-tenant cost allocation
- **Scope:** Cost attribution display, cost trends, budget alerts
- **Inputs:** Cost tracking data, budget envelopes
- **Outputs:** Cost dashboard with real-time cost data
- **Dependencies:** TASK-H4-001-01, TASK-H4-004-01
- **Acceptance Criteria:**
  - Costs displayed by tenant and workflow
  - Cost trends visible over time
  - Budget alerts trigger correctly
- **Tests:** Cost dashboard integration test
- **Files likely touched:** `teaagent/tui/cockpit.py`, `teaagent/budget.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-001-05: Memory Registry Screen
- **Goal:** Implement memory registry inspection screen
- **Scope:** Active memory display, memory metadata, quarantine status
- **Inputs:** Memory catalog, memory metadata
- **Outputs:** Memory registry screen with inspection capabilities
- **Dependencies:** TASK-H4-001-01
- **Acceptance Criteria:**
  - Active memory entries displayed
  - Memory metadata (scope, source, confidence) visible
  - Quarantined memory clearly labeled
- **Tests:** Memory registry integration test
- **Files likely touched:** `teaagent/tui/cockpit.py`, `teaagent/memory.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-001-06: Background Lifecycle Screen
- **Goal:** Implement background run lifecycle management screen
- **Scope:** Background run listing, attach/resume/stop actions
- **Inputs:** Background run store, worker status
- **Outputs:** Background lifecycle screen with management actions
- **Dependencies:** TASK-H4-001-01, TASK-H4-003-01
- **Acceptance Criteria:**
  - Background runs displayed with status
  - Attach/resume/stop actions work correctly
  - Progress indicators update in real-time
- **Tests:** Background lifecycle integration test
- **Files likely touched:** `teaagent/tui/cockpit.py`, `teaagent/background.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

### H4-002: Collaboration & Swarm Policy Enforcement

#### TASK-H4-002-01: Policy Engine Foundation
- **Goal:** Create policy engine for collaboration rules
- **Scope:** Policy definition, policy storage, policy evaluation
- **Inputs:** Policy schema, role definitions
- **Outputs:** Policy engine with basic evaluation
- **Dependencies:** None
- **Acceptance Criteria:**
  - Policies can be defined and stored
  - Policy evaluation returns allow/deny decisions
  - Policy conflicts resolved with deterministic precedence
- **Tests:** Policy engine unit tests
- **Files likely touched:** `teaagent/policy.py`, `teaagent/policy_engine.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-002-02: Role-Based Access Control
- **Goal:** Implement role-based access control for agent actions
- **Scope:** Role definitions, role assignment, permission checks
- **Inputs:** User roles, action permissions
- **Outputs:** RBAC system with permission enforcement
- **Dependencies:** TASK-H4-002-01
- **Acceptance Criteria:**
  - Roles can be defined and assigned
  - Permission checks enforce role boundaries
  - Role changes take effect immediately
- **Tests:** RBAC integration tests
- **Files likely touched:** `teaagent/rbac.py`, `teaagent/policy.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

#### TASK-H4-002-03: Multi-Agent Consensus Validation
- **Goal:** Implement consensus validation for collaborative runs
- **Scope:** Consensus rules, vote tracking, consensus decision
- **Inputs:** Policy requirements, user votes
- **Outputs:** Consensus validation system
- **Dependencies:** TASK-H4-002-01, TASK-H4-002-02
- **Acceptance Criteria:**
  - Consensus rules (e.g., 2-of-3) enforced
  - Vote tracking accurate
  - Consensus decisions trigger actions automatically
- **Tests:** Consensus validation integration tests
- **Files likely touched:** `teaagent/consensus.py`, `teaagent/policy.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-002-04: Policy-Based Routing
- **Goal:** Implement policy-based routing for collaborative runs
- **Scope:** Routing rules, policy-aware dispatch, routing audit
- **Inputs:** Policy engine, routing rules
- **Outputs:** Policy-based routing system
- **Dependencies:** TASK-H4-002-01
- **Acceptance Criteria:**
  - Actions routed based on policy rules
  - Routing decisions logged for audit
  - Policy violations block routing
- **Tests:** Policy routing integration tests
- **Files likely touched:** `teaagent/router.py`, `teaagent/policy.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

### H4-003: Background/Cloud Durability

#### TASK-H4-003-01: Background Run Persistence
- **Goal:** Implement persistent run state for background tasks
- **Scope:** Run state serialization, persistence layer, state recovery
- **Inputs:** Run state, persistence backend
- **Outputs:** Background run persistence system
- **Dependencies:** None
- **Acceptance Criteria:**
  - Run state serialized and persisted correctly
  - State recovery works after process restart
  - State corruption detected and handled
- **Tests:** Persistence unit tests, recovery integration tests
- **Files likely touched:** `teaagent/background.py`, `teaagent/persistence.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-003-02: Cloud Task Intake Gateway
- **Goal:** Implement cloud gateway for task intake
- **Scope:** Gateway API, task queue, cloud worker coordination
- **Inputs:** Task definitions, cloud provider SDK
- **Outputs:** Cloud task intake gateway
- **Dependencies:** TASK-H4-003-01
- **Acceptance Criteria:**
  - Tasks submitted via gateway API
  - Task queue managed correctly
  - Cloud workers coordinate properly
- **Tests:** Gateway integration tests
- **Files likely touched:** `teaagent/gateway.py`, `teaagent/cloud.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

#### TASK-H4-003-03: Background Worker Lifecycle
- **Goal:** Implement background worker lifecycle management
- **Scope:** Worker startup, health monitoring, worker restart
- **Inputs:** Worker process, health checks
- **Outputs:** Background worker lifecycle manager
- **Dependencies:** TASK-H4-003-01
- **Acceptance Criteria:**
  - Workers start and stop correctly
  - Worker health monitored
  - Failed workers restarted automatically
- **Tests:** Worker lifecycle integration tests
- **Files likely touched:** `teaagent/worker.py`, `teaagent/background.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-003-04: Network Interruption Recovery
- **Goal:** Implement recovery from network interruptions
- **Scope:** Network failure detection, retry logic, state reconciliation
- **Inputs:** Network status, retry policy
- **Outputs:** Network interruption recovery system
- **Dependencies:** TASK-H4-003-01
- **Acceptance Criteria:**
  - Network failures detected
  - Retry logic works correctly
  - State reconciled after reconnection
- **Tests:** Network failure simulation tests
- **Files likely touched:** `teaagent/recovery.py`, `teaagent/background.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

### H4-004: Cost Attribution

#### TASK-H4-004-01: Per-Tenant Cost Tracking
- **Goal:** Implement cost tracking per tenant
- **Scope:** Cost allocation by tenant, cost aggregation, cost storage
- **Inputs:** Cost events, tenant metadata
- **Outputs:** Per-tenant cost tracking system
- **Dependencies:** None
- **Acceptance Criteria:**
  - Costs allocated to correct tenant
  - Cost aggregation accurate
  - Cost storage efficient
- **Tests:** Cost tracking unit tests
- **Files likely touched:** `teaagent/cost.py`, `teaagent/budget.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-004-02: Workflow-Level Cost Envelopes
- **Goal:** Implement cost envelopes at workflow level
- **Scope:** Workflow budget definition, envelope enforcement, cost alerts
- **Inputs:** Workflow definitions, budget limits
- **Outputs:** Workflow cost envelope system
- **Dependencies:** TASK-H4-004-01
- **Acceptance Criteria:**
  - Workflow budgets defined and enforced
  - Cost alerts trigger correctly
  - Envelope violations block new work
- **Tests:** Cost envelope integration tests
- **Files likely touched:** `teaagent/cost.py`, `teaagent/budget.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H4-004-03: Cost Alerting
- **Goal:** Implement cost alerting mechanism
- **Scope:** Alert thresholds, alert delivery, alert history
- **Inputs:** Cost data, alert configuration
- **Outputs:** Cost alerting system
- **Dependencies:** TASK-H4-004-01
- **Acceptance Criteria:**
  - Alerts trigger at configured thresholds
  - Alerts delivered to correct recipients
  - Alert history maintained
- **Tests:** Alerting integration tests
- **Files likely touched:** `teaagent/alerts.py`, `teaagent/cost.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

## H5: Quality and Eval Loop

### H5-001: Eval-Gating Release Pipelines

#### TASK-H5-001-01: Eval Suite Framework
- **Goal:** Create eval suite framework for automated testing
- **Scope:** Test discovery, test execution, result aggregation
- **Inputs:** Test files, test configuration
- **Outputs:** Eval suite framework
- **Dependencies:** None
- **Acceptance Criteria:**
  - Tests discovered and executed
  - Results aggregated correctly
  - Test execution time tracked
- **Tests:** Framework unit tests
- **Files likely touched:** `teaagent/eval.py`, `scripts/eval_runner.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-001-02: Prompt Regression Suite
- **Goal:** Implement prompt change regression tests
- **Scope:** Prompt test fixtures, response comparison, regression detection
- **Inputs:** Prompt templates, expected responses
- **Outputs:** Prompt regression test suite
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Prompt changes tested against fixtures
  - Response comparison accurate
  - Regressions detected correctly
- **Tests:** Regression suite integration tests
- **Files likely touched:** `tests/eval/prompt_regression.py`, `teaagent/eval.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-001-03: Repo-Map Benchmark Automation
- **Goal:** Automate repo-map benchmark in eval suite
- **Scope:** Benchmark integration, baseline comparison, performance tracking
- **Inputs:** Existing `scripts/repo_map_benchmark.py`
- **Outputs:** Automated repo-map benchmark
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Benchmark runs in eval suite
  - Baseline comparison works
  - Performance trends tracked
- **Tests:** Benchmark integration test
- **Files likely touched:** `scripts/repo_map_benchmark.py`, `teaagent/eval.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-001-04: Long-Session Context Health Tests
- **Goal:** Implement long-session context health tests
- **Scope:** Long-session fixtures, context drift detection, memory leak tests
- **Inputs:** Long-session test data
- **Outputs:** Long-session context health tests
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Long-session scenarios tested
  - Context drift detected
  - Memory leaks identified
- **Tests:** Long-session integration tests
- **Files likely touched:** `tests/eval/long_session.py`, `teaagent/eval.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-001-05: Scope-Creep Detection Tests
- **Goal:** Implement scope-creep detection tests
- **Scope:** Scope boundary tests, creep detection, violation reporting
- **Inputs:** Scope definitions, test scenarios
- **Outputs:** Scope-creep detection tests
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Scope boundaries enforced
  - Scope creep detected
  - Violations reported clearly
- **Tests:** Scope-creep integration tests
- **Files likely touched:** `tests/eval/scope_creep.py`, `teaagent/eval.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-001-06: Release Pipeline Integration
- **Goal:** Integrate eval gates into release pipeline
- **Scope:** CI integration, gate enforcement, failure handling
- **Inputs:** CI configuration, eval results
- **Outputs:** Eval-gated release pipeline
- **Dependencies:** TASK-H5-001-01 through TASK-H5-001-05
- **Acceptance Criteria:**
  - Eval suite runs in CI
  - Release blocked on eval failure
  - Failure handling clear
- **Tests:** CI integration test
- **Files likely touched:** `.github/workflows/release.yml`, `teaagent/eval.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

### H5-002: Evidence Bundle Export

#### TASK-H5-002-01: Evidence Bundle Schema
- **Goal:** Define evidence bundle schema and structure
- **Scope:** Bundle format, content types, metadata
- **Inputs:** Audit data, compliance requirements
- **Outputs:** Evidence bundle schema
- **Dependencies:** None
- **Acceptance Criteria:**
  - Bundle schema defined
  - Content types specified
  - Metadata requirements clear
- **Tests:** Schema validation tests
- **Files likely touched:** `teaagent/evidence/schema.py`, `api/data-formats.md`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-002-02: Bundle Generation
- **Goal:** Implement evidence bundle generation
- **Scope:** Data collection, bundle assembly, compression
- **Inputs:** Audit trail, cost data, policy violations
- **Outputs:** Evidence bundle generator
- **Dependencies:** TASK-H5-002-01
- **Acceptance Criteria:**
  - Bundles generated correctly
  - All required data included
  - Compression efficient
- **Tests:** Bundle generation tests
- **Files likely touched:** `teaagent/evidence/generator.py`, `teaagent/audit_export.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-002-03: Bundle Signing
- **Goal:** Implement cryptographic signing for evidence bundles
- **Scope:** Signature generation, key management, signature verification
- **Inputs:** Signing keys, bundle data
- **Outputs:** Bundle signing system
- **Dependencies:** TASK-H5-002-02
- **Acceptance Criteria:**
  - Bundles signed correctly
  - Signatures verifiable
  - Key management secure
- **Tests:** Signing integration tests
- **Files likely touched:** `teaagent/evidence/signing.py`, `teaagent/evidence/generator.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

#### TASK-H5-002-04: Bundle Verification
- **Goal:** Implement evidence bundle verification
- **Scope:** Signature verification, integrity checks, validation
- **Inputs:** Signed bundles, verification keys
- **Outputs:** Bundle verification system
- **Dependencies:** TASK-H5-002-03
- **Acceptance Criteria:**
  - Signatures verified correctly
  - Integrity checks pass
  - Validation errors clear
- **Tests:** Verification integration tests
- **Files likely touched:** `teaagent/evidence/verification.py`, `teaagent/evidence/signing.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

#### TASK-H5-002-05: CLI Commands for Evidence
- **Goal:** Implement CLI commands for evidence export and verification
- **Scope:** Export command, verify command, inspect command
- **Inputs:** Bundle data, CLI framework
- **Outputs:** Evidence CLI commands
- **Dependencies:** TASK-H5-002-02, TASK-H5-002-04
- **Acceptance Criteria:**
  - Export command works
  - Verify command works
  - Inspect command shows bundle contents
- **Tests:** CLI command tests
- **Files likely touched:** `teaagent/cli.py`, `teaagent/evidence/cli.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

### H5-003: Regression Test Management

#### TASK-H5-003-01: Baseline Management
- **Goal:** Implement regression test baseline management
- **Scope:** Baseline storage, baseline updates, baseline versioning
- **Inputs:** Test results, baseline data
- **Outputs:** Baseline management system
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Baselines stored correctly
  - Baselines updated safely
  - Baseline versioning works
- **Tests:** Baseline management tests
- **Files likely touched:** `teaagent/regression/baseline.py`, `teaagent/eval.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-003-02: Flaky Test Detection
- **Goal:** Implement flaky test detection and quarantine
- **Scope:** Flakiness detection, quarantine mechanism, quarantine management
- **Inputs:** Test results, flakiness thresholds
- **Outputs:** Flaky test detection system
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Flaky tests detected
  - Quarantine mechanism works
  - Quarantine management clear
- **Tests:** Flaky test detection tests
- **Files likely touched:** `teaagent/regression/flaky.py`, `teaagent/eval.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-003-03: Regression Trend Analysis
- **Goal:** Implement regression trend analysis
- **Scope:** Trend tracking, trend visualization, trend alerts
- **Inputs:** Historical test results
- **Outputs:** Regression trend analysis system
- **Dependencies:** TASK-H5-001-01
- **Acceptance Criteria:**
  - Trends tracked over time
  - Trends visualized clearly
  - Trend alerts trigger correctly
- **Tests:** Trend analysis tests
- **Files likely touched:** `teaagent/regression/trends.py`, `teaagent/eval.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H5-003-04: Exception Process
- **Goal:** Implement exception process for eval failures
- **Scope:** Exception requests, justification tracking, approval workflow
- **Inputs:** Failure data, exception requests
- **Outputs:** Exception process system
- **Dependencies:** TASK-H5-001-06
- **Acceptance Criteria:**
  - Exceptions can be requested
  - Justifications tracked
  - Approval workflow works
- **Tests:** Exception process tests
- **Files likely touched:** `teaagent/regression/exception.py`, `teaagent/eval.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

## H6: Packaging and Adoption

### H6-001: Desktop/Client-Server Packaging

#### TASK-H6-001-01: Build Automation
- **Goal:** Implement automated build system for packages
- **Scope:** Build scripts, platform-specific builds, build artifacts
- **Inputs:** Source code, build configuration
- **Outputs:** Automated build system
- **Dependencies:** None
- **Acceptance Criteria:**
  - Builds automated for all platforms
  - Build artifacts reproducible
  - Build failures detected
- **Tests:** Build automation tests
- **Files likely touched:** `scripts/build.py`, `scripts/build_*.sh`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-001-02: macOS Packaging
- **Goal:** Create macOS package (pkg)
- **Scope:** Package creation, dependency bundling, installation script
- **Inputs:** Build artifacts, packaging tools
- **Outputs:** macOS package
- **Dependencies:** TASK-H6-001-01
- **Acceptance Criteria:**
  - Package installs correctly
  - Dependencies bundled
  - Installation script works
- **Tests:** macOS package installation test
- **Files likely touched:** `scripts/package_macos.py`, `scripts/install_macos.sh`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-001-03: Windows Packaging
- **Goal:** Create Windows package (msi)
- **Scope:** Package creation, dependency bundling, installation script
- **Inputs:** Build artifacts, packaging tools
- **Outputs:** Windows package
- **Dependencies:** TASK-H6-001-01
- **Acceptance Criteria:**
  - Package installs correctly
  - Dependencies bundled
  - Installation script works
- **Tests:** Windows package installation test
- **Files likely touched:** `scripts/package_windows.py`, `scripts/install_windows.ps1`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-001-04: Linux Packaging
- **Goal:** Create Linux packages (deb, rpm)
- **Scope:** Package creation, dependency bundling, repository setup
- **Inputs:** Build artifacts, packaging tools
- **Outputs:** Linux packages
- **Dependencies:** TASK-H6-001-01
- **Acceptance Criteria:**
  - Packages install correctly
  - Dependencies specified
  - Repository setup works
- **Tests:** Linux package installation test
- **Files likely touched:** `scripts/package_linux.py`, `scripts/install_linux.sh`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-001-05: Client-Server Distribution
- **Goal:** Create client-server distribution package
- **Scope:** Server package, client package, coordination
- **Inputs:** Build artifacts, server components
- **Outputs:** Client-server distribution
- **Dependencies:** TASK-H6-001-01
- **Acceptance Criteria:**
  - Server package works
  - Client package works
  - Client-server coordination works
- **Tests:** Client-server integration test
- **Files likely touched:** `scripts/package_client_server.py`, `teaagent/server.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

### H6-002: SBOM and Binary Signing

#### TASK-H6-002-01: SBOM Generation
- **Goal:** Implement Software Bill of Materials (SBOM) generation
- **Scope:** Dependency scanning, SBOM format, SBOM generation
- **Inputs:** Source code, dependency data
- **Outputs:** SBOM generation system
- **Dependencies:** None
- **Acceptance Criteria:**
  - SBOM generated in standard format
  - All dependencies included
  - SBOM accurate
- **Tests:** SBOM generation tests
- **Files likely touched:** `scripts/sbom.py`, `teaagent/sbom.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-002-02: Binary Signing
- **Goal:** Implement binary signing for packages
- **Scope:** Signing process, key management, signature verification
- **Inputs:** Build artifacts, signing keys
- **Outputs:** Binary signing system
- **Dependencies:** TASK-H6-001-01
- **Acceptance Criteria:**
  - Binaries signed correctly
  - Signatures verifiable
  - Key management secure
- **Tests:** Binary signing tests
- **Files likely touched:** `scripts/sign.py`, `teaagent/signing.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

#### TASK-H6-002-03: Dependency Vulnerability Scanning
- **Goal:** Implement dependency vulnerability scanning
- **Scope:** Vulnerability database, scanning process, reporting
- **Inputs:** Dependency data, vulnerability database
- **Outputs:** Vulnerability scanning system
- **Dependencies:** TASK-H6-002-01
- **Acceptance Criteria:**
  - Vulnerabilities scanned
  - Reports generated
  - High-severity vulnerabilities block builds
- **Tests:** Vulnerability scanning tests
- **Files likely touched:** `scripts/scan_vulnerabilities.py`, `teaagent/security.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-002-04: Package Verification
- **Goal:** Implement package verification (signature + SBOM)
- **Scope:** Signature verification, SBOM verification, integrity checks
- **Inputs:** Package files, verification keys
- **Outputs:** Package verification system
- **Dependencies:** TASK-H6-002-01, TASK-H6-002-02
- **Acceptance Criteria:**
  - Signatures verified
  - SBOM verified
  - Integrity checks pass
- **Tests:** Package verification tests
- **Files likely touched:** `scripts/verify_package.py`, `teaagent/verification.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

### H6-003: Update Mechanism

#### TASK-H6-003-01: Update Check
- **Goal:** Implement update check mechanism
- **Scope:** Version check, update server, version comparison
- **Inputs:** Current version, update server
- **Outputs:** Update check system
- **Dependencies:** None
- **Acceptance Criteria:**
  - Updates checked automatically
  - Version comparison correct
  - Update server reliable
- **Tests:** Update check tests
- **Files likely touched:** `teaagent/update.py`, `teaagent/version.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-003-02: Delta Updates
- **Goal:** Implement delta update mechanism for efficiency
- **Scope:** Delta generation, delta application, delta verification
- **Inputs:** Current version, new version
- **Outputs:** Delta update system
- **Dependencies:** TASK-H6-003-01
- **Acceptance Criteria:**
  - Deltas generated correctly
  - Deltas applied safely
  - Delta verification works
- **Tests:** Delta update tests
- **Files likely touched:** `teaagent/update/delta.py`, `teaagent/update.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-003-03: Update Application
- **Goal:** Implement update application with rollback
- **Scope:** Update download, update installation, rollback mechanism
- **Inputs:** Update packages, current installation
- **Outputs:** Update application system
- **Dependencies:** TASK-H6-003-01
- **Acceptance Criteria:**
  - Updates downloaded correctly
  - Updates installed safely
  - Rollback works on failure
- **Tests:** Update application tests
- **Files likely touched:** `teaagent/update/installer.py`, `teaagent/update.py`
- **Risk:** High
- **Parallelizable:** No
- **Human Review Required:** Yes

#### TASK-H6-003-04: Changelog Display
- **Goal:** Implement changelog display in update UI
- **Scope:** Changelog format, changelog display, version history
- **Inputs:** Changelog data, version history
- **Outputs:** Changelog display system
- **Dependencies:** TASK-H6-003-01
- **Acceptance Criteria:**
  - Changelog displayed clearly
  - Version history accessible
  - Changes highlighted
- **Tests:** Changelog display tests
- **Files likely touched:** `teaagent/update/changelog.py`, `teaagent/tui/update.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

### H6-004: Session Attach

#### TASK-H6-004-01: Session Persistence
- **Goal:** Implement session state persistence
- **Scope:** Session serialization, persistence backend, session recovery
- **Inputs:** Session state, persistence layer
- **Outputs:** Session persistence system
- **Dependencies:** None
- **Acceptance Criteria:**
  - Sessions serialized correctly
  - Sessions persisted reliably
  - Sessions recovered after restart
- **Tests:** Session persistence tests
- **Files likely touched:** `teaagent/session.py`, `teaagent/persistence.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-004-02: Session Listing
- **Goal:** Implement session listing UI
- **Scope:** Session discovery, session metadata, session filtering
- **Inputs:** Session store, session metadata
- **Outputs:** Session listing UI
- **Dependencies:** TASK-H6-004-01
- **Acceptance Criteria:**
  - Sessions listed correctly
  - Session metadata displayed
  - Session filtering works
- **Tests:** Session listing tests
- **Files likely touched:** `teaagent/session/list.py`, `teaagent/tui/session.py`
- **Risk:** Low
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-004-03: Session Attach
- **Goal:** Implement session attach functionality
- **Scope:** Session attachment, state restoration, context continuity
- **Inputs:** Session ID, session state
- **Outputs:** Session attach system
- **Dependencies:** TASK-H6-004-01
- **Acceptance Criteria:**
  - Sessions attach correctly
  - State restored accurately
  - Context continuous
- **Tests:** Session attach tests
- **Files likely touched:** `teaagent/session/attach.py`, `teaagent/tui/session.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

#### TASK-H6-004-04: Session Corruption Handling
- **Goal:** Implement session corruption detection and recovery
- **Scope:** Corruption detection, recovery mechanisms, error handling
- **Inputs:** Session state, validation logic
- **Outputs:** Session corruption handling
- **Dependencies:** TASK-H6-004-01
- **Acceptance Criteria:**
  - Corruption detected
  - Recovery attempted
  - Error handling clear
- **Tests:** Corruption handling tests
- **Files likely touched:** `teaagent/session/recovery.py`, `teaagent/session.py`
- **Risk:** Medium
- **Parallelizable:** No
- **Human Review Required:** No

## Summary

**Total Tickets:** 48
- H4: 18 tickets
- H5: 15 tickets
- H6: 15 tickets

**Estimated Duration:** 48-96 hours (assuming 1-2 hours per ticket)

**High-Risk Tickets (Human Review Required):**
- TASK-H4-002-02: Role-Based Access Control
- TASK-H4-003-02: Cloud Task Intake Gateway
- TASK-H5-001-06: Release Pipeline Integration
- TASK-H5-002-03: Bundle Signing
- TASK-H5-002-04: Bundle Verification
- TASK-H6-001-05: Client-Server Distribution
- TASK-H6-002-02: Binary Signing
- TASK-H6-002-04: Package Verification
- TASK-H6-003-03: Update Application

**Critical Path:**
1. H4-001 (TUI Cockpit) → H4-002 (Policy) → H4-003 (Background) → H4-004 (Cost)
2. H4 complete → H5-001 (Eval Suite) → H5-002 (Evidence) → H5-003 (Regression)
3. H5 complete → H6-001 (Packaging) → H6-002 (Signing) → H6-003 (Update) → H6-004 (Session)
