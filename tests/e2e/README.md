# End-to-End (e2e) Tests

This directory contains end-to-end integration tests that exercise the
full TeaAgent stack (agent loop + MCP HTTP server + RunStore + audit logging).

## Relationship to Acceptance Tests

- `tests/acceptance/` — **user-facing workflow tests** that simulate real
  user journeys (e.g. first-run experience, CLI/TUI parity, plan-mode flows).
  These are marked with `@pytest.mark.acceptance` and may require a configured
  provider or environment. There are ~127 such tests.

- `tests/e2e/` — **programmatic integration tests** that verify internal
  component wiring without requiring user configuration or provider keys.
  These tests use `FakeAdapter` and in-process HTTP servers to validate
  that the agent loop, MCP transport, audit persistence, and workspace tools
  all work together correctly.

## Contract

e2e tests in this directory MUST:

1. Run without any external provider, API key, or network access.
2. Use only `FakeAdapter` or `tmp_path` for isolation.
3. Complete in under 5 seconds each.
4. Test multi-component integration (not just unit-level).

They are NOT:
- User-journey simulations (those belong in `tests/acceptance/`)
- Provider or model conformance checks
- Performance benchmarks

## Existing Tests

- `test_end_to_end.py` — 3 tests covering agent loop persistence,
  pending-approval resume, and MCP HTTP initialize+tool-call.
