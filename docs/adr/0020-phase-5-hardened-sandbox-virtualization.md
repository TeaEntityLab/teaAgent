# ADR 0020: Phase 5 - Hardened Sandbox Virtualization

## Status

Accepted and Implemented (Beta) - 2026-05-27 to 2026-05-29

## Context

The TeaAgent multi-agent system required hardened sandbox virtualization to ensure safe execution of untrusted code and skills. The initial isolation support (ADR 0003) provided basic code mode sandboxing, but lacked:

1. **Docker resource limits** - No CPU/memory constraints on containerized execution
2. **WASM runtime support** - No lightweight sandboxing for skills
3. **Skill routing** - No automatic sandbox selection based on risk level
4. **Resource monitoring** - No real-time tracking of container resource usage
5. **Cognitive swarm evolution** - No self-healing validation or cross-sandbox Delta sharing
6. **Remote JIT approval** - No SSE-based approval server with timeout

These gaps created security risks where untrusted code could consume unlimited resources, skills could not be safely isolated, and there was no visibility into resource usage or execution safety.

## Decision

Implement comprehensive hardened sandbox virtualization with multiple isolation modes and resource management:

### Core Components

#### 1. Docker Resource Limits (TASK-007)

**Implementation:**
- Added `cpu_quota` and `memory_limit` fields to `IsolationContext`
- Extended `prepare_subagent_isolation` to accept resource limit parameters
- Modified Docker container creation to include `--cpus` and `--memory` flags
- Resource limits are optional and backward compatible
- Logging for configured resource limits

**Files:**
- `teaagent/subagents/_isolation.py` (49 lines modified)

**Features:**
- CPU quota control via `--cpus` flag
- Memory limit control via `--memory` flag
- Backward compatible (limits are optional)
- Only applied to Docker isolation mode

**Tests:**
- `tests/test_subagent_isolation.py` (74 lines added, 3 new tests)

#### 2. WASM Runtime Wrapper (TASK-008)

**Implementation:**
- `WASMRuntime` class with wasmer integration for lightweight sandboxing
- Skill compatibility checking (detects async/await, socket, subprocess, eval/exec)
- Optional dependency on wasmer via `teaagent[wasm]` extra
- Dummy types for type checking when wasmer is not installed

**Files:**
- `teaagent/wasm_runtime.py` (222 lines)

**Features:**
- Lightweight sandboxing via WebAssembly
- Automatic skill compatibility detection
- Graceful degradation when wasmer is not installed
- Type-safe dummy types for optional dependency

**Tests:**
- `tests/test_wasm_runtime.py` (130 lines, 7 tests)

#### 3. Skill Execution Routing (TASK-009)

**Implementation:**
- `SkillRouter` for automatic sandbox selection based on risk level
- `RoutingDecision` with reasoning and warnings
- Support for user-preferred sandbox override
- Integration of WASM compatibility checks into routing logic
- Auto-selection: low-risk→directory-snapshot, medium-risk→Docker, high-risk→WASM/Docker

**Files:**
- `teaagent/skill_router.py` (245 lines)

**Features:**
- Automatic sandbox selection based on risk level
- User-preferred sandbox override support
- WASM compatibility checking
- Routing decision reasoning and warnings
- Configurable routing policies

**Tests:**
- `tests/test_skill_router.py` (144 lines, 10 tests)

#### 4. Resource Monitoring (TASK-010)

**Implementation:**
- `ResourceMonitor` for Docker container resource tracking
- Real-time CPU and memory usage monitoring via Docker stats
- Violation detection with severity levels (warning/critical)
- `monitor_container()` function for duration-based monitoring

**Files:**
- `teaagent/resource_monitor.py` (288 lines)

**Features:**
- Real-time CPU and memory monitoring
- Violation detection with severity levels
- Duration-based monitoring
- Docker stats integration
- Configurable thresholds

**Tests:**
- `tests/test_resource_monitor.py` (201 lines, 12 tests)

#### 5. CLI Commands for Sandbox (TASK-011)

**Implementation:**
- `sandbox route` command for skill routing with configuration display
- `sandbox monitor` command for container resource monitoring
- `sandbox check wasm` command for WASM availability check
- `sandbox check compatibility` command for skill WASM compatibility
- Sandbox CLI argument parsers
- Integration into main CLI

**Files:**
- `teaagent/cli/_sandbox_parsers.py` (127 lines)
- `teaagent/cli/_handlers/_sandbox.py` (140 lines)

**CLI Commands:**
- `teaagent sandbox route <skill_path>` - Route skill to appropriate sandbox
- `teaagent sandbox monitor <container_id>` - Monitor container resources
- `teaagent sandbox check wasm` - Check WASM availability
- `teaagent sandbox check compatibility <skill_path>` - Check skill WASM compatibility

**Tests:**
- `tests/test_sandbox_cli.py` (160 lines, 8 tests)

#### 6. Cognitive Swarm Evolution

**Implementation:**
- Self-healing validation loops with ruff/mypy/pytest
- Cross-sandbox Delta sharing with WAL-mode SQLite
- Evolutionary prompt self-tuning based on performance feedback
- Remote SSE JIT approval server with 3-minute timeout

**Files:**
- `teaagent/workflow_engine.py` (170 lines added)
- `teaagent/context_bus.py` (278 lines)
- `teaagent/agent_factory.py` (124 lines added)
- `teaagent/jit_approval_server.py` (328 lines)

**Features:**
- Self-healing validation with automatic hot-reload and re-execution (max 3 attempts)
- Cross-sandbox Delta sharing via WAL-mode SQLite for concurrent access
- Evolutionary prompt tuning with LLM and heuristic fallback
- Remote SSE JIT approval with 3-minute timeout and safe abort

**Tests:**
- `tests/test_phase5_workflow_engine.py` (91 lines, 9 tests)
- `tests/test_phase5_context_bus.py` (195 lines, 7 tests)
- `tests/test_phase5_agent_factory.py` (65 lines, 3 tests)
- `tests/test_phase5_jit_approval_server.py` (251 lines, 10 tests)

### Configuration

**IsolationContext:**
```python
@dataclass
class IsolationContext:
    isolation: IsolationMode
    root: str
    cpu_quota: Optional[float] = None  # CPU quota (e.g., 2.0 for 2 CPUs)
    memory_limit: Optional[str] = None  # Memory limit (e.g., "512m")
```

**Routing Policies:**
- Low-risk skills → directory-snapshot isolation
- Medium-risk skills → Docker isolation
- High-risk skills → WASM or Docker isolation
- User override via `--isolation` flag

**Resource Thresholds:**
- CPU warning: 80% of quota
- CPU critical: 95% of quota
- Memory warning: 80% of limit
- Memory critical: 95% of limit

## Implementation Timeline

**2026-05-28 17:21:48 +0800** - Docker resource limits
- Commit: `277be6afb20733e85d3ed54c704b9d9fa4cf03fd`
- Files: `teaagent/subagents/_isolation.py`
- Tests: 3 new tests for Docker resource limits

**2026-05-28 17:32:26 +0800** - Hardened sandbox virtualization
- Commit: `98009ed8e337149155a1a95faf741cd2375f68b7`
- Files: WASM runtime, skill router, resource monitor, sandbox CLI
- Tests: 37 new tests across WASM runtime, skill routing, resource monitoring, and sandbox CLI

**2026-05-28 19:43:42 +0800** - Cognitive swarm evolution
- Commit: `3a101b230a461f6d7755124aabfc58fa0288ef43`
- Files: workflow engine, context bus, agent factory, JIT approval server
- Tests: 29 new tests across 4 test files

**2026-05-28 22:36:09 +0800** - Docker preflight fallback and Phase 6 sandbox tests
- Commit: `548c6e734b84d37df9634ca0b1dcbb849a91ddc0`

**2026-05-28 23:07:31 +0800** - Phase 6 control plane and complete sandbox tournament flows
- Commit: `4cea960213e5280af20e5049d501dcd49c5912d7`

**2026-05-29 13:20:30 +0800** - Ship Phase 4 consensus gate and Phase 5 skill sandbox routing
- Commit: `2b94b1d0b6180936216bfbf09b0dc351d854c2df`

**2026-05-29 13:35:51 +0800** - Ship remaining Phase 4-6 hardening: skill execution, async consensus, docker CI
- Commit: `6a518a097295dee9c7951e3145fa405b5a51232e`

**2026-05-29 14:44:07 +0800** - Add SSH vote relay, WASM skill CI workflow, and multi-tenant control plane
- Commit: `a91ce31a5183eb84426999aec1c85a0f8b0dec6b`

## Git History

**Key Commits:**
- `277be6afb20733e85d3ed54c704b9d9fa4cf03fd` (2026-05-28 17:21:48) - "feat: Implement Phase 5 Docker resource limits"
- `98009ed8e337149155a1a95faf741cd2375f68b7` (2026-05-28 17:32:26) - "feat: Implement Phase 5 Hardened Sandbox Virtualization"
- `3a101b230a461f6d7755124aabfc58fa0288ef43` (2026-05-28 19:43:42) - "feat: Implement Phase 5 Cognitive Swarm Evolution"
- `548c6e734b84d37df9634ca0b1dcbb849a91ddc0` (2026-05-28 22:36:09) - "Add Docker preflight fallback and Phase 6 sandbox tests"
- `4cea960213e5280af20e5049d501dcd49c5912d7` (2026-05-28 23:07:31) - "Add Phase 6 control plane and complete sandbox tournament flows"
- `2b94b1d0b6180936216bfbf09b0dc351d854c2df` (2026-05-29 13:20:30) - "Ship Phase 4 consensus gate and Phase 5 skill sandbox routing"
- `6a518a097295dee9c7951e3145fa405b5a51232e` (2026-05-29 13:35:51) - "Ship remaining Phase 4-6 hardening: skill execution, async consensus, docker CI"
- `a91ce31a5183eb84426999aec1c85a0f8b0dec6b` (2026-05-29 14:44:07) - "Add SSH vote relay, WASM skill CI workflow, and multi-tenant control plane"

**Implementation Files:**
- `teaagent/subagents/_isolation.py` - Docker resource limits (49 lines modified)
- `teaagent/wasm_runtime.py` - WASM runtime wrapper (222 lines)
- `teaagent/skill_router.py` - Skill execution routing (245 lines)
- `teaagent/resource_monitor.py` - Resource monitoring (288 lines)
- `teaagent/cli/_sandbox_parsers.py` - Sandbox CLI parsers (127 lines)
- `teaagent/cli/_handlers/_sandbox.py` - Sandbox CLI handlers (140 lines)
- `teaagent/workflow_engine.py` - Self-healing validation (170 lines added)
- `teaagent/context_bus.py` - Cross-sandbox Delta sharing (278 lines)
- `teaagent/agent_factory.py` - Evolutionary prompt tuning (124 lines added)
- `teaagent/jit_approval_server.py` - Remote JIT approval server (328 lines)

**Test Files:**
- `tests/test_subagent_isolation.py` - Docker resource limits tests (74 lines added, 3 tests)
- `tests/test_wasm_runtime.py` - WASM runtime tests (130 lines, 7 tests)
- `tests/test_skill_router.py` - Skill routing tests (144 lines, 10 tests)
- `tests/test_resource_monitor.py` - Resource monitoring tests (201 lines, 12 tests)
- `tests/test_sandbox_cli.py` - Sandbox CLI tests (160 lines, 8 tests)
- `tests/test_phase5_workflow_engine.py` - Self-healing validation tests (91 lines, 9 tests)
- `tests/test_phase5_context_bus.py` - Context bus tests (195 lines, 7 tests)
- `tests/test_phase5_agent_factory.py` - Evolutionary prompt tuning tests (65 lines, 3 tests)
- `tests/test_phase5_jit_approval_server.py` - JIT approval server tests (251 lines, 10 tests)

## Consequences

**Positive:**
- Docker resource limits prevent resource exhaustion
- WASM runtime provides lightweight sandboxing for skills
- Automatic skill routing based on risk level
- Real-time resource monitoring with violation detection
- Self-healing validation with automatic hot-reload
- Cross-sandbox Delta sharing for collaborative execution
- Evolutionary prompt tuning for performance optimization
- Remote JIT approval with timeout support
- Comprehensive test coverage (66 new tests)

**Negative:**
- Increased complexity in sandbox management
- Additional operational overhead for resource monitoring
- WASM runtime is optional and gracefully degrades
- Resource monitoring only works with Docker containers
- Context bus requires WAL-mode SQLite for concurrent access
- JIT approval server requires SSE support

**Risk:**
- Medium - sandbox virtualization affects subagent execution paths
- Mitigated by comprehensive unit and acceptance tests
- Graceful degradation for optional dependencies (WASM)
- Backward compatible configuration (resource limits are optional)
- Gradual rollout with feature flags for breaking changes

## Alternatives Considered

1. **Keep basic isolation without resource limits** - Rejected due to resource exhaustion risks
2. **Use external sandbox framework (gVisor, Firecracker)** - Rejected as over-engineering for this use case
3. **Implement only Docker limits without WASM** - Rejected as incomplete coverage
4. **Defer sandbox hardening to later phases** - Rejected as security risk for untrusted code

## References

- [ADR 0003: P2 Code Mode Sandbox](0003-p2-code-mode-sandbox.md)
- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)
- [ADR 0019: Phase 4 - Federated Swarm Consensus](0019-phase-4-federated-swarm-consensus.md)
- [Architecture - Phase 4-5 Roadmap](../architecture.md#phase-4-5-roadmap-beta)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Backlog Priority](../backlog-priority.md)

## Verification Commands

```bash
# Docker resource limits
pytest tests/test_subagent_isolation.py -v

# WASM runtime
pytest tests/test_wasm_runtime.py -v
teaagent sandbox check wasm

# Skill routing
pytest tests/test_skill_router.py -v
teaagent sandbox route <skill_path>
teaagent sandbox check compatibility <skill_path>

# Resource monitoring
pytest tests/test_resource_monitor.py -v
teaagent sandbox monitor <container_id>

# Sandbox CLI
pytest tests/test_sandbox_cli.py -v

# Cognitive swarm evolution
pytest tests/test_phase5_workflow_engine.py -v
pytest tests/test_phase5_context_bus.py -v
pytest tests/test_phase5_agent_factory.py -v
pytest tests/test_phase5_jit_approval_server.py -v

# Acceptance tests
pytest tests/acceptance/test_sandbox_enhancement_flow.py -v
```

## Post-Implementation Notes (2026-05-29)

Phase 5 hardened sandbox virtualization is now in Beta with CLI, unit tests, and E2E acceptance. The system provides Docker resource limits, WASM runtime support, automatic skill routing, real-time resource monitoring, self-healing validation, cross-sandbox Delta sharing, evolutionary prompt tuning, and remote JIT approval. Remaining Beta work includes native WASM modules and deeper tournament benchmarks. WASM runtime is optional and gracefully degrades when wasmer is not installed. Resource monitoring only works with Docker containers. Context bus requires WAL-mode SQLite for concurrent access.
