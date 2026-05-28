# TeaAgent Next-Generation Task Plan

## Phase 4: Federated Swarm Consensus & Peer Attestations

### TASK-001: Consensus Data Structures
- **Goal**: Define core data structures for consensus system
- **Scope**: Create models for peers, votes, proposals, and consensus state
- **Inputs**: None (new feature)
- **Outputs**: `teaagent/consensus.py` with dataclasses for consensus entities
- **Dependencies**: None
- **Acceptance Criteria**:
  - Peer model with SSH key identity
  - Vote model with signature and timestamp
  - Proposal model with risk classification
  - Consensus state model with voting status
  - All models are type-annotated and mypy-clean
- **Tests**: Unit tests for data model validation and serialization
- **Files likely touched**: `teaagent/consensus.py`, `tests/test_consensus.py`
- **Risk**: Low (data structures only)
- **Parallelizable**: Yes
- **Human Review Required**: No

### TASK-002: Peer Identity Management
- **Goal**: Implement peer registration and SSH key verification
- **Scope**: Add peer CRUD operations with cryptographic verification
- **Inputs**: SSH public keys, peer metadata
- **Outputs**: Peer registry with signature verification
- **Dependencies**: TASK-001
- **Acceptance Criteria**:
  - Register peer with SSH public key
  - Verify peer identity using SSH signatures
  - List registered peers
  - Remove/revoke peers
  - Key rotation support
- **Tests**: Unit tests for peer operations, integration tests for signature verification
- **Files likely touched**: `teaagent/consensus.py`, `teaagent/swarm.py`
- **Risk**: Medium (cryptography involved)
- **Parallelizable**: No (depends on TASK-001)
- **Human Review Required**: Yes (security review)

### TASK-003: Voting Mechanism
- **Goal**: Implement voting logic for proposals
- **Scope**: Add vote collection, aggregation, and threshold checking
- **Inputs**: Proposals, peer votes
- **Outputs**: Voting results with quorum determination
- **Dependencies**: TASK-001, TASK-002
- **Acceptance Criteria**:
  - Collect votes from peers
  - Aggregate votes by proposal
  - Check voting thresholds (majority, supermajority, unanimous)
  - Handle timeout scenarios
  - Support vote cancellation
- **Tests**: Unit tests for voting logic, integration tests for quorum scenarios
- **Files likely touched**: `teaagent/consensus.py`
- **Risk**: Medium (consensus logic correctness)
- **Parallelizable**: No (depends on TASK-001, TASK-002)
- **Human Review Required**: Yes (logic review)

### TASK-004: Consensus Engine
- **Goal**: Implement core consensus engine with state management
- **Scope**: Create consensus coordinator with state synchronization
- **Inputs**: Proposals, peer votes, configuration
- **Outputs**: Consensus decisions with attestation
- **Dependencies**: TASK-001, TASK-002, TASK-003
- **Acceptance Criteria**:
  - Coordinate consensus process
  - Manage consensus state machine
  - Generate attestation signatures
  - Handle conflict resolution
  - Provide consensus status API
- **Tests**: Unit tests for engine logic, integration tests for state transitions
- **Files likely touched**: `teaagent/consensus.py`
- **Risk**: High (core consensus logic)
- **Parallelizable**: No (depends on TASK-001, TASK-002, TASK-003)
- **Human Review Required**: Yes (critical path review)

### TASK-005: Swarm Integration
- **Goal**: Integrate consensus into existing swarm orchestration
- **Scope**: Add consensus checks before subagent launches
- **Inputs**: Swarm task requests
- **Outputs**: Consensus-gated task execution
- **Dependencies**: TASK-004
- **Acceptance Criteria**:
  - Check consensus before high-risk tool calls
  - Fallback to single-agent mode on consensus failure
  - Audit log consensus events
  - Support consensus bypass with manual approval
- **Tests**: Integration tests with existing swarm tests
- **Files likely touched**: `teaagent/swarm.py`, `teaagent/runner/_core.py`
- **Risk**: High (integration with existing system)
- **Parallelizable**: No (depends on TASK-004)
- **Human Review Required**: Yes (integration review)

### TASK-006: CLI Commands for Consensus
- **Goal**: Add CLI commands for consensus management
- **Scope**: Create CLI handlers for peer and consensus operations
- **Inputs**: CLI arguments
- **Outputs**: Interactive consensus management
- **Dependencies**: TASK-002, TASK-004
- **Acceptance Criteria**:
  - `teaagent swarm peers list/add/remove`
  - `teaagent swarm consensus status/history`
  - `teaagent swarm config set voting-threshold`
  - Clear error messages and help text
- **Tests**: CLI tests for all commands
- **Files likely touched**: `teaagent/cli/_handlers/_swarm.py`, `teaagent/cli/_swarm_parsers.py`
- **Risk**: Low (CLI only)
- **Parallelizable**: Yes (can be done in parallel with TASK-005)
- **Human Review Required**: No

## Phase 5: Hardened Sandbox Virtualization

### TASK-007: Docker Resource Limits
- **Goal**: Add CPU and memory resource constraints to Docker isolation
- **Scope**: Extend Docker container creation with resource limits
- **Inputs**: Resource limit configuration
- **Outputs**: Docker containers with enforced limits
- **Dependencies**: None (extends existing Docker isolation)
- **Acceptance Criteria**:
  - Configurable CPU quotas (shares, caps)
  - Configurable memory limits (soft, hard)
  - Container health monitoring
  - Resource usage tracking
  - Automatic cleanup on limit violation
- **Tests**: Unit tests for limit configuration, integration tests with Docker
- **Files likely touched**: `teaagent/subagents/_isolation.py`
- **Risk**: Medium (Docker API integration)
- **Parallelizable**: Yes (can start immediately)
- **Human Review Required**: Yes (Docker configuration review)

### TASK-008: WASM Runtime Wrapper
- **Goal**: Create lightweight WASM runtime for Python-compatible modules
- **Scope**: Implement WASM sandbox with memory isolation
- **Inputs**: WASM module binaries
- **Outputs**: Isolated WASM execution environment
- **Dependencies**: None (new feature)
- **Acceptance Criteria**:
  - WASM runtime initialization
  - Memory isolation enforcement
  - Controlled syscall filtering
  - Fast startup (< 100ms)
  - Graceful degradation if WASM unavailable
- **Tests**: Unit tests for runtime, integration tests with simple WASM modules
- **Files likely touched**: `teaagent/wasm_runtime.py`
- **Risk**: High (new runtime technology)
- **Parallelizable**: Yes (can start immediately)
- **Human Review Required**: Yes (security review)

### TASK-009: Skill Execution Routing
- **Goal**: Route skills to appropriate sandbox based on risk level
- **Scope**: Add sandbox selection logic to skill loader
- **Inputs**: Skill metadata, risk classification
- **Outputs**: Sandbox selection with fallback mechanisms
- **Dependencies**: TASK-007, TASK-008
- **Acceptance Criteria**:
  - Risk-based sandbox selection
  - Skill-level sandbox preferences
  - Fallback on sandbox failure
  - Compatibility checking before WASM
  - Audit log of sandbox choices
- **Tests**: Unit tests for routing logic, integration tests with skill loading
- **Files likely touched**: `teaagent/skill_loader.py`, `teaagent/subagents/_isolation.py`
- **Risk**: Medium (routing logic)
- **Parallelizable**: No (depends on TASK-007, TASK-008)
- **Human Review Required**: Yes (logic review)

### TASK-010: Resource Monitoring
- **Goal**: Implement real-time resource usage tracking
- **Scope**: Add monitoring for CPU, memory, and sandbox health
- **Inputs**: Sandbox execution events
- **Outputs**: Resource metrics and alerts
- **Dependencies**: TASK-007, TASK-008
- **Acceptance Criteria**:
  - Real-time resource usage tracking
  - Per-sandbox resource accounting
  - Alerting on resource violations
  - Historical resource reporting
  - Integration with audit log
- **Tests**: Unit tests for monitoring, integration tests with sandboxes
- **Files likely touched**: `teaagent/subagents/_isolation.py`, `teaagent/telemetry/`
- **Risk**: Low (monitoring only)
- **Parallelizable**: Yes (can be done in parallel with TASK-009)
- **Human Review Required**: No

### TASK-011: CLI Commands for Sandbox
- **Goal**: Add CLI commands for sandbox configuration and monitoring
- **Scope**: Create CLI handlers for sandbox operations
- **Inputs**: CLI arguments
- **Outputs**: Interactive sandbox management
- **Dependencies**: TASK-007, TASK-008, TASK-010
- **Acceptance Criteria**:
  - `teaagent isolation list`
  - `teaagent isolation configure docker/wasm`
  - `teaagent isolation status`
  - `teaagent skill run --sandbox`
  - Clear error messages and help text
- **Tests**: CLI tests for all commands
- **Files likely touched**: `teaagent/cli/_handlers/_isolation.py`, `teaagent/cli/_isolation_parsers.py`
- **Risk**: Low (CLI only)
- **Parallelizable**: Yes (can be done in parallel with TASK-009)
- **Human Review Required**: No

## Verification Tasks

### TASK-012: Consensus Integration Tests
- **Goal**: End-to-end testing of consensus system
- **Scope**: Full swarm workflow with consensus
- **Dependencies**: TASK-001 through TASK-006
- **Acceptance Criteria**:
  - Successful consensus vote
  - Consensus timeout handling
  - Peer unavailability handling
  - Audit log verification
- **Files likely touched**: `tests/acceptance/test_consensus_flow.py`
- **Risk**: Low (testing only)
- **Parallelizable**: No (depends on all Phase 4 tasks)
- **Human Review Required**: No

### TASK-013: Sandbox Integration Tests
- **Goal**: End-to-end testing of sandbox enhancements
- **Scope**: Full skill execution with enhanced sandboxes
- **Dependencies**: TASK-007 through TASK-011
- **Acceptance Criteria**:
  - Docker with resource limits
  - WASM skill execution
  - Resource limit violations
  - Fallback mechanisms
- **Files likely touched**: `tests/acceptance/test_sandbox_enhancement_flow.py`
- **Risk**: Low (testing only)
- **Parallelizable**: No (depends on all Phase 5 tasks)
- **Human Review Required**: No

### TASK-014: Documentation Updates
- **Goal**: Update documentation for new features
- **Scope**: Update CLI docs, API docs, and examples
- **Dependencies**: TASK-006, TASK-011
- **Acceptance Criteria**:
  - CLI documentation updated
  - API documentation updated
  - Usage examples added
  - Migration guide if needed
- **Files likely touched**: `docs/cli.md`, `docs/api.md`, `docs/USAGE.md`
- **Risk**: Low (documentation only)
- **Parallelizable**: Yes (can start after TASK-006, TASK-011)
- **Human Review Required**: No

## Execution Order

### Critical Path (Sequential)
1. TASK-001 → TASK-002 → TASK-003 → TASK-004 → TASK-005 (Phase 4 core)
2. TASK-007 → TASK-008 → TASK-009 (Phase 5 core)

### Parallelizable Tracks
- Track A: TASK-001, TASK-007, TASK-008 (can start immediately)
- Track B: TASK-006, TASK-010, TASK-011 (can start after dependencies)
- Track C: TASK-012, TASK-013, TASK-014 (verification phase)

### Estimated Timeline
- **Week 1**: TASK-001, TASK-002, TASK-007, TASK-008
- **Week 2**: TASK-003, TASK-004, TASK-009, TASK-010
- **Week 3**: TASK-005, TASK-006, TASK-011
- **Week 4**: TASK-012, TASK-013, TASK-014

## Risk Mitigation

### High-Risk Tasks
- **TASK-004 (Consensus Engine)**: Requires thorough code review and threat modeling
- **TASK-005 (Swarm Integration)**: Requires careful integration testing with existing swarm
- **TASK-008 (WASM Runtime)**: Requires security review and compatibility testing

### Rollback Strategy
- All features are additive (no breaking changes)
- Can disable consensus via config flag
- Can disable WASM via optional dependency
- Docker resource limits are opt-in via config

### Human Review Points
- TASK-002: Cryptography and peer identity
- TASK-003: Voting logic correctness
- TASK-004: Consensus engine design
- TASK-005: Swarm integration
- TASK-007: Docker configuration
- TASK-008: WASM security
- TASK-009: Routing logic
