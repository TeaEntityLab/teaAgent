# ADR 0007: ANP Adapter Boundary for External Federation

## Status

Proposed (minimum-scope draft).

## Decision

Adopt ANP (Agent Network Protocol) as an optional external federation surface
through a bidirectional adapter boundary, not as a replacement for TeaAgent
core runtime governance.

Two directions are in scope:

1. Inbound adapter (ANP -> TeaAgent):
   accept ANP network requests, normalize into internal task/delegation calls,
   execute through existing `ToolRegistry`, `ApprovalPolicy`, `AgentRunner`,
   and `AuditLogger`.
2. Outbound adapter (TeaAgent -> ANP):
   delegate selected tasks to ANP peers through a typed client, then map
   responses into TeaAgent result/audit models.

## Rationale

- TeaAgent already has strong internal governance primitives (tool schema
  validation, approval gating, budget limits, audit chain). Replacing internal
  execution protocol would create risk without proportional near-term value.
- TeaAgent already exposes adjacent protocol surfaces:
  - MCP for tool interoperability.
  - A2A/AgentCard for discovery and delegation.
  - ACP for IDE integration.
- ANP is most valuable here as a network interoperability layer for
  cross-team/cross-organization federation.

## Scope

Included:

- ANP adapter interfaces and mapping contracts.
- Request/response normalization and error taxonomy mapping.
- Trace propagation and audit event correlation for inbound/outbound flows.
- Capability-based routing between local execution and remote ANP delegation.

Excluded:

- Rewriting `AgentRunner` decision loop.
- Replacing `ToolRegistry`, `ApprovalPolicy`, or audit persistence.
- Introducing a second independent agent framework inside core runtime.

## Architecture Boundary

Inbound path:

`ANP Transport -> ANP Inbound Adapter -> Internal Request Model -> Agent/A2A Execution -> Internal Result -> ANP Response`

Outbound path:

`TeaAgent Routing Decision -> ANP Outbound Adapter -> ANP Peer -> Internal Result Mapping -> Audit + Return`

Hard invariants:

- All destructive actions still require current TeaAgent approval semantics.
- All tool calls still pass through `ToolRegistry` schema validation.
- All delegated and local outcomes still emit audit events.
- Budget and iteration limits remain enforced by TeaAgent runtime.

## Most Suitable Scenarios

ANP adapter is recommended when:

- Teams need federated delegation to external agents not natively on MCP/A2A.
- Cross-boundary discovery and capability routing matter more than low latency.
- Enterprise integration needs protocol-level interoperability contracts.

ANP adapter is not recommended as first priority when:

- Primary workload is local coding-agent loops within one repository/workspace.
- Existing MCP + A2A surfaces already satisfy current integration needs.

## Consequences

Positive:

- Enables broader external agent-network interoperability without destabilizing
  core governance.
- Preserves existing safety/audit model while adding federation reach.
- Supports incremental rollout and rollback via adapter toggles.

Negative:

- Adds protocol mapping and test matrix complexity.
- Requires careful semantic alignment of identity/authn/error handling.
- Introduces dual-path delegation behavior (local vs remote) that must be
  observable and deterministic.

## Minimum Implementation Plan (PoC)

1. Define `ANPInboundAdapter` and `ANPOutboundClient` protocol interfaces.
2. Implement mapping layer:
   - ANP task -> internal request model.
   - internal result/error -> ANP response model.
3. Add routing policy gate:
   - local-first default, remote ANP delegation by explicit capability/route.
4. Add audit/trace fields for ANP correlation IDs and peer endpoint identity.
5. Add acceptance tests:
   - inbound success/failure/approval-required.
   - outbound delegation timeout/retry/fallback.
   - invariant checks for audit + approval + budget enforcement.

## Acceptance Criteria

- No bypass path around `ToolRegistry`/`ApprovalPolicy`/`AuditLogger`.
- Inbound and outbound ANP flows are fully observable in audit records.
- Remote delegation failures degrade gracefully to local fallback when policy
  allows.
- Existing non-ANP workflows and tests remain green.

## Alternatives Considered

- Full ANP-native runtime rewrite:
  rejected for now due to governance-regression risk and migration cost.
- No ANP support:
  rejected as long-term posture if cross-org federation is a target.
- ANP as outbound-only:
  viable as phase-1 fallback if inbound surface is deferred.
