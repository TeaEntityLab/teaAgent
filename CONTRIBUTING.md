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

Pre-commit runs a smoke subset by default. For the full test suite locally:

```bash
TEAAGENT_PRECOMMIT_FULL=1 pre-commit run --all-files
```

Docs consistency (same check as CI):

```bash
./scripts/verify_docs.sh
```

### CI jobs

| Job | Blocks merge? | Purpose |
|-----|---------------|---------|
| `lint` | Yes | Ruff, mypy, format |
| `governance-gate` | Yes | Governance fuzz, plan gate, Phase 4–5 acceptance, Phase 5 unit tests |
| `docker-smoke` | **No** (`continue-on-error`) | `tests/test_phase6_docker.py` when Docker/Podman is available |
| `package` | Yes | Wheel/sdist build |

Run `pytest tests/test_phase6_docker.py` locally before relying on container Code Mode in production.

## Pull Requests

- Keep changes small and focused.
- Add or update tests for behavior changes.
- Update docs/ADR files when changing tool governance, audit semantics, OAuth,
  MCP transport, or Code Mode isolation boundaries.
- Do not commit secrets, `.teaagent/` runtime state, build artifacts, or cache
  directories.
- Destructive-tool behavior must remain explicit, auditable, and approval-gated.

## Docstrings

Public API modules should use Google-style docstrings with `Args`, `Returns`, and
`Raises` where applicable. Run `task docs` to regenerate API reference.

## Deprecation policy

- Public API: deprecate in release X.Y, remove no sooner than the next minor or major per ADR.
- Emit `DeprecationWarning` with migration hint when deprecating.
- See [breaking-changes.md](docs/processes/breaking-changes.md).

## Dependency pinning

Release builds may export pinned deps via `scripts/freeze-deps.sh`.

## Security

Do not open public issues for security-sensitive findings. Follow `SECURITY.md`.
