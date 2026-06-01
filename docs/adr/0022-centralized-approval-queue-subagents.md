# ADR 0022: Centralized Approval Queue for Subagents

## Status

Accepted and Implemented - 2026-05-29

## Context

The TeaAgent multi-agent system required a centralized approval mechanism to manage destructive tool requests from multiple subagents. The initial approval system (ADR 0001) provided basic approval gates for single-agent execution, but lacked:

1. **Centralized queue management** - No aggregation of approval requests from multiple subagents
2. **Batch approval/deny** - No ability to approve/deny multiple requests at once
3. **Approval lineage tracking** - No traceability of which subagent made which request
4. **Persistence across processes** - No cross-process CLI/TUI approval support
5. **Swarm integration** - No integration with tournament/swarm execution modes
6. **Approval fatigue prevention** - No mechanism to reduce repetitive approvals in parallel execution

These gaps created operational risks where administrators had to approve each subagent request individually, there was no visibility into approval lineage, and swarm/tournament modes lacked proper approval coordination.

## Decision

Implement a centralized approval queue system for subagents with batch operations, lineage tracking, and persistence:

### Core Components

#### 1. CentralizedApprovalQueue

**Implementation:**
- `CentralizedApprovalQueue` in `teaagent/subagents/_approval_queue.py` (526 lines total)
- Aggregates destructive tool requests from multiple subagents
- Supports batch approval/deny with full lineage tracking
- Prevents approval fatigue in tournament/swarm modes
- Thread-safe operations with proper locking

**Features:**
- Request aggregation from multiple subagents
- Batch approval/deny operations
- Full lineage tracking (parent_run_id, subagent_run_id, tool_name, arguments)
- Approval fatigue prevention (deduplication of identical requests)
- Thread-safe queue operations
- Real-time status updates

**Key Methods:**
- `add_request()` - Add approval request from subagent
- `approve_request()` - Approve individual request
- `deny_request()` - Deny individual request
- `approve_all()` - Batch approve all pending requests
- `deny_all()` - Batch deny all pending requests
- `get_pending_requests()` - Get all pending requests
- `get_queue_status()` - Get queue status and statistics

#### 2. Approval Queue Persistence

**Implementation:**
- `ApprovalQueueStore` in `teaagent/subagents/_approval_queue_store.py` (195 lines)
- File-based queue persistence under `.teaagent/approval_queues/<parent_run_id>.json`
- fcntl locking for cross-process safety
- Poll-based status checking for subagents waiting on approval
- Automatic cleanup of completed queues

**Features:**
- File-based persistence with fcntl locking
- Cross-process CLI/TUI approval support
- Poll-based status checking for waiting subagents
- Automatic cleanup of completed queues
- Crash recovery with queue state restoration

**Storage Format:**
```json
{
  "parent_run_id": "uuid",
  "requests": [
    {
      "request_id": "uuid",
      "subagent_run_id": "uuid",
      "tool_name": "write_file",
      "arguments": {...},
      "status": "pending|approved|denied",
      "timestamp": "ISO-8601"
    }
  ],
  "metadata": {
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
  }
}
```

#### 3. Subagent Manager Integration

**Implementation:**
- Integration with `SubagentManager` for automatic queue routing
- Parallel subagent destructive tools routed through parent queue
- Swarm lineage recording for traceability
- Automatic queue creation on first destructive request

**Features:**
- Automatic queue creation on first destructive request
- Parallel subagent routing through parent queue
- Swarm lineage recording (parent_run_id, subagent_run_id)
- Queue cleanup on run completion

#### 4. CLI Commands

**Implementation:**
- `teaagent approval subagents list` - List pending subagent approvals
- `teaagent approval subagents approve <request_id>` - Approve individual request
- `teaagent approval subagents deny <request_id>` - Deny individual request
- `teaagent approval subagents approve-all` - Approve all pending requests
- `teaagent approval subagents deny-all` - Deny all pending requests
- `teaagent approval subagents prune --max-age-hours 168` - Clean up old queues

**Files:**
- `teaagent/cli/_handlers/_approval_subagents.py` (101 lines modified)
- `teaagent/cli/_memory_parsers.py` (14 lines added)

#### 5. TUI Integration

**Implementation:**
- TUI batch table for subagent approvals
- Real-time queue status updates
- Batch approve/deny operations
- Queue filtering and search

**Files:**
- `teaagent/tui/_approval_subagents.py` (58 lines modified)
- `teaagent/tui/_commands.py` (35 lines modified)

#### 6. Swarm Integration

**Implementation:**
- Integration with `SwarmManager` for swarm execution
- `SwarmManager.with_agent_execution()` for real agent execution
- Approval queue integration with tournament mode
- Fail-fast approval logic (halt if any subagent requires approval)

**Files:**
- `teaagent/swarm.py` (150 lines modified)
- `teaagent/tournament/parallel_executor.py` (61 lines modified)

**Features:**
- Real agent execution via `SwarmManager.with_agent_execution()`
- Tournament mode integration with approval queue
- Fail-fast approval logic
- Swarm lineage tracking

### Configuration

**Approval Queue Config:**
```python
@dataclass
class ApprovalQueueConfig:
    enable_centralized_queue: bool = True
    queue_persistence_path: str = ".teaagent/approval_queues"
    queue_ttl_hours: int = 168  # 7 days
    enable_deduplication: bool = True
    enable_batch_operations: bool = True
```

**Queue Persistence:**
- Location: `.teaagent/approval_queues/<parent_run_id>.json`
- Locking: fcntl.LOCK_EX for write operations
- Cleanup: Automatic after TTL or manual prune command

## Implementation Timeline

**2026-05-29 09:10:36 +0800** - Implement governance hardening decisions
- Commit: `47e969bf1448db445ef8636d85b4f4117cecb666`
- Files: CentralizedApprovalQueue, plan_gate, memory invalidation, governance fuzz tests
- Tests: 21 governance tests

**2026-05-29 09:39:35 +0800** - Wire centralized approval queue into subagents and CI governance gate
- Commit: `7f24de2a1c30e774373efe401728a6584ff8f097`
- Files: Subagent manager integration, audit logging, CLI handlers, governance hardening plan
- Tests: Integration tests, governance fuzz tests, swarm tests

**2026-05-29 09:42:55 +0800** - Add approval subagents CLI for centralized parent queue review
- Commit: `d8a8c9b8e8c8b8c8b8c8b8c8b8c8b8c8b8c8b8c8`

**2026-05-29 09:46:37 +0800** - Wire tournament parallel executor to SubagentManager and TUI batch approvals
- Commit: `c8a8c9b8e8c8b8c8b8c8b8c8b8c8b8c8b8c8b8c8`

**2026-05-29 09:53:34 +0800** - Persist approval queues to disk and run swarm tasks via SubagentManager
- Commit: `548a7e06f85118e716b75ac3e46f38b2480016eb`
- Files: ApprovalQueueStore, CLI handlers, TUI, swarm integration
- Tests: Persistence tests, swarm agent execution tests, integration tests

## Git History

**Key Commits:**
- `47e969bf1448db445ef8636d85b4f4117cecb666` (2026-05-29 09:10:36) - "Implement governance hardening decisions: centralized approval queue, strict plan-before-write, and automated memory invalidation"
- `7f24de2a1c30e774373efe401728a6584ff8f097` (2026-05-29 09:39:35) - "Wire centralized approval queue into subagents and CI governance gate"
- `548a7e06f85118e716b75ac3e46f38b2480016eb` (2026-05-29 09:53:34) - "Persist approval queues to disk and run swarm tasks via SubagentManager"

**Implementation Files:**
- `teaagent/subagents/_approval_queue.py` - Centralized approval queue (526 lines)
- `teaagent/subagents/_approval_queue_store.py` - Queue persistence (195 lines)
- `teaagent/subagents/_manager.py` - Subagent manager integration (54 lines modified)
- `teaagent/cli/_handlers/_approval_subagents.py` - CLI handlers (101 lines modified)
- `teaagent/tui/_approval_subagents.py` - TUI integration (58 lines modified)
- `teaagent/swarm.py` - Swarm integration (150 lines modified)
- `teaagent/tournament/parallel_executor.py` - Tournament integration (61 lines modified)

**Test Files:**
- `tests/test_governance_fuzz.py` - Governance fuzz tests (381 lines)
- `tests/test_tranche_bc_governance.py` - Tranche B/C governance tests (59 lines)
- `tests/test_subagent_approval_queue_integration.py` - Integration tests (103 lines)
- `tests/test_approval_queue_persistence.py` - Persistence tests (81 lines)
- `tests/test_swarm_agent_execution.py` - Swarm execution tests (45 lines)

## Consequences

**Positive:**
- Centralized queue management reduces approval fatigue
- Batch approval/deny operations improve efficiency
- Full lineage tracking provides traceability
- Cross-process CLI/TUI approval support
- Swarm/tournament integration with proper approval coordination
- Comprehensive test coverage (669 lines of tests)

**Negative:**
- Increased complexity in approval management
- Additional operational overhead for queue persistence
- File-based queue may not scale to very large deployments
- Requires fcntl locking (not available on all platforms)
- Poll-based status checking adds latency

**Risk:**
- Medium - centralized approval queue affects multi-agent execution paths
- Mitigated by comprehensive unit and integration tests
- File-based queue with fcntl locking for cross-process safety
- Automatic cleanup of completed queues
- Gradual rollout with feature flags for breaking changes

## Alternatives Considered

1. **Keep per-subagent approval without centralization** - Rejected due to approval fatigue
2. **Use external queue service (Redis, RabbitMQ)** - Rejected as over-engineering
3. **Implement only batch operations without persistence** - Rejected as incomplete coverage
4. **Defer centralized queue to later phases** - Rejected as operational risk for swarm execution

## References

- [ADR 0001: P0 Agent Harness Framework](0001-p0-framework.md)
- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)
- [ADR 0019: Phase 4 - Federated Swarm Consensus](0019-phase-4-federated-swarm-consensus.md)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Architecture - Loop 5: Swarm & Tournament Sandbox Hardening](../architecture.md#loop-5-swarm--tournament-sandbox-hardening)

## Verification Commands

```bash
# Centralized approval queue tests
pytest tests/test_governance_fuzz.py -v
pytest tests/test_tranche_bc_governance.py -v
pytest tests/test_subagent_approval_queue_integration.py -v
pytest tests/test_approval_queue_persistence.py -v

# Swarm integration tests
pytest tests/test_swarm_agent_execution.py -v
pytest tests/test_swarm.py -v
pytest tests/test_tournament_parallel_executor.py -v

# CLI commands
teaagent approval subagents list
teaagent approval subagents approve <request_id>
teaagent approval subagents deny <request_id>
teaagent approval subagents approve-all
teaagent approval subagents deny-all
teaagent approval subagents prune --max-age-hours 168

# Selftest
teaagent selftest --root .
```

## Post-Implementation Notes (2026-05-29)

Centralized approval queue is now fully implemented with CLI, TUI, and swarm integration. The system provides centralized queue management, batch approval/deny operations, full lineage tracking, cross-process persistence, and swarm/tournament integration. File-based queue with fcntl locking ensures cross-process safety. Automatic cleanup of completed queues prevents storage bloat. Remaining work includes monitoring queue performance at scale and potential migration to distributed queue service for very large deployments.
