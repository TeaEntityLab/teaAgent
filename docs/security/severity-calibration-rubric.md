# Security Severity Calibration Rubric

This document defines the shared security severity scale for all vulnerability disclosures, threat models, risk registers, and module documentation in the TeaAgent repository.

## Severity Scale

The severity of a security gap, threat, or vulnerability is determined by the potential impact of exploitation on the TeaAgent trust boundary:

| Severity | Definition | Exploit/Bypass Impact | Remediated Cadence / Gate |
|---|---|---|---|
| **Critical** | Complete trust boundary bypass. | Bypasses approval gates entirely, allows forgeability of the audit trail, executes arbitrary commands directly on the host machine (no container isolation), or causes irreversible data deletion. | Immediately Blocking. Must be resolved before commit/push is declared complete. |
| **High** | Severe compromise of security defense-in-depth or resource controls. | Exposes sensitive host credentials/files, bypasses cost/budget boundaries (causing financial risk), spawns Docker containers without isolation flags (allowing network access), or expands path-restricted approvals to global access. | Blocker for release packaging. Must be addressed within the current development sprint. |
| **Medium** | Forensic, validation, or minor trust enforcement flaws. | Replay window for authentication tokens, partial undo visibility, silenced warnings on storage failure, or absence of sandbox runtime warning flags. | Should be addressed within the active development cycle. |
| **Low** | Minor usability, UI inconsistency, or code cleanliness issues. | Stale metadata properties, cosmetic logging errors, or UI cost display desynchronization. | Backlog items. Checked during regular maintenance passes. |

---

## Calibrated Severity Mapping

Based on the shared rubric, the core security mechanisms map to the following calibrated levels:

1. **`DANGER_FULL_ACCESS` Mode**: **Critical** (Bypasses all checks and gates by design; entering this mode must be cryptographically signed and recorded in the hash-chained audit log).
2. **`allow_all_destructive` Bypass**: **Critical** (If allowed to bypass approval without explicit confirmation, it constitutes a total security boundary bypass).
3. **Audit Chain Forgeability**: **Critical** (Ephemeral HMAC keys allow attackers to reconstruct the SHA-256 hash chain, defeating non-repudiation).
4. **Subagent Process Isolation**: **High** (Running subagents on host or using root-owned Docker containers with network access enables filesystem escape or data exfiltration).
5. **Path-Scoped Expansion**: **High** (Empty paths expanding to global workspace access violates the principle of least privilege).
6. **Credential Leakage via Inspect**: **High** (Treating mutating commands like `cat`/`head` as read-only inspection allows exfiltration of keys/secrets).
