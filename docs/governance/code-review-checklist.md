# Code Review Checklist

Use this checklist when reviewing any pull request. Items marked **[block]** must be resolved before approval; items marked **[flag]** should be noted but do not block at reviewer discretion.

---

## Correctness

- [ ] [block] Logic change is covered by a test that would fail before the fix.
- [ ] [block] No off-by-one, race condition, or TOCTOU introduced. Pay special attention to: file locking sequences, asyncio/thread boundaries, SQLite transaction spans.
- [ ] [block] Error paths are handled — no silent swallowing of exceptions in governance or audit code paths.
- [ ] [block] New async code does not call `asyncio.set_event_loop` or create a new event loop from within a running loop (see ADR 0018, `async_bridge.run_coroutine_sync`).
- [ ] [flag] Edge cases at budget limits (iteration, cost, tool-call count) are tested.

## Security

- [ ] [block] No hardcoded credentials, API keys, tokens, or secrets anywhere in the diff.
- [ ] [block] Workspace path confinement is preserved — all new path construction goes through `resolve_workspace_path()`. No raw `os.path.join` with user-controlled input.
- [ ] [block] Shell commands that reach `run_shell_command` are classified before execution. New command patterns are covered by classifier property tests.
- [ ] [block] New MCP or HTTP endpoints that accept external input validate and sanitise inputs before use. No string-concatenated SQL or Cypher — use parameterised queries.
- [ ] [block] Any new tool that can mutate the workspace or execute code is declared `destructive=True` in its `ToolDefinition`, so approval gating applies.
- [ ] [block] Audit redaction covers any new parameter that could carry credentials (match the `api_key|authorization|credential|password|secret|token` pattern).
- [ ] [flag] New network-facing code enforces loopback-only by default unless `--auth-token` or `--oauth-issuer` is provided.
- [ ] [flag] New OAuth/auth code adds a corresponding `jti`/nonce replay test.

## Governance

- [ ] [block] Changes to tool schemas, audit event shapes, or permission semantics cite an existing ADR or include a new one in `docs/adr/`.
- [ ] [block] Destructive-tool behaviour remains explicit, auditable, and approval-gated — no new code path that bypasses `check_tool_access`.
- [ ] [block] No change weakens the `fail-closed` invariant: unknown/unregistered tools must be denied, not allowed.
- [ ] [flag] New audit event types are documented in `docs/audit-events.md`.

## Code quality

- [ ] [block] `ruff check .` and `ruff format --check .` pass with no suppressions added.
- [ ] [block] `mypy teaagent/` passes — no new `# type: ignore` comments without an explanation comment.
- [ ] [block] All new public functions and methods have complete type annotations.
- [ ] [block] Test coverage does not drop below 75% (visible in CI `test` job summary).
- [ ] [flag] No comments explaining *what* the code does — only *why* for non-obvious constraints.
- [ ] [flag] No unused imports, dead code, or `TODO(someday)` comments.

## Tests

- [ ] [block] New behaviour has at least one unit test that fails before the change.
- [ ] [block] Security invariants (path confinement, classifier correctness, approval gating) have property tests, not just example-based tests.
- [ ] [flag] Integration tests cover the happy path end-to-end for new workflows.
- [ ] [flag] Test names follow `test_<unit>_<scenario>_<expected>` convention.
- [ ] [flag] Mocks are limited to the system boundary (LLM API, filesystem, network). Internal module mocks are a code smell — restructure instead.

## Documentation

- [ ] [block] `CHANGELOG.md` has a one-line entry under `## Unreleased`.
- [ ] [flag] `docs/cli.md` is updated if CLI surface changed.
- [ ] [flag] `docs/audit-events.md` is updated if audit event shapes changed.
- [ ] [flag] `docs/acceptance.md` count matches actual acceptance tests (`--collect-only`).

---

## Reviewer sign-off levels

| Change type | Approvals required |
|---|---|
| Bug fix, docs, chore | 1 |
| New feature | 1 |
| Security fix (SECURITY.md threat surface) | 2 |
| Breaking change (MAJOR version bump) | 2 + ADR merged first |
| Release tag | 1 (maintainer only) + compliance checklist complete |

The second reviewer for security fixes should have read the relevant section of `SECURITY.md` and the affected code before approving.
