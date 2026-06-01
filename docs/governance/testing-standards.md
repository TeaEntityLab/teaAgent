# Testing Standards

---

## Test directory layout

```
tests/
├── conftest.py                     # shared fixtures and FakeAdapter
├── test_support.py                 # (project root) socket/loopback helpers
│
├── test_*.py                       # unit tests — fast, no I/O beyond tempdir
│
├── integration/
│   └── test_*.py                   # integration tests — real DB, real filesystem
│
├── e2e/
│   └── test_end_to_end.py          # end-to-end — real agent loop, fake LLM
│
├── acceptance/
│   └── test_*_flow.py              # acceptance flows tied to docs/acceptance.md
│
├── policy/
│   └── test_permission_matrix.py   # permission-model matrix tests
│
└── regression/
    └── test_*.py                   # regression tests for previously fixed bugs
```

Pick the lowest layer that adequately exercises the behaviour. Unit tests are preferred; reach for integration or acceptance tests only when the behaviour cannot be meaningfully verified in isolation.

---

## Test naming convention

```
test_<unit>_<scenario>_<expected_outcome>
```

Examples:
- `test_resolve_workspace_path_parent_traversal_raises`
- `test_check_tool_access_unregistered_tool_denied`
- `test_audit_logger_redacts_api_key_field`
- `test_jit_approval_single_use_discards_after_check`

Acceptance flow test files are named after the flow: `test_consensus_flow.py`, `test_sandbox_enhancement_flow.py`.

---

## Coverage requirements

| Scope | Threshold | Enforced by |
|---|---|---|
| Overall `teaagent/` package | ≥ 75% lines | `pytest --cov-fail-under=75` (CI `test` job) |
| New skill bundles | ≥ 80% lines | Manual gate (`docs/skill-governance.md`) |

Modules listed in `[tool.coverage.run] omit` in `pyproject.toml` are excluded from the threshold (mostly TUI, WASM, Docker, and generated stubs). Do not add new production modules to the omit list without documenting why coverage is impractical.

---

## Unit tests

- Use `tempfile.TemporaryDirectory` (or the `temp_workspace` helper in `conftest.py`) for all filesystem operations. Never write to the project directory.
- Use `FakeAdapter` from `conftest.py` for LLM interactions. Never call a real LLM API in unit tests.
- Mock at the system boundary only: LLM HTTP, external network, OS-level resources. Do not mock internal module functions — restructure the code instead.
- Tests must be deterministic. If behaviour depends on time, inject a clock; if it depends on random IDs, seed or mock.
- Each test should have one logical assertion. Split tests rather than asserting multiple unrelated things in one function.

---

## Integration tests (`tests/integration/`)

- May use a real SQLite database created in a temporary directory.
- Must clean up all temporary resources in a `finally` block or via pytest fixtures.
- Must not require a live network connection, a running LLM, or a running agent loop.
- Use the `can_bind_loopback` / `skip_if_socket_bind_is_blocked` helpers from `test_support.py` for socket-dependent tests.

---

## Acceptance tests (`tests/acceptance/`)

Acceptance tests correspond 1-to-1 with rows in `docs/acceptance.md`. When adding a new acceptance flow:

1. Add the test file as `tests/acceptance/test_<flow_name>_flow.py`.
2. Add a corresponding row to `docs/acceptance.md`.
3. Run `python3 scripts/run_acceptance_tier.py --tier all` to confirm the count matches.

CI blocks merge if the acceptance count diverges.

---

## Security / property tests

Security invariants must use property-based testing, not just example-based testing. The shell classifier (`tests/test_workspace_tools.py:ShellClassifierPropertyTests`) is the canonical pattern:

```python
@pytest.mark.parametrize('cmd', INSPECT_COMMANDS)
def test_inspect_classified_as_inspect(cmd):
    assert classify_shell_command_policy(cmd) == 'inspect'

@pytest.mark.parametrize('cmd', MUTATE_COMMANDS)
def test_mutate_classified_as_mutate(cmd):
    assert classify_shell_command_policy(cmd) == 'mutate'
```

Add new invariants as parameterised tests, not prose assertions inside a single test function.

---

## Pre-commit smoke subset

Pre-commit runs a fast subset by default:

```
tests/test_p0_harness.py
tests/test_surface_auth_hardening.py
tests/test_policy.py
tests/test_phase5_context_bus.py
tests/test_governance_hardening.py
```

Run the full suite before opening a PR. To run the full suite via pre-commit:

```bash
TEAAGENT_PRECOMMIT_FULL=1 pre-commit run --all-files
```

Or directly:

```bash
pytest -q
```

---

## CI test matrix

| Job | Python versions | Blocks merge? |
|---|---|---|
| `test` | 3.10, 3.11, 3.12 | Yes |
| `test-telemetry` | 3.12 | Yes |
| `governance-gate` | 3.12 | Yes |
| `acceptance-p0` | 3.12 | Yes |
| `acceptance-p1` | 3.12 (after p0) | Yes |
| `acceptance-all` | 3.12, main branch only | Yes |
| `docker-smoke` | 3.12 | No (`continue-on-error`) |

---

## Mocking rules

| Layer | Mock allowed? | Notes |
|---|---|---|
| LLM API (HTTP) | Yes | Use `FakeAdapter` |
| Filesystem (reads) | Prefer `temp_workspace` | Only mock if tempdir is truly impractical |
| OS sockets / bind | Yes (`can_bind_loopback`) | Skip tests when loopback unavailable |
| `fcntl` / file locks | Avoid | Test with real files in tempdir instead |
| Internal functions inside `teaagent/` | No | Restructure the code instead |
| `time.time` / `datetime.now` | Yes (inject clock) | Required for determinism |

---

## Regression tests (`tests/regression/`)

When a bug is fixed, add a regression test that would have caught it. The test name must reference the fix ticket or a one-line description of the failure mode:

```python
def test_approval_queue_prune_holds_lock_before_read():
    # Regression: FIND-03-LOCK — concurrent prune raced on dict read
```
