# ADR 0019: Phase 4 - Federated Swarm Consensus & Peer Attestations

## Status

Accepted and Implemented (Beta) - 2026-05-27 to 2026-05-29

## Context

The TeaAgent multi-agent system required a federated consensus mechanism to enable safe distributed execution across multiple agents and peers. The initial multi-agent support (ADR 0001 Post-Implementation) provided basic A2A HTTP discovery and routing, but lacked:

1. **Peer identity management** - No secure peer registration and authentication
2. **Voting mechanisms** - No structured proposal voting and quorum coordination
3. **Attestation trails** - No cryptographic proof of consensus decisions
4. **Swarm pre-approval gates** - No automatic consensus checking for high-risk tasks
5. **Peer attestation** - No verification of peer identity and signature verification

These gaps created security risks where distributed execution could not be trusted, high-risk tasks could execute without proper approval, and there was no audit trail of consensus decisions.

## Decision

Implement a comprehensive federated swarm consensus system with peer attestation support:

### Core Components

#### 1. Consensus Data Structures (TASK-001)

**Implementation:**
- `PeerIdentity` with SSH key fingerprinting and signature verification
- `Vote`, `Proposal`, and `ConsensusState` data models
- `VotingThreshold` and `RiskLevel` enums
- `ConsensusConfig` for system configuration
- Full serialization support for all models

**Files:**
- `teaagent/consensus.py` (1005 lines)

#### 2. Peer Identity Management (TASK-002)

**Implementation:**
- `PeerRegistry` for managing peer identities
- CRUD operations for peers (register, unregister, activate, deactivate)
- SSH key rotation support
- Persistent storage to JSON
- Signature verification through registry

**Features:**
- Peer registration with SSH key fingerprinting
- Peer activation/deactivation for availability management
- Key rotation without breaking existing attestations
- JSON persistence for peer registry state

#### 3. Voting Mechanism (TASK-003)

**Implementation:**
- `VotingMechanism` for managing proposal voting
- Vote casting with duplicate prevention
- Vote cancellation support
- Timeout handling for proposals
- Automatic voting completion detection
- Cleanup of completed voting states

**Features:**
- Proposal creation with risk level classification
- Vote casting with signature verification
- Duplicate vote prevention
- Configurable voting thresholds (simple majority, supermajority, unanimous)
- Automatic timeout and cleanup

#### 4. Consensus Engine (TASK-004)

**Implementation:**
- `ConsensusEngine` coordinating voting and attestation
- Request consensus with automatic peer selection
- Vote submission with signature verification
- Attestation generation for approved proposals
- Conflict resolution support
- State persistence to storage

**Features:**
- Automatic peer selection based on task risk level
- Vote submission with cryptographic verification
- Attestation generation for approved proposals
- Conflict resolution for competing proposals
- Persistent state management

#### 5. Swarm Integration (TASK-005)

**Implementation:**
- Consensus mode in `SwarmManager` with enable/disable methods
- Extended `SubagentTask` with `risk_level` and `require_consensus` fields
- Automatic consensus checking for high-risk tasks
- Task filtering based on consensus results
- Fallback to single-agent mode when consensus fails

**Files:**
- `teaagent/swarm.py` (112 lines added)

**Features:**
- Automatic consensus checking for high-risk tasks
- Task filtering based on consensus results
- Fallback to single-agent mode when consensus fails
- Integration with existing swarm execution

#### 6. CLI Commands for Consensus (TASK-006)

**Implementation:**
- Consensus CLI handlers for peer management (list, add, remove, activate, deactivate)
- Consensus status and history commands
- Consensus configuration management
- Consensus request and vote commands
- Consensus argument parsers
- Integration into main CLI

**Files:**
- `teaagent/cli/_consensus_parsers.py` (136 lines)
- `teaagent/cli/_handlers/_consensus.py` (259 lines)

**CLI Commands:**
- `teaagent consensus peers list` - List registered peers
- `teaagent consensus peers add` - Add new peer
- `teaagent consensus peers remove` - Remove peer
- `teaagent consensus peers activate` - Activate peer
- `teaagent consensus peers deactivate` - Deactivate peer
- `teaagent consensus status` - Show consensus status
- `teaagent consensus history` - Show consensus history
- `teaagent consensus request` - Request consensus for proposal
- `teaagent consensus vote` - Vote on proposal

#### 7. Cooragent Multi-Agent Integration

**Implementation:**
- `TaskCoordinator` for task classification and routing with LLM/heuristic fallback
- `AgentFactory` for dynamic agent generation with LLM-structured prompts
- `ToolPermissions` for tool safety classification and JIT approval
- `WorkflowEngine` for multi-step workflow execution with polish mode

**Files:**
- `teaagent/coordinator.py` (426 lines)
- `teaagent/agent_factory.py` (275 lines)
- `teaagent/tool_permissions.py` (292 lines)
- `teaagent/workflow_engine.py` (280 lines)

**Features:**
- Task classification by type (code_review, testing, documentation, etc.)
- Dynamic agent generation with LLM-structured system prompts
- Tool safety levels (safe, inspect, destructive) with safe defaults
- JIT approval for destructive tool access
- Multi-step workflow planning and execution
- Polish mode with hot-reload and unified diff display

### Configuration

**ConsensusConfig:**
```python
@dataclass
class ConsensusConfig:
    enable_pre_approval: bool = False
    async_vote_collection: bool = False
    voting_timeout_seconds: int = 300
    min_peers_for_consensus: int = 3
    default_threshold: VotingThreshold = VotingThreshold.SIMPLE_MAJORITY
```

**Risk Levels:**
- `RiskLevel.LOW` - No consensus required
- `RiskLevel.MEDIUM` - Simple majority required
- `RiskLevel.HIGH` - Supermajority required
- `RiskLevel.CRITICAL` - Unanimous consent required

**Voting Thresholds:**
- `VotingThreshold.SIMPLE_MAJORITY` - >50% of active peers
- `VotingThreshold.SUPERMAJORITY` - ≥67% of active peers
- `VotingThreshold.UNANIMOUS` - 100% of active peers

## Implementation Timeline

**2026-05-28 17:15:48 +0800** - Consensus data structures and engine
- Commit: `e2361d9573ae7575a3682ec8bdd2bb428ce6a83d`
- Files: `teaagent/consensus.py` (1005 lines), `tests/test_consensus.py` (1190 lines)
- Tests: 59 unit tests covering all data structures, peer registry, voting, and consensus engine

**2026-05-28 17:20:01 +0800** - Swarm integration and consensus CLI
- Commit: `6e3934adb6207fc570e1a41d56631b8b60fce6b0`
- Files: CLI handlers, parsers, swarm integration
- Tests: 17 swarm tests (5 consensus integration), 11 consensus CLI tests

**2026-05-28 19:28:37 +0800** - Cooragent multi-agent integration
- Commit: `d55cd298aa3ce94acc1ccc4cc5438693a44128e8`
- Files: coordinator, agent_factory, tool_permissions, workflow_engine
- Tests: 35 new tests across 4 test files

**2026-05-29 13:20:30 +0800** - Ship Phase 4 consensus gate and Phase 5 skill sandbox routing
- Commit: `2b94b1d0b6180966216bfbf09b0dc351d854c2df`

**2026-05-29 13:35:51 +0800** - Ship remaining Phase 4-6 hardening: skill execution, async consensus, docker CI
- Commit: `6a518a097295dee9c7951e3145fa405b5a51232e`

**2026-05-29 14:35:14 +0800** - Close Phase 4–6 maturity gaps with peer vote import, swarm dashboard, and comparator tournament
- Commit: `ef88c1b88004de6a3ddb56be8b4def7d00352a5b`

## Git History

**Key Commits:**
- `e2361d9573ae7575a3682ec8bdd2bb428ce6a83d` (2026-05-28 17:15:48) - "feat: Implement Phase 4 consensus data structures and engine"
- `6e3934adb6207fc570e1a41d56631b8b60fce6b0` (2026-05-28 17:20:01) - "feat: Implement Phase 4 swarm integration and consensus CLI"
- `d55cd298aa3ce94acc1ccc4cc5438693a44128e8` (2026-05-28 19:28:37) - "feat: Implement Cooragent multi-agent integration (Phase 4)"
- `2b94b1d0b6180966216bfbf09b0dc351d854c2df` (2026-05-29 13:20:30) - "Ship Phase 4 consensus gate and Phase 5 skill sandbox routing"
- `6a518a097295dee9c7951e3145fa405b5a51232e` (2026-05-29 13:35:51) - "Ship remaining Phase 4-6 hardening: skill execution, async consensus, docker CI"
- `ef88c1b88004de6a3ddb56be8b4def7d00352a5b` (2026-05-29 14:35:14) - "Close Phase 4–6 maturity gaps with peer vote import, swarm dashboard, and comparator tournament"

**Implementation Files:**
- `teaagent/consensus.py` - Core consensus engine (1005 lines)
- `teaagent/swarm.py` - Swarm integration (112 lines added)
- `teaagent/coordinator.py` - Task coordinator (426 lines)
- `teaagent/agent_factory.py` - Agent factory (275 lines)
- `teaagent/tool_permissions.py` - Tool permissions (292 lines)
- `teaagent/workflow_engine.py` - Workflow engine (280 lines)
- `teaagent/cli/_consensus_parsers.py` - CLI parsers (136 lines)
- `teaagent/cli/_handlers/_consensus.py` - CLI handlers (259 lines)

**Test Files:**
- `tests/test_consensus.py` - Consensus tests (1190 lines)
- `tests/test_consensus_cli.py` - Consensus CLI tests (228 lines)
- `tests/test_swarm.py` - Swarm tests (97 lines added)
- `tests/test_phase4_coordinator.py` - Coordinator tests (112 lines)
- `tests/test_phase4_agent_factory.py` - Agent factory tests (129 lines)
- `tests/test_phase4_tool_permissions.py` - Tool permissions tests (167 lines)
- `tests/test_phase4_workflow_engine.py` - Workflow engine tests (290 lines)

## Consequences

**Positive:**
- Secure peer identity management with SSH key fingerprinting
- Structured voting mechanisms with configurable thresholds
- Cryptographic attestation trails for consensus decisions
- Automatic consensus checking for high-risk tasks
- CLI tools for peer and consensus management
- Dynamic multi-agent coordination with fallback support
- Comprehensive test coverage (59 consensus tests, 35 integration tests)

**Negative:**
- Increased complexity in multi-agent coordination
- Additional operational overhead for peer management
- Configuration persistence not yet implemented (config is in-memory)
- Signature verification uses simplified hash-based approach (production should use proper SSH signing)
- JSON persistence for peer registry and consensus state (may need migration to SQLite/Postgres)

**Risk:**
- Medium - consensus system affects multi-agent execution paths
- Mitigated by comprehensive unit and acceptance tests
- Fallback to single-agent mode when consensus fails
- Gradual rollout with feature flags for breaking changes

## Alternatives Considered

1. **Keep basic A2A routing without consensus** - Rejected due to security risks
2. **Use external consensus framework (Raft, Paxos)** - Rejected as over-engineering for this use case
3. **Implement only peer management without voting** - Rejected as incomplete coverage
4. **Defer consensus to later phases** - Rejected as security risk for distributed execution

## References

- [ADR 0001: P0 Agent Harness Framework](0001-p0-framework.md) (Post-Implementation section)
- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)
- [Architecture - Phase 4-5 Roadmap](../architecture.md#phase-4-5-roadmap-beta)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Backlog Priority](../backlog-priority.md)

## Verification Commands

```bash
# Consensus tests
pytest tests/test_consensus.py -v
pytest tests/test_consensus_cli.py -v

# Swarm integration tests
pytest tests/test_swarm.py -v

# Phase 4 integration tests
pytest tests/test_phase4_coordinator.py -v
pytest tests/test_phase4_agent_factory.py -v
pytest tests/test_phase4_tool_permissions.py -v
pytest tests/test_phase4_workflow_engine.py -v

# Acceptance tests
pytest tests/acceptance/test_consensus_flow.py -v

# CLI commands
teaagent consensus peers list
teaagent consensus status
teaagent consensus history
```

## Post-Implementation Notes (2026-05-29)

Phase 4 consensus system is now in Beta with CLI, unit tests, and E2E acceptance. The system provides secure peer identity management, structured voting mechanisms, and cryptographic attestation trails for distributed multi-agent execution. Remaining Beta work includes native WASM modules and deeper tournament benchmarks. Configuration persistence should be migrated from JSON to SQLite/Postgres for production use. Signature verification should be upgraded from hash-based to proper SSH signing for production deployments.
