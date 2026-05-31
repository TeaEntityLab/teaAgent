# Comprehensive Plan — All Aspects — 2026-05-31

**Purpose:** Master plan index consolidating all open risks across six
dimensions: Security, Reliability, Maintainability, Test Coverage,
Documentation, and Operational. Each plan is self-contained with acceptance
criteria. New findings from today's audit are marked `[NEW]`.

**Prerequisite reading:**
- `docs/analysis/comprehensive-audit-2026-05-29.md` — baseline audit
- `docs/analysis/new-risk-findings-2026-05-31.md` — new findings this session
- `docs/plans/remediation-roadmap.md` — previously accepted fix plan (P0–P4)
- `docs/plans/future-roadmap-risk-usability-backlog-2026-05-31.md` — horizon roadmap

**Principle:** Smallest verifiable fix per item. No big-bang refactors.
Human review required before executing any plan that touches auth, audit, or
permissions.

---

## Dimension 1 — Security

### Plan S1 — Fix AuditLevel.L3 "encrypted at rest" documentation fraud [NEW] [HIGH]

**Why:** `teaagent/audit.py:166` docstring claims L3 is "encrypted at rest."
The implementation returns the raw payload without encryption. This is a
compliance risk for any operator who relies on this claim.

**Phase A — Immediate (1 day):**
1. Remove "encrypted at rest" from the `audit.py:166` docstring. Replace with:
   `L3: Full local trace (all data, no redaction). Encryption at rest is NOT
   currently implemented.`
2. Update `docs/threat-model.md` — add new row: `AuditLevel.L3 plaintext | Medium | Documentation corrected; encryption roadmap item |`.
3. Update `docs/specs/security-spec.md` if it references L3 encryption.

**Phase B — Optional encryption (2–3 days if needed for compliance):**
1. Add `audit_encryption_key: str | None = None` to `AuditLogger.__init__`.
2. If set, wrap the payload with `cryptography.fernet.Fernet` before write.
3. Add `teaagent audit decrypt` subcommand for reading encrypted logs.
4. Gate behind `[extras.audit-encryption]` optional dependency.

**Acceptance criteria (Phase A):**
- `grep -n "encrypted at rest" teaagent/audit.py` returns nothing.
- `docs/threat-model.md` has a row for L3 plaintext.
- No other file claims L3 encrypts.

**Acceptance criteria (Phase B):**
- `pytest tests/test_audit_encryption.py` passes.
- `teaagent audit decrypt` round-trips encrypted log.

---

### Plan S2 — Gate `ChildProcessCodeModeBackend` as trusted-user only [NEW] [MEDIUM]

**Why:** `code_mode/_child_process.py` uses `exec()` in a forked child with
`SAFE_BUILTINS` and resource limits. The fork shares FDs with the parent. For
untrusted input, `ContainerCodeModeBackend` (Docker) is the correct path.

**Steps:**
1. Add a docstring to `ChildProcessCodeModeBackend`: "For trusted-user inputs
   only. For untrusted or multi-tenant workloads, use ContainerCodeModeBackend."
2. Add a `trusted_only: bool = True` field. When `False`, raise
   `ValueError("Use ContainerCodeModeBackend for untrusted inputs")`.
3. Update `docs/specs/security-spec.md` with a code_mode trust boundary table.

**Acceptance:** `ChildProcessCodeModeBackend(trusted_only=False)` raises.
Docstring change is auditable via `git log`.

---

### Plan S3 — Open items from comprehensive-audit-2026-05-29.md (carry-forward)

The following security items from the prior audit remain open. Each has its
own acceptance in the remediation roadmap but is listed here for completeness:

| ID | Item | Priority |
|---|---|---|
| S-H3 | `workspace_run_shell` `shell=True` → argv-only path | High |
| S-H4 | Shell normalization adversarial matrix gaps | High |
| S-H5 | MCP loopback no-auth default | High |
| S-H6 | Vote relay loopback without `auth_policy` | High |
| S-H8 | Plugin audit fail-open | High |
| S-M2 | Plaintext bearer token files | Medium |
| S-M3 | Audit verify swallows exceptions | Medium |

Ref: `docs/plans/remediation-roadmap.md` Phase P1 for tracking.

---

## Dimension 2 — Reliability

### Plan R1 — Fix fragile async loop management in approval paths [NEW] [HIGH]

**Why:** `teaagent/approval_manager.py:514-524` and `teaagent/policy.py:523-533`
call `asyncio.set_event_loop(new_loop)` before running a coroutine synchronously.
This mutates the thread-local event loop pointer, which can leave it closed after
the call, causing `RuntimeError: Event loop is closed` for any subsequent async
operation in the same thread.

**Steps:**
1. Replace the `new_loop` pattern with:
   ```python
   try:
       loop = asyncio.get_running_loop()
   except RuntimeError:
       loop = None
   if loop and loop.is_running():
       # We're inside an event loop — use a thread to avoid nesting
       future = asyncio.run_coroutine_threadsafe(coro, loop)
       return future.result(timeout=_APPROVAL_TIMEOUT_S)
   else:
       return asyncio.run(coro)
   ```
2. Remove the `asyncio.set_event_loop(new_loop)` call entirely.
3. Apply identical fix to both `approval_manager.py` and `policy.py`.

**Acceptance:**
- `pytest tests/test_approval_async_from_sync.py` — new test that calls
  `assert_allowed` from a coroutine running in `asyncio.run()`. Must not raise
  `RuntimeError: Event loop is closed`.
- No `asyncio.set_event_loop` calls remain in the approval paths.

---

### Plan R2 — Fix ACP stdio loop silent exception swallow [NEW] [MEDIUM]

**Why:** `teaagent/acp_adapter.py:349` — `except Exception: pass` silently
drops any internal error in the ACP request handler. IDE clients (VS Code, Zed,
JetBrains) hang waiting for a response that never comes.

**Steps:**
1. Replace the bare `except Exception: pass` block with:
   ```python
   except json.JSONDecodeError:
       continue
   except Exception as exc:
       logger.exception("ACP handler error: %s", exc)
       error_response = {
           "jsonrpc": "2.0",
           "id": request_data.get("id"),
           "error": {"code": -32603, "message": str(exc)},
       }
       print(json.dumps(error_response, ensure_ascii=False), file=sys.stdout)
       sys.stdout.flush()
   ```
2. Add `logger = logging.getLogger(__name__)` if not present.

**Acceptance:**
- `pytest tests/test_acp_adapter_error_response.py` — inject a handler that
  raises, confirm error JSON is emitted to stdout.
- No bare `except Exception: pass` in the ACP loop.

---

### Plan R3 — Open concurrency items (carry-forward from comprehensive-audit)

| ID | Item | Severity | Plan |
|---|---|---|---|
| C-H3 | `ContextBus._reconnect()` closes all thread connections | High | `docs/plans/remediation-roadmap.md` P2.1 ✅ |
| C-H6 | `archive_to_rag` non-transactional | High | P2.2 (open) |
| C-H2 | Multiple `AuditLogger` same path breaks hash chain | High | P2.3 ✅ |
| C-M11 | Swarm heartbeat does not cancel executor work | Medium | P2.5 ✅ |
| C-M12 | Parallel swarm git on same root | Medium | Open |
| C-M13 | `RunStore.logger_for_result` race | Medium | P2.4 ✅ |

**P2.2 — `archive_to_rag` transactional fix (open):**
Wrap `archive_to_rag` in a single SQLite transaction. Use `BEGIN IMMEDIATE`
to serialize against concurrent publish.
Acceptance: `test_archive_to_rag_concurrent_publish` passes without hash-chain
corruption.

**C-M12 — Parallel swarm git on same root fix (open):**
Guard `git stash` / `git checkout` operations in `git_sandbox.py` with a
per-root file lock. Use `fcntl.flock` or `threading.Lock` keyed by resolved
absolute path.
Acceptance: `test_parallel_swarm_same_root_no_stash_collision` passes.

---

## Dimension 3 — Maintainability

### Plan M1 — Document and guard code_mode backend trust model [NEW] [MEDIUM]

See Plan S2 above — security and maintainability overlap here.

---

### Plan M2 — Add test coverage for 30 untested security-critical modules [NEW] [MEDIUM]

**Why:** `approval_manager`, `security_env`, `ssh_signatures`, `storage`,
`tls_server`, `vote_relay`, `mcp_trust`, `plugin_system`, `read_only_gate`,
`readiness`, `subagent_run_context` have no test files.

**Phased approach (prioritized by threat-model impact):**

**Sprint 1 — Highest-risk modules (1 week):**
- `security_env.py` — test all env-var flags: `allow_dev_signatures()`,
  `strict_local_services()`, `plugins_strict_audit()`.
- `read_only_gate.py` — test gate blocks write operations in read-only mode.
- `mcp_trust.py` — test per-server trust levels and default behaviors.

**Sprint 2 — Infrastructure modules (1 week):**
- `storage.py` — test atomic write, read, and concurrent access.
- `tls_server.py` — test TLS handshake with self-signed cert.
- `vote_relay.py` — test rate limiting and auth_policy enforcement.

**Sprint 3 — Agent lifecycle modules (1 week):**
- `approval_manager.py` — dedicated unit tests for `ApprovalManager`
  (currently only tested via integration paths).
- `ssh_signatures.py` — test verify path and dev-signature fallback gate.
- `readiness.py` — test health check outputs.

**Acceptance:** Each sprint produces ≥1 test file per module. All new tests
pass in `uv run pytest`. Coverage report shows the module is exercised.

---

### Plan M3 — Bound `_GRAPH_BY_ROOT` process-global dict [NEW] [LOW]

**Why:** `teaagent/code_analysis/_tools.py:303` — `_GRAPH_BY_ROOT` grows
unbounded. In long-running processes or automation that switches workspaces,
this is a memory leak.

**Steps:**
1. Replace `dict` with a simple bounded dict (max 8 entries, LRU eviction):
   ```python
   from collections import OrderedDict
   _MAX_GRAPH_CACHE = 8
   _GRAPH_BY_ROOT: OrderedDict[str, KnowledgeGraph] = OrderedDict()
   ```
2. In `_ingest_graph`, after adding to dict, trim oldest entries:
   ```python
   while len(_GRAPH_BY_ROOT) > _MAX_GRAPH_CACHE:
       _GRAPH_BY_ROOT.popitem(last=False)
   ```
3. Export `clear_graph_cache()` for test teardown.

**Acceptance:**
- `pytest tests/test_code_analysis_graph_cache.py` — fill 9 roots, confirm
  oldest is evicted and dict stays ≤ 8.

---

### Plan M4 — Add `__all__` to high-traffic public modules [LOW]

**Why:** 30+ modules in `teaagent/` lack `__all__`. Wildcard imports produce
undefined public surfaces. Causes IDE confusion and accidental re-exports.

**Approach:** Focus on modules with external consumers first:
`approval_manager`, `errors`, `tools`, `runner/__init__`, `governance/__init__`,
`schema`, `policy`.

Add `__all__ = [...]` listing the public classes and functions.

**Acceptance:** `grep -rn "from teaagent.X import \*"` in dependent code finds
no unexpected names. Mypy `--no-implicit-reexport` passes.

---

## Dimension 4 — Test Coverage

### Plan T1 — Threat-model adversarial tests for open S-H gaps

**Why:** S-H3, S-H4 (shell normalization) and S-H8 (plugin fail-open) from the
prior audit have no dedicated adversarial test matrix.

**Shell normalization (S-H4):**
```
tests/test_shell_normalization_adversarial.py
```
Cover:
- Brace expansion: `/pr{od,oduction}/data`
- Process substitution: `<(echo /prod)`
- Encoded chars: `\x72m`, `$'\x72\x6d'`
- Unicode homoglyphs in path names
- Nested quotes: `"rm '-rf'"`, `'"rm" "-rf"'`

**Plugin fail-open (S-H8):**
```
tests/test_plugin_audit_fail_closed.py
```
Cover:
- Plugin with missing manifest → rejected
- Plugin with invalid entry_point → rejected
- `TEAAGENT_PLUGINS_STRICT=0` vs `=1` behavior

**Acceptance:** All new tests in CI. No regressions in existing `test_policy.py`.

---

### Plan T2 — `archive_to_rag` concurrent write test

Covered in Plan R3 (`C-H6`).

---

### Plan T3 — Acceptance tests for AuditLevel.L3 behavior

**Why:** After Plan S1 corrects the L3 claim, ensure audit levels have
dedicated acceptance tests so the behavior can't regress silently.

```
tests/test_audit_levels.py
```
Cover:
- L0: only tool name and timestamp logged
- L1: arguments truncated, no secrets
- L2: redaction applied
- L3: no redaction, no encryption (document explicitly)

**Acceptance:** Tests pass. If encryption is later added (Plan S1 Phase B),
tests extend without breaking.

---

## Dimension 5 — Documentation

### Plan D1 — Fix all stale / false claims in existing docs [HIGH]

**Immediate corrections (same PR):**

1. **`teaagent/audit.py:166`** — Remove "encrypted at rest". See Plan S1 Phase A.

2. **`docs/analysis/system-transparency-risk-audit-2026-05-31.md`** — Remove two
   false rows:
   - "Hook registry execution ignored returned values" — **false**, hooks are used.
   - "External cx/qmd without timeout" — **false**, both have `timeout=30`.

3. **`docs/threat-model.md`** — Add row for S-NEW1 (L3 plaintext).

4. **`docs/specs/security-spec.md`** — Verify no L3 encryption claim exists; add
   explicit statement: "L3 audit level writes unencrypted full payloads. Do not
   use L3 in deployments with data residency requirements without enabling
   audit-encryption extra."

**Acceptance:**
- `grep -rn "encrypted at rest" teaagent/ docs/` returns nothing except this plan.
- `grep -rn "hook.*ignored\|ignored.*hook" docs/analysis/system-transparency-risk-audit-2026-05-31.md` returns nothing.

---

### Plan D2 — Close code_mode sandbox documentation gap [MEDIUM]

**Why:** There is no single doc explaining when to use `ChildProcessCodeModeBackend`
vs `ContainerCodeModeBackend`. Users may choose the wrong one.

**Steps:**
1. Update `docs/specs/security-spec.md` with a "Code Mode Trust Boundary" section:

   | Backend | Isolation | Use when |
   |---|---|---|
   | `ChildProcessCodeModeBackend` | Fork + SAFE_BUILTINS + resource limits | Trusted user inputs only |
   | `ContainerCodeModeBackend` | Docker with `--network none`, non-root user | Untrusted or multi-tenant |

2. Add a warning in `teaagent/code_mode/_child_process.py` docstring.
3. Update `docs/USAGE.md` to recommend `ContainerCodeModeBackend` for any
   scenario involving user-supplied code.

---

### Plan D3 — ADR for async loop management pattern [MEDIUM]

**Why:** The async-from-sync pattern appears in at least two places
(`approval_manager.py`, `policy.py`) and is tricky. Document the correct
pattern to prevent future regressions.

Create `docs/adr/009-async-from-sync-pattern.md`:
- Context: approval checks are called from sync tool dispatch but use async
  I/O for signature relay and JIT server.
- Decision: Use `run_coroutine_threadsafe` when inside a running loop; use
  `asyncio.run` otherwise. Never call `asyncio.set_event_loop` from within
  an active request context.
- Consequences: Approval paths are thread-safe without blocking the main event loop.

---

### Plan D4 — Docs index and freshness tracking [LOW]

**Why:** The docs/ directory now has 70+ files. There is no index or freshness
policy. Stale docs cause the same class of risk as stale code.

**Steps:**
1. Create `docs/INDEX.md` — one-line description per doc, date last verified.
2. Add a CI check: any doc older than 90 days without a `last-verified` header
   emits a warning (not a hard failure).
3. Establish a quarterly doc review ritual: pick the 5 oldest unverified docs
   and update or archive them.

---

## Dimension 6 — Operational

### Plan O1 — Bound `_GRAPH_BY_ROOT` cache [NEW] [LOW]

See Plan M3.

---

### Plan O2 — ACP error visibility for IDE integrations [NEW] [MEDIUM]

See Plan R2.

---

### Plan O3 — Audit export tiering [MEDIUM]

**Why:** The threat-model notes "over-redaction reduces debuggability — export
tiers future work." Operators need different views of the audit log for
different consumers (CI, security team, developer).

**Design:**
- `teaagent audit export --tier dev` — L2 redaction, timestamps, tool names
- `teaagent audit export --tier security` — L3 payload, no redaction (requires
  auth token)
- `teaagent audit export --tier ci` — L1, summary only

**Acceptance:**
- `teaagent audit export --tier dev` produces valid JSON without secrets.
- `teaagent audit export --tier security` requires `TEAAGENT_AUDIT_EXPORT_TOKEN`.

---

### Plan O4 — `approve_session` scope creep documentation and operator alert [MEDIUM]

**Why:** `approve_session(tool_name)` grants approval for ALL future calls to
that tool in the session (S-H2). This is documented as "by design" but no
operator-visible warning is emitted when a session-level approval is granted.

**Steps:**
1. When `approve_session` is called, emit a structured audit event:
   `{"event": "session_approval_granted", "tool": tool_name, "scope": "session"}`.
2. Add a TUI/CLI warning: "Session approval granted for `tool_name`. All future
   calls will be auto-approved."
3. Update `docs/threat-model.md` S-H2 row with this mitigation.

---

### Plan O5 — Resource monitor for long-running agents [LOW]

**Why:** `teaagent/resource_monitor.py` exists but its integration path is
unclear. Long-running agents without resource caps can exhaust memory or CPU.

**Steps:**
1. Verify `ResourceMonitor` is wired into `AgentRunner.__init__` by default.
2. If not, add `resource_monitor: ResourceMonitor | None = None` to `AgentRunner`
   and call `monitor.check()` at each iteration.
3. Document `--max-memory-mb` and `--max-cpu-percent` CLI flags if they exist,
   or add them.

---

## Execution Priority Matrix

| Priority | Plans | Target |
|---|---|---|
| **P0 — This week** | S1-A (audit docfix), D1 (stale claims), R2 (ACP silent errors) | Correctness + trust |
| **P1 — Next 2 weeks** | R1 (async loop), T1 (adversarial tests), S2 (code_mode docs), M2-Sprint1 | Security hardening |
| **P2 — Next month** | R3 open items, M2-Sprint2, T3 (audit level tests), D2, D3 | Reliability + test coverage |
| **P3 — Quarter** | M2-Sprint3, M3, M4, D4, O3, O4, O5, S1-B (encryption) | Maintainability + ops |

---

## Human Review Gates

The following plans require Human Review before execution:

| Plan | Gate reason |
|---|---|
| S1-B (L3 encryption) | Changes audit write path — could corrupt existing audit logs if not backward-compatible |
| R1 (async loop) | Touches every approval check — any regression blocks all tool execution |
| O3 (audit export tiers) | Introduces access control on audit data — security design review needed |
| M2-Sprint2 (tls_server tests) | Any test that starts a real TLS server needs network/port allocation review |

No code changes are made by this plan document. All items above require
explicit implementation approval before work begins.
