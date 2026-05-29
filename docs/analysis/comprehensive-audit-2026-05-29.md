# Comprehensive Repository Audit — 2026-05-29

**Mode:** reflective-dispatch → reflective-review + reflective-risk gate  
**Strictness:** L3 (engineering) with L4 notes for WAN-exposed surfaces  
**Scope:** Full harness — security, concurrency, docs, tests, cost/ops  
**Evidence:** Parallel read-only scans + targeted fixes in this tranche (`1be358e` baseline + follow-up)

---

## Executive summary

TeaAgent’s harness is **registry-first** with strong audit/approval primitives on the happy path. Residual risk clusters into four buckets:

1. **Trust-boundary gaps** — dev-hash signatures, file-based multi-sig, loopback HTTP without bearer tokens  
2. **Concurrency footguns** — global SQLite reconnect, unlocked JIT state (partially fixed this tranche), JSON state without atomic writes (partially fixed)  
3. **Documentation drift** — CHANGELOG/threat-model/README mismatches on timeouts and “shipped” CI gates  
4. **Test gaps** — threat-model claims for shell obfuscation and workflow rollback lack dedicated adversarial tests  

This tranche **fixed** actionable defects: `cleanup_old_deltas` cross-workflow delete, federated sync atomic state + lock, JIT server request-state lock, control-plane JIT timeout default alignment, CHANGELOG timeout drift.

---

## 1. Security & governance

### Critical / high (open)

| ID | Finding | Impact | Mitigation status |
|----|---------|--------|-------------------|
| S-C1 | Dev-hash SSH fallback forgeable if pubkey+message known | Multi-sig / relay bypass in dev mode | Documented; production must use `require_ssh=True` + bearer |
| S-C2 | File-based multi-sig under `.teaagent/pending_approvals/` | Workspace writer forges quorum | Experimental; needs authenticated transport |
| S-H1 | Legacy `approved_call_ids` (no digest) | Wrong payload approved | Deprecation path in policy |
| S-H2 | JIT session approval grants whole tool | Scope creep | By design; document operator risk |
| S-H3 | `workspace_run_shell` uses `shell=True` | Post-approval injection | Policy + argv-only path future work |
| S-H4 | Shell normalization gaps vs obfuscation | Bypass high-risk patterns | Add adversarial test matrix |
| S-H5 | MCP loopback: no auth ⇒ allow all | Local process invokes all tools | Require token on shared machines |
| S-H6 | Vote relay loopback without `auth_policy` | Local vote spam | Default bearer in prod profiles |
| S-H8 | Plugin audit fail-open | Malicious entry points | Allowlist / fail-closed audit |

### Medium (open)

| ID | Finding | Notes |
|----|---------|-------|
| S-M1 | Scoped approval TOCTOU (check then consume) | Use atomic consume under flock |
| S-M2 | Plaintext bearer token files | Ops: chmod 600, outside repo |
| S-M3 | Audit verify swallows some exceptions | Fail CI on verify errors |
| S-M6 | Hooks run `shell=True` | Trust hook config |

### Fixed / improved this tranche

- Federated `import_sync_message` logs `OSError` (prior commit)  
- Context bus thread-local SQLite + WAL (prior commit)  
- Relay rate limits, surface auth, tenant paths (prior commits)  

---

## 2. Concurrency & state

### Fixed this tranche

| Component | Fix |
|-----------|-----|
| `ContextBus.cleanup_old_deltas` | `DELETE` now includes `workflow_id` |
| `FederatedGraphSync` | `atomic_write_text` + `file_lock`; `_state_lock` on pending changes |
| `JITApprovalServer` | `threading.Lock` on `_requests` / `_pending_events` mutations |

### Open (ranked)

| ID | Finding | Severity |
|----|---------|----------|
| C-H3 | `ContextBus._reconnect()` closes all thread connections | High under error storms |
| C-H6 | `archive_to_rag` non-transactional vs concurrent publish | High |
| C-H2 | Multiple `AuditLogger` same path breaks hash chain | High |
| C-M11 | Swarm heartbeat does not cancel executor work | Medium |
| C-M12 | Parallel swarm git on same root | Medium |
| C-M13 | `RunStore.logger_for_result` race | Medium |

---

## 3. Documentation drift

| Topic | Doc | Code | Action |
|-------|-----|------|--------|
| Context Bus timeout | Was `30.0` in CHANGELOG | `5.0` (`_SQLITE_TIMEOUT_SECONDS`) | **Fixed CHANGELOG** |
| JIT timeout | README/architecture: 180s | `JITApprovalServer` default 180; control plane was 300 | **Fixed CLI default → 180** |
| Workflow rollback | threat-model row 32, verification `—` | Implemented in `workflow_engine.py` | Add test; update verification column |
| Async P2P signatures | threat-model row 26 | `collect_approval_signatures` async | Add test |
| docker-smoke “shipped” | architecture | `continue-on-error: true` in CI | Clarify as advisory gate |
| README Foundation vs Beta | §8–9 Foundation | maturity-matrix Beta | Reconcile labels (roadmap item) |

See also: `docs/plans/remediation-roadmap.md`.

---

## 4. Test & CI posture

| Layer | Coverage | Gap |
|-------|----------|-----|
| Unit | ~2,600+ tests | Shell obfuscation adversarial; workflow rollback |
| governance-gate | Fuzz, matrix, subset acceptance | Omits phase5 context bus, JIT, federated |
| pre-commit | Full `pytest -q` | Slow; no fast smoke subset |
| docker-smoke | Phase 6 docker | Non-blocking in CI |
| Live / optional | OTel, sigstore, ssh-keygen | Skipped when deps missing |

**Added this tranche:** workflow-scoped cleanup test, federated concurrent record test, JIT concurrent approve test.

---

## 5. Cost & operations risks

| Cost vector | Risk | Control |
|-------------|------|---------|
| LLM tokens | Unbounded runs | `RunBudget`, iteration caps |
| Tool calls | Loop / spam | Tool-call limits, rate limits on relay |
| Parallel swarm | N × subagent cost | `max_parallel`, tournament caps |
| SQLite WAL | Disk growth on context bus | `cleanup_old_deltas`, archive path |
| Audit L3 | Disk + secret surface | Tiered audit; redaction |
| CI time | Full pytest every commit | Consider smoke subset hook |
| Human time | Approval fatigue | Centralized queue; batch approve |

---

## 6. Trust boundaries (unchanged)

```text
Trusted:   Harness (Runner, Policy, Audit, built-in workspace tools)
Reviewed:  Plugins, MCP servers, skills
Untrusted: Model output, external MCP payloads, plugin handlers
```

---

## 7. Verification performed (this tranche)

- Targeted pytest: context bus, federated sync, JIT  
- Full pre-commit: ruff, mypy, pytest (post-fix)  

---

## 8. Related documents

| Document | Purpose |
|----------|---------|
| `docs/plans/remediation-roadmap.md` | Phased fix plan P0–P3 |
| `docs/analysis/strategic-features-report.md` | Relay / WASM / tenant tranche |
| `docs/threat-model.md` | Threat → mitigation matrix |
| `docs/context-bus-and-federated-sync.md` | Operator guide for Phase 5 stores |
| `docs/http-surface-auth.md` | WAN / bearer / mTLS |

---

## Evidence vs inference

- **Evidence:** Citations from source scans, tests run in Agent mode, commits on `main`.  
- **Inference:** Exploit ease for dev-hash forgery, NFS multi-writer JSONL without live repro tests.
