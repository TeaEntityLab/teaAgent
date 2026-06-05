# New Risk Findings — 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. All findings
> were absorbed into the risk register
> (`docs/security/risk-register-and-threat-model-2026-06-02.md`) and tracked
> through the Phase 0 trust repair work. For current risk status, use the risk
> register. For closure evidence, use
> `docs/work-log/phase-0-governance-closure-report-2026-06-04.md`.

**Method:** cx-cli semantic navigation + grep pattern sweep across 312 source
files + 158 MD docs. Read-only audit. No code changes.

**Baseline:** `docs/analysis/comprehensive-audit-2026-05-29.md` and
`docs/analysis/system-transparency-risk-audit-2026-05-31.md` are authoritative
for all previously documented risks. This document records **new or
contradictory findings only**.

---

## Corrections to Prior Audit Claims

| Prior claim | File | Actual state | Action |
|---|---|---|---|
| "Hook registry execution ignored returned values" (system-transparency-risk-audit) | `teaagent/hooks.py:131`, `teaagent/tools.py:192-204` | Return values ARE used — `run_pre_hooks` returns modified args; `tools.py` assigns `arguments = modified_args` when non-None | Remove stale risk row from system-transparency-risk-audit |
| "External cx and qmd subprocess adapters run without an explicit timeout" (system-transparency-risk-audit) | `teaagent/external_backends.py:22,425` | Both have `timeout: int = 30` and handle `subprocess.TimeoutExpired` | Remove stale risk row |

---

## New Risk Findings

### S-NEW1 — AuditLevel.L3 "encrypted at rest" claim is FALSE [HIGH]

| Field | Value |
|---|---|
| File | `teaagent/audit.py:166` |
| Evidence | Docstring: `L3: Full local trace (all data, encrypted at rest)`. Actual L3 branch (lines 185–190): returns raw unredacted payload without encryption. |
| Impact | Operators relying on L3 for compliance assume encryption that does not exist. Sensitive tool arguments, API keys passed as tool inputs, and personal data in prompts are written in plaintext at L3. |
| Blast radius | Any deployment that sets `audit_level = 'L3'` under a compliance or data-handling requirement. |
| Mitigation options | (a) Remove "encrypted at rest" from the docstring and update threat model — **immediate, low cost**. (b) Implement AES-GCM encryption via a key derived from a machine secret — **medium cost, needed for compliance use**. |
| Plan ref | See Plan D1 below |

---

### R-NEW1 — `asyncio.run()` + new-loop fallback in synchronous approval paths is fragile [HIGH]

| Field | Value |
|---|---|
| Files | `teaagent/approval_manager.py:514-524`, `teaagent/policy.py:523-533` |
| Evidence | Both call `asyncio.run(coro)` or `new_loop.run_until_complete(coro)` in a try/except. The check is `asyncio.get_event_loop().is_running()`. The new-loop path calls `asyncio.set_event_loop(new_loop)` — this sets the thread-local event loop globally for that thread, which affects any subsequent `asyncio.get_event_loop()` calls in the same thread. |
| Impact | In a threaded server context (gateway, TLS server, MCP HTTP), setting and then closing a new event loop mid-thread can leave the thread-local loop in a closed state, causing `RuntimeError: Event loop is closed` on any subsequent async operation in that thread. |
| Blast radius | `ApprovalManager` and `ApprovalPolicy` are used on every tool execution that requires approval. The failure mode is silent if caught by a broad except upstream. |
| Mitigation | Use `asyncio.run_coroutine_threadsafe(coro, running_loop)` when a loop is running, without modifying thread-local loop state. |
| Plan ref | See Plan R1 below |

---

### R-NEW2 — `acp_adapter.py` bare `except Exception: pass` in main stdio loop [MEDIUM]

| Field | Value |
|---|---|
| File | `teaagent/acp_adapter.py:349` |
| Evidence | The main ACP JSON-RPC stdio loop catches `Exception` and passes silently. A tool dispatch error, a schema validation error, or an internal crash returns nothing to the caller and is not logged. |
| Impact | ACP clients (VS Code, Zed, JetBrains) receive no response for errored requests, causing hangs or silent failures that are invisible in logs. |
| Mitigation | Replace with a logged error response: `log.exception(...)` + send an ACP error response JSON to stdout. |
| Plan ref | See Plan R2 below |

---

### O-NEW1 — `_GRAPH_BY_ROOT` process-global dict grows unbounded [LOW]

| Field | Value |
|---|---|
| File | `teaagent/code_analysis/_tools.py:303` |
| Evidence | `_GRAPH_BY_ROOT: dict[str, KnowledgeGraph] = {}` is a module-level dict. Each call to `_ingest_graph` with a new root path appends a new `KnowledgeGraph` entry. It is never evicted. |
| Impact | Long-running agent processes that analyze multiple workspaces (e.g., via `--root`) accumulate in-memory `KnowledgeGraph` objects indefinitely. Each graph holds AST node data for all files in the workspace. |
| Blast radius | Low in single-workspace sessions. High in multi-workspace or automation contexts. |
| Mitigation | Bound dict size (LRU eviction at N=5 roots) or add explicit cache-clear API. **Partial (2026-05-31):** graphs are keyed per workspace root (`scope_key`), eliminating cross-root contamination; eviction still open. |
| Plan ref | See Plan O1 below |

---

### M-NEW1 — `code_mode` in-process `exec()` relies on `SAFE_BUILTINS` restriction [MEDIUM]

| Field | Value |
|---|---|
| File | `teaagent/code_mode/_child_process.py:65` |
| Evidence | `exec(compile(code, ...), namespace, namespace)` where `namespace['__builtins__'] = SAFE_BUILTINS`. `SAFE_BUILTINS` restricts to `abs`, `dict`, `len`, etc. — no `__import__`, no `open`, no `os`. Resource limits are applied via `_apply_resource_limits` (CPU, memory, nproc). Runs in a forked child process. |
| Assessment | Better than previously indicated: (1) forked child process isolates from parent, (2) resource limits cap CPU/memory/nproc, (3) `SAFE_BUILTINS` blocks common escape paths. Risk is residual: fork shares file descriptors and memory-mapped regions with parent. A SAFE_BUILTINS bypass via ctypes/bytearray can still read parent memory on some platforms. |
| Mitigation | For high-trust scenarios, `ContainerCodeModeBackend` (Docker) is the recommended path. `ChildProcessCodeModeBackend` should be documented as "trusted-user only" in the code_mode docs. |
| Plan ref | See Plan M1 below |

---

### M-NEW2 — 30 security-critical modules lack acceptance tests [MEDIUM]

| Field | Value |
|---|---|
| Evidence | `approval_manager`, `security_env`, `ssh_signatures`, `storage`, `tls_server`, `vote_relay`, `mcp_trust`, `plugin_system`, `read_only_gate`, `readiness`, `subagent_run_context` have no matching test files. |
| Impact | Regressions in security boundaries go undetected by CI. Threat-model claims for these modules are unverified. |
| Plan ref | See Plan M2 below |

---

### D-NEW1 — AuditLevel.L3 documentation fraud [HIGH]

Duplicate of S-NEW1. Both the security risk (no encryption) and the documentation risk (misleading claim) must be addressed. See Plan D1.

---

## Risk Status Summary

| ID | Severity | Type | Status |
|---|---|---|---|
| S-NEW1 / D-NEW1 | HIGH | Security + Documentation | Open — requires docfix + optional encryption impl |
| R-NEW1 | HIGH | Reliability | Open — fragile async loop management |
| R-NEW2 | MEDIUM | Reliability | Open — ACP silent failures |
| M-NEW1 (code_mode) | MEDIUM | Security/Maintainability | Partially mitigated — needs documentation |
| M-NEW2 | MEDIUM | Test Coverage | Open — 30 modules untested |
| O-NEW1 | LOW | Operational | Open — unbounded graph cache |

---

## Stale / False Risk Rows to Remove

The following rows in `docs/analysis/system-transparency-risk-audit-2026-05-31.md`
are **incorrect** and should be retracted:

1. "Hook registry supports argument and result mutation, but registry execution
   ignored returned values" — **FALSE** as of current code.
2. "External cx and qmd subprocess adapters run without an explicit timeout" —
   **FALSE**, both have `timeout=30` and handle `TimeoutExpired`.
