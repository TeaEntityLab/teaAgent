# Contributing

TeaAgent keeps the harness thin: orchestration, tool governance, state boundaries,
audit, and validation belong in this repository. Domain reasoning belongs in the
model or reviewed skills.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev,oauth,telemetry]"
pre-commit install
```

## Checks

Run the same checks as CI before opening a pull request:

```bash
.venv/bin/ruff check .
.venv/bin/mypy teaagent/
.venv/bin/pytest -q
```

## Pull Requests

- Keep changes small and focused.
- Add or update tests for behavior changes.
- Update docs/ADR files when changing tool governance, audit semantics, OAuth,
  MCP transport, or Code Mode isolation boundaries.
- Do not commit secrets, `.teaagent/` runtime state, build artifacts, or cache
  directories.
- Destructive-tool behavior must remain explicit, auditable, and approval-gated.

## Security

Do not open public issues for security-sensitive findings. Follow `SECURITY.md`.
