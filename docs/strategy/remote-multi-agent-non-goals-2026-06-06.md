# Remote Multi-Agent Non-Goals (Phase 0/1)
# 2026-06-06

> **Owns:** Which remote/federated multi-agent claims are intentionally unsupported.
>
> **Review trigger:** Subagent, swarm, federation, or multi-sig behavior changes.

Until WS2 safety gates pass, TeaAgent **does not** claim the following for
production or WAN deployments:

| Non-goal | Why | Re-enable gate |
| --- | --- | --- |
| Cryptographic peer identity | `agent_id` is a string, forgeable (SEC-NEW1) | Ed25519 agent identity + signed approvals |
| Remote approval orchestration | Approval queues are local/file-backed | Durable coordination abstraction (WS2-005) |
| Federated trust by URL/name alone | MCP trust anchored to operator config, not PKI | Certificate-backed MCP trust policy |
| Prompt-injection detection | Approval gates only; no detector layer | SEC-NEW2 module with tests |
| Behavioral contracts at run start | No signed pre-run contract artifact | SEC-NEW3 module with tests |
| Shared workspace as silent default for subagents | Process/filesystem isolation modes differ | WS2-001 explicit isolation default + docs |
| Unbounded subagent batches | Batch timeout/cancel incomplete | WS2-002 batch deadline enforcement |
| Child budget inheritance | Child runs may not inherit all caps | WS2-003 budget envelope propagation |
| Depth/concurrency bypass | Definitionless launches must not bypass policy | WS2-004 global depth controls |

## Supported today (local operator)

- Prompt-mode destructive approvals with numbered selectors.
- Local subagent queues with parent-run scoped approvals.
- Hardened Docker isolation mode when explicitly selected.
- Run receipts and progress summaries from RunStore audit trails.

## Documentation rule

Release notes and README must not use **enterprise**, **WAN-ready**, or
**federated production** language unless every row above is marked supported with
linked acceptance tests.

See [risk register §6](../security/risk-register-and-threat-model-2026-06-02.md)
for residual risk acceptance boundaries.
