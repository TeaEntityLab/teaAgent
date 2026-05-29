# TeaAgent Threat Model

Last updated: 2026-05-29 (3rd edition — post comprehensive audit)

This document maps threats to mitigations and verification. It complements [tool-authoring.md](tool-authoring.md) and [architecture.md](architecture.md).

| Threat | Impact | Mitigation (current) | Verification | Gap / notes |
|--------|--------|----------------------|--------------|-------------|
| Prompt injection causing destructive tools | High | Permission modes; `ApprovalPolicy`; policy-as-code deny rules | `test_policy_as_code_flow.py`, `tests/policy/test_permission_matrix.py` | Model may still *request* bad tools; harness blocks execution |
| Mislabelled tool annotations (`read_only` on write tool) | High | `teaagent tool lint`; runtime policy on destructive flag | `tests/test_tranche_b_governance.py`, `tests/test_governance_fuzz.py` | Plugin handlers not sandboxed by default — trust boundary |
| Path traversal / symlink escape | High | Workspace path resolution; protected paths | `test_contract_policy.py`, `test_protected_paths_flow.py` | Fuzz coverage ongoing |
| Shell mutation in workspace-write mode | High | `ApprovalPolicy` blocks non-file destructive tools in workspace-write | `tests/policy/test_permission_matrix.py` | Dangerous flag lists in shell classifier — maintain with tests |
| Shell command obfuscation bypass | High | Multi-pass `_normalize_shell_arg` (quotes, escapes, backticks, `$()`, shlex); list-argument normalization | `tests/test_policy.py` (MultiSigQuorumTests) | Catches `rm -r"f" /prod`, backtick injection, list-based bypass |
| Secret leakage in audit logs | Medium | Audit redaction keys and truncation | `test_audit_chain_integrity_flow.py` | Over-redaction reduces debuggability — export tiers future work |
| Audit log tampering | Medium | Hash chain (`audit verify`); fsync | `test_audit_chain_integrity_flow.py` | Local-only unless signed export |
| Plugin supply-chain execution | High | Plugin verify/install gates; entry-point audit | `test_plugin_install_security_flow.py` | Capability manifest formalization in progress |
| MCP server tool explosion / exfiltration | High | MCP tool filter hook; HTTP auth for remote MCP | `test_remote_mcp_consumption_flow.py` | MCP trust CLI implemented — per-server defaults |
| Memory poisoning / failure-card bias | Medium | Failure cards; warning injection; automated invalidation rules | `test_memory_auto_curation_flow.py`, `tests/test_governance_fuzz.py` | TTL/confidence schema enforced with conservative defaults |
| Subagent privilege escalation | High | Per-agent JIT approval (`_agent_approved_tools`); subagent defs; lineage; isolation modes; centralized approval queue | `test_subagent_lineage_flow.py`, `test_approval_is_per_agent_not_global`, worktree/container isolation flows, `tests/test_governance_fuzz.py` | Global mutation fixed — approval now scoped per-agent |
| Parallel branch contamination | Medium | Git sandbox branches; worktree isolation | `test_subagent_worktree_isolation_flow.py` | Main-branch write blocked in tournament — verify per release |
| Unplanned destructive writes | High | Strict plan-before-write enforcement in workspace-write mode | `tests/test_governance_fuzz.py`, `tests/test_tranche_b_governance.py` | `--skip-plan-check` override available for power users |
| Provider response schema drift | Low | JSON schema for model decisions | `test_live_provider_conformance_flow.py` | Provider-specific quirks remain |
| Unbounded run cost | Medium | `RunBudget`; iteration/tool/cost caps | `test_p0_harness.py`, `test_p0_slo_flow.py` | User must configure caps |
| JIT approval server unresponsive during wait | High | Async `_wait_for_approval` using `asyncio.Event` + `asyncio.wait_for`; SSE server remains responsive | `tests/test_phase6_jit_server.py` | Fixed synchronous `time.sleep` spin-lock blocking event loop |
| Context Bus SQLite lock contention / transaction leaks | Medium | Per-thread SQLite connections (`threading.local`); `timeout=5.0` on connect; WAL pragmas on each new connection; `_execute_with_retry` with exponential backoff (5 retries) + generation-based reconnect; explicit `conn.rollback()` on write failure; `cleanup_old_deltas` scoped to `workflow_id` | `tests/test_phase5_context_bus.py` (incl. parallel publish + workflow-scoped cleanup) | Global `_reconnect()` still closes all thread handles; see `docs/plans/remediation-roadmap.md` P2.1 |
| Federated sync state corruption on crash | Medium | `atomic_write_text` + file lock on `federated_sync_state.json`; lock on pending changes | `tests/test_federated_sync.py` | File-based multi-sig quorum still experimental |
| JIT approval server race on approve/reject | Medium | `threading.Lock` on `_requests` / `_pending_events` | `tests/test_phase5_jit_approval_server.py` | Approve from thread without running event loop still drops SSE broadcast |
| Asyncio event loop starvation from synchronous P2P approval polling | High | `collect_approval_signatures` converted to `async def` with `asyncio.sleep`; `_collect_peer_signatures` dispatches via `run_coroutine_threadsafe` or `asyncio.run()` | — | Previously 5-minute synchronous `time.sleep` polling blocked event loop — now fully non-blocking |
| Shell normalization bypass via brace expansion / process substitution | High | Multi-pass `_normalize_shell_arg` now handles `{a,b}` expansion, `<()` process substitution, and non-string/non-list fallback | `tests/test_policy.py` | Catches `/pr{od,oduction}`, `<(echo /prod)`, dict-type command args |
| Protected directory bypass via alternate write tools | High | `workspace_write_*` tool pattern + `.git*` argument pattern covers all write tools and subdirectory contents | `tests/test_policy.py`, `tests/test_file_policy.py` | Previously only `workspace_write_file` was covered |
| Swarm hang / undetected thread deadlock | High | `ThreadPoolExecutor.as_completed(timeout=...)` with partial result collection; `Subagent` tracks `is_running`/`last_heartbeat`; `_heartbeat_monitor_loop` uses thread-ref liveness instead of defunct PID-based `is_process_alive` | `tests/test_swarm.py` | Previously heartbeat monitor checked parent PID (always alive) — now detects actual thread hangs |
| Git stash stack corruption in parallel sandboxes | Critical | `stash_save` returns actual stash reflog selector; `stash_pop` accepts specific ref | `tests/test_sandbox.py` | Previously hardcoded `stash@{0}` caused cross-agent stash confusion |
| Workflow self-healing infinite recursion | High | `_execute_step` accepts `current_attempt` parameter preserved across recursive re-execution; abort guard checks attempts against max before proceeding | `tests/test_phase5_workflow_engine.py` | Previously `self_healing_attempts` reset to 0 on new `StepExecution` — now passed through recursion chain |
| Workflow strict validation rollback never executed | High | `execute_workflow` integrates `UndoJournal` + `AuditLogger`; checks `result.requires_rollback` and calls `journal.restore()` on strict validation failure | — | Previously `requires_rollback` flag set but never consumed — now triggers full workspace undo |

## Trust Boundaries

```text
Trusted:   TeaAgent harness (Runner, Policy, Audit, built-in workspace tools)
Reviewed:  Project plugins, MCP servers, skills (manifest + human enable)
Untrusted: Model output, external MCP payloads, arbitrary plugin handlers
```

## Operator Checklist (High-Risk Repos)

1. Start with `--permission-mode read-only`.
2. Run `teaagent tool lint` after adding plugins.
3. Use `--require-plan` + `--from-plan` for writes (now enforced by default in workspace-write mode).
4. Use `--skip-plan-check` only when you understand the security implications.
5. Run `teaagent memory failures auto-invalidate` periodically to clean stale failure cards.
6. Never use `danger-full-access` outside an isolated sandbox.
7. Review `teaagent runs export <run_id>` after each autonomous edit session.
8. Check CI governance gate results before merging changes.
