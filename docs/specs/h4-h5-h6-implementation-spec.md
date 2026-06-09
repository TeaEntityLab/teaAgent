# H4/H5/H6 Implementation Specification

> **Status:** Draft
> **Last Updated:** 2026-06-09
> **Owner:** TBD

## Problem Statement

TeaAgent has completed H0-H3 (claim hygiene, daily operator loop, multi-surface continuity, and ecosystem trust foundations). The next three horizons (H4, H5, H6) represent the transition from individual operator workflows to durable team operations, quality-gated release processes, and packaged adoption channels.

## Goals

1. **H4 (Durable Team Operations):** Enable long-running and team workflows with durable execution, control-plane views, policy enforcement, audit trails, and cost attribution
2. **H5 (Quality and Eval Loop):** Ensure prompt/runtime/model changes cannot silently degrade daily outcomes through automated eval gates and regression testing
3. **H6 (Packaging and Adoption):** Package desktop and client-server launch channels with supply-chain security, update mechanisms, and support infrastructure

## Non-Goals

- Redesigning core agent execution architecture (H0-H3 foundations are stable)
- Adding new AI capabilities beyond current scope
- Building custom cloud infrastructure (leverage existing cloud providers)
- Creating new programming languages or frameworks

## Actors

- **Team Operator:** Manages long-running workflows, monitors team activity, enforces policies
- **Release Engineer:** Runs eval gates, manages release evidence bundles, signs packages
- **End User:** Installs packaged TeaAgent, receives updates, attaches to sessions
- **Security Reviewer:** Audits evidence bundles, validates compliance

## Inputs / Outputs

### Inputs
- Existing H0-H3 implementation (multi-tenant partitioning, MCP trust, skill lifecycle)
- Current audit and run evidence infrastructure
- Existing TUI cockpit foundation
- Repo-map benchmark script (`scripts/repo_map_benchmark.py`)
- Audit export script (`audit_export.py`)

### Outputs
- **H4:** Control-plane operator cockpit, collaboration policy enforcement, background/cloud durability
- **H5:** Eval-gated release pipeline, evidence bundle export, regression test suite
- **H6:** Packaged desktop/client-server builds, SBOM/signing infrastructure, update mechanism

## Functional Requirements

### H4: Durable Team Operations

#### H4-001: Control Plane Operator Cockpit (TUI)
- **Requirement:** TUI screens to visualize multi-tenant execution/workflow states
- **Screens:**
  - Pending approvals queue with tenant context
  - Resource/cost allocation dashboard per tenant
  - Active memory registry inspection
  - Background/cloud run lifecycle management
- **Acceptance:** Operator can view and approve/reject pending actions across tenants

#### H4-002: Collaboration & Swarm Policy Enforcement
- **Requirement:** Role-aware routing rules for multi-agent workflows
- **Features:**
  - Role-based access control for agent actions
  - Multi-agent consensus validation patterns
  - Policy-based routing for collaborative runs
- **Acceptance:** Agents respect role boundaries and require consensus for destructive actions

#### H4-003: Background/Cloud Durability
- **Requirement:** Long-running workflows survive process restarts and network interruptions
- **Features:**
  - Persistent run state with resumption
  - Cloud task intake gateway
  - Background worker lifecycle management
- **Acceptance:** Background runs complete successfully despite interruptions

#### H4-004: Cost Attribution
- **Requirement:** Per-tenant and per-workflow cost tracking
- **Features:**
  - Cost allocation by tenant/workspace
  - Workflow-level cost envelopes
  - Cost alerting and budget enforcement
- **Acceptance:** Operators can view and control costs at tenant and workflow granularity

### H5: Quality and Eval Loop

#### H5-001: Eval-Gating Release Pipelines
- **Requirement:** Automated eval gates prevent silent degradation
- **Features:**
  - Prompt change regression suite
  - Repo-map benchmark automation
  - Long-session context health tests
  - Scope-creep detection tests
- **Acceptance:** Release pipeline fails if eval gates don't pass

#### H5-002: Evidence Bundle Export
- **Requirement:** Tamper-proof, verified receipts of agent executions
- **Features:**
  - Compliance bundle verification and signing
  - Audit export hardening
  - Evidence bundle schema validation
- **Acceptance:** Teams can export and verify evidence bundles for compliance

#### H5-003: Regression Test Suite
- **Requirement:** Comprehensive regression tests for prompt/runtime/model changes
- **Features:**
  - Deterministic test fixtures
  - Baseline performance metrics
  - Automated diff detection
- **Acceptance:** Regression suite catches degradations before release

### H6: Packaging and Adoption

#### H6-001: Desktop/Client-Server Packaging
- **Requirement:** Packaged launch artifacts for multiple platforms
- **Features:**
  - Desktop application packages (macOS, Windows, Linux)
  - Client-server distribution
  - Cross-platform build automation
- **Acceptance:** Users can install TeaAgent via package managers or download

#### H6-002: SBOM and Binary Signing
- **Requirement:** Supply-chain security for packaged artifacts
- **Features:**
  - Software Bill of Materials (SBOM) generation
  - Binary signing with verifiable keys
  - Dependency vulnerability scanning
- **Acceptance:** Packages are signed and include SBOM for verification

#### H6-003: Update Mechanism
- **Requirement:** Secure, rollback-capable update process
- **Features:**
  - Automatic update checks
  - Delta updates for efficiency
  - Rollback capability on failure
- **Acceptance:** Users can update safely with rollback option

#### H6-004: Session Attach
- **Requirement:** Users can attach to running sessions across restarts
- **Features:**
  - Session persistence and recovery
  - Cross-device session continuity
  - Session state synchronization
- **Acceptance:** Users can resume sessions after client restarts

## Non-Functional Requirements

### Performance
- TUI cockpit refresh rate: < 500ms for state updates
- Background run overhead: < 5% CPU impact
- Eval suite execution: < 30 minutes for full regression

### Security
- Evidence bundles must be cryptographically signed
- Role-based access control enforced at all policy boundaries
- Audit trail immutable for compliance requirements

### Reliability
- Background runs must survive process restarts
- Update mechanism must support rollback
- Control-plane must remain available during agent failures

### Usability
- TUI cockpit must be navigable without documentation
- Installation process must be < 5 minutes
- Error messages must include actionable remediation steps

## Edge Cases

### H4 Edge Cases
- **Tenant isolation breach:** Detect and block cross-tenant data access
- **Policy conflict:** Resolve conflicting routing rules with deterministic precedence
- **Background worker death:** Detect and restart failed background workers
- **Cost envelope exhaustion:** Block new work when budget exceeded

### H5 Edge Cases
- **Eval timeout:** Handle long-running evals with timeout and partial results
- **Baseline drift:** Detect and alert when test baselines become stale
- **Evidence bundle corruption:** Validate bundle integrity before export
- **Regression false positives:** Allow exception process for known acceptable changes

### H6 Edge Cases
- **Update failure:** Automatic rollback on update failure
- **Signature verification failure:** Block installation of unsigned packages
- **SBOM generation failure:** Fail build if SBOM cannot be generated
- **Cross-platform incompatibility:** Detect and block platform-specific issues

## Failure Modes

### H4 Failure Modes
- **Control-plane unavailable:** Fallback to CLI for emergency operations
- **Policy engine crash:** Fail-closed (block all actions) until recovery
- **Background queue overflow:** Reject new work with clear error message
- **Cost tracking corruption:** Rebuild from audit logs on detection

### H5 Failure Modes
- **Eval suite crash:** Block release until evals pass
- **Evidence bundle signing failure:** Fail release if signing unavailable
- **Regression test flakiness:** Quarantine flaky tests, require manual review
- **Baseline corruption:** Restore from version-controlled baselines

### H6 Failure Modes
- **Package build failure:** Block release until build succeeds
- **Update server unavailable:** Continue with current version, retry later
- **Signature key compromise:** Revoked key mechanism, emergency re-signing process
- **Installation corruption:** Validation on startup, re-download if corrupted

## Resolved Design Decisions

1. **H4 Collaboration Policies**: Tenant-specific. All policy files, routing configurations, and consensus rules are stored and isolated within each tenant's respective storage path (`.teaagent/tenants/{tenant_id}/policies/`).
2. **H5 Regression Thresholds**: The acceptable regression threshold is set at a maximum of 10% compared to the baseline run metrics. Exceeding this limit automatically blocks the release pipeline.
3. **H6 Package Managers**: Initial packaging support will prioritize `Homebrew` (macOS), `apt` (Linux), and standard zip/tarball archives for Windows.
4. **Cross-Horizon Integration**: Yes. Cost logs and budget allocation details from H4 must be bundled into H5 compliance evidence exports to allow comprehensive cost audits.

## Dependencies

### H4 Dependencies
- H3 complete (ecosystem trust foundations)
- Multi-tenant partitioning (already complete)
- Existing TUI foundation

### H5 Dependencies
- H4 complete (cost attribution needed for evidence bundles)
- Existing repo-map benchmark script
- Existing audit export script

### H6 Dependencies
- H5 complete (eval-gated releases needed for stable packages)
- Existing build infrastructure
- Code signing infrastructure

## Risks

### H4 Risks
- **Policy complexity:** Overly complex collaboration policies may be unusable
- **Performance impact:** Background durability may add significant overhead
- **Multi-tenant security:** Tenant isolation bugs could cause data leaks

### H5 Risks
- **Eval false positives:** Overly strict evals may block valid improvements
- **Maintenance burden:** Regression suite requires ongoing maintenance
- **Evidence bundle size:** Large bundles may be impractical for compliance

### H6 Risks
- **Platform fragmentation:** Supporting multiple platforms increases maintenance
- **Supply-chain attacks:** Compromised build infrastructure could distribute malware
- **Update rollbacks:** Rollback mechanism may fail in some scenarios

## Success Metrics

### H4 Success Metrics
- TUI cockpit adoption rate: > 80% of team operators
- Background run success rate: > 99.5%
- Policy enforcement violations: < 0.1% of runs

### H5 Success Metrics
- Eval suite execution time: < 30 minutes
- Regression detection rate: > 95% of degradations
- Evidence bundle verification time: < 5 seconds

### H6 Success Metrics
- Package installation success rate: > 98%
- Update success rate: > 99%
- Time to install: < 5 minutes

## Definition of Done

Each horizon is complete when:
- All functional requirements are implemented
- All acceptance criteria are met
- All edge cases are handled
- All failure modes have recovery procedures
- Success metrics are measured and meet targets
- Documentation is updated
- Tests pass (including acceptance tests)
- Security review is complete
