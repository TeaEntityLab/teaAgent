# Security Standards

This document translates the threat model in [SECURITY.md](../../SECURITY.md) into concrete coding rules.

---

## Threat surface summary

| Threat | Primary defence |
|---|---|
| Model misbehavior / workspace escape | `resolve_workspace_path()` confinement, shell classifier |
| Untrusted MCP clients | Bearer token or OAuth 2.1 + DPoP mandatory on non-loopback |
| Network attackers | Loopback-only default; TLS via reverse proxy for remote |
| Multi-tenant workspace collision | `GitBranchSandbox._sandbox_lock`, separate workspace roots |
| Prompt injection | Audit redaction, read-only gate, approval gating |

---

## Credential handling

**Rules — no exceptions:**

1. LLM API keys are read from environment variables only. Never accept them as function arguments, config file values, or CLI flags.
2. `--auth-token` and `--oauth-signing-key` are command-line arguments (visible in `ps`). Production deployments must use a secrets manager or environment variable injection instead.
3. OAuth client secrets are stored as PBKDF2-SHA256 hashes with per-client salts (`SQLiteOAuthStore`). Never store them in plaintext.
4. The audit logger redacts keys matching the pattern `api_key|authorization|credential|password|secret|token` (case-insensitive) in all event payloads. New tool parameters that carry credentials must have names matching this pattern so redaction applies automatically.
5. Never log environment variables wholesale. Extract only the specific variable by name.

---

## Path confinement

All new code that constructs file paths from user-supplied or LLM-generated input **must** call `resolve_workspace_path(workspace_root, user_path)`. The resolver:

- Resolves relative paths against the workspace root.
- Rejects `../` traversal, absolute paths, and symlinks that escape the root.
- Rejects `.git` directory access.

**Wrong:**
```python
target = os.path.join(workspace_root, user_supplied_path)
```

**Right:**
```python
target = resolve_workspace_path(workspace_root, user_supplied_path)
```

Property tests for path confinement live in `tests/test_workspace_tools.py`. Add cases for new path-constructing code.

---

## Shell command safety

The shell classifier (`workspace_tools.classify_shell_command_policy`) must run before any shell execution. Rules:

- `inspect` commands execute via `shlex.split()` with `shell=False`.
- `mutate` commands require a `workspace-write` or higher permission mode and explicit approval in `prompt` mode.
- Adding a new command to the `inspect` allowlist requires a property test demonstrating it cannot chain, redirect, or substitute.
- Never pass `shell=True` to `subprocess` or `os.system` with any user-controlled input.

---

## Injection prevention

### SQL / Cypher

Use parameterised queries exclusively. Never build query strings by concatenation or f-string formatting.

```python
# Wrong
cursor.execute(f"SELECT * FROM docs WHERE id = '{doc_id}'")

# Right
cursor.execute("SELECT * FROM docs WHERE id = ?", (doc_id,))
```

GraphQLite / Cypher follows the same rule: use `$param` placeholders.

### HTML / JS

The TUI is terminal-only and does not render HTML. Any future HTTP surface must escape user-supplied content before reflection.

### SSRF

Code that makes outbound HTTP requests to URLs derived from user input or LLM output must call `_validate_relay_url()` (in `federated_sync.py`) or an equivalent that:
- Allows only `https://` (or explicit `http://` for loopback).
- Resolves the hostname to IPs and rejects private ranges (RFC 1918, loopback, link-local, multicast).
- Bakes the resolved IP into the request URL to prevent DNS rebinding.

---

## Approval and destructive-tool gating

Every tool whose execution can modify files, run shell commands, or make network calls must be declared `destructive=True` in its `ToolDefinition`. The `check_tool_access` function enforces the approval gate. **Never bypass it** by calling the tool function directly in production code paths.

JIT approvals are single-use: `check_tool_access` calls `agent_approved.discard(tool_name)` after a successful check. Do not re-add the tool to the whitelist after approval.

Unknown or unregistered tools are denied (`permission is None` guard in `check_tool_access`). This is an invariant: if you add a registration path, add a test that an unregistered tool is denied.

---

## MCP / HTTP server security

- Default bind: loopback (`127.0.0.1`). Refuse to start on a non-loopback host without `--auth-token` or `--oauth-issuer`. This is enforced at two layers (CLI and library) — do not remove either layer.
- Bearer tokens: static secrets. Every request must include `Authorization: Bearer <token>`.
- OAuth 2.1 + DPoP: proof-of-possession. Access tokens are bound to the client's DPoP key. DPoP `jti` values are cached for the proof freshness window; replay fails.
- OAuth DPoP nonces are consumed on validation — replay of the same nonce fails.
- Allowed origins: pass `--allowed-origin` to restrict browser CORS. Without it, all origins are accepted — acceptable for localhost but not for remote deployments.
- TLS: the MCP HTTP server has no built-in TLS. Use a reverse proxy (nginx, Caddy, Cloudflare Tunnel) for remote deployments.

---

## Code Mode sandbox

LLM-generated code submitted to Code Mode goes through:

1. AST allow-list validation (limited node types, restricted builtins, no imports, no attributes, no arbitrary calls).
2. Child-process backend: `RLIMIT_CPU`, best-effort `RLIMIT_AS`, wall-clock timeout.
3. Container backend (optional): `--network none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root `--user`, tmpfs `/tmp`.

For untrusted workloads, set `ChildProcessCodeModeBackend.trusted_only = False` or use the container backend with `require_image_digest = True` and an explicit `allowed_images` list.

---

## Dependency management

- Dependency auditing follows the segmented policy in
  [dependency-audit-policy.md](../security/dependency-audit-policy.md): base
  PR gate, weekly dev/lockfile visibility, and optional-extra release review.
- CI runs the base `pip-audit` lane on every PR and the broader lanes on the
  scheduled or manual security workflow (see `.github/workflows/security.yml`).
- `uv.lock` is the lockfile. Pin CVE fixes via `[tool.uv] constraint-dependencies` in `pyproject.toml`.
- When a Dependabot alert is resolved in-tree, dismiss it in GitHub Security → Dependabot with reason *fix already on default branch*.
- Adding a new optional dependency requires: a stated purpose, a pin in the
  relevant extras group, and confirmation that the base audit remains clean and
  the relevant optional-extra audit result is documented.

```bash
uv export --format requirements-txt --no-dev --no-emit-project --frozen -o /tmp/teaagent-base-requirements.txt
pip-audit -r /tmp/teaagent-base-requirements.txt
```

---

## Concurrency safety

Write-path code (audit log, memory catalog, approval queue) must use `fcntl.LOCK_EX` advisory locking via `teaagent.storage.append_jsonl_line()` or `teaagent.storage.atomic_write_text()`. Never write JSONL directly with `open(..., 'a')` without the lock.

Cross-thread shared state must be protected by `threading.Lock`. Asyncio + threading boundaries must not hold `asyncio.Lock` during blocking I/O; use `loop.run_in_executor` for blocking operations called from async contexts.

---

## Vulnerability disclosure

Report security vulnerabilities privately to the project maintainers. Do not file public GitHub issues. See [SECURITY.md](../../SECURITY.md) for the full disclosure scope and process.

The maintainers will acknowledge receipt within 3 business days, assess severity, and coordinate a fix + disclosure timeline.
