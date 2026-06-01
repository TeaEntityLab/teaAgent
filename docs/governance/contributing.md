# Contributing to TeaAgent

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,oauth,telemetry]"
pre-commit install
```

Run the same checks as CI before opening a pull request:

```bash
ruff check .
ruff format --check .
mypy teaagent/
pytest -q
./scripts/verify_docs.sh
```

---

## Scope

This repository contains the agent harness: orchestration, tool governance, state boundaries, audit, and validation. It does **not** contain domain-specific reasoning or LLM prompts for end-user tasks. When in doubt, ask whether the change belongs in the harness or in a reviewed skill.

---

## Branch and PR workflow

```
main  ← protected, always green CI
  └── fix/<ticket>-<short-slug>          # bug fixes
  └── feat/<ticket>-<short-slug>         # new features
  └── chore/<short-slug>                 # tooling/deps/docs with no behaviour change
  └── security/<cve-or-short-slug>       # security fixes (keep private until disclosed)
```

1. Branch from `main`. Keep the branch focused on a single concern.
2. Open a draft PR early if you want feedback; convert to ready when CI is green.
3. Require at least **one reviewer approval** before merge.
4. Security fixes affecting `SECURITY.md`-listed threat surfaces require a second reviewer.
5. Changes to tool governance, audit semantics, OAuth, MCP transport, or Code Mode isolation require either an ADR citation or a new ADR in `docs/adr/`.
6. Squash or rebase — no merge commits on `main`.

---

## Commit message format

```
<type>(<scope>): <imperative summary under 72 chars>

<optional body — wrap at 80 chars>

BREAKING CHANGE: <if applicable>
Closes #<issue>
```

### Type

| Type | When to use |
|---|---|
| `feat` | New observable capability |
| `fix` | Bug fix |
| `security` | Security hardening without new capability |
| `refactor` | No behaviour change |
| `test` | Tests only |
| `docs` | Documentation only |
| `chore` | Build, deps, CI, tooling |
| `perf` | Performance improvement without behaviour change |

### Scope (optional but encouraged)

Use the primary module affected: `audit`, `policy`, `runner`, `tui`, `cli`, `workspace`, `approval`, `sandbox`, `swarm`, `llm`, `mcp`.

### Examples

```
fix(approval): make JIT approvals single-use (discard after check)

security(sandbox): resolve hostname before ip_address() to prevent ValueError

feat(audit): add denial reason codes to tool_call_denied events

docs(adr): ADR 0018 — async-from-sync pattern for approval paths
```

---

## What to include in a PR

- **Tests**: any behaviour change must add or update tests. Coverage must not drop below 75%.
- **Type annotations**: all new public functions and methods must have full annotations compatible with `mypy --disallow-untyped-defs`.
- **ADR or ADR citation**: required for governance, audit, permission model, or protocol changes.
- **Changelog entry**: add one line under `## Unreleased` in `CHANGELOG.md`.
- **Docs update**: if the PR changes CLI surface, tool schemas, audit event shapes, or permission semantics, update the corresponding doc in `docs/`.

---

## What NOT to include

- Secrets, API keys, or tokens of any kind.
- `.teaagent/` runtime state, build artifacts, `dist/`, `__pycache__`, `.pytest_cache/`, `.uv-cache/`.
- Commented-out dead code or TODO comments for hypothetical future requirements.
- Backwards-compatibility shims for removed features (just remove the feature).
- Comments explaining *what* the code does — only add a comment when the *why* is non-obvious.

---

## Change control

### Backwards-compatible changes

Bug fixes, new optional features, and additive API changes follow the standard PR workflow with a single reviewer.

### Breaking changes

A **breaking change** is any change to:

- The public Python API of any `teaagent.*` module (function signatures, class interfaces, exported names).
- Tool schemas (field names, types, required/optional status).
- Audit event shapes (event type strings, required payload keys).
- Permission mode semantics or the approval gate contract.
- The `teaagent` CLI command surface (command names, flag names, output format).
- Wire formats for MCP, ACP, A2A, or ANP.

Breaking changes require:

1. An ADR in `docs/adr/NNNN-short-title.md` with `Status: Proposed` created in a preparatory PR.
2. The ADR reviewed and status updated to `Status: Accepted` before the implementation PR opens.
3. A `### Breaking` entry in `CHANGELOG.md` with a migration note.
4. A `MAJOR` version bump in `pyproject.toml`.
5. Two reviewer approvals.

### RFC (Request for Comment) process

For significant new capabilities or protocol changes that don't have an obvious implementation path:

1. Open a GitHub Issue labelled `rfc` with a short description of the problem and proposed approach.
2. Interested parties comment for a minimum of **5 business days**.
3. If consensus emerges, convert the RFC into an ADR and proceed with implementation.
4. If consensus does not emerge, note the outcome in the issue and close it.

RFCs are lightweight — a well-described issue is sufficient. A formal document template is not required.

### Governance and audit changes

Changes to the approval gate, audit event schema, permission modes, or tool classification algorithm are treated as breaking changes even if they are additive (e.g. a new permission mode), because they change the security posture of existing deployments. All such changes need an ADR.

---

## Code of conduct

See [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md).

---

## Security reports

Do not open public issues for security-sensitive findings. Follow the process in [SECURITY.md](../../SECURITY.md).
