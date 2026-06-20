# 01 - Security & Risk Audit

> Dimension priority: **Highest** | Audit method: cx semantic navigation + Read/Grep across ~40 modules | Every finding includes `file_path:line_number`

## Strengths

1. **Layered fail-closed approval pipeline**: `ApprovalManager.assert_allowed` performs nine-stage resolution (backend -> path containment -> skill protection -> JIT -> preset -> scoped -> payload digest -> multi-sig -> prompt); unmatched calls raise `ToolPermissionError` (`teaagent/approval_manager.py:839-1006`).
2. **HMAC-bound, consume-once scoped approval tokens**: `(run_id, call_id, tool_name, argument_digest)` is consumed atomically under `file_lock`; replay protection, tamper resistance, cross-run isolation, and concurrency exclusion are all tested (`teaagent/ergonomics/_approval_state.py:333-379`; `tests/test_approval_token_exactness.py`).
3. **Tamper-evident audit chain**: SHA-256 hash chaining + per-run HMAC + monotonic timestamps + `fsync` + `file_lock` (`teaagent/audit.py:455-479`; `teaagent/audit_chain.py:298-436`).
4. **Configurable redaction**: 11 built-in patterns (Bearer/sk-/JWT/AKIA/GitHub PAT/SSH private keys, and others) plus extension points (`teaagent/redaction.py:60-168`).
5. **Strong workspace boundary**: symlinks are rejected before resolution, followed by a second `relative_to(root)` check at both the approval and tool layers for defense in depth (`teaagent/workspace_tools/_helpers.py:74-83`; `teaagent/approval_manager.py:1090-1141`).
6. **Subagent permission clamping**: child permissions are clamped to `WORKSPACE_WRITE` when the parent uses `allow` or `danger-full-access` (`teaagent/subagents/_manager.py:36-37,125-151`).
7. **Loopback by construction**: the JIT approval server and signature relay refuse non-loopback binding when authentication is absent (`teaagent/jit_approval_server.py:80-106`; `teaagent/signature_relay.py:130-137`).
8. **Compliance mode enabled by default**: failure to persist audit data raises `AuditDurabilityError` (`teaagent/audit.py:504-508`).
9. **Defense-grade CI security pipeline**: pip-audit (blocking) + bandit + CodeQL + Dependabot + CVE pinning self-test (`.github/workflows/security.yml`, `teaagent/selftest.py:17-45`).
10. **Constant-time comparison**: `secrets.compare_digest` / `hmac.compare_digest` are used at all sensitive comparison points.

## Gaps (with Severity)

| ID | Severity | Summary | Evidence |
| --- | --- | --- | --- |
| G1 | **High** | `AutoModeManager` silently switches allowlisted tools to `DANGER_FULL_ACCESS` with `allow_all_destructive=True`, bypassing the approval-authority/JIT/multi-sig pipeline | `teaagent/runner/_auto_mode_manager.py:52-66`; applied in `teaagent/runner/_core.py:688-690` |
| G2 | Medium | `ToolPermissionManager.check_scope_budget` fails open on exceptions (returns `None`, meaning allowed) | `teaagent/tool_permissions.py:219-228` |
| G3 | Medium | Approval queue HMAC is disabled by default; when `TEAAGENT_APPROVAL_HMAC_KEY` is unset, validation returns `True` | `teaagent/subagents/_approval_queue_store.py:102-110,341-347` |
| G4 | Medium | Library callers at `chat_agent.py:755` fall back to in-memory `AuditLogger()`, with no durable audit trail | `teaagent/chat_agent.py:755`; `teaagent/audit.py:226-227` |
| G5 | Medium | Redis approval queue password/SSL defaults are `None`/`False` | `teaagent/subagents/_approval_queue_redis_store.py:39-40`; `teaagent/coordination/approval_backend.py:280-281` |
| G6 | Medium | `edit_at_hash` line hashes use only 8 bits (`zlib.crc32 & 0xFF`) | `teaagent/workspace_tools/_helpers.py:90-94` |
| G7 | Low | Audit chain HMAC verification is silently skipped when the key file is missing | `teaagent/audit_chain.py:314-315,439-457` |
| G8 | Low | Multi-sig dev-hash fallback uses `sha256(msg+pubkey)` as a mock signature | `teaagent/approval_manager.py:1216-1219` |
| G9 | Low | `_assert_paths_in_workspace` does not explicitly reject symlinks and relies on the tool-layer defense | `teaagent/approval_manager.py:1090-1141` |
| G10 | Low | `GitBranchSandbox` does not sanitize branch names as git refs | `teaagent/sandbox/_git_branch.py:119` |
| G11 | Low | The bandit step in `ci.yml` is non-blocking (`|| echo "::warning::..."`) | `.github/workflows/ci.yml:201-203` |
| G12 | Low | The `notify.py:42` docstring incorrectly claims `shell=True`; the implementation uses `shell=False` | `teaagent/notify.py:42,138-141` |

## Risk Scenarios (Severity x Likelihood x Impact)

- **R1 - High / Medium / High - Destructive auto-mode bypass**: `--auto-mode` + broad allowlist -> runner escalates to `DANGER_FULL_ACCESS` -> a prompt-injected model calls `workspace_run_shell_mutate "rm -rf /important/path"` without JIT or exact-call approval. Normal tool lifecycle events are still recorded, but no dedicated auto-mode approval-authority event explains the bypass; workspace containment remains the principal authorization guard. (Fix G1)
- **R2 - Medium / Low / High - Forged approval queue record**: on a shared host, incorrect `.teaagent/` permissions let an attacker write a forged `APPROVED` record; with no configured HMAC, the record is accepted and a subagent executes a destructive call. (Fix G3)
- **R3 - Medium / Low / High - Unaudited library caller**: a programmatic call to `run_chat_agent(...)` without an `audit` argument uses only in-memory logging; when the process exits there is no JSONL evidence chain, violating the "every tool call recorded" rule and impairing post-incident forensics. (Fix G4)
- **R4 - Medium / Low / Medium - Forged Redis approval**: a cross-host Redis deployment without password or SSL lets a network attacker submit `APPROVED` directly to Redis. (Fix G5)
- **R5 - Medium / Medium / Low - Stale read passes hash check**: an 8-bit CRC has a 1/256 collision probability at the hash gate; the `old` text check still catches most cases, but a carefully arranged concurrent edit can bypass it. (Fix G6)
- **R6 - Low / Low / High - Audit HMAC neutralization**: an actor with owner-level file access deletes `~/.teaagent/run-keys/<run>.key`; `verify_audit_chain` skips HMAC verification and accepts forged events. (Fix G7)
- **R7 - Low / Low / Medium - Silent scope-budget failure**: a plugin enforcer throws an exception; `check_scope_budget` returns `None`, so an out-of-scope tool call is not vetoed. (Fix G2)

## AGENTS.md Rule Compliance (Rule by Rule)

| Rule | Assessment | Key Evidence |
| --- | --- | --- |
| Tools registered through ToolRegistry | Compliant | `teaagent/tools.py:129-178` is the single registration path and enforces five fields |
| Every tool requires name/description/input/output/annotations | Compliant | `register()` rejects empty names/descriptions; `ToolDefinition` contains all five fields; 50+ tools comply |
| Destructive tools require an exact-call approval token | **Violated (see G1)** | Normal approval paths bind `(call_id, tool_name, argument_digest)`, and exactness tests are comprehensive. **However, `AutoModeManager` escalates to `DANGER_FULL_ACCESS` and allows destructive calls without an exact-call token.** |
| Tool errors are actionable and classified | Compliant | 11 `DenialReasonCode` values; `AgentHarnessError.hint`; `format_denial_message` |
| Every run has iteration and tool-call limits | Compliant | `RunBudget(max_iterations=25, max_tool_calls=25)`; enforced by the runner; clamped for subagents |
| Every tool call and final result is audited | **Partial (see G4)** | CLI paths are complete; **the library caller at `chat_agent.py:755` falls back to in-memory logging** |
| Long-lived state is externalized | Compliant | RunStore/ApprovalPresetStore/Ultrawork/Checkpoint/audit JSONL |
| No second framework without an ADR | Compliant | swarm/consensus/subagents are covered by ADR-0019/0022/0028/0029 |

## Recommendations (P0/P1/P2)

### P0
- **P0-1 (fix G1)**: At `teaagent/runner/_auto_mode_manager.py:52-66`, stop unconditionally escalating to `DANGER_FULL_ACCESS`. Preserve the parent mode and inject bounded `preapproved_payload_digests` so destructive auto-mode calls remain payload-scoped and still produce approval audit records. Alternatively, require `full_access_acknowledged=True` to be set through a separate CLI ceremony and emit a `tool_call_approved` event with `authority_type='auto_mode'` for every auto-approved destructive call.
- **P0-2 (fix G3)**: At `teaagent/subagents/_approval_queue_store.py:102-110`, when `TEAAGENT_APPROVAL_HMAC_KEY` is unset, generate a 32-byte key and persist it with mode `0o600` (following `ApprovalPersistence._get_workspace_secret`), or refuse to load and report a clear error.

### P1
- **P1-1 (fix G4)**: At `teaagent/chat_agent.py:755`, when `audit is None`, create `AuditLogger(path=RunStore(root).audit_path_for_run(run_id))`; add an explicit `--no-audit` escape hatch with a warning.
- **P1-2 (fix G2)**: At `teaagent/tool_permissions.py:219-228`, return a denial reason when an enforcer raises, or at minimum log at `ERROR` and re-raise unless `TEAAGENT_SCOPE_FAIL_OPEN=1` is explicitly set.
- **P1-3 (fix G5)**: At `teaagent/coordination/approval_backend.py:278-325`, follow `require_signature_relay_bind_auth`: raise when `redis_host` is non-loopback and neither password nor SSL is configured.
- **P1-4 (fix G6)**: At `teaagent/workspace_tools/_helpers.py:90-94`, replace `& 0xFF` with a full SHA-256 hex digest (or at least `& 0xFFFFFFFF`); gate the wire-format change behind a workspace configuration flag and migration.

### P2
- **P2-1 (fix G7)**: At `teaagent/audit_chain.py:439-457`, if an event contains `chain_hmac` but its key is missing, emit a `missing_chain_key` warning failure instead of silently skipping verification.
- **P2-2 (fix G9)**: At `teaagent/approval_manager.py:1090-1141`, explicitly check `Path(...).is_symlink()` before resolving the path.
- **P2-3 (fix G10)**: At `teaagent/sandbox/_git_branch.py:119`, sanitize `run_id` to `[A-Za-z0-9._-]`.
- **P2-4 (fix G11)**: At `.github/workflows/ci.yml:201-203`, remove the `|| echo` fallback to match the blocking behavior in `security.yml`.
- **P2-5 (fix G8, G12)**: Correct the `notify.py:42` docstring; make `config_lint` warn when `allow_dev_signatures` is enabled outside a development workspace (partially implemented at `teaagent/config_lint.py:102-108`; extend it to `MultiSigQuorumConfig`).
