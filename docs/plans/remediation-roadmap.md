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
| P1.1 | ✅ Gate dev-hash behind explicit flag (`TEAAGENT_ALLOW_DEV_SIGNATURES`) | S-C1 | `tests/test_remediation_p1_p2.py` |
| P1.2 | ✅ Mark file-based multi-sig experimental in docs | S-C2 | `federated_sync` docstring |
| P1.3 | ✅ Ignore legacy `approved_call_ids` in `assert_allowed` | S-H1 | Updated policy/contract tests |
| P1.4 | ✅ MCP loopback require token when `TEAAGENT_STRICT_LOCAL=1` | S-H5 | `test_remediation_p1_p2.py` |
| P1.5 | ✅ Vote relay auto-load `relay-tokens.json` / env | S-H6 | `surface_auth.default_relay_token_file` |
| P1.6 | ✅ Atomic scoped-approval consume under flock | S-M1 | `try_consume_scoped_approval` + test |
| P1.7 | ✅ Shell obfuscation adversarial matrix | S-H4 | `ShellObfuscationTests` |

---

## Phase P2 — Concurrency & resilience (1–2 weeks)

| # | Task | Risk addressed | Tests to add |
|---|------|--------------|--------------|
| P2.1 | ✅ Per-thread-only `ContextBus._reconnect` | C-H3 | Generation bump; other threads lazy refresh |
| P2.2 | `archive_to_rag` in single SQLite transaction | C-H6 | Future |
| P2.3 | ✅ AuditLogger reload `prev_hash` before append | C-H2 | `test_two_loggers_same_path_preserve_chain` |
| P2.4 | ✅ `RunStore.logger_for_result` under file_lock | C-M13 | Read under lock |
| P2.5 | ✅ Swarm merge heartbeat hang into `results` | C-M11 | `execute_swarm` |
| P2.6 | ✅ Workflow strict-validation rollback test | Doc drift | `WorkflowRollbackTests` |

---

## Phase P3 — Docs, CI, and ops (ongoing)

| # | Task | Output |
|---|------|--------|
| P3.1 | ✅ Reconcile README Foundation vs maturity Beta | README + matrix sync |
| P3.2 | ✅ Fix `architecture.md` duplicate section numbers | Editorial |
| P3.3 | ✅ threat-model verification columns (Context Bus, async P2P, swarm, workflow rollback) | `docs/threat-model.md` |
| P3.4 | ✅ governance-gate: Phase 5 unit files; docker only in `docker-smoke` | `.github/workflows/ci.yml` |
| P3.5 | ✅ Optional pre-commit smoke (`TEAAGENT_PRECOMMIT_FULL=1` for full suite) | `.pre-commit-config.yaml` |
| P3.6 | ✅ docker-smoke advisory (`continue-on-error`); documented in CONTRIBUTING | `CONTRIBUTING.md` |
| P3.7 | ✅ Plugin fail-closed when `TEAAGENT_PLUGINS_STRICT=1` | S-H8 | `plugins.py` |

---

## Phase P4 — Strategic (quarters)

| # | Item | Status | Reference |
|---|------|--------|-----------|
| P4.1 | JSONL / NFS posture + migration ADR | ✅ tranche | [ADR 0008](../adr/0008-p4-strategic-posture.md), threat-model NFS row |
| P4.2 | MCP TLS via reverse proxy (no native TLS) | ✅ documented | [http-surface-auth.md](../http-surface-auth.md), ADR 0008 |
| P4.3 | File P2P signature `auth_token` when `TEAAGENT_FEDERATED_SIGNATURE_TOKEN` set | ✅ shipped | `federated_sync.py`, `security_env.py` |
| P4.3b | HTTP P2P multi-sig channel | 🔲 future | ADR 0008 — reuse relay bearer shape |
| P4.4 | `jaraco.context` CVE-2026-23949 (Dependabot #10) | ✅ constrained | `pyproject.toml` `jaraco-context>=6.1.0`, `selftest` version check |
| P4.5 | Async `collect_approval_signatures` unit tests | ✅ shipped | `tests/test_federated_sync.py` |

Full SQLite audit/run migration remains **P4+ / backlog** — not started.

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
