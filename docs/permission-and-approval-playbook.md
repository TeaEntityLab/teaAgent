# Permission And Approval Playbook
# As of 2026-09-15

> **Last reviewed:** 2026-09-15
> **Review trigger:** Approval, permission, or MCP trust behavior changes.
> **Changes since 2026-06-06 review:** matched deny grants now hard-block in
> every mode (`1611e71b` G1 fix — previously advisory-only); `approval preset
> strict` applies wildcard-scoped denies (G6 fix); new `approval reject
> <call_id>` denies a queued pending call and resumes the run without it
> (G15); paused approvals auto-deny after `TEAAGENT_PENDING_APPROVAL_TTL_SECONDS`
> (default 24h, G16); `approval check` evaluates deny grants in allow mode too.

This playbook is for users operating TeaAgent in repositories where tool authority
matters.

## Default modes

| Situation | Suggested mode | Rationale |
|-----------|----------------|-----------|
| First run in a repo | Prompt for approvals | Learn what tools and paths are requested. |
| Known safe read-only audit | Inspect/read-only | Avoid unnecessary write authority. |
| Repeated local task in narrow path | Path-scoped approvals | Grants authority without opening the whole repo. |
| Broad refactor or delete-heavy task | Prompt with human review | High blast radius. |

## Prompt mode

In prompt mode, approval is part of the product experience:

1. Read the tool name.
2. Read the path.
3. Read the operation.
4. Compare with the task.
5. Approve, reject, or ask the agent to narrow the plan.

## Path-scoped approval

Good path scopes:

- One file being edited.
- One docs directory for docs-only work.
- One generated output directory.
- A test file paired with its implementation file.

Risky path scopes:

- Repository root for a small change.
- Home directory.
- Empty path.
- Hidden config directories unless the task is explicitly about config.

## Pending approvals

Useful TUI/CLI concepts:

- `approval pending` to inspect blocked calls (reads the full audit log — no
  `limit=20` window since the G5/G21 unification fix).
- `approval approve <call_id> [--resume]` to approve one queued call
  (`--selector N` from `approval pending --human` also works).
- `approval reject <call_id>` to deny a queued call and resume the run
  without executing it (records `tool_call_denied`; `approval deny` is
  grant-only and does not touch queued calls).
- `approval check <tool>` to test whether current presets would allow, prompt,
  or deny a call — a matched deny grant now hard-blocks (`POLICY_DENIED`) in
  prompt, allow, workspace-write, and read-only modes.
- `approval preset strict` applies wildcard deny grants (`path_globs: ["*"]`)
  so "deny all destructive tools" actually applies (was a no-op before G6).
- Paused approvals expire: a run paused longer than
  `TEAAGENT_PENDING_APPROVAL_TTL_SECONDS` (default 24h) is auto-denied.
- `unapprove` or `revoke` when authority is no longer needed.

## Revoking approvals

Revoke when:

- The task changed.
- The path was broader than intended.
- The run was interrupted and resumed later.
- A child agent or tool requested authority outside its assigned scope.

## Unsafe shortcuts

- Do not approve destructive tools without an exact path and rollback story.
- Do not approve broad writes because a previous run was safe.
- Do not treat approval logs as optional; they are part of the audit chain.
- Do not hide "pending approval" behind a generic failed status.

## Common scenarios with exact scope

### Scenario 1: Editing a single test file
- **Task**: Fix failing test in `tests/test_auth.py`
- **Approval scope**: `path_globs: ["tests/test_auth.py"]`
- **Why safe**: The agent can only write to the exact test file
- **Alternative**: Use prompt mode to approve each edit individually
- **Run**: `teaagent agent run gpt "fix tests/test_auth.py" --permission-mode prompt`

### Scenario 2: Docs-only updates
- **Task**: Update API documentation in `docs/api/`
- **Approval scope**: `path_globs: ["docs/api/**"]`
- **Why safe**: Agent cannot touch source code, only docs
- **Risk**: If path_globs is omitted, the grant silently applies to all paths
- **Safe alternative**: Always specify `path_globs` — an empty path_globs means unrestricted

### Scenario 3: Broad refactor across multiple directories
- **Task**: Rename a module from `src/old/` to `src/new/`
- **Approval scope**: `path_globs: ["src/old/**", "src/new/**"]`
- **Why prompt is safer**: Path-glob combinations can miss edge cases
- **Recommendation**: Use prompt mode unless the refactor is well-understood

### Scenario 4: Root workspace containment
- **Setup**: `--root /home/user/project`
- **Agent tries**: `workspace_write_file(path="/etc/crontab")` → **DENIED**
- **Why**: The path resolves outside `/home/user/project`. Explicit root always wins.
- **Good**: Agent retries with `path="config/app.conf"` which resolves within root
- **Check**: Run evidence includes `workspace_root` field to verify which root was active

### Scenario 5: Scoped path approval for a directory
- **Task**: Allow edits to only the `src/` directory
- **Command**: `teaagent run --permission-mode workspace-write --approve-path src/`
- **Scope**: All `workspace_write_file` calls to paths under `src/` are auto-approved
- **Why safe**: The agent cannot write outside `src/`, limiting blast radius
- **Cockpit**: `teaagent daily` shows active approval scope: `workspace-write (scoped: src/**)`

### Scenario 6: Single tool call approval
- **Task**: Approve one specific queued tool call without granting session-wide access
- **Command**: `teaagent approval approve <call_id> [--resume]`
- **Scope**: That exact queued call; no other calls are approved
- **Why safe**: One-time approval of the exact call prevents scope creep
- **Audit**: Each approval is recorded in the run evidence bundle with `scope_path` and `authority_type` (`cli_approval`/`operator` for CLI approvals)
- **Note**: `--approve-call-id` on `agent run` is deprecated and ignored; the
  removed per-call preapproval path must not be confused with approving an
  already-queued call. There is no `teaagent approve` top-level command — the
  surface is `teaagent approval approve`.

### Scenario 7: Rejecting a queued destructive call
- **Task**: Decline a pending destructive call without executing it
- **Command**: `teaagent approval reject <call_id>`
- **Scope**: That exact queued call; the run resumes without it
- **Why safe**: Records `tool_call_denied` (clears the pending entry); the
  denied call is not re-executed on resume
- **Audit**: Denial is recorded with the call id; `approval deny <tool>` is
  grant-only (registers a deny grant for future calls, requires
  `--path-glob`/`--command-prefix` scope) and cannot reject an already-queued call.

## Security review checklist (P2-A-004)

Review each item before granting elevated authority in a production workspace.

### MCP trust expiry
- [ ] All trusted MCP servers have a valid `expires_at` timestamp that has not elapsed.
- [ ] Call-time trust check (`check_mcp_server_trust_at_call_time`) rejects expired entries.
- [ ] Untrusted servers (trusted=False) are blocked at the pre-tool hook.
- [ ] MCP trust policy is encrypted at rest with `TEAAGENT_MCP_TRUST_KEY`.

### Skill isolation
- [ ] Skill diagnostics (`skill-diagnostics` command) include `isolation_status` with available backends.
- [ ] When neither WASM (wasmer) nor Docker is available, `downgrade_label` = `native-execution-fallback`.
- [ ] Native-execution warnings are visible in the TUI before running isolated skills.
- [ ] No sensitive skills execute natively without an explicit isolation downgrade acknowledgement.

### Subagent authority inheritance
- [ ] Subagent permission mode is capped at `workspace-write` when the parent runs in `allow` or `danger-full-access`.
- [ ] Subagent defs that explicitly set their own permission mode are respected (no silent override).
- [ ] Workspace snapshot copies (`_copy_workspace_snapshot`) exclude secret files: `.env`, `.pem`, `credentials.*`, `.ssh/`, `.gnupg/`.
- [ ] Audit logs record when a subagent permission mode was capped for safety.

### General approval hardening
- [ ] Path-scoped approvals never have an empty `path_globs` without explicit developer acknowledgement.
- [ ] `workspace_root` containment is checked before any JIT approval is granted.

## Maintainer checklist

- Approval prompts include run id, tool name, input summary, and path scope.
- Approval records are written to audit logs.
- Empty path approval is rejected or explicitly explained (labeled as "unrestricted").
- TUI and CLI approval wording match.
- Workspace root containment is enforced before JIT approval.
- Run evidence bundles include active workspace_root for forensic traceability.
