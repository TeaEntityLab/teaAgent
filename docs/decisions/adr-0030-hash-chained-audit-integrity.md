# ADR-0030: SHA-256 HMAC Hash Chain for Audit Log Tamper Detection

**Status:** Accepted  
**Date:** 2026-06-02  
**Deciders:** Core team  
**Related ADRs:** ADR-0009 (5-Loop Governance — Loop 3), ADR-0026 (JSONL Persistence)

---

## Context

Audit logs must be tamper-evident for two reasons:
1. **Post-incident forensics:** An operator must be able to tell whether the audit trail was modified after the fact (e.g., to conceal an unauthorized tool call)
2. **Compliance posture:** Regulated environments require evidence that logs have not been altered

Tamper detection must work offline (no external service), must not add cryptographic key management overhead for the common case, and must be verifiable with `teaagent audit verify`.

## Decision

Each `AuditEvent` carries a `chain_hmac` field: the HMAC-SHA256 of `(serialized_event_data + previous_chain_hmac)`, keyed with a per-project secret stored in `.teaagent/audit_key` (generated on first run with `os.urandom(32)`). The genesis event carries `chain_hmac = HMAC(event_data, key)`.

```
event_N.chain_hmac = HMAC-SHA256(
    key    = audit_key,
    msg    = event_N.canonical_json + event_{N-1}.chain_hmac
)
```

`teaagent audit verify` replays the chain from genesis, recomputing each HMAC and comparing. Any gap, reorder, insertion, or modification breaks the chain at that point.

Per-project encryption of the full audit payload (not just HMAC) is supported via an optional `TEAAGENT_AUDIT_ENCRYPT_KEY` env var (AES-GCM via `cryptography` optional dep).

## Consequences

**Positive:**
- Detects append, modify, delete, and reorder of any event in the chain
- No external service — verification is `teaagent audit verify` against the local JSONL file
- HMAC key rotation via `teaagent audit rechain --new-key` (re-seals the whole log)
- Tiered audit levels (L0 metrics → L3 full trace) independently apply to payload; integrity check applies at all levels
- Credentials in payload are redacted before hashing — the HMAC protects redacted content, not raw secrets

**Negative:**
- If the audit key file `.teaagent/audit_key` is deleted or overwritten, verification fails for all historical events — key backup is the operator's responsibility
- Parallel subagent runs appending to the same log require serialization (via `fcntl.LOCK_EX`) to maintain chain order — contention under high concurrency
- Chain is per-project, not cross-project — cross-project audit correlation requires external aggregation
- Does not detect exfiltration (reading the log is not logged) — a separate access control concern

## Alternatives Considered

### No integrity protection
- **Rejected:** A compromised agent process (prompt injection achieving RCE) could silently delete its own audit trail. Tamper detection is a hard requirement for operational trust.

### Digital signature per event (RSA/ECDSA)
- **Rejected:** Requires asymmetric key management (key generation, distribution, rotation, revocation). Per-event signing adds ~1ms/event CPU overhead. The additional security over HMAC-chain is marginal for single-operator deployments.

### Merkle tree
- **Rejected:** Optimised for proving membership without replaying the full log (useful for blockchain-style selective disclosure). For TeaAgent, full log replay is always available and efficient. Merkle adds complexity without benefit.

### External blockchain / timestamping service (RFC 3161)
- **Rejected:** External service dependency. Network latency on every audit write. RFC 3161 is appropriate for long-term legal evidence chains but is engineering overkill for an agent runtime.

### Append-only log service (e.g., Loki, OpenSearch)
- **Rejected:** Heavy operational dependency. Appropriate as an integration target (export to Loki) but cannot replace local tamper detection.

## Rationale

HMAC-SHA256 chaining is the lightest mechanism that provides strong sequential integrity guarantees. It is used in production audit systems (AWS CloudTrail, macOS Unified Log digest). The per-project key scope is correct: each project's audit trail is independently verifiable, and key compromise affects only that project's historical chain.

## Conditions to Reconsider

- If cross-project audit correlation becomes a requirement → centralized log service with shared key or external timestamping
- If regulatory compliance requires non-repudiation (not just tamper detection) → switch to per-event RSA signatures with a Hardware Security Module (HSM)
- If the audit key rotation workflow becomes a common operational pain → consider key derivation from a master secret (HKDF) to simplify rotation
