# Security Risk Assessment — teaAgent

**Date:** 2026-06-02  
**Reviewer:** Security Review (automated + manual)  
**Scope:** Full source under `teaagent/`  
**Method:** Static code analysis, control-flow tracing, adversarial scenario modeling

> **Note on line-number references:** Source file references (e.g., `audit.py:127`) were accurate as of 2026-06-02 but may drift as the codebase evolves. Verify against current source before acting on specific line references.

---

## Reflective Risk Gate

### Goal
Identify, document, and prioritize every exploitable security weakness in the teaAgent codebase so that the team can make informed hardening decisions before expanding the agent's production footprint or capability surface.

### Stakeholders
- **Developer/operator** who runs agents against their local workspace
- **Team users** who share a multi-agent federation workspace
- **Third-party MCP servers** that are granted tool trust

### Assets at Risk
- Local filesystem (workspace files, git history)
- Anthropic API spend (cost budget)
- Audit log (tamper evidence)
- SSH/OAuth credentials in environment
- MCP tool execution permissions

---

## Threat Model

Attacker classes considered:

| Class | Entry Point | Goal |
|-------|-------------|------|
| **Prompt-injected agent** | Malicious content in a file the agent reads | Escalate permissions, exfiltrate, exceed budget |
| **Rogue subagent** | Spawned with weaker isolation | Inherit parent approvals or escape sandbox |
| **Compromised MCP server** | Gained `trusted=True` in trust policy | Execute arbitrary tools after trust expires |
| **Insider / local attacker** | Write access to audit log file | Forge/delete audit entries, defeat accountability |
| **Peer signature replay** | Captured approval signature in multi-sig flow | Re-authorize a high-risk operation without fresh consent |

---

## Risk Register

### SEC-01 · CRITICAL · Audit HMAC key ephemeral — chain authentication unverifiable across runs

**File:** [`teaagent/audit.py:127`](../../teaagent/audit.py)  
**Severity:** Critical | **Likelihood:** Certain | **Impact:** Complete loss of tamper evidence

**Description:**  
`AuditLogger._chain_key` is generated per-process via `os.urandom(32)`. It is never persisted. The HMAC (`chain_hmac`) stored in each event is keyed by this ephemeral key. After any process restart the original key is gone.

`audit_export.py:56` calls `verify_audit_chain(log_path)` **without** a `secret_key` argument, so HMAC is never checked during export — only the SHA-256 hash chain is verified.

**Defeat scenario:**  
An attacker with write access to the `.teaagent/runs/*.jsonl` file can:
1. Read all events.
2. Modify, insert, or delete events at will.
3. Recompute all SHA-256 hashes, updating `prev_hash` and `hash` fields to restore chain validity.
4. `verify_audit_chain` will return `valid=True`.

The hash chain is tamper-evident only when the key is available. Without persisting and re-loading the key, the HMAC adds zero protection for any multi-run or post-restart scenario.

**Recommendation (immediate):** Persist the HMAC key to `~/.teaagent/run-keys/<run_id>.key` with `chmod 600`, and pass it to `verify_audit_chain` during export. Alternatively, use a workspace-level signing key.

**Recommendation (design):** Adopt Sigstore/SSH-signed append-only log so integrity is externally verifiable without a secret key.

---

### SEC-02 · HIGH · MCP server trust expiry never enforced at call time

**File:** [`teaagent/mcp_trust.py:152`](../../teaagent/mcp_trust.py)  
**Severity:** High | **Likelihood:** High | **Impact:** Permanently trusted rogue server

**Description:**  
`is_server_trust_expired()` is defined (line 220) but is called **nowhere** in the hot path. `apply_mcp_trust_hooks()` calls `merged_tool_filters()`, which iterates `policy.servers.values()` and unconditionally merges `allowed_tools` regardless of `expires_at`.

```python
# mcp_trust.py:141-149 — expires_at never checked here
def merged_tool_filters(policy):
    for server in policy.servers.values():
        allowed.update(server.allowed_tools)   # expired entries included
```

**Defeat scenario:**  
1. Operator grants `trusted=True` to `some-mcp-server` with `ttl=3600` (1 hour).
2. After 1 hour the entry expires logically but the registered pre-hook is not refreshed.
3. The server retains full tool access indefinitely until the process restarts and reloads the policy.

**Recommendation (immediate):** Add a check in `merged_tool_filters()` and/or in the pre-hook callback: `if not is_server_trust_expired(server_trust)`. Also schedule periodic policy reload (e.g. every 60 s).

---

### SEC-03 · HIGH · `allow_all_destructive=True` is a total permission bypass

**File:** [`teaagent/approval_manager.py:203`](../../teaagent/approval_manager.py)  
**Severity:** High | **Likelihood:** Low (intentional flag) | **Impact:** All destructive tools unrestricted

**Description:**  
`PermissionModeEnforcer.check()` short-circuits to `None` (allowed) whenever `allow_all_destructive=True` and the tool is destructive — regardless of mode, plan contract, or JIT state:

```python
if destructive and self.allow_all_destructive:
    return None     # bypass everything
```

This flag can be set by any caller constructing `ApprovalManager`. If a code path inadvertently passes `allow_all_destructive=True` (e.g. via an automation template or config deserialisation), it silently disables the entire permission gate.

**Defeat scenario:**  
Automation template config `"allow_all_destructive": true` in `.teaagent/config.json` deserialised without strict schema validation would activate this bypass.

**Recommendation:** Require `DANGER_FULL_ACCESS` permission mode for this flag to take effect; reject it in any other mode. Log a prominent warning when this flag is set.

---

### SEC-04 · HIGH · Chat/agent mode defaults to unlimited cost (`max_estimated_cost_cents=0`)

**File:** [`teaagent/chat_agent.py:70`](../../teaagent/chat_agent.py)  
**Severity:** High | **Likelihood:** Certain | **Impact:** Unbounded API spend

**Description:**  
`ChatAgentConfig.max_estimated_cost_cents` defaults to `0`. At `runner/_core.py:142`:

```python
def _assert_cost_budget(self, cost_cents: float) -> None:
    if self.budget.max_estimated_cost_cents <= 0:
        return   # no budget enforcement at all
```

A runaway chat session or prompt-injection loop in chat mode has no cost ceiling unless the operator explicitly sets a cap. In practice most users don't set this, and the TUI previously displayed `$0.00` (known bug CG-03 partially fixed but underlying default remains 0).

**Recommendation (immediate):** Change default to a safe non-zero value (e.g. 500 cents / $5). Prompt the user on first run if no budget is configured.

---

### SEC-05 · HIGH · Cost accounting trusts LLM adapter's output dict — injectable

**File:** [`teaagent/runner/_core.py:322-325`](../../teaagent/runner/_core.py)  
**Severity:** High | **Likelihood:** Low | **Impact:** Budget cap defeated

**Description:**  
After each `decide()` call, the runner reads cost from the context dict that `decide()` populates:

```python
cost_cents = context.get('_cost_cents', cost_cents)
input_tokens = context.get('_input_tokens', input_tokens)
```

If the LLM adapter is malicious or if an adversarial prompt causes the adapter to write falsified values back into `context['_cost_cents']` (e.g. by returning `0.0`), the budget enforcement is silently bypassed.

**Defeat scenario:**  
A prompt injection that instructs the model to emit a structured response that causes the adapter to zero out `_cost_cents` before returning — the budget check then always passes.

**Recommendation:** Cost should come from a side-channel outside the LLM response (e.g. API response headers or a trusted accounting layer), not from fields the decide function can write.

---

### SEC-06 · HIGH · Bidirectional JIT state sync can leak session approvals to subagents

**File:** [`teaagent/policy.py:110-135`](../../teaagent/policy.py)  
**Severity:** High | **Likelihood:** Medium | **Impact:** Privilege escalation via approval inheritance

**Description:**  
`ApprovalPolicy.assert_allowed()` performs a **bidirectional** sync of `session_approved_tools` between the caller's `jit_state` and the internal `ApprovalManager`'s state:

```python
# Before check: parent state → manager
manager_state.session_approved_tools.update(jit_state.session_approved_tools)

# After check: manager state → parent (picks up newly granted tools)
jit_state.session_approved_tools.update(manager_state.session_approved_tools)
```

If a parent agent shares its `jit_state` object with a subagent's `ApprovalPolicy` (directly or via a shared context), tools approved for the parent session are automatically inherited by the subagent. The subagent can then call those tools without prompting.

**Defeat scenario:**  
Parent has session-approved `workspace_run_shell_mutate`. Subagent is constructed with `isolation=shared` and receives the same `jit_state`. Subagent can now run shell mutations without additional approval.

**Recommendation:** Pass a **copy** of the JIT state to subagents, or use one-directional sync (parent→child only at spawn time, never child→parent). Add an explicit `clone_for_subagent()` method.

---

### SEC-07 · HIGH · Docker subagent runs as root with no network isolation

**File:** [`teaagent/subagents/_isolation.py:222-275`](../../teaagent/subagents/_isolation.py)  
**Severity:** High | **Likelihood:** High | **Impact:** Container escape / data exfiltration

**Description:**  
The Docker isolation mode creates containers without:
- `--user` (runs as root inside)
- `--network none` (full internet access)
- `--read-only` root filesystem (only workspace is read-only)
- `--cap-drop ALL` (all Linux capabilities)
- Security profile (no seccomp/apparmor)

```python
docker_cmd = ['docker', 'run', '-d', '--name', f'teaagent-subagent-{session_key}',
              '-v', f'{temp_dir}:/workspace:ro', '-w', '/workspace',
              'python:3.11-slim', 'sleep', 'infinity']
```

A subagent running in this container can exfiltrate data, make outbound network calls, or attempt container escape.

**Recommendation (immediate):** Add `--user 65534:65534 --network none --cap-drop ALL --read-only --security-opt no-new-privileges` to the Docker command. Use a minimal purpose-built image rather than `python:3.11-slim`.

---

### SEC-08 · MEDIUM · `directory-snapshot` isolation provides no OS-level process isolation

**File:** [`teaagent/subagents/_isolation.py:181-200`](../../teaagent/subagents/_isolation.py)  
**Severity:** Medium | **Likelihood:** Certain | **Impact:** Subagent escapes to host filesystem

**Description:**  
The deprecation warning for the `container` alias explicitly says _"does not provide OS-level container isolation."_ However, this mode (`directory-snapshot`) is still available and the deprecation only applies to the old name. The new name `directory-snapshot` appears safe-ish by name but provides only file-system-level isolation within the snapshot, not process isolation.

A subagent running under `directory-snapshot` can:
- Read the host's `/etc/`, `/proc/`, `~/.ssh/`
- Spawn child processes with access to host environment
- Make network connections

**Recommendation:** Remove `directory-snapshot` from production isolation options, or add a prominent runtime warning that it provides no process isolation.

---

### SEC-09 · MEDIUM · Multi-sig approval hash has 1-hour replay window

**File:** [`teaagent/approval_manager.py:393`](../../teaagent/approval_manager.py)  
**Severity:** Medium | **Likelihood:** Medium | **Impact:** High-risk operation approved without fresh consent

**Description:**  
The approval hash used for multi-sig quorum includes a `time_window` binned at hourly granularity:

```python
'time_window': int(time.time() / 3600)
```

A valid signature captured at the start of an hour is valid for up to 59 minutes and 59 seconds for any identical operation. If a peer signature is intercepted or stored, it can be replayed within the same hour bucket.

**Duplicate implementation risk:** The same hash logic is implemented independently in both `approval_manager.py:387-398` and `policy.py:379-398`. These two implementations could diverge.

**Recommendation:** Use a monotonically increasing nonce or a shorter window (e.g. 5 minutes). Deduplicate the hash function to a single canonical location.

---

### SEC-10 · MEDIUM · `inspect` shell commands allow reading secrets from the filesystem

**File:** [`teaagent/workspace_tools/_shell.py:175-211`](../../teaagent/workspace_tools/_shell.py)  
**Severity:** Medium | **Likelihood:** Medium | **Impact:** Secret/credential exfiltration

**Description:**  
`_INSPECT_EXECUTABLES` includes `cat`, `head`, `tail`. These tools pass the read-only classify check and can be executed without destructive approval:

```python
_INSPECT_EXECUTABLES = frozenset({'pwd', 'ls', 'rg', 'grep', 'cat', 'head', 'tail', 'wc'})
```

An agent that has only inspect approval can execute:
- `cat ~/.ssh/id_rsa` — reads SSH private key
- `cat /etc/shadow` (if permissions allow)
- `head -1000 .env` — reads environment secrets

These are classified as "inspect" (no side effects) but can leak secrets from outside the workspace.

**Recommendation:** Remove `cat`, `head`, `tail` from `_INSPECT_EXECUTABLES` or restrict them to workspace-relative paths only. The `workspace_read_file` tool is the correct abstraction.

---

### SEC-11 · MEDIUM · UndoJournal does not cover shell mutations — false undo safety

**File:** [`teaagent/run_undo.py:48-55`](../../teaagent/run_undo.py)  
**Severity:** Medium | **Likelihood:** High | **Impact:** User believes undo restored all changes when it didn't

**Description:**  
`_PATH_WRITE_TOOLS` covers only `workspace_write_file`, `workspace_apply_patch`, `workspace_edit_at_hash`. Shell mutations via `workspace_run_shell_mutate` are **not tracked** and therefore not undoable:

```python
_PATH_WRITE_TOOLS = frozenset({
    'workspace_write_file',
    'workspace_apply_patch',
    'workspace_edit_at_hash',
})
```

Known bug CG-02 in the daily-driver review identified this gap. The UI presents "undo available" without distinguishing shell-mutation runs from file-only runs, giving users false confidence.

**Recommendation:** When `workspace_run_shell_mutate` is in the tool history, add an explicit warning that undo is **partial** and shell side effects are not reversed.

---

### SEC-12 · MEDIUM · Audit disk errors silenced — events dropped without alert

**File:** [`teaagent/audit.py:298-307`](../../teaagent/audit.py)  
**Severity:** Medium | **Likelihood:** Low | **Impact:** Missing audit trail without operator awareness

**Description:**  
When `os.fsync()` raises `OSError`, the audit logger catches the exception, records an in-memory `_disk_write_error` event, and then retries after 30 seconds:

```python
except OSError as exc:
    with self._lock:
        self._disk_error = exc
        self._last_disk_error_time = time.monotonic()
```

The audit file continues to fill in memory only. If a disk-full attack is sustained for >30 seconds, no audit events reach disk. There is no notification to the operator.

**Defeat scenario:** An attacker who can trigger repeated disk full (or remove write permissions from `.teaagent/runs/`) causes the audit to silently degrade to in-memory only. After process exit, all events are lost.

**Recommendation:** Emit a stderr warning (or OS notification) when disk writes fail. After N consecutive failures, raise `BudgetExceededError` or halt the run.

---

### SEC-13 · MEDIUM · Test-mock anti-patterns hide real cost/budget bugs (CG-16)

**Files:** [`tests/test_chat_agent.py`](../../tests/test_chat_agent.py), multiple acceptance tests  
**Severity:** Medium | **Likelihood:** High | **Impact:** Budget enforcement bugs undetected until production

**Description:**  
Key security-critical paths are mocked in tests, bypassing real logic:

- **`create_llm_adapter` mocked in every chat test** — the actual cost tracking path (`context['_cost_cents']`) is never exercised with realistic values. Tests cannot detect if an adapter fails to write cost data back to context.
- **Approval flows mocked** — `patch('builtins.input', return_value='yes')` bypasses the actual TTY prompt logic and doesn't test denial paths.
- **Audit HMAC tests absent** — no test verifies that `verify_audit_chain` with the correct `secret_key` succeeds and fails with a wrong key.

```python
# test_chat_agent.py:381 — real adapter never used in tests
with patch('teaagent.cli.create_llm_adapter', return_value=adapter):
```

Known bug CG-03 (cost always shown as $0) was present for months precisely because the cost path was mocked out in tests.

**Recommendation:**  
- Add integration tests that run the full runner loop with a stub (but real) adapter that returns realistic cost values, and verify `RunResult.cost_cents > 0`.
- Add a test that verifies `verify_audit_chain` with and without the correct HMAC key.
- Test `is_server_trust_expired` is actually called in the enforcement path (currently it's dead call).

---

### SEC-14 · LOW · `preapproved_call_ids` deprecated but functional — bypass vector remains

**File:** [`teaagent/policy.py:101-107`](../../teaagent/policy.py)  
**Severity:** Low | **Likelihood:** Low | **Impact:** Scoped approval bypass

**Description:**  
A deprecation warning is issued when `preapproved_call_ids` is non-empty, but the logic is still fully operational:

```python
if self.preapproved_call_ids:
    warnings.warn('preapproved_call_ids is deprecated...', DeprecationWarning)
# ... and it still works
```

Old integrations (or adversarial callers) using this field can pre-approve arbitrary call IDs without HMAC argument-digest verification.

**Recommendation:** On the next major version, remove the functionality entirely and raise `ValueError` instead of `DeprecationWarning`.

---

### SEC-15 · LOW · `allow_dev_signatures` env-var lowers multi-sig security globally

**File:** [`teaagent/security_env.py:12-14`](../../teaagent/security_env.py)  
**Severity:** Low | **Likelihood:** Low | **Impact:** Signature forgery accepted in production

**Description:**  
When `TEAAGENT_ALLOW_DEV_SIGNATURES=1`, the verification fallback accepts a simple SHA-256 of `(message + pubkey)` instead of a real SSH signature. This is documented as "never for production WAN surfaces" but there is no runtime guard preventing this flag from being set in a production deployment.

```python
if not allow_dev_signatures:
    return False
expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
return secrets.compare_digest(signature, expected)
```

**Recommendation:** Add a check: if `multi_sig_config.enabled` and the relay URL is not loopback, reject `allow_dev_signatures=True` with a hard error.

---

### SEC-16 · LOW · Dead code in `BudgetMonitor.check()` after early return

**File:** [`teaagent/budget_monitor.py:102-119`](../../teaagent/budget_monitor.py)  
**Severity:** Low | **Likelihood:** N/A | **Impact:** Misleading code, maintenance risk

**Description:**  
`BudgetMonitor.check()` has an unreachable second loop (lines 104-119) after `return highest_action` on line 102. This dead code is a maintenance hazard — a future refactor could accidentally remove the early return, activating the second loop and changing behavior.

**Recommendation:** Remove lines 104-119.

---

## Summary Table

| ID | Category | Title | Severity | Action |
|----|----------|-------|----------|--------|
| SEC-01 | Audit Chain | HMAC key ephemeral — chain authentication broken | **Critical** | Immediate: persist key |
| SEC-02 | Access Control | MCP trust expiry never enforced at call time | **High** | Immediate: fix `merged_tool_filters` |
| SEC-03 | Permission | `allow_all_destructive` total policy bypass | **High** | Near-term: gate on DANGER mode |
| SEC-04 | Cost | Chat mode defaults to unlimited cost | **High** | Immediate: change default |
| SEC-05 | Cost | Cost injectable from LLM adapter output | **High** | Design: side-channel accounting |
| SEC-06 | Permission | JIT session approval leaks to subagents | **High** | Near-term: one-way sync |
| SEC-07 | Isolation | Docker subagent runs as root, no network isolation | **High** | Immediate: add hardening flags |
| SEC-08 | Isolation | `directory-snapshot` no process isolation | **Medium** | Near-term: deprecate/warn |
| SEC-09 | Multi-sig | 1-hour replay window in approval hash | **Medium** | Near-term: shorter window, dedup |
| SEC-10 | Shell | `cat`/`head`/`tail` in inspect allowlist — secret leak | **Medium** | Near-term: remove or restrict |
| SEC-11 | Undo | Shell mutations not tracked — false undo safety | **Medium** | Near-term: UI warning |
| SEC-12 | Audit | Disk errors silenced without alert | **Medium** | Near-term: operator notification |
| SEC-13 | Testing | Mock anti-patterns hide cost/budget bugs | **Medium** | Near-term: add integration tests |
| SEC-14 | Permission | Deprecated `preapproved_call_ids` still functional | **Low** | Future: remove in next major |
| SEC-15 | Multi-sig | `allow_dev_signatures` env-var no prod guard | **Low** | Near-term: add production check |
| SEC-16 | Code Quality | Dead code in `BudgetMonitor.check()` | **Low** | Cleanup: remove dead loop |

---

## Immediate Hardening Checklist (≤1 sprint)

- [ ] **SEC-01** — Persist HMAC key per-run; pass key to `verify_audit_chain` in `audit_export.py`
- [ ] **SEC-02** — Call `is_server_trust_expired()` in `merged_tool_filters()` and in pre-hook callback
- [ ] **SEC-04** — Change `ChatAgentConfig.max_estimated_cost_cents` default from `0` to `500` (or prompt)
- [ ] **SEC-07** — Add Docker hardening flags: `--user 65534 --network none --cap-drop ALL --read-only`
- [ ] **SEC-10** — Remove `cat`, `head`, `tail` from `_INSPECT_EXECUTABLES`
- [ ] **SEC-16** — Delete dead code at `budget_monitor.py:104-119`

## Design-Level Recommendations (future sprints)

- **Cost side-channel:** Move cost tracking out of the LLM adapter context dict into a separate tamper-resistant accounting layer (e.g. signed by the API response or measured at the HTTP transport level).
- **Audit key management:** Adopt an append-only signed log using SSH or Sigstore. The per-process HMAC approach cannot provide cross-run tamper evidence.
- **Subagent capability model:** Replace JIT state sharing with an explicit capability token that cannot be escalated — subagents receive a narrower policy envelope derived from, but strictly less than, the parent's.
- **MCP trust lifecycle:** Implement periodic policy reload (every 60 s) and make expiry enforcement synchronous with each tool dispatch.
- **Shell sandbox:** Remove user-facing shell from the inspect classification entirely; implement a true read-only shell using `seccomp` or `pledge`/`unveil` on supported platforms.

---

## Audit Log Plan

Every security finding remediation commit should:
1. Include a unit test that would have caught the vulnerability.
2. Be tagged with the SEC-NN identifier in the commit message.
3. Be captured in the audit chain with event type `security_remediation`.

## Human Review Required

- **SEC-03** (`allow_all_destructive`) — Review all callers; determine if any production automation templates set this flag.
- **SEC-05** (cost injection) — Architecture decision: whether cost should be sourced from API response headers or from a dedicated accounting proxy.
- **SEC-07** (Docker isolation) — Determine minimum-viable Docker hardening compatible with the agent's actual task requirements.

## Go / No-go Decision

**No-go for production expansion** until SEC-01, SEC-02, SEC-04, and SEC-07 are resolved.  
SEC-05 and SEC-06 require design discussion before the agent is exposed to untrusted input sources.  
All remaining items are acceptable risk for internal/local developer use with known caveats documented.
