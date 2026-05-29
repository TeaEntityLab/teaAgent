# Remediation Roadmap — Post-Audit 2026-05-29

Phased plan derived from `docs/analysis/comprehensive-audit-2026-05-29.md`.  
Principle: **smallest verifiable step** per phase; no big-bang refactors.

---

## Phase P0 — Correctness bugs (days)

| # | Task | Owner module | Acceptance |
|---|------|--------------|------------|
| P0.1 | ✅ `cleanup_old_deltas` scoped to `workflow_id` | `context_bus.py` | `test_cleanup_old_deltas_scoped_to_workflow` |
| P0.2 | ✅ Federated sync atomic state + pending lock | `federated_sync.py` | `test_concurrent_record_node_changes` |
| P0.3 | ✅ JIT server state lock | `jit_approval_server.py` | `test_concurrent_approve_is_idempotent` |
| P0.4 | ✅ CHANGELOG Context Bus timeout 5.0 | `CHANGELOG.md` | Matches `_SQLITE_TIMEOUT_SECONDS` |
| P0.5 | ✅ Control plane JIT default 180s | `_control_plane_parsers.py` | Matches `JITApprovalServer` |

---

## Phase P1 — Security hardening (1–2 weeks)

| # | Task | Risk addressed | Tests to add |
|---|------|--------------|--------------|
| P1.1 | Gate dev-hash behind explicit flag; reject in production relay/multi-sig | S-C1 | `test_dev_hash_rejected_when_strict` |
| P1.2 | Mark file-based multi-sig experimental in CLI/docs | S-C2 | — |
| P1.3 | Remove legacy `approved_call_ids` path | S-H1 | Argument mismatch denial |
| P1.4 | MCP loopback require token when `TEAAGENT_STRICT_LOCAL=1` | S-H5 | `test_mcp_loopback_requires_token` |
| P1.5 | Vote relay: default `auth_policy` from token file on loopback | S-H6 | CLI integration smoke |
| P1.6 | Atomic scoped-approval consume under flock | S-M1 | Concurrent consume test |
| P1.7 | Shell obfuscation adversarial matrix | S-H4 | Extend `tests/test_policy.py` |

---

## Phase P2 — Concurrency & resilience (1–2 weeks)

| # | Task | Risk addressed | Tests to add |
|---|------|--------------|--------------|
| P2.1 | Per-thread-only `ContextBus._reconnect` | C-H3 | Publish + reconnect stress |
| P2.2 | `archive_to_rag` in single SQLite transaction | C-H6 | Concurrent publish + archive |
| P2.3 | AuditLogger singleton-per-path or reload `prev_hash` | C-H2 | Two-loggers same file |
| P2.4 | `RunStore.logger_for_result` under file_lock | C-M13 | Append during finalize |
| P2.5 | Swarm: propagate hang into `results` + optional cancel | C-M11 | Hang scenario test |
| P2.6 | Workflow strict-validation rollback test | Doc drift | `test_workflow_strict_rollback` |

---

## Phase P3 — Docs, CI, and ops (ongoing)

| # | Task | Output |
|---|------|--------|
| P3.1 | Reconcile README Foundation vs maturity Beta | README + matrix sync |
| P3.2 | Fix `architecture.md` duplicate section numbers | Editorial |
| P3.3 | threat-model verification columns for rows 26, 32 | Link to new tests |
| P3.4 | governance-gate: add phase5/6 unit files | `.github/workflows/ci.yml` |
| P3.5 | Optional pre-commit smoke job (subset pytest) | `.pre-commit-config.yaml` |
| P3.6 | docker-smoke: decide block vs advisory | CI policy doc |
| P3.7 | Plugin fail-closed audit or allowlist | S-H8 |

---

## Phase P4 — Strategic (quarters)

| Item | Reference |
|------|-----------|
| Distributed JSONL locks / DB migration | threat-model, NFS note |
| Native MCP TLS | reverse-proxy termination |
| Authenticated P2P multi-sig transport | federated_sync HTTP channel |
| Dependabot #10 dependency bump | Security UI |

---

## Cost controls (operational)

| Control | Config / command |
|---------|------------------|
| Iteration cap | Runner budget |
| Tool-call cap | Runner budget |
| Relay abuse | `--rate-limit-calls` / window |
| Audit disk | L0–L2 tiers; prune old runs |
| Swarm parallelism | `--max-parallel` |

---

## Human review gates

Stop for explicit review before:

- Exposing vote relay or control plane on `0.0.0.0` without mTLS + bearer  
- Enabling `danger-full-access` or `--skip-plan-check` in CI  
- Shipping file-based multi-sig as “production ready”  

---

## Tracking

Update this file when P0 items complete (check ✅) and when opening PRs for P1+.
