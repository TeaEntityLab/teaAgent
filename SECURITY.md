# Security

## Threat Model

TeaAgent is a governance-first agent harness that gives an LLM-controlled agent access to
a workspace directory through registered tools. The primary threats are:

1. **Model misbehavior** — the LLM generates tool calls that escape the workspace,
   execute dangerous shell commands, or exfiltrate data.
2. **Untrusted MCP clients** — remote MCP clients that attempt unauthorized tool
   execution or credential theft.
3. **Network attackers** — attackers on the same network that intercept MCP HTTP
   traffic or replay authenticated sessions.
4. **Multi-tenant workspace collision** — concurrent agent runs on the same workspace
   root corrupting each other's state.
5. **Prompt injection** — attacker-controlled content in workspace files influencing
   the agent's decision-making loop.

TeaAgent assumes the LLM provider and local process boundary are trusted. It does
**not** protect against a compromised Python runtime, operating system, or LLM provider
infrastructure.

## Permission Modes

| Mode                  | Read | File Write | Shell Mutate | Approval Required |
|-----------------------|------|------------|-------------|--------------------|
| `read-only`           | Yes  | No         | No          | N/A                |
| `workspace-write`     | Yes  | Yes        | No          | N/A                |
| `prompt`              | Yes  | Conditional| Conditional | Human-in-the-loop   |
| `allow`               | Yes  | Yes        | Yes         | Session-scoped     |
| `danger-full-access`  | Yes  | Yes        | Yes         | None               |

Even in `danger-full-access`, the harness enforces:
- Workspace path confinement (tools reject `../`, absolute paths, symlink escapes)
- File size limits (`max_read_bytes`, `max_write_bytes`, `max_shell_output_bytes`)
- Shell command size limits (`max_shell_command_bytes`)
- Shell command timeout ceiling (`max_shell_timeout_seconds`)
- Iteration and tool-call budgets

## Shell Sandbox

Shell commands are classified as **inspect** or **mutate** before execution:

- **Inspect**: `pwd`, `ls`, `find`, `rg`, `grep`, `cat`, `head`, `tail`, `wc`,
  safe `git` subcommands (`status`, `diff`, `log`, `show`, `branch`, `grep`)
- **Mutate**: everything else

### Classification Algorithm

The classifier (`workspace_tools.py:classify_shell_command_policy`) uses quote-aware
scanning to detect unquoted shell operators (`>`, `<`, `|`, `&&`, `;`, `` ` ``, `$(`).
Quoted operators (e.g., `git log --grep='>'`) are correctly classified as inspect
because the shell treats them as string content, not operators.

**Property tests** (`tests/test_workspace_tools.py:ShellClassifierPropertyTests`)
verify that:
- All inspect commands are classified as inspect
- All mutate commands are classified as mutate
- Quoted operators do not trigger mutate
- Actual redirect/pipe/chain operators trigger mutate
- Command substitution triggers mutate
- Workspace-escape paths trigger mutate

### Inspect Execution

Inspect commands are executed via `shlex.split()` with `shell=False`, which:
- Prevents shell metacharacter expansion
- Prevents command chaining (the `;`, `&&`, `||` operators are rejected by the
  classifier *before* reaching execution)
- Rejects workspace-escaping arguments (`/`, `~`, `..`)

### Known Limitations

- The classifier uses a heuristic approach. An adversarial prompt may discover edge
  cases. Report findings as described below.
- `shell_arg_escapes_workspace` only checks literal path prefixes; it does not
  expand environment variables or glob patterns.
- Commands that match the inspect allowlist but spawn subprocesses (e.g., `git`
  hooks, custom pager configurations) can execute arbitrary code.

## MCP HTTP Security

### Bind Enforcement

The MCP HTTP server enforces authentication at two layers:

1. **CLI layer** (`cli/__init__.py:mcp_serve_command`): refuses to start on a
   non-loopback host (`0.0.0.0`, `::`, external IPs) unless `--auth-token` or
   `--oauth-issuer` is provided.
2. **Library layer** (`mcp_http.py:build_mcp_http_server`): raises `ValueError` when
   constructed with a non-loopback host and no `auth_token` or `oauth_server`.

### Authentication Options

- **Bearer token**: static shared secret via `--auth-token`. Every request must
  include `Authorization: Bearer <token>`.
- **OAuth 2.1 with DPoP**: proof-of-possession token binding via
  `--oauth-issuer` + `--oauth-signing-key`. Access tokens are bound to the
  client's DPoP key, preventing token replay by network observers.

### Origin Control

Pass `--allowed-origin` (repeatable) to restrict browser-originated requests.
Without it, all origins are accepted.

### Transport

The MCP HTTP server does not support TLS natively. When serving on non-loopback
hosts, place a reverse proxy (nginx, Caddy, Cloudflare Tunnel) with TLS termination
in front of the server.

## Code Mode

Code Mode executes LLM-generated Python code only after AST allow-list validation
(limited node types, restricted builtins, no imports, no attributes, no arbitrary
function calls). It has two backends:

- **Child process backend** (default): runs `exec()` in a child Python process with
  wall-clock timeout, `RLIMIT_CPU`, and best-effort `RLIMIT_AS` memory limits.
- **Container backend** (`ContainerCodeModeBackend`): delegates execution to a
  Docker/Podman-style runtime with `--network none`, `--read-only`,
  `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root `--user`, tmpfs
  `/tmp`, memory/swap limits, CPU ulimit, and PID limit.

Code Mode is still **not** a complete production sandbox:

- The default backend runs inside the same Python interpreter family; isolate it
  from untrusted workloads.
- The container backend does not install a project-specific seccomp/AppArmor/SELinux
  profile, does not enforce image digest pinning, and checks stdout size after the
  child exits rather than streaming with a hard read cap.
- Memory limits are advisory on macOS for the child-process backend.

For high-risk production use, prefer a hardened external execution service, VM
sandbox, V8 isolate, or container runtime with pinned images and mandatory security
profiles.

## File System Access

All workspace tools enforce path confinement through `resolve_workspace_path()`:
- Paths are resolved relative to the workspace root
- `../` escapes, absolute paths, and symlink escapes are rejected
- `.git` directories are excluded from `list_files` and `search_text`

Write tools (`workspace_write_file`, `workspace_apply_patch`, `workspace_edit_at_hash`)
enforce `max_write_bytes` before any write occurs.

## Edit Safety

- `workspace_apply_patch` requires the `old` text to appear **exactly once** in the
  target file. If it appears multiple times, the edit is rejected — the caller must
  provide more context or use `workspace_edit_at_hash`.
- `workspace_edit_at_hash` uses CRC32 line anchors (`LINE#HASH|content`). If the
  hash of the target line has changed (stale read), the edit is rejected.

## Audit Trail

Every tool call, approval decision, iteration, and final result is recorded in the
audit log with:
- Per-run JSONL persistence (file mode `0600`)
- Argument redaction for sensitive keys (API keys, passwords, tokens, secrets)
- Result content redaction for stdout/stderr
- Truncation of long strings at 20,000 characters

Audit logs are append-only. TeaAgent does not rotate or expire audit files — set up
external log rotation for long-running deployments. The CLI provides manual lifecycle
commands: `teaagent audit list`, `teaagent audit show`, and `teaagent audit prune`.

## Credential Handling

- LLM API keys are read from environment variables only; never from files or
  command-line arguments
- MCP `--auth-token` and `--oauth-signing-key` are command-line arguments (visible
  in `ps`). Prefer environment variables or a secrets manager for production
- `SQLiteOAuthStore` stores OAuth client secrets as PBKDF2-SHA256 hashes with
  per-client salts; the in-memory store keeps secrets in process memory only.
- Audit logs redact keys matching `api_key`, `authorization`, `credential`,
  `password`, `secret`, `token` in any casing

## LLM Provider Resilience

- The LLM adapter layer includes configurable exponential-backoff retry
  (`LLMRetryConfig`) for transient errors (HTTP 429, 5xx, connection failures).
- Cost budget pre-flight (`RunBudget.check_cost_preflight`) estimates the maximum
  possible cost of an LLM call before spending money, rejecting calls that would
  exceed the budget.
- Every run has hard limits on iterations and tool calls, enforced by `AgentRunner`.

## Concurrent Access

`AuditLogger` and `MemoryCatalog` write JSONL through `teaagent.storage.append_jsonl_line()`,
which acquires an `fcntl.LOCK_EX` advisory lock and `fsync()`s after every append. On
platforms without `fcntl` (Windows), the lock is a best-effort no-op but the append
and `fsync` still run. `RunStore` final-state writes and `UltraworkStore` worker
records use `teaagent.storage.atomic_write_text()` (lock + temp file + `os.replace`).

Remaining concurrency limitations:
- The lock is per-file advisory; non-cooperating writers can still corrupt the file.
- Cross-host concurrency (NFS, SMB) is not supported — the `fcntl` lock is local.
- For multi-worker production, use separate workspace roots per worker or replace the
  JSONL backend with a transactional store (SQLite, PostgreSQL).

## Reporting a Vulnerability

Report security vulnerabilities to the project maintainers. Do not file public
issues for security-sensitive findings.

**Scope**: vulnerabilities in TeaAgent's harness logic, tool governance, sandbox
escape vectors, or authentication bypasses.

**Out of scope**: vulnerabilities in LLM providers, the Python standard library,
the operating system, or upstream dependencies.
