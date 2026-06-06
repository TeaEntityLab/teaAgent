# Do Not Claim
# 2026-06-06

> **Claim class:** Current truth for what TeaAgent explicitly does not provide.
>
> **Purpose:** Prevent documentation, release notes, or public messaging from
> claiming capabilities that are intentionally unsupported. Backlog items and
> roadmap rows must not promise what this document lists as a non-claim.
>
> **Review trigger:** Any release note, README change, roadmap row addition, or
> public-facing claim that might over-promise.
>
> **Related:** [When Not to Use TeaAgent](../guides/when-not-to-use-teaagent.md) —
> honest non-fit guidance for users choosing a tool.
> [Remote multi-agent non-goals](../strategy/remote-multi-agent-non-goals-2026-06-06.md) —
> subagent and federation non-goals for Phase 0/1.

---

Each row is a **non-claim**: something TeaAgent does not do, is not, or
intentionally does not support. If a new capability ships that reverses a
non-claim, the row must be removed from this document and linked exit evidence
must exist.

### Product Identity

| Non-claim | Rationale | Reference |
|---|---|---|
| **Generic IDE agent clone** | TeaAgent is a governance-first harness, not a feature-matched clone of Cursor, Copilot, or Windsurf. | [README](../../README.md), [When Not to Use](../guides/when-not-to-use-teaagent.md) |
| **Hosted cloud delegate** | No multi-tenant SaaS offering. Users operate the runner, storage, and keys locally or in their CI. | [README](../../README.md), [When Not to Use](../guides/when-not-to-use-teaagent.md#hosted-cloud-delegation) |

### Execution Model

| Non-claim | Rationale | Reference |
|---|---|---|
| **Keystroke-level autocomplete** | TeaAgent orchestrates multi-step tool loops, not tab-complete suggestions. | [When Not to Use](../guides/when-not-to-use-teaagent.md#instant-autocomplete-only) |
| **Zero-config / zero-permission tool** | Permission modes, audit paths, and approval queues are governance features. Setup expects deliberate choices. | [When Not to Use](../guides/when-not-to-use-teaagent.md#zero-config-beginners) |
| **"Set issue and forget" product management** | Human approval, budgets, and audit are intentional brakes — not bugs to bypass. | [When Not to Use](../guides/when-not-to-use-teaagent.md#set-issue-and-forget-product-management) |
| **CI/CD system** | TeaAgent can run in CI, but is not itself a pipeline orchestrator or build system. | [Architecture](../../README.md#architecture) |

### Enterprise Readiness

| Non-claim | Rationale | Reference |
|---|---|---|
| **SOC 2 / ISO 27001 certified** | Architecture supports evidence collection; certification and hosted enterprise packaging are organizational/roadmap items, not shipped OSS defaults. | [When Not to Use](../guides/when-not-to-use-teaagent.md#enterprise-procurement-without-engineering-evaluation) |
| **Daemon or service** | TeaAgent is not a daemon. To expose it as a service, users supply their own process supervisor. | [Deployment Guide](../ops/deployment-guide.md) |

### Safety and Review

| Non-claim | Rationale | Reference |
|---|---|---|
| **Replacement for human code review** | The [code-review-checklist](code-review-checklist.md) defines required human review gates. Approval policies assist, not replace, operator judgment. | [Code Review Checklist](code-review-checklist.md), [Standards](standards.md) |
| **Zero-risk operation** | TeaAgent makes agent actions **provable**, not risk-free. Trust model accepts residual risk with observable boundaries. | [Trust and Audit Whitepaper](trust-and-audit-whitepaper.md) |

### Multi-Agent and Federation

| Non-claim | Rationale | Reference |
|---|---|---|
| **Cryptographic peer identity** | `agent_id` is a string; forgeable. Ed25519 identity and signed approvals are future work (SEC-NEW1). | [Remote multi-agent non-goals](../strategy/remote-multi-agent-non-goals-2026-06-06.md) |
| **Remote approval orchestration** | Approval queues are local/file-backed. Durable coordination abstraction is future work (WS2-005). | [Remote multi-agent non-goals](../strategy/remote-multi-agent-non-goals-2026-06-06.md) |
| **Federated trust by URL/name alone** | MCP trust is anchored to operator config, not PKI. | [Remote multi-agent non-goals](../strategy/remote-multi-agent-non-goals-2026-06-06.md) |
| **Unbounded subagent batches** | Batch timeout/cancel is incomplete. | [Remote multi-agent non-goals](../strategy/remote-multi-agent-non-goals-2026-06-06.md) |

### Vendor and Ecosystem

| Non-claim | Rationale | Reference |
|---|---|---|
| **Bound to one IDE or model family** | TeaAgent supports multiple providers (14 adapters), MCP, ACP, and CLI/TUI surfaces. It is not a single-IDE or single-model product. | [README](../../README.md), [Competitor comparison](../analysis/competitor-self-comparison-matrix-2026-06-06.md) |

---

## Supersession Rule

If a capability listed above ships with acceptance tests and stable docs,
remove the row from this document. Do not move it to a "formerly not" section.
The absence from this list is the claim.

## Verification

```bash
# Check that no release note or README draft claims a non-claim
python3 scripts/validate_docs_consistency.py
```
