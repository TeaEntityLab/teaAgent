# ADR 0021: Phase 6 - Skill Writer, Docker Monitor, Control Plane

## Status

Accepted and Implemented (Beta) - 2026-05-27 to 2026-05-29

## Context

The TeaAgent multi-agent system required advanced tooling for skill management, resource monitoring, and operational control. Phase 4-5 provided consensus and sandbox virtualization, but lacked:

1. **Skill writer pipeline** - No review-gated skill publish/discovery workflow
2. **Docker sandbox monitoring** - No resource polling and validation for Docker containers
3. **Control plane dashboard** - No HTML/SSE dashboard for workflow/focus/JIT approval
4. **Prompt tournament scoring** - No deterministic fitness scoring with success hard-gate
5. **Multi-tenant support** - No bearer tokens, mTLS, or tenant authorization

These gaps created operational risks where skills could not be safely published, Docker containers lacked monitoring, there was no visual interface for approval management, and multi-tenant deployments lacked proper authentication.

## Decision

Implement comprehensive Phase 6 tooling for skill management, resource monitoring, and operational control:

### Core Components

#### 1. Skill Writer Pipeline

**Implementation:**
- `SkillWriter` publish/review pipeline with review-gated publish/discovery
- Safe skill writer flow with validation and review checks
- Skill discovery with metadata indexing
- Review workflow with approval/rejection

**Files:**
- `teaagent/skill_writer.py` (150 lines total)

**Features:**
- Review-gated skill publishing
- Skill discovery with metadata
- Validation checks before publish
- Approval/rejection workflow
- Skill versioning

**Tests:**
- `tests/test_phase6_skill_writer.py` (31 lines, 4 tests)

#### 2. Docker Sandbox Monitoring

**Implementation:**
- `DockerSandbox` resource polling and validation
- Real-time resource usage tracking
- Sandbox validation checks
- Resource limit enforcement

**Files:**
- `teaagent/docker_sandbox.py` (89 lines modified)

**Features:**
- Resource polling for Docker containers
- Sandbox validation checks
- Resource limit enforcement
- Health monitoring

**Tests:**
- `tests/test_phase6_docker.py` (39 lines, 5 tests)

#### 3. Control Plane API

**Implementation:**
- `ControlPlaneAPI` HTTP server with workflow/focus/JIT endpoints
- HTML/SSE dashboard for JIT approve/reject
- Workflow tracking and focus management
- JIT approval server integration

**Files:**
- `teaagent/control_plane_api.py` (356 lines total)
- `teaagent/html_dashboard/app.js` (94 lines)
- `teaagent/html_dashboard/index.html` (35 lines)
- `teaagent/html_dashboard/styles.css` (125 lines)

**Features:**
- HTTP API for control plane operations
- HTML dashboard with SSE for real-time updates
- JIT approve/reject interface
- Workflow tracking
- Focus management

**Tests:**
- `tests/test_phase6_control_plane.py` (111 lines total, 11 tests)

#### 4. Prompt Tournament Fitness Scoring

**Implementation:**
- Deterministic swarm fitness scoring with success hard-gate
- Prompt gene pool persistence (`.teaagent/prompt_gene_pool.jsonl`)
- Fitness scoring with weighted metrics
- Tournament comparator integration

**Files:**
- `teaagent/swarm.py` (137 lines added)

**Features:**
- Deterministic fitness scoring
- Success hard-gate for tournament
- Prompt gene pool persistence
- Weighted comparator schema (tests 40%, performance 15%, lint 10%, diff size 10%, architectural fit 15%, security 10%)

**Tests:**
- `tests/test_phase6_swarm_score.py` (129 lines total, 12 tests)

#### 5. Control Plane CLI

**Implementation:**
- `control-plane serve` CLI command
- Control plane argument parsers
- Integration into main CLI
- Local HTTP server on loopback

**Files:**
- `teaagent/cli/_control_plane_parsers.py` (45 lines)
- `teaagent/cli/_handlers/_control_plane.py` (26 lines)

**CLI Commands:**
- `teaagent control-plane serve --host 127.0.0.1 --port 8765` - Start control plane server

**Features:**
- Local HTTP server on loopback
- Configurable host and port
- Integration with control plane API
- No auth layer added (local-only)

#### 6. Multi-Tenant Hardening

**Implementation:**
- Bearer token authentication for vote relay
- mTLS support for control plane
- Tenant authorization (authZ)
- SSH vote relay integration

**Files:**
- Enhanced `teaagent/control_plane_api.py`
- Enhanced `teaagent/jit_approval_server.py`

**Features:**
- Bearer token authentication
- mTLS support
- Tenant authorization
- SSH vote relay

### Configuration

**Control Plane Config:**
```python
@dataclass
class ControlPlaneConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    enable_auth: bool = False
    bearer_token_file: Optional[str] = None
    mtls_cert_file: Optional[str] = None
    mtls_key_file: Optional[str] = None
```

**Fitness Scoring Weights:**
- Tests: 40%
- Performance: 15%
- Lint: 10%
- Diff size: 10%
- Architectural fit: 15%
- Security: 10%

**Skill Writer Config:**
```python
@dataclass
class SkillWriterConfig:
    review_required: bool = True
    auto_approve_safe: bool = False
    skill_index_path: str = ".teaagent/skill_index.json"
```

## Implementation Timeline

**2026-05-28 22:36:09 +0800** - Docker preflight fallback and Phase 6 sandbox tests
- Commit: `548c6e734b84d37df9634ca0b1dcbb849a91ddc0`

**2026-05-28 22:44:30 +0800** - Phase 6 skill writer and prompt fitness scoring
- Commit: `355e26cf100356cbbcc6fc9c44e003e709640a73`
- Files: skill_writer.py, swarm.py
- Tests: 4 skill writer tests, 3 swarm score tests

**2026-05-28 23:07:31 +0800** - Phase 6 control plane and complete sandbox tournament flows
- Commit: `4cea960213e5280af20e5049d501dcd49c5912d7`
- Files: control_plane_api.py, docker_sandbox.py, html_dashboard, jit_approval_server.py, skill_writer.py, swarm.py
- Tests: 5 docker tests, 1 control plane test, 7 swarm score tests

**2026-05-28 23:07:48 +0800** - Apply ruff-format follow-up on Phase 6 modules
- Commit: `a46fc85e7d1805db8a78f70c47037fc4addbf274`

**2026-05-29 13:59:35 +0800** - Control-plane serve CLI and sync Phase 6 documentation
- Commit: `8f6d8193a3d6411db85bbd58ed14b242474c3f83`
- Files: CLI handlers, parsers, documentation
- Tests: 4 control plane tests

**2026-05-29 14:26:28 +0800** - Control plane JIT regression tests and document approval wiring
- Commit: `067a610ad2945913ea6d570eee7ded57a101f20b`

**2026-05-29 14:44:07 +0800** - SSH vote relay, WASM skill CI workflow, and multi-tenant control plane
- Commit: `a91ce31a5183eb84426999aec1c85a0f8b0dec6b`

**2026-05-29 14:52:50 +0800** - Harden vote relay and control plane with bearer tokens, mTLS, and tenant authZ
- Commit: `b9ba17d80faad633bcb3dc983f33e3f36582edef`

## Git History

**Key Commits:**
- `548c6e734b84d37df9634ca0b1dcbb849a91ddc0` (2026-05-28 22:36:09) - "Add Docker preflight fallback and Phase 6 sandbox tests"
- `355e26cf100356cbbcc6fc9c44e003e709640a73` (2026-05-28 22:44:30) - "Add Phase 6 skill writer and prompt fitness scoring"
- `4cea960213e5280af20e5049d501dcd49c5912d7` (2026-05-28 23:07:31) - "Add Phase 6 control plane and complete sandbox tournament flows"
- `a46fc85e7d1805db8a78f70c47037fc4addbf274` (2026-05-28 23:07:48) - "Apply ruff-format follow-up on Phase 6 modules"
- `8f6d8193a3d6411db85bbd58ed14b242474c3f83` (2026-05-29 13:59:35) - "Add control-plane serve CLI and sync Phase 6 documentation"
- `067a610ad2945913ea6d570eee7ded57a101f20b` (2026-05-29 14:26:28) - "Add control plane JIT regression tests and document approval wiring"
- `a91ce31a5183eb84426999aec1c85a0f8b0dec6b` (2026-05-29 14:44:07) - "Add SSH vote relay, WASM skill CI workflow, and multi-tenant control plane"
- `b9ba17d80faad633bcb3dc983f33e3f36582edef` (2026-05-29 14:52:50) - "Harden vote relay and control plane with bearer tokens, mTLS, and tenant authZ"

**Implementation Files:**
- `teaagent/skill_writer.py` - Skill writer pipeline (150 lines)
- `teaagent/docker_sandbox.py` - Docker sandbox monitoring (89 lines modified)
- `teaagent/control_plane_api.py` - Control plane API (356 lines)
- `teaagent/html_dashboard/app.js` - Dashboard JavaScript (94 lines)
- `teaagent/html_dashboard/index.html` - Dashboard HTML (35 lines)
- `teaagent/html_dashboard/styles.css` - Dashboard CSS (125 lines)
- `teaagent/swarm.py` - Prompt tournament scoring (137 lines added)
- `teaagent/cli/_control_plane_parsers.py` - CLI parsers (45 lines)
- `teaagent/cli/_handlers/_control_plane.py` - CLI handlers (26 lines)

**Test Files:**
- `tests/test_phase6_skill_writer.py` - Skill writer tests (31 lines, 4 tests)
- `tests/test_phase6_docker.py` - Docker sandbox tests (39 lines, 5 tests)
- `tests/test_phase6_control_plane.py` - Control plane tests (111 lines, 11 tests)
- `tests/test_phase6_swarm_score.py` - Swarm score tests (129 lines, 12 tests)
- `tests/test_phase6_jit_server.py` - JIT server tests (49 lines, 5 tests)

## Consequences

**Positive:**
- Review-gated skill publishing ensures quality
- Docker sandbox monitoring provides visibility
- HTML dashboard enables visual approval management
- Deterministic fitness scoring improves tournament quality
- Multi-tenant support enables secure deployments
- Comprehensive test coverage (37 new tests)

**Negative:**
- Increased complexity in skill management
- Additional operational overhead for monitoring
- Control plane is local-only (no auth layer by default)
- Multi-tenant hardening requires additional configuration
- HTML dashboard requires SSE support

**Risk:**
- Medium - Phase 6 tooling affects operational workflows
- Mitigated by comprehensive unit and acceptance tests
- Control plane is local-only by default (no auth layer)
- Multi-tenant features are optional
- Gradual rollout with feature flags for breaking changes

## Alternatives Considered

1. **Keep basic skill management without review** - Rejected due to quality risks
2. **Use external control plane framework** - Rejected as over-engineering
3. **Implement only dashboard without CLI** - Rejected as incomplete coverage
4. **Defer Phase 6 to later phases** - Rejected as operational risk

## References

- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)
- [ADR 0019: Phase 4 - Federated Swarm Consensus](0019-phase-4-federated-swarm-consensus.md)
- [ADR 0020: Phase 5 - Hardened Sandbox Virtualization](0020-phase-5-hardened-sandbox-virtualization.md)
- [Architecture - Phase 4-5 Roadmap](../architecture.md#phase-4-5-roadmap-beta)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Backlog Priority](../backlog-priority.md)

## Verification Commands

```bash
# Skill writer
pytest tests/test_phase6_skill_writer.py -v

# Docker sandbox monitoring
pytest tests/test_phase6_docker.py -v

# Control plane
pytest tests/test_phase6_control_plane.py -v
teaagent control-plane serve --host 127.0.0.1 --port 8765

# Prompt tournament scoring
pytest tests/test_phase6_swarm_score.py -v

# JIT server
pytest tests/test_phase6_jit_server.py -v

# Full Phase 6 suite
pytest tests/test_phase6_*.py -v
```

## Post-Implementation Notes (2026-05-29)

Phase 6 tooling is now in Beta with CLI, unit tests, and E2E acceptance. The system provides review-gated skill publishing, Docker sandbox monitoring, HTML/SSE dashboard for approval management, deterministic prompt tournament scoring, and multi-tenant support with bearer tokens and mTLS. Control plane is local-only by default (no auth layer). Multi-tenant features are optional and require additional configuration. Remaining Beta work includes native WASM modules and deeper tournament benchmarks.
