# TeaAgent Next-Generation Evolution Specification

## Problem Statement

TeaAgent has achieved excellent security, reliability, and telemetry foundations. The next evolutionary step requires:
1. **Multi-agent coordination**: Enable safe, auditable consensus for distributed agent swarms
2. **Hardened isolation**: Extend sandboxing with resource constraints and WASM for ultra-fast isolation

## Goals

### Phase 4: Federated Swarm Consensus & Peer Attestations
- Enable cryptographic peer-to-peer attestation for multi-agent swarms
- Implement voting mechanisms for high-risk tool calls
- Provide audit trail for consensus decisions
- Support SSH-based peer signatures

### Phase 5: Hardened Sandbox Virtualization
- Add CPU/memory resource constraints to Docker isolation
- Integrate WebAssembly runtime for fast, lightweight sandboxing
- Support untrusted dynamic skill execution in WASM
- Maintain backward compatibility with existing isolation modes

## Non-Goals

- Full blockchain integration (keep it lightweight)
- Complex smart contract execution
- Network-level peer discovery (use existing SSH infrastructure)
- Complete WASM standard compliance (focus on Python-compatible subset)

## Actors

- **Swarm Orchestrator**: Coordinates multiple agents and manages consensus
- **Peer Agent**: Individual agent in a swarm that can vote and attest
- **Consensus Engine**: Manages voting thresholds and agreement verification
- **Sandbox Manager**: Handles Docker and WASM isolation with resource limits
- **Skill Loader**: Loads and executes dynamic skills in appropriate sandboxes

## Inputs / Outputs

### Phase 4 Inputs
- SSH public keys for peer identity
- Tool call requests with risk classification
- Voting threshold configuration
- Consensus timeout settings

### Phase 4 Outputs
- Consensus decision (approved/rejected)
- Attestation signatures
- Audit log entries for consensus events
- Peer reputation scores

### Phase 5 Inputs
- Resource limit configurations (CPU quotas, memory limits)
- WASM module binaries
- Skill execution requests
- Container health check parameters

### Phase 5 Outputs
- Isolated execution results
- Resource usage metrics
- Sandbox health status
- Execution audit logs

## Functional Requirements

### Phase 4: Consensus System

#### FR-1: Peer Identity Management
- Peers must register with SSH public keys
- Peer identities must be cryptographically verifiable
- Support peer revocation and key rotation

#### FR-2: Voting Mechanism
- High-risk tool calls require quorum approval
- Voting must be time-bounded with configurable timeouts
- Support different voting thresholds (simple majority, supermajority, unanimous)

#### FR-3: Consensus Engine
- State synchronization across peers
- Vote aggregation and decision logic
- Conflict resolution for divergent votes
- Attestation signature generation

#### FR-4: Swarm Integration
- Consensus checks before parallel subagent launches
- Fallback to single-agent mode if consensus fails
- Audit trail for all consensus events

### Phase 5: Sandbox Enhancement

#### FR-5: Docker Resource Limits
- Configurable CPU quotas (shares, caps)
- Configurable memory limits (soft, hard)
- Container health monitoring
- Automatic cleanup on resource exhaustion

#### FR-6: WASM Runtime
- Lightweight WASM sandbox for Python-compatible modules
- Fast startup (< 100ms)
- Memory isolation
- Controlled syscalls

#### FR-7: Skill Execution Routing
- Route skills to appropriate sandbox based on risk level
- Support skill-level sandbox preferences
- Fallback mechanisms for sandbox failures

#### FR-8: Resource Monitoring
- Real-time resource usage tracking
- Per-sandbox resource accounting
- Alerting on resource violations

## Non-Functional Requirements

### NFR-1: Performance
- Consensus decisions within 5 seconds for small swarms (< 10 peers)
- WASM sandbox startup < 100ms
- Docker container startup < 2 seconds
- Minimal overhead for non-consensus operations

### NFR-2: Security
- Cryptographic verification of all peer signatures
- No privilege escalation in sandboxes
- Resource isolation enforcement
- Audit trail immutability

### NFR-3: Reliability
- Graceful degradation if consensus fails
- Automatic sandbox recovery
- No single point of failure in consensus

### NFR-4: Compatibility
- Backward compatible with existing isolation modes
- No breaking changes to existing swarm API
- Optional WASM dependency

## Edge Cases

### Phase 4 Edge Cases
- Peer network partition during voting
- Malicious peer submitting false signatures
- Timeout expiration before quorum reached
- Key rotation during active consensus
- Split-brain scenarios

### Phase 5 Edge Cases
- Resource limit configuration errors
- WASM module compilation failures
- Container OOM during execution
- Sandbox startup failures
- Resource exhaustion on host

## Failure Modes

### Phase 4 Failures
- **Consensus timeout**: Fallback to single-agent mode with audit log
- **Signature verification failure**: Reject vote, log incident
- **Peer unavailability**: Exclude from quorum calculation
- **Network partition**: Use last-known-good state, log partition event

### Phase 5 Failures
- **Docker unavailable**: Fallback to directory-snapshot isolation
- **WASM unavailable**: Use Docker or directory-snapshot
- **Resource limit exceeded**: Terminate sandbox, log resource violation
- **Container health check failure**: Restart container, log event

## Open Questions

1. Should consensus be mandatory for all swarm operations or only high-risk ones?
2. What is the default voting threshold for new swarms?
3. Should WASM support be required or optional?
4. How to handle peer reputation and trust scoring?
5. What is the maximum swarm size supported?
6. How to handle consensus in offline/air-gapped environments?
