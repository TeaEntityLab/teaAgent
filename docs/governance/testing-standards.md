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

### CI Runner Environment Notes & Debt Register

> **Corrected 2026-10-09.** The 2026-09-30 wording ("specific test failure causes
> are not yet reproduced off-runner") was wrong: the CI job logs reach the pytest
> summary and name the failing tests, and all 9 reproduce off-runner (8 in a shallow clone, the ninth with `rg` removed from `PATH`). Record
> in [Roadmap Review 2026-10-09](../reviews/roadmap-review-and-improvement-plan-2026-10-09.md) §3.1.

- **Observed:** `main` runs 851–858 (2026-09-29→09-30) failed only in
  `test (ubuntu-latest, 3.12)` (job `109721112346`: `9 failed, 6752 passed,
  25 skipped`, coverage 78.97% ≥ 75%) and `acceptance-all` (job `109721655607`:
  `1 failed, 672 passed`). The 13 other jobs were green. The failures are
  deterministic test failures, not runner resource termination.
- **Root causes (verified by re-running the 9 tests in a `--depth 50` clone and
  again after `git fetch --unshallow`):**

  | Tests | Cause | Repair (R0-1…R0-4, landed 2026-10-09) |
  | --- | --- | --- |
  | `test_check_dr006_gate_trailer.py::test_real_history_87d1c61_passes` | commit `87d1c61` absent from a shallow checkout | `fetch-depth: 0` on the `test` and `acceptance-all` checkouts; test skips with a reason when the commit is absent |
  | `test_refresh_competitive_docs.py` (4 tests), `test_report_docs_aging.py::test_check_docs_aging_dashboard_passes_for_repo` | `cc7bed6` made the docs-aging check fail loud on shallow clones; these tests run the real repo check | same `fetch-depth: 0`; tests skip with a reason on a shallow clone |
  | `test_evidence_ledger.py::test_real_delivery_ledger_passes` | globbed `.teaagent/delivery/**`, which is gitignored, so it could only pass on the author's machine | skip with a reason when no local ledger exists; validation still runs when one does |
  | `test_g2_g3_g22_focused.py::test_rollback_refuses_when_head_not_on_sandbox_branch` | `git init` then `git checkout main`; runners default to `master` | pin the initial branch with `git symbolic-ref HEAD refs/heads/main` after `git init` |
  | `acceptance/test_run_evidence_summary_flow.py::test_real_run_receipt_completeness_from_plan` | the fake-adapter verify step ran `rg`; GitHub `ubuntu-latest` has no ripgrep, so the inspect tool raised `FileNotFoundError`, the runner recorded `tool_call_failed`, and the receipt rendered the command without any outcome (reproduced off-runner by removing `rg` from `PATH`) | test uses POSIX `grep`; receipt builder now renders `[failed: …]` / `[outcome unknown]` for commands that did not complete (R0-5) |

- **Still true:** the multi-platform smoke matrix (`macos-3.12`, `windows-3.12`,
  `ubuntu-3.10`, `ubuntu-3.11`), `acceptance-p0`, `acceptance-p1`, and the gating
  jobs (`lint`, `use-case-matrix`, `review-institution`, `governance-gate`,
  `docker-smoke`, `package`) pass. The unit suite with coverage passes locally
  (6,761 passed, 79.03% coverage, 636 s on 2026-09-30).
- **Rule derived from this incident:** a test that reads repository history, the
  repo-root `.teaagent/` directory, or the user's git configuration must either
  create that state itself under `tmp_path` or skip with an explicit `reason=`
  when the state is absent. `pytest-github-actions-annotate-failures` stays
  installed in CI so failing test names are always public.

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
